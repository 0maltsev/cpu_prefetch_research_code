#!/usr/bin/env python3
"""Execute one corrected bootstrap-signed D-096 P4-K-v2 action."""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any

import execute_d095_p4_k_a as frozen


DECISION_ID = "D-096"
TRANSACTION_ID = "Q15-R-P4-K-A-D096-20260826-01"
OWNER_PRINCIPAL = "cpu-prefetch-bootstrap-owner"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
SIGNATURE_NAMESPACE = "cpu-prefetch-q15-authorization"
BOOTSTRAP_FINGERPRINT = "SHA256:JuRM4SuWL9C1xvOes9z+CAKZV1rvel27VZ/+qiuVNs0"
BOOTSTRAP_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519"
)
BOOTSTRAP_ALLOWED_SIGNERS = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public/allowed_signers"
)
D095_PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/public"
)
D095_TARGET_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v1/id_ed25519"
)
TARGET_PRIVATE = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/id_ed25519"
)
TARGET_PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public"
)
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
ACTION_PYTHON = pathlib.Path("/usr/bin/python3")
TARGET_KEY_COMMENT = "cpu-prefetch-q15-p4-k-v2"
D095_HELPER_SHA256 = "dee54311e8698c50d63709b7294af9895c482647ca8a51b8a6341e08364a16c9"
D095_EVIDENCE_SHA256 = "ccfe61af14b8aca872a9fd0f4ab4371fb3e74cf445846c8b1a8b30e660f2fa2d"
BOOTSTRAP_ALLOWED_SIGNERS_SHA256 = (
    "6c21b0d631a3842e182bd92e0856aa5073c949f5c5a6b4a8e85b48dd2016f33d"
)
D095_PUBLIC_HASHES = {
    "action_authorization.json": "e1a8934198dd2a581ff97564dfc33e4830750c18184893a18f37d80067a94728",
    "action_authorization.json.sig": "9c447e077f388ebf257e16384eafbd81b54c267296db7c0633809b5c874f23f1",
    "owner_pre_action_review.json": "2bb30b1fe2f987e0efba9bbd4623e0682bac2302c15f3665c378014390f4fc5e",
    "failure_receipt.json": "efe4b3c8b526f20600c0d2217f5110afbbc97fb63676b12416030586b3ecea99",
}
PUBLIC_NAMES_BEFORE_RECEIPT = (
    "action_authorization.json",
    "action_authorization.json.sig",
    "bootstrap_signature_verification.json",
    "owner_pre_action_review.json",
    "target_allowed_signers",
    "target_fingerprint.txt",
    "target_public_key.pub",
)


class D096Error(RuntimeError):
    """A fail-closed D-096 preflight or action failure."""


