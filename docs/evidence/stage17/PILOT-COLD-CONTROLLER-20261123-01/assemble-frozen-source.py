from pathlib import Path
import subprocess,tarfile,io,json,hashlib
p=Path('build/stage17-s180-cold-operator-prep');root=p/'frozen-source-34247ce-1';root.mkdir()
rev='34247cedab4abe4b44732daae8fdac1700eccffd';raw=subprocess.check_output(['git','archive',rev,'include','src','tools'])
with tarfile.open(fileobj=io.BytesIO(raw)) as t:
 assert all(m.isfile() or m.isdir() for m in t.getmembers());t.extractall(root,filter='data')
rows=[]
for f in sorted(root.rglob('*')):
 if f.is_dir():continue
 raw=f.read_bytes();rows.append(dict(path=str(f.relative_to(root)),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
m=json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-frozen-native-source-package/1',source_revision=rev,source_clean_snapshot=True,files=rows,execution_authority=False),sort_keys=True,separators=(',',':')).encode()
(root/'FROZEN_SOURCE_MANIFEST.json').write_bytes(m)
archive=p/'frozen-source-34247ce-1.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=3) as t:
 for f in sorted(root.rglob('*')):t.add(f,arcname=str(f.relative_to(root)),recursive=False)
result=dict(files=len(rows)+1,payload_bytes=sum(x['size_bytes'] for x in rows),manifest_sha256=hashlib.sha256(m).hexdigest(),transport_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),transport_size_bytes=archive.stat().st_size)
(p/'frozen-source-assembly.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result))
