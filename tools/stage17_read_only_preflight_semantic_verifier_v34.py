"""Fresh preflight policy34 binds executor34 and the generic policy60 journal."""
from __future__ import annotations
import pathlib
from typing import Any
import stage17_read_only_preflight_semantic_verifier_v33 as predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v34.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v34.schema.json"
POLICY_V33_PATH = predecessor.POLICY_PATH
ADR_0231_PATH = "docs/decisions/0231-formal-admission-custody-successor.md"
EFFECTIVE_ACTION_PLAN_PATH = predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = predecessor.SUCCESSOR_ACTION_PLAN_PATH
SCHEMA_PATHS = predecessor.SCHEMA_PATHS
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = predecessor.VERIFIER_VERSION
IMPLEMENTATION_PATHS = {**predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v34.py",
    "state_journal": "tools/stage17_state_journal_v56.py"}
verify_s17_ext_001_semantics_v27 = predecessor.verify_s17_ext_001_semantics_v27


def verify_policy_v34(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Check the unchanged preflight rules with D231 predecessor/runtime bindings."""
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v34")
    expected_predecessor = {
        "policy_v33": _binding_for(root, POLICY_V33_PATH),
        "adr_0231": _binding_for(root, ADR_0231_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v34 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v34 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v34 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v34 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v34 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v34 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v34 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v34 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v34 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v34 authority boundary drifted")


verify_policy_v27 = verify_policy_v34

verify_s17_ext_001_semantics_v34 = verify_s17_ext_001_semantics_v27
