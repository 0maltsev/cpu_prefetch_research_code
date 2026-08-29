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

import stage17_operational_semantics_v4 as semantics
import stage17_output_registry_v4 as output_registry


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
    anchor: dict[str, Any]
    anchor_payload: bytes
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
    attempt_path = root / f"stage17-{token}-attempt-v4.json"
    result_path = root / output_registry.RESULT_NAME
    completion_path = root / f"stage17-{token}-completion-v4.json"
    attempt, attempt_payload = _load(attempt_path)
    result, result_payload = _load(result_path)
    completion, completion_payload = _load(completion_path)
    registry = output_registry.pin_registry(repository_root.resolve())
    output_registry.validate_document(
        registry, attempt,
        "config/schemas/stage17-phase-action-attempt-v4.schema.json", "pilot attempt",
    )
    output_registry.validate_document(
        registry, completion,
        "config/schemas/stage17-phase-action-completion-v4.schema.json",
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
    session_binding = [item for item in result["artifacts"]
                       if item["role"] == "STAGE17_PILOT_SESSION_COMPLETION"]
    if len(session_binding) != 1:
        raise ExitError("pilot session completion is absent or duplicated")
    session_path = root / session_binding[0]["file_name"]
    session, session_payload = _load(session_path)
    _schema(repository_root,
            "config/schemas/stage17-pilot-session-completion-v1.schema.json",
            session)
    if (len(session_payload), sha(session_payload)) != (
            session_binding[0]["size_bytes"], session_binding[0]["sha256"]):
        raise ExitError("pilot session completion byte identity drifted")
    plan = ext8.semantic_context["pilot_plan"]
    expected_runs = 180 * plan["repetitions_per_cell"]
    expected_artifacts = expected_runs * 12 + 1
    if (sealed["run_count"] != expected_runs
            or sealed["artifact_count"] != expected_artifacts
            or sealed["plan_sha256"] != ext8.semantic_context["pilot_plan_sha256"]
            or not sealed["treatment_blind"]
            or sealed["confirmatory_outcomes_accessed"]
            or session["run_count"] != expected_runs
            or session["plan_sha256"] != ext8.semantic_context["pilot_plan_sha256"]
            or session["authorization_sha256"] != sha(authorization_payload)
            or session["request_sha256"] != sha(request_payload)
            or session["sealed_manifest"]["sha256"] != sha(sealed_payload)
            or not session["all_runs_complete"]
            or not session["restoration_verified"] or session["quarantined"]
            or session["run_attempt_sha256s"] != sealed["run_attempt_sha256s"]
            or session["run_completion_sha256s"]
            != sealed["run_completion_sha256s"]):
        raise ExitError("sealed pilot manifest is not the complete frozen run set")
    document = {
        "schema_version": "cpu-prefetch-stage17-completion/4",
        "completion_id": request["attempt_id"] + ":stage17-completion",
        "operational_journal_sha256": operational_validation.latest_journal_sha256,
        "ext010_resolution": {"resolution_id": ext10.resolution_id,
                              "sha256": ext10.sha256},
        "pilot_authorization_sha256": sha(authorization_payload),
        "pilot_request_sha256": sha(request_payload),
        "pilot_attempt_sha256": sha(attempt_payload),
        "pilot_result_sha256": sha(result_payload),
        "pilot_controller_completion_sha256": sha(completion_payload),
        "pilot_session_completion_sha256": sha(session_payload),
        "sealed_pilot_manifest_sha256": sha(sealed_payload),
        "frozen_plan_sha256": ext8.semantic_context["pilot_plan_sha256"],
        "run_count": expected_runs,
        "run_attempt_sha256s": session["run_attempt_sha256s"],
        "run_completion_sha256s": session["run_completion_sha256s"],
        "artifact_count": len(result["artifacts"]),
        "treatment_blind": True, "confirmatory_outcomes_accessed": False,
        "controller_authenticated": True, "stage17_complete": True,
        "synthetic_test_only": synthetic_test_only,
        "phase18_authority": False,
    }
    _schema(repository_root, "config/schemas/stage17-completion-v4.schema.json",
            document)
    return Stage17CompletionContext(document, canonical(document), sealed)


def admit_phase18_trust(
    *, repository_root: pathlib.Path, operational_validation: Any,
    anchor_path: pathlib.Path, expected_anchor_id: str,
    expected_anchor_sha256: str, expected_public_key_fingerprint: str,
) -> Phase18TrustContext:
    """Admit an owner-supplied trust root only against prior external facts.

    No Stage 17 key or readiness record can enroll this root.  The caller must
    supply an already-approved anchor ID, exact record hash, and actual public
    key fingerprint from an independent custody process.
    """
    anchor, payload = _load(anchor_path)
    _schema(repository_root,
            "config/schemas/phase18-external-trust-anchor-v4.schema.json",
            anchor)
    if (anchor["anchor_id"] != expected_anchor_id
            or sha(payload) != expected_anchor_sha256
            or anchor["public_key_fingerprint_sha256"]
            != expected_public_key_fingerprint):
        raise ExitError("Phase 18 trust differs from pre-admitted external facts")
    ext3 = operational_validation.resolutions["S17-EXT-003"].semantic_context
    stage17_trust = ext3["trust"]
    locator = pathlib.Path(anchor["allowed_signers"]["path"])
    metadata = locator.lstat()
    allowed = locator.read_bytes()
    binding = anchor["allowed_signers"]
    if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_mode & 0o022
            or (len(allowed), sha(allowed)) != (
                binding["size_bytes"], binding["sha256"])
            or sha(allowed) == stage17_trust["measurements"][
                "allowed_signers_sha256"]):
        raise ExitError("Phase 18 trust anchor is unsafe, drifted, or not independent")
    lines = [line for line in allowed.decode("utf-8").splitlines() if line.strip()]
    if len(lines) != 1:
        raise ExitError("Phase 18 allowed-signers must contain one exact principal")
    fields = lines[0].split()
    if (len(fields) < 3 or fields[0] != anchor["principal"]
            or fields[1] != "ssh-ed25519"):
        raise ExitError("Phase 18 allowed-signers principal/key type drifted")
    import base64
    try:
        wire = base64.b64decode(fields[2], validate=True)
    except ValueError as exception:
        raise ExitError("Phase 18 public key base64 is malformed") from exception
    import subprocess
    completed = subprocess.run(
        ["/usr/bin/ssh-keygen", "-lf", "-", "-E", "sha256"],
        input=(fields[1] + " " + fields[2] + "\n").encode("ascii"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=10,
    )
    output = completed.stdout.decode("utf-8", errors="strict").split()
    if (completed.returncode != 0 or len(output) < 2
            or output[1] != expected_public_key_fingerprint or len(wire) < 32):
        raise ExitError("Phase 18 actual public-key fingerprint drifted")
    return Phase18TrustContext(anchor, payload, locator, allowed)


def phase18_readiness(
    *, repository_root: pathlib.Path, completion: Stage17CompletionContext,
    trust: Phase18TrustContext | None, created_at_utc: str,
) -> dict[str, Any]:
    document = {
        "schema_version": "cpu-prefetch-phase18-readiness/4",
        "readiness_id": completion.document["completion_id"] + ":phase18-readiness",
        "stage17_completion_sha256": sha(completion.payload),
        "external_trust_anchor": None if trust is None else {
            "anchor_id": trust.anchor["anchor_id"],
            "sha256": sha(trust.anchor_payload),
            "public_key_fingerprint_sha256": trust.anchor[
                "public_key_fingerprint_sha256"
            ],
        },
        "state": ("BLOCKED_EXTERNAL_PHASE18_TRUST_REQUIRED" if trust is None
                  else "READY_FOR_SEPARATE_PHASE18_AUTHORIZATION"),
        "authorization_issued": False, "created_at_utc": created_at_utc,
        "phase18_authority": False,
    }
    _schema(repository_root, "config/schemas/phase18-readiness-v4.schema.json",
            document)
    return document


def validate_phase18_authorization(
    *, repository_root: pathlib.Path, completion: Stage17CompletionContext,
    trust: Phase18TrustContext, readiness: dict[str, Any],
    authorization_path: pathlib.Path, signature_path: pathlib.Path,
    actual_utc: str,
) -> dict[str, Any]:
    authorization, payload = _load(authorization_path)
    _schema(repository_root, "config/schemas/phase18-authorization-v4.schema.json",
            authorization)
    if (authorization["external_trust_anchor_sha256"] != sha(trust.anchor_payload)
            or authorization["public_key_fingerprint_sha256"]
            != trust.anchor["public_key_fingerprint_sha256"]
            or authorization["stage17_completion_sha256"] != sha(completion.payload)
            or authorization["readiness_sha256"] != sha(canonical(readiness))
            or authorization["actor"] != trust.anchor["principal"]
            or authorization["reviewer"] != trust.anchor["reviewer_role"]
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
            "principal": trust.anchor["principal"],
            "sshsig_namespace": trust.anchor["namespace"],
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
    *, repository_root: pathlib.Path, trust: Phase18TrustContext,
    authorization: dict[str, Any], authorization_payload: bytes,
    transitions: list[tuple[pathlib.Path, pathlib.Path]], actual_utc: str,
) -> str:
    current = PHASE18_STATES[0]
    previous = "0" * 64
    if len(transitions) > len(PHASE18_STATES) - 1:
        raise ExitError("Phase 18 chronology contains extra transitions")
    actual = dt.datetime.fromisoformat(actual_utc.replace("Z", "+00:00"))
    issued = dt.datetime.fromisoformat(
        authorization["issued_at_utc"].replace("Z", "+00:00")
    )
    expires = dt.datetime.fromisoformat(
        authorization["expires_at_utc"].replace("Z", "+00:00")
    )
    if not issued <= actual < expires:
        raise ExitError("Phase 18 transition authority is not currently valid")
    for sequence, (transition_path, signature_path) in enumerate(transitions, 1):
        transition, payload = _load(transition_path)
        _schema(repository_root,
                "config/schemas/phase18-access-transition-v4.schema.json",
                transition)
        expected_to = PHASE18_STATES[sequence]
        if (transition["sequence_number"] != sequence
                or transition["from_state"] != current
                or transition["to_state"] != expected_to
                or transition["previous_transition_sha256"] != previous
                or transition["authorization_id"] != authorization["authorization_id"]
                or transition["authorization_sha256"] != sha(authorization_payload)
                or transition["actor"] != trust.anchor["principal"]
                or transition["reviewer"] != trust.anchor["reviewer_role"]):
            raise ExitError("Phase 18 chronology is reordered, forked, or expanded")
        signature_payload = signature_path.read_bytes()
        semantics.verify_sshsig(
            authorization=semantics.Artifact(
                "PHASE18_TRANSITION", transition_path, payload, len(payload),
                sha(payload), transition, {},
            ),
            signature=semantics.Artifact(
                "PHASE18_TRANSITION_SIGNATURE", signature_path,
                signature_payload, len(signature_payload),
                sha(signature_payload), None, {},
            ),
            trust_record={"measurements": {
                "allowed_signers_path": str(trust.allowed_signers_path),
                "allowed_signers_size_bytes": len(trust.allowed_signers_payload),
                "allowed_signers_sha256": sha(trust.allowed_signers_payload),
                "principal": trust.anchor["principal"],
                "sshsig_namespace": trust.anchor["namespace"],
            }},
        )
        previous = sha(payload); current = expected_to
    return current
