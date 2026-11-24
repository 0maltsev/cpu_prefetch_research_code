from pathlib import Path
import sys,hashlib,json,time,os,subprocess,datetime
common=Path('/opt/cpu-prefetch-s180-common-0919b87-1');manifest=common/'S180_COLD_SOURCE_MANIFEST.json'
raw=manifest.read_bytes();assert hashlib.sha256(raw).hexdigest()=='bccde38abc2d97181f20100e18a2f5e1e8e62e4d41683c8ec497fb4d63fbcd7d'
d=json.loads(raw)
for row in d['files']:
 p=common/row['path'];s=p.stat(follow_symlinks=False);assert s.st_uid==0 and not s.st_mode&0o022 and s.st_size==row['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
frozen=Path('/opt/cpu-prefetch-s180-native-sources-34247ce-1')
raw=(frozen/'FROZEN_SOURCE_MANIFEST.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='bd86f1b81686ab119607868cb64f94f6617e620fa82e93750b9877e6ba1c578b'
for row in json.loads(raw)['files']:
 p=frozen/row['path'];st=p.stat(follow_symlinks=False);assert st.st_uid==0 and not st.st_mode&0o022 and st.st_size==row['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
sys.path.insert(0,str(common/'tools'))
import stage17_s180_owner_replay_v1 as replay
import stage17_s180_calibration_compatibility_v1 as compatibility
import stage17_s180_source_author_v1 as author
root=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/admission-root');e=root.parent
arguments=dict(repository_root=root,evidence_root=e,latest_journal=e/'journal/stage17-state-journal-000010.json',journal_directory=e/'journal',pilot_archive=e.parent/'cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz',pilot_sidecar=e.parent/'cpu-prefetch-pilot-candidate-2.0.0-7b7c263-clean-5e100e05e49b.tar.gz.sha256')
started=time.monotonic_ns();proof={}
try:
 identity=subprocess.run([str(common/'frozen-native-release/cpu_prefetch_runner'),'--stage17-s180-runtime-identity-v1'],stdin=subprocess.DEVNULL,capture_output=True,timeout=30,check=True)
 assert len(identity.stdout)<=8192 and len(identity.stderr)<=16384
 proof['actual_frozen_native_identity']=json.loads(identity.stdout)
 base=replay.verify_original(base_replay_arguments=arguments,deadline_ns=time.monotonic_ns()+600*10**9)
 view=base.view();proof['owned_original_replay']=base.proof()
 ancestry,context=compatibility._ancestry(view,compatibility._review())
 proof['actual_original_bundle_root']=context['archive_bundle_root']
 proof['actual_closed_original_ancestry_consumer_passed']=True
 sizing=replay.archive.parse_json((common/author.SIZING_PATH).read_bytes());proof['source_requirements']= {k:v for k,v in author.requirements(sizing).items() if k!='jobs'}
 actual=compatibility.verify(base_validation=view,plan_sha256=author.planning.sha(sizing),original_bundle=Path(context['archive_bundle_root']),source_root=frozen,release_root=common/'frozen-native-release',codegen_report=common/'frozen-native-release/s180_codegen_report-final.json')
 proof['actual_current_native_compatibility']=actual.proof(base_validation=view,plan_sha256=author.planning.sha(sizing),for_execution=True)
except BaseException as error:
 print(json.dumps(dict(status='COLD_COMMON_READONLY_VERIFICATION_FAILED',error_type=type(error).__name__,error=str(error),process_report=getattr(error,'report',None),subprocess_stderr=getattr(error,'stderr',b'').decode(errors='replace')[:16384],completed_proof=proof,operational_window_started=False,qualification_performed=False),sort_keys=True,indent=2))
 raise SystemExit(1)
print(json.dumps(dict(status='ACTUAL_COLD_COMMON_SOFTWARE_AND_ORIGINAL_REPLAY_PASS',utc=datetime.datetime.now(datetime.UTC).isoformat(),elapsed_ns=time.monotonic_ns()-started,proof=proof,root_uids=list(os.getresuid()),source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True,indent=2))
