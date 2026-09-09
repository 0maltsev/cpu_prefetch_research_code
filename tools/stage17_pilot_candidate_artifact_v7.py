#!/usr/bin/env python3
"""Stage 17 pilot-candidate artifact successor recognizing the real,
currently-shipping `STAGE17-PILOT-CANDIDATE-BUNDLE-v21` profile (ADR-0153).

`tools/stage17_pilot_candidate_artifact_v6.py` (ADR-0129, not yet accepted
into any policy's runtime closure as an `S17-EXT-006` release-verifier
binding) already broadens `RECOGNIZED_PROFILES` far enough to include
`STAGE17-PILOT-CANDIDATE-BUNDLE-v21` -- the literal `STAGE17_PROFILE`
constant `tools/create_stand_bundle.py` has stamped into every real bundle
this whole engagement has built. But no accepted module ever paired that
broadened whitelist with the two `S17-EXT-006`-specific functions --
`build_contract_v4`/`verify_pilot_candidate_artifact_v4` (frozen in `v4`,
predecessor-only in `v5`/`v6`) -- that actually author and verify the
EXT-006 external contract. `v6` only retargeted the *release-receipt*
pair (`build_extracted_release_receipt_v6`/`verify_extracted_release_
receipt_v6`, the separate `S17-EXT-002`/`S17-EXT-003` call site), not the
contract pair `S17-EXT-006` actually uses. This is why a real EXT-006
attempt against any bundle newer than `v6`'s narrower ancestors would
fail at authoring time (`stage17_operational_cli_v11.py`'s `author-
ext006-contract` still called the frozen `v4` module's `build_contract_v4`,
whose own `verify_extracted_bundle_v4` recognizes only two profile
strings) before ever reaching admission-time verification.

This is a new, additive file. It does not modify `v6.py`'s bytes, so any
already-accepted-shaped runtime-closure hash for that file remains valid
and unchanged. `build_contract_v7`/`verify_pilot_candidate_artifact_v7`
are faithful copies of `v4`'s same-named functions (the last version to
define them), retargeted only to call `v6`'s broadened
`verify_extracted_bundle_v6` instead of the frozen `v4` module's
`verify_extracted_bundle_v4`. Every other check is byte-identical to the
`v4` predecessor. `VERIFIER_ID`/`VERIFIER_VERSION` stay exactly
`"STAGE17-PILOT-CANDIDATE-EXTERNAL-VERIFIER"`/`"4"` -- the same stable,
value-compared protocol identity every predecessor in this chain has kept
frozen (ADR-0126/ADR-0128).

`build_contract_v4` is re-exported here as a compatibility alias for
`stage17_operational_cli_v11.py`'s existing `author-ext006-contract` call
site, which spells the function that way and is not itself being edited
beyond its own import line -- the same alias technique `v5.py` already
used for `verify_extracted_bundle_v4`/`verify_pilot_candidate_artifact_v4`.
"""

from __future__ import annotations

import pathlib
import tempfile
from typing import Any

from jsonschema import Draft202012Validator

import stage17_pilot_candidate_artifact_v6 as predecessor


VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = predecessor.VERIFIER_VERSION
# The frozen v4 schema's own manifest.bundle_profile enum hardcodes just
# the original two profile strings -- broadening RECOGNIZED_PROFILES
# without a matching schema successor still fails build_contract_v7's own
# schema-validation step. This new schema is otherwise byte-identical to
# the v4 predecessor, widened only in that one enum to the same set v6's
# RECOGNIZED_PROFILES already recognizes.
SCHEMA = "config/schemas/stage17-pilot-candidate-external-contract-v6.schema.json"
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

verify_extracted_bundle_v6 = predecessor.verify_extracted_bundle_v6


