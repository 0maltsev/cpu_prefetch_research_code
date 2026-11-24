#!/usr/bin/env python3
"""Validate Q15-R-P1 controller and unapplied role/custody profiles."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


EXPECTED_PRINCIPALS = (
    "cpu-prefetch-q15-operator",
    "cpu-prefetch-q15-controller",
    "cpu-prefetch-q15-custodian",
    "cpu-prefetch-q15-auditor",
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def reject(validator: Draft202012Validator, document: dict[str, object], name: str) -> None:
    if not list(validator.iter_errors(document)):
        raise AssertionError(f"q15-controller-profile negative accepted: {name}")


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    profile_path = root / "config/q15/q15-r-controller-profile-v1.json"
    setup_path = root / "config/q15/q15-r-role-custody-setup-plan-v1.json"
    profile_schema = load(
        root / "config/schemas/q15-r-controller-profile-v1.schema.json"
    )
    setup_schema = load(
        root / "config/schemas/q15-r-role-custody-setup-plan-v1.schema.json"
    )
    profile = load(profile_path)
    setup = load(setup_path)
    Draft202012Validator.check_schema(profile_schema)
    Draft202012Validator.check_schema(setup_schema)
    profile_validator = Draft202012Validator(profile_schema)
    setup_validator = Draft202012Validator(setup_schema)
    for name, validator, document in (
        ("controller", profile_validator, profile),
        ("setup", setup_validator, setup),
    ):
        errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
        if errors:
            for error in errors:
                print(
                    f"q15-controller-profile-check: FAIL: {name}: {error.message}",
                    file=sys.stderr,
                )
            return 1

    source_paths: set[str] = set()
    for binding in profile["source_bindings"]:
        relative = pathlib.Path(binding["path"])
        if relative.is_absolute() or ".." in relative.parts:
            print("q15-controller-profile-check: FAIL: unsafe source path", file=sys.stderr)
            return 1
        if binding["path"] in source_paths:
            print("q15-controller-profile-check: FAIL: duplicate source path", file=sys.stderr)
            return 1
        source_paths.add(binding["path"])
        path = root / relative
        if not path.is_file() or sha256(path) != binding["sha256"]:
            print(
                f"q15-controller-profile-check: FAIL: source drift {relative}",
                file=sys.stderr,
            )
            return 1

    principals = tuple(profile["principal_ids"])
    setup_principals = tuple(item["principal_id"] for item in setup["principals"])
    if principals != EXPECTED_PRINCIPALS or setup_principals != EXPECTED_PRINCIPALS:
        print("q15-controller-profile-check: FAIL: principal order", file=sys.stderr)
        return 1
    if len(set(principals)) != 4:
        print("q15-controller-profile-check: FAIL: principals not distinct", file=sys.stderr)
        return 1
    domains = [item["domain_id"] for item in setup["custody_domains"]]
    if len(set(domains)) != 2 or tuple(domains) != (
        profile["custody_contract"]["primary_domain_id"],
        profile["custody_contract"]["secondary_domain_id"],
    ):
        print("q15-controller-profile-check: FAIL: custody domains", file=sys.stderr)
        return 1

    negative_count = 0
    for description, mutate, validator, document in (
        (
            "stand authority",
            lambda value: value["authority_boundary"].__setitem__(
                "stand_access_authorized", True
            ),
            profile_validator,
            profile,
        ),
        (
            "retry",
            lambda value: value["command_contract"].__setitem__(
                "retry_or_fallback", True
            ),
            profile_validator,
            profile,
        ),
        (
            "graph drift",
            lambda value: value["command_contract"]["graph"].reverse(),
            profile_validator,
            profile,
        ),
        (
            "limit drift",
            lambda value: value["limits"].__setitem__(
                "external_start_watchdog_seconds", 61
            ),
            profile_validator,
            profile,
        ),
        (
            "account applied",
            lambda value: value["principals"][0].__setitem__(
                "account_created", True
            ),
            setup_validator,
            setup,
        ),
        (
            "key evidence invented",
            lambda value: value["principals"][0].__setitem__(
                "public_key_fingerprint", "SHA256:invented"
            ),
            setup_validator,
            setup,
        ),
        (
            "filesystem applied",
            lambda value: value["custody_domains"][0].__setitem__(
                "path_created", True
            ),
            setup_validator,
            setup,
        ),
        (
            "setup authority",
            lambda value: value["authority_boundary"].__setitem__(
                "account_creation_authorized", True
            ),
            setup_validator,
            setup,
        ),
    ):
        mutant = copy.deepcopy(document)
        mutate(mutant)
        reject(validator, mutant, description)
        negative_count += 1

    print(
        "q15-controller-profile-check: PASS "
        f"(controller + unapplied setup, {negative_count} negative, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
