#!/usr/bin/env python3
"""Typed Stage 17 exit and independently authorized Phase 18 chronology."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib
import stat
import subprocess
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

import stage17_openssh_parent_snapshot_v1 as snapshot_broker


EXIT_STATES = (
    "READY_FOR_STAGE17_PHASE_AUTHORIZATION", "PILOT_AUTHORIZED",
    "PILOT_EXECUTED", "PILOT_EVIDENCE_SEALED", "STAGE17_COMPLETE",
    "PHASE18_HANDOFF_PREPARED",
)
PHASE18_STATES = (
    "PLANNED", "COLLECTED_SEALED", "TRAINING_OPEN", "SELECTION_FROZEN",
    "VALIDATION_UNSEALED", "H3_EVALUATED", "H1H2_RELEASED", "ARCHIVED",
)
EXIT_GENESIS_SHA256 = hashlib.sha256(b"STAGE17-EXIT-GENESIS-v2\n").hexdigest()
PHASE18_GENESIS_SHA256 = hashlib.sha256(b"PHASE18-ACCESS-GENESIS-v2\n").hexdigest()


class ExitStateError(ValueError):
    pass


@dataclass(frozen=True)
class ExitValidation:
    current_state: str
    stage17_complete: bool
    phase18_handoff_prepared: bool
    record_count: int


def canonical(document: object) -> bytes:
    return (json.dumps(document, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode()


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise ExitStateError(f"not a nonsymlink regular file: {path}")
    payload = path.read_bytes()
    document = json.loads(payload)
    if not isinstance(document, dict):
        raise ExitStateError("JSON root is not an object")
    return document, payload


def _validate(root: pathlib.Path, schema_name: str, document: dict[str, Any], label: str) -> None:
    schema, _ = _load(root / "config/schemas" / schema_name)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document))
    if errors:
        raise ExitStateError(f"{label} schema rejection: {errors[0].message}")


def _binding(binding: dict[str, Any]) -> tuple[pathlib.Path, dict[str, Any] | None, bytes]:
    path = pathlib.Path(binding["path"])
    document, payload = _load(path) if path.suffix == ".json" else (None, path.read_bytes())
    if (len(payload), sha(payload)) != (binding["size_bytes"], binding["sha256"]):
        raise ExitStateError("source binding byte identity mismatch")
    return path, document, payload


def validate_exit_journal_v2(
    *, repository_root: pathlib.Path, journal_path: pathlib.Path,
    operational_validation: Any, allow_synthetic: bool = False,
) -> ExitValidation:
    root = repository_root.resolve()
    journal, _ = _load(journal_path)
    _validate(root, "stage17-exit-journal-v2.schema.json", journal, "exit journal v2")
    if journal["synthetic_test_only"] and not allow_synthetic:
        raise ExitStateError("synthetic exit journal cannot establish production progress")
    if operational_validation.current_state != EXIT_STATES[0] or not operational_validation.pilot_ready:
        raise ExitStateError("operational journal has not admitted exact pilot authority")
    if journal["operational_journal_sha256"] != operational_validation.latest_journal_sha256:
        raise ExitStateError("exit journal operational predecessor drifted")
    state, previous = EXIT_STATES[0], EXIT_GENESIS_SHA256
    records: dict[str, list[tuple[dict[str, Any], str]]] = {}
    for sequence, reference in enumerate(journal["record_references"], 1):
        _, record, payload = _binding(reference)
        assert record is not None
        _validate(root, "stage17-exit-record-v2.schema.json", record, "exit record v2")
        digest = sha(payload)
        if record["sequence_number"] != sequence or record["previous_record_sha256"] != previous:
            raise ExitStateError("exit hash chain fork/replay")
        if record["synthetic_test_only"] != journal["synthetic_test_only"]:
            raise ExitStateError("exit synthetic classification drifted")
        sources = [_binding(item) for item in record["source_bindings"]]
        kind = record["record_type"]
        if kind != "STATE_TRANSITION":
            records.setdefault(kind, []).append((record, digest))
        else:
            target = EXIT_STATES[EXIT_STATES.index(state) + 1]
            if record["payload"].get("from_state") != state or record["payload"].get("to_state") != target:
                raise ExitStateError("exit transition chronology violation")
            required = {
                "PILOT_AUTHORIZED": ("PILOT_AUTHORITY_ADMISSION",),
                "PILOT_EXECUTED": ("PILOT_ATTEMPT", "PILOT_ACTION_RESULT", "PILOT_CONTROLLER_COMPLETION"),
                "PILOT_EVIDENCE_SEALED": ("SEALED_PILOT_ARTIFACT_MANIFEST", "TREATMENT_BLIND_FREEZE"),
                "STAGE17_COMPLETE": ("ROLE_SEPARATION_DECLARATION", "STAGE17_COMPLETION_STATEMENT"),
                "PHASE18_HANDOFF_PREPARED": ("PHASE18_READINESS_REPORT", "PHASE18_AUTHORIZATION_DRAFT"),
            }[target]
            if record["payload"].get("evidence_record_types") != list(required) or any(len(records.get(item, [])) != 1 for item in required):
                raise ExitStateError("exit transition typed evidence family is incomplete")
            state = target
        previous = digest

    if state in EXIT_STATES[2:]:
        result_record = records["PILOT_ACTION_RESULT"][0][0]
        completion_record = records["PILOT_CONTROLLER_COMPLETION"][0][0]
        _, result, result_bytes = _binding(result_record["source_bindings"][0])
        _, completion, _ = _binding(completion_record["source_bindings"][0])
        assert result and completion
        _validate(root, "stage17-phase-action-result-v2.schema.json", result, "pilot result")
        _validate(root, "stage17-phase-action-completion-v2.schema.json", completion, "pilot completion")
        if result["action_id"] != "STAGE17-BLINDED-PILOT" or completion["result"]["sha256"] != sha(result_bytes):
            raise ExitStateError("pilot completion does not bind exact typed pilot result")
        if not completion["leader_reaped"] or not completion["process_group_gone"]:
            raise ExitStateError("pilot process family is not quiescent")
    if state in EXIT_STATES[3:]:
        seal = records["SEALED_PILOT_ARTIFACT_MANIFEST"][0][0]
        if seal["payload"].get("pilot_result_sha256") != records["PILOT_ACTION_RESULT"][0][1] or seal["payload"].get("controller_completion_sha256") != records["PILOT_CONTROLLER_COMPLETION"][0][1]:
            raise ExitStateError("sealed pilot manifest lineage drifted")
    if state in EXIT_STATES[4:]:
        statement = records["STAGE17_COMPLETION_STATEMENT"][0][0]["payload"]
        expected_resolutions = [
            {"input_id": item.input_id, "resolution_id": item.resolution_id, "sha256": item.sha256}
            for item in operational_validation.resolutions.values()
        ]
        if statement.get("admitted_resolutions") != expected_resolutions or statement.get("pilot_evidence_sealed") is not True or statement.get("phase18_authority") is not False:
            raise ExitStateError("Stage 17 completion is not derived from exact admitted evidence")
    if journal["current_state_claim"] != state:
        raise ExitStateError("exit current-state claim drifted")
    return ExitValidation(state, EXIT_STATES.index(state) >= 4, state == EXIT_STATES[-1],
                          len(journal["record_references"]))


def _utc(value: Any) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ExitStateError("authority timestamp is not UTC")
    try:
        return dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exception:
        raise ExitStateError("authority timestamp is malformed") from exception


def validate_phase18_access_journal_v2(
    *, repository_root: pathlib.Path, journal_path: pathlib.Path,
    readiness_report_path: pathlib.Path, actual_utc: str | None = None,
    allow_synthetic: bool = False,
) -> str:
    root = repository_root.resolve()
    journal, _ = _load(journal_path)
    _validate(root, "phase18-access-journal-v2.schema.json", journal, "Phase 18 journal v2")
    if journal["synthetic_test_only"] and not allow_synthetic:
        raise ExitStateError("synthetic Phase 18 chronology is not production authority")
    readiness, readiness_bytes = _load(readiness_report_path)
    _validate(root, "phase18-readiness-report-v2.schema.json", readiness,
              "Phase 18 readiness report v2")
    trust_path, trust_context, trust_bytes = _binding(
        readiness["independent_trust_context"]
    )
    assert trust_context is not None
    _validate(root, "phase18-trust-context-v2.schema.json", trust_context,
              "Phase 18 trust context v2")
    if trust_context["independent_from_stage17_authority"] is not True:
        raise ExitStateError("Phase 18 trust context reuses Stage 17 authority")
    if (journal["trust_context_id"], journal["trust_context_sha256"]) != (
        trust_context.get("trust_context_id"), sha(trust_bytes)):
        raise ExitStateError("Phase 18 trust context is not independently anchored")
    _, authorization, authorization_bytes = _binding(journal["authorization"])
    signature_path, _, _ = _binding(journal["signature"])
    assert authorization is not None
    _validate(root, "phase18-authorization-v2.schema.json", authorization, "Phase 18 authorization v2")
    if authorization["trust_context_id"] != trust_context["trust_context_id"] or authorization["trust_context_sha256"] != sha(trust_bytes):
        raise ExitStateError("Phase 18 authorization self-selected its trust root")
    if authorization["phase18_readiness_sha256"] != sha(readiness_bytes):
        raise ExitStateError("Phase 18 authorization does not bind admitted readiness")
    allowed_binding = trust_context.get("allowed_signers")
    if not isinstance(allowed_binding, dict):
        raise ExitStateError("Phase 18 allowed-signers binding is absent")
    allowed_path, _, _ = _binding(allowed_binding)
    allowed_snapshot: snapshot_broker.ParentSnapshot | None = None
    signature_snapshot: snapshot_broker.ParentSnapshot | None = None
    try:
        allowed_snapshot = snapshot_broker.pin_bound_input({
            "locator": str(allowed_path),
            "size_bytes": allowed_binding["size_bytes"],
            "sha256": allowed_binding["sha256"],
        }, "PHASE18_ALLOWED_SIGNERS")
        signature_snapshot = snapshot_broker.pin_bound_input({
            "locator": str(signature_path),
            "size_bytes": journal["signature"]["size_bytes"],
            "sha256": journal["signature"]["sha256"],
        }, "PHASE18_SIGNATURE")
    except snapshot_broker.SnapshotError as exception:
        snapshot_broker.close_snapshots(allowed_snapshot, signature_snapshot)
        raise ExitStateError("Phase 18 signature inputs could not be sealed") from exception
    assert allowed_snapshot is not None and signature_snapshot is not None
    try:
        verified = subprocess.run(
            ["/usr/bin/ssh-keygen", "-Y", "verify", "-f",
             allowed_snapshot.locator, "-I", trust_context["principal"], "-n",
             trust_context["sshsig_namespace"], "-s", signature_snapshot.locator],
            input=authorization_bytes, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=10,
        )
        snapshot_broker.verify_snapshot(allowed_snapshot)
        snapshot_broker.verify_snapshot(signature_snapshot)
    except (OSError, subprocess.SubprocessError,
            snapshot_broker.SnapshotError) as exception:
        raise ExitStateError("Phase 18 signature verification boundary failed") from exception
    finally:
        snapshot_broker.close_snapshots(allowed_snapshot, signature_snapshot)
    if verified.returncode != 0:
        raise ExitStateError("Phase 18 authorization signature rejected")
    issued = _utc(authorization["issued_at_utc"])
    expires = _utc(authorization["expires_at_utc"])
    sample = (_utc(actual_utc) if allow_synthetic and actual_utc is not None
              else dt.datetime.now(dt.timezone.utc))
    if (authorization["actor"] != trust_context["principal"]
            or not issued <= sample < expires
            or expires - issued > dt.timedelta(seconds=1800)):
        raise ExitStateError("Phase 18 authorization is future or expired")
    if authorization["stage17_completion_sha256"] != readiness["stage17_completion_sha256"]:
        raise ExitStateError("Phase 18 authorization does not bind Stage 17 completion")
    state, previous = PHASE18_STATES[0], PHASE18_GENESIS_SHA256
    authorization_sha = sha(authorization_bytes)
    for sequence, transition in enumerate(journal["transitions"], 1):
        target = PHASE18_STATES[PHASE18_STATES.index(state) + 1]
        if (transition["sequence_number"], transition["from_state"], transition["to_state"], transition["previous_transition_sha256"], transition["authorization_sha256"]) != (sequence, state, target, previous, authorization_sha):
            raise ExitStateError("Phase 18 chronology/hash/authority violation")
        if transition["actor"] != authorization["actor"]:
            raise ExitStateError("Phase 18 transition actor differs from authority")
        for evidence in transition["evidence"]:
            _binding(evidence)
        if transition["stage17_authority_used"] is not False:
            raise ExitStateError("Stage 17 authority cannot advance Phase 18")
        if not _utc(authorization["issued_at_utc"]) <= _utc(transition["timestamp_utc"]) < _utc(authorization["expires_at_utc"]):
            raise ExitStateError("Phase 18 transition outside authority window")
        previous, state = sha(canonical(transition)), target
    if journal["current_state_claim"] != state:
        raise ExitStateError("Phase 18 current-state claim mismatch")
    return state
