#!/usr/bin/env python3
"""Fixed fail-closed executor for a later exactly authorized P4-R-C action.

Repository verification may run only ``--self-test`` and ``--describe-contract``.
The ``--execute`` path requires a complete canonical D-104 authorization,
detached P4-K signature, and accepted single-owner pre-execution review.  None
of those action records exists in the no-authority implementation state.
"""

from __future__ import annotations

import argparse
import dataclasses
from datetime import UTC, datetime
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import sys
import tempfile
import threading
from typing import Any, BinaryIO, Protocol


ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "2.0.0-pre.2"
STAND_ID = "XEON-CPU-FETCH"
DESTINATION = "root@185.184.131.153"
SSH = pathlib.Path("/usr/bin/ssh")
SSH_KEYGEN = pathlib.Path("/usr/bin/ssh-keygen")
TRANSPORT_PRIVATE = pathlib.Path("/home/omaltsev/.ssh/id_ed25519")
TRANSPORT_PUBLIC = pathlib.Path("/home/omaltsev/.ssh/id_ed25519.pub")
PINNED_HOSTS = ROOT / "config/q15/q15-r-p4-r-i-d099-pinned-host-v1.known_hosts"
TARGET_ALLOWED_SIGNERS = pathlib.Path(
    "/home/omaltsev/.local/share/cpu-prefetch-q15/p4-k-v2/public/target_allowed_signers"
)

ARCHIVE = ROOT / (
    "build/release-gcc/q15-qualification-tool-bundle/"
    "cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1.tar.gz"
)
SIDECAR = pathlib.Path(str(ARCHIVE) + ".sha256")
ARCHIVE_SHA256 = "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a"
ARCHIVE_BYTES = 4642298
SELECTED_RELEASE_SHA256 = (
    "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01"
)
COLLECTOR_SHA256 = "4716e1dfc2e65fd61dce1ea54a70fd876a0b4322b69d9ad1fde5c67a65c48a57"
CONTRACT_SHA256 = "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87"
# D-102 makes remote tool bytes compatibility identity.  D-099 did not capture
# /usr/bin/python3, /usr/bin/dd, or the Python tar runtime, so action execution
# remains deliberately impossible until a prospective successor freezes that
# evidence or an explicit compatibility-risk acceptance.
REMOTE_RUNTIME_ACCEPTANCE_SHA256: str | None = None

CAPTURE_ID = "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01"
CUSTODY_ROOT = ROOT / "docs/evidence/stage17" / CAPTURE_ID
IDENTITY = CUSTODY_ROOT / "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json"
IDENTITY_SIDECAR = pathlib.Path(str(IDENTITY) + ".sha256")
IDENTITY_REVIEW = CUSTODY_ROOT / (
    "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.owner-review.json"
)
IDENTITY_REVIEW_SIDECAR = pathlib.Path(str(IDENTITY_REVIEW) + ".sha256")
IDENTITY_MANIFEST = CUSTODY_ROOT / "SHA256SUMS"
COLLECTOR_STDOUT = CUSTODY_ROOT / f"{CAPTURE_ID}.json"
COLLECTOR_STDERR = CUSTODY_ROOT / f"{CAPTURE_ID}.stderr.bin"
COLLECTOR_SIDECAR = pathlib.Path(str(COLLECTOR_STDOUT) + ".sha256")
TRANSFER_RECEIPT = CUSTODY_ROOT / f"{CAPTURE_ID}.transfer-receipt.json"
OWNER_REVIEW = CUSTODY_ROOT / f"{CAPTURE_ID}.independent-review.json"
FAILURE = CUSTODY_ROOT / f"{CAPTURE_ID}.failure.json"

EXPECTED_PREDECESSORS = {
    IDENTITY.name: "774aca6d192a9adaeeb3daf7bc357c61e957c5b2e6169c9db82cf7722cc3dab6",
    IDENTITY_SIDECAR.name: "15e6b3579fc2844cc4fdb76f73a68495ddf4fab50928733db62545740257bafc",
    IDENTITY_REVIEW.name: "f01e14303f305210819d633345cf454eb6985e394ab36b30e167491374b3b037",
    IDENTITY_REVIEW_SIDECAR.name: "29fa86edd128552203708314b25d03bee7263fa7f560ea459b54ce1c19a420f1",
    IDENTITY_MANIFEST.name: "72ff382125f19a900ef22cad83011ce5dfb0c91e1c676168fe0b9e472892f3ff",
}

REMOTE_NAMESPACE = "/root/cpu-prefetch-q15-r-p4-r"
REMOTE_TRANSACTION = f"{REMOTE_NAMESPACE}/{CAPTURE_ID}"
REMOTE_INCOMING = f"{REMOTE_TRANSACTION}/incoming"
REMOTE_RELEASE_PARENT = f"{REMOTE_TRANSACTION}/release"
TOP_LEVEL = "cpu-prefetch-q15-qualification-tool-2.0.0-34da95d-clean-5fc75063e1d1"
REMOTE_RELEASE = f"{REMOTE_RELEASE_PARENT}/{TOP_LEVEL}"
REMOTE_ARCHIVE = f"{REMOTE_INCOMING}/{ARCHIVE.name}"
REMOTE_SIDECAR = f"{REMOTE_INCOMING}/{SIDECAR.name}"
REMOTE_COLLECTOR = f"{REMOTE_RELEASE}/release/bin/cpu_prefetch_q15_prestate_collector"
REMOTE_VALIDATOR = f"{REMOTE_RELEASE}/tools/validate_q15_r_prestate.py"

MAX_STDOUT = 1 << 20
MAX_STDERR = 1 << 20
TOTAL_WATCHDOG_SECONDS = 900
COMMAND_TIMEOUT_SECONDS = 30
HASH_RE = re.compile(r"^[0-9a-f]{64}$")
NANO_UTC_RE = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{9}Z$"
)
SAFE_REMOTE_RE = re.compile(r"^[A-Za-z0-9_./:=@+,-]+(?: [A-Za-z0-9_./:=@+,-]+)*$")

SELF_TEST_OUTPUT = (
    b"q15-prestate-self-test: PASS commands=25 shell=NONE stand=NOT_ACCESSED "
    b"execution=NOT_STARTED authority=NONE\n"
)
DESCRIBE_OUTPUT = (
    b"contract=Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1 "
    b"contract_sha256=4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87 "
    b"commands=25 retries=0 timeout_seconds=30 total_watchdog_seconds=900 "
    b"shell=false inherited_environment=false mutation=false stand_access=false "
    b"execution=false authority=NONE\n"
)


class ActionError(RuntimeError):
    """A fail-closed D-104 action error."""


class PlanFailure(ActionError):
    """A terminal remote-plan failure with bounded retained evidence."""

    def __init__(
        self,
        phase: str,
        message: str,
        completed: list[str],
        stdout: bytes = b"",
        stderr: bytes = b"",
    ) -> None:
        super().__init__(message)
        self.phase = phase
        self.completed = list(completed)
        self.stdout = stdout
        self.stderr = stderr


@dataclasses.dataclass(frozen=True)
class Result:
    returncode: int
    stdout: bytes = b""
    stderr: bytes = b""


@dataclasses.dataclass(frozen=True)
class Step:
    identifier: str
    operation: str


@dataclasses.dataclass(frozen=True)
class OutputPaths:
    stdout: pathlib.Path
    stderr: pathlib.Path
    sidecar: pathlib.Path
    receipt: pathlib.Path
    review: pathlib.Path
    failure: pathlib.Path


OUTPUTS = OutputPaths(
    COLLECTOR_STDOUT,
    COLLECTOR_STDERR,
    COLLECTOR_SIDECAR,
    TRANSFER_RECEIPT,
    OWNER_REVIEW,
    FAILURE,
)


