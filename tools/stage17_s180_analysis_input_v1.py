"""Original ledger/header inputs after collection; physical validity is pending.

The owned inverse workers must still hash and reconstruct every archive byte.
This input never permits native continuation or successful dataset publication.
Collection's existing strict registry route remains unchanged.
"""
import os
import struct
import time

import stage17_s180_archive_registry_v1 as registry
import stage17_s180_analysis_phase_v1 as phase

archive=registry.archive
require=phase.require
SCHEMA='cpu-prefetch-stage17-s180-pending-analysis-input/1'


def _header_metadata(path,*,expected_header,role,physical,profile,limits):
    require(time.monotonic_ns()<limits.deadline_ns,'original analysis header deadline expired')
    archive.validate_header(expected_header,role,profile,limits);physical.validate()
    require(physical.size_bytes<=limits.max_archive_bytes,'original physical byte ceiling')
    with archive.open_regular(path) as stream:
        before=archive.file_stamp(os.fstat(stream.fileno()))
        require(before[2]==physical.size_bytes and before[-1]==1,'original physical extent/link differs')
        prefix=stream.read(16)
        require(len(prefix)==16 and prefix[:8]==b'CPFA2331','original archive prefix differs')
        length,=struct.unpack('<Q',prefix[8:])
        require(0<length<=limits.max_header_bytes,'original archive header ceiling')
        registry.same(archive.parse_json(stream.read(length)),expected_header,'original physical header')
        require(before==archive.file_stamp(os.fstat(stream.fileno()))
            ==archive.file_stamp(path.stat(follow_symlinks=False)),'original archive changed during header check')
    require(time.monotonic_ns()<limits.deadline_ns,'original analysis header deadline expired')
    return physical  # Expected ledger binding, explicitly not a fresh payload hash.


def verify_original(*,phase_owner,store,capture,checkpoint_binding,receipt_binding,decoder_profile,decoder_limits):
    require(type(phase_owner) is phase._AnalysisPhase,'actual post-restoration analysis owner required')
    phase_owner.check()
    try:
        return _verify_owned(phase_owner=phase_owner,store=store,capture=capture,checkpoint_binding=checkpoint_binding,
            receipt_binding=receipt_binding,decoder_profile=decoder_profile,decoder_limits=decoder_limits)
    except BaseException:
        phase_owner.failed=True
        raise


def _verify_owned(*,phase_owner,store,capture,checkpoint_binding,receipt_binding,decoder_profile,decoder_limits):
    require(phase_owner.plan_sha256==store.family_id and not phase_owner._pool_consumed,
        'original unconsumed analysis plan differs')
    require(decoder_limits.deadline_ns<=phase_owner.deadline_ns,'input deadline exceeds original analysis phase')
    proof=registry._verify_capture_metadata(store=store,capture=capture,checkpoint_binding=checkpoint_binding,
        receipt_binding=receipt_binding,decoder_profile=decoder_profile,decoder_limits=decoder_limits,
        physical_metadata=_header_metadata)
    require(proof['continuation_allowed'] is True,'complete original released custody required')
    proof.update(schema_version=SCHEMA,continuation_allowed=False,original_collection_release_verified=True,
        physical_sha256_verification_pending=True,independent_inverse_required=True)
    phase_owner.check();return proof


def check(proof):
    """Recognize exact pending semantics without upgrading it to custody/authority."""
    if proof.get('schema_version')==SCHEMA:
        for key,value in dict(continuation_allowed=False,original_collection_release_verified=True,
                physical_sha256_verification_pending=True,independent_inverse_required=True,
                inverse_readback_performed=False,scientific_validity='NOT_ASSESSED',
                execution_authority=False,phase18_authority=False).items():
            registry.same(proof[key],value,'pending original analysis '+key)
    else:
        require('schema_version' not in proof and proof['continuation_allowed'] is True,
            'unknown original custody/input proof')
    return True
