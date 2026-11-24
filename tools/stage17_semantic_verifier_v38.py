#!/usr/bin/env python3
"""Stage 17 registry completing the executor journal-reachability
lockstep this same ADR's own bindings-completion move requires
(ADR-0145).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v37.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v37.json` runtime-closure
hash for that file remains valid and unchanged. `S17-EXT-001` resolution-
time semantics are re-intercepted here (exactly as every prior ADR in
this chain has re-intercepted it at its own outer layer) and delegated to
`stage17_read_only_preflight_semantic_verifier_v26.verify_s17_ext_001_semantics_v26`
(a deliberate alias of `v25`'s unchanged logic -- see that module's
docstring). `S17-EXT-002` and every other input's dispatch is completely
unchanged, delegated to `predecessor.verify_input` (`v37`, which still
handles `S17-EXT-002` via `stage17_operational_semantics_v7.
verify_manifest_v7` -- ADR-0140's own fix, untouched by this follow-up).

Unlike ADR-0143/ADR-0144, this ADR folds the bindings-completion (pinning
`stage17_q15_session_controller_v10.py`/`v11.py`, `stage17_phase_
controller_v13.py`, and `stage17-q15-session-failure-v2.schema.json` --
a real Q15 session failure-retention schema fix) and the resulting
executor/journal reachability move (`stage17_read_only_preflight_
executor_v24.py`, `stage17_state_journal_v34.py`) into the same
generation, applying the ADR-0143/ADR-0144 lesson proactively rather
than discovering the reachability gap a generation later.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import stage17_read_only_preflight_semantic_verifier_v26 as preflight
import stage17_semantic_verifier_v37 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v38.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v38.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "38"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v38(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v38 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v34.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v24.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v5.py",
        "tools/stage17_read_only_preflight_collector_v3.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v26.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v6.py",
        "tools/stage17_operational_semantics_v7.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v38 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v23.py" in discovered:
        raise SemanticAdmissionError(
            "policy v38 must bind executor v24, not the superseded v23 entry point"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "tools/stage17_phase_controller_v13.py",
        "tools/stage17_q15_session_controller_v10.py",
        "tools/stage17_q15_session_controller_v11.py",
        "config/schemas/stage17-q15-session-failure-v2.schema.json",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v38 must pin the ADR-0145 dynamic-action controller "
            "entrypoints and Q15 session failure-retention schema fix"
        )
    # Every module generation older than what this policy's own
    # IMPLEMENTATION_PATHS binds legitimately remains reachable too: each
    # new successor imports its own immediate predecessor to re-export
    # everything but the one thing it changed. Their presence in the
    # discovered closure is expected, not a drift signal -- the same
    # coexistence already documented for phase_controller v8/v9, pilot_
    # candidate_artifact v4/v5, and process_group_supervisor v2/v3.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v38(**arguments)


def _verify_ext001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    policy = json.loads(policy_path.read_text())
    entry = next(
        item for item in policy["entries"] if item["input_id"] == "S17-EXT-001"
    )
    try:
        preflight.verify_policy_v26(
            root=root, policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v26(
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
