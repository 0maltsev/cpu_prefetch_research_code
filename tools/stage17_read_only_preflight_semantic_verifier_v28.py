#!/usr/bin/env python3
"""Stage 17 preflight-plan-policy authoring successor (ADR-0156, follow-up).

`author-ext001` embeds a snapshot of this policy's own `implementations`
into `S17-EXT-001`'s `semantic_context`, and the real fixed-action
executor path (via `evaluate_s17_ext_001_action_readiness_v20` ->
`_verify_loaded_runtime`) re-checks, on every real preflight/action run,
that the *actually loaded* `executor`/`state_journal` source file
basenames still match that frozen snapshot. `v27.py`'s own
`IMPLEMENTATION_PATHS` pins `executor` = `tools/stage17_read_only_
preflight_executor_v25.py` and `state_journal` = `tools/stage17_state_
journal_v35.py` -- the exact files ADR-0156's own `_v26.py`/`_v36.py`
fix (see those files' own docstrings) replaces at the operational-
admission-policy layer. Missing this successor is a real, first-time-
observed gap: standv2-21's own `S17-EXT-001` was authored against `v27`
(before this file existed), then its preflight capture failed twice --
first on `policy-v41`'s stale `cli_v11.py` binding (fixed by patching
`_v26.py`/`_v36.py` into the admission root), then on *this* policy's
own frozen `executor`/`state_journal` basenames no longer matching the
now-patched `_v26.py`/`_v36.py` -- an unresolvable deadlock for that one
already-admitted `S17-EXT-001`, requiring a fresh journal authored
*after* this file exists.

`verify_policy_v28` is a copy of `verify_policy_v27`'s body, not an
alias, for the exact reason `v27.py`'s own docstring already gives for
why *it* isn't an alias of `v26`'s: a function's free variables resolve
against the module that defines it, not the module through which it is
accessed. Every other name is a plain, unaffected re-export.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v27 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v28.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v28.schema.json"
POLICY_V27_PATH = immediate_predecessor.POLICY_PATH
ADR_0156_PATH = "docs/decisions/0156-stage17-fixed-action-kernel-thread-tolerance.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v26.py",
    "state_journal": "tools/stage17_state_journal_v36.py",
}
"""``semantic_verifier`` deliberately keeps `v20`'s own value unchanged
(action-time re-validation still loads `current_semantic` = `v20`'s own
functions unchanged); ``collector``, ``process_group_supervisor``, and
``openssh_snapshot_broker`` deliberately keep `v27`'s own inherited
values (`v3`/`v3`/`v5`); this fix does not touch the collector, process-
group supervision, or OpenSSH consumption at all -- only which executor/
state-journal source files `S17-EXT-001`'s own frozen snapshot expects
to be loaded at real action time."""

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
verify_s17_ext_001_semantics_v28 = immediate_predecessor.verify_s17_ext_001_semantics_v27


def verify_policy_v28(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v27``, retargeted at v28.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v28's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v26/state_journal v36
    instead of v25/v35, and the ``policy_v27``/``adr_0156`` predecessor
    keys instead of ``policy_v26``/``adr_0146``), because a Python
    function alias resolves free variables against the module it was
    *defined* in, not the module it is *accessed* through -- aliasing
    predecessor's function here would have silently kept validating
    against v27's own executor-v25/state_journal-v35 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v28")
    expected_predecessor = {
        "policy_v27": _binding_for(root, POLICY_V27_PATH),
        "adr_0156": _binding_for(root, ADR_0156_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v28 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v28 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v28 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v28 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v28 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v28 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v28 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v28 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v28 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v28 authority boundary drifted")
