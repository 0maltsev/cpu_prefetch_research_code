"""One D260 qualification; wait finitely for an independently admitted study.

Root supervisor. It records the sole24h anchor before admission initialization,
never performs Q16, and restores isolation if qualification or handoff fails.
"""
import argparse,datetime as dt,hashlib,importlib.util,json,os,pathlib,signal,subprocess,time
ROOT=pathlib.Path('/home/omaltsev/stage17-owner-evidence')
BOOT='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
B=ROOT/'v27-bootstrap-1';E=ROOT/'local-authoring-cpuprefetchv5-27';P=E/'operator-preparation-v27'
INVENTORY='7eaa83f6bf303b15f43834a7c236aed1378cd8b361c299b3da6c43f6a8f37e90'
PREFIX=dict(path=str(ROOT/'local-authoring-cpuprefetchv5-26/d260-prefix-custody-complete-1/complete.json'),size_bytes=16540,sha256='24a2926078396c2efe43eac6ac06887ca7e54d562a587a9bced2f62c355cd202')
WATCHDOG_NS=55860*10**9;QUALIFICATION_NS=7200*10**9;ANALYSIS_NS=13500*10**9;CLEANUP_NS=1800*10**9;WINDOW_NS=86400*10**9

def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(p):
 with pathlib.Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path,maximum=131072):
 p=pathlib.Path(path);require(not p.is_symlink() and p.stat().st_size<=maximum,'bounded regular metadata required')
 return json.loads(p.read_bytes())
