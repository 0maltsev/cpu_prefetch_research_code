#!/usr/bin/env python3
"""Validate and disk-test the append-only Stage 17 state journal."""

from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import stat
import sys
import tempfile
import threading
from unittest import mock
from typing import Any

from stage17_state_journal import (
    ADR_0105_PATH,
    FIXED_PREFLIGHT_OBSERVATION_IDS,
    GENESIS_PATH,
    LEGACY_TEMPLATE_PATHS,
    PINNED_HOST_KEY_SCHEMA_PATH,
    READ_ONLY_PERMISSION_MATRIX,
    SCHEMA_PATHS,
    SEMANTIC_ENVELOPE_SCHEMA_PATH,
    SEMANTIC_POLICY_PATH,
    SEMANTIC_POLICY_SCHEMA_PATH,
    S17_EXT_001_AUTHORIZATION_SCHEMA_PATH,
    S17_EXT_001_CONTRACT_SCHEMA_PATH,
    ExternalInputResolution,
    JournalError,
    canonical_json_bytes,
    load_json,
    parse_utc,
    record_from_ref,
    repository_file,
    sha256_bytes,
    sha256_file,
    validate_graph_catalog,
    validate_journal,
    validate_journal_lineage,
    validate_schema,
    validate_transitions,
    version_hashes,
)
from stage17_semantic_verifier_v4 import (
    ACTION_PLAN_PATH,
    ADR_0107_PATH,
    ADR_0108_PATH,
    ATTEMPT_SCHEMA_PATH,
    COLLECTOR_PATH,
    COMPLETION_SCHEMA_PATH,
    EXECUTOR_PATH,
    FAILURE_SCHEMA_PATH,
    IMPLEMENTATION_PATHS,
    POLICY_V3_PATH,
    RECEIPT_SCHEMA_PATH,
    V4_SCHEMA_PATHS,
)
import stage17_read_only_preflight_executor_v2 as production_executor
import stage17_read_only_preflight_collector_v2 as production_collector
from stage17_read_only_preflight_collector_v2 import render_observation_program


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_JOURNAL = pathlib.Path(
    "config/stage17/journal/stage17-state-journal-000000.json"
)
DRAFT_PATH = pathlib.Path(
    "config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v4.json"
)
LEGACY_DRAFT_PATH = pathlib.Path(
    "config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v1.json"
)
GRAPH_PATH = pathlib.Path(
    "config/stage17/stage17-operational-graph-definition-v1.json"
)
CATALOG_PATH = pathlib.Path(
    "config/stage17/stage17-external-input-catalog-v1.json"
)
PILOT_CONTRACT_PATH = pathlib.Path(
    "config/stage17/stage17-pilot-candidate-external-contract-v1.json"
)
PILOT_CONTRACT_SCHEMA_PATH = pathlib.Path(
    "config/schemas/stage17-pilot-candidate-external-contract-v1.schema.json"
)
PILOT_VERIFIER_PATH = pathlib.Path("tools/stage17_pilot_candidate_artifact.py")
BASE_TIME = "2030-01-01"
LEGACY_DRAFT_SHA256 = "012646a0a7eba1d0f1d25cd7f08f1855241d5efe720bb4f6ce38710fde7cd462"
PREDECESSOR_DRAFT_V3_PATH = pathlib.Path(
    "config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v3.json"
)


def write_json(path: pathlib.Path, document: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode(
                "utf-8"
            )
        )
        stream.write(b"\n")


