#!/usr/bin/env python3
"""Validate D-053 without executing the stand or a PMU."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = document.get("source_contract", {})
    path = root / source.get("path", "")
    if (
        not path.is_file()
        or source.get("sha256") != sha256(path)
        or source.get("sha256")
        != "c5a13646ea5e413239337e1b83b3162578c35591a54d6002f656a78acfd3d531"
    ):
        errors.append("frozen D-052 source-contract hash mismatch")
    boundary = document.get("authority_boundary", {})
    for field in (
        "calibration_authorized",
        "confirmatory_authorized",
        "dynamic_pmu_execution_authorized",
        "pilot_authorized",
        "privileged_controls_authorized",
        "q15_r_authorized",
        "q15_w_authorized",
        "stand_access_authorized",
    ):
        if boundary.get(field) is not False:
            errors.append(f"D-053 authority boundary enables {field}")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    profile_path = root / "config/q15/q15-probe-implementation-profile-v1.json"
    schema_path = (
        root / "config/schemas/q15-probe-implementation-profile-v1.schema.json"
    )
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failures = [error.message for error in validator.iter_errors(profile)]
    failures.extend(semantic_errors(root, profile))
    if failures:
        for failure in failures:
            print(f"q15-probe-implementation-check: FAIL: {failure}", file=sys.stderr)
        return 1

    mutations: tuple[tuple[str, str, object], ...] = (
        ("seed_profile", "master_seed_hex", "0" * 64),
        ("seed_profile", "namespace", "wrong"),
        ("seed_profile", "purpose", "event-order"),
        ("seed_profile", "derived_key_hex", "0" * 16),
        ("integrity_profile", "dependent_load_count", "AT_MOST_LINE_COUNT"),
        ("integrity_profile", "counted_traversal_checksum_operations", 1),
        ("pointer_buffer_profile", "start_index", "ZERO"),
        ("authority_boundary", "dynamic_pmu_execution_authorized", True),
        ("authority_boundary", "stand_access_authorized", True),
        ("source_contract", "sha256", "0" * 64),
    )
    for index, (section, field, value) in enumerate(mutations):
        mutated = copy.deepcopy(profile)
        mutated[section][field] = value
        if not list(validator.iter_errors(mutated)) and not semantic_errors(root, mutated):
            print(
                f"q15-probe-implementation-check: FAIL: negative {index} passed",
                file=sys.stderr,
            )
            return 1

    print(
        "q15-probe-implementation-check: PASS "
        "(1 D-053 profile, 10 negative, stand/PMU not accessed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
