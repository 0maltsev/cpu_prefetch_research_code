#!/usr/bin/env python3
"""Validate D-099 authorization, capture, review, and completion evidence."""

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


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import execute_d099_p4_r_i as executor  # noqa: E402


AUTH_HASH = "def07da593ffa6b90fc9fb14263e426766a84fe738b59fbdc6c2edbc232cc310"
SIGNATURE_HASH = "09a75c98895dfa04974e2b2183a9b235c2aaed13f2e3f0cd34a3b78b58f7ff21"
ARTIFACT_HASH = "774aca6d192a9adaeeb3daf7bc357c61e957c5b2e6169c9db82cf7722cc3dab6"
ARTIFACT_SIDECAR_HASH = "15e6b3579fc2844cc4fdb76f73a68495ddf4fab50928733db62545740257bafc"
REVIEW_HASH = "f01e14303f305210819d633345cf454eb6985e394ab36b30e167491374b3b037"
REVIEW_SIDECAR_HASH = "29fa86edd128552203708314b25d03bee7263fa7f560ea459b54ce1c19a420f1"
MANIFEST_HASH = "72ff382125f19a900ef22cad83011ce5dfb0c91e1c676168fe0b9e472892f3ff"
AUTH_PATH = ROOT / "config/q15/q15-r-p4-r-i-d099-authorization-v1.json"
SIGNATURE_PATH = ROOT / "config/q15/q15-r-p4-r-i-d099-authorization-v1.json.sig"
COMPLETE_PATH = ROOT / "config/q15/q15-r-p4-r-i-d099-complete-evidence-v1.json"
CAPTURE_ROOT = ROOT / "docs/evidence/stage17/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
ARTIFACT_PATH = CAPTURE_ROOT / "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json"
ARTIFACT_SIDECAR_PATH = CAPTURE_ROOT / "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json.sha256"
REVIEW_PATH = CAPTURE_ROOT / "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.owner-review.json"
REVIEW_SIDECAR_PATH = CAPTURE_ROOT / "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.owner-review.json.sha256"
MANIFEST_PATH = CAPTURE_ROOT / "SHA256SUMS"
TARGET_ALLOWED_SIGNERS = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public/target_allowed_signers"
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_errors(record: dict[str, Any], schema_name: str) -> list[str]:
    schema = load(ROOT / "config/schemas" / schema_name)
    Draft202012Validator.check_schema(schema)
    return [item.message for item in Draft202012Validator(schema).iter_errors(record)]


def bound_repository_input_errors(authorization: dict[str, Any]) -> list[str]:
    """Verify every repository-local file whose digest is frozen in D-099."""
    errors: list[str] = []
    for path_field in (
        "d097_complete_evidence_path",
        "decision_adr_path",
        "executor_path",
        "owner_waiver_path",
        "pinned_hosts_path",
        "predecessor_template_path",
        "transport_public_evidence_path",
    ):
        digest_field = path_field.removesuffix("_path") + "_sha256"
        relative = authorization.get(path_field)
        expected = authorization.get(digest_field)
        if not isinstance(relative, str) or not isinstance(expected, str):
            errors.append(f"D-099 bound input is incomplete: {path_field}")
            continue
        path = ROOT / relative
        try:
            if not path.is_file() or sha256(path) != expected:
                errors.append(f"D-099 bound repository input mismatch: {path_field}")
        except OSError as exception:
            errors.append(f"D-099 bound repository input unavailable: {path_field}: {exception}")
    return errors


