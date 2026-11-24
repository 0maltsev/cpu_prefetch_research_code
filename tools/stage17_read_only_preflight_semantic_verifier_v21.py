#!/usr/bin/env python3
"""Stage 17 S17-EXT-001 semantic-verifier successor rebinding executor v19
and the collector's corrected runtime-tool symlink identity (ADR-0135,
`PROPOSED`).

This module is a new, additive file.  It does not modify
`stage17_read_only_preflight_semantic_verifier_v20.py`'s bytes, so any
already-accepted-adjacent closure hash for that file remains valid and
unchanged.  It exists to rebind `IMPLEMENTATION_PATHS["executor"]` and
`IMPLEMENTATION_PATHS["collector"]` to `stage17_read_only_preflight_
executor_v19.py` and `stage17_read_only_preflight_collector_v3.py` -- the
additive successors ADR-0135 introduces to fix the real, reproduced
`REMOTE_NONZERO_EXIT`/`runtime file` failure when `S17-RO-PREFLIGHT-005-
RUNTIME-TOOL-IDENTITIES` rejected `/usr/bin/python3`/`sha256sum`/`uname`
outright for being symlinks, which they ordinarily are on real hosts --
and, in lockstep, `IMPLEMENTATION_PATHS["state_journal"]` to `stage17_
state_journal_v25.py`, since `executor_v19.py`'s own `current_journal`
import moved there too (the same reachability-gap class ADR-0130 through
ADR-0134 already established; unlike `current_semantic`, `current_
journal` always tracks the newest generation, never staying pinned to an
older one). `IMPLEMENTATION_PATHS["process_group_supervisor"]` and
`["openssh_snapshot_broker"]` are unaffected and stay at `v20`'s
inherited `v3`/`v5` bindings.  No semantic verification logic changes: `evaluate_s17_ext_001_
action_readiness_v20` is reused as-is from `v20`, keeping its existing
`_v20`-suffixed name unchanged (the same convention `v16`-`v19` already
established relative to `v15`'s own fresh copy), since it is generic
over whichever policy the admitted resolution's own `semantic_context`
records and never touches the collector's own file identity beyond the
generic `implementations` closure check.  `verify_s17_ext_001_semantics_
v21` is therefore a deliberate alias of `verify_s17_ext_001_semantics_
v20`, for the same reason `v16`-`v19`'s aliases were correct: its body
takes `policy`/`policy_path`/`policy_sha256` as arguments and otherwise
only reads `predecessor`/`immediate_predecessor` attributes and frozen
protocol-identity constants that do not vary by policy version.
`verify_policy_v21` is a fresh copy, following the same rationale
`verify_policy_v16`-`v20` themselves documented.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v20 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v21.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v21.schema.json"
POLICY_V20_PATH = immediate_predecessor.POLICY_PATH
ADR_0135_PATH = "docs/decisions/0135-stage17-preflight-runtime-tool-symlink-identity.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v19.py",
    "collector": "tools/stage17_read_only_preflight_collector_v3.py",
    "state_journal": "tools/stage17_state_journal_v25.py",
}
"""``semantic_verifier`` deliberately keeps `v20`'s own value (`v20.py`
itself, since `v20` is where real archive-identity revalidation logic
last changed); action-time re-validation still loads `current_semantic`
= `v20`'s own functions unchanged. ``process_group_supervisor`` and
``openssh_snapshot_broker`` deliberately keep `v20`'s own inherited
values (`v3.py`/`v5.py`); this ADR does not touch process-group
supervision or OpenSSH consumption at all. ``state_journal`` moves to
`v25` (bound to policy `v29`) because `executor_v19.py`'s own `current_
journal` import moved there too, in lockstep with `cli_v11.py`'s own
journal_runtime import -- the same reachability-gap class ADR-0130
through ADR-0134 already established."""

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
verify_s17_ext_001_semantics_v21 = immediate_predecessor.verify_s17_ext_001_semantics_v20


def verify_policy_v21(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v20``, retargeted at v21.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v21's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v19/collector v3 instead of
    v18/v2, and the ``policy_v20``/``adr_0135`` predecessor keys instead
    of ``policy_v19``/``adr_0134``), because a Python function alias
    resolves free variables against the module it was *defined* in, not
    the module it is *accessed* through -- aliasing predecessor's function
    here would have silently kept validating against v20's own
    executor-v18/collector-v2 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v21")
    expected_predecessor = {
        "policy_v20": _binding_for(root, POLICY_V20_PATH),
        "adr_0135": _binding_for(root, ADR_0135_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v21 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v21 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v21 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v21 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v21 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v21 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v21 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v21 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v21 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v21 authority boundary drifted")
