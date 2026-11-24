#!/usr/bin/env python3
"""Stage 17 journal runtime with immutable-repository/external-evidence split.

The logical graph, catalog, resolution, transition, and journal records remain
the accepted v1 contracts.  This runtime changes only locator resolution:
immutable graph/catalog/schema/repository evidence is rooted at the verified
bundle, while journal snapshots, resolution/transition records, and custody
receipts are rooted at a distinct owner-controlled evidence directory.
"""

from __future__ import annotations

import dataclasses
import json
import os
import pathlib
import stat
from typing import Any

import stage17_semantic_verifier_v11 as semantic
import stage17_state_journal as base
import stage17_state_journal_v8 as predecessor


SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = base.SCHEMA_PATHS
JournalError = base.JournalError
ExternalInputResolution = base.ExternalInputResolution
StateTransition = base.StateTransition


@dataclasses.dataclass(frozen=True)
class OperationalJournalValidation:
    current_state: str
    pilot_ready: bool
    resolved_input_ids: tuple[str, ...]
    missing_input_ids: tuple[str, ...]
    resolution_count: int
    transition_count: int
    latest_journal_sha256: str
    action_ready: bool
    stand_status: str
    resolutions: dict[str, ExternalInputResolution]
    transitions: tuple[StateTransition, ...]


