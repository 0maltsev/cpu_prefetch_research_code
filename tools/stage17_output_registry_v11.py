"""Persistent formal-family custody admission; independent science remains pending.

Only explicit v6 requests use this contract. Historical formal and diagnostic
requests retain their previous validators. No admission here grants EXT007 or
turns native completion into scientific validity.
"""
from __future__ import annotations

import json
import os
import pathlib

from jsonschema import Draft202012Validator

import stage17_output_registry_v10 as predecessor
import stage17_formal_plan_v1 as contract

base = predecessor.base
OutputAdmissionError = base.OutputAdmissionError
PinnedOutputRegistry = base.PinnedOutputRegistry
validate_document = base.validate_document
canonical = base.canonical
sha256 = base.sha256_bytes
FORMAL_ACTIONS = frozenset(("Q16a", "Q16b", "Q16c"))
PLAN_PATH = "config/stage17/stage17-fixed-phase-actions-v8.json"
PLAN_SCHEMA = "config/schemas/stage17-fixed-phase-actions-v8.schema.json"
REPORT_SCHEMA = "config/schemas/stage17-formal-retention-report-v1.schema.json"
REPORT_NAME = "formal-retention-report.json"
RESULT_NAME = "stage17-action-result-v6.json"
FAMILIES = predecessor.FAMILIES


def schema_path(family):
    if family not in FAMILIES:
        raise OutputAdmissionError("unknown formal schema family")
    return f"config/schemas/stage17-{family}-v6.schema.json"


def pin_registry(root):
    old = predecessor.pin_registry(root)
    schemas = dict(old.schemas)
    for path in (PLAN_SCHEMA, REPORT_SCHEMA, *contract.SCHEMA.values(),
                 *(schema_path(family) for family in FAMILIES)):
        payload = base._safe_repository_file(root, pathlib.PurePosixPath(path))
        document = json.loads(payload)
        Draft202012Validator.check_schema(document)
        schemas[path] = base.PinnedSchema(path, len(payload), sha256(payload), document,
                                          Draft202012Validator(document))
    payload = base._safe_repository_file(root, pathlib.PurePosixPath(PLAN_PATH))
    plan = json.loads(payload)
    schemas[PLAN_SCHEMA].validator.validate(plan)
    if plan["predecessor"] != {"path": predecessor.PLAN_PATH,
                               "size_bytes": len(old.plan_bytes), "sha256": old.plan_sha256}:
        raise OutputAdmissionError("formal profile predecessor binding differs")
    for previous, current in zip(old.plan["actions"], plan["actions"], strict=True):
        if previous["action_id"] not in FORMAL_ACTIONS:
            if previous != current:
                raise OutputAdmissionError("formal profile changed an unrelated action")
        elif {k: v for k, v in previous.items() if k != "outputs"} != {
                k: v for k, v in current.items() if k != "outputs"}:
            raise OutputAdmissionError("formal profile changed permissions or prerequisite state")
    old_policy = dict(plan["execution_policy"])
    del old_policy["formal_entrypoint"], old_policy["formal_deadline"]
    if old_policy != old.plan["execution_policy"]:
        raise OutputAdmissionError("formal profile changed historical execution policy")
    return base.PinnedOutputRegistry(payload, sha256(payload), plan, schemas)


def capture_names(action, ordinal):
    if action not in FORMAL_ACTIONS or type(ordinal) is not int or ordinal < 0:
        raise OutputAdmissionError("invalid formal capture identity")
    prefix = f"{action.lower()}-c{ordinal}"
    names = []
    for phase in ("warmup", "measurement"):
        for role in ("producer", "consumer"):
            names.append(f"{prefix}-{phase}-{role}.bin")
            if action == "Q16a":
                names.append(f"{prefix}-{phase}-{role}-demand.bin")
    if action != "Q16a":
        names.append(prefix + "-node-order.bin")
    if action == "Q16c":
        names.extend(f"{prefix}-{phase}-schedule.bin" for phase in ("warmup", "measurement"))
    names.append(prefix + "-control.json")
    return tuple(names)


