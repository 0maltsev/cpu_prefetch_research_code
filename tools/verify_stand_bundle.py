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
