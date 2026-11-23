"""Synthetic packed page parser plus exact residency-value checks only."""
from contextlib import ExitStack
import datetime,hashlib,json,os,resource,signal,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools'))
manifest=json.loads((ROOT/'source-closure.json').read_bytes())
for row in manifest['files']:
 raw=(ROOT/row['path']).read_bytes();assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
import stage17_discovery_validation_v3 as validation
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def expired(*_):raise TimeoutError('original bounded synthetic page timing')
signal.signal(signal.SIGALRM,expired);signal.alarm(180);count=1000000;base=0x7f0000000000
with tempfile.TemporaryDirectory(prefix='SOFTWARE-ONLY-S180-PAGES-',dir=ROOT/'build') as name:
 path=Path(name)/'control-fragment.json'
 with path.open('x',encoding='ascii',buffering=1024**2) as stream:
  stream.write('{"page_addresses":[')
  for i in range(count):stream.write((',' if i else '')+str(base+i*4096))
  stream.write('],"page_status":['+'0,'*(count-1)+'0]}');stream.flush();os.fsync(stream.fileno())
 size=path.stat().st_size;started=time.monotonic_ns()
 with ExitStack() as stack:
  with path.open('r',encoding='ascii') as stream:document=validation.JsonReader(stream,stack).document()
  parsed=time.monotonic_ns()-started;started=time.monotonic_ns()
  assert len(document['page_addresses'])==len(document['page_status'])==count
  for i,(address,node) in enumerate(zip(document['page_addresses'],document['page_status'],strict=True)):
   validation.exact(address,base+i*4096,'synthetic residency page');validation.exact(node,0,'synthetic residency node')
  checked=time.monotonic_ns()-started
root=Path(name);assert not root.exists();signal.alarm(0)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-software-packed-pages-timing/1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 page_count=count,numeric_observations=2*count,metadata_bytes=size,packed_parse_ns=parsed,exact_residency_values_ns=checked,
 resident_high_water_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,synthetic_files_removed=True,software_only=True,
 whole_control_validation_timed=False,original_research_raw_read=False,scientific_source_generated=False,qualification_performed=False,
 operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True))
