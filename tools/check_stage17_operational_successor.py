#!/usr/bin/env python3
"""Validate the finite Stage 17 pilot operational-governance successor."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
SUCCESSOR_PATH = ROOT / "config/stage17/stage17-operational-authorization-successor-v1.json"
SUCCESSOR_SCHEMA = ROOT / "config/schemas/stage17-operational-authorization-successor-v1.schema.json"
CHECKLIST_PATH = ROOT / "config/stage17/stage17-external-input-checklist-v1.json"
CHECKLIST_SCHEMA = ROOT / "config/schemas/stage17-external-input-checklist-v1.schema.json"
PRESERVATION_PATH = ROOT / "config/stage17/d099-d108-preservation-manifest-v1.json"
PRESERVATION_SCHEMA = ROOT / "config/schemas/stage17-predecessor-preservation-v1.schema.json"
EXTERNAL_ARCHIVE_CONTRACT = ROOT / "config/q15/q15-qualification-archive-external-contract-v1.json"
EXTERNAL_ARCHIVE_SCHEMA = ROOT / "config/schemas/q15-qualification-archive-external-contract-v1.schema.json"
RELEASE_EVIDENCE_PATH = ROOT / "config/stage17/stage17-pilot-candidate-release-evidence-v1.json"
RELEASE_EVIDENCE_SCHEMA = ROOT / "config/schemas/stage17-pilot-candidate-release-evidence-v1.schema.json"

STATE_ORDER = [
    "PREPARED",
    "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT",
    "PREFLIGHT_ACCEPTED",
    "READY_FOR_STAGE17_PHASE_AUTHORIZATION",
]
CONFIRMATORY_ORDER = [
    "PLANNED",
    "COLLECTED_SEALED",
    "TRAINING_OPEN",
    "SELECTION_FROZEN",
    "VALIDATION_UNSEALED",
    "H3_EVALUATED",
    "H1H2_RELEASED",
    "ARCHIVED",
]
PILOT_READY_IDS = {f"S17-EXT-{index:03d}" for index in range(1, 11)}


class TransitionError(ValueError):
    """A requested state transition violates the frozen finite graph."""


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256(path: pathlib.Path) -> str:
    return sha256_bytes(path.read_bytes())


def schema_errors(document: dict[str, Any], schema_path: pathlib.Path) -> list[str]:
    schema = load(schema_path)
    Draft202012Validator.check_schema(schema)
    return [
        f"$/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in Draft202012Validator(schema).iter_errors(document)
    ]


def resolved_ids(checklist: dict[str, Any]) -> set[str]:
    return {
        str(item.get("input_id"))
        for item in checklist.get("items", [])
        if item.get("status") in {"RESOLVED", "NOT_APPLICABLE"}
    }


def evaluate_state(successor: dict[str, Any], checklist: dict[str, Any]) -> str:
    state = STATE_ORDER[0]
    resolved = resolved_ids(checklist)
    for transition in successor.get("transitions", []):
        if transition.get("from") != state:
            raise TransitionError("transition graph is not one adjacent ordered chain")
        required = set(transition.get("required_external_input_ids", []))
        if not required <= resolved:
            break
        state = str(transition.get("to"))
    return state


def transition_to(
    successor: dict[str, Any], checklist: dict[str, Any], target: str
) -> str:
    current = str(successor.get("current_state"))
    try:
        index = STATE_ORDER.index(current)
    except ValueError as exception:
        raise TransitionError("unknown current state") from exception
    if index + 1 >= len(STATE_ORDER) or target != STATE_ORDER[index + 1]:
        raise TransitionError("only the next adjacent state is reachable")
    transition = successor.get("transitions", [])[index]
    required = set(transition.get("required_external_input_ids", []))
    missing = sorted(required - resolved_ids(checklist))
    if missing:
        raise TransitionError(f"transition inputs unresolved: {','.join(missing)}")
    return target


def pilot_ready(successor: dict[str, Any], checklist: dict[str, Any]) -> bool:
    return (
        evaluate_state(successor, checklist)
        == "READY_FOR_STAGE17_PHASE_AUTHORIZATION"
        and PILOT_READY_IDS <= resolved_ids(checklist)
    )


def verify_artifact_ref(reference: dict[str, Any], label: str) -> list[str]:
    path_text = reference.get("path")
    if not isinstance(path_text, str):
        return [f"{label} path is missing"]
    path = pathlib.PurePosixPath(path_text)
    if path.is_absolute() or ".." in path.parts:
        return [f"{label} path is not repository-relative"]
    actual = ROOT / path
    if not actual.is_file():
        return [f"{label} file is absent: {path_text}"]
    if sha256(actual) != reference.get("sha256"):
        return [f"{label} SHA-256 mismatch: {path_text}"]
    return []


def preservation_errors(preservation: dict[str, Any]) -> list[str]:
    errors = schema_errors(preservation, PRESERVATION_SCHEMA)
    artifacts = preservation.get("tracked_artifacts", [])
    paths = [item.get("path") for item in artifacts]
    if len(paths) != len(set(paths)):
        errors.append("preservation manifest contains duplicate tracked paths")
    for item in artifacts:
        errors.extend(verify_artifact_ref(item, "preserved predecessor"))
    for source in preservation.get("historical_implementation_sources", []):
        revision = source.get("git_revision")
        path = source.get("path")
        completed = subprocess.run(
            ["git", "show", f"{revision}:{path}"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            errors.append(f"historical implementation unavailable: {revision}:{path}")
        elif sha256_bytes(completed.stdout) != source.get("sha256"):
            errors.append(f"historical implementation SHA-256 mismatch: {revision}:{path}")
    return errors


def checklist_errors(checklist: dict[str, Any]) -> list[str]:
    errors = schema_errors(checklist, CHECKLIST_SCHEMA)
    items = checklist.get("items", [])
    identifiers = [item.get("input_id") for item in items]
    if set(identifiers) != PILOT_READY_IDS or len(identifiers) != len(PILOT_READY_IDS):
        errors.append("external checklist is not the exact unique S17-EXT-001..010 set")
    unresolved = [item for item in items if item.get("status") == "EXTERNAL_REQUIRED"]
    if checklist.get("unresolved_count") != len(unresolved):
        errors.append("external checklist unresolved_count mismatch")
    complete = not unresolved
    if checklist.get("all_resolved") is not complete:
        errors.append("external checklist all_resolved mismatch")
    expected_status = "COMPLETE" if complete else "EXTERNAL_INPUTS_REQUIRED"
    if checklist.get("status") != expected_status:
        errors.append("external checklist status mismatch")
    for item in items:
        resolved = item.get("status") in {"RESOLVED", "NOT_APPLICABLE"}
        has_reference = isinstance(item.get("artifact_id"), str) and isinstance(
            item.get("sha256"), str
        )
        if resolved is not has_reference:
            errors.append(f"{item.get('input_id')} resolution/reference mismatch")
    release_item = next(
        (item for item in items if item.get("input_id") == "S17-EXT-006"), None
    )
    if release_item is None or release_item.get("status") != "RESOLVED":
        errors.append("S17-EXT-006 clean release evidence is not resolved")
    else:
        release_evidence = load(RELEASE_EVIDENCE_PATH)
        errors.extend(schema_errors(release_evidence, RELEASE_EVIDENCE_SCHEMA))
        if release_item.get("artifact_id") != release_evidence.get("evidence_id"):
            errors.append("S17-EXT-006 evidence identity mismatch")
        if release_item.get("sha256") != sha256(RELEASE_EVIDENCE_PATH):
            errors.append("S17-EXT-006 evidence SHA-256 mismatch")
        authority = release_evidence.get("authority_boundary", {})
        if any(authority.values()):
            errors.append("S17-EXT-006 release evidence grants operational authority")
    return errors


def semantic_errors(
    successor: dict[str, Any],
    checklist: dict[str, Any],
    preservation: dict[str, Any],
    *,
    verify_files: bool,
) -> list[str]:
    errors: list[str] = []
    if successor.get("state_order") != STATE_ORDER:
        errors.append("Stage 17 state order drifted")
    transitions = successor.get("transitions", [])
    expected_edges = list(zip(STATE_ORDER[:-1], STATE_ORDER[1:], strict=True))
    observed_edges = [
        (transition.get("from"), transition.get("to")) for transition in transitions
    ]
    if observed_edges != expected_edges:
        errors.append("Stage 17 transition graph is not the exact finite chain")
    all_transition_inputs = [
        item
        for transition in transitions
        for item in transition.get("required_external_input_ids", [])
    ]
    if all_transition_inputs != [f"S17-EXT-{index:03d}" for index in range(1, 7)]:
        errors.append("transition inputs must be the exact ordered S17-EXT-001..006 prefix")
    pilot = successor.get("pilot_governance", {})
    roles = pilot.get("roles", {})
    if set(roles.values()) != {pilot.get("role_principal")}:
        errors.append("pilot owner/operator/controller/custodian/auditor are not collapsed")
    if pilot.get("independent_review_claimed") is not False:
        errors.append("collapsed pilot governance claimed independent review")
    if pilot.get("pki_ceremony_per_read_only_observation_required") is not False:
        errors.append("pilot successor reintroduced per-observation PKI")
    confirmatory = successor.get("confirmatory_governance", {})
    if (
        confirmatory.get("access_state_order") != CONFIRMATORY_ORDER
        or confirmatory.get("strict_chronology_preserved") is not True
        or confirmatory.get("pilot_role_collapse_applies") is not False
        or confirmatory.get("stage17_authority_may_authorize_stage18") is not False
    ):
        errors.append("Stage 18 access/sealing boundary was weakened")
    try:
        expected_state = evaluate_state(successor, checklist)
        if successor.get("current_state") != expected_state:
            errors.append("current state claims transitions not supported by checklist evidence")
    except TransitionError as exception:
        errors.append(str(exception))
    if successor.get("status") == "PREPARED_EXTERNAL_INPUTS_REQUIRED" and pilot_ready(
        successor, checklist
    ):
        errors.append("prepared successor is inconsistently pilot-ready")
    errors.extend(checklist_errors(checklist))
    errors.extend(preservation_errors(preservation) if verify_files else [])
    if verify_files:
        for field, label in (
            ("prospective_adr", "prospective ADR"),
            ("preserved_predecessors", "preservation manifest"),
            ("external_input_checklist", "external checklist"),
        ):
            errors.extend(verify_artifact_ref(successor.get(field, {}), label))
        executor = successor.get("hermetic_executor_successor", {})
        errors.extend(verify_artifact_ref(executor, "hermetic executor successor"))
        errors.extend(
            verify_artifact_ref(
                executor.get("external_archive_contract", {}),
                "external archive contract",
            )
        )
        errors.extend(schema_errors(load(EXTERNAL_ARCHIVE_CONTRACT), EXTERNAL_ARCHIVE_SCHEMA))
    return errors


def mark_resolved(checklist: dict[str, Any], identifiers: set[str]) -> None:
    for item in checklist["items"]:
        if item["input_id"] in identifiers:
            item["status"] = "RESOLVED"
            item["artifact_id"] = f"SYNTHETIC-{item['input_id']}"
            item["sha256"] = "a" * 64
    unresolved = sum(item["status"] == "EXTERNAL_REQUIRED" for item in checklist["items"])
    checklist["unresolved_count"] = unresolved
    checklist["all_resolved"] = unresolved == 0
    checklist["status"] = "COMPLETE" if unresolved == 0 else "EXTERNAL_INPUTS_REQUIRED"


def self_test(successor: dict[str, Any], checklist: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    positive_successor = copy.deepcopy(successor)
    positive_checklist = copy.deepcopy(checklist)
    for target, inputs in (
        ("AUTHORIZED_FOR_READ_ONLY_PREFLIGHT", {"S17-EXT-001"}),
        ("PREFLIGHT_ACCEPTED", {"S17-EXT-002", "S17-EXT-003"}),
        (
            "READY_FOR_STAGE17_PHASE_AUTHORIZATION",
            {"S17-EXT-004", "S17-EXT-005", "S17-EXT-006"},
        ),
    ):
        mark_resolved(positive_checklist, inputs)
        try:
            transition_to(positive_successor, positive_checklist, target)
        except TransitionError as exception:
            errors.append(f"positive transition to {target} failed: {exception}")
            break
        positive_successor["current_state"] = target
    if pilot_ready(positive_successor, positive_checklist):
        errors.append("phase-ready state became pilot-ready before S17-EXT-007..010")
    mark_resolved(
        positive_checklist,
        {"S17-EXT-007", "S17-EXT-008", "S17-EXT-009", "S17-EXT-010"},
    )
    if not pilot_ready(positive_successor, positive_checklist):
        errors.append("fully resolved known-answer checklist did not become pilot-ready")

    for label, current, target, resolved in (
        ("skip", "PREPARED", "PREFLIGHT_ACCEPTED", {"S17-EXT-001", "S17-EXT-002", "S17-EXT-003"}),
        ("missing", "PREPARED", "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT", set()),
        ("regression", "PREFLIGHT_ACCEPTED", "AUTHORIZED_FOR_READ_ONLY_PREFLIGHT", PILOT_READY_IDS),
    ):
        mutant_successor = copy.deepcopy(successor)
        mutant_successor["current_state"] = current
        mutant_checklist = copy.deepcopy(checklist)
        mark_resolved(mutant_checklist, resolved)
        try:
            transition_to(mutant_successor, mutant_checklist, target)
        except TransitionError:
            continue
        errors.append(f"negative {label} transition passed")

    mutants: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    role_mutant = copy.deepcopy(successor)
    role_mutant["pilot_governance"]["roles"]["auditor"] = "fabricated-independent-auditor"
    mutants.append((role_mutant, checklist, "role split drift"))
    pki_mutant = copy.deepcopy(successor)
    pki_mutant["pilot_governance"]["pki_ceremony_per_read_only_observation_required"] = True
    mutants.append((pki_mutant, checklist, "per-observation PKI"))
    stage18_mutant = copy.deepcopy(successor)
    stage18_mutant["confirmatory_governance"]["access_state_order"].remove("SELECTION_FROZEN")
    mutants.append((stage18_mutant, checklist, "Stage 18 chronology"))
    ahead_mutant = copy.deepcopy(successor)
    ahead_mutant["current_state"] = "PREFLIGHT_ACCEPTED"
    mutants.append((ahead_mutant, checklist, "unsupported current state"))
    count_mutant = copy.deepcopy(checklist)
    count_mutant["unresolved_count"] -= 1
    mutants.append((successor, count_mutant, "checklist count"))
    for mutant_successor, mutant_checklist, label in mutants:
        if not schema_errors(mutant_successor, SUCCESSOR_SCHEMA) and not semantic_errors(
            mutant_successor,
            mutant_checklist,
            load(PRESERVATION_PATH),
            verify_files=False,
        ):
            errors.append(f"negative {label} mutation passed")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--print-missing", action="store_true")
    arguments = parser.parse_args()
    successor = load(SUCCESSOR_PATH)
    checklist = load(CHECKLIST_PATH)
    preservation = load(PRESERVATION_PATH)
    errors = schema_errors(successor, SUCCESSOR_SCHEMA)
    errors.extend(semantic_errors(successor, checklist, preservation, verify_files=True))
    if arguments.self_test:
        errors.extend(self_test(successor, checklist))
    if errors:
        for error in errors:
            print(f"stage17-operational-successor-check: FAIL: {error}", file=sys.stderr)
        return 1
    if arguments.print_missing:
        output = {
            "current_state": successor["current_state"],
            "pilot_ready": pilot_ready(successor, checklist),
            "missing_external_inputs": [
                item["input_id"]
                for item in checklist["items"]
                if item["status"] == "EXTERNAL_REQUIRED"
            ],
        }
        print(json.dumps(output, sort_keys=True, separators=(",", ":")))
    else:
        print(
            "stage17-operational-successor-check: PASS "
            f"(state={successor['current_state']}; transitions=3; "
            f"external_inputs={checklist['unresolved_count']}; pilot_ready=false; "
            "Stage17/Stage18 complete=false; stand=NOT_ACCESSED)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
