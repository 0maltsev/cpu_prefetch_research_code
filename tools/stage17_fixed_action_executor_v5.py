#!/usr/bin/env python3
"""Stage 17 fixed-action execution v5 -- ADR-0131 kernel-thread tolerance,
extended to the fixed-action worker's own process-group cleanup.

ADR-0131 fixed `_identity_at`'s crash on a real host's kernel threads
(`SupervisorError("empty or nonpositive NSpgid")`, raised because a kernel
thread structurally reports `NSpgid: 0`) by adding `stage17_process_group_
supervisor_v3.py` and cascading the import to the read-only-preflight chain
(`_v14.py` -> `_v15.py`) and the Q15 session controller (`_v13.py` ->
`_v14.py`). It never reached this file: `stage17_fixed_action_executor_v4.
py` still imports `stage17_process_group_supervisor_v2` directly, because
at the time ADR-0131 was written this fixed-action path had never yet
executed against a real host's `/proc` (every prior exercise ran inside a
private PID namespace with no visible kernel threads).

The first real, live Q16a execution (standv2-20, 708 real hardware
captures, journal at `/home/omaltsev/stage17-owner-evidence/stage17-
operational-evidence-standv2-20/`) hit exactly this defect: the real
capture campaign completed in full (`Q16A_CAPTURE_COMPLETE`, all 1417
expected artifacts present, hardware restoration verified via a real MSR
readback matching baseline on CPUs 0/1/26) but the wrapper reported
`PROCESS_SUPERVISOR_FALLBACK: empty or nonpositive NSpgid`. Root-caused by
direct code tracing, not assumed: `cleanup_process_group` (`stage17_
process_group_supervisor_v2.py:455`) calls `identity_model.identity_for_
local_pid(leader_pid)`, which walks every PID under `/proc` calling `self.
_identity_at(...)` with **no retry wrapping** (unlike every other `/proc`
scan in that function, which is deliberately retry-wrapped because a
procfs read can be transient). With the unfixed `v2` model this call is
guaranteed, not merely likely, to hit the first kernel thread it
encounters on any real host and raise immediately. This is deterministic,
not a race: any retry of Q16a against `v4` unchanged would fail the same
way every time.

Because Python resolves a function's free variables against the module
that *defines* it, not the module that imports it (the same lesson ADR-
0126 and ADR-0131 already recorded), fixing this requires more than
switching one import line: `_run_worker` and `execute_fixed_action` are
both defined here in `v4`'s own body and must be redefined -- copied
verbatim except for the one import they close over -- rather than merely
re-exported, or they would keep resolving `process_supervisor`/`_run_
worker` against `v4`'s own (unfixed) globals no matter what a successor
imports. Every other name below (`ExecutionOutcome`, `_fallback_reap`,
`canonical`, `sha256`, the schema/quarantine/output-root helpers) does not
reference `process_supervisor` and is re-exported unchanged.

`FixedActionExecutionError` here subclasses `v4`'s own (which subclasses
`v2`'s), preserving `isinstance` compatibility for any caller still
checking against an older class in the chain, exactly as `v4` did relative
to `v2`.
"""

from __future__ import annotations

import os
import pathlib
import selectors
import subprocess
import time
from typing import Any

import stage17_fixed_action_executor_v2 as predecessor
import stage17_fixed_action_executor_v4 as _v4
import stage17_hardware_recovery_v1 as hardware_recovery
import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_output_registry_v4 as output_registry
import stage17_process_group_supervisor_v3 as process_supervisor


RESULT_NAME = _v4.RESULT_NAME
GLOBAL_WALL_SECONDS = _v4.GLOBAL_WALL_SECONDS
FIXED_ENVIRONMENT = _v4.FIXED_ENVIRONMENT


class FixedActionExecutionError(_v4.FixedActionExecutionError):
    pass


