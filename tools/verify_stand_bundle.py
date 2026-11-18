#!/usr/bin/env python3
"""Verify a cleanly extracted Stage 16 stand bundle without mutating the host."""

from __future__ import annotations

import argparse
import ast
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


def daycap_admission_tuple(profile, controller):
    """Select explicit qualification tuples; historical manifests keep their route."""
    if (profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            and isinstance(controller, dict)
            and isinstance(controller.get("policy"), dict)
            and controller["policy"].get("path") ==
                "config/stage17/stage17-operational-evidence-admission-policy-v62.json"):
        return (62, 36, 36,
                "STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v4",
                "tools/stage17_phase_controller_daycap_v4.py")
    if (profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            and isinstance(controller, dict)
            and isinstance(controller.get("policy"), dict)
            and controller["policy"].get("path") ==
                "config/stage17/stage17-operational-evidence-admission-policy-v61.json"):
        return (61, 35, 35,
                "STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v3",
                "tools/stage17_phase_controller_daycap_v3.py")
    if (profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            and isinstance(controller, dict)
            and isinstance(controller.get("policy"), dict)
            and controller["policy"].get("path") ==
                "config/stage17/stage17-operational-evidence-admission-policy-v60.json"):
        return (60, 34, 34,
                "STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v2",
                "tools/stage17_phase_controller_daycap_v2.py")
    if (profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            and isinstance(controller, dict)
            and isinstance(controller.get("policy"), dict)
            and controller["policy"].get("path") ==
                "config/stage17/stage17-operational-evidence-admission-policy-v59.json"):
        return (59, 33, 33,
                "STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v1",
                "tools/stage17_phase_controller_daycap_v1.py")
    return None


