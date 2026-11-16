"""D260 incident-bound17-capture prefix admission; no inverse or measurements.

Authenticate the exact completed independent reader/custody gate, each original
report/checkpoint/receipt/release record and current physical archive bytes.
Check both actual qualified releases, the entire measured source closure and
the physical platform. A different or incomplete prefix cannot select /4.
"""
from __future__ import annotations

import hashlib
import pathlib
import time
import types

import stage17_formal_service_continuation_v2 as contract
import stage17_formal_calibration_v1 as calibration
import stage17_q16a_continuation_admission_v1 as admission
import stage17_q16a_service_continuation_handoff_v1 as handoff
import stage17_daycap_administration_v1 as association
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as capture_registry
import stage17_formal_checkpoint_v1 as checkpoint
import stage17_phase_controller_v2 as signature

PREFIX_SHA256 = '24a2926078396c2efe43eac6ac06887ca7e54d562a587a9bced2f62c355cd202'
PREFIX_SIZE = 16540
VALIDATION_SHA256 = '6f95694880e143a25e27bdf39990817a0310b0a032a78781688ba8bb7701f9a3'
RECOVERY_AUTH_SHA256 = 'fb7eef138d6448913cfdecbf9133906ca747bea8e237f0de8cc6e831e1f60bcd'
ORIGINAL_WORKER = '305cedfc5438c68ececfa6a0f954d757112a50c87f687b93ad7b013b7ed757dd'
ORIGINAL_INVENTORY = '371ce6e04bc9def7322f1df97d7db2b8f7a659495da6763746f1c8ca6e75b12d'
ORIGINAL_CODEGEN = 'f55a9ad0258fcf3c6c3ab4501554d1b43140ccab5f1fec24b938970d0faa8bf9'
ORIGINAL_CONTEXT_SIZE = 5295
ORIGINAL_CONTEXT_SHA256 = 'b015a73b93cbe5d5d34cc8a599800e6d579e3b6983d0909e6b6de760b1019f98'
COMPATIBILITY_SCHEMA = 'cpu-prefetch-stage17-d260-prefix-compatibility/1'
same, require, fields = admission.same, admission.require, admission.fields


def _named_binding(directory, value):
    require(type(value) is dict and set(value) == {'file_name','size_bytes','sha256'}, 'named binding shape')
    name = value['file_name']
    require(type(name) is str and pathlib.Path(name).name == name, 'named binding basename')
    return dict(path=str(directory/name), size_bytes=value['size_bytes'], sha256=value['sha256'])


