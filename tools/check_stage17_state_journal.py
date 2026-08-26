#!/usr/bin/env python3
"""Validate and disk-test the append-only Stage 17 state journal."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile
from typing import Any

from stage17_pilot_candidate_artifact import ArtifactVerification
from stage17_state_journal import (
    LEGACY_TEMPLATE_PATHS,
    SCHEMA_PATHS,
    JournalError,
    canonical_json_bytes,
    load_json,
    repository_file,
    sha256_bytes,
    sha256_file,
    validate_journal,
    version_hashes,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_JOURNAL = pathlib.Path(
    "config/stage17/journal/stage17-state-journal-000000.json"
)
DRAFT_PATH = pathlib.Path(
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


class SyntheticBuilder:
    """Write immutable fixtures and journal successors to a real temporary tree."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root
        for relative in (
            *SCHEMA_PATHS.values(),
            *LEGACY_TEMPLATE_PATHS.values(),
            GRAPH_PATH.as_posix(),
            CATALOG_PATH.as_posix(),
            PILOT_CONTRACT_PATH.as_posix(),
            PILOT_CONTRACT_SCHEMA_PATH.as_posix(),
            PILOT_VERIFIER_PATH.as_posix(),
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
    ) -> dict[str, Any]:
        sequence = len(self.resolutions) + 1
        actor = "synthetic-stage17-owner"
        item = next(entry for entry in self.catalog["items"] if entry["input_id"] == input_id)
        authorization_document: dict[str, Any] | None = None
        authorization_evidence: dict[str, Any] | None = None
        if item["authorization_required"]:
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
                "evidence_path": authorization_evidence["path"],
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

    def validate(self, *, as_of_utc: str | None = None):
        return validate_journal(
            repository_root=self.root,
            latest_journal=self.latest_path.relative_to(self.root),
            journal_directory=self.root / "config/stage17/journal",
            pilot_archive=self.pilot_archive,
            pilot_sidecar=self.pilot_sidecar,
            as_of_utc=as_of_utc,
            pilot_verifier=synthetic_pilot_verifier,
        )


def synthetic_pilot_verifier(**arguments: Any) -> ArtifactVerification:
    del arguments["repository_root"], arguments["contract_path"]
    archive = pathlib.Path(arguments["archive"])
    sidecar = pathlib.Path(arguments["sidecar"])
    archive_sha256 = sha256_file(archive)
    if sidecar.read_bytes() != f"{archive_sha256}  {archive.name}\n".encode("ascii"):
        raise JournalError("synthetic pilot sidecar does not bind its archive")
    return ArtifactVerification(
        artifact_size_bytes=archive.stat().st_size,
        artifact_sha256=archive_sha256,
        sidecar_size_bytes=sidecar.stat().st_size,
        sidecar_sha256=sha256_file(sidecar),
        manifest_sha256="synthetic-not-used",
        file_count=1,
    )


def expect_failure(label: str, action) -> None:
    try:
        action()
    except (JournalError, OSError, json.JSONDecodeError):
        return
    raise JournalError(f"negative self-test passed unexpectedly: {label}")


