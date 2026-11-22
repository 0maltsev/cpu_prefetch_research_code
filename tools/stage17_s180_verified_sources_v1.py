"""Owned verified/sealed S180 sources for the qualified parent.

Run original generation verification once before a short journal transaction.
Keep its proof and the exact sealed native inputs alive in the same process.
Serialized reports never construct this handle or supply execution authority.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import stat
import time

import stage17_formal_archive_v1 as archive
import stage17_s180_source_provenance_v1 as provenance

SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
CONTROL_RESERVE = 8
DAY_NS = 86_400_000_000_000
_TOKEN = object()


class SourcesError(archive.ArchiveError):
    pass


def require(value, message):
    if not value:
        raise SourcesError("S180 verified sources: " + message)


def _before(deadline):
    require(type(deadline) is int and time.monotonic_ns() < deadline, "source ownership deadline expired")


def _stamp(path):
    require(path.resolve(strict=True) == path, "source path became symlinked")
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and not st.st_mode & 0o022, "unsafe original source")
    return provenance._stamp(st)


def _originals(records):
    require(type(records) is list and len(records) == 36, "complete original source records required")
    observed = {}
    for record in records:
        provenance._fields(record, provenance.RECORD_FIELDS, "source record")
        for name in ("binary", "envelope", "derivation"):
            binding = record[name]
            provenance._fields(binding, provenance.FILE_FIELDS, name)
            require(type(binding["path"]) is str, "source locator must be text")
            path = Path(binding["path"])
            require(path.is_absolute() and str(path) == binding["path"] and path not in observed,
                    "absolute unique original path required")
            observed[path] = _stamp(path)
    return observed


def _check_originals(observed):
    for path, before in observed.items():
        require(_stamp(path) == before, "original source changed since generation verification")


def _fd_identity(fd):
    st = os.fstat(fd)
    return st.st_dev, st.st_ino, st.st_size


def _release(held):
    changed = []
    for fd, identity in reversed(tuple(held)):
        try:
            if _fd_identity(fd) == identity:
                os.close(fd)
            else:
                changed.append(fd)  # Never close an unrelated replacement FD.
        except OSError:
            changed.append(fd)
    require(not changed, "owned source descriptors were replaced or failed cleanup")


def _pin(binding, *, deadline):
    """Stream an exact already-verified binary into one sealed read-only memfd."""
    _before(deadline)
    path = Path(binding["path"])
    before = _stamp(path)
    source = writer = reader = None
    try:
        source = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        require(provenance._stamp(os.fstat(source)) == before and before[4] == binding["size_bytes"],
                "source changed before sealing")
        writer = os.memfd_create("stage17-s180-verified-source", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        digest, offset = hashlib.sha256(), 0
        while offset < binding["size_bytes"]:
            _before(deadline)
            block = os.pread(source, min(65536,binding["size_bytes"]-offset),offset)
            require(bool(block), "original truncated during sealing")
            digest.update(block)
            view = memoryview(block)
            while view:
                _before(deadline)
                written = os.write(writer,view)
                require(written > 0, "sealed source write made no progress")
                view = view[written:]
            offset += len(block)
        require(os.pread(source,1,offset) == b"" and digest.hexdigest() == binding["sha256"]
                and provenance._stamp(os.fstat(source)) == before == _stamp(path),
                "original bytes/identity changed while sealing")
        fcntl.fcntl(writer,fcntl.F_ADD_SEALS,SEALS)
        reader = os.open(f"/proc/self/fd/{writer}",os.O_RDONLY | os.O_CLOEXEC)
        _before(deadline)
        result, reader = reader, None
        return result
    finally:
        for fd in (reader,writer,source):
            if fd is not None:
                os.close(fd)


class _VerifiedSources:
    def __init__(self, *, token, report, bindings, originals, maximum_vector_bytes, valid_until_ns,
                 maximum_loading_ns):
        require(token is _TOKEN, "only actual verification constructs an owned source bank")
        self._report = archive.canonical(report)
        self._bindings = archive.canonical(bindings)
        self._originals = originals
        self._identity = {b["descriptor"]:_fd_identity(b["descriptor"]) for b in bindings}
        self._vector = maximum_vector_bytes
        self._until = valid_until_ns
        self._loading_limit = archive.uint(maximum_loading_ns,"native source setup budget",positive=True)
        self._pid = os.getpid()
        self._boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        self._closed = False

    def _check(self, plan_sha256):
        require(not self._closed and os.getpid() == self._pid, "source owner is closed or belongs to another process")
        require(Path("/proc/sys/kernel/random/boot_id").read_text().strip() == self._boot,
                "source owner belongs to another boot")
        _before(self._until)
        require(plan_sha256 == archive.parse_json(self._report)["plan_sha256"], "source owner plan differs")
        _check_originals(self._originals)
        for fd, identity in self._identity.items():
            require(_fd_identity(fd) == identity and fcntl.fcntl(fd,fcntl.F_GET_SEALS)&SEALS == SEALS
                    and fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE == os.O_RDONLY,
                    "sealed source descriptor changed or is writable")
        _before(self._until)

    def generation_report(self, *, plan_sha256):
        self._check(plan_sha256)
        return self._report

    def native_inputs(self, *, plan_sha256, loading_deadline_ns):
        """Exact existing native context and inherited FDs; not a launch ticket."""
        self._check(plan_sha256)
        now=time.monotonic_ns()
        require(type(loading_deadline_ns) is int and now < loading_deadline_ns <= self._until
                and loading_deadline_ns-now <= self._loading_limit,
                "native source loading deadline exceeds setup or owner lifetime")
        bindings = archive.parse_json(b'{"bindings":'+self._bindings+b'}')["bindings"]
        context = dict(schema_version="cpu-prefetch-stage17-s180-schedule-source-context/1",
            maximum_vector_bytes=self._vector, deadline_monotonic_ns=loading_deadline_ns, bindings=bindings)
        return context, tuple(b["descriptor"] for b in bindings)

    def proof(self, *, plan_sha256):
        self._check(plan_sha256)
        return dict(schema_version="cpu-prefetch-stage17-s180-verified-source-owner/1",
            plan_sha256=plan_sha256, generation_report_sha256=hashlib.sha256(self._report).hexdigest(),
            source_count=36, sealed_source_bytes=sum(v[2] for v in self._identity.values()),
            owner_pid=self._pid, boot_id=self._boot, valid_until_monotonic_ns=self._until,
            maximum_native_source_loading_ns=self._loading_limit,
            namespace_freshness_verified=False, resource_admission_performed=False,
            execution_authority=False, phase18_authority=False)

    def _close(self):
        self._closed = True
        _release(self._identity.items())


@contextlib.contextmanager
def verified_sources(*, plan, seed_id, records, maximum_source_bytes, maximum_vector_bytes,
                     verification_deadline_ns, valid_until_ns):
    """Verify once, pin exact sources and keep a same-process proof until exit.

    Call outside D322's short metadata lease. The parent still authenticates
    source closure, original namespace ownership, live resources and authority.
    Limits are caller-frozen prospective budgets, never inferred permissions.
    """
    _before(verification_deadline_ns)
    require(type(valid_until_ns) is int and verification_deadline_ns <= valid_until_ns
            and 0 < valid_until_ns-time.monotonic_ns() <= DAY_NS, "finite original source lifetime required")
    provenance._integer_control(plan)
    provenance._integer_control(records)
    plan_raw, records_raw = archive.canonical(plan), archive.canonical(dict(records=records))
    require(len(plan_raw) <= 16*1024**2 and len(records_raw) <= 1024**2, "source control byte bound")
    plan, records = archive.parse_json(plan_raw), archive.parse_json(records_raw)["records"]
    expected = provenance.expected_sources(plan,seed_id=seed_id)
    total = peak = 0
    for e in expected:
        size = archive.checked_product(e["offered_count"],8)
        peak = max(peak,archive.checked_sum(total,archive.checked_product(size,2)))
        total = archive.checked_sum(total,size)
    require(total <= archive.uint(maximum_source_bytes,"sealed source budget",positive=True)
            and peak <= archive.uint(maximum_vector_bytes,"native vector budget",positive=True),
            "sealed source/native vector byte budget insufficient")
    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    require(soft == resource.RLIM_INFINITY or len(os.listdir("/proc/self/fd"))+36+3+CONTROL_RESERVE <= soft,
            "actual FD limit cannot retain sources and control reserve")
    originals = _originals(records)
    report = provenance.verify_source_bank(plan=plan,seed_id=seed_id,records=records,
        maximum_source_bytes=maximum_source_bytes,deadline_ns=verification_deadline_ns)
    bindings, held, owner = [], [], None
    try:
        for row in report["sources"]:
            fd = _pin(row["binary"],deadline=verification_deadline_ns)
            held.append((fd,_fd_identity(fd)))
            bindings.append(dict(artifact_id=row["binary"]["artifact_id"],canonical_sha256=row["binary"]["sha256"],
                size_bytes=row["binary"]["size_bytes"],descriptor=fd))
        _check_originals(originals)
        _before(verification_deadline_ns)
        owner = _VerifiedSources(token=_TOKEN,report=report,bindings=bindings,originals=originals,
            maximum_vector_bytes=maximum_vector_bytes,valid_until_ns=valid_until_ns,
            maximum_loading_ns=plan['budget']['setup_ns'])
        owner._check(report["plan_sha256"])
        yield owner
    finally:
        if owner is not None:
            owner._close()
        else:
            _release(held)
