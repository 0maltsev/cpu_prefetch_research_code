#!/usr/bin/env python3
"""Execute the one bootstrap-signed D-095 P4-K-A action."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any


DECISION_ID = "D-095"
TRANSACTION_ID = "Q15-R-P4-K-A-D095-20260825-01"
OWNER_PRINCIPAL = "cpu-prefetch-bootstrap-owner"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
SIGNATURE_NAMESPACE = "cpu-prefetch-q15-authorization"
BOOTSTRAP_FINGERPRINT = "SHA256:JuRM4SuWL9C1xvOes9z+CAKZV1rvel27VZ/+qiuVNs0"
BOOTSTRAP_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519"
)
BOOTSTRAP_PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public"
)
TARGET_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/id_ed25519"
)
TARGET_PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/public"
)
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
ACTION_PYTHON = pathlib.Path("/usr/bin/python3")
TARGET_KEY_COMMENT = "cpu-prefetch-q15-p4-k-v1"
ACTIVE_LIFECYCLE_SHA256 = (
    "75f9724160e6a6868014a699eb4608dfbfdd37da4ef952f977a31b79d70619ae"
)
BOOTSTRAP_ALLOWED_SIGNERS_SHA256 = (
    "6c21b0d631a3842e182bd92e0856aa5073c949f5c5a6b4a8e85b48dd2016f33d"
)
PUBLIC_NAMES_BEFORE_RECEIPT = (
    "action_authorization.json",
    "action_authorization.json.sig",
    "bootstrap_signature_verification.json",
    "owner_pre_action_review.json",
    "target_allowed_signers",
    "target_fingerprint.txt",
    "target_public_key.pub",
)


class D095Error(RuntimeError):
    """A fail-closed D-095 preflight or action failure."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_exclusive(path: pathlib.Path, value: bytes, mode: int = 0o644) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, mode)
    try:
        view = memoryview(value)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise D095Error("exclusive public write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def fsync_directory(path: pathlib.Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require_private_metadata(path: pathlib.Path) -> os.stat_result:
    metadata = os.lstat(path)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_uid != 1000
    ):
        raise D095Error("private-key metadata differs from the exact contract")
    return metadata


def reject_symlinked_existing_components(path: pathlib.Path) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            continue
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise D095Error("an existing output-path component is not a real directory")


def create_parent_directories(path: pathlib.Path) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if os.path.lexists(current):
            metadata = os.lstat(current)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise D095Error("an output parent is not a real directory")
            continue
        os.mkdir(current, 0o700)


def parse_public_key_line(value: str) -> tuple[str, str]:
    tokens = value.strip().split()
    if len(tokens) != 3 or tokens[0] != "ssh-ed25519" or tokens[2] != TARGET_KEY_COMMENT:
        raise D095Error("target public-key shape differs from the D-095 contract")
    try:
        decoded = base64.b64decode(tokens[1], validate=True)
    except ValueError as exception:
        raise D095Error("target public-key payload is not canonical base64") from exception
    if not decoded:
        raise D095Error("target public-key payload is empty")
    return tokens[0], tokens[1]


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise D095Error("authorization UTC value is not an exact whole-second UTC instant")
    return parsed


def run_direct(
    argv: list[str], *, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        check=False,
        stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )


def exact_authorization_errors(record: dict[str, Any]) -> list[str]:
    expected = {
        "schema_version": "cpu-prefetch-q15-r-p4-k-a-d095-action-authorization/1",
        "authorization_id": "Q15-R-P4-K-A-D095-AUTHORIZATION-20260825-01",
        "protocol_version": "2.0.0-pre.2",
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "AUTHORIZED_ONE_BOOTSTRAP_SIGNATURE_AND_ONE_P4_K_A_ACTION",
        "source_commit": "22b8b1b1695a1548b51cfac1cd9870f7c7fcd3ab",
        "owner_principal": OWNER_PRINCIPAL,
        "bootstrap_fingerprint": BOOTSTRAP_FINGERPRINT,
        "bootstrap_private_key_absolute_path": str(BOOTSTRAP_PRIVATE),
        "target_private_key_absolute_path": str(TARGET_PRIVATE),
        "target_public_root_absolute_path": str(TARGET_PUBLIC_ROOT),
        "private_key_encrypted": False,
        "independent_recovery_required": False,
        "distinct_auditor_required": False,
        "development_host_allowed": True,
        "bootstrap_signature_attempt_count": 1,
        "target_key_generation_attempt_count": 1,
        "retry_count": 0,
        "overwrite_allowed": False,
        "p4_k_r_or_later_phase_authorized": False,
    }
    return [
        f"authorization field mismatch: {name}"
        for name, expected_value in expected.items()
        if record.get(name) != expected_value
    ]


