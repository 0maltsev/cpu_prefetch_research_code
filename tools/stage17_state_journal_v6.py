#!/usr/bin/env python3
"""Current Stage 17 journal runtime for complete semantic-admission policy v9."""

from __future__ import annotations

import pathlib
from typing import Any, Callable

import stage17_state_journal as journal_v1
from stage17_pilot_candidate_artifact import (
    ArtifactError as PilotArtifactError,
    verify_pilot_candidate_artifact,
)
from stage17_semantic_verifier_v3 import SemanticAdmissionError
from stage17_semantic_verifier_v9 import (
    evaluate_s17_ext_001_action_readiness_v9,
    verify_operational_manifest_semantics,
    verify_policy_v9,
    verify_s17_ext_001_semantics_v9,
)


ADR_0105_PATH = journal_v1.ADR_0105_PATH
FIXED_PREFLIGHT_OBSERVATION_IDS = journal_v1.FIXED_PREFLIGHT_OBSERVATION_IDS
GENESIS_PATH = journal_v1.GENESIS_PATH
LEGACY_TEMPLATE_PATHS = journal_v1.LEGACY_TEMPLATE_PATHS
PINNED_HOST_KEY_SCHEMA_PATH = journal_v1.PINNED_HOST_KEY_SCHEMA_PATH
READ_ONLY_PERMISSION_MATRIX = journal_v1.READ_ONLY_PERMISSION_MATRIX
SCHEMA_PATHS = journal_v1.SCHEMA_PATHS
STATE_ORDER = journal_v1.STATE_ORDER
SEMANTIC_POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v9.json"
)
SEMANTIC_POLICY_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v9.schema.json"
)
SEMANTIC_ENVELOPE_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-envelope-v9.schema.json"
)
S17_EXT_001_AUTHORIZATION_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-read-only-preflight-authorization-v8.schema.json"
)
S17_EXT_001_CONTRACT_SCHEMA_PATH = pathlib.PurePosixPath(
    "config/schemas/stage17-read-only-preflight-supporting-contract-v8.schema.json"
)

ExternalInputResolution = journal_v1.ExternalInputResolution
JournalError = journal_v1.JournalError
JournalValidation = journal_v1.JournalValidation
canonical_json_bytes = journal_v1.canonical_json_bytes
sha256_bytes = journal_v1.sha256_bytes
sha256_file = journal_v1.sha256_file
load_json = journal_v1.load_json
parse_utc = journal_v1.parse_utc
repository_file = journal_v1.repository_file
validate_schema = journal_v1.validate_schema
version_hashes = journal_v1.version_hashes
verify_file_binding = journal_v1.verify_file_binding
verify_external_file_binding = journal_v1.verify_external_file_binding
record_from_ref = journal_v1.record_from_ref
validate_graph_catalog = journal_v1.validate_graph_catalog
validate_journal_lineage = journal_v1.validate_journal_lineage
validate_transitions = journal_v1.validate_transitions

SemanticVerifier = Callable[..., dict[str, Any] | None]


def load_semantic_policy(
    root: pathlib.Path,
    *,
    graph_sha256: str,
    catalog_sha256: str,
    genesis_sha256: str,
) -> tuple[dict[str, Any], pathlib.Path, str]:
    policy_path = repository_file(root, SEMANTIC_POLICY_PATH.as_posix())
    policy = load_json(policy_path)
    validate_schema(policy, root / SEMANTIC_POLICY_SCHEMA_PATH, "semantic-admission policy v9")
    try:
        verify_policy_v9(
            root=root,
            policy=policy,
            graph_sha256=graph_sha256,
            catalog_sha256=catalog_sha256,
            genesis_file_sha256=sha256_file(root / GENESIS_PATH),
            genesis_record_sha256=genesis_sha256,
            resolution_schema_sha256=sha256_file(
                root / SCHEMA_PATHS["resolution_schema_sha256"]
            ),
        )
    except SemanticAdmissionError as exception:
        raise JournalError(str(exception)) from exception
    return policy, policy_path, sha256_file(policy_path)


