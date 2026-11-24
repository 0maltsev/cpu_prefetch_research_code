#!/usr/bin/env python3
"""Linux parent-procfd OpenSSH snapshot broker for Stage 17, reporting the
real, currently active capability-layer mechanism identity on each pinned
input's own metadata (ADR-0132).

This is a new, additive file. It does not modify `stage17_openssh_parent_
snapshot_v3.py`'s bytes, so any already-accepted-adjacent closure hash for
that file remains valid and unchanged.

Root cause (ADR-0132, confirmed against the real attempt-marker schema,
not assumed): `pin_bound_input` in `stage17_openssh_parent_snapshot_v1.py`
hardcodes each pinned input's own `metadata["snapshot_mechanism"]` to the
module-level constant `MECHANISM = "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1"`.
`v2`/`v3` re-export this function unchanged, so every version through `v3`
still emits the `v1` identity regardless of which capability-proof wrapper
is actually in use. The attempt-marker schema was bumped at `v9` (still
in effect at the currently active `v10`) to require the `v2` identity for
this same field, consistently with `openssh_consumption_capability.
mechanism` and `process_supervisor_capability.mechanism`, both of which
already correctly report `v2` identities -- the corresponding code change
to `pin_bound_input` was simply never made.

`pin_bound_input` here is therefore a faithful copy of `v1`'s
implementation -- not an alias -- because its body reads `MECHANISM` as a
bare name resolved against whichever module it is *defined* in (the same
free-variable-resolves-via-defining-module lesson ADR-0126 already
recorded): aliasing `v1`'s function here would still emit `v1`'s own
`MECHANISM` value. Every other check (ownership/permission verification,
size/hash reverification, sealed-memfd creation and seal verification,
procfs locator construction) is byte-identical to `v1`'s.
`verify_snapshot`, `validate_identity_parseability`, `close_snapshots`,
and every helper function never read `MECHANISM`, so they are re-exported
unchanged.
"""

from __future__ import annotations

import fcntl
import os
import pathlib
import stat
from typing import Any

import stage17_openssh_parent_snapshot_v3 as immediate_predecessor
import stage17_openssh_parent_snapshot_v1 as predecessor


MECHANISM = "LINUX_PARENT_PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2"

SnapshotError = predecessor.SnapshotError
ProcfsIdentity = predecessor.ProcfsIdentity
ParentSnapshot = predecessor.ParentSnapshot
sha256_bytes = predecessor.sha256_bytes
sha256_file = predecessor.sha256_file
REQUIRED_SEAL_NAMES = predecessor.REQUIRED_SEAL_NAMES
discover_procfs_identity = predecessor.discover_procfs_identity
_read_exact = predecessor._read_exact
_write_all = predecessor._write_all
_verify_locator = predecessor._verify_locator
_seal_mask = predecessor._seal_mask

validate_identity_parseability = immediate_predecessor.validate_identity_parseability
verify_snapshot = immediate_predecessor.verify_snapshot
close_snapshots = immediate_predecessor.close_snapshots


def pin_bound_input(
    binding: dict[str, Any],
    role: str,
    *,
    proc_root: pathlib.Path = pathlib.Path("/proc"),
) -> ParentSnapshot:
    """Faithful copy of predecessor `pin_bound_input`, retargeted at this
    module's own `MECHANISM`. Every other check is byte-identical to `v1`.
    """

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
