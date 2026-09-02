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
are faithful copies of `v4`'s same-named functions, retargeted to call the
new `verify_extracted_bundle_v6` below and the new
`config/schemas/stage17-runtime-release-provenance-v5.schema.json` (a
schema successor to the frozen `v18`-closure `-v4.schema.json`, whose own
`bundle_profile` enum was just as frozen and narrow as the Python
whitelist it accompanies -- discovered the same way, by actually running
the rehearsal rather than assuming schema-level checks were already
covered). Everything else is re-exported from `v5` unchanged.

While rebasing the hermetic rehearsal against a freshly promoted v22/v23
chain, the real sealed candidate bundle advanced to
`STAGE17-PILOT-CANDIDATE-BUNDLE-v7` (and dry-run to `-v4`) -- profiles
newer than `v5`'s own accepted, frozen `RECOGNIZED_PROFILES`/
`DRY_RUN_PROFILES`. `verify_extracted_bundle_v5` (defined in the already-
accepted `v5.py`) resolves those two names as its own module's globals,
so merely re-assigning them here would not change its behavior -- the
same free-variable-resolves-via-defining-module lesson ADR-0126 already
recorded. `verify_extracted_bundle_v6` is therefore a faithful copy of
`verify_extracted_bundle_v5`'s full body (not an edit to it), broadened to
recognize `v7`/dry-run-`v4` in addition to everything `v5` already
recognized; every other check is byte-identical to the predecessor. This
file remains part of ADR-0129 (`PROPOSED`, not yet accepted), so widening
its own whitelist here -- rather than minting yet another successor -- is
still the accepted-vs-mutable file discipline, not an exception to it.

The real sealed candidate bundle later advanced again to
`STAGE17-PILOT-CANDIDATE-BUNDLE-v8` (and dry-run to `-v5`) while sealing
ADR-0130's fix. `RECOGNIZED_PROFILES`/`DRY_RUN_PROFILES` widen the same
way, for the same reason: this file is still ADR-0129's own mutable
deliverable, not yet accepted.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
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

RECOGNIZED_PROFILES = predecessor.RECOGNIZED_PROFILES | {
    "STAGE17-PILOT-CANDIDATE-BUNDLE-v7",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
    "STAGE17-PILOT-CANDIDATE-BUNDLE-v8",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
}
DRY_RUN_PROFILES = predecessor.DRY_RUN_PROFILES | {
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v4",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v5",
}
verify_extracted_bundle_v5 = predecessor.verify_extracted_bundle_v5
verify_pilot_candidate_artifact_v5 = predecessor.verify_pilot_candidate_artifact_v5
build_contract_v4 = predecessor.predecessor.build_contract_v4


