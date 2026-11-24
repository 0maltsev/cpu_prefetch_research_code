from pathlib import Path
import os,hashlib,io,json,tarfile,stat
source=Path('/tmp/cpu-prefetch-s180-service-7efa351.tar');raw=source.read_bytes()
assert len(raw)==317440 and hashlib.sha256(raw).hexdigest()=='d8c52e24816892175c131a5238750ae99d67d8e296dffb0f303c0e11d86f00bf'
root=Path('/opt/cpu-prefetch-s180-service-1')
original=root/'profile.json';assert hashlib.sha256(original.read_bytes()).hexdigest()=='44800f7dd6ae47fdf21ef3187cf0c346dc5bbd04fdbeb5f9fc19d3a4c493df7d'
assert not Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/s180-d310-1').exists()
retained=Path('/opt/cpu-prefetch-s180-service-170ad22-unstarted-1');assert not os.path.lexists(retained)
root.rename(retained)
assert not os.path.lexists(root)
with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:
 members=tf.getmembers();names=[m.name for m in members];assert len(names)==23 and len(set(names))==23
 assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and m.size<2*1024**2 for m in members)
 profile_raw=tf.extractfile('profile.json').read();assert len(profile_raw)==3280 and hashlib.sha256(profile_raw).hexdigest()=='548884312b7508d76d697863caf57ba0656ba0c2c114021e692c7c83c54df718'
 profile=json.loads(profile_raw);assert profile['source_revision']=='7efa351c4820790ff4a4d928da9023a0f2ef61bf'
 rows={r['path']:r for r in profile['files']};assert set(names)==set(rows)|{'profile.json'}
 root.mkdir(mode=0o755)
 for member in members:
  data=tf.extractfile(member).read();target=root/member.name
  if member.name!='profile.json':
   r=rows[member.name];assert len(data)==r['size_bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
  target.parent.mkdir(parents=True,exist_ok=True)
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
  try:
   assert os.write(fd,data)==len(data);os.fsync(fd)
  finally:os.close(fd)
  assert target.read_bytes()==data;target.chmod(0o444)
 for path in sorted(root.rglob('*'),key=lambda p:len(p.parts),reverse=True):
  if path.is_dir():path.chmod(0o555)
  fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
  try:os.fsync(fd)
  finally:os.close(fd)
 root.chmod(0o555)
 fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
source.unlink()
print(json.dumps(dict(status='CLEAN_SERVICE_SOFTWARE_INSTALLED',source_revision=profile['source_revision'],files=len(rows),profile_sha256=hashlib.sha256(profile_raw).hexdigest(),operational_window_started=False,qualification_performed=False,execution_authority=False)))
