#!/usr/bin/env python3
"""Durable one-shot executor for the fixed Stage 17 read-only preflight.

Production execution accepts no caller-selected authority time, commands, argv,
stdin, remote command, transport factory, retry, or output filenames.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import selectors
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

import stage17_pilot_candidate_artifact
import stage17_read_only_preflight_collector_v1
import stage17_read_only_preflight_collector_v2
import stage17_semantic_verifier_v3
import stage17_semantic_verifier_v4
import stage17_state_journal


EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v2"
FIXED_LOCAL_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "TZ": "UTC0"}
SAFE_CHILD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ActionExecutionError(RuntimeError):
    """The fixed one-shot action was rejected or failed."""


@dataclass(frozen=True)
class TransportResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    failure: str | None = None


@dataclass(frozen=True)
class PreparedAction:
    context: dict[str, Any]
    ssh_argv: tuple[str, ...]
    ssh_argv_sha256: str
    programs: tuple[bytes, ...]
    program_descriptors: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class OperationalFailure(Exception):
    stage: str
    category: str
    reason: str
    ordinal: int | None = None
    observation_id: str | None = None
    program_sha256: str | None = None


def runtime_identity_paths() -> dict[str, str]:
    """Return the actual loaded repository runtime closure."""

    return {
        "semantic_verifier": str(pathlib.Path(stage17_semantic_verifier_v4.__file__).resolve()),
        "executor": str(pathlib.Path(__file__).resolve()),
        "collector": str(pathlib.Path(stage17_read_only_preflight_collector_v2.__file__).resolve()),
        "state_journal": str(pathlib.Path(stage17_state_journal.__file__).resolve()),
        "semantic_verifier_v3_helper": str(pathlib.Path(stage17_semantic_verifier_v3.__file__).resolve()),
        "collector_v1_helper": str(pathlib.Path(stage17_read_only_preflight_collector_v1.__file__).resolve()),
        "pilot_candidate_verifier": str(pathlib.Path(stage17_pilot_candidate_artifact.__file__).resolve()),
    }


def _actual_utc_now() -> str:
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _argv_bytes(argv: tuple[str, ...]) -> bytes:
    encoded: list[bytes] = []
    for item in argv:
        value = item.encode("utf-8", errors="strict")
        if b"\x00" in value:
            raise ActionExecutionError("fixed SSH argv contains NUL")
        encoded.append(value)
    return b"\x00".join(encoded) + b"\x00"


def _schema(path_value: str, document: dict[str, Any], label: str) -> None:
    path = pathlib.Path(path_value)
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        first = errors[0]
        location = "/".join(str(item) for item in first.absolute_path)
        raise ActionExecutionError(f"{label} schema error at $/{location}: {first.message}")


def _ssh_argv(context: dict[str, Any]) -> tuple[str, ...]:
    substitutions = {
        "{PINNED_KNOWN_HOSTS_PATH}": str(context["known_hosts_path"]),
        "{TRANSPORT_IDENTITY_LOCATOR}": str(context["transport_identity_locator"]),
        "{SSH_TARGET}": str(context["ssh_target"]),
    }
    rendered: list[str] = []
    for source in context["fixed_ssh_argv_template"]:
        token = source
        for placeholder, value in substitutions.items():
            token = token.replace(placeholder, value)
        if "{" in token or "}" in token or "\x00" in token:
            raise ActionExecutionError("fixed SSH argv has unresolved or invalid token")
        rendered.append(token)
    return tuple(rendered)


def _prepare_action(context: dict[str, Any]) -> PreparedAction:
    argv = _ssh_argv(context)
    if len(context["observation_ids"]) != 6:
        raise ActionExecutionError("fixed observation family is not six")
    programs: list[bytes] = []
    descriptors: list[dict[str, Any]] = []
    for ordinal, observation_id in enumerate(context["observation_ids"], start=1):
        program = stage17_read_only_preflight_collector_v2.render_observation_program(
            observation_id, context["collector_context"]
        )
        compile(program, f"<stage17:{observation_id}>", "exec")
        programs.append(program)
        descriptors.append(
            {
                "ordinal": ordinal,
                "observation_id": observation_id,
                "size_bytes": len(program),
                "sha256": _sha256_bytes(program),
            }
        )
        for name in (
            f"s17-ro-{ordinal:03d}.stdout.bin",
            f"s17-ro-{ordinal:03d}.stderr.bin",
            f"s17-ro-{ordinal:03d}.receipt-v1.json",
        ):
            if SAFE_CHILD_NAME.fullmatch(name) is None:
                raise ActionExecutionError("fixed output name is unsafe")
    for name in (
        context["attempt_marker_name"],
        context["failure_name"],
        context["completion_name"],
    ):
        if SAFE_CHILD_NAME.fullmatch(name) is None:
            raise ActionExecutionError("fixed action record name is unsafe")
    return PreparedAction(
        context=context,
        ssh_argv=argv,
        ssh_argv_sha256=_sha256_bytes(_argv_bytes(argv)),
        programs=tuple(programs),
        program_descriptors=tuple(descriptors),
    )


def _transport_once(
    argv: tuple[str, ...], stdin: bytes, timeout_seconds: float, output_limit: int
) -> TransportResult:
    """Open exactly one bounded transport with local ``shell=False``."""

    process = subprocess.Popen(
        list(argv),
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
                    remaining_output = output_limit - len(output["stdout"]) - len(
                        output["stderr"]
                    )
                    if len(chunk) > remaining_output:
                        output[kind].extend(chunk[: max(remaining_output, 0)])
                        failure = "OUTPUT_LIMIT_EXCEEDED"
                        process.kill()
                        break
                    output[kind].extend(chunk)
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


def _open_evidence_root(context: dict[str, Any]) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open(context["evidence_root"], flags)
    metadata = os.fstat(descriptor)
    expected = context["evidence_root_identity"]
    actual = {
        "device": metadata.st_dev,
        "inode": metadata.st_ino,
        "uid": metadata.st_uid,
        "mode": stat.S_IMODE(metadata.st_mode),
    }
    if not stat.S_ISDIR(metadata.st_mode) or actual != expected:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root directory identity changed")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root ownership or permissions are unsafe")
    return descriptor


def _write_exclusive_at(
    directory_fd: int,
    name: str,
    payload: bytes,
    *,
    sync_directory: bool = True,
) -> str:
    if SAFE_CHILD_NAME.fullmatch(name) is None:
        raise ActionExecutionError("unsafe fixed child name")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
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
    if sync_directory:
        os.fsync(directory_fd)
    return _sha256_bytes(payload)


def _remaining_seconds(deadline_ns: int) -> float:
    remaining_ns = deadline_ns - time.monotonic_ns()
    if remaining_ns <= 0:
        raise OperationalFailure(
            "GLOBAL_DEADLINE", "GLOBAL_WALL_TIMEOUT", "global 180-second deadline expired"
        )
    return remaining_ns / 1_000_000_000


def _reason(exception: BaseException) -> str:
    value = f"{type(exception).__name__}: {exception}"
    value = " ".join(value.split())
    return value[:512] or type(exception).__name__


def _base_links(context: dict[str, Any]) -> dict[str, Any]:
    hashes = context["runtime_implementation_hashes"]
    return {
        "attempt_id": context["attempt_id"],
        "authorization_id": context["authorization_id"],
        "authorization_sha256": context["authorization_sha256"],
        "resolution_id": context["resolution_id"],
        "resolution_sha256": context["resolution_sha256"],
        "transition_id": context["transition_id"],
        "transition_sha256": context["transition_sha256"],
        "action_plan_sha256": context["action_plan_sha256"],
        "executor_sha256": hashes["executor"],
        "collector_sha256": hashes["collector"],
    }


def _write_failure(
    *,
    directory_fd: int,
    prepared: PreparedAction,
    failure: OperationalFailure,
    completed: list[str],
    action_started_ns: int,
) -> None:
    context = prepared.context
    document = {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-failure/2",
        **_base_links(context),
        "failed_stage": failure.stage,
        "failed_ordinal": failure.ordinal,
        "failed_observation_id": failure.observation_id,
        "completed_observation_ids": list(completed),
        "reason_category": failure.category,
        "reason": failure.reason[:512],
        "actual_failed_at_utc": _actual_utc_now(),
        "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
        "ssh_argv_sha256": prepared.ssh_argv_sha256,
        "rendered_program_sha256": failure.program_sha256,
        "retry_allowed": False,
        "partial_evidence_retained": True,
        "stage18_authority": False,
    }
    _schema(context["record_schema_paths"]["failure"], document, "failure record")
    _write_exclusive_at(
        directory_fd,
        context["failure_name"],
        stage17_state_journal.canonical_json_bytes(document) + b"\n",
    )


def _prospective_validation(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
    actual_utc: str,
) -> stage17_state_journal.JournalValidation:
    return stage17_state_journal.validate_journal(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        as_of_utc=actual_utc,
        requested_action_input_id="S17-EXT-001",
        runtime_identity_paths=runtime_identity_paths(),
    )


def execute_once(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
) -> None:
    """Execute one admitted action using actual system UTC and durable one-shot state."""

    first_now = _actual_utc_now()
    validation = _prospective_validation(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        actual_utc=first_now,
    )
    if not validation.action_ready or validation.action_context is None:
        raise ActionExecutionError("S17-EXT-001 is not action-ready at actual system UTC")
    _prepare_action(validation.action_context)

    actual_now = _actual_utc_now()
    final_validation = _prospective_validation(
        repository_root=repository_root,
        latest_journal=latest_journal,
        journal_directory=journal_directory,
        actual_utc=actual_now,
    )
    if not final_validation.action_ready or final_validation.action_context is None:
        raise ActionExecutionError("S17-EXT-001 ceased to be action-ready before marker")
    prepared = _prepare_action(final_validation.action_context)
    context = prepared.context
    issued = stage17_state_journal.parse_utc(
        context["authorization"]["issued_at_utc"], "actual authority issue"
    )
    expires = stage17_state_journal.parse_utc(
        context["authorization"]["expires_at_utc"], "actual authority expiry"
    )
    actual = stage17_state_journal.parse_utc(actual_now, "actual execution UTC")
    if not issued <= actual < expires:
        raise ActionExecutionError("authorization is not live at actual system UTC")

    directory_fd = _open_evidence_root(context)
    marker_created = False
    action_started_ns = time.monotonic_ns()
    deadline_ns = action_started_ns + int(context["max_wall_seconds"]) * 1_000_000_000
    marker = {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/2",
        "attempt_id": context["attempt_id"],
        "authorization_id": context["authorization_id"],
        "authorization_sha256": context["authorization_sha256"],
        "resolution_id": context["resolution_id"],
        "resolution_sha256": context["resolution_sha256"],
        "transition_id": context["transition_id"],
        "transition_sha256": context["transition_sha256"],
        "action_plan_sha256": context["action_plan_sha256"],
        "runtime_implementation_hashes": context["runtime_implementation_hashes"],
        "ssh_argv_sha256": prepared.ssh_argv_sha256,
        "rendered_programs": list(prepared.program_descriptors),
        "actual_started_at_utc": actual_now,
        "monotonic_deadline_ns": deadline_ns,
        "attempt_number": 1,
        "retry_allowed": False,
        "transport_may_start_after_durable_marker": True,
        "stage18_authority": False,
    }
    _schema(context["record_schema_paths"]["attempt"], marker, "attempt marker")
    try:
        _write_exclusive_at(
            directory_fd,
            context["attempt_marker_name"],
            stage17_state_journal.canonical_json_bytes(marker) + b"\n",
        )
        marker_created = True
    except FileExistsError as exception:
        os.close(directory_fd)
        raise ActionExecutionError("one-shot attempt marker already exists") from exception
    except BaseException:
        os.close(directory_fd)
        raise

    completed: list[str] = []
    receipt_hashes: list[str] = []
    total_output = 0
    active_descriptor: dict[str, Any] | None = None
    try:
        for descriptor, program in zip(
            prepared.program_descriptors, prepared.programs, strict=True
        ):
            active_descriptor = descriptor
            remaining = _remaining_seconds(deadline_ns)
            timeout = min(float(context["timeout_seconds"]), remaining)
            observation_started_utc = _actual_utc_now()
            observation_started_ns = time.monotonic_ns()
            try:
                result = _transport_once(
                    prepared.ssh_argv,
                    program,
                    timeout,
                    int(context["max_output_bytes"]),
                )
            except BaseException as exception:
                raise OperationalFailure(
                    "TRANSPORT",
                    "TRANSPORT_EXCEPTION",
                    _reason(exception),
                    descriptor["ordinal"],
                    descriptor["observation_id"],
                    descriptor["sha256"],
                ) from exception
            _remaining_seconds(deadline_ns)
            total_output += len(result.stdout) + len(result.stderr)
            if total_output > int(context["max_total_output_bytes"]):
                raise OperationalFailure(
                    "GLOBAL_DEADLINE",
                    "TOTAL_OUTPUT_LIMIT_EXCEEDED",
                    "total output exceeded the fixed action limit",
                    descriptor["ordinal"],
                    descriptor["observation_id"],
                    descriptor["sha256"],
                )
            ordinal = descriptor["ordinal"]
            try:
                _write_exclusive_at(
                    directory_fd, f"s17-ro-{ordinal:03d}.stdout.bin", result.stdout
                )
                _write_exclusive_at(
                    directory_fd, f"s17-ro-{ordinal:03d}.stderr.bin", result.stderr
                )
            except BaseException as exception:
                raise OperationalFailure(
                    "OUTPUT_RETENTION",
                    "OUTPUT_WRITE_EXCEPTION",
                    _reason(exception),
                    ordinal,
                    descriptor["observation_id"],
                    descriptor["sha256"],
                ) from exception
            receipt = {
                "schema_version": "cpu-prefetch-stage17-read-only-preflight-observation-receipt/1",
                **_base_links(context),
                "ordinal": ordinal,
                "observation_id": descriptor["observation_id"],
                "rendered_program_sha256": descriptor["sha256"],
                "ssh_argv_sha256": prepared.ssh_argv_sha256,
                "actual_started_at_utc": observation_started_utc,
                "actual_completed_at_utc": _actual_utc_now(),
                "duration_ns": max(0, time.monotonic_ns() - observation_started_ns),
                "returncode": result.returncode,
                "failure": result.failure,
                "stdout_size_bytes": len(result.stdout),
                "stdout_sha256": _sha256_bytes(result.stdout),
                "stderr_size_bytes": len(result.stderr),
                "stderr_sha256": _sha256_bytes(result.stderr),
                "attempt": 1,
                "retry": 0,
                "stage18_authority": False,
            }
            try:
                _schema(context["record_schema_paths"]["receipt"], receipt, "observation receipt")
                receipt_hashes.append(
                    _write_exclusive_at(
                        directory_fd,
                        f"s17-ro-{ordinal:03d}.receipt-v1.json",
                        stage17_state_journal.canonical_json_bytes(receipt) + b"\n",
                    )
                )
            except BaseException as exception:
                raise OperationalFailure(
                    "RECEIPT_RETENTION",
                    "RECEIPT_WRITE_EXCEPTION",
                    _reason(exception),
                    ordinal,
                    descriptor["observation_id"],
                    descriptor["sha256"],
                ) from exception
            if result.failure is not None or result.returncode != 0:
                raise OperationalFailure(
                    "TRANSPORT",
                    result.failure or "REMOTE_NONZERO_EXIT",
                    result.failure or f"remote exit {result.returncode}",
                    ordinal,
                    descriptor["observation_id"],
                    descriptor["sha256"],
                )
            completed.append(descriptor["observation_id"])
            _remaining_seconds(deadline_ns)
        completion = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-completion/1",
            **_base_links(context),
            "ssh_argv_sha256": prepared.ssh_argv_sha256,
            "completed_observation_ids": completed,
            "receipt_sha256s": receipt_hashes,
            "actual_started_at_utc": actual_now,
            "actual_completed_at_utc": _actual_utc_now(),
            "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
            "attempts": 6,
            "retries": 0,
            "stage18_authority": False,
        }
        _schema(context["record_schema_paths"]["completion"], completion, "completion record")
        _remaining_seconds(deadline_ns)
        try:
            _write_exclusive_at(
                directory_fd,
                context["completion_name"],
                stage17_state_journal.canonical_json_bytes(completion) + b"\n",
            )
        except BaseException as exception:
            raise OperationalFailure(
                "COMPLETION_RETENTION",
                "COMPLETION_WRITE_EXCEPTION",
                _reason(exception),
            ) from exception
    except BaseException as exception:
        if isinstance(exception, OperationalFailure):
            failure = exception
        else:
            failure = OperationalFailure(
                "UNEXPECTED_OPERATIONAL_EXCEPTION",
                "UNEXPECTED_OPERATIONAL_EXCEPTION",
                _reason(exception),
                active_descriptor["ordinal"] if active_descriptor else None,
                active_descriptor["observation_id"] if active_descriptor else None,
                active_descriptor["sha256"] if active_descriptor else None,
            )
        try:
            _write_failure(
                directory_fd=directory_fd,
                prepared=prepared,
                failure=failure,
                completed=completed,
                action_started_ns=action_started_ns,
            )
        except BaseException:
            pass
        raise ActionExecutionError(
            f"fixed read-only preflight stopped: {failure.category}"
        ) from exception
    finally:
        if marker_created:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
        os.close(directory_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root,
            latest_journal=arguments.journal,
            journal_directory=arguments.journal_directory,
        )
    except (ActionExecutionError, stage17_state_journal.JournalError, OSError, ValueError) as exception:
        print(f"stage17-read-only-preflight-v2: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-read-only-preflight-v2: PASS fixed=6 retry=0 Stage18=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
