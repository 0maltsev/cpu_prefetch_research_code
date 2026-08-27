#!/usr/bin/env python3
"""Authority-guarded, child-owning Stage 17 read-only preflight executor.

Production accepts no caller authority time, command, argv, stdin, remote
command, transport factory, retry, credential bytes, or output filename.
"""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import pathlib
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator

import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_pilot_candidate_artifact
import stage17_read_only_preflight_collector_v1
import stage17_read_only_preflight_collector_v2
import stage17_semantic_verifier_v3
import stage17_semantic_verifier_v4
import stage17_semantic_verifier_v5
import stage17_semantic_verifier_v6
import stage17_semantic_verifier_v7
import stage17_state_journal
import stage17_state_journal_v2
import stage17_state_journal_v3
import stage17_state_journal_v4


EXECUTOR_ID = "STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v5"
FIXED_LOCAL_ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "TZ": "UTC0"}
SAFE_CHILD_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ActionExecutionError(RuntimeError):
    """The fixed one-shot action was rejected or failed."""


class PreMarkerBlocker(ActionExecutionError):
    """Typed fail-closed rejection before one-shot consumption begins."""

    def __init__(self, category: str, reason: str):
        super().__init__(f"{category}: {reason}")
        self.category = category
        self.reason = reason


@dataclass(frozen=True)
class TransportResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    failure: str | None = None
    authority_sample_utc: str | None = None
    child_reaped: bool = True
    process_group_cleanup: str = "NOT_STARTED"


class TransportLifecycleError(ActionExecutionError):
    """A transport failure after its final authority boundary."""

    def __init__(
        self,
        category: str,
        reason: str,
        *,
        authority_sample_utc: str | None,
        child_started: bool,
        child_reaped: bool,
        process_group_cleanup: str,
    ) -> None:
        super().__init__(f"{category}: {reason}")
        self.category = category
        self.reason = reason
        self.authority_sample_utc = authority_sample_utc
        self.child_started = child_started
        self.child_reaped = child_reaped
        self.process_group_cleanup = process_group_cleanup


@dataclass
class PreparedAction:
    context: dict[str, Any]
    ssh_argv: tuple[str, ...]
    ssh_argv_sha256: str
    programs: tuple[bytes, ...]
    program_descriptors: tuple[dict[str, Any], ...]
    snapshots: tuple[snapshot_broker.ParentSnapshot, snapshot_broker.ParentSnapshot]
    pinned_inputs_metadata: dict[str, Any]
    pinned_inputs_metadata_sha256: str
    openssh_capability: dict[str, Any]
    record_validators: dict[str, Draft202012Validator]
    directory_fd: int
    attempt_marker_sha256: str | None = None

    def close(self) -> None:
        try:
            os.close(self.directory_fd)
        except OSError:
            pass
        snapshot_broker.close_snapshots(*self.snapshots)


@dataclass(frozen=True)
class OperationalFailure(Exception):
    stage: str
    category: str
    reason: str
    ordinal: int | None = None
    observation_id: str | None = None
    program_sha256: str | None = None
    authority_clock_relation: str = "LIVE_NONDECREASING"
    child_started: bool = False
    child_reaped: bool = True
    process_group_cleanup: str = "NOT_STARTED"
    transport_authority_sample_utc: str | None = None


def runtime_identity_paths() -> dict[str, str]:
    """Return the exact loaded policy-v7 runtime closure."""

    return {
        "semantic_verifier": str(pathlib.Path(stage17_semantic_verifier_v7.__file__).resolve()),
        "executor": str(pathlib.Path(__file__).resolve()),
        "collector": str(pathlib.Path(stage17_read_only_preflight_collector_v2.__file__).resolve()),
        "state_journal": str(pathlib.Path(stage17_state_journal_v4.__file__).resolve()),
        "openssh_snapshot_broker": str(pathlib.Path(snapshot_broker.__file__).resolve()),
        "semantic_verifier_v6_helper": str(pathlib.Path(stage17_semantic_verifier_v6.__file__).resolve()),
        "semantic_verifier_v5_helper": str(pathlib.Path(stage17_semantic_verifier_v5.__file__).resolve()),
        "semantic_verifier_v4_helper": str(pathlib.Path(stage17_semantic_verifier_v4.__file__).resolve()),
        "semantic_verifier_v3_helper": str(pathlib.Path(stage17_semantic_verifier_v3.__file__).resolve()),
        "collector_v1_helper": str(pathlib.Path(stage17_read_only_preflight_collector_v1.__file__).resolve()),
        "state_journal_v3_helper": str(pathlib.Path(stage17_state_journal_v3.__file__).resolve()),
        "state_journal_v2_helper": str(pathlib.Path(stage17_state_journal_v2.__file__).resolve()),
        "state_journal_v1_helper": str(pathlib.Path(stage17_state_journal.__file__).resolve()),
        "pilot_candidate_verifier": str(pathlib.Path(stage17_pilot_candidate_artifact.__file__).resolve()),
    }


def _actual_utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _argv_bytes(argv: tuple[str, ...]) -> bytes:
    values: list[bytes] = []
    for item in argv:
        encoded = item.encode("utf-8", errors="strict")
        if b"\x00" in encoded:
            raise ActionExecutionError("fixed SSH argv contains NUL")
        values.append(encoded)
    return b"\x00".join(values) + b"\x00"


