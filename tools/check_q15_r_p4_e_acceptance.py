#!/usr/bin/env python3
"""Validate Q15-R-P4-E acceptance and its no-authority successor boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_ACCEPTANCE = (
    "Q15-R-P4-E — accept D-071 and select clean commit "
    "34da95d002e912069c959bfef8e88a23b4880cea with no-authority v3 archive "
    "SHA-256 f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a "
    "as the exact Q15-R-P4-R collector-release evidence input only. Authorize "
    "repository-local creation and verification of a versioned successor P4-R "
    "preparation that resolves only the clean collector-release evidence group, "
    "leaves the other seven P4-R inputs null, and preserves P4-K unchanged with "
    "all eight inputs null. Do not access or modify the stand, select or create "
    "literal paths, transfer or install artifacts, execute the collector, create, "
    "import, copy, or use keys, issue, sign, or execute Q15-R-P4-R, Q15-R-P4-K, "
    "Q15-R, or Q15-W, perform PMU/MSR/affinity/NUMA operations, calibrate, pilot, "
    "measure, or perform confirmatory work. Every external-input and execution "
    "phase requires separate explicit approval."
)
EXPECTED_PROPOSAL_SHA256 = (
    "89092ce9158267a20540878514fb1b629db3ab021f9b49863e57f922672b4b71"
)
EXPECTED_PREDECESSOR_SHA256 = (
    "1925d9e8d23e42df5feef4bb900de3010a7a612724417f446f8df5d42aa11d9e"
)
EXPECTED_P4_K_SHA256 = (
    "c56ae3dc74142d244e448b9a6f638960f0cce1eb1a9e7a106fea90a4bcf55e0f"
)
EXPECTED_SUCCESSOR_SHA256 = (
    "f8c63d1f95d69c6a9562cfec6d2635757c9dbba80137d68fdedf56bd189b6ba4"
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(root: pathlib.Path, value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    binding = value.get("decision_input_binding", {})
    proposal_path = root / binding.get("path", "")
    if (
        binding.get("sha256") != EXPECTED_PROPOSAL_SHA256
        or not proposal_path.is_file()
        or sha256(proposal_path) != EXPECTED_PROPOSAL_SHA256
    ):
        errors.append("P4-E acceptance must bind the immutable D-071 proposal")
    if value.get("user_acceptance") != EXPECTED_ACCEPTANCE:
        errors.append("P4-E acceptance text mismatch")
    boundary = value.get("authority_boundary", {})
    true_authority = {
        name
        for name, state in boundary.items()
        if name.endswith("_authorized") and state is True
    }
    if true_authority != {"repository_local_successor_preparation_authorized"}:
        errors.append("P4-E acceptance widens authority")

    constraints = value.get("successor_constraints", {})
    predecessor_path = root / constraints.get("predecessor_path", "")
    if (
        constraints.get("predecessor_sha256") != EXPECTED_PREDECESSOR_SHA256
        or not predecessor_path.is_file()
        or sha256(predecessor_path) != EXPECTED_PREDECESSOR_SHA256
    ):
        errors.append("P4-E acceptance must preserve the immutable P4-R predecessor")

    p4_k = value.get("p4_k_preservation", {})
    p4_k_path = root / p4_k.get("path", "")
    if (
        p4_k.get("sha256") != EXPECTED_P4_K_SHA256
        or not p4_k_path.is_file()
        or sha256(p4_k_path) != EXPECTED_P4_K_SHA256
    ):
        errors.append("P4-E acceptance must preserve the immutable P4-K preparation")

    proposal = load(proposal_path) if proposal_path.is_file() else {}
    release = value.get("release_selection", {})
    evidence = proposal.get("collector_release_evidence", {})
    if (
        release.get("source_commit") != evidence.get("source_revision")
        or release.get("archive_name") != evidence.get("archive_name")
        or release.get("archive_sha256") != evidence.get("archive_sha256")
        or release.get("bundle_profile") != evidence.get("bundle_profile")
        or release.get("authority") != "NONE"
    ):
        errors.append("P4-E selection does not match the proposed release bytes")

    successor = root / "config/q15/q15-r-p4-r.preparation-v2.json"
    if not successor.is_file() or sha256(successor) != EXPECTED_SUCCESSOR_SHA256:
        errors.append("authorized versioned P4-R successor is missing or has drifted")
    elif (
        load(successor).get("acceptance_binding", {}).get("sha256")
        != sha256(root / "config/q15/q15-r-p4-e-acceptance-v1.json")
    ):
        errors.append("P4-R successor does not bind this acceptance")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-e-acceptance-v1.json")
    schema = load(root / "config/schemas/q15-r-p4-e-acceptance-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))

    negatives = []
    authority = copy.deepcopy(record)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    proposal = copy.deepcopy(record)
    proposal["decision_input_binding"]["sha256"] = "0" * 64
    negatives.append(proposal)
    release = copy.deepcopy(record)
    release["release_selection"]["archive_sha256"] = "0" * 64
    negatives.append(release)
    widened = copy.deepcopy(record)
    widened["successor_constraints"]["remaining_external_input_names"].pop()
    negatives.append(widened)
    p4_k = copy.deepcopy(record)
    p4_k["p4_k_preservation"]["sha256"] = "0" * 64
    negatives.append(p4_k)
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p4-e-acceptance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p4-e-acceptance-check: PASS "
        "(D-071 accepted, successor hash-bound, P4-K preserved, "
        "5 negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
