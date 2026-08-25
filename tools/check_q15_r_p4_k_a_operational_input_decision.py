#!/usr/bin/env python3
"""Validate proposed P4-K-A inputs without key, signer, or execution authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777"
DECISION_IDS = ("D-080", "D-081", "D-082", "D-083", "D-084", "D-085")
LINEAGE_HASHES = {
    "config/q15/q15-r-p4-k-d-acceptance-v1.json": "11b9c357468515145bc5e7b2b477515c814d31ec97603245eff378d0259e6be7",
    "config/q15/q15-r-p4-k-a.authorization-template-v1.json": "7669a2f693a7ffca3fa583ec3ed7a45e1ea130a51ee009ac33a77b936409ccb5",
    "config/q15/q15-r-p4-k-r.authorization-template-v1.json": "ae71ce73cf0636294995c0ca3311d4ccf6f857916c07fe9df67bb9682d20efcf",
    "docs/decisions/0076-q15-r-p4-k-new-offline-key-ceremony.md": "449113f623f1c5b9dd221c579545d9fce980cfc1bad26eed95331c5eddd247fa",
    "docs/decisions/0077-q15-r-p4-k-custody-identifiers.md": "97b3815229e700869b56133d4a83626a5015710f902440a76ea1de86507198b1",
    "docs/decisions/0078-q15-r-p4-k-split-acquisition-review.md": "984e1ddc95021cfe3f22d0696f907c10de2fd45f5fcf6a0f6f3dcbc4fae10ac5",
    "docs/decisions/0079-q15-r-p4-k-authority-validity.md": "90dd4dd47ed5e49b10fdf923bd0b32b099dd5fea22ea9152c908d16e07313fd0",
}
INPUT_MAPPING = (
    (
        "EXACT_OFFLINE_CEREMONY_AND_PUBLIC_EXTRACTION_TOOL_IDS_VERSIONS_SHA256_AND_FIXED_ARGV",
        ("D-080", "D-084"),
    ),
    (
        "CREATE_EXCLUSIVE_PUBLIC_ARTIFACT_IDS_AND_ABSOLUTE_SOURCE_PATHS",
        ("D-082",),
    ),
    (
        "OFFLINE_CUSTODY_CONTROL_AND_CEREMONY_ENVIRONMENT_EVIDENCE_ID_AND_SHA256",
        ("D-080", "D-081"),
    ),
    (
        "BOOTSTRAP_AUTHORIZATION_SIGNER_FINGERPRINT_AND_TRUST_EVIDENCE_SHA256",
        ("D-083",),
    ),
    ("LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS", ("D-085",)),
    (
        "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
        ("D-083", "D-085"),
    ),
    (
        "DISTINCT_AUDITOR_PRE_EXECUTION_REVIEW_ARTIFACT_ID_AND_SHA256",
        ("D-085",),
    ),
)
QUESTION_ANSWERS = (
    (
        "P4KA-Q1",
        ("ACCEPT_D080_RECOMMENDATION", "REVISE", "REMAIN_BLOCKED"),
    ),
    (
        "P4KA-Q2",
        ("ACCEPT_D081_RECOMMENDATION", "REVISE", "REMAIN_BLOCKED"),
    ),
    (
        "P4KA-Q3",
        ("ACCEPT_D082_RECOMMENDATION", "REVISE", "REMAIN_BLOCKED"),
    ),
    (
        "P4KA-Q4",
        (
            "QUALIFYING_BOOTSTRAP_SIGNER_EVIDENCE_EXISTS_TO_BE_SUPPLIED_LATER",
            "NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED",
        ),
    ),
    (
        "P4KA-Q5",
        ("ACCEPT_D084_D085_RECOMMENDATIONS", "REVISE", "REMAIN_BLOCKED"),
    ),
)
REQUIRED_RECOMMENDATION_MARKERS = {
    "D-080": ("dedicated owner-controlled offline Linux", "network interfaces"),
    "D-081": ("encrypted OpenSSH Ed25519 private key", "passphrase"),
    "D-082": ("absolute create-exclusive public export root", "private-key path"),
    "D-083": ("already established signer distinct from the target", "stop"),
    "D-084": ("repository-owned controller", "retries zero times"),
    "D-085": ("1800 seconds apart", "mandatory stop"),
}


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    direct_bindings = {
        lineage.get("p4_k_d_acceptance_path"): lineage.get("p4_k_d_acceptance_sha256"),
        lineage.get("p4_k_a_template_path"): lineage.get("p4_k_a_template_sha256"),
        lineage.get("p4_k_r_template_path"): lineage.get("p4_k_r_template_sha256"),
    }
    adr_bindings = {
        item.get("path"): item.get("sha256")
        for item in lineage.get("adr_bindings", [])
    }
    if {**direct_bindings, **adr_bindings} != LINEAGE_HASHES:
        errors.append("P4-K-D/template/ADR lineage must be exact")
    for relative, expected in LINEAGE_HASHES.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable lineage artifact mismatch: {relative}")

    decisions = record.get("decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISION_IDS:
        errors.append("D-080 through D-085 must be exact, unique, and ordered")
    for item in decisions:
        decision_id = item.get("decision_id")
        if item.get("selected_option") is not None:
            errors.append("P4-K-A operational decisions must remain unselected")
        options = item.get("options_considered", [])
        if not options or options[-1] != "REMAIN_BLOCKED":
            errors.append(f"{decision_id} must retain an explicit remain-blocked option")
        recommendation = str(item.get("recommended_option", ""))
        if any(
            marker not in recommendation
            for marker in REQUIRED_RECOMMENDATION_MARKERS.get(decision_id, ())
        ):
            errors.append(f"{decision_id} recommendation contract drifted")

    actual_inputs = tuple(
        (item.get("name"), tuple(item.get("decision_ids", [])))
        for item in record.get("external_input_mapping", [])
    )
    if actual_inputs != INPUT_MAPPING:
        errors.append("the seven P4-K-A inputs and decision mappings must be exact")
    if any(
        item.get("value") is not None
        or not str(item.get("state", "")).startswith("UNRESOLVED_")
        for item in record.get("external_input_mapping", [])
    ):
        errors.append("P4-K-A external evidence cannot be fabricated or defaulted")

    questions = record.get("minimum_owner_inputs_before_policy_acceptance", [])
    actual_questions = tuple(
        (item.get("question_id"), tuple(item.get("allowed_answers", [])))
        for item in questions
    )
    if actual_questions != QUESTION_ANSWERS or any(
        item.get("answer") is not None for item in questions
    ):
        errors.append("the five minimum owner questions must be exact and unanswered")

    contract = record.get("fixed_nonnegotiable_contract", {})
    if (
        contract.get("target_key_may_authorize_its_own_creation") is not False
        or contract.get("target_private_key_path_bytes_passphrase_or_seed_may_be_recorded")
        is not False
        or contract.get("action_attempt_count") != 1
        or contract.get("retry_repair_overwrite_or_cleanup_count") != 0
        or contract.get("mandatory_stop_before_p4_k_r") is not True
        or contract.get("automatic_continuation_to_installation_p4_r_q15_or_experiment")
        is not False
    ):
        errors.append("the accepted P4-K privacy, one-shot, and stop boundary drifted")

    boundary = record.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {"repository_local_decision_bundle_preparation_authorized"}:
        errors.append("P4-K-A proposal widens authority beyond local decision preparation")

    acquisition = load(root / "config/q15/q15-r-p4-k-a.authorization-template-v1.json")
    if tuple(
        (item.get("name"), item.get("value"))
        for item in acquisition.get("unresolved_inputs", [])
    ) != tuple((name, None) for name, _ in INPUT_MAPPING):
        errors.append("P4-K-A template must retain the same seven null inputs")
    if any(
        value is True
        for name, value in acquisition.get("authority_boundary", {}).items()
        if name != "repository_local_unissued_template_creation_authorized"
    ):
        errors.append("P4-K-A template must remain unissued and no-authority")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record_path = root / "config/q15/q15-r-p4-k-a-operational-input-decision-v1.json"
    record = load(record_path)
    schema = load(
        root
        / "config/schemas/q15-r-p4-k-a-operational-input-decision-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    if sha256(record_path) != PROPOSAL_SHA256:
        errors.append("P4-K-A operational-input proposal bytes drifted")

    negatives: list[dict[str, Any]] = []
    implementation = copy.deepcopy(record)
    implementation["authority_boundary"][
        "repository_local_acceptance_adr_controller_schema_or_template_implementation_authorized"
    ] = True
    negatives.append(implementation)
    environment = copy.deepcopy(record)
    environment["authority_boundary"]["offline_environment_access_or_inventory_authorized"] = True
    negatives.append(environment)
    key = copy.deepcopy(record)
    key["authority_boundary"]["key_read_generation_import_copy_fingerprint_or_use_authorized"] = True
    negatives.append(key)
    signer = copy.deepcopy(record)
    signer["authority_boundary"]["bootstrap_signer_or_trust_artifact_access_authorized"] = True
    negatives.append(signer)
    stand = copy.deepcopy(record)
    stand["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(stand)
    selected = copy.deepcopy(record)
    selected["decisions"][0]["selected_option"] = selected["decisions"][0][
        "options_considered"
    ][0]
    negatives.append(selected)
    reordered = copy.deepcopy(record)
    reordered["decisions"][0], reordered["decisions"][1] = (
        reordered["decisions"][1],
        reordered["decisions"][0],
    )
    negatives.append(reordered)
    filled = copy.deepcopy(record)
    filled["external_input_mapping"][0]["value"] = "invented-tool"
    negatives.append(filled)
    mapping = copy.deepcopy(record)
    mapping["external_input_mapping"][3]["decision_ids"] = ["D-080"]
    negatives.append(mapping)
    self_authorize = copy.deepcopy(record)
    self_authorize["fixed_nonnegotiable_contract"][
        "target_key_may_authorize_its_own_creation"
    ] = True
    negatives.append(self_authorize)
    secret = copy.deepcopy(record)
    secret["fixed_nonnegotiable_contract"][
        "target_private_key_path_bytes_passphrase_or_seed_may_be_recorded"
    ] = True
    negatives.append(secret)
    retry = copy.deepcopy(record)
    retry["fixed_nonnegotiable_contract"]["retry_repair_overwrite_or_cleanup_count"] = 1
    negatives.append(retry)
    answer = copy.deepcopy(record)
    answer["minimum_owner_inputs_before_policy_acceptance"][0]["answer"] = (
        "ACCEPT_D080_RECOMMENDATION"
    )
    negatives.append(answer)
    missing = copy.deepcopy(record)
    missing["minimum_owner_inputs_before_policy_acceptance"].pop()
    negatives.append(missing)
    lineage = copy.deepcopy(record)
    lineage["lineage"]["p4_k_a_template_sha256"] = "0" * 64
    negatives.append(lineage)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-p4-k-a-operational-input-decision-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    print(
        "q15-r-p4-k-a-operational-input-decision-check: PASS "
        "(D-080..D-085 proposed, 7 inputs null, 5 owner questions open, "
        "15 negative, key/signer/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
