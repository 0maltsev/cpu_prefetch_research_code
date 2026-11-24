#!/usr/bin/env python3
"""Stage 17 registry binding executor v14's journal-reachability fix (ADR-0130).

This is a new, additive file.  It does not modify
`stage17_semantic_verifier_v23.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v23.json` runtime-closure
hash for that file remains valid and unchanged.  `S17-EXT-001` resolution-
time semantics are delegated to
`stage17_read_only_preflight_semantic_verifier_v16.verify_s17_ext_001_semantics_v16`
(itself a deliberate alias of `v15`'s unchanged logic -- see that module's
docstring). The only real change here is which preflight-plan policy and
executor/journal generation the outer policy's `runtime_closure` requires:
`stage17_read_only_preflight_executor_v14.py` (fixing the real journal-
reachability defect in `executor_v13.py`'s own hardcoded `stage17_state_
journal_v17` import) and `stage17_state_journal_v20.py`, the same journal
generation `stage17_operational_cli_v11.py` itself uses (bumped from `v18`
to `v20` in lockstep once `cli_v11.py`'s own journal import moved during
this same ADR-0130 pass). `S17-EXT-002`
and `S17-EXT-006` dispatch are unchanged from `v23`; every other input's
dispatch is unchanged from `v21`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v16 as preflight
import stage17_semantic_verifier_v23 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v24.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v24.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "24"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v24(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v24 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v20.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v14.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v16.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v15.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v5.py",
        "tools/stage17_openssh_parent_snapshot_v2.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v24 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v13.py" in discovered:
        raise SemanticAdmissionError(
            "policy v24 must bind executor v14, not the superseded v13 entry point"
        )


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v24(**arguments)


def _verify_ext001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    policy = json.loads(policy_path.read_text())
    entry = next(
        item for item in policy["entries"] if item["input_id"] == "S17-EXT-001"
    )
    try:
        preflight.verify_policy_v16(
            root=root, policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v16(
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
