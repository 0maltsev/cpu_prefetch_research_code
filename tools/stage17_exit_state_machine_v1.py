#!/usr/bin/env python3
"""Append-only Stage 17 exit and Phase 18 access-chronology validator."""

from __future__ import annotations

import hashlib
import json
import pathlib
import stat
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator


EXIT_STATES = (
    "READY_FOR_STAGE17_PHASE_AUTHORIZATION", "PILOT_AUTHORIZED",
    "PILOT_EXECUTED", "PILOT_EVIDENCE_SEALED", "STAGE17_COMPLETE",
    "PHASE18_HANDOFF_PREPARED",
)
PHASE18_STATES = (
    "PLANNED", "COLLECTED_SEALED", "TRAINING_OPEN", "SELECTION_FROZEN",
    "VALIDATION_UNSEALED", "H3_EVALUATED", "H1H2_RELEASED", "ARCHIVED",
)
EXIT_GENESIS_SHA256 = hashlib.sha256(b"STAGE17-EXIT-GENESIS-v1\n").hexdigest()
PHASE18_GENESIS_SHA256 = hashlib.sha256(b"PHASE18-ACCESS-GENESIS-v1\n").hexdigest()
TYPE_SCHEMAS = {
    "PILOT_ATTEMPT": "stage17-pilot-attempt-v1.schema.json",
    "PILOT_RECEIPT": "stage17-pilot-receipt-v1.schema.json",
    "PILOT_FAILURE": "stage17-pilot-failure-v1.schema.json",
    "PILOT_COMPLETION": "stage17-pilot-completion-v1.schema.json",
    "SEALED_PILOT_ARTIFACT_MANIFEST":
        "stage17-sealed-pilot-artifact-manifest-v1.schema.json",
    "TREATMENT_BLIND_FREEZE": "stage17-treatment-blind-freeze-v1.schema.json",
    "STAGE17_COMPLETION_STATEMENT":
        "stage17-completion-statement-v1.schema.json",
}


class ExitStateError(ValueError):
    pass


@dataclass(frozen=True)
class ExitValidation:
    current_state: str
    record_count: int
    synthetic_test_only: bool
    stage17_complete: bool
    phase18_handoff_prepared: bool


def canonical(document: Any) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ExitStateError(f"record is not a nonsymlink regular file: {path}")
    payload = path.read_bytes()
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exception:
        raise ExitStateError(f"record is malformed JSON: {path}") from exception
    if not isinstance(document, dict):
        raise ExitStateError("record JSON root is not an object")
    return document, payload


def _schema(root: pathlib.Path, name: str) -> Draft202012Validator:
    document, _ = _load(root / "config/schemas" / name)
    Draft202012Validator.check_schema(document)
    return Draft202012Validator(document)


def _validate(validator: Draft202012Validator, document: dict[str, Any], label: str) -> None:
    errors = sorted(validator.iter_errors(document), key=lambda item: tuple(item.path))
    if errors:
        path = "/".join(str(item) for item in errors[0].path) or "<root>"
        raise ExitStateError(f"{label} schema error at {path}: {errors[0].message}")


def _bindings(record: dict[str, Any]) -> None:
    seen: set[str] = set()
    for binding in record["source_bindings"]:
        if binding["artifact_id"] in seen:
            raise ExitStateError("duplicate source artifact ID")
        seen.add(binding["artifact_id"])
        path = pathlib.Path(binding["path"])
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ExitStateError("exit source is not a nonsymlink regular file")
        document, payload = _load(path) if path.suffix == ".json" else ({}, path.read_bytes())
        del document
        if len(payload) != binding["size_bytes"] or sha(payload) != binding["sha256"]:
            raise ExitStateError("exit source binding mismatch")


