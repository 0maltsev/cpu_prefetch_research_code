#!/usr/bin/env python3
"""Linux parent-procfd OpenSSH snapshot broker for Stage 17.

The broker keeps sealed memfds alive in the executor. OpenSSH receives only
``/proc/<procfs-visible-parent>/fd/N`` pathnames and inherits no credential fd.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import pwd
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any


MECHANISM = "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1"
SSH_PATH = pathlib.Path("/usr/bin/ssh")
SSHD_PATH = pathlib.Path("/usr/sbin/sshd")
SSH_KEYGEN_PATH = pathlib.Path("/usr/bin/ssh-keygen")
REQUIRED_SEAL_NAMES = (
    "F_SEAL_WRITE",
    "F_SEAL_GROW",
    "F_SEAL_SHRINK",
    "F_SEAL_SEAL",
)
MAX_INPUT_BYTES = 16 * 1024 * 1024
CAPABILITY_TIMEOUT_SECONDS = 15


class SnapshotError(RuntimeError):
    """A credential snapshot or local OpenSSH capability failed closed."""


@dataclass(frozen=True)
class ProcfsIdentity:
    visible_pid: int
    process_directory_device: int
    process_directory_inode: int
    process_directory_uid: int


@dataclass(frozen=True)
class ParentSnapshot:
    role: str
    descriptor: int
    locator: str
    metadata: dict[str, Any]

    def close(self) -> None:
        try:
            os.close(self.descriptor)
        except OSError:
            pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_bytes(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _seal_mask() -> int:
    try:
        return sum(int(getattr(fcntl, name)) for name in REQUIRED_SEAL_NAMES)
    except AttributeError as error:
        raise SnapshotError("Linux memfd sealing constants are unavailable") from error


def discover_procfs_identity(proc_root: pathlib.Path = pathlib.Path("/proc")) -> ProcfsIdentity:
    """Discover this process's PID as represented by the mounted procfs."""

    self_path = proc_root / "self"
    try:
        target = os.readlink(self_path)
    except OSError as error:
        raise SnapshotError("procfs /proc/self is unavailable or denied") from error
    candidate = pathlib.PurePosixPath(target).name
    if not candidate.isascii() or not candidate.isdigit() or int(candidate) < 1:
        raise SnapshotError("procfs /proc/self does not expose a numeric process ID")
    visible_pid = int(candidate)
    process_path = proc_root / candidate
    try:
        self_metadata = os.stat(self_path)
        process_metadata = os.stat(process_path)
        fd_metadata = os.stat(process_path / "fd")
    except OSError as error:
        raise SnapshotError("procfs process/fd identity is unavailable or denied") from error
    if (
        self_metadata.st_dev != process_metadata.st_dev
        or self_metadata.st_ino != process_metadata.st_ino
        or not stat.S_ISDIR(process_metadata.st_mode)
        or not stat.S_ISDIR(fd_metadata.st_mode)
        or process_metadata.st_uid != os.geteuid()
    ):
        raise SnapshotError("procfs-visible process identity is inconsistent")
    return ProcfsIdentity(
        visible_pid=visible_pid,
        process_directory_device=process_metadata.st_dev,
        process_directory_inode=process_metadata.st_ino,
        process_directory_uid=process_metadata.st_uid,
    )


