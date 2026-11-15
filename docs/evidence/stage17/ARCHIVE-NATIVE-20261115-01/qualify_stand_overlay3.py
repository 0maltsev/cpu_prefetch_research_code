"""Bounded cold archive proof; no measurement or collection authority."""
import os,sys,pathlib,json,hashlib,time,types,base64,struct,resource,datetime
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';N=E/'q16b-native-archive-preparation-1';B=E/'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a';M='6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919'
assert os.getresuid()==(1000,)*3;os.sched_setaffinity(0,{3});resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
raw=(P/'stage17_formal_admin_v3.py').read_bytes();sys.path.insert(0,str(P));module=types.ModuleType('stage17_formal_admin_v3');module.__file__=str(P/'stage17_formal_admin_v3.py');sys.modules[module.__name__]=module;exec(compile(raw,module.__file__,'exec'),module.__dict__)
cli=module.activate_packet(M);module.activate_packet(M);print('ACTUAL_VERIFIED_PACKET_AND_REENTRY_PASS',flush=True)
archive=E.parent/(B.name+'.tar.gz');validation=cli.formal_functions()['_validation'](E/'admission-root',E,archive,pathlib.Path(str(archive)+'.sha256'))
import stage17_archive_overlay_v1 as overlay
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as a
D=overlay._CONFIG[2];minimal={'action_id':'Q16b','action_inputs':{'plan':{'storage':{'implementation_profile_sha256':D['overlay_profile']['sha256']}}}}
profile=overlay.qualified_profile(minimal,validation,deadline_ns=time.monotonic_ns()+120_000_000_000)
print('ACTUAL_ORIGINAL_RELEASE_AND_OVERLAY_CLOSURE_PASS',flush=True)

import stage17_archive_metadata_fast_v1 as metadata
import stage17_formal_archive_custody_v1 as custody
program=E.parent/'local-authoring-cpuprefetchv5-23/formal-archive-program-1';family='ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702';store_limits=custody.CustodyLimits(1059517716,1000000,1000000,1059517716,time.monotonic_ns()+600_000_000_000)
snapshot=None;samples=[]
for label,cls in [('original',custody.ProgramStore),('optimized',metadata.make_store_class()),('optimized',metadata.make_store_class()),('original',custody.ProgramStore)]:
 t=time.monotonic()
 with cls(program,scope_sha256='4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2',family_id=family,limits=store_limits) as store:
  elapsed=time.monotonic()-t
  state=(store._sequence,store._previous,store._states,store._families,store._capture_pending,store._retained_receipts,store._record_bindings)
  if snapshot is None:snapshot=state
  else:assert state==snapshot,'Complete replay state differs'
  assert store.reserved_bytes()==0 and not store._capture_pending
  t_inventory=time.monotonic();usage=store.physical_accounting();inventory_seconds=time.monotonic()-t_inventory
  if label=='original' and snapshot is state:original_usage=usage
  else:assert usage==original_usage,'Actual inventory fields differ'
  tip=vars(store.ledger_binding())
  samples.append(dict(implementation=label,seconds=elapsed,inventory_seconds=inventory_seconds,physical_usage=vars(usage),ledger_tip=tip,states=len(store._states),families=len(store._families)))
 print('ALL_RECORDS_REPLAYED_IDENTICALLY',label,elapsed,flush=True)
report=dict(status='STAND_NATIVE_AND_METADATA_OVERLAY_QUALIFICATION_PASS',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),qualified_state=validation.current_state,qualified_resolutions=len(validation.resolutions),packet_sha256=M,profile=D['overlay_profile'],native_image=D['native_image'],full_ledger_replay_samples=samples,complete_replay_state_equal=True,ledger_mutated=False,observations_added=0,scientific_validity='NOT_ASSESSED',execution_authority=False)
with (N/'cold-qualification-3.json').open('xb') as f:f.write(overlay.canonical(report));f.flush();os.fsync(f.fileno())
print(json.dumps(report),flush=True)
