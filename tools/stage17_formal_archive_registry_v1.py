"""Read-only logical/physical custody verification for one formal capture.

The caller owns the admitted ProgramStore scope and qualified bounded decoder
runtime. This verifies custody only; independent raw scientific analysis follows
through the returned exact logical-to-physical inventory.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import os
import struct

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
from stage17_formal_checkpoint_v1 import validate_checkpoint
from stage17_output_registry_v11 import artifact_identity, capture_names

RECEIPT_FIELDS = frozenset(("schema_version program_scope_sha256 plan_sha256 capture_ordinal "
                           "checkpoint ledger_tip artifacts status scientific_validity execution_authority").split())
ARTIFACT_FIELDS = frozenset(("logical expected_logical failure_receipt artifact_id released_record "
                            "archive_name physical").split())


def same(actual, expected, label):
    if archive.canonical(actual) != archive.canonical(expected):
        raise custody.CustodyError(label + " differs")


def _bound(store, path, binding, maximum):
    value = custody.BoundFile(**binding)
    raw = store._read_bound(path / value.file_name, value.binding(), maximum)
    return archive.parse_json(raw)


def _ledger(store, binding):
    return store.read_verified_record(custody.BoundFile(**binding))


def role_profile(action, name):
    role, canonical_format, _ = artifact_identity(action, name)
    layout = ("bytes" if name.endswith("-control.json") else
              "u64" if name.endswith(("-node-order.bin", "-schedule.bin")) else
              "demand" if name.endswith("-demand.bin") else
              "producer" if name.endswith("-producer.bin") else "consumer")
    return archive.RoleProfile(role, canonical_format, layout)


def verify_capture(*, store, action, capture, checkpoint_binding, receipt_binding,
                   decoder_profile, decoder_limits, readback):
    """Mandatory readback is the qualified child decoder, never a truth flag.

    Tests may use the same independent decoder in a bounded local process.
    Production admission must bind this implementation and the runtime profile
    to the qualified release, not accept a caller-authored proof object.
    """
    return _verify_capture(store=store, action=action, capture=capture,
        checkpoint_binding=checkpoint_binding, receipt_binding=receipt_binding,
        decoder_profile=decoder_profile, decoder_limits=decoder_limits, readback=readback,
        metadata_only=False)


def verify_capture_metadata(*, store, action, capture, checkpoint_binding,
                            receipt_binding, decoder_profile, decoder_limits):
    """Check durable custody and physical bytes, without claiming an inverse.

    No decoder callback, fake VerifiedArchive or scientific credit. Historical
    pre-release readback records remain evidence; independent inverse is separate.
    """
    return _verify_capture(store=store, action=action, capture=capture,
        checkpoint_binding=checkpoint_binding, receipt_binding=receipt_binding,
        decoder_profile=decoder_profile, decoder_limits=decoder_limits, readback=None,
        metadata_only=True)


def _physical_metadata(path, *, expected_header, role, physical, profile, limits):
    archive.validate_header(expected_header, role, profile, limits)
    physical.validate()
    if physical.size_bytes > limits.max_archive_bytes:
        raise custody.CustodyError("physical metadata archive byte bound")
    with archive.open_regular(path) as stream:
        before = archive.file_stamp(os.fstat(stream.fileno()))
        if before[2] != physical.size_bytes or before[-1] != 1:
            raise custody.CustodyError("physical archive size or link identity differs")
        prefix = stream.read(16)
        if len(prefix) != 16 or prefix[:8] != b"CPFA2331":
            raise custody.CustodyError("physical archive header prefix differs")
        length, = struct.unpack("<Q", prefix[8:])
        if not 0 < length <= limits.max_header_bytes:
            raise custody.CustodyError("physical archive header bound")
        same(archive.parse_json(stream.read(length)), expected_header, "physical archive header")
        if before != archive.file_stamp(os.fstat(stream.fileno())):
            raise custody.CustodyError("physical archive changed during header read")
    if archive.hash_file(path, max_bytes=physical.size_bytes, deadline_ns=limits.deadline_ns) != physical:
        raise custody.CustodyError("physical archive hash differs")
    if before != archive.file_stamp(path.stat(follow_symlinks=False)):
        raise custody.CustodyError("physical archive identity changed during metadata verification")
    return physical


def _verify_capture(*, store, action, capture, checkpoint_binding, receipt_binding,
                    decoder_profile, decoder_limits, readback, metadata_only):
    store._check()
    ordinal = archive.uint(capture["ordinal"], "capture ordinal")
    if (store.family_id not in store._families
            or checkpoint_binding["file_name"] != f"formal-capture-{ordinal}-final-checkpoint.json"
            or receipt_binding["file_name"] != f"formal-capture-{ordinal}-archive-custody.json"):
        raise custody.CustodyError("capture working scope or receipt identity differs")
    family = store._families[store.family_id]
    observed = store.working.stat(follow_symlinks=False)
    if (observed.st_dev, observed.st_ino) != (family["device"], family["inode"]):
        raise custody.CustodyError("family output root differs from original ledger")
    final = _bound(store, store.working, checkpoint_binding, store.limits.max_checkpoint_bytes)
    receipt = _bound(store, store.working, receipt_binding, store.limits.max_record_bytes)
    if set(receipt) != RECEIPT_FIELDS:
        raise custody.CustodyError("custody receipt field set differs")
    for key, expected in dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1",
            program_scope_sha256=store.scope_sha256, plan_sha256=store.family_id,
            capture_ordinal=ordinal, checkpoint=checkpoint_binding, status="ARCHIVED_AND_RELEASED",
            scientific_validity="NOT_ASSESSED", execution_authority=False).items():
        same(receipt[key], expected, "custody receipt " + key)
    tip = _ledger(store, receipt["ledger_tip"])
    expected_names = capture_names(action, ordinal)
    rows = receipt["artifacts"]
    if type(rows) is not list or len(rows) != len(expected_names):
        raise custody.CustodyError("custody receipt omits a required original artifact")
    sources, inventory = [], []
    for name, row in zip(expected_names, rows, strict=True):
        if type(row) is not dict or set(row) != ARTIFACT_FIELDS:
            raise custody.CustodyError("custody artifact row differs")
        artifact_id = store.family_id + ":" + name
        same(row["artifact_id"], artifact_id, "logical artifact identity")
        logical = custody.BoundFile(**row["logical"])
        logical.binding()
        same(logical.file_name, name, "logical file name")
        same(row["expected_logical"], row["logical"], "actual versus original canonical bytes")
        same(row["failure_receipt"], None, "successful custody failure binding")
        source = custody.SourceBinding(artifact_id, logical, logical.binding(), None)
        sources.append(source)
        record = _ledger(store, row["released_record"])
        if record["sequence"] > tip["sequence"]:
            raise custody.CustodyError("release occurred after the receipt's ledger tip")
        same(record["kind"], "RELEASED", "source release transition")
        same(record["artifact_id"], artifact_id, "release artifact identity")
        same(store._states.get(artifact_id), record, "durable current artifact state")
        payload = record["payload"]
        same(payload["source"], asdict(source), "released original source binding")
        same(payload["checkpoint_sha256"], checkpoint_binding["sha256"], "release checkpoint")
        same(payload["storage_domain_id"], store.scope["storage_domain_id"], "storage domain")
        archive_name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".cpfa"
        same(row["archive_name"], archive_name, "physical archive identity")
        same(payload["archive_name"], archive_name, "release physical path")
        same(payload["physical"], row["physical"], "release physical binding")
        role = role_profile(action, name)
        same(payload["role"], asdict(role), "canonical role profile")
        header = payload["header"]
        same(header["artifact_id"], artifact_id, "archive header logical identity")
        same(header["canonical_size_bytes"], logical.size_bytes, "archive canonical size")
        same(header["canonical_sha256"], logical.sha256, "archive canonical hash")
        expected_phase = next((phase for phase in ("warmup", "measurement") if f"-{phase}-" in name), None)
        expected_run = capture[expected_phase]["run_id"] if expected_phase else None
        same(header["phase"], expected_phase, "archive phase")
        same(header["run_id"], expected_run, "archive run identity")
        expected_worker = next((worker for worker in ("producer", "consumer")
                                if f"-{worker}" in name), None)
        same(header["worker"], expected_worker, "archive worker identity")
        arguments = dict(expected_header=header, role=role,
            physical=archive.PhysicalBinding(**row["physical"]),
            profile=decoder_profile, limits=decoder_limits)
        path = store.root / "archives" / archive_name
        if metadata_only:
            physical = _physical_metadata(path, **arguments)
        else:
            physical = custody.checked_readback(readback, path, **arguments).physical
        inventory.append(dict(artifact_id=artifact_id, logical=asdict(logical),
            archive_name=archive_name, physical=asdict(physical), header=header,
            role=asdict(role), released_record=row["released_record"]))
    validate_checkpoint(final, action=action, plan_sha256=store.family_id,
                        capture=capture, sources=tuple(sources))
    same(final["native_complete"], True, "native checkpoint completion")
    retained_copy = store.root / "metadata" / ("checkpoint-" + checkpoint_binding["sha256"] + ".json")
    store._read_bound(retained_copy, custody.BoundFile(**checkpoint_binding).binding(),
                      store.limits.max_checkpoint_bytes)
    # The next record binds the durable receipt without a circular self-hash.
    following = tip["sequence"] + 1
    if following >= len(store._record_bindings):
        raise custody.CustodyError("custody receipt is not in the authenticated ledger")
    registration = store.read_verified_record(store._record_bindings[following])
    same(registration["kind"], "CUSTODY_RECEIPT", "receipt ledger registration")
    same(registration["payload"], dict(family_id=store.family_id,
         checkpoint_sha256=checkpoint_binding["sha256"], receipt=receipt_binding), "receipt registration binding")
    store._check()
    return dict(capture_ordinal=ordinal, checkpoint=checkpoint_binding,
                custody_receipt=receipt_binding, artifacts=inventory,
                native_result_after_cleanup=final["native_result_after_cleanup"],
                inverse_readback_performed=not metadata_only,
                scientific_validity="NOT_ASSESSED", execution_authority=False)
