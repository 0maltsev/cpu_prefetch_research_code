#!/usr/bin/env python3
"""Focused full-matrix Stage 17 pilot-plan admission regressions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import tempfile
import types
from typing import Any, Callable

from jsonschema import Draft202012Validator

import stage17_operational_semantics_v3 as semantics
import stage17_output_registry_v3 as output_registry


ROOT = pathlib.Path(__file__).resolve().parents[1]
KINDS = (
    "PROTOCOL_SNAPSHOT", "SOURCE_RELEASE", "RUN_PLAN", "WARMUP_SCHEDULE",
    "MEASUREMENT_SCHEDULE", "SEED_DERIVATION", "PLATFORM_INVENTORY",
    "PLATFORM_REQUEST", "PLATFORM_VERIFICATION", "HARDWARE_PREFETCH_MAPPING",
    "SOFTWARE_PREFETCH_MAPPING", "CLOCK_QUALIFICATION", "QUEUE_PROVENANCE",
    "RUNTIME_ATOMIC_LAYOUT", "ADDRESS_RESIDENCY", "STORAGE_BUDGET",
    "DURABILITY_DOMAINS", "CALIBRATION_FREEZE", "EXECUTION_LIMITS",
    "AUTHORITY_CUSTODY", "PHASE_EXECUTION_AUTHORIZATION",
)


class CheckError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def schedule_hash(deadlines: list[int], horizon: int) -> str:
    return digest(canonical({
        "schema_version": "cpu-prefetch-stage17-frozen-schedule/2",
        "arrival_family": "OPEN_LOOP_FROZEN", "deadline_ticks": deadlines,
        "origin_ticks": 0, "horizon_ticks": horizon,
    }))


def admitted() -> dict[str, Any]:
    result: dict[str, Any] = {}
    artifact_index = {
        f"ADMITTED-{index:02d}": {"sha256": f"{index:064x}"}
        for index in range(1, 40)
    }
    for index in range(1, 8):
        input_id = f"S17-EXT-{index:03d}"
        context: dict[str, Any] = {"artifact_index": artifact_index}
        if index == 6:
            context.update({
                "source_revision": "a" * 40,
                "release_artifact_sha256": "b" * 64,
            })
        result[input_id] = types.SimpleNamespace(
            resolution_id=f"SYNTHETIC-{input_id}-RESOLUTION",
            sha256=f"{100 + index:064x}", semantic_context=context,
        )
    return result


def plan_fixture(
    repetitions: int = 2, *, resolutions: dict[str, Any] | None = None,
    source_revision: str = "a" * 40, worker_sha256: str = "b" * 64,
    q15_w_result_sha256: str = "c" * 64,
    q15_prestate: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolutions = admitted() if resolutions is None else resolutions
    packages = ("R0", "R1", "R2", "L0", "L1")
    placements = ("NEAR", "FAR")
    working_sets = ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC")
    loads = ("L025", "L050", "L075")
    cells: list[dict[str, Any]] = []
    ordinal = 0
    for state in ("H0", "H1"):
        for package in packages:
            for placement in placements:
                for working_set in working_sets:
                    for load in loads:
                        runs = []
                        for repetition in range(repetitions):
                            family = f"{placement}-{working_set}-{load}-R{repetition}"
                            deadlines = [0, 5, 10, 15]
                            warmup = [0, 10]
                            runs.append({
                                "cell_ordinal": ordinal,
                                "repetition_ordinal": repetition,
                                "hardware_state": state, "placement": placement,
                                "working_set_class": working_set, "load_level": load,
                                "capacity": 64, "offered_count": len(deadlines),
                                "package": package, "d2_cache_lines": 2,
                                "schedule_sha256": schedule_hash(deadlines, 100),
                                "run_id": f"SYNTHETIC-PILOT-{ordinal:03d}-{repetition:03d}",
                                "seed_id": "SYNTHETIC-SEED-" + family,
                                "seed_hex": digest(family.encode()),
                                "cache_line_bytes": 64, "base_page_bytes": 4096,
                                "schedule_deadline_ticks": deadlines,
                                "schedule_origin_ticks": 0,
                                "schedule_horizon_ticks": 100,
                                "duration_ticks": 100,
                                "warmup_run_id": "SYNTHETIC-WARMUP-" + family,
                                "warmup_schedule_sha256": schedule_hash(warmup, 50),
                                "warmup_seed_id": "SYNTHETIC-WARMUP-SEED-" + family,
                                "warmup_schedule_deadline_ticks": warmup,
                                "warmup_schedule_origin_ticks": 0,
                                "warmup_schedule_horizon_ticks": 50,
                                "shared_memory_node": 0,
                            })
                        cells.append({
                            "cell_ordinal": ordinal, "package": package,
                            "hardware_state": state, "placement": placement,
                            "working_set_class": working_set, "load_level": load,
                            "runs": runs,
                        })
                        ordinal += 1
    plan = {
        "schema_version": "cpu-prefetch-stage17-pilot-plan/3",
        "plan_id": "SYNTHETIC-FULL-STAGE17-PILOT-TEST-ONLY",
        "plan_core_sha256": "0" * 64, "protocol_version": "2.0.0-pre.2",
        "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
        "repetitions_per_cell": repetitions, "whole_plot_order": ["H0", "H1"],
        "hardware_control": {
            "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
            "q15_w_result_sha256": q15_w_result_sha256,
            "prestate": (
                q15_prestate if q15_prestate is not None else
                [{"cpu": cpu, "complete_value_hex": "0000000000000000"}
                 for cpu in (0, 1, 26)]
            ),
        },
        "cells": cells, "treatment_blind": True,
        "confirmatory_outcomes_accessed": False,
        "synthetic_test_only": True, "phase18_authority": False,
    }
    plan["plan_core_sha256"] = digest(canonical(semantics._pilot_plan_core(plan)))
    known: dict[str, str] = {}
    for resolution in resolutions.values():
        known[resolution.resolution_id] = resolution.sha256
        context = resolution.semantic_context
        if isinstance(context, dict):
            for key, value in context.get("artifact_index", {}).items():
                if isinstance(value, dict) and isinstance(value.get("sha256"), str):
                    known[key] = value["sha256"]
    if len(known) < len(KINDS) - 5:
        raise CheckError("admitted fixture lacks enough exact evidence bindings")
    generic = iter(known.items())
    for cell in cells:
        for run in cell["runs"]:
            binding_id = "BINDING-" + run["run_id"]
            special = {
                "SOURCE_RELEASE": worker_sha256,
                "RUN_PLAN": plan["plan_core_sha256"],
                "WARMUP_SCHEDULE": run["warmup_schedule_sha256"],
                "MEASUREMENT_SCHEDULE": run["schedule_sha256"],
                "SEED_DERIVATION": semantics._seed_derivation_hash(run),
            }
            evidence = []
            for kind in KINDS:
                if kind in special:
                    artifact_id, value = "DERIVED-" + kind, special[kind]
                else:
                    try:
                        artifact_id, value = next(generic)
                    except StopIteration:
                        generic = iter(known.items())
                        artifact_id, value = next(generic)
                evidence.append({
                    "kind": kind, "artifact_id": artifact_id,
                    "path": "admitted-context/" + artifact_id,
                    "sha256": value, "binding_id": binding_id,
                    "immutable": True, "eligible": True,
                })
            admission = {
                "schema_version": "cpu-prefetch-runner-admission/3",
                "protocol_version": "2.0.0-pre.2",
                "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
                "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
                "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
                "source_revision": source_revision,
                "binary_sha256": worker_sha256,
                "stand_id": plan["stand_id"], "binding_id": binding_id,
                "package": run["package"], "placement": run["placement"],
                "producer_cpu": 0,
                "consumer_cpu": 1 if run["placement"] == "NEAR" else 26,
                "execution_limits": {"controller_start_poll_limit": 1000000,
                                     "worker_start_poll_limit": 1000000},
                "evidence": evidence,
            }
            run["runner_admission"] = admission
            run["runner_admission_sha256"] = digest(canonical(admission))
            run["runner_evidence_set_sha256"] = digest(canonical(evidence))
    return plan, resolutions


def expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except BaseException:
        print(f"stage17-pilot-semantics-v3: PASS negative={label}")
        return
    raise CheckError(f"negative fixture admitted: {label}")


def self_test() -> tuple[int, int]:
    pinned = {
        "config/schemas/runner-admission-v3.schema.json": (
            ROOT / "config/schemas/runner-admission-v3.schema.json"
        ).read_bytes()
    }
    plan, resolutions = plan_fixture()
    schema = json.loads((ROOT / "config/schemas/stage17-pilot-plan-v3.schema.json").read_bytes())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(plan))
    if errors:
        raise CheckError(f"positive plan schema rejection: {errors[0].message}")
    def validate(document: dict[str, Any]) -> None:
        semantics._validate_pilot_plan(
            document, stand_id="SYNTHETIC-STAND-NOT-ACCESSED",
            synthetic=True, admitted_resolutions=resolutions, pinned=pinned,
        )
    validate(plan)
    print("stage17-pilot-semantics-v3: PASS positive=full_180_by_2")
    # Exercise the production streaming verifier at the registered high-tail
    # boundary without retaining the raw observation stream in Python memory.
    # 200,000 joined rows at the v3 physical maximum are deliberately larger
    # than the removed development-only 16 MiB cap.
    row_count = 200_000
    run_id = "SYNTHETIC-NEFF-200000"
    raw_size = row_count * (2 + len(run_id.encode()) + 24 * 8)
    with tempfile.TemporaryDirectory(prefix="stage17-neff-stream-") as temporary:
        root = pathlib.Path(temporary)
        raw = root / "joined-raw-v1.bin"
        descriptor = os.open(
            raw, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600,
        )
        try:
            chunk = bytes(range(256)) * 4096
            remaining = raw_size
            while remaining:
                written = os.write(descriptor, chunk[:min(len(chunk), remaining)])
                if written <= 0:
                    raise CheckError("stream fixture short write")
                remaining -= written
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            raw_fd = os.open(
                raw.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=directory_fd,
            )
            try:
                raw_bytes = os.fstat(raw_fd).st_size
                raw_hash = output_registry.sha256_fd(raw_fd, raw_bytes)
            finally:
                os.close(raw_fd)
            binding = {
                "file_name": raw.name, "size_bytes": raw_bytes,
                "sha256": raw_hash,
            }
            output_registry._stream_binding(
                directory_fd, binding,
                output_registry._raw_maximum({
                    "offered_count": row_count, "run_id": run_id,
                }),
            )
        finally:
            os.close(directory_fd)
    print("stage17-pilot-semantics-v3: PASS positive=neff_200000_streaming")
    negatives = 0
    for label, mutate in (
        ("one_cell_only", lambda value: value.__setitem__("cells", value["cells"][:1])),
        ("plan_core_drift", lambda value: value.__setitem__("plan_core_sha256", "f" * 64)),
        ("release_worker_drift", lambda value: value["cells"][0]["runs"][0]["runner_admission"].__setitem__("binary_sha256", "f" * 64)),
        ("common_schedule_drift", lambda value: value["cells"][90]["runs"][0].__setitem__("seed_id", "OUTCOME-DEPENDENT")),
        ("embedded_plan_self_hash", lambda value: value["cells"][0]["runs"][0].__setitem__("plan_sha256", "a" * 64)),
    ):
        changed = copy.deepcopy(plan); mutate(changed)
        expect_failure(label, lambda changed=changed: validate(changed)); negatives += 1
    return 2, negatives


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if not arguments.self_test:
        parser.error("--self-test is required")
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-pilot-semantics-v3: FAIL: {exception}")
        return 1
    print(f"stage17-pilot-semantics-v3: PASS positive={positive} negative={negative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
