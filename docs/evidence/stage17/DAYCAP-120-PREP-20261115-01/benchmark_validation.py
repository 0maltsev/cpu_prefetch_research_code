"""Timed independent validation of retained Q16b bytes; no new experiment."""
import os,sys,pathlib,json,hashlib,time,types,resource,datetime,signal,traceback
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';O=E/'archive-overhead-bench-1';DATA=O/'dataset-2'
assert os.getresuid()==(1000,)*3 and not pathlib.Path('/proc/210874').exists()
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(16*1024**3,)*2);resource.setrlimit(resource.RLIMIT_CPU,(1200,1200))
def timeout(*_):raise TimeoutError('retained validation timing exceeded 1200s wall budget')
signal.signal(signal.SIGALRM,timeout);signal.alarm(1200)
raw=(P/'stage17_formal_admin_v3.py').read_bytes();assert hashlib.sha256(raw).hexdigest()=='746638cb545c2b933549907d51dd1014bb5414ae982a9173cace48a841dddce3'
sys.path.insert(0,str(P));m=types.ModuleType('stage17_formal_admin_v3');m.__file__=str(P/'stage17_formal_admin_v3.py');sys.modules[m.__name__]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__);m.activate_packet('6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919')
import stage17_formal_service_capture_validation_v1 as validation
F=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1/working/6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
r=(E/'admission-root/evidence/formal-q16b-2/request.json').read_bytes();assert hashlib.sha256(r).hexdigest()=='9d95435d14e1541520831964fd3c57145717a84ceeb59ae9492c8ada5917ab09'
request=json.loads(r);item=request['action_inputs']['plan']['captures'][0]
proof=json.loads((O/'dataset-proof-2.json').read_bytes());assert proof['execution_authority'] is False
checkpoint=json.loads((F/'formal-capture-0-final-checkpoint.json').read_bytes());report={'schema_version':'software-retained-validation-timing/1','execution_authority':False,'observations_added':0,'input_capture_ordinal':0,'input_plan_sha256':checkpoint['plan_sha256'],'logical_bytes':proof['logical_bytes'],'utc_started':datetime.datetime.now(datetime.timezone.utc).isoformat()}
t=time.monotonic()
try:
 control=json.loads((DATA/'q16b-c0-control.json').read_bytes());report['control_parse_seconds']=time.monotonic()-t;print('CONTROL_PARSED',report['control_parse_seconds'],flush=True)
 t0=time.monotonic();result=validation.validate_capture(DATA,control,checkpoint['native_result_after_cleanup'],item['capture'],item['resources'],item['monitoring'],request['action_inputs']['hardware_control']);report['raw_validation_seconds']=time.monotonic()-t0;report['status']='VALIDATION_PASS';report['validation_report']=result
except BaseException as error:
 report['status']='SOFTWARE_TIMING_FAILED';report['error_type']=type(error).__name__;report['error']=str(error);report['traceback']=traceback.format_exc()
finally:
 report['total_seconds']=time.monotonic()-t;report['maximum_resident_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;report['utc_completed']=datetime.datetime.now(datetime.timezone.utc).isoformat();signal.alarm(0)
 with (O/'retained-validation-timing.json').open('x') as f:json.dump(report,f,indent=2)
 print(json.dumps({k:v for k,v in report.items() if k not in ('validation_report','traceback')}),flush=True)
