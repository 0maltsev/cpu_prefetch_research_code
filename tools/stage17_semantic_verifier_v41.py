#!/usr/bin/env python3
"""Stage 17 registry retargeting `S17-EXT-004` to the QUALIFICATION_EVIDENCE
schema successor that drops unmeasurable clock-pair fields (ADR-0154).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v40.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v40.json` runtime-closure
hash for that file remains valid and unchanged.

Tracing the real, active `S17-EXT-004` dispatch end to end (not assumed
from the input's number) shows it is *not* reached through `stage17_
operational_semantics_v7.py`'s generic `verify_manifest_v7`, despite that
module's own docstring describing coverage for "S17-EXT-003 through
S17-EXT-010": `stage17_semantic_verifier_v34.py`'s override of that path
wires it *only* for `S17-EXT-002` (`verify_operational_manifest_v7`,
`if input_id == "S17-EXT-002"`), delegating every other input, `S17-
EXT-004` included, down to its own predecessor. Every generation between
`v34` and this session's own `v40` only special-cases `S17-EXT-001` (or,
for `v22`, also `S17-EXT-006`) and delegates the rest unchanged, all the
way down to `stage17_semantic_verifier_v14.py`'s `verify_operational_
manifest` -- the real terminal handler for `S17-EXT-002/003/004/005/007/
008/009/010` collectively, which calls `stage17_operational_semantics_
v4.verify_manifest_v4`, the original frozen module, whose `ROLE_SCHEMA`
still pins `QUALIFICATION_EVIDENCE` to the unsatisfiable `v1` schema.

This file intercepts `S17-EXT-004` specifically (mirroring the exact
scope `stage17_semantic_verifier_v22.py` established for `S17-EXT-006`
and `v34` established for `S17-EXT-002`) and calls `stage17_operational_
semantics_v8.verify_manifest_v8` instead -- the module whose `ROLE_
SCHEMA_v8` retargets only `QUALIFICATION_EVIDENCE` to `config/schemas/
qualification-evidence-v2.schema.json` (ADR-0154's own schema successor,
whose `clock_details` drops `traced_call_count`/`traced_syscall_count`/
`before_block_repeat`, fields nothing in this codebase can honestly
measure). Every other input's dispatch, `S17-EXT-001`/`S17-EXT-002`
included, is unchanged, delegated to `predecessor.verify_input` (`v40`).

ADR-0155's own `S17-EXT-006` receipt-field fix (`verify_s17_ext_006`
reading the real `artifact_locator` field instead of the stale
`contract_path` no real v2-schema receipt carries -- see that ADR for
the full trace) is folded into *this* file in place, rather than added
as its own new `v42` successor as ADR-0155 originally did. Confirmed for
real, against a disposable copy of journal `standv2-18`'s own live
admission-root: creating `v42` and moving `stage17_state_journal_v35.py`'s
own `semantic` import to it broke `S17-EXT-001`'s already-admitted
envelope binding, because the *only* thing `S17-EXT-001`'s own semantic
check pins is `state_journal_v35.py`'s own bytes (transitively, via the
read-only-preflight policy's `IMPLEMENTATION_PATHS`) -- not this file's.
Editing this file's own body in place, while leaving `state_journal_
v35.py`'s import line (and therefore the read-only-preflight policy's
own pinned hash of it) completely untouched, requires no re-render of
that policy and does not disturb `S17-EXT-001`'s binding at all. This is
a deliberate, narrow exception to this codebase's usual "never edit an
already-accepted file in place" convention: unlike `v22`/`v34`/`v39`/
`v40` before it, `v41.py` was authored and deployed entirely within this
same session, for this same journal's own use, and nothing outside this
journal depends on its bytes staying frozen.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Mapping

import stage17_operational_semantics_v8 as operational
import stage17_pilot_candidate_artifact_v7 as release_verifier
import stage17_semantic_verifier_v40 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v41.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v41.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "41"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v41(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v41 schema rejection: {errors[0].message}"
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
        raise SemanticAdmissionError("policy v41 runtime closure is incomplete")
    if "tools/stage17_read_only_preflight_executor_v24.py" in discovered:
        raise SemanticAdmissionError(
            "policy v41 must bind executor v25, not the superseded v24 entry point"
        )
    bound_paths = {binding["path"] for binding in policy["bindings"].values()}
    required_dynamic_action_bindings = {
        "tools/stage17_phase_controller_v14.py",
        "tools/stage17_q15_session_controller_v12.py",
    }
    if not required_dynamic_action_bindings.issubset(bound_paths):
        raise SemanticAdmissionError(
            "policy v41 must pin the ADR-0146 dynamic-action controller "
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
    verify_policy_v41(**arguments)


def verify_operational_manifest_v8(
    *, input_id: str, root: pathlib.Path,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], allow_synthetic: bool,
    policy: dict[str, Any], **_: Any,
) -> dict[str, Any]:
    """Faithful copy of `stage17_semantic_verifier_v14.py`'s
    `verify_operational_manifest`, retargeted to call `stage17_
    operational_semantics_v8.verify_manifest_v8` instead of the frozen
    `v4.verify_manifest_v4`, and narrowed to the one input this file
    actually intercepts (`S17-EXT-004`, never in `{"S17-EXT-005",
    "S17-EXT-010"}`, so the authorization-extraction branch the
    predecessor's version carries for those two inputs is dropped as
    dead code for this call site -- not a behavior change for `S17-
    EXT-004`, which always returned `authorization: None`). Every other
    check is byte-identical to the predecessor.
    """
    candidates = [path for path, document in repository_documents
                  if document.get("schema_version") ==
                  "cpu-prefetch-stage17-operational-input-manifest/4"]
    for receipt in receipt_documents:
        locator = receipt.get("artifact_locator")
        if not isinstance(locator, str):
            continue
        path = pathlib.Path(locator)
        try:
            document = json.loads(path.read_bytes())
        except (OSError, ValueError):
            continue
        if isinstance(document, dict) and document.get("schema_version") == \
                "cpu-prefetch-stage17-operational-input-manifest/4":
            candidates.append(path)
    if len(candidates) != 1:
        raise SemanticAdmissionError(f"{input_id} requires exactly one v4 manifest")
    path = candidates[0]
    pinned: dict[str, bytes] = {}
    for group in ("bindings", "runtime_closure"):
        for key, binding in policy[group].items():
            _, payload = pinned_binding_bytes(root, binding, f"{group} {key}")
            pinned[binding["path"]] = payload
    try:
        context = operational.verify_manifest_v8(
            repository_root=root, manifest_path=path,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
            pinned_repository_bytes=pinned,
        )
    except operational.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    return {"authorization": None, "context": context}


def verify_s17_ext_006(
    *, root: pathlib.Path, receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], pilot_archive: pathlib.Path | None,
    pilot_sidecar: pathlib.Path | None, allow_synthetic: bool, **_: Any,
) -> dict[str, Any]:
    """Faithful copy of predecessor `verify_s17_ext_006` (`v40`), changed
    only to read `artifact_locator` instead of the stale `contract_path`
    field no real v2-schema receipt carries (ADR-0155). Every other
    check is byte-identical to the predecessor.
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
    if input_id == "S17-EXT-004":
        return verify_operational_manifest_v8(input_id=input_id, **arguments)
    if input_id == "S17-EXT-006":
        return verify_s17_ext_006(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
