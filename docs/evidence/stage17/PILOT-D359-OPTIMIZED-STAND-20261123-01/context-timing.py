"""Synthetic deterministic replay cost; no original scientific source generation."""
import datetime,hashlib,json,os,resource,signal,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'tools'))
manifest=json.loads((ROOT/'source-closure.json').read_bytes())
for row in manifest['files']:
 raw=(ROOT/row['path']).read_bytes();assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
import stage17_s180_capture_validation_v1 as validation
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
def expired(*_):raise TimeoutError('original bounded synthetic context timing')
signal.signal(signal.SIGALRM,expired);signal.alarm(180);deadline=time.monotonic_ns()+170*10**9
results=[]
for capacity in (512,65536,1048576):
 capture=dict(requested_geometry=dict(capacity=capacity,cache_line_bytes=64,base_page_bytes=4096),
  arena_namespace=f'SOFTWARE-ONLY-S180-CONTEXT-TIMING-ARENA-{capacity}',
  node_order_namespace=f'SOFTWARE-ONLY-S180-CONTEXT-TIMING-NODES-{capacity}')
 cache=validation.ReplayCache();before=time.monotonic_ns();value=cache.get(capture,'0'*63+'1',deadline);cold=time.monotonic_ns()-before
 before=time.monotonic_ns();reused=cache.get(capture,'0'*63+'1',deadline);cached=time.monotonic_ns()-before
 assert reused is value and len(value[0].order)==capacity and len(value[1])==capacity+1
 results.append(dict(capacity=capacity,cold_reconstruction_ns=cold,cached_integrity_readback_ns=cached,
  packed_arena_and_node_bytes=sum(len(x)*x.itemsize for x in (value[0].order,value[0].payload,value[1])),
  resident_high_water_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,cache_identity_reused=True))
signal.alarm(0)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-software-context-timing/1',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 results=results,software_only=True,scientific_source_generated=False,original_research_raw_read=False,qualification_performed=False,
 operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True))