def retain(path,doc):
 raw=(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode()
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o440)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 os.chown(path,0,1000)
 fd=os.open(pathlib.Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def properties(unit):
 q=subprocess.run(['systemctl','show',unit,'-p','ActiveState','-p','MainPID','-p','Result','-p','ExecMainStatus','-p','ControlGroup','-p','InvocationID','-p','User'],capture_output=True,text=True,check=True,timeout=15)
 return dict(line.split('=',1) for line in q.stdout.splitlines())
def validate_anchor(anchor,now):
 require(anchor['boot_id']==BOOT and type(now) is int,'actual boot and monotonic clock required')
 start=anchor['started_monotonic_ns'];require(type(start) is int and 0<start<=now,'invalid window start')
 require(anchor['deadline_monotonic_ns']==start+WINDOW_NS,'24-hour deadline changed')
 require(anchor['qualification_deadline_monotonic_ns']==start+QUALIFICATION_NS,'qualification deadline changed')
 require(anchor['last_safe_collection_start_ns']==start+WINDOW_NS-WATCHDOG_NS-ANALYSIS_NS-CLEANUP_NS,'handoff deadline changed')
 require(now<anchor['last_safe_collection_start_ns'],'insufficient whole continuation budget remains')
def require_prefix():
 p=pathlib.Path(PREFIX['path']);require(p.stat().st_size==PREFIX['size_bytes'] and sha(p)==PREFIX['sha256'],'accepted17 prefix changed')
 d=load(p);require(d['status']=='PREFIX_17_VALID_CUSTODY_COMPLETE' and len(d['captures'])==17 and d['boot_id']==BOOT,'complete prefix required')
 for unit in ('cpu-prefetch-c16-custody-recovery-1.service','cpu-prefetch-prefix-custody-admission-1.service'):
  state=properties(unit);require(state['MainPID']=='0' and state['ControlGroup']=='' and state['Result']=='success' and state['ExecMainStatus']=='0','retained-prefix workers not successfully reaped')
def supervise(argv,deadline):
 child=subprocess.Popen(list(map(str,argv)),stdin=subprocess.DEVNULL,close_fds=True)
 try:
  remaining=(deadline-time.monotonic_ns())/10**9;require(remaining>0,'qualification deadline expired')
  require(child.wait(timeout=remaining)==0,'qualification child failed')
 finally:
  if child.poll() is None:
   child.terminate()
   child.wait(timeout=2400)  # original Q15 recovery before infrastructure cleanup

def main(expected_sha):
 require(os.getuid()==os.geteuid()==0,'root supervisor required')
 require(sha(__file__)==expected_sha,'qualification supervisor bytes changed')
 require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'boot changed')
 require(WATCHDOG_NS+QUALIFICATION_NS+ANALYSIS_NS+CLEANUP_NS<=WINDOW_NS,'finite envelope exceeds24h')
 installer=module('bound_v27_installer',B/'packet-1/install_v27.py');installer.verify_packet(B/'packet-1',INVENTORY)
 require_prefix();require(not E.exists(),'fresh qualification namespace required')
 require(not pathlib.Path('/run/cpu-prefetch-recovery-v27-qualified-1').exists(),'fresh isolation namespace required')
 for number in (25,26):
  unit=f'cpu-prefetch-recovery-v{number}-qualified-1.service';state=properties(unit)
  require(state['MainPID']=='0' and state['ControlGroup']=='' and state['ActiveState'] in ('inactive','failed'),'prior experiment isolation remains active')
 started=time.monotonic_ns()
 anchor=dict(schema_version='cpu-prefetch-stage17-d260-continuation-window/1',boot_id=BOOT,started_monotonic_ns=started,
  started_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),deadline_monotonic_ns=started+WINDOW_NS,
  qualification_deadline_monotonic_ns=started+QUALIFICATION_NS,last_safe_collection_start_ns=started+WINDOW_NS-WATCHDOG_NS-ANALYSIS_NS-CLEANUP_NS,
  suffix_watchdog_ns=WATCHDOG_NS,analysis_reserve_ns=ANALYSIS_NS,cleanup_reserve_ns=CLEANUP_NS,
  prefix=PREFIX,qualification_packet_sha256=INVENTORY,source_revision='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8',
  owner_proposal_sha256='ae6f7d141c0a439f0aa96a963166a63909a1441c5295bdd16be03d32a51114f1',automatic_retries=0,formal_execution_authority=False,phase18_authority=False)
 validate_anchor(anchor,started);retain(B/'continuation-window-1.json',anchor)
 def interrupted(number,frame):raise RuntimeError('qualification supervisor signal '+str(number))
 for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):signal.signal(sig,interrupted)
 try:
  supervise(['/usr/bin/python3','-B',B/'packet-1/install_v27.py','--bootstrap',B,'--packet-inventory-sha256',INVENTORY],anchor['qualification_deadline_monotonic_ns'])
  os.link(B/'continuation-window-1.json',E/'continuation-window-1.json');require(sha(E/'continuation-window-1.json')==sha(B/'continuation-window-1.json'),'anchor copy changed')
  for mode in ('--prerequisites','--qualify'):
   supervise(['/usr/bin/python3','-B',P/'run_qualification_v27.py',mode,'--packet-inventory-sha256',INVENTORY],anchor['qualification_deadline_monotonic_ns'])
  retain(B/'qualification-complete-1.json',dict(success=True,completed_monotonic_ns=time.monotonic_ns(),window_sha256=sha(B/'continuation-window-1.json'),collection_started=False))
  print('QUALIFICATION_COMPLETE_WAITING_FOR_SEPARATELY_ADMITTED103',flush=True)
  while True:
   validate_anchor(anchor,time.monotonic_ns())
   handoff=E/'collection-supervision-handoff-1.json'
   if handoff.exists():
    d=load(handoff);require(d['schema_version']=='cpu-prefetch-stage17-d260-supervision-handoff/1' and d['window_sha256']==sha(B/'continuation-window-1.json') and d['unit']=='cpu-prefetch-q16b-v27-study-1.service','incorrect collection supervision handoff')
    state=properties(d['unit']);require(state['ActiveState']=='active' and state['MainPID']==str(d['main_pid']) and state['InvocationID']==d['invocation_id'] and state['User'] in ('','root'),'collection root supervision not actually owned')
    require(d['global_deadline_ns']==anchor['deadline_monotonic_ns'] and d['remaining_capture_count']==103 and d['cleanup_owned'] is True,'collection deadline/cleanup binding differs')
    retain(B/'supervision-transferred-1.json',dict(handoff_sha256=sha(handoff),unit=state,completed_monotonic_ns=time.monotonic_ns()))
    return
   time.sleep(5)
 except BaseException as error:
  result=dict(error=repr(error),automatic_retry=False,completed_monotonic_ns=time.monotonic_ns())
  try:
   isolation_path=P/'run_clock_qualification_v27.py'
   pre=E/'isolation-preparation-v27-1/prospective-prestate.json'
   if isolation_path.exists() and pre.exists():
    isolation=module('bound_v27_cleanup',isolation_path);isolation.configure(isolation.BINDINGS)
    isolation.cleanup_after_external_failure(error,quiescence_timeout_seconds=120)
    result['infrastructure_cleanup_completed']=True
   else:result['infrastructure_preparation_not_started']=True
  except BaseException as cleanup:result['cleanup_error']=repr(cleanup)
  retain(B/'qualification-supervision-failure-1.json',result)
  raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--operator-sha256',required=True);a=p.parse_args();main(a.operator_sha256)
