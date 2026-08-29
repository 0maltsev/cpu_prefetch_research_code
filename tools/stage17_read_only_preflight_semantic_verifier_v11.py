#!/usr/bin/env python3
"""Stage 17 read-only preflight canonical-serializer semantic successor."""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import stage17_read_only_preflight_semantic_verifier_v10 as policy_predecessor
import stage17_semantic_verifier_v8 as predecessor
from stage17_operational_semantics_v1 import (
    OperationalSemanticError,
    verify_manifest,
)
from stage17_semantic_verifier_v3 import (
    LIMITS, OBSERVATION_IDS, PERMISSIONS, SemanticAdmissionError,
    _binding, _binding_for, _load_json, _parse_utc, _sha256, _validate_schema,
)
from stage17_semantic_verifier_v5 import _exact_second


POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v11.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v11.schema.json"
POLICY_V10_PATH = (
    "config/stage17/stage17-read-only-preflight-"
    "evidence-admission-policy-v10.json"
)
ADR_0119_PATH = "docs/decisions/0119-stage17-preflight-canonical-serializer-runtime.md"
EFFECTIVE_ACTION_PLAN_PATH = predecessor.ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = "config/stage17/stage17-read-only-preflight-fixed-action-plan-v7.json"
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-fixed-action-plan-v7.schema.json"
ENVELOPE_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-envelope-v11.schema.json"
AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-authorization-v9.schema.json"
CONTRACT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-supporting-contract-v9.schema.json"
ATTEMPT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-attempt-v7.schema.json"
OPERATIONAL_MANIFEST_SCHEMA_PATH = "config/schemas/stage17-operational-input-manifest-v1.schema.json"
ACTION_AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-phase-action-authorization-v1.schema.json"
ACTION_RESULT_SCHEMA_PATH = "config/schemas/stage17-phase-action-result-v1.schema.json"
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "11"

SCHEMA_PATHS = (
    POLICY_SCHEMA_PATH, ENVELOPE_SCHEMA_PATH,
    AUTHORIZATION_SCHEMA_PATH, CONTRACT_SCHEMA_PATH,
    predecessor.PLAN_SCHEMA_PATH, SUCCESSOR_ACTION_PLAN_SCHEMA_PATH,
    predecessor.ATTEMPT_SCHEMA_PATH, ATTEMPT_SCHEMA_PATH,
    predecessor.RECEIPT_SCHEMA_PATH,
    predecessor.FAILURE_SCHEMA_PATH, predecessor.FAILURE_RETENTION_SCHEMA_PATH,
    predecessor.COMPLETION_SCHEMA_PATH, OPERATIONAL_MANIFEST_SCHEMA_PATH,
    ACTION_AUTHORIZATION_SCHEMA_PATH,
    "config/schemas/stage17-operational-input-external-contract-v1.schema.json",
    "config/schemas/stage17-fixed-phase-actions-v1.schema.json",
    "config/schemas/stage17-fixed-action-request-v1.schema.json",
    "config/schemas/stage17-phase-action-evidence-v1.schema.json",
    "config/schemas/stage17-pilot-exit-record-v1.schema.json",
    "config/schemas/stage17-pilot-exit-journal-v1.schema.json",
    "config/schemas/phase18-access-journal-v1.schema.json",
    "config/schemas/phase18-readiness-report-v1.schema.json",
    "config/schemas/phase18-authorization-draft-v1.schema.json",
    "config/schemas/stage17-pilot-attempt-v1.schema.json",
    "config/schemas/stage17-pilot-receipt-v1.schema.json",
    "config/schemas/stage17-pilot-failure-v1.schema.json",
    "config/schemas/stage17-pilot-completion-v1.schema.json",
    "config/schemas/stage17-sealed-pilot-artifact-manifest-v1.schema.json",
    "config/schemas/stage17-completion-statement-v1.schema.json",
    "config/schemas/stage17-treatment-blind-freeze-v1.schema.json",
)

