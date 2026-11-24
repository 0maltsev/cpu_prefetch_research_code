#!/usr/bin/env python3
"""Full-bundle EXT006 v4 verifier and contract authoring support."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


VERIFIER_ID = "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
VERIFIER_VERSION = "4"
SCHEMA = "config/schemas/stage17-pilot-candidate-external-contract-v4.schema.json"
SUPPORTED_ACTIONS = (
    "Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT",
)


class ArtifactError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseContext:
    archive_locator: pathlib.Path
    archive_size_bytes: int
    archive_sha256: str
    sidecar_locator: pathlib.Path
    sidecar_size_bytes: int
    sidecar_sha256: str
    manifest_member_path: str
    manifest_size_bytes: int
    manifest_sha256: str
    source_revision: str
    worker_member_path: str
    worker_size_bytes: int
    worker_sha256: str
    worker_role: str
    runtime_profile: str
    supported_actions: tuple[str, ...]
    primary_custody_domain_id: str
    secondary_custody_domain_id: str
    bundle_profile: str
    synthetic_test_only: bool
    sha256s_sha256: str
    sbom_sha256: str
    inventory_sha256: str


@dataclass(frozen=True)
class ExtractedReleaseContext:
    bundle_root: pathlib.Path
    manifest_size_bytes: int
    manifest_sha256: str
    source_revision: str
    worker_path: pathlib.Path
    worker_member_path: str
    worker_size_bytes: int
    worker_sha256: str
    worker_role: str
    runtime_profile: str
    supported_actions: tuple[str, ...]
    bundle_profile: str
    synthetic_test_only: bool
    sha256s_sha256: str
    sbom_sha256: str
    inventory_sha256: str
    full_verifier_size_bytes: int
    full_verifier_sha256: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular(path: pathlib.Path) -> os.stat_result:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ArtifactError(f"not a nonsymlink regular file: {path}")
    return metadata


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_bytes())
    if not isinstance(document, dict):
        raise ArtifactError(f"JSON root is not an object: {path}")
    return document


def _safe_extract(archive: pathlib.Path, destination: pathlib.Path) -> pathlib.Path:
    roots: set[str] = set()
    with tarfile.open(archive, "r:gz") as source:
        members = source.getmembers()
        for member in members:
            relative = pathlib.PurePosixPath(member.name)
            if (relative.is_absolute() or not relative.parts or ".." in relative.parts
                    or member.issym() or member.islnk() or member.isdev()
                    or member.isfifo() or not member.isfile()):
                raise ArtifactError(f"unsafe/nonregular archive member: {member.name}")
            roots.add(relative.parts[0])
        if len(roots) != 1:
            raise ArtifactError("bundle does not have exactly one top-level root")
        for member in members:
            relative = pathlib.PurePosixPath(member.name)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(
                target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
                os.O_CLOEXEC, 0o755 if member.mode & 0o111 else 0o644,
            )
            try:
                stream = source.extractfile(member)
                if stream is None:
                    raise ArtifactError(f"archive member cannot be read: {member.name}")
                while chunk := stream.read(1024 * 1024):
                    view = memoryview(chunk)
                    while view:
                        count = os.write(descriptor, view)
                        if count <= 0:
                            raise ArtifactError("archive extraction write stalled")
                        view = view[count:]
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    return destination / next(iter(roots))


def _binding(path: pathlib.Path, member_path: str) -> dict[str, Any]:
    metadata = _regular(path)
    return {"member_path": member_path, "size_bytes": metadata.st_size,
            "sha256": sha256_file(path)}


def _parse_sums(root: pathlib.Path) -> dict[str, str]:
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise ArtifactError("SHA256SUMS line is malformed")
        digest, locator = line[:64], line[66:]
        relative = pathlib.PurePosixPath(locator)
        if (len(digest) != 64 or any(item not in "0123456789abcdef" for item in digest)
                or relative.is_absolute() or ".." in relative.parts
                or locator in sums):
            raise ArtifactError("SHA256SUMS entry is unsafe or duplicated")
        path = root.joinpath(*relative.parts)
        if not path.is_file() or path.is_symlink() or sha256_file(path) != digest:
            raise ArtifactError(f"SHA256SUMS byte mismatch: {locator}")
        sums[locator] = digest
    checksum_file = root / "SHA256SUMS"
    actual = {
        item.relative_to(root).as_posix() for item in root.rglob("*")
        if item.is_file() and not item.is_symlink() and item != checksum_file
    }
    if set(sums) != actual:
        raise ArtifactError("SHA256SUMS does not cover the exact extracted file set")
    return sums


def _verify_inventory(root: pathlib.Path, sums: dict[str, str]) -> dict[str, Any]:
    inventory = _load_json(root / "BUNDLE_INVENTORY.json")
    if inventory.get("schema_version") != "cpu-prefetch-stand-bundle-inventory/1":
        raise ArtifactError("bundle inventory schema identity drifted")
    entries = inventory.get("files")
    if not isinstance(entries, list):
        raise ArtifactError("bundle inventory file set is absent")
    observed = {
        item.get("path"): (item.get("size_bytes"), item.get("sha256"))
        for item in entries if isinstance(item, dict)
    }
    expected_paths = set(sums) - {"BUNDLE_INVENTORY.json"}
    if set(observed) != expected_paths:
        raise ArtifactError("bundle inventory does not name the exact pre-inventory set")
    for relative, (size, digest) in observed.items():
        path = root / relative
        if (path.stat().st_size, sha256_file(path)) != (size, digest):
            raise ArtifactError(f"bundle inventory byte mismatch: {relative}")
    return inventory


def _run_full_verifier(root: pathlib.Path) -> None:
    verifier = root / "validators/verify_stand_bundle.py"
    if not verifier.is_file() or verifier.is_symlink():
        raise ArtifactError("bundle full verifier is absent")
    completed = subprocess.run(
        [sys.executable, "-B", str(verifier), "--root", str(root)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TZ": "UTC",
             "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise ArtifactError(
            "full verify_stand_bundle failed: " +
            completed.stderr.decode("utf-8", errors="replace")[:1000]
        )


def verify_extracted_bundle_v4(bundle_root: pathlib.Path) -> ExtractedReleaseContext:
    """Verify a clean extracted v4 bundle and derive its immutable runtime class.

    The caller cannot select production versus synthetic behavior.  That class
    is derived from the full verified manifest and the exact worker bytes.
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
    if profile not in {
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
    }:
        raise ArtifactError("extracted bundle profile is not a v4 Stage 17 profile")
    synthetic = profile == "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2"
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


