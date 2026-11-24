#!/usr/bin/env python3
"""Stage 17A.7 lifecycle-schema and retention-order regressions."""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import os
import time
import tempfile
import threading
import sys
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

import stage17_read_only_preflight_executor_v6 as executor
import stage17_read_only_preflight_executor_v5 as predecessor_executor


ROOT = pathlib.Path(__file__).resolve().parents[1]
SHA = "1" * 64
UTC = "2030-01-01T00:00:00.000001Z"
CLEANUP_OUTCOMES = (
    "NORMAL_LEADER_REAPED_GROUP_QUIESCENT",
    "SIGTERM_LEADER_REAPED_GROUP_QUIESCENT",
    "SIGKILL_LEADER_REAPED_GROUP_QUIESCENT",
    "SIGKILL_BARRIER_LEADER_REAPED_GROUP_QUIESCENT",
)


class CheckError(RuntimeError):
    pass


def _schema(name: str) -> Draft202012Validator:
    document = json.loads((ROOT / "config/schemas" / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document)


def _base() -> dict[str, Any]:
    return {
        "attempt_id": "SYNTHETIC-ATTEMPT",
        "attempt_marker_sha256": SHA,
        "authorization_id": "SYNTHETIC-AUTHORIZATION",
        "authorization_sha256": SHA,
        "resolution_id": "SYNTHETIC-RESOLUTION",
        "resolution_sha256": SHA,
        "transition_id": "SYNTHETIC-TRANSITION",
        "transition_sha256": SHA,
        "action_plan_sha256": SHA,
        "runtime_implementation_hashes": {
            f"implementation_{index:02d}": SHA for index in range(17)
        },
        "executor_sha256": SHA,
        "collector_sha256": SHA,
        "pinned_inputs_metadata_sha256": SHA,
        "consumed_known_hosts_sha256": SHA,
        "consumed_transport_identity_sha256": SHA,
        "openssh_consumption_capability_sha256": SHA,
    }


def _failure(child_started: bool, outcome: str) -> dict[str, Any]:
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-failure/6",
        **_base(),
        "failed_stage": "TRANSPORT",
        "failed_ordinal": 1,
        "failed_observation_id": "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
        "completed_observation_ids": [],
        "reason_category": "SYNTHETIC_FAILURE",
        "reason": "synthetic typed lifecycle failure",
        "actual_authority_sample_before_marker_utc": UTC,
        "actual_authority_sample_before_first_transport_utc": None,
        "transport_authority_sample_utc": None,
        "authority_clock_relation": "LIVE_NONDECREASING",
        "actual_failed_at_utc": UTC,
        "duration_ns": 1,
        "ssh_argv_sha256": SHA,
        "rendered_program_sha256": SHA,
        "child_started": child_started,
        "leader_reaped": child_started,
        "process_group_gone": True,
        "terminal_cleanup_outcome": outcome,
        "descendants_detected_after_leader_exit": child_started,
        "maximum_descendant_count": 1 if child_started else 0,
        "cleanup_deadline_overrun": False,
        "cleanup_diagnostics": [],
        "retry_allowed": False,
        "partial_evidence_retained": True,
        "stage18_authority": False,
    }


def _receipt(outcome: str) -> dict[str, Any]:
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-observation-receipt/5",
        **_base(),
        "ordinal": 1,
        "observation_id": "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
        "rendered_program_sha256": SHA,
        "ssh_argv_sha256": SHA,
        "actual_authority_sample_before_marker_utc": UTC,
        "actual_authority_sample_before_first_transport_utc": UTC,
        "transport_authority_sample_utc": UTC,
        "actual_started_at_utc": UTC,
        "actual_completed_at_utc": UTC,
        "duration_ns": 1,
        "returncode": 0,
        "failure": None,
        "stdout_size_bytes": 0,
        "stdout_sha256": SHA,
        "stderr_size_bytes": 0,
        "stderr_sha256": SHA,
        "leader_reaped": True,
        "process_group_gone": True,
        "terminal_cleanup_outcome": outcome,
        "descendants_detected_after_leader_exit": False,
        "maximum_descendant_count": 0,
        "cleanup_deadline_overrun": False,
        "cleanup_diagnostics": [],
        "attempt": 1,
        "retry": 0,
        "stage18_authority": False,
    }


def _completion() -> dict[str, Any]:
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-completion/5",
        **_base(),
        "ssh_argv_sha256": SHA,
        "completed_observation_ids": [f"SYNTHETIC-{value}" for value in range(6)],
        "receipt_sha256s": [SHA] * 6,
        "actual_authority_sample_before_marker_utc": UTC,
        "actual_authority_sample_before_first_transport_utc": UTC,
        "actual_completed_at_utc": UTC,
        "duration_ns": 1,
        "all_leaders_reaped": True,
        "all_process_groups_gone": True,
        "process_group_policy": "LINUX_SUBREAPER_HOLD_LEADER_WNOWAIT_QUIESCE_GROUP_THEN_REAP",
        "attempts": 6,
        "retries": 0,
        "stage18_authority": False,
    }