IMPLEMENTATION_PATHS = {
    "semantic_verifier": "tools/stage17_read_only_preflight_semantic_verifier_v11.py",
    "executor": "tools/stage17_read_only_preflight_executor_v9.py",
    "collector": predecessor.COLLECTOR_PATH,
    "state_journal": "tools/stage17_state_journal_v12.py",
    "openssh_snapshot_broker": predecessor.SNAPSHOT_BROKER_PATH,
    "process_group_supervisor": "tools/stage17_process_group_supervisor_v2.py",
    "semantic_verifier_v8_helper": "tools/stage17_semantic_verifier_v8.py",
    "semantic_verifier_v10_helper":
        "tools/stage17_read_only_preflight_semantic_verifier_v10.py",
    "semantic_verifier_v7_helper": "tools/stage17_semantic_verifier_v7.py",
    "semantic_verifier_v6_helper": "tools/stage17_semantic_verifier_v6.py",
    "semantic_verifier_v5_helper": "tools/stage17_semantic_verifier_v5.py",
    "semantic_verifier_v4_helper": "tools/stage17_semantic_verifier_v4.py",
    "semantic_verifier_v3_helper": "tools/stage17_semantic_verifier_v3.py",
    "collector_v1_helper": "tools/stage17_read_only_preflight_collector_v1.py",
    "state_journal_v10_helper": "tools/stage17_state_journal_v10.py",
    "state_journal_v11_helper": "tools/stage17_state_journal_v11.py",
    "state_journal_v1_helper": "tools/stage17_state_journal.py",
    "pilot_candidate_verifier": "tools/stage17_pilot_candidate_artifact.py",
    "operational_semantics": "tools/stage17_operational_semantics_v1.py",
}


