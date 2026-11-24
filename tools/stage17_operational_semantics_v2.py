#!/usr/bin/env python3
"""Closed-world, exact-byte semantic admission for Stage 17 EXT002--010."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import subprocess
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


MANIFEST_SCHEMA = "config/schemas/stage17-operational-input-manifest-v2.schema.json"
ARTIFACT_SCHEMA = "config/schemas/stage17-operational-artifact-v2.schema.json"
TYPED_SCHEMA = "config/schemas/stage17-operational-typed-record-v2.schema.json"
AUTH_SCHEMA = "config/schemas/stage17-phase-action-authorization-v2.schema.json"
REQUEST_SCHEMA = "config/schemas/stage17-fixed-action-request-v2.schema.json"
ATTEMPT_SCHEMA = "config/schemas/stage17-phase-action-attempt-v2.schema.json"
RESULT_SCHEMA = "config/schemas/stage17-phase-action-result-v2.schema.json"
COMPLETION_SCHEMA = "config/schemas/stage17-phase-action-completion-v2.schema.json"
ACTION_OUTPUT_SCHEMA = "config/schemas/stage17-action-output-v2.schema.json"
SCHEDULE_SCHEMA = "config/schemas/stage17-frozen-schedule-v2.schema.json"
RUNNER_ADMISSION_SCHEMA = "config/schemas/runner-admission-v3.schema.json"
SUPPORTED_ACTIONS = (
    "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT",
)


class OperationalSemanticError(ValueError):
    pass


@dataclass(frozen=True)
class Artifact:
    role: str
    path: pathlib.Path
    payload: bytes
    document: dict[str, Any] | None
    reference: dict[str, Any]


ROLE_SCHEMA: dict[str, str | None] = {
    "PREFLIGHT_STDOUT": None, "PREFLIGHT_STDERR": None,
    "RUNTIME_WORKER_BINARY": None, "TRUST_ALLOWED_SIGNERS": None,
    "QUALIFICATION_SOURCE": None,
    "AUTHORIZATION_SIGNATURE": None,
    "PILOT_SCHEDULE": SCHEDULE_SCHEMA,
    "RUNNER_ADMISSION": RUNNER_ADMISSION_SCHEMA,
    **{role: TYPED_SCHEMA for role in (
        "PREFLIGHT_ATTEMPT", "PREFLIGHT_OBSERVATION_RECEIPT",
        "PREFLIGHT_COMPLETION", "RUNTIME_IDENTITY", "TRUST_ANCHOR",
        "OWNER_ACCEPTANCE", "QUALIFICATION_NEAR_FAR", "QUALIFICATION_CLOCK",
        "QUALIFICATION_ATOMICS_LAYOUT", "QUALIFICATION_AFFINITY_MIGRATION",
        "QUALIFICATION_NUMA_PAGES", "QUALIFICATION_STORAGE_RECOVERY",
        "QUALIFICATION_HARDWARE_PREFETCH", "QUALIFICATION_STAND_PRESTATE",
        "QUALIFICATION_Q15_COLLECTOR", "CALIBRATION_FREEZE", "PILOT_PLAN",
        "STORAGE_BUDGET", "CUSTODY_DOMAIN", "COPY_LEDGER", "RECOVERY_TEST",
    )},
    **{role: AUTH_SCHEMA for role in (
        "PHASE_ACTION_AUTHORIZATION", "CALIBRATION_Q16A_AUTHORIZATION",
        "CALIBRATION_Q16B_AUTHORIZATION", "CALIBRATION_Q16C_AUTHORIZATION",
    "PILOT_AUTHORIZATION",
    )},
    "PHASE_ACTION_REQUEST": REQUEST_SCHEMA,
    "PILOT_REQUEST": REQUEST_SCHEMA,
    "PHASE_ACTION_ATTEMPT": ATTEMPT_SCHEMA,
    "PHASE_ACTION_RESULT": RESULT_SCHEMA,
    "PHASE_ACTION_COMPLETION": COMPLETION_SCHEMA,
    "CALIBRATION_Q16A_RESULT": RESULT_SCHEMA,
    "CALIBRATION_Q16A_REQUEST": REQUEST_SCHEMA,
    "CALIBRATION_Q16A_ATTEMPT": ATTEMPT_SCHEMA,
    "CALIBRATION_Q16A_COMPLETION": COMPLETION_SCHEMA,
    "CALIBRATION_Q16B_RESULT": RESULT_SCHEMA,
    "CALIBRATION_Q16B_REQUEST": REQUEST_SCHEMA,
    "CALIBRATION_Q16B_ATTEMPT": ATTEMPT_SCHEMA,
    "CALIBRATION_Q16B_COMPLETION": COMPLETION_SCHEMA,
    "CALIBRATION_Q16C_RESULT": RESULT_SCHEMA,
    "CALIBRATION_Q16C_REQUEST": REQUEST_SCHEMA,
    "CALIBRATION_Q16C_ATTEMPT": ATTEMPT_SCHEMA,
    "CALIBRATION_Q16C_COMPLETION": COMPLETION_SCHEMA,
}

EXPECTED_ROLES: dict[str, Counter[str]] = {
    "S17-EXT-002": Counter({
        "PREFLIGHT_ATTEMPT": 1, "PREFLIGHT_OBSERVATION_RECEIPT": 6,
        "PREFLIGHT_STDOUT": 6, "PREFLIGHT_STDERR": 6,
        "PREFLIGHT_COMPLETION": 1, "RUNTIME_IDENTITY": 1, "TRUST_ANCHOR": 1,
        "RUNTIME_WORKER_BINARY": 1, "TRUST_ALLOWED_SIGNERS": 1,
    }),
    "S17-EXT-003": Counter({"OWNER_ACCEPTANCE": 1}),
    "S17-EXT-004": Counter({
        "QUALIFICATION_SOURCE": 12,
        "QUALIFICATION_NEAR_FAR": 1, "QUALIFICATION_CLOCK": 1,
        "QUALIFICATION_ATOMICS_LAYOUT": 1, "QUALIFICATION_AFFINITY_MIGRATION": 1,
        "QUALIFICATION_NUMA_PAGES": 1, "QUALIFICATION_STORAGE_RECOVERY": 1,
        "QUALIFICATION_HARDWARE_PREFETCH": 1, "QUALIFICATION_STAND_PRESTATE": 1,
        "QUALIFICATION_Q15_COLLECTOR": 1,
    }),
    "S17-EXT-005": Counter({
        "PHASE_ACTION_AUTHORIZATION": 1, "AUTHORIZATION_SIGNATURE": 1,
        "PHASE_ACTION_REQUEST": 1, "PHASE_ACTION_ATTEMPT": 1,
        "PHASE_ACTION_RESULT": 1, "PHASE_ACTION_COMPLETION": 1,
    }),
    "S17-EXT-007": Counter({
        "CALIBRATION_Q16A_AUTHORIZATION": 1, "CALIBRATION_Q16A_REQUEST": 1, "CALIBRATION_Q16A_ATTEMPT": 1, "CALIBRATION_Q16A_RESULT": 1, "CALIBRATION_Q16A_COMPLETION": 1,
        "CALIBRATION_Q16B_AUTHORIZATION": 1, "CALIBRATION_Q16B_REQUEST": 1, "CALIBRATION_Q16B_ATTEMPT": 1, "CALIBRATION_Q16B_RESULT": 1, "CALIBRATION_Q16B_COMPLETION": 1,
        "CALIBRATION_Q16C_AUTHORIZATION": 1, "CALIBRATION_Q16C_REQUEST": 1, "CALIBRATION_Q16C_ATTEMPT": 1, "CALIBRATION_Q16C_RESULT": 1, "CALIBRATION_Q16C_COMPLETION": 1,
        "AUTHORIZATION_SIGNATURE": 3, "CALIBRATION_FREEZE": 1,
    }),
    "S17-EXT-008": Counter({"PILOT_PLAN": 1, "PILOT_SCHEDULE": 1,
                              "RUNNER_ADMISSION": 1}),
    "S17-EXT-009": Counter({
        "STORAGE_BUDGET": 1, "CUSTODY_DOMAIN": 2, "COPY_LEDGER": 1,
        "RECOVERY_TEST": 1,
    }),
    "S17-EXT-010": Counter({"PILOT_AUTHORIZATION": 1, "PILOT_REQUEST": 1,
                              "AUTHORIZATION_SIGNATURE": 1}),
}

MEASUREMENT_KEYS: dict[str, frozenset[str]] = {
    "PREFLIGHT_ATTEMPT": frozenset({"authorization_sha256", "observation_ids", "one_attempt", "retries"}),
    "PREFLIGHT_OBSERVATION_RECEIPT": frozenset({"ordinal", "observation_id", "stdout_sha256", "stderr_sha256", "runtime_sha256", "returncode"}),
    "PREFLIGHT_COMPLETION": frozenset({"attempt_sha256", "ordered_receipt_sha256s", "observation_ids", "leader_reaped", "process_group_gone"}),
    "RUNTIME_IDENTITY": frozenset({"worker_path", "worker_size_bytes", "worker_sha256", "worker_role", "runtime_profile", "supported_actions"}),
    "TRUST_ANCHOR": frozenset({"allowed_signers_path", "allowed_signers_size_bytes", "allowed_signers_sha256", "principal", "sshsig_namespace", "signer_role", "reviewer_role", "stand_anchor_sha256"}),
    "OWNER_ACCEPTANCE": frozenset({"ext002_resolution_id", "ext002_resolution_sha256", "runtime_record_sha256", "trust_record_sha256", "distinct_auditor", "independent_review", "role_collapse_accepted"}),
    "QUALIFICATION_NEAR_FAR": frozenset({"near_producer_cpu", "near_consumer_cpu", "far_producer_cpu", "far_consumer_cpu", "topology_sha256"}),
    "QUALIFICATION_CLOCK": frozenset({"clock_id", "per_core_samples", "cross_core_samples", "maximum_regressions", "qualification_sha256"}),
    "QUALIFICATION_ATOMICS_LAYOUT": frozenset({"pointer_width", "pointer_alignment", "termination_width", "cache_line_bytes", "layout_sha256"}),
    "QUALIFICATION_AFFINITY_MIGRATION": frozenset({"producer_cpu", "consumer_cpu", "sample_count", "migration_count", "readback_sha256"}),
    "QUALIFICATION_NUMA_PAGES": frozenset({"region_count", "page_count", "wrong_node_pages", "residency_sha256"}),
    "QUALIFICATION_STORAGE_RECOVERY": frozenset({"capacity_bytes", "recovery_test_id", "recovery_artifact_sha256"}),
    "QUALIFICATION_HARDWARE_PREFETCH": frozenset({"mapping_id", "prestate_sha256", "readback_sha256", "restoration_sha256"}),
    "QUALIFICATION_STAND_PRESTATE": frozenset({"stand_id", "inventory_sha256", "capture_id"}),
    "QUALIFICATION_Q15_COLLECTOR": frozenset({"collector_count", "collector_manifest_sha256", "qualification_archive_sha256"}),
    "CALIBRATION_FREEZE": frozenset({"q16a_result_sha256", "q16b_result_sha256", "q16c_result_sha256", "mu_ref", "distance_context_count", "zero_loss_bound"}),
    "PILOT_PLAN": frozenset({"run_ids", "schedule_sha256s", "seed_ids", "master_seed_hexes",
                              "horizons", "capacities", "offered_counts", "packages",
                              "d2_cache_lines", "cache_line_bytes", "base_page_bytes",
                              "runner_admission_sha256s", "treatment_blind_labels",
                              "runner_admission_artifact_ids",
                              "runner_evidence_set_sha256s",
                              "schedule_artifact_ids",
                              "stop_rules", "resource_limits", "artifact_names",
                              "predecessor_resolution_sha256s"}),
    "STORAGE_BUDGET": frozenset({"planned_bytes", "available_bytes", "temporary_copies", "durable_copies", "budget_formula_id"}),
    "CUSTODY_DOMAIN": frozenset({"domain_id", "locator", "owner_uid", "mode", "independent_domain_id"}),
    "COPY_LEDGER": frozenset({"source_locator", "source_sha256", "primary_copy_locator", "primary_copy_sha256", "secondary_copy_locator", "secondary_copy_sha256", "transfer_verified_at_utc"}),
    "RECOVERY_TEST": frozenset({"failure_fixture_locator", "failure_fixture_sha256", "restored_locator", "restored_sha256", "recovery_procedure_id", "result_code"}),
}


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    payload = path.read_bytes()
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise OperationalSemanticError(f"JSON root is not an object: {path}")
    return document, payload


def _schema(root: pathlib.Path, relative: str) -> tuple[dict[str, Any], bytes]:
    return load(root / relative)


def _validate(root: pathlib.Path, document: dict[str, Any], relative: str, label: str) -> None:
    schema, _ = _schema(root, relative)
    Draft202012Validator.check_schema(schema)
    registry = Registry()
    if relative == MANIFEST_SCHEMA:
        artifact, _ = _schema(root, ARTIFACT_SCHEMA)
        registry = registry.with_resource(
            "urn:cpu-prefetch:stage17:operational-input-manifest:stage17-operational-artifact-v2.schema.json",
            Resource.from_contents(artifact),
        ).with_resource(
            "stage17-operational-artifact-v2.schema.json", Resource.from_contents(artifact)
        )
    errors = sorted(Draft202012Validator(schema, registry=registry).iter_errors(document), key=lambda item: tuple(item.path))
    if errors:
        path = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise OperationalSemanticError(f"{label} schema error at {path}: {errors[0].message}")


def _artifact_path(manifest_path: pathlib.Path, locator: Any) -> pathlib.Path:
    if not isinstance(locator, str):
        raise OperationalSemanticError("artifact locator is absent")
    relative = pathlib.PurePosixPath(locator)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise OperationalSemanticError("artifact locator is not manifest-relative")
    current = manifest_path.parent
    for part in relative.parts:
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            raise OperationalSemanticError("artifact locator traverses a symlink")
    metadata = current.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise OperationalSemanticError("artifact is not a regular file")
    return current


def _read_artifacts(root: pathlib.Path, manifest_path: pathlib.Path, manifest: dict[str, Any]) -> list[Artifact]:
    result: list[Artifact] = []
    ids: set[str] = set()
    for reference in manifest["artifacts"]:
        role = reference["role"]
        if role not in ROLE_SCHEMA:
            raise OperationalSemanticError(f"unknown artifact role: {role}")
        if reference["artifact_id"] in ids:
            raise OperationalSemanticError("duplicate artifact ID")
        ids.add(reference["artifact_id"])
        path = _artifact_path(manifest_path, reference["locator"])
        payload = path.read_bytes()
        if (len(payload), sha(payload)) != (reference["size_bytes"], reference["sha256"]):
            raise OperationalSemanticError(f"artifact byte identity mismatch: {role}")
        expected_schema = ROLE_SCHEMA[role]
        document: dict[str, Any] | None = None
        if expected_schema is None:
            if reference["media_type"] != "application/octet-stream" or reference["schema_identity"] is not None or reference["schema_binding"] is not None:
                raise OperationalSemanticError(f"binary artifact schema contract drifted: {role}")
        else:
            if reference["media_type"] != "application/json":
                raise OperationalSemanticError(f"JSON artifact media type drifted: {role}")
            schema_document, schema_payload = _schema(root, expected_schema)
            expected_binding = {"path": expected_schema, "size_bytes": len(schema_payload), "sha256": sha(schema_payload)}
            if reference["schema_binding"] != expected_binding:
                raise OperationalSemanticError(f"artifact schema binding drifted: {role}")
            document = json.loads(payload)
            if not isinstance(document, dict):
                raise OperationalSemanticError(f"artifact JSON root is not an object: {role}")
            _validate(root, document, expected_schema, role)
            if reference["schema_identity"] != document.get("schema_version"):
                raise OperationalSemanticError(f"artifact schema identity drifted: {role}")
            if expected_schema == TYPED_SCHEMA:
                if document.get("record_role") != role:
                    raise OperationalSemanticError(f"typed record role mismatch: {role}")
                expected_keys = MEASUREMENT_KEYS[role]
                if frozenset(document["measurements"]) != expected_keys:
                    raise OperationalSemanticError(f"typed measurements are incomplete or expanded: {role}")
                values = tuple(document["measurements"].values())
                if values and all(isinstance(value, bool) for value in values):
                    raise OperationalSemanticError(f"boolean-only impostor rejected: {role}")
        result.append(Artifact(role, path, payload, document, reference))
    return result


def _verify_cross_artifact_lineage(
    artifacts: list[Artifact], admitted: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    index: dict[str, tuple[int, str]] = {
        item.reference["artifact_id"]: (len(item.payload), sha(item.payload))
        for item in artifacts
    }
    for resolution in admitted.values():
        index[resolution.resolution_id] = (
            pathlib.Path(resolution.path).stat().st_size, resolution.sha256
        )
        context = resolution.semantic_context
        if isinstance(context, dict):
            for artifact_id, binding in context.get("artifact_index", {}).items():
                index.setdefault(artifact_id, (binding["size_bytes"], binding["sha256"]))
    for artifact in artifacts:
        for lineage in artifact.reference["lineage"]:
            observed = index.get(lineage["id"])
            if observed is None or observed[1] != lineage["sha256"]:
                raise OperationalSemanticError(
                    f"artifact lineage is unknown or drifted: {artifact.role}"
                )
        if artifact.document is not None and artifact.document.get("schema_version") == "cpu-prefetch-stage17-operational-typed-record/2":
            for source in artifact.document["source_bindings"]:
                observed = index.get(source["id"])
                if observed != (source["size_bytes"], source["sha256"]):
                    raise OperationalSemanticError(
                        f"typed source binding is unknown or drifted: {artifact.role}"
                    )
    return {
        artifact_id: {"size_bytes": size, "sha256": digest}
        for artifact_id, (size, digest) in index.items()
        if artifact_id in {item.reference["artifact_id"] for item in artifacts}
    }


def _resolution_bindings(admitted: Mapping[str, Any], ids: tuple[str, ...]) -> list[dict[str, str]]:
    result = []
    for input_id in ids:
        item = admitted.get(input_id)
        if item is None:
            raise OperationalSemanticError(f"missing predecessor resolution: {input_id}")
        result.append({"input_id": input_id, "resolution_id": item.resolution_id, "sha256": item.sha256})
    return result


def _one(artifacts: list[Artifact], role: str) -> Artifact:
    matches = [item for item in artifacts if item.role == role]
    if len(matches) != 1:
        raise OperationalSemanticError(f"expected exactly one {role}")
    return matches[0]


def _verify_worker_binary_shape(worker: Artifact) -> None:
    metadata = worker.path.stat()
    required_tokens = (
        b"--execute-fixed-stage17-action-v2",
        b"STAGE17-FIXED-ACTION-WORKER-v2",
        *(item.encode("ascii") for item in SUPPORTED_ACTIONS),
    )
    if (worker.payload[:4] != b"\x7fELF" or metadata.st_uid != os.geteuid()
            or metadata.st_mode & 0o022 or not metadata.st_mode & 0o100
            or any(token not in worker.payload for token in required_tokens)):
        raise OperationalSemanticError(
            "runtime worker is not the owned, non-writable compiled fixed dispatcher"
        )


def _parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OperationalSemanticError("authorization timestamp is not UTC")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise OperationalSemanticError("authorization timestamp is malformed") from exception


def verify_sshsig(
    *, authorization: Artifact, signature: Artifact, trust: dict[str, Any],
) -> None:
    measurements = trust["measurements"]
    allowed = pathlib.Path(measurements["allowed_signers_path"])
    metadata = allowed.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise OperationalSemanticError("trust anchor locator is unsafe")
    payload = allowed.read_bytes()
    if (len(payload), sha(payload)) != (measurements["allowed_signers_size_bytes"], measurements["allowed_signers_sha256"]):
        raise OperationalSemanticError("trust anchor bytes drifted")
    completed = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(allowed), "-I",
         measurements["principal"], "-n", measurements["sshsig_namespace"],
         "-s", str(signature.path)], input=authorization.payload,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10,
    )
    if completed.returncode != 0:
        raise OperationalSemanticError("authorization SSHSIG verification failed")


def _verify_result_outputs(root: pathlib.Path, result_artifact: Artifact) -> None:
    assert result_artifact.document is not None
    result = result_artifact.document
    for binding in result["artifacts"]:
        path = _artifact_path(result_artifact.path, binding["file_name"])
        payload = path.read_bytes()
        if (len(payload), sha(payload)) != (binding["size_bytes"], binding["sha256"]):
            raise OperationalSemanticError("fixed worker output byte identity mismatch")
        if binding["media_type"] == "application/json":
            document = json.loads(payload)
            if not isinstance(document, dict) or document.get("schema_version") != binding["schema_identity"]:
                raise OperationalSemanticError("fixed worker output schema identity mismatch")
            _validate(root, document, ACTION_OUTPUT_SCHEMA, "fixed worker output")
        elif (binding["media_type"] != "application/octet-stream"
              or binding["schema_identity"] != "RAW-OBS-U64LE-LP-RUNID-v1"
              or binding["role"] not in {"PRODUCER_RAW_OBSERVATIONS", "CONSUMER_RAW_OBSERVATIONS"}):
            raise OperationalSemanticError("fixed worker binary output contract drifted")


def _phase_action_family(root: pathlib.Path, artifacts: list[Artifact], trust: dict[str, Any], expected_action: str | None = None, prefix: str = "PHASE_ACTION") -> dict[str, Any]:
    authorization = _one(artifacts, f"{prefix}_AUTHORIZATION")
    signature = _one(artifacts, "AUTHORIZATION_SIGNATURE")
    request = _one(artifacts, f"{prefix}_REQUEST")
    attempt = _one(artifacts, f"{prefix}_ATTEMPT")
    result = _one(artifacts, f"{prefix}_RESULT")
    completion = _one(artifacts, f"{prefix}_COMPLETION")
    assert all(item.document is not None for item in (authorization, request, attempt, result, completion))
    verify_sshsig(authorization=authorization, signature=signature, trust=trust)
    auth, req, att, res, comp = (item.document for item in (authorization, request, attempt, result, completion))
    if expected_action is not None and auth["action_id"] != expected_action:
        raise OperationalSemanticError("phase action identity mismatch")
    if not _parse_utc(auth["issued_at_utc"]) < _parse_utc(auth["expires_at_utc"]):
        raise OperationalSemanticError("phase authorization lifetime is invalid")
    auth_sha, request_sha = sha(authorization.payload), sha(request.payload)
    if auth["request_binding"] != {"path": str(request.path), "size_bytes": len(request.payload), "sha256": request_sha}:
        raise OperationalSemanticError("phase authorization request binding mismatch")
    if (req["authorization_id"], req["action_id"]) != (auth["authorization_id"], auth["action_id"]):
        raise OperationalSemanticError("phase request authorization lineage mismatch")
    if (att["authorization_sha256"], att["request_sha256"], att["action_id"]) != (auth_sha, request_sha, auth["action_id"]):
        raise OperationalSemanticError("phase attempt lineage mismatch")
    if (res["authorization_sha256"], res["request_sha256"], res["attempt_id"], res["action_id"]) != (auth_sha, request_sha, att["attempt_id"], auth["action_id"]):
        raise OperationalSemanticError("phase result lineage mismatch")
    if (comp["authorization_sha256"], comp["request_sha256"], comp["attempt_id"], comp["action_id"]) != (auth_sha, request_sha, att["attempt_id"], auth["action_id"]):
        raise OperationalSemanticError("phase completion lineage mismatch")
    if not comp["leader_reaped"] or not comp["process_group_gone"]:
        raise OperationalSemanticError("phase completion precedes process quiescence")
    if auth["action_id"] == "Q15-W" and (not res["restoration_verified"] or res["quarantined"] or not comp["restoration_verified"]):
        raise OperationalSemanticError("Q15-W completion lacks proven restoration")
    _verify_result_outputs(root, result)
    return {"authorization": auth, "authorization_path": authorization.path, "authorization_sha256": auth_sha, "request": req, "result": res, "completion": comp}


def verify_manifest_v2(
    *, repository_root: pathlib.Path, manifest_path: pathlib.Path,
    admitted_resolutions: Mapping[str, Any], expected_input_id: str,
    allow_synthetic: bool,
) -> dict[str, Any]:
    root = repository_root.resolve()
    manifest, payload = load(manifest_path)
    _validate(root, manifest, MANIFEST_SCHEMA, "operational manifest v2")
    if manifest["input_id"] != expected_input_id or expected_input_id not in EXPECTED_ROLES:
        raise OperationalSemanticError("operational manifest input identity mismatch")
    if manifest["synthetic_test_only"] != allow_synthetic:
        raise OperationalSemanticError("synthetic classification mismatch")
    artifacts = _read_artifacts(root, manifest_path, manifest)
    artifact_index = _verify_cross_artifact_lineage(artifacts, admitted_resolutions)
    if Counter(item.role for item in artifacts) != EXPECTED_ROLES[expected_input_id]:
        raise OperationalSemanticError(f"{expected_input_id} exact artifact family mismatch")
    expected_predecessors = tuple(f"S17-EXT-{index:03d}" for index in range(1, int(expected_input_id[-3:])))
    if manifest["predecessor_resolutions"] != _resolution_bindings(admitted_resolutions, expected_predecessors):
        raise OperationalSemanticError("manifest predecessor resolution lineage mismatch")
    context: dict[str, Any] = {"manifest_id": manifest["manifest_id"], "manifest_path": manifest_path, "manifest_sha256": sha(payload), "stand_id": manifest["stand_id"], "synthetic_test_only": allow_synthetic, "artifact_index": artifact_index}
    if expected_input_id == "S17-EXT-002":
        ext1 = admitted_resolutions.get("S17-EXT-001")
        if ext1 is None or not isinstance(ext1.semantic_context, dict):
            raise OperationalSemanticError("preflight evidence lacks admitted EXT001 authority")
        ext1_contract = ext1.semantic_context.get("contract")
        if not isinstance(ext1_contract, dict):
            raise OperationalSemanticError("preflight evidence lacks admitted EXT001 contract")
        ext1_target = ext1_contract.get("target")
        if not isinstance(ext1_target, dict):
            raise OperationalSemanticError("preflight evidence lacks admitted EXT001 target")
        attempt = _one(artifacts, "PREFLIGHT_ATTEMPT").document
        completion = _one(artifacts, "PREFLIGHT_COMPLETION").document
        runtime = _one(artifacts, "RUNTIME_IDENTITY").document
        trust = _one(artifacts, "TRUST_ANCHOR").document
        assert attempt and completion and runtime and trust
        receipts = [item.document for item in artifacts if item.role == "PREFLIGHT_OBSERVATION_RECEIPT"]
        receipts = sorted(receipts, key=lambda item: item["measurements"]["ordinal"] if item else -1)
        observation_ids = [item["measurements"]["observation_id"] for item in receipts if item]
        if observation_ids != attempt["measurements"]["observation_ids"] or observation_ids != completion["measurements"]["observation_ids"] or [item["measurements"]["ordinal"] for item in receipts if item] != list(range(1, 7)):
            raise OperationalSemanticError("preflight observation order/completeness mismatch")
        if any(item["measurements"]["returncode"] != 0 for item in receipts if item):
            raise OperationalSemanticError("preflight contains a failed observation")
        if (manifest["stand_id"] != ext1_target.get("stand_id")
                or attempt["measurements"]["authorization_sha256"]
                != ext1.semantic_context.get("authorization_sha256")
                or trust["measurements"]["stand_anchor_sha256"]
                != ext1_target.get("pinned_host_key_evidence", {}).get("sha256")):
            raise OperationalSemanticError(
                "preflight trust/target evidence is not bound to admitted EXT001"
            )
        context.update({"runtime": runtime, "trust": trust, "observation_ids": tuple(observation_ids)})
        worker = _one(artifacts, "RUNTIME_WORKER_BINARY")
        signers = _one(artifacts, "TRUST_ALLOWED_SIGNERS")
        _verify_worker_binary_shape(worker)
        if runtime["measurements"]["worker_size_bytes"] != len(worker.payload) or runtime["measurements"]["worker_sha256"] != sha(worker.payload) or pathlib.Path(runtime["measurements"]["worker_path"]) != worker.path:
            raise OperationalSemanticError("runtime identity does not bind the observed worker bytes")
        if trust["measurements"]["allowed_signers_size_bytes"] != len(signers.payload) or trust["measurements"]["allowed_signers_sha256"] != sha(signers.payload) or pathlib.Path(trust["measurements"]["allowed_signers_path"]) != signers.path:
            raise OperationalSemanticError("trust context does not bind observed allowed-signers bytes")
    elif expected_input_id == "S17-EXT-003":
        ext2 = admitted_resolutions["S17-EXT-002"]
        accepted = _one(artifacts, "OWNER_ACCEPTANCE").document
        assert accepted and ext2.semantic_context
        values = accepted["measurements"]
        if (values["ext002_resolution_id"], values["ext002_resolution_sha256"]) != (ext2.resolution_id, ext2.sha256) or values["distinct_auditor"] is not False or values["independent_review"] is not False or values["role_collapse_accepted"] is not True:
            raise OperationalSemanticError("owner acceptance/role-collapse contract mismatch")
        ext2_index = ext2.semantic_context["artifact_index"]
        if (values["runtime_record_sha256"] != ext2_index["EXT002-RUNTIME"]["sha256"]
                or values["trust_record_sha256"] != ext2_index["EXT002-TRUST"]["sha256"]):
            raise OperationalSemanticError("owner acceptance runtime/trust hash binding drifted")
        context.update({"runtime": ext2.semantic_context["runtime"], "trust": ext2.semantic_context["trust"], "owner_acceptance": accepted})
    elif expected_input_id == "S17-EXT-004":
        records = [item for item in artifacts if item.role != "QUALIFICATION_SOURCE"]
        sources = {item.reference["artifact_id"]: sha(item.payload)
                   for item in artifacts if item.role == "QUALIFICATION_SOURCE"}
        if any(item.document is None or item.document["outcome"] != "VERIFIED" for item in records):
            raise OperationalSemanticError("qualification family contains an unverified record")
        for item in records:
            assert item.document
            bound = {binding["id"]: binding["sha256"]
                     for binding in item.document["source_bindings"]
                     if binding["id"] in sources}
            measurement_hashes = {
                value for key, value in item.document["measurements"].items()
                if key.endswith("_sha256")
            }
            if not measurement_hashes or set(bound.values()) != measurement_hashes:
                raise OperationalSemanticError(
                    f"qualification record does not bind every raw source byte hash: {item.role}"
                )
        context["qualification_records"] = {item.role: item.document for item in records}
        context["qualification_source_sha256s"] = tuple(sorted(sources.values()))
    elif expected_input_id == "S17-EXT-005":
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        context.update(_phase_action_family(root, artifacts, trust, "Q15-W"))
    elif expected_input_id == "S17-EXT-007":
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        actions: dict[str, Any] = {}
        for token, action in (("Q16A", "Q16a"), ("Q16B", "Q16b"), ("Q16C", "Q16c")):
            prefix = f"CALIBRATION_{token}"
            auth_artifact, result_artifact = _one(artifacts, f"{prefix}_AUTHORIZATION"), _one(artifacts, f"{prefix}_RESULT")
            signatures = [item for item in artifacts if item.role == "AUTHORIZATION_SIGNATURE"]
            assert auth_artifact.document and result_artifact.document
            matching = [item for item in signatures if any(lineage["id"] == auth_artifact.reference["artifact_id"] for lineage in item.reference["lineage"])]
            if len(matching) != 1:
                raise OperationalSemanticError(f"{action} detached signature lineage mismatch")
            verify_sshsig(authorization=auth_artifact, signature=matching[0], trust=trust)
            family = _phase_action_family(root, [item for item in artifacts if item.role.startswith(prefix) or item is matching[0]], trust, action, prefix)
            actions[action] = {**family, "result_sha256": sha(result_artifact.payload)}
        freeze = _one(artifacts, "CALIBRATION_FREEZE").document
        assert freeze
        if freeze["measurements"]["q16a_result_sha256"] != actions["Q16a"]["result_sha256"] or freeze["measurements"]["q16b_result_sha256"] != actions["Q16b"]["result_sha256"] or freeze["measurements"]["q16c_result_sha256"] != actions["Q16c"]["result_sha256"]:
            raise OperationalSemanticError("calibration freeze result lineage mismatch")
        context.update({"actions": actions, "calibration_freeze": freeze})
    elif expected_input_id == "S17-EXT-008":
        plan = _one(artifacts, "PILOT_PLAN").document
        assert plan
        values = plan["measurements"]
        vector_names = ("run_ids", "schedule_sha256s", "seed_ids", "master_seed_hexes",
                        "horizons", "capacities", "offered_counts", "packages",
                        "d2_cache_lines", "runner_admission_sha256s",
                        "runner_admission_artifact_ids",
                        "runner_evidence_set_sha256s", "schedule_artifact_ids",
                        "treatment_blind_labels")
        if (not all(values[name] for name in (*vector_names, "stop_rules",
                                              "resource_limits", "artifact_names"))
                or len({len(values[name]) for name in vector_names}) != 1
                or values["cache_line_bytes"] < 1 or values["base_page_bytes"] < 1):
            raise OperationalSemanticError("pilot plan is not fully frozen")
        expected_hashes = [
            admitted_resolutions[f"S17-EXT-{index:03d}"].sha256
            for index in range(1, 8)
        ]
        if values["predecessor_resolution_sha256s"] != expected_hashes:
            raise OperationalSemanticError("pilot plan predecessor hash family drifted")
        schedule = _one(artifacts, "PILOT_SCHEDULE")
        admission = _one(artifacts, "RUNNER_ADMISSION")
        assert schedule.document and admission.document
        if (values["schedule_artifact_ids"] != [schedule.reference["artifact_id"]]
                or values["runner_admission_artifact_ids"] != [admission.reference["artifact_id"]]
                or values["schedule_sha256s"] != [sha(schedule.payload)]
                or values["runner_admission_sha256s"] != [sha(admission.payload)]
                or values["runner_evidence_set_sha256s"] !=
                   [sha(canonical(admission.document["evidence"]))]):
            raise OperationalSemanticError("pilot plan exact schedule/admission byte binding drifted")
        deadlines = schedule.document["deadline_ticks"]
        if (schedule.document["arrival_family"] != "OPEN_LOOP_FROZEN"
                or deadlines != sorted(deadlines)
                or len(deadlines) != values["offered_counts"][0]
                or deadlines[-1] >= schedule.document["horizon_ticks"]
                or schedule.document["horizon_ticks"] != values["horizons"][0]
                or admission.document["package"] != values["packages"][0]
                or admission.document["binary_sha256"] !=
                   admitted_resolutions["S17-EXT-006"].semantic_context["release_artifact_sha256"]):
            raise OperationalSemanticError("pilot schedule/admission semantics drifted")
        known_evidence = {
            artifact_id: binding["sha256"]
            for resolution in admitted_resolutions.values()
            for artifact_id, binding in
            (resolution.semantic_context or {}).get("artifact_index", {}).items()
        }
        known_evidence.update({resolution.resolution_id: resolution.sha256
                               for resolution in admitted_resolutions.values()})
        if any(known_evidence.get(item["artifact_id"]) != item["sha256"]
               for item in admission.document["evidence"]):
            raise OperationalSemanticError("runner admission uses evidence outside admitted contexts")
        context.update({"pilot_plan": plan, "pilot_schedule": schedule.document,
                        "runner_admission": admission.document})
    elif expected_input_id == "S17-EXT-009":
        domains = [_one([item], "CUSTODY_DOMAIN").document for item in artifacts if item.role == "CUSTODY_DOMAIN"]
        if len({item["measurements"]["domain_id"] for item in domains if item}) != 2:
            raise OperationalSemanticError("storage readiness lacks two custody domains")
        values = [item["measurements"] for item in domains if item]
        if ({item["independent_domain_id"] for item in values} !=
                {item["domain_id"] for item in values}
                or any(item["independent_domain_id"] == item["domain_id"]
                       for item in values)):
            raise OperationalSemanticError("custody domains are not reciprocal and independent")
        for item in values:
            path = pathlib.Path(item["locator"])
            metadata = path.lstat()
            if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode)
                    or metadata.st_uid != item["owner_uid"]
                    or f"{stat.S_IMODE(metadata.st_mode):04o}" != item["mode"]):
                raise OperationalSemanticError("custody locator ownership/permissions drifted")
        budget = _one(artifacts, "STORAGE_BUDGET").document
        ledger = _one(artifacts, "COPY_LEDGER").document
        recovery = _one(artifacts, "RECOVERY_TEST").document
        assert budget and ledger and recovery
        if (budget["measurements"]["planned_bytes"] >
                budget["measurements"]["available_bytes"]
                or budget["measurements"]["durable_copies"] < 2):
            raise OperationalSemanticError("storage budget cannot retain two durable copies")
        ledger_values = ledger["measurements"]
        ledger_payloads = []
        for locator, digest_name in (
            ("source_locator", "source_sha256"),
            ("primary_copy_locator", "primary_copy_sha256"),
            ("secondary_copy_locator", "secondary_copy_sha256"),
        ):
            artifact = pathlib.Path(ledger_values[locator])
            metadata = artifact.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise OperationalSemanticError("copy ledger locator is unsafe")
            payload = artifact.read_bytes()
            if sha(payload) != ledger_values[digest_name]:
                raise OperationalSemanticError("copy ledger byte hash drifted")
            ledger_payloads.append(payload)
        if not ledger_payloads[0] == ledger_payloads[1] == ledger_payloads[2]:
            raise OperationalSemanticError("custody copies are not byte-identical")
        recovery_values = recovery["measurements"]
        for locator, digest_name in (
            ("failure_fixture_locator", "failure_fixture_sha256"),
            ("restored_locator", "restored_sha256"),
        ):
            artifact = pathlib.Path(recovery_values[locator])
            metadata = artifact.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise OperationalSemanticError("recovery locator is unsafe")
            if sha(artifact.read_bytes()) != recovery_values[digest_name]:
                raise OperationalSemanticError("recovery artifact byte hash drifted")
        if recovery_values["result_code"] != "PASS":
            raise OperationalSemanticError("storage recovery test did not pass")
        context["storage_records"] = {item.reference["artifact_id"]: item.document for item in artifacts}
    elif expected_input_id == "S17-EXT-010":
        authorization = _one(artifacts, "PILOT_AUTHORIZATION")
        request = _one(artifacts, "PILOT_REQUEST")
        signature = _one(artifacts, "AUTHORIZATION_SIGNATURE")
        trust = admitted_resolutions["S17-EXT-003"].semantic_context["trust"]
        assert authorization.document
        verify_sshsig(authorization=authorization, signature=signature, trust=trust)
        expected = _resolution_bindings(admitted_resolutions, tuple(f"S17-EXT-{index:03d}" for index in range(1, 10)))
        if authorization.document["action_id"] != "STAGE17-BLINDED-PILOT" or authorization.document["predecessor_resolutions"] != expected:
            raise OperationalSemanticError("pilot authorization predecessor/run scope drifted")
        assert request.document
        expected_request_binding = {"path": str(request.path),
                                    "size_bytes": len(request.payload),
                                    "sha256": sha(request.payload)}
        if authorization.document["request_binding"] != expected_request_binding:
            raise OperationalSemanticError("pilot authorization does not bind admitted request bytes")
        if (request.document["authorization_id"] != authorization.document["authorization_id"]
                or request.document["action_id"] != "STAGE17-BLINDED-PILOT"
                or request.document["predecessor_resolutions"] != expected):
            raise OperationalSemanticError("pilot request lineage/scope drifted")
        release = admitted_resolutions["S17-EXT-006"].semantic_context
        expected_runtime = {
            "role": release["release_artifact_role"],
            "profile": release["runtime_profile"],
            "size_bytes": release["release_artifact_size_bytes"],
            "sha256": release["release_artifact_sha256"],
        }
        expected_release = {
            "source_resolution_id": admitted_resolutions["S17-EXT-006"].resolution_id,
            "source_resolution_sha256": admitted_resolutions["S17-EXT-006"].sha256,
            "artifact_role": release["release_artifact_role"],
            "runtime_profile": release["runtime_profile"],
            "worker_size_bytes": release["release_artifact_size_bytes"],
            "worker_sha256": release["release_artifact_sha256"],
        }
        plan = admitted_resolutions["S17-EXT-008"].semantic_context["pilot_plan"]
        plan_values = plan["measurements"]
        if allow_synthetic:
            expected_inputs = {"fixture_nonce": "pilot-future-execution"}
        else:
            if len(plan_values["run_ids"]) != 1:
                raise OperationalSemanticError("production pilot request requires one fixed admitted run")
            expected_inputs = {
                "run_id": plan_values["run_ids"][0],
                "schedule_sha256": plan_values["schedule_sha256s"][0],
                "seed_id": plan_values["seed_ids"][0],
                "seed_hex": plan_values["master_seed_hexes"][0],
                "capacity": plan_values["capacities"][0],
                "offered_count": plan_values["offered_counts"][0],
                "package": plan_values["packages"][0],
                "d2_cache_lines": plan_values["d2_cache_lines"][0],
                "cache_line_bytes": plan_values["cache_line_bytes"],
                "base_page_bytes": plan_values["base_page_bytes"],
                "runner_admission_sha256": plan_values["runner_admission_sha256s"][0],
                "runner_admission": admitted_resolutions["S17-EXT-008"].semantic_context["runner_admission"],
                "runner_evidence_set_sha256": plan_values["runner_evidence_set_sha256s"][0],
                "schedule_deadline_ticks": admitted_resolutions["S17-EXT-008"].semantic_context["pilot_schedule"]["deadline_ticks"],
                "schedule_origin_ticks": admitted_resolutions["S17-EXT-008"].semantic_context["pilot_schedule"]["origin_ticks"],
                "schedule_horizon_ticks": admitted_resolutions["S17-EXT-008"].semantic_context["pilot_schedule"]["horizon_ticks"],
                "duration_ticks": admitted_resolutions["S17-EXT-008"].semantic_context["pilot_schedule"]["horizon_ticks"],
                "plan_sha256": admitted_resolutions["S17-EXT-008"].semantic_context["artifact_index"]["EXT008-PLAN"]["sha256"],
            }
        if (request.document["runtime_binding"] != expected_runtime
                or request.document["release_binding"] != expected_release
                or request.document["action_inputs"] != expected_inputs):
            raise OperationalSemanticError("pilot request runtime/release/frozen-plan binding drifted")
        context.update({"authorization": authorization.document,
                        "authorization_path": authorization.path,
                        "authorization_sha256": sha(authorization.payload),
                        "request": request.document,
                        "request_path": request.path,
                        "request_sha256": sha(request.payload)})
    return context
