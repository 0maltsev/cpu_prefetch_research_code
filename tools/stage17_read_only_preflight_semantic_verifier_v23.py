#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor completing the
executor journal-reachability lockstep ADR-0138 missed (ADR-0139,
`ACCEPTED`).

This module is a new, additive file. It does not modify
`stage17_read_only_preflight_semantic_verifier_v22.py`'s bytes, so any
already-accepted-adjacent closure hash for that file remains valid and
unchanged. It exists solely to rebind `IMPLEMENTATION_PATHS["executor"]`
to `stage17_read_only_preflight_executor_v21.py` (whose own `current_
journal` import moves to `stage17_state_journal_v29.py` -- this same
ADR's own new journal generation, so the executor and `cli_v11.py` land
on the identical final journal generation once this ADR's implementation
completes, exactly as `v20`/`v27` matched at the end of ADR-0137 --
completing the reachability-gap class ADR-0130 first established: `v22`
correctly moved `IMPLEMENTATION_PATHS["state_journal"]` to `v27` in
lockstep with `executor_v20.py`'s own import at the time, but ADR-0138
then advanced `cli_v11.py`'s own `journal_runtime` to `v28` without
advancing the executor's matching import, reopening the same gap one
generation later) -- and, in lockstep, `IMPLEMENTATION_PATHS[
"state_journal"]` to `stage17_state_journal_v29.py` to match.
`IMPLEMENTATION_PATHS["collector"]`, `["process_group_supervisor"]`, and
`["openssh_snapshot_broker"]` are unaffected and stay at `v22`'s inherited
`v3`/`v3`/`v5` bindings. No semantic verification logic changes:
`evaluate_s17_ext_001_action_readiness_v20` is reused as-is from `v20`
(via `v21` via `v22`), keeping its existing `_v20`-suffixed name
unchanged, the same convention `v16`-`v22` already established.
`verify_s17_ext_001_semantics_v23` is therefore a deliberate alias of
`v22`'s own `verify_s17_ext_001_semantics_v22`, for the same reason
`v16`-`v22`'s aliases were correct. `verify_policy_v23` is a fresh copy,
following the same rationale `verify_policy_v16`-`v22` themselves
documented.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v22 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v23.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v23.schema.json"
POLICY_V22_PATH = immediate_predecessor.POLICY_PATH
ADR_0139_PATH = "docs/decisions/0139-stage17-executor-journal-reachability-followup-2.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v21.py",
    "state_journal": "tools/stage17_state_journal_v29.py",
}
"""``semantic_verifier`` deliberately keeps `v20`'s own value unchanged
(action-time re-validation still loads `current_semantic` = `v20`'s own
functions unchanged); ``collector``, ``process_group_supervisor``, and
``openssh_snapshot_broker`` deliberately keep `v22`'s own inherited
values (`v3`/`v3`/`v5`); this ADR does not touch the collector, process-
group supervision, or OpenSSH consumption at all."""

ENVELOPE_SCHEMA_PATH = immediate_predecessor.ENVELOPE_SCHEMA_PATH
AUTHORIZATION_SCHEMA_PATH = immediate_predecessor.AUTHORIZATION_SCHEMA_PATH
CONTRACT_V12_SCHEMA_PATH = immediate_predecessor.CONTRACT_V12_SCHEMA_PATH
CONTRACT_V13_SCHEMA_PATH = immediate_predecessor.CONTRACT_V13_SCHEMA_PATH
CONTRACT_V14_SCHEMA_PATH = immediate_predecessor.CONTRACT_V14_SCHEMA_PATH
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
_verify_captured_pilot_candidate_identity = (
    immediate_predecessor._verify_captured_pilot_candidate_identity
)

evaluate_s17_ext_001_action_readiness_v20 = (
    immediate_predecessor.evaluate_s17_ext_001_action_readiness_v20
)
verify_s17_ext_001_semantics_v23 = immediate_predecessor.verify_s17_ext_001_semantics_v22


def verify_policy_v23(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v22``, retargeted at v23.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v23's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v21/state_journal v28
    instead of v20/v27, and the ``policy_v22``/``adr_0139`` predecessor
    keys instead of ``policy_v21``/``adr_0137``), because a Python
    function alias resolves free variables against the module it was
    *defined* in, not the module it is *accessed* through -- aliasing
    predecessor's function here would have silently kept validating
    against v22's own executor-v20/state_journal-v27 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v23")
    expected_predecessor = {
        "policy_v22": _binding_for(root, POLICY_V22_PATH),
        "adr_0139": _binding_for(root, ADR_0139_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v23 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v23 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v23 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v23 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v23 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v23 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v23 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v23 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v23 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v23 authority boundary drifted")
