#!/usr/bin/env python3
"""Create a typed receipt for the preserved D-120 pre-marker blocker."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import sys

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).parents[1]
SCHEMA = ROOT / "config/schemas/stage17-preflight-pre-marker-blocker-v1.schema.json"


def _binding(path: pathlib.Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    metadata = resolved.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"source is not a nonsymlink regular file: {path}")
    payload = resolved.read_bytes()
    return {"locator": str(resolved), "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def render(*, blocker_id: str, recorded_at_utc: str, transaction_id: str,
           journal: pathlib.Path, authorization: pathlib.Path,
           output_root: pathlib.Path) -> dict[str, object]:
    parsed = dt.datetime.strptime(recorded_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    if parsed.tzinfo is not None:
        raise ValueError("recorded UTC is invalid")
    resolved_output = output_root.resolve(strict=True)
    metadata = resolved_output.stat(follow_symlinks=False)
    if output_root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("source preflight output root is unsafe")
    if any(resolved_output.iterdir()):
        raise ValueError("source preflight output root is not empty")
    document = {
        "schema_version": "cpu-prefetch-stage17-preflight-pre-marker-blocker/1",
        "blocker_id": blocker_id, "recorded_at_utc": recorded_at_utc,
        "source_transaction_id": transaction_id,
        "source_revision": "41802850ce405b3a8324b4efc4d058f1fc33afa2",
        "source_journal": _binding(journal),
        "source_authorization": _binding(authorization),
        "source_preflight_output_root": str(resolved_output),
        "failure_stage": "PRE_MARKER_SCHEMA_VALIDATION",
        "failure_category": "RUNTIME_IMPLEMENTATION_HASH_CARDINALITY_MISMATCH",
        "schema_expected_runtime_identities": 17,
        "actual_policy_runtime_identities": 19,
        "attempt_marker_absent": True, "transport_started": False,
        "stand_observations_started": False, "retry_performed": False,
        "successor_authority": False, "stage18_authority": False,
    }
    schema = json.loads(SCHEMA.read_text())
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        raise ValueError(f"blocker schema rejection: {errors[0].message}")
    return document


def _canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocker-id", required=True)
    parser.add_argument("--recorded-at-utc", required=True)
    parser.add_argument("--transaction-id", required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--preflight-output-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        payload = _canonical(render(
            blocker_id=arguments.blocker_id,
            recorded_at_utc=arguments.recorded_at_utc,
            transaction_id=arguments.transaction_id,
            journal=arguments.journal,
            authorization=arguments.authorization,
            output_root=arguments.preflight_output_root,
        ))
        descriptor = os.open(arguments.output, os.O_WRONLY | os.O_CREAT |
                             os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(arguments.output.parent,
                            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except (OSError, ValueError) as exception:
        print(f"stage17-pre-marker-blocker: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-pre-marker-blocker: PASS output={arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
