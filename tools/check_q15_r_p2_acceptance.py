#!/usr/bin/env python3
"""Validate Q15-R-P2 acceptance while preserving every later authority boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


DECISIONS = ("D-061", "D-062", "D-063", "D-064")


def load(path: pathlib.Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def failures(validator: Draft202012Validator, record: dict[str, object]) -> list[str]:
    errors = [item.message for item in validator.iter_errors(record)]
    decisions = record.get("accepted_decisions", [])
    if tuple(item.get("decision_id") for item in decisions) != DECISIONS:
        errors.append("accepted decisions must be unique and ordered D-061 through D-064")
    boundary = record.get("authority_boundary", {})
    permitted_true = {
        "operational_adapter_implementation_authorized",
        "release_and_setup_record_synchronization_authorized",
        "stand_setup_authorization_preparation_authorized",
    }
    if {key for key, value in boundary.items() if value is True} != permitted_true:
        errors.append("Q15-R-P2 authority has been widened or narrowed")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record_path = root / "config/q15/q15-r-p2-acceptance-v1.json"
    schema = load(root / "config/schemas/q15-r-p2-acceptance-v1.schema.json")
    record = load(record_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    proposal = root / record["proposal_binding"]["path"]
    if hashlib.sha256(proposal.read_bytes()).hexdigest() != record["proposal_binding"]["sha256"]:
        print("q15-r-p2-acceptance-check: FAIL: accepted proposal drift", file=sys.stderr)
        return 1
    if errors := failures(validator, record):
        print(f"q15-r-p2-acceptance-check: FAIL: {errors}", file=sys.stderr)
        return 1
    acceptance_sha = hashlib.sha256(record_path.read_bytes()).hexdigest()
    profile_path = root / "config/q15/q15-r-trust-anchor-adapter-profile-v1.json"
    profile_sha = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    setup_path = root / "config/q15/q15-r-stand-setup-authorization.preparation.json"
    setup_sha = hashlib.sha256(setup_path.read_bytes()).hexdigest()
    expected = {
        "acceptance_id": record["acceptance_id"],
        "acceptance_sha256": acceptance_sha,
        "adapter_profile_id": "Q15-R-TRUST-ANCHOR-ADAPTER-v1",
        "adapter_profile_sha256": profile_sha,
        "base_release_archive_sha256": "48c460b008790e3b73aefbda94cacddaeb3c842622ca5bac5c763e50515ae035",
        "base_release_authority": "NONE",
        "stand_setup_preparation_id": "Q15-R-STAND-SETUP-AUTHORIZATION-PREPARATION-20260825-01",
        "stand_setup_preparation_sha256": setup_sha,
    }
    synchronized = (
        load(root / "config/q15/q15-r-role-custody-setup-plan-v1.json").get(
            "accepted_operational_prerequisites"
        ),
        load(root / "config/q15/q15-r.preparation.json")
        .get("known_inputs", {})
        .get("q15_r_operational_prerequisites"),
        load(root / "config/q15/q15-w.preparation.json")
        .get("known_inputs", {})
        .get("q15_r_operational_prerequisites"),
    )
    if any(item != expected for item in synchronized):
        print("q15-r-p2-acceptance-check: FAIL: no-authority record synchronization drift", file=sys.stderr)
        return 1
    controller = load(root / "config/q15/q15-r-controller-profile-v1.json")
    adapter = controller.get("trust_anchor_adapter_binding", {})
    if (
        adapter.get("profile_id") != expected["adapter_profile_id"]
        or adapter.get("profile_sha256") != profile_sha
        or adapter.get("controller_cli_enabled") is not False
    ):
        print("q15-r-p2-acceptance-check: FAIL: controller adapter binding drift", file=sys.stderr)
        return 1
    negatives = []
    widened = copy.deepcopy(record)
    widened["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(widened)
    omitted = copy.deepcopy(record)
    omitted["accepted_decisions"].pop()
    negatives.append(omitted)
    reordered = copy.deepcopy(record)
    reordered["accepted_decisions"].reverse()
    negatives.append(reordered)
    for index, mutant in enumerate(negatives):
        if not failures(validator, mutant):
            print(f"q15-r-p2-acceptance-check: FAIL: negative {index} passed", file=sys.stderr)
            return 1
    print("q15-r-p2-acceptance-check: PASS (D-061..D-064 accepted, 4 records synchronized, 3 negative, authority=REPOSITORY_LOCAL_ONLY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
