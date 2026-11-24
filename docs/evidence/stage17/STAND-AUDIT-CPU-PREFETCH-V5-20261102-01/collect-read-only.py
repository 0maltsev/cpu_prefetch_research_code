"""Read current stand facts; do not run calibration or modify machine state."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import os
import resource
import socket
import stat


def read(path):
    try:
        return {"observed": Path(path).read_text().strip()}
    except OSError as error:
        return {"unavailable_errno": error.errno}


evidence = Path("/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-12")
cpus = {}
for cpu in (0, 1, 8):
    base = Path(f"/sys/devices/system/cpu/cpu{cpu}")
    caches = []
    for index in sorted((base / "cache").glob("index*")):
        caches.append({"index": index.name, **{name: read(index / name) for name in (
            "id", "level", "type", "size", "coherency_line_size", "shared_cpu_list")}})
    cpus[str(cpu)] = {
        "topology": {name: read(base / "topology" / name) for name in (
            "physical_package_id", "core_id", "thread_siblings_list", "core_siblings_list")},
        "numa_node_links": [p.name for p in sorted(base.glob("node*"))],
        "caches": caches,
    }
memory = {}
for line in Path("/proc/meminfo").read_text().splitlines():
    key, value = line.split(":", 1)
    if key in ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree"):
        memory[key] = value.strip()
filesystem = os.statvfs(evidence)
journals = []
for p in sorted((evidence / "journal").glob("*.json")):
    payload = p.read_bytes()
    journals.append({"path": str(p), "size_bytes": len(payload),
                     "sha256": hashlib.sha256(payload).hexdigest()})
devices = {}
for cpu in (0, 1, 8):
    p = Path(f"/dev/cpu/{cpu}/msr")
    try:
        metadata = p.stat()
        devices[str(cpu)] = {"mode": oct(stat.S_IMODE(metadata.st_mode)),
                             "uid": metadata.st_uid, "gid": metadata.st_gid}
    except OSError as error:
        devices[str(cpu)] = {"unavailable_errno": error.errno}
retained_files = []
for p in (
    evidence / "q15-r-output-v3.json", evidence / "q15-w-output-v3.json",
    evidence / "q16a-authoring-1/q16a-action-inputs-1.json",
    evidence / "q16a-authoring-1/matrix-spec-1.json",
    evidence.parent / "cpu-prefetch-pilot-candidate-2.0.0-a820e6e-clean-9ee9e64490e5.tar.gz",
    evidence.parent / "cpu-prefetch-pilot-candidate-2.0.0-a820e6e-clean-9ee9e64490e5.tar.gz.sha256",
):
    try:
        hasher = hashlib.sha256()
        with p.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                hasher.update(chunk)
        retained_files.append({"path": str(p), "size_bytes": p.stat().st_size,
                               "sha256": hasher.hexdigest()})
    except OSError as error:
        retained_files.append({"path": str(p), "unavailable_errno": error.errno})
result = {
    "scope": "READ_ONLY_NO_EXPERIMENT_NO_MSR_READ_OR_WRITE",
    "captured_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "hostname": socket.gethostname(), "effective_uid": os.geteuid(),
    "boot_id": read("/proc/sys/kernel/random/boot_id"),
    "uptime": read("/proc/uptime"), "kernel_release": os.uname().release,
    "online_cpus": read("/sys/devices/system/cpu/online"),
    "requested_cpu_queries": [0, 1, 8], "observed_cpus": cpus,
    "observed_numa_nodes": {p.name: read(p / "cpulist")
                            for p in sorted(Path("/sys/devices/system/node").glob("node[0-9]*"))},
    "base_page_bytes": os.sysconf("SC_PAGESIZE"), "memory_raw": memory,
    "filesystem_available_bytes": filesystem.f_bavail * filesystem.f_frsize,
    "filesystem_queried_path": str(evidence),
    "root_shell_memlock_limit_bytes": list(resource.getrlimit(resource.RLIMIT_MEMLOCK)),
    "memlock_scope": "READ_ONLY_ROOT_SHELL_NOT_FUTURE_MEASUREMENT_OWNER",
    "msr_device_metadata_only": devices, "journal_files": journals,
    "retained_artifacts": retained_files,
    "temporary_validator_present": Path("/tmp/operational_cli_v11_local_patch_v4.py").is_file(),
    "resource_budget_frozen": False, "hardware_state_qualified": False,
    "execution_authority": False, "measurement_performed": False,
}
print(json.dumps(result, indent=2))
