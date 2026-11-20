import datetime as dt,hashlib,json,os,stat,sys,tarfile
from pathlib import Path

e=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
cfg=e/'d306-continuation-1/launch-configuration.json'
assert hashlib.sha256(cfg.read_bytes()).hexdigest()=='bf817971e193d8e4fa1e1ba0ba947583467561aa95a6a1f64db259571c43d6c0'
c=json.loads(cfg.read_bytes());root=Path(c['repository_root'])
assert root==e/'admission-root' and os.geteuid()==0
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|gz') as archive:
 files={}
 for member in archive:
  assert member.isfile() and not Path(member.name).is_absolute() and '..' not in Path(member.name).parts
  assert member.size<4*1024**2
  files[member.name]=archive.extractfile(member).read()
raw=files.pop('installation-manifest.json')
assert hashlib.sha256(raw).hexdigest()=='277ce6f77354cdf0564a05712af6c3a429ed71950e65f8176a1d327abec4ad80'
manifest=json.loads(raw)
assert manifest['schema_version']=='software-d307-additive-admission-packet/1'
assert len(manifest['files'])==14 and len(files)==14 and manifest['overwrite_existing'] is False
assert manifest['source_revision']=='241b844cabcc58fee869ed186779a726705855ae'
for row in manifest['files']:
 raw=files[row['path']];assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
old=json.loads((root/'config/stage17/stage17-operational-evidence-admission-policy-v63.json').read_bytes())
old_bindings={b['path']:b for group in ('bindings','runtime_closure') for b in old[group].values()}
assert not (set(files)&set(old_bindings))
def unchanged():
 result=[]
 for name,b in sorted(old_bindings.items()):
  p=root/name;assert not p.is_symlink() and stat.S_ISREG(p.stat().st_mode)
  raw=p.read_bytes();assert len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],name
  result.append(dict(path=name,size_bytes=len(raw),sha256=b['sha256']))
 return hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
before=unchanged()
for row in manifest['files']:
 rel=row['path'];target=root/rel
 assert not target.exists() and not target.is_symlink(),rel
 for parent in reversed(target.parent.relative_to(root).parents):
  p=root/parent
  if not p.exists():p.mkdir(mode=0o555);os.chown(p,1000,1000)
 if not target.parent.exists():target.parent.mkdir(mode=0o555);os.chown(target.parent,1000,1000)
 assert all(not p.is_symlink() for p in (target.parent,*target.parent.parents))
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o444)
 with os.fdopen(fd,'wb') as stream:
  stream.write(files[rel]);stream.flush();os.fsync(stream.fileno());os.fchown(stream.fileno(),1000,1000);os.fchmod(stream.fileno(),0o444)
after=unchanged();assert before==after
result=dict(status='D307_ADDITIVE_ADMISSION_FILES_INSTALLED',checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
 source_revision=manifest['source_revision'],added_files=manifest['files'],inherited_file_count=len(old_bindings),
 inherited_aggregate_sha256=before,inherited_files_unchanged=True,qualified_bundle_modified=False,
 new_measurements=0,raw_data_read=False,phase18_authority=False)
path=e/'d307-admission-install-1.json'
with path.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
os.chown(path,1000,1000)
print(json.dumps(result),flush=True)