def _external_file(root: pathlib.Path, relative_text: object,
                   label: str) -> pathlib.Path:
    if not isinstance(relative_text, str):
        raise JournalError(f"{label} path is missing")
    relative = pathlib.PurePosixPath(relative_text)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise JournalError(f"unsafe {label} path")
    descriptor = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        for index, component in enumerate(relative.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index + 1 < len(relative.parts):
                flags |= os.O_DIRECTORY
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise JournalError(f"{label} is not a regular file")
        path = root.joinpath(*relative.parts)
        return path
    except OSError as exception:
        raise JournalError(f"{label} cannot be opened safely") from exception
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _external_bytes(root: pathlib.Path, relative_text: object,
                    label: str, maximum_bytes: int = 64 * 1024 * 1024) \
        -> tuple[pathlib.Path, bytes]:
    """Read one external record through the descriptor used for validation.

    Returning a pathname from a component-wise validation and reopening it was
    a TOCTOU boundary: an owner could exchange a directory component between
    the two opens.  Operational control records are small, so admission pins
    their exact bytes during the single no-follow descriptor traversal.
    """
    if not isinstance(relative_text, str):
        raise JournalError(f"{label} path is missing")
    relative = pathlib.PurePosixPath(relative_text)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise JournalError(f"unsafe {label} path")
    descriptor = os.open(
        root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    try:
        for index, component in enumerate(relative.parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
            if index + 1 < len(relative.parts):
                flags |= os.O_DIRECTORY
            child = os.open(component, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_size < 1
                or metadata.st_size > maximum_bytes):
            raise JournalError(f"{label} is not a bounded nonempty regular file")
        payload = os.pread(descriptor, metadata.st_size + 1, 0)
        if len(payload) != metadata.st_size:
            raise JournalError(f"{label} changed during its pinned read")
        path = root.joinpath(*relative.parts)
        return path, payload
    except OSError as exception:
        raise JournalError(f"{label} cannot be opened safely") from exception
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _record(root: pathlib.Path, reference: dict[str, Any], label: str) \
        -> tuple[pathlib.Path, dict[str, Any], str]:
    path, payload = _external_bytes(root, reference.get("path"), label)
    digest = base.sha256_bytes(payload)
    if digest != reference.get("sha256"):
        raise JournalError(f"{label} reference SHA-256 mismatch")
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exception:
        raise JournalError(f"{label} is not valid JSON") from exception
    if not isinstance(document, dict):
        raise JournalError(f"{label} JSON root is not an object")
    return path, document, digest


def _lineage(
    *, evidence_root: pathlib.Path, latest_path: pathlib.Path,
    schema_path: pathlib.Path, journal_directory: pathlib.Path | None,
) -> tuple[list[tuple[pathlib.Path, dict[str, Any], str]], dict[str, Any]]:
    try:
        current = latest_path.resolve().relative_to(evidence_root)
    except ValueError as exception:
        raise JournalError("journal is outside the operational evidence root") from exception
    reversed_lineage: list[tuple[pathlib.Path, dict[str, Any], str]] = []
    seen: set[str] = set()
    while True:
        path, payload = _external_bytes(
            evidence_root, current.as_posix(), "state journal"
        )
        digest = base.sha256_bytes(payload)
        if digest in seen:
            raise JournalError("journal predecessor cycle/replay detected")
        seen.add(digest)
        try:
            document = json.loads(payload)
        except json.JSONDecodeError as exception:
            raise JournalError("state journal is not valid JSON") from exception
        if not isinstance(document, dict):
            raise JournalError("state journal JSON root is not an object")
        base.validate_schema(document, schema_path, "state journal")
        reversed_lineage.append((path, document, digest))
        previous = document.get("previous_journal")
        if previous is None:
            break
        predecessor_path, _, predecessor_digest = _record(
            evidence_root, previous, "previous journal"
        )
        if predecessor_digest in seen:
            raise JournalError("journal predecessor cycle/replay detected")
        current = predecessor_path.relative_to(evidence_root)
    lineage = list(reversed(reversed_lineage))
    genesis = lineage[0][1]
    if genesis.get("journal_sequence_number") != 0 or genesis.get(
            "previous_journal") is not None:
        raise JournalError("operational journal has no valid genesis")
    prior = genesis
    for sequence, (_, document, _) in enumerate(lineage[1:], 1):
        if document.get("journal_sequence_number") != sequence:
            raise JournalError("journal sequence is missing/duplicated/replayed")
        for field in (
            "journal_id", "protocol_version", "graph", "catalog",
            "version_hashes", "genesis", "authority_boundary",
        ):
            if document.get(field) != genesis.get(field):
                raise JournalError(f"journal immutable field changed: {field}")
        old_resolutions = prior.get("resolution_records", [])
        old_transitions = prior.get("transition_records", [])
        resolutions = document.get("resolution_records", [])
        transitions = document.get("transition_records", [])
        if (resolutions[:len(old_resolutions)] != old_resolutions
                or transitions[:len(old_transitions)] != old_transitions):
            raise JournalError("journal append-only prefix changed")
        if ((len(resolutions) - len(old_resolutions))
                + (len(transitions) - len(old_transitions)) != 1
                or sequence != len(resolutions) + len(transitions)):
            raise JournalError("journal successor did not append exactly one record")
        prior = document
    if journal_directory is not None:
        children: dict[str, int] = {}
        for candidate in journal_directory.glob("*.json"):
            try:
                document = base.load_json(candidate)
            except BaseException:
                continue
            previous = document.get("previous_journal")
            if document.get("schema_version") == "cpu-prefetch-stage17-state-journal/1" \
                    and isinstance(previous, dict):
                digest = str(previous.get("sha256"))
                children[digest] = children.get(digest, 0) + 1
        if any(count > 1 for count in children.values()):
            raise JournalError("journal fork detected")
    return lineage, lineage[-1][1]


def _receipt_documents(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    evidence: list[dict[str, Any]], recorded_at: Any,
) -> tuple[set[str], list[tuple[pathlib.Path, dict[str, Any]]],
           list[dict[str, Any]]]:
    kinds: set[str] = set()
    repositories: list[tuple[pathlib.Path, dict[str, Any]]] = []
    receipts: list[dict[str, Any]] = []
    receipt_schema = repository_root / SCHEMA_PATHS["custody_receipt_schema_sha256"]
    for item in evidence:
        kind = str(item.get("kind")); kinds.add(kind)
        if kind == "REPOSITORY_FILE":
            path = base.verify_file_binding(
                repository_root, path_text=item.get("path"),
                expected_size=item.get("size_bytes"),
                expected_sha256=item.get("sha256"), label="repository evidence",
            )
            repositories.append((path, base.load_json(path)))
        elif kind == "EXTERNAL_CUSTODY_RECEIPT":
            path, payload = _external_bytes(
                evidence_root, item.get("receipt_path"),
                "external custody receipt",
            )
            if (len(payload), base.sha256_bytes(payload)) != (
                    item.get("receipt_size_bytes"), item.get("receipt_sha256")):
                raise JournalError("external custody receipt bytes drifted")
            try:
                receipt = json.loads(payload)
            except json.JSONDecodeError as exception:
                raise JournalError(
                    "external custody receipt is not valid JSON"
                ) from exception
            if not isinstance(receipt, dict):
                raise JournalError(
                    "external custody receipt JSON root is not an object"
                )
            if receipt.get("schema_version") == \
                    "cpu-prefetch-stage17-external-custody-receipt/2":
                base.validate_schema(
                    receipt,
                    repository_root / "config/schemas/stage17-external-custody-receipt-v2.schema.json",
                    "external custody receipt v2",
                )
            else:
                base.validate_schema(receipt, receipt_schema, "external custody receipt")
            base.verify_external_file_binding(
                locator=receipt.get("artifact_locator"),
                expected_size=receipt.get("artifact_size_bytes"),
                expected_sha256=receipt.get("artifact_sha256"),
                label="external custody artifact",
            )
            for sidecar in receipt.get("sidecars", []):
                base.verify_external_file_binding(
                    locator=sidecar.get("locator"),
                    expected_size=sidecar.get("size_bytes"),
                    expected_sha256=sidecar.get("sha256"),
                    label="external custody sidecar",
                )
            if receipt.get("schema_version") == \
                    "cpu-prefetch-stage17-external-custody-receipt/2":
                binding = receipt["contract"]
                contract, contract_payload = _external_bytes(
                    evidence_root, binding["locator"], "external artifact contract",
                )
                if (len(contract_payload), base.sha256_bytes(contract_payload)) != (
                        binding["size_bytes"], binding["sha256"]):
                    raise JournalError("external artifact contract bytes drifted")
                try:
                    parsed_contract = json.loads(contract_payload)
                except json.JSONDecodeError as exception:
                    raise JournalError("external artifact contract is not JSON") from exception
                if not isinstance(parsed_contract, dict):
                    raise JournalError("external artifact contract root is not an object")
                receipt["contract_path"] = str(contract)
                receipt["contract_sha256"] = binding["sha256"]
            else:
                contract = base.verify_file_binding(
                    repository_root, path_text=receipt.get("contract_path"),
                    expected_size=base.repository_file(
                        repository_root, receipt.get("contract_path")
                    ).stat().st_size,
                    expected_sha256=receipt.get("contract_sha256"),
                    label="external artifact contract",
                )
                base.load_json(contract)
            if base.parse_utc(receipt.get("verified_at_utc"), "receipt time") > recorded_at:
                raise JournalError("receipt postdates its resolution")
            receipts.append(receipt)
        else:
            raise JournalError(f"unknown evidence kind: {kind}")
    return kinds, repositories, receipts


def _resolutions(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    references: list[dict[str, Any]], graph_sha256: str, catalog_sha256: str,
    versions: dict[str, str], catalog: dict[str, Any], genesis_sha256: str,
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
    allow_synthetic: bool,
) -> dict[str, ExternalInputResolution]:
    policy = predecessor._policy(
        repository_root, graph_sha256, catalog_sha256, genesis_sha256,
        versions["resolution_schema_sha256"],
    )
    entries = {item["input_id"]: item for item in policy["entries"]}
    catalog_items = {item["input_id"]: item for item in catalog["items"]}
    result: dict[str, ExternalInputResolution] = {}
    seen_ids: set[str] = set(); seen_hashes: set[str] = set()
    schema = repository_root / SCHEMA_PATHS["resolution_schema_sha256"]
    for sequence, reference in enumerate(references, 1):
        path, document, digest = _record(
            evidence_root, reference, "external-input resolution"
        )
        base.validate_schema(document, schema, "external-input resolution")
        input_id = str(document["input_id"]); resolution_id = str(document["resolution_id"])
        if (document.get("sequence_number") != sequence or input_id in result
                or resolution_id in seen_ids or digest in seen_hashes):
            raise JournalError("resolution sequence is missing/duplicated/replayed")
        seen_ids.add(resolution_id); seen_hashes.add(digest)
        expected_entry = {
            "input_id": input_id, "status": "IMPLEMENTED",
            "verifier_id": semantic.VERIFIER_ID,
            "verifier_version": semantic.VERIFIER_VERSION,
        }
        if input_id not in catalog_items or entries.get(input_id) != expected_entry:
            raise JournalError(f"semantic registry drifted: {input_id}")
        if (document.get("graph_sha256"), document.get("catalog_sha256"),
                document.get("version_hashes")) != (
                    graph_sha256, catalog_sha256, versions):
            raise JournalError("resolution graph/catalog/version binding drifted")
        recorded = base.parse_utc(document.get("recorded_at_utc"), "resolution time")
        kinds, repository_documents, receipt_documents = _receipt_documents(
            repository_root=repository_root, evidence_root=evidence_root,
            evidence=document.get("evidence", []), recorded_at=recorded,
        )
        expected_kinds = {
            "REPOSITORY_FILE": {"REPOSITORY_FILE"},
            "EXTERNAL_CUSTODY_RECEIPT": {"EXTERNAL_CUSTODY_RECEIPT"},
            "MIXED": {"REPOSITORY_FILE", "EXTERNAL_CUSTODY_RECEIPT"},
        }[catalog_items[input_id]["evidence_policy"]]
        if kinds != expected_kinds:
            raise JournalError(f"{input_id} evidence policy mismatch")
        requires_authority = catalog_items[input_id]["authorization_required"]
        summary = document.get("authorization")
        if requires_authority != isinstance(summary, dict):
            raise JournalError(f"{input_id} authorization presence mismatch")
        try:
            verified = semantic.verify_input(
                input_id=input_id, root=repository_root, resolution=document,
                repository_documents=repository_documents,
                receipt_documents=receipt_documents,
                admitted_resolutions=result, allow_synthetic=allow_synthetic,
                policy=policy, graph_sha256=graph_sha256,
                catalog_sha256=catalog_sha256, genesis_sha256=genesis_sha256,
                catalog=catalog,
                resolution_schema_sha256=versions["resolution_schema_sha256"],
                pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
            )
        except semantic.SemanticAdmissionError as exception:
            raise JournalError(str(exception)) from exception
        authorization = verified.get("authorization")
        context = verified.get("context")
        if requires_authority:
            if not isinstance(authorization, dict):
                raise JournalError(f"{input_id} verifier returned no authority")
            expected_summary = {
                field: authorization[field] for field in (
                    "authorization_id", "issued_at_utc", "expires_at_utc",
                    "authority_scope",
                ) if field in authorization
            }
            if "authority_scope" not in expected_summary:
                expected_summary["authority_scope"] = {
                    "STAGE17-BLINDED-PILOT": "STAGE17_PILOT_PHASE_ONLY"
                }.get(authorization.get("action_id"), authorization.get("action_id"))
            if any(summary.get(key) != value
                   for key, value in expected_summary.items()):
                raise JournalError(f"{input_id} authorization summary drifted")
        result[input_id] = ExternalInputResolution(
            resolution_id, sequence, input_id, str(document["actor"]), recorded,
            path, digest, document, authorization,
            context if isinstance(context, dict) else None,
        )
    return result


def _transitions(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    references: list[dict[str, Any]], graph: dict[str, Any], graph_sha256: str,
    catalog_sha256: str, versions: dict[str, str], genesis_sha256: str,
    resolutions: dict[str, ExternalInputResolution],
) -> tuple[str, list[StateTransition]]:
    current = str(graph["initial_state"]); previous_sha = genesis_sha256
    result: list[StateTransition] = []; seen_ids: set[str] = set(); seen_sha: set[str] = set()
    schema = repository_root / SCHEMA_PATHS["transition_schema_sha256"]
    for sequence, reference in enumerate(references, 1):
        path, document, digest = _record(evidence_root, reference, "state transition")
        base.validate_schema(document, schema, "state transition")
        if sequence > len(graph["transitions"]):
            raise JournalError("transition exceeds finite graph")
        edge = graph["transitions"][sequence - 1]
        transition_id = str(document["transition_id"])
        if (document.get("sequence_number") != sequence or transition_id in seen_ids
                or digest in seen_sha or document.get("previous_transition_sha256") != previous_sha
                or document.get("from_state") != current
                or document.get("from_state") != edge["from_state"]
                or document.get("to_state") != edge["to_state"]):
            raise JournalError("transition sequence/predecessor/edge drifted")
        seen_ids.add(transition_id); seen_sha.add(digest)
        if (document.get("graph_sha256"), document.get("catalog_sha256"),
                document.get("version_hashes"), document.get("authority_scope")) != (
                    graph_sha256, catalog_sha256, versions, edge["authority_scope"]):
            raise JournalError("transition immutable binding drifted")
        evidence = {item["input_id"]: item
                    for item in document.get("evidence_resolutions", [])}
        if set(evidence) != set(edge["required_input_ids"]):
            raise JournalError("transition evidence set is incomplete/expanded")
        timestamp = base.parse_utc(document.get("timestamp_utc"), "transition time")
        for input_id, item in evidence.items():
            resolution = resolutions.get(input_id)
            if (resolution is None or item.get("resolution_id") != resolution.resolution_id
                    or item.get("sha256") != resolution.sha256
                    or resolution.recorded_at_utc > timestamp):
                raise JournalError("transition resolution lineage/time drifted")
        authorizations = {item["input_id"]: item
                          for item in document.get("authorizations", [])}
        if set(authorizations) != set(edge["authorization_input_ids"]):
            raise JournalError("transition authorization set is incomplete/expanded")
        for input_id, item in authorizations.items():
            resolution = resolutions[input_id]
            summary = resolution.document.get("authorization")
            if (not isinstance(summary, dict)
                    or item.get("resolution_id") != resolution.resolution_id
                    or item.get("authorization_id") != summary.get("authorization_id")
                    or item.get("authority_scope") != summary.get("authority_scope")):
                raise JournalError("transition authorization lineage drifted")
            issued = base.parse_utc(summary["issued_at_utc"], "authorization issue")
            expires = base.parse_utc(summary["expires_at_utc"], "authorization expiry")
            if not issued <= timestamp < expires:
                raise JournalError("transition authority is future/expired")
        current = str(document["to_state"]); previous_sha = digest
        result.append(StateTransition(
            transition_id, sequence, str(document["from_state"]), current,
            timestamp, path, digest, document,
        ))
    return current, result


def validate_operational_journal(
    *, repository_root: pathlib.Path, evidence_root: pathlib.Path,
    latest_journal: pathlib.Path, journal_directory: pathlib.Path | None = None,
    pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None, as_of_utc: str | None = None,
    allow_synthetic_test_evidence: bool = False,
) -> OperationalJournalValidation:
    repository = repository_root.resolve(); evidence = evidence_root.resolve()
    lineage, latest = _lineage(
        evidence_root=evidence, latest_path=latest_journal,
        schema_path=repository / SCHEMA_PATHS["journal_schema_sha256"],
        journal_directory=journal_directory,
    )
    graph, catalog, graph_sha, catalog_sha, versions = base.validate_graph_catalog(
        repository, latest
    )
    genesis_record = {
        "journal_id": latest["journal_id"],
        "protocol_version": latest["protocol_version"],
        "initial_state": graph["initial_state"], "graph_sha256": graph_sha,
        "catalog_sha256": catalog_sha, "version_hashes": versions,
        "authority_scope": "NO_EXECUTION_AUTHORITY",
    }
    genesis_sha = base.sha256_bytes(base.canonical_json_bytes(genesis_record))
    if (latest["genesis"].get("genesis_record") != genesis_record
            or latest["genesis"].get("genesis_sha256") != genesis_sha
            or latest["journal_sequence_number"] != len(
                latest["resolution_records"]) + len(latest["transition_records"])):
        raise JournalError("operational journal genesis/append count drifted")
    resolutions = _resolutions(
        repository_root=repository, evidence_root=evidence,
        references=latest["resolution_records"], graph_sha256=graph_sha,
        catalog_sha256=catalog_sha, versions=versions, catalog=catalog,
        genesis_sha256=genesis_sha, pilot_archive=pilot_archive,
        pilot_sidecar=pilot_sidecar, allow_synthetic=allow_synthetic_test_evidence,
    )
    current, transitions = _transitions(
        repository_root=repository, evidence_root=evidence,
        references=latest["transition_records"], graph=graph,
        graph_sha256=graph_sha, catalog_sha256=catalog_sha, versions=versions,
        genesis_sha256=genesis_sha, resolutions=resolutions,
    )
    ids = tuple(item["input_id"] for item in catalog["items"])
    resolved = tuple(item for item in ids if item in resolutions)
    missing = tuple(item for item in ids if item not in resolutions)
    pilot_ready = current == "READY_FOR_STAGE17_PHASE_AUTHORIZATION" and not missing
    if pilot_ready:
        authorization = resolutions["S17-EXT-010"].authorization_document
        if as_of_utc is None or not isinstance(authorization, dict):
            pilot_ready = False
        else:
            sampled = base.parse_utc(as_of_utc, "pilot readiness time")
            pilot_ready = (
                base.parse_utc(authorization["issued_at_utc"], "pilot issue")
                <= sampled <
                base.parse_utc(authorization["expires_at_utc"], "pilot expiry")
            )
    return OperationalJournalValidation(
        current, pilot_ready, resolved, missing, len(resolutions), len(transitions),
        lineage[-1][2], False,
        "NOT_ACCESSED" if not resolutions else "EVIDENCE_DEPENDENT",
        resolutions, tuple(transitions),
    )


def checked_in_status(root: pathlib.Path) -> predecessor.OperationalJournalValidation:
    return predecessor.checked_in_status(root)
