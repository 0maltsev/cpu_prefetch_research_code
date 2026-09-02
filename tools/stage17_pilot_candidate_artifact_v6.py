#!/usr/bin/env python3
"""Stage 17 pilot-candidate artifact successor adding release-receipt
authoring/verification against the broadened profile whitelist (ADR-0129).

`tools/stage17_pilot_candidate_artifact_v5.py` (ADR-0128, accepted) added
`verify_extracted_bundle_v5`'s broadened profile whitelist but did not add
release-receipt equivalents, since ADR-0128's scope was only the
`S17-EXT-006` archive/sidecar call site. Real `S17-EXT-002` admission goes
through a different call site -- `stage17_operational_semantics_v4.py`'s
`_verify_extracted_release`, which calls `stage17_pilot_candidate_
artifact_v4.py`'s `verify_extracted_release_receipt_v4`, which internally
still calls the frozen, narrow `verify_extracted_bundle_v4`. `v5` is
itself now an accepted, immutable file, so this is a new, additive
successor rather than an edit to it.

`build_extracted_release_receipt_v6`/`verify_extracted_release_receipt_v6`
are faithful copies of `v4`'s same-named functions, retargeted to call
`v5`'s already-broadened `verify_extracted_bundle_v5` instead of `v4`'s
narrower `verify_extracted_bundle_v4`. Everything else is re-exported
from `v5` unchanged.
"""

from __future__ import annotations

import pathlib
from typing import Any

from jsonschema import Draft202012Validator

import stage17_pilot_candidate_artifact_v5 as predecessor


VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = predecessor.VERIFIER_VERSION
SCHEMA = predecessor.SCHEMA
SUPPORTED_ACTIONS = predecessor.SUPPORTED_ACTIONS

ArtifactError = predecessor.ArtifactError
ReleaseContext = predecessor.ReleaseContext
ExtractedReleaseContext = predecessor.ExtractedReleaseContext

sha256_bytes = predecessor.sha256_bytes
sha256_file = predecessor.sha256_file
_regular = predecessor._regular
_load_json = predecessor._load_json
_safe_extract = predecessor._safe_extract
_binding = predecessor._binding
_parse_sums = predecessor._parse_sums
_verify_inventory = predecessor._verify_inventory
_run_full_verifier = predecessor._run_full_verifier

RECOGNIZED_PROFILES = predecessor.RECOGNIZED_PROFILES
DRY_RUN_PROFILES = predecessor.DRY_RUN_PROFILES
verify_extracted_bundle_v5 = predecessor.verify_extracted_bundle_v5
verify_pilot_candidate_artifact_v5 = predecessor.verify_pilot_candidate_artifact_v5


def build_extracted_release_receipt_v6(
    *, bundle_root: pathlib.Path, receipt_id: str,
) -> dict[str, Any]:
    context = verify_extracted_bundle_v5(bundle_root)
    relative_worker = context.worker_path.relative_to(context.bundle_root).as_posix()
    return {
        "schema_version": "cpu-prefetch-stage17-runtime-release-provenance/4",
        "receipt_id": receipt_id,
        "bundle_root": str(context.bundle_root),
        "bundle_profile": context.bundle_profile,
        "source_revision": context.source_revision,
        "bundle_manifest": {
            "path": "BUNDLE_MANIFEST.json",
            "size_bytes": context.manifest_size_bytes,
            "sha256": context.manifest_sha256,
        },
        "sha256s": {
            "path": "SHA256SUMS",
            "size_bytes": (context.bundle_root / "SHA256SUMS").stat().st_size,
            "sha256": context.sha256s_sha256,
        },
        "sbom": {
            "path": "SBOM.spdx.json",
            "size_bytes": (context.bundle_root / "SBOM.spdx.json").stat().st_size,
            "sha256": context.sbom_sha256,
        },
        "inventory": {
            "path": "BUNDLE_INVENTORY.json",
            "size_bytes": (context.bundle_root / "BUNDLE_INVENTORY.json").stat().st_size,
            "sha256": context.inventory_sha256,
        },
        "worker": {
            "path": relative_worker,
            "size_bytes": context.worker_size_bytes,
            "sha256": context.worker_sha256,
            "role": context.worker_role,
            "runtime_profile": context.runtime_profile,
            "supported_actions": list(context.supported_actions),
        },
        "full_bundle_verifier": {
            "path": "validators/verify_stand_bundle.py",
            "size_bytes": context.full_verifier_size_bytes,
            "sha256": context.full_verifier_sha256,
            "result": "PASS",
        },
        "synthetic_test_only": context.synthetic_test_only,
        "phase18_authority": False,
    }


def verify_extracted_release_receipt_v6(
    *, repository_root: pathlib.Path, receipt: dict[str, Any],
) -> ExtractedReleaseContext:
    schema = _load_json(
        repository_root / "config/schemas/stage17-runtime-release-provenance-v4.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise ArtifactError(
            f"runtime-release receipt schema rejection: {errors[0].message}"
        )
    context = verify_extracted_bundle_v5(pathlib.Path(receipt["bundle_root"]))
    expected = build_extracted_release_receipt_v6(
        bundle_root=context.bundle_root, receipt_id=receipt["receipt_id"]
    )
    if receipt != expected:
        raise ArtifactError("runtime-release receipt differs from verified bundle bytes")
    return context
