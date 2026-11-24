#!/usr/bin/env python3
"""Constructive Stage 17 pilot-plan v4 admission.

The JSON schema fixes the closed record shape.  This module proves the
scientific cross-record facts that the schema cannot express: exact loads from
``mu_ref``, cache-capacity selection from every measured footprint candidate,
topology placement, deterministic schedule regeneration, common schedule
families, five-second pre-freeze warm-up, and complete counterbalanced temporal
blocks.  It never supplies a platform value.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import pathlib
import tempfile
from collections import Counter
from fractions import Fraction
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import generate_schedule


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = "config/schemas/stage17-pilot-plan-v4.schema.json"
PROTOCOL_VERSION = "2.0.0-pre.3"
WARMUP_TICKS = 5_000_000_000_000
PACKAGES = ("R0", "R1", "R2", "L0", "L1")
STATES = ("H0", "H1")
PLACEMENTS = ("NEAR", "FAR")
WORKING_SETS = ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC")
LOADS = ("L025", "L050", "L075")
EXPECTED_FACTORS = frozenset(
    (package, state, placement, working_set, load)
    for state in STATES for package in PACKAGES for placement in PLACEMENTS
    for working_set in WORKING_SETS for load in LOADS
)
ADMISSION_KINDS = frozenset({
    "PROTOCOL_SNAPSHOT", "SOURCE_RELEASE", "RUN_PLAN", "WARMUP_SCHEDULE",
    "MEASUREMENT_SCHEDULE", "SEED_DERIVATION", "PLATFORM_INVENTORY",
    "PLATFORM_REQUEST", "PLATFORM_VERIFICATION", "HARDWARE_PREFETCH_MAPPING",
    "SOFTWARE_PREFETCH_MAPPING", "CLOCK_QUALIFICATION", "QUEUE_PROVENANCE",
    "RUNTIME_ATOMIC_LAYOUT", "ADDRESS_RESIDENCY", "STORAGE_BUDGET",
    "DURABILITY_DOMAINS", "CALIBRATION_FREEZE", "EXECUTION_LIMITS",
    "AUTHORITY_CUSTODY", "PHASE_EXECUTION_AUTHORIZATION",
})


class PilotPlanError(RuntimeError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def plan_core(plan: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result.pop("plan_core_sha256", None)
    for cell in result.get("cells", []):
        for run in cell.get("runs", []):
            for key in (
                "runner_admission", "runner_admission_sha256",
                "runner_evidence_set_sha256",
            ):
                run.pop(key, None)
    return result


def _reduced(value: Mapping[str, Any], label: str) -> Fraction:
    try:
        numerator = value["numerator"]
        denominator = value["denominator_ticks"]
    except (KeyError, TypeError) as exception:
        raise PilotPlanError(f"{label}: exact rational is absent") from exception
    if (not isinstance(numerator, int) or isinstance(numerator, bool)
            or not isinstance(denominator, int) or isinstance(denominator, bool)
            or numerator <= 0 or denominator <= 0
            or math.gcd(numerator, denominator) != 1):
        raise PilotPlanError(f"{label}: exact rational is not positive/reduced")
    return Fraction(numerator, denominator)


def _rational(value: Fraction) -> dict[str, int]:
    return {"numerator": value.numerator,
            "denominator_ticks": value.denominator}


def frozen_schedule_hash(run: Mapping[str, Any], *, warmup: bool) -> str:
    prefix = "warmup_" if warmup else ""
    rate = run["nominal_rate"]
    return sha256(canonical({
        "schema_version": "cpu-prefetch-stage17-frozen-schedule/3",
        "arrival_family": "POISSON_EXPONENTIAL",
        "algorithm": run["schedule_algorithm"],
        "algorithm_version": run["schedule_algorithm_version"],
        "seed_id": run[prefix + "seed_id"],
        "master_seed_hex": run["seed_hex"],
        "namespace_id": run[prefix + "schedule_namespace_id"],
        "parent_namespace_id": run[prefix + "schedule_parent_namespace_id"],
        "nominal_rate": rate,
        "deadline_ticks": run[prefix + "schedule_deadline_ticks"],
        "origin_ticks": run[prefix + "schedule_origin_ticks"],
        "horizon_ticks": run[prefix + "schedule_horizon_ticks"],
        "inclusion": "[origin,origin+horizon)",
    }))


def seed_derivation_hash(run: Mapping[str, Any]) -> str:
    return sha256(canonical({
        "schema_version": "cpu-prefetch-stage17-pilot-seed-binding/2",
        "algorithm": run["schedule_algorithm"],
        "algorithm_version": run["schedule_algorithm_version"],
        "master_seed_hex": run["seed_hex"],
        "measurement_seed_id": run["seed_id"],
        "measurement_namespace_id": run["schedule_namespace_id"],
        "measurement_parent_namespace_id": run["schedule_parent_namespace_id"],
        "warmup_seed_id": run["warmup_seed_id"],
        "warmup_namespace_id": run["warmup_schedule_namespace_id"],
        "warmup_parent_namespace_id": run["warmup_schedule_parent_namespace_id"],
    }))


def _regenerate(run: Mapping[str, Any], *, warmup: bool) -> tuple[int, ...]:
    prefix = "warmup_" if warmup else ""
    rate = _reduced(run["nominal_rate"], "nominal_rate")
    spec = generate_schedule.ScheduleSpec(
        schedule_id=run[prefix + "run_id"],
        schedule_kind="WARMUP" if warmup else "PILOT",
        namespace_id=run[prefix + "schedule_namespace_id"],
        parent_namespace_id=run[prefix + "schedule_parent_namespace_id"],
        seed_id=run[prefix + "seed_id"],
        derivation_record_id=run[prefix + "run_id"] + ":derivation",
        master_seed=bytes.fromhex(run["seed_hex"]),
        origin_ticks=run[prefix + "schedule_origin_ticks"],
        horizon_ticks=run[prefix + "schedule_horizon_ticks"],
        numerator_events=rate.numerator,
        denominator_ticks=rate.denominator,
        artifact_id=run[prefix + "run_id"] + ":deadlines",
        artifact_uri=run[prefix + "run_id"] + ".u64be",
    )
    key = generate_schedule._derive_key(spec.master_seed, spec.namespace_id)
    return generate_schedule._generate_deadlines(
        spec, lambda ordinal: generate_schedule._philox_draw(key, ordinal)
    )


def _permutation(count: int, seed_hex: str, namespace: str) -> list[int]:
    key = generate_schedule._derive_key(bytes.fromhex(seed_hex), namespace)
    result = list(range(count))
    draw_ordinal = 0
    for remaining in range(count, 1, -1):
        threshold = ((1 << 64) - remaining) % remaining
        while True:
            draw = generate_schedule._philox_draw(key, draw_ordinal)
            draw_ordinal += 1
            if draw >= threshold:
                break
        selected = draw % remaining
        result[remaining - 1], result[selected] = (
            result[selected], result[remaining - 1]
        )
    return result


def _capacity_match(candidate: Mapping[str, int], evidence: Mapping[str, Any],
                    working_set: str) -> bool:
    b = evidence["cache_line_bytes"]
    l2 = evidence["usable_l2_bytes"]
    llc = evidence["producer_home_llc_bytes"]
    def one(value: int) -> bool:
        if working_set == "L2_RESIDENT":
            return 4 * b < value <= l2 // 2
        if working_set == "LLC_RESIDENT":
            return 2 * l2 < value <= llc // 2
        return value >= 2 * llc
    return one(candidate["ring_bytes"]) and one(candidate["linked_bytes"])


def _validate_capacities(plan: Mapping[str, Any]) -> None:
    for placement in PLACEMENTS:
        evidence = plan["cache_capacity_evidence"]["placements"][placement]
        candidates = evidence["candidates"]
        capacities = [item["capacity"] for item in candidates]
        if (len(capacities) != len(set(capacities))
                or any(value <= 0 or value & (value - 1) for value in capacities)
                or evidence["cache_line_bytes"] &
                (evidence["cache_line_bytes"] - 1)):
            raise PilotPlanError("capacity candidates/line size are not unique powers of two")
        by_capacity = {item["capacity"]: item for item in candidates}
        for working_set in WORKING_SETS:
            eligible = [item for item in candidates
                        if _capacity_match(item, evidence, working_set)]
            if not eligible:
                raise PilotPlanError(f"{placement}/{working_set}: no common capacity")
            expected = (min if working_set == "BEYOND_LLC" else max)(
                item["capacity"] for item in eligible
            )
            if (evidence["selected"][working_set] != expected
                    or expected not in by_capacity):
                raise PilotPlanError(
                    f"{placement}/{working_set}: selected capacity is not the exact boundary"
                )


def _known_evidence(admitted: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for resolution in admitted.values():
        result[resolution.resolution_id] = resolution.sha256
        context = resolution.semantic_context
        if isinstance(context, dict):
            for artifact_id, binding in context.get("artifact_index", {}).items():
                if isinstance(binding, dict) and isinstance(binding.get("sha256"), str):
                    result[artifact_id] = binding["sha256"]
    return result


def _validate_source_binding(binding: Mapping[str, Any], known: Mapping[str, str],
                             label: str) -> None:
    if known.get(binding["artifact_id"]) != binding["sha256"]:
        raise PilotPlanError(f"{label}: source bytes are not admitted evidence")


def _validate_admission(run: Mapping[str, Any], plan: Mapping[str, Any],
                        ext6: Mapping[str, Any], known: Mapping[str, str],
                        runner_schema: Draft202012Validator) -> None:
    admission = run["runner_admission"]
    errors = sorted(runner_schema.iter_errors(admission), key=lambda item: tuple(item.path))
    if errors:
        raise PilotPlanError(f"runner admission schema: {errors[0].message}")
    evidence = admission["evidence"]
    if ({item["kind"] for item in evidence} != ADMISSION_KINDS
            or len({item["binding_id"] for item in evidence}) != 1
            or admission["binding_id"] != evidence[0]["binding_id"]):
        raise PilotPlanError("runner evidence family/binding is incomplete")
    special = {
        "SOURCE_RELEASE": ext6["release_artifact_sha256"],
        "RUN_PLAN": plan["plan_core_sha256"],
        "WARMUP_SCHEDULE": run["warmup_schedule_sha256"],
        "MEASUREMENT_SCHEDULE": run["schedule_sha256"],
        "SEED_DERIVATION": seed_derivation_hash(run),
    }
    for item in evidence:
        expected = special.get(item["kind"], known.get(item["artifact_id"]))
        if expected is None or item["sha256"] != expected:
            raise PilotPlanError("runner evidence is self-selected or unadmitted")
    expected_consumer = (plan["topology_evidence"][
        "near_consumer_cpu" if run["placement"] == "NEAR" else "far_consumer_cpu"
    ])
    if (admission["protocol_version"] != PROTOCOL_VERSION
            or admission["stand_id"] != plan["stand_id"]
            or admission["source_revision"] != ext6["source_revision"]
            or admission["binary_sha256"] != ext6["release_artifact_sha256"]
            or admission["package"] != run["package"]
            or admission["placement"] != run["placement"]
            or admission["producer_cpu"] != plan["topology_evidence"]["producer_cpu"]
            or admission["consumer_cpu"] != expected_consumer
            or run["runner_admission_sha256"] != sha256(canonical(admission))
            or run["runner_evidence_set_sha256"] != sha256(canonical(evidence))):
        raise PilotPlanError("runner admission/release/topology lineage drifted")


def validate(plan: dict[str, Any], *, stand_id: str,
             synthetic_test_only: bool, admitted_resolutions: Mapping[str, Any],
             repository_root: pathlib.Path = ROOT) -> None:
    schema = json.loads((repository_root / SCHEMA).read_bytes())
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(plan),
                    key=lambda item: tuple(item.path))
    if errors:
        raise PilotPlanError(f"pilot plan schema: {errors[0].message}")
    if (plan["stand_id"] != stand_id
            or plan["synthetic_test_only"] is not synthetic_test_only
            or plan["protocol_version"] != PROTOCOL_VERSION
            or plan["plan_core_sha256"] != sha256(canonical(plan_core(plan)))):
        raise PilotPlanError("pilot plan identity/classification/core hash drifted")
    if plan["per_run_deadline_seconds"] != 180:
        raise PilotPlanError("per-run deadline is not 180 seconds")
    lower_bound = sum(
        run["warmup_duration_ticks"] + run["duration_ticks"]
        for cell in plan["cells"] for run in cell["runs"]
    ) + plan["recovery"]["duration_ticks"] * plan["repetitions_per_cell"]
    if lower_bound <= plan["per_run_deadline_seconds"] * 1_000_000_000_000:
        raise PilotPlanError("pilot duration lower bound does not prove session necessity")
    mu_ref = _reduced(plan["mu_ref"], "mu_ref")
    expected_loads = {
        "L025": mu_ref / 4, "L050": mu_ref / 2, "L075": 3 * mu_ref / 4,
    }
    actual_loads = {
        name: _reduced(plan["load_rates"][name], f"load_rates/{name}")
        for name in LOADS
    }
    if actual_loads != expected_loads or len(set(actual_loads.values())) != 3:
        raise PilotPlanError("load rates are not exact distinct mu_ref fractions")
    _validate_capacities(plan)
    topology = plan["topology_evidence"]
    if (topology["producer_cpu"] in {
            topology["near_consumer_cpu"], topology["far_consumer_cpu"]}
            or topology["near_consumer_numa_node"] != topology["producer_numa_node"]
            or topology["far_consumer_numa_node"] == topology["producer_numa_node"]):
        raise PilotPlanError("near/far topology does not prove the registered placement")
    known = _known_evidence(admitted_resolutions)
    for label, binding in (
        ("mu_ref", plan["mu_ref_source"]),
        ("cache capacity", plan["cache_capacity_evidence"]),
        ("topology", plan["topology_evidence"]),
    ):
        _validate_source_binding(binding, known, label)
    platform_context = admitted_resolutions["S17-EXT-004"].semantic_context
    if not isinstance(platform_context, dict):
        raise PilotPlanError("admitted EXT004 platform context is absent")
    measured = platform_context.get("pilot_platform_measurements")
    if not isinstance(measured, dict):
        raise PilotPlanError("admitted pilot platform measurements are absent")
    expected_topology = copy.deepcopy(measured.get("topology_evidence"))
    expected_capacity = copy.deepcopy(measured.get("cache_capacity_evidence"))
    if not isinstance(expected_topology, dict) or not isinstance(
            expected_capacity, dict):
        raise PilotPlanError("admitted platform measurement shape is invalid")
    expected_topology.update({
        "artifact_id": plan["topology_evidence"]["artifact_id"],
        "sha256": plan["topology_evidence"]["sha256"],
    })
    expected_capacity.update({
        "artifact_id": plan["cache_capacity_evidence"]["artifact_id"],
        "sha256": plan["cache_capacity_evidence"]["sha256"],
    })
    if (topology != expected_topology
            or plan["cache_capacity_evidence"] != expected_capacity):
        raise PilotPlanError(
            "pilot topology/cache values differ from admitted measurements"
        )
    ext6_context = admitted_resolutions["S17-EXT-006"].semantic_context
    if not isinstance(ext6_context, dict):
        raise PilotPlanError("admitted EXT006 release context is absent")
    runner_schema_doc = json.loads(
        (repository_root / "config/schemas/runner-admission-v4.schema.json").read_bytes()
    )
    runner_schema = Draft202012Validator(runner_schema_doc)
    factors: set[tuple[str, str, str, str, str]] = set()
    ordinals: set[int] = set()
    run_ids: set[str] = set()
    namespace_roles: dict[str, str] = {}
    common: dict[tuple[str, str, str, int], list[tuple[Any, ...]]] = {}
    temporal: dict[int, list[tuple[int, str, int, str]]] = {
        repetition: [] for repetition in range(plan["repetitions_per_cell"])
    }
    for cell in plan["cells"]:
        factor = (cell["package"], cell["hardware_state"], cell["placement"],
                  cell["working_set_class"], cell["load_level"])
        if (factor in factors or cell["cell_ordinal"] in ordinals
                or len(cell["runs"]) != plan["repetitions_per_cell"]):
            raise PilotPlanError("pilot Cartesian factors/ordinals are duplicated")
        factors.add(factor); ordinals.add(cell["cell_ordinal"])
        for repetition, run in enumerate(cell["runs"]):
            expected_capacity = plan["cache_capacity_evidence"]["placements"][
                run["placement"]
            ]["selected"][run["working_set_class"]]
            expected_consumer = topology[
                "near_consumer_cpu" if run["placement"] == "NEAR"
                else "far_consumer_cpu"
            ]
            if (run["run_id"] in run_ids or run["cell_ordinal"] != cell["cell_ordinal"]
                    or run["repetition_ordinal"] != repetition
                    or tuple(run[name] for name in (
                        "package", "hardware_state", "placement",
                        "working_set_class", "load_level")) != factor
                    or run["capacity"] != expected_capacity
                    or _reduced(run["nominal_rate"], "run nominal rate")
                    != actual_loads[run["load_level"]]
                    or run["producer_cpu"] != topology["producer_cpu"]
                    or run["consumer_cpu"] != expected_consumer
                    or run["shared_memory_node"] != topology["producer_numa_node"]
                    or run["cache_line_bytes"] != plan["cache_capacity_evidence"][
                        "placements"
                    ][run["placement"]]["cache_line_bytes"]
                    or run["duration_ticks"] != run["schedule_horizon_ticks"]
                    or run["schedule_origin_ticks"] + run["schedule_horizon_ticks"]
                    > (1 << 64) - 1):
                raise PilotPlanError("pilot run factor/rate/capacity/topology drifted")
            if (run["warmup_regime"] == "PRE_FREEZE_BOOTSTRAP"
                    and (run["warmup_duration_ticks"] != WARMUP_TICKS
                         or run["warmup_schedule_horizon_ticks"] != WARMUP_TICKS
                         or run["warmup_freeze_ref"] is not None)):
                raise PilotPlanError("pre-freeze warm-up is not exactly five seconds")
            if (run["warmup_regime"] == "FROZEN_LATER_WARMUP"
                    and run["warmup_freeze_ref"] is None):
                raise PilotPlanError("later warm-up lacks the admitted freeze reference")
            for namespace, role in (
                (run["schedule_namespace_id"], "PILOT"),
                (run["warmup_schedule_namespace_id"], "WARMUP"),
            ):
                prior = namespace_roles.setdefault(namespace, role)
                if prior != role:
                    raise PilotPlanError("warm-up and measurement namespaces overlap")
            regenerated = _regenerate(run, warmup=False)
            regenerated_warmup = _regenerate(run, warmup=True)
            if (tuple(run["schedule_deadline_ticks"]) != regenerated
                    or tuple(run["warmup_schedule_deadline_ticks"])
                    != regenerated_warmup
                    or len(regenerated) != run["offered_count"]
                    or not regenerated or not regenerated_warmup
                    or run["schedule_sha256"] != frozen_schedule_hash(run, warmup=False)
                    or run["warmup_schedule_sha256"]
                    != frozen_schedule_hash(run, warmup=True)):
                raise PilotPlanError("schedule does not reproduce from the frozen inputs")
            _validate_admission(run, plan, ext6_context, known, runner_schema)
            run_ids.add(run["run_id"])
            temporal[repetition].append((
                run["execution_ordinal"], run["hardware_state"],
                run["temporal_block_ordinal"], run["recovery_boundary_id"],
            ))
            key = (run["placement"], run["working_set_class"],
                   run["load_level"], repetition)
            common.setdefault(key, []).append((
                run["seed_id"], run["seed_hex"], run["schedule_namespace_id"],
                run["schedule_parent_namespace_id"],
                tuple(run["schedule_deadline_ticks"]), run["schedule_sha256"],
                run["warmup_seed_id"], run["warmup_schedule_namespace_id"],
                tuple(run["warmup_schedule_deadline_ticks"]),
                run["warmup_schedule_sha256"], run["capacity"],
                run["shared_memory_node"], run["cache_line_bytes"],
                run["base_page_bytes"],
            ))
    if factors != EXPECTED_FACTORS or ordinals != set(range(180)) \
            or len(run_ids) != 180 * plan["repetitions_per_cell"]:
        raise PilotPlanError("pilot is not the complete 180-cell repeated matrix")
    if (len(common) != 18 * plan["repetitions_per_cell"]
            or any(len(values) != 10 or len(set(values)) != 1
                   for values in common.values())):
        raise PilotPlanError("matched treatments do not use one common schedule/mapping")
    if len({next(iter(values))[4] for values in common.values()}) < 3:
        raise PilotPlanError("load schedules collapsed to an identical deadline family")
    if len(plan["whole_plot_orders"]) != plan["repetitions_per_cell"]:
        raise PilotPlanError("one whole-plot order is required per temporal block")
    temporal_config = plan["temporal_order"]
    initial_indices = _permutation(
        2, temporal_config["seed_hex"],
        temporal_config["namespace_prefix"] + "/whole-plot-order",
    )
    initial_order = [STATES[index] for index in initial_indices]
    expected_orders = [
        initial_order if repetition % 2 == 0 else list(reversed(initial_order))
        for repetition in range(plan["repetitions_per_cell"])
    ]
    if plan["whole_plot_orders"] != expected_orders:
        raise PilotPlanError("whole-plot order does not reproduce from the frozen seed")
    order_counts = Counter(tuple(item) for item in plan["whole_plot_orders"])
    if (set(order_counts) != {("H0", "H1"), ("H1", "H0")}
            or abs(order_counts[("H0", "H1")] - order_counts[("H1", "H0")]) > 1):
        raise PilotPlanError("whole-plot orders are not counterbalanced")
    for repetition, observations in temporal.items():
        ordered = sorted(observations)
        if [item[0] for item in ordered] != list(range(180)):
            raise PilotPlanError("execution ordinals are incomplete within a block")
        expected_order = plan["whole_plot_orders"][repetition]
        if ({item[2] for item in ordered[:90]} != {2 * repetition}
                or {item[2] for item in ordered[90:]} != {2 * repetition + 1}
                or {item[1] for item in ordered[:90]} != {expected_order[0]}
                or {item[1] for item in ordered[90:]} != {expected_order[1]}
                or len({item[3] for item in ordered}) != 2):
            raise PilotPlanError("temporal block/whole-plot/recovery ordering drifted")
        expected_ordinals: list[int] = []
        for state in expected_order:
            state_cells = sorted(
                cell["cell_ordinal"] for cell in plan["cells"]
                if cell["hardware_state"] == state
            )
            permutation = _permutation(
                len(state_cells), temporal_config["seed_hex"],
                temporal_config["namespace_prefix"] +
                f"/repetition-{repetition}/{state}/cell-order",
            )
            expected_ordinals.extend(state_cells[index] for index in permutation)
        actual_ordinals = [
            next(cell["cell_ordinal"] for cell in plan["cells"]
                 if any(run["repetition_ordinal"] == repetition
                        and run["execution_ordinal"] == execution
                        for run in cell["runs"]))
            for execution in range(180)
        ]
        if actual_ordinals != expected_ordinals:
            raise PilotPlanError("within-whole-plot order is not the frozen permutation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=pathlib.Path)
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()
    if args.plan is None:
        raise PilotPlanError("--plan is required")
    plan = json.loads(args.plan.read_bytes())
    schema = json.loads((ROOT / SCHEMA).read_bytes())
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(plan))
    if errors:
        raise PilotPlanError(errors[0].message)
    if not args.schema_only:
        raise PilotPlanError(
            "production semantic validation requires admitted-resolution contexts"
        )
    print("stage17-pilot-plan-v4: PASS schema")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, PilotPlanError) as error:
        print(f"stage17-pilot-plan-v4: FAIL: {error}", file=__import__("sys").stderr)
        raise SystemExit(1) from error
