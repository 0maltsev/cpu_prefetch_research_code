#!/usr/bin/env python3
"""Stage 17 registry completing the phase-controller/Q15-session-
controller entrypoint bindings ADR-0142's own fix left untracked
(ADR-0143).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v35.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v35.json` runtime-closure
hash for that file remains valid and unchanged. No `verify_input` logic
changes at all -- `S17-EXT-001`, `S17-EXT-002`, and every other input
dispatch exactly as `v35` already did, delegated unchanged. The only
change is which policy generation `POLICY_PATH` points at: `v36` pins
`tools/stage17_phase_controller_v11.py`, `tools/stage17_q15_session_
controller_v7.py`, and `tools/stage17_q15_session_controller_v8.py` --
files ADR-0142 added to the live tree but never pinned as policy
bindings, because none of them are reachable via a real Python `import`
statement from any of policy v35's `runtime_import_roots`
(`stage17_phase_controller_v9` and `stage17_q15_session_controller_v6`
are still the literal roots; `v11`/`v7`/`v8` only became reachable
transitively through `stage17_operational_cli_v11`'s own updated
`import stage17_phase_controller_v11 as controller` -- and even then,
`stage17_q15_session_controller_v7.py`/`v8.py` are never imported by
anything at all, since they are standalone CLI entrypoints invoked
directly from the shell, not library modules). Consequence: no sealed
bundle has ever shipped these files, so the first real attempt to run
`stage17_q15_session_controller_v8.py` against a real, bundle-sourced
admission root failed with a plain `FileNotFoundError` -- the file
simply was not present in the admission root's own `tools/` directory.
Found via that real, safe (no stand contact -- `python3` failed to even
open the entrypoint file) second Q15-R attempt.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_semantic_verifier_v35 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v36.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v36.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "36"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes

REQUIRED_DYNAMIC_ACTION_ENTRYPOINT_BINDINGS = frozenset({
    "tools/stage17_phase_controller_v11.py",
    "tools/stage17_q15_session_controller_v7.py",
    "tools/stage17_q15_session_controller_v8.py",
})


def verify_policy_v36(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v36 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v32.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v22.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v5.py",
        "tools/stage17_read_only_preflight_collector_v3.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v24.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v6.py",
        "tools/stage17_operational_semantics_v7.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v36 runtime closure is incomplete")
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    if not REQUIRED_DYNAMIC_ACTION_ENTRYPOINT_BINDINGS.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v36 must pin the ADR-0142 dynamic-action controller "
            "entrypoints (stage17_phase_controller_v11.py, stage17_q15_"
            "session_controller_v7.py, stage17_q15_session_controller_v8.py)"
        )
    # Every module generation older than what this policy's own
    # IMPLEMENTATION_PATHS binds legitimately remains reachable too: each
    # new successor imports its own immediate predecessor to re-export
    # everything but the one thing it changed. Their presence in the
    # discovered closure is expected, not a drift signal -- the same
    # coexistence already documented for phase_controller v8/v9, pilot_
    # candidate_artifact v4/v5, and process_group_supervisor v2/v3.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v36(**arguments)


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    return predecessor.verify_input(input_id=input_id, **arguments)
