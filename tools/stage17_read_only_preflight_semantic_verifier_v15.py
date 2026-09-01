#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor adding the D-124
no-predecessor-attestation branch (ADR-0124, `PROPOSED`).

This module is a new, additive file.  It does not modify
`stage17_read_only_preflight_semantic_verifier_v14.py`'s bytes, so the
already-accepted `stage17-operational-evidence-admission-policy-v18.json`
runtime-closure hash for that file remains valid and unchanged.  It is not
wired into that policy's `runtime_closure`, so it is not the production
verifier for any currently accepted admission path; a real policy successor
(a new `stage17-operational-evidence-admission-policy` version binding this
file's own hash, alongside `stage17_operational_cli_v11.py`'s) is required
before this branch can resolve a real `S17-EXT-001` transaction.  That is
explicit follow-on work, not performed here.

`verify_s17_ext_001_semantics_v15` is a faithful copy of predecessor
`verify_s17_ext_001_semantics_v14`, broadened only to accept a
`stage17-read-only-preflight-supporting-contract/13` contract using either
the unchanged three-blocker-receipt branch or the new
`no_predecessor_attestation` branch, exactly as the v13 schema's `oneOf`
already enforces.  A `/12` contract is verified with byte-identical logic to
v14; the three-blocker helpers are reused unmodified from v14.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import stage17_read_only_preflight_semantic_verifier_v14 as immediate_predecessor
from stage17_semantic_verifier_v3 import (
    LIMITS, OBSERVATION_IDS, PERMISSIONS, SemanticAdmissionError,
    _binding, _binding_for, _load_json, _validate_schema, _sha256,
)
from stage17_semantic_verifier_v5 import _exact_second


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v15.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v15.schema.json"
POLICY_V14_PATH = immediate_predecessor.POLICY_PATH
ADR_0126_PATH = (
    "docs/decisions/0126-stage17-no-predecessor-attestation-executor-binding.md"
)
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "semantic_verifier": "tools/stage17_read_only_preflight_semantic_verifier_v15.py",
    "executor": "tools/stage17_read_only_preflight_executor_v13.py",
    "state_journal": "tools/stage17_state_journal_v17.py",
}

ENVELOPE_SCHEMA_PATH = immediate_predecessor.ENVELOPE_SCHEMA_PATH
AUTHORIZATION_SCHEMA_PATH = immediate_predecessor.AUTHORIZATION_SCHEMA_PATH
CONTRACT_V12_SCHEMA_PATH = immediate_predecessor.CONTRACT_SCHEMA_PATH
CONTRACT_V13_SCHEMA_PATH = (
    "config/schemas/stage17-read-only-preflight-supporting-contract-v13.schema.json"
)
NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH = (
    "config/schemas/stage17-preflight-no-predecessor-attestation-v1.schema.json"
)
NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY = (
    "cpu-prefetch-stage17-preflight-no-predecessor-attestation/1"
)
VERIFIER_ID = immediate_predecessor.VERIFIER_ID
VERIFIER_VERSION = immediate_predecessor.VERIFIER_VERSION

_verify_pre_marker_predecessor = immediate_predecessor._verify_pre_marker_predecessor
_verify_post_marker_predecessor = immediate_predecessor._verify_post_marker_predecessor
_verify_action_revalidation_predecessor = (
    immediate_predecessor._verify_action_revalidation_predecessor
)
_verify_external_binding = immediate_predecessor._verify_external_binding
_verify_successor_plan = immediate_predecessor._verify_successor_plan