def semantic_errors(
    authorization: dict[str, Any],
    artifact: dict[str, Any],
    review: dict[str, Any],
    complete: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    expected_enabled = {
        "one_target_sshsig_authorized",
        "four_fixed_read_only_identity_observations_authorized",
        "one_create_exclusive_local_capture_authorized",
        "one_single_owner_public_review_authorized",
        "repository_local_records_tests_and_evidence_authorized",
    }
    enabled = {
        name for name, value in authorization.get("authority_boundary", {}).items() if value is True
    }
    if enabled != expected_enabled:
        errors.append("D-099 authorization omitted or widened authority")
    expected_observations = [
        {"id": identifier, "argv": list(argv)} for identifier, argv in executor.OBSERVATIONS
    ]
    if authorization.get("fixed_read_only_observations") != expected_observations:
        errors.append("D-099 fixed observation vectors drifted")
    try:
        executor.validate_capture(artifact, AUTH_HASH)
        executor.validate_observation_semantics(artifact)
    except executor.IdentityError as exception:
        errors.append(f"identity artifact semantic failure: {exception}")
    if (
        review.get("artifact_sha256") != ARTIFACT_HASH
        or review.get("authorization_sha256") != AUTH_HASH
        or review.get("signature_sha256") != SIGNATURE_HASH
        or review.get("automatic_continuation") is not False
        or review.get("p4_r_c_authorized") is not False
        or review.get("review_attempt") != 1
    ):
        errors.append("owner-review lineage or P4-R-C stop drifted")
    capture = complete.get("capture", {})
    completion_review = complete.get("review", {})
    disposition = complete.get("disposition", {})
    if (
        complete.get("authorization", {}).get("sha256") != AUTH_HASH
        or complete.get("authorization", {}).get("signature_sha256") != SIGNATURE_HASH
        or capture.get("artifact_sha256") != ARTIFACT_HASH
        or capture.get("sidecar_sha256") != ARTIFACT_SIDECAR_HASH
        or capture.get("manifest_sha256") != MANIFEST_HASH
        or completion_review.get("sha256") != REVIEW_HASH
        or completion_review.get("sidecar_sha256") != REVIEW_SIDECAR_HASH
        or disposition.get("automatic_continuation") is not False
        or disposition.get("p4_r_c_issued_or_executed") is not False
    ):
        errors.append("complete-evidence lineage or mandatory stop drifted")
    return errors


def external_errors() -> list[str]:
    errors: list[str] = []
    for path, expected in (
        (TARGET_ALLOWED_SIGNERS, "b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718"),
        (pathlib.Path("/home/omaltsev/.ssh/id_ed25519.pub"), "b46d49976a60f4a578282ff4d2061e7d58640eb74993c3f5333fa609792d488a"),
        (pathlib.Path("/usr/bin/ssh"), "e3bc4b0d2382755b4dd398101c9c00ab20df91c2e565b017f0c8f033004391f2"),
        (pathlib.Path("/usr/bin/ssh-keygen"), "f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11"),
    ):
        try:
            if not path.is_file() or sha256(path) != expected:
                errors.append(f"external public/tool evidence mismatch: {path}")
        except OSError as exception:
            errors.append(f"external public/tool evidence unavailable: {path}: {exception}")
    private_path = pathlib.Path("/home/omaltsev/.ssh/id_ed25519")
    try:
        metadata = os.lstat(private_path)
        if not private_path.is_file() or (metadata.st_mode & 0o777) != 0o600:
            errors.append("transport private-key metadata mismatch")
    except OSError as exception:
        errors.append(f"transport private-key metadata unavailable: {exception}")
    verification = subprocess.run(
        [
            "/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(TARGET_ALLOWED_SIGNERS),
            "-I", "cpu-prefetch-q15-authorization", "-n", "cpu-prefetch-q15-authorization",
            "-s", str(SIGNATURE_PATH),
        ],
        check=False,
        input=AUTH_PATH.read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if verification.returncode != 0:
        errors.append("D-099 target SSHSIG verification failed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-external", action="store_true")
    arguments = parser.parse_args()
    files = (
        (AUTH_PATH, AUTH_HASH),
        (SIGNATURE_PATH, SIGNATURE_HASH),
        (ARTIFACT_PATH, ARTIFACT_HASH),
        (ARTIFACT_SIDECAR_PATH, ARTIFACT_SIDECAR_HASH),
        (REVIEW_PATH, REVIEW_HASH),
        (REVIEW_SIDECAR_PATH, REVIEW_SIDECAR_HASH),
        (MANIFEST_PATH, MANIFEST_HASH),
    )
    errors: list[str] = []
    for path, expected in files:
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"immutable D-099 file mismatch: {path}")
    authorization = load(AUTH_PATH)
    artifact = load(ARTIFACT_PATH)
    review = load(REVIEW_PATH)
    complete = load(COMPLETE_PATH)
    for record, schema_name in (
        (authorization, "q15-r-p4-r-i-d099-authorization-v1.schema.json"),
        (artifact, "q15-r-p4-r-i-d099-identity-v1.schema.json"),
        (review, "q15-r-p4-r-i-d099-owner-review-v1.schema.json"),
        (complete, "q15-r-p4-r-i-d099-complete-evidence-v1.schema.json"),
    ):
        errors.extend(schema_errors(record, schema_name))
    for path, record in ((AUTH_PATH, authorization), (ARTIFACT_PATH, artifact), (REVIEW_PATH, review)):
        if path.read_bytes() != canonical(record):
            errors.append(f"artifact is not canonical: {path.name}")
    errors.extend(bound_repository_input_errors(authorization))
    errors.extend(semantic_errors(authorization, artifact, review, complete))
    expected_artifact_sidecar = f"{ARTIFACT_HASH}  {ARTIFACT_PATH.name}\n"
    expected_review_sidecar = f"{REVIEW_HASH}  {REVIEW_PATH.name}\n"
    if ARTIFACT_SIDECAR_PATH.read_text(encoding="ascii") != expected_artifact_sidecar:
        errors.append("identity sidecar bytes mismatch")
    if REVIEW_SIDECAR_PATH.read_text(encoding="ascii") != expected_review_sidecar:
        errors.append("review sidecar bytes mismatch")
    expected_manifest = "".join(
        f"{sha256(path)}  {path.name}\n"
        for path in (ARTIFACT_PATH, ARTIFACT_SIDECAR_PATH, REVIEW_PATH, REVIEW_SIDECAR_PATH)
    )
    if MANIFEST_PATH.read_text(encoding="ascii") != expected_manifest:
        errors.append("D-099 SHA256SUMS bytes mismatch")
    if (CAPTURE_ROOT / "identity-failure.json").exists():
        errors.append("successful D-099 transaction contains a failure receipt")
    source = (ROOT / "tools/execute_d099_p4_r_i.py").read_text(encoding="utf-8")
    for forbidden in (
        "shell=True", "os.system", "sshpass", "StrictHostKeyChecking=no",
        "PasswordAuthentication=yes", "KbdInteractiveAuthentication=yes",
        "p4-k-v2/id_ed25519",
    ):
        if forbidden in source:
            errors.append(f"D-099 executor contains forbidden token: {forbidden}")
    mutants: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for section, field, value in (
        ("authorization", "retry_count", 1),
        ("authorization", "automatic_continuation", True),
        ("identity", "stand_filesystem_mutation_performed", True),
        ("review", "p4_r_c_authorized", True),
        ("complete_disposition", "automatic_continuation", True),
        ("complete_authority", "p4_r_c_authorized", True),
    ):
        mutated = (copy.deepcopy(authorization), copy.deepcopy(artifact), copy.deepcopy(review), copy.deepcopy(complete))
        if section == "authorization":
            mutated[0][field] = value
        elif section == "identity":
            mutated[1][field] = value
        elif section == "review":
            mutated[2][field] = value
        elif section == "complete_disposition":
            mutated[3]["disposition"][field] = value
        else:
            mutated[3]["authority_boundary"][field] = value
        mutants.append(mutated)
    reordered = (copy.deepcopy(authorization), copy.deepcopy(artifact), copy.deepcopy(review), copy.deepcopy(complete))
    reordered[1]["observations"].reverse()
    mutants.append(reordered)
    corrupted = (copy.deepcopy(authorization), copy.deepcopy(artifact), copy.deepcopy(review), copy.deepcopy(complete))
    corrupted[1]["observations"][0]["stdout_sha256"] = "0" * 64
    mutants.append(corrupted)
    schemas = (
        "q15-r-p4-r-i-d099-authorization-v1.schema.json",
        "q15-r-p4-r-i-d099-identity-v1.schema.json",
        "q15-r-p4-r-i-d099-owner-review-v1.schema.json",
        "q15-r-p4-r-i-d099-complete-evidence-v1.schema.json",
    )
    for index, mutant in enumerate(mutants):
        mutation_errors: list[str] = []
        for record, schema_name in zip(mutant, schemas, strict=True):
            mutation_errors.extend(schema_errors(record, schema_name))
        mutation_errors.extend(semantic_errors(*mutant))
        if not mutation_errors:
            errors.append(f"negative mutation {index} passed")
    if arguments.verify_external:
        errors.extend(external_errors())
    if errors:
        for error in errors:
            print(f"d099-p4-r-i-complete-check: FAIL: {error}", file=sys.stderr)
        return 1
    suffix = " + external public/tool/signature evidence" if arguments.verify_external else ""
    print(
        "d099-p4-r-i-complete-check: PASS "
        f"(4 observations, 8 negative{suffix}, P4-R-C/later authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