def build_contract_v7(
    *, repository_root: pathlib.Path, archive: pathlib.Path, sidecar: pathlib.Path,
    primary_custody_domain_id: str, secondary_custody_domain_id: str,
    contract_id: str,
) -> dict[str, Any]:
    """Faithful copy of predecessor `build_contract_v4`, calling this
    module's broadened `verify_extracted_bundle_v6` instead of the frozen
    `v4` module's two-string whitelist. Every other check is byte-identical
    to the predecessor.
    """
    _regular(archive); _regular(sidecar)
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-ext006-author-") as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v6(extracted)
        manifest_path = extracted / "BUNDLE_MANIFEST.json"
        manifest = _load_json(manifest_path)
        runtime = manifest.get("stage17_fixed_action_runtime")
        if not isinstance(runtime, dict):
            raise ArtifactError("bundle fixed-action runtime is absent")
        worker_path = extracted / str(runtime.get("member_path", ""))
        result = {
            "schema_version": "cpu-prefetch-stage17-pilot-candidate-external-contract/4",
            "contract_id": contract_id,
            "archive": {"filename": archive.name, "size_bytes": archive.stat().st_size,
                        "sha256": sha256_file(archive)},
            "sidecar": {"filename": sidecar.name, "size_bytes": sidecar.stat().st_size,
                        "sha256": sha256_file(sidecar),
                        "exact_ascii": sidecar.read_text(encoding="ascii")},
            "manifest": {**_binding(manifest_path, "BUNDLE_MANIFEST.json"),
                         "bundle_profile": manifest.get("bundle_profile")},
            "sha256s": _binding(extracted / "SHA256SUMS", "SHA256SUMS"),
            "sbom": _binding(extracted / "SBOM.spdx.json", "SBOM.spdx.json"),
            "inventory": _binding(extracted / "BUNDLE_INVENTORY.json",
                                  "BUNDLE_INVENTORY.json"),
            "worker": {**_binding(worker_path, runtime["member_path"]),
                       "role": runtime.get("role"),
                       "runtime_profile": runtime.get("runtime_profile"),
                       "supported_actions": runtime.get("supported_actions")},
            "source_revision": extracted_context.source_revision,
            "custody": {"archive_locator": str(archive),
                        "sidecar_locator": str(sidecar),
                        "primary_domain_id": primary_custody_domain_id,
                        "secondary_domain_id": secondary_custody_domain_id},
            "authority": {"pilot": False, "confirmatory": False, "phase18": False},
        }
    schema = _load_json(repository_root / SCHEMA)
    errors = list(Draft202012Validator(schema).iter_errors(result))
    if errors:
        raise ArtifactError(f"generated EXT006 contract is invalid: {errors[0].message}")
    return result


