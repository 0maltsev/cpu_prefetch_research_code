"""One approved D282 window and exact once-only qualification/handoff launch."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');P=E/'q16c-configuration-1';Q=E/'operator-preparation-v29';R=E/'admission-root';O=E.with_name('local-authoring-cpuprefetchv5-28');B=next((E/'local-bundle-extract').iterdir());D=E/'owner-decision-1'
assert os.geteuid()==0
sys.path.insert(0,str(P));import stage17_q16c_execution_window_v2 as window
def binding(p):
 p=Path(p);assert not any(q.is_symlink() for q in (p,*p.parents));raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(p):return json.loads(Path(p).read_bytes())
def save(p,x,canonical=False):
 raw=window.canonical(x) if canonical else json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 os.chown(p,1000,1000)
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return binding(p)
c=load(E/'d282-launch-preparation-1.json');assert binding(E/'d282-launch-preparation-1.json')['sha256']=='8afa519b9975d15a085ba16e64e8dca61e815c53abe64b6f4ac0a6c20996d543'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==window.BOOT
assert len(list((E/'journal').glob('*.json')))==1
assert not (E/'qualification-family-intent-1.json').exists() and not (E/'q16c-study-1').exists() and not (E/'d282-execution-window-1').exists()
for b in c['files'].values():assert binding(b['path'])==b
assert binding(P/'manifest.json')['sha256']=='731e59e84edd1a56d1ea54d37ba055dffc990d09f88b6ea83084214c8f6f023a'
assert binding(Q/'preparation-inventory.json')['sha256']=='f4b5c4c6fbac24b392de34af34359ee4096064137b20d341b00d133887fbcc76'
sys.path.insert(0,str(Q));from install_v29 import verify_packet
verify_packet(Q,'f4b5c4c6fbac24b392de34af34359ee4096064137b20d341b00d133887fbcc76',installed=True)
storage=load(E/'d282-storage-prelaunch-1.json');assert storage['status']=='PASS' and storage['old_program_quiescent'] is True
ledger=storage['ledger'];assert binding(Path(c['program_root'])/'ledger'/ledger['file_name'])['sha256']==ledger['sha256']
fs=os.statvfs(c['program_root']);assert fs.f_bavail*fs.f_frsize>=storage['required_free_bytes']
plan=load(P/'plan.json');assert len(plan['captures'])==180 and plan['source_revision']==window.SOURCE
size=load(E/'software-sizing-3/complete.json');assert size['status']=='ALL_180_CORRECTED_NATIVE_LAYOUTS_VERIFIED' and len(size['layouts'])==180 and size['plan']['sha256']==binding(P/'plan.json')['sha256']
old=load(O/'q16c-d277-launch-inputs-1.json');source=load(c['files']['source_manifest']['path']);original_complete=load(c['files']['source_completion']['path'])
lineage=dict(source_manifest=c['files']['source_manifest'],source_signature=original_complete['signature'],sizing=binding(E/'software-sizing-3/complete.json'),acceptance=binding(D/'owner-acceptance.json'),decision=binding(D/'0282-q16c-empty-attempt-corrected-release-continuation-proposal.md'),plan=binding(P/'plan.json'),qualified_inventory=binding(B/'BUNDLE_INVENTORY.json'),qualified_worker=c['worker'],administrative_manifest=c['files']['manifest'],original_execution_window=old['files']['execution_window'],source_reuse=c['files']['source_reuse'])
assert set(lineage)==window.ROLES and lineage['decision']['sha256']==window.DECISION_SHA
for b in lineage.values():assert binding(b['path'])==b
start=time.monotonic_ns();stamp=datetime.datetime.now(datetime.timezone.utc)
record=dict(schema_version=window.SCHEMA,execution_window_id=window.IDENTITY,decision_id='D282',source_revision=window.SOURCE,worker_sha256=window.WORKER,boot_id=window.BOOT,stand_id=plan['stand_id'],started_monotonic_ns=start,global_deadline_ns=start+86400*10**9,started_at_utc=stamp.isoformat().replace('+00:00','Z'),bindings=lineage,qualification_seconds=7200,family_seconds=47820,analysis_seconds=5400,restoration_seconds=2400,automatic_retries=0,new_windows_allowed=0,execution_authority=False,phase18_authority=False)
window.validate(record,now=time.monotonic_ns(),qualification=True)
W=E/'d282-execution-window-1';W.mkdir(mode=0o700);os.chown(W,1000,1000);wb=save(W/'window.json',record,canonical=True)
r=subprocess.run(['runuser','-u','omaltsev','--','ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',wb['path']],capture_output=True,timeout=30)
save(W/'signing-result.json',dict(exit_code=r.returncode,stdout=r.stdout.decode(errors='replace'),stderr=r.stderr.decode(errors='replace')));assert r.returncode==0
signature=binding(W/'window.json.sig');proof=dict(manifest=wb,signature=signature)
verification="import json,sys;from pathlib import Path;sys.path.insert(0,"+repr(str(R/'tools'))+");import stage17_phase_controller_v2 as v; x=json.loads(Path("+repr(str(E/'source-bank-reuse-3/original-context.json'))+").read_bytes());v._verify_signature(Path("+repr(wb['path'])+").read_bytes(),Path("+repr(signature['path'])+"),x['resolutions']['S17-EXT-003']['semantic_context']['trust']);print('OWNER_SIGNATURE_VERIFIED')"
v=subprocess.run(['runuser','-u','omaltsev','--','python3','-B','-c',verification],check=True,capture_output=True,text=True,timeout=30)
save(W/'complete.json',dict(status='OWNER_SIGNED_SEPARATE_EXECUTION_WINDOW',proof=proof,original_timestamps_unchanged=True,source_generation_repeated=False,signature_verification=v.stdout,automatic_retries=0,phase18_authority=False))
save(E/'continuation-window-1.json',dict(boot_id=window.BOOT,execution_window=wb,qualification_deadline_monotonic_ns=start+7200*10**9,global_deadline_ns=record['global_deadline_ns'],automatic_retries=0))
c['files']['execution_window']=wb;c['files']['execution_window_signature']=signature;cb=save(E/'q16c-d282-launch-inputs-1.json',c)
memlock=max(cap['resources']['total_mapping_bytes'] for cap in plan['captures']);now=time.monotonic_ns();remaining=(record['global_deadline_ns']-now)//10**9
assert remaining>62820
launcher=P/'launch_stage17_q16c_after_qualification_v4.py';auto=['systemd-run','--unit=cpu-prefetch-q16c-d282-after-qualification-v29-1','--property=Restart=no','--property=TimeoutStopSec=2400','--property=RuntimeMaxSec='+str(remaining-2400),'--property=LimitMEMLOCK='+str(memlock),'--setenv=PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-B',str(launcher),'--configuration',cb['path'],'--configuration-sha256',cb['sha256'],'--operator-sha256',binding(launcher)['sha256']]
qualification=['systemd-run','--unit=cpu-prefetch-q16c-d282-qualification-v29-1','--property=Restart=no','--property=TimeoutStopSec=2400','--property=RuntimeMaxSec='+str((start+7200*10**9-now)//10**9),'--property=LimitMEMLOCK=8388608','--setenv=PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-B',str(Q/'run_qualification_v29.py'),'--all','--packet-inventory-sha256','f4b5c4c6fbac24b392de34af34359ee4096064137b20d341b00d133887fbcc76']
save(E/'d282-native-launch-intent-1.json',dict(configuration=cb,qualification_argv=qualification,handoff_argv=auto,approximate_complete_ceiling_seconds=62820,estimated_ceiling_at_utc=(stamp+datetime.timedelta(seconds=62820)).isoformat(),global_deadline_at_utc=(stamp+datetime.timedelta(days=1)).isoformat(),automatic_retries=0,phase18_authority=False))
subprocess.run(auto,check=True,capture_output=True,timeout=30)
try:subprocess.run(qualification,check=True,capture_output=True,timeout=30)
except BaseException:
 subprocess.run(['systemctl','stop','cpu-prefetch-q16c-d282-after-qualification-v29-1.service'],capture_output=True,timeout=30);raise
status=dict(status='QUALIFICATION_STARTED_SUCCESS_ONLY_Q16C_HANDOFF_ARMED',configuration=cb,started_at_utc=record['started_at_utc'],estimated_ceiling_at_utc=(stamp+datetime.timedelta(seconds=62820)).isoformat(),global_deadline_at_utc=(stamp+datetime.timedelta(days=1)).isoformat(),memlock_bytes=memlock,automatic_retries=0,phase18_authority=False)
save(E/'d282-native-launch-complete-1.json',status);print(json.dumps(status),flush=True)
