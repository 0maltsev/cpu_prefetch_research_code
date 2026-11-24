#!/usr/bin/env python3
"""Validate complete D-097 public evidence without any private-key access."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import stat
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_PUBLIC = {
    "SHA256SUMS": ("67acc9b2858c500c56a7fd025850a1f4300458e47a61c5380cc7bd81a3bb83b5", 471),
    "accepted_public_trust_evidence.json": ("8d1a906d8c54576dd8bba179a5847dd1f735a874e8a8fb66ee957db5a41875a4", 638),
    "owner_pre_review_waiver.json": ("12e9ac9a1bc83c1c60ad95a477c6bcf2709576143cf9acc3f8fadb94561f7261", 1049),
    "review_authorization.json": ("a34a244118dd43e6cd3b4780ae2432491832546ef36071870fabbec7d9dc9306", 4284),
    "review_authorization.json.sig": ("ab874dcc46bea92330b101c9ea98ed233b745809964dcc9a5d396b2022eb2c78", 330),
    "review_receipt.json": ("5a3233fbbab534a762549455d3d8b7eefa2f7497c8ec0b0871da19cfdcee00f1", 964),
}
BOOTSTRAP_TRUST = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public/allowed_signers"
)
TARGET_PUBLIC = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public/target_public_key.pub"
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    lineage = record.get("lineage", {})
    for path_field, hash_field in (
        ("decision_adr_path", "decision_adr_sha256"),
        ("d095_terminal_evidence_path", "d095_terminal_evidence_sha256"),
        ("d096_complete_evidence_path", "d096_complete_evidence_sha256"),
        ("review_tool_path", "review_tool_sha256"),
        ("authorization_path", "authorization_sha256"),
        ("authorization_signature_path", "authorization_signature_sha256"),
        ("owner_waiver_path", "owner_waiver_sha256"),
    ):
        path = root / str(lineage.get(path_field, ""))
        if not path.is_file() or sha256(path) != lineage.get(hash_field):
            errors.append(f"lineage mismatch: {path_field}")
    observed = {
        item.get("filename"): (item.get("sha256"), item.get("size_bytes"))
        for item in record.get("public_artifacts", [])
    }
    if observed != EXPECTED_PUBLIC:
        errors.append("exact six-artifact review inventory mismatch")
    review = record.get("review_evidence", {})
    disposition = record.get("disposition", {})
    if (
        review.get("review_attempts") != 1
        or review.get("retry_count") != 0
        or review.get("private_key_access_or_presence_probe_performed") is not False
        or review.get("installation_or_activation_performed") is not False
        or disposition.get("d097_complete") is not True
        or disposition.get("automatic_continuation") is not False
        or disposition.get("next_gate") != "SEPARATE_P5_STAND_SETUP_DECISION_AND_AUTHORIZATION_REQUIRED"
    ):
        errors.append("review result or mandatory P5 stop boundary drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "read_only_external_public_evidence_verification_authorized",
        "repository_local_complete_evidence_and_checker_authorized",
    }:
        errors.append("post-D-097 authority omitted or widened")
    return errors


def external_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    public_root = pathlib.Path(str(record["external_review_root"]))
    for filename, (expected_hash, expected_size) in EXPECTED_PUBLIC.items():
        path = public_root / filename
        try:
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                errors.append(f"external public artifact type mismatch: {filename}")
                continue
            if metadata.st_size != expected_size or sha256(path) != expected_hash:
                errors.append(f"external public artifact mismatch: {filename}")
        except OSError as exception:
            errors.append(f"external public artifact unavailable: {filename}: {exception}")
    authorization = (public_root / "review_authorization.json").read_bytes()
    verify = subprocess.run([
        "/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(BOOTSTRAP_TRUST),
        "-I", "cpu-prefetch-q15-authorization", "-n", "cpu-prefetch-q15-authorization",
        "-s", str(public_root / "review_authorization.json.sig"),
    ], check=False, input=authorization, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if verify.returncode != 0:
        errors.append("external D-097 authorization SSHSIG verification failed")
    fingerprint = subprocess.run(
        ["/usr/bin/ssh-keygen", "-l", "-f", str(TARGET_PUBLIC), "-E", "sha256"],
        check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if fingerprint.returncode != 0 or "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM" not in fingerprint.stdout:
        errors.append("external target public fingerprint mismatch")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-external", action="store_true")
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    record = json.loads((root / "config/q15/q15-r-p4-k-r-d097-complete-evidence-v1.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "config/schemas/q15-r-p4-k-r-d097-complete-evidence-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    for index, (section, field, value) in enumerate((
        ("review_evidence", "review_attempts", 2),
        ("review_evidence", "retry_count", 1),
        ("review_evidence", "private_key_access_or_presence_probe_performed", True),
        ("review_evidence", "installation_or_activation_performed", True),
        ("disposition", "automatic_continuation", True),
        ("authority_boundary", "p5_installation_or_trust_activation_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        mutant[section][field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    if arguments.verify_external:
        errors.extend(external_errors(record))
    if errors:
        for error in errors:
            print(f"d097-complete-evidence-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + external public evidence" if arguments.verify_external else ""
    print(f"d097-complete-evidence-check: PASS (complete, 6 negative{suffix}, P5/later authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
