"""A dedicated binary-only repository. Latest catalog is the retention authority."""
import json, os, re, urllib.request

def cleanup_plan(catalog, releases, repository):
    versions=[r['version'] for r in catalog['releases']]
    assert catalog['schema']==1 and catalog['package']=='kr.callnote.app'
    assert 1<=len(versions)<=3 and len(set(versions))==len(versions)
    assert all(re.fullmatch(r'\d+\.\d+\.\d+',v) for v in versions)
    assert versions==sorted(versions,key=lambda v:tuple(map(int,v.split('.'))),reverse=True)
    live=next(r for r in releases if r['tag_name']=='v'+versions[0] and not r['draft'])
    assert len([a for a in live['assets'] if a['name']=='catalog.json'])==1
    for entry in catalog['releases']:
        assert entry['code']==catalog['generation']
        asset=next(a for a in live['assets'] if a['name']==f"CallNote-{entry['version']}.apk")
        assert asset['size']==entry['size'] and entry['sha256']==asset['digest'].removeprefix('sha256:')
        assert entry['url']==asset['browser_download_url']
        assert entry['url'].startswith(f'https://github.com/{repository}/releases/download/')
    keep={'v'+v for v in versions}
    delete_releases=[r for r in releases if re.fullmatch(r'v\d+\.\d+\.\d+',r['tag_name']) and r['tag_name'] not in keep and not r['draft']]
    allowed={f'CallNote-{v}.apk' for v in versions}
    delete_assets=[a for r in releases if r not in delete_releases and not r['draft'] for a in r['assets'] if a['name'].endswith('.apk') and a['name'] not in allowed]
    return delete_releases,delete_assets

def main():
    repo=os.environ['GITHUB_REPOSITORY']
    base=f'https://api.github.com/repos/{repo}'
    def api(path,method='GET'):
        req=urllib.request.Request(base+path,method=method,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'CallNote-release-retention','X-GitHub-Api-Version':'2022-11-28'})
        with urllib.request.urlopen(req,timeout=60) as r:
            data=r.read();return json.loads(data) if data else None
    latest=api('/releases/latest')
    asset=next(a for a in latest['assets'] if a['name']=='catalog.json')
    with urllib.request.urlopen(asset['browser_download_url'],timeout=60) as r: catalog=json.load(r)
    assert latest['tag_name']=='v'+catalog['releases'][0]['version']
    releases=[]
    for page in range(1,100):
        batch=api(f'/releases?per_page=100&page={page}');releases.extend(batch)
        if len(batch)<100:break
    remove,assets=cleanup_plan(catalog,releases,repo)
    # No deletion happens before the complete new catalog and all APKs validate.
    for a in assets:
        api('/releases/assets/'+str(a['id']),'DELETE');print('Removed obsolete APK:',a['name'])
    for r in remove:
        api('/releases/'+str(r['id']),'DELETE')
        api('/git/refs/tags/'+r['tag_name'],'DELETE');print('Removed old release and tag:',r['tag_name'])
    print('Retained product versions:',', '.join(x['version'] for x in catalog['releases']))

if __name__=='__main__':main()
