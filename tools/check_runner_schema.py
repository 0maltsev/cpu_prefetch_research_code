#!/usr/bin/env python3
"""Validate all implementation-owned runner admission schema generations."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


V1_KINDS = [
    "PROTOCOL_SNAPSHOT",
    "SOURCE_RELEASE",
    "RUN_PLAN",
    "WARMUP_SCHEDULE",
    "MEASUREMENT_SCHEDULE",
    "SEED_DERIVATION",
    "PLATFORM_INVENTORY",
    "PLATFORM_REQUEST",
    "PLATFORM_VERIFICATION",
    "HARDWARE_PREFETCH_MAPPING",
    "CLOCK_QUALIFICATION",
    "QUEUE_PROVENANCE",
    "RUNTIME_ATOMIC_LAYOUT",
    "ADDRESS_RESIDENCY",
    "STORAGE_BUDGET",
    "DURABILITY_DOMAINS",
    "CALIBRATION_FREEZE",
    "EXECUTION_LIMITS",
    "AUTHORITY_CUSTODY",
    "PILOT_EXECUTION_AUTHORIZATION",
]
V2_KINDS = [
    *V1_KINDS[:10],
    "SOFTWARE_PREFETCH_MAPPING",
    *V1_KINDS[10:-1],
    "PHASE_EXECUTION_AUTHORIZATION",
]


def fixture(version: int) -> dict[str, object]:
    zero_hash = "0" * 64
    kinds = V1_KINDS if version == 1 else V2_KINDS
    limits = {
        "controller_start_poll_limit": 1,
        "worker_start_poll_limit": 1,
    }
    if version < 3:
        limits.update(
            {
                "producer_due_poll_limit_per_arrival": 1,
                "consumer_empty_poll_limit_before_finish": 1,
                "drain_poll_limit": 1,
            }
        )
    return {
        "schema_version": f"cpu-prefetch-runner-admission/{version}",
        "protocol_version": "2.0.0-pre.2",
        "runner_profile_id": f"STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v{version}",
        "cpu_pair_selection_id": "XEON-CPU-FETCH-P0-NEAR-0-1-FAR-0-26-v1",
        "relax_mapping_id": "X86-PAUSE-ONE-PER-RELAX-SITE-v1",
        "source_revision": "SYNTHETIC",
        "binary_sha256": zero_hash,
        "stand_id": "SYNTHETIC-NOT-A-STAND",
        "binding_id": "SYNTHETIC-BINDING",
        "package": "R0",
        "placement": "NEAR",
        "producer_cpu": 0,
        "consumer_cpu": 1,
        "execution_limits": limits,
        "evidence": [
            {
                "kind": kind,
                "artifact_id": f"synthetic-{index}",
                "path": "synthetic.bin",
                "sha256": zero_hash,
                "binding_id": "SYNTHETIC-BINDING",
                "immutable": True,
                "eligible": True,
            }
            for index, kind in enumerate(kinds)
        ],
    }


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    validators: dict[int, Draft202012Validator] = {}
    for version in (1, 2, 3):
        schema_path = (
            root / "config" / "schemas" / f"runner-admission-v{version}.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validators[version] = Draft202012Validator(schema)
        validators[version].validate(fixture(version))

    validator = validators[3]
    valid = fixture(3)

    invalids: list[dict[str, object]] = []
    wrong_pair = copy.deepcopy(valid)
    wrong_pair["consumer_cpu"] = 26
    invalids.append(wrong_pair)
    mutable = copy.deepcopy(valid)
    mutable["evidence"][0]["immutable"] = False  # type: ignore[index]
    invalids.append(mutable)
    missing = copy.deepcopy(valid)
    missing["evidence"] = missing["evidence"][:-1]  # type: ignore[index]
    invalids.append(missing)
    unknown = copy.deepcopy(valid)
    unknown["extra"] = True
    invalids.append(unknown)
    legacy_under_v3 = fixture(2)
    invalids.append(legacy_under_v3)
    legacy_limits = copy.deepcopy(valid)
    legacy_limits["execution_limits"]["drain_poll_limit"] = 1  # type: ignore[index]
    invalids.append(legacy_limits)
    for index, document in enumerate(invalids):
        if not list(validator.iter_errors(document)):
            print(f"runner-schema-check: FAIL: invalid fixture {index} passed", file=sys.stderr)
            return 1
    print("runner-schema-check: PASS (Draft 2020-12; 3 positive, 6 negative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
