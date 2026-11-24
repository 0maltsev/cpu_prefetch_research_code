#!/usr/bin/env python3
"""Execute the one D-093 bootstrap-root action without emitting private bytes."""

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


SCHEMA_VERSION = "cpu-prefetch-q15-r-bootstrap-root-d093-action-authorization/1"
DECISION_ID = "D-093"
TRANSACTION_ID = "Q15-R-BOOTSTRAP-D093-20260825-01"
OWNER_PRINCIPAL = "cpu-prefetch-bootstrap-owner"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
KEY_COMMENT = "cpu-prefetch-q15-bootstrap-root-v1"
PRIVATE_KEY = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519"
)
PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public"
)
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
ACTION_PYTHON = pathlib.Path("/usr/bin/python3")
PUBLIC_FILENAMES = (
    "action_authorization.json",
    "allowed_signers",
    "fingerprint.txt",
    "root_public_key.pub",
)


class D093Error(RuntimeError):
    """A fail-closed D-093 preflight or execution failure."""


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
                raise D093Error("exclusive public-artifact write made no progress")
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


def parse_public_key_line(value: str) -> tuple[str, str]:
    tokens = value.strip().split()
    if len(tokens) != 3 or tokens[0] != "ssh-ed25519" or tokens[2] != KEY_COMMENT:
        raise D093Error("generated public-key shape differs from the D-093 contract")
    try:
        decoded = base64.b64decode(tokens[1], validate=True)
    except ValueError as exception:
        raise D093Error("generated public-key payload is not canonical base64") from exception
    if not decoded:
        raise D093Error("generated public-key payload is empty")
    return tokens[0], tokens[1]


def canonical_allowed_signers(key_type: str, public_payload: str) -> bytes:
    return f"{AUTHORIZATION_PRINCIPAL} {key_type} {public_payload}\n".encode()


def reject_symlinked_existing_components(path: pathlib.Path) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if not os.path.lexists(current):
            continue
        metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise D093Error("an existing output-path component is not a real directory")


def create_parent_directories(path: pathlib.Path) -> None:
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if os.path.lexists(current):
            metadata = os.lstat(current)
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
                raise D093Error("an output parent is not a real directory")
            continue
        os.mkdir(current, 0o700)


def exact_authorization_errors(record: dict[str, Any]) -> list[str]:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "AUTHORIZED_ONE_CREATE_EXCLUSIVE_ACTION",
        "owner_principal": OWNER_PRINCIPAL,
        "owner_posix_account": "omaltsev",
        "private_key_absolute_path": str(PRIVATE_KEY),
        "public_root_absolute_path": str(PUBLIC_ROOT),
        "ssh_keygen_absolute_path": str(SSH_KEYGEN),
        "action_python_absolute_path": str(ACTION_PYTHON),
        "algorithm": "OPENSSH_ED25519",
        "private_key_encrypted": False,
        "role_separation_required": False,
        "independent_recovery_required": False,
        "development_host_allowed": True,
        "action_attempt_count": 1,
        "retry_count": 0,
        "overwrite_allowed": False,
        "private_key_output_or_repository_import_allowed": False,
        "p4_k_a_or_later_phase_authorized": False,
    }
    errors = [
        f"authorization field mismatch: {name}"
        for name, value in expected.items()
        if record.get(name) != value
    ]
    if record.get("public_filenames") != list(PUBLIC_FILENAMES):
        errors.append("public artifact filename contract drifted")
    return errors


