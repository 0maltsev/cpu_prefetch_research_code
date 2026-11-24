#!/usr/bin/env python3
"""Fail-closed semantic admission for Stage 17 external inputs 002--010.

This module admits evidence, not execution.  It always reopens each declared
artifact, rejects symlinks/non-regular files, verifies byte count and SHA-256,
and then applies an input-specific closed-world contract.  Synthetic evidence
uses the same verifier and must be explicitly enabled by the test caller.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from jsonschema import Draft202012Validator


MANIFEST_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-input-manifest-v1.schema.json"
)
ACTION_AUTHORIZATION_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-phase-action-authorization-v1.schema.json"
)
ACTION_RESULT_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-phase-action-result-v1.schema.json"
)
ACTION_REQUEST_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-fixed-action-request-v1.schema.json"
)
FIXED_ACTIONS_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-fixed-phase-actions-v1.json"
)
OBSERVATION_IDS = (
    "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
    "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
    "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
    "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
    "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
    "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
)
QUALIFICATION_CLASSES = (
    "NEAR_MEMORY_PAIR", "FAR_MEMORY_PAIR", "CLOCK_SUITABILITY",
    "ATOMICS_AND_LAYOUT", "AFFINITY_AND_MIGRATION", "NUMA_AND_PAGE_PLACEMENT",
    "STORAGE_AND_RECOVERY", "HARDWARE_PREFETCH", "STAND_PRESTATE",
    "Q15_COLLECTOR",
)
CALIBRATION_PHASES = ("Q16a", "Q16b", "Q16c")


class OperationalSemanticError(ValueError):
    pass


@dataclass(frozen=True)
class Artifact:
    role: str
    artifact_id: str
    path: pathlib.Path
    size_bytes: int
    sha256: str
    media_type: str
    schema_identity: str | None
    document: dict[str, Any] | None


def canonical_json_bytes(document: Any) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OperationalSemanticError(f"{label} is not exact UTC")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exception:
        raise OperationalSemanticError(f"{label} is not second-precision UTC") from exception
    return parsed.replace(tzinfo=dt.timezone.utc)


def _schema_validate(document: Any, schema_path: pathlib.Path, label: str) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exception:
        raise OperationalSemanticError(f"cannot load {label} schema") from exception
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: tuple(item.path))
    if errors:
        path = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise OperationalSemanticError(f"{label} schema violation at {path}: {errors[0].message}")


def _exact_keys(document: Mapping[str, Any], expected: Iterable[str], label: str) -> None:
    actual, wanted = set(document), set(expected)
    if actual != wanted:
        raise OperationalSemanticError(
            f"{label} keys mismatch missing={sorted(wanted-actual)} extra={sorted(actual-wanted)}"
        )


def _read_bound_artifact(binding: Mapping[str, Any], *, label: str) -> Artifact:
    locator = binding.get("locator")
    if not isinstance(locator, str) or not locator:
        raise OperationalSemanticError(f"{label} locator is absent")
    path = pathlib.Path(locator)
    try:
        metadata = path.lstat()
    except OSError as exception:
        raise OperationalSemanticError(f"{label} cannot be opened: {exception}") from exception
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise OperationalSemanticError(f"{label} is not a nonsymlink regular file")
    try:
        payload = path.read_bytes()
    except OSError as exception:
        raise OperationalSemanticError(f"{label} cannot be read: {exception}") from exception
    if len(payload) != binding.get("size_bytes"):
        raise OperationalSemanticError(f"{label} byte count mismatch")
    digest = sha256_bytes(payload)
    if digest != binding.get("sha256"):
        raise OperationalSemanticError(f"{label} SHA-256 mismatch")
    document: dict[str, Any] | None = None
    if binding.get("media_type") == "application/json":
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exception:
            raise OperationalSemanticError(f"{label} JSON is malformed") from exception
        if not isinstance(decoded, dict):
            raise OperationalSemanticError(f"{label} JSON is not an object")
        document = decoded
    return Artifact(
        role=str(binding["role"]), artifact_id=str(binding["artifact_id"]),
        path=path, size_bytes=len(payload), sha256=digest,
        media_type=str(binding["media_type"]),
        schema_identity=binding.get("schema_identity"), document=document,
    )


def load_manifest(path: pathlib.Path, *, repository_root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Artifact]]:
    artifact = _read_bound_artifact({
        "role": "MANIFEST", "artifact_id": path.name, "locator": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_bytes(path.read_bytes()), "media_type": "application/json",
        "schema_identity": "cpu-prefetch-stage17-operational-input-manifest/1",
    }, label="operational input manifest")
    assert artifact.document is not None
    manifest = artifact.document
    _schema_validate(manifest, repository_root / MANIFEST_SCHEMA, "operational input manifest")
    by_role: dict[str, Artifact] = {}
    artifact_ids: set[str] = set()
    for binding in manifest["artifacts"]:
        role, artifact_id = binding["role"], binding["artifact_id"]
        if role in by_role or artifact_id in artifact_ids:
            raise OperationalSemanticError("duplicate artifact role or ID")
        artifact_ids.add(artifact_id)
        by_role[role] = _read_bound_artifact(binding, label=f"artifact {role}")
    return manifest, by_role


def _document(artifacts: Mapping[str, Artifact], role: str) -> dict[str, Any]:
    artifact = artifacts.get(role)
    if artifact is None or artifact.document is None:
        raise OperationalSemanticError(f"required JSON artifact is absent: {role}")
    return artifact.document


def _roles(artifacts: Mapping[str, Artifact], expected: Iterable[str]) -> None:
    wanted = set(expected)
    if set(artifacts) != wanted:
        raise OperationalSemanticError(
            f"artifact role set mismatch missing={sorted(wanted-set(artifacts))} extra={sorted(set(artifacts)-wanted)}"
        )


def _predecessors(
    manifest: Mapping[str, Any], admitted: Mapping[str, Any], expected_ids: Iterable[str]
) -> None:
    expected = tuple(expected_ids)
    bindings = manifest.get("predecessor_resolutions")
    if not isinstance(bindings, list) or tuple(item.get("input_id") for item in bindings) != expected:
        raise OperationalSemanticError("predecessor resolution order/set mismatch")
    for binding in bindings:
        item = admitted.get(binding["input_id"])
        if item is None:
            raise OperationalSemanticError(f"unadmitted predecessor {binding['input_id']}")
        if (binding.get("resolution_id"), binding.get("sha256")) != (item.resolution_id, item.sha256):
            raise OperationalSemanticError(f"predecessor binding drifted: {binding['input_id']}")


def _signature_verify(
    *, authorization: Artifact, signature: Artifact, allowed_signers: Artifact,
    principal: Any, namespace: Any,
) -> None:
    if not isinstance(principal, str) or not principal or not isinstance(namespace, str) or not namespace:
        raise OperationalSemanticError("SSHSIG principal/namespace is invalid")
    command = [
        "/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(allowed_signers.path),
        "-I", principal, "-n", namespace, "-s", str(signature.path),
    ]
    try:
        result = subprocess.run(
            command, input=authorization.path.read_bytes(), stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exception:
        raise OperationalSemanticError(f"SSHSIG verifier unavailable: {exception}") from exception
    if result.returncode != 0:
        raise OperationalSemanticError("SSHSIG verification failed")


def _verify_ext002(payload: Mapping[str, Any], artifacts: Mapping[str, Artifact]) -> None:
    _exact_keys(payload, (
        "successful", "observation_ids", "attempt_role", "receipt_roles",
        "stdout_roles", "stderr_roles", "completion_role", "failure_roles",
        "retention_roles", "runtime_identities_verified", "inventory_input_sha256",
        "qualification_input_sha256",
    ), "S17-EXT-002 payload")
    if payload["successful"] is not True or tuple(payload["observation_ids"]) != OBSERVATION_IDS:
        raise OperationalSemanticError("preflight was not a complete ordered success")
    receipt_roles = tuple(f"OBSERVATION_{index:02d}_RECEIPT" for index in range(1, 7))
    stdout_roles = tuple(f"OBSERVATION_{index:02d}_STDOUT" for index in range(1, 7))
    stderr_roles = tuple(f"OBSERVATION_{index:02d}_STDERR" for index in range(1, 7))
    if tuple(payload["receipt_roles"]) != receipt_roles or tuple(payload["stdout_roles"]) != stdout_roles or tuple(payload["stderr_roles"]) != stderr_roles:
        raise OperationalSemanticError("preflight artifact ordering drifted")
    if payload["failure_roles"] != [] or payload["retention_roles"] != [] or payload["runtime_identities_verified"] is not True:
        raise OperationalSemanticError("failed/partial/unverified preflight cannot be admitted")
    _roles(artifacts, ("ATTEMPT", "COMPLETION", *receipt_roles, *stdout_roles, *stderr_roles))
    attempt, completion = _document(artifacts, "ATTEMPT"), _document(artifacts, "COMPLETION")
    attempt_id = attempt.get("attempt_id")
    if not attempt_id or completion.get("attempt_id") != attempt_id:
        raise OperationalSemanticError("preflight attempt/completion lineage mismatch")
    if completion.get("completed_observation_ids") != list(OBSERVATION_IDS):
        raise OperationalSemanticError("completion observation order mismatch")
    receipt_hashes: list[str] = []
    for ordinal, (receipt_role, stdout_role, stderr_role, observation_id) in enumerate(zip(receipt_roles, stdout_roles, stderr_roles, OBSERVATION_IDS), start=1):
        receipt = _document(artifacts, receipt_role)
        if (receipt.get("attempt_id"), receipt.get("ordinal"), receipt.get("observation_id")) != (attempt_id, ordinal, observation_id):
            raise OperationalSemanticError("observation receipt lineage/order mismatch")
        if receipt.get("returncode") != 0 or receipt.get("failure") is not None or receipt.get("retry") != 0:
            raise OperationalSemanticError("observation receipt is not successful and nonretrying")
        if receipt.get("leader_reaped") is not True or receipt.get("process_group_gone") is not True:
            raise OperationalSemanticError("observation cleanup proof is absent")
        if (receipt.get("stdout_size_bytes"), receipt.get("stdout_sha256")) != (artifacts[stdout_role].size_bytes, artifacts[stdout_role].sha256):
            raise OperationalSemanticError("stdout binding mismatch")
        if (receipt.get("stderr_size_bytes"), receipt.get("stderr_sha256")) != (artifacts[stderr_role].size_bytes, artifacts[stderr_role].sha256):
            raise OperationalSemanticError("stderr binding mismatch")
        receipt_hashes.append(artifacts[receipt_role].sha256)
    if completion.get("receipt_sha256s") != receipt_hashes:
        raise OperationalSemanticError("completion receipt-hash order mismatch")
    if completion.get("all_leaders_reaped") is not True or completion.get("all_process_groups_gone") is not True or completion.get("retries") != 0:
        raise OperationalSemanticError("completion lifecycle proof is incomplete")


def _verify_ext003(payload: Mapping[str, Any], artifacts: Mapping[str, Artifact], admitted: Mapping[str, Any]) -> None:
    _exact_keys(payload, (
        "accepted_manifest_sha256", "all_hashes_recomputed", "six_observations_complete",
        "owner_acceptance", "owner_id", "distinct_auditor", "independent_review",
        "role_collapse", "trust_anchor_role", "authority_expansion",
    ), "S17-EXT-003 payload")
    _roles(artifacts, ("TRUST_ANCHOR",))
    ext002 = admitted["S17-EXT-002"].semantic_context
    if not isinstance(ext002, dict) or payload["accepted_manifest_sha256"] != ext002.get("manifest_sha256"):
        raise OperationalSemanticError("owner acceptance does not bind admitted preflight")
    if not all(payload[name] is True for name in ("all_hashes_recomputed", "six_observations_complete", "owner_acceptance")):
        raise OperationalSemanticError("owner acceptance checks are incomplete")
    if payload["distinct_auditor"] is not False or payload["independent_review"] is not False:
        raise OperationalSemanticError("pilot role-collapse declaration is inconsistent")
    if payload["role_collapse"] != ["OWNER", "OPERATOR", "CUSTODIAN", "AUDITOR"] or payload["authority_expansion"] is not False:
        raise OperationalSemanticError("role collapse or authority boundary drifted")
    trust = _document(artifacts, "TRUST_ANCHOR")
    _exact_keys(trust, ("schema_version", "principal", "namespace", "allowed_signers_sha256", "stage18_authority"), "trust anchor")
    if trust["schema_version"] != "cpu-prefetch-stage17-trust-anchor/1" or trust["stage18_authority"] is not False:
        raise OperationalSemanticError("trust anchor version/authority mismatch")


def _verify_ext004(payload: Mapping[str, Any], artifacts: Mapping[str, Artifact]) -> None:
    _exact_keys(payload, (
        "stand_id", "qualification_classes", "requested_verified_separate",
        "all_eligible", "development_host_evidence", "q15_collector_role",
    ), "S17-EXT-004 payload")
    if tuple(payload["qualification_classes"]) != QUALIFICATION_CLASSES:
        raise OperationalSemanticError("qualification class set/order mismatch")
    if payload["requested_verified_separate"] is not True or payload["all_eligible"] is not True or payload["development_host_evidence"] is not False:
        raise OperationalSemanticError("qualification eligibility/readback boundary failed")
    roles = tuple(f"QUALIFICATION_{name}" for name in QUALIFICATION_CLASSES)
    _roles(artifacts, roles)
    if payload["q15_collector_role"] != "QUALIFICATION_Q15_COLLECTOR":
        raise OperationalSemanticError("Q15 collector role mismatch")
    for role in roles:
        evidence = _document(artifacts, role)
        if evidence.get("stand_id") != payload["stand_id"] or evidence.get("eligible") is not True:
            raise OperationalSemanticError(f"qualification failed or target drifted: {role}")
        if evidence.get("requested_state") == evidence.get("verified_state") or "requested_state" not in evidence or "verified_state" not in evidence:
            # Equality of values is allowed; equality of the two fields is not
            # itself a problem.  They must, however, be distinct named fields.
            if "requested_state" not in evidence or "verified_state" not in evidence:
                raise OperationalSemanticError(f"requested/verified state missing: {role}")


def _authorization_and_signature(
    payload: Mapping[str, Any], artifacts: Mapping[str, Artifact], *, action: str,
    prefix: str = "",
) -> dict[str, Any]:
    key = lambda name: f"{prefix}{name}" if prefix else name
    authorization = artifacts[payload[key("authorization_role")]]
    signature = artifacts[payload[key("signature_role")]]
    allowed = artifacts[payload[key("allowed_signers_role")]]
    if authorization.document is None:
        raise OperationalSemanticError("authorization artifact is not JSON")
    _schema_validate(authorization.document, pathlib.Path(__file__).resolve().parents[1] / ACTION_AUTHORIZATION_SCHEMA, "phase authorization")
    if authorization.document.get("action_id") != action:
        raise OperationalSemanticError("phase authorization action mismatch")
    if authorization.document.get("allowed_signers_binding") != {
        "path": str(allowed.path), "size_bytes": allowed.size_bytes,
        "sha256": allowed.sha256,
    }:
        raise OperationalSemanticError("phase authorization allowed-signers binding mismatch")
    if (authorization.document.get("principal"), authorization.document.get("sshsig_namespace")) != (payload[key("principal")], payload[key("namespace")]):
        raise OperationalSemanticError("phase authorization SSHSIG profile mismatch")
    issued = _utc(authorization.document.get("issued_at_utc"), "authorization issue")
    expires = _utc(authorization.document.get("expires_at_utc"), "authorization expiry")
    if not issued < expires or (expires - issued).total_seconds() > 1800:
        raise OperationalSemanticError("authorization lifetime is invalid")
    _signature_verify(
        authorization=authorization, signature=signature, allowed_signers=allowed,
        principal=payload[key("principal")], namespace=payload[key("namespace")],
    )
    return authorization.document


def _verify_fixed_request(
    *, authorization: Mapping[str, Any], request_artifact: Artifact,
    action: str, synthetic_test_only: bool,
) -> dict[str, Any]:
    request = _document({"ACTION_REQUEST": request_artifact}, "ACTION_REQUEST")
    root = pathlib.Path(__file__).resolve().parents[1]
    _schema_validate(request, root / ACTION_REQUEST_SCHEMA, "fixed action request")
    expected_binding = {
        "path": str(request_artifact.path),
        "size_bytes": request_artifact.size_bytes,
        "sha256": request_artifact.sha256,
    }
    if authorization.get("request_binding") != expected_binding:
        raise OperationalSemanticError("authorization does not bind the exact action request")
    if (
        request.get("action_id") != action
        or request.get("stand_id") != authorization.get("target", {}).get("stand_id")
        or request.get("expected_prestate_sha256")
        != authorization.get("expected_prestate_sha256")
        or request.get("synthetic_test_only") is not synthetic_test_only
        or any(request.get(name) is not None for name in
               ("command_override", "argv_override", "stdin_override"))
    ):
        raise OperationalSemanticError("fixed request target, prestate, or override boundary drifted")
    fixed_actions = root / FIXED_ACTIONS_PATH
    if authorization.get("fixed_action_definition_sha256") != sha256_bytes(fixed_actions.read_bytes()):
        raise OperationalSemanticError("authorization fixed-action definition binding drifted")
    return request


def _verify_action_time(
    *, authorization: Mapping[str, Any], started: Any, completed: Any,
    label: str,
) -> None:
    issued = _utc(authorization.get("issued_at_utc"), f"{label} authorization issue")
    expires = _utc(authorization.get("expires_at_utc"), f"{label} authorization expiry")
    actual_started = _utc(started, f"{label} actual start")
    actual_completed = _utc(completed, f"{label} actual completion")
    if not issued <= actual_started < expires or actual_completed < actual_started:
        raise OperationalSemanticError(f"{label} action was not started under live authority")


def _verify_ext005(
    payload: Mapping[str, Any], artifacts: Mapping[str, Artifact],
    admitted: Mapping[str, Any], *, synthetic_test_only: bool,
) -> dict[str, Any]:
    _exact_keys(payload, (
        "request_role", "authorization_role", "signature_role", "allowed_signers_role",
        "result_role", "before_role", "after_role", "readback_role", "probe_role",
        "principal", "namespace", "admitted_after_state", "one_attempt", "retry_allowed",
        "restoration_verified", "quarantine", "action_request_precedes_resolution",
    ), "S17-EXT-005 payload")
    _roles(artifacts, (
        "ACTION_REQUEST", "AUTHORIZATION", "SIGNATURE", "ALLOWED_SIGNERS", "ACTION_RESULT",
        "BEFORE_STATE", "AFTER_STATE", "READBACK", "PROBES",
    ))
    if payload["admitted_after_state"] != "PREFLIGHT_ACCEPTED" or payload["one_attempt"] is not True or payload["retry_allowed"] is not False or payload["action_request_precedes_resolution"] is not True:
        raise OperationalSemanticError("S17-EXT-005 action graph/one-shot boundary failed")
    authorization = _authorization_and_signature(payload, artifacts, action="Q15-W")
    expected_predecessors = [
        {"input_id": item, "resolution_id": admitted[item].resolution_id,
         "sha256": admitted[item].sha256}
        for item in (f"S17-EXT-{index:03d}" for index in range(1, 5))
    ]
    if authorization.get("predecessor_resolutions") != expected_predecessors:
        raise OperationalSemanticError("S17-EXT-005 authorization predecessor drifted")
    request = _verify_fixed_request(
        authorization=authorization, request_artifact=artifacts["ACTION_REQUEST"],
        action="Q15-W", synthetic_test_only=synthetic_test_only,
    )
    result = _document(artifacts, "ACTION_RESULT")
    _schema_validate(result, pathlib.Path(__file__).resolve().parents[1] / ACTION_RESULT_SCHEMA, "phase result")
    if (
        result.get("authorization_id") != authorization.get("authorization_id")
    ):
        raise OperationalSemanticError("S17-EXT-005 request/result authorization lineage mismatch")
    if result.get("authorization_sha256") != artifacts["AUTHORIZATION"].sha256:
        raise OperationalSemanticError("S17-EXT-005 result authorization hash mismatch")
    expected_hashes = {
        "before_sha256": artifacts["BEFORE_STATE"].sha256,
        "after_sha256": artifacts["AFTER_STATE"].sha256,
        "readback_sha256": artifacts["READBACK"].sha256,
        "probe_sha256": artifacts["PROBES"].sha256,
    }
    if any(result.get(name) != value for name, value in expected_hashes.items()):
        raise OperationalSemanticError("S17-EXT-005 before/after/readback/probe binding mismatch")
    if payload["restoration_verified"] is not True or result.get("restoration") != "VERIFIED" or payload["quarantine"] is not False or result.get("quarantine") is not False:
        raise OperationalSemanticError("restoration failed; stand must remain quarantined")
    _verify_action_time(
        authorization=authorization, started=result.get("actual_started_at_utc"),
        completed=result.get("actual_completed_at_utc"), label="S17-EXT-005",
    )
    return authorization


def _verify_ext007(
    payload: Mapping[str, Any], artifacts: Mapping[str, Artifact],
    admitted: Mapping[str, Any], *, synthetic_test_only: bool,
) -> None:
    _exact_keys(payload, ("phases", "calibration_freeze_role", "treatment_blind", "confirmatory_outcomes_accessed"), "S17-EXT-007 payload")
    if tuple(item.get("phase") for item in payload["phases"]) != CALIBRATION_PHASES:
        raise OperationalSemanticError("calibration phase order/set mismatch")
    roles = {"CALIBRATION_FREEZE"}
    for phase in CALIBRATION_PHASES:
        roles.update({f"{phase.upper()}_PLAN", f"{phase.upper()}_AUTHORIZATION", f"{phase.upper()}_SIGNATURE", f"{phase.upper()}_ALLOWED_SIGNERS", f"{phase.upper()}_RAW", f"{phase.upper()}_RESULT"})
    _roles(artifacts, roles)
    if payload["treatment_blind"] is not True or payload["confirmatory_outcomes_accessed"] is not False or payload["calibration_freeze_role"] != "CALIBRATION_FREEZE":
        raise OperationalSemanticError("calibration blinding/freeze boundary failed")
    run_ids: list[str] = []
    for phase_record in payload["phases"]:
        phase = phase_record["phase"]
        expected = {
            "phase", "plan_role", "authorization_role", "signature_role",
            "allowed_signers_role", "raw_role", "result_role", "principal",
            "namespace", "run_id",
        }
        _exact_keys(phase_record, expected, f"{phase} calibration entry")
        if phase_record["run_id"] in run_ids:
            raise OperationalSemanticError("calibration run ID reused")
        run_ids.append(phase_record["run_id"])
        authorization = _authorization_and_signature(phase_record, artifacts, action=phase)
        expected_predecessors = [
            {"input_id": item, "resolution_id": admitted[item].resolution_id,
             "sha256": admitted[item].sha256}
            for item in (f"S17-EXT-{index:03d}" for index in range(1, 7))
        ]
        if authorization.get("predecessor_resolutions") != expected_predecessors:
            raise OperationalSemanticError(f"{phase} authorization predecessor drifted")
        _verify_fixed_request(
            authorization=authorization,
            request_artifact=artifacts[phase_record["plan_role"]], action=phase,
            synthetic_test_only=synthetic_test_only,
        )
        result = _document(artifacts, phase_record["result_role"])
        if result.get("phase") != phase or result.get("run_id") != phase_record["run_id"] or result.get("authorization_sha256") != artifacts[phase_record["authorization_role"]].sha256 or result.get("valid") is not True:
            raise OperationalSemanticError(f"{phase} result lineage/validity failed")
        if authorization.get("action_id") != phase:
            raise OperationalSemanticError(f"{phase} authorization mismatch")
        _verify_action_time(
            authorization=authorization, started=result.get("actual_started_at_utc"),
            completed=result.get("actual_completed_at_utc"), label=phase,
        )
    freeze = _document(artifacts, "CALIBRATION_FREEZE")
    if freeze.get("state") != "FROZEN" or freeze.get("unresolved_inputs") != [] or freeze.get("source_run_ids") != run_ids:
        raise OperationalSemanticError("calibration freeze is incomplete or source lineage drifted")


def _verify_ext008(payload: Mapping[str, Any], artifacts: Mapping[str, Artifact], admitted: Mapping[str, Any]) -> None:
    _exact_keys(payload, (
        "frozen", "run_ids", "schedule_roles", "seed_roles", "horizons_ticks",
        "capacities", "treatment_blind_labels", "stop_rules", "resource_limits",
        "artifact_names", "expected_artifact_hashes", "confirmatory_namespace",
        "outcome_dependent", "predecessor_manifest_hashes",
    ), "S17-EXT-008 payload")
    if payload["frozen"] is not True or not payload["run_ids"] or len(payload["run_ids"]) != len(set(payload["run_ids"])):
        raise OperationalSemanticError("pilot run set is empty, duplicate, or unfrozen")
    if payload["confirmatory_namespace"] is not False or payload["outcome_dependent"] is not False:
        raise OperationalSemanticError("pilot plan enters confirmatory/outcome-dependent scope")
    if any(not isinstance(value, int) or value <= 0 for value in payload["horizons_ticks"].values()) or any(not isinstance(value, int) or value <= 0 for value in payload["capacities"].values()):
        raise OperationalSemanticError("pilot horizons/capacities are not positive frozen integers")
    if not all(payload[name] for name in ("treatment_blind_labels", "stop_rules", "resource_limits", "artifact_names")):
        raise OperationalSemanticError("pilot plan is incomplete")
    expected_roles = set(payload["schedule_roles"]) | set(payload["seed_roles"])
    _roles(artifacts, expected_roles)
    expected_hashes = {item: admitted[item].semantic_context["manifest_sha256"] for item in tuple(f"S17-EXT-{index:03d}" for index in range(1, 8))}
    if payload["predecessor_manifest_hashes"] != expected_hashes:
        raise OperationalSemanticError("pilot plan predecessor manifest hashes drifted")
    for role, digest in payload["expected_artifact_hashes"].items():
        if role not in artifacts or artifacts[role].sha256 != digest:
            raise OperationalSemanticError("pilot planned artifact hash mismatch")


def _verify_ext009(payload: Mapping[str, Any], artifacts: Mapping[str, Artifact]) -> None:
    _exact_keys(payload, (
        "budget_role", "custody_domains", "copy_ledger_role", "transfer_role",
        "recovery_test_role", "archive_naming", "ownership_verified",
        "permissions_verified", "pilot_artifact_ids", "recovery_procedure_role",
    ), "S17-EXT-009 payload")
    _roles(artifacts, ("STORAGE_BUDGET", "COPY_LEDGER", "TRANSFER_VERIFICATION", "RECOVERY_TEST", "RECOVERY_PROCEDURE"))
    if payload["budget_role"] != "STORAGE_BUDGET" or len(payload["custody_domains"]) != 2 or len(set(payload["custody_domains"])) != 2:
        raise OperationalSemanticError("two independent custody domains are not proven")
    if payload["ownership_verified"] is not True or payload["permissions_verified"] is not True or not payload["pilot_artifact_ids"]:
        raise OperationalSemanticError("storage ownership/permissions/pilot binding incomplete")
    budget = _document(artifacts, "STORAGE_BUDGET")
    if budget.get("checked") is not True or budget.get("required_bytes", 0) <= 0 or budget.get("available_bytes", 0) < budget.get("required_bytes", 0):
        raise OperationalSemanticError("storage budget is insufficient")
    ledger = _document(artifacts, "COPY_LEDGER")
    if sorted(ledger.get("custody_domains", [])) != sorted(payload["custody_domains"]) or ledger.get("all_hashes_verified") is not True:
        raise OperationalSemanticError("copy ledger/custody mismatch")
    if _document(artifacts, "TRANSFER_VERIFICATION").get("verified") is not True or _document(artifacts, "RECOVERY_TEST").get("passed") is not True:
        raise OperationalSemanticError("transfer or recovery test failed")
    if not isinstance(payload["archive_naming"], str) or "{run_id}" not in payload["archive_naming"]:
        raise OperationalSemanticError("archive naming does not bind run ID")


def _verify_ext010(
    payload: Mapping[str, Any], artifacts: Mapping[str, Artifact],
    admitted: Mapping[str, Any], *, synthetic_test_only: bool,
) -> dict[str, Any]:
    _exact_keys(payload, (
        "request_role", "authorization_role", "signature_role", "allowed_signers_role", "principal",
        "namespace", "pilot_plan_sha256", "run_ids", "exact_predecessors",
        "graph_state", "command_expansion", "argv_expansion", "stdin_expansion",
        "run_set_expansion", "target_expansion", "phase18_authority",
    ), "S17-EXT-010 payload")
    _roles(artifacts, ("ACTION_REQUEST", "AUTHORIZATION", "SIGNATURE", "ALLOWED_SIGNERS"))
    authorization = _authorization_and_signature(payload, artifacts, action="STAGE17-BLINDED-PILOT")
    request = _verify_fixed_request(
        authorization=authorization, request_artifact=artifacts["ACTION_REQUEST"],
        action="STAGE17-BLINDED-PILOT", synthetic_test_only=synthetic_test_only,
    )
    expected = [
        {"input_id": item, "resolution_id": admitted[item].resolution_id, "sha256": admitted[item].sha256}
        for item in (f"S17-EXT-{index:03d}" for index in range(1, 10))
    ]
    if payload["exact_predecessors"] != expected or authorization.get("predecessor_resolutions") != expected:
        raise OperationalSemanticError("pilot authorization does not bind every admitted predecessor")
    plan = admitted["S17-EXT-008"].semantic_context
    if payload["pilot_plan_sha256"] != plan.get("manifest_sha256") or payload["run_ids"] != plan.get("run_ids"):
        raise OperationalSemanticError("pilot authorization run set/plan binding mismatch")
    if request.get("parameters", {}).get("pilot_plan_sha256") != payload["pilot_plan_sha256"] or request.get("parameters", {}).get("run_ids") != payload["run_ids"]:
        raise OperationalSemanticError("pilot fixed request does not bind the frozen plan/run set")
    if authorization.get("permission_matrix") != {"read_only_observation": False, "privileged_controls": False, "calibration": False, "pilot_execution": True, "measurement": True, "phase18": False}:
        raise OperationalSemanticError("pilot authorization permission matrix drifted")
    if payload["graph_state"] != "READY_FOR_STAGE17_PHASE_AUTHORIZATION" or any(payload[name] is not False for name in ("command_expansion", "argv_expansion", "stdin_expansion", "run_set_expansion", "target_expansion", "phase18_authority")):
        raise OperationalSemanticError("pilot authorization expands authority")
    return authorization


def verify_manifest(
    *, manifest_path: pathlib.Path, repository_root: pathlib.Path,
    admitted_resolutions: Mapping[str, Any], expected_input_id: str,
    allow_synthetic: bool = False,
) -> dict[str, Any]:
    manifest, artifacts = load_manifest(manifest_path, repository_root=repository_root)
    if manifest.get("input_id") != expected_input_id:
        raise OperationalSemanticError("manifest input ID mismatch")
    if manifest.get("synthetic_test_only") and not allow_synthetic:
        raise OperationalSemanticError("synthetic evidence is forbidden in production admission")
    expected_predecessors = {
        "S17-EXT-002": range(1, 2), "S17-EXT-003": range(2, 3),
        "S17-EXT-004": range(1, 4), "S17-EXT-005": range(1, 5),
        "S17-EXT-007": range(1, 7), "S17-EXT-008": range(1, 8),
        "S17-EXT-009": range(1, 9), "S17-EXT-010": range(1, 10),
    }
    predecessor_ids = tuple(f"S17-EXT-{index:03d}" for index in expected_predecessors[expected_input_id])
    _predecessors(manifest, admitted_resolutions, predecessor_ids)
    payload = manifest["payload"]
    authorization: dict[str, Any] | None = None
    if expected_input_id == "S17-EXT-002":
        _verify_ext002(payload, artifacts)
    elif expected_input_id == "S17-EXT-003":
        _verify_ext003(payload, artifacts, admitted_resolutions)
    elif expected_input_id == "S17-EXT-004":
        _verify_ext004(payload, artifacts)
    elif expected_input_id == "S17-EXT-005":
        authorization = _verify_ext005(
            payload, artifacts, admitted_resolutions,
            synthetic_test_only=manifest["synthetic_test_only"]
        )
    elif expected_input_id == "S17-EXT-007":
        _verify_ext007(
            payload, artifacts, admitted_resolutions,
            synthetic_test_only=manifest["synthetic_test_only"]
        )
    elif expected_input_id == "S17-EXT-008":
        _verify_ext008(payload, artifacts, admitted_resolutions)
    elif expected_input_id == "S17-EXT-009":
        _verify_ext009(payload, artifacts)
    elif expected_input_id == "S17-EXT-010":
        authorization = _verify_ext010(
            payload, artifacts, admitted_resolutions,
            synthetic_test_only=manifest["synthetic_test_only"],
        )
    else:
        raise OperationalSemanticError("no production semantic verifier is registered")
    result = {
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "manifest_path": str(manifest_path),
        "input_id": expected_input_id,
        "run_ids": payload.get("run_ids"),
        "authorization": authorization,
        "synthetic_test_only": manifest["synthetic_test_only"],
    }
    if authorization is not None:
        authorization_artifact = artifacts["AUTHORIZATION"]
        result["authorization_path"] = str(authorization_artifact.path)
        result["authorization_sha256"] = authorization_artifact.sha256
    return result
