#!/usr/bin/env python3
"""Stage 17 registry adding real `S17-EXT-006` profile recognition (ADR-0128).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v21.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v21.json` runtime-closure
hash for that file remains valid and unchanged. Unlike every successor
since `v19` (which only special-cased `S17-EXT-001`), this one ALSO
special-cases `S17-EXT-006`: the frozen `v14` implementation this input
would otherwise keep delegating to hardcodes
`stage17_pilot_candidate_artifact_v4.py`'s two-profile whitelist, which
does not recognize `STAGE17-PILOT-CANDIDATE-BUNDLE-v5`/`v6` or
`STAGE17-HERMETIC-DRY-RUN-BUNDLE-v3` -- meaning even the promoted `v21`
chain could not admit a real `S17-EXT-006` transaction for any bundle
newer than `v4`, until now. `S17-EXT-001` dispatch and every other
input's dispatch are unchanged from `v21`.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import stage17_pilot_candidate_artifact_v5 as release_verifier
import stage17_read_only_preflight_semantic_verifier_v15 as preflight
import stage17_semantic_verifier_v21 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v22.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v22.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "22"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v22(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v22 schema rejection: {errors[0].message}"
        )
    if (policy["graph_sha256"] != graph_sha256
            or policy["catalog_sha256"] != catalog_sha256
            or policy["genesis_record_sha256"] != genesis_record_sha256
            or policy["resolution_schema_sha256"] != resolution_schema_sha256):
        raise SemanticAdmissionError("policy graph/catalog/genesis binding drifted")
    expected = [
        {"input_id": item, "status": "IMPLEMENTED",
         "verifier_id": VERIFIER_ID, "verifier_version": VERIFIER_VERSION}
        for item in INPUT_IDS
    ]
    if policy["entries"] != expected:
        raise SemanticAdmissionError("policy does not implement exactly ten inputs")
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            pinned_binding_bytes(root, binding, f"{group} {key}")
    discovered = discover_python_closure(
        root, tuple(policy["runtime_import_roots"])
    )
    if discovered != {item["path"] for item in policy["runtime_closure"].values()}:
        raise SemanticAdmissionError(
            "policy Python runtime closure is incomplete/expanded"
        )
    required = {
        "tools/stage17_state_journal_v17.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v13.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v15.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v14.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_openssh_parent_snapshot_v2.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v22 runtime closure is incomplete")
    # stage17_pilot_candidate_artifact_v4 legitimately remains reachable
    # too: stage17_operational_semantics_v4.py's EXT-002 path
    # (_verify_extracted_release) still uses it unchanged, and
    # stage17_pilot_candidate_artifact_v5.py itself imports v4 as its own
    # predecessor to re-export everything but the profile whitelist. Its
    # presence in the discovered closure is expected, not a drift signal
    # -- mirroring the phase_controller v8/v9 coexistence v21 already
    # documented.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v22(**arguments)


def _verify_ext001(**arguments: Any) -> dict[str, Any]:
    root = arguments["root"]
    policy_path = root / preflight.POLICY_PATH
    import json
    policy = json.loads(policy_path.read_text())
    entry = next(
        item for item in policy["entries"] if item["input_id"] == "S17-EXT-001"
    )
    try:
        preflight.verify_policy_v15(
            root=root, policy=policy,
            graph_sha256=arguments["graph_sha256"],
            catalog_sha256=arguments["catalog_sha256"],
            genesis_file_sha256=sha_file(
                root / "config/stage17/journal/stage17-state-journal-000000.json"
            ),
            genesis_record_sha256=arguments["genesis_sha256"],
            resolution_schema_sha256=arguments["resolution_schema_sha256"],
        )
        return preflight.verify_s17_ext_001_semantics_v15(
            **{key: value for key, value in arguments.items() if key != "policy"},
            policy=policy, policy_path=policy_path,
            policy_sha256=sha_file(policy_path), policy_entry=entry,
        )
    except Exception as exception:
        raise SemanticAdmissionError(str(exception)) from exception


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_s17_ext_006` (`v14`), calling
    `stage17_pilot_candidate_artifact_v5`'s broadened profile-recognition
    instead of the frozen `v4` module's two-string whitelist. Every other
    check is byte-identical to the predecessor.
    """
    if len(receipt_documents) != 1 or pilot_archive is None or pilot_sidecar is None:
        raise SemanticAdmissionError("EXT006 requires exact archive/sidecar bytes")
    receipt = receipt_documents[0]
    if (receipt.get("verifier_id"), receipt.get("verifier_version")) != (
        release_verifier.VERIFIER_ID, release_verifier.VERIFIER_VERSION
    ):
        raise SemanticAdmissionError("EXT006 verifier identity drifted")
    contract_path = root / str(receipt.get("contract_path", ""))
    try:
        context = release_verifier.verify_pilot_candidate_artifact_v5(
            repository_root=root, contract_path=contract_path,
            archive=pilot_archive, sidecar=pilot_sidecar,
        )
    except release_verifier.ArtifactError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    ext3 = admitted_resolutions.get("S17-EXT-003")
    if ext3 is None or not isinstance(ext3.semantic_context, dict):
        raise SemanticAdmissionError("EXT006 lacks owner-accepted runtime")
    release = ext3.semantic_context.get("release")
    if release is None:
        raise SemanticAdmissionError("EXT003 clean-release context is absent")
    if (context.worker_size_bytes, context.worker_sha256, context.worker_role,
        context.runtime_profile, context.supported_actions,
        context.synthetic_test_only) != (
            release.worker_size_bytes, release.worker_sha256, release.worker_role,
            release.runtime_profile, release.supported_actions,
            release.synthetic_test_only,
        ):
        raise SemanticAdmissionError("EXT006 archive worker differs from EXT002/003")
    if context.synthetic_test_only is not allow_synthetic:
        raise SemanticAdmissionError("EXT006 verified classification drifted")
    return {"authorization": None, "context": {
        "archive_locator": str(context.archive_locator),
        "archive_size_bytes": context.archive_size_bytes,
        "archive_sha256": context.archive_sha256,
        "sidecar_locator": str(context.sidecar_locator),
        "sidecar_size_bytes": context.sidecar_size_bytes,
        "sidecar_sha256": context.sidecar_sha256,
        "manifest_member_path": context.manifest_member_path,
        "manifest_size_bytes": context.manifest_size_bytes,
        "manifest_sha256": context.manifest_sha256,
        "source_revision": context.source_revision,
        "release_artifact_path": str(release.worker_path),
        "release_artifact_member_path": context.worker_member_path,
        "release_artifact_size_bytes": context.worker_size_bytes,
        "release_artifact_sha256": context.worker_sha256,
        "release_artifact_role": context.worker_role,
        "runtime_profile": context.runtime_profile,
        "supported_actions": list(context.supported_actions),
        "bundle_profile": context.bundle_profile,
        "synthetic_test_only": context.synthetic_test_only,
        "sha256s_sha256": context.sha256s_sha256,
        "sbom_sha256": context.sbom_sha256,
        "inventory_sha256": context.inventory_sha256,
    }}


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id == "S17-EXT-001":
        return _verify_ext001(input_id=input_id, **arguments)
    if input_id == "S17-EXT-006":
        return verify_s17_ext_006(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
