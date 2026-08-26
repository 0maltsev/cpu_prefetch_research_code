#!/usr/bin/env python3
"""Execute and review one fail-closed D-099 P4-R-I identity transaction."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from typing import Any, Callable


DECISION_ID = "D-099"
TRANSACTION_ID = "Q15-R-P4-R-I-D099-XEON-CPU-FETCH-20260826-01"
ARTIFACT_ID = "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01"
HOST = "185.184.131.153"
DESTINATION = f"root@{HOST}"
HOST_FINGERPRINT = "SHA256:HZMyUcQIuSQIodYGxXGQ3RCoqR8UcOWPPzuTDhXKtS4"
TRANSPORT_FINGERPRINT = "SHA256:mtIlJWQzNackGLwexvC6bTnmLb8yJtdUQdC/k+FxKRo"
SIGNER_FINGERPRINT = "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM"
AUTHORIZATION_PRINCIPAL = "cpu-prefetch-q15-authorization"
SIGNATURE_NAMESPACE = "cpu-prefetch-q15-authorization"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
PINNED_HOSTS = PROJECT_ROOT / "config/q15/q15-r-p4-r-i-d099-pinned-host-v1.known_hosts"
TRANSPORT_PUBLIC = pathlib.Path("/home/omaltsev/.ssh/id_ed25519.pub")
TRANSPORT_PRIVATE = pathlib.Path("/home/omaltsev/.ssh/id_ed25519")
TARGET_ALLOWED_SIGNERS = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public/target_allowed_signers"
)
SSH = pathlib.Path("/usr/bin/ssh")
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
CAPTURE_ROOT = (
    PROJECT_ROOT
    / "docs/evidence/stage17/Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
)
ARTIFACT = CAPTURE_ROOT / f"{ARTIFACT_ID}.json"
SIDECAR = CAPTURE_ROOT / f"{ARTIFACT_ID}.json.sha256"
REVIEW = CAPTURE_ROOT / f"{ARTIFACT_ID}.owner-review.json"
REVIEW_SIDECAR = CAPTURE_ROOT / f"{ARTIFACT_ID}.owner-review.json.sha256"
OBSERVATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("P4RI-001", ("/usr/bin/hostname",)),
    ("P4RI-002", ("/usr/bin/uname", "--kernel-name", "--kernel-release", "--machine")),
    (
        "P4RI-003",
        (
            "/usr/bin/stat",
            "--format=%n|%F|%a|%u|%g|%s|%d|%i",
            "--",
            "/",
            "/root",
            "/dev/md3",
        ),
    ),
    (
        "P4RI-004",
        (
            "/usr/bin/findmnt",
            "--json",
            "--target",
            "/",
            "--output",
            "TARGET,SOURCE,FSTYPE,OPTIONS,PROPAGATION",
        ),
    ),
)
MAX_OUTPUT_BYTES = 1_048_576
COMMAND_TIMEOUT_SECONDS = 30


class IdentityError(RuntimeError):
    """Fail-closed P4-R-I contract violation."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise IdentityError("timestamp is not an exact UTC second")
    return parsed


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_regular(path: pathlib.Path, *, mode: int | None = None) -> os.stat_result:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise IdentityError(f"required input is not a regular non-symlink file: {path}")
    if mode is not None and stat.S_IMODE(metadata.st_mode) != mode:
        raise IdentityError(f"required input mode mismatch: {path}")
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


def direct_run(
    argv: list[str], *, input_bytes: bytes | None = None, timeout: int = 30
) -> subprocess.CompletedProcess[bytes]:
    options: dict[str, Any] = {
        "check": False,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "timeout": timeout,
        "env": {
            "HOME": "/home/omaltsev",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin",
            "TZ": "UTC",
        },
    }
    if input_bytes is None:
        options["stdin"] = subprocess.DEVNULL
    else:
        options["input"] = input_bytes
    return subprocess.run(argv, **options)


def ssh_argv(logical_argv: tuple[str, ...]) -> list[str]:
    if logical_argv not in {item[1] for item in OBSERVATIONS}:
        raise IdentityError("remote argv is not one of the four frozen observations")
    remote_command = " ".join(shlex.quote(item) for item in logical_argv)
    return [
        str(SSH),
        "-F",
        "/dev/null",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={PINNED_HOSTS}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "HostKeyAlgorithms=ssh-ed25519",
        "-o",
        "UpdateHostKeys=no",
        "-o",
        "PubkeyAuthentication=yes",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PreferredAuthentications=publickey",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"IdentityFile={TRANSPORT_PRIVATE}",
        "-o",
        "IdentityAgent=none",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=1",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "LogLevel=ERROR",
        DESTINATION,
        remote_command,
    ]


