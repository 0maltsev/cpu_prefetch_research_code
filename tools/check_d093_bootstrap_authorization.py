#!/usr/bin/env python3
"""Validate D-093 and its one-action boundary without generating a key."""

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


AUTHORIZATION_SHA256 = "271584663d21718357b6fcf013ca0a83a842410cae24d9463b4723217cdb954e"
ACTION_TOOL_SHA256 = "b98032e7353b37a10257603dc28b5e78d050440ff5090058f890c9bdbb2549ad"
ACTION_PYTHON_SHA256 = "d03d1d28647adf7842ad7eaddbc8cf9981d294afe7287ac9fe59bcc115dac5c2"
SSH_KEYGEN_SHA256 = "f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11"
ADR_SHA256 = "25caddc4f8a1f4917bf12ccf2e9fd7f1b08c740c242b54ca3257f9766ec53c09"
LINEAGE = (
    (
        "bootstrap_governance_root_proposal_path",
        "bootstrap_governance_root_proposal_sha256",
        "config/q15/q15-r-bootstrap-governance-root-decision-input-v1.json",
        "065d8a6d5f882bff84ee9bdbe27eb0e0c9e2bfea56c58cbe2b9bfc61cab3a4b7",
    ),
    (
        "bootstrap_blocking_adr_path",
        "bootstrap_blocking_adr_sha256",
        "docs/decisions/0083-q15-r-p4-k-a-bootstrap-governance-root.md",
        "fd608cabbf9a9bf01cc70c6f991a2c19564548ddf2baa45d017b31f7a505cfe5",
    ),
    (
        "generic_controller_profile_path",
        "generic_controller_profile_sha256",
        "config/q15/q15-r-p4-k-a-controller-profile-v1.json",
        "0ceafd80200ba62584532e035a4c2a21015c2b56f75d0ebbfdffbd7f3b945875",
    ),
)


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(
    root: pathlib.Path, record: dict[str, Any], verify_action_host: bool = False
) -> list[str]:
    errors: list[str] = []
    if record.get("decision_id") != "D-093":
        errors.append("only D-093 may authorize this action")
    lineage = record.get("lineage", {})
    for path_field, hash_field, expected_path, expected_hash in LINEAGE:
        path = root / str(lineage.get(path_field, ""))
        if (
            lineage.get(path_field) != expected_path
            or lineage.get(hash_field) != expected_hash
            or not path.is_file()
            or sha256(path) != expected_hash
        ):
            errors.append(f"immutable lineage mismatch: {path_field}")

    action_tool = root / str(record.get("action_tool_path", ""))
    if (
        record.get("action_tool_sha256") != ACTION_TOOL_SHA256
        or not action_tool.is_file()
        or sha256(action_tool) != ACTION_TOOL_SHA256
    ):
        errors.append("action-tool identity mismatch")
    if (
        record.get("ssh_keygen_sha256") != SSH_KEYGEN_SHA256
        or record.get("action_python_sha256") != ACTION_PYTHON_SHA256
    ):
        errors.append("recorded action-host tool identity mismatch")
    if verify_action_host:
        ssh_keygen = pathlib.Path(str(record.get("ssh_keygen_absolute_path", "")))
        if not ssh_keygen.is_file() or sha256(ssh_keygen) != SSH_KEYGEN_SHA256:
            errors.append("action-host ssh-keygen identity mismatch")
        action_python = pathlib.Path(
            str(record.get("action_python_absolute_path", ""))
        )
        if not action_python.is_file() or sha256(action_python) != ACTION_PYTHON_SHA256:
            errors.append("action-host Python identity mismatch")

    downgrade = record.get("selected_security_downgrade", {})
    if set(downgrade.values()) != {True}:
        errors.append("every exact D-093 downgrade and risk acceptance must be true")
    if (
        record.get("action_attempt_count") != 1
        or record.get("retry_count") != 0
        or record.get("overwrite_allowed") is not False
        or record.get("private_key_output_or_repository_import_allowed") is not False
        or record.get("p4_k_a_or_later_phase_authorized") is not False
    ):
        errors.append("one-attempt no-output no-later-phase boundary drifted")
    boundary = record.get("authority_boundary", {})
    enabled = {
        name for name, value in boundary.items() if name.endswith("_authorized") and value
    }
    if enabled != {
        "repository_local_d093_acceptance_adr_schema_tool_and_test_authorized",
        "development_host_inventory_authorized",
        "one_create_exclusive_bootstrap_key_generation_authorized",
        "public_trust_artifact_creation_authorized",
    }:
        errors.append("D-093 authority widened or omitted an accepted local action")

    source = action_tool.read_text(encoding="utf-8") if action_tool.is_file() else ""
    forbidden = (
        "PRIVATE_KEY.read_bytes",
        "PRIVATE_KEY.read_text",
        "sha256_file(PRIVATE_KEY)",
        "open(PRIVATE_KEY",
        "shell=True",
        "os.system",
        "private_key_emitted\": True",
    )
    if any(token in source for token in forbidden):
        errors.append("action tool contains a forbidden private-read/output or shell seam")

    adr = root / "docs/decisions/0093-single-owner-development-host-unencrypted-bootstrap-root.md"
    if not adr.is_file() or sha256(adr) != ADR_SHA256:
        errors.append("ADR-0093 hash mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--verify-action-host",
        action="store_true",
        help="also recheck the exact development-host Python and ssh-keygen bytes",
    )
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-bootstrap-root-d093-action-authorization-v1.json"
    schema_path = (
        root
        / "config/schemas/q15-r-bootstrap-root-d093-action-authorization-v1.schema.json"
    )
    record = load(path)
    schema = load(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record, arguments.verify_action_host))
    if sha256(path) != AUTHORIZATION_SHA256:
        errors.append("D-093 action authorization bytes drifted")

    mutations: list[dict[str, Any]] = []
    for field, value in (
        ("action_attempt_count", 2),
        ("retry_count", 1),
        ("overwrite_allowed", True),
        ("private_key_encrypted", True),
        ("role_separation_required", True),
        ("independent_recovery_required", True),
        ("development_host_allowed", False),
        ("private_key_output_or_repository_import_allowed", True),
        ("p4_k_a_or_later_phase_authorized", True),
        ("algorithm", "ANY_KEY"),
    ):
        mutant = copy.deepcopy(record)
        mutant[field] = value
        mutations.append(mutant)
    path_mutant = copy.deepcopy(record)
    path_mutant["private_key_absolute_path"] += ".changed"
    mutations.append(path_mutant)
    authority_mutant = copy.deepcopy(record)
    authority_mutant["authority_boundary"]["stand_access_authorized"] = True
    mutations.append(authority_mutant)
    risk_mutant = copy.deepcopy(record)
    risk_mutant["selected_security_downgrade"][
        "critical_impersonation_and_key_loss_risks_accepted"
    ] = False
    mutations.append(risk_mutant)

    for index, mutant in enumerate(mutations):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    self_test = subprocess.run(
        [sys.executable, str(root / "tools/create_d093_bootstrap_root.py"), "--self-test"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if self_test.returncode != 0 or "SELF-TEST PASS" not in self_test.stdout:
        errors.append("D-093 action-tool no-key self-test failed")

    if errors:
        for error in errors:
            print(f"d093-bootstrap-authorization-check: FAIL: {error}", file=sys.stderr)
        return 1
    host_scope = " + action-host binaries" if arguments.verify_action_host else ""
    print(
        "d093-bootstrap-authorization-check: PASS "
        f"(1 create-exclusive action, 13 negative, no key generated{host_scope}, "
        "P4-K/stand/Q15/pilot authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
