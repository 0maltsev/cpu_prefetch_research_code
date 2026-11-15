"""Bounded, stand-only D254 analysis of the completed120-capture family.

No collection, retry, signature or journal admission. The supplied exact
configuration binds the qualified CLI, signed request, archive descriptor and
retained Q16a contexts. All raw bytes are independently reconstructed and
hash-checked before the unchanged per-capture scientific validator runs.
"""
import argparse,dataclasses,datetime,gc,hashlib,io,json,multiprocessing as mp,os,pathlib,resource,signal,sys,time
GIB=1024**3

def require(ok,message):
 if not ok:raise ValueError(message)
def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def read(b,maximum=128*1024**2):
 require(set(b)=={'path','size_bytes','sha256'},'exact file binding required');p=pathlib.Path(b['path'])
 require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)),'absolute nonsymlink path required')
 with p.open('rb') as stream:
  before=os.fstat(stream.fileno());require(0<before.st_size==b['size_bytes']<=maximum,'bounded input size')
  raw=stream.read(before.st_size+1);after=os.fstat(stream.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==before.st_size and sha(raw)==b['sha256'],'input binding changed')
 return raw
def binding(path):
 p=pathlib.Path(path);raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=sha(raw))
def save(path,value):
 raw=canonical(value)
 with pathlib.Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 return binding(path)
def workers_for(online,observed):
 chosen={}
 for cpu in sorted(online):
  package,core=observed[cpu];chosen.setdefault((package,core),cpu)
 require(len(chosen)>=8,'eight actual physical cores required')
 return list(chosen.values())[:8]
def scratch_proof(canonical_per_capture):
 require(type(canonical_per_capture)is int and 0<canonical_per_capture<=31227906332,'canonical capture ceiling')
 total=8*canonical_per_capture+17*GIB
 require(total<=256*GIB,'eight worker scratch exceeds signed256GiB')
 return total

def configure(c):
 require(c['schema_version']=='software-d254-offline-analysis/1' and c['execution_authority'] is False,'offline config')
 root=pathlib.Path(c['repository_root']);require(root.is_absolute(),'absolute qualifiedroot')
 for b in c['files'].values():read(b)
 require(c['operator_sha256']==sha(pathlib.Path(__file__).read_bytes()),'operator changed')
 wrapper=__import__('types').ModuleType('daycap_cli');wrapper.__file__=c['files']['cli_wrapper']['path']
 exec(compile(read(c['files']['cli_wrapper']),wrapper.__file__,'exec'),wrapper.__dict__)
 cli,_=wrapper.configure(pathlib.Path(c['files']['cli_configuration']['path']),c['files']['cli_configuration']['sha256'])
 return cli

@__import__('contextlib').contextmanager
def control(common,root,logical):
 class FormalJson(common.JsonReader):
  def value(self,key='',depth=0):
   require(key!='drain_rows','unexpected formal drain JSON')
   return super().value(key,depth)
 with __import__('contextlib').ExitStack() as stack:
  raw=stack.enter_context(common.opened(root,logical));text=io.TextIOWrapper(raw,encoding='utf-8',errors='strict')
  try:yield FormalJson(text,stack).document()
  finally:text.detach()

def selected_archive_modules(profile,deadline):
 # Each source is freshly hash/identity checked by the qualified runtime. It is
 # executed from the authenticated immutable bytes, without path/pyc reopening.
 # Unique aliases and module-local imports leave all qualified science modules
 # and the parent's public import cache untouched.
 import builtins,types
 import stage17_formal_archive_runtime_v1 as runtime
 images=runtime._closure_bytes(profile,deadline)
 cache={};prefix='_d254_archive_'+str(os.getpid())+'_'
 real_import=builtins.__import__
 def load(name):
  if name in cache:return cache[name]
  binding,raw=images[name];alias=prefix+name
  require(alias not in sys.modules,'private archive alias already used')
  module=types.ModuleType(alias);module.__file__=str(binding.image.path);module.__package__=''
  cache[name]=module;sys.modules[alias]=module
  namespace=dict(vars(builtins));namespace['__import__']=scoped_import
  module.__dict__['__builtins__']=namespace
  exec(compile(raw,module.__file__,'exec'),module.__dict__)
  return module
 def scoped_import(name,globals=None,locals=None,fromlist=(),level=0):
  if level==0 and name in images:return load(name)
  return real_import(name,globals,locals,fromlist,level)
 return load('stage17_formal_archive_v1'),load('stage17_formal_archive_custody_v1')

