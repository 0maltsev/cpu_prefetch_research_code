#!/usr/bin/env python3
"""D233 cold custody primitives for NEW prospective formal program roots only.

No collection, encoder launch, scientific validation, or execution authority.
The qualified caller must verify the checkpoint AND live quiescence, serialize
the codec child, and bind all inputs to its admitted plan. Filesystem operations
are no-overwrite; incomplete transitions are retained for explicit recovery.
"""
from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import time
from dataclasses import asdict, dataclass, replace
from typing import Callable, Iterator

import stage17_formal_archive_v1 as archive

PROGRAM_QUOTA = 6_000_000_000_000
WORKSPACE = 549_755_813_888
SCRATCH = 274_877_906_944
RESERVE = 17_179_869_184
PROPOSAL_SHA256 = "e0afc7010b7c0ee84adccf25eaf00679dbc79f51d1970fce3f42f8223ab91c02"
CHECKPOINT_SCHEMA = "cpu-prefetch-stage17-formal-capture-checkpoint/1"
LEDGER_SCHEMA = "cpu-prefetch-stage17-formal-representation-ledger/1"


class CustodyError(archive.ArchiveError):
    pass


@dataclass(frozen=True)
class CapacitySnapshot:
    free_bytes: int
    free_inodes: int
    retained_bytes: int
    in_flight_reserved_bytes: int
    unrelated_reserved_bytes: int
    unrelated_reserved_inodes: int


@dataclass(frozen=True)
class SpacePlan:
    canonical_capture_bytes: int
    control_and_final_bytes: int
    publication_staging_bytes: int
    archive_staging_bytes: int
    retained_metadata_bytes: int
    analysis_spool_bytes: int
    required_inodes: int


@dataclass(frozen=True)
class PhysicalUsage:
    logical_size_bytes: int
    allocated_bytes: int
    quota_bytes: int
    unique_objects: int


def check_capacity(snapshot: CapacitySnapshot, plan: SpacePlan) -> None:
    """Actual free space already excludes historical and current retained bytes."""
    for key, value in {**vars(snapshot), **vars(plan)}.items():
        archive.uint(value, key)
    used = archive.checked_sum(snapshot.retained_bytes, snapshot.in_flight_reserved_bytes)
    if archive.checked_sum(used, plan.archive_staging_bytes, plan.retained_metadata_bytes) > PROGRAM_QUOTA:
        raise CustodyError("shared program physical quota exhausted")
    if archive.checked_sum(plan.canonical_capture_bytes, plan.control_and_final_bytes,
                           plan.publication_staging_bytes, plan.archive_staging_bytes) > WORKSPACE:
        raise CustodyError("capture/publication/archive workspace exceeds W")
    if plan.analysis_spool_bytes > SCRATCH:
        raise CustodyError("analysis spool exceeds S")
    # Reserved future bytes are not yet reflected in free space: subtract only
    # physically retained bytes from Q, never the prospective reservations.
    required = archive.checked_sum(PROGRAM_QUOTA - snapshot.retained_bytes,
                                   WORKSPACE, SCRATCH, RESERVE, snapshot.unrelated_reserved_bytes)
    if snapshot.free_bytes < required:
        raise CustodyError("fresh free space does not support remaining Q+W+S+R")
    if snapshot.free_inodes < archive.checked_sum(plan.required_inodes, snapshot.unrelated_reserved_inodes):
        raise CustodyError("fresh inode budget insufficient")


@dataclass(frozen=True)
class BoundFile:
    file_name: str
    size_bytes: int
    sha256: str

    def binding(self):
        result = archive.PhysicalBinding(self.size_bytes, self.sha256)
        result.validate()
        _name(self.file_name)
        return result


@dataclass(frozen=True)
class SourceBinding:
    artifact_id: str
    expected: BoundFile
    actual: archive.PhysicalBinding
    failure_receipt: BoundFile | None


@dataclass(frozen=True)
class CustodyLimits:
    max_record_bytes: int
    max_ledger_records: int
    max_inventory_files: int
    max_checkpoint_bytes: int
    deadline_ns: int

    def validate(self):
        for key, value in vars(self).items():
            archive.uint(value, key, positive=True)
        self.check_time()

    def check_time(self):
        if time.monotonic_ns() >= self.deadline_ns:
            raise CustodyError("custody deadline expired")


def _name(name: str) -> str:
    if (not isinstance(name, str) or not name or name in (".", "..")
            or "/" in name or "\x00" in name):
        raise CustodyError("unsafe scoped file name")
    return name