def run_direct(
    argv: list[str], *, input_bytes: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
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
        raise D096Error("authorization UTC is not an exact whole-second UTC instant")
    return parsed


def parse_public_key_line(value: str) -> tuple[str, str]:
    tokens = value.strip().split()
    if len(tokens) != 3 or tokens[0] != "ssh-ed25519" or tokens[2] != TARGET_KEY_COMMENT:
        raise D096Error("target public-key shape differs from the D-096 contract")
    try:
        decoded = base64.b64decode(tokens[1], validate=True)
    except ValueError as exception:
        raise D096Error("target public-key payload is not canonical base64") from exception
    if not decoded:
        raise D096Error("target public-key payload is empty")
    return tokens[0], tokens[1]


def exact_authorization_errors(record: dict[str, Any]) -> list[str]:
    expected = {
        "schema_version": "cpu-prefetch-q15-r-p4-k-a-d096-action-authorization/1",
        "authorization_id": "Q15-R-P4-K-A-D096-AUTHORIZATION-20260826-01",
        "protocol_version": "2.0.0-pre.2",
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "AUTHORIZED_ONE_CORRECTED_BOOTSTRAP_SIGNATURE_AND_ONE_P4_K_V2_ACTION",
        "source_commit": "7a2c4e58bf771543edac6afd3e3a110ae61b30bf",
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
        "d095_evidence_mutation_allowed": False,
        "p4_k_r_or_later_phase_authorized": False,
    }
    return [
        f"authorization field mismatch: {name}"
        for name, value in expected.items()
        if record.get(name) != value
    ]


def load_and_verify_authorization(
    path: pathlib.Path, expected_sha256: str
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if frozen.sha256_bytes(raw) != expected_sha256:
        raise D096Error("canonical action-authorization SHA-256 mismatch")
    record = json.loads(raw)
    if raw != frozen.canonical_json(record):
        raise D096Error("action authorization is not exact JCS-I64-v1 bytes")
    errors = exact_authorization_errors(record)
    if record.get("action_tool_sha256") != frozen.sha256_file(pathlib.Path(__file__)):
        errors.append("action-tool SHA-256 mismatch")
    helper_path = pathlib.Path(frozen.__file__)
    if record.get("d095_frozen_helper_sha256") != frozen.sha256_file(helper_path):
        errors.append("frozen D-095 helper SHA-256 mismatch")
    if record.get("d095_frozen_helper_sha256") != D095_HELPER_SHA256:
        errors.append("unexpected D-095 helper identity")
    if record.get("action_python_sha256") != frozen.sha256_file(ACTION_PYTHON):
        errors.append("action Python SHA-256 mismatch")
    if record.get("ssh_keygen_sha256") != frozen.sha256_file(SSH_KEYGEN):
        errors.append("ssh-keygen SHA-256 mismatch")
    if record.get("d095_terminal_evidence_sha256") != D095_EVIDENCE_SHA256:
        errors.append("D-095 terminal evidence identity mismatch")
    if pathlib.Path(sys.executable).resolve() != ACTION_PYTHON.resolve():
        errors.append("action is running under an unbound Python interpreter")
    issued = parse_utc(str(record.get("issued_at_utc", "")))
    expires = parse_utc(str(record.get("expires_at_utc", "")))
    if int((expires - issued).total_seconds()) != 1800:
        errors.append("authorization window is not exactly 1,800 seconds")
    now = datetime.now(UTC).replace(microsecond=0)
    if now < issued or now >= expires:
        errors.append("authorization is outside its nonrenewable UTC window")
    if errors:
        raise D096Error("; ".join(errors))
    return record, raw


def verify_d095_immutable() -> None:
    repository_evidence = pathlib.Path(
        "config/q15/q15-r-p4-k-a-d095-terminal-failure-evidence-v1.json"
    )
    if frozen.sha256_file(repository_evidence) != D095_EVIDENCE_SHA256:
        raise D096Error("repository D-095 terminal evidence drifted")
    for filename, expected_hash in D095_PUBLIC_HASHES.items():
        candidate = D095_PUBLIC_ROOT / filename
        if not candidate.is_file() or frozen.sha256_file(candidate) != expected_hash:
            raise D096Error(f"D-095 partial public evidence drifted: {filename}")
    if os.path.lexists(D095_TARGET_PRIVATE):
        raise D096Error("D-095 target private path unexpectedly exists")


def retain_failure(phase: str, authorization_sha256: str) -> None:
    if not TARGET_PUBLIC_ROOT.is_dir():
        return
    failure_path = TARGET_PUBLIC_ROOT / "failure_receipt.json"
    if os.path.lexists(failure_path):
        return
    failure = {
        "schema_version": "cpu-prefetch-q15-r-p4-k-a-d096-failure/1",
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
        "phase": phase,
        "authorization_sha256": authorization_sha256,
        "automatic_continuation": False,
    }
    frozen.write_exclusive(failure_path, frozen.canonical_json(failure))
    frozen.fsync_directory(TARGET_PUBLIC_ROOT)


def execute(authorization_path: pathlib.Path, authorization_sha256: str) -> int:
    phase = "PREFLIGHT"
    try:
        authorization, authorization_bytes = load_and_verify_authorization(
            authorization_path, authorization_sha256
        )
        verify_d095_immutable()
        frozen.require_private_metadata(BOOTSTRAP_PRIVATE)
        if frozen.sha256_file(BOOTSTRAP_ALLOWED_SIGNERS) != BOOTSTRAP_ALLOWED_SIGNERS_SHA256:
            raise D096Error("bootstrap allowed-signers SHA-256 mismatch")
        if os.path.lexists(TARGET_PRIVATE.parent):
            raise D096Error("create-exclusive P4-K-v2 transaction already exists")
        frozen.reject_symlinked_existing_components(TARGET_PRIVATE.parent.parent)
        frozen.create_parent_directories(TARGET_PRIVATE.parent.parent)
        os.mkdir(TARGET_PRIVATE.parent, 0o700)
        os.mkdir(TARGET_PUBLIC_ROOT, 0o700)
        frozen.fsync_directory(TARGET_PRIVATE.parent.parent)

        phase = "WRITE_AUTHORIZATION_AND_OWNER_REVIEW"
        action_copy = TARGET_PUBLIC_ROOT / "action_authorization.json"
        frozen.write_exclusive(action_copy, authorization_bytes)
        review = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d096-owner-review/1",
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "ACCEPTED_SINGLE_OWNER_D096_REVIEW_WAIVER_APPLIED",
            "owner_principal": OWNER_PRINCIPAL,
            "authorization_sha256": authorization_sha256,
            "reviewed_at_utc": authorization["issued_at_utc"],
            "d095_partial_tree_preserved": True,
            "corrected_wrapper_regression_passed": True,
            "distinct_auditor_exists": False,
            "action_authorized": True,
            "p4_k_r_or_later_authorized": False,
        }
        review_path = TARGET_PUBLIC_ROOT / "owner_pre_action_review.json"
        frozen.write_exclusive(review_path, frozen.canonical_json(review))

        phase = "BOOTSTRAP_SSHSIG_SIGN"
        sign_result = run_direct([
            str(SSH_KEYGEN), "-Y", "sign", "-f", str(BOOTSTRAP_PRIVATE),
            "-n", SIGNATURE_NAMESPACE, "-O", "hashalg=sha512", str(action_copy),
        ])
        signature_path = pathlib.Path(f"{action_copy}.sig")
        if sign_result.returncode != 0 or not signature_path.is_file():
            raise D096Error("bootstrap SSHSIG creation failed; retry forbidden")

        phase = "BOOTSTRAP_SSHSIG_VERIFY"
        verify_result = run_direct([
            str(SSH_KEYGEN), "-Y", "verify", "-f", str(BOOTSTRAP_ALLOWED_SIGNERS),
            "-I", AUTHORIZATION_PRINCIPAL, "-n", SIGNATURE_NAMESPACE,
            "-s", str(signature_path),
        ], input_bytes=authorization_bytes)
        if verify_result.returncode != 0:
            raise D096Error("bootstrap SSHSIG verification failed; action stopped")
        verification = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d096-bootstrap-verification/1",
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "PASS",
            "authorization_sha256": authorization_sha256,
            "signature_sha256": frozen.sha256_file(signature_path),
            "bootstrap_fingerprint": BOOTSTRAP_FINGERPRINT,
            "allowed_signers_sha256": BOOTSTRAP_ALLOWED_SIGNERS_SHA256,
            "principal": AUTHORIZATION_PRINCIPAL,
            "namespace": SIGNATURE_NAMESPACE,
            "hash_algorithm": "sha512",
        }
        verification_path = TARGET_PUBLIC_ROOT / "bootstrap_signature_verification.json"
        frozen.write_exclusive(verification_path, frozen.canonical_json(verification))

        phase = "TARGET_SSH_KEYGEN"
        keygen_result = run_direct([
            str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C",
            TARGET_KEY_COMMENT, "-f", str(TARGET_PRIVATE),
        ])
        generated_public = pathlib.Path(f"{TARGET_PRIVATE}.pub")
        if keygen_result.returncode != 0 or not TARGET_PRIVATE.is_file() or not generated_public.is_file():
            raise D096Error("target ssh-keygen failed; partial retained and retry forbidden")
        os.chmod(TARGET_PRIVATE, 0o600)

        phase = "TARGET_PUBLIC_EVIDENCE"
        public_line = generated_public.read_text(encoding="utf-8")
        key_type, public_payload = parse_public_key_line(public_line)
        target_public_path = TARGET_PUBLIC_ROOT / "target_public_key.pub"
        os.rename(generated_public, target_public_path)
        os.chmod(target_public_path, 0o644)
        frozen.write_exclusive(
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
            raise D096Error("target fingerprint derivation failed closed")
        target_fingerprint = fingerprint_tokens[1]
        frozen.write_exclusive(
            TARGET_PUBLIC_ROOT / "target_fingerprint.txt",
            f"{target_fingerprint}\n".encode(),
        )

        phase = "SEAL_EVIDENCE"
        private_metadata = frozen.require_private_metadata(TARGET_PRIVATE)
        initial_paths = [TARGET_PUBLIC_ROOT / name for name in PUBLIC_NAMES_BEFORE_RECEIPT]
        receipt = {
            "schema_version": "cpu-prefetch-q15-r-p4-k-a-d096-action-receipt/1",
            "protocol_version": authorization["protocol_version"],
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "COMPLETE_VALID_P4_K_V2_CREATED_STOPPED_FOR_P4_K_R",
            "completed_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "authorization_sha256": authorization_sha256,
            "bootstrap_signature_sha256": frozen.sha256_file(signature_path),
            "bootstrap_fingerprint": BOOTSTRAP_FINGERPRINT,
            "owner_review_sha256": frozen.sha256_file(review_path),
            "bootstrap_verification_sha256": frozen.sha256_file(verification_path),
            "d095_terminal_evidence_sha256": D095_EVIDENCE_SHA256,
            "d095_partial_tree_preserved": True,
            "target_fingerprint": target_fingerprint,
            "target_private_key_absolute_path": str(TARGET_PRIVATE),
            "target_private_key_mode_octal": "0600",
            "target_private_key_size_bytes_observed_without_content_read": private_metadata.st_size,
            "target_private_key_content_read_or_hashed_by_action_tool": False,
            "target_private_key_encrypted": False,
            "independent_recovery_exists": False,
            "public_artifacts_before_receipt": [frozen.public_artifact(path) for path in initial_paths],
            "automatic_continuation": False,
            "next_gate": "SEPARATE_P4_K_R_REVIEW_AUTHORIZATION_REQUIRED",
        }
        receipt_path = TARGET_PUBLIC_ROOT / "action_receipt.json"
        frozen.write_exclusive(receipt_path, frozen.canonical_json(receipt))
        checksum_paths = initial_paths + [receipt_path]
        checksum_lines = "".join(
            f"{frozen.sha256_file(path)}  {path.name}\n"
            for path in sorted(checksum_paths)
        )
        frozen.write_exclusive(TARGET_PUBLIC_ROOT / "SHA256SUMS", checksum_lines.encode())
        frozen.fsync_directory(TARGET_PUBLIC_ROOT)
        frozen.fsync_directory(TARGET_PRIVATE.parent)
        print(json.dumps({
            "status": receipt["status"],
            "transaction_id": TRANSACTION_ID,
            "authorization_sha256": authorization_sha256,
            "bootstrap_signature_sha256": receipt["bootstrap_signature_sha256"],
            "target_fingerprint": target_fingerprint,
            "target_public_root": str(TARGET_PUBLIC_ROOT),
            "target_private_key_created": True,
            "target_private_key_emitted": False,
            "automatic_continuation": False,
        }, sort_keys=True, separators=(",", ":")))
        return 0
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError) as exception:
        try:
            retain_failure(phase, authorization_sha256)
        except OSError:
            pass
        raise D096Error(f"{phase}: {exception}") from exception


