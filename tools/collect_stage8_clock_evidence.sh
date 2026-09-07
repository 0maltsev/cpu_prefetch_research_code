#!/usr/bin/env bash
# Collect read-only host and repository evidence for preparing decision D-009.
# This is not a clock qualification test and does not authorize Stage 8.

set -Eeuo pipefail

readonly COLLECTOR_VERSION="stage8-clock-evidence-v1"
readonly PROTOCOL_VERSION="2.0.0-pre.1"

usage() {
  cat <<'EOF'
Usage:
  collect_stage8_clock_evidence.sh --cpus CPU_LIST [--output FILE] [--repo DIR]

Required:
  --cpus CPU_LIST  Explicit Linux CPU-list syntax, for example 2,18 or 2-3,18.
                   Every selected CPU must exist and be available to this process.

Optional:
  --output FILE    New .tar.gz archive to create. The file must not already exist.
                   Default: ./stage8-clock-evidence-<UTC>.tar.gz
  --repo DIR       Repository root. Default: parent of this script's directory.
  -h, --help       Show this help.

The collector performs no package installation, network access, sudo, MSR access,
hardware-state mutation, or performance experiment. It records unavailable tools
and permission failures in collection_issues.tsv rather than hiding them.
EOF
}

die() {
  printf 'collect-stage8-clock-evidence: ERROR: %s\n' "$*" >&2
  exit 1
}

CPUS_RAW=""
OUTPUT_ARG=""
SCRIPT_PATH="$(realpath "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)"

