#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor rebinding executor v17
and the OpenSSH snapshot broker's completed re-export surface (ADR-0133,
`ACCEPTED`).

This module is a new, additive file.  It does not modify
`stage17_read_only_preflight_semantic_verifier_v18.py`'s bytes, so any
already-accepted-adjacent closure hash for that file remains valid and
unchanged.  It exists solely to rebind `IMPLEMENTATION_PATHS["executor"]`,
`IMPLEMENTATION_PATHS["openssh_snapshot_broker"]`, and
`IMPLEMENTATION_PATHS["state_journal"]` to `stage17_read_only_preflight_
executor_v17.py`, `stage17_openssh_parent_snapshot_v5.py`, and `stage17_
state_journal_v23.py` -- the additive successors ADR-0133 introduces to
fix the real, reproduced `AttributeError` when `v4.py`'s incomplete
re-export surface omitted `verify_local_openssh_parent_procfd_
capability`, plus the journal rebind `executor_v17.py`'s own `current_
journal` import needs to stay on the same generation `cli_v11.py` itself
uses (the same reachability-gap class ADR-0130/ADR-0131/ADR-0132 already
fixed three times).  `IMPLEMENTATION_PATHS["process_group_supervisor"]`
is unaffected by this fix and stays at `v18`'s inherited `v3` binding.
No semantic verification logic changes: `evaluate_s17_ext_001_action_
readiness_v15` is reused as-is from `v15`, exactly as `v16`/`v17`/`v18`
already established, since it is generic over whichever policy the
admitted resolution's own `semantic_context` records and never touches
the OpenSSH snapshot broker's own file identity beyond the generic
`implementations` closure check.  `verify_s17_ext_001_semantics_v19` is
therefore a deliberate alias of `verify_s17_ext_001_semantics_v15`, for
the same reason `v16`/`v17`/`v18`'s aliases were correct: its body takes
`policy`/`policy_path`/`policy_sha256` as arguments and otherwise only
reads `predecessor`/`immediate_predecessor` attributes and frozen
protocol-identity constants that do not vary by policy version.
`verify_policy_v19` is a fresh copy, following the same rationale
`verify_policy_v16`/`v17`/`v18` themselves documented.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v18 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v19.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v19.schema.json"
POLICY_V18_PATH = immediate_predecessor.POLICY_PATH
ADR_0133_PATH = "docs/decisions/0133-stage17-openssh-snapshot-broker-reexport-completeness.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v17.py",
    "openssh_snapshot_broker": "tools/stage17_openssh_parent_snapshot_v5.py",
    "state_journal": "tools/stage17_state_journal_v23.py",
}
"""``semantic_verifier`` deliberately keeps v16's own inherited value
(v15.py) rather than pointing at this file: action-time re-validation
still loads `current_semantic` = v15 directly (unchanged since ADR-0130).
`process_group_supervisor` deliberately keeps v18's own inherited value
(v3.py), since ADR-0133 does not touch process-group supervision at all.
`state_journal` moves to `v23` (bound to policy v27) because `executor_
v17.py`'s own `current_journal` import moved there too, in lockstep with
`cli_v11.py`'s own journal_runtime import -- the exact same
reachability-gap class ADR-0130 already established and ADR-0131/
ADR-0132 already had to re-apply."""

ENVELOPE_SCHEMA_PATH = immediate_predecessor.ENVELOPE_SCHEMA_PATH
AUTHORIZATION_SCHEMA_PATH = immediate_predecessor.AUTHORIZATION_SCHEMA_PATH
CONTRACT_V12_SCHEMA_PATH = immediate_predecessor.CONTRACT_V12_SCHEMA_PATH
CONTRACT_V13_SCHEMA_PATH = immediate_predecessor.CONTRACT_V13_SCHEMA_PATH
NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH = (
    immediate_predecessor.NO_PREDECESSOR_ATTESTATION_SCHEMA_PATH
)
NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY = (
    immediate_predecessor.NO_PREDECESSOR_ATTESTATION_SCHEMA_IDENTITY
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
_verify_no_predecessor_attestation = immediate_predecessor._verify_no_predecessor_attestation
classify_predecessor_evidence = immediate_predecessor.classify_predecessor_evidence

evaluate_s17_ext_001_action_readiness_v15 = (
    immediate_predecessor.evaluate_s17_ext_001_action_readiness_v15
)
verify_s17_ext_001_semantics_v19 = immediate_predecessor.verify_s17_ext_001_semantics_v18


def verify_policy_v19(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v18``, retargeted at v19.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v19's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v17/openssh snapshot v5
    instead of v16/v4, and the ``policy_v18``/``adr_0133`` predecessor keys
    instead of ``policy_v17``/``adr_0132``), because a Python function
    alias resolves free variables against the module it was *defined* in,
    not the module it is *accessed* through -- aliasing predecessor's
    function here would have silently kept validating against v18's own
    executor-v16/openssh-snapshot-v4 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v19")
    expected_predecessor = {
        "policy_v18": _binding_for(root, POLICY_V18_PATH),
        "adr_0133": _binding_for(root, ADR_0133_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v19 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v19 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v19 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v19 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v19 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v19 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v19 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v19 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v19 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v19 authority boundary drifted")
