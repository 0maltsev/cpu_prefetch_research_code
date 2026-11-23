import hashlib,json,os,pathlib,sys,time
source=pathlib.Path('/tmp/cpu-prefetch-s180-owner-replay-software-42fc51b-5/stage17_s180_owner_replay_v1.py')
assert hashlib.sha256(source.read_bytes()).hexdigest()=='dd884038b97f32c2861690029091ef630ac3d15fb090c3fcde73bc0c77a0a7ff'
root=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/admission-root');e=root.parent
sys.path[:0]=[str(source.parent),str(root/'tools')]
import stage17_s180_owner_replay_v1 as replay
arguments=dict(repository_root=root,evidence_root=e,latest_journal=e/'journal/stage17-state-journal-000010.json',journal_directory=e/'journal',pilot_archive=e.parent/'cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz',pilot_sidecar=e.parent/'cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz.sha256')
try:
 owner=replay.verify_original(base_replay_arguments=arguments,deadline_ns=time.monotonic_ns()+600*10**9)
except BaseException as error:
 print(json.dumps(dict(status='OWNED_REPLAY_DIAGNOSTIC_FAILURE',error=str(error),report=getattr(error,'report',None)),sort_keys=True,indent=2))
 raise SystemExit(1)
view=owner.view()
print(json.dumps(dict(status='ACTUAL_SUPERVISED_OWNER_REPLAY_PASS',new_helper_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),proof=owner.proof(),original_latest_journal_sha256=view.latest_journal_sha256,original_resolution_count=view.resolution_count,original_transition_count=view.transition_count,original_resolution_sha256={k:v.sha256 for k,v in view.resolutions.items()},pilot_ready=view.pilot_ready,actual_parent_uids=list(os.getresuid()),source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True,indent=2))