def expected_authority() -> set[str]:
    return {
        "one_target_sshsig_authorized",
        "four_fixed_read_only_identity_observations_authorized",
        "one_create_exclusive_local_capture_authorized",
        "one_single_owner_public_review_authorized",
        "repository_local_records_tests_and_evidence_authorized",
    }


def verify_signature(
    authorization_bytes: bytes, signature_path: pathlib.Path, signature_hash: str
) -> None:
    require_regular(signature_path)
    if sha256_file(signature_path) != signature_hash:
        raise IdentityError("detached-signature SHA-256 mismatch")
    require_regular(TARGET_ALLOWED_SIGNERS)
    result = direct_run(
        [
            str(SSH_KEYGEN),
            "-Y",
            "verify",
            "-f",
            str(TARGET_ALLOWED_SIGNERS),
            "-I",
            AUTHORIZATION_PRINCIPAL,
            "-n",
            SIGNATURE_NAMESPACE,
            "-s",
            str(signature_path),
        ],
        input_bytes=authorization_bytes,
    )
    if result.returncode != 0:
        raise IdentityError("target SSHSIG verification failed")


def verify_public_fingerprint(path: pathlib.Path, expected: str) -> None:
    result = direct_run([str(SSH_KEYGEN), "-l", "-f", str(path), "-E", "sha256"])
    tokens = result.stdout.decode("utf-8").strip().split()
    if result.returncode != 0 or len(tokens) < 4 or tokens[1] != expected:
        raise IdentityError(f"public fingerprint mismatch: {path.name}")


def verify_authorization(
    authorization_path: pathlib.Path,
    authorization_hash: str,
    signature_path: pathlib.Path,
    signature_hash: str,
    *,
    require_current: bool,
) -> tuple[dict[str, Any], bytes]:
    require_regular(authorization_path)
    raw = authorization_path.read_bytes()
    if sha256_bytes(raw) != authorization_hash:
        raise IdentityError("authorization SHA-256 mismatch")
    record = json.loads(raw)
    if raw != canonical(record):
        raise IdentityError("authorization is not canonical JCS-I64-v1 bytes")
    expected = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-i-d099-authorization/1",
        "decision_id": DECISION_ID,
        "transaction_id": TRANSACTION_ID,
        "artifact_id": ARTIFACT_ID,
        "host": HOST,
        "stand_id": "XEON-CPU-FETCH",
        "signer_fingerprint": SIGNER_FINGERPRINT,
        "pinned_host_key_fingerprint": HOST_FINGERPRINT,
        "transport_public_key_fingerprint": TRANSPORT_FINGERPRINT,
        "capture_artifact_absolute_path": str(ARTIFACT),
        "capture_sidecar_absolute_path": str(SIDECAR),
        "review_artifact_absolute_path": str(REVIEW),
        "review_sidecar_absolute_path": str(REVIEW_SIDECAR),
        "observation_attempts": 1,
        "review_attempts": 1,
        "retry_count": 0,
        "automatic_continuation": False,
        "p4_r_c_or_later_authorized": False,
    }
    if any(record.get(name) != value for name, value in expected.items()):
        raise IdentityError("authorization identity, path, or one-attempt boundary mismatch")
    if record.get("fixed_read_only_observations") != [
        {"id": identifier, "argv": list(argv)} for identifier, argv in OBSERVATIONS
    ]:
        raise IdentityError("four fixed read-only observations drifted")
    issued = parse_utc(str(record.get("issued_at_utc", "")))
    expires = parse_utc(str(record.get("expires_at_utc", "")))
    if int((expires - issued).total_seconds()) != 1800:
        raise IdentityError("authorization validity is not exactly 1,800 seconds")
    if require_current:
        now = datetime.now(UTC).replace(microsecond=0)
        if now < issued or now >= expires:
            raise IdentityError("authorization is expired or premature")
    enabled = {
        name for name, value in record.get("authority_boundary", {}).items() if value is True
    }
    if enabled != expected_authority():
        raise IdentityError("D-099 authority boundary omitted or widened")
    fixed_bindings = (
        ("decision_adr_path", "decision_adr_sha256"),
        ("owner_waiver_path", "owner_waiver_sha256"),
        ("executor_path", "executor_sha256"),
        ("predecessor_template_path", "predecessor_template_sha256"),
        ("d097_complete_evidence_path", "d097_complete_evidence_sha256"),
        ("pinned_hosts_path", "pinned_hosts_sha256"),
        ("transport_public_evidence_path", "transport_public_evidence_sha256"),
    )
    for path_field, hash_field in fixed_bindings:
        path = PROJECT_ROOT / str(record.get(path_field, ""))
        require_regular(path)
        if sha256_file(path) != record.get(hash_field):
            raise IdentityError(f"bound repository input mismatch: {path_field}")
    if record.get("executor_sha256") != sha256_file(pathlib.Path(__file__)):
        raise IdentityError("executor SHA-256 mismatch")
    for path, expected_hash in (
        (TARGET_ALLOWED_SIGNERS, str(record.get("target_allowed_signers_sha256", ""))),
        (TRANSPORT_PUBLIC, str(record.get("transport_public_key_sha256", ""))),
        (SSH, str(record.get("ssh_sha256", ""))),
        (SSH_KEYGEN, str(record.get("ssh_keygen_sha256", ""))),
    ):
        require_regular(path)
        if sha256_file(path) != expected_hash:
            raise IdentityError(f"bound external public/tool input mismatch: {path.name}")
    require_regular(TRANSPORT_PRIVATE, mode=0o600)
    verify_public_fingerprint(PINNED_HOSTS, HOST_FINGERPRINT)
    verify_public_fingerprint(TRANSPORT_PUBLIC, TRANSPORT_FINGERPRINT)
    verify_signature(raw, signature_path, signature_hash)
    return record, raw


