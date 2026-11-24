#!/usr/bin/env python3
"""Stage 17 registry successor fixing `S17-EXT-001`'s own admission-time
check against the preflight-plan-policy (ADR-0157, second follow-up).

`verify_input`'s `S17-EXT-001` branch is not handled by `v39.py`'s own
successors (`v40` through `v43`, this session's own `v42`/`v43`
included) at all -- it is intercepted once, terminally, inside `v39.py`
itself, via `_verify_ext001`, which reads `preflight.POLICY_PATH` and
calls `preflight.verify_policy_v27`/`preflight.verify_s17_ext_001_
semantics_v27`, where `preflight` is `v39.py`'s own hardcoded `import
stage17_read_only_preflight_semantic_verifier_v27 as preflight`.

`cli_v11.py`'s `author-ext001` (ADR-0157's own fix) now embeds `S17-
EXT-001`'s envelope `semantic_policy` field from `...policy-v28.json`,
but `_verify_ext001`'s own hardcoded `preflight` binding still expects
`...policy-v27.json` -- a third, independent hardcoded reference to the
preflight-plan-policy generation, missed by both ADR-0156 and ADR-0157's
first pass, and only reachable (hence only observable) once a journal
actually got as far as calling `admit-resolution --input-id S17-EXT-001`
against an admission root whose `author-ext001` had already moved to
`v28.json` -- which is exactly what burned `standv2-22`: `append_
resolution` writes the resolution record via exclusive create *before*
running this validation, so once it raised, that record was permanently
unrecoverable.

Fixed the same way `stage17_read_only_preflight_executor_v26.py` fixed
`current_journal`: monkey-patch `v39`'s own `preflight` module attribute
rather than redefining `_verify_ext001`/`verify_input`, since neither
function's own logic needs to change -- only which sibling module
`preflight` refers to, and both already access it purely by attribute,
never by importing individual names from it.
"""

from __future__ import annotations

import stage17_read_only_preflight_semantic_verifier_v28 as preflight
import stage17_semantic_verifier_v39 as v39
import stage17_semantic_verifier_v43 as predecessor


v39.preflight = preflight

POLICY_PATH = predecessor.POLICY_PATH.parent / (
    "stage17-operational-evidence-admission-policy-v44.json"
)
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / (
    "stage17-operational-evidence-admission-policy-v44.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "44"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
verify_input = predecessor.verify_input


def verify_policy_v44(*, root, policy, graph_sha256, catalog_sha256,
                      genesis_record_sha256, resolution_schema_sha256):
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v44 schema rejection: {errors[0].message}"
        )
    if (policy["graph_sha256"] != graph_sha256
            or policy["catalog_sha256"] != catalog_sha256
            or policy["genesis_record_sha256"] != genesis_record_sha256
            or policy["resolution_schema_sha256"] != resolution_schema_sha256):
        raise SemanticAdmissionError("policy graph/catalog/genesis binding drifted")
    expected = [
        {"input_id": item, "status": "IMPLEMENTED",
         "verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}
        for item in INPUT_IDS
    ]
    if policy["entries"] != expected:
        raise SemanticAdmissionError("policy does not implement exactly ten inputs")
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            pinned_binding_bytes(root, binding, f"{group} {key}")
    discovered = discover_python_closure(
        root, tuple(policy["runtime_import_roots"])
    )
    if discovered != {item["path"] for item in policy["runtime_closure"].values()}:
        raise SemanticAdmissionError(
            "policy Python runtime closure is incomplete/expanded"
        )
    required = {
        "tools/stage17_state_journal_v35.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v26.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v5.py",
        "tools/stage17_read_only_preflight_collector_v3.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v27.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_pilot_candidate_artifact_v7.py",
        "tools/stage17_operational_semantics_v6.py",
        "tools/stage17_operational_semantics_v7.py",
        "tools/stage17_operational_semantics_v8.py",
        "tools/stage17_phase_controller_v15.py",
        "tools/stage17_fixed_action_executor_v5.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v44 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v44 must bind executor v25 (via v26), not the superseded v24 entry point"
        )
    if "tools/stage17_read_only_preflight_executor_v25.py" not in discovered:
        raise SemanticAdmissionError(
            "policy v44 must keep v25 reachable through v26's own re-export"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "tools/stage17_phase_controller_v14.py",
        "tools/stage17_q15_session_controller_v12.py",
        "tools/stage17_phase_controller_v15.py",
        "tools/stage17_fixed_action_executor_v5.py",
        "tools/stage17_read_only_preflight_executor_v26.py",
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v28.json",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v44 must pin the ADR-0157 preflight-plan-policy follow-up "
            "entrypoints"
        )
    if v39.preflight is not preflight:
        raise SemanticAdmissionError(
            "S17-EXT-001's own preflight-plan-policy binding (v39.preflight) "
            "must be v28, not v27"
        )


def verify_policy_v14(**arguments):
    verify_policy_v44(**arguments)
