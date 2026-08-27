#!/usr/bin/env python3
"""Production authority boundary for fixed Q15/Q16/Stage-17-pilot actions.

The production CLI has no fake backend and accepts no command, argv, stdin, or
retry option.  It verifies an SSHSIG authorization, current journal state,
actual executable/request bytes, and system UTC before a durable one-shot
marker.  Synthetic tests monkeypatch subprocess internals from a separate test
module; that facility is not selectable by this CLI.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import subprocess
import sys
import time
from typing import Any

from jsonschema import Draft202012Validator

import stage17_process_group_supervisor_v2 as process_supervisor
import stage17_read_only_preflight_executor_v7 as transport_runtime
import stage17_state_journal_v6 as journal_runtime


FIXED_ACTIONS_PATH = pathlib.PurePosixPath("config/stage17/stage17-fixed-phase-actions-v1.json")
FIXED_ACTIONS_SCHEMA = pathlib.PurePosixPath("config/schemas/stage17-fixed-phase-actions-v1.schema.json")
AUTHORIZATION_SCHEMA = pathlib.PurePosixPath("config/schemas/stage17-phase-action-authorization-v1.schema.json")
REQUEST_SCHEMA = pathlib.PurePosixPath("config/schemas/stage17-fixed-action-request-v1.schema.json")
RESULT_SCHEMA = pathlib.PurePosixPath("config/schemas/stage17-phase-action-result-v1.schema.json")
EVIDENCE_SCHEMA = pathlib.PurePosixPath("config/schemas/stage17-phase-action-evidence-v1.schema.json")
MAX_OUTPUT_BYTES = 16 * 1024 * 1024
PERMISSIONS = {
    "Q15-R": {"read_only_observation": True, "privileged_controls": False,
               "calibration": False, "pilot_execution": False,
               "measurement": False, "phase18": False},
    "Q15-W": {"read_only_observation": False, "privileged_controls": True,
               "calibration": False, "pilot_execution": False,
               "measurement": False, "phase18": False},
    "Q16a": {"read_only_observation": False, "privileged_controls": False,
              "calibration": True, "pilot_execution": False,
              "measurement": True, "phase18": False},
    "Q16b": {"read_only_observation": False, "privileged_controls": False,
              "calibration": True, "pilot_execution": False,
              "measurement": True, "phase18": False},
    "Q16c": {"read_only_observation": False, "privileged_controls": False,
              "calibration": True, "pilot_execution": False,
              "measurement": True, "phase18": False},
    "STAGE17-BLINDED-PILOT": {
        "read_only_observation": False, "privileged_controls": False,
        "calibration": False, "pilot_execution": True,
        "measurement": True, "phase18": False,
    },
}


class ControllerError(RuntimeError):
    pass


def _canonical(document: Any) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ControllerError("authorization time is not UTC")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise ControllerError("authorization time is malformed") from exception


def _load_json(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ControllerError(f"not a nonsymlink regular file: {path}")
        payload = path.read_bytes()
        document = json.loads(payload)
    except (OSError, json.JSONDecodeError) as exception:
        raise ControllerError(f"cannot load JSON {path}: {exception}") from exception
    if not isinstance(document, dict):
        raise ControllerError(f"JSON root is not an object: {path}")
    return document, payload


def _validator(root: pathlib.Path, relative: pathlib.PurePosixPath) -> Draft202012Validator:
    schema, _ = _load_json(root / relative)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _validate(validator: Draft202012Validator, document: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(document), key=lambda item: tuple(item.path))
    if errors:
        path = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise ControllerError(f"{label} schema error at {path}: {errors[0].message}")


def _verify_binding(path: pathlib.Path, binding: dict[str, Any], label: str) -> bytes:
    if str(path) != binding.get("path"):
        raise ControllerError(f"{label} locator mismatch")
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ControllerError(f"{label} is not a nonsymlink regular file")
        payload = path.read_bytes()
    except OSError as exception:
        raise ControllerError(f"cannot read {label}: {exception}") from exception
    if len(payload) != binding.get("size_bytes") or _sha(payload) != binding.get("sha256"):
        raise ControllerError(f"{label} byte identity mismatch")
    return payload


def _verify_signature(
    authorization_bytes: bytes, signature: pathlib.Path,
    allowed_signers: pathlib.Path, principal: str, namespace: str,
) -> None:
    result = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "verify", "-f", str(allowed_signers),
         "-I", principal, "-n", namespace, "-s", str(signature)],
        input=authorization_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=10, check=False,
    )
    if result.returncode != 0:
        raise ControllerError("SSHSIG authorization verification failed")


def _open_root(path: pathlib.Path, repository_root: pathlib.Path) -> int:
    if not path.is_absolute() or path == pathlib.Path("/") or path == repository_root or repository_root in path.parents:
        raise ControllerError("evidence root is unsafe")
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise ControllerError("evidence root must be a nonsymlink directory")
    if metadata.st_uid != os.geteuid() or metadata.st_mode & 0o022:
        raise ControllerError("evidence root ownership/permissions are unsafe")
    descriptor = os.open(
        path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    opened = os.fstat(descriptor)
    if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
        os.close(descriptor)
        raise ControllerError("evidence root changed during open")
    if opened.st_uid != os.geteuid() or opened.st_mode & 0o022:
        os.close(descriptor)
        raise ControllerError("opened evidence root ownership/permissions are unsafe")
    return descriptor


def _write_exclusive(directory_fd: int, name: str, payload: bytes) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(descriptor, view)
            if count <= 0:
                raise ControllerError("short evidence write")
            view = view[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.fsync(directory_fd)
    return _sha(payload)


def _action_definition(root: pathlib.Path, action_id: str) -> tuple[dict[str, Any], str]:
    document, payload = _load_json(root / FIXED_ACTIONS_PATH)
    _validate(_validator(root, FIXED_ACTIONS_SCHEMA), document, "fixed actions")
    matches = [item for item in document["actions"] if item["action_id"] == action_id]
    if len(matches) != 1:
        raise ControllerError("fixed action is absent or duplicated")
    return matches[0], _sha(payload)


def _state_gate(
    *, root: pathlib.Path, journal: pathlib.Path, journal_directory: pathlib.Path,
    action: dict[str, Any], as_of_utc: str,
) -> journal_runtime.JournalValidation:
    validation = journal_runtime.validate_journal(
        repository_root=root, latest_journal=journal,
        journal_directory=journal_directory, as_of_utc=as_of_utc,
    )
    if validation.current_state != action["required_state"]:
        raise ControllerError("journal state does not permit the fixed action")
    required = tuple(action["required_resolution_ids"])
    if tuple(item for item in validation.resolved_input_ids if item in required) != required:
        raise ControllerError("fixed action predecessor resolutions are incomplete")
    if action["action_id"] == "STAGE17-BLINDED-PILOT" and not validation.pilot_ready:
        raise ControllerError("pilot authorization is not currently ready")
    return validation


def _admitted_bindings(
    root: pathlib.Path, latest_journal: pathlib.Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    latest_path = latest_journal if latest_journal.is_absolute() else root / latest_journal
    latest, _ = _load_json(latest_path)
    by_input: dict[str, dict[str, Any]] = {}
    documents: dict[str, dict[str, Any]] = {}
    for reference in latest.get("resolution_records", []):
        relative = reference.get("path")
        if not isinstance(relative, str):
            raise ControllerError("journal resolution reference path is absent")
        path = root / relative
        document, payload = _load_json(path)
        digest = _sha(payload)
        if digest != reference.get("sha256"):
            raise ControllerError("journal resolution reference hash drifted")
        input_id = document.get("input_id")
        if not isinstance(input_id, str) or input_id in by_input:
            raise ControllerError("journal resolution input is absent or duplicated")
        by_input[input_id] = {
            "input_id": input_id, "resolution_id": document["resolution_id"],
            "sha256": digest,
        }
        documents[input_id] = document
    return by_input, documents


def execute_once(
    *, repository_root: pathlib.Path, journal: pathlib.Path,
    journal_directory: pathlib.Path, authorization_path: pathlib.Path,
    signature_path: pathlib.Path,
) -> None:
    root = repository_root.resolve()
    authorization, authorization_bytes = _load_json(authorization_path)
    _validate(_validator(root, AUTHORIZATION_SCHEMA), authorization, "phase authorization")
    if authorization.get("stage18_authority") is not False:
        raise ControllerError("Stage 18 authority is forbidden")
    action, fixed_actions_sha = _action_definition(root, authorization["action_id"])
    if authorization["fixed_action_definition_sha256"] != fixed_actions_sha:
        raise ControllerError("fixed-action definition binding drifted")
    if authorization["permission_matrix"] != PERMISSIONS[authorization["action_id"]]:
        raise ControllerError("phase authorization permission matrix drifted")
    allowed_signers = pathlib.Path(authorization["allowed_signers_binding"]["path"])
    _verify_binding(allowed_signers, authorization["allowed_signers_binding"], "allowed signers")
    _verify_signature(
        authorization_bytes, signature_path, allowed_signers,
        authorization["principal"], authorization["sshsig_namespace"],
    )
    request_path = pathlib.Path(authorization["request_binding"]["path"])
    request_bytes = _verify_binding(request_path, authorization["request_binding"], "fixed request")
    request = json.loads(request_bytes)
    _validate(_validator(root, REQUEST_SCHEMA), request, "fixed action request")
    if request["synthetic_test_only"] is not False:
        raise ControllerError("synthetic request is forbidden in production")
    if (request["action_id"], request["stand_id"], request["expected_prestate_sha256"]) != (authorization["action_id"], authorization["target"]["stand_id"], authorization["expected_prestate_sha256"]):
        raise ControllerError("fixed request target/prestate mismatch")
    if any(request[name] is not None for name in ("command_override", "argv_override", "stdin_override")):
        raise ControllerError("caller command/argv/stdin is forbidden")
    admitted, resolution_documents = _admitted_bindings(root, journal)
    required_bindings = [admitted[item] for item in action["required_resolution_ids"]]
    if authorization["predecessor_resolutions"] != required_bindings:
        raise ControllerError("phase authorization predecessor binding drifted")
    if authorization["action_id"] == "STAGE17-BLINDED-PILOT":
        ext010 = resolution_documents.get("S17-EXT-010")
        if not isinstance(ext010, dict) or not isinstance(ext010.get("authorization"), dict):
            raise ControllerError("pilot authorization is not admitted as S17-EXT-010")
        admitted_authorization = root / ext010["authorization"]["evidence_path"]
        if (
            admitted_authorization.resolve() != authorization_path.resolve()
            or _sha(authorization_bytes) != _sha(admitted_authorization.read_bytes())
            or ext010["authorization"].get("authorization_id")
            != authorization.get("authorization_id")
        ):
            raise ControllerError("executed pilot authorization differs from admitted S17-EXT-010")
    if len(authorization["executable_bindings"]) != 1:
        raise ControllerError("fixed action requires exactly one executable")
    executable_binding = authorization["executable_bindings"][0]
    executable = pathlib.Path(executable_binding["path"])
    executable_bytes = _verify_binding(executable, executable_binding, "fixed action executable")
    if executable.stat().st_mode & 0o111 == 0:
        raise ControllerError("fixed action executable is not executable")
    actual_before_marker = _now()
    actual_time = _parse_utc(actual_before_marker)
    issued, expires = _parse_utc(authorization["issued_at_utc"]), _parse_utc(authorization["expires_at_utc"])
    if not issued <= actual_time < expires:
        raise ControllerError("authorization is future or expired before marker")
    _state_gate(
        root=root, journal=journal, journal_directory=journal_directory,
        action=action, as_of_utc=actual_before_marker,
    )
    evidence_root = pathlib.Path(authorization["evidence_root"])
    directory_fd = _open_root(evidence_root, root)
    action_token = authorization["action_id"].lower().replace("-", "_")
    marker_name = f"stage17-{action_token}-attempt-v1.json"
    output_name = f"stage17-{action_token}-stdout.bin"
    error_name = f"stage17-{action_token}-stderr.bin"
    terminal_name = f"stage17-{action_token}-terminal-v1.json"
    marker_created = False
    started_ns = time.monotonic_ns()
    deadline_ns = started_ns + int(authorization["max_wall_seconds"]) * 1_000_000_000
    try:
        if any(os.path.exists(evidence_root / name) for name in (marker_name, output_name, error_name, terminal_name)):
            raise ControllerError("one-shot action was already attempted")
        capability = process_supervisor.verify_supervisor_capability()
        marker = {
            "schema_version": "cpu-prefetch-stage17-phase-action-evidence/1",
            "evidence_id": authorization["authorization_id"] + ":attempt",
            "kind": "ATTEMPT", "action_id": authorization["action_id"],
            "authorization_id": authorization["authorization_id"],
            "authorization_sha256": _sha(authorization_bytes),
            "request_sha256": _sha(request_bytes), "fixed_action_definition_sha256": fixed_actions_sha,
            "runtime_sha256": _sha(executable_bytes), "attempt": 1, "retries": 0,
            "actual_started_at_utc": actual_before_marker, "actual_completed_at_utc": actual_before_marker,
            "duration_ns": 0, "returncode": None, "stdout_size_bytes": 0,
            "stdout_sha256": _sha(b""), "stderr_size_bytes": 0, "stderr_sha256": _sha(b""),
            "leader_reaped": False, "process_group_gone": True,
            "terminal_cleanup_outcome": capability["mechanism"], "failure_category": None,
            "partial_retained": True, "quarantine": False, "phase18_authority": False,
        }
        _validate(_validator(root, EVIDENCE_SCHEMA), marker, "phase attempt")
        _write_exclusive(directory_fd, marker_name, _canonical(marker))
        marker_created = True
        substitutions = {"{EXECUTABLE}": str(executable), "{REQUEST}": str(request_path), "{EVIDENCE_ROOT}": str(evidence_root)}
        argv: list[str] = []
        for source in action["fixed_argv_template"]:
            value = source
            for placeholder, replacement in substitutions.items():
                value = value.replace(placeholder, replacement)
            if "{" in value or "}" in value or "\x00" in value:
                raise ControllerError("fixed argv rendering failed")
            argv.append(value)

        previous = actual_time
        def authority_guard() -> str:
            sample_text = _now()
            sample = _parse_utc(sample_text)
            if sample < previous or not issued <= sample < expires or time.monotonic_ns() >= deadline_ns:
                raise ControllerError("authorization/monotonic guard failed before process start")
            return sample_text

        result = transport_runtime._transport_once(
            tuple(argv), b"", float(authorization["max_wall_seconds"]), MAX_OUTPUT_BYTES,
            global_deadline_ns=deadline_ns, authority_guard=authority_guard,
        )
        _write_exclusive(directory_fd, output_name, result.stdout)
        _write_exclusive(directory_fd, error_name, result.stderr)
        failure = result.failure or result.cleanup_failure
        if result.returncode != 0 and failure is None:
            failure = "FIXED_WORKER_NONZERO"
        kind = "COMPLETION" if failure is None else "FAILURE"
        quarantine = bool(action["requires_restoration"] and failure is not None)
        terminal = {
            "schema_version": "cpu-prefetch-stage17-phase-action-evidence/1",
            "evidence_id": authorization["authorization_id"] + ":terminal", "kind": kind,
            "action_id": authorization["action_id"], "authorization_id": authorization["authorization_id"],
            "authorization_sha256": _sha(authorization_bytes), "request_sha256": _sha(request_bytes),
            "fixed_action_definition_sha256": fixed_actions_sha, "runtime_sha256": _sha(executable_bytes),
            "attempt": 1, "retries": 0, "actual_started_at_utc": actual_before_marker,
            "actual_completed_at_utc": _now(), "duration_ns": max(0, time.monotonic_ns() - started_ns),
            "returncode": result.returncode, "stdout_size_bytes": len(result.stdout), "stdout_sha256": _sha(result.stdout),
            "stderr_size_bytes": len(result.stderr), "stderr_sha256": _sha(result.stderr),
            "leader_reaped": result.leader_reaped, "process_group_gone": result.process_group_gone,
            "terminal_cleanup_outcome": result.terminal_cleanup_outcome,
            "failure_category": failure, "partial_retained": True,
            "quarantine": quarantine, "phase18_authority": False,
        }
        _validate(_validator(root, EVIDENCE_SCHEMA), terminal, "phase terminal evidence")
        _write_exclusive(directory_fd, terminal_name, _canonical(terminal))
        if failure is not None:
            raise ControllerError(f"fixed action failed: {failure}; quarantine={quarantine}")
    except BaseException as exception:
        if marker_created and not os.path.exists(evidence_root / terminal_name):
            leader_reaped = bool(getattr(exception, "leader_reaped", False))
            process_group_gone = bool(
                getattr(
                    exception, "process_group_gone",
                    not getattr(exception, "child_started", False),
                )
            )
            cleanup_outcome = str(
                getattr(
                    exception, "terminal_cleanup_outcome",
                    "NOT_STARTED_OR_TRANSPORT_RETAINED_OWN_CLEANUP",
                )
            )
            fallback = {
                "schema_version": "cpu-prefetch-stage17-phase-action-evidence/1",
                "evidence_id": authorization["authorization_id"] + ":terminal", "kind": "FAILURE",
                "action_id": authorization["action_id"], "authorization_id": authorization["authorization_id"],
                "authorization_sha256": _sha(authorization_bytes), "request_sha256": _sha(request_bytes),
                "fixed_action_definition_sha256": fixed_actions_sha, "runtime_sha256": _sha(executable_bytes),
                "attempt": 1, "retries": 0, "actual_started_at_utc": actual_before_marker,
                "actual_completed_at_utc": _now(), "duration_ns": max(0, time.monotonic_ns() - started_ns),
                "returncode": None, "stdout_size_bytes": 0, "stdout_sha256": _sha(b""),
                "stderr_size_bytes": 0, "stderr_sha256": _sha(b""),
                "leader_reaped": leader_reaped,
                "process_group_gone": process_group_gone,
                "terminal_cleanup_outcome": cleanup_outcome,
                "failure_category": type(exception).__name__, "partial_retained": True,
                "quarantine": bool(action["requires_restoration"]), "phase18_authority": False,
            }
            try:
                _validate(_validator(root, EVIDENCE_SCHEMA), fallback, "phase fallback")
                _write_exclusive(directory_fd, terminal_name, _canonical(fallback))
            except BaseException as retention_error:
                raise ControllerError(f"action failed and failure retention failed: primary={exception}; retention={retention_error}") from retention_error
        raise
    finally:
        os.close(directory_fd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--authorization", type=pathlib.Path, required=True)
    parser.add_argument("--signature", type=pathlib.Path, required=True)
    arguments = parser.parse_args()
    try:
        execute_once(
            repository_root=arguments.repository_root, journal=arguments.journal,
            journal_directory=arguments.journal_directory,
            authorization_path=arguments.authorization, signature_path=arguments.signature,
        )
    except BaseException as exception:
        print(f"stage17-phase-controller: FAIL: {exception}", file=sys.stderr)
        return 1
    print("stage17-phase-controller: PASS action=COMPLETED authority=STAGE17_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
