"""Explicit admission for signed persistent formal families; no execution by import.

This successor requires the complete v26 release profile and exact prospective
plans. Historical actions delegate unchanged. Native success and custody alone
cannot satisfy a prior independent calibration-result requirement.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import types

import stage17_phase_controller_v24 as predecessor
import stage17_phase_controller_v21 as hardware_controller
import stage17_output_registry_v11 as registry
import stage17_formal_plan_v1 as contract
import stage17_q16a_discovery_v2 as discovery_selector
import stage17_formal_calibration_v1 as calibration
import stage17_q16c_schedule_provenance_v1 as schedule_provenance
import stage17_state_journal_v52 as journal_runtime

ControllerError = predecessor.ControllerError
PreparedAction = predecessor.PreparedAction
support = predecessor.support
old = predecessor.old
_runtime_from_context = predecessor._runtime_from_context
_validate_action_inputs = predecessor._validate_action_inputs


def activate():
    journal_runtime.activate()


def _with_globals(function, replacements, arguments):
    namespace = dict(function.__globals__)
    namespace.update(replacements)
    rebound = types.FunctionType(function.__code__, namespace, argdefs=function.__defaults__)
    rebound.__kwdefaults__ = function.__kwdefaults__
    return rebound(**arguments)


def _prepare_legacy(**arguments):
    def old_formal(**values):
        return _with_globals(predecessor.formal_prepare.prepare_action,
            {"journal_runtime": journal_runtime, "_runtime_from_context": _runtime_from_context}, values)
    def legacy_runtime(validation):
        profile = validation.resolutions["S17-EXT-006"].semantic_context.get("bundle_profile")
        if profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}:
            return runtime_from_context(validation)
        return predecessor.runtime_from_context(validation)
    def legacy_inputs(request, validation):
        return _with_globals(predecessor.validate_action_inputs,
            {"runtime_from_context": legacy_runtime}, {"request": request, "validation": validation})
    return _with_globals(predecessor.prepare_action,
        {"activate": activate, "journal_runtime": journal_runtime,
         "_prepare_formal": old_formal, "runtime_from_context": legacy_runtime,
         "validate_action_inputs": legacy_inputs}, arguments)


def deadline_policy(extent):
    if extent.declared.cleanup_ns < 2_000_000_000:
        raise ControllerError("formal cleanup must include the existing two-second supervisor reserve")
    def seconds(ns):
        return ns // 1_000_000_000 + bool(ns % 1_000_000_000)
    return dict(mode="BOUNDED_FORMAL_CALIBRATION_SESSION",
        per_run_max_wall_seconds=seconds(max(c.declared.watchdog_ns for c in extent.captures)),
        session_max_wall_seconds=seconds(extent.declared.watchdog_ns),
        implicit_extension=False, partial_session_completes=False)


def runtime_from_context(validation):
    source = validation.resolutions["S17-EXT-006"]
    context = source.semantic_context
    if (context.get("bundle_profile") not in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                                               "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            or context.get("supported_actions") != ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                                                    "STAGE17-BLINDED-PILOT", "Q16A-DURATION-DISCOVERY"]
            or context.get("release_artifact_role") != "STAGE17_FIXED_ACTION_WORKER"
            or context.get("runtime_profile") != "STAGE17-FIXED-ACTION-WORKER-v4"):
        raise ControllerError("formal execution requires the complete successor qualified release")
    runtime = dict(role=context["release_artifact_role"], profile=context["runtime_profile"],
                   size_bytes=context["release_artifact_size_bytes"], sha256=context["release_artifact_sha256"])
    release = dict(source_resolution_id=source.resolution_id, source_resolution_sha256=source.sha256,
                   artifact_role=runtime["role"], runtime_profile=runtime["profile"],
                   worker_size_bytes=runtime["size_bytes"], worker_sha256=runtime["sha256"])
    return runtime, release, pathlib.Path(context["release_artifact_path"])


def _bound_bytes(binding, label, maximum_bytes=128 * 1024**2):
    if (not isinstance(binding, dict) or set(binding) != {"path", "size_bytes", "sha256"}
            or type(binding["size_bytes"]) is not int or not 0 < binding["size_bytes"] <= maximum_bytes):
        raise ControllerError(label + " requires a bounded exact file binding")
    try:
        _, payload = support._read_binding(binding, label)
    except (support.ControllerError, OSError) as error:
        raise ControllerError(label + " file binding failed: " + str(error)) from error
    return payload


def _bound_document(binding, label):
    payload = _bound_bytes(binding, label)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ControllerError(label + " has a duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(payload, object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as error:
        raise ControllerError(label + " is not strict JSON") from error


def validate_prior_calibration(result, prior, plan, selected_duration_ns):
    """Recompute prior coverage/math; signed bindings authenticate its provenance."""
    try:
        calibration.validate_calibration_record(result)
    except calibration.CalibrationError as error:
        raise ControllerError("prior formal calibration semantics failed: " + str(error)) from error
    if (result["status"] != "VALIDATED" or result["action_id"] != prior
            or result["method_id"] != contract.METHOD[prior]
            or result["source_revision"] != plan["source_revision"]
            or result["stand_id"] != plan["stand_id"]):
        raise ControllerError("prior formal calibration is unresolved or from a different release")
    if prior == "Q16a" and (
            result["prospective"]["measurement_ns"] != selected_duration_ns
            or result["prospective"]["minimum_observations_per_series"] !=
                discovery_selector.MINIMUM_OBSERVATIONS_PER_SEQUENCE):
        raise ControllerError("prior Q16a differs from accepted discovery duration/minimum")


def validate_ring_reuse(plan, ring_result, binding):
    """Every later ring context uses the measured geometry and exact R2 result."""
    evidence_id = "q16a-sha256-" + binding["sha256"]
    for item in plan["captures"]:
        capture = item["capture"]
        if capture["package"] not in {"R0", "R1", "R2"}:
            continue
        context = (0 if capture["placement"] == "NEAR" else 3) + contract.WORKING_SETS.index(
            capture["working_set_class"])
        prior_geometry = ring_result["ring_geometry"][context]
        geometry = capture["geometry"]
        if any(geometry[key] != prior_geometry[key] for key in ("capacity", "cache_line_bytes")):
            raise ControllerError("formal ring geometry differs from prior Q16a")
        if capture["package"] == "R2":
            distance = ring_result["derived_result"]["contexts"][context]["distance"]
            if capture["ring_distance"] != dict(cache_lines=distance["d2_cache_lines"],
                                                calibration_evidence_id=evidence_id):
                raise ControllerError("R2 distance/evidence differs from exact bound Q16a result")


def validate_schedule_sources(plan, sources, registrations, service_result):
    """Check accepted original source bytes against the signed namespace record."""
    if not isinstance(sources, list) or not isinstance(registrations, list):
        raise ControllerError("schedule sources/namespace registrations must be lists")
    by_id = {}
    for source in sources:
        if (not isinstance(source, dict) or set(source) != {"artifact_id", "binding", "envelope_binding",
                "derivation_binding", "parent_namespace_id"} or source["artifact_id"] in by_id):
            raise ControllerError("duplicate or malformed schedule source binding")
        by_id[source["artifact_id"]] = source
    by_schedule = {}
    for registration in registrations:
        if (not isinstance(registration, dict) or set(registration) != {
                "schedule_id", "namespace_id", "seed_id", "phase", "parent_namespace_id"}
                or registration["schedule_id"] in by_schedule):
            raise ControllerError("duplicate or malformed schedule namespace registration")
        by_schedule[registration["schedule_id"]] = registration
    used = set()
    used_schedules = set()
    for item in plan["captures"]:
        capture = item["capture"]
        for phase, schedule in zip(("warmup", "measurement"), capture["schedules"], strict=True):
            source = by_id.get(schedule["source_artifact"]["artifact_id"])
            registration = by_schedule.get(schedule["schedule_id"])
            if source is None or registration is None:
                raise ControllerError("schedule source or namespace registration is absent")
            expected = {key: schedule[key] for key in ("schedule_id", "namespace_id", "seed_id")}
            expected.update(phase=phase, parent_namespace_id=source["parent_namespace_id"])
            if registration != expected:
                raise ControllerError("schedule source differs from the registered namespace")
            binary = source["binding"]
            if not isinstance(binary, dict) or set(binary) != {"path", "size_bytes", "sha256"}:
                raise ControllerError("schedule binary needs an exact file binding")
            def receipt(binding, suffix):
                return dict(artifact_id=source["artifact_id"] + suffix,
                            size_bytes=binding["size_bytes"], sha256=binding["sha256"])
            envelope = _bound_bytes(source["envelope_binding"], "schedule envelope",
                                    schedule_provenance.MAX_METADATA_BYTES)
            derivation = _bound_bytes(source["derivation_binding"], "schedule derivation",
                                      schedule_provenance.MAX_METADATA_BYTES)
            try:
                schedule_provenance.verify_schedule_source(schedule=schedule, phase=phase,
                    duration_ns=capture[phase + "_ns"], scale_ordinal=plan["scale_ordinal"],
                    load_level=capture["load_level"], calibration_record=service_result,
                    artifact_path=pathlib.Path(binary["path"]), artifact_binding=receipt(binary, ""),
                    envelope_utf8_bytes=envelope, envelope_binding=receipt(source["envelope_binding"], ":envelope"),
                    derivation_utf8_bytes=derivation, derivation_binding=receipt(source["derivation_binding"], ":derivation"),
                    expected_parent_namespace_id=registration["parent_namespace_id"])
            except schedule_provenance.ScheduleProvenanceError as error:
                raise ControllerError("accepted schedule provenance failed: " + str(error)) from error
            used.add(source["artifact_id"])
            used_schedules.add(schedule["schedule_id"])
    if used != set(by_id) or used_schedules != set(by_schedule):
        raise ControllerError("unreferenced schedule source or namespace registration")


def validate_action_inputs(request, validation):
    action = request["action_id"]
    inputs = request["action_inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"plan", "hardware_control", "prerequisite_bindings"}:
        raise ControllerError("formal action input field set differs")
    plan = inputs["plan"]
    extent = contract.validate_plan(action, plan)
    runtime_from_context(validation)
    if (plan["stand_id"] != request["stand_id"] or plan["source_revision"] !=
            validation.resolutions["S17-EXT-006"].semantic_context["source_revision"]):
        raise ControllerError("formal plan stand/source differs from qualification")
    hardware_controller._validate_hardware_control(inputs, validation)
    mapping = inputs["hardware_control"]["mapping_id"]
    identity = {"family": 6, "model": {"INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1": 85,
                                     "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1": 62}[mapping]}
    qualified_cpus = [row["cpu"] for row in inputs["hardware_control"]["prestate"]]
    for item in plan["captures"]:
        geometry = item["capture"]["geometry"]
        consumer = qualified_cpus[1 if item["capture"]["placement"] == "NEAR" else 2]
        if (item["monitoring"]["hardware_identity"] != identity
                or (geometry["producer_cpu"], geometry["consumer_cpu"]) != (qualified_cpus[0], consumer)):
            raise ControllerError("formal native pair/model differs from qualified hardware")
    prerequisites = inputs["prerequisite_bindings"]
    if not isinstance(prerequisites, dict) or set(prerequisites) != {
            "discovery_validation", "q16a_validation", "q16b_validation",
            "namespace_registry", "schedule_sources"}:
        raise ControllerError("formal prerequisite bindings are incomplete or expanded")
    discovery = _bound_document(prerequisites["discovery_validation"], "validated discovery")
    if (discovery.get("status") != "FULL_STUDY_VALIDATED"
            or discovery.get("scope") != "D207_D213_INDEPENDENT_VALIDATOR_V3"
            or discovery.get("execution_authority") is not False
            or discovery.get("formal_runs_contributed") != 0):
        raise ControllerError("discovery prerequisite is not an independent completed study")
    study = discovery["validated_study"]
    validator_bytes = pathlib.Path(__file__).with_name("stage17_discovery_validation_v3.py").read_bytes()
    if (discovery.get("successor_validator_sha256") != hashlib.sha256(validator_bytes).hexdigest()
            or study.get("plan_sha256") != discovery.get("plan_sha256")
            or study.get("diagnostic_only") is not True
            or study.get("execution_authority") is not False
            or study.get("formal_runs_contributed") != 0):
        raise ControllerError("discovery validator/plan/scope binding differs")
    # Recompute the count-only selection from every authenticated study summary.
    observed = []
    for row in study["captures"]:
        observed.append(discovery_selector.DiagnosticCapture(
            discovery_selector.CaptureKey(**row["key"]), row["elapsed_ns"],
            discovery_selector.ObservationCounts(**row["counts"]),
            discovery_selector.StopReason(row["stop_reason"]), tuple(row["validity_failures"])))
    selected = discovery_selector.select_duration(observed)
    if selected.state != discovery_selector.SelectionState.selected:
        raise ControllerError("discovery has no selected duration")
    expected_selection = dict(state=selected.state.value,
        selected_duration_ns=selected.selected_duration_ns,
        eligible_durations_ns=list(selected.eligible_durations_ns),
        present_captures=selected.present_captures, diagnostic_only=True,
        formal_runs_contributed=0, execution_authority=False)
    if registry.canonical(study.get("selection")) != registry.canonical(expected_selection):
        raise ControllerError("discovery selection differs from all retained counts")
    if (action == "Q16a" and (plan["measurement_ns"] != selected.selected_duration_ns
            or plan["minimum_observations_per_series"] != discovery_selector.MINIMUM_OBSERVATIONS_PER_SEQUENCE)):
        raise ControllerError("formal Q16a duration/minimum differs from accepted discovery selection")
    prior_results = {}
    for prior in ("Q16a", "Q16b"):
        binding = prerequisites[prior.lower() + "_validation"]
        required = prior == "Q16a" and action in {"Q16b", "Q16c"} or prior == "Q16b" and action == "Q16c"
        if not required:
            if binding is not None:
                raise ControllerError("formal prerequisite references a future phase")
            continue
        result = _bound_document(binding, prior + " independent calibration")
        validate_prior_calibration(result, prior, plan, selected.selected_duration_ns)
        prior_results[prior] = result
    if "Q16a" in prior_results:
        validate_ring_reuse(plan, prior_results["Q16a"], prerequisites["q16a_validation"])
    namespace = _bound_document(prerequisites["namespace_registry"], "prospective namespace registration")
    if not isinstance(namespace, dict) or set(namespace) != {
            "schema_version", "plan_sha256", "stand_id", "phase_identities",
            "schedule_namespaces", "execution_authority"}:
        raise ControllerError("namespace registration field set differs")
    expected_ids = [item["capture"][phase] for item in plan["captures"] for phase in ("warmup", "measurement")]
    if (namespace.get("schema_version") != "cpu-prefetch-stage17-formal-namespace-registration/1"
            or namespace.get("plan_sha256") != registry.sha256(registry.canonical(plan))
            or namespace.get("stand_id") != plan["stand_id"] or namespace.get("phase_identities") != expected_ids
            or namespace.get("execution_authority") is not False):
        raise ControllerError("formal namespace registration differs from the complete prospective family")
    sources = prerequisites["schedule_sources"]
    if (not isinstance(sources, list) or not isinstance(namespace["schedule_namespaces"], list)
            or (action != "Q16c" and (sources or namespace["schedule_namespaces"]))):
        raise ControllerError("unexpected scheduled-source prerequisites")
    if action == "Q16c":
        validate_schedule_sources(plan, sources, namespace["schedule_namespaces"], prior_results["Q16b"])
    return extent


def _prepare_action(*, for_retention, **arguments):
    activate()
    authorization, authorization_bytes = support._load(arguments["authorization_path"])
    if authorization.get("schema_version") != "cpu-prefetch-stage17-phase-action-authorization/6":
        if for_retention:
            raise ControllerError("formal retention preparation requires an explicit v6 authority")
        return _prepare_legacy(**arguments)
    root = arguments["repository_root"].resolve()
    pinned = registry.pin_registry(root)
    registry.validate_document(pinned, authorization, registry.schema_path("phase-action-authorization"), "formal authorization")
    now = support._now()
    validation = journal_runtime.validate_operational_journal(repository_root=root,
        evidence_root=arguments["operational_evidence_root"], latest_journal=arguments["journal"],
        journal_directory=arguments["journal_directory"], pilot_archive=arguments.get("pilot_archive"),
        pilot_sidecar=arguments.get("pilot_sidecar"), as_of_utc=now,
        allow_synthetic_test_evidence=arguments.get("synthetic_test_only", False))
    definition = pinned.action(authorization["action_id"])
    expected = [old._binding(validation.resolutions[key]) for key in definition["required_resolution_ids"]]
    trust = validation.resolutions["S17-EXT-003"].semantic_context["trust"]
    if (validation.current_state != definition["required_state"]
            or authorization["predecessor_resolutions"] != expected
            or authorization["fixed_action_definition_sha256"] != pinned.plan_sha256
            or authorization["permission_matrix"] != definition["permission_matrix"]
            or authorization["actor"] != trust["measurements"]["principal"]
            or authorization["reviewer"] != trust["measurements"]["reviewer_role"]
            or authorization["target"]["stand_id"] != trust["subject_id"]
            or authorization["trust_context"] != {"ext002_resolution": expected[1], "ext003_resolution": expected[2]}):
        raise ControllerError("formal authority/trust/state/predecessor differs")
    support._verify_signature(authorization_bytes, arguments["signature_path"], trust)
    _, request_bytes = support._read_binding(authorization["request_binding"], "formal request")
    request = json.loads(request_bytes)
    registry.validate_document(pinned, request, registry.schema_path("fixed-action-request"), "formal request")
    if request_bytes != registry.canonical(request):
        raise ControllerError("formal request is not canonical")
    runtime, release, worker_path = runtime_from_context(validation)
    if (request["runtime_binding"] != runtime or request["release_binding"] != release
            or request["predecessor_resolutions"] != expected
            or request["evidence_root_binding"] != authorization["evidence_root_binding"]
            or request["stand_id"] != authorization["target"]["stand_id"]
            or any(request[key] != authorization[key] for key in ("action_id", "session_id", "authorization_id"))
            or request["synthetic_test_only"] is not arguments.get("synthetic_test_only", False)):
        raise ControllerError("formal request lineage differs")
    extent = validate_action_inputs(request, validation)
    policy = deadline_policy(extent)
    issued, expires, actual = (support._parse_utc(value) for value in (
        authorization["issued_at_utc"], authorization["expires_at_utc"], now))
    if (authorization["deadline_policy"] != policy or not issued < expires or actual < issued
            or (not for_retention and actual >= expires)
            or expires - issued > dt.timedelta(seconds=policy["session_max_wall_seconds"])):
        raise ControllerError("formal deadline/authority window differs")
    support._read_binding({"path": str(worker_path), "size_bytes": runtime["size_bytes"],
                          "sha256": runtime["sha256"]}, "qualified formal worker")
    return PreparedAction(root, authorization, authorization_bytes, request, request_bytes,
                          runtime, worker_path, release, validation, pinned)


def prepare_action(**arguments):
    return _prepare_action(for_retention=False, **arguments)


def prepare_retention(**arguments):
    """Authenticate past v6 collection for custody; never authorize execution."""
    return _prepare_action(for_retention=True, **arguments)


def execute_once(**arguments):
    prepared = prepare_action(**arguments)
    if prepared.request.get("schema_version") != "cpu-prefetch-stage17-fixed-action-request/6":
        return _with_globals(predecessor.execute_once,
            {"activate": activate, "prepare_action": lambda **unused: prepared}, arguments)
    import stage17_fixed_action_executor_v10 as executor
    return executor.execute_fixed_action(repository_root=prepared.root,
        authorization=prepared.authorization, authorization_bytes=prepared.authorization_bytes,
        request=prepared.request, request_bytes=prepared.request_bytes,
        worker_binding=prepared.runtime, worker_path=prepared.worker_path,
        release_binding=prepared.release,
        output_root=pathlib.Path(prepared.request["evidence_root_binding"]["absolute_path"]),
        synthetic_test_only=arguments.get("synthetic_test_only", False))
