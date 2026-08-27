#!/usr/bin/env python3
"""Synthetic end-to-end Stage 17B production semantic-admission suite.

All records and credentials are disposable, explicitly synthetic, and confined
to temporary directories.  The test invokes the production semantic registry;
it never calls validate_mechanics(), touches the checked-in journal, or opens a
network transport.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile
import types
from dataclasses import dataclass
from typing import Any, Callable

import stage17_state_journal as base_journal
import stage17_state_journal_v6 as journal
from stage17_exit_state_machine_v1 import (
    EXIT_GENESIS_SHA256, PHASE18_GENESIS_SHA256, canonical,
    sha, validate_exit_journal, validate_phase18_access_journal,
)
from stage17_operational_semantics_v1 import OBSERVATION_IDS


SOURCE_ROOT = pathlib.Path(__file__).resolve().parents[1]
BASE_TIME = "2030-01-01"
SHA_EMPTY = hashlib.sha256(b"").hexdigest()


class CheckError(RuntimeError):
    pass


def utc(minute: int) -> str:
    hour, minute = divmod(minute, 60)
    return f"{BASE_TIME}T{hour:02d}:{minute:02d}:00Z"


def write_json(path: pathlib.Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(document, sort_keys=True, indent=2).encode("utf-8") + b"\n")


def sha_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def binding(path: pathlib.Path, *, role: str, artifact_id: str, schema: str | None = None, media: str = "application/json") -> dict[str, Any]:
    return {
        "role": role, "artifact_id": artifact_id, "locator": str(path),
        "size_bytes": path.stat().st_size, "sha256": sha_file(path),
        "media_type": media, "schema_identity": schema,
    }


@dataclass
class ResolutionInfo:
    resolution_id: str
    sha256: str
    semantic_context: dict[str, Any]


class Builder:
    def __init__(self, base: pathlib.Path) -> None:
        self.base = base
        self.root = base / "repo"
        self.external = base / "external"
        self.root.mkdir()
        self.external.mkdir(mode=0o700)
        for directory in ("config", "tools", "docs", "protocol"):
            shutil.copytree(SOURCE_ROOT / directory, self.root / directory, symlinks=True)
        self.graph = json.loads((self.root / "config/stage17/stage17-operational-graph-definition-v1.json").read_text())
        self.catalog = json.loads((self.root / "config/stage17/stage17-external-input-catalog-v1.json").read_text())
        self.graph_sha = sha_file(self.root / "config/stage17/stage17-operational-graph-definition-v1.json")
        self.catalog_sha = sha_file(self.root / "config/stage17/stage17-external-input-catalog-v1.json")
        self.versions = base_journal.version_hashes(self.root)
        self.genesis_record = {
            "journal_id": "STAGE17-STATE-JOURNAL-v1", "protocol_version": "2.0.0-pre.2",
            "initial_state": "PREPARED", "graph_sha256": self.graph_sha,
            "catalog_sha256": self.catalog_sha, "version_hashes": self.versions,
            "authority_scope": "NO_EXECUTION_AUTHORITY",
        }
        self.genesis_sha = base_journal.sha256_bytes(base_journal.canonical_json_bytes(self.genesis_record))
        self.latest_path = self.root / "config/stage17/journal/stage17-state-journal-000000.json"
        self.latest = json.loads(self.latest_path.read_text())
        if self.latest["genesis"]["genesis_sha256"] != self.genesis_sha:
            raise CheckError("copied genesis does not match synthetic projection")
        self.resolutions: dict[str, tuple[pathlib.Path, dict[str, Any], str]] = {}
        self.contexts: dict[str, dict[str, Any]] = {}
        self.transition_count = 0
        self.previous_transition_sha = self.genesis_sha
        self.pilot_archive: pathlib.Path | None = None
        self.pilot_sidecar: pathlib.Path | None = None
        self.allowed_signers, self.signing_key = self._synthetic_signer()

    def _synthetic_signer(self) -> tuple[pathlib.Path, pathlib.Path]:
        directory = self.external / "synthetic-sshsig"
        directory.mkdir(mode=0o700)
        key = directory / "id_ed25519"
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if result.returncode != 0:
            raise CheckError("cannot create disposable synthetic Ed25519 fixture")
        public = subprocess.run(
            ["/usr/bin/ssh-keygen", "-y", "-f", str(key)], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=10,
        ).stdout.strip()
        allowed = directory / "allowed_signers"
        allowed.write_bytes(b"synthetic-stage17-owner " + public + b"\n")
        return allowed, key

    def append(self, kind: str, reference: dict[str, Any]) -> None:
        previous_path = self.latest_path
        document = copy.deepcopy(self.latest)
        sequence = document["journal_sequence_number"] + 1
        document["journal_sequence_number"] = sequence
        document["previous_journal"] = {
            "path": previous_path.relative_to(self.root).as_posix(),
            "sha256": sha_file(previous_path),
        }
        document[kind].append(reference)
        path = self.root / "config/stage17/journal" / f"stage17-state-journal-{sequence:06d}.json"
        write_json(path, document)
        self.latest, self.latest_path = document, path

    def repository_evidence(self, path: pathlib.Path) -> dict[str, Any]:
        return {"kind": "REPOSITORY_FILE", "path": path.relative_to(self.root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha_file(path)}

    def external_receipt(self, input_id: str, artifact: pathlib.Path, *, contract_path: pathlib.Path | None = None, sidecars: list[pathlib.Path] | None = None, verifier_id: str = "STAGE17-OPERATIONAL-MANIFEST-VERIFIER", verifier_version: str = "1") -> dict[str, Any]:
        contract_path = contract_path or self.root / "config/stage17/stage17-operational-input-external-contract-v1.json"
        receipt = {
            "schema_version": "cpu-prefetch-stage17-external-custody-receipt/1",
            "receipt_id": f"SYNTHETIC-{input_id}-RECEIPT", "artifact_locator": str(artifact),
            "artifact_size_bytes": artifact.stat().st_size, "artifact_sha256": sha_file(artifact),
            "sidecars": [{"locator": str(item), "size_bytes": item.stat().st_size, "sha256": sha_file(item)} for item in (sidecars or [])],
            "custody_domain_id": "SYNTHETIC-TEST-ONLY-CUSTODY", "verifier_id": verifier_id,
            "verifier_version": verifier_version, "verification_result": "PASS",
            "verified_at_utc": utc(len(self.resolutions) + 1),
            "contract_path": contract_path.relative_to(self.root).as_posix(),
            "contract_sha256": sha_file(contract_path),
        }
        path = self.root / "evidence" / f"{input_id.lower()}-receipt.json"
        write_json(path, receipt)
        return {"kind": "EXTERNAL_CUSTODY_RECEIPT", "receipt_path": path.relative_to(self.root).as_posix(), "receipt_size_bytes": path.stat().st_size, "receipt_sha256": sha_file(path)}

    def predecessor_bindings(self, stop: int, *, start: int = 1) -> list[dict[str, Any]]:
        return [
            {"input_id": input_id, "resolution_id": self.resolutions[input_id][1]["resolution_id"], "sha256": self.resolutions[input_id][2]}
            for input_id in (f"S17-EXT-{index:03d}" for index in range(start, stop + 1))
        ]

    def manifest(self, input_id: str, predecessors: list[dict[str, Any]], artifacts: list[dict[str, Any]], payload: dict[str, Any]) -> pathlib.Path:
        path = self.root / "evidence" / f"{input_id.lower()}-manifest-v1.json"
        write_json(path, {
            "schema_version": "cpu-prefetch-stage17-operational-input-manifest/1",
            "manifest_id": f"SYNTHETIC-{input_id}-MANIFEST-TEST-ONLY", "input_id": input_id,
            "protocol_version": "2.0.0-pre.2", "created_at_utc": utc(len(self.resolutions) + 1),
            "synthetic_test_only": True, "predecessor_resolutions": predecessors,
            "artifacts": artifacts, "payload": payload,
            "authority_expansion": False, "phase18_authority": False,
        })
        return path

    def add_resolution(self, input_id: str, evidence: list[dict[str, Any]], authorization: dict[str, Any] | None, context_hint: dict[str, Any]) -> None:
        sequence = len(self.resolutions) + 1
        document = {
            "schema_version": "cpu-prefetch-stage17-external-input-resolution/1",
            "resolution_id": f"SYNTHETIC-{input_id}-RESOLUTION-TEST-ONLY",
            "sequence_number": sequence, "input_id": input_id,
            "actor": "synthetic-stage17-owner", "recorded_at_utc": utc(sequence + 1),
            "graph_sha256": self.graph_sha, "catalog_sha256": self.catalog_sha,
            "version_hashes": self.versions, "evidence": evidence,
            "authorization": authorization, "verification_result": "PASS",
            "automatic_resolution": False, "retry_authority": False,
            "stage18_authority": False,
        }
        path = self.root / "records" / f"resolution-{sequence:03d}.json"
        write_json(path, document)
        digest = sha_file(path)
        self.append("resolution_records", {"path": path.relative_to(self.root).as_posix(), "sha256": digest})
        self.resolutions[input_id] = (path, document, digest)
        self.contexts[input_id] = context_hint

    def add_transition(self) -> None:
        sequence = self.transition_count + 1
        edge = self.graph["transitions"][sequence - 1]
        evidence = [
            {"input_id": item, "resolution_id": self.resolutions[item][1]["resolution_id"], "sha256": self.resolutions[item][2]}
            for item in edge["required_input_ids"]
        ]
        authorizations: list[dict[str, Any]] = []
        for item in edge["authorization_input_ids"]:
            summary = self.resolutions[item][1]["authorization"]
            authorizations.append({"input_id": item, "resolution_id": self.resolutions[item][1]["resolution_id"], "authorization_id": summary["authorization_id"], "authority_scope": summary["authority_scope"]})
        document = {
            "schema_version": "cpu-prefetch-stage17-state-transition/1",
            "transition_id": f"SYNTHETIC-STAGE17-TRANSITION-{sequence:03d}",
            "sequence_number": sequence, "from_state": edge["from_state"], "to_state": edge["to_state"],
            "previous_transition_sha256": self.previous_transition_sha,
            "actor": "synthetic-stage17-owner", "timestamp_utc": utc(20 + sequence),
            "evidence_resolutions": evidence, "authorizations": authorizations,
            "graph_sha256": self.graph_sha, "catalog_sha256": self.catalog_sha,
            "version_hashes": self.versions, "authority_scope": edge["authority_scope"],
            "automatic_transition": False, "retry_allowed": False, "stage18_authority": False,
        }
        path = self.root / "records" / f"transition-{sequence:03d}.json"
        write_json(path, document)
        digest = sha_file(path)
        self.append("transition_records", {"path": path.relative_to(self.root).as_posix(), "sha256": digest})
        self.previous_transition_sha = digest
        self.transition_count += 1

    def sign(self, authorization_path: pathlib.Path, namespace: str) -> pathlib.Path:
        result = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "sign", "-f", str(self.signing_key), "-n", namespace, str(authorization_path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=10,
        )
        if result.returncode != 0:
            raise CheckError("synthetic SSHSIG signing failed")
        return pathlib.Path(str(authorization_path) + ".sig")

    def phase_authorization(self, action: str, predecessors: list[dict[str, Any]], request: pathlib.Path, *, permission: dict[str, bool]) -> tuple[pathlib.Path, pathlib.Path]:
        path = self.root / "evidence" / f"synthetic-{action.lower()}-authorization.json"
        fixed = self.root / "config/stage17/stage17-fixed-phase-actions-v1.json"
        executable = self.root / "tools/stage17_phase_controller_v1.py"
        document = {
            "schema_version": "cpu-prefetch-stage17-phase-action-authorization/1",
            "authorization_id": f"SYNTHETIC-{action}-AUTHORIZATION-TEST-ONLY",
            "action_id": action, "actor": "synthetic-stage17-owner",
            "target": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "execution_root": str(self.external)},
            "issued_at_utc": utc(0), "expires_at_utc": utc(30),
            "predecessor_resolutions": predecessors,
            "fixed_action_definition_sha256": sha_file(fixed),
            "request_binding": {"path": str(request), "size_bytes": request.stat().st_size, "sha256": sha_file(request)},
            "allowed_signers_binding": {"path": str(self.allowed_signers), "size_bytes": self.allowed_signers.stat().st_size, "sha256": sha_file(self.allowed_signers)},
            "principal": "synthetic-stage17-owner", "sshsig_namespace": "cpu-prefetch-stage17-test-v1",
            "executable_bindings": [{"path": str(executable), "size_bytes": executable.stat().st_size, "sha256": sha_file(executable)}],
            "evidence_root": str(self.external), "expected_prestate_sha256": "1" * 64,
            "permission_matrix": permission, "max_wall_seconds": 180,
            "one_attempt": True, "retry_allowed": False, "stop_first": True,
            "retain_partial": True, "stage18_authority": False,
        }
        write_json(path, document)
        return path, self.sign(path, "cpu-prefetch-stage17-test-v1")

    def fixed_request(
        self, action: str, output_names: list[str],
        parameters: dict[str, Any] | None = None,
    ) -> pathlib.Path:
        path = self.root / "evidence" / f"synthetic-{action.lower()}-request.json"
        write_json(path, {
            "schema_version": "cpu-prefetch-stage17-fixed-action-request/1",
            "request_id": f"SYNTHETIC-{action}-REQUEST-TEST-ONLY", "action_id": action,
            "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "expected_prestate_sha256": "1" * 64,
            "parameters": parameters or {"test_fixture": True},
            "output_artifact_names": output_names,
            "command_override": None, "argv_override": None, "stdin_override": None,
            "synthetic_test_only": True, "phase18_authority": False,
        })
        return path

    def ext001(self) -> None:
        policy = json.loads((self.root / journal.SEMANTIC_POLICY_PATH).read_text())
        pinned = self.root / "evidence/synthetic-pinned-host-key.json"
        key_type, public = b"ssh-ed25519", bytes(range(32))
        blob = len(key_type).to_bytes(4, "big") + key_type + len(public).to_bytes(4, "big") + public
        fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
        write_json(pinned, {"schema_version": "cpu-prefetch-stage17-pinned-host-key-evidence/1", "evidence_id": "SYNTHETIC-PIN", "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "ssh_target": "synthetic@synthetic.invalid", "algorithm": "ssh-ed25519", "public_key_base64": base64.b64encode(blob).decode(), "fingerprint_sha256": fingerprint, "source": "OWNER_PROVIDED_OUT_OF_BAND_PIN", "runtime_observation": False})
        known = self.root / "evidence/synthetic.known_hosts"
        known.write_bytes(b"synthetic.invalid ssh-ed25519 " + base64.b64encode(blob) + b"\n")
        identity = self.external / "synthetic-transport-identity"
        identity.write_bytes(b"synthetic-not-a-production-private-key\n")
        identity.chmod(0o600)
        evidence_root = self.external / "preflight-evidence"
        evidence_root.mkdir(mode=0o700)
        effective = {**policy["fixed_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/6"}
        pilot_fixed = self.catalog["fixed_evidence_contracts"][0]
        contract = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-supporting-contract/8",
            "contract_id": "SYNTHETIC-S17-EXT-001-CONTRACT-TEST-ONLY", "protocol_version": "2.0.0-pre.2",
            "fixed_action_plan": effective,
            "target": {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "ssh_target": "synthetic@synthetic.invalid", "known_hosts_host": "synthetic.invalid", "pinned_host_key_evidence": {"path": pinned.relative_to(self.root).as_posix(), "size_bytes": pinned.stat().st_size, "sha256": sha_file(pinned), "schema_identity": "cpu-prefetch-stage17-pinned-host-key-evidence/1"}, "pinned_known_hosts": {"path": known.relative_to(self.root).as_posix(), "size_bytes": known.stat().st_size, "sha256": sha_file(known)}, "transport_identity": {"locator": str(identity), "size_bytes": identity.stat().st_size, "sha256": sha_file(identity)}},
            "pilot_candidate": {"contract": {"path": pilot_fixed["path"], "size_bytes": pilot_fixed["size_bytes"], "sha256": pilot_fixed["sha256"], "schema_identity": "cpu-prefetch-stage17-pilot-candidate-external-contract/1"}, "archive_locator": "/synthetic/pilot.tar.gz", "sidecar_locator": "/synthetic/pilot.tar.gz.sha256", "bundle_root_locator": "/synthetic/bundle"},
            "capture": {"capture_id": "SYNTHETIC-S17-PREFLIGHT-TEST-ONLY", "captured_at_utc": utc(10)}, "evidence_root": str(evidence_root),
            "prospective_local_action_identities": [
                {"identity_id": "STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR", "role": "EXECUTOR", "execution_path": str(self.root / policy["implementations"]["executor"]["path"]), "source_binding": policy["implementations"]["executor"]},
                {"identity_id": "STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR", "role": "COLLECTOR", "execution_path": str(self.root / policy["implementations"]["collector"]["path"]), "source_binding": policy["implementations"]["collector"]},
            ],
            "remote_runtime_identity_policy": {"source_input_id": "S17-EXT-002", "identity_classes": ["REMOTE_EXECUTABLE", "REMOTE_MODULE", "REMOTE_DEPENDENCY"], "prospective_values_present": False},
            "limits": {"max_commands": 6, "max_wall_seconds": 180, "max_total_output_bytes": 6291456, "max_output_bytes_per_observation": 1048576, "timeout_seconds_per_observation": 30, "attempts_per_observation": 1, "retries": 0},
            "stop_policy": "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT", "retention_policy": "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE",
            "authority_boundary": {"stand_read_only": True, "stand_mutation": False, "privileged_controls": False, "qualification": False, "calibration": False, "pilot_execution": False, "measurement": False, "stage18_authority": False},
        }
        contract_path = self.root / "evidence/s17-ext-001-contract-v8.json"
        write_json(contract_path, contract)
        contract_binding = {"path": contract_path.relative_to(self.root).as_posix(), "size_bytes": contract_path.stat().st_size, "sha256": sha_file(contract_path), "schema_identity": "cpu-prefetch-stage17-read-only-preflight-supporting-contract/8"}
        authorization = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-authorization/8", "authorization_id": "SYNTHETIC-S17-EXT-001-AUTHORIZATION-TEST-ONLY", "attempt_id": "SYNTHETIC-S17-EXT-001-ATTEMPT-TEST-ONLY", "input_id": "S17-EXT-001", "actor": "synthetic-stage17-owner", "issued_at_utc": utc(0), "expires_at_utc": "2030-01-02T00:00:00Z", "authority_scope": "READ_ONLY_PREFLIGHT", "target_scope": "STAND_ID=SYNTHETIC-STAND-NOT-ACCESSED;SSH_TARGET=synthetic@synthetic.invalid;SCOPE=READ_ONLY_PREFLIGHT;PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v6",
            "target": {"stand_id": contract["target"]["stand_id"], "ssh_target": contract["target"]["ssh_target"], "known_hosts_host": contract["target"]["known_hosts_host"], "pinned_host_key_evidence_sha256": contract["target"]["pinned_host_key_evidence"]["sha256"], "pinned_known_hosts_sha256": contract["target"]["pinned_known_hosts"]["sha256"], "transport_identity_sha256": contract["target"]["transport_identity"]["sha256"]},
            "frozen_observation_ids": list(OBSERVATION_IDS), "fixed_action_plan": effective, "supporting_observation_contract": contract_binding, "evidence_root": str(evidence_root), "limits": contract["limits"], "role_collapse_acknowledged": True, "independent_review_claimed": False, "permissions": contract["authority_boundary"], "automatic_transition": False, "retry_allowed": False, "stage18_authority": False,
        }
        auth_path = self.root / "evidence/s17-ext-001-authorization-v8.json"
        write_json(auth_path, authorization)
        auth_binding = {"path": auth_path.relative_to(self.root).as_posix(), "size_bytes": auth_path.stat().st_size, "sha256": sha_file(auth_path), "schema_identity": "cpu-prefetch-stage17-read-only-preflight-authorization/8"}
        policy_path = self.root / journal.SEMANTIC_POLICY_PATH
        envelope = {
            "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/9", "envelope_id": "SYNTHETIC-S17-EXT-001-ENVELOPE-TEST-ONLY", "input_id": "S17-EXT-001",
            "predecessor": {"graph_sha256": self.graph_sha, "catalog_sha256": self.catalog_sha, "genesis_sha256": self.genesis_sha, "resolution_schema_identity": "cpu-prefetch-stage17-external-input-resolution/1", "resolution_schema_sha256": self.versions["resolution_schema_sha256"], "semantic_policy_v8_sha256": policy["predecessor"]["policy_v8"]["sha256"], "adr_0113_sha256": policy["predecessor"]["adr_0113"]["sha256"]},
            "semantic_policy": {"path": journal.SEMANTIC_POLICY_PATH.as_posix(), "size_bytes": policy_path.stat().st_size, "sha256": sha_file(policy_path)}, "semantic_verifier": {"verifier_id": "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER", "verifier_version": "9"},
            "authorization": auth_binding, "supporting_contract": contract_binding, "effective_action_plan": effective,
            "successor_action_plan": {**policy["successor_action_plan"], "schema_identity": "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/7"},
            "runtime_implementations": policy["implementations"], "stage18_authority": False,
        }
        envelope_path = self.root / "evidence/s17-ext-001-envelope-v9.json"
        write_json(envelope_path, envelope)
        summary = {"authorization_id": authorization["authorization_id"], "evidence_path": auth_path.relative_to(self.root).as_posix(), "issued_at_utc": authorization["issued_at_utc"], "expires_at_utc": authorization["expires_at_utc"], "authority_scope": "READ_ONLY_PREFLIGHT"}
        self.add_resolution("S17-EXT-001", [self.repository_evidence(envelope_path)], summary, {"manifest_sha256": sha_file(envelope_path)})

    def ext002(self) -> None:
        artifacts: list[dict[str, Any]] = []
        attempt = self.root / "evidence/ext002-attempt.json"
        write_json(attempt, {"attempt_id": "SYNTHETIC-PREFLIGHT-ATTEMPT", "runtime_implementation_hashes": {"synthetic": "2" * 64}, "rendered_programs": [{"ordinal": index, "observation_id": value} for index, value in enumerate(OBSERVATION_IDS, 1)]})
        artifacts.append(binding(attempt, role="ATTEMPT", artifact_id="ATTEMPT"))
        receipt_hashes: list[str] = []
        for ordinal, observation_id in enumerate(OBSERVATION_IDS, 1):
            stdout = self.root / "evidence" / f"ext002-{ordinal:02d}.stdout"
            stderr = self.root / "evidence" / f"ext002-{ordinal:02d}.stderr"
            stdout.write_bytes((json.dumps({"observation_id": observation_id, "synthetic": True}) + "\n").encode())
            stderr.write_bytes(b"")
            receipt = self.root / "evidence" / f"ext002-{ordinal:02d}.receipt.json"
            write_json(receipt, {"attempt_id": "SYNTHETIC-PREFLIGHT-ATTEMPT", "ordinal": ordinal, "observation_id": observation_id, "returncode": 0, "failure": None, "retry": 0, "leader_reaped": True, "process_group_gone": True, "stdout_size_bytes": stdout.stat().st_size, "stdout_sha256": sha_file(stdout), "stderr_size_bytes": 0, "stderr_sha256": SHA_EMPTY})
            artifacts.extend((binding(receipt, role=f"OBSERVATION_{ordinal:02d}_RECEIPT", artifact_id=f"RECEIPT-{ordinal}"), binding(stdout, role=f"OBSERVATION_{ordinal:02d}_STDOUT", artifact_id=f"STDOUT-{ordinal}", media="application/octet-stream"), binding(stderr, role=f"OBSERVATION_{ordinal:02d}_STDERR", artifact_id=f"STDERR-{ordinal}", media="application/octet-stream")))
            receipt_hashes.append(sha_file(receipt))
        completion = self.root / "evidence/ext002-completion.json"
        write_json(completion, {"attempt_id": "SYNTHETIC-PREFLIGHT-ATTEMPT", "completed_observation_ids": list(OBSERVATION_IDS), "receipt_sha256s": receipt_hashes, "all_leaders_reaped": True, "all_process_groups_gone": True, "retries": 0})
        artifacts.insert(1, binding(completion, role="COMPLETION", artifact_id="COMPLETION"))
        manifest = self.manifest("S17-EXT-002", self.predecessor_bindings(1), artifacts, {"successful": True, "observation_ids": list(OBSERVATION_IDS), "attempt_role": "ATTEMPT", "receipt_roles": [f"OBSERVATION_{i:02d}_RECEIPT" for i in range(1, 7)], "stdout_roles": [f"OBSERVATION_{i:02d}_STDOUT" for i in range(1, 7)], "stderr_roles": [f"OBSERVATION_{i:02d}_STDERR" for i in range(1, 7)], "completion_role": "COMPLETION", "failure_roles": [], "retention_roles": [], "runtime_identities_verified": True, "inventory_input_sha256": "3" * 64, "qualification_input_sha256": "4" * 64})
        self.add_resolution("S17-EXT-002", [self.external_receipt("S17-EXT-002", manifest)], None, {"manifest_sha256": sha_file(manifest)})

    def ext003(self) -> None:
        trust = self.root / "evidence/ext003-trust.json"
        write_json(trust, {"schema_version": "cpu-prefetch-stage17-trust-anchor/1", "principal": "synthetic-stage17-owner", "namespace": "cpu-prefetch-stage17-test-v1", "allowed_signers_sha256": sha_file(self.allowed_signers), "stage18_authority": False})
        manifest = self.manifest("S17-EXT-003", self.predecessor_bindings(2, start=2), [binding(trust, role="TRUST_ANCHOR", artifact_id="TRUST")], {"accepted_manifest_sha256": self.contexts["S17-EXT-002"]["manifest_sha256"], "all_hashes_recomputed": True, "six_observations_complete": True, "owner_acceptance": True, "owner_id": "synthetic-stage17-owner", "distinct_auditor": False, "independent_review": False, "role_collapse": ["OWNER", "OPERATOR", "CUSTODIAN", "AUDITOR"], "trust_anchor_role": "TRUST_ANCHOR", "authority_expansion": False})
        self.add_resolution("S17-EXT-003", [self.repository_evidence(manifest)], None, {"manifest_sha256": sha_file(manifest)})

    def ext004(self) -> None:
        artifacts = []
        classes = ("NEAR_MEMORY_PAIR", "FAR_MEMORY_PAIR", "CLOCK_SUITABILITY", "ATOMICS_AND_LAYOUT", "AFFINITY_AND_MIGRATION", "NUMA_AND_PAGE_PLACEMENT", "STORAGE_AND_RECOVERY", "HARDWARE_PREFETCH", "STAND_PRESTATE", "Q15_COLLECTOR")
        for name in classes:
            path = self.root / "evidence" / f"ext004-{name.lower()}.json"
            write_json(path, {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "qualification_class": name, "requested_state": {"value": "SYNTHETIC"}, "verified_state": {"value": "SYNTHETIC"}, "eligible": True, "synthetic_test_only": True})
            artifacts.append(binding(path, role=f"QUALIFICATION_{name}", artifact_id=name))
        manifest = self.manifest("S17-EXT-004", self.predecessor_bindings(3), artifacts, {"stand_id": "SYNTHETIC-STAND-NOT-ACCESSED", "qualification_classes": list(classes), "requested_verified_separate": True, "all_eligible": True, "development_host_evidence": False, "q15_collector_role": "QUALIFICATION_Q15_COLLECTOR"})
        self.add_resolution("S17-EXT-004", [self.external_receipt("S17-EXT-004", manifest)], None, {"manifest_sha256": sha_file(manifest)})

    def ext005(self) -> None:
        request = self.fixed_request("Q15-W", ["before.json", "after.json", "readback.json", "probes.json"])
        auth, signature = self.phase_authorization("Q15-W", self.predecessor_bindings(4), request, permission={"read_only_observation": False, "privileged_controls": True, "calibration": False, "pilot_execution": False, "measurement": False, "phase18": False})
        docs: dict[str, pathlib.Path] = {}
        for role in ("BEFORE_STATE", "AFTER_STATE", "READBACK", "PROBES"):
            path = self.root / "evidence" / f"ext005-{role.lower()}.json"
            write_json(path, {"role": role, "verified": True, "synthetic_test_only": True})
            docs[role] = path
        result = self.root / "evidence/ext005-result.json"
        auth_doc = json.loads(auth.read_text())
        write_json(result, {"schema_version": "cpu-prefetch-stage17-phase-action-result/1", "result_id": "SYNTHETIC-Q15-W-RESULT", "action_id": "Q15-W", "authorization_id": auth_doc["authorization_id"], "authorization_sha256": sha_file(auth), "attempt_id": "SYNTHETIC-Q15-W-ATTEMPT", "actual_started_at_utc": utc(5), "actual_completed_at_utc": utc(6), "before_sha256": sha_file(docs["BEFORE_STATE"]), "after_sha256": sha_file(docs["AFTER_STATE"]), "readback_sha256": sha_file(docs["READBACK"]), "probe_sha256": sha_file(docs["PROBES"]), "restoration": "VERIFIED", "quarantine": False, "completed": True, "retry_allowed": False, "phase18_authority": False})
        artifacts = [binding(request, role="ACTION_REQUEST", artifact_id="REQUEST"), binding(auth, role="AUTHORIZATION", artifact_id="AUTH"), binding(signature, role="SIGNATURE", artifact_id="SIGN", media="application/octet-stream"), binding(self.allowed_signers, role="ALLOWED_SIGNERS", artifact_id="SIGNERS", media="text/plain"), binding(result, role="ACTION_RESULT", artifact_id="RESULT"), *(binding(path, role=role, artifact_id=role) for role, path in docs.items())]
        payload = {"request_role": "ACTION_REQUEST", "authorization_role": "AUTHORIZATION", "signature_role": "SIGNATURE", "allowed_signers_role": "ALLOWED_SIGNERS", "result_role": "ACTION_RESULT", "before_role": "BEFORE_STATE", "after_role": "AFTER_STATE", "readback_role": "READBACK", "probe_role": "PROBES", "principal": "synthetic-stage17-owner", "namespace": "cpu-prefetch-stage17-test-v1", "admitted_after_state": "PREFLIGHT_ACCEPTED", "one_attempt": True, "retry_allowed": False, "restoration_verified": True, "quarantine": False, "action_request_precedes_resolution": True}
        manifest = self.manifest("S17-EXT-005", self.predecessor_bindings(4), artifacts, payload)
        summary = {"authorization_id": auth_doc["authorization_id"], "evidence_path": auth.relative_to(self.root).as_posix(), "issued_at_utc": auth_doc["issued_at_utc"], "expires_at_utc": auth_doc["expires_at_utc"], "authority_scope": "PRIVILEGED_QUALIFICATION_CONTROL"}
        self.add_resolution("S17-EXT-005", [self.repository_evidence(auth), self.external_receipt("S17-EXT-005", manifest)], summary, {"manifest_sha256": sha_file(manifest)})

    def _synthetic_pilot_bundle(self) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
        tree_parent = self.external / "pilot-tree"
        top = tree_parent / "synthetic-stage17-pilot-candidate"
        top.mkdir(parents=True)
        protocol_target = top / "protocol/2.0.0-pre.2/IMPORT_MANIFEST.json"
        protocol_target.parent.mkdir(parents=True)
        shutil.copyfile(self.root / "protocol/2.0.0-pre.2/IMPORT_MANIFEST.json", protocol_target)
        source = top / "source/synthetic-source.tar"
        source.parent.mkdir()
        source.write_bytes(b"synthetic source fixture\n")
        releases = []
        for name in ("cpu_prefetch_runner", "cpu_prefetch_qualification"):
            path = top / "release/bin" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"synthetic {name}\n".encode())
            releases.append({"path": path.relative_to(top).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha_file(path)})
        for report_name in ("queue_codegen_report.json", "workload_codegen_report.json", "timing_codegen_report.json", "storage_codegen_report.json", "runner_relax_codegen_report.json", "runner_combined_codegen_report.json"):
            path = top / "build-provenance" / report_name
            path.parent.mkdir(parents=True, exist_ok=True)
            document = {"status": "PASS", "missing_tools": []}
            if report_name == "runner_combined_codegen_report.json":
                document.update({"schema_version": "cpu-prefetch-runner-combined-codegen/2", "software_prefetch_mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1"})
            write_json(path, document)
        example = top / "config/examples/stage16-stand-inputs.example.json"
        example.parent.mkdir(parents=True)
        write_json(example, {"authoritative": False, "required_external_inputs": {"stand_id": None}})
        manifest = top / "BUNDLE_MANIFEST.json"
        write_json(manifest, {"schema_version": "cpu-prefetch-pilot-candidate-bundle/1", "bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v1", "protocol_version": "2.0.0-pre.2", "protocol_import_manifest_sha256": sha_file(protocol_target), "readiness_state": "RELEASE_INPUT_READY_FOR_Q15_PREPARATION", "pilot_authorized": False, "confirmatory_authorized": False, "dynamic_qualification_authorized": False, "measurement_execution_command_present": False, "software_prefetch_mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1", "debug_symbol_strategy": "UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE", "source_archive": {"path": source.relative_to(top).as_posix(), "sha256": sha_file(source), "source_revision": "0" * 40, "source_dirty": False}, "release_artifacts": releases})
        files = sorted(path for path in top.rglob("*") if path.is_file())
        sums = top / "SHA256SUMS"
        sums.write_text("".join(f"{sha_file(path)}  {path.relative_to(top).as_posix()}\n" for path in files), encoding="ascii")
        archive = self.external / "synthetic-stage17-pilot-candidate.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            bundle.add(top, arcname=top.name)
        sidecar = self.external / (archive.name + ".sha256")
        sidecar.write_text(f"{sha_file(archive)}  {archive.name}\n", encoding="ascii")
        contract = self.root / "config/stage17/synthetic-stage17-pilot-contract-v1.json"
        write_json(contract, {"schema_version": "cpu-prefetch-stage17-pilot-candidate-external-contract/1", "contract_id": "STAGE17-PILOT-CANDIDATE-EXTERNAL-CONTRACT-v1", "protocol_version": "2.0.0-pre.2", "source_revision": "0" * 40, "archive": {"filename": archive.name, "size_bytes": archive.stat().st_size, "sha256": sha_file(archive)}, "sidecar": {"filename": sidecar.name, "size_bytes": sidecar.stat().st_size, "sha256": sha_file(sidecar), "exact_ascii": sidecar.read_text()}, "release_identity": {"top_level_directory": top.name, "manifest_path": "BUNDLE_MANIFEST.json", "manifest_sha256": sha_file(manifest), "bundle_profile": "STAGE17-PILOT-CANDIDATE-BUNDLE-v1", "file_count": len(files)}, "verifier": {"id": "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER", "version": "1", "path": "tools/check_stage17_pilot_candidate_artifact.py"}, "custody_recovery": {"policy": "BYTE_IDENTICAL_CUSTODY_COPY_OR_REPRODUCIBLE_REBUILD", "clean_checkout_configure_command": "cmake --preset release-gcc", "clean_checkout_build_command": "cmake --build --preset release-gcc --target pilot-candidate-bundle", "acceptance_rule": "REBUILT_ARCHIVE_AND_SIDECAR_MUST_MATCH_EVERY_CONTRACTED_BYTE_SIZE_AND_SHA256_OR_S17_EXT_006_REMAINS_UNRESOLVED"}, "authority_boundary": {"stand_access": False, "preflight": False, "calibration": False, "pilot": False, "stage18": False}})
        return archive, sidecar, contract

    def ext006(self) -> None:
        archive, sidecar, contract = self._synthetic_pilot_bundle()
        self.pilot_archive, self.pilot_sidecar = archive, sidecar
        receipt = self.external_receipt("S17-EXT-006", archive, contract_path=contract, sidecars=[sidecar], verifier_id="STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER", verifier_version="1")
        self.add_resolution("S17-EXT-006", [receipt], None, {"manifest_sha256": sha_file(archive)})

    def ext007(self) -> None:
        artifacts: list[dict[str, Any]] = []
        phase_entries = []
        run_ids = []
        for phase in ("Q16a", "Q16b", "Q16c"):
            plan = self.fixed_request(phase, [f"{phase}-raw.json", f"{phase}-result.json"])
            auth, signature = self.phase_authorization(phase, self.predecessor_bindings(6), plan, permission={"read_only_observation": False, "privileged_controls": False, "calibration": True, "pilot_execution": False, "measurement": True, "phase18": False})
            raw = self.root / "evidence" / f"{phase}-raw.json"
            result = self.root / "evidence" / f"{phase}-result.json"
            run_id = f"SYNTHETIC-{phase}-RUN"
            write_json(raw, {"phase": phase, "run_id": run_id, "synthetic_test_only": True})
            write_json(result, {"phase": phase, "run_id": run_id, "authorization_sha256": sha_file(auth), "actual_started_at_utc": utc(5), "actual_completed_at_utc": utc(6), "valid": True, "synthetic_test_only": True})
            prefix = phase.upper()
            roles = {"plan_role": f"{prefix}_PLAN", "authorization_role": f"{prefix}_AUTHORIZATION", "signature_role": f"{prefix}_SIGNATURE", "allowed_signers_role": f"{prefix}_ALLOWED_SIGNERS", "raw_role": f"{prefix}_RAW", "result_role": f"{prefix}_RESULT"}
            phase_entries.append({"phase": phase, **roles, "principal": "synthetic-stage17-owner", "namespace": "cpu-prefetch-stage17-test-v1", "run_id": run_id})
            artifacts.extend((binding(plan, role=roles["plan_role"], artifact_id=f"{phase}-PLAN"), binding(auth, role=roles["authorization_role"], artifact_id=f"{phase}-AUTH"), binding(signature, role=roles["signature_role"], artifact_id=f"{phase}-SIGN", media="application/octet-stream"), binding(self.allowed_signers, role=roles["allowed_signers_role"], artifact_id=f"{phase}-SIGNERS", media="text/plain"), binding(raw, role=roles["raw_role"], artifact_id=f"{phase}-RAW"), binding(result, role=roles["result_role"], artifact_id=f"{phase}-RESULT")))
            run_ids.append(run_id)
        freeze = self.root / "evidence/calibration-freeze.json"
        write_json(freeze, {"state": "FROZEN", "unresolved_inputs": [], "source_run_ids": run_ids, "synthetic_test_only": True})
        artifacts.append(binding(freeze, role="CALIBRATION_FREEZE", artifact_id="CALIBRATION-FREEZE"))
        manifest = self.manifest("S17-EXT-007", self.predecessor_bindings(6), artifacts, {"phases": phase_entries, "calibration_freeze_role": "CALIBRATION_FREEZE", "treatment_blind": True, "confirmatory_outcomes_accessed": False})
        self.add_resolution("S17-EXT-007", [self.external_receipt("S17-EXT-007", manifest)], None, {"manifest_sha256": sha_file(manifest)})

    def ext008(self) -> None:
        schedule = self.root / "evidence/pilot-schedule.bin"
        seed = self.root / "evidence/pilot-seed.bin"
        schedule.write_bytes(b"synthetic deterministic schedule\n")
        seed.write_bytes(b"synthetic deterministic seed namespace\n")
        artifacts = [binding(schedule, role="PILOT_SCHEDULE", artifact_id="PILOT-SCHEDULE", media="application/octet-stream"), binding(seed, role="PILOT_SEED", artifact_id="PILOT-SEED", media="application/octet-stream")]
        run_ids = ["SYNTHETIC-PILOT-RUN-001", "SYNTHETIC-PILOT-RUN-002"]
        predecessor_hashes = {item: self.contexts[item]["manifest_sha256"] for item in (f"S17-EXT-{index:03d}" for index in range(1, 8))}
        payload = {"frozen": True, "run_ids": run_ids, "schedule_roles": ["PILOT_SCHEDULE"], "seed_roles": ["PILOT_SEED"], "horizons_ticks": {"warmup": 100, "measurement": 1000}, "capacities": {"ring": 1024, "raw_rows": 4096}, "treatment_blind_labels": {"A": "BLIND-A"}, "stop_rules": {"watchdog_ticks": 2000}, "resource_limits": {"max_bytes": 1048576}, "artifact_names": {"manifest": "pilot-manifest.json"}, "expected_artifact_hashes": {"PILOT_SCHEDULE": sha_file(schedule), "PILOT_SEED": sha_file(seed)}, "confirmatory_namespace": False, "outcome_dependent": False, "predecessor_manifest_hashes": predecessor_hashes}
        manifest = self.manifest("S17-EXT-008", self.predecessor_bindings(7), artifacts, payload)
        self.add_resolution("S17-EXT-008", [self.repository_evidence(manifest)], None, {"manifest_sha256": sha_file(manifest), "run_ids": run_ids})

    def ext009(self) -> None:
        docs: dict[str, pathlib.Path] = {}
        values = {"STORAGE_BUDGET": {"checked": True, "required_bytes": 1024, "available_bytes": 4096}, "COPY_LEDGER": {"custody_domains": ["SYNTHETIC-A", "SYNTHETIC-B"], "all_hashes_verified": True}, "TRANSFER_VERIFICATION": {"verified": True}, "RECOVERY_TEST": {"passed": True}, "RECOVERY_PROCEDURE": {"procedure": "synthetic-test-only"}}
        for role, document in values.items():
            path = self.root / "evidence" / f"ext009-{role.lower()}.json"
            write_json(path, {**document, "synthetic_test_only": True})
            docs[role] = path
        artifacts = [binding(path, role=role, artifact_id=role) for role, path in docs.items()]
        payload = {"budget_role": "STORAGE_BUDGET", "custody_domains": ["SYNTHETIC-A", "SYNTHETIC-B"], "copy_ledger_role": "COPY_LEDGER", "transfer_role": "TRANSFER_VERIFICATION", "recovery_test_role": "RECOVERY_TEST", "archive_naming": "stage17-pilot-{run_id}.tar.zst", "ownership_verified": True, "permissions_verified": True, "pilot_artifact_ids": ["SYNTHETIC-PILOT-RUN-001", "SYNTHETIC-PILOT-RUN-002"], "recovery_procedure_role": "RECOVERY_PROCEDURE"}
        manifest = self.manifest("S17-EXT-009", self.predecessor_bindings(8), artifacts, payload)
        self.add_resolution("S17-EXT-009", [self.repository_evidence(docs["STORAGE_BUDGET"]), self.external_receipt("S17-EXT-009", manifest)], None, {"manifest_sha256": sha_file(manifest)})

    def ext010(self) -> None:
        request = self.fixed_request(
            "STAGE17-BLINDED-PILOT",
            ["pilot-attempt.json", "pilot-completion.json"],
            {"pilot_plan_sha256": self.contexts["S17-EXT-008"]["manifest_sha256"],
             "run_ids": self.contexts["S17-EXT-008"]["run_ids"]},
        )
        predecessors = self.predecessor_bindings(9)
        auth, signature = self.phase_authorization("STAGE17-BLINDED-PILOT", predecessors, request, permission={"read_only_observation": False, "privileged_controls": False, "calibration": False, "pilot_execution": True, "measurement": True, "phase18": False})
        payload = {"request_role": "ACTION_REQUEST", "authorization_role": "AUTHORIZATION", "signature_role": "SIGNATURE", "allowed_signers_role": "ALLOWED_SIGNERS", "principal": "synthetic-stage17-owner", "namespace": "cpu-prefetch-stage17-test-v1", "pilot_plan_sha256": self.contexts["S17-EXT-008"]["manifest_sha256"], "run_ids": self.contexts["S17-EXT-008"]["run_ids"], "exact_predecessors": predecessors, "graph_state": "READY_FOR_STAGE17_PHASE_AUTHORIZATION", "command_expansion": False, "argv_expansion": False, "stdin_expansion": False, "run_set_expansion": False, "target_expansion": False, "phase18_authority": False}
        manifest = self.manifest("S17-EXT-010", predecessors, [binding(request, role="ACTION_REQUEST", artifact_id="PILOT-REQUEST"), binding(auth, role="AUTHORIZATION", artifact_id="PILOT-AUTH"), binding(signature, role="SIGNATURE", artifact_id="PILOT-SIGN", media="application/octet-stream"), binding(self.allowed_signers, role="ALLOWED_SIGNERS", artifact_id="PILOT-SIGNERS", media="text/plain")], payload)
        auth_doc = json.loads(auth.read_text())
        summary = {"authorization_id": auth_doc["authorization_id"], "evidence_path": auth.relative_to(self.root).as_posix(), "issued_at_utc": auth_doc["issued_at_utc"], "expires_at_utc": auth_doc["expires_at_utc"], "authority_scope": "STAGE17_PILOT_PHASE_ONLY"}
        self.add_resolution("S17-EXT-010", [self.repository_evidence(manifest)], summary, {"manifest_sha256": sha_file(manifest)})

    def build_all(self) -> journal.JournalValidation:
        self.ext001(); self.add_transition()
        self.ext002(); self.ext003(); self.add_transition()
        self.ext004(); self.ext005(); self.ext006(); self.add_transition()
        self.ext007(); self.ext008(); self.ext009(); self.ext010()
        return journal.validate_journal(
            repository_root=self.root, latest_journal=self.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            pilot_archive=self.pilot_archive, pilot_sidecar=self.pilot_sidecar,
            as_of_utc=utc(15), allow_synthetic_test_evidence=True,
        )


def _expect_failure(label: str, action: Callable[[], Any]) -> None:
    try:
        action()
    except BaseException:
        print(f"stage17-complete-admission: PASS negative={label}")
        return
    raise CheckError(f"negative fixture was admitted: {label}")


def _semantic_negative_cases(builder: Builder) -> int:
    semantics = __import__("stage17_operational_semantics_v1")
    admitted = {
        input_id: types.SimpleNamespace(
            resolution_id=document["resolution_id"], sha256=digest,
            semantic_context=builder.contexts[input_id],
        )
        for input_id, (_, document, digest) in builder.resolutions.items()
    }
    count = 0

    def reject(
        label: str, input_id: str,
        mutate: Callable[[dict[str, Any], pathlib.Path], None],
    ) -> None:
        nonlocal count
        source = builder.root / "evidence" / f"{input_id.lower()}-manifest-v1.json"
        document = copy.deepcopy(json.loads(source.read_text()))
        target = builder.root / "evidence" / f"negative-{label}.json"
        mutate(document, target)
        write_json(target, document)
        _expect_failure(
            label,
            lambda: semantics.verify_manifest(
                manifest_path=target, repository_root=builder.root,
                admitted_resolutions=admitted, expected_input_id=input_id,
                allow_synthetic=True,
            ),
        )
        count += 1

    reject("ext002_missing_artifact", "S17-EXT-002", lambda d, _: d["artifacts"].pop())
    reject("ext002_duplicate_artifact", "S17-EXT-002", lambda d, _: d["artifacts"].append(copy.deepcopy(d["artifacts"][0])))
    reject("ext002_reordered_receipts", "S17-EXT-002", lambda d, _: d["payload"].__setitem__("receipt_roles", list(reversed(d["payload"]["receipt_roles"]))))
    reject("ext002_hash_drift", "S17-EXT-002", lambda d, _: d["artifacts"][0].__setitem__("sha256", "a" * 64))
    reject("ext002_size_drift", "S17-EXT-002", lambda d, _: d["artifacts"][0].__setitem__("size_bytes", d["artifacts"][0]["size_bytes"] + 1))
    reject("ext002_path_drift", "S17-EXT-002", lambda d, _: d["artifacts"][0].__setitem__("locator", "/does/not/exist/stage17"))
    reject("ext002_runtime_drift", "S17-EXT-002", lambda d, _: d["payload"].__setitem__("runtime_identities_verified", False))
    reject("ext002_partial_bundle", "S17-EXT-002", lambda d, _: d["payload"].__setitem__("successful", False))
    reject("ext003_improper_role_collapse", "S17-EXT-003", lambda d, _: d["payload"].__setitem__("distinct_auditor", True))
    reject("ext003_wrong_preflight_hash", "S17-EXT-003", lambda d, _: d["payload"].__setitem__("accepted_manifest_sha256", "b" * 64))
    reject("ext004_missing_qualification", "S17-EXT-004", lambda d, _: d["artifacts"].pop())
    reject("ext004_wrong_target", "S17-EXT-004", lambda d, _: d["payload"].__setitem__("stand_id", "WRONG-STAND"))
    reject("ext004_ineligible", "S17-EXT-004", lambda d, _: d["payload"].__setitem__("all_eligible", False))
    reject("ext005_wrong_state", "S17-EXT-005", lambda d, _: d["payload"].__setitem__("admitted_after_state", "PREPARED"))
    reject("ext005_restoration_failure", "S17-EXT-005", lambda d, _: d["payload"].__setitem__("restoration_verified", False))
    reject("ext005_quarantine_mismatch", "S17-EXT-005", lambda d, _: d["payload"].__setitem__("quarantine", True))
    reject("ext005_unauthorized_argv", "S17-EXT-005", lambda d, _: d["artifacts"][0].__setitem__("sha256", "c" * 64))
    reject("ext007_phase_reorder", "S17-EXT-007", lambda d, _: d["payload"].__setitem__("phases", list(reversed(d["payload"]["phases"]))))
    reject("ext007_duplicate_run", "S17-EXT-007", lambda d, _: d["payload"]["phases"][1].__setitem__("run_id", d["payload"]["phases"][0]["run_id"]))
    reject("ext007_outcome_access", "S17-EXT-007", lambda d, _: d["payload"].__setitem__("confirmatory_outcomes_accessed", True))
    reject("ext008_duplicate_run", "S17-EXT-008", lambda d, _: d["payload"].__setitem__("run_ids", [d["payload"]["run_ids"][0]] * 2))
    reject("ext008_plan_hash_drift", "S17-EXT-008", lambda d, _: d["payload"]["predecessor_manifest_hashes"].__setitem__("S17-EXT-007", "d" * 64))
    reject("ext008_outcome_dependent", "S17-EXT-008", lambda d, _: d["payload"].__setitem__("outcome_dependent", True))
    reject("ext009_single_custody", "S17-EXT-009", lambda d, _: d["payload"].__setitem__("custody_domains", ["ONLY-ONE"]))
    reject("ext009_permissions_unverified", "S17-EXT-009", lambda d, _: d["payload"].__setitem__("permissions_verified", False))
    reject("ext009_missing_recovery", "S17-EXT-009", lambda d, _: d["artifacts"].pop())
    reject("ext010_missing_predecessor", "S17-EXT-010", lambda d, _: d["payload"].__setitem__("exact_predecessors", d["payload"]["exact_predecessors"][:-1]))
    reject("ext010_wrong_run_set", "S17-EXT-010", lambda d, _: d["payload"].__setitem__("run_ids", ["WRONG-RUN"]))
    reject("ext010_phase18_authority", "S17-EXT-010", lambda d, _: d["payload"].__setitem__("phase18_authority", True))
    reject("cross_version_manifest", "S17-EXT-010", lambda d, _: d.__setitem__("schema_version", "cpu-prefetch-stage17-operational-input-manifest/999"))
    reject("schema_drift_after_admission", "S17-EXT-010", lambda d, _: d.__setitem__("unexpected", True))
    return count


def _exit_and_phase18(builder: Builder) -> tuple[int, int]:
    records_dir = builder.root / "synthetic-exit-records"
    records_dir.mkdir()
    refs: list[dict[str, Any]] = []
    previous = EXIT_GENESIS_SHA256
    sequence = 0

    def record(
        kind: str, payload: dict[str, Any],
        sources: list[tuple[str, pathlib.Path]] | None = None,
    ) -> tuple[pathlib.Path, str]:
        nonlocal sequence, previous
        sequence += 1
        source_bindings = [
            {"artifact_id": artifact_id, "path": str(path),
             "size_bytes": path.stat().st_size, "sha256": sha_file(path)}
            for artifact_id, path in (sources or [])
        ]
        document = {"schema_version": "cpu-prefetch-stage17-pilot-exit-record/1", "record_id": f"SYNTHETIC-EXIT-{sequence:03d}", "record_type": kind, "sequence_number": sequence, "previous_record_sha256": previous, "created_at_utc": utc(30 + sequence), "actor": "synthetic-stage17-owner", "synthetic_test_only": True, "source_bindings": source_bindings, "payload": payload, "automatic_transition": False, "retry_authority": False, "phase18_authority": False}
        path = records_dir / f"record-{sequence:03d}.json"
        write_json(path, document)
        digest = sha_file(path)
        refs.append({"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest})
        previous = digest
        return path, digest

    ext010_path, ext010_document, ext010_sha = builder.resolutions["S17-EXT-010"]
    ext010_authorization = json.loads((builder.root / ext010_document["authorization"]["evidence_path"]).read_text())
    pilot_plan_sha = builder.contexts["S17-EXT-008"]["manifest_sha256"]
    run_ids = builder.contexts["S17-EXT-008"]["run_ids"]
    record("STATE_TRANSITION", {"from_state": "READY_FOR_STAGE17_PHASE_AUTHORIZATION", "to_state": "PILOT_AUTHORIZED", "evidence_record_types": ["S17_EXT_010_ADMITTED"], "admitted_ext010_sha256": ext010_sha, "authority_scope": "STAGE17_EXIT_STATE_ADVANCE_ONLY", "phase18_authority": False}, [("S17-EXT-010-RESOLUTION", ext010_path)])
    marker = builder.root / "evidence/synthetic-pilot-one-shot-marker.json"
    write_json(marker, {"attempt": 1, "synthetic_test_only": True})
    attempt_path, attempt_sha = record("PILOT_ATTEMPT", {"attempt": 1, "retries": 0, "authorization_id": ext010_authorization["authorization_id"], "authorization_sha256": sha_file(builder.root / ext010_document["authorization"]["evidence_path"]), "resolution_id": ext010_document["resolution_id"], "resolution_sha256": ext010_sha, "pilot_plan_sha256": pilot_plan_sha, "run_ids": run_ids, "one_shot_marker_sha256": sha_file(marker), "actual_started_at_utc": utc(31), "authorized_by_ext010": True, "stage18_authority": False}, [("S17-EXT-010-RESOLUTION", ext010_path), ("ONE-SHOT-MARKER", marker)])
    pilot_artifacts: list[pathlib.Path] = []
    receipt_paths: list[pathlib.Path] = []
    receipt_hashes: list[str] = []
    for ordinal, run_id in enumerate(run_ids, start=1):
        pilot_artifact = builder.root / f"evidence/synthetic-pilot-run-{ordinal:03d}.bin"
        pilot_artifact.write_bytes(
            f"synthetic pilot artifact {ordinal}; no empirical result\n".encode()
        )
        receipt_path, receipt_sha = record("PILOT_RECEIPT", {"attempt": 1, "retries": 0, "run_id": run_id, "run_ordinal": ordinal, "artifact_manifest_sha256": sha_file(pilot_artifact), "valid_join": True, "partial": False, "leader_reaped": True, "process_group_gone": True, "actual_started_at_utc": utc(31 + ordinal), "actual_completed_at_utc": utc(32 + ordinal), "stage18_authority": False}, [("PILOT-ATTEMPT", attempt_path), (f"PILOT-RUN-{ordinal:03d}-ARTIFACT", pilot_artifact)])
        pilot_artifacts.append(pilot_artifact)
        receipt_paths.append(receipt_path)
        receipt_hashes.append(receipt_sha)
    completion_path, completion_sha = record("PILOT_COMPLETION", {"completed": True, "attempt": 1, "retries": 0, "run_ids": run_ids, "receipt_sha256s": receipt_hashes, "all_artifacts_immutable": True, "all_leaders_reaped": True, "all_process_groups_gone": True, "stage18_authority": False}, [(f"PILOT-RECEIPT-{index:03d}", path) for index, path in enumerate(receipt_paths, start=1)])
    record("STATE_TRANSITION", {"from_state": "PILOT_AUTHORIZED", "to_state": "PILOT_EXECUTED", "evidence_record_types": ["PILOT_ATTEMPT", "PILOT_RECEIPT", "PILOT_COMPLETION"], "authority_scope": "STAGE17_EXIT_STATE_ADVANCE_ONLY", "phase18_authority": False})
    sealed_path, sealed_sha = record("SEALED_PILOT_ARTIFACT_MANIFEST", {"sealed": True, "checksums_verified": True, "run_ids": run_ids, "artifact_bindings": [{"artifact_id": f"PILOT-RUN-{index:03d}-ARTIFACT", "size_bytes": path.stat().st_size, "sha256": sha_file(path)} for index, path in enumerate(pilot_artifacts, start=1)], "completion_sha256": completion_sha, "sealed_at_utc": utc(34), "stage18_authority": False}, [("PILOT-COMPLETION", completion_path), *((f"PILOT-RUN-{index:03d}-ARTIFACT", path) for index, path in enumerate(pilot_artifacts, start=1))])
    freeze_path, freeze_sha = record("TREATMENT_BLIND_FREEZE", {"treatment_labels_blinded": True, "outcome_accessed": False, "freeze_immutable": True, "pilot_plan_sha256": pilot_plan_sha, "sealed_manifest_sha256": sealed_sha, "created_at_utc": utc(35), "phase18_authority": False}, [("SEALED-PILOT-MANIFEST", sealed_path)])
    record("STATE_TRANSITION", {"from_state": "PILOT_EXECUTED", "to_state": "PILOT_EVIDENCE_SEALED", "evidence_record_types": ["SEALED_PILOT_ARTIFACT_MANIFEST", "TREATMENT_BLIND_FREEZE"], "authority_scope": "STAGE17_EXIT_STATE_ADVANCE_ONLY", "phase18_authority": False})
    record("ROLE_SEPARATION_DECLARATION", {"stage17_single_owner_collapse": True, "distinct_auditor": False, "independent_review": False, "phase18_separate_authority_required": True, "phase18_chronology_strict": True})
    record("STAGE17_COMPLETION_STATEMENT", {"all_ten_inputs_admitted": True, "operational_journal_sha256": sha_file(builder.latest_path), "pilot_completion_sha256": completion_sha, "sealed_manifest_sha256": sealed_sha, "treatment_blind_freeze_sha256": freeze_sha, "pilot_evidence_sealed": True, "completed_at_utc": utc(36), "phase18_authority": False}, [("OPERATIONAL-JOURNAL", builder.latest_path), ("PILOT-COMPLETION", completion_path), ("SEALED-PILOT-MANIFEST", sealed_path), ("TREATMENT-BLIND-FREEZE", freeze_path)])
    record("STATE_TRANSITION", {"from_state": "PILOT_EVIDENCE_SEALED", "to_state": "STAGE17_COMPLETE", "evidence_record_types": ["ROLE_SEPARATION_DECLARATION", "STAGE17_COMPLETION_STATEMENT"], "authority_scope": "STAGE17_EXIT_STATE_ADVANCE_ONLY", "phase18_authority": False})
    record("PHASE18_READINESS_REPORT", {"state": "READY_FOR_SEPARATE_PHASE18_AUTHORIZATION", "blockers": [], "phase18_authority": False})
    record("PHASE18_AUTHORIZATION_DRAFT", {"issued": False, "authorization_id": None, "stage17_authority_reuse_allowed": False})
    record("STATE_TRANSITION", {"from_state": "STAGE17_COMPLETE", "to_state": "PHASE18_HANDOFF_PREPARED", "evidence_record_types": ["PHASE18_READINESS_REPORT", "PHASE18_AUTHORIZATION_DRAFT"], "authority_scope": "STAGE17_EXIT_STATE_ADVANCE_ONLY", "phase18_authority": False})
    exit_journal = builder.root / "synthetic-exit-journal.json"
    write_json(exit_journal, {"schema_version": "cpu-prefetch-stage17-pilot-exit-journal/1", "journal_id": "SYNTHETIC-STAGE17-EXIT-JOURNAL", "initial_state": "READY_FOR_STAGE17_PHASE_AUTHORIZATION", "record_references": refs, "current_state_claim": "PHASE18_HANDOFF_PREPARED", "synthetic_test_only": True, "phase18_authority": False})
    result = validate_exit_journal(repository_root=builder.root, journal_path=exit_journal, allow_synthetic=True)
    if not result.stage17_complete or not result.phase18_handoff_prepared:
        raise CheckError("synthetic exit did not reach the handoff state")

    transitions = []
    previous_transition = PHASE18_GENESIS_SHA256
    for sequence, (source, target) in enumerate(zip(("PLANNED", "COLLECTED_SEALED", "TRAINING_OPEN", "SELECTION_FROZEN", "VALIDATION_UNSEALED", "H3_EVALUATED", "H1H2_RELEASED"), ("COLLECTED_SEALED", "TRAINING_OPEN", "SELECTION_FROZEN", "VALIDATION_UNSEALED", "H3_EVALUATED", "H1H2_RELEASED", "ARCHIVED")), 1):
        transition = {"sequence_number": sequence, "from_state": source, "to_state": target, "previous_transition_sha256": previous_transition, "evidence_sha256s": [f"{sequence:x}" * 64][:1], "actor": "synthetic-phase18-owner", "timestamp_utc": utc(50 + sequence), "authority_scope": "PHASE18_ACCESS_TRANSITION_ONLY", "stage17_authority_used": False, "automatic_transition": False}
        # Use a structurally valid, distinct SHA-256 evidence value.
        transition["evidence_sha256s"] = [hashlib.sha256(str(sequence).encode()).hexdigest()]
        transitions.append(transition)
        previous_transition = sha(canonical(transition))
    phase18 = builder.root / "synthetic-phase18-journal.json"
    write_json(phase18, {"schema_version": "cpu-prefetch-phase18-access-journal/1", "journal_id": "SYNTHETIC-PHASE18-ACCESS", "authorization_id": "SYNTHETIC-SEPARATE-PHASE18-AUTH", "authorization_sha256": "b" * 64, "synthetic_test_only": True, "transitions": transitions, "current_state_claim": "ARCHIVED"})
    if validate_phase18_access_journal(repository_root=builder.root, journal_path=phase18, allow_synthetic=True) != "ARCHIVED":
        raise CheckError("Phase 18 chronology did not reach ARCHIVED")
    mutated = copy.deepcopy(json.loads(phase18.read_text()))
    mutated["transitions"][1]["to_state"] = "VALIDATION_UNSEALED"
    invalid = builder.root / "synthetic-phase18-invalid.json"
    write_json(invalid, mutated)
    _expect_failure("phase18_out_of_order", lambda: validate_phase18_access_journal(repository_root=builder.root, journal_path=invalid, allow_synthetic=True))
    mutated = copy.deepcopy(json.loads(phase18.read_text()))
    mutated["transitions"][0]["stage17_authority_used"] = True
    invalid = builder.root / "synthetic-phase18-stage17-authority.json"
    write_json(invalid, mutated)
    _expect_failure("stage17_authority_in_phase18", lambda: validate_phase18_access_journal(repository_root=builder.root, journal_path=invalid, allow_synthetic=True))
    return 2, 2


def self_test() -> tuple[int, int]:
    with tempfile.TemporaryDirectory(prefix="stage17b-complete-") as temporary:
        builder = Builder(pathlib.Path(temporary))
        validation = builder.build_all()
        if validation.current_state != "READY_FOR_STAGE17_PHASE_AUTHORIZATION" or validation.resolution_count != 10 or validation.transition_count != 3 or not validation.pilot_ready:
            raise CheckError("ten-input production semantic admission did not reach pilot-ready projection")
        print("stage17-complete-admission: PASS positive=ten_inputs_and_three_transitions")

        # One closed-world mutation per input.  Every validation rebuild reads
        # the mutated bytes from disk through the production registry.
        negative = 0
        for index in range(1, 11):
            input_id = f"S17-EXT-{index:03d}"
            path, document, _ = builder.resolutions[input_id]
            original = path.read_bytes()
            mutated = copy.deepcopy(document)
            mutated["stage18_authority"] = True
            path.write_bytes(json.dumps(mutated, sort_keys=True, indent=2).encode() + b"\n")
            _expect_failure(f"{input_id}_authority_expansion", lambda: journal.validate_journal(repository_root=builder.root, latest_journal=builder.latest_path.relative_to(builder.root), journal_directory=builder.root / "config/stage17/journal", pilot_archive=builder.pilot_archive, pilot_sidecar=builder.pilot_sidecar, as_of_utc=utc(15), allow_synthetic_test_evidence=True))
            path.write_bytes(original)
            negative += 1

        negative += _semantic_negative_cases(builder)
        # A production admission call must reject every synthetic record.
        _expect_failure("synthetic_without_test_gate", lambda: journal.validate_journal(repository_root=builder.root, latest_journal=builder.latest_path.relative_to(builder.root), journal_directory=builder.root / "config/stage17/journal", pilot_archive=builder.pilot_archive, pilot_sidecar=builder.pilot_sidecar, as_of_utc=utc(15), allow_synthetic_test_evidence=False))
        negative += 1
        exit_positive, exit_negative = _exit_and_phase18(builder)
        return 1 + exit_positive, negative + exit_negative


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true", required=True)
    parser.parse_args()
    try:
        positive, negative = self_test()
    except BaseException as exception:
        print(f"stage17-complete-admission: FAIL: {exception}", file=sys.stderr)
        return 1
    print(f"stage17-complete-admission: PASS positive={positive} negative={negative} mechanics_bypass=false checked_in_journal_unchanged=true stand=NOT_ACCESSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
