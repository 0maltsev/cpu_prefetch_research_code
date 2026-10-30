"""Versioned calibration mapping, schema, and controller closure."""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import stage17_operational_semantics_v12 as operational_v12
import stage17_semantic_verifier_v53 as predecessor


POLICY_PATH = predecessor.POLICY_PATH.parent / (
    "stage17-operational-evidence-admission-policy-v54.json"
)
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / (
    "stage17-operational-evidence-admission-policy-v54.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "54"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v54(*, root, policy, graph_sha256, catalog_sha256,
                      genesis_record_sha256, resolution_schema_sha256):
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v54 schema rejection: {errors[0].message}"
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
        "tools/stage17_output_registry_v8.py",
        "tools/stage17_phase_controller_v21.py",
        "tools/stage17_operational_cli_v14.py",
        "tools/stage17_state_journal_v48.py",
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
        "tools/stage17_operational_semantics_v12.py",
        "tools/stage17_phase_controller_v15.py",
        "tools/stage17_fixed_action_executor_v5.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v54 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v54 must bind executor v25 (via v26), not the superseded v24 entry point"
        )
    if "tools/stage17_read_only_preflight_executor_v25.py" not in discovered:
        raise SemanticAdmissionError(
            "policy v54 must keep v25 reachable through v26's own re-export"
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
            "policy v54 must pin the ADR-0157 preflight-plan-policy follow-up "
            "entrypoints"
        )
    cpp_binding = policy["bindings"].get("src__runner__stage17_fixed_action_cpp")
    if cpp_binding is None or cpp_binding["path"] != "src/runner/stage17_fixed_action.cpp":
        raise SemanticAdmissionError(
            "policy v54 must pin src/runner/stage17_fixed_action.cpp"
        )


def verify_policy_v14(**arguments):
    verify_policy_v54(**arguments)


def verify_operational_manifest_v11(
    *, input_id: str, root: pathlib.Path,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], allow_synthetic: bool,
    policy: dict[str, Any], **_: Any,
) -> dict[str, Any]:
    """Faithful copy of `stage17_semantic_verifier_v41.py`'s
    `verify_operational_manifest_v8`, retargeted to call `stage17_
    operational_semantics_v11.verify_manifest_v11` instead of `v8`'s own
    `verify_manifest_v8`. Every other check is byte-identical to the
    predecessor.
    """
    import json

    candidates = [path for path, document in repository_documents
                  if document.get("schema_version") ==
                  "cpu-prefetch-stage17-operational-input-manifest/4"]
    for receipt in receipt_documents:
        locator = receipt.get("artifact_locator")
        if not isinstance(locator, str):
            continue
        path = pathlib.Path(locator)
        try:
            document = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and document.get("schema_version") == \
                "cpu-prefetch-stage17-operational-input-manifest/4":
            candidates.append(path)
    if len(candidates) != 1:
        raise SemanticAdmissionError(f"{input_id} requires exactly one v4 manifest")
    path = candidates[0]
    pinned: dict[str, bytes] = {}
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            _, payload = pinned_binding_bytes(root, binding, f"{group} {key}")
            pinned[binding["path"]] = payload
    try:
        context = operational_v12.verify_manifest_v11(
            repository_root=root, manifest_path=path,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
            pinned_repository_bytes=pinned,
        )
    except operational_v12.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    return {"authorization": None, "context": context}


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id in {"S17-EXT-004", "S17-EXT-007"}:
        return verify_operational_manifest_v11(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
