#!/usr/bin/env python3
"""PID-namespace-safe held-leader/subreaper lifecycle proof for Stage 17."""

from __future__ import annotations

import ctypes
import dataclasses
import errno
import os
import pathlib
import signal
import subprocess
import sys
import threading
import time
from typing import Any


PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37
TERM_GRACE_NS = 500_000_000
KILL_GRACE_NS = 1_000_000_000
POLL_NS = 5_000_000


class SupervisorError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class ProcessIdentity:
    local_pid: int
    local_pgid: int
    visible_pid: int
    visible_pgid: int
    namespace_inode: str
    nspid: tuple[int, ...]
    nspgid: tuple[int, ...]
    start_time_ticks: int


@dataclasses.dataclass(frozen=True)
class NamespaceSnapshot:
    namespace_inode: str
    procfs_namespace_inode: str
    local_pid: int
    local_pgid: int
    visible_pid: int
    visible_pgid: int
    nspid: tuple[int, ...]
    nspgid: tuple[int, ...]


@dataclasses.dataclass(frozen=True)
class CleanupResult:
    returncode: int
    leader_reaped: bool
    process_group_gone: bool
    terminal_cleanup_outcome: str
    descendants_detected_after_leader_exit: bool
    maximum_descendant_count: int
    leader_wait_timed_out: bool
    cleanup_deadline_overrun: bool
    cleanup_diagnostics: tuple[str, ...]
    namespace_snapshot: NamespaceSnapshot | None = None


_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.prctl.restype = ctypes.c_int
_SUPERVISOR_LOCK = threading.Lock()


def _prctl_get_subreaper() -> int:
    value = ctypes.c_int()
    result = _LIBC.prctl(
        PR_GET_CHILD_SUBREAPER, ctypes.byref(value), 0, 0, 0
    )
    if result != 0:
        error = ctypes.get_errno()
        raise SupervisorError(f"PR_GET_CHILD_SUBREAPER failed errno={error}")
    return int(value.value)


def _prctl_set_subreaper(value: int) -> None:
    result = _LIBC.prctl(PR_SET_CHILD_SUBREAPER, int(value), 0, 0, 0)
    if result != 0:
        error = ctypes.get_errno()
        raise SupervisorError(f"PR_SET_CHILD_SUBREAPER failed errno={error}")


def _parse_integer_vector(value: str, label: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(token) for token in value.split())
    except ValueError as exception:
        raise SupervisorError(f"malformed {label}") from exception
    if not parsed or any(item <= 0 for item in parsed):
        raise SupervisorError(f"empty or nonpositive {label}")
    return parsed


def _namespace_inode(path: pathlib.Path) -> str:
    try:
        target = os.readlink(path)
    except OSError as exception:
        raise SupervisorError(f"cannot read PID namespace identity: {exception}") from exception
    if not target.startswith("pid:[") or not target.endswith("]"):
        raise SupervisorError("malformed PID namespace identity")
    value = target[5:-1]
    if not value.isdigit():
        raise SupervisorError("nonnumeric PID namespace inode")
    return value


