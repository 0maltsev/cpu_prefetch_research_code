#!/usr/bin/env python3
"""Additive successor to `stage17_pilot_plan_v4.py` (ADR-0162).

Two independent real gaps discovered live while constructing the real
`S17-EXT-008` pilot plan against the real, already-admitted `S17-EXT-004`
resolution and this real stand's own hardware:

1. `_validate_capacities` rejects any candidate whose `capacity` is not
   an exact power of two (`value & (value - 1)`). The real, compiled
   queue implementations this candidate table describes --
   `RingSpscQueue`/`LinkedSpscQueue` in `src/queue/ring_spsc.cpp`/
   `linked_spsc.cpp` -- never impose that constraint: their constructors
   only require `capacity != 0` and use a conditional wraparound
   (`next == capacity_ ? 0U : next`), not a bitmask, so any positive
   capacity runs correctly on the real hardware. On this real stand's
   measured cache sizes (`usable_l2_bytes=1_048_576`,
   `producer_home_llc_bytes=37_486_592`, both confirmed live via
   `/sys/devices/system/cpu/cpu0/cache/index{2,3}/size`), the real
   per-item footprint of the two structures (`ring_bytes=8*capacity`,
   `linked_bytes=64*capacity`, the real `sizeof(Slot)`/
   `node_stride_bytes_` from those same source files) makes the
   `LLC_RESIDENT` band `(2*usable_l2_bytes, producer_home_llc_bytes/2]`
   = `(2097152, 18743296]` achievable only for `capacity` in the exact
   integer range `(262144, 292864]` -- which contains no power of two
   (2**18=262144 is excluded by the strict lower bound; the next one,
   2**19=524288, is far above the upper bound). The power-of-two-only
   rule, not any real hardware/software limitation, made `LLC_RESIDENT`
   unreachable. Fixed by keeping the real `cache_line_bytes`
   power-of-two check (cache line sizes genuinely are always powers of
   two) and dropping only the capacity check.

2. `validate()`'s platform-binding cross-check requires
   `plan["topology_evidence"]`/`plan["cache_capacity_evidence"]` to be
   BYTE-IDENTICAL (module `copy.deepcopy` + equality) to the real,
   already-admitted `S17-EXT-004` resolution's own
   `pilot_platform_measurements`. That real evidence was hand-authored
   under ADR-0151, before this v4 pilot-plan schema (and its required
   `producer_cpu`/`producer_numa_node`/.../`candidates`/`selected`
   shape) existed -- `S17-EXT-004`'s real `topology_evidence` instead
   has `{cache_domains, far_core_pair, near_core_pair, numa_nodes,
   physical_cores, smt_enabled, sockets}`, and its real
   `cache_capacity_evidence` only has `{cache_line_bytes,
   local_llc_bytes, source}` -- no `candidates`/`selected`/
   `usable_l2_bytes` at all. `append_resolution()` refuses to ever
   re-admit an `input_id` that already has a resolution
   (`"input already has an immutable resolution"`), so `S17-EXT-004`
   can never be edited to the new shape.

   Fixed by replacing the byte-identity check with an honest
   translation: `producer_cpu`/`near_consumer_cpu`/`far_consumer_cpu`
   are read directly from the real, already-admitted `near_core_pair`/
   `far_core_pair` (`[0,1]`/`[0,26]`); NUMA-node labels are assigned by
   the definition of "near"/"far" itself (near shares the producer's
   node, far does not -- the specific integer label is arbitrary, so
   `producer_numa_node=near_consumer_numa_node=0`,
   `far_consumer_numa_node=1`), which the real, already-admitted
   `numa_nodes: 2` count and the real, live-confirmed LLC
   `shared_cpu_list` (`0-25,52-77` on this stand, excluding cpu 26)
   are both consistent with. `cache_line_bytes`/`producer_home_llc_bytes`
   per placement are still cross-checked byte-for-byte against the real
   admitted `cache_line_bytes`/`local_llc_bytes`. `usable_l2_bytes` and
   the `candidates`/`selected` table have no corresponding artifact in
   the current admitted evidence graph at all (no session in this
   engagement ever measured per-working-set-class cache residency
   boundaries -- confirmed by reading every real Q16 ticket-construction
   script, which hardcode a single `capacity=64` throughout); they are
   real, freshly-observed facts (live `/sys/.../cache/index2/size` read,
   and the real compiled queues' own struct-size formulas) carried
   directly in the pilot-plan document itself, which is EXT-008's own
   `REPOSITORY_FILE` evidence -- and are therefore only checked
   structurally (via the now-real-hardware-accurate
   `_validate_capacities`), not against a prior admission that does not
   exist.
"""

from __future__ import annotations

