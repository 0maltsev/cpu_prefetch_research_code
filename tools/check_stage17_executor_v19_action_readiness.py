#!/usr/bin/env python3
"""D-135 regression for executor v19's corrected runtime-tool symlink
identity.

Two independent proofs. First, a direct, real proof of the collector fix
itself: `stage17_read_only_preflight_collector_v1.render_observation_
program` (the pre-fix logic) and `stage17_read_only_preflight_collector_
v3.render_observation_program` (ADR-0135's fix) are both used to render
`S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES`'s fixed program against a
real local bundle fixture, and each rendered program is actually executed
via `subprocess` -- no mocking. `/usr/bin/python3` is a real symlink on
this machine too (confirmed via `stat`, matching what the real stand
showed), so this reproduces the exact real failure class: `v1`'s program
must fail with `RuntimeError: runtime file`, and `v3`'s must succeed,
proving the fix resolves through the symlink rather than rejecting it.
Second, the same CLI-flow regression `check_stage17_executor_v18_action_
readiness.py` already established: a real admission built through the
live `author-ext001`/`admit-resolution` wiring resolves cleanly and
`action_ready` is true under executor v19 / semantic verifier v21 /
journal v25 / preflight-plan policy v21 (ADR-0135), and the three-
blocker-receipt branch is still cleanly rejected exactly as ADR-0134
left it. Like `check_stage17_executor_v18_action_readiness.py` before
this generation moved past it, this file exercises the repository's own
current `author-ext001`/`admit-resolution` wiring directly, with no
fixture patching -- it will need the same historical-commit pinning
`v13`'s and `v18`'s own regressions already adopted once a later ADR
moves `cli_v11.py`'s default past this generation. It does not create a
transport marker and does not open SSH.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from typing import Any

import author_stage17_action_revalidation_blocker_v1 as action_blocker
import author_stage17_no_predecessor_attestation_v1 as attestation_tool
import author_stage17_post_marker_blocker_v1 as post_blocker
import author_stage17_pre_marker_blocker_v1 as pre_blocker


POSITIVE_CASES = 2
NEGATIVE_CASES = 1
SHA = "a" * 64


class CheckError(RuntimeError):
    pass


def run(command: list[str], *, cwd: pathlib.Path | None = None,
        expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command, cwd=cwd, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
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
        "source_size_bytes": 1, "consumed_sha256": SHA, "snapshot_size_bytes": 1,
        "snapshot_mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
        "verified_seals": ["F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"],
        "procfs_visible_parent_pid": 1, "procfs_process_directory_device": 1,
        "procfs_process_directory_inode": 1, "procfs_process_directory_uid": 1,
        "credential_fd_inherited_by_child": False,
        "source_path_reused_after_marker": False, "private_bytes_recorded": False,
    }
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/8",
        "attempt_id": "SYNTHETIC-D133-ATTEMPT",
        "authorization_id": "SYNTHETIC-D133-AUTHORIZATION",
        "authorization_sha256": SHA, "resolution_id": "SYNTHETIC-RESOLUTION",
        "resolution_sha256": SHA, "transition_id": "SYNTHETIC-T1",
        "transition_sha256": SHA, "action_plan_sha256": SHA,
        "runtime_implementation_hashes": {name: SHA for name in runtime_names},
        "ssh_argv_sha256": SHA,
        "rendered_programs": [
            {"ordinal": ordinal, "observation_id": f"SYNTHETIC-{ordinal}",
             "size_bytes": 1, "sha256": SHA}
            for ordinal in range(1, 7)
        ],
        "pinned_openssh_inputs": {
            "known_hosts": {**snapshot, "role": "KNOWN_HOSTS"},
            "transport_identity": {**snapshot, "role": "TRANSPORT_IDENTITY"},
        },
        "openssh_consumption_capability": {
            "mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1", "result": "PASS",
            "ssh_version": "SYNTHETIC", "ssh_sha256": SHA, "sshd_sha256": SHA,
            "ssh_keygen_sha256": SHA, "procfs_visible_parent_pid": 1,
            "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True, "public_key_authentication": True,
            "local_proxy_pipe_only": True, "network_used": False,
            "private_bytes_recorded": False, "report_sha256": SHA,
        },
        "process_supervisor_capability": {
            "mechanism": "LINUX_SUBREAPER_NSPID_NSPGID_HELD_LEADER-v2",
            "namespace_local_executor_pid": 1, "namespace_local_executor_pgid": 1,
            "procfs_visible_executor_pid": 1, "procfs_visible_executor_pgid": 1,
            "pid_namespace_inode": "1", "procfs_pid_namespace_inode": "1",
            "nspid": [1], "nspgid": [1], "mapping_unambiguous": True,
            "waitid_wnowait_available": True, "subreaper_state_readable": True,
            "initial_subreaper_state": 0, "signal_after_leader_reap_allowed": False,
            "result": "PASS",
        },
        "prospective_evaluation_at_utc": "2030-01-01T00:00:00Z",
        "actual_authority_sample_before_marker_utc": "2030-01-01T00:00:00Z",
        "monotonic_deadline_ns": 2, "monotonic_authority_deadline_ns": 2,
        "process_group_ownership":
            "LINUX_SUBREAPER_NSPID_NSPGID_HOLD_LEADER_QUIESCE_THEN_REAP",
        "attempt_number": 1, "retry_allowed": False,
        "post_marker_authority_sample_required": True, "stage18_authority": False,
    }


def create_blocker_evidence(root: pathlib.Path, temporary: pathlib.Path) \
        -> dict[str, pathlib.Path]:
    source_journal = temporary / "source-journal.json"
    source_authorization = temporary / "source-authorization.json"
    source_resolution = temporary / "source-resolution.json"
    source_transition = temporary / "source-transition.json"
    for path, label in (
        (source_journal, "journal"), (source_authorization, "authorization"),
        (source_resolution, "resolution"), (source_transition, "transition"),
    ):
        write_json(path, {"synthetic": label})
    pre_output = temporary / "d120-empty-output"
    pre_output.mkdir(mode=0o700)
    pre_document = pre_blocker.render(
        blocker_id="SYNTHETIC-D120-BLOCKER", recorded_at_utc="2030-01-01T00:00:00Z",
        transaction_id="SYNTHETIC-D120", journal=source_journal,
        authorization=source_authorization, output_root=pre_output,
    )
    pre_path = temporary / "pre-marker-blocker.json"
    write_json(pre_path, pre_document)
    post_output = temporary / "d121-marker-only-output"
    post_output.mkdir(mode=0o700)
    marker = post_output / post_blocker.ATTEMPT_NAME
    write_json(marker, synthetic_v8_marker(root))
    post_document = post_blocker.build(SimpleNamespace(
        blocker_id="SYNTHETIC-D121-BLOCKER", actor="synthetic-owner",
        output_root=post_output, journal=source_journal,
        authorization=source_authorization, resolution=source_resolution,
        transition=source_transition,
    ))
    post_path = temporary / "post-marker-blocker.json"
    write_json(post_path, post_document)
    action_output = temporary / "d123-empty-output"
    action_output.mkdir(mode=0o700)
    action_document = action_blocker.render(SimpleNamespace(
        blocker_id="SYNTHETIC-D123-BLOCKER", recorded_at_utc="2030-01-01T00:00:03Z",
        actor="synthetic-owner", transaction_id="SYNTHETIC-D123",
        journal=source_journal, authorization=source_authorization,
        resolution=source_resolution, transition=source_transition,
        output_root=action_output,
    ))
    action_path = temporary / "action-revalidation-blocker.json"
    write_json(action_path, action_document)
    return {"pre": pre_path, "post": post_path, "action": action_path}


def create_attestation_evidence(temporary: pathlib.Path) -> pathlib.Path:
    search_evidence = temporary / "d133-search-evidence.txt"
    search_evidence.write_text(
        "synthetic D-133 regression fixture; not real search evidence\n",
        encoding="ascii",
    )
    output = temporary / "no-predecessor-attestation.json"
    completed = run([
        sys.executable, "-B", str(pathlib.Path(attestation_tool.__file__)),
        "--attestation-id", "SYNTHETIC-D133-ATTESTATION",
        "--actor", "synthetic-owner",
        "--search-evidence", str(search_evidence),
        "--search-evidence-schema-identity",
        "cpu-prefetch-stage17-d120-d121-d123-search-record/1",
        "--output", str(output),
    ])
    assert "PASS" in completed.stdout
    return output


def cli(python: str, repository: pathlib.Path, evidence: pathlib.Path,
        *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run([
        python, "-B", str(repository / "tools/stage17_operational_cli_v11.py"),
        "--repository-root", str(repository), "--evidence-root", str(evidence),
        *arguments,
    ], expected=expected)


def run_branch(root: pathlib.Path, source_bundle: pathlib.Path, *,
               branch: str, output_subdir: str) -> dict[str, Any]:
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix=f"stage17-d133-{branch.lower()}-") as text:
        temporary = pathlib.Path(text)
        evidence = temporary / "operational"
        evidence.mkdir(mode=0o700)
        preflight = temporary / "preflight-output"
        preflight.mkdir(mode=0o700)
        bundle_root = temporary / "remote-bundle-root"
        bundle_root.mkdir(mode=0o700)
        (bundle_root / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D135-CAPTURED-BUNDLE"}\n', encoding="ascii",
        )
        (bundle_root / "SHA256SUMS").write_text(
            "synthetic-inventory-line-1\nsynthetic-inventory-line-2\n", encoding="ascii",
        )
        archive = temporary / "candidate.tar.gz"
        sidecar = temporary / "candidate.tar.gz.sha256"
        archive.write_bytes(b"synthetic candidate archive\n")
        sidecar.write_text("0" * 64 + "  candidate.tar.gz\n", encoding="ascii")
        identity = temporary / "identity"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(identity)])
        identity.chmod(0o600)
        public = identity.with_suffix(".pub")
        public_fields = public.read_text(encoding="ascii").split()
        known_hosts = temporary / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {public_fields[0]} {public_fields[1]}\n",
            encoding="ascii",
        )
        initialized = cli(
            python, source_bundle, evidence, "init", "--materialize-admission-root",
        )
        marker = "admission_root="
        admission = pathlib.Path(initialized.stdout.split(marker, 1)[1].strip())
        issued = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
        recorded = issued + dt.timedelta(seconds=4)
        transition_time = issued + dt.timedelta(seconds=5)
        evaluated = issued + dt.timedelta(seconds=6)
        expires = issued + dt.timedelta(minutes=30)
        output = admission / output_subdir
        base_args = [
            "--stand-id", "SYNTHETIC-STAND", "--ssh-target", "synthetic@synthetic.invalid",
            "--known-hosts-host", "synthetic.invalid",
            "--pinned-host-public-key", str(public),
            "--pinned-known-hosts", str(known_hosts),
            "--transport-identity", str(identity),
            "--bundle-root-locator", str(bundle_root),
            "--capture-id", f"SYNTHETIC-D135-{branch}-CAPTURE",
            "--captured-at-utc", exact_second(recorded),
            "--preflight-evidence-root", str(preflight),
        ]
        if branch == "BLOCKERS":
            blockers = create_blocker_evidence(source_bundle, temporary)
            base_args += [
                "--pre-marker-blocker", str(blockers["pre"]),
                "--post-marker-blocker", str(blockers["post"]),
                "--action-revalidation-blocker", str(blockers["action"]),
            ]
        elif branch == "ATTESTATION":
            attestation = create_attestation_evidence(temporary)
            base_args += ["--no-predecessor-attestation", str(attestation)]
        else:
            raise AssertionError(branch)
        base_args += [
            "--actor", "synthetic-owner",
            "--issued-at-utc", exact_second(issued),
            "--expires-at-utc", exact_second(expires),
            "--authorization-id", f"SYNTHETIC-EXT001-D135-{branch}-AUTH",
            "--attempt-id", f"SYNTHETIC-EXT001-D135-{branch}-ATTEMPT",
            "--contract-id", f"SYNTHETIC-EXT001-D135-{branch}-CONTRACT",
            "--envelope-id", f"SYNTHETIC-EXT001-D135-{branch}-ENVELOPE",
            "--output-directory", str(output),
        ]
        cli(python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "author-ext001", *base_args)
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "admit-resolution",
            "--input-id", "S17-EXT-001", "--actor", "synthetic-owner",
            "--recorded-at-utc", exact_second(recorded),
            "--repository-evidence", str(output / "envelope-v14.json"),
            "--authorization-file", str(output / "authorization-v11.json"),
        )
        cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "append-transition",
            "--actor", "synthetic-owner", "--timestamp-utc", exact_second(transition_time),
        )
        latest = evidence / "journal/stage17-state-journal-000002.json"
        code = """
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(%r) / 'tools'))
import stage17_read_only_preflight_executor_v19 as executor
assert hasattr(executor.current_semantic, 'evaluate_s17_ext_001_action_readiness_v20')
assert executor.current_semantic.__name__ == 'stage17_read_only_preflight_semantic_verifier_v20', (
    'regression: executor v19 must keep current_semantic bound to semantic verifier v20 directly'
)
assert executor.snapshot_broker.__name__ == 'stage17_openssh_parent_snapshot_v5', (
    'regression: executor v19 must consult openssh snapshot broker v5'
)
assert executor.stage17_read_only_preflight_collector_v3.__name__ == (
    'stage17_read_only_preflight_collector_v3'
), 'regression: executor v19 must consult collector v3'
validation = executor._prospective_validation(
    repository_root=pathlib.Path(%r),
    latest_journal=pathlib.Path(%r),
    journal_directory=pathlib.Path(%r),
    actual_utc=%r,
)
assert validation.current_state == 'AUTHORIZED_FOR_READ_ONLY_PREFLIGHT'
assert validation.resolution_count == 1 and validation.transition_count == 1
assert validation.action_ready and validation.action_context is not None
bindings = validation.action_context['pre_marker_file_bindings']
extra = bindings[-1:] if %r == 'ATTESTATION' else bindings[-3:]
collector_context = validation.action_context['collector_context']
print(json.dumps({
    'extra_binding_count': len(extra), 'total_binding_count': len(bindings),
    'archive_size_bytes': collector_context['archive_size_bytes'],
    'archive_sha256': collector_context['archive_sha256'],
}))
""" % (
            str(admission), str(admission), str(latest), str(latest.parent),
            exact_second(evaluated), branch,
        )
        completed = run([python, "-B", "-c", code], cwd=admission)
        result = json.loads(completed.stdout)
        expected_count = 1 if branch == "ATTESTATION" else 3
        if result["extra_binding_count"] != expected_count:
            raise CheckError(
                f"{branch}: expected {expected_count} extra file bindings, "
                f"got {result['extra_binding_count']}"
            )
        if any(preflight.iterdir()):
            raise CheckError(f"{branch}: action-readiness evaluation created preflight evidence")
        return result


def run_rejected_blockers_branch(root: pathlib.Path, source_bundle: pathlib.Path) -> None:
    """Prove the three-blocker-receipt branch is cleanly rejected, not
    silently mismatched or crashed, under policy v20/v28 -- ADR-0134
    explicitly scopes the archive-identity fix to the attestation branch
    only (see its own text); this is the negative case proving that scope
    boundary is safe rather than merely unexercised.
    """
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix="stage17-d134-blockers-") as text:
        temporary = pathlib.Path(text)
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
        identity.chmod(0o600)
        public = identity.with_suffix(".pub")
        public_fields = public.read_text(encoding="ascii").split()
        known_hosts = temporary / "known_hosts"
        known_hosts.write_text(
            f"synthetic.invalid {public_fields[0]} {public_fields[1]}\n",
            encoding="ascii",
        )
        initialized = cli(
            python, source_bundle, evidence, "init", "--materialize-admission-root",
        )
        marker = "admission_root="
        admission = pathlib.Path(initialized.stdout.split(marker, 1)[1].strip())
        issued = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
        recorded = issued + dt.timedelta(seconds=4)
        expires = issued + dt.timedelta(minutes=30)
        output = admission / "evidence/ext001-d134-blockers-rejected"
        blockers = create_blocker_evidence(source_bundle, temporary)
        args = [
            "--stand-id", "SYNTHETIC-STAND", "--ssh-target", "synthetic@synthetic.invalid",
            "--known-hosts-host", "synthetic.invalid",
            "--pinned-host-public-key", str(public),
            "--pinned-known-hosts", str(known_hosts),
            "--transport-identity", str(identity),
            "--bundle-root-locator", str(bundle_root),
            "--capture-id", "SYNTHETIC-D135-BLOCKERS-CAPTURE",
            "--captured-at-utc", exact_second(recorded),
            "--preflight-evidence-root", str(preflight),
            "--pre-marker-blocker", str(blockers["pre"]),
            "--post-marker-blocker", str(blockers["post"]),
            "--action-revalidation-blocker", str(blockers["action"]),
            "--actor", "synthetic-owner",
            "--issued-at-utc", exact_second(issued),
            "--expires-at-utc", exact_second(expires),
            "--authorization-id", "SYNTHETIC-EXT001-D135-BLOCKERS-AUTH",
            "--attempt-id", "SYNTHETIC-EXT001-D135-BLOCKERS-ATTEMPT",
            "--contract-id", "SYNTHETIC-EXT001-D135-BLOCKERS-CONTRACT",
            "--envelope-id", "SYNTHETIC-EXT001-D135-BLOCKERS-ENVELOPE",
            "--output-directory", str(output),
        ]
        cli(python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "author-ext001", *args)
        rejected = cli(
            python, admission, evidence, "--pilot-archive", str(archive),
            "--pilot-sidecar", str(sidecar), "admit-resolution",
            "--input-id", "S17-EXT-001", "--actor", "synthetic-owner",
            "--recorded-at-utc", exact_second(recorded),
            "--repository-evidence", str(output / "envelope-v14.json"),
            "--authorization-file", str(output / "authorization-v11.json"),
            expected=1,
        )
        if "contract schema drifted" not in rejected.stderr:
            raise CheckError(
                "regression: three-blocker-receipt admission must be rejected "
                f"with a clear contract-schema message, got: {rejected.stderr}"
            )
        if any(preflight.iterdir()):
            raise CheckError("rejected admission created preflight evidence")


def check_collector_v3_symlink_fix(root: pathlib.Path) -> None:
    """Real, direct proof of ADR-0135's fix: render `S17-RO-PREFLIGHT-005-
    RUNTIME-TOOL-IDENTITIES` with the pre-fix (`v1`) and post-fix (`v3`)
    collectors against a real local bundle fixture, then actually execute
    each rendered program via `subprocess` -- no mocking. `/usr/bin/
    python3` is confirmed a real symlink on this machine too (the same
    class of ordinary Linux packaging the real stand showed), so `v1`'s
    program reproduces the exact real failure and `v3`'s must resolve
    through it instead.
    """
    sys.path.insert(0, str(root / "tools"))
    import stage17_read_only_preflight_collector_v1 as collector_v1
    import stage17_read_only_preflight_collector_v3 as collector_v3

    system_target = pathlib.Path("/usr/bin/python3")
    if not system_target.is_symlink():
        raise CheckError(
            "this regression requires /usr/bin/python3 to be a real symlink "
            "on the machine running it, to reproduce the exact real failure "
            "class -- it is not here, so the fix cannot be proven"
        )
    with tempfile.TemporaryDirectory(prefix="stage17-d135-collector-") as text:
        bundle_root = pathlib.Path(text) / "bundle"
        bin_dir = bundle_root / "release/bin"
        bin_dir.mkdir(parents=True)
        artifacts = {}
        for name in ("cpu_prefetch_smoke", "cpu_prefetch_preflight", "cpu_prefetch_qualification"):
            payload = f"synthetic {name}\n".encode("ascii")
            (bin_dir / name).write_bytes(payload)
            (bin_dir / name).chmod(0o755)
            artifacts[f"release/bin/{name}"] = {
                "path": f"release/bin/{name}",
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        manifest_document = {"release_artifacts": list(artifacts.values())}
        manifest_payload = canonical(manifest_document)
        (bundle_root / "BUNDLE_MANIFEST.json").write_bytes(manifest_payload)
        context = {
            "archive_locator": "/nonexistent/archive.tar.gz",
            "sidecar_locator": "/nonexistent/archive.tar.gz.sha256",
            "bundle_root_locator": str(bundle_root),
            "capture_id": "D135-REGRESSION-CAPTURE",
            "captured_at_utc": "2026-01-01T00:00:00Z",
            "archive_size_bytes": 1, "archive_sha256": "a" * 64,
            "sidecar_size_bytes": 1, "sidecar_sha256": "a" * 64,
            "manifest_sha256": hashlib.sha256(manifest_payload).hexdigest(),
            "internal_file_count": 1,
        }
        observation_5 = collector_v1.OBSERVATION_IDS[4]
        old_program = collector_v1.render_observation_program(observation_5, context)
        old_completed = subprocess.run(
            [sys.executable, "-c", old_program.decode()],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        if old_completed.returncode == 0 or "runtime file" not in old_completed.stderr:
            raise CheckError(
                "regression fixture invalid: v1's pre-fix collector was "
                "expected to fail with 'runtime file' against a real "
                f"symlinked system path, got returncode={old_completed.returncode} "
                f"stderr={old_completed.stderr!r}"
            )
        new_program = collector_v3.render_observation_program(observation_5, context)
        new_completed = subprocess.run(
            [sys.executable, "-c", new_program.decode()],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        if new_completed.returncode != 0:
            raise CheckError(
                "regression: v3's collector must resolve the real "
                f"/usr/bin/python3 symlink instead of rejecting it, got "
                f"returncode={new_completed.returncode} stderr={new_completed.stderr!r}"
            )
        emitted = json.loads(new_completed.stdout)
        identities = emitted["result"]["runtime_identities"]
        if len(identities) != 6 or identities[0]["path"] != "/usr/bin/python3":
            raise CheckError("regression: v3's runtime_identities shape drifted")
        real_sha256 = hashlib.sha256(system_target.read_bytes()).hexdigest()
        if identities[0]["sha256"] != real_sha256:
            raise CheckError(
                "regression: v3 must record the resolved target's real "
                "SHA-256, not a symlink-relative or fabricated value"
            )


def self_test(root: pathlib.Path) -> None:
    if shutil.which("ssh-keygen") is None:
        raise CheckError("ssh-keygen is required for the synthetic Ed25519 fixture")
    check_collector_v3_symlink_fix(root)
    import stage17_read_only_preflight_executor_v19 as executor_module
    if executor_module.snapshot_broker.__name__ != "stage17_openssh_parent_snapshot_v5":
        raise CheckError(
            "regression: stage17_read_only_preflight_executor_v19 must import "
            "stage17_openssh_parent_snapshot_v5 as snapshot_broker"
        )
    if executor_module.current_semantic.__name__ != "stage17_read_only_preflight_semantic_verifier_v20":
        raise CheckError(
            "regression: stage17_read_only_preflight_executor_v19 must keep "
            "current_semantic bound to semantic verifier v20 directly, exactly "
            "as v18 had it -- v21 is a pure IMPLEMENTATION_PATHS rebind used "
            "only by the outer registry's resolution-time dispatch, the same "
            "structural pattern v16-v19 established relative to v15"
        )
    if executor_module.stage17_read_only_preflight_collector_v3.__name__ != (
        "stage17_read_only_preflight_collector_v3"
    ):
        raise CheckError(
            "regression: stage17_read_only_preflight_executor_v19 must import "
            "stage17_read_only_preflight_collector_v3"
        )
    if not hasattr(
        executor_module.current_semantic, "evaluate_s17_ext_001_action_readiness_v20"
    ):
        raise CheckError(
            "regression: stage17_read_only_preflight_semantic_verifier_v20 "
            "must define evaluate_s17_ext_001_action_readiness_v20"
        )
    import stage17_read_only_preflight_semantic_verifier_v21 as preflight_v21
    if preflight_v21.IMPLEMENTATION_PATHS["executor"] != "tools/stage17_read_only_preflight_executor_v19.py":
        raise CheckError("regression: preflight policy v21 must bind executor v19")
    if preflight_v21.IMPLEMENTATION_PATHS["collector"] != "tools/stage17_read_only_preflight_collector_v3.py":
        raise CheckError("regression: preflight policy v21 must bind collector v3")
    with tempfile.TemporaryDirectory(prefix="stage17-d135-source-") as text:
        source_bundle = pathlib.Path(text) / "source-bundle"
        # This regression specifically proves executor v19's own
        # action-readiness binding (ADR-0135), which only ever validates a
        # resolution admitted against preflight-plan policy v21, dispatched
        # through `cli_v11.py`'s own `journal_runtime` import (`v26`) and
        # `author-ext001`'s own hardcoded policy path (`v21.json`). ADR-0137
        # moves both forward (journal v27, policy v22), so a `source_bundle`
        # built from the live working tree would build envelopes against the
        # wrong policy generation for this file's own `executor_v19`/
        # `current_semantic` binding -- the same drift class v13's own
        # regression already hit twice against a hand-patched live copy.
        # Extracting the entire tree from the fixed historical commit this
        # generation was actually accepted against keeps every file in this
        # regression's own closure mutually self-consistent by construction,
        # immune to ADR-0137's later, unrelated edits.
        commit_pinned_to_v21 = "e26dc34c67c57c9df8a3351df75afcc725c70720"
        source_bundle.mkdir()
        archive = subprocess.run(
            ["git", "archive", commit_pinned_to_v21], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True,
        ).stdout
        subprocess.run(
            ["tar", "-x"], input=archive, cwd=source_bundle, check=True,
        )
        (source_bundle / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D135-REGRESSION"}\n', encoding="ascii",
        )
        (source_bundle / "SHA256SUMS").write_text(
            "synthetic D135 regression fixture; not release evidence\n", encoding="ascii",
        )
        result = run_branch(root, source_bundle, branch="ATTESTATION",
                             output_subdir="evidence/ext001-d135-attestation")
        if result["extra_binding_count"] != 1:
            raise CheckError("regression: attestation branch binding count drifted")
        run_rejected_blockers_branch(root, source_bundle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    try:
        self_test(arguments.root.resolve())
    except Exception as exception:
        print(f"stage17-executor-v19-action-readiness: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-executor-v19-action-readiness: PASS "
        f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES} transport=0 marker=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
