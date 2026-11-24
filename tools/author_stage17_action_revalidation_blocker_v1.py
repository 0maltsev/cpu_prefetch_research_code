#!/usr/bin/env python3
"""Create the typed receipt for the preserved D-123 pre-marker stop."""

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
SCHEMA = ROOT / (
    "config/schemas/stage17-preflight-action-revalidation-blocker-v1.schema.json"
)


def _binding(path: pathlib.Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    metadata = resolved.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"source is not a nonsymlink regular file: {path}")
    payload = resolved.read_bytes()
    return {"locator": str(resolved), "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def render(arguments: argparse.Namespace) -> dict[str, object]:
    dt.datetime.strptime(arguments.recorded_at_utc, "%Y-%m-%dT%H:%M:%SZ")
    output_root = arguments.output_root.resolve(strict=True)
    metadata = output_root.stat(follow_symlinks=False)
    if arguments.output_root.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError("source preflight output root is unsafe")
    if any(output_root.iterdir()):
        raise ValueError("source preflight output root is not empty")
    document = {
        "schema_version":
            "cpu-prefetch-stage17-preflight-action-revalidation-blocker/1",
        "blocker_id": arguments.blocker_id,
        "recorded_at_utc": arguments.recorded_at_utc,
        "actor": arguments.actor,
        "source_transaction_id": arguments.transaction_id,
        "source_revision": "327fc387a0fa792dea4a26043d2fbaa1ad10a54f",
        "source_journal": _binding(arguments.journal),
        "source_authorization": _binding(arguments.authorization),
        "source_resolution": _binding(arguments.resolution),
        "source_transition": _binding(arguments.transition),
        "source_preflight_output_root": str(output_root),
        "failure_stage": "PRE_MARKER_ACTION_REVALIDATION",
        "failure_category": "CURRENT_RECEIPT_SCHEMA_BINDING_KEY_MISMATCH",
        "inherited_schema_lookup_path":
            "config/schemas/stage17-read-only-preflight-observation-receipt-v5.schema.json",
        "current_policy_schema_path":
            "config/schemas/stage17-read-only-preflight-observation-receipt-v6.schema.json",
        "attempt_marker_absent": True,
        "transport_started": False,
        "stand_observations_started": False,
        "retry_performed": False,
        "replacement_transaction_required": True,
        "successor_authority": False,
        "stage18_authority": False,
    }
    schema = json.loads(SCHEMA.read_text())
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        raise ValueError(f"D-123 blocker schema rejection: {errors[0].message}")
    return document


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocker-id", required=True)
    parser.add_argument("--recorded-at-utc", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--transaction-id", required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--resolution", type=pathlib.Path, required=True)
    parser.add_argument("--transition", type=pathlib.Path, required=True)
    parser.add_argument("--output-root", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        payload = canonical(render(arguments))
        descriptor = os.open(
            arguments.output,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        try:
            os.write(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(
            arguments.output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except (OSError, ValueError) as exception:
        print(f"stage17-action-revalidation-blocker: FAIL: {exception}",
              file=sys.stderr)
        return 1
    print(f"stage17-action-revalidation-blocker: PASS output={arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
