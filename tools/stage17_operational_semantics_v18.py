"""D307 separately scoped descriptive EXT007; legacy v17 remains unchanged."""
import hashlib
import json
from pathlib import Path
import types

import stage17_operational_semantics_v17 as predecessor
import stage17_operational_semantics_v11 as reader
import stage17_descriptive_freeze_v1 as freeze
import stage17_archive_metadata_fast_v1 as cloning

OperationalSemanticError = predecessor.OperationalSemanticError
MANIFEST_SCHEMA = 'config/schemas/stage17-operational-input-manifest-v5.schema.json'
ACCEPTED_PATH = 'docs/evidence/stage17/EXT007-D307-FREEZE-PUBLISHED-20261120-01/accepted-bindings.json'
SIGNATURE_ROLE = 'CALIBRATION_FREEZE_SIGNATURE'
CODE_MEMBERS = ('prepare_stage17_descriptive_freeze_v1.py','stage17_descriptive_freeze_v1.py')
require = predecessor.require


def exact(value, expected, label):
    require(freeze.canonical(value) == freeze.canonical(expected), label+' differs')


def pair(binding):
    return [binding['size_bytes'], binding['sha256']]


def validate(root,document,relative,label,pinned):
    """Resolve the new manifest's v5 reference without rebinding legacy v4."""
    from jsonschema import Draft202012Validator,FormatChecker
    from jsonschema.exceptions import ValidationError
    from referencing import Registry,Resource
    schema,_ = reader._schema(root,relative,pinned)
    registry = Registry()
    if relative == MANIFEST_SCHEMA:
        artifact,_ = reader._schema(root,'config/schemas/stage17-operational-artifact-v5.schema.json',pinned)
        resource = Resource.from_contents(artifact)
        for name in ('stage17-operational-artifact-v5.schema.json',artifact['$id'],
                     'urn:cpu-prefetch:stage17:operational-input-manifest:stage17-operational-artifact-v5.schema.json'):
            registry = registry.with_resource(name,resource)
    try:
        Draft202012Validator(schema,registry=registry,format_checker=FormatChecker()).validate(document)
    except ValidationError as error:
        raise OperationalSemanticError(label+' schema rejection: '+error.message) from error


