#!/usr/bin/env python3
"""Prospective finite discovery launcher; no experiment authority is granted here.

Root entry -> finite limits -> setpriv UID1000 -> readback -> controller23.
No alarm, timeout, affinity change or background fork. Only per-process limits.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import resource
import stat
import sys

AS_BYTES = 224 * 1024**3
MEMLOCK_BYTES = 12 * 1024**3
CAP_NAMES = ("sys_ptrace", "sys_rawio", "dac_override", "perfmon")
CAP_MASK = sum(1 << bit for bit in (19, 17, 1, 38))


def status():
    return dict(line.split(":", 1) for line in
                pathlib.Path("/proc/self/status").read_text().splitlines() if ":" in line)


def binding(path):
    path = pathlib.Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("not a regular file: " + str(path))
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return dict(path=str(path), size_bytes=path.stat().st_size, sha256=digest.hexdigest())


def validate_readback(observed, gid):
    if observed["uid"] != [1000] * 3 or observed["gid"] != [gid] * 3 or observed["groups"]:
        raise ValueError("UID/GID/supplementary-group readback differs")
    if observed["rlimits"]["RLIMIT_AS"] != [AS_BYTES, AS_BYTES]:
        raise ValueError("address-space readback differs")
    if observed["rlimits"]["RLIMIT_MEMLOCK"] != [MEMLOCK_BYTES, MEMLOCK_BYTES]:
        raise ValueError("finite 12 GiB memlock readback differs")
    for field in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"):
        if int(observed["proc_status"][field], 16) != CAP_MASK:
            raise ValueError("capability readback differs: " + field)


def command(args):
    caps = "-all," + ",".join("+" + name for name in CAP_NAMES)
    return [str(args.setpriv), "--reuid=1000", "--regid=" + str(args.gid),
            "--clear-groups", "--bounding-set=" + caps, "--inh-caps=" + caps,
            "--ambient-caps=" + caps, str(args.python), "-B", str(pathlib.Path(__file__).resolve()),
            "--inner", "--python", str(args.python), "--setpriv", str(args.setpriv),
            "--gid", str(args.gid), "--controller", str(args.controller),
            "--record", str(args.record), "--", *args.controller_args]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("python", "setpriv", "controller", "record"):
        parser.add_argument("--" + name, type=pathlib.Path, required=True)
    parser.add_argument("--gid", type=int, required=True)
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("controller_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.controller_args[:1] == ["--"]:
        args.controller_args = args.controller_args[1:]
    if args.gid < 0 or args.controller.name != "stage17_phase_controller_v23.py":
        raise ValueError("explicit GID and controller23 are required")
    if "--authorization" not in args.controller_args or "--signature" not in args.controller_args:
        raise ValueError("finite signed discovery authorization is required")
    for name in ("python", "setpriv", "controller"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.record = args.record.absolute()
    authorization_path = pathlib.Path(args.controller_args[args.controller_args.index("--authorization") + 1])
    authorization = json.loads(authorization_path.read_bytes())
    if authorization.get("action_id") != "Q16A-DURATION-DISCOVERY":
        raise ValueError("launcher is restricted to the diagnostic action")
    if args.record.exists():
        raise ValueError("readback record already exists; refusing reuse")
    if not args.inner:
        if os.geteuid() != 0:
            raise ValueError("initial entry requires root to set explicit credentials")
        if int(status()["CapBnd"], 16) & CAP_MASK != CAP_MASK:
            raise ValueError("required capabilities absent from inherited bounding set")
        resource.setrlimit(resource.RLIMIT_AS, (AS_BYTES, AS_BYTES))
        resource.setrlimit(resource.RLIMIT_MEMLOCK, (MEMLOCK_BYTES, MEMLOCK_BYTES))
        argv = command(args)
        os.execv(argv[0], argv)
    observed = dict(uid=list(os.getresuid()), gid=list(os.getresgid()), groups=os.getgroups(),
        affinity=sorted(os.sched_getaffinity(0)), proc_status={k: v.strip() for k, v in status().items()},
        rlimits={name: list(resource.getrlimit(getattr(resource, name)))
                 for name in sorted(dir(resource)) if name.startswith("RLIMIT_")})
    validate_readback(observed, args.gid)
    python_mode = args.python.stat().st_mode
    if python_mode & (stat.S_ISUID | stat.S_ISGID) or "security.capability" in os.listxattr(args.python):
        raise ValueError("Python executable must preserve ambient caps across ordinary exec")
    argv = [str(args.python), "-B", str(args.controller), *args.controller_args]
    record = dict(schema_version="cpu-prefetch-discovery-launch-readback/1",
        observed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        pid=os.getpid(), ppid=os.getppid(), requested=dict(uid=1000, gid=args.gid,
            address_space_bytes=AS_BYTES, memory_lock_bytes=MEMLOCK_BYTES,
            capabilities=list(CAP_NAMES), capability_mask_hex=f"{CAP_MASK:016x}"),
        observed=observed, executable_bindings={name: binding(getattr(args, name))
            for name in ("python", "setpriv", "controller")}, launcher=binding(__file__),
        exec_argv=argv, execution_authority=False, qualification_result=False)
    payload = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(args.record, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(args.record.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    os.execv(argv[0], argv)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit("discovery-launch: FAIL: " + str(error))
