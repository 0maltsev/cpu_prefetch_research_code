#!/usr/bin/env python3
"""Exercise the no-authority Q15 bundle-profile policy without sealing a bundle."""

from __future__ import annotations

import copy

from verify_stand_bundle import q15_profile_errors


DENIED_FIELDS = (
    "account_or_key_changes_authorized",
    "bundle_transfer_or_install_authorized",
    "calibration_authorized",
    "confirmatory_authorized",
    "dynamic_qualification_authorized",
    "measurement_authorized",
    "measurement_execution_command_present",
    "msr_read_authorized",
    "msr_write_authorized",
    "pilot_authorized",
    "q15_r_authorized",
    "q15_w_authorized",
    "real_affinity_numa_authorized",
    "real_pmu_authorized",
    "scientific_schedule_access_authorized",
    "stand_access_authorized",
)

REQUIRED_PATHS = {
    "release/bin/cpu_prefetch_smoke",
    "release/bin/cpu_prefetch_preflight",
    "release/bin/cpu_prefetch_qualification",
    "release/bin/cpu_prefetch_q15_controller",
    "release/bin/cpu_prefetch_q15_prestate_collector",
    "release/bin/cpu_prefetch_q15_tool",
    "release/lib/libcpu_prefetch_foundation.a",
    "release/lib/libcpu_prefetch_platform.a",
    "release/lib/libcpu_prefetch_protocol.a",
    "release/lib/libcpu_prefetch_q15_qualification.a",
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
        "dynamic_implementation_profile": {
            "profile_id": "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1",
            "path": "config/q15/q15-dynamic-implementation-profile-v1.json",
            "sha256": "0" * 64,
        },
        "authorization_v2_contract": {
            "path": (
                "config/schemas/implementation/"
                "q15-qualification-authorization-v2.schema.json"
            ),
            "schema_version": "cpu-prefetch-q15-qualification-authorization/2",
            "sha256": "0" * 64,
        },
        "controller_profile": {
            "path": "config/q15/q15-r-controller-profile-v1.json",
            "profile_id": "Q15-R-STATIC-CONTROLLER-v1",
            "sha256": "0" * 64,
        },
        "role_custody_setup_plan": {
            "path": "config/q15/q15-r-role-custody-setup-plan-v1.json",
            "plan_id": "Q15-R-ROLE-CUSTODY-SETUP-PLAN-v1",
            "sha256": "0" * 64,
            "status": "PREPARED_NO_STAND_AUTHORITY",
        },
        "q15_r_p2_acceptance": {
            "acceptance_id": "Q15-R-P2-ACCEPTANCE-20260825-01",
            "authority": "REPOSITORY_LOCAL_ONLY",
            "path": "config/q15/q15-r-p2-acceptance-v1.json",
            "sha256": "0" * 64,
        },
        "q15_r_p4_d_acceptance": {
            "acceptance_id": "Q15-R-P4-D-ACCEPTANCE-20260825-01",
            "authority": "REPOSITORY_LOCAL_ONLY",
            "path": "config/q15/q15-r-p4-d-acceptance-v1.json",
            "sha256": "0" * 64,
        },
        "q15_r_p4_r_preparation": {
            "path": "config/q15/q15-r-p4-r.preparation.json",
            "preparation_id": "Q15-R-P4-R-PREPARATION-20260825-01",
            "sha256": "0" * 64,
            "status": "BLOCKED_CLEAN_COLLECTOR_RELEASE_AND_EXACT_AUTHORITY_REQUIRED",
        },
        "q15_r_p4_k_preparation": {
            "path": "config/q15/q15-r-p4-k.preparation.json",
            "preparation_id": "Q15-R-P4-K-PREPARATION-20260825-01",
            "sha256": "0" * 64,
            "status": "BLOCKED_OWNER_KEY_SOURCE_CUSTODY_AND_EXACT_AUTHORITY_REQUIRED",
        },
        "q15_r_prestate_collector_contract": {
            "contract_id": "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1",
            "path": "config/q15/q15-r-stand-prestate-collector-contract-v1.json",
            "sha256": "0" * 64,
            "status": "ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_EXECUTION_AUTHORITY",
        },
        "q15_r_prestate_artifact_validator": {
            "path": "validators/validate_q15_r_prestate.py",
            "sha256": "0" * 64,
            "state": "OFFLINE_READ_ONLY_VALIDATOR",
        },
        "stand_setup_authorization_preparation": {
            "path": "config/q15/q15-r-stand-setup-authorization.preparation.json",
            "preparation_id": "Q15-R-STAND-SETUP-AUTHORIZATION-PREPARATION-20260825-01",
            "sha256": "0" * 64,
            "status": "BLOCKED_INPUTS_REQUIRED_NO_AUTHORITY",
        },
        "trust_anchor_adapter_profile": {
            "implementation_state": "IMPLEMENTED_REPOSITORY_LOCAL_FAKE_BACKEND_ONLY_NO_AUTHORITY",
            "path": "config/q15/q15-r-trust-anchor-adapter-profile-v1.json",
            "profile_id": "Q15-R-TRUST-ANCHOR-ADAPTER-v1",
            "sha256": "0" * 64,
        },
        "source_archive": {"source_dirty": False},
    }
    document.update({field: False for field in DENIED_FIELDS})
    return document


