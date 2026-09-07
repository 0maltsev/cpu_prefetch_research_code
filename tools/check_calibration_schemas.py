#!/usr/bin/env python3
"""Validate the five implementation-owned Stage 13 record contracts."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


SHA256 = "0" * 64


def artifact(identifier: str) -> dict[str, str]:
    return {"artifact_id": identifier, "sha256": SHA256}


def rational(numerator: int, denominator: int) -> dict[str, str]:
    return {"numerator": str(numerator), "denominator": str(denominator)}


def documents() -> dict[str, dict[str, object]]:
    plan = {
        "schema_version": "cpu-prefetch-calibration-plan/1",
        "protocol_version": "2.0.0-pre.2",
        "record_id": "synthetic-service-plan",
        "plan_kind": "SERVICE_RATE",
        "estimator_id": "SERVICE-RATE-NP-LTL95C95-MIN-v1",
        "arithmetic_profile_id": None,
        "canonicalization_suite": "JCS-I64-v1",
        "seed_namespace_id": "synthetic-calibration",
        "assumptions": ["synthetic independent fixed-duration runs"],
        "owner_ids": ["synthetic-calibration-owner"],
        "authority": artifact("synthetic-authority"),
        "stand_budget": artifact("synthetic-stand-budget"),
        "planned_cells": [
            {
                "cell_id": "cell-000",
                "context_fingerprint_sha256": SHA256,
                "planned_run_ids": ["run-000"],
                "duration_ticks": "100",
                "minimum_observations_per_series": None,
            }
        ],
        "external_inputs": [
            {"name": "stand", "state": "UNRESOLVED", "artifact": None}
        ],
        "record_sha256": SHA256,
    }
    service_cell = {
        "cell_id": "cell",
        "state": "RESOLVED",
        "planned_runs": 59,
        "present_runs": 59,
        "valid_runs": 59,
        "run_decisions": [
            {
                "run_id": f"service-run-{index:02d}",
                "validity": "VALID",
                "consumed_events": "80",
                "interval_ticks": "100",
                "ticks_per_second": "100",
                "throughput": rational(80, 1),
                "raw_run_artifacts": [artifact(f"service-raw-{index:02d}")],
                "integrity_artifact": artifact(f"service-integrity-{index:02d}"),
                "failure_artifact": None,
            }
            for index in range(59)
        ],
        "mu_cell": rational(80, 1),
        "blockers": [],
    }
    service = {
        "schema_version": "cpu-prefetch-service-rate-result/1",
        "protocol_version": "2.0.0-pre.2",
        "record_id": "synthetic-service-result",
        "plan": artifact("synthetic-service-plan"),
        "estimator_id": "SERVICE-RATE-NP-LTL95C95-MIN-v1",
        "state": "RESOLVED",
        "assumptions": ["independent identically distributed run throughput"],
        "cells": [
            {
                **service_cell,
                "cell_id": f"cell-{cell_index:02d}",
                "run_decisions": [
                    {
                        **decision,
                        "run_id": f"service-{cell_index:02d}-{run_index:02d}",
                        "raw_run_artifacts": [
                            artifact(
                                f"service-raw-{cell_index:02d}-{run_index:02d}"
                            )
                        ],
                        "integrity_artifact": artifact(
                            f"service-integrity-{cell_index:02d}-{run_index:02d}"
                        ),
                    }
                    for run_index, decision in enumerate(
                        service_cell["run_decisions"]
                    )
                ],
            }
            for cell_index in range(60)
        ],
        "mu_ref": rational(80, 1),
        "candidate_loads": [rational(20, 1), rational(40, 1), rational(60, 1)],
        "record_sha256": SHA256,
    }
    ring_context = {
        "context_id": "context",
        "state": "RESOLVED",
        "run_decisions": [
            {
                "run_id": f"ring-run-{index:03d}",
                "hardware_state": "H0" if index < 59 else "H1",
                "validity": "VALID",
                "producer_demand_p999_ticks": "100",
                "consumer_demand_p999_ticks": "20",
                "producer_issue_p001_ticks": "4",
                "consumer_issue_p001_ticks": "4",
                "raw_run_artifacts": [artifact(f"ring-raw-{index:03d}")],
                "integrity_artifact": artifact(f"ring-integrity-{index:03d}"),
                "failure_artifact": None,
            }
            for index in range(118)
        ],
        "producer_demand_upper_ticks": "100",
        "consumer_demand_upper_ticks": "20",
        "producer_issue_lower_ticks": "4",
        "consumer_issue_lower_ticks": "4",
        "conservative_demand_ticks": "100",
        "conservative_issue_ticks": "4",
        "d1_slots": "8",
        "d2_cache_lines": "4",
        "producer_distance_slots": "32",
        "consumer_distance_slots": "32",
        "blockers": [],
    }
    ring = {
        "schema_version": "cpu-prefetch-ring-distance-result/1",
        "protocol_version": "2.0.0-pre.2",
        "record_id": "synthetic-ring-result",
        "plan": artifact("synthetic-ring-plan"),
        "estimator_id": "RING-D2-RUNTAIL-LTL95C95-v1",
        "state": "RESOLVED",
        "assumptions": ["marginal 95/95 run-level tolerance extremes"],
        "contexts": [
            {
                **ring_context,
                "context_id": f"ring-context-{context_index}",
                "run_decisions": [
                    {
                        **decision,
                        "run_id": f"ring-{context_index}-{run_index:03d}",
                        "raw_run_artifacts": [
                            artifact(
                                f"ring-raw-{context_index}-{run_index:03d}"
                            )
                        ],
                        "integrity_artifact": artifact(
                            f"ring-integrity-{context_index}-{run_index:03d}"
                        ),
                    }
                    for run_index, decision in enumerate(
                        ring_context["run_decisions"]
                    )
                ],
            }
            for context_index in range(6)
        ],
        "record_sha256": SHA256,
    }
    feasibility_cell = {
        "cell_id": "cell",
        "namespace_id": "synthetic-g1",
        "schedule": artifact("schedule"),
        "run_decisions": [
            {
                "run_id": "probe-run",
                "validity": "VALID",
                "offered_count": "100",
                "full_count": "0",
                "raw_run_artifact": artifact("probe"),
                "integrity_artifact": artifact("probe-integrity"),
                "failure_artifact": None,
            }
        ],
        "offered_count": "100",
        "full_count": "0",
        "sum_squared_weights": rational(1, 59),
        "p_hat": rational(0, 1),
        "p_upper": "0.2881578992302643",
        "simultaneous_alpha": rational(1, 18000),
    }
    feasibility = {
        "schema_version": "cpu-prefetch-zero-loss-feasibility-result/1",
        "protocol_version": "2.0.0-pre.2",
        "record_id": "synthetic-feasibility",
        "plan": artifact("synthetic-feasibility-plan"),
        "estimator_id": "MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1",
        "arithmetic_profile_id": "HOEFFDING-DECIMAL80-GUARD160-UP-v1",
        "python_runtime": "3.14.5",
        "state": "EVALUATED",
        "assumptions": [
            "independent run clusters and common per-cell candidate marginal"
        ],
        "confidence": rational(19, 20),
        "acceptance_threshold": rational(19, 20),
        "candidate_index": 0,
        "global_scale": rational(1, 1),
        "planned_blocks": 1,
        "planned_runs": 180,
        "planned_offered_events": "18000",
        "cells": [
            {
                **feasibility_cell,
                "cell_id": f"cell-{index:03d}",
                "schedule": artifact(f"schedule-{index:03d}"),
                "run_decisions": [
                    {
                        **feasibility_cell["run_decisions"][0],
                        "run_id": f"probe-run-{index:03d}",
                        "raw_run_artifact": artifact(f"probe-{index:03d}"),
                        "integrity_artifact": artifact(
                            f"probe-integrity-{index:03d}"
                        ),
                    }
                ],
            }
            for index in range(180)
        ],
        "matrix_probability_lower": "0",
        "passes": False,
        "blockers": [],
        "record_sha256": SHA256,
    }
    freeze = {
        "schema_version": "cpu-prefetch-calibration-freeze/1",
        "protocol_version": "2.0.0-pre.2",
        "record_id": "synthetic-not-evaluated-freeze",
        "state": "NOT_EVALUATED",
        "owner_ids": ["synthetic-calibration-owner"],
        "authority": None,
        "decided_at_utc": None,
        "source_records": [artifact("synthetic-service-plan")],
        "invalidation_fingerprint_sha256": SHA256,
        "proposed_outputs": [],
        "unresolved_inputs": ["stand evidence", "durations and run plan"],
        "supersedes_record_id": None,
        "record_sha256": SHA256,
    }
    return {
        "calibration-plan-v1.schema.json": plan,
        "service-rate-result-v1.schema.json": service,
        "ring-distance-result-v1.schema.json": ring,
        "zero-loss-feasibility-result-v1.schema.json": feasibility,
        "calibration-freeze-v1.schema.json": freeze,
    }


def must_reject(validator: Draft202012Validator, value: dict[str, object]) -> None:
    try:
        validator.validate(value)
    except ValidationError:
        return
    raise ValueError("negative Stage 13 fixture unexpectedly passed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    fixtures = documents()
    negative_count = 0
    for filename, document in fixtures.items():
        schema = json.loads(
            (args.source_root / "config" / "schemas" / filename).read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        validator.validate(document)

        wrong_version = copy.deepcopy(document)
        wrong_version["protocol_version"] = "2.0.0-pre.1"
        must_reject(validator, wrong_version)
        negative_count += 1

        extra = copy.deepcopy(document)
        extra["invented_freeze_output"] = 1
        must_reject(validator, extra)
        negative_count += 1

    unresolved = copy.deepcopy(fixtures["calibration-plan-v1.schema.json"])
    unresolved["external_inputs"][0]["artifact"] = artifact("fabricated")  # type: ignore[index]
    schema = json.loads(
        (
            args.source_root
            / "config"
            / "schemas"
            / "calibration-plan-v1.schema.json"
        ).read_text(encoding="utf-8")
    )
    must_reject(Draft202012Validator(schema), unresolved)
    negative_count += 1

    unresolved_freeze = copy.deepcopy(
        fixtures["calibration-freeze-v1.schema.json"]
    )
    unresolved_freeze["state"] = "FROZEN"
    must_reject(
        Draft202012Validator(
            json.loads(
                (
                    args.source_root
                    / "config"
                    / "schemas"
                    / "calibration-freeze-v1.schema.json"
                ).read_text(encoding="utf-8")
            )
        ),
        unresolved_freeze,
    )
    negative_count += 1

    unresolved_feasibility = copy.deepcopy(
        fixtures["zero-loss-feasibility-result-v1.schema.json"]
    )
    unresolved_feasibility["state"] = "NOT_EVALUATED"
    unresolved_feasibility["cells"] = []
    unresolved_feasibility["planned_blocks"] = 0
    unresolved_feasibility["planned_runs"] = 0
    unresolved_feasibility["planned_offered_events"] = "0"
    unresolved_feasibility["matrix_probability_lower"] = None
    unresolved_feasibility["passes"] = None
    unresolved_feasibility["blockers"] = ["stand probe evidence absent"]
    feasibility_validator = Draft202012Validator(
        json.loads(
            (
                args.source_root
                / "config"
                / "schemas"
                / "zero-loss-feasibility-result-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
    )
    feasibility_validator.validate(unresolved_feasibility)

    dishonest_partial = copy.deepcopy(unresolved_feasibility)
    dishonest_partial["blockers"] = []
    must_reject(feasibility_validator, dishonest_partial)
    negative_count += 1

    dishonest_service = copy.deepcopy(
        fixtures["service-rate-result-v1.schema.json"]
    )
    dishonest_service["cells"][0]["mu_cell"] = None  # type: ignore[index]
    service_validator = Draft202012Validator(
        json.loads(
            (
                args.source_root
                / "config"
                / "schemas"
                / "service-rate-result-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
    )
    must_reject(service_validator, dishonest_service)
    negative_count += 1

    dishonest_ring = copy.deepcopy(
        fixtures["ring-distance-result-v1.schema.json"]
    )
    dishonest_ring["contexts"][0]["d2_cache_lines"] = None  # type: ignore[index]
    ring_validator = Draft202012Validator(
        json.loads(
            (
                args.source_root
                / "config"
                / "schemas"
                / "ring-distance-result-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
    )
    must_reject(ring_validator, dishonest_ring)
    negative_count += 1

    invalid_evaluated_probe = copy.deepcopy(
        fixtures["zero-loss-feasibility-result-v1.schema.json"]
    )
    invalid_run = invalid_evaluated_probe["cells"][0]["run_decisions"][0]  # type: ignore[index]
    invalid_run["validity"] = "INVALID"
    invalid_run["raw_run_artifact"] = None
    invalid_run["integrity_artifact"] = None
    invalid_run["failure_artifact"] = artifact("probe-failure")
    must_reject(feasibility_validator, invalid_evaluated_probe)
    negative_count += 1

    positive_count = len(fixtures) + 1
    print(
        "calibration-schema-check: PASS "
        f"({positive_count} positive, {negative_count} negative Draft 2020-12 cases)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
