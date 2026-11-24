#!/usr/bin/env python3
"""Validate Q15-R-P3 acceptance and its no-authority successor boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_ACCEPTANCE = (
    "Q15-R-P3 — accept D-065 and select clean commit "
    "c8b69abf0c6aec7b740efe78d998a93545302a94 with no-authority archive "
    "SHA-256 8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01 "
    "as the exact Q15-R operational-release evidence input. Authorize "
    "repository-local creation and verification of a versioned successor "
    "stand-setup preparation that resolves only the clean-release evidence "
    "group and leaves all five external input groups unresolved. Do not access "
    "or modify the stand, create accounts or keys, transfer or install "
    "artifacts, execute access probes, issue/sign/execute Q15-R or Q15-W, use "
    "real PMU/MSR/affinity/NUMA operations, calibrate, pilot, measure, or "
    "perform confirmatory work. Stand setup and every later phase require "
    "separate explicit approval."
)
EXPECTED_PROPOSAL_SHA256 = (
    "c7f7401f99ac25f2e56ceac889a6e64174efa047d2e06f71e74c2065aa2faa58"
)
EXPECTED_PREDECESSOR_SHA256 = (
    "a671fad5b45823a617140d9ee1f684235812daede0048fb67e1255ce74ecb057"
)
EXPECTED_SUCCESSOR_SHA256 = (
    "25ab86661f2a0ea1c92237aea06585e585bea9303f9309678e110978c7bd5338"
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
        errors.append("P3 acceptance must bind the immutable D-065 proposal")
    predecessor = value.get("successor_constraints", {})
    predecessor_path = root / predecessor.get("predecessor_path", "")
    if (
        predecessor.get("predecessor_sha256") != EXPECTED_PREDECESSOR_SHA256
        or not predecessor_path.is_file()
        or sha256(predecessor_path) != EXPECTED_PREDECESSOR_SHA256
    ):
        errors.append("P3 acceptance must preserve the immutable predecessor")
    if value.get("user_acceptance") != EXPECTED_ACCEPTANCE:
        errors.append("P3 acceptance text mismatch")
    boundary = value.get("authority_boundary", {})
    true_authority = {
        name
        for name, state in boundary.items()
        if name.endswith("_authorized") and state is True
    }
    if true_authority != {"repository_local_successor_preparation_authorized"}:
        errors.append("P3 acceptance widens authority")
    proposal = load(proposal_path) if proposal_path.is_file() else {}
    release = value.get("release_selection", {})
    evidence = proposal.get("operational_release_evidence", {})
    if (
        release.get("source_commit") != evidence.get("source_revision")
        or release.get("archive_name") != evidence.get("archive_name")
        or release.get("archive_sha256") != evidence.get("archive_sha256")
        or release.get("authority") != "NONE"
    ):
        errors.append("P3 selection does not match the proposed release bytes")
    successor = (
        root / "config/q15/q15-r-stand-setup-authorization.preparation-v2.json"
    )
    if not successor.is_file() or sha256(successor) != EXPECTED_SUCCESSOR_SHA256:
        errors.append("authorized versioned successor is missing or has drifted")
    elif successor.is_file():
        successor_value = load(successor)
        if (
            successor_value.get("acceptance_binding", {}).get("sha256")
            != sha256(root / "config/q15/q15-r-p3-acceptance-v1.json")
        ):
            errors.append("successor does not bind this acceptance")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p3-acceptance-v1.json")
    schema = load(root / "config/schemas/q15-r-p3-acceptance-v1.schema.json")
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
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-p3-acceptance-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "q15-r-p3-acceptance-check: PASS "
        "(D-065 accepted, successor hash-bound, 4 negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
