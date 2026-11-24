"""Retained-data cold pipeline timing only; never starts a queue worker."""
import argparse,datetime,hashlib,importlib.abc,importlib.util,json,os,pathlib,resource,shutil,struct,sys,time
sys.dont_write_bytecode=True
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');O=E/'archive-overhead-bench-1'
PROGRAM=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1'
ORIGINAL_FAMILY='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
BENCH_FAMILY=hashlib.sha256(b'D253_SOFTWARE_TIMING_ONLY_NOT_EXPERIMENT').hexdigest()
SCOPE='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2'
PROFILE_MEMBER='config/stage17/formal-archive-implementation-profile-v1.json'
assert os.getresuid()==(1000,)*3
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,8*1024**3))
assert not pathlib.Path('/proc/210874').exists()
restore=json.loads((E/'formal-q16b-launch-3/supervisor-result.json').read_bytes())
assert restore['child_reaped'] and restore['hardware_restoration_verified'] and restore['partition_restoration']['verified']
parser=argparse.ArgumentParser();parser.add_argument('mode',choices=('prepare','previous','candidate'));args=parser.parse_args()
descriptor=json.loads((E/'q16b-admission-operators-5/archive-overlay.json').read_bytes())
root=pathlib.Path(descriptor['overlay_bundle_root']) if args.mode!='candidate' else O/'candidate-1'
profile_raw=(root/PROFILE_MEMBER).read_bytes();profile_doc=json.loads(profile_raw)
expected_hash=descriptor['overlay_profile']['sha256'] if args.mode!='candidate' else json.loads((O/'candidate-metadata-summary.json').read_bytes())['candidate']['profile']['sha256']
assert hashlib.sha256(profile_raw).hexdigest()==expected_hash
sources={}
for row in profile_doc['source_closure']:
 image=row['image'];assert image['location']=='bundle' and image['path']=='tools/'+row['module']+'.py'
 path=root/image['path'];raw=path.read_bytes();assert len(raw)==image['size_bytes'] and hashlib.sha256(raw).hexdigest()==image['sha256'];sources[row['module']]=(path,raw)
class PinnedSources(importlib.abc.MetaPathFinder,importlib.abc.Loader):
 def find_spec(self,name,path=None,target=None):
  if name in sources:return importlib.util.spec_from_loader(name,self,origin=str(sources[name][0]))
 def create_module(self,spec):return None
 def exec_module(self,module):
  path,raw=sources[module.__name__];module.__file__=str(path);exec(compile(raw,str(path),'exec'),module.__dict__)
sys.meta_path.insert(0,PinnedSources())
import stage17_formal_archive_v1 as a
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
from stage17_formal_archive_jobs_v1 import build_capture_jobs
from stage17_formal_archive_registry_v1 import role_profile
from stage17_formal_checkpoint_v1 import validate_checkpoint
from dataclasses import replace,asdict
profile=runtime.load_runtime_profile(root/PROFILE_MEMBER,expected=a.PhysicalBinding(len(profile_raw),expected_hash),bundle_root=root,runtime_root=pathlib.Path(descriptor['runtime_root']),max_profile_bytes=131072,deadline_ns=time.monotonic_ns()+900_000_000_000)
DATA=O/'dataset-2';source_family=PROGRAM/'working'/ORIGINAL_FAMILY
receipt=json.loads((source_family/'formal-capture-0-archive-custody.json').read_bytes())
original_checkpoint=(source_family/'formal-capture-0-final-checkpoint.json').read_bytes()
assert hashlib.sha256(original_checkpoint).hexdigest()==receipt['checkpoint']['sha256']
def save(path,d):
 with path.open('x') as f:json.dump(d,f,indent=2);f.flush();os.fsync(f.fileno())
if args.mode=='prepare':
 resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,8*1024**3))
 DATA.mkdir(mode=0o700,exist_ok=True)
 assert {p.name for p in DATA.iterdir()} <= {x['logical']['file_name'] for x in receipt['artifacts']}
 total=sum(x['logical']['size_bytes'] for x in receipt['artifacts']);assert total<=16*1024**3
 assert shutil.disk_usage(O).free>total*3+32*1024**3
 for item in receipt['artifacts']:
  path=PROGRAM/'archives'/item['archive_name'];target=DATA/item['logical']['file_name']
  with path.open('rb') as f:
   assert f.read(8)==b'CPFA2331';length=struct.unpack('<Q',f.read(8))[0];assert 0<length<=32768;header=a.parse_json(f.read(length))
  role=role_profile('Q16b',item['logical']['file_name'])
  limits=a.DecodeLimits(32768,8*1024**2,4*1024**2,item['physical']['size_bytes'],item['logical']['size_bytes'],100000,1<<22,time.monotonic_ns()+900_000_000_000)
  t=time.monotonic()
  if target.exists():
   if target.stat().st_mode & 0o777 == 0o400:
    digest=hashlib.sha256()
    with target.open('rb') as prior:
     for chunk in iter(lambda:prior.read(1024**2),b''):digest.update(chunk)
    assert target.stat().st_size==item['logical']['size_bytes'] and digest.hexdigest()==item['logical']['sha256']
    print('RETAINED_SOFTWARE_DATASET_HASH_RECHECKED',target.name,flush=True);continue
   assert target.stat().st_size==0,'retain nonempty failed software source';target.unlink()
  with target.open('xb') as sink:proof=a.verify_archive(path,expected_header=header,role=role,physical=a.PhysicalBinding(**item['physical']),profile=replace(profile.decoder,implementation_profile_sha256=header['implementation_profile_sha256']),limits=limits,sink=sink)
  assert proof.canonical.sha256==item['logical']['sha256'];target.chmod(0o400)
  print('RETAINED_BYTES_RECONSTRUCTED',target.name,item['logical']['size_bytes'],time.monotonic()-t,flush=True)
 save(O/'dataset-proof-2.json',dict(execution_authority=False,observations_added=0,logical_bytes=total,source_checkpoint_sha256=receipt['checkpoint']['sha256'],artifacts=[x['logical'] for x in receipt['artifacts']]))
 sys.exit(0)
