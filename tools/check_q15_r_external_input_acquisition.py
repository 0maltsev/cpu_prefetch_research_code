#!/usr/bin/env python3
"""Validate the proposed Q15-R-P4 external-input acquisition bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


DECISION_IDS = ("D-066", "D-067", "D-068", "D-069", "D-070")
INPUTS = (
    "@ALLOWED_SIGNERS_SOURCE@",
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
    "CURRENT_STAND_PRESTATE_ARTIFACT_ID_AND_SHA256",
    "ACTUAL_ALLOWED_SIGNERS_ARTIFACT_ID_SHA256_AND_ED25519_FINGERPRINT",
)
GATES = ("Q15-R-P4-D", "Q15-R-P4-R", "Q15-R-P4-K", "Q15-R-P5", "Q15-R", "Q15-W")
EXPECTED_HASHES = {
    "config/q15/q15-r-p3-acceptance-v1.json": (
        "8b90ed2e6bf865b7df2b05aef7e18a8c7aeacac953b79baa7fb2ed7ea03dd167"
    ),
    "config/q15/q15-r-stand-setup-authorization.preparation-v2.json": (
        "25ab86661f2a0ea1c92237aea06585e585bea9303f9309678e110978c7bd5338"
    ),
}


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decisions = document.get("decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISION_IDS:
        errors.append("D-066 through D-070 must be exact, unique, and ordered")
    if any(item.get("selected_option") is not None for item in decisions):
        errors.append("a proposal cannot fill an unaccepted decision")
    inputs = document.get("external_input_contracts", [])
    if tuple(item.get("name") for item in inputs) != INPUTS:
        errors.append("the five P3 external input groups must be exact and ordered")
    if tuple(item.get("decision_id") for item in inputs) != DECISION_IDS:
        errors.append("each external input must map one-to-one to D-066..D-070")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in inputs
    ):
        errors.append("external inputs cannot be fabricated or defaulted")
    boundary = document.get("authority_boundary", {})
    true_fields = {name for name, value in boundary.items() if value is True}
    if true_fields != {"repository_local_decision_bundle_preparation_authorized"}:
        errors.append("bundle widens authority beyond repository-local preparation")
    collector = document.get("proposed_prestate_collector_contract", {})
    if (
        collector.get("implementation_state") != "NOT_IMPLEMENTED"
        or collector.get("execution_authorized") is not False
        or collector.get("mutation_allowed") is not False
    ):
        errors.append("prestate collector must remain proposed and non-executable")
    gates = document.get("future_gates", [])
    if tuple(item.get("gate") for item in gates) != GATES:
        errors.append("future gates must remain exact, ordered, and separate")
    if any(item.get("state") not in {"NOT_ACCEPTED", "NOT_ISSUED"} for item in gates):
        errors.append("no future gate may be accepted or issued")
    lineage = document.get("lineage", {})
    bindings = {
        lineage.get("acceptance_path"): lineage.get("acceptance_sha256"),
        lineage.get("successor_preparation_path"): lineage.get(
            "successor_preparation_sha256"
        ),
    }
    if bindings != EXPECTED_HASHES:
        errors.append("P3 lineage paths or hashes drifted")
    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable lineage artifact mismatch: {relative}")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    document = load(
        root
        / "config/q15/q15-r-external-input-acquisition-decision-input-v1.json"
    )
    schema = load(
        root
        / "config/schemas/q15-r-external-input-acquisition-decision-input-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(document)]
    errors.extend(semantic_errors(root, document))

    negatives: list[dict[str, Any]] = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    selected = copy.deepcopy(document)
    selected["decisions"][0]["selected_option"] = "invented"
    negatives.append(selected)
    filled = copy.deepcopy(document)
    filled["external_input_contracts"][1]["value"] = "/invented/path"
    negatives.append(filled)
    missing = copy.deepcopy(document)
    missing["external_input_contracts"].pop()
    negatives.append(missing)
    reordered = copy.deepcopy(document)
    reordered["decisions"][0], reordered["decisions"][1] = (
        reordered["decisions"][1],
        reordered["decisions"][0],
    )
    negatives.append(reordered)
    implemented = copy.deepcopy(document)
    implemented["proposed_prestate_collector_contract"]["implementation_state"] = (
        "IMPLEMENTED"
    )
    negatives.append(implemented)
    mutating = copy.deepcopy(document)
    mutating["proposed_prestate_collector_contract"]["mutation_allowed"] = True
    negatives.append(mutating)
    issued = copy.deepcopy(document)
    issued["future_gates"][1]["state"] = "ISSUED"
    negatives.append(issued)
    drift = copy.deepcopy(document)
    drift["lineage"]["successor_preparation_sha256"] = "0" * 64
    negatives.append(drift)

    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-external-input-acquisition-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    print(
        "q15-r-external-input-acquisition-check: PASS "
        "(D-066..D-070 proposed, 5 unresolved, 9 negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
