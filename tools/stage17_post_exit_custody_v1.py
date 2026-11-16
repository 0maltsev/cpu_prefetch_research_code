"""Explicit post-exit closure of already published capture custody, D260/D262.

No encoder, new capture, live-worker claim or retry. The authorized caller
authenticates original signed lineage, all scientific prefix reports, current
worker absence/restoration and a separately signed storage-recovery authority.
This primitive rechecks original durable state and uses the ordinary guarded
working-copy release and custody publication paths. Incomplete failure stays
in the ledger; it is never reset or silently retried.
"""
from __future__ import annotations

from dataclasses import asdict

import stage17_formal_archive_custody_v1 as original_custody
import stage17_retained_capture_inspection_v1 as inspection
from stage17_formal_checkpoint_v1 import validate_checkpoint

VERSION = 'cpu-prefetch-stage17-post-exit-published-custody/1'


def close_published_capture(*, store, action, capture, checkpoint_binding,
                            profile, limits, readback, verify_post_exit,
                            retained_evidence, custody_api=original_custody):
    """Close only a fully published capture, after a raising post-exit verifier.

    retained_evidence maps named proof roles to real metadata BoundFile values.
    The verifier must authenticate their contents/signatures and must raise on
    failure, never return a boolean. This function supplies no authorization.
    custody_api must be the caller-authenticated profile's module namespace.
    """
    c = custody_api
    a = c.archive
    store._check()
    if store.release_working_copy.__func__.__globals__['archive'] is not a:
        raise c.CustodyError('store and authenticated decoder/custody namespaces differ')
    if not callable(verify_post_exit) or not callable(readback):
        raise c.CustodyError('post-exit verifier and actual archive readback required')
    required = {'authorization', 'signature', 'prefix_validation', 'native_failure', 'restoration'}
    if type(retained_evidence) is not dict or set(retained_evidence) != required:
        raise c.CustodyError('closed post-exit evidence set required')
    if store._checkpoint is not None or store._sources or store._verify_checkpoint is not None:
        raise c.CustodyError('post-exit closure requires a freshly reopened store')
    checkpoint = c.BoundFile(**checkpoint_binding)
    if store._capture_pending != {(store.family_id, checkpoint.sha256)}:
        raise c.CustodyError('another pending capture prevents post-exit closure')
    inspected = inspection.inspect_capture(store=store, action=action, capture=capture,
        checkpoint_binding=checkpoint_binding, decoder_profile=profile, decoder_limits=limits)
    sources = tuple(c.SourceBinding(row['artifact_id'], c.BoundFile(**row['logical']),
        a.PhysicalBinding(row['logical']['size_bytes'], row['logical']['sha256']), None)
        for row in inspected['artifacts'])
    ids = {s.artifact_id for s in sources}
    if any(state['kind'] != 'RELEASED' for key, state in store._states.items() if key not in ids):
        raise c.CustodyError('unrelated incomplete custody prevents post-exit closure')
    # This boundary deliberately cannot restart an encoder or interrupted unlink.
    # Every source must already have a published, verified representation.
    if not any(row['current_state'] == 'PUBLISHED' for row in inspected['artifacts']):
        raise c.CustodyError('no published source release remains to close')
    evidence = {}
    for role, value in retained_evidence.items():
        bound = c.BoundFile(**value)
        store._read_bound(store.root/'metadata'/bound.file_name,
                          bound.binding(), store.limits.max_checkpoint_bytes)
        evidence[role] = asdict(bound)
    document = a.parse_json(store._read_bound(store.working/checkpoint.file_name,
        checkpoint.binding(), store.limits.max_checkpoint_bytes))

    def verify(current, original_sources):
        validate_checkpoint(current, action=action, plan_sha256=store.family_id,
                            capture=capture, sources=original_sources)
        if verify_post_exit(current, original_sources) is not None:
            raise c.CustodyError('post-exit verifier must raise, not return a boolean')

    verify(document, sources)
    # Authenticate all still-present originals before any release intent is written.
    for source in sources:
        if store._states[source.artifact_id]['kind'] == 'PUBLISHED':
            if a.hash_file(store.working/source.expected.file_name,
                    max_bytes=source.actual.size_bytes, deadline_ns=limits.deadline_ns) != source.actual:
                raise c.CustodyError('published original bytes changed')
    family = store._families[store.family_id]
    store._family_identity = (family['device'], family['inode'])
    store._checkpoint = (checkpoint, 'checkpoint-'+checkpoint.sha256+'.json', document)
    store._sources = {s.artifact_id:s for s in sources}
    store._verify_checkpoint = verify
    store._quiescent()  # explicit verified post-exit condition; no live worker invented
    store.append('RECOVERY', None, dict(schema_version=VERSION, family_id=store.family_id,
        checkpoint_sha256=checkpoint.sha256, capture_ordinal=capture['ordinal'],
        mode='POST_EXIT_ALREADY_PUBLISHED_ONLY', retained_evidence=evidence,
        scientific_validity='NOT_ASSESSED', execution_authority=False))
    for source in sources:
        if store._states[source.artifact_id]['kind'] == 'PUBLISHED':
            store.release_working_copy(source.artifact_id, profile=profile,
                                       limits=limits, readback=readback)
    rows = []
    for source in sources:
        state = store._states[source.artifact_id]
        if state['kind'] != 'RELEASED':
            raise c.CustodyError('post-exit source did not reach RELEASED')
        rows.append(dict(logical=asdict(source.expected), expected_logical=asdict(source.expected),
            failure_receipt=None, artifact_id=source.artifact_id,
            released_record=asdict(store.ledger_binding(state)),
            archive_name=state['payload']['archive_name'], physical=state['payload']['physical']))
    receipt = dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',
        program_scope_sha256=store.scope_sha256, plan_sha256=store.family_id,
        capture_ordinal=capture['ordinal'], checkpoint=asdict(checkpoint),
        ledger_tip=asdict(store.ledger_binding()), artifacts=rows,
        status='ARCHIVED_AND_RELEASED', scientific_validity='NOT_ASSESSED', execution_authority=False)
    binding = store.retain_custody_receipt(
        f"formal-capture-{capture['ordinal']}-archive-custody.json", a.canonical(receipt))
    return dict(schema_version=VERSION, checkpoint=asdict(checkpoint), custody_receipt=asdict(binding),
        ledger_tip=asdict(store.ledger_binding()), encoded_new_archives=False,
        repeated_measurements=0, scientific_validity='NOT_ASSESSED', execution_authority=False)
