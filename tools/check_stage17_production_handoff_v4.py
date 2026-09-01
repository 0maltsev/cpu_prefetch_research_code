#!/usr/bin/env python3
"""Hermetic Stage 17B.1 admission and compiled fixed-dispatch integration.

The fixture uses disposable SSHSIG keys, temporary typed artifacts, the real
policy-v11 journal runtime, controller v3, sealed snapshots, and the separately
linked C++ test worker.  It opens no socket and grants no real authority.  The
outer driver copies the repository to a disposable bundle-root projection so
repository-owned governance records never modify the checked-in tree.
"""

from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import traceback
from types import SimpleNamespace
from typing import Any, Callable

import author_stage17_action_revalidation_blocker_v1 as action_blocker
import author_stage17_post_marker_blocker_v1 as post_blocker
import author_stage17_pre_marker_blocker_v1 as pre_blocker
import check_stage17_complete_operational_admission as legacy
import stage17_operational_semantics_v4 as semantics
import stage17_exit_state_machine_v4 as exit_machine
import stage17_output_registry_v4 as output_registry
import stage17_pilot_candidate_artifact_v4 as release_artifact
import check_stage17_pilot_semantics_v4 as pilot_plan_builder
import stage17_phase_controller_v1 as rejected_controller
import stage17_phase_controller_v8 as controller
import stage17_q15_session_controller_v6 as q15_session
import stage17_semantic_verifier_v18 as semantic_registry
import stage17_state_journal_v16 as journal


ROOT = pathlib.Path(__file__).resolve().parents[1]
PYTHON = pathlib.Path(sys.executable)
OBSERVATIONS = (
    "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
    "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
    "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
    "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
    "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
    "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
)


class CheckError(RuntimeError):
    pass


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: pathlib.Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(document))


