#!/usr/bin/env python3
"""PID-namespace-safe held-leader/subreaper lifecycle proof for Stage 17,
tolerating kernel threads during a full `/proc` scan (ADR-0131).

ADR-0209 also classifies ESRCH from the status/namespace/stat reads as a
vanished scan candidate, like ENOENT. Required identities and owned-child
ambiguity still fail in the inherited callers; other read errors propagate.

This is a new, additive file. It does not modify `stage17_process_group_
supervisor_v2.py`'s bytes, so any already-accepted closure hash for that
file remains valid and unchanged.

Root cause (ADR-0131, confirmed against real evidence, not assumed):
`ProcfsIdentityModel._identity_at` in `v2` only tolerates a process
vanishing mid-scan (`FileNotFoundError`); it does not tolerate a process
that legitimately exists but reports `NSpgid: 0` in `/proc/<pid>/status`
-- which every kernel thread does, correctly, since a kernel thread
structurally cannot belong to any process group. `process_group_members`
(the one caller that walks the *entire* `/proc` tree, as opposed to
`direct_children`, which only walks the calling process's own
kernel-reported children) already treats a `None` return from
`_identity_at` as "not a match, skip" -- so the only change needed is
making `_identity_at` return `None` for this one case instead of letting
`_parse_integer_vector`'s `SupervisorError("empty or nonpositive
NSpgid")` propagate uncaught.

`ProcfsIdentityModel` here is therefore a subclass overriding only
`_identity_at`; `direct_children`, `process_group_members`,
`identity_for_local_pid`, and `verify_stable` are inherited unchanged and
correctly dispatch to the override polymorphically (all call `self.
_identity_at(...)`, never the base class explicitly). `SupervisorLease`
must be a subclass too, overriding only `enter`, because its body
constructs `ProcfsIdentityModel()` as a bare name resolved against
whichever module *defines* `enter` -- the same free-variable-resolves-via-
defining-module lesson ADR-0126 already recorded, so importing `v2`'s
`SupervisorLease` unchanged would still construct `v2`'s own, unfixed
model. `verify_supervisor_capability` is a fresh copy for the same
reason. `_direct_children_fail_stop`, `_process_group_members_fail_stop`,
`_reap_owned_nonleader`, `_waitpid_leader_fail_stop`, and
`cleanup_process_group` are all re-exported unchanged: each already takes
its `ProcfsIdentityModel` *instance* as an explicit parameter rather than
constructing one internally, so passing this module's fixed model (via
this module's own `SupervisorLease`) is sufficient -- no fresh copy is
needed for functions that never hardcode which class to instantiate.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import stage17_process_group_supervisor_v2 as predecessor


SupervisorError = predecessor.SupervisorError
ProcessIdentity = predecessor.ProcessIdentity
NamespaceSnapshot = predecessor.NamespaceSnapshot
CleanupResult = predecessor.CleanupResult

_prctl_get_subreaper = predecessor._prctl_get_subreaper
_prctl_set_subreaper = predecessor._prctl_set_subreaper
_parse_integer_vector = predecessor._parse_integer_vector
_namespace_inode = predecessor._namespace_inode
_status_fields = predecessor._status_fields
_start_time_ticks = predecessor._start_time_ticks
_peek_leader_exit_held = predecessor._peek_leader_exit_held
_send_group = predecessor._send_group
_send_owned_pid = predecessor._send_owned_pid
_direct_children_fail_stop = predecessor._direct_children_fail_stop
_process_group_members_fail_stop = predecessor._process_group_members_fail_stop
_reap_owned_nonleader = predecessor._reap_owned_nonleader
_waitpid_leader_fail_stop = predecessor._waitpid_leader_fail_stop
cleanup_process_group = predecessor.cleanup_process_group

_SUPERVISOR_LOCK = predecessor._SUPERVISOR_LOCK


class ProcfsIdentityModel(predecessor.ProcfsIdentityModel):
    """Faithful copy of predecessor `_identity_at`, tolerating a kernel
    thread's `NSpgid: 0` as "not a process-group member" instead of
    letting the underlying `SupervisorError` propagate. Every other check
    remains unchanged except for the ADR-0209 disappearance classification;
    `_capture_self` (used for the
    calling process's own identity, which is never a kernel thread) is
    unchanged and inherited as-is.
    """

    def _identity_at(self, visible_pid: int) -> predecessor.ProcessIdentity | None:
        root = self.proc_root / str(visible_pid)
        try:
            fields = _status_fields(root / "status")
            namespace_inode = _namespace_inode(root / "ns/pid")
            start_time = _start_time_ticks(root / "stat")
        except SupervisorError as exception:
            if isinstance(exception.__cause__, (FileNotFoundError, ProcessLookupError)):
                return None
            raise
        if namespace_inode != self.snapshot.namespace_inode:
            return None
        nspid = _parse_integer_vector(fields.get("NSpid", ""), "NSpid")
        try:
            nspgid = _parse_integer_vector(fields.get("NSpgid", ""), "NSpgid")
        except SupervisorError as exception:
            if str(exception) == "empty or nonpositive NSpgid":
                return None
            raise
        try:
            status_pid = int(fields.get("Pid", "0"))
        except ValueError as exception:
            raise SupervisorError("malformed status PID") from exception
        if status_pid != visible_pid or nspid[0] != visible_pid:
            raise SupervisorError("procfs-visible PID mapping mismatch")
        return predecessor.ProcessIdentity(
            nspid[-1], nspgid[-1], visible_pid, nspgid[0], namespace_inode,
            nspid, nspgid, start_time,
        )


class SupervisorLease(predecessor.SupervisorLease):
    """Faithful copy of predecessor `enter`, constructing this module's own
    fixed `ProcfsIdentityModel` instead of `v2`'s. `close` is inherited
    unchanged: it only clears `self.identity_model` and restores subreaper
    state, neither of which depends on which `ProcfsIdentityModel` class
    was used.
    """

    def enter(self) -> None:
        _SUPERVISOR_LOCK.acquire()
        self._locked = True
        try:
            self.identity_model = ProcfsIdentityModel()
            if self.identity_model.direct_children():
                raise SupervisorError("executor already owns a child before transport")
            self._original = _prctl_get_subreaper()
            _prctl_set_subreaper(1)
            if _prctl_get_subreaper() != 1:
                raise SupervisorError("subreaper readback mismatch")
            self._active = True
        except BaseException:
            self.close(suppress=True)
            raise


def verify_supervisor_capability() -> dict[str, Any]:
    """Faithful copy of predecessor `verify_supervisor_capability`,
    retargeted at this module's own fixed `ProcfsIdentityModel`. Every
    check is identical; only the module-level binding this function
    resolves against differs, for the same reason `SupervisorLease.enter`
    above needed its own copy.
    """
    if sys.platform != "linux":
        raise SupervisorError("Linux is required for process-group supervision")
    if not hasattr(os, "waitid") or not hasattr(os, "WNOWAIT"):
        raise SupervisorError("waitid WNOWAIT is unavailable")
    model = ProcfsIdentityModel()
    model.verify_stable()
    current = _prctl_get_subreaper()
    model.process_group_members(model.snapshot.local_pgid)
    model.direct_children()
    return {
        "mechanism": "LINUX_SUBREAPER_NSPID_NSPGID_HELD_LEADER-v2",
        "namespace_local_executor_pid": model.snapshot.local_pid,
        "namespace_local_executor_pgid": model.snapshot.local_pgid,
        "procfs_visible_executor_pid": model.snapshot.visible_pid,
        "procfs_visible_executor_pgid": model.snapshot.visible_pgid,
        "pid_namespace_inode": model.snapshot.namespace_inode,
        "procfs_pid_namespace_inode": model.snapshot.procfs_namespace_inode,
        "nspid": list(model.snapshot.nspid),
        "nspgid": list(model.snapshot.nspgid),
        "mapping_unambiguous": True,
        "waitid_wnowait_available": True,
        "subreaper_state_readable": True,
        "initial_subreaper_state": current,
        "signal_after_leader_reap_allowed": False,
        "result": "PASS",
    }