def validate_s17_ext_001_draft(root: pathlib.Path, journal_path: pathlib.Path) -> None:
    draft = load_json(repository_file(root, DRAFT_PATH.as_posix()))
    relative_journal = (
        journal_path.relative_to(root) if journal_path.is_absolute() else journal_path
    )
    journal = load_json(repository_file(root, relative_journal.as_posix()))
    if (
        draft.get("status") != "DRAFT_NOT_ISSUED_OWNER_INPUT_REQUIRED"
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
    bindings = draft.get("journal_bindings", {})
    if (
        bindings.get("graph_sha256") != journal["graph"]["sha256"]
        or bindings.get("catalog_sha256") != journal["catalog"]["sha256"]
        or bindings.get("genesis_sha256") != journal["genesis"]["genesis_sha256"]
        or bindings.get("journal_path") != relative_journal.as_posix()
    ):
        raise JournalError("S17-EXT-001 draft journal binding drifted")
    payload = draft.get("authorization_payload", {})
    fixed_observations = [
        "S17-RO-PREFLIGHT-001-TARGET-AND-TRANSPORT-IDENTITY",
        "S17-RO-PREFLIGHT-002-ARCHIVE-AND-SIDECAR-BYTE-VERIFICATION",
        "S17-RO-PREFLIGHT-003-BUNDLE-INTERNAL-VERIFICATION",
        "S17-RO-PREFLIGHT-004-NONPRIVILEGED-SELF-TESTS",
        "S17-RO-PREFLIGHT-005-RUNTIME-TOOL-IDENTITIES",
        "S17-RO-PREFLIGHT-006-READ-ONLY-PLATFORM-INVENTORY",
    ]
    if (
        payload.get("input_id") != "S17-EXT-001"
        or payload.get("authority_scope") != "READ_ONLY_PREFLIGHT"
        or payload.get("frozen_observation_ids") != fixed_observations
        or payload.get("permissions")
        != {
            "stand_read_only": True,
            "stand_mutation": False,
            "privileged_controls": False,
            "calibration": False,
            "pilot_execution": False,
            "stage18_authority": False,
        }
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
        for field in ("max_commands", "max_wall_seconds")
    ):
        raise JournalError("S17-EXT-001 draft fabricated owner limits")
    supporting = draft.get("supporting_observation_contract", {})
    observed_identifiers = [
        item.get("observation_id")
        for item in supporting.get("observations", [])
    ]
    if observed_identifiers != fixed_observations:
        raise JournalError("S17-EXT-001 supporting observation family drifted")
    owner_fields = (
        *supporting.get("target", {}).values(),
        supporting.get("archive_locator"),
        supporting.get("sidecar_locator"),
        *(
            value
            for observation in supporting.get("observations", [])
            for key, value in observation.items()
            if key != "observation_id"
        ),
    )
    if any(value is not None for value in owner_fields):
        raise JournalError("S17-EXT-001 draft fabricated target or observation data")


def positive_disk_test() -> tuple[int, int]:
    with tempfile.TemporaryDirectory(prefix="stage17-journal-positive-") as temporary:
        builder = SyntheticBuilder(pathlib.Path(temporary))
        genesis = builder.validate()
        if genesis.current_state != "PREPARED" or genesis.pilot_ready:
            raise JournalError("disk genesis did not evaluate to PREPARED")
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        first = builder.validate()
        if first.current_state != "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT":
            raise JournalError("first persisted transition did not reload")
        builder.add_resolution("S17-EXT-002")
        builder.add_resolution("S17-EXT-003")
        builder.add_transition()
        second = builder.validate()
        if second.current_state != "PREFLIGHT_ACCEPTED":
            raise JournalError("second persisted transition did not reload")
        for input_id in ("S17-EXT-004", "S17-EXT-005", "S17-EXT-006"):
            builder.add_resolution(input_id)
        builder.add_transition()
        third = builder.validate()
        if (
            third.current_state != "READY_FOR_STAGE17_PHASE_AUTHORIZATION"
            or third.pilot_ready
        ):
            raise JournalError("phase-ready state or pilot gate was miscomputed")
        for input_id in ("S17-EXT-007", "S17-EXT-008", "S17-EXT-009", "S17-EXT-010"):
            builder.add_resolution(input_id)
        final = builder.validate(as_of_utc=utc(90))
        if not final.pilot_ready or final.missing_input_ids:
            raise JournalError("fully persisted synthetic fixture did not become pilot-ready")
        for reference in builder.latest_document["resolution_records"]:
            path = builder.root / reference["path"]
            if sha256_file(path) != reference["sha256"] or not load_json(path):
                raise JournalError("resolution fixture did not reload from disk")
        for reference in builder.latest_document["transition_records"]:
            path = builder.root / reference["path"]
            if sha256_file(path) != reference["sha256"] or not load_json(path):
                raise JournalError("transition fixture did not reload from disk")
        return final.resolution_count, final.transition_count


def negative_tests() -> int:
    negative_count = 0

    def run(label: str, scenario) -> None:
        nonlocal negative_count
        with tempfile.TemporaryDirectory(prefix=f"stage17-negative-{label}-") as temporary:
            builder = SyntheticBuilder(pathlib.Path(temporary))
            scenario(builder)
            expect_failure(label, builder.validate)
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

    run("skip", skip)

    def incomplete(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(overrides={"evidence_resolutions": []})

    run("incomplete", incomplete)

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

    run("duplicate-transition-input", duplicate_transition_input)

    def replaced_predecessor(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition(overrides={"previous_transition_sha256": "b" * 64})

    run("replaced-predecessor", replaced_predecessor)

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

    run("unknown-authorization", unknown_authorization)

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

    run("backward", backward)

    def duplicate_sequence(builder: SyntheticBuilder) -> None:
        builder.add_resolution("S17-EXT-001")
        builder.add_transition()
        builder.add_resolution("S17-EXT-002")
        builder.add_resolution("S17-EXT-003")
        builder.add_transition(overrides={"sequence_number": 1})

    run("duplicate-sequence", duplicate_sequence)

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


def self_test() -> tuple[int, int, int]:
    resolutions, transitions = positive_disk_test()
    negatives = negative_tests()
    return resolutions, transitions, negatives


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=pathlib.Path, default=ROOT)
    parser.add_argument("--journal", type=pathlib.Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--journal-directory", type=pathlib.Path)
    parser.add_argument("--pilot-candidate-archive", type=pathlib.Path)
    parser.add_argument("--pilot-candidate-sidecar", type=pathlib.Path)
    parser.add_argument("--as-of-utc")
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
        )
        validate_s17_ext_001_draft(root, arguments.journal)
        resolutions = transitions = negatives = 0
        if arguments.self_test:
            resolutions, transitions, negatives = self_test()
    except (JournalError, OSError, json.JSONDecodeError) as exception:
        print(f"stage17-state-journal-check: FAIL: {exception}", file=sys.stderr)
        return 1
    status = {
        "current_state": result.current_state,
        "pilot_ready": result.pilot_ready,
        "resolved_input_ids": list(result.resolved_input_ids),
        "missing_input_ids": list(result.missing_input_ids),
        "transition_count": result.transition_count,
    }
    if arguments.print_status:
        print(json.dumps(status, sort_keys=True, separators=(",", ":")))
    else:
        print(
            "stage17-state-journal-check: PASS "
            f"state={result.current_state} resolved={result.resolution_count} "
            f"missing={len(result.missing_input_ids)} pilot_ready={str(result.pilot_ready).lower()} "
            f"disk_positive={resolutions}/{transitions} negative={negatives} "
            "nonexistent_evidence=REJECTED reload=PASS Stage18=false stand=NOT_ACCESSED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
