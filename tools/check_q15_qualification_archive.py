#!/usr/bin/env python3
"""Validate an explicitly supplied exact Q15 qualification archive.

This is an integration/action-input check.  It is intentionally separate from
the hermetic D-104 fake/self-test path and never discovers a build directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys
import tarfile
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "config/q15/q15-qualification-archive-external-contract-v1.json"
SCHEMA_PATH = ROOT / "config/schemas/q15-qualification-archive-external-contract-v1.schema.json"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def regular_nonsymlink(path: pathlib.Path) -> os.stat_result:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"not a regular nonsymlink file: {path}")
    return metadata


def load_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(contract))
    if errors:
        raise ValueError(f"external artifact contract invalid: {errors[0].message}")
    return contract


def verify(archive: pathlib.Path, sidecar: pathlib.Path) -> None:
    contract = load_contract()
    archive_contract = contract["archive"]
    sidecar_contract = contract["sidecar"]
    archive_metadata = regular_nonsymlink(archive)
    sidecar_metadata = regular_nonsymlink(sidecar)
    if archive.name != archive_contract["filename"]:
        raise ValueError("archive filename does not match the external contract")
    if sidecar.name != sidecar_contract["filename"]:
        raise ValueError("sidecar filename does not match the external contract")
    if archive_metadata.st_size != archive_contract["bytes"]:
        raise ValueError("archive byte count mismatch")
    if sidecar_metadata.st_size != sidecar_contract["bytes"]:
        raise ValueError("sidecar byte count mismatch")
    if sha256(archive) != archive_contract["sha256"]:
        raise ValueError("archive SHA-256 mismatch")
    if sha256(sidecar) != sidecar_contract["sha256"]:
        raise ValueError("sidecar SHA-256 mismatch")
    if sidecar.read_bytes() != sidecar_contract["exact_ascii"].encode("ascii"):
        raise ValueError("sidecar content mismatch")

    top_level = contract["release_identity"]["top_level_directory"]
    seen_top_levels: set[str] = set()
    with tarfile.open(archive, mode="r:gz") as bundle:
        members = bundle.getmembers()
        if not members:
            raise ValueError("archive is empty")
        for member in members:
            pure = pathlib.PurePosixPath(member.name)
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                raise ValueError(f"unsafe archive member: {member.name}")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ValueError(f"forbidden archive member type: {member.name}")
            seen_top_levels.add(pure.parts[0])
    if seen_top_levels != {top_level}:
        raise ValueError("archive top-level directory mismatch")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=pathlib.Path, required=True)
    parser.add_argument("--sidecar", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        verify(arguments.archive, arguments.sidecar)
    except (OSError, ValueError, tarfile.TarError) as exception:
        print(f"q15-qualification-archive-check: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "q15-qualification-archive-check: PASS "
        "(explicit external artifact, exact bytes/hash/top-level; authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
