#!/usr/bin/env python3
"""Stage 17 read-only preflight terminal-compatibility semantic successor."""

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


POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v13.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v13.schema.json"
POLICY_V12_PATH = (
    "config/stage17/stage17-read-only-preflight-"
    "evidence-admission-policy-v12.json"
)
ADR_0122_PATH = "docs/decisions/0122-stage17-preflight-terminal-compatibility.md"
EFFECTIVE_ACTION_PLAN_PATH = predecessor.ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = "config/stage17/stage17-read-only-preflight-fixed-action-plan-v8.json"
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-fixed-action-plan-v8.schema.json"
ENVELOPE_SCHEMA_PATH = "config/schemas/stage17-operational-evidence-envelope-v13.schema.json"
AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-authorization-v11.schema.json"
CONTRACT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-supporting-contract-v11.schema.json"
ATTEMPT_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-attempt-v9.schema.json"
OPERATIONAL_MANIFEST_SCHEMA_PATH = "config/schemas/stage17-operational-input-manifest-v1.schema.json"
ACTION_AUTHORIZATION_SCHEMA_PATH = "config/schemas/stage17-phase-action-authorization-v1.schema.json"
ACTION_RESULT_SCHEMA_PATH = "config/schemas/stage17-phase-action-result-v1.schema.json"
BLOCKER_SCHEMA_PATH = "config/schemas/stage17-preflight-pre-marker-blocker-v1.schema.json"
POST_MARKER_BLOCKER_SCHEMA_PATH = (
    "config/schemas/stage17-preflight-post-marker-blocker-v1.schema.json"
)
RECEIPT_SCHEMA_PATH = (
    "config/schemas/stage17-read-only-preflight-observation-receipt-v6.schema.json"
)
FAILURE_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-failure-v7.schema.json"
FAILURE_RETENTION_SCHEMA_PATH = (
    "config/schemas/stage17-read-only-preflight-failure-retention-v2.schema.json"
)
COMPLETION_SCHEMA_PATH = (
    "config/schemas/stage17-read-only-preflight-completion-v6.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "13"

SCHEMA_PATHS = (
    POLICY_SCHEMA_PATH, ENVELOPE_SCHEMA_PATH,
    AUTHORIZATION_SCHEMA_PATH, CONTRACT_SCHEMA_PATH, BLOCKER_SCHEMA_PATH,
    POST_MARKER_BLOCKER_SCHEMA_PATH,
    predecessor.PLAN_SCHEMA_PATH, SUCCESSOR_ACTION_PLAN_SCHEMA_PATH,
    predecessor.ATTEMPT_SCHEMA_PATH,
    "config/schemas/stage17-read-only-preflight-attempt-v7.schema.json",
    ATTEMPT_SCHEMA_PATH,
    RECEIPT_SCHEMA_PATH, FAILURE_SCHEMA_PATH, FAILURE_RETENTION_SCHEMA_PATH,
    COMPLETION_SCHEMA_PATH, OPERATIONAL_MANIFEST_SCHEMA_PATH,
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
    "semantic_verifier": "tools/stage17_read_only_preflight_semantic_verifier_v13.py",
    "executor": "tools/stage17_read_only_preflight_executor_v11.py",
    "collector": predecessor.COLLECTOR_PATH,
    "state_journal": "tools/stage17_state_journal_v15.py",
    "openssh_snapshot_broker": "tools/stage17_openssh_parent_snapshot_v2.py",
    "openssh_snapshot_broker_v1_helper": predecessor.SNAPSHOT_BROKER_PATH,
    "process_group_supervisor": "tools/stage17_process_group_supervisor_v2.py",
    "semantic_verifier_v8_helper": "tools/stage17_semantic_verifier_v8.py",
    "semantic_verifier_v10_helper":
        "tools/stage17_read_only_preflight_semantic_verifier_v10.py",
    "semantic_verifier_v11_helper":
        "tools/stage17_read_only_preflight_semantic_verifier_v11.py",
    "semantic_verifier_v12_helper":
        "tools/stage17_read_only_preflight_semantic_verifier_v12.py",
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


def verify_policy_v13(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v13")
    expected_predecessor = {
        "policy_v12": _binding_for(root, POLICY_V12_PATH),
        "adr_0122": _binding_for(root, ADR_0122_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v13 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v13 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v13 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v13 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v13 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v13 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v2.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v13 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v13 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v13 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v13 authority boundary drifted")


def _verify_successor_plan(root: pathlib.Path, policy: Mapping[str, Any]) -> None:
    path = _binding(root, policy["successor_action_plan"], "successor action plan v8")
    plan = _load_json(path)
    _validate_schema(root, plan, SUCCESSOR_ACTION_PLAN_SCHEMA_PATH, "successor action plan v8")
    if (plan.get("predecessor") != _binding_for(root, predecessor.ACTION_PLAN_PATH)
            or plan.get("effective_action_plan") !=
            _binding_for(root, predecessor.ACTION_PLAN_PATH)
            or plan.get("predecessor_successor") != _binding_for(
                root,
                "config/stage17/stage17-read-only-preflight-fixed-action-plan-v7.json",
            )):
        raise SemanticAdmissionError("successor action plan lineage drifted")


def _verify_pre_marker_predecessor(
    root: pathlib.Path, binding: Mapping[str, Any]
) -> tuple[dict[str, Any], pathlib.Path]:
    """Recheck the immutable blocker and its empty predecessor output root."""

    blocker_path = pathlib.Path(str(binding.get("locator", "")))
    if (not blocker_path.is_absolute() or blocker_path.is_symlink()
            or not blocker_path.is_file()):
        raise SemanticAdmissionError("pre-marker predecessor blocker locator is unsafe")
    blocker_payload = blocker_path.read_bytes()
    if (len(blocker_payload) != binding.get("size_bytes")
            or _sha256(blocker_path) != binding.get("sha256")):
        raise SemanticAdmissionError("pre-marker predecessor blocker bytes drifted")
    blocker_document = _load_json(blocker_path)
    _validate_schema(root, blocker_document, BLOCKER_SCHEMA_PATH,
                     "pre-marker predecessor blocker")
    for field in ("source_journal", "source_authorization"):
        source = blocker_document[field]
        source_path = pathlib.Path(source["locator"])
        if (not source_path.is_absolute() or source_path.is_symlink()
                or not source_path.is_file()
                or source_path.stat().st_size != source["size_bytes"]
                or _sha256(source_path) != source["sha256"]):
            raise SemanticAdmissionError(
                f"pre-marker blocker {field} source bytes drifted"
            )
    predecessor_output = pathlib.Path(
        blocker_document["source_preflight_output_root"]
    )
    if (not predecessor_output.is_absolute() or predecessor_output.is_symlink()
            or not predecessor_output.is_dir()
            or any(predecessor_output.iterdir())):
        raise SemanticAdmissionError(
            "pre-marker predecessor output is absent, unsafe, or nonempty"
        )
    return blocker_document, blocker_path


def _verify_external_binding(binding: Mapping[str, Any], label: str) -> pathlib.Path:
    path = pathlib.Path(str(binding.get("locator", "")))
    if (not path.is_absolute() or path.is_symlink() or not path.is_file()
            or path.stat().st_size != binding.get("size_bytes")
            or _sha256(path) != binding.get("sha256")):
        raise SemanticAdmissionError(f"post-marker blocker {label} bytes drifted")
    return path


def _verify_post_marker_predecessor(
    root: pathlib.Path, binding: Mapping[str, Any]
) -> tuple[dict[str, Any], pathlib.Path]:
    blocker_path = _verify_external_binding(binding, "receipt")
    blocker = _load_json(blocker_path)
    _validate_schema(root, blocker, POST_MARKER_BLOCKER_SCHEMA_PATH,
                     "post-marker predecessor blocker")
    source_paths = {
        field: _verify_external_binding(blocker[field], field)
        for field in (
            "predecessor_attempt_marker", "predecessor_journal",
            "predecessor_authorization", "predecessor_resolution",
            "predecessor_transition",
        )
    }
    marker = _load_json(source_paths["predecessor_attempt_marker"])
    _validate_schema(
        root, marker,
        "config/schemas/stage17-read-only-preflight-attempt-v8.schema.json",
        "D-121 predecessor attempt marker",
    )
    output_root = pathlib.Path(blocker["predecessor_output_root"]["locator"])
    if (not output_root.is_absolute() or output_root.is_symlink()
            or not output_root.is_dir()
            or sorted(item.name for item in output_root.iterdir()) !=
            ["stage17-read-only-preflight-attempt-v8.json"]
            or source_paths["predecessor_attempt_marker"] !=
            output_root / "stage17-read-only-preflight-attempt-v8.json"):
        raise SemanticAdmissionError("post-marker predecessor inventory drifted")
    observed = blocker["observed_failure"]
    if (observed["transport_started"] is not False
            or observed["remote_observation_count"] != 0
            or observed["completed_observation_ids"] != []
            or blocker["retry_allowed"] is not False
            or blocker["replacement_transaction_required"] is not True):
        raise SemanticAdmissionError("post-marker predecessor is not replaceable")
    return blocker, blocker_path


def verify_s17_ext_001_semantics_v13(
    *, root: pathlib.Path, resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], policy: dict[str, Any],
    policy_path: pathlib.Path, policy_sha256: str, policy_entry: dict[str, Any],
    graph_sha256: str, catalog_sha256: str, genesis_sha256: str,
    catalog: dict[str, Any], resolution_schema_sha256: str, **_: Any,
) -> dict[str, Any]:
    if receipt_documents:
        raise SemanticAdmissionError("S17-EXT-001 cannot use an external receipt")
    envelopes = [(path, document) for path, document in repository_documents if document.get("schema_version") == "cpu-prefetch-stage17-operational-evidence-envelope/13"]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v13 envelope")
    envelope_path, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 v13 envelope")
    if envelope.get("semantic_policy") != {"path": policy_path.relative_to(root).as_posix(), "size_bytes": policy_path.stat().st_size, "sha256": policy_sha256}:
        raise SemanticAdmissionError("S17-EXT-001 policy binding mismatch")
    if envelope.get("semantic_verifier") != {"verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}:
        raise SemanticAdmissionError("S17-EXT-001 verifier identity mismatch")
    expected_predecessor = {
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v12_sha256": policy["predecessor"]["policy_v12"]["sha256"],
        "adr_0122_sha256": policy["predecessor"]["adr_0122"]["sha256"],
    }
    if envelope.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("S17-EXT-001 v13 predecessor binding drifted")
    if envelope.get("runtime_implementations") != policy.get("implementations"):
        raise SemanticAdmissionError("S17-EXT-001 runtime closure drifted")
    expected_effective = {**policy["fixed_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6"}
    expected_successor = {**policy["successor_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/8"}
    if envelope.get("effective_action_plan") != expected_effective or envelope.get("successor_action_plan") != expected_successor:
        raise SemanticAdmissionError("S17-EXT-001 action plan binding drifted")
    _verify_successor_plan(root, policy)
    authorization_path = _binding(root, envelope["authorization"], "authorization")
    contract_path = _binding(root, envelope["supporting_contract"], "supporting contract")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/11" or envelope["supporting_contract"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-supporting-contract/11":
        raise SemanticAdmissionError("S17-EXT-001 authorization/contract schema drifted")
    authorization, contract = _load_json(authorization_path), _load_json(contract_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "authorization v11")
    _validate_schema(root, contract, CONTRACT_SCHEMA_PATH, "supporting contract v11")
    if authorization.get("supporting_observation_contract") != envelope["supporting_contract"] or authorization.get("fixed_action_plan") != expected_effective:
        raise SemanticAdmissionError("authorization contract/effective-plan binding drifted")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issued_at_utc")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expires_at_utc")
    if expires <= issued:
        raise SemanticAdmissionError("authorization expiry must follow issue")
    schema_by_path = {item["path"]: dict(item) for item in policy["schema_bindings"]}
    verified = predecessor._verify_contract_action_inputs(root, contract, policy, catalog)
    blocker = contract.get("pre_marker_predecessor")
    if not isinstance(blocker, dict):
        raise SemanticAdmissionError("pre-marker predecessor blocker binding is absent")
    _verify_pre_marker_predecessor(root, blocker)
    verified["pre_marker_predecessor"] = dict(blocker)
    post_marker = contract.get("post_marker_predecessor")
    if not isinstance(post_marker, dict):
        raise SemanticAdmissionError("post-marker predecessor blocker binding is absent")
    _verify_post_marker_predecessor(root, post_marker)
    verified["post_marker_predecessor"] = dict(post_marker)
    # The predecessor's inner contract verifier intentionally returns only
    # immutable inputs.  Its public v8 verifier added these record bindings to
    # the semantic context; reconstruct that public context here while
    # retaining the unchanged attempt and terminal-record schemas.
    verified["record_schema_bindings"] = {
        "attempt": schema_by_path[ATTEMPT_SCHEMA_PATH],
        "receipt": schema_by_path[RECEIPT_SCHEMA_PATH],
        "failure": schema_by_path[FAILURE_SCHEMA_PATH],
        "failure_retention": schema_by_path[FAILURE_RETENTION_SCHEMA_PATH],
        "completion": schema_by_path[COMPLETION_SCHEMA_PATH],
    }
    verified["attempt_marker_name"] = "stage17-read-only-preflight-attempt-v9.json"
    verified["failure_name"] = "stage17-read-only-preflight-failure-v7.json"
    verified["failure_retention_name"] = (
        "stage17-read-only-preflight-failure-retention-v2.json"
    )
    verified["completion_name"] = "stage17-read-only-preflight-completion-v6.json"
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


def evaluate_s17_ext_001_action_readiness_v13(
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
        _, blocker_path = _verify_pre_marker_predecessor(
            root, semantic_context["contract"]["pre_marker_predecessor"]
        )
        _, post_marker_path = _verify_post_marker_predecessor(
            root, semantic_context["contract"]["post_marker_predecessor"]
        )
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
    action["pre_marker_file_bindings"] = [
        *action["pre_marker_file_bindings"],
        {
            "locator": str(blocker_path),
            "size_bytes": blocker_path.stat().st_size,
            "sha256": _sha256(blocker_path),
        },
        {
            "locator": str(post_marker_path),
            "size_bytes": post_marker_path.stat().st_size,
            "sha256": _sha256(post_marker_path),
        },
    ]
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