def _sync_dir(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_new(path: Path, data: bytes):
    # A failed/partial write remains visible as an incomplete object; no retry.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        if os.write(fd, data) != len(data):
            raise CustodyError("partial custody write")
        os.fsync(fd)
    finally:
        os.close(fd)
    _sync_dir(path.parent)


def _move_no_replace(source: Path, destination: Path):
    # Linux atomic no-overwrite move: a raced source is retained at destination
    # for diagnosis, never unlinked under a stale path-based identity check.
    libc = ctypes.CDLL(None, use_errno=True)
    fn = libc.renameat2
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    fn.restype = ctypes.c_int
    if fn(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(source))


class ProgramStore:
    """Exclusive broker for one shared Q16a/b/c program, not one quota per family.

    New roots are created only by initialize(). Opening one requires its exact
    immutable scope hash. Unfinished ledger writes block normal progress.
    No method infers experimental authority from this storage-policy record.
    """
    DIRECTORIES = ("working", "archives", "ledger", "metadata", "spool", "release-hold")

    @staticmethod
    def initialize(root: Path, *, program_id: str, storage_domain_id: str,
                   prospective_admission_sha256: str) -> str:
        _name(program_id)
        _name(storage_domain_id)
        archive.sha(prospective_admission_sha256, "prospective admission hash")
        root = Path(root).absolute()
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise CustodyError("symlink program initialization path")
        root.mkdir(mode=0o700)  # parent must exist; never adopt an existing tree
        for name in ProgramStore.DIRECTORIES:
            (root / name).mkdir(mode=0o700)
        scope = archive.canonical(dict(schema_version="cpu-prefetch-stage17-formal-archive-scope/1",
            policy_id=archive.POLICY_ID, proposal_sha256=PROPOSAL_SHA256, program_id=program_id,
            storage_domain_id=storage_domain_id, prospective_admission_sha256=prospective_admission_sha256,
            created_at_unix_ns=time.time_ns(), shared_program_quota_bytes=PROGRAM_QUOTA,
            future_formal_only=True, execution_authority=False))
        _write_new(root / "scope.json", scope)
        _write_new(root / "broker.lock", b"")
        _sync_dir(root)
        _sync_dir(root.parent)
        return hashlib.sha256(scope).hexdigest()

    def __init__(self, root: Path, *, scope_sha256: str, family_id: str, limits: CustodyLimits):
        self.root, self.limits = Path(root).absolute(), limits
        self.scope_sha256 = archive.sha(scope_sha256, "scope hash")
        self.family_id = archive.sha(family_id, "family plan SHA256")
        self.working = self.root / "working" / self.family_id
        self._family_identity = None
        limits.validate()
        self._lock = None
        self._checkpoint = None
        self._sources = {}
        self._verify_checkpoint = None

    def __enter__(self):
        for path in (self.root, *self.root.parents):
            if path.is_symlink():
                raise CustodyError("symlink program path")
        for name in self.DIRECTORIES:
            path = self.root / name
            if path.is_symlink() or not path.is_dir():
                raise CustodyError("program directory identity invalid")
        self._directories = {name: (self.root / name).stat().st_ino for name in self.DIRECTORIES}
        self._root_identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        self._lock = archive.open_regular(self.root / "broker.lock")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw = self._read_bound(self.root / "scope.json", None, self.limits.max_record_bytes)
            if hashlib.sha256(raw).hexdigest() != self.scope_sha256:
                raise CustodyError("program scope changed")
            self.scope = archive.parse_json(raw)
            if (self.scope.get("policy_id") != archive.POLICY_ID
                    or self.scope.get("proposal_sha256") != PROPOSAL_SHA256
                    or self.scope.get("shared_program_quota_bytes") != PROGRAM_QUOTA
                    or self.scope.get("future_formal_only") is not True
                    or self.scope.get("execution_authority") is not False):
                raise CustodyError("unsupported program scope")
            self._replay()
            return self
        except BaseException:
            self._lock.close()
            self._lock = None
            raise

    def __exit__(self, *_):
        self._lock.close()
        self._lock = None

    def _check(self):
        self.limits.check_time()
        if self._lock is None:
            raise CustodyError("broker lock is not held")
        current = self.root.stat(follow_symlinks=False)
        if (current.st_dev, current.st_ino) != self._root_identity:
            raise CustodyError("program root changed")
        for name, inode in self._directories.items():
            st = (self.root / name).stat(follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or st.st_ino != inode or st.st_dev != current.st_dev:
                raise CustodyError("program directory changed or crossed filesystem")
        if self._family_identity is not None:
            st = self.working.stat(follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != self._family_identity:
                raise CustodyError("family working directory changed")

    def _family_scope_fields(self):
        return {}

    def prepare_family(self, family_id: str) -> Path:
        """Select/create only the constructor-bound admitted plan namespace.

        Existing names are usable only with their original durable FAMILY record;
        an orphan directory or incomplete prior capture requires explicit recovery.
        """
        self._check()
        if archive.sha(family_id, "family plan SHA256") != self.family_id:
            raise CustodyError("family differs from constructor binding")
        if self._capture_pending or any(state["kind"] != "RELEASED" for state in self._states.values()):
            raise CustodyError("previous capture custody not released; explicit recovery required")
        if family_id in self._families:
            facts = self._families[family_id]
            if facts.get("storage_extension") != self._family_scope_fields().get("storage_extension"):
                raise CustodyError("family storage scope extension differs")
            st = self.working.stat(follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != (facts["device"], facts["inode"]):
                raise CustodyError("existing family identity differs")
        else:
            self._before_write(os.statvfs(self.root).f_frsize)
            self.working.mkdir(mode=0o700)  # exclusive, never adopts orphan paths
            _sync_dir(self.working)
            _sync_dir(self.working.parent)
            st = self.working.stat(follow_symlinks=False)
            self.append("FAMILY", None, dict(family_id=family_id, working_relative_path="working/"+family_id,
                        device=st.st_dev, inode=st.st_ino, **self._family_scope_fields()))
        self._family_identity = (st.st_dev, st.st_ino)
        return self.working

    def _read_bound(self, path: Path, binding: archive.PhysicalBinding | None, maximum: int) -> bytes:
        with archive.open_regular(path) as stream:
            before = archive.file_stamp(os.fstat(stream.fileno()))
            if before[2] > maximum:
                raise CustodyError("metadata byte bound")
            raw = stream.read(maximum + 1)
            if len(raw) > maximum or before[2] != len(raw):
                raise CustodyError("metadata read length")
            if binding is not None and archive.PhysicalBinding(len(raw), hashlib.sha256(raw).hexdigest()) != binding:
                raise CustodyError("metadata binding differs")
            if (before != archive.file_stamp(os.fstat(stream.fileno()))
                    or before != archive.file_stamp(path.stat(follow_symlinks=False))):
                raise CustodyError("metadata changed during read")
        return raw

    def _replay(self):
        self._sequence, self._previous, self._states = 0, None, {}
        self._retained_receipts = set()
        self._families = {}
        self._capture_pending = set()
        self._record_bindings = []
        names = []
        for path in (self.root / "ledger").iterdir():
            if len(names) >= self.limits.max_ledger_records:
                raise CustodyError("ledger record limit")
            names.append(path)
        names.sort()
        for path in names:
            if path.name != f"{self._sequence:016d}.json":
                raise CustodyError("ledger incomplete/unexpected object; explicit recovery required")
            raw = self._read_bound(path, None, self.limits.max_record_bytes)
            record = archive.parse_json(raw)
            archive.uint(record.get("sequence"),"ledger sequence")
            archive.uint(record.get("timestamp_unix_ns"),"ledger timestamp",positive=True)
            if (set(record) != {"schema_version", "scope_sha256", "sequence", "previous_sha256", "kind", "artifact_id", "payload", "timestamp_unix_ns"}
                    or record["schema_version"] != LEDGER_SCHEMA or record["scope_sha256"] != self.scope_sha256
                    or record["sequence"] != self._sequence or record["previous_sha256"] != self._previous):
                raise CustodyError("ledger chain differs")
            self._apply(record)
            self._sequence += 1
            self._previous = hashlib.sha256(raw).hexdigest()
            self._record_bindings.append(BoundFile(path.name,len(raw),self._previous))

    def _validate_transition(self, record):
        kind, artifact = record["kind"], record["artifact_id"]
        allowed = {"FAMILY", "CHECKPOINT", "SOURCE_BOUND", "RESERVED", "VERIFIED", "PUBLISHED", "RELEASE_INTENT", "RELEASED", "CODEC_RESULT", "CUSTODY_RECEIPT", "FAILURE", "RECOVERY"}
        if kind not in allowed:
            raise CustodyError("unknown ledger transition")
        if kind == "FAMILY":
            family_id = archive.sha(record["payload"]["family_id"], "ledger family ID")
            if family_id in self._families or record["payload"]["working_relative_path"] != "working/"+family_id:
                raise CustodyError("duplicate/unsafe family ledger binding")
        if kind == "CUSTODY_RECEIPT" and (record["payload"]["family_id"],record["payload"]["checkpoint_sha256"]) not in self._capture_pending:
            raise CustodyError("custody receipt lacks pending checkpoint")
        if kind not in ("FAMILY", "CHECKPOINT", "CODEC_RESULT", "CUSTODY_RECEIPT", "FAILURE", "RECOVERY"):
            _name(artifact)
            previous = self._states.get(artifact)
            previous_kind = previous["kind"] if previous is not None else None
            required = {"SOURCE_BOUND": None, "RESERVED": "SOURCE_BOUND", "VERIFIED": "RESERVED",
                        "PUBLISHED": "VERIFIED", "RELEASE_INTENT": "PUBLISHED", "RELEASED": "RELEASE_INTENT"}
            if previous_kind != required[kind]:
                raise CustodyError("invalid ledger state transition")
    def _apply(self, record):
        self._validate_transition(record)
        if record["kind"] == "FAMILY":
            self._families[record["payload"]["family_id"]] = record["payload"]
        elif record["kind"] == "CHECKPOINT":
            family = archive.sha(record["payload"]["family_id"], "checkpoint family ID")
            self._retained_receipts.add((family, _name(record["payload"]["original_receipt"]["file_name"])))
            self._capture_pending.add((family,record["payload"]["original_receipt"]["sha256"]))
        elif record["kind"] == "CUSTODY_RECEIPT":
            family=archive.sha(record["payload"]["family_id"],"custody family ID")
            self._retained_receipts.add((family,_name(record["payload"]["receipt"]["file_name"])))
            pending=(family,record["payload"]["checkpoint_sha256"])
            if pending not in self._capture_pending:raise CustodyError("custody receipt lacks pending checkpoint")
            self._capture_pending.remove(pending)
        elif record["kind"] not in ("CODEC_RESULT", "FAILURE", "RECOVERY"):
            self._states[record["artifact_id"]] = record

    def physical_accounting(self) -> PhysicalUsage:
        self._check()
        total, logical, allocated, count, seen = 0, 0, 0, 0, set()

        def account(path, *, directory=False):
            nonlocal total, logical, allocated
            st = path.stat(follow_symlinks=False)
            if not (stat.S_ISDIR(st.st_mode) if directory else stat.S_ISREG(st.st_mode)):
                raise CustodyError("unexpected physical inventory object")
            identity = (st.st_dev, st.st_ino)
            if identity not in seen:
                seen.add(identity)
                disk = archive.checked_product(st.st_blocks, 512)
                logical = archive.checked_sum(logical, st.st_size)
                allocated = archive.checked_sum(allocated, disk)
                total = archive.checked_sum(total, max(st.st_size, disk))

        account(self.root, directory=True)
        for name in self.DIRECTORIES:
            account(self.root / name, directory=True)
        for path in (self.root / "working").iterdir():
            archive.sha(path.name, "working family namespace")
            account(path, directory=True)
            for child in path.iterdir():
                count+=1
                if count>self.limits.max_inventory_files:raise CustodyError("working inventory limit")
                if re.fullmatch(r"(?:formal-capture-[0-9]+-(?:final-checkpoint|archive-custody)|s180-e[0-9]+-(?:checkpoint|archive-custody))\.json",child.name):
                    account(child)
        for path in (self.root / "scope.json", self.root / "broker.lock"):
            account(path)
        for name in ("archives", "metadata", "ledger"):
            for path in (self.root / name).iterdir():
                count += 1
                if count > self.limits.max_inventory_files:
                    raise CustodyError("physical inventory limit")
                account(path)
        # Exact native receipts remain retained even though the publisher wrote
        # them to the working directory. They receive no raw-workspace exemption.
        for family, name in getattr(self, "_retained_receipts", set()):
            account(self.root / "working" / family / _name(name))
        return PhysicalUsage(logical, allocated, total, len(seen))

    def physical_usage(self) -> int:
        return self.physical_accounting().quota_bytes

    def reserved_bytes(self) -> int:
        reserved = 0
        for record in self._states.values():
            if record["kind"] in ("RESERVED", "VERIFIED"):
                payload = record["payload"]
                staging = self.root / "archives" / _name(payload["staging_name"])
                st = staging.stat(follow_symlinks=False) if staging.exists() else None
                actual = st.st_size if st is not None else 0
                maximum = payload["maximum_archive_bytes"]
                if actual > maximum:
                    raise CustodyError("staging exceeded reserved maximum")
                allocated = max(actual, st.st_blocks * 512) if st is not None else 0
                reserved = archive.checked_sum(reserved, max(0, payload["maximum_allocated_bytes"] - allocated))
        return reserved

    def _before_write(self, amount: int):
        self._check()
        amount = archive.uint(amount, "write amount")
        fs = os.statvfs(self.root)
        fragment = archive.uint(fs.f_frsize, "observed filesystem fragment size", positive=True)
        allocated = archive.checked_product((amount + fragment - 1) // fragment, fragment)
        if archive.checked_sum(self.physical_usage(), self.reserved_bytes(), allocated) > PROGRAM_QUOTA:
            raise CustodyError("write exceeds shared physical program quota")
        if fs.f_bavail * fs.f_frsize < archive.checked_sum(allocated, RESERVE) or fs.f_favail < 1:
            raise CustodyError("write would consume failure reserve or exhaust inodes")

    def append(self, kind: str, artifact_id: str | None, payload: dict):
        self._check()
        if self._sequence >= self.limits.max_ledger_records:
            raise CustodyError("ledger exhausted")
        record = dict(schema_version=LEDGER_SCHEMA, scope_sha256=self.scope_sha256,
            sequence=self._sequence, previous_sha256=self._previous, kind=kind,
            artifact_id=artifact_id, payload=payload, timestamp_unix_ns=time.time_ns())
        self._validate_transition(record)
        raw = archive.canonical(record)
        if len(raw) > self.limits.max_record_bytes:
            raise CustodyError("ledger record byte bound")
        self._before_write(len(raw))
        directory = self.root / "ledger"
        pending = directory / f"{self._sequence:016d}.pending"
        final = directory / f"{self._sequence:016d}.json"
        _write_new(pending, raw)
        os.link(pending, final, follow_symlinks=False)  # atomic, fails if final exists
        _sync_dir(directory)
        pending.unlink()
        _sync_dir(directory)
        if self._read_bound(final, archive.PhysicalBinding(len(raw), hashlib.sha256(raw).hexdigest()), len(raw)) != raw:
            raise CustodyError("ledger durable visibility differs")
        self._apply(record)
        self._previous, self._sequence = hashlib.sha256(raw).hexdigest(), self._sequence + 1
        binding=BoundFile(final.name,len(raw),self._previous)
        self._record_bindings.append(binding)
        return binding

    def _checkpoint_contract(self, document):
        if (document.get("schema_version") != CHECKPOINT_SCHEMA
                or document.get("plan_sha256") != self.family_id
                or document.get("scientific_validity") != "NOT_ASSESSED"
                or document.get("execution_authority") is not False):
            raise CustodyError("checkpoint cannot assert archive scientific validity or authority")
        return document.get("artifacts")

    def capture_archive_status(self, sources):
        return ("ARCHIVED_FAILED_EVIDENCE" if any(s.actual != s.expected.binding() for s in sources)
                else "ARCHIVED_AND_RELEASED")

    def capture_archive_receipt(self, checkpoint, artifacts, status):
        ordinal = self._checkpoint[2]["capture_ordinal"]
        document = dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1",
            program_scope_sha256=self.scope_sha256, plan_sha256=self.family_id, capture_ordinal=ordinal,
            checkpoint=asdict(checkpoint), ledger_tip=asdict(self.ledger_binding()), artifacts=artifacts,
            status=status, scientific_validity="NOT_ASSESSED", execution_authority=False)
        return f"formal-capture-{ordinal}-archive-custody.json", document

    def begin_capture(self, checkpoint: BoundFile, sources: tuple[SourceBinding, ...], *,
                      verify_checkpoint: Callable[[dict, tuple[SourceBinding, ...]], None]):
        """Required callback validates original cleanup fields AND current quiescence.

        It must raise on any failure; a boolean return is rejected. The exact
        checkpoint bytes and expected/actual source hashes are retained separately.
        """
        self._check()
        if self._capture_pending or any(state["kind"] != "RELEASED" for state in self._states.values()):
            raise CustodyError("previous capture custody not released; explicit recovery required")
        if self._family_identity is None:
            raise CustodyError("prepare_family is required before checkpoint")
        if not callable(verify_checkpoint):
            raise CustodyError("qualified checkpoint verifier is mandatory")
        raw = self._read_bound(self.working / _name(checkpoint.file_name),
                               checkpoint.binding(), self.limits.max_checkpoint_bytes)
        document = archive.parse_json(raw)
        references = self._checkpoint_contract(document)
        if not isinstance(references, list) or archive.canonical(references) != archive.canonical([asdict(s.expected) for s in sources]):
            raise CustodyError("checkpoint does not bind every original source in exact order")
        if len({s.artifact_id for s in sources}) != len(sources) or len({s.expected.file_name for s in sources}) != len(sources):
            raise CustodyError("duplicate source identity")
        for source in sources:
            _name(source.artifact_id)
            if source.artifact_id != self.family_id + ":" + source.expected.file_name:
                raise CustodyError("source artifact ID is not family-bound")
            source.expected.binding()
            source.actual.validate()
            if source.artifact_id in self._states:
                raise CustodyError("source artifact identity already present")
            path = self.working / source.expected.file_name
            actual = archive.hash_file(path, max_bytes=source.actual.size_bytes, deadline_ns=self.limits.deadline_ns)
            if actual != source.actual:
                raise CustodyError("actual source bytes differ")
            if source.actual != source.expected.binding() and source.failure_receipt is None:
                raise CustodyError("source discrepancy requires explicit retained failure binding")
            if source.failure_receipt is not None:
                failure = source.failure_receipt
                self._read_bound(self.root / "metadata" / _name(failure.file_name), failure.binding(), self.limits.max_checkpoint_bytes)
            with archive.open_regular(path) as stream:
                os.fsync(stream.fileno())
        if verify_checkpoint(document, sources) is not None:
            raise CustodyError("checkpoint callback must raise on failure, not return a boolean")
        with archive.open_regular(self.working / checkpoint.file_name) as stream:
            os.fsync(stream.fileno())
        _sync_dir(self.working)
        # Metadata receipt is an exact copy; producer-native original stays untouched.
        retained_name = "checkpoint-" + checkpoint.sha256 + ".json"
        self._retained_receipts.add((self.family_id, checkpoint.file_name))
        self._before_write(len(raw))
        _write_new(self.root / "metadata" / retained_name, raw)
        self.append("CHECKPOINT", None, dict(family_id=self.family_id, original_receipt=asdict(checkpoint), retained_receipt=retained_name,
                    sources=[asdict(s) for s in sources]))
        for source in sources:
            self.append("SOURCE_BOUND", source.artifact_id, dict(source=asdict(source), checkpoint_sha256=checkpoint.sha256))
        self._checkpoint = (checkpoint, retained_name, document)
        self._sources = {s.artifact_id: s for s in sources}
        self._verify_checkpoint = verify_checkpoint

    def _quiescent(self):
        self._check()
        if self._checkpoint is None or self._verify_checkpoint is None:
            raise CustodyError("no authenticated live checkpoint context")
        checkpoint, retained_name, _ = self._checkpoint
        raw = self._read_bound(self.root / "metadata" / retained_name, checkpoint.binding(), self.limits.max_checkpoint_bytes)
        if self._verify_checkpoint(archive.parse_json(raw), tuple(self._sources.values())) is not None:
            raise CustodyError("checkpoint callback returned an unsourced boolean")

    def reserve_archive(self, artifact_id: str, *, staging_name: str, maximum_archive_bytes: int) -> Path:
        """Reserve worst case before opening native encoder output. Native enforces
        the same output ceiling before each write; this reservation survives exit.
        """
        self._quiescent()
        _name(staging_name)
        archive.uint(maximum_archive_bytes, "archive reservation", positive=True)
        state = self._states.get(artifact_id)
        if state is None or state["kind"] != "SOURCE_BOUND" or artifact_id not in self._sources:
            raise CustodyError("archive source is not newly bound")
        path = self.root / "archives" / staging_name
        if path.exists() or path.is_symlink():
            raise CustodyError("archive staging already exists")
        self._before_write(maximum_archive_bytes)
        fragment = archive.uint(os.statvfs(self.root).f_frsize, "observed filesystem fragment size", positive=True)
        allocated = archive.checked_product((maximum_archive_bytes + fragment - 1) // fragment, fragment)
        self.append("RESERVED", artifact_id, dict(source=asdict(self._sources[artifact_id]),
                    staging_name=staging_name, maximum_archive_bytes=maximum_archive_bytes,
                    maximum_allocated_bytes=allocated))
        # Caller creates this exact object O_EXCL and passes only that fd to the
        # bounded encoder. It must not start another capture until acknowledgement.
        return path

    def verify_and_publish(self, artifact_id: str, *, archive_name: str, expected_header: dict,
                           role: archive.RoleProfile, physical: archive.PhysicalBinding,
                           profile: archive.DecoderProfile, limits: archive.DecodeLimits,
                           readback: Callable = archive.verify_archive) -> archive.VerifiedArchive:
        self._quiescent()
        state = self._states.get(artifact_id)
        if state is None or state["kind"] != "RESERVED":
            raise CustodyError("archive reservation absent or already used")
        payload = state["payload"]
        source = self._sources[artifact_id]
        if (expected_header["artifact_id"] != artifact_id
                or expected_header["canonical_size_bytes"] != source.actual.size_bytes
                or expected_header["canonical_sha256"] != source.actual.sha256
                or physical.size_bytes > payload["maximum_archive_bytes"]):
            raise CustodyError("archive differs from actual bound source/reservation")
        staging = self.root / "archives" / payload["staging_name"]
        destination = self.root / "archives" / _name(archive_name)
        if destination == staging:
            raise CustodyError("published archive must have a new identity")
        with archive.open_regular(staging) as stream:
            if os.fstat(stream.fileno()).st_nlink != 1:
                raise CustodyError("staging has unexpected hardlink")
            os.fsync(stream.fileno())
        _sync_dir(staging.parent)
        proof = checked_readback(readback, staging, expected_header=expected_header, role=role,
                                 physical=physical, profile=profile, limits=limits)
        self.append("VERIFIED", artifact_id, dict(payload, physical=asdict(physical), header=expected_header,
                    canonical=asdict(proof.canonical), verified_at_unix_ns=proof.verified_at_unix_ns))
        self._quiescent()
        # A changed staging pathname cannot be published on an earlier proof.
        if archive.file_stamp(staging.stat(follow_symlinks=False)) != proof.file_identity:
            raise CustodyError("verified staging identity changed")
        os.link(staging, destination, follow_symlinks=False)
        _sync_dir(destination.parent)
        # Link publication changes ctime/nlink. Rehash its exact bytes before
        # recording publication; retain both names if any later transition fails.
        if archive.hash_file(destination, max_bytes=physical.size_bytes, deadline_ns=limits.deadline_ns) != physical:
            raise CustodyError("published archive readback differs")
        staging.unlink()
        _sync_dir(staging.parent)
        self.append("PUBLISHED", artifact_id, dict(source=asdict(source), archive_name=archive_name,
                    physical=asdict(physical), header=expected_header, role=asdict(role),
                    checkpoint_sha256=self._checkpoint[0].sha256, verified_at_unix_ns=proof.verified_at_unix_ns,
                    storage_domain_id=self.scope["storage_domain_id"]))
        return proof

    def release_working_copy(self, artifact_id: str, *, profile: archive.DecoderProfile,
                             limits: archive.DecodeLimits, readback: Callable = archive.verify_archive):
        """Never releases failed/unverified storage. Scientific validity is irrelevant.

        Durable intent precedes quarantine-move/unlink. A crash can leave an extra
        working/hold name; it never removes the verified published representation.
        No automatic recovery or repeated release is attempted.
        """
        self._quiescent()
        # Authenticate the exact indexed durable publication record. Replaying
        # the entire program per artifact would make archival quadratic.
        record = self._states.get(artifact_id)
        if record is None or record["kind"] != "PUBLISHED" or artifact_id not in self._sources:
            raise CustodyError("durable verified publication required before release")
        self.ledger_binding(record)
        value = record["payload"]
        source = self._sources[artifact_id]
        if archive.canonical(value["source"]) != archive.canonical(asdict(source)):
            raise CustodyError("publication/source binding differs")
        destination = self.root / "archives" / _name(value["archive_name"])
        checked_readback(readback, destination, expected_header=value["header"], role=archive.RoleProfile(**value["role"]),
            physical=archive.PhysicalBinding(**value["physical"]), profile=profile, limits=limits)
        original = self.working / source.expected.file_name
        with archive.open_regular(original) as stream:
            before = archive.file_stamp(os.fstat(stream.fileno()))
            if before[-1] != 1:
                raise CustodyError("working source has unexpected hardlinks")
        if archive.hash_file(original, max_bytes=source.actual.size_bytes, deadline_ns=limits.deadline_ns) != source.actual:
            raise CustodyError("working source changed before release")
        if archive.file_stamp(original.stat(follow_symlinks=False)) != before:
            raise CustodyError("working source identity changed")
        hold_name = hashlib.sha256(artifact_id.encode()).hexdigest() + ".held"
        hold = self.root / "release-hold" / hold_name
        self.append("RELEASE_INTENT", artifact_id, dict(value, hold_name=hold_name, source_identity=list(before)))
        self._quiescent()
        if archive.file_stamp(original.stat(follow_symlinks=False)) != before:
            raise CustodyError("working source changed after intent")
        _move_no_replace(original, hold)
        _sync_dir(hold.parent)
        _sync_dir(original.parent)
        # Check the moved object's identity and bytes before its deletion. A race
        # can only leave a retained object in hold; it cannot delete a replacement.
        if (hold.stat(follow_symlinks=False).st_ino != before[1]
                or archive.hash_file(hold, max_bytes=source.actual.size_bytes, deadline_ns=limits.deadline_ns) != source.actual
                or hold.stat(follow_symlinks=False).st_nlink != 1):
            raise CustodyError("release moved identity differs")
        hold.unlink()
        _sync_dir(hold.parent)
        self.append("RELEASED", artifact_id, dict(value, released_at_unix_ns=time.time_ns()))

    def record_failure(self, artifact_id: str | None, *, operation: str, detail: str, evidence: dict | None = None):
        self.append("FAILURE", artifact_id, dict(operation=operation, detail=detail,evidence=evidence))

    def retain_metadata(self, file_name: str, raw: bytes) -> BoundFile:
        """Retain exact small result/authority bytes, charged to the shared quota."""
        self._before_write(len(raw))
        path=self.root/"metadata"/_name(file_name)
        _write_new(path,raw)
        binding=BoundFile(file_name,len(raw),hashlib.sha256(raw).hexdigest())
        self._read_bound(path,binding.binding(),len(raw))
        return binding

    def ledger_binding(self, record: dict | None = None) -> BoundFile:
        self._check()
        sequence=self._sequence-1 if record is None else record["sequence"]
        if type(sequence) is not int or not 0<=sequence<self._sequence:
            raise CustodyError("ledger reference sequence")
        binding=self._record_bindings[sequence]
        actual=self.read_verified_record(binding)
        if record is not None and archive.canonical(actual)!=archive.canonical(record):
            raise CustodyError("ledger reference snapshot changed")
        if record is None and binding.sha256!=self._previous:
            raise CustodyError("ledger tip hash changed")
        return binding

    def read_verified_record(self, binding: BoundFile) -> dict:
        """Bounded exact read against the replay/append index, including old records."""
        self._check()
        if re.fullmatch(r"[0-9]{16}\.json",binding.file_name) is None:
            raise CustodyError("ledger record filename")
        sequence=int(binding.file_name[:-5])
        if sequence>=len(self._record_bindings) or binding!=self._record_bindings[sequence]:
            raise CustodyError("ledger record differs from authenticated index")
        raw=self._read_bound(self.root/"ledger"/binding.file_name,binding.binding(),self.limits.max_record_bytes)
        return archive.parse_json(raw)

    def _custody_filename(self, name):
        return re.fullmatch(r"formal-capture-[0-9]+-archive-custody\.json", name) is not None

    def _custody_contract(self, document):
        expected_status=("ARCHIVED_FAILED_EVIDENCE" if any(s.actual!=s.expected.binding() for s in self._sources.values())
                         else "ARCHIVED_AND_RELEASED")
        if (document.get("program_scope_sha256")!=self.scope_sha256 or document.get("plan_sha256")!=self.family_id
                or document.get("checkpoint")!=asdict(self._checkpoint[0])
                or document.get("schema_version")!="cpu-prefetch-stage17-formal-archive-custody/1"
                or document.get("scientific_validity")!="NOT_ASSESSED" or document.get("execution_authority") is not False
                or document.get("capture_ordinal")!=self._checkpoint[2]["capture_ordinal"]
                or document.get("status")!=expected_status):
            raise CustodyError("custody receipt checkpoint/program binding differs")

    def retain_custody_receipt(self, file_name: str, raw: bytes) -> BoundFile:
        self._quiescent()
        if not self._custody_filename(file_name):
            raise CustodyError("custody receipt filename")
        if any(self._states[s]["kind"]!="RELEASED" for s in self._sources):
            raise CustodyError("all source releases required before custody receipt")
        document=archive.parse_json(raw)
        self._custody_contract(document)
        self._before_write(len(raw))
        binding=BoundFile(file_name,len(raw),hashlib.sha256(raw).hexdigest())
        _write_new(self.working/file_name,raw)
        self._retained_receipts.add((self.family_id,file_name))
        self._read_bound(self.working/file_name,binding.binding(),len(raw))
        self.append("CUSTODY_RECEIPT",None,dict(family_id=self.family_id,receipt=asdict(binding),
                                             checkpoint_sha256=self._checkpoint[0].sha256))
        return binding

    def recovery_inventory(self) -> dict:
        """Read-only evidence, never a retry/delete permission or automatic repair."""
        self._check()
        return dict(execution_authority=False, automatic_recovery=False,
            ledger_objects=sorted(p.name for p in (self.root / "ledger").iterdir()),
            archive_objects=sorted(p.name for p in (self.root / "archives").iterdir()),
            held_sources=sorted(p.name for p in (self.root / "release-hold").iterdir()))


def checked_readback(readback: Callable, path: Path, **kwargs) -> archive.VerifiedArchive:
    """Qualified runtime seam, not an API accepting a precomputed proof or bool.

    The subprocess implementation authenticates pinned exec/sealed input, actual
    reap/cleanup and bounded sealed result before it returns VerifiedArchive.
    In-process default calls the independent decoder under its enforced AS limit.
    """
    result = readback(path, **kwargs)
    header = kwargs["expected_header"]
    if (type(result) is not archive.VerifiedArchive
            or result.physical != kwargs["physical"]
            or result.canonical != archive.PhysicalBinding(header["canonical_size_bytes"], header["canonical_sha256"])
            or result.header_sha256 != hashlib.sha256(archive.canonical(header)).hexdigest()
            or result.block_count != header["block_count"]
            or result.file_identity != archive.file_stamp(path.stat(follow_symlinks=False))):
        raise CustodyError("qualified readback result does not match actual artifact/bindings")
    return result


@dataclass(frozen=True)
class SpoolArtifact:
    file_name: str
    archive_path: Path
    expected_header: dict
    role: archive.RoleProfile
    physical: archive.PhysicalBinding


@contextlib.contextmanager
def capture_spool(directory: Path, *, capture_id: str, canonical_bytes_bound: int,
                  deadline_ns: int, artifacts: tuple[SpoolArtifact, ...],
                  profile: archive.DecoderProfile, limits: archive.DecodeLimits) -> Iterator[Path]:
    """One exclusive capture spool per process, provisional until resolver succeeds.

    The caller's admitted analysis plan reserves aggregate scratch across processes;
    every artifact uses verify_archive(..., sink=...) and fails on any bad byte.
    Failed spool contents remain for diagnosis. Success cleanup removes only the
    newly created disposable canonical representations, never the archives.
    """
    _name(capture_id)
    archive.uint(canonical_bytes_bound, "spool bound")
    archive.uint(deadline_ns, "spool deadline", positive=True)
    if canonical_bytes_bound > SCRATCH:
        raise CustodyError("spool exceeds S")
    planned = 0
    names = set()
    for artifact in artifacts:
        _name(artifact.file_name)
        if artifact.file_name in names or artifact.file_name == "reservation.json":
            raise CustodyError("duplicate/reserved spool name")
        names.add(artifact.file_name)
        planned = archive.checked_sum(planned, artifact.expected_header["canonical_size_bytes"])
    if planned > canonical_bytes_bound:
        raise CustodyError("prospective decoded spool exceeds bound")
    limits = replace(limits, deadline_ns=min(deadline_ns, limits.deadline_ns))
    limits.validate()
    directory = Path(directory).absolute()
    if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
        raise CustodyError("symlink spool root")
    lock = directory / f"process-{os.getpid()}.lock"
    lock_fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        root = directory / f"{os.getpid()}-{capture_id}"
        root.mkdir(mode=0o700)
        # Prospective reservation is durable before decode writes. Parallel caller
        # must account it, not just the bytes currently visible in partial files.
        reservation = archive.canonical(dict(capture_id=capture_id, pid=os.getpid(),
            maximum_canonical_bytes=canonical_bytes_bound, deadline_monotonic_ns=deadline_ns))
        _write_new(root / "reservation.json", reservation)
        if time.monotonic_ns() >= deadline_ns:
            raise CustodyError("spool deadline expired")
        remaining = canonical_bytes_bound
        class Sink:
            def __init__(self, stream):
                self.stream = stream

            def write(self, data):
                nonlocal remaining
                limits.check_time()
                if len(data) > remaining:
                    raise CustodyError("decoded write exceeds spool reservation")
                fs = os.statvfs(directory)
                if fs.f_bavail * fs.f_frsize < archive.checked_sum(len(data), RESERVE):
                    raise CustodyError("decoded write would consume failure reserve")
                count = self.stream.write(data)
                if count != len(data):
                    raise CustodyError("partial spool write")
                remaining -= count
                return count
        for artifact in artifacts:
            target = root / artifact.file_name
            with target.open("xb", buffering=0) as stream:
                archive.verify_archive(artifact.archive_path, expected_header=artifact.expected_header,
                    role=artifact.role, physical=artifact.physical, profile=profile, limits=limits, sink=Sink(stream))
                os.fsync(stream.fileno())
        _sync_dir(root)
        total = 0
        identities = {}
        for path in root.iterdir():
            st = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise CustodyError("unexpected spool object")
            identities[path] = archive.file_stamp(st)
            if path.name != "reservation.json":
                total = archive.checked_sum(total, st.st_size)
        if total > canonical_bytes_bound or time.monotonic_ns() >= deadline_ns:
            raise CustodyError("spool size/deadline bound exceeded")
        yield root
        for path, identity in identities.items():
            if archive.file_stamp(path.stat(follow_symlinks=False)) != identity:
                raise CustodyError("analysis mutated canonical spool")
        if set(root.iterdir()) != set(identities):
            raise CustodyError("analysis added unexpected spool objects")
        for path in identities:
            path.unlink()
        root.rmdir()
        _sync_dir(directory)
    finally:
        os.close(lock_fd)
