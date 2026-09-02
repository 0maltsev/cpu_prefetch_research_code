#!/usr/bin/env python3
"""Quiescent OpenSSH parent-procfd snapshot capability successor rebinding
the process-group supervisor to its kernel-thread-tolerant fix (ADR-0131).

This is a new, additive file. It does not modify `stage17_openssh_parent_
snapshot_v2.py`'s bytes, so any already-accepted closure hash for that
file remains valid and unchanged. `_direct_children`,
`_quiesce_capability_children`, and `verify_local_openssh_parent_procfd_
capability` are faithful copies of `v2`'s same-named functions -- not
aliases -- because each references `supervisor.SupervisorLease`, and a
Python function resolves that free variable against the module it was
*defined* in, not the module it is imported into (the same lesson
ADR-0126 already recorded): aliasing `v2`'s functions here would still
construct `v2`'s own, unfixed `SupervisorLease`/`ProcfsIdentityModel`.
`_reap_nonblocking` and `_signal_children` never reference `supervisor` at
all, so they are re-exported unchanged.
"""

from __future__ import annotations

import os
import signal
import time
from typing import Any

import stage17_openssh_parent_snapshot_v1 as predecessor
import stage17_openssh_parent_snapshot_v2 as immediate_predecessor
import stage17_process_group_supervisor_v3 as supervisor


ParentSnapshot = predecessor.ParentSnapshot
SnapshotError = predecessor.SnapshotError
pin_bound_input = predecessor.pin_bound_input
validate_identity_parseability = predecessor.validate_identity_parseability
verify_snapshot = predecessor.verify_snapshot
close_snapshots = predecessor.close_snapshots

QUIESCE_TIMEOUT_NS = 5_000_000_000
POLL_NS = 10_000_000

_reap_nonblocking = immediate_predecessor._reap_nonblocking
_signal_children = immediate_predecessor._signal_children


def _direct_children(lease: supervisor.SupervisorLease) -> tuple[int, ...]:
    model = lease.identity_model
    if model is None:
        raise SnapshotError("OpenSSH capability subreaper identity is absent")
    try:
        return tuple(sorted(model.direct_children()))
    except BaseException as exception:
        raise SnapshotError("OpenSSH capability child inventory failed") from exception


def _quiesce_capability_children(
    lease: supervisor.SupervisorLease,
) -> dict[str, Any]:
    deadline = time.monotonic_ns() + QUIESCE_TIMEOUT_NS
    term_sent = False
    kill_sent = False
    maximum_children = 0
    reaped = 0
    while True:
        reaped += _reap_nonblocking()
        children = _direct_children(lease)
        maximum_children = max(maximum_children, len(children))
        if not children:
            # A second scan closes the adoption/reap observation boundary.
            time.sleep(POLL_NS / 1_000_000_000)
            reaped += _reap_nonblocking()
            if not _direct_children(lease):
                return {
                    "mechanism": "SUBREAPER_CAPABILITY_CHILD_REAP_BARRIER-v2",
                    "maximum_adopted_children": maximum_children,
                    "reaped_children": reaped,
                    "sigterm_sent": term_sent,
                    "sigkill_sent": kill_sent,
                    "children_remaining": 0,
                    "result": "PASS",
                }
        now = time.monotonic_ns()
        if now >= deadline:
            raise SnapshotError("OpenSSH capability child quiescence timed out")
        if children and not term_sent:
            _signal_children(children, signal.SIGTERM)
            term_sent = True
        elif children and not kill_sent and now + 1_000_000_000 >= deadline:
            _signal_children(children, signal.SIGKILL)
            kill_sent = True
        time.sleep(POLL_NS / 1_000_000_000)


def verify_local_openssh_parent_procfd_capability() -> dict[str, Any]:
    """Prove v1 consumption and reap every fixture descendant before return."""

    lease = supervisor.SupervisorLease()
    entered = False
    primary: BaseException | None = None
    report: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    try:
        lease.enter()
        entered = True
        report = predecessor.verify_local_openssh_parent_procfd_capability()
    except BaseException as exception:
        primary = exception
    finally:
        if entered:
            try:
                cleanup = _quiesce_capability_children(lease)
            except BaseException as exception:
                if primary is None:
                    primary = exception
            try:
                lease.close()
            except BaseException as exception:
                if primary is None:
                    primary = exception
    if primary is not None:
        if isinstance(primary, SnapshotError):
            raise primary
        raise SnapshotError("quiescent OpenSSH capability proof failed") from primary
    if report is None or cleanup is None:
        raise SnapshotError("quiescent OpenSSH capability proof is incomplete")
    result = dict(report)
    result.update({
        "mechanism": "LINUX_PARENT_PROCFD_OPENSSH_SUBREAPER_QUIESCENT-v2",
        "fixture_process_quiescence": cleanup,
        "result": "PASS",
    })
    result.pop("report_sha256", None)
    result["report_sha256"] = predecessor.sha256_bytes(
        predecessor.canonical_json_bytes(result)
    )
    return result
