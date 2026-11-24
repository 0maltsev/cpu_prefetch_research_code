"""Read-only actual old admission and D247 handoff; no raw reconstruction."""
import hashlib,json,pathlib,sys,datetime,os,dataclasses
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
A=E/'q16b-admission-operators-5';sys.path.insert(0,str(A))
import stage17_formal_admin_v3 as admin
manifest_sha='6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919'
cli=admin.activate_packet(manifest_sha)
name='cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
archive=E.parent/(name+'.tar.gz');sidecar=pathlib.Path(str(archive)+'.sha256')
validation=cli.formal_functions()['_validation'](E/'admission-root',E,archive,sidecar)
plan_path=E/'formal-q16b-preparation-2/plan.json';raw=plan_path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
plan=json.loads(raw);handoff_path=E/'q16b-handoff-preparation-1/q16a-handoff.json'
import stage17_q16a_handoff_v1 as handoff
result=handoff.consume(json.loads(handoff_path.read_bytes()),validation=validation,plan=plan,selected_duration_ns=1000000000)
keys=('S17-EXT-004','S17-EXT-006')
# EXT002 contains public trust metadata only. No key bytes are opened here.
contexts={k:validation.resolutions[k].semantic_context for k in keys}
def bound(path):
 b=path.read_bytes();return dict(path=str(path),size_bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
doc=dict(schema_version='cpu-prefetch-stage17-original-q16a-admission-contexts/1',
 validated_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 original_admin_manifest=bound(A/'manifest.json'),original_journal=bound(E/'journal/stage17-state-journal-000009.json'),
 original_plan=bound(plan_path),handoff=bound(handoff_path),
 source_revision=plan['source_revision'],contexts=contexts,calibration_status=result['status'],calibration_run_sources=len(result['run_sources']),
 raw_revalidated=False,execution_authority=False,phase18_authority=False)
# No dataclass-valued EXT003 release object is exported.
encoded=(json.dumps(doc,sort_keys=True,separators=(',',':'),default=lambda value: str(value) if isinstance(value,pathlib.Path) else dataclasses.asdict(value) if dataclasses.is_dataclass(value) else (_ for _ in ()).throw(TypeError(type(value).__name__)))+'\n').encode()
print(encoded.decode(),end='')