def load_and_verify_authorization(
    path: pathlib.Path, expected_sha256: str
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise D095Error("canonical action-authorization SHA-256 mismatch")
    record = json.loads(raw)
    if raw != canonical_json(record):
        raise D095Error("action authorization is not exact JCS-I64-v1 bytes")
    errors = exact_authorization_errors(record)
    if record.get("action_tool_sha256") != sha256_file(pathlib.Path(__file__)):
        errors.append("action-tool SHA-256 mismatch")
    if record.get("ssh_keygen_sha256") != sha256_file(SSH_KEYGEN):
        errors.append("ssh-keygen SHA-256 mismatch")
    if record.get("action_python_sha256") != sha256_file(ACTION_PYTHON):
        errors.append("action Python SHA-256 mismatch")
    if pathlib.Path(sys.executable).resolve() != ACTION_PYTHON.resolve():
        errors.append("action is running under an unbound Python interpreter")
    if record.get("active_lifecycle_state_sha256") != ACTIVE_LIFECYCLE_SHA256:
        errors.append("active bootstrap lifecycle identity mismatch")
    issued = parse_utc(str(record.get("issued_at_utc", "")))
    expires = parse_utc(str(record.get("expires_at_utc", "")))
    if int((expires - issued).total_seconds()) != 1800:
        errors.append("authorization window is not exactly 1,800 seconds")
    now = datetime.now(UTC).replace(microsecond=0)
    if now < issued or now >= expires:
        errors.append("authorization is outside its nonrenewable UTC window")
    if errors:
        raise D095Error("; ".join(errors))
    return record, raw


def public_artifact(path: pathlib.Path) -> dict[str, Any]:
    return {"filename": path.name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size}


def retain_failure(phase: str, authorization_sha256: str) -> None:
    if not TARGET_PUBLIC_ROOT.is_dir():
        return
    failure_path = TARGET_PUBLIC_ROOT / "failure_receipt.json"
    if os.path.lexists(failure_path):
        return
    failure = {
        "schema_version": "cpu-prefetch-q15-r-p4-k-a-d095-failure/1",
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
        "phase": phase,
        "authorization_sha256": authorization_sha256,
        "automatic_continuation": False,
    }
    write_exclusive(failure_path, canonical_json(failure))
    fsync_directory(TARGET_PUBLIC_ROOT)


def execute(authorization_path: pathlib.Path, authorization_sha256: str) -> int:
    phase = "PREFLIGHT"
    try:
        authorization, authorization_bytes = load_and_verify_authorization(
            authorization_path, authorization_sha256
        )
        require_private_metadata(BOOTSTRAP_PRIVATE)
        allowed_signers = BOOTSTRAP_PUBLIC_ROOT / "allowed_signers"
        if sha256_file(allowed_signers) != BOOTSTRAP_ALLOWED_SIGNERS_SHA256:
            raise D095Error("bootstrap allowed-signers SHA-256 mismatch")
        if os.path.lexists(TARGET_PRIVATE.parent):
            raise D095Error("create-exclusive P4-K-A transaction already exists")
        reject_symlinked_existing_components(TARGET_PRIVATE.parent.parent)
        create_parent_directories(TARGET_PRIVATE.parent.parent)
        os.mkdir(TARGET_PRIVATE.parent, 0o700)
        os.mkdir(TARGET_PUBLIC_ROOT, 0o700)
        fsync_directory(TARGET_PRIVATE.parent.parent)

        phase = "WRITE_AUTHORIZATION_AND_OWNER_REVIEW"
        action_copy = TARGET_PUBLIC_ROOT / "action_authorization.json"
        write_exclusive(action_copy, authorization_bytes)
        review = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d095-owner-review/1",
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "ACCEPTED_SINGLE_OWNER_REVIEW_WAIVER_APPLIED",
            "owner_principal": OWNER_PRINCIPAL,
            "authorization_sha256": authorization_sha256,
            "reviewed_at_utc": authorization["issued_at_utc"],
            "distinct_auditor_exists": False,
            "critical_role_collapse_and_misuse_risks_accepted": True,
            "action_authorized": True,
            "p4_k_r_or_later_authorized": False,
        }
        review_path = TARGET_PUBLIC_ROOT / "owner_pre_action_review.json"
        write_exclusive(review_path, canonical_json(review))

        phase = "BOOTSTRAP_SSHSIG_SIGN"
        sign_result = run_direct([
            str(SSH_KEYGEN), "-Y", "sign", "-f", str(BOOTSTRAP_PRIVATE),
            "-n", SIGNATURE_NAMESPACE, "-O", "hashalg=sha512", str(action_copy),
        ])
        signature_path = pathlib.Path(f"{action_copy}.sig")
        if sign_result.returncode != 0 or not signature_path.is_file():
            raise D095Error("bootstrap SSHSIG creation failed; retry forbidden")

        phase = "BOOTSTRAP_SSHSIG_VERIFY"
        verify_result = run_direct([
            str(SSH_KEYGEN), "-Y", "verify", "-f", str(allowed_signers),
            "-I", AUTHORIZATION_PRINCIPAL, "-n", SIGNATURE_NAMESPACE,
            "-s", str(signature_path),
        ], input_bytes=authorization_bytes)
        if verify_result.returncode != 0:
            raise D095Error("bootstrap SSHSIG verification failed; action stopped")
        verification = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d095-bootstrap-verification/1",
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "PASS",
            "authorization_sha256": authorization_sha256,
            "signature_sha256": sha256_file(signature_path),
            "bootstrap_fingerprint": BOOTSTRAP_FINGERPRINT,
            "allowed_signers_sha256": BOOTSTRAP_ALLOWED_SIGNERS_SHA256,
            "principal": AUTHORIZATION_PRINCIPAL,
            "namespace": SIGNATURE_NAMESPACE,
            "hash_algorithm": "sha512",
        }
        verification_path = TARGET_PUBLIC_ROOT / "bootstrap_signature_verification.json"
        write_exclusive(verification_path, canonical_json(verification))

        phase = "TARGET_SSH_KEYGEN"
        keygen_result = run_direct([
            str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C",
            TARGET_KEY_COMMENT, "-f", str(TARGET_PRIVATE),
        ])
        generated_public = pathlib.Path(f"{TARGET_PRIVATE}.pub")
        if keygen_result.returncode != 0 or not TARGET_PRIVATE.is_file() or not generated_public.is_file():
            raise D095Error("target ssh-keygen failed; partial retained and retry forbidden")
        os.chmod(TARGET_PRIVATE, 0o600)

        phase = "TARGET_PUBLIC_EVIDENCE"
        public_line = generated_public.read_text(encoding="utf-8")
        key_type, public_payload = parse_public_key_line(public_line)
        target_public_path = TARGET_PUBLIC_ROOT / "target_public_key.pub"
        os.rename(generated_public, target_public_path)
        os.chmod(target_public_path, 0o644)
        write_exclusive(
            TARGET_PUBLIC_ROOT / "target_allowed_signers",
            f"{AUTHORIZATION_PRINCIPAL} {key_type} {public_payload}\n".encode(),
        )
        fingerprint_result = run_direct([
            str(SSH_KEYGEN), "-l", "-f", str(target_public_path), "-E", "sha256",
        ])
        fingerprint_tokens = fingerprint_result.stdout.decode().strip().split()
        if (
            fingerprint_result.returncode != 0 or len(fingerprint_tokens) < 4
            or fingerprint_tokens[0] != "256"
            or not fingerprint_tokens[1].startswith("SHA256:")
            or fingerprint_tokens[-1] != "(ED25519)"
        ):
            raise D095Error("target fingerprint derivation failed closed")
        target_fingerprint = fingerprint_tokens[1]
        write_exclusive(TARGET_PUBLIC_ROOT / "target_fingerprint.txt", f"{target_fingerprint}\n".encode())

        phase = "SEAL_EVIDENCE"
        private_metadata = require_private_metadata(TARGET_PRIVATE)
        initial_paths = [TARGET_PUBLIC_ROOT / name for name in PUBLIC_NAMES_BEFORE_RECEIPT]
        receipt = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d095-action-receipt/1",
            "protocol_version": authorization["protocol_version"],
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "COMPLETE_VALID_BOOTSTRAP_SIGNATURE_TARGET_KEY_CREATED_STOPPED_FOR_P4_K_R",
            "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "authorization_sha256": authorization_sha256,
            "bootstrap_signature_sha256": sha256_file(signature_path),
            "bootstrap_fingerprint": BOOTSTRAP_FINGERPRINT,
            "owner_review_sha256": sha256_file(review_path),
            "bootstrap_verification_sha256": sha256_file(verification_path),
            "target_fingerprint": target_fingerprint,
            "target_private_key_absolute_path": str(TARGET_PRIVATE),
            "target_private_key_mode_octal": "0600",
            "target_private_key_size_bytes_observed_without_content_read": private_metadata.st_size,
            "target_private_key_content_read_or_hashed_by_action_tool": False,
            "target_private_key_encrypted": False,
            "independent_recovery_exists": False,
            "public_artifacts_before_receipt": [public_artifact(path) for path in initial_paths],
            "automatic_continuation": False,
            "next_gate": "SEPARATE_P4_K_R_REVIEW_AUTHORIZATION_REQUIRED",
        }
        receipt_path = TARGET_PUBLIC_ROOT / "action_receipt.json"
        write_exclusive(receipt_path, canonical_json(receipt))
        checksum_paths = initial_paths + [receipt_path]
        checksum_lines = "".join(
            f"{sha256_file(path)}  {path.name}\n" for path in sorted(checksum_paths)
        )
        write_exclusive(TARGET_PUBLIC_ROOT / "SHA256SUMS", checksum_lines.encode())
        fsync_directory(TARGET_PUBLIC_ROOT)
        fsync_directory(TARGET_PRIVATE.parent)
        print(json.dumps({
            "status": receipt["status"], "transaction_id": TRANSACTION_ID,
            "authorization_sha256": authorization_sha256,
            "bootstrap_signature_sha256": receipt["bootstrap_signature_sha256"],
            "target_fingerprint": target_fingerprint,
            "target_public_root": str(TARGET_PUBLIC_ROOT),
            "target_private_key_created": True, "target_private_key_emitted": False,
            "automatic_continuation": False,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except (D095Error, OSError, ValueError, json.JSONDecodeError) as exception:
        try:
            retain_failure(phase, authorization_sha256)
        except OSError:
            pass
        raise D095Error(f"{phase}: {exception}") from exception


def self_test() -> int:
    fixture = {"ascii": "D-095", "integer": 1800, "nested": {"false": False, "null": None, "true": True}}
    expected = b'{"ascii":"D-095","integer":1800,"nested":{"false":false,"null":null,"true":true}}\n'
    if canonical_json(fixture) != expected:
        raise D095Error("self-test canonicalization failed")
    payload = base64.b64encode(b"non-secret-d095-fixture").decode()
    key_type, parsed = parse_public_key_line(f"ssh-ed25519 {payload} {TARGET_KEY_COMMENT}\n")
    if key_type != "ssh-ed25519" or parsed != payload:
        raise D095Error("self-test target public-key parsing failed")
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "exclusive"
        write_exclusive(path, b"public fixture\n")
        try:
            write_exclusive(path, b"overwrite\n")
        except FileExistsError:
            pass
        else:
            raise D095Error("self-test overwrite mutation passed")
    print("execute-d095-p4-k-a: SELF-TEST PASS (no signing or key generated)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=pathlib.Path)
    parser.add_argument("--authorization-sha256")
    arguments = parser.parse_args()
    try:
        if arguments.self_test:
            if arguments.authorization_record or arguments.authorization_sha256:
                raise D095Error("self-test accepts no authorization arguments")
            return self_test()
        if not arguments.authorization_record or not arguments.authorization_sha256:
            raise D095Error("execute requires exact authorization path and SHA-256")
        return execute(arguments.authorization_record, arguments.authorization_sha256)
    except D095Error as exception:
        print(f"execute-d095-p4-k-a: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
