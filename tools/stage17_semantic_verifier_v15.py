#!/usr/bin/env python3
"""Stage 17 semantic registry with post-preflight controller compatibility."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator

import stage17_semantic_verifier_v14 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v15.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v15.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "15"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v15(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    schema = json.loads((root / POLICY_SCHEMA).read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v15 schema rejection: {errors[0].message}"
        )
    if (policy["graph_sha256"] != graph_sha256
            or policy["catalog_sha256"] != catalog_sha256
            or policy["genesis_record_sha256"] != genesis_record_sha256
            or policy["resolution_schema_sha256"] != resolution_schema_sha256):
        raise SemanticAdmissionError("policy graph/catalog/genesis binding drifted")
    if policy["predecessor_status"] != \
            "SUPERSEDED_POST_PREFLIGHT_CONTROLLER_INCOMPATIBLE":
        raise SemanticAdmissionError("policy v14 predecessor status is absent")
    entries = policy["entries"]
    expected = [
        {
            "input_id": input_id,
            "status": "IMPLEMENTED",
            "verifier_id": VERIFIER_ID,
            "verifier_version": VERIFIER_VERSION,
        }
        for input_id in INPUT_IDS
    ]
    if entries != expected:
        raise SemanticAdmissionError("policy does not implement exactly ten inputs")
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            pinned_binding_bytes(root, binding, f"{group} {key}")
    roots = tuple(policy["runtime_import_roots"])
    discovered = discover_python_closure(root, roots)
    recorded = {
        item["path"] for item in policy["runtime_closure"].values()
    }
    if discovered != recorded:
        raise SemanticAdmissionError("policy Python runtime closure is incomplete/expanded")
    required = {
        "tools/stage17_state_journal_v13.py",
        "tools/stage17_phase_controller_v5.py",
        "tools/stage17_q15_session_controller_v3.py",
        "tools/stage17_operational_cli_v7.py",
        "tools/stage17_read_only_preflight_executor_v9.py",
    }
    if not required.issubset(recorded):
        raise SemanticAdmissionError("policy v15 current runtime closure is incomplete")


def verify_policy_v14(**arguments: Any) -> None:
    """Compatibility entrypoint required by the immutable journal-v12 body.

    The name is inherited from that predecessor; the implementation validates
    policy v15 and never accepts policy v14 as the current production policy.
    """
    verify_policy_v15(**arguments)


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id == "S17-EXT-001":
        return predecessor.verify_s17_ext_001(input_id=input_id, **arguments)
    if input_id == "S17-EXT-006":
        return predecessor.verify_s17_ext_006(**arguments)
    if input_id in {
        "S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-005",
        "S17-EXT-007", "S17-EXT-008", "S17-EXT-009", "S17-EXT-010",
    }:
        return predecessor.verify_operational_manifest(
            input_id=input_id, **arguments
        )
    raise SemanticAdmissionError(f"no semantic verifier registered for {input_id}")
