#!/usr/bin/env python3
"""Create-exclusively author a D-124 no-predecessor attestation.

Per ADR-0124 (`PROPOSED`), this attests that a real search for D-120,
D-121, and D-123 predecessor blocker-receipt evidence was performed and
found nothing recoverable -- never that no predecessor incident occurred.
It never invents an evidence hash: every byte comes from an owner-supplied
search-evidence file read through one no-follow file descriptor.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import sys
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).parents[1]
SCHEMA = ROOT / "config/schemas/stage17-preflight-no-predecessor-attestation-v1.schema.json"


class AttestationError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def binding(path: pathlib.Path, schema_identity: str) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1:
            raise AttestationError(f"not a nonempty regular file: {path}")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise AttestationError(f"file changed while read: {path}")
    return {"locator": str(path.resolve()), "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "schema_identity": schema_identity}


def actual_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def build(arguments: argparse.Namespace) -> dict[str, Any]:
    return {
        "schema_version": "cpu-prefetch-stage17-preflight-no-predecessor-attestation/1",
        "attestation_id": arguments.attestation_id,
        "actor": arguments.actor,
        "recorded_at_utc": actual_utc(),
        "search_evidence": binding(
            arguments.search_evidence, arguments.search_evidence_schema_identity
        ),
        "search_scope": [
            "REPOSITORY_GIT_HISTORY",
            "LOCAL_FILESYSTEM_OUTSIDE_WORKING_TREE",
            "LOCAL_BUILD_AND_CI_ARTIFACT_STORAGE",
        ],
        "declaration": "NO_REAL_PREDECESSOR_EVIDENCE_FOUND",
        "covers_incident_ids": ["D-120", "D-121", "D-123"],
        "retry_allowed": False,
        "replacement_transaction_required": False,
        "stage18_authority": False,
    }


def write_exclusive(path: pathlib.Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
    )
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attestation-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--search-evidence", type=pathlib.Path, required=True)
    parser.add_argument(
        "--search-evidence-schema-identity", required=True,
        help="schema/kind identity of the bound search-evidence record",
    )
    parser.add_argument("--output", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        document = build(arguments)
        schema = json.loads(SCHEMA.read_text())
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(document))
        if errors:
            raise AttestationError(errors[0].message)
        write_exclusive(arguments.output, canonical(document))
    except Exception as exception:
        print(f"stage17-no-predecessor-attestation: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-no-predecessor-attestation: PASS output={arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
