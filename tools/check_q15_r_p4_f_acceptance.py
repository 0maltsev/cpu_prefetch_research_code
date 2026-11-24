#!/usr/bin/env python3
"""Validate accepted D-072..D-075 without widening operational authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604"
P4_R_SHA256 = "f8c63d1f95d69c6a9562cfec6d2635757c9dbba80137d68fdedf56bd189b6ba4"
P4_K_SHA256 = "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
DECISIONS = (
    ("D-072", "EXACT_CREATE_EXCLUSIVE_NO_ACTIVATION_STAGING_TREE_v1"),
    ("D-073", "EXACT_CAPTURE_AND_DEVELOPMENT_CUSTODY_PATHS_v1"),
    ("D-074", "NAMED_OPERATOR_1800S_SSHSIG_AND_DISTINCT_AUDITOR_v1"),
    ("D-075", "SPLIT_IDENTITY_THEN_ONE_SHOT_COLLECTION_FAIL_CLOSED_v1"),
)
EXPECTED_ACCEPTANCE = (
    "Q15-R-P4-F — accept D-072 through D-075 in the exact Q15-R-P4-R staging "
    "and read-only stand-prestate authorization decision bundle, bound to "
    "governance commit f30036e31acc8ae036f2f31086d493eeb30db9d7 and immutable "
    "v3 archive SHA-256 "
    "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a. "
    "Accept the exact create-exclusive stand staging tree, fixed capture and "
    "development-custody paths, cpu-prefetch-q15-operator named authority, "
    "nonrenewable 1800-second UTC policy, accepted OpenSSH SSHSIG profile with "
    "distinct auditor review, and split P4-R-I identity then P4-R-C one-shot "
    "staging/collection graph with stop-retain-no-delete rollback. Authorize "
    "repository-local creation and verification of acceptance, ADR, and "
    "still-unissued successor authorization templates only. Do not access or "
    "modify the stand, create paths, transfer or extract artifacts, execute "
    "self-tests or the collector on the stand, create/import/copy/use keys, "
    "sign or issue P4-R-I/P4-R-C/P4-K/Q15-R/Q15-W, perform platform controls, "
    "calibrate, pilot, measure, or perform confirmatory work. Every external-"
    "input, signature, and execution phase requires a later separate exact "
    "approval."
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
        errors.append("Q15-R-P4-F must bind the immutable D-072..D-075 proposal")
    if binding.get("governance_commit") != (
        "f30036e31acc8ae036f2f31086d493eeb30db9d7"
    ):
        errors.append("governance commit drifted")
    if binding.get("immutable_v3_archive_sha256") != (
        "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a"
    ):
        errors.append("immutable v3 archive identity drifted")

    selected = tuple(
        (item.get("decision_id"), item.get("selected_option"))
        for item in record.get("accepted_decisions", [])
    )
    if selected != DECISIONS:
        errors.append("D-072 through D-075 selections must be exact and ordered")
    if record.get("user_acceptance") != EXPECTED_ACCEPTANCE:
        errors.append("Q15-R-P4-F user acceptance text mismatch")

    selection = record.get("selection_effect", {})
    if not all(
        selection.get(name) is True
        for name in (
            "literal_candidate_paths_frozen",
            "capture_identity_frozen",
            "principal_validity_signature_and_review_policy_frozen",
            "split_identity_then_collection_graph_frozen",
            "repository_local_acceptance_adr_and_unissued_template_creation_authorized",
        )
    ):
        errors.append("accepted template literals or repository-local scope drifted")
    if selection.get("stand_path_or_custody_artifact_created") is not False or selection.get(
        "authorization_issued"
    ) is not False:
        errors.append("acceptance cannot claim path creation or issuance")

    boundary = record.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {
        "repository_local_acceptance_adr_and_unissued_template_creation_authorized"
    }:
        errors.append("Q15-R-P4-F widens authority beyond repository-local records")

    preservation = record.get("predecessor_preservation", {})
    expected = (
        ("p4_r_preparation_path", "p4_r_preparation_sha256", P4_R_SHA256, 7),
        ("p4_k_preparation_path", "p4_k_preparation_sha256", P4_K_SHA256, 8),
    )
    for path_field, hash_field, expected_hash, _ in expected:
        path = root / str(preservation.get(path_field, ""))
        if (
            preservation.get(hash_field) != expected_hash
            or not path.is_file()
            or sha256(path) != expected_hash
        ):
            errors.append(f"immutable predecessor mismatch: {path_field}")

    p4_r = load(root / "config/q15/q15-r-p4-r.preparation-v2.json")
    if len(p4_r.get("remaining_required_inputs", [])) != 7 or any(
        item.get("value") is not None
        for item in p4_r.get("remaining_required_inputs", [])
    ):
        errors.append("P4-R v2 must retain seven null external inputs")
    p4_k = load(root / "config/q15/q15-r-p4-k.preparation.json")
    if len(p4_k.get("unresolved_inputs", [])) != 8 or any(
        item.get("value") is not None for item in p4_k.get("unresolved_inputs", [])
    ):
        errors.append("P4-K must retain eight null external inputs")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-f-acceptance-v1.json")
    schema = load(root / "config/schemas/q15-r-p4-f-acceptance-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))

    negatives: list[dict[str, Any]] = []
    authority = copy.deepcopy(record)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    path_action = copy.deepcopy(record)
    path_action["authority_boundary"][
        "stand_or_custody_path_creation_authorized"
    ] = True
    negatives.append(path_action)
    proposal = copy.deepcopy(record)
    proposal["decision_input_binding"]["sha256"] = "0" * 64
    negatives.append(proposal)
    option = copy.deepcopy(record)
    option["accepted_decisions"][0]["selected_option"] = "INVENTED"
    negatives.append(option)
    issuance = copy.deepcopy(record)
    issuance["selection_effect"]["authorization_issued"] = True
    negatives.append(issuance)
    predecessor = copy.deepcopy(record)
    predecessor["predecessor_preservation"]["p4_k_preparation_sha256"] = "0" * 64
    negatives.append(predecessor)
    text = copy.deepcopy(record)
    text["user_acceptance"] += " widened"
    negatives.append(text)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-f-acceptance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-f-acceptance-check: PASS "
        "(D-072..D-075 accepted, 7 negative, operational authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
