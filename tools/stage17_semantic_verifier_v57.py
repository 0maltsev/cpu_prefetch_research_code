"""D-208: source-bound D207 discovery and unchanged qualification admission."""
from __future__ import annotations

import types

import stage17_semantic_verifier_v56 as predecessor
import stage17_semantic_verifier_v55 as diagnostic
import stage17_semantic_verifier_v39 as preflight_dispatch
import stage17_read_only_preflight_semantic_verifier_v31 as preflight
import stage17_operational_semantics_v15 as operational
import stage17_pilot_candidate_artifact_v11 as release

POLICY_PATH = predecessor.POLICY_PATH.parent / "stage17-operational-evidence-admission-policy-v57.json"
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / "stage17-operational-evidence-admission-policy-v57.schema.json"
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "57"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes


def verify_policy_v57(**arguments):
    # Preserve every v55 check, resolving only the version/schema globals here.
    namespace = dict(diagnostic.verify_policy_v55.__globals__)
    namespace.update(POLICY_SCHEMA=POLICY_SCHEMA, VERIFIER_VERSION=VERIFIER_VERSION)
    types.FunctionType(diagnostic.verify_policy_v55.__code__, namespace)(**arguments)
    policy = arguments["policy"]
    paths = {item["path"] for item in policy["bindings"].values()}
    required = {
        preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH,
        predecessor.POLICY_PATH.as_posix(),
        "config/stage17/stage17-read-only-preflight-evidence-admission-policy-v30.json",
        "docs/decisions/0204-stage17-preflight-successor-policy-binding.md",
        "docs/decisions/0206-stage17-ext007-stand-primary-custody.md",
        "docs/decisions/0207-stage17-ext007-discovery-duration-revision.md",
        "docs/decisions/0208-stage17-discovery-v2-implementation.md",
        "docs/decisions/0209-stage17-procfs-disappearing-process.md",
        "docs/evidence/stage17/DISCOVERY-D207-ACCEPTANCE-20261103-01/owner-acceptance.json",
        "docs/evidence/stage17/DISCOVERY-D207-ACCEPTANCE-20261103-01/proposal.md",
        "config/schemas/stage17-discovery-plan-v2.schema.json",
        release.SCHEMA, release.RUNTIME_RELEASE_PROVENANCE_SCHEMA,
    }
    if not required.issubset(paths):
        raise SemanticAdmissionError("policy v57 lacks D-208/accepted D207 bindings")
    closure = {item["path"] for item in policy["runtime_closure"].values()}
    required_runtime = {
        "tools/stage17_operational_cli_v17.py",
        "tools/stage17_phase_controller_v24.py",
        "tools/stage17_state_journal_v51.py",
        "tools/stage17_read_only_preflight_executor_v31.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v31.py",
        "tools/stage17_q15_session_controller_v19.py",
        "tools/stage17_discovery_contract_v2.py",
        "tools/stage17_q16a_discovery_v2.py",
        "tools/stage17_discovery_validation_v2.py",
        "tools/stage17_output_registry_v10.py",
        "tools/stage17_fixed_action_executor_v9.py",
        "tools/stage17_pilot_candidate_artifact_v11.py",
        "tools/stage17_operational_semantics_v15.py",
    }
    if not required_runtime.issubset(closure):
        raise SemanticAdmissionError("policy v57 lacks current D207 runtime")



verify_policy_v14 = verify_policy_v57


def verify_input(*, input_id, **arguments):
    if input_id == "S17-EXT-001":
        namespace = dict(preflight_dispatch._verify_ext001.__globals__)
        namespace["preflight"] = preflight
        return types.FunctionType(preflight_dispatch._verify_ext001.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id in {"S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-007"}:
        namespace = dict(diagnostic.verify_operational_manifest_v11.__globals__)
        namespace["operational_v13"] = types.SimpleNamespace(
            OperationalSemanticError=operational.OperationalSemanticError,
            verify_manifest_v13=operational.verify_manifest_v15)
        return types.FunctionType(diagnostic.verify_operational_manifest_v11.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id == "S17-EXT-006" and any(
            item.get("verifier_version") == release.VERIFIER_VERSION
            for item in arguments.get("receipt_documents", [])):
        namespace = dict(diagnostic.verify_s17_ext_006.__globals__)
        namespace["release_verifier"] = types.SimpleNamespace(
            VERIFIER_ID=release.VERIFIER_ID, VERIFIER_VERSION=release.VERIFIER_VERSION,
            ArtifactError=release.ArtifactError,
            verify_pilot_candidate_artifact_v9=release.verify_pilot_candidate_artifact_v11)
        return types.FunctionType(diagnostic.verify_s17_ext_006.__code__, namespace)(**arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
