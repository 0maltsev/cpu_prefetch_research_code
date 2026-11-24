#!/usr/bin/env python3
"""D-122 OpenSSH-fixture quiescence and terminal-schema regressions."""

from __future__ import annotations

import argparse
import copy
import json
import pathlib
import sys
import tempfile
from types import SimpleNamespace

from jsonschema import Draft202012Validator

import stage17_openssh_parent_snapshot_v1 as snapshot_v1
import stage17_openssh_parent_snapshot_v2 as snapshot_v2
import stage17_process_group_supervisor_v2 as supervisor
import stage17_read_only_preflight_semantic_verifier_v13 as verifier_v13
import author_stage17_post_marker_blocker_v1 as blocker_author


ROOT = pathlib.Path(__file__).parents[1]
RUNTIME_KEYS = (
    "collector", "collector_v1_helper", "executor",
    "openssh_snapshot_broker", "openssh_snapshot_broker_v1_helper",
    "operational_semantics", "pilot_candidate_verifier",
    "process_group_supervisor", "semantic_verifier",
    "semantic_verifier_v10_helper", "semantic_verifier_v11_helper",
    "semantic_verifier_v12_helper", "semantic_verifier_v3_helper",
    "semantic_verifier_v4_helper", "semantic_verifier_v5_helper",
    "semantic_verifier_v6_helper", "semantic_verifier_v7_helper",
    "semantic_verifier_v8_helper", "state_journal",
    "state_journal_v10_helper", "state_journal_v11_helper",
    "state_journal_v1_helper",
)

def _schema_runtime_case(name: str) -> None:
    schema = json.loads((ROOT / "config/schemas" / name).read_text())
    Draft202012Validator.check_schema(schema)
    runtime_schema = schema["properties"]["runtime_implementation_hashes"]
    if runtime_schema == {"$ref": "#/$defs/runtime_hashes"}:
        runtime_schema = schema["$defs"]["runtime_hashes"]
    isolated = copy.deepcopy(runtime_schema)
    isolated["$defs"] = copy.deepcopy(schema["$defs"])
    validator = Draft202012Validator(isolated)
    runtime = {key: "a" * 64 for key in RUNTIME_KEYS}
    errors = list(validator.iter_errors(runtime))
    if errors:
        raise AssertionError(f"{name} exact runtime set rejected: {errors[0].message}")
    missing = copy.deepcopy(runtime)
    missing.pop(RUNTIME_KEYS[-1])
    if not list(validator.iter_errors(missing)):
        raise AssertionError(f"{name} accepted a missing runtime identity")
    extra = copy.deepcopy(runtime)
    extra["invented"] = "a" * 64
    if not list(validator.iter_errors(extra)):
        raise AssertionError(f"{name} accepted an extra runtime identity")
    malformed = copy.deepcopy(runtime)
    malformed[RUNTIME_KEYS[0]] = "not-a-sha256"
    if not list(validator.iter_errors(malformed)):
        raise AssertionError(f"{name} accepted a malformed runtime identity")


