#!/usr/bin/env python3
"""D-126 regression for executor v13's action-readiness binding.

Builds one temporary operational journal through the public CLI v11 for
each S17-EXT-001 predecessor-evidence branch (the unchanged three-blocker
path, and the new D-124 no-predecessor attestation) and verifies that
executor v13's action-readiness check -- reached exactly as the real
executor reaches it, via `current_semantic.evaluate_s17_ext_001_action_
readiness_v15` -- resolves each branch correctly.  It also proves the
defect this ADR fixes: the new preflight verifier module never defined an
`evaluate_s17_ext_001_action_readiness_v14` attribute, so binding it
unchanged behind the old executor's call site would have raised
`AttributeError` before transport.  It does not create a transport marker
and does not open SSH.
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
        "attempt_id": "SYNTHETIC-D126-ATTEMPT",
        "authorization_id": "SYNTHETIC-D126-AUTHORIZATION",
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
    search_evidence = temporary / "d126-search-evidence.txt"
    search_evidence.write_text(
        "synthetic D-126 regression fixture; not real search evidence\n",
        encoding="ascii",
    )
    output = temporary / "no-predecessor-attestation.json"
    completed = run([
        sys.executable, "-B", str(pathlib.Path(attestation_tool.__file__)),
        "--attestation-id", "SYNTHETIC-D126-ATTESTATION",
        "--actor", "synthetic-owner",
        "--search-evidence", str(search_evidence),
        "--search-evidence-schema-identity",
        "cpu-prefetch-stage17-d120-d121-d123-search-record/1",
        "--output", str(output),
    ])
    assert "PASS" in completed.stdout
    return output


def cli(python: str, repository: pathlib.Path, evidence: pathlib.Path,
        *arguments: str) -> subprocess.CompletedProcess[str]:
    return run([
        python, "-B", str(repository / "tools/stage17_operational_cli_v11.py"),
        "--repository-root", str(repository), "--evidence-root", str(evidence),
        *arguments,
    ])


def run_branch(root: pathlib.Path, source_bundle: pathlib.Path, *,
               branch: str, output_subdir: str) -> dict[str, Any]:
    python = sys.executable
    with tempfile.TemporaryDirectory(prefix=f"stage17-d126-{branch.lower()}-") as text:
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
            "--capture-id", f"SYNTHETIC-D126-{branch}-CAPTURE",
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
            "--authorization-id", f"SYNTHETIC-EXT001-D126-{branch}-AUTH",
            "--attempt-id", f"SYNTHETIC-EXT001-D126-{branch}-ATTEMPT",
            "--contract-id", f"SYNTHETIC-EXT001-D126-{branch}-CONTRACT",
            "--envelope-id", f"SYNTHETIC-EXT001-D126-{branch}-ENVELOPE",
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
import stage17_read_only_preflight_executor_v13 as executor
assert hasattr(executor.current_semantic, 'evaluate_s17_ext_001_action_readiness_v15')
assert not hasattr(executor.current_semantic, 'evaluate_s17_ext_001_action_readiness_v14'), (
    'regression: the new preflight verifier module must never grow the old v14 name; '
    'the fix binds the version-matched v15 name instead of aliasing the old one'
)
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
print(json.dumps({'extra_binding_count': len(extra), 'total_binding_count': len(bindings)}))
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


def self_test(root: pathlib.Path) -> None:
    if shutil.which("ssh-keygen") is None:
        raise CheckError("ssh-keygen is required for the synthetic Ed25519 fixture")
    import stage17_read_only_preflight_semantic_verifier_v15 as preflight_module
    if not hasattr(preflight_module, "evaluate_s17_ext_001_action_readiness_v15"):
        raise CheckError(
            "regression: stage17_read_only_preflight_semantic_verifier_v15 "
            "must define evaluate_s17_ext_001_action_readiness_v15"
        )
    if hasattr(preflight_module, "evaluate_s17_ext_001_action_readiness_v14"):
        raise CheckError(
            "regression: v15 must not silently alias the old v14 action-readiness "
            "name -- executor v13 must call the version-matched v15 name directly"
        )
    with tempfile.TemporaryDirectory(prefix="stage17-d126-source-") as text:
        source_bundle = pathlib.Path(text) / "source-bundle"
        # This regression specifically proves executor v13's own
        # action-readiness binding (ADR-0126), which only ever validates a
        # resolution admitted against preflight-plan policy v15, dispatched
        # through `cli_v11.py`'s own `journal_runtime` import (`v19`, ->
        # policy v23 as of this commit) and `author-ext001`'s own hardcoded
        # policy path (`v15.json`). Both keep moving forward as later ADRs
        # land (policy v16, journal v20/v24, and whatever comes after), and
        # `admit-resolution`'s own bindings check verifies cli_v11.py's real
        # bytes against whichever policy its journal chain resolves to at
        # actual runtime -- so a `source_bundle` built from the live working
        # tree plus a single hand-patched file broke twice already (once
        # against a stale, still-mutable v23 pin, once against the current
        # file's own accumulated later edits): literal string substitution
        # can never guarantee byte-for-byte equality with a hash some
        # *other* policy generation already pinned, and any one live file
        # in the closure moving independently reintroduces the same class
        # of drift. Extracting the entire tree from one fixed historical
        # commit -- rather than the live tree -- keeps every file in this
        # regression's own closure mutually self-consistent by
        # construction, immune to any later, unrelated edit.
        commit_pinned_to_v22 = "b4065e411879876c6d5e8e0dd52952af87dbd810"
        source_bundle.mkdir()
        archive = subprocess.run(
            ["git", "archive", commit_pinned_to_v22], cwd=root,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True,
        ).stdout
        subprocess.run(
            ["tar", "-x"], input=archive, cwd=source_bundle, check=True,
        )
        (source_bundle / "BUNDLE_MANIFEST.json").write_text(
            '{"bundle_profile":"SYNTHETIC-D126-REGRESSION"}\n', encoding="ascii",
        )
        (source_bundle / "SHA256SUMS").write_text(
            "synthetic D126 regression fixture; not release evidence\n", encoding="ascii",
        )
        run_branch(root, source_bundle, branch="BLOCKERS",
                   output_subdir="evidence/ext001-d126-blockers")
        run_branch(root, source_bundle, branch="ATTESTATION",
                   output_subdir="evidence/ext001-d126-attestation")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).parents[1])
    arguments = parser.parse_args()
    try:
        self_test(arguments.root.resolve())
    except Exception as exception:
        print(f"stage17-executor-v13-action-readiness: FAIL: {exception}", file=sys.stderr)
        return 1
    print(
        "stage17-executor-v13-action-readiness: PASS "
        f"positive={POSITIVE_CASES} negative={NEGATIVE_CASES} transport=0 marker=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
