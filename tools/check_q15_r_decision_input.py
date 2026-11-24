#!/usr/bin/env python3
"""Validate the non-authorizing Q15-R decision/input bundle."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


EXPECTED_DECISIONS = ("D-057", "D-058", "D-059", "D-060")
U64_MAX = 18_446_744_073_709_551_615
FORBIDDEN_AUTHORITY_TRUE = {
    "stand_access_authorized",
    "account_or_key_changes_authorized",
    "bundle_transfer_or_install_authorized",
    "q15_r_authorized",
    "q15_w_authorized",
    "dynamic_qualification_authorized",
    "real_pmu_authorized",
    "msr_read_authorized",
    "msr_write_authorized",
    "real_affinity_numa_authorized",
    "calibration_authorized",
    "pilot_authorized",
    "measurement_authorized",
    "confirmatory_authorized",
}
LOCAL_HASH_BINDINGS = {
    "config/q15/q15-probe-collector-contract-v1.json": (
        "qualification_component_release",
        "probe_contract_sha256",
    ),
    "config/q15/q15-probe-implementation-profile-v1.json": (
        "qualification_component_release",
        "probe_implementation_sha256",
    ),
    "config/q15/q15-dynamic-implementation-profile-v1.json": (
        "qualification_component_release",
        "dynamic_profile_sha256",
    ),
    "protocol/2.0.0-pre.2/IMPORT_MANIFEST.json": (
        "qualification_component_release",
        "protocol_import_manifest_sha256",
    ),
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decision_map(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get("decision_id", ""): item
        for item in document.get("decisions", [])
        if isinstance(item, dict)
    }


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if tuple(document.get("decision_ids", ())) != EXPECTED_DECISIONS:
        errors.append("decision IDs must be exactly D-057 through D-060 in order")
    decisions = decision_map(document)
    if tuple(decisions) != EXPECTED_DECISIONS:
        errors.append("decision records must be unique and ordered D-057 through D-060")

    boundary = document.get("authority_boundary", {})
    for field in FORBIDDEN_AUTHORITY_TRUE:
        if boundary.get(field) is not False:
            errors.append(f"{field} must remain false in a preparation bundle")
    if boundary.get("repository_local_implementation_authorized") is not True:
        errors.append("accepted Q15-R-P1 record must authorize repository-local work")

    for relative, (section, field) in LOCAL_HASH_BINDINGS.items():
        path = root / relative
        if not path.is_file():
            errors.append(f"bound local artifact is missing: {relative}")
            continue
        expected = document.get(section, {}).get(field)
        if expected != sha256(path):
            errors.append(f"bound local artifact hash mismatch: {relative}")

    decision_hash = sha256(root / "config/q15/q15-r-decision-input-v1.json")
    for name in ("q15-r.preparation.json", "q15-w.preparation.json"):
        preparation_path = root / "config/q15" / name
        try:
            preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            errors.append(f"blocked preparation is missing or malformed: {name}")
            continue
        known = preparation.get("known_inputs", {})
        if (
            known.get("q15_r_decision_input_id")
            != "Q15-R-DECISION-INPUT-20260824-01"
            or known.get("q15_r_decision_input_sha256") != decision_hash
        ):
            errors.append(f"blocked preparation does not bind this decision input: {name}")

    for artifact in document.get("stand_evidence", {}).values():
        if not isinstance(artifact, dict) or "relative_path" not in artifact:
            continue
        relative = artifact["relative_path"]
        path = root / relative
        if not path.is_file():
            errors.append(f"bound stand artifact is missing: {relative}")
        elif artifact.get("sha256") != sha256(path):
            errors.append(f"bound stand artifact hash mismatch: {relative}")

    d57 = decisions.get("D-057", {}).get("exact_inputs_if_approved", {})
    if d57.get("controller_executable") != "cpu_prefetch_q15_controller":
        errors.append("D-057 must use the fixed separate Q15 controller")
    if d57.get("authorization_format") != "cpu-prefetch-q15-qualification-authorization/2":
        errors.append("D-057 must require the controller-graph authorization v2")
    if d57.get("arbitrary_runtime_selectors") is not False:
        errors.append("D-057 cannot permit arbitrary runtime selectors")
    graph = d57.get("command_graph", [])
    if len(graph) != len(set(graph)) or graph[-1:] != [
        "WAIT_FOR_SEPARATE_Q15_W_OR_EXPIRE_FAIL_CLOSED"
    ]:
        errors.append("D-057 graph must be unique and end in fail-closed handoff")
    required_graph = {
        "COLLECT_FIXED_MSR_PRESTATE_AS_AUDITOR",
        "RUN_H0_REGULAR_STREAM_PROBE",
        "RUN_H0_POINTER_STREAM_PROBE",
        "SEAL_Q15_R_EVIDENCE",
    }
    if not required_graph.issubset(graph):
        errors.append("D-057 graph is missing mandatory Q15-R operations")

    d58 = decisions.get("D-058", {}).get("exact_inputs_if_approved", {})
    principals = [
        d58.get("operator_principal_id"),
        d58.get("controller_principal_id"),
        d58.get("custodian_principal_id"),
        d58.get("auditor_principal_id"),
    ]
    if None in principals or len(set(principals)) != 4:
        errors.append("D-058 requires four exact distinct principal IDs")
    if d58.get("primary_domain_id") == d58.get("secondary_domain_id"):
        errors.append("D-058 requires distinct primary and secondary custody domains")
    output_root = d58.get("output_root")
    if not isinstance(output_root, str) or not output_root.startswith("/var/lib/"):
        errors.append("D-058 output root must be the exact scoped /var/lib path")

    d59 = decisions.get("D-059", {}).get("exact_inputs_if_approved", {})
    numeric_fields = (
        "authorization_validity_seconds",
        "controller_start_poll_limit",
        "external_start_watchdog_seconds",
        "frame_maximum_payload_bytes",
        "max_active_collection_wall_seconds",
        "max_artifact_count",
        "max_cpu_seconds",
        "max_output_bytes",
        "max_same_buffer_session_wall_seconds",
        "primary_custody_quota_bytes",
        "worker_start_poll_limit",
    )
    if any(not isinstance(d59.get(field), int) or d59[field] <= 0 for field in numeric_fields):
        errors.append("D-059 limits must all be explicit positive integers")
    elif not (
        d59["controller_start_poll_limit"] == U64_MAX
        and d59["worker_start_poll_limit"] == U64_MAX
        and d59["external_start_watchdog_seconds"]
        < d59["max_active_collection_wall_seconds"]
        < d59["max_same_buffer_session_wall_seconds"]
        <= d59["authorization_validity_seconds"]
        and d59["frame_maximum_payload_bytes"]
        < d59["max_output_bytes"]
        < d59["primary_custody_quota_bytes"]
    ):
        errors.append("D-059 limits violate the frozen containment ordering")
    stops = d59.get("stop_conditions", [])
    if "PRESERVE_PARTIAL_EVIDENCE_AND_NEVER_RETRY" not in stops:
        errors.append("D-059 must stop without retry and retain partial evidence")

    d60 = decisions.get("D-060", {}).get("exact_inputs_if_approved", {})
    if d60.get("authorization_signature_scheme") != "OPENSSH-SSHSIG-ED25519-SHA512-v1":
        errors.append("D-060 signature scheme drift")
    if d60.get("authorization_signature_namespace") != "cpu-prefetch-q15-authorization":
        errors.append("D-060 signature namespace drift")
    if d60.get("issuance_requires_new_explicit_approval") is not True:
        errors.append("D-060 must require later explicit Q15-R issuance approval")
    prohibited = set(d60.get("approval_does_not_authorize", []))
    for value in ("STAND_ACCESS", "Q15_R_EXECUTION", "Q15_W_PREPARATION_OR_EXECUTION", "PILOT"):
        if value not in prohibited:
            errors.append(f"D-060 approval boundary is missing {value}")

    gates = document.get("remaining_evidence_gates", [])
    if not any("later explicit approval" in item.casefold() for item in gates):
        errors.append("remaining gates must require a later explicit Q15-R approval")
    return errors


def validate(
    root: pathlib.Path,
    validator: Draft202012Validator,
    document: dict[str, Any],
) -> list[str]:
    failures = [error.message for error in validator.iter_errors(document)]
    failures.extend(semantic_errors(root, document))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--document", type=pathlib.Path)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    schema_path = root / "config/schemas/q15-r-decision-input-v1.schema.json"
    if not schema_path.is_file():
        schema_path = (
            root
            / "config/schemas/implementation/q15-r-decision-input-v1.schema.json"
        )
    document_path = args.document or root / "config/q15/q15-r-decision-input-v1.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        document = json.loads(document_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"q15-r-decision-input-check: FAIL: {error}", file=sys.stderr)
        return 1
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    if failures := validate(root, validator, document):
        for failure in failures:
            print(f"q15-r-decision-input-check: FAIL: {failure}", file=sys.stderr)
        return 1

    negatives: list[dict[str, Any]] = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["q15_r_authorized"] = True
    negatives.append(authority)
    overlap = copy.deepcopy(document)
    overlap["decisions"][1]["exact_inputs_if_approved"]["auditor_principal_id"] = (
        overlap["decisions"][1]["exact_inputs_if_approved"]["operator_principal_id"]
    )
    negatives.append(overlap)
    missing_graph = copy.deepcopy(document)
    missing_graph["decisions"][0]["exact_inputs_if_approved"]["command_graph"].remove(
        "RUN_H0_POINTER_STREAM_PROBE"
    )
    negatives.append(missing_graph)
    no_watchdog = copy.deepcopy(document)
    no_watchdog["decisions"][2]["exact_inputs_if_approved"][
        "external_start_watchdog_seconds"
    ] = 0
    negatives.append(no_watchdog)
    no_later_approval = copy.deepcopy(document)
    no_later_approval["decisions"][3]["exact_inputs_if_approved"][
        "issuance_requires_new_explicit_approval"
    ] = False
    negatives.append(no_later_approval)
    for index, negative in enumerate(negatives):
        if not validate(root, validator, negative):
            print(
                f"q15-r-decision-input-check: FAIL: negative {index} passed",
                file=sys.stderr,
            )
            return 1
    print(
        "q15-r-decision-input-check: PASS "
        "(D-057..D-060, 5 negative, no authority issued)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
