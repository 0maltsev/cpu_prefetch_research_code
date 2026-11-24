"""Launch once only after signed preparation completes; original clock retained."""
import datetime,hashlib,json,os,pathlib,subprocess,time
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27');B=E.parent/'v27-bootstrap-1';OP=B/'d268-operators-2';CFG=OP/'configuration.json';O=E/'d267-admission-preparation-3'
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def props(unit):return dict(line.split('=',1) for line in subprocess.run(['systemctl','show',unit,'-p','MainPID','-p','ActiveState','-p','Result','-p','ExecMainStatus','-p','ControlGroup','-p','InvocationID'],check=True,capture_output=True,text=True).stdout.splitlines())
def save(p,v):
 with p.open('x') as f:json.dump(v,f,sort_keys=True,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.chmod(p,0o444)
require(os.geteuid()==0,'root launch required');require(sha(CFG)=='0e6ad4e71cd6740a79cc9f914bdfc52fea7edc5c9364c176bc8fbc436d27e021','reviewed configuration')
c=json.loads(CFG.read_bytes())
for b in c['files'].values():
 p=pathlib.Path(b['path']);require(not p.is_symlink() and p.stat().st_size==b['size_bytes'] and sha(p)==b['sha256'],'configuration source changed')
u=props('cpu-prefetch-d268-v27-signing-preparation-2.service');require(u['MainPID']=='0' and u['ControlGroup']=='' and u['Result']=='success' and u['ExecMainStatus']=='0' and u['ActiveState']=='inactive','signed preparation not successfully reaped')
require((O/'authority-supersession-complete.json').is_file(),'explicit unconsumed authority supersession')
d=json.loads((O/'prepared-phase.json').read_bytes());w=json.loads(pathlib.Path(c['files']['window']['path']).read_bytes());now=time.monotonic_ns()
require(now<w['deadline_monotonic_ns']-(56460+13500+1800)*10**9 and now<w['last_safe_collection_start_ns'],'complete remaining budget unavailable')
require(w['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'boot changed')
phase=pathlib.Path(d['output_root']);require(phase.name=='1ccafebafafea4b8491b4daf5b70f1065d1ea2c0b854d662bae388bfb031b2ba' and phase.is_dir() and not list(phase.iterdir()),'registered family not empty')
require(not (E/'d260-study-1').exists(),'study already consumed; no retry')
require(not pathlib.Path('/sys/fs/cgroup/cpu-prefetch-recovery-v27-qualified-1.service/reserved').exists(),'old isolation remains')
unit='cpu-prefetch-q16b-v27-study-1.service';require(props(unit)['MainPID']=='0','study already active')
remaining=(w['deadline_monotonic_ns']-now)//10**9
argv=['systemd-run','--unit='+unit,'--property=User=root','--property=RuntimeMaxSec='+str(remaining),'--property=TimeoutStopSec=2400','--property=KillMode=process','--property=MemoryMax=280G','--property=LimitAS=infinity','--property=LimitMEMLOCK=infinity','--property=StandardOutput=append:'+str(B/'collection-study-1.log'),'--property=StandardError=append:'+str(B/'collection-study-1.log'),'/usr/bin/python3','-B',str(OP/'run_d260_study.py'),'--run','--config',str(CFG),'--config-sha256','0e6ad4e71cd6740a79cc9f914bdfc52fea7edc5c9364c176bc8fbc436d27e021']
save(B/'collection-launch-intent-1.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),monotonic_ns=now,original_window=c['files']['window'],global_deadline_ns=w['deadline_monotonic_ns'],approximate_whole_family_hours=[11,15],argv=argv,automatic_retries=0,remaining_captures=103,original_captures_reused=17,qualification_repeated=False))
subprocess.run(argv,check=True);state=props(unit);require(int(state['MainPID'])>1 and state['ActiveState']=='active','study did not start')
save(B/'collection-launch-result-1.json',dict(unit=unit,properties=state,observed_monotonic_ns=time.monotonic_ns(),native_collection_verified=False))
print(json.dumps(dict(status='ROOT_SUPERVISOR_STARTED_OWNER_ADMISSION_PENDING',properties=state)),flush=True)
