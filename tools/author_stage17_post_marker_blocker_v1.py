#!/usr/bin/env python3
"""Create-exclusively retain the observed D-121 post-marker blocker."""

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
SCHEMA = ROOT / "config/schemas/stage17-preflight-post-marker-blocker-v1.schema.json"
ATTEMPT_NAME = "stage17-read-only-preflight-attempt-v8.json"


class BlockerError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def binding(path: pathlib.Path, schema_identity: str) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1:
            raise BlockerError(f"not a nonempty regular file: {path}")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
    finally:
        os.close(descriptor)
    if len(payload) != metadata.st_size:
        raise BlockerError(f"file changed while read: {path}")
    return {"locator": str(path.resolve()), "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "schema_identity": schema_identity}


def actual_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def build(arguments: argparse.Namespace) -> dict[str, Any]:
    entries = sorted(item.name for item in arguments.output_root.iterdir())
    if entries != [ATTEMPT_NAME]:
        raise BlockerError(f"predecessor output inventory is not marker-only: {entries}")
    marker = binding(
        arguments.output_root / ATTEMPT_NAME,
        "cpu-prefetch-stage17-read-only-preflight-attempt/8",
    )
    return {
        "schema_version": "cpu-prefetch-stage17-preflight-post-marker-blocker/1",
        "blocker_id": arguments.blocker_id,
        "predecessor_attempt_marker": marker,
        "predecessor_journal": binding(
            arguments.journal, "cpu-prefetch-stage17-state-journal/1"
        ),
        "predecessor_authorization": binding(
            arguments.authorization,
            "cpu-prefetch-stage17-read-only-preflight-authorization/10",
        ),
        "predecessor_resolution": binding(
            arguments.resolution, "cpu-prefetch-stage17-external-input-resolution/1"
        ),
        "predecessor_transition": binding(
            arguments.transition, "cpu-prefetch-stage17-state-transition/1"
        ),
        "predecessor_output_root": {
            "locator": str(arguments.output_root.resolve()),
            "entries": entries, "attempt_marker_only": True,
        },
        "observed_failure": {
            "failure_stage": "TRANSPORT_SETUP",
            "reason_category": "PROCESS_SUPERVISOR_SETUP_FAILURE",
            "transport_started": False, "remote_observation_count": 0,
            "completed_observation_ids": [],
            "full_failure_record_present": False,
            "fallback_failure_record_present": False,
            "retention_failure_category":
                "TERMINAL_SCHEMA_RUNTIME_CARDINALITY_MISMATCH",
            "source": "OPERATOR_OBSERVED_EXECUTOR_ERROR_AND_OUTPUT_ROOT_INVENTORY",
        },
        "actor": arguments.actor, "recorded_at_utc": actual_utc(),
        "retry_allowed": False, "replacement_transaction_required": True,
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
    parser.add_argument("--blocker-id", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--resolution", type=pathlib.Path, required=True)
    parser.add_argument("--transition", type=pathlib.Path, required=True)
    parser.add_argument("--output-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        document = build(arguments)
        schema = json.loads(SCHEMA.read_text())
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(document))
        if errors:
            raise BlockerError(errors[0].message)
        write_exclusive(arguments.output, canonical(document))
    except Exception as exception:
        print(f"stage17-post-marker-blocker: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-post-marker-blocker: PASS output={arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