assert (O/'dataset-proof-2.json').exists()
bench=O/('program-'+args.mode+'-2');assert not bench.exists();bench.mkdir(mode=0o700)
for name in custody.ProgramStore.DIRECTORIES:(bench/name).mkdir(mode=0o700)
for name in ('scope.json','broker.lock'):shutil.copyfile(PROGRAM/name,bench/name)
# Independent small-file copies; no hardlinks to historical evidence. Sparse
# unrelated archives reproduce inventory names/logical sizes, never raw bytes.
for name in ('ledger','metadata'):
 for p in (PROGRAM/name).iterdir():
  assert p.is_file() and not p.is_symlink();shutil.copyfile(p,bench/name/p.name)
for family in (PROGRAM/'working').iterdir():
 assert family.is_dir() and not family.is_symlink();dst=bench/'working'/family.name;dst.mkdir(mode=0o700)
 for p in family.iterdir():
  if p.name.startswith('formal-capture-') and p.name.endswith('.json'):shutil.copyfile(p,dst/p.name)
for p in (PROGRAM/'archives').iterdir():
 assert p.is_file() and not p.is_symlink()
 with (bench/'archives'/p.name).open('xb') as f:f.truncate(p.stat().st_size)
limits=custody.CustodyLimits(1059517716,1000000,1000000,1059517716,time.monotonic_ns()+900_000_000_000)
t=time.monotonic()
with custody.ProgramStore(bench,scope_sha256=SCOPE,family_id=BENCH_FAMILY,limits=limits) as store:
 initial_replay=time.monotonic()-t;store.prepare_family(BENCH_FAMILY)
 working=store.working
 checkpoint=json.loads(original_checkpoint);checkpoint['plan_sha256']=BENCH_FAMILY
 cp_raw=a.canonical(checkpoint);cp_path=working/'formal-capture-0-final-checkpoint.json';cp_path.write_bytes(cp_raw)
 for item in receipt['artifacts']:shutil.copyfile(DATA/item['logical']['file_name'],working/item['logical']['file_name'])
 plan=json.loads((E/'formal-q16b-preparation-2/plan.json').read_bytes());item=plan['captures'][0];storage={**plan['storage'],'implementation_profile_sha256':expected_hash}
 def observe():
  if pathlib.Path('/proc/210874').exists():raise RuntimeError('unexpected native worker; software bench stops')
 def verify(document,sources):
  validate_checkpoint(document,action='Q16b',plan_sha256=BENCH_FAMILY,capture=item['capture'],sources=sources);observe()
 inventory_times=[];original_inventory=store.physical_accounting
 def timed_inventory():
  t=time.monotonic();value=original_inventory();inventory_times.append(time.monotonic()-t);return value
 store.physical_accounting=timed_inventory
 t=time.monotonic();jobs_t=t
 sources_,jobs=build_capture_jobs(store=store,action='Q16b',capture=item['capture'],document=checkpoint,profile=profile,storage=storage,maximum_capture_bytes=item['execution_budget']['max_output_bytes'],deadline_ns=limits.deadline_ns,verify_quiescence=observe)
 construction=time.monotonic()-jobs_t
 runtime_limits=runtime.RuntimeLimits(storage['broker_address_space_bytes'],storage['codec_address_space_bytes'],128*1024**2,storage['checkpoint_bytes'],2*1024**2,2_000_000_000,limits.deadline_ns,limits.deadline_ns,18)
 engine=runtime.ColdArchiveRuntime(store,profile=profile,limits=runtime_limits)
 outcome=engine.archive_capture(custody.BoundFile(cp_path.name,len(cp_raw),hashlib.sha256(cp_raw).hexdigest()),sources_,jobs,verify_checkpoint=verify)
 elapsed=time.monotonic()-t
 assert outcome.status=='ARCHIVED_AND_RELEASED' and engine.child_count==18
 actual=json.loads((working/outcome.receipt.file_name).read_bytes());assert len(actual['artifacts'])==6
 assert all(x['logical']==x['expected_logical'] and x['failure_receipt'] is None for x in actual['artifacts'])
 report=dict(schema_version='software-retained-capture-cold-benchmark/1',implementation=args.mode,execution_authority=False,observations_added=0,scientific_validity='NOT_ASSESSED',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),initial_replay_seconds=initial_replay,construction_seconds=construction,cold_pipeline_seconds=elapsed,inventory_calls=len(inventory_times),inventory_seconds=sum(inventory_times),inventory_samples=inventory_times,codec_children=engine.child_count,logical_bytes=sum(x['logical']['size_bytes'] for x in actual['artifacts']),archive_bytes=sum(x['physical']['size_bytes'] for x in actual['artifacts']),status=outcome.status,profile_sha256=expected_hash,ledger_tip=asdict(store.ledger_binding()),fixture_note='Independent copied historical metadata; unrelated old archives are sparse inventory placeholders. Same retained capture bytes, original encoder/options, both real sealed readbacks and release checks. Excludes native measurement/preparation, full broker transport, post-custody controller gates and future history growth.')
 save(O/(args.mode+'-capture-timing.json'),report);print(json.dumps(report),flush=True)
