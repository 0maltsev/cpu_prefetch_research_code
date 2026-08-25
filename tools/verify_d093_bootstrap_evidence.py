#!/usr/bin/env python3
"""Read-only verification of D-093 public evidence and private-file metadata."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
from typing import Any


PRIVATE_KEY = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/id_ed25519"
)
PUBLIC_ROOT = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/bootstrap-root-v1/public"
)
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
AUTHORIZATION_SHA256 = "271584663d21718357b6fcf013ca0a83a842410cae24d9463b4723217cdb954e"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
EXPECTED_PUBLIC_FILES = {
    "SHA256SUMS",
    "action_authorization.json",
    "allowed_signers",
    "fingerprint.txt",
    "public_receipt.json",
    "root_public_key.pub",
}


class VerificationError(RuntimeError):
    """A D-093 public-evidence or metadata mismatch."""


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_real_directory(path: pathlib.Path, expected_mode: int) -> os.stat_result:
    metadata = os.lstat(path)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise VerificationError(f"not a real directory: {path}")
    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise VerificationError(f"directory mode mismatch: {path}")
    return metadata


def private_metadata_without_reading() -> dict[str, Any]:
    metadata = os.lstat(PRIVATE_KEY)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise VerificationError("private key is not a real regular file")
    if stat.S_IMODE(metadata.st_mode) != 0o600:
        raise VerificationError("private-key mode is not 0600")
    if os.path.lexists(pathlib.Path(f"{PRIVATE_KEY}.pub")):
        raise VerificationError("unexpected public-key copy remains beside private key")
    return {
        "mode_octal": "0600",
        "owner_uid": metadata.st_uid,
        "owner_gid": metadata.st_gid,
        "size_bytes_observed_without_content_read": metadata.st_size,
        "content_read_or_hashed": False,
    }


def parse_checksum_sidecar(path: pathlib.Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, separator, filename = line.partition("  ")
        if (
            not separator
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not filename
            or "/" in filename
            or filename in result
        ):
            raise VerificationError("malformed SHA256SUMS entry")
        result[filename] = digest
    return result


def verify() -> dict[str, Any]:
    base_metadata = require_real_directory(PRIVATE_KEY.parent, 0o700)
    public_metadata = require_real_directory(PUBLIC_ROOT, 0o700)
    if base_metadata.st_uid != 1000 or public_metadata.st_uid != 1000:
        raise VerificationError("D-093 output directories have unexpected owner")
    observed_names = {entry.name for entry in PUBLIC_ROOT.iterdir()}
    if observed_names != EXPECTED_PUBLIC_FILES:
        raise VerificationError("public artifact inventory differs from the exact set")

    private = private_metadata_without_reading()
    authorization_path = PUBLIC_ROOT / "action_authorization.json"
    if sha256_file(authorization_path) != AUTHORIZATION_SHA256:
        raise VerificationError("copied action authorization hash mismatch")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if authorization.get("decision_id") != "D-093":
        raise VerificationError("copied action authorization is not D-093")

    public_line = (PUBLIC_ROOT / "root_public_key.pub").read_text(
        encoding="utf-8"
    )
    tokens = public_line.strip().split()
    if len(tokens) != 3 or tokens[0] != "ssh-ed25519":
        raise VerificationError("public key is not the exact OpenSSH Ed25519 shape")
    expected_allowed = f"{AUTHORIZATION_PRINCIPAL} {tokens[0]} {tokens[1]}\n"
    if (PUBLIC_ROOT / "allowed_signers").read_text(
        encoding="utf-8"
    ) != expected_allowed:
        raise VerificationError("allowed-signers bytes do not match the public key")

    fingerprint_result = subprocess.run(
        [
            str(SSH_KEYGEN),
            "-l",
            "-f",
            str(PUBLIC_ROOT / "root_public_key.pub"),
            "-E",
            "sha256",
        ],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )
    fingerprint_tokens = fingerprint_result.stdout.strip().split()
    if fingerprint_result.returncode != 0 or len(fingerprint_tokens) < 2:
        raise VerificationError("public fingerprint verification command failed")
    fingerprint = fingerprint_tokens[1]
    if (PUBLIC_ROOT / "fingerprint.txt").read_text(
        encoding="utf-8"
    ) != f"{fingerprint}\n":
        raise VerificationError("fingerprint artifact differs from public-key evidence")

    sidecar_path = PUBLIC_ROOT / "SHA256SUMS"
    sidecar = parse_checksum_sidecar(sidecar_path)
    protected_names = EXPECTED_PUBLIC_FILES - {"SHA256SUMS"}
    if set(sidecar) != protected_names:
        raise VerificationError("SHA256SUMS does not protect the exact public inventory")
    for filename, expected_hash in sidecar.items():
        if sha256_file(PUBLIC_ROOT / filename) != expected_hash:
            raise VerificationError(f"public artifact hash mismatch: {filename}")

    receipt_path = PUBLIC_ROOT / "public_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if (
        receipt.get("decision_id") != "D-093"
        or receipt.get("status")
        != "COMPLETE_PUBLIC_EVIDENCE_ONLY_PRIVATE_KEY_NOT_EMITTED"
        or receipt.get("fingerprint") != fingerprint
        or receipt.get("private_key_content_read_by_action_tool") is not False
        or receipt.get("private_key_hash_or_bytes_recorded") is not False
        or receipt.get("automatic_continuation") is not False
        or receipt.get("next_gate") != "SEPARATE_P4_K_A_AUTHORIZATION_REQUIRED"
    ):
        raise VerificationError("public receipt boundary or relationship mismatch")

    artifacts = [
        {
            "filename": name,
            "sha256": sha256_file(PUBLIC_ROOT / name),
            "size_bytes": (PUBLIC_ROOT / name).stat().st_size,
        }
        for name in sorted(EXPECTED_PUBLIC_FILES)
    ]
    return {
        "schema_version": "cpu-prefetch-q15-r-bootstrap-root-d093-verification-summary/1",
        "decision_id": "D-093",
        "transaction_id": receipt["transaction_id"],
        "status": "VERIFIED_PUBLIC_EVIDENCE_PRIVATE_METADATA_ONLY",
        "created_at_utc": receipt["created_at_utc"],
        "fingerprint": fingerprint,
        "authorization_principal": AUTHORIZATION_PRINCIPAL,
        "public_root_absolute_path": str(PUBLIC_ROOT),
        "private_key_metadata": private,
        "public_artifacts": artifacts,
        "automatic_continuation": False,
        "next_gate": "SEPARATE_P4_K_A_AUTHORIZATION_REQUIRED",
    }


def main() -> int:
    try:
        summary = verify()
    except (VerificationError, OSError, ValueError, json.JSONDecodeError) as exception:
        print(f"verify-d093-bootstrap-evidence: FAIL: {exception}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
