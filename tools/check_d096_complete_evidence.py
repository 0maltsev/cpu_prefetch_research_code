#!/usr/bin/env python3
"""Validate complete D-096 evidence without reading private-key content."""

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
    "SHA256SUMS": ("1bf9a96ce92c25369730ef97b69acf1cef8f37eef69b21dd53d50d3cb08d3489", 739),
    "action_authorization.json": ("8feb2ccffcd565ca9b202c8da736fe9f62e3869cb08e68ef87e38af6439be761", 4500),
    "action_authorization.json.sig": ("2514a67103b4850889653efd0c38b75d5669e7da97870d2c1ff1ccb6a16d7e0c", 330),
    "action_receipt.json": ("36db7093c7e8854c6307707883e856864ff58db0c48d69ee89a89f917e92f4d0", 2353),
    "bootstrap_signature_verification.json": ("f4a5ed840e005622b56482300221405f160618d99b76b08bdb8aced243b83cec", 625),
    "owner_pre_action_review.json": ("ea6c9a9a829becdd287f83e1600142fc874368287355512ab94c8e591db52724", 548),
    "target_allowed_signers": ("b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718", 112),
    "target_fingerprint.txt": ("9c0da30e9f634b01eab451dd2e129f246ff7c0783bac8aa323cbc18392cbbba0", 51),
    "target_public_key.pub": ("41cf7aab4c512c38dc0c3f802fdc0e3265cb3327828b5d3bcc0ba2cacf273b21", 106),
}
TARGET_PRIVATE = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/id_ed25519")
BOOTSTRAP_ALLOWED_SIGNERS = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public/allowed_signers")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field in (
        ("d095_terminal_evidence_path", "d095_terminal_evidence_sha256"),
        ("decision_adr_path", "decision_adr_sha256"),
        ("action_authorization_path", "action_authorization_sha256"),
        ("executed_action_tool_path", "executed_action_tool_sha256"),
        ("frozen_d095_helper_path", "frozen_d095_helper_sha256"),
    ):
        candidate = root / str(lineage.get(path_field, ""))
        if not candidate.is_file() or sha256(candidate) != lineage.get(hash_field):
            errors.append(f"lineage mismatch: {path_field}")
    observed = {
        item.get("filename"): (item.get("sha256"), item.get("size_bytes"))
        for item in record.get("public_artifacts", [])
    }
    if observed != EXPECTED_PUBLIC:
        errors.append("complete public-artifact inventory mismatch")
    target = record.get("target_key_evidence", {})
    d095 = record.get("d095_preservation", {})
    disposition = record.get("disposition", {})
    if (
        target.get("generation_attempts") != 1
        or target.get("private_content_read_or_hashed") is not False
        or target.get("fingerprint") != "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM"
        or d095.get("partial_public_tree_reverified") is not True
        or d095.get("target_private_path_remains_absent") is not True
        or d095.get("mutation_cleanup_or_deletion_performed") is not False
        or disposition.get("d096_complete") is not True
        or disposition.get("p4_k_r_executed") is not False
        or disposition.get("automatic_continuation") is not False
    ):
        errors.append("complete target, D-095 preservation, or P4-K-R stop boundary drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "repository_local_complete_evidence_and_checker_authorized",
        "read_only_public_and_private_metadata_verification_authorized",
    }:
        errors.append("post-D-096 authority widened")
    return errors


def external_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    public_root = pathlib.Path(str(record["external_public_root"]))
    for filename, (expected_hash, expected_size) in EXPECTED_PUBLIC.items():
        candidate = public_root / filename
        if not candidate.is_file() or candidate.stat().st_size != expected_size or sha256(candidate) != expected_hash:
            errors.append(f"external public artifact mismatch: {filename}")
    try:
        metadata = os.lstat(TARGET_PRIVATE)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != 1000
            or metadata.st_size != 419
        ):
            errors.append("target private metadata mismatch")
    except OSError as exception:
        errors.append(f"target private metadata unavailable: {exception}")
    authorization = (public_root / "action_authorization.json").read_bytes()
    verify = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(BOOTSTRAP_ALLOWED_SIGNERS),
         "-I", "cpu-prefetch-q15-authorization", "-n", "cpu-prefetch-q15-authorization",
         "-s", str(public_root / "action_authorization.json.sig")],
        check=False,
        input=authorization,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )
    if verify.returncode != 0:
        errors.append("external bootstrap SSHSIG verification failed")
    fingerprint = subprocess.run(
        ["/usr/bin/ssh-keygen", "-l", "-f", str(public_root / "target_public_key.pub"), "-E", "sha256"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )
    if fingerprint.returncode != 0 or "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM" not in fingerprint.stdout:
        errors.append("external target public fingerprint mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-external", action="store_true")
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    record = load(root / "config/q15/q15-r-p4-k-a-d096-complete-evidence-v1.json")
    schema = load(root / "config/schemas/q15-r-p4-k-a-d096-complete-evidence-v1.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    for index, (section, field, value) in enumerate((
        ("target_key_evidence", "generation_attempts", 2),
        ("target_key_evidence", "private_content_read_or_hashed", True),
        ("d095_preservation", "mutation_cleanup_or_deletion_performed", True),
        ("disposition", "d096_complete", False),
        ("disposition", "p4_k_r_executed", True),
        ("authority_boundary", "p4_k_r_or_later_phase_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        mutant[section][field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    if arguments.verify_external:
        errors.extend(external_errors(record))
    if errors:
        for error in errors:
            print(f"d096-complete-evidence-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + external public/private-metadata-only evidence" if arguments.verify_external else ""
    print(f"d096-complete-evidence-check: PASS (complete, 6 negative{suffix}, P4-K-R/later authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
