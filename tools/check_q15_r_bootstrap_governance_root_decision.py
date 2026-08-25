#!/usr/bin/env python3
"""Validate the proposed bootstrap governance-root gate without key authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "065d8a6d5f882bff84ee9bdbe27eb0e0c9e2bfea56c58cbe2b9bfc61cab3a4b7"
LINEAGE = (
    (
        "p4_k_a_policy_acceptance_path",
        "p4_k_a_policy_acceptance_sha256",
        "config/q15/q15-r-p4-k-a-d-acceptance-v1.json",
        "c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf",
    ),
    (
        "bootstrap_blocking_adr_path",
        "bootstrap_blocking_adr_sha256",
        "docs/decisions/0083-q15-r-p4-k-a-bootstrap-governance-root.md",
        "fd608cabbf9a9bf01cc70c6f991a2c19564548ddf2baa45d017b31f7a505cfe5",
    ),
    (
        "generic_controller_profile_path",
        "generic_controller_profile_sha256",
        "config/q15/q15-r-p4-k-a-controller-profile-v1.json",
        "0ceafd80200ba62584532e035a4c2a21015c2b56f75d0ebbfdffbd7f3b945875",
    ),
)
DECISIONS = tuple(f"D-{value:03d}" for value in range(87, 93))
INPUTS = (
    "GENESIS_AUTHORITY_IDENTITY_METHOD_ATTESTATION_ARTIFACT_AND_SHA256",
    "DISTINCT_GENESIS_OPERATOR_CUSTODIAN_AUDITOR_IDENTITIES_AND_EVIDENCE",
    "PRIMARY_AND_RECOVERY_OFFLINE_CUSTODY_DOMAIN_EVIDENCE_IDS_AND_SHA256",
    "OFFLINE_ENVIRONMENT_OS_TOOL_LIBRARY_VERSION_ARGV_HASHES_AND_NETWORK_EVIDENCE",
    "EXACT_KEY_ENCODING_KDF_WORK_SECRET_BOUNDARY_RECOVERY_ROTATION_AND_DESTRUCTION_POLICY",
    "CREATE_EXCLUSIVE_PUBLIC_EXPORT_TRANSACTION_ID_ABSOLUTE_PATHS_AND_ARTIFACT_IDS",
    "ROOT_PUBLIC_KEY_FINGERPRINT_CANONICAL_ALLOWED_SIGNERS_BYTES_AND_SHA256",
    "DISTINCT_AUDITOR_GENESIS_AND_PUBLIC_TRUST_REVIEW_ARTIFACT_AND_SHA256",
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field, expected_path, expected_hash in LINEAGE:
        path = root / str(lineage.get(path_field, ""))
        if (
            lineage.get(path_field) != expected_path
            or lineage.get(hash_field) != expected_hash
            or not path.is_file()
            or sha256(path) != expected_hash
        ):
            errors.append(f"immutable lineage mismatch: {path_field}")

    decisions = record.get("decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISIONS:
        errors.append("D-087 through D-092 must be exact and ordered")
    if any(item.get("selected_option") is not None for item in decisions):
        errors.append("external-capability-dependent options must remain unselected")
    if any(item.get("scientific_effect") != "none" for item in decisions):
        errors.append("bootstrap governance decisions cannot change scientific semantics")

    inputs = record.get("external_inputs", [])
    if tuple(item.get("name") for item in inputs) != INPUTS or any(
        item.get("value") is not None for item in inputs
    ):
        errors.append("the exact eight external inputs must remain null")
    questions = record.get("owner_questions", [])
    expected_questions = tuple(f"BGR-Q{index}" for index in range(1, 7))
    if tuple(item.get("question_id") for item in questions) != expected_questions or any(
        item.get("answer") is not None for item in questions
    ):
        errors.append("the exact six owner questions must remain unanswered")

    boundary = record.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {"repository_local_decision_bundle_preparation_authorized"}:
        errors.append("bootstrap proposal widens authority beyond record preparation")

    serialized = json.dumps(record, sort_keys=True).lower()
    for forbidden in (
        "begin openssh private key",
        '"private_key_path":',
        '"passphrase":',
        '"seed":',
    ):
        if forbidden in serialized:
            errors.append("bootstrap proposal contains a forbidden secret field or material")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-bootstrap-governance-root-decision-input-v1.json"
    record = load(path)
    schema = load(
        root
        / "config/schemas/q15-r-bootstrap-governance-root-decision-input-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    if sha256(path) != PROPOSAL_SHA256:
        errors.append("bootstrap governance-root proposal bytes drifted")

    negatives: list[dict[str, Any]] = []
    for field in (
        "repository_local_acceptance_adr_controller_schema_or_template_implementation_authorized",
        "genesis_identity_or_witness_action_authorized",
        "offline_environment_access_or_inventory_authorized",
        "bootstrap_key_generation_import_copy_fingerprint_or_use_authorized",
        "custody_or_public_export_path_creation_authorized",
        "public_trust_artifact_creation_authorized",
        "signing_activation_rotation_revocation_or_recovery_authorized",
        "p4_k_a_or_p4_k_r_authorized",
        "stand_access_authorized",
        "calibration_pilot_measurement_or_confirmatory_authorized",
    ):
        mutant = copy.deepcopy(record)
        mutant["authority_boundary"][field] = True
        negatives.append(mutant)
    selected = copy.deepcopy(record)
    selected["decisions"][0]["selected_option"] = selected["decisions"][0][
        "options_considered"
    ][0]
    negatives.append(selected)
    value = copy.deepcopy(record)
    value["external_inputs"][0]["value"] = "invented"
    negatives.append(value)
    answer = copy.deepcopy(record)
    answer["owner_questions"][0]["answer"] = "ACCEPT"
    negatives.append(answer)
    reorder = copy.deepcopy(record)
    reorder["decisions"][0], reorder["decisions"][1] = (
        reorder["decisions"][1],
        reorder["decisions"][0],
    )
    negatives.append(reorder)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-bootstrap-governance-root-decision-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    print(
        "q15-r-bootstrap-governance-root-decision-check: PASS "
        "(D-087..D-092 proposed, 8 inputs null, 6 questions open, 14 negative, "
        "key/trust/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
