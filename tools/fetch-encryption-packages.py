import urllib.request,tarfile,io,json,hashlib,re
from pathlib import Path
root=Path('/home/a/mktel'); out=root/'artifacts/packages'
base='https://dl-cdn.alpinelinux.org/alpine/v3.23/main/aarch64/'
data=urllib.request.urlopen(base+'APKINDEX.tar.gz').read()
with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as t: index=t.extractfile('APKINDEX').read().decode()
def records(s):
 result=[]
 for block in s.split('\n\n'):
  item=dict(l.split(':',1) for l in block.splitlines() if ':' in l)
  if 'P' in item:result.append(item)
 return result
pkgs=records(index); names={p['P']:p for p in pkgs}; providers={}
for p in pkgs:
 providers[p['P']]=p
 for v in p.get('p','').split(): providers.setdefault(re.split(r'[=<>~]',v)[0],p)
with tarfile.open(root/'artifacts/alpine-minirootfs-aarch64.tar.gz') as t:
 member=next(m for m in t.getmembers() if m.name.lstrip('./')=='lib/apk/db/installed')
 installed=records(t.extractfile(member).read().decode())
have=set()
for p in installed:
 have.add(p['P']);have.update(re.split(r'[=<>~]',v)[0] for v in p.get('p','').split())
selected={}
def need(dep):
 dep=re.split(r'[=<>~]',dep)[0]
 if dep.startswith('!') or dep in have:return
 p=providers.get(dep)
 if p is None:raise Exception('Unresolved dependency '+dep)
 if p['P'] in selected:return
 selected[p['P']]=p
 for d in p.get('D','').split():need(d)
for p in ['cryptsetup','e2fsprogs','e2fsprogs-extra']:need(p)
for name,p in selected.items():
 filename=name+'-'+p['V']+'.apk'; payload=urllib.request.urlopen(base+filename).read()
 path=out/filename;path.write_bytes(payload)
 (out/(name+'.json')).write_text(json.dumps({'url':base+filename,'sha256':hashlib.sha256(payload).hexdigest(),'package':p},indent=2)+'\n')
 print(name,p['V'],len(payload))
with tarfile.open(root/'artifacts/encryption-packages.tar','w') as t:
 for name,p in selected.items():
  path=out/(name+'-'+p['V']+'.apk');t.add(path,arcname=path.name)
(root/'artifacts/encryption-packages.json').write_text(json.dumps(list(selected.values()),indent=2)+'\n')
print('Total archive bytes',(root/'artifacts/encryption-packages.tar').stat().st_size)
