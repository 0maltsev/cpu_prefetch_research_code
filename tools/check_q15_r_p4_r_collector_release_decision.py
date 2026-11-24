#!/usr/bin/env python3
"""Validate the proposed no-authority Q15-R-P4-R collector release."""

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
    "34da95d-clean-5fc75063e1d1.tar.gz"
)
EXPECTED_RELEASE = {
    "archive_bytes": 4_642_298,
    "archive_name": ARCHIVE_NAME,
    "archive_sha256": "f45d25f4aa6bff56c39face088c46c4cccd21bfaf903c9c320100b561402ff3a",
    "bundle_manifest_sha256": "84338ec24a1af44468c5a37d5c8aeedec126abc8fdc5ec846d15685aca178f20",
    "bundle_profile": "Q15-QUALIFICATION-TOOL-BUNDLE-v3",
    "collector_binary_sha256": "4716e1dfc2e65fd61dce1ea54a70fd876a0b4322b69d9ad1fde5c67a65c48a57",
    "collector_contract_sha256": "4123735a940da144e00247957d0210216cde4bf19fbdbea0378b52dab2161b87",
    "controller_binary_sha256": "1b23a743de084449cb622f14b1301b37af1c59878c6ca70abce1bb875a853f45",
    "controller_codegen_report_sha256": "7fc0d36b0e095df9a5e4563dd48d02c7a3acf4718f8816a87f2e137af43942ca",
    "internal_file_count": 154,
    "internal_sha256s_sha256": "6880faa79b0b7a9faaabe788b01dd2cd7d441d8646efd31d8929acba63f8f525",
    "p4_d_acceptance_sha256": "1645c2a7fb356272afbf9377b99784e307f54f8a7df5fbb09f46d70edae3c521",
    "prestate_validator_sha256": "6f8ee09975a3c610f57b16117e6906f26af9482a5b750d30e2bdfa2c9552f247",
    "probe_codegen_report_sha256": "cb3368f851c5c5ac8e2c5ef5747ecf53f27e586b4b756798daa8386a1266f4aa",
    "q15_qualification_library_sha256": "c8364af26d355bd736e557058db77274a3fab6d539b8622c4f0905d1be470bad",
    "q15_tool_binary_sha256": "10386c653fe33c9d8ac60b205962fed12a5240ccd354ba82ae30533f01c0d217",
    "repository_license": "NO-LICENSE-GRANT",
    "runtime_codegen_report_sha256": "e3c09d4fcbb759b0008c728d563f984d38bdb93e269ac70f3ebd6a1d99ab7014",
    "sbom_sha256": "a9bc3b59726c54171b0510c964d1ac05ece652593b33abc8238083ff14ed8e93",
    "sidecar_sha256": "f2bf9e3f2ed97541905b7e0fbc24dfa15d3b5c3096bd7e9ab0d23dcdbe0fffd4",
    "source_archive_name": "cpu-prefetch-source-34da95d-clean.tar.gz",
    "source_archive_sha256": "5fc75063e1d1d0a1602beec4e10c11080d8b02511755951210009bcc2586625c",
    "source_dirty": False,
    "source_revision": "34da95d002e912069c959bfef8e88a23b4880cea",
    "version_metadata_sha256": "7d9df7638e30dafdd1c0d52abdcff9ff8511ed0a98e33c4119ddcdfaa500ea49",
}
EXPECTED_REMAINING = (
    "COLLECTOR_RELEASE_ROOT",
    "AUTHORIZATION_ID_CANONICAL_BYTES_AND_SHA256",
    "NAMED_AUTHORITY_PRINCIPAL_ISSUE_AND_EXPIRY_UTC",
    "CAPTURE_ID",
    "OUTPUT_STDOUT_STDERR_AND_SIDECAR_CUSTODY_DESTINATIONS",
    "DETACHED_SIGNATURE_AND_INDEPENDENT_REVIEW_ARTIFACTS",
    "FRESH_PRE_EXECUTION_STAND_IDENTITY_BINDING",
)
EXTRACTED_BINDINGS = {
    "BUNDLE_MANIFEST.json": "bundle_manifest_sha256",
    "SBOM.spdx.json": "sbom_sha256",
    "SHA256SUMS": "internal_sha256s_sha256",
    "source/cpu-prefetch-source-34da95d-clean.tar.gz": "source_archive_sha256",
    "release/bin/cpu_prefetch_q15_prestate_collector": "collector_binary_sha256",
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
    "config/q15/q15-r-stand-prestate-collector-contract-v1.json": (
        "collector_contract_sha256"
    ),
    "config/q15/q15-r-p4-d-acceptance-v1.json": "p4_d_acceptance_sha256",
    "validators/validate_q15_r_prestate.py": "prestate_validator_sha256",
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
    if document.get("collector_release_evidence") != EXPECTED_RELEASE:
        errors.append("collector release evidence must match the exact verified bytes")
    decision = document.get("decision", {})
    if decision.get("decision_id") != "D-071" or decision.get("state") != (
        "PROPOSED_AWAITING_EXPLICIT_OWNER_ACCEPTANCE_NO_AUTHORITY"
    ):
        errors.append("D-071 must remain proposed until explicit owner acceptance")
    boundary = document.get("authority_boundary", {})
    authorized = {
        name
        for name, value in boundary.items()
        if name.endswith("_authorized") and value is True
    }
    if authorized != {"repository_local_decision_bundle_preparation_authorized"}:
        errors.append("proposal widens authority beyond local decision preparation")
    remaining = document.get("remaining_required_inputs", [])
    if tuple(item.get("name") for item in remaining) != EXPECTED_REMAINING:
        errors.append("the seven remaining P4-R inputs must be exact and ordered")
    if any(
        item.get("state") != "UNRESOLVED" or item.get("value") is not None
        for item in remaining
    ):
        errors.append("external P4-R inputs cannot be fabricated or defaulted")

    predecessor = document.get("predecessor_p4_r_preparation", {})
    predecessor_path = root / predecessor.get("path", "")
    if not predecessor_path.is_file() or sha256(predecessor_path) != predecessor.get(
        "sha256"
    ):
        errors.append("immutable P4-R predecessor is missing or has drifted")

    p4_k = document.get("p4_k_preparation", {})
    p4_k_path = root / p4_k.get("path", "")
    if not p4_k_path.is_file() or sha256(p4_k_path) != p4_k.get("sha256"):
        errors.append("P4-K preparation must remain unchanged and hash-bound")
    elif len(load(p4_k_path).get("unresolved_inputs", [])) != 8:
        errors.append("P4-K must retain all eight unresolved inputs")
    return errors


def release_errors(
    document: dict[str, Any], archive_dir: pathlib.Path, extracted_root: pathlib.Path
) -> list[str]:
    errors: list[str] = []
    evidence = document["collector_release_evidence"]
    archive = archive_dir / ARCHIVE_NAME
    sidecar = archive_dir / f"{ARCHIVE_NAME}.sha256"
    if not archive.is_file() or archive.stat().st_size != evidence["archive_bytes"]:
        errors.append("collector archive is missing or has the wrong size")
    elif sha256(archive) != evidence["archive_sha256"]:
        errors.append("collector archive hash mismatch")
    if not sidecar.is_file() or sha256(sidecar) != evidence["sidecar_sha256"]:
        errors.append("collector sidecar is missing or has drifted")
    else:
        expected_line = f'{evidence["archive_sha256"]}  {ARCHIVE_NAME}\n'
        if sidecar.read_text(encoding="utf-8") != expected_line:
            errors.append("collector sidecar content mismatch")
    for relative, field in EXTRACTED_BINDINGS.items():
        path = extracted_root / relative
        if not path.is_file() or sha256(path) != evidence[field]:
            errors.append(f"extracted release binding mismatch: {relative}")
    sums = extracted_root / "SHA256SUMS"
    if sums.is_file() and len(sums.read_text(encoding="utf-8").splitlines()) != (
        evidence["internal_file_count"]
    ):
        errors.append("internal file count mismatch")
    manifest_path = extracted_root / "BUNDLE_MANIFEST.json"
    if manifest_path.is_file():
        manifest = load(manifest_path)
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
            "account_or_key_changes_authorized",
            "dynamic_qualification_authorized",
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
        root
        / "config/q15/q15-r-p4-r-collector-release-decision-input-v1.json"
    )
    schema = load(
        root
        / "config/schemas/q15-r-p4-r-collector-release-decision-input-v1.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [item.message for item in validator.iter_errors(document)]
    errors.extend(semantic_errors(root, document))
    if args.archive_dir is not None and args.extracted_root is not None:
        errors.extend(release_errors(document, args.archive_dir, args.extracted_root))

    negatives = []
    authority = copy.deepcopy(document)
    authority["authority_boundary"]["stand_access_authorized"] = True
    negatives.append(authority)
    accepted = copy.deepcopy(document)
    accepted["decision"]["state"] = "ACCEPTED"
    negatives.append(accepted)
    drift = copy.deepcopy(document)
    drift["collector_release_evidence"]["archive_sha256"] = "0" * 64
    negatives.append(drift)
    fabricated = copy.deepcopy(document)
    fabricated["remaining_required_inputs"][0] = {
        "name": "COLLECTOR_RELEASE_ROOT",
        "state": "RESOLVED",
        "value": "/unapproved/path",
    }
    negatives.append(fabricated)
    missing = copy.deepcopy(document)
    missing["remaining_required_inputs"].pop()
    negatives.append(missing)
    p4_k_drift = copy.deepcopy(document)
    p4_k_drift["p4_k_preparation"]["sha256"] = "0" * 64
    negatives.append(p4_k_drift)
    for index, mutant in enumerate(negatives):
        mutant_errors = [item.message for item in validator.iter_errors(mutant)]
        mutant_errors.extend(semantic_errors(root, mutant))
        if not mutant_errors:
            errors.append(f"negative mutation {index} passed")

    if errors:
        for error in errors:
            print(
                f"q15-r-p4-r-collector-release-decision-check: FAIL: {error}",
                file=sys.stderr,
            )
        return 1
    release_suffix = " + exact local release" if args.archive_dir else ""
    print(
        "q15-r-p4-r-collector-release-decision-check: PASS "
        f"(D-071 proposed, 7 P4-R + 8 P4-K unresolved, 6 negative"
        f"{release_suffix}, authority=NONE)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
