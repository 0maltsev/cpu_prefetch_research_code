#!/usr/bin/env python3
"""Characterize and verify the Stage 17 authority/child lifecycle boundary.

The suite is repository-local. It uses only synthetic temporary inputs and
local processes; it opens no socket, DNS lookup, stand, or external transport.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import signal
import subprocess
import tempfile
import threading
import time
from unittest import mock

import stage17_openssh_parent_snapshot_v1 as snapshot_broker
import stage17_read_only_preflight_executor_v4 as predecessor_executor
import stage17_read_only_preflight_executor_v5 as executor
import stage17_semantic_verifier_v6 as predecessor_verifier
import stage17_semantic_verifier_v7 as verifier
from check_stage17_openssh_snapshot_consumption import (
    RuntimeFixture,
    _binding,
    _capability_stub,
    _repository_binding,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LifecycleCheckError(RuntimeError):
    """The focused characterization or successor regression failed."""


def characterize_v4_authority_gap() -> dict[str, object]:
    """Show that v4 opens transport after expiry during snapshot recheck."""

    with tempfile.TemporaryDirectory(prefix="stage17a6-v4-authority-gap-") as temporary:
        fixture = RuntimeFixture(pathlib.Path(temporary))
        fixture.context["authorization"]["expires_at_utc"] = "2030-01-01T00:00:01Z"
        current = ["2030-01-01T00:00:00.900000Z"]
        transport_times: list[str] = []
        verify_calls = 0

        def clock() -> str:
            return current[0]

        def verify_snapshot(_snapshot: object) -> None:
            nonlocal verify_calls
            verify_calls += 1
            if verify_calls >= 5:
                current[0] = "2030-01-01T00:00:01.215974Z"

        def transport(_argv: object, _stdin: bytes, _timeout: float, _limit: int):
            transport_times.append(current[0])
            return predecessor_executor.TransportResult(0, b"{}\n", b"")

        validation = fixture.validation()
        with (
            mock.patch.object(predecessor_executor, "_actual_utc_now", side_effect=clock),
            mock.patch.object(
                predecessor_executor, "_prospective_validation", return_value=validation
            ),
            mock.patch.object(
                predecessor_executor.snapshot_broker,
                "verify_local_openssh_parent_procfd_capability",
                side_effect=lambda: _capability_stub(),
            ),
            mock.patch.object(
                predecessor_executor.snapshot_broker,
                "verify_snapshot",
                side_effect=verify_snapshot,
            ),
            mock.patch.object(
                predecessor_executor, "_transport_once", side_effect=transport
            ),
        ):
            predecessor_executor.execute_once(
                repository_root=ROOT,
                latest_journal=ROOT
                / "config/stage17/journal/stage17-state-journal-000000.json",
                journal_directory=ROOT / "config/stage17/journal",
            )
        if not transport_times or transport_times[0] != "2030-01-01T00:00:01.215974Z":
            raise LifecycleCheckError("v4 authority-gap characterization did not reproduce")
        return {
            "transport_calls_after_expiry": len(transport_times),
            "first_transport_actual_utc": transport_times[0],
        }


def characterize_v4_unreaped_child() -> dict[str, object]:
    """Show that v4 leaks a child when first post-Popen setup raises."""

    original_popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []

    def open_child(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child

    observed_exception = False
    try:
        with (
            mock.patch.object(predecessor_executor.subprocess, "Popen", side_effect=open_child),
            mock.patch.object(
                predecessor_executor.os,
                "set_blocking",
                side_effect=OSError("synthetic first set_blocking failure"),
            ),
        ):
            predecessor_executor._transport_once(
                (
                    "/usr/bin/python3",
                    "-c",
                    "import time; time.sleep(30)",
                ),
                b"",
                2.0,
                1024,
            )
    except OSError:
        observed_exception = True
    if not observed_exception or len(children) != 1:
        raise LifecycleCheckError("v4 child-leak characterization did not reach setup failure")
    child = children[0]
    alive_after_exception = child.poll() is None
    if alive_after_exception:
        child.kill()
    child.wait(timeout=5)
    if not alive_after_exception:
        raise LifecycleCheckError("v4 unexpectedly reaped the child during characterization")
    return {"alive_after_setup_exception": True, "characterization_cleanup_reaped": True}


def _v5_fixture(root: pathlib.Path) -> RuntimeFixture:
    fixture = RuntimeFixture(root)
    fixture.context.update(
        {
            "attempt_marker_name": "stage17-read-only-preflight-attempt-v5.json",
            "failure_name": "stage17-read-only-preflight-failure-v5.json",
            "completion_name": "stage17-read-only-preflight-completion-v4.json",
            "action_plan_sha256": _binding(
                ROOT / verifier.ACTION_PLAN_PATH
            )["sha256"],
            "runtime_implementation_hashes": {
                name: f"{index:x}"[-1] * 64
                for index, name in enumerate(verifier.IMPLEMENTATION_PATHS, start=1)
            },
            "fixed_ssh_argv_template": json.loads(
                (ROOT / verifier.ACTION_PLAN_PATH).read_text(encoding="utf-8")
            )["transport"]["fixed_ssh_argv_template"],
            "record_schema_bindings": {
                "attempt": _repository_binding(verifier.ATTEMPT_SCHEMA_PATH),
                "receipt": _repository_binding(verifier.RECEIPT_SCHEMA_PATH),
                "failure": _repository_binding(verifier.FAILURE_SCHEMA_PATH),
                "completion": _repository_binding(verifier.COMPLETION_SCHEMA_PATH),
            },
        }
    )
    return fixture


def _expect_failure(label: str, action, expected: type[BaseException] = Exception) -> BaseException:
    try:
        action()
    except expected as exception:
        return exception
    raise LifecycleCheckError(f"negative regression passed unexpectedly: {label}")


def _execute_fixture(
    fixture: RuntimeFixture,
    *,
    clock,
    verify_snapshot=None,
    transport_wrapper=None,
    monotonic_ns=None,
) -> None:
    validation = fixture.validation()
    original_transport = executor._transport_once

    def selected_transport(*args: object, **kwargs: object):
        if transport_wrapper is None:
            return original_transport(*args, **kwargs)
        return transport_wrapper(original_transport, args, kwargs)

    patches = [
        mock.patch.object(executor, "_actual_utc_now", side_effect=clock),
        mock.patch.object(executor, "_prospective_validation", return_value=validation),
        mock.patch.object(
            snapshot_broker,
            "verify_local_openssh_parent_procfd_capability",
            side_effect=lambda: _capability_stub(),
        ),
        mock.patch.object(executor, "_transport_once", side_effect=selected_transport),
    ]
    if verify_snapshot is not None:
        patches.append(
            mock.patch.object(snapshot_broker, "verify_snapshot", side_effect=verify_snapshot)
        )
    if monotonic_ns is not None:
        patches.append(mock.patch.object(executor.time, "monotonic_ns", side_effect=monotonic_ns))
    with patches[0], patches[1], patches[2], patches[3]:
        if len(patches) == 4:
            executor.execute_once(
                repository_root=ROOT,
                latest_journal=ROOT
                / "config/stage17/journal/stage17-state-journal-000000.json",
                journal_directory=ROOT / "config/stage17/journal",
            )
        elif len(patches) == 5:
            with patches[4]:
                executor.execute_once(
                    repository_root=ROOT,
                    latest_journal=ROOT
                    / "config/stage17/journal/stage17-state-journal-000000.json",
                    journal_directory=ROOT / "config/stage17/journal",
                )
        else:
            with patches[4], patches[5]:
                executor.execute_once(
                    repository_root=ROOT,
                    latest_journal=ROOT
                    / "config/stage17/journal/stage17-state-journal-000000.json",
                    journal_directory=ROOT / "config/stage17/journal",
                )


class _MutableClock:
    def __init__(self, value: str) -> None:
        self.value = value

    def __call__(self) -> str:
        return self.value


def authority_regressions() -> tuple[int, list[str]]:
    """Prove that every final guard rejects stale system/monotonic authority."""

    labels: list[str] = []
    with tempfile.TemporaryDirectory(prefix="stage17a6-delayed-snapshots-") as temporary:
        fixture = _v5_fixture(pathlib.Path(temporary))
        fixture.context["authorization"]["expires_at_utc"] = "2030-01-01T00:00:01Z"
        clock = _MutableClock("2030-01-01T00:00:00.900000Z")
        verify_count = 0
        popen_calls = 0

        def delayed_verify(_snapshot: object) -> None:
            nonlocal verify_count
            verify_count += 1
            if verify_count >= 5:
                clock.value = "2030-01-01T00:00:01.215974Z"

        def count_popen(original, args, kwargs):
            nonlocal popen_calls
            original_popen = subprocess.Popen

            def opened(*popen_args: object, **popen_kwargs: object):
                nonlocal popen_calls
                popen_calls += 1
                return original_popen(*popen_args, **popen_kwargs)

            with mock.patch.object(executor.subprocess, "Popen", side_effect=opened):
                return original(*args, **kwargs)

        _expect_failure(
            "expiry during both snapshot checks",
            lambda: _execute_fixture(
                fixture, clock=clock, verify_snapshot=delayed_verify,
                transport_wrapper=count_popen,
            ),
            executor.ActionExecutionError,
        )
        failure = json.loads(
            (fixture.evidence / "stage17-read-only-preflight-failure-v5.json").read_text()
        )
        if (
            popen_calls != 0
            or failure["reason_category"] != "AUTHORITY_EXPIRED_BEFORE_TRANSPORT"
            or failure["child_started"] is not False
            or failure["child_reaped"] is not True
        ):
            raise LifecycleCheckError("expiry during snapshot checks crossed Popen boundary")
        labels.append("expiry_after_snapshot_recheck")
    for label, prospective, before_marker, guard, marker_expected, category in (
        (
            "expiry immediately before guard",
            "2030-01-01T00:00:00.500000Z",
            "2030-01-01T00:00:00.700000Z",
            "2030-01-01T00:00:01.000000Z",
            True,
            "AUTHORITY_EXPIRED_BEFORE_TRANSPORT",
        ),
        (
            "future authority",
            "2029-12-31T23:59:59.000000Z",
            "2029-12-31T23:59:59.000000Z",
            "2029-12-31T23:59:59.000000Z",
            False,
            None,
        ),
        (
            "wall clock rollback",
            "2030-01-01T00:00:00.500000Z",
            "2030-01-01T00:00:00.700000Z",
            "2030-01-01T00:00:00.600000Z",
            True,
            "AUTHORITY_ROLLBACK_BEFORE_TRANSPORT",
        ),
    ):
        with tempfile.TemporaryDirectory(prefix="stage17a6-authority-case-") as temporary:
            fixture = _v5_fixture(pathlib.Path(temporary))
            fixture.context["authorization"]["expires_at_utc"] = "2030-01-01T00:00:01Z"
            values = iter((prospective, before_marker, guard))
            popen_calls = 0

            def clock() -> str:
                return next(values, guard)

            def count_popen(original, args, kwargs):
                nonlocal popen_calls
                original_popen = subprocess.Popen

                def opened(*popen_args: object, **popen_kwargs: object):
                    nonlocal popen_calls
                    popen_calls += 1
                    return original_popen(*popen_args, **popen_kwargs)

                with mock.patch.object(executor.subprocess, "Popen", side_effect=opened):
                    return original(*args, **kwargs)

            _expect_failure(
                label,
                lambda: _execute_fixture(
                    fixture, clock=clock, transport_wrapper=count_popen
                ),
                executor.ActionExecutionError,
            )
            marker = fixture.evidence / "stage17-read-only-preflight-attempt-v5.json"
            failure_path = fixture.evidence / "stage17-read-only-preflight-failure-v5.json"
            if popen_calls or marker.exists() is not marker_expected:
                raise LifecycleCheckError(f"{label} crossed its authority boundary")
            if category is not None:
                if not failure_path.is_file() or json.loads(failure_path.read_text())["reason_category"] != category:
                    raise LifecycleCheckError(f"{label} typed failure drifted")
            labels.append(label.replace(" ", "_"))
    with tempfile.TemporaryDirectory(prefix="stage17a6-monotonic-authority-") as temporary:
        fixture = _v5_fixture(pathlib.Path(temporary))
        fixture.context["authorization"]["expires_at_utc"] = "2030-01-01T00:00:01Z"
        monotonic_values = iter(
            (1_000_000_000, 1_050_000_000, 1_060_000_000, 1_200_000_000)
        )

        def monotonic_ns() -> int:
            return next(monotonic_values, 1_250_000_000)

        _expect_failure(
            "monotonic authority expiry",
            lambda: _execute_fixture(
                fixture,
                clock=lambda: "2030-01-01T00:00:00.900000Z",
                monotonic_ns=monotonic_ns,
            ),
            executor.ActionExecutionError,
        )
        failure = json.loads(
            (fixture.evidence / "stage17-read-only-preflight-failure-v5.json").read_text()
        )
        if failure["reason_category"] != "AUTHORITY_MONOTONIC_EXPIRED_BEFORE_TRANSPORT":
            raise LifecycleCheckError("monotonic authority deadline was not enforced")
        labels.append("monotonic_authority_expiry")
    return len(labels), labels


class _SelectorFault:
    def __init__(self, mode: str, factory) -> None:
        self.mode = mode
        self.inner = factory()

    def register(self, *args: object, **kwargs: object):
        if self.mode == "register":
            raise OSError("synthetic selector registration failure")
        return self.inner.register(*args, **kwargs)

    def unregister(self, *args: object, **kwargs: object):
        return self.inner.unregister(*args, **kwargs)

    def select(self, *args: object, **kwargs: object):
        if self.mode == "select":
            raise OSError("synthetic selector select failure")
        return self.inner.select(*args, **kwargs)

    def get_map(self):
        return self.inner.get_map()

    def close(self) -> None:
        self.inner.close()


def _group_is_gone(group_id: int) -> bool:
    try:
        os.killpg(group_id, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def _transport_fault_case(label: str) -> tuple[bool, str]:
    """Run one real local child fault and require group termination plus reap."""

    original_popen = subprocess.Popen
    original_selector = executor.selectors.DefaultSelector
    original_write = os.write
    original_read = os.read
    original_killpg = os.killpg
    original_wait = subprocess.Popen.wait
    children: list[subprocess.Popen[bytes]] = []
    child_opened = False

    def opened(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
        nonlocal child_opened
        if label == "popen":
            raise OSError("synthetic Popen failure")
        child = original_popen(*args, **kwargs)
        children.append(child)
        child_opened = True
        return child

    def write_fault(descriptor: int, payload: object) -> int:
        if child_opened and label == "epipe":
            raise BrokenPipeError("synthetic EPIPE")
        return original_write(descriptor, payload)

    def read_fault(descriptor: int, size: int) -> bytes:
        if child_opened and label == "read":
            raise OSError("synthetic pipe read failure")
        return original_read(descriptor, size)

    wait_count = 0
    killpg_count = 0

    def wait_fault(self, timeout=None):
        nonlocal wait_count
        if label == "cleanup_primary" and wait_count == 0:
            wait_count += 1
            raise OSError("synthetic wait cleanup failure")
        if label == "repeated_wait" and wait_count < 2:
            wait_count += 1
            raise subprocess.TimeoutExpired(self.args, timeout)
        return original_wait(self, timeout=timeout)

    def killpg_fault(group: int, requested_signal: int) -> None:
        nonlocal killpg_count
        killpg_count += 1
        if label == "cleanup_primary" and killpg_count == 1:
            raise OSError("synthetic SIGTERM cleanup failure")
        original_killpg(group, requested_signal)

    program = "import time; time.sleep(30)"
    stdin = b"payload"
    timeout = 0.1
    if label == "read":
        program = "import sys,time; sys.stdout.write('x'); sys.stdout.flush(); time.sleep(30)"
        stdin = b""
    if label == "normal":
        program = (
            "import sys; data=sys.stdin.buffer.read(); "
            "sys.stdout.buffer.write(data); sys.stdout.buffer.flush()"
        )
        timeout = 2.0
    if label == "process_group":
        program = (
            "import subprocess,time; "
            "subprocess.Popen(['/usr/bin/python3','-c','import time; time.sleep(30)']); "
            "time.sleep(30)"
        )
    patches = [
        mock.patch.object(executor.subprocess, "Popen", side_effect=opened),
        mock.patch.object(executor.os, "write", side_effect=write_fault),
        mock.patch.object(executor.os, "read", side_effect=read_fault),
        mock.patch.object(executor.subprocess.Popen, "wait", new=wait_fault),
    ]
    if label in {"set_blocking", "process_group", "cleanup_primary"}:
        patches.append(
            mock.patch.object(
                executor.os, "set_blocking",
                side_effect=OSError("synthetic first set_blocking failure"),
            )
        )
    if label == "cleanup_primary":
        patches.append(mock.patch.object(executor.os, "killpg", side_effect=killpg_fault))
    if label in {"register", "select"}:
        patches.append(
            mock.patch.object(
                executor.selectors, "DefaultSelector",
                side_effect=lambda: _SelectorFault(label, original_selector),
            )
        )
    deadline_ns = time.monotonic_ns() + 3_000_000_000
    result: executor.TransportResult | None = None
    exception: BaseException | None = None
    started = time.monotonic()
    with patches[0], patches[1], patches[2], patches[3]:
        if len(patches) == 4:
            try:
                result = executor._transport_once(
                    ("/usr/bin/python3", "-c", program), stdin, timeout, 4096,
                    global_deadline_ns=deadline_ns,
                    authority_guard=lambda: "2030-01-01T00:00:00.500000Z",
                )
            except BaseException as caught:
                exception = caught
        elif len(patches) == 5:
            with patches[4]:
                try:
                    result = executor._transport_once(
                        ("/usr/bin/python3", "-c", program), stdin, timeout, 4096,
                        global_deadline_ns=deadline_ns,
                        authority_guard=lambda: "2030-01-01T00:00:00.500000Z",
                    )
                except BaseException as caught:
                    exception = caught
        else:
            with patches[4], patches[5]:
                try:
                    result = executor._transport_once(
                        ("/usr/bin/python3", "-c", program), stdin, timeout, 4096,
                        global_deadline_ns=deadline_ns,
                        authority_guard=lambda: "2030-01-01T00:00:00.500000Z",
                    )
                except BaseException as caught:
                    exception = caught
    elapsed = time.monotonic() - started
    if label == "normal":
        if exception is not None or result is None or result.stdout != stdin:
            raise LifecycleCheckError("normal transport did not round trip and reap")
    elif label in {"timeout", "repeated_wait"}:
        if exception is not None or result is None or result.failure != "TIMEOUT":
            raise LifecycleCheckError(f"{label} did not return typed timeout result")
    elif not isinstance(exception, executor.TransportLifecycleError):
        raise LifecycleCheckError(f"{label} did not produce a lifecycle error")
    if label == "cleanup_primary" and (
        not isinstance(exception, executor.TransportLifecycleError)
        or exception.category != "TRANSPORT_RUNTIME_EXCEPTION"
        or "cleanup=SIGTERM:OSError" not in exception.reason
        or "WAIT_AFTER_SIGTERM:OSError" not in exception.reason
    ):
        raise LifecycleCheckError("cleanup exception hid or replaced the primary failure")
    if any(child.poll() is None for child in children):
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=5)
        raise LifecycleCheckError(f"{label} returned with a live child")
    if any(not _group_is_gone(child.pid) for child in children):
        raise LifecycleCheckError(f"{label} returned with a live process group")
    if elapsed >= 3.0:
        raise LifecycleCheckError(f"{label} cleanup exceeded the global deadline")
    cleanup = (
        result.process_group_cleanup
        if result is not None
        else getattr(exception, "process_group_cleanup", "NOT_STARTED")
    )
    return bool(children), cleanup


def lifecycle_regressions() -> tuple[int, int, list[str]]:
    labels: list[str] = []
    positive = 0
    negative = 0
    for label in (
        "normal", "popen", "set_blocking", "register", "select", "epipe",
        "read", "timeout", "repeated_wait", "process_group", "cleanup_primary",
    ):
        child_started, cleanup = _transport_fault_case(label)
        if label == "normal":
            positive += 1
        else:
            negative += 1
        if label != "popen" and not child_started:
            raise LifecycleCheckError(f"{label} did not start its local child")
        if label != "popen" and cleanup == "NOT_STARTED":
            raise LifecycleCheckError(f"{label} did not report process cleanup")
        labels.append(label)
    return positive, negative, labels


def actual_openssh_acceptance_cases() -> tuple[int, dict[str, str]]:
    """Run actual OpenSSH once per source-mutation class, without a socket."""

    inplace = snapshot_broker.verify_local_openssh_parent_procfd_capability()
    original_write = pathlib.Path.write_bytes
    mutation = b"MUTATED-SOURCE-MUST-NOT-BE-CONSUMED\n"

    def atomic_write(path: pathlib.Path, payload: bytes) -> int:
        if payload == mutation:
            replacement = path.with_name(path.name + ".atomic-replacement")
            count = original_write(replacement, payload)
            os.replace(replacement, path)
            return count
        return original_write(path, payload)

    with mock.patch.object(pathlib.Path, "write_bytes", new=atomic_write):
        atomic = snapshot_broker.verify_local_openssh_parent_procfd_capability()
    for label, report in (("in_place", inplace), ("atomic_replacement", atomic)):
        if (
            report.get("result") != "PASS"
            or report.get("network_used") is not False
            or report.get("strict_host_key_verification") is not True
            or report.get("public_key_authentication") is not True
        ):
            raise LifecycleCheckError(f"actual OpenSSH {label} acceptance failed")
    return 2, {
        "in_place": "KNOWN_HOSTS_AND_TRANSPORT_IDENTITY",
        "atomic_replacement": "KNOWN_HOSTS_AND_TRANSPORT_IDENTITY",
    }


def outer_failure_and_order_regressions() -> tuple[int, list[str]]:
    """Require typed evidence only after process cleanup and before snapshots close."""

    labels: list[str] = []
    for label in ("popen", "set_blocking"):
        with tempfile.TemporaryDirectory(prefix=f"stage17a6-outer-{label}-") as temporary:
            fixture = _v5_fixture(pathlib.Path(temporary))
            children: list[subprocess.Popen[bytes]] = []
            original_popen = subprocess.Popen
            original_close = executor.PreparedAction.close
            close_order_verified = False

            def transport_wrapper(original, args, kwargs):
                del args

                def opened(*popen_args: object, **popen_kwargs: object):
                    if label == "popen":
                        raise OSError("synthetic Popen failure")
                    child = original_popen(*popen_args, **popen_kwargs)
                    children.append(child)
                    return child

                local_argv = (
                    "/usr/bin/python3", "-c", "import time; time.sleep(30)"
                )
                with mock.patch.object(executor.subprocess, "Popen", side_effect=opened):
                    if label == "set_blocking":
                        with mock.patch.object(
                            executor.os, "set_blocking",
                            side_effect=OSError("synthetic set_blocking failure"),
                        ):
                            return original(
                                local_argv, b"", 0.2, 1024, **kwargs
                            )
                    return original(local_argv, b"", 0.2, 1024, **kwargs)

            def ordered_close(prepared) -> None:
                nonlocal close_order_verified
                failure_path = fixture.evidence / "stage17-read-only-preflight-failure-v5.json"
                if not failure_path.is_file() or any(
                    child.poll() is None for child in children
                ):
                    raise LifecycleCheckError(
                        "snapshots closed before typed failure or child reap"
                    )
                close_order_verified = True
                original_close(prepared)

            with mock.patch.object(executor.PreparedAction, "close", new=ordered_close):
                _expect_failure(
                    f"outer {label}",
                    lambda: _execute_fixture(
                        fixture,
                        clock=lambda: "2030-01-01T00:10:00.000000Z",
                        transport_wrapper=transport_wrapper,
                    ),
                    executor.ActionExecutionError,
                )
            failure = json.loads(
                (fixture.evidence / "stage17-read-only-preflight-failure-v5.json").read_text()
            )
            if (
                not close_order_verified
                or failure["child_reaped"] is not True
                or failure["child_started"] is not (label == "set_blocking")
                or any(child.poll() is None for child in children)
            ):
                raise LifecycleCheckError(f"outer {label} cleanup/evidence order drifted")
            labels.append(f"typed_{label}_failure_after_cleanup")
    return len(labels), labels


def replay_and_concurrency_regressions() -> tuple[int, int, list[str]]:
    labels: list[str] = []
    negative = 0
    positive = 0
    for version in range(1, 6):
        with tempfile.TemporaryDirectory(prefix=f"stage17a6-marker-v{version}-") as temporary:
            fixture = _v5_fixture(pathlib.Path(temporary))
            (fixture.evidence / f"stage17-read-only-preflight-attempt-v{version}.json").write_bytes(
                b"{}\n"
            )
            calls = 0

            def transport_wrapper(_original, _args, _kwargs):
                nonlocal calls
                calls += 1
                raise LifecycleCheckError("transport must not run for predecessor marker")

            _expect_failure(
                f"cross-version marker v{version}",
                lambda: _execute_fixture(
                    fixture, clock=lambda: "2030-01-01T00:10:00.000000Z",
                    transport_wrapper=transport_wrapper,
                ),
            )
            if calls:
                raise LifecycleCheckError("cross-version marker opened transport")
            negative += 1
            labels.append(f"marker_v{version}_blocks")
    with tempfile.TemporaryDirectory(prefix="stage17a6-concurrent-") as temporary:
        fixture = _v5_fixture(pathlib.Path(temporary))
        validation = fixture.validation()
        original_write = executor._write_exclusive_at
        barrier = threading.Barrier(2)
        transport_calls = 0
        results: list[str] = []

        def synchronized_write(directory_fd, name, payload, **kwargs):
            if name == "stage17-read-only-preflight-attempt-v5.json":
                barrier.wait(timeout=10)
            return original_write(directory_fd, name, payload, **kwargs)

        def fake_transport(_argv, _stdin, _timeout, _limit, **kwargs):
            nonlocal transport_calls
            sample = kwargs["authority_guard"]()
            transport_calls += 1
            return executor.TransportResult(
                0, b"{}\n", b"", authority_sample_utc=sample,
                child_reaped=True, process_group_cleanup="NORMAL_EXIT_REAPED",
            )

        def worker() -> None:
            try:
                executor.execute_once(
                    repository_root=ROOT,
                    latest_journal=ROOT
                    / "config/stage17/journal/stage17-state-journal-000000.json",
                    journal_directory=ROOT / "config/stage17/journal",
                )
                results.append("PASS")
            except Exception as exception:
                results.append(f"BLOCKED:{type(exception).__name__}")

        with (
            mock.patch.object(executor, "_write_exclusive_at", side_effect=synchronized_write),
            mock.patch.object(
                executor, "_actual_utc_now", return_value="2030-01-01T00:10:00.000000Z"
            ),
            mock.patch.object(executor, "_prospective_validation", return_value=validation),
            mock.patch.object(
                snapshot_broker,
                "verify_local_openssh_parent_procfd_capability",
                side_effect=lambda: _capability_stub(),
            ),
            mock.patch.object(executor, "_transport_once", side_effect=fake_transport),
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
        if (
            len(results) != 2
            or results.count("PASS") != 1
            or transport_calls != 6
        ):
            raise LifecycleCheckError(
                f"concurrent one-shot drifted: results={results} calls={transport_calls}"
            )
        positive += 1
        negative += 1
        labels.append("concurrent_one_marker_one_transport_family")
    return positive, negative, labels


def version_regressions() -> tuple[int, list[str]]:
    v7_envelope = {
        "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/7"
    }
    _expect_failure(
        "v4 production verifier rejects v7",
        lambda: predecessor_verifier.verify_s17_ext_001_semantics_v6(
            root=ROOT, resolution={},
            repository_documents=[(ROOT / "README.md", v7_envelope)],
            receipt_documents=[], policy={}, policy_path=ROOT / "README.md",
            policy_sha256="0" * 64, policy_entry={}, graph_sha256="0" * 64,
            catalog_sha256="0" * 64, genesis_sha256="0" * 64, catalog={},
            resolution_schema_sha256="0" * 64,
        ),
    )
    v6_envelope = {
        "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/6"
    }
    _expect_failure(
        "v5 production verifier rejects v6",
        lambda: verifier.verify_s17_ext_001_semantics_v7(
            root=ROOT, resolution={},
            repository_documents=[(ROOT / "README.md", v6_envelope)],
            receipt_documents=[], policy={}, policy_path=ROOT / "README.md",
            policy_sha256="0" * 64, policy_entry={}, graph_sha256="0" * 64,
            catalog_sha256="0" * 64, genesis_sha256="0" * 64, catalog={},
            resolution_schema_sha256="0" * 64,
        ),
    )
    return 2, ["executor_v4_rejects_v7", "executor_v5_rejects_v6"]


def self_test() -> tuple[int, int, dict[str, str], list[str]]:
    characterize_v4_authority_gap()
    characterize_v4_unreaped_child()
    positive = 2
    negative = 0
    labels = ["v4_authority_gap_characterized", "v4_child_leak_characterized"]
    authority_negative, authority_labels = authority_regressions()
    negative += authority_negative
    labels.extend(authority_labels)
    lifecycle_positive, lifecycle_negative, lifecycle_labels = lifecycle_regressions()
    positive += lifecycle_positive
    negative += lifecycle_negative
    labels.extend(lifecycle_labels)
    outer_negative, outer_labels = outer_failure_and_order_regressions()
    negative += outer_negative
    labels.extend(outer_labels)
    replay_positive, replay_negative, replay_labels = replay_and_concurrency_regressions()
    positive += replay_positive
    negative += replay_negative
    labels.extend(replay_labels)
    version_negative, version_labels = version_regressions()
    negative += version_negative
    labels.extend(version_labels)
    openssh_positive, mutation_classes = actual_openssh_acceptance_cases()
    positive += openssh_positive
    labels.extend(
        ["actual_openssh_in_place", "actual_openssh_atomic_replacement"]
    )
    return positive, negative, mutation_classes, labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characterize-v4", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.characterize_v4 == arguments.self_test:
        parser.error("select exactly one of --characterize-v4 or --self-test")
    try:
        if arguments.self_test:
            positive, negative, mutations, labels = self_test()
            print(
                "stage17-authority-child-lifecycle-check: PASS "
                f"positive={positive} negative={negative} "
                f"actual_openssh_in_place={mutations['in_place']} "
                f"actual_openssh_atomic={mutations['atomic_replacement']} "
                f"cases={','.join(labels)} network=false"
            )
            return 0
        authority = characterize_v4_authority_gap()
        child = characterize_v4_unreaped_child()
    except (LifecycleCheckError, OSError, subprocess.SubprocessError) as error:
        print(f"stage17-authority-child-lifecycle-check: FAIL: {error}")
        return 1
    print(
        "stage17-authority-child-lifecycle-check: PASS "
        f"v4_transport_after_expiry={authority['transport_calls_after_expiry']} "
        f"v4_child_alive_after_setup_exception={str(child['alive_after_setup_exception']).lower()} "
        "network=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
