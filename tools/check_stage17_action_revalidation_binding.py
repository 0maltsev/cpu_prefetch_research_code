#!/usr/bin/env python3
"""D-123 regression for action-time terminal schema binding.

The check builds one temporary operational journal through the public CLI and
verifies that the current S17-EXT-001 action-readiness context selects the
policy-v14 terminal record schemas.  It does not create a marker and does not
open SSH transport.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any

from jsonschema import Draft202012Validator

import author_stage17_action_revalidation_blocker_v1 as action_blocker
import author_stage17_post_marker_blocker_v1 as post_blocker
import author_stage17_pre_marker_blocker_v1 as pre_blocker


POSITIVE_CASES = 3
NEGATIVE_CASES = 4
SHA = "a" * 64


class CheckError(RuntimeError):
    pass


def run(command: list[str], *, cwd: pathlib.Path | None = None,
        expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != expected:
        raise CheckError(
            f"command returned {completed.returncode}, expected {expected}: "
            f"{' '.join(command)}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        )
    return completed


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: pathlib.Path, document: object) -> None:
    path.write_bytes(canonical(document))


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: pathlib.Path) -> dict[str, object]:
    return {
        "locator": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def exact_second(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")


def synthetic_v8_marker(root: pathlib.Path) -> dict[str, object]:
    runtime_names = json.loads(
        (root / "config/schemas/stage17-read-only-preflight-attempt-v8.schema.json")
        .read_text(encoding="utf-8")
    )["properties"]["runtime_implementation_hashes"]["propertyNames"]["enum"]
    snapshot = {
        "source_size_bytes": 1,
        "consumed_sha256": SHA,
        "snapshot_size_bytes": 1,
        "snapshot_mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
        "verified_seals": [
            "F_SEAL_WRITE",
            "F_SEAL_GROW",
            "F_SEAL_SHRINK",
            "F_SEAL_SEAL",
        ],
        "procfs_visible_parent_pid": 1,
        "procfs_process_directory_device": 1,
        "procfs_process_directory_inode": 1,
        "procfs_process_directory_uid": 1,
        "credential_fd_inherited_by_child": False,
        "source_path_reused_after_marker": False,
        "private_bytes_recorded": False,
    }
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/8",
        "attempt_id": "SYNTHETIC-D121-ATTEMPT",
        "authorization_id": "SYNTHETIC-D121-AUTHORIZATION",
        "authorization_sha256": SHA,
        "resolution_id": "SYNTHETIC-RESOLUTION",
        "resolution_sha256": SHA,
        "transition_id": "SYNTHETIC-T1",
        "transition_sha256": SHA,
        "action_plan_sha256": SHA,
        "runtime_implementation_hashes": {name: SHA for name in runtime_names},
        "ssh_argv_sha256": SHA,
        "rendered_programs": [
            {
                "ordinal": ordinal,
                "observation_id": f"SYNTHETIC-{ordinal}",
                "size_bytes": 1,
                "sha256": SHA,
            }
            for ordinal in range(1, 7)
        ],
        "pinned_openssh_inputs": {
            "known_hosts": {**snapshot, "role": "KNOWN_HOSTS"},
            "transport_identity": {**snapshot, "role": "TRANSPORT_IDENTITY"},
        },
        "openssh_consumption_capability": {
            "mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
            "result": "PASS",
            "ssh_version": "SYNTHETIC",
            "ssh_sha256": SHA,
            "sshd_sha256": SHA,
            "ssh_keygen_sha256": SHA,
            "procfs_visible_parent_pid": 1,
            "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True,
            "public_key_authentication": True,
            "local_proxy_pipe_only": True,
            "network_used": False,
            "private_bytes_recorded": False,
            "report_sha256": SHA,
        },
        "process_supervisor_capability": {
            "mechanism": "LINUX_SUBREAPER_NSPID_NSPGID_HELD_LEADER-v2",
            "namespace_local_executor_pid": 1,
            "namespace_local_executor_pgid": 1,
            "procfs_visible_executor_pid": 1,
            "procfs_visible_executor_pgid": 1,
            "pid_namespace_inode": "1",
            "procfs_pid_namespace_inode": "1",
            "nspid": [1],
            "nspgid": [1],
            "mapping_unambiguous": True,
            "waitid_wnowait_available": True,
            "subreaper_state_readable": True,
            "initial_subreaper_state": 0,
            "signal_after_leader_reap_allowed": False,
            "result": "PASS",
        },
        "prospective_evaluation_at_utc": "2030-01-01T00:00:00Z",
        "actual_authority_sample_before_marker_utc": "2030-01-01T00:00:00Z",
        "monotonic_deadline_ns": 2,
        "monotonic_authority_deadline_ns": 2,
        "process_group_ownership":
            "LINUX_SUBREAPER_NSPID_NSPGID_HOLD_LEADER_QUIESCE_THEN_REAP",
        "attempt_number": 1,
        "retry_allowed": False,
        "post_marker_authority_sample_required": True,
        "stage18_authority": False,
    }


def create_predecessor_blockers(root: pathlib.Path, temporary: pathlib.Path) \
        -> dict[str, pathlib.Path]:
    source_journal = temporary / "source-journal.json"
    source_authorization = temporary / "source-authorization.json"
    source_resolution = temporary / "source-resolution.json"
    source_transition = temporary / "source-transition.json"
    for path, label in (
        (source_journal, "journal"),
        (source_authorization, "authorization"),
        (source_resolution, "resolution"),
        (source_transition, "transition"),
    ):
        write_json(path, {"synthetic": label})

    pre_output = temporary / "d120-empty-output"
    pre_output.mkdir(mode=0o700)
    pre_document = pre_blocker.render(
        blocker_id="SYNTHETIC-D120-BLOCKER",
        recorded_at_utc="2030-01-01T00:00:00Z",
        transaction_id="SYNTHETIC-D120",
        journal=source_journal,
        authorization=source_authorization,
        output_root=pre_output,
    )
    pre_path = temporary / "pre-marker-blocker.json"
    write_json(pre_path, pre_document)

    post_output = temporary / "d121-marker-only-output"
    post_output.mkdir(mode=0o700)
    marker = post_output / post_blocker.ATTEMPT_NAME
    write_json(marker, synthetic_v8_marker(root))
    post_document = post_blocker.build(SimpleNamespace(
        blocker_id="SYNTHETIC-D122-BLOCKER",
        actor="synthetic-owner",
        output_root=post_output,
        journal=source_journal,
        authorization=source_authorization,
        resolution=source_resolution,
        transition=source_transition,
    ))
    post_path = temporary / "post-marker-blocker.json"
    write_json(post_path, post_document)

    action_output = temporary / "d123-empty-output"
    action_output.mkdir(mode=0o700)
    action_document = action_blocker.render(SimpleNamespace(
        blocker_id="SYNTHETIC-D123-BLOCKER",
        recorded_at_utc="2030-01-01T00:00:03Z",
        actor="synthetic-owner",
        transaction_id="SYNTHETIC-D123",
        journal=source_journal,
        authorization=source_authorization,
        resolution=source_resolution,
        transition=source_transition,
        output_root=action_output,
    ))
    action_path = temporary / "action-revalidation-blocker.json"
    write_json(action_path, action_document)

    return {"pre": pre_path, "post": post_path, "action": action_path}


def validate_blocker_rejection(root: pathlib.Path, action_path: pathlib.Path) -> None:
    document = json.loads(action_path.read_text(encoding="utf-8"))
    document["retry_performed"] = True
    schema = json.loads(
        (root / "config/schemas/stage17-preflight-action-revalidation-blocker-v1.schema.json")
        .read_text(encoding="utf-8")
    )
    if not list(Draft202012Validator(schema).iter_errors(document)):
        raise CheckError("D-123 blocker schema accepted retry_performed=true")


def cli(python: str, repository: pathlib.Path, evidence: pathlib.Path,
        *arguments: str) -> subprocess.CompletedProcess[str]:
    return run([
        python,
        "-B",
        str(repository / "tools/stage17_operational_cli_v10.py"),
        "--repository-root",
        str(repository),
        "--evidence-root",
        str(evidence),
        *arguments,
    ])


def self_test(root: pathlib.Path) -> None:
    if shutil.which("ssh-keygen") is None:
        raise CheckError("ssh-keygen is required for the synthetic Ed25519 fixture")
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="stage17-d123-") as text:
        temporary = pathlib.Path(text)
        source_bundle = temporary / "source-bundle"
        shutil.copytree(
            root,
            source_bundle,
            symlinks=False,
            ignore=shutil.ignore_patterns(
                ".git",
                "build",
                "build-*",
                "__pycache__",
                ".pytest_cache",
                "evidence",
            ),
        )
        (source_bundle / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D123-REGRESSION"}\n',
            encoding="ascii",
        )
        (source_bundle / "SHA256SUMS").write_text(
            "synthetic D123 regression fixture; not release evidence\n",
            encoding="ascii",
        )
        evidence = temporary / "operational"
        evidence.mkdir(mode=0o700)
        preflight = temporary / "preflight-output"
        preflight.mkdir(mode=0o700)
        bundle_root = temporary / "remote-bundle-root"
        bundle_root.mkdir(mode=0o700)
        archive = temporary / "candidate.tar.gz"
        sidecar = temporary / "candidate.tar.gz.sha256"
        archive.write_bytes(b"synthetic candidate archive\n")
        sidecar.write_text("0" * 64 + "  candidate.tar.gz\n", encoding="ascii")

        identity = temporary / "identity"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity)])
        public = identity.with_suffix(".pub")
        public_fields = public.read_text(encoding="ascii").split()
        known_hosts = temporary / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {public_fields[0]} {public_fields[1]}\n",
            encoding="ascii",
        )

        blockers = create_predecessor_blockers(source_bundle, temporary)
        validate_blocker_rejection(source_bundle, blockers["action"])
        initialized = cli(
            python, source_bundle, evidence, "init",
            "--materialize-admission-root",
        )
        marker = "admission_root="
        admission_text = initialized.stdout.split(marker, 1)[1].strip()
        admission = pathlib.Path(admission_text)
        issued = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
        recorded = issued + dt.timedelta(seconds=4)
        transition_time = issued + dt.timedelta(seconds=5)
        evaluated = issued + dt.timedelta(seconds=6)
        expires = issued + dt.timedelta(minutes=30)
        output = admission / "evidence/ext001-v14"
        cli(
            python,
            admission,
            evidence,
            "--pilot-archive",
            str(archive),
            "--pilot-sidecar",
            str(sidecar),
            "author-ext001",
            "--stand-id",
            "SYNTHETIC-STAND",
            "--ssh-target",
            "synthetic@synthetic.invalid",
            "--known-hosts-host",
            "synthetic.invalid",
            "--pinned-host-public-key",
            str(public),
            "--pinned-known-hosts",
            str(known_hosts),
            "--transport-identity",
            str(identity),
            "--bundle-root-locator",
            str(bundle_root),
            "--capture-id",
            "SYNTHETIC-D123-CAPTURE",
            "--captured-at-utc",
            exact_second(recorded),
            "--preflight-evidence-root",
            str(preflight),
            "--pre-marker-blocker",
            str(blockers["pre"]),
            "--post-marker-blocker",
            str(blockers["post"]),
            "--action-revalidation-blocker",
            str(blockers["action"]),
            "--actor",
            "synthetic-owner",
            "--issued-at-utc",
            exact_second(issued),
            "--expires-at-utc",
            exact_second(expires),
            "--authorization-id",
            "SYNTHETIC-EXT001-D123-AUTH",
            "--attempt-id",
            "SYNTHETIC-EXT001-D123-ATTEMPT",
            "--contract-id",
            "SYNTHETIC-EXT001-D123-CONTRACT",
            "--envelope-id",
            "SYNTHETIC-EXT001-D123-ENVELOPE",
            "--output-directory",
            str(output),
        )
        cli(
            python,
            admission,
            evidence,
            "--pilot-archive",
            str(archive),
            "--pilot-sidecar",
            str(sidecar),
            "admit-resolution",
            "--input-id",
            "S17-EXT-001",
            "--actor",
            "synthetic-owner",
            "--recorded-at-utc",
            exact_second(recorded),
            "--repository-evidence",
            str(output / "envelope-v14.json"),
            "--authorization-file",
            str(output / "authorization-v11.json"),
        )
        cli(
            python,
            admission,
            evidence,
            "--pilot-archive",
            str(archive),
            "--pilot-sidecar",
            str(sidecar),
            "append-transition",
            "--actor",
            "synthetic-owner",
            "--timestamp-utc",
            exact_second(transition_time),
        )
        latest = evidence / "journal/stage17-state-journal-000002.json"
        code = """
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(%r) / 'tools'))
import stage17_read_only_preflight_executor_v12 as executor
validation = executor._prospective_validation(
    repository_root=pathlib.Path(%r),
    latest_journal=pathlib.Path(%r),
    journal_directory=pathlib.Path(%r),
    actual_utc=%r,
)
assert validation.current_state == 'AUTHORIZED_FOR_READ_ONLY_PREFLIGHT'
assert validation.resolution_count == 1 and validation.transition_count == 1
assert validation.action_ready and validation.action_context is not None
print(json.dumps({
    'record_schema_bindings': {
        key: pathlib.PurePosixPath(value['path']).name
        for key, value in validation.action_context['record_schema_bindings'].items()
    },
    'attempt_marker_name': validation.action_context['attempt_marker_name'],
    'failure_name': validation.action_context['failure_name'],
    'completion_name': validation.action_context['completion_name'],
}, sort_keys=True))
""" % (
            str(admission),
            str(admission),
            str(latest),
            str(latest.parent),
            exact_second(evaluated),
        )
        completed = run([python, "-B", "-c", code], cwd=admission)
        context = json.loads(completed.stdout)
        expected = {
            "attempt": "stage17-read-only-preflight-attempt-v10.schema.json",
            "receipt": "stage17-read-only-preflight-observation-receipt-v7.schema.json",
            "failure": "stage17-read-only-preflight-failure-v8.schema.json",
            "failure_retention":
                "stage17-read-only-preflight-failure-retention-v3.schema.json",
            "completion": "stage17-read-only-preflight-completion-v7.schema.json",
        }
        actual = context["record_schema_bindings"]
        if actual != expected:
            raise CheckError(f"current terminal schema binding drifted: {actual}")
        if context["attempt_marker_name"] != "stage17-read-only-preflight-attempt-v10.json":
            raise CheckError("current attempt marker name drifted")
        if context["failure_name"] != "stage17-read-only-preflight-failure-v8.json":
            raise CheckError("current failure record name drifted")
        if context["completion_name"] != "stage17-read-only-preflight-completion-v7.json":
            raise CheckError("current completion record name drifted")
        if any(preflight.iterdir()):
            raise CheckError("action-readiness evaluation created preflight evidence")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument(
        "--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1]
    )
    arguments = parser.parse_args()
    try:
        self_test(arguments.root.resolve())
    except Exception as exception:
        print(f"stage17-action-revalidation-binding: FAIL: {exception}",
              file=sys.stderr)
        return 1
    print(
        "stage17-action-revalidation-binding: PASS "
        f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES} transport=0 marker=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
