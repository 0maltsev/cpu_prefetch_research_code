#!/usr/bin/env python3
"""Verify accepted D-100..D-103 implementation without keys or stand access."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import execute_d104_p4_r_c as executor  # noqa: E402


ACCEPTANCE = ROOT / "config/q15/q15-r-p4-r-c-d100-acceptance-v1.json"
PREPARATION = ROOT / "config/q15/q15-r-p4-r-c-d104-preparation-v1.json"
TEMPLATE = ROOT / "config/q15/q15-r-p4-r-c-d104-action-authorization-template-v1.json"
HISTORICAL_D104_REVISION = "dc643df498fa36c3c34507f977634c05421751b1"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def historical_d104_executor() -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{HISTORICAL_D104_REVISION}:tools/execute_d104_p4_r_c.py"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("historical D-104 executor Git object is unavailable")
    return completed.stdout


def validate(document: pathlib.Path, schema_name: str) -> list[str]:
    record = load(document)
    schema = load(ROOT / "config/schemas" / schema_name)
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(record)]


def schema_mutations() -> list[str]:
    errors: list[str] = []
    preparation = load(PREPARATION)
    schema = load(ROOT / "config/schemas/q15-r-p4-r-c-d104-preparation-v1.schema.json")
    mutants = []
    for field in (
        "target_private_key_use_authorized",
        "stand_access_authorized",
        "p4_r_c_or_later_authorized",
        "calibration_pilot_measurement_or_confirmatory_authorized",
    ):
        mutant = copy.deepcopy(preparation)
        mutant["authority_boundary"][field] = True
        mutants.append(mutant)
    resolved = copy.deepcopy(preparation)
    resolved["unresolved_action_inputs"]["exact_action_owner_approval"] = "fabricated"
    mutants.append(resolved)
    runtime = copy.deepcopy(preparation)
    runtime["status"] = "READY_FOR_ACTION"
    mutants.append(runtime)
    validator = Draft202012Validator(schema)
    for index, mutant in enumerate(mutants):
        if not list(validator.iter_errors(mutant)):
            errors.append(f"preparation negative mutation {index} passed")
    return errors


def evidence_schema_tests() -> list[str]:
    errors: list[str] = []

    def check(record: dict[str, Any], schema_name: str, label: str) -> None:
        schema = load(ROOT / "config/schemas" / schema_name)
        found = list(Draft202012Validator(schema).iter_errors(record))
        if found:
            errors.append(f"synthetic {label} failed schema: {found[0].message}")

    authorization_hash = "a" * 64
    with tempfile.TemporaryDirectory(prefix="d104-schema-test-") as directory:
        root = pathlib.Path(directory)
        outputs = executor.OutputPaths(
            root / "artifact.json",
            root / "artifact.stderr.bin",
            root / "artifact.json.sha256",
            root / "receipt.json",
            root / "review.json",
            root / "failure.json",
        )
        executor.emit_success(
            authorization_hash,
            executor.synthetic_collector_artifact(authorization_hash),
            b"",
            [f"P4RC-{index:03d}" for index in range(1, 12)],
            outputs,
        )
        check(
            load(outputs.receipt),
            "q15-r-p4-r-c-d104-transfer-receipt-v1.schema.json",
            "receipt",
        )
    with tempfile.TemporaryDirectory(prefix="d104-failure-schema-test-") as directory:
        root = pathlib.Path(directory)
        outputs = executor.OutputPaths(
            root / "artifact.json",
            root / "artifact.stderr.bin",
            root / "artifact.json.sha256",
            root / "receipt.json",
            root / "review.json",
            root / "failure.json",
        )
        executor.retain_failure(
            authorization_hash,
            "P4RC-004-ARCHIVE",
            "synthetic",
            ["P4RC-001", "P4RC-002", "P4RC-003"],
            b"partial",
            b"injected",
            outputs,
        )
        check(
            load(outputs.failure),
            "q15-r-p4-r-c-d104-failure-v1.schema.json",
            "failure",
        )
    pre_review = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-pre-execution-review/1",
        "status": "ACCEPTED_SINGLE_OWNER_PRE_EXECUTION_REVIEW",
        "authorization_sha256": authorization_hash,
        "signature_sha256": "b" * 64,
        "review_principal": "cpu-prefetch-q15-auditor",
        "distinct_reviewer": False,
        "single_owner_waiver": True,
        "all_bound_inputs_verified": True,
        "p4_r_c_action_authorized": True,
        "review_attempt": 1,
        "reviewed_at_utc": "2026-08-26T00:01:00Z",
        "automatic_continuation": False,
    }
    check(
        pre_review,
        "q15-r-p4-r-c-d104-pre-execution-review-v1.schema.json",
        "pre-execution review",
    )
    owner_review = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-owner-review/1",
        "transaction_id": "Q15-R-P4-R-C-D104-XEON-CPU-FETCH-20260826-01",
        "authorization_sha256": authorization_hash,
        "transfer_receipt_sha256": "c" * 64,
        "collector_stdout_sha256": "d" * 64,
        "status": "ACCEPTED_SINGLE_OWNER_PUBLIC_REVIEW_STOPPED_BEFORE_P5",
        "review_principal": "cpu-prefetch-q15-auditor",
        "distinct_reviewer": False,
        "single_owner_waiver": True,
        "review_attempt": 1,
        "p5_or_later_authorized": False,
        "automatic_continuation": False,
        "reviewed_at_utc": "2026-08-26T00:02:00Z",
    }
    check(owner_review, "q15-r-p4-r-c-d104-owner-review-v1.schema.json", "owner review")
    return errors


def main() -> int:
    errors: list[str] = []
    acceptance = load(ACCEPTANCE)
    preparation = load(PREPARATION)
    template = load(TEMPLATE)
    expected_selections = {
        "D-100": "ACCEPT_SINGLE_OWNER_OPERATOR_CUSTODIAN_AUDITOR_COLLAPSE_FOR_ONE_P4_R_C",
        "D-101": "ALLOW_ONLY_THE_EXACT_VERIFIED_D099_CUSTODY_ROOT_AND_REQUIRE_EVERY_P4_R_C_OUTPUT_TO_BE_ABSENT_AND_CREATE_EXCLUSIVE",
        "D-102": "ACCEPT_ONLY_PRECOMPUTED_HASH_BOUND_CONSTANT_REMOTE_COMMAND_STRINGS_WITH_LOCAL_SHELL_FALSE_NO_USER_INTERPOLATION_AND_STRICT_TOKEN_VALIDATION",
        "D-103": "AUTHORIZE_CREATE_EXCLUSIVE_MODE_0700_NAMESPACE_PARENT_IF_ABSENT_AND_REQUIRE_EXACT_ROOT_OWNED_NONSYMLINK_STATE_IF_PRESENT",
    }
    if acceptance.get("accepted_selections") != expected_selections:
        errors.append("D-100 through D-103 accepted selections drifted")
    if sha256(ACCEPTANCE) != "bdfe690a15b80c85d9fdf747a2036d48c1d8f56a8f2856dfc7e1d7b597c4a65f":
        errors.append("D-100 acceptance bytes drifted")
    errors.extend(validate(ACCEPTANCE, "q15-r-p4-r-c-d100-acceptance-v1.schema.json"))
    errors.extend(validate(PREPARATION, "q15-r-p4-r-c-d104-preparation-v1.schema.json"))
    errors.extend(
        validate(
            TEMPLATE,
            "q15-r-p4-r-c-d104-action-authorization-template-v1.schema.json",
        )
    )
    schema_names = (
        "q15-r-p4-r-c-d104-action-authorization-v1.schema.json",
        "q15-r-p4-r-c-d104-pre-execution-review-v1.schema.json",
        "q15-r-p4-r-c-d104-transfer-receipt-v1.schema.json",
        "q15-r-p4-r-c-d104-failure-v1.schema.json",
        "q15-r-p4-r-c-d104-owner-review-v1.schema.json",
    )
    for name in schema_names:
        try:
            Draft202012Validator.check_schema(load(ROOT / "config/schemas" / name))
        except Exception as exception:  # noqa: BLE001 - report every schema defect.
            errors.append(f"invalid D-104 schema {name}: {exception}")
    try:
        historical_executor_sha256 = hashlib.sha256(historical_d104_executor()).hexdigest()
    except RuntimeError as exception:
        errors.append(str(exception))
    else:
        if preparation.get("executor_sha256") != historical_executor_sha256:
            errors.append("D-104 preparation does not bind its historical executor bytes")
    unresolved = preparation.get("unresolved_action_inputs", {})
    if len(unresolved) != 8 or any(value is not None for value in unresolved.values()):
        errors.append("D-104 preparation fabricated an external/action input")
    if executor.REMOTE_RUNTIME_ACCEPTANCE_SHA256 is not None:
        errors.append("executor fabricated remote Python/dd/tar compatibility acceptance")
    if template.get("status") != (
        "STILL_UNISSUED_REQUIRES_CLEAN_COMMIT_SIGNATURE_REVIEW_AND_EXACT_APPROVAL"
    ):
        errors.append("D-104 authorization template was issued")
    for field in (
        "clean_implementation_commit",
        "executor_sha256",
        "issued_at_utc",
        "expires_at_utc",
        "authorization_sha256",
        "detached_signature_sha256",
        "pre_execution_review_sha256",
        "action_owner_approval",
    ):
        if template.get(field) is not None:
            errors.append(f"D-104 authorization template fabricated {field}")
    for forbidden in (
        "q15-r-p4-r-c-d104-action-authorization-v1.json",
        "q15-r-p4-r-c-d104-action-authorization-v1.json.sig",
        "q15-r-p4-r-c-d104-pre-execution-review-v1.json",
    ):
        if (ROOT / "config/q15" / forbidden).exists():
            errors.append(f"still-unissued D-104 action artifact exists: {forbidden}")
    source = (ROOT / "tools/execute_d104_p4_r_c.py").read_text(encoding="utf-8")
    for required in (
        "shell=False",
        "O_EXCL",
        "StrictHostKeyChecking=yes",
        "ConnectionAttempts=1",
        "REMOTE_RUNTIME_ACCEPTANCE_SHA256: str | None = None",
        "SEPARATE_SINGLE_OWNER_RESULT_REVIEW_AND_STOP_BEFORE_P5",
    ):
        if required not in source:
            errors.append(f"executor source omits fixed boundary: {required}")
    for forbidden in (
        "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/id_ed25519",
        "shell=True",
        "os.system(",
        "requests.",
        "paramiko",
    ):
        if forbidden in source:
            errors.append(f"executor source contains forbidden capability: {forbidden}")
    try:
        executor.ssh_argv("/bin/sh -c id")
    except executor.ActionError:
        pass
    else:
        errors.append("executor accepted an unregistered remote shell command")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools/execute_d104_p4_r_c.py"), "--self-test"],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        shell=False,
    )
    if result.returncode != 0 or "SELF-TEST PASS" not in result.stdout:
        errors.append("D-104 executor self-test failed")
    with tempfile.TemporaryDirectory(prefix="d104-blocked-action-test-") as directory:
        root = pathlib.Path(directory)
        authorization = root / "authorization.json"
        authorization.write_bytes(
            executor.canonical(
                {
                    "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-action-authorization/1",
                    "status": "AUTHORIZED_ONE_P4_R_C_ACTION",
                }
            )
        )
        blocked = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/execute_d104_p4_r_c.py"),
                "--execute",
                "--authorization",
                str(authorization),
                "--authorization-sha256",
                sha256(authorization),
                "--signature",
                str(root / "absent.sig"),
                "--signature-sha256",
                "b" * 64,
                "--pre-execution-review",
                str(root / "absent-review.json"),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            shell=False,
        )
        if blocked.returncode == 0 or "remote Python/dd/tar runtime compatibility remains unresolved" not in blocked.stderr:
            errors.append("D-104 action path did not stop at the unresolved runtime gate")
    errors.extend(schema_mutations())
    errors.extend(evidence_schema_tests())
    if errors:
        for error in errors:
            print(f"d104-p4-r-c-implementation-check: FAIL: {error}", file=sys.stderr)
        return 1
    print(
        "d104-p4-r-c-implementation-check: PASS "
        "(accepted D-100..D-103; 13-step fake graph; 6 schema negatives; "
        "action/stand/key authority=NONE; remote-runtime gate=BLOCKED)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