def _semantic_record(root: pathlib.Path, record: dict[str, Any]) -> None:
    kind, payload = record["record_type"], record["payload"]
    if kind in TYPE_SCHEMAS:
        _validate(_schema(root, TYPE_SCHEMAS[kind]), payload, f"{kind} payload")
    if kind == "PILOT_ATTEMPT":
        if payload["authorized_by_ext010"] is not True:
            raise ExitStateError("pilot attempt semantics drifted")
    elif kind == "PILOT_RECEIPT":
        if payload.get("valid_join") is not True or payload.get("partial") is not False:
            raise ExitStateError("pilot receipt semantics failed")
    elif kind == "PILOT_FAILURE":
        if not payload.get("failure_category") or payload.get("retry_allowed") is not False:
            raise ExitStateError("pilot failure semantics drifted")
    elif kind == "PILOT_COMPLETION":
        if payload.get("completed") is not True or payload.get("all_artifacts_immutable") is not True:
            raise ExitStateError("pilot completion is incomplete")
    elif kind == "SEALED_PILOT_ARTIFACT_MANIFEST":
        if payload.get("sealed") is not True or payload.get("checksums_verified") is not True or not payload.get("artifact_bindings"):
            raise ExitStateError("pilot seal is incomplete")
    elif kind == "TREATMENT_BLIND_FREEZE":
        if payload.get("treatment_labels_blinded") is not True or payload.get("outcome_accessed") is not False or payload.get("freeze_immutable") is not True:
            raise ExitStateError("treatment-blind freeze semantics drifted")
    elif kind == "ROLE_SEPARATION_DECLARATION":
        if payload != {"stage17_single_owner_collapse": True, "distinct_auditor": False, "independent_review": False, "phase18_separate_authority_required": True, "phase18_chronology_strict": True}:
            raise ExitStateError("role-separation declaration drifted")
    elif kind == "STAGE17_COMPLETION_STATEMENT":
        if payload.get("all_ten_inputs_admitted") is not True or payload.get("pilot_evidence_sealed") is not True or payload.get("phase18_authority") is not False:
            raise ExitStateError("Stage 17 completion statement is incomplete")
    elif kind == "PHASE18_READINESS_REPORT":
        if payload.get("state") != "READY_FOR_SEPARATE_PHASE18_AUTHORIZATION" or payload.get("blockers") != [] or payload.get("phase18_authority") is not False:
            raise ExitStateError("Phase 18 readiness report is not a no-authority handoff")
    elif kind == "PHASE18_AUTHORIZATION_DRAFT":
        if payload.get("issued") is not False or payload.get("authorization_id") is not None or payload.get("stage17_authority_reuse_allowed") is not False:
            raise ExitStateError("Phase 18 authorization draft is not unissued")


