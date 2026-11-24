#!/usr/bin/env python3
"""Validate D-095 terminal failure and optionally its public external evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_PUBLIC = {
    "action_authorization.json": ("e1a8934198dd2a581ff97564dfc33e4830750c18184893a18f37d80067a94728", 4045),
    "action_authorization.json.sig": ("9c447e077f388ebf257e16384eafbd81b54c267296db7c0633809b5c874f23f1", 330),
    "owner_pre_action_review.json": ("2bb30b1fe2f987e0efba9bbd4623e0682bac2302c15f3665c378014390f4fc5e", 521),
    "failure_receipt.json": ("efe4b3c8b526f20600c0d2217f5110afbbc97fb63676b12416030586b3ecea99", 332),
}
TARGET_PRIVATE = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/id_ed25519")
ALLOWED_SIGNERS = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public/allowed_signers")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field in (
        ("decision_adr_path", "decision_adr_sha256"),
        ("action_authorization_path", "action_authorization_sha256"),
        ("executed_action_tool_path", "executed_action_tool_sha256"),
    ):
        candidate = root / str(lineage.get(path_field, ""))
        if not candidate.is_file() or sha256(candidate) != lineage.get(hash_field):
            errors.append(f"lineage mismatch: {path_field}")
    observed = {
        item.get("filename"): (item.get("sha256"), item.get("size_bytes"))
        for item in record.get("public_artifacts", [])
    }
    if observed != EXPECTED_PUBLIC:
        errors.append("partial public-artifact inventory mismatch")
    failure = record.get("failure", {})
    target = record.get("target_key_state", {})
    disposition = record.get("disposition", {})
    if (
        failure.get("category") != "IMPLEMENTATION_ERROR_SUBPROCESS_STDIN_AND_INPUT_CONFLICT"
        or failure.get("automatic_retry_or_repair_performed") is not False
        or target.get("generation_attempts") != 0
        or target.get("private_path_present_by_metadata_check") is not False
        or target.get("private_content_read_or_hashed") is not False
        or disposition.get("d095_terminal") is not True
        or disposition.get("retry_repair_overwrite_cleanup_or_deletion_authorized") is not False
        or disposition.get("p4_k_r_eligible") is not False
        or disposition.get("automatic_continuation") is not False
    ):
        errors.append("terminal failure, no-target-key, or no-retry boundary drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "repository_local_failure_evidence_and_checker_authorized",
        "read_only_public_and_private_metadata_verification_authorized",
    }:
        errors.append("post-failure authority widened")
    return errors


def external_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    public_root = pathlib.Path(str(record["external_public_root"]))
    for filename, (expected_hash, expected_size) in EXPECTED_PUBLIC.items():
        candidate = public_root / filename
        if not candidate.is_file() or candidate.stat().st_size != expected_size or sha256(candidate) != expected_hash:
            errors.append(f"external public artifact mismatch: {filename}")
    # Metadata-only: never open or hash this target private path.
    if os.path.lexists(TARGET_PRIVATE):
        metadata = os.lstat(TARGET_PRIVATE)
        errors.append(f"target private path unexpectedly exists: mode={stat.S_IMODE(metadata.st_mode):04o}")
    verify = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(ALLOWED_SIGNERS),
         "-I", "cpu-prefetch-q15-authorization", "-n", "cpu-prefetch-q15-authorization",
         "-s", str(public_root / "action_authorization.json.sig")],
        check=False,
        input=(public_root / "action_authorization.json").read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )
    if verify.returncode != 0:
        errors.append("external public SSHSIG verification failed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-external", action="store_true")
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-k-a-d095-terminal-failure-evidence-v1.json")
    schema = load(root / "config/schemas/q15-r-p4-k-a-d095-terminal-failure-evidence-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    for index, (section, field, value) in enumerate((
        ("target_key_state", "generation_attempts", 1),
        ("target_key_state", "private_path_present_by_metadata_check", True),
        ("failure", "automatic_retry_or_repair_performed", True),
        ("disposition", "d095_terminal", False),
        ("disposition", "p4_k_r_eligible", True),
        ("authority_boundary", "second_signature_or_target_key_action_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        mutant[section][field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    if arguments.verify_external:
        errors.extend(external_errors(record))
    if errors:
        for error in errors:
            print(f"d095-terminal-failure-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + external public/private-metadata-only evidence" if arguments.verify_external else ""
    print(f"d095-terminal-failure-check: PASS (terminal, 6 negative{suffix}, P4-K-R/later authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
