#!/usr/bin/env python3
"""Stage 17 registry successor re-pinning `src/runner/stage17_fixed_
action.cpp`'s changed bytes (ADR-0170, Q15-R CPU-identity diagnostic).

No admission *logic* changes here -- `verify_input`, `_verify_ext001`,
and every other check `predecessor` (`v47`) already performs are
inherited unchanged. This generation exists solely because ADR-0170
added one `std::fprintf` diagnostic line to `src/runner/stage17_fixed_
action.cpp` in place again (the same single compiled worker source
file ADR-0159/v45, ADR-0166/v46, and ADR-0168/v47 already re-pinned),
and that file's bytes are individually pinned under
`policy["bindings"]["src__runner__stage17_fixed_action_cpp"]`.
`pinned_binding_bytes` already re-verifies every binding's bytes
generically on each admission; this successor's only job is to carry a
*policy* whose own `bindings` entry for that path reflects the file's
current, real hash rather than `v47`'s now-stale one.

`verify_policy_v48` is a faithful copy of `verify_policy_v47`'s body
(not an alias), for the exact reason every predecessor in this chain
already gives: its own `POLICY_SCHEMA`/`VERIFIER_VERSION` free
variables resolve against whichever module *defines* the function, not
the module it is accessed through -- aliasing `predecessor.verify_
policy_v47` here would have silently kept validating new policy
documents against `v47`'s own schema and verifier-version expectations.
Every other check is byte-identical to the predecessor; the file-path
requirement sets are unchanged because this edit adds no new tool
entry point and removes none.
"""

from __future__ import annotations

import stage17_semantic_verifier_v47 as predecessor


POLICY_PATH = predecessor.POLICY_PATH.parent / (
    "stage17-operational-evidence-admission-policy-v48.json"
)
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / (
    "stage17-operational-evidence-admission-policy-v48.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "48"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
verify_input = predecessor.verify_input


def verify_policy_v48(*, root, policy, graph_sha256, catalog_sha256,
                      genesis_record_sha256, resolution_schema_sha256):
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v48 schema rejection: {errors[0].message}"
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
        raise SemanticAdmissionError("policy v48 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v48 must bind executor v25 (via v26), not the superseded v24 entry point"
        )
    if "tools/stage17_read_only_preflight_executor_v25.py" not in discovered:
        raise SemanticAdmissionError(
            "policy v48 must keep v25 reachable through v26's own re-export"
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
            "policy v48 must pin the ADR-0157 preflight-plan-policy follow-up "
            "entrypoints"
        )
    cpp_binding = policy["bindings"].get("src__runner__stage17_fixed_action_cpp")
    if cpp_binding is None or cpp_binding["path"] != "src/runner/stage17_fixed_action.cpp":
        raise SemanticAdmissionError(
            "policy v48 must pin src/runner/stage17_fixed_action.cpp"
        )