def validate_exit_journal(
    *, repository_root: pathlib.Path, journal_path: pathlib.Path,
    allow_synthetic: bool = False,
) -> ExitValidation:
    root = repository_root.resolve()
    journal, _ = _load(journal_path)
    _validate(_schema(root, "stage17-pilot-exit-journal-v1.schema.json"), journal, "exit journal")
    if journal["synthetic_test_only"] and not allow_synthetic:
        raise ExitStateError("synthetic exit journal is forbidden in production admission")
    validator = _schema(root, "stage17-pilot-exit-record-v1.schema.json")
    records: list[tuple[dict[str, Any], str]] = []
    previous = EXIT_GENESIS_SHA256
    for sequence, reference in enumerate(journal["record_references"], start=1):
        path = pathlib.Path(reference["path"])
        document, payload = _load(path)
        digest = sha(payload)
        if len(payload) != reference["size_bytes"] or digest != reference["sha256"]:
            raise ExitStateError("exit record reference mismatch")
        _validate(validator, document, "exit record")
        if document["sequence_number"] != sequence or document["previous_record_sha256"] != previous:
            raise ExitStateError("exit journal sequence/hash chain forked or replayed")
        if document["synthetic_test_only"] != journal["synthetic_test_only"]:
            raise ExitStateError("exit journal synthetic classification drifted")
        _bindings(document)
        _semantic_record(root, document)
        records.append((document, digest))
        previous = digest

    current = EXIT_STATES[0]
    present_types: list[str] = []
    typed_records: dict[str, list[tuple[dict[str, Any], str]]] = {}
    failure_seen = False
    for document, record_digest in records:
        kind = document["record_type"]
        if kind != "STATE_TRANSITION":
            present_types.append(kind)
            typed_records.setdefault(kind, []).append((document, record_digest))
            failure_seen = failure_seen or kind == "PILOT_FAILURE"
            continue
        payload = document["payload"]
        expected_to = EXIT_STATES[EXIT_STATES.index(current) + 1]
        if payload.get("from_state") != current or payload.get("to_state") != expected_to:
            raise ExitStateError("Stage 17 exit transition skipped, reversed, or replayed")
        required = {
            "PILOT_AUTHORIZED": ("S17_EXT_010_ADMITTED",),
            "PILOT_EXECUTED": ("PILOT_ATTEMPT", "PILOT_RECEIPT", "PILOT_COMPLETION"),
            "PILOT_EVIDENCE_SEALED": ("SEALED_PILOT_ARTIFACT_MANIFEST", "TREATMENT_BLIND_FREEZE"),
            "STAGE17_COMPLETE": ("ROLE_SEPARATION_DECLARATION", "STAGE17_COMPLETION_STATEMENT"),
            "PHASE18_HANDOFF_PREPARED": ("PHASE18_READINESS_REPORT", "PHASE18_AUTHORIZATION_DRAFT"),
        }[expected_to]
        declared = tuple(payload.get("evidence_record_types", []))
        available = set(present_types)
        if expected_to == "PILOT_AUTHORIZED":
            if payload.get("admitted_ext010_sha256") is None:
                raise ExitStateError("pilot authorization does not bind admitted S17-EXT-010")
        elif declared != required or not set(required).issubset(available):
            raise ExitStateError("exit transition evidence set is incomplete or reordered")
        if expected_to == "PILOT_EXECUTED":
            attempts = typed_records.get("PILOT_ATTEMPT", [])
            receipts = typed_records.get("PILOT_RECEIPT", [])
            completions = typed_records.get("PILOT_COMPLETION", [])
            if len(attempts) != 1 or len(completions) != 1 or not receipts:
                raise ExitStateError("pilot attempt/receipt/completion family is incomplete")
            completion = completions[0][0]["payload"]
            attempt = attempts[0][0]["payload"]
            receipt_payloads = [item[0]["payload"] for item in receipts]
            if (
                completion.get("run_ids") != attempt.get("run_ids")
                or completion.get("run_ids") != [item["run_id"] for item in receipt_payloads]
                or completion.get("receipt_sha256s") != [item[1] for item in receipts]
            ):
                raise ExitStateError("pilot completion does not bind the ordered receipts")
        if failure_seen and expected_to in {"PILOT_EXECUTED", "PILOT_EVIDENCE_SEALED", "STAGE17_COMPLETE", "PHASE18_HANDOFF_PREPARED"}:
            raise ExitStateError("failed pilot cannot advance the success exit graph")
        if payload.get("authority_scope") != "STAGE17_EXIT_STATE_ADVANCE_ONLY" or payload.get("phase18_authority") is not False:
            raise ExitStateError("exit transition authority expanded")
        current = expected_to
    if journal["current_state_claim"] != current:
        raise ExitStateError("exit journal current-state claim mismatch")
    return ExitValidation(
        current_state=current, record_count=len(records),
        synthetic_test_only=journal["synthetic_test_only"],
        stage17_complete=EXIT_STATES.index(current) >= EXIT_STATES.index("STAGE17_COMPLETE"),
        phase18_handoff_prepared=current == "PHASE18_HANDOFF_PREPARED",
    )


def validate_phase18_access_journal(
    *, repository_root: pathlib.Path, journal_path: pathlib.Path,
    allow_synthetic: bool = False,
) -> str:
    root = repository_root.resolve()
    document, _ = _load(journal_path)
    _validate(_schema(root, "phase18-access-journal-v1.schema.json"), document, "Phase 18 access journal")
    if document["synthetic_test_only"] and not allow_synthetic:
        raise ExitStateError("synthetic Phase 18 journal is forbidden in production")
    state, previous = PHASE18_STATES[0], PHASE18_GENESIS_SHA256
    seen_hashes: set[str] = set()
    for sequence, transition in enumerate(document["transitions"], start=1):
        if transition["sequence_number"] != sequence or transition["previous_transition_sha256"] != previous:
            raise ExitStateError("Phase 18 transition chain forked or replayed")
        expected = PHASE18_STATES[PHASE18_STATES.index(state) + 1]
        if (transition["from_state"], transition["to_state"]) != (state, expected):
            raise ExitStateError("Phase 18 chronology violation")
        if transition["stage17_authority_used"] is not False or transition["authority_scope"] != "PHASE18_ACCESS_TRANSITION_ONLY":
            raise ExitStateError("Stage 17 authority was reused in Phase 18")
        digest = sha(canonical(transition))
        if digest in seen_hashes:
            raise ExitStateError("Phase 18 transition replay")
        seen_hashes.add(digest)
        previous, state = digest, expected
    if document["current_state_claim"] != state:
        raise ExitStateError("Phase 18 current-state claim mismatch")
    return state
