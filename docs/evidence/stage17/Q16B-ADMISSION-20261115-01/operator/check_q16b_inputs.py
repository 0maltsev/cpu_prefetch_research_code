"""Read-only actual Q16b semantic admission; no namespace/signature/execution."""
import datetime,hashlib,json,os,pathlib,sys
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-1';C=E/'formal-q16b-preparation-1'
assert os.getuid()==os.geteuid()==1000
assert sys.argv[1]=='34db47d894557354e871b7699182ffd3a8bd12cc094374ccf380a715f43a7648'
sys.path.insert(0,str(P));import stage17_formal_admin_v1 as admin
cli=admin.activate_packet(sys.argv[1]);import validate_suffix as v
c=v.config(E/'offline-suffix-preparation-1/inputs/analysis-config.json',admin.CONFIG_SHA)
print('QUALIFIED_SOURCE_AND_ADMIN_PACKET_VERIFIED',flush=True)
validation=cli.formal_functions()['_validation'](pathlib.Path(c['repository_root']),E,pilot_archive=pathlib.Path(c['pilot_archive']['path']),pilot_sidecar=pathlib.Path(c['pilot_sidecar']['path']),synthetic=False)
print('CURRENT_QUALIFIED_JOURNAL_VERIFIED',validation.current_state,len(validation.resolutions),flush=True)
def bind(p):
 assert p.is_file() and not p.is_symlink()
 with p.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 return dict(path=str(p),size_bytes=p.stat().st_size,sha256=sha)
plan_raw=(C/'plan.json').read_bytes();assert hashlib.sha256(plan_raw).hexdigest()=='ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702'
plan=json.loads(plan_raw);original=json.loads(v.read(c['files']['REQUEST']))
prerequisites=dict(original['action_inputs']['prerequisite_bindings']);prerequisites.update(q16a_validation=bind(E/'q16b-handoff-preparation-1/q16a-handoff.json'),q16b_validation=None,namespace_registry=bind(C/'namespace_registry.json'),schedule_sources=[])
inputs=dict(plan=plan,hardware_control=original['action_inputs']['hardware_control'],prerequisite_bindings=prerequisites)
request=dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',action_id='Q16b',stand_id=plan['stand_id'],action_inputs=inputs)
extent=cli.controller.validate_action_inputs(request,validation)
report=dict(status='Q16B_INPUT_SEMANTICS_VERIFIED_NOT_LAUNCH_ADMITTED',observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),plan=bind(C/'plan.json'),administrative_packet_sha256=sys.argv[1],operator_source_sha256=bind(pathlib.Path(__file__))['sha256'],qualified_state=validation.current_state,qualified_resolutions=len(validation.resolutions),captures=len(extent.captures),family_watchdog_ns=extent.required_watchdog_ns,required_family_as_bytes=extent.declared.memory_bytes,namespace_registered=False,signature_created=False,experiment_started=False,execution_authority=False)
out=E/'q16b-input-semantics-1.json';assert not out.exists();temp=E/'q16b-input-semantics-1.partial'
with temp.open('x') as f:json.dump(report,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
os.rename(temp,out);print(json.dumps(report,sort_keys=True),flush=True)
