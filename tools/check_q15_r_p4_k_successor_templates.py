#!/usr/bin/env python3
"""Validate still-unissued split P4-K-A/P4-K-R templates."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


ACCEPTANCE_SHA256 = "11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7"
P4_K_A_SHA256 = "7669a2f693a7ffca3fa583ec3ed7a45e1ea130a51ee009ac33a77b936409ccb5"
P4_K_R_SHA256 = "ae71ce73cf0636294995c0ca3311d4ccf6f857916c07fe9df67bb9682d20efcf"
ADR_BINDINGS = (
    ("D-076", "docs/decisions/0076-q15-r-p4-k-new-offline-key-ceremony.md", "449113f623f1c5b9dd221c579545d9fce980cfc1bad26eed95331c5eddd247fa"),
    ("D-077", "docs/decisions/0077-q15-r-p4-k-custody-identifiers.md", "97b3815229e700869b56133d4a83626a5015710f902440a76ea1de86507198b1"),
    ("D-078", "docs/decisions/0078-q15-r-p4-k-split-acquisition-review.md", "984e1ddc95021cfe3f22d0696f907c10de2fd45f5fcf6a0f6f3dcbc4fae10ac5"),
    ("D-079", "docs/decisions/0079-q15-r-p4-k-authority-validity.md", "90dd4dd47ed5e49b10fdf923bd0b32b099dd5fea22ea9152c908d16e07313fd0"),
)
A_OUTPUTS = (
    "ED25519_PUBLIC_KEY_ARTIFACT_ID_BYTES_AND_SHA256",
    "ED25519_SHA256_FINGERPRINT",
    "CANONICAL_ALLOWED_SIGNERS_ARTIFACT_ID_BYTES_AND_SHA256",
    "ALLOWED_SIGNERS_SOURCE_ABSOLUTE_PATH_FOR_LATER_SETUP",
    "OFFLINE_CUSTODY_EVIDENCE_ARTIFACT_ID_AND_SHA256_WITHOUT_PRIVATE_PATH_OR_BYTES",
    "P4_K_A_COMPLETE_OR_PARTIAL_ACTION_RECEIPT_ID_AND_SHA256",
)
A_INPUTS = (
    "EXACT_OFFLINE_CEREMONY_AND_PUBLIC_EXTRACTION_TOOL_IDS_VERSIONS_SHA256_AND_FIXED_ARGV",
    "CREATE_EXCLUSIVE_PUBLIC_ARTIFACT_IDS_AND_ABSOLUTE_SOURCE_PATHS",
    "OFFLINE_CUSTODY_CONTROL_AND_CEREMONY_ENVIRONMENT_EVIDENCE_ID_AND_SHA256",
    "BOOTSTRAP_AUTHORIZATION_SIGNER_FINGERPRINT_AND_TRUST_EVIDENCE_SHA256",
    "LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS",
    "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
    "DISTINCT_AUDITOR_PRE_EXECUTION_REVIEW_ARTIFACT_ID_AND_SHA256",
)
R_INPUTS = (
    "ACCEPTED_COMPLETE_P4_K_A_ACTION_RECEIPT_ID_AND_SHA256",
    "ED25519_PUBLIC_KEY_ARTIFACT_ID_BYTES_AND_SHA256",
    "ED25519_SHA256_FINGERPRINT",
    "CANONICAL_ALLOWED_SIGNERS_ARTIFACT_ID_BYTES_SHA256_AND_ABSOLUTE_PUBLIC_SOURCE_PATH",
    "OFFLINE_CUSTODY_EVIDENCE_ARTIFACT_ID_AND_SHA256_WITHOUT_PRIVATE_PATH_OR_BYTES",
    "P4_K_R_EXACT_REVIEW_TOOL_IDS_VERSIONS_SHA256_AND_FIXED_ARGV",
    "BOOTSTRAP_AUTHORIZATION_SIGNER_FINGERPRINT_TRUST_AUTHORIZATION_SIGNATURE_AND_UTC_EVIDENCE",
)
R_OUTPUTS = (
    "INDEPENDENT_P4_K_REVIEW_ARTIFACT_ID_AND_SHA256",
    "ACCEPTED_P4_K_TRUST_ANCHOR_EVIDENCE_RECORD_ID_AND_SHA256",
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def null_names(items: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(item.get("name", "") for item in items)


def semantic_errors(
    root: pathlib.Path, acquisition: dict[str, Any], review: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    acceptance_path = root / "config/q15/q15-r-p4-k-d-acceptance-v1.json"
    if not acceptance_path.is_file() or sha256(acceptance_path) != ACCEPTANCE_SHA256:
        errors.append("P4-K templates must bind the exact P4-K-D acceptance")

    for record in (acquisition, review):
        lineage = record.get("lineage", {})
        if lineage.get("acceptance_sha256") != ACCEPTANCE_SHA256:
            errors.append("P4-K template acceptance lineage drifted")
        actual_adrs = tuple(
            (item.get("decision_id"), item.get("path"), item.get("sha256"))
            for item in lineage.get("adr_bindings", [])
        )
        if actual_adrs != ADR_BINDINGS:
            errors.append("P4-K template ADR bindings must be exact and ordered")
        for _, path_text, expected_hash in ADR_BINDINGS:
            path = root / path_text
            if not path.is_file() or sha256(path) != expected_hash:
                errors.append(f"P4-K ADR bytes drifted: {path_text}")
        gate = record.get("gate", {})
        if (
            gate.get("source_mode")
            != "NEW_OFFLINE_ED25519_KEY_CEREMONY_UNDER_LATER_SEPARATE_EXACT_AUTHORIZATION"
            or gate.get("custody_domain_id") != "OWNER-OFFLINE-Q15-KEY-CUSTODY"
            or gate.get("custodian_principal_id") != "cpu-prefetch-q15-custodian"
            or gate.get("named_authority_principal") != "cpu-prefetch-q15-operator"
            or gate.get("independent_review_principal") != "cpu-prefetch-q15-auditor"
        ):
            errors.append("P4-K source, custody, authority, or reviewer drifted")
        if len(
            {
                gate.get("custodian_principal_id"),
                gate.get("named_authority_principal"),
                gate.get("independent_review_principal"),
            }
        ) != 3:
            errors.append("P4-K authority, custodian, and reviewer must be distinct")
        nullable_gate_fields = (
            "authorization_id",
            "authorization_sha256",
            "issued_at_utc",
            "expires_at_utc",
            "bootstrap_authorization_signer_fingerprint",
            "bootstrap_authorization_trust_evidence_sha256",
            "detached_signature_sha256",
            "pre_execution_independent_review_sha256",
        )
        if any(gate.get(name) is not None for name in nullable_gate_fields):
            errors.append("P4-K template cannot fabricate authorization evidence")
        boundary = record.get("authority_boundary", {})
        enabled = {
            name
            for name, value in boundary.items()
            if name.endswith("_authorized") and value
        }
        if enabled != {"repository_local_unissued_template_creation_authorized"}:
            errors.append("P4-K template widens authority beyond local preparation")

    if review.get("lineage", {}).get("p4_k_a_template_sha256") != P4_K_A_SHA256:
        errors.append("P4-K-R must bind the exact still-unissued P4-K-A template")
    acquisition_path = root / "config/q15/q15-r-p4-k-a.authorization-template-v1.json"
    if not acquisition_path.is_file() or sha256(acquisition_path) != P4_K_A_SHA256:
        errors.append("P4-K-A template bytes drifted")

    if null_names(acquisition.get("prospective_outputs", [])) != A_OUTPUTS or any(
        item.get("value") is not None for item in acquisition.get("prospective_outputs", [])
    ):
        errors.append("P4-K-A prospective outputs must remain exact and null")
    if null_names(acquisition.get("unresolved_inputs", [])) != A_INPUTS or any(
        item.get("value") is not None for item in acquisition.get("unresolved_inputs", [])
    ):
        errors.append("P4-K-A unresolved inputs must remain exact and null")
    if null_names(review.get("required_evidence", [])) != R_INPUTS or any(
        item.get("value") is not None for item in review.get("required_evidence", [])
    ):
        errors.append("P4-K-R required evidence must remain exact and null")
    if null_names(review.get("prospective_outputs", [])) != R_OUTPUTS or any(
        item.get("value") is not None for item in review.get("prospective_outputs", [])
    ):
        errors.append("P4-K-R outputs must remain exact and null")

    a_contract = acquisition.get("fixed_action_contract", {})
    if (
        a_contract.get("target_key_may_authorize_its_own_creation") is not False
        or a_contract.get("action_attempt_count") != 1
        or a_contract.get("retry_count") != 0
        or a_contract.get("automatic_continuation_to_p4_k_r") is not False
        or a_contract.get("installation_or_q15_signing_allowed") is not False
    ):
        errors.append("P4-K-A one-shot stop boundary drifted")
    r_contract = review.get("fixed_review_contract", {})
    if (
        r_contract.get("reviewer_must_differ_from_authority_and_custodian") is not True
        or r_contract.get("private_key_read_or_presence_allowed") is not False
        or r_contract.get("review_attempt_count") != 1
        or r_contract.get("retry_count") != 0
        or r_contract.get("mutation_installation_or_signing_allowed") is not False
        or r_contract.get("automatic_continuation_to_p5_p4_r_or_q15") is not False
    ):
        errors.append("P4-K-R read-only independent stop boundary drifted")
    if review.get("gate", {}).get("required_complete_p4_k_a_receipt_sha256") is not None:
        errors.append("P4-K-R cannot fabricate its required P4-K-A predecessor")

    predecessor = load(root / "config/q15/q15-r-p4-k.preparation.json")
    if len(predecessor.get("unresolved_inputs", [])) != 8 or any(
        item.get("value") is not None for item in predecessor.get("unresolved_inputs", [])
    ):
        errors.append("immutable predecessor P4-K must retain eight null inputs")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    a_path = root / "config/q15/q15-r-p4-k-a.authorization-template-v1.json"
    r_path = root / "config/q15/q15-r-p4-k-r.authorization-template-v1.json"
    acquisition = load(a_path)
    review = load(r_path)
    a_schema = load(root / "config/schemas/q15-r-p4-k-a-authorization-template-v1.schema.json")
    r_schema = load(root / "config/schemas/q15-r-p4-k-r-authorization-template-v1.schema.json")
    Draft202012Validator.check_schema(a_schema)
    Draft202012Validator.check_schema(r_schema)
    a_validator = Draft202012Validator(a_schema)
    r_validator = Draft202012Validator(r_schema)
    errors = [item.message for item in a_validator.iter_errors(acquisition)]
    errors.extend(item.message for item in r_validator.iter_errors(review))
    errors.extend(semantic_errors(root, acquisition, review))
    if sha256(a_path) != P4_K_A_SHA256 or sha256(r_path) != P4_K_R_SHA256:
        errors.append("P4-K-A or P4-K-R template bytes drifted")

    negatives: list[tuple[dict[str, Any], dict[str, Any]]] = []
    authority_a = copy.deepcopy(acquisition)
    authority_a["authority_boundary"]["p4_k_a_authorized"] = True
    negatives.append((authority_a, copy.deepcopy(review)))
    authority_r = copy.deepcopy(review)
    authority_r["authority_boundary"]["p4_k_r_authorized"] = True
    negatives.append((copy.deepcopy(acquisition), authority_r))
    filled = copy.deepcopy(acquisition)
    filled["unresolved_inputs"][0]["value"] = "invented-tool"
    negatives.append((filled, copy.deepcopy(review)))
    source = copy.deepcopy(acquisition)
    source["gate"]["source_mode"] = "EXISTING_KEY"
    negatives.append((source, copy.deepcopy(review)))
    domain = copy.deepcopy(review)
    domain["gate"]["custody_domain_id"] = "STAND"
    negatives.append((copy.deepcopy(acquisition), domain))
    self_authorize = copy.deepcopy(acquisition)
    self_authorize["fixed_action_contract"]["target_key_may_authorize_its_own_creation"] = True
    negatives.append((self_authorize, copy.deepcopy(review)))
    retry = copy.deepcopy(acquisition)
    retry["fixed_action_contract"]["retry_count"] = 1
    negatives.append((retry, copy.deepcopy(review)))
    continue_a = copy.deepcopy(acquisition)
    continue_a["fixed_action_contract"]["automatic_continuation_to_p4_k_r"] = True
    negatives.append((continue_a, copy.deepcopy(review)))
    install = copy.deepcopy(review)
    install["fixed_review_contract"]["mutation_installation_or_signing_allowed"] = True
    negatives.append((copy.deepcopy(acquisition), install))
    private = copy.deepcopy(review)
    private["fixed_review_contract"]["private_key_read_or_presence_allowed"] = True
    negatives.append((copy.deepcopy(acquisition), private))
    collapse = copy.deepcopy(review)
    collapse["gate"]["independent_review_principal"] = "cpu-prefetch-q15-operator"
    negatives.append((copy.deepcopy(acquisition), collapse))
    lineage = copy.deepcopy(review)
    lineage["lineage"]["p4_k_a_template_sha256"] = "0" * 64
    negatives.append((copy.deepcopy(acquisition), lineage))
    receipt = copy.deepcopy(review)
    receipt["gate"]["required_complete_p4_k_a_receipt_sha256"] = "0" * 64
    negatives.append((copy.deepcopy(acquisition), receipt))
    issued = copy.deepcopy(acquisition)
    issued["gate"]["authorization_id"] = "ISSUED"
    negatives.append((issued, copy.deepcopy(review)))

    for index, (a_mutant, r_mutant) in enumerate(negatives):
        mutant_errors = [item.message for item in a_validator.iter_errors(a_mutant)]
        mutant_errors.extend(item.message for item in r_validator.iter_errors(r_mutant))
        mutant_errors.extend(semantic_errors(root, a_mutant, r_mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-k-successor-templates-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-k-successor-templates-check: PASS "
        "(P4-K-A/P4-K-R split, 13+9 null fields, 14 negative, issued=NO, "
        "key/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