def _ssh_argv(
    context: dict[str, Any],
    known_hosts: snapshot_broker.ParentSnapshot,
    identity: snapshot_broker.ParentSnapshot,
) -> tuple[str, ...]:
    substitutions = {
        "{PARENT_PROCFD_KNOWN_HOSTS_LOCATOR}": known_hosts.locator,
        "{PARENT_PROCFD_TRANSPORT_IDENTITY_LOCATOR}": identity.locator,
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
    argv = tuple(rendered)
    if not argv or argv[0] != "/usr/bin/ssh":
        raise ActionExecutionError("fixed SSH executable drifted")
    return argv


def _load_record_validator(
    root: pathlib.Path, binding: dict[str, Any], label: str
) -> Draft202012Validator:
    path = root / binding["path"]
    payload = path.read_bytes()
    if len(payload) != binding["size_bytes"] or _sha256_bytes(payload) != binding["sha256"]:
        raise ActionExecutionError(f"{label} schema bytes drifted before marker")
    try:
        schema = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exception:
        raise ActionExecutionError(f"{label} schema is malformed") from exception
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate_record(
    prepared: PreparedAction, kind: str, document: dict[str, Any], label: str
) -> None:
    errors = list(prepared.record_validators[kind].iter_errors(document))
    if errors:
        first = errors[0]
        location = "/".join(str(item) for item in first.absolute_path)
        raise ActionExecutionError(f"{label} schema error at $/{location}: {first.message}")


def _open_evidence_root(context: dict[str, Any]) -> int:
    descriptor = os.open(
        context["evidence_root"],
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
    )
    metadata = os.fstat(descriptor)
    actual = {
        "device": metadata.st_dev, "inode": metadata.st_ino,
        "uid": metadata.st_uid, "mode": stat.S_IMODE(metadata.st_mode),
    }
    if not stat.S_ISDIR(metadata.st_mode) or actual != context["evidence_root_identity"]:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root directory identity changed")
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o022:
        os.close(descriptor)
        raise ActionExecutionError("evidence-root ownership or permissions are unsafe")
    return descriptor


def _child_exists(directory_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _verify_pre_marker_bindings(context: dict[str, Any]) -> None:
    for binding in context["pre_marker_file_bindings"]:
        path = pathlib.Path(binding["locator"])
        payload = path.read_bytes()
        if len(payload) != binding["size_bytes"] or _sha256_bytes(payload) != binding["sha256"]:
            raise ActionExecutionError("prospective repository input drifted during preparation")


def _all_one_shot_names(context: dict[str, Any]) -> list[str]:
    names = [
        *(f"stage17-read-only-preflight-attempt-v{version}.json" for version in range(1, 6)),
        "stage17-read-only-preflight-failure-v2.json",
        "stage17-read-only-preflight-failure-v3.json",
        "stage17-read-only-preflight-failure-v4.json",
        context["failure_name"],
        "stage17-read-only-preflight-completion-v1.json",
        "stage17-read-only-preflight-completion-v2.json",
        "stage17-read-only-preflight-completion-v3.json",
        context["completion_name"],
    ]
    names.extend(
        f"s17-ro-{ordinal:03d}{suffix}"
        for ordinal in range(1, 7)
        for suffix in (
            ".stdout.bin", ".stderr.bin", ".receipt-v1.json",
            ".receipt-v2.json", ".receipt-v3.json", ".receipt-v4.json",
        )
    )
    return names


def _prepare_action(repository_root: pathlib.Path, context: dict[str, Any]) -> PreparedAction:
    snapshots: list[snapshot_broker.ParentSnapshot] = []
    directory_fd: int | None = None
    try:
        try:
            known_hosts = snapshot_broker.pin_bound_input(
                context["known_hosts_binding"], "KNOWN_HOSTS"
            )
            snapshots.append(known_hosts)
            identity = snapshot_broker.pin_bound_input(
                context["transport_identity_binding"], "TRANSPORT_IDENTITY"
            )
            snapshots.append(identity)
            snapshot_broker.validate_identity_parseability(identity)
        except snapshot_broker.SnapshotError as exception:
            raise PreMarkerBlocker("OPENSSH_INPUT_PINNING_BLOCKED", str(exception)) from exception
        argv = _ssh_argv(context, known_hosts, identity)
        programs: list[bytes] = []
        descriptors: list[dict[str, Any]] = []
        for ordinal, observation_id in enumerate(context["observation_ids"], start=1):
            program = stage17_read_only_preflight_collector_v2.render_observation_program(
                observation_id, context["collector_context"]
            )
            compile(program, f"<stage17:{observation_id}>", "exec")
            programs.append(program)
            descriptors.append({
                "ordinal": ordinal, "observation_id": observation_id,
                "size_bytes": len(program), "sha256": _sha256_bytes(program),
            })
        validators = {
            kind: _load_record_validator(repository_root, binding, kind)
            for kind, binding in context["record_schema_bindings"].items()
        }
        directory_fd = _open_evidence_root(context)
        names = _all_one_shot_names(context)
        if any(SAFE_CHILD_NAME.fullmatch(name) is None for name in names):
            raise ActionExecutionError("fixed output name is unsafe")
        if any(_child_exists(directory_fd, name) for name in names):
            raise ActionExecutionError("one-shot predecessor/current output appeared during preparation")
        _verify_pre_marker_bindings(context)
        try:
            snapshot_broker.verify_snapshot(known_hosts)
            snapshot_broker.verify_snapshot(identity)
            capability = snapshot_broker.verify_local_openssh_parent_procfd_capability()
            snapshot_broker.verify_snapshot(known_hosts)
            snapshot_broker.verify_snapshot(identity)
        except snapshot_broker.SnapshotError as exception:
            raise PreMarkerBlocker("OPENSSH_CONSUMPTION_CAPABILITY_BLOCKED", str(exception)) from exception
        metadata = {
            "known_hosts": known_hosts.metadata,
            "transport_identity": identity.metadata,
        }
        result = PreparedAction(
            context=context, ssh_argv=argv,
            ssh_argv_sha256=_sha256_bytes(_argv_bytes(argv)),
            programs=tuple(programs), program_descriptors=tuple(descriptors),
            snapshots=(known_hosts, identity), pinned_inputs_metadata=metadata,
            pinned_inputs_metadata_sha256=_sha256_bytes(
                stage17_state_journal_v3.canonical_json_bytes(metadata)
            ),
            openssh_capability=capability, record_validators=validators,
            directory_fd=directory_fd,
        )
        directory_fd = None
        snapshots.clear()
        return result
    except (PreMarkerBlocker, ActionExecutionError):
        raise
    except BaseException as exception:
        raise PreMarkerBlocker("PRE_MARKER_PREPARATION_BLOCKED", _reason(exception)) from exception
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        snapshot_broker.close_snapshots(*snapshots)


CLEANUP_RESERVE_NS = 2_000_000_000
AuthorityGuard = Callable[[], str]


def _remaining_cleanup_seconds(deadline_ns: int, cap_seconds: float) -> float:
    remaining = (deadline_ns - time.monotonic_ns()) / 1_000_000_000
    return max(0.001, min(cap_seconds, remaining))


def _waitpid_until(process: subprocess.Popen[bytes], deadline_ns: int) -> bool:
    """Reap after mocked/repeated Popen.wait timeouts without leaking a child."""

    while time.monotonic_ns() < deadline_ns:
        try:
            pid, status_value = os.waitpid(process.pid, os.WNOHANG)
        except ChildProcessError:
            if process.returncode is None:
                process.returncode = -signal.SIGKILL
            return True
        if pid == process.pid:
            process.returncode = os.waitstatus_to_exitcode(status_value)
            return True
        time.sleep(0.005)
    return False


def _blocking_waitpid_reap(
    process: subprocess.Popen[bytes], cleanup_errors: list[str]
) -> bool:
    """Final SIGKILL reap barrier; it may overrun the deadline but never leaks."""

    while True:
        try:
            pid, status_value = os.waitpid(process.pid, 0)
        except InterruptedError:
            continue
        except ChildProcessError:
            if process.returncode is None:
                process.returncode = -signal.SIGKILL
            return True
        except OSError as exception:
            if exception.errno == errno.ECHILD:
                if process.returncode is None:
                    process.returncode = -signal.SIGKILL
                return True
            cleanup_errors.append(f"FINAL_WAITPID:{type(exception).__name__}")
            return False
        if pid == process.pid:
            process.returncode = os.waitstatus_to_exitcode(status_value)
            return True


def _terminate_and_reap(
    process: subprocess.Popen[bytes], *, deadline_ns: int, force_group_stop: bool
) -> tuple[bool, str, str | None]:
    """Own, stop, and reap one process group within the reserved deadline."""

    state = "NORMAL_EXIT_REAPED"
    cleanup_errors: list[str] = []
    try:
        alive = process.poll() is None
    except BaseException as exception:
        cleanup_errors.append(f"POLL:{type(exception).__name__}")
        alive = True
    if force_group_stop or alive:
        state = "SIGTERM_GROUP_REAPED"
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exception:
            cleanup_errors.append(f"SIGTERM:{type(exception).__name__}")
        term_timed_out = False
        try:
            process.wait(timeout=_remaining_cleanup_seconds(deadline_ns, 0.5))
        except subprocess.TimeoutExpired:
            term_timed_out = True
        except BaseException as exception:
            cleanup_errors.append(f"WAIT_AFTER_SIGTERM:{type(exception).__name__}")
            term_timed_out = True
        if term_timed_out:
            state = "SIGKILL_GROUP_REAPED"
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exception:
                cleanup_errors.append(f"SIGKILL:{type(exception).__name__}")
            kill_timed_out = False
            try:
                process.wait(timeout=_remaining_cleanup_seconds(deadline_ns, 1.0))
            except subprocess.TimeoutExpired:
                kill_timed_out = True
            except BaseException as exception:
                cleanup_errors.append(f"WAIT_AFTER_SIGKILL:{type(exception).__name__}")
                kill_timed_out = True
            if kill_timed_out:
                state = "SIGKILL_WAITPID_REAPED"
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exception:
                    cleanup_errors.append(f"SIGKILL_REPEAT:{type(exception).__name__}")
                if not _waitpid_until(process, deadline_ns):
                    cleanup_errors.append("REAP_DEADLINE_EXPIRED")
    else:
        try:
            process.wait(timeout=_remaining_cleanup_seconds(deadline_ns, 0.25))
        except subprocess.TimeoutExpired:
            state = "SIGKILL_GROUP_REAPED"
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exception:
                cleanup_errors.append(f"SIGKILL:{type(exception).__name__}")
            if not _waitpid_until(process, deadline_ns):
                cleanup_errors.append("REAP_DEADLINE_EXPIRED")
        except BaseException as exception:
            cleanup_errors.append(f"WAIT_NORMAL:{type(exception).__name__}")
    if process.returncode is None:
        state = "SIGKILL_FINAL_WAITPID_REAPED"
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError as exception:
            cleanup_errors.append(f"SIGKILL_FINAL:{type(exception).__name__}")
        if not _blocking_waitpid_reap(process, cleanup_errors):
            cleanup_errors.append("FINAL_REAP_UNCONFIRMED")
    reaped = process.returncode is not None
    if not reaped:
        cleanup_errors.append("CHILD_NOT_REAPED")
    return reaped, state if reaped else "CLEANUP_FAILED", ";".join(cleanup_errors) or None


def _transport_once(
    argv: tuple[str, ...], stdin: bytes, timeout_seconds: float, output_limit: int,
    *, global_deadline_ns: int, authority_guard: AuthorityGuard,
) -> TransportResult:
    """Guard, open, exclusively own, terminate, and reap one transport group."""

    popen_argv = list(argv)
    selector = selectors.DefaultSelector()
    authority_sample_utc: str | None = None
    process: subprocess.Popen[bytes] | None = None
    streams: dict[int, tuple[str, Any]] = {}
    output = {"stdout": bytearray(), "stderr": bytearray()}
    failure: str | None = None
    primary: BaseException | None = None
    cleanup_error: str | None = None
    child_reaped = True
    cleanup_state = "NOT_STARTED"
    try:
        # This is the final fallible preparation boundary. Popen is the next
        # operation after the system/monotonic authority guard returns.
        authority_sample_utc = authority_guard()
        try:
            process = subprocess.Popen(
                popen_argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, shell=False, env=FIXED_LOCAL_ENVIRONMENT,
                close_fds=True, start_new_session=True,
            )
        except BaseException as exception:
            raise TransportLifecycleError(
                "POPEN_EXCEPTION", _reason(exception),
                authority_sample_utc=authority_sample_utc, child_started=False,
                child_reaped=True, process_group_cleanup="NOT_STARTED",
            ) from exception
        try:
            if process.stdin is None or process.stdout is None or process.stderr is None:
                raise ActionExecutionError("transport pipes were not created")
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
            work_deadline_ns = min(
                time.monotonic_ns() + int(timeout_seconds * 1_000_000_000),
                global_deadline_ns - CLEANUP_RESERVE_NS,
            )
            while selector.get_map():
                remaining_ns = work_deadline_ns - time.monotonic_ns()
                if remaining_ns <= 0:
                    failure = "TIMEOUT"
                    break
                events = selector.select(min(remaining_ns / 1_000_000_000, 0.25))
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
                        remaining_output = (
                            output_limit - len(output["stdout"]) - len(output["stderr"])
                        )
                        if len(chunk) > remaining_output:
                            output[kind].extend(chunk[:max(remaining_output, 0)])
                            failure = "OUTPUT_LIMIT_EXCEEDED"
                            break
                        output[kind].extend(chunk)
                if failure is not None:
                    break
        except BaseException as exception:
            primary = exception
        finally:
            secondary_cleanup_errors: list[str] = []
            try:
                selector.close()
            except BaseException as exception:
                if primary is None:
                    primary = exception
                else:
                    secondary_cleanup_errors.append(
                        f"SELECTOR_CLOSE:{type(exception).__name__}"
                    )
            for _, stream in streams.values():
                try:
                    stream.close()
                except BaseException as exception:
                    if primary is None:
                        primary = exception
                    else:
                        secondary_cleanup_errors.append(
                            f"PIPE_CLOSE:{type(exception).__name__}"
                        )
            try:
                child_reaped, cleanup_state, cleanup_error = _terminate_and_reap(
                    process, deadline_ns=global_deadline_ns,
                    force_group_stop=primary is not None or failure is not None,
                )
            except BaseException as exception:
                secondary_cleanup_errors.append(
                    f"TERMINATION_BOUNDARY:{type(exception).__name__}"
                )
                if primary is None:
                    primary = exception
                cleanup_state = "SIGKILL_FINAL_WAITPID_REAPED"
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as kill_exception:
                    secondary_cleanup_errors.append(
                        f"SIGKILL_EMERGENCY:{type(kill_exception).__name__}"
                    )
                child_reaped = _blocking_waitpid_reap(
                    process, secondary_cleanup_errors
                )
            if secondary_cleanup_errors:
                suffix = ";".join(secondary_cleanup_errors)
                cleanup_error = (
                    f"{cleanup_error};{suffix}" if cleanup_error else suffix
                )
    finally:
        if process is None:
            try:
                selector.close()
            except BaseException:
                pass
    if primary is not None or cleanup_error is not None or not child_reaped:
        category = "TRANSPORT_RUNTIME_EXCEPTION" if primary is not None else "PROCESS_CLEANUP_FAILURE"
        reason = _reason(primary) if primary is not None else str(cleanup_error)
        if cleanup_error is not None:
            reason = f"{reason}; cleanup={cleanup_error}"[:512]
        raise TransportLifecycleError(
            category, reason, authority_sample_utc=authority_sample_utc,
            child_started=True, child_reaped=child_reaped,
            process_group_cleanup=cleanup_state,
        ) from primary
    assert process is not None and process.returncode is not None
    return TransportResult(
        returncode=process.returncode, stdout=bytes(output["stdout"]),
        stderr=bytes(output["stderr"]), failure=failure,
        authority_sample_utc=authority_sample_utc, child_reaped=child_reaped,
        process_group_cleanup=cleanup_state,
    )


def _write_exclusive_at(
    directory_fd: int, name: str, payload: bytes, *, sync_directory: bool = True
) -> str:
    if SAFE_CHILD_NAME.fullmatch(name) is None:
        raise ActionExecutionError("unsafe fixed child name")
    descriptor = os.open(
        name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600, dir_fd=directory_fd,
    )
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


def _timedelta_ns(value: dt.timedelta) -> int:
    return (
        (value.days * 86400 + value.seconds) * 1_000_000_000
        + value.microseconds * 1000
    )


def _reason(exception: BaseException) -> str:
    value = " ".join(f"{type(exception).__name__}: {exception}".split())
    return value[:512] or type(exception).__name__


def _base_links(prepared: PreparedAction) -> dict[str, Any]:
    if prepared.attempt_marker_sha256 is None:
        raise ActionExecutionError("post-marker record has no attempt-marker binding")
    context = prepared.context
    hashes = context["runtime_implementation_hashes"]
    return {
        "attempt_id": context["attempt_id"],
        "attempt_marker_sha256": prepared.attempt_marker_sha256,
        "authorization_id": context["authorization_id"],
        "authorization_sha256": context["authorization_sha256"],
        "resolution_id": context["resolution_id"], "resolution_sha256": context["resolution_sha256"],
        "transition_id": context["transition_id"], "transition_sha256": context["transition_sha256"],
        "action_plan_sha256": context["action_plan_sha256"],
        "runtime_implementation_hashes": dict(hashes),
        "executor_sha256": hashes["executor"], "collector_sha256": hashes["collector"],
        "pinned_inputs_metadata_sha256": prepared.pinned_inputs_metadata_sha256,
        "consumed_known_hosts_sha256": prepared.snapshots[0].metadata["consumed_sha256"],
        "consumed_transport_identity_sha256": prepared.snapshots[1].metadata["consumed_sha256"],
        "openssh_consumption_capability_sha256": prepared.openssh_capability["report_sha256"],
    }


def _safe_failure_time(fallback: str) -> str:
    try:
        return _actual_utc_now()
    except BaseException:
        return fallback


def _write_failure(
    *, prepared: PreparedAction, failure: OperationalFailure, completed: list[str],
    action_started_ns: int, before_marker_utc: str, before_transport_utc: str | None,
) -> None:
    document = {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-failure/5",
        **_base_links(prepared), "failed_stage": failure.stage,
        "failed_ordinal": failure.ordinal, "failed_observation_id": failure.observation_id,
        "completed_observation_ids": list(completed), "reason_category": failure.category,
        "reason": failure.reason[:512],
        "actual_authority_sample_before_marker_utc": before_marker_utc,
        "actual_authority_sample_before_first_transport_utc": before_transport_utc,
        "transport_authority_sample_utc": failure.transport_authority_sample_utc,
        "authority_clock_relation": failure.authority_clock_relation,
        "actual_failed_at_utc": _safe_failure_time(before_transport_utc or before_marker_utc),
        "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
        "ssh_argv_sha256": prepared.ssh_argv_sha256,
        "rendered_program_sha256": failure.program_sha256,
        "child_started": failure.child_started,
        "child_reaped": failure.child_reaped,
        "process_group_cleanup": failure.process_group_cleanup,
        "retry_allowed": False, "partial_evidence_retained": True,
        "stage18_authority": False,
    }
    _validate_record(prepared, "failure", document, "failure record")
    _write_exclusive_at(
        prepared.directory_fd, prepared.context["failure_name"],
        stage17_state_journal_v3.canonical_json_bytes(document) + b"\n",
    )


def _prospective_validation(
    *, repository_root: pathlib.Path, latest_journal: pathlib.Path,
    journal_directory: pathlib.Path, actual_utc: str,
) -> stage17_state_journal_v4.JournalValidation:
    return stage17_state_journal_v4.validate_journal(
        repository_root=repository_root, latest_journal=latest_journal,
        journal_directory=journal_directory, as_of_utc=actual_utc,
        requested_action_input_id="S17-EXT-001",
        runtime_identity_paths=runtime_identity_paths(),
    )


def _authority_relation(
    *, sample: dt.datetime, previous: dt.datetime,
    issued: dt.datetime, expires: dt.datetime,
) -> str:
    if sample < previous:
        return "ROLLBACK"
    if sample < issued:
        return "NOT_YET_VALID"
    if sample >= expires:
        return "EXPIRED"
    return "LIVE_NONDECREASING"


def execute_once(
    *, repository_root: pathlib.Path, latest_journal: pathlib.Path,
    journal_directory: pathlib.Path,
) -> None:
    """Execute one admitted action with a final per-Popen authority guard."""

    prospective_utc = _actual_utc_now()
    validation = _prospective_validation(
        repository_root=repository_root, latest_journal=latest_journal,
        journal_directory=journal_directory, actual_utc=prospective_utc,
    )
    if not validation.action_ready or validation.action_context is None:
        raise ActionExecutionError("S17-EXT-001 is not prospectively action-ready")
    prepared = _prepare_action(repository_root.resolve(), validation.action_context)
    marker_created = False
    action_started_ns = 0
    before_transport_utc: str | None = None
    try:
        before_marker_monotonic_ns = time.monotonic_ns()
        before_marker_utc = _actual_utc_now()
        context = prepared.context
        issued = stage17_state_journal_v4.parse_utc(
            context["authorization"]["issued_at_utc"], "actual authority issue"
        )
        expires = stage17_state_journal_v4.parse_utc(
            context["authorization"]["expires_at_utc"], "actual authority expiry"
        )
        prospective = stage17_state_journal_v4.parse_utc(
            prospective_utc, "prospective authority UTC"
        )
        before_marker = stage17_state_journal_v4.parse_utc(
            before_marker_utc, "actual pre-marker UTC"
        )
        relation = _authority_relation(
            sample=before_marker, previous=prospective, issued=issued, expires=expires
        )
        if relation != "LIVE_NONDECREASING":
            raise ActionExecutionError(f"authorization rejected before marker: {relation}")
        action_started_ns = before_marker_monotonic_ns
        deadline_ns = action_started_ns + int(context["max_wall_seconds"]) * 1_000_000_000
        authority_deadline_ns = (
            before_marker_monotonic_ns + _timedelta_ns(expires - before_marker)
        )
        if authority_deadline_ns <= before_marker_monotonic_ns:
            raise ActionExecutionError("authorization has no positive monotonic lifetime")
        marker = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/5",
            "attempt_id": context["attempt_id"], "authorization_id": context["authorization_id"],
            "authorization_sha256": context["authorization_sha256"],
            "resolution_id": context["resolution_id"], "resolution_sha256": context["resolution_sha256"],
            "transition_id": context["transition_id"], "transition_sha256": context["transition_sha256"],
            "action_plan_sha256": context["action_plan_sha256"],
            "runtime_implementation_hashes": context["runtime_implementation_hashes"],
            "ssh_argv_sha256": prepared.ssh_argv_sha256,
            "rendered_programs": list(prepared.program_descriptors),
            "pinned_openssh_inputs": prepared.pinned_inputs_metadata,
            "openssh_consumption_capability": prepared.openssh_capability,
            "prospective_evaluation_at_utc": prospective_utc,
            "actual_authority_sample_before_marker_utc": before_marker_utc,
            "monotonic_deadline_ns": deadline_ns,
            "monotonic_authority_deadline_ns": authority_deadline_ns,
            "process_group_ownership": "START_NEW_SESSION_TERMINATE_GROUP_REAP_BEFORE_EVIDENCE",
            "attempt_number": 1,
            "retry_allowed": False, "post_marker_authority_sample_required": True,
            "stage18_authority": False,
        }
        _validate_record(prepared, "attempt", marker, "attempt marker")
        try:
            prepared.attempt_marker_sha256 = _write_exclusive_at(
                prepared.directory_fd, context["attempt_marker_name"],
                stage17_state_journal_v4.canonical_json_bytes(marker) + b"\n",
            )
            marker_created = True
        except FileExistsError as exception:
            raise ActionExecutionError("one-shot attempt marker already exists") from exception
        completed: list[str] = []
        receipt_hashes: list[str] = []
        total_output = 0
        active_descriptor: dict[str, Any] | None = None
        previous_authority_sample = before_marker
        try:
            for descriptor, program in zip(prepared.program_descriptors, prepared.programs, strict=True):
                active_descriptor = descriptor
                try:
                    snapshot_broker.verify_snapshot(prepared.snapshots[0])
                    snapshot_broker.verify_snapshot(prepared.snapshots[1])
                except BaseException as exception:
                    raise OperationalFailure(
                        "TRANSPORT", "SNAPSHOT_REVERIFY_EXCEPTION", _reason(exception),
                        descriptor["ordinal"], descriptor["observation_id"],
                        descriptor["sha256"], child_started=False, child_reaped=True,
                        process_group_cleanup="NOT_STARTED",
                    ) from exception
                remaining_ns = deadline_ns - time.monotonic_ns()
                if remaining_ns <= CLEANUP_RESERVE_NS:
                    raise OperationalFailure(
                        "GLOBAL_DEADLINE", "GLOBAL_WALL_TIMEOUT",
                        "global deadline reached its process-cleanup reserve",
                        descriptor["ordinal"], descriptor["observation_id"],
                        descriptor["sha256"],
                    )
                timeout = min(
                    float(context["timeout_seconds"]),
                    (remaining_ns - CLEANUP_RESERVE_NS) / 1_000_000_000,
                )

                def final_authority_guard() -> str:
                    nonlocal before_transport_utc, previous_authority_sample
                    try:
                        actual_utc = _actual_utc_now()
                        actual = stage17_state_journal_v4.parse_utc(
                            actual_utc, "actual transport-boundary UTC"
                        )
                    except BaseException as exception:
                        raise OperationalFailure(
                            "AUTHORITY_TIME", "AUTHORITY_CLOCK_READ_FAILURE", _reason(exception),
                            descriptor["ordinal"], descriptor["observation_id"],
                            descriptor["sha256"],
                            authority_clock_relation="CLOCK_READ_FAILURE",
                        ) from exception
                    relation = _authority_relation(
                        sample=actual, previous=previous_authority_sample,
                        issued=issued, expires=expires,
                    )
                    if relation != "LIVE_NONDECREASING":
                        raise OperationalFailure(
                            "AUTHORITY_TIME", f"AUTHORITY_{relation}_BEFORE_TRANSPORT",
                            f"transport-boundary authority sample rejected: {relation}",
                            descriptor["ordinal"], descriptor["observation_id"],
                            descriptor["sha256"],
                            authority_clock_relation=relation,
                            transport_authority_sample_utc=actual_utc,
                        )
                    monotonic_now = time.monotonic_ns()
                    if monotonic_now >= authority_deadline_ns:
                        raise OperationalFailure(
                            "AUTHORITY_TIME", "AUTHORITY_MONOTONIC_EXPIRED_BEFORE_TRANSPORT",
                            "monotonic authorization deadline expired before transport",
                            descriptor["ordinal"], descriptor["observation_id"],
                            descriptor["sha256"],
                            authority_clock_relation="MONOTONIC_EXPIRED",
                            transport_authority_sample_utc=actual_utc,
                        )
                    if monotonic_now >= deadline_ns - CLEANUP_RESERVE_NS:
                        raise OperationalFailure(
                            "GLOBAL_DEADLINE", "GLOBAL_WALL_TIMEOUT",
                            "global deadline reached cleanup reserve before transport",
                            descriptor["ordinal"], descriptor["observation_id"],
                            descriptor["sha256"],
                            transport_authority_sample_utc=actual_utc,
                        )
                    previous_authority_sample = actual
                    if before_transport_utc is None:
                        before_transport_utc = actual_utc
                    return actual_utc

                observation_started_ns = time.monotonic_ns()
                try:
                    result = _transport_once(
                        prepared.ssh_argv, program, timeout, int(context["max_output_bytes"]),
                        global_deadline_ns=deadline_ns,
                        authority_guard=final_authority_guard,
                    )
                except OperationalFailure:
                    raise
                except TransportLifecycleError as exception:
                    raise OperationalFailure(
                        "TRANSPORT", exception.category, exception.reason,
                        descriptor["ordinal"], descriptor["observation_id"],
                        descriptor["sha256"], child_started=exception.child_started,
                        child_reaped=exception.child_reaped,
                        process_group_cleanup=exception.process_group_cleanup,
                        transport_authority_sample_utc=exception.authority_sample_utc,
                    ) from exception
                except BaseException as exception:
                    raise OperationalFailure(
                        "TRANSPORT", "TRANSPORT_EXCEPTION", _reason(exception),
                        descriptor["ordinal"], descriptor["observation_id"], descriptor["sha256"],
                    ) from exception
                if not result.child_reaped:
                    raise OperationalFailure(
                        "TRANSPORT", "PROCESS_CLEANUP_FAILURE",
                        "transport returned before child reap",
                        descriptor["ordinal"], descriptor["observation_id"],
                        descriptor["sha256"], child_started=True, child_reaped=False,
                        process_group_cleanup=result.process_group_cleanup,
                        transport_authority_sample_utc=result.authority_sample_utc,
                    )
                _remaining_seconds(deadline_ns)
                total_output += len(result.stdout) + len(result.stderr)
                if total_output > int(context["max_total_output_bytes"]):
                    raise OperationalFailure(
                        "GLOBAL_DEADLINE", "TOTAL_OUTPUT_LIMIT_EXCEEDED",
                        "total output exceeded the fixed action limit", descriptor["ordinal"],
                        descriptor["observation_id"], descriptor["sha256"],
                        child_started=True, child_reaped=result.child_reaped,
                        process_group_cleanup=result.process_group_cleanup,
                        transport_authority_sample_utc=result.authority_sample_utc,
                    )
                ordinal = descriptor["ordinal"]
                try:
                    _write_exclusive_at(prepared.directory_fd, f"s17-ro-{ordinal:03d}.stdout.bin", result.stdout)
                    _write_exclusive_at(prepared.directory_fd, f"s17-ro-{ordinal:03d}.stderr.bin", result.stderr)
                except BaseException as exception:
                    raise OperationalFailure(
                        "OUTPUT_RETENTION", "OUTPUT_WRITE_EXCEPTION", _reason(exception), ordinal,
                        descriptor["observation_id"], descriptor["sha256"],
                        child_started=True, child_reaped=result.child_reaped,
                        process_group_cleanup=result.process_group_cleanup,
                        transport_authority_sample_utc=result.authority_sample_utc,
                    ) from exception
                receipt = {
                    "schema_version": "cpu-prefetch-stage17-read-only-preflight-observation-receipt/4",
                    **_base_links(prepared), "ordinal": ordinal,
                    "observation_id": descriptor["observation_id"],
                    "rendered_program_sha256": descriptor["sha256"],
                    "ssh_argv_sha256": prepared.ssh_argv_sha256,
                    "actual_authority_sample_before_marker_utc": before_marker_utc,
                    "actual_authority_sample_before_first_transport_utc": before_transport_utc,
                    "transport_authority_sample_utc": result.authority_sample_utc,
                    "actual_started_at_utc": result.authority_sample_utc,
                    "actual_completed_at_utc": _actual_utc_now(),
                    "duration_ns": max(0, time.monotonic_ns() - observation_started_ns),
                    "returncode": result.returncode, "failure": result.failure,
                    "stdout_size_bytes": len(result.stdout), "stdout_sha256": _sha256_bytes(result.stdout),
                    "stderr_size_bytes": len(result.stderr), "stderr_sha256": _sha256_bytes(result.stderr),
                    "child_reaped": result.child_reaped,
                    "process_group_cleanup": result.process_group_cleanup,
                    "attempt": 1, "retry": 0, "stage18_authority": False,
                }
                try:
                    _validate_record(prepared, "receipt", receipt, "observation receipt")
                    receipt_hashes.append(_write_exclusive_at(
                        prepared.directory_fd, f"s17-ro-{ordinal:03d}.receipt-v4.json",
                        stage17_state_journal_v4.canonical_json_bytes(receipt) + b"\n",
                    ))
                except BaseException as exception:
                    raise OperationalFailure(
                        "RECEIPT_RETENTION", "RECEIPT_WRITE_EXCEPTION", _reason(exception), ordinal,
                        descriptor["observation_id"], descriptor["sha256"],
                        child_started=True, child_reaped=result.child_reaped,
                        process_group_cleanup=result.process_group_cleanup,
                        transport_authority_sample_utc=result.authority_sample_utc,
                    ) from exception
                if result.failure is not None or result.returncode != 0:
                    raise OperationalFailure(
                        "TRANSPORT", result.failure or "REMOTE_NONZERO_EXIT",
                        result.failure or f"remote exit {result.returncode}", ordinal,
                        descriptor["observation_id"], descriptor["sha256"],
                        child_started=True, child_reaped=result.child_reaped,
                        process_group_cleanup=result.process_group_cleanup,
                        transport_authority_sample_utc=result.authority_sample_utc,
                    )
                completed.append(descriptor["observation_id"])
                _remaining_seconds(deadline_ns)
            completion = {
                "schema_version": "cpu-prefetch-stage17-read-only-preflight-completion/4",
                **_base_links(prepared), "ssh_argv_sha256": prepared.ssh_argv_sha256,
                "completed_observation_ids": completed, "receipt_sha256s": receipt_hashes,
                "actual_authority_sample_before_marker_utc": before_marker_utc,
                "actual_authority_sample_before_first_transport_utc": before_transport_utc,
                "actual_completed_at_utc": _actual_utc_now(),
                "duration_ns": max(0, time.monotonic_ns() - action_started_ns),
                "all_children_reaped": True,
                "process_group_policy": "START_NEW_SESSION_TERMINATE_GROUP_REAP_BEFORE_EVIDENCE",
                "attempts": 6, "retries": 0, "stage18_authority": False,
            }
            _validate_record(prepared, "completion", completion, "completion record")
            _remaining_seconds(deadline_ns)
            try:
                _write_exclusive_at(
                    prepared.directory_fd, context["completion_name"],
                    stage17_state_journal_v4.canonical_json_bytes(completion) + b"\n",
                )
            except BaseException as exception:
                raise OperationalFailure(
                    "COMPLETION_RETENTION", "COMPLETION_WRITE_EXCEPTION", _reason(exception)
                ) from exception
        except BaseException as exception:
            failure = exception if isinstance(exception, OperationalFailure) else OperationalFailure(
                "UNEXPECTED_OPERATIONAL_EXCEPTION", "UNEXPECTED_OPERATIONAL_EXCEPTION",
                _reason(exception), active_descriptor["ordinal"] if active_descriptor else None,
                active_descriptor["observation_id"] if active_descriptor else None,
                active_descriptor["sha256"] if active_descriptor else None,
            )
            try:
                _write_failure(
                    prepared=prepared, failure=failure, completed=completed,
                    action_started_ns=action_started_ns, before_marker_utc=before_marker_utc,
                    before_transport_utc=before_transport_utc,
                )
            except BaseException:
                pass
            raise ActionExecutionError(f"fixed read-only preflight stopped: {failure.category}") from exception
    finally:
        if marker_created:
            try:
                os.fsync(prepared.directory_fd)
            except OSError:
                pass
        prepared.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root, latest_journal=arguments.journal,
            journal_directory=arguments.journal_directory,
        )
    except (ActionExecutionError, stage17_state_journal_v4.JournalError, OSError, ValueError) as exception:
        print(f"stage17-read-only-preflight-v5: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-read-only-preflight-v5: PASS fixed=6 retry=0 Stage18=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
