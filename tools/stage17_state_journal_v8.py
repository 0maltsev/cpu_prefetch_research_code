#!/usr/bin/env python3
"""Current Stage 17 operational journal runtime for semantic policy v11."""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys
from typing import Any

import stage17_semantic_verifier_v11 as semantic
import stage17_state_journal as base
import stage17_state_journal_v7 as predecessor


SEMANTIC_POLICY_PATH = semantic.POLICY_PATH
SCHEMA_PATHS = base.SCHEMA_PATHS
STATE_ORDER = base.STATE_ORDER
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


def _policy(root: pathlib.Path, graph_sha256: str, catalog_sha256: str,
            genesis_sha256: str, resolution_schema_sha256: str) -> dict[str, Any]:
    path = base.repository_file(root, SEMANTIC_POLICY_PATH.as_posix())
    policy = base.load_json(path)
    try:
        semantic.verify_policy_v11(
            root=root, policy=policy, graph_sha256=graph_sha256,
            catalog_sha256=catalog_sha256,
            genesis_record_sha256=genesis_sha256,
            resolution_schema_sha256=resolution_schema_sha256,
        )
    except semantic.SemanticAdmissionError as exception:
        raise JournalError(str(exception)) from exception
    return policy


def validate_resolutions(
    *, root: pathlib.Path, references: list[dict[str, Any]], graph_sha256: str,
    catalog_sha256: str, expected_versions: dict[str, str],
    catalog: dict[str, Any], genesis_sha256: str,
    pilot_archive: pathlib.Path | None, pilot_sidecar: pathlib.Path | None,
    allow_synthetic: bool,
) -> dict[str, ExternalInputResolution]:
    policy = _policy(root, graph_sha256, catalog_sha256, genesis_sha256,
                     expected_versions["resolution_schema_sha256"])
    entries = {item["input_id"]: item for item in policy["entries"]}
    catalog_items = {item["input_id"]: item for item in catalog["items"]}
    result: dict[str, ExternalInputResolution] = {}
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    schema = root / SCHEMA_PATHS["resolution_schema_sha256"]
    for sequence, reference in enumerate(references, 1):
        path, document, digest = base.record_from_ref(
            root, reference, "external-input resolution"
        )
        base.validate_schema(document, schema, "external-input resolution")
        input_id = str(document["input_id"])
        resolution_id = str(document["resolution_id"])
        if (document.get("sequence_number") != sequence or input_id in result
                or resolution_id in seen_ids or digest in seen_hashes):
            raise JournalError("resolution sequence is missing, duplicated, or replayed")
        seen_ids.add(resolution_id); seen_hashes.add(digest)
        expected_entry = {
            "input_id": input_id, "status": "IMPLEMENTED",
            "verifier_id": semantic.VERIFIER_ID,
            "verifier_version": semantic.VERIFIER_VERSION,
        }
        if (input_id not in catalog_items or entries.get(input_id) != expected_entry):
            raise JournalError(f"semantic registry drifted: {input_id}")
        if (document.get("graph_sha256"), document.get("catalog_sha256"),
                document.get("version_hashes")) != (
                    graph_sha256, catalog_sha256, expected_versions
                ):
            raise JournalError("resolution graph/catalog/version binding drifted")
        recorded = base.parse_utc(document.get("recorded_at_utc"), "resolution time")
        kinds, repository_documents, receipt_documents = predecessor._receipt_documents(
            root, document.get("evidence", []), recorded
        )
        evidence_policy = catalog_items[input_id]["evidence_policy"]
        expected_kinds = {
            "REPOSITORY_FILE": {"REPOSITORY_FILE"},
            "EXTERNAL_CUSTODY_RECEIPT": {"EXTERNAL_CUSTODY_RECEIPT"},
            "MIXED": {"REPOSITORY_FILE", "EXTERNAL_CUSTODY_RECEIPT"},
        }[evidence_policy]
        if kinds != expected_kinds:
            raise JournalError(f"{input_id} evidence policy mismatch")
        summary = document.get("authorization")
        requires_authority = catalog_items[input_id]["authorization_required"]
        if requires_authority != isinstance(summary, dict):
            raise JournalError(f"{input_id} authorization presence mismatch")
        try:
            verified = semantic.verify_input(
                input_id=input_id, root=root, resolution=document,
                repository_documents=repository_documents,
                receipt_documents=receipt_documents, admitted_resolutions=result,
                allow_synthetic=allow_synthetic, policy=policy,
                graph_sha256=graph_sha256, catalog_sha256=catalog_sha256,
                genesis_sha256=genesis_sha256, catalog=catalog,
                resolution_schema_sha256=expected_versions[
                    "resolution_schema_sha256"
                ], pilot_archive=pilot_archive, pilot_sidecar=pilot_sidecar,
            )
        except semantic.SemanticAdmissionError as exception:
            raise JournalError(str(exception)) from exception
        authorization = verified.get("authorization")
        context = verified.get("context")
        if requires_authority:
            if not isinstance(authorization, dict):
                raise JournalError(f"{input_id} verifier returned no authority")
            expected_summary = {
                field: authorization[field]
                for field in (
                    "authorization_id", "issued_at_utc", "expires_at_utc",
                    "authority_scope",
                ) if field in authorization
            }
            if "authority_scope" not in expected_summary:
                expected_summary["authority_scope"] = {
                    "STAGE17-BLINDED-PILOT": "STAGE17_PILOT_PHASE_ONLY"
                }.get(authorization.get("action_id"), authorization.get("action_id"))
            if not isinstance(summary, dict) or any(
                summary.get(key) != value for key, value in expected_summary.items()
            ):
                raise JournalError(f"{input_id} authorization summary drifted")
        result[input_id] = ExternalInputResolution(
            resolution_id=resolution_id, sequence_number=sequence,
            input_id=input_id, actor=str(document["actor"]),
            recorded_at_utc=recorded, path=path, sha256=digest,
            document=document, authorization_document=authorization,
            semantic_context=context if isinstance(context, dict) else None,
        )
    return result