def self_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = pathlib.Path(directory)
        private = root / "fixture_key"
        message = root / "message.json"
        message_bytes = b'{"d096":"regression"}\n'
        message.write_bytes(message_bytes)
        keygen = run_direct([
            str(SSH_KEYGEN), "-q", "-t", "ed25519", "-N", "", "-C",
            "d096-disposable-regression", "-f", str(private),
        ])
        if keygen.returncode != 0:
            raise D096Error("disposable regression key generation failed")
        public_tokens = pathlib.Path(f"{private}.pub").read_text(encoding="utf-8").split()
        allowed = root / "allowed_signers"
        allowed.write_text(
            f"{AUTHORIZATION_PRINCIPAL} {public_tokens[0]} {public_tokens[1]}\n",
            encoding="utf-8",
        )
        sign = run_direct([
            str(SSH_KEYGEN), "-Y", "sign", "-f", str(private), "-n",
            SIGNATURE_NAMESPACE, "-O", "hashalg=sha512", str(message),
        ])
        signature = pathlib.Path(f"{message}.sig")
        if sign.returncode != 0 or not signature.is_file():
            raise D096Error("disposable regression signature failed")
        verify_argv = [
            str(SSH_KEYGEN), "-Y", "verify", "-f", str(allowed), "-I",
            AUTHORIZATION_PRINCIPAL, "-n", SIGNATURE_NAMESPACE, "-s", str(signature),
        ]
        if run_direct(verify_argv, input_bytes=message_bytes).returncode != 0:
            raise D096Error("corrected stdin regression verification failed")
        if run_direct(verify_argv, input_bytes=b"wrong\n").returncode == 0:
            raise D096Error("wrong-message regression mutation passed")
    print("execute-d096-p4-k-a: SELF-TEST PASS (disposable sign/verify, no real key used)")
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
                raise D096Error("self-test accepts no authorization arguments")
            return self_test()
        if not arguments.authorization_record or not arguments.authorization_sha256:
            raise D096Error("execute requires exact authorization path and SHA-256")
        return execute(arguments.authorization_record, arguments.authorization_sha256)
    except D096Error as exception:
        print(f"execute-d096-p4-k-a: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