def load_and_verify_authorization(
    path: pathlib.Path, expected_sha256: str
) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if sha256_bytes(raw) != expected_sha256:
        raise D093Error("action-authorization SHA-256 mismatch")
    record = json.loads(raw)
    errors = exact_authorization_errors(record)
    if record.get("action_tool_sha256") != sha256_file(pathlib.Path(__file__)):
        errors.append("action-tool SHA-256 mismatch")
    if record.get("ssh_keygen_sha256") != sha256_file(SSH_KEYGEN):
        errors.append("ssh-keygen SHA-256 mismatch")
    if record.get("action_python_sha256") != sha256_file(ACTION_PYTHON):
        errors.append("action Python SHA-256 mismatch")
    if pathlib.Path(sys.executable).resolve() != ACTION_PYTHON.resolve():
        errors.append("action is running under an unbound Python interpreter")
    if errors:
        raise D093Error("; ".join(errors))
    return record, raw


def run_direct(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )


def public_artifact(path: pathlib.Path) -> dict[str, Any]:
    return {
        "filename": path.name,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def execute(authorization_path: pathlib.Path, authorization_sha256: str) -> int:
    authorization, authorization_bytes = load_and_verify_authorization(
        authorization_path, authorization_sha256
    )
    base = PRIVATE_KEY.parent
    if os.path.lexists(base):
        raise D093Error("create-exclusive bootstrap-root transaction already exists")
    reject_symlinked_existing_components(base.parent)
    create_parent_directories(base.parent)
    os.mkdir(base, 0o700)
    os.mkdir(PUBLIC_ROOT, 0o700)
    fsync_directory(base.parent)

    keygen = run_direct(
        [
            str(SSH_KEYGEN),
            "-q",
            "-t",
            "ed25519",
            "-N",
            "",
            "-C",
            KEY_COMMENT,
            "-f",
            str(PRIVATE_KEY),
        ]
    )
    if keygen.returncode != 0:
        failure = {
            "schema_version": "cpu-prefetch-q15-r-bootstrap-root-d093-failure/1",
            "decision_id": DECISION_ID,
            "transaction_id": TRANSACTION_ID,
            "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
            "phase": "SSH_KEYGEN",
            "exit_code": keygen.returncode,
            "authorization_sha256": authorization_sha256,
        }
        write_exclusive(PUBLIC_ROOT / "failure_receipt.json", canonical_json(failure))
        fsync_directory(PUBLIC_ROOT)
        raise D093Error("ssh-keygen failed; partial evidence retained and retry forbidden")

    generated_public = pathlib.Path(f"{PRIVATE_KEY}.pub")
    if not PRIVATE_KEY.is_file() or not generated_public.is_file():
        raise D093Error("ssh-keygen returned success without both required outputs")
    os.chmod(PRIVATE_KEY, 0o600)
    public_line = generated_public.read_text(encoding="utf-8")
    key_type, public_payload = parse_public_key_line(public_line)

    public_key_path = PUBLIC_ROOT / "root_public_key.pub"
    os.rename(generated_public, public_key_path)
    os.chmod(public_key_path, 0o644)
    write_exclusive(
        PUBLIC_ROOT / "allowed_signers",
        canonical_allowed_signers(key_type, public_payload),
    )
    write_exclusive(PUBLIC_ROOT / "action_authorization.json", authorization_bytes)

    fingerprint_result = run_direct(
        [str(SSH_KEYGEN), "-l", "-f", str(public_key_path), "-E", "sha256"]
    )
    fingerprint_tokens = fingerprint_result.stdout.strip().split()
    if (
        fingerprint_result.returncode != 0
        or len(fingerprint_tokens) < 4
        or fingerprint_tokens[0] != "256"
        or not fingerprint_tokens[1].startswith("SHA256:")
        or fingerprint_tokens[-1] != "(ED25519)"
    ):
        raise D093Error("public fingerprint derivation failed closed")
    fingerprint = fingerprint_tokens[1]
    write_exclusive(PUBLIC_ROOT / "fingerprint.txt", f"{fingerprint}\n".encode())

    initial_artifacts = [
        public_artifact(PUBLIC_ROOT / name) for name in PUBLIC_FILENAMES
    ]
    receipt = {
        "schema_version": "cpu-prefetch-q15-r-bootstrap-root-d093-public-receipt/1",
        "protocol_version": authorization["protocol_version"],
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "status": "COMPLETE_PUBLIC_EVIDENCE_ONLY_PRIVATE_KEY_NOT_EMITTED",
        "created_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "owner_principal": OWNER_PRINCIPAL,
        "owner_posix_account": "omaltsev",
        "roles_collapsed_by_d093": True,
        "development_host_used_by_d093": True,
        "algorithm": "OPENSSH_ED25519",
        "private_key_encrypted": False,
        "independent_recovery_exists": False,
        "private_key_absolute_path": str(PRIVATE_KEY),
        "private_key_mode_octal": "0600",
        "private_key_content_read_by_action_tool": False,
        "private_key_hash_or_bytes_recorded": False,
        "authorization_sha256": authorization_sha256,
        "public_root_absolute_path": str(PUBLIC_ROOT),
        "authorization_principal": AUTHORIZATION_PRINCIPAL,
        "fingerprint": fingerprint,
        "public_artifacts": initial_artifacts,
        "automatic_continuation": False,
        "next_gate": "SEPARATE_P4_K_A_AUTHORIZATION_REQUIRED",
    }
    receipt_path = PUBLIC_ROOT / "public_receipt.json"
    write_exclusive(receipt_path, canonical_json(receipt))
    checksum_paths = [PUBLIC_ROOT / name for name in PUBLIC_FILENAMES] + [receipt_path]
    checksum_lines = "".join(
        f"{sha256_file(path)}  {path.name}\n" for path in sorted(checksum_paths)
    )
    write_exclusive(PUBLIC_ROOT / "SHA256SUMS", checksum_lines.encode())
    fsync_directory(PUBLIC_ROOT)
    fsync_directory(base)

    summary = {
        "status": receipt["status"],
        "transaction_id": TRANSACTION_ID,
        "public_root": str(PUBLIC_ROOT),
        "fingerprint": fingerprint,
        "authorization_sha256": authorization_sha256,
        "private_key_created": True,
        "private_key_emitted": False,
        "automatic_continuation": False,
    }
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


def self_test() -> int:
    payload = base64.b64encode(b"non-secret-d093-fixture").decode()
    key_type, parsed = parse_public_key_line(
        f"ssh-ed25519 {payload} {KEY_COMMENT}\n"
    )
    expected = (
        f"{AUTHORIZATION_PRINCIPAL} ssh-ed25519 {payload}\n".encode()
    )
    if key_type != "ssh-ed25519" or parsed != payload:
        raise D093Error("self-test public-key parsing failed")
    if canonical_allowed_signers(key_type, parsed) != expected:
        raise D093Error("self-test allowed-signers canonicalization failed")
    for invalid in (
        f"ssh-rsa {payload} {KEY_COMMENT}",
        f"ssh-ed25519 {payload}",
        f"ssh-ed25519 !!! {KEY_COMMENT}",
    ):
        try:
            parse_public_key_line(invalid)
        except D093Error:
            continue
        raise D093Error("self-test invalid public-key mutation passed")
    with tempfile.TemporaryDirectory() as directory:
        path = pathlib.Path(directory) / "exclusive"
        write_exclusive(path, b"public fixture\n")
        try:
            write_exclusive(path, b"overwrite\n")
        except FileExistsError:
            pass
        else:
            raise D093Error("self-test overwrite mutation passed")
    print("create-d093-bootstrap-root: SELF-TEST PASS (no key generated)")
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
                raise D093Error("self-test accepts no authorization inputs")
            return self_test()
        if not arguments.authorization_record or not arguments.authorization_sha256:
            raise D093Error("execution requires an exact authorization record and hash")
        return execute(arguments.authorization_record, arguments.authorization_sha256)
    except (D093Error, FileExistsError, json.JSONDecodeError, OSError) as exception:
        print(f"create-d093-bootstrap-root: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
