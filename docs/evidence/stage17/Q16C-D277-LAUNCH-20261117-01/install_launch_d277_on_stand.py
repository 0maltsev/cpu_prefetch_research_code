"""Install reviewed D277 Q15 bindings, arm success-only Q16c handoff, launch once."""
import datetime,hashlib,json,os,subprocess,sys,tarfile,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28');P=E/'q16c-configuration-2';Q=E/'operator-preparation-v28-3'
INV='1c9889681ee28551ed2162794d7393fa78b0f6a0ceb5d0ed1cc81342bb98710d'
TAR='6c74bb7a962c92c4186d02f1c02cb2c66c9a518b8ac454aeb3538b8f6bcd8127'
MANIFEST='34f37eeeae416da7028fe868d05a49c7ceca83e1eb58066d32e1a38d5ac1dc15'
REV='ce40650a39a1fb088bd0223a0d9cb656d19d111a'
assert os.geteuid()==0

def binding(path):
 raw=path.read_bytes();return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(path):return json.loads(path.read_bytes())
def save(path,value):
 with path.open('x') as f:json.dump(value,f,sort_keys=True,separators=(',',':'),allow_nan=False);f.flush();os.fsync(f.fileno())
 os.chown(path,1000,1000)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return binding(path)
window=load(E/'d277-execution-window-1/window.json');complete=load(E/'d277-execution-window-1/complete.json')
assert binding(E/'d277-execution-window-1/window.json')==complete['proof']['manifest']
assert binding(E/'d277-execution-window-1/window.json.sig')==complete['proof']['signature']
assert complete['status']=='OWNER_SIGNED_SEPARATE_EXECUTION_WINDOW'
assert binding(P/'manifest.json')['sha256']==MANIFEST
assert not Q.exists() and not list(E.glob('stage17-q15*')) and not (E/'q16c-study-1').exists()
tarpath=E.parent/'q16c-d277-qualification-ce40650-5.tar';assert binding(tarpath)['sha256']==TAR
Q.mkdir(mode=0o700);os.chown(Q,1000,1000)
with tarfile.open(tarpath) as tar:
 for member in tar.getmembers():
  assert member.isfile() and Path(member.name).name==member.name
  path=Q/member.name
  with path.open('xb') as f:f.write(tar.extractfile(member).read())
  os.chown(path,1000,1000);os.chmod(path,0o444)
sys.path.insert(0,str(Q));from install_v28 import verify_packet,PUBLIC
rows=[]
for old,new,digest in PUBLIC:
 src=E/'operator-preparation-v28-2'/new;assert binding(src)['sha256']==digest
 dst=Q/new
 with dst.open('xb') as f:f.write(src.read_bytes());f.flush();os.fsync(f.fileno())
 os.chown(dst,1000,1000);os.chmod(dst,0o444);rows.append(dict(original_path=str(src),**binding(dst)))
save(Q/'original-public-inputs-reuse.json',dict(original_records_unchanged=True,new_search_claimed=False,files=rows))
verify_packet(Q,INV,installed=True)
finite=load(Q/'finite-qualification-plan.json')
assert finite['finite_scope']['near_clock_max']==finite['finite_scope']['far_clock_max']==0
assert finite['qualification_budget_seconds']==7200
assert time.monotonic_ns()<finite['preparation_latest_qualify_start_monotonic_ns']
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==window['boot_id']
save(E/'d277-qualification-window-1.json',dict(boot_id=window['boot_id'],execution_window=complete['proof']['manifest'],
 qualification_deadline_monotonic_ns=window['started_monotonic_ns']+7200*10**9,global_deadline_ns=window['global_deadline_ns'],
 clock_measurements_repeated=False,automatic_retries=0))
c=load(E/'q16c-launch-inputs-1.json');c.update(administrative_source_revision=REV,packet_root=str(P))
for key,name in dict(action_operator='stage17_q16c_operator_v1.py',geometry_provenance='native-geometry-provenance.json',loader='stage17_q16c_packet_v2.py',local_audit='local-namespace-audit.json',manifest='manifest.json',ownership_core='original_supervisor.py',preparation_operator='stage17_q16c_prepare_v2.py',restoration_helper='stage17_q16c_restoration_v1.py',study_driver='stage17_q16c_study_v3.py',window_helper='stage17_q16c_execution_window_v1.py',execution_owner_guard='check_stage17_execution_owner_v1.py',frozen_plan='plan.json').items():c['files'][key]=binding(P/name)
c['files']['clock_adapter']=binding(Q/'run_clock_qualification_v28.py')
c['files']['execution_window']=complete['proof']['manifest'];c['files']['execution_window_signature']=complete['proof']['signature']
cb=save(E/'q16c-d277-launch-inputs-1.json',c)
plan=load(P/'plan.json');memlock=max(cap['resources']['total_mapping_bytes'] for cap in plan['captures'])
now=time.monotonic_ns();remaining=(window['global_deadline_ns']-now)//10**9
assert remaining>62820 and memlock>0
launcher=P/'launch_stage17_q16c_after_qualification_v3.py'
auto=['systemd-run','--unit=cpu-prefetch-q16c-d277-after-qualification-v28-1','--property=Restart=no',
 '--property=TimeoutStopSec=2400','--property=RuntimeMaxSec='+str(remaining-2400),'--property=LimitMEMLOCK='+str(memlock),
 '--setenv=PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-B',str(launcher),'--configuration',cb['path'],
 '--configuration-sha256',cb['sha256'],'--operator-sha256',binding(launcher)['sha256']]
qualification=['systemd-run','--unit=cpu-prefetch-q16c-d277-qualification-v28-1','--property=Restart=no',
 '--property=TimeoutStopSec=2400','--property=RuntimeMaxSec='+str((window['started_monotonic_ns']+7200*10**9-now)//10**9),
 '--property=LimitMEMLOCK=8388608','--setenv=PYTHONDONTWRITEBYTECODE=1','/usr/bin/python3','-B',str(Q/'run_qualification_v28.py'),
 '--qualify','--packet-inventory-sha256',INV]
save(E/'d277-native-launch-intent-1.json',dict(configuration=cb,qualification_argv=qualification,handoff_argv=auto,
 approximate_complete_ceiling_seconds=62820,automatic_retries=0,source_and_clock_measurements_repeated=False,
 original_global_deadline_unchanged=True,phase18_authority=False))
subprocess.run(auto,check=True,capture_output=True,timeout=30)
try:subprocess.run(qualification,check=True,capture_output=True,timeout=30)
except BaseException:
 subprocess.run(['systemctl','stop','cpu-prefetch-q16c-d277-after-qualification-v28-1.service'],capture_output=True,timeout=30)
 raise
save(E/'d277-native-launch-complete-1.json',dict(status='QUALIFICATION_STARTED_SUCCESS_ONLY_Q16C_HANDOFF_ARMED',
 configuration=cb,qualification_inventory_sha256=INV,started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 automatic_retries=0,phase18_authority=False))
print(json.dumps(dict(status='QUALIFICATION_STARTED_SUCCESS_ONLY_Q16C_HANDOFF_ARMED',configuration=cb,memlock_bytes=memlock)),flush=True)
