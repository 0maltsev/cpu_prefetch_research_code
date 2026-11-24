"""Read-only cold gate software timing; no execution/ACK or new observations."""
import os,sys,pathlib,json,hashlib,time,types,resource,base64,datetime
from dataclasses import asdict
from types import SimpleNamespace
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';N=E/'archive-overhead-operators-1';X=E/'archive-overhead-flow-operators-1';O=E/'archive-overhead-bench-1'
assert os.getresuid()==(1000,)*3 and not pathlib.Path('/proc/210874').exists()
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
for root,digest in [(N,'985399c66c1fdeef650d3873d9a9a4166add74550f96dd8fde5b4182fbfff799'),(X,'d445e9b2dba03026fb6d01176f90ef0915e62023ae0322dfdfd27b659ff1a01e')]:
 r=(root/'manifest.json').read_bytes();assert hashlib.sha256(r).hexdigest()==digest
 for row in json.loads(r)['files']:
  raw=(root/row['name']).read_bytes();assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
raw=(P/'stage17_formal_admin_v3.py').read_bytes();assert hashlib.sha256(raw).hexdigest()=='746638cb545c2b933549907d51dd1014bb5414ae982a9173cace48a841dddce3'
sys.path.insert(0,str(P));m=types.ModuleType('stage17_formal_admin_v3');m.__file__=str(P/'stage17_formal_admin_v3.py');sys.modules[m.__name__]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__);m.activate_packet('6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919')
sys.path[:0]=[str(X),str(N)]
import stage17_archive_flow_private_v1 as flow
import stage17_archive_inventory_native_v1 as native
import stage17_archive_metadata_fast_v1 as metadata
import stage17_fixed_action_executor_v11 as original
import stage17_formal_archive_custody_v1 as custody
r=(N/'inventory.so').read_bytes();native._NATIVE=native.NativeInventory(base64.b85encode(r),len(r),hashlib.sha256(r).hexdigest())
old=metadata.make_executor(original);new=flow.make_executor()
r=(E/'admission-root/evidence/formal-q16b-2/request.json').read_bytes();assert hashlib.sha256(r).hexdigest()=='9d95435d14e1541520831964fd3c57145717a84ceeb59ae9492c8ada5917ab09'
request=json.loads(r);plan=request['action_inputs']['plan'];extent=original.plans.validate_plan('Q16b',plan)
program=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1';family=pathlib.Path(request['evidence_root_binding']['absolute_path'])
cp_raw=(family/'formal-capture-0-final-checkpoint.json').read_bytes();cp=json.loads(cp_raw);cu_raw=(family/'formal-capture-0-archive-custody.json').read_bytes();cu=json.loads(cu_raw)
receipt=custody.BoundFile('formal-capture-0-archive-custody.json',len(cu_raw),hashlib.sha256(cu_raw).hexdigest())
record_path=program/'ledger/0000000000059634.json';record_raw=record_path.read_bytes();record=json.loads(record_raw)
assert record['kind']=='CUSTODY_RECEIPT' and record['payload']['receipt']==asdict(receipt)
# This is a software boundary fixture, not a newly observed broker process.
# Its cleanup fields are retained original codec cleanup evidence. The real
# receipt/chain/resource functions execute unchanged and read-only below.
codec=json.loads((program/'ledger/0000000000059633.json').read_bytes())['payload']['cleanup']
outcome=SimpleNamespace(status='ARCHIVED_AND_RELEASED',receipt=receipt,receipt_ledger_record=custody.BoundFile(record_path.name,len(record_raw),hashlib.sha256(record_raw).hexdigest()),cleanup=SimpleNamespace(**codec))
pending=SimpleNamespace(binding=cu['checkpoint'],ordinal=0,document=cp)
assert hashlib.sha256(cp_raw).hexdigest()==pending.binding['sha256']
fd=os.open(family,os.O_RDONLY|os.O_DIRECTORY);samples=[];deadline=time.monotonic_ns()+600_000_000_000
try:
 for label in ('previous','candidate','candidate','previous'):
  t=time.monotonic()
  if label=='previous':
   result=old._broker_receipt(request,pending,outcome,deadline);old.live_resources(fd,extent,request=request,deadline_ns=deadline,ordinal=1)
  else:result=new._finish_archived_capture(request,pending,outcome,deadline,directory_fd=fd,extent=extent)
  elapsed=time.monotonic()-t;assert result==asdict(receipt);samples.append(dict(implementation=label,seconds=elapsed));print(json.dumps(samples[-1]),flush=True)
finally:os.close(fd)
report=dict(status='READ_ONLY_RECEIPT_RESOURCE_TRANSACTION_PARITY_PASS',execution_authority=False,observations_added=0,ledger_mutated=False,software_cleanup_boundary_fixture=True,request_sha256=hashlib.sha256(r).hexdigest(),samples=samples,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
with (O/'flow-timing.json').open('x') as f:json.dump(report,f,indent=2)
print('READ_ONLY_FLOW_TIMING_COMPLETE',flush=True)
