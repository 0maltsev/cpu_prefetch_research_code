#!/usr/bin/env python3
"""Validate the proposed no-authority Q15-R operational-release decision."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import sys
from typing import Any

from jsonschema import Draft202012Validator


ARCHIVE_NAME = (
    "cpu-prefetch-q15-qualification-tool-2.0.0-"
    "c8b69ab-clean-8d27197443f2.tar.gz"
)
EXPECTED_RELEASE = {
    "archive_bytes": 4_356_358,
    "archive_name": ARCHIVE_NAME,
    "archive_sha256": "8e8ad6d781b2bffadcfc10cf3b12d5666c7a1d4c7d7e291d7318a19503e6ab01",
    "bundle_manifest_sha256": "e5636a34c5dc083cfa01daa00091ee0baafa840174dda6ac2bbd1903115b7ebf",
    "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v2",
    "controller_binary_sha256": "9bdda2b7eab5b4c50f82fc478f6c936a7a2bafffd85b05c68262360f3b04650d",
    "controller_codegen_report_sha256": "7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca",
    "internal_file_count": 133,
    "internal_sha256s_sha256": "b1c5d9cffa57d29800c97f51ecaea146139cb0624a379f38d50aab81a1c30281",
    "probe_codegen_report_sha256": "cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa",
    "q15_qualification_library_sha256": "c9eae879c66cda471b8bc2043bc6b61da21c64f008006ae969ab94faa44a27f0",
    "q15_tool_binary_sha256": "0b7afb5c0501c108c8ff17c3dbb319525d531b68e8a9b8d767f2ed0eab0a37d5",
    "repository_license": "NO-LICENSE-GRANT",
    "runtime_codegen_report_sha256": "e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014",
    "sbom_sha256": "77a4fd2f44fa4d6c8d214d4bfa5eb7231ed3a5597f83437b7fe84d9de42b65df",
    "sidecar_sha256": "b251133526412f620ec3c5d9685b201a4b0280bb4fabc2382636c2c4b04343f1",
    "source_archive_name": "cpu-prefetch-source-c8b69ab-clean.tar.gz",
    "source_archive_sha256": "8d27197443f2ed016e6ac7e3788a0660fadab84ffc78e31934f4092bbc143df7",
    "source_dirty": False,
    "source_revision": "c8b69abf0c6aec7b740efe78d998a93545302a94",
    "version_metadata_sha256": "7c9a6b7442a62beac9f3310e36ad997365269b24a34d86abb71ecfd3cebd27a0",
}
EXPECTED_REMAINING = (
    "@ALLOWED_SIGNERS_SOURCE@",
    "@OPERATIONAL_RELEASE_ROOT@",
    "@SECONDARY_CUSTODY_ROOT@",
    "CURRENT_STAND_PRESTATE_ARTIFACT_ID_AND_SHA256",
    "ACTUAL_ALLOWED_SIGNERS_ARTIFACT_ID_SHA256_AND_ED25519_FINGERPRINT",
)
EXTRACTED_BINDINGS = {
    "BUNDLE_MANIFEST.json": "bundle_manifest_sha256",
    "SBOM.spdx.json": "sbom_sha256",
    "SHA256SUMS": "internal_sha256s_sha256",
    "source/cpu-prefetch-source-c8b69ab-clean.tar.gz": "source_archive_sha256",
    "release/bin/cpu_prefetch_q15_controller": "controller_binary_sha256",
    "release/bin/cpu_prefetch_q15_tool": "q15_tool_binary_sha256",
    "release/lib/libcpu_prefetch_q15_qualification.a": (
        "q15_qualification_library_sha256"
    ),
    "build-provenance/version_metadata.json": "version_metadata_sha256",
    "build-provenance/q15_probe_codegen_report.json": (
        "probe_codegen_report_sha256"
    ),
    "build-provenance/q15_runtime_codegen_report.json": (
        "runtime_codegen_report_sha256"
    ),
    "build-provenance/q15_controller_codegen_report.json": (
        "controller_codegen_report_sha256"
    ),
}


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def semantic_errors(root: pathlib.Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if document.get("operational_release_evidence") != EXPECTED_RELEASE:
        errors.append("operational release evidence must match the exact verified bytes")
    decision = document.get("decision", {})
    if decision.get("decision_id") != "D-065" or decision.get("state") != (
        "PROPOSED_AWAITING_EXPLICIT_OWNER_ACCEPTANCE_NO_AUTHORITY"
    ):
        errors.append("D-065 must remain proposed until explicit owner acceptance")
    boundary = document.get("authority_boundary", {})
    authorized = {
        name
        for name, value in boundary.items()
        if name.endswith("_authorized") and value is True
    }
    if authorized != {"repository_local_record_synchronization_authorized"}:
        errors.append("proposal widens authority beyond repository-local records")
    remaining = document.get("remaining_required_inputs", [])
    if tuple(item.get("name") for item in remaining) != EXPECTED_REMAINING:
        errors.append("the five remaining input groups must be exact and ordered")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in remaining
    ):
        errors.append("external setup inputs cannot be fabricated or defaulted")
    predecessor = document.get("predecessor_preparation", {})
    predecessor_path = root / predecessor.get("path", "")
    if not predecessor_path.is_file() or sha256(predecessor_path) != predecessor.get(
        "sha256"
    ):
        errors.append("immutable predecessor preparation is missing or has drifted")
    return errors


def release_errors(
    document: dict[str, Any], archive_dir: pathlib.Path, extracted_root: pathlib.Path
) -> list[str]:
    errors: list[str] = []
    evidence = document["operational_release_evidence"]
    archive = archive_dir / ARCHIVE_NAME
    sidecar = archive_dir / f"{ARCHIVE_NAME}.sha256"
    if not archive.is_file() or archive.stat().st_size != evidence["archive_bytes"]:
        errors.append("operational archive is missing or has the wrong size")
    elif sha256(archive) != evidence["archive_sha256"]:
        errors.append("operational archive hash mismatch")
    if not sidecar.is_file() or sha256(sidecar) != evidence["sidecar_sha256"]:
        errors.append("operational sidecar is missing or has drifted")
    else:
        expected_line = f'{evidence["archive_sha256"]}  {ARCHIVE_NAME}\n'
        if sidecar.read_text(encoding="utf-8") != expected_line:
            errors.append("operational sidecar content mismatch")
    for relative, field in EXTRACTED_BINDINGS.items():
        path = extracted_root / relative
        if not path.is_file() or sha256(path) != evidence[field]:
            errors.append(f"extracted release binding mismatch: {relative}")
    sums = extracted_root / "SHA256SUMS"
    if sums.is_file() and len(sums.read_text(encoding="utf-8").splitlines()) != (
        evidence["internal_file_count"]
    ):
        errors.append("internal file count mismatch")
    if (extracted_root / "BUNDLE_MANIFEST.json").is_file():
        manifest = load(extracted_root / "BUNDLE_MANIFEST.json")
        if (
            manifest.get("source_archive", {}).get("source_revision")
            != evidence["source_revision"]
            or manifest.get("source_archive", {}).get("source_dirty") is not False
            or manifest.get("bundle_profile") != evidence["bundle_profile"]
        ):
            errors.append("bundle manifest release identity mismatch")
        forbidden = (
            "stand_access_authorized",
            "bundle_transfer_or_install_authorized",
            "q15_r_authorized",
            "q15_w_authorized",
            "real_pmu_authorized",
            "msr_read_authorized",
            "msr_write_authorized",
            "real_affinity_numa_authorized",
            "calibration_authorized",
            "pilot_authorized",
            "measurement_authorized",
            "confirmatory_authorized",
        )
        if any(manifest.get(name) is not False for name in forbidden):
            errors.append("bundle manifest grants forbidden authority")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-dir", type=pathlib.Path)
    parser.add_argument("--extracted-root", type=pathlib.Path)
    args = parser.parse_args()
    if (args.archive_dir is None) != (args.extracted_root is None):
        parser.error("--archive-dir and --extracted-root must be supplied together")

    root = pathlib.Path(__file__).resolve().parents[1]
    document = load(
        root / "config/q15/q15-r-operational-release-decision-input-v1.json"
    )
    schema = load(
        root
        / "config/schemas/q15-r-operational-release-decision-input-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(document)]
    errors.extend(semantic_errors(root, document))
    if args.archive_dir is not None and args.extracted_root is not None:
        errors.extend(release_errors(document, args.archive_dir, args.extracted_root))

    negatives = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["stand_setup_authorized"] = True
    negatives.append(authority)
    accepted = copy.deepcopy(document)
    accepted["decision"]["state"] = "ACCEPTED"
    negatives.append(accepted)
    drift = copy.deepcopy(document)
    drift["operational_release_evidence"]["archive_sha256"] = "0" * 64
    negatives.append(drift)
    fabricated = copy.deepcopy(document)
    fabricated["remaining_required_inputs"][0] = {
        "name": "@ALLOWED_SIGNERS_SOURCE@",
        "state": "RESOLVED",
        "value": "/tmp/unbound",
    }
    negatives.append(fabricated)
    missing = copy.deepcopy(document)
    missing["remaining_required_inputs"].pop()
    negatives.append(missing)
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(f"q15-r-operational-release-decision-check: FAIL: {error}", file=sys.stderr)
        return 1
    release_suffix = " + exact local release" if args.archive_dir else ""
    print(
        "q15-r-operational-release-decision-check: PASS "
        f"(D-065 proposed, 5 unresolved, 5 negative{release_suffix}, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