ExecutionOutcome = _v4.ExecutionOutcome
_fallback_reap = _v4._fallback_reap
canonical = _v4.canonical
sha256 = _v4.sha256
_utc_now = _v4._utc_now
_parse_utc = _v4._parse_utc
_componentwise_output_root = _v4._componentwise_output_root
_verify_root_identity = _v4._verify_root_identity
_read_json_control = _v4._read_json_control
_validate_schema = _v4._validate_schema
_quarantine = _v4._quarantine
_quarantine_present = _v4._quarantine_present


def _run_worker(
    argv: tuple[str, ...], pass_fds: tuple[int, ...], *,
    global_deadline_ns: int, authority_guard: Any,
) -> predecessor.TransportOutcome:
    """Own one child family until a normal or fallback quiescence proof."""
    selector = selectors.DefaultSelector()
    lease = process_supervisor.SupervisorLease()
    process: subprocess.Popen[bytes] | None = None
    output = {"stdout": bytearray(), "stderr": bytearray()}
    streams: dict[int, tuple[str, Any]] = {}
    primary: BaseException | None = None
    timed_out = False
    cleanup = None
    cleanup_error: BaseException | None = None
    lease.enter()
    try:
        try:
            authority_guard()
            process = subprocess.Popen(
                list(argv), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=False, close_fds=True,
                pass_fds=pass_fds, start_new_session=True,
                env=FIXED_ENVIRONMENT,
            )
        except BaseException as exception:
            primary = exception
        try:
            if process is None:
                raise primary if primary is not None else FixedActionExecutionError(
                    "WORKER_START", "fixed worker did not start"
                )
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
                    if (len(output["stdout"]) + len(output["stderr"])
                            + len(chunk) > predecessor.MAX_OUTPUT_BYTES):
                        raise FixedActionExecutionError(
                            "WORKER_OUTPUT_LIMIT",
                            "fixed worker output exceeded the fixed bound",
                        )
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
            if process is not None:
                try:
                    if lease.identity_model is None:
                        raise FixedActionExecutionError(
                            "PROCESS_CLEANUP", "supervisor identity model is absent"
                        )
                    cleanup = process_supervisor.cleanup_process_group(
                        process, force_stop=primary is not None or timed_out,
                        leader_wait_deadline_ns=min(
                            time.monotonic_ns() + 2_000_000_000,
                            global_deadline_ns,
                        ),
                        global_deadline_ns=global_deadline_ns,
                        identity_model=lease.identity_model,
                    )
                except BaseException as exception:
                    cleanup_error = exception
                    cleanup = _fallback_reap(process)
    finally:
        lease.close(suppress=(primary is not None or cleanup_error is not None))
    if process is None:
        failure = FixedActionExecutionError(
            "WORKER_START", f"fixed worker did not start: {primary}"
        )
        failure.cleanup_proof = predecessor.TransportOutcome(
            -1, b"", b"", True, True, "NO_PROCESS_CREATED"
        )
        raise failure from primary
    if (cleanup is None or not cleanup.leader_reaped
            or not cleanup.process_group_gone):
        failure = FixedActionExecutionError(
            "PROCESS_CLEANUP", "fixed worker family is not quiescent"
        )
        if cleanup is not None:
            failure.cleanup_proof = cleanup
        raise failure
    if cleanup_error is not None:
        failure = FixedActionExecutionError(
            "PROCESS_SUPERVISOR_FALLBACK",
            f"primary supervisor failed after fallback cleanup: {cleanup_error}",
        )
        failure.cleanup_proof = cleanup
        raise failure from cleanup_error
    if primary is not None:
        failure = FixedActionExecutionError("WORKER_RUNTIME", str(primary))
        failure.cleanup_proof = cleanup
        raise failure from primary
    if timed_out:
        failure = FixedActionExecutionError(
            "WORKER_TIMEOUT", "fixed worker exceeded the common wall deadline"
        )
        failure.cleanup_proof = cleanup
        raise failure
    if cleanup.descendants_detected_after_leader_exit:
        failure = FixedActionExecutionError(
            "WORKER_DESCENDANT", "fixed worker left a descendant"
        )
        failure.cleanup_proof = cleanup
        raise failure
    return predecessor.TransportOutcome(
        cleanup.returncode, bytes(output["stdout"]), bytes(output["stderr"]),
        cleanup.leader_reaped, cleanup.process_group_gone,
        cleanup.terminal_cleanup_outcome,
    )


