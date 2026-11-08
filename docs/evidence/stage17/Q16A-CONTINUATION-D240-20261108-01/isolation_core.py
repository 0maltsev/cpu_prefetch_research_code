"""Cold recovery infrastructure primitives; no scientific or launch authority.

The managed unit requests cpuset from PID1. Its own exclusive-CPU field is
configured explicitly because systemd 259 has no corresponding property.
Only the delegated child is made a remote isolated partition. A real cold
daemon-reload/readback is mandatory before this setup can qualify anything.
"""
from __future__ import annotations

import os
import re
import argparse
import datetime
import hashlib
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

RESERVED = frozenset((0, 1, 2, 8, 16, 17, 18, 24))
HOUSEKEEPING = frozenset(range(32)) - RESERVED
CPU_LIST = "0-2,8,16-18,24"
TIMER_SERVICES = {
    "apt-daily.timer": "apt-daily.service",
    "apt-daily-upgrade.timer": "apt-daily-upgrade.service",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def cpus(text):
    result = set()
    for part in text.strip().split(","):
        if not part:
            continue
        pair = part.split("-")
        require(len(pair) in (1, 2) and all(x.isdecimal() for x in pair), "CPU list")
        first, last = int(pair[0]), int(pair[-1])
        require(0 <= first <= last < 4096, "CPU range")
        result.update(range(first, last + 1))
    return result


def read(path):
    return Path(path).read_text().strip()


def write_control(path, value):
    """Never try creating a missing kernfs control file (old Path.open('w'))."""
    fd = os.open(path, os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        raw = (value + "\n").encode("ascii")
        require(os.write(fd, raw) == len(raw), "short control write")
    finally:
        os.close(fd)


def unit_text(unit, keeper, lifetime_seconds, stop_seconds):
    require(re.fullmatch(r"cpu-prefetch-recovery-[a-z0-9-]+\.service", unit), "owned unit name")
    require(re.fullmatch(r"/[A-Za-z0-9_./-]+", str(keeper)), "safe absolute keeper path")
    require(type(lifetime_seconds) is int and lifetime_seconds > 0, "finite lifecycle required")
    require(type(stop_seconds) is int and 0 < stop_seconds < lifetime_seconds, "finite cleanup reserve required")
    return (
        "[Unit]\nDescription=Owned bounded Stage17 recovery isolation\n"
        "[Service]\nType=exec\nUser=root\nGroup=root\nSlice=-.slice\n"
        "Delegate=cpuset\nDelegateSubgroup=supervisor\n"
        "AllowedCPUs=0-31\nAllowedMemoryNodes=0-1\nCPUAffinity=3\n"
        f"ExecStart=/usr/bin/python3 {keeper} --keeper\n"
        "Restart=no\nKillMode=control-group\n"
        f"RuntimeMaxSec={lifetime_seconds}\nTimeoutStopSec={stop_seconds}\n"
    )


def maintenance_plan(states):
    """Explicitly scoped apt units; no package process is stopped or killed."""
    names = set(TIMER_SERVICES) | set(TIMER_SERVICES.values())
    require(set(states) == names, "exact apt timer/service inventory required")
    for row in states.values():
        require(row["UnitFileState"] in {"enabled", "enabled-runtime", "disabled", "static", "indirect", "masked", "masked-runtime"},
                "unknown apt unit enablement")
    for timer, service in TIMER_SERVICES.items():
        require(states[service]["ActiveState"] == "inactive"
                and states[service]["SubState"] == "dead", "package maintenance is active/uncertain")
        require(states[timer]["ActiveState"] in ("active", "inactive"), "timer is transitioning")
    # Persistent enablement is untouched; runtime masks are separately restored.
    return {
        "stop_timers": sorted(t for t in TIMER_SERVICES if states[t]["ActiveState"] == "active"),
        "add_runtime_masks": sorted(n for n in names if states[n]["UnitFileState"] not in ("masked", "masked-runtime")),
        "restart_timers": sorted(t for t in TIMER_SERVICES if states[t]["ActiveState"] == "active"),
    }


def restore_maintenance_commands(plan):
    result = []
    if plan["add_runtime_masks"]:
        result.append(["systemctl", "unmask", "--runtime", *plan["add_runtime_masks"]])
    # Restore starts only timers, never oneshot apt services.
    if plan["restart_timers"]:
        result.append(["systemctl", "start", *plan["restart_timers"]])
    return result


def mask_identity(path):
    path = Path(path)
    require(path.is_symlink() and os.readlink(path) == "/dev/null", "runtime mask changed")
    st = path.lstat()
    return [st.st_dev, st.st_ino]


def remove_empty_partition(path, expected_identity, *, reader=read,
                           writer=write_control, remove=None):
    """Remove only the pinned owned empty leaf, even after controller loss.

    ENOENT is accepted solely for a vanished control whose parent's active
    controller set also lacks cpuset. EACCES/ENODEV on a present control is an
    error, not proof that cleanup succeeded. No parent controller is enabled.
    """
    path = Path(path)
    require(not path.is_symlink(), "partition symlink")
    st = path.stat()
    require((st.st_dev, st.st_ino) == tuple(expected_identity), "owned cgroup identity changed")
    require(reader(path / "cgroup.procs") == "", "partition has tasks; do not move/kill")
    require("populated 0" in reader(path / "cgroup.events").splitlines(), "partition populated")
    require(not any(p.is_dir() for p in path.iterdir()), "unexpected owned descendants")
    control = path / "cpuset.cpus.partition"
    missing = False
    try:
        reader(control)
    except FileNotFoundError:
        require("cpuset" not in reader(path.parent / "cgroup.subtree_control").split(),
                "partition control missing while cpuset remains enabled")
        missing = True
    if not missing:
        writer(control, "member")
        require(reader(control) == "member", "partition demotion failed")
    # Recheck after writes and before rmdir, which is the final kernel task guard.
    st = path.stat()
    require((st.st_dev, st.st_ino) == tuple(expected_identity), "cgroup replaced during cleanup")
    require(reader(path / "cgroup.procs") == ""
            and "populated 0" in reader(path / "cgroup.events").splitlines(), "tasks appeared during cleanup")
    (remove or (lambda p: p.rmdir()))(path)
    return {"removed": True, "controller_already_absent": missing}


def verify_isolation(snapshot):
    require(snapshot["partition"] == "isolated", "invalid isolated partition")
    for key in ("cpus", "effective", "exclusive", "exclusive_effective", "root_isolated"):
        require(cpus(snapshot[key]) == RESERVED, "reserved CPU readback differs: " + key)
    require(cpus(snapshot["mems_effective"]) == {0, 1}, "NUMA readback differs")
    require(cpus(snapshot["root_effective"]) == HOUSEKEEPING, "root exclusion differs")
    require("cpuset" in snapshot["root_subtree_control"].split(), "root controller disabled")
    require("cpuset" in snapshot["unit_subtree_control"].split(), "delegation disabled")
    require(snapshot["supervisor_affinity"] == [3], "supervisor affinity differs")
    for name, value in snapshot["outside_effective"].items():
        require(cpus(value) and cpus(value) <= HOUSEKEEPING, "outside task exclusion differs: " + name)


def verify_reload(before, after):
    verify_isolation(before)
    verify_isolation(after)
    require(before["boot_id"] == after["boot_id"], "boot changed")
    require(before["control_identities"] == after["control_identities"], "control inode changed across reload")
    require(before["partition_path"] == after["partition_path"], "partition path changed")


# Execution entry points remain subject to main's exact-operations review.
# Nothing in this module starts Q15/Q16, changes MSRs, or admits a family.
ROOT = Path("/sys/fs/cgroup")
CG = None
Q = None
REVISION = None
BOOT = None
CONFIG = None
MONITORED = ("cpuset.cpus", "cpuset.cpus.effective", "cpuset.cpus.exclusive",
             "cpuset.cpus.partition", "cpuset.mems.effective")


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def retain(path, value):
    path = Path(path)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if os.geteuid() == 0:
        os.chown(path, 1000, 1000)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def configure(pre):
    global CONFIG, CG, Q, REVISION, BOOT
    c = pre["operator_config"]
    require(set(c) == {"unit_name", "source_revision", "boot_id", "lifecycle_seconds", "stop_seconds", "protected_work_ns", "evidence_root"},
            "exact infrastructure configuration required")
    unit_text(c["unit_name"], Path(__file__).resolve(), c["lifecycle_seconds"], c["stop_seconds"])
    require(type(c["protected_work_ns"]) is int and c["protected_work_ns"] >= 0
            and c["protected_work_ns"] + c["stop_seconds"] * 10**9 < c["lifecycle_seconds"] * 10**9,
            "keeper lifetime does not cover prospective work plus cleanup")
    require(re.fullmatch("[0-9a-f]{40}", c["source_revision"]), "source revision")
    require(re.fullmatch("[0-9a-f-]{36}", c["boot_id"]), "boot identity")
    evidence = Path(c["evidence_root"])
    require(evidence.is_absolute() and ".." not in evidence.parts
            and evidence.is_relative_to("/home/omaltsev/stage17-owner-evidence"), "owned evidence root required")
    require(all(not p.is_symlink() for p in (evidence, *evidence.parents)), "evidence symlink")
    CONFIG = dict(c)
    CG = ROOT / c["unit_name"] / "reserved"
    Q = evidence
    REVISION, BOOT = c["source_revision"], c["boot_id"]
    require(pre.get("partition_path", str(CG)) == str(CG), "partition path differs")


def command(*args):
    result = subprocess.run(list(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, timeout=CONFIG["stop_seconds"], check=False)
    require(result.returncode == 0, "operator command failed: " + repr(args) + ": " + result.stderr[-4096:])
    return result.stdout.strip()


def systemd_state(unit):
    raw = command("systemctl", "show", unit, "--property=ActiveState", "--property=SubState", "--property=UnitFileState")
    result = dict(line.split("=", 1) for line in raw.splitlines())
    require(set(result) == {"ActiveState", "SubState", "UnitFileState"}, "incomplete systemd state")
    return result


def root_state():
    return {name: read(ROOT / name) for name in (
        "cgroup.controllers", "cgroup.subtree_control", "cpuset.cpus.effective",
        "cpuset.mems.effective", "cpuset.cpus.isolated")}


def identity(path):
    require(not Path(path).is_symlink(), "cgroup symlink")
    st = Path(path).stat()
    return [st.st_dev, st.st_ino]


def start_ticks(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def isolated_state():
    require(read("/proc/sys/kernel/random/boot_id") == BOOT, "boot changed")
    unit = CG.parent
    state = dict(partition=read(CG / "cpuset.cpus.partition"), cpus=read(CG / "cpuset.cpus"),
                 effective=read(CG / "cpuset.cpus.effective"), exclusive=read(CG / "cpuset.cpus.exclusive"),
                 exclusive_effective=read(CG / "cpuset.cpus.exclusive.effective"),
                 mems_effective=read(CG / "cpuset.mems.effective"),
                 root_isolated=read(ROOT / "cpuset.cpus.isolated"), root_effective=read(ROOT / "cpuset.cpus.effective"),
                 root_subtree_control=read(ROOT / "cgroup.subtree_control"),
                 unit_subtree_control=read(unit / "cgroup.subtree_control"),
                 supervisor_affinity=sorted(os.sched_getaffinity(0)),
                 outside_effective={name: read(ROOT / name / "cpuset.cpus.effective")
                                    for name in ("system.slice", "user.slice", "init.scope")},
                 boot_id=BOOT, partition_path=str(CG),
                 control_identities={name: identity(CG / name) for name in MONITORED})
    require(read(CG / "cgroup.type") == "domain" and read(CG / "cgroup.subtree_control") == "", "leaf cgroup type/delegation differs")
    verify_isolation(state)
    return {"captured_at_utc": utc(), "root": root_state(),
            "partition": {name: read(CG / name) for name in (
                "cgroup.type", "cgroup.subtree_control", "cgroup.procs", "cgroup.events",
                "cpuset.cpus", "cpuset.cpus.effective", "cpuset.cpus.exclusive",
                "cpuset.cpus.exclusive.effective", "cpuset.cpus.partition",
                "cpuset.mems", "cpuset.mems.effective")},
            "supervisor_affinity": state["supervisor_affinity"], "validation": state}


def restore(prestate):
    """Symmetric owned cleanup; never disables a parent/root controller directly."""
    require(os.geteuid() == 0 and read("/proc/sys/kernel/random/boot_id") == BOOT, "root/same boot required")
    require(prestate["operator_config"] == CONFIG, "cleanup configuration differs")
    unit = CG.parent
    unit_file = Path("/run/systemd/system") / CONFIG["unit_name"]
    observation = {"utc": utc(), "verified": False, "partition_absent": False, "errors": []}
    try:
        _restore_owned_unit(prestate, unit, unit_file, observation)
    except BaseException as error:
        observation["errors"].append({"stage": "owned_cgroup", "error": repr(error),
                                      "errno": getattr(error, "errno", None), "filename": getattr(error, "filename", None)})
    # Every owned maintenance change is considered independently, even when
    # partition demotion/removal failed. Never discard the cleanup failure.
    for name, observed_identity in prestate["owned_masks"].items():
        try:
            require(mask_identity(Path("/run/systemd/system") / name) == observed_identity, "owned mask replaced; do not unmask")
            command("systemctl", "unmask", "--runtime", name)
        except BaseException as error:
            observation["errors"].append({"stage": "unmask", "unit": name, "error": repr(error)})
    for name in prestate["maintenance_plan"]["restart_timers"]:
        try:
            command("systemctl", "start", name)
        except BaseException as error:
            observation["errors"].append({"stage": "restart_timer", "unit": name, "error": repr(error)})
    try:
        observed_root = root_state()
        observation["root"] = observed_root
        observation["root_restoration_verified"] = observed_root == prestate["root"]
    except BaseException as error:
        observation["errors"].append({"stage": "root_readback", "error": repr(error)})
        observation["root_restoration_verified"] = False
    maintenance = {}
    for name in prestate["maintenance_before"]:
        try:
            maintenance[name] = systemd_state(name)
        except BaseException as error:
            observation["errors"].append({"stage": "maintenance_readback", "unit": name, "error": repr(error)})
    observation["maintenance"] = maintenance
    observation["maintenance_restoration_verified"] = all(
        name in maintenance and maintenance[name]["UnitFileState"] == row["UnitFileState"]
        and (name not in TIMER_SERVICES or maintenance[name]["ActiveState"] == row["ActiveState"])
        for name, row in prestate["maintenance_before"].items())
    observation["partition_absent"] = not CG.exists()
    observation["verified"] = (not observation["errors"] and observation["root_restoration_verified"]
                               and observation["partition_absent"] and observation["maintenance_restoration_verified"])
    retain(Q / "restoration.json", observation)
    require(observation["verified"], "restoration incomplete; inspect retained independent facts")


def _restore_owned_unit(prestate, unit, unit_file, observation):
    if CG.exists():
        observation["partition_cleanup"] = remove_empty_partition(CG, prestate["partition_identity"])
    if unit.exists():
        require(identity(unit) == prestate["unit_identity"], "owned unit cgroup replaced")
        require({p.name for p in unit.iterdir() if p.is_dir()} == {"supervisor"}, "unexpected unit subtree")
        keeper = prestate["keeper_pid"]
        require(read(unit / "cgroup.procs") == "" and read(unit / "supervisor/cgroup.procs") == str(keeper),
                "unrelated/live unit tasks; do not stop")
        require(start_ticks(keeper) == prestate["keeper_start_ticks"], "keeper PID reused")
        require(command("systemctl", "show", CONFIG["unit_name"], "--property=MainPID", "--value") == str(keeper), "unit keeper differs")
        command("systemctl", "stop", CONFIG["unit_name"])
        require(not unit.exists(), "owned unit cgroup remains")
    if prestate.get("unit_file_created") and unit_file.exists():
        require(not unit_file.is_symlink() and sha(unit_file.read_bytes()) == prestate["unit_file_sha256"], "unit file changed; do not remove")
        require(identity(unit_file) == prestate["unit_file_identity"], "unit file replaced; do not remove")
        unit_file.unlink()
        command("systemctl", "daemon-reload")
    # Removal of our declared dependency is delegated to PID1, not a root -cpuset write.


def verify_remaining_lifetime(prestate, watchdog_ns, cleanup_ns):
    require(type(watchdog_ns) is int and watchdog_ns > 0 and type(cleanup_ns) is int and cleanup_ns > 0,
            "explicit finite family watchdog and cleanup required")
    required = watchdog_ns + cleanup_ns
    require(CONFIG["protected_work_ns"] >= required, "keeper config omits actual family watchdog/cleanup")
    require(prestate["keeper_deadline_monotonic_ns"] - time.monotonic_ns()
            > required + CONFIG["stop_seconds"] * 10**9, "keeper remaining lifetime cannot cover family and cleanup")


def prepare(config):
    configure({"operator_config": config})
    require(os.geteuid() == 0 and read("/proc/sys/kernel/random/boot_id") == BOOT, "root/same boot required")
    source = Path(__file__).resolve()
    st = source.stat()
    require(st.st_uid == 0 and not st.st_mode & 0o022, "root-owned immutable operator required")
    require(not Q.exists(), "fresh preparation namespace required")
    unit_file = Path("/run/systemd/system") / CONFIG["unit_name"]
    require(not unit_file.exists() and not unit_file.is_symlink() and not CG.parent.exists(), "unit namespace already exists")
    os.sched_setaffinity(0, {3})
    before = root_state()
    require(cpus(before["cpuset.cpus.effective"]) == set(range(32)) and before["cpuset.cpus.isolated"] == "", "preexisting isolation")
    maintenance = {name: systemd_state(name) for name in (*TIMER_SERVICES, *TIMER_SERVICES.values())}
    plan = maintenance_plan(maintenance)
    for name in plan["add_runtime_masks"]:
        path = Path("/run/systemd/system") / name
        require(not path.exists() and not path.is_symlink(), "runtime unit override already exists; do not replace")
    text = unit_text(CONFIG["unit_name"], source, CONFIG["lifecycle_seconds"], CONFIG["stop_seconds"])
    state = dict(operator_config=CONFIG, root=before, maintenance_before=maintenance,
                 maintenance_plan=plan, unit_file_sha256=sha(text.encode()), owned_masks={}, unit_file_created=False)
    Q.mkdir(mode=0o755)
    retain(Q / "preparation-intent.json", {"utc": utc(), "prestate": state,
           "operator_script_sha256": sha(source.read_bytes()), "unit_text": text})
    try:
        if plan["stop_timers"]:
            command("systemctl", "stop", *plan["stop_timers"])
        for name in plan["add_runtime_masks"]:
            command("systemctl", "mask", "--runtime", name)
            state["owned_masks"][name] = mask_identity(Path("/run/systemd/system") / name)
        # Recheck services after preventing new activation; never kill apt/dpkg.
        maintenance_plan({name: systemd_state(name) for name in maintenance})
        with unit_file.open("x") as stream:
            state["unit_file_created"] = True
            state["unit_file_identity"] = identity(unit_file)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        command("systemctl", "daemon-reload")
        command("systemctl", "start", CONFIG["unit_name"])
        state["unit_identity"] = identity(CG.parent)
        pid = int(command("systemctl", "show", CONFIG["unit_name"], "--property=MainPID", "--value"))
        require(pid > 1 and read(CG.parent / "supervisor/cgroup.procs") == str(pid), "delegated supervisor missing")
        state.update(keeper_pid=pid, keeper_start_ticks=start_ticks(pid))
        started_us = int(command("systemctl", "show", CONFIG["unit_name"], "--property=ExecMainStartTimestampMonotonic", "--value"))
        require(started_us > 0, "actual keeper start time missing")
        state["keeper_deadline_monotonic_ns"] = started_us * 1000 + CONFIG["lifecycle_seconds"] * 10**9
        require(read(CG.parent / "cgroup.procs") == "", "unit has internal processes")
        write_control(CG.parent / "cgroup.subtree_control", "+cpuset")
        write_control(CG.parent / "supervisor/cpuset.cpus", "3")
        write_control(CG.parent / "cpuset.cpus.exclusive", CPU_LIST)
        CG.mkdir()
        state["partition_identity"] = identity(CG)
        write_control(CG / "cpuset.mems", "0-1")
        write_control(CG / "cpuset.cpus", CPU_LIST)
        write_control(CG / "cpuset.cpus.exclusive", CPU_LIST)
        write_control(CG / "cpuset.cpus.partition", "isolated")
        first = isolated_state()
        retain(Q / "before-reload.json", first)
        command("systemctl", "daemon-reload")
        second = isolated_state()
        verify_reload(first["validation"], second["validation"])
        retain(Q / "after-reload.json", second)
        pre = dict(operator_config=CONFIG, prestate=state, operator_script_sha256=sha(source.read_bytes()),
                   source_revision=REVISION, boot_id=BOOT, partition_path=str(CG))
        retain(Q / "prospective-prestate.json", pre)
        retain(Q / "isolation-ready.json", {"utc": utc(), "verified": True,
               "daemon_reload_verified": True, "partition_path": str(CG), "observation": second})
        return pre
    except BaseException as error:
        retain(Q / "preparation-failure.json", {"utc": utc(), "error": repr(error), "partial_state": state})
        # Cleanup only where recorded identities make ownership provable. Any
        # gap remains explicit; no second preparation or capture is attempted.
        try:
            restore(state)
        except BaseException as cleanup_error:
            retain(Q / "preparation-cleanup-error.json", {"utc": utc(), "error": repr(cleanup_error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--keeper", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--restore", action="store_true")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--config-sha256")
    args = parser.parse_args()
    if args.keeper:
        require(os.geteuid() == 0, "root keeper required")
        os.sched_setaffinity(0, {3})
        while True:
            signal.pause()
    require(args.config is not None and args.config_sha256 is not None, "explicit bound config required")
    raw = args.config.read_bytes()
    require(sha(raw) == args.config_sha256, "configuration hash differs")
    document = json.loads(raw)
    if args.restore:
        configure(document)
        restore(document["prestate"])
    else:
        prepare(document)


if __name__ == "__main__":
    main()