def build_extracted_release_receipt_v4(
    *, bundle_root: pathlib.Path, receipt_id: str,
) -> dict[str, Any]:
    context = verify_extracted_bundle_v4(bundle_root)
    relative_worker = context.worker_path.relative_to(context.bundle_root).as_posix()
    result = {
        "schema_version": "cpu-prefetch-stage17-runtime-release-provenance/4",
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
    return result


def verify_extracted_release_receipt_v4(
    *, repository_root: pathlib.Path, receipt: dict[str, Any],
) -> ExtractedReleaseContext:
    schema = _load_json(
        repository_root / "config/schemas/stage17-runtime-release-provenance-v4.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise ArtifactError(
            f"runtime-release receipt schema rejection: {errors[0].message}"
        )
    context = verify_extracted_bundle_v4(pathlib.Path(receipt["bundle_root"]))
    expected = build_extracted_release_receipt_v4(
        bundle_root=context.bundle_root, receipt_id=receipt["receipt_id"]
    )
    if receipt != expected:
        raise ArtifactError("runtime-release receipt differs from verified bundle bytes")
    return context


def build_contract_v4(
    *, repository_root: pathlib.Path, archive: pathlib.Path, sidecar: pathlib.Path,
    primary_custody_domain_id: str, secondary_custody_domain_id: str,
    contract_id: str,
) -> dict[str, Any]:
    _regular(archive); _regular(sidecar)
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-ext006-author-") as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v4(extracted)
        manifest_path = extracted / "BUNDLE_MANIFEST.json"
        manifest = _load_json(manifest_path)
        runtime = manifest.get("stage17_fixed_action_runtime")
        if not isinstance(runtime, dict):
            raise ArtifactError("bundle fixed-action runtime is absent")
        worker_path = extracted / str(runtime.get("member_path", ""))
        result = {
            "schema_version": "cpu-prefetch-stage17-pilot-candidate-external-contract/4",
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


def verify_pilot_candidate_artifact_v4(
    *, repository_root: pathlib.Path, contract_path: pathlib.Path,
    archive: pathlib.Path, sidecar: pathlib.Path,
) -> ReleaseContext:
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
        extracted_context = verify_extracted_bundle_v4(extracted)
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
            "synthetic_test_only": manifest["bundle_profile"] ==
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
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