def semantic_policy_entry(policy: dict[str, Any], input_id: str) -> dict[str, Any]:
    matches = [entry for entry in policy.get("entries", []) if entry.get("input_id") == input_id]
    if len(matches) != 1:
        raise JournalError(f"SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED:{input_id}")
    entry = matches[0]
    if entry.get("status") != "IMPLEMENTED":
        raise JournalError(f"SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED:{input_id}")
    return entry


SEMANTIC_VERIFIERS: dict[tuple[str, str, str], SemanticVerifier] = {
    ("S17-EXT-001", "STAGE17-S17-EXT-001-SEMANTIC-VERIFIER", "9"):
        verify_s17_ext_001_semantics_v9,
    ("S17-EXT-006", "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER", "1"):
        journal_v1.verify_s17_ext_006_semantics,
}


def _verify_synthetic_ext006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
) -> None:
    """Test-only exact-byte route through the production artifact verifier."""

    if pilot_archive is None or pilot_sidecar is None or len(receipt_documents) != 1:
        raise JournalError("synthetic S17-EXT-006 exact bytes are absent")
    receipt = receipt_documents[0]
    if (
        receipt.get("verifier_id") != "STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"
        or receipt.get("verifier_version") != "1"
        or pathlib.Path(str(receipt.get("artifact_locator"))) != pilot_archive
        or len(receipt.get("sidecars", [])) != 1
        or pathlib.Path(receipt["sidecars"][0]["locator"]) != pilot_sidecar
    ):
        raise JournalError("synthetic S17-EXT-006 receipt/verifier binding drifted")
    contract_path = repository_file(root, receipt.get("contract_path"))
    contract = load_json(contract_path)
    # The immutable production schema fixes the contract ID.  Test authority
    # is carried only by the explicit caller gate and the synthetic resolution
    # record; weakening that schema for a synthetic ID would stop exercising
    # the real exact-byte contract.
    if contract.get("contract_id") != "STAGE17-PILOT-CANDIDATE-EXTERNAL-CONTRACT-v1":
        raise JournalError("synthetic S17-EXT-006 does not use the production contract identity")
    try:
        result = verify_pilot_candidate_artifact(
            repository_root=root, contract_path=contract_path,
            archive=pilot_archive, sidecar=pilot_sidecar,
        )
    except PilotArtifactError as exception:
        raise JournalError(f"synthetic S17-EXT-006 exact-byte verification failed: {exception}") from exception
    if (
        (receipt["artifact_size_bytes"], receipt["artifact_sha256"])
        != (result.artifact_size_bytes, result.artifact_sha256)
        or (receipt["sidecars"][0]["size_bytes"], receipt["sidecars"][0]["sha256"])
        != (result.sidecar_size_bytes, result.sidecar_sha256)
    ):
        raise JournalError("synthetic S17-EXT-006 receipt does not match verified bytes")


