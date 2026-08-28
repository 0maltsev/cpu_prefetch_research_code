#!/usr/bin/env python3
"""Derived Stage 17 completion and independently rooted Phase 18 admission."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import stage17_operational_semantics_v3 as semantics
import stage17_output_registry_v3 as output_registry


PHASE18_STATES = (
    "PLANNED", "COLLECTED_SEALED", "TRAINING_OPEN", "SELECTION_FROZEN",
    "VALIDATION_UNSEALED", "H3_EVALUATED", "H1H2_RELEASED", "ARCHIVED",
)


class ExitError(ValueError):
    pass


@dataclass(frozen=True)
class Stage17CompletionContext:
    document: dict[str, Any]
    payload: bytes
    sealed_manifest: dict[str, Any]


@dataclass(frozen=True)
class Phase18TrustContext:
    enrollment: dict[str, Any]
    enrollment_payload: bytes
    allowed_signers_path: pathlib.Path
    allowed_signers_payload: bytes


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: pathlib.Path, maximum: int = 64 * 1024 * 1024) \
        -> tuple[dict[str, Any], bytes]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > maximum:
            raise ExitError(f"unsafe/unbounded record: {path}")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise ExitError(f"record changed while read: {path}")
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise ExitError(f"record root is not an object: {path}")
    return document, payload


def _schema(root: pathlib.Path, relative: str, document: dict[str, Any]) -> None:
    schema, _ = _load(root / relative)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(
        schema, format_checker=FormatChecker()
    ).iter_errors(document))
    if errors:
        raise ExitError(f"{relative}: {errors[0].message}")


def _binding(path: pathlib.Path) -> dict[str, Any]:
    metadata = path.stat()
    payload = path.read_bytes()
    return {"path": str(path), "size_bytes": metadata.st_size,
            "sha256": sha(payload)}


def validate_stage17_completion(
    *, repository_root: pathlib.Path, operational_validation: Any,
    pilot_output_root: pathlib.Path, synthetic_test_only: bool,
) -> Stage17CompletionContext:
    if (operational_validation.current_state
            != "READY_FOR_STAGE17_PHASE_AUTHORIZATION"
            or operational_validation.resolution_count != 10
            or operational_validation.transition_count != 3):
        raise ExitError("Stage 17 completion requires exact 10/3 operational state")
    ext8 = operational_validation.resolutions["S17-EXT-008"]
    ext10 = operational_validation.resolutions["S17-EXT-010"]
    if not isinstance(ext10.semantic_context, dict):
        raise ExitError("admitted EXT010 context is absent")
    context = ext10.semantic_context
    authorization = context["authorization"]
    request = context["request"]
    authorization_payload = canonical(authorization)
    request_payload = canonical(request)
    if (sha(authorization_payload) != context["authorization_sha256"]
            or sha(request_payload) != context["request_sha256"]):
        raise ExitError("EXT010 canonical authorization/request binding drifted")
    root = pilot_output_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ExitError("pilot output root is not a nonsymlink directory")
    token = "stage17_blinded_pilot"
    attempt_path = root / f"stage17-{token}-attempt-v3.json"
    result_path = root / output_registry.RESULT_NAME
    completion_path = root / f"stage17-{token}-completion-v3.json"
    attempt, attempt_payload = _load(attempt_path)
    result, result_payload = _load(result_path)
    completion, completion_payload = _load(completion_path)
    registry = output_registry.pin_registry(repository_root.resolve())
    output_registry.validate_document(
        registry, attempt,
        "config/schemas/stage17-phase-action-attempt-v3.schema.json", "pilot attempt",
    )
    output_registry.validate_document(
        registry, completion,
        "config/schemas/stage17-phase-action-completion-v3.schema.json",
        "pilot completion",
    )
    directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                           os.O_CLOEXEC)
    try:
        output_registry.validate_worker_result(
            registry=registry, directory_fd=directory_fd, result=result,
            request=request, authorization_sha256=sha(authorization_payload),
            synthetic_test_only=synthetic_test_only,
        )
    finally:
        os.close(directory_fd)
    expected_result = {
        "file_name": result_path.name, "size_bytes": len(result_payload),
        "sha256": sha(result_payload),
    }
    artifact_bindings = [{
        "file_name": item["file_name"], "size_bytes": item["size_bytes"],
        "sha256": item["sha256"],
    } for item in result["artifacts"]]
    if (attempt["authorization_sha256"] != sha(authorization_payload)
            or attempt["request_sha256"] != sha(request_payload)
            or attempt["attempt_id"] != request["attempt_id"]
            or completion["result"] != expected_result
            or completion["artifact_bindings"] != artifact_bindings
            or completion["attempt_id"] != attempt["attempt_id"]
            or completion["authorization_sha256"] != sha(authorization_payload)
            or completion["request_sha256"] != sha(request_payload)
            or not completion["leader_reaped"]
            or not completion["process_group_gone"]
            or not completion["restoration_verified"]
            or completion["quarantined"]):
        raise ExitError("pilot attempt/result/completion lineage is incomplete")
    sealed_binding = [item for item in result["artifacts"]
                      if item["role"] == "SEALED_PILOT_ARTIFACT_MANIFEST"]
    if len(sealed_binding) != 1:
        raise ExitError("pilot sealed manifest is absent or duplicated")
    sealed_path = root / sealed_binding[0]["file_name"]
    sealed, sealed_payload = _load(sealed_path)
    if (len(sealed_payload), sha(sealed_payload)) != (
            sealed_binding[0]["size_bytes"], sealed_binding[0]["sha256"]):
        raise ExitError("sealed pilot manifest byte identity drifted")
    plan = ext8.semantic_context["pilot_plan"]
    expected_runs = 180 * plan["repetitions_per_cell"]
    expected_artifacts = expected_runs * 10 + 1
    if (sealed["run_count"] != expected_runs
            or sealed["artifact_count"] != expected_artifacts
            or sealed["plan_sha256"] != ext8.semantic_context["pilot_plan_sha256"]
            or not sealed["treatment_blind"]
            or sealed["confirmatory_outcomes_accessed"]):
        raise ExitError("sealed pilot manifest is not the complete frozen run set")
    document = {
        "schema_version": "cpu-prefetch-stage17-completion/3",
        "completion_id": request["attempt_id"] + ":stage17-completion",
        "operational_journal_sha256": operational_validation.latest_journal_sha256,
        "ext010_resolution": {"resolution_id": ext10.resolution_id,
                              "sha256": ext10.sha256},
        "pilot_authorization_sha256": sha(authorization_payload),
        "pilot_request_sha256": sha(request_payload),
        "pilot_attempt_sha256": sha(attempt_payload),
        "pilot_result_sha256": sha(result_payload),
        "pilot_controller_completion_sha256": sha(completion_payload),
        "sealed_pilot_manifest_sha256": sha(sealed_payload),
        "frozen_plan_sha256": ext8.semantic_context["pilot_plan_sha256"],
        "run_count": expected_runs, "artifact_count": len(result["artifacts"]),
        "treatment_blind": True, "confirmatory_outcomes_accessed": False,
        "stage17_complete": True, "synthetic_test_only": synthetic_test_only,
        "phase18_authority": False,
    }
    _schema(repository_root, "config/schemas/stage17-completion-v3.schema.json",
            document)
    return Stage17CompletionContext(document, canonical(document), sealed)


def admit_phase18_trust(
    *, repository_root: pathlib.Path, operational_validation: Any,
    completion: Stage17CompletionContext, enrollment_path: pathlib.Path,
    enrollment_signature_path: pathlib.Path,
) -> Phase18TrustContext:
    enrollment, payload = _load(enrollment_path)
    _schema(repository_root, "config/schemas/phase18-trust-enrollment-v3.schema.json",
            enrollment)
    ext3 = operational_validation.resolutions["S17-EXT-003"].semantic_context
    stage17_trust = ext3["trust"]
    expected_stage17 = {
        "ext002_resolution_id": operational_validation.resolutions[
            "S17-EXT-002"
        ].resolution_id,
        "ext002_resolution_sha256": operational_validation.resolutions[
            "S17-EXT-002"
        ].sha256,
        "ext003_resolution_id": operational_validation.resolutions[
            "S17-EXT-003"
        ].resolution_id,
        "ext003_resolution_sha256": operational_validation.resolutions[
            "S17-EXT-003"
        ].sha256,
        "trust_record_sha256": ext3["trust"]["measurements"][
            "allowed_signers_sha256"
        ],
    }
    if (enrollment["stage17_completion_sha256"] != sha(completion.payload)
            or enrollment["stage17_trust_context"] != expected_stage17):
        raise ExitError("Phase 18 trust enrollment lacks admitted Stage 17 lineage")
    signature_payload = enrollment_signature_path.read_bytes()
    authorization_artifact = semantics.Artifact(
        "PHASE18_TRUST_ENROLLMENT", enrollment_path, payload,
        len(payload), sha(payload), enrollment, {},
    )
    signature_artifact = semantics.Artifact(
        "PHASE18_TRUST_ENROLLMENT_SIGNATURE", enrollment_signature_path,
        signature_payload, len(signature_payload), sha(signature_payload),
        None, {},
    )
    semantics.verify_sshsig(
        authorization=authorization_artifact, signature=signature_artifact,
        trust_record=stage17_trust,
    )
    locator = pathlib.Path(enrollment["independent_allowed_signers"]["path"])
    metadata = locator.lstat()
    allowed = locator.read_bytes()
    binding = enrollment["independent_allowed_signers"]
    if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o022
            or (len(allowed), sha(allowed)) != (
                binding["size_bytes"], binding["sha256"])
            or sha(allowed) == stage17_trust["measurements"][
                "allowed_signers_sha256"]):
        raise ExitError("Phase 18 trust anchor is unsafe, drifted, or not independent")
    return Phase18TrustContext(enrollment, payload, locator, allowed)


def phase18_readiness(
    *, repository_root: pathlib.Path, completion: Stage17CompletionContext,
    trust: Phase18TrustContext,
) -> dict[str, Any]:
    document = {
        "schema_version": "cpu-prefetch-phase18-readiness/3",
        "readiness_id": completion.document["completion_id"] + ":phase18-readiness",
        "stage17_completion_sha256": sha(completion.payload),
        "trust_enrollment_sha256": sha(trust.enrollment_payload),
        "state": "READY_FOR_SEPARATE_PHASE18_AUTHORIZATION",
        "authorization_issued": False, "phase18_authority": False,
    }
    _schema(repository_root, "config/schemas/phase18-readiness-v3.schema.json",
            document)
    return document


def validate_phase18_authorization(
    *, repository_root: pathlib.Path, completion: Stage17CompletionContext,
    trust: Phase18TrustContext, readiness: dict[str, Any],
    authorization_path: pathlib.Path, signature_path: pathlib.Path,
    actual_utc: str,
) -> dict[str, Any]:
    authorization, payload = _load(authorization_path)
    _schema(repository_root, "config/schemas/phase18-authorization-v3.schema.json",
            authorization)
    if (authorization["trust_enrollment_sha256"] != sha(trust.enrollment_payload)
            or authorization["stage17_completion_sha256"] != sha(completion.payload)
            or authorization["readiness_sha256"] != sha(canonical(readiness))
            or authorization["actor"] != trust.enrollment["principal"]
            or authorization["reviewer"] != trust.enrollment["reviewer_role"]
            or tuple(authorization["allowed_chronology"]) != PHASE18_STATES):
        raise ExitError("Phase 18 authority lineage/trust/chronology drifted")
    issued = dt.datetime.fromisoformat(authorization["issued_at_utc"].replace("Z", "+00:00"))
    expires = dt.datetime.fromisoformat(authorization["expires_at_utc"].replace("Z", "+00:00"))
    actual = dt.datetime.fromisoformat(actual_utc.replace("Z", "+00:00"))
    if not issued <= actual < expires or expires - issued > dt.timedelta(minutes=30):
        raise ExitError("Phase 18 authorization is future, expired, or overlong")
    trust_record = {
        "measurements": {
            "allowed_signers_path": str(trust.allowed_signers_path),
            "allowed_signers_size_bytes": len(trust.allowed_signers_payload),
            "allowed_signers_sha256": sha(trust.allowed_signers_payload),
            "principal": trust.enrollment["principal"],
            "sshsig_namespace": trust.enrollment["namespace"],
        }
    }
    signature_payload = signature_path.read_bytes()
    semantics.verify_sshsig(
        authorization=semantics.Artifact(
            "PHASE18_AUTHORIZATION", authorization_path, payload,
            len(payload), sha(payload), authorization, {},
        ),
        signature=semantics.Artifact(
            "PHASE18_SIGNATURE", signature_path, signature_payload,
            len(signature_payload), sha(signature_payload), None, {},
        ),
        trust_record=trust_record,
    )
    return authorization


def validate_phase18_chronology(
    *, authorization: dict[str, Any], transitions: list[dict[str, Any]],
) -> str:
    current = PHASE18_STATES[0]
    previous = "0" * 64
    for sequence, transition in enumerate(transitions, 1):
        expected_to = PHASE18_STATES[sequence]
        if (transition != {
            "sequence_number": sequence, "from_state": current,
            "to_state": expected_to, "previous_transition_sha256": previous,
            "authorization_id": authorization["authorization_id"],
            "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY",
            "stage17_authority_used": False,
        }):
            raise ExitError("Phase 18 chronology is reordered, forked, or expanded")
        previous = sha(canonical(transition)); current = expected_to
    return current
