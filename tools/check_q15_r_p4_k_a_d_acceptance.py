#!/usr/bin/env python3
"""Validate Q15-R-P4-K-A-D policy acceptance and its fail-closed trust state."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "8acfebfb22ba7449233b5c4c5b2a7ecf9c9a48323b1d79b45b42d26867199777"
ACCEPTANCE_SHA256 = "c68e1b9427df9306a53cac590dfe268862fa528ef5bf665bf0002972cf77ffaf"
P4_K_A_SHA256 = "7669a2f693a7ffca3fa583ec3ed7a45e1ea130a51ee009ac33a77b936409ccb5"
P4_K_R_SHA256 = "ae71ce73cf0636294995c0ca3311d4ccf6f857916c07fe9df67bb9682d20efcf"
DECISIONS = (
    (
        "D-080",
        "DEDICATED_OWNER_CONTROLLED_OFFLINE_LINUX_OPENSSH_TOOLCHAIN_WITH_"
        "EXACT_INVENTORY_HASHES_AND_NETWORK_UNAVAILABLE_DURING_ACTION",
    ),
    (
        "D-081",
        "ENCRYPTED_OPENSSH_ED25519_PRIVATE_KEY_WITH_INTERACTIVE_UNRECORDED_"
        "SECRET_AND_HASH_BOUND_NONSECRET_CUSTODY_RECEIPT",
    ),
    (
        "D-082",
        "UNIQUE_CREATE_EXCLUSIVE_PUBLIC_EXPORT_ROOT_OUTSIDE_REPOSITORY_AND_"
        "STAND_WITH_FIXED_ARTIFACT_IDS_AND_NO_PRIVATE_PATH_SERIALIZATION",
    ),
    (
        "D-083",
        "SEPARATELY_ESTABLISH_A_BOOTSTRAP_GOVERNANCE_ROOT_BEFORE_RETURNING_"
        "TO_P4_K_A",
    ),
    (
        "D-084",
        "HASH_BOUND_NO_SHELL_FIXED_CONTROLLER_WITH_PREOPENED_SECRET_TTY_"
        "BOUNDARY_O_EXCL_PUBLIC_OUTPUTS_ONE_ATTEMPT_AND_ZERO_RETRY",
    ),
    (
        "D-085",
        "DISTINCT_AUDITOR_PRE_EXECUTION_REVIEW_EXACT_1800S_UTC_SSHSIG_ONE_"
        "ACTION_APPEND_ONLY_PARTIAL_EVIDENCE_AND_STOP_FOR_P4_K_R",
    ),
)
USER_RESPONSES = (
    "P4KA-Q1=ACCEPT_D080_RECOMMENDATION",
    "P4KA-Q2=ACCEPT_D081_RECOMMENDATION",
    "P4KA-Q3=ACCEPT_D082_RECOMMENDATION",
    "P4KA-Q4=NO_QUALIFYING_BOOTSTRAP_SIGNER_REMAIN_BLOCKED",
    "P4KA-Q5=ACCEPT_D084_D085_RECOMMENDATIONS",
)
BOUNDARY = (
    "Accept the D-080 through D-085 policy recommendations and record their "
    "ADRs. The explicit Q4 response is negative evidence only: no qualifying "
    "bootstrap signer exists, no signer or trust artifact is inferred, and "
    "P4-K-A remains blocked. Because the response grants no broader action "
    "scope, controller/schema/template implementation and every external, key, "
    "trust, path, signature, issuance, stand, Q15, calibration, pilot, "
    "measurement, and confirmatory action remain unauthorized."
)
ADRS = (
    (
        "docs/decisions/0080-q15-r-p4-k-a-offline-environment-toolchain.md",
        "5f7690d27da236ca52c394e3ed0281ce2c19be3b80c4fe7966644c750e9646fc",
        "ACCEPTED_POLICY_EXTERNAL_EVIDENCE_REQUIRED_NO_ENVIRONMENT_ACCESS_AUTHORITY",
    ),
    (
        "docs/decisions/0081-q15-r-p4-k-a-private-key-protection.md",
        "18524737960f581dd63194dfa2dbf59394c97ece3c97684e724b3028e970bf8a",
        "ACCEPTED_POLICY_LITERAL_KDF_AND_EXTERNAL_CUSTODY_EVIDENCE_REQUIRED",
    ),
    (
        "docs/decisions/0082-q15-r-p4-k-a-public-export-identity.md",
        "dcfacb082696e2189bb7059d10637758b75f551eed1dcdf9662bf96c33bf116a",
        "ACCEPTED_POLICY_LITERAL_PUBLIC_PATH_AND_IDENTITY_REQUIRED",
    ),
    (
        "docs/decisions/0083-q15-r-p4-k-a-bootstrap-governance-root.md",
        "fd608cabbf9a9bf01cc70c6f991a2c19564548ddf2baa45d017b31f7a505cfe5",
        "ACCEPTED_POLICY_BLOCKED_NO_QUALIFYING_BOOTSTRAP_SIGNER",
    ),
    (
        "docs/decisions/0084-q15-r-p4-k-a-fixed-controller-contract.md",
        "f4ab3d9d899059da1b212ec1c9ec9aec14824aa2bff64b48baadcba73b9d2a2b",
        "ACCEPTED_POLICY_IMPLEMENTATION_REQUIRES_SEPARATE_EXPLICIT_AUTHORITY",
    ),
    (
        "docs/decisions/0085-q15-r-p4-k-a-issuance-review-partial-evidence.md",
        "218d4c6aadfe087a26512d695d40179bfa2641e68d7649c4bb7e33ee9f7db004",
        "ACCEPTED_POLICY_LITERAL_ISSUANCE_AND_REVIEW_EVIDENCE_REQUIRED",
    ),
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
        errors.append("acceptance must bind the immutable D-080..D-085 proposal")

    proposal = load(proposal_path) if proposal_path.is_file() else {}
    selected = tuple(
        (item.get("decision_id"), item.get("selected_option"))
        for item in record.get("accepted_decisions", [])
    )
    if selected != DECISIONS:
        errors.append("D-080 through D-085 selections must be exact and ordered")
    options = {
        item.get("decision_id"): item.get("options_considered", [])
        for item in proposal.get("decisions", [])
    }
    if any(option not in options.get(decision_id, []) for decision_id, option in selected):
        errors.append("acceptance selects an option absent from the proposal")

    if tuple(record.get("user_responses", [])) != USER_RESPONSES:
        errors.append("owner responses drifted")
    if record.get("bounded_interpretation") != BOUNDARY:
        errors.append("bounded no-authority interpretation drifted")

    bootstrap = record.get("bootstrap_trust_disposition", {})
    if (
        bootstrap.get("owner_response") != USER_RESPONSES[3].split("=", 1)[1]
        or bootstrap.get("qualifying_bootstrap_signer_evidence_exists") is not False
        or bootstrap.get("bootstrap_signer_or_trust_evidence_supplied") is not False
        or bootstrap.get("target_key_may_self_authorize") is not False
        or bootstrap.get("required_next_governance_gate")
        != "SEPARATELY_ESTABLISH_BOOTSTRAP_GOVERNANCE_ROOT"
        or bootstrap.get("p4_k_a_issuance_state") != "BLOCKED"
    ):
        errors.append("negative Q4 must fail closed on a separate bootstrap-root gate")

    selection = record.get("selection_effect", {})
    if selection.get("repository_local_acceptance_and_adr_creation_authorized") is not True:
        errors.append("acceptance/ADR recording must be the only enabled local effect")
    if any(
        selection.get(name) is not False
        for name in (
            "repository_local_controller_schema_or_template_implementation_authorized",
            "external_input_value_selected_or_inferred",
            "bootstrap_signer_or_trust_evidence_claimed",
            "key_public_artifact_path_signature_or_issuance_created",
        )
    ):
        errors.append("acceptance cannot claim implementation or external evidence/action")

    authority = record.get("authority_boundary", {})
    enabled = {
        name for name, value in authority.items() if name.endswith("_authorized") and value
    }
    if enabled != {"repository_local_acceptance_and_adr_creation_authorized"}:
        errors.append("authority widened beyond repository-local acceptance and ADRs")

    if len(proposal.get("external_input_mapping", [])) != 7 or any(
        item.get("value") is not None for item in proposal.get("external_input_mapping", [])
    ):
        errors.append("immutable proposal must retain seven null external inputs")
    if len(proposal.get("minimum_owner_inputs_before_policy_acceptance", [])) != 5 or any(
        item.get("answer") is not None
        for item in proposal.get("minimum_owner_inputs_before_policy_acceptance", [])
    ):
        errors.append("immutable proposal must retain five null owner-answer fields")

    preservation = record.get("predecessor_preservation", {})
    for path_field, hash_field, expected in (
        ("p4_k_a_template_path", "p4_k_a_template_sha256", P4_K_A_SHA256),
        ("p4_k_r_template_path", "p4_k_r_template_sha256", P4_K_R_SHA256),
    ):
        path = root / str(preservation.get(path_field, ""))
        if (
            preservation.get(hash_field) != expected
            or not path.is_file()
            or sha256(path) != expected
        ):
            errors.append(f"immutable predecessor mismatch: {path_field}")

    for path_text, expected_hash, expected_status in ADRS:
        path = root / path_text
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if not path.is_file() or sha256(path) != expected_hash:
            errors.append(f"accepted ADR hash mismatch: {path_text}")
        elif f"Status: `{expected_status}`" not in text:
            errors.append(f"accepted ADR status mismatch: {path_text}")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-p4-k-a-d-acceptance-v1.json"
    record = load(path)
    schema = load(root / "config/schemas/q15-r-p4-k-a-d-acceptance-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    if sha256(path) != ACCEPTANCE_SHA256:
        errors.append("Q15-R-P4-K-A-D acceptance bytes drifted")

    negatives: list[dict[str, Any]] = []
    for field in (
        "repository_local_controller_schema_or_template_implementation_authorized",
        "offline_environment_access_or_inventory_authorized",
        "key_read_generation_import_copy_fingerprint_or_use_authorized",
        "bootstrap_governance_root_establishment_authorized",
        "bootstrap_signer_or_trust_artifact_access_authorized",
        "signing_or_issuance_authorized",
        "p4_k_a_authorized",
        "stand_access_authorized",
        "calibration_pilot_measurement_or_confirmatory_authorized",
    ):
        mutant = copy.deepcopy(record)
        mutant["authority_boundary"][field] = True
        negatives.append(mutant)
    signer = copy.deepcopy(record)
    signer["bootstrap_trust_disposition"][
        "qualifying_bootstrap_signer_evidence_exists"
    ] = True
    negatives.append(signer)
    supplied = copy.deepcopy(record)
    supplied["bootstrap_trust_disposition"][
        "bootstrap_signer_or_trust_evidence_supplied"
    ] = True
    negatives.append(supplied)
    self_auth = copy.deepcopy(record)
    self_auth["bootstrap_trust_disposition"]["target_key_may_self_authorize"] = True
    negatives.append(self_auth)
    unblocked = copy.deepcopy(record)
    unblocked["bootstrap_trust_disposition"]["p4_k_a_issuance_state"] = "READY"
    negatives.append(unblocked)
    option = copy.deepcopy(record)
    option["accepted_decisions"][3]["selected_option"] = "REMAIN_BLOCKED"
    negatives.append(option)
    response = copy.deepcopy(record)
    response["user_responses"][3] = (
        "P4KA-Q4=QUALIFYING_BOOTSTRAP_SIGNER_EVIDENCE_EXISTS_TO_BE_SUPPLIED_LATER"
    )
    negatives.append(response)
    implementation = copy.deepcopy(record)
    implementation["selection_effect"][
        "repository_local_controller_schema_or_template_implementation_authorized"
    ] = True
    negatives.append(implementation)
    external = copy.deepcopy(record)
    external["selection_effect"]["external_input_value_selected_or_inferred"] = True
    negatives.append(external)
    predecessor = copy.deepcopy(record)
    predecessor["predecessor_preservation"]["p4_k_a_template_sha256"] = "0" * 64
    negatives.append(predecessor)
    scope = copy.deepcopy(record)
    scope["bounded_interpretation"] += " Implement the controller."
    negatives.append(scope)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-k-a-d-acceptance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-k-a-d-acceptance-check: PASS "
        "(D-080..D-085 policy accepted, Q4=BLOCKED, 19 negative, "
        "controller/key/trust/stand/execution authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
