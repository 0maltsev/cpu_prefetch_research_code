"""Seven-action diagnostic release admission; predecessor archives remain unchanged."""
from __future__ import annotations
import json
import pathlib
import subprocess
import tempfile
from typing import Any
from jsonschema import Draft202012Validator
import stage17_pilot_candidate_artifact_v8 as predecessor

VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "5"
SCHEMA = "config/schemas/stage17-pilot-candidate-external-contract-v7.schema.json"
RUNTIME_RELEASE_PROVENANCE_SCHEMA = "config/schemas/stage17-runtime-release-provenance-v7.schema.json"
SUPPORTED_ACTIONS = tuple(predecessor.SUPPORTED_ACTIONS) + ("Q16A-DURATION-DISCOVERY",)
RECOGNIZED_PROFILES = {"STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19"}
DRY_RUN_PROFILES = {"STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19"}
ArtifactError = predecessor.ArtifactError
ReleaseContext = predecessor.ReleaseContext
ExtractedReleaseContext = predecessor.ExtractedReleaseContext
sha256_file = predecessor.sha256_file
_regular = predecessor._regular
_load_json = predecessor._load_json
_safe_extract = predecessor._safe_extract
_binding = predecessor._binding
_parse_sums = predecessor._parse_sums
_verify_inventory = predecessor._verify_inventory
_run_full_verifier = predecessor._run_full_verifier


