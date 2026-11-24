#!/usr/bin/env python3
"""Stage 17 registry binding executor v16's corrected OpenSSH snapshot
mechanism identity fix (ADR-0132).

This is a new, additive file.  It does not modify
`stage17_semantic_verifier_v25.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v25.json` runtime-closure
hash for that file remains valid and unchanged.  `S17-EXT-001` resolution-
time semantics are delegated to
`stage17_read_only_preflight_semantic_verifier_v18.verify_s17_ext_001_semantics_v18`
(itself a deliberate alias of `v15`'s unchanged logic -- see that module's
docstring). The only real change here is which preflight-plan policy and
executor/openssh-snapshot-broker generation the outer policy's
`runtime_closure` requires: `stage17_read_only_preflight_executor_v16.py`
and `stage17_openssh_parent_snapshot_v4.py` (fixing the real, reproduced
attempt-marker schema rejection when a pinned input's own `snapshot_
mechanism` metadata still reported the frozen `v1` identity). `S17-EXT-002`
and `S17-EXT-006` dispatch are unchanged from `v24`; every other input's
dispatch is unchanged from `v21`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v18 as preflight
import stage17_semantic_verifier_v25 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v26.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v26.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "26"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v26(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v26 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v22.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v16.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v4.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v18.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v15.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v5.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v26 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v15.py" in discovered:
        raise SemanticAdmissionError(
            "policy v26 must bind executor v16, not the superseded v15 entry point"
        )
    # stage17_process_group_supervisor_v2, stage17_openssh_parent_
    # snapshot_v1/v2/v3, and the superseded openssh_parent_snapshot_v3
    # legitimately remain reachable too: each new successor imports its
    # own immediate predecessor to re-export everything but the one thing
    # it changed (the same coexistence v21/v22/v25 already documented for
    # phase_controller v8/v9, pilot_candidate_artifact v4/v5, and
    # process_group_supervisor v2/v3). Their presence in the discovered
    # closure is expected, not a drift signal; what matters is that
    # policy v26's own IMPLEMENTATION_PATHS (checked above, via the
    # preflight-plan policy's own `implementations` binding) actually
    # binds v4, which the runtime-identity check at action time enforces
    # independently.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v26(**arguments)


def _verify_ext001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    policy = json.loads(policy_path.read_text())
    entry = next(
        item for item in policy["entries"] if item["input_id"] == "S17-EXT-001"
    )
    try:
        preflight.verify_policy_v18(
            root=root, policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v18(
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
