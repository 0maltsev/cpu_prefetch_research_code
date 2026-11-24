#!/usr/bin/env python3
"""Hermetic Stage 17A.7 held-leader process-group lifecycle regressions."""

from __future__ import annotations

import argparse
import errno
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable

import stage17_process_group_supervisor_v1 as supervisor


class CheckError(RuntimeError):
    pass


def _group_gone(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return True
    return False


def _leader_program(
    *, count: int, exit_code: int, ignore_term: bool = False,
    keep_pipes: bool = False,
) -> str:
    child = (
        "import signal,time;"
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN);" if ignore_term else "")
        + "time.sleep(60)"
    )
    stream_args = "" if keep_pipes else ",stdin=d,stdout=d,stderr=d"
    return "".join((
        "import os,subprocess,sys;",
        f"d=open(os.devnull,'r+b'); ps=[subprocess.Popen([sys.executable,'-c',{child!r}]",
        f"{stream_args}) for _ in range({count})];",
        "print(','.join(str(p.pid) for p in ps),flush=True);",
        "__import__('time').sleep(0.1);" if ignore_term else "",
        f"sys.exit({exit_code})",
    ))


def _run_case(
    *, count: int, exit_code: int, ignore_term: bool = False,
    keep_pipes: bool = False,
    waitpid_fault: Callable[[int, int], tuple[int, int]] | None = None,
) -> supervisor.CleanupResult:
    lease = supervisor.SupervisorLease()
    lease.enter()
    process: subprocess.Popen[bytes] | None = None
    original_waitpid = supervisor.os.waitpid
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", _leader_program(
                count=count, exit_code=exit_code, ignore_term=ignore_term,
                keep_pipes=keep_pipes,
            )],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, start_new_session=True, close_fds=True,
        )
        assert process.stdout is not None
        line = process.stdout.readline().decode("ascii").strip()
        descendant_pids = [int(value) for value in line.split(",") if value]
        if len(descendant_pids) != count:
            raise CheckError("leader did not publish the expected descendant IDs")
        if waitpid_fault is not None:
            supervisor.os.waitpid = waitpid_fault  # type: ignore[assignment]
        now = time.monotonic_ns()
        result = supervisor.cleanup_process_group(
            process, force_stop=False,
            leader_wait_deadline_ns=now + 2_000_000_000,
            global_deadline_ns=now + 4_000_000_000,
        )
        if not result.leader_reaped or not result.process_group_gone:
            raise CheckError("cleanup returned without both lifecycle proofs")
        if not _group_gone(process.pid):
            raise CheckError("transport process group remained live")
        if any(pathlib.Path(f"/proc/{pid}").exists() for pid in descendant_pids):
            raise CheckError("a descendant remained visible after cleanup")
        return result
    finally:
        supervisor.os.waitpid = original_waitpid  # type: ignore[assignment]
        if process is not None and not _group_gone(process.pid):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        lease.close(suppress=True)


def _normal_success() -> None:
    result = _run_case(count=0, exit_code=0)
    if result.returncode != 0 or result.descendants_detected_after_leader_exit:
        raise CheckError("ordinary transport did not retain its success semantics")


def _leader_zero_descendant() -> None:
    result = _run_case(count=1, exit_code=0)
    if not result.descendants_detected_after_leader_exit:
        raise CheckError("normal leader exit hid a descendant")


def _leader_nonzero_descendant() -> None:
    result = _run_case(count=1, exit_code=17)
    if result.returncode != 17 or not result.descendants_detected_after_leader_exit:
        raise CheckError("nonzero leader/descendant state was lost")


def _closed_pipes_descendant() -> None:
    result = _run_case(count=1, exit_code=0, keep_pipes=False)
    if result.maximum_descendant_count < 1:
        raise CheckError("closed pipes were incorrectly treated as group quiescence")


def _multiple_descendants() -> None:
    result = _run_case(count=3, exit_code=0)
    if result.maximum_descendant_count < 3:
        raise CheckError("not all descendants were observed")


def _sigterm_ignored() -> None:
    result = _run_case(count=1, exit_code=0, ignore_term=True)
    if "SIGKILL" not in result.terminal_cleanup_outcome:
        raise CheckError("SIGTERM-resistant descendant did not require SIGKILL")


def _waitpid_eintr() -> None:
    original = supervisor.os.waitpid
    calls = 0

    def injected(pid: int, options: int) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise InterruptedError(errno.EINTR, "synthetic EINTR")
        return original(pid, options)

    result = _run_case(count=0, exit_code=0, waitpid_fault=injected)
    if "LEADER_WAITPID_EINTR" not in result.cleanup_diagnostics:
        raise CheckError("EINTR was not recorded and retried")


def _waitpid_other_error() -> None:
    original = supervisor.os.waitpid
    calls = 0

    def injected(pid: int, options: int) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError(errno.EIO, "synthetic EIO")
        return original(pid, options)

    result = _run_case(count=0, exit_code=0, waitpid_fault=injected)
    if "LEADER_WAITPID_5" not in result.cleanup_diagnostics:
        raise CheckError("non-EINTR waitpid error did not remain in cleanup evidence")


def _preexisting_child_rejected() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        lease = supervisor.SupervisorLease()
        try:
            lease.enter()
        except supervisor.SupervisorError:
            return
        finally:
            lease.close(suppress=True)
        raise CheckError("supervisor admitted an ambiguous pre-existing child")
    finally:
        child.kill()
        child.wait()


def self_test() -> tuple[int, int]:
    positives = [
        ("normal_transport", _normal_success),
        ("eintr_retry", _waitpid_eintr),
        ("non_eintr_retry", _waitpid_other_error),
    ]
    negatives = [
        ("leader_zero_descendant", _leader_zero_descendant),
        ("leader_nonzero_descendant", _leader_nonzero_descendant),
        ("closed_pipes_descendant", _closed_pipes_descendant),
        ("multiple_descendants", _multiple_descendants),
        ("sigterm_ignored", _sigterm_ignored),
        ("ambiguous_preexisting_child", _preexisting_child_rejected),
    ]
    for label, check in positives + negatives:
        check()
        print(f"stage17-process-group-quiescence: PASS {label}")
    return len(positives), len(negatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-process-group-quiescence: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-process-group-quiescence: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