def artifact_identity(action, name):
    if name == REPORT_NAME:
        return "FORMAL_CALIBRATION_RETENTION_REPORT", "cpu-prefetch-stage17-formal-retention-report/1", "application/json"
    if name.endswith("-control.json"):
        kind = {"Q16a": "ring", "Q16b": "service", "Q16c": "scheduled"}[action]
        return action.upper() + "_FORMAL_CAPTURE_CONTROL", f"cpu-prefetch-stage17-formal-{kind}-control/1", "application/json"
    role, schema = action.upper() + "_PRIMARY_RAW", "RAW-OBS-U64LE-LP-RUNID-v1"
    if name.endswith("-demand.bin"):
        if action != "Q16a":
            raise OutputAdmissionError("unexpected formal demand stream")
        role, schema = "Q16A_DEMAND_RAW", "Q16A-DEMAND-U64LE-LP-RUNID-v1"
    elif name.endswith("-node-order.bin"):
        if action == "Q16a":
            raise OutputAdmissionError("unexpected formal node order")
        role, schema = action.upper() + "_NODE_ORDER", "NODEORDER-U64LE-v1"
    elif name.endswith("-schedule.bin"):
        if action != "Q16c":
            raise OutputAdmissionError("unexpected formal schedule")
        role, schema = "Q16C_PREPARED_SCHEDULE", "SCHEDULE-DEADLINES-U64LE-v1"
    elif not name.endswith(("-producer.bin", "-consumer.bin")):
        raise OutputAdmissionError("unknown formal artifact")
    return role, schema, "application/octet-stream"


def _same(actual, expected, label):
    # bool/integer equality cannot admit a different JSON type.
    if canonical(actual) != canonical(expected):
        raise OutputAdmissionError(label + " differs")


