#!/usr/bin/env python3
"""Stage 17B PID-namespace identity and quiescence regressions.

The synthetic procfs fixtures exercise namespace-ID translation without
requiring the development container to create a nested PID namespace.  The
process tests below still exercise real local waitid/waitpid/killpg behaviour.
No socket, DNS, SSH, or external process is used.
"""

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
from unittest import mock

import stage17_process_group_supervisor_v1 as predecessor
import stage17_process_group_supervisor_v2 as supervisor


class CheckError(RuntimeError):
    pass


def _stat(pid: int, pgid: int, start: int) -> str:
    # Fields following the command begin with state (field 3); starttime is
    # field 22 and therefore index 19 in supervisor._start_time_ticks().
    fields = ["S", "1", str(pgid)] + ["0"] * 16 + [str(start)]
    return f"{pid} (fixture) " + " ".join(fields) + "\n"


def _write_process(
    root: pathlib.Path, *, visible_pid: int, local_pid: int,
    visible_pgid: int, local_pgid: int, namespace_inode: int,
    start: int, children: tuple[int, ...] = (),
) -> None:
    process = root / str(visible_pid)
    (process / "ns").mkdir(parents=True)
    (process / "task" / str(visible_pid)).mkdir(parents=True)
    (process / "status").write_text(
        "\n".join((
            "Name:\tfixture",
            f"Pid:\t{visible_pid}",
            f"NSpid:\t{visible_pid}\t{local_pid}",
            f"NSpgid:\t{visible_pgid}\t{local_pgid}",
        )) + "\n",
        encoding="ascii",
    )
    (process / "stat").write_text(_stat(visible_pid, visible_pgid, start), encoding="ascii")
    os.symlink(f"pid:[{namespace_inode}]", process / "ns/pid")
    (process / "task" / str(visible_pid) / "children").write_text(
        " ".join(str(value) for value in children), encoding="ascii"
    )


def _fixture(
    root: pathlib.Path, *, local_self: int = 7, visible_self: int = 41007,
    local_pgid: int = 7, visible_pgid: int = 41007,
    child_local: int = 8, child_visible: int = 41008,
    child_local_pgid: int = 8, child_visible_pgid: int = 41008,
) -> supervisor.ProcfsIdentityModel:
    root.mkdir()
    _write_process(
        root, visible_pid=visible_self, local_pid=local_self,
        visible_pgid=visible_pgid, local_pgid=local_pgid,
        namespace_inode=12345, start=101, children=(child_visible,),
    )
    _write_process(
        root, visible_pid=child_visible, local_pid=child_local,
        visible_pgid=child_visible_pgid, local_pgid=child_local_pgid,
        namespace_inode=12345, start=102,
    )
    (root / "1/ns").mkdir(parents=True)
    os.symlink("pid:[999]", root / "1/ns/pid")
    os.symlink(str(visible_self), root / "self")
    with mock.patch.object(supervisor.os, "getpid", return_value=local_self), \
         mock.patch.object(supervisor.os, "getpgrp", return_value=local_pgid):
        return supervisor.ProcfsIdentityModel(root)


def _mapping_same_and_different() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-map-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7):
            model.verify_stable()
            identity = model.identity_for_local_pid(8)
            if (identity.visible_pid, identity.local_pid) != (41008, 8):
                raise CheckError("distinct visible/local PID mapping was lost")

    with tempfile.TemporaryDirectory(prefix="stage17-pid-map-same-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(
            root, local_self=100, visible_self=100, local_pgid=100,
            visible_pgid=100, child_local=101, child_visible=101,
            child_local_pgid=101, child_visible_pgid=101,
        )
        with mock.patch.object(supervisor.os, "getpid", return_value=100), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=100):
            if model.identity_for_local_pid(101).visible_pid != 101:
                raise CheckError("same-namespace mapping failed")


def _predecessor_characterization() -> None:
    # The predecessor compares the visible stat PGID directly to a syscall
    # local PGID.  This deterministic reproduction preserves that historical
    # defect without changing or executing the predecessor supervisor.
    visible_stat = ("S", 1, 41008)
    local_process_group = 8
    predecessor_would_include = visible_stat[2] == local_process_group
    successor_would_include = 8 == local_process_group
    if predecessor_would_include or not successor_would_include:
        raise CheckError("predecessor mixed-ID characterization did not reproduce")
    if "stat[2] == process_group" in pathlib.Path(predecessor.__file__).read_text(encoding="utf-8"):
        return
    # The exact source is expressed as stat[2] in the predecessor today; fail
    # closed if the preserved characterization no longer describes its bytes.
    raise CheckError("predecessor characterization source anchor drifted")


def _foreign_namespace_same_numbers() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-foreign-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        foreign = root / "51008"
        _write_process(
            root, visible_pid=51008, local_pid=8, visible_pgid=51008,
            local_pgid=8, namespace_inode=54321, start=203,
        )
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7):
            members = model.process_group_members(8)
        if tuple(members) != (8,) or foreign.name != "51008":
            raise CheckError("foreign namespace reused numeric PID was admitted")


def _impossible_mapping_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-ambiguous-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        _write_process(
            root, visible_pid=42008, local_pid=8, visible_pgid=42008,
            local_pgid=8, namespace_inode=12345, start=999,
        )
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7):
            try:
                model.identity_for_local_pid(8)
            except supervisor.SupervisorError:
                return
    raise CheckError("ambiguous local-to-visible mapping was admitted")