def _capture(reader, row, parent, program):
    ordinal = row['original_ordinal']
    item = parent['captures'][ordinal]
    capture = item['capture']
    phase = program/'working'/contract.PARENT_SHA256
    cp = reader.document(_named_binding(phase, row['checkpoint']))
    receipt = reader.document(_named_binding(phase, row['custody_receipt']))
    authenticated = reader.document(row['verified_custody'])
    report = reader.document(row['scientific_report'])
    for key, value in dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',
            capture_ordinal=ordinal, plan_sha256=contract.PARENT_SHA256,
            program_scope_sha256=parent['storage']['program_scope_sha256'],
            checkpoint=row['checkpoint'], status='ARCHIVED_AND_RELEASED',
            scientific_validity='NOT_ASSESSED', execution_authority=False).items():
        same(receipt[key], value, 'original custody '+key)
    for key, value in dict(capture_ordinal=ordinal, checkpoint=row['checkpoint'],
            custody_receipt=row['custody_receipt'], execution_authority=False).items():
        same(authenticated[key], value, 'completed custody check '+key)
    names = capture_registry.capture_names('Q16b', ordinal)
    require(len(receipt['artifacts']) == len(authenticated['artifacts']) == len(names) == 6,
            'six original Q16b artifacts required')
    tip = admission._ledger_record(reader, program/'ledger', receipt['ledger_tip'])
    logical = []
    for name, artifact, verified in zip(names, receipt['artifacts'], authenticated['artifacts'], strict=True):
        same(artifact['logical']['file_name'], name, 'original logical filename')
        same(artifact['logical'], artifact['expected_logical'], 'no original discrepancy')
        same(artifact['failure_receipt'], None, 'no original custody failure')
        same(artifact['artifact_id'], contract.PARENT_SHA256+':'+name, 'original artifact identity')
        for key in ('artifact_id','logical','physical','archive_name','released_record'):
            same(artifact[key], verified[key], 'authenticated original '+key)
        same(verified['role'], vars(capture_registry.role_profile('Q16b', name)), 'original role')
        record = admission._ledger_record(reader, program/'ledger', artifact['released_record'])
        same(record['kind'], 'RELEASED', 'original release kind')
        same(record['artifact_id'], artifact['artifact_id'], 'original release identity')
        require(record['sequence'] <= tip['sequence'], 'release after original custody')
        for key in ('header','physical','archive_name'):
            same(record['payload'][key], verified[key], 'released original '+key)
        same(record['payload']['checkpoint_sha256'], row['checkpoint']['sha256'], 'released checkpoint')
        header = verified['header']
        same(header['artifact_id'], artifact['artifact_id'], 'original archive identity')
        same(header['canonical_sha256'], artifact['logical']['sha256'], 'original canonical hash')
        same(header['canonical_size_bytes'], artifact['logical']['size_bytes'], 'original canonical size')
        name_hash = hashlib.sha256(artifact['artifact_id'].encode()).hexdigest()+'.cpfa'
        same(artifact['archive_name'], name_hash, 'original archive basename')
        expected = archive.PhysicalBinding(**artifact['physical'])
        archive_path = program/'archives'/name_hash
        require(archive_path.stat(follow_symlinks=False).st_nlink == 1, 'original archive hardlink')
        physical = archive.hash_file(archive_path, max_bytes=expected.size_bytes,
                                     deadline_ns=int(reader.deadline*10**9))
        same(vars(physical), vars(expected), 'current physical archive bytes')
        logical.append(artifact['logical'])
    same(cp['artifacts'], logical, 'original checkpoint artifact order')
    sources = tuple(types.SimpleNamespace(expected=types.SimpleNamespace(**r)) for r in logical)
    checkpoint.validate_checkpoint(cp, action='Q16b', plan_sha256=contract.PARENT_SHA256,
                                   capture=capture, sources=sources)
    same(cp['native_complete'], True, 'original native completion')
    same(authenticated['native_result_after_cleanup'], cp['native_result_after_cleanup'], 'actual native cleanup')
    calibration._valid_summary('Q16b', report, capture, item['resources'])
    index = {row['file_name']:row for row in logical}
    for i, phase_report in enumerate(report['phases']):
        native = cp['native_result_after_cleanup']['session']['phases'][i]
        for field in ('attempted','accepted','full'):
            same(phase_report['counts'][field], native['producer'][field], 'independent producer '+field)
        same(phase_report['counts']['consumed_including_drain'], native['consumer']['consumed_including_drain'],
             'independent consumer reconciliation')
        for role in ('producer','consumer'):
            name = f"q16b-c{ordinal}-{phase_report['phase']}-{role}.bin"
            same(phase_report['stream_sha256'][role], index[name]['sha256'], 'original raw report hash')
    registration_path = program/'ledger'/f"{tip['sequence']+1:016d}.json"
    require(registration_path.stat().st_size <= 131072, 'bounded receipt registration')
    raw = registration_path.read_bytes()
    registration = reader.document(dict(path=str(registration_path), size_bytes=len(raw),
                                       sha256=hashlib.sha256(raw).hexdigest()))
    same(registration['previous_sha256'], receipt['ledger_tip']['sha256'], 'receipt registration chain')
    same(registration['kind'], 'CUSTODY_RECEIPT', 'receipt registration kind')
    same(registration['payload'], dict(family_id=contract.PARENT_SHA256,
        checkpoint_sha256=row['checkpoint']['sha256'], receipt=row['custody_receipt']), 'registered receipt')


