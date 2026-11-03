"""Diagnostic custody admission; formal actions delegate unchanged to v8/v4.

This admits retained bytes and lineage, never scientific validity, duration
selection, formal calibration credit or a new operational resolution.
"""
from __future__ import annotations

import json
import os
import pathlib
import stat

from jsonschema import Draft202012Validator

import stage17_output_registry_v8 as predecessor
import stage17_discovery_contract_v1 as contract

base = predecessor.base
ACTION = "Q16A-DURATION-DISCOVERY"
PLAN_PATH = "config/stage17/stage17-fixed-phase-actions-v7.json"
PLAN_SCHEMA = "config/schemas/stage17-fixed-phase-actions-v7.schema.json"
REPORT_SCHEMA = "config/schemas/stage17-discovery-retention-report-v1.schema.json"
REPORT_NAME = "retention-report.json"
RESULT_NAME = "stage17-action-result-v5.json"
FAMILIES = ("fixed-action-request", "phase-action-authorization", "fixed-action-context",
            "phase-action-result", "phase-action-attempt", "phase-action-failure",
            "phase-action-completion")
OutputAdmissionError = base.OutputAdmissionError
validate_document = base.validate_document
canonical = base.canonical
sha256 = base.sha256_bytes


def schema_path(family: str) -> str:
    return f"config/schemas/stage17-{family}-v5.schema.json"


def pin_registry(root: pathlib.Path) -> base.PinnedOutputRegistry:
    old = base.pin_registry(root)
    schemas = dict(old.schemas)
    for path in (PLAN_SCHEMA, REPORT_SCHEMA, contract.SCHEMA_PATH,
                 *(schema_path(family) for family in FAMILIES)):
        payload = base._safe_repository_file(root, pathlib.PurePosixPath(path))
        document = json.loads(payload)
        Draft202012Validator.check_schema(document)
        schemas[path] = base.PinnedSchema(path, len(payload), sha256(payload), document,
                                          Draft202012Validator(document))
    payload = base._safe_repository_file(root, pathlib.PurePosixPath(PLAN_PATH))
    plan = json.loads(payload)
    schemas[PLAN_SCHEMA].validator.validate(plan)
    if (plan["actions"][:6] != old.plan["actions"] or len(plan["actions"]) != 7
            or plan["actions"][-1]["action_id"] != ACTION
            or plan["predecessor"] != {"path": base.PLAN_PATH.as_posix(),
                                       "size_bytes": len(old.plan_bytes), "sha256": old.plan_sha256}):
        raise OutputAdmissionError("diagnostic profile changed formal actions or predecessor")
    return base.PinnedOutputRegistry(payload, sha256(payload), plan, schemas)


def capture_names(ordinal: int) -> tuple[str, ...]:
    return tuple(f"discovery-c{ordinal:02d}-{phase}-{kind}"
                 for phase in ("warmup", "measurement")
                 for kind in ("producer.bin", "consumer.bin", "demand.bin")) + (
                     f"discovery-c{ordinal:02d}-control.json",)


def artifact_identity(name: str) -> tuple[str, str | None, str]:
    if name == REPORT_NAME:
        return "DISCOVERY_RETENTION_REPORT", "cpu-prefetch-stage17-discovery-retention-report/1", "application/json"
    if name == "studyhardware.json":
        return "DISCOVERY_HARDWARE_STATE", "cpu-prefetch-stage17-discovery-hardware/1", "application/json"
    for suffix, role, schema, media in (
            ("-producer.bin", "DISCOVERY_PRODUCER_RAW", base.RAW_SCHEMA, "application/octet-stream"),
            ("-consumer.bin", "DISCOVERY_CONSUMER_RAW", base.RAW_SCHEMA, "application/octet-stream"),
            ("-demand.bin", "DISCOVERY_DEMAND_RAW", "DISCOVERY-FOUR-U64LE-VECTORS-v1", "application/octet-stream"),
            ("-control.json", "DISCOVERY_CAPTURE_CONTROL", "cpu-prefetch-stage17-discovery-control/1", "application/json")):
        if name.endswith(suffix):
            return role, schema, media
    raise OutputAdmissionError("unknown diagnostic artifact")


