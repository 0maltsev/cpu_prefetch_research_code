from pathlib import Path
import hashlib,tarfile,json,stat,os,time
source=Path('/tmp/cpu-prefetch-s180-frozen-source-34247ce-1.tar.gz');root=Path('/opt/cpu-prefetch-s180-native-sources-34247ce-1');started=time.monotonic_ns()
assert os.geteuid()==0 and not root.exists() and not root.is_symlink()
assert source.stat().st_size==2957874 and hashlib.sha256(source.read_bytes()).hexdigest()=='f4aee69461d45a9cb0cbae657cf35e58dde08a095091ebbe00259d085b833837'
root.mkdir(mode=0o755)
with tarfile.open(source) as t:
 rows=t.getmembers();assert len(rows)<5000 and all(m.isdir() or m.isfile() for m in rows)
 assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in rows)
 t.extractall(root,filter='data')
m=root/'FROZEN_SOURCE_MANIFEST.json';raw=m.read_bytes();assert hashlib.sha256(raw).hexdigest()=='bd86f1b81686ab119607868cb64f94f6617e620fa82e93750b9877e6ba1c578b'
d=json.loads(raw);assert d['source_revision']=='34247cedab4abe4b44732daae8fdac1700eccffd'
assert {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}=={r['path'] for r in d['files']}|{m.name}
for r in d['files']:
 p=root/r['path'];s=p.stat(follow_symlinks=False);assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and not s.st_mode&0o022 and s.st_size==r['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
for p in [m,*[root/r['path'] for r in d['files']]]:
 p.chmod(0o444);fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
for p in [root,*[q for q in root.rglob('*') if q.is_dir()]]:
 p.chmod(0o555);fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
source.unlink()
print(json.dumps(dict(status='FROZEN_NATIVE_SOURCE_AND_TOOL_CLOSURE_INSTALLED',root=str(root),files=len(d['files']),manifest_sha256=hashlib.sha256(raw).hexdigest(),elapsed_ns=time.monotonic_ns()-started,source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False),sort_keys=True,indent=2))