def prepare_capture_root() -> None:
    if os.path.lexists(CAPTURE_ROOT):
        raise IdentityError("create-exclusive capture root already exists")
    evidence_root = PROJECT_ROOT / "docs/evidence"
    metadata = os.lstat(evidence_root)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise IdentityError("repository evidence root is unsafe")
    stage17 = evidence_root / "stage17"
    if not os.path.lexists(stage17):
        os.mkdir(stage17, 0o755)
        fsync_directory(evidence_root)
    stage17_metadata = os.lstat(stage17)
    if stat.S_ISLNK(stage17_metadata.st_mode) or not stat.S_ISDIR(stage17_metadata.st_mode):
        raise IdentityError("stage17 evidence parent is unsafe")
    os.mkdir(CAPTURE_ROOT, 0o700)
    fsync_directory(stage17)


def retain_failure(phase: str, authorization_hash: str, completed_ids: list[str]) -> None:
    if not CAPTURE_ROOT.is_dir():
        return
    path = CAPTURE_ROOT / "identity-failure.json"
    if os.path.lexists(path):
        return
    write_exclusive(
        path,
        canonical(
            {
                "authorization_sha256": authorization_hash,
                "automatic_continuation": False,
                "completed_observation_ids": completed_ids,
                "decision_id": DECISION_ID,
                "phase": phase,
                "retry_authorized": False,
                "schema_version": "cpu-prefetch-q15-r-p4-r-i-d099-failure/1",
                "stand_filesystem_mutation_performed": False,
                "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
                "transaction_id": TRANSACTION_ID,
            }
        ),
    )
    fsync_directory(CAPTURE_ROOT)


