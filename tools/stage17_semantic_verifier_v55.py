"""Source-bound seven-action release and diagnostic admission successor."""

from __future__ import annotations

import pathlib
import ast
from typing import Any, Mapping

import stage17_operational_semantics_v13 as operational_v13
import stage17_pilot_candidate_artifact_v9 as release_verifier
import stage17_semantic_verifier_v54 as predecessor


POLICY_PATH = predecessor.POLICY_PATH.parent / (
    "stage17-operational-evidence-admission-policy-v55.json"
)
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / (
    "stage17-operational-evidence-admission-policy-v55.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "55"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file

def discover_python_closure(root, roots):
    """Every repository-local Python import, including historical non-stage17 helpers."""
    pending = list(roots)
    found = set()
    while pending:
        name = pending.pop()
        relative = "tools/" + name + ".py"
        if relative in found:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise SemanticAdmissionError("runtime module is absent: " + relative)
        found.add(relative)
        for node in ast.walk(ast.parse(path.read_text(), filename=relative)):
            imports = ([item.name.split(".")[0] for item in node.names]
                       if isinstance(node, ast.Import) else
                       [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            for child in imports:
                if child.startswith("stage17_") or (root / "tools" / (child + ".py")).is_file():
                    pending.append(child)
    return found


pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v55(*, root, policy, graph_sha256, catalog_sha256,
                      genesis_record_sha256, resolution_schema_sha256):
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v55 schema rejection: {errors[0].message}"
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
        "tools/stage17_discovery_contract_v1.py",
        "tools/stage17_discovery_validation_v1.py",
        "tools/stage17_discovery_environment_v1.py",
        "tools/check_canonical.py",
        "tools/stage17_q15_session_controller_v17.py",
        "tools/stage17_output_registry_v9.py",
        "tools/stage17_phase_controller_v22.py",
        "tools/stage17_operational_cli_v15.py",
        "tools/stage17_fixed_action_executor_v8.py",
        "tools/stage17_pilot_candidate_artifact_v9.py",
        "tools/stage17_operational_semantics_v13.py",
        "tools/stage17_state_journal_v49.py",
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
        raise SemanticAdmissionError("policy v55 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v55 must bind executor v25 (via v26), not the superseded v24 entry point"
        )
    if "tools/stage17_read_only_preflight_executor_v25.py" not in discovered:
        raise SemanticAdmissionError(
            "policy v55 must keep v25 reachable through v26's own re-export"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "config/stage17/stage17-fixed-phase-actions-v7.json",
        "config/schemas/stage17-discovery-plan-v1.schema.json",
        "config/schemas/stage17-discovery-retention-report-v1.schema.json",
        "config/schemas/stage17-fixed-phase-actions-v7.schema.json",
        "config/schemas/stage17-pilot-candidate-external-contract-v7.schema.json",
        "config/schemas/stage17-runtime-release-provenance-v7.schema.json",
        *("config/schemas/stage17-" + family + "-v5.schema.json" for family in (
            "fixed-action-request", "fixed-action-context", "phase-action-authorization",
            "phase-action-result", "phase-action-attempt", "phase-action-failure", "phase-action-completion")),
        "tools/stage17_phase_controller_v14.py",
        "tools/stage17_q15_session_controller_v12.py",
        "tools/stage17_phase_controller_v15.py",
        "tools/stage17_fixed_action_executor_v5.py",
        "tools/stage17_read_only_preflight_executor_v26.py",
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v28.json",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v55 must pin the ADR-0157 preflight-plan-policy follow-up "
            "entrypoints"
        )
    cpp_binding = policy["bindings"].get("src__runner__stage17_fixed_action_cpp")
    if cpp_binding is None or cpp_binding["path"] != "src/runner/stage17_fixed_action.cpp":
        raise SemanticAdmissionError(
            "policy v55 must pin src/runner/stage17_fixed_action.cpp"
        )


def verify_policy_v14(**arguments):
    verify_policy_v55(**arguments)


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
        context = operational_v13.verify_manifest_v13(
            repository_root=root, manifest_path=path,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
            pinned_repository_bytes=pinned,
        )
    except operational_v13.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    return {"authorization": None, "context": context}


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_s17_ext_006` (`v40`), changed
    only to read `artifact_locator` instead of the stale `contract_path`
    field no real v2-schema receipt carries (ADR-0155). Every other
    check is byte-identical to the predecessor.
    """
    if len(receipt_documents) != 1 or pilot_archive is None or pilot_sidecar is None:
        raise SemanticAdmissionError("EXT006 requires exact archive/sidecar bytes")
    receipt = receipt_documents[0]
    if (receipt.get("verifier_id"), receipt.get("verifier_version")) != (
        release_verifier.VERIFIER_ID, release_verifier.VERIFIER_VERSION
    ):
        raise SemanticAdmissionError("EXT006 verifier identity drifted")
    contract_path = root / str(receipt.get("artifact_locator", ""))
    try:
        context = release_verifier.verify_pilot_candidate_artifact_v9(
            repository_root=root, contract_path=contract_path,
            archive=pilot_archive, sidecar=pilot_sidecar,
        )
    except release_verifier.ArtifactError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    ext3 = admitted_resolutions.get("S17-EXT-003")
    if ext3 is None or not isinstance(ext3.semantic_context, dict):
        raise SemanticAdmissionError("EXT006 lacks owner-accepted runtime")
    release = ext3.semantic_context.get("release")
    if release is None:
        raise SemanticAdmissionError("EXT003 clean-release context is absent")
    if (context.worker_size_bytes, context.worker_sha256, context.worker_role,
        context.runtime_profile, context.supported_actions,
        context.synthetic_test_only) != (
            release.worker_size_bytes, release.worker_sha256, release.worker_role,
            release.runtime_profile, release.supported_actions,
            release.synthetic_test_only,
        ):
        raise SemanticAdmissionError("EXT006 archive worker differs from EXT002/003")
    if context.synthetic_test_only is not allow_synthetic:
        raise SemanticAdmissionError("EXT006 verified classification drifted")
    return {"authorization": None, "context": {
        "archive_locator": str(context.archive_locator),
        "archive_size_bytes": context.archive_size_bytes,
        "archive_sha256": context.archive_sha256,
        "sidecar_locator": str(context.sidecar_locator),
        "sidecar_size_bytes": context.sidecar_size_bytes,
        "sidecar_sha256": context.sidecar_sha256,
        "manifest_member_path": context.manifest_member_path,
        "manifest_size_bytes": context.manifest_size_bytes,
        "manifest_sha256": context.manifest_sha256,
        "source_revision": context.source_revision,
        "release_artifact_path": str(release.worker_path),
        "release_artifact_member_path": context.worker_member_path,
        "release_artifact_size_bytes": context.worker_size_bytes,
        "release_artifact_sha256": context.worker_sha256,
        "release_artifact_role": context.worker_role,
        "runtime_profile": context.runtime_profile,
        "supported_actions": list(context.supported_actions),
        "bundle_profile": context.bundle_profile,
        "synthetic_test_only": context.synthetic_test_only,
        "sha256s_sha256": context.sha256s_sha256,
        "sbom_sha256": context.sbom_sha256,
        "inventory_sha256": context.inventory_sha256,
    }}

def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id in {"S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-007"}:
        return verify_operational_manifest_v11(input_id=input_id, **arguments)
    if input_id == "S17-EXT-006" and any(
            receipt.get("verifier_version") == release_verifier.VERIFIER_VERSION
            for receipt in arguments.get("receipt_documents", [])):
        return verify_s17_ext_006(**arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
