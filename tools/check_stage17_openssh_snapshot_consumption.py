#!/usr/bin/env python3
"""Characterize and verify Stage 17 OpenSSH snapshot consumption locally.

Every test uses a local ``ProxyCommand`` only. No socket, DNS lookup, stand,
operational key, authorization, or evidence record is used.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import threading
from types import SimpleNamespace
from unittest import mock

import stage17_openssh_parent_snapshot_v1 as broker
import stage17_read_only_preflight_executor_v4 as executor
import stage17_semantic_verifier_v5 as predecessor_verifier
import stage17_semantic_verifier_v6 as verifier


SSH = pathlib.Path("/usr/bin/ssh")


class ConsumptionCheckError(RuntimeError):
    """The local OpenSSH characterization did not prove its contract."""


ROOT = pathlib.Path(__file__).resolve().parents[1]
OBSERVATIONS = (
    "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
    "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
    "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
    "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
    "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
    "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(path: pathlib.Path) -> dict[str, object]:
    return {"locator": str(path), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _repository_binding(relative: str) -> dict[str, object]:
    path = ROOT / relative
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}


def _generate_key(path: pathlib.Path) -> None:
    result = subprocess.run(
        ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(path)],
        check=False, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=5,
    )
    if result.returncode != 0:
        raise ConsumptionCheckError("disposable Ed25519 key generation failed")


def _capability_stub() -> dict[str, object]:
    base = {
        "mechanism": broker.MECHANISM, "result": "PASS", "ssh_version": "SYNTHETIC",
        "ssh_sha256": "1" * 64, "sshd_sha256": "2" * 64,
        "ssh_keygen_sha256": "3" * 64, "procfs_visible_parent_pid": 1,
        "descriptor_inheritance_used": False, "source_mutation_before_consumption": True,
        "strict_host_key_verification": True, "public_key_authentication": True,
        "local_proxy_pipe_only": True, "network_used": False,
        "private_bytes_recorded": False,
    }
    base["report_sha256"] = hashlib.sha256(
        json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return base


class RuntimeFixture:
    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        self.root.chmod(0o700)
        self.identity = root / "identity"
        _generate_key(self.identity)
        self.known_hosts = root / "known_hosts"
        self.known_hosts.write_bytes(
            b"synthetic.invalid " + self.identity.with_suffix(".pub").read_bytes()
        )
        self.known_hosts.chmod(0o600)
        self.evidence = root / "evidence"
        self.evidence.mkdir(mode=0o700)
        metadata = self.evidence.stat()
        self.context: dict[str, object] = {
            "attempt_id": "SYNTHETIC-ATTEMPT-NO-AUTHORITY",
            "authorization_id": "SYNTHETIC-AUTH-NO-AUTHORITY",
            "authorization_sha256": "4" * 64,
            "authorization": {
                "issued_at_utc": "2030-01-01T00:00:00Z",
                "expires_at_utc": "2030-01-01T00:30:00Z",
            },
            "resolution_id": "SYNTHETIC-RESOLUTION-NO-AUTHORITY",
            "resolution_sha256": "5" * 64,
            "transition_id": "SYNTHETIC-TRANSITION-NO-AUTHORITY",
            "transition_sha256": "6" * 64,
            "evidence_root": str(self.evidence),
            "evidence_root_identity": {
                "device": metadata.st_dev, "inode": metadata.st_ino,
                "uid": metadata.st_uid, "mode": metadata.st_mode & 0o7777,
            },
            "attempt_marker_name": "stage17-read-only-preflight-attempt-v4.json",
            "failure_name": "stage17-read-only-preflight-failure-v4.json",
            "completion_name": "stage17-read-only-preflight-completion-v3.json",
            "ssh_target": "synthetic@synthetic.invalid",
            "known_hosts_binding": _binding(self.known_hosts),
            "transport_identity_binding": _binding(self.identity),
            "action_plan_sha256": "7" * 64,
            "runtime_implementation_hashes": {
                name: f"{index:x}" * 64
                for index, name in enumerate(verifier.IMPLEMENTATION_PATHS, start=1)
            },
            "observation_ids": list(OBSERVATIONS),
            "fixed_ssh_argv_template": json.loads(
                (ROOT / verifier.ACTION_PLAN_PATH).read_text()
            )["transport"]["fixed_ssh_argv_template"],
            "timeout_seconds": 30, "max_output_bytes": 1048576,
            "max_total_output_bytes": 6291456, "max_wall_seconds": 180,
            "record_schema_bindings": {
                "attempt": _repository_binding(verifier.ATTEMPT_SCHEMA_PATH),
                "receipt": _repository_binding(verifier.RECEIPT_SCHEMA_PATH),
                "failure": _repository_binding(verifier.FAILURE_SCHEMA_PATH),
                "completion": _repository_binding(verifier.COMPLETION_SCHEMA_PATH),
            },
            "pre_marker_file_bindings": [],
            "collector_context": {
                "archive_locator": "/synthetic/archive", "sidecar_locator": "/synthetic/sidecar",
                "bundle_root_locator": "/synthetic/bundle", "capture_id": "SYNTHETIC-CAPTURE",
                "captured_at_utc": "2030-01-01T00:01:00Z",
                "archive_size_bytes": 1, "archive_sha256": "8" * 64,
                "sidecar_size_bytes": 1, "sidecar_sha256": "9" * 64,
                "manifest_sha256": "a" * 64, "internal_file_count": 1,
            },
        }

    def validation(self) -> SimpleNamespace:
        return SimpleNamespace(action_ready=True, action_context=self.context)


def _sealed_memfd(name: str, payload: bytes) -> int:
    descriptor = os.memfd_create(
        name, os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING
    )
    try:
        os.write(descriptor, payload)
        os.fchmod(descriptor, 0o600)
        fcntl.fcntl(
            descriptor,
            fcntl.F_ADD_SEALS,
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL,
        )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def characterize_self_procfd_closefrom() -> dict[str, object]:
    """Prove that OpenSSH does not retain the caller's fd >= 3 identity."""

    if not SSH.is_file():
        raise ConsumptionCheckError("/usr/bin/ssh is unavailable")
    descriptors = [
        _sealed_memfd("stage17-old-known-hosts", b"synthetic-known-hosts\n"),
        _sealed_memfd("stage17-old-identity", b"synthetic-identity\n"),
    ]
    try:
        original = {
            str(descriptor): os.readlink(f"/proc/self/fd/{descriptor}")
            for descriptor in descriptors
        }
        with tempfile.TemporaryDirectory(
            prefix="stage17-openssh-closefrom-characterization-"
        ) as temporary:
            root = pathlib.Path(temporary)
            output = root / "observed.json"
            helper = root / "observe-openssh-parent-fds.py"
            helper.write_text(
                "#!/usr/bin/python3\n"
                "import json,os,pathlib,sys\n"
                "result={}\n"
                "for value in sys.argv[2:]:\n"
                " path=f'/proc/{os.getppid()}/fd/{value}'\n"
                " try: result[value]=os.readlink(path)\n"
                " except OSError as error: "
                "result[value]=f'{type(error).__name__}:{error.errno}'\n"
                "pathlib.Path(sys.argv[1]).write_text(json.dumps(result))\n",
                encoding="utf-8",
            )
            helper.chmod(0o755)
            proxy_command = " ".join(
                [str(helper), str(output), *(str(item) for item in descriptors)]
            )
            completed = subprocess.run(
                [
                    str(SSH),
                    "-F",
                    "/dev/null",
                    "-T",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ProxyCommand={proxy_command}",
                    "--",
                    "synthetic@synthetic.invalid",
                    "/usr/bin/true",
                ],
                check=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=tuple(descriptors),
                timeout=5,
            )
            if not output.is_file():
                raise ConsumptionCheckError(
                    "real OpenSSH did not execute the local fd observer"
                )
            observed = json.loads(output.read_text(encoding="utf-8"))
        if any(
            observed.get(str(descriptor)) == original[str(descriptor)]
            for descriptor in descriptors
        ):
            raise ConsumptionCheckError(
                "OpenSSH unexpectedly retained an inherited sealed memfd identity"
            )
        version = subprocess.run(
            [str(SSH), "-V"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        version_text = (version.stderr or version.stdout).decode(
            "utf-8", errors="replace"
        ).strip()
        return {
            "ssh_version": version_text,
            "ssh_returncode": completed.returncode,
            "original_targets": original,
            "post_hygiene_targets": observed,
            "inherited_identity_retained": False,
            "network_used": False,
        }
    finally:
        for descriptor in descriptors:
            os.close(descriptor)


def _expect_failure(label: str, action, exceptions=(Exception,)) -> None:
    try:
        action()
    except exceptions:
        return
    raise ConsumptionCheckError(f"negative regression passed unexpectedly: {label}")


def snapshot_regressions() -> tuple[int, int]:
    """Test immutable source consumption and procfs/seal failure boundaries."""

    positive = 0
    negative = 0
    procfs = broker.discover_procfs_identity()
    with mock.patch.object(broker.os, "getpid", return_value=procfs.visible_pid + 1000000):
        if broker.discover_procfs_identity().visible_pid != procfs.visible_pid:
            raise ConsumptionCheckError("procfs-visible PID was derived from os.getpid")
    positive += 1
    with tempfile.TemporaryDirectory(prefix="stage17a5-procfs-unavailable-") as temporary:
        _expect_failure(
            "procfs unavailable",
            lambda: broker.discover_procfs_identity(pathlib.Path(temporary)),
            (broker.SnapshotError,),
        )
        negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17a5-source-mutation-") as temporary:
        root = pathlib.Path(temporary)
        root.chmod(0o700)
        replacement_key = root / "replacement-key"
        _generate_key(replacement_key)
        for role, atomic in (
            ("KNOWN_HOSTS", True), ("KNOWN_HOSTS", False),
            ("TRANSPORT_IDENTITY", True), ("TRANSPORT_IDENTITY", False),
        ):
            source = root / f"{role.lower()}-{'atomic' if atomic else 'inplace'}"
            if role == "TRANSPORT_IDENTITY":
                _generate_key(source)
            else:
                source.write_bytes(b"synthetic.invalid ssh-ed25519 SYNTHETIC\n")
                source.chmod(0o600)
            binding = _binding(source)
            snapshot = broker.pin_bound_input(binding, role)
            try:
                if atomic:
                    replacement = root / f"replacement-{role.lower()}"
                    if role == "TRANSPORT_IDENTITY":
                        shutil.copyfile(replacement_key, replacement)
                        replacement.chmod(0o600)
                    else:
                        replacement.write_bytes(b"ATOMIC-REPLACEMENT\n")
                    os.replace(replacement, source)
                else:
                    source.write_bytes(b"IN-PLACE-MUTATION\n")
                    source.chmod(0o600)
                broker.verify_snapshot(snapshot)
                if snapshot.metadata["consumed_sha256"] != binding["sha256"]:
                    raise ConsumptionCheckError("snapshot digest changed with owner source")
                if role == "TRANSPORT_IDENTITY":
                    broker.validate_identity_parseability(snapshot)
            finally:
                snapshot.close()
            positive += 1
        premature = root / "premature"
        premature.write_bytes(b"premature-close\n")
        snapshot = broker.pin_bound_input(_binding(premature), "KNOWN_HOSTS")
        snapshot.close()
        _expect_failure("premature snapshot close", lambda: broker.verify_snapshot(snapshot))
        negative += 1
        invalid = root / "invalid-key"
        invalid.write_bytes(b"not-an-openssh-private-key\n")
        invalid.chmod(0o600)
        snapshot = broker.pin_bound_input(_binding(invalid), "TRANSPORT_IDENTITY")
        try:
            _expect_failure(
                "invalid identity parseability",
                lambda: broker.validate_identity_parseability(snapshot),
                (broker.SnapshotError,),
            )
            negative += 1
        finally:
            snapshot.close()
        _expect_failure(
            "bound size mismatch",
            lambda: broker.pin_bound_input(
                {**_binding(invalid), "size_bytes": invalid.stat().st_size + 1},
                "TRANSPORT_IDENTITY",
            ),
            (broker.SnapshotError,),
        )
        negative += 1
        _expect_failure(
            "bound SHA-256 mismatch",
            lambda: broker.pin_bound_input(
                {**_binding(invalid), "sha256": "0" * 64}, "TRANSPORT_IDENTITY"
            ),
            (broker.SnapshotError,),
        )
        negative += 1
    descriptor = os.memfd_create(
        "stage17-unsealed-negative", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING
    )
    try:
        payload = b"unsealed\n"
        os.write(descriptor, payload)
        os.fchmod(descriptor, 0o600)
        procfs = broker.discover_procfs_identity()
        snapshot = broker.ParentSnapshot(
            role="KNOWN_HOSTS", descriptor=descriptor,
            locator=f"/proc/{procfs.visible_pid}/fd/{descriptor}",
            metadata={"snapshot_size_bytes": len(payload),
                "consumed_sha256": hashlib.sha256(payload).hexdigest()},
        )
        _expect_failure("missing memfd seals", lambda: broker.verify_snapshot(snapshot), (broker.SnapshotError,))
        negative += 1
    finally:
        os.close(descriptor)
    return positive, negative


class _Clock:
    def __init__(self, *values: str):
        self.values = list(values)
        self.last = values[-1]

    def __call__(self) -> str:
        if self.values:
            self.last = self.values.pop(0)
        return self.last


def _execute_fixture(
    fixture: RuntimeFixture, clock: _Clock, transport_calls: list[tuple[str, ...]],
    *, capability=None,
) -> None:
    capability_action = capability or (lambda: _capability_stub())

    def transport(argv, stdin, timeout, output_limit):
        del stdin, timeout, output_limit
        transport_calls.append(argv)
        return executor.TransportResult(0, b"{}\n", b"")

    with (
        mock.patch.object(executor, "_actual_utc_now", side_effect=clock),
        mock.patch.object(executor, "_prospective_validation", return_value=fixture.validation()),
        mock.patch.object(broker, "verify_local_openssh_parent_procfd_capability", side_effect=capability_action),
        mock.patch.object(executor, "_transport_once", side_effect=transport),
    ):
        executor.execute_once(
            repository_root=ROOT,
            latest_journal=ROOT / "config/stage17/journal/stage17-state-journal-000000.json",
            journal_directory=ROOT / "config/stage17/journal",
        )


def executor_regressions() -> tuple[int, int]:
    """Exercise v4 time, capability, replay, and version gates without transport."""

    positive = 0
    negative = 0
    cases = (
        ("future", ("2029-12-31T23:59:59.000000Z", "2029-12-31T23:59:59.000000Z")),
        ("expired", ("2030-01-01T00:31:00.000000Z", "2030-01-01T00:31:00.000000Z")),
        ("pre-marker rollback", ("2030-01-01T00:10:00.000000Z", "2030-01-01T00:09:59.000000Z")),
    )
    for label, values in cases:
        with tempfile.TemporaryDirectory(prefix=f"stage17a5-{label}-") as temporary:
            fixture = RuntimeFixture(pathlib.Path(temporary))
            calls: list[tuple[str, ...]] = []
            _expect_failure(label, lambda: _execute_fixture(fixture, _Clock(*values), calls))
            if calls or (fixture.evidence / "stage17-read-only-preflight-attempt-v4.json").exists():
                raise ConsumptionCheckError(f"{label} crossed pre-marker boundary")
            negative += 1
    for label, values, category in (
        ("post-marker expiry", (
            "2030-01-01T00:10:00.000000Z", "2030-01-01T00:29:59.000000Z",
            "2030-01-01T00:30:01.000000Z"), "AUTHORITY_EXPIRED_BEFORE_FIRST_TRANSPORT"),
        ("post-marker rollback", (
            "2030-01-01T00:10:00.000000Z", "2030-01-01T00:11:00.000000Z",
            "2030-01-01T00:10:59.000000Z"), "AUTHORITY_ROLLBACK_BEFORE_FIRST_TRANSPORT"),
    ):
        with tempfile.TemporaryDirectory(prefix=f"stage17a5-{label}-") as temporary:
            fixture = RuntimeFixture(pathlib.Path(temporary))
            calls = []
            _expect_failure(label, lambda: _execute_fixture(fixture, _Clock(*values), calls))
            failure_path = fixture.evidence / "stage17-read-only-preflight-failure-v4.json"
            marker_path = fixture.evidence / "stage17-read-only-preflight-attempt-v4.json"
            if calls or not marker_path.is_file() or not failure_path.is_file():
                raise ConsumptionCheckError(f"{label} did not retain typed post-marker failure")
            if json.loads(failure_path.read_text())["reason_category"] != category:
                raise ConsumptionCheckError(f"{label} failure category drifted")
            negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17a5-capability-failure-") as temporary:
        fixture = RuntimeFixture(pathlib.Path(temporary))
        calls = []

        def fail_capability():
            raise broker.SnapshotError("synthetic procfs denial")

        _expect_failure(
            "capability failure before marker",
            lambda: _execute_fixture(
                fixture, _Clock("2030-01-01T00:10:00.000000Z"), calls,
                capability=fail_capability,
            ),
        )
        if calls or any(fixture.evidence.iterdir()):
            raise ConsumptionCheckError("capability failure consumed one-shot state")
        negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17a5-schema-drift-") as temporary:
        fixture = RuntimeFixture(pathlib.Path(temporary))
        fixture.context["record_schema_bindings"]["attempt"]["sha256"] = "0" * 64  # type: ignore[index]
        calls = []
        _expect_failure(
            "record schema drift before marker",
            lambda: _execute_fixture(fixture, _Clock("2030-01-01T00:10:00.000000Z"), calls),
        )
        if calls or any(fixture.evidence.iterdir()):
            raise ConsumptionCheckError("schema drift crossed marker boundary")
        negative += 1
    for version in range(1, 5):
        with tempfile.TemporaryDirectory(prefix=f"stage17a5-cross-marker-v{version}-") as temporary:
            fixture = RuntimeFixture(pathlib.Path(temporary))
            (fixture.evidence / f"stage17-read-only-preflight-attempt-v{version}.json").write_bytes(b"{}\n")
            calls = []
            _expect_failure(
                f"cross-version marker v{version}",
                lambda: _execute_fixture(fixture, _Clock("2030-01-01T00:10:00.000000Z"), calls),
            )
            if calls:
                raise ConsumptionCheckError("cross-version marker allowed transport")
            negative += 1
    with tempfile.TemporaryDirectory(prefix="stage17a5-concurrent-") as temporary:
        fixture = RuntimeFixture(pathlib.Path(temporary))
        calls: list[tuple[str, ...]] = []
        results: list[str] = []
        barrier = threading.Barrier(2)
        original_write = executor._write_exclusive_at

        def synchronized_write(directory_fd, name, payload, **kwargs):
            if name == "stage17-read-only-preflight-attempt-v4.json":
                barrier.wait(timeout=10)
            return original_write(directory_fd, name, payload, **kwargs)

        def worker():
            try:
                executor.execute_once(
                    repository_root=ROOT,
                    latest_journal=ROOT / "config/stage17/journal/stage17-state-journal-000000.json",
                    journal_directory=ROOT / "config/stage17/journal",
                )
                results.append("PASS")
            except Exception as exception:
                results.append(f"BLOCKED:{type(exception).__name__}:{exception}")

        def transport(argv, stdin, timeout, output_limit):
            del stdin, timeout, output_limit
            calls.append(argv)
            return executor.TransportResult(0, b"{}\n", b"")

        with (
            mock.patch.object(executor, "_write_exclusive_at", side_effect=synchronized_write),
            mock.patch.object(executor, "_actual_utc_now", return_value="2030-01-01T00:10:00.000000Z"),
            mock.patch.object(executor, "_prospective_validation", return_value=fixture.validation()),
            mock.patch.object(broker, "verify_local_openssh_parent_procfd_capability", side_effect=lambda: _capability_stub()),
            mock.patch.object(executor, "_transport_once", side_effect=transport),
        ):
            threads = [threading.Thread(target=worker) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
        if len(results) != 2 or results.count("PASS") != 1 or len(calls) != 6:
            raise ConsumptionCheckError(
                "concurrent attempts did not yield one transport family: "
                f"results={sorted(results)} transport_calls={len(calls)}"
            )
        before = len(calls)
        _expect_failure(
            "replay after durable marker",
            lambda: _execute_fixture(fixture, _Clock("2030-01-01T00:10:00.000000Z"), calls),
        )
        if len(calls) != before:
            raise ConsumptionCheckError("replay opened a transport")
        positive += 1
        negative += 1
    v6_envelope = {"schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/6"}
    _expect_failure(
        "executor-v3 verifier rejects v6 envelope",
        lambda: predecessor_verifier.verify_s17_ext_001_semantics_v5(
            root=ROOT, resolution={}, repository_documents=[(ROOT / "README.md", v6_envelope)],
            receipt_documents=[], policy={}, policy_path=ROOT / "README.md", policy_sha256="0" * 64,
            policy_entry={}, graph_sha256="0" * 64, catalog_sha256="0" * 64,
            genesis_sha256="0" * 64, catalog={}, resolution_schema_sha256="0" * 64,
        ),
        (Exception,),
    )
    negative += 1
    v5_envelope = {"schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/5"}
    _expect_failure(
        "executor-v4 verifier rejects predecessor envelope",
        lambda: verifier.verify_s17_ext_001_semantics_v6(
            root=ROOT, resolution={}, repository_documents=[(ROOT / "README.md", v5_envelope)],
            receipt_documents=[], policy={}, policy_path=ROOT / "README.md", policy_sha256="0" * 64,
            policy_entry={}, graph_sha256="0" * 64, catalog_sha256="0" * 64,
            genesis_sha256="0" * 64, catalog={}, resolution_schema_sha256="0" * 64,
        ),
        (Exception,),
    )
    negative += 1
    return positive, negative


def self_test() -> tuple[int, int, str]:
    old = characterize_self_procfd_closefrom()
    real = broker.verify_local_openssh_parent_procfd_capability()
    if old["inherited_identity_retained"] is not False or real["result"] != "PASS":
        raise ConsumptionCheckError("real OpenSSH characterization/acceptance did not pass")
    snapshot_positive, snapshot_negative = snapshot_regressions()
    runtime_positive, runtime_negative = executor_regressions()
    return 2 + snapshot_positive + runtime_positive, snapshot_negative + runtime_negative, str(real["ssh_version"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--characterize-old-mechanism", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if arguments.characterize_old_mechanism == arguments.self_test:
        parser.error("select exactly one of --characterize-old-mechanism or --self-test")
    try:
        if arguments.self_test:
            positive, negative, version = self_test()
            print(
                "stage17-openssh-consumption-check: PASS "
                f"positive={positive} negative={negative} real_openssh=true "
                f"network=false ssh={version}"
            )
            return 0
        result = characterize_self_procfd_closefrom()
    except (ConsumptionCheckError, OSError, subprocess.SubprocessError) as error:
        print(f"stage17-openssh-consumption-check: FAIL: {error}")
        return 1
    print(
        "stage17-openssh-consumption-check: PASS "
        f"old_self_procfd_retained={str(result['inherited_identity_retained']).lower()} "
        f"network={str(result['network_used']).lower()} "
        f"ssh={result['ssh_version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
