#!/usr/bin/env python3
"""Validate the proposed no-authority Q15-R-P4-K owner decision bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "cf05bbfdfeb92e9f4de438beac7a05f9f77bfc316c8dc3793e76cf2a47f52ff5"
DECISION_IDS = ("D-076", "D-077", "D-078", "D-079")
OWNER_INPUTS = (
    ("OWNER_KEY_SOURCE_MODE_EXISTING_OR_NEW_OFFLINE", "D-076"),
    ("OFFLINE_PRIVATE_KEY_CUSTODY_DOMAIN_AND_CUSTODIAN", "D-077"),
    ("ED25519_PUBLIC_KEY_ARTIFACT_ID_BYTES_AND_SHA256", "D-078"),
    ("ED25519_SHA256_FINGERPRINT", "D-078"),
    ("CANONICAL_ALLOWED_SIGNERS_ARTIFACT_ID_BYTES_AND_SHA256", "D-078"),
    ("ALLOWED_SIGNERS_SOURCE_ABSOLUTE_PATH_FOR_LATER_SETUP", "D-077"),
    ("INDEPENDENT_REVIEW_ARTIFACT_ID_AND_SHA256", "D-078"),
    ("NAMED_AUTHORITY_PRINCIPAL_ISSUE_AND_EXPIRY_UTC", "D-079"),
)
GATES = ("Q15-R-P4-K-D", "Q15-R-P4-K-A", "Q15-R-P4-K-R", "Q15-R-P5")
QUESTIONS = ("P4K-Q1", "P4K-Q2", "P4K-Q3")
EXPECTED_HASHES = {
    "config/q15/q15-r-p4-k.preparation.json": (
        "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
    ),
    "config/q15/q15-r-p4-d-acceptance-v1.json": (
        "1645c2a7fb356272afbf9377b99784e307f54f8a7df5fbb09f46d70edae3c521"
    ),
    "config/q15/q15-r-p4-f-acceptance-v1.json": (
        "ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c"
    ),
    "docs/decisions/0066-q15-r-offline-signer-custody.md": (
        "3177e68ae602d6bc81693c11985a0c5dae239e35a8080ff2dd13efd89a5174cc"
    ),
    "docs/decisions/0070-q15-r-allowed-signers-binding.md": (
        "544e300d04b7bdfb721f8dd10c314977befc2d6d448a84324182349c08e5d6ed"
    ),
}
EXPECTED_OPTIONS = {
    "D-076": (
        "EXISTING_OWNER_CONTROLLED_OFFLINE_ED25519_WITH_COMPLETE_CUSTODY_EVIDENCE",
        "NEW_OFFLINE_ED25519_KEY_CEREMONY_UNDER_LATER_SEPARATE_EXACT_AUTHORIZATION",
        "REMAIN_BLOCKED",
    ),
    "D-077": (
        "OWNER_SUPPLIED_NON_STAND_CUSTODY_DOMAIN_DISTINCT_CUSTODIAN_AND_CREATE_EXCLUSIVE_PUBLIC_ARTIFACT_PATH",
        "REPOSITORY_OR_STAND_PRIVATE_KEY_CUSTODY_OR_INFERRED_PATH",
        "REMAIN_BLOCKED",
    ),
    "D-078": (
        "P4_K_A_ONE_SHOT_OFFLINE_ACQUISITION_AND_PUBLIC_ARTIFACT_CONSTRUCTION_THEN_STOP_FOR_P4_K_R_INDEPENDENT_REVIEW",
        "COMBINE_KEY_ACTION_REVIEW_INSTALLATION_AND_SIGNING",
        "RETRY_OR_REPAIR_IN_PLACE",
        "REMAIN_BLOCKED",
    ),
    "D-079": (
        "CPU_PREFETCH_Q15_OPERATOR_NONRENEWABLE_1800S_JCS_I64_SSHSIG_WITH_DISTINCT_AUDITOR",
        "A_DIFFERENT_OWNER_SUPPLIED_NAMED_AUTHORITY_OR_VALIDITY_POLICY",
        "ROOT_OR_SSH_REACHABILITY_AS_AUTHORITY",
        "UNSIGNED_RENEWABLE_OR_SELF_REVIEWED_ACTION",
        "REMAIN_BLOCKED",
    ),
}


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    proposal_path = root / "config/q15/q15-r-p4-k-decision-input-v1.json"
    if document is load_document_sentinel and sha256(proposal_path) != PROPOSAL_SHA256:
        errors.append("P4-K proposal bytes drifted")

    lineage = document.get("lineage", {})
    bindings = {
        lineage.get("p4_k_preparation_path"): lineage.get("p4_k_preparation_sha256"),
        lineage.get("p4_d_acceptance_path"): lineage.get("p4_d_acceptance_sha256"),
        lineage.get("p4_f_acceptance_path"): lineage.get("p4_f_acceptance_sha256"),
        lineage.get("adr_0066_path"): lineage.get("adr_0066_sha256"),
        lineage.get("adr_0070_path"): lineage.get("adr_0070_sha256"),
    }
    if bindings != EXPECTED_HASHES:
        errors.append("P4-K preparation, acceptance, or ADR lineage drifted")
    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable lineage artifact mismatch: {relative}")

    decisions = document.get("decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISION_IDS:
        errors.append("D-076 through D-079 must be exact, unique, and ordered")
    for item in decisions:
        decision_id = item.get("decision_id")
        if tuple(item.get("options_considered", [])) != EXPECTED_OPTIONS.get(
            decision_id, ()
        ):
            errors.append(f"{decision_id} options drifted")
        if item.get("selected_option") is not None:
            errors.append("owner-dependent P4-K decisions must remain unselected")

    inputs = document.get("owner_input_contract", [])
    actual_inputs = tuple(
        (item.get("name"), item.get("decision_id")) for item in inputs
    )
    if actual_inputs != OWNER_INPUTS:
        errors.append("the eight P4-K inputs and decision mappings must be exact")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in inputs
    ):
        errors.append("P4-K external inputs cannot be fabricated or defaulted")

    p4_k = load(root / "config/q15/q15-r-p4-k.preparation.json")
    p4_k_inputs = tuple(item.get("name") for item in p4_k.get("unresolved_inputs", []))
    if p4_k_inputs != tuple(name for name, _ in OWNER_INPUTS) or any(
        item.get("value") is not None for item in p4_k.get("unresolved_inputs", [])
    ):
        errors.append("the immutable P4-K preparation must retain eight null inputs")
    policy = document.get("fixed_accepted_policy", {})
    p4_k_policy = p4_k.get("fixed_policy", {})
    for name, value in p4_k_policy.items():
        if policy.get(name) != value:
            errors.append(f"accepted P4-K policy drifted: {name}")
    if (
        policy.get("private_key_in_repository_allowed") is not False
        or policy.get("stand_private_key_allowed") is not False
    ):
        errors.append("the private key is prohibited from repository and stand")

    gates = document.get("proposed_gate_graph", [])
    if tuple(item.get("gate_id") for item in gates) != GATES:
        errors.append("P4-K decision, acquisition, review, and setup gates must be split")
    if any(
        not str(item.get("state", "")).startswith(("PROPOSED_", "NOT_PREPARED_"))
        for item in gates
    ):
        errors.append("no P4-K successor gate may be accepted, prepared, or issued")
    if "one future" not in str(gates[1].get("scope", "")) or "distinct" not in str(
        gates[2].get("scope", "")
    ):
        errors.append("P4-K acquisition must be one-shot and independently reviewed")

    questions = document.get("minimum_owner_inputs_before_exact_acceptance", [])
    if tuple(item.get("question_id") for item in questions) != QUESTIONS or any(
        item.get("answer") is not None for item in questions
    ):
        errors.append("the three minimum owner questions must remain exact and unanswered")
    allowed_q1 = tuple(questions[0].get("allowed_answers", [])) if questions else ()
    if allowed_q1 != EXPECTED_OPTIONS["D-076"][:2]:
        errors.append("P4K-Q1 must expose exactly existing-key and new-ceremony modes")

    boundary = document.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {"repository_local_decision_input_bundle_preparation_authorized"}:
        errors.append("P4-K proposal widens authority beyond local decision preparation")

    identity = load(root / "config/q15/q15-r-p4-r-i.authorization-template-v1.json")
    collection = load(root / "config/q15/q15-r-p4-r-c.authorization-template-v1.json")
    if any(
        value is True
        for record in (identity, collection)
        for name, value in record.get("authority_boundary", {}).items()
        if name != "repository_local_unissued_template_creation_authorized"
    ):
        errors.append("P4-K proposal cannot widen P4-R-I or P4-R-C authority")
    return errors


load_document_sentinel: dict[str, Any] = {}


def main() -> int:
    global load_document_sentinel
    root = pathlib.Path(__file__).resolve().parents[1]
    record_path = root / "config/q15/q15-r-p4-k-decision-input-v1.json"
    record = load(record_path)
    load_document_sentinel = record
    schema = load(root / "config/schemas/q15-r-p4-k-decision-input-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))

    negatives: list[dict[str, Any]] = []
    stand = copy.deepcopy(record)
    stand["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(stand)
    key_action = copy.deepcopy(record)
    key_action["authority_boundary"][
        "key_read_generation_import_copy_fingerprint_or_use_authorized"
    ] = True
    negatives.append(key_action)
    selected = copy.deepcopy(record)
    selected["decisions"][0]["selected_option"] = EXPECTED_OPTIONS["D-076"][0]
    negatives.append(selected)
    option = copy.deepcopy(record)
    option["decisions"][0]["options_considered"][0] = "STAND_LOCAL_KEY"
    negatives.append(option)
    filled = copy.deepcopy(record)
    filled["owner_input_contract"][1]["value"] = "invented-custody"
    negatives.append(filled)
    mapping = copy.deepcopy(record)
    mapping["owner_input_contract"][2]["decision_id"] = "D-077"
    negatives.append(mapping)
    gate = copy.deepcopy(record)
    gate["proposed_gate_graph"].pop(2)
    negatives.append(gate)
    issued = copy.deepcopy(record)
    issued["proposed_gate_graph"][1]["state"] = "ISSUED"
    negatives.append(issued)
    answer = copy.deepcopy(record)
    answer["minimum_owner_inputs_before_exact_acceptance"][0]["answer"] = (
        EXPECTED_OPTIONS["D-076"][0]
    )
    negatives.append(answer)
    private_key = copy.deepcopy(record)
    private_key["fixed_accepted_policy"]["private_key_in_repository_allowed"] = True
    negatives.append(private_key)
    lineage = copy.deepcopy(record)
    lineage["lineage"]["p4_k_preparation_sha256"] = "0" * 64
    negatives.append(lineage)
    p4_r = copy.deepcopy(record)
    p4_r["authority_boundary"]["p4_r_i_or_p4_r_c_authorized"] = True
    negatives.append(p4_r)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-k-decision-input-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-k-decision-input-check: PASS "
        "(D-076..D-079 proposed, 8 inputs null, 3 owner questions open, "
        "12 negative, key/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