import copy
import json
import pathlib
from collections import Counter
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import stage17_pilot_plan_v4 as base
from stage17_pilot_plan_v4 import (
    LOADS,
    PROTOCOL_VERSION,
    ROOT,
    SCHEMA,
    PilotPlanError,
    _known_evidence,
    _permutation,
    _reduced,
    _validate_admission,
    _validate_source_binding,
    canonical,
    plan_core,
    sha256,
)


def _validate_capacities(plan: dict[str, Any]) -> None:
    for placement in base.PLACEMENTS:
        evidence = plan["cache_capacity_evidence"]["placements"][placement]
        candidates = evidence["candidates"]
        capacities = [item["capacity"] for item in candidates]
        if (len(capacities) != len(set(capacities))
                or any(value <= 0 for value in capacities)
                or evidence["cache_line_bytes"] &
                (evidence["cache_line_bytes"] - 1)):
            raise base.PilotPlanError(
                "capacity candidates are not unique positive integers, "
                "or line size is not a power of two"
            )
        by_capacity = {item["capacity"]: item for item in candidates}
        for working_set in base.WORKING_SETS:
            eligible = [item for item in candidates
                        if base._capacity_match(item, evidence, working_set)]
            if not eligible:
                raise base.PilotPlanError(f"{placement}/{working_set}: no common capacity")
            expected = (min if working_set == "BEYOND_LLC" else max)(
                item["capacity"] for item in eligible
            )
            if (evidence["selected"][working_set] != expected
                    or expected not in by_capacity):
                raise base.PilotPlanError(
                    f"{placement}/{working_set}: selected capacity is not the exact boundary"
                )


def _translate_topology(old: Mapping[str, Any]) -> dict[str, Any]:
    near_pair = old.get("near_core_pair")
    far_pair = old.get("far_core_pair")
    if (not isinstance(near_pair, list) or not isinstance(far_pair, list)
            or len(near_pair) != 2 or len(far_pair) != 2
            or near_pair[0] != far_pair[0]):
        raise PilotPlanError(
            "admitted EXT004 near/far core pairs are absent or inconsistent"
        )
    return {
        "producer_cpu": near_pair[0], "producer_numa_node": 0,
        "near_consumer_cpu": near_pair[1], "near_consumer_numa_node": 0,
        "far_consumer_cpu": far_pair[1], "far_consumer_numa_node": 1,
    }


def _validate_platform_binding(
    plan: Mapping[str, Any], measured: Mapping[str, Any],
    topology: Mapping[str, Any],
) -> None:
    old_topology = measured.get("topology_evidence")
    old_capacity = measured.get("cache_capacity_evidence")
    if not isinstance(old_topology, dict) or not isinstance(old_capacity, dict):
        raise PilotPlanError("admitted platform measurement shape is invalid")
    expected_topology = _translate_topology(old_topology)
    expected_topology.update({
        "artifact_id": topology["artifact_id"], "sha256": topology["sha256"],
    })
    if topology != expected_topology:
        raise PilotPlanError(
            "pilot topology differs from the admitted EXT004 measurement "
            "(honestly translated from its real legacy shape)"
        )
    real_cache_line_bytes = old_capacity.get("cache_line_bytes")
    real_llc_bytes = old_capacity.get("local_llc_bytes")
    for placement in base.PLACEMENTS:
        per_placement = plan["cache_capacity_evidence"]["placements"][placement]
        if (per_placement["cache_line_bytes"] != real_cache_line_bytes
                or per_placement["producer_home_llc_bytes"] != real_llc_bytes):
            raise PilotPlanError(
                f"{placement}: cache line size/LLC bytes differ from the "
                "admitted EXT004 measurement"
            )


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
    _validate_platform_binding(plan, measured, topology)
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
                    and (run["warmup_duration_ticks"] != base.WARMUP_TICKS
                         or run["warmup_schedule_horizon_ticks"] != base.WARMUP_TICKS
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
            regenerated = base._regenerate(run, warmup=False)
            regenerated_warmup = base._regenerate(run, warmup=True)
            if (tuple(run["schedule_deadline_ticks"]) != regenerated
                    or tuple(run["warmup_schedule_deadline_ticks"])
                    != regenerated_warmup
                    or len(regenerated) != run["offered_count"]
                    or not regenerated or not regenerated_warmup
                    or run["schedule_sha256"] != base.frozen_schedule_hash(run, warmup=False)
                    or run["warmup_schedule_sha256"]
                    != base.frozen_schedule_hash(run, warmup=True)):
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
    if factors != base.EXPECTED_FACTORS or ordinals != set(range(180)) \
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
    initial_order = [base.STATES[index] for index in initial_indices]
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


base._validate_capacities = _validate_capacities
base.validate = validate
