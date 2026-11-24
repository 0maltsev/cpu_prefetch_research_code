#!/usr/bin/env python3
"""Stage 17 preflight-plan-policy authoring successor (ADR-0168, follow-up).

ADR-0168 changed `src/runner/stage17_fixed_action.cpp` again (the pilot
worker's run-field whitelist fix) and re-pinned the *operational*
admission chain's binding (`stage17_semantic_verifier_v46` ->
`_v47`, `tools/stage17_read_only_preflight_executor_v27.py` ->
`_v28.py`'s own successor retarget), but nobody ever authored a new
*preflight*-admission-policy generation referencing that new executor
-- the exact same class of gap `v28.py`'s own docstring already
describes for ADR-0156/`_v26.py`. Confirmed live: a fresh `S17-EXT-001`
admitted against (unpatched) policy v28 failed its own real, no-stand-
contact prospective action-readiness check with `bindings src__runner__
stage17_fixed_action_cpp file identity/size drifted`, because policy
v28's own frozen `IMPLEMENTATION_PATHS["executor"]` (`_v26.py`) only
monkey-patches `current_journal`'s ancestor `semantic` as far as
`stage17_semantic_verifier_v45` -- stale by two ADR-0168/ADR-0166
generations relative to the real, current `fixed_action.cpp` bytes.
`_v28.py`'s own successor retarget (to `_v47`) is the real fix, but
neither `_v27.py` nor `_v28.py` (the executor family) ever wrapped
`runtime_identity_paths()["executor"]` the way `_v26.py` did -- neither
needed to before now, since both were always imported purely for their
own side effect *alongside* `_v26.py`, which remained the actual
policy-approved identity through policy v28. Pointing this policy
directly at `_v28.py` without that wrapper fails `S17-EXT-001`'s own
real, no-stand-contact prospective-readiness check with `actual
executor source path does not match policy role` (confirmed live).
`tools/stage17_read_only_preflight_executor_v29.py` (the executor
family's own v29, a distinct successor from this file) adds exactly
that missing wrapper, mirroring `_v26.py`'s own technique; this policy
points `implementations.executor` at it. `implementations.state_journal`
deliberately stays `_v36.py` -- `_v28.py`'s own executor file explicitly
keeps `current_journal` at `_v36.py` and only monkey-patches its
ancestor `semantic` binding, the same "third fix" its own docstring
documents; there is no new `state_journal` generation to point at here.

`verify_policy_v29` is a copy of `verify_policy_v28`'s body, not an
alias, for the exact reason every predecessor in this chain already
gives: a function's free variables resolve against the module that
defines it, not the module through which it is accessed. Every other
name is a plain, unaffected re-export.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v28 as immediate_predecessor
from stage17_semantic_verifier_v3 import _binding_for, SemanticAdmissionError


predecessor = immediate_predecessor.predecessor

POLICY_PATH = "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v29.json"
POLICY_SCHEMA_PATH = "config/schemas/stage17-read-only-preflight-evidence-admission-policy-v29.schema.json"
POLICY_V28_PATH = immediate_predecessor.POLICY_PATH
ADR_0168_PATH = "docs/decisions/0168-stage17-pilot-worker-run-field-whitelist.md"
EFFECTIVE_ACTION_PLAN_PATH = immediate_predecessor.EFFECTIVE_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_PATH = immediate_predecessor.SUCCESSOR_ACTION_PLAN_PATH
SUCCESSOR_ACTION_PLAN_SCHEMA_PATH = (
    immediate_predecessor.SUCCESSOR_ACTION_PLAN_SCHEMA_PATH
)
SCHEMA_PATHS = immediate_predecessor.SCHEMA_PATHS
IMPLEMENTATION_PATHS = {
    **immediate_predecessor.IMPLEMENTATION_PATHS,
    "executor": "tools/stage17_read_only_preflight_executor_v29.py",
}
"""``state_journal`` deliberately keeps `v28`'s own value (`_v36.py`)
unchanged -- `_v28.py` (the executor) already keeps `current_journal`
at `_v36.py` and only monkey-patches its ancestor `semantic` binding;
``semantic_verifier``, ``collector``, ``process_group_supervisor``, and
``openssh_snapshot_broker`` deliberately keep their inherited values
unchanged -- this fix does not touch any of those, only which executor
source file `S17-EXT-001`'s own frozen snapshot expects to be loaded at
real action time."""

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
verify_s17_ext_001_semantics_v29 = immediate_predecessor.verify_s17_ext_001_semantics_v28


def verify_policy_v29(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_file_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    """Faithful copy of predecessor ``verify_policy_v28``, retargeted at v29.

    Every check is identical; only the module-level bindings this function
    resolves against differ (v29's own ``POLICY_SCHEMA_PATH``,
    ``IMPLEMENTATION_PATHS`` binding executor v28 instead of v26, and the
    ``policy_v28``/``adr_0168`` predecessor keys instead of
    ``policy_v27``/``adr_0156``), because a Python function alias
    resolves free variables against the module it was *defined* in, not
    the module it is *accessed* through -- aliasing predecessor's
    function here would have silently kept validating against v28's own
    executor-v26 expectations.
    """
    from stage17_semantic_verifier_v3 import _validate_schema
    _validate_schema(root, policy, POLICY_SCHEMA_PATH, "semantic policy v29")
    expected_predecessor = {
        "policy_v28": _binding_for(root, POLICY_V28_PATH),
        "adr_0168": _binding_for(root, ADR_0168_PATH),
        "graph_sha256": graph_sha256, "catalog_sha256": catalog_sha256,
        "genesis_file_sha256": genesis_file_sha256,
        "genesis_record_sha256": genesis_record_sha256,
        "resolution_schema_sha256": resolution_schema_sha256,
    }
    if policy.get("predecessor") != expected_predecessor:
        raise SemanticAdmissionError("semantic policy v29 predecessor binding drifted")
    if policy.get("schema_bindings") != [_binding_for(root, item) for item in SCHEMA_PATHS]:
        raise SemanticAdmissionError("semantic policy v29 schema binding drifted")
    if policy.get("fixed_action_plan") != _binding_for(root, EFFECTIVE_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v29 effective action plan drifted")
    if policy.get("successor_action_plan") != _binding_for(root, SUCCESSOR_ACTION_PLAN_PATH):
        raise SemanticAdmissionError("semantic policy v29 successor action plan drifted")
    if policy.get("operational_contract") != _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"):
        raise SemanticAdmissionError("semantic policy v29 operational contract drifted")
    if policy.get("implementations") != {
        name: _binding_for(root, path) for name, path in IMPLEMENTATION_PATHS.items()
    }:
        raise SemanticAdmissionError("semantic policy v29 runtime closure drifted")
    expected_operational_implementations = {
        "semantic_admission": _binding_for(root, "tools/stage17_operational_semantics_v1.py"),
        "phase_controller": _binding_for(root, "tools/stage17_phase_controller_v1.py"),
        "exit_state_machine": _binding_for(root, "tools/stage17_exit_state_machine_v1.py"),
        "pid_namespace_supervisor": _binding_for(root, "tools/stage17_process_group_supervisor_v3.py"),
    }
    if policy.get("operational_implementations") != expected_operational_implementations:
        raise SemanticAdmissionError("semantic policy v29 operational runtime drifted")
    expected_operational_definitions = {
        "external_contract": _binding_for(root, "config/stage17/stage17-operational-input-external-contract-v1.json"),
        "fixed_phase_actions": _binding_for(root, "config/stage17/stage17-fixed-phase-actions-v1.json"),
        "phase18_readiness_template": _binding_for(root, "config/stage17/phase18-readiness-template-v1.json"),
        "phase18_authorization_draft": _binding_for(root, "config/stage17/phase18-authorization-draft-v1.json"),
    }
    if policy.get("operational_definitions") != expected_operational_definitions:
        raise SemanticAdmissionError("semantic policy v29 operational definitions drifted")
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
        raise SemanticAdmissionError("semantic policy v29 complete registry drifted")
    if policy.get("synthetic_bypass_available") is not False or policy.get("stage18_authority") is not False:
        raise SemanticAdmissionError("semantic policy v29 authority boundary drifted")


# `stage17_semantic_verifier_v39.py`'s own `_verify_ext001` -- frozen,
# never touched since ADR-0156/0157/0158 -- calls `preflight.verify_
# policy_v27(...)` and `preflight.verify_s17_ext_001_semantics_v27(...)`
# by these exact, hardcoded attribute names, not just `preflight.POLICY_
# PATH`. Whichever module is monkey-patched in as `v39.preflight` must
# keep exposing those same names. Both remain correct as plain aliases
# for the same reason every predecessor in this chain already gives.
verify_policy_v27 = verify_policy_v29
verify_s17_ext_001_semantics_v27 = verify_s17_ext_001_semantics_v29
