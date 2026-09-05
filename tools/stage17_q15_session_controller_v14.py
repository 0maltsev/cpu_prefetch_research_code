#!/usr/bin/env python3
"""Real Q15 session-controller successor fixing a real diagnostic-loss
defect: the worker's own stderr/stdout is discarded, unread, whenever a
real Q15-W attempt fails.

`stage17_q15_session_controller_v10.py`'s own `execute_session` launches
the real worker (`cpu_prefetch_runner`) with `stdout=subprocess.PIPE,
stderr=subprocess.PIPE`, but no code path anywhere in `v10.py` ever reads
either stream -- both are only closed, unread, in `execute_session`'s own
`finally` block. `_write_session_failure`'s own record schema
(`cpu-prefetch-stage17-q15-session-failure/2`) has no field for worker
output either. A real, live Q15-W attempt on the real stand hit this for
real: the worker process exited with a real, nonzero exit code
(`Q15SessionError: Q15 session worker returned 1`), meaning `runner_
main.cpp`'s own outer exception handler had already printed a real
`"runner: FAIL: <message>"` diagnostic to the worker's own stderr -- but
because nothing ever read that pipe, the message was unrecoverable after
the fact, even with full stand access, confirmed by direct code reading
rather than continued log searching.

Fixes it by adding a best-effort, non-blocking tail capture of both
streams (`_capture_stream_tail`) at the same point in `execute_session`'s
own failure handling where the worker process is already confirmed
reaped (either by the `cleanup.returncode != 0` primary-path check, or
by the except-block's own forced cleanup/fallback-reap), and threading
the captured text into a new `stage17-q15-session-failure-v3.schema.json`
generation via two new nullable fields, `worker_stdout_tail`/
`worker_stderr_tail`, each capped at 8192 bytes of the stream's own tail
so a runaway worker can never bloat the failure record. Capture is
strictly best-effort and can never raise or block: diagnostic capture
must not risk masking or delaying the real failure it exists to explain.

Like `v12.py` (`execute_session` itself) and `v13.py` (`NSpgid`), this is
a full, targeted copy of `v10.py`'s own `execute_session`/`_write_
session_failure` rather than a monkeypatch, because the fix changes
function bodies, not just which already-built object a name resolves
to -- but the *wiring* follows the exact same "reassign the attribute on
the module that actually reads it" mechanism: `run_start` (defined in
`v2.py`) resolves `execute_session` as a bare name against `v2.py`'s own
module globals at call time, so this generation's own `execute_session`
is patched onto `_v2` directly, the same as every prior generation.
`v13.py` is imported as `predecessor` (not `v10.py` directly) purely to
pick up its own already-verified `NSpgid`/`supervisor` fix and
`phase_controller` propagation as an import-time side effect; `main`
delegates to `predecessor.main`, which is ultimately `v2.py`'s own
`main()`/`run_start()`/`run_continue()`, unchanged.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import time
from collections.abc import Callable
from typing import Any

import stage17_fixed_action_executor_v4 as action_executor
import stage17_hardware_recovery_v1 as hardware_recovery
import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_output_registry_v4 as output_registry
import stage17_phase_controller_v14 as phase_controller
import stage17_process_group_supervisor_v3 as supervisor
import stage17_q15_session_controller_v2 as _v2
import stage17_q15_session_controller_v13 as predecessor
import stage17_q15_session_controller_v10 as _v10


WAITING_NAME = _v10.WAITING_NAME
Q15_R_RESULT_NAME = _v10.Q15_R_RESULT_NAME
Q15_W_RESULT_NAME = _v10.Q15_W_RESULT_NAME
MAX_CONTROL_BYTES = _v10.MAX_CONTROL_BYTES
Q15_W_ACTION_SECONDS = _v10.Q15_W_ACTION_SECONDS

Q15SessionError = _v10.Q15SessionError
_fallback_reap = _v10._fallback_reap
_parse_prestate = _v10._parse_prestate
_verify_live_prestate = _v10._verify_live_prestate
_restore_live_prestate = _v10._restore_live_prestate
SessionOutcome = _v10.SessionOutcome
_canonical = _v10._canonical
_sha = _v10._sha
_context = _v10._context
_read_json_at = _v10._read_json_at
_write_quarantine = _v10._write_quarantine


def _capture_stream_tail(stream: Any, *, limit: int = 8192) -> str | None:
    """Best-effort, non-blocking tail capture of an already-exited
    worker's own output stream. Must never raise or block: diagnostic
    capture is not allowed to mask or delay the real failure it exists
    to explain."""
    if stream is None:
        return None
    try:
        descriptor = stream.fileno()
        os.set_blocking(descriptor, False)
        chunks: list[bytes] = []
        total = 0
        while total <= limit * 4:
            try:
                chunk = os.read(descriptor, 65536)
            except (BlockingIOError, OSError):
                break
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        data = b"".join(chunks)
        if not data:
            return None
        return data[-limit:].decode("utf-8", errors="replace")
    except Exception:
        return None


def _write_session_failure(
    *, directory_fd: int, q15_r: phase_controller.PreparedAction,
    q15_w: phase_controller.PreparedAction | None, stage: str,
    cleanup_error_occurred: bool,
    cause: BaseException, cleanup: Any, quarantine_sha256: str | None,
    supervisor_restore: list[dict[str, object]] | None,
    worker_stdout_tail: str | None, worker_stderr_tail: str | None,
) -> None:
    session_id = str(q15_r.request["action_inputs"]["session_id"])
    record = {
        "schema_version": "cpu-prefetch-stage17-q15-session-failure/3",
        "failure_id": session_id + ":failure",
        "session_id": session_id,
        "failure_stage": stage,
        "cleanup_error_occurred": cleanup_error_occurred,
        "failure_category": getattr(cause, "category", type(cause).__name__),
        "q15_r_attempt_id": q15_r.request["attempt_id"],
        "q15_w_attempt_id": q15_w.request["attempt_id"] if q15_w else None,
        "leader_reaped": bool(cleanup is None or cleanup.leader_reaped),
        "process_group_gone": bool(cleanup is None or cleanup.process_group_gone),
        "restoration_verified": supervisor_restore is not None,
        "supervisor_restore_readback": supervisor_restore,
        "quarantine_operation": {
            "performed": quarantine_sha256 is not None,
            "record_sha256": quarantine_sha256,
        },
        "worker_stdout_tail": worker_stdout_tail,
        "worker_stderr_tail": worker_stderr_tail,
        "partial_retained": True,
        "recorded_at_utc": action_executor._utc_now(),
        "phase18_authority": False,
    }
    schema_path = (
        q15_r.root / "config/schemas/stage17-q15-session-failure-v3.schema.json"
    )
    schema = json.loads(schema_path.read_bytes())
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(schema).iter_errors(record))
    if errors:
        raise Q15SessionError(
            f"Q15 session failure record rejected: {errors[0].message}"
        )
    action_executor.predecessor._write_exclusive(
        directory_fd, "stage17-q15-session-failure-v3.json", _canonical(record)
    )


def execute_session(
    *, q15_r: phase_controller.PreparedAction,
    wait_for_q15_w: Callable[[], phase_controller.PreparedAction],
    synthetic_test_only: bool = False,
) -> SessionOutcome:
    if q15_r.authorization["action_id"] != "Q15-R":
        raise Q15SessionError("session start requires Q15-R")
    root = q15_r.root
    output_root = pathlib.Path(
        q15_r.request["evidence_root_binding"]["absolute_path"]
    )
    directory_fd: int | None = None
    worker_snapshot = None
    request_snapshot = None
    context_snapshot = None
    worker_control: int | None = None
    controller_control: int | None = None
    lease = supervisor.SupervisorLease()
    process: subprocess.Popen[bytes] | None = None
    marker_created = False
    q15_w_marker_created = False
    cleanup = None
    primary: BaseException | None = None
    q15_w: phase_controller.PreparedAction | None = None
    q15_prestate: tuple[tuple[int, int], ...] | None = None
    started_ns = time.monotonic_ns()
    failure_stage = "Q15_R_PRESTATE"
    try:
        registry = output_registry.pin_registry(root)
        worker_snapshot = action_executor.predecessor._pin_worker(
            q15_r.worker_path, q15_r.runtime
        )
        request_snapshot = action_executor.predecessor._pin_generated(
            q15_r.request_bytes, "Q15_R_REQUEST_V4"
        )
        context_document = _context(q15_r, synthetic_test_only)
        action_executor._validate_schema(
            registry,
            "config/schemas/stage17-fixed-action-context-v4.schema.json",
            context_document,
            "Q15-R context",
        )
        context_snapshot = action_executor.predecessor._pin_generated(
            _canonical(context_document), "Q15_R_CONTEXT_V4"
        )
        directory_fd, root_identity = action_executor._componentwise_output_root(
            output_root, root, q15_r.request["evidence_root_binding"]
        )
        action_executor._verify_root_identity(directory_fd, root_identity)
        for action in ("q15_r", "q15_w"):
            for version in range(1, 5):
                if action_executor.predecessor._exists_at(
                    directory_fd, f"stage17-{action}-attempt-v{version}.json"
                ):
                    raise Q15SessionError("cross-version Q15 one-shot marker exists")
        initial = action_executor._parse_utc(action_executor._utc_now())
        issued = action_executor._parse_utc(q15_r.authorization["issued_at_utc"])
        expires = action_executor._parse_utc(q15_r.authorization["expires_at_utc"])
        if not issued <= initial < expires:
            raise Q15SessionError("Q15-R authority is future or expired")
        attempt = {
            "schema_version": "cpu-prefetch-stage17-phase-action-attempt/4",
            "attempt_id": q15_r.request["attempt_id"],
            "action_id": "Q15-R",
            "authorization_id": q15_r.authorization["authorization_id"],
            "authorization_sha256": _sha(q15_r.authorization_bytes),
            "request_sha256": _sha(q15_r.request_bytes),
            "runtime_sha256": q15_r.runtime["sha256"],
            "release_resolution_id": q15_r.release["source_resolution_id"],
            "release_resolution_sha256": q15_r.release["source_resolution_sha256"],
            "evidence_root_binding": q15_r.request["evidence_root_binding"],
            "started_at_utc": action_executor._utc_now(),
            "one_attempt": True,
            "retries": 0,
            "marker_durable": True,
            "phase18_authority": False,
        }
        action_executor._validate_schema(
            registry,
            "config/schemas/stage17-phase-action-attempt-v4.schema.json",
            attempt,
            "Q15-R attempt",
        )
        action_executor.predecessor._write_exclusive(
            directory_fd, "stage17-q15_r-attempt-v4.json", _canonical(attempt)
        )
        marker_created = True
        worker_control, controller_control = os.pipe2(os.O_CLOEXEC)
        current = action_executor._parse_utc(action_executor._utc_now())
        if current < initial or not issued <= current < expires:
            raise Q15SessionError("Q15-R authority failed at session spawn")
        lease.enter()
        process = subprocess.Popen(
            (
                worker_snapshot.locator,
                "--execute-stage17-q15-session-v1",
                "--q15-r-request-fd",
                str(request_snapshot.descriptor),
                "--q15-r-context-fd",
                str(context_snapshot.descriptor),
                "--q15-w-control-fd",
                str(worker_control),
                "--output-dir-fd",
                str(directory_fd),
                "--fixed-dispatch-end",
            ),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            close_fds=True,
            pass_fds=(
                request_snapshot.descriptor,
                context_snapshot.descriptor,
                worker_control,
                directory_fd,
            ),
            start_new_session=True,
            env=action_executor.FIXED_ENVIRONMENT,
        )
        os.close(worker_control)
        worker_control = None
        failure_stage = "Q15_R_WAIT"
        wait_deadline = time.monotonic_ns() + int(
            (expires - current).total_seconds() * 1_000_000_000
        )
        while not action_executor.predecessor._exists_at(directory_fd, WAITING_NAME):
            if time.monotonic_ns() >= wait_deadline:
                raise Q15SessionError("Q15-R session did not seal before expiry")
            exited = os.waitid(
                os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT
            )
            if exited is not None:
                raise Q15SessionError("Q15-R worker exited before sealed handoff")
            time.sleep(0.01)
        q15_r_result, q15_r_result_bytes = _read_json_at(
            directory_fd, Q15_R_RESULT_NAME
        )
        output_registry.validate_worker_result(
            registry=registry,
            directory_fd=directory_fd,
            result=q15_r_result,
            request=q15_r.request,
            authorization_sha256=_sha(q15_r.authorization_bytes),
            synthetic_test_only=synthetic_test_only,
        )
        q15_r_binding = next(
            item for item in q15_r_result["artifacts"]
            if item["role"] == "Q15_R_READ_ONLY_PRESTATE"
        )
        q15_r_output, _ = _read_json_at(
            directory_fd, q15_r_binding["file_name"]
        )
        q15_prestate = _parse_prestate(q15_r_output["prestate"])
        failure_stage = "Q15_W_ADMISSION"
        q15_w = wait_for_q15_w()
        if (
            q15_w.worker_path != q15_r.worker_path
            or q15_w.runtime != q15_r.runtime
            or q15_w.request["evidence_root_binding"]
            != q15_r.request["evidence_root_binding"]
            or q15_w.request["action_inputs"]["session_id"]
            != q15_r.request["action_inputs"]["session_id"]
            or q15_w.request["action_inputs"]["q15_r_result_sha256"]
            != _sha(q15_r_result_bytes)
        ):
            raise Q15SessionError("Q15-W runtime/session/Q15-R lineage drifted")
        q15_r_attempt_bytes = action_executor.predecessor._read_at(
            directory_fd, "stage17-q15_r-attempt-v4.json", 1024 * 1024
        )
        if (
            q15_w.request["action_inputs"]["q15_r_attempt_sha256"]
            != _sha(q15_r_attempt_bytes)
        ):
            raise Q15SessionError("Q15-W exact Q15-R attempt lineage drifted")
        q15_w_context = _context(q15_w, synthetic_test_only)
        action_executor._validate_schema(
            registry,
            "config/schemas/stage17-fixed-action-context-v4.schema.json",
            q15_w_context,
            "Q15-W context",
        )
        q15_w_now = action_executor._parse_utc(action_executor._utc_now())
        q15_w_issued = action_executor._parse_utc(
            q15_w.authorization["issued_at_utc"]
        )
        q15_w_expires = action_executor._parse_utc(
            q15_w.authorization["expires_at_utc"]
        )
        if not q15_w_issued <= q15_w_now < q15_w_expires:
            raise Q15SessionError("Q15-W authority is future or expired")
        q15_w_attempt = {
            "schema_version": "cpu-prefetch-stage17-phase-action-attempt/4",
            "attempt_id": q15_w.request["attempt_id"],
            "action_id": "Q15-W",
            "authorization_id": q15_w.authorization["authorization_id"],
            "authorization_sha256": _sha(q15_w.authorization_bytes),
            "request_sha256": _sha(q15_w.request_bytes),
            "runtime_sha256": q15_w.runtime["sha256"],
            "release_resolution_id": q15_w.release["source_resolution_id"],
            "release_resolution_sha256": q15_w.release["source_resolution_sha256"],
            "evidence_root_binding": q15_w.request["evidence_root_binding"],
            "started_at_utc": action_executor._utc_now(),
            "one_attempt": True,
            "retries": 0,
            "marker_durable": True,
            "phase18_authority": False,
        }
        action_executor._validate_schema(
            registry,
            "config/schemas/stage17-phase-action-attempt-v4.schema.json",
            q15_w_attempt,
            "Q15-W attempt",
        )
        action_executor.predecessor._write_exclusive(
            directory_fd, "stage17-q15_w-attempt-v4.json",
            _canonical(q15_w_attempt),
        )
        q15_w_marker_created = True
        q15_w_guard = action_executor._parse_utc(action_executor._utc_now())
        if q15_w_guard < q15_w_now or not q15_w_issued <= q15_w_guard < q15_w_expires:
            raise Q15SessionError("Q15-W authority failed at control handoff")
        assert controller_control is not None
        for packet in (q15_w.request_bytes, _canonical(q15_w_context)):
            if not packet or len(packet) > MAX_CONTROL_BYTES:
                raise Q15SessionError("Q15-W sealed control packet is oversized")
            framed = len(packet).to_bytes(4, "big") + packet
            offset = 0
            while offset != len(framed):
                written = os.write(controller_control, framed[offset:])
                if written <= 0:
                    raise Q15SessionError("Q15-W sealed control pipe closed")
                offset += written
        failure_stage = "Q15_W_MUTATION"
        assert process is not None and lease.identity_model is not None
        action_deadline = min(
            time.monotonic_ns() + Q15_W_ACTION_SECONDS * 1_000_000_000,
            time.monotonic_ns()
            + int((q15_w_expires - q15_w_guard).total_seconds() * 1_000_000_000),
        )
        cleanup = supervisor.cleanup_process_group(
            process,
            force_stop=False,
            leader_wait_deadline_ns=action_deadline,
            global_deadline_ns=action_deadline,
            identity_model=lease.identity_model,
        )
        if cleanup.returncode != 0:
            raise Q15SessionError(f"Q15 session worker returned {cleanup.returncode}")
        failure_stage = "Q15_W_RESTORE"
        q15_w_result, q15_w_result_bytes = _read_json_at(
            directory_fd, Q15_W_RESULT_NAME
        )
        output_registry.validate_worker_result(
            registry=registry,
            directory_fd=directory_fd,
            result=q15_w_result,
            request=q15_w.request,
            authorization_sha256=_sha(q15_w.authorization_bytes),
            synthetic_test_only=synthetic_test_only,
        )
        if not q15_w_result["restoration_verified"] or q15_w_result["quarantined"]:
            raise Q15SessionError("Q15-W did not prove restoration")
        assert q15_prestate is not None
        if synthetic_test_only:
            hardware_recovery.verify(q15_prestate, synthetic=True)
        else:
            _verify_live_prestate(q15_prestate)
        completion = {
            "schema_version": "cpu-prefetch-stage17-phase-action-completion/4",
            "completion_id": q15_w.request["attempt_id"] + ":completion",
            "attempt_id": q15_w.request["attempt_id"],
            "action_id": "Q15-W",
            "authorization_sha256": _sha(q15_w.authorization_bytes),
            "request_sha256": _sha(q15_w.request_bytes),
            "runtime_sha256": q15_w.runtime["sha256"],
            "result": {
                "file_name": Q15_W_RESULT_NAME,
                "size_bytes": len(q15_w_result_bytes),
                "sha256": _sha(q15_w_result_bytes),
            },
            "artifact_bindings": [
                {
                    "file_name": item["file_name"],
                    "size_bytes": item["size_bytes"],
                    "sha256": item["sha256"],
                }
                for item in q15_w_result["artifacts"]
            ],
            "leader_reaped": cleanup.leader_reaped,
            "process_group_gone": cleanup.process_group_gone,
            "restoration_verified": True,
            "live_restoration_readback": (
                hardware_recovery.verify(q15_prestate, synthetic=True)
                if synthetic_test_only
                else _verify_live_prestate(q15_prestate)
            ),
            "quarantined": False,
            "completed_at_utc": action_executor._utc_now(),
            "phase18_authority": False,
        }
        action_executor._validate_schema(
            registry,
            "config/schemas/stage17-phase-action-completion-v4.schema.json",
            completion,
            "Q15-W completion",
        )
        completion_name = "stage17-q15_w-completion-v4.json"
        action_executor.predecessor._write_exclusive(
            directory_fd, completion_name, _canonical(completion)
        )
        return SessionOutcome(
            q15_r_result=q15_r_result,
            q15_w_result=q15_w_result,
            completion_path=output_root / completion_name,
        )
    except BaseException as exception:
        primary = exception
        cleanup_error = None
        if process is not None and cleanup is None:
            try:
                if lease.identity_model is None:
                    raise Q15SessionError("Q15 supervisor identity model is absent")
                cleanup_deadline = time.monotonic_ns() + 2_000_000_000
                cleanup = supervisor.cleanup_process_group(
                    process,
                    force_stop=True,
                    leader_wait_deadline_ns=cleanup_deadline,
                    global_deadline_ns=cleanup_deadline,
                    identity_model=lease.identity_model,
                )
            except BaseException as supervisor_exception:
                cleanup_error = supervisor_exception
                cleanup = _fallback_reap(process)
        worker_stdout_tail = (
            _capture_stream_tail(process.stdout) if process is not None else None
        )
        worker_stderr_tail = (
            _capture_stream_tail(process.stderr) if process is not None else None
        )
        quarantine_sha256 = None
        supervisor_restore = None
        if q15_w_marker_created and directory_fd is not None:
            try:
                if q15_prestate is None:
                    raise Q15SessionError(
                        "Q15-R prestate unavailable to supervisor"
                    )
                supervisor_restore = (
                    hardware_recovery.restore(q15_prestate, synthetic=True)
                    if synthetic_test_only
                    else _restore_live_prestate(q15_prestate)
                )
            except BaseException as restoration:
                quarantine_sha256 = _write_quarantine(
                    directory_fd,
                    q15_w.request["attempt_id"] if q15_w
                    else q15_r.request["attempt_id"],
                    restoration,
                )
        if marker_created and directory_fd is not None:
            try:
                _write_session_failure(
                    directory_fd=directory_fd, q15_r=q15_r, q15_w=q15_w,
                    stage=failure_stage,
                    cleanup_error_occurred=cleanup_error is not None,
                    cause=exception, cleanup=cleanup,
                    quarantine_sha256=quarantine_sha256,
                    supervisor_restore=supervisor_restore,
                    worker_stdout_tail=worker_stdout_tail,
                    worker_stderr_tail=worker_stderr_tail,
                )
            except BaseException as retention:
                raise Q15SessionError(
                    f"primary={exception}; failure-retention={retention}"
                ) from retention
        raise
    finally:
        if controller_control is not None:
            os.close(controller_control)
        if worker_control is not None:
            os.close(worker_control)
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        lease.close(suppress=primary is not None)
        snapshot_broker.close_snapshots(request_snapshot, context_snapshot)
        if worker_snapshot is not None:
            worker_snapshot.close()
        if directory_fd is not None:
            os.close(directory_fd)


_v2.execute_session = execute_session

main = predecessor.main


if __name__ == "__main__":
    raise SystemExit(main())
