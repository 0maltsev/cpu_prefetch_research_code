#!/usr/bin/env python3
"""Exact EXT006 v2 archive/sidecar/member verifier returning runtime context."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


VERIFIER_ID = "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
VERIFIER_VERSION = "2"
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
    synthetic_test_only: bool


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _regular(path: pathlib.Path) -> os.stat_result:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ArtifactError(f"not a nonsymlink regular file: {path}")
    return metadata


def _load(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ArtifactError(f"JSON root is not an object: {path}")
    return document


def _member(bundle: tarfile.TarFile, name: str) -> bytes:
    try:
        metadata = bundle.getmember(name)
    except KeyError as exception:
        raise ArtifactError(f"required archive member is absent: {name}") from exception
    if not metadata.isfile() or metadata.issym() or metadata.islnk():
        raise ArtifactError(f"required archive member is not a regular file: {name}")
    source = bundle.extractfile(metadata)
    if source is None:
        raise ArtifactError(f"required archive member cannot be read: {name}")
    return source.read()


def verify_pilot_candidate_artifact_v2(
    *, repository_root: pathlib.Path, contract_path: pathlib.Path,
    archive: pathlib.Path, sidecar: pathlib.Path, synthetic_test_only: bool = False,
) -> ReleaseContext:
    contract = _load(contract_path)
    schema = _load(repository_root / "config/schemas/stage17-pilot-candidate-external-contract-v2.schema.json")
    Draft202012Validator.check_schema(schema)
    errors = sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda item: tuple(item.path))
    if errors:
        raise ArtifactError(f"EXT006 v2 contract schema rejection: {errors[0].message}")
    archive_meta, sidecar_meta = _regular(archive), _regular(sidecar)
    if archive.name != contract["archive"]["filename"] or sidecar.name != contract["sidecar"]["filename"]:
        raise ArtifactError("EXT006 archive/sidecar filename drift")
    archive_sha, sidecar_sha = sha256_file(archive), sha256_file(sidecar)
    if (archive_meta.st_size, archive_sha) != (contract["archive"]["size_bytes"], contract["archive"]["sha256"]):
        raise ArtifactError("EXT006 archive byte identity mismatch")
    if (sidecar_meta.st_size, sidecar_sha) != (contract["sidecar"]["size_bytes"], contract["sidecar"]["sha256"]):
        raise ArtifactError("EXT006 sidecar byte identity mismatch")
    if sidecar.read_bytes() != contract["sidecar"]["exact_ascii"].encode("ascii"):
        raise ArtifactError("EXT006 sidecar exact bytes mismatch")
    with tarfile.open(archive, "r:gz") as bundle:
        for item in bundle.getmembers():
            relative = pathlib.PurePosixPath(item.name)
            if relative.is_absolute() or not relative.parts or ".." in relative.parts or item.issym() or item.islnk() or item.isdev() or item.isfifo():
                raise ArtifactError(f"unsafe EXT006 archive member: {item.name}")
        names = [item.name for item in bundle.getmembers()]
        manifest_suffix = contract["manifest"]["member_path"]
        manifests = [name for name in names if name == manifest_suffix or name.endswith("/" + manifest_suffix)]
        if len(manifests) != 1:
            raise ArtifactError("EXT006 manifest member is absent or duplicated")
        manifest_bytes = _member(bundle, manifests[0])
        worker_suffix = contract["worker"]["member_path"]
        workers = [name for name in names if name == worker_suffix or name.endswith("/" + worker_suffix)]
        if len(workers) != 1:
            raise ArtifactError("EXT006 release worker member is absent or duplicated")
        worker_bytes = _member(bundle, workers[0])
    if (len(manifest_bytes), sha256_bytes(manifest_bytes)) != (contract["manifest"]["size_bytes"], contract["manifest"]["sha256"]):
        raise ArtifactError("EXT006 manifest member identity mismatch")
    if (len(worker_bytes), sha256_bytes(worker_bytes)) != (contract["worker"]["size_bytes"], contract["worker"]["sha256"]):
        raise ArtifactError("EXT006 release worker member identity mismatch")
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("bundle_profile") != contract["manifest"]["bundle_profile"]:
        raise ArtifactError("EXT006 bundle profile mismatch")
    if manifest.get("source_archive", {}).get("source_revision") != contract["source_revision"]:
        raise ArtifactError("EXT006 source revision mismatch")
    runtime = manifest.get("stage17_fixed_action_runtime")
    expected_runtime = {
        "member_path": contract["worker"]["member_path"],
        "size_bytes": contract["worker"]["size_bytes"],
        "sha256": contract["worker"]["sha256"],
        "role": "STAGE17_FIXED_ACTION_WORKER",
        "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v2",
        "supported_actions": list(SUPPORTED_ACTIONS),
    }
    if runtime != expected_runtime:
        raise ArtifactError("EXT006 manifest runtime binding mismatch")
    if any(manifest.get(field) is not False for field in ("pilot_authorized", "confirmatory_authorized", "dynamic_qualification_authorized")):
        raise ArtifactError("EXT006 archive grants forbidden authority")
    custody = contract["custody"]
    if pathlib.Path(custody["archive_locator"]) != archive or pathlib.Path(custody["sidecar_locator"]) != sidecar:
        raise ArtifactError("EXT006 custody locator mismatch")
    if custody["primary_domain_id"] == custody["secondary_domain_id"]:
        raise ArtifactError("EXT006 requires two distinct custody domains")
    return ReleaseContext(
        archive, archive_meta.st_size, archive_sha, sidecar, sidecar_meta.st_size,
        sidecar_sha, manifests[0], len(manifest_bytes), sha256_bytes(manifest_bytes),
        contract["source_revision"], workers[0], len(worker_bytes),
        sha256_bytes(worker_bytes), "STAGE17_FIXED_ACTION_WORKER",
        "STAGE17-FIXED-ACTION-WORKER-v2", SUPPORTED_ACTIONS,
        custody["primary_domain_id"], custody["secondary_domain_id"],
        synthetic_test_only,
    )