def verify_extracted_bundle_v6(bundle_root: pathlib.Path) -> ExtractedReleaseContext:
    """Faithful copy of predecessor `verify_extracted_bundle_v5`, broadened
    only to recognize this module's own `RECOGNIZED_PROFILES` (v7/dry-run-v4
    added) instead of `v5`'s frozen set. Every other check is byte-identical
    to the predecessor.
    """
    root = bundle_root.resolve()
    if not root.is_dir() or root.is_symlink():
        raise ArtifactError("extracted bundle root is not a nonsymlink directory")
    _run_full_verifier(root)
    sums = _parse_sums(root)
    _verify_inventory(root, sums)
    manifest_path = root / "BUNDLE_MANIFEST.json"
    manifest = _load_json(manifest_path)
    runtime = manifest.get("stage17_fixed_action_runtime")
    if not isinstance(runtime, dict):
        raise ArtifactError("extracted bundle fixed-action runtime is absent")
    profile = manifest.get("bundle_profile")
    if profile not in RECOGNIZED_PROFILES:
        raise ArtifactError("extracted bundle profile is not a recognized Stage 17 profile")
    synthetic = profile in DRY_RUN_PROFILES
    expected_runtime = {
        "member_path": "release/bin/cpu_prefetch_runner",
        "size_bytes": (root / "release/bin/cpu_prefetch_runner").stat().st_size,
        "sha256": sha256_file(root / "release/bin/cpu_prefetch_runner"),
        "role": "STAGE17_FIXED_ACTION_WORKER",
        "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
        "supported_actions": list(SUPPORTED_ACTIONS),
        "synthetic_test_only": synthetic,
    }
    if runtime != expected_runtime:
        raise ArtifactError("extracted bundle runtime object is not exact")
    worker = root / runtime["member_path"]
    payload = worker.read_bytes()
    if (payload[:4] != b"\x7fELF"
            or b"--execute-fixed-stage17-action-v4" not in payload
            or b"STAGE17-FIXED-ACTION-WORKER-v4" not in payload):
        raise ArtifactError("extracted bundle worker lacks the fixed dispatcher")
    source_revision = manifest.get("source_archive", {}).get("source_revision")
    if (not isinstance(source_revision, str) or len(source_revision) != 40
            or any(item not in "0123456789abcdef" for item in source_revision)):
        raise ArtifactError("extracted bundle source revision is malformed")
    completed = subprocess.run(
        [str(worker), "--stage17-runtime-identity-v4"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=False, timeout=15,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TZ": "UTC"},
    )
    try:
        identity = json.loads(completed.stdout)
    except json.JSONDecodeError as exception:
        raise ArtifactError(
            "fixed worker did not emit its closed runtime identity"
        ) from exception
    expected_identity = {
        "binary_sha256": sha256_file(worker),
        "protocol_version": "2.0.0-pre.3",
        "role": "STAGE17_FIXED_ACTION_WORKER",
        "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
        "source_dirty": False,
        "source_revision": source_revision,
        "supported_actions": list(SUPPORTED_ACTIONS),
        "synthetic_test_only": synthetic,
    }
    if completed.returncode != 0 or identity != expected_identity:
        raise ArtifactError(
            "fixed worker runtime identity differs from clean release provenance"
        )
    verifier = root / "validators/verify_stand_bundle.py"
    _regular(verifier)
    return ExtractedReleaseContext(
        bundle_root=root,
        manifest_size_bytes=manifest_path.stat().st_size,
        manifest_sha256=sha256_file(manifest_path),
        source_revision=source_revision,
        worker_path=worker,
        worker_member_path=runtime["member_path"],
        worker_size_bytes=worker.stat().st_size,
        worker_sha256=sha256_file(worker),
        worker_role=runtime["role"],
        runtime_profile=runtime["runtime_profile"],
        supported_actions=tuple(runtime["supported_actions"]),
        bundle_profile=profile,
        synthetic_test_only=synthetic,
        sha256s_sha256=sha256_file(root / "SHA256SUMS"),
        sbom_sha256=sha256_file(root / "SBOM.spdx.json"),
        inventory_sha256=sha256_file(root / "BUNDLE_INVENTORY.json"),
        full_verifier_size_bytes=verifier.stat().st_size,
        full_verifier_sha256=sha256_file(verifier),
    )


def build_extracted_release_receipt_v6(
    *, bundle_root: pathlib.Path, receipt_id: str,
) -> dict[str, Any]:
    context = verify_extracted_bundle_v6(bundle_root)
    relative_worker = context.worker_path.relative_to(context.bundle_root).as_posix()
    return {
        "schema_version": "cpu-prefetch-stage17-runtime-release-provenance/5",
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
        repository_root / "config/schemas/stage17-runtime-release-provenance-v5.schema.json"
    )
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(receipt))
    if errors:
        raise ArtifactError(
            f"runtime-release receipt schema rejection: {errors[0].message}"
        )
    context = verify_extracted_bundle_v6(pathlib.Path(receipt["bundle_root"]))
    expected = build_extracted_release_receipt_v6(
        bundle_root=context.bundle_root, receipt_id=receipt["receipt_id"]
    )
    if receipt != expected:
        raise ArtifactError("runtime-release receipt differs from verified bundle bytes")
    return context
