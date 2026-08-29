#!/usr/bin/env python3
"""Pinned, closed-world Stage 17 fixed-action output verification.

This module is a production dependency.  It never imports a test schema and it
does not accept a caller supplied role/schema pair.  JSON schemas are loaded
and hashed once before an attempt marker is created; validation after the
worker exits uses only those in-memory validators.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import pathlib
import stat
from dataclasses import dataclass
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import stage17_raw_stream_decoder_v1 as raw_decoder


PLAN_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-fixed-phase-actions-v4.json"
)
PLAN_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-fixed-phase-actions-v4.schema.json"
)
RESULT_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-phase-action-result-v4.schema.json"
)
RESULT_NAME = "stage17-action-result-v4.json"
RAW_SCHEMA = "RAW-OBS-U64LE-LP-RUNID-v1"
RAW_ROLES = frozenset({
    "PRODUCER_RAW_OBSERVATIONS", "CONSUMER_RAW_OBSERVATIONS",
    "JOINED_RAW_OBSERVATIONS",
})
RUN_JSON = {
    "PHASE_INTEGRITY": (
        "cpu-prefetch-phase-integrity-report/2", None,
    ),
    "PRODUCER_RAW_ENVELOPE": ("2.0.0-pre.3", None),
    "CONSUMER_RAW_ENVELOPE": ("2.0.0-pre.3", None),
    "JOINED_RAW_ENVELOPE": ("2.0.0-pre.3", None),
    "JOIN_AUDIT": (
        "cpu-prefetch-stage17-join-audit/3",
        "config/schemas/stage17-join-audit-v3.schema.json",
    ),
    "PAGE_RESIDENCY_PROVENANCE": (
        "cpu-prefetch-stage17-page-residency/3",
        "config/schemas/stage17-page-residency-v3.schema.json",
    ),
}
PILOT_HARDWARE_ROLE = "STAGE17_PILOT_HARDWARE_STATE"
PILOT_HARDWARE_SCHEMA = (
    "config/schemas/stage17-pilot-hardware-state-v2.schema.json"
)
CALIBRATION_HARDWARE_SCHEMA = (
    "config/schemas/stage17-calibration-hardware-state-v1.schema.json"
)
SUMMARY_ROLE = {
    "Q16b": ("Q16B_SERVICE_RATE_CAPTURE", "cpu-prefetch-stage17-q16b-output/3"),
    "Q16c": ("Q16C_ZERO_LOSS_FEASIBILITY_CAPTURE", "cpu-prefetch-stage17-q16c-output/3"),
    "STAGE17-BLINDED-PILOT": (
        "STAGE17_BLINDED_PILOT_RUN",
        "cpu-prefetch-stage17-blinded-pilot-run/3",
    ),
}


class OutputAdmissionError(ValueError):
    pass


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_fd(descriptor: int, size: int) -> str:
    digest = hashlib.sha256()
    offset = 0
    while offset < size:
        chunk = os.pread(descriptor, min(1024 * 1024, size - offset), offset)
        if not chunk:
            raise OutputAdmissionError("artifact short read during streaming hash")
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def _safe_repository_file(root: pathlib.Path, relative: pathlib.PurePosixPath) -> bytes:
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise OutputAdmissionError("unsafe repository schema locator")
    descriptor = os.open(root / relative, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1:
            raise OutputAdmissionError("schema/plan is not a nonempty regular file")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size:
            raise OutputAdmissionError("schema/plan short read")
        return payload
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class PinnedSchema:
    path: str
    size_bytes: int
    sha256: str
    document: dict[str, Any]
    validator: Draft202012Validator


@dataclass(frozen=True)
class PinnedOutputRegistry:
    plan_bytes: bytes
    plan_sha256: str
    plan: dict[str, Any]
    schemas: Mapping[str, PinnedSchema]

    def action(self, action_id: str) -> dict[str, Any]:
        matches = [item for item in self.plan["actions"]
                   if item["action_id"] == action_id]
        if len(matches) != 1:
            raise OutputAdmissionError("action definition absent or duplicated")
        return matches[0]


def pin_registry(root: pathlib.Path) -> PinnedOutputRegistry:
    root = root.resolve()
    plan_bytes = _safe_repository_file(root, PLAN_PATH)
    plan = json.loads(plan_bytes)
    plan_schema_bytes = _safe_repository_file(root, PLAN_SCHEMA_PATH)
    plan_schema = json.loads(plan_schema_bytes)
    Draft202012Validator.check_schema(plan_schema)
    errors = list(Draft202012Validator(plan_schema).iter_errors(plan))
    if errors:
        raise OutputAdmissionError(
            f"fixed-action plan v4 schema rejection: {errors[0].message}"
        )
    if [item["ordinal"] for item in plan["actions"]] != list(range(1, 7)):
        raise OutputAdmissionError("fixed-action ordinals drifted")
    schema_paths = {
        RESULT_SCHEMA_PATH.as_posix(), PLAN_SCHEMA_PATH.as_posix(),
        "config/schemas/stage17-fixed-action-context-v4.schema.json",
        "config/schemas/stage17-phase-action-attempt-v4.schema.json",
        "config/schemas/stage17-phase-action-failure-v4.schema.json",
        "config/schemas/stage17-phase-action-completion-v4.schema.json",
    }
    for action in plan["actions"]:
        for output in action["outputs"]:
            if output["schema_path"] is not None:
                schema_paths.add(output["schema_path"])
    schema_paths.update(path for _, path in RUN_JSON.values() if path is not None)
    schema_paths.add("config/schemas/stage17-run-output-v3.schema.json")
    schema_paths.add(
        "config/schemas/stage17-sealed-pilot-artifact-manifest-v4.schema.json"
    )
    schema_paths.update({
        "config/schemas/stage17-pilot-plan-v4.schema.json",
        "config/schemas/stage17-pilot-run-attempt-v1.schema.json",
        "config/schemas/stage17-pilot-run-completion-v1.schema.json",
        "config/schemas/stage17-pilot-run-failure-v1.schema.json",
        "config/schemas/stage17-pilot-session-completion-v1.schema.json",
    })
    schema_paths.add(PILOT_HARDWARE_SCHEMA)
    schema_paths.add(CALIBRATION_HARDWARE_SCHEMA)
    pinned: dict[str, PinnedSchema] = {}
    for text in sorted(schema_paths):
        payload = _safe_repository_file(root, pathlib.PurePosixPath(text))
        document = json.loads(payload)
        Draft202012Validator.check_schema(document)
        pinned[text] = PinnedSchema(
            text, len(payload), sha256_bytes(payload), document,
            Draft202012Validator(document),
        )
    return PinnedOutputRegistry(plan_bytes, sha256_bytes(plan_bytes), plan, pinned)


def validate_document(registry: PinnedOutputRegistry, document: dict[str, Any],
                      schema_path: str, label: str) -> None:
    schema = registry.schemas.get(schema_path)
    if schema is None:
        raise OutputAdmissionError(f"unregistered production schema: {schema_path}")
    errors = sorted(schema.validator.iter_errors(document), key=lambda item: tuple(item.path))
    if errors:
        where = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise OutputAdmissionError(
            f"{label} schema rejection at {where}: {errors[0].message}"
        )


def _open_output(directory_fd: int, name: str) -> tuple[int, os.stat_result]:
    if not name or "/" in name or name in {".", ".."}:
        raise OutputAdmissionError("unsafe fixed output name")
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd
    )
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1:
        os.close(descriptor)
        raise OutputAdmissionError("fixed output is not a nonempty regular file")
    return descriptor, metadata


def _json_output(directory_fd: int, name: str, size: int) -> dict[str, Any]:
    if size > 64 * 1024 * 1024:
        raise OutputAdmissionError("JSON control output exceeds the 64 MiB bound")
    descriptor, metadata = _open_output(directory_fd, name)
    try:
        if metadata.st_size != size:
            raise OutputAdmissionError("JSON output size changed")
        payload = os.pread(descriptor, size + 1, 0)
        if len(payload) != size:
            raise OutputAdmissionError("JSON output short read")
        document = json.loads(payload)
        if not isinstance(document, dict):
            raise OutputAdmissionError("JSON output root is not an object")
        return document
    finally:
        os.close(descriptor)


def _stream_binding(directory_fd: int, binding: dict[str, Any],
                    maximum_size: int) -> None:
    descriptor, metadata = _open_output(directory_fd, binding["file_name"])
    try:
        if metadata.st_size > maximum_size:
            raise OutputAdmissionError("artifact exceeds the frozen-plan-derived bound")
        if (metadata.st_size != binding["size_bytes"]
                or sha256_fd(descriptor, metadata.st_size) != binding["sha256"]):
            raise OutputAdmissionError("artifact byte identity mismatch")
    finally:
        os.close(descriptor)


def _raw_maximum(run: dict[str, Any]) -> int:
    offered = int(run["offered_count"])
    prefix, _, _, _ = raw_decoder.row_layout(run["run_id"])
    producer = offered * (prefix + 15 * 8)
    consumer = offered * (prefix + 10 * 8)
    joined = offered * (prefix + 24 * 8)
    return max(producer, consumer, joined, 64 * 1024 * 1024)


def _msr_map(values: object) -> dict[int, str]:
    if not isinstance(values, list):
        raise OutputAdmissionError("MSR evidence is not an array")
    result: dict[int, str] = {}
    for item in values:
        if (not isinstance(item, dict) or set(item) != {
                "cpu", "complete_value_hex"}
                or item.get("cpu") in result):
            raise OutputAdmissionError("MSR evidence is malformed or duplicated")
        result[item["cpu"]] = item["complete_value_hex"]
    if set(result) != {0, 1, 26}:
        raise OutputAdmissionError("MSR evidence does not cover CPUs 0/1/26")
    return result


def _run_groups(action_id: str, request: dict[str, Any],
                artifacts: list[dict[str, Any]]) -> tuple[
                    dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]
                ]:
    ordered_runs: list[tuple[str, dict[str, Any]]] = []
    if action_id == "STAGE17-BLINDED-PILOT":
        plan = request["action_inputs"]["pilot_plan"]
        for cell in plan["cells"]:
            for run in cell["runs"]:
                materialized_run = dict(run)
                materialized_run["plan_sha256"] = request["action_inputs"][
                    "plan_sha256"
                ]
                ordered_runs.append((
                    f"pilot-b{run['repetition_ordinal']:03d}-"
                    f"e{run['execution_ordinal']:03d}-",
                    materialized_run,
                ))
    else:
        token = "q16b" if action_id == "Q16b" else "q16c"
        ordered_runs = [
            (f"{token}-r{index:05d}-", run)
            for index, run in enumerate(request["action_inputs"]["runs"])
        ]
    by_prefix: dict[str, dict[str, Any]] = {}
    for prefix, run in ordered_runs:
        if prefix in by_prefix:
            raise OutputAdmissionError("duplicate run output prefix")
        by_prefix[prefix] = run
    expected = len(by_prefix) * 10
    prefix_length = 16 if action_id == "STAGE17-BLINDED-PILOT" else 12
    grouped = {prefix: [] for prefix in by_prefix}
    for item in artifacts:
        prefix = item["file_name"][:prefix_length]
        if prefix in grouped and item["role"] in (
                set(RAW_ROLES) | set(RUN_JSON) |
                {SUMMARY_ROLE[action_id][0]}):
            grouped[prefix].append(item)
    if sum(len(group) for group in grouped.values()) != expected:
        raise OutputAdmissionError("run artifact family is incomplete")
    return by_prefix, grouped


def _validate_run_families(
    registry: PinnedOutputRegistry, directory_fd: int, action_id: str,
    request: dict[str, Any], artifacts: list[dict[str, Any]],
) -> None:
    prefixes, groups = _run_groups(action_id, request, artifacts)
    summary_role, summary_schema = SUMMARY_ROLE[action_id]
    role_set = set(RAW_ROLES) | set(RUN_JSON) | {summary_role}
    for prefix, run in prefixes.items():
        group = groups[prefix]
        if {item["role"] for item in group} != role_set or len(group) != 10:
            raise OutputAdmissionError("per-run role family is incomplete or duplicated")
        maximum = _raw_maximum(run)
        raw_hashes: dict[str, str] = {}
        documents: dict[str, dict[str, Any]] = {}
        for binding in group:
            _stream_binding(directory_fd, binding, maximum)
            role = binding["role"]
            if role in RAW_ROLES:
                if binding["media_type"] != "application/octet-stream" or binding["schema_identity"] != RAW_SCHEMA:
                    raise OutputAdmissionError("raw observation contract drifted")
                raw_hashes[role] = binding["sha256"]
                continue
            if binding["media_type"] != "application/json":
                raise OutputAdmissionError("run JSON artifact media type drifted")
            document = _json_output(directory_fd, binding["file_name"], binding["size_bytes"])
            documents[role] = document
            if role == summary_role:
                if binding["schema_identity"] != summary_schema:
                    raise OutputAdmissionError("run summary schema identity drifted")
                validate_document(registry, document,
                                  "config/schemas/stage17-run-output-v3.schema.json",
                                  binding["file_name"])
                if any(document.get(key) != run.get(key) for key in (
                    "run_id", "plan_sha256", "schedule_sha256", "seed_id",
                    "runner_admission_sha256", "package", "cell_ordinal",
                    "repetition_ordinal", "hardware_state", "placement",
                    "working_set_class", "load_level",
                )):
                    raise OutputAdmissionError("run summary differs from signed request")
                if document["offered_count"] != run["offered_count"]:
                    raise OutputAdmissionError("run offered count differs from frozen plan")
            else:
                identity, schema_path = RUN_JSON[role]
                if binding["schema_identity"] != identity:
                    raise OutputAdmissionError("run JSON schema identity drifted")
                if schema_path is not None:
                    validate_document(registry, document, schema_path,
                                      binding["file_name"])
        audit = documents.get("JOIN_AUDIT")
        summary = documents.get(summary_role)
        if summary is None:
            raise OutputAdmissionError("run summary is absent")
        raw_bindings = {item["role"]: item for item in group
                        if item["role"] in RAW_ROLES}
        independently_joined = raw_decoder.reconcile(
            pathlib.Path(f"/proc/self/fd/{directory_fd}"),
            {
                "schema_version": "cpu-prefetch-stage17-raw-stream-contract/1",
                "run_id": run["run_id"],
                "physical_format": RAW_SCHEMA,
                "streams": {
                    "producer": {
                        "path": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["offered_count"],
                    },
                    "consumer": {
                        "path": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["consumed_count"],
                    },
                    "joined": {
                        "path": raw_bindings["JOINED_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["JOINED_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["JOINED_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["accepted_count"],
                    },
                },
            },
        )
        if (independently_joined["offered_count"] != summary["offered_count"]
                or independently_joined["accepted_count"] != summary["accepted_count"]
                or independently_joined["full_count"] != summary["full_count"]
                or independently_joined["consumed_count"] != summary["consumed_count"]
                or (independently_joined["zero_loss_status"] == "PASS")
                is not summary["zero_loss"]):
            raise OutputAdmissionError(
                "worker summary differs from independently decoded records"
            )
        if (audit is None or audit.get("run_id") != run["run_id"]
                or audit.get("producer_raw_sha256")
                != raw_hashes.get("PRODUCER_RAW_OBSERVATIONS")
                or audit.get("consumer_raw_sha256")
                != raw_hashes.get("CONSUMER_RAW_OBSERVATIONS")
                or audit.get("joined_raw_sha256")
                != raw_hashes.get("JOINED_RAW_OBSERVATIONS")
                or audit.get("producer_rows") != summary["offered_count"]
                or audit.get("accepted_rows") != summary["accepted_count"]
                or audit.get("full_rows") != summary["full_count"]
                or audit.get("consumer_rows") != summary["consumed_count"]
                or audit.get("join_status") != "PASSED"
                or audit.get("record_index_is_event_identity") is not False):
            raise OutputAdmissionError("join audit differs from exact raw stream bytes")
        for role in ("PRODUCER_RAW_ENVELOPE", "CONSUMER_RAW_ENVELOPE",
                     "JOINED_RAW_ENVELOPE"):
            if documents.get(role, {}).get("run_id") != run["run_id"]:
                raise OutputAdmissionError("raw envelope run lineage drifted")
        residency = documents.get("PAGE_RESIDENCY_PROVENANCE")
        expected_consumer = 1 if run["placement"] == "NEAR" else 26
        if (residency is None or residency.get("run_id") != run["run_id"]
                or residency.get("producer_cpu") != 0
                or residency.get("consumer_cpu") != expected_consumer
                or residency.get("producer_migrated") is not False
                or residency.get("consumer_migrated") is not False
                or residency.get("verified") is not True):
            raise OutputAdmissionError("page/affinity/migration evidence drifted")


def _validate_q16a_family(
    registry: PinnedOutputRegistry, directory_fd: int,
    request: dict[str, Any], artifacts: list[dict[str, Any]],
) -> None:
    captures = request["action_inputs"]["captures"]
    if len(artifacts) != len(captures) * 2 + 1:
        raise OutputAdmissionError("Q16a capture artifact family is incomplete")
    for capture in captures:
        prefix = (
            f"q16a-c{capture['context_ordinal']:02d}-"
            f"r{capture['repetition_ordinal']:03d}-"
        )
        group = [item for item in artifacts
                 if item["file_name"].startswith(prefix)]
        if len(group) != 2 or {item["role"] for item in group} != {
            "Q16A_RING_DISTANCE_CAPTURE", "Q16A_RING_DEMAND_TRACE",
        }:
            raise OutputAdmissionError("Q16a per-capture pair is incomplete")
        expected = {
            "Q16A_RING_DISTANCE_CAPTURE": (
                "cpu-prefetch-stage17-q16a-output/3",
                "config/schemas/stage17-q16a-output-v3.schema.json",
                prefix + "output-v3.json",
            ),
            "Q16A_RING_DEMAND_TRACE": (
                "cpu-prefetch-stage17-q16a-trace/3",
                "config/schemas/stage17-q16a-trace-v3.schema.json",
                prefix + "trace-v3.json",
            ),
        }
        for binding in group:
            identity, schema_path, name = expected[binding["role"]]
            if (binding["schema_identity"] != identity
                    or binding["media_type"] != "application/json"
                    or binding["file_name"] != name):
                raise OutputAdmissionError("Q16a output identity drifted")
            _stream_binding(directory_fd, binding, 64 * 1024 * 1024)
            document = _json_output(
                directory_fd, binding["file_name"], binding["size_bytes"]
            )
            validate_document(registry, document, schema_path, name)
            for field in (
                "calibration_plan_sha256", "seed_id", "context_ordinal",
                "repetition_ordinal", "hardware_state", "placement",
                "working_set_class",
            ):
                if document[field] != capture[field]:
                    raise OutputAdmissionError(
                        "Q16a output differs from signed capture request"
                    )


def _validate_calibration_hardware(
    registry: PinnedOutputRegistry, directory_fd: int, action_id: str,
    request: dict[str, Any], artifacts: list[dict[str, Any]], run_count: int,
) -> None:
    matches = [item for item in artifacts
               if item["role"] == "STAGE17_CALIBRATION_HARDWARE_STATE"]
    if len(matches) != 1:
        raise OutputAdmissionError(
            "calibration hardware-state evidence is absent or duplicated"
        )
    binding = matches[0]
    expected_name = f"stage17-{action_id}-hardware-state-v1.json"
    if (binding["schema_identity"]
            != "cpu-prefetch-stage17-calibration-hardware-state/1"
            or binding["file_name"] != expected_name
            or binding["media_type"] != "application/json"):
        raise OutputAdmissionError("calibration hardware-state identity drifted")
    _stream_binding(directory_fd, binding, 64 * 1024 * 1024)
    document = _json_output(
        directory_fd, binding["file_name"], binding["size_bytes"]
    )
    validate_document(
        registry, document, CALIBRATION_HARDWARE_SCHEMA,
        "calibration hardware state",
    )
    control = request["action_inputs"]["hardware_control"]
    if (document["action_id"] != action_id
            or document["plan_sha256"]
            != request["action_inputs"]["plan_sha256"]
            or document["q15_w_result_sha256"]
            != control["q15_w_result_sha256"]
            or document["run_count"] != run_count
            or _msr_map(document["restore_readback"])
            != _msr_map(control["prestate"])
            or [item["cpu"] for item in document["apply_readback"]]
            != [0, 1, 26]):
        raise OutputAdmissionError(
            "calibration hardware state differs from signed request"
        )


def validate_worker_result(
    *, registry: PinnedOutputRegistry, directory_fd: int,
    result: dict[str, Any], request: dict[str, Any], authorization_sha256: str,
    synthetic_test_only: bool,
) -> None:
    validate_document(registry, result, RESULT_SCHEMA_PATH.as_posix(), "worker result")
    action_id = request["action_id"]
    if (result["authorization_sha256"] != authorization_sha256
            or result["request_sha256"] != sha256_bytes(canonical(request))
            or result["request_id"] != request["request_id"]
            or result["attempt_id"] != request["attempt_id"]
            or result["action_id"] != action_id
            or result["runtime_binding"] != request["runtime_binding"]
            or result["release_binding"] != request["release_binding"]
            or result["predecessor_resolutions"] != request["predecessor_resolutions"]
            or result["synthetic_test_only"] is not synthetic_test_only
            or result["phase18_authority"] is not False):
        raise OutputAdmissionError("worker result lineage differs from signed request")
    artifacts = result["artifacts"]
    names = [item["file_name"] for item in artifacts]
    if len(names) != len(set(names)) or RESULT_NAME in names:
        raise OutputAdmissionError("worker output names are duplicated/reserved")
    if action_id == "Q16a":
        _validate_q16a_family(registry, directory_fd, request, artifacts)
        _validate_calibration_hardware(
            registry, directory_fd, action_id, request, artifacts,
            len(request["action_inputs"]["captures"]),
        )
        return
    if action_id in {"Q16b", "Q16c", "STAGE17-BLINDED-PILOT"}:
        _validate_run_families(registry, directory_fd, action_id, request, artifacts)
        if action_id in {"Q16b", "Q16c"}:
            if len(artifacts) != len(request["action_inputs"]["runs"]) * 10 + 1:
                raise OutputAdmissionError(
                    "Q16 result contains an incomplete/expanded output family"
                )
            _validate_calibration_hardware(
                registry, directory_fd, action_id, request, artifacts,
                len(request["action_inputs"]["runs"]),
            )
        if action_id == "STAGE17-BLINDED-PILOT":
            pilot_plan = request["action_inputs"]["pilot_plan"]
            run_count = 180 * pilot_plan["repetitions_per_cell"]
            if len(artifacts) != run_count * 12 + 3:
                raise OutputAdmissionError(
                    "pilot result contains an incomplete/expanded output family"
                )
            attempts = [item for item in artifacts
                        if item["role"] == "STAGE17_PILOT_RUN_ATTEMPT"]
            completions = [item for item in artifacts
                           if item["role"] == "STAGE17_PILOT_RUN_COMPLETION"]
            if len(attempts) != run_count or len(completions) != run_count:
                raise OutputAdmissionError("pilot run lifecycle family is incomplete")
            attempt_by_prefix = {}
            completion_by_prefix = {}
            for binding, destination, schema_identity, schema_path in (
                    *((item, attempt_by_prefix,
                       "cpu-prefetch-stage17-pilot-run-attempt/1",
                       "config/schemas/stage17-pilot-run-attempt-v1.schema.json")
                      for item in attempts),
                    *((item, completion_by_prefix,
                       "cpu-prefetch-stage17-pilot-run-completion/1",
                       "config/schemas/stage17-pilot-run-completion-v1.schema.json")
                      for item in completions)):
                if binding["schema_identity"] != schema_identity:
                    raise OutputAdmissionError("pilot lifecycle schema identity drifted")
                _stream_binding(directory_fd, binding, 64 * 1024 * 1024)
                document = _json_output(
                    directory_fd, binding["file_name"], binding["size_bytes"]
                )
                validate_document(registry, document, schema_path,
                                  binding["file_name"])
                prefix = binding["file_name"][:16]
                if prefix in destination:
                    raise OutputAdmissionError("pilot lifecycle prefix duplicated")
                destination[prefix] = (binding, document)
            run_prefixes, _ = _run_groups(action_id, request, artifacts)
            if set(attempt_by_prefix) != set(run_prefixes) \
                    or set(completion_by_prefix) != set(run_prefixes):
                raise OutputAdmissionError("pilot lifecycle/run prefix lineage drifted")
            for prefix, run in run_prefixes.items():
                attempt_binding, attempt = attempt_by_prefix[prefix]
                _, completion = completion_by_prefix[prefix]
                if (attempt["session_id"] != request["session_id"]
                        or attempt["run_id"] != run["run_id"]
                        or attempt["plan_sha256"]
                        != request["action_inputs"]["plan_sha256"]
                        or attempt["authorization_sha256"] != authorization_sha256
                        or attempt["cell_ordinal"] != run["cell_ordinal"]
                        or attempt["repetition_ordinal"] != run["repetition_ordinal"]
                        or attempt["execution_ordinal"] != run["execution_ordinal"]
                        or completion["attempt_id"] != attempt["attempt_id"]
                        or completion["run_id"] != run["run_id"]
                        or completion["attempt_sha256"] != attempt_binding["sha256"]):
                    raise OutputAdmissionError("pilot lifecycle signed lineage drifted")
            hardware = [item for item in artifacts
                        if item["role"] == PILOT_HARDWARE_ROLE]
            if len(hardware) != 1:
                raise OutputAdmissionError(
                    "pilot hardware-state evidence is absent or duplicated"
                )
            hardware_binding = hardware[0]
            if (hardware_binding["schema_identity"]
                    != "cpu-prefetch-stage17-pilot-hardware-state/2"
                    or hardware_binding["file_name"]
                    != "stage17-pilot-hardware-state-v2.json"):
                raise OutputAdmissionError("pilot hardware-state identity drifted")
            _stream_binding(directory_fd, hardware_binding, 64 * 1024 * 1024)
            hardware_document = _json_output(
                directory_fd, hardware_binding["file_name"],
                hardware_binding["size_bytes"],
            )
            validate_document(
                registry, hardware_document, PILOT_HARDWARE_SCHEMA,
                "pilot hardware state",
            )
            expected_q15w = request["action_inputs"]["pilot_plan"][
                "hardware_control"
            ]["q15_w_result_sha256"]
            if hardware_document["q15_w_result_sha256"] != expected_q15w:
                raise OutputAdmissionError(
                    "pilot hardware state lacks exact Q15-W lineage"
                )
            if (_msr_map(hardware_document["restore_readback"])
                    != _msr_map(request["action_inputs"]["pilot_plan"][
                        "hardware_control"
                    ]["prestate"])
                    or [item["cpu"] for item in hardware_document[
                        "apply_readback"
                    ]] != [0, 1, 26]):
                raise OutputAdmissionError(
                    "pilot hardware-state restore/readback drifted"
                )
            manifests = [item for item in artifacts
                         if item["role"] == "SEALED_PILOT_ARTIFACT_MANIFEST"]
            if len(manifests) != 1:
                raise OutputAdmissionError("sealed pilot manifest is absent or duplicated")
            binding = manifests[0]
            _stream_binding(directory_fd, binding, 64 * 1024 * 1024)
            manifest = _json_output(directory_fd, binding["file_name"], binding["size_bytes"])
            validate_document(
                registry, manifest,
                "config/schemas/stage17-sealed-pilot-artifact-manifest-v4.schema.json",
                "sealed pilot manifest",
            )
            listed = manifest["artifacts"]
            expected = [
                {key: item[key] for key in ("role", "schema_identity", "file_name",
                                             "size_bytes", "sha256")}
                for item in artifacts
                if item["role"] not in {
                    "SEALED_PILOT_ARTIFACT_MANIFEST",
                    "STAGE17_PILOT_SESSION_COMPLETION",
                }
            ]
            if (manifest["plan_sha256"] != request["action_inputs"]["plan_sha256"]
                    or listed != expected
                    or manifest["artifact_count"] != len(expected)):
                raise OutputAdmissionError("sealed pilot manifest lineage/index drifted")
            sessions = [item for item in artifacts
                        if item["role"] == "STAGE17_PILOT_SESSION_COMPLETION"]
            if len(sessions) != 1:
                raise OutputAdmissionError("pilot session completion is absent")
            session_binding = sessions[0]
            _stream_binding(directory_fd, session_binding, 64 * 1024 * 1024)
            session = _json_output(directory_fd, session_binding["file_name"],
                                   session_binding["size_bytes"])
            validate_document(
                registry, session,
                "config/schemas/stage17-pilot-session-completion-v1.schema.json",
                "pilot session completion",
            )
            if (session["session_id"] != request["session_id"]
                    or session["authorization_id"] != request["authorization_id"]
                    or session["authorization_sha256"] != authorization_sha256
                    or session["request_sha256"] != sha256_bytes(canonical(request))
                    or session["stand_id"] != request["stand_id"]
                    or session["run_count"] != run_count
                    or session["run_attempt_sha256s"]
                    != [item["sha256"] for item in attempts]
                    or session["run_completion_sha256s"]
                    != [item["sha256"] for item in completions]
                    or session["sealed_manifest"]["sha256"] != binding["sha256"]
                    or session["hardware_state"]["sha256"]
                    != hardware_binding["sha256"]):
                raise OutputAdmissionError("pilot session completion lineage drifted")
        return
    definition = registry.action(action_id)
    expected = {(item["role"], item["schema_identity"], item["file_pattern"],
                 item["media_type"], item["schema_path"])
                for item in definition["outputs"]}
    observed = {(item["role"], item["schema_identity"], item["file_name"],
                 item["media_type"])
                for item in artifacts}
    if {(a, b, c, d) for a, b, c, d, _ in expected} != observed:
        raise OutputAdmissionError("fixed action output set differs from registry")
    for role, identity, name, media, schema_path in expected:
        binding = next(item for item in artifacts if item["file_name"] == name)
        _stream_binding(directory_fd, binding, 64 * 1024 * 1024)
        if media == "application/json":
            document = _json_output(directory_fd, name, binding["size_bytes"])
            assert schema_path is not None
            validate_document(registry, document, schema_path, name)
    if action_id == "Q15-R":
        binding = next(item for item in artifacts
                       if item["file_name"] == "q15-r-output-v3.json")
        document = _json_output(
            directory_fd, binding["file_name"], binding["size_bytes"]
        )
        values = request["action_inputs"]
        if (document["authorization_sha256"] != authorization_sha256
                or document["qualification_id"] != values["qualification_id"]
                or document["attempt_id"] != values["attempt_id"]
                or document["session_id"] != values["session_id"]
                or not document["read_only"] or not document["complete"]
                or not document["regular_probe"]["integrity_verified"]
                or not document["pointer_probe"]["integrity_verified"]):
            raise OutputAdmissionError(
                "Q15-R output differs from the signed live-probe request"
            )
    if action_id == "Q15-W":
        document = _json_output(directory_fd, "q15-w-output-v3.json",
                                next(item["size_bytes"] for item in artifacts
                                     if item["file_name"] == "q15-w-output-v3.json"))
        q15r = request["action_inputs"]
        if (document["authorization_sha256"] != authorization_sha256
                or document["q15_r_attempt_sha256"] != q15r["q15_r_attempt_sha256"]
                or document["q15_r_result_sha256"] != q15r["q15_r_result_sha256"]
                or document["session_id"] != q15r["session_id"]
                or _msr_map(document["restore_readback"])
                != _msr_map(q15r["prestate"])
                or not document["regular_probe"]["accepted"]
                or not document["regular_probe"]["integrity_verified"]
                or not document["pointer_probe"]["accepted"]
                or not document["pointer_probe"]["integrity_verified"]
                or not document["restoration_verified"]
                or document["quarantine_operation"] != {
                    "performed": False, "reason": "RESTORATION_VERIFIED"
                }):
            raise OutputAdmissionError("Q15-W lacks exact Q15-R/restoration lineage")


def policy_schema_bindings(registry: PinnedOutputRegistry) -> list[dict[str, Any]]:
    return [
        {"path": item.path, "size_bytes": item.size_bytes, "sha256": item.sha256}
        for item in sorted(registry.schemas.values(), key=lambda value: value.path)
    ]