def _bound_report(directory_fd, binding, maximum_bytes):
    """Parse the exact bounded bytes whose binding was checked on one descriptor."""
    if binding["size_bytes"] > maximum_bytes:
        raise OutputAdmissionError("formal family metadata exceeds prospective bound")
    descriptor, before = base._open_output(directory_fd, binding["file_name"])
    try:
        if before.st_size != binding["size_bytes"]:
            raise OutputAdmissionError("formal report size differs")
        payload = bytearray()
        while len(payload) < before.st_size:
            chunk = os.read(descriptor, min(1024 * 1024, before.st_size - len(payload)))
            if not chunk:
                raise OutputAdmissionError("formal report was truncated")
            payload.extend(chunk)
        if os.read(descriptor, 1):
            raise OutputAdmissionError("formal report grew during reading")
        def identity(metadata):
            return (metadata.st_dev, metadata.st_ino, metadata.st_size,
                    metadata.st_mtime_ns, metadata.st_ctime_ns)
        if (identity(before) != identity(os.fstat(descriptor))
                or identity(before) != identity(os.stat(binding["file_name"], dir_fd=directory_fd,
                                                        follow_symlinks=False))
                or sha256(payload) != binding["sha256"]):
            raise OutputAdmissionError("formal report identity or hash differs")
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise OutputAdmissionError("formal report has a duplicate JSON key")
                value[key] = item
            return value
        return json.loads(payload, object_pairs_hook=unique,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (OSError, UnicodeError, ValueError) as error:
        raise OutputAdmissionError("formal report snapshot rejected: " + str(error)) from error
    finally:
        os.close(descriptor)


def validate_worker_result(*, registry, directory_fd, result, request,
                           authorization_sha256, synthetic_test_only):
    if request.get("schema_version") != "cpu-prefetch-stage17-fixed-action-request/6":
        return predecessor.validate_worker_result(registry=registry, directory_fd=directory_fd,
            result=result, request=request, authorization_sha256=authorization_sha256,
            synthetic_test_only=synthetic_test_only)
    action = request["action_id"]
    if action not in FORMAL_ACTIONS:
        raise OutputAdmissionError("v6 request is not a formal action")
    validate_document(registry, result, schema_path("phase-action-result"), "formal result")
    for field in ("request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
                  "runtime_binding", "release_binding", "predecessor_resolutions"):
        _same(result[field], request[field], "formal result " + field)
    if (result["authorization_sha256"] != authorization_sha256
            or result["request_sha256"] != sha256(canonical(request))
            or result["synthetic_test_only"] is not synthetic_test_only
            or result["restoration_verified"] is not True or result["quarantined"] is not False):
        raise OutputAdmissionError("formal authority/restoration differs")
    plan = request["action_inputs"]["plan"]
    extent = contract.validate_plan(action, plan)
    artifacts = result["artifacts"]
    names = [item["file_name"] for item in artifacts]
    expected = {REPORT_NAME}
    for capture in extent.captures:
        expected.update(capture_names(action, capture.ordinal))
    if len(names) != len(set(names)) or set(names) != expected:
        raise OutputAdmissionError("formal retained artifact family is not exact")
    indexed = {item["file_name"]: item for item in artifacts}
    for item in artifacts:
        if (item["role"], item["schema_identity"], item["media_type"]) != artifact_identity(action, item["file_name"]):
            raise OutputAdmissionError("formal artifact role/schema/media differs")
        if item["file_name"] != REPORT_NAME:
            predecessor._stream(directory_fd, item, extent.declared.max_output_bytes)
    if sum(item["size_bytes"] for item in artifacts) > extent.declared.max_output_bytes:
        raise OutputAdmissionError("formal family output exceeds prospective bound")
    if indexed[REPORT_NAME]["size_bytes"] > extent.declared.metadata_output_bytes:
        raise OutputAdmissionError("formal family metadata exceeds prospective bound")
    report = _bound_report(directory_fd, indexed[REPORT_NAME], extent.declared.metadata_output_bytes)
    validate_document(registry, report, REPORT_SCHEMA, "formal retention report")
    hardware = request["action_inputs"]["hardware_control"]
    if (report["plan_sha256"] != sha256(canonical(plan)) or report["action_id"] != action
            or report["mapping_id"] != hardware["mapping_id"]):
        raise OutputAdmissionError("formal retained plan/mapping identity differs")
    prestate = hardware["prestate"]
    for state, plot in zip(("H0", "H1"), report["whole_plots"], strict=True):
        applied = [{"cpu": v["cpu"], "complete_value_hex": f"{int(v['complete_value_hex'], 16) | 15:016x}"}
                   for v in prestate] if state == "H1" else []
        _same(plot, dict(state=state, apply_readback=applied,
                        restore_readback=list(reversed(prestate)) if state == "H1" else [],
                        restoration_verified=True), "formal whole-plot action readbacks")
    if len(report["captures"]) != len(extent.captures) or len(report["native_results_after_cleanup"]) != len(extent.captures):
        raise OutputAdmissionError("formal retention or final-cleanup count differs")
    for capture, retained in zip(extent.captures, report["captures"], strict=True):
        bindings = [indexed[name] for name in capture_names(action, capture.ordinal)]
        references = [{field: item[field] for field in ("file_name", "size_bytes", "sha256")} for item in bindings]
        _same(retained, {"ordinal": capture.ordinal, "artifacts": references,
                         "native_complete": True}, "formal capture retention")
        if sum(item["size_bytes"] for item in bindings) > capture.declared.max_output_bytes:
            raise OutputAdmissionError("formal capture output exceeds prospective bound")
        if sum(item["size_bytes"] for item in bindings if item["media_type"] == "application/json") > capture.declared.metadata_output_bytes:
            raise OutputAdmissionError("formal capture metadata exceeds prospective bound")
    return report
