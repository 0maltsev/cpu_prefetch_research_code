#!/usr/bin/env python3
"""Current closed-world Stage 17 semantic admission registry (policy v10)."""

from __future__ import annotations

import ast
import hashlib
import json
import pathlib
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import stage17_operational_semantics_v2 as operational
import stage17_pilot_candidate_artifact_v2 as release_verifier
import stage17_semantic_verifier_v9 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v10.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v10.schema.json"
)
VERIFIER_ID = "STAGE17-SEMANTIC-ADMISSION-VERIFIER"
VERIFIER_VERSION = "10"
INPUT_IDS = tuple(f"S17-EXT-{index:03d}" for index in range(1, 11))
EXPECTED_RUNTIME_CLOSURE_PATHS = {
    "semantic_verifier": "tools/stage17_semantic_verifier_v10.py",
    "operational_semantics": "tools/stage17_operational_semantics_v2.py",
    "operational_semantics_predecessor": "tools/stage17_operational_semantics_v1.py",
    "pilot_candidate_verifier": "tools/stage17_pilot_candidate_artifact_v2.py",
    "pilot_candidate_verifier_predecessor": "tools/stage17_pilot_candidate_artifact.py",
    "ext001_predecessor_verifier": "tools/stage17_semantic_verifier_v9.py",
    "ext001_predecessor_verifier_v8": "tools/stage17_semantic_verifier_v8.py",
    "ext001_predecessor_verifier_v5": "tools/stage17_semantic_verifier_v5.py",
    "ext001_predecessor_verifier_v4": "tools/stage17_semantic_verifier_v4.py",
    "ext001_predecessor_verifier_v3": "tools/stage17_semantic_verifier_v3.py",
    "preflight_collector_v2": "tools/stage17_read_only_preflight_collector_v2.py",
    "preflight_collector_v1": "tools/stage17_read_only_preflight_collector_v1.py",
    "state_journal": "tools/stage17_state_journal_v7.py",
    "state_journal_base": "tools/stage17_state_journal.py",
    "phase_controller": "tools/stage17_phase_controller_v2.py",
    "fixed_action_executor": "tools/stage17_fixed_action_executor_v2.py",
    "snapshot_broker": "tools/stage17_openssh_parent_snapshot_v1.py",
    "process_group_supervisor": "tools/stage17_process_group_supervisor_v2.py",
    "worker_source": "src/runner/stage17_fixed_action.cpp",
    "worker_header": "include/cpu_prefetch/runner/stage17_fixed_action.hpp",
    "runner_core_source": "src/runner/runner.cpp",
    "runner_core_header": "include/cpu_prefetch/runner/runner.hpp",
    "runner_entrypoint": "tools/runner_main.cpp",
    "exit_state_machine": "tools/stage17_exit_state_machine_v2.py",
}
RUNTIME_IMPORT_ROOTS = (
    "stage17_semantic_verifier_v10",
    "stage17_state_journal_v7",
    "stage17_phase_controller_v2",
    "stage17_fixed_action_executor_v2",
    "stage17_exit_state_machine_v2",
    "stage17_pilot_candidate_artifact_v2",
)


class SemanticAdmissionError(ValueError):
    pass


def sha_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def verify_binding(root: pathlib.Path, binding: dict[str, Any], label: str) -> pathlib.Path:
    path = root / str(binding.get("path", ""))
    try:
        relative = path.resolve().relative_to(root.resolve())
    except (OSError, ValueError) as exception:
        raise SemanticAdmissionError(f"{label} leaves repository") from exception
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise SemanticAdmissionError(f"{label} is not a repository regular file")
    if (path.stat().st_size, sha_file(path)) != (binding.get("size_bytes"), binding.get("sha256")):
        raise SemanticAdmissionError(f"{label} bytes drifted")
    return path


