#!/usr/bin/env python3
"""Stage 17 registry fixing `S17-EXT-006`'s own receipt field read, which
has never matched any real, schema-valid receipt (ADR-0155).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v41.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v41.json` runtime-closure
hash for that file remains valid and unchanged.

`verify_s17_ext_006` (defined once in `stage17_semantic_verifier_v22.py`,
faithfully copied unchanged through `v40`'s own copy this session already
made) reads `receipt.get("contract_path", "")` to locate the real
`S17-EXT-006` pilot-candidate contract document a receipt wraps. That
field name matches the *old* `stage17-external-custody-receipt-v1`
schema (`contract_path`/`contract_sha256`, flat string fields) --
confirmed directly in that schema's own `required` list. The real,
currently-active receipt schema is `v2`
(`tools/stage17_operational_cli_v11.py`'s own `author_custody_receipt`
function emits `"schema_version": "cpu-prefetch-stage17-external-
custody-receipt/2"`, confirmed against every real receipt this
engagement's admissions have actually produced), whose `additionalProperties:
false` restructured those two flat fields into a nested `contract:
{locator, sha256, scope}` object used for a completely different purpose
throughout every other real admission this session -- scoping the
receipt to the operational evidence root's own journal genesis file, not
locating the wrapped artifact. `receipt.get("contract_path", "")`
therefore always resolves to the empty string against any real `v2`
receipt, which `verify_pilot_candidate_artifact_v7` would then fail to
even open as a file. This was never caught before because no real
`S17-EXT-006` admission has ever been attempted in this engagement's
history.

The real, wrapped `S17-EXT-006` contract document's own path is already
present on the receipt at `artifact_locator` -- the field every other
real receipt this session has used to locate what a receipt actually
wraps, and the field `author_custody_receipt` already populates from
whatever `--artifact` path is passed to `author-custody-receipt
--input-id S17-EXT-006`. This file's own `verify_s17_ext_006` is a
faithful copy of `v40`'s, changed only to read `artifact_locator`
instead of `contract_path`; every other check is byte-identical.
"""

from __future__ import annotations

import pathlib
from typing import Any, Mapping

import stage17_pilot_candidate_artifact_v7 as release_verifier
import stage17_semantic_verifier_v41 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v42.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v42.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "42"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v42(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    import json
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v42 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v35.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v25.py",
        "tools/stage17_process_group_supervisor_v3.py",
        "tools/stage17_openssh_parent_snapshot_v5.py",
        "tools/stage17_read_only_preflight_collector_v3.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v27.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v20.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_pilot_candidate_artifact_v7.py",
        "tools/stage17_operational_semantics_v6.py",
        "tools/stage17_operational_semantics_v7.py",
        "tools/stage17_operational_semantics_v8.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v42 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v42 must bind executor v25, not the superseded v24 entry point"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "tools/stage17_phase_controller_v14.py",
        "tools/stage17_q15_session_controller_v12.py",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v42 must pin the ADR-0146 dynamic-action controller "
            "entrypoints (the real execute_session wiring fix)"
        )
    # Every module generation older than what this policy's own
    # IMPLEMENTATION_PATHS binds legitimately remains reachable too: each
    # new successor imports its own immediate predecessor to re-export
    # everything but the one thing it changed. Their presence in the
    # discovered closure is expected, not a drift signal -- the same
    # coexistence already documented for phase_controller v8/v9, pilot_
    # candidate_artifact v4/v5/v6/v7, and process_group_supervisor v2/v3.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v42(**arguments)


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_s17_ext_006` (`v40`), changed
    only to read `artifact_locator` instead of the stale `contract_path`
    field no real v2-schema receipt carries. Every other check is
    byte-identical to the predecessor.
    """
    if len(receipt_documents) != 1 or pilot_archive is None or pilot_sidecar is None:
        raise SemanticAdmissionError("EXT006 requires exact archive/sidecar bytes")
    receipt = receipt_documents[0]
    if (receipt.get("verifier_id"), receipt.get("verifier_version")) != (
        release_verifier.VERIFIER_ID, release_verifier.VERIFIER_VERSION
    ):
        raise SemanticAdmissionError("EXT006 verifier identity drifted")
    contract_path = root / str(receipt.get("artifact_locator", ""))
    try:
        context = release_verifier.verify_pilot_candidate_artifact_v7(
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
    if input_id == "S17-EXT-006":
        return verify_s17_ext_006(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