def _stream(directory_fd: int, binding: dict, maximum: int) -> None:
    name = binding["file_name"]
    if not name or "/" in name or name in {".", ".."}:
        raise OutputAdmissionError("unsafe diagnostic artifact name")
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size != binding["size_bytes"]
                or metadata.st_size > maximum
                or base.sha256_fd(descriptor, metadata.st_size) != binding["sha256"]):
            raise OutputAdmissionError("diagnostic artifact bytes/budget differ")
    finally:
        os.close(descriptor)


def validate_worker_result(*, registry, directory_fd, result, request,
                           authorization_sha256, synthetic_test_only):
    if request["action_id"] != ACTION:
        return base.validate_worker_result(registry=registry, directory_fd=directory_fd,
            result=result, request=request, authorization_sha256=authorization_sha256,
            synthetic_test_only=synthetic_test_only)
    validate_document(registry, result, schema_path("phase-action-result"), "diagnostic result")
    for field in ("request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
                  "runtime_binding", "release_binding", "predecessor_resolutions"):
        if result[field] != request[field]:
            raise OutputAdmissionError("diagnostic result lineage drifted: " + field)
    if (result["authorization_sha256"] != authorization_sha256
            or result["request_sha256"] != sha256(canonical(request))
            or result["synthetic_test_only"] is not synthetic_test_only
            or not result["restoration_verified"] or result["quarantined"]):
        raise OutputAdmissionError("diagnostic result authority/restoration differs")
    plan = contract.validate_plan(request["action_inputs"]["plan"])
    artifacts = result["artifacts"]
    names = [item["file_name"] for item in artifacts]
    expected = {REPORT_NAME, "studyhardware.json"}
    for capture in plan.captures:
        expected.update(capture_names(capture.ordinal))
    if len(names) != len(set(names)) or set(names) != expected:
        raise OutputAdmissionError("diagnostic output set is not exact")
    indexed = {item["file_name"]: item for item in artifacts}
    for item in artifacts:
        if (item["role"], item["schema_identity"], item["media_type"]) != artifact_identity(item["file_name"]):
            raise OutputAdmissionError("diagnostic role/schema/media differs")
        _stream(directory_fd, item, plan.maximum_output_bytes)
    if sum(item["size_bytes"] for item in artifacts) > plan.maximum_output_bytes:
        raise OutputAdmissionError("diagnostic total output exceeds frozen bound")
    report = base._json_output(directory_fd, REPORT_NAME, indexed[REPORT_NAME]["size_bytes"])
    validate_document(registry, report, REPORT_SCHEMA, "diagnostic retention report")
    if report["plan_sha256"] != plan.sha256:
        raise OutputAdmissionError("retained diagnostic plan hash differs")
    def short(item):
        return {field: item[field] for field in ("file_name", "size_bytes", "sha256")}
    if report["hardware_state"] != short(indexed["studyhardware.json"]):
        raise OutputAdmissionError("retained hardware binding differs")
    study_metadata = indexed[REPORT_NAME]["size_bytes"] + indexed["studyhardware.json"]["size_bytes"]
    if study_metadata > plan.budget.metadata_output_bytes:
        raise OutputAdmissionError("diagnostic study metadata exceeds bound")
    for capture, retained in zip(plan.captures, report["captures"], strict=True):
        expected_files = [short(indexed[name]) for name in capture_names(capture.ordinal)]
        if (retained["ordinal"] != capture.ordinal
                or retained["warmup_run_id"] != capture.warmup.run_id
                or retained["measurement_run_id"] != capture.measurement.run_id
                or retained["artifacts"] != expected_files
                or sum(item["size_bytes"] for item in expected_files) > capture.budget.max_output_bytes):
            raise OutputAdmissionError("diagnostic capture identity/artifact/budget differs")
        if retained["failure_reasons"] or (
                retained["native_stop"], retained["native_validity"]) not in {
                    ("complete", "VALID"), ("complete", "INSUFFICIENT"),
                    ("trace_capacity", "INSUFFICIENT")}:
            raise OutputAdmissionError("native stop/validity/failure claims disagree")
    return report
