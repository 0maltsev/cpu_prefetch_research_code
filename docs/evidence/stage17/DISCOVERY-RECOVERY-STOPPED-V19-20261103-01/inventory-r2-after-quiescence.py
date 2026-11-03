"""Original-byte inventory only after the approved R2 family has stopped/restored."""
import base64, datetime, hashlib, json, os, pathlib, stat, sys, time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
O=E/'discovery-output-r2-1'; Q=E/'admission-root/evidence/discovery-r2-fresh'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
supervisor_path=E/'discovery-supervisor-result-r2-1.json'
supervisor_raw=supervisor_path.read_bytes(); supervisor=json.loads(supervisor_raw)
assert type(supervisor['exit_code']) is int
assert supervisor['partition_procs']==''
assert supervisor['partition_restoration']['verified'] is True
assert supervisor['partition_restoration']['partition_absent'] is True
assert not pathlib.Path('/sys/fs/cgroup/cpu-prefetch-v5-clock-qualified-2').exists()
for record in ('discovery-supervisor-pid-r2-1.json','discovery-child-pid-r2-1.json'):
    pid=json.loads((E/record).read_bytes())['pid']; proc=pathlib.Path('/proc')/str(pid)
    for unused in range(10):
        if not proc.exists():break
        time.sleep(0.5)
    assert not proc.exists(),('recorded process still exists',pid)
started=utc();files=[];source_names=sorted(p.name for p in O.iterdir())
assert source_names
def item(path,name,embed):
    metadata=path.lstat();assert stat.S_ISREG(metadata.st_mode) and not path.is_symlink(),name
    h=hashlib.sha256()
    with path.open('rb') as f:
        before=os.fstat(f.fileno())
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
        after=os.fstat(f.fileno())
    assert (before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    result=dict(path=name,size_bytes=before.st_size,sha256=h.hexdigest())
    if embed:
        b=path.read_bytes();assert hashlib.sha256(b).hexdigest()==result['sha256']
        result['base64']=base64.b64encode(b).decode()
    return result
for ordinal,name in enumerate(source_names):
    files.append(item(O/name,name,(O/name).stat().st_size<=100000))
    print('HASHED',ordinal+1,len(source_names),name,file=sys.stderr,flush=True)
assert source_names==sorted(p.name for p in O.iterdir()),'output inventory changed'
operators=['discovery-supervisor-pid-r2-1.json','discovery-child-pid-r2-1.json',
 'discovery-supervisor-result-r2-1.json','discovery-launch-readback-r2-1.json',
 'discovery-launch-intent-r2-1.json','discovery-supervisor-prelaunch-r2-1.json',
 'discovery-session-r2-1.log','discovery-isolation-r2-1/prestate.json',
 'discovery-isolation-r2-1/isolation-verified.json','discovery-isolation-r2-1/restoration.json']
for name in operators:files.append(item(E/name,'operator/'+name,True))
for name in ['request.json','authorization.json','authorization.json.sig']:
    files.append(item(Q/name,'operator/signed-authority/'+name,True))
assert supervisor_path.read_bytes()==supervisor_raw
manifest=dict(observed_at_utc=utc(),started_at_utc=started,root=str(O),files=files)
raw=(json.dumps(manifest,indent=2)+'\n').encode()
audit=dict(root=str(O),inventory_sha256=hashlib.sha256(raw).hexdigest(),
 supervisor_result_sha256=hashlib.sha256(supervisor_raw).hexdigest(),observed_at_utc=utc(),
 post_quiescence=True,complete=True,regular_files_only=True,no_symlinks=True,errors=[],
 scope='Complete output inventory after recorded supervisor and controller are gone and partition restored; no scientific validation')
def retain(name,data):
    p=E/name
    with p.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    os.chown(p,1000,1000);p.chmod(0o400)
retain('r2-output-inventory.json',raw)
retain('r2-output-inventory-audit.json',(json.dumps(audit,indent=2)+'\n').encode())
sys.stdout.buffer.write(raw);sys.stdout.buffer.flush()