def validate_resolutions(
    *, root: pathlib.Path, references: list[dict[str, Any]], graph_sha256: str,
    catalog_sha256: str, expected_versions: dict[str, str], catalog: dict[str, Any],
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
    genesis_sha256: str, allow_synthetic: bool,
) -> dict[str, ExternalInputResolution]:
    catalog_items = {item["input_id"]: item for item in catalog["items"]}
    by_input: dict[str, ExternalInputResolution] = {}
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    resolution_schema = root / SCHEMA_PATHS["resolution_schema_sha256"]
    receipt_schema = root / SCHEMA_PATHS["custody_receipt_schema_sha256"]
    policy, policy_path, policy_sha256 = load_semantic_policy(
        root, graph_sha256=graph_sha256, catalog_sha256=catalog_sha256,
        genesis_sha256=genesis_sha256,
    )
    for expected_sequence, reference in enumerate(references, start=1):
        path, document, digest = record_from_ref(root, reference, "external-input resolution")
        validate_schema(document, resolution_schema, "external-input resolution")
        if document.get("sequence_number") != expected_sequence:
            raise JournalError("resolution sequence is missing, duplicated, or replayed")
        resolution_id, input_id = str(document["resolution_id"]), str(document["input_id"])
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
        repository_documents: list[tuple[pathlib.Path, dict[str, Any]]] = []
        receipt_documents: list[dict[str, Any]] = []
        for evidence in document.get("evidence", []):
            kind = str(evidence.get("kind"))
            evidence_kinds.add(kind)
            if kind == "REPOSITORY_FILE":
                evidence_path = verify_file_binding(
                    root, path_text=evidence.get("path"),
                    expected_size=evidence.get("size_bytes"),
                    expected_sha256=evidence.get("sha256"), label="repository evidence",
                )
                repository_documents.append((evidence_path, load_json(evidence_path)))
            elif kind == "EXTERNAL_CUSTODY_RECEIPT":
                receipt_path = verify_file_binding(
                    root, path_text=evidence.get("receipt_path"),
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
                        locator=sidecar.get("locator"), expected_size=sidecar.get("size_bytes"),
                        expected_sha256=sidecar.get("sha256"), label="external custody sidecar",
                    )
                contract_path = verify_file_binding(
                    root, path_text=receipt.get("contract_path"),
                    expected_size=repository_file(root, receipt.get("contract_path")).stat().st_size,
                    expected_sha256=receipt.get("contract_sha256"), label="external artifact contract",
                )
                load_json(contract_path)
                if parse_utc(receipt.get("verified_at_utc"), "receipt time") > recorded_at:
                    raise JournalError("receipt postdates its resolution")
                receipt_documents.append(receipt)
        evidence_policy = catalog_items[input_id]["evidence_policy"]
        if evidence_policy == "REPOSITORY_FILE" and evidence_kinds != {"REPOSITORY_FILE"}:
            raise JournalError(f"{input_id} evidence policy mismatch")
        if evidence_policy == "EXTERNAL_CUSTODY_RECEIPT" and "EXTERNAL_CUSTODY_RECEIPT" not in evidence_kinds:
            raise JournalError(f"{input_id} requires an external custody receipt")
        if evidence_policy == "MIXED" and evidence_kinds != {"REPOSITORY_FILE", "EXTERNAL_CUSTODY_RECEIPT"}:
            raise JournalError(f"{input_id} requires mixed repository/external evidence")
        authorization_summary = document.get("authorization")
        if catalog_items[input_id]["authorization_required"]:
            if not isinstance(authorization_summary, dict):
                raise JournalError(f"{input_id} requires authorization evidence")
        elif authorization_summary is not None:
            raise JournalError(f"{input_id} unexpectedly carries authorization")
        entry = semantic_policy_entry(policy, input_id)
        key = (input_id, str(entry.get("verifier_id")), str(entry.get("verifier_version")))
        try:
            verifier = SEMANTIC_VERIFIERS.get(key)
            if verifier is not None:
                if input_id == "S17-EXT-006" and allow_synthetic:
                    _verify_synthetic_ext006(
                        root=root, receipt_documents=receipt_documents,
                        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
                    )
                    semantic_result = {"authorization": None, "context": {
                        "manifest_id": "SYNTHETIC-EXT006-EXACT-BYTES",
                        "manifest_sha256": receipt_documents[0]["artifact_sha256"],
                        "synthetic_test_only": True,
                    }}
                else:
                    semantic_result = verifier(
                        root=root, resolution=document, repository_documents=repository_documents,
                        receipt_documents=receipt_documents, policy=policy, policy_path=policy_path,
                        policy_sha256=policy_sha256, policy_entry=entry, graph_sha256=graph_sha256,
                        catalog_sha256=catalog_sha256, genesis_sha256=genesis_sha256,
                        resolution_schema_sha256=expected_versions["resolution_schema_sha256"],
                        catalog=catalog, pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
                    )
            else:
                if input_id not in {"S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-005", "S17-EXT-007", "S17-EXT-008", "S17-EXT-009", "S17-EXT-010"}:
                    raise JournalError(f"SEMANTIC_VERIFIER_NOT_IMPLEMENTED_FAIL_CLOSED:{input_id}")
                semantic_result = verify_operational_manifest_semantics(
                    root=root, input_id=input_id,
                    repository_documents=repository_documents,
                    receipt_documents=receipt_documents,
                    admitted_resolutions=by_input, allow_synthetic=allow_synthetic,
                )
        except SemanticAdmissionError as exception:
            raise JournalError(str(exception)) from exception
        authorization_document: dict[str, Any] | None = None
        semantic_context: dict[str, Any] | None = None
        if isinstance(semantic_result, dict) and "authorization" in semantic_result:
            authorization_document = semantic_result.get("authorization")
            semantic_context = semantic_result.get("context")
        elif isinstance(semantic_result, dict):
            authorization_document = semantic_result
        if catalog_items[input_id]["authorization_required"]:
            if not isinstance(authorization_document, dict):
                raise JournalError(f"{input_id} semantic verifier returned no authorization")
            journal_v1.validate_authorization_permissions(authorization_document, input_id)
            expected_summary = {
                field: authorization_document[field]
                for field in (
                    "authorization_id", "issued_at_utc", "expires_at_utc",
                    "authority_scope",
                )
            }
            if not isinstance(authorization_summary, dict) or any(
                authorization_summary.get(field) != value
                for field, value in expected_summary.items()
            ):
                raise JournalError(f"{input_id} authorization summary drifted")
            if input_id in {"S17-EXT-005", "S17-EXT-010"}:
                if not isinstance(semantic_context, dict):
                    raise JournalError(f"{input_id} authorization context is absent")
                authorization_path = pathlib.Path(
                    str(semantic_context.get("authorization_path", ""))
                )
                try:
                    expected_evidence_path = authorization_path.relative_to(root).as_posix()
                except ValueError as exception:
                    raise JournalError(
                        f"{input_id} authorization is outside the repository evidence root"
                    ) from exception
                if authorization_summary.get("evidence_path") != expected_evidence_path:
                    raise JournalError(f"{input_id} authorization evidence path drifted")
        by_input[input_id] = ExternalInputResolution(
            resolution_id=resolution_id, sequence_number=expected_sequence, input_id=input_id,
            actor=str(document["actor"]), recorded_at_utc=recorded_at, path=path, sha256=digest,
            document=document, authorization_document=authorization_document,
            semantic_context=semantic_context,
        )
    return by_input