STEPS = (
    Step("P4RC-001", "VALIDATE_AUTHORIZATION_SIGNATURE_REVIEW_AND_LOCAL_INPUTS"),
    Step("P4RC-002", "VERIFY_PINNED_HOST_AND_FRESH_IDENTITY"),
    Step("P4RC-003", "CREATE_EXCLUSIVE_NAMESPACE_AND_TRANSACTION_TREE"),
    Step("P4RC-004", "TRANSFER_ARCHIVE_AND_SIDECAR_ONCE"),
    Step("P4RC-005", "VERIFY_REMOTE_ARCHIVE_BYTES_AND_SIDECAR"),
    Step("P4RC-006", "VERIFY_SAFE_ARCHIVE_MEMBER_INVENTORY"),
    Step("P4RC-007", "EXTRACT_ONCE_WITHOUT_OWNER_OR_PERMISSION_PRESERVATION"),
    Step("P4RC-008", "VERIFY_INTERNAL_BUNDLE_HASHES"),
    Step("P4RC-009", "RUN_SELF_TEST_AND_DESCRIBE_CONTRACT_ONCE"),
    Step("P4RC-010", "VERIFY_FIXED_REMOTE_COMMAND_BOUNDARY"),
    Step("P4RC-011", "RUN_COLLECTOR_ONCE"),
    Step("P4RC-012", "VALIDATE_AND_SEAL_LOCAL_COLLECTOR_ARTIFACTS"),
    Step("P4RC-013", "SEPARATE_SINGLE_OWNER_RESULT_REVIEW_AND_STOP_BEFORE_P5"),
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def seal_collector_artifact(artifact: dict[str, Any]) -> bytes:
    artifact["artifact_sha256"] = "0" * 64
    artifact["artifact_sha256"] = sha256_bytes(canonical(artifact))
    return canonical(artifact)


def synthetic_collector_artifact(authorization_hash: str, *, complete: bool = True) -> bytes:
    """Build a known-answer artifact for the no-network fake backend only."""
    contract = json.loads(
        (ROOT / "config/q15/q15-r-stand-prestate-collector-contract-v1.json").read_text(
            encoding="utf-8"
        )
    )
    commands = contract["commands"] if complete else contract["commands"][:3]
    observations: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        accepted = complete or index + 1 < len(commands)
        observations.append(
            {
                "accepted": accepted,
                "argv": command["argv"],
                "command_id": command["id"],
                "ended_at_utc": f"2026-08-26T00:00:00.{2 * index + 1:09d}Z",
                "exit_code": 0 if accepted else 9,
                "launched": True,
                "observation_kind": command["observation_kind"],
                "output_limit_exceeded": False,
                "spawn_error": 0,
                "started_at_utc": f"2026-08-26T00:00:00.{2 * index:09d}Z",
                "stderr_hex": "",
                "stdout_hex": "76616c75650a",
                "terminating_signal": None,
                "timed_out": False,
            }
        )
    artifact = {
        "artifact_hash_profile": "Q15-R-PRESTATE-JCS-I64-ZEROSELF-SHA256-v1",
        "artifact_sha256": "0" * 64,
        "authorization_sha256": authorization_hash,
        "canonicalization": "JCS-I64-v1",
        "capture_id": CAPTURE_ID,
        "collector_binary_sha256": COLLECTOR_SHA256,
        "collector_contract_id": "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1",
        "collector_contract_sha256": CONTRACT_SHA256,
        "completion_state": "COMPLETE" if complete else "PARTIAL_FAILED",
        "failed_command_id": None if complete else commands[-1]["id"],
        "failure_category": None if complete else "UNEXPECTED_EXIT_CODE",
        "observations": observations,
        "protocol_version": PROTOCOL_VERSION,
        "schema_version": "cpu-prefetch-q15-r-stand-prestate/1",
        "selected_release_archive_sha256": SELECTED_RELEASE_SHA256,
        "source_revision": "34da95d002e912069c959bfef8e88a23b4880cea",
        "stand_id": STAND_ID,
    }
    return seal_collector_artifact(artifact)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo != UTC or parsed.microsecond != 0:
        raise ActionError("timestamp is not an exact UTC second")
    return parsed


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_regular(path: pathlib.Path, expected_hash: str | None = None) -> os.stat_result:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ActionError(f"required file is not regular and nonsymlinked: {path}")
    if expected_hash is not None and sha256_file(path) != expected_hash:
        raise ActionError(f"required file SHA-256 mismatch: {path}")
    return metadata


def write_exclusive(path: pathlib.Path, value: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def fsync_directory(path: pathlib.Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_local_custody(outputs: OutputPaths = OUTPUTS) -> None:
    metadata = os.lstat(CUSTODY_ROOT)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ActionError("D-099 custody root is not a nonsymlink directory")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ActionError("D-099 custody root mode is not 0700")
    names = {item.name for item in CUSTODY_ROOT.iterdir()}
    if names != set(EXPECTED_PREDECESSORS):
        raise ActionError("D-099 custody root contains missing or unexpected entries")
    for name, digest in EXPECTED_PREDECESSORS.items():
        require_regular(CUSTODY_ROOT / name, digest)
    for output in dataclasses.astuple(outputs):
        if os.path.lexists(output):
            raise ActionError(f"P4-R-C output destination already exists: {output}")


def validate_local_custody_for_review(outputs: OutputPaths = OUTPUTS) -> None:
    metadata = os.lstat(CUSTODY_ROOT)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ActionError("D-099 custody root is not a nonsymlink directory")
    if stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ActionError("D-099 custody root mode is not 0700")
    expected = set(EXPECTED_PREDECESSORS) | {
        outputs.stdout.name,
        outputs.stderr.name,
        outputs.sidecar.name,
        outputs.receipt.name,
    }
    if {item.name for item in CUSTODY_ROOT.iterdir()} != expected:
        raise ActionError("P4-R-C custody inventory is not the exact review input set")
    for name, digest in EXPECTED_PREDECESSORS.items():
        require_regular(CUSTODY_ROOT / name, digest)
    for path in (outputs.stdout, outputs.stderr, outputs.sidecar, outputs.receipt):
        require_regular(path)
    for path in (outputs.review, outputs.failure):
        if os.path.lexists(path):
            raise ActionError(f"P4-R-C review destination already exists: {path}")


def ssh_argv(remote_command: str) -> list[str]:
    if not SAFE_REMOTE_RE.fullmatch(remote_command):
        raise ActionError("remote command violates the accepted fixed-token grammar")
    fixed = {
        REMOTE_PYTHON_STDIN,
        REMOTE_UPLOAD_ARCHIVE,
        REMOTE_UPLOAD_SIDECAR,
        REMOTE_SELF_TEST,
        REMOTE_DESCRIBE,
    }
    collect_prefix = (
        f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 {REMOTE_COLLECTOR} --collect "
    )
    if remote_command not in fixed:
        if not remote_command.startswith(collect_prefix):
            raise ActionError("remote command is not registered by the fixed executor")
        arguments = remote_command[len(collect_prefix) :].split(" ")
        if (
            len(arguments) != 4
            or not HASH_RE.fullmatch(arguments[0])
            or arguments[1:] != [COLLECTOR_SHA256, CONTRACT_SHA256, CAPTURE_ID]
        ):
            raise ActionError("collector command arguments drifted")
    return [
        str(SSH), "-F", "/dev/null", "-T",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={PINNED_HOSTS}",
        "-o", "GlobalKnownHostsFile=/dev/null",
        "-o", "HostKeyAlgorithms=ssh-ed25519",
        "-o", "UpdateHostKeys=no",
        "-o", "PubkeyAuthentication=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "PreferredAuthentications=publickey",
        "-o", "IdentitiesOnly=yes",
        "-o", f"IdentityFile={TRANSPORT_PRIVATE}",
        "-o", "IdentityAgent=none",
        "-o", "ConnectionAttempts=1",
        "-o", "ConnectTimeout=10",
        "-o", "ServerAliveInterval=5",
        "-o", "ServerAliveCountMax=1",
        "-o", "ClearAllForwardings=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ControlMaster=no",
        "-o", "ControlPath=none",
        "-o", "LogLevel=ERROR",
        DESTINATION,
        remote_command,
    ]


def _script_payload(source: str) -> bytes:
    return source.encode("utf-8")


REMOTE_PREFLIGHT_SCRIPT = f"""import json,os,platform,socket,stat
paths={{'namespace':{REMOTE_NAMESPACE!r},'transaction':{REMOTE_TRANSACTION!r}}}
def state(path):
 try:
  s=os.lstat(path)
 except FileNotFoundError:
  return {{'exists':False}}
 return {{'exists':True,'directory':stat.S_ISDIR(s.st_mode),'symlink':stat.S_ISLNK(s.st_mode),'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}}
out={{'hostname':socket.gethostname(),'kernel':platform.system(),'release':platform.release(),'machine':platform.machine(),'paths':{{k:state(v) for k,v in paths.items()}}}}
print(json.dumps(out,sort_keys=True,separators=(',',':')))
"""

REMOTE_CREATE_SCRIPT = f"""import json,os,stat
namespace={REMOTE_NAMESPACE!r}; transaction={REMOTE_TRANSACTION!r}; incoming={REMOTE_INCOMING!r}; release={REMOTE_RELEASE_PARENT!r}
def req(value,message):
 if not value: raise RuntimeError(message)
def valid_existing(path):
 s=os.lstat(path)
 return stat.S_ISDIR(s.st_mode) and not stat.S_ISLNK(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==0 and s.st_gid==0
if os.path.lexists(namespace):
 req(valid_existing(namespace),'invalid namespace parent')
else:
 os.mkdir(namespace,0o700)
req(not os.path.lexists(transaction),'transaction collision')
os.mkdir(transaction,0o700); os.mkdir(incoming,0o700); os.mkdir(release,0o700)
print(json.dumps({{'created':[transaction,incoming,release]}},sort_keys=True,separators=(',',':')))
"""

REMOTE_VERIFY_SCRIPT = f"""import hashlib,json,os,tarfile
archive={REMOTE_ARCHIVE!r}; sidecar={REMOTE_SIDECAR!r}; expected={ARCHIVE_SHA256!r}; size={ARCHIVE_BYTES}; root={TOP_LEVEL!r}
def req(value,message):
 if not value: raise RuntimeError(message)
req(os.path.getsize(archive)==size,'archive size')
def digest(path):
 h=hashlib.sha256()
 with open(path,'rb') as stream:
  while True:
   chunk=stream.read(1048576)
   if not chunk: break
   h.update(chunk)
 return h.hexdigest()
h=digest(archive); req(h==expected,'archive hash')
req(open(sidecar,'rb').read()==(expected+'  {ARCHIVE.name}\\n').encode(),'sidecar')
with tarfile.open(archive,'r:gz') as t:
 members=t.getmembers(); seen=set(); total=0
 for m in members:
  parts=m.name.split('/')
  req(parts and parts[0]==root and m.name[0]!='/' and '..' not in parts and '' not in parts,'member path')
  req(not (m.issym() or m.islnk() or m.isdev() or m.isfifo()),'member type')
  req(m.name not in seen,'duplicate member'); seen.add(m.name)
  req(m.isdir() or m.isfile(),'unsupported member'); total+=m.size
  req(total<134217728,'expanded byte bound')
print(json.dumps({{'archive_sha256':h,'members':len(members)}},sort_keys=True,separators=(',',':')))
"""

REMOTE_EXTRACT_SCRIPT = f"""import os,tarfile
archive={REMOTE_ARCHIVE!r}; parent={REMOTE_RELEASE_PARENT!r}; root={REMOTE_RELEASE!r}
def req(value,message):
 if not value: raise RuntimeError(message)
req(os.listdir(parent)==[],'release parent not empty')
with tarfile.open(archive,'r:gz') as t:
 for m in t.getmembers():
  target=os.path.join(parent,m.name)
  if m.isdir():
   os.mkdir(target,0o700)
  elif m.isfile():
   req(os.path.isdir(os.path.dirname(target)),'member parent missing')
   fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'wb') as out, t.extractfile(m) as src:
    while True:
     chunk=src.read(65536)
     if not chunk: break
     out.write(chunk)
  else: raise AssertionError('unsupported member')
req(os.path.isdir(root),'release root missing')
print('EXTRACTED_CREATE_EXCLUSIVE')
"""

REMOTE_INTERNAL_SCRIPT = f"""import hashlib,os,stat
root={REMOTE_RELEASE!r}; sums=os.path.join(root,'SHA256SUMS'); collector={REMOTE_COLLECTOR!r}; lines=open(sums,encoding='ascii').read().splitlines(); seen=set()
def req(value,message):
 if not value: raise RuntimeError(message)
for line in lines:
 digest,rel=line.split('  ',1); req(rel not in seen and '..' not in rel.split('/') and not rel.startswith('/'),'manifest path'); seen.add(rel)
 path=os.path.join(root,rel); req(os.path.isfile(path) and not os.path.islink(path),'manifest file')
 h=hashlib.sha256(open(path,'rb').read()).hexdigest(); req(h==digest,rel)
req(hashlib.sha256(open(collector,'rb').read()).hexdigest()=={COLLECTOR_SHA256!r},'collector hash')
os.chmod(collector,0o700); s=os.lstat(collector); req(stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode) and stat.S_IMODE(s.st_mode)==0o700 and s.st_uid==0 and s.st_gid==0,'collector mode')
print('INTERNAL_SHA256SUMS_OK files='+str(len(seen)))
"""

REMOTE_PYTHON_STDIN = "/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/python3 -"
REMOTE_UPLOAD_ARCHIVE = f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/dd of={REMOTE_ARCHIVE} bs=65536 conv=excl status=none"
REMOTE_UPLOAD_SIDECAR = f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/dd of={REMOTE_SIDECAR} bs=65536 conv=excl status=none"
REMOTE_SELF_TEST = f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 {REMOTE_COLLECTOR} --self-test"
REMOTE_DESCRIBE = f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 {REMOTE_COLLECTOR} --describe-contract"


def remote_script_hashes() -> dict[str, str]:
    return {
        "preflight": sha256_bytes(REMOTE_PREFLIGHT_SCRIPT.encode()),
        "create": sha256_bytes(REMOTE_CREATE_SCRIPT.encode()),
        "verify": sha256_bytes(REMOTE_VERIFY_SCRIPT.encode()),
        "extract": sha256_bytes(REMOTE_EXTRACT_SCRIPT.encode()),
        "internal": sha256_bytes(REMOTE_INTERNAL_SCRIPT.encode()),
    }


def expected_local_paths() -> dict[str, str]:
    return {
        "archive_source": str(ARCHIVE),
        "archive_sidecar_source": str(SIDECAR),
        "pinned_hosts": str(PINNED_HOSTS),
        "target_allowed_signers": str(TARGET_ALLOWED_SIGNERS),
        "transport_public_key": str(TRANSPORT_PUBLIC),
        "transport_private_key": str(TRANSPORT_PRIVATE),
        "ssh": str(SSH),
        "ssh_keygen": str(SSH_KEYGEN),
        "d099_identity": str(IDENTITY),
        "d099_review": str(IDENTITY_REVIEW),
        "custody_root": str(CUSTODY_ROOT),
        "collector_stdout": str(COLLECTOR_STDOUT),
        "collector_stderr": str(COLLECTOR_STDERR),
        "collector_sidecar": str(COLLECTOR_SIDECAR),
        "transfer_receipt": str(TRANSFER_RECEIPT),
        "owner_review": str(OWNER_REVIEW),
        "failure": str(FAILURE),
    }


def expected_remote_paths() -> dict[str, str]:
    return {
        "namespace": REMOTE_NAMESPACE,
        "transaction": REMOTE_TRANSACTION,
        "incoming": REMOTE_INCOMING,
        "release_parent": REMOTE_RELEASE_PARENT,
        "release_root": REMOTE_RELEASE,
        "archive": REMOTE_ARCHIVE,
        "archive_sidecar": REMOTE_SIDECAR,
        "collector": REMOTE_COLLECTOR,
        "validator": REMOTE_VALIDATOR,
    }


class Backend(Protocol):
    def invoke(self, identifier: str, remote_command: str, stdin: bytes, timeout: int) -> Result: ...


def _bounded_reader(
    stream: BinaryIO,
    limit: int,
    chunks: list[bytes],
    exceeded: threading.Event,
    process: subprocess.Popen[bytes],
) -> None:
    retained = 0
    while True:
        chunk = stream.read(65536)
        if not chunk:
            return
        remaining = max(0, limit + 1 - retained)
        if remaining:
            chunks.append(chunk[:remaining])
            retained += min(len(chunk), remaining)
        if retained > limit or len(chunk) > remaining:
            exceeded.set()
            process.kill()


def _bounded_writer(stream: BinaryIO, value: bytes) -> None:
    try:
        for offset in range(0, len(value), 65536):
            stream.write(value[offset : offset + 65536])
            stream.flush()
    except BrokenPipeError:
        pass
    finally:
        stream.close()


def run_bounded(
    argv: list[str], stdin: bytes, timeout: int, stdout_limit: int, stderr_limit: int
) -> Result:
    process = subprocess.Popen(
        argv,
        shell=False,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "HOME": "/home/omaltsev",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin",
            "TZ": "UTC",
        },
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        process.wait()
        raise ActionError("bounded subprocess pipes were not created")
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    exceeded = threading.Event()
    threads = [
        threading.Thread(
            target=_bounded_reader,
            args=(process.stdout, stdout_limit, stdout_chunks, exceeded, process),
            daemon=True,
        ),
        threading.Thread(
            target=_bounded_reader,
            args=(process.stderr, stderr_limit, stderr_chunks, exceeded, process),
            daemon=True,
        ),
        threading.Thread(target=_bounded_writer, args=(process.stdin, stdin), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        returncode = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as exception:
        process.kill()
        process.wait()
        for thread in threads:
            thread.join()
        raise ActionError("fixed command exceeded its watchdog") from exception
    for thread in threads:
        thread.join()
    if exceeded.is_set():
        raise ActionError("fixed command exceeded its output bound")
    return Result(returncode, b"".join(stdout_chunks), b"".join(stderr_chunks))


class OpenSshBackend:
    def __init__(self, expires_at: datetime) -> None:
        self.attempts: set[str] = set()
        self.expires_at = expires_at

    def invoke(self, identifier: str, remote_command: str, stdin: bytes, timeout: int) -> Result:
        if identifier in self.attempts:
            raise ActionError(f"retry forbidden for {identifier}")
        self.attempts.add(identifier)
        if datetime.now(UTC) >= self.expires_at:
            raise ActionError("authorization expired before the next remote operation")
        if timeout > COMMAND_TIMEOUT_SECONDS and identifier != "P4RC-011-COLLECT":
            raise ActionError("per-command timeout widened")
        stdout_limit = 1 << 26 if identifier == "P4RC-011-COLLECT" else MAX_STDOUT
        return run_bounded(
            ssh_argv(remote_command), stdin, timeout, stdout_limit, MAX_STDERR
        )


class FakeBackend:
    def __init__(self, fail_at: str | None = None) -> None:
        self.fail_at = fail_at
        self.calls: list[tuple[str, str, int, int]] = []
        self.attempts: set[str] = set()

    def invoke(self, identifier: str, remote_command: str, stdin: bytes, timeout: int) -> Result:
        if identifier in self.attempts:
            raise ActionError(f"retry forbidden for {identifier}")
        self.attempts.add(identifier)
        ssh_argv(remote_command)
        self.calls.append((identifier, remote_command, len(stdin), timeout))
        if identifier == self.fail_at:
            return Result(17, b"partial", b"injected")
        outputs = {
            "P4RC-002-PREFLIGHT": canonical({
                "hostname": "xeon-cpu-fetch", "kernel": "Linux",
                "release": "7.0.0-27-generic", "machine": "x86_64",
                "paths": {"namespace": {"exists": False}, "transaction": {"exists": False}},
            }),
            "P4RC-003-CREATE": canonical({"created": [REMOTE_TRANSACTION, REMOTE_INCOMING, REMOTE_RELEASE_PARENT]}),
            "P4RC-009-SELFTEST": SELF_TEST_OUTPUT,
            "P4RC-009-DESCRIBE": DESCRIBE_OUTPUT,
        }
        if identifier == "P4RC-011-COLLECT":
            tokens = remote_command.split(" ")
            authorization_hash = tokens[tokens.index("--collect") + 1]
            return Result(0, synthetic_collector_artifact(authorization_hash), b"")
        return Result(0, outputs.get(identifier, b"OK\n"), b"")


def require_success(identifier: str, result: Result) -> bytes:
    if result.returncode != 0:
        raise ActionError(f"{identifier} failed with status {result.returncode}")
    if result.stderr:
        raise ActionError(f"{identifier} produced unexpected stderr")
    return result.stdout


def require_plan_success(identifier: str, result: Result, completed: list[str]) -> bytes:
    try:
        return require_success(identifier, result)
    except ActionError as exception:
        raise PlanFailure(
            identifier, str(exception), completed, result.stdout, result.stderr
        ) from exception


def verify_signature(auth_bytes: bytes, signature: pathlib.Path, expected_hash: str) -> None:
    require_regular(signature, expected_hash)
    require_regular(TARGET_ALLOWED_SIGNERS, "b08f32720b7987218a5c51f31f822f2ea1d22ff948beb41382518927d815c718")
    completed = subprocess.run(
        [str(SSH_KEYGEN), "-Y", "verify", "-f", str(TARGET_ALLOWED_SIGNERS),
         "-I", "cpu-prefetch-q15-authorization", "-n", "cpu-prefetch-q15-authorization",
         "-s", str(signature)],
        input=auth_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        env={"HOME": "/home/omaltsev", "LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin", "TZ": "UTC"},
    )
    if completed.returncode != 0:
        raise ActionError("P4-K SSHSIG verification failed")


def load_action_records(
    authorization_path: pathlib.Path,
    authorization_hash: str,
    signature_path: pathlib.Path,
    signature_hash: str,
    review_path: pathlib.Path,
) -> tuple[dict[str, Any], str]:
    require_regular(authorization_path, authorization_hash)
    auth_bytes = authorization_path.read_bytes()
    authorization = json.loads(auth_bytes)
    if auth_bytes != canonical(authorization):
        raise ActionError("authorization is not canonical JCS-I64-v1 bytes")
    if authorization.get("schema_version") != "cpu-prefetch-q15-r-p4-r-c-d104-action-authorization/1":
        raise ActionError("unknown D-104 authorization schema")
    if authorization.get("status") != "AUTHORIZED_ONE_P4_R_C_ACTION":
        raise ActionError("D-104 authorization is not issued")
    if REMOTE_RUNTIME_ACCEPTANCE_SHA256 is None:
        raise ActionError(
            "remote Python/dd/tar runtime compatibility remains unresolved; "
            "P4-R-C execution is blocked"
        )
    required_authorization_fields = {
        "schema_version", "protocol_version", "status", "transaction_id",
        "capture_id", "stand_id", "endpoint", "decision_acceptance_sha256",
        "implementation_commit", "executor_sha256", "executor_contract_sha256",
        "remote_runtime_acceptance_sha256", "signer_key_fingerprint",
        "pinned_host_key_fingerprint", "transport_public_key_fingerprint",
        "transport_public_key_sha256", "ssh_sha256", "ssh_keygen_sha256",
        "issued_at_utc", "expires_at_utc", "archive_sha256", "archive_bytes",
        "archive_sidecar_sha256", "collector_binary_sha256",
        "collector_contract_sha256", "collector_embedded_selected_release_sha256",
        "d099_complete_evidence_sha256", "local_paths", "remote_paths",
        "remote_script_sha256", "limits", "retry_count", "review_attempts",
        "automatic_continuation", "authority_boundary",
    }
    if set(authorization) != required_authorization_fields:
        raise ActionError("D-104 authorization fields differ from schema v1")
    if authorization.get("remote_runtime_acceptance_sha256") != REMOTE_RUNTIME_ACCEPTANCE_SHA256:
        raise ActionError("remote runtime compatibility acceptance drifted")
    issued = parse_utc(authorization["issued_at_utc"])
    expires = parse_utc(authorization["expires_at_utc"])
    now = datetime.now(UTC)
    if int((expires - issued).total_seconds()) != 1800 or not (issued <= now < expires):
        raise ActionError("D-104 authorization window is invalid or expired")
    auth_hash = sha256_bytes(auth_bytes)
    expected_fields = {
        "protocol_version": PROTOCOL_VERSION,
        "transaction_id": "Q15-R-P4-R-C-D104-XEON-CPU-FETCH-20260826-01",
        "capture_id": CAPTURE_ID,
        "stand_id": STAND_ID,
        "endpoint": DESTINATION,
        "decision_acceptance_sha256": "bdfe690a15b80c85d9fdf747a2036d48c1d8f56a8f2856dfc7e1d7b597c4a65f",
        "signer_key_fingerprint": "SHA256:bOmXmBSxD0rBKid1AKOXQ25jIUjCOrijbM5sN18qLGM",
        "pinned_host_key_fingerprint": "SHA256:HZMyUcQIuSQIodYGxXGQ3RCoqR8UcOWPPzuTDhXKtS4",
        "transport_public_key_fingerprint": "SHA256:mtIlJWQzNackGLwexvC6bTnmLb8yJtdUQdC/k+FxKRo",
        "transport_public_key_sha256": "b46d49976a60f4a578282ff4d2061e7d58640eb74993c3f5333fa609792d488a",
        "ssh_sha256": "e3bc4b0d2382755b4dd398101c9c00ab20df91c2e565b017f0c8f033004391f2",
        "ssh_keygen_sha256": "f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11",
        "archive_sha256": ARCHIVE_SHA256,
        "archive_bytes": ARCHIVE_BYTES,
        "archive_sidecar_sha256": "f2bf9e3f2ed97541905b7e0fbc24dfa15d3b5c3096bd7e9ab0d23dcdbe0fffd4",
        "collector_binary_sha256": COLLECTOR_SHA256,
        "collector_contract_sha256": CONTRACT_SHA256,
        "collector_embedded_selected_release_sha256": SELECTED_RELEASE_SHA256,
        "d099_complete_evidence_sha256": "afc31fca0451e883dc72c86827a814da209da7031c0b2ec66316b92301c4c241",
        "retry_count": 0,
        "automatic_continuation": False,
    }
    if any(authorization.get(name) != value for name, value in expected_fields.items()):
        raise ActionError("D-104 authorization identity or fixed input drifted")
    implementation_commit = authorization.get("implementation_commit")
    if not isinstance(implementation_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", implementation_commit
    ):
        raise ActionError("D-104 implementation commit is malformed")
    if (
        authorization.get("executor_contract_sha256")
        != sha256_bytes(canonical(describe_contract()))
        or authorization.get("remote_script_sha256") != remote_script_hashes()
        or authorization.get("local_paths") != expected_local_paths()
        or authorization.get("remote_paths") != expected_remote_paths()
        or authorization.get("limits")
        != {
            "authorization_validity_seconds": 1800,
            "external_watchdog_seconds": 900,
            "per_command_timeout_seconds": 30,
            "maximum_stdout_bytes_per_command": MAX_STDOUT,
            "maximum_stderr_bytes_per_command": MAX_STDERR,
            "maximum_artifact_bytes": 1 << 26,
        }
        or authorization.get("review_attempts") != 1
    ):
        raise ActionError("D-104 authorization executor contract or paths drifted")
    if authorization.get("executor_sha256") != sha256_file(pathlib.Path(__file__)):
        raise ActionError("executor source hash drifted")
    if authorization.get("archive_sha256") != ARCHIVE_SHA256:
        raise ActionError("authorization archive identity drifted")
    boundary = authorization.get("authority_boundary", {})
    enabled = {name for name, value in boundary.items() if value is True}
    expected = {
        "one_target_sshsig_authorized", "one_p4_r_c_staging_and_collection_authorized",
        "one_single_owner_pre_execution_review_authorized",
        "append_only_local_evidence_authorized",
    }
    if enabled != expected:
        raise ActionError("D-104 authorization omitted or widened authority")
    verify_signature(auth_bytes, signature_path, signature_hash)
    require_regular(review_path)
    review_bytes = review_path.read_bytes()
    review = json.loads(review_bytes)
    if review_bytes != canonical(review):
        raise ActionError("pre-execution review is not canonical")
    reviewed = parse_utc(str(review.get("reviewed_at_utc", "")))
    if (
        review.get("schema_version")
        != "cpu-prefetch-q15-r-p4-r-c-d104-pre-execution-review/1"
        or review.get("status") != "ACCEPTED_SINGLE_OWNER_PRE_EXECUTION_REVIEW"
        or review.get("authorization_sha256") != auth_hash
        or review.get("signature_sha256") != signature_hash
        or review.get("review_principal") != "cpu-prefetch-q15-auditor"
        or review.get("distinct_reviewer") is not False
        or review.get("single_owner_waiver") is not True
        or review.get("all_bound_inputs_verified") is not True
        or review.get("p4_r_c_action_authorized") is not True
        or review.get("review_attempt") != 1
        or not (issued <= reviewed < expires)
        or review.get("automatic_continuation") is not False
    ):
        raise ActionError("D-104 pre-execution review mismatch")
    return authorization, auth_hash


def run_remote_plan(
    backend: Backend, authorization_hash: str, completed: list[str] | None = None
) -> tuple[bytes, bytes, list[str]]:
    if completed is None:
        completed = ["P4RC-001"]
    preflight = require_plan_success(
        "P4RC-002",
        backend.invoke("P4RC-002-PREFLIGHT", REMOTE_PYTHON_STDIN, _script_payload(REMOTE_PREFLIGHT_SCRIPT), COMMAND_TIMEOUT_SECONDS),
        completed,
    )
    try:
        parsed = json.loads(preflight)
    except json.JSONDecodeError as exception:
        raise PlanFailure("P4RC-002", "preflight output is not JSON", completed, preflight) from exception
    if (
        parsed.get("hostname") != "xeon-cpu-fetch"
        or parsed.get("kernel") != "Linux"
        or parsed.get("release") != "7.0.0-27-generic"
        or parsed.get("machine") != "x86_64"
        or parsed.get("paths", {}).get("transaction", {}).get("exists") is not False
    ):
        raise PlanFailure(
            "P4RC-002", "fresh stand identity or transaction absence mismatch", completed, preflight
        )
    namespace = parsed["paths"]["namespace"]
    if namespace.get("exists") and namespace != {
        "exists": True, "directory": True, "symlink": False, "mode": 448, "uid": 0, "gid": 0
    }:
        raise PlanFailure(
            "P4RC-002", "existing namespace parent is not exact root:root mode 0700", completed, preflight
        )
    completed.append("P4RC-002")
    require_plan_success("P4RC-003", backend.invoke("P4RC-003-CREATE", REMOTE_PYTHON_STDIN, _script_payload(REMOTE_CREATE_SCRIPT), COMMAND_TIMEOUT_SECONDS), completed); completed.append("P4RC-003")
    require_plan_success("P4RC-004-ARCHIVE", backend.invoke("P4RC-004-ARCHIVE", REMOTE_UPLOAD_ARCHIVE, ARCHIVE.read_bytes(), COMMAND_TIMEOUT_SECONDS), completed)
    require_plan_success("P4RC-004-SIDECAR", backend.invoke("P4RC-004-SIDECAR", REMOTE_UPLOAD_SIDECAR, SIDECAR.read_bytes(), COMMAND_TIMEOUT_SECONDS), completed); completed.append("P4RC-004")
    require_plan_success("P4RC-005/006", backend.invoke("P4RC-005-006-VERIFY", REMOTE_PYTHON_STDIN, _script_payload(REMOTE_VERIFY_SCRIPT), COMMAND_TIMEOUT_SECONDS), completed); completed.extend(["P4RC-005", "P4RC-006"])
    require_plan_success("P4RC-007", backend.invoke("P4RC-007-EXTRACT", REMOTE_PYTHON_STDIN, _script_payload(REMOTE_EXTRACT_SCRIPT), COMMAND_TIMEOUT_SECONDS), completed); completed.append("P4RC-007")
    require_plan_success("P4RC-008", backend.invoke("P4RC-008-INTERNAL", REMOTE_PYTHON_STDIN, _script_payload(REMOTE_INTERNAL_SCRIPT), COMMAND_TIMEOUT_SECONDS), completed); completed.append("P4RC-008")
    selftest = require_plan_success("P4RC-009-SELFTEST", backend.invoke("P4RC-009-SELFTEST", REMOTE_SELF_TEST, b"", COMMAND_TIMEOUT_SECONDS), completed)
    if selftest != SELF_TEST_OUTPUT:
        raise PlanFailure("P4RC-009-SELFTEST", "collector self-test identity mismatch", completed, selftest)
    described = require_plan_success("P4RC-009-DESCRIBE", backend.invoke("P4RC-009-DESCRIBE", REMOTE_DESCRIBE, b"", COMMAND_TIMEOUT_SECONDS), completed)
    if described != DESCRIBE_OUTPUT:
        raise PlanFailure("P4RC-009-DESCRIBE", "collector contract description mismatch", completed, described)
    completed.extend(["P4RC-009", "P4RC-010"])
    if not HASH_RE.fullmatch(authorization_hash):
        raise ActionError("authorization hash is not a safe collector argument")
    collect_command = (
        f"/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 {REMOTE_COLLECTOR} --collect "
        f"{authorization_hash} {COLLECTOR_SHA256} {CONTRACT_SHA256} {CAPTURE_ID}"
    )
    result = backend.invoke("P4RC-011-COLLECT", collect_command, b"", TOTAL_WATCHDOG_SECONDS)
    if result.returncode != 0:
        raise PlanFailure(
            "P4RC-011-COLLECT",
            f"collector failed with status {result.returncode}",
            completed,
            result.stdout,
            result.stderr,
        )
    if len(result.stdout) > (1 << 26) or len(result.stderr) > MAX_STDERR:
        raise PlanFailure(
            "P4RC-011-COLLECT", "collector artifact or stderr bound exceeded", completed
        )
    completed.append("P4RC-011")
    return result.stdout, result.stderr, completed


def validate_collector_artifact(value: bytes, authorization_hash: str) -> dict[str, Any]:
    try:
        artifact = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise ActionError(f"collector artifact is not JSON: {exception}") from exception
    if value != canonical(artifact):
        raise ActionError("collector artifact is not canonical")
    if (
        artifact.get("schema_version") != "cpu-prefetch-q15-r-stand-prestate/1"
        or artifact.get("protocol_version") != PROTOCOL_VERSION
        or artifact.get("canonicalization") != "JCS-I64-v1"
        or artifact.get("artifact_hash_profile")
        != "Q15-R-PRESTATE-JCS-I64-ZEROSELF-SHA256-v1"
        or artifact.get("collector_contract_id")
        != "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1"
        or artifact.get("capture_id") != CAPTURE_ID
        or artifact.get("authorization_sha256") != authorization_hash
        or artifact.get("collector_binary_sha256") != COLLECTOR_SHA256
        or artifact.get("collector_contract_sha256") != CONTRACT_SHA256
        or artifact.get("selected_release_archive_sha256") != SELECTED_RELEASE_SHA256
        or artifact.get("source_revision")
        != "34da95d002e912069c959bfef8e88a23b4880cea"
        or artifact.get("stand_id") != STAND_ID
    ):
        raise ActionError("collector artifact identity drifted")
    zeroed = dict(artifact)
    claimed = zeroed.get("artifact_sha256")
    zeroed["artifact_sha256"] = "0" * 64
    if not isinstance(claimed, str) or sha256_bytes(canonical(zeroed)) != claimed:
        raise ActionError("collector zero-self SHA-256 mismatch")
    contract_path = ROOT / "config/q15/q15-r-stand-prestate-collector-contract-v1.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if sha256_file(contract_path) != CONTRACT_SHA256:
        raise ActionError("local collector contract hash drifted")
    required_keys = {
        "artifact_hash_profile", "artifact_sha256", "authorization_sha256",
        "canonicalization", "capture_id", "collector_binary_sha256",
        "collector_contract_id", "collector_contract_sha256", "completion_state",
        "failed_command_id", "failure_category", "observations", "protocol_version",
        "schema_version", "selected_release_archive_sha256", "source_revision", "stand_id",
    }
    if set(artifact) != required_keys:
        raise ActionError("collector artifact fields differ from schema v1")
    observations = artifact.get("observations")
    commands = contract.get("commands")
    if not isinstance(observations, list) or not isinstance(commands, list) or not (
        1 <= len(observations) <= 25
    ):
        raise ActionError("collector observation count is outside the fixed contract")
    total = 0
    final_failure: str | None = None
    observation_keys = {
        "accepted", "argv", "command_id", "ended_at_utc", "exit_code", "launched",
        "observation_kind", "output_limit_exceeded", "spawn_error", "started_at_utc",
        "stderr_hex", "stdout_hex", "terminating_signal", "timed_out",
    }
    for index, (observation, command) in enumerate(
        zip(observations, commands, strict=False)
    ):
        if not isinstance(observation, dict) or set(observation) != observation_keys:
            raise ActionError(f"collector observation {index} fields drifted")
        if (
            observation.get("command_id") != command.get("id")
            or observation.get("observation_kind") != command.get("observation_kind")
            or observation.get("argv") != command.get("argv")
        ):
            raise ActionError(f"collector observation {index} is not the exact command prefix")
        for boolean_field in (
            "accepted",
            "launched",
            "output_limit_exceeded",
            "timed_out",
        ):
            if not isinstance(observation.get(boolean_field), bool):
                raise ActionError(
                    f"collector observation {index} {boolean_field} is not boolean"
                )
        started = observation.get("started_at_utc")
        ended = observation.get("ended_at_utc")
        if (
            not isinstance(started, str)
            or not isinstance(ended, str)
            or not NANO_UTC_RE.fullmatch(started)
            or not NANO_UTC_RE.fullmatch(ended)
            or started > ended
        ):
            raise ActionError(f"collector observation {index} timestamp is invalid")
        try:
            stdout_hex = observation.get("stdout_hex", "")
            stderr_hex = observation.get("stderr_hex", "")
            if (
                not isinstance(stdout_hex, str)
                or not isinstance(stderr_hex, str)
                or re.fullmatch(r"(?:[0-9a-f]{2})*", stdout_hex) is None
                or re.fullmatch(r"(?:[0-9a-f]{2})*", stderr_hex) is None
            ):
                raise ValueError("noncanonical hex")
            stdout_size = len(bytes.fromhex(stdout_hex))
            stderr_size = len(bytes.fromhex(stderr_hex))
        except (TypeError, ValueError) as exception:
            raise ActionError(f"collector observation {index} output is not byte hex") from exception
        if stdout_size > MAX_STDOUT or stderr_size > MAX_STDERR:
            raise ActionError(f"collector observation {index} exceeds output bounds")
        total += stdout_size + stderr_size
        if total > (1 << 24):
            raise ActionError("collector observations exceed the total output bound")
        launched = observation.get("launched") is True
        timed_out = observation.get("timed_out") is True
        output_exceeded = observation.get("output_limit_exceeded") is True
        spawn_error = observation.get("spawn_error")
        exit_code = observation.get("exit_code")
        signal = observation.get("terminating_signal")
        if (
            not isinstance(spawn_error, int)
            or isinstance(spawn_error, bool)
            or spawn_error < 0
            or (
                exit_code is not None
                and (
                    not isinstance(exit_code, int)
                    or isinstance(exit_code, bool)
                    or not 0 <= exit_code <= 255
                )
            )
            or (
                signal is not None
                and (
                    not isinstance(signal, int)
                    or isinstance(signal, bool)
                    or signal < 1
                )
            )
        ):
            raise ActionError(f"collector observation {index} status fields are malformed")
        if not launched:
            final_failure = "SPAWN_FAILURE"
        elif timed_out:
            final_failure = "COMMAND_TIMEOUT"
        elif output_exceeded:
            final_failure = "COMMAND_OUTPUT_LIMIT"
        elif not isinstance(spawn_error, int) or isinstance(spawn_error, bool) or spawn_error != 0:
            final_failure = "CAPTURE_FAILURE"
        elif signal is not None:
            final_failure = "COMMAND_SIGNAL"
        elif not isinstance(exit_code, int) or isinstance(exit_code, bool):
            final_failure = "MISSING_EXIT_STATUS"
        elif exit_code not in command.get("accepted_exit_codes", []):
            final_failure = "UNEXPECTED_EXIT_CODE"
        else:
            final_failure = None
        if observation.get("accepted") is not (final_failure is None):
            raise ActionError(f"collector observation {index} accepted flag is inconsistent")
        if index + 1 < len(observations) and final_failure is not None:
            raise ActionError("collector continued after a failed observation")
    complete = artifact.get("completion_state") == "COMPLETE"
    if complete:
        if (
            len(observations) != len(commands)
            or final_failure is not None
            or artifact.get("failed_command_id") is not None
            or artifact.get("failure_category") is not None
        ):
            raise ActionError("COMPLETE collector artifact is semantically incomplete")
    elif artifact.get("completion_state") == "PARTIAL_FAILED":
        if (
            final_failure is None
            or artifact.get("failed_command_id") != observations[-1].get("command_id")
            or artifact.get("failure_category") != final_failure
        ):
            raise ActionError("PARTIAL_FAILED collector artifact is semantically inconsistent")
    else:
        raise ActionError("unknown collector completion state")
    if len(value) > (1 << 26):
        raise ActionError("collector artifact exceeds its byte bound")
    return artifact


def emit_success(
    authorization_hash: str,
    stdout: bytes,
    stderr: bytes,
    completed: list[str],
    outputs: OutputPaths = OUTPUTS,
) -> None:
    validate_collector_artifact(stdout, authorization_hash)
    write_exclusive(outputs.stdout, stdout)
    write_exclusive(outputs.stderr, stderr)
    sidecar = f"{sha256_bytes(stdout)}  {outputs.stdout.name}\n".encode("ascii")
    write_exclusive(outputs.sidecar, sidecar)
    completed.append("P4RC-012")
    receipt = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-transfer-receipt/1",
        "transaction_id": "Q15-R-P4-R-C-D104-XEON-CPU-FETCH-20260826-01",
        "authorization_sha256": authorization_hash,
        "status": "COMPLETE_VALID_STAGING_AND_COLLECTION_STOPPED_FOR_SEPARATE_OWNER_REVIEW",
        "completed_steps": completed,
        "archive_sha256": ARCHIVE_SHA256,
        "collector_stdout_sha256": sha256_bytes(stdout),
        "collector_stderr_sha256": sha256_bytes(stderr),
        "retry_count": 0,
        "partial_staging_retained": True,
        "stand_activation_performed": False,
        "automatic_continuation": False,
        "created_at_utc": utc_now(),
    }
    write_exclusive(outputs.receipt, canonical(receipt))
    fsync_directory(outputs.receipt.parent)


def retain_failure(
    authorization_hash: str,
    phase: str,
    message: str,
    completed: list[str],
    stdout: bytes = b"",
    stderr: bytes = b"",
    outputs: OutputPaths = OUTPUTS,
) -> None:
    if os.path.lexists(outputs.failure):
        return
    record = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-failure/1",
        "transaction_id": "Q15-R-P4-R-C-D104-XEON-CPU-FETCH-20260826-01",
        "authorization_sha256": authorization_hash,
        "status": "FAILED_PARTIAL_RETAINED_NO_RETRY",
        "failed_phase": phase,
        "completed_steps": completed,
        "failure_message": message[:1024],
        "remote_stdout_hex": stdout.hex(),
        "remote_stdout_sha256": sha256_bytes(stdout),
        "remote_stderr_hex": stderr.hex(),
        "remote_stderr_sha256": sha256_bytes(stderr),
        "retry_authorized": False,
        "delete_cleanup_or_reuse_authorized": False,
        "automatic_continuation": False,
        "created_at_utc": utc_now(),
    }
    write_exclusive(outputs.failure, canonical(record))
    fsync_directory(outputs.failure.parent)


def review_result(
    authorization: pathlib.Path,
    authorization_hash: str,
    signature: pathlib.Path,
    signature_hash: str,
    pre_execution_review: pathlib.Path,
    outputs: OutputPaths = OUTPUTS,
) -> None:
    _, verified_hash = load_action_records(
        authorization,
        authorization_hash,
        signature,
        signature_hash,
        pre_execution_review,
    )
    validate_local_custody_for_review(outputs)
    stdout = outputs.stdout.read_bytes()
    stderr = outputs.stderr.read_bytes()
    validate_collector_artifact(stdout, verified_hash)
    if outputs.sidecar.read_bytes() != (
        f"{sha256_bytes(stdout)}  {outputs.stdout.name}\n".encode("ascii")
    ):
        raise ActionError("collector sidecar mismatch during result review")
    receipt_bytes = outputs.receipt.read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt_bytes != canonical(receipt):
        raise ActionError("transfer receipt is not canonical")
    if (
        receipt.get("authorization_sha256") != verified_hash
        or receipt.get("collector_stdout_sha256") != sha256_bytes(stdout)
        or receipt.get("collector_stderr_sha256") != sha256_bytes(stderr)
        or receipt.get("status")
        != "COMPLETE_VALID_STAGING_AND_COLLECTION_STOPPED_FOR_SEPARATE_OWNER_REVIEW"
        or receipt.get("completed_steps") != [f"P4RC-{index:03d}" for index in range(1, 13)]
        or receipt.get("retry_count") != 0
        or receipt.get("automatic_continuation") is not False
    ):
        raise ActionError("transfer receipt mismatch during result review")
    review = {
        "schema_version": "cpu-prefetch-q15-r-p4-r-c-d104-owner-review/1",
        "transaction_id": receipt["transaction_id"],
        "authorization_sha256": verified_hash,
        "transfer_receipt_sha256": sha256_file(outputs.receipt),
        "collector_stdout_sha256": sha256_bytes(stdout),
        "status": "ACCEPTED_SINGLE_OWNER_PUBLIC_REVIEW_STOPPED_BEFORE_P5",
        "review_principal": "cpu-prefetch-q15-auditor",
        "distinct_reviewer": False,
        "single_owner_waiver": True,
        "review_attempt": 1,
        "p5_or_later_authorized": False,
        "automatic_continuation": False,
        "reviewed_at_utc": utc_now(),
    }
    write_exclusive(outputs.review, canonical(review))
    fsync_directory(outputs.review.parent)


def execute(
    authorization: pathlib.Path,
    authorization_hash: str,
    signature: pathlib.Path,
    signature_hash: str,
    pre_execution_review: pathlib.Path,
) -> None:
    auth, auth_hash = load_action_records(
        authorization,
        authorization_hash,
        signature,
        signature_hash,
        pre_execution_review,
    )
    del auth
    validate_local_custody()
    require_regular(ARCHIVE, ARCHIVE_SHA256)
    if ARCHIVE.stat().st_size != ARCHIVE_BYTES:
        raise ActionError("archive byte count mismatch")
    require_regular(SIDECAR, "f2bf9e3f2ed97541905b7e0fbc24dfa15d3b5c3096bd7e9ab0d23dcdbe0fffd4")
    require_regular(PINNED_HOSTS, "89ddf9b9d9dc48520c9d30968bb4a63a58aa976bf9be341ac811f735eaef757d")
    require_regular(TRANSPORT_PUBLIC, "b46d49976a60f4a578282ff4d2061e7d58640eb74993c3f5333fa609792d488a")
    transport_metadata = require_regular(TRANSPORT_PRIVATE)
    if stat.S_IMODE(transport_metadata.st_mode) != 0o600:
        raise ActionError("SSH transport private key mode is not 0600")
    require_regular(SSH, "e3bc4b0d2382755b4dd398101c9c00ab20df91c2e565b017f0c8f033004391f2")
    require_regular(SSH_KEYGEN, "f5a191e91589ab689c93caccc09d827a3a9d4ab28f950dc94ae05351c1389e11")
    completed = ["P4RC-001"]
    try:
        expires = parse_utc(auth["expires_at_utc"])
        stdout, stderr, completed = run_remote_plan(
            OpenSshBackend(expires), auth_hash, completed
        )
        emit_success(auth_hash, stdout, stderr, completed)
    except PlanFailure as exception:
        retain_failure(
            auth_hash,
            exception.phase,
            str(exception),
            exception.completed,
            exception.stdout,
            exception.stderr,
        )
        raise
    except Exception as exception:
        retain_failure(
            auth_hash,
            "REMOTE_OR_LOCAL_FINALIZATION",
            str(exception),
            completed,
        )
        raise


def self_test() -> None:
    if len(STEPS) != 13 or [step.identifier for step in STEPS] != [f"P4RC-{index:03d}" for index in range(1, 14)]:
        raise ActionError("exact 13-step graph drifted")
    for command in (
        REMOTE_PYTHON_STDIN, REMOTE_UPLOAD_ARCHIVE, REMOTE_UPLOAD_SIDECAR,
        REMOTE_SELF_TEST, REMOTE_DESCRIBE,
    ):
        ssh_argv(command)
    for source in (
        REMOTE_PREFLIGHT_SCRIPT, REMOTE_CREATE_SCRIPT, REMOTE_VERIFY_SCRIPT,
        REMOTE_EXTRACT_SCRIPT, REMOTE_INTERNAL_SCRIPT,
    ):
        if any(
            forbidden in source
            for forbidden in (
                "subprocess.",
                "os.system",
                "shell" + "=True",
                "popen(",
                "assert ",
            )
        ):
            raise ActionError("remote script contains forbidden process escape")
    authorization_hash = "a" * 64
    stdout, stderr, completed = run_remote_plan(FakeBackend(), authorization_hash)
    if stderr or completed != [f"P4RC-{index:03d}" for index in range(1, 12)]:
        raise ActionError("complete fake graph order drifted")
    validate_collector_artifact(stdout, authorization_hash)
    backend = FakeBackend()
    # Avoid archive I/O and collector JSON in the structural fake: exercise the
    # exact backend call contract directly and separately test stop-first below.
    expected_calls = (
        ("P4RC-002-PREFLIGHT", REMOTE_PYTHON_STDIN, REMOTE_PREFLIGHT_SCRIPT.encode()),
        ("P4RC-003-CREATE", REMOTE_PYTHON_STDIN, REMOTE_CREATE_SCRIPT.encode()),
        ("P4RC-004-ARCHIVE", REMOTE_UPLOAD_ARCHIVE, b"archive"),
        ("P4RC-004-SIDECAR", REMOTE_UPLOAD_SIDECAR, b"sidecar"),
        ("P4RC-005-006-VERIFY", REMOTE_PYTHON_STDIN, REMOTE_VERIFY_SCRIPT.encode()),
        ("P4RC-007-EXTRACT", REMOTE_PYTHON_STDIN, REMOTE_EXTRACT_SCRIPT.encode()),
        ("P4RC-008-INTERNAL", REMOTE_PYTHON_STDIN, REMOTE_INTERNAL_SCRIPT.encode()),
        ("P4RC-009-SELFTEST", REMOTE_SELF_TEST, b""),
        ("P4RC-009-DESCRIBE", REMOTE_DESCRIBE, b""),
    )
    for identifier, command, payload in expected_calls:
        require_success(identifier, backend.invoke(identifier, command, payload, COMMAND_TIMEOUT_SECONDS))
    if len(backend.calls) != len(expected_calls):
        raise ActionError("fake backend did not observe every fixed operation")
    try:
        backend.invoke(expected_calls[0][0], expected_calls[0][1], b"", COMMAND_TIMEOUT_SECONDS)
    except ActionError:
        pass
    else:
        raise ActionError("retry was not rejected")
    for identifier, command, payload in expected_calls:
        failing = FakeBackend(fail_at=identifier)
        result = failing.invoke(identifier, command, payload, COMMAND_TIMEOUT_SECONDS)
        try:
            require_success(identifier, result)
        except ActionError:
            if len(failing.calls) != 1:
                raise ActionError("failure injection retried")
        else:
            raise ActionError(f"failure injection did not stop: {identifier}")
    for unsafe in (
        "/bin/sh -c id", "echo ok;id", "echo $(id)", "echo *", "echo 'quoted'",
    ):
        try:
            ssh_argv(unsafe)
        except ActionError:
            continue
        raise ActionError(f"unsafe remote string accepted: {unsafe}")
    for identifier in (
        "P4RC-002-PREFLIGHT",
        "P4RC-003-CREATE",
        "P4RC-004-ARCHIVE",
        "P4RC-004-SIDECAR",
        "P4RC-005-006-VERIFY",
        "P4RC-007-EXTRACT",
        "P4RC-008-INTERNAL",
        "P4RC-009-SELFTEST",
        "P4RC-009-DESCRIBE",
        "P4RC-011-COLLECT",
    ):
        try:
            run_remote_plan(FakeBackend(fail_at=identifier), authorization_hash)
        except PlanFailure:
            pass
        else:
            raise ActionError(f"full-graph failure injection did not stop: {identifier}")
    corrupt = bytearray(synthetic_collector_artifact(authorization_hash))
    corrupt[-3] ^= 1
    try:
        validate_collector_artifact(bytes(corrupt), authorization_hash)
    except ActionError:
        pass
    else:
        raise ActionError("corrupt collector artifact was accepted")
    semantic_mutants: list[dict[str, Any]] = []
    for mutate in (
        lambda value: value["observations"][0].update({"accepted": "true"}),
        lambda value: value["observations"][0].update({"stdout_hex": "76 61"}),
        lambda value: value["observations"][0].update({"command_id": "P4R-002"}),
        lambda value: value.update({"unexpected": False}),
        lambda value: value.update({"completion_state": "PARTIAL_FAILED"}),
    ):
        mutant = json.loads(synthetic_collector_artifact(authorization_hash))
        mutate(mutant)
        semantic_mutants.append(mutant)
    for index, mutant in enumerate(semantic_mutants):
        try:
            validate_collector_artifact(
                seal_collector_artifact(mutant), authorization_hash
            )
        except ActionError:
            pass
        else:
            raise ActionError(f"semantic collector mutation {index} was accepted")
    with tempfile.TemporaryDirectory(prefix="d104-p4-r-c-self-test-") as directory:
        root = pathlib.Path(directory)
        outputs = OutputPaths(
            root / "artifact.json",
            root / "artifact.stderr.bin",
            root / "artifact.json.sha256",
            root / "receipt.json",
            root / "review.json",
            root / "failure.json",
        )
        completed_for_emit = [f"P4RC-{index:03d}" for index in range(1, 12)]
        emit_success(
            authorization_hash,
            synthetic_collector_artifact(authorization_hash),
            b"",
            completed_for_emit,
            outputs,
        )
        if outputs.review.exists() or outputs.failure.exists():
            raise ActionError("collection emission fabricated review or failure evidence")
        try:
            emit_success(
                authorization_hash,
                synthetic_collector_artifact(authorization_hash),
                b"",
                [f"P4RC-{index:03d}" for index in range(1, 12)],
                outputs,
            )
        except FileExistsError:
            pass
        else:
            raise ActionError("create-exclusive collection output was overwritten")
    with tempfile.TemporaryDirectory(prefix="d104-p4-r-c-failure-test-") as directory:
        root = pathlib.Path(directory)
        outputs = OutputPaths(
            root / "artifact.json",
            root / "artifact.stderr.bin",
            root / "artifact.json.sha256",
            root / "receipt.json",
            root / "review.json",
            root / "failure.json",
        )
        retain_failure(
            authorization_hash,
            "P4RC-004-ARCHIVE",
            "synthetic failure",
            ["P4RC-001", "P4RC-002", "P4RC-003"],
            b"partial",
            b"injected",
            outputs,
        )
        first = outputs.failure.read_bytes()
        retain_failure(
            authorization_hash,
            "P4RC-004-ARCHIVE",
            "replacement forbidden",
            [],
            outputs=outputs,
        )
        if outputs.failure.read_bytes() != first:
            raise ActionError("terminal failure evidence was overwritten")


def describe_contract() -> dict[str, Any]:
    return {
        "contract": "Q15-R-P4-R-C-EXECUTOR-CONTRACT-v1",
        "protocol_version": PROTOCOL_VERSION,
        "stand_id": STAND_ID,
        "steps": [dataclasses.asdict(item) for item in STEPS],
        "remote_script_sha256": remote_script_hashes(),
        "remote_command_policy": "PRECOMPUTED_FIXED_TOKEN_STRINGS_LOCAL_SHELL_FALSE_REMOTE_LOGIN_SHELL_ACCEPTED",
        "attempts": {"archive": 1, "sidecar": 1, "self_test": 1, "describe": 1, "collect": 1, "review": 1},
        "retry_count": 0,
        "authority": (
            "NONE_REMOTE_RUNTIME_COMPATIBILITY_UNRESOLVED_AND_WITHOUT_EXACT_"
            "D104_AUTHORIZATION_SIGNATURE_AND_REVIEW"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true")
    mode.add_argument("--describe-contract", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--review-result", action="store_true")
    parser.add_argument("--authorization", type=pathlib.Path)
    parser.add_argument("--authorization-sha256")
    parser.add_argument("--signature", type=pathlib.Path)
    parser.add_argument("--signature-sha256")
    parser.add_argument("--pre-execution-review", type=pathlib.Path)
    arguments = parser.parse_args()
    try:
        if arguments.self_test:
            if any(
                (
                    arguments.authorization,
                    arguments.authorization_sha256,
                    arguments.signature,
                    arguments.signature_sha256,
                    arguments.pre_execution_review,
                )
            ):
                raise ActionError("self-test accepts no action records")
            self_test()
            print("execute-d104-p4-r-c: SELF-TEST PASS (fixed 13-step graph, fake failures, no network)")
            return 0
        if arguments.describe_contract:
            if any(
                (
                    arguments.authorization,
                    arguments.authorization_sha256,
                    arguments.signature,
                    arguments.signature_sha256,
                    arguments.pre_execution_review,
                )
            ):
                raise ActionError("describe-contract accepts no action records")
            sys.stdout.buffer.write(canonical(describe_contract()))
            return 0
        action_inputs = (
            arguments.authorization,
            arguments.authorization_sha256,
            arguments.signature,
            arguments.signature_sha256,
            arguments.pre_execution_review,
        )
        if not all(action_inputs):
            raise ActionError(
                "execute/review-result requires exact authorization, hashes, signature, "
                "and pre-execution-review path"
            )
        if arguments.review_result:
            review_result(*action_inputs)
            print("execute-d104-p4-r-c: REVIEW COMPLETE STOPPED_BEFORE_P5")
            return 0
        execute(*action_inputs)
        print("execute-d104-p4-r-c: COLLECTION COMPLETE STOPPED_FOR_SEPARATE_REVIEW")
        return 0
    except (ActionError, OSError, subprocess.SubprocessError, ValueError, KeyError) as exception:
        print(f"execute-d104-p4-r-c: FAIL: {exception}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
