#!/usr/bin/env python3
"""Validate the accepted Q15-S3 software profile without executing it."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys

from jsonschema import Draft202012Validator


COLLECTORS = (
    "Q15-CLOCK-COLLECTOR-v1",
    "Q15-ATOMIC-LAYOUT-COLLECTOR-v1",
    "Q15-ACTUAL-CPU-MIGRATION-COLLECTOR-v1",
    "Q15-ADDRESS-RESIDENCY-COLLECTOR-v1",
    "Q15-SOFTWARE-PREFETCH-COLLECTOR-v1",
    "Q15-MSR-PRESTATE-COLLECTOR-v1",
    "Q15-MSR-READBACK-COLLECTOR-v1",
)


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=pathlib.Path)
    args = parser.parse_args()
    root = (args.source_root or pathlib.Path(__file__).resolve().parents[1]).resolve()
    profile_path = root / "config/q15/q15-dynamic-implementation-profile-v1.json"
    schema_path = root / "config/schemas/q15-dynamic-implementation-profile-v1.schema.json"
    evidence_schema_path = root / "config/schemas/q15-collector-evidence-v1.schema.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    evidence_schema = json.loads(evidence_schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(evidence_schema)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(profile), key=lambda item: list(item.path))
    if errors:
        for error in errors:
            print(f"q15-dynamic-implementation-check: FAIL: {error.message}", file=sys.stderr)
        return 1

    for source in profile["source_profiles"]:
        path = root / source["path"]
        if not path.is_file() or digest(path) != source["sha256"]:
            print(f"q15-dynamic-implementation-check: FAIL: source hash {source['id']}", file=sys.stderr)
            return 1

    boundary = profile["authority_boundary"]
    if any(value for key, value in boundary.items() if key != "authorized_operations"):
        print("q15-dynamic-implementation-check: FAIL: authority escaped", file=sys.stderr)
        return 1
    if tuple(profile["collector_profile"]["collector_ids"]) != COLLECTORS:
        print("q15-dynamic-implementation-check: FAIL: collector order", file=sys.stderr)
        return 1

    source_text = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "include/cpu_prefetch/platform/q15_runtime.hpp",
            "src/platform/q15_counted_region.cpp",
            "src/platform/q15_runtime.cpp",
            "include/cpu_prefetch/qualification/q15_collectors.hpp",
            "src/qualification/q15_collectors.cpp",
            "tools/q15_qualification_tool_main.cpp",
        )
    )
    required = (
        "SYS_perf_event_open",
        "PERF_TYPE_RAW",
        "kQ15AllPrefetchPerfConfig",
        "MAP_PRIVATE | MAP_ANONYMOUS",
        "SYS_mbind",
        "MADV_NOHUGEPAGE",
        "SYS_move_pages",
        "RUSAGE_THREAD",
        "CLOCK_MONOTONIC_RAW",
        "cpu_prefetch_q15_regular_counted_region",
        "h0_sealed_waiting_for_q15_w",
        "kQ15CollectorContracts",
        "q15_collector_registry",
        "--describe-dynamic-scope",
    )
    if any(token not in source_text for token in required):
        print("q15-dynamic-implementation-check: FAIL: implementation token missing", file=sys.stderr)
        return 1

    for description, mutate in (
        ("real PMU authority", lambda value: value["authority_boundary"].__setitem__("real_pmu_authorized", True)),
        ("fallback", lambda value: value["linux_acquisition"].__setitem__("retry_or_fallback", True)),
        ("network listener", lambda value: value["session_profile"].__setitem__("network_listener", True)),
        ("same buffer", lambda value: value["session_profile"].__setitem__("buffer_lifetime", "SAME_BYTES")),
    ):
        mutant = copy.deepcopy(profile)
        mutate(mutant)
        if not list(validator.iter_errors(mutant)):
            print(f"q15-dynamic-implementation-check: FAIL: accepted mutant {description}", file=sys.stderr)
            return 1

    print(
        "q15-dynamic-implementation-check: PASS "
        "(D-054..D-056, 7 collectors, 4 negative mutations, no authority)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