def require_rejected(
    document: dict[str, object], paths: set[str | None], description: str
) -> None:
    if not q15_profile_errors(
        document, paths, controller_v2=True, prestate_v3=True
    ):
        raise AssertionError(f"Q15 bundle-profile negative accepted: {description}")


def main() -> int:
    positive = base_manifest()
    if q15_profile_errors(
        positive, set(REQUIRED_PATHS), controller_v2=True, prestate_v3=True
    ):
        raise AssertionError("valid no-authority Q15 bundle profile was rejected")

    legacy_v2 = copy.deepcopy(positive)
    for name in (
        "q15_r_p4_d_acceptance",
        "q15_r_p4_r_preparation",
        "q15_r_p4_k_preparation",
        "q15_r_prestate_collector_contract",
        "q15_r_prestate_artifact_validator",
    ):
        del legacy_v2[name]
    legacy_paths = set(REQUIRED_PATHS) - {
        "release/bin/cpu_prefetch_q15_prestate_collector"
    }
    if q15_profile_errors(
        legacy_v2, legacy_paths, controller_v2=True, prestate_v3=False
    ):
        raise AssertionError("historical controller-bearing v2 profile regressed")
    legacy_v1_paths = legacy_paths - {
        "release/bin/cpu_prefetch_q15_controller"
    }
    if q15_profile_errors(
        legacy_v2, legacy_v1_paths, controller_v2=False, prestate_v3=False
    ):
        raise AssertionError("historical qualification-tool v1 profile regressed")

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

    for key, value in (
        ("profile_id", "UNREGISTERED"),
        ("path", "../outside.json"),
        ("sha256", "not-a-sha256"),
    ):
        mutated = copy.deepcopy(positive)
        mutated["dynamic_implementation_profile"][key] = value
        require_rejected(mutated, set(REQUIRED_PATHS), f"dynamic profile {key}")
        negative_count += 1

    missing_dynamic = copy.deepcopy(positive)
    del missing_dynamic["dynamic_implementation_profile"]
    require_rejected(missing_dynamic, set(REQUIRED_PATHS), "missing dynamic profile")
    negative_count += 1

    for name in (
        "trust_anchor_adapter_profile",
        "q15_r_p2_acceptance",
        "q15_r_p4_d_acceptance",
        "q15_r_p4_r_preparation",
        "q15_r_p4_k_preparation",
        "q15_r_prestate_collector_contract",
        "q15_r_prestate_artifact_validator",
        "stand_setup_authorization_preparation",
    ):
        mutated = copy.deepcopy(positive)
        del mutated[name]
        require_rejected(mutated, set(REQUIRED_PATHS), f"missing {name}")
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
        f"(3 synthetic positive including v1/v2 compatibility, "
        f"{negative_count} negative, no bundle sealed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
