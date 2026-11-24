#!/usr/bin/env python3
"""Exact-byte, one-shot Stage 17 fixed-action worker execution boundary.

This module has no command-line interface and no fake-backend switch.  The
production controller is its only production caller.  Test-linked workers are
admitted only by the separate hermetic test harness.
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import selectors
import stat
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_process_group_supervisor_v2 as process_supervisor


MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_WORKER_BYTES = 64 * 1024 * 1024
GLOBAL_WALL_SECONDS = 180
RESULT_NAME = "stage17-action-result-v2.json"
FIXED_ENVIRONMENT = {
    "LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TZ": "UTC",
}


class FixedActionExecutionError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class WorkerSnapshot:
    descriptor: int
    locator: str
    size_bytes: int
    sha256: str

    def close(self) -> None:
        try:
            os.close(self.descriptor)
        except OSError:
            pass


@dataclass(frozen=True)
class TransportOutcome:
    returncode: int
    stdout: bytes
    stderr: bytes
    leader_reaped: bool
    process_group_gone: bool
    cleanup_outcome: str


@dataclass(frozen=True)
class ExecutionOutcome:
    attempt_path: pathlib.Path
    result_path: pathlib.Path
    completion_path: pathlib.Path
    result: dict[str, Any]
    completion: dict[str, Any]


def canonical(document: object) -> bytes:
    return (json.dumps(document, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FixedActionExecutionError("AUTHORITY_TIME", "authority time is not UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise FixedActionExecutionError("AUTHORITY_TIME", "authority time is malformed") from exception
    if parsed.tzinfo is None:
        raise FixedActionExecutionError("AUTHORITY_TIME", "authority time is naive")
    return parsed


def load_schema_validator(root: pathlib.Path, relative: str) -> Draft202012Validator:
    schema = json.loads((root / relative).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_with_schema(
    validator: Draft202012Validator, document: dict[str, Any], label: str,
) -> None:
    errors = sorted(
        validator.iter_errors(document),
        key=lambda item: tuple(item.path),
    )
    if errors:
        path = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise FixedActionExecutionError("SCHEMA", f"{label} invalid at {path}: {errors[0].message}")


def validate_schema(root: pathlib.Path, relative: str, document: dict[str, Any], label: str) -> None:
    validate_with_schema(load_schema_validator(root, relative), document, label)


def _read_bound_regular(path: pathlib.Path, binding: dict[str, Any], *, executable: bool) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        metadata = os.fstat(descriptor)
        mode = stat.S_IMODE(metadata.st_mode)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.geteuid():
            raise FixedActionExecutionError("FILE_IDENTITY", "bound input is not an owner regular file")
        if mode & 0o022:
            raise FixedActionExecutionError("FILE_PERMISSIONS", "bound input is group/world writable")
        if executable and mode & 0o111 == 0:
            raise FixedActionExecutionError("WORKER_NOT_EXECUTABLE", "bound worker is not executable")
        if metadata.st_size < 1 or metadata.st_size > MAX_WORKER_BYTES:
            raise FixedActionExecutionError("FILE_SIZE", "bound worker exceeds its fixed size limit")
        if metadata.st_size != binding.get("size_bytes"):
            raise FixedActionExecutionError("FILE_SIZE", "bound input size drifted")
        payload = bytearray()
        while len(payload) <= metadata.st_size:
            chunk = os.read(descriptor, min(65536, metadata.st_size + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        result = bytes(payload)
        if len(result) != metadata.st_size or sha256(result) != binding.get("sha256"):
            raise FixedActionExecutionError("FILE_HASH", "bound input bytes drifted")
        return result
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _pin_worker(path: pathlib.Path, binding: dict[str, Any]) -> WorkerSnapshot:
    payload = _read_bound_regular(path, binding, executable=True)
    if not hasattr(os, "memfd_create"):
        raise FixedActionExecutionError("WORKER_SNAPSHOT", "Linux memfd is unavailable")
    descriptor = os.memfd_create(
        "cpu-prefetch-stage17-fixed-worker-v2",
        int(getattr(os, "MFD_CLOEXEC", 1)) | int(getattr(os, "MFD_ALLOW_SEALING", 2)),
    )
    try:
        os.fchmod(descriptor, 0o500)
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise FixedActionExecutionError("WORKER_SNAPSHOT", "worker snapshot write stalled")
            view = view[count:]
        seals = sum(int(getattr(fcntl, name)) for name in (
            "F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"
        ))
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
        if int(fcntl.fcntl(descriptor, fcntl.F_GET_SEALS)) & seals != seals:
            raise FixedActionExecutionError("WORKER_SNAPSHOT", "worker snapshot seals are incomplete")
        identity = snapshot_broker.discover_procfs_identity()
        locator = pathlib.Path("/proc") / str(identity.visible_pid) / "fd" / str(descriptor)
        reopened = os.open(locator, os.O_RDONLY | os.O_CLOEXEC)
        try:
            observed = os.pread(reopened, len(payload) + 1, 0)
            metadata = os.fstat(reopened)
            if (observed != payload or not stat.S_ISREG(metadata.st_mode)
                    or metadata.st_size != len(payload)):
                raise FixedActionExecutionError("WORKER_SNAPSHOT", "worker procfd identity drifted")
        finally:
            os.close(reopened)
        return WorkerSnapshot(descriptor, str(locator), len(payload), sha256(payload))
    except BaseException:
        os.close(descriptor)
        raise


def _pin_generated(payload: bytes, role: str) -> snapshot_broker.ParentSnapshot:
    if not payload or not hasattr(os, "memfd_create"):
        raise FixedActionExecutionError("CONTEXT_SNAPSHOT", "cannot create generated sealed context")
    descriptor = os.memfd_create(
        f"cpu-prefetch-stage17-{role.lower()}",
        int(getattr(os, "MFD_CLOEXEC", 1)) | int(getattr(os, "MFD_ALLOW_SEALING", 2)),
    )
    try:
        os.fchmod(descriptor, 0o600)
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise FixedActionExecutionError("CONTEXT_SNAPSHOT", "context snapshot write stalled")
            view = view[count:]
        seals = sum(int(getattr(fcntl, name)) for name in (
            "F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"
        ))
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
        identity = snapshot_broker.discover_procfs_identity()
        locator = f"/proc/{identity.visible_pid}/fd/{descriptor}"
        metadata = {
            "role": role, "source_size_bytes": len(payload),
            "consumed_sha256": sha256(payload), "snapshot_size_bytes": len(payload),
            "snapshot_mechanism": snapshot_broker.MECHANISM,
            "verified_seals": list(snapshot_broker.REQUIRED_SEAL_NAMES),
            "procfs_visible_parent_pid": identity.visible_pid,
            "credential_fd_inherited_by_child": True,
            "source_path_reused_after_marker": False,
            "private_bytes_recorded": False,
        }
        result = snapshot_broker.ParentSnapshot(role, descriptor, locator, metadata)
        snapshot_broker.verify_snapshot(result)
        return result
    except BaseException:
        os.close(descriptor)
        raise


def _open_output_root(path: pathlib.Path, repository_root: pathlib.Path) -> int:
    if not path.is_absolute() or path == repository_root or repository_root in path.parents:
        raise FixedActionExecutionError("OUTPUT_ROOT", "output root must be outside the repository")
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    metadata = os.fstat(descriptor)
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        os.close(descriptor)
        raise FixedActionExecutionError("OUTPUT_ROOT", "output root must be owner-owned mode 0700")
    return descriptor


def _write_exclusive(directory_fd: int, name: str, payload: bytes) -> str:
    if not name or "/" in name or name in {".", ".."}:
        raise FixedActionExecutionError("OUTPUT_NAME", "unsafe fixed output name")
    descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600, dir_fd=directory_fd,
    )
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise FixedActionExecutionError("OUTPUT_WRITE", "output write stalled")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)
    return sha256(payload)


def _exists_at(directory_fd: int, name: str) -> bool:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=directory_fd)
    except FileNotFoundError:
        return False
    else:
        os.close(descriptor)
        return True


def _read_at(directory_fd: int, name: str, limit: int = 16 * 1024 * 1024) -> bytes:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=directory_fd)
    except FileNotFoundError as exception:
        raise FixedActionExecutionError(
            "RESULT_MISSING", "mandatory typed result/output is absent"
        ) from exception
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1 or metadata.st_size > limit:
            raise FixedActionExecutionError("RESULT_FILE", "result/output is not a bounded regular file")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size:
            raise FixedActionExecutionError("RESULT_FILE", "result/output short read")
        return payload
    finally:
        os.close(descriptor)


def _authority_guard(authorization: dict[str, Any], previous: dt.datetime,
                     monotonic_expiry_ns: int, global_deadline_ns: int) -> str:
    text = utc_now()
    current = parse_utc(text)
    issued = parse_utc(authorization["issued_at_utc"])
    expires = parse_utc(authorization["expires_at_utc"])
    now_ns = time.monotonic_ns()
    if current < previous or not issued <= current < expires:
        raise FixedActionExecutionError("AUTHORITY_TIME", "authorization is future, expired, or wall clock rolled back")
    if now_ns >= monotonic_expiry_ns or now_ns >= global_deadline_ns:
        raise FixedActionExecutionError("AUTHORITY_DEADLINE", "authority/global monotonic deadline expired")
    return text


def _run_worker(argv: tuple[str, ...], pass_fds: tuple[int, ...], *,
                global_deadline_ns: int, authority_guard: Callable[[], str]) -> TransportOutcome:
    selector = selectors.DefaultSelector()
    lease = process_supervisor.SupervisorLease()
    process: subprocess.Popen[bytes] | None = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    streams: dict[int, tuple[str, Any]] = {}
    primary: BaseException | None = None
    timed_out = False
    cleanup: process_supervisor.CleanupResult | None = None
    lease.enter()
    try:
        authority_guard()
        process = subprocess.Popen(
            list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, close_fds=True,
            pass_fds=pass_fds, start_new_session=True, env=FIXED_ENVIRONMENT,
        )
        try:
            assert process.stdout is not None and process.stderr is not None
            streams = {
                process.stdout.fileno(): ("stdout", process.stdout),
                process.stderr.fileno(): ("stderr", process.stderr),
            }
            for descriptor, (_, stream) in streams.items():
                os.set_blocking(descriptor, False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                remaining = global_deadline_ns - time.monotonic_ns()
                if remaining <= 2_000_000_000:
                    timed_out = True
                    break
                for key, _ in selector.select(min(remaining / 1e9, 0.25)):
                    kind, stream = streams[key.fd]
                    try:
                        chunk = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    if len(output["stdout"]) + len(output["stderr"]) + len(chunk) > MAX_OUTPUT_BYTES:
                        raise FixedActionExecutionError("WORKER_OUTPUT_LIMIT", "worker output exceeded fixed bound")
                    output[kind].extend(chunk)
        except BaseException as exception:
            primary = exception
        finally:
            selector.close()
            for _, stream in streams.values():
                try:
                    stream.close()
                except OSError:
                    pass
            assert process is not None and lease.identity_model is not None
            cleanup = process_supervisor.cleanup_process_group(
                process, force_stop=primary is not None or timed_out,
                leader_wait_deadline_ns=min(time.monotonic_ns() + 2_000_000_000,
                                            global_deadline_ns),
                global_deadline_ns=global_deadline_ns,
                identity_model=lease.identity_model,
            )
    finally:
        lease.close()
    if cleanup is None or not cleanup.leader_reaped or not cleanup.process_group_gone:
        raise FixedActionExecutionError("PROCESS_CLEANUP", "worker process family was not proven quiescent")
    if primary is not None:
        raise FixedActionExecutionError("WORKER_RUNTIME", str(primary)) from primary
    if timed_out:
        raise FixedActionExecutionError("WORKER_TIMEOUT", "worker exceeded the common wall deadline")
    if cleanup.descendants_detected_after_leader_exit:
        raise FixedActionExecutionError("WORKER_DESCENDANT", "worker left a descendant after leader exit")
    return TransportOutcome(
        cleanup.returncode, bytes(output["stdout"]), bytes(output["stderr"]),
        cleanup.leader_reaped, cleanup.process_group_gone,
        cleanup.terminal_cleanup_outcome,
    )


def execute_fixed_action(
    *, repository_root: pathlib.Path, authorization: dict[str, Any],
    authorization_bytes: bytes, request: dict[str, Any], request_bytes: bytes,
    worker_binding: dict[str, Any], worker_path: pathlib.Path,
    release_binding: dict[str, Any], output_root: pathlib.Path,
    test_linked_worker: bool = False,
) -> ExecutionOutcome:
    """Execute one admitted action; caller has already verified trust/state."""

    root = repository_root.resolve()
    action = authorization["action_id"]
    token = action.lower().replace("-", "_")
    marker_name = f"stage17-{token}-attempt-v2.json"
    failure_name = f"stage17-{token}-failure-v2.json"
    completion_name = f"stage17-{token}-completion-v2.json"
    worker_snapshot: WorkerSnapshot | None = None
    request_snapshot: snapshot_broker.ParentSnapshot | None = None
    context_snapshot: snapshot_broker.ParentSnapshot | None = None
    directory_fd: int | None = None
    marker_created = False
    attempt: dict[str, Any] | None = None
    started_ns = time.monotonic_ns()
    global_deadline_ns = started_ns + GLOBAL_WALL_SECONDS * 1_000_000_000
    try:
        schema_validators = {
            "context": load_schema_validator(
                root, "config/schemas/stage17-fixed-action-context-v2.schema.json"
            ),
            "attempt": load_schema_validator(
                root, "config/schemas/stage17-phase-action-attempt-v2.schema.json"
            ),
            "failure": load_schema_validator(
                root, "config/schemas/stage17-phase-action-failure-v2.schema.json"
            ),
            "result": load_schema_validator(
                root, "config/schemas/stage17-phase-action-result-v2.schema.json"
            ),
            "output": load_schema_validator(
                root, "config/schemas/stage17-action-output-v2.schema.json"
            ),
            "completion": load_schema_validator(
                root, "config/schemas/stage17-phase-action-completion-v2.schema.json"
            ),
        }
        action_plan_bytes = (
            root / "config/stage17/stage17-fixed-phase-actions-v2.json"
        ).read_bytes()
        if sha256(action_plan_bytes) != authorization["fixed_action_definition_sha256"]:
            raise FixedActionExecutionError(
                "ACTION_PLAN", "fixed action plan bytes drifted before marker"
            )
        action_plan = json.loads(action_plan_bytes)
        definitions = [
            item for item in action_plan["actions"] if item["action_id"] == action
        ]
        if len(definitions) != 1:
            raise FixedActionExecutionError(
                "ACTION_PLAN", "fixed action is absent or duplicated"
            )
        expected_output_names = (
            {RESULT_NAME, "synthetic-fixed-action-output-v2.json"}
            if test_linked_worker
            else {RESULT_NAME, *definitions[0]["fixed_output_names"]}
        )
        worker_snapshot = _pin_worker(worker_path, worker_binding)
        request_snapshot = snapshot_broker.pin_bound_input(
            {"locator": str(authorization["request_binding"]["path"]),
             "size_bytes": len(request_bytes), "sha256": sha256(request_bytes)},
            "FIXED_ACTION_REQUEST",
        )
        snapshot_broker.verify_snapshot(request_snapshot)
        if os.pread(request_snapshot.descriptor, len(request_bytes) + 1, 0) != request_bytes:
            raise FixedActionExecutionError("REQUEST_SNAPSHOT", "request snapshot bytes drifted")
        context = {
            "schema_version": "cpu-prefetch-stage17-fixed-action-context/2",
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": sha256(authorization_bytes),
            "request_id": request["request_id"], "request_sha256": sha256(request_bytes),
            "attempt_id": request["attempt_id"], "action_id": authorization["action_id"],
            "phase18_authority": False,
        }
        validate_with_schema(schema_validators["context"], context, "worker context")
        context_snapshot = _pin_generated(canonical(context), "FIXED_ACTION_CONTEXT")
        directory_fd = _open_output_root(output_root.resolve(), root)
        for version in range(1, 3):
            if _exists_at(directory_fd, f"stage17-{token}-attempt-v{version}.json"):
                raise FixedActionExecutionError("REPLAY", "a predecessor/current one-shot marker exists")
        if any(_exists_at(directory_fd, name) for name in (failure_name, completion_name, RESULT_NAME)):
            raise FixedActionExecutionError("REPLAY", "terminal or worker result already exists")

        before_marker_text = utc_now()
        before_marker = parse_utc(before_marker_text)
        issued, expires = parse_utc(authorization["issued_at_utc"]), parse_utc(authorization["expires_at_utc"])
        if not issued <= before_marker < expires:
            raise FixedActionExecutionError("AUTHORITY_TIME", "authorization is future or expired before marker")
        monotonic_expiry_ns = time.monotonic_ns() + int((expires - before_marker).total_seconds() * 1e9)
        attempt = {
            "schema_version": "cpu-prefetch-stage17-phase-action-attempt/2",
            "attempt_id": request["attempt_id"], "action_id": action,
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": sha256(authorization_bytes),
            "request_sha256": sha256(request_bytes),
            "runtime_sha256": worker_snapshot.sha256,
            "release_resolution_id": release_binding["source_resolution_id"],
            "release_resolution_sha256": release_binding["source_resolution_sha256"],
            "started_at_utc": before_marker_text, "one_attempt": True,
            "retries": 0, "marker_durable": True, "phase18_authority": False,
        }
        validate_with_schema(schema_validators["attempt"], attempt, "attempt")
        _write_exclusive(directory_fd, marker_name, canonical(attempt))
        marker_created = True

        argv = (
            worker_snapshot.locator, "--execute-fixed-stage17-action-v2", action,
            "--request-fd", str(request_snapshot.descriptor),
            "--context-fd", str(context_snapshot.descriptor),
            "--output-dir-fd", str(directory_fd), "--fixed-dispatch-end",
        )
        transport = _run_worker(
            argv, (request_snapshot.descriptor, context_snapshot.descriptor, directory_fd),
            global_deadline_ns=global_deadline_ns,
            authority_guard=lambda: _authority_guard(
                authorization, before_marker, monotonic_expiry_ns, global_deadline_ns
            ),
        )
        _write_exclusive(directory_fd, f"stage17-{token}-stdout-v2.bin", transport.stdout)
        _write_exclusive(directory_fd, f"stage17-{token}-stderr-v2.bin", transport.stderr)
        if transport.returncode != 0:
            raise FixedActionExecutionError("WORKER_NONZERO", f"fixed worker returned {transport.returncode}")
        result_bytes = _read_at(directory_fd, RESULT_NAME)
        result = json.loads(result_bytes)
        if not isinstance(result, dict):
            raise FixedActionExecutionError("RESULT_SCHEMA", "typed result root is not an object")
        validate_with_schema(schema_validators["result"], result, "worker result")
        expected = (
            result["authorization_id"] == authorization["authorization_id"]
            and result["authorization_sha256"] == sha256(authorization_bytes)
            and result["request_id"] == request["request_id"]
            and result["request_sha256"] == sha256(request_bytes)
            and result["action_id"] == action and result["attempt_id"] == request["attempt_id"]
            and result["runtime_binding"] == request["runtime_binding"]
            and result["release_binding"] == release_binding
            and result["predecessor_resolutions"] == request["predecessor_resolutions"]
            and result["synthetic_test_only"] is test_linked_worker
            and result["phase18_authority"] is False
        )
        if not expected:
            raise FixedActionExecutionError("RESULT_LINEAGE", "typed result lineage/runtime drifted")
        if action == "Q15-W" and (not result["restoration_verified"] or result["quarantined"]):
            raise FixedActionExecutionError("RESTORATION", "Q15-W lacks successful restoration")
        actual_output_names = {RESULT_NAME, *(item["file_name"] for item in result["artifacts"])}
        if actual_output_names != expected_output_names:
            raise FixedActionExecutionError("RESULT_ARTIFACT", "worker output set differs from fixed action plan")
        artifact_bindings = []
        seen_names = {RESULT_NAME}
        for binding in result["artifacts"]:
            name = binding["file_name"]
            if name in seen_names:
                raise FixedActionExecutionError("RESULT_ARTIFACT", "duplicate output name")
            seen_names.add(name)
            payload = _read_at(directory_fd, name)
            if (len(payload), sha256(payload)) != (binding["size_bytes"], binding["sha256"]):
                raise FixedActionExecutionError("RESULT_ARTIFACT", "worker artifact bytes drifted")
            if binding["media_type"] == "application/json":
                document = json.loads(payload)
                validate_with_schema(schema_validators["output"], document, name)
                if document.get("schema_version") != binding["schema_identity"]:
                    raise FixedActionExecutionError("RESULT_ARTIFACT", "worker artifact schema identity drifted")
            elif (binding["media_type"] != "application/octet-stream"
                  or binding["schema_identity"] != "RAW-OBS-U64LE-LP-RUNID-v1"
                  or binding["role"] not in {"PRODUCER_RAW_OBSERVATIONS", "CONSUMER_RAW_OBSERVATIONS"}):
                raise FixedActionExecutionError("RESULT_ARTIFACT", "worker binary artifact contract drifted")
            artifact_bindings.append({"file_name": name, "size_bytes": len(payload), "sha256": sha256(payload)})
        completion = {
            "schema_version": "cpu-prefetch-stage17-phase-action-completion/2",
            "completion_id": request["attempt_id"] + ":completion",
            "attempt_id": request["attempt_id"], "action_id": action,
            "authorization_sha256": sha256(authorization_bytes),
            "request_sha256": sha256(request_bytes),
            "runtime_sha256": worker_snapshot.sha256,
            "result": {"file_name": RESULT_NAME, "size_bytes": len(result_bytes), "sha256": sha256(result_bytes)},
            "artifact_bindings": artifact_bindings,
            "leader_reaped": transport.leader_reaped,
            "process_group_gone": transport.process_group_gone,
            "restoration_verified": result["restoration_verified"],
            "quarantined": result["quarantined"], "completed_at_utc": utc_now(),
            "phase18_authority": False,
        }
        validate_with_schema(schema_validators["completion"], completion, "completion")
        _write_exclusive(directory_fd, completion_name, canonical(completion))
        return ExecutionOutcome(output_root / marker_name, output_root / RESULT_NAME,
                                output_root / completion_name, result, completion)
    except BaseException as exception:
        if marker_created and directory_fd is not None and attempt is not None and not _exists_at(directory_fd, failure_name):
            failure = {
                "schema_version": "cpu-prefetch-stage17-phase-action-failure/2",
                "failure_id": request["attempt_id"] + ":failure",
                "attempt_id": request["attempt_id"], "action_id": authorization["action_id"],
                "authorization_sha256": sha256(authorization_bytes),
                "request_sha256": sha256(request_bytes),
                "runtime_sha256": worker_snapshot.sha256 if worker_snapshot else "0" * 64,
                "failure_category": getattr(exception, "category", type(exception).__name__),
                "failure_stage": "POST_MARKER_FIXED_ACTION",
                "returncode": None, "leader_reaped": True,
                "process_group_gone": True, "partial_retained": True,
                "quarantined": authorization["action_id"] == "Q15-W",
                "completed_at_utc": utc_now(), "phase18_authority": False,
            }
            try:
                validate_with_schema(schema_validators["failure"], failure, "failure")
                _write_exclusive(directory_fd, failure_name, canonical(failure))
            except BaseException as retention:
                raise FixedActionExecutionError(
                    "FAILURE_RETENTION", f"primary={exception}; retention={retention}"
                ) from retention
        raise
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        if request_snapshot is not None:
            request_snapshot.close()
        if context_snapshot is not None:
            context_snapshot.close()
        if worker_snapshot is not None:
            worker_snapshot.close()
