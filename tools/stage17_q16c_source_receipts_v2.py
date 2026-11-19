"""D288 authenticate only the188 pending sources from the signed360-source job.

A signature from the independently admitted owner trust authenticates the actual
supervised software validation record. Every source byte is rehashed on reuse;
no caller-provided success flag substitutes for the signed complete record.
Caller separately owns phase authority and live global-deadline admission.
"""
from pathlib import Path
from fractions import Fraction
import time

from stage17_q16c_admission_limits_v1 import ADMISSION as admission
import stage17_q16c_schedule_provenance_v2 as provenance
import stage17_semantic_verifier_v61 as semantic
import stage17_phase_controller_v25 as controller
import stage17_formal_archive_v1 as archive

SCHEMA = 'cpu-prefetch-stage17-q16c-source-preparation/1'
PURPOSE = 'D270-ORIGINAL-GENERATION-AND-INDEPENDENT-VALIDATION-ONLY'
SOURCE_CAP_NS = 22_500_000_000_000
DAY_NS = 86_400_000_000_000
Error, require, same, fields = admission.AdmissionError, admission.require, admission.same, admission.fields


def _uint(value):
    require(type(value) is int and 0 <= value < 2**64, 'exact unsigned64 software timing/count required')
    return value


def validate(plan, sources, registrations, proof, *, validation, source_plan, boot_id, deadline_ns):
    """Authenticate the complete old job, then hash only original indices172–359.

    The caller incident-authenticates source_plan and the zero-event failed86.
    No original signed generation timestamp/identity/provenance is rewritten.
    """
    import stage17_formal_scheduled_continuation_v1 as continuation
    continuation.validate_plan(plan)
    require(type(source_plan) is dict and len(source_plan['captures'])==180,
        'complete original generation plan required')
    fields(proof, 'manifest signature', 'source preparation proof')
    reader = admission.BoundReader()
    raw = reader.read(proof['manifest']); record = admission._json(raw)
    reader.read(proof['signature'])
    trust = validation.resolutions['S17-EXT-003'].semantic_context['trust']
    controller.support._verify_signature(raw, Path(proof['signature']['path']), trust)
    fields(record, 'schema_version purpose protocol_version stand_id boot_id software_source_revision '
        'bundle_inventory_sha256 load_basis_sha256 source_root source_closure source_setup started_monotonic_ns '
        'completed_monotonic_ns source_deadline_ns global_deadline_ns workers all_workers_reaped '
        'sources experimental_actions execution_authority phase18_authority', 'signed source job')
    same(record['schema_version'], SCHEMA, 'source job schema')
    same(record['purpose'], PURPOSE, 'source job purpose supplies no action authority')
    same(record['protocol_version'], '2.0.0-pre.3', 'original generator protocol')
    same(record['stand_id'], plan['stand_id'], 'source job actual stand')
    same(record['boot_id'], boot_id, 'same actual boot')
    for flag in ('execution_authority', 'phase18_authority'): same(record[flag], False, 'source job authority')
    same(record['experimental_actions'], 0, 'source job contains no experimental action')
    same(record['all_workers_reaped'], True, 'owned software workers completed and reaped')
    same(record['workers'], 32, 'prospective bounded software worker pool')
    start, end = (_uint(record[k]) for k in ('started_monotonic_ns', 'completed_monotonic_ns'))
    require(0 < start <= end < _uint(record['source_deadline_ns']), 'completed source preparation deadline')
    same(record['source_deadline_ns'], start + SOURCE_CAP_NS, 'unchanged source preparation cap')
    same(record['global_deadline_ns'], start + DAY_NS, 'one original absolute24h window')
    release = validation.resolutions['S17-EXT-006'].semantic_context
    same(record['software_source_revision'], source_plan['source_revision'], 'actual original generation source')
    same(record['software_source_revision'], release['source_revision'], 'actual qualified source')
    same(record['bundle_inventory_sha256'], release['inventory_sha256'], 'actual qualified source inventory')
    same(record['load_basis_sha256'], provenance.BASIS_SHA256, 'exact completed descriptive load basis')
    root = Path(release['archive_bundle_root'])
    inventory = reader.document(dict(path=str(root/'BUNDLE_INVENTORY.json'),
        size_bytes=(root/'BUNDLE_INVENTORY.json').stat().st_size, sha256=release['inventory_sha256']))
    index = admission._inventory(inventory)
    basis = admission._json(reader.read(dict(
        path=str(root/'docs/evidence/stage17/Q16B-HANDOFF-20261117-01/descriptive-load-basis.json'),
        size_bytes=provenance.BASIS_BYTES, sha256=provenance.BASIS_SHA256)))
    expected = semantic.discover_python_closure(root, ('generate_schedule', 'stage17_q16c_schedule_provenance_v2'))
    expected |= {'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json',
        'config/schemas/schedule-derivation-v2.schema.json',
        'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
    same(sorted(record['source_closure']), sorted(expected), 'complete accepted generator/validator source closure')
    for name in sorted(expected):
        bound = dict(index[name], path=str(root/name))
        same(record['source_closure'][name], bound, 'actual source closure '+name)
        reader.read(bound)
    source_root = Path(record['source_root'])
    require(source_root.is_absolute() and source_root.resolve(strict=True) == source_root,
            'original source job root must be canonical and nonsymlink')
    same(proof['manifest']['path'], str(source_root/'source-preparation.json'), 'original signed job location')
    same(proof['signature']['path'], str(source_root/'source-preparation.json.sig'), 'original signed job signature')
    setup = reader.document(record['source_setup'])
    fields(setup, 'schema_version stand_id boot_id bundle_root source_revision bundle_inventory_sha256 '
                 'sources execution_authority phase18_authority', 'original prospective source setup')
    for key, expected_value in dict(schema_version='cpu-prefetch-stage17-q16c-source-setup/1',
            stand_id=plan['stand_id'], boot_id=boot_id, bundle_root=str(root), source_revision=source_plan['source_revision'],
            bundle_inventory_sha256=release['inventory_sha256'], execution_authority=False, phase18_authority=False).items():
        same(setup[key], expected_value, 'original source setup '+key)
    require(type(sources) is list and len(sources) == 188 and type(registrations) is list
            and len(registrations) == 188 and type(record['sources']) is list
            and len(record['sources']) == 360 and type(setup['sources']) is list
            and len(setup['sources']) == 360, 'complete original360-source proof and exact188 pending namespace registrations required')
    registered = {r['schedule_id']:r for r in registrations}
    require(len(registered) == 188, 'duplicate registered source identity')
    binary_bindings = []; total = 0; physical = set()
    for local, (source, saved) in enumerate(zip(sources, record['sources'][172:], strict=True)):
        ordinal=172+local
        require(time.monotonic_ns() < deadline_ns, 'source custody proof deadline expired')
        fields(source, 'artifact_id binding envelope_binding derivation_binding parent_namespace_id source_preparation',
               'prospective source binding')
        same(source['source_preparation'], proof, 'one exact signed source preparation')
        fields(saved, 'ordinal binary envelope derivation provenance exit_code leader_reaped', 'owned source result')
        same([saved['ordinal'], saved['exit_code'], saved['leader_reaped']], [ordinal, 0, True], 'owned original source completion')
        capture = source_plan['captures'][ordinal//2]['capture']; phase = ('warmup','measurement')[ordinal%2]
        same(plan['captures'][local//2]['capture']['schedules'][local%2],capture['schedules'][ordinal%2],
            'exact original pending source, including unmodified generation history')
        schedule = capture['schedules'][ordinal%2]; p = saved['provenance']
        original_setup = setup['sources'][ordinal]
        fields(original_setup, 'ordinal capture_ordinal phase load_level schedule_id seed_id seed_hex namespace_id '
            'parent_namespace_id artifact_id artifact_uri derivation_record_id', 'original prospective source coordinates')
        expected_setup = dict(ordinal=ordinal, capture_ordinal=ordinal//2, phase=phase, load_level=capture['load_level'],
            **{key:schedule[key] for key in ('schedule_id','seed_id','seed_hex','namespace_id')},
            parent_namespace_id=source['parent_namespace_id'], artifact_id=source['artifact_id'],
            artifact_uri=p['artifact_uri'])
        for name, expected_value in expected_setup.items(): same(original_setup[name], expected_value, 'original source setup '+name)
        original = source['binding']; identity = source['artifact_id']
        same(identity, schedule['source_artifact']['artifact_id'], 'ordered original source identity')
        for name, saved_name in (('binding','binary'),('envelope_binding','envelope'),('derivation_binding','derivation')):
            same(source[name], saved[saved_name], 'original bound '+saved_name)
            path = Path(source[name]['path'])
            require(source_root in path.parents and path.resolve(strict=True) == path, 'source outside original job namespace')
            st = path.lstat(); inode = (st.st_dev, st.st_ino)
            require(inode not in physical, 'aliased original source artifacts')
            physical.add(inode)
        fields(p, 'schema_version phase schedule_id namespace_id parent_namespace_id seed_id artifact_binding envelope_binding '
            'derivation_binding schedule_sha256 derivation_record_sha256 decoded_deadlines_sha256 artifact_uri '
            'source_origin_ticks source_horizon_ticks duration_ticks offered_count scale_ordinal load_level nominal_offered_rate '
            'descriptive_load_basis_sha256 family_method_id confidence_claim accepted_generation_verified execution_authority phase18_authority',
            'accepted original-source provenance')
        expected_registration = {key:schedule[key] for key in ('schedule_id','namespace_id','seed_id')}
        expected_registration.update(phase=phase,parent_namespace_id=source['parent_namespace_id'])
        same(registered[schedule['schedule_id']], expected_registration, 'registered prospective source')
        expected_provenance = dict(schema_version=provenance.SCHEMA_ID, phase=phase,
            schedule_id=schedule['schedule_id'], namespace_id=schedule['namespace_id'],
            seed_id=schedule['seed_id'], parent_namespace_id=source['parent_namespace_id'],
            source_origin_ticks=schedule['source_origin_ticks'], source_horizon_ticks=schedule['source_horizon_ticks'],
            offered_count=schedule['offered_count'], duration_ticks=capture[phase+'_ns']*1000,
            scale_ordinal=0, load_level=capture['load_level'], descriptive_load_basis_sha256=provenance.BASIS_SHA256,
            family_method_id='MATRIX-FULL-DESCRIPTIVE-SCREEN-v1', confidence_claim=None,
            accepted_generation_verified=True, execution_authority=False, phase18_authority=False)
        base_rate = basis['base_rates'][capture['load_level']]
        rate = Fraction(base_rate['numerator'], base_rate['denominator']) / 10**12
        expected_provenance['nominal_offered_rate'] = dict(numerator_events=rate.numerator,
                                                        denominator_ticks=rate.denominator)
        for name, expected_value in expected_provenance.items(): same(p[name], expected_value, 'signed accepted provenance '+name)
        for name, binding, suffix in (('artifact_binding',original,''), ('envelope_binding',source['envelope_binding'],':envelope'),
                                      ('derivation_binding',source['derivation_binding'],':derivation')):
            same(p[name], dict(artifact_id=identity+suffix, size_bytes=binding['size_bytes'], sha256=binding['sha256']),
                 'accepted verifier original '+name)
        same(original['size_bytes'], schedule['offered_count']*8, 'exact original source extent')
        same(original['sha256'], schedule['source_artifact']['sha256'], 'actual original hash')
        envelope = reader.document(source['envelope_binding'])
        derivation = reader.document(source['derivation_binding'])
        same(envelope['schedule_sha256'], p['schedule_sha256'], 'original envelope self identity')
        same(envelope['decoded_deadlines_sha256'], p['decoded_deadlines_sha256'], 'original decoded source identity')
        same(derivation['record_sha256'], p['derivation_record_sha256'], 'original derivation self identity')
        same(derivation['record_id'], original_setup['derivation_record_id'], 'original derivation record identity')
        for binding in (original, source['envelope_binding'], source['derivation_binding']):
            observed = archive.hash_file(Path(binding['path']), max_bytes=binding['size_bytes'], deadline_ns=deadline_ns)
            same([observed.size_bytes,observed.sha256], [binding['size_bytes'],binding['sha256']], 'current immutable source custody')
        total += original['size_bytes']
        binary_bindings.append(dict(artifact_id=identity, **original))
    same(total, plan['source_transport']['source_bytes'], 'complete original source-byte accounting')
    reader.finish()
    return record, binary_bindings