def discover_stage17_python_closure(root: pathlib.Path) -> set[str]:
    pending = list(RUNTIME_IMPORT_ROOTS)
    discovered: set[str] = set()
    while pending:
        module = pending.pop()
        relative = f"tools/{module}.py"
        if relative in discovered:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise SemanticAdmissionError(f"loaded runtime module is absent: {relative}")
        discovered.add(relative)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exception:
            raise SemanticAdmissionError(
                f"loaded runtime module cannot be parsed: {relative}"
            ) from exception
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [item.name.split(".", 1)[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module.split(".", 1)[0]]
            for name in imported:
                candidate = root / "tools" / f"{name}.py"
                if name.startswith("stage17_") and candidate.is_file():
                    pending.append(name)
    return discovered


def verify_policy_v10(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    schema = json.loads((root / POLICY_SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(f"policy v10 schema rejection: {errors[0].message}")
    if policy["graph_sha256"] != graph_sha256 or policy["catalog_sha256"] != catalog_sha256:
        raise SemanticAdmissionError("policy graph/catalog binding drifted")
    if policy["genesis_record_sha256"] != genesis_record_sha256 or policy["resolution_schema_sha256"] != resolution_schema_sha256:
        raise SemanticAdmissionError("policy genesis/resolution binding drifted")
    for label, binding in policy["bindings"].items():
        verify_binding(root, binding, label)
    entries = policy["entries"]
    if tuple(item["input_id"] for item in entries) != INPUT_IDS or any(
        item["status"] != "IMPLEMENTED" or item["verifier_version"] != "10"
        for item in entries
    ):
        raise SemanticAdmissionError("policy does not implement the exact ten-input registry")
    closure = policy["runtime_closure"]
    declared_python_paths = {
        binding["path"] for binding in closure.values()
        if str(binding.get("path", "")).startswith("tools/stage17_")
        and str(binding.get("path", "")).endswith(".py")
    }
    if (tuple(policy["runtime_closure_keys"])
            != tuple(EXPECTED_RUNTIME_CLOSURE_PATHS)
            or set(closure) != set(EXPECTED_RUNTIME_CLOSURE_PATHS)
            or any(closure[key].get("path") != path
                   for key, path in EXPECTED_RUNTIME_CLOSURE_PATHS.items())
            or declared_python_paths != discover_stage17_python_closure(root)):
        raise SemanticAdmissionError("policy runtime-key set differs from its loaded closure")
    for label, binding in closure.items():
        verify_binding(root, binding, f"runtime closure {label}")
    if policy["predecessor_status"] != "REJECTED_FAIL_OPEN_PREDECESSOR":
        raise SemanticAdmissionError("policy v9 predecessor rejection is absent")


def _v9_policy(root: pathlib.Path) -> tuple[dict[str, Any], pathlib.Path, str]:
    path = root / "config/stage17/stage17-operational-evidence-admission-policy-v9.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    return document, path, sha_file(path)


def verify_s17_ext_001(
    *, root: pathlib.Path, resolution: dict[str, Any],
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], graph_sha256: str,
    catalog_sha256: str, genesis_sha256: str, catalog: dict[str, Any],
    resolution_schema_sha256: str, **_: Any,
) -> dict[str, Any]:
    # S17-EXT-001 v9 records remain the accepted read-only preflight contract;
    # policy v10 wraps rather than rewrites that immutable evidence language.
    policy, path, digest = _v9_policy(root)
    entry = next(item for item in policy["entries"] if item["input_id"] == "S17-EXT-001")
    try:
        return predecessor.verify_s17_ext_001_semantics_v9(
            root=root, resolution=resolution,
            repository_documents=repository_documents,
            receipt_documents=receipt_documents, policy=policy,
            policy_path=path, policy_sha256=digest, policy_entry=entry,
            graph_sha256=graph_sha256, catalog_sha256=catalog_sha256,
            genesis_sha256=genesis_sha256, catalog=catalog,
            resolution_schema_sha256=resolution_schema_sha256,
        )
    except Exception as exception:
        raise SemanticAdmissionError(str(exception)) from exception


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    if len(receipt_documents) != 1 or pilot_archive is None or pilot_sidecar is None:
        raise SemanticAdmissionError("S17-EXT-006 requires caller-supplied archive/sidecar bytes")
    receipt = receipt_documents[0]
    if (receipt.get("verifier_id"), receipt.get("verifier_version")) != (
        release_verifier.VERIFIER_ID, release_verifier.VERIFIER_VERSION
    ):
        raise SemanticAdmissionError("S17-EXT-006 verifier identity drifted")
    contract_path = root / str(receipt.get("contract_path", ""))
    try:
        context = release_verifier.verify_pilot_candidate_artifact_v2(
            repository_root=root, contract_path=contract_path,
            archive=pilot_archive, sidecar=pilot_sidecar,
            synthetic_test_only=allow_synthetic,
        )
    except release_verifier.ArtifactError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    ext003 = admitted_resolutions.get("S17-EXT-003")
    if ext003 is None or not isinstance(ext003.semantic_context, dict):
        raise SemanticAdmissionError("S17-EXT-006 lacks admitted EXT003 runtime")
    runtime_record = ext003.semantic_context.get("runtime")
    measurements = runtime_record.get("measurements") if isinstance(runtime_record, dict) else None
    if not isinstance(measurements, dict):
        raise SemanticAdmissionError("S17-EXT-006 accepted runtime measurements are absent")
    if (context.worker_size_bytes, context.worker_sha256, context.worker_role,
        context.runtime_profile, context.supported_actions) != (
            measurements.get("worker_size_bytes"), measurements.get("worker_sha256"),
            measurements.get("worker_role"), measurements.get("runtime_profile"),
            tuple(measurements.get("supported_actions", [])),
        ):
        raise SemanticAdmissionError("EXT006 release worker differs from EXT002/EXT003 runtime")
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
        "release_artifact_path": measurements["worker_path"],
        "release_artifact_member_path": context.worker_member_path,
        "release_artifact_size_bytes": context.worker_size_bytes,
        "release_artifact_sha256": context.worker_sha256,
        "release_artifact_role": context.worker_role,
        "runtime_profile": context.runtime_profile,
        "supported_actions": list(context.supported_actions),
        "primary_custody_domain_id": context.primary_custody_domain_id,
        "secondary_custody_domain_id": context.secondary_custody_domain_id,
        "synthetic_test_only": context.synthetic_test_only,
    }}


def verify_input(
    *, input_id: str, root: pathlib.Path,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]], admitted_resolutions: Mapping[str, Any],
    allow_synthetic: bool, **kwargs: Any,
) -> dict[str, Any]:
    if input_id == "S17-EXT-001":
        return verify_s17_ext_001(
            root=root, repository_documents=repository_documents,
            receipt_documents=receipt_documents, **kwargs,
        )
    if input_id == "S17-EXT-006":
        return verify_s17_ext_006(
            root=root, receipt_documents=receipt_documents,
            admitted_resolutions=admitted_resolutions,
            allow_synthetic=allow_synthetic, **kwargs,
        )
    paths = [
        path for path, document in repository_documents
        if document.get("schema_version") == "cpu-prefetch-stage17-operational-input-manifest/2"
    ]
    paths.extend(
        pathlib.Path(receipt["artifact_locator"])
        for receipt in receipt_documents
        if isinstance(receipt.get("artifact_locator"), str)
    )
    candidates = []
    for path in paths:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if document.get("schema_version") == "cpu-prefetch-stage17-operational-input-manifest/2":
            candidates.append(path)
    if len(candidates) != 1:
        raise SemanticAdmissionError(f"{input_id} requires exactly one manifest v2")
    try:
        context = operational.verify_manifest_v2(
            repository_root=root, manifest_path=candidates[0],
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
        )
    except operational.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    authorization = context.get("authorization") if input_id in {"S17-EXT-005", "S17-EXT-010"} else None
    return {"authorization": authorization, "context": context}
