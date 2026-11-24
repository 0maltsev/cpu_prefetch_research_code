"""Bounded, signed S180 EXT008-010 journal anchored in authenticated EXT001-007.

The qualified caller supplies an authenticated base replay and a pinned semantic
replay function. The latter MUST independently verify the plan/source/platform/
qualification/resource evidence; signatures/hashes do not replace those checks.
No verifier, command, key or backend is selectable through journal input data.
This module grants no execution, generic readiness or Stage18 authority.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import time

import stage17_formal_archive_v1 as archive
import stage17_s180_signature_v1 as signatures
import stage17_q16a_continuation_admission_v1 as readers
import stage17_s180_authority_v1 as authority
from stage17_s180_checkpoint_v1 import BLUEPRINT_SHA256, APPROVAL_SHA256

SCOPE = "D310-S180-SCOPED-INPUT-JOURNAL-v1"
JOURNAL_SCHEMA = "cpu-prefetch-stage17-s180-input-journal/1"
RECORD_SCHEMA = "cpu-prefetch-stage17-s180-input-resolution/1"
RECORD_FIELDS = frozenset(("schema_version input_id resolution_id anchor_sha256 "
    "previous_scoped_record_sha256 recorded_at_unix_ns payload semantic_context_sha256 "
    "synthetic_test_only execution_authority phase18_authority").split())
JOURNAL_FIELDS = frozenset(("schema_version scope_id plan_sha256 blueprint_sha256 approval_sha256 "
    "base_journal_sha256 base_resolutions semantic_policy_sha256 synthetic_test_only "
    "generation previous_journal_sha256 records execution_authority phase18_authority").split())
LIMIT = 16 * 1024**2
MAX_READ_BYTES = 256 * 1024**2
METADATA_NS = 120_000_000_000
CALIBRATION_SCOPE = "STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY"


class JournalError(archive.ArchiveError):
    pass


def require(value, message):
    if not value:
        raise JournalError("S180 journal: " + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class Resolution:
    input_id: str
    resolution_id: str
    sha256: str
    semantic_context: dict


@dataclass(frozen=True)
class JournalView:
    _resolutions: dict
    journal_sha256: str
    generation: int
    synthetic_test_only: bool
    pilot_ready: bool = False
    execution_authority: bool = False
    phase18_authority: bool = False

    @property
    def resolutions(self):
        return copy.deepcopy(self._resolutions)

    @property
    def scoped_inputs_complete(self):
        # Completeness is not permission to construct a native launch context.
        return self.generation == 3


class ScopedJournal:
    """Library boundary for the qualified S180 parent; no standalone launch CLI.

    semantic_replay(input_id, payload, preceding_view, *, for_execution) must
    return the independently derived D319 context or raise. It is qualified code,
    never an input-provided plugin. Current production fact producers and parent
    wiring remain mandatory; tests supply an explicitly synthetic replay.
    """
    def __init__(self, root, *, base_validation, plan, semantic_policy_sha256,
                 semantic_replay, synthetic_test_only=False):
        self.root = Path(root)
        require(self.root.is_absolute() and ".." not in self.root.parts,
                "absolute canonical journal root required")
        require(callable(semantic_replay), "independent qualified semantic replay required")
        require(type(synthetic_test_only) is bool, "explicit journal classification required")
        raw = archive.canonical(plan)
        require(0 < len(raw) <= LIMIT, "plan byte bound")
        self.plan = archive.parse_json(raw)
        require(self.plan.get("schema_version") == "cpu-prefetch-stage17-s180-session-plan/1"
                and sha(archive.canonical(self.plan["blueprint"])) == BLUEPRINT_SHA256,
                "exact frozen S180 plan required")
        self.base = copy.deepcopy(base_validation.resolutions)
        require(set(self.base) == {f"S17-EXT-{i:03d}" for i in range(1, 8)},
                "exactly the original seven admitted inputs are required")
        for key, value in self.base.items():
            require(value.input_id == key, "base input identity differs")
            archive.sha(value.sha256, key)
        previous = self.base["S17-EXT-007"]
        require(previous.sha256 == self.plan["blueprint"]["ext007_resolution"]["sha256"]
                and previous.semantic_context.get("calibration_scope") == CALIBRATION_SCOPE
                and previous.semantic_context.get("data_provenance_accepted") is True
                and previous.semantic_context.get("legacy_statistical_freeze_satisfied") is False,
                "original descriptive EXT007 lineage required")
        self.trust = copy.deepcopy(self.base["S17-EXT-003"].semantic_context["trust"])
        self.semantic_replay = semantic_replay
        self.mode = synthetic_test_only
        self._fd = self._lock = None
        self._identity = None
        self._deadline_ns = time.monotonic_ns()+METADATA_NS
        self._read_bytes = 0
        self._observed = {}
        self.anchor = dict(schema_version=JOURNAL_SCHEMA, scope_id=SCOPE,
            plan_sha256=sha(raw), blueprint_sha256=BLUEPRINT_SHA256,
            approval_sha256=APPROVAL_SHA256,
            base_journal_sha256=archive.sha(base_validation.latest_journal_sha256, "base journal"),
            base_resolutions=[authority.binding(self.base[f"S17-EXT-{i:03d}"]) for i in range(1, 8)],
            semantic_policy_sha256=archive.sha(semantic_policy_sha256, "semantic policy"),
            synthetic_test_only=self.mode, generation=0, previous_journal_sha256=None,
            records=[], execution_authority=False, phase18_authority=False)
        self.anchor_sha256 = sha(archive.canonical(self.anchor))

    def initialize(self):
        """Create a fresh metadata journal; existing/orphan roots are not adopted."""
        require(self._fd is None, "journal already open")
        require(self.root.parent.resolve(strict=True) == self.root.parent,
                "symlink journal parent")
        self.root.mkdir(mode=0o700)
        self._fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            self._identity = self._root_identity()
            self._write_new("journal.lock", b"")
            self._write_new("journal-0.json", archive.canonical(self.anchor))
            parent = os.open(self.root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        finally:
            os.close(self._fd)
            self._fd = None

    def _root_identity(self):
        observed = os.fstat(self._fd)
        require(stat.S_ISDIR(observed.st_mode) and observed.st_uid == os.geteuid()
                and not observed.st_mode & 0o022, "unsafe journal root")
        return observed.st_dev, observed.st_ino

    def _check(self):
        require(time.monotonic_ns() < self._deadline_ns, "metadata deadline expired")
        require(self._fd is not None and self.root.resolve(strict=True) == self.root,
                "journal root unavailable or symlinked")
        observed = self.root.stat(follow_symlinks=False)
        require(self._root_identity() == self._identity == (observed.st_dev, observed.st_ino),
                "held journal root changed")
        if self._lock is not None:
            held = os.fstat(self._lock)
            named = os.stat("journal.lock", dir_fd=self._fd, follow_symlinks=False)
            require(stat.S_ISREG(named.st_mode) and named.st_uid == os.geteuid()
                    and not named.st_mode & 0o022 and named.st_size == 0
                    and (held.st_dev, held.st_ino) == (named.st_dev, named.st_ino),
                    "held journal lock changed")

    def __enter__(self):
        require(self._fd is None and self.root.resolve(strict=True) == self.root,
                "journal is open or root is symlinked")
        self._fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            self._identity = self._root_identity()
            self._lock = os.open("journal.lock", os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self._fd)
            st = os.fstat(self._lock)
            require(stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid()
                    and st.st_size == 0 and not st.st_mode & 0o022, "unsafe journal lock")
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.inspect()
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if self._lock is not None:
            os.close(self._lock)
        if self._fd is not None:
            os.close(self._fd)
        self._lock = self._fd = None

    def _read(self, name, maximum=LIMIT):
        self._check()
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self._fd)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_uid == os.geteuid()
                    and not before.st_mode & 0o022 and 0 < before.st_size <= maximum,
                    "journal object is not an owned bounded regular file")
            self._read_bytes += before.st_size
            require(self._read_bytes <= MAX_READ_BYTES, "aggregate metadata read bound")
            raw = os.pread(fd, before.st_size+1, 0)
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
            require(len(raw) == before.st_size and stamp(before) == stamp(os.fstat(fd))
                    == stamp(os.stat(name, dir_fd=self._fd, follow_symlinks=False)), "journal object changed")
            first = self._observed.setdefault(name, stamp(before))
            require(first == stamp(before), "journal object changed between references")
            return raw
        finally:
            os.close(fd)

    def _write_new(self, name, raw):
        # Never removes a partial write: an orphan makes subsequent replay fail.
        self._check()
        require(len(raw) <= LIMIT, "journal publication byte bound")
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600, dir_fd=self._fd)
        try:
            require(os.write(fd, raw) == len(raw), "partial journal publication")
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(self._fd)
        self._check()

    def _view(self, resolutions, generation, journal_sha256):
        return JournalView(copy.deepcopy(resolutions), journal_sha256, generation, self.mode)

    def _finish_snapshot(self, expected):
        require(set(os.listdir(self._fd)) == expected, "journal inventory changed during replay")
        for name, first in self._observed.items():
            st = os.stat(name, dir_fd=self._fd, follow_symlinks=False)
            require(first == (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns),
                    "journal object changed before replay completed")
        self._check()

    def _shape(self, input_id, context, resolutions):
        context = archive.parse_json(archive.canonical(context))
        common = {"scope_id", "plan_sha256", "window_binding", "evidence_root_binding", "phase18_authority"}
        if input_id == "S17-EXT-008":
            authority.fields(context, common | {"runtime_binding", "release_binding", "qualification_sha256",
                "compatibility_sha256", "runtime_profile_sha256"}, "scoped plan context")
            require(context["scope_id"] == authority.PLAN_SCOPE, "scoped plan context required")
            for name in ("qualification_sha256", "compatibility_sha256", "runtime_profile_sha256"):
                archive.sha(context[name], name)
            runtime, release = context["runtime_binding"], context["release_binding"]
            authority.fields(runtime, {"role", "profile", "sha256", "size_bytes"}, "scoped runtime")
            authority.fields(release, {"source_revision", "worker_sha256"}, "scoped release")
            require(runtime["role"] == authority.ROLE and runtime["profile"] == authority.PROFILE
                    and release["source_revision"] == self.plan["source_revision"]
                    and type(release["source_revision"]) is str
                    and re.fullmatch(r"[0-9a-f]{40}", release["source_revision"]) is not None
                    and archive.sha(runtime["sha256"], "runtime") == release["worker_sha256"],
                    "scoped qualified runtime/release differ")
            archive.uint(runtime["size_bytes"], "runtime size", positive=True)
        else:
            authority.fields(context, common | {"resource_admission_status"}, "scoped resource context")
            require(context["scope_id"] == authority.RESOURCE_SCOPE
                    and context["resource_admission_status"] == "ADMITTED", "scoped resource admission required")
            previous = resolutions["S17-EXT-008"].semantic_context
            for key in ("window_binding", "evidence_root_binding"):
                authority.same(context[key], previous[key], "plan/resource " + key)
        require(context["plan_sha256"] == self.anchor["plan_sha256"]
                and context["phase18_authority"] is False, "scoped plan identity/authority differs")
        window = context["window_binding"]
        authority.fields(window, {"boot_id", "start_monotonic_ns", "end_monotonic_ns"}, "original window")
        start = archive.uint(window["start_monotonic_ns"], "window start", positive=True)
        end = archive.uint(window["end_monotonic_ns"], "window end", positive=True)
        require(end > start and end-start == authority.DAY_NS, "original24h window differs")
        authority.opaque(window["boot_id"], "original boot")
        root = context["evidence_root_binding"]
        authority.fields(root, {"absolute_path", "device", "inode"}, "original output root")
        path = Path(root["absolute_path"])
        require(path.is_absolute() and ".." not in path.parts and path.name == self.anchor["plan_sha256"]
                and path.parent.name == "working" and str(path) == root["absolute_path"], "family path differs")
        archive.uint(root["device"], "root device")
        archive.uint(root["inode"], "root inode", positive=True)
        return context

    def _context(self, record, view, *, for_execution):
        self._check()
        if record["input_id"] != "S17-EXT-010":
            context = self.semantic_replay(record["input_id"], copy.deepcopy(record["payload"]),
                view, for_execution=for_execution)
            require(type(context) is dict, "semantic replay must derive a context, never a boolean")
            require(len(archive.canonical(context)) <= 1024**2, "semantic context exceeds bound")
            context = self._shape(record["input_id"], context, view.resolutions)
            if for_execution:
                window = context["window_binding"]
                require(window["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
                        and window["start_monotonic_ns"] <= time.monotonic_ns() < window["end_monotonic_ns"],
                        "original operational window/boot is not current")
        else:
            authority.fields(record["payload"], {"authorization", "signature"}, "EXT010 proof")
            reader = readers.BoundReader()
            raw = reader.read(record["payload"]["authorization"])
            reader.read(record["payload"]["signature"])
            args = dict(authorization_bytes=raw, signature_path=Path(record["payload"]["signature"]["path"]),
                plan=self.plan, validation=view)
            if for_execution:
                authority.verify_authorization(**args)
            else:
                authority.verify_historical_authorization(**args)
            reader.finish()
            context = dict(scope_id="D310-S180-FAMILY-AUTHORIZATION-v1", authorization_sha256=sha(raw),
                authorization=archive.parse_json(raw), phase18_authority=False)
        context_raw = archive.canonical(context)
        require(len(context_raw) <= 1024**2, "semantic context exceeds bound")
        self._check()
        return archive.parse_json(context_raw)

    def _record(self, raw, signature_path, view, previous, *, for_execution):
        record = archive.parse_json(raw)
        authority.fields(record, RECORD_FIELDS, "scoped input record")
        require(record["schema_version"] == RECORD_SCHEMA
                and record["input_id"] == f"S17-EXT-{8+view.generation:03d}"
                and record["anchor_sha256"] == self.anchor_sha256
                and record["previous_scoped_record_sha256"] == previous
                and record["synthetic_test_only"] is self.mode
                and record["execution_authority"] is False and record["phase18_authority"] is False,
                "scoped input order/anchor/classification differs")
        authority.opaque(record["resolution_id"], "resolution ID")
        require(type(record["payload"]) is dict, "input payload must be an object")
        timestamp = archive.uint(record["recorded_at_unix_ns"], "record time", positive=True)
        require(timestamp <= time.time_ns(), "future input record")
        signatures._verify_signature(raw, signature_path, self.trust)
        context = self._context(record, view, for_execution=for_execution)
        require(sha(archive.canonical(context)) == record["semantic_context_sha256"],
                "independently derived semantic context differs")
        return record, context

    def inspect(self, *, for_execution=False):
        """Replay signatures/semantics; historical inspection grants no live authority."""
        self._check()
        self._observed = {}
        names = set(os.listdir(self._fd))
        require(len(names) <= 11, "journal inventory bound/orphan publication")
        require(self._read("journal-0.json") == archive.canonical(self.anchor), "original anchor differs")
        resolutions, references = copy.deepcopy(self.base), []
        previous_record, previous_journal, last_time = None, self.anchor_sha256, 0
        expected = {"journal.lock", "journal-0.json"}
        generation = 0
        for ordinal in range(1, 4):
            name = f"journal-{ordinal}.json"
            if name not in names:
                break
            raw = self._read(name)
            journal = archive.parse_json(raw)
            authority.fields(journal, JOURNAL_FIELDS, "scoped journal")
            view = self._view(resolutions, generation, previous_journal)
            record_name, signature_name = f"record-{7+ordinal:03d}.json", f"record-{7+ordinal:03d}.sig"
            record_raw = self._read(record_name)
            signature_raw = self._read(signature_name, 65536)
            record, context = self._record(record_raw, self.root / signature_name, view, previous_record,
                for_execution=for_execution)
            require(record["recorded_at_unix_ns"] >= last_time, "input chronology regressed")
            last_time = record["recorded_at_unix_ns"]
            previous_record = sha(record_raw)
            references.append(dict(record=dict(file_name=record_name, size_bytes=len(record_raw), sha256=previous_record),
                signature=dict(file_name=signature_name, size_bytes=len(signature_raw), sha256=sha(signature_raw))))
            required = dict(self.anchor, generation=ordinal, previous_journal_sha256=previous_journal,
                records=references)
            require(raw == archive.canonical(required), "journal prefix/hash chain differs")
            resolutions[record["input_id"]] = Resolution(record["input_id"], record["resolution_id"],
                previous_record, context)
            previous_journal, generation = sha(raw), ordinal
            expected.update((name, record_name, signature_name))
        require(names == expected, "journal has a gap, fork, orphan or unexpected object")
        self._finish_snapshot(expected)
        return self._view(resolutions, generation, previous_journal)

    def prepare_record(self, *, input_id, resolution_id, payload):
        """Derive semantics before signing; creates no journal record or permission."""
        view = self.inspect(for_execution=True)
        require(view.generation < 3 and input_id == f"S17-EXT-{8+view.generation:03d}", "next input differs")
        authority.opaque(resolution_id, "resolution ID")
        require(type(payload) is dict, "input payload must be an object")
        payload_raw = archive.canonical(payload)
        require(len(payload_raw) <= LIMIT, "input payload exceeds bound")
        payload = archive.parse_json(payload_raw)
        previous = None if view.generation == 0 else view.resolutions[f"S17-EXT-{7+view.generation:03d}"].sha256
        record = dict(schema_version=RECORD_SCHEMA, input_id=input_id, resolution_id=resolution_id,
            anchor_sha256=self.anchor_sha256, previous_scoped_record_sha256=previous,
            recorded_at_unix_ns=time.time_ns(), payload=copy.deepcopy(payload), semantic_context_sha256="",
            synthetic_test_only=self.mode, execution_authority=False, phase18_authority=False)
        context = self._context(record, view, for_execution=True)
        record["semantic_context_sha256"] = sha(archive.canonical(context))
        raw = archive.canonical(record)
        require(len(raw) <= LIMIT, "scoped input record exceeds bound")
        return raw

    def append(self, *, record_binding, signature_binding):
        """Publish exact verified signed bytes once; partial objects block reentry."""
        view = self.inspect(for_execution=True)
        require(view.generation < 3, "one scoped family is already complete")
        reader = readers.BoundReader()
        raw, signature = reader.read(record_binding), reader.read(signature_binding)
        require(len(raw) <= LIMIT and 0 < len(signature) <= 65536, "record/signature size bound")
        # Check everything before the first immutable publication, using the
        # original external signature. No copy is treated as permission by itself.
        previous = None if view.generation == 0 else view.resolutions[f"S17-EXT-{7+view.generation:03d}"].sha256
        record, context = self._record(raw, Path(signature_binding["path"]), view, previous,
            for_execution=True)
        now = record["recorded_at_unix_ns"]
        if view.generation:
            old = archive.parse_json(self._read(f"record-{7+view.generation:03d}.json"))
            require(now >= old["recorded_at_unix_ns"], "input chronology regressed")
        reader.finish()
        ordinal = view.generation+1
        prior = archive.parse_json(self._read(f"journal-{view.generation}.json"))
        record_name, signature_name = f"record-{7+ordinal:03d}.json", f"record-{7+ordinal:03d}.sig"
        refs = [*prior["records"], dict(record=dict(file_name=record_name, size_bytes=len(raw), sha256=sha(raw)),
            signature=dict(file_name=signature_name, size_bytes=len(signature), sha256=sha(signature)))]
        journal = dict(self.anchor, generation=ordinal, previous_journal_sha256=view.journal_sha256, records=refs)
        expected = {"journal.lock", "journal-0.json"}
        for i in range(1, view.generation+1):
            expected.update((f"journal-{i}.json", f"record-{7+i:03d}.json", f"record-{7+i:03d}.sig"))
        self._finish_snapshot(expected)
        self._write_new(record_name, raw)
        self._write_new(signature_name, signature)
        self._write_new(f"journal-{ordinal}.json", archive.canonical(journal))
        return self.inspect(for_execution=True)


def from_authenticated_base(root, *, base_replay_arguments, plan,
                            semantic_policy_sha256, semantic_replay):
    """Qualified-parent adapter: actual UTC, policy65 replay, no synthetic selector.

    The parent still authenticates its semantic source closure. No policy/verifier
    name, caller time or allow-synthetic flag can be supplied through this data.
    """
    import stage17_state_journal_v62 as original
    authority.fields(base_replay_arguments, {"repository_root", "evidence_root", "latest_journal",
        "journal_directory", "pilot_archive", "pilot_sidecar"}, "original replay locators")
    base = original.validate_operational_journal(**base_replay_arguments,
        as_of_utc=signatures._now(), allow_synthetic_test_evidence=False)
    return ScopedJournal(root, base_validation=base, plan=plan,
        semantic_policy_sha256=semantic_policy_sha256, semantic_replay=semantic_replay,
        synthetic_test_only=False)
