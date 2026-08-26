#!/usr/bin/env python3
"""Validate and disk-test the append-only Stage 17 state journal."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
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


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_JOURNAL = pathlib.Path(
    "config/stage17/journal/stage17-state-journal-000000.json"
)
DRAFT_PATH = pathlib.Path(
    "config/stage17/stage17-s17-ext-001-read-only-preflight-authorization-draft-v2.json"
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
            DRAFT_PATH.as_posix(),
            PILOT_CONTRACT_PATH.as_posix(),
            PILOT_CONTRACT_SCHEMA_PATH.as_posix(),
            PILOT_VERIFIER_PATH.as_posix(),
            SEMANTIC_POLICY_PATH.as_posix(),
            SEMANTIC_POLICY_SCHEMA_PATH.as_posix(),
            SEMANTIC_ENVELOPE_SCHEMA_PATH.as_posix(),
            S17_EXT_001_AUTHORIZATION_SCHEMA_PATH.as_posix(),
            S17_EXT_001_CONTRACT_SCHEMA_PATH.as_posix(),
            PINNED_HOST_KEY_SCHEMA_PATH.as_posix(),
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
        pinned_path = self.root / "synthetic/pinned-host-key.txt"
        pinned_path.parent.mkdir(parents=True, exist_ok=True)
        synthetic_host_key = b"synthetic-ed25519-host-key-bytes-not-authority"
        fingerprint = "SHA256:" + base64.b64encode(
            hashlib.sha256(synthetic_host_key).digest()
        ).decode("ascii").rstrip("=")
        write_json(
            pinned_path,
            {
                "schema_version": "cpu-prefetch-stage17-pinned-host-key-evidence/1",
                "evidence_id": "SYNTHETIC-PINNED-HOST-KEY-NO-AUTHORITY",
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "ssh_target": "synthetic.invalid",
                "algorithm": "ssh-ed25519",
                "public_key_base64": base64.b64encode(synthetic_host_key).decode("ascii"),
                "fingerprint_sha256": fingerprint,
                "source": "OWNER_PROVIDED_OUT_OF_BAND_PIN",
                "runtime_observation": False,
            },
        )
        launcher_path = self.root / "synthetic/local-launcher"
        collector_path = self.root / "synthetic/local-collector"
        launcher_path.write_bytes(b"synthetic local launcher bytes\n")
        collector_path.write_bytes(b"synthetic local collector bytes\n")
        pilot_fixed = self.catalog["fixed_evidence_contracts"][0]
        identities = [
            {
                "identity_id": "LOCAL_PREFLIGHT_LAUNCHER",
                "role": "LAUNCHER",
                "execution_path": "/synthetic/stage17/bin/launcher",
                "source_path": launcher_path.relative_to(self.root).as_posix(),
                "size_bytes": launcher_path.stat().st_size,
                "sha256": sha256_file(launcher_path),
            },
            {
                "identity_id": "LOCAL_PREFLIGHT_COLLECTOR",
                "role": "COLLECTOR",
                "execution_path": "/synthetic/stage17/bin/collector",
                "source_path": collector_path.relative_to(self.root).as_posix(),
                "size_bytes": collector_path.stat().st_size,
                "sha256": sha256_file(collector_path),
            },
        ]
        observations = []
        for index, observation_id in enumerate(FIXED_PREFLIGHT_OBSERVATION_IDS, start=1):
            local_identity_id = (
                "LOCAL_PREFLIGHT_LAUNCHER"
                if index == 1
                else "LOCAL_PREFLIGHT_COLLECTOR"
            )
            execution_path = next(
                identity["execution_path"]
                for identity in identities
                if identity["identity_id"] == local_identity_id
            )
            observations.append(
                {
                    "observation_id": observation_id,
                    "local_action_identity_id": local_identity_id,
                    "argv_bytes_base64": [
                        b64(execution_path),
                        b64(f"--observation={index}"),
                    ],
                    "stdin_bytes_base64": b64(""),
                    "remote_command_bytes_base64": b64(
                        f"synthetic-read-only-observation-{index}"
                    ),
                    "output_locator": f"/synthetic/stage17/output/observation-{index}.json",
                    "output_creation": "CREATE_EXCLUSIVE",
                    "max_output_bytes": 1024,
                }
            )
        contract: dict[str, Any] = {
            "schema_version": (
                "cpu-prefetch-stage17-read-only-preflight-supporting-contract/2"
            ),
            "contract_id": "SYNTHETIC-S17-EXT-001-SUPPORTING-CONTRACT-NO-AUTHORITY",
            "protocol_version": "2.0.0-pre.2",
            "target": {
                "stand_id": "SYNTHETIC-STAND-NOT-ACCESSED",
                "ssh_target": "synthetic.invalid",
                "pinned_host_key_evidence": {
                    "path": pinned_path.relative_to(self.root).as_posix(),
                    "size_bytes": pinned_path.stat().st_size,
                    "sha256": sha256_file(pinned_path),
                    "schema_identity": (
                        "cpu-prefetch-stage17-pinned-host-key-evidence/1"
                    ),
                },
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
            },
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
            "observations": observations,
            "limits": {
                "max_commands": 6,
                "max_wall_seconds": 600,
                "max_total_output_bytes": 8192,
                "attempts_per_observation": 1,
                "retries": 0,
            },
            "stop_policy": "STOP_ON_FIRST_MISMATCH_OR_NONZERO_EXIT",
            "retention_policy": (
                "CREATE_EXCLUSIVE_APPEND_ONLY_RETAIN_SUCCESS_AND_FAILURE_NO_DELETE"
            ),
            "authority_boundary": copy.deepcopy(READ_ONLY_PERMISSION_MATRIX),
        }
        if contract_mutator is not None:
            contract_mutator(contract)
        contract_path = self.root / "evidence/s17-ext-001-supporting-contract-v2.json"
        write_json(contract_path, contract)
        contract_binding = {
            "path": contract_path.relative_to(self.root).as_posix(),
            "size_bytes": contract_path.stat().st_size,
            "sha256": sha256_file(contract_path),
            "schema_identity": (
                "cpu-prefetch-stage17-read-only-preflight-supporting-contract/2"
            ),
        }
        authorization: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-read-only-preflight-authorization/2",
            "authorization_id": "SYNTHETIC-S17-EXT-001-AUTHORIZATION-NO-AUTHORITY",
            "input_id": "S17-EXT-001",
            "actor": actor,
            "issued_at_utc": utc(0),
            "expires_at_utc": "2030-01-02T00:00:00Z",
            "authority_scope": "READ_ONLY_PREFLIGHT",
            "target_scope": (
                "STAND_ID=SYNTHETIC-STAND-NOT-ACCESSED;"
                "SSH_TARGET=synthetic.invalid;SCOPE=READ_ONLY_PREFLIGHT"
            ),
            "target": {
                "stand_id": contract["target"]["stand_id"],
                "ssh_target": contract["target"]["ssh_target"],
                "pinned_host_key_evidence_sha256": contract["target"][
                    "pinned_host_key_evidence"
                ]["sha256"],
            },
            "frozen_observation_ids": list(FIXED_PREFLIGHT_OBSERVATION_IDS),
            "supporting_observation_contract": contract_binding,
            "limits": copy.deepcopy(contract["limits"]),
            "role_collapse_acknowledged": True,
            "independent_review_claimed": False,
            "permissions": copy.deepcopy(READ_ONLY_PERMISSION_MATRIX),
        }
        if authorization_mutator is not None:
            authorization_mutator(authorization)
        authorization_path = self.root / "evidence/s17-ext-001-authorization-v2.json"
        write_json(authorization_path, authorization)
        authorization_binding = {
            "path": authorization_path.relative_to(self.root).as_posix(),
            "size_bytes": authorization_path.stat().st_size,
            "sha256": sha256_file(authorization_path),
            "schema_identity": "cpu-prefetch-stage17-read-only-preflight-authorization/2",
        }
        policy_path = self.root / SEMANTIC_POLICY_PATH
        envelope: dict[str, Any] = {
            "schema_version": "cpu-prefetch-stage17-operational-evidence-envelope/2",
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
            },
            "semantic_policy": {
                "path": SEMANTIC_POLICY_PATH.as_posix(),
                "size_bytes": policy_path.stat().st_size,
                "sha256": sha256_file(policy_path),
            },
            "semantic_verifier": {
                "verifier_id": "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER",
                "verifier_version": "2",
            },
            "authorization": authorization_binding,
            "supporting_contract": contract_binding,
            "stage18_authority": False,
        }
        if envelope_mutator is not None:
            envelope_mutator(envelope)
        envelope_path = self.root / "evidence/s17-ext-001-semantic-envelope-v2.json"
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
                    "evidence/s17-ext-001-authorization-v2.json"
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
    relative_journal = (
        journal_path.relative_to(root) if journal_path.is_absolute() else journal_path
    )
    journal = load_json(repository_file(root, relative_journal.as_posix()))
    if (
        draft.get("schema_version")
        != "cpu-prefetch-stage17-s17-ext-001-authorization-draft/2"
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
    if (
        bindings.get("graph_sha256") != journal["graph"]["sha256"]
        or bindings.get("catalog_sha256") != journal["catalog"]["sha256"]
        or bindings.get("genesis_sha256") != journal["genesis"]["genesis_sha256"]
        or bindings.get("predecessor_draft_path") != LEGACY_DRAFT_PATH.as_posix()
        or bindings.get("predecessor_draft_sha256") != LEGACY_DRAFT_SHA256
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
    ):
        raise JournalError("S17-EXT-001 draft fixed authorization scope drifted")
    for field in (
        "authorization_id",
        "actor",
        "issued_at_utc",
        "expires_at_utc",
        "target_scope",
    ):
        if payload.get(field) is not None:
            raise JournalError(f"S17-EXT-001 draft fabricated owner field: {field}")
    if any(
        payload.get("limits", {}).get(field) is not None
        for field in ("max_wall_seconds", "max_total_output_bytes")
    ):
        raise JournalError("S17-EXT-001 draft fabricated owner limits")
    supporting = draft.get("supporting_observation_contract", {})
    observed_identifiers = tuple(
        item.get("observation_id")
        for item in supporting.get("observations", [])
    )
    if observed_identifiers != FIXED_PREFLIGHT_OBSERVATION_IDS:
        raise JournalError("S17-EXT-001 supporting observation family drifted")
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
        for field in ("stand_id", "ssh_target", "pinned_host_key_evidence_sha256")
    ]
    owner_values.extend(
        payload.get("supporting_observation_contract", {}).get(field)
        for field in ("path", "size_bytes", "sha256")
    )
    owner_values.extend(
        supporting.get("target", {}).get(field) for field in ("stand_id", "ssh_target")
    )
    owner_values.extend(
        supporting.get("target", {})
        .get("pinned_host_key_evidence", {})
        .get(field)
        for field in ("path", "size_bytes", "sha256")
    )
    owner_values.extend(
        supporting.get("pilot_candidate", {}).get(field)
        for field in ("archive_locator", "sidecar_locator")
    )
    owner_values.extend(
        identity.get(field)
        for identity in supporting.get("prospective_local_action_identities", [])
        for field in ("execution_path", "source_path", "size_bytes", "sha256")
    )
    owner_values.extend(
        observation.get(field)
        for observation in supporting.get("observations", [])
        for field in (
            "local_action_identity_id",
            "argv_bytes_base64",
            "stdin_bytes_base64",
            "remote_command_bytes_base64",
            "output_locator",
            "max_output_bytes",
        )
    )
    owner_values.extend(
        supporting.get("limits", {}).get(field)
        for field in ("max_wall_seconds", "max_total_output_bytes")
    )
    if any(value is not None for value in owner_values):
        raise JournalError("S17-EXT-001 draft fabricated target or observation data")


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
        (builder.root / "evidence/s17-ext-001-supporting-contract-v2.json").unlink()

    run("missing-supporting-contract", missing_supporting_contract)

    def changed_supporting_contract(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        contract_path = builder.root / "evidence/s17-ext-001-supporting-contract-v2.json"
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
        "contract-observation-id-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document["observations"][0].update(
                {"observation_id": "ARBITRARY-OBSERVATION"}
            ),
        ),
    )
    run(
        "prospective-local-executable-sha-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document[
                "prospective_local_action_identities"
            ][0].update({"sha256": "a" * 64}),
        ),
    )
    run(
        "argv-executable-mismatch",
        lambda builder: builder.add_resolution(
            "S17-EXT-001",
            contract_mutator=lambda document: document["observations"][0].update(
                {"argv_bytes_base64": [b64("/wrong/executable")]}
            ),
        ),
    )

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

    with tempfile.TemporaryDirectory(prefix="stage17-negative-expired-action-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        expect_failure(
            "expired-action-readiness",
            lambda: builder.validate(
                as_of_utc="2030-01-02T00:00:00Z",
                requested_action_input_id="S17-EXT-001",
            ),
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


def self_test() -> tuple[int, int, int, int, int]:
    semantic_resolutions, semantic_transitions, mechanics_resolutions, mechanics_transitions = (
        positive_disk_test()
    )
    negatives = negative_tests()
    return (
        semantic_resolutions,
        semantic_transitions,
        mechanics_resolutions,
        mechanics_transitions,
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
        mechanics_resolutions = mechanics_transitions = negatives = 0
        if arguments.self_test:
            (
                semantic_resolutions,
                semantic_transitions,
                mechanics_resolutions,
                mechanics_transitions,
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
            f"negative={negatives} nonexistent_evidence=REJECTED "
            "generic_evidence=REJECTED reload=PASS Stage18=false stand=NOT_ACCESSED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
