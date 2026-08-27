#!/usr/bin/env python3
"""Hermetic authority-boundary regressions for Stage 17 phase controllers.

The production CLI exposes no test switch.  This separate test module replaces
only the child transport and journal reader after real schema, exact-byte and
OpenSSH SSHSIG verification.  It creates disposable Ed25519 material in a
temporary directory and never opens a socket or contacts a stand.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock

import stage17_phase_controller_v1 as controller
from stage17_read_only_preflight_executor_v7 import TransportResult


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CheckError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, document: object) -> None:
    path.write_bytes(canonical(document))


class Fixture:
    def __init__(self, root: pathlib.Path, action: str = "Q15-R") -> None:
        self.root, self.action = root, action
        self.evidence = root / "evidence"
        self.evidence.mkdir(mode=0o700)
        self.key = root / "signer"
        generated = subprocess.run(
            ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if generated.returncode != 0:
            raise CheckError("cannot generate disposable SSHSIG key")
        public = pathlib.Path(str(self.key) + ".pub").read_text().strip()
        self.allowed = root / "allowed_signers"
        self.allowed.write_text(f"synthetic-owner {public}\n", encoding="ascii")
        self.executable = root / "fixed-worker"
        self.executable.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        self.executable.chmod(0o700)
        self.required = {
            f"S17-EXT-{index:03d}": {
                "input_id": f"S17-EXT-{index:03d}",
                "resolution_id": f"SYNTHETIC-RES-{index:03d}",
                "sha256": f"{index:x}" * 64,
            }
            for index in range(1, 4 if action == "Q15-R" else 5)
        }
        self.request = root / "request.json"
        write(self.request, {
            "schema_version": "cpu-prefetch-stage17-fixed-action-request/1",
            "request_id": f"SYNTHETIC-{action}-REQUEST", "action_id": action,
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
            "expected_prestate_sha256": "1" * 64,
            "parameters": {"synthetic_fixture": True},
            "output_artifact_names": ["synthetic-output.json"],
            "command_override": None, "argv_override": None,
            "stdin_override": None, "synthetic_test_only": False,
            "phase18_authority": False,
        })
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.authorization = root / "authorization.json"
        permissions = controller.PERMISSIONS[action]
        write(self.authorization, {
            "schema_version": "cpu-prefetch-stage17-phase-action-authorization/1",
            "authorization_id": f"SYNTHETIC-{action}-AUTHORITY",
            "action_id": action, "actor": "synthetic-owner",
            "target": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "execution_root": str(root)},
            "issued_at_utc": (now - dt.timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + dt.timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
            "predecessor_resolutions": list(self.required.values()),
            "fixed_action_definition_sha256": digest(ROOT / controller.FIXED_ACTIONS_PATH),
            "request_binding": {"path": str(self.request), "size_bytes": self.request.stat().st_size, "sha256": digest(self.request)},
            "allowed_signers_binding": {"path": str(self.allowed), "size_bytes": self.allowed.stat().st_size, "sha256": digest(self.allowed)},
            "principal": "synthetic-owner", "sshsig_namespace": "cpu-prefetch-stage17-controller-test-v1",
            "executable_bindings": [{"path": str(self.executable), "size_bytes": self.executable.stat().st_size, "sha256": digest(self.executable)}],
            "evidence_root": str(self.evidence), "expected_prestate_sha256": "1" * 64,
            "permission_matrix": permissions, "max_wall_seconds": 180,
            "one_attempt": True, "retry_allowed": False, "stop_first": True,
            "retain_partial": True, "stage18_authority": False,
        })
        self.signature = self._sign()

    def _sign(self) -> pathlib.Path:
        old = pathlib.Path(str(self.authorization) + ".sig")
        old.unlink(missing_ok=True)
        signed = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(self.key),
             "-n", "cpu-prefetch-stage17-controller-test-v1", str(self.authorization)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if signed.returncode != 0 or not old.is_file():
            raise CheckError("cannot create disposable SSHSIG")
        return old

    def resign(self, document: dict[str, object]) -> None:
        write(self.authorization, document)
        self.signature = self._sign()

    def execute(self, *, transport: TransportResult | None = None) -> int:
        calls = 0

        def fake_transport(*_: object, **__: object) -> TransportResult:
            nonlocal calls
            calls += 1
            return transport or TransportResult(
                0, b"synthetic stdout\n", b"", leader_reaped=True,
                process_group_gone=True,
                terminal_cleanup_outcome="NORMAL_LEADER_REAPED_GROUP_QUIESCENT",
            )

        capability = {"mechanism": "SYNTHETIC-TEST-ONLY-CAPABILITY"}
        validation = SimpleNamespace(
            current_state="PREFLIGHT_ACCEPTED", pilot_ready=False,
            resolved_input_ids=tuple(self.required),
        )
        with mock.patch.object(controller, "_state_gate", return_value=validation), \
             mock.patch.object(controller, "_admitted_bindings", return_value=(self.required, {})), \
             mock.patch.object(controller.process_supervisor, "verify_supervisor_capability", return_value=capability), \
             mock.patch.object(controller.transport_runtime, "_transport_once", side_effect=fake_transport):
            controller.execute_once(
                repository_root=ROOT, journal=self.root / "synthetic-journal.json",
                journal_directory=self.root, authorization_path=self.authorization,
                signature_path=self.signature,
            )
        return calls


def expect_rejected(label: str, operation: object) -> None:
    try:
        assert callable(operation)
        operation()
    except BaseException:
        print(f"stage17-phase-controller: PASS negative={label}")
        return
    raise CheckError(f"controller admitted negative fixture: {label}")


def self_test() -> tuple[int, int]:
    positive = 0
    negative = 0
    with tempfile.TemporaryDirectory(prefix="stage17-controller-") as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        if fixture.execute() != 1:
            raise CheckError("successful controller action did not invoke one transport")
        positive += 1
        expect_rejected("replay_marker", fixture.execute); negative += 1

    for label, mutation in (
        ("future_authority", lambda d: d.__setitem__("issued_at_utc", "2999-01-01T00:00:00Z")),
        ("expired_authority", lambda d: d.__setitem__("expires_at_utc", "2000-01-01T00:00:00Z")),
        ("wrong_target", lambda d: d["target"].__setitem__("stand_id", "WRONG-STAND")),
        ("wrong_predecessor", lambda d: d.__setitem__("predecessor_resolutions", d["predecessor_resolutions"][:-1])),
        ("permission_expansion", lambda d: d["permission_matrix"].__setitem__("phase18", True)),
        ("cross_version", lambda d: d.__setitem__("schema_version", "cpu-prefetch-stage17-phase-action-authorization/999")),
    ):
        with tempfile.TemporaryDirectory(prefix="stage17-controller-negative-") as temporary:
            fixture = Fixture(pathlib.Path(temporary))
            document = json.loads(fixture.authorization.read_text())
            mutation(document)
            fixture.resign(document)
            expect_rejected(label, fixture.execute)
            negative += 1

    with tempfile.TemporaryDirectory(prefix="stage17-controller-signer-") as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        fixture.allowed.write_text("synthetic-owner ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n", encoding="ascii")
        expect_rejected("wrong_signer", fixture.execute); negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17-controller-runtime-") as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        fixture.executable.write_text("#!/bin/sh\nexit 7\n", encoding="ascii")
        expect_rejected("runtime_drift", fixture.execute); negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17-controller-request-") as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        request = json.loads(fixture.request.read_text())
        request["argv_override"] = ["--forbidden"]
        write(fixture.request, request)
        expect_rejected("caller_argv", fixture.execute); negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17-controller-cleanup-") as temporary:
        fixture = Fixture(pathlib.Path(temporary))
        failed = TransportResult(
            1, b"partial", b"failed", failure="FIXED_WORKER_NONZERO",
            leader_reaped=True, process_group_gone=True,
            terminal_cleanup_outcome="SIGTERM_LEADER_REAPED_GROUP_QUIESCENT",
        )
        expect_rejected("typed_transport_failure", lambda: fixture.execute(transport=failed))
        terminal = fixture.evidence / "stage17-q15_r-terminal-v1.json"
        if not terminal.is_file() or json.loads(terminal.read_text())["kind"] != "FAILURE":
            raise CheckError("typed failure was not retained after cleanup")
        positive += 1; negative += 1
    return positive, negative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-phase-controller: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-phase-controller: PASS positive={positive} negative={negative} production_cli_test_mode=false stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
