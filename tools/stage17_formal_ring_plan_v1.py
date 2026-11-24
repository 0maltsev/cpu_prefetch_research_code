"""Pure prospective D212 family contract; declarations grant no run authority.

The single-capture native boundary recomputes layout. This module validates
complete prospective coverage and checked finite budget arithmetic. Hardware,
source qualification, prior-study validity, seed reservation, measured free
resources and phase authorization must be independently bound at admission.
"""
from __future__ import annotations

from dataclasses import dataclass
import pathlib

from jsonschema import Draft202012Validator
import json

from check_canonical import canonicalize
import stage17_formal_storage_budget_v1 as storage_budget
from stage17_discovery_contract_v2 import (
    ContractError, _constant, _geometry, _object, _product, _sum, _text, _uint,
)

VERSION = "cpu-prefetch-stage17-formal-ring-plan/1"
METHOD = "RING-D2-RUNTAIL-LTL95C95-WINDOW-v2"
CUSTODY = "EXT007-RAW-NONE-STAND-PRIMARY-v1"
CONTEXTS = tuple((state, placement, working_set)
                 for state in ("H0", "H1") for placement in ("NEAR", "FAR")
                 for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"))
SCHEMA = pathlib.Path(__file__).resolve().parents[1] / "config/schemas/stage17-formal-ring-native-input-v1.schema.json"


@dataclass(frozen=True)
class CaptureBudget:
    setup_ns: int
    publication_ns: int
    cleanup_ns: int
    watchdog_ns: int
    publication_memory_bytes: int
    other_memory_bytes: int
    memory_bytes: int
    metadata_output_bytes: int
    max_output_bytes: int


@dataclass(frozen=True)
class FamilyBudget:
    setup_ns: int
    cleanup_ns: int
    watchdog_ns: int
    controller_memory_bytes: int
    memory_bytes: int
    metadata_output_bytes: int
    max_output_bytes: int
    analysis_scratch_bytes: int
    disk_reserve_bytes: int
    required_free_disk_bytes: int


@dataclass(frozen=True)
class CaptureExtent:
    ordinal: int
    raw_bytes: int
    largest_raw_copy_bytes: int
    mapping_bytes: int
    required_watchdog_ns: int
    declared: CaptureBudget


@dataclass(frozen=True)
class FamilyExtent:
    captures: tuple[CaptureExtent, ...]
    required_watchdog_ns: int
    peak_memory_bytes: int
    maximum_output_bytes: int
    required_free_disk_bytes: int
    declared: FamilyBudget
    execution_authority: bool = False


def _budget(value, cls, path):
    fields = tuple(cls.__dataclass_fields__)
    obj = _object(value, " ".join(fields), path)
    return cls(**{name: _uint(obj[name], path + "." + name, 1) for name in fields})


def _require(condition, path, message):
    if not condition:
        raise ContractError(f"{path}: {message}")


def _raw_extent(capture, resources, path):
    """Exact existing LP identity + u64 bodies, including every warmup/drain row."""
    extents = []
    for index, phase in enumerate(("warmup", "measurement")):
        run_id = capture[phase]["run_id"].encode("utf-8")
        prefix = _uint((4 + len(run_id) + 7) // 8 * 8, path + ".prefix")
        rows = resources["phase_capacity"][index]
        # Native row bodies: producer 15 words; consumer 10; D214 demand 9.
        for name, body in (("producer_primary_rows", 120),
                           ("consumer_primary_rows", 80),
                           ("producer_demand_rows", 72),
                           ("consumer_demand_rows", 72)):
            extents.append(_product(rows[name], prefix + body, path + "." + name))
        bounds = capture["budget"]["phases"][index]
        for name in ("producer_primary_rows", "consumer_primary_rows", "producer_demand_rows"):
            _require(rows[name] >= bounds["producer_attempt_limit"], path + "." + name,
                     "does not cover the prospective producer bound")
        _require(rows["consumer_demand_rows"] >= bounds["consumer_poll_limit"], path,
                 "consumer demand capacity does not cover all prospective polls")
    return _sum(extents, path + ".raw_bytes"), max(extents)


def validate_plan(value) -> FamilyExtent:
    return _validate_plan(value, archived=False)


def _validate_plan(value, *, archived: bool, continuation: bool = False) -> FamilyExtent:
    # Only the explicit D240 successor can select a partial execution family.
    # Historical callers retain exact full-family coverage and version checks.
    if continuation:
        from stage17_formal_ring_continuation_v1 import validate_declaration
        _require(archived, "plan", "continuation requires archival custody")
        validate_declaration(value)
    # JSON Schema accepts integral floats as integers, but canonical native
    # contracts require actual integer tokens throughout every nested input.
    def reject_floats(item):
        _require(not isinstance(item, float), "plan", "floating-point input is forbidden")
        if isinstance(item, dict):
            for nested in item.values(): reject_floats(nested)
        elif isinstance(item, list):
            for nested in item: reject_floats(nested)
    reject_floats(value)
    plan = _object(value, "schema_version plan_id protocol_version action_id method_id "
                   "source_revision clean_source stand_id repetitions_per_context measurement_ns "
                   "minimum_observations_per_series warmup_namespace measurement_namespace "
                   "custody_policy_id captures budget" + (" storage" if archived else "")
                   + (" continuation" if continuation else ""), "plan")
    version = VERSION.replace("/1", "/3" if continuation else "/2") if archived else VERSION
    for name, expected in (("schema_version", version), ("protocol_version", "2.0.0-pre.3"),
                           ("action_id", "Q16a"), ("method_id", METHOD),
                           ("clean_source", True), ("custody_policy_id",
                            storage_budget.POLICY if archived else CUSTODY)):
        _constant(plan[name], expected, "plan." + name)
    for name in ("plan_id", "stand_id", "warmup_namespace", "measurement_namespace"):
        _text(plan[name], "plan." + name)
    _text(plan["source_revision"], "plan.source_revision", r"[0-9a-f]{40}")
    _require(plan["warmup_namespace"] != plan["measurement_namespace"], "plan", "phase namespaces coincide")
    repetitions = _uint(plan["repetitions_per_context"], "plan.repetitions_per_context", 59)
    duration = _uint(plan["measurement_ns"], "plan.measurement_ns", 1)
    _product(duration, 1000, "plan.measurement_ticks")
    minimum = _uint(plan["minimum_observations_per_series"], "plan.minimum_observations_per_series", 1)
    first_context = 3 if continuation else 0
    expected_count = _product(len(CONTEXTS) - first_context, repetitions, "plan.capture_count")
    captures = plan["captures"]
    _require(isinstance(captures, list) and len(captures) == expected_count,
             "plan.captures", "requires every prospectively frozen context/repetition")
    validator = Draft202012Validator(json.loads(SCHEMA.read_text(encoding="utf-8")))
    seen = {name: set() for name in ("run_id", "seed_id", "seed_hex")}
    geometries = {}
    layouts = {}
    extents = []
    for ordinal, item in enumerate(captures):
        path = f"plan.captures[{ordinal}]"
        item = _object(item, "capture resources monitoring execution_budget", path)
        native = {name: item[name] for name in ("capture", "resources", "monitoring")}
        errors = list(validator.iter_errors(native))
        _require(not errors, path, str(errors[0].message) if errors else "")
        capture, resources, monitoring = (item[name] for name in ("capture", "resources", "monitoring"))
        context, repetition = divmod(ordinal, repetitions)
        context += first_context
        state, placement, working_set = CONTEXTS[context]
        for name, expected in (("ordinal", ordinal), ("context_ordinal", context),
                               ("repetition_ordinal", repetition), ("hardware_state", state),
                               ("placement", placement), ("working_set_class", working_set),
                               ("measurement_ns", duration),
                               ("minimum_observations_per_series", minimum)):
            _constant(capture[name], expected, path + ".capture." + name)
        for name, source in (("resources", resources), ("monitoring", monitoring)):
            _constant(source["ordinal"], ordinal, path + "." + name + ".ordinal")
        for phase in ("warmup", "measurement"):
            identity = capture[phase]
            for field in ("run_id", "seed_id", "namespace_id"):
                _text(identity[field], path + "." + phase + "." + field)
            _text(identity["seed_hex"], path + "." + phase + ".seed_hex", r"[0-9a-f]{64}")
            _constant(identity["namespace_id"], plan[phase + "_namespace"], path + "." + phase + ".namespace_id")
            for field, used in seen.items():
                _require(identity[field] not in used, path + "." + phase + "." + field,
                         "reused run/seed identity or seed value")
                used.add(identity[field])
        _constant(capture["arena_seed"], capture["measurement"], path + ".arena_seed")
        geometry = capture["geometry"]
        _geometry(geometry, placement, path + ".geometry")
        key = (placement, working_set)
        if key in geometries:
            _constant(geometry, geometries[key], path + ".geometry")
        geometries[key] = geometry
        # Prospective CPU topology/readback remains a separate qualified binding.
        _require(geometry["producer_cpu"] != geometry["consumer_cpu"], path, "workers share a CPU")
        _require((geometry["producer_node"] == geometry["consumer_node"]) == (placement == "NEAR"), path,
                 "node relationship differs from placement")
        _constant(geometry["shared_node"], geometry["producer_node"], path + ".shared_node")
        for role in ("producer", "consumer"):
            stack = resources["workers"][role + "_stack"]
            _constant(stack["owner_cpu"], geometry[role + "_cpu"], path + ".workers." + role)
            _constant(stack["requested_node"], geometry[role + "_node"], path + ".workers." + role)
        _require(resources["controller_stack"]["owner_cpu"] not in
                 (geometry["producer_cpu"], geometry["consumer_cpu"]), path, "controller shares a worker CPU")
        for index, phase in enumerate(capture["budget"]["phases"]):
            phase_ns = capture["warmup_ns"] if index == 0 else duration
            _require(monitoring["during_offset_ticks"][index] < _product(phase_ns, 1000, path), path,
                     "during observation begins outside its phase")
            _product(phase["drain_ns"], 1000, path + ".drain_ticks")
        measurement = capture["budget"]["phases"][1]
        _require(minimum < min(measurement["producer_attempt_limit"], measurement["consumer_poll_limit"]),
                 path, "watchdog bounds cannot supply the required issue count")
        # Same context repeats use identical prospective bounds, not outcome adaptation.
        invariant = {"budget": capture["budget"], "resources": {k: v for k, v in resources.items() if k != "ordinal"},
                     "monitoring": {k: v for k, v in monitoring.items() if k != "ordinal"}}
        if context in layouts:
            _constant(invariant, layouts[context], path + ".context_bounds")
        layouts[context] = invariant
        raw, largest = _raw_extent(capture, resources, path)
        budget = _budget(item["execution_budget"], CaptureBudget, path + ".execution_budget")
        known_time = _sum([budget.setup_ns, capture["warmup_ns"], duration,
                          *(phase["drain_ns"] for phase in capture["budget"]["phases"]),
                          budget.publication_ns, budget.cleanup_ns], path + ".required_watchdog_ns")
        mapping = resources["total_mapping_bytes"]
        _require(mapping <= capture["budget"]["memory_bytes"], path, "native mapping ceiling is insufficient")
        _require(budget.watchdog_ns >= known_time, path, "watchdog omits required phase/publication time")
        _require(budget.publication_memory_bytes >= largest, path, "publication memory omits largest raw copy")
        memory = _sum([mapping, budget.publication_memory_bytes, budget.other_memory_bytes], path + ".required_memory")
        _require(budget.memory_bytes >= memory, path, "process memory omits declared mapped/publication/other extents")
        _require(budget.max_output_bytes >= _sum([raw, budget.metadata_output_bytes], path + ".required_output"),
                 path, "output ceiling omits raw or metadata")
        extents.append(CaptureExtent(ordinal, raw, largest, mapping, known_time, budget))
    family = _budget(plan["budget"], FamilyBudget, "plan.budget")
    watchdog = _sum([family.setup_ns, family.cleanup_ns, *(c.declared.watchdog_ns for c in extents)], "plan.required_watchdog_ns")
    memory = _sum([family.controller_memory_bytes, max(c.declared.memory_bytes for c in extents)], "plan.peak_memory_bytes")
    output = _sum([family.metadata_output_bytes, *(c.declared.max_output_bytes for c in extents)], "plan.maximum_output_bytes")
    if archived:
        storage = storage_budget.validate_storage_plan(
            plan["storage"], [c.declared for c in extents], family,
            native_family_watchdog_ns=watchdog, native_family_memory_bytes=memory,
            logical_output_bound_bytes=output)
        disk = storage.required_initial_free_bytes
        watchdog = storage.minimum_family_watchdog_ns
        memory = storage.minimum_family_memory_bytes
    else:
        disk = _sum([output, family.analysis_scratch_bytes, family.disk_reserve_bytes], "plan.required_free_disk_bytes")
    for actual, required, label in ((family.watchdog_ns, watchdog, "watchdog"),
                                    (family.memory_bytes, memory, "memory"),
                                    (family.max_output_bytes, output, "output"),
                                    (family.required_free_disk_bytes, disk, "free disk")):
        _require(actual >= required, "plan.budget", label + " ceiling omits a declared component")
    _require(family.controller_memory_bytes >= len(canonicalize(plan).encode("utf-8")), "plan.budget",
             "controller budget cannot even hold the canonical prospective plan")
    return FamilyExtent(tuple(extents), watchdog, memory, output, disk, family)
