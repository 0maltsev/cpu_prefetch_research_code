"""D239 signed archival-family bridge; new EXT007 remains fail-closed.

Historical dispatch is unchanged. Registry12/controller26 are lazy, source-
pinned dependencies, never permissive substitutes. This bridge authenticates
collection/custody only. Actual bounded D220/D229/D232 analysis and its final
freeze integration must be connected before the new EXT007 branch can admit.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import re

import stage17_operational_semantics_v16 as predecessor
import stage17_operational_semantics_v11 as reader
import stage17_operational_semantics_v4 as lifecycle
import stage17_fixed_action_executor_v4 as roots
import stage17_phase_controller_v25 as existing_controller
import stage17_formal_plan_v2 as plans
import stage17_formal_calibration_v2 as archival_calibration
import stage17_calibration_export_v1 as strict

OperationalSemanticError = predecessor.OperationalSemanticError
PREDECESSORS = tuple(f'S17-EXT-{i:03d}' for i in range(1, 7))
DEPENDENCIES = {
    'stage17_output_registry_v12': 'verify_archived_formal_family',
    'stage17_phase_controller_v26': 'prepare_retention',
}
ROLES = ('AUTHORIZATION', 'SIGNATURE', 'REQUEST', 'ATTEMPT', 'RESULT', 'COMPLETION')


def require(condition, message):
    if not condition:
        raise OperationalSemanticError(message)


def exact(actual, expected, message):
    require(strict.calibration.canonical(actual) == strict.calibration.canonical(expected), message)


def _dependencies(repository_root, pinned):
    result = {}
    for name, member in DEPENDENCIES.items():
        relative = 'tools/' + name + '.py'
        path = Path(repository_root) / relative
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise OperationalSemanticError('required archival admission dependency unavailable: ' + name) from error
        require(relative in pinned and payload == pinned[relative],
                'archival admission dependency is not policy-pinned: ' + name)
        try:
            module = importlib.import_module(name)
        except ImportError as error:
            raise OperationalSemanticError('required archival admission dependency unavailable: ' + name) from error
        require(Path(module.__file__).resolve() == path.resolve(), 'dependency imported from another source tree')
        require(callable(getattr(module, member, None)), 'required archival verifier unavailable: ' + name + '.' + member)
        result[name] = module
    return result['stage17_output_registry_v12'], result['stage17_phase_controller_v26']


def _original(artifact):
    """Use the existing bounded nonsymlink reader, then strict original JSON."""
    _, raw, size, digest = reader._artifact_content(
        artifact.path.parent / 'unused-manifest-anchor', artifact.path.name,
        load=True, expected_size=artifact.size_bytes)
    require(raw == artifact.payload and size == artifact.size_bytes and digest == artifact.sha256,
            'original lifecycle artifact bytes drifted: ' + artifact.role)
    if artifact.role.endswith('_SIGNATURE'):
        return None
    document = json.loads(raw.decode('utf-8'), object_pairs_hook=strict.calibration._unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    strict.calibration._strict(document)
    exact(document, artifact.document, 'lifecycle parsed document differs from original bytes')
    return document


def _msrs(rows):
    require(type(rows) is list, 'restoration readbacks absent')
    result = {}
    for row in rows:
        require(type(row) is dict and set(row) == {'cpu', 'complete_value_hex'}, 'MSR readback fields differ')
        cpu, value = row['cpu'], row['complete_value_hex']
        require(type(cpu) is int and cpu >= 0 and cpu not in result, 'MSR CPU duplicate or malformed')
        require(type(value) is str and re.fullmatch('[0-9a-f]{16}', value), 'MSR value malformed')
        result[cpu] = value
    return result


def _restoration(rows, prestate):
    expected = _msrs(prestate)
    require(type(rows) is list, 'live restoration readbacks absent')
    observed = []
    for row in rows:
        require(type(row) is dict and set(row) == {'cpu', 'expected_hex', 'observed_hex', 'matches'},
                'live restoration readback fields differ')
        require(type(row['cpu']) is int and row['cpu'] in expected, 'unqualified restoration CPU')
        exact(row['matches'], True, 'live restoration mismatch flag')
        exact(row['expected_hex'], expected[row['cpu']], 'restoration expected full value differs')
        observed.append(dict(cpu=row['cpu'], complete_value_hex=row['observed_hex']))
    exact(_msrs(observed), expected, 'full live restoration differs from admitted prestate')


def _receipts(*, artifacts, action_id, trust, expected_predecessors, extent, allow_synthetic):
    """Exact signed receipt linkage; not a journal, release or custody admission."""
    require(action_id in ('Q16a', 'Q16b', 'Q16c'), 'not a formal action')
    selected = {role: reader._one(artifacts, action_id.upper() + '_' + role) for role in ROLES}
    docs = {role: _original(artifact) for role, artifact in selected.items()}
    lifecycle.verify_sshsig(authorization=selected['AUTHORIZATION'], signature=selected['SIGNATURE'], trust_record=trust)
    auth, request, attempt, result, completion = (docs[key] for key in
        ('AUTHORIZATION', 'REQUEST', 'ATTEMPT', 'RESULT', 'COMPLETION'))
    versions = {'AUTHORIZATION': 'phase-action-authorization', 'REQUEST': 'fixed-action-request',
                'ATTEMPT': 'phase-action-attempt', 'RESULT': 'phase-action-result', 'COMPLETION': 'phase-action-completion'}
    for role, family in versions.items():
        exact(docs[role]['schema_version'], 'cpu-prefetch-stage17-' + family + '/6', 'not an original v6 receipt')
        exact(docs[role]['action_id'], action_id, 'phase action identity differs')
        authority_field = 'stage18_authority' if role == 'AUTHORIZATION' else 'phase18_authority'
        exact(docs[role][authority_field], False, 'receipt claims Phase18 authority')
    authorization_sha = selected['AUTHORIZATION'].sha256
    request_sha = selected['REQUEST'].sha256
    exact(auth['request_binding'], dict(path=str(selected['REQUEST'].path),
        size_bytes=selected['REQUEST'].size_bytes, sha256=request_sha), 'signed request byte binding differs')
    for doc in (auth, request, result):
        exact(doc['predecessor_resolutions'], expected_predecessors, 'signed predecessor lineage differs')
    exact(request['authorization_id'], auth['authorization_id'], 'authorization ID differs')
    exact(request['session_id'], auth['session_id'], 'session ID differs')
    exact(request['stand_id'], auth['target']['stand_id'], 'target stand differs')
    exact(request['synthetic_test_only'], allow_synthetic, 'request classification differs')
    exact(result['synthetic_test_only'], allow_synthetic, 'result classification differs')
    exact(auth['evidence_root_binding'], request['evidence_root_binding'], 'signed root differs')
    exact(attempt['evidence_root_binding'], request['evidence_root_binding'], 'attempt root differs')
    for doc in (attempt, result, completion):
        exact(doc['authorization_sha256'], authorization_sha, 'authorization original SHA differs')
        exact(doc['request_sha256'], request_sha, 'request original SHA differs')
        exact(doc['attempt_id'], request['attempt_id'], 'attempt ID differs')
    exact(attempt['authorization_id'], request['authorization_id'], 'attempt authorization differs')
    for key in ('request_id', 'authorization_id', 'stand_id', 'runtime_binding', 'release_binding'):
        exact(result[key], request[key], 'result ' + key + ' differs')
    for doc in (attempt, completion):
        exact(doc['runtime_sha256'], request['runtime_binding']['sha256'], 'runtime SHA differs')
    exact(attempt['release_resolution_id'], request['release_binding']['source_resolution_id'], 'release resolution differs')
    exact(attempt['release_resolution_sha256'], request['release_binding']['source_resolution_sha256'], 'release resolution SHA differs')
    for key, value in (('one_attempt', True), ('retries', 0), ('marker_durable', True)):
        exact(attempt[key], value, 'one-shot durable attempt differs')
    exact(completion['completion_id'], request['attempt_id'] + ':completion', 'completion ID differs')
    exact(completion['result'], dict(file_name=selected['RESULT'].path.name,
        size_bytes=selected['RESULT'].size_bytes, sha256=selected['RESULT'].sha256), 'completion result binding differs')
    logical = [{key: item[key] for key in ('file_name', 'size_bytes', 'sha256')} for item in result['artifacts']]
    require(len({item['file_name'] for item in logical}) == len(logical), 'duplicate result artifact')
    exact(completion['artifact_bindings'], logical, 'completion artifact bindings differ')
    for doc in (result, completion):
        exact(doc['restoration_verified'], True, 'restoration not verified')
        exact(doc['quarantined'], False, 'quarantined collection')
    for key in ('leader_reaped', 'process_group_gone'):
        exact(completion[key], True, 'worker family not quiescent')
    _restoration(completion['live_restoration_readback'], request['action_inputs']['hardware_control']['prestate'])
    policy = existing_controller.deadline_policy(extent)
    exact(auth['deadline_policy'], policy, 'prospective deadline differs')
    issued, expires, started, ended = map(lifecycle._parse_utc, (
        auth['issued_at_utc'], auth['expires_at_utc'], attempt['started_at_utc'], completion['completed_at_utc']))
    require(issued <= started < expires and started <= ended <= expires, 'original UTC authority/receipt order differs')
    native_started, native_ended = map(lifecycle._parse_utc, (result['started_at_utc'], result['completed_at_utc']))
    require(started <= native_started <= native_ended <= ended, 'native result UTC order differs from supervised receipts')
    maximum = dt.timedelta(seconds=policy['session_max_wall_seconds'])
    require(expires - issued <= maximum and ended - started <= maximum, 'original finite session duration exceeded')
    require(strict.uint(result['duration_ns']) <= policy['session_max_wall_seconds'] * 1_000_000_000,
            'native duration exceeds prospective session bound')
    resources = completion['resource_admission']
    exact(resources['required_memory_bytes'], extent.declared.memory_bytes, 'completion memory declaration differs')
    plan = request['action_inputs'].get('plan', {})
    if plan.get('schema_version') == plans.VERSION[action_id]:
        storage = plan['storage']
        for field in ('retained_program_bytes', 'remaining_program_quota_bytes', 'capture_ordinal'):
            value = resources.get(field)
            require(type(value) is int and 0 <= value <= strict.calibration.MAX_U64,
                    'archival resource integer absent or malformed: ' + field)
        quota = strict.uint(storage['archive_quota_bytes'])
        retained = resources['retained_program_bytes']
        require(retained <= quota, 'retained shared program exceeds quota')
        exact(resources['remaining_program_quota_bytes'], quota - retained, 'remaining shared quota differs')
        exact(resources.get('program_scope_sha256'), storage['program_scope_sha256'], 'resource program scope differs')
        exact(resources['capture_ordinal'], 0, 'completion resource observation is not initial worker boundary')
        overhead = sum(strict.uint(storage[key]) for key in
                       ('workspace_bytes', 'analysis_scratch_bytes', 'disk_reserve_bytes'))
        initial = quota + overhead
        require(initial <= strict.calibration.MAX_U64
                and extent.declared.required_free_disk_bytes >= initial,
                'prospective initial declaration omits full shared quota/reserves')
        exact(resources['required_free_disk_bytes'], quota - retained + overhead,
              'completion remaining-program disk declaration differs')
    else:
        exact(resources['required_free_disk_bytes'], extent.declared.required_free_disk_bytes, 'completion disk declaration differs')
    for observed, required in (('memory_available_bytes', 'required_memory_bytes'),
                               ('filesystem_available_bytes', 'required_free_disk_bytes')):
        require(strict.uint(resources[observed]) >= strict.uint(resources[required]), 'recorded fresh admission below declaration')
    exact(resources['filesystem_device'], request['evidence_root_binding']['device'], 'resource filesystem differs')
    exact(resources['reservation_established'], False, 'availability observation claims a reservation')
    require(started <= lifecycle._parse_utc(resources['observed_at_utc']) <= ended,
            'resource observation is outside the original worker-boundary interval')
    output = Path(request['evidence_root_binding']['absolute_path'])
    require(all(selected[key].path.parent == output for key in ('ATTEMPT', 'RESULT', 'COMPLETION')),
            'receipt is outside signed original output root')
    return dict(authorization=auth, authorization_sha256=authorization_sha,
        request=request, request_sha256=request_sha, attempt=attempt, attempt_sha256=selected['ATTEMPT'].sha256,
        result=result, result_sha256=selected['RESULT'].sha256, completion=completion,
        completion_sha256=selected['COMPLETION'].sha256)


def _historical(prepared, admitted, historical_journal):
    observed = prepared.validation.resolutions
    require(set(observed) == set(PREDECESSORS), 'historical journal must end exactly through EXT006')
    expected = reader._resolution_bindings(admitted, PREDECESSORS)
    exact(reader._resolution_bindings(observed, PREDECESSORS), expected, 'historical predecessor resolution hashes differ')
    raw = Path(historical_journal).read_bytes()
    exact(hashlib.sha256(raw).hexdigest(), prepared.validation.latest_journal_sha256, 'historical journal bytes differ')
    return expected


def _archive_scope(archive_report, request, repository_root):
    """Check the real registry's scope projection; not an archive proof alone."""
    storage = request['action_inputs']['plan']['storage']
    require(type(archive_report) is dict and type(archive_report.get('scope_bindings')) is dict,
            'archive verifier omitted verified scope bindings')
    verified_scope = archive_report['scope_bindings']
    for key in ('program_id', 'implementation_profile_sha256', 'program_scope_sha256'):
        exact(verified_scope[key], storage[key], 'archive scope differs: ' + key)
    exact(verified_scope['phase_root_binding'], request['evidence_root_binding'], 'archive phase root differs')
    phase_root = Path(request['evidence_root_binding']['absolute_path'])
    program = verified_scope['program_root_binding']
    exact(program['absolute_path'], str(phase_root.parent.parent), 'archive program root differs')
    program_fd, program_identity = roots._componentwise_output_root(Path(program['absolute_path']),
                                                                  Path(repository_root), program)
    try:
        roots._verify_root_identity(program_fd, program_identity)
    finally:
        os.close(program_fd)
    ledger = strict.fields(verified_scope['ledger_head'], 'sequence_number sha256', 'ledger head')
    strict.uint(ledger['sequence_number'])
    require(type(ledger['sha256']) is str and re.fullmatch('[0-9a-f]{64}', ledger['sha256']), 'ledger head SHA absent')


