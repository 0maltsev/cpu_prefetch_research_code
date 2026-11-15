"""Read-only stand software timing; no capture or experiment authority."""
import os,sys,pathlib,json,hashlib,time,types,resource,cProfile,pstats,io,datetime
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';O=E/'archive-overhead-bench-1'
assert os.getresuid()==(1000,)*3
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2)
assert (E/'formal-q16b-launch-3/supervisor-result.json').exists()
assert not pathlib.Path('/proc/210874').exists()
O.mkdir(mode=0o700)
raw=(P/'stage17_formal_admin_v3.py').read_bytes();assert hashlib.sha256(raw).hexdigest()=='746638cb545c2b933549907d51dd1014bb5414ae982a9173cace48a841dddce3'
sys.path.insert(0,str(P));m=types.ModuleType('stage17_formal_admin_v3');m.__file__=str(P/'stage17_formal_admin_v3.py');sys.modules[m.__name__]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__);m.activate_packet('6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919')
import stage17_archive_metadata_fast_v1 as metadata
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_v1 as a
import stage17_archive_canonical_fast_v1 as fast
program=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1';family='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
limits=custody.CustodyLimits(1059517716,1000000,1000000,1059517716,time.monotonic_ns()+900_000_000_000)
report={'scope':'READ_ONLY_COLD_METADATA_BENCHMARK','execution_authority':False,'observations_added':0,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
prof=cProfile.Profile();prof.enable();t=time.monotonic()
with metadata.make_store_class()(program,scope_sha256='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2',family_id=family,limits=limits) as store:
 report['profiled_replay_seconds']=time.monotonic()-t;report['ledger_records']=store._sequence;report['ledger_tip']=vars(store.ledger_binding());report['pending']=len(store._capture_pending);report['reserved_bytes']=store.reserved_bytes()
prof.disable();s=io.StringIO();pstats.Stats(prof,stream=s).sort_stats('cumtime').print_stats(35);(O/'metadata-profile.txt').write_text(s.getvalue());print('REPLAY_PROFILE_SAVED',report['profiled_replay_seconds'],flush=True)
with metadata.make_store_class()(program,scope_sha256='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2',family_id=family,limits=limits) as store:
 samples=[]
 for _ in range(3):
  t=time.monotonic();usage=store.physical_accounting();samples.append(time.monotonic()-t)
 report['inventory_seconds']=samples;report['physical_usage']=vars(usage)
raw=(E/'formal-q16b-preparation-2/plan.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==family
plan=json.loads(raw);samples={}
for label,fn in [('original',a.canonical),('fast',fast.canonical)]:
 t=time.monotonic();encoded=fn(plan);elapsed=time.monotonic()-t;assert encoded==raw;samples[label]=elapsed;print('PLAN_CANONICAL',label,elapsed,flush=True)
report['plan_canonical_seconds']=samples;report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['ledger_mutated']=False
(O/'metadata-summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
