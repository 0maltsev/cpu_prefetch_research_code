"""Twelve-core disjoint synthetic archive-to-publication timing only."""
import ast,datetime,hashlib,json,multiprocessing,os,resource,signal,time
from pathlib import Path
from multiprocessing.connection import wait
ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/'source-closure.json').read_bytes())
for row in manifest['files']:
 raw=(ROOT/row['path']).read_bytes();assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
source=(ROOT/'benchmark.py').read_bytes();tree=ast.parse(source)
stop=next(i for i,node in enumerate(tree.body) if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call)
 and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='umask')
body=ast.unparse(ast.Module(body=tree.body[:stop],type_ignores=[]))
assert body.count('usage = resource.getrusage(resource.RUSAGE_SELF)')==1
body=body.replace('usage = resource.getrusage(resource.RUSAGE_SELF)','READY_GATE(); usage = resource.getrusage(resource.RUSAGE_SELF)')
scope=dict(__file__=str(ROOT/'benchmark.py'),__name__='software_capture_timing')
exec(compile(body,str(ROOT/'benchmark.py'),'exec'),scope)
mem={line.split(':',1)[0]:line.split(':',1)[1].split() for line in Path('/proc/meminfo').read_text().splitlines()}
assert int(mem['MemAvailable'][0])*1024>=196*1024**3
fs=os.statvfs(ROOT);assert fs.f_bavail*fs.f_frsize>=48*1024**3 and fs.f_favail>=1024
cores={};topology={}
for cpu in sorted(os.sched_getaffinity(0)):
 p=Path(f'/sys/devices/system/cpu/cpu{cpu}/topology');pair=tuple(int((p/name).read_text()) for name in ('physical_package_id','core_id'))
 topology[cpu]=pair;cores.setdefault(pair,cpu)
assert len(cores)>=12;cpus=list(cores.values())[:12]
for proc in Path('/proc').iterdir():
 if not proc.name.isdecimal():continue
 try:assert (proc/'comm').read_text().strip()!='cpu_prefetch_runner'[:15]
 except (OSError,ValueError):pass
os.umask(0o077);resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,16*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
DEADLINE=time.monotonic_ns()+590*10**9
scope['DEADLINE']=DEADLINE
def expired(*_):raise TimeoutError('original bounded synthetic concurrency deadline')
signal.signal(signal.SIGALRM,expired);signal.alarm(600)
def child(channel,cpu):
 try:
  os.setsid();os.sched_setaffinity(0,{cpu});assert os.sched_getaffinity(0)=={cpu}
  resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,16*1024**3));resource.setrlimit(resource.RLIMIT_FSIZE,(2*1024**3,2*1024**3))
  signal.alarm(580)
  def gate():
   channel.send(dict(status='READY',cpu=cpu,pid=os.getpid()))
   assert channel.poll(max(0,(DEADLINE-time.monotonic_ns())/10**9)) and channel.recv()=='GO'
  scope['READY_GATE']=gate
  result=scope['run'](1000000)
  channel.send(dict(status='PASSED',cpu=cpu,pid=os.getpid(),result=result))
 except BaseException as error:
  channel.send(dict(status='FAILED',cpu=cpu,error=repr(error)));raise
 finally:channel.close()
context=multiprocessing.get_context('fork');active={};processes=[];results=[];all_started=time.monotonic_ns()
try:
 for cpu in cpus:
  receiver,sender=context.Pipe();process=context.Process(target=child,args=(sender,cpu))
  process.start();sender.close();processes.append(process);active[receiver]=(process,cpu)
 ready=[]
 while len(ready)<12:
  assert time.monotonic_ns()<DEADLINE
  for channel in wait([c for c in active if c not in ready],timeout=.2):
   value=channel.recv();assert value['status']=='READY' and value['cpu']==active[channel][1],value;ready.append(channel)
 started=time.monotonic_ns()
 for channel in ready:channel.send('GO')
 while active:
  assert time.monotonic_ns()<DEADLINE
  for channel in wait(list(active),timeout=.2):
   process,cpu=active.pop(channel);result=channel.recv();channel.close();process.join(5)
   assert result['status']=='PASSED' and result['cpu']==cpu and process.exitcode==0 and not process.is_alive(),result
   result['leader_reaped']=True;results.append(result)
 elapsed=time.monotonic_ns()-started
finally:
 for process in processes:
  if process.is_alive():process.kill()
  process.join(5);assert not process.is_alive();process.close()
signal.alarm(0)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-software-capture-concurrency-timing/1',
 utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),results=sorted(results,key=lambda r:r['cpu']),physical_cpus=cpus,
 topology={cpu:topology[cpu] for cpu in cpus},analysis_and_reap_ns=elapsed,including_preparation_ns=time.monotonic_ns()-all_started,
 total_synthetic_accepted_events=12*2*1000000,all_children_reaped=True,all_synthetic_files_removed=all(r['result']['synthetic_files_removed'] for r in results),
 original_research_raw_read=False,scientific_source_preparation_performed=False,qualification_performed=False,operational_window_started=False,
 exact5400s_family_budget_verified=False,actual_production_pool_used=False,whole_family_timing=False,execution_authority=False,phase18_authority=False),sort_keys=True))
