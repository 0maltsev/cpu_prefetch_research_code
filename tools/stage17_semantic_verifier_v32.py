#!/usr/bin/env python3
"""Stage 17 registry completing the S17-EXT-002 manifest schema-binding
ADR-0136 left incomplete (ADR-0138).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v31.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v31.json` runtime-closure
hash for that file remains valid and unchanged. No `verify_input` logic
changes at all -- `S17-EXT-001` and `S17-EXT-002` (and every other input)
dispatch exactly as `v31` already did, delegated unchanged. The only
change is which policy generation `POLICY_PATH` points at: `v32` pins the
three real preflight record schemas
(`stage17-read-only-preflight-attempt-v10.schema.json`,
`-observation-receipt-v7.schema.json`, `-completion-v7.schema.json`)
`stage17_operational_semantics_v6.ROLE_SCHEMA_v6` has required since
ADR-0136, but which `v30`/`v31`'s own `bindings` never pinned -- found via
the first real `admit-resolution --input-id S17-EXT-002` attempt ever to
reach that check (a real, local, no-stand-contact investigation; S17-EXT-002
admission is pure evidence recording).
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_semantic_verifier_v31 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v32.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v32.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "32"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes

REQUIRED_EXT002_RECORD_SCHEMAS = frozenset({
    "config/schemas/stage17-read-only-preflight-attempt-v10.schema.json",
    "config/schemas/stage17-read-only-preflight-observation-receipt-v7.schema.json",
    "config/schemas/stage17-read-only-preflight-completion-v7.schema.json",
})


def verify_policy_v32(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v32 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v27.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v20.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v5.py",
        "tools/stage17_read_only_preflight_collector_v3.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v22.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v6.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v32 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v19.py" in discovered:
        raise SemanticAdmissionError(
            "policy v32 must bind executor v20, not the superseded v19 entry point"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    if not REQUIRED_EXT002_RECORD_SCHEMAS.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v32 must pin the ADR-0136 S17-EXT-002 preflight record schemas"
        )
    # Every module generation older than what this policy's own
    # IMPLEMENTATION_PATHS binds legitimately remains reachable too: each
    # new successor imports its own immediate predecessor to re-export
    # everything but the one thing it changed. Their presence in the
    # discovered closure is expected, not a drift signal -- the same
    # coexistence already documented for phase_controller v8/v9, pilot_
    # candidate_artifact v4/v5, and process_group_supervisor v2/v3.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v32(**arguments)


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    return predecessor.verify_input(input_id=input_id, **arguments)