def verify_signed_formal_family(*, repository_root, evidence_root, historical_journal,
        journal_directory, artifacts, action_id, admitted_resolutions, allow_synthetic, pinned_repository_bytes,
        analysis_limits=None):
    """Authenticate historical collection and call the real archival registry.

    No scientific credit or freeze follows. Dependency absence is a hard failure.
    The caller supplies the original journal through EXT006, never a pending
    EXT007 journal. No capture, signing, release or hardware action is invoked.
    """
    try:
        registry, controller = _dependencies(repository_root, pinned_repository_bytes)
        authorization = reader._one(artifacts, action_id.upper() + '_AUTHORIZATION')
        signature = reader._one(artifacts, action_id.upper() + '_SIGNATURE')
        prepared = controller.prepare_retention(repository_root=Path(repository_root),
            operational_evidence_root=Path(evidence_root), journal=Path(historical_journal),
            journal_directory=Path(journal_directory), authorization_path=authorization.path,
            signature_path=signature.path, synthetic_test_only=allow_synthetic)
        expected = _historical(prepared, admitted_resolutions, historical_journal)
        for role, family in (('AUTHORIZATION', 'phase-action-authorization'), ('REQUEST', 'fixed-action-request'),
                             ('ATTEMPT', 'phase-action-attempt'), ('RESULT', 'phase-action-result'),
                             ('COMPLETION', 'phase-action-completion')):
            artifact = reader._one(artifacts, action_id.upper() + '_' + role)
            reader._validate(Path(repository_root), _original(artifact),
                'config/schemas/stage17-' + family + '-v6.schema.json', role, pinned_repository_bytes)
        request_artifact = reader._one(artifacts, action_id.upper() + '_REQUEST')
        require(prepared.authorization_bytes == authorization.payload and prepared.request_bytes == request_artifact.payload,
                'prepared authority/request differs from original lifecycle bytes')
        plan = prepared.request['action_inputs']['plan']
        exact(plan['schema_version'], plans.VERSION[action_id], 'archival bridge requires original /2 plan')
        extent = plans.validate_plan(action_id, plan)
        family = _receipts(artifacts=artifacts, action_id=action_id,
            trust=prepared.validation.resolutions['S17-EXT-003'].semantic_context['trust'],
            expected_predecessors=expected, extent=extent, allow_synthetic=allow_synthetic)
        phase_root = Path(prepared.request['evidence_root_binding']['absolute_path'])
        require(phase_root.parent.name == 'working' and phase_root.name == hashlib.sha256(
            archival_calibration.plan_bytes(plan)).hexdigest(), 'phase root is not original program/working/plan-SHA')
        descriptor, identity = roots._componentwise_output_root(phase_root, Path(repository_root),
                                                               prepared.request['evidence_root_binding'])
        try:
            archive_report = registry.verify_archived_formal_family(registry=prepared.registry,
                repository_root=Path(repository_root), directory_fd=descriptor, result=family['result'],
                request=prepared.request, authorization_sha256=family['authorization_sha256'],
                synthetic_test_only=allow_synthetic,
                archive_runtime_profile=prepared.archive_runtime_profile,
                analysis_limits=analysis_limits)
            roots._verify_root_identity(descriptor, identity)
            _archive_scope(archive_report, prepared.request, repository_root)
        finally:
            os.close(descriptor)
        return dict(lifecycle=family, archive_report=archive_report,
            historical_journal_sha256=prepared.validation.latest_journal_sha256,
            scientific_credit_established=False, execution_authority=False, phase18_authority=False)
    except OperationalSemanticError:
        raise
    except (OSError, KeyError, ValueError, TypeError, RuntimeError) as error:
        raise OperationalSemanticError('archival signed-family rejected: ' + str(error)) from error


def verify_manifest_v17(**arguments):
    """Legacy dispatch stays exact; new archival EXT007 cannot yet freeze."""
    if arguments['expected_input_id'] != 'S17-EXT-007':
        return predecessor.verify_manifest_v16(**arguments)
    manifest, _ = reader.load(arguments['manifest_path'])
    current = any(item.get('role') in {'Q16A_REQUEST', 'Q16B_REQUEST', 'Q16C_REQUEST'}
                  and item.get('schema_identity') == 'cpu-prefetch-stage17-fixed-action-request/6'
                  for item in manifest.get('artifacts', []))
    if not current:
        return predecessor.verify_manifest_v16(**arguments)
    reader._validate(Path(arguments['repository_root']), manifest, reader.MANIFEST_SCHEMA,
                     'archival EXT007 manifest', arguments['pinned_repository_bytes'])
    _dependencies(arguments['repository_root'], arguments['pinned_repository_bytes'])
    raise OperationalSemanticError(
        'archival EXT007 requires the bounded actual D220/D229/D232 analysis and scoped freeze integration; '
        'signed custody alone cannot grant calibration credit')