def capture(
    authorization_path: pathlib.Path,
    authorization_hash: str,
    signature_path: pathlib.Path,
    signature_hash: str,
    *,
    runner: Callable[[list[str]], subprocess.CompletedProcess[bytes]] | None = None,
) -> int:
    phase = "PREFLIGHT"
    completed_ids: list[str] = []
    try:
        authorization, _ = verify_authorization(
            authorization_path,
            authorization_hash,
            signature_path,
            signature_hash,
            require_current=True,
        )
        prepare_capture_root()
        phase = "READ_ONLY_OBSERVATIONS"
        started_at = utc_now()
        observations: list[dict[str, Any]] = []
        execute = runner or (lambda argv: direct_run(argv, timeout=COMMAND_TIMEOUT_SECONDS))
        for identifier, logical_argv in OBSERVATIONS:
            result = execute(ssh_argv(logical_argv))
            if len(result.stdout) > MAX_OUTPUT_BYTES or len(result.stderr) > MAX_OUTPUT_BYTES:
                raise IdentityError(f"bounded output exceeded: {identifier}")
            if result.returncode != 0:
                raise IdentityError(f"read-only observation failed: {identifier}")
            observations.append(
                {
                    "argv": list(logical_argv),
                    "attempt": 1,
                    "id": identifier,
                    "returncode": result.returncode,
                    "stderr_base64": base64.b64encode(result.stderr).decode("ascii"),
                    "stderr_bytes": len(result.stderr),
                    "stderr_sha256": sha256_bytes(result.stderr),
                    "stdout_base64": base64.b64encode(result.stdout).decode("ascii"),
                    "stdout_bytes": len(result.stdout),
                    "stdout_sha256": sha256_bytes(result.stdout),
                }
            )
            completed_ids.append(identifier)
        completed_at = utc_now()
        issued = parse_utc(str(authorization["issued_at_utc"]))
        expires = parse_utc(str(authorization["expires_at_utc"]))
        if parse_utc(started_at) < issued or parse_utc(completed_at) >= expires:
            raise IdentityError("capture left the exact authorization window")
        artifact = {
            "artifact_id": ARTIFACT_ID,
            "authorization_sha256": authorization_hash,
            "automatic_continuation_to_p4_r_c": False,
            "capture_completed_at_utc": completed_at,
            "capture_started_at_utc": started_at,
            "decision_id": DECISION_ID,
            "host": HOST,
            "observations": observations,
            "pinned_host_key_fingerprint": HOST_FINGERPRINT,
            "protocol_version": "2.0.0-pre.2",
            "read_only": True,
            "retry_count": 0,
            "schema_version": "cpu-prefetch-q15-r-p4-r-i-d099-identity/1",
            "stand_filesystem_mutation_performed": False,
            "stand_id": "XEON-CPU-FETCH",
            "status": "COMPLETE_VALID_READ_ONLY_IDENTITY_STOPPED_FOR_REVIEW",
            "transaction_id": TRANSACTION_ID,
            "transport_account": "root",
            "transport_public_key_fingerprint": TRANSPORT_FINGERPRINT,
        }
        write_exclusive(ARTIFACT, canonical(artifact), 0o644)
        sidecar = f"{sha256_file(ARTIFACT)}  {ARTIFACT.name}\n".encode()
        write_exclusive(SIDECAR, sidecar, 0o644)
        fsync_directory(CAPTURE_ROOT)
        print(
            json.dumps(
                {
                    "artifact_sha256": sha256_file(ARTIFACT),
                    "automatic_continuation": False,
                    "completed_observations": len(observations),
                    "status": artifact["status"],
                    "transaction_id": TRANSACTION_ID,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception as exception:  # noqa: BLE001 - retain terminal partial evidence.
        retain_failure(phase, authorization_hash, completed_ids)
        print(f"execute-d099-p4-r-i: TERMINAL FAILURE: {phase}: {exception}", file=sys.stderr)
        return 1


def validate_capture(record: dict[str, Any], authorization_hash: str) -> None:
    expected = {
        "artifact_id": ARTIFACT_ID,
        "authorization_sha256": authorization_hash,
        "automatic_continuation_to_p4_r_c": False,
        "decision_id": DECISION_ID,
        "host": HOST,
        "pinned_host_key_fingerprint": HOST_FINGERPRINT,
        "read_only": True,
        "retry_count": 0,
        "stand_filesystem_mutation_performed": False,
        "stand_id": "XEON-CPU-FETCH",
        "transaction_id": TRANSACTION_ID,
        "transport_public_key_fingerprint": TRANSPORT_FINGERPRINT,
    }
    if any(record.get(name) != value for name, value in expected.items()):
        raise IdentityError("captured identity metadata mismatch")
    observations = record.get("observations", [])
    if len(observations) != 4:
        raise IdentityError("captured identity does not contain four observations")
    for observed, (identifier, argv) in zip(observations, OBSERVATIONS, strict=True):
        if (
            observed.get("id") != identifier
            or observed.get("argv") != list(argv)
            or observed.get("attempt") != 1
            or observed.get("returncode") != 0
        ):
            raise IdentityError(f"captured observation contract mismatch: {identifier}")
        for prefix in ("stdout", "stderr"):
            raw = base64.b64decode(observed.get(f"{prefix}_base64", ""), validate=True)
            if len(raw) != observed.get(f"{prefix}_bytes") or sha256_bytes(raw) != observed.get(
                f"{prefix}_sha256"
            ):
                raise IdentityError(f"captured {prefix} bytes mismatch: {identifier}")


def validate_observation_semantics(record: dict[str, Any]) -> None:
    outputs = [
        base64.b64decode(item["stdout_base64"], validate=True).decode("utf-8")
        for item in record["observations"]
    ]
    hostname = outputs[0].strip()
    if not hostname or "\n" in hostname or len(hostname.encode("utf-8")) > 255:
        raise IdentityError("hostname observation is malformed")
    uname = outputs[1].strip().split()
    if len(uname) != 3 or uname[0] != "Linux" or uname[2] != "x86_64":
        raise IdentityError("uname observation is not the accepted Linux x86-64 shape")
    stat_lines = outputs[2].splitlines()
    if len(stat_lines) != 3 or any(
        not line.startswith(f"{expected}|")
        for line, expected in zip(stat_lines, ("/", "/root", "/dev/md3"), strict=True)
    ):
        raise IdentityError("stat observation does not cover /, /root, and /dev/md3 exactly")
    try:
        findmnt = json.loads(outputs[3])
    except json.JSONDecodeError as exception:
        raise IdentityError("findmnt observation is not JSON") from exception
    filesystems = findmnt.get("filesystems", [])
    if not isinstance(filesystems, list) or not any(
        isinstance(item, dict) and item.get("target") == "/" for item in filesystems
    ):
        raise IdentityError("findmnt observation does not identify the root mount")


def review(
    authorization_path: pathlib.Path,
    authorization_hash: str,
    signature_path: pathlib.Path,
    signature_hash: str,
) -> int:
    try:
        authorization, _ = verify_authorization(
            authorization_path,
            authorization_hash,
            signature_path,
            signature_hash,
            require_current=False,
        )
        for path in (ARTIFACT, SIDECAR):
            require_regular(path)
        if os.path.lexists(REVIEW) or os.path.lexists(REVIEW_SIDECAR):
            raise IdentityError("create-exclusive owner-review output already exists")
        expected_sidecar = f"{sha256_file(ARTIFACT)}  {ARTIFACT.name}\n"
        if SIDECAR.read_text(encoding="ascii") != expected_sidecar:
            raise IdentityError("identity sidecar mismatch")
        artifact_bytes = ARTIFACT.read_bytes()
        artifact = json.loads(artifact_bytes)
        if artifact_bytes != canonical(artifact):
            raise IdentityError("identity artifact is not canonical")
        validate_capture(artifact, authorization_hash)
        validate_observation_semantics(artifact)
        issued = parse_utc(str(authorization["issued_at_utc"]))
        expires = parse_utc(str(authorization["expires_at_utc"]))
        if (
            parse_utc(str(artifact["capture_started_at_utc"])) < issued
            or parse_utc(str(artifact["capture_completed_at_utc"])) >= expires
        ):
            raise IdentityError("captured identity is outside the authorization window")
        review_record = {
            "artifact_sha256": sha256_file(ARTIFACT),
            "authorization_sha256": authorization_hash,
            "automatic_continuation": False,
            "decision_id": DECISION_ID,
            "distinct_reviewer": False,
            "owner_waiver_status": "ACCEPTED_SINGLE_OWNER_P4_R_I_WAIVER",
            "p4_r_c_authorized": False,
            "protocol_version": "2.0.0-pre.2",
            "review_attempt": 1,
            "review_principal": "cpu-prefetch-q15-auditor",
            "reviewed_at_utc": utc_now(),
            "schema_version": "cpu-prefetch-q15-r-p4-r-i-d099-owner-review/1",
            "sidecar_sha256": sha256_file(SIDECAR),
            "signature_sha256": signature_hash,
            "stand_access_performed_during_review": False,
            "status": "ACCEPTED_SINGLE_OWNER_PUBLIC_REVIEW_STOPPED_BEFORE_P4_R_C",
            "transaction_id": TRANSACTION_ID,
        }
        write_exclusive(REVIEW, canonical(review_record), 0o644)
        write_exclusive(
            REVIEW_SIDECAR,
            f"{sha256_file(REVIEW)}  {REVIEW.name}\n".encode(),
            0o644,
        )
        manifest_paths = (ARTIFACT, SIDECAR, REVIEW, REVIEW_SIDECAR)
        manifest = "".join(f"{sha256_file(path)}  {path.name}\n" for path in manifest_paths).encode()
        write_exclusive(CAPTURE_ROOT / "SHA256SUMS", manifest, 0o644)
        fsync_directory(CAPTURE_ROOT)
        print(
            json.dumps(
                {
                    "artifact_sha256": review_record["artifact_sha256"],
                    "automatic_continuation": False,
                    "review_sha256": sha256_file(REVIEW),
                    "status": review_record["status"],
                    "transaction_id": TRANSACTION_ID,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except Exception as exception:  # noqa: BLE001 - review failure is terminal.
        print(f"execute-d099-p4-r-i: REVIEW FAILURE: {exception}", file=sys.stderr)
        return 1


def self_test() -> int:
    stat_argv = OBSERVATIONS[2][1]
    rendered = ssh_argv(stat_argv)
    if rendered[-1] != "/usr/bin/stat '--format=%n|%F|%a|%u|%g|%s|%d|%i' -- / /root /dev/md3":
        raise IdentityError("static remote shell quotation known answer failed")
    if rendered.count("ConnectionAttempts=1") != 1 or "StrictHostKeyChecking=yes" not in rendered:
        raise IdentityError("fixed SSH fail-closed options missing")
    try:
        ssh_argv(("/bin/true",))
    except IdentityError:
        pass
    else:
        raise IdentityError("unregistered remote argv was accepted")
    synthetic = {
        "artifact_id": ARTIFACT_ID,
        "authorization_sha256": "a" * 64,
        "automatic_continuation_to_p4_r_c": False,
        "decision_id": DECISION_ID,
        "host": HOST,
        "observations": [],
        "pinned_host_key_fingerprint": HOST_FINGERPRINT,
        "read_only": True,
        "retry_count": 0,
        "stand_filesystem_mutation_performed": False,
        "stand_id": "XEON-CPU-FETCH",
        "transaction_id": TRANSACTION_ID,
        "transport_public_key_fingerprint": TRANSPORT_FINGERPRINT,
    }
    synthetic_outputs = (
        b"stand-host\n",
        b"Linux 7.0.0-test x86_64\n",
        b"/|directory|755|0|0|4096|1|2\n/root|directory|700|0|0|4096|1|3\n/dev/md3|block special file|660|0|6|0|2|4\n",
        b'{"filesystems":[{"target":"/","source":"/dev/md3","fstype":"ext4"}]}\n',
    )
    for (identifier, argv), stdout in zip(OBSERVATIONS, synthetic_outputs, strict=True):
        synthetic["observations"].append(
            {
                "argv": list(argv),
                "attempt": 1,
                "id": identifier,
                "returncode": 0,
                "stderr_base64": "",
                "stderr_bytes": 0,
                "stderr_sha256": sha256_bytes(b""),
                "stdout_base64": base64.b64encode(stdout).decode(),
                "stdout_bytes": len(stdout),
                "stdout_sha256": sha256_bytes(stdout),
            }
        )
    validate_capture(synthetic, "a" * 64)
    validate_observation_semantics(synthetic)
    synthetic["observations"][1]["stdout_sha256"] = "0" * 64
    try:
        validate_capture(synthetic, "a" * 64)
    except IdentityError:
        pass
    else:
        raise IdentityError("corrupt captured bytes were accepted")
    with tempfile.TemporaryDirectory(prefix="d099-self-test-"):
        pass
    print("execute-d099-p4-r-i: SELF-TEST PASS (fixed argv/options + corruption rejection)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--capture", action="store_true")
    mode.add_argument("--review", action="store_true")
    parser.add_argument("--authorization", type=pathlib.Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--signature", type=pathlib.Path)
    parser.add_argument("--signature-sha256")
    arguments = parser.parse_args()
    if arguments.self_test:
        return self_test()
    if any(
        value is None
        for value in (
            arguments.authorization,
            arguments.authorization_sha256,
            arguments.signature,
            arguments.signature_sha256,
        )
    ):
        parser.error("capture/review requires exact authorization and signature arguments")
    if arguments.capture:
        return capture(
            arguments.authorization,
            arguments.authorization_sha256,
            arguments.signature,
            arguments.signature_sha256,
        )
    return review(
        arguments.authorization,
        arguments.authorization_sha256,
        arguments.signature,
        arguments.signature_sha256,
    )


if __name__ == "__main__":
    raise SystemExit(main())