def verify_policy_v15(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v14``, retargeted at v15.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v15's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v13 instead of v12, and the
    ``policy_v14``/``adr_0126`` predecessor keys instead of
    ``policy_v13``/``adr_0123``), because a Python function alias resolves
    free variables against the module it was *defined* in, not the module it
    is *accessed* through -- aliasing predecessor's function here would have
    silently kept validating against v14's own executor-v12 expectations.
    """
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v15")
    expected_predecessor = {
        "policy_v14": _binding_for(root, POLICY_V14_PATH),
        "adr_0126": _binding_for(root, ADR_0126_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v15 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v15 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v15 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v15 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v15 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v15 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v2.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v15 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v15 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v15 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v15 authority boundary drifted")


def _verify_no_predecessor_attestation(
    root: pathlib.Path, binding: Mapping[str, Any]
) -> tuple[dict[str, Any], pathlib.Path]:
    """Verify a D-124 attestation record and its bound search-evidence bytes.

    This never asserts that no predecessor incident occurred -- only that the
    attestation's own real bytes, and the real search-evidence file they
    bind, are exactly what the record claims.
    """
    attestation_path = _verify_external_binding(binding, "no-predecessor attestation")
    attestation = _load_json(attestation_path)
    _validate_schema(
        root, attestation, NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH,
        "D-124 no-predecessor attestation",
    )
    search_evidence = attestation.get("search_evidence")
    if not isinstance(search_evidence, dict):
        raise SemanticAdmissionError("no-predecessor attestation search_evidence is absent")
    _verify_external_binding(search_evidence, "search_evidence")
    if (attestation.get("declaration") != "NO_REAL_PREDECESSOR_EVIDENCE_FOUND"
            or attestation.get("covers_incident_ids") != ["D-120", "D-121", "D-123"]
            or attestation.get("retry_allowed") is not False
            or attestation.get("replacement_transaction_required") is not False
            or attestation.get("stage18_authority") is not False):
        raise SemanticAdmissionError("no-predecessor attestation governance fields drifted")
    return attestation, attestation_path


def classify_predecessor_evidence(contract: Mapping[str, Any]) -> str:
    """Return which exclusive predecessor-evidence branch a contract uses.

    Defense in depth: the v13 contract schema's `oneOf` already rejects a
    contract binding both branches or neither, but this is re-checked here
    so the classification is safe to call directly, independent of schema
    validation having already run.
    """
    has_attestation = isinstance(contract.get("no_predecessor_attestation"), dict)
    has_any_blocker = any(
        isinstance(contract.get(field), dict)
        for field in (
            "pre_marker_predecessor", "post_marker_predecessor",
            "action_revalidation_predecessor",
        )
    )
    if has_attestation and has_any_blocker:
        raise SemanticAdmissionError(
            "S17-EXT-001 cannot combine a no-predecessor attestation with any "
            "blocker-receipt binding"
        )
    if not has_attestation and not has_any_blocker:
        raise SemanticAdmissionError(
            "S17-EXT-001 requires either blocker-receipt bindings or a "
            "no-predecessor attestation"
        )
    return "ATTESTATION" if has_attestation else "BLOCKERS"


def verify_s17_ext_001_semantics_v15(
    *, root: pathlib.Path, resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], policy: dict[str, Any],
    policy_path: pathlib.Path, policy_sha256: str, policy_entry: dict[str, Any],
    graph_sha256: str, catalog_sha256: str, genesis_sha256: str,
    catalog: dict[str, Any], resolution_schema_sha256: str, **_: Any,
) -> dict[str, Any]:
    if receipt_documents:
        raise SemanticAdmissionError("S17-EXT-001 cannot use an external receipt")
    envelopes = [(path, document) for path, document in repository_documents if document.get("schema_version") == "cpu-prefetch-stage17-operational-evidence-envelope/14"]
    if len(envelopes) != 1 or len(repository_documents) != 1:
        raise SemanticAdmissionError("S17-EXT-001 requires exactly one v14 envelope")
    envelope_path, envelope = envelopes[0]
    _validate_schema(root, envelope, ENVELOPE_SCHEMA_PATH, "S17-EXT-001 v14 envelope")
    if envelope.get("semantic_policy") != {"path": policy_path.relative_to(root).as_posix(), "size_bytes": policy_path.stat().st_size, "sha256": policy_sha256}:
        raise SemanticAdmissionError("S17-EXT-001 policy binding mismatch")
    if envelope.get("semantic_verifier") != {"verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}:
        raise SemanticAdmissionError("S17-EXT-001 verifier identity mismatch")
    expected_predecessor = {
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_sha256": genesis_sha256,
        "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1",
        "resolution_schema_sha256": resolution_schema_sha256,
        "semantic_policy_v13_sha256": _sha256(root / immediate_predecessor.POLICY_V13_PATH),
        "adr_0123_sha256": _sha256(root / immediate_predecessor.ADR_0123_PATH),
    }
    if envelope.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("S17-EXT-001 v14 predecessor binding drifted")
    if envelope.get("runtime_implementations") != policy.get("implementations"):
        raise SemanticAdmissionError("S17-EXT-001 runtime closure drifted")
    expected_effective = {**policy["fixed_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6"}
    expected_successor = {**policy["successor_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/9"}
    if envelope.get("effective_action_plan") != expected_effective or envelope.get("successor_action_plan") != expected_successor:
        raise SemanticAdmissionError("S17-EXT-001 action plan binding drifted")
    _verify_successor_plan(root, policy)
    authorization_path = _binding(root, envelope["authorization"], "authorization")
    contract_path = _binding(root, envelope["supporting_contract"], "supporting contract")
    contract_schema_identity = envelope["supporting_contract"].get("schema_identity")
    if envelope["authorization"].get("schema_identity") != "cpu-prefetch-stage17-read-only-preflight-authorization/11":
        raise SemanticAdmissionError("S17-EXT-001 authorization schema drifted")
    if contract_schema_identity not in (
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/12",
        "cpu-prefetch-stage17-read-only-preflight-supporting-contract/13",
    ):
        raise SemanticAdmissionError("S17-EXT-001 contract schema drifted")
    authorization, contract = _load_json(authorization_path), _load_json(contract_path)
    _validate_schema(root, authorization, AUTHORIZATION_SCHEMA_PATH, "authorization v11")
    contract_schema_path = (
        CONTRACT_V13_SCHEMA_PATH if contract_schema_identity.endswith("/13")
        else CONTRACT_V12_SCHEMA_PATH
    )
    contract_schema_label = (
        "supporting contract v13" if contract_schema_identity.endswith("/13")
        else "supporting contract v12"
    )
    _validate_schema(root, contract, contract_schema_path, contract_schema_label)
    if authorization.get("supporting_observation_contract") != envelope["supporting_contract"] or authorization.get("fixed_action_plan") != expected_effective:
        raise SemanticAdmissionError("authorization contract/effective-plan binding drifted")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issued_at_utc")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expires_at_utc")
    if expires <= issued:
        raise SemanticAdmissionError("authorization expiry must follow issue")
    verified = predecessor._verify_contract_action_inputs(root, contract, policy, catalog)
    has_attestation = classify_predecessor_evidence(contract) == "ATTESTATION"
    if has_attestation:
        attestation, _attestation_path = _verify_no_predecessor_attestation(
            root, contract["no_predecessor_attestation"]
        )
        verified["no_predecessor_attestation"] = dict(contract["no_predecessor_attestation"])
    else:
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
        action_revalidation = contract.get("action_revalidation_predecessor")
        if not isinstance(action_revalidation, dict):
            raise SemanticAdmissionError(
                "action-revalidation predecessor blocker binding is absent"
            )
        _verify_action_revalidation_predecessor(root, action_revalidation)
        verified["action_revalidation_predecessor"] = dict(action_revalidation)
    schema_by_path = {item["path"]: dict(item) for item in policy["schema_bindings"]}
    verified["record_schema_bindings"] = {
        "attempt": schema_by_path[immediate_predecessor.ATTEMPT_SCHEMA_PATH],
        "receipt": schema_by_path[immediate_predecessor.RECEIPT_SCHEMA_PATH],
        "failure": schema_by_path[immediate_predecessor.FAILURE_SCHEMA_PATH],
        "failure_retention":
            schema_by_path[immediate_predecessor.FAILURE_RETENTION_SCHEMA_PATH],
        "completion": schema_by_path[immediate_predecessor.COMPLETION_SCHEMA_PATH],
    }
    verified["attempt_marker_name"] = "stage17-read-only-preflight-attempt-v10.json"
    verified["failure_name"] = "stage17-read-only-preflight-failure-v8.json"
    verified["failure_retention_name"] = (
        "stage17-read-only-preflight-failure-retention-v3.json"
    )
    verified["completion_name"] = "stage17-read-only-preflight-completion-v7.json"
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
    recorded = immediate_predecessor._parse_utc(
        resolution.get("recorded_at_utc"), "resolution time"
    )
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


def evaluate_s17_ext_001_action_readiness_v15(
    *, root: pathlib.Path, current_state: str,
    transition_documents: list[dict[str, Any]],
    transition_ids_and_hashes: list[tuple[str, str]], resolution_id: str,
    resolution_sha256: str, authorization: dict[str, Any],
    semantic_context: dict[str, Any], as_of_utc: str,
    runtime_identity_paths: dict[str, str] | None,
) -> dict[str, Any] | None:
    """Action-time revalidation, extended for either predecessor-evidence branch.

    A faithful copy of predecessor ``evaluate_s17_ext_001_action_readiness_v14``
    for every check unrelated to which predecessor-evidence branch the bound
    contract uses.  ``_reverify_current_action_inputs`` is reused unmodified
    from v14 -- it never inspects the blocker/attestation fields.  Only the
    branch-specific re-verification and its resulting file bindings differ,
    selected by the same ``classify_predecessor_evidence`` used at
    resolution time, so action-time and resolution-time agree on which
    branch a contract uses.
    """
    if current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT" or len(transition_documents) != 1:
        return None
    transition = transition_documents[0]
    if transition.get("evidence_resolutions") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "sha256": resolution_sha256}]:
        return None
    if transition.get("authorizations") != [{"input_id": "S17-EXT-001", "resolution_id": resolution_id, "authorization_id": authorization.get("authorization_id"), "authority_scope": "READ_ONLY_PREFLIGHT"}]:
        return None
    evaluation = immediate_predecessor._parse_utc(as_of_utc, "action evaluation time")
    issued = _exact_second(authorization.get("issued_at_utc"), "authorization issue")
    expires = _exact_second(authorization.get("expires_at_utc"), "authorization expiry")
    if not issued <= evaluation < expires:
        return None
    try:
        action = immediate_predecessor._reverify_current_action_inputs(
            root, semantic_context, runtime_identity_paths
        )
        _verify_successor_plan(root, semantic_context["policy"])
        contract = semantic_context["contract"]
        if classify_predecessor_evidence(contract) == "ATTESTATION":
            _, attestation_path = _verify_no_predecessor_attestation(
                root, contract["no_predecessor_attestation"]
            )
            extra_file_bindings = [{
                "locator": str(attestation_path),
                "size_bytes": attestation_path.stat().st_size,
                "sha256": _sha256(attestation_path),
            }]
        else:
            _, blocker_path = _verify_pre_marker_predecessor(
                root, contract["pre_marker_predecessor"]
            )
            _, post_marker_path = _verify_post_marker_predecessor(
                root, contract["post_marker_predecessor"]
            )
            _, action_revalidation_path = _verify_action_revalidation_predecessor(
                root, contract["action_revalidation_predecessor"],
            )
            extra_file_bindings = [
                {"locator": str(blocker_path), "size_bytes": blocker_path.stat().st_size, "sha256": _sha256(blocker_path)},
                {"locator": str(post_marker_path), "size_bytes": post_marker_path.stat().st_size, "sha256": _sha256(post_marker_path)},
                {"locator": str(action_revalidation_path), "size_bytes": action_revalidation_path.stat().st_size, "sha256": _sha256(action_revalidation_path)},
            ]
    except (KeyError, SemanticAdmissionError, OSError, ValueError):
        return None
    evidence_root = pathlib.Path(action["evidence_root"])
    if any(evidence_root.iterdir()):
        return None
    action["pre_marker_file_bindings"] = [
        *action["pre_marker_file_bindings"],
        *extra_file_bindings,
    ]
    transition_id, transition_sha256 = transition_ids_and_hashes[0]
    action.update({"resolution_id": resolution_id, "resolution_sha256": resolution_sha256, "transition_id": transition_id, "transition_sha256": transition_sha256})
    return action
