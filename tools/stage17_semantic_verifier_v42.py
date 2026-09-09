#!/usr/bin/env python3
"""Stage 17 registry successor for the fixed-action process-supervisor fix
(ADR-0156).

No `S17-EXT-00N` manifest/schema semantics change at all: `verify_input`'s
dispatch (`S17-EXT-004`/`S17-EXT-006` special cases, everything else
delegated to `predecessor`) is byte-identical to `v41`'s. This file exists
because `verify_policy_v41` (defined here in `v41.py`, reached from
`S17-EXT-001`'s handler via `semantic.verify_policy_v14`, a module
attribute the journal-runtime chain monkey-patches onto its own
ancestors -- see `stage17_state_journal_v36.py`) closes over `v41`'s own
`VERIFIER_VERSION`/`POLICY_SCHEMA` and a `required`/`required_dynamic_
action_bindings` set naming `v41`'s own current entry points. A fresh
journal admitting `S17-EXT-001` against a `v42`-numbered policy document
needs those checks to expect "42" and the real, current fixed-action
entry points (`stage17_phase_controller_v15.py`, reachable once `stage17_
operational_cli_v11.py`'s import moves there, and `stage17_fixed_action_
executor_v5.py`, its own new `executor` binding) -- not `v41`'s frozen
expectations. `verify_policy_v41`'s own body is otherwise copied verbatim
(same schema-drift/graph-binding/closure-completeness checks); only the
version string and the two required-file sets grow by one entry each,
exactly as `v41.py` grew them by one relative to `v40.py` for `_v25.py`.

`stage17_fixed_action_executor_v4.py`/`stage17_phase_controller_v14.py`
staying reachable in the closure remains expected, not a drift signal,
for the same reason the predecessor's own comment already gives: each
new fixed-action/phase-controller successor imports its immediate
predecessor to re-export everything but the one thing it changed, so
every older generation legitimately coexists.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_semantic_verifier_v41 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v42.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v42.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "42"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
verify_operational_manifest_v8 = predecessor.verify_operational_manifest_v8
verify_s17_ext_006 = predecessor.verify_s17_ext_006


def verify_policy_v42(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v42 schema rejection: {errors[0].message}"
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
        "tools/stage17_read_only_preflight_executor_v25.py",
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
        raise SemanticAdmissionError("policy v42 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v42 must bind executor v25, not the superseded v24 entry point"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "tools/stage17_phase_controller_v14.py",
        "tools/stage17_q15_session_controller_v12.py",
        "tools/stage17_phase_controller_v15.py",
        "tools/stage17_fixed_action_executor_v5.py",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v42 must pin the ADR-0156 kernel-thread-tolerant "
            "fixed-action entrypoints"
        )
    # Every module generation older than what this policy's own
    # IMPLEMENTATION_PATHS binds legitimately remains reachable too: each
    # new successor imports its own immediate predecessor to re-export
    # everything but the one thing it changed. Their presence in the
    # discovered closure is expected, not a drift signal -- the same
    # coexistence already documented for phase_controller v8/v9/v14/v15,
    # fixed_action_executor v2/v3/v4/v5, pilot_candidate_artifact
    # v4/v5/v6/v7, and process_group_supervisor v2/v3.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v42(**arguments)


# `verify_input` never references `verify_policy_v14`/`verify_policy_v42`
# (only `S17-EXT-001`'s handler, reached via the monkey-patched `semantic`
# attribute, does) and its own EXT-004/EXT-006 dispatch is unchanged, so
# it is a plain, correct re-export -- no free-variable issue to redefine
# around, unlike `verify_policy_v42` above.
verify_input = predecessor.verify_input
