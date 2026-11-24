from pathlib import Path
import hashlib,json,os,tarfile,time,stat
source=Path('/tmp/cpu-prefetch-s180-common-0919b87-1.tar.gz');destination=Path('/opt/cpu-prefetch-s180-common-0919b87-1')
start=time.monotonic_ns();assert os.geteuid()==0 and destination.is_dir() and not destination.is_symlink()
assert source.stat().st_size==64307039 and hashlib.sha256(source.read_bytes()).hexdigest()=='425d6b3679f669c1172a5d58f789b3df7891ebfba4a91f426221e21230c2bc57'
manifest=destination/'S180_COLD_SOURCE_MANIFEST.json';raw=manifest.read_bytes()
assert len(raw)==1211592 and hashlib.sha256(raw).hexdigest()=='bccde38abc2d97181f20100e18a2f5e1e8e62e4d41683c8ec497fb4d63fbcd7d'
d=json.loads(raw);assert d['source_revision']=='0919b87fe18185a27440b49df2f9a2fbee1e12dd' and d['source_clean_verified'] is True
actual={str(f.relative_to(destination)) for f in destination.rglob('*') if f.is_file()}
assert actual=={r['path'] for r in d['files']}|{manifest.name}
for r in d['files']:
 p=destination/r['path'];s=p.stat(follow_symlinks=False)
 assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and s.st_size==r['size_bytes'] and stat.S_IMODE(s.st_mode) in (r['mode'],r['mode']|0o200)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
 fd=os.open(p,os.O_RDONLY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
# All original payload hashes passed before any permission finalization.
for r in d['files']:
 p=destination/r['path'];p.chmod(r['mode'])
 assert stat.S_IMODE(p.stat().st_mode)==r['mode']
manifest.chmod(0o444)
for p in [destination,*[q for q in destination.rglob('*') if q.is_dir()]]:
 p.chmod(0o555);fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
fd=os.open(manifest,os.O_RDONLY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
fd=os.open(destination.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);os.fsync(fd);os.close(fd)
source.unlink()
print(json.dumps(dict(status='COLD_COMMON_SOFTWARE_INSTALLED_VERIFIED',root=str(destination),source_revision=d['source_revision'],manifest_sha256=hashlib.sha256(raw).hexdigest(),payload_files=len(d['files']),elapsed_ns=time.monotonic_ns()-start,original_transport_verified_then_removed=True,initial_filter_owner_write_bit_removed=True,actual_experiment_namespace_created=False,source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True,indent=2))
