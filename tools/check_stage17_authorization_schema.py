#!/usr/bin/env python3
"""Validate Q14/Q15-P0 authorization envelopes without granting authority."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


FORBIDDEN_EXACT_TOKENS = {"*", "latest", "current", "unresolved", "tbd"}
EXECUTION_PHASES = (
    "D2_CALIBRATION",
    "SERVICE_RATE_CALIBRATION",
    "ZERO_LOSS_FEASIBILITY",
    "BLINDED_PILOT_FREEZE_INPUT",
)


def artifact(identity: str) -> dict[str, object]:
    return {"artifact_id": identity, "sha256": "0" * 64}


def base(phase: str) -> dict[str, Any]:
    phase_inputs: dict[str, Any] | None = None
    if phase != "STAND_QUALIFICATION":
        phase_inputs = {
            "qualification_artifact": artifact("SYNTHETIC-QUALIFICATION"),
            "run_plan": artifact("SYNTHETIC-RUN-PLAN"),
            "configurations": [artifact("SYNTHETIC-CONFIG")],
            "schedules": [artifact("SYNTHETIC-SCHEDULE")],
            "namespaces": [f"SYNTHETIC-{phase}-NAMESPACE"],
            "seeds": [artifact("SYNTHETIC-SEED")],
            "predecessor_artifacts": (
                [] if phase == "D2_CALIBRATION" else [artifact("SYNTHETIC-PREDECESSOR")]
            ),
            "permitted_run_ids": ["SYNTHETIC-RUN-0001"],
            "permitted_run_count": 1,
            "hardware_states": ["H0", "H1"],
        }
    return {
        "schema_version": "cpu-prefetch-stage17-authorization/2",
        "protocol_version": "2.0.0-pre.2",
        "authorization_id": f"SYNTHETIC-{phase}-AUTHORIZATION",
        "authorization_version": "SYNTHETIC-v1",
        "phase": phase,
        "status": "AUTHORIZED",
        "issued_at_utc": "2026-08-22T00:00:00Z",
        "expires_at_utc": "2026-08-23T00:00:00Z",
        "stand_id": "SYNTHETIC-STAND",
        "binding_id": "SYNTHETIC-BINDING",
        "source_revision": "0123456789abcdef",
        "binary_sha256": "0" * 64,
        "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v3",
        "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
        "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
        "prerequisite_artifacts": [artifact("SYNTHETIC-PREREQUISITE")],
        "authorities": {
            "operator": "SYNTHETIC-OPERATOR",
            "controller": "SYNTHETIC-CONTROLLER",
            "custodian": "SYNTHETIC-CUSTODIAN",
            "auditor": "SYNTHETIC-AUDITOR",
        },
        "permitted_commands": [
            {
                "command_id": "SYNTHETIC-COMMAND",
                "executable_sha256": "0" * 64,
                "argv": ["/synthetic/bin/tool", "--exact-value", "SYNTHETIC-VALUE"],
                "privilege": "NONPRIVILEGED",
                "exact_target": "SYNTHETIC-TARGET",
                "inverse_argv": ["/synthetic/bin/tool", "--restore", "SYNTHETIC-PRESTATE"],
                "independent_readback_argv": ["/synthetic/bin/readback", "SYNTHETIC-TARGET"],
                "probe_argv": ["/synthetic/bin/probe", "SYNTHETIC-TARGET"],
                "output_artifact_id": "SYNTHETIC-COMMAND-OUTPUT",
            }
        ],
        "limits": {
            "max_wall_seconds": 1,
            "max_output_bytes": 1,
            "max_artifact_count": 1,
            "max_cpu_seconds": 1,
        },
        "storage_custody": {
            "primary_domain_id": "SYNTHETIC-PRIMARY",
            "secondary_domain_id": "SYNTHETIC-SECONDARY",
            "output_root": "/synthetic/exact/output",
            "append_only_policy_id": "SYNTHETIC-APPEND-ONLY",
            "transfer_policy_id": "SYNTHETIC-TRANSFER",
            "partial_artifact_policy_id": "SYNTHETIC-PARTIAL",
        },
        "stop_conditions": ["SYNTHETIC-STOP-ON-FIRST-MISMATCH"],
        "phase_inputs": phase_inputs,
        "prohibitions": {
            "confirmatory_execution": False,
            "later_phase_execution": False,
            "outcome_driven_tuning": False,
            "top_up": False,
            "cell_repair": False,
            "hidden_retry": False,
            "unlisted_privilege": False,
        },
        "detached_signature": {
            "scheme": "SYNTHETIC-SCHEME",
            "signer_id": "SYNTHETIC-SIGNER",
            "artifact_id": "SYNTHETIC-SIGNATURE",
            "sha256": "0" * 64,
        },
    }


def parse_utc(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for child in value for item in collect_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in collect_strings(child)]
    return []


def duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        if parse_utc(document["expires_at_utc"]) <= parse_utc(document["issued_at_utc"]):
            errors.append("authorization expiry must follow issuance")
    except (KeyError, TypeError, ValueError):
        errors.append("authorization timestamps must be parseable UTC values")

    authorities = list(document.get("authorities", {}).values())
    if duplicates(authorities):
        errors.append("operator/controller/custodian/auditor identities must be distinct")

    primary = document.get("storage_custody", {}).get("primary_domain_id")
    secondary = document.get("storage_custody", {}).get("secondary_domain_id")
    if primary == secondary:
        errors.append("durable domains must be distinct")

    commands = document.get("permitted_commands", [])
    command_ids = [command.get("command_id", "") for command in commands]
    output_ids = [command.get("output_artifact_id", "") for command in commands]
    if duplicates(command_ids) or duplicates(output_ids):
        errors.append("command and output artifact IDs must be unique")

    prerequisite_ids = [
        item.get("artifact_id", "") for item in document.get("prerequisite_artifacts", [])
    ]
    if duplicates(prerequisite_ids):
        errors.append("prerequisite artifact IDs must be unique")

    for value in collect_strings(document):
        if value.casefold() in FORBIDDEN_EXACT_TOKENS:
            errors.append("wildcard/latest/current/unresolved/TBD tokens are forbidden")
            break

    if document.get("storage_custody", {}).get("output_root") == "/":
        errors.append("filesystem root cannot be the output root")

    phase = document.get("phase")
    phase_inputs = document.get("phase_inputs")
    if (
        document.get("schema_version") == "cpu-prefetch-stage17-authorization/2"
        and phase == "STAND_QUALIFICATION"
    ):
        errors.append("ADR-0051 supersedes new omnibus Q15 requests")
    if phase == "STAND_QUALIFICATION" and phase_inputs is not None:
        errors.append("stand qualification cannot contain scientific phase inputs")
    if phase in EXECUTION_PHASES:
        if not isinstance(phase_inputs, dict):
            errors.append("execution phase requires exact phase inputs")
        else:
            run_ids = phase_inputs.get("permitted_run_ids", [])
            if len(run_ids) != phase_inputs.get("permitted_run_count"):
                errors.append("permitted run count must equal exact run-ID count")
            if duplicates(run_ids):
                errors.append("permitted run IDs must be unique")
            if duplicates(phase_inputs.get("namespaces", [])):
                errors.append("seed namespaces must be unique")
            if any("confirmatory" in item.casefold() for item in phase_inputs.get("namespaces", [])):
                errors.append("confirmatory namespaces are forbidden")
            if phase != "D2_CALIBRATION" and not phase_inputs.get("predecessor_artifacts"):
                errors.append("dependent phase requires predecessor artifacts")

    return errors


def validation_errors(
    validator: Draft202012Validator, document: dict[str, Any]
) -> list[str]:
    errors = [
        f"$/{'/'.join(str(item) for item in error.absolute_path)}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    ]
    errors.extend(f"semantic: {message}" for message in semantic_errors(document))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--document",
        type=pathlib.Path,
        help="validate one exact prospective authorization; never issues authority",
    )
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    semantic_admission_schema_paths = (
        "stage17-operational-evidence-admission-policy-v2.schema.json",
        "stage17-operational-evidence-envelope-v2.schema.json",
        "stage17-read-only-preflight-authorization-v2.schema.json",
        "stage17-read-only-preflight-supporting-contract-v2.schema.json",
        "stage17-operational-evidence-admission-policy-v3.schema.json",
        "stage17-operational-evidence-envelope-v3.schema.json",
        "stage17-read-only-preflight-authorization-v3.schema.json",
        "stage17-read-only-preflight-supporting-contract-v3.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v1.schema.json",
        "stage17-read-only-preflight-attempt-v1.schema.json",
        "stage17-pinned-host-key-evidence-v1.schema.json",
        "stage17-operational-evidence-admission-policy-v4.schema.json",
        "stage17-operational-evidence-envelope-v4.schema.json",
        "stage17-read-only-preflight-authorization-v4.schema.json",
        "stage17-read-only-preflight-supporting-contract-v4.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v2.schema.json",
        "stage17-read-only-preflight-attempt-v2.schema.json",
        "stage17-read-only-preflight-observation-receipt-v1.schema.json",
        "stage17-read-only-preflight-failure-v2.schema.json",
        "stage17-read-only-preflight-completion-v1.schema.json",
        "stage17-operational-evidence-admission-policy-v5.schema.json",
        "stage17-operational-evidence-envelope-v5.schema.json",
        "stage17-read-only-preflight-authorization-v5.schema.json",
        "stage17-read-only-preflight-supporting-contract-v5.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v3.schema.json",
        "stage17-read-only-preflight-attempt-v3.schema.json",
        "stage17-read-only-preflight-observation-receipt-v2.schema.json",
        "stage17-read-only-preflight-failure-v3.schema.json",
        "stage17-read-only-preflight-completion-v2.schema.json",
        "stage17-operational-evidence-admission-policy-v6.schema.json",
        "stage17-operational-evidence-envelope-v6.schema.json",
        "stage17-read-only-preflight-authorization-v6.schema.json",
        "stage17-read-only-preflight-supporting-contract-v6.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v4.schema.json",
        "stage17-read-only-preflight-attempt-v4.schema.json",
        "stage17-read-only-preflight-observation-receipt-v3.schema.json",
        "stage17-read-only-preflight-failure-v4.schema.json",
        "stage17-read-only-preflight-completion-v3.schema.json",
        "stage17-operational-evidence-admission-policy-v7.schema.json",
        "stage17-operational-evidence-envelope-v7.schema.json",
        "stage17-read-only-preflight-authorization-v7.schema.json",
        "stage17-read-only-preflight-supporting-contract-v7.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v5.schema.json",
        "stage17-read-only-preflight-attempt-v5.schema.json",
        "stage17-read-only-preflight-observation-receipt-v4.schema.json",
        "stage17-read-only-preflight-failure-v5.schema.json",
        "stage17-read-only-preflight-completion-v4.schema.json",
        "stage17-operational-evidence-admission-policy-v8.schema.json",
        "stage17-operational-evidence-envelope-v8.schema.json",
        "stage17-read-only-preflight-authorization-v8.schema.json",
        "stage17-read-only-preflight-supporting-contract-v8.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v6.schema.json",
        "stage17-read-only-preflight-attempt-v6.schema.json",
        "stage17-read-only-preflight-observation-receipt-v5.schema.json",
        "stage17-read-only-preflight-failure-v6.schema.json",
        "stage17-read-only-preflight-failure-retention-v1.schema.json",
        "stage17-read-only-preflight-completion-v5.schema.json",
        "stage17-operational-evidence-admission-policy-v9.schema.json",
        "stage17-operational-evidence-envelope-v9.schema.json",
        "stage17-read-only-preflight-fixed-action-plan-v7.schema.json",
        "stage17-read-only-preflight-attempt-v7.schema.json",
        "stage17-operational-input-manifest-v1.schema.json",
        "stage17-phase-action-authorization-v1.schema.json",
        "stage17-fixed-action-request-v1.schema.json",
        "stage17-phase-action-result-v1.schema.json",
        "stage17-phase-action-evidence-v1.schema.json",
        "stage17-pilot-exit-record-v1.schema.json",
        "stage17-pilot-exit-journal-v1.schema.json",
        "stage17-pilot-attempt-v1.schema.json",
        "stage17-pilot-receipt-v1.schema.json",
        "stage17-pilot-failure-v1.schema.json",
        "stage17-pilot-completion-v1.schema.json",
        "stage17-sealed-pilot-artifact-manifest-v1.schema.json",
        "stage17-completion-statement-v1.schema.json",
        "stage17-treatment-blind-freeze-v1.schema.json",
        "phase18-access-journal-v1.schema.json",
        "phase18-readiness-report-v1.schema.json",
        "phase18-authorization-draft-v1.schema.json",
        "stage17-operational-evidence-admission-policy-v12.schema.json",
        "stage17-operational-evidence-admission-policy-v13.schema.json",
        "stage17-operational-evidence-envelope-v10.schema.json",
        "stage17-read-only-preflight-authorization-v9.schema.json",
        "stage17-read-only-preflight-supporting-contract-v9.schema.json",
        "stage17-read-only-preflight-evidence-admission-policy-v10.schema.json",
        "stage17-operational-evidence-admission-policy-v14.schema.json",
        "stage17-operational-evidence-envelope-v11.schema.json",
        "stage17-read-only-preflight-evidence-admission-policy-v11.schema.json",
        "stage17-operational-input-manifest-v4.schema.json",
        "stage17-operational-artifact-v4.schema.json",
        "stage17-phase-action-authorization-v4.schema.json",
        "stage17-fixed-action-request-v4.schema.json",
        "stage17-fixed-action-context-v4.schema.json",
        "stage17-phase-action-attempt-v4.schema.json",
        "stage17-phase-action-result-v4.schema.json",
        "stage17-phase-action-failure-v4.schema.json",
        "stage17-phase-action-completion-v4.schema.json",
        "stage17-fixed-phase-actions-v4.schema.json",
        "stage17-runtime-release-provenance-v4.schema.json",
        "stage17-pilot-candidate-external-contract-v4.schema.json",
        "stage17-pilot-plan-v4.schema.json",
        "stage17-pilot-run-attempt-v1.schema.json",
        "stage17-pilot-run-completion-v1.schema.json",
        "stage17-pilot-run-failure-v1.schema.json",
        "stage17-pilot-session-completion-v1.schema.json",
        "stage17-pilot-hardware-state-v2.schema.json",
        "stage17-sealed-pilot-artifact-manifest-v4.schema.json",
        "stage17-completion-v4.schema.json",
        "phase18-external-trust-anchor-v4.schema.json",
        "phase18-readiness-v4.schema.json",
        "phase18-authorization-v4.schema.json",
        "phase18-access-transition-v4.schema.json",
        "runner-admission-v4.schema.json",
        "phase-integrity-report-v2.schema.json",
    )
    for filename in semantic_admission_schema_paths:
        schema = json.loads(
            (root / "config/schemas" / filename).read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
    schemas = {
        version: json.loads(
            (root / f"config/schemas/stage17-authorization-v{version}.schema.json").read_text(
                encoding="utf-8"
            )
        )
        for version in (1, 2)
    }
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
    validators = {
        version: Draft202012Validator(schema) for version, schema in schemas.items()
    }
    validator = validators[2]
    if args.document is not None:
        try:
            document = json.loads(args.document.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"stage17-authorization-check: FAIL: {error}", file=sys.stderr)
            return 1
        if not isinstance(document, dict):
            print(
                "stage17-authorization-check: FAIL: document root must be an object",
                file=sys.stderr,
            )
            return 1
        schema_version = document.get("schema_version")
        if (
            schema_version == "cpu-prefetch-stage17-authorization/2"
            and document.get("phase") == "STAND_QUALIFICATION"
        ):
            print(
                "stage17-authorization-check: FAIL: ADR-0051 supersedes new omnibus "
                "Q15 requests; use split Q15-R/Q15-W records",
                file=sys.stderr,
            )
            return 1
        selected = {
            "cpu-prefetch-stage17-authorization/1": validators[1],
            "cpu-prefetch-stage17-authorization/2": validators[2],
        }.get(schema_version)
        errors = (["unsupported authorization schema version"] if selected is None else
                  validation_errors(selected, document))
        if errors:
            for error in errors:
                print(f"stage17-authorization-check: FAIL: {error}", file=sys.stderr)
            return 1
        print(
            "stage17-authorization-check: PASS "
            f"phase={document['phase']} authority=VALIDATED_NOT_ISSUED"
        )
        return 0

    legacy = base("STAND_QUALIFICATION")
    legacy["schema_version"] = "cpu-prefetch-stage17-authorization/1"
    legacy["runner_profile_id"] = "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v2"
    validators[1].validate(legacy)
    superseded_q15 = base("STAND_QUALIFICATION")
    validator.validate(superseded_q15)
    if not semantic_errors(superseded_q15):
        print(
            "stage17-authorization-check: FAIL: omnibus v2 Q15 was not superseded",
            file=sys.stderr,
        )
        return 1
    positives = [base(phase) for phase in EXECUTION_PHASES]
    for document in positives:
        validator.validate(document)
        if errors := semantic_errors(document):
            print(f"stage17-authorization-check: FAIL: positive: {errors}", file=sys.stderr)
            return 1

    negatives: list[dict[str, Any]] = []
    omnibus = copy.deepcopy(superseded_q15)
    omnibus["phase"] = "ALL_STAGE17"
    negatives.append(omnibus)
    wildcard = copy.deepcopy(superseded_q15)
    wildcard["permitted_commands"][0]["exact_target"] = "*"
    negatives.append(wildcard)
    overlap = copy.deepcopy(superseded_q15)
    overlap["authorities"]["auditor"] = overlap["authorities"]["operator"]
    negatives.append(overlap)
    inverted_time = copy.deepcopy(superseded_q15)
    inverted_time["expires_at_utc"] = inverted_time["issued_at_utc"]
    negatives.append(inverted_time)
    scientific_q15 = copy.deepcopy(positives[0])
    scientific_q15["phase"] = "STAND_QUALIFICATION"
    negatives.append(scientific_q15)
    missing_predecessor = copy.deepcopy(positives[1])
    missing_predecessor["phase_inputs"]["predecessor_artifacts"] = []
    negatives.append(missing_predecessor)
    wrong_count = copy.deepcopy(positives[2])
    wrong_count["phase_inputs"]["permitted_run_count"] = 2
    negatives.append(wrong_count)
    confirmatory = copy.deepcopy(positives[3])
    confirmatory["phase_inputs"]["namespaces"] = ["confirmatory-forbidden"]
    negatives.append(confirmatory)
    authority = copy.deepcopy(positives[0])
    authority["prohibitions"]["confirmatory_execution"] = True
    negatives.append(authority)

    for index, document in enumerate(negatives):
        schema_errors = list(validator.iter_errors(document))
        if not schema_errors and not semantic_errors(document):
            print(
                f"stage17-authorization-check: FAIL: negative fixture {index} passed",
                file=sys.stderr,
            )
            return 1
    print(
        "stage17-authorization-check: PASS "
        "(1 legacy + 4 current execution positive, 1 superseded Q15, 9 negative, "
        f"{len(semantic_admission_schema_paths)} semantic-admission schemas, "
        "no authority issued)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
