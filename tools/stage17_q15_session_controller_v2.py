#!/usr/bin/env python3
"""Authority-verifying phase-spanning Q15-R/Q15-W controller.

The production CLI keeps this process in the foreground while the compiled
runner retains one private anonymous probe mapping.  A second invocation can
submit only repository-defined Q15-W authorization/request locators through a
credential-checked local SOCK_SEQPACKET endpoint.  No command, argv, stdin,
MSR number, mask, probe outcome, or backend is caller selectable.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import socket
import signal
import stat
import struct
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import stage17_fixed_action_executor_v4 as action_executor
import stage17_hardware_recovery_v1 as hardware_recovery
import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_output_registry_v4 as output_registry
import stage17_phase_controller_v4 as phase_controller
import stage17_phase_controller_v2 as controller_support
import stage17_process_group_supervisor_v2 as supervisor


WAITING_NAME = "stage17-q15-session-waiting-v1.json"
Q15_R_RESULT_NAME = "stage17-q15-r-result-v4.json"
Q15_W_RESULT_NAME = "stage17-q15-w-result-v4.json"
CONTROL_PROTOCOL = "STAGE17-Q15-SEPARATE-AUTHORITY-CONTROL-v1"
MAX_CONTROL_BYTES = 64 * 1024
Q15_W_ACTION_SECONDS = 180
Q15_MSR = 0x1A4
Q15_CPUS = (0, 1, 26)


class Q15SessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class _FallbackCleanup:
    returncode: int
    leader_reaped: bool
    process_group_gone: bool


def _fallback_reap(process: subprocess.Popen[bytes]) -> _FallbackCleanup:
    """Last-resort fixed-PGID barrier when procfs supervision itself faults."""
    pgid = process.pid
    for selected_signal, seconds in ((signal.SIGTERM, 0.5),
                                     (signal.SIGKILL, 2.0)):
        try:
            os.killpg(pgid, selected_signal)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                process.wait(timeout=0.02)
            except subprocess.TimeoutExpired:
                pass
            try:
                os.killpg(pgid, 0)
            except ProcessLookupError:
                return _FallbackCleanup(
                    process.returncode if process.returncode is not None else -1,
                    process.returncode is not None, True,
                )
            time.sleep(0.005)
    raise Q15SessionError(
        "Q15 worker process group could not be made quiescent"
    )


def _parse_prestate(values: object) -> tuple[tuple[int, int], ...]:
    if not isinstance(values, list) or len(values) != len(Q15_CPUS):
        raise Q15SessionError("Q15-R complete prestate is absent")
    parsed: list[tuple[int, int]] = []
    for expected_cpu, item in zip(Q15_CPUS, values, strict=True):
        if (not isinstance(item, dict) or item.get("cpu") != expected_cpu
                or not isinstance(item.get("complete_value_hex"), str)
                or len(item["complete_value_hex"]) != 16):
            raise Q15SessionError("Q15-R complete prestate is malformed")
        try:
            value = int(item["complete_value_hex"], 16)
        except ValueError as exception:
            raise Q15SessionError("Q15-R complete prestate is malformed") from exception
        parsed.append((expected_cpu, value))
    return tuple(parsed)


def _msr_read(cpu: int) -> int:
    descriptor = os.open(
        f"/dev/cpu/{cpu}/msr",
        os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        payload = os.pread(descriptor, 8, Q15_MSR)
        if len(payload) != 8:
            raise Q15SessionError("fixed MSR read was incomplete")
        return struct.unpack("<Q", payload)[0]
    finally:
        os.close(descriptor)


def _msr_restore(cpu: int, value: int) -> int:
    descriptor = os.open(
        f"/dev/cpu/{cpu}/msr",
        os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
    )
    try:
        payload = struct.pack("<Q", value)
        if os.pwrite(descriptor, payload, Q15_MSR) != len(payload):
            raise Q15SessionError("fixed MSR restore write was incomplete")
        observed = os.pread(descriptor, 8, Q15_MSR)
        if len(observed) != 8:
            raise Q15SessionError("fixed MSR restore readback was incomplete")
        return struct.unpack("<Q", observed)[0]
    finally:
        os.close(descriptor)


def _verify_live_prestate(prestate: tuple[tuple[int, int], ...]) \
        -> list[dict[str, object]]:
    result = []
    for cpu, expected in prestate:
        observed = _msr_read(cpu)
        result.append({
            "cpu": cpu,
            "expected_hex": f"{expected:016x}",
            "observed_hex": f"{observed:016x}",
            "matches": observed == expected,
        })
    if not all(item["matches"] for item in result):
        raise Q15SessionError("live MSR state differs from Q15-R prestate")
    return result


def _restore_live_prestate(prestate: tuple[tuple[int, int], ...]) \
        -> list[dict[str, object]]:
    result = []
    failures: list[str] = []
    for cpu, expected in reversed(prestate):
        try:
            observed = _msr_restore(cpu, expected)
            matches = observed == expected
        except BaseException as exception:
            observed = None
            matches = False
            failures.append(f"cpu={cpu}:{type(exception).__name__}")
        result.append({
            "cpu": cpu,
            "requested_hex": f"{expected:016x}",
            "observed_hex": f"{observed:016x}" if observed is not None else None,
            "matches": matches,
        })
    if failures or not all(item["matches"] for item in result):
        raise Q15SessionError(
            "supervisor MSR restore/readback failed: " + ",".join(failures)
        )
    return result


@dataclass(frozen=True)
class SessionOutcome:
    q15_r_result: dict[str, Any]
    q15_w_result: dict[str, Any]
    completion_path: pathlib.Path


def _canonical(value: object) -> bytes:
    return output_registry.canonical(value)


def _sha(value: bytes) -> str:
    return output_registry.sha256_bytes(value)


def _context(prepared: phase_controller.PreparedAction,
             synthetic_test_only: bool = False) -> dict[str, Any]:
    return {
        "schema_version": "cpu-prefetch-stage17-fixed-action-context/4",
        "authorization_id": prepared.authorization["authorization_id"],
        "authorization_sha256": _sha(prepared.authorization_bytes),
        "request_id": prepared.request["request_id"],
        "request_sha256": _sha(prepared.request_bytes),
        "session_id": prepared.request["session_id"],
        "attempt_id": prepared.request["attempt_id"],
        "action_id": prepared.authorization["action_id"],
        "fixed_action_definition_sha256": prepared.registry.plan_sha256,
        "runtime_sha256": prepared.runtime["sha256"],
        "release_sha256": prepared.release["worker_sha256"],
        "predecessor_sha256s": [
            item["sha256"] for item in prepared.request["predecessor_resolutions"]
        ],
        "issued_at_epoch_seconds": int(action_executor._parse_utc(
            prepared.authorization["issued_at_utc"]
        ).timestamp()),
        "expires_at_epoch_seconds": int(action_executor._parse_utc(
            prepared.authorization["expires_at_utc"]
        ).timestamp()),
        "per_run_deadline_seconds": 180,
        "synthetic_test_only": synthetic_test_only,
        "phase18_authority": False,
    }


def _read_json_at(directory_fd: int, name: str) -> tuple[dict[str, Any], bytes]:
    payload = action_executor.predecessor._read_at(
        directory_fd, name, 64 * 1024 * 1024
    )
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise Q15SessionError(f"{name} is not a JSON object")
    return document, payload


def _peer_uid(connection: socket.socket) -> int:
    payload = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    _, uid, _ = struct.unpack("3i", payload)
    return uid


def _control_endpoint(attempt_id: str) -> str:
    token = _sha(attempt_id.encode("utf-8"))[:32]
    return "\0cpu-prefetch-stage17-q15-" + token


def _receive_control(connection: socket.socket) -> dict[str, str]:
    payload = connection.recv(MAX_CONTROL_BYTES + 1)
    if not payload or len(payload) > MAX_CONTROL_BYTES:
        raise Q15SessionError("Q15-W control envelope is absent or oversized")
    value = json.loads(payload)
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "journal",
            "journal_directory",
            "operational_evidence_root",
            "authorization",
            "signature",
            "pilot_archive",
            "pilot_sidecar",
        }
        or value["schema_version"] != CONTROL_PROTOCOL
        or any(
            not isinstance(value[name], str) or not value[name]
            for name in (
                "journal",
                "journal_directory",
                "operational_evidence_root",
                "authorization",
                "signature",
            )
        )
        or any(
            value[name] is not None and not isinstance(value[name], str)
            for name in ("pilot_archive", "pilot_sidecar")
        )
    ):
        raise Q15SessionError("Q15-W control envelope contract drifted")
    return value


def _prepare_q15_w_from_control(
    root: pathlib.Path, connection: socket.socket,
) -> phase_controller.PreparedAction:
    if _peer_uid(connection) != os.geteuid():
        raise Q15SessionError("Q15-W control peer UID differs from controller")
    value = _receive_control(connection)
    prepared = phase_controller.prepare_action(
        repository_root=root,
        journal=pathlib.Path(value["journal"]),
        journal_directory=pathlib.Path(value["journal_directory"]),
        operational_evidence_root=pathlib.Path(
            value["operational_evidence_root"]
        ),
        authorization_path=pathlib.Path(value["authorization"]),
        signature_path=pathlib.Path(value["signature"]),
        pilot_archive=(
            pathlib.Path(value["pilot_archive"])
            if value["pilot_archive"] is not None
            else None
        ),
        pilot_sidecar=(
            pathlib.Path(value["pilot_sidecar"])
            if value["pilot_sidecar"] is not None
            else None
        ),
        synthetic_test_only=False,
    )
    if prepared.authorization["action_id"] != "Q15-W":
        raise Q15SessionError("control continuation is not exact Q15-W")
    return prepared


def _write_quarantine(
    directory_fd: int, attempt_id: str, cause: BaseException,
) -> str:
    if action_executor.predecessor._exists_at(
        directory_fd, "stage17-stand-quarantine-v1.json"
    ):
        payload = action_executor.predecessor._read_at(
            directory_fd, "stage17-stand-quarantine-v1.json", 1024 * 1024
        )
        return _sha(payload)
    record = {
        "schema_version": "cpu-prefetch-stage17-stand-quarantine/1",
        "quarantine_id": attempt_id + ":quarantine",
        "action_id": "Q15-W",
        "attempt_id": attempt_id,
        "cause_category": getattr(cause, "category", type(cause).__name__),
        "created_at_utc": action_executor._utc_now(),
        "blocks_all_stage17_actions": True,
        "manual_platform_recovery_required": True,
        "phase18_authority": False,
    }
    return action_executor.predecessor._write_exclusive(
        directory_fd, "stage17-stand-quarantine-v1.json", _canonical(record)
    )


def _write_session_failure(
    *, directory_fd: int, q15_r: phase_controller.PreparedAction,
    q15_w: phase_controller.PreparedAction | None, stage: str,
    cause: BaseException, cleanup: Any, quarantine_sha256: str | None,
    supervisor_restore: list[dict[str, object]] | None,
) -> None:
    session_id = str(q15_r.request["action_inputs"]["session_id"])
    record = {
        "schema_version": "cpu-prefetch-stage17-q15-session-failure/1",
        "failure_id": session_id + ":failure",
        "session_id": session_id,
        "failure_stage": stage,
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
        "partial_retained": True,
        "recorded_at_utc": action_executor._utc_now(),
        "phase18_authority": False,
    }
    schema_path = (
        q15_r.root / "config/schemas/stage17-q15-session-failure-v1.schema.json"
    )
    schema = json.loads(schema_path.read_bytes())
    from jsonschema import Draft202012Validator
    errors = list(Draft202012Validator(schema).iter_errors(record))
    if errors:
        raise Q15SessionError(
            f"Q15 session failure record rejected: {errors[0].message}"
        )
    action_executor.predecessor._write_exclusive(
        directory_fd, "stage17-q15-session-failure-v1.json", _canonical(record)
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
                    stage=(failure_stage if cleanup_error is None
                           else failure_stage + ":SUPERVISOR_FALLBACK"),
                    cause=exception, cleanup=cleanup,
                    quarantine_sha256=quarantine_sha256,
                    supervisor_restore=supervisor_restore,
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


def run_start(arguments: argparse.Namespace) -> int:
    prepared = phase_controller.prepare_action(
        repository_root=arguments.repository_root,
        journal=arguments.journal,
        journal_directory=arguments.journal_directory,
        operational_evidence_root=arguments.operational_evidence_root,
        authorization_path=arguments.authorization,
        signature_path=arguments.signature,
        pilot_archive=arguments.pilot_archive,
        pilot_sidecar=arguments.pilot_sidecar,
        synthetic_test_only=False,
    )
    endpoint = _control_endpoint(prepared.request["attempt_id"])
    listener = socket.socket(
        socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC
    )
    listener.bind(endpoint)
    listener.listen(1)
    expiry = controller_support._parse_utc(
        prepared.authorization["expires_at_utc"]
    )
    remaining = (expiry - controller_support._parse_utc(
        controller_support._now()
    )).total_seconds()
    if remaining <= 0:
        listener.close()
        raise Q15SessionError("Q15-R session authority expired before listen")
    listener.settimeout(remaining)

    def wait_for_q15_w() -> phase_controller.PreparedAction:
        print(
            "stage17-q15-session: H0_SEALED_WAITING_FOR_Q15_W "
            f"control_id={endpoint[1:]}",
            flush=True,
        )
        connection, _ = listener.accept()
        with connection:
            return _prepare_q15_w_from_control(
                arguments.repository_root.resolve(), connection
            )

    try:
        execute_session(q15_r=prepared, wait_for_q15_w=wait_for_q15_w)
    finally:
        listener.close()
    print("stage17-q15-session: PASS state=Q15_W_RESTORED_COMPLETE")
    return 0


def run_continue(arguments: argparse.Namespace) -> int:
    value = {
        "schema_version": CONTROL_PROTOCOL,
        "journal": str(arguments.journal),
        "journal_directory": str(arguments.journal_directory),
        "operational_evidence_root": str(arguments.operational_evidence_root),
        "authorization": str(arguments.authorization),
        "signature": str(arguments.signature),
        "pilot_archive": str(arguments.pilot_archive) if arguments.pilot_archive else None,
        "pilot_sidecar": str(arguments.pilot_sidecar) if arguments.pilot_sidecar else None,
    }
    endpoint = "\0" + arguments.control_id
    client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    try:
        client.connect(endpoint)
        client.send(_canonical(value))
    finally:
        client.close()
    print("stage17-q15-session: PASS continuation=SUBMITTED authority=NOT_EXPANDED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start", action="store_true")
    mode.add_argument("--continue-q15-w", action="store_true")
    parser.add_argument("--repository-root", type=pathlib.Path)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--operational-evidence-root", type=pathlib.Path,
                        required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--signature", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    parser.add_argument("--control-id")
    arguments = parser.parse_args()
    try:
        if arguments.start:
            if arguments.repository_root is None or arguments.control_id is not None:
                raise Q15SessionError("start requires repository root and no control id")
            return run_start(arguments)
        if arguments.control_id is None or arguments.repository_root is not None:
            raise Q15SessionError("continuation requires control id only")
        return run_continue(arguments)
    except BaseException as exception:
        print(f"stage17-q15-session: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