def diagnostic_runtime_closure_errors(root, policy):
    """Check the exact local import graph and import the bundled projection alone."""
    failures = []
    declared = {item["path"] for item in policy["runtime_closure"].values()}
    pending = list(policy["runtime_import_roots"])
    discovered = set()
    while pending:
        name = pending.pop()
        relative = "tools/" + name + ".py"
        if relative in discovered:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            return ["diagnostic runtime import absent: " + relative]
        discovered.add(relative)
        for node in ast.walk(ast.parse(path.read_text(), filename=relative)):
            names = ([item.name.split(".")[0] for item in node.names]
                     if isinstance(node, ast.Import) else
                     [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            for child in names:
                if child.startswith("stage17_") or (root / "tools" / (child + ".py")).is_file():
                    pending.append(child)
    if discovered != declared:
        return ["diagnostic runtime closure differs from all local imports"]
    code = ("import importlib,json,pathlib,sys; "
            "sys.path.insert(0,sys.argv[1]); "
            "[importlib.import_module(name) for name in json.loads(sys.argv[2])]")
    try:
        completed = subprocess.run([sys.executable, "-I", "-B", "-c", code,
            str(root / "tools"), json.dumps(sorted(pathlib.PurePosixPath(path).stem for path in declared))],
            cwd=root, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=45, check=False)
    except (OSError, subprocess.SubprocessError) as exception:
        return ["diagnostic isolated runtime import failed: " + str(exception)]
    if completed.returncode:
        failures.append("diagnostic isolated runtime import failed: " + completed.stderr.decode(errors="replace")[-2000:])
    return failures


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
    formal = profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v26", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
    if formal:
        import stage17_archive_bundle_profile_v1 as archive_profile
        try:
            document = archive_profile.verify_profile(bundle_root=root)
            if manifest.get("stage17_archive_implementation") != archive_profile.manifest_binding(
                    bundle_root=root, document=document):
                raise ValueError("archive implementation manifest binding differs")
            sbom = json.loads((root / "SBOM.spdx.json").read_text())
            if not any(p.get("name") == "zstd" and "1.5.7" in p.get("versionInfo", "")
                       for p in sbom.get("packages", [])):
                raise ValueError("archive zstd1.5.7 SBOM dependency missing")
        except (ValueError, OSError, KeyError, TypeError) as exception:
            failures.append("formal archive profile rejected: " + str(exception))
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
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3": (
            "cpu-prefetch-pilot-candidate-bundle/6",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4": (
            "cpu-prefetch-pilot-candidate-bundle/7",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v5": (
            "cpu-prefetch-pilot-candidate-bundle/5",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v6": (
            "cpu-prefetch-pilot-candidate-bundle/6",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v7": (
            "cpu-prefetch-pilot-candidate-bundle/7",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5": (
            "cpu-prefetch-pilot-candidate-bundle/8",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v8": (
            "cpu-prefetch-pilot-candidate-bundle/8",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6": (
            "cpu-prefetch-pilot-candidate-bundle/9",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v9": (
            "cpu-prefetch-pilot-candidate-bundle/9",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7": (
            "cpu-prefetch-pilot-candidate-bundle/10",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v10": (
            "cpu-prefetch-pilot-candidate-bundle/10",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8": (
            "cpu-prefetch-pilot-candidate-bundle/11",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v11": (
            "cpu-prefetch-pilot-candidate-bundle/11",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9": (
            "cpu-prefetch-pilot-candidate-bundle/12",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v12": (
            "cpu-prefetch-pilot-candidate-bundle/12",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10": (
            "cpu-prefetch-pilot-candidate-bundle/13",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v13": (
            "cpu-prefetch-pilot-candidate-bundle/13",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v14": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v15": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v16": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v17": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v18": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v19": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v20": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v21": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v22": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v23": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v24": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v25": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-PILOT-CANDIDATE-BUNDLE-v26": (
            "cpu-prefetch-pilot-candidate-bundle/14",
            "RELEASE_INPUT_READY_FOR_Q15_PREPARATION",
        ),
        "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22": (
            "cpu-prefetch-pilot-candidate-bundle/14",
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
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v9",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v10",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v11",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v12",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v13",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v14",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v15",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v16",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v17",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v18",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v19",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v20",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v21",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v22",
            "STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
            "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22",
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
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v9",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v10",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v11",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v12",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v13",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v14",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v15",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v16",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v17",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v18",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v19",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v20",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v21",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v22",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22") and value is not False:
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
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v9",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v10",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v11",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v12",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v13",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v14",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v15",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v16",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v17",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v18",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v19",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v20",
                   "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v21",
                   "STAGE17-PILOT-CANDIDATE-BUNDLE-v22",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"):
        if manifest.get("software_prefetch_mapping_id") not in (
            "X86-64-PREFETCHW-PREFETCHT0-v1",
            "X86-64-PREFETCHT0-ONLY-v1",
        ):
            failures.append("pilot candidate has no accepted D-047/ADR-0175 mapping identity")
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
            *(("formal_codegen_report.json",) if formal else ()),
            "queue_codegen_report.json",
            "workload_codegen_report.json",
            "timing_codegen_report.json",
            "storage_codegen_report.json",
            "runner_relax_codegen_report.json",
            "runner_combined_codegen_report.json",
            *(("discovery_codegen_report.json",) if profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"} else ()),
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
            if report == "formal_codegen_report.json":
                import check_formal_codegen as formal_codegen
                try:
                    formal_codegen.validate_report_bindings(report_document,
                        binary=root / "release/bin/cpu_prefetch_runner", source_root=root)
                except (formal_codegen.AuditError, OSError, ValueError, KeyError) as exception:
                    failures.append("formal codegen actual-worker/source binding failed: " + str(exception))
            if report == "discovery_codegen_report.json":
                import check_discovery_codegen as discovery_codegen
                try:
                    discovery_codegen.validate_report_bindings(report_document,
                        binary=root / "release/bin/cpu_prefetch_runner", source_root=root)
                except (discovery_codegen.AuditError, OSError, ValueError, KeyError) as exception:
                    failures.append("discovery codegen actual-worker/source binding failed: " + str(exception))
            if report == "runner_combined_codegen_report.json" and (
                report_document.get("schema_version")
                not in (
                    "cpu-prefetch-runner-combined-codegen/2",
                    "cpu-prefetch-runner-combined-codegen/3",
                )
                or report_document.get("software_prefetch_mapping_id")
                not in (
                    "X86-64-PREFETCHW-PREFETCHT0-v1",
                    "X86-64-PREFETCHT0-ONLY-v1",
                )
            ):
                failures.append(
                    "pilot candidate combined report lacks D-047/ADR-0175 identity"
                )
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
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v9",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v10",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v11",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v12",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v13",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v14",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v15",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v16",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v17",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v18",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v19",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v20",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v21",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v22",
                       "STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                       "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"):
            runtime = manifest.get("stage17_fixed_action_runtime")
            expected_actions = ["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c",
                                "STAGE17-BLINDED-PILOT"]
            worker = root / "release/bin/cpu_prefetch_runner"
            current_v5 = profile == "STAGE17-PILOT-CANDIDATE-BUNDLE-v5"
            current_v6 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
            }
            current_v7 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
            }
            current_v8 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
            }
            current_v9 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v9",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
            }
            current_v10 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v10",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
            }
            current_v11 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v11",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
            }
            current_v12 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v12",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
            }
            current_v13 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v13",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
            }
            current_v14 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v14",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
            }
            current_v15 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v15",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
            }
            current_v16 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v16",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
            }
            current_v17 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v17",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
            }
            current_v18 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v18",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
            }
            current_v19 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v19",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
            }
            current_v20 = profile in {
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v20",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
                # v21/dry-run-v18 add the real clock-qualification and
                # qualification-evidence tools to the bundle's release
                # binaries (ADR-0150) without touching the admission
                # policy/executor/preflight-plan chain, so they share v20's
                # generation rather than advancing it.
                "STAGE17-PILOT-CANDIDATE-BUNDLE-v21",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
            }
            # v22 (ADR-0159) raises the compiled fixed-action worker's
            # request-size bound (kMaximumRequestBytes, 16MiB -> 64MiB) so
            # Q16b's real ~35-47MB request can be admitted, and re-pins
            # this tool's own long-stale policy/controller/nested-policy
            # references (create_stand_bundle.py had been stuck at v39/
            # v9/v27 since ADR-0146, silently skipping ADR-0156 through
            # ADR-0158's own moves). No matching dry-run bundle profile
            # exists yet for this generation.
            current_v21 = profile == "STAGE17-PILOT-CANDIDATE-BUNDLE-v22"
            current_v25 = profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21"}
            current_v24 = profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20"}
            diagnostic = profile in {"STAGE17-PILOT-CANDIDATE-BUNDLE-v23", "STAGE17-PILOT-CANDIDATE-BUNDLE-v24", "STAGE17-PILOT-CANDIDATE-BUNDLE-v25", "STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
                                     "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"}
            if diagnostic:
                expected_actions.append("Q16A-DURATION-DISCOVERY")
            # The compiled worker binary (release/bin/cpu_prefetch_runner) is
            # unaffected by the D-124/D-125/D-126/D-127/D-128/D-130/D-131/
            # D-132/D-133/D-134/D-135/D-136/D-137/D-138/D-139/D-140/D-141/
            # D-142/D-143/D-144/D-145/D-146 admission-side changes v5/v6/
            # v7/v8/v9/v10/v11/v12/v13/v14/v15/v16/v17/v18/v19/v20 seal, so
            # its own runtime identity stays at its unchanged v4 compiled-
            # in strings even under bundle profile v5..v20. Only the
            # admission-side policy/
            # executor/controller identity below advances -- v6 (and the
            # matching dry-run v3) promoted phase-controller v9 (ADR-0127)
            # and operational policy v21; v7 (and dry-run v4) further
            # promotes operational policy v22 (ADR-0128, real S17-EXT-006
            # profile recognition); v8 (and dry-run v5) further promotes
            # operational policy v24 (ADR-0130, executor journal-
            # reachability fix), which also advances the executor and
            # preflight-plan-policy identity to v14/v16 for the first time
            # since ADR-0126's v13/v15; v9 (and dry-run v6) further
            # promotes operational policy v25 (ADR-0131, process-group
            # supervisor kernel-thread tolerance), which also advances the
            # executor and preflight-plan-policy identity to v15/v17; v10
            # (and dry-run v7) further promotes operational policy v26
            # (ADR-0132, OpenSSH snapshot mechanism identity), which also
            # advances the executor and preflight-plan-policy identity to
            # v16/v18; v11 (and dry-run v8) further promotes operational
            # policy v27 (ADR-0133, OpenSSH snapshot broker re-export
            # completeness), which also advances the executor and
            # preflight-plan-policy identity to v17/v19; v12 (and dry-run
            # v9) further promotes operational policy v28 (ADR-0134,
            # preflight archive-identity source), which also advances the
            # executor and preflight-plan-policy identity to v18/v20 (the
            # semantic verifier itself also moves, for the first time
            # since ADR-0126, but that identity is not tracked in this
            # ladder); v13 (and dry-run v10) further promotes operational
            # policy v29 (ADR-0135, preflight runtime-tool symlink
            # identity), which also advances the executor and preflight-
            # plan-policy identity to v19/v21 (the collector identity
            # moves too, for the first time this ladder has ever tracked
            # it, but is not itself tracked here); v14 (and dry-run v11)
            # further promotes operational policy v30 (ADR-0136, S17-
            # EXT-002 preflight role schema versions) -- this one does not
            # touch the preflight-plan policy or executor at all, so
            # nested_policy_version/executor_version stay at v13's own
            # v21/v19 values for v14 too; v15 (and dry-run v12) further
            # promotes operational policy v31 (ADR-0137, executor journal-
            # reachability follow-up), which advances the executor and
            # preflight-plan-policy identity to v20/v22 (completing the
            # lockstep move v14 itself left incomplete); v16 (and dry-run
            # v13) further promotes operational policy v33 (ADR-0139,
            # completing the same reachability lockstep ADR-0138's own
            # operational policy v32 -- S17-EXT-002 manifest schema-binding
            # completion, not itself tracked in this ladder -- left
            # incomplete), which advances the executor and preflight-plan-
            # policy identity to v21/v23; v17 (and dry-run v14) further
            # promotes operational policy v35 (ADR-0141, completing the
            # same reachability lockstep ADR-0140's own operational policy
            # v34 -- S17-EXT-002 preflight receipt-to-artifact pairing,
            # not itself tracked in this ladder -- left incomplete), which
            # advances the executor and preflight-plan-policy identity to
            # v22/v24; v18 (and dry-run v15) further promotes operational
            # policy v37 (ADR-0144, completing the same reachability
            # lockstep ADR-0143's own operational policy v36 -- pinning
            # the phase-controller/Q15-session-controller entrypoints
            # ADR-0142 left untracked, not itself tracked in this ladder --
            # left incomplete), which advances the executor and preflight-
            # plan-policy identity to v23/v25; v19 (and dry-run v16)
            # further promotes operational policy v38 (ADR-0145, a real
            # Q15 session failure-retention schema fix folding its own
            # bindings-completion and reachability lockstep into the same
            # generation rather than a separate follow-up ADR), which
            # advances the executor and preflight-plan-policy identity to
            # v24/v26; v20 (and dry-run v17) further promotes operational
            # policy v39 (ADR-0146, a real Q15 session execute_session
            # wiring fix -- ADR-0145's own rebind never reached run_
            # start's real call site -- again folding its own bindings-
            # completion and reachability lockstep into the same
            # generation), which advances the executor and preflight-
            # plan-policy identity to v25/v27.
            current_v4 = (
                current_v5 or current_v6 or current_v7 or current_v8
                or current_v9 or current_v10 or current_v11 or current_v12
                or current_v13 or current_v14 or current_v15 or current_v16
                or current_v17 or current_v18 or current_v19 or current_v20
                or current_v21 or diagnostic
                or profile in {
                    "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
                    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                }
            )
            version = 4 if current_v4 else 3
            controller_version = (
                26 if formal else 24 if current_v25 else 23 if current_v24 else 22 if diagnostic else 15 if current_v21
                else 9 if (current_v6 or current_v7 or current_v8 or current_v9
                      or current_v10 or current_v11 or current_v12 or current_v13
                      or current_v14 or current_v15 or current_v16 or current_v17
                      or current_v18 or current_v19 or current_v20)
                else 8 if current_v4 else version
            )
            admission_policy_version = (
                58 if formal else 57 if current_v25 else 56 if current_v24 else 55 if diagnostic else 53 if current_v21
                else 39 if current_v20
                else 38 if current_v19
                else 37 if current_v18
                else 35 if current_v17
                else 33 if current_v16
                else 31 if current_v15
                else 30 if current_v14
                else 29 if current_v13
                else 28 if current_v12
                else 27 if current_v11
                else 26 if current_v10
                else 25 if current_v9
                else 24 if current_v8
                else 22 if current_v7
                else 21 if current_v6
                else 20 if current_v5
                else 18 if current_v4
                else 11
            )
            nested_policy_version = (
                32 if formal else 31 if current_v25 else 30 if current_v24 else 28 if (current_v21 or diagnostic)
                else 27 if current_v20
                else 26 if current_v19
                else 25 if current_v18
                else 24 if current_v17
                else 23 if current_v16
                else 22 if current_v15
                else 21 if (current_v13 or current_v14)
                else 20 if current_v12
                else 19 if current_v11
                else 18 if current_v10
                else 17 if current_v9
                else 16 if current_v8
                else 15 if (current_v5 or current_v6 or current_v7) else 14
            )
            executor_version = (
                32 if formal else 31 if current_v25 else 30 if current_v24 else 26 if (current_v21 or diagnostic)
                else 25 if current_v20
                else 24 if current_v19
                else 23 if current_v18
                else 22 if current_v17
                else 21 if current_v16
                else 20 if current_v15
                else 19 if (current_v13 or current_v14)
                else 18 if current_v12
                else 17 if current_v11
                else 16 if current_v10
                else 15 if current_v9
                else 14 if current_v8
                else 13 if (current_v5 or current_v6 or current_v7) else 12
            )
            expected_synthetic = profile in {"STAGE17-HERMETIC-DRY-RUN-BUNDLE-v19", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v20", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v21", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22"} or profile in {
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v1",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v6",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v7",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v9",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v10",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v11",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v12",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v13",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v14",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v15",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v16",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v17",
                "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v18",
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
                          *( (b"--execute-fixed-stage17-action-v5",) if diagnostic else () ),
                          *( (b"--describe-stage17-discovery-layout-v2",) if (current_v25 or formal) else () ),
                          *((b"--execute-fixed-stage17-action-v6",) if formal else ()),
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
            controller_id = f"STAGE17-FIXED-ACTION-PHASE-CONTROLLER-v{controller_version}"
            controller_entrypoint = f"tools/stage17_phase_controller_v{controller_version}.py"
            selected = daycap_admission_tuple(profile, controller)
            if selected is not None:
                (admission_policy_version, nested_policy_version, executor_version,
                 controller_id, controller_entrypoint) = selected
            policy_path = root / (
                "config/stage17/"
                f"stage17-operational-evidence-admission-policy-v{admission_policy_version}.json"
            )
            if (not isinstance(controller, dict)
                    or controller.get("controller_id")
                    != controller_id
                    or controller.get("entrypoint")
                    != controller_entrypoint
                    or controller.get("invocation")
                    != ["python3", controller_entrypoint]
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
                    "stage17-read-only-preflight-evidence-admission-policy-"
                    f"v{nested_policy_version}.json"
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
                if diagnostic:
                    failures.extend(diagnostic_runtime_closure_errors(root, policy))
                for relative in (
                    f"tools/stage17_read_only_preflight_executor_v{executor_version}.py",
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