def _read_exact(descriptor: int, expected_size: int) -> bytes:
    if expected_size < 1 or expected_size > MAX_INPUT_BYTES:
        raise SnapshotError("snapshot input size is outside the fixed safety bound")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = expected_size + 1
    while remaining:
        chunk = os.read(descriptor, min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    payload = b"".join(chunks)
    if len(payload) != expected_size:
        raise SnapshotError("snapshot source byte count changed during read")
    return payload


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        count = os.write(descriptor, view)
        if count <= 0:
            raise SnapshotError("snapshot write made no progress")
        view = view[count:]


def _verify_locator(
    snapshot_fd: int,
    locator: pathlib.Path,
    expected_payload: bytes,
    expected_sha256: str,
) -> None:
    reopened: int | None = None
    try:
        reopened = os.open(locator, os.O_RDONLY | os.O_CLOEXEC)
        source_metadata = os.fstat(snapshot_fd)
        reopened_metadata = os.fstat(reopened)
        if (
            not stat.S_ISREG(reopened_metadata.st_mode)
            or reopened_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(reopened_metadata.st_mode) != 0o600
            or reopened_metadata.st_dev != source_metadata.st_dev
            or reopened_metadata.st_ino != source_metadata.st_ino
            or reopened_metadata.st_size != len(expected_payload)
        ):
            raise SnapshotError("parent procfd locator identity is inconsistent")
        seals = int(fcntl.fcntl(reopened, fcntl.F_GET_SEALS))
        mask = _seal_mask()
        if seals & mask != mask:
            raise SnapshotError("parent procfd locator does not expose all required seals")
        observed = os.pread(reopened, len(expected_payload) + 1, 0)
        if observed != expected_payload or sha256_bytes(observed) != expected_sha256:
            raise SnapshotError("parent procfd locator bytes or SHA-256 mismatch")
    except OSError as error:
        raise SnapshotError("parent procfd locator is unavailable or denied") from error
    finally:
        if reopened is not None:
            os.close(reopened)


def pin_bound_input(
    binding: dict[str, Any],
    role: str,
    *,
    proc_root: pathlib.Path = pathlib.Path("/proc"),
) -> ParentSnapshot:
    """Copy one exact owner binding into a sealed parent-held memfd."""

    if set(binding) != {"locator", "size_bytes", "sha256"}:
        raise SnapshotError(f"{role} binding is incomplete")
    source_path = pathlib.Path(binding["locator"])
    source_fd: int | None = None
    snapshot_fd: int | None = None
    try:
        source_fd = os.open(
            source_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        source_metadata = os.fstat(source_fd)
        if not stat.S_ISREG(source_metadata.st_mode):
            raise SnapshotError(f"{role} source is not a regular file")
        if role == "TRANSPORT_IDENTITY" and (
            source_metadata.st_uid != os.geteuid()
            or stat.S_IMODE(source_metadata.st_mode) & 0o077
        ):
            raise SnapshotError("transport identity ownership or permissions are unsafe")
        if source_metadata.st_size != binding["size_bytes"]:
            raise SnapshotError(f"{role} source size changed before snapshotting")
        payload = _read_exact(source_fd, int(binding["size_bytes"]))
        digest = sha256_bytes(payload)
        if digest != binding["sha256"]:
            raise SnapshotError(f"{role} source SHA-256 changed before snapshotting")
        if not hasattr(os, "memfd_create"):
            raise SnapshotError("Linux memfd_create is unavailable")
        snapshot_fd = os.memfd_create(
            f"cpu-prefetch-stage17-{role.lower()}",
            int(getattr(os, "MFD_CLOEXEC", 0x0001))
            | int(getattr(os, "MFD_ALLOW_SEALING", 0x0002)),
        )
        os.fchmod(snapshot_fd, 0o600)
        _write_all(snapshot_fd, payload)
        mask = _seal_mask()
        fcntl.fcntl(snapshot_fd, fcntl.F_ADD_SEALS, mask)
        actual_seals = int(fcntl.fcntl(snapshot_fd, fcntl.F_GET_SEALS))
        if actual_seals & mask != mask:
            raise SnapshotError(f"{role} snapshot sealing is incomplete")
        procfs = discover_procfs_identity(proc_root)
        locator = proc_root / str(procfs.visible_pid) / "fd" / str(snapshot_fd)
        _verify_locator(snapshot_fd, locator, payload, digest)
        result = ParentSnapshot(
            role=role,
            descriptor=snapshot_fd,
            locator=str(locator),
            metadata={
                "role": role,
                "source_size_bytes": len(payload),
                "consumed_sha256": digest,
                "snapshot_size_bytes": len(payload),
                "snapshot_mechanism": MECHANISM,
                "verified_seals": list(REQUIRED_SEAL_NAMES),
                "procfs_visible_parent_pid": procfs.visible_pid,
                "procfs_process_directory_device": procfs.process_directory_device,
                "procfs_process_directory_inode": procfs.process_directory_inode,
                "procfs_process_directory_uid": procfs.process_directory_uid,
                "credential_fd_inherited_by_child": False,
                "source_path_reused_after_marker": False,
                "private_bytes_recorded": False,
            },
        )
        snapshot_fd = None
        return result
    except OSError as error:
        raise SnapshotError(f"{role} snapshot creation failed") from error
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if snapshot_fd is not None:
            os.close(snapshot_fd)


def verify_snapshot(snapshot: ParentSnapshot) -> None:
    """Reverify a live snapshot without consulting its owner source path."""

    expected_size = int(snapshot.metadata["snapshot_size_bytes"])
    payload = os.pread(snapshot.descriptor, expected_size + 1, 0)
    _verify_locator(
        snapshot.descriptor,
        pathlib.Path(snapshot.locator),
        payload,
        str(snapshot.metadata["consumed_sha256"]),
    )


def validate_identity_parseability(snapshot: ParentSnapshot) -> dict[str, Any]:
    """Require the exact identity snapshot to parse without recording key bytes."""

    if snapshot.role != "TRANSPORT_IDENTITY":
        raise SnapshotError("identity parseability received the wrong snapshot role")
    try:
        result = subprocess.run(
            [str(SSH_KEYGEN_PATH), "-y", "-f", snapshot.locator],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("transport identity parseability check failed") from error
    public = result.stdout.strip()
    if result.returncode != 0 or not public.startswith(b"ssh-ed25519 "):
        raise SnapshotError("transport identity is not a usable unencrypted Ed25519 key")
    return {
        "algorithm": "ssh-ed25519",
        "public_key_sha256": sha256_bytes(public),
        "private_bytes_recorded": False,
    }


def _run_fixed(
    argv: list[str], *, timeout: int = CAPABILITY_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            argv,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            close_fds=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SnapshotError("local OpenSSH capability process failed") from error


def verify_local_openssh_parent_procfd_capability() -> dict[str, Any]:
    """Use real local OpenSSH/sshd pipes to prove snapshot consumption."""

    for path in (SSH_PATH, SSHD_PATH, SSH_KEYGEN_PATH):
        try:
            metadata = path.stat()
        except OSError as error:
            raise SnapshotError(f"required local OpenSSH tool is unavailable: {path}") from error
        if not stat.S_ISREG(metadata.st_mode) or not os.access(path, os.X_OK):
            raise SnapshotError(f"required local OpenSSH tool is not executable: {path}")
    procfs = discover_procfs_identity()
    with tempfile.TemporaryDirectory(
        prefix="stage17-openssh-parent-procfd-"
    ) as temporary, contextlib.ExitStack() as snapshot_stack:
        root = pathlib.Path(temporary)
        root.chmod(0o700)
        host_key = root / "synthetic-host-ed25519"
        client_key = root / "synthetic-client-ed25519"
        for key in (host_key, client_key):
            result = _run_fixed(
                [
                    str(SSH_KEYGEN_PATH),
                    "-q",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-f",
                    str(key),
                ]
            )
            if result.returncode != 0:
                raise SnapshotError("disposable Ed25519 key generation failed")
        authorized_keys = root / "authorized_keys"
        authorized_keys.write_bytes(client_key.with_suffix(".pub").read_bytes())
        authorized_keys.chmod(0o600)
        host_public = host_key.with_suffix(".pub").read_text(encoding="ascii").strip()
        known_hosts = root / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {host_public}\n", encoding="ascii"
        )
        known_hosts.chmod(0o600)
        identity_binding = {
            "locator": str(client_key),
            "size_bytes": client_key.stat().st_size,
            "sha256": sha256_file(client_key),
        }
        known_hosts_binding = {
            "locator": str(known_hosts),
            "size_bytes": known_hosts.stat().st_size,
            "sha256": sha256_file(known_hosts),
        }
        known_hosts_snapshot = pin_bound_input(known_hosts_binding, "KNOWN_HOSTS")
        snapshot_stack.callback(known_hosts_snapshot.close)
        identity_snapshot = pin_bound_input(identity_binding, "TRANSPORT_IDENTITY")
        snapshot_stack.callback(identity_snapshot.close)
        validate_identity_parseability(identity_snapshot)
        known_hosts.write_bytes(b"MUTATED-SOURCE-MUST-NOT-BE-CONSUMED\n")
        client_key.write_bytes(b"MUTATED-SOURCE-MUST-NOT-BE-CONSUMED\n")
        client_key.chmod(0o600)
        user = pwd.getpwuid(os.getuid()).pw_name
        sshd_config = root / "sshd_config"
        sshd_config.write_text(
            "\n".join(
                [
                    f"HostKey {host_key}",
                    f"AuthorizedKeysFile {authorized_keys}",
                    "StrictModes no",
                    "PasswordAuthentication no",
                    "KbdInteractiveAuthentication no",
                    "UsePAM no",
                    "PubkeyAuthentication yes",
                    f"AllowUsers {user}",
                    "LogLevel ERROR",
                    "PidFile none",
                    "Subsystem sftp internal-sftp",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        config_check = _run_fixed(
            [str(SSHD_PATH), "-t", "-f", str(sshd_config)]
        )
        if config_check.returncode != 0:
            raise SnapshotError("disposable local sshd configuration is invalid")
        proxy_command = f"{SSHD_PATH} -i -e -f {sshd_config}"
        command = [
            str(SSH_PATH),
            "-F",
            "/dev/null",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_snapshot.locator}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            "HostKeyAlgorithms=ssh-ed25519",
            "-o",
            "UpdateHostKeys=no",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            f"IdentityFile={identity_snapshot.locator}",
            "-o",
            "IdentityAgent=none",
            "-o",
            "HostKeyAlias=synthetic.invalid",
            "-o",
            f"ProxyCommand={proxy_command}",
            "--",
            f"{user}@synthetic.invalid",
            "/usr/bin/true",
        ]
        acceptance = _run_fixed(command)
        if acceptance.returncode != 0:
            raise SnapshotError(
                "real OpenSSH did not consume both exact parent-procfd snapshots"
            )
        verify_snapshot(known_hosts_snapshot)
        verify_snapshot(identity_snapshot)
        version = _run_fixed([str(SSH_PATH), "-V"], timeout=5)
        version_text = (version.stderr or version.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        report = {
            "mechanism": MECHANISM,
            "result": "PASS",
            "ssh_version": version_text,
            "ssh_sha256": sha256_file(SSH_PATH),
            "sshd_sha256": sha256_file(SSHD_PATH),
            "ssh_keygen_sha256": sha256_file(SSH_KEYGEN_PATH),
            "procfs_visible_parent_pid": procfs.visible_pid,
            "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True,
            "public_key_authentication": True,
            "local_proxy_pipe_only": True,
            "network_used": False,
            "private_bytes_recorded": False,
        }
        report["report_sha256"] = sha256_bytes(canonical_json_bytes(report))
        return report


def close_snapshots(*snapshots: ParentSnapshot | None) -> None:
    for snapshot in snapshots:
        if snapshot is not None:
            snapshot.close()
