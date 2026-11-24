#!/usr/bin/env python3
"""Stage 17 registry adding real `S17-EXT-002` profile recognition (ADR-0129).

This is a new, additive file. It does not modify
`stage17_semantic_verifier_v22.py`'s bytes, so the already-accepted-shaped
`stage17-operational-evidence-admission-policy-v22.json` runtime-closure
hash for that file remains valid and unchanged. In addition to `v22`'s
`S17-EXT-006` override, this one ALSO special-cases `S17-EXT-002`: the
frozen `v14` implementation this input would otherwise keep delegating to
calls `stage17_operational_semantics_v4.py`'s `verify_manifest_v4`, whose
`S17-EXT-002` branch hardcodes `stage17_pilot_candidate_artifact_v4.py`'s
frozen, narrow profile whitelist through a *different* call site than the
one `v22` already fixed for `S17-EXT-006` -- meaning even the promoted
`v22` chain could not admit a real `S17-EXT-002` transaction for evidence
captured from any bundle newer than `v4`, until now. `S17-EXT-001` and
`S17-EXT-006` dispatch are unchanged from `v22` (delegated to its own
implementations); every other input's dispatch is unchanged from `v21`.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any, Mapping

import stage17_operational_semantics_v5 as operational
import stage17_semantic_verifier_v22 as predecessor


POLICY_PATH = pathlib.PurePosixPath(
    "config/stage17/stage17-operational-evidence-admission-policy-v23.json"
)
POLICY_SCHEMA = pathlib.PurePosixPath(
    "config/schemas/stage17-operational-evidence-admission-policy-v23.schema.json"
)
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "23"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v23(*, root: pathlib.Path, policy: dict[str, Any],
                      graph_sha256: str, catalog_sha256: str,
                      genesis_record_sha256: str,
                      resolution_schema_sha256: str) -> None:
    from jsonschema import Draft202012Validator
    schema = json.loads((root / POLICY_SCHEMA).read_text())
    errors = list(Draft202012Validator(schema).iter_errors(policy))
    if errors:
        raise SemanticAdmissionError(
            f"policy v23 schema rejection: {errors[0].message}"
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
        "tools/stage17_state_journal_v19.py",
        "tools/stage17_phase_controller_v9.py",
        "tools/stage17_operational_cli_v11.py",
        "tools/stage17_read_only_preflight_executor_v13.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v15.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v14.py",
        "tools/stage17_pilot_candidate_artifact_v5.py",
        "tools/stage17_pilot_candidate_artifact_v6.py",
        "tools/stage17_operational_semantics_v5.py",
        "tools/stage17_openssh_parent_snapshot_v2.py",
    }
    if not required.issubset(discovered):
        raise SemanticAdmissionError("policy v23 runtime closure is incomplete")
    # stage17_pilot_candidate_artifact_v4 and stage17_operational_
    # semantics_v4 legitimately remain reachable too: every EXT-00N branch
    # other than 002/006 still uses the frozen v4 modules unchanged, and
    # each new successor imports its own immediate predecessor to
    # re-export everything but the one thing it changed. Their presence
    # in the discovered closure is expected, not a drift signal --
    # mirroring the same coexistence v21/v22 already documented for
    # phase_controller v8/v9 and pilot_candidate_artifact v4/v5.


def verify_policy_v14(**arguments: Any) -> None:
    verify_policy_v23(**arguments)


def verify_operational_manifest_v5(
    *, input_id: str, root: pathlib.Path,
    repository_documents: list[tuple[pathlib.Path, dict[str, Any]]],
    receipt_documents: list[dict[str, Any]],
    admitted_resolutions: Mapping[str, Any], allow_synthetic: bool,
    policy: dict[str, Any], **_: Any,
) -> dict[str, Any]:
    """Faithful copy of `stage17_semantic_verifier_v14.py`'s
    `verify_operational_manifest`, retargeted to call
    `stage17_operational_semantics_v5.verify_manifest_v5` instead of the
    frozen `v4.verify_manifest_v4`. Every other check is byte-identical to
    the predecessor.
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
        context = operational.verify_manifest_v5(
            repository_root=root, manifest_path=path,
            admitted_resolutions=admitted_resolutions,
            expected_input_id=input_id, allow_synthetic=allow_synthetic,
            pinned_repository_bytes=pinned,
        )
    except operational.OperationalSemanticError as exception:
        raise SemanticAdmissionError(str(exception)) from exception
    authorization = None
    if input_id in {"S17-EXT-005", "S17-EXT-010"}:
        admitted_authorization = context.get("authorization")
        if not isinstance(admitted_authorization, dict):
            raise SemanticAdmissionError(
                f"{input_id} semantic authority context is absent"
            )
        authorization = dict(admitted_authorization)
        authorization["authority_scope"] = (
            "PRIVILEGED_QUALIFICATION_CONTROL"
            if input_id == "S17-EXT-005"
            else "STAGE17_PILOT_PHASE_ONLY"
        )
    return {"authorization": authorization, "context": context}


def verify_input(*, input_id: str, **arguments: Any) -> dict[str, Any]:
    if input_id == "S17-EXT-002":
        return verify_operational_manifest_v5(input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
