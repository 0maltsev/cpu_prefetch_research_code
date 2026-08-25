#!/usr/bin/env python3
"""Create deterministic preflight, pilot-candidate, or Q15 tool bundles."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from typing import Any


STAGE16_PROFILE = "STAGE16-STAND-BUNDLE-v1"
STAGE17_PROFILE = "STAGE17-PILOT-CANDIDATE-BUNDLE-v1"
Q15_TOOL_PROFILE = "Q15-QUALIFICATION-TOOL-BUNDLE-v2"
STAGE17_CODEGEN_INPUTS = {
    "queue_codegen_report.json": (
        "cpu_prefetch_queue_codegen_probe",
        "check_queue_codegen.py",
    ),
    "workload_codegen_report.json": (
        "cpu_prefetch_workload_codegen_probe",
        "check_workload_codegen.py",
    ),
    "timing_codegen_report.json": (
        "cpu_prefetch_timing_codegen_probe",
        "check_timing_codegen.py",
    ),
    "storage_codegen_report.json": (
        "cpu_prefetch_storage_codegen_probe",
        "check_storage_codegen.py",
    ),
    "runner_relax_codegen_report.json": (
        "cpu_prefetch_runner_codegen_probe",
        "check_runner_codegen.py",
    ),
    "runner_combined_codegen_report.json": (
        "cpu_prefetch_runner_combined_codegen_probe",
        "check_runner_combined_codegen.py",
    ),
}
Q15_CODEGEN_INPUTS = {
    "q15_controller_codegen_report.json": (
        "cpu_prefetch_q15_controller_codegen_probe",
        "check_q15_controller_codegen.py",
    ),
    "q15_probe_codegen_report.json": (
        "cpu_prefetch_q15_probe_codegen_probe",
        "check_q15_probe_codegen.py",
    ),
    "q15_runtime_codegen_report.json": (
        "cpu_prefetch_q15_runtime_codegen_probe",
        "check_q15_runtime_codegen.py",
    ),
}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(root: pathlib.Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=root, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()


def source_paths(root: pathlib.Path) -> list[pathlib.Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    paths = [pathlib.Path(item.decode("utf-8")) for item in output.split(b"\0") if item]
    return sorted(path for path in paths if (root / path).is_file())


def add_file(archive: tarfile.TarFile, source: pathlib.Path, name: str) -> None:
    info = archive.gettarinfo(str(source), arcname=name)
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = 0
    info.mode = 0o755 if os.access(source, os.X_OK) else 0o644
    with source.open("rb") as stream:
        archive.addfile(info, stream)


def deterministic_tar(output: pathlib.Path, entries: list[tuple[pathlib.Path, str]]) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.GNU_FORMAT) as archive:
                for source, name in sorted(entries, key=lambda item: item[1]):
                    add_file(archive, source, name)


def copy_tree_files(source: pathlib.Path, destination: pathlib.Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(0o755 if os.access(path, os.X_OK) else 0o644)


def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def normalize_report_paths(value: Any, root: pathlib.Path, build: pathlib.Path) -> Any:
    if isinstance(value, str):
        return value.replace(str(build), "<BUILD_DIR>").replace(
            str(root), "<SOURCE_ROOT>"
        )
    if isinstance(value, list):
        return [normalize_report_paths(item, root, build) for item in value]
    if isinstance(value, dict):
        return {
            normalize_report_paths(key, root, build): normalize_report_paths(
                item, root, build
            )
            for key, item in value.items()
        }
    return value


def normalized_ldd_output(output: str) -> str:
    """Remove per-process loader addresses while retaining resolved identities."""
    return re.sub(r"[ \t]+\(0x[0-9A-Fa-f]+\)(?=\n|$)", "", output)


def verify_codegen_report(
    root: pathlib.Path,
    build: pathlib.Path,
    report_path: pathlib.Path,
    probe_name: str,
    rule_name: str,
) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS":
        raise ValueError(
            f"pilot-candidate codegen report is not PASS: "
            f"{report_path.name}={report.get('status')}"
        )
    if report.get("missing_tools") != []:
        raise ValueError(f"pilot-candidate codegen tools incomplete: {report_path.name}")
    probe = build / probe_name
    if not probe.is_file():
        raise ValueError(f"pilot-candidate codegen probe is missing: {probe_name}")
    binary_hash = report.get("binary_sha256")
    if binary_hash is None:
        binary_hash = report.get("binary", {}).get("sha256")
    if binary_hash != sha256(probe):
        raise ValueError(f"pilot-candidate codegen binary drift: {report_path.name}")
    rule_hash = report.get("rule_set_sha256")
    if rule_hash is None:
        rule_hash = report.get("rule_set", {}).get("sha256")
    if rule_hash != sha256(root / "tools" / rule_name):
        raise ValueError(f"pilot-candidate codegen rule drift: {report_path.name}")
    return report


def make_sbom(
    root: pathlib.Path, dependencies: dict[str, Any], revision: str, profile: str
) -> dict[str, Any]:
    packages: list[dict[str, Any]] = [
        {
            "SPDXID": "SPDXRef-Repository",
            "copyrightText": "NOASSERTION",
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "name": "cpu-prefetch-research-code",
            "versionInfo": revision,
        }
    ]
    relationships: list[dict[str, str]] = []
    for dependency in dependencies["dependencies"]:
        spdx_id = "SPDXRef-Dependency-" + "".join(
            character if character.isalnum() else "-" for character in dependency["id"]
        )
        packages.append(
            {
                "SPDXID": spdx_id,
                "copyrightText": "NOASSERTION",
                "downloadLocation": dependency["source"],
                "filesAnalyzed": False,
                "licenseConcluded": dependency["license"],
                "licenseDeclared": dependency["license"],
                "name": dependency["id"],
                "summary": dependency["purpose"],
                "versionInfo": dependency["version_rule"],
            }
        )
        relationships.append(
            {
                "relatedSpdxElement": spdx_id,
                "relationshipType": "DEPENDS_ON",
                "spdxElementId": "SPDXRef-Repository",
            }
        )
    return {
        "SPDXID": "SPDXRef-DOCUMENT",
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: create_stand_bundle.py"],
        },
        "dataLicense": "CC0-1.0",
        "documentNamespace": f"https://example.invalid/cpu-prefetch/sbom/{revision}",
        "name": {
            STAGE17_PROFILE: "cpu-prefetch-stage17-pilot-candidate",
            Q15_TOOL_PROFILE: "cpu-prefetch-q15-qualification-tool",
        }.get(profile, "cpu-prefetch-stage16-stand-bundle"),
        "packages": packages,
        "relationships": relationships,
        "spdxVersion": "SPDX-2.3",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=pathlib.Path, required=True)
    parser.add_argument("--build-dir", type=pathlib.Path, required=True)
    parser.add_argument("--output-dir", type=pathlib.Path, required=True)
    parser.add_argument(
        "--profile",
        choices=(
            "stage16-preflight",
            "stage17-pilot-candidate",
            "q15-qualification-tool",
        ),
        default="stage16-preflight",
    )
    args = parser.parse_args()
    root = args.source_root.resolve()
    build = args.build_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    revision = git(root, "rev-parse", "HEAD")
    revision_short = revision[:7]
    dirty = bool(git(root, "status", "--porcelain=v1"))
    source_state = "dirty" if dirty else "clean"
    stage17 = args.profile == "stage17-pilot-candidate"
    q15_tool = args.profile == "q15-qualification-tool"
    profile = (
        STAGE17_PROFILE
        if stage17
        else Q15_TOOL_PROFILE if q15_tool else STAGE16_PROFILE
    )
    if (stage17 or q15_tool) and dirty:
        raise ValueError(
            f"{profile} requires a clean exact source revision"
        )
    version_metadata = json.loads(
        (build / "generated" / "version_metadata.json").read_text(encoding="utf-8")
    )
    if version_metadata["protocol_version"] != "2.0.0-pre.2":
        raise ValueError("release metadata is not bound to protocol 2.0.0-pre.2")
    if version_metadata["source_revision"] != revision:
        raise ValueError("release metadata revision differs from the source tree")

    required_binaries = ["cpu_prefetch_smoke", "cpu_prefetch_preflight"]
    if stage17:
        required_binaries.extend(
            ["cpu_prefetch_runner", "cpu_prefetch_qualification"]
        )
    if q15_tool:
        required_binaries.extend(
            [
                "cpu_prefetch_qualification",
                "cpu_prefetch_q15_controller",
                "cpu_prefetch_q15_tool",
            ]
        )
        q15_library_names = {
            "libcpu_prefetch_foundation.a",
            "libcpu_prefetch_platform.a",
            "libcpu_prefetch_protocol.a",
            "libcpu_prefetch_q15_qualification.a",
            "libcpu_prefetch_workload.a",
        }
        required_libraries = sorted(
            library
            for library in build.glob("libcpu_prefetch_*.a")
            if library.name in q15_library_names
        )
    else:
        required_libraries = sorted(
            library
            for library in build.glob("libcpu_prefetch_*.a")
            if stage17 or library.name != "libcpu_prefetch_runner_core.a"
        )
    for name in required_binaries:
        if not (build / name).is_file():
            raise ValueError(f"missing release binary: {name}")
    if not required_libraries:
        raise ValueError("release libraries are absent")

    codegen_reports: list[pathlib.Path] = []
    if stage17:
        for name, (probe_name, rule_name) in STAGE17_CODEGEN_INPUTS.items():
            path = build / name
            if not path.is_file():
                raise ValueError(f"missing pilot-candidate codegen report: {name}")
            verify_codegen_report(root, build, path, probe_name, rule_name)
            codegen_reports.append(path)
    if q15_tool:
        for name, (probe_name, rule_name) in Q15_CODEGEN_INPUTS.items():
            path = build / name
            if not path.is_file():
                raise ValueError(f"missing Q15 codegen report: {name}")
            verify_codegen_report(root, build, path, probe_name, rule_name)
            codegen_reports.append(path)

    with tempfile.TemporaryDirectory(
        prefix=(
            "cpu-prefetch-stage17-"
            if stage17
            else "cpu-prefetch-q15-tool-" if q15_tool else "cpu-prefetch-stage16-"
        )
    ) as temporary:
        staging = pathlib.Path(temporary) / "bundle"
        staging.mkdir()
        source_archive = staging / "source" / f"cpu-prefetch-source-{revision_short}-{source_state}.tar.gz"
        source_archive.parent.mkdir(parents=True)
        deterministic_tar(
            source_archive,
            [(root / path, f"cpu_prefetch_research_code/{path.as_posix()}") for path in source_paths(root)],
        )

        release_bin = staging / "release" / "bin"
        release_lib = staging / "release" / "lib"
        release_bin.mkdir(parents=True)
        release_lib.mkdir(parents=True)
        for name in required_binaries:
            shutil.copyfile(build / name, release_bin / name)
            (release_bin / name).chmod(0o755)
        for library in required_libraries:
            shutil.copyfile(library, release_lib / library.name)

        provenance = staging / "build-provenance"
        provenance.mkdir()
        shutil.copyfile(build / "generated" / "version_metadata.json", provenance / "version_metadata.json")
        shutil.copyfile(build / "compile_commands.json", provenance / "compile_commands.json")
        for report in codegen_reports:
            write_json(
                provenance / report.name,
                normalize_report_paths(
                    json.loads(report.read_text(encoding="utf-8")), root, build
                ),
            )
        runtime_lines: list[str] = []
        for name in required_binaries:
            completed = subprocess.run(
                ["ldd", str(build / name)], check=True, text=True, stdout=subprocess.PIPE
            )
            runtime_lines.append(f"[{name}]\n{normalized_ldd_output(completed.stdout)}")
        (provenance / "runtime-dependencies.txt").write_text(
            "\n".join(runtime_lines), encoding="utf-8"
        )

        copy_tree_files(root / "protocol" / "2.0.0-pre.2", staging / "protocol" / "2.0.0-pre.2")
        copy_tree_files(root / "config" / "schemas", staging / "config" / "schemas" / "implementation")
        copy_tree_files(
            root / "protocol" / "2.0.0-pre.2" / "handoff" / "schemas",
            staging / "config" / "schemas" / "imported",
        )
        copy_tree_files(root / "config" / "examples", staging / "config" / "examples")
        if q15_tool:
            copy_tree_files(root / "config" / "q15", staging / "config" / "q15")
            for relative in (
                pathlib.Path(
                    "docs/evidence/stage16/"
                    "STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02/"
                    "STAND-PREFLIGHT-XEON-CPU-FETCH-20260822-02.json"
                ),
                pathlib.Path(
                    "docs/evidence/stage16/"
                    "STAND-TOPOLOGY-XEON-CPU-FETCH-20260822-01/SHA256SUMS"
                ),
                pathlib.Path(
                    "docs/evidence/stage16/"
                    "STAND-STORAGE-XEON-CPU-FETCH-20260822-01/SHA256SUMS"
                ),
            ):
                target = staging / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(root / relative, target)
        licenses = staging / "licenses"
        licenses.mkdir()
        shutil.copyfile(root / "config" / "dependencies.json", licenses / "dependencies.json")
        shutil.copyfile(root / "docs" / "NO_LICENSE_GRANT.md", licenses / "NO_LICENSE_GRANT.md")
        documents = [
            "PRE_PILOT_READINESS_REPORT.md",
            "STAND_BUNDLE.md",
            "STAND_RUNBOOK.md",
        ]
        if stage17:
            documents.extend(
                [
                    "PRODUCTION_RUNNER.md",
                    "STAGE17_PILOT_AUTHORIZATION_DECISION_BUNDLE.md",
                ]
            )
        if q15_tool:
            documents.extend(
                [
                    "PLATFORM_CONTROL.md",
                    "Q15_DYNAMIC_IMPLEMENTATION_DECISION_BUNDLE.md",
                    "Q15_PREREQUISITE_CLOSURE.md",
                    "Q15_QUALIFICATION_CONTRACT.md",
                    "Q15_QUALIFICATION_TOOL.md",
                    "Q15_R_CONTROLLER.md",
                    "Q15_R_DECISION_INPUT_BUNDLE.md",
                    "Q15_R_ROLE_CUSTODY_SETUP_PLAN.md",
                    "Q15_STAND_QUALIFICATION_DECISION_BUNDLE.md",
                ]
            )
        for document in documents:
            target = staging / "docs" / document
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / "docs" / document, target)

        validator_names = [
            "check_calibration_schemas.py",
            "check_canonical.py",
            "check_orchestration_schemas.py",
            "check_protocol.py",
            "check_protocol_fixtures.py",
            "check_reconciliation_schema.py",
            "check_storage_schemas.py",
            "verify_stand_bundle.py",
        ]
        if stage17:
            validator_names.extend(
                [
                    "check_qualification_schema.py",
                    "check_hardware_prefetch_schema.py",
                    "check_runner_schema.py",
                    "check_stage17_authorization_schema.py",
                ]
            )
        if q15_tool:
            validator_names.extend(
                [
                    "check_hardware_prefetch_schema.py",
                    "check_q15_authorization_schema.py",
                    "check_q15_authorization_v2.py",
                    "check_q15_controller_codegen.py",
                    "check_q15_controller_profile.py",
                    "check_q15_r_decision_input.py",
                    "check_q15_dynamic_implementation.py",
                    "check_q15_probe_collector_contract.py",
                    "check_q15_probe_implementation.py",
                    "check_qualification_schema.py",
                    "check_stage17_authorization_schema.py",
                ]
            )
        validators = staging / "validators"
        validators.mkdir()
        for name in validator_names:
            shutil.copyfile(root / "tools" / name, validators / name)
            (validators / name).chmod(0o755)
        copy_tree_files(root / "tests" / "fixtures", staging / "tests" / "fixtures")

        dependencies = json.loads(
            (root / "config" / "dependencies.json").read_text(encoding="utf-8")
        )
        write_json(
            staging / "SBOM.spdx.json",
            make_sbom(root, dependencies, revision, profile),
        )

        release_artifacts = []
        for path in sorted((staging / "release").rglob("*")):
            if path.is_file():
                release_artifacts.append(
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "sha256": sha256(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
        manifest = {
            "bundle_profile": profile,
            "confirmatory_authorized": False,
            "debug_symbol_strategy":
                "UNSTRIPPED_RELEASE_BINARIES_WITH_EXACT_BUILD_PROVENANCE",
            "dynamic_qualification_authorized": False,
            "measurement_execution_command_present": False,
            "pilot_authorized": False,
            "protocol_import_manifest_sha256": sha256(
                root / "protocol" / "2.0.0-pre.2" / "IMPORT_MANIFEST.json"
            ),
            "protocol_version": "2.0.0-pre.2",
            "readiness_state": (
                "RELEASE_INPUT_READY_FOR_Q15_PREPARATION"
                if stage17
                else "Q15_TOOL_RELEASE_NO_AUTHORITY"
                if q15_tool
                else "READY_FOR_STAND_PREFLIGHT"
            ),
            "release_artifacts": release_artifacts,
            "repository_license": "NO-LICENSE-GRANT",
            "schema_version": (
                "cpu-prefetch-pilot-candidate-bundle/1"
                if stage17
                else "cpu-prefetch-q15-qualification-tool-bundle/2"
                if q15_tool
                else "cpu-prefetch-stand-bundle/1"
            ),
            "source_archive": {
                "path": source_archive.relative_to(staging).as_posix(),
                "sha256": sha256(source_archive),
                "source_dirty": dirty,
                "source_revision": revision,
            },
            "unresolved_before_pilot": (
                [
                    "exact Q15 stand-qualification authorization and evidence",
                    "two exact start-barrier limits, an external process-watchdog record, and every platform/control/restoration record",
                    "clock, atomic/layout, actual-CPU/migration, address-residency, and storage/custody evidence",
                    "separate dependency-ready Q16 phase inputs and authorization",
                ]
                if stage17
                else [
                    "separately signed exact Q15-R authorization before any dynamic read or collection",
                    "clean release hashes and exact authorized Q15-R/Q15-W argv binding the implemented dynamic probe and seven collectors",
                    "sealed Q15-R evidence and complete CPU 0/1/26 prestates before Q15-W",
                    "separately signed exact Q15-W authorization before any MSR write",
                    "four effective roles, negative access evidence, exact limits, custody, and restoration policy",
                ]
                if q15_tool
                else [
                    "production measurement executable and final integrated worker codegen",
                    "eligible stand, selected worker pairs, and runtime atomic checks",
                    "privileged authority, exact controls, independent readback, probes, and restoration",
                    "clock, address residency, storage domains/capacity/custody, and recovery evidence",
                    "prospective calibration and pilot inputs and authorization",
                ]
            ),
        }
        if stage17:
            manifest["software_prefetch_mapping_id"] = (
                "X86-64-PREFETCHW-PREFETCHT0-v1"
            )
        if q15_tool:
            probe_contract_path = (
                root / "config" / "q15" / "q15-probe-collector-contract-v1.json"
            )
            probe_profile_path = (
                root / "config" / "q15" / "q15-probe-implementation-profile-v1.json"
            )
            dynamic_profile_path = (
                root / "config" / "q15" / "q15-dynamic-implementation-profile-v1.json"
            )
            controller_profile_path = (
                root / "config" / "q15" / "q15-r-controller-profile-v1.json"
            )
            authorization_schema_path = (
                root
                / "config"
                / "schemas"
                / "q15-qualification-authorization-v2.schema.json"
            )
            setup_plan_path = (
                root
                / "config"
                / "q15"
                / "q15-r-role-custody-setup-plan-v1.json"
            )
            manifest.update(
                {
                    "account_or_key_changes_authorized": False,
                    "authorization_v2_contract": {
                        "path": (
                            "config/schemas/implementation/"
                            "q15-qualification-authorization-v2.schema.json"
                        ),
                        "schema_version": (
                            "cpu-prefetch-q15-qualification-authorization/2"
                        ),
                        "sha256": sha256(authorization_schema_path),
                    },
                    "bundle_transfer_or_install_authorized": False,
                    "calibration_authorized": False,
                    "controller_profile": {
                        "path": "config/q15/q15-r-controller-profile-v1.json",
                        "profile_id": "Q15-R-STATIC-CONTROLLER-v1",
                        "sha256": sha256(controller_profile_path),
                    },
                    "dynamic_implementation_profile": {
                        "profile_id": "Q15-DYNAMIC-IMPLEMENTATION-PROFILE-v1",
                        "path": "config/q15/q15-dynamic-implementation-profile-v1.json",
                        "sha256": sha256(dynamic_profile_path),
                    },
                    "hardware_prefetch_mapping_id": "INTEL-06_55H-MSR-1A4-DISABLE-0_3-v1",
                    "measurement_authorized": False,
                    "msr_read_authorized": False,
                    "msr_write_authorized": False,
                    "probe_collector_contract": {
                        "contract_id": "Q15-PROBE-COLLECTOR-CONTRACT-v1",
                        "path": "config/q15/q15-probe-collector-contract-v1.json",
                        "sha256": sha256(probe_contract_path),
                    },
                    "probe_implementation_profile": {
                        "profile_id": "Q15-PROBE-IMPLEMENTATION-PROFILE-v1",
                        "path": "config/q15/q15-probe-implementation-profile-v1.json",
                        "sha256": sha256(probe_profile_path),
                    },
                    "qualification_tool_profile_id": "Q15-FIXED-QUALIFICATION-TOOL-v1",
                    "q15_r_authorized": False,
                    "q15_w_authorized": False,
                    "real_affinity_numa_authorized": False,
                    "real_pmu_authorized": False,
                    "role_custody_setup_plan": {
                        "path": "config/q15/q15-r-role-custody-setup-plan-v1.json",
                        "plan_id": "Q15-R-ROLE-CUSTODY-SETUP-PLAN-v1",
                        "sha256": sha256(setup_plan_path),
                        "status": "PREPARED_NO_STAND_AUTHORITY",
                    },
                    "scientific_schedule_access_authorized": False,
                    "stand_access_authorized": False,
                }
            )
        write_json(staging / "BUNDLE_MANIFEST.json", manifest)

        checksum_files = sorted(
            path
            for path in staging.rglob("*")
            if path.is_file() and path != staging / "SHA256SUMS"
        )
        (staging / "SHA256SUMS").write_text(
            "".join(
                f"{sha256(path)}  {path.relative_to(staging).as_posix()}\n"
                for path in checksum_files
            ),
            encoding="utf-8",
        )

        source_hash_short = sha256(source_archive)[:12]
        bundle_prefix = (
            "cpu-prefetch-pilot-candidate"
            if stage17
            else "cpu-prefetch-q15-qualification-tool"
            if q15_tool
            else "cpu-prefetch-stand-bundle"
        )
        bundle_name = (
            f"{bundle_prefix}-2.0.0-{revision_short}-{source_state}-"
            f"{source_hash_short}.tar.gz"
        )
        output = output_dir / bundle_name
        if output.exists() or output.with_suffix(output.suffix + ".sha256").exists():
            raise FileExistsError(f"append-only bundle output already exists: {output}")
        top = bundle_name.removesuffix(".tar.gz")
        deterministic_tar(
            output,
            [(path, f"{top}/{path.relative_to(staging).as_posix()}") for path in staging.rglob("*") if path.is_file()],
        )
        outer_hash = sha256(output)
        output.with_suffix(output.suffix + ".sha256").write_text(
            f"{outer_hash}  {output.name}\n", encoding="utf-8"
        )
        print(
            f"{'pilot-candidate-bundle' if stage17 else 'q15-tool-bundle' if q15_tool else 'stand-bundle'}: "
            f"PASS path={output} sha256={outer_hash} authority=NONE"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
