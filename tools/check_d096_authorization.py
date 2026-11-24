#!/usr/bin/env python3
"""Validate D-096 authorization without using real credentials."""

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


AUTHORIZATION_SHA256 = "8feb2ccffcd565ca9b202c8da736fe9f62e3869cb08e68ef87e38af6439be761"
ADR_SHA256 = "1a6614ada5af2a47672ac9f715d89f34dd23ef7e672e39defe4cdb149a442046"
ACTION_TOOL_SHA256 = "7c9e7841348d8a51e7809ff9059110997bd308a7f53f2055a06b816846f518d3"
D095_HELPER_SHA256 = "dee54311e8698c50d63709b7294af9895c482647ca8a51b8a6341e08364a16c9"
D095_EVIDENCE_SHA256 = "ccfe61af14b8aca872a9fd0f4ab4371fb3e74cf445846c8b1a8b30e660f2fa2d"
PYTHON_SHA256 = "d03d1d28647adf7842ad7eaddbc8cf9981d294afe7287ac9fe59bcc115dac5c2"
SSH_KEYGEN_SHA256 = "f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11"
BOOTSTRAP_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519"
)
D095_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/id_ed25519"
)
D096_ROOT = pathlib.Path("/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2")


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def semantic_errors(root: pathlib.Path, record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    bindings = (
        ("decision_adr_path", "decision_adr_sha256", ADR_SHA256),
        ("action_tool_path", "action_tool_sha256", ACTION_TOOL_SHA256),
        ("d095_frozen_helper_path", "d095_frozen_helper_sha256", D095_HELPER_SHA256),
        ("d095_terminal_evidence_path", "d095_terminal_evidence_sha256", D095_EVIDENCE_SHA256),
    )
    for path_field, hash_field, expected in bindings:
        candidate = root / str(record.get(path_field, ""))
        if record.get(hash_field) != expected or not candidate.is_file() or sha256(candidate) != expected:
            errors.append(f"immutable binding mismatch: {path_field}")
    if record.get("action_python_sha256") != PYTHON_SHA256 or record.get("ssh_keygen_sha256") != SSH_KEYGEN_SHA256:
        errors.append("action-host tool identity mismatch")
    if set(record.get("selected_security_downgrade", {}).values()) != {True}:
        errors.append("all accepted D-096 security downgrade values must be true")
    regression = record.get("regression_contract", {})
    if regression != {
        "disposable_key_only": True,
        "real_bootstrap_or_target_key_used_by_test": False,
        "sign_verify_success_required": True,
        "wrong_message_rejection_required": True,
    }:
        errors.append("corrected-wrapper regression contract drifted")
    if (
        record.get("bootstrap_signature_attempt_count") != 1
        or record.get("target_key_generation_attempt_count") != 1
        or record.get("retry_count") != 0
        or record.get("overwrite_allowed") is not False
        or record.get("d095_evidence_mutation_allowed") is not False
        or record.get("p4_k_r_or_later_phase_authorized") is not False
    ):
        errors.append("one-sign/one-key/no-retry/no-later-phase boundary drifted")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "one_corrected_bootstrap_sshsig_authorized",
        "one_create_exclusive_p4_k_v2_action_authorized",
        "public_and_private_metadata_evidence_capture_authorized",
        "repository_local_d096_records_tool_tests_and_evidence_authorized",
    }:
        errors.append("D-096 authority was omitted or widened")
    action_source = (root / "tools/execute_d096_p4_k_a.py").read_text(encoding="utf-8")
    if "options[\"stdin\"]" not in action_source or "options[\"input\"]" not in action_source:
        errors.append("corrected mutually exclusive subprocess-input branches are absent")
    forbidden = (
        "frozen.run_direct",
        "sha256_file(TARGET_PRIVATE)",
        "TARGET_PRIVATE.read_bytes",
        "TARGET_PRIVATE.read_text",
        "shell=True",
        "os.system",
    )
    if any(token in action_source for token in forbidden):
        errors.append("action tool contains a forbidden failed seam, private read, or shell")
    return errors


def external_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected in (
        ("action_python_absolute_path", PYTHON_SHA256),
        ("ssh_keygen_absolute_path", SSH_KEYGEN_SHA256),
    ):
        candidate = pathlib.Path(str(record.get(field, "")))
        if not candidate.is_file() or sha256(candidate) != expected:
            errors.append(f"external tool mismatch: {field}")
    try:
        metadata = os.lstat(BOOTSTRAP_PRIVATE)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_uid != 1000
        ):
            errors.append("bootstrap private metadata mismatch")
    except OSError as exception:
        errors.append(f"bootstrap private metadata unavailable: {exception}")
    if os.path.lexists(D095_PRIVATE):
        errors.append("D-095 target private path unexpectedly exists")
    if os.path.lexists(D096_ROOT):
        errors.append("create-exclusive D-096 target root already exists")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-action-host", action="store_true")
    arguments = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    record_path = root / "config/q15/q15-r-p4-k-a-d096-action-authorization-v1.json"
    schema_path = root / "config/schemas/q15-r-p4-k-a-d096-action-authorization-v1.schema.json"
    record = load(record_path)
    schema = load(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(record)]
    errors.extend(semantic_errors(root, record))
    raw = record_path.read_bytes()
    if raw != canonical(record):
        errors.append("authorization is not canonical JCS-I64-v1 bytes")
    if sha256(record_path) != AUTHORIZATION_SHA256:
        errors.append("authorization SHA-256 mismatch")
    for index, (field, value) in enumerate((
        ("bootstrap_signature_attempt_count", 2),
        ("target_key_generation_attempt_count", 2),
        ("retry_count", 1),
        ("overwrite_allowed", True),
        ("d095_evidence_mutation_allowed", True),
        ("p4_k_r_or_later_phase_authorized", True),
    )):
        mutant = copy.deepcopy(record)
        mutant[field] = value
        if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
            errors.append(f"negative mutation {index} passed")
    mutant = copy.deepcopy(record)
    mutant["authority_boundary"]["stand_access_or_modification_authorized"] = True
    if not list(validator.iter_errors(mutant)) and not semantic_errors(root, mutant):
        errors.append("negative authority mutation passed")
    if arguments.verify_action_host:
        errors.extend(external_errors(record))
    self_test = subprocess.run(
        ["/usr/bin/python3", str(root / "tools/execute_d096_p4_k_a.py"), "--self-test"],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if self_test.returncode != 0 or "SELF-TEST PASS" not in self_test.stdout:
        errors.append("disposable-key corrected-wrapper regression failed")
    if errors:
        for error in errors:
            print(f"d096-authorization-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + action-host metadata" if arguments.verify_action_host else ""
    print(f"d096-authorization-check: PASS (corrected wrapper, 7 negative{suffix}, later authority=NONE)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
