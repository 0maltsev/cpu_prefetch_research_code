#!/usr/bin/env python3
"""Clock-fresh, credential-pinned Stage 17 read-only preflight executor.

Production execution accepts no caller authority time, command, argv, stdin,
remote command, transport factory, retry, or output filename.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import re
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

import stage17_pilot_candidate_artifact
import stage17_read_only_preflight_collector_v1
import stage17_read_only_preflight_collector_v2
import stage17_semantic_verifier_v3
import stage17_semantic_verifier_v4
import stage17_semantic_verifier_v5
import stage17_state_journal
import stage17_state_journal_v2


EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v3"
FIXED_LOCAL_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "TZ": "UTC0"}
SAFE_CHILD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
PINNING_MECHANISM = "LINUX_SEALED_MEMFD_PROC_SELF_FD-v1"
SEAL_NAMES = ["F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"]
MAX_PINNED_INPUT_BYTES = 16 * 1024 * 1024


class ActionExecutionError(RuntimeError):
    """The fixed one-shot action was rejected or failed."""


@dataclass(frozen=True)
class TransportResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    failure: str | None = None


@dataclass(frozen=True)
class PinnedSnapshot:
    role: str
    descriptor: int
    proc_path: str
    metadata: dict[str, Any]


@dataclass
class PreparedAction:
    context: dict[str, Any]
    ssh_argv: tuple[str, ...]
    ssh_argv_sha256: str
    programs: tuple[bytes, ...]
    program_descriptors: tuple[dict[str, Any], ...]
    snapshots: tuple[PinnedSnapshot, PinnedSnapshot]
    pinned_inputs_metadata: dict[str, Any]
    pinned_inputs_metadata_sha256: str
    record_validators: dict[str, Draft202012Validator]
    directory_fd: int

    @property
    def pass_fds(self) -> tuple[int, int]:
        return tuple(item.descriptor for item in self.snapshots)  # type: ignore[return-value]

    def close(self) -> None:
        descriptors = [self.directory_fd, *(item.descriptor for item in self.snapshots)]
        for descriptor in descriptors:
            try:
                os.close(descriptor)
            except OSError:
                pass


@dataclass(frozen=True)
class OperationalFailure(Exception):
    stage: str
    category: str
    reason: str
    ordinal: int | None = None
    observation_id: str | None = None
    program_sha256: str | None = None
    authority_clock_relation: str = "LIVE_NONDECREASING"


def runtime_identity_paths() -> dict[str, str]:
    """Return the actual loaded repository runtime closure."""

    return {
        "semantic_verifier": str(pathlib.Path(stage17_semantic_verifier_v5.__file__).resolve()),
        "executor": str(pathlib.Path(__file__).resolve()),
        "collector": str(pathlib.Path(stage17_read_only_preflight_collector_v2.__file__).resolve()),
        "state_journal": str(pathlib.Path(stage17_state_journal_v2.__file__).resolve()),
        "semantic_verifier_v4_helper": str(pathlib.Path(stage17_semantic_verifier_v4.__file__).resolve()),
        "semantic_verifier_v3_helper": str(pathlib.Path(stage17_semantic_verifier_v3.__file__).resolve()),
        "collector_v1_helper": str(pathlib.Path(stage17_read_only_preflight_collector_v1.__file__).resolve()),
        "state_journal_v1_helper": str(pathlib.Path(stage17_state_journal.__file__).resolve()),
        "pilot_candidate_verifier": str(pathlib.Path(stage17_pilot_candidate_artifact.__file__).resolve()),
    }


def _actual_utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _argv_bytes(argv: tuple[str, ...]) -> bytes:
    encoded: list[bytes] = []
    for item in argv:
        value = item.encode("utf-8", errors="strict")
        if b"\x00" in value:
            raise ActionExecutionError("fixed SSH argv contains NUL")
        encoded.append(value)
    return b"\x00".join(encoded) + b"\x00"


def _read_descriptor_exact(descriptor: int, size_bytes: int) -> bytes:
    if size_bytes < 1 or size_bytes > MAX_PINNED_INPUT_BYTES:
        raise ActionExecutionError("pinned input size is outside the fixed safety bound")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = size_bytes + 1
    while remaining:
        chunk = os.read(descriptor, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    if len(payload) != size_bytes:
        raise ActionExecutionError("pinned input byte count changed during read")
    return payload


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            raise ActionExecutionError("sealed snapshot write made no progress")
        view = view[count:]


def _required_seal_mask() -> int:
    names = ("F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL")
    try:
        return sum(int(getattr(fcntl, name)) for name in names)
    except AttributeError as exception:
        raise ActionExecutionError("Linux memfd sealing constants are unavailable") from exception


def _pin_bound_input(binding: dict[str, Any], role: str) -> PinnedSnapshot:
    path = pathlib.Path(binding["locator"])
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    source_fd = os.open(path, flags)
    snapshot_fd: int | None = None
    try:
        metadata = os.fstat(source_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise ActionExecutionError(f"{role} source is not a regular file")
        if role == "TRANSPORT_IDENTITY" and (
            metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise ActionExecutionError("transport identity ownership or permissions changed")
        if metadata.st_size != binding["size_bytes"]:
            raise ActionExecutionError(f"{role} source size changed before pinning")
        payload = _read_descriptor_exact(source_fd, int(binding["size_bytes"]))
        digest = _sha256_bytes(payload)
        if digest != binding["sha256"]:
            raise ActionExecutionError(f"{role} source hash changed before pinning")
        if not hasattr(os, "memfd_create"):
            raise ActionExecutionError("Linux memfd_create is unavailable")
        flags_value = int(getattr(os, "MFD_CLOEXEC", 0x0001)) | int(
            getattr(os, "MFD_ALLOW_SEALING", 0x0002)
        )
        snapshot_fd = os.memfd_create(f"cpu-prefetch-stage17-{role.lower()}", flags_value)
        os.fchmod(snapshot_fd, 0o600)
        _write_all(snapshot_fd, payload)
        seal_mask = _required_seal_mask()
        fcntl.fcntl(snapshot_fd, fcntl.F_ADD_SEALS, seal_mask)
        actual_seals = int(fcntl.fcntl(snapshot_fd, fcntl.F_GET_SEALS))
        if actual_seals & seal_mask != seal_mask:
            raise ActionExecutionError(f"{role} sealed snapshot is incomplete")
        snapshot = os.pread(snapshot_fd, len(payload) + 1, 0)
        if snapshot != payload or _sha256_bytes(snapshot) != digest:
            raise ActionExecutionError(f"{role} sealed snapshot verification failed")
        proc_path = f"/proc/self/fd/{snapshot_fd}"
        result = PinnedSnapshot(
            role=role,
            descriptor=snapshot_fd,
            proc_path=proc_path,
            metadata={
                "role": role,
                "source_size_bytes": len(payload),
                "consumed_sha256": digest,
                "snapshot_size_bytes": len(snapshot),
                "snapshot_mechanism": PINNING_MECHANISM,
                "verified_seals": list(SEAL_NAMES),
                "source_path_reused_after_marker": False,
                "private_bytes_recorded": False,
            },
        )
        snapshot_fd = None
        return result
    finally:
        os.close(source_fd)
        if snapshot_fd is not None:
            os.close(snapshot_fd)


def _ssh_argv(
    context: dict[str, Any], known_hosts: PinnedSnapshot, identity: PinnedSnapshot
) -> tuple[str, ...]:
    substitutions = {
        "{PINNED_KNOWN_HOSTS_SNAPSHOT_PATH}": known_hosts.proc_path,
        "{TRANSPORT_IDENTITY_SNAPSHOT_PATH}": identity.proc_path,
        "{SSH_TARGET}": str(context["ssh_target"]),
    }
    rendered: list[str] = []
    for source in context["fixed_ssh_argv_template"]:
        token = source
        for placeholder, value in substitutions.items():
            token = token.replace(placeholder, value)
        if "{" in token or "}" in token or "\x00" in token:
            raise ActionExecutionError("fixed SSH argv has unresolved or invalid token")
        rendered.append(token)
    return tuple(rendered)


def _load_record_validator(
    root: pathlib.Path, binding: dict[str, Any], label: str
) -> Draft202012Validator:
    path = root / binding["path"]
    payload = path.read_bytes()
    if len(payload) != binding["size_bytes"] or _sha256_bytes(payload) != binding["sha256"]:
        raise ActionExecutionError(f"{label} schema bytes drifted before marker")
    try:
        schema = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise ActionExecutionError(f"{label} schema is malformed") from exception
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_record(
    prepared: PreparedAction, kind: str, document: dict[str, Any], label: str
) -> None:
    errors = list(prepared.record_validators[kind].iter_errors(document))
    if errors:
        first = errors[0]
        location = "/".join(str(item) for item in first.absolute_path)
        raise ActionExecutionError(f"{label} schema error at $/{location}: {first.message}")


def _open_evidence_root(context: dict[str, Any]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(context["evidence_root"], flags)
    metadata = os.fstat(descriptor)
    expected = context["evidence_root_identity"]
    actual = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }
    if not stat.S_ISDIR(metadata.st_mode) or actual != expected:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root directory identity changed")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root ownership or permissions are unsafe")
    return descriptor


def _child_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _verify_pre_marker_bindings(context: dict[str, Any]) -> None:
    for binding in context["pre_marker_file_bindings"]:
        path = pathlib.Path(binding["locator"])
        payload = path.read_bytes()
        if len(payload) != binding["size_bytes"] or _sha256_bytes(payload) != binding["sha256"]:
            raise ActionExecutionError("prospective repository input drifted during preparation")


def _prepare_action(repository_root: pathlib.Path, context: dict[str, Any]) -> PreparedAction:
    snapshots: list[PinnedSnapshot] = []
    directory_fd: int | None = None
    try:
        known_hosts = _pin_bound_input(context["known_hosts_binding"], "KNOWN_HOSTS")
        snapshots.append(known_hosts)
        identity = _pin_bound_input(
            context["transport_identity_binding"], "TRANSPORT_IDENTITY"
        )
        snapshots.append(identity)
        argv = _ssh_argv(context, known_hosts, identity)
        programs: list[bytes] = []
        descriptors: list[dict[str, Any]] = []
        for ordinal, observation_id in enumerate(context["observation_ids"], start=1):
            program = stage17_read_only_preflight_collector_v2.render_observation_program(
                observation_id, context["collector_context"]
            )
            compile(program, f"<stage17:{observation_id}>", "exec")
            programs.append(program)
            descriptors.append(
                {
                    "ordinal": ordinal,
                    "observation_id": observation_id,
                    "size_bytes": len(program),
                    "sha256": _sha256_bytes(program),
                }
            )
            for name in (
                f"s17-ro-{ordinal:03d}.stdout.bin",
                f"s17-ro-{ordinal:03d}.stderr.bin",
                f"s17-ro-{ordinal:03d}.receipt-v2.json",
            ):
                if SAFE_CHILD_NAME.fullmatch(name) is None:
                    raise ActionExecutionError("fixed output name is unsafe")
        for name in (
            context["attempt_marker_name"],
            context["failure_name"],
            context["completion_name"],
        ):
            if SAFE_CHILD_NAME.fullmatch(name) is None:
                raise ActionExecutionError("fixed action record name is unsafe")
        validators = {
            kind: _load_record_validator(repository_root, binding, kind)
            for kind, binding in context["record_schema_bindings"].items()
        }
        directory_fd = _open_evidence_root(context)
        names = [context["attempt_marker_name"], context["failure_name"], context["completion_name"]]
        names.extend(
            f"s17-ro-{ordinal:03d}{suffix}"
            for ordinal in range(1, 7)
            for suffix in (".stdout.bin", ".stderr.bin", ".receipt-v2.json")
        )
        if any(_child_exists(directory_fd, name) for name in names):
            raise ActionExecutionError("one-shot output appeared during preparation")
        _verify_pre_marker_bindings(context)
        metadata = {
            "known_hosts": known_hosts.metadata,
            "transport_identity": identity.metadata,
        }
        result = PreparedAction(
            context=context,
            ssh_argv=argv,
            ssh_argv_sha256=_sha256_bytes(_argv_bytes(argv)),
            programs=tuple(programs),
            program_descriptors=tuple(descriptors),
            snapshots=(known_hosts, identity),
            pinned_inputs_metadata=metadata,
            pinned_inputs_metadata_sha256=_sha256_bytes(
                stage17_state_journal_v2.canonical_json_bytes(metadata)
            ),
            record_validators=validators,
            directory_fd=directory_fd,
        )
        directory_fd = None
        snapshots.clear()
        return result
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        for snapshot in snapshots:
            try:
                os.close(snapshot.descriptor)
            except OSError:
                pass


def _transport_once(
    argv: tuple[str, ...],
    stdin: bytes,
    timeout_seconds: float,
    output_limit: int,
    pass_fds: tuple[int, int],
) -> TransportResult:
    """Open exactly one bounded transport with local ``shell=False``."""

    process = subprocess.Popen(
        list(argv),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=FIXED_LOCAL_ENVIRONMENT,
        close_fds=True,
        pass_fds=pass_fds,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise ActionExecutionError("transport pipes were not created")
    selector = selectors.DefaultSelector()
    streams = {
        process.stdin.fileno(): ("stdin", process.stdin),
        process.stdout.fileno(): ("stdout", process.stdout),
        process.stderr.fileno(): ("stderr", process.stderr),
    }
    for descriptor in streams:
        os.set_blocking(descriptor, False)
    selector.register(process.stdin, selectors.EVENT_WRITE)
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    pending = memoryview(stdin)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    failure: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "TIMEOUT"
                process.kill()
                break
            events = selector.select(min(remaining, 0.25))
            if not events and process.poll() is not None:
                for key in list(selector.get_map().values()):
                    if streams[key.fd][0] == "stdin":
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                continue
            for key, mask in events:
                kind, stream = streams[key.fd]
                if kind == "stdin":
                    if not pending:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    try:
                        count = os.write(key.fd, pending[:65536])
                    except BlockingIOError:
                        continue
                    pending = pending[count:]
                elif mask & selectors.EVENT_READ:
                    try:
                        chunk = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    remaining_output = output_limit - len(output["stdout"]) - len(output["stderr"])
                    if len(chunk) > remaining_output:
                        output[kind].extend(chunk[: max(remaining_output, 0)])
                        failure = "OUTPUT_LIMIT_EXCEEDED"
                        process.kill()
                        break
                    output[kind].extend(chunk)
            if failure is not None:
                break
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=2)
            failure = failure or "TERMINATION_TIMEOUT"
    finally:
        selector.close()
        for _, stream in streams.values():
            try:
                stream.close()
            except OSError:
                pass
    return TransportResult(
        returncode=returncode,
        stdout=bytes(output["stdout"]),
        stderr=bytes(output["stderr"]),
        failure=failure,
    )


def _write_exclusive_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    sync_directory: bool = True,
) -> str:
    if SAFE_CHILD_NAME.fullmatch(name) is None:
        raise ActionExecutionError("unsafe fixed child name")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    if sync_directory:
        os.fsync(directory_fd)
    return _sha256_bytes(payload)


def _remaining_seconds(deadline_ns: int) -> float:
    remaining_ns = deadline_ns - time.monotonic_ns()
    if remaining_ns <= 0:
        raise OperationalFailure(
            "GLOBAL_DEADLINE", "GLOBAL_WALL_TIMEOUT", "global 180-second deadline expired"
        )
    return remaining_ns / 1_000_000_000


def _reason(exception: BaseException) -> str:
    value = f"{type(exception).__name__}: {exception}"
    value = " ".join(value.split())
    return value[:512] or type(exception).__name__


def _base_links(prepared: PreparedAction) -> dict[str, Any]:
    context = prepared.context
    hashes = context["runtime_implementation_hashes"]
    return {
        "attempt_id": context["attempt_id"],
        "authorization_id": context["authorization_id"],
        "authorization_sha256": context["authorization_sha256"],
        "resolution_id": context["resolution_id"],
        "resolution_sha256": context["resolution_sha256"],
        "transition_id": context["transition_id"],
        "transition_sha256": context["transition_sha256"],
        "action_plan_sha256": context["action_plan_sha256"],
        "runtime_implementation_hashes": dict(hashes),
        "executor_sha256": hashes["executor"],
        "collector_sha256": hashes["collector"],
        "pinned_inputs_metadata_sha256": prepared.pinned_inputs_metadata_sha256,
    }


def _safe_failure_time(fallback: str) -> str:
    try:
        return _actual_utc_now()
    except BaseException:
        return fallback


def _write_failure(
    *,
    prepared: PreparedAction,
    failure: OperationalFailure,
    completed: list[str],
    action_started_ns: int,
    before_marker_utc: str,
    before_transport_utc: str | None,
) -> None:
    document = {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-failure/3",
        **_base_links(prepared),
        "failed_stage": failure.stage,
        "failed_ordinal": failure.ordinal,
        "failed_observation_id": failure.observation_id,
        "completed_observation_ids": list(completed),
        "reason_category": failure.category,
        "reason": failure.reason[:512],
        "actual_authority_sample_before_marker_utc": before_marker_utc,
        "actual_authority_sample_before_first_transport_utc": before_transport_utc,
        "authority_clock_relation": failure.authority_clock_relation,
        "actual_failed_at_utc": _safe_failure_time(before_transport_utc or before_marker_utc),
        "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
        "ssh_argv_sha256": prepared.ssh_argv_sha256,
        "rendered_program_sha256": failure.program_sha256,
        "retry_allowed": False,
        "partial_evidence_retained": True,
        "stage18_authority": False,
    }
    _validate_record(prepared, "failure", document, "failure record")
    _write_exclusive_at(
        prepared.directory_fd,
        prepared.context["failure_name"],
        stage17_state_journal_v2.canonical_json_bytes(document) + b"\n",
    )


def _prospective_validation(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
    actual_utc: str,
) -> stage17_state_journal_v2.JournalValidation:
    return stage17_state_journal_v2.validate_journal(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        as_of_utc=actual_utc,
        requested_action_input_id="S17-EXT-001",
        runtime_identity_paths=runtime_identity_paths(),
    )


def _authority_relation(
    *,
    sample: dt.datetime,
    previous: dt.datetime,
    issued: dt.datetime,
    expires: dt.datetime,
) -> str:
    if sample < previous:
        return "ROLLBACK"
    if sample < issued:
        return "NOT_YET_VALID"
    if sample >= expires:
        return "EXPIRED"
    return "LIVE_NONDECREASING"


def execute_once(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
) -> None:
    """Execute one admitted action using fresh clocks and sealed input snapshots."""

    prospective_utc = _actual_utc_now()
    validation = _prospective_validation(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        actual_utc=prospective_utc,
    )
    if not validation.action_ready or validation.action_context is None:
        raise ActionExecutionError("S17-EXT-001 is not prospectively action-ready")
    prepared = _prepare_action(repository_root.resolve(), validation.action_context)
    marker_created = False
    action_started_ns = 0
    before_transport_utc: str | None = None
    try:
        before_marker_utc = _actual_utc_now()
        context = prepared.context
        issued = stage17_state_journal_v2.parse_utc(
            context["authorization"]["issued_at_utc"], "actual authority issue"
        )
        expires = stage17_state_journal_v2.parse_utc(
            context["authorization"]["expires_at_utc"], "actual authority expiry"
        )
        prospective = stage17_state_journal_v2.parse_utc(
            prospective_utc, "prospective authority UTC"
        )
        before_marker = stage17_state_journal_v2.parse_utc(
            before_marker_utc, "actual pre-marker UTC"
        )
        relation = _authority_relation(
            sample=before_marker,
            previous=prospective,
            issued=issued,
            expires=expires,
        )
        if relation != "LIVE_NONDECREASING":
            raise ActionExecutionError(
                f"authorization rejected before marker: {relation}"
            )

        action_started_ns = time.monotonic_ns()
        deadline_ns = action_started_ns + int(context["max_wall_seconds"]) * 1_000_000_000
        marker = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/3",
            "attempt_id": context["attempt_id"],
            "authorization_id": context["authorization_id"],
            "authorization_sha256": context["authorization_sha256"],
            "resolution_id": context["resolution_id"],
            "resolution_sha256": context["resolution_sha256"],
            "transition_id": context["transition_id"],
            "transition_sha256": context["transition_sha256"],
            "action_plan_sha256": context["action_plan_sha256"],
            "runtime_implementation_hashes": context["runtime_implementation_hashes"],
            "ssh_argv_sha256": prepared.ssh_argv_sha256,
            "rendered_programs": list(prepared.program_descriptors),
            "pinned_openssh_inputs": prepared.pinned_inputs_metadata,
            "prospective_evaluation_at_utc": prospective_utc,
            "actual_authority_sample_before_marker_utc": before_marker_utc,
            "monotonic_deadline_ns": deadline_ns,
            "attempt_number": 1,
            "retry_allowed": False,
            "post_marker_authority_sample_required": True,
            "stage18_authority": False,
        }
        _validate_record(prepared, "attempt", marker, "attempt marker")
        try:
            _write_exclusive_at(
                prepared.directory_fd,
                context["attempt_marker_name"],
                stage17_state_journal_v2.canonical_json_bytes(marker) + b"\n",
            )
            marker_created = True
        except FileExistsError as exception:
            raise ActionExecutionError("one-shot attempt marker already exists") from exception

        completed: list[str] = []
        receipt_hashes: list[str] = []
        total_output = 0
        active_descriptor: dict[str, Any] | None = None
        try:
            for descriptor, program in zip(
                prepared.program_descriptors, prepared.programs, strict=True
            ):
                active_descriptor = descriptor
                remaining = _remaining_seconds(deadline_ns)
                timeout = min(float(context["timeout_seconds"]), remaining)
                if descriptor["ordinal"] == 1:
                    try:
                        before_transport_utc = _actual_utc_now()
                        before_transport = stage17_state_journal_v2.parse_utc(
                            before_transport_utc, "actual pre-transport UTC"
                        )
                    except BaseException as exception:
                        raise OperationalFailure(
                            "AUTHORITY_TIME",
                            "AUTHORITY_CLOCK_READ_FAILURE",
                            _reason(exception),
                            authority_clock_relation="CLOCK_READ_FAILURE",
                        ) from exception
                    relation = _authority_relation(
                        sample=before_transport,
                        previous=before_marker,
                        issued=issued,
                        expires=expires,
                    )
                    if relation != "LIVE_NONDECREASING":
                        raise OperationalFailure(
                            "AUTHORITY_TIME",
                            f"AUTHORITY_{relation}_BEFORE_FIRST_TRANSPORT",
                            f"post-marker authority sample rejected: {relation}",
                            authority_clock_relation=relation,
                        )
                    observation_started_utc = before_transport_utc
                else:
                    observation_started_utc = _actual_utc_now()
                observation_started_ns = time.monotonic_ns()
                try:
                    result = _transport_once(
                        prepared.ssh_argv,
                        program,
                        timeout,
                        int(context["max_output_bytes"]),
                        prepared.pass_fds,
                    )
                except BaseException as exception:
                    raise OperationalFailure(
                        "TRANSPORT",
                        "TRANSPORT_EXCEPTION",
                        _reason(exception),
                        descriptor["ordinal"],
                        descriptor["observation_id"],
                        descriptor["sha256"],
                    ) from exception
                _remaining_seconds(deadline_ns)
                total_output += len(result.stdout) + len(result.stderr)
                if total_output > int(context["max_total_output_bytes"]):
                    raise OperationalFailure(
                        "GLOBAL_DEADLINE",
                        "TOTAL_OUTPUT_LIMIT_EXCEEDED",
                        "total output exceeded the fixed action limit",
                        descriptor["ordinal"],
                        descriptor["observation_id"],
                        descriptor["sha256"],
                    )
                ordinal = descriptor["ordinal"]
                try:
                    _write_exclusive_at(
                        prepared.directory_fd,
                        f"s17-ro-{ordinal:03d}.stdout.bin",
                        result.stdout,
                    )
                    _write_exclusive_at(
                        prepared.directory_fd,
                        f"s17-ro-{ordinal:03d}.stderr.bin",
                        result.stderr,
                    )
                except BaseException as exception:
                    raise OperationalFailure(
                        "OUTPUT_RETENTION",
                        "OUTPUT_WRITE_EXCEPTION",
                        _reason(exception),
                        ordinal,
                        descriptor["observation_id"],
                        descriptor["sha256"],
                    ) from exception
                receipt = {
                    "schema_version": "cpu-prefetch-stage17-read-only-preflight-observation-receipt/2",
                    **_base_links(prepared),
                    "ordinal": ordinal,
                    "observation_id": descriptor["observation_id"],
                    "rendered_program_sha256": descriptor["sha256"],
                    "ssh_argv_sha256": prepared.ssh_argv_sha256,
                    "actual_authority_sample_before_marker_utc": before_marker_utc,
                    "actual_authority_sample_before_first_transport_utc": before_transport_utc,
                    "actual_started_at_utc": observation_started_utc,
                    "actual_completed_at_utc": _actual_utc_now(),
                    "duration_ns": max(0, time.monotonic_ns() - observation_started_ns),
                    "returncode": result.returncode,
                    "failure": result.failure,
                    "stdout_size_bytes": len(result.stdout),
                    "stdout_sha256": _sha256_bytes(result.stdout),
                    "stderr_size_bytes": len(result.stderr),
                    "stderr_sha256": _sha256_bytes(result.stderr),
                    "attempt": 1,
                    "retry": 0,
                    "stage18_authority": False,
                }
                try:
                    _validate_record(prepared, "receipt", receipt, "observation receipt")
                    receipt_hashes.append(
                        _write_exclusive_at(
                            prepared.directory_fd,
                            f"s17-ro-{ordinal:03d}.receipt-v2.json",
                            stage17_state_journal_v2.canonical_json_bytes(receipt) + b"\n",
                        )
                    )
                except BaseException as exception:
                    raise OperationalFailure(
                        "RECEIPT_RETENTION",
                        "RECEIPT_WRITE_EXCEPTION",
                        _reason(exception),
                        ordinal,
                        descriptor["observation_id"],
                        descriptor["sha256"],
                    ) from exception
                if result.failure is not None or result.returncode != 0:
                    raise OperationalFailure(
                        "TRANSPORT",
                        result.failure or "REMOTE_NONZERO_EXIT",
                        result.failure or f"remote exit {result.returncode}",
                        ordinal,
                        descriptor["observation_id"],
                        descriptor["sha256"],
                    )
                completed.append(descriptor["observation_id"])
                _remaining_seconds(deadline_ns)
            completion = {
                "schema_version": "cpu-prefetch-stage17-read-only-preflight-completion/2",
                **_base_links(prepared),
                "ssh_argv_sha256": prepared.ssh_argv_sha256,
                "completed_observation_ids": completed,
                "receipt_sha256s": receipt_hashes,
                "actual_authority_sample_before_marker_utc": before_marker_utc,
                "actual_authority_sample_before_first_transport_utc": before_transport_utc,
                "actual_completed_at_utc": _actual_utc_now(),
                "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
                "attempts": 6,
                "retries": 0,
                "stage18_authority": False,
            }
            _validate_record(prepared, "completion", completion, "completion record")
            _remaining_seconds(deadline_ns)
            try:
                _write_exclusive_at(
                    prepared.directory_fd,
                    context["completion_name"],
                    stage17_state_journal_v2.canonical_json_bytes(completion) + b"\n",
                )
            except BaseException as exception:
                raise OperationalFailure(
                    "COMPLETION_RETENTION",
                    "COMPLETION_WRITE_EXCEPTION",
                    _reason(exception),
                ) from exception
        except BaseException as exception:
            if isinstance(exception, OperationalFailure):
                failure = exception
            else:
                failure = OperationalFailure(
                    "UNEXPECTED_OPERATIONAL_EXCEPTION",
                    "UNEXPECTED_OPERATIONAL_EXCEPTION",
                    _reason(exception),
                    active_descriptor["ordinal"] if active_descriptor else None,
                    active_descriptor["observation_id"] if active_descriptor else None,
                    active_descriptor["sha256"] if active_descriptor else None,
                )
            try:
                _write_failure(
                    prepared=prepared,
                    failure=failure,
                    completed=completed,
                    action_started_ns=action_started_ns,
                    before_marker_utc=before_marker_utc,
                    before_transport_utc=before_transport_utc,
                )
            except BaseException:
                pass
            raise ActionExecutionError(
                f"fixed read-only preflight stopped: {failure.category}"
            ) from exception
    finally:
        if marker_created:
            try:
                os.fsync(prepared.directory_fd)
            except OSError:
                pass
        prepared.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root,
            latest_journal=arguments.journal,
            journal_directory=arguments.journal_directory,
        )
    except (
        ActionExecutionError,
        stage17_state_journal_v2.JournalError,
        OSError,
        ValueError,
    ) as exception:
        print(f"stage17-read-only-preflight-v3: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-read-only-preflight-v3: PASS fixed=6 retry=0 Stage18=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
