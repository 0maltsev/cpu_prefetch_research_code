#!/usr/bin/env python3
"""Validate the still-unissued D-096-bound P4-K-R preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_UNRESOLVED = (
    "D097_REVIEW_SEPARATION_OR_EXPLICIT_SINGLE_OWNER_WAIVER",
    "D097_REVIEW_PRINCIPAL_AND_EXACT_CREATE_EXCLUSIVE_OUTPUT_ROOT",
    "P4_K_R_EXACT_REVIEW_TOOL_IDS_VERSIONS_SHA256_AND_FIXED_ARGV",
    "P4_K_R_LITERAL_ISSUE_EXPIRY_AUTHORIZATION_SIGNATURE_AND_PRE_REVIEW_HASHES",
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field in (
        ("predecessor_template_path", "predecessor_template_sha256"),
        ("d095_terminal_evidence_path", "d095_terminal_evidence_sha256"),
        ("d096_decision_adr_path", "d096_decision_adr_sha256"),
        ("d096_complete_evidence_path", "d096_complete_evidence_sha256"),
    ):
        candidate = root / str(lineage.get(path_field, ""))
        if not candidate.is_file() or sha256(candidate) != lineage.get(hash_field):
            errors.append(f"lineage mismatch: {path_field}")
    unresolved = record.get("unresolved_inputs", [])
    if tuple(item.get("name") for item in unresolved) != EXPECTED_UNRESOLVED:
        errors.append("exact four D-097 unresolved inputs are required in order")
    if any(item.get("value") is not None for item in unresolved):
        errors.append("D-097 preparation fabricated a review input")
    if any(item.get("value") is not None for item in record.get("prospective_outputs", [])):
        errors.append("D-097 preparation fabricated a review output")
    gate = record.get("gate", {})
    nullable = (
        "review_principal", "review_separation_policy", "review_output_root_absolute_path",
        "authorization_id", "authorization_sha256", "issued_at_utc", "expires_at_utc",
        "detached_signature_sha256", "pre_execution_review_sha256",
    )
    if any(gate.get(field) is not None for field in nullable):
        errors.append("D-097 preparation was prematurely specialized or issued")
    contract = record.get("fixed_review_contract", {})
    if (
        contract.get("private_key_read_hash_copy_use_or_presence_probe_allowed") is not False
        or contract.get("review_scope_public_evidence_only") is not True
        or contract.get("review_attempt_count") != 1
        or contract.get("retry_count") != 0
        or contract.get("automatic_continuation_to_p5_p4_r_or_q15") is not False
    ):
        errors.append("public-only one-attempt stop contract drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {"repository_local_unissued_successor_preparation_authorized"}:
        errors.append("still-unissued P4-K-R authority widened")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-k-r.authorization-template-v2.json")
    schema = load(root / "config/schemas/q15-r-p4-k-r-authorization-template-v2.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    for index, (section, field, value) in enumerate((
        ("gate", "authorization_id", "PREMATURE"),
        ("fixed_review_contract", "private_key_read_hash_copy_use_or_presence_probe_allowed", True),
        ("fixed_review_contract", "retry_count", 1),
        ("authority_boundary", "p4_k_r_authorized", True),
        ("authority_boundary", "stand_access_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        mutant[section][field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    mutant = copy.deepcopy(record)
    mutant["unresolved_inputs"][0]["value"] = "INVENTED"
    if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
        errors.append("negative fabricated-input mutation passed")
    if errors:
        for error in errors:
            print(f"d097-p4-k-r-preparation-check: FAIL: {error}", file=sys.stderr)
        return 1
    print("d097-p4-k-r-preparation-check: PASS (D-096 bound, 4 null inputs, 6 negative, P4-K-R authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
