#!/usr/bin/env python3
"""Exact, caller-supplied Stage 17 pilot-candidate artifact verification."""

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
VERIFIER_VERSION = "1"


class ArtifactError(ValueError):
    """The supplied external artifact does not satisfy its immutable contract."""


@dataclass(frozen=True)
class ArtifactVerification:
    artifact_size_bytes: int
    artifact_sha256: str
    sidecar_size_bytes: int
    sidecar_sha256: str
    manifest_sha256: str
    file_count: int


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ArtifactError(f"JSON root is not an object: {path}")
    return document


def require_regular_nonsymlink(path: pathlib.Path) -> os.stat_result:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ArtifactError(f"not a regular nonsymlink file: {path}")
    return metadata


def validate_contract(
    contract_path: pathlib.Path, schema_path: pathlib.Path
) -> dict[str, Any]:
    contract = load_json(contract_path)
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(contract))
    if errors:
        raise ArtifactError(f"external contract is invalid: {errors[0].message}")
    return contract


def verify_contracted_bytes(
    contract: dict[str, Any], archive: pathlib.Path, sidecar: pathlib.Path
) -> ArtifactVerification:
    archive_metadata = require_regular_nonsymlink(archive)
    sidecar_metadata = require_regular_nonsymlink(sidecar)
    archive_contract = contract["archive"]
    sidecar_contract = contract["sidecar"]
    if archive.name != archive_contract["filename"]:
        raise ArtifactError("archive filename mismatch")
    if sidecar.name != sidecar_contract["filename"]:
        raise ArtifactError("sidecar filename mismatch")
    if archive_metadata.st_size != archive_contract["size_bytes"]:
        raise ArtifactError("archive byte-count mismatch")
    if sidecar_metadata.st_size != sidecar_contract["size_bytes"]:
        raise ArtifactError("sidecar byte-count mismatch")
    archive_sha256 = sha256_file(archive)
    sidecar_sha256 = sha256_file(sidecar)
    if archive_sha256 != archive_contract["sha256"]:
        raise ArtifactError("archive SHA-256 mismatch")
    if sidecar_sha256 != sidecar_contract["sha256"]:
        raise ArtifactError("sidecar SHA-256 mismatch")
    if sidecar.read_bytes() != sidecar_contract["exact_ascii"].encode("ascii"):
        raise ArtifactError("sidecar exact bytes mismatch")
    return ArtifactVerification(
        artifact_size_bytes=archive_metadata.st_size,
        artifact_sha256=archive_sha256,
        sidecar_size_bytes=sidecar_metadata.st_size,
        sidecar_sha256=sidecar_sha256,
        manifest_sha256="",
        file_count=0,
    )


def safe_extract(archive: pathlib.Path, destination: pathlib.Path) -> int:
    file_count = 0
    with tarfile.open(archive, mode="r:gz") as bundle:
        for member in bundle.getmembers():
            relative = pathlib.PurePosixPath(member.name)
            if relative.is_absolute() or not relative.parts or ".." in relative.parts:
                raise ArtifactError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ArtifactError(f"forbidden archive member type: {member.name}")
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ArtifactError(f"unsupported archive member type: {member.name}")
            source = bundle.extractfile(member)
            if source is None:
                raise ArtifactError(f"cannot read archive member: {member.name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
            file_count += 1
    return file_count


def verify_pilot_candidate_artifact(
    *,
    repository_root: pathlib.Path,
    contract_path: pathlib.Path,
    archive: pathlib.Path,
    sidecar: pathlib.Path,
) -> ArtifactVerification:
    schema_path = (
        repository_root
        / "config/schemas/stage17-pilot-candidate-external-contract-v1.schema.json"
    )
    contract = validate_contract(contract_path, schema_path)
    contracted = verify_contracted_bytes(contract, archive, sidecar)
    with tempfile.TemporaryDirectory(prefix="stage17-pilot-candidate-verify-") as temporary:
        extraction_root = pathlib.Path(temporary)
        archive_regular_file_count = safe_extract(archive, extraction_root)
        identity = contract["release_identity"]
        expected_root = extraction_root / identity["top_level_directory"]
        actual_roots = [path for path in extraction_root.iterdir() if path.is_dir()]
        if actual_roots != [expected_root]:
            raise ArtifactError("archive top-level directory mismatch")
        manifest_path = expected_root / identity["manifest_path"]
        require_regular_nonsymlink(manifest_path)
        manifest_sha256 = sha256_file(manifest_path)
        if manifest_sha256 != identity["manifest_sha256"]:
            raise ArtifactError("bundle manifest SHA-256 mismatch")
        manifest = load_json(manifest_path)
        if manifest.get("bundle_profile") != identity["bundle_profile"]:
            raise ArtifactError("bundle profile mismatch")
        if manifest.get("source_archive", {}).get("source_revision") != contract[
            "source_revision"
        ]:
            raise ArtifactError("bundle source revision mismatch")
        if any(
            manifest.get(field) is not False
            for field in (
                "pilot_authorized",
                "confirmatory_authorized",
                "dynamic_qualification_authorized",
            )
        ):
            raise ArtifactError("bundle grants forbidden execution authority")
        verifier = repository_root / "tools/verify_stand_bundle.py"
        completed = subprocess.run(
            [sys.executable, str(verifier), "--root", str(expected_root)],
            cwd=repository_root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            raise ArtifactError(
                "trusted internal bundle verifier failed: "
                + (completed.stderr.strip() or completed.stdout.strip())
            )
        checksum_inventory = expected_root / "SHA256SUMS"
        require_regular_nonsymlink(checksum_inventory)
        inventory_file_count = len(
            checksum_inventory.read_text(encoding="utf-8").splitlines()
        )
        if inventory_file_count != identity["file_count"]:
            raise ArtifactError("internal checksum-inventory file count mismatch")
        if archive_regular_file_count != inventory_file_count + 1:
            raise ArtifactError("archive regular-file count is not inventory plus SHA256SUMS")
    return ArtifactVerification(
        artifact_size_bytes=contracted.artifact_size_bytes,
        artifact_sha256=contracted.artifact_sha256,
        sidecar_size_bytes=contracted.sidecar_size_bytes,
        sidecar_sha256=contracted.sidecar_sha256,
        manifest_sha256=manifest_sha256,
        file_count=inventory_file_count,
    )
