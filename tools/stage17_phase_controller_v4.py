#!/usr/bin/env python3
"""Production authority-verifying Stage 17 fixed-action controller v4.

The CLI has no test-backend switch.  Synthetic test-linked execution is
available only to the separately packaged hermetic dry-run driver.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import pathlib
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Any

import stage17_fixed_action_executor_v4 as executor
import stage17_output_registry_v4 as output_registry
import stage17_phase_controller_v3 as predecessor
import stage17_phase_controller_v2 as controller_support
import stage17_pilot_plan_v4 as pilot_plan_runtime
import stage17_state_journal_v10 as journal_runtime


AUTH_SCHEMA = "config/schemas/stage17-phase-action-authorization-v4.schema.json"
REQUEST_SCHEMA = "config/schemas/stage17-fixed-action-request-v4.schema.json"


class ControllerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedAction:
    root: pathlib.Path
    authorization: dict[str, Any]
    authorization_bytes: bytes
    request: dict[str, Any]
    request_bytes: bytes
    runtime: dict[str, Any]
    worker_path: pathlib.Path
    release: dict[str, Any]
    validation: journal_runtime.OperationalJournalValidation
    registry: output_registry.PinnedOutputRegistry


def _binding(resolution: Any) -> dict[str, str]:
    return {
        "input_id": resolution.input_id,
        "resolution_id": resolution.resolution_id,
        "sha256": resolution.sha256,
    }


def _runtime_from_context(
    action: str, validation: journal_runtime.OperationalJournalValidation,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if action in {"Q15-R", "Q15-W"}:
        source = validation.resolutions["S17-EXT-003"]
        context = source.semantic_context
        if not isinstance(context, dict):
            raise ControllerError("EXT003 runtime context is absent")
        runtime_record = context.get("runtime")
        measurements = (
            runtime_record.get("measurements")
            if isinstance(runtime_record, dict) else None
        )
        if not isinstance(measurements, dict):
            raise ControllerError("EXT003 runtime measurements are absent")
        path = measurements["worker_path"]
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": measurements["worker_role"],
            "runtime_profile": measurements["runtime_profile"],
            "worker_size_bytes": measurements["worker_size_bytes"],
            "worker_sha256": measurements["worker_sha256"],
        }
    else:
        source = validation.resolutions["S17-EXT-006"]
        context = source.semantic_context
        if not isinstance(context, dict):
            raise ControllerError("EXT006 release context is absent")
        measurements = {
            "worker_path": context["release_artifact_path"],
            "worker_size_bytes": context["release_artifact_size_bytes"],
            "worker_sha256": context["release_artifact_sha256"],
            "worker_role": context["release_artifact_role"],
            "runtime_profile": context["runtime_profile"],
            "supported_actions": context["supported_actions"],
        }
        path = measurements["worker_path"]
        release = {
            "source_resolution_id": source.resolution_id,
            "source_resolution_sha256": source.sha256,
            "artifact_role": measurements["worker_role"],
            "runtime_profile": measurements["runtime_profile"],
            "worker_size_bytes": measurements["worker_size_bytes"],
            "worker_sha256": measurements["worker_sha256"],
        }
    if (measurements["worker_role"] != "STAGE17_FIXED_ACTION_WORKER"
            or measurements["runtime_profile"]
            != "STAGE17-FIXED-ACTION-WORKER-v4"
            or tuple(measurements["supported_actions"]) != (
                "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                "STAGE17-BLINDED-PILOT",
            ) or action not in measurements["supported_actions"]):
        raise ControllerError("admitted fixed-action runtime surface drifted")
    runtime = {
        "path": path, "role": measurements["worker_role"],
        "profile": measurements["runtime_profile"],
        "size_bytes": measurements["worker_size_bytes"],
        "sha256": measurements["worker_sha256"],
    }
    return runtime, release


def _action_definition(root: pathlib.Path, action_id: str) \
        -> tuple[dict[str, Any], output_registry.PinnedOutputRegistry]:
    registry = output_registry.pin_registry(root)
    return registry.action(action_id), registry


def _validate_hash(value: Any, label: str) -> None:
    if (not isinstance(value, str) or len(value) != 64
            or any(item not in "0123456789abcdef" for item in value)):
        raise ControllerError(f"{label} is not SHA-256")


def _validate_q16_matrix(action: str, values: dict[str, Any]) -> None:
    packages = ("R0", "R1", "R2", "L0", "L1")
    states = ("H0", "H1")
    placements = ("NEAR", "FAR")
    working_sets = ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC")
    loads = ("L025", "L050", "L075")
    expected = [
        (package, state, placement, working_set) + (
            (load,) if action == "Q16c" else ()
        )
        for state in states for package in packages for placement in placements
        for working_set in working_sets
        for load in (loads if action == "Q16c" else (None,))
    ]
    counts: Counter[tuple[str, ...]] = Counter()
    ordinals: dict[tuple[str, ...], int] = {}
    repetitions: dict[tuple[str, ...], set[int]] = {}
    run_ids: set[str] = set()
    observed_order: list[tuple[int, int]] = []
    for run in values["runs"]:
        key = tuple(run.get(name) for name in (
            "package", "hardware_state", "placement", "working_set_class"
        )) + ((run.get("load_level"),) if action == "Q16c" else ())
        run_id = run.get("run_id")
        ordinal = run.get("cell_ordinal")
        repetition = run.get("repetition_ordinal")
        if (key not in expected or not isinstance(run_id, str) or not run_id
                or run_id in run_ids or not isinstance(ordinal, int)
                or not isinstance(repetition, int) or repetition < 0
                or run.get("plan_sha256") != values["plan_sha256"]
                or run.get("q16a_result_sha256")
                != values["q16a_result_sha256"]
                or (action == "Q16c" and run.get("q16b_result_sha256")
                    != values["q16b_result_sha256"])
                or (action == "Q16b" and "load_level" in run)):
            raise ControllerError("Q16 run matrix/lineage is invalid")
        run_ids.add(run_id); counts[key] += 1
        observed_order.append((ordinal, repetition))
        if key in ordinals and ordinals[key] != ordinal:
            raise ControllerError("Q16 cell ordinal changed within a cell")
        ordinals[key] = ordinal
        repetitions.setdefault(key, set()).add(repetition)
    minimum = 59 if action == "Q16b" else 1
    if (set(counts) != set(expected)
            or set(ordinals.values()) != set(range(len(expected)))
            or any(count < minimum for count in counts.values())
            or any(repetitions[key] != set(range(counts[key])) for key in expected)
            or observed_order != sorted(observed_order)):
        raise ControllerError("Q16 frozen matrix is incomplete or nonprospective")
    canonical_rows = [
        {name: value for name, value in run.items() if name != "plan_sha256"}
        for run in values["runs"]
    ]
    if hashlib.sha256(output_registry.canonical(canonical_rows)).hexdigest() \
            != values["plan_sha256"]:
        raise ControllerError("Q16 frozen plan hash does not bind exact runs")


def _validate_q16a_matrix(values: dict[str, Any]) -> None:
    expected = [
        (state, placement, working_set)
        for state in ("H0", "H1")
        for placement in ("NEAR", "FAR")
        for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC")
    ]
    counts: Counter[tuple[str, str, str]] = Counter()
    contexts: dict[tuple[str, str, str], int] = {}
    repetitions: dict[tuple[str, str, str], set[int]] = {}
    seed_ids: set[str] = set()
    captures = values.get("captures")
    if not isinstance(captures, list) or not captures:
        raise ControllerError("Q16a frozen capture family is absent")
    observed_order: list[tuple[int, int]] = []
    for capture in captures:
        if not isinstance(capture, dict):
            raise ControllerError("Q16a capture is not an object")
        key = (
            capture.get("hardware_state"), capture.get("placement"),
            capture.get("working_set_class"),
        )
        context = capture.get("context_ordinal")
        repetition = capture.get("repetition_ordinal")
        seed_id = capture.get("seed_id")
        if (key not in expected or not isinstance(context, int)
                or not isinstance(repetition, int) or repetition < 0
                or not isinstance(seed_id, str) or not seed_id
                or seed_id in seed_ids
                or capture.get("calibration_plan_sha256")
                != values.get("plan_sha256")):
            raise ControllerError("Q16a capture matrix/lineage is invalid")
        seed_ids.add(seed_id)
        counts[key] += 1
        observed_order.append((context, repetition))
        if key in contexts and contexts[key] != context:
            raise ControllerError("Q16a context ordinal changed within a context")
        contexts[key] = context
        repetitions.setdefault(key, set()).add(repetition)
    if (set(counts) != set(expected)
            or set(contexts.values()) != set(range(12))
            or any(count < 59 for count in counts.values())
            or any(repetitions[key] != set(range(counts[key])) for key in expected)
            or observed_order != sorted(observed_order)):
        raise ControllerError("Q16a frozen matrix is incomplete or nonprospective")


def _validate_hardware_control(values: dict[str, Any], validation: Any) -> None:
    ext5 = validation.resolutions["S17-EXT-005"].semantic_context
    if not isinstance(ext5, dict) or not isinstance(ext5.get("q15_w"), dict):
        raise ControllerError("admitted Q15-W context is absent")
    q15w = ext5["q15_w"]
    q15w_request = q15w.get("request")
    if not isinstance(q15w_request, dict):
        raise ControllerError("admitted Q15-W request is absent")
    expected = {
        "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
        "q15_w_result_sha256": q15w["result_sha256"],
        "prestate": q15w_request["action_inputs"]["prestate"],
    }
    if values.get("hardware_control") != expected:
        raise ControllerError("Q16 hardware control differs from admitted Q15-W")


def _validate_action_inputs(
    *, action: str, request: dict[str, Any], validation: Any,
    synthetic_test_only: bool,
) -> None:
    values = request["action_inputs"]
    if not isinstance(values, dict):
        raise ControllerError("fixed action inputs are not an object")
    # The test-linked dispatcher consumes the same typed scientific input
    # families.  Its backend is synthetic; its contract is not a nonce bypass.
    if action == "Q15-R":
        expected = {
            "qualification_id", "attempt_id", "session_id",
            "probe_platform_binding",
        }
    elif action == "Q15-W":
        expected = {
            "q15_r_attempt_sha256", "q15_r_result_sha256", "session_id",
            "prestate",
        }
    elif action == "Q16a":
        expected = {"plan_sha256", "hardware_control", "captures"}
    elif action == "Q16b":
        expected = {
            "plan_sha256", "q16a_result_sha256", "hardware_control", "runs"
        }
    elif action == "Q16c":
        expected = {
            "plan_sha256", "q16a_result_sha256", "q16b_result_sha256",
            "hardware_control", "runs"
        }
    else:
        expected = {"plan_sha256", "pilot_plan"}
    if set(values) != expected:
        raise ControllerError("production action input family is incomplete/expanded")
    if action == "STAGE17-BLINDED-PILOT":
        plan_context = validation.resolutions["S17-EXT-008"].semantic_context
        if (values["plan_sha256"] != plan_context["pilot_plan_sha256"]
                or values["pilot_plan"] != plan_context["pilot_plan"]):
            raise ControllerError("pilot action differs from admitted frozen plan")
        pilot_plan_runtime.validate(
            values["pilot_plan"], stand_id=request["stand_id"],
            synthetic_test_only=synthetic_test_only,
            admitted_resolutions=validation.resolutions,
        )
    for name, value in values.items():
        if name.endswith("_sha256"):
            _validate_hash(value, name)
    if action == "Q16a":
        _validate_hardware_control(values, validation)
        _validate_q16a_matrix(values)
        for capture in values["captures"]:
            for name, value in capture.items():
                if name.endswith("_sha256"):
                    _validate_hash(value, f"captures/{name}")
    if action in {"Q16b", "Q16c"}:
        _validate_hardware_control(values, validation)
        if not isinstance(values["runs"], list) or not values["runs"]:
            raise ControllerError("Q16 frozen run family is absent")
        for run in values["runs"]:
            if not isinstance(run, dict):
                raise ControllerError("Q16 frozen run is not an object")
            for name, value in run.items():
                if name.endswith("_sha256"):
                    _validate_hash(value, f"runs/{name}")
        _validate_q16_matrix(action, values)


def prepare_action(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, operational_evidence_root: pathlib.Path,
    authorization_path: pathlib.Path,
    signature_path: pathlib.Path, pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
    synthetic_test_only: bool = False,
) -> PreparedAction:
    root = repository_root.resolve()
    authorization, authorization_bytes = controller_support._load(authorization_path)
    controller_support._validate(
        root, AUTH_SCHEMA, authorization, "phase authorization"
    )
    definition, registry = _action_definition(root, authorization["action_id"])
    if authorization["fixed_action_definition_sha256"] != registry.plan_sha256:
        raise ControllerError("fixed-action plan byte binding drifted")
    if authorization["permission_matrix"] != definition["permission_matrix"]:
        raise ControllerError("fixed action permission matrix drifted")
    expected_deadline_mode = (
        "DURABLE_PILOT_SESSION"
        if authorization["action_id"] == "STAGE17-BLINDED-PILOT"
        else "ONE_SHOT_ACTION"
    )
    policy = authorization["deadline_policy"]
    if (policy["mode"] != expected_deadline_mode
            or policy["per_run_max_wall_seconds"] != 180
            or policy["implicit_extension"] is not False
            or policy["partial_session_completes"] is not False):
        raise ControllerError("action deadline/session policy drifted")
    actual_now = controller_support._now()
    validation = journal_runtime.validate_operational_journal(
        repository_root=root, evidence_root=operational_evidence_root,
        latest_journal=journal,
        journal_directory=journal_directory, pilot_archive=pilot_archive,
        pilot_sidecar=pilot_sidecar, as_of_utc=actual_now,
        allow_synthetic_test_evidence=synthetic_test_only,
    )
    required_ids = tuple(definition["required_resolution_ids"])
    if any(item not in validation.resolutions for item in required_ids):
        raise ControllerError("fixed action predecessor is absent")
    if validation.current_state != definition["required_state"]:
        raise ControllerError("fixed action state gate is not satisfied")
    expected_predecessors = [
        _binding(validation.resolutions[item]) for item in required_ids
    ]
    if authorization["predecessor_resolutions"] != expected_predecessors:
        raise ControllerError("authorization predecessor lineage drifted")
    authority_resolution = definition["authorization_resolution_id"]
    if authority_resolution is not None:
        admitted = validation.resolutions.get(authority_resolution)
        if admitted is None or not isinstance(admitted.semantic_context, dict):
            raise ControllerError("action authorization resolution is absent")
        if (admitted.semantic_context.get("authorization_sha256")
                != controller_support._sha(authorization_bytes)
                or admitted.semantic_context.get("authorization") != authorization):
            raise ControllerError("execution authority differs from admitted bytes")
    ext3 = validation.resolutions["S17-EXT-003"].semantic_context
    if not isinstance(ext3, dict) or not isinstance(ext3.get("trust"), dict):
        raise ControllerError("admitted trust context is absent")
    trust = ext3["trust"]
    values = trust["measurements"]
    expected_trust_context = {
        "ext002_resolution": _binding(validation.resolutions["S17-EXT-002"]),
        "ext003_resolution": _binding(validation.resolutions["S17-EXT-003"]),
    }
    if (authorization["trust_context"] != expected_trust_context
            or authorization["actor"] != values["principal"]
            or authorization["reviewer"] != values["reviewer_role"]
            or authorization["target"]["stand_id"] != trust["subject_id"]):
        raise ControllerError("authorization trust actor/reviewer/stand drifted")
    controller_support._verify_signature(
        authorization_bytes, signature_path, trust
    )
    issued = controller_support._parse_utc(authorization["issued_at_utc"])
    expires = controller_support._parse_utc(authorization["expires_at_utc"])
    sampled = controller_support._parse_utc(actual_now)
    if authorization["action_id"] == "STAGE17-BLINDED-PILOT":
        pilot = validation.resolutions["S17-EXT-008"].semantic_context[
            "pilot_plan"
        ]
        repetitions = pilot["repetitions_per_cell"]
        recovery_seconds = math.ceil(
            pilot["recovery"]["duration_ticks"] / 1_000_000_000_000
        )
        maximum_seconds = (
            180 * 180 * repetitions
            + recovery_seconds * max(repetitions - 1, 0)
            + 180
        )
        if policy["session_max_wall_seconds"] != maximum_seconds:
            raise ControllerError("pilot session maximum is not plan-derived")
    else:
        maximum_seconds = 1800
        if policy["session_max_wall_seconds"] is not None:
            raise ControllerError("one-shot action cannot declare a session maximum")
    if (not issued <= sampled < expires
            or expires - issued > dt.timedelta(seconds=maximum_seconds)):
        raise ControllerError("authorization is future/expired/overlong")
    request_path, request_bytes = controller_support._read_binding(
        authorization["request_binding"], "fixed request"
    )
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ControllerError("fixed request root is not an object")
    controller_support._validate(root, REQUEST_SCHEMA, request, "fixed request")
    runtime, release = _runtime_from_context(authorization["action_id"], validation)
    expected_runtime = {key: runtime[key] for key in (
        "role", "profile", "size_bytes", "sha256",
    )}
    if (request["runtime_binding"] != expected_runtime
            or request["release_binding"] != release
            or authorization["evidence_root_binding"]
            != request["evidence_root_binding"]
            or request["predecessor_resolutions"] != expected_predecessors
            or request["authorization_id"] != authorization["authorization_id"]
            or request["session_id"] != authorization["session_id"]
            or request["action_id"] != authorization["action_id"]
            or request["stand_id"] != authorization["target"]["stand_id"]
            or request["synthetic_test_only"] is not synthetic_test_only
            or pathlib.Path(authorization["request_binding"]["path"])
            != request_path):
        raise ControllerError("fixed request lineage/runtime/release drifted")
    _validate_action_inputs(
        action=authorization["action_id"], request=request,
        validation=validation, synthetic_test_only=synthetic_test_only,
    )
    worker_path = pathlib.Path(runtime.pop("path"))
    return PreparedAction(
        root=root, authorization=authorization,
        authorization_bytes=authorization_bytes, request=request,
        request_bytes=request_bytes, runtime=runtime, worker_path=worker_path,
        release=release, validation=validation, registry=registry,
    )


def execute_once(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, operational_evidence_root: pathlib.Path,
    authorization_path: pathlib.Path,
    signature_path: pathlib.Path, pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
    synthetic_test_only: bool = False,
) -> executor.ExecutionOutcome:
    prepared = prepare_action(
        repository_root=repository_root, journal=journal,
        journal_directory=journal_directory,
        operational_evidence_root=operational_evidence_root,
        authorization_path=authorization_path, signature_path=signature_path,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
        synthetic_test_only=synthetic_test_only,
    )
    if prepared.authorization["action_id"] in {"Q15-R", "Q15-W"}:
        raise ControllerError(
            "Q15 actions require the phase-spanning session controller"
        )
    return executor.execute_fixed_action(
        repository_root=prepared.root, authorization=prepared.authorization,
        authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=pathlib.Path(
            prepared.request["evidence_root_binding"]["absolute_path"]
        ),
        synthetic_test_only=synthetic_test_only,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--operational-evidence-root", type=pathlib.Path,
                        required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--signature", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    arguments = parser.parse_args()
    try:
        execute_once(
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
    except BaseException as exception:
        print(f"stage17-phase-controller-v4: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-phase-controller-v4: PASS action=COMPLETED authority=STAGE17_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
