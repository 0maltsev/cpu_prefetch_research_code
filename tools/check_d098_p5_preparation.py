#!/usr/bin/env python3
"""Validate the D-097-bound still-unissued P5 preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_UNRESOLVED = (
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
    "CURRENT_STAND_PRESTATE_ARTIFACT_ID_AND_SHA256",
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field in (
        ("predecessor_path", "predecessor_sha256"),
        ("d097_complete_evidence_path", "d097_complete_evidence_sha256"),
    ):
        path = root / str(lineage.get(path_field, ""))
        if not path.is_file() or sha256(path) != lineage.get(hash_field):
            errors.append(f"lineage mismatch: {path_field}")
    resolved = record.get("resolved_input_groups", [])
    if tuple(item.get("name") for item in resolved) != (
        "ALLOWED_SIGNERS_SOURCE",
        "ACTUAL_ALLOWED_SIGNERS_ARTIFACT_ID_SHA256_AND_ED25519_FINGERPRINT",
    ):
        errors.append("only the two D-097 public groups may be resolved")
    unresolved = record.get("remaining_required_inputs", [])
    if tuple(item.get("name") for item in unresolved) != EXPECTED_UNRESOLVED:
        errors.append("exact three remaining P5 inputs are required")
    if any(item.get("state") != "UNRESOLVED" or item.get("value") is not None for item in unresolved):
        errors.append("P5 preparation fabricated an external input")
    future = record.get("future_authorization_contract", {})
    if future.get("status") != "NOT_ISSUED" or any(
        future.get(field) is not None for field in (
            "authorization_id", "authorization_sha256", "issued_at_utc",
            "expires_at_utc", "signature_sha256", "independent_review_sha256",
        )
    ):
        errors.append("P5 preparation was prematurely issued")
    transaction = record.get("transaction_contract", {})
    if tuple(transaction.get(field) for field in (
        "setup_command_count", "access_probe_count", "required_denial_count", "rollback_command_count",
    )) != (20, 24, 18, 10):
        errors.append("accepted P5 command/test/denial/rollback counts drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {"repository_local_successor_preparation_authorized"}:
        errors.append("still-unissued P5 authority widened")
    if "id_ed25519" in json.dumps(record):
        errors.append("P5 preparation contains a private-key path")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = json.loads((root / "config/q15/q15-r-stand-setup-authorization.preparation-v3.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "config/schemas/q15-r-stand-setup-authorization-preparation-v3.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    for index, (section, field, value) in enumerate((
        ("authority_boundary", "stand_access_authorized", True),
        ("authority_boundary", "p5_authorized", True),
        ("authority_boundary", "trust_anchor_installation_or_activation_authorized", True),
        ("authority_boundary", "p4_r_i_or_p4_r_c_authorized", True),
        ("future_authorization_contract", "authorization_id", "PREMATURE"),
    )):
        mutant = copy.deepcopy(record)
        mutant[section][field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    mutant = copy.deepcopy(record)
    mutant["remaining_required_inputs"][0]["value"] = "/invented"
    mutant["remaining_required_inputs"][0]["state"] = "RESOLVED"
    if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
        errors.append("negative fabricated-input mutation passed")
    if errors:
        for error in errors:
            print(f"d098-p5-preparation-check: FAIL: {error}", file=sys.stderr)
        return 1
    print("d098-p5-preparation-check: PASS (2 D-097 groups resolved, 3 null, 6 negative, P5 authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
