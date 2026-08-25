#!/usr/bin/env python3
"""Execute one public-only D-097 P4-K-R review and stop before P5."""

from __future__ import annotations

import argparse
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


DECISION_ID = "D-097"
TRANSACTION_ID = "Q15-R-P4-K-R-D097-20260826-01"
REVIEW_PRINCIPAL = "cpu-prefetch-bootstrap-owner"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
SIGNATURE_NAMESPACE = "cpu-prefetch-q15-authorization"
TARGET_FINGERPRINT = "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM"
PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public"
)
REVIEW_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/review-v1"
)
BOOTSTRAP_ALLOWED_SIGNERS = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public/allowed_signers"
)
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
EXPECTED_PUBLIC = {
    "SHA256SUMS": "1bf9a96ce92c25369730ef97b69acf1cef8f37eef69b21dd53d50d3cb08d3489",
    "action_authorization.json": "8feb2ccffcd565ca9b202c8da736fe9f62e3869cb08e68ef87e38af6439be761",
    "action_authorization.json.sig": "2514a67103b4850889653efd0c38b75d5669e7da97870d2c1ff1ccb6a16d7e0c",
    "action_receipt.json": "36db7093c7e8854c6307707883e856864ff58db0c48d69ee89a89f917e92f4d0",
    "bootstrap_signature_verification.json": "f4a5ed840e005622b56482300221405f160618d99b76b08bdb8aced243b83cec",
    "owner_pre_action_review.json": "ea6c9a9a829becdd287f83e1600142fc874368287355512ab94c8e591db52724",
    "target_allowed_signers": "b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718",
    "target_fingerprint.txt": "9c0da30e9f634b01eab451dd2e129f246ff7c0783bac8aa323cbc18392cbbba0",
    "target_public_key.pub": "41cf7aab4c512c38dc0c3f802fdc0e3265cb3327828b5d3bcc0ba2cacf273b21",
}
D095_EVIDENCE = "ccfe61af14b8aca872a9fd0f4ab4371fb3e74cf445846c8b1a8b30e660f2fa2d"
D096_EVIDENCE = "8c30c1fb941179f0498943fd6ac34264ba185a318661513802fd1b2e29dfa4c8"
BOOTSTRAP_TRUST = "6c21b0d631a3842e182bd92e0856aa5073c949f5c5a6b4a8e85b48dd2016f33d"


