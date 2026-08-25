#!/usr/bin/env python3
"""Validate the exact D-097 public-only review authorization."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


AUTHORIZATION_SHA256 = "a34a244118dd43e6cd3b4780ae2432491832546ef36071870fabbec7d9dc9306"
ADR_SHA256 = "341eb2145a9a252e93bb1296792840c6f18a3f87a275670e76dd8e5cae5a414d"
WAIVER_SHA256 = "12e9ac9a1bc83c1c60ad95a477c6bcf2709576143cf9acc3f8fadb94561f7261"
TOOL_SHA256 = "139b734aab6a9313c3aedc58ea687256d1061661e995803a91349cc07beb71c9"
REVIEW_ROOT = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/review-v1")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path_field, hash_field, expected in (
        ("decision_adr_path", "decision_adr_sha256", ADR_SHA256),
        ("waiver_path", "waiver_sha256", WAIVER_SHA256),
        ("review_tool_path", "review_tool_sha256", TOOL_SHA256),
        ("d095_terminal_evidence_path", "d095_terminal_evidence_sha256", "ccfe61af14b8aca872a9fd0f4ab4371fb3e74cf445846c8b1a8b30e660f2fa2d"),
        ("d096_complete_evidence_path", "d096_complete_evidence_sha256", "8c30c1fb941179f0498943fd6ac34264ba185a318661513802fd1b2e29dfa4c8"),
        ("predecessor_template_path", "predecessor_template_sha256", "3a2c713552d59786cc0f2db623fb817ef3894020bc12733bfcb53c6cf04e7ceb"),
    ):
        path = root / str(record.get(path_field, ""))
        if record.get(hash_field) != expected or not path.is_file() or sha256(path) != expected:
            errors.append(f"binding mismatch: {path_field}")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "one_bootstrap_sshsig_authorized",
        "one_create_exclusive_public_review_authorized",
        "repository_local_records_tests_and_evidence_authorized",
    }:
        errors.append("D-097 authority omitted or widened")
    if (
        record.get("review_attempt_count") != 1
        or record.get("retry_count") != 0
        or record.get("overwrite_allowed") is not False
        or record.get("p5_or_later_authorized") is not False
        or record.get("review_separation_policy")
        != "EXPLICIT_SINGLE_OWNER_WAIVER_ACCEPTED_NO_INDEPENDENT_DETECTION"
    ):
        errors.append("one-attempt/single-owner/P5-stop contract drifted")
    source = (root / "tools/execute_d097_p4_k_r.py").read_text(encoding="utf-8")
    for forbidden in ("id_ed25519", "TARGET_PRIVATE", "BOOTSTRAP_PRIVATE", "shell=True", "os.system"):
        if forbidden in source:
            errors.append(f"review tool contains forbidden private/shell token: {forbidden}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-action-host", action="store_true")
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    path = root / "config/q15/q15-r-p4-k-r-d097-action-authorization-v1.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((root / "config/schemas/q15-r-p4-k-r-d097-action-authorization-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    if path.read_bytes() != canonical(record) or sha256(path) != AUTHORIZATION_SHA256:
        errors.append("authorization canonical bytes or SHA-256 mismatch")
    for index, (section, field, value) in enumerate((
        (None, "review_attempt_count", 2),
        (None, "retry_count", 1),
        (None, "overwrite_allowed", True),
        (None, "p5_or_later_authorized", True),
        ("authority_boundary", "private_key_access_or_presence_probe_authorized", True),
        ("authority_boundary", "stand_access_authorized", True),
        ("authority_boundary", "target_key_signing_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        target = mutant if section is None else mutant[section]
        target[field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    test = subprocess.run(
        ["/usr/bin/python3", str(root / "tools/execute_d097_p4_k_r.py"), "--self-test"],
        check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if test.returncode != 0 or "SELF-TEST PASS" not in test.stdout:
        errors.append("public-only review-tool self-test failed")
    if arguments.verify_action_host and os.path.lexists(REVIEW_ROOT):
        errors.append("create-exclusive D-097 review root already exists")
    if errors:
        for error in errors:
            print(f"d097-authorization-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + unused output path" if arguments.verify_action_host else ""
    print(f"d097-authorization-check: PASS (public-only, 7 negative{suffix}, P5/later authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