def _status_fields(path: pathlib.Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exception:
        raise SupervisorError(f"cannot read process status: {exception}") from exception
    result: dict[str, str] = {}
    for line in lines:
        if ":" in line:
            name, value = line.split(":", 1)
            result[name] = value.strip()
    return result


def _start_time_ticks(path: pathlib.Path) -> int:
    try:
        payload = path.read_text(encoding="ascii")
    except OSError as exception:
        raise SupervisorError(f"cannot read process stat: {exception}") from exception
    closing = payload.rfind(") ")
    if closing < 0:
        raise SupervisorError("malformed process stat")
    fields = payload[closing + 2 :].split()
    if len(fields) <= 19:
        raise SupervisorError("short process stat")
    try:
        return int(fields[19])
    except ValueError as exception:
        raise SupervisorError("invalid process start time") from exception


class ProcfsIdentityModel:
    """Map procfs-visible IDs to the namespace-local IDs used by syscalls."""

    def __init__(self, proc_root: pathlib.Path = pathlib.Path("/proc")) -> None:
        self.proc_root = proc_root
        self.snapshot = self._capture_self()

    def _capture_self(self) -> NamespaceSnapshot:
        if not self.proc_root.is_dir():
            raise SupervisorError("procfs root is unavailable")
        fields = _status_fields(self.proc_root / "self/status")
        nspid = _parse_integer_vector(fields.get("NSpid", ""), "NSpid")
        nspgid = _parse_integer_vector(fields.get("NSpgid", ""), "NSpgid")
        try:
            visible_pid = int(os.readlink(self.proc_root / "self"))
            status_pid = int(fields.get("Pid", "0"))
        except (OSError, ValueError) as exception:
            raise SupervisorError("cannot resolve procfs-visible self PID") from exception
        local_pid, local_pgid = os.getpid(), os.getpgrp()
        if (
            visible_pid <= 0 or status_pid != visible_pid
            or nspid[0] != visible_pid or nspid[-1] != local_pid
            or nspgid[-1] != local_pgid
        ):
            raise SupervisorError("ambiguous self NSpid/NSpgid mapping")
        namespace_inode = _namespace_inode(self.proc_root / "self/ns/pid")
        procfs_namespace_inode = _namespace_inode(self.proc_root / "1/ns/pid")
        return NamespaceSnapshot(
            namespace_inode, procfs_namespace_inode, local_pid, local_pgid,
            visible_pid, nspgid[0], nspid, nspgid,
        )

    def verify_stable(self) -> None:
        if self._capture_self() != self.snapshot:
            raise SupervisorError("PID namespace or procfs mapping changed")

    def _identity_at(self, visible_pid: int) -> ProcessIdentity | None:
        root = self.proc_root / str(visible_pid)
        try:
            fields = _status_fields(root / "status")
            namespace_inode = _namespace_inode(root / "ns/pid")
            start_time = _start_time_ticks(root / "stat")
        except SupervisorError as exception:
            if isinstance(exception.__cause__, FileNotFoundError):
                return None
            raise
        if namespace_inode != self.snapshot.namespace_inode:
            return None
        nspid = _parse_integer_vector(fields.get("NSpid", ""), "NSpid")
        nspgid = _parse_integer_vector(fields.get("NSpgid", ""), "NSpgid")
        try:
            status_pid = int(fields.get("Pid", "0"))
        except ValueError as exception:
            raise SupervisorError("malformed status PID") from exception
        if status_pid != visible_pid or nspid[0] != visible_pid:
            raise SupervisorError("procfs-visible PID mapping mismatch")
        return ProcessIdentity(
            nspid[-1], nspgid[-1], visible_pid, nspgid[0], namespace_inode,
            nspid, nspgid, start_time,
        )

    def identity_for_local_pid(self, local_pid: int) -> ProcessIdentity:
        self.verify_stable()
        matches: list[ProcessIdentity] = []
        try:
            entries = tuple(self.proc_root.iterdir())
        except OSError as exception:
            raise SupervisorError(f"cannot enumerate procfs: {exception}") from exception
        for entry in entries:
            if not entry.name.isdigit():
                continue
            identity = self._identity_at(int(entry.name))
            if identity is not None and identity.local_pid == local_pid:
                matches.append(identity)
        if len(matches) != 1:
            raise SupervisorError("local PID has no unique procfs/NSpid mapping")
        return matches[0]

    def direct_children(self) -> dict[int, ProcessIdentity]:
        self.verify_stable()
        visible_children: set[int] = set()
        try:
            tasks = tuple((self.proc_root / "self/task").iterdir())
        except OSError as exception:
            raise SupervisorError(f"cannot enumerate procfs tasks: {exception}") from exception
        for task in tasks:
            try:
                payload = (task / "children").read_text(encoding="ascii").strip()
            except FileNotFoundError:
                continue
            except OSError as exception:
                raise SupervisorError(f"cannot read task children: {exception}") from exception
            for token in payload.split():
                if not token.isdigit() or int(token) <= 0:
                    raise SupervisorError("malformed visible child identity")
                visible_children.add(int(token))
        result: dict[int, ProcessIdentity] = {}
        for visible_pid in visible_children:
            identity = self._identity_at(visible_pid)
            if identity is None or identity.local_pid in result:
                raise SupervisorError("child PID namespace mapping is ambiguous")
            result[identity.local_pid] = identity
        return result

    def process_group_members(self, local_pgid: int) -> dict[int, ProcessIdentity]:
        self.verify_stable()
        members: dict[int, ProcessIdentity] = {}
        try:
            entries = tuple(self.proc_root.iterdir())
        except OSError as exception:
            raise SupervisorError(f"cannot enumerate procfs: {exception}") from exception
        for entry in entries:
            if not entry.name.isdigit():
                continue
            identity = self._identity_at(int(entry.name))
            if identity is None or identity.local_pgid != local_pgid:
                continue
            if identity.local_pid in members:
                raise SupervisorError("duplicate local PID in process-group mapping")
            members[identity.local_pid] = identity
        return members


def verify_supervisor_capability() -> dict[str, Any]:
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


class SupervisorLease:
    def __init__(self) -> None:
        self._locked = False
        self._active = False
        self._original = 0
        self.identity_model: ProcfsIdentityModel | None = None

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

    def close(self, *, suppress: bool = False) -> None:
        failure: BaseException | None = None
        if self._active:
            try:
                _prctl_set_subreaper(self._original)
                if _prctl_get_subreaper() != self._original:
                    raise SupervisorError("subreaper restoration readback mismatch")
            except BaseException as exception:
                failure = exception
            self._active = False
        if self._locked:
            self._locked = False
            _SUPERVISOR_LOCK.release()
        self.identity_model = None
        if failure is not None and not suppress:
            raise failure


def _peek_leader_exit_held(pid: int, diagnostics: list[str]) -> os.waitid_result | None:
    while True:
        try:
            return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
        except InterruptedError:
            diagnostics.append("WAITID_EINTR")
            continue
        except OSError as exception:
            diagnostics.append(f"WAITID_{exception.errno or type(exception).__name__}")
            time.sleep(POLL_NS / 1_000_000_000)


def _send_group(process_group: int, requested_signal: int, diagnostics: list[str]) -> None:
    try:
        os.killpg(process_group, requested_signal)
    except ProcessLookupError:
        return
    except OSError as exception:
        diagnostics.append(
            f"KILLPG_{requested_signal}_{exception.errno or type(exception).__name__}"
        )


def _send_owned_pid(pid: int, requested_signal: int, diagnostics: list[str]) -> None:
    try:
        os.kill(pid, requested_signal)
    except ProcessLookupError:
        return
    except OSError as exception:
        diagnostics.append(
            f"KILL_{requested_signal}_{exception.errno or type(exception).__name__}"
        )


def _direct_children_fail_stop(
    model: ProcfsIdentityModel, diagnostics: list[str]
) -> dict[int, ProcessIdentity]:
    """Never release a live transport family because a procfs read was transient."""

    while True:
        try:
            return model.direct_children()
        except BaseException as exception:
            diagnostics.append(
                f"CHILD_SCAN_{getattr(exception, 'errno', None) or type(exception).__name__}"
            )
            time.sleep(POLL_NS / 1_000_000_000)


def _process_group_members_fail_stop(
    model: ProcfsIdentityModel, process_group: int, diagnostics: list[str]
) -> dict[int, ProcessIdentity]:
    """Keep the leader waitable until the process group can be inspected."""

    while True:
        try:
            return model.process_group_members(process_group)
        except BaseException as exception:
            diagnostics.append(
                f"GROUP_SCAN_{getattr(exception, 'errno', None) or type(exception).__name__}"
            )
            time.sleep(POLL_NS / 1_000_000_000)


def _reap_owned_nonleader(
    model: ProcfsIdentityModel, leader_pid: int, diagnostics: list[str]
) -> set[int]:
    owned = set(_direct_children_fail_stop(model, diagnostics)) - {leader_pid}
    for pid in tuple(owned):
        while True:
            try:
                waited, _ = os.waitpid(pid, os.WNOHANG)
                if waited == pid:
                    owned.discard(pid)
                break
            except InterruptedError:
                diagnostics.append("DESCENDANT_WAITPID_EINTR")
                continue
            except ChildProcessError:
                owned.discard(pid)
                break
            except OSError as exception:
                diagnostics.append(
                    f"DESCENDANT_WAITPID_{exception.errno or type(exception).__name__}"
                )
                break
    return owned


def _waitpid_leader_fail_stop(pid: int, diagnostics: list[str]) -> int:
    """Never return an unconfirmed status; transient and injected errors retry."""

    while True:
        try:
            waited, status_value = os.waitpid(pid, 0)
            if waited == pid:
                return os.waitstatus_to_exitcode(status_value)
            diagnostics.append("LEADER_WAITPID_ZERO")
        except InterruptedError:
            diagnostics.append("LEADER_WAITPID_EINTR")
        except OSError as exception:
            diagnostics.append(
                f"LEADER_WAITPID_{exception.errno or type(exception).__name__}"
            )
        time.sleep(POLL_NS / 1_000_000_000)


def cleanup_process_group(
    process: subprocess.Popen[bytes], *, force_stop: bool,
    leader_wait_deadline_ns: int, global_deadline_ns: int,
    identity_model: ProcfsIdentityModel,
) -> CleanupResult:
    """Prove group quiescence while the leader PID/PGID remains unreaped."""

    leader_pid = process.pid
    process_group = leader_pid
    diagnostics: list[str] = []
    identity_model.verify_stable()
    leader_identity = identity_model.identity_for_local_pid(leader_pid)
    if leader_identity.local_pgid != process_group:
        raise SupervisorError("leader local PGID does not match start_new_session identity")
    term_sent = False
    kill_sent = False
    deadline_overrun = False
    leader_wait_timed_out = False
    descendants_detected = False
    maximum_descendants = 0

    if force_stop:
        _send_group(process_group, signal.SIGTERM, diagnostics)
        term_sent = True

    leader_exit: os.waitid_result | None = None
    while leader_exit is None:
        leader_exit = _peek_leader_exit_held(leader_pid, diagnostics)
        if leader_exit is not None:
            break
        now = time.monotonic_ns()
        if now >= leader_wait_deadline_ns:
            leader_wait_timed_out = True
            if not term_sent:
                _send_group(process_group, signal.SIGTERM, diagnostics)
                term_sent = True
                leader_wait_deadline_ns = min(now + TERM_GRACE_NS, global_deadline_ns)
            else:
                _send_group(process_group, signal.SIGKILL, diagnostics)
                kill_sent = True
                leader_wait_deadline_ns = min(now + KILL_GRACE_NS, global_deadline_ns)
        if now >= global_deadline_ns:
            deadline_overrun = True
            _send_group(process_group, signal.SIGKILL, diagnostics)
            kill_sent = True
        time.sleep(POLL_NS / 1_000_000_000)

    nonleader_members = _process_group_members_fail_stop(
        identity_model, process_group, diagnostics
    )
    nonleader_members.pop(leader_pid, None)
    owned = set(_direct_children_fail_stop(identity_model, diagnostics)) - {leader_pid}
    maximum_descendants = max(len(set(nonleader_members) | owned), maximum_descendants)
    if nonleader_members or owned:
        descendants_detected = True
        if not term_sent:
            _send_group(process_group, signal.SIGTERM, diagnostics)
            for pid in owned - set(nonleader_members):
                _send_owned_pid(pid, signal.SIGTERM, diagnostics)
            term_sent = True

    term_until = min(time.monotonic_ns() + TERM_GRACE_NS, global_deadline_ns)
    while True:
        owned = _reap_owned_nonleader(identity_model, leader_pid, diagnostics)
        nonleader_members = _process_group_members_fail_stop(
            identity_model, process_group, diagnostics
        )
        nonleader_members.pop(leader_pid, None)
        descendants = set(nonleader_members) | owned
        maximum_descendants = max(maximum_descendants, len(descendants))
        if not descendants:
            break
        now = time.monotonic_ns()
        if now >= term_until or kill_sent:
            _send_group(process_group, signal.SIGKILL, diagnostics)
            for pid in owned - set(nonleader_members):
                _send_owned_pid(pid, signal.SIGKILL, diagnostics)
            kill_sent = True
        if now >= global_deadline_ns:
            deadline_overrun = True
        time.sleep(POLL_NS / 1_000_000_000)

    # The zombie leader still reserves both PID and PGID here. No signal is
    # sent after this point, so PGID reuse cannot redirect cleanup.
    returncode = _waitpid_leader_fail_stop(leader_pid, diagnostics)
    process.returncode = returncode
    if _direct_children_fail_stop(identity_model, diagnostics):
        raise SupervisorError("owned descendant appeared after quiescence proof")
    identity_model.verify_stable()

    if kill_sent and deadline_overrun:
        outcome = "SIGKILL_BARRIER_LEADER_REAPED_GROUP_QUIESCENT"
    elif kill_sent:
        outcome = "SIGKILL_LEADER_REAPED_GROUP_QUIESCENT"
    elif term_sent:
        outcome = "SIGTERM_LEADER_REAPED_GROUP_QUIESCENT"
    else:
        outcome = "NORMAL_LEADER_REAPED_GROUP_QUIESCENT"
    return CleanupResult(
        returncode=returncode,
        leader_reaped=True,
        process_group_gone=True,
        terminal_cleanup_outcome=outcome,
        descendants_detected_after_leader_exit=descendants_detected,
        maximum_descendant_count=maximum_descendants,
        leader_wait_timed_out=leader_wait_timed_out,
        cleanup_deadline_overrun=deadline_overrun,
        cleanup_diagnostics=tuple(diagnostics),
        namespace_snapshot=identity_model.snapshot,
    )
