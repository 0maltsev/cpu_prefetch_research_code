"""Cold job construction from original native receipts and observed source bytes.

The qualified caller must keep the native worker parked throughout this call.
No observations are truncated, filtered or given scientific credit here.
"""
from dataclasses import asdict
import hashlib
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
from stage17_formal_archive_registry_v1 import capture_names, role_profile
from stage17_formal_checkpoint_v1 import validate_checkpoint

HEADER_BYTES = 32768
IO_CHUNK_BYTES = 1024**2
CONTEXT_BYTES = 64 * 1024**2


def build_capture_jobs(*, store, action, capture, document, profile, storage,
                       maximum_capture_bytes, deadline_ns, verify_quiescence):
    """Observe bounded actual files; retain a discrepancy before any release.

    Returns the exact original source order. Incomplete native publication may
    contribute only a successful prefix; unlisted partial files remain on disk.
    The caller's failure path must retain that directory and stop the family.
    """
    store._check()
    if (profile.decoder.implementation_profile_sha256 != storage["implementation_profile_sha256"]
            or store.scope_sha256 != storage["program_scope_sha256"]
            or store.scope["program_id"] != storage["program_id"]):
        raise custody.CustodyError("archive jobs differ from admitted program/profile")
    archive.uint(maximum_capture_bytes, "capture canonical byte bound", positive=True)
    archive.uint(deadline_ns, "cold job deadline", positive=True)
    names = capture_names(action, capture["ordinal"])
    references = document.get("artifacts")
    if (type(references) is not list or len(references) > len(names)
            or [r.get("file_name") for r in references] != list(names[:len(references)])):
        raise custody.CustodyError("native artifacts are not the original publication prefix")
    sources, jobs = [], []
    observed_bytes = 0
    for reference in references:
        if time.monotonic_ns() >= deadline_ns:
            raise custody.CustodyError("cold job deadline expired")
        verify_quiescence()
        if type(reference) is not dict or set(reference) != {"file_name", "size_bytes", "sha256"}:
            raise custody.CustodyError("original source binding field set differs")
        expected = custody.BoundFile(**reference)
        expected.binding()
        actual = archive.hash_file(store.working / expected.file_name,
            max_bytes=maximum_capture_bytes - observed_bytes, deadline_ns=deadline_ns)
        observed_bytes = archive.checked_sum(observed_bytes, actual.size_bytes)
        artifact_id = store.family_id + ":" + expected.file_name
        failure = None
        if actual != expected.binding():
            raw = archive.canonical(dict(schema_version="cpu-prefetch-stage17-source-discrepancy/1",
                artifact_id=artifact_id, plan_sha256=store.family_id, capture_ordinal=capture["ordinal"],
                expected=asdict(expected), observed=asdict(actual),
                scientific_validity="NOT_ASSESSED", execution_authority=False))
            if len(raw) > store.limits.max_checkpoint_bytes:
                raise custody.CustodyError("source discrepancy exceeds metadata bound")
            failure = store.retain_metadata("source-discrepancy-" + hashlib.sha256(artifact_id.encode()).hexdigest() + ".json", raw)
        source = custody.SourceBinding(artifact_id, expected, actual, failure)
        sources.append(source)
        name = expected.file_name
        role = role_profile(action, name)
        phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
        run_id = capture[phase]["run_id"] if phase else None
        worker = next((w for w in ("producer", "consumer") if f"-{w}" in name), None)
        width = role.row_bytes(run_id)
        fallback = None
        if width is not None:
            if actual.size_bytes % width:
                fallback = "INCOMPLETE_CANONICAL_ROW"
            elif actual != expected.binding():
                fallback = "SOURCE_BINDING_DISCREPANCY"
            elif document.get("native_complete") is not True:
                fallback = "NATIVE_CAPTURE_INCOMPLETE"
        rows = width is not None and fallback is None
        block_bytes = archive.checked_product(archive.ROWS_PER_BLOCK, width) if rows else archive.BYTE_BLOCK
        blocks = (actual.size_bytes + block_bytes - 1) // block_bytes
        decoded_bound = max(1, min(actual.size_bytes, block_bytes))
        encoded_bound = archive.checked_sum(archive.checked_product(decoded_bound, 2), IO_CHUNK_BYTES)
        staging = archive.uint(storage["archive_staging_bytes"], "archive staging", positive=True)
        header = dict(schema_version=archive.HEADER_SCHEMA, policy_id=archive.POLICY_ID,
            codec_id=archive.RAW_CODEC if rows else archive.BYTE_CODEC, artifact_id=artifact_id,
            artifact_role=role.artifact_role, canonical_format=role.canonical_format,
            run_id=run_id, phase=phase, worker=worker, canonical_size_bytes=actual.size_bytes,
            canonical_sha256=actual.sha256, row_bytes=width if rows else None,
            row_count=actual.size_bytes // width if rows else None, block_size_bytes=block_bytes,
            block_count=blocks, fallback_reason=fallback,
            implementation_profile_sha256=profile.decoder.implementation_profile_sha256,
            encoder_sha256=profile.encoder.sha256, zstd_library_sha256=profile.decoder.zstd_library_sha256,
            zstd_version="1.5.7", compression_level=3, worker_threads=1,
            window_log=profile.decoder.window_log, checksum_flag=1, content_size_flag=1, dictionary_id_flag=0)
        limits = archive.DecodeLimits(HEADER_BYTES, encoded_bound, decoded_bound, staging,
            actual.size_bytes, blocks, 1 << profile.decoder.window_log, deadline_ns)
        archive.validate_header(header, role, profile.decoder, limits)
        io_calls = archive.checked_product(8, archive.checked_sum(
            (actual.size_bytes + IO_CHUNK_BYTES - 1) // IO_CHUNK_BYTES,
            (staging + IO_CHUNK_BYTES - 1) // IO_CHUNK_BYTES, 4 * blocks, 32))
        encoder_limits = dict(window_log=profile.decoder.window_log, maximum_header_bytes=HEADER_BYTES,
            maximum_decoded_block_bytes=decoded_bound, maximum_encoded_block_bytes=encoded_bound,
            maximum_archive_bytes=staging, maximum_observed_context_bytes=CONTEXT_BYTES,
            io_chunk_bytes=IO_CHUNK_BYTES, maximum_io_calls=io_calls, deadline_monotonic_ns=deadline_ns)
        jobs.append(runtime.ArchiveJob(artifact_id, header, role, encoder_limits, limits))
    validate_checkpoint(document, action=action, plan_sha256=store.family_id,
                        capture=capture, sources=tuple(sources))
    verify_quiescence()
    return tuple(sources), tuple(jobs)