while (($# > 0)); do
  case "$1" in
    --cpus)
      (($# >= 2)) || die "--cpus requires a value"
      CPUS_RAW="$2"
      shift 2
      ;;
    --output)
      (($# >= 2)) || die "--output requires a value"
      OUTPUT_ARG="$2"
      shift 2
      ;;
    --repo)
      (($# >= 2)) || die "--repo requires a value"
      REPO_ROOT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown argument: $1"
      ;;
  esac
done

[[ -n "$CPUS_RAW" ]] || die "--cpus is required; do not infer stand CPUs"
[[ "$CPUS_RAW" != *[[:space:]]* ]] || die "--cpus must not contain whitespace"
[[ "$(uname -s)" == "Linux" ]] || die "this collector supports Linux only"

for required_command in realpath sha256sum tar find sort taskset lscpu; do
  command -v "$required_command" >/dev/null 2>&1 ||
    die "required command is unavailable: $required_command"
done

if command -v python3.14 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3.14)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
else
  die "python3.14 or python3 is required for independent manifest verification"
fi

REPO_ROOT="$(realpath "$REPO_ROOT")"
[[ -f "$REPO_ROOT/AGENTS.md" ]] || die "not a repository root: $REPO_ROOT"
[[ -f "$REPO_ROOT/protocol/$PROTOCOL_VERSION/IMPORT_MANIFEST.json" ]] ||
  die "protocol/$PROTOCOL_VERSION/IMPORT_MANIFEST.json is missing"

declare -a SELECTED_CPUS=()
declare -A SEEN_CPUS=()
IFS=',' read -r -a CPU_TERMS <<<"$CPUS_RAW"
for term in "${CPU_TERMS[@]}"; do
  [[ -n "$term" ]] || die "empty term in --cpus: $CPUS_RAW"
  if [[ "$term" =~ ^([0-9]+)$ ]]; then
    start_cpu="${BASH_REMATCH[1]}"
    end_cpu="$start_cpu"
  elif [[ "$term" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    start_cpu="${BASH_REMATCH[1]}"
    end_cpu="${BASH_REMATCH[2]}"
    ((end_cpu >= start_cpu)) || die "descending CPU range is invalid: $term"
  else
    die "invalid CPU-list term: $term"
  fi

  ((end_cpu - start_cpu <= 8192)) || die "CPU range is unreasonably large: $term"
  for ((cpu = start_cpu; cpu <= end_cpu; ++cpu)); do
    [[ -z "${SEEN_CPUS[$cpu]+present}" ]] || die "duplicate CPU in --cpus: $cpu"
    [[ -d "/sys/devices/system/cpu/cpu$cpu" ]] || die "CPU $cpu does not exist"
    taskset -c "$cpu" true >/dev/null 2>&1 ||
      die "CPU $cpu is not online or is unavailable to this process's cpuset"
    SEEN_CPUS[$cpu]=1
    SELECTED_CPUS+=("$cpu")
  done
done
(( ${#SELECTED_CPUS[@]} > 0 )) || die "--cpus selected no CPUs"

NORMALIZED_CPUS="$(IFS=,; printf '%s' "${SELECTED_CPUS[*]}")"
UTC_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ -z "$OUTPUT_ARG" ]]; then
  OUTPUT_ARG="$PWD/stage8-clock-evidence-$UTC_STAMP.tar.gz"
fi

OUTPUT_PARENT="$(dirname "$OUTPUT_ARG")"
OUTPUT_BASENAME="$(basename "$OUTPUT_ARG")"
[[ -d "$OUTPUT_PARENT" ]] || die "output directory does not exist: $OUTPUT_PARENT"
OUTPUT_PARENT="$(cd "$OUTPUT_PARENT" && pwd -P)"
OUTPUT_PATH="$OUTPUT_PARENT/$OUTPUT_BASENAME"
[[ "$OUTPUT_BASENAME" != "." && "$OUTPUT_BASENAME" != ".." ]] ||
  die "invalid output file name"
[[ "$OUTPUT_PATH" == *.tar.gz ]] || die "--output must end in .tar.gz"
[[ ! -e "$OUTPUT_PATH" ]] || die "refusing to overwrite existing output: $OUTPUT_PATH"
[[ ! -L "$OUTPUT_PATH" ]] || die "refusing to replace output symlink: $OUTPUT_PATH"

umask 077
TMP_BASE="${TMPDIR:-/tmp}"
[[ -d "$TMP_BASE" && -w "$TMP_BASE" ]] || die "temporary directory is not writable: $TMP_BASE"
WORK_DIR="$(mktemp -d "$TMP_BASE/cpu-prefetch-stage8-clock.XXXXXX")"
BUNDLE_NAME="stage8-clock-evidence-$UTC_STAMP"
EVIDENCE_DIR="$WORK_DIR/$BUNDLE_NAME"
PARTIAL_OUTPUT="$OUTPUT_PATH.partial.$$"
mkdir -p "$EVIDENCE_DIR"

cleanup() {
  if [[ -n "${PARTIAL_OUTPUT:-}" && -f "$PARTIAL_OUTPUT" ]]; then
    rm -f -- "$PARTIAL_OUTPUT"
  fi
  if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" &&
        "$WORK_DIR" == "$TMP_BASE"/cpu-prefetch-stage8-clock.* ]]; then
    rm -rf -- "$WORK_DIR"
  fi
}
trap cleanup EXIT HUP INT TERM

ISSUES_FILE="$EVIDENCE_DIR/collection_issues.tsv"
printf 'severity\tcategory\tdetail\n' >"$ISSUES_FILE"
critical_count=0

record_issue() {
  local severity="$1"
  local category="$2"
  local detail="$3"
  detail="${detail//$'\t'/ }"
  detail="${detail//$'\n'/ }"
  printf '%s\t%s\t%s\n' "$severity" "$category" "$detail" >>"$ISSUES_FILE"
  if [[ "$severity" == "CRITICAL" ]]; then
    ((critical_count += 1))
  fi
}

print_command() {
  printf 'command:'
  printf ' %q' "$@"
  printf '\n'
}

capture_command() {
  local relative_path="$1"
  shift
  local output_file="$EVIDENCE_DIR/$relative_path"
  local exit_code
  mkdir -p "$(dirname "$output_file")"
  {
    print_command "$@"
    printf '%s\n' '--- output ---'
    if "$@"; then
      exit_code=0
    else
      exit_code=$?
    fi
    printf '\n--- exit_code=%d ---\n' "$exit_code"
  } >"$output_file" 2>&1
  if ((exit_code != 0)); then
    record_issue "WARNING" "command_failed" "$relative_path exited $exit_code"
  fi
}

capture_optional_command() {
  local relative_path="$1"
  local command_name="$2"
  shift 2
  if command -v "$command_name" >/dev/null 2>&1; then
    capture_command "$relative_path" "$command_name" "$@"
  else
    mkdir -p "$(dirname "$EVIDENCE_DIR/$relative_path")"
    printf 'UNAVAILABLE: command not installed: %s\n' "$command_name" \
      >"$EVIDENCE_DIR/$relative_path"
    record_issue "INFO" "tool_unavailable" "$command_name"
  fi
}

snapshot_paths() {
  local relative_path="$1"
  shift
  local output_file="$EVIDENCE_DIR/$relative_path"
  local source_path
  mkdir -p "$(dirname "$output_file")"
  : >"$output_file"
  for source_path in "$@"; do
    printf '\n### %s\n' "$source_path" >>"$output_file"
    if [[ -f "$source_path" && -r "$source_path" ]]; then
      if ! cat -- "$source_path" >>"$output_file" 2>&1; then
        record_issue "WARNING" "read_failed" "$source_path"
      fi
      printf '\n' >>"$output_file"
    elif [[ -e "$source_path" ]]; then
      printf 'UNREADABLE_OR_NOT_REGULAR\n' >>"$output_file"
      record_issue "INFO" "path_unreadable" "$source_path"
    else
      printf 'UNAVAILABLE\n' >>"$output_file"
      record_issue "INFO" "path_unavailable" "$source_path"
    fi
  done
}

snapshot_tree() {
  local relative_path="$1"
  local source_root="$2"
  local max_depth="$3"
  local output_file="$EVIDENCE_DIR/$relative_path"
  local source_path
  local found=0
  local -a source_paths=()
  mkdir -p "$(dirname "$output_file")"
  : >"$output_file"
  if [[ ! -e "$source_root" ]]; then
    printf 'UNAVAILABLE: %s\n' "$source_root" >"$output_file"
    record_issue "INFO" "path_unavailable" "$source_root"
    return
  fi
  while IFS= read -r -d '' source_path; do
    source_paths+=("$source_path")
  done < <(find "$source_root" -maxdepth "$max_depth" -type f -readable -print0 | sort -z)
  for source_path in "${source_paths[@]}"; do
    found=1
    printf '\n### %s\n' "$source_path" >>"$output_file"
    if ! cat -- "$source_path" >>"$output_file" 2>&1; then
      record_issue "WARNING" "read_failed" "$source_path"
    fi
    printf '\n' >>"$output_file"
  done
  if ((found == 0)); then
    printf 'NO_READABLE_REGULAR_FILES: %s\n' "$source_root" >"$output_file"
    record_issue "INFO" "tree_empty" "$source_root"
  fi
}

capture_redacted_kernel_command_line() {
  local output_file="$EVIDENCE_DIR/host/kernel-command-line.txt"
  mkdir -p "$(dirname "$output_file")"
  if "$PYTHON_BIN" - /proc/cmdline <<'PY' >"$output_file" 2>&1
import hashlib
import sys
from pathlib import Path


source = Path(sys.argv[1])
raw = source.read_bytes()
text = raw.decode("utf-8").strip()
redacted_keys = {
    "bootdev",
    "cryptdevice",
    "ip",
    "nfsroot",
    "rd.luks.key",
    "rd.luks.name",
    "rd.luks.uuid",
    "resume",
    "root",
}
tokens = []
redacted = []
for token in text.split():
    key, separator, value = token.partition("=")
    if separator and (key in redacted_keys or key.startswith("iscsi_")):
        tokens.append(f"{key}=<REDACTED>")
        redacted.append(key)
    else:
        tokens.append(token)

print("source=/proc/cmdline")
print(f"source_sha256={hashlib.sha256(raw).hexdigest()}")
print("redaction_policy=identity-bearing boot/storage/network values only")
print(f"redacted_keys={','.join(redacted) if redacted else 'none'}")
print(f"redacted_command_line={' '.join(tokens)}")
PY
  then
    printf '\n--- exit_code=0 ---\n' >>"$output_file"
  else
    command_line_rc=$?
    printf '\n--- exit_code=%d ---\n' "$command_line_rc" >>"$output_file"
    record_issue "WARNING" "kernel_command_line_redaction_failed" \
      "redaction helper exited $command_line_rc"
  fi
}

cat >"$EVIDENCE_DIR/README.txt" <<EOF
D-009 Stage 8 clock decision evidence

Collector version: $COLLECTOR_VERSION
Protocol version:  $PROTOCOL_VERSION
Collection UTC:    $UTC_STAMP
Selected CPUs:     $NORMALIZED_CPUS

Scope:
- read-only capability and configuration evidence;
- exact repository/protocol binding;
- no clock source, conversion, serialization sequence, or acceptance limit is selected;
- no skew, drift, resolution-distribution, or read-cost qualification is claimed;
- no Stage 8 implementation, pilot, or performance experiment is authorized.

Review collection_issues.tsv first. CRITICAL entries mean the archive cannot be
used as clean protocol-bound evidence. INFO/WARNING entries identify evidence
that was unavailable or commands that failed and must not be silently inferred.

Privacy: this archive contains hostname, CPU, kernel, firmware product, affinity,
repository-state, and kernel-log excerpts. Review it before sharing. It excludes
environment variables, machine-id, DMI UUIDs, and serial-number fields by design.
EOF

cat >"$EVIDENCE_DIR/collection_metadata.txt" <<EOF
collector_version=$COLLECTOR_VERSION
collector_path=$SCRIPT_PATH
protocol_version=$PROTOCOL_VERSION
collection_utc=$UTC_STAMP
collection_local=$(date --iso-8601=seconds)
timezone_name=$(date +%Z)
timezone_offset=$(date +%:z)
selected_cpus_input=$CPUS_RAW
selected_cpus_normalized=$NORMALIZED_CPUS
repository_root=$REPO_ROOT
effective_uid=$(id -u)
effective_gid=$(id -g)
EOF

mkdir -p "$EVIDENCE_DIR/collector"
cp -- "$SCRIPT_PATH" "$EVIDENCE_DIR/collector/collect_stage8_clock_evidence.sh"
(
  cd "$EVIDENCE_DIR/collector"
  sha256sum collect_stage8_clock_evidence.sh >collector.sha256
)

# Host, OS, process constraints, and virtualization context.
capture_command "host/uname.txt" uname -a
capture_optional_command "host/os-release.txt" cat /etc/os-release
capture_optional_command "host/hostname.txt" hostname
capture_optional_command "host/virtualization.txt" systemd-detect-virt --vm --container
capture_optional_command "host/locale.txt" locale
capture_optional_command "host/uptime.txt" uptime
capture_optional_command "host/memory.txt" free -b
capture_optional_command "host/mounts.txt" findmnt --kernel --real
capture_optional_command "host/cgroups.txt" cat /proc/self/cgroup
capture_optional_command "host/process-status.txt" cat /proc/self/status
capture_command "host/current-affinity.txt" taskset -pc "$$"
capture_command "host/limits.txt" bash -c 'ulimit -a'
capture_redacted_kernel_command_line
snapshot_paths "host/kernel-hostname.txt" /proc/sys/kernel/hostname
snapshot_paths "host/cpu-global-sysfs.txt" \
  /sys/devices/system/cpu/possible \
  /sys/devices/system/cpu/present \
  /sys/devices/system/cpu/online \
  /sys/devices/system/cpu/offline \
  /sys/devices/system/cpu/isolated \
  /sys/devices/system/cpu/nohz_full \
  /sys/devices/system/cpu/smt/active \
  /sys/devices/system/cpu/smt/control

# CPU topology, feature flags, cache topology, microcode, and frequency controls.
capture_command "cpu/lscpu.txt" lscpu
capture_command "cpu/lscpu-json.txt" lscpu --json
capture_command "cpu/lscpu-extended.txt" \
  lscpu --extended=CPU,NODE,SOCKET,CORE,CACHE,ONLINE,MAXMHZ,MINMHZ
snapshot_paths "cpu/proc-cpuinfo.txt" /proc/cpuinfo
capture_optional_command "cpu/numa-hardware.txt" numactl --hardware
capture_optional_command "cpu/hwloc.txt" lstopo-no-graphics
snapshot_tree "cpu/vulnerabilities.txt" /sys/devices/system/cpu/vulnerabilities 1
snapshot_tree "cpu/cpufreq-policies.txt" /sys/devices/system/cpu/cpufreq 3
snapshot_tree "cpu/intel-pstate.txt" /sys/devices/system/cpu/intel_pstate 2
snapshot_tree "cpu/amd-pstate.txt" /sys/devices/system/cpu/amd_pstate 2

for cpu in "${SELECTED_CPUS[@]}"; do
  snapshot_tree "cpu/selected/cpu$cpu-sysfs.txt" \
    "/sys/devices/system/cpu/cpu$cpu" 4
  if command -v cpuid >/dev/null 2>&1; then
    capture_command "cpu/selected/cpu$cpu-cpuid-raw.txt" \
      taskset -c "$cpu" cpuid -1 -r
  else
    printf 'UNAVAILABLE: cpuid utility is not installed\n' \
      >"$EVIDENCE_DIR/cpu/selected/cpu$cpu-cpuid-raw.txt"
    record_issue "WARNING" "tool_unavailable" \
      "cpuid; raw per-core CPUID leaves were not collected"
  fi
  if command -v cpupower >/dev/null 2>&1; then
    capture_command "cpu/selected/cpu$cpu-cpupower-frequency.txt" \
      cpupower -c "$cpu" frequency-info
  else
    printf 'UNAVAILABLE: cpupower utility is not installed\n' \
      >"$EVIDENCE_DIR/cpu/selected/cpu$cpu-cpupower-frequency.txt"
    record_issue "INFO" "tool_unavailable" "cpupower"
  fi
done

# Clocksource, clockevent, timekeeping, kernel, and firmware context.
snapshot_tree "clock/clocksource-sysfs.txt" /sys/devices/system/clocksource 4
for cpu in "${SELECTED_CPUS[@]}"; do
  snapshot_tree "clock/clockevent-cpu$cpu.txt" \
    "/sys/devices/system/clockevents/clockevent$cpu" 3
done
snapshot_tree "clock/clockevent-broadcast.txt" \
  /sys/devices/system/clockevents/broadcast 3
snapshot_paths "clock/kernel-timekeeping-inputs.txt" \
  /proc/timer_list \
  /proc/interrupts
capture_optional_command "clock/timedatectl.txt" timedatectl show --all
capture_optional_command "clock/adjtimex.txt" adjtimex --print
capture_command "clock/dmesg-clock-excerpt.txt" bash -o pipefail -c \
  "dmesg --color=never 2>&1 | awk 'BEGIN { IGNORECASE=1 } /tsc|clocksource|clockevent|hpet|timekeeping|unstable/'"

if "$PYTHON_BIN" - <<'PY' >"$EVIDENCE_DIR/clock/posix-clock-capabilities.txt" 2>&1
import ctypes
import errno
import json
import os
import platform
import time


class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


libc = ctypes.CDLL(None, use_errno=True)
clock_getres = libc.clock_getres
clock_getres.argtypes = [ctypes.c_int, ctypes.POINTER(Timespec)]
clock_getres.restype = ctypes.c_int
clock_gettime = libc.clock_gettime
clock_gettime.argtypes = [ctypes.c_int, ctypes.POINTER(Timespec)]
clock_gettime.restype = ctypes.c_int

linux_clock_ids = {
    "CLOCK_REALTIME": 0,
    "CLOCK_MONOTONIC": 1,
    "CLOCK_MONOTONIC_RAW": 4,
    "CLOCK_BOOTTIME": 7,
    "CLOCK_TAI": 11,
}
result = {
    "platform": platform.platform(),
    "python": platform.python_version(),
    "stdlib": {
        name: {
            "adjustable": info.adjustable,
            "implementation": info.implementation,
            "monotonic": info.monotonic,
            "resolution_seconds": info.resolution,
        }
        for name in ("monotonic", "perf_counter", "process_time", "thread_time", "time")
        for info in (time.get_clock_info(name),)
    },
    "linux_clock_getres": {},
}
for name, clock_id in linux_clock_ids.items():
    resolution = Timespec()
    sample = Timespec()
    ctypes.set_errno(0)
    res_rc = clock_getres(clock_id, ctypes.byref(resolution))
    res_errno = ctypes.get_errno()
    ctypes.set_errno(0)
    time_rc = clock_gettime(clock_id, ctypes.byref(sample))
    time_errno = ctypes.get_errno()
    result["linux_clock_getres"][name] = {
        "clock_id": clock_id,
        "getres_rc": res_rc,
        "getres_errno": errno.errorcode.get(res_errno, str(res_errno)),
        "resolution_seconds": resolution.tv_sec,
        "resolution_nanoseconds": resolution.tv_nsec,
        "gettime_rc": time_rc,
        "gettime_errno": errno.errorcode.get(time_errno, str(time_errno)),
        "single_sample_seconds": sample.tv_sec,
        "single_sample_nanoseconds": sample.tv_nsec,
    }
print(json.dumps(result, indent=2, sort_keys=True))
PY
then
  printf '\n--- exit_code=0 ---\n' >>"$EVIDENCE_DIR/clock/posix-clock-capabilities.txt"
else
  clock_probe_rc=$?
  printf '\n--- exit_code=%d ---\n' "$clock_probe_rc" \
    >>"$EVIDENCE_DIR/clock/posix-clock-capabilities.txt"
  record_issue "WARNING" "clock_capability_probe_failed" \
    "Python clock_getres probe exited $clock_probe_rc"
fi

kernel_release="$(uname -r)"
mkdir -p "$EVIDENCE_DIR/kernel"
if [[ -r /proc/config.gz ]] && command -v gzip >/dev/null 2>&1; then
  capture_command "kernel/config.txt" gzip -cd /proc/config.gz
elif [[ -r "/boot/config-$kernel_release" ]]; then
  snapshot_paths "kernel/config.txt" "/boot/config-$kernel_release"
else
  printf 'UNAVAILABLE: neither /proc/config.gz nor /boot/config-%s is readable\n' \
    "$kernel_release" >"$EVIDENCE_DIR/kernel/config.txt"
  record_issue "INFO" "kernel_config_unavailable" "$kernel_release"
fi
capture_optional_command "kernel/sysctl-clock-context.txt" sysctl \
  kernel.nmi_watchdog kernel.perf_event_paranoid kernel.sched_rt_runtime_us

snapshot_paths "firmware/dmi-allowlist.txt" \
  /sys/class/dmi/id/sys_vendor \
  /sys/class/dmi/id/product_name \
  /sys/class/dmi/id/product_version \
  /sys/class/dmi/id/board_vendor \
  /sys/class/dmi/id/board_name \
  /sys/class/dmi/id/board_version \
  /sys/class/dmi/id/bios_vendor \
  /sys/class/dmi/id/bios_version \
  /sys/class/dmi/id/bios_date \
  /sys/class/dmi/id/chassis_vendor \
  /sys/class/dmi/id/chassis_type

# Exact toolchain identities; absent secondary tools remain visible gaps.
mkdir -p "$EVIDENCE_DIR/toolchain"
{
  printf 'collector PATH entries are intentionally not recorded\n'
  for tool in bash git cmake ninja gcc g++ clang clang++ ld as objdump llvm-objdump \
              python3 python3.14 openssl tar sha256sum cpuid cpupower numactl; do
    if command -v "$tool" >/dev/null 2>&1; then
      printf '%s\t%s\n' "$tool" "$(command -v "$tool")"
    else
      printf '%s\tUNAVAILABLE\n' "$tool"
    fi
  done
} >"$EVIDENCE_DIR/toolchain/paths.tsv"
capture_optional_command "toolchain/bash-version.txt" bash --version
capture_optional_command "toolchain/git-version.txt" git --version
capture_optional_command "toolchain/cmake-version.txt" cmake --version
capture_optional_command "toolchain/ninja-version.txt" ninja --version
capture_optional_command "toolchain/gcc-version.txt" gcc -v
capture_optional_command "toolchain/gxx-version.txt" g++ -v
capture_optional_command "toolchain/clang-version.txt" clang --version
capture_optional_command "toolchain/clangxx-version.txt" clang++ --version
capture_optional_command "toolchain/libc-version.txt" ldd --version
capture_optional_command "toolchain/binutils-version.txt" objdump --version
capture_optional_command "toolchain/llvm-objdump-version.txt" llvm-objdump --version
capture_command "toolchain/python-version.txt" "$PYTHON_BIN" --version
capture_optional_command "toolchain/openssl-version.txt" openssl version -a

# Bind the evidence to the repository state and immutable imported protocol.
mkdir -p "$EVIDENCE_DIR/repository"
if [[ -d "$REPO_ROOT/.git" ]] && command -v git >/dev/null 2>&1; then
  capture_command "repository/git-revision.txt" git -C "$REPO_ROOT" rev-parse HEAD
  capture_command "repository/git-describe.txt" \
    git -C "$REPO_ROOT" describe --always --dirty --broken
  capture_command "repository/git-status-porcelain-v2.txt" \
    git -C "$REPO_ROOT" status --porcelain=v2 --branch --untracked-files=all
  capture_command "repository/git-submodules.txt" \
    git -C "$REPO_ROOT" submodule status --recursive
else
  printf 'UNAVAILABLE: repository has no readable .git directory\n' \
    >"$EVIDENCE_DIR/repository/git-revision.txt"
  record_issue "WARNING" "git_metadata_unavailable" "$REPO_ROOT"
fi

capture_command "repository/protocol-file-sha256.txt" bash -o pipefail -c '
  cd "$1"
  find "protocol/$2" -type f -print0 | sort -z | xargs -0 sha256sum
' _ "$REPO_ROOT" "$PROTOCOL_VERSION"

cp -- "$REPO_ROOT/protocol/$PROTOCOL_VERSION/IMPORT_MANIFEST.json" \
  "$EVIDENCE_DIR/repository/IMPORT_MANIFEST.json"
for repository_file in \
  AGENTS.md \
  STATUS.md \
  PLAN.md \
  config/dependencies.json \
  docs/IMPLEMENTATION_DECISIONS.md \
  docs/DECISIONS_REQUIRED.md \
  docs/ARCHITECTURE.md \
  docs/DATA_FLOW.md \
  docs/TEST_STRATEGY.md \
  docs/TRACEABILITY_MATRIX.md \
  docs/RISK_REGISTER.md \
  docs/decisions/0008-linux-x86-64-target-family.md \
  docs/decisions/0016-generated-code-evidence-policy.md \
  docs/decisions/0018-unprivileged-measurement-and-control-boundary.md \
  docs/decisions/0019-linux-platform-control-interface.md \
  docs/decisions/0029-stage7-schedule-generation-suite.md; do
  if [[ -f "$REPO_ROOT/$repository_file" ]]; then
    printf '%s  %s\n' "$(sha256sum "$REPO_ROOT/$repository_file" | awk '{print $1}')" \
      "$repository_file" >>"$EVIDENCE_DIR/repository/decision-input-sha256.txt"
  else
    printf 'UNAVAILABLE  %s\n' "$repository_file" \
      >>"$EVIDENCE_DIR/repository/decision-input-sha256.txt"
    record_issue "WARNING" "repository_file_unavailable" "$repository_file"
  fi
done

protocol_verify_output="$EVIDENCE_DIR/repository/protocol-manifest-verification.txt"
if "$PYTHON_BIN" - "$REPO_ROOT" "$PROTOCOL_VERSION" <<'PY' >"$protocol_verify_output" 2>&1
import hashlib
import json
import re
import sys
from pathlib import Path


root = Path(sys.argv[1]).resolve()
version = sys.argv[2]
snapshot = root / "protocol" / version
manifest_path = snapshot / "IMPORT_MANIFEST.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("protocol_version") != version:
    raise SystemExit("FAIL: protocol_version mismatch")

declared = set()
for artifact in manifest.get("artifacts", []):
    relative = Path(artifact["imported_relative_path"])
    path = root / relative
    declared.add(relative)
    if not path.is_file():
        raise SystemExit(f"FAIL: missing {relative}")
    size = path.stat().st_size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if size != artifact["file_size_bytes"]:
        raise SystemExit(f"FAIL: size mismatch {relative}: {size}")
    if digest != artifact["sha256"]:
        raise SystemExit(f"FAIL: SHA-256 mismatch {relative}: {digest}")

actual = {
    path.relative_to(root)
    for path in snapshot.rglob("*")
    if path.is_file() and path != manifest_path
}
if actual != declared:
    missing = sorted(str(path) for path in declared - actual)
    extra = sorted(str(path) for path in actual - declared)
    raise SystemExit(f"FAIL: inventory mismatch missing={missing} extra={extra}")

version_record = snapshot / "handoff" / "PROTOCOL_VERSION.md"
current_section = version_record.read_text(encoding="utf-8").split(
    "## Current authoritative hashes", maxsplit=1
)[1]
authoritative = {
    "paper/main.pdf": snapshot / "main.pdf",
    "EXPERIMENT_IMPLEMENTATION_SPEC.md": snapshot / "EXPERIMENT_IMPLEMENTATION_SPEC.md",
    "PROTOCOL_FREEZE_CHECKLIST.md": snapshot / "PROTOCOL_FREEZE_CHECKLIST.md",
    "AGENTS.md": snapshot / "PAPER_AGENTS.md",
}
for declared_name, path in authoritative.items():
    match = re.search(
        rf"\| `{re.escape(declared_name)}` \| `([0-9a-f]{{64}})` \|",
        current_section,
    )
    if match is None:
        raise SystemExit(f"FAIL: no authoritative hash for {declared_name}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != match.group(1):
        raise SystemExit(f"FAIL: authoritative SHA-256 mismatch {declared_name}: {digest}")

print(
    f"PASS: {len(declared)} imported artifacts match size, SHA-256, and inventory; "
    f"{len(authoritative)} current authoritative hashes match"
)
PY
then
  printf '\n--- exit_code=0 ---\n' >>"$protocol_verify_output"
else
  protocol_verify_rc=$?
  printf '\n--- exit_code=%d ---\n' "$protocol_verify_rc" >>"$protocol_verify_output"
  record_issue "CRITICAL" "protocol_manifest_verification_failed" \
    "independent verifier exited $protocol_verify_rc"
fi

if [[ -f "$REPO_ROOT/tools/check_protocol.py" ]]; then
  capture_command "repository/full-protocol-check.txt" \
    "$PYTHON_BIN" "$REPO_ROOT/tools/check_protocol.py"
else
  printf 'UNAVAILABLE: tools/check_protocol.py\n' \
    >"$EVIDENCE_DIR/repository/full-protocol-check.txt"
  record_issue "WARNING" "repository_file_unavailable" "tools/check_protocol.py"
fi

while IFS= read -r -d '' metadata_file; do
  relative_metadata="${metadata_file#"$REPO_ROOT"/}"
  safe_name="${relative_metadata//\//__}"
  cp -- "$metadata_file" "$EVIDENCE_DIR/repository/$safe_name"
done < <(find "$REPO_ROOT" -path '*/generated/version_metadata.json' -type f -print0 | sort -z)

warning_count="$(awk -F '\t' '$1 == "WARNING" {count++} END {print count+0}' "$ISSUES_FILE")"
info_count="$(awk -F '\t' '$1 == "INFO" {count++} END {print count+0}' "$ISSUES_FILE")"
cat >>"$EVIDENCE_DIR/collection_metadata.txt" <<EOF
critical_issue_count=$critical_count
warning_issue_count=$warning_count
info_issue_count=$info_count
EOF

(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS
)
chmod -R go-rwx "$EVIDENCE_DIR"
tar -C "$WORK_DIR" -czf "$PARTIAL_OUTPUT" "$BUNDLE_NAME"
mv -- "$PARTIAL_OUTPUT" "$OUTPUT_PATH"

archive_hash="$(sha256sum "$OUTPUT_PATH" | awk '{print $1}')"
printf 'collect-stage8-clock-evidence: archive=%s\n' "$OUTPUT_PATH"
printf 'collect-stage8-clock-evidence: sha256=%s\n' "$archive_hash"
printf 'collect-stage8-clock-evidence: selected_cpus=%s\n' "$NORMALIZED_CPUS"
printf 'collect-stage8-clock-evidence: issues=critical:%d,warning:%s,info:%s\n' \
  "$critical_count" "$warning_count" "$info_count"
printf '%s\n' \
  'Review the archive for hostname/firmware/kernel information before sharing it.'

if ((critical_count > 0)); then
  printf '%s\n' \
    'collect-stage8-clock-evidence: archive retained, but critical evidence failed.' >&2
  exit 2
fi
