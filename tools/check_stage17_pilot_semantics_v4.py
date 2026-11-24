#!/usr/bin/env python3
"""Focused constructive Stage 17 pilot-plan v4 regressions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import types
from fractions import Fraction
from typing import Any, Callable

import generate_schedule
import stage17_pilot_plan_v4 as pilot


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator,
            "denominator_ticks": value.denominator}


def admitted() -> dict[str, Any]:
    artifact_index = {
        f"ADMITTED-{index:02d}": {"sha256": f"{index:064x}"}
        for index in range(1, 50)
    }
    artifact_index.update({
        "MU-REF-EVIDENCE": {"sha256": "a1" * 32},
        "CAPACITY-EVIDENCE": {"sha256": "a2" * 32},
        "TOPOLOGY-EVIDENCE": {"sha256": "a3" * 32},
    })
    result: dict[str, Any] = {}
    for index in range(1, 11):
        input_id = f"S17-EXT-{index:03d}"
        context: dict[str, Any] = {"artifact_index": artifact_index}
        if index == 6:
            context.update({
                "source_revision": "1" * 40,
                "release_artifact_sha256": "b" * 64,
            })
        result[input_id] = types.SimpleNamespace(
            input_id=input_id, resolution_id=f"SYNTHETIC-{input_id}-RESOLUTION",
            sha256=f"{100 + index:064x}", semantic_context=context,
        )
    return result


def _deadlines(seed_hex: str, namespace: str, parent: str, seed_id: str,
               rate: Fraction, horizon: int, kind: str) -> list[int]:
    spec = generate_schedule.ScheduleSpec(
        schedule_id=namespace + ":schedule", schedule_kind=kind,
        namespace_id=namespace, parent_namespace_id=parent, seed_id=seed_id,
        derivation_record_id=namespace + ":derivation",
        master_seed=bytes.fromhex(seed_hex), origin_ticks=0,
        horizon_ticks=horizon, numerator_events=rate.numerator,
        denominator_ticks=rate.denominator, artifact_id=namespace + ":artifact",
        artifact_uri=namespace + ".u64be",
    )
    key = generate_schedule._derive_key(spec.master_seed, spec.namespace_id)
    return list(generate_schedule._generate_deadlines(
        spec, lambda ordinal: generate_schedule._philox_draw(key, ordinal)
    ))


def fixture(
    repetitions: int = 2, *, resolutions: dict[str, Any] | None = None,
    source_revision: str | None = None, worker_sha256: str | None = None,
    q15_w_result_sha256: str | None = None,
    q15_prestate: list[dict[str, Any]] | None = None,
    source_bindings: dict[str, dict[str, str]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolutions = admitted() if resolutions is None else resolutions
    ext6_context = resolutions["S17-EXT-006"].semantic_context
    if not isinstance(ext6_context, dict):
        raise RuntimeError("synthetic EXT006 context is absent")
    if source_revision is not None:
        ext6_context["source_revision"] = source_revision
    if worker_sha256 is not None:
        ext6_context["release_artifact_sha256"] = worker_sha256
    if source_bindings is None:
        # Standalone unit fixtures own their complete synthetic admission
        # context.  Operational fixtures must instead pass bindings obtained
        # by reloading admitted artifact bytes from disk.
        source_bindings = {
            "mu_ref": {"artifact_id": "MU-REF-EVIDENCE", "sha256": "a1" * 32},
            "capacity": {
                "artifact_id": "CAPACITY-EVIDENCE", "sha256": "a2" * 32,
            },
            "topology": {
                "artifact_id": "TOPOLOGY-EVIDENCE", "sha256": "a3" * 32,
            },
        }
        evidence_owner = resolutions["S17-EXT-007"].semantic_context
        index = evidence_owner.setdefault("artifact_index", {})
        index.update({
            item["artifact_id"]: {"sha256": item["sha256"]}
            for item in source_bindings.values()
        })
    mu_ref = Fraction(4, 1_000_000_000_000)
    load_rates = {
        "L025": mu_ref / 4, "L050": mu_ref / 2, "L075": 3 * mu_ref / 4,
    }
    temporal = {
        "algorithm": "PHILOX4X32-10-HMAC-SHA256-DESCENDING-UNBIASED-FISHER-YATES",
        "algorithm_version": "1", "seed_hex": "c" * 64,
        "namespace_prefix": "SYNTHETIC/STAGE17/PILOT/ORDER",
        "counterbalance_rule": "RANDOM-FIRST-THEN-ALTERNATE-v1",
    }
    first = [pilot.STATES[index] for index in pilot._permutation(
        2, temporal["seed_hex"], temporal["namespace_prefix"] + "/whole-plot-order"
    )]
    orders = [first if item % 2 == 0 else list(reversed(first))
              for item in range(repetitions)]
    plan: dict[str, Any] = {
        "schema_version": "cpu-prefetch-stage17-pilot-plan/4",
        "plan_id": "SYNTHETIC-FULL-STAGE17-PILOT-v4",
        "plan_core_sha256": "0" * 64,
        "protocol_version": "2.0.0-pre.3",
        "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
        "time_unit": "PICOSECONDS", "mu_ref": rational(mu_ref),
        "mu_ref_source": source_bindings["mu_ref"],
        "load_rates": {name: rational(value) for name, value in load_rates.items()},
        "cache_capacity_evidence": {
            **source_bindings["capacity"],
            "placements": {
                placement: {
                    "cache_line_bytes": 64, "usable_l2_bytes": 4096,
                    "producer_home_llc_bytes": 65536,
                    "candidates": [
                        {"capacity": 8, "ring_bytes": 600, "linked_bytes": 700},
                        {"capacity": 16, "ring_bytes": 2500, "linked_bytes": 2600},
                        {"capacity": 32, "ring_bytes": 9000, "linked_bytes": 10000},
                        {"capacity": 64, "ring_bytes": 140000, "linked_bytes": 150000},
                    ],
                    "selected": {"L2_RESIDENT": 8, "LLC_RESIDENT": 32,
                                 "BEYOND_LLC": 64},
                } for placement in pilot.PLACEMENTS
            },
        },
        "topology_evidence": {
            **source_bindings["topology"],
            "producer_cpu": 0, "producer_numa_node": 0,
            "near_consumer_cpu": 1, "near_consumer_numa_node": 0,
            "far_consumer_cpu": 26, "far_consumer_numa_node": 1,
        },
        "repetitions_per_cell": repetitions, "temporal_order": temporal,
        "whole_plot_orders": orders,
        "recovery": {"duration_ticks": 1_000_000_000,
                     "acceptance_rule_id": "SYNTHETIC-RECOVERY-v1"},
        "per_run_deadline_seconds": 180,
        "hardware_control": {
            "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
            "q15_w_result_sha256": q15_w_result_sha256 or "d" * 64,
            "prestate": q15_prestate or [
                {"cpu": cpu, "complete_value_hex": "0" * 16}
                for cpu in (0, 1, 26)
            ],
        },
        "cells": [], "treatment_blind": True,
        "confirmatory_outcomes_accessed": False, "synthetic_test_only": True,
        "phase18_authority": False,
    }
    ordinal = 0
    for state in pilot.STATES:
        for package in pilot.PACKAGES:
            for placement in pilot.PLACEMENTS:
                for working_set in pilot.WORKING_SETS:
                    for load in pilot.LOADS:
                        plan["cells"].append({
                            "cell_ordinal": ordinal, "package": package,
                            "hardware_state": state, "placement": placement,
                            "working_set_class": working_set, "load_level": load,
                            "runs": [],
                        })
                        ordinal += 1
    execution: dict[tuple[int, int], int] = {}
    for repetition, order in enumerate(orders):
        sequence: list[int] = []
        for state in order:
            state_cells = sorted(cell["cell_ordinal"] for cell in plan["cells"]
                                 if cell["hardware_state"] == state)
            permutation = pilot._permutation(
                90, temporal["seed_hex"], temporal["namespace_prefix"] +
                f"/repetition-{repetition}/{state}/cell-order",
            )
            sequence.extend(state_cells[index] for index in permutation)
        execution.update({(repetition, cell): index
                          for index, cell in enumerate(sequence)})
    schedule_cache: dict[tuple[str, str, str, int], tuple[Any, ...]] = {}
    for cell in plan["cells"]:
        for repetition in range(repetitions):
            family = (cell["placement"], cell["working_set_class"],
                      cell["load_level"], repetition)
            if family not in schedule_cache:
                token = "/".join(map(str, family))
                seed_hex = digest(token.encode())
                measure_ns = "SYNTHETIC/PILOT/" + token
                warmup_ns = "SYNTHETIC/WARMUP/" + token
                rate = load_rates[cell["load_level"]]
                measurement = _deadlines(
                    seed_hex, measure_ns, "SYNTHETIC/PILOT", "PILOT-" + token,
                    rate, 4_000_000_000_000, "PILOT",
                )
                warmup = _deadlines(
                    seed_hex, warmup_ns, "SYNTHETIC/WARMUP", "WARMUP-" + token,
                    rate, pilot.WARMUP_TICKS, "WARMUP",
                )
                schedule_cache[family] = (
                    seed_hex, measure_ns, warmup_ns, measurement, warmup,
                )
            seed_hex, measure_ns, warmup_ns, measurement, warmup = schedule_cache[family]
            run_id = f"SYNTHETIC-PILOT-C{cell['cell_ordinal']:03d}-R{repetition:03d}"
            run: dict[str, Any] = {
                "cell_ordinal": cell["cell_ordinal"],
                "repetition_ordinal": repetition,
                "hardware_state": cell["hardware_state"],
                "placement": cell["placement"],
                "working_set_class": cell["working_set_class"],
                "load_level": cell["load_level"],
                "capacity": plan["cache_capacity_evidence"]["placements"][
                    cell["placement"]
                ]["selected"][cell["working_set_class"]],
                "offered_count": len(measurement), "package": cell["package"],
                "d2_cache_lines": 2, "schedule_sha256": "0" * 64,
                "nominal_rate": rational(load_rates[cell["load_level"]]),
                "run_id": run_id, "seed_id": "PILOT-" + "/".join(map(str, family)),
                "seed_hex": seed_hex,
                "schedule_algorithm": generate_schedule.SCHEDULE_ALGORITHM,
                "schedule_algorithm_version": generate_schedule.SCHEDULE_VERSION,
                "schedule_namespace_id": measure_ns,
                "schedule_parent_namespace_id": "SYNTHETIC/PILOT",
                "cache_line_bytes": 64, "base_page_bytes": 4096,
                "runner_admission": {}, "runner_admission_sha256": "0" * 64,
                "runner_evidence_set_sha256": "0" * 64,
                "schedule_deadline_ticks": measurement,
                "schedule_origin_ticks": 0,
                "schedule_horizon_ticks": 4_000_000_000_000,
                "duration_ticks": 4_000_000_000_000,
                "warmup_run_id": run_id + ":WARMUP",
                "warmup_regime": "PRE_FREEZE_BOOTSTRAP",
                "warmup_duration_ticks": pilot.WARMUP_TICKS,
                "warmup_freeze_ref": None,
                "warmup_schedule_sha256": "0" * 64,
                "warmup_seed_id": "WARMUP-" + "/".join(map(str, family)),
                "warmup_schedule_namespace_id": warmup_ns,
                "warmup_schedule_parent_namespace_id": "SYNTHETIC/WARMUP",
                "warmup_schedule_deadline_ticks": warmup,
                "warmup_schedule_origin_ticks": 0,
                "warmup_schedule_horizon_ticks": pilot.WARMUP_TICKS,
                "shared_memory_node": 0, "producer_cpu": 0,
                "consumer_cpu": 1 if cell["placement"] == "NEAR" else 26,
                "temporal_block_ordinal": (
                    2 * repetition + orders[repetition].index(cell["hardware_state"])
                ),
                "execution_ordinal": execution[(repetition, cell["cell_ordinal"])],
                "recovery_boundary_id": (
                    f"SYNTHETIC-RECOVERY-R{repetition:03d}-" +
                    cell["hardware_state"]
                ),
            }
            run["schedule_sha256"] = pilot.frozen_schedule_hash(run, warmup=False)
            run["warmup_schedule_sha256"] = pilot.frozen_schedule_hash(run, warmup=True)
            cell["runs"].append(run)
    plan["plan_core_sha256"] = digest(canonical(pilot.plan_core(plan)))
    known = pilot._known_evidence(resolutions)
    generic = iter(sorted(known.items()))
    ext6 = resolutions["S17-EXT-006"].semantic_context
    for cell in plan["cells"]:
        for run in cell["runs"]:
            binding_id = "BINDING-" + run["run_id"]
            special = {
                "SOURCE_RELEASE": ext6["release_artifact_sha256"],
                "RUN_PLAN": plan["plan_core_sha256"],
                "WARMUP_SCHEDULE": run["warmup_schedule_sha256"],
                "MEASUREMENT_SCHEDULE": run["schedule_sha256"],
                "SEED_DERIVATION": pilot.seed_derivation_hash(run),
            }
            evidence = []
            for kind in sorted(pilot.ADMISSION_KINDS):
                if kind in special:
                    artifact_id, value = "DERIVED-" + kind, special[kind]
                else:
                    try:
                        artifact_id, value = next(generic)
                    except StopIteration:
                        generic = iter(sorted(known.items()))
                        artifact_id, value = next(generic)
                evidence.append({
                    "kind": kind, "artifact_id": artifact_id,
                    "path": "admitted/" + artifact_id, "sha256": value,
                    "binding_id": binding_id, "immutable": True, "eligible": True,
                })
            admission = {
                "schema_version": "cpu-prefetch-runner-admission/4",
                "protocol_version": "2.0.0-pre.3",
                "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
                "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
                "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
                "source_revision": ext6["source_revision"],
                "binary_sha256": ext6["release_artifact_sha256"],
                "stand_id": plan["stand_id"], "binding_id": binding_id,
                "package": run["package"], "placement": run["placement"],
                "producer_cpu": run["producer_cpu"],
                "consumer_cpu": run["consumer_cpu"],
                "execution_limits": {"controller_start_poll_limit": 1_000_000,
                                     "worker_start_poll_limit": 1_000_000},
                "evidence": evidence,
            }
            run["runner_admission"] = admission
            run["runner_admission_sha256"] = digest(canonical(admission))
            run["runner_evidence_set_sha256"] = digest(canonical(evidence))
    resolutions["S17-EXT-004"].semantic_context[
        "pilot_platform_measurements"
    ] = {
        "topology_evidence": {
            key: copy.deepcopy(value) for key, value in
            plan["topology_evidence"].items()
            if key not in {"artifact_id", "sha256"}
        },
        "cache_capacity_evidence": {
            key: copy.deepcopy(value) for key, value in
            plan["cache_capacity_evidence"].items()
            if key not in {"artifact_id", "sha256"}
        },
    }
    return plan, resolutions


# Compatibility name used only by the hermetic public-workflow fixture.
plan_fixture = fixture


def expect_failure(label: str, action: Callable[[], None]) -> None:
    try:
        action()
    except BaseException:
        return
    raise RuntimeError(f"negative pilot fixture admitted: {label}")


def self_test() -> tuple[int, int]:
    plan, resolutions = fixture()
    def validate(value: dict[str, Any]) -> None:
        pilot.validate(
            value, stand_id="SYNTHETIC-STAND-NOT-ACCESSED",
            synthetic_test_only=True, admitted_resolutions=resolutions,
        )
    validate(plan)
    positives = 1
    lower_bound_ticks = sum(
        run["warmup_duration_ticks"] + run["duration_ticks"]
        for cell in plan["cells"] for run in cell["runs"]
    ) + plan["recovery"]["duration_ticks"] * plan["repetitions_per_cell"]
    if lower_bound_ticks <= 180 * 1_000_000_000_000:
        raise RuntimeError("pilot lower-bound duration did not exceed 180 seconds")
    positives += 1
    negatives = 0
    mutations: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
        ("identical_loads", lambda value: value["load_rates"].__setitem__(
            "L050", copy.deepcopy(value["load_rates"]["L025"]))),
        ("identical_capacities", lambda value: value["cache_capacity_evidence"][
            "placements"]["NEAR"]["selected"].__setitem__("LLC_RESIDENT", 8)),
        ("short_warmup", lambda value: value["cells"][0]["runs"][0].__setitem__(
            "warmup_duration_ticks", pilot.WARMUP_TICKS - 1)),
        ("temporal_drift", lambda value: value["cells"][0]["runs"][0].__setitem__(
            "execution_ordinal", value["cells"][1]["runs"][0]["execution_ordinal"])),
        ("schedule_drift", lambda value: value["cells"][0]["runs"][0][
            "schedule_deadline_ticks"].__setitem__(0, 0)),
        ("topology_drift", lambda value: value["cells"][0]["runs"][0].__setitem__(
            "shared_memory_node", 1)),
        ("unadmitted_capacity", lambda value: value["cache_capacity_evidence"].__setitem__(
            "sha256", "e" * 64)),
        ("admitted_platform_drift", lambda value: value[
            "cache_capacity_evidence"]["placements"]["NEAR"].__setitem__(
                "usable_l2_bytes", 4160)),
        ("protocol_predecessor", lambda value: value.__setitem__(
            "protocol_version", "2.0.0-pre.2")),
    ]
    for label, mutate in mutations:
        value = copy.deepcopy(plan)
        mutate(value)
        value["plan_core_sha256"] = digest(canonical(pilot.plan_core(value)))
        expect_failure(label, lambda value=value: validate(value))
        negatives += 1
    return positives, negatives


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        raise RuntimeError("--self-test is required")
    positives, negatives = self_test()
    print(f"stage17-pilot-semantics-v4: PASS ({positives} positive, {negatives} negative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
