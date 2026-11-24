"""Prospective S180 directory identity before EXT009; no capture permission.

Uses existing D233 FAMILY/metadata primitives without changing its ledger or
historical scopes. A separate immutable EXT009 binding is mandatory before the
S180 store may prepare a capture. The qualified caller authenticates EXT009.
"""
from dataclasses import asdict
import hashlib
import os
import stat

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as base
import stage17_s180_checkpoint_v1 as contract

SCHEMA = "cpu-prefetch-stage17-s180-storage-extension/2"
RESERVATION_SCHEMA = "cpu-prefetch-stage17-s180-directory-reservation/1"
ADMISSION_SCHEMA = "cpu-prefetch-stage17-s180-storage-admission-binding/1"


def require(condition, message):
    if not condition:
        raise base.CustodyError("S180 directory reservation: " + message)


def _names(store):
    return (f"s180-extension-{store.family_id}.json",
            f"s180-reservation-{store.family_id}.json",
            f"s180-admission-{store.family_id}.json")


def _extension(store):
    return dict(schema_version=SCHEMA, approval_sha256=contract.APPROVAL_SHA256,
        blueprint_sha256=contract.BLUEPRINT_SHA256, program_scope_sha256=store.scope_sha256,
        family_id=store.family_id, program_id=store.scope["program_id"],
        storage_domain_id=store.scope["storage_domain_id"],
        shared_program_quota_bytes=base.PROGRAM_QUOTA, workspace_bytes=base.WORKSPACE,
        analysis_scratch_bytes=base.SCRATCH, reserve_bytes=base.RESERVE,
        admission_receipt_name=_names(store)[2], admission_required_before_capture=True,
        independent_raw_backup=False, execution_authority=False, phase18_authority=False,
        policy_id="D310-S180-LOSSLESS-STAND-PRIMARY-v1")


def _root(store):
    st = store.working.stat(follow_symlinks=False)
    require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid() and not st.st_mode & 0o022
        and (st.st_dev, st.st_ino) == (
        store._families[store.family_id]["device"], store._families[store.family_id]["inode"]),
        "working directory differs from durable FAMILY")
    return dict(absolute_path=str(store.working), device=st.st_dev, inode=st.st_ino)


def extension_binding(store):
    store._check()
    require(store.family_id in store._families, "original reserved FAMILY is missing")
    binding = base.BoundFile(**store._families[store.family_id]["storage_extension"])
    require(binding.file_name == _names(store)[0], "extension name differs")
    raw = store._read_bound(store.root / "metadata" / binding.file_name,
        binding.binding(), store.limits.max_record_bytes)
    require(raw == archive.canonical(_extension(store)), "original reservation extension differs")
    store._extension_binding = binding
    _root(store)
    return binding


def is_reserved_family(store):
    family = store._families.get(store.family_id)
    if family is None or type(family.get("storage_extension")) is not dict:
        return False
    binding = base.BoundFile(**family["storage_extension"])
    raw = store._read_bound(store.root / "metadata" / binding.file_name,
        binding.binding(), store.limits.max_record_bytes)
    return archive.parse_json(raw).get("schema_version") == SCHEMA


def inspect_reservation(store):
    """Read the original directory receipt; this grants no admission or capture."""
    extension = extension_binding(store)
    name = _names(store)[1]
    raw = store._read_bound(store.root / "metadata" / name, None, store.limits.max_record_bytes)
    document = archive.parse_json(raw)
    require(set(document) == {"schema_version", "family_id", "program_scope_sha256",
        "storage_extension", "family_record", "evidence_root_binding", "admission_bound",
        "execution_authority", "phase18_authority"}, "reservation receipt fields differ")
    record = base.BoundFile(**document["family_record"])
    actual = store.read_verified_record(record)
    require(actual["kind"] == "FAMILY" and actual["artifact_id"] is None
            and actual["payload"] == store._families[store.family_id],
            "reservation does not name the original FAMILY record")
    expected = dict(schema_version=RESERVATION_SCHEMA, family_id=store.family_id,
        program_scope_sha256=store.scope_sha256, storage_extension=asdict(extension),
        family_record=asdict(record), evidence_root_binding=_root(store),
        admission_bound=False, execution_authority=False, phase18_authority=False)
    require(raw == archive.canonical(expected), "original reservation receipt differs")
    binding = base.BoundFile(name, len(raw), hashlib.sha256(raw).hexdigest())
    return document, binding


def reserve_family(store):
    store._check()
    require(store.ext009_resolution_sha256 is None, "reservation must explicitly precede EXT009")
    require(store.family_id not in store._families, "reservation cannot be replayed or adopted")
    require(not any(v.get("storage_extension") is not None for v in store._families.values()),
            "D310 permits only one prospective S180 family")
    require(not store._capture_pending and all(s["kind"] == "RELEASED" for s in store._states.values()),
            "previous capture custody is incomplete")
    require(not store.working.exists() and not store.working.is_symlink(), "orphan working directory")
    for name in _names(store):
        path = store.root / "metadata" / name
        require(not path.exists() and not path.is_symlink(), "orphan reservation/admission metadata")
    store._extension_binding = store.retain_metadata(_names(store)[0], archive.canonical(_extension(store)))
    store._reserving_directory = True
    try:
        # Uses only the existing FAMILY transition and its exclusive mkdir.
        base.ProgramStore.prepare_family(store, store.family_id)
    finally:
        store._reserving_directory = False
    document = dict(schema_version=RESERVATION_SCHEMA, family_id=store.family_id,
        program_scope_sha256=store.scope_sha256, storage_extension=asdict(store._extension_binding),
        family_record=asdict(store.ledger_binding()), evidence_root_binding=_root(store),
        admission_bound=False, execution_authority=False, phase18_authority=False)
    binding = store.retain_metadata(_names(store)[1], archive.canonical(document))
    return dict(document=document, binding=asdict(binding))


def _admission(store, reservation):
    require(store.ext009_resolution_sha256 is not None, "actual EXT009 binding is required before capture")
    return dict(schema_version=ADMISSION_SCHEMA, family_id=store.family_id,
        program_scope_sha256=store.scope_sha256, ext009_resolution_sha256=store.ext009_resolution_sha256,
        reservation=asdict(reservation), execution_authority=False, phase18_authority=False)


def bind_admission(store):
    """Record caller-authenticated EXT009 once; never overwrites/retries a receipt."""
    store._check()
    require(store.ext009_resolution_sha256 is not None, "actual EXT009 binding is absent")
    _, reservation = inspect_reservation(store)
    require(not any(store.working.iterdir()), "capture/attempt data predates storage admission")
    # retain_metadata is durable, exclusive, quota checked; an interrupted file
    # remains evidence and cannot be adopted or repaired by this method.
    return store.retain_metadata(_names(store)[2], archive.canonical(_admission(store, reservation)))


def verify_admission(store):
    _, reservation = inspect_reservation(store)
    expected = archive.canonical(_admission(store, reservation))
    raw = store._read_bound(store.root / "metadata" / _names(store)[2], None, store.limits.max_record_bytes)
    require(raw == expected, "storage admission absent, partial or belongs to another EXT009")


def prepare_reserved_family(store, family_id):
    require(family_id == store.family_id, "reserved family differs")
    verify_admission(store)
    return base.ProgramStore.prepare_family(store, family_id)
