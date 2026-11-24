#!/usr/bin/env python3
"""One-shot executor for the fixed Stage 17 read-only preflight plan.

The CLI accepts journal and time identity only.  It has no command, argv,
stdin, remote-command, retry, transport-factory, or fake-backend option.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import selectors
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from stage17_read_only_preflight_collector_v1 import render_observation_program
from stage17_state_journal import JournalError, canonical_json_bytes, validate_journal


EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v1"
FIXED_REMOTE_COMMAND = (
    "/usr/bin/env -i LANG=C LC_ALL=C TZ=UTC0 /usr/bin/python3 -I -S -"
)
FIXED_LOCAL_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "TZ": "UTC0"}


class ActionExecutionError(RuntimeError):
    """The one-shot fixed action could not proceed or complete."""


@dataclass(frozen=True)
class TransportResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    failure: str | None = None


def _write_exclusive(path: pathlib.Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _transport_once(
    argv: list[str], stdin: bytes, timeout_seconds: int, output_limit: int
) -> TransportResult:
    """Open exactly one bounded transport with local ``shell=False``."""

    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        env=FIXED_LOCAL_ENVIRONMENT,
        close_fds=True,
    )
    if process.stdin is None or process.stdout is None or process.stderr is None:
        process.kill()
        raise ActionExecutionError("transport pipes were not created")
    selector = selectors.DefaultSelector()
    streams = {
        process.stdin.fileno(): ("stdin", process.stdin),
        process.stdout.fileno(): ("stdout", process.stdout),
        process.stderr.fileno(): ("stderr", process.stderr),
    }
    for descriptor in streams:
        os.set_blocking(descriptor, False)
    selector.register(process.stdin, selectors.EVENT_WRITE)
    selector.register(process.stdout, selectors.EVENT_READ)
    selector.register(process.stderr, selectors.EVENT_READ)
    pending = memoryview(stdin)
    output = {"stdout": bytearray(), "stderr": bytearray()}
    deadline = time.monotonic() + timeout_seconds
    failure: str | None = None
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "TIMEOUT"
                process.kill()
                break
            events = selector.select(min(remaining, 0.25))
            if not events and process.poll() is not None:
                for key in list(selector.get_map().values()):
                    if streams[key.fd][0] == "stdin":
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                continue
            for key, mask in events:
                kind, stream = streams[key.fd]
                if kind == "stdin":
                    if not pending:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    try:
                        count = os.write(key.fd, pending[:65536])
                    except BlockingIOError:
                        continue
                    pending = pending[count:]
                elif mask & selectors.EVENT_READ:
                    try:
                        chunk = os.read(key.fd, 65536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(stream)
                        stream.close()
                        continue
                    target = output[kind]
                    remaining_output = output_limit - len(output["stdout"]) - len(
                        output["stderr"]
                    )
                    if len(chunk) > remaining_output:
                        target.extend(chunk[: max(remaining_output, 0)])
                        failure = "OUTPUT_LIMIT_EXCEEDED"
                        process.kill()
                        break
                    target.extend(chunk)
            if failure is not None:
                break
        try:
            returncode = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            returncode = process.wait(timeout=2)
            failure = failure or "TERMINATION_TIMEOUT"
    finally:
        selector.close()
        for _, stream in streams.values():
            try:
                stream.close()
            except OSError:
                pass
    return TransportResult(
        returncode=returncode,
        stdout=bytes(output["stdout"]),
        stderr=bytes(output["stderr"]),
        failure=failure,
    )


def _ssh_argv(context: dict[str, Any]) -> list[str]:
    known_hosts = str(context["known_hosts_path"])
    identity = str(context["transport_identity_locator"])
    target = str(context["ssh_target"])
    return [
        "/usr/bin/ssh",
        "-F",
        "/dev/null",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        f"UserKnownHostsFile={known_hosts}",
        "-o",
        "GlobalKnownHostsFile=/dev/null",
        "-o",
        "HostKeyAlgorithms=ssh-ed25519",
        "-o",
        "UpdateHostKeys=no",
        "-o",
        "PubkeyAuthentication=yes",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "PreferredAuthentications=publickey",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        f"IdentityFile={identity}",
        "-o",
        "IdentityAgent=none",
        "-o",
        "ConnectionAttempts=1",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=1",
        "-o",
        "ClearAllForwardings=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "ControlMaster=no",
        "-o",
        "ControlPath=none",
        "-o",
        "PermitLocalCommand=no",
        "-o",
        "RequestTTY=no",
        "-o",
        "LogLevel=ERROR",
        "--",
        target,
        FIXED_REMOTE_COMMAND,
    ]


def execute_once(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
    as_of_utc: str,
) -> None:
    """Execute the admitted fixed action once; never retries."""

    validation = validate_journal(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        as_of_utc=as_of_utc,
        requested_action_input_id="S17-EXT-001",
    )
    if not validation.action_ready or validation.action_context is None:
        raise ActionExecutionError("S17-EXT-001 is not action-ready")
    context = validation.action_context
    marker_path = pathlib.Path(context["attempt_marker_path"])
    marker = {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/1",
        "attempt_id": context["attempt_id"],
        "authorization_id": context["authorization_id"],
        "authorization_sha256": context["authorization_sha256"],
        "resolution_id": context["resolution_id"],
        "resolution_sha256": context["resolution_sha256"],
        "transition_id": context["transition_id"],
        "transition_sha256": context["transition_sha256"],
        "action_plan_sha256": context["action_plan_sha256"],
        "started_at_utc": as_of_utc,
        "attempt_number": 1,
        "retry_allowed": False,
        "transport_may_start_after_marker": True,
        "stage18_authority": False,
    }
    _write_exclusive(marker_path, canonical_json_bytes(marker) + b"\n")

    completed: list[str] = []
    for index, observation_id in enumerate(context["observation_ids"], start=1):
        program = render_observation_program(observation_id, context["collector_context"])
        result = _transport_once(
            _ssh_argv(context),
            program,
            int(context["timeout_seconds"]),
            int(context["max_output_bytes"]),
        )
        stem = pathlib.Path(context["evidence_root"]) / f"s17-ro-{index:03d}"
        _write_exclusive(stem.with_suffix(".stdout.bin"), result.stdout)
        _write_exclusive(stem.with_suffix(".stderr.bin"), result.stderr)
        receipt = {
            "observation_id": observation_id,
            "returncode": result.returncode,
            "failure": result.failure,
            "stdout_size_bytes": len(result.stdout),
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_size_bytes": len(result.stderr),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
            "attempt": 1,
            "retry": 0,
        }
        _write_exclusive(
            stem.with_suffix(".receipt.json"), canonical_json_bytes(receipt) + b"\n"
        )
        if result.failure is not None or result.returncode != 0:
            failure = {
                "schema_version": "cpu-prefetch-stage17-read-only-preflight-failure/1",
                "failed_observation_id": observation_id,
                "completed_observation_ids": completed,
                "failure": result.failure or f"REMOTE_EXIT_{result.returncode}",
                "retry_allowed": False,
                "partial_evidence_retained": True,
                "stage18_authority": False,
            }
            _write_exclusive(
                pathlib.Path(context["evidence_root"])
                / "stage17-read-only-preflight-failure-v1.json",
                canonical_json_bytes(failure) + b"\n",
            )
            raise ActionExecutionError("fixed read-only preflight stopped on failure")
        completed.append(observation_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--as-of-utc", required=True)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root,
            latest_journal=arguments.journal,
            journal_directory=arguments.journal_directory,
            as_of_utc=arguments.as_of_utc,
        )
    except (ActionExecutionError, JournalError, OSError, ValueError) as exception:
        print(f"stage17-read-only-preflight: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-read-only-preflight: PASS fixed observations=6 retry=0 Stage18=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
