"""Bounded D-178 admission using the existing journal, trust and fd executor.

Formal actions retain the v21 implementation. This successor requires a future
source-bound release/policy admission; importing it is not execution authority.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import types
import stage17_phase_controller_v18 as formal_prepare

import stage17_phase_controller_v21 as predecessor
import stage17_phase_controller_v4 as old
import stage17_state_journal_v49 as journal_runtime
import stage17_output_registry_v9 as registry
import stage17_discovery_contract_v1 as contract

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
support = old.controller_support
ACTION = registry.ACTION
_validate_action_inputs = predecessor._validate_action_inputs


def deadline_policy(plan: contract.DiscoveryPlan) -> dict:
    if plan.budget.cleanup_ns < 2_000_000_000:
        raise ControllerError("diagnostic cleanup must cover the existing two-second supervisor reserve")
    # Ceiling is explicit and checked; no fixed 180-second session assumption.
    def seconds(ns):
        return (ns + 999_999_999) // 1_000_000_000
    return {"mode": "BOUNDED_DIAGNOSTIC_SESSION",
            "per_run_max_wall_seconds": seconds(max(c.budget.watchdog_ns for c in plan.captures)),
            "session_max_wall_seconds": seconds(plan.budget.watchdog_ns),
            "implicit_extension": False, "partial_session_completes": False}


def runtime_from_context(validation):
    source = validation.resolutions["S17-EXT-006"]
    context = source.semantic_context
    expected = ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT", ACTION]
    if (context["supported_actions"] != expected
            or context["release_artifact_role"] != "STAGE17_FIXED_ACTION_WORKER"
            or context["runtime_profile"] != "STAGE17-FIXED-ACTION-WORKER-v4"):
        raise ControllerError("release does not declare the exact diagnostic action surface")
    runtime = {"role": context["release_artifact_role"], "profile": context["runtime_profile"],
               "size_bytes": context["release_artifact_size_bytes"], "sha256": context["release_artifact_sha256"]}
    release = {"source_resolution_id": source.resolution_id, "source_resolution_sha256": source.sha256,
               "artifact_role": runtime["role"], "runtime_profile": runtime["profile"],
               "worker_size_bytes": runtime["size_bytes"], "worker_sha256": runtime["sha256"]}
    return runtime, release, pathlib.Path(context["release_artifact_path"])


def _native_inputs(plan, resources, monitoring, native):
    """Explicit NativeDiscoveryCapturePlan JSON mapping, no platform defaults.