def execute_fixed_action(
    *, repository_root: pathlib.Path, authorization: dict[str, Any],
    authorization_bytes: bytes, request: dict[str, Any], request_bytes: bytes,
    worker_binding: dict[str, Any], worker_path: pathlib.Path,
    release_binding: dict[str, Any], output_root: pathlib.Path,
    synthetic_test_only: bool = False,
) -> ExecutionOutcome:
    root = repository_root.resolve()
    initial_utc_text = _utc_now()
    initial_utc = _parse_utc(initial_utc_text)
    action = authorization["action_id"]
    deadline_policy = authorization["deadline_policy"]
    if action == "STAGE17-BLINDED-PILOT":
        global_wall_seconds = deadline_policy["session_max_wall_seconds"]
        if (deadline_policy["mode"] != "DURABLE_PILOT_SESSION"
                or not isinstance(global_wall_seconds, int)
                or global_wall_seconds <= GLOBAL_WALL_SECONDS):
            raise FixedActionExecutionError(
                "PILOT_SESSION_DEADLINE",
                "pilot requires its frozen bounded durable-session deadline",
            )
    else:
        if (deadline_policy["mode"] != "ONE_SHOT_ACTION"
                or deadline_policy["session_max_wall_seconds"] is not None):
            raise FixedActionExecutionError(
                "ACTION_DEADLINE", "one-shot action deadline contract drifted"
            )
        global_wall_seconds = GLOBAL_WALL_SECONDS
    started_ns = time.monotonic_ns()
    global_deadline_ns = started_ns + global_wall_seconds * 1_000_000_000
    token = action.lower().replace("-", "_")
    marker_name = f"stage17-{token}-attempt-v4.json"
    failure_name = f"stage17-{token}-failure-v4.json"
    completion_name = f"stage17-{token}-completion-v4.json"
    worker_snapshot: predecessor.WorkerSnapshot | None = None
    request_snapshot: snapshot_broker.ParentSnapshot | None = None
    context_snapshot: snapshot_broker.ParentSnapshot | None = None
    directory_fd: int | None = None
    root_identity: tuple[int, int] | None = None
    marker_created = False
    attempt: dict[str, Any] | None = None
    schemas: output_registry.PinnedOutputRegistry | None = None
    transport: predecessor.TransportOutcome | None = None
    worker_boundary_entered = False
    hardware_prestate: tuple[tuple[int, int], ...] | None = None
    try:
        # Every schema, plan, executable and request byte needed after the marker
        # is loaded/pinned before the final authority sample.
        schemas = output_registry.pin_registry(root)
        if authorization["fixed_action_definition_sha256"] != schemas.plan_sha256:
            raise FixedActionExecutionError(
                "ACTION_PLAN", "fixed action definition bytes drifted"
            )
        definition = schemas.action(action)
        try:
            hardware_prestate = hardware_recovery.request_prestate(action, request)
        except hardware_recovery.HardwareRecoveryError as exception:
            raise FixedActionExecutionError(
                "HARDWARE_PRESTATE", str(exception)
            ) from exception
        if bool(definition["requires_restoration"]) != (
                hardware_prestate is not None):
            raise FixedActionExecutionError(
                "HARDWARE_PRESTATE",
                "action restoration contract and request prestate differ",
            )
        worker_snapshot = predecessor._pin_worker(worker_path, worker_binding)
        request_snapshot = predecessor._pin_generated(request_bytes, "FIXED_ACTION_REQUEST_V4")
        snapshot_broker.verify_snapshot(request_snapshot)
        if os.pread(request_snapshot.descriptor, len(request_bytes) + 1, 0) != request_bytes:
            raise FixedActionExecutionError("REQUEST_SNAPSHOT", "request snapshot bytes drifted")
        predecessor_hashes = [item["sha256"] for item in request["predecessor_resolutions"]]
        context = {
            "schema_version": "cpu-prefetch-stage17-fixed-action-context/4",
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": sha256(authorization_bytes),
            "request_id": request["request_id"],
            "request_sha256": sha256(request_bytes),
            "session_id": request["session_id"],
            "attempt_id": request["attempt_id"], "action_id": action,
            "fixed_action_definition_sha256": schemas.plan_sha256,
            "runtime_sha256": worker_snapshot.sha256,
            "release_sha256": release_binding["worker_sha256"],
            "predecessor_sha256s": predecessor_hashes,
            "issued_at_epoch_seconds": int(_parse_utc(
                authorization["issued_at_utc"]
            ).timestamp()),
            "expires_at_epoch_seconds": int(_parse_utc(
                authorization["expires_at_utc"]
            ).timestamp()),
            "per_run_deadline_seconds": 180,
            "synthetic_test_only": synthetic_test_only,
            "phase18_authority": False,
        }
        _validate_schema(
            schemas, "config/schemas/stage17-fixed-action-context-v4.schema.json",
            context, "worker context",
        )
        context_snapshot = predecessor._pin_generated(
            canonical(context), "FIXED_ACTION_CONTEXT_V4"
        )
        directory_fd, root_identity = _componentwise_output_root(
            output_root, root, request["evidence_root_binding"]
        )
        if authorization["evidence_root_binding"] != request["evidence_root_binding"]:
            raise FixedActionExecutionError(
                "OUTPUT_ROOT", "authorization/request evidence-root binding differs"
            )
        if _quarantine_present(directory_fd):
            raise FixedActionExecutionError(
                "QUARANTINED", "stand is quarantined from a prior failed mutation"
            )
        for version in range(1, 5):
            if predecessor._exists_at(
                directory_fd, f"stage17-{token}-attempt-v{version}.json"
            ):
                raise FixedActionExecutionError(
                    "REPLAY", "a predecessor/current one-shot marker exists"
                )
        if any(predecessor._exists_at(directory_fd, name) for name in (
            failure_name, completion_name, RESULT_NAME,
        )):
            raise FixedActionExecutionError("REPLAY", "terminal/current result exists")
        _verify_root_identity(directory_fd, root_identity)
        final_pre_marker_text = _utc_now()
        final_pre_marker = _parse_utc(final_pre_marker_text)
        issued = _parse_utc(authorization["issued_at_utc"])
        expires = _parse_utc(authorization["expires_at_utc"])
        if (final_pre_marker < initial_utc or not issued <= final_pre_marker < expires
                or time.monotonic_ns() >= global_deadline_ns):
            raise FixedActionExecutionError(
                "AUTHORITY_TIME", "authority is future/expired, clock rolled back, or preparation timed out"
            )
        monotonic_expiry_ns = time.monotonic_ns() + int(
            (expires - final_pre_marker).total_seconds() * 1_000_000_000
        )
        attempt = {
            "schema_version": "cpu-prefetch-stage17-phase-action-attempt/4",
            "attempt_id": request["attempt_id"], "action_id": action,
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": sha256(authorization_bytes),
            "request_sha256": sha256(request_bytes),
            "runtime_sha256": worker_snapshot.sha256,
            "release_resolution_id": release_binding["source_resolution_id"],
            "release_resolution_sha256": release_binding["source_resolution_sha256"],
            "evidence_root_binding": request["evidence_root_binding"],
            "started_at_utc": final_pre_marker_text,
            "one_attempt": True, "retries": 0, "marker_durable": True,
            "phase18_authority": False,
        }
        _validate_schema(
            schemas, "config/schemas/stage17-phase-action-attempt-v4.schema.json",
            attempt, "attempt",
        )
        predecessor._write_exclusive(directory_fd, marker_name, canonical(attempt))
        marker_created = True
        _verify_root_identity(directory_fd, root_identity)

        def authority_guard() -> str:
            _verify_root_identity(directory_fd, root_identity)
            current_text = _utc_now()
            current = _parse_utc(current_text)
            now_ns = time.monotonic_ns()
            if (current < final_pre_marker or not issued <= current < expires
                    or now_ns >= monotonic_expiry_ns
                    or now_ns >= global_deadline_ns):
                raise FixedActionExecutionError(
                    "AUTHORITY_TIME", "authority failed at the immediate worker boundary"
                )
            return current_text

        argv = (
            (worker_snapshot.locator, "--execute-stage17-pilot-session-v1",
             "--request-fd", str(request_snapshot.descriptor),
             "--context-fd", str(context_snapshot.descriptor),
             "--output-dir-fd", str(directory_fd), "--fixed-dispatch-end")
            if action == "STAGE17-BLINDED-PILOT"
            else (worker_snapshot.locator, "--execute-fixed-stage17-action-v4", action,
                  "--request-fd", str(request_snapshot.descriptor),
                  "--context-fd", str(context_snapshot.descriptor),
                  "--output-dir-fd", str(directory_fd), "--fixed-dispatch-end")
        )
        try:
            worker_boundary_entered = True
            transport = _run_worker(
                argv,
                (request_snapshot.descriptor, context_snapshot.descriptor, directory_fd),
                global_deadline_ns=global_deadline_ns,
                authority_guard=authority_guard,
            )
        except predecessor.FixedActionExecutionError as exception:
            proof = getattr(exception, "cleanup_proof", None)
            if proof is not None:
                transport = predecessor.TransportOutcome(
                    proof.returncode, b"", b"", proof.leader_reaped,
                    proof.process_group_gone,
                    getattr(proof, "cleanup_outcome",
                            "FALLBACK_SIGTERM_SIGKILL_REAP"),
                )
            if isinstance(exception, FixedActionExecutionError):
                raise
            raise FixedActionExecutionError(
                exception.category, str(exception)
            ) from exception
        if not transport.leader_reaped or not transport.process_group_gone:
            raise FixedActionExecutionError(
                "PROCESS_CLEANUP", "worker family is not proven quiescent"
            )
        predecessor._write_exclusive(
            directory_fd, f"stage17-{token}-stdout-v4.bin", transport.stdout
        )
        predecessor._write_exclusive(
            directory_fd, f"stage17-{token}-stderr-v4.bin", transport.stderr
        )
        if transport.returncode != 0:
            raise FixedActionExecutionError(
                "WORKER_NONZERO", f"fixed worker returned {transport.returncode}"
            )
        result, result_bytes = _read_json_control(directory_fd, RESULT_NAME)
        try:
            output_registry.validate_worker_result(
                registry=schemas, directory_fd=directory_fd, result=result,
                request=request, authorization_sha256=sha256(authorization_bytes),
                synthetic_test_only=synthetic_test_only,
            )
        except output_registry.OutputAdmissionError as exception:
            raise FixedActionExecutionError("RESULT_ARTIFACT", str(exception)) from exception
        if action == "Q15-W" and (
            not result["restoration_verified"] or result["quarantined"]
        ):
            raise FixedActionExecutionError(
                "RESTORATION", "Q15-W did not prove restoration"
            )
        live_restoration = None
        if definition["requires_restoration"]:
            if not result["restoration_verified"] or result["quarantined"]:
                raise FixedActionExecutionError(
                    "RESTORATION", "mutating action did not report restoration"
                )
            assert hardware_prestate is not None
            try:
                live_restoration = hardware_recovery.verify(
                    hardware_prestate, synthetic=synthetic_test_only
                )
            except hardware_recovery.HardwareRecoveryError as exception:
                raise FixedActionExecutionError(
                    "RESTORATION_READBACK", str(exception)
                ) from exception
        bindings = [
            {"file_name": item["file_name"], "size_bytes": item["size_bytes"],
             "sha256": item["sha256"]}
            for item in result["artifacts"]
        ]
        completion = {
            "schema_version": "cpu-prefetch-stage17-phase-action-completion/4",
            "completion_id": request["attempt_id"] + ":completion",
            "attempt_id": request["attempt_id"], "action_id": action,
            "authorization_sha256": sha256(authorization_bytes),
            "request_sha256": sha256(request_bytes),
            "runtime_sha256": worker_snapshot.sha256,
            "result": {"file_name": RESULT_NAME, "size_bytes": len(result_bytes),
                       "sha256": sha256(result_bytes)},
            "artifact_bindings": bindings,
            "leader_reaped": True, "process_group_gone": True,
            "restoration_verified": result["restoration_verified"],
            "live_restoration_readback": live_restoration,
            "quarantined": result["quarantined"],
            "completed_at_utc": _utc_now(), "phase18_authority": False,
        }
        _validate_schema(
            schemas, "config/schemas/stage17-phase-action-completion-v4.schema.json",
            completion, "completion",
        )
        predecessor._write_exclusive(
            directory_fd, completion_name, canonical(completion)
        )
        return ExecutionOutcome(
            output_root / marker_name, output_root / RESULT_NAME,
            output_root / completion_name, result, completion,
        )
    except BaseException as exception:
        if (marker_created and directory_fd is not None and attempt is not None
                and schemas is not None
                and not predecessor._exists_at(directory_fd, failure_name)):
            quarantine = {"performed": False, "record_sha256": None}
            restoration = not bool(
                schemas.action(action)["requires_restoration"]
            )
            recovery_readback = None
            if schemas.action(action)["requires_restoration"]:
                try:
                    if hardware_prestate is None:
                        raise hardware_recovery.HardwareRecoveryError(
                            "sealed recovery prestate is absent"
                        )
                    recovery_readback = hardware_recovery.restore(
                        hardware_prestate, synthetic=synthetic_test_only
                    )
                    restoration = True
                except BaseException as recovery_exception:
                    quarantine = _quarantine(
                        directory_fd, action, request["attempt_id"],
                        recovery_exception,
                    )
            proof = getattr(exception, "cleanup_proof", None)
            if transport is None and proof is None and worker_boundary_entered:
                raise FixedActionExecutionError(
                    "FAILURE_RETENTION",
                    "worker boundary failed without a quiescence proof",
                ) from exception
            leader_reaped = (
                transport.leader_reaped if transport is not None
                else proof.leader_reaped if proof is not None
                else True  # No process boundary was entered.
            )
            process_group_gone = (
                transport.process_group_gone if transport is not None
                else proof.process_group_gone if proof is not None
                else True  # No process family could have been created.
            )
            failure = {
                "schema_version": "cpu-prefetch-stage17-phase-action-failure/4",
                "failure_id": request["attempt_id"] + ":failure",
                "attempt_id": request["attempt_id"], "action_id": action,
                "authorization_sha256": sha256(authorization_bytes),
                "request_sha256": sha256(request_bytes),
                "runtime_sha256": worker_snapshot.sha256 if worker_snapshot else "0" * 64,
                "failure_category": getattr(exception, "category", type(exception).__name__),
                "failure_stage": "POST_MARKER_FIXED_ACTION_V4",
                "leader_reaped": leader_reaped,
                "process_group_gone": process_group_gone,
                "partial_retained": True,
                "restoration_verified": restoration,
                "recovery_readback": recovery_readback,
                "quarantine_operation": quarantine,
                "completed_at_utc": _utc_now(), "phase18_authority": False,
            }
            try:
                _validate_schema(
                    schemas, "config/schemas/stage17-phase-action-failure-v4.schema.json",
                    failure, "failure",
                )
                predecessor._write_exclusive(
                    directory_fd, failure_name, canonical(failure)
                )
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