def validate_operational_journal(
    *, repository_root: pathlib.Path, latest_journal: pathlib.Path,
    journal_directory: pathlib.Path | None = None,
    pilot_archive: pathlib.Path | None = None,
    pilot_sidecar: pathlib.Path | None = None, as_of_utc: str | None = None,
    allow_synthetic_test_evidence: bool = False,
) -> OperationalJournalValidation:
    root = repository_root.resolve()
    lineage, latest = base.validate_journal_lineage(
        root, latest_journal, root / SCHEMA_PATHS["journal_schema_sha256"],
        journal_directory,
    )
    graph, catalog, graph_sha, catalog_sha, versions = base.validate_graph_catalog(
        root, latest
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
            or latest["genesis"].get("genesis_sha256") != genesis_sha):
        raise JournalError("genesis record/hash drifted")
    if latest["journal_sequence_number"] != (
        len(latest["resolution_records"]) + len(latest["transition_records"])
    ):
        raise JournalError("journal append count mismatch")
    resolutions = validate_resolutions(
        root=root, references=latest["resolution_records"],
        graph_sha256=graph_sha, catalog_sha256=catalog_sha,
        expected_versions=versions, catalog=catalog,
        genesis_sha256=genesis_sha, pilot_archive=pilot_archive,
        pilot_sidecar=pilot_sidecar, allow_synthetic=allow_synthetic_test_evidence,
    )
    current, transitions = base.validate_transitions(
        root=root, references=latest["transition_records"], graph=graph,
        graph_sha256=graph_sha, catalog_sha256=catalog_sha,
        expected_versions=versions, genesis_sha256=genesis_sha,
        resolutions=resolutions,
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
            sample = base.parse_utc(as_of_utc, "pilot readiness time")
            pilot_ready = (
                base.parse_utc(authorization["issued_at_utc"], "pilot issue")
                <= sample <
                base.parse_utc(authorization["expires_at_utc"], "pilot expiry")
            )
    return OperationalJournalValidation(
        current_state=current, pilot_ready=pilot_ready,
        resolved_input_ids=resolved, missing_input_ids=missing,
        resolution_count=len(resolutions), transition_count=len(transitions),
        latest_journal_sha256=lineage[-1][2], action_ready=False,
        stand_status="NOT_ACCESSED" if not resolutions else "EVIDENCE_DEPENDENT",
        resolutions=resolutions, transitions=tuple(transitions),
    )


def checked_in_status(root: pathlib.Path) -> OperationalJournalValidation:
    latest = root / "config/stage17/journal/stage17-state-journal-000000.json"
    return validate_operational_journal(
        repository_root=root, latest_journal=latest,
        journal_directory=latest.parent,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=pathlib.Path, required=True)
    parser.add_argument("--journal", type=pathlib.Path, required=True)
    parser.add_argument("--journal-directory", type=pathlib.Path, required=True)
    parser.add_argument("--pilot-archive", type=pathlib.Path)
    parser.add_argument("--pilot-sidecar", type=pathlib.Path)
    parser.add_argument("--as-of-utc")
    parser.add_argument("--print-status", action="store_true", required=True)
    arguments = parser.parse_args()
    try:
        result = validate_operational_journal(
            repository_root=arguments.repository_root,
            latest_journal=arguments.journal,
            journal_directory=arguments.journal_directory,
            pilot_archive=arguments.pilot_archive,
            pilot_sidecar=arguments.pilot_sidecar,
            as_of_utc=arguments.as_of_utc,
        )
    except BaseException as exception:
        print(f"stage17-state-journal-v8: FAIL: {exception}", file=sys.stderr)
        return 1
    print(json.dumps({
        "action_ready": result.action_ready, "current_state": result.current_state,
        "missing_inputs": list(result.missing_input_ids),
        "pilot_ready": result.pilot_ready,
        "resolution_count": result.resolution_count,
        "stand": result.stand_status,
        "transition_count": result.transition_count,
    }, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
