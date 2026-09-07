#!/usr/bin/env python3
"""Validate the implementation-owned Q13 admission schema and fixtures."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


KINDS = [
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


def fixture() -> dict[str, object]:
    zero_hash = "0" * 64
    return {
        "schema_version": "cpu-prefetch-runner-admission/1",
        "protocol_version": "2.0.0-pre.2",
        "runner_profile_id": "STAGE17-STATIC-FIVE-PACKAGE-FAIL-CLOSED-v1",
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
        "execution_limits": {
            "controller_start_poll_limit": 1,
            "worker_start_poll_limit": 1,
            "producer_due_poll_limit_per_arrival": 1,
            "consumer_empty_poll_limit_before_finish": 1,
            "drain_poll_limit": 1,
        },
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
            for index, kind in enumerate(KINDS)
        ],
    }


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    schema_path = root / "config" / "schemas" / "runner-admission-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    valid = fixture()
    validator.validate(valid)

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
    for index, document in enumerate(invalids):
        if not list(validator.iter_errors(document)):
            print(f"runner-schema-check: FAIL: invalid fixture {index} passed", file=sys.stderr)
            return 1
    print("runner-schema-check: PASS (Draft 2020-12; 1 positive, 4 negative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
