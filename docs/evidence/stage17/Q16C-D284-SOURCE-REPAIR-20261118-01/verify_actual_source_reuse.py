"""Read-only repaired source validation against actual completed qualification.

No journal append, family registration, signing, isolation, hardware operation,
source generation, capture or experiment entry point is called.
"""
import datetime,hashlib,json,os,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29')
R=E/'admission-root';S=Path(__file__).resolve().parent;P=E/'q16c-configuration-1'
assert os.getuid()==os.geteuid()==1000
packet_root=S/'packet'
sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(packet_root))
import stage17_q16c_packet_v3 as loader
raw=(packet_root/'manifest.json').read_bytes()
manifest,members=loader.verify_packet(packet_root,hashlib.sha256(raw).hexdigest())
proof_path=E/'source-bank-reuse-3/reuse-proof.json';proof_raw=proof_path.read_bytes()
loader.load_modules(packet_root,members,dict(path=str(proof_path),size_bytes=len(proof_raw),sha256=hashlib.sha256(proof_raw).hexdigest()))
reuse=sys.modules['stage17_q16c_empty_reuse_v1']
cli=sys.modules['stage17_q16c_descriptive_administration_v3'].make_cli()
assert Path(reuse.__file__).resolve()==packet_root/'stage17_q16c_empty_reuse_v1.py'
assert hashlib.sha256(Path(reuse.__file__).read_bytes()).hexdigest()=='d1ffac09c9c2cfa2f277d93750dcca30794ea8d934421151d9fcdebd3604b1e4'
def binding(path):
 raw=Path(path).read_bytes();return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(path):return json.loads(Path(path).read_bytes())
c=load(E/'q16c-d282-launch-inputs-1.json');G=Path(c['program_root']);ledger=max((G/'ledger').glob('*.json'));before=binding(ledger)
assert before['sha256']=='25a3d0aee5a175eb2a0a8d49a6d8c564716ce3d17f0240c98eed4540ec16280d'
assert not (E/'admission-root/evidence/formal-q16c-d282-1').exists()
assert not Path(c['cgroup']).exists()
started=time.monotonic_ns();cli.activate()
validation=cli._validation(R,E,pilot_archive=Path(c['files']['archive']['path']),pilot_sidecar=Path(c['files']['sidecar']['path']))
assert validation.current_state=='READY_FOR_STAGE17_PHASE_AUTHORIZATION'
assert set(validation.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,7)}
plan=load(c['files']['frozen_plan']['path']);incident=load(c['files']['source_reuse']['path'])
record=load(c['files']['source_manifest']['path']);setup=load(record['source_setup']['path']);completion=load(c['files']['source_completion']['path']);proof={k:completion[k] for k in ('manifest','signature')}
sources=[];registrations=[]
for original,saved in zip(setup['sources'],record['sources'],strict=True):
 sources.append(dict(artifact_id=original['artifact_id'],binding=saved['binary'],envelope_binding=saved['envelope'],derivation_binding=saved['derivation'],parent_namespace_id=original['parent_namespace_id'],source_preparation=proof))
 registrations.append({k:original[k] for k in ('schedule_id','namespace_id','seed_id','phase','parent_namespace_id')})
verified,bindings=reuse.validate(plan,sources,registrations,proof,validation=validation,boot_id=c['boot_id'],deadline_ns=time.monotonic_ns()+120*10**9,reuse=incident)
assert verified==record and len(bindings)==360
assert before==binding(ledger) and ledger==max((G/'ledger').glob('*.json'))
assert not (G/'working'/c['files']['frozen_plan']['sha256']).exists()
assert not (E/'admission-root/evidence/formal-q16c-d282-1').exists() and not Path(c['cgroup']).exists()
loader.check_loaded()
report=dict(staged_packet_manifest=binding(packet_root/'manifest.json'),administrative_source_revision=manifest['administrative_source_revision'],loaded_packet_modules=len(loader._LOADED),schema_version='cpu-prefetch-stage17-qualified-source-reuse-software-check/1',status='PASS',verified_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_ns=time.monotonic_ns()-started,actual_qualification_state=validation.current_state,actual_qualified_source=validation.resolutions['S17-EXT-006'].semantic_context['source_revision'],actual_qualified_worker_sha256=validation.resolutions['S17-EXT-006'].semantic_context['release_artifact_sha256'],original_producer_source=verified['software_source_revision'],repaired_administrative_source=binding(Path(reuse.__file__)),stand_verifier=binding(Path(__file__).resolve()),source_manifest=proof['manifest'],source_count=len(bindings),source_bytes=sum(b['size_bytes'] for b in bindings),original_signature_and_all_source_hashes_verified=True,original_ledger_before=before,original_ledger_after=binding(ledger),experimental_actions=0,source_generation_actions=0,qualification_repeated=False,native_binary_changed=False,collection_restarted=False,phase18_authority=False)
with (S/'complete.json').open('x') as f:json.dump(report,f,sort_keys=True,separators=(',',':'));f.flush();os.fsync(f.fileno())
print(json.dumps(report),flush=True)