class ReviewError(RuntimeError):
    """Fail-closed review-contract violation."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def require_regular(path: pathlib.Path) -> os.stat_result:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ReviewError(f"public input is not a regular non-symlink file: {path.name}")
    return metadata


def write_exclusive(path: pathlib.Path, value: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def fsync_directory(path: pathlib.Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def run_direct(argv: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    options: dict[str, Any] = {
        "check": False,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": {"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    }
    if input_bytes is None:
        options["stdin"] = subprocess.DEVNULL
    else:
        options["input"] = input_bytes
    return subprocess.run(argv, **options)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise ReviewError("authorization time is not an exact UTC second")
    return parsed


def verify_public_pair(public_path: pathlib.Path, allowed_path: pathlib.Path) -> str:
    public_tokens = public_path.read_text(encoding="utf-8").strip().split()
    allowed_tokens = allowed_path.read_text(encoding="utf-8").strip().split()
    if len(public_tokens) != 3 or public_tokens[0] != "ssh-ed25519":
        raise ReviewError("target public-key grammar mismatch")
    if len(allowed_tokens) != 3 or allowed_tokens[0] != AUTHORIZATION_PRINCIPAL:
        raise ReviewError("allowed-signers principal or grammar mismatch")
    if allowed_tokens[1:] != public_tokens[:2]:
        raise ReviewError("allowed-signers public-key bytes differ")
    result = run_direct([str(SSH_KEYGEN), "-l", "-f", str(public_path), "-E", "sha256"])
    tokens = result.stdout.decode().strip().split()
    if result.returncode != 0 or len(tokens) < 4 or tokens[0] != "256" or tokens[-1] != "(ED25519)":
        raise ReviewError("public fingerprint derivation failed")
    return tokens[1]


def verify_authorization(path: pathlib.Path, expected_hash: str) -> tuple[dict[str, Any], bytes]:
    require_regular(path)
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_hash:
        raise ReviewError("authorization SHA-256 mismatch")
    record = json.loads(raw)
    if raw != canonical(record):
        raise ReviewError("authorization is not canonical JCS-I64-v1 bytes")
    expected = {
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "review_principal": REVIEW_PRINCIPAL,
        "public_source_root_absolute_path": str(PUBLIC_ROOT),
        "review_output_root_absolute_path": str(REVIEW_ROOT),
        "review_attempt_count": 1,
        "retry_count": 0,
        "p5_or_later_authorized": False,
    }
    if any(record.get(name) != value for name, value in expected.items()):
        raise ReviewError("authorization identity or one-attempt boundary mismatch")
    issued = parse_utc(str(record.get("issued_at_utc", "")))
    expires = parse_utc(str(record.get("expires_at_utc", "")))
    now = datetime.now(UTC).replace(microsecond=0)
    if int((expires - issued).total_seconds()) != 1800 or now < issued or now >= expires:
        raise ReviewError("authorization is expired, premature, or not exactly 1,800 seconds")
    if record.get("review_tool_sha256") != sha256_file(pathlib.Path(__file__)):
        raise ReviewError("review-tool SHA-256 mismatch")
    enabled = {name for name, value in record.get("authority_boundary", {}).items() if value is True}
    if enabled != {
        "one_bootstrap_sshsig_authorized",
        "one_create_exclusive_public_review_authorized",
        "repository_local_records_tests_and_evidence_authorized",
    }:
        raise ReviewError("D-097 authority boundary omitted or widened")
    return record, raw


def retain_failure(phase: str, authorization_hash: str) -> None:
    if not REVIEW_ROOT.is_dir():
        return
    path = REVIEW_ROOT / "failure_receipt.json"
    if os.path.lexists(path):
        return
    write_exclusive(path, canonical({
        "authorization_sha256": authorization_hash,
        "automatic_continuation": False,
        "decision_id": DECISION_ID,
        "phase": phase,
        "retry_authorized": False,
        "schema_version": "cpu-prefetch-q15-r-p4-k-r-d097-failure/1",
        "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
        "transaction_id": TRANSACTION_ID,
    }))
    fsync_directory(REVIEW_ROOT)


def execute(
    authorization_path: pathlib.Path,
    authorization_hash: str,
    signature_path: pathlib.Path,
    signature_hash: str,
    waiver_path: pathlib.Path,
    waiver_hash: str,
) -> int:
    phase = "PREFLIGHT"
    try:
        authorization, authorization_bytes = verify_authorization(authorization_path, authorization_hash)
        for path, expected in (
            (signature_path, signature_hash),
            (waiver_path, waiver_hash),
            (pathlib.Path("config/q15/q15-r-p4-k-a-d095-terminal-failure-evidence-v1.json"), D095_EVIDENCE),
            (pathlib.Path("config/q15/q15-r-p4-k-a-d096-complete-evidence-v1.json"), D096_EVIDENCE),
            (BOOTSTRAP_ALLOWED_SIGNERS, BOOTSTRAP_TRUST),
        ):
            require_regular(path)
            if sha256_file(path) != expected:
                raise ReviewError(f"bound input SHA-256 mismatch: {path.name}")
        waiver = json.loads(waiver_path.read_text(encoding="utf-8"))
        if waiver.get("status") != "ACCEPTED_SINGLE_OWNER_PUBLIC_ONLY_REVIEW_WAIVER":
            raise ReviewError("single-owner waiver is not accepted")
        signature_result = run_direct([
            str(SSH_KEYGEN), "-Y", "verify", "-f", str(BOOTSTRAP_ALLOWED_SIGNERS),
            "-I", AUTHORIZATION_PRINCIPAL, "-n", SIGNATURE_NAMESPACE,
            "-s", str(signature_path),
        ], input_bytes=authorization_bytes)
        if signature_result.returncode != 0:
            raise ReviewError("bootstrap SSHSIG verification failed")
        for filename, expected in EXPECTED_PUBLIC.items():
            candidate = PUBLIC_ROOT / filename
            require_regular(candidate)
            if sha256_file(candidate) != expected:
                raise ReviewError(f"D-096 public artifact mismatch: {filename}")
        observed_fingerprint = verify_public_pair(
            PUBLIC_ROOT / "target_public_key.pub", PUBLIC_ROOT / "target_allowed_signers"
        )
        if observed_fingerprint != TARGET_FINGERPRINT:
            raise ReviewError("target public fingerprint mismatch")
        if (PUBLIC_ROOT / "target_fingerprint.txt").read_text(encoding="utf-8") != f"{TARGET_FINGERPRINT}\n":
            raise ReviewError("recorded fingerprint bytes mismatch")
        if os.path.lexists(REVIEW_ROOT):
            raise ReviewError("create-exclusive review root already exists")
        parent_metadata = os.lstat(REVIEW_ROOT.parent)
        if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISDIR(parent_metadata.st_mode):
            raise ReviewError("review parent is not a regular directory")
        os.mkdir(REVIEW_ROOT, 0o700)
        fsync_directory(REVIEW_ROOT.parent)

        phase = "COPY_BOUND_PUBLIC_AUTHORITY"
        write_exclusive(REVIEW_ROOT / "review_authorization.json", authorization_bytes)
        write_exclusive(REVIEW_ROOT / "review_authorization.json.sig", signature_path.read_bytes())
        write_exclusive(REVIEW_ROOT / "owner_pre_review_waiver.json", waiver_path.read_bytes())

        phase = "WRITE_REVIEW_EVIDENCE"
        trust = {
            "activation_or_installation_performed": False,
            "allowed_signers_sha256": EXPECTED_PUBLIC["target_allowed_signers"],
            "decision_id": DECISION_ID,
            "fingerprint": TARGET_FINGERPRINT,
            "principal": AUTHORIZATION_PRINCIPAL,
            "protocol_version": "2.0.0-pre.2",
            "public_key_sha256": EXPECTED_PUBLIC["target_public_key.pub"],
            "schema_version": "cpu-prefetch-q15-r-p4-k-r-d097-reviewed-public-trust/1",
            "signature_namespace": SIGNATURE_NAMESPACE,
            "status": "REVIEWED_PUBLIC_TRUST_EVIDENCE_NOT_INSTALLED_NOT_ACTIVE",
            "transaction_id": TRANSACTION_ID,
        }
        trust_path = REVIEW_ROOT / "accepted_public_trust_evidence.json"
        write_exclusive(trust_path, canonical(trust))
        receipt = {
            "accepted_public_trust_evidence_sha256": sha256_file(trust_path),
            "authorization_sha256": authorization_hash,
            "automatic_continuation": False,
            "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "d095_terminal_evidence_sha256": D095_EVIDENCE,
            "d096_complete_evidence_sha256": D096_EVIDENCE,
            "decision_id": DECISION_ID,
            "installation_or_activation_performed": False,
            "private_key_access_or_presence_probe_performed": False,
            "protocol_version": "2.0.0-pre.2",
            "review_attempts": 1,
            "review_principal": REVIEW_PRINCIPAL,
            "retry_count": 0,
            "schema_version": "cpu-prefetch-q15-r-p4-k-r-d097-review-receipt/1",
            "status": "COMPLETE_VALID_PUBLIC_ONLY_REVIEW_STOPPED_BEFORE_P5",
            "target_fingerprint": TARGET_FINGERPRINT,
            "transaction_id": TRANSACTION_ID,
        }
        receipt_path = REVIEW_ROOT / "review_receipt.json"
        write_exclusive(receipt_path, canonical(receipt))
        manifest_paths = tuple(sorted(path for path in REVIEW_ROOT.iterdir() if path.name != "SHA256SUMS"))
        manifest = "".join(f"{sha256_file(path)}  {path.name}\n" for path in manifest_paths).encode()
        write_exclusive(REVIEW_ROOT / "SHA256SUMS", manifest, 0o644)
        fsync_directory(REVIEW_ROOT)
        print(json.dumps({
            "authorization_sha256": authorization_hash,
            "automatic_continuation": False,
            "review_receipt_sha256": sha256_file(receipt_path),
            "status": receipt["status"],
            "target_fingerprint": TARGET_FINGERPRINT,
            "transaction_id": TRANSACTION_ID,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception as exception:  # noqa: BLE001 - terminal evidence must retain every failure.
        retain_failure(phase, authorization_hash)
        print(f"execute-d097-p4-k-r: TERMINAL FAILURE: {phase}: {exception}", file=sys.stderr)
        return 1


def self_test() -> int:
    public_line = (
        "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIH6bUDq2M4V7T2DZ0W/"
        "yRgaIGw2Co28o1XaKKwM8DMih cpu-prefetch-q15-p4-k-v2\n"
    )
    allowed_line = (
        "cpu-prefetch-q15-authorization ssh-ed25519 "
        "AAAAC3NzaC1lZDI1NTE5AAAAIH6bUDq2M4V7T2DZ0W/yRgaIGw2Co28o1XaKKwM8DMih\n"
    )
    with tempfile.TemporaryDirectory(prefix="d097-public-only-") as temporary:
        root = pathlib.Path(temporary)
        public_path = root / "target.pub"
        allowed_path = root / "allowed_signers"
        public_path.write_text(public_line, encoding="utf-8")
        allowed_path.write_text(allowed_line, encoding="utf-8")
        if verify_public_pair(public_path, allowed_path) != TARGET_FINGERPRINT:
            raise ReviewError("public-only known-answer fingerprint failed")
        allowed_path.write_text(allowed_line.replace(AUTHORIZATION_PRINCIPAL, "wrong"), encoding="utf-8")
        try:
            verify_public_pair(public_path, allowed_path)
        except ReviewError:
            pass
        else:
            raise ReviewError("wrong principal was accepted")
    print("execute-d097-p4-k-r: SELF-TEST PASS (public-only known answer + wrong-principal rejection)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--authorization", type=pathlib.Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--signature", type=pathlib.Path)
    parser.add_argument("--signature-sha256")
    parser.add_argument("--waiver", type=pathlib.Path)
    parser.add_argument("--waiver-sha256")
    arguments = parser.parse_args()
    if arguments.self_test:
        return self_test()
    required = (
        arguments.authorization, arguments.authorization_sha256, arguments.signature,
        arguments.signature_sha256, arguments.waiver, arguments.waiver_sha256,
    )
    if any(value is None for value in required):
        parser.error("execution requires every exact authorization/signature/waiver argument")
    return execute(
        arguments.authorization, arguments.authorization_sha256, arguments.signature,
        arguments.signature_sha256, arguments.waiver, arguments.waiver_sha256,
    )


if __name__ == "__main__":
    raise SystemExit(main())