def verify_manifest_v18(*,repository_root,manifest_path,admitted_resolutions,expected_input_id,
                        allow_synthetic,pinned_repository_bytes):
    manifest,payload = reader.load(manifest_path)
    if manifest.get('schema_version') != 'cpu-prefetch-stage17-operational-input-manifest/5':
        return predecessor.verify_manifest_v17(repository_root=repository_root,manifest_path=manifest_path,
            admitted_resolutions=admitted_resolutions,expected_input_id=expected_input_id,
            allow_synthetic=allow_synthetic,pinned_repository_bytes=pinned_repository_bytes)
    require(expected_input_id == manifest['input_id'] == 'S17-EXT-007' and allow_synthetic is False,
            'scoped descriptive admission is real EXT007 only')
    root = Path(repository_root).resolve(); pinned = pinned_repository_bytes
    validate(root,manifest,MANIFEST_SCHEMA,'scoped descriptive manifest',pinned)
    require(ACCEPTED_PATH in pinned, 'policy-pinned actual publisher evidence missing')
    accepted = json.loads(pinned[ACCEPTED_PATH])
    exact(accepted['schema_version'],'cpu-prefetch-stage17-descriptive-freeze-audited-bindings/1','audited bindings version')
    exact(accepted['decision'],'D307','audited binding scope')
    exact(accepted['scope'],'EXACT_COMPLETED_INCIDENT_ONLY','closed audited incident scope')
    exact(accepted['operational_admission'],False,'audited data alone grants no resolution')
    exact(accepted['phase18_authority'],False,'audited data grants no Stage18')
    predecessors = reader._resolution_bindings(admitted_resolutions,tuple(f'S17-EXT-{i:03d}' for i in range(1,7)))
    exact(manifest['predecessor_resolutions'],predecessors,'actual six predecessor identities')
    roles = {'CALIBRATION_FREEZE':freeze.SCHEMA_PATH,SIGNATURE_ROLE:None}
    read = cloning._clone(reader._read_artifacts_v11,{**reader._read_artifacts_v11.__globals__,
        'ROLE_SCHEMA_v11':roles,'SIGNATURE_ROLES':set(reader.SIGNATURE_ROLES)|{SIGNATURE_ROLE}})
    artifacts = read(root,manifest_path,manifest,pinned)
    require(len(artifacts) == 2 and {a.role for a in artifacts} == set(roles), 'exact freeze/signature artifact pair')
    record,signature = (reader._one(artifacts,role) for role in ('CALIBRATION_FREEZE',SIGNATURE_ROLE))
    exact([record.size_bytes,record.sha256],accepted['freeze'],'actual audited signed freeze')
    exact(record.reference['lineage'],[],'freeze artifact has no invented lineage')
    exact(signature.reference['lineage'],[dict(id=record.reference['artifact_id'],sha256=record.sha256)],'signature signs this freeze')
    trust = admitted_resolutions['S17-EXT-003'].semantic_context['trust']
    from stage17_phase_controller_v2 import _verify_signature,ControllerError
    try:
        _verify_signature(record.payload,signature.path,trust)
    except ControllerError as error:
        raise OperationalSemanticError('freeze signature rejected: '+str(error)) from error
    value = freeze.verify(record.document)
    exact(value['predecessor_resolutions'],predecessors,'frozen predecessor identities')
    exact(value['stand_id'],manifest['stand_id'],'frozen stand identity')
    for key in ('S17-EXT-002','S17-EXT-004'):
        exact(admitted_resolutions[key].semantic_context['stand_id'],value['stand_id'],'admitted actual stand')
    exact(pair(value['provenance_record']),accepted['provenance'],'actual verified producer provenance')
    bound_reader = freeze.admission.BoundReader()
    proof = bound_reader.document(value['provenance_record'])
    exact(proof['status'],'SIGNED_LINEAGE_CUSTODY_AND_REPORTS_VERIFIED','actual producer preparation status')
    exact(proof['source_records'],value['source_records'],'actual original source records')
    exact(proof['predecessor_resolutions'],predecessors,'producer predecessor lineage')
    exact(proof['boot_id'],accepted['boot_id'],'original physical boot')
    exact(proof['stand_id'],value['stand_id'],'producer stand')
    current = admitted_resolutions['S17-EXT-006'].semantic_context
    for actual,expected in ((proof['qualified_source_revision'],current['source_revision']),
        (proof['qualified_worker']['sha256'],current['release_artifact_sha256']),
        (proof['qualified_inventory']['sha256'],current['inventory_sha256'])):
        exact(actual,expected,'actual qualified release identity')
    exact([current['source_revision'],current['release_artifact_sha256'],current['inventory_sha256']],
          accepted['qualified_release'],'original independently qualified native release')
    exact(pair(proof['historical_journal']),accepted['historical_journal'],'original completed six-input journal')
    journal = bound_reader.document(proof['historical_journal'])
    require(len(journal['resolution_records']) == 6, 'provenance journal must precede this EXT007 resolution')
    exact([r['sha256'] for r in journal['resolution_records']],[p['sha256'] for p in predecessors],
          'actual original journal qualification record hashes')
    exact(proof['archive_capture_count'],94,'all completed continuation custody')
    exact(proof['q16c_completion']['report_hashes_verified'],180,'all180 report identities')
    exact(proof['q16c_completion']['new_process_receipts_verified'],94,'all94 completed validation children')
    exact(proof['q16c_completion']['raw_decoding_repeated'],False,'no repeated raw validation')
    packet = bound_reader.document(proof['administrative_packet'])
    exact(packet['administrative_source_revision'],accepted['publisher_source_revision'],'actual publisher source revision')
    for name in CODE_MEMBERS:
        path = 'tools/'+name
        require(path in pinned, 'policy-pinned freeze producer source missing')
        bound = proof['source_code_bindings'][name]
        exact(pair(bound),[len(pinned[path]),hashlib.sha256(pinned[path]).hexdigest()],'actual reviewed producer source')
        bound_reader.read(bound)
    bound_reader.finish()
    return dict(manifest_id=manifest['manifest_id'],manifest_path=manifest_path,manifest_sha256=reader.sha(payload),
        stand_id=manifest['stand_id'],synthetic_test_only=False,artifact_index=reader._artifact_index(artifacts,admitted_resolutions),
        calibration_freeze=value,calibration_scope=freeze.SCOPE,data_provenance_accepted=True,
        legacy_statistical_freeze_satisfied=False,pilot_execution_eligible=False,
        final_matrix_feasibility='NOT_EVALUATED',phase18_authority=False)
