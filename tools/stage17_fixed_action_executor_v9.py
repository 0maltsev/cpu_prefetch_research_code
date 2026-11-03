"""D207 diagnostic fd executor successor. Existing actions delegate unchanged.

The lifecycle is copied from v6 to bind new schemas and a plan-derived deadline;
all snapshot, supervision, restoration and retention helpers are reused.
"""
from __future__ import annotations
import os
import pathlib
import time
from typing import Any
import stage17_fixed_action_executor_v7  # accepted formal side effects
import stage17_fixed_action_executor_v6 as base
import stage17_output_registry_v10 as output_registry
import stage17_discovery_contract_v2 as contract

predecessor = base.predecessor
snapshot_broker = base.snapshot_broker
hardware_recovery = base.hardware_recovery
FixedActionExecutionError = base.FixedActionExecutionError
_utc_now = base._utc_now
_parse_utc = base._parse_utc
_componentwise_output_root = base._componentwise_output_root
_quarantine_present = base._quarantine_present
_verify_root_identity = base._verify_root_identity
_run_worker = base._run_worker
_validate_schema = base._validate_schema
_read_json_control = base._read_json_control
_quarantine = base._quarantine
canonical = base.canonical
sha256 = base.sha256
RESULT_NAME = output_registry.RESULT_NAME
ExecutionOutcome = base.ExecutionOutcome


def diagnostic_prestate(request):
    control = request["action_inputs"]["hardware_control"]
    values = output_registry.predecessor.validate_hardware_control(control)
    return tuple((cpu, int(value, 16)) for cpu, value in values.items())


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
    if action != output_registry.ACTION:
        return base.execute_fixed_action(repository_root=repository_root,
            authorization=authorization, authorization_bytes=authorization_bytes,
            request=request, request_bytes=request_bytes, worker_binding=worker_binding,
            worker_path=worker_path, release_binding=release_binding,
            output_root=output_root, synthetic_test_only=synthetic_test_only)
    plan = contract.validate_plan(request["action_inputs"]["plan"])
    from stage17_phase_controller_v24 import deadline_policy as expected_policy
    if deadline_policy != expected_policy(plan):
        raise FixedActionExecutionError("ACTION_DEADLINE", "diagnostic budget differs")
    global_wall_seconds = deadline_policy["session_max_wall_seconds"]
    started_ns = time.monotonic_ns()
    global_deadline_ns = started_ns + global_wall_seconds * 1_000_000_000
    token = action.lower().replace("-", "_")
    marker_name = f"stage17-{token}-attempt-v5.json"
    failure_name = f"stage17-{token}-failure-v5.json"
    completion_name = f"stage17-{token}-completion-v5.json"
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
            hardware_prestate = diagnostic_prestate(request)
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
        request_snapshot = predecessor._pin_generated(request_bytes, "FIXED_ACTION_REQUEST_V5")
        snapshot_broker.verify_snapshot(request_snapshot)
        if os.pread(request_snapshot.descriptor, len(request_bytes) + 1, 0) != request_bytes:
            raise FixedActionExecutionError("REQUEST_SNAPSHOT", "request snapshot bytes drifted")
        predecessor_hashes = [item["sha256"] for item in request["predecessor_resolutions"]]
        context = {
            "schema_version": "cpu-prefetch-stage17-fixed-action-context/5",
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
            "per_run_deadline_seconds": deadline_policy["per_run_max_wall_seconds"],
            "session_deadline_seconds": global_wall_seconds,
            "synthetic_test_only": synthetic_test_only,
            "phase18_authority": False,
        }
        _validate_schema(
            schemas, "config/schemas/stage17-fixed-action-context-v5.schema.json",
            context, "worker context",
        )
        context_snapshot = predecessor._pin_generated(
            canonical(context), "FIXED_ACTION_CONTEXT_V5"
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
        for version in range(1, 6):
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
            "schema_version": "cpu-prefetch-stage17-phase-action-attempt/5",
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
            schemas, "config/schemas/stage17-phase-action-attempt-v5.schema.json",
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
            else (worker_snapshot.locator, "--execute-fixed-stage17-action-v5", action,
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
            directory_fd, f"stage17-{token}-stdout-v5.bin", transport.stdout
        )
        predecessor._write_exclusive(
            directory_fd, f"stage17-{token}-stderr-v5.bin", transport.stderr
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
            "schema_version": "cpu-prefetch-stage17-phase-action-completion/5",
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
            schemas, "config/schemas/stage17-phase-action-completion-v5.schema.json",
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
                "schema_version": "cpu-prefetch-stage17-phase-action-failure/5",
                "failure_id": request["attempt_id"] + ":failure",
                "attempt_id": request["attempt_id"], "action_id": action,
                "authorization_sha256": sha256(authorization_bytes),
                "request_sha256": sha256(request_bytes),
                "runtime_sha256": worker_snapshot.sha256 if worker_snapshot else "0" * 64,
                "failure_category": getattr(exception, "category", type(exception).__name__),
                "failure_stage": "POST_MARKER_FIXED_ACTION_V5",
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
                    schemas, "config/schemas/stage17-phase-action-failure-v5.schema.json",
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