def validate_journal(
    *, repository_root: pathlib.Path, latest_journal: pathlib.Path,
    journal_directory: pathlib.Path | None = None,
    pilot_archive: pathlib.Path | None = None, pilot_sidecar: pathlib.Path | None = None,
    as_of_utc: str | None = None, requested_action_input_id: str | None = None,
    runtime_identity_paths: dict[str, str] | None = None,
    allow_synthetic_test_evidence: bool = False,
) -> JournalValidation:
    root = repository_root.resolve()
    journal_schema = root / SCHEMA_PATHS["journal_schema_sha256"]
    lineage, latest = validate_journal_lineage(root, latest_journal, journal_schema, journal_directory)
    graph, catalog, graph_sha256, catalog_sha256, expected_versions = validate_graph_catalog(root, latest)
    genesis = latest["genesis"]
    expected_genesis_record = {
        "journal_id": latest["journal_id"], "protocol_version": latest["protocol_version"],
        "initial_state": graph["initial_state"], "graph_sha256": graph_sha256,
        "catalog_sha256": catalog_sha256, "version_hashes": expected_versions,
        "authority_scope": "NO_EXECUTION_AUTHORITY",
    }
    if genesis.get("genesis_record") != expected_genesis_record:
        raise JournalError("genesis record drifted")
    genesis_sha256 = sha256_bytes(canonical_json_bytes(expected_genesis_record))
    if genesis.get("genesis_sha256") != genesis_sha256:
        raise JournalError("genesis SHA-256 mismatch")
    if lineage[-1][1].get("journal_sequence_number") != len(latest.get("resolution_records", [])) + len(latest.get("transition_records", [])):
        raise JournalError("latest journal append count mismatch")
    resolutions = validate_resolutions(
        root=root, references=latest.get("resolution_records", []), graph_sha256=graph_sha256,
        catalog_sha256=catalog_sha256, expected_versions=expected_versions, catalog=catalog,
        pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar, genesis_sha256=genesis_sha256,
        allow_synthetic=allow_synthetic_test_evidence,
    )
    current_state, transitions = validate_transitions(
        root=root, references=latest.get("transition_records", []), graph=graph,
        graph_sha256=graph_sha256, catalog_sha256=catalog_sha256,
        expected_versions=expected_versions, genesis_sha256=genesis_sha256,
        resolutions=resolutions,
    )
    expected_ids = tuple(item["input_id"] for item in catalog["items"])
    resolved_ids = tuple(item for item in expected_ids if item in resolutions)
    missing_ids = tuple(item for item in expected_ids if item not in resolutions)
    action_ready = False
    action_context: dict[str, Any] | None = None
    if requested_action_input_id is not None:
        if requested_action_input_id not in {"S17-EXT-001", "S17-EXT-010"}:
            raise JournalError("requested action has no registered authorization boundary")
        if as_of_utc is None:
            raise JournalError("requested action requires an explicit UTC evaluation time")
        action_resolution = resolutions.get(requested_action_input_id)
        if action_resolution is None:
            raise JournalError(f"requested action authorization is unresolved: {requested_action_input_id}")
        action_authorization = action_resolution.authorization_document
        if not isinstance(action_authorization, dict):
            raise JournalError("requested action has no verified authorization")
        evaluation_time = parse_utc(as_of_utc, "action-readiness evaluation time")
        issued = parse_utc(action_authorization.get("issued_at_utc"), "action authorization issue")
        expires = parse_utc(action_authorization.get("expires_at_utc"), "action authorization expiry")
        if requested_action_input_id == "S17-EXT-001":
            if action_resolution.semantic_context is None:
                raise JournalError("S17-EXT-001 action context is absent")
            action_context = evaluate_s17_ext_001_action_readiness_v9(
                root=root, current_state=current_state,
                transition_documents=[item.document for item in transitions],
                transition_ids_and_hashes=[(item.transition_id, item.sha256) for item in transitions],
                resolution_id=action_resolution.resolution_id,
                resolution_sha256=action_resolution.sha256,
                authorization=action_authorization,
                semantic_context=action_resolution.semantic_context, as_of_utc=as_of_utc,
                runtime_identity_paths=runtime_identity_paths,
            )
            action_ready = action_context is not None
        elif issued <= evaluation_time < expires:
            action_ready = True
    pilot_ready = current_state == STATE_ORDER[-1] and not missing_ids
    if pilot_ready:
        if as_of_utc is None:
            pilot_ready = False
        else:
            evaluation_time = parse_utc(as_of_utc, "pilot readiness evaluation time")
            pilot_authorization = resolutions["S17-EXT-010"].authorization_document
            if not isinstance(pilot_authorization, dict):
                raise JournalError("pilot-ready state has no S17-EXT-010 authorization")
            issued = parse_utc(pilot_authorization.get("issued_at_utc"), "pilot authorization issue")
            expires = parse_utc(pilot_authorization.get("expires_at_utc"), "pilot authorization expiry")
            if not issued <= evaluation_time < expires:
                raise JournalError("pilot authorization is expired or not yet valid")
    return JournalValidation(
        current_state=current_state, pilot_ready=pilot_ready, resolved_input_ids=resolved_ids,
        missing_input_ids=missing_ids, resolution_count=len(resolutions),
        transition_count=len(transitions), latest_journal_sha256=lineage[-1][2],
        requested_action_input_id=requested_action_input_id,
        action_ready=action_ready, action_context=action_context,
    )