def admit(plan, validation):
    reader = admission.BoundReader()
    continuation = plan['continuation']
    parent_bytes = reader.read(continuation['parent_plan'])
    extent = contract.validate_parent(plan, parent_bytes)
    parent = admission._json(parent_bytes)
    binding = continuation['accepted_prefix_manifest']
    same([binding['size_bytes'],binding['sha256']], [PREFIX_SIZE,PREFIX_SHA256], 'actual completed17 gate')
    prefix = reader.document(binding)
    for key, value in dict(status='PREFIX_17_VALID_CUSTODY_COMPLETE',original_plan_sha256=contract.PARENT_SHA256,
            original_source_revision=contract.PARENT_SOURCE,original_worker_sha256=ORIGINAL_WORKER,
            stand_id=plan['stand_id'],execution_authority=False,phase18_authority=False).items():
        same(prefix[key], value, 'retained prefix '+key)
    boot = pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    same(prefix['boot_id'], boot, 'same retained physical boot')
    same([row['original_ordinal'] for row in prefix['captures']], list(range(17)), 'complete prefix order')
    same(prefix['prefix_validation']['sha256'], VALIDATION_SHA256, 'completed independent analysis')
    analysis = reader.document(prefix['prefix_validation'])
    same(analysis['all_raw_reconstructed_and_hash_checked'], True, 'actual original inverse')
    same(analysis['captures'], 17, 'all17 independently valid')
    require(all(row['report']==prefix['captures'][i]['scientific_report'] for i,row in enumerate(analysis['reports'])),
            'actual17 independent report bindings')
    recovery = reader.document(prefix['recovery'])
    for key, value in dict(repeated_measurements=0,encoded_new_archives=False,
            all17_scientific_reports_preserved=True,original_failed_family_still_failed=True).items():
        same(recovery[key], value, 'actual storage recovery '+key)
    auth_bytes = reader.read(prefix['recovery_authorization'])
    same(prefix['recovery_authorization']['sha256'], RECOVERY_AUTH_SHA256, 'signed actual recovery authority')
    reader.read(prefix['recovery_signature'])
    trust = validation.resolutions['S17-EXT-003'].semantic_context['trust']
    signature._verify_signature(auth_bytes, pathlib.Path(prefix['recovery_signature']['path']), trust)
    request = reader.document(prefix['original_request'])
    same(request['action_inputs']['plan'], parent, 'actual original signed plan')
    program = pathlib.Path(request['evidence_root_binding']['absolute_path']).parent.parent
    admission._ledger_record(reader, program/'ledger', prefix['ledger_before'])
    admission._ledger_record(reader, program/'ledger', prefix['ledger_after'])
    for row in prefix['captures']:
        _capture(reader, row, parent, program)
    proof = reader.document(continuation['compatibility_manifest'])
    fields(proof, 'schema_version original current original_qualification source_comparisons queue_libraries '
                  'project_headers platform_manifests execution_authority phase18_authority', 'prefix compatibility')
    same(proof['schema_version'], COMPATIBILITY_SCHEMA, 'prefix compatibility version')
    same([proof['execution_authority'],proof['phase18_authority']], [False,False], 'no compatibility authority')
    context_binding = proof['original_qualification']
    same([context_binding['size_bytes'], context_binding['sha256']],
         [ORIGINAL_CONTEXT_SIZE, ORIGINAL_CONTEXT_SHA256], 'actual original qualification export')
    context = reader.document(context_binding)
    same(context['schema_version'], 'cpu-prefetch-stage17-d260-prefix-qualification-context/1', 'original qualification export')
    same(context['projection_id'], 'D260-PREFIX-COMPATIBILITY-FIELDS-v1', 'original qualification fields')
    same(context['boot_id'], boot, 'original qualification boot')
    same(context['original_request'], prefix['original_request'], 'original qualification request')
    same([context['execution_authority'],context['phase18_authority']], [False,False], 'original export authority')
    old = types.SimpleNamespace(resolutions={k:types.SimpleNamespace(semantic_context=v['semantic_context'])
                                           for k,v in context['resolutions'].items()})
    old = association.associated_validation(old, plan['stand_id'])
    current = association.associated_validation(validation, plan['stand_id'])
    view = handoff.make_handoff()
    releases = {side:view._release(proof[side], checked.resolutions['S17-EXT-006'].semantic_context,
                                  reader, source) for side,checked,source in
                [('original',old,contract.PARENT_SOURCE),('current',current,plan['source_revision'])]}
    same(old.resolutions['S17-EXT-006'].semantic_context['release_artifact_sha256'], ORIGINAL_WORKER, 'actual original worker')
    same(old.resolutions['S17-EXT-006'].semantic_context['inventory_sha256'], ORIGINAL_INVENTORY, 'actual original inventory')
    same(proof['original']['formal_codegen']['sha256'], ORIGINAL_CODEGEN, 'actual original generated-code evidence')
    view._platforms(proof['platform_manifests'], old, current, reader)
    names = admission._source_names(releases['original'][1])
    same(sorted(names), sorted(admission._source_names(releases['current'][1])), 'entire original measured closure')
    view._comparison(proof['source_comparisons'], names, releases, reader, identical=False)
    view._comparison([dict(relative_path=view.QUEUE, **proof['queue_libraries'])], {view.QUEUE}, releases, reader, identical=True)
    view._comparison(proof['project_headers'], set(view.HEADERS), releases, reader, identical=True)
    for side,(root,_,report) in releases.items():
        view.codegen.validate_report_bindings(report,binary=pathlib.Path(proof[side]['worker']['path']),source_root=pathlib.Path(root))
    reader.finish()
    return extent
