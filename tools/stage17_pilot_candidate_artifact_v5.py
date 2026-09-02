#!/usr/bin/env python3
"""Stage 17 pilot-candidate artifact successor recognizing newer bundle
profiles (ADR-0128).

`tools/stage17_pilot_candidate_artifact_v4.py`'s `verify_extracted_bundle_v4`
hardcodes an exact-match profile whitelist of exactly
`{"STAGE17-PILOT-CANDIDATE-BUNDLE-v4", "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2"}`.
It is part of the already-accepted, hash-pinned `v18` closure, so it cannot
be edited in place, and it does not recognize the `STAGE17-PILOT-CANDIDATE-
BUNDLE-v5`/`v6` real-candidate profiles or the `STAGE17-HERMETIC-DRY-RUN-
BUNDLE-v3` dry-run profile sealed later than `v4`/`v2`. This is a new,
additive successor: `v4` and its entire accepted closure are untouched.

`VERIFIER_ID`/`VERIFIER_VERSION` stay exactly `"STAGE17-PILOT-CANDIDATE-
EXTERNAL-VERIFIER"`/`"4"` -- a stable protocol-level identity that
`verify_s17_ext_006`-equivalent dispatch compares by value, not a literal
file-version tag, matching the same frozen-historical-anchor pattern
ADR-0126 already established for the envelope's `semantic_verifier` field.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_pilot_candidate_artifact_v4 as predecessor


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

RECOGNIZED_PROFILES = frozenset({
    "STAGE17-PILOT-CANDIDATE-BUNDLE-v4",
    "STAGE17-PILOT-CANDIDATE-BUNDLE-v5",
    "STAGE17-PILOT-CANDIDATE-BUNDLE-v6",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
})
DRY_RUN_PROFILES = frozenset({
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v2",
    "STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3",
})


def verify_extracted_bundle_v5(bundle_root: pathlib.Path) -> ExtractedReleaseContext:
    """Faithful copy of predecessor `verify_extracted_bundle_v4`, broadened
    only to recognize `RECOGNIZED_PROFILES` instead of the two-string `v4`
    whitelist. Every other check is byte-identical to the predecessor.
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
    completed = predecessor.subprocess.run(
        [str(worker), "--stage17-runtime-identity-v4"],
        stdin=predecessor.subprocess.DEVNULL, stdout=predecessor.subprocess.PIPE,
        stderr=predecessor.subprocess.PIPE, check=False, timeout=15,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/usr/bin:/bin", "TZ": "UTC"},
    )
    try:
        identity = predecessor.json.loads(completed.stdout)
    except predecessor.json.JSONDecodeError as exception:
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


# Compatibility name for any caller still spelling the predecessor's
# function name; resolves to the broadened v5 implementation.
verify_extracted_bundle_v4 = verify_extracted_bundle_v5


def verify_pilot_candidate_artifact_v5(
    *, repository_root: pathlib.Path, contract_path: pathlib.Path,
    archive: pathlib.Path, sidecar: pathlib.Path,
) -> ReleaseContext:
    """Faithful copy of predecessor `verify_pilot_candidate_artifact_v4`,
    calling this module's broadened `verify_extracted_bundle_v5` and using
    `RECOGNIZED_PROFILES`/`DRY_RUN_PROFILES` instead of the `v4` two-string
    literals. Every other check is byte-identical to the predecessor.
    """
    contract = _load_json(contract_path)
    schema = _load_json(repository_root / SCHEMA)
    predecessor.Draft202012Validator.check_schema(schema)
    errors = list(predecessor.Draft202012Validator(schema).iter_errors(contract))
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
    with predecessor.tempfile.TemporaryDirectory(
        prefix="cpu-prefetch-ext006-verify-"
    ) as temporary:
        extracted = _safe_extract(archive, pathlib.Path(temporary))
        extracted_context = verify_extracted_bundle_v5(extracted)
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


# Compatibility name for any caller still spelling the predecessor's
# function name; resolves to the broadened v5 implementation.
verify_pilot_candidate_artifact_v4 = verify_pilot_candidate_artifact_v5
