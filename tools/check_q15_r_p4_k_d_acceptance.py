#!/usr/bin/env python3
"""Validate Q15-R-P4-K-D delegated choices without operational authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5"
ACCEPTANCE_SHA256 = "11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7"
P4_K_SHA256 = "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
P4_R_I_SHA256 = "38223ea7ff54b3a0ae748f670fcfd00a723272b03211e4eddda997d5b603f1d8"
P4_R_C_SHA256 = "22d4aa6f4c4ffa60c3fb31c08f3eea4831a790a0b46907b2aab5af3dcc0377df"
DECISIONS = (
    (
        "D-076",
        "NEW_OFFLINE_ED25519_KEY_CEREMONY_UNDER_LATER_SEPARATE_EXACT_AUTHORIZATION",
    ),
    (
        "D-077",
        "OWNER_SUPPLIED_NON_STAND_CUSTODY_DOMAIN_DISTINCT_CUSTODIAN_AND_CREATE_EXCLUSIVE_PUBLIC_ARTIFACT_PATH",
    ),
    (
        "D-078",
        "P4_K_A_ONE_SHOT_OFFLINE_ACQUISITION_AND_PUBLIC_ARTIFACT_CONSTRUCTION_THEN_STOP_FOR_P4_K_R_INDEPENDENT_REVIEW",
    ),
    (
        "D-079",
        "CPU_PREFETCH_Q15_OPERATOR_NONRENEWABLE_1800S_JCS_I64_SSHSIG_WITH_DISTINCT_AUDITOR",
    ),
)
USER_MESSAGES = ("I accept any og your choices.", "do it")
BOUNDARY = (
    "Select the recommended D-076 through D-079 options and non-secret logical "
    "identifiers for repository-local acceptance, ADRs, and still-unissued "
    "P4-K-A/P4-K-R templates only, under the immediately preceding explicit "
    "prohibition on key, artifact, stand, signature, issuance, setup, Q15, "
    "calibration, pilot, measurement, and confirmatory actions."
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    binding = record.get("decision_input_binding", {})
    proposal_path = root / str(binding.get("path", ""))
    if (
        binding.get("sha256") != PROPOSAL_SHA256
        or not proposal_path.is_file()
        or sha256(proposal_path) != PROPOSAL_SHA256
    ):
        errors.append("P4-K-D acceptance must bind the immutable proposal")

    selected = tuple(
        (item.get("decision_id"), item.get("selected_option"))
        for item in record.get("accepted_decisions", [])
    )
    if selected != DECISIONS:
        errors.append("D-076 through D-079 selections must be exact and ordered")
    proposal = load(proposal_path) if proposal_path.is_file() else {}
    proposed_options = {
        item.get("decision_id"): item.get("options_considered", [])
        for item in proposal.get("decisions", [])
    }
    if any(option not in proposed_options.get(decision_id, []) for decision_id, option in selected):
        errors.append("acceptance selects an option absent from the proposal")

    owner = record.get("delegated_owner_choice", {})
    if (
        owner.get("key_source_mode") != DECISIONS[0][1]
        or owner.get("custody_domain_id") != "OWNER-OFFLINE-Q15-KEY-CUSTODY"
        or owner.get("custodian_principal_id") != "cpu-prefetch-q15-custodian"
        or owner.get("custody_domain_is_logical_identifier_only") is not True
        or owner.get("custody_domain_operational_existence_or_control_verified")
        is not False
        or owner.get("private_key_or_public_artifact_evidence_present") is not False
        or owner.get("private_key_path_or_secret_recorded") is not False
    ):
        errors.append("delegated choices must remain logical-only with no external evidence")

    if tuple(record.get("user_acceptance_messages", [])) != USER_MESSAGES:
        errors.append("exact owner acceptance messages drifted")
    if record.get("bounded_interpretation") != BOUNDARY:
        errors.append("the no-authority interpretation boundary drifted")

    selection = record.get("selection_effect", {})
    prohibited_effects = (
        "key_read_generated_imported_copied_fingerprinted_or_used",
        "public_key_or_allowed_signers_artifact_created",
        "custody_or_public_artifact_path_created",
        "authorization_signed_or_issued",
    )
    if any(selection.get(name) is not False for name in prohibited_effects):
        errors.append("acceptance cannot claim a key, artifact, path, signature, or issuance")

    boundary = record.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {
        "repository_local_acceptance_adr_and_unissued_template_creation_authorized"
    }:
        errors.append("P4-K-D widens authority beyond repository-local records")

    preservation = record.get("predecessor_preservation", {})
    predecessors = (
        ("p4_k_preparation_path", "p4_k_preparation_sha256", P4_K_SHA256),
        ("p4_r_i_template_path", "p4_r_i_template_sha256", P4_R_I_SHA256),
        ("p4_r_c_template_path", "p4_r_c_template_sha256", P4_R_C_SHA256),
    )
    for path_name, hash_name, expected_hash in predecessors:
        path = root / str(preservation.get(path_name, ""))
        if (
            preservation.get(hash_name) != expected_hash
            or not path.is_file()
            or sha256(path) != expected_hash
        ):
            errors.append(f"immutable predecessor mismatch: {path_name}")

    p4_k = load(root / "config/q15/q15-r-p4-k.preparation.json")
    if len(p4_k.get("unresolved_inputs", [])) != 8 or any(
        item.get("value") is not None for item in p4_k.get("unresolved_inputs", [])
    ):
        errors.append("the predecessor P4-K record must retain eight null inputs")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-p4-k-d-acceptance-v1.json"
    record = load(path)
    schema = load(root / "config/schemas/q15-r-p4-k-d-acceptance-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    if sha256(path) != ACCEPTANCE_SHA256:
        errors.append("P4-K-D acceptance bytes drifted")

    negatives: list[dict[str, Any]] = []
    stand = copy.deepcopy(record)
    stand["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(stand)
    key = copy.deepcopy(record)
    key["authority_boundary"]["key_read_generation_import_copy_fingerprint_or_use_authorized"] = True
    negatives.append(key)
    source = copy.deepcopy(record)
    source["accepted_decisions"][0]["selected_option"] = (
        "EXISTING_OWNER_CONTROLLED_OFFLINE_ED25519_WITH_COMPLETE_CUSTODY_EVIDENCE"
    )
    negatives.append(source)
    domain = copy.deepcopy(record)
    domain["delegated_owner_choice"]["custody_domain_id"] = "INVENTED-STAND-DOMAIN"
    negatives.append(domain)
    verified = copy.deepcopy(record)
    verified["delegated_owner_choice"]["custody_domain_operational_existence_or_control_verified"] = True
    negatives.append(verified)
    evidence = copy.deepcopy(record)
    evidence["delegated_owner_choice"]["private_key_or_public_artifact_evidence_present"] = True
    negatives.append(evidence)
    issuance = copy.deepcopy(record)
    issuance["selection_effect"]["authorization_signed_or_issued"] = True
    negatives.append(issuance)
    predecessor = copy.deepcopy(record)
    predecessor["predecessor_preservation"]["p4_k_preparation_sha256"] = "0" * 64
    negatives.append(predecessor)
    message = copy.deepcopy(record)
    message["user_acceptance_messages"][1] = "issue it"
    negatives.append(message)
    interpretation = copy.deepcopy(record)
    interpretation["bounded_interpretation"] += " Execute the ceremony."
    negatives.append(interpretation)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-k-d-acceptance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-k-d-acceptance-check: PASS "
        "(D-076..D-079 accepted, logical custody only, 10 negative, "
        "key/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
