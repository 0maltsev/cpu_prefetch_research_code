#!/usr/bin/env python3
"""Validate still-unissued split P4-R-I and P4-R-C authorization templates."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


PROPOSAL_SHA256 = "18c29f6f3710b061bcf593ad6615589a6b50c4bf28ebceb4bee3714702389604"
ACCEPTANCE_SHA256 = "ae879bd113939ee06fd3673c0f14d054d92d6c30c0162ffa6727d2a42973cb8c"
IDENTITY_TEMPLATE_SHA256 = (
    "38223ea7ff54b3a0ae748f670fcfd00a723272b03211e4eddda997d5b603f1d8"
)
COLLECTION_TEMPLATE_SHA256 = (
    "22d4aa6f4c4ffa60c3fb31c08f3eea4831a790a0b46907b2aab5af3dcc0377df"
)
P4_R_SHA256 = "f8c63d1f95d69c6a9562cfec6d2635757c9dbba80137d68fdedf56bd189b6ba4"
P4_K_SHA256 = "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
ADR_HASHES = {
    "D-072": "e9522f038c4a797c7c516d325725e888e9d5b54d2ce15e579bb3299546ab938a",
    "D-073": "8b9366d3f1a0bbb68f57e9946db5afd4f49b2b778d87e65d451003a7c879db1b",
    "D-074": "d6a19259b75cc250bffe7c2ab1024559cc6bd5839274019bf061aec0735a0db5",
    "D-075": "e2793a6a31af6210fd304f30893b9b3043c4d91af35c90cba938f86f4147e6b4",
}
IDENTITY_INPUTS = (
    "PINNED_SSH_HOST_KEY_FINGERPRINT",
    "BOOTSTRAP_TRANSPORT_CREDENTIAL_AND_ACCESS_EVIDENCE",
    "P4_K_ALLOWED_SIGNERS_FINGERPRINT_AND_OFF_STAND_CUSTODY_EVIDENCE",
    "LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS",
    "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
    "DIRECT_FIXED_ARGV_TRANSPORT_AND_DISTINCT_INDEPENDENT_REVIEW_EVIDENCE",
)
COLLECTION_INPUTS = (
    "PINNED_SSH_HOST_KEY_AND_BOOTSTRAP_TRANSPORT_CREDENTIAL_EVIDENCE",
    "P4_K_ALLOWED_SIGNERS_FINGERPRINT_AND_OFF_STAND_CUSTODY_EVIDENCE",
    "LITERAL_ISSUE_AND_EXPIRY_UTC_INSTANTS",
    "CANONICAL_AUTHORIZATION_SHA256_AND_DETACHED_SIGNATURE_SHA256",
    "ACCEPTED_FRESH_Q15_R_P4_R_I_ARTIFACT_AND_REVIEW_HASHES",
    "DIRECT_FIXED_ARGV_TRANSPORT_AND_DISTINCT_INDEPENDENT_REVIEW_EVIDENCE",
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def authority_errors(record: dict[str, Any], label: str) -> list[str]:
    boundary = record.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {"repository_local_unissued_template_creation_authorized"}:
        return [f"{label} widens authority beyond repository-local template creation"]
    return []


def lineage_errors(root: pathlib.Path, record: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    bindings = (
        ("decision_input_path", "decision_input_sha256", PROPOSAL_SHA256),
        ("acceptance_path", "acceptance_sha256", ACCEPTANCE_SHA256),
        ("p4_k_path", "p4_k_sha256", P4_K_SHA256),
    )
    for path_name, hash_name, expected_hash in bindings:
        path = root / str(lineage.get(path_name, ""))
        if (
            lineage.get(hash_name) != expected_hash
            or not path.is_file()
            or sha256(path) != expected_hash
        ):
            errors.append(f"{label} immutable lineage mismatch: {path_name}")
    actual_adrs = {
        item.get("decision_id"): item for item in lineage.get("adr_bindings", [])
    }
    if set(actual_adrs) != set(ADR_HASHES):
        errors.append(f"{label} must bind ADR-0072 through ADR-0075 exactly")
    else:
        for decision_id, expected_hash in ADR_HASHES.items():
            item = actual_adrs[decision_id]
            path = root / str(item.get("path", ""))
            if (
                item.get("sha256") != expected_hash
                or not path.is_file()
                or sha256(path) != expected_hash
            ):
                errors.append(f"{label} ADR binding mismatch: {decision_id}")
    return errors


def unresolved_errors(
    record: dict[str, Any], expected: tuple[str, ...], label: str
) -> list[str]:
    inputs = record.get("unresolved_inputs", [])
    names = tuple(item.get("name") for item in inputs)
    if names != expected or any(item.get("value") is not None for item in inputs):
        return [f"{label} unresolved inputs must remain exact, ordered, and null"]
    return []


def semantic_errors(
    root: pathlib.Path, identity: dict[str, Any], collection: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    proposal = load(
        root / "config/q15/q15-r-p4-r-staging-authorization-decision-input-v1.json"
    )
    transaction = proposal.get("candidate_transaction", {})
    errors.extend(lineage_errors(root, identity, "P4-R-I"))
    errors.extend(lineage_errors(root, collection, "P4-R-C"))
    errors.extend(authority_errors(identity, "P4-R-I"))
    errors.extend(authority_errors(collection, "P4-R-C"))
    errors.extend(unresolved_errors(identity, IDENTITY_INPUTS, "P4-R-I"))
    errors.extend(unresolved_errors(collection, COLLECTION_INPUTS, "P4-R-C"))

    identity_gate = identity.get("gate", {})
    null_identity_fields = (
        "ssh_host_key_fingerprint",
        "authorization_id",
        "authorization_sha256",
        "issued_at_utc",
        "expires_at_utc",
        "signer_key_fingerprint",
        "detached_signature_sha256",
        "independent_review_sha256",
    )
    if any(identity_gate.get(name) is not None for name in null_identity_fields):
        errors.append("P4-R-I signature, time, host-key, and issuance values must be null")
    expected_observations = transaction.get("fresh_identity_authorization", {}).get(
        "required_fixed_observations"
    )
    if identity.get("fixed_read_only_observations") != expected_observations:
        errors.append("P4-R-I fixed read-only observations drifted")
    capture = identity.get("capture_contract", {})
    proposed_paths = transaction.get("proposed_paths", {})
    if (
        capture.get("artifact_path") != proposed_paths.get("identity_artifact")
        or capture.get("sidecar_path") != proposed_paths.get("identity_sidecar")
        or any(
            capture.get(name) is not None
            for name in (
                "artifact_sha256",
                "sidecar_sha256",
                "independent_review_sha256",
            )
        )
        or capture.get("stop_after_capture") is not True
        or capture.get("automatic_continuation_to_p4_r_c") is not False
    ):
        errors.append("P4-R-I capture, null-evidence, or stop boundary drifted")

    collection_lineage = collection.get("lineage", {})
    identity_path = root / str(collection_lineage.get("identity_template_path", ""))
    if (
        collection_lineage.get("identity_template_sha256")
        != IDENTITY_TEMPLATE_SHA256
        or not identity_path.is_file()
        or sha256(identity_path) != IDENTITY_TEMPLATE_SHA256
    ):
        errors.append("P4-R-C must bind the immutable unissued P4-R-I template")
    collection_gate = collection.get("gate", {})
    null_collection_fields = (
        "required_p4_r_i_artifact_sha256",
        "required_p4_r_i_review_sha256",
        "required_ssh_host_key_fingerprint",
        "authorization_id",
        "authorization_sha256",
        "issued_at_utc",
        "expires_at_utc",
        "signer_key_fingerprint",
        "detached_signature_sha256",
        "independent_review_sha256",
    )
    if any(collection_gate.get(name) is not None for name in null_collection_fields):
        errors.append("P4-R-C predecessor, signature, time, and issuance values must be null")

    release = collection.get("release", {})
    proposal_lineage = proposal.get("lineage", {})
    if (
        release.get("source_commit")
        != proposal_lineage.get("collector_release_source_commit")
        or release.get("archive_name")
        != proposal_lineage.get("collector_release_archive_name")
        or release.get("archive_bytes")
        != proposal_lineage.get("collector_release_archive_bytes")
        or release.get("archive_sha256")
        != proposal_lineage.get("collector_release_archive_sha256")
        or release.get("collector_binary_sha256")
        != proposal_lineage.get("collector_binary_sha256")
        or release.get("collector_contract_sha256")
        != proposal_lineage.get("collector_contract_sha256")
    ):
        errors.append("P4-R-C immutable collector release drifted")
    expected_paths = {
        "capture_id": transaction.get("capture_id"),
        **{
            name: proposed_paths.get(name)
            for name in collection.get("paths", {})
            if name != "capture_id"
        },
    }
    if collection.get("paths") != expected_paths:
        errors.append("P4-R-C accepted literal paths drifted")

    staging = collection.get("staging_and_invocation", {})
    proposed_collection = transaction.get("staging_collection_authorization", {})
    invocation = proposed_collection.get("collector_invocation", {})
    if (
        staging.get("collector_argv") != invocation.get("argv")
        or staging.get("fixed_environment") != invocation.get("fixed_environment")
        or staging.get("shell") is not False
        or staging.get("glob") is not False
        or staging.get("inherited_environment") is not False
        or staging.get("direct_fixed_argv_transport_evidence") is not None
        or staging.get("create_exclusive") is not True
        or staging.get("archive_transfer_count") != 1
        or staging.get("collector_attempt_count") != 1
        or staging.get("retry_count") != 0
    ):
        errors.append("P4-R-C fixed launch or one-shot staging contract drifted")
    transfer = transaction.get("transfer_and_verification_contract", {})
    if collection.get("ordered_actions") != transfer.get("ordered_actions"):
        errors.append("P4-R-C thirteen ordered verification actions drifted")
    expected_limits = {
        key: transfer.get(key)
        for key in collection.get("limits", {})
    }
    if collection.get("limits") != expected_limits:
        errors.append("P4-R-C exact bounded limits drifted")
    if collection.get("rollback") != transaction.get("rollback_contract"):
        errors.append("P4-R-C stop-retain-no-delete rollback drifted")
    if collection.get("stop_conditions") != transaction.get("stop_conditions"):
        errors.append("P4-R-C eleven stop-condition groups drifted")

    if sha256(root / "config/q15/q15-r-p4-r-i.authorization-template-v1.json") != (
        IDENTITY_TEMPLATE_SHA256
    ):
        errors.append("P4-R-I template bytes drifted")
    if sha256(root / "config/q15/q15-r-p4-r-c.authorization-template-v1.json") != (
        COLLECTION_TEMPLATE_SHA256
    ):
        errors.append("P4-R-C template bytes drifted")

    p4_r_path = root / "config/q15/q15-r-p4-r.preparation-v2.json"
    p4_k_path = root / "config/q15/q15-r-p4-k.preparation.json"
    if sha256(p4_r_path) != P4_R_SHA256:
        errors.append("P4-R v2 predecessor bytes drifted")
    if sha256(p4_k_path) != P4_K_SHA256:
        errors.append("P4-K predecessor bytes drifted")
    p4_r = load(p4_r_path)
    p4_k = load(p4_k_path)
    if len(p4_r.get("remaining_required_inputs", [])) != 7 or any(
        item.get("value") is not None
        for item in p4_r.get("remaining_required_inputs", [])
    ):
        errors.append("P4-R v2 must retain seven null inputs")
    if len(p4_k.get("unresolved_inputs", [])) != 8 or any(
        item.get("value") is not None for item in p4_k.get("unresolved_inputs", [])
    ):
        errors.append("P4-K must retain eight null inputs")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    identity = load(root / "config/q15/q15-r-p4-r-i.authorization-template-v1.json")
    collection = load(root / "config/q15/q15-r-p4-r-c.authorization-template-v1.json")
    identity_schema = load(
        root
        / "config/schemas/q15-r-p4-r-i-authorization-template-v1.schema.json"
    )
    collection_schema = load(
        root
        / "config/schemas/q15-r-p4-r-c-authorization-template-v1.schema.json"
    )
    Draft202012Validator.check_schema(identity_schema)
    Draft202012Validator.check_schema(collection_schema)
    identity_validator = Draft202012Validator(identity_schema)
    collection_validator = Draft202012Validator(collection_schema)
    errors = [item.message for item in identity_validator.iter_errors(identity)]
    errors.extend(item.message for item in collection_validator.iter_errors(collection))
    errors.extend(semantic_errors(root, identity, collection))

    negatives: list[tuple[dict[str, Any], dict[str, Any]]] = []
    mutant_i = copy.deepcopy(identity)
    mutant_i["authority_boundary"]["stand_access_authorized"] = True
    negatives.append((mutant_i, copy.deepcopy(collection)))
    mutant_i = copy.deepcopy(identity)
    mutant_i["fixed_read_only_observations"][0]["argv"] = ["/usr/bin/id"]
    negatives.append((mutant_i, copy.deepcopy(collection)))
    mutant_i = copy.deepcopy(identity)
    mutant_i["capture_contract"]["automatic_continuation_to_p4_r_c"] = True
    negatives.append((mutant_i, copy.deepcopy(collection)))
    mutant_i = copy.deepcopy(identity)
    mutant_i["gate"]["ssh_host_key_fingerprint"] = "SHA256:fabricated"
    negatives.append((mutant_i, copy.deepcopy(collection)))
    mutant_c = copy.deepcopy(collection)
    mutant_c["gate"]["required_p4_r_i_artifact_sha256"] = "0" * 64
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["staging_and_invocation"]["retry_count"] = 1
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["staging_and_invocation"]["shell"] = True
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["ordered_actions"].pop()
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["paths"]["stand_transaction_root"] = "/tmp/invented"
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["release"]["archive_sha256"] = "0" * 64
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["rollback"]["delete_authorized"] = True
    negatives.append((copy.deepcopy(identity), mutant_c))
    mutant_c = copy.deepcopy(collection)
    mutant_c["authority_boundary"]["collector_execution_authorized"] = True
    negatives.append((copy.deepcopy(identity), mutant_c))

    for index, (mutant_identity, mutant_collection) in enumerate(negatives):
        mutant_errors = [
            item.message for item in identity_validator.iter_errors(mutant_identity)
        ]
        mutant_errors.extend(
            item.message
            for item in collection_validator.iter_errors(mutant_collection)
        )
        mutant_errors.extend(
            semantic_errors(root, mutant_identity, mutant_collection)
        )
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-p4-r-successor-templates-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    print(
        "q15-r-p4-r-successor-templates-check: PASS "
        "(P4-R-I/P4-R-C split, 6+6 null inputs, 12 negative, "
        "issued=NO, operational authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