def _synthetic_v8_marker() -> dict[str, object]:
    sha = "a" * 64
    runtime_names = json.loads(
        (ROOT / "config/schemas/stage17-read-only-preflight-attempt-v8.schema.json")
        .read_text()
    )["properties"]["runtime_implementation_hashes"]["propertyNames"]["enum"]
    snapshot = {
        "source_size_bytes": 1, "consumed_sha256": sha,
        "snapshot_size_bytes": 1,
        "snapshot_mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
        "verified_seals": [
            "F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL",
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
        "authorization_sha256": sha, "resolution_id": "SYNTHETIC-RESOLUTION",
        "resolution_sha256": sha, "transition_id": "SYNTHETIC-T1",
        "transition_sha256": sha, "action_plan_sha256": sha,
        "runtime_implementation_hashes": {name: sha for name in runtime_names},
        "ssh_argv_sha256": sha,
        "rendered_programs": [
            {"ordinal": ordinal, "observation_id": f"SYNTHETIC-{ordinal}",
             "size_bytes": 1, "sha256": sha}
            for ordinal in range(1, 7)
        ],
        "pinned_openssh_inputs": {
            "known_hosts": {**snapshot, "role": "KNOWN_HOSTS"},
            "transport_identity": {**snapshot, "role": "TRANSPORT_IDENTITY"},
        },
        "openssh_consumption_capability": {
            "mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
            "result": "PASS", "ssh_version": "SYNTHETIC",
            "ssh_sha256": sha, "sshd_sha256": sha, "ssh_keygen_sha256": sha,
            "procfs_visible_parent_pid": 1, "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True,
            "public_key_authentication": True, "local_proxy_pipe_only": True,
            "network_used": False, "private_bytes_recorded": False,
            "report_sha256": sha,
        },
        "process_supervisor_capability": {
            "mechanism": "LINUX_SUBREAPER_NSPID_NSPGID_HELD_LEADER-v2",
            "namespace_local_executor_pid": 1,
            "namespace_local_executor_pgid": 1,
            "procfs_visible_executor_pid": 1,
            "procfs_visible_executor_pgid": 1,
            "pid_namespace_inode": "1", "procfs_pid_namespace_inode": "1",
            "nspid": [1], "nspgid": [1], "mapping_unambiguous": True,
            "waitid_wnowait_available": True, "subreaper_state_readable": True,
            "initial_subreaper_state": 0,
            "signal_after_leader_reap_allowed": False, "result": "PASS",
        },
        "prospective_evaluation_at_utc": "2030-01-01T00:00:00Z",
        "actual_authority_sample_before_marker_utc": "2030-01-01T00:00:00Z",
        "monotonic_deadline_ns": 2, "monotonic_authority_deadline_ns": 2,
        "process_group_ownership":
            "LINUX_SUBREAPER_NSPID_NSPGID_HOLD_LEADER_QUIESCE_THEN_REAP",
        "attempt_number": 1, "retry_allowed": False,
        "post_marker_authority_sample_required": True,
        "stage18_authority": False,
    }


def _post_marker_blocker_cases() -> None:
    with tempfile.TemporaryDirectory(prefix="stage17-d122-") as temporary_text:
        temporary = pathlib.Path(temporary_text)
        output = temporary / "marker-only-output"
        output.mkdir(mode=0o700)
        marker = output / blocker_author.ATTEMPT_NAME
        marker.write_text(json.dumps(_synthetic_v8_marker(), sort_keys=True) + "\n")
        sources: dict[str, pathlib.Path] = {}
        for name in ("journal", "authorization", "resolution", "transition"):
            path = temporary / f"{name}.json"
            path.write_text(json.dumps({"synthetic": name}) + "\n")
            sources[name] = path
        blocker = blocker_author.build(SimpleNamespace(
            blocker_id="SYNTHETIC-D122-BLOCKER", actor="synthetic-owner",
            output_root=output, **sources,
        ))
        blocker_path = temporary / "blocker.json"
        blocker_path.write_text(json.dumps(blocker, sort_keys=True) + "\n")
        binding = {
            "locator": str(blocker_path), "size_bytes": blocker_path.stat().st_size,
            "sha256": verifier_v13._sha256(blocker_path),
        }
        verified, verified_path = verifier_v13._verify_post_marker_predecessor(
            ROOT, binding
        )
        if verified_path != blocker_path or verified["retry_allowed"] is not False:
            raise AssertionError("valid post-marker blocker was not retained")

        marker.write_text(json.dumps({"drifted": True}) + "\n")
        try:
            verifier_v13._verify_post_marker_predecessor(ROOT, binding)
        except verifier_v13.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("drifted predecessor marker was accepted")
        marker.write_text(json.dumps(_synthetic_v8_marker(), sort_keys=True) + "\n")

        unexpected = output / "unexpected"
        unexpected.write_text("synthetic\n")
        try:
            verifier_v13._verify_post_marker_predecessor(ROOT, binding)
        except verifier_v13.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("non-marker predecessor output was accepted")
        unexpected.unlink()

        blocker["retry_allowed"] = True
        blocker_path.write_text(json.dumps(blocker, sort_keys=True) + "\n")
        binding["size_bytes"] = blocker_path.stat().st_size
        binding["sha256"] = verifier_v13._sha256(blocker_path)
        try:
            verifier_v13._verify_post_marker_predecessor(ROOT, binding)
        except verifier_v13.SemanticAdmissionError:
            pass
        else:
            raise AssertionError("retry-enabled post-marker blocker was accepted")


def run_self_test() -> None:
    # Characterize the immutable v1 fixture: under a subreaper its short-lived
    # sshd processes are still adopted after the fixture claims PASS.
    predecessor_lease = supervisor.SupervisorLease()
    predecessor_lease.enter()
    try:
        predecessor_report = \
            snapshot_v1.verify_local_openssh_parent_procfd_capability()
        predecessor_children = predecessor_lease.identity_model.direct_children()
        if predecessor_report["result"] != "PASS" or not predecessor_children:
            raise AssertionError("v1 adopted-child defect was not reproduced")
    finally:
        try:
            snapshot_v2._quiesce_capability_children(predecessor_lease)
        finally:
            predecessor_lease.close()

    # The real local OpenSSH/sshd pipe fixture must leave no adopted child.
    report = snapshot_v2.verify_local_openssh_parent_procfd_capability()
    if report["result"] != "PASS" or \
            report["fixture_process_quiescence"]["children_remaining"] != 0:
        raise AssertionError("OpenSSH capability did not reach quiescence")
    lease = supervisor.SupervisorLease()
    lease.enter()
    lease.close()

    for schema_name in (
        "stage17-read-only-preflight-attempt-v9.schema.json",
        "stage17-read-only-preflight-observation-receipt-v6.schema.json",
        "stage17-read-only-preflight-failure-v7.schema.json",
        "stage17-read-only-preflight-failure-retention-v2.schema.json",
        "stage17-read-only-preflight-completion-v6.schema.json",
    ):
        _schema_runtime_case(schema_name)
    _post_marker_blocker_cases()
    print("stage17-preflight-terminal-compatibility: PASS positive=8 negative=19 "
          "transport=0 stand=NOT_ACCESSED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    arguments = parser.parse_args()
    if not arguments.self_test:
        parser.error("--self-test is required")
    try:
        run_self_test()
    except Exception as exception:
        print(f"stage17-preflight-terminal-compatibility: FAIL: {exception}",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