def schema_binding(root: pathlib.Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {"path": relative, "size_bytes": path.stat().st_size, "sha256": digest(path)}


def synthetic_d121_marker(root: pathlib.Path) -> dict[str, object]:
    """A synthetic v8-schema attempt marker for the D-121 post-marker blocker.

    The post-marker-blocker schema is permanently bound to schema
    cpu-prefetch-stage17-read-only-preflight-attempt/8 (D-121's own frozen
    predecessor evidence), independent of which attempt schema the current
    production executor actually emits (v10). This mirrors the same fixture
    construction tools/check_stage17_executor_v13_action_readiness.py uses.
    """
    sha_placeholder = "a" * 64
    runtime_names = json.loads(
        (root / "config/schemas/stage17-read-only-preflight-attempt-v8.schema.json")
        .read_text(encoding="utf-8")
    )["properties"]["runtime_implementation_hashes"]["propertyNames"]["enum"]
    snapshot = {
        "source_size_bytes": 1, "consumed_sha256": sha_placeholder,
        "snapshot_size_bytes": 1,
        "snapshot_mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
        "verified_seals": ["F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"],
        "procfs_visible_parent_pid": 1, "procfs_process_directory_device": 1,
        "procfs_process_directory_inode": 1, "procfs_process_directory_uid": 1,
        "credential_fd_inherited_by_child": False,
        "source_path_reused_after_marker": False, "private_bytes_recorded": False,
    }
    return {
        "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/8",
        "attempt_id": "SYNTHETIC-HERMETIC-D121-ATTEMPT",
        "authorization_id": "SYNTHETIC-HERMETIC-D121-AUTHORIZATION",
        "authorization_sha256": sha_placeholder,
        "resolution_id": "SYNTHETIC-HERMETIC-RESOLUTION",
        "resolution_sha256": sha_placeholder, "transition_id": "SYNTHETIC-HERMETIC-T1",
        "transition_sha256": sha_placeholder, "action_plan_sha256": sha_placeholder,
        "runtime_implementation_hashes": {name: sha_placeholder for name in runtime_names},
        "ssh_argv_sha256": sha_placeholder,
        "rendered_programs": [
            {"ordinal": ordinal, "observation_id": f"SYNTHETIC-{ordinal}",
             "size_bytes": 1, "sha256": sha_placeholder}
            for ordinal in range(1, 7)
        ],
        "pinned_openssh_inputs": {
            "known_hosts": {**snapshot, "role": "KNOWN_HOSTS"},
            "transport_identity": {**snapshot, "role": "TRANSPORT_IDENTITY"},
        },
        "openssh_consumption_capability": {
            "mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1", "result": "PASS",
            "ssh_version": "SYNTHETIC", "ssh_sha256": sha_placeholder,
            "sshd_sha256": sha_placeholder, "ssh_keygen_sha256": sha_placeholder,
            "procfs_visible_parent_pid": 1, "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True, "public_key_authentication": True,
            "local_proxy_pipe_only": True, "network_used": False,
            "private_bytes_recorded": False, "report_sha256": sha_placeholder,
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


def create_hermetic_blocker_evidence(
    root: pathlib.Path, temporary: pathlib.Path,
) -> dict[str, pathlib.Path]:
    """Synthetic D-120/D-121/D-123 blocker receipts for the hermetic rehearsal.

    Mirrors tools/check_stage17_executor_v13_action_readiness.py's
    create_blocker_evidence(): these are explicitly synthetic fixtures, not
    real predecessor evidence, and never touch the checked-in journal or a
    real stand.
    """
    source_journal = temporary / "blocker-source-journal.json"
    source_authorization = temporary / "blocker-source-authorization.json"
    source_resolution = temporary / "blocker-source-resolution.json"
    source_transition = temporary / "blocker-source-transition.json"
    for path, label in (
        (source_journal, "journal"), (source_authorization, "authorization"),
        (source_resolution, "resolution"), (source_transition, "transition"),
    ):
        write(path, {"synthetic": label})
    pre_output = temporary / "d120-empty-output"
    pre_output.mkdir(mode=0o700)
    pre_document = pre_blocker.render(
        blocker_id="SYNTHETIC-HERMETIC-D120-BLOCKER",
        recorded_at_utc="2030-01-01T00:00:00Z",
        transaction_id="SYNTHETIC-HERMETIC-D120", journal=source_journal,
        authorization=source_authorization, output_root=pre_output,
    )
    pre_path = temporary / "pre-marker-blocker.json"
    write(pre_path, pre_document)
    post_output = temporary / "d121-marker-only-output"
    post_output.mkdir(mode=0o700)
    marker = post_output / post_blocker.ATTEMPT_NAME
    write(marker, synthetic_d121_marker(root))
    post_document = post_blocker.build(SimpleNamespace(
        blocker_id="SYNTHETIC-HERMETIC-D121-BLOCKER", actor="synthetic-stage17-owner",
        output_root=post_output, journal=source_journal,
        authorization=source_authorization, resolution=source_resolution,
        transition=source_transition,
    ))
    post_path = temporary / "post-marker-blocker.json"
    write(post_path, post_document)
    action_output = temporary / "d123-empty-output"
    action_output.mkdir(mode=0o700)
    action_document = action_blocker.render(SimpleNamespace(
        blocker_id="SYNTHETIC-HERMETIC-D123-BLOCKER",
        recorded_at_utc="2030-01-01T00:00:03Z",
        actor="synthetic-stage17-owner", transaction_id="SYNTHETIC-HERMETIC-D123",
        journal=source_journal, authorization=source_authorization,
        resolution=source_resolution, transition=source_transition,
        output_root=action_output,
    ))
    action_path = temporary / "action-revalidation-blocker.json"
    write(action_path, action_document)
    return {"pre": pre_path, "post": post_path, "action": action_path}


class OperationalWorkflowDriver:
    """Append operational state below one external evidence root.

    Repository evidence is authored only in the outer driver's disposable
    repository projection.  Journal snapshots, records, and receipts are kept
    in the distinct owner evidence root used by the production v9 runtime.
    """

    def __init__(self, base: pathlib.Path, root: pathlib.Path | None = None) -> None:
        self.base = base
        # Repository evidence is authored only in the outer driver's
        # disposable repository projection: the real extracted bundle root
        # when one is supplied by the hermetic Fixture, so `init` finds a
        # real BUNDLE_MANIFEST.json instead of the raw development tree.
        self.root = (root if root is not None else ROOT).resolve()
        self.external = base / "external"
        self.external.mkdir(mode=0o700)
        self.graph = json.loads((
            self.root / "config/stage17/stage17-operational-graph-definition-v1.json"
        ).read_text())
        self.catalog = json.loads((
            self.root / "config/stage17/stage17-external-input-catalog-v1.json"
        ).read_text())
        self.graph_sha = digest(
            self.root / "config/stage17/stage17-operational-graph-definition-v1.json"
        )
        self.catalog_sha = digest(
            self.root / "config/stage17/stage17-external-input-catalog-v1.json"
        )
        self.versions = legacy.base_journal.version_hashes(self.root)
        self.genesis_record = {
            "journal_id": "STAGE17-STATE-JOURNAL-v1",
            # The immutable graph/catalog/genesis v1 remains bound to pre.2;
            # current policy v12 separately binds the pre.3 implementation.
            "protocol_version": "2.0.0-pre.2", "initial_state": "PREPARED",
            "graph_sha256": self.graph_sha, "catalog_sha256": self.catalog_sha,
            "version_hashes": self.versions,
            "authority_scope": "NO_EXECUTION_AUTHORITY",
        }
        self.genesis_sha = legacy.base_journal.sha256_bytes(
            legacy.base_journal.canonical_json_bytes(self.genesis_record)
        )
        self.resolutions: dict[str, tuple[pathlib.Path, dict[str, Any], str]] = {}
        self.contexts: dict[str, dict[str, Any]] = {}
        self.transition_count = 0
        self.previous_transition_sha = self.genesis_sha
        self.pilot_archive: pathlib.Path | None = None
        self.pilot_sidecar: pathlib.Path | None = None
        self.allowed_signers, self.signing_key = self._synthetic_signer()
        self.operational = base / "operational-evidence"
        self.operational.mkdir(mode=0o700)
        # `init` without --materialize-admission-root just echoes back
        # --repository-root as the admission root, which has no writable
        # evidence/ directory when self.root is a read-only bundle
        # extraction. Materializing a real private admission-root
        # projection (matching the real STAGE17_STAND_HANDOFF.md workflow)
        # gives author-ext001 and friends somewhere to actually write.
        initialized = self._cli("init", "--materialize-admission-root")
        marker = "admission_root="
        self.root = pathlib.Path(initialized.split(marker, 1)[1].strip())
        self.latest_path = self._latest_journal()
        self.latest = json.loads(self.latest_path.read_text())

    def _synthetic_signer(self) -> tuple[pathlib.Path, pathlib.Path]:
        directory = self.external / "synthetic-sshsig"
        directory.mkdir(mode=0o700)
        key = directory / "id_ed25519"
        completed = subprocess.run(
            ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f",
             str(key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=10,
        )
        if completed.returncode != 0:
            raise CheckError("cannot create disposable synthetic Ed25519 fixture")
        public = subprocess.run(
            ["/usr/bin/ssh-keygen", "-y", "-f", str(key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, timeout=10,
        ).stdout.strip()
        allowed = directory / "allowed_signers"
        allowed.write_bytes(b"synthetic-stage17-owner " + public + b"\n")
        return allowed, key

    def repository_evidence(self, path: pathlib.Path) -> dict[str, Any]:
        return {
            "kind": "REPOSITORY_FILE",
            "path": path.relative_to(self.root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": digest(path),
        }

    def predecessor_bindings(self, stop: int, *, start: int = 1) \
            -> list[dict[str, str]]:
        return [
            {
                "input_id": input_id,
                "resolution_id": self.resolutions[input_id][1]["resolution_id"],
                "sha256": self.resolutions[input_id][2],
            }
            for input_id in (
                f"S17-EXT-{index:03d}" for index in range(start, stop + 1)
            )
        ]

    def _cli(
        self, command: str, *arguments: str,
        stdin_payload: bytes | None = None,
    ) -> str:
        invocation = [
            str(PYTHON), "-B", str(self.root / "tools/stage17_operational_cli_v10.py"),
            "--repository-root", str(self.root),
            "--evidence-root", str(self.operational),
        ]
        if self.pilot_archive is not None:
            invocation.extend(("--pilot-archive", str(self.pilot_archive)))
        if self.pilot_sidecar is not None:
            invocation.extend(("--pilot-sidecar", str(self.pilot_sidecar)))
        invocation.extend(("--synthetic-test-only", command, *arguments))
        completed = subprocess.run(
            invocation, cwd=self.root,
            stdin=subprocess.DEVNULL if stdin_payload is None else None,
            input=stdin_payload,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            timeout=1800,
        )
        if completed.returncode != 0:
            raise CheckError(
                "public operational CLI failed: "
                + completed.stderr.decode("utf-8", errors="replace")
            )
        output = completed.stdout.decode("utf-8", errors="strict").rstrip()
        print(output)
        return output

    def _latest_journal(self) -> pathlib.Path:
        candidates = sorted((self.operational / "journal").glob(
            "stage17-state-journal-[0-9][0-9][0-9][0-9][0-9][0-9].json"
        ))
        if not candidates:
            raise CheckError("public CLI did not create a journal")
        return candidates[-1]

    def _reload(self) -> None:
        self.latest_path = self._latest_journal()
        self.latest = json.loads(self.latest_path.read_text())

    def append(self, kind: str, reference: dict[str, Any]) -> None:
        del kind, reference
        raise CheckError("direct journal append is forbidden; use public CLI")

    def ext001(self) -> None:
        host_public = pathlib.Path(str(self.signing_key) + ".pub")
        public_fields = host_public.read_bytes().strip().split()
        if len(public_fields) < 2:
            raise CheckError("synthetic host public key is malformed")
        known = self.external / "synthetic-host.known_hosts"
        known.write_bytes(
            b"synthetic.invalid " + public_fields[0] + b" "
            + public_fields[1] + b"\n"
        )
        self.pilot_archive = self.pilot_archive or (
            self.external / "synthetic-unset-pilot.tar.gz"
        )
        self.pilot_sidecar = self.pilot_sidecar or pathlib.Path(
            str(self.pilot_archive) + ".sha256"
        )
        output = self.root / "evidence/ext001-v11"
        preflight = self.external / "preflight-evidence"
        preflight.mkdir(mode=0o700, exist_ok=True)
        blockers_dir = self.external / "d120-d121-d123-blockers"
        blockers_dir.mkdir(mode=0o700, exist_ok=True)
        blockers = create_hermetic_blocker_evidence(self.root, blockers_dir)
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self._cli(
            "author-ext001",
            "--stand-id", "SYNTHETIC-STAND-NOT-ACCESSED",
            "--ssh-target", "synthetic@synthetic.invalid",
            "--known-hosts-host", "synthetic.invalid",
            "--pinned-host-public-key", str(host_public),
            "--pinned-known-hosts", str(known),
            "--transport-identity", str(self.signing_key),
            "--bundle-root-locator", str(self.root),
            "--capture-id", "SYNTHETIC-S17-PREFLIGHT-TEST-ONLY",
            "--captured-at-utc", now.isoformat().replace("+00:00", "Z"),
            "--preflight-evidence-root", str(preflight),
            "--pre-marker-blocker", str(blockers["pre"]),
            "--post-marker-blocker", str(blockers["post"]),
            "--action-revalidation-blocker", str(blockers["action"]),
            "--actor", "synthetic-stage17-owner",
            "--issued-at-utc", (now - dt.timedelta(seconds=5)).isoformat().replace(
                "+00:00", "Z"
            ),
            "--expires-at-utc", (now + dt.timedelta(minutes=20)).isoformat().replace(
                "+00:00", "Z"
            ),
            "--authorization-id",
            "SYNTHETIC-S17-EXT-001-AUTHORIZATION-TEST-ONLY",
            "--attempt-id", "SYNTHETIC-S17-EXT-001-ATTEMPT-TEST-ONLY",
            "--contract-id", "SYNTHETIC-S17-EXT-001-CONTRACT-TEST-ONLY",
            "--envelope-id", "SYNTHETIC-S17-EXT-001-ENVELOPE-TEST-ONLY",
            "--output-directory", str(output),
        )
        authorization_path = output / "authorization-v11.json"
        authorization = json.loads(authorization_path.read_text())
        envelope_path = output / "envelope-v14.json"
        summary = {
            "authorization_id": authorization["authorization_id"],
            "evidence_path": authorization_path.relative_to(self.root).as_posix(),
            "issued_at_utc": authorization["issued_at_utc"],
            "expires_at_utc": authorization["expires_at_utc"],
            "authority_scope": "READ_ONLY_PREFLIGHT",
        }
        self.add_resolution(
            "S17-EXT-001", [self.repository_evidence(envelope_path)], summary,
            {"manifest_sha256": digest(envelope_path)},
        )

    def _legacy_ext001_fixture_reference(self) -> None:
        """Retained characterization source; never called by the workflow."""
        policy_path = self.root / (
            "config/stage17/stage17-operational-evidence-admission-policy-v9.json"
        )
        policy = json.loads(policy_path.read_text())
        repository_evidence = self.root / "evidence"
        repository_evidence.mkdir(exist_ok=True)
        pinned = repository_evidence / "synthetic-pinned-host-key.json"
        key_type, public = b"ssh-ed25519", bytes(range(32))
        blob = (
            len(key_type).to_bytes(4, "big") + key_type
            + len(public).to_bytes(4, "big") + public
        )
        fingerprint = (
            "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest())
            .decode().rstrip("=")
        )
        write(pinned, {
            "schema_version": "cpu-prefetch-stage17-pinned-host-key-evidence/1",
            "evidence_id": "SYNTHETIC-PIN", "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
            "ssh_target": "synthetic@synthetic.invalid", "algorithm": "ssh-ed25519",
            "public_key_base64": base64.b64encode(blob).decode(),
            "fingerprint_sha256": fingerprint,
            "source": "OWNER_PROVIDED_OUT_OF_BAND_PIN", "runtime_observation": False,
        })
        known = repository_evidence / "synthetic.known_hosts"
        known.write_bytes(
            b"synthetic.invalid ssh-ed25519 " + base64.b64encode(blob) + b"\n"
        )
        identity = self.external / "synthetic-transport-identity"
        identity.write_bytes(b"synthetic-not-a-production-private-key\n")
        identity.chmod(0o600)
        preflight_evidence = self.external / "preflight-evidence"
        preflight_evidence.mkdir(mode=0o700)
        effective = {
            **policy["fixed_action_plan"],
            "schema_identity":
                "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6",
        }
        successor = {
            **policy["successor_action_plan"],
            "schema_identity":
                "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/7",
        }
        pilot_fixed = self.catalog["fixed_evidence_contracts"][0]
        captured = legacy.utc(10)
        contract = {
            "schema_version":
                "cpu-prefetch-stage17-read-only-preflight-supporting-contract/8",
            "contract_id": "SYNTHETIC-S17-EXT-001-CONTRACT-TEST-ONLY",
            "protocol_version": "2.0.0-pre.2", "fixed_action_plan": effective,
            "target": {
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "ssh_target": "synthetic@synthetic.invalid",
                "known_hosts_host": "synthetic.invalid",
                "pinned_host_key_evidence": {
                    "path": pinned.relative_to(self.root).as_posix(),
                    "size_bytes": pinned.stat().st_size, "sha256": digest(pinned),
                    "schema_identity":
                        "cpu-prefetch-stage17-pinned-host-key-evidence/1",
                },
                "pinned_known_hosts": {
                    "path": known.relative_to(self.root).as_posix(),
                    "size_bytes": known.stat().st_size, "sha256": digest(known),
                },
                "transport_identity": {
                    "locator": str(identity), "size_bytes": identity.stat().st_size,
                    "sha256": digest(identity),
                },
            },
            "pilot_candidate": {
                "contract": {
                    "path": pilot_fixed["path"],
                    "size_bytes": pilot_fixed["size_bytes"],
                    "sha256": pilot_fixed["sha256"],
                    "schema_identity":
                        "cpu-prefetch-stage17-pilot-candidate-external-contract/1",
                },
                "archive_locator": "/synthetic/pilot.tar.gz",
                "sidecar_locator": "/synthetic/pilot.tar.gz.sha256",
                "bundle_root_locator": "/synthetic/bundle",
            },
            "capture": {
                "capture_id": "SYNTHETIC-S17-PREFLIGHT-TEST-ONLY",
                "captured_at_utc": captured,
            },
            "evidence_root": str(preflight_evidence),
            "prospective_local_action_identities": [
                {
                    "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR",
                    "role": "EXECUTOR",
                    "execution_path": str(
                        self.root / policy["implementations"]["executor"]["path"]
                    ),
                    "source_binding": policy["implementations"]["executor"],
                },
                {
                    "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR",
                    "role": "COLLECTOR",
                    "execution_path": str(
                        self.root / policy["implementations"]["collector"]["path"]
                    ),
                    "source_binding": policy["implementations"]["collector"],
                },
            ],
            "remote_runtime_identity_policy": {
                "source_input_id": "S17-EXT-002",
                "identity_classes": [
                    "REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY",
                ],
                "prospective_values_present": False,
            },
            "limits": {
                "max_commands": 6, "max_wall_seconds": 180,
                "max_total_output_bytes": 6_291_456,
                "max_output_bytes_per_observation": 1_048_576,
                "timeout_seconds_per_observation": 30,
                "attempts_per_observation": 1, "retries": 0,
            },
            "stop_policy":
                "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT",
            "retention_policy":
                "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE",
            "authority_boundary": {
                "stand_read_only": True, "stand_mutation": False,
                "privileged_controls": False, "qualification": False,
                "calibration": False, "pilot_execution": False,
                "measurement": False, "stage18_authority": False,
            },
        }
        contract_path = repository_evidence / "s17-ext-001-contract-v8.json"
        write(contract_path, contract)
        contract_binding = {
            "path": contract_path.relative_to(self.root).as_posix(),
            "size_bytes": contract_path.stat().st_size,
            "sha256": digest(contract_path),
            "schema_identity":
                "cpu-prefetch-stage17-read-only-preflight-supporting-contract/8",
        }
        issued = legacy.utc(0)
        expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).replace(
            microsecond=0
        ).isoformat().replace("+00:00", "Z")
        authorization = {
            "schema_version":
                "cpu-prefetch-stage17-read-only-preflight-authorization/8",
            "authorization_id":
                "SYNTHETIC-S17-EXT-001-AUTHORIZATION-TEST-ONLY",
            "attempt_id": "SYNTHETIC-S17-EXT-001-ATTEMPT-TEST-ONLY",
            "input_id": "S17-EXT-001", "actor": "synthetic-stage17-owner",
            "issued_at_utc": issued, "expires_at_utc": expires,
            "authority_scope": "READ_ONLY_PREFLIGHT",
            "target_scope": (
                "STAND_ID=SYNTHETIC-STAND-NOT-ACCESSED;"
                "SSH_TARGET=synthetic@synthetic.invalid;SCOPE=READ_ONLY_PREFLIGHT;"
                "PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v6"
            ),
            "target": {
                "stand_id": contract["target"]["stand_id"],
                "ssh_target": contract["target"]["ssh_target"],
                "known_hosts_host": contract["target"]["known_hosts_host"],
                "pinned_host_key_evidence_sha256":
                    contract["target"]["pinned_host_key_evidence"]["sha256"],
                "pinned_known_hosts_sha256":
                    contract["target"]["pinned_known_hosts"]["sha256"],
                "transport_identity_sha256":
                    contract["target"]["transport_identity"]["sha256"],
            },
            "frozen_observation_ids": list(OBSERVATIONS),
            "fixed_action_plan": effective,
            "supporting_observation_contract": contract_binding,
            "evidence_root": str(preflight_evidence), "limits": contract["limits"],
            "role_collapse_acknowledged": True,
            "independent_review_claimed": False,
            "permissions": contract["authority_boundary"],
            "automatic_transition": False, "retry_allowed": False,
            "stage18_authority": False,
        }
        authorization_path = repository_evidence / (
            "s17-ext-001-authorization-v8.json"
        )
        write(authorization_path, authorization)
        authorization_binding = {
            "path": authorization_path.relative_to(self.root).as_posix(),
            "size_bytes": authorization_path.stat().st_size,
            "sha256": digest(authorization_path),
            "schema_identity":
                "cpu-prefetch-stage17-read-only-preflight-authorization/8",
        }
        envelope = {
            "schema_version":
                "cpu-prefetch-stage17-operational-evidence-envelope/9",
            "envelope_id": "SYNTHETIC-S17-EXT-001-ENVELOPE-TEST-ONLY",
            "input_id": "S17-EXT-001",
            "predecessor": {
                "graph_sha256": self.graph_sha,
                "catalog_sha256": self.catalog_sha,
                "genesis_sha256": self.genesis_sha,
                "resolution_schema_identity":
                    "cpu-prefetch-stage17-external-input-resolution/1",
                "resolution_schema_sha256":
                    self.versions["resolution_schema_sha256"],
                "semantic_policy_v8_sha256":
                    policy["predecessor"]["policy_v8"]["sha256"],
                "adr_0113_sha256":
                    policy["predecessor"]["adr_0113"]["sha256"],
            },
            "semantic_policy": {
                "path": policy_path.relative_to(self.root).as_posix(),
                "size_bytes": policy_path.stat().st_size,
                "sha256": digest(policy_path),
            },
            "semantic_verifier": {
                "verifier_id": "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER",
                "verifier_version": "9",
            },
            "authorization": authorization_binding,
            "supporting_contract": contract_binding,
            "effective_action_plan": effective,
            "successor_action_plan": successor,
            "runtime_implementations": policy["implementations"],
            "stage18_authority": False,
        }
        envelope_path = repository_evidence / "s17-ext-001-envelope-v9.json"
        write(envelope_path, envelope)
        summary = {
            "authorization_id": authorization["authorization_id"],
            "evidence_path": authorization_path.relative_to(self.root).as_posix(),
            "issued_at_utc": authorization["issued_at_utc"],
            "expires_at_utc": authorization["expires_at_utc"],
            "authority_scope": "READ_ONLY_PREFLIGHT",
        }
        self.add_resolution(
            "S17-EXT-001", [self.repository_evidence(envelope_path)], summary,
            {"manifest_sha256": digest(envelope_path)},
        )

    def external_receipt(
        self, input_id: str, artifact: pathlib.Path, *,
        contract_path: pathlib.Path | None = None,
        sidecars: list[pathlib.Path] | None = None,
        verifier_id: str = "STAGE17-OPERATIONAL-MANIFEST-VERIFIER",
        verifier_version: str = "3",
    ) -> dict[str, Any]:
        contract_source = contract_path or (
            self.root /
            "config/stage17/stage17-operational-input-external-contract-v2.json"
        )
        del verifier_id, verifier_version
        contract_copy = self.operational / "manifests" / (
            f"{input_id.lower()}-external-contract.json"
        )
        shutil.copyfile(contract_source, contract_copy)
        path = self.operational / "receipts" / f"{input_id.lower()}-receipt.json"
        arguments = [
            "--input-id", input_id, "--artifact", str(artifact),
            "--contract", str(contract_copy), "--custody-domain",
            "SYNTHETIC-TEST-ONLY-CUSTODY", "--output", str(path),
        ]
        for item in sidecars or []:
            arguments.extend(("--sidecar", str(item)))
        self._cli("author-custody-receipt", *arguments)
        return {
            "kind": "EXTERNAL_CUSTODY_RECEIPT",
            "receipt_path": path.relative_to(self.operational).as_posix(),
            "receipt_size_bytes": path.stat().st_size,
            "receipt_sha256": digest(path),
        }

    def add_resolution(
        self, input_id: str, evidence: list[dict[str, Any]],
        authorization: dict[str, Any] | None, context_hint: dict[str, Any],
    ) -> None:
        arguments = [
            "--input-id", input_id, "--actor", "synthetic-stage17-owner",
            "--recorded-at-utc", dt.datetime.now(dt.timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
        ]
        for item in evidence:
            if item["kind"] == "REPOSITORY_FILE":
                arguments.extend(("--repository-evidence",
                                  str(self.root / item["path"])))
            elif item["kind"] == "EXTERNAL_CUSTODY_RECEIPT":
                arguments.extend(("--receipt-evidence",
                                  str(self.operational / item["receipt_path"])))
            else:
                raise CheckError("unsupported public CLI evidence kind")
        if authorization is not None:
            evidence_path = pathlib.Path(authorization["evidence_path"])
            candidates = (self.root / evidence_path, self.external / evidence_path)
            authorization_path = next((item for item in candidates if item.is_file()), None)
            if authorization_path is None:
                raise CheckError("authorization summary has no real source bytes")
            arguments.extend(("--authorization-file", str(authorization_path)))
        self._cli("admit-resolution", *arguments)
        self._reload()
        reference = self.latest["resolution_records"][-1]
        path = self.operational / reference["path"]
        document = json.loads(path.read_text())
        value = digest(path)
        if value != reference["sha256"]:
            raise CheckError("public CLI resolution journal hash drifted")
        self.resolutions[input_id] = (path, document, value)
        self.contexts[input_id] = context_hint

    def add_transition(self) -> None:
        self._cli(
            "append-transition", "--actor", "synthetic-stage17-owner",
            "--timestamp-utc", dt.datetime.now(dt.timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z"),
        )
        self._reload()
        reference = self.latest["transition_records"][-1]
        path = self.operational / reference["path"]
        value = digest(path)
        if value != reference["sha256"]:
            raise CheckError("public CLI transition journal hash drifted")
        self.previous_transition_sha = value
        self.transition_count += 1


class Fixture:
    def __init__(
        self, temporary: pathlib.Path, worker: pathlib.Path,
        bundle_root: pathlib.Path, bundle_archive: pathlib.Path,
        bundle_sidecar: pathlib.Path,
    ) -> None:
        # Move legacy timestamps into the already elapsed day while retaining
        # its immutable exact-second test contracts.
        fixture_epoch = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) - dt.timedelta(minutes=23)
        legacy.BASE_TIME = fixture_epoch.date().isoformat()
        legacy.utc = lambda minute: (fixture_epoch + dt.timedelta(minutes=minute)).isoformat().replace("+00:00", "Z")
        self.bundle_root = bundle_root.resolve()
        self.bundle_archive = bundle_archive.resolve()
        self.bundle_sidecar = bundle_sidecar.resolve()
        self.builder = OperationalWorkflowDriver(temporary, root=self.bundle_root)
        self.root, self.external = self.builder.root, self.builder.external
        self.worker = self.external / "observed-cpu-prefetch-stage17-test-worker"
        shutil.copyfile(worker, self.worker)
        self.worker.chmod(0o700)
        self.allowed = self.external / "observed-allowed-signers"
        shutil.copyfile(self.builder.allowed_signers, self.allowed)
        self.allowed.chmod(0o600)
        self.external_contract = self.root / (
            "config/stage17/stage17-operational-input-external-contract-v2.json"
        )
        self.builder.pilot_archive = self.bundle_archive
        self.builder.pilot_sidecar = self.bundle_sidecar
        self.positive_actions = 0

    def source(self, artifact_id: str, path: pathlib.Path) -> dict[str, Any]:
        return {"id": artifact_id, "size_bytes": path.stat().st_size, "sha256": digest(path)}

    def typed(
        self, directory: pathlib.Path, artifact_id: str, role: str,
        measurements: dict[str, Any], sources: list[dict[str, Any]],
        outcome: str = "VERIFIED", *,
        subject_id: str = "SYNTHETIC-STAGE17-TEST-ONLY",
    ) -> pathlib.Path:
        path = directory / f"{artifact_id.lower()}.json"
        write(path, {
            "schema_version": "cpu-prefetch-stage17-operational-typed-record/4",
            "record_id": artifact_id, "record_role": role,
            "subject_id": subject_id,
            "source_bindings": sources, "measurements": measurements,
            "outcome": outcome, "recorded_at_utc": legacy.utc(3),
            "synthetic_test_only": True, "phase18_authority": False,
        })
        return path

    def artifact(
        self, manifest_dir: pathlib.Path, artifact_id: str, role: str,
        path: pathlib.Path, *, schema: str | None = None,
        lineage: list[dict[str, str]] | None = None,
        schema_identity: str | None = None,
        media_type: str | None = None,
    ) -> dict[str, Any]:
        try:
            locator = path.relative_to(manifest_dir).as_posix()
        except ValueError as exception:
            raise CheckError("fixture artifact is not under its manifest directory") from exception
        document = json.loads(path.read_text()) if schema else None
        return {
            "artifact_id": artifact_id, "role": role,
            "media_type": media_type or (
                "application/json" if schema or schema_identity
                else "application/sshsig" if role in semantics.SIGNATURE_ROLES
                else "application/octet-stream"
            ),
            "locator": locator, "size_bytes": path.stat().st_size, "sha256": digest(path),
            "schema_identity": (
                document["schema_version"] if document else schema_identity
            ),
            "schema_binding": schema_binding(self.root, schema) if schema else None,
            "lineage": lineage or [],
        }

    def manifest(
        self, input_id: str, directory: pathlib.Path,
        artifacts: list[dict[str, Any]], predecessors: list[dict[str, str]],
    ) -> pathlib.Path:
        path = directory / f"{input_id.lower()}-manifest-v4.json"
        arguments = [
            "--input-id", input_id, "--manifest-id",
            f"SYNTHETIC-{input_id}-MANIFEST-v4-TEST-ONLY",
            "--stand-id", "SYNTHETIC-STAND-NOT-ACCESSED",
            "--output", str(path),
        ]
        artifact_specs = b"".join(
            (
                f"{item['role']}:{item['artifact_id']}="
                f"{directory / item['locator']}\n"
            ).encode("utf-8")
            for item in artifacts
        )
        arguments.append("--artifact-stdin")
        self.builder._cli(
            "author-manifest", *arguments, stdin_payload=artifact_specs
        )
        authored = json.loads(path.read_text())
        if authored["predecessor_resolutions"] != predecessors:
            raise CheckError("public manifest predecessor lineage drifted")
        return path

    def receipt(self, input_id: str, artifact: pathlib.Path, *,
                contract: pathlib.Path | None = None,
                sidecars: list[pathlib.Path] | None = None,
                verifier_id: str = "STAGE17-OPERATIONAL-MANIFEST-VERIFIER",
                verifier_version: str = "3") -> dict[str, Any]:
        return self.builder.external_receipt(
            input_id, artifact, contract_path=contract or self.external_contract,
            sidecars=sidecars, verifier_id=verifier_id,
            verifier_version=verifier_version,
        )

    def add(self, input_id: str, evidence: list[dict[str, Any]],
            authorization: dict[str, Any] | None = None) -> None:
        self.builder.add_resolution(input_id, evidence, authorization, {})

    def predecessors(self, stop: int) -> list[dict[str, str]]:
        return self.builder.predecessor_bindings(stop)

    def validate(self, *, as_of_utc: str | None = None) \
            -> journal.OperationalJournalValidation:
        return journal.validate_operational_journal(
            repository_root=self.root,
            evidence_root=self.builder.operational,
            latest_journal=self.builder.latest_path,
            journal_directory=self.builder.operational / "journal",
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
            as_of_utc=as_of_utc,
            allow_synthetic_test_evidence=True,
        )

    def ext001(self) -> None:
        self.builder.ext001()
        self.builder.add_transition()

    def ext002(self) -> None:
        ext1_validation = self.validate()
        ext1_resolution = ext1_validation.resolutions["S17-EXT-001"]
        ext1_context = ext1_resolution.semantic_context
        if not isinstance(ext1_context, dict):
            raise CheckError("synthetic EXT001 semantic context is absent")
        ext1_authorization = ext1_resolution.authorization_document
        if not isinstance(ext1_authorization, dict):
            raise CheckError("synthetic EXT001 authorization is absent")
        ext1_target = ext1_context["contract"]["target"]
        directory = self.external / "ext002"
        directory.mkdir(mode=0o700)
        release_root = directory / "verified-release"
        shutil.copytree(self.bundle_root, release_root, symlinks=False)
        provenance_document = release_artifact.build_extracted_release_receipt_v4(
            bundle_root=release_root,
            receipt_id="SYNTHETIC-EXT002-CLEAN-RELEASE-v4",
        )
        provenance = directory / "runtime-release-provenance-v4.json"
        write(provenance, provenance_document)
        worker = release_root / "release/bin/cpu_prefetch_runner"
        self.worker = worker
        signers = directory / "allowed_signers"
        shutil.copyfile(self.allowed, signers); signers.chmod(0o600)
        artifacts = [
            self.artifact(directory, "EXT002-WORKER", "RUNTIME_WORKER_BINARY", worker),
            self.artifact(directory, "EXT002-SIGNERS", "TRUST_ALLOWED_SIGNERS", signers),
            self.artifact(
                directory, "EXT002-RELEASE", "RUNTIME_RELEASE_PROVENANCE",
                provenance,
                schema="config/schemas/stage17-runtime-release-provenance-v4.schema.json",
            ),
        ]
        runtime = self.typed(directory, "EXT002-RUNTIME", "RUNTIME_IDENTITY", {
            "bundle_profile": provenance_document["bundle_profile"],
            "source_revision": provenance_document["source_revision"],
            "bundle_manifest_sha256": provenance_document["bundle_manifest"]["sha256"],
            "sha256s_sha256": provenance_document["sha256s"]["sha256"],
            "sbom_sha256": provenance_document["sbom"]["sha256"],
            "inventory_sha256": provenance_document["inventory"]["sha256"],
            "worker_path": str(worker), "worker_size_bytes": worker.stat().st_size,
            "worker_sha256": digest(worker), "worker_role": "STAGE17_FIXED_ACTION_WORKER",
            "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
            "supported_actions": ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT"],
            "full_bundle_verifier_sha256": provenance_document[
                "full_bundle_verifier"
            ]["sha256"],
        }, [self.source("EXT002-WORKER", worker),
            self.source("EXT002-RELEASE", provenance)])
        trust = self.typed(directory, "EXT002-TRUST", "TRUST_ANCHOR", {
            "allowed_signers_path": str(signers), "allowed_signers_size_bytes": signers.stat().st_size,
            "allowed_signers_sha256": digest(signers), "principal": "synthetic-stage17-owner",
            "sshsig_namespace": "cpu-prefetch-stage17-fixed-action-test-v2",
            "signer_role": "OWNER_OPERATOR_CUSTODIAN", "reviewer_role": "OWNER_AUDITOR_COLLAPSED",
            "stand_anchor_sha256": ext1_target["pinned_host_key_evidence"]["sha256"],
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
        }, [self.source("EXT002-SIGNERS", signers)],
                           subject_id="SYNTHETIC-STAND-NOT-ACCESSED")
        artifacts.extend((
            self.artifact(directory, "EXT002-RUNTIME", "RUNTIME_IDENTITY", runtime,
                          schema=semantics.TYPED_SCHEMA),
            self.artifact(directory, "EXT002-TRUST", "TRUST_ANCHOR", trust,
                          schema=semantics.TYPED_SCHEMA),
        ))
        transition = ext1_validation.transitions[0]
        action_plan_sha = "1" * 64
        runtime_hashes = {f"runtime_{index:02d}": f"{index + 16:064x}"
                          for index in range(17)}
        programs = []
        for ordinal, observation in enumerate(OBSERVATIONS, 1):
            payload = f"synthetic-fixed-read-only-program:{ordinal}:{observation}\n".encode()
            programs.append({"ordinal": ordinal, "observation_id": observation,
                             "size_bytes": len(payload),
                             "sha256": hashlib.sha256(payload).hexdigest()})
        snapshot = lambda role, value: {
            "role": role, "source_size_bytes": len(value),
            "consumed_sha256": hashlib.sha256(value).hexdigest(),
            "snapshot_size_bytes": len(value),
            "snapshot_mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1",
            "verified_seals": ["F_SEAL_WRITE", "F_SEAL_GROW", "F_SEAL_SHRINK", "F_SEAL_SEAL"],
            "procfs_visible_parent_pid": os.getpid(),
            "procfs_process_directory_device": 1,
            "procfs_process_directory_inode": 1,
            "procfs_process_directory_uid": os.getuid(),
            "credential_fd_inherited_by_child": False,
            "source_path_reused_after_marker": False,
            "private_bytes_recorded": False,
        }
        known_bytes = b"synthetic-known-hosts\n"
        identity_bytes = b"synthetic-private-bytes-not-recorded"
        capability = {
            "mechanism": "LINUX_SEALED_MEMFD_PARENT_PROCFS-v1", "result": "PASS",
            "ssh_version": "synthetic-hermetic", "ssh_sha256": "2" * 64,
            "sshd_sha256": "3" * 64, "ssh_keygen_sha256": "4" * 64,
            "procfs_visible_parent_pid": os.getpid(),
            "descriptor_inheritance_used": False,
            "source_mutation_before_consumption": True,
            "strict_host_key_verification": True,
            "public_key_authentication": True, "local_proxy_pipe_only": True,
            "network_used": False, "private_bytes_recorded": False,
            "report_sha256": "5" * 64,
        }
        supervisor = {
            "mechanism": "LINUX_SUBREAPER_NSPID_NSPGID_HELD_LEADER-v2",
            "namespace_local_executor_pid": os.getpid(),
            "namespace_local_executor_pgid": os.getpgrp(),
            "procfs_visible_executor_pid": os.getpid(),
            "procfs_visible_executor_pgid": os.getpgrp(),
            "pid_namespace_inode": "1", "procfs_pid_namespace_inode": "1",
            "nspid": [os.getpid()], "nspgid": [os.getpgrp()],
            "mapping_unambiguous": True, "waitid_wnowait_available": True,
            "subreaper_state_readable": True, "initial_subreaper_state": 0,
            "signal_after_leader_reap_allowed": False, "result": "PASS",
        }
        attempt_document = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-attempt/7",
            "attempt_id": "SYNTHETIC-PREFLIGHT-ATTEMPT-v7",
            "authorization_id": ext1_authorization["authorization_id"],
            "authorization_sha256": ext1_context["authorization_sha256"],
            "resolution_id": ext1_validation.resolutions["S17-EXT-001"].resolution_id,
            "resolution_sha256": ext1_validation.resolutions["S17-EXT-001"].sha256,
            "transition_id": transition.transition_id,
            "transition_sha256": transition.sha256,
            "action_plan_sha256": action_plan_sha,
            "runtime_implementation_hashes": runtime_hashes,
            "ssh_argv_sha256": "6" * 64, "rendered_programs": programs,
            "pinned_openssh_inputs": {
                "known_hosts": snapshot("KNOWN_HOSTS", known_bytes),
                "transport_identity": snapshot("TRANSPORT_IDENTITY", identity_bytes),
            },
            "openssh_consumption_capability": capability,
            "process_supervisor_capability": supervisor,
            "prospective_evaluation_at_utc": legacy.utc(1),
            "actual_authority_sample_before_marker_utc": legacy.utc(1),
            "monotonic_deadline_ns": 180_000_000_000,
            "monotonic_authority_deadline_ns": 180_000_000_000,
            "process_group_ownership": "LINUX_SUBREAPER_NSPID_NSPGID_HOLD_LEADER_QUIESCE_THEN_REAP",
            "attempt_number": 1, "retry_allowed": False,
            "post_marker_authority_sample_required": True,
            "stage18_authority": False,
        }
        attempt = directory / "preflight-attempt-v7.json"
        write(attempt, attempt_document)
        artifacts.append(self.artifact(
            directory, "EXT002-ATTEMPT", "PREFLIGHT_ATTEMPT", attempt,
            schema="config/schemas/stage17-read-only-preflight-attempt-v7.schema.json",
        ))
        common_receipt = {
            "attempt_id": attempt_document["attempt_id"],
            "attempt_marker_sha256": digest(attempt),
            "authorization_id": attempt_document["authorization_id"],
            "authorization_sha256": attempt_document["authorization_sha256"],
            "resolution_id": attempt_document["resolution_id"],
            "resolution_sha256": attempt_document["resolution_sha256"],
            "transition_id": transition.transition_id,
            "transition_sha256": transition.sha256,
            "action_plan_sha256": action_plan_sha,
            "runtime_implementation_hashes": runtime_hashes,
            "executor_sha256": runtime_hashes["runtime_00"],
            "collector_sha256": runtime_hashes["runtime_01"],
            "pinned_inputs_metadata_sha256": "7" * 64,
            "consumed_known_hosts_sha256": hashlib.sha256(known_bytes).hexdigest(),
            "consumed_transport_identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
            "openssh_consumption_capability_sha256": hashlib.sha256(
                canonical(capability)
            ).hexdigest(),
        }
        receipt_paths = []
        for ordinal, observation in enumerate(OBSERVATIONS, 1):
            stdout = directory / f"observation-{ordinal:02d}.stdout"
            stderr = directory / f"observation-{ordinal:02d}.stderr"
            stdout.write_bytes(canonical({"observation_id": observation, "synthetic_test_only": True}))
            stderr.write_bytes(f"synthetic-stderr:{ordinal}\n".encode("ascii"))
            stdout_id, stderr_id = f"EXT002-STDOUT-{ordinal}", f"EXT002-STDERR-{ordinal}"
            artifacts.extend((self.artifact(directory, stdout_id, "PREFLIGHT_STDOUT", stdout),
                              self.artifact(directory, stderr_id, "PREFLIGHT_STDERR", stderr)))
            receipt = directory / f"preflight-receipt-{ordinal:02d}-v5.json"
            write(receipt, {
                "schema_version": "cpu-prefetch-stage17-read-only-preflight-observation-receipt/5",
                **common_receipt, "ordinal": ordinal, "observation_id": observation,
                "rendered_program_sha256": programs[ordinal - 1]["sha256"],
                "ssh_argv_sha256": attempt_document["ssh_argv_sha256"],
                "actual_authority_sample_before_marker_utc": legacy.utc(1),
                "actual_authority_sample_before_first_transport_utc": legacy.utc(1),
                "transport_authority_sample_utc": legacy.utc(1),
                "actual_started_at_utc": legacy.utc(1),
                "actual_completed_at_utc": legacy.utc(1), "duration_ns": 1,
                "returncode": 0, "failure": None,
                "stdout_size_bytes": stdout.stat().st_size,
                "stdout_sha256": digest(stdout),
                "stderr_size_bytes": stderr.stat().st_size,
                "stderr_sha256": digest(stderr),
                "leader_reaped": True, "process_group_gone": True,
                "terminal_cleanup_outcome": "NORMAL_LEADER_REAPED_GROUP_QUIESCENT",
                "descendants_detected_after_leader_exit": False,
                "maximum_descendant_count": 0,
                "cleanup_deadline_overrun": False, "cleanup_diagnostics": [],
                "attempt": 1, "retry": 0, "stage18_authority": False,
            })
            receipt_paths.append(receipt)
            artifacts.append(self.artifact(
                directory, f"EXT002-RECEIPT-{ordinal}",
                "PREFLIGHT_OBSERVATION_RECEIPT", receipt,
                schema="config/schemas/stage17-read-only-preflight-observation-receipt-v5.schema.json",
            ))
        completion = directory / "preflight-completion-v5.json"
        write(completion, {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-completion/5",
            **common_receipt,
            "ssh_argv_sha256": attempt_document["ssh_argv_sha256"],
            "completed_observation_ids": list(OBSERVATIONS),
            "receipt_sha256s": [digest(item) for item in receipt_paths],
            "actual_authority_sample_before_marker_utc": legacy.utc(1),
            "actual_authority_sample_before_first_transport_utc": legacy.utc(1),
            "actual_completed_at_utc": legacy.utc(1), "duration_ns": 6,
            "all_leaders_reaped": True, "all_process_groups_gone": True,
            "process_group_policy": "LINUX_SUBREAPER_HOLD_LEADER_WNOWAIT_QUIESCE_GROUP_THEN_REAP",
            "attempts": 6, "retries": 0, "stage18_authority": False,
        })
        artifacts.append(self.artifact(
            directory, "EXT002-COMPLETION", "PREFLIGHT_COMPLETION", completion,
            schema="config/schemas/stage17-read-only-preflight-completion-v5.schema.json",
        ))
        manifest = self.manifest("S17-EXT-002", directory, artifacts, self.predecessors(1))
        self.add("S17-EXT-002", [self.receipt("S17-EXT-002", manifest)])

    def ext003(self) -> None:
        directory = self.root / "evidence/ext003-v4"
        directory.mkdir(parents=True)
        ext2_path, ext2_doc, ext2_sha = self.builder.resolutions["S17-EXT-002"]
        ext2_manifest = self.external / "ext002/s17-ext-002-manifest-v4.json"
        ext2 = json.loads(ext2_manifest.read_text())
        index = {item["artifact_id"]: item for item in ext2["artifacts"]}
        acceptance = self.typed(directory, "EXT003-ACCEPTANCE", "OWNER_ACCEPTANCE", {
            "ext002_resolution_id": ext2_doc["resolution_id"], "ext002_resolution_sha256": ext2_sha,
            "runtime_record_sha256": index["EXT002-RUNTIME"]["sha256"],
            "trust_record_sha256": index["EXT002-TRUST"]["sha256"],
            "runtime_release_provenance_sha256": index["EXT002-RELEASE"]["sha256"],
            "distinct_auditor": False, "independent_review": False,
            "role_collapse_accepted": True,
        }, [self.source(ext2_doc["resolution_id"], ext2_path),
            {"id": "EXT002-RUNTIME", "size_bytes": index["EXT002-RUNTIME"]["size_bytes"], "sha256": index["EXT002-RUNTIME"]["sha256"]},
            {"id": "EXT002-TRUST", "size_bytes": index["EXT002-TRUST"]["size_bytes"], "sha256": index["EXT002-TRUST"]["sha256"]}], outcome="ACCEPTED")
        manifest = self.manifest("S17-EXT-003", directory, [
            self.artifact(directory, "EXT003-ACCEPTANCE", "OWNER_ACCEPTANCE", acceptance, schema=semantics.TYPED_SCHEMA)
        ], self.predecessors(2))
        self.add("S17-EXT-003", [self.builder.repository_evidence(manifest)])
        self.builder.add_transition()

    def _sign(self, path: pathlib.Path) -> pathlib.Path:
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(self.builder.signing_key),
             "-n", "cpu-prefetch-stage17-fixed-action-test-v2", str(path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        signature = pathlib.Path(str(path) + ".sig")
        if result.returncode != 0 or not signature.is_file():
            raise CheckError("synthetic phase authorization signing failed")
        return signature

    def prepare_action(
        self, action_id: str, action_inputs: dict[str, Any],
        directory: pathlib.Path,
    ) -> tuple[controller.PreparedAction, pathlib.Path, pathlib.Path]:
        directory.mkdir(mode=0o700, exist_ok=True)
        token = action_id.lower().replace("-", "_")
        action_inputs_path = directory / f"{token}-action-inputs.json"
        write(action_inputs_path, action_inputs)
        request_path = directory / f"{action_id.lower().replace('-', '_')}-request-v4.json"
        request_id = f"SYNTHETIC-{action_id}-REQUEST-v4"
        session_id = action_inputs.get(
            "session_id", f"SYNTHETIC-{action_id}-SESSION-v4"
        )
        authorization_id = f"SYNTHETIC-{action_id}-AUTH-v4"
        attempt_id = f"SYNTHETIC-{action_id}-ATTEMPT-v4"
        self.builder._cli(
            "author-request", "--action", action_id,
            "--action-inputs", str(action_inputs_path),
            "--request-id", request_id, "--session-id", session_id,
            "--authorization-id", authorization_id,
            "--attempt-id", attempt_id, "--output-root", str(directory),
            "--output", str(request_path),
        )
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        authorization_path = directory / (
            f"{action_id.lower().replace('-', '_')}-authorization-v4.json"
        )
        self.builder._cli(
            "author-authorization", "--request", str(request_path),
            "--actor", "synthetic-stage17-owner",
            "--reviewer", "OWNER_AUDITOR_COLLAPSED",
            "--issued-at-utc", (now - dt.timedelta(seconds=10)).isoformat().replace(
                "+00:00", "Z"
            ),
            "--expires-at-utc", (now + dt.timedelta(seconds=300)).isoformat().replace(
                "+00:00", "Z"
            ),
            "--output", str(authorization_path),
        )
        signature = self._sign(authorization_path)
        self.builder._cli(
            "verify-signature", "--authorization", str(authorization_path),
            "--signature", str(signature),
        )
        prepared = controller.prepare_action(
            repository_root=self.root,
            journal=self.builder.latest_path,
            journal_directory=self.builder.operational / "journal",
            operational_evidence_root=self.builder.operational,
            authorization_path=authorization_path, signature_path=signature,
            pilot_archive=self.builder.pilot_archive,
            pilot_sidecar=self.builder.pilot_sidecar,
            synthetic_test_only=True,
        )
        return prepared, authorization_path, signature

    def action(
        self, action_id: str, action_inputs: dict[str, Any],
        directory: pathlib.Path,
    ) -> dict[str, Any]:
        prepared, authorization_path, signature = self.prepare_action(
            action_id, action_inputs, directory
        )
        self.builder._cli(
            "execute-action", "--authorization", str(authorization_path),
            "--signature", str(signature),
        )
        token = action_id.lower().replace("-", "_")
        attempt = directory / f"stage17-{token}-attempt-v4.json"
        result = directory / output_registry.RESULT_NAME
        completion = directory / f"stage17-{token}-completion-v4.json"
        for path in (attempt, result, completion):
            if not path.is_file():
                raise CheckError(f"public action CLI omitted output: {path.name}")
        self.positive_actions += 1
        return {"directory": directory, "authorization": authorization_path,
                "signature": signature,
                "request": pathlib.Path(prepared.authorization["request_binding"]["path"]),
                "attempt": attempt, "result": result,
                "completion": completion,
                "result_document": json.loads(result.read_text())}

    def phase_artifacts(
        self, directory: pathlib.Path, token: str, action: dict[str, Any],
        *, include_completion: bool = True, waiting: pathlib.Path | None = None,
    ) -> list[dict[str, Any]]:
        prefix = token.upper()
        roles = {
            "authorization": prefix + "_AUTHORIZATION",
            "signature": prefix + "_SIGNATURE",
            "request": prefix + "_REQUEST", "attempt": prefix + "_ATTEMPT",
            "result": prefix + "_RESULT", "completion": prefix + "_COMPLETION",
        }
        artifacts = []
        for key in ("authorization", "request", "attempt", "result"):
            path = action[key]
            artifacts.append(self.artifact(
                directory, f"{prefix}-{key.upper()}", roles[key], path,
                schema={
                    "authorization": semantics.AUTH_SCHEMA,
                    "request": semantics.REQUEST_SCHEMA,
                    "attempt": semantics.ATTEMPT_SCHEMA,
                    "result": semantics.RESULT_SCHEMA,
                }[key],
            ))
        artifacts.append(self.artifact(
            directory, f"{prefix}-SIGNATURE", roles["signature"],
            action["signature"],
            lineage=[{"id": f"{prefix}-AUTHORIZATION",
                      "sha256": digest(action["authorization"])}],
        ))
        if include_completion:
            artifacts.append(self.artifact(
                directory, f"{prefix}-COMPLETION", roles["completion"],
                action["completion"], schema=semantics.COMPLETION_SCHEMA,
            ))
        if waiting is not None:
            artifacts.append(self.artifact(
                directory, "Q15-R-SESSION-WAITING", "Q15_R_SESSION_WAITING",
                waiting,
                schema="config/schemas/stage17-q15-session-waiting-v1.schema.json",
            ))
        result = json.loads(action["result"].read_text())
        for index, item in enumerate(result["artifacts"]):
            role = item["role"]
            if role not in semantics.ROLE_SCHEMA:
                raise CheckError(f"unexpected phase artifact role: {role}")
            schema = semantics.ROLE_SCHEMA[role]
            artifacts.append(self.artifact(
                directory, f"{prefix}-OUTPUT-{index:05d}", role,
                action["result"].parent / item["file_name"], schema=schema,
                schema_identity=item["schema_identity"],
                media_type=item["media_type"],
            ))
        return artifacts

    def ext004_and_ext005(self) -> None:
        directory = self.external / "q15-session"
        directory.mkdir(mode=0o700)
        q15_r_inputs = {
            "qualification_id": "SYNTHETIC-Q15-QUALIFICATION-v4",
            "attempt_id": "SYNTHETIC-Q15-R-ATTEMPT-v4",
            "session_id": "SYNTHETIC-Q15-SESSION-v4",
            "probe_platform_binding": {
                "cpu": 0, "numa_node": 0,
                "verified_local_llc_bytes": 33_554_432,
                "verified_base_page_bytes": 4096,
            },
        }
        q15_r, q15_r_auth, q15_r_signature = self.prepare_action(
            "Q15-R", q15_r_inputs, directory
        )

        def admit_q15_r_then_prepare_q15_w() -> controller.PreparedAction:
            q15_r_action = {
                "authorization": q15_r_auth, "signature": q15_r_signature,
                "request": pathlib.Path(q15_r.authorization["request_binding"]["path"]),
                "attempt": directory / "stage17-q15_r-attempt-v4.json",
                "result": directory / "stage17-q15-r-result-v4.json",
            }
            waiting = directory / "stage17-q15-session-waiting-v1.json"
            artifacts = self.phase_artifacts(
                directory, "Q15_R", q15_r_action,
                include_completion=False, waiting=waiting,
            )
            q15_output = directory / "q15-r-output-v3.json"
            output = json.loads(q15_output.read_text())
            release = self.validate().resolutions["S17-EXT-003"].semantic_context[
                "release"
            ]
            q15_result_source = self.source("Q15-R-RESULT", q15_r_action["result"])
            common = {
                "schema_version": "cpu-prefetch-qualification-evidence/1",
                "protocol_version": "2.0.0-pre.2",
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "binding_id": "SYNTHETIC-Q15-R-BINDING-v4",
                "source_revision": release.source_revision,
                "binary_sha256": digest(self.worker),
                "captured_at_utc": legacy.utc(4),
                "producer_cpu": 0, "consumer_cpu": 1,
                "sources": [{"artifact_id": q15_result_source["id"],
                             "sha256": q15_result_source["sha256"]}],
                "eligible": True,
            }
            details = {
                "SELECTED_PAIR_CLOCK": {
                    "producer_prime_read_count": 8,
                    "consumer_prime_read_count": 8,
                    "producer_delta_count": 8, "consumer_delta_count": 8,
                    "traced_call_count": 8, "traced_syscall_count": 0,
                    "producer_to_consumer_window_count": 8,
                    "consumer_to_producer_window_count": 8,
                    "exchanges_per_window": 8,
                    "per_core_evaluator_passed": True,
                    "cross_core_evaluator_passed": True,
                    "before_block_repeat": True,
                },
                "RUNTIME_ATOMIC_LAYOUT": {
                    "pointer_atomic_width_bytes": 8,
                    "pointer_atomic_alignment_bytes": 8,
                    "termination_atomic_width_bytes": 4,
                    "termination_atomic_alignment_bytes": 4,
                    "cache_line_bytes": 64,
                    "pointer_atomic_runtime_lock_free": True,
                    "termination_atomic_runtime_lock_free": True,
                    "queue_layout_passed": True,
                    "ownership_lines_separated": True,
                    "termination_dedicated_line": True,
                },
                "ACTUAL_CPU_MIGRATION": {
                    "producer_sample_count": 8, "consumer_sample_count": 8,
                    "producer_first_cpu": 0, "producer_last_cpu": 0,
                    "consumer_first_cpu": 1, "consumer_last_cpu": 1,
                    "producer_migration_count": 0,
                    "consumer_migration_count": 0,
                    "producer_singleton_affinity": True,
                    "consumer_singleton_affinity": True,
                },
                "ADDRESS_RESIDENCY": {
                    "mechanism_id": "SYNTHETIC-MOVE-PAGES-v1",
                    **{
                        name: {"region": name, "expected_node": 0,
                               "before_page_count": 1,
                               "during_page_count": 1,
                               "after_page_count": 1,
                               "unavailable_page_count": 0,
                               "wrong_node_page_count": 0,
                               "migrated_page_count": 0}
                        for name in (
                            "shared_event_and_queue_pages",
                            "producer_private_pages", "consumer_private_pages"
                        )
                    },
                },
                "SOFTWARE_PREFETCH_MAPPING": {
                    "mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
                    "producer_maximum_extended_leaf": 0x80000001,
                    "producer_extended_leaf_ecx": 1 << 8,
                    "producer_prfchw_supported": True,
                    "consumer_maximum_extended_leaf": 0x80000001,
                    "consumer_extended_leaf_ecx": 1 << 8,
                    "consumer_prfchw_supported": True,
                    "ring_producer_instruction": "PREFETCHW",
                    "ring_consumer_instruction": "PREFETCHT0",
                    "linked_consumer_instruction": "PREFETCHT0",
                    "gcc_codegen_passed": True, "clang_codegen_passed": True,
                    "gnu_objdump_passed": True, "llvm_objdump_passed": True,
                },
            }
            for index, (kind, values) in enumerate(details.items(), 1):
                path = directory / f"qualification-{index:02d}.json"
                write(path, {**common, "artifact_id": f"Q15-QUAL-{index:02d}",
                             "kind": kind, "details": values})
                artifacts.append(self.artifact(
                    directory, f"EXT004-QUAL-{index:02d}",
                    "QUALIFICATION_EVIDENCE", path,
                    schema="config/schemas/qualification-evidence-v1.schema.json",
                ))
            platform_path = directory / "platform-v4.json"
            write(platform_path, {
                "schema_version": "2.0.0-pre.3", "protocol_version": "2.0.0-pre.3",
                "platform_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "cpu": {"vendor": "GenuineIntel", "model": "06_55H",
                        "stepping": "synthetic", "microcode": "synthetic",
                        "cache_line_bytes": 64, "atomic_width_bits": 64,
                        "atomic_alignment_bytes": 8},
                "topology": {"sockets": 1, "numa_nodes": 2,
                             "physical_cores": 27, "smt_enabled": False,
                             "cache_domains": ["SYNTHETIC-LLC-0"],
                             "near_core_pair": [0, 1], "far_core_pair": [0, 26]},
                "memory": {"population": "synthetic-test-only",
                           "base_page_bytes": 4096,
                           "residency_verification_method": "synthetic-fixture"},
                "software": {"operating_system": "synthetic-linux",
                             "kernel": "synthetic", "compiler": "synthetic",
                             "standard_library": "synthetic", "language_standard": "C++20",
                             "flags": [], "link_mode": "dynamic"},
                "clock": {"source": "synthetic-monotonic", "time_unit": "tick",
                          "conversion_record_id": "SYNTHETIC-CONVERSION",
                          "serialization_record_id": "SYNTHETIC-SERIALIZATION",
                          "acceptance_record_id": "SYNTHETIC-CLOCK-ACCEPTANCE"},
                "hardware_prefetch_states": [
                    {"requested": state, "verified": verified,
                     "readback_artifact_id": "Q15-R-OUTPUT",
                     "behavioral_probe_artifact_id": "Q15-R-OUTPUT",
                     "privileged_authority_id": "SYNTHETIC-NONE"}
                    for state, verified in (("H0", "VERIFIED_DEFAULT"),
                                            ("H1", "VERIFIED_CHANGED"))
                ],
                "record_sha256": digest(q15_output),
            })
            artifacts.append(self.artifact(
                directory, "EXT004-PLATFORM", "PLATFORM_MANIFEST", platform_path,
                schema="protocol/2.0.0-pre.3/handoff/schemas/platform.schema.json",
            ))
            hw_path = directory / "hardware-prefetch-qualification-v1.json"
            prestate = output["prestate"]
            write(hw_path, {
                "schema_version": "cpu-prefetch-hardware-prefetch-qualification/1",
                "protocol_version": "2.0.0-pre.2",
                "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
                "artifact_id": "SYNTHETIC-Q15-R-H0", "stand_id": common["stand_id"],
                "binding_id": common["binding_id"],
                "source_revision": release.source_revision,
                "command_sha256": digest(q15_r_action["request"]),
                "captured_at_utc": legacy.utc(4), "execution_state": "COMPLETE",
                "requested_state": "H0", "cpu_family_hex": "06",
                "cpu_model_hex": "55", "msr_hex": "000001a4",
                "disable_mask_hex": "000000000000000f",
                "cpu_values": [
                    {"cpu": item["cpu"], "prestate_hex": item["complete_value_hex"],
                     "requested_hex": item["complete_value_hex"],
                     "apply_readback_hex": item["complete_value_hex"],
                     "restore_readback_hex": item["complete_value_hex"]}
                    for item in prestate
                ],
                "regular_probe": {"artifact_id": "Q15-R-OUTPUT",
                                  "sha256": digest(q15_output), "passed": True},
                "pointer_probe": {"artifact_id": "Q15-R-OUTPUT",
                                  "sha256": digest(q15_output), "passed": True},
                "applied": False, "verified": True, "restored": True,
                "quarantined": False, "eligible": True,
            })
            artifacts.append(self.artifact(
                directory, "EXT004-HW-PREFETCH", "HARDWARE_PREFETCH_QUALIFICATION",
                hw_path,
                schema="config/schemas/hardware-prefetch-qualification-v1.schema.json",
            ))
            capacity_placements = {
                placement: {
                    "cache_line_bytes": 64, "usable_l2_bytes": 4096,
                    "producer_home_llc_bytes": 65536,
                    "candidates": [
                        {"capacity": 8, "ring_bytes": 600,
                         "linked_bytes": 700},
                        {"capacity": 16, "ring_bytes": 2500,
                         "linked_bytes": 2600},
                        {"capacity": 32, "ring_bytes": 9000,
                         "linked_bytes": 10000},
                        {"capacity": 64, "ring_bytes": 140000,
                         "linked_bytes": 150000},
                    ],
                    "selected": {"L2_RESIDENT": 8, "LLC_RESIDENT": 32,
                                 "BEYOND_LLC": 64},
                }
                for placement in ("NEAR", "FAR")
            }
            pilot_platform = self.typed(
                directory, "EXT004-PILOT-PLATFORM",
                "PILOT_PLATFORM_MEASUREMENTS",
                {
                    "platform_manifest_sha256": digest(platform_path),
                    "q15_r_result_sha256": digest(q15_r_action["result"]),
                    "topology_evidence": {
                        "producer_cpu": 0, "producer_numa_node": 0,
                        "near_consumer_cpu": 1,
                        "near_consumer_numa_node": 0,
                        "far_consumer_cpu": 26,
                        "far_consumer_numa_node": 1,
                    },
                    "cache_capacity_evidence": {
                        "placements": capacity_placements,
                    },
                },
                [self.source("EXT004-PLATFORM", platform_path),
                 self.source("Q15_R-RESULT", q15_r_action["result"])],
                subject_id=common["stand_id"],
            )
            artifacts.append(self.artifact(
                directory, "EXT004-PILOT-PLATFORM",
                "PILOT_PLATFORM_MEASUREMENTS", pilot_platform,
                schema=semantics.TYPED_SCHEMA,
            ))
            manifest = self.manifest(
                "S17-EXT-004", directory, artifacts, self.predecessors(3)
            )
            self.add("S17-EXT-004", [self.receipt("S17-EXT-004", manifest)])

            q15_r_attempt = directory / "stage17-q15_r-attempt-v4.json"
            q15_r_result = directory / "stage17-q15-r-result-v4.json"
            q15_w_inputs = {
                "q15_r_attempt_sha256": digest(q15_r_attempt),
                "q15_r_result_sha256": digest(q15_r_result),
                "session_id": q15_r_inputs["session_id"],
                "prestate": output["prestate"],
            }
            prepared, q15_w_auth, q15_w_signature = self.prepare_action(
                "Q15-W", q15_w_inputs, directory
            )
            self._q15_w_paths = (q15_w_auth, q15_w_signature)
            return prepared

        outcome = q15_session.execute_session(
            q15_r=q15_r, wait_for_q15_w=admit_q15_r_then_prepare_q15_w,
            synthetic_test_only=True,
        )
        self.positive_actions += 2
        q15_w_auth, q15_w_signature = self._q15_w_paths
        q15_w_action = {
            "authorization": q15_w_auth, "signature": q15_w_signature,
            "request": pathlib.Path(
                json.loads(q15_w_auth.read_text())["request_binding"]["path"]
            ),
            "attempt": directory / "stage17-q15_w-attempt-v4.json",
            "result": directory / "stage17-q15-w-result-v4.json",
            "completion": outcome.completion_path,
        }
        artifacts = self.phase_artifacts(directory, "Q15_W", q15_w_action)
        manifest = self.manifest(
            "S17-EXT-005", directory, artifacts, self.predecessors(4)
        )
        mixed = self.root / "evidence/ext005-mixed-index-v4.json"
        write(mixed, {
            "schema_version": "cpu-prefetch-stage17-mixed-evidence-index/2",
            "input_id": "S17-EXT-005", "manifest_sha256": digest(manifest),
            "synthetic_test_only": True, "phase18_authority": False,
        })
        authorization = json.loads(q15_w_auth.read_text())
        summary = {
            "authorization_id": authorization["authorization_id"],
            "evidence_path": q15_w_auth.relative_to(self.external).as_posix(),
            "issued_at_utc": authorization["issued_at_utc"],
            "expires_at_utc": authorization["expires_at_utc"],
            "authority_scope": "PRIVILEGED_QUALIFICATION_CONTROL",
        }
        self.add(
            "S17-EXT-005",
            [self.builder.repository_evidence(mixed),
             self.receipt("S17-EXT-005", manifest)],
            summary,
        )

    def ext006(self) -> None:
        contract = self.root / "evidence/synthetic-ext006-contract-v4.json"
        contract.parent.mkdir(parents=True, exist_ok=True)
        write(contract, release_artifact.build_contract_v4(
            repository_root=self.root, archive=self.bundle_archive,
            sidecar=self.bundle_sidecar,
            primary_custody_domain_id="SYNTHETIC-CUSTODY-A",
            secondary_custody_domain_id="SYNTHETIC-CUSTODY-B",
            contract_id="SYNTHETIC-EXT006-CONTRACT-v4-TEST-ONLY",
        ))
        receipt = self.receipt("S17-EXT-006", self.bundle_archive,
                               contract=contract, sidecars=[self.bundle_sidecar],
                               verifier_id="STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER",
                               verifier_version="4")
        self.builder.pilot_archive = self.bundle_archive
        self.builder.pilot_sidecar = self.bundle_sidecar
        self.add("S17-EXT-006", [receipt])
        self.builder.add_transition()

    def ext007(self) -> None:
        directory = self.external / "ext007"; directory.mkdir(mode=0o700)
        validation = self.validate()
        q15w = validation.resolutions["S17-EXT-005"].semantic_context["q15_w"]
        hardware = {
            "mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
            "q15_w_result_sha256": q15w["result_sha256"],
            "prestate": q15w["request"]["action_inputs"]["prestate"],
        }
        captures = []
        context = 0
        for state in ("H0", "H1"):
            for placement in ("NEAR", "FAR"):
                for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"):
                    for repetition in range(59):
                        captures.append({
                            "context_ordinal": context,
                            "repetition_ordinal": repetition,
                            "hardware_state": state, "placement": placement,
                            "working_set_class": working_set,
                            "seed_id": f"SYNTHETIC-Q16A-{context:02d}-{repetition:03d}",
                            "calibration_plan_sha256": "0" * 64,
                        })
                    context += 1
        q16a_plan = hashlib.sha256(canonical([
            {key: value for key, value in item.items()
             if key != "calibration_plan_sha256"} for item in captures
        ])).hexdigest()
        for item in captures:
            item["calibration_plan_sha256"] = q16a_plan
        q16a = self.action(
            "Q16a", {"plan_sha256": q16a_plan,
                     "hardware_control": hardware, "captures": captures},
            directory / "q16a",
        )

        def runs_for(action_id: str, q16a_hash: str,
                     q16b_hash: str | None = None) -> tuple[str, list[dict[str, Any]]]:
            rows = []
            ordinal = 0
            for state in ("H0", "H1"):
                for package in ("R0", "R1", "R2", "L0", "L1"):
                    for placement in ("NEAR", "FAR"):
                        for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"):
                            for load in (("L025", "L050", "L075")
                                         if action_id == "Q16c" else (None,)):
                                repetitions = 1 if action_id == "Q16c" else 59
                                for repetition in range(repetitions):
                                    run = {
                                        "run_id": f"SYNTHETIC-{action_id}-{ordinal:03d}-{repetition:03d}",
                                        "cell_ordinal": ordinal,
                                        "repetition_ordinal": repetition,
                                        "package": package, "hardware_state": state,
                                        "placement": placement,
                                        "working_set_class": working_set,
                                        "plan_sha256": "0" * 64,
                                        "q16a_result_sha256": q16a_hash,
                                        "schedule_sha256": hashlib.sha256(
                                            f"{action_id}:{ordinal}:{repetition}".encode()
                                        ).hexdigest(),
                                        "seed_id": f"SYNTHETIC-{action_id}-SEED-{ordinal:03d}-{repetition:03d}",
                                        "runner_admission_sha256": "8" * 64,
                                        "offered_count": 4,
                                    }
                                    if load is not None:
                                        run["load_level"] = load
                                    if q16b_hash is not None:
                                        run["q16b_result_sha256"] = q16b_hash
                                    rows.append(run)
                                ordinal += 1
            plan = hashlib.sha256(canonical([
                {key: value for key, value in row.items() if key != "plan_sha256"}
                for row in rows
            ])).hexdigest()
            for row in rows:
                row["plan_sha256"] = plan
            return plan, rows

        q16a_hash = digest(q16a["result"])
        q16b_plan, q16b_runs = runs_for("Q16b", q16a_hash)
        q16b = self.action(
            "Q16b", {"plan_sha256": q16b_plan,
                     "q16a_result_sha256": q16a_hash,
                     "hardware_control": hardware, "runs": q16b_runs},
            directory / "q16b",
        )
        q16b_hash = digest(q16b["result"])
        q16c_plan, q16c_runs = runs_for("Q16c", q16a_hash, q16b_hash)
        q16c = self.action(
            "Q16c", {"plan_sha256": q16c_plan,
                     "q16a_result_sha256": q16a_hash,
                     "q16b_result_sha256": q16b_hash,
                     "hardware_control": hardware, "runs": q16c_runs},
            directory / "q16c",
        )
        artifacts = []
        for token, action in (("Q16A", q16a), ("Q16B", q16b), ("Q16C", q16c)):
            artifacts.extend(self.phase_artifacts(
                directory, token, action, include_completion=True
            ))
        results = {"Q16a": q16a_hash, "Q16b": q16b_hash,
                   "Q16c": digest(q16c["result"])}
        freeze = directory / "calibration-freeze-v1.json"
        sources = [{"artifact_id": f"EXT007-{name}-RESULT",
                    "sha256": results[name]}
                   for name in ("Q16a", "Q16b", "Q16c")]
        write(freeze, {
            "schema_version": "cpu-prefetch-calibration-freeze/1",
            "protocol_version": "2.0.0-pre.2",
            "record_id": "SYNTHETIC-STAGE17-CALIBRATION-FREEZE-v1",
            "state": "FROZEN", "owner_ids": ["synthetic-stage17-owner"],
            "authority": {
                "artifact_id": "EXT007-Q16C-AUTHORIZATION",
                "sha256": digest(q16c["authorization"]),
            },
            "decided_at_utc": legacy.utc(7),
            "source_records": sources,
            "invalidation_fingerprint_sha256": hashlib.sha256(
                canonical(sources)
            ).hexdigest(),
            "proposed_outputs": [
                {"name": "mu_ref", "value": "1/1", "unit": "events_per_tick"},
                {"name": "d2", "value": "2", "unit": "cache_lines"},
            ],
            "unresolved_inputs": [], "supersedes_record_id": None,
            "record_sha256": hashlib.sha256(canonical(results)).hexdigest(),
        })
        artifacts.append(self.artifact(
            directory, "EXT007-CALIBRATION-FREEZE", "CALIBRATION_FREEZE", freeze,
            schema="config/schemas/calibration-freeze-v1.schema.json",
        ))
        manifest = self.manifest("S17-EXT-007", directory, artifacts, self.predecessors(6))
        self.add("S17-EXT-007", [self.receipt("S17-EXT-007", manifest)])

    def ext008(self) -> None:
        directory = self.root / "evidence/ext008-v4"
        directory.mkdir(parents=True)
        validation = self.validate()
        ext6 = validation.resolutions["S17-EXT-006"].semantic_context
        ext5 = validation.resolutions["S17-EXT-005"].semantic_context
        ext4_index = validation.resolutions["S17-EXT-004"].semantic_context[
            "artifact_index"
        ]
        ext7_index = validation.resolutions["S17-EXT-007"].semantic_context[
            "artifact_index"
        ]
        source_bindings = {
            "mu_ref": {
                "artifact_id": "EXT007-CALIBRATION-FREEZE",
                "sha256": ext7_index["EXT007-CALIBRATION-FREEZE"]["sha256"],
            },
            "capacity": {
                "artifact_id": "EXT004-PILOT-PLATFORM",
                "sha256": ext4_index["EXT004-PILOT-PLATFORM"]["sha256"],
            },
            "topology": {
                "artifact_id": "EXT004-PILOT-PLATFORM",
                "sha256": ext4_index["EXT004-PILOT-PLATFORM"]["sha256"],
            },
        }
        plan, _ = pilot_plan_builder.plan_fixture(
            2, resolutions=validation.resolutions,
            source_revision=ext6["source_revision"],
            worker_sha256=ext6["release_artifact_sha256"],
            q15_w_result_sha256=ext5["q15_w"]["result_sha256"],
            q15_prestate=ext5["q15_w"]["request"]["action_inputs"]["prestate"],
            source_bindings=source_bindings,
        )
        plan_path = directory / "stage17-pilot-plan-v4.json"
        write(plan_path, plan)
        manifest = self.manifest("S17-EXT-008", directory, [
            self.artifact(
                directory, "EXT008-PILOT-PLAN-V4", "PILOT_PLAN_V4",
                plan_path, schema="config/schemas/stage17-pilot-plan-v4.schema.json",
            ),
        ], self.predecessors(7))
        self.add("S17-EXT-008", [self.builder.repository_evidence(manifest)])

    def ext009(self) -> None:
        directory = self.external / "ext009"; directory.mkdir(mode=0o700)
        predecessor = self.builder.resolutions["S17-EXT-008"]
        common = [self.source(predecessor[1]["resolution_id"], predecessor[0])]
        domain_a, domain_b = directory / "custody-a", directory / "custody-b"
        domain_a.mkdir(mode=0o700); domain_b.mkdir(mode=0o700)
        source = directory / "source-copy.bin"; source.write_bytes(b"synthetic-custody-copy")
        primary, secondary = domain_a / "pilot-copy.bin", domain_b / "pilot-copy.bin"
        shutil.copyfile(source, primary); shutil.copyfile(source, secondary)
        failure_fixture = directory / "recovery-failure.bin"
        restored = directory / "recovery-restored.bin"
        failure_fixture.write_bytes(b"synthetic-recovery")
        shutil.copyfile(failure_fixture, restored)
        plan_sha = self.validate().resolutions[
            "S17-EXT-008"
        ].semantic_context["pilot_plan_sha256"]
        records = [
            ("EXT009-BUDGET", "STORAGE_BUDGET", {"planned_bytes": 1024, "available_bytes": 4096, "temporary_copies": 1, "durable_copies": 2, "budget_formula_id": "STAGE11-BUDGET-v1", "pilot_plan_sha256": plan_sha}),
            ("EXT009-CUSTODY-A", "CUSTODY_DOMAIN", {"domain_id": "A", "locator": str(domain_a), "owner_uid": os.getuid(), "mode": "0700", "independent_domain_id": "B"}),
            ("EXT009-CUSTODY-B", "CUSTODY_DOMAIN", {"domain_id": "B", "locator": str(domain_b), "owner_uid": os.getuid(), "mode": "0700", "independent_domain_id": "A"}),
            ("EXT009-LEDGER", "COPY_LEDGER", {"source_locator": str(source), "source_sha256": digest(source), "primary_copy_locator": str(primary), "primary_copy_sha256": digest(primary), "secondary_copy_locator": str(secondary), "secondary_copy_sha256": digest(secondary), "transfer_verified_at_utc": legacy.utc(4)}),
            ("EXT009-RECOVERY", "RECOVERY_TEST", {"failure_fixture_locator": str(failure_fixture), "failure_fixture_sha256": digest(failure_fixture), "restored_locator": str(restored), "restored_sha256": digest(restored), "recovery_procedure_id": "SYNTHETIC-RECOVERY", "result_code": "PASS"}),
        ]
        artifacts = []
        for artifact_id, role, values in records:
            path = self.typed(directory, artifact_id, role, values, common, outcome="VERIFIED")
            artifacts.append(self.artifact(directory, artifact_id, role, path, schema=semantics.TYPED_SCHEMA))
        manifest = self.manifest("S17-EXT-009", directory, artifacts, self.predecessors(8))
        index = self.root / "evidence/ext009-mixed-index.json"
        write(index, {"schema_version": "cpu-prefetch-stage17-mixed-evidence-index/2", "input_id": "S17-EXT-009", "manifest_sha256": digest(manifest), "synthetic_test_only": True, "phase18_authority": False})
        self.add("S17-EXT-009", [self.builder.repository_evidence(index), self.receipt("S17-EXT-009", manifest)])

    def ext010(self) -> None:
        directory = self.root / "evidence/ext010-v4"; directory.mkdir(parents=True)
        validation = self.validate()
        registry = output_registry.pin_registry(self.root)
        definition = registry.action("STAGE17-BLINDED-PILOT")
        predecessors = [{"input_id": item,
                         "resolution_id": validation.resolutions[item].resolution_id,
                         "sha256": validation.resolutions[item].sha256}
                        for item in definition["required_resolution_ids"]]
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        request_placeholder = directory / "pilot-request-v4.json"
        pilot_output = self.external / "future-pilot-output"
        pilot_output.mkdir(mode=0o700)
        plan = validation.resolutions["S17-EXT-008"].semantic_context["pilot_plan"]
        runtime, release = controller._runtime_from_context(
            "STAGE17-BLINDED-PILOT", validation
        )
        meta = pilot_output.stat()
        root_binding = {"absolute_path": str(pilot_output.resolve()),
                        "device": meta.st_dev, "inode": meta.st_ino,
                        "owner_uid": meta.st_uid,
                        "mode": f"{meta.st_mode & 0o7777:04o}"}
        request = {
            "schema_version": "cpu-prefetch-stage17-fixed-action-request/4",
            "request_id": "SYNTHETIC-PILOT-REQUEST-v4",
            "session_id": "SYNTHETIC-PILOT-SESSION-v4",
            "action_id": "STAGE17-BLINDED-PILOT",
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
            "authorization_id": "SYNTHETIC-PILOT-AUTH-v4",
            "attempt_id": "SYNTHETIC-PILOT-ATTEMPT-v4",
            "runtime_binding": {key: runtime[key] for key in
                                ("role", "profile", "size_bytes", "sha256")},
            "release_binding": release,
            "evidence_root_binding": root_binding,
            "predecessor_resolutions": predecessors,
            "action_inputs": {
                "plan_sha256": validation.resolutions[
                    "S17-EXT-008"
                ].semantic_context["pilot_plan_sha256"],
                "pilot_plan": plan,
            },
            "synthetic_test_only": True, "phase18_authority": False,
        }
        write(request_placeholder, request)
        ext2, ext3 = validation.resolutions["S17-EXT-002"], validation.resolutions["S17-EXT-003"]
        authorization = {
            "schema_version": "cpu-prefetch-stage17-phase-action-authorization/4",
            "authorization_id": request["authorization_id"],
            "session_id": request["session_id"],
            "action_id": "STAGE17-BLINDED-PILOT",
            "actor": "synthetic-stage17-owner",
            "reviewer": "OWNER_AUDITOR_COLLAPSED",
            "target": {"stand_id": request["stand_id"]},
            "issued_at_utc": (now - dt.timedelta(seconds=10)).isoformat().replace("+00:00", "Z"),
            "expires_at_utc": (now + dt.timedelta(seconds=300)).isoformat().replace("+00:00", "Z"),
            "trust_context": {
                "ext002_resolution": {"input_id": ext2.input_id,
                                      "resolution_id": ext2.resolution_id,
                                      "sha256": ext2.sha256},
                "ext003_resolution": {"input_id": ext3.input_id,
                                      "resolution_id": ext3.resolution_id,
                                      "sha256": ext3.sha256},
            },
            "predecessor_resolutions": predecessors,
            "fixed_action_definition_sha256": registry.plan_sha256,
            "request_binding": {"path": str(request_placeholder),
                                "size_bytes": request_placeholder.stat().st_size,
                                "sha256": digest(request_placeholder)},
            "evidence_root_binding": root_binding,
            "permission_matrix": definition["permission_matrix"],
            "deadline_policy": {
                "mode": "DURABLE_PILOT_SESSION",
                "per_run_max_wall_seconds": 180,
                "session_max_wall_seconds": (
                    180 * 180 * plan["repetitions_per_cell"]
                    + ((plan["recovery"]["duration_ticks"] + 999_999_999_999)
                       // 1_000_000_000_000)
                    * max(plan["repetitions_per_cell"] - 1, 0) + 180
                ),
                "implicit_extension": False,
                "partial_session_completes": False,
            },
            "one_attempt": True,
            "retry_allowed": False, "stop_first": True,
            "retain_partial": True, "stage18_authority": False,
        }
        auth = directory / "pilot-authorization-v4.json"; write(auth, authorization)
        signature = self._sign(auth)
        auth_artifact = self.artifact(directory, "EXT010-AUTH", "PILOT_AUTHORIZATION", auth, schema=semantics.AUTH_SCHEMA)
        request_artifact = self.artifact(directory, "EXT010-REQUEST", "PILOT_REQUEST",
                                         request_placeholder,
                                         schema=semantics.REQUEST_SCHEMA)
        sig_artifact = self.artifact(directory, "EXT010-SIGNATURE", "PILOT_SIGNATURE", signature, lineage=[{"id": "EXT010-AUTH", "sha256": digest(auth)}])
        manifest = self.manifest("S17-EXT-010", directory,
                                 [auth_artifact, request_artifact, sig_artifact],
                                 self.predecessors(9))
        summary = {"authorization_id": authorization["authorization_id"],
                   "evidence_path": auth.relative_to(self.root).as_posix(),
                   "issued_at_utc": authorization["issued_at_utc"],
                   "expires_at_utc": authorization["expires_at_utc"],
                   "authority_scope": "STAGE17_PILOT_PHASE_ONLY"}
        self.add("S17-EXT-010", [self.builder.repository_evidence(manifest)], summary)

    def execute_pilot(self) -> dict[str, Any]:
        directory = self.root / "evidence/ext010-v4"
        authorization_path = directory / "pilot-authorization-v4.json"
        authorization = json.loads(authorization_path.read_text())
        request_path = pathlib.Path(authorization["request_binding"]["path"])
        request = json.loads(request_path.read_text())
        output_root = pathlib.Path(
            request["evidence_root_binding"]["absolute_path"]
        )
        self.builder._cli(
            "execute-action", "--authorization",
            str(authorization_path),
            "--signature", str(directory / "pilot-authorization-v4.json.sig"),
        )
        attempt = output_root / "stage17-stage17_blinded_pilot-attempt-v4.json"
        result = output_root / output_registry.RESULT_NAME
        completion = output_root / "stage17-stage17_blinded_pilot-completion-v4.json"
        for path in (attempt, result, completion):
            if not path.is_file():
                raise CheckError(f"public pilot CLI omitted output: {path.name}")
        self.positive_actions += 1
        return {
            "authorization": directory / "pilot-authorization-v4.json",
            "attempt": attempt, "result": result,
            "completion": completion,
            "result_document": json.loads(result.read_text()),
        }

    def build(self) -> journal.OperationalJournalValidation:
        self.ext001(); self.ext002(); self.ext003(); self.ext004_and_ext005(); self.ext006()
        self.ext007(); self.ext008(); self.ext009(); self.ext010()
        return self.validate(
            as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
        )


def expect_failure(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except BaseException:
        print(f"stage17-fixed-production: PASS negative={label}")
        return
    raise CheckError(f"negative fixture was admitted: {label}")


def file_binding(path: pathlib.Path) -> dict[str, Any]:
    return {"path": str(path), "size_bytes": path.stat().st_size,
            "sha256": digest(path)}


def _sign_with(key: pathlib.Path, namespace: str,
               document: pathlib.Path) -> pathlib.Path:
    completed = subprocess.run(
        ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(key), "-n",
         namespace, str(document)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=10,
    )
    signature = pathlib.Path(str(document) + ".sig")
    if completed.returncode != 0 or not signature.is_file():
        raise CheckError("synthetic SSHSIG creation failed")
    return signature


def exercise_exit_and_phase18(
    fixture: Fixture, validation: journal.OperationalJournalValidation,
    pilot: dict[str, Any],
) -> tuple[int, int]:
    """Derive Stage 17 completion and prove the separate Phase 18 root."""
    directory = fixture.external / "stage17-exit-v4"
    directory.mkdir(mode=0o700)
    completion_path = directory / "stage17-completion-v4.json"
    fixture.builder._cli(
        "derive-stage17-completion", "--pilot-output-root",
        str(pilot["result"].parent), "--output", str(completion_path),
    )
    completion_document = json.loads(completion_path.read_text())
    completion = exit_machine.Stage17CompletionContext(
        completion_document, completion_path.read_bytes(), {}
    )

    phase = directory / "phase18-preparation"
    phase.mkdir(mode=0o700)
    independent_key = phase / "independent-ed25519"
    subprocess.run(
        ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f",
         str(independent_key)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True, timeout=10,
    )
    public = pathlib.Path(str(independent_key) + ".pub").read_text().strip()
    allowed = phase / "independent-allowed-signers"
    allowed.write_text(f"synthetic-phase18-owner {public}\n", encoding="ascii")
    allowed.chmod(0o600)
    ext3 = validation.resolutions["S17-EXT-003"]
    trust_context = ext3.semantic_context["trust"]
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    fingerprint_output = subprocess.run(
        ["/usr/bin/ssh-keygen", "-lf", str(independent_key) + ".pub", "-E", "sha256"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=10,
    ).stdout.decode().split()[1]
    anchor = {
        "schema_version": "cpu-prefetch-phase18-external-trust-anchor/4",
        "anchor_id": "SYNTHETIC-INDEPENDENT-PHASE18-ANCHOR-v4",
        "allowed_signers": file_binding(allowed),
        "public_key_fingerprint_sha256": fingerprint_output,
        "principal": "synthetic-phase18-owner",
        "namespace": "cpu-prefetch-phase18-access-v4",
        "signer_role": "SYNTHETIC-INDEPENDENT-PHASE18-SIGNER",
        "reviewer_role": "SYNTHETIC-INDEPENDENT-PHASE18-REVIEWER",
        "custody_approval_id": "SYNTHETIC-INDEPENDENT-CUSTODY-v4",
        "independent_from_stage17": True,
        "admitted_at_utc": now.isoformat().replace("+00:00", "Z"),
        "phase18_authority": False,
    }
    anchor_path = phase / "phase18-external-trust-anchor-v4.json"
    write(anchor_path, anchor)
    trust = exit_machine.admit_phase18_trust(
        repository_root=fixture.root, operational_validation=validation,
        anchor_path=anchor_path, expected_anchor_id=anchor["anchor_id"],
        expected_anchor_sha256=digest(anchor_path),
        expected_public_key_fingerprint=fingerprint_output,
    )
    readiness_path = phase / "phase18-readiness-v4.json"
    fixture.builder._cli(
        "prepare-phase18-readiness", "--stage17-completion",
        str(completion_path), "--created-at-utc",
        now.isoformat().replace("+00:00", "Z"), "--output",
        str(readiness_path),
    )
    readiness = json.loads(readiness_path.read_text())
    if readiness["state"] != "BLOCKED_EXTERNAL_PHASE18_TRUST_REQUIRED":
        raise CheckError("public readiness CLI self-enrolled Phase 18 trust")
    readiness = exit_machine.phase18_readiness(
        repository_root=fixture.root, completion=completion, trust=trust,
        created_at_utc=now.isoformat().replace("+00:00", "Z"),
    )
    # An independently admitted trust root permits a separately signed
    # readiness successor; the public no-trust command above remains blocked.
    write(readiness_path.with_name("phase18-ready-with-trust-v4.json"), readiness)
    authorization = {
        "schema_version": "cpu-prefetch-phase18-authorization/4",
        "authorization_id": "SYNTHETIC-PHASE18-AUTHORIZATION-v4",
        "actor": anchor["principal"],
        "reviewer": anchor["reviewer_role"],
        "external_trust_anchor_sha256": digest(anchor_path),
        "public_key_fingerprint_sha256": fingerprint_output,
        "stage17_completion_sha256": hashlib.sha256(
            completion.payload
        ).hexdigest(),
        "readiness_sha256": hashlib.sha256(
            exit_machine.canonical(readiness)
        ).hexdigest(),
        "issued_at_utc": (now - dt.timedelta(seconds=5)).isoformat().replace(
            "+00:00", "Z"
        ),
        "expires_at_utc": (now + dt.timedelta(minutes=10)).isoformat().replace(
            "+00:00", "Z"
        ),
        "allowed_chronology": list(exit_machine.PHASE18_STATES),
        "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY",
        "stage17_authority_reuse_allowed": False,
        "automatic_transition": False, "retry_allowed": False,
    }
    authorization_path = phase / "phase18-authorization-v4.json"
    write(authorization_path, authorization)
    signature = _sign_with(
        independent_key, anchor["namespace"], authorization_path
    )
    admitted = exit_machine.validate_phase18_authorization(
        repository_root=fixture.root, completion=completion, trust=trust,
        readiness=readiness, authorization_path=authorization_path,
        signature_path=signature,
        actual_utc=now.isoformat().replace("+00:00", "Z"),
    )
    transitions: list[tuple[pathlib.Path, pathlib.Path]] = []
    previous = "0" * 64
    for sequence, (source, target) in enumerate(
        zip(exit_machine.PHASE18_STATES, exit_machine.PHASE18_STATES[1:]), 1
    ):
        transition = {
            "schema_version": "cpu-prefetch-phase18-access-transition/4",
            "sequence_number": sequence, "from_state": source,
            "to_state": target, "previous_transition_sha256": previous,
            "authorization_id": admitted["authorization_id"],
            "authorization_sha256": digest(authorization_path),
            "evidence_sha256s": [f"{sequence:064x}"],
            "actor": anchor["principal"], "reviewer": anchor["reviewer_role"],
            "timestamp_utc": now.isoformat().replace("+00:00", "Z"),
            "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY",
            "stage17_authority_used": False, "automatic_transition": False,
            "retry_allowed": False,
        }
        path = phase / f"phase18-transition-{sequence:02d}-v4.json"
        write(path, transition)
        transition_signature = _sign_with(independent_key, anchor["namespace"], path)
        transitions.append((path, transition_signature))
        previous = digest(path)
    if exit_machine.validate_phase18_chronology(
            repository_root=fixture.root, trust=trust,
            authorization=admitted, authorization_payload=authorization_path.read_bytes(),
            transitions=transitions,
            actual_utc=now.isoformat().replace("+00:00", "Z")) != "ARCHIVED":
        raise CheckError("independently authorized Phase 18 chronology failed")

    negative = 0
    saved = signature.read_bytes()
    signature.write_bytes(b"UNSIGNED\n")
    expect_failure(
        "phase18_unsigned_authority",
        lambda: exit_machine.validate_phase18_authorization(
            repository_root=fixture.root, completion=completion, trust=trust,
            readiness=readiness, authorization_path=authorization_path,
            signature_path=signature,
            actual_utc=now.isoformat().replace("+00:00", "Z"),
        ),
    )
    signature.write_bytes(saved); negative += 1
    expect_failure(
        "phase18_expired_authority",
        lambda: exit_machine.validate_phase18_authorization(
            repository_root=fixture.root, completion=completion, trust=trust,
            readiness=readiness, authorization_path=authorization_path,
            signature_path=signature,
            actual_utc=(now + dt.timedelta(days=1)).isoformat().replace(
                "+00:00", "Z"
            ),
        ),
    ); negative += 1
    same_anchor = copy.deepcopy(anchor)
    stage17_allowed = pathlib.Path(
        trust_context["measurements"]["allowed_signers_path"]
    )
    same_anchor["allowed_signers"] = file_binding(stage17_allowed)
    same_path = phase / "self-rooted-anchor-v4.json"
    write(same_path, same_anchor)
    expect_failure(
        "phase18_coherently_self_rooted_chain",
        lambda: exit_machine.admit_phase18_trust(
            repository_root=fixture.root, operational_validation=validation,
            anchor_path=same_path, expected_anchor_id=anchor["anchor_id"],
            expected_anchor_sha256=digest(anchor_path),
            expected_public_key_fingerprint=fingerprint_output,
        ),
    ); negative += 1
    reordered_path = phase / "phase18-reordered-v4.json"
    reordered_document = json.loads(transitions[0][0].read_text())
    reordered_document["to_state"] = "TRAINING_OPEN"
    write(reordered_path, reordered_document)
    reordered = [(reordered_path, _sign_with(
        independent_key, anchor["namespace"], reordered_path
    ))] + transitions[1:]
    expect_failure(
        "phase18_chronology_skip",
        lambda: exit_machine.validate_phase18_chronology(
            repository_root=fixture.root, trust=trust, authorization=admitted,
            authorization_payload=authorization_path.read_bytes(),
            transitions=reordered,
            actual_utc=now.isoformat().replace("+00:00", "Z"),
        ),
    ); negative += 1
    reuse_path = phase / "phase18-stage17-reuse-v4.json"
    reuse_document = json.loads(transitions[0][0].read_text())
    reuse_document["stage17_authority_used"] = True
    write(reuse_path, reuse_document)
    stage17_reuse = [(reuse_path, _sign_with(
        independent_key, anchor["namespace"], reuse_path
    ))] + transitions[1:]
    expect_failure(
        "phase18_stage17_authority_reuse",
        lambda: exit_machine.validate_phase18_chronology(
            repository_root=fixture.root, trust=trust, authorization=admitted,
            authorization_payload=authorization_path.read_bytes(),
            transitions=stage17_reuse,
            actual_utc=now.isoformat().replace("+00:00", "Z"),
        ),
    ); negative += 1
    return 4, negative


def _manifest_path(fixture: Fixture, input_id: str) -> pathlib.Path:
    if input_id in {"S17-EXT-003", "S17-EXT-008", "S17-EXT-010"}:
        return fixture.root / "evidence" / {
            "S17-EXT-003": "ext003-v4/s17-ext-003-manifest-v4.json",
            "S17-EXT-008": "ext008-v4/s17-ext-008-manifest-v4.json",
            "S17-EXT-010": "ext010-v4/s17-ext-010-manifest-v4.json",
        }[input_id]
    return fixture.external / {
        "S17-EXT-002": "ext002/s17-ext-002-manifest-v4.json",
        "S17-EXT-004": "q15-session/s17-ext-004-manifest-v4.json",
        "S17-EXT-005": "q15-session/s17-ext-005-manifest-v4.json",
        "S17-EXT-007": "ext007/s17-ext-007-manifest-v4.json",
        "S17-EXT-009": "ext009/s17-ext-009-manifest-v4.json",
    }[input_id]


def semantic_regressions(
    fixture: Fixture, validation: journal.OperationalJournalValidation,
    pilot: dict[str, Any],
) -> int:
    negative = 0

    def verify_manifest(input_id: str) -> dict[str, Any]:
        ordinal = int(input_id[-3:])
        admitted = {
            key: value for key, value in validation.resolutions.items()
            if int(key[-3:]) < ordinal
        }
        pinned = semantic_registry.pinned_policy_bytes(fixture.root)
        return semantics.verify_manifest_v4(
            repository_root=fixture.root,
            manifest_path=_manifest_path(fixture, input_id),
            admitted_resolutions=admitted, expected_input_id=input_id,
            allow_synthetic=True, pinned_repository_bytes=pinned,
        )

    ext2 = _manifest_path(fixture, "S17-EXT-002")
    ext2_document = json.loads(ext2.read_text())
    worker_reference = next(
        item for item in ext2_document["artifacts"]
        if item["role"] == "RUNTIME_WORKER_BINARY"
    )
    worker_path = ext2.parent / worker_reference["locator"]
    worker_saved = worker_path.read_bytes()
    manifest_saved = ext2.read_bytes()
    malicious = pathlib.Path("/bin/true").read_bytes() + (
        b"\0--execute-fixed-stage17-action-v4\0"
        b"STAGE17-FIXED-ACTION-WORKER-v4\0"
    )
    worker_path.write_bytes(malicious); worker_path.chmod(0o700)
    worker_reference.update({"size_bytes": len(malicious),
                             "sha256": hashlib.sha256(malicious).hexdigest()})
    write(ext2, ext2_document)
    expect_failure("marker_bearing_adversarial_elf", lambda: verify_manifest(
        "S17-EXT-002"
    )); negative += 1
    worker_path.write_bytes(worker_saved); worker_path.chmod(0o755)
    ext2.write_bytes(manifest_saved)

    ext8 = _manifest_path(fixture, "S17-EXT-008")
    ext8_document = json.loads(ext8.read_text())
    plan_reference = ext8_document["artifacts"][0]
    plan_path = ext8.parent / plan_reference["locator"]
    plan_saved, ext8_saved = plan_path.read_bytes(), ext8.read_bytes()
    plan_document = json.loads(plan_saved)
    plan_document["cells"] = plan_document["cells"][:1]
    write(plan_path, plan_document)
    plan_reference.update({"size_bytes": plan_path.stat().st_size,
                           "sha256": digest(plan_path)})
    write(ext8, ext8_document)
    expect_failure("one_cell_pilot_plan", lambda: verify_manifest(
        "S17-EXT-008"
    )); negative += 1
    plan_path.write_bytes(plan_saved); ext8.write_bytes(ext8_saved)

    ext5 = _manifest_path(fixture, "S17-EXT-005")
    ext5_document = json.loads(ext5.read_text())
    q15w_reference = next(item for item in ext5_document["artifacts"]
                          if item["role"] == "Q15_W_TRANSACTION")
    q15w_path = ext5.parent / q15w_reference["locator"]
    q15w_saved, ext5_saved = q15w_path.read_bytes(), ext5.read_bytes()
    q15w_document = json.loads(q15w_saved)
    q15w_document["live_prestate_matches"] = False
    write(q15w_path, q15w_document)
    q15w_reference.update({"size_bytes": q15w_path.stat().st_size,
                           "sha256": digest(q15w_path)})
    write(ext5, ext5_document)
    expect_failure("q15w_stale_live_msr_prestate", lambda: verify_manifest(
        "S17-EXT-005"
    )); negative += 1
    q15w_path.write_bytes(q15w_saved); ext5.write_bytes(ext5_saved)

    ext7 = _manifest_path(fixture, "S17-EXT-007")
    ext7_saved = ext7.read_bytes()
    ext7_document = json.loads(ext7_saved)
    output_reference = next(item for item in ext7_document["artifacts"]
                            if item["role"] == "Q16A_RING_DEMAND_TRACE")
    output_reference["schema_identity"] = "cpu-prefetch-stage17-run-output/4"
    write(ext7, ext7_document)
    expect_failure("swapped_action_output_schema", lambda: verify_manifest(
        "S17-EXT-007"
    )); negative += 1
    ext7.write_bytes(ext7_saved)

    schema = fixture.root / semantics.REQUEST_SCHEMA
    schema_saved = schema.read_bytes()
    schema_mode = schema.stat().st_mode
    schema.chmod(0o600)
    try:
        schema.write_bytes(schema_saved + b"\n")
        expect_failure(
            "preload_schema_policy_drift",
            lambda: fixture.validate(
                as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                    "+00:00", "Z"
                )
            ),
        ); negative += 1
    finally:
        schema.write_bytes(schema_saved)
        schema.chmod(schema_mode)

    result_saved = pilot["result"].read_bytes()
    result_document = json.loads(result_saved)
    result_document["request_sha256"] = "f" * 64
    write(pilot["result"], result_document)
    expect_failure(
        "forged_stage17_exit_lineage",
        lambda: exit_machine.validate_stage17_completion(
            repository_root=fixture.root, operational_validation=validation,
            pilot_output_root=pilot["result"].parent,
            synthetic_test_only=True,
        ),
    ); negative += 1
    pilot["result"].write_bytes(result_saved)

    expect_failure(
        "rejected_fail_open_controller_v1",
        lambda: rejected_controller.execute_once(
            repository_root=fixture.root, journal=pathlib.Path("missing"),
            journal_directory=pathlib.Path("missing"),
            authorization_path=pathlib.Path("missing"),
            signature_path=pathlib.Path("missing"),
        ),
    ); negative += 1
    return negative


def run_hermetic_workflow(
    worker: pathlib.Path, no_result_worker: pathlib.Path,
    bundle_root: pathlib.Path, bundle_archive: pathlib.Path,
    bundle_sidecar: pathlib.Path,
) -> tuple[int, int]:
    del no_result_worker  # predecessor runtime suites retain the rc=0 negative.
    positive = 0
    negative = 0
    with tempfile.TemporaryDirectory(
        prefix="stage17-fixed-production-"
    ) as temporary:
        fixture = Fixture(
            pathlib.Path(temporary), worker, bundle_root,
            bundle_archive, bundle_sidecar,
        )
        validation = fixture.build()
        if (validation.current_state, validation.resolution_count,
                validation.transition_count, validation.pilot_ready) != (
                "READY_FOR_STAGE17_PHASE_AUTHORIZATION", 10, 3, True):
            raise CheckError("ten-input/three-transition semantic admission failed")
        positive += 1
        pilot = fixture.execute_pilot()
        if (pilot["result_document"]["action_id"]
                != "STAGE17-BLINDED-PILOT"):
            raise CheckError("compiled fixed dispatcher did not execute pilot")
        if fixture.positive_actions != 6:
            raise CheckError("not all six compiled fixed actions executed")
        positive += fixture.positive_actions
        exit_positive, exit_negative = exercise_exit_and_phase18(
            fixture, validation, pilot
        )
        positive += exit_positive
        negative += exit_negative
        negative += semantic_regressions(fixture, validation, pilot)
        reloaded = fixture.validate(
            as_of_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
        )
        if (reloaded.resolution_count, reloaded.transition_count,
                reloaded.pilot_ready) != (10, 3, True):
            raise CheckError("disk-reloaded operational journal drifted")
        positive += 1
    return positive, negative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-hermetic-workflow", action="store_true", required=True)
    parser.add_argument("--worker", type=pathlib.Path, required=True)
    parser.add_argument("--no-result-worker", type=pathlib.Path, required=True)
    parser.add_argument("--bundle-root", type=pathlib.Path)
    parser.add_argument("--bundle-archive", type=pathlib.Path, required=True)
    parser.add_argument("--bundle-sidecar", type=pathlib.Path, required=True)
    args = parser.parse_args()
    args.worker = args.worker.resolve()
    args.no_result_worker = args.no_result_worker.resolve()
    args.bundle_archive = args.bundle_archive.resolve()
    args.bundle_sidecar = args.bundle_sidecar.resolve()
    extracted: tempfile.TemporaryDirectory | None = None
    if args.bundle_root is None:
        extracted = tempfile.TemporaryDirectory(
            prefix="stage17-hermetic-workflow-bundle-"
        )
        args.bundle_root = release_artifact._safe_extract(
            args.bundle_archive, pathlib.Path(extracted.name)
        )
    try:
        positive, negative = run_hermetic_workflow(
            args.worker, args.no_result_worker, args.bundle_root.resolve(),
            args.bundle_archive, args.bundle_sidecar,
        )
    except BaseException as exception:
        print(f"stage17-fixed-production: FAIL: {exception}", file=sys.stderr)
        traceback.print_exc()
        return 1
    finally:
        if extracted is not None:
            extracted.cleanup()
    print(
        "stage17-fixed-production: PASS "
        f"positive={positive} negative={negative} compiled_dispatch=true "
        "state_gate_mock=false checked_in_journal_untouched=true "
        "stand=NOT_ACCESSED"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