def child(connection,job,profile,decoder_limits,hardware,cpu,deadline):
 try:
  os.sched_setaffinity(0,{cpu});require(os.sched_getaffinity(0)=={cpu},'analysis CPU pin')
  resource.setrlimit(resource.RLIMIT_AS,(2*GIB,16*GIB));resource.setrlimit(resource.RLIMIT_CPU,(900,900))
  def expired(*_):raise TimeoutError('capture independent analysis900s limit')
  signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,min(900,int((deadline-time.monotonic_ns())/1e9))))
  import stage17_formal_service_capture_validation_v1 as validator
  a,custody=selected_archive_modules(profile,deadline)
  decoder=a.DecoderProfile(**dataclasses.asdict(profile.decoder))
  decoder_limits=a.DecodeLimits(**dataclasses.asdict(decoder_limits))
  item=job['item'];verified=job['verified'];ordinal=item['capture']['ordinal'];start=time.monotonic_ns()
  artifacts=tuple(custody.SpoolArtifact(row['logical']['file_name'],pathlib.Path(job['program_root'])/'archives'/row['archive_name'],row['header'],a.RoleProfile(**row['role']),a.PhysicalBinding(**row['physical'])) for row in verified['artifacts'])
  require(len(artifacts)==6 and artifacts[-1].file_name==f'q16b-c{ordinal}-control.json','exact service artifact set')
  limit=dataclasses.replace(decoder_limits,deadline_ns=min(deadline,time.monotonic_ns()+900*10**9))
  gc.collect()
  with custody.capture_spool(pathlib.Path(job['scratch']),capture_id=f'capture-{ordinal}',canonical_bytes_bound=job['canonical_bytes'],deadline_ns=limit.deadline_ns,artifacts=artifacts,profile=decoder,limits=limit) as root:
   resource.setrlimit(resource.RLIMIT_AS,(16*GIB,16*GIB))
   with control(validator.common,root,verified['artifacts'][-1]['logical']) as document:
    report=validator.validate_capture(root,document,verified['native_result_after_cleanup'],item['capture'],item['resources'],item['monitoring'],hardware)
   result=save(pathlib.Path(job['reports'])/f'capture-{ordinal}.json',report)
  connection.send(dict(status='VALID',ordinal=ordinal,report=result,seconds=(time.monotonic_ns()-start)/1e9,maximum_resident_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,canonical_spool_removed=True))
 except BaseException as error:
  connection.send(dict(status='FAILED',ordinal=job['item']['capture']['ordinal'],error=f'{type(error).__name__}: {error}'))
 finally:connection.close()