def _schema_terminal_states() -> None:
    failure = _schema("stage17-read-only-preflight-failure-v6.schema.json")
    receipt = _schema("stage17-read-only-preflight-observation-receipt-v5.schema.json")
    completion = _schema("stage17-read-only-preflight-completion-v5.schema.json")
    failure.validate(_failure(False, "NOT_STARTED_GROUP_ABSENT"))
    for outcome in CLEANUP_OUTCOMES:
        failure.validate(_failure(True, outcome))
        receipt.validate(_receipt(outcome))
    completion.validate(_completion())


def _group_false_rejected() -> None:
    validator = _schema("stage17-read-only-preflight-failure-v6.schema.json")
    document = _failure(True, CLEANUP_OUTCOMES[0])
    document["process_group_gone"] = False
    if not list(validator.iter_errors(document)):
        raise CheckError("failure schema admitted an unproved live process group")


def _leader_false_rejected_after_start() -> None:
    validator = _schema("stage17-read-only-preflight-failure-v6.schema.json")
    document = _failure(True, CLEANUP_OUTCOMES[0])
    document["leader_reaped"] = False
    if not list(validator.iter_errors(document)):
        raise CheckError("failure schema admitted an unreaped started leader")


def _descendant_receipt_rejected() -> None:
    validator = _schema("stage17-read-only-preflight-observation-receipt-v5.schema.json")
    document = _receipt(CLEANUP_OUTCOMES[1])
    document["descendants_detected_after_leader_exit"] = True
    document["maximum_descendant_count"] = 1
    if not list(validator.iter_errors(document)):
        raise CheckError("receipt schema admitted a post-leader descendant")


def _completion_without_group_proof_rejected() -> None:
    validator = _schema("stage17-read-only-preflight-completion-v5.schema.json")
    document = _completion()
    document["all_process_groups_gone"] = False
    if not list(validator.iter_errors(document)):
        raise CheckError("completion schema admitted missing group proof")


def _executor_normal_group_success() -> None:
    result = executor._transport_once(
        (sys.executable, "-c", "import sys;print(len(sys.stdin.buffer.read()))"),
        b"abc", 2.0, 1024,
        global_deadline_ns=time.monotonic_ns() + 5_000_000_000,
        authority_guard=lambda: UTC,
    )
    if (
        result.returncode != 0 or not result.leader_reaped
        or not result.process_group_gone
        or result.descendants_detected_after_leader_exit
    ):
        raise CheckError("ordinary executor transport lacked terminal group proof")


def _executor_descendant_fails_after_quiescence() -> None:
    program = (
        "import os,subprocess,sys;d=open(os.devnull,'r+b');"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
        "stdin=d,stdout=d,stderr=d);sys.exit(0)"
    )
    try:
        executor._transport_once(
            (sys.executable, "-c", program), b"", 2.0, 1024,
            global_deadline_ns=time.monotonic_ns() + 5_000_000_000,
            authority_guard=lambda: UTC,
        )
    except executor.TransportLifecycleError as exception:
        if (
            exception.category != "PROCESS_GROUP_NOT_QUIESCENT_AT_LEADER_EXIT"
            or not exception.leader_reaped or not exception.process_group_gone
            or not exception.descendants_detected_after_leader_exit
        ):
            raise CheckError("descendant failure escaped before group quiescence") from exception
        return
    raise CheckError("executor emitted success despite a post-leader descendant")


def _predecessor_defect_characterized() -> None:
    program = (
        "import os,subprocess,sys;d=open(os.devnull,'r+b');"
        "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
        "stdin=d,stdout=d,stderr=d);sys.exit(0)"
    )
    original_popen = predecessor_executor.subprocess.Popen
    leaders: list[int] = []

    def capture_popen(*args: Any, **kwargs: Any):
        process = original_popen(*args, **kwargs)
        leaders.append(process.pid)
        return process

    predecessor_executor.subprocess.Popen = capture_popen  # type: ignore[assignment]
    try:
        result = predecessor_executor._transport_once(
            (sys.executable, "-c", program), b"", 2.0, 1024,
            global_deadline_ns=time.monotonic_ns() + 5_000_000_000,
            authority_guard=lambda: UTC,
        )
    finally:
        predecessor_executor.subprocess.Popen = original_popen  # type: ignore[assignment]
    if not leaders:
        raise CheckError("predecessor characterization did not capture its leader")
    process_group = leaders[0]
    try:
        try:
            os.killpg(process_group, 0)
        except ProcessLookupError as exception:
            raise CheckError("predecessor defect was not reproduced") from exception
        if (
            result.returncode != 0 or not result.child_reaped
            or result.process_group_cleanup != "NORMAL_EXIT_REAPED"
        ):
            raise CheckError("predecessor did not expose the confirmed false-success state")
    finally:
        try:
            os.killpg(process_group, 9)
        except ProcessLookupError:
            pass