def verify_policy_v11(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v11")
    expected_predecessor = {
        "policy_v10": _binding_for(root, POLICY_V10_PATH),
        "adr_0119": _binding_for(root, ADR_0119_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v11 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v11 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v11 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v11 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v11 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v11 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v2.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v11 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v11 operational definitions drifted")
    entries = policy.get("entries")
    expected = [
        {"input_id": f"S17-EXT-{index:03d}", "status": "IMPLEMENTED",
         "verifier_id": f"STAGE17-S17-EXT-{index:03d}-SEMANTIC-VERIFIER",
         "verifier_version": "9" if index == 1 else ("1" if index != 6 else "1")}
        for index in range(1, 11)
    ]
    expected[0]["verifier_id"] = VERIFIER_ID
    expected[0]["verifier_version"] = VERIFIER_VERSION
    expected[5]["verifier_id"] = "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
    if entries != expected:
        raise SemanticAdmissionError("semantic policy v11 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v11 authority boundary drifted")


def _verify_successor_plan(root: pathlib.Path, policy: Mapping[str, Any]) -> None:
    path = _binding(root, policy["successor_action_plan"], "successor action plan v7")
    plan = _load_json(path)
    _validate_schema(root, plan, SUCCESSOR_ACTION_PLAN_SCHEMA_PATH, "successor action plan v7")
    if plan.get("predecessor") != _binding_for(root, predecessor.ACTION_PLAN_PATH) or plan.get("effective_action_plan") != _binding_for(root, predecessor.ACTION_PLAN_PATH):
        raise SemanticAdmissionError("successor action plan lineage drifted")


def verify_s17_ext_001_semantics_v11(
    *, root: pathlib.Path, resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], policy: dict[str, Any],
    policy_path: pathlib.Path, policy_sha256: str, policy_entry: dict[str, Any],
    graph_sha256: str, catalog_sha256: str, genesis_sha256: str,
    catalog: dict[str, Any], resolution_schema_sha256: str, **_: Any,
) -> dict[str, Any]:
    if receipt_documents:
        raise SemanticAdmissionError("S17-EXT-001 cannot use an external receipt")
    envelopes = [(path, document) for path, document in repository_documents if document.get("schema_version") == "cpu-prefetch-stage17-operational-evidence-envelope/11"]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v11 envelope")
    envelope_path, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 v11 envelope")
    if envelope.get("semantic_policy") != {"path": policy_path.relative_to(root).as_posix(), "size_bytes": policy_path.stat().st_size, "sha256": policy_sha256}:
        raise SemanticAdmissionError("S17-EXT-001 policy binding mismatch")
    if envelope.get("semantic_verifier") != {"verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}:
        raise SemanticAdmissionError("S17-EXT-001 verifier identity mismatch")
    expected_predecessor = {
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v10_sha256": policy["predecessor"]["policy_v10"]["sha256"],
        "adr_0119_sha256": policy["predecessor"]["adr_0119"]["sha256"],
    }
    if envelope.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("S17-EXT-001 v11 predecessor binding drifted")
    if envelope.get("runtime_implementations") != policy.get("implementations"):
        raise SemanticAdmissionError("S17-EXT-001 runtime closure drifted")
    expected_effective = {**policy["fixed_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6"}
    expected_successor = {**policy["successor_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/7"}
    if envelope.get("effective_action_plan") != expected_effective or envelope.get("successor_action_plan") != expected_successor:
        raise SemanticAdmissionError("S17-EXT-001 action plan binding drifted")
    _verify_successor_plan(root, policy)
    authorization_path = _binding(root, envelope["authorization"], "authorization")
    contract_path = _binding(root, envelope["supporting_contract"], "supporting contract")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/9" or envelope["supporting_contract"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-supporting-contract/9":
        raise SemanticAdmissionError("S17-EXT-001 authorization/contract schema drifted")
    authorization, contract = _load_json(authorization_path), _load_json(contract_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "authorization v9")
    _validate_schema(root, contract, CONTRACT_SCHEMA_PATH, "supporting contract v9")
    if authorization.get("supporting_observation_contract") != envelope["supporting_contract"] or authorization.get("fixed_action_plan") != expected_effective:
        raise SemanticAdmissionError("authorization contract/effective-plan binding drifted")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issued_at_utc")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expires_at_utc")
    if expires <= issued:
        raise SemanticAdmissionError("authorization expiry must follow issue")
    schema_by_path = {item["path"]: dict(item) for item in policy["schema_bindings"]}
    verified = predecessor._verify_contract_action_inputs(root, contract, policy, catalog)
    # The predecessor's inner contract verifier intentionally returns only
    # immutable inputs.  Its public v8 verifier added these record bindings to
    # the semantic context; reconstruct that public context here while
    # retaining the unchanged attempt and terminal-record schemas.
    verified["record_schema_bindings"] = {
        "attempt": schema_by_path[ATTEMPT_SCHEMA_PATH],
        "receipt": schema_by_path[predecessor.RECEIPT_SCHEMA_PATH],
        "failure": schema_by_path[predecessor.FAILURE_SCHEMA_PATH],
        "failure_retention": schema_by_path[predecessor.FAILURE_RETENTION_SCHEMA_PATH],
        "completion": schema_by_path[predecessor.COMPLETION_SCHEMA_PATH],
    }
    verified["attempt_marker_name"] = "stage17-read-only-preflight-attempt-v7.json"
    verified["failure_name"] = predecessor.FAILURE_NAME
    verified["failure_retention_name"] = predecessor.FAILURE_RETENTION_NAME
    verified["completion_name"] = predecessor.COMPLETION_NAME
    target = contract["target"]
    expected_target = {
        "stand_id": target["stand_id"], "ssh_target": target["ssh_target"],
        "known_hosts_host": target["known_hosts_host"],
        "pinned_host_key_evidence_sha256": target["pinned_host_key_evidence"]["sha256"],
        "pinned_known_hosts_sha256": target["pinned_known_hosts"]["sha256"],
        "transport_identity_sha256": target["transport_identity"]["sha256"],
    }
    if authorization.get("target") != expected_target or tuple(authorization.get("frozen_observation_ids", [])) != OBSERVATION_IDS:
        raise SemanticAdmissionError("authorization target/observation family drifted")
    expected_scope = (
        f"STAND_ID={target['stand_id']};SSH_TARGET={target['ssh_target']};"
        "SCOPE=READ_ONLY_PREFLIGHT;PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v6"
    )
    if authorization.get("target_scope") != expected_scope or authorization.get("evidence_root") != contract.get("evidence_root"):
        raise SemanticAdmissionError("authorization target scope/evidence root drifted")
    if authorization.get("limits") != LIMITS or authorization.get("permissions") != PERMISSIONS:
        raise SemanticAdmissionError("authorization limits/permissions widened")
    if any((authorization.get("role_collapse_acknowledged") is not True, authorization.get("independent_review_claimed") is not False, authorization.get("automatic_transition") is not False, authorization.get("retry_allowed") is not False, authorization.get("stage18_authority") is not False)):
        raise SemanticAdmissionError("authorization governance boundary drifted")
    summary = resolution.get("authorization")
    if not isinstance(summary, dict):
        raise SemanticAdmissionError("resolution authorization summary is missing")
    for field in ("authorization_id", "issued_at_utc", "expires_at_utc", "authority_scope"):
        if summary.get(field) != authorization.get(field):
            raise SemanticAdmissionError(f"resolution authorization {field} mismatch")
    if summary.get("evidence_path") != authorization_path.relative_to(root).as_posix() or authorization.get("actor") != resolution.get("actor"):
        raise SemanticAdmissionError("resolution authorization path/actor mismatch")
    recorded = _parse_utc(resolution.get("recorded_at_utc"), "resolution time")
    if not issued <= recorded < expires:
        raise SemanticAdmissionError("authorization is not valid at resolution time")
    return {"authorization": authorization, "context": {
        "authorization_path": authorization_path, "authorization_sha256": _sha256(authorization_path),
        "contract_path": contract_path, "contract_sha256": _sha256(contract_path),
        "contract": contract, "policy": policy, "policy_path": policy_path,
        "policy_sha256": policy_sha256, "manifest_id": envelope["envelope_id"],
        "manifest_path": str(envelope_path), "manifest_sha256": _sha256(envelope_path),
        "synthetic_test_only": envelope["envelope_id"].startswith("SYNTHETIC-"),
        **verified,
    }}


def evaluate_s17_ext_001_action_readiness_v11(
    *, root: pathlib.Path, current_state: str,
    transition_documents: list[dict[str, Any]],
    transition_ids_and_hashes: list[tuple[str, str]], resolution_id: str,
    resolution_sha256: str, authorization: dict[str, Any],
    semantic_context: dict[str, Any], as_of_utc: str,
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any] | None:
    if current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT" or len(transition_documents) != 1:
        return None
    transition = transition_documents[0]
    if transition.get("evidence_resolutions") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "sha256": resolution_sha256}]:
        return None
    if transition.get("authorizations") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "authorization_id": authorization.get("authorization_id"), "authority_scope": "READ_ONLY_PREFLIGHT"}]:
        return None
    evaluation = _parse_utc(as_of_utc, "action evaluation time")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issue")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expiry")
    if not issued <= evaluation < expires:
        return None
    try:
        action = predecessor.reverify_action_inputs(root, semantic_context, runtime_identity_paths)
        _verify_successor_plan(root, semantic_context["policy"])
    except (SemanticAdmissionError, OSError, ValueError):
        return None
    evidence_root = pathlib.Path(action["evidence_root"])
    if (evidence_root / semantic_context["attempt_marker_name"]).exists():
        return None
    action["record_schema_bindings"] = dict(
        semantic_context["record_schema_bindings"]
    )
    action["attempt_marker_name"] = semantic_context["attempt_marker_name"]
    action["failure_name"] = semantic_context["failure_name"]
    action["failure_retention_name"] = semantic_context["failure_retention_name"]
    action["completion_name"] = semantic_context["completion_name"]
    transition_id, transition_sha256 = transition_ids_and_hashes[0]
    action.update({"resolution_id": resolution_id, "resolution_sha256": resolution_sha256, "transition_id": transition_id, "transition_sha256": transition_sha256})
    return action


