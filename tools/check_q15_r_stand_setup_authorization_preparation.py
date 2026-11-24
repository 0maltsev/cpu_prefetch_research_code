#!/usr/bin/env python3
"""Validate the exact-but-blocked Q15-R stand-setup authorization preparation."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


def load(path: pathlib.Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def failures(validator: Draft202012Validator, value: dict[str, object]) -> list[str]:
    errors = [item.message for item in validator.iter_errors(value)]
    if any(value.get("authority_boundary", {}).values()):
        errors.append("stand-setup preparation grants authority")
    expected = {
        "setup_command_ids": [f"SETUP-{index:03d}" for index in range(1, 21)],
        "access_probe_ids": [f"NA-{index:03d}" for index in range(1, 25)],
        "rollback_ids": [f"RB-{index:03d}" for index in range(1, 11)],
    }
    contract = value.get("transaction_contract", {})
    for name, sequence in expected.items():
        if contract.get(name) != sequence:
            errors.append(f"{name} must be complete and ordered")
    if any(item.get("state") != "UNRESOLVED" or item.get("value") is not None for item in value.get("required_literal_inputs", [])):
        errors.append("preparation cannot fabricate unresolved operational input")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-stand-setup-authorization.preparation.json")
    schema = load(root / "config/schemas/q15-r-stand-setup-authorization-preparation-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    if errors := failures(validator, record):
        print(f"q15-r-stand-setup-preparation-check: FAIL: {errors}", file=sys.stderr)
        return 1
    contract = record["transaction_contract"]
    if sha256(root / contract["command_source_path"]) != contract["command_source_sha256"]:
        print("q15-r-stand-setup-preparation-check: FAIL: command source drift", file=sys.stderr)
        return 1
    profile_path = root / "config/q15/q15-r-trust-anchor-adapter-profile-v1.json"
    if sha256(profile_path) != record["implementation_binding"]["adapter_profile_sha256"]:
        print("q15-r-stand-setup-preparation-check: FAIL: adapter profile drift", file=sys.stderr)
        return 1
    negatives = []
    authority = copy.deepcopy(record)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    resolved = copy.deepcopy(record)
    resolved["required_literal_inputs"][0]["state"] = "RESOLVED"
    resolved["required_literal_inputs"][0]["value"] = "/tmp/unbound"
    negatives.append(resolved)
    omitted = copy.deepcopy(record)
    omitted["transaction_contract"]["access_probe_ids"].pop()
    negatives.append(omitted)
    issued = copy.deepcopy(record)
    issued["future_authorization_contract"]["status"] = "AUTHORIZED"
    negatives.append(issued)
    for index, mutant in enumerate(negatives):
        if not failures(validator, mutant):
            print(f"q15-r-stand-setup-preparation-check: FAIL: negative {index} passed", file=sys.stderr)
            return 1
    print("q15-r-stand-setup-preparation-check: PASS (20 setup, 24 access, 10 quarantine, 6 unresolved, authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
