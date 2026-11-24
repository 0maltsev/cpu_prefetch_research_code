#!/usr/bin/env python3
"""Quiescent OpenSSH parent-procfd snapshot capability successor.

The v1 capability fixture proves exact-byte consumption, but a process acting
as PID 1 can adopt the fixture's short-lived sshd descendants after the
fixture leader has returned.  This module runs the unchanged v1 proof while
the caller is a subreaper and establishes a complete child-reap barrier before
returning.  It is used only before the durable one-shot marker.
"""

from __future__ import annotations

import errno
import os
import signal
import time
from typing import Any

import stage17_openssh_parent_snapshot_v1 as predecessor
import stage17_process_group_supervisor_v2 as supervisor


ParentSnapshot = predecessor.ParentSnapshot
SnapshotError = predecessor.SnapshotError
pin_bound_input = predecessor.pin_bound_input
validate_identity_parseability = predecessor.validate_identity_parseability
verify_snapshot = predecessor.verify_snapshot
close_snapshots = predecessor.close_snapshots

QUIESCE_TIMEOUT_NS = 5_000_000_000
POLL_NS = 10_000_000


def _reap_nonblocking() -> int:
    reaped = 0
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return reaped
        except InterruptedError:
            continue
        if pid == 0:
            return reaped
        reaped += 1


def _direct_children(lease: supervisor.SupervisorLease) -> tuple[int, ...]:
    model = lease.identity_model
    if model is None:
        raise SnapshotError("OpenSSH capability subreaper identity is absent")
    try:
        return tuple(sorted(model.direct_children()))
    except BaseException as exception:
        raise SnapshotError("OpenSSH capability child inventory failed") from exception


def _signal_children(children: tuple[int, ...], requested: signal.Signals) -> None:
    for child in children:
        try:
            os.kill(child, requested)
        except ProcessLookupError:
            continue
        except OSError as exception:
            if exception.errno != errno.ESRCH:
                raise SnapshotError("OpenSSH capability child termination failed") \
                    from exception


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
