#!/usr/bin/env python3
"""Validate the frozen Q15 probe/collector contract without executing it."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


COLLECTOR_IDS = {
    "Q15-CLOCK-COLLECTOR-v1",
    "Q15-ATOMIC-LAYOUT-COLLECTOR-v1",
    "Q15-ACTUAL-CPU-MIGRATION-COLLECTOR-v1",
    "Q15-ADDRESS-RESIDENCY-COLLECTOR-v1",
    "Q15-SOFTWARE-PREFETCH-COLLECTOR-v1",
    "Q15-MSR-PRESTATE-COLLECTOR-v1",
    "Q15-MSR-READBACK-COLLECTOR-v1",
}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sources = document.get("source_evidence", [])
    local_sources = [item for item in sources if not item.get("locator", "").startswith("https://")]
    for source in local_sources:
        path = root / source.get("locator", "")
        if not path.is_file() or sha256(path) != source.get("sha256"):
            errors.append(f"source hash mismatch: {source.get('artifact_id')}")

    scope = document.get("candidate_scope", {})
    if scope != {
        "base_page_bytes": 4096,
        "cache_line_bytes": 64,
        "cpu_family_hex": "06",
        "cpu_model_hex": "55",
        "cpu_order": [0, 1, 26],
        "far_pair": [0, 26],
        "near_pair": [0, 1],
    }:
        errors.append("candidate scope drift")

    counter = document.get("counter_contract", {})
    expected_counter = {
        "config_hex": "000000000000f824",
        "counter_name": "L2_RQSTS.ALL_PF",
        "event_select_hex": "24",
        "exclude_guest": True,
        "exclude_hypervisor": True,
        "exclude_kernel": True,
        "exclude_user": False,
        "inherit": False,
        "linux_interface": "perf_event_open",
        "pinned": True,
        "read_format": "TOTAL_TIME_ENABLED|TOTAL_TIME_RUNNING",
        "scope": "PER_THREAD_ON_SINGLETON_AFFINITY",
        "type": "PERF_TYPE_RAW",
        "umask_hex": "f8",
    }
    if counter != expected_counter:
        errors.append("counter programming drift")

    common = document.get("probe_common", {})
    common_expected = {
        "working_set_bytes_formula": "ROUND_UP(2*VERIFIED_LOCAL_LLC_BYTES,VERIFIED_BASE_PAGE_BYTES)",
        "priming_passes_per_state": 1,
        "counted_passes_per_state": 1,
        "time_enabled_must_equal_time_running": True,
        "counter_multiplexing_allowed": False,
        "minor_faults_allowed_in_counted_pass": 0,
        "major_faults_allowed_in_counted_pass": 0,
        "timing_role": "DIAGNOSTIC_ONLY",
        "h1_sequence": "H0_BASELINE_THEN_ONE_CPU_H1_APPLY_THEN_INDEPENDENT_READBACK_THEN_H1_PROBES_THEN_COMPLETE_RESTORE_THEN_INDEPENDENT_RESTORE_READBACK",
    }
    if any(common.get(key) != value for key, value in common_expected.items()):
        errors.append("common probe contract drift")
    for forbidden in (
        "dynamic_allocation_in_traversal",
        "filesystem_io_in_traversal",
        "prefetch_instructions_allowed",
    ):
        if common.get(forbidden) is not False:
            errors.append(f"probe hot path enables {forbidden}")

    regular = document.get("regular_probe", {})
    regular_acceptance = regular.get("acceptance", {})
    if (
        regular.get("probe_id") != "Q15-REGULAR-STREAM-ALL-PF-v1"
        or regular.get("address_order") != "ASCENDING_CACHE_LINES"
        or regular_acceptance.get("h0_all_pf_relation") != "GREATER_THAN"
        or regular_acceptance.get("h0_all_pf_threshold") != 0
        or regular_acceptance.get("h1_counter_relation") != "EQUAL"
        or regular_acceptance.get("h1_all_pf_count") != 0
        or regular_acceptance.get("integrity_required") is not True
    ):
        errors.append("regular-stream acceptance drift")

    pointer = document.get("pointer_probe", {})
    pointer_acceptance = pointer.get("acceptance", {})
    if (
        pointer.get("probe_id") != "Q15-POINTER-DEPENDENT-ALL-PF-v1"
        or pointer.get("address_order") != "SINGLE_DEPENDENT_CYCLE_OVER_ALL_CACHE_LINES"
        or pointer.get("seed_hex")
        != "b7ad8c3db8469f8b60ec679eb68b10b040a4b509438882732854257d582aff9b"
        or pointer_acceptance.get("h1_all_pf_count") != 0
        or pointer_acceptance.get("h0_positive_classification") != "DISTINGUISHED"
        or pointer_acceptance.get("h0_zero_classification")
        != "NOT_DISTINGUISHABLE_WHERE_NOT_POSSIBLE"
        or pointer_acceptance.get("integrity_required") is not True
    ):
        errors.append("pointer-dependent acceptance drift")

    collectors = document.get("collector_contracts", [])
    ids = [item.get("collector_id") for item in collectors]
    if set(ids) != COLLECTOR_IDS or len(ids) != len(set(ids)):
        errors.append("collector set drift")

    artifact = document.get("artifact_policy", {})
    if (
        artifact.get("append_only") is not True
        or artifact.get("partial_failure_retained") is not True
        or artifact.get("raw_counter_values_retained") is not True
        or artifact.get("raw_timestamps_retained") is not True
        or artifact.get("timing_subtracted_from_counter") is not False
    ):
        errors.append("artifact policy drift")

    boundary = document.get("unimplemented_boundary", {})
    if any(value is not False for value in boundary.values()) or set(boundary) != {
        "collector_executables_present",
        "dynamic_execution_authorized",
        "probe_executable_present",
        "q15_r_authorization_present",
        "q15_w_authorization_present",
    }:
        errors.append("unimplemented/no-authority boundary drift")
    return errors


def set_path(document: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    current: dict[str, Any] = document
    for component in path[:-1]:
        current = current[component]
    current[path[-1]] = value


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    contract_path = root / "config/q15/q15-probe-collector-contract-v1.json"
    schema_path = root / "config/schemas/q15-probe-collector-contract-v1.schema.json"
    if not schema_path.is_file():
        schema_path = (
            root
            / "config/schemas/implementation/q15-probe-collector-contract-v1.schema.json"
        )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    failures = [error.message for error in validator.iter_errors(contract)]
    failures.extend(semantic_errors(root, contract))
    if failures:
        for failure in failures:
            print(f"q15-probe-collector-contract-check: FAIL: {failure}", file=sys.stderr)
        return 1

    mutations: tuple[tuple[tuple[str, ...], object], ...] = (
        (("candidate_scope", "cpu_order"), [0, 26, 1]),
        (("counter_contract", "event_select_hex"), "25"),
        (("counter_contract", "umask_hex"), "00"),
        (("counter_contract", "exclude_kernel"), False),
        (("counter_contract", "pinned"), False),
        (("probe_common", "working_set_bytes_formula"), "UNRESOLVED"),
        (("probe_common", "counter_multiplexing_allowed"), True),
        (("probe_common", "minor_faults_allowed_in_counted_pass"), 1),
        (("probe_common", "timing_role"), "ACCEPTANCE_THRESHOLD"),
        (("regular_probe", "address_order"), "OUTCOME_DEPENDENT"),
        (("regular_probe", "acceptance", "h0_all_pf_threshold"), 1),
        (("regular_probe", "acceptance", "h1_all_pf_count"), 1),
        (("pointer_probe", "seed_hex"), "0" * 64),
        (("pointer_probe", "acceptance", "h0_zero_classification"), "FAILED"),
        (("artifact_policy", "partial_failure_retained"), False),
        (("artifact_policy", "timing_subtracted_from_counter"), True),
        (("unimplemented_boundary", "dynamic_execution_authorized"), True),
    )
    for index, (path, value) in enumerate(mutations):
        mutated = copy.deepcopy(contract)
        set_path(mutated, path, value)
        errors = [error.message for error in validator.iter_errors(mutated)]
        errors.extend(semantic_errors(root, mutated))
        if not errors:
            print(
                f"q15-probe-collector-contract-check: FAIL: negative {index} passed",
                file=sys.stderr,
            )
            return 1

    missing_collector = copy.deepcopy(contract)
    missing_collector["collector_contracts"].pop()
    if not list(validator.iter_errors(missing_collector)) and not semantic_errors(
        root, missing_collector
    ):
        print(
            "q15-probe-collector-contract-check: FAIL: missing collector passed",
            file=sys.stderr,
        )
        return 1

    print(
        "q15-probe-collector-contract-check: PASS "
        "(1 frozen contract, 18 negative, no collector/probe execution)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