def copy_file(source: pathlib.Path, destination: pathlib.Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def utc(minute: int) -> str:
    hour, minute_in_hour = divmod(minute, 60)
    return f"{BASE_TIME}T{hour:02d}:{minute_in_hour:02d}:00Z"


def b64(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


class SyntheticBuilder:
    """Write immutable fixtures and journal successors to a real temporary tree."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        for relative in (
            *SCHEMA_PATHS.values(),
            *LEGACY_TEMPLATE_PATHS.values(),
            ADR_0105_PATH.as_posix(),
            GRAPH_PATH.as_posix(),
            CATALOG_PATH.as_posix(),
            LEGACY_DRAFT_PATH.as_posix(),
            "config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v2.json",
            PREDECESSOR_DRAFT_V3_PATH.as_posix(),
            DRAFT_PATH.as_posix(),
            PILOT_CONTRACT_PATH.as_posix(),
            PILOT_CONTRACT_SCHEMA_PATH.as_posix(),
            PILOT_VERIFIER_PATH.as_posix(),
            POLICY_V3_PATH,
            ADR_0107_PATH,
            ADR_0108_PATH,
            "config/stage17/stage17-read-only-preflight-fixed-action-plan-v1.json",
            ACTION_PLAN_PATH,
            *IMPLEMENTATION_PATHS.values(),
            *V4_SCHEMA_PATHS,
            SEMANTIC_POLICY_PATH.as_posix(),
            SEMANTIC_POLICY_SCHEMA_PATH.as_posix(),
            SEMANTIC_ENVELOPE_SCHEMA_PATH.as_posix(),
            S17_EXT_001_AUTHORIZATION_SCHEMA_PATH.as_posix(),
            S17_EXT_001_CONTRACT_SCHEMA_PATH.as_posix(),
            PINNED_HOST_KEY_SCHEMA_PATH.as_posix(),
            ATTEMPT_SCHEMA_PATH,
            RECEIPT_SCHEMA_PATH,
            FAILURE_SCHEMA_PATH,
            COMPLETION_SCHEMA_PATH,
        ):
            copy_file(ROOT / relative, root / relative)
        self.graph = load_json(root / GRAPH_PATH)
        self.catalog = load_json(root / CATALOG_PATH)
        self.graph_sha256 = sha256_file(root / GRAPH_PATH)
        self.catalog_sha256 = sha256_file(root / CATALOG_PATH)
        self.versions = version_hashes(root)
        self.genesis_record = {
            "journal_id": "STAGE17-STATE-JOURNAL-v1",
            "protocol_version": "2.0.0-pre.2",
            "initial_state": "PREPARED",
            "graph_sha256": self.graph_sha256,
            "catalog_sha256": self.catalog_sha256,
            "version_hashes": self.versions,
            "authority_scope": "NO_EXECUTION_AUTHORITY",
        }
        self.genesis_sha256 = sha256_bytes(canonical_json_bytes(self.genesis_record))
        self.latest_document: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-state-journal/1",
            "journal_id": "STAGE17-STATE-JOURNAL-v1",
            "journal_sequence_number": 0,
            "protocol_version": "2.0.0-pre.2",
            "previous_journal": None,
            "graph": {"path": GRAPH_PATH.as_posix(), "sha256": self.graph_sha256},
            "catalog": {
                "path": CATALOG_PATH.as_posix(),
                "sha256": self.catalog_sha256,
            },
            "version_hashes": self.versions,
            "genesis": {
                "hash_algorithm": "SHA-256-CANONICAL-JSON-v1",
                "initial_state": "PREPARED",
                "genesis_record": self.genesis_record,
                "genesis_sha256": self.genesis_sha256,
            },
            "resolution_records": [],
            "transition_records": [],
            "authority_boundary": {
                "automatic_transition": False,
                "retry_allowed": False,
                "stage18_authority": False,
            },
        }
        self.latest_path = (
            root / "config/stage17/journal/stage17-state-journal-000000.json"
        )
        write_json(self.latest_path, self.latest_document)
        self.resolutions: dict[str, tuple[pathlib.Path, dict[str, Any], str]] = {}
        self.previous_transition_sha256 = self.genesis_sha256
        self.transition_count = 0
        self.pilot_archive: pathlib.Path | None = None
        self.pilot_sidecar: pathlib.Path | None = None
        self._external_temporary = tempfile.TemporaryDirectory(
            prefix="stage17-action-fixture-"
        )
        self.external_root = pathlib.Path(self._external_temporary.name)

    def append_snapshot(
        self, kind: str, reference: dict[str, str], *, previous: pathlib.Path | None = None
    ) -> pathlib.Path:
        predecessor_path = previous or self.latest_path
        predecessor = load_json(predecessor_path)
        document = copy.deepcopy(predecessor)
        sequence = int(predecessor["journal_sequence_number"]) + 1
        document["journal_sequence_number"] = sequence
        document["previous_journal"] = {
            "path": predecessor_path.relative_to(self.root).as_posix(),
            "sha256": sha256_file(predecessor_path),
        }
        document[kind].append(reference)
        path = (
            self.root
            / "config/stage17/journal"
            / f"stage17-state-journal-{sequence:06d}.json"
        )
        write_json(path, document)
        if previous is None:
            self.latest_path = path
            self.latest_document = document
        return path

    def repository_evidence(self, input_id: str, document: object) -> dict[str, Any]:
        path = self.root / "evidence" / f"{input_id.lower()}-repository.json"
        write_json(path, document)
        return {
            "kind": "REPOSITORY_FILE",
            "path": path.relative_to(self.root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    def s17_ext_001_evidence(
        self,
        actor: str,
        *,
        contract_mutator=None,
        authorization_mutator=None,
        envelope_mutator=None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        pinned_path = self.root / "synthetic/pinned-host-key.json"
        pinned_path.parent.mkdir(parents=True, exist_ok=True)
        key_type = b"ssh-ed25519"
        public_key = bytes(range(32))
        synthetic_host_key = (
            len(key_type).to_bytes(4, "big")
            + key_type
            + len(public_key).to_bytes(4, "big")
            + public_key
        )
        fingerprint = "SHA256:" + base64.b64encode(
            hashlib.sha256(synthetic_host_key).digest()
        ).decode("ascii").rstrip("=")
        write_json(
            pinned_path,
            {
                "schema_version": "cpu-prefetch-stage17-pinned-host-key-evidence/1",
                "evidence_id": "SYNTHETIC-PINNED-HOST-KEY-NO-AUTHORITY",
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "ssh_target": "synthetic@synthetic.invalid",
                "algorithm": "ssh-ed25519",
                "public_key_base64": base64.b64encode(synthetic_host_key).decode("ascii"),
                "fingerprint_sha256": fingerprint,
                "source": "OWNER_PROVIDED_OUT_OF_BAND_PIN",
                "runtime_observation": False,
            },
        )
        known_hosts_path = self.root / "synthetic/pinned.known_hosts"
        known_hosts_path.write_bytes(
            b"synthetic.invalid ssh-ed25519 "
            + base64.b64encode(synthetic_host_key)
            + b"\n"
        )
        transport_identity = self.external_root / "synthetic-transport-identity"
        transport_identity.write_bytes(b"synthetic non-key transport fixture\n")
        transport_identity.chmod(0o600)
        launcher_path = pathlib.Path(production_executor.__file__).resolve()
        collector_path = pathlib.Path(production_collector.__file__).resolve()
        evidence_root = self.external_root / "evidence-root"
        evidence_root.mkdir(mode=0o700)
        policy = load_json(self.root / SEMANTIC_POLICY_PATH)
        action_plan_binding = {
            **policy["fixed_action_plan"],
            "schema_identity": (
                "cpu-prefetch-stage17-read-only-preflight-fixed-action-plan/2"
            ),
        }
        pilot_fixed = self.catalog["fixed_evidence_contracts"][0]
        identities = [
            {
                "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_EXECUTOR",
                "role": "EXECUTOR",
                "execution_path": str(launcher_path),
                "source_binding": copy.deepcopy(policy["implementations"]["executor"]),
            },
            {
                "identity_id": "STAGE17_READ_ONLY_PREFLIGHT_COLLECTOR",
                "role": "COLLECTOR",
                "execution_path": str(collector_path),
                "source_binding": copy.deepcopy(policy["implementations"]["collector"]),
            },
        ]
        contract: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-supporting-contract/4",
            "contract_id": "SYNTHETIC-S17-EXT-001-SUPPORTING-CONTRACT-NO-AUTHORITY",
            "protocol_version": "2.0.0-pre.2",
            "fixed_action_plan": action_plan_binding,
            "target": {
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "ssh_target": "synthetic@synthetic.invalid",
                "known_hosts_host": "synthetic.invalid",
                "pinned_host_key_evidence": {
                    "path": pinned_path.relative_to(self.root).as_posix(),
                    "size_bytes": pinned_path.stat().st_size,
                    "sha256": sha256_file(pinned_path),
                    "schema_identity": (
                        "cpu-prefetch-stage17-pinned-host-key-evidence/1"
                    ),
                },
                "pinned_known_hosts": {
                    "path": known_hosts_path.relative_to(self.root).as_posix(),
                    "size_bytes": known_hosts_path.stat().st_size,
                    "sha256": sha256_file(known_hosts_path),
                },
                "transport_identity_locator": str(transport_identity),
            },
            "pilot_candidate": {
                "contract": {
                    "path": pilot_fixed["path"],
                    "size_bytes": pilot_fixed["size_bytes"],
                    "sha256": pilot_fixed["sha256"],
                    "schema_identity": (
                        "cpu-prefetch-stage17-pilot-candidate-external-contract/1"
                    ),
                },
                "archive_locator": "/synthetic/custody/pilot-candidate.tar.gz",
                "sidecar_locator": "/synthetic/custody/pilot-candidate.tar.gz.sha256",
                "bundle_root_locator": "/synthetic/stand/extracted-pilot-candidate",
            },
            "capture": {
                "capture_id": "SYNTHETIC-S17-PREFLIGHT-NO-AUTHORITY",
                "captured_at_utc": utc(21),
            },
            "evidence_root": str(evidence_root),
            "prospective_local_action_identities": identities,
            "remote_runtime_identity_policy": {
                "source_input_id": "S17-EXT-002",
                "identity_classes": [
                    "REMOTE_EXECUTABLE",
                    "REMOTE_MODULE",
                    "REMOTE_DEPENDENCY",
                ],
                "prospective_values_present": False,
            },
            "limits": {
                "max_commands": 6,
                "max_wall_seconds": 180,
                "max_total_output_bytes": 6291456,
                "max_output_bytes_per_observation": 1048576,
                "timeout_seconds_per_observation": 30,
                "attempts_per_observation": 1,
                "retries": 0,
            },
            "stop_policy": "STOP_ON_FIRST_MISMATCH_NONZERO_EXIT_TIMEOUT_OR_OUTPUT_LIMIT",
            "retention_policy": (
                "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_FAILURE_AND_PARTIAL_NO_DELETE"
            ),
            "authority_boundary": copy.deepcopy(READ_ONLY_PERMISSION_MATRIX),
        }
        if contract_mutator is not None:
            contract_mutator(contract)
        contract_path = self.root / "evidence/s17-ext-001-supporting-contract-v4.json"
        write_json(contract_path, contract)
        contract_binding = {
            "path": contract_path.relative_to(self.root).as_posix(),
            "size_bytes": contract_path.stat().st_size,
            "sha256": sha256_file(contract_path),
            "schema_identity": (
                "cpu-prefetch-stage17-read-only-preflight-supporting-contract/4"
            ),
        }
        authorization: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-authorization/4",
            "authorization_id": "SYNTHETIC-S17-EXT-001-AUTHORIZATION-NO-AUTHORITY",
            "attempt_id": "SYNTHETIC-S17-EXT-001-ATTEMPT-NO-AUTHORITY",
            "input_id": "S17-EXT-001",
            "actor": actor,
            "issued_at_utc": utc(0),
            "expires_at_utc": "2030-01-02T00:00:00Z",
            "authority_scope": "READ_ONLY_PREFLIGHT",
            "target_scope": (
                "STAND_ID=SYNTHETIC-STAND-NOT-ACCESSED;"
                "SSH_TARGET=synthetic@synthetic.invalid;SCOPE=READ_ONLY_PREFLIGHT;"
                "PLAN=STAGE17-READ-ONLY-PREFLIGHT-FIXED-ACTION-PLAN-v2"
            ),
            "target": {
                "stand_id": contract["target"]["stand_id"],
                "ssh_target": contract["target"]["ssh_target"],
                "known_hosts_host": contract["target"]["known_hosts_host"],
                "pinned_host_key_evidence_sha256": contract["target"][
                    "pinned_host_key_evidence"
                ]["sha256"],
                "pinned_known_hosts_sha256": contract["target"][
                    "pinned_known_hosts"
                ]["sha256"],
            },
            "frozen_observation_ids": list(FIXED_PREFLIGHT_OBSERVATION_IDS),
            "fixed_action_plan": action_plan_binding,
            "supporting_observation_contract": contract_binding,
            "evidence_root": str(evidence_root),
            "limits": copy.deepcopy(contract["limits"]),
            "role_collapse_acknowledged": True,
            "independent_review_claimed": False,
            "permissions": copy.deepcopy(READ_ONLY_PERMISSION_MATRIX),
            "automatic_transition": False,
            "retry_allowed": False,
            "stage18_authority": False,
        }
        if authorization_mutator is not None:
            authorization_mutator(authorization)
        authorization_path = self.root / "evidence/s17-ext-001-authorization-v4.json"
        write_json(authorization_path, authorization)
        authorization_binding = {
            "path": authorization_path.relative_to(self.root).as_posix(),
            "size_bytes": authorization_path.stat().st_size,
            "sha256": sha256_file(authorization_path),
            "schema_identity": "cpu-prefetch-stage17-read-only-preflight-authorization/4",
        }
        policy_path = self.root / SEMANTIC_POLICY_PATH
        envelope: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/4",
            "envelope_id": "SYNTHETIC-S17-EXT-001-SEMANTIC-ENVELOPE-NO-AUTHORITY",
            "input_id": "S17-EXT-001",
            "predecessor": {
                "graph_sha256": self.graph_sha256,
                "catalog_sha256": self.catalog_sha256,
                "genesis_sha256": self.genesis_sha256,
                "resolution_schema_identity": (
                    "cpu-prefetch-stage17-external-input-resolution/1"
                ),
                "resolution_schema_sha256": self.versions[
                    "resolution_schema_sha256"
                ],
                "semantic_policy_v3_sha256": policy["predecessor"]["policy_v3"][
                    "sha256"
                ],
                "adr_0107_sha256": policy["predecessor"]["adr_0107"]["sha256"],
                "adr_0108_sha256": policy["predecessor"]["adr_0108"]["sha256"],
            },
            "semantic_policy": {
                "path": SEMANTIC_POLICY_PATH.as_posix(),
                "size_bytes": policy_path.stat().st_size,
                "sha256": sha256_file(policy_path),
            },
            "semantic_verifier": {
                "verifier_id": "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER",
                "verifier_version": "4",
            },
            "authorization": authorization_binding,
            "supporting_contract": contract_binding,
            "fixed_action_plan": action_plan_binding,
            "runtime_implementations": copy.deepcopy(policy["implementations"]),
            "stage18_authority": False,
        }
        if envelope_mutator is not None:
            envelope_mutator(envelope)
        envelope_path = self.root / "evidence/s17-ext-001-semantic-envelope-v4.json"
        write_json(envelope_path, envelope)
        evidence = {
            "kind": "REPOSITORY_FILE",
            "path": envelope_path.relative_to(self.root).as_posix(),
            "size_bytes": envelope_path.stat().st_size,
            "sha256": sha256_file(envelope_path),
        }
        return authorization, evidence

    def authorization_document(self, input_id: str, actor: str) -> dict[str, Any]:
        scopes = {
            "S17-EXT-001": "READ_ONLY_PREFLIGHT",
            "S17-EXT-005": "PRIVILEGED_QUALIFICATION_CONTROL",
            "S17-EXT-010": "STAGE17_PILOT_PHASE_ONLY",
        }
        permissions = {
            "stand_read_only": True,
            "stand_mutation": input_id == "S17-EXT-005",
            "privileged_controls": input_id == "S17-EXT-005",
            "calibration": False,
            "pilot_execution": input_id == "S17-EXT-010",
            "stage18_authority": False,
        }
        return {
            "schema_version": "cpu-prefetch-stage17-operational-authorization-evidence/1",
            "authorization_id": f"SYNTHETIC-{input_id}-AUTHORIZATION",
            "input_id": input_id,
            "actor": actor,
            "issued_at_utc": utc(0),
            "expires_at_utc": "2030-01-02T00:00:00Z",
            "authority_scope": scopes[input_id],
            "target_scope": f"SYNTHETIC-{input_id}-TARGET",
            "frozen_observation_ids": [f"SYNTHETIC-{input_id}-OBSERVATION"],
            "limits": {
                "max_commands": 1,
                "max_wall_seconds": 60,
                "attempts_per_observation": 1,
                "retries": 0,
            },
            "role_collapse_acknowledged": True,
            "independent_review_claimed": False,
            "permissions": permissions,
        }

    def external_receipt(
        self, input_id: str, sequence: int, *, pilot_candidate: bool = False
    ) -> dict[str, Any]:
        if pilot_candidate:
            artifact = self.root / "external" / "synthetic-pilot.tar.gz"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"synthetic-pilot-candidate-archive\n")
            artifact_sha256 = sha256_file(artifact)
            sidecar = self.root / "external" / "synthetic-pilot.tar.gz.sha256"
            sidecar.write_bytes(
                f"{artifact_sha256}  {artifact.name}\n".encode("ascii")
            )
            fixed_contract = self.catalog["fixed_evidence_contracts"][0]
            contract_path = self.root / fixed_contract["path"]
            self.pilot_archive = artifact
            self.pilot_sidecar = sidecar
            verifier_id = "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
            verifier_version = "1"
            sidecars = [
                {
                    "locator": str(sidecar),
                    "size_bytes": sidecar.stat().st_size,
                    "sha256": sha256_file(sidecar),
                }
            ]
        else:
            contract_path = self.root / "evidence/synthetic-external-contract.json"
            if not contract_path.exists():
                write_json(contract_path, {"contract_id": "SYNTHETIC-EXTERNAL-CONTRACT"})
            payload = f"synthetic-external-{input_id}\n".encode("utf-8")
            artifact = self.root / "external" / f"{input_id.lower()}.bin"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(payload)
            artifact_sha256 = sha256_bytes(payload)
            verifier_id = "SYNTHETIC-EXTERNAL-VERIFIER"
            verifier_version = "1"
            sidecars = []
        receipt = {
            "schema_version": "cpu-prefetch-stage17-external-custody-receipt/1",
            "receipt_id": f"SYNTHETIC-{input_id}-RECEIPT",
            "artifact_locator": str(artifact),
            "artifact_size_bytes": artifact.stat().st_size,
            "artifact_sha256": artifact_sha256,
            "sidecars": sidecars,
            "custody_domain_id": "SYNTHETIC-CUSTODY",
            "verifier_id": verifier_id,
            "verifier_version": verifier_version,
            "verification_result": "PASS",
            "verified_at_utc": utc(sequence),
            "contract_path": contract_path.relative_to(self.root).as_posix(),
            "contract_sha256": sha256_file(contract_path),
        }
        receipt_path = self.root / "evidence" / f"{input_id.lower()}-receipt.json"
        write_json(receipt_path, receipt)
        return {
            "kind": "EXTERNAL_CUSTODY_RECEIPT",
            "receipt_path": receipt_path.relative_to(self.root).as_posix(),
            "receipt_size_bytes": receipt_path.stat().st_size,
            "receipt_sha256": sha256_file(receipt_path),
        }

    def add_resolution(
        self,
        input_id: str,
        *,
        evidence_override: list[dict[str, Any]] | None = None,
        resolution_id: str | None = None,
        extra_fields: dict[str, Any] | None = None,
        contract_mutator=None,
        authorization_mutator=None,
        envelope_mutator=None,
    ) -> dict[str, Any]:
        sequence = len(self.resolutions) + 1
        actor = "synthetic-stage17-owner"
        item = next(entry for entry in self.catalog["items"] if entry["input_id"] == input_id)
        authorization_document: dict[str, Any] | None = None
        authorization_evidence: dict[str, Any] | None = None
        if input_id == "S17-EXT-001":
            authorization_document, authorization_evidence = self.s17_ext_001_evidence(
                actor,
                contract_mutator=contract_mutator,
                authorization_mutator=authorization_mutator,
                envelope_mutator=envelope_mutator,
            )
        elif item["authorization_required"]:
            authorization_document = self.authorization_document(input_id, actor)
            authorization_evidence = self.repository_evidence(
                input_id, authorization_document
            )
        if evidence_override is not None:
            evidence = evidence_override
        elif item["evidence_policy"] == "REPOSITORY_FILE":
            evidence = [
                authorization_evidence
                or self.repository_evidence(
                    input_id, {"synthetic_input_id": input_id, "accepted": True}
                )
            ]
        elif item["evidence_policy"] == "EXTERNAL_CUSTODY_RECEIPT":
            evidence = [
                self.external_receipt(
                    input_id, sequence, pilot_candidate=input_id == "S17-EXT-006"
                )
            ]
        else:
            evidence = [
                authorization_evidence
                or self.repository_evidence(
                    input_id, {"synthetic_input_id": input_id, "accepted": True}
                ),
                self.external_receipt(input_id, sequence),
            ]
        authorization = None
        if authorization_document is not None and authorization_evidence is not None:
            authorization = {
                "authorization_id": authorization_document["authorization_id"],
                "evidence_path": (
                    "evidence/s17-ext-001-authorization-v4.json"
                    if input_id == "S17-EXT-001"
                    else authorization_evidence["path"]
                ),
                "issued_at_utc": authorization_document["issued_at_utc"],
                "expires_at_utc": authorization_document["expires_at_utc"],
                "authority_scope": authorization_document["authority_scope"],
            }
        document: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-external-input-resolution/1",
            "resolution_id": resolution_id or f"SYNTHETIC-{input_id}-RESOLUTION",
            "sequence_number": sequence,
            "input_id": input_id,
            "actor": actor,
            "recorded_at_utc": utc(sequence + 1),
            "graph_sha256": self.graph_sha256,
            "catalog_sha256": self.catalog_sha256,
            "version_hashes": self.versions,
            "evidence": evidence,
            "authorization": authorization,
            "verification_result": "PASS",
            "automatic_resolution": False,
            "retry_authority": False,
            "stage18_authority": False,
        }
        if extra_fields:
            document.update(extra_fields)
        path = self.root / "records" / f"resolution-{sequence:03d}.json"
        write_json(path, document)
        digest = sha256_file(path)
        reference = {"path": path.relative_to(self.root).as_posix(), "sha256": digest}
        self.append_snapshot("resolution_records", reference)
        self.resolutions[input_id] = (path, document, digest)
        return document

    def add_transition(self, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        sequence = self.transition_count + 1
        edge = self.graph["transitions"][min(sequence - 1, 2)]
        evidence = [
            {
                "input_id": input_id,
                "resolution_id": self.resolutions[input_id][1]["resolution_id"],
                "sha256": self.resolutions[input_id][2],
            }
            for input_id in edge["required_input_ids"]
            if input_id in self.resolutions
        ]
        authorizations = []
        for input_id in edge["authorization_input_ids"]:
            if input_id not in self.resolutions:
                continue
            resolution = self.resolutions[input_id][1]
            authorization = resolution.get("authorization")
            if isinstance(authorization, dict):
                authorizations.append(
                    {
                        "input_id": input_id,
                        "resolution_id": resolution["resolution_id"],
                        "authorization_id": authorization["authorization_id"],
                        "authority_scope": authorization["authority_scope"],
                    }
                )
        document: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-state-transition/1",
            "transition_id": f"SYNTHETIC-STAGE17-TRANSITION-{sequence:03d}",
            "sequence_number": sequence,
            "from_state": edge["from_state"],
            "to_state": edge["to_state"],
            "previous_transition_sha256": self.previous_transition_sha256,
            "actor": "synthetic-stage17-owner",
            "timestamp_utc": utc(20 + sequence),
            "evidence_resolutions": evidence,
            "authorizations": authorizations,
            "graph_sha256": self.graph_sha256,
            "catalog_sha256": self.catalog_sha256,
            "version_hashes": self.versions,
            "authority_scope": edge["authority_scope"],
            "automatic_transition": False,
            "retry_allowed": False,
            "stage18_authority": False,
        }
        if overrides:
            document.update(overrides)
        path = self.root / "records" / f"transition-{sequence:03d}.json"
        write_json(path, document)
        digest = sha256_file(path)
        reference = {"path": path.relative_to(self.root).as_posix(), "sha256": digest}
        self.append_snapshot("transition_records", reference)
        self.previous_transition_sha256 = digest
        self.transition_count += 1
        return document

    def validate(
        self,
        *,
        as_of_utc: str | None = None,
        requested_action_input_id: str | None = None,
    ):
        return validate_journal(
            repository_root=self.root,
            latest_journal=self.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            pilot_archive=self.pilot_archive,
            pilot_sidecar=self.pilot_sidecar,
            as_of_utc=as_of_utc,
            requested_action_input_id=requested_action_input_id,
            runtime_identity_paths=(
                production_executor.runtime_identity_paths()
                if requested_action_input_id == "S17-EXT-001"
                else None
            ),
        )

    def validate_mechanics(self) -> tuple[str, int, int]:
        """Exercise storage/replay mechanics without admitting operational evidence."""
        lineage, latest = validate_journal_lineage(
            self.root,
            self.latest_path.relative_to(self.root),
            self.root / SCHEMA_PATHS["journal_schema_sha256"],
            self.root / "config/stage17/journal",
        )
        graph, _, graph_sha256, catalog_sha256, expected_versions = (
            validate_graph_catalog(self.root, latest)
        )
        mechanical_resolutions: dict[str, ExternalInputResolution] = {}
        schema_path = self.root / SCHEMA_PATHS["resolution_schema_sha256"]
        for expected_sequence, reference in enumerate(
            latest["resolution_records"], start=1
        ):
            path, document, digest = record_from_ref(
                self.root, reference, "mechanical resolution fixture"
            )
            validate_schema(document, schema_path, "mechanical resolution fixture")
            if document.get("sequence_number") != expected_sequence:
                raise JournalError("mechanical fixture resolution sequence drifted")
            input_id = str(document["input_id"])
            mechanical_resolutions[input_id] = ExternalInputResolution(
                resolution_id=str(document["resolution_id"]),
                sequence_number=expected_sequence,
                input_id=input_id,
                actor=str(document["actor"]),
                recorded_at_utc=parse_utc(
                    document["recorded_at_utc"], "mechanical resolution time"
                ),
                path=path,
                sha256=digest,
                document=document,
                authorization_document=None,
                semantic_context=None,
            )
        current_state, transitions = validate_transitions(
            root=self.root,
            references=latest["transition_records"],
            graph=graph,
            graph_sha256=graph_sha256,
            catalog_sha256=catalog_sha256,
            expected_versions=expected_versions,
            genesis_sha256=self.genesis_sha256,
            resolutions=mechanical_resolutions,
        )
        return current_state, len(mechanical_resolutions), len(transitions)


def expect_failure(label: str, action) -> None:
    try:
        action()
    except (JournalError, OSError, json.JSONDecodeError):
        return
    raise JournalError(f"negative self-test passed unexpectedly: {label}")


def validate_s17_ext_001_draft(root: pathlib.Path, journal_path: pathlib.Path) -> None:
    if sha256_file(repository_file(root, LEGACY_DRAFT_PATH.as_posix())) != (
        LEGACY_DRAFT_SHA256
    ):
        raise JournalError("immutable S17-EXT-001 draft v1 drifted")
    draft = load_json(repository_file(root, DRAFT_PATH.as_posix()))
    del journal_path
    if (
        draft.get("schema_version")
        != "cpu-prefetch-stage17-s17-ext-001-authorization-draft/4"
        or draft.get("status") != "DRAFT_NOT_ISSUED_OWNER_INPUT_REQUIRED"
        or draft.get("authority_boundary")
        != {
            "stand_access": False,
            "preflight": False,
            "stand_mutation": False,
            "calibration": False,
            "pilot": False,
            "stage18": False,
        }
    ):
        raise JournalError("S17-EXT-001 draft claims authority")
    bindings = draft.get("compatibility", {})
    policy_path = repository_file(root, SEMANTIC_POLICY_PATH.as_posix())
    predecessor_v3 = PREDECESSOR_DRAFT_V3_PATH.as_posix()
    if (
        bindings.get("predecessor_draft_path") != predecessor_v3
        or bindings.get("predecessor_draft_sha256")
        != sha256_file(repository_file(root, predecessor_v3))
        or bindings.get("semantic_policy_path") != SEMANTIC_POLICY_PATH.as_posix()
        or bindings.get("semantic_policy_size_bytes") != policy_path.stat().st_size
        or bindings.get("semantic_policy_sha256") != sha256_file(policy_path)
    ):
        raise JournalError("S17-EXT-001 draft compatibility binding drifted")
    payload = draft.get("authorization_payload", {})
    if (
        payload.get("input_id") != "S17-EXT-001"
        or payload.get("authority_scope") != "READ_ONLY_PREFLIGHT"
        or tuple(payload.get("frozen_observation_ids", ()))
        != FIXED_PREFLIGHT_OBSERVATION_IDS
        or payload.get("permissions") != READ_ONLY_PERMISSION_MATRIX
        or payload.get("limits", {}).get("max_commands") != 6
        or payload.get("limits", {}).get("attempts_per_observation") != 1
        or payload.get("limits", {}).get("retries") != 0
        or payload.get("automatic_transition") is not False
        or payload.get("retry_allowed") is not False
        or payload.get("stage18_authority") is not False
    ):
        raise JournalError("S17-EXT-001 draft fixed authorization scope drifted")
    for field in (
        "authorization_id",
        "attempt_id",
        "actor",
        "issued_at_utc",
        "expires_at_utc",
        "target_scope",
        "evidence_root",
    ):
        if payload.get(field) is not None:
            raise JournalError(f"S17-EXT-001 draft fabricated owner field: {field}")
    supporting = draft.get("supporting_observation_contract", {})
    if (
        "observations" in supporting
        or draft.get("owner_command_argv_or_stdin_fields") != []
    ):
        raise JournalError("S17-EXT-001 v4 draft exposes owner command bytes")
    if supporting.get("remote_runtime_identity_policy") != {
        "source_input_id": "S17-EXT-002",
        "identity_classes": [
            "REMOTE_EXECUTABLE",
            "REMOTE_MODULE",
            "REMOTE_DEPENDENCY",
        ],
        "prospective_values_present": False,
    }:
        raise JournalError("S17-EXT-001 draft runtime identity boundary drifted")
    owner_values = [
        payload.get("target", {}).get(field)
        for field in (
            "stand_id",
            "ssh_target",
            "known_hosts_host",
            "pinned_host_key_evidence_sha256",
            "pinned_known_hosts_sha256",
        )
    ]
    owner_values.extend(
        payload.get("supporting_observation_contract", {}).get(field)
        for field in ("path", "size_bytes", "sha256")
    )
    owner_values.extend(
        supporting.get("target", {}).get(field)
        for field in (
            "stand_id",
            "ssh_target",
            "known_hosts_host",
            "transport_identity_locator",
        )
    )
    owner_values.extend(
        supporting.get("target", {})
        .get("pinned_host_key_evidence", {})
        .get(field)
        for field in ("path", "size_bytes", "sha256")
    )
    owner_values.extend(
        supporting.get("target", {}).get("pinned_known_hosts", {}).get(field)
        for field in ("path", "size_bytes", "sha256")
    )
    owner_values.extend(
        supporting.get("pilot_candidate", {}).get(field)
        for field in ("archive_locator", "sidecar_locator", "bundle_root_locator")
    )
    owner_values.extend(
        supporting.get("capture", {}).get(field)
        for field in ("capture_id", "captured_at_utc")
    )
    owner_values.append(supporting.get("evidence_root"))
    owner_values.extend(
        identity.get(field)
        for identity in supporting.get("prospective_local_action_identities", [])
        for field in ("execution_path",)
    )
    if any(value is not None for value in owner_values):
        raise JournalError("S17-EXT-001 draft fabricated target or observation data")
    if draft.get("runtime_boundary") != {
        "caller_controlled_execution_time": False,
        "actual_system_utc_required_before_marker": True,
        "loaded_runtime_identity_required": True,
        "openssh_option_expansion_allowed": False,
        "pre_marker_render_and_compile_count": 6,
        "durable_marker_file_and_parent_fsync": True,
        "global_monotonic_deadline_seconds": 180,
    }:
        raise JournalError("S17-EXT-001 v4 runtime boundary drifted")


def positive_disk_test() -> tuple[int, int, int, int]:
    with tempfile.TemporaryDirectory(prefix="stage17-semantic-positive-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        genesis = builder.validate()
        if genesis.current_state != "PREPARED" or genesis.pilot_ready:
            raise JournalError("disk genesis did not evaluate to PREPARED")
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        first = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if (
            first.current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT"
            or first.resolution_count != 1
            or first.transition_count != 1
            or not first.action_ready
            or first.pilot_ready
        ):
            raise JournalError("typed S17-EXT-001 did not survive disk/hash admission")
        if first.action_context is None:
            raise JournalError("positive action context is absent")
        plan = load_json(builder.root / ACTION_PLAN_PATH)
        substitutions = {
            "{PINNED_KNOWN_HOSTS_PATH}": first.action_context["known_hosts_path"],
            "{TRANSPORT_IDENTITY_LOCATOR}": first.action_context[
                "transport_identity_locator"
            ],
            "{SSH_TARGET}": first.action_context["ssh_target"],
        }
        expected_argv = []
        for token in plan["transport"]["fixed_ssh_argv_template"]:
            rendered = token
            for placeholder, value in substitutions.items():
                rendered = rendered.replace(placeholder, value)
            expected_argv.append(rendered)
        if list(production_executor._ssh_argv(first.action_context)) != expected_argv:
            raise JournalError("production executor argv differs from fixed action plan")
        for observation_id in FIXED_PREFLIGHT_OBSERVATION_IDS:
            program = render_observation_program(
                observation_id, first.action_context["collector_context"]
            )
            if not program or b"shell=True" in program or b"/usr/bin/touch" in program:
                raise JournalError("fixed collector rendered forbidden program bytes")
            compile(program, f"<{observation_id}>", "exec")
        for reference in builder.latest_document["resolution_records"]:
            path = builder.root / reference["path"]
            if sha256_file(path) != reference["sha256"] or not load_json(path):
                raise JournalError("semantic resolution fixture did not reload from disk")
        for reference in builder.latest_document["transition_records"]:
            path = builder.root / reference["path"]
            if sha256_file(path) != reference["sha256"] or not load_json(path):
                raise JournalError("semantic transition fixture did not reload from disk")

    with tempfile.TemporaryDirectory(prefix="stage17-mechanics-positive-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        builder.add_resolution("S17-EXT-002")
        builder.add_resolution("S17-EXT-003")
        builder.add_transition()
        for input_id in ("S17-EXT-004", "S17-EXT-005", "S17-EXT-006"):
            builder.add_resolution(input_id)
        builder.add_transition()
        for input_id in (
            "S17-EXT-007",
            "S17-EXT-008",
            "S17-EXT-009",
            "S17-EXT-010",
        ):
            builder.add_resolution(input_id)
        state, resolution_count, transition_count = builder.validate_mechanics()
        if (
            state != "READY_FOR_STAGE17_PHASE_AUTHORIZATION"
            or resolution_count != 10
            or transition_count != 3
        ):
            raise JournalError("state-machine-only persisted fixture did not replay")
        for kind in ("resolution_records", "transition_records"):
            for reference in builder.latest_document[kind]:
                path = builder.root / reference["path"]
                if sha256_file(path) != reference["sha256"] or not load_json(path):
                    raise JournalError("mechanical fixture did not reload from disk")
        return 1, 1, resolution_count, transition_count


def runtime_positive_tests() -> int:
    positive_count = 0
    with tempfile.TemporaryDirectory(prefix="stage17-runtime-positive-ssh-g-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        result = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if not result.action_ready or result.action_context is None:
            raise JournalError("ssh-G positive fixture is not action-ready")
        argv = list(production_executor._ssh_argv(result.action_context))
        argv[argv.index("-T")] = "-G"
        argv.pop()
        completed = subprocess.run(
            argv,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=production_executor.FIXED_LOCAL_ENVIRONMENT,
        )
        if completed.returncode != 0:
            raise JournalError(
                f"local ssh -G failed: {completed.stderr.decode(errors='replace')}"
            )
        effective: dict[str, list[str]] = {}
        for line in completed.stdout.decode("utf-8").splitlines():
            key, separator, value = line.partition(" ")
            if separator:
                effective.setdefault(key, []).append(value)
        if effective.get("userknownhostsfile") != [
            result.action_context["known_hosts_path"]
        ] or effective.get("identityfile") != [
            result.action_context["transport_identity_locator"]
        ]:
            raise JournalError("ssh -G changed an admitted OpenSSH option path")
        positive_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-runtime-positive-success-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        calls: list[float] = []

        def successful_transport(_argv, _stdin, timeout_seconds, _output_limit):
            calls.append(timeout_seconds)
            return production_executor.TransportResult(0, b"synthetic stdout\n", b"")

        with mock.patch.object(
            production_executor, "_transport_once", side_effect=successful_transport
        ), mock.patch.object(production_executor, "_actual_utc_now", return_value=utc(22)):
            production_executor.execute_once(
                repository_root=builder.root,
                latest_journal=builder.latest_path.relative_to(builder.root),
                journal_directory=builder.root / "config/stage17/journal",
            )
        if len(calls) != 6 or any(not 0 < value <= 30 for value in calls):
            raise JournalError("successful fixed action did not execute six bounded calls")
        evidence_root = builder.external_root / "evidence-root"
        attempt = load_json(evidence_root / "stage17-read-only-preflight-attempt-v2.json")
        completion = load_json(
            evidence_root / "stage17-read-only-preflight-completion-v1.json"
        )
        validate_schema(
            attempt, builder.root / ATTEMPT_SCHEMA_PATH, "positive durable attempt"
        )
        validate_schema(
            completion,
            builder.root / COMPLETION_SCHEMA_PATH,
            "positive durable completion",
        )
        if completion["completed_observation_ids"] != list(
            FIXED_PREFLIGHT_OBSERVATION_IDS
        ) or (evidence_root / "stage17-read-only-preflight-failure-v2.json").exists():
            raise JournalError("successful fixed action has incomplete or failure evidence")
        for ordinal, observation_id in enumerate(FIXED_PREFLIGHT_OBSERVATION_IDS, start=1):
            receipt_path = evidence_root / f"s17-ro-{ordinal:03d}.receipt-v1.json"
            receipt = load_json(receipt_path)
            validate_schema(
                receipt, builder.root / RECEIPT_SCHEMA_PATH, "positive observation receipt"
            )
            if receipt["observation_id"] != observation_id:
                raise JournalError("positive receipt observation order drifted")
        positive_count += 1
    return positive_count


def negative_tests() -> int:
    negative_count = 0

    def run(label: str, scenario, *, mechanics: bool = False) -> None:
        nonlocal negative_count
        with tempfile.TemporaryDirectory(prefix=f"stage17-negative-{label}-") as temporary:
            builder = SyntheticBuilder(pathlib.Path(temporary))
            scenario(builder)
            expect_failure(
                label,
                builder.validate_mechanics if mechanics else builder.validate,
            )
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-concurrent-attempt-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        first_transport_started = threading.Event()
        release_transport = threading.Event()
        call_threads: list[int] = []
        call_lock = threading.Lock()
        outcomes: list[str] = []

        def concurrent_transport(*_args, **_kwargs):
            with call_lock:
                call_threads.append(threading.get_ident())
                first = len(call_threads) == 1
            if first:
                first_transport_started.set()
                if not release_transport.wait(timeout=5):
                    raise JournalError("concurrent test transport release timed out")
            return production_executor.TransportResult(0, b"ok", b"")

        def concurrent_action() -> None:
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except production_executor.ActionExecutionError:
                outcomes.append("REJECTED")
            else:
                outcomes.append("COMPLETED")

        with mock.patch.object(
            production_executor, "_transport_once", side_effect=concurrent_transport
        ), mock.patch.object(production_executor, "_actual_utc_now", return_value=utc(22)):
            winner = threading.Thread(target=concurrent_action)
            loser = threading.Thread(target=concurrent_action)
            winner.start()
            if not first_transport_started.wait(timeout=5):
                raise JournalError("first concurrent action did not reach transport")
            loser.start()
            loser.join(timeout=5)
            release_transport.set()
            winner.join(timeout=5)
        if winner.is_alive() or loser.is_alive():
            raise JournalError("concurrent one-shot test did not terminate")
        if sorted(outcomes) != ["COMPLETED", "REJECTED"]:
            raise JournalError("concurrent one-shot did not have exactly one winner")
        if len(call_threads) != 6 or len(set(call_threads)) != 1:
            raise JournalError("losing concurrent attempt opened a transport")
        evidence_root = builder.external_root / "evidence-root"
        if not (
            evidence_root / "stage17-read-only-preflight-attempt-v2.json"
        ).is_file() or not (
            evidence_root / "stage17-read-only-preflight-completion-v1.json"
        ).is_file():
            raise JournalError("concurrent winner did not retain marker/completion")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-marker-durability-order-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        events: list[str] = []
        original_fsync = production_executor.os.fsync
        durable_before_transport = False

        def recording_fsync(descriptor: int) -> None:
            metadata = os.fstat(descriptor)
            events.append("directory" if stat.S_ISDIR(metadata.st_mode) else "file")
            original_fsync(descriptor)

        def durability_transport(*_args, **_kwargs):
            nonlocal durable_before_transport
            durable_before_transport = events[:2] == ["file", "directory"]
            return production_executor.TransportResult(1, b"", b"stop")

        with mock.patch.object(
            production_executor.os, "fsync", side_effect=recording_fsync
        ), mock.patch.object(
            production_executor, "_transport_once", side_effect=durability_transport
        ), mock.patch.object(production_executor, "_actual_utc_now", return_value=utc(22)):
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except production_executor.ActionExecutionError:
                pass
            else:
                raise JournalError("durability-order fixture did not stop")
        if not durable_before_transport:
            raise JournalError("marker file and directory were not fsynced before transport")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-global-wall-deadline-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        now_ns = [0]
        observed_timeouts: list[float] = []

        def monotonic_ns() -> int:
            return now_ns[0]

        def deadline_transport(_argv, _stdin, timeout_seconds, _output_limit):
            observed_timeouts.append(timeout_seconds)
            now_ns[0] += 40_000_000_000
            return production_executor.TransportResult(0, b"ok", b"")

        with mock.patch.object(
            production_executor.time, "monotonic_ns", side_effect=monotonic_ns
        ), mock.patch.object(
            production_executor, "_transport_once", side_effect=deadline_transport
        ), mock.patch.object(production_executor, "_actual_utc_now", return_value=utc(22)):
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except production_executor.ActionExecutionError:
                pass
            else:
                raise JournalError("global deadline did not stop the action")
        failure = load_json(
            builder.external_root
            / "evidence-root/stage17-read-only-preflight-failure-v2.json"
        )
        if (
            failure["reason_category"] != "GLOBAL_WALL_TIMEOUT"
            or len(observed_timeouts) != 5
            or observed_timeouts[-1] != 20.0
            or any(value > 30.0 for value in observed_timeouts)
        ):
            raise JournalError("global deadline was treated as per-command timeout")
        negative_count += 1

    run(
        "nonexistent-evidence",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            evidence_override=[
                {
                    "kind": "REPOSITORY_FILE",
                    "path": "DOES-NOT-EXIST",
                    "size_bytes": 1,
                    "sha256": "a" * 64,
                }
            ],
        ),
    )
    run(
        "legacy-artifact-id-only",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            extra_fields={"artifact_id": "DOES-NOT-EXIST", "sha256": "a" * 64},
        ),
    )

    run(
        "one-arbitrary-observation-id",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            authorization_mutator=lambda document: document.update(
                {"frozen_observation_ids": ["ARBITRARY-OBSERVATION"]}
            ),
        ),
    )

    def missing_supporting_contract(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        (builder.root / "evidence/s17-ext-001-supporting-contract-v4.json").unlink()

    run("missing-supporting-contract", missing_supporting_contract)

    def changed_supporting_contract(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        contract_path = builder.root / "evidence/s17-ext-001-supporting-contract-v4.json"
        contract = load_json(contract_path)
        contract["target"]["stand_id"] = "CHANGED-AFTER-BINDING"
        contract_path.write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    run("changed-supporting-contract", changed_supporting_contract)

    run(
        "unbound-supporting-contract",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            authorization_mutator=lambda document: document[
                "supporting_observation_contract"
            ].update({"sha256": "a" * 64}),
        ),
    )
    run(
        "target-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            authorization_mutator=lambda document: document["target"].update(
                {"stand_id": "MISMATCHED-STAND"}
            ),
        ),
    )
    run(
        "pilot-contract-sha-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document["pilot_candidate"][
                "contract"
            ].update({"sha256": "a" * 64}),
        ),
    )
    run(
        "limits-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            authorization_mutator=lambda document: document["limits"].update(
                {"max_wall_seconds": 601}
            ),
        ),
    )
    run(
        "mutating-remote-command",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document.update(
                {
                    "remote_command_bytes_base64": b64(
                        "/usr/bin/touch /tmp/STAGE17-MUTATION"
                    )
                }
            ),
        ),
    )
    for label, command in (
        ("sudo-command", "sudo /usr/bin/id"),
        ("shell-command", "/bin/sh -c /usr/bin/id"),
        ("redirect-command", "/usr/bin/id > /tmp/output"),
        ("pipe-command", "/usr/bin/id | /usr/bin/cat"),
        ("command-substitution", "/usr/bin/id $(/usr/bin/hostname)"),
    ):
        run(
            label,
            lambda builder, value=command: builder.add_resolution(
                "S17-EXT-001",
                contract_mutator=lambda document: document.update(
                    {"owner_remote_command": value}
                ),
            ),
        )
    run(
        "arbitrary-argv",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document.update(
                {"argv_bytes_base64": [b64("/usr/bin/touch")]}
            ),
        ),
    )
    run(
        "arbitrary-stdin",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document.update(
                {"stdin_bytes_base64": b64("mutating input")}
            ),
        ),
    )
    run(
        "prospective-local-executable-sha-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document[
                "prospective_local_action_identities"
            ][0]["source_binding"].update({"sha256": "a" * 64}),
        ),
    )

    def arbitrary_launcher_bytes(builder: SyntheticBuilder) -> None:
        arbitrary = builder.root / "synthetic/arbitrary-launcher.py"
        arbitrary.parent.mkdir(parents=True, exist_ok=True)
        arbitrary.write_bytes(b"#!/usr/bin/python3\nprint('arbitrary')\n")
        arbitrary.chmod(0o755)
        binding = {
            "path": arbitrary.relative_to(builder.root).as_posix(),
            "size_bytes": arbitrary.stat().st_size,
            "sha256": sha256_file(arbitrary),
        }
        builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document[
                "prospective_local_action_identities"
            ][0].update({"execution_path": str(arbitrary), "source_binding": binding}),
        )

    run("arbitrary-launcher-bytes", arbitrary_launcher_bytes)
    run(
        "prospective-collector-source-sha-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document[
                "prospective_local_action_identities"
            ][1]["source_binding"].update({"sha256": "b" * 64}),
        ),
    )

    def non_executable_launcher(builder: SyntheticBuilder) -> None:
        def mutate(document: dict[str, Any]) -> None:
            path = builder.external_root / "non-executable-launcher"
            shutil.copyfile(pathlib.Path(production_executor.__file__), path)
            path.chmod(0o644)
            document["prospective_local_action_identities"][0]["execution_path"] = str(path)

        builder.add_resolution("S17-EXT-001", contract_mutator=mutate)

    run("non-executable-launcher", non_executable_launcher)

    def hash_mismatched_execution_file(builder: SyntheticBuilder) -> None:
        def mutate(document: dict[str, Any]) -> None:
            path = builder.external_root / "hash-mismatched-launcher"
            shutil.copyfile(pathlib.Path(production_executor.__file__), path)
            path.write_bytes(path.read_bytes() + b"# drift\n")
            path.chmod(0o755)
            document["prospective_local_action_identities"][0]["execution_path"] = str(path)

        builder.add_resolution("S17-EXT-001", contract_mutator=mutate)

    run("hash-mismatched-local-action", hash_mismatched_execution_file)
    run(
        "raw-observation-contract-forbidden",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document.update(
                {"observations": [{"argv": ["/wrong/executable"]}]}
            ),
        ),
    )

    def unsafe_output_root(builder: SyntheticBuilder) -> None:
        builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document.update(
                {"evidence_root": "/etc/stage17-new-output"}
            ),
            authorization_mutator=lambda document: document.update(
                {"evidence_root": "/etc/stage17-new-output"}
            ),
        )

    run("output-outside-evidence-root", unsafe_output_root)

    def generic_accepted(builder: SyntheticBuilder) -> None:
        evidence = builder.repository_evidence(
            "S17-EXT-001-GENERIC", {"accepted": True}
        )
        builder.add_resolution("S17-EXT-001", evidence_override=[evidence])

    run("generic-accepted-json", generic_accepted)
    run(
        "arbitrary-external-receipt",
        lambda builder: builder.add_resolution("S17-EXT-002"),
    )

    def unknown_semantic_verifier(builder: SyntheticBuilder) -> None:
        policy_path = builder.root / SEMANTIC_POLICY_PATH
        policy = load_json(policy_path)
        policy["entries"][0]["verifier_id"] = "UNKNOWN-SEMANTIC-VERIFIER"
        policy_path.write_text(
            json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        builder.add_resolution("S17-EXT-001")

    run("unknown-semantic-verifier", unknown_semantic_verifier)

    def malformed_ed25519_blob(builder: SyntheticBuilder) -> None:
        def mutate(document: dict[str, Any]) -> None:
            binding = document["target"]["pinned_host_key_evidence"]
            path = builder.root / binding["path"]
            pinned = load_json(path)
            malformed = b"x" * 32
            pinned["public_key_base64"] = base64.b64encode(malformed).decode("ascii")
            pinned["fingerprint_sha256"] = "SHA256:" + base64.b64encode(
                hashlib.sha256(malformed).digest()
            ).decode("ascii").rstrip("=")
            path.write_text(
                json.dumps(pinned, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            binding["size_bytes"] = path.stat().st_size
            binding["sha256"] = sha256_file(path)

        builder.add_resolution("S17-EXT-001", contract_mutator=mutate)

    run("malformed-ed25519-wire-blob", malformed_ed25519_blob)

    def drift_file(builder: SyntheticBuilder, relative: str) -> None:
        path = builder.root / relative
        path.write_bytes(path.read_bytes() + b"\n")
        builder.add_resolution("S17-EXT-001")

    run(
        "fixed-action-plan-drift",
        lambda builder: drift_file(builder, ACTION_PLAN_PATH),
    )
    run(
        "v4-schema-drift",
        lambda builder: drift_file(builder, V4_SCHEMA_PATHS[1]),
    )
    run(
        "production-verifier-drift",
        lambda builder: drift_file(builder, "tools/stage17_semantic_verifier_v4.py"),
    )
    run(
        "s17-ext-010-without-predecessor-bindings",
        lambda builder: builder.add_resolution("S17-EXT-010"),
    )
    run(
        "expanded-permission-matrix",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            authorization_mutator=lambda document: document["permissions"].update(
                {"measurement": True}
            ),
        ),
    )

    for label, value in (
        ("fractional-capture-time", "2030-01-01T00:21:00.500Z"),
        ("malformed-capture-time", "2030-01-01 00:21:00Z"),
        ("impossible-capture-date", "2030-02-31T00:21:00Z"),
    ):
        run(
            label,
            lambda builder, capture=value: builder.add_resolution(
                "S17-EXT-001",
                contract_mutator=lambda document: document["capture"].update(
                    {"captured_at_utc": capture}
                ),
            ),
        )

    def openssh_known_hosts_token(builder: SyntheticBuilder, token: str) -> None:
        def mutate(document: dict[str, Any]) -> None:
            binding = document["target"]["pinned_known_hosts"]
            source = builder.root / binding["path"]
            destination = source.parent / f"pinned-{token}.known_hosts"
            destination.write_bytes(source.read_bytes())
            binding.update(
                {
                    "path": destination.relative_to(builder.root).as_posix(),
                    "size_bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                }
            )

        builder.add_resolution("S17-EXT-001", contract_mutator=mutate)

    def openssh_identity_token(builder: SyntheticBuilder, token: str) -> None:
        def mutate(document: dict[str, Any]) -> None:
            source = pathlib.Path(document["target"]["transport_identity_locator"])
            destination = builder.external_root / f"identity-{token}"
            destination.write_bytes(source.read_bytes())
            destination.chmod(0o600)
            document["target"]["transport_identity_locator"] = str(destination)

        builder.add_resolution("S17-EXT-001", contract_mutator=mutate)

    for token in ("%h", "%n", "%r", "%C"):
        run(
            f"openssh-known-hosts-{token[1:]}",
            lambda builder, item=token: openssh_known_hosts_token(builder, item),
        )
    for label, token in (
        ("home-expansion", "${HOME}"),
        ("whitespace", "space name"),
        ("control", "line\nfeed"),
        ("backslash", "back\\slash"),
        ("quote", "quoted'name"),
    ):
        run(
            f"openssh-identity-{label}",
            lambda builder, item=token: openssh_identity_token(builder, item),
        )

    for role_index, label, source in (
        (0, "approved-actual-executor-mismatch", pathlib.Path(production_executor.__file__)),
        (1, "approved-actual-collector-mismatch", pathlib.Path(production_collector.__file__)),
    ):
        with tempfile.TemporaryDirectory(prefix=f"stage17-negative-{label}-") as temporary:
            builder = SyntheticBuilder(pathlib.Path(temporary))

            def use_dead_copy(document: dict[str, Any], *, index=role_index, source_path=source) -> None:
                dead = builder.external_root / f"dead-runtime-{index}"
                shutil.copyfile(source_path, dead)
                dead.chmod(0o755)
                document["prospective_local_action_identities"][index]["execution_path"] = str(dead)

            builder.add_resolution("S17-EXT-001", contract_mutator=use_dead_copy)
            builder.add_transition()
            result = builder.validate(
                as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
            )
            if result.action_ready:
                raise JournalError(f"{label} remained action-ready")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-missing-runtime-context-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        result = validate_journal(
            repository_root=builder.root,
            latest_journal=builder.latest_path.relative_to(builder.root),
            journal_directory=builder.root / "config/stage17/journal",
            as_of_utc=utc(22),
            requested_action_input_id="S17-EXT-001",
        )
        if result.action_ready:
            raise JournalError("action readiness did not require actual runtime identity")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-no-transition-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        result = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if (
            result.current_state != "PREPARED"
            or result.transition_count != 0
            or result.action_ready
        ):
            raise JournalError("S17-EXT-001 became action-ready without transition 1")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-expired-action-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        expired = builder.validate(
            as_of_utc="2030-01-02T00:00:00Z",
            requested_action_input_id="S17-EXT-001",
        )
        if expired.action_ready:
            raise JournalError("expired S17-EXT-001 remained action-ready")
        negative_count += 1

    for label, actual_time in (
        ("future-authorization-actual-clock", "2029-12-31T23:59:59Z"),
        ("expired-authorization-actual-clock", "2030-01-02T00:00:00Z"),
    ):
        with tempfile.TemporaryDirectory(prefix=f"stage17-negative-{label}-") as temporary:
            builder = SyntheticBuilder(pathlib.Path(temporary))
            builder.add_resolution("S17-EXT-001")
            builder.add_transition()
            calls = 0

            def forbidden_transport(*_args, **_kwargs):
                nonlocal calls
                calls += 1
                raise JournalError("transport must not open outside actual authority time")

            with mock.patch.object(
                production_executor, "_actual_utc_now", return_value=actual_time
            ), mock.patch.object(
                production_executor, "_transport_once", side_effect=forbidden_transport
            ):
                try:
                    production_executor.execute_once(
                        repository_root=builder.root,
                        latest_journal=builder.latest_path.relative_to(builder.root),
                        journal_directory=builder.root / "config/stage17/journal",
                    )
                except production_executor.ActionExecutionError:
                    pass
                else:
                    raise JournalError(f"{label} reached production execution")
            evidence_root = builder.external_root / "evidence-root"
            if calls or (evidence_root / "stage17-read-only-preflight-attempt-v2.json").exists():
                raise JournalError(f"{label} created marker or transport")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-caller-time-bypass-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        prospective = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if not prospective.action_ready:
            raise JournalError("prospective time fixture was not ready")
        with mock.patch.object(
            production_executor, "_actual_utc_now", return_value="2029-12-31T23:59:59Z"
        ), mock.patch.object(sys, "argv", [
            "stage17_read_only_preflight_executor_v2.py",
            "--execute",
            "--repository-root", str(builder.root),
            "--journal", str(builder.latest_path.relative_to(builder.root)),
            "--journal-directory", str(builder.root / "config/stage17/journal"),
            "--as-of-utc", utc(22),
        ]), contextlib.redirect_stderr(io.StringIO()):
            try:
                production_executor.main()
            except SystemExit as exception:
                if exception.code != 2:
                    raise
            else:
                raise JournalError("production CLI accepted caller-controlled time")
        if (builder.external_root / "evidence-root/stage17-read-only-preflight-attempt-v2.json").exists():
            raise JournalError("caller-controlled time bypass created marker")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-render-before-marker-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        calls = 0

        def forbidden_transport(*_args, **_kwargs):
            nonlocal calls
            calls += 1
            return production_executor.TransportResult(0, b"", b"")

        with mock.patch.object(
            production_executor.stage17_read_only_preflight_collector_v2,
            "render_observation_program",
            side_effect=ValueError("synthetic render error"),
        ), mock.patch.object(
            production_executor, "_actual_utc_now", return_value=utc(22)
        ), mock.patch.object(
            production_executor, "_transport_once", side_effect=forbidden_transport
        ):
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except ValueError:
                pass
            else:
                raise JournalError("render error did not stop before marker")
        evidence_root = builder.external_root / "evidence-root"
        if calls or (evidence_root / "stage17-read-only-preflight-attempt-v2.json").exists():
            raise JournalError("render error created marker or transport")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-attempt-marker-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        ready = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if not ready.action_ready or ready.action_context is None:
            raise JournalError("one-shot marker fixture was not initially ready")
        marker = pathlib.Path(ready.action_context["evidence_root"]) / ready.action_context[
            "attempt_marker_name"
        ]
        write_json(marker, {"synthetic_attempt_started": True})
        repeated = builder.validate(
            as_of_utc=utc(22), requested_action_input_id="S17-EXT-001"
        )
        if repeated.action_ready:
            raise JournalError("existing create-exclusive marker allowed repeat")
        negative_count += 1

    with tempfile.TemporaryDirectory(prefix="stage17-negative-partial-failure-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        calls = 0

        def fail_first_transport(*_args, **_kwargs):
            nonlocal calls
            marker = (
                builder.external_root / "evidence-root"
                / "stage17-read-only-preflight-attempt-v2.json"
            )
            if not marker.is_file():
                raise JournalError("transport opened before create-exclusive marker")
            calls += 1
            return production_executor.TransportResult(
                returncode=1,
                stdout=b"synthetic partial stdout",
                stderr=b"synthetic failure",
            )

        with mock.patch.object(
            production_executor, "_transport_once", side_effect=fail_first_transport
        ), mock.patch.object(production_executor, "_actual_utc_now", return_value=utc(22)):
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except production_executor.ActionExecutionError:
                pass
            else:
                raise JournalError("partial transport failure did not stop execution")
            try:
                production_executor.execute_once(
                    repository_root=builder.root,
                    latest_journal=builder.latest_path.relative_to(builder.root),
                    journal_directory=builder.root / "config/stage17/journal",
                )
            except production_executor.ActionExecutionError:
                pass
            else:
                raise JournalError("second executor invocation was not blocked")
        if calls != 1:
            raise JournalError("partial failure opened transport more than once")
        marker_path = (
            builder.external_root / "evidence-root"
            / "stage17-read-only-preflight-attempt-v2.json"
        )
        validate_schema(
            load_json(marker_path),
            builder.root / ATTEMPT_SCHEMA_PATH,
            "synthetic one-shot attempt marker",
        )
        failure_path = (
            builder.external_root / "evidence-root"
            / "stage17-read-only-preflight-failure-v2.json"
        )
        if not failure_path.is_file():
            raise JournalError("partial failure evidence was not retained")
        negative_count += 1

    for failure_kind in (
        "popen-exception",
        "pipe-exception",
        "output-write-exception",
        "receipt-write-exception",
        "transport-timeout",
    ):
        with tempfile.TemporaryDirectory(
            prefix=f"stage17-negative-{failure_kind}-"
        ) as temporary:
            builder = SyntheticBuilder(pathlib.Path(temporary))
            builder.add_resolution("S17-EXT-001")
            builder.add_transition()
            transport_calls = 0
            original_write = production_executor._write_exclusive_at

            def failure_transport(*_args, **_kwargs):
                nonlocal transport_calls
                transport_calls += 1
                if failure_kind == "popen-exception":
                    raise OSError("synthetic Popen error")
                if failure_kind == "pipe-exception":
                    raise BrokenPipeError("synthetic pipe error")
                if failure_kind == "transport-timeout":
                    return production_executor.TransportResult(
                        -9, b"partial stdout", b"timeout", "TIMEOUT"
                    )
                return production_executor.TransportResult(0, b"stdout", b"")

            def failure_write(directory_fd, name, payload, **kwargs):
                if failure_kind == "output-write-exception" and name.endswith(
                    ".stdout.bin"
                ):
                    raise OSError("synthetic output write error")
                if failure_kind == "receipt-write-exception" and name.endswith(
                    ".receipt-v1.json"
                ):
                    raise OSError("synthetic receipt write error")
                return original_write(directory_fd, name, payload, **kwargs)

            with mock.patch.object(
                production_executor, "_transport_once", side_effect=failure_transport
            ), mock.patch.object(
                production_executor, "_write_exclusive_at", side_effect=failure_write
            ), mock.patch.object(
                production_executor, "_actual_utc_now", return_value=utc(22)
            ):
                try:
                    production_executor.execute_once(
                        repository_root=builder.root,
                        latest_journal=builder.latest_path.relative_to(builder.root),
                        journal_directory=builder.root / "config/stage17/journal",
                    )
                except production_executor.ActionExecutionError:
                    pass
                else:
                    raise JournalError(f"{failure_kind} did not fail")
                first_calls = transport_calls
                try:
                    production_executor.execute_once(
                        repository_root=builder.root,
                        latest_journal=builder.latest_path.relative_to(builder.root),
                        journal_directory=builder.root / "config/stage17/journal",
                    )
                except production_executor.ActionExecutionError:
                    pass
                else:
                    raise JournalError(f"{failure_kind} allowed a retry")
            evidence_root = builder.external_root / "evidence-root"
            marker_path = evidence_root / "stage17-read-only-preflight-attempt-v2.json"
            failure_path = evidence_root / "stage17-read-only-preflight-failure-v2.json"
            if (
                first_calls != 1
                or transport_calls != first_calls
                or not marker_path.is_file()
                or not failure_path.is_file()
            ):
                raise JournalError(f"{failure_kind} lost marker/failure or retried")
            validate_schema(
                load_json(failure_path),
                builder.root / FAILURE_SCHEMA_PATH,
                f"{failure_kind} typed failure",
            )
        negative_count += 1

    def synthetic_pilot_placeholders(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        for input_id in ("S17-EXT-002", "S17-EXT-003"):
            builder.add_resolution(input_id)
        builder.add_transition()
        for input_id in ("S17-EXT-004", "S17-EXT-005", "S17-EXT-006"):
            builder.add_resolution(input_id)
        builder.add_transition()
        for input_id in (
            "S17-EXT-007",
            "S17-EXT-008",
            "S17-EXT-009",
            "S17-EXT-010",
        ):
            builder.add_resolution(input_id)

    run("synthetic-placeholders-cannot-be-pilot-ready", synthetic_pilot_placeholders)
    run(
        "arbitrary-pilot-candidate-bytes",
        lambda builder: builder.add_resolution("S17-EXT-006"),
    )

    def missing_external_bytes(builder: SyntheticBuilder) -> None:
        evidence = builder.external_receipt("S17-EXT-002", 1)
        receipt_path = builder.root / evidence["receipt_path"]
        receipt = load_json(receipt_path)
        receipt["artifact_locator"] = "/DOES-NOT-EXIST"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        evidence["receipt_size_bytes"] = receipt_path.stat().st_size
        evidence["receipt_sha256"] = sha256_file(receipt_path)
        builder.add_resolution("S17-EXT-002", evidence_override=[evidence])

    run("missing-external-bytes", missing_external_bytes)

    def skip(builder: SyntheticBuilder) -> None:
        for input_id in ("S17-EXT-001", "S17-EXT-002", "S17-EXT-003"):
            builder.add_resolution(input_id)
        builder.add_transition(
            overrides={
                "to_state": "PREFLIGHT_ACCEPTED",
                "evidence_resolutions": [
                    {
                        "input_id": input_id,
                        "resolution_id": builder.resolutions[input_id][1]["resolution_id"],
                        "sha256": builder.resolutions[input_id][2],
                    }
                    for input_id in ("S17-EXT-001", "S17-EXT-002", "S17-EXT-003")
                ],
            }
        )

    run("skip", skip, mechanics=True)

    def incomplete(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(overrides={"evidence_resolutions": []})

    run("incomplete", incomplete, mechanics=True)

    def duplicate_transition_input(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        resolution = builder.resolutions["S17-EXT-001"]
        builder.add_transition(
            overrides={
                "evidence_resolutions": [
                    {
                        "input_id": "S17-EXT-001",
                        "resolution_id": resolution[1]["resolution_id"],
                        "sha256": resolution[2],
                    },
                    {
                        "input_id": "S17-EXT-001",
                        "resolution_id": "DUPLICATE-S17-EXT-001",
                        "sha256": "c" * 64,
                    },
                ]
            }
        )

    run("duplicate-transition-input", duplicate_transition_input, mechanics=True)

    def replaced_predecessor(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(overrides={"previous_transition_sha256": "b" * 64})

    run("replaced-predecessor", replaced_predecessor, mechanics=True)

    def unknown_authorization(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(
            overrides={
                "authorizations": [
                    {
                        "input_id": "S17-EXT-001",
                        "resolution_id": "DOES-NOT-EXIST",
                        "authorization_id": "DOES-NOT-EXIST",
                        "authority_scope": "READ_ONLY_PREFLIGHT",
                    }
                ]
            }
        )

    run("unknown-authorization", unknown_authorization, mechanics=True)

    def expired_authorization(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(overrides={"timestamp_utc": "2030-01-02T00:00:00Z"})

    run("expired-authorization", expired_authorization)

    def replay(builder: SyntheticBuilder) -> None:
        first = builder.add_resolution("S17-EXT-001")
        builder.add_resolution(
            "S17-EXT-002", resolution_id=str(first["resolution_id"])
        )

    run("replay", replay)

    def backward(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        builder.add_resolution("S17-EXT-002")
        builder.add_resolution("S17-EXT-003")
        builder.add_transition(
            overrides={
                "to_state": "PREPARED",
                "authority_scope": "PREFLIGHT_ACCEPTANCE_STATE_ADVANCE_ONLY",
            }
        )

    run("backward", backward, mechanics=True)

    def duplicate_sequence(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        builder.add_resolution("S17-EXT-002")
        builder.add_resolution("S17-EXT-003")
        builder.add_transition(overrides={"sequence_number": 1})

    run("duplicate-sequence", duplicate_sequence, mechanics=True)

    def graph_change(builder: SyntheticBuilder) -> None:
        graph_path = builder.root / GRAPH_PATH
        graph = load_json(graph_path)
        graph["transitions"][0]["authority_scope"] = (
            "STAGE17_PHASE_AUTHORIZATION_PREPARATION_ONLY"
        )
        graph_path.write_text(
            json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    run("graph-change", graph_change)

    def stage18_change(builder: SyntheticBuilder) -> None:
        graph_path = builder.root / GRAPH_PATH
        graph = load_json(graph_path)
        graph["confirmatory_governance"]["access_state_order"].remove(
            "SELECTION_FROZEN"
        )
        graph_path.write_text(
            json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    run("stage18-chronology", stage18_change)

    with tempfile.TemporaryDirectory(prefix="stage17-negative-fork-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        first_path = builder.root / "records/fork-a.json"
        second_path = builder.root / "records/fork-b.json"
        write_json(first_path, {"fork": "a"})
        write_json(second_path, {"fork": "b"})
        genesis_path = builder.latest_path
        builder.append_snapshot(
            "resolution_records",
            {"path": first_path.relative_to(builder.root).as_posix(), "sha256": sha256_file(first_path)},
            previous=genesis_path,
        )
        alternate = copy.deepcopy(load_json(genesis_path))
        alternate["journal_sequence_number"] = 1
        alternate["previous_journal"] = {
            "path": genesis_path.relative_to(builder.root).as_posix(),
            "sha256": sha256_file(genesis_path),
        }
        alternate["resolution_records"].append(
            {"path": second_path.relative_to(builder.root).as_posix(), "sha256": sha256_file(second_path)}
        )
        alternate_path = builder.root / "config/stage17/journal/stage17-state-journal-fork.json"
        write_json(alternate_path, alternate)
        expect_failure("fork", builder.validate)
        negative_count += 1
    return negative_count


def self_test() -> tuple[int, int, int, int, int, int]:
    semantic_resolutions, semantic_transitions, mechanics_resolutions, mechanics_transitions = (
        positive_disk_test()
    )
    runtime_positives = runtime_positive_tests()
    negatives = negative_tests()
    return (
        semantic_resolutions,
        semantic_transitions,
        mechanics_resolutions,
        mechanics_transitions,
        runtime_positives,
        negatives,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--journal", type=pathlib.Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--journal-directory", type=pathlib.Path)
    parser.add_argument("--pilot-candidate-archive", type=pathlib.Path)
    parser.add_argument("--pilot-candidate-sidecar", type=pathlib.Path)
    parser.add_argument("--as-of-utc")
    parser.add_argument("--requested-action-input-id")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--print-status", action="store_true")
    arguments = parser.parse_args()
    root = arguments.repository_root.resolve()
    journal_directory = arguments.journal_directory
    if journal_directory is None:
        journal_directory = root / arguments.journal.parent
    try:
        result = validate_journal(
            repository_root=root,
            latest_journal=arguments.journal,
            journal_directory=journal_directory,
            pilot_archive=arguments.pilot_candidate_archive,
            pilot_sidecar=arguments.pilot_candidate_sidecar,
            as_of_utc=arguments.as_of_utc,
            requested_action_input_id=arguments.requested_action_input_id,
        )
        validate_s17_ext_001_draft(root, arguments.journal)
        semantic_resolutions = semantic_transitions = 0
        mechanics_resolutions = mechanics_transitions = runtime_positives = negatives = 0
        if arguments.self_test:
            (
                semantic_resolutions,
                semantic_transitions,
                mechanics_resolutions,
                mechanics_transitions,
                runtime_positives,
                negatives,
            ) = self_test()
    except (JournalError, OSError, json.JSONDecodeError) as exception:
        print(f"stage17-state-journal-check: FAIL: {exception}", file=sys.stderr)
        return 1
    status = {
        "current_state": result.current_state,
        "pilot_ready": result.pilot_ready,
        "resolved_input_ids": list(result.resolved_input_ids),
        "missing_input_ids": list(result.missing_input_ids),
        "transition_count": result.transition_count,
        "requested_action_input_id": result.requested_action_input_id,
        "action_ready": result.action_ready,
        "stand": "NOT_ACCESSED",
    }
    if arguments.print_status:
        print(json.dumps(status, sort_keys=True, separators=(",", ":")))
    else:
        print(
            "stage17-state-journal-check: PASS "
            f"state={result.current_state} resolved={result.resolution_count} "
            f"missing={len(result.missing_input_ids)} pilot_ready={str(result.pilot_ready).lower()} "
            f"semantic_positive={semantic_resolutions}/{semantic_transitions} "
            f"mechanics_positive={mechanics_resolutions}/{mechanics_transitions} "
            f"runtime_positive={runtime_positives} "
            f"negative={negatives} nonexistent_evidence=REJECTED "
            "generic_evidence=REJECTED reload=PASS Stage18=false stand=NOT_ACCESSED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
