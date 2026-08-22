#!/usr/bin/env python3
"""Validate the Q14 qualification-evidence schema with synthetic fixtures."""

from __future__ import annotations

import copy
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


def base(kind: str, details: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": "cpu-prefetch-qualification-evidence/1",
        "protocol_version": "2.0.0-pre.2",
        "artifact_id": "SYNTHETIC-QUALIFICATION",
        "kind": kind,
        "stand_id": "SYNTHETIC-NOT-A-STAND",
        "binding_id": "SYNTHETIC-BINDING",
        "source_revision": "SYNTHETIC-REVISION",
        "binary_sha256": "0" * 64,
        "captured_at_utc": "2026-08-22T00:00:00Z",
        "producer_cpu": 0,
        "consumer_cpu": 1,
        "sources": [{"artifact_id": "SYNTHETIC-SOURCE", "sha256": "0" * 64}],
        "eligible": False,
        "details": details,
    }


def fixtures() -> list[dict[str, object]]:
    clock = {
        "producer_prime_read_count": 100000,
        "consumer_prime_read_count": 100000,
        "producer_delta_count": 10000000,
        "consumer_delta_count": 10000000,
        "traced_call_count": 10000000,
        "traced_syscall_count": 0,
        "producer_to_consumer_window_count": 3,
        "consumer_to_producer_window_count": 3,
        "exchanges_per_window": 100000,
        "per_core_evaluator_passed": True,
        "cross_core_evaluator_passed": True,
        "before_block_repeat": True,
    }
    atomics = {
        "pointer_atomic_width_bytes": 8,
        "pointer_atomic_alignment_bytes": 8,
        "termination_atomic_width_bytes": 4,
        "termination_atomic_alignment_bytes": 4,
        "cache_line_bytes": 64,
        "pointer_atomic_runtime_lock_free": True,
        "termination_atomic_runtime_lock_free": True,
        "queue_layout_passed": True,
        "ownership_lines_separated": True,
        "termination_dedicated_line": True,
    }
    cpu = {
        "producer_sample_count": 2,
        "consumer_sample_count": 2,
        "producer_first_cpu": 0,
        "producer_last_cpu": 0,
        "consumer_first_cpu": 1,
        "consumer_last_cpu": 1,
        "producer_migration_count": 0,
        "consumer_migration_count": 0,
        "producer_singleton_affinity": True,
        "consumer_singleton_affinity": True,
    }
    region = {
        "region": "SYNTHETIC",
        "expected_node": 0,
        "before_page_count": 1,
        "during_page_count": 1,
        "after_page_count": 1,
        "unavailable_page_count": 0,
        "wrong_node_page_count": 0,
        "migrated_page_count": 0,
    }
    residency = {
        "mechanism_id": "SYNTHETIC-MECHANISM",
        "shared_event_and_queue_pages": region,
        "producer_private_pages": region,
        "consumer_private_pages": region,
    }
    software_prefetch = {
        "mapping_id": "X86-64-PREFETCHW-PREFETCHT0-v1",
        "producer_maximum_extended_leaf": 0x80000008,
        "producer_extended_leaf_ecx": 0x121,
        "producer_prfchw_supported": True,
        "consumer_maximum_extended_leaf": 0x80000008,
        "consumer_extended_leaf_ecx": 0x121,
        "consumer_prfchw_supported": True,
        "ring_producer_instruction": "PREFETCHW",
        "ring_consumer_instruction": "PREFETCHT0",
        "linked_consumer_instruction": "PREFETCHT0",
        "gcc_codegen_passed": True,
        "clang_codegen_passed": True,
        "gnu_objdump_passed": True,
        "llvm_objdump_passed": True,
    }
    return [
        base("SELECTED_PAIR_CLOCK", clock),
        base("RUNTIME_ATOMIC_LAYOUT", atomics),
        base("ACTUAL_CPU_MIGRATION", cpu),
        base("ADDRESS_RESIDENCY", residency),
        base("SOFTWARE_PREFETCH_MAPPING", software_prefetch),
    ]


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    schema = json.loads(
        (root / "config/schemas/qualification-evidence-v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    valid = fixtures()
    for document in valid:
        validator.validate(document)

    invalids: list[dict[str, object]] = []
    unknown = copy.deepcopy(valid[0])
    unknown["unknown"] = True
    invalids.append(unknown)
    missing = copy.deepcopy(valid[1])
    del missing["details"]["queue_layout_passed"]  # type: ignore[index]
    invalids.append(missing)
    wrong_details = copy.deepcopy(valid[2])
    wrong_details["details"] = valid[0]["details"]
    invalids.append(wrong_details)
    wrong_mapping = copy.deepcopy(valid[4])
    wrong_mapping["details"]["ring_producer_instruction"] = "PREFETCHT0"  # type: ignore[index]
    invalids.append(wrong_mapping)
    for index, document in enumerate(invalids):
        if not list(validator.iter_errors(document)):
            print(
                f"qualification-schema-check: FAIL: invalid fixture {index} passed",
                file=sys.stderr,
            )
            return 1
    print("qualification-schema-check: PASS (5 synthetic positive, 4 negative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
