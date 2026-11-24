from pathlib import Path
import datetime,hashlib,json,os,sys,time
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32');p=E/'d301-continuation-2'
f=p/'launch-configuration.json';assert hashlib.sha256(f.read_bytes()).hexdigest()=='7211b3618a386cd45ea095888cbaaac9e4a64002288bec37070ab98ff604987b'
assert os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups()
sys.path.insert(0,str(p));import stage17_q16c_continuation_operator_v1 as io
c=json.loads(f.read_bytes());assert not Path(c['cgroup']).exists()
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip()=='1'
cli,authority,args=io.common(c)
started=time.monotonic_ns();prepared=cli.verify_formal_signature(**args)
family=Path(prepared.request['evidence_root_binding']['absolute_path'])
assert not list(family.iterdir()) and not Path(c['cgroup']).exists()
result=dict(status='ACTUAL_SIGNED_FORMAL_PREPARATION_PASS_NO_EXECUTION',checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_ns=time.monotonic_ns()-started,request_sha256=hashlib.sha256(prepared.request_bytes).hexdigest(),authorization_sha256=hashlib.sha256(prepared.authorization_bytes).hexdigest(),runtime_sha256=prepared.runtime['sha256'],native_attempt_started=False,empty_family=True,executed=False,controls_rearmed=False,new_execution_window=False,execution_authority=False)
path=E/'d305-signed-admission-software-check-1.json'
with path.open('x') as f:json.dump(result,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
print(json.dumps(result),flush=True)
