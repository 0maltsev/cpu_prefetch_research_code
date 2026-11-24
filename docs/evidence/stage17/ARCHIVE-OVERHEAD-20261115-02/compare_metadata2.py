"""Stand full-history software benchmark only; no experimental execution."""
import os,sys,pathlib,json,hashlib,time,types,resource,base64,datetime,statistics
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';N=E/'archive-overhead-operators-2';O=E/'archive-overhead-bench-1'
assert os.getresuid()==(1000,)*3
os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2)
assert (E/'formal-q16b-launch-3/supervisor-result.json').exists() and not pathlib.Path('/proc/210874').exists()
manifest=(N/'manifest.json').read_bytes();assert hashlib.sha256(manifest).hexdigest()=='27aa04609b20c799b0458ce0eab0379a289e40ed584997170da08d963ba9b66a'
for row in json.loads(manifest)['files']:
 r=(N/row['name']).read_bytes();assert len(r)==row['size_bytes'] and hashlib.sha256(r).hexdigest()==row['sha256']
raw=(P/'stage17_formal_admin_v3.py').read_bytes();assert hashlib.sha256(raw).hexdigest()=='746638cb545c2b933549907d51dd1014bb5414ae982a9173cace48a841dddce3'
sys.path.insert(0,str(P));m=types.ModuleType('stage17_formal_admin_v3');m.__file__=str(P/'stage17_formal_admin_v3.py');sys.modules[m.__name__]=m;exec(compile(raw,m.__file__,'exec'),m.__dict__);m.activate_packet('6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919')
sys.path.insert(0,str(N))
import stage17_archive_metadata_fast_v1 as old
import stage17_archive_inventory_native_v1 as new
import stage17_formal_archive_custody_v1 as custody
import stage17_archive_inventory_bundle_v1 as bundle
r=(N/'inventory.so').read_bytes();new._NATIVE=new.NativeInventory(base64.b85encode(r),len(r),hashlib.sha256(r).hexdigest())
program=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1';family='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847';scope='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2'
limits=custody.CustodyLimits(1059517716,1000000,1000000,1059517716,time.monotonic_ns()+900_000_000_000)
state=None;usage=None;samples=[]
for label,cls in [('previous',old.make_store_class()),('candidate',new.make_store_class()),('candidate',new.make_store_class()),('previous',old.make_store_class())]:
 t=time.monotonic()
 with cls(program,scope_sha256=scope,family_id=family,limits=limits) as store:
  replay=time.monotonic()-t
  current=(store._sequence,store._previous,store._states,store._families,store._capture_pending,store._retained_receipts,store._record_bindings)
  if state is None:state=current
  else:assert state==current,'Full replay state differs'
  assert not store._capture_pending and store.reserved_bytes()==0
  inventories=[]
  for i in range(3):
   t=time.monotonic();observed=store.physical_accounting();inventories.append(time.monotonic()-t)
   if usage is None:usage=observed
   else:assert usage==observed,'Live complete inventory differs'
  sample=dict(implementation=label,replay_seconds=replay,inventory_seconds=inventories,ledger_records=store._sequence,states=len(store._states),usage=vars(observed),ledger_tip=vars(store.ledger_binding()))
  samples.append(sample);print(json.dumps(sample),flush=True)
descriptor=json.loads((P/'archive-overlay.json').read_bytes())
candidate=bundle.build_candidate(baseline_bundle_root=descriptor['overlay_bundle_root'],runtime_root=descriptor['runtime_root'],destination=O/'candidate-2',native_library=N/'inventory.so',source_root=N)
report=dict(status='FULL_FRESH_METADATA_AND_INVENTORY_PARITY_PASS',execution_authority=False,observations_added=0,ledger_mutated=False,complete_replay_state_equal=True,all_inventory_fields_equal=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),samples=samples,candidate=candidate)
with (O/'candidate-metadata-summary-2.json').open('x') as f:json.dump(report,f,indent=2)
print('METADATA_TIMING_AND_COLD_CANDIDATE_COMPLETE',flush=True)
