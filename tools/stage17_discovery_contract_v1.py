"""Pure D-178 prospective plan/request validation; never execution authority.

Bindings are declarations, not verified files or observed hardware. Admission
must independently verify their bytes, provenance, namespace registration,
topology, resource sizing and monitoring coverage against the qualified runner.
All durations are integer nanoseconds; runtime tick conversion is a separate
checked boundary. Captures execute sequentially, with no implicit retry.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from check_canonical import canonicalize
from stage17_q16a_discovery_v1 import (
    CONTEXTS, DESIGN_ID, MINIMUM_OBSERVATIONS_PER_SEQUENCE, required_captures,
)

SCHEMA_PATH = "config/schemas/stage17-discovery-plan-v1.schema.json"
PLAN_VERSION = "cpu-prefetch-stage17-discovery-plan/1"
REQUEST_VERSION = "cpu-prefetch-stage17-discovery-request/1"
MAX_U64 = (1 << 64) - 1
WARMUP_NS = 5_000_000_000
SEQUENCES = ("producer_demand", "consumer_demand", "producer_issue", "consumer_issue")


class ContractError(ValueError):
    """A path-specific structural, identity or finite-budget violation."""


def _fail(path: str, reason: str) -> None:
    raise ContractError(f"{path}: {reason}")


def _object(value: Any, names: str, path: str) -> dict[str, Any]:
    expected = set(names.split())
    if not isinstance(value, dict) or set(value) != expected:
        _fail(path, f"requires exactly fields {sorted(expected)}")
    return value


def _uint(value: Any, path: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_U64:
        _fail(path, f"requires integer in [{minimum}, {MAX_U64}]")
    return value


def _text(value: Any, path: str, pattern: str = r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}") -> str:
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        _fail(path, "invalid identifier or digest")
    return value


def _constant(value: Any, expected: Any, path: str) -> None:
    if type(value) is not type(expected) or value != expected:
        _fail(path, f"requires {expected!r}")


def _sum(values: tuple[int, ...] | list[int], path: str) -> int:
    return _uint(sum(values), path)


def _product(left: int, right: int, path: str) -> int:
    return _uint(left * right, path)


@dataclass(frozen=True)
class Binding:
    artifact_id: str
    size_bytes: int
    sha256: str


def _binding(value: Any, path: str) -> Binding:
    obj = _object(value, "artifact_id size_bytes sha256", path)
    return Binding(_text(obj["artifact_id"], path + ".artifact_id"),
                   _uint(obj["size_bytes"], path + ".size_bytes", 1),
                   _text(obj["sha256"], path + ".sha256", r"[0-9a-f]{64}"))


@dataclass(frozen=True)
class Dependency:
    input_id: str
    resolution: Binding


@dataclass(frozen=True)
class PhaseIdentity:
    run_id: str
    seed_id: str
    seed_hex: str
    namespace_id: str


def _identity(value: Any, namespace: str, path: str) -> PhaseIdentity:
    obj = _object(value, "run_id seed_id seed_hex namespace_id", path)
    _constant(obj["namespace_id"], namespace, path + ".namespace_id")
    return PhaseIdentity(_text(obj["run_id"], path + ".run_id"),
                         _text(obj["seed_id"], path + ".seed_id"),
                         _text(obj["seed_hex"], path + ".seed_hex", r"[0-9a-f]{64}"),
                         namespace)


@dataclass(frozen=True)
class Geometry:
    producer_cpu: int
    consumer_cpu: int
    producer_node: int
    consumer_node: int
    shared_node: int
    capacity: int
    cache_line_bytes: int
    base_page_bytes: int


def _geometry(value: Any, placement: str, path: str) -> Geometry:
    names = tuple(Geometry.__dataclass_fields__)
    obj = _object(value, " ".join(names), path)
    values = {name: _uint(obj[name], path + "." + name,
                         1 if name in names[5:] else 0) for name in names}
    result = Geometry(**values)
    if result.producer_cpu == result.consumer_cpu:
        _fail(path, "producer and consumer must use distinct CPUs")
    if (result.producer_node == result.consumer_node) != (placement == "NEAR"):
        _fail(path, "node relationship differs from placement")
    if result.shared_node != result.producer_node:
        _fail(path, "shared data must be producer-home")
    for name in names[5:]:
        number = values[name]
        if number & (number - 1):
            _fail(path + "." + name, "requires power-of-two geometry")
    if result.base_page_bytes < result.cache_line_bytes:
        _fail(path, "base page is smaller than cache line")
    _product(result.capacity, result.cache_line_bytes, path + ".record_arena_bytes")
    return result


@dataclass(frozen=True)
class CaptureBudget:
    setup_ns: int
    drain_ns: int
    publication_ns: int
    cleanup_ns: int
    watchdog_ns: int
    warmup_attempt_capacity: int
    measurement_attempt_capacity: int
    drain_attempt_capacity: int
    barrier_poll_limit: int
    memory_bytes: int
    retained_output_bytes: int
    metadata_output_bytes: int
    max_output_bytes: int


def _capture_budget(value: Any, measurement_ns: int, path: str) -> CaptureBudget:
    names = tuple(CaptureBudget.__dataclass_fields__)
    obj = _object(value, " ".join(names), path)
    result = CaptureBudget(**{name: _uint(obj[name], path + "." + name, 1)
                              for name in names})
    # One drain_ns window per phase, matching DiscoverySessionPlan. setup_ns
    # includes preparation, barriers, reset and out-of-window monitoring.
    drains = _product(result.drain_ns, 2, path + ".both_drains_ns")
    known = _sum([result.setup_ns, WARMUP_NS, measurement_ns, drains,
                  result.publication_ns, result.cleanup_ns], path + ".known_ns")
    if result.watchdog_ns < known:
        _fail(path + ".watchdog_ns", "does not cover all declared stages")
    if result.retained_output_bytes > result.memory_bytes:
        _fail(path + ".memory_bytes", "does not cover retained output buffers")
    output = _sum([result.retained_output_bytes, result.metadata_output_bytes],
                  path + ".output_bytes")
    if result.max_output_bytes < output:
        _fail(path + ".max_output_bytes", "does not cover declared output")
    return result


@dataclass(frozen=True)
class Capture:
    ordinal: int
    context_ordinal: int
    hardware_state: str
    placement: str
    working_set_class: str
    measurement_ns: int
    warmup: PhaseIdentity
    measurement: PhaseIdentity
    arena_seed: PhaseIdentity
    geometry: Geometry
    budget: CaptureBudget


@dataclass(frozen=True)
class CustodyDomain:
    domain_id: str
    copies: int
    budget_bytes: int


@dataclass(frozen=True)
class StudyBudget:
    setup_ns: int
    cleanup_ns: int
    watchdog_ns: int
    controller_memory_bytes: int
    memory_budget_bytes: int
    metadata_output_bytes: int
    output_budget_bytes: int
    custody_domains: tuple[CustodyDomain, ...]


@dataclass(frozen=True)
class DiscoveryPlan:
    plan_id: str
    stand_id: str
    source_revision: str
    release: Binding
    stand: Binding
    qualification: Binding
    resource_plan: Binding
    monitoring_plan: Binding
    namespace_registry: Binding
    dependencies: tuple[Dependency, ...]
    warmup_namespace: str
    measurement_namespace: str
    captures: tuple[Capture, ...]
    budget: StudyBudget
    unavoidable_duration_ns: int
    required_watchdog_ns: int
    peak_memory_bytes: int
    maximum_output_bytes: int
    canonical_bytes: bytes
    sha256: str
    execution_authority: bool = False


def validate_plan(document: Any) -> DiscoveryPlan:
    """Return an immutable structural/budget contract, without file admission."""
    obj = _object(document, "schema_version protocol_version design_id plan_id stand_id "
                  "source_revision clean_source release stand qualification resource_plan "
                  "monitoring_plan namespace_registry dependencies warmup_namespace "
                  "measurement_namespace minimum_observations captures budget diagnostic_only "
                  "execution_authority phase18_authority retries", "plan")
    for key, expected in (("schema_version", PLAN_VERSION), ("protocol_version", "2.0.0-pre.3"),
                          ("design_id", DESIGN_ID), ("clean_source", True),
                          ("diagnostic_only", True), ("execution_authority", False),
                          ("phase18_authority", False), ("retries", 0)):
        _constant(obj[key], expected, "plan." + key)
    plan_id, stand_id = (_text(obj[key], "plan." + key) for key in ("plan_id", "stand_id"))
    revision = _text(obj["source_revision"], "plan.source_revision", r"[0-9a-f]{40}")
    bindings = {key: _binding(obj[key], "plan." + key) for key in (
        "release", "stand", "qualification", "resource_plan", "monitoring_plan", "namespace_registry")}
    dependencies = obj["dependencies"]
    if not isinstance(dependencies, list) or len(dependencies) != 6:
        _fail("plan.dependencies", "requires exact ordered EXT001-006 bindings")
    parsed_dependencies = []
    for index, item in enumerate(dependencies, 1):
        path = f"plan.dependencies[{index - 1}]"
        dep = _object(item, "input_id resolution", path)
        expected = f"S17-EXT-{index:03d}"
        _constant(dep["input_id"], expected, path + ".input_id")
        parsed_dependencies.append(Dependency(expected, _binding(dep["resolution"], path + ".resolution")))
    namespaces = tuple(_text(obj[key], "plan." + key)
                       for key in ("warmup_namespace", "measurement_namespace"))
    if namespaces[0] == namespaces[1]:
        _fail("plan", "warmup and measurement seed namespaces must be disjoint")
    minima = _object(obj["minimum_observations"], " ".join(SEQUENCES), "plan.minimum_observations")
    for key in SEQUENCES:
        _constant(minima[key], MINIMUM_OBSERVATIONS_PER_SEQUENCE, "plan.minimum_observations." + key)
    captures = obj["captures"]
    required = required_captures()
    if not isinstance(captures, list) or len(captures) != len(required):
        _fail("plan.captures", "requires exactly the 36 prospective captures; no extras or retries")
    parsed = []
    run_ids: set[str] = set()
    seed_ids: set[str] = set()
    seed_values: set[str] = set()
    geometries: dict[tuple[str, str], Geometry] = {}
    for ordinal, (item, key) in enumerate(zip(captures, required, strict=True)):
        path = f"plan.captures[{ordinal}]"
        cap = _object(item, "ordinal context_ordinal hardware_state placement working_set_class "
                      "warmup_ns measurement_ns warmup measurement arena_seed seed_use geometry budget", path)
        state, placement, working_set = CONTEXTS[key.context_ordinal]
        for name, expected in (("ordinal", ordinal), ("context_ordinal", key.context_ordinal),
                               ("hardware_state", state), ("placement", placement),
                               ("working_set_class", working_set), ("warmup_ns", WARMUP_NS),
                               ("measurement_ns", key.duration_ns)):
            _constant(cap[name], expected, path + "." + name)
        identities = tuple(_identity(cap[name], namespace, path + "." + name)
                           for name, namespace in zip(("warmup", "measurement"), namespaces, strict=True))
        _constant(cap["seed_use"], "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS", path + ".seed_use")
        arena_seed = _identity(cap["arena_seed"], namespaces[1], path + ".arena_seed")
        if arena_seed != identities[1]:
            _fail(path + ".arena_seed", "must explicitly equal measurement identity; one persistent arena")
        for identity in identities:
            for field, seen in (("run_id", run_ids), ("seed_id", seed_ids), ("seed_hex", seed_values)):
                value = getattr(identity, field)
                if value in seen:
                    _fail(path + "." + field, "reused warmup/measurement identity or seed")
                seen.add(value)
        geometry = _geometry(cap["geometry"], placement, path + ".geometry")
        group = (placement, working_set)
        if group in geometries and geometries[group] != geometry:
            _fail(path + ".geometry", "geometry changes within a paired placement/class")
        geometries[group] = geometry
        capture_budget = _capture_budget(cap["budget"], key.duration_ns, path + ".budget")
        # A lower bound only: the resource-plan binding must additionally cover
        # the actual queue, stacks, permutation, objects and all control storage.
        known_memory = _sum([geometry.capacity * geometry.cache_line_bytes,
                             capture_budget.retained_output_bytes], path + ".known_memory_bytes")
        if capture_budget.memory_bytes < known_memory:
            _fail(path + ".budget.memory_bytes", "does not cover arena plus retained output buffers")
        parsed.append(Capture(ordinal, key.context_ordinal, state, placement, working_set,
                              key.duration_ns, *identities, arena_seed, geometry, capture_budget))
    budget_names = tuple(StudyBudget.__dataclass_fields__)
    raw_budget = _object(obj["budget"], " ".join(budget_names), "plan.budget")
    values = {name: _uint(raw_budget[name], "plan.budget." + name, 1)
              for name in budget_names if name != "custody_domains"}
    domains = raw_budget["custody_domains"]
    if not isinstance(domains, list) or not domains:
        _fail("plan.budget.custody_domains", "requires explicit custody budgets")
    parsed_domains = []
    for index, item in enumerate(domains):
        path = f"plan.budget.custody_domains[{index}]"
        domain = _object(item, "domain_id copies budget_bytes", path)
        parsed_domains.append(CustodyDomain(_text(domain["domain_id"], path + ".domain_id"),
                                           _uint(domain["copies"], path + ".copies", 1),
                                           _uint(domain["budget_bytes"], path + ".budget_bytes", 1)))
    if len({domain.domain_id for domain in parsed_domains}) != len(parsed_domains):
        _fail("plan.budget.custody_domains", "duplicate custody domain")
    budget = StudyBudget(**values, custody_domains=tuple(parsed_domains))
    unavoidable = _sum([WARMUP_NS + key.duration_ns for key in required], "plan.unavoidable_ns")
    watchdog = _sum([budget.setup_ns, budget.cleanup_ns] +
                    [capture.budget.watchdog_ns for capture in parsed], "plan.required_watchdog_ns")
    peak_memory = _sum([budget.controller_memory_bytes,
                       max(capture.budget.memory_bytes for capture in parsed)], "plan.peak_memory_bytes")
    output = _sum([budget.metadata_output_bytes] + [capture.budget.max_output_bytes for capture in parsed],
                  "plan.maximum_output_bytes")
    if budget.watchdog_ns < watchdog:
        _fail("plan.budget.watchdog_ns", "does not cover setup, all capture watchdogs and cleanup")
    if budget.memory_budget_bytes < peak_memory:
        _fail("plan.budget.memory_budget_bytes", "does not cover sequential peak plus controller")
    if budget.output_budget_bytes < output:
        _fail("plan.budget.output_budget_bytes", "does not cover all capture outputs and metadata")
    for domain in parsed_domains:
        required_bytes = _product(output, domain.copies, "plan.custody_copy_bytes")
        if domain.budget_bytes < required_bytes:
            _fail("plan.budget.custody_domains", f"{domain.domain_id} cannot hold its declared copies")
    payload = canonicalize(obj).encode("utf-8")
    return DiscoveryPlan(plan_id, stand_id, revision, **bindings,
                         dependencies=tuple(parsed_dependencies), warmup_namespace=namespaces[0],
                         measurement_namespace=namespaces[1], captures=tuple(parsed), budget=budget,
                         unavoidable_duration_ns=unavoidable, required_watchdog_ns=watchdog,
                         peak_memory_bytes=peak_memory, maximum_output_bytes=output,
                         canonical_bytes=payload, sha256=hashlib.sha256(payload).hexdigest())


@dataclass(frozen=True)
class DiscoveryRequest:
    request_id: str
    plan: DiscoveryPlan
    canonical_bytes: bytes
    sha256: str
    execution_authority: bool = False


def validate_request(document: Any, plan_document: Any) -> DiscoveryRequest:
    """Bind exactly one validated prospective plan; not a signed phase request."""
    obj = _object(document, "schema_version request_id plan_binding diagnostic_only "
                  "execution_authority phase18_authority", "request")
    for key, expected in (("schema_version", REQUEST_VERSION), ("diagnostic_only", True),
                          ("execution_authority", False), ("phase18_authority", False)):
        _constant(obj[key], expected, "request." + key)
    request_id = _text(obj["request_id"], "request.request_id")
    binding = _binding(obj["plan_binding"], "request.plan_binding")
    plan = validate_plan(plan_document)
    if binding != Binding(plan.plan_id, len(plan.canonical_bytes), plan.sha256):
        _fail("request.plan_binding", "does not match exact canonical plan identity/size/hash")
    payload = canonicalize(obj).encode("utf-8")
    return DiscoveryRequest(request_id, plan, payload, hashlib.sha256(payload).hexdigest())