resources contains three OwnerMappingPlans and expected native layout sizes;
monitoring contains the seven-region query schedule and 2x2 owner/phase limits.
The native parser must recompute native_discovery_layout and compare every size.
Time offsets are picoseconds; all plan nanosecond durations multiply by 1000.
"""
    for document, version in ((resources, "cpu-prefetch-discovery-resources/1"),
                              (monitoring, "cpu-prefetch-discovery-monitoring/1")):
        contract._object(document, "schema_version captures", "bound native document")
        contract._constant(document["schema_version"], version, "native document version")
        if not isinstance(document["captures"], list) or len(document["captures"]) != 36:
            raise ControllerError("native document must enumerate all 36 captures")
    if not isinstance(native, list) or len(native) != 36:
        raise ControllerError("native input list must enumerate all 36 captures")
    for cap, r, m, n in zip(plan.captures, resources["captures"], monitoring["captures"], native, strict=True):
        if n != {"ordinal": cap.ordinal, "resources": r, "monitoring": m}:
            raise ControllerError("native inputs differ from bound resource/monitoring documents")
        contract._object(r, "ordinal workers controller_stack core_bytes monitor_bytes "
                         "total_mapping_bytes region_bytes tls_module_capacity thread_stat_bytes "
                         "thread_status_bytes thread_affinity_words initial_consumer_state", "native resources")
        contract._object(m, "ordinal during_first_page during_page_count during_offset_ticks "
                         "observer_wait_poll_limit control_region_index counter_limits hardware_identity environment_sources", "native monitoring")
        contract._constant(r["ordinal"], cap.ordinal, "resource ordinal")
        contract._constant(m["ordinal"], cap.ordinal, "monitor ordinal")
        for key in ("core_bytes", "monitor_bytes", "total_mapping_bytes", "tls_module_capacity",
                    "thread_stat_bytes", "thread_status_bytes", "thread_affinity_words"):
            contract._uint(r[key], "resources." + key, 1)
        contract._uint(r["initial_consumer_state"], "initial_consumer_state")
        contract._object(r["workers"], "producer_stack consumer_stack", "workers")
        for role in ("producer", "consumer", "controller"):
            stack = contract._object((r if role == "controller" else r["workers"])[role + "_stack"],
                "bytes verified_base_page_bytes owner_cpu requested_node", role + "_stack")
            for key, value in stack.items():
                contract._uint(value, role + "." + key, 1 if key in ("bytes", "verified_base_page_bytes") else 0)
            if (stack["verified_base_page_bytes"] != cap.geometry.base_page_bytes
                    or stack["bytes"] % cap.geometry.base_page_bytes):
                raise ControllerError("native stack page geometry differs")
            if role != "controller" and (stack["owner_cpu"], stack["requested_node"]) != (
                    getattr(cap.geometry, role + "_cpu"), getattr(cap.geometry, role + "_node")):
                raise ControllerError("native owner CPU/node differs from plan")
        if r["controller_stack"]["owner_cpu"] in (cap.geometry.producer_cpu, cap.geometry.consumer_cpu):
            raise ControllerError("controller shares a worker CPU")
        for key, source, count, minimum in (("region_bytes", r, 7, 1),
                ("during_first_page", m, 7, 0), ("during_page_count", m, 7, 1),
                ("during_offset_ticks", m, 2, 1)):
            values = source[key]
            if not isinstance(values, list) or len(values) != count:
                raise ControllerError("native array length differs: " + key)
            for value in values:
                contract._uint(value, key, minimum)
        expected_total = contract._sum(r["region_bytes"] + [r["monitor_bytes"], 3 * cap.geometry.base_page_bytes], "native total mapping")
        if r["total_mapping_bytes"] != expected_total or expected_total > cap.budget.memory_bytes:
            raise ControllerError("native mapping sizes exceed/differ from resource budget")
        for first, count, size in zip(m["during_first_page"], m["during_page_count"], r["region_bytes"], strict=True):
            if contract._product(contract._sum([first, count], "page range"), cap.geometry.base_page_bytes, "page extent") > size:
                raise ControllerError("native monitoring range exceeds region")
        for offset, ns in zip(m["during_offset_ticks"], (contract.WARMUP_NS, cap.measurement_ns), strict=True):
            if offset >= contract._product(ns, 1000, "native horizon ticks"):
                raise ControllerError("native during offset lies outside phase")
        contract._product(cap.budget.drain_ns, 1000, "native drain ticks")
        contract._uint(m["observer_wait_poll_limit"], "observer_wait_poll_limit", 1)
        if type(m["control_region_index"]) is not int or not 0 <= m["control_region_index"] < 7:
            raise ControllerError("invalid native control region")
        identity = contract._object(m["hardware_identity"], "family model", "hardware_identity")
        for value in identity.values():
            contract._uint(value, "hardware identity")
        sources = m["environment_sources"]
        if not isinstance(sources, list):
            raise ControllerError("environment_sources must be an explicit array")
        source_paths = set()
        reserved_bytes = []
        for source in sources:
            contract._object(source, "path byte_capacity chunk_bytes max_data_reads requested", "environment source")
            path = source["path"]
            if not isinstance(path, str) or not path.startswith("/") or "\0" in path or path in source_paths:
                raise ControllerError("environment source path must be unique absolute UTF-8 without NUL")
            try:
                path_bytes = len(path.encode("utf-8", errors="strict"))
            except UnicodeError as exception:
                raise ControllerError("environment source path is not UTF-8") from exception
            source_paths.add(path)
            for key in ("byte_capacity", "chunk_bytes", "max_data_reads"):
                contract._uint(source[key], "environment." + key, 1)
            if source["chunk_bytes"] > source["byte_capacity"]:
                raise ControllerError("environment read chunk exceeds byte capacity")
            requested = source["requested"]
            if (not isinstance(requested, list) or len(requested) != 6
                    or any(type(value) is not bool for value in requested) or not any(requested)):
                raise ControllerError("environment source requires six explicit booleans and an observation")
            # Native layout reserves every slot, even when not requested. Exact
            # C++ object/read-array sizes are recomputed by native_discovery_layout.
            buffers = contract._product(source["byte_capacity"], 6, "environment six buffers")
            contract._product(source["max_data_reads"], 6, "environment six read arrays")
            reserved_bytes.extend((buffers, contract._sum([path_bytes, 1], "environment frozen path")))
        if contract._sum(reserved_bytes, "environment storage lower bound") > r["monitor_bytes"]:
            raise ControllerError("environment storage exceeds monitor memory budget")
        limits = m["counter_limits"]
        if not isinstance(limits, list) or len(limits) != 2:
            raise ControllerError("native counter limits require two phases")
        for phase in limits:
            if not isinstance(phase, list) or len(phase) != 2:
                raise ControllerError("native counter limits require two owners")
            for owner in phase:
                contract._object(owner, "minor_faults major_faults voluntary_switches involuntary_switches", "counter limits")
                for value in owner.values():
                    if value is not None:
                        contract._uint(value, "counter limit")


def validate_action_inputs(request, validation):
    values = contract._object(request["action_inputs"],
        "plan hardware_control bound_documents native_captures", "diagnostic inputs")
    plan = contract.validate_plan(values["plan"])
    runtime, _, _ = runtime_from_context(validation)
    ext = validation.resolutions
    if (plan.stand_id != request["stand_id"]
            or plan.source_revision != ext["S17-EXT-006"].semantic_context["source_revision"]
            or (plan.release.size_bytes, plan.release.sha256) != (runtime["size_bytes"], runtime["sha256"])):
        raise ControllerError("diagnostic plan release/source/stand differs from admitted facts")
    trust = ext["S17-EXT-003"].semantic_context["trust"]["measurements"]
    if (plan.stand.sha256 != trust["stand_anchor_sha256"]
            or plan.qualification.sha256 != ext["S17-EXT-004"].semantic_context["manifest_sha256"]):
        raise ControllerError("stand/qualification binding is not the admitted predecessor")
    for dep in plan.dependencies:
        actual = ext[dep.input_id]
        if (dep.resolution.artifact_id, dep.resolution.sha256) != (actual.resolution_id, actual.sha256):
            raise ControllerError("diagnostic predecessor binding differs")
    predecessor._validate_hardware_control(values, validation)
    mapping = values["hardware_control"]["mapping_id"]
    expected_identity = {"family": 6, "model": {
        "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1": 85,
        "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1": 62}[mapping]}
    bindings = [plan.stand, plan.qualification, plan.resource_plan, plan.monitoring_plan,
                plan.namespace_registry] + [dep.resolution for dep in plan.dependencies]
    documents = values["bound_documents"]
    if not isinstance(documents, list) or len(documents) != len(bindings):
        raise ControllerError("bound documents must supply every nonbinary plan input")
    by_id = {}
    byte_payloads = {}
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ControllerError("duplicate key in bound document bytes")
            result[key] = value
        return result
    for item in documents:
        contract._object(item, "artifact_id document utf8_bytes", "bound document")
        if item["artifact_id"] in by_id or not isinstance(item["document"], dict):
            raise ControllerError("duplicate or malformed bound document")
        if not isinstance(item["utf8_bytes"], str):
            raise ControllerError("bound document utf8_bytes must be an exact UTF-8 string")
        try:
            payload = item["utf8_bytes"].encode("utf-8", errors="strict")
            parsed = json.loads(payload, object_pairs_hook=unique_pairs,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except (UnicodeError, ValueError) as exception:
            raise ControllerError("bound document is not strict UTF-8 JSON") from exception
        if registry.canonical(parsed) != registry.canonical(item["document"]):
            raise ControllerError("bound document parsed bytes differ from supplied document")
        by_id[item["artifact_id"]] = parsed
        byte_payloads[item["artifact_id"]] = payload
    if set(by_id) != {binding.artifact_id for binding in bindings}:
        raise ControllerError("bound document identities differ")
    for binding in bindings:
        payload = byte_payloads[binding.artifact_id]
        if (len(payload), registry.sha256(payload)) != (binding.size_bytes, binding.sha256):
            raise ControllerError("bound document bytes differ: " + binding.artifact_id)
    _native_inputs(plan, by_id[plan.resource_plan.artifact_id], by_id[plan.monitoring_plan.artifact_id], values["native_captures"])
    if any(item["monitoring"]["hardware_identity"] != expected_identity
           for item in values["native_captures"]):
        raise ControllerError("native family/model differs from admitted mapping")
    return plan


def _runtime_from_context(
    action: str, validation: object,
) -> tuple[dict[str, object], dict[str, object]]:
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
            or tuple(measurements["supported_actions"]) not in ((
                "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                "STAGE17-BLINDED-PILOT",
            ), ("Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                "STAGE17-BLINDED-PILOT", ACTION))
            or action not in measurements["supported_actions"]):
        raise ControllerError("admitted fixed-action runtime surface drifted")
    runtime = {
        "path": path, "role": measurements["worker_role"],
        "profile": measurements["runtime_profile"],
        "size_bytes": measurements["worker_size_bytes"],
        "sha256": measurements["worker_sha256"],
    }
    return runtime, release


def _prepare_formal(**arguments):
    # Preserve the full existing formal admission body, changing only capability
    # admission and its prospective journal runtime. No predecessor globals change.
    namespace = dict(formal_prepare.prepare_action.__globals__)
    namespace.update(_runtime_from_context=_runtime_from_context, journal_runtime=journal_runtime)
    function = types.FunctionType(formal_prepare.prepare_action.__code__, namespace,
                                  argdefs=formal_prepare.prepare_action.__defaults__)
    function.__kwdefaults__ = formal_prepare.prepare_action.__kwdefaults__
    return function(**arguments)


def prepare_action(**arguments):
    authorization, authorization_bytes = support._load(arguments["authorization_path"])
    if authorization.get("action_id") != ACTION:
        return _prepare_formal(**arguments)
    root = arguments["repository_root"].resolve()
    pinned = registry.pin_registry(root)
    registry.validate_document(pinned, authorization, registry.schema_path("phase-action-authorization"), "diagnostic authorization")
    now = support._now()
    validation = journal_runtime.validate_operational_journal(repository_root=root,
        evidence_root=arguments["operational_evidence_root"], latest_journal=arguments["journal"],
        journal_directory=arguments["journal_directory"], pilot_archive=arguments.get("pilot_archive"),
        pilot_sidecar=arguments.get("pilot_sidecar"), as_of_utc=now,
        allow_synthetic_test_evidence=arguments.get("synthetic_test_only", False))
    definition = pinned.action(ACTION)
    if validation.current_state != definition["required_state"]:
        raise ControllerError("diagnostic state gate is not satisfied")
    expected = [old._binding(validation.resolutions[key]) for key in definition["required_resolution_ids"]]
    trust = validation.resolutions["S17-EXT-003"].semantic_context["trust"]
    if (authorization["predecessor_resolutions"] != expected
            or authorization["fixed_action_definition_sha256"] != pinned.plan_sha256
            or authorization["permission_matrix"] != definition["permission_matrix"]
            or authorization["actor"] != trust["measurements"]["principal"]
            or authorization["reviewer"] != trust["measurements"]["reviewer_role"]
            or authorization["target"]["stand_id"] != trust["subject_id"]
            or authorization["trust_context"] != {
                "ext002_resolution": expected[1], "ext003_resolution": expected[2]}):
        raise ControllerError("diagnostic authority/trust/predecessor binding differs")
    support._verify_signature(authorization_bytes, arguments["signature_path"], trust)
    _, request_bytes = support._read_binding(authorization["request_binding"], "diagnostic request")
    request = json.loads(request_bytes)
    registry.validate_document(pinned, request, registry.schema_path("fixed-action-request"), "diagnostic request")
    if request_bytes != registry.canonical(request):
        raise ControllerError("diagnostic request is not canonical")
    runtime, release, worker_path = runtime_from_context(validation)
    if (request["runtime_binding"] != runtime or request["release_binding"] != release
            or request["predecessor_resolutions"] != expected
            or request["evidence_root_binding"] != authorization["evidence_root_binding"]
            or request["stand_id"] != authorization["target"]["stand_id"]
            or any(request[key] != authorization[key] for key in ("action_id", "session_id", "authorization_id"))
            or request["synthetic_test_only"] is not arguments.get("synthetic_test_only", False)):
        raise ControllerError("diagnostic request lineage differs")
    plan = validate_action_inputs(request, validation)
    policy = deadline_policy(plan)
    issued, expires, actual = (support._parse_utc(value) for value in (
        authorization["issued_at_utc"], authorization["expires_at_utc"], now))
    if (authorization["deadline_policy"] != policy or not issued <= actual < expires
            or expires - issued > dt.timedelta(seconds=policy["session_max_wall_seconds"])):
        raise ControllerError("diagnostic deadline/authority window differs")
    support._read_binding({"path": str(worker_path), "size_bytes": runtime["size_bytes"],
                           "sha256": runtime["sha256"]}, "diagnostic release worker")
    return PreparedAction(root, authorization, authorization_bytes, request, request_bytes,
                          runtime, worker_path, release, validation, pinned)


def execute_once(**arguments):
    prepared = prepare_action(**arguments)
    if prepared.request["action_id"] != ACTION:
        namespace = dict(predecessor.execute_once.__globals__)
        namespace["prepare_action"] = lambda **unused: prepared
        function = types.FunctionType(predecessor.execute_once.__code__, namespace,
                                      argdefs=predecessor.execute_once.__defaults__)
        function.__kwdefaults__ = predecessor.execute_once.__kwdefaults__
        return function(**arguments)
    import stage17_fixed_action_executor_v8 as executor
    return executor.execute_fixed_action(repository_root=prepared.root,
        authorization=prepared.authorization, authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=pathlib.Path(prepared.request["evidence_root_binding"]["absolute_path"]),
        synthetic_test_only=arguments.get("synthetic_test_only", False))


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repository-root", "journal", "journal-directory", "operational-evidence-root", "authorization", "signature"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    args = parser.parse_args()
    execute_once(repository_root=args.repository_root, journal=args.journal,
        journal_directory=args.journal_directory, operational_evidence_root=args.operational_evidence_root,
        authorization_path=args.authorization, signature_path=args.signature,
        pilot_archive=args.pilot_archive, pilot_sidecar=args.pilot_sidecar)
    print("stage17-phase-controller: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