def _verify_diagnostic_bundle(bundle_root: pathlib.Path) -> ExtractedReleaseContext:
    """Faithful copy of predecessor `verify_extracted_bundle_v5`, broadened
    only to recognize this module's own `RECOGNIZED_PROFILES` (v7/dry-run-v4
    added) instead of `v5`'s frozen set. Every other check is byte-identical
    to the predecessor.
    """
    root = bundle_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ArtifactError("extracted bundle root is not a nonsymlink directory")
    _run_full_verifier(root)
    sums = _parse_sums(root)
    _verify_inventory(root, sums)
    manifest_path = root / "BUNDLE_MANIFEST.json"
    manifest = _load_json(manifest_path)
    runtime = manifest.get("stage17_fixed_action_runtime")
    if not isinstance(runtime, dict):
        raise ArtifactError("extracted bundle fixed-action runtime is absent")
    profile = manifest.get("bundle_profile")
    if profile not in RECOGNIZED_PROFILES:
        raise ArtifactError("extracted bundle profile is not a recognized Stage 17 profile")
    synthetic = profile in DRY_RUN_PROFILES
    expected_runtime = {
        "member_path": "release/bin/cpu_prefetch_runner",
        "size_bytes": (root / "release/bin/cpu_prefetch_runner").stat().st_size,
        "sha256": sha256_file(root / "release/bin/cpu_prefetch_runner"),
        "role": "STAGE17_FIXED_ACTION_WORKER",
        "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
        "supported_actions": list(SUPPORTED_ACTIONS),
        "synthetic_test_only": synthetic,
    }
    if runtime != expected_runtime:
        raise ArtifactError("extracted bundle runtime object is not exact")
    worker = root / runtime["member_path"]
    payload = worker.read_bytes()
    if (payload[:4] != b"\x7fELF"
            or b"--execute-fixed-stage17-action-v5" not in payload
            or b"--execute-fixed-stage17-action-v4" not in payload
            or b"STAGE17-FIXED-ACTION-WORKER-v4" not in payload):
        raise ArtifactError("extracted bundle worker lacks the fixed dispatcher")
    source_revision = manifest.get("source_archive", {}).get("source_revision")
    if (not isinstance(source_revision, str) or len(source_revision) != 40
            or any(item not in "0123456789abcdef" for item in source_revision)):
        raise ArtifactError("extracted bundle source revision is malformed")
    completed = subprocess.run(
        [str(worker), "--stage17-runtime-identity-v4"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=15,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TZ": "UTC"},
    )
    try:
        identity = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise ArtifactError(
            "fixed worker did not emit its closed runtime identity"
        ) from exception
    expected_identity = {
        "binary_sha256": sha256_file(worker),
        "protocol_version": "2.0.0-pre.3",
        "role": "STAGE17_FIXED_ACTION_WORKER",
        "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
        "source_dirty": False,
        "source_revision": source_revision,
        "supported_actions": list(SUPPORTED_ACTIONS),
        "synthetic_test_only": synthetic,
    }
    if completed.returncode != 0 or identity != expected_identity:
        raise ArtifactError(
            "fixed worker runtime identity differs from clean release provenance"
        )
    verifier = root / "validators/verify_stand_bundle.py"
    _regular(verifier)
    return ExtractedReleaseContext(
        bundle_root=root,
        manifest_size_bytes=manifest_path.stat().st_size,
        manifest_sha256=sha256_file(manifest_path),
        source_revision=source_revision,
        worker_path=worker,
        worker_member_path=runtime["member_path"],
        worker_size_bytes=worker.stat().st_size,
        worker_sha256=sha256_file(worker),
        worker_role=runtime["role"],
        runtime_profile=runtime["runtime_profile"],
        supported_actions=tuple(runtime["supported_actions"]),
        bundle_profile=profile,
        synthetic_test_only=synthetic,
        sha256s_sha256=sha256_file(root / "SHA256SUMS"),
        sbom_sha256=sha256_file(root / "SBOM.spdx.json"),
        inventory_sha256=sha256_file(root / "BUNDLE_INVENTORY.json"),
        full_verifier_size_bytes=verifier.stat().st_size,
        full_verifier_sha256=sha256_file(verifier),
    )

def build_contract_v9(
    *, repository_root: pathlib.Path, archive: pathlib.Path, sidecar: pathlib.Path,
    primary_custody_domain_id: str, secondary_custody_domain_id: str,
    contract_id: str,
) -> dict[str, Any]:
    """Faithful copy of predecessor `build_contract_v4`, calling this
    module's broadened `verify_extracted_bundle_v6` instead of the frozen
    `v4` module's two-string whitelist. Every other check is byte-identical
    to the predecessor.
    """
    _regular(archive); _regular(sidecar)
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-ext006-author-") as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v9(extracted)
        manifest_path = extracted / "BUNDLE_MANIFEST.json"
        manifest = _load_json(manifest_path)
        runtime = manifest.get("stage17_fixed_action_runtime")
        if not isinstance(runtime, dict):
            raise ArtifactError("bundle fixed-action runtime is absent")
        worker_path = extracted / str(runtime.get("member_path", ""))
        result = {
            "schema_version": "cpu-prefetch-stage17-pilot-candidate-external-contract/5",
            "contract_id": contract_id,
            "archive": {"filename": archive.name, "size_bytes": archive.stat().st_size,
                        "sha256": sha256_file(archive)},
            "sidecar": {"filename": sidecar.name, "size_bytes": sidecar.stat().st_size,
                        "sha256": sha256_file(sidecar),
                        "exact_ascii": sidecar.read_text(encoding="ascii")},
            "manifest": {**_binding(manifest_path, "BUNDLE_MANIFEST.json"),
                         "bundle_profile": manifest.get("bundle_profile")},
            "sha256s": _binding(extracted / "SHA256SUMS", "SHA256SUMS"),
            "sbom": _binding(extracted / "SBOM.spdx.json", "SBOM.spdx.json"),
            "inventory": _binding(extracted / "BUNDLE_INVENTORY.json",
                                  "BUNDLE_INVENTORY.json"),
            "worker": {**_binding(worker_path, runtime["member_path"]),
                       "role": runtime.get("role"),
                       "runtime_profile": runtime.get("runtime_profile"),
                       "supported_actions": runtime.get("supported_actions")},
            "source_revision": extracted_context.source_revision,
            "custody": {"archive_locator": str(archive),
                        "sidecar_locator": str(sidecar),
                        "primary_domain_id": primary_custody_domain_id,
                        "secondary_domain_id": secondary_custody_domain_id},
            "authority": {"pilot": False, "confirmatory": False, "phase18": False},
        }
    schema = _load_json(repository_root / SCHEMA)
    errors = list(Draft202012Validator(schema).iter_errors(result))
    if errors:
        raise ArtifactError(f"generated EXT006 contract is invalid: {errors[0].message}")
    return result

def _verify_diagnostic_contract(
    *, repository_root: pathlib.Path, contract_path: pathlib.Path,
    archive: pathlib.Path, sidecar: pathlib.Path,
) -> ReleaseContext:
    """Faithful copy of predecessor `verify_pilot_candidate_artifact_v4`,
    calling this module's broadened `verify_extracted_bundle_v6` and using
    `RECOGNIZED_PROFILES`/`DRY_RUN_PROFILES` instead of the `v4` two-string
    literals. Every other check is byte-identical to the predecessor.
    """
    contract = _load_json(contract_path)
    schema = _load_json(repository_root / SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(contract))
    if errors:
        raise ArtifactError(f"EXT006 v4 contract schema rejection: {errors[0].message}")
    archive_meta, sidecar_meta = _regular(archive), _regular(sidecar)
    if (archive.name, archive_meta.st_size, sha256_file(archive)) != (
        contract["archive"]["filename"], contract["archive"]["size_bytes"],
        contract["archive"]["sha256"],
    ):
        raise ArtifactError("EXT006 archive byte identity mismatch")
    if (sidecar.name, sidecar_meta.st_size, sha256_file(sidecar),
            sidecar.read_text(encoding="ascii")) != (
        contract["sidecar"]["filename"], contract["sidecar"]["size_bytes"],
        contract["sidecar"]["sha256"], contract["sidecar"]["exact_ascii"],
    ):
        raise ArtifactError("EXT006 sidecar byte identity mismatch")
    if contract["custody"]["primary_domain_id"] == contract["custody"]["secondary_domain_id"]:
        raise ArtifactError("EXT006 requires two distinct custody domains")
    if (pathlib.Path(contract["custody"]["archive_locator"]) != archive
            or pathlib.Path(contract["custody"]["sidecar_locator"]) != sidecar):
        raise ArtifactError("EXT006 custody locator mismatch")
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-ext006-verify-") as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v9(extracted)
        manifest_path = extracted / "BUNDLE_MANIFEST.json"
        manifest = _load_json(manifest_path)
        runtime = manifest.get("stage17_fixed_action_runtime")
        if not isinstance(runtime, dict):
            raise ArtifactError("EXT006 runtime binding is absent")
        bindings = {
            "manifest": manifest_path,
            "sha256s": extracted / "SHA256SUMS",
            "sbom": extracted / "SBOM.spdx.json",
            "inventory": extracted / "BUNDLE_INVENTORY.json",
            "worker": extracted / str(runtime.get("member_path", "")),
        }
        for name, path in bindings.items():
            expected = contract[name]
            if (path.relative_to(extracted).as_posix(), path.stat().st_size,
                    sha256_file(path)) != (
                expected["member_path"], expected["size_bytes"], expected["sha256"]
            ):
                raise ArtifactError(f"EXT006 {name} member identity mismatch")
        expected_runtime = {
            "member_path": contract["worker"]["member_path"],
            "size_bytes": contract["worker"]["size_bytes"],
            "sha256": contract["worker"]["sha256"],
            "role": "STAGE17_FIXED_ACTION_WORKER",
            "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
            "supported_actions": list(SUPPORTED_ACTIONS),
            "synthetic_test_only": manifest["bundle_profile"] in DRY_RUN_PROFILES,
        }
        if runtime != expected_runtime:
            raise ArtifactError("EXT006 manifest/runtime object mismatch")
        if any(manifest.get(field) is not False for field in (
            "pilot_authorized", "confirmatory_authorized",
            "dynamic_qualification_authorized",
        )):
            raise ArtifactError("EXT006 bundle grants forbidden authority")
        if manifest.get("source_archive", {}).get("source_revision") != contract["source_revision"]:
            raise ArtifactError("EXT006 source revision mismatch")
        worker = bindings["worker"]
        payload = worker.read_bytes()
        if (payload[:4] != b"\x7fELF" or
                b"--execute-fixed-stage17-action-v5" not in payload or
                b"--execute-fixed-stage17-action-v4" not in payload or
                b"STAGE17-FIXED-ACTION-WORKER-v4" not in payload):
            raise ArtifactError("EXT006 worker is not the fixed v4 dispatcher")
        context = ReleaseContext(
            archive, archive_meta.st_size, contract["archive"]["sha256"],
            sidecar, sidecar_meta.st_size, contract["sidecar"]["sha256"],
            "BUNDLE_MANIFEST.json", manifest_path.stat().st_size,
            sha256_file(manifest_path), contract["source_revision"],
            runtime["member_path"], worker.stat().st_size, sha256_file(worker),
            runtime["role"], runtime["runtime_profile"],
            tuple(runtime["supported_actions"]),
            contract["custody"]["primary_domain_id"],
            contract["custody"]["secondary_domain_id"],
            extracted_context.bundle_profile,
            extracted_context.synthetic_test_only,
            extracted_context.sha256s_sha256,
            extracted_context.sbom_sha256,
            extracted_context.inventory_sha256,
        )
    return context

def build_extracted_release_receipt_v9(
    *, bundle_root: pathlib.Path, receipt_id: str,
) -> dict[str, Any]:
    context = verify_extracted_bundle_v9(bundle_root)
    relative_worker = context.worker_path.relative_to(context.bundle_root).as_posix()
    return {
        "schema_version": "cpu-prefetch-stage17-runtime-release-provenance/6",
        "receipt_id": receipt_id,
        "bundle_root": str(context.bundle_root),
        "bundle_profile": context.bundle_profile,
        "source_revision": context.source_revision,
        "bundle_manifest": {
            "path": "BUNDLE_MANIFEST.json",
            "size_bytes": context.manifest_size_bytes,
            "sha256": context.manifest_sha256,
        },
        "sha256s": {
            "path": "SHA256SUMS",
            "size_bytes": (context.bundle_root / "SHA256SUMS").stat().st_size,
            "sha256": context.sha256s_sha256,
        },
        "sbom": {
            "path": "SBOM.spdx.json",
            "size_bytes": (context.bundle_root / "SBOM.spdx.json").stat().st_size,
            "sha256": context.sbom_sha256,
        },
        "inventory": {
            "path": "BUNDLE_INVENTORY.json",
            "size_bytes": (context.bundle_root / "BUNDLE_INVENTORY.json").stat().st_size,
            "sha256": context.inventory_sha256,
        },
        "worker": {
            "path": relative_worker,
            "size_bytes": context.worker_size_bytes,
            "sha256": context.worker_sha256,
            "role": context.worker_role,
            "runtime_profile": context.runtime_profile,
            "supported_actions": list(context.supported_actions),
        },
        "full_bundle_verifier": {
            "path": "validators/verify_stand_bundle.py",
            "size_bytes": context.full_verifier_size_bytes,
            "sha256": context.full_verifier_sha256,
            "result": "PASS",
        },
        "synthetic_test_only": context.synthetic_test_only,
        "phase18_authority": False,
    }

def _verify_diagnostic_receipt(
    *, repository_root: pathlib.Path, receipt: dict[str, Any],
) -> ExtractedReleaseContext:
    schema = _load_json(repository_root / RUNTIME_RELEASE_PROVENANCE_SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise ArtifactError(
            f"runtime-release receipt schema rejection: {errors[0].message}"
        )
    context = verify_extracted_bundle_v9(pathlib.Path(receipt["bundle_root"]))
    expected = build_extracted_release_receipt_v9(
        bundle_root=context.bundle_root, receipt_id=receipt["receipt_id"]
    )
    if receipt != expected:
        raise ArtifactError("runtime-release receipt differs from verified bundle bytes")
    return context

def verify_extracted_bundle_v9(bundle_root):
    profile = _load_json(pathlib.Path(bundle_root) / "BUNDLE_MANIFEST.json").get("bundle_profile")
    if profile not in RECOGNIZED_PROFILES:
        return predecessor.verify_extracted_bundle_v6(bundle_root)
    return _verify_diagnostic_bundle(bundle_root)


def verify_pilot_candidate_artifact_v9(**arguments):
    document = _load_json(arguments["contract_path"])
    if document.get("schema_version") != "cpu-prefetch-stage17-pilot-candidate-external-contract/5":
        return predecessor.verify_pilot_candidate_artifact_v7(**arguments)
    return _verify_diagnostic_contract(**arguments)


def verify_extracted_release_receipt_v9(**arguments):
    if arguments["receipt"].get("schema_version") != "cpu-prefetch-stage17-runtime-release-provenance/6":
        return predecessor.verify_extracted_release_receipt_v8(**arguments)
    return _verify_diagnostic_receipt(**arguments)