def verify_operational_manifest_semantics(
    *, root: pathlib.Path, input_id: str,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], admitted_resolutions: Mapping[str, Any],
    allow_synthetic: bool,
) -> dict[str, Any]:
    candidates: list[pathlib.Path] = []
    candidates.extend(path for path, document in repository_documents if document.get("schema_version") == "cpu-prefetch-stage17-operational-input-manifest/1")
    for receipt in receipt_documents:
        locator = receipt.get("artifact_locator")
        if isinstance(locator, str):
            candidate = pathlib.Path(locator)
            try:
                document = _load_json(candidate)
            except (OSError, ValueError):
                document = {}
            if document.get("schema_version") == "cpu-prefetch-stage17-operational-input-manifest/1":
                candidates.append(candidate)
    candidates = [path for path in candidates if path.is_file()]
    if len(candidates) != 1:
        raise SemanticAdmissionError(f"{input_id} requires exactly one operational manifest")
    try:
        result = verify_manifest(
            manifest_path=candidates[0], repository_root=root,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
        )
    except OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    phase_authorization = result.pop("authorization")
    authorization: dict[str, Any] | None = None
    if isinstance(phase_authorization, dict):
        if input_id == "S17-EXT-005":
            authorization = {
                "authorization_id": phase_authorization["authorization_id"],
                "issued_at_utc": phase_authorization["issued_at_utc"],
                "expires_at_utc": phase_authorization["expires_at_utc"],
                "authority_scope": "PRIVILEGED_QUALIFICATION_CONTROL",
                "permissions": {
                    "privileged_controls": True, "calibration": False,
                    "pilot_execution": False, "stage18_authority": False,
                },
            }
        elif input_id == "S17-EXT-010":
            authorization = {
                "authorization_id": phase_authorization["authorization_id"],
                "issued_at_utc": phase_authorization["issued_at_utc"],
                "expires_at_utc": phase_authorization["expires_at_utc"],
                "authority_scope": "STAGE17_PILOT_PHASE_ONLY",
                "permissions": {
                    "pilot_execution": True, "stage18_authority": False,
                },
            }
        result["phase_authorization"] = phase_authorization
    return {"authorization": authorization, "context": result}
