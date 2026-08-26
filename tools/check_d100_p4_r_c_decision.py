#!/usr/bin/env python3
"""Validate the no-action D-100 through D-103 P4-R-C decision bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tarfile
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
RECORD_PATH = ROOT / "config/q15/q15-r-p4-r-c-d100-decision-input-v1.json"
SCHEMA_PATH = ROOT / "config/schemas/q15-r-p4-r-c-d100-decision-input-v1.schema.json"

EXPECTED_DECISIONS = {
    "D-100": "ACCEPT_SINGLE_OWNER_OPERATOR_CUSTODIAN_AUDITOR_COLLAPSE_FOR_ONE_P4_R_C",
    "D-101": (
        "ALLOW_ONLY_THE_EXACT_VERIFIED_D099_CUSTODY_ROOT_AND_REQUIRE_EVERY_"
        "P4_R_C_OUTPUT_TO_BE_ABSENT_AND_CREATE_EXCLUSIVE"
    ),
    "D-102": (
        "ACCEPT_ONLY_PRECOMPUTED_HASH_BOUND_CONSTANT_REMOTE_COMMAND_STRINGS_WITH_"
        "LOCAL_SHELL_FALSE_NO_USER_INTERPOLATION_AND_STRICT_TOKEN_VALIDATION"
    ),
    "D-103": (
        "AUTHORIZE_CREATE_EXCLUSIVE_MODE_0700_NAMESPACE_PARENT_IF_ABSENT_AND_"
        "REQUIRE_EXACT_ROOT_OWNED_NONSYMLINK_STATE_IF_PRESENT"
    ),
}

EXPECTED_ACTION = {
    "transaction_id": "Q15-R-P4-R-C-D100-XEON-CPU-FETCH-20260826-01",
    "capture_id": "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01",
    "authorization_validity_seconds": 1800,
    "external_watchdog_seconds": 900,
    "target_key_sshsig_attempts": 1,
    "archive_transfer_attempts": 1,
    "sidecar_transfer_attempts": 1,
    "collector_self_test_attempts": 1,
    "collector_contract_description_attempts": 1,
    "collector_attempts": 1,
    "review_attempts": 1,
    "retry_count": 0,
    "stand_namespace_parent": "/root/cpu-prefetch-q15-r-p4-r",
    "stand_transaction_root": (
        "/root/cpu-prefetch-q15-r-p4-r/"
        "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
    ),
    "stand_incoming_root": (
        "/root/cpu-prefetch-q15-r-p4-r/"
        "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01/incoming"
    ),
    "stand_extraction_parent": (
        "/root/cpu-prefetch-q15-r-p4-r/"
        "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01/release"
    ),
    "custody_root": (
        "/home/omaltsev/research/cpu_prefetch_research_code/docs/evidence/stage17/"
        "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
    ),
    "rollback": "STOP_RETAIN_NO_DELETE_NO_OVERWRITE_NO_REUSE_NO_AUTOMATIC_CLEANUP",
    "mandatory_stop": (
        "STOP_BEFORE_P5_Q15_R_Q15_W_PLATFORM_CONTROL_CALIBRATION_PILOT_"
        "MEASUREMENT_AND_CONFIRMATORY_WORK"
    ),
}

EXPECTED_AUTHORITY = {
    "repository_local_decision_preparation_authorized": True,
    "repository_local_executor_implementation_authorized": False,
    "target_private_key_use_authorized": False,
    "signing_or_authorization_issuance_authorized": False,
    "stand_access_authorized": False,
    "stand_filesystem_mutation_authorized": False,
    "archive_or_sidecar_transfer_authorized": False,
    "bundle_extraction_authorized": False,
    "collector_self_test_or_description_authorized": False,
    "collector_execution_authorized": False,
    "p4_r_c_authorized": False,
    "p5_or_q15_r_or_q15_w_authorized": False,
    "platform_controls_authorized": False,
    "calibration_pilot_measurement_or_confirmatory_authorized": False,
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(record: dict[str, Any]) -> list[str]:
    schema = load(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(record)]


def safe_archive_errors(path: pathlib.Path, expected_size: int, expected_hash: str) -> list[str]:
    errors: list[str] = []
    if not path.is_file():
        return ["exact local v3 archive is absent"]
    if path.stat().st_size != expected_size or sha256(path) != expected_hash:
        return ["exact local v3 archive size or SHA-256 drifted"]
    expected_root = "cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1"
    try:
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exception:
        return [f"v3 archive cannot be inspected: {exception}"]
    if not members:
        errors.append("v3 archive is empty")
    for member in members:
        pure = pathlib.PurePosixPath(member.name)
        if (
            pure.is_absolute()
            or not pure.parts
            or pure.parts[0] != expected_root
            or ".." in pure.parts
            or member.issym()
            or member.islnk()
            or member.isdev()
            or member.isfifo()
        ):
            errors.append(f"unsafe or unexpected v3 archive member: {member.name}")
            break
    return errors


def semantic_errors(record: dict[str, Any], verify_files: bool = True) -> list[str]:
    errors: list[str] = []
    decisions = record.get("conflicts_requiring_decision", [])
    identifiers = [item.get("decision_id") for item in decisions if isinstance(item, dict)]
    if identifiers != list(EXPECTED_DECISIONS):
        errors.append("D-100 through D-103 must be unique and ordered")
    for item in decisions:
        if not isinstance(item, dict):
            continue
        identifier = item.get("decision_id")
        if identifier in EXPECTED_DECISIONS:
            if item.get("recommended_option") != EXPECTED_DECISIONS[identifier]:
                errors.append(f"{identifier} recommendation drifted")
            if item.get("recommended_option") not in item.get("options", []):
                errors.append(f"{identifier} recommendation is not an offered option")
            if item.get("selected_option") is not None:
                errors.append(f"{identifier} was selected without exact owner acceptance")
    if record.get("frozen_action_if_accepted") != EXPECTED_ACTION:
        errors.append("proposed one-shot action identity, bounds, paths, or stop drifted")
    authority = record.get("authority_boundary", {})
    if authority != EXPECTED_AUTHORITY:
        errors.append("D-100 proposal omitted or widened no-action authority")
    prerequisites = record.get("required_before_action", {})
    if len(prerequisites) != 7 or any(prerequisites.values()):
        errors.append("D-100 proposal fabricated a completed action prerequisite")
    statement = record.get("exact_owner_acceptance_template", "")
    for token in (
        "@DECISION_INPUT_SHA256@",
        "909b698a071203adb97746511b97a9316dd55f07",
        "afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241",
        "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a",
        "Do not use keys",
        "later separately signed and explicitly approved authorization",
    ):
        if token not in statement:
            errors.append(f"exact acceptance template omits required boundary: {token}")
    if verify_files:
        inputs = record.get("immutable_inputs", {})
        local_bindings = (
            ("p4_r_c_template_path", "p4_r_c_template_sha256"),
            ("d099_complete_evidence_path", "d099_complete_evidence_sha256"),
            ("d099_identity_path", "d099_identity_sha256"),
            ("d099_review_path", "d099_review_sha256"),
            ("archive_sidecar_path", "archive_sidecar_sha256"),
            ("pinned_hosts_path", "pinned_hosts_sha256"),
            ("transport_public_evidence_path", "transport_public_evidence_sha256"),
        )
        for path_field, digest_field in local_bindings:
            path_value = inputs.get(path_field)
            expected = inputs.get(digest_field)
            if not isinstance(path_value, str) or not isinstance(expected, str):
                errors.append(f"incomplete immutable binding: {path_field}")
                continue
            path = ROOT / path_value
            if not path.is_file() or sha256(path) != expected:
                errors.append(f"immutable input mismatch: {path_field}")
        archive_value = inputs.get("archive_path")
        if isinstance(archive_value, str):
            errors.extend(
                safe_archive_errors(
                    ROOT / archive_value,
                    inputs.get("archive_size", -1),
                    inputs.get("archive_sha256", ""),
                )
            )
    return errors


def main() -> int:
    record = load(RECORD_PATH)
    errors = schema_errors(record)
    errors.extend(semantic_errors(record))
    d099 = subprocess.run(
        [sys.executable, str(ROOT / "tools/check_d099_p4_r_i_complete.py")],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if d099.returncode != 0:
        errors.append("D-099 predecessor evidence no longer verifies")

    mutants: list[dict[str, Any]] = []
    for field in (
        "stand_access_authorized",
        "stand_filesystem_mutation_authorized",
        "target_private_key_use_authorized",
        "p4_r_c_authorized",
        "collector_execution_authorized",
    ):
        mutant = copy.deepcopy(record)
        mutant["authority_boundary"][field] = True
        mutants.append(mutant)
    selected = copy.deepcopy(record)
    selected["conflicts_requiring_decision"][0]["selected_option"] = EXPECTED_DECISIONS["D-100"]
    mutants.append(selected)
    retry = copy.deepcopy(record)
    retry["frozen_action_if_accepted"]["retry_count"] = 1
    mutants.append(retry)
    path_drift = copy.deepcopy(record)
    path_drift["frozen_action_if_accepted"]["stand_transaction_root"] += "-alternate"
    mutants.append(path_drift)
    custody_drift = copy.deepcopy(record)
    custody_drift["frozen_action_if_accepted"]["custody_root"] = "/tmp/q15"
    mutants.append(custody_drift)
    omission = copy.deepcopy(record)
    omission["conflicts_requiring_decision"].pop()
    mutants.append(omission)
    fabricated = copy.deepcopy(record)
    fabricated["required_before_action"]["fresh_1800_second_canonical_authorization_created"] = True
    mutants.append(fabricated)
    statement_drift = copy.deepcopy(record)
    statement_drift["exact_owner_acceptance_template"] = "accept everything"
    mutants.append(statement_drift)

    for index, mutant in enumerate(mutants):
        if not schema_errors(mutant) and not semantic_errors(mutant, verify_files=False):
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"d100-p4-r-c-decision-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "d100-p4-r-c-decision-check: PASS "
        "(D-100..D-103 proposed, 12 negative, action authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
