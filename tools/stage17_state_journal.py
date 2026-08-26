#!/usr/bin/env python3
"""Typed, append-only Stage 17 operational-state journal validation."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
from dataclasses import dataclass
from typing import Any, Callable

from jsonschema import Draft202012Validator

from stage17_pilot_candidate_artifact import (
    ArtifactVerification,
    VERIFIER_ID,
    VERIFIER_VERSION,
    verify_pilot_candidate_artifact,
)


STATE_ORDER = (
    "PREPARED",
    "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT",
    "PREFLIGHT_ACCEPTED",
    "READY_FOR_STAGE17_PHASE_AUTHORIZATION",
)
CONFIRMATORY_ORDER = (
    "PLANNED",
    "COLLECTED_SEALED",
    "TRAINING_OPEN",
    "SELECTION_FROZEN",
    "VALIDATION_UNSEALED",
    "H3_EVALUATED",
    "H1H2_RELEASED",
    "ARCHIVED",
)
SCHEMA_PATHS = {
    "graph_schema_sha256": "config/schemas/stage17-operational-graph-definition-v1.schema.json",
    "catalog_schema_sha256": "config/schemas/stage17-external-input-catalog-v1.schema.json",
    "resolution_schema_sha256": "config/schemas/stage17-external-input-resolution-v1.schema.json",
    "transition_schema_sha256": "config/schemas/stage17-state-transition-v1.schema.json",
    "journal_schema_sha256": "config/schemas/stage17-state-journal-v1.schema.json",
    "custody_receipt_schema_sha256": "config/schemas/stage17-external-custody-receipt-v1.schema.json",
    "authorization_schema_sha256": "config/schemas/stage17-operational-authorization-evidence-v1.schema.json",
}
LEGACY_TEMPLATE_PATHS = {
    "adr_0104_sha256": "docs/decisions/0104-stage17-pilot-operational-governance-successor.md",
    "successor_v1_sha256": "config/stage17/stage17-operational-authorization-successor-v1.json",
    "checklist_v1_sha256": "config/stage17/stage17-external-input-checklist-v1.json",
    "predecessor_manifest_sha256": "config/stage17/d099-d108-preservation-manifest-v1.json",
}


class JournalError(ValueError):
    """The journal or one of its immutable dependencies is invalid."""


@dataclass(frozen=True)
class ExternalInputResolution:
    resolution_id: str
    sequence_number: int
    input_id: str
    actor: str
    recorded_at_utc: dt.datetime
    path: pathlib.Path
    sha256: str
    document: dict[str, Any]


@dataclass(frozen=True)
class StateTransition:
    transition_id: str
    sequence_number: int
    from_state: str
    to_state: str
    timestamp_utc: dt.datetime
    path: pathlib.Path
    sha256: str
    document: dict[str, Any]


@dataclass(frozen=True)
class JournalValidation:
    current_state: str
    pilot_ready: bool
    resolved_input_ids: tuple[str, ...]
    missing_input_ids: tuple[str, ...]
    resolution_count: int
    transition_count: int
    latest_journal_sha256: str


PilotVerifier = Callable[..., ArtifactVerification]


def canonical_json_bytes(document: object) -> bytes:
    return json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: pathlib.Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise JournalError(f"JSON root is not an object: {path}")
    return document


def parse_utc(value: object, label: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise JournalError(f"{label} is not an explicit UTC timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise JournalError(f"{label} is not a parseable UTC timestamp") from exception
    if parsed.tzinfo != dt.timezone.utc:
        raise JournalError(f"{label} is not UTC")
    return parsed


def repository_file(root: pathlib.Path, relative_text: object) -> pathlib.Path:
    if not isinstance(relative_text, str):
        raise JournalError("repository evidence path is missing")
    relative = pathlib.PurePosixPath(relative_text)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise JournalError(f"unsafe repository-relative path: {relative_text}")
    current = root
    for part in relative.parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except OSError as exception:
            raise JournalError(f"repository evidence file is absent: {relative_text}") from exception
        if stat.S_ISLNK(metadata.st_mode):
            raise JournalError(f"repository evidence path contains a symlink: {relative_text}")
    metadata = os.lstat(current)
    if not stat.S_ISREG(metadata.st_mode):
        raise JournalError(f"repository evidence is not a regular file: {relative_text}")
    return current


def validate_schema(
    document: dict[str, Any], schema_path: pathlib.Path, label: str
) -> None:
    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(document))
    if errors:
        first = errors[0]
        path = "/".join(str(part) for part in first.absolute_path)
        raise JournalError(f"{label} schema error at $/{path}: {first.message}")


def version_hashes(root: pathlib.Path) -> dict[str, str]:
    return {
        field: sha256_file(repository_file(root, relative))
        for field, relative in SCHEMA_PATHS.items()
    }


def verify_file_binding(
    root: pathlib.Path,
    *,
    path_text: object,
    expected_size: object,
    expected_sha256: object,
    label: str,
) -> pathlib.Path:
    path = repository_file(root, path_text)
    if not isinstance(expected_size, int) or path.stat().st_size != expected_size:
        raise JournalError(f"{label} byte-count mismatch")
    if sha256_file(path) != expected_sha256:
        raise JournalError(f"{label} SHA-256 mismatch")
    return path


def external_regular_file(locator: object, label: str) -> pathlib.Path:
    if not isinstance(locator, str):
        raise JournalError(f"{label} locator is missing")
    path = pathlib.Path(locator)
    if not path.is_absolute():
        raise JournalError(f"{label} locator is not absolute")
    current = pathlib.Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exception:
            raise JournalError(f"{label} bytes are absent: {locator}") from exception
        if stat.S_ISLNK(metadata.st_mode):
            raise JournalError(f"{label} locator contains a symlink: {locator}")
    if not stat.S_ISREG(os.lstat(path).st_mode):
        raise JournalError(f"{label} is not a regular file: {locator}")
    return path


def verify_external_file_binding(
    *, locator: object, expected_size: object, expected_sha256: object, label: str
) -> pathlib.Path:
    path = external_regular_file(locator, label)
    if not isinstance(expected_size, int) or path.stat().st_size != expected_size:
        raise JournalError(f"{label} byte-count mismatch")
    if sha256_file(path) != expected_sha256:
        raise JournalError(f"{label} SHA-256 mismatch")
    return path


def record_from_ref(
    root: pathlib.Path, reference: dict[str, Any], label: str
) -> tuple[pathlib.Path, dict[str, Any], str]:
    path = repository_file(root, reference.get("path"))
    digest = sha256_file(path)
    if digest != reference.get("sha256"):
        raise JournalError(f"{label} reference SHA-256 mismatch")
    return path, load_json(path), digest


def validate_graph_catalog(
    root: pathlib.Path, journal: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str, str, dict[str, str]]:
    graph_path, graph, graph_sha256 = record_from_ref(root, journal["graph"], "graph")
    catalog_path, catalog, catalog_sha256 = record_from_ref(
        root, journal["catalog"], "catalog"
    )
    validate_schema(
        graph,
        root / SCHEMA_PATHS["graph_schema_sha256"],
        "operational graph",
    )
    validate_schema(
        catalog,
        root / SCHEMA_PATHS["catalog_schema_sha256"],
        "external-input catalog",
    )
    del graph_path, catalog_path
    if tuple(graph.get("state_order", ())) != STATE_ORDER:
        raise JournalError("operational state order drifted")
    expected_edges = list(zip(STATE_ORDER[:-1], STATE_ORDER[1:], strict=True))
    observed_edges = [
        (item.get("from_state"), item.get("to_state"))
        for item in graph.get("transitions", [])
    ]
    if observed_edges != expected_edges:
        raise JournalError("operational transition graph drifted")
    confirmatory = graph.get("confirmatory_governance", {})
    if (
        tuple(confirmatory.get("access_state_order", ())) != CONFIRMATORY_ORDER
        or confirmatory.get("strict_chronology_preserved") is not True
        or confirmatory.get("pilot_role_collapse_applies") is not False
        or confirmatory.get("stage17_authority_may_authorize_stage18") is not False
    ):
        raise JournalError("Stage 18 chronology or authority boundary was weakened")
    expected_ids = [f"S17-EXT-{index:03d}" for index in range(1, 11)]
    catalog_ids = [item.get("input_id") for item in catalog.get("items", [])]
    if catalog_ids != expected_ids:
        raise JournalError("external-input catalog is not exact ordered S17-EXT-001..010")
    if graph.get("pilot_ready_input_ids") != expected_ids:
        raise JournalError("pilot-ready input family drifted")
    fixed_contracts = catalog.get("fixed_evidence_contracts")
    if not isinstance(fixed_contracts, list) or len(fixed_contracts) != 1:
        raise JournalError("fixed external-evidence contract family drifted")
    fixed_contract = fixed_contracts[0]
    if fixed_contract.get("input_id") != "S17-EXT-006":
        raise JournalError("pilot-candidate contract is not bound to S17-EXT-006")
    verify_file_binding(
        root,
        path_text=fixed_contract.get("path"),
        expected_size=fixed_contract.get("size_bytes"),
        expected_sha256=fixed_contract.get("sha256"),
        label="fixed S17-EXT-006 contract",
    )
    for path_field, hash_field, label in (
        ("schema_path", "schema_sha256", "fixed S17-EXT-006 contract schema"),
        ("verifier_path", "verifier_sha256", "fixed S17-EXT-006 verifier"),
    ):
        bound_path = repository_file(root, fixed_contract.get(path_field))
        if sha256_file(bound_path) != fixed_contract.get(hash_field):
            raise JournalError(f"{label} SHA-256 mismatch")
    for field, relative in LEGACY_TEMPLATE_PATHS.items():
        actual = sha256_file(repository_file(root, relative))
        if graph.get("legacy_templates", {}).get(field) != actual:
            raise JournalError(f"immutable legacy template drifted: {relative}")
    expected_versions = version_hashes(root)
    if journal.get("version_hashes") != expected_versions:
        raise JournalError("journal schema/version hashes drifted")
    return graph, catalog, graph_sha256, catalog_sha256, expected_versions


def validate_journal_lineage(
    root: pathlib.Path,
    latest_path: pathlib.Path,
    journal_schema_path: pathlib.Path,
    journal_directory: pathlib.Path | None,
) -> tuple[list[tuple[pathlib.Path, dict[str, Any], str]], dict[str, Any]]:
    lineage_reversed: list[tuple[pathlib.Path, dict[str, Any], str]] = []
    seen_hashes: set[str] = set()
    current_path = latest_path
    while True:
        if current_path.is_absolute():
            try:
                relative = current_path.relative_to(root)
            except ValueError as exception:
                raise JournalError("journal path is outside repository root") from exception
            current_path = repository_file(root, relative.as_posix())
        else:
            current_path = repository_file(root, current_path.as_posix())
        digest = sha256_file(current_path)
        if digest in seen_hashes:
            raise JournalError("journal predecessor cycle or replay detected")
        seen_hashes.add(digest)
        document = load_json(current_path)
        validate_schema(document, journal_schema_path, "state journal")
        lineage_reversed.append((current_path, document, digest))
        previous = document.get("previous_journal")
        if previous is None:
            break
        predecessor_path, _, predecessor_digest = record_from_ref(
            root, previous, "previous journal"
        )
        if predecessor_digest in seen_hashes:
            raise JournalError("journal predecessor cycle or replay detected")
        current_path = predecessor_path
    lineage = list(reversed(lineage_reversed))
    genesis_document = lineage[0][1]
    if genesis_document.get("journal_sequence_number") != 0:
        raise JournalError("journal lineage does not begin at sequence zero")
    if genesis_document.get("previous_journal") is not None:
        raise JournalError("genesis journal unexpectedly has a predecessor")
    previous_document = genesis_document
    for index, (_, document, _) in enumerate(lineage[1:], start=1):
        if document.get("journal_sequence_number") != index:
            raise JournalError("journal sequence is missing, duplicated, or replayed")
        for field in (
            "journal_id",
            "protocol_version",
            "graph",
            "catalog",
            "version_hashes",
            "genesis",
            "authority_boundary",
        ):
            if document.get(field) != genesis_document.get(field):
                raise JournalError(f"journal immutable field changed: {field}")
        prior_resolutions = previous_document.get("resolution_records", [])
        prior_transitions = previous_document.get("transition_records", [])
        resolutions = document.get("resolution_records", [])
        transitions = document.get("transition_records", [])
        if resolutions[: len(prior_resolutions)] != prior_resolutions:
            raise JournalError("resolution journal prefix changed")
        if transitions[: len(prior_transitions)] != prior_transitions:
            raise JournalError("transition journal prefix changed")
        appended = (len(resolutions) - len(prior_resolutions)) + (
            len(transitions) - len(prior_transitions)
        )
        if appended != 1:
            raise JournalError("each append-only journal successor must add exactly one record")
        if document.get("journal_sequence_number") != len(resolutions) + len(transitions):
            raise JournalError("journal sequence does not equal append count")
        previous_document = document
    latest = lineage[-1][1]
    if journal_directory is not None:
        children: dict[str, list[pathlib.Path]] = {}
        for candidate in sorted(journal_directory.glob("*.json")):
            try:
                candidate_document = load_json(candidate)
            except (OSError, json.JSONDecodeError, JournalError):
                continue
            if candidate_document.get("schema_version") != (
                "cpu-prefetch-stage17-state-journal/1"
            ):
                continue
            previous = candidate_document.get("previous_journal")
            if isinstance(previous, dict):
                children.setdefault(str(previous.get("sha256")), []).append(candidate)
        forks = [paths for paths in children.values() if len(paths) > 1]
        if forks:
            raise JournalError("journal fork detected")
    return lineage, latest


def validate_authorization_permissions(document: dict[str, Any], input_id: str) -> None:
    permissions = document.get("permissions", {})
    if permissions.get("stage18_authority") is not False:
        raise JournalError("authorization grants Stage 18 authority")
    if input_id == "S17-EXT-001":
        expected = {
            "stand_read_only": True,
            "stand_mutation": False,
            "privileged_controls": False,
            "calibration": False,
            "pilot_execution": False,
            "stage18_authority": False,
        }
        if permissions != expected or document.get("authority_scope") != "READ_ONLY_PREFLIGHT":
            raise JournalError("S17-EXT-001 authorization exceeds read-only preflight")
    elif input_id == "S17-EXT-005":
        if (
            document.get("authority_scope") != "PRIVILEGED_QUALIFICATION_CONTROL"
            or permissions.get("privileged_controls") is not True
            or permissions.get("calibration") is not False
            or permissions.get("pilot_execution") is not False
        ):
            raise JournalError("S17-EXT-005 authorization scope mismatch")
    elif input_id == "S17-EXT-010":
        if (
            document.get("authority_scope") != "STAGE17_PILOT_PHASE_ONLY"
            or permissions.get("pilot_execution") is not True
            or permissions.get("stage18_authority") is not False
        ):
            raise JournalError("S17-EXT-010 authorization scope mismatch")


def validate_resolutions(
    *,
    root: pathlib.Path,
    references: list[dict[str, Any]],
    graph_sha256: str,
    catalog_sha256: str,
    expected_versions: dict[str, str],
    catalog: dict[str, Any],
    pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None,
    pilot_verifier: PilotVerifier,
) -> dict[str, ExternalInputResolution]:
    catalog_items = {item["input_id"]: item for item in catalog["items"]}
    by_input: dict[str, ExternalInputResolution] = {}
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    resolution_schema = root / SCHEMA_PATHS["resolution_schema_sha256"]
    receipt_schema = root / SCHEMA_PATHS["custody_receipt_schema_sha256"]
    authorization_schema = root / SCHEMA_PATHS["authorization_schema_sha256"]
    for expected_sequence, reference in enumerate(references, start=1):
        path, document, digest = record_from_ref(
            root, reference, "external-input resolution"
        )
        validate_schema(document, resolution_schema, "external-input resolution")
        if document.get("sequence_number") != expected_sequence:
            raise JournalError("resolution sequence is missing, duplicated, or replayed")
        resolution_id = str(document["resolution_id"])
        input_id = str(document["input_id"])
        if resolution_id in seen_ids or digest in seen_hashes or input_id in by_input:
            raise JournalError("duplicate or replayed resolution record")
        seen_ids.add(resolution_id)
        seen_hashes.add(digest)
        if input_id not in catalog_items:
            raise JournalError(f"resolution uses unknown input ID: {input_id}")
        if document.get("graph_sha256") != graph_sha256:
            raise JournalError("resolution graph hash mismatch")
        if document.get("catalog_sha256") != catalog_sha256:
            raise JournalError("resolution catalog hash mismatch")
        if document.get("version_hashes") != expected_versions:
            raise JournalError("resolution schema/version hashes drifted")
        recorded_at = parse_utc(document.get("recorded_at_utc"), "resolution time")
        evidence_kinds: set[str] = set()
        repository_evidence_paths: set[str] = set()
        receipt_documents: list[dict[str, Any]] = []
        for evidence in document.get("evidence", []):
            kind = str(evidence.get("kind"))
            evidence_kinds.add(kind)
            if kind == "REPOSITORY_FILE":
                evidence_path = verify_file_binding(
                    root,
                    path_text=evidence.get("path"),
                    expected_size=evidence.get("size_bytes"),
                    expected_sha256=evidence.get("sha256"),
                    label="repository evidence",
                )
                repository_evidence_paths.add(
                    evidence_path.relative_to(root).as_posix()
                )
            elif kind == "EXTERNAL_CUSTODY_RECEIPT":
                receipt_path = verify_file_binding(
                    root,
                    path_text=evidence.get("receipt_path"),
                    expected_size=evidence.get("receipt_size_bytes"),
                    expected_sha256=evidence.get("receipt_sha256"),
                    label="external custody receipt",
                )
                receipt = load_json(receipt_path)
                validate_schema(receipt, receipt_schema, "external custody receipt")
                verify_external_file_binding(
                    locator=receipt.get("artifact_locator"),
                    expected_size=receipt.get("artifact_size_bytes"),
                    expected_sha256=receipt.get("artifact_sha256"),
                    label="external custody artifact",
                )
                for sidecar in receipt.get("sidecars", []):
                    verify_external_file_binding(
                        locator=sidecar.get("locator"),
                        expected_size=sidecar.get("size_bytes"),
                        expected_sha256=sidecar.get("sha256"),
                        label="external custody sidecar",
                    )
                contract_path = verify_file_binding(
                    root,
                    path_text=receipt.get("contract_path"),
                    expected_size=(
                        repository_file(root, receipt.get("contract_path")).stat().st_size
                    ),
                    expected_sha256=receipt.get("contract_sha256"),
                    label="external artifact contract",
                )
                load_json(contract_path)
                if parse_utc(receipt.get("verified_at_utc"), "receipt time") > recorded_at:
                    raise JournalError("receipt postdates its resolution")
                receipt_documents.append(receipt)
        policy = catalog_items[input_id]["evidence_policy"]
        if policy == "REPOSITORY_FILE" and evidence_kinds != {"REPOSITORY_FILE"}:
            raise JournalError(f"{input_id} evidence policy mismatch")
        if policy == "EXTERNAL_CUSTODY_RECEIPT" and "EXTERNAL_CUSTODY_RECEIPT" not in evidence_kinds:
            raise JournalError(f"{input_id} requires an external custody receipt")
        if policy == "MIXED" and evidence_kinds != {
            "REPOSITORY_FILE",
            "EXTERNAL_CUSTODY_RECEIPT",
        }:
            raise JournalError(f"{input_id} requires mixed repository/external evidence")
        authorization = document.get("authorization")
        if catalog_items[input_id]["authorization_required"]:
            if not isinstance(authorization, dict):
                raise JournalError(f"{input_id} requires authorization evidence")
            evidence_path_text = str(authorization.get("evidence_path"))
            if evidence_path_text not in repository_evidence_paths:
                raise JournalError("authorization path is not verified repository evidence")
            authorization_path = repository_file(root, evidence_path_text)
            authorization_document = load_json(authorization_path)
            validate_schema(
                authorization_document,
                authorization_schema,
                "operational authorization",
            )
            for field in (
                "authorization_id",
                "issued_at_utc",
                "expires_at_utc",
                "authority_scope",
            ):
                if authorization.get(field) != authorization_document.get(field):
                    raise JournalError(f"authorization {field} mismatch")
            if authorization_document.get("input_id") != input_id:
                raise JournalError("authorization input ID mismatch")
            if authorization_document.get("actor") != document.get("actor"):
                raise JournalError("authorization actor mismatch")
            issued = parse_utc(authorization.get("issued_at_utc"), "authorization issue")
            expires = parse_utc(authorization.get("expires_at_utc"), "authorization expiry")
            if not issued <= recorded_at < expires:
                raise JournalError("authorization is unknown, not yet valid, or expired")
            validate_authorization_permissions(authorization_document, input_id)
        elif authorization is not None:
            raise JournalError(f"{input_id} unexpectedly carries authorization")
        if input_id == "S17-EXT-006":
            if pilot_archive is None or pilot_sidecar is None:
                raise JournalError(
                    "S17-EXT-006 requires caller-supplied archive and sidecar bytes"
                )
            if len(receipt_documents) != 1:
                raise JournalError("S17-EXT-006 requires exactly one custody receipt")
            receipt = receipt_documents[0]
            fixed_contract = catalog["fixed_evidence_contracts"][0]
            if (
                receipt.get("contract_path") != fixed_contract["path"]
                or receipt.get("contract_sha256") != fixed_contract["sha256"]
                or receipt.get("verifier_id") != fixed_contract["verifier_id"]
                or receipt.get("verifier_version")
                != fixed_contract["verifier_version"]
            ):
                raise JournalError("S17-EXT-006 receipt is not bound to the fixed contract")
            if pathlib.Path(receipt["artifact_locator"]) != pilot_archive.absolute():
                raise JournalError("S17-EXT-006 archive locator differs from caller input")
            sidecars = receipt.get("sidecars", [])
            if (
                len(sidecars) != 1
                or pathlib.Path(sidecars[0]["locator"]) != pilot_sidecar.absolute()
            ):
                raise JournalError("S17-EXT-006 sidecar locator differs from caller input")
            contract_path = repository_file(root, receipt["contract_path"])
            result = pilot_verifier(
                repository_root=root,
                contract_path=contract_path,
                archive=pilot_archive,
                sidecar=pilot_sidecar,
            )
            if (
                receipt.get("artifact_size_bytes") != result.artifact_size_bytes
                or receipt.get("artifact_sha256") != result.artifact_sha256
                or receipt.get("verifier_id") != VERIFIER_ID
                or receipt.get("verifier_version") != VERIFIER_VERSION
            ):
                raise JournalError("S17-EXT-006 custody receipt does not match real bytes")
            if len(sidecars) != 1 or (
                sidecars[0].get("size_bytes") != result.sidecar_size_bytes
                or sidecars[0].get("sha256") != result.sidecar_sha256
            ):
                raise JournalError("S17-EXT-006 sidecar receipt does not match real bytes")
        by_input[input_id] = ExternalInputResolution(
            resolution_id=resolution_id,
            sequence_number=expected_sequence,
            input_id=input_id,
            actor=str(document["actor"]),
            recorded_at_utc=recorded_at,
            path=path,
            sha256=digest,
            document=document,
        )
    return by_input


def validate_transitions(
    *,
    root: pathlib.Path,
    references: list[dict[str, Any]],
    graph: dict[str, Any],
    graph_sha256: str,
    catalog_sha256: str,
    expected_versions: dict[str, str],
    genesis_sha256: str,
    resolutions: dict[str, ExternalInputResolution],
) -> tuple[str, list[StateTransition]]:
    current_state = str(graph["initial_state"])
    previous_sha256 = genesis_sha256
    transitions: list[StateTransition] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    schema_path = root / SCHEMA_PATHS["transition_schema_sha256"]
    graph_transitions = graph["transitions"]
    for expected_sequence, reference in enumerate(references, start=1):
        path, document, digest = record_from_ref(root, reference, "state transition")
        validate_schema(document, schema_path, "state transition")
        if expected_sequence > len(graph_transitions):
            raise JournalError("transition sequence exceeds finite graph")
        edge = graph_transitions[expected_sequence - 1]
        transition_id = str(document["transition_id"])
        if (
            document.get("sequence_number") != expected_sequence
            or transition_id in seen_ids
            or digest in seen_hashes
        ):
            raise JournalError("transition sequence is duplicated or replayed")
        seen_ids.add(transition_id)
        seen_hashes.add(digest)
        if document.get("previous_transition_sha256") != previous_sha256:
            raise JournalError("transition predecessor was replaced or forked")
        if (
            document.get("from_state") != current_state
            or document.get("from_state") != edge["from_state"]
            or document.get("to_state") != edge["to_state"]
        ):
            raise JournalError("transition skips, reverses, or leaves the finite graph")
        if document.get("graph_sha256") != graph_sha256:
            raise JournalError("transition graph hash mismatch")
        if document.get("catalog_sha256") != catalog_sha256:
            raise JournalError("transition catalog hash mismatch")
        if document.get("version_hashes") != expected_versions:
            raise JournalError("transition schema/version hashes drifted")
        if document.get("authority_scope") != edge["authority_scope"]:
            raise JournalError("transition authority scope mismatch")
        evidence = document.get("evidence_resolutions", [])
        evidence_by_input = {item.get("input_id"): item for item in evidence}
        if len(evidence_by_input) != len(evidence):
            raise JournalError("transition has duplicate evidence input IDs")
        if set(evidence_by_input) != set(edge["required_input_ids"]):
            raise JournalError("transition has an incomplete or extra evidence set")
        timestamp = parse_utc(document.get("timestamp_utc"), "transition time")
        for input_id, item in evidence_by_input.items():
            resolution = resolutions.get(str(input_id))
            if resolution is None:
                raise JournalError(f"transition references unknown resolution: {input_id}")
            if (
                item.get("resolution_id") != resolution.resolution_id
                or item.get("sha256") != resolution.sha256
            ):
                raise JournalError(f"transition resolution identity mismatch: {input_id}")
            if resolution.recorded_at_utc > timestamp:
                raise JournalError("transition predates required evidence")
        authorizations = document.get("authorizations", [])
        authorization_by_input = {item.get("input_id"): item for item in authorizations}
        if len(authorization_by_input) != len(authorizations):
            raise JournalError("transition has duplicate authorization input IDs")
        if set(authorization_by_input) != set(edge["authorization_input_ids"]):
            raise JournalError("transition authorization set is unknown or incomplete")
        for input_id, item in authorization_by_input.items():
            resolution = resolutions.get(str(input_id))
            if resolution is None:
                raise JournalError("transition references unknown authorization")
            authorization = resolution.document.get("authorization")
            if not isinstance(authorization, dict):
                raise JournalError("transition references a non-authorization resolution")
            if (
                item.get("resolution_id") != resolution.resolution_id
                or item.get("authorization_id") != authorization.get("authorization_id")
                or item.get("authority_scope") != authorization.get("authority_scope")
            ):
                raise JournalError("transition authorization identity mismatch")
            issued = parse_utc(authorization.get("issued_at_utc"), "authorization issue")
            expires = parse_utc(authorization.get("expires_at_utc"), "authorization expiry")
            if not issued <= timestamp < expires:
                raise JournalError("transition authorization is expired or not yet valid")
        current_state = str(document["to_state"])
        previous_sha256 = digest
        transitions.append(
            StateTransition(
                transition_id=transition_id,
                sequence_number=expected_sequence,
                from_state=str(document["from_state"]),
                to_state=current_state,
                timestamp_utc=timestamp,
                path=path,
                sha256=digest,
                document=document,
            )
        )
    return current_state, transitions


def validate_journal(
    *,
    repository_root: pathlib.Path,
    latest_journal: pathlib.Path,
    journal_directory: pathlib.Path | None = None,
    pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None,
    as_of_utc: str | None = None,
    pilot_verifier: PilotVerifier = verify_pilot_candidate_artifact,
) -> JournalValidation:
    root = repository_root.resolve()
    journal_schema = root / SCHEMA_PATHS["journal_schema_sha256"]
    lineage, latest = validate_journal_lineage(
        root, latest_journal, journal_schema, journal_directory
    )
    graph, catalog, graph_sha256, catalog_sha256, expected_versions = (
        validate_graph_catalog(root, latest)
    )
    genesis = latest["genesis"]
    expected_genesis_record = {
        "journal_id": latest["journal_id"],
        "protocol_version": latest["protocol_version"],
        "initial_state": graph["initial_state"],
        "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256,
        "version_hashes": expected_versions,
        "authority_scope": "NO_EXECUTION_AUTHORITY",
    }
    if genesis.get("genesis_record") != expected_genesis_record:
        raise JournalError("genesis record drifted")
    genesis_sha256 = sha256_bytes(canonical_json_bytes(expected_genesis_record))
    if genesis.get("genesis_sha256") != genesis_sha256:
        raise JournalError("genesis SHA-256 mismatch")
    if lineage[-1][1].get("journal_sequence_number") != len(
        latest.get("resolution_records", [])
    ) + len(latest.get("transition_records", [])):
        raise JournalError("latest journal append count mismatch")
    resolutions = validate_resolutions(
        root=root,
        references=latest.get("resolution_records", []),
        graph_sha256=graph_sha256,
        catalog_sha256=catalog_sha256,
        expected_versions=expected_versions,
        catalog=catalog,
        pilot_archive=pilot_archive,
        pilot_sidecar=pilot_sidecar,
        pilot_verifier=pilot_verifier,
    )
    current_state, transitions = validate_transitions(
        root=root,
        references=latest.get("transition_records", []),
        graph=graph,
        graph_sha256=graph_sha256,
        catalog_sha256=catalog_sha256,
        expected_versions=expected_versions,
        genesis_sha256=genesis_sha256,
        resolutions=resolutions,
    )
    expected_ids = tuple(item["input_id"] for item in catalog["items"])
    resolved_ids = tuple(item for item in expected_ids if item in resolutions)
    missing_ids = tuple(item for item in expected_ids if item not in resolutions)
    pilot_ready = current_state == STATE_ORDER[-1] and not missing_ids
    if pilot_ready:
        if as_of_utc is None:
            pilot_ready = False
        else:
            evaluation_time = parse_utc(as_of_utc, "pilot readiness evaluation time")
            pilot_authorization = resolutions["S17-EXT-010"].document.get(
                "authorization"
            )
            if not isinstance(pilot_authorization, dict):
                raise JournalError("pilot-ready state has no S17-EXT-010 authorization")
            issued = parse_utc(
                pilot_authorization.get("issued_at_utc"), "pilot authorization issue"
            )
            expires = parse_utc(
                pilot_authorization.get("expires_at_utc"), "pilot authorization expiry"
            )
            if not issued <= evaluation_time < expires:
                raise JournalError("pilot authorization is expired or not yet valid")
    return JournalValidation(
        current_state=current_state,
        pilot_ready=pilot_ready,
        resolved_input_ids=resolved_ids,
        missing_input_ids=missing_ids,
        resolution_count=len(resolutions),
        transition_count=len(transitions),
        latest_journal_sha256=lineage[-1][2],
    )
