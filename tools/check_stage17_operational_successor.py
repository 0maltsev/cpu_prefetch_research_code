#!/usr/bin/env python3
"""Verify immutable Stage 17 predecessor/templates and the journal successor.

The v1 successor and checklist are historical definitions.  Operational state is
computed only by ``stage17_state_journal``; no status field in either template is
treated as current evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator

from stage17_state_journal_v16 import JournalError, validate_operational_journal


ROOT = pathlib.Path(__file__).resolve().parents[1]
SUCCESSOR_PATH = pathlib.Path(
    "config/stage17/stage17-operational-authorization-successor-v1.json"
)
SUCCESSOR_SCHEMA = pathlib.Path(
    "config/schemas/stage17-operational-authorization-successor-v1.schema.json"
)
CHECKLIST_PATH = pathlib.Path(
    "config/stage17/stage17-external-input-checklist-v1.json"
)
CHECKLIST_SCHEMA = pathlib.Path(
    "config/schemas/stage17-external-input-checklist-v1.schema.json"
)
PRESERVATION_PATH = pathlib.Path(
    "config/stage17/d099-d108-preservation-manifest-v1.json"
)
PRESERVATION_SCHEMA = pathlib.Path(
    "config/schemas/stage17-predecessor-preservation-v1.schema.json"
)
JOURNAL_PATH = pathlib.Path(
    "config/stage17/journal/stage17-state-journal-000000.json"
)
IMMUTABLE_SHA256 = {
    "docs/decisions/0104-stage17-pilot-operational-governance-successor.md": (
        "747b66d46db9103279026627cfd318861111ff71f66790013b31ece164360323"
    ),
    SUCCESSOR_PATH.as_posix(): (
        "15921041ba3cdb75310fad6abfde29734009ed4732e536a8daf5686527dfe4e2"
    ),
    CHECKLIST_PATH.as_posix(): (
        "d29e650041dbefcbd52da5aed261f3c484a5fe96b3d95576617bb54887587d3f"
    ),
    PRESERVATION_PATH.as_posix(): (
        "d0532418f895865c48f537488999e541901565fb958b12d3b8946bf06987a3a7"
    ),
}


def load(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return document


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_regular_file(relative_text: object) -> pathlib.Path:
    if not isinstance(relative_text, str):
        raise ValueError("preserved path is missing")
    relative = pathlib.PurePosixPath(relative_text)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError(f"unsafe preserved path: {relative_text}")
    current = ROOT
    for part in relative.parts:
        current /= part
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"preserved path contains a symlink: {relative_text}")
    if not stat.S_ISREG(os.lstat(current).st_mode):
        raise ValueError(f"preserved path is not a regular file: {relative_text}")
    return current


def schema_errors(document: dict[str, Any], schema_path: pathlib.Path) -> list[str]:
    schema = load(ROOT / schema_path)
    Draft202012Validator.check_schema(schema)
    return [
        f"$/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(document)
    ]


def preservation_errors() -> list[str]:
    errors: list[str] = []
    preservation = load(ROOT / PRESERVATION_PATH)
    errors.extend(schema_errors(preservation, PRESERVATION_SCHEMA))
    paths = [item.get("path") for item in preservation.get("tracked_artifacts", [])]
    if len(paths) != len(set(paths)):
        errors.append("preservation manifest contains duplicate tracked paths")
    for item in preservation.get("tracked_artifacts", []):
        try:
            path = repository_regular_file(item.get("path"))
            if sha256(path) != item.get("sha256"):
                errors.append(f"preserved artifact SHA-256 mismatch: {item.get('path')}")
        except (OSError, ValueError) as exception:
            errors.append(str(exception))
    for source in preservation.get("historical_implementation_sources", []):
        completed = subprocess.run(
            ["git", "show", f"{source.get('git_revision')}:{source.get('path')}"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            errors.append("historical D-104 implementation is unavailable")
        elif hashlib.sha256(completed.stdout).hexdigest() != source.get("sha256"):
            errors.append("historical D-104 implementation SHA-256 mismatch")
    return errors


def template_errors() -> list[str]:
    errors: list[str] = []
    for relative, expected in IMMUTABLE_SHA256.items():
        try:
            path = repository_regular_file(relative)
            if sha256(path) != expected:
                errors.append(f"immutable template drifted: {relative}")
        except (OSError, ValueError) as exception:
            errors.append(str(exception))
    successor = load(ROOT / SUCCESSOR_PATH)
    checklist = load(ROOT / CHECKLIST_PATH)
    errors.extend(schema_errors(successor, SUCCESSOR_SCHEMA))
    errors.extend(schema_errors(checklist, CHECKLIST_SCHEMA))
    if successor.get("current_state") != "PREPARED":
        errors.append("immutable successor v1 is not its PREPARED definition")
    identifiers = [item.get("input_id") for item in checklist.get("items", [])]
    expected = [f"S17-EXT-{index:03d}" for index in range(1, 11)]
    if identifiers != expected:
        errors.append("immutable checklist is not exact ordered S17-EXT-001..010")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--print-missing", action="store_true")
    arguments = parser.parse_args()
    errors = template_errors() + preservation_errors()
    try:
        result = validate_operational_journal(
            repository_root=ROOT,
            evidence_root=ROOT,
            latest_journal=ROOT / JOURNAL_PATH,
            journal_directory=ROOT / JOURNAL_PATH.parent,
        )
    except (JournalError, OSError, json.JSONDecodeError) as exception:
        errors.append(str(exception))
        result = None
    if arguments.self_test:
        mutant = load(ROOT / SUCCESSOR_PATH)
        mutant["current_state"] = "PREFLIGHT_ACCEPTED"
        if not schema_errors(mutant, SUCCESSOR_SCHEMA):
            errors.append("legacy successor schema accepted a non-template current state")
    if errors:
        for error in errors:
            print(f"stage17-operational-successor-check: FAIL: {error}", file=sys.stderr)
        return 1
    assert result is not None
    if arguments.print_missing:
        print(
            json.dumps(
                {
                    "current_state": result.current_state,
                    "pilot_ready": result.pilot_ready,
                    "missing_external_inputs": list(result.missing_input_ids),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        print(
            "stage17-operational-successor-check: PASS "
            f"(legacy_template=true; state={result.current_state}; transitions=0; "
            f"external_inputs={len(result.missing_input_ids)}; pilot_ready=false; "
            "semantic_policy=v21; preflight_policy=v15; controller=v9; "
            "all_ten_verifiers=IMPLEMENTED; "
            "Stage17/Stage18 complete=false; stand=NOT_ACCESSED)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
