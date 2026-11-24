"""Single collection-only D260 supervisor; preserved qualification, same clock."""
import argparse,hashlib,json,os,pathlib,resource,signal,subprocess,sys,time,traceback,types
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27')
O=E/'d265-admission-preparation-2';STUDY=E/'d260-study-1';OP=pathlib.Path(__file__).resolve().parent
CG=pathlib.Path('/sys/fs/cgroup/cpu-prefetch-recovery-v27-qualified-1.service/reserved')
CORE='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
SOURCE='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8';NANO=10**9

def require(ok,message):
 if not ok:raise RuntimeError(message)
def binding(p):
 raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(b):
 p=pathlib.Path(b['path']);require(p.is_absolute() and not any(q.is_symlink() for q in (p,*p.parents)),'nonsymlink binding')
 with p.open('rb') as f:
  before=os.fstat(f.fileno());require(0<before.st_size==b['size_bytes']<=128*1024**2,'bounded metadata');raw=f.read(before.st_size+1);after=os.fstat(f.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256'],'binding changed');return raw
def load(b):return json.loads(read(b))
def save(p,value):
 raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
 with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 if os.geteuid()==0:os.chown(p,1000,1000)
 fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
def module(name,b):
 m=types.ModuleType(name);m.__file__=b['path'];sys.modules[name]=m;exec(compile(read(b),m.__file__,'exec'),m.__dict__);return m

def configure(args):
 c=load(dict(path=str(args.config),size_bytes=args.config.stat().st_size,sha256=args.config_sha256))
 require(c['execution_authority'] is False and c['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'same boot')
 for b in c['files'].values():read(b)
 require(c['files']['driver']==binding(pathlib.Path(__file__)),'driver changed')
 w=load(c['files']['window']);require(w['deadline_monotonic_ns']-w['started_monotonic_ns']==86400*NANO,'original24h clock')
 require(w['source_revision']==SOURCE and w['boot_id']==c['boot_id'],'actual qualified source')
 helper=module('d260_owned_supervision',c['files']['original_supervisor'])
 require(c['files']['original_supervisor']['sha256']=='47e819dbcd6110d5b356d091e706141131efa5938b0ae0740059efc4d3cb1416','D258 ownership core')
 return c,w,helper

def prepared(c):
 pb=binding(O/'prepared-phase.json');d=load(pb)
 require(d['source_revision']==SOURCE and d['boot_id']==c['boot_id'] and d['execution_authority'] is False and d['phase18_authority'] is False,'actual prepared source')
 for b in (*d['files'].values(),*d['wrappers'].values(),d['worker']):read(b)
 plan=load(d['files']['plan']);request=load(d['files']['request']);auth=load(d['files']['authorization']);limits=load(d['files']['limits'])
 require(d['files']['plan']['sha256']=='d980ed9417ddf76e88931d849a62573971522b10604975c51f5fa709335698f4' and len(plan['captures'])==103 and plan['source_revision']==SOURCE and plan['budget']['watchdog_ns']==55860*NANO,'exact103')
 require(request['action_inputs']['plan']==plan and auth['request_binding']==d['files']['request'],'signed plan changed')
 require(d['output_root']==request['evidence_root_binding']['absolute_path'] and pathlib.Path(d['output_root']).name==d['files']['plan']['sha256'],'actual family root')
 require(d['worker']['sha256']=='5497678d637578843abaf5e9d708cecaebe3b26acd4f5b1da48c8fbf91835cb8','actual qualified worker')
 require(limits==dict(address_space_bytes=max(i['execution_budget']['memory_bytes'] for i in plan['captures']),memlock_bytes=max(i['resources']['total_mapping_bytes'] for i in plan['captures'])),'derived worker limits')
 for role,key in [('cli','cli_wrapper'),('owner_check','owner_check'),('analysis','analysis')]:require(d['wrappers'][role]==c['files'][key],'reviewed wrapper changed')
 return pb,d,request,limits

def owner(args,c,w,h):
 intent=json.loads((STUDY/'study-intent.json').read_bytes());require(os.getppid()==intent['supervisor_pid'] and h.start_ticks(os.getppid())==intent['supervisor_start_ticks'] and intent['configuration_sha256']==args.config_sha256,'actual dedicated parent required')
 pb,d,request,limits=prepared(c);native=args.role in ('check','collection');deadline=args.deadline_ns
 require(time.monotonic_ns()<deadline<=w['deadline_monotonic_ns'],'original absolute deadline')
 if args.owner:
  require(os.geteuid()==0 and len(list(pathlib.Path('/proc/self/task').iterdir()))==1,'single-threaded root handoff')
  resource.setrlimit(resource.RLIMIT_AS,((limits['address_space_bytes'] if native else 16*1024**3),)*2)
  resource.setrlimit(resource.RLIMIT_MEMLOCK,((limits['memlock_bytes'] if native else 8*1024**2),)*2)
  if native:
   require((CG/'cgroup.procs').read_text().strip()=='','fresh empty partition')
   with (CG/'cgroup.procs').open('w') as f:f.write(str(os.getpid())+'\n')
  os.sched_setaffinity(0,{2 if native else 3});names=h.CAP_NAMES if native else ('sys_ptrace',);caps='-all,'+','.join('+'+n for n in names)
  argv=['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups','--bounding-set='+caps,'--inh-caps='+caps,'--ambient-caps='+caps,sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--inner','--role',args.role,'--config',str(args.config),'--config-sha256',args.config_sha256,'--deadline-ns',str(deadline)]
  os.execv(argv[0],argv)
 require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(),'exact owner identity')
 mask=h.CAP_MASK if native else h.ANALYSIS_CAP_MASK;status=dict(line.split(':',1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
 require(all(int(status[k].strip(),16)==mask for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'exact owner capabilities')
 require(os.sched_getaffinity(0)=={2 if native else 3},'actual owner placement')
 if native:require(resource.getrlimit(resource.RLIMIT_AS)==(limits['address_space_bytes'],)*2 and resource.getrlimit(resource.RLIMIT_MEMLOCK)==(limits['memlock_bytes'],)*2,'actual owner limits')
 if args.role=='check':argv=[sys.executable,'-B',d['wrappers']['owner_check']['path'],'--prepared-phase',pb['path'],'--prepared-phase-sha256',pb['sha256'],'--global-deadline-ns',str(deadline)]
 elif args.role=='collection':
  q=json.loads((STUDY/'collection-intent.json').read_bytes());require(q['prepared_phase']==pb and q['deadline_ns']==deadline and q['owner_check_passed'] is True and q['automatic_retries']==0,'exact checked collection intent')
  cfg=load(d['files']['cli_configuration']);argv=[sys.executable,'-B',d['wrappers']['cli']['path'],'--configuration',d['files']['cli_configuration']['path'],'--configuration-sha256',d['files']['cli_configuration']['sha256'],'execute-formal','--repository-root',d['repository_root'],'--evidence-root',str(E),'--authorization',d['files']['authorization']['path'],'--signature',d['files']['signature']['path'],'--pilot-archive',cfg['archive']['path'],'--pilot-sidecar',cfg['sidecar']['path']]
 else:argv=[sys.executable,'-B',d['wrappers']['analysis']['path'],'--config',d['files']['analysis_config']['path'],'--config-sha256',d['files']['analysis_config']['sha256'],'--global-deadline-ns',str(deadline)]
 os.execv(argv[0],argv)

def run(args,c,w,h):
 require(os.geteuid()==0 and len(list(pathlib.Path('/proc/self/task').iterdir()))==1,'dedicated root required');os.sched_setaffinity(0,{3});require(not h.descendants(os.getpid()),'no unrelated children');h.subreaper()
 require(time.monotonic_ns()<w['last_safe_collection_start_ns'],'latest safe collection start passed');require(not STUDY.exists(),'one exclusive study; no retry');STUDY.mkdir();os.chown(STUDY,1000,1000)
 result=dict(schema_version='software-d260-collection-study/1',source_revision=SOURCE,configuration_sha256=args.config_sha256,supervisor_pid=os.getpid(),supervisor_start_ticks=h.start_ticks(os.getpid()),started_monotonic_ns=time.monotonic_ns(),global_deadline_ns=w['deadline_monotonic_ns'],automatic_retries=0,success=False,errors=[],phases=[],qualification_repeated=False,retained_captures=17,new_captures=103,ext007_admitted=False,phase18_authority=False)
 save(STUDY/'study-intent.json',result);active=None;iso=None;pre=None;restored=False;d=request=None
 def interrupted(number,frame):raise RuntimeError('study signal '+str(number))
 old={s:signal.signal(s,interrupted) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
 def command(role,deadline):
  nonlocal active
  configure(args);record=dict(phase=role,started_monotonic_ns=time.monotonic_ns(),deadline_ns=deadline)
  argv=[sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--owner','--role',role,'--config',str(args.config),'--config-sha256',args.config_sha256,'--deadline-ns',str(deadline)]
  pb,d,request,limits=prepared(c);native={(d['worker']['size_bytes'],d['worker']['sha256'])}
  try:
   with (STUDY/(role+'.log')).open('xb') as log:
    active=h.OwnedProcess(argv,log,native,protect_native=role in ('check','collection'));record['pid']=active.process.pid
    code=active.wait(deadline);record.update(exit_code=code,leader_reaped=True);require(code==0,role+' exit '+str(code));active=None
  except BaseException:
   record['failure_traceback']=traceback.format_exc(limit=20)[-32768:];raise
  finally:
   record['completed_monotonic_ns']=time.monotonic_ns();save(STUDY/(role+'-result.json'),record);result['phases'].append(record)
 try:
  pb,d,request,limits=prepared(c);phase=pathlib.Path(d['output_root']);require(not list(phase.iterdir()),'family already consumed')
  require(load(c['files']['qualification_complete'])['success'] is True and load(c['files']['original_restoration'])['verified'] is True,'preserved qualification/restoration')
  ib=c['files']['isolation_core'];require(ib['sha256']==CORE,'unchanged isolation core');iso=module('d260_original_isolation',ib)
  original=load(c['files']['original_preparation'])['prestate'];require(iso.root_state()==original['root'],'original root differs before rearm')
  cfg=load(c['files']['isolation_config']);cfg['evidence_root']=str(E/'isolation-preparation-v27-resume-1');cfg['lifecycle_seconds']=(w['deadline_monotonic_ns']-time.monotonic_ns())//NANO-120;cfg['protected_work_ns']=(55860+120)*NANO
  require(cfg['lifecycle_seconds']>55860+600,'remaining keeper budget');iso.configure(dict(operator_config=cfg))
  for name,state in original['maintenance_before'].items():
   actual=iso.systemd_state(name);require(actual['UnitFileState']==state['UnitFileState'] and (name not in iso.TIMER_SERVICES or actual['ActiveState']==state['ActiveState']),'original maintenance differs')
  pre=iso.prepare(cfg);require(pre['prestate']['root']==original['root'],'fresh root target differs');iso.verify_remaining_lifetime(pre['prestate'],55860*NANO,120*NANO)
  save(STUDY/'isolation-rearm.json',dict(configuration=cfg,prospective_prestate=binding(iso.Q/'prospective-prestate.json'),original_preparation=c['files']['original_preparation'],verified=True))
  command('check',w['last_safe_collection_start_ns']);require(not h.descendants(os.getpid()),'owner check descendants remain')
  require(iso.identity(CG)==pre['prestate']['partition_identity'] and (CG/'cgroup.procs').read_text().strip()=='','empty actual partition');iso.isolated_state()
  now=time.monotonic_ns();require(now<w['last_safe_collection_start_ns'] and now+(55860+13500+1800)*NANO<=w['deadline_monotonic_ns'],'whole remaining family budget')
  deadline=now+55860*NANO;save(STUDY/'collection-intent.json',dict(prepared_phase=pb,deadline_ns=deadline,owner_check_passed=True,automatic_retries=0));command('collection',deadline)
  receipt_path=phase/'stage17-q16b-completion-v6.json';receipt=load(binding(receipt_path));observed=h.restoration_status(receipt,attempt_id=request['attempt_id'],request_sha256=d['files']['request']['sha256'],authorization_sha256=d['files']['authorization']['sha256'],expected_prestate=request['action_inputs']['hardware_control']['prestate'])
  require(observed['executor_completed'] and observed['hardware_restoration_verified'],'native completion/restoration');result['collection_receipt']=binding(receipt_path)
 except BaseException as error:result['errors'].append(repr(error));result['failure_traceback']=traceback.format_exc(limit=20)[-32768:]
 finally:
  for s in old:signal.signal(s,lambda n,f:result['errors'].append('signal during cleanup '+str(n)))
  if active is not None:
   try:active.stop(w['deadline_monotonic_ns']);require(not active.forced,'forced cleanup occurred')
   except BaseException as error:result['errors'].append('owned cleanup '+repr(error))
   active=None
  if d is not None and request is not None:
   try:
    phase=pathlib.Path(d['output_root']);receipts=[phase/n for n in ('stage17-q16b-completion-v6.json','stage17-q16b-failure-v6.json') if (phase/n).exists()]
    if receipts:
     require(len(receipts)==1,'conflicting native terminal receipts');receipt=load(binding(receipts[0]))
     recovery=h.restoration_status(receipt,attempt_id=request['attempt_id'],request_sha256=d['files']['request']['sha256'],authorization_sha256=d['files']['authorization']['sha256'],expected_prestate=request['action_inputs']['hardware_control']['prestate'])
     require(recovery['hardware_restoration_verified'],'native hardware recovery not verified');result['native_terminal_receipt']=binding(receipts[0])
    else:require(not (phase/'stage17-attempt.json').exists(),'native attempt has no recovery receipt')
   except BaseException as error:result['errors'].append('native recovery '+repr(error))
  def restore_owned():
   report=dict(verified=False,errors=[])
   try:
    if iso is not None and pre is not None:
     iso.restore(pre['prestate']);receipt=load(binding(iso.Q/'restoration.json'));require(receipt['verified'] is True,'original core restoration')
     report['receipt']=binding(iso.Q/'restoration.json')
    elif iso is not None and (iso.Q/'restoration.json').exists():
     require(load(binding(iso.Q/'restoration.json'))['verified'] is True,'partial preparation restoration')
    require(not CG.exists(),'reserved partition remains')
    original=load(c['files']['original_preparation'])['prestate']
    core=iso if iso is not None else module('d260_cleanup_core',c['files']['isolation_core'])
    core.configure(dict(operator_config=load(c['files']['isolation_config'])))
    require(core.root_state()==original['root'],'original root restoration')
    for name,state in original['maintenance_before'].items():
     actual=core.systemd_state(name);require(actual['UnitFileState']==state['UnitFileState'] and (name not in core.TIMER_SERVICES or actual['ActiveState']==state['ActiveState']),'original maintenance restoration')
    report['verified']=True
   except BaseException as error:report['errors'].append(repr(error))
   save(STUDY/'partition-restoration.json',report);return report['verified']
  try:
   state=types.SimpleNamespace(budget=types.SimpleNamespace(end=w['deadline_monotonic_ns']),root=STUDY,result=result,restore=restore_owned)
   restored=h.Study.bounded_restore(state);require(restored,'bounded isolation restoration unverified')
  except BaseException as error:result['errors'].append('isolation cleanup '+repr(error))
 try:
  if not result['errors'] and restored:
   for s in old:signal.signal(s,interrupted)
   deadline=min(time.monotonic_ns()+13500*NANO,w['deadline_monotonic_ns']-1800*NANO);command('analysis',deadline)
   done=load(binding(E/'d260-analysis-1/analysis-complete.json'));require(done['status']=='ALL_103_ANALYZED' and done['combined_capture_count']==120 and done['all_raw_reconstructed_and_hash_checked'] is True,'all103 actual validation required');result['analysis_complete']=binding(E/'d260-analysis-1/analysis-complete.json');result['success']=True
 except BaseException as error:result['errors'].append('analysis '+repr(error));result['failure_traceback']=traceback.format_exc(limit=20)[-32768:]
 finally:
  for s in old:signal.signal(s,lambda n,f:result['errors'].append('signal during final cleanup '+str(n)))
  if active is not None:
   try:active.stop(w['deadline_monotonic_ns'])
   except BaseException as error:result['errors'].append('analysis cleanup '+repr(error))
  if h.descendants(os.getpid()):result['errors'].append('owned descendants remain')
  result['success']=result['success'] and not result['errors'] and restored and time.monotonic_ns()<w['deadline_monotonic_ns'];result['completed_monotonic_ns']=time.monotonic_ns();save(STUDY/'study-result.json',result)
  for s,handler in old.items():signal.signal(s,handler)
 return 0 if result['success'] else 1

if __name__=='__main__':
 p=argparse.ArgumentParser();m=p.add_mutually_exclusive_group(required=True)
 for role in ('run','owner','inner'):m.add_argument('--'+role,action='store_true')
 p.add_argument('--role',choices=('check','collection','analysis'));p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--deadline-ns',type=int);a=p.parse_args();c,w,h=configure(a)
 if a.run:raise SystemExit(run(a,c,w,h))
 owner(a,c,w,h)
