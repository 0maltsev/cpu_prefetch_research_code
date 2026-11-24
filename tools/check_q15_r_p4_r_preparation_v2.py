#!/usr/bin/env python3
"""Validate the Q15-R-P4-E successor P4-R preparation without authority."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_REMAINING = (
    "COLLECTOR_RELEASE_ROOT",
    "AUTHORIZATION_ID_CANONICAL_BYTES_AND_SHA256",
    "NAMED_AUTHORITY_PRINCIPAL_ISSUE_AND_EXPIRY_UTC",
    "CAPTURE_ID",
    "OUTPUT_STDOUT_STDERR_AND_SIDECAR_CUSTODY_DESTINATIONS",
    "DETACHED_SIGNATURE_AND_INDEPENDENT_REVIEW_ARTIFACTS",
    "FRESH_PRE_EXECUTION_STAND_IDENTITY_BINDING",
)
EXPECTED_RELEASE_NAME = (
    "CLEAN_COLLECTOR_SOURCE_COMMIT_ARCHIVE_MANIFEST_SBOM_BINARY_AND_CONTRACT_HASHES"
)
EXPECTED_RELEASE = {
    "archive_bytes": 4_642_298,
    "archive_name": (
        "cpu-prefetch-q15-qualification-tool-2.0.0-"
        "34da95d-clean-5fc75063e1d1.tar.gz"
    ),
    "archive_sha256": "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a",
    "bundle_manifest_sha256": "84338ec24a1af44468c5a37d5c8aeedec126abc8fdc5ec846d15685aca178f20",
    "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v3",
    "collector_binary_sha256": "4716e1dfc2e65fd61dce1ea54a70fd876a0b4322b69d9ad1fde5c67a65c48a57",
    "collector_contract_sha256": "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87",
    "controller_binary_sha256": "1b23a743de084449cb622f14b1301b37af1c59878c6ca70abce1bb875a853f45",
    "controller_codegen_report_sha256": "7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca",
    "internal_file_count": 154,
    "internal_sha256s_sha256": "6880faa79b0b7a9faaabe788b01dd2cd7d441d8646efd31d8929acba63f8f525",
    "p4_d_acceptance_sha256": "1645c2a7fb356272afbf9377b99784e307f54f8a7df5fbb09f46d70edae3c521",
    "prestate_validator_sha256": "6f8ee09975a3c610f57b16117e6906f26af9482a5b750d30e2bdfa2c9552f247",
    "probe_codegen_report_sha256": "cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa",
    "q15_qualification_library_sha256": "c8364af26d355bd736e557058db77274a3fab6d539b8622c4f0905d1be470bad",
    "q15_tool_binary_sha256": "10386c653fe33c9d8ac60b205962fed12a5240ccd354ba82ae30533f01c0d217",
    "repository_license": "NO-LICENSE-GRANT",
    "runtime_codegen_report_sha256": "e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014",
    "sbom_sha256": "a9bc3b59726c54171b0510c964d1ac05ece652593b33abc8238083ff14ed8e93",
    "sidecar_sha256": "f2bf9e3f2ed97541905b7e0fbc24dfa15d3b5c3096bd7e9ab0d23dcdbe0fffd4",
    "source_archive_name": "cpu-prefetch-source-34da95d-clean.tar.gz",
    "source_archive_sha256": "5fc75063e1d1d0a1602beec4e10c11080d8b02511755951210009bcc2586625c",
    "source_commit": "34da95d002e912069c959bfef8e88a23b4880cea",
    "version_metadata_sha256": "7d9df7638e30dafdd1c0d52abdcff9ff8511ed0a98e33c4119ddcdfaa500ea49",
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
        ("p4_k_binding", "path", "sha256"),
    ):
        binding = value.get(binding_name, {})
        path = root / binding.get(path_name, "")
        if not path.is_file() or sha256(path) != binding.get(hash_name):
            errors.append(f"{binding_name} is missing or has drifted")

    remaining = value.get("remaining_required_inputs", [])
    if tuple(item.get("name") for item in remaining) != EXPECTED_REMAINING:
        errors.append("successor must retain exactly seven P4-R inputs in order")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in remaining
    ):
        errors.append("successor cannot fabricate an external P4-R input")

    resolved = value.get("resolved_input_groups", [])
    if (
        len(resolved) != 1
        or resolved[0].get("name") != EXPECTED_RELEASE_NAME
        or resolved[0].get("state")
        != "RESOLVED_BY_Q15_R_P4_E_ACCEPTED_VERIFIED_LOCAL_EVIDENCE"
        or resolved[0].get("value") != EXPECTED_RELEASE
    ):
        errors.append("successor may resolve only the exact accepted release group")

    boundary = value.get("authority_boundary", {})
    true_authority = {
        name
        for name, state in boundary.items()
        if name.endswith("_authorized") and state is True
    }
    if true_authority != {"repository_local_preparation_authorized"}:
        errors.append("successor preparation grants external authority")

    predecessor = load(root / "config/q15/q15-r-p4-r.preparation.json")
    if value.get("exact_invocation_template") != predecessor.get(
        "exact_invocation_template"
    ):
        errors.append("successor invocation template must preserve the predecessor")
    if value.get("internal_command_ids") != predecessor.get("internal_command_ids"):
        errors.append("successor must preserve all 25 command IDs")
    if value.get("limits") != predecessor.get("limits"):
        errors.append("successor must preserve all fixed collector limits")

    p4_k = load(root / "config/q15/q15-r-p4-k.preparation.json")
    if len(p4_k.get("unresolved_inputs", [])) != 8 or p4_k.get(
        "future_authorization", {}
    ).get("status") != "NOT_ISSUED":
        errors.append("P4-K must remain unissued with eight unresolved inputs")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-r.preparation-v2.json")
    schema = load(root / "config/schemas/q15-r-p4-r-preparation-v2.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))

    negatives = []
    authority = copy.deepcopy(record)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    lineage = copy.deepcopy(record)
    lineage["lineage"]["predecessor_sha256"] = "0" * 64
    negatives.append(lineage)
    release = copy.deepcopy(record)
    release["resolved_input_groups"][0]["value"]["archive_sha256"] = "0" * 64
    negatives.append(release)
    fabricated = copy.deepcopy(record)
    fabricated["remaining_required_inputs"][0] = {
        "name": "COLLECTOR_RELEASE_ROOT",
        "state": "RESOLVED",
        "value": "/unapproved/path",
    }
    negatives.append(fabricated)
    missing = copy.deepcopy(record)
    missing["remaining_required_inputs"].pop()
    negatives.append(missing)
    command = copy.deepcopy(record)
    command["internal_command_ids"].pop()
    negatives.append(command)
    issued = copy.deepcopy(record)
    issued["future_authorization"]["status"] = "AUTHORIZED"
    negatives.append(issued)
    p4_k = copy.deepcopy(record)
    p4_k["p4_k_binding"]["sha256"] = "0" * 64
    negatives.append(p4_k)
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-r-preparation-v2-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-r-preparation-v2-check: PASS "
        "(1 collector-release group resolved, 7 P4-R + 8 P4-K unresolved, "
        "25 commands, 8 negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