def _concurrent_one_marker_one_transport_family() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17a7-concurrent-") as temporary:
        root = pathlib.Path(temporary)
        marker_name = "stage17-read-only-preflight-attempt-v6.json"
        barrier = threading.Barrier(2)
        transport_count = 0
        lock = threading.Lock()
        outcomes: list[str] = []

        def attempt() -> None:
            nonlocal transport_count
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                barrier.wait(timeout=2)
                executor._write_exclusive_at(directory_fd, marker_name, b"synthetic\n")
                with lock:
                    transport_count += 1
                result = executor._transport_once(
                    (sys.executable, "-c", "pass"), b"", 2.0, 1024,
                    global_deadline_ns=time.monotonic_ns() + 5_000_000_000,
                    authority_guard=lambda: UTC,
                )
                outcomes.append(f"winner:{result.returncode}")
            except FileExistsError:
                outcomes.append("blocked")
            finally:
                os.close(directory_fd)

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        if any(thread.is_alive() for thread in threads):
            raise CheckError("concurrent v6 attempts did not terminate")
        if transport_count != 1 or sorted(outcomes) != ["blocked", "winner:0"]:
            raise CheckError("concurrent v6 attempts escaped one-shot transport admission")


def _cross_version_markers_listed() -> None:
    context = {
        "failure_name": "stage17-read-only-preflight-failure-v6.json",
        "failure_retention_name": "stage17-read-only-preflight-failure-retention-v1.json",
        "completion_name": "stage17-read-only-preflight-completion-v5.json",
    }
    names = set(executor._all_one_shot_names(context))
    required = {
        *(f"stage17-read-only-preflight-attempt-v{version}.json" for version in range(1, 7)),
        *(f"stage17-read-only-preflight-failure-v{version}.json" for version in range(2, 7)),
        *(f"stage17-read-only-preflight-completion-v{version}.json" for version in range(1, 6)),
    }
    if not required <= names:
        raise CheckError("successor omitted a predecessor/current one-shot marker")


def _fallback_retention_not_suppressed() -> None:
    original_full = executor._write_failure
    original_fallback = executor._write_failure_retention
    calls: list[str] = []
    try:
        def full(**_: Any) -> None:
            calls.append("full")
            raise ValueError("schema mismatch")

        def fallback(**_: Any) -> None:
            calls.append("fallback")

        executor._write_failure = full  # type: ignore[assignment]
        executor._write_failure_retention = fallback  # type: ignore[assignment]
        result = executor._retain_operational_failure(
            prepared=SimpleNamespace(),
            failure=executor.OperationalFailure("TRANSPORT", "PRIMARY", "primary"),
            completed=[], action_started_ns=0, before_marker_utc=UTC,
            before_transport_utc=None,
        )
        if calls != ["full", "fallback"] or not result.startswith("FALLBACK_RETAINED:"):
            raise CheckError("typed fallback did not preserve full-retention failure")
    finally:
        executor._write_failure = original_full  # type: ignore[assignment]
        executor._write_failure_retention = original_fallback  # type: ignore[assignment]


def _double_retention_error_visible() -> None:
    original_full = executor._write_failure
    original_fallback = executor._write_failure_retention
    try:
        executor._write_failure = lambda **_: (_ for _ in ()).throw(ValueError("full"))  # type: ignore[assignment]
        executor._write_failure_retention = lambda **_: (_ for _ in ()).throw(OSError("fallback"))  # type: ignore[assignment]
        try:
            executor._retain_operational_failure(
                prepared=SimpleNamespace(),
                failure=executor.OperationalFailure("TRANSPORT", "PRIMARY", "primary"),
                completed=[], action_started_ns=0, before_marker_utc=UTC,
                before_transport_utc=None,
            )
        except executor.ActionExecutionError as exception:
            message = str(exception)
            if not all(value in message for value in ("primary=PRIMARY", "full", "fallback")):
                raise CheckError("composite retention error lost a cause") from exception
            return
        raise CheckError("double retention error was silently suppressed")
    finally:
        executor._write_failure = original_full  # type: ignore[assignment]
        executor._write_failure_retention = original_fallback  # type: ignore[assignment]


def self_test() -> tuple[int, int]:
    positives = [
        ("all_terminal_schema_states", _schema_terminal_states),
        ("typed_fallback_retention", _fallback_retention_not_suppressed),
        ("executor_normal_group_success", _executor_normal_group_success),
        ("concurrent_one_marker_one_transport", _concurrent_one_marker_one_transport_family),
    ]
    negatives = [
        ("live_group_rejected", _group_false_rejected),
        ("unreaped_leader_rejected", _leader_false_rejected_after_start),
        ("descendant_receipt_rejected", _descendant_receipt_rejected),
        ("completion_without_group_proof_rejected", _completion_without_group_proof_rejected),
        ("executor_descendant_fails_after_quiescence", _executor_descendant_fails_after_quiescence),
        ("predecessor_false_success_characterized", _predecessor_defect_characterized),
        ("cross_version_markers_fail_closed", _cross_version_markers_listed),
        ("double_retention_error_visible", _double_retention_error_visible),
    ]
    for label, check in positives + negatives:
        check()
        print(f"stage17-process-group-evidence: PASS {label}")
    return len(positives), len(negatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-process-group-evidence: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-process-group-evidence: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
