#!/usr/bin/env python3
"""Validate the Q15-R-P3 successor setup preparation without stand authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_REMAINING = (
    "@ALLOWED_SIGNERS_SOURCE@",
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
    "CURRENT_STAND_PRESTATE_ARTIFACT_ID_AND_SHA256",
    "ACTUAL_ALLOWED_SIGNERS_ARTIFACT_ID_SHA256_AND_ED25519_FINGERPRINT",
)
EXPECTED_RELEASE_NAME = (
    "CLEAN_OPERATIONAL_RELEASE_ARCHIVE_MANIFEST_SBOM_BINARY_AND_REPORT_HASHES"
)
EXPECTED_RELEASE = {
    "archive_bytes": 4_356_358,
    "archive_name": (
        "cpu-prefetch-q15-qualification-tool-2.0.0-"
        "c8b69ab-clean-8d27197443f2.tar.gz"
    ),
    "archive_sha256": "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01",
    "bundle_manifest_sha256": "e5636a34c5dc083cfa01daa00091ee0baafa840174dda6ac2bbd1903115b7ebf",
    "controller_binary_sha256": "9bdda2b7eab5b4c50f82fc478f6c936a7a2bafffd85b05c68262360f3b04650d",
    "controller_codegen_report_sha256": "7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca",
    "internal_file_count": 133,
    "internal_sha256s_sha256": "b1c5d9cffa57d29800c97f51ecaea146139cb0624a379f38d50aab81a1c30281",
    "probe_codegen_report_sha256": "cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa",
    "q15_qualification_library_sha256": "c9eae879c66cda471b8bc2043bc6b61da21c64f008006ae969ab94faa44a27f0",
    "q15_tool_binary_sha256": "0b7afb5c0501c108c8ff17c3dbb319525d531b68e8a9b8d767f2ed0eab0a37d5",
    "runtime_codegen_report_sha256": "e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014",
    "sbom_sha256": "77a4fd2f44fa4d6c8d214d4bfa5eb7231ed3a5597f83437b7fe84d9de42b65df",
    "sidecar_sha256": "b251133526412f620ec3c5d9685b201a4b0280bb4fabc2382636c2c4b04343f1",
    "source_archive_name": "cpu-prefetch-source-c8b69ab-clean.tar.gz",
    "source_archive_sha256": "8d27197443f2ed016e6ac7e3788a0660fadab84ffc78e31934f4092bbc143df7",
    "source_commit": "c8b69abf0c6aec7b740efe78d998a93545302a94",
    "version_metadata_sha256": "7c9a6b7442a62beac9f3310e36ad997365269b24a34d86abb71ecfd3cebd27a0",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(root: pathlib.Path, value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for binding_name, path_name, hash_name in (
        ("acceptance_binding", "path", "sha256"),
        ("decision_binding", "decision_input_path", "decision_input_sha256"),
        ("lineage", "predecessor_path", "predecessor_sha256"),
    ):
        binding = value.get(binding_name, {})
        path = root / binding.get(path_name, "")
        if not path.is_file() or sha256(path) != binding.get(hash_name):
            errors.append(f"{binding_name} is missing or has drifted")
    profile = root / "config/q15/q15-r-trust-anchor-adapter-profile-v1.json"
    if (
        not profile.is_file()
        or sha256(profile)
        != value.get("implementation_binding", {}).get("adapter_profile_sha256")
    ):
        errors.append("adapter profile binding mismatch")
    command = value.get("transaction_contract", {})
    command_path = root / command.get("command_source_path", "")
    if not command_path.is_file() or sha256(command_path) != command.get(
        "command_source_sha256"
    ):
        errors.append("command-source binding mismatch")
    remaining = value.get("remaining_required_inputs", [])
    if tuple(item.get("name") for item in remaining) != EXPECTED_REMAINING:
        errors.append("successor must retain exactly five external inputs in order")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in remaining
    ):
        errors.append("successor cannot fabricate an external input")
    resolved = value.get("resolved_input_groups", [])
    if (
        len(resolved) != 1
        or resolved[0].get("name") != EXPECTED_RELEASE_NAME
        or resolved[0].get("state")
        != "RESOLVED_BY_Q15_R_P3_ACCEPTED_VERIFIED_LOCAL_EVIDENCE"
        or resolved[0].get("value") != EXPECTED_RELEASE
    ):
        errors.append("successor may resolve only the exact accepted release group")
    if any(value.get("authority_boundary", {}).values()):
        errors.append("successor preparation grants authority")
    transaction = value.get("transaction_contract", {})
    expected_sequences = {
        "setup_command_ids": [f"SETUP-{index:03d}" for index in range(1, 21)],
        "access_probe_ids": [f"NA-{index:03d}" for index in range(1, 25)],
        "rollback_ids": [f"RB-{index:03d}" for index in range(1, 11)],
    }
    for name, expected in expected_sequences.items():
        if transaction.get(name) != expected:
            errors.append(f"{name} must preserve the complete ordered transaction")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(
        root / "config/q15/q15-r-stand-setup-authorization.preparation-v2.json"
    )
    schema = load(
        root
        / "config/schemas/q15-r-stand-setup-authorization-preparation-v2.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))

    negatives = []
    authority = copy.deepcopy(record)
    authority["authority_boundary"]["stand_setup_execution_authorized"] = True
    negatives.append(authority)
    lineage = copy.deepcopy(record)
    lineage["lineage"]["predecessor_sha256"] = "0" * 64
    negatives.append(lineage)
    release = copy.deepcopy(record)
    release["resolved_input_groups"][0]["value"]["archive_sha256"] = "0" * 64
    negatives.append(release)
    fabricated = copy.deepcopy(record)
    fabricated["remaining_required_inputs"][0] = {
        "name": "@ALLOWED_SIGNERS_SOURCE@",
        "state": "RESOLVED",
        "value": "/tmp/unbound",
    }
    negatives.append(fabricated)
    missing = copy.deepcopy(record)
    missing["remaining_required_inputs"].pop()
    negatives.append(missing)
    transaction = copy.deepcopy(record)
    transaction["transaction_contract"]["access_probe_ids"].pop()
    negatives.append(transaction)
    issued = copy.deepcopy(record)
    issued["future_authorization_contract"]["status"] = "AUTHORIZED"
    negatives.append(issued)
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-stand-setup-preparation-v2-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-stand-setup-preparation-v2-check: PASS "
        "(1 release group resolved, 5 external unresolved, 20/24/10, "
        "7 negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
