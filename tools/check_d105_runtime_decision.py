#!/usr/bin/env python3
"""Validate the no-action D-105 through D-108 runtime decision bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD = ROOT / "config/q15/q15-r-p4-r-c-d105-runtime-decision-input-v1.json"
SCHEMA = ROOT / "config/schemas/q15-r-p4-r-c-d105-runtime-decision-input-v1.schema.json"
EXPECTED = {
    "D-105": "ACQUIRE_ONE_SIGNED_READ_ONLY_RUNTIME_IDENTITY_CAPTURE_THEN_REVIEW",
    "D-106": "EXTEND_SINGLE_OWNER_WAIVER_FOR_ONE_RUNTIME_IDENTITY_CAPTURE_AND_REVIEW",
    "D-107": "FIX_EXACT_PINNED_OPENSSH_COMMAND_AND_STDIN_SCRIPT_GRAPH",
    "D-108": "REQUIRE_CANONICAL_COMPLETE_CAPTURE_SEPARATE_REVIEW_AND_CLEAN_SUCCESSOR",
}
HISTORICAL_D104_REVISION = "dc643df498fa36c3c34507f977634c05421751b1"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def historical_d104_executor_sha256() -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{HISTORICAL_D104_REVISION}:tools/execute_d104_p4_r_c.py"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        return None
    return hashlib.sha256(completed.stdout).hexdigest()


def semantic_errors(record: dict[str, Any], *, verify_files: bool) -> list[str]:
    errors: list[str] = []
    decisions = record.get("decisions", [])
    if [item.get("decision_id") for item in decisions] != list(EXPECTED):
        errors.append("D-105 through D-108 must be unique and ordered")
    for item in decisions:
        identifier = item.get("decision_id")
        if identifier in EXPECTED:
            if item.get("recommended_option") != EXPECTED[identifier]:
                errors.append(f"{identifier} recommendation drifted")
            if item.get("recommended_option") not in item.get("options", []):
                errors.append(f"{identifier} recommendation is not an option")
            if item.get("selected_option") is not None:
                errors.append(f"{identifier} was selected without exact acceptance")
    required = record.get("required_before_runtime_action", {})
    if len(required) != 9 or any(value is not None for value in required.values()):
        errors.append("runtime action prerequisites were fabricated")
    authority = record.get("authority_boundary", {})
    enabled = {name for name, value in authority.items() if value is True}
    if enabled != {"repository_local_decision_preparation_authorized"}:
        errors.append("D-105 proposal omitted or widened no-action authority")
    scope = record.get("proposed_repository_local_scope_if_accepted", {})
    enabled_scope = {name for name, value in scope.items() if value is True}
    if enabled_scope != {
        "implement_fixed_read_only_runtime_collector",
        "implement_fake_backend_schema_and_negative_tests",
        "prepare_still_unissued_runtime_authorization_and_review_templates",
    }:
        errors.append("proposed acceptance scope omitted or widened repository-local work")
    statement = record.get("exact_owner_acceptance_template", "")
    for token in (
        "@DECISION_INPUT_SHA256@",
        "dc643df498fa36c3c34507f977634c05421751b1",
        "afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241",
        "0b7e2f1c65849abe7d29ed8fd91fabb6105b8977d3051b9947ac7346fc14bdf6",
        "Do not use keys",
        "later separately signed and explicitly approved authorization",
    ):
        if token not in statement:
            errors.append(f"acceptance template omits exact boundary: {token}")
    if verify_files:
        inputs = record.get("immutable_inputs", {})
        for path_field, hash_field in (
            ("d100_acceptance_path", "d100_acceptance_sha256"),
            ("d104_preparation_path", "d104_preparation_sha256"),
        ):
            path = ROOT / str(inputs.get(path_field, ""))
            if not path.is_file() or sha256(path) != inputs.get(hash_field):
                errors.append(f"immutable local input drifted: {path_field}")
        historical_hash = historical_d104_executor_sha256()
        if historical_hash is None or historical_hash != inputs.get("d104_executor_sha256"):
            errors.append("immutable historical D-104 executor Git object drifted")
        d099 = subprocess.run(
            [sys.executable, str(ROOT / "tools/check_d099_p4_r_i_complete.py")],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if d099.returncode != 0:
            errors.append("D-099 predecessor no longer verifies")
        d104 = subprocess.run(
            [sys.executable, str(ROOT / "tools/check_d104_p4_r_c_implementation.py")],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if d104.returncode != 0:
            errors.append("D-104 blocked implementation no longer verifies")
    return errors


def main() -> int:
    record = load(RECORD)
    schema = load(SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(record, verify_files=True))
    mutants: list[dict[str, Any]] = []
    for field in (
        "target_private_key_use_authorized",
        "stand_access_authorized",
        "runtime_collection_authorized",
        "p4_r_c_or_later_authorized",
        "calibration_pilot_measurement_or_confirmatory_authorized",
    ):
        mutant = copy.deepcopy(record)
        mutant["authority_boundary"][field] = True
        mutants.append(mutant)
    selected = copy.deepcopy(record)
    selected["decisions"][0]["selected_option"] = EXPECTED["D-105"]
    mutants.append(selected)
    fabricated = copy.deepcopy(record)
    fabricated["required_before_runtime_action"]["exact_runtime_action_owner_approval"] = True
    mutants.append(fabricated)
    source_drift = copy.deepcopy(record)
    source_drift["source_commit"] = "0" * 40
    mutants.append(source_drift)
    omitted = copy.deepcopy(record)
    omitted["decisions"].pop()
    mutants.append(omitted)
    statement = copy.deepcopy(record)
    statement["exact_owner_acceptance_template"] = "accept everything"
    mutants.append(statement)
    for index, mutant in enumerate(mutants):
        if not list(validator.iter_errors(mutant)) and not semantic_errors(
            mutant, verify_files=False
        ):
            errors.append(f"negative mutation {index} passed")
    if errors:
        for error in errors:
            print(f"d105-runtime-decision-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "d105-runtime-decision-check: PASS "
        "(D-105..D-108 proposed, 10 negative, key/stand/runtime/P4-R-C authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
