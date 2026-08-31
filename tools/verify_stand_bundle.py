#!/usr/bin/env python3
"""Verify a cleanly extracted Stage 16 stand bundle without mutating the host."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def q15_profile_errors(
    manifest: dict[str, object],
    release_paths: set[str | None],
    *,
    controller_v2: bool,
    prestate_v3: bool = False,
) -> list[str]:
    failures: list[str] = []
    source_archive = manifest.get("source_archive")
    source_dirty = (
        source_archive.get("source_dirty")
        if isinstance(source_archive, dict)
        else None
    )
    if source_dirty is not False:
        failures.append("Q15 qualification-tool source must be clean")
    if manifest.get("qualification_tool_profile_id") != (
        "Q15-FIXED-QUALIFICATION-TOOL-v1"
    ):
        failures.append("Q15 qualification-tool profile is absent")
    if manifest.get("hardware_prefetch_mapping_id") != (
        "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1"
    ):
        failures.append("Q15 qualification-tool mapping is absent")
    contract = manifest.get("probe_collector_contract")
    if not isinstance(contract, dict):
        failures.append("Q15 probe/collector contract binding is absent")
    elif (
        contract.get("contract_id") != "Q15-PROBE-COLLECTOR-CONTRACT-v1"
        or contract.get("path")
        != "config/q15/q15-probe-collector-contract-v1.json"
        or not isinstance(contract.get("sha256"), str)
        or len(contract.get("sha256", "")) != 64
        or any(character not in "0123456789abcdef" for character in contract["sha256"])
    ):
        failures.append("Q15 probe/collector contract binding is invalid")
    implementation = manifest.get("probe_implementation_profile")
    if not isinstance(implementation, dict):
        failures.append("Q15 probe implementation profile binding is absent")
    elif (
        implementation.get("profile_id") != "Q15-PROBE-IMPLEMENTATION-PROFILE-v1"
        or implementation.get("path")
        != "config/q15/q15-probe-implementation-profile-v1.json"
        or not isinstance(implementation.get("sha256"), str)
        or len(implementation.get("sha256", "")) != 64
        or any(
            character not in "0123456789abcdef"
            for character in implementation["sha256"]
        )
    ):
        failures.append("Q15 probe implementation profile binding is invalid")
    dynamic = manifest.get("dynamic_implementation_profile")
    if not isinstance(dynamic, dict):
        failures.append("Q15 dynamic implementation profile binding is absent")
    elif (
        dynamic.get("profile_id") != "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1"
        or dynamic.get("path")
        != "config/q15/q15-dynamic-implementation-profile-v1.json"
        or not isinstance(dynamic.get("sha256"), str)
        or len(dynamic.get("sha256", "")) != 64
        or any(character not in "0123456789abcdef" for character in dynamic["sha256"])
    ):
        failures.append("Q15 dynamic implementation profile binding is invalid")
    denied_fields = [
        "dynamic_qualification_authorized",
        "msr_read_authorized",
        "msr_write_authorized",
        "scientific_schedule_access_authorized",
        "measurement_execution_command_present",
        "pilot_authorized",
        "confirmatory_authorized",
    ]
    if controller_v2:
        denied_fields.extend(
            [
                "stand_access_authorized",
                "account_or_key_changes_authorized",
                "bundle_transfer_or_install_authorized",
                "q15_r_authorized",
                "q15_w_authorized",
                "real_pmu_authorized",
                "real_affinity_numa_authorized",
                "calibration_authorized",
                "measurement_authorized",
            ]
        )
    for field in denied_fields:
        if manifest.get(field) is not False:
            failures.append(f"Q15 qualification-tool must deny {field}")
    for required in (
        "release/bin/cpu_prefetch_smoke",
        "release/bin/cpu_prefetch_preflight",
        "release/bin/cpu_prefetch_qualification",
        "release/bin/cpu_prefetch_q15_tool",
        "release/lib/libcpu_prefetch_foundation.a",
        "release/lib/libcpu_prefetch_platform.a",
        "release/lib/libcpu_prefetch_protocol.a",
        "release/lib/libcpu_prefetch_q15_qualification.a",
        "release/lib/libcpu_prefetch_workload.a",
    ):
        if required not in release_paths:
            failures.append(f"Q15 qualification-tool misses {required}")
    if controller_v2:
        for required_binary in ("release/bin/cpu_prefetch_q15_controller",):
            if required_binary not in release_paths:
                failures.append(
                    f"Q15 controller bundle misses {required_binary}"
                )
        for name, expected_id, expected_path in (
            (
                "controller_profile",
                "Q15-R-STATIC-CONTROLLER-v1",
                "config/q15/q15-r-controller-profile-v1.json",
            ),
            (
                "role_custody_setup_plan",
                "Q15-R-ROLE-CUSTODY-SETUP-PLAN-v1",
                "config/q15/q15-r-role-custody-setup-plan-v1.json",
            ),
        ):
            binding = manifest.get(name)
            identity_key = "profile_id" if name == "controller_profile" else "plan_id"
            if not isinstance(binding, dict) or (
                binding.get(identity_key) != expected_id
                or binding.get("path") != expected_path
                or not isinstance(binding.get("sha256"), str)
                or len(binding.get("sha256", "")) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in binding.get("sha256", "")
                )
                or (
                    name == "role_custody_setup_plan"
                    and binding.get("status") != "PREPARED_NO_STAND_AUTHORITY"
                )
            ):
                failures.append(f"Q15 controller bundle has invalid {name}")
        authorization = manifest.get("authorization_v2_contract")
        if not isinstance(authorization, dict) or (
            authorization.get("schema_version")
            != "cpu-prefetch-q15-qualification-authorization/2"
            or authorization.get("path")
            != (
                "config/schemas/implementation/"
                "q15-qualification-authorization-v2.schema.json"
            )
            or not isinstance(authorization.get("sha256"), str)
            or len(authorization.get("sha256", "")) != 64
            or any(
                character not in "0123456789abcdef"
                for character in authorization.get("sha256", "")
            )
        ):
            failures.append("Q15 controller bundle has invalid authorization-v2 binding")
        binding_specs = [
            (
                "trust_anchor_adapter_profile",
                "profile_id",
                "Q15-R-TRUST-ANCHOR-ADAPTER-v1",
                "config/q15/q15-r-trust-anchor-adapter-profile-v1.json",
                "implementation_state",
                "IMPLEMENTED_REPOSITORY_LOCAL_FAKE_BACKEND_ONLY_NO_AUTHORITY",
            ),
            (
                "q15_r_p2_acceptance",
                "acceptance_id",
                "Q15-R-P2-ACCEPTANCE-20260825-01",
                "config/q15/q15-r-p2-acceptance-v1.json",
                "authority",
                "REPOSITORY_LOCAL_ONLY",
            ),
            (
                "stand_setup_authorization_preparation",
                "preparation_id",
                "Q15-R-STAND-SETUP-AUTHORIZATION-PREPARATION-20260825-01",
                "config/q15/q15-r-stand-setup-authorization.preparation.json",
                "status",
                "BLOCKED_INPUTS_REQUIRED_NO_AUTHORITY",
            ),
        ]
        if prestate_v3:
            if "release/bin/cpu_prefetch_q15_prestate_collector" not in release_paths:
                failures.append(
                    "Q15 prestate bundle misses prestate collector executable"
                )
            binding_specs.extend(
                [
                    (
                        "q15_r_p4_d_acceptance",
                        "acceptance_id",
                        "Q15-R-P4-D-ACCEPTANCE-20260825-01",
                        "config/q15/q15-r-p4-d-acceptance-v1.json",
                        "authority",
                        "REPOSITORY_LOCAL_ONLY",
                    ),
                    (
                        "q15_r_p4_r_preparation",
                        "preparation_id",
                        "Q15-R-P4-R-PREPARATION-20260825-01",
                        "config/q15/q15-r-p4-r.preparation.json",
                        "status",
                        "BLOCKED_CLEAN_COLLECTOR_RELEASE_AND_EXACT_AUTHORITY_REQUIRED",
                    ),
                    (
                        "q15_r_p4_k_preparation",
                        "preparation_id",
                        "Q15-R-P4-K-PREPARATION-20260825-01",
                        "config/q15/q15-r-p4-k.preparation.json",
                        "status",
                        "BLOCKED_OWNER_KEY_SOURCE_CUSTODY_AND_EXACT_AUTHORITY_REQUIRED",
                    ),
                    (
                        "q15_r_prestate_collector_contract",
                        "contract_id",
                        "Q15-R-STAND-PRESTATE-COLLECTOR-CONTRACT-v1",
                        "config/q15/q15-r-stand-prestate-collector-contract-v1.json",
                        "status",
                        "ACCEPTED_IMPLEMENTED_REPOSITORY_LOCAL_NO_EXECUTION_AUTHORITY",
                    ),
                    (
                        "q15_r_prestate_artifact_validator",
                        "state",
                        "OFFLINE_READ_ONLY_VALIDATOR",
                        "validators/validate_q15_r_prestate.py",
                        "state",
                        "OFFLINE_READ_ONLY_VALIDATOR",
                    ),
                ]
            )
        for (
            name,
            expected_id_key,
            expected_id,
            expected_path,
            expected_state_key,
            expected_state,
        ) in binding_specs:
            binding = manifest.get(name)
            if not isinstance(binding, dict) or (
                binding.get(expected_id_key) != expected_id
                or binding.get("path") != expected_path
                or binding.get(expected_state_key) != expected_state
                or not isinstance(binding.get("sha256"), str)
                or len(binding.get("sha256", "")) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in binding.get("sha256", "")
                )
            ):
                failures.append(f"Q15 controller bundle has invalid {name}")
    for forbidden in (
        "release/bin/cpu_prefetch_runner",
        "release/lib/libcpu_prefetch_runner_core.a",
    ):
        if forbidden in release_paths:
            failures.append(f"Q15 qualification-tool contains forbidden {forbidden}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=pathlib.Path, default=pathlib.Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    checksum_path = root / "SHA256SUMS"
    manifest_path = root / "BUNDLE_MANIFEST.json"
    failures: list[str] = []
    declared: set[pathlib.Path] = set()

    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative_text = line.split("  ", maxsplit=1)
        relative = pathlib.Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            failures.append(f"unsafe checksum path: {relative}")
            continue
        declared.add(relative)
        path = root / relative
        if not path.is_file():
            failures.append(f"missing declared file: {relative}")
        elif sha256(path) != expected:
            failures.append(f"SHA-256 mismatch: {relative}")

    actual = {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if actual != declared:
        failures.append(
            "inventory mismatch: missing="
            f"{sorted(map(str, declared - actual))} extra={sorted(map(str, actual - declared))}"
        )
    inventory_path = root / "BUNDLE_INVENTORY.json"
    if not inventory_path.is_file():
        failures.append("bundle inventory document is absent")
    else:
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
        inventory_entries = inventory.get("files", [])
        inventory_paths = {
            pathlib.Path(item.get("path", "")) for item in inventory_entries
            if isinstance(item, dict)
        }
        expected_inventory = declared - {pathlib.Path("BUNDLE_INVENTORY.json")}
        if (inventory.get("schema_version")
                != "cpu-prefetch-stand-bundle-inventory/1"
                or inventory_paths != expected_inventory):
            failures.append("bundle inventory document does not cover exact payload")
        else:
            for item in inventory_entries:
                path = root / item["path"]
                if (path.stat().st_size, sha256(path)) != (
                    item.get("size_bytes"), item.get("sha256")
                ):
                    failures.append(
                        f"bundle inventory byte mismatch: {item['path']}"
                    )
                    break

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = manifest.get("bundle_profile")
    expected = {
        "STAGE16-STAND-BUNDLE-v1": (
            "cpu-prefetch-stand-bundle/1",
            "READY_FOR_STAND_PREFLIGHT",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v1": (
            "cpu-prefetch-pilot-candidate-bundle/1",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v2": (
            "cpu-prefetch-pilot-candidate-bundle/2",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v3": (
            "cpu-prefetch-pilot-candidate-bundle/3",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1": (
            "cpu-prefetch-pilot-candidate-bundle/3",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v4": (
            "cpu-prefetch-pilot-candidate-bundle/4",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2": (
            "cpu-prefetch-pilot-candidate-bundle/4",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "Q15-QUALIFICATION-TOOL-BUNDLE-v1": (
            "cpu-prefetch-q15-qualification-tool-bundle/1",
            "Q15_TOOL_RELEASE_NO_AUTHORITY",
        ),
        "Q15-QUALIFICATION-TOOL-BUNDLE-v2": (
            "cpu-prefetch-q15-qualification-tool-bundle/2",
            "Q15_TOOL_RELEASE_NO_AUTHORITY",
        ),
        "Q15-QUALIFICATION-TOOL-BUNDLE-v3": (
            "cpu-prefetch-q15-qualification-tool-bundle/3",
            "Q15_TOOL_RELEASE_NO_AUTHORITY",
        ),
    }
    if profile not in expected:
        failures.append("unknown bundle profile")
        expected_schema, expected_readiness = "", ""
    else:
        expected_schema, expected_readiness = expected[profile]
    if manifest.get("schema_version") != expected_schema:
        failures.append("unknown or profile-mismatched bundle schema")
    expected_protocol = (
        "2.0.0-pre.3" if profile in {
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
        } else "2.0.0-pre.2"
    )
    if manifest.get("protocol_version") != expected_protocol:
        failures.append("wrong protocol version")
    protocol_manifest = root / "protocol" / expected_protocol / "IMPORT_MANIFEST.json"
    if (
        not protocol_manifest.is_file()
        or sha256(protocol_manifest) != manifest.get("protocol_import_manifest_sha256")
    ):
        failures.append("protocol import manifest path/hash mismatch")
    if manifest.get("readiness_state") != expected_readiness:
        failures.append("bundle readiness does not match its fail-closed profile")
    if manifest.get("pilot_authorized") is not False:
        failures.append("bundle must explicitly prohibit pilot execution")
    if manifest.get("confirmatory_authorized") is not False:
        failures.append("bundle must explicitly prohibit confirmatory execution")
    for field, description in (
        ("dynamic_qualification_authorized", "dynamic qualification"),
        ("measurement_execution_command_present", "a measurement command"),
    ):
        value = manifest.get(field)
        if profile in ("STAGE17-PILOT-CANDIDATE-BUNDLE-v1",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v2",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v3",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2") and value is not False:
            failures.append(f"pilot candidate must explicitly prohibit {description}")
        elif profile == "STAGE16-STAND-BUNDLE-v1" and value not in (None, False):
            failures.append(f"Stage 16 bundle unexpectedly enables {description}")

    release_paths: set[str | None] = set()
    for item in manifest.get("release_artifacts", []):
        relative_text = item.get("path")
        if relative_text in release_paths:
            failures.append(f"duplicate release artifact path: {relative_text}")
            continue
        release_paths.add(relative_text)
        if not isinstance(relative_text, str):
            failures.append("release artifact path must be a string")
            continue
        relative = pathlib.Path(relative_text)
        if relative.is_absolute() or ".." in relative.parts:
            failures.append(f"unsafe release artifact path: {relative_text}")
            continue
        release_path = root / relative
        if not release_path.is_file():
            failures.append(f"missing release artifact: {relative_text}")
        elif sha256(release_path) != item.get("sha256"):
            failures.append(f"release manifest hash mismatch: {relative_text}")
        elif release_path.stat().st_size != item.get("size_bytes"):
            failures.append(f"release manifest size mismatch: {relative_text}")

    source = manifest.get("source_archive", {})
    source_text = source.get("path")
    if not isinstance(source_text, str):
        failures.append("source archive path must be a string")
        source_path = root / "SOURCE_PATH_INVALID"
    else:
        source_relative = pathlib.Path(source_text)
        if source_relative.is_absolute() or ".." in source_relative.parts:
            failures.append("unsafe source archive path")
            source_path = root / "SOURCE_PATH_INVALID"
        else:
            source_path = root / source_relative
    if not source_path.is_file() or sha256(source_path) != source.get("sha256"):
        failures.append("source archive path/hash mismatch")

    if profile in ("STAGE17-PILOT-CANDIDATE-BUNDLE-v1",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v2",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v3",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2"):
        if (
            manifest.get("software_prefetch_mapping_id")
            != "X86-64-PREFETCHW-PREFETCHT0-v1"
        ):
            failures.append("pilot candidate has no accepted D-047 mapping identity")
        if manifest.get("debug_symbol_strategy") != (
            "UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE"
        ):
            failures.append("pilot candidate has no accepted debug-symbol strategy")
        if manifest.get("source_archive", {}).get("source_dirty") is not False:
            failures.append("pilot-candidate source must be clean")
        for required in (
            "release/bin/cpu_prefetch_runner",
            "release/bin/cpu_prefetch_qualification",
        ):
            if required not in release_paths:
                failures.append(f"pilot candidate misses {required}")
        for report in (
            "queue_codegen_report.json",
            "workload_codegen_report.json",
            "timing_codegen_report.json",
            "storage_codegen_report.json",
            "runner_relax_codegen_report.json",
            "runner_combined_codegen_report.json",
        ):
            report_relative = pathlib.Path("build-provenance") / report
            if report_relative not in declared:
                failures.append(f"pilot candidate misses codegen report {report}")
                continue
            report_document = json.loads((root / report_relative).read_text(encoding="utf-8"))
            if report_document.get("status") != "PASS" or report_document.get(
                "missing_tools"
            ) != []:
                failures.append(f"pilot candidate codegen report is not strict: {report}")
            if report == "runner_combined_codegen_report.json" and (
                report_document.get("schema_version")
                != "cpu-prefetch-runner-combined-codegen/2"
                or report_document.get("software_prefetch_mapping_id")
                != "X86-64-PREFETCHW-PREFETCHT0-v1"
            ):
                failures.append("pilot candidate combined report lacks D-047 identity")
        if profile == "STAGE17-PILOT-CANDIDATE-BUNDLE-v2":
            runtime = manifest.get("stage17_fixed_action_runtime")
            expected_actions = ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                                "STAGE17-BLINDED-PILOT"]
            worker = root / "release/bin/cpu_prefetch_runner"
            if (not isinstance(runtime, dict)
                    or runtime.get("member_path") != "release/bin/cpu_prefetch_runner"
                    or runtime.get("size_bytes") != worker.stat().st_size
                    or runtime.get("sha256") != sha256(worker)
                    or runtime.get("role") != "STAGE17_FIXED_ACTION_WORKER"
                    or runtime.get("runtime_profile") != "STAGE17-FIXED-ACTION-WORKER-v2"
                    or runtime.get("supported_actions") != expected_actions
                    or runtime.get("synthetic_test_only") is not False):
                failures.append("pilot candidate v2 fixed-action runtime binding is invalid")
            payload = worker.read_bytes()
            for token in (b"--execute-fixed-stage17-action-v2",
                          b"STAGE17-FIXED-ACTION-WORKER-v2",
                          *(item.encode("ascii") for item in expected_actions)):
                if token not in payload:
                    failures.append("pilot candidate v2 worker lacks fixed dispatcher surface")
                    break
            controller = manifest.get("stage17_controller_runtime")
            if not isinstance(controller, dict):
                failures.append("pilot candidate v2 controller runtime is absent")
            else:
                policy_binding = controller.get("policy")
                policy_path = root / "config/stage17/stage17-operational-evidence-admission-policy-v10.json"
                if (controller.get("controller_id")
                        != "STAGE17-FIXED-ACTION-PHASE-CONTROLLER-v2"
                        or controller.get("entrypoint")
                        != "tools/stage17_phase_controller_v2.py"
                        or controller.get("invocation")
                        != ["python3", "tools/stage17_phase_controller_v2.py"]
                        or controller.get("production_test_mode_available") is not False
                        or controller.get("authority_embedded") is not False
                        or controller.get("repository_evidence_roots")
                        != ["config", "docs"]
                        or not isinstance(policy_binding, dict)
                        or policy_binding.get("path")
                        != "config/stage17/stage17-operational-evidence-admission-policy-v10.json"
                        or not policy_path.is_file()
                        or policy_binding.get("size_bytes") != policy_path.stat().st_size
                        or policy_binding.get("sha256") != sha256(policy_path)):
                    failures.append("pilot candidate v2 controller identity is invalid")
                else:
                    policy_document = json.loads(policy_path.read_text(encoding="utf-8"))
                    expected_bound_files = []
                    for group_name in ("bindings", "runtime_closure"):
                        for key, binding in policy_document.get(group_name, {}).items():
                            expected_bound_files.append({
                                "group": group_name,
                                "key": key,
                                "path": binding.get("path"),
                                "size_bytes": binding.get("size_bytes"),
                                "sha256": binding.get("sha256"),
                            })
                    if controller.get("bound_files") != expected_bound_files:
                        failures.append("pilot candidate v2 controller closure differs from policy")
                    else:
                        for binding in expected_bound_files:
                            relative_text = binding["path"]
                            relative = pathlib.Path(relative_text)
                            candidate = root / relative
                            if (relative.is_absolute() or ".." in relative.parts
                                    or not candidate.is_file() or candidate.is_symlink()
                                    or candidate.stat().st_size != binding["size_bytes"]
                                    or sha256(candidate) != binding["sha256"]):
                                failures.append(
                                    f"pilot candidate v2 controller binding drifted: {relative_text}"
                                )
                                break
                    entrypoint = root / "tools/stage17_phase_controller_v2.py"
                    entrypoint_payload = entrypoint.read_bytes() if entrypoint.is_file() else b""
                    if (b"test_linked_worker=False" not in entrypoint_payload
                            or b"--test-linked-worker" in entrypoint_payload):
                        failures.append("pilot candidate v2 controller exposes a production test mode")
                    for relative_text in (
                        "docs/decisions/0104-stage17-pilot-operational-governance-successor.md",
                        "config/q15/q15-r-p4-r-i-d099-authorization-v1.json",
                        "docs/evidence/stage17/"
                        "Q15-R-P4-R-XEON-CPU-FETCH-20260825-01/"
                        "Q15-R-P4-R-IDENTITY-XEON-CPU-FETCH-20260825-01.json",
                    ):
                        candidate = root / relative_text
                        if not candidate.is_file() or candidate.is_symlink():
                            failures.append(
                                "pilot candidate v2 repository evidence is absent: "
                                + relative_text
                            )

        if profile in ("STAGE17-PILOT-CANDIDATE-BUNDLE-v3",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2"):
            runtime = manifest.get("stage17_fixed_action_runtime")
            expected_actions = ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                                "STAGE17-BLINDED-PILOT"]
            worker = root / "release/bin/cpu_prefetch_runner"
            current_v4 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
            }
            version = 4 if current_v4 else 3
            controller_version = 7 if current_v4 else version
            expected_synthetic = profile in {
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
            }
            if (not isinstance(runtime, dict)
                    or runtime.get("member_path") != "release/bin/cpu_prefetch_runner"
                    or runtime.get("size_bytes") != worker.stat().st_size
                    or runtime.get("sha256") != sha256(worker)
                    or runtime.get("role") != "STAGE17_FIXED_ACTION_WORKER"
                    or runtime.get("runtime_profile")
                    != f"STAGE17-FIXED-ACTION-WORKER-v{version}"
                    or runtime.get("supported_actions") != expected_actions
                    or runtime.get("synthetic_test_only") is not expected_synthetic):
                failures.append("pilot candidate fixed-action runtime binding is invalid")
            payload = worker.read_bytes()
            for token in (f"--execute-fixed-stage17-action-v{version}".encode(),
                          f"STAGE17-FIXED-ACTION-WORKER-v{version}".encode(),
                          *( (b"--execute-stage17-pilot-session-v1",)
                             if current_v4 else () ),
                          *(item.encode("ascii") for item in expected_actions)):
                if token not in payload:
                    failures.append("pilot candidate worker lacks fixed dispatcher surface")
                    break
            completed = None
            try:
                completed = subprocess.run(
                    [str(worker), f"--stage17-runtime-identity-v{version}"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, check=False, timeout=15,
                    env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin",
                         "TZ": "UTC"},
                )
                identity = json.loads(completed.stdout)
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
                identity = None
            expected_identity = {
                "binary_sha256": sha256(worker),
                "protocol_version": "2.0.0-pre.3" if current_v4 else "2.0.0-pre.2",
                "role": "STAGE17_FIXED_ACTION_WORKER",
                "runtime_profile": f"STAGE17-FIXED-ACTION-WORKER-v{version}",
                "source_dirty": False,
                "source_revision": manifest.get("source_archive", {}).get(
                    "source_revision"
                ),
                "supported_actions": expected_actions,
                "synthetic_test_only": expected_synthetic,
            }
            if (completed is None or completed.returncode != 0
                    or identity != expected_identity):
                failures.append(
                    "pilot candidate worker runtime identity/provenance is invalid"
                )
            controller = manifest.get("stage17_controller_runtime")
            policy_path = root / (
                "config/stage17/"
                f"stage17-operational-evidence-admission-policy-v{17 if current_v4 else 11}.json"
            )
            if (not isinstance(controller, dict)
                    or controller.get("controller_id")
                    != f"STAGE17-FIXED-ACTION-PHASE-CONTROLLER-v{controller_version}"
                    or controller.get("entrypoint")
                    != f"tools/stage17_phase_controller_v{controller_version}.py"
                    or controller.get("invocation")
                    != ["python3", f"tools/stage17_phase_controller_v{controller_version}.py"]
                    or controller.get("production_test_mode_available") is not False
                    or controller.get("authority_embedded") is not False
                    or not policy_path.is_file()):
                failures.append("pilot candidate controller identity is invalid")
            else:
                binding = controller.get("policy", {})
                if (binding.get("path") != policy_path.relative_to(root).as_posix()
                        or binding.get("size_bytes") != policy_path.stat().st_size
                        or binding.get("sha256") != sha256(policy_path)):
                    failures.append("pilot candidate policy binding is invalid")
                policy = json.loads(policy_path.read_text(encoding="utf-8"))
                expected_bound = [
                    {"group": group, "key": key, "path": item.get("path"),
                     "size_bytes": item.get("size_bytes"),
                     "sha256": item.get("sha256")}
                    for group in ("bindings", "runtime_closure")
                    for key, item in policy.get(group, {}).items()
                ]
                if controller.get("bound_files") != expected_bound:
                    failures.append("pilot candidate controller closure differs from policy")
                for item in expected_bound:
                    candidate = root / str(item["path"])
                    if (not candidate.is_file() or candidate.is_symlink()
                            or candidate.stat().st_size != item["size_bytes"]
                            or sha256(candidate) != item["sha256"]):
                        failures.append(
                            f"pilot candidate controller binding drifted: {item['path']}"
                        )
                        break
                nested_path = root / (
                    "config/stage17/"
                    "stage17-read-only-preflight-evidence-admission-policy-v13.json"
                )
                nested_summary = controller.get("nested_preflight_policy", {})
                if not nested_path.is_file():
                    failures.append("nested preflight policy is absent")
                else:
                    nested_policy = json.loads(nested_path.read_text(encoding="utf-8"))
                    expected_nested = [
                        {
                            "group": group,
                            "key": key,
                            "path": item.get("path"),
                            "size_bytes": item.get("size_bytes"),
                            "sha256": item.get("sha256"),
                        }
                        for group in ("implementations", "operational_implementations")
                        for key, item in nested_policy.get(group, {}).items()
                    ]
                    if (nested_summary.get("path")
                            != nested_path.relative_to(root).as_posix()
                            or nested_summary.get("size_bytes")
                            != nested_path.stat().st_size
                            or nested_summary.get("sha256") != sha256(nested_path)
                            or nested_summary.get("bound_files") != expected_nested):
                        failures.append("nested preflight policy closure drifted")
                    for item in expected_nested:
                        candidate = root / str(item["path"])
                        if (not candidate.is_file() or candidate.is_symlink()
                                or candidate.stat().st_size != item["size_bytes"]
                                or sha256(candidate) != item["sha256"]):
                            failures.append(
                                "nested preflight bound file is absent or drifted"
                            )
                            break
                for relative in (
                    "tools/stage17_read_only_preflight_executor_v11.py",
                    "tools/stage17_read_only_preflight_collector_v2.py",
                ):
                    candidate = root / relative
                    if (not candidate.is_file() or candidate.is_symlink()
                            or not os.access(candidate, os.X_OK)):
                        failures.append(
                            "pilot candidate S17-EXT-001 action identity is not "
                            f"executable: {relative}"
                        )

    if profile in (
        "Q15-QUALIFICATION-TOOL-BUNDLE-v1",
        "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
        "Q15-QUALIFICATION-TOOL-BUNDLE-v3",
    ):
        controller_v2 = profile in (
            "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
            "Q15-QUALIFICATION-TOOL-BUNDLE-v3",
        )
        prestate_v3 = profile == "Q15-QUALIFICATION-TOOL-BUNDLE-v3"
        failures.extend(
            q15_profile_errors(
                manifest,
                release_paths,
                controller_v2=controller_v2,
                prestate_v3=prestate_v3,
            )
        )
        for required_evidence in (
            pathlib.Path(
                "docs/evidence/stage16/"
                "STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/"
                "STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02.json"
            ),
            pathlib.Path(
                "docs/evidence/stage16/"
                "STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01/SHA256SUMS"
            ),
        ):
            if required_evidence not in declared:
                failures.append(
                    f"Q15 probe/collector contract misses source evidence {required_evidence}"
                )
        binding_names = [
            "probe_collector_contract",
            "probe_implementation_profile",
            "dynamic_implementation_profile",
        ]
        if controller_v2:
            binding_names.extend(
                ["controller_profile", "role_custody_setup_plan"]
            )
        for binding_name in binding_names:
            binding = manifest.get(binding_name, {})
            binding_text = binding.get("path") if isinstance(binding, dict) else None
            if not isinstance(binding_text, str):
                failures.append(f"Q15 {binding_name} path is absent")
                continue
            binding_relative = pathlib.Path(binding_text)
            if binding_relative.is_absolute() or ".." in binding_relative.parts:
                failures.append(f"unsafe Q15 {binding_name} path")
                continue
            binding_path = root / binding_relative
            if (
                not binding_path.is_file()
                or sha256(binding_path) != binding.get("sha256")
            ):
                failures.append(f"Q15 {binding_name} path/hash mismatch")
        if controller_v2:
            authorization = manifest.get("authorization_v2_contract", {})
            authorization_text = (
                authorization.get("path")
                if isinstance(authorization, dict)
                else None
            )
            if not isinstance(authorization_text, str):
                failures.append("Q15 authorization-v2 path is absent")
            else:
                authorization_relative = pathlib.Path(authorization_text)
                authorization_path = root / authorization_relative
                if (
                    authorization_relative.is_absolute()
                    or ".." in authorization_relative.parts
                    or not authorization_path.is_file()
                    or sha256(authorization_path) != authorization.get("sha256")
                ):
                    failures.append("Q15 authorization-v2 path/hash mismatch")
            controller_binding_names = [
                "trust_anchor_adapter_profile",
                "q15_r_p2_acceptance",
                "stand_setup_authorization_preparation",
            ]
            if prestate_v3:
                controller_binding_names.extend(
                    [
                        "q15_r_p4_d_acceptance",
                        "q15_r_p4_r_preparation",
                        "q15_r_p4_k_preparation",
                        "q15_r_prestate_collector_contract",
                        "q15_r_prestate_artifact_validator",
                    ]
                )
            for binding_name in controller_binding_names:
                binding = manifest.get(binding_name, {})
                binding_text = (
                    binding.get("path") if isinstance(binding, dict) else None
                )
                if not isinstance(binding_text, str):
                    failures.append(f"Q15 {binding_name} path is absent")
                    continue
                binding_relative = pathlib.Path(binding_text)
                binding_path = root / binding_relative
                if (
                    binding_relative.is_absolute()
                    or ".." in binding_relative.parts
                    or not binding_path.is_file()
                    or sha256(binding_path) != binding.get("sha256")
                ):
                    failures.append(f"Q15 {binding_name} path/hash mismatch")
        reports = [
            "q15_probe_codegen_report.json",
            "q15_runtime_codegen_report.json",
        ]
        if controller_v2:
            reports.append("q15_controller_codegen_report.json")
        for report in reports:
            report_relative = pathlib.Path("build-provenance") / report
            if report_relative not in declared:
                failures.append(f"Q15 qualification-tool misses codegen report {report}")
                continue
            report_document = json.loads(
                (root / report_relative).read_text(encoding="utf-8")
            )
            if report_document.get("status") != "PASS" or report_document.get(
                "missing_tools"
            ) != []:
                failures.append(f"Q15 codegen report is not strict: {report}")

    example = json.loads(
        (root / "config" / "examples" / "stage16-stand-inputs.example.json").read_text(
            encoding="utf-8"
        )
    )
    if example.get("authoritative") is not False or any(
        value is not None for value in example["required_external_inputs"].values()
    ):
        failures.append("nonauthoritative example embeds a frozen-looking value")

    if failures:
        for failure in failures:
            print(f"stand-bundle-check: FAIL: {failure}", file=sys.stderr)
        return 1
    print(
        "stand-bundle-check: PASS "
        f"({len(declared)} files, {profile}, protocol {expected_protocol}, "
        "dynamic/pilot/confirmatory prohibited)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
