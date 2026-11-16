"""Read-only inspection of a native-complete capture with unfinished custody.

This is an analysis input boundary, never a completed-family admission. It
accepts only already published archives and authenticates their actual bytes.
No source is released, no ledger record is written and no experiment is run.
The caller must separately authenticate the original signed plan and release.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib

import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
from stage17_formal_checkpoint_v1 import validate_checkpoint


def inspect_capture(*, store, action, capture, checkpoint_binding,
                    decoder_profile, decoder_limits):
    """Return actual published artifacts, explicitly withholding custody credit."""
    store._check()
    same = registry.same
    ordinal = capture['ordinal']
    same(checkpoint_binding['file_name'],
         f'formal-capture-{ordinal}-final-checkpoint.json', 'checkpoint name')
    family = store._families.get(store.family_id)
    if family is None:
        raise custody.CustodyError('unregistered original family')
    observed = store.working.stat(follow_symlinks=False)
    same([observed.st_dev, observed.st_ino],
         [family['device'], family['inode']], 'original working directory')
    checkpoint = custody.BoundFile(**checkpoint_binding)
    raw = store._read_bound(store.working/checkpoint.file_name,
                           checkpoint.binding(), store.limits.max_checkpoint_bytes)
    document = registry.archive.parse_json(raw)
    same(document['native_complete'], True, 'native completion')
    if (store.family_id, checkpoint.sha256) not in store._capture_pending:
        raise custody.CustodyError('original checkpoint is not pending custody')
    retained_name = 'checkpoint-'+checkpoint.sha256+'.json'
    if store._read_bound(store.root/'metadata'/retained_name,
            checkpoint.binding(), store.limits.max_checkpoint_bytes) != raw:
        raise custody.CustodyError('retained original checkpoint differs')
    registration = None
    for binding in reversed(store._record_bindings):
        record = store.read_verified_record(binding)
        if (record['kind'] == 'CHECKPOINT'
                and record['payload'].get('family_id') == store.family_id
                and record['payload'].get('original_receipt') == checkpoint_binding):
            registration = record
            break
    if registration is None:
        raise custody.CustodyError('checkpoint lacks original ledger registration')
    same(registration['payload']['retained_receipt'], retained_name,
         'checkpoint retained path')
    names = registry.capture_names(action, ordinal)
    same([row['file_name'] for row in document['artifacts']], list(names),
         'complete original capture artifacts')
    sources = tuple(custody.SourceBinding(store.family_id+':'+row['file_name'],
        custody.BoundFile(**row), custody.BoundFile(**row).binding(), None)
        for row in document['artifacts'])
    same(registration['payload']['sources'], [asdict(s) for s in sources],
         'original checkpoint sources')
    validate_checkpoint(document, action=action, plan_sha256=store.family_id,
                        capture=capture, sources=sources)
    artifacts = []
    for source in sources:
        current = store._states.get(source.artifact_id)
        if current is None or current['kind'] not in ('PUBLISHED', 'RELEASED'):
            raise custody.CustodyError('required artifact has no published archive')
        record_binding = store.ledger_binding(current)
        if current['sequence'] <= registration['sequence']:
            raise custody.CustodyError('archive state precedes checkpoint')
        value = current['payload']
        same(value['source'], asdict(source), 'archive source')
        same(value['checkpoint_sha256'], checkpoint.sha256, 'archive checkpoint')
        same(value['storage_domain_id'], store.scope['storage_domain_id'], 'archive storage domain')
        name = source.expected.file_name
        archive_name = hashlib.sha256(source.artifact_id.encode()).hexdigest()+'.cpfa'
        same(value['archive_name'], archive_name, 'archive name')
        role = registry.role_profile(action, name)
        same(value['role'], asdict(role), 'archive role')
        header = value['header']
        expected_phase = next((p for p in ('warmup', 'measurement') if f'-{p}-' in name), None)
        expected_worker = next((w for w in ('producer', 'consumer') if f'-{w}' in name), None)
        for key, expected in dict(artifact_id=source.artifact_id,
                canonical_size_bytes=source.actual.size_bytes,
                canonical_sha256=source.actual.sha256, phase=expected_phase,
                run_id=capture[expected_phase]['run_id'] if expected_phase else None,
                worker=expected_worker).items():
            same(header[key], expected, 'archive header '+key)
        registry._physical_metadata(store.root/'archives'/archive_name,
            expected_header=header, role=role,
            physical=registry.archive.PhysicalBinding(**value['physical']),
            profile=decoder_profile, limits=decoder_limits)
        artifacts.append(dict(artifact_id=source.artifact_id, logical=asdict(source.expected),
            archive_name=archive_name, physical=value['physical'], header=header,
            role=asdict(role), current_state=current['kind'], state_record=asdict(record_binding)))
    store._check()
    return dict(capture_ordinal=ordinal, checkpoint=checkpoint_binding, artifacts=artifacts,
        native_result_after_cleanup=document['native_result_after_cleanup'],
        custody_complete=False, family_completion_established=False,
        inverse_readback_performed=False, scientific_validity='NOT_ASSESSED',
        execution_authority=False, phase18_authority=False)
