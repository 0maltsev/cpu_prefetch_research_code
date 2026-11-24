"""D-204: bind prospective preflight to the current operational policy."""
from __future__ import annotations

import types

import stage17_semantic_verifier_v55 as predecessor
import stage17_semantic_verifier_v39 as preflight_dispatch
import stage17_read_only_preflight_semantic_verifier_v30 as preflight
import stage17_operational_semantics_v14 as operational
import stage17_pilot_candidate_artifact_v10 as release

POLICY_PATH = predecessor.POLICY_PATH.parent / "stage17-operational-evidence-admission-policy-v56.json"
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / "stage17-operational-evidence-admission-policy-v56.schema.json"
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "56"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v56(**arguments):
    # Preserve every v55 check, resolving only the version/schema globals here.
    namespace = dict(predecessor.verify_policy_v55.__globals__)
    namespace.update(POLICY_SCHEMA=POLICY_SCHEMA, VERIFIER_VERSION=VERIFIER_VERSION)
    types.FunctionType(predecessor.verify_policy_v55.__code__, namespace)(**arguments)
    policy = arguments["policy"]
    paths = {item["path"] for item in policy["bindings"].values()}
    required = {preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH,
                "docs/decisions/0204-stage17-preflight-successor-policy-binding.md"}
    if not required.issubset(paths):
        raise SemanticAdmissionError("policy v56 lacks D-204 preflight bindings")
    closure = {item["path"] for item in policy["runtime_closure"].values()}
    if not {"tools/stage17_operational_cli_v16.py",
            "tools/stage17_read_only_preflight_executor_v30.py",
            "tools/stage17_state_journal_v50.py"}.issubset(closure):
        raise SemanticAdmissionError("policy v56 lacks current preflight runtime")


verify_policy_v14 = verify_policy_v56


def verify_input(*, input_id, **arguments):
    if input_id == "S17-EXT-001":
        namespace = dict(preflight_dispatch._verify_ext001.__globals__)
        namespace["preflight"] = preflight
        return types.FunctionType(preflight_dispatch._verify_ext001.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id in {"S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-007"}:
        namespace = dict(predecessor.verify_operational_manifest_v11.__globals__)
        namespace["operational_v13"] = types.SimpleNamespace(
            OperationalSemanticError=operational.OperationalSemanticError,
            verify_manifest_v13=operational.verify_manifest_v14)
        return types.FunctionType(predecessor.verify_operational_manifest_v11.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id == "S17-EXT-006" and any(
            item.get("verifier_version") == release.VERIFIER_VERSION
            for item in arguments.get("receipt_documents", [])):
        namespace = dict(predecessor.verify_s17_ext_006.__globals__)
        namespace["release_verifier"] = types.SimpleNamespace(
            VERIFIER_ID=release.VERIFIER_ID, VERIFIER_VERSION=release.VERIFIER_VERSION,
            ArtifactError=release.ArtifactError,
            verify_pilot_candidate_artifact_v9=release.verify_pilot_candidate_artifact_v10)
        return types.FunctionType(predecessor.verify_s17_ext_006.__code__, namespace)(**arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
