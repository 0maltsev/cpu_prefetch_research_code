#!/usr/bin/env python3
"""Linux parent-procfd OpenSSH snapshot broker for Stage 17, completing
`v4`'s incomplete re-export surface (ADR-0133).

This is a new, additive file. It does not modify `stage17_openssh_parent_
snapshot_v4.py`'s bytes, so any already-accepted-adjacent closure hash
for that file remains valid and unchanged.

Root cause (ADR-0133, confirmed by a real `AttributeError` on the
owner's real machine, not assumed): when `v4.py` was written for
ADR-0132, `validate_identity_parseability`, `verify_snapshot`, and
`close_snapshots` were correctly re-exported from `v3.py`, but `verify_
local_openssh_parent_procfd_capability` -- a fourth function `v3.py`
defines directly, rather than re-exporting, since its body constructs
`supervisor.SupervisorLease()` and needed its own copy when `v3` was
written for ADR-0131 -- was omitted entirely. This module fixes exactly
that omission: `verify_local_openssh_parent_procfd_capability` is a
deliberate alias of `v3`'s function, not a fresh copy, because its body
sets `result["mechanism"]` to a hardcoded literal
(`"LINUX_PARENT_PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2"`), never reading
`MECHANISM` or any other free variable that varies between `v3` and `v4`
-- so it is unaffected by ADR-0132's change and safe to re-export
unchanged. Every other name is re-exported unchanged from `v4`.
"""

from __future__ import annotations

import stage17_openssh_parent_snapshot_v3 as immediate_predecessor_v3
import stage17_openssh_parent_snapshot_v4 as predecessor


MECHANISM = predecessor.MECHANISM
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

validate_identity_parseability = predecessor.validate_identity_parseability
verify_snapshot = predecessor.verify_snapshot
close_snapshots = predecessor.close_snapshots
pin_bound_input = predecessor.pin_bound_input

verify_local_openssh_parent_procfd_capability = (
    immediate_predecessor_v3.verify_local_openssh_parent_procfd_capability
)
