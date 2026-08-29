#!/usr/bin/env python3
"""Stage 17 closed semantic registry with external-journal preflight runtime (policy v13)."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import pathlib
import stat
import sys
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import stage17_operational_semantics_v4 as operational
import stage17_pilot_candidate_artifact_v4 as release_verifier
import stage17_semantic_verifier_v12 as predecessor
import stage17_read_only_preflight_semantic_verifier_v10 as preflight


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v13.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v13.schema.json"
)
VERIFIER_ID = "STAGE17-SEMANTIC-ADMISSION-VERIFIER"
VERIFIER_VERSION = "13"
INPUT_IDS = tuple(f"S17-EXT-{index:03d}" for index in range(1, 11))


class SemanticAdmissionError(ValueError):
    pass


def sha_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def pinned_binding_bytes(root: pathlib.Path, binding: dict[str, Any], label: str) \
        -> tuple[pathlib.Path, bytes]:
    """Read one policy-bound repository object through one no-follow fd."""
    relative = pathlib.PurePosixPath(str(binding.get("path", "")))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise SemanticAdmissionError(f"{label} locator is unsafe")
    descriptor = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        for index, component in enumerate(relative.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index + 1 < len(relative.parts):
                flags |= os.O_DIRECTORY
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode)
                or metadata.st_size != binding.get("size_bytes")
                or metadata.st_size < 1
                or metadata.st_size > 64 * 1024 * 1024):
            raise SemanticAdmissionError(f"{label} file identity/size drifted")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size or hashlib.sha256(payload).hexdigest() != \
                binding.get("sha256"):
            raise SemanticAdmissionError(f"{label} bytes drifted")
        return root.joinpath(*relative.parts), payload
    except OSError as exception:
        raise SemanticAdmissionError(f"{label} cannot be opened safely") from exception
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def verify_binding(root: pathlib.Path, binding: dict[str, Any], label: str) \
        -> pathlib.Path:
    path, _ = pinned_binding_bytes(root, binding, label)
    return path


def discover_python_closure(root: pathlib.Path, roots: tuple[str, ...]) -> set[str]:
    pending = list(roots)
    discovered: set[str] = set()
    while pending:
        module = pending.pop()
        relative = f"tools/{module}.py"
        if relative in discovered:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise SemanticAdmissionError(f"runtime module is absent: {relative}")
        discovered.add(relative)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [item.name.split(".", 1)[0] for item in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            for name in names:
                if name.startswith("stage17_") and (root / "tools" / f"{name}.py").is_file():
                    pending.append(name)
    return discovered


def verify_policy_v13(
    *, root: pathlib.Path, policy: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, genesis_record_sha256: str,
    resolution_schema_sha256: str,
) -> None:
    schema = json.loads((root / POLICY_SCHEMA).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v13 schema rejection: {errors[0].message}"
        )
    if (policy["graph_sha256"] != graph_sha256
            or policy["catalog_sha256"] != catalog_sha256
            or policy["genesis_record_sha256"] != genesis_record_sha256
            or policy["resolution_schema_sha256"] != resolution_schema_sha256):
        raise SemanticAdmissionError("policy graph/catalog/genesis binding drifted")
    if policy["predecessor_status"] != "SUPERSEDED_EXTERNAL_JOURNAL_RUNTIME_DEFECT":
        raise SemanticAdmissionError("policy v12 predecessor status is absent")
    entries = policy["entries"]
    if (tuple(item["input_id"] for item in entries) != INPUT_IDS
            or any(item != {
                "input_id": item["input_id"], "status": "IMPLEMENTED",
                "verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION,
            } for item in entries)):
        raise SemanticAdmissionError("policy does not implement exactly ten inputs")
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            verify_binding(root, binding, f"{group} {key}")
    roots = tuple(policy["runtime_import_roots"])
    discovered = discover_python_closure(root, roots)
    declared = {
        item["path"] for item in policy["runtime_closure"].values()
        if item["path"].startswith("tools/stage17_")
        and item["path"].endswith(".py")
    }
    if discovered != declared:
        raise SemanticAdmissionError("policy Python runtime closure is incomplete/expanded")
    # Characterization/test processes may also import immutable predecessors.
    # Authority is defined by the statically discovered current production
    # roots, not by every diagnostic module present in ``sys.modules``.  The
    # loop below still pins every module reachable from those roots to its
    # exact repository path and bytes; an undeclared import reachable from a
    # production root changes ``discovered`` and fails above.
    for relative in sorted(discovered):
        module_name = pathlib.PurePosixPath(relative).stem
        module = sys.modules.get(module_name)
        module_path_text = getattr(module, "__file__", None)
        binding = next(
            item for item in policy["runtime_closure"].values()
            if item["path"] == relative
        )
        expected_path, payload = pinned_binding_bytes(
            root, binding, f"loaded runtime {module_name}"
        )
        if module is None:
            continue
        if not isinstance(module_path_text, str):
            raise SemanticAdmissionError(f"runtime module path is absent: {module_name}")
        actual_path = pathlib.Path(module_path_text)
        if actual_path.suffix == ".pyc":
            actual_path = pathlib.Path(getattr(module, "__cached__", module_path_text))
            source = getattr(module, "__file__", module_path_text)
            actual_path = pathlib.Path(source)
        if actual_path.resolve() != expected_path.resolve() or sha_file(actual_path) != \
                hashlib.sha256(payload).hexdigest():
            raise SemanticAdmissionError(f"loaded runtime identity drifted: {module_name}")


def verify_s17_ext_001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    entry = next(item for item in policy["entries"]
                 if item["input_id"] == "S17-EXT-001")
    try:
        preflight.verify_policy_v10(
            root=root,
            policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v10(
            **{
                key: value
                for key, value in arguments.items()
                if key != "policy"
            },
            policy=policy,
            policy_path=policy_path,
            policy_sha256=sha_file(policy_path),
            policy_entry=entry,
        )
    except Exception as exception:
        raise SemanticAdmissionError(str(exception)) from exception


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    if len(receipt_documents) != 1 or pilot_archive is None or pilot_sidecar is None:
        raise SemanticAdmissionError("EXT006 requires exact archive/sidecar bytes")
    receipt = receipt_documents[0]
    if (receipt.get("verifier_id"), receipt.get("verifier_version")) != (
        release_verifier.VERIFIER_ID, release_verifier.VERIFIER_VERSION
    ):
        raise SemanticAdmissionError("EXT006 verifier identity drifted")
    contract_path = root / str(receipt.get("contract_path", ""))
    try:
        context = release_verifier.verify_pilot_candidate_artifact_v4(
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


def verify_operational_manifest(
    *, input_id: str, root: pathlib.Path,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], allow_synthetic: bool,
    policy: dict[str, Any], **_: Any,
) -> dict[str, Any]:
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
        context = operational.verify_manifest_v4(
            repository_root=root, manifest_path=path,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
            pinned_repository_bytes=pinned,
        )
    except operational.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    authorization = None
    if input_id in {"S17-EXT-005", "S17-EXT-010"}:
        admitted_authorization = context.get("authorization")
        if not isinstance(admitted_authorization, dict):
            raise SemanticAdmissionError(
                f"{input_id} semantic authority context is absent"
            )
        authorization = dict(admitted_authorization)
        authorization["authority_scope"] = (
            "PRIVILEGED_QUALIFICATION_CONTROL"
            if input_id == "S17-EXT-005"
            else "STAGE17_PILOT_PHASE_ONLY"
        )
    return {"authorization": authorization, "context": context}


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id == "S17-EXT-001":
        return verify_s17_ext_001(input_id=input_id, **arguments)
    if input_id == "S17-EXT-006":
        return verify_s17_ext_006(**arguments)
    if input_id in {
        "S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-005",
        "S17-EXT-007", "S17-EXT-008", "S17-EXT-009", "S17-EXT-010",
    }:
        return verify_operational_manifest(input_id=input_id, **arguments)
    raise SemanticAdmissionError(f"no semantic verifier registered for {input_id}")
