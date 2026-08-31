#!/usr/bin/env python3
"""Stage 17 registry with the D-123 action-revalidation successor."""

from __future__ import annotations

import json
import pathlib
from typing import Any

from jsonschema import Draft202012Validator

import stage17_read_only_preflight_semantic_verifier_v14 as preflight
import stage17_semantic_verifier_v17 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v18.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v18.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "18"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v18(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v18 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v16.py",
        "tools/stage17_phase_controller_v8.py",
        "tools/stage17_operational_cli_v10.py",
        "tools/stage17_read_only_preflight_executor_v12.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v14.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v13.py",
        "tools/stage17_openssh_parent_snapshot_v2.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v18 runtime closure is incomplete")


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v18(**arguments)


def _verify_ext001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    policy = json.loads(policy_path.read_text())
    entry = next(
        item for item in policy["entries"] if item["input_id"] == "S17-EXT-001"
    )
    try:
        preflight.verify_policy_v14(
            root=root, policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v14(
            **{key: value for key, value in arguments.items() if key != "policy"},
            policy=policy, policy_path=policy_path,
            policy_sha256=sha_file(policy_path), policy_entry=entry,
        )
    except Exception as exception:
        raise SemanticAdmissionError(str(exception)) from exception


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id == "S17-EXT-001":
        return _verify_ext001(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