def analyze(c,global_deadline):
 cli=configure(c);evidence=pathlib.Path(c['evidence_root']);root=pathlib.Path(c['analysis_root']);require(not root.exists(),'exclusive fresh analysis; no retry')
 require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==c['boot_id'],'boot changed')
 online=set()
 for token in pathlib.Path('/sys/devices/system/cpu/online').read_text().strip().split(','):
  if '-' in token:
   a,b=map(int,token.split('-'));online.update(range(a,b+1))
  else:online.add(int(token))
 # Runs only after signed completion has proved native reaping/restoration.
 os.sched_setaffinity(0,online);allowed=os.sched_getaffinity(0)
 observed={cpu:tuple(int((pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')/name).read_text()) for name in ('physical_package_id','core_id')) for cpu in allowed}
 cpus=workers_for(allowed,observed)
 mem={line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
 require(mem['MemAvailable']>=164*GIB,'fresh164GiB available-memory admission')
 canonical_bytes=c['canonical_capture_bytes'];scratch=scratch_proof(canonical_bytes)
 fs=os.statvfs(root.parent);require(fs.f_bavail*fs.f_frsize>=256*GIB+16*GIB,'fresh scratch+failure reserve')
 resource.setrlimit(resource.RLIMIT_AS,(2*GIB,16*GIB));resource.setrlimit(resource.RLIMIT_FSIZE,(256*GIB,256*GIB))
 prepared=cli.prepare_formal_retention(repository_root=pathlib.Path(c['repository_root']),operational_evidence_root=evidence,journal=pathlib.Path(c['files']['journal']['path']),journal_directory=evidence/'journal',authorization_path=pathlib.Path(c['files']['authorization']['path']),signature_path=pathlib.Path(c['files']['signature']['path']),pilot_archive=pathlib.Path(c['archive']),pilot_sidecar=pathlib.Path(c['sidecar']))
 require(prepared.request_bytes==read(c['files']['request']),'actual signed request differs')
 plan=prepared.request['action_inputs']['plan'];require(len(plan['captures'])==120,'all120 required')
 phase=pathlib.Path(prepared.request['evidence_root_binding']['absolute_path'])
 verified=cli.admit_formal_retention(prepared,phase)
 require(verified['inverse_readback_performed'] is False and len(verified['captures'])==120,'independent decode required for all120')
 root.mkdir(mode=0o700);(root/'scratch').mkdir();(root/'reports').mkdir()
 deadline=min(global_deadline,time.monotonic_ns()+13500*10**9)
 save(root/'analysis-intent.json',dict(deadline_monotonic_ns=deadline,worker_count=8,physical_cpus=cpus,observed_memory_available_bytes=mem['MemAvailable'],scratch_bytes=scratch,per_capture_seconds=900,execution_authority=False))
 save(root/'signed-family-metadata.json',verified)
 a=cli.registry.archive;decode=cli.registry._metadata_decode_limits(plan,cli.controller.contract.validate_plan('Q16b',plan),prepared.archive_runtime_profile,deadline)
 jobs=[dict(item=item,verified=cap,program_root=str(phase.parent.parent),scratch=str(root/'scratch'),reports=str(root/'reports'),canonical_bytes=canonical_bytes) for item,cap in zip(plan['captures'],verified['captures'],strict=True)]
 context=mp.get_context('fork');pending=list(jobs);active={};results={}
 try:
  while pending or active:
   require(time.monotonic_ns()<deadline,'whole offline-analysis deadline')
   for cpu in cpus:
    if cpu in active or not pending:continue
    job=pending.pop(0);receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=child,args=(sender,job,prepared.archive_runtime_profile,decode,prepared.request['action_inputs']['hardware_control'],cpu,deadline))
    process.start();sender.close();active[cpu]=(process,receiver,time.monotonic_ns(),job['item']['capture']['ordinal'])
   for cpu,(process,connection,started,ordinal) in list(active.items()):
    require(time.monotonic_ns()-started<902*10**9,'capture child cleanup deadline')
    if connection.poll():
     result=connection.recv();process.join(timeout=2);require(process.exitcode==0,'analysis child exit')
     save(root/f'capture-{ordinal}-process.json',result);require(result['status']=='VALID' and result['ordinal']==ordinal,'invalid required capture: '+str(result))
     results[ordinal]=result;connection.close();del active[cpu]
     print(json.dumps(dict(completed=len(results),total=120,capture_ordinal=ordinal)),flush=True)
    elif not process.is_alive():raise RuntimeError('capture analysis exited without report '+str(ordinal))
   if active:time.sleep(.1)
 finally:
  for process,connection,_,_ in active.values():
   if process.is_alive():process.terminate()
  for process,connection,_,_ in active.values():
   process.join(timeout=2)
   if process.is_alive():process.kill();process.join(timeout=2)
   connection.close()
  require(all(not p.is_alive() for p,_,_,_ in active.values()),'analysis children not reaped')
 records=[]
 for ordinal in range(120):
  raw=read(results[ordinal]['report']);records.append(dict(capture_ordinal=ordinal,measurement_run_id=plan['captures'][ordinal]['capture']['measurement']['run_id'],validity='VALID',report_binding=dict(artifact_id=f'Q16B-CAPTURE-{ordinal}',size_bytes=len(raw),sha256=sha(raw)),report_utf8_bytes=raw.decode()))
 import stage17_formal_service_daycap_v1 as daycap
 result=daycap.evaluate(plan,records);save(root/'calibration-validation.json',result)
 save(root/'analysis-complete.json',dict(status='ALL_120_ANALYZED',calibration_status=result['status'],report=binding(root/'calibration-validation.json'),captures=120,cells=60,repetitions_per_cell=2,all_raw_reconstructed_and_hash_checked=True,canonical_spools_removed=True,execution_authority=False,phase18_authority=False,ext007_admitted=False))
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--global-deadline-ns',type=int,required=True);args=p.parse_args()
 require(os.getuid()==os.geteuid()==1000,'actual evidence owner required')
 c=json.loads(read(dict(path=str(args.config),size_bytes=args.config.stat().st_size,sha256=args.config_sha256)))
 analyze(c,args.global_deadline_ns)
