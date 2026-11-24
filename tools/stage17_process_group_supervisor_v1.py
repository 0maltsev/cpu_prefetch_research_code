#!/usr/bin/env python3
"""Linux held-leader/subreaper lifecycle proof for Stage 17 read-only transport."""

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


def _procfs_self_pid() -> int:
    target = os.readlink("/proc/self")
    if not target.isdigit() or int(target) <= 0:
        raise SupervisorError("/proc/self is not a numeric process identity")
    return int(target)


def _direct_children() -> set[int]:
    result: set[int] = set()
    task_root = pathlib.Path("/proc/self/task")
    try:
        tasks = tuple(task_root.iterdir())
    except OSError as exception:
        raise SupervisorError(f"cannot enumerate /proc/self/task: {exception}") from exception
    for task in tasks:
        try:
            payload = (task / "children").read_text(encoding="ascii").strip()
        except FileNotFoundError:
            continue
        except OSError as exception:
            raise SupervisorError(f"cannot read task children: {exception}") from exception
        for token in payload.split():
            if not token.isdigit() or int(token) <= 0:
                raise SupervisorError("malformed /proc task children identity")
            result.add(int(token))
    return result


def _read_process_stat(pid: int) -> tuple[str, int, int] | None:
    try:
        payload = pathlib.Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    except OSError as exception:
        if exception.errno in (errno.ENOENT, errno.ESRCH):
            return None
        raise SupervisorError(f"cannot read process stat: {exception}") from exception
    closing = payload.rfind(") ")
    if closing < 0:
        raise SupervisorError("malformed /proc process stat")
    fields = payload[closing + 2 :].split()
    if len(fields) < 4:
        raise SupervisorError("short /proc process stat")
    try:
        return fields[0], int(fields[1]), int(fields[2])
    except ValueError as exception:
        raise SupervisorError("invalid numeric /proc process stat") from exception


def _process_group_members(process_group: int) -> dict[int, str]:
    members: dict[int, str] = {}
    try:
        entries = tuple(pathlib.Path("/proc").iterdir())
    except OSError as exception:
        raise SupervisorError(f"cannot enumerate /proc: {exception}") from exception
    for entry in entries:
        if not entry.name.isdigit():
            continue
        stat = _read_process_stat(int(entry.name))
        if stat is not None and stat[2] == process_group:
            members[int(entry.name)] = stat[0]
    return members


def verify_supervisor_capability() -> dict[str, Any]:
    if sys.platform != "linux":
        raise SupervisorError("Linux is required for process-group supervision")
    if not hasattr(os, "waitid") or not hasattr(os, "WNOWAIT"):
        raise SupervisorError("waitid WNOWAIT is unavailable")
    visible_pid = _procfs_self_pid()
    current = _prctl_get_subreaper()
    _process_group_members(visible_pid)
    _direct_children()
    return {
        "mechanism": "LINUX_SUBREAPER_HELD_LEADER_WNOWAIT_PROCFS-v1",
        "procfs_visible_executor_pid": visible_pid,
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

    def enter(self) -> None:
        _SUPERVISOR_LOCK.acquire()
        self._locked = True
        try:
            if _direct_children():
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


def _direct_children_fail_stop(diagnostics: list[str]) -> set[int]:
    """Never release a live transport family because a procfs read was transient."""

    while True:
        try:
            return _direct_children()
        except BaseException as exception:
            diagnostics.append(
                f"CHILD_SCAN_{getattr(exception, 'errno', None) or type(exception).__name__}"
            )
            time.sleep(POLL_NS / 1_000_000_000)


def _process_group_members_fail_stop(
    process_group: int, diagnostics: list[str]
) -> dict[int, str]:
    """Keep the leader waitable until the process group can be inspected."""

    while True:
        try:
            return _process_group_members(process_group)
        except BaseException as exception:
            diagnostics.append(
                f"GROUP_SCAN_{getattr(exception, 'errno', None) or type(exception).__name__}"
            )
            time.sleep(POLL_NS / 1_000_000_000)


def _reap_owned_nonleader(leader_pid: int, diagnostics: list[str]) -> set[int]:
    owned = _direct_children_fail_stop(diagnostics) - {leader_pid}
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
) -> CleanupResult:
    """Prove group quiescence while the leader PID/PGID remains unreaped."""

    leader_pid = process.pid
    process_group = leader_pid
    diagnostics: list[str] = []
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

    nonleader_members = _process_group_members_fail_stop(process_group, diagnostics)
    nonleader_members.pop(leader_pid, None)
    owned = _direct_children_fail_stop(diagnostics) - {leader_pid}
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
        owned = _reap_owned_nonleader(leader_pid, diagnostics)
        nonleader_members = _process_group_members_fail_stop(process_group, diagnostics)
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
    if _direct_children_fail_stop(diagnostics):
        raise SupervisorError("owned descendant appeared after quiescence proof")

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
    )
