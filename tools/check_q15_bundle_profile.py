#!/usr/bin/env python3
"""Exercise the no-authority Q15 bundle-profile policy without sealing a bundle."""

from __future__ import annotations

import copy

from verify_stand_bundle import q15_profile_errors


DENIED_FIELDS = (
    "dynamic_qualification_authorized",
    "msr_read_authorized",
    "msr_write_authorized",
    "scientific_schedule_access_authorized",
    "measurement_execution_command_present",
    "pilot_authorized",
    "confirmatory_authorized",
)

REQUIRED_PATHS = {
    "release/bin/cpu_prefetch_smoke",
    "release/bin/cpu_prefetch_preflight",
    "release/bin/cpu_prefetch_qualification",
    "release/bin/cpu_prefetch_q15_tool",
    "release/lib/libcpu_prefetch_foundation.a",
    "release/lib/libcpu_prefetch_platform.a",
    "release/lib/libcpu_prefetch_protocol.a",
    "release/lib/libcpu_prefetch_workload.a",
}


def base_manifest() -> dict[str, object]:
    document: dict[str, object] = {
        "hardware_prefetch_mapping_id": (
            "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1"
        ),
        "qualification_tool_profile_id": "Q15-FIXED-QUALIFICATION-TOOL-v1",
        "probe_collector_contract": {
            "contract_id": "Q15-PROBE-COLLECTOR-CONTRACT-v1",
            "path": "config/q15/q15-probe-collector-contract-v1.json",
            "sha256": "0" * 64,
        },
        "probe_implementation_profile": {
            "profile_id": "Q15-PROBE-IMPLEMENTATION-PROFILE-v1",
            "path": "config/q15/q15-probe-implementation-profile-v1.json",
            "sha256": "0" * 64,
        },
        "source_archive": {"source_dirty": False},
    }
    document.update({field: False for field in DENIED_FIELDS})
    return document


def require_rejected(
    document: dict[str, object], paths: set[str | None], description: str
) -> None:
    if not q15_profile_errors(document, paths):
        raise AssertionError(f"Q15 bundle-profile negative accepted: {description}")


def main() -> int:
    positive = base_manifest()
    if q15_profile_errors(positive, set(REQUIRED_PATHS)):
        raise AssertionError("valid no-authority Q15 bundle profile was rejected")

    negative_count = 0
    for field in DENIED_FIELDS:
        mutated = copy.deepcopy(positive)
        mutated[field] = True
        require_rejected(mutated, set(REQUIRED_PATHS), field)
        negative_count += 1

    for key in ("qualification_tool_profile_id", "hardware_prefetch_mapping_id"):
        mutated = copy.deepcopy(positive)
        mutated[key] = "UNREGISTERED"
        require_rejected(mutated, set(REQUIRED_PATHS), key)
        negative_count += 1

    for key, value in (
        ("contract_id", "UNREGISTERED"),
        ("path", "../outside.json"),
        ("sha256", "not-a-sha256"),
    ):
        mutated = copy.deepcopy(positive)
        mutated["probe_collector_contract"][key] = value
        require_rejected(mutated, set(REQUIRED_PATHS), f"probe contract {key}")
        negative_count += 1

    missing_contract = copy.deepcopy(positive)
    del missing_contract["probe_collector_contract"]
    require_rejected(missing_contract, set(REQUIRED_PATHS), "missing probe contract")
    negative_count += 1

    for key, value in (
        ("profile_id", "UNREGISTERED"),
        ("path", "../outside.json"),
        ("sha256", "not-a-sha256"),
    ):
        mutated = copy.deepcopy(positive)
        mutated["probe_implementation_profile"][key] = value
        require_rejected(mutated, set(REQUIRED_PATHS), f"probe profile {key}")
        negative_count += 1

    missing_profile = copy.deepcopy(positive)
    del missing_profile["probe_implementation_profile"]
    require_rejected(missing_profile, set(REQUIRED_PATHS), "missing probe profile")
    negative_count += 1

    dirty = copy.deepcopy(positive)
    dirty["source_archive"] = {"source_dirty": True}
    require_rejected(dirty, set(REQUIRED_PATHS), "dirty source")
    negative_count += 1

    for missing in sorted(REQUIRED_PATHS):
        require_rejected(positive, set(REQUIRED_PATHS) - {missing}, missing)
        negative_count += 1

    for forbidden in (
        "release/bin/cpu_prefetch_runner",
        "release/lib/libcpu_prefetch_runner_core.a",
    ):
        require_rejected(positive, set(REQUIRED_PATHS) | {forbidden}, forbidden)
        negative_count += 1

    print(
        "q15-bundle-profile-check: PASS "
        f"(1 synthetic positive, {negative_count} negative, no bundle sealed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
