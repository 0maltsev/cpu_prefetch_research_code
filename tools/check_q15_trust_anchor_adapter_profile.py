#!/usr/bin/env python3
"""Validate the repository-local no-authority Q15-R trust-anchor adapter."""

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
    descriptors = value.get("descriptor_contract", {})
    fds = [descriptors.get(name, {}).get("fd") for name in ("authorization_core", "detached_signature", "verification_receipt")]
    if fds != [3, 4, 5] or len(set(fds)) != 3:
        errors.append("descriptor contract must be exactly distinct FDs 3, 4, and 5")
    authority = value.get("authority_boundary", {})
    if any(item is True for name, item in authority.items() if name != "operational_adapter_implemented_repository_local"):
        errors.append("adapter profile grants operational authority")
    return errors


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    profile = load(root / "config/q15/q15-r-trust-anchor-adapter-profile-v1.json")
    schema = load(root / "config/schemas/q15-r-trust-anchor-adapter-profile-v1.schema.json")
    receipt_schema = load(root / "config/schemas/q15-r-signature-verification-receipt-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(receipt_schema)
    validator = Draft202012Validator(schema)
    if errors := failures(validator, profile):
        print(f"q15-trust-anchor-adapter-profile-check: FAIL: {errors}", file=sys.stderr)
        return 1
    for binding in profile["source_bindings"]:
        relative = pathlib.Path(binding["path"])
        if relative.is_absolute() or ".." in relative.parts or sha256(root / relative) != binding["sha256"]:
            print(f"q15-trust-anchor-adapter-profile-check: FAIL: source drift {relative}", file=sys.stderr)
            return 1
    acceptance = profile["acceptance_binding"]
    if sha256(root / acceptance["path"]) != acceptance["sha256"]:
        print("q15-trust-anchor-adapter-profile-check: FAIL: acceptance drift", file=sys.stderr)
        return 1
    negatives = []
    shell = copy.deepcopy(profile)
    shell["prohibited_interfaces"].remove("SHELL")
    negatives.append(shell)
    authority = copy.deepcopy(profile)
    authority["authority_boundary"]["q15_r_authorized"] = True
    negatives.append(authority)
    retry = copy.deepcopy(profile)
    retry["descriptor_contract"]["retry_or_fallback"] = True
    negatives.append(retry)
    fd_drift = copy.deepcopy(profile)
    fd_drift["descriptor_contract"]["verification_receipt"]["fd"] = 4
    negatives.append(fd_drift)
    anchor = copy.deepcopy(profile)
    anchor["trust_anchor_contract"]["private_key_permitted_on_stand"] = True
    negatives.append(anchor)
    for index, mutant in enumerate(negatives):
        if not failures(validator, mutant):
            print(f"q15-trust-anchor-adapter-profile-check: FAIL: negative {index} passed", file=sys.stderr)
            return 1
    print("q15-trust-anchor-adapter-profile-check: PASS (FDs=3/4/5, 5 negative, fakeable, authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