def verify_pilot_candidate_artifact_v7(
    *, repository_root: pathlib.Path, contract_path: pathlib.Path,
    archive: pathlib.Path, sidecar: pathlib.Path,
) -> ReleaseContext:
    """Faithful copy of predecessor `verify_pilot_candidate_artifact_v4`,
    calling this module's broadened `verify_extracted_bundle_v6` and using
    `RECOGNIZED_PROFILES`/`DRY_RUN_PROFILES` instead of the `v4` two-string
    literals. Every other check is byte-identical to the predecessor.
    """
    contract = _load_json(contract_path)
    schema = _load_json(repository_root / SCHEMA)
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(contract))
    if errors:
        raise ArtifactError(f"EXT006 v4 contract schema rejection: {errors[0].message}")
    archive_meta, sidecar_meta = _regular(archive), _regular(sidecar)
    if (archive.name, archive_meta.st_size, sha256_file(archive)) != (
        contract["archive"]["filename"], contract["archive"]["size_bytes"],
        contract["archive"]["sha256"],
    ):
        raise ArtifactError("EXT006 archive byte identity mismatch")
    if (sidecar.name, sidecar_meta.st_size, sha256_file(sidecar),
            sidecar.read_text(encoding="ascii")) != (
        contract["sidecar"]["filename"], contract["sidecar"]["size_bytes"],
        contract["sidecar"]["sha256"], contract["sidecar"]["exact_ascii"],
    ):
        raise ArtifactError("EXT006 sidecar byte identity mismatch")
    if contract["custody"]["primary_domain_id"] == contract["custody"]["secondary_domain_id"]:
        raise ArtifactError("EXT006 requires two distinct custody domains")
    if (pathlib.Path(contract["custody"]["archive_locator"]) != archive
            or pathlib.Path(contract["custody"]["sidecar_locator"]) != sidecar):
        raise ArtifactError("EXT006 custody locator mismatch")
    with tempfile.TemporaryDirectory(prefix="cpu-prefetch-ext006-verify-") as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v6(extracted)
        manifest_path = extracted / "BUNDLE_MANIFEST.json"
        manifest = _load_json(manifest_path)
        runtime = manifest.get("stage17_fixed_action_runtime")
        if not isinstance(runtime, dict):
            raise ArtifactError("EXT006 runtime binding is absent")
        bindings = {
            "manifest": manifest_path,
            "sha256s": extracted / "SHA256SUMS",
            "sbom": extracted / "SBOM.spdx.json",
            "inventory": extracted / "BUNDLE_INVENTORY.json",
            "worker": extracted / str(runtime.get("member_path", "")),
        }
        for name, path in bindings.items():
            expected = contract[name]
            if (path.relative_to(extracted).as_posix(), path.stat().st_size,
                    sha256_file(path)) != (
                expected["member_path"], expected["size_bytes"], expected["sha256"]
            ):
                raise ArtifactError(f"EXT006 {name} member identity mismatch")
        expected_runtime = {
            "member_path": contract["worker"]["member_path"],
            "size_bytes": contract["worker"]["size_bytes"],
            "sha256": contract["worker"]["sha256"],
            "role": "STAGE17_FIXED_ACTION_WORKER",
            "runtime_profile": "STAGE17-FIXED-ACTION-WORKER-v4",
            "supported_actions": list(SUPPORTED_ACTIONS),
            "synthetic_test_only": manifest["bundle_profile"] in DRY_RUN_PROFILES,
        }
        if runtime != expected_runtime:
            raise ArtifactError("EXT006 manifest/runtime object mismatch")
        if any(manifest.get(field) is not False for field in (
            "pilot_authorized", "confirmatory_authorized",
            "dynamic_qualification_authorized",
        )):
            raise ArtifactError("EXT006 bundle grants forbidden authority")
        if manifest.get("source_archive", {}).get("source_revision") != contract["source_revision"]:
            raise ArtifactError("EXT006 source revision mismatch")
        worker = bindings["worker"]
        payload = worker.read_bytes()
        if (payload[:4] != b"\x7fELF" or
                b"--execute-fixed-stage17-action-v4" not in payload or
                b"STAGE17-FIXED-ACTION-WORKER-v4" not in payload):
            raise ArtifactError("EXT006 worker is not the fixed v4 dispatcher")
        context = ReleaseContext(
            archive, archive_meta.st_size, contract["archive"]["sha256"],
            sidecar, sidecar_meta.st_size, contract["sidecar"]["sha256"],
            "BUNDLE_MANIFEST.json", manifest_path.stat().st_size,
            sha256_file(manifest_path), contract["source_revision"],
            runtime["member_path"], worker.stat().st_size, sha256_file(worker),
            runtime["role"], runtime["runtime_profile"],
            tuple(runtime["supported_actions"]),
            contract["custody"]["primary_domain_id"],
            contract["custody"]["secondary_domain_id"],
            extracted_context.bundle_profile,
            extracted_context.synthetic_test_only,
            extracted_context.sha256s_sha256,
            extracted_context.sbom_sha256,
            extracted_context.inventory_sha256,
        )
    return context


# Compatibility name for `stage17_operational_cli_v11.py`'s existing
# `author-ext006-contract` call site, which spells the function this way
# and is not itself being edited beyond its own import line.
build_contract_v4 = build_contract_v7
