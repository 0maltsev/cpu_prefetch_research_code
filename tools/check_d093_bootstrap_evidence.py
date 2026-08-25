#!/usr/bin/env python3
"""Validate the repository D-093 evidence and created/not-active boundary."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


EVIDENCE = "config/q15/q15-r-bootstrap-root-d093-evidence-v1.json"
EVIDENCE_SCHEMA = "config/schemas/q15-r-bootstrap-root-d093-evidence-v1.schema.json"
LIFECYCLE = "config/q15/q15-r-bootstrap-root-d093-lifecycle-policy-v1.json"
LIFECYCLE_SCHEMA = (
    "config/schemas/q15-r-bootstrap-root-d093-lifecycle-policy-v1.schema.json"
)
EXPECTED_ARTIFACTS = {
    "SHA256SUMS": ("9d770c1c065e4d71c5f8e6bb5a5b9aac72f9468eed6fac42ee9742de59834570", 428),
    "action_authorization.json": ("271584663d21718357b6fcf013ca0a83a842410cae24d9463b4723217cdb954e", 5723),
    "allowed_signers": ("6c21b0d631a3842e182bd92e0856aa5073c949f5c5a6b4a8e85b48dd2016f33d", 112),
    "fingerprint.txt": ("eb40e36768566f4fc36a2fa1b75fec8bbc2b82aea94ef75780b4afee5ec87208", 51),
    "public_receipt.json": ("3c97bf7d6d12079ee247f823b66c4fc164258e317820c592661ecf055039cbc9", 1693),
    "root_public_key.pub": ("3a8d2f9eeb799a9be2af035beb00f4a6ef822fd0dad963c4eaea91344ff95527", 116),
}


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_schema(instance: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(instance)]


def semantic_errors(
    root: pathlib.Path, evidence: dict[str, Any], lifecycle: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    lineage = evidence.get("lineage", {})
    for path_name, hash_name in (
        ("action_authorization_path", "action_authorization_sha256"),
        ("decision_adr_path", "decision_adr_sha256"),
        ("action_tool_path", "action_tool_sha256"),
        ("read_only_verifier_path", "read_only_verifier_sha256"),
        ("lifecycle_policy_path", "lifecycle_policy_sha256"),
    ):
        relative = lineage.get(path_name)
        expected_hash = lineage.get(hash_name)
        candidate = root / str(relative)
        if not candidate.is_file() or sha256(candidate) != expected_hash:
            errors.append(f"lineage file/hash mismatch: {path_name}")

    resolutions = evidence.get("bootstrap_governance_resolution", [])
    if [entry.get("question_id") for entry in resolutions] != [
        "BGR-Q1", "BGR-Q2", "BGR-Q3", "BGR-Q4", "BGR-Q5", "BGR-Q6"
    ]:
        errors.append("BGR-Q1 through BGR-Q6 must appear exactly once and in order")

    observed = {
        entry.get("filename"): (entry.get("sha256"), entry.get("size_bytes"))
        for entry in evidence.get("public_trust_evidence", {}).get("artifacts", [])
    }
    if observed != EXPECTED_ARTIFACTS:
        errors.append("public artifact inventory/hash/size mapping mismatch")

    private = evidence.get("private_key_metadata_only", {})
    forbidden_private_fields = {
        "bytes",
        "content",
        "private_key",
        "private_key_sha256",
        "sha256",
    }
    if forbidden_private_fields.intersection(private):
        errors.append("private key bytes or content hash must not enter repository evidence")
    if (
        private.get("content_read_or_hashed_by_repository_tools") is not False
        or private.get("private_key_bytes_or_hash_recorded") is not False
    ):
        errors.append("private evidence is not metadata-only")

    root_state = evidence.get("root_lifecycle", {})
    if (
        root_state.get("current_state") != "CREATED"
        or root_state.get("activated_for_signing") is not False
        or root_state.get("used_to_sign") is not False
        or root_state.get("automatic_continuation") is not False
    ):
        errors.append("created root was promoted, used, or continued without authority")
    boundary = evidence.get("authority_boundary", {})
    enabled = {name for name, value in boundary.items() if value is True}
    if enabled != {"repository_evidence_and_policy_recording_authorized"}:
        errors.append("repository evidence authority widened into a later phase")

    if (
        lifecycle.get("decision_id") != evidence.get("decision_id")
        or lifecycle.get("transaction_id") != evidence.get("transaction_id")
        or lifecycle.get("fingerprint") != evidence.get("fingerprint")
        or lifecycle.get("current_root_state") != root_state.get("current_state")
    ):
        errors.append("lifecycle/evidence identity or state mismatch")
    lifecycle_boundary = lifecycle.get("authority_boundary", {})
    if (
        lifecycle_boundary.get("root_activation_authorized") is not False
        or lifecycle_boundary.get("root_signing_authorized") is not False
        or lifecycle_boundary.get("p4_k_a_or_p4_k_r_authorized") is not False
        or lifecycle_boundary.get("stand_or_q15_authorized") is not False
    ):
        errors.append("lifecycle policy grants unaccepted authority")
    if lifecycle.get("governance", {}).get(
        "activation_requires_separate_exact_authorization"
    ) is not True:
        errors.append("separate root-activation gate was removed")
    return errors


def mutations(record: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path, value in (
        (("root_lifecycle", "current_state"), "ACTIVE"),
        (("root_lifecycle", "activated_for_signing"), True),
        (("root_lifecycle", "used_to_sign"), True),
        (("root_lifecycle", "automatic_continuation"), True),
        (("authority_boundary", "root_activation_authorized"), True),
        (("authority_boundary", "root_signing_authorized"), True),
        (("authority_boundary", "stand_access_or_modification_authorized"), True),
        (("security_posture", "critical_key_loss_risk_accepted"), False),
    ):
        mutant = copy.deepcopy(record)
        mutant[path[0]][path[1]] = value
        result.append(mutant)
    duplicate = copy.deepcopy(record)
    duplicate["bootstrap_governance_resolution"][5]["question_id"] = "BGR-Q5"
    result.append(duplicate)
    artifact = copy.deepcopy(record)
    artifact["public_trust_evidence"]["artifacts"][0]["sha256"] = "0" * 64
    result.append(artifact)
    secret = copy.deepcopy(record)
    secret["private_key_metadata_only"]["private_key_sha256"] = "0" * 64
    result.append(secret)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-external",
        action="store_true",
        help="also run the read-only verifier against the development-host artifacts",
    )
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    evidence = load(root / EVIDENCE)
    evidence_schema = load(root / EVIDENCE_SCHEMA)
    lifecycle = load(root / LIFECYCLE)
    lifecycle_schema = load(root / LIFECYCLE_SCHEMA)
    errors = validate_schema(evidence, evidence_schema)
    errors.extend(validate_schema(lifecycle, lifecycle_schema))
    errors.extend(semantic_errors(root, evidence, lifecycle))

    validator = Draft202012Validator(evidence_schema)
    for index, mutant in enumerate(mutations(evidence)):
        rejected = list(validator.iter_errors(mutant)) or semantic_errors(
            root, mutant, lifecycle
        )
        if not rejected:
            errors.append(f"negative mutation {index} passed")

    if arguments.verify_external:
        external = subprocess.run(
            [sys.executable, str(root / "tools/verify_d093_bootstrap_evidence.py")],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if external.returncode != 0:
            errors.append(f"external read-only verifier failed: {external.stderr.strip()}")
        else:
            summary = json.loads(external.stdout)
            if (
                summary.get("fingerprint") != evidence.get("fingerprint")
                or summary.get("automatic_continuation") is not False
                or summary.get("private_key_metadata", {}).get("content_read_or_hashed")
                is not False
            ):
                errors.append("external verification summary differs from repository evidence")

    if errors:
        for error in errors:
            print(f"d093-bootstrap-evidence-check: FAIL: {error}", file=sys.stderr)
        return 1
    scope = " + external read-only artifacts" if arguments.verify_external else ""
    print(
        "d093-bootstrap-evidence-check: PASS "
        f"(CREATED, not active, 11 negative{scope}, later authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
