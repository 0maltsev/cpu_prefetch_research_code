#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor rebinding executor v14
and journal v20 (ADR-0130, `PROPOSED`).

This module is a new, additive file.  It does not modify
`stage17_read_only_preflight_semantic_verifier_v15.py`'s bytes, so the
already-accepted `stage17-operational-evidence-admission-policy-v22.json`
runtime-closure hash for that file remains valid and unchanged.  It exists
solely to rebind `IMPLEMENTATION_PATHS["executor"]` and
`IMPLEMENTATION_PATHS["state_journal"]` to `stage17_read_only_preflight_
executor_v14.py` and `stage17_state_journal_v20.py` -- the additive
successors ADR-0130 introduces to fix the real journal-reachability defect
found in `executor_v13.py`'s own hardcoded journal import.  No semantic
verification logic changes: `evaluate_s17_ext_001_action_readiness_v15`
(action-time re-validation) is deliberately left in `v15` unchanged and
reused as-is, since it is already generic over whichever policy the
admitted resolution's own `semantic_context` records -- confirmed
empirically (see ADR-0130) by directly re-running it against the real,
already-admitted `S17-EXT-001` resolution.  `verify_s17_ext_001_semantics_
v16` is therefore a deliberate alias of `verify_s17_ext_001_semantics_v15`,
not a fresh copy: unlike `verify_policy_v15` (which closes over version-
specific module constants such as `IMPLEMENTATION_PATHS`/
`POLICY_SCHEMA_PATH` and therefore required a fresh copy when v15 was
created), `verify_s17_ext_001_semantics_v15`'s body takes `policy`/
`policy_path`/`policy_sha256` as arguments and otherwise only reads
`predecessor`/`immediate_predecessor` attributes and frozen protocol-
identity constants (`VERIFIER_ID`, `VERIFIER_VERSION`,
`ENVELOPE_SCHEMA_PATH`, etc.) that do not vary by policy version -- so
aliasing it resolves correctly against whatever `policy`/`policy_path` its
caller (the outer registry's `_verify_ext001`) passes in for this version.
`verify_policy_v16` is a fresh copy, following the same rationale
`verify_policy_v15` itself documented.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v15 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v16.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v16.schema.json"
POLICY_V15_PATH = immediate_predecessor.POLICY_PATH
ADR_0130_PATH = "docs/decisions/0130-stage17-executor-journal-reachability.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v14.py",
    "state_journal": "tools/stage17_state_journal_v20.py",
}
"""``semantic_verifier`` deliberately keeps v15's own self-reference
(inherited unchanged above) rather than pointing at this file: action-time
re-validation still loads `current_semantic` = v15 directly (see module
docstring), so v15.py -- not this file -- is what is actually resident at
that role at runtime. This module exists only to hold new policy/ADR
constants for admission-time dispatch; binding it into its own
`implementations.semantic_verifier` would describe a file the action-time
path never actually loads, and would fail `_verify_loaded_runtime`'s
real-identity check the same way a stale executor/journal binding would."""

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
verify_s17_ext_001_semantics_v16 = immediate_predecessor.verify_s17_ext_001_semantics_v15


def verify_policy_v16(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v15``, retargeted at v16.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v16's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v14/journal v20 instead of
    v13/v17, and the ``policy_v15``/``adr_0130`` predecessor keys instead of
    ``policy_v14``/``adr_0126``), because a Python function alias resolves
    free variables against the module it was *defined* in, not the module it
    is *accessed* through -- aliasing predecessor's function here would have
    silently kept validating against v15's own executor-v13 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v16")
    expected_predecessor = {
        "policy_v15": _binding_for(root, POLICY_V15_PATH),
        "adr_0130": _binding_for(root, ADR_0130_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v16 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v16 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v16 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v16 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v16 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v16 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v2.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v16 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v16 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v16 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v16 authority boundary drifted")
