#!/usr/bin/env python3
"""Verify a cleanly extracted Stage 16 stand bundle without mutating the host."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def q15_profile_errors(
    manifest: dict[str, object], release_paths: set[str | None], *, controller_v2: bool
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
        if "release/bin/cpu_prefetch_q15_controller" not in release_paths:
            failures.append("Q15 controller bundle misses controller executable")
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
        "Q15-QUALIFICATION-TOOL-BUNDLE-v1": (
            "cpu-prefetch-q15-qualification-tool-bundle/1",
            "Q15_TOOL_RELEASE_NO_AUTHORITY",
        ),
        "Q15-QUALIFICATION-TOOL-BUNDLE-v2": (
            "cpu-prefetch-q15-qualification-tool-bundle/2",
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
    if manifest.get("protocol_version") != "2.0.0-pre.2":
        failures.append("wrong protocol version")
    protocol_manifest = root / "protocol" / "2.0.0-pre.2" / "IMPORT_MANIFEST.json"
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
        if profile == "STAGE17-PILOT-CANDIDATE-BUNDLE-v1" and value is not False:
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

    if profile == "STAGE17-PILOT-CANDIDATE-BUNDLE-v1":
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

    if profile in (
        "Q15-QUALIFICATION-TOOL-BUNDLE-v1",
        "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
    ):
        controller_v2 = profile == "Q15-QUALIFICATION-TOOL-BUNDLE-v2"
        failures.extend(
            q15_profile_errors(manifest, release_paths, controller_v2=controller_v2)
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
        f"({len(declared)} files, {profile}, protocol 2.0.0-pre.2, "
        "dynamic/pilot/confirmatory prohibited)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