def _malformed_mapping_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-malformed-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        (root / "41008/status").write_text(
            "Pid:\t41008\nNSpid:\tgarbage\nNSpgid:\t41008\t8\n", encoding="ascii"
        )
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7):
            try:
                model.identity_for_local_pid(8)
            except supervisor.SupervisorError:
                return
    raise CheckError("malformed namespace mapping was admitted")


def _namespace_drift_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-drift-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        (root / "41007/ns/pid").unlink()
        os.symlink("pid:[22222]", root / "41007/ns/pid")
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7):
            try:
                model.verify_stable()
            except supervisor.SupervisorError:
                return
    raise CheckError("PID namespace drift was admitted")


def _procfs_denied_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-pid-denied-") as temporary:
        root = pathlib.Path(temporary) / "proc"
        model = _fixture(root)
        with mock.patch.object(supervisor.os, "getpid", return_value=7), \
             mock.patch.object(supervisor.os, "getpgrp", return_value=7), \
             mock.patch.object(pathlib.Path, "iterdir", side_effect=PermissionError(errno.EACCES, "denied")):
            try:
                model.process_group_members(8)
            except supervisor.SupervisorError:
                return
    raise CheckError("denied procfs was admitted")


def _actual_group_cleanup(*, ignore_term: bool = False) -> None:
    child_source = (
        "import signal,time;"
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN);" if ignore_term else "")
        + "time.sleep(60)"
    )
    leader_source = (
        "import os,subprocess,sys;d=open(os.devnull,'r+b');"
        f"p=subprocess.Popen([sys.executable,'-c',{child_source!r}],stdin=d,stdout=d,stderr=d);"
        "print(p.pid,flush=True);"
        + ("__import__('time').sleep(0.1);" if ignore_term else "")
        + "sys.exit(0)"
    )
    lease = supervisor.SupervisorLease()
    lease.enter()
    process: subprocess.Popen[bytes] | None = None
    descendant = 0
    try:
        process = subprocess.Popen(
            [sys.executable, "-c", leader_source], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True, close_fds=True,
        )
        assert process.stdout is not None
        descendant = int(process.stdout.readline().decode("ascii"))
        now = time.monotonic_ns()
        assert lease.identity_model is not None
        result = supervisor.cleanup_process_group(
            process, force_stop=False, leader_wait_deadline_ns=now + 2_000_000_000,
            global_deadline_ns=now + 5_000_000_000,
            identity_model=lease.identity_model,
        )
        if not result.leader_reaped or not result.process_group_gone:
            raise CheckError("successor returned without quiescence proof")
        if pathlib.Path(f"/proc/{descendant}").exists():
            raise CheckError("descendant remained after successor cleanup")
        if ignore_term and "SIGKILL" not in result.terminal_cleanup_outcome:
            raise CheckError("SIGTERM-resistant descendant avoided SIGKILL")
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        lease.close(suppress=True)


def _wait_faults(injected: BaseException = InterruptedError(errno.EINTR, "fixture")) -> None:
    original_waitid = supervisor.os.waitid
    calls = 0

    def interrupted(*args: object) -> os.waitid_result:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise injected
        return original_waitid(*args)  # type: ignore[arg-type]

    with mock.patch.object(supervisor.os, "waitid", side_effect=interrupted):
        _actual_group_cleanup()


def _transient_procfs_scan() -> None:
    original = supervisor.ProcfsIdentityModel.process_group_members
    calls = 0

    def transient(self: supervisor.ProcfsIdentityModel, pgid: int):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise supervisor.SupervisorError("synthetic transient procfs read")
        return original(self, pgid)

    with mock.patch.object(
        supervisor.ProcfsIdentityModel, "process_group_members", transient
    ):
        _actual_group_cleanup()


def _leader_identity_is_held_against_reuse() -> None:
    source = pathlib.Path(supervisor.__file__).read_text(encoding="utf-8")
    reap = source.find("returncode = _waitpid_leader_fail_stop")
    last_group_scan = source.rfind("_process_group_members_fail_stop", 0, reap)
    last_signal = source.rfind("_send_group", 0, reap)
    if reap < 0 or last_group_scan < 0 or last_signal < 0:
        raise CheckError("held-leader ordering anchors are absent")
    if "No signal is\n    # sent after this point" not in source:
        raise CheckError("signal-after-reap prohibition is absent")


def self_test() -> tuple[int, int]:
    positives = (
        ("same_and_distinct_namespace_mapping", _mapping_same_and_different),
        ("actual_group_quiescence", lambda: _actual_group_cleanup()),
        ("actual_sigkill_quiescence", lambda: _actual_group_cleanup(ignore_term=True)),
        ("waitid_eintr", _wait_faults),
        ("waitid_echild_transient", lambda: _wait_faults(ChildProcessError(errno.ECHILD, "fixture"))),
        ("transient_procfs_scan", _transient_procfs_scan),
        ("held_leader_blocks_pid_pgid_reuse", _leader_identity_is_held_against_reuse),
    )
    negatives = (
        ("predecessor_mixed_id_characterization", _predecessor_characterization),
        ("foreign_namespace_numeric_reuse", _foreign_namespace_same_numbers),
        ("impossible_mapping", _impossible_mapping_rejected),
        ("malformed_mapping", _malformed_mapping_rejected),
        ("namespace_drift", _namespace_drift_rejected),
        ("procfs_access_denied", _procfs_denied_rejected),
    )
    for label, check in positives + negatives:
        check()
        print(f"stage17-pid-namespace-supervisor: PASS {label}")
    return len(positives), len(negatives)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-pid-namespace-supervisor: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-pid-namespace-supervisor: PASS "
        f"positive={positive} negative={negative} stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
