#!/usr/bin/env python3
"""Draft 2020-12 conformance fixtures for every imported protocol snapshot."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

VERSIONS = ("2.0.0-pre.1", "2.0.0-pre.2")
VERSION = VERSIONS[0]
HASH = "0" * 64


def artifact(name: str) -> dict[str, Any]:
    return {"artifact_id": name, "sha256": HASH}


def block_plan(replacement: bool = False) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    ordinal = 0
    for package in ("R0", "R1", "R2", "L0", "L1"):
        for hardware in ("H0", "H1"):
            for placement in ("NEAR", "FAR"):
                for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"):
                    for load in ("L025", "L050", "L075"):
                        cells.append(
                            {
                                "cell_ordinal": ordinal,
                                "package": package,
                                "requested_hardware_state": hardware,
                                "placement": placement,
                                "working_set_class": working_set,
                                "load_level": load,
                                "arrival_seed_ref": f"arrival-{ordinal}",
                                "node_seed_ref": (
                                    f"node-{ordinal}" if package.startswith("L") else None
                                ),
                                "event_seed_ref": f"event-{ordinal}",
                            }
                        )
                        ordinal += 1
    record: dict[str, Any] = {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "block_id": "block-replacement" if replacement else "block-original",
        "platform_id": "platform-fixture",
        "build_id": "build-fixture",
        "stage": "STAGE_A",
        "block_role": "H3_TRAIN",
        "block_ordinal": 2 if replacement else 1,
        "seed_subspace_id": "subspace-replacement" if replacement else "subspace-original",
        "replaces_block_id": "block-original" if replacement else None,
        "replacement_authorization_id": "replacement-auth" if replacement else None,
        "replacement_lineage": (
            {
                "replaced_block_ordinal": 1,
                "replaced_block_role": "H3_TRAIN",
                "replaced_seed_subspace_id": "subspace-original",
            }
            if replacement
            else None
        ),
        "whole_plot_order": ["H0", "H1"],
        "cells": cells,
        "access_state": "PLANNED",
        "plan_sha256": HASH,
    }
    return record


def integrity() -> dict[str, Any]:
    checksum = {
        "algorithm_record_id": "algorithm-record",
        "algorithm_version": "unresolved-test-fixture",
        "value_hex": "00",
    }
    return {
        "report_artifact": artifact("integrity-report"),
        "final_consumer_rolling_checksum": copy.deepcopy(checksum),
        "event_records_pre_checksum": copy.deepcopy(checksum),
        "event_records_post_checksum": copy.deepcopy(checksum),
        "ordered_index_checksum": copy.deepcopy(checksum),
        "address_delta_checksum": copy.deepcopy(checksum),
    }


def manifest(
    *, full: int = 0, n_eff: int = 200_000, early_failure: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "run_id": "run-fixture",
        "platform_id": "platform-fixture",
        "build_id": "build-fixture",
        "within_cell_ordinal": 0,
        "queue_provenance_id": "queue-provenance",
        "provenance": {
            "paper_repository_revision": "paper-revision",
            "implementation_repository_revision": "implementation-revision",
            "build_artifact_sha256": HASH,
            "compiler_identity": "compiler-fixture",
            "compiler_flags": [],
            "standard_library": "stdlib-fixture",
            "dependency_record_id": "dependency-record",
        },
        "stage": "STAGE_A",
        "run_mode": "LATENCY",
        "lifecycle_state": "PRE_RUN_FAILURE" if early_failure else "COMPLETED",
        "block_id": "block-original",
        "block_role": "H3_TRAIN",
        "package": "R0",
        "requested_hardware_state": "H0",
        "verified_hardware_state": "VERIFIED_DEFAULT",
        "placement": "NEAR",
        "working_set_class": "L2_RESIDENT",
        "load_level": "L025",
        "capacity_events": 64,
        "time_unit": "candidate_ticks",
        "schedule_refs": {
            "measurement": artifact("measurement-schedule"),
            "warmup": artifact("warmup-schedule"),
        },
        "seed_refs": {
            "arrival": "arrival-seed",
            "node_order": None,
            "event_order": "event-seed",
            "warmup": "warmup-seed",
            "derivation_record_id": "derivation-record",
        },
        "validity": "INVALID" if early_failure else "VALID",
        "count_reconciliation": "NOT_EVALUATED" if early_failure else "PASS",
        "zero_loss_status": "NOT_EVALUATED" if early_failure else ("FAIL" if full else "PASS"),
        "effective_tail_status": (
            "NOT_EVALUATED" if early_failure else ("PASS" if n_eff >= 200_000 else "FAIL")
        ),
        "confirmatory_estimability": (
            "BLOCKED_INVALID_RUN"
            if early_failure
            else (
                "BLOCKED_ZERO_LOSS"
                if full
                else ("ESTIMABLE" if n_eff >= 200_000 else "BLOCKED_EFFECTIVE_TAIL")
            )
        ),
        "block_completeness": "INCOMPLETE" if early_failure else "COMPLETE",
        "join_status": "NOT_ATTEMPTED" if early_failure else "PASSED",
        "failure_record_ids": ["failure-record"] if early_failure else [],
        "artifact_refs": [],
        "manifest_sha256": HASH,
    }
    if VERSION == "2.0.0-pre.2":
        blockers: list[str] = []
        if not early_failure:
            if n_eff < 200_000:
                blockers.append("BLOCKED_EFFECTIVE_TAIL")
            if full:
                blockers.append("BLOCKED_ZERO_LOSS")
        result["confirmatory_blockers"] = blockers
        if early_failure:
            result["confirmatory_estimability"] = "NOT_EVALUATED"
        elif len(blockers) > 1:
            result["confirmatory_estimability"] = "BLOCKED_MULTIPLE"
        elif blockers:
            result["confirmatory_estimability"] = blockers[0]
        else:
            result["confirmatory_estimability"] = "ESTIMABLE"
    if not early_failure:
        accepted = 10 - full
        result["counts"] = {
            "offered": 10,
            "attempted": 10,
            "accepted": accepted,
            "full": full,
            "consumed": accepted,
            "final_occupancy": 0,
            "raw_sample_count": accepted,
            "n_eff_p999": n_eff,
        }
        result["integrity_evidence"] = integrity()
        result["artifact_refs"] = [
            {**artifact("producer"), "relationship": "PRODUCER_RAW"},
            {**artifact("consumer"), "relationship": "CONSUMER_RAW"},
            {**artifact("join-audit"), "relationship": "JOIN_AUDIT"},
            {**artifact("joined"), "relationship": "JOINED_DERIVED"},
            {**artifact("integrity-report"), "relationship": "PHASE_INTEGRITY_REPORT"},
            {**artifact("provenance"), "relationship": "PROVENANCE"},
        ]
    return result


def raw_observation(outcome: str = "ACCEPTED") -> dict[str, Any]:
    row: dict[str, Any] = {
        "run_id": "run-fixture",
        "logical_sequence": 0,
        "record_index": 0,
        "scheduled_arrival": 10,
        "producer_handle_begin": 11,
        "record_lookup_completion": 12,
        "enqueue_invocation": 13,
        "enqueue_attempt_completion": 15,
        "attempted": True,
        "outcome": outcome,
    }
    if outcome == "ACCEPTED":
        row["enqueue_linearization"] = 14
        row["accepted_ordinal"] = 0
    return {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "artifact_id": "producer-artifact",
        "run_id": "run-fixture",
        "stream_kind": "PRODUCER",
        "logical_row_schema_version": VERSION,
        "physical_format_record_id": "inline-test-format",
        "encoding": "INLINE_TEST_JSON",
        "time_unit": "candidate_ticks",
        "endianness": "NOT_APPLICABLE",
        "compression": "NONE",
        "row_count": 1,
        "byte_count": 0,
        "immutable_ordering": True,
        "storage": {"mode": "INLINE_TEST_ONLY", "inline_rows": [row]},
        "integrity_artifact_ref": artifact("integrity-report"),
        "artifact_sha256": HASH,
    }


def schedule() -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "schedule_id": "schedule-fixture",
        "schedule_kind": "CONFIRMATORY",
        "arrival_family": "POISSON_EXPONENTIAL",
        "namespace_id": "namespace-fixture",
        "rng": {
            "algorithm": "unresolved-test-fixture",
            "version": "test-only",
            "seed_id": "seed-fixture",
            "derivation_record_id": "derivation-record",
            "parent_namespace_id": "parent-namespace",
        },
        "time_unit": "candidate_ticks",
        "deadline_encoding": "ABSOLUTE_INTEGER_TICKS",
        "origin_ticks": 100,
        "horizon_ticks": 100,
        "inclusion_boundary": {"start_inclusive": True, "end_exclusive": True},
        "offered_count": 2,
        "nominal_offered_rate": {"numerator_events": 1, "denominator_ticks": 10},
        "overflow_rule_record_id": "overflow-rule",
        "immutable_ordering": True,
        "deadline_storage": {"mode": "INLINE_TEST_ONLY", "deadline_ticks": [110, 120]},
        "decoded_deadlines_sha256": HASH,
        "schedule_sha256": HASH,
    }


def platform() -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "platform_id": "platform-fixture",
        "cpu": {
            "vendor": "fixture",
            "model": "fixture",
            "stepping": "fixture",
            "microcode": "fixture",
            "cache_line_bytes": 64,
            "atomic_width_bits": 64,
            "atomic_alignment_bytes": 8,
        },
        "topology": {
            "sockets": 1,
            "numa_nodes": 2,
            "physical_cores": 4,
            "smt_enabled": False,
            "cache_domains": ["cache-domain"],
            "near_core_pair": [0, 1],
            "far_core_pair": [0, 2],
        },
        "memory": {
            "population": "fixture",
            "base_page_bytes": 4096,
            "residency_verification_method": "fixture",
        },
        "software": {
            "operating_system": "Linux",
            "kernel": "fixture",
            "compiler": "fixture",
            "standard_library": "fixture",
            "language_standard": "C++20",
            "flags": [],
            "link_mode": "fixture",
        },
        "clock": {
            "source": "candidate-only",
            "time_unit": "candidate_ticks",
            "conversion_record_id": "clock-conversion",
            "serialization_record_id": "clock-serialization",
            "acceptance_record_id": "clock-acceptance",
        },
        "hardware_prefetch_states": [
            {
                "requested": requested,
                "verified": verified,
                "readback_artifact_id": f"readback-{requested}",
                "behavioral_probe_artifact_id": f"probe-{requested}",
                "privileged_authority_id": "platform-operator",
            }
            for requested, verified in (("H0", "VERIFIED_DEFAULT"), ("H1", "VERIFIED_CHANGED"))
        ],
        "record_sha256": HASH,
    }


def failure_record() -> dict[str, Any]:
    return {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "failure_record_id": "failure-record",
        "platform_id": "platform-fixture",
        "stage": "STAGE_A",
        "scope": "RUN",
        "run_id": "run-fixture",
        "block_id": "block-original",
        "build_id": "build-fixture",
        "category": "CORRECTNESS",
        "detected_phase": "PRE_RUN",
        "observed_at_utc": "2026-08-17T00:00:00Z",
        "description": "synthetic conformance fixture",
        "invalidates_run": True,
        "block_consequence": "ORIGINAL_BLOCK_INCOMPLETE",
        "resolution_status": "OPEN",
        "replacement_authorization_id": None,
        "replacement_block_id": None,
        "supersedes_id": None,
        "evidence_refs": [artifact("failure-evidence")],
        "record_sha256": HASH,
    }


CONTEXTS = (
    "NEAR_L2_L050",
    "NEAR_LLC_L050",
    "NEAR_BEYOND_LLC_L050",
    "FAR_L2_L050",
    "FAR_LLC_L050",
    "FAR_BEYOND_LLC_L050",
)


def freeze_record(kind: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": VERSION,
        "protocol_version": VERSION,
        "record_id": f"freeze-{kind.lower()}",
        "record_kind": kind,
        "decision_id": "decision-fixture",
        "readiness_boundary": "BLOCKED_BEFORE_CONFIRMATORY_EXECUTION",
        "status": "OPEN",
        "authorization_status": "NOT_APPLICABLE",
        "created_at_utc": "2026-08-17T00:00:00Z",
        "authority": {
            "authority_id": "authority-fixture",
            "role": "PROTOCOL_OWNER",
            "attestation": "synthetic conformance fixture",
            "signature_artifact_id": None,
        },
        "access_state_before": "PLANNED",
        "access_state_after": "PLANNED",
        "outcome_access_prohibited": True,
        "input_artifacts": [
            {**artifact("input-artifact"), "access_class": "PUBLIC_PROTOCOL"}
        ],
        "record_sha256": HASH,
    }
    if kind == "SELECTION_FREEZE":
        record.update(
            status="FROZEN",
            authorization_status="AUTHORIZED",
            authority={**record["authority"], "role": "FREEZE_AUTHORITY"},
            access_state_before="TRAINING_OPEN",
            access_state_after="SELECTION_FROZEN",
            affected_block_ids=["training-block"],
            h3_selections={
                context: {"package": "R0", "requested_hardware_state": "H0"}
                for context in CONTEXTS
            },
            training_input_artifacts=[artifact("training-input")],
            selection_rule_version=VERSION,
            selection_record_checksum_sha256=HASH,
        )
    elif kind == "VALIDATION_UNSEAL":
        record.update(
            status="AUTHORIZED",
            authorization_status="AUTHORIZED",
            authority={**record["authority"], "role": "VALIDATION_CUSTODIAN"},
            access_state_before="SELECTION_FROZEN",
            access_state_after="VALIDATION_UNSEALED",
            outcome_access_prohibited=False,
            affected_block_ids=["validation-block"],
            selection_record_ref=artifact("selection-record"),
            validation_namespace_id="validation-namespace",
            validation_artifact_ref=artifact("validation-artifact"),
        )
    elif kind == "H3_EVALUATED":
        record.update(
            status="FROZEN",
            authorization_status="AUTHORIZED",
            authority={**record["authority"], "role": "CONFIRMATORY_ANALYST"},
            access_state_before="VALIDATION_UNSEALED",
            access_state_after="H3_EVALUATED",
            outcome_access_prohibited=False,
            affected_block_ids=["validation-block"],
            h3_evaluation_artifact_ref=artifact("h3-evaluation"),
            selection_record_ref=artifact("selection-record"),
            validation_namespace_id="validation-namespace",
            validation_artifact_ref=artifact("validation-artifact"),
            validation_unseal_record_ref=artifact("unseal-record"),
        )
    elif kind == "H1H2_RELEASED":
        record.update(
            status="AUTHORIZED",
            authorization_status="AUTHORIZED",
            authority={**record["authority"], "role": "VALIDATION_CUSTODIAN"},
            access_state_before="H3_EVALUATED",
            access_state_after="H1H2_RELEASED",
            outcome_access_prohibited=False,
            affected_block_ids=["stage-a-block"],
            h3_access_record_ref=artifact("h3-access"),
            h3_evaluation_artifact_ref=artifact("h3-evaluation"),
        )
    elif kind == "REPLACEMENT_AUTHORIZATION":
        record.update(
            status="AUTHORIZED",
            authorization_status="AUTHORIZED",
            authority={**record["authority"], "role": "REPLACEMENT_AUTHORITY"},
            affected_block_ids=["block-original"],
            replacement={
                "original_block_id": "block-original",
                "replacement_block_id": "block-replacement",
                "replacement_block_ordinal": 2,
                "block_role": "H3_TRAIN",
                "replacement_seed_subspace_id": "subspace-replacement",
                "failure_record_id": "failure-record",
                "replacement_budget_record_id": "replacement-budget",
            },
        )
    elif kind == "AMENDMENT":
        record.update(
            status="FROZEN",
            authorization_status="AUTHORIZED",
            rationale="synthetic conformance fixture",
            supersedes_id="prior-freeze",
            prior_protocol_version="2.0.0-pre.0",
            new_protocol_version=VERSION,
            affected_documents=["document"],
            affected_schema_ids=["schema"],
            affected_estimands=["estimand"],
            affected_contrast_ids=[],
            pilot_record_disposition="no pilot data",
            prior_authoritative_hashes=[artifact("prior-authoritative")],
        )
    return record


def expect_valid(validator: Draft202012Validator, instance: dict[str, Any], name: str) -> None:
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise RuntimeError(f"{name}: expected valid; first error: {errors[0].message}")


def expect_invalid(validator: Draft202012Validator, instance: dict[str, Any], name: str) -> None:
    if not list(validator.iter_errors(instance)):
        raise RuntimeError(f"{name}: expected schema rejection")


def mutate(value: dict[str, Any], action: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    action(result)
    return result


def run_version(version: str) -> tuple[int, int, int]:
    global VERSION
    VERSION = version
    root = Path(__file__).resolve().parents[1]
    schema_dir = root / "protocol" / VERSION / "handoff" / "schemas"
    schemas = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in schema_dir.glob("*.schema.json")
    }
    validators = {
        name: Draft202012Validator(schema, format_checker=FormatChecker())
        for name, schema in schemas.items()
    }
    if len(validators) != 7:
        raise RuntimeError(f"expected seven schemas, found {len(validators)}")

    positives: list[tuple[str, dict[str, Any], str]] = [
        ("platform.schema.json", platform(), "platform"),
        ("schedule.schema.json", schedule(), "schedule"),
        ("raw-observation.schema.json", raw_observation(), "accepted producer row"),
        ("raw-observation.schema.json", raw_observation("FULL"), "FULL producer row"),
        ("run-manifest.schema.json", manifest(early_failure=True), "partial invalid manifest"),
        ("run-manifest.schema.json", manifest(full=1), "valid FULL manifest"),
        ("run-manifest.schema.json", manifest(n_eff=199_999), "valid low-N_eff manifest"),
        ("block-plan.schema.json", block_plan(), "original block"),
        ("block-plan.schema.json", block_plan(True), "replacement block"),
        ("failure-record.schema.json", failure_record(), "failure"),
    ]
    if VERSION == "2.0.0-pre.2":
        positives.append(
            (
                "run-manifest.schema.json",
                manifest(full=1, n_eff=199_999),
                "valid exhaustive simultaneous blockers",
            )
        )
    positives.extend(
        ("freeze-record.schema.json", freeze_record(kind), f"freeze {kind}")
        for kind in (
            "PROTOCOL_FREEZE",
            "SELECTION_FREEZE",
            "VALIDATION_UNSEAL",
            "H3_EVALUATED",
            "H1H2_RELEASED",
            "REPLACEMENT_AUTHORIZATION",
            "AMENDMENT",
        )
    )
    for schema_name, instance, name in positives:
        expect_valid(validators[schema_name], instance, name)

    negatives: list[tuple[str, dict[str, Any], str]] = []
    missing_artifact = manifest()
    missing_artifact["artifact_refs"] = [
        item for item in missing_artifact["artifact_refs"] if item["relationship"] != "JOINED_DERIVED"
    ]
    negatives.append(("run-manifest.schema.json", missing_artifact, "completed missing evidence"))
    bad_full = raw_observation("FULL")
    bad_full["storage"]["inline_rows"][0]["accepted_ordinal"] = 0
    negatives.append(("raw-observation.schema.json", bad_full, "FULL accepted ordinal"))
    bad_accepted = raw_observation()
    del bad_accepted["storage"]["inline_rows"][0]["enqueue_linearization"]
    negatives.append(("raw-observation.schema.json", bad_accepted, "accepted missing timestamp"))
    missing_context = freeze_record("SELECTION_FREEZE")
    del missing_context["h3_selections"][CONTEXTS[0]]
    negatives.append(("freeze-record.schema.json", missing_context, "missing H3 context"))
    extra_context = freeze_record("SELECTION_FREEZE")
    extra_context["h3_selections"]["DUPLICATE_ALIAS_CONTEXT"] = {
        "package": "R0",
        "requested_hardware_state": "H0",
    }
    negatives.append(("freeze-record.schema.json", extra_context, "extra H3 context"))
    missing_unseal_hash = freeze_record("VALIDATION_UNSEAL")
    del missing_unseal_hash["selection_record_ref"]["sha256"]
    negatives.append(("freeze-record.schema.json", missing_unseal_hash, "unseal missing hash"))
    empty_blocks = freeze_record("VALIDATION_UNSEAL")
    empty_blocks["affected_block_ids"] = []
    negatives.append(("freeze-record.schema.json", empty_blocks, "empty affected blocks"))
    unknown_version = schedule()
    unknown_version["protocol_version"] = "3.0.0"
    negatives.append(("schedule.schema.json", unknown_version, "unknown protocol version"))
    unknown_schema_version = schedule()
    unknown_schema_version["schema_version"] = "3.0.0"
    negatives.append(
        ("schedule.schema.json", unknown_schema_version, "unknown schema version")
    )
    unknown_enum = manifest(early_failure=True)
    unknown_enum["package"] = "FUTURE_QUEUE"
    negatives.append(("run-manifest.schema.json", unknown_enum, "unknown enum"))
    malformed_hash = platform()
    malformed_hash["record_sha256"] = "ABC"
    negatives.append(("platform.schema.json", malformed_hash, "malformed hash"))
    malformed_id = failure_record()
    malformed_id["failure_record_id"] = ""
    negatives.append(("failure-record.schema.json", malformed_id, "empty ID"))
    malformed_unit = schedule()
    malformed_unit["time_unit"] = ""
    negatives.append(("schedule.schema.json", malformed_unit, "empty unit"))
    invalid_cross_field = schedule()
    invalid_cross_field["arrival_family"] = "CONTINUOUS_READY"
    negatives.append(("schedule.schema.json", invalid_cross_field, "confirmatory family"))
    malformed_replacement = block_plan(True)
    malformed_replacement["replacement_authorization_id"] = None
    negatives.append(("block-plan.schema.json", malformed_replacement, "replacement combination"))
    if VERSION == "2.0.0-pre.2":
        missing_blockers = manifest()
        del missing_blockers["confirmatory_blockers"]
        negatives.append(
            ("run-manifest.schema.json", missing_blockers, "missing blocker array")
        )
        duplicate_blockers = manifest(full=1, n_eff=199_999)
        duplicate_blockers["confirmatory_blockers"] = [
            "BLOCKED_ZERO_LOSS",
            "BLOCKED_ZERO_LOSS",
        ]
        negatives.append(
            ("run-manifest.schema.json", duplicate_blockers, "duplicate blockers")
        )
    for schema_name, instance, name in negatives:
        expect_invalid(validators[schema_name], instance, name)

    return len(validators), len(positives), len(negatives)


def main() -> int:
    totals = [0, 0, 0]
    for version in VERSIONS:
        counts = run_version(version)
        totals = [left + right for left, right in zip(totals, counts)]
    print(
        "protocol-fixtures: PASS "
        f"({len(VERSIONS)} snapshots, {totals[0]} schemas, "
        f"{totals[1]} positive, {totals[2]} negative)"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f"protocol-fixtures: FAIL: {error}", file=sys.stderr)
        raise SystemExit(1) from error
