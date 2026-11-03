"""D231: source-bound persistent formal release and unchanged prerequisite rules."""
from __future__ import annotations

import types

import stage17_semantic_verifier_v57 as predecessor
import stage17_semantic_verifier_v55 as diagnostic
import stage17_semantic_verifier_v39 as preflight_dispatch
import stage17_read_only_preflight_semantic_verifier_v32 as preflight
import stage17_operational_semantics_v16 as operational
import stage17_pilot_candidate_artifact_v12 as release

POLICY_PATH = predecessor.POLICY_PATH.parent / "stage17-operational-evidence-admission-policy-v58.json"
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / "stage17-operational-evidence-admission-policy-v58.schema.json"
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = "58"
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
FORMAL_DECISIONS = tuple("docs/decisions/" + name + ".md" for name in (
    "0210-persistent-service-session-core", "0211-stage17-q16b-completion-interval",
    "0212-stage17-q16a-demand-window", "0213-discovery-whole-plot-readback-validation",
    "0214-q16a-demand-trace-contract", "0215-caller-owned-termination-storage",
    "0216-shared-native-cold-observation-storage", "0217-formal-native-input-contract",
    "0218-typed-persistent-service-backend", "0219-persistent-scheduled-feasibility-session",
    "0220-stage17-q16a-independent-capture-validation", "0221-formal-ring-prospective-family-contract",
    "0222-calibration-allocation-bound-verification", "0223-formal-service-native-contract",
    "0224-parallel-retained-discovery-validation", "0225-formal-native-generated-code-verification",
    "0226-q16c-native-input-and-retention", "0227-formal-family-dispatch-boundary",
    "0228-formal-service-scheduled-family-contract", "0229-formal-service-and-scheduled-capture-validation",
    "0230-formal-calibration-from-bound-capture-reports", "0231-formal-admission-custody-successor",
    "0232-q16c-original-schedule-source-provenance", "0233-stage17-formal-lossless-archive-proposal",
    "0234-offline-analysis-exit-race-and-bounded-pool", "0235-stage17-formal-archive-wire-format",
    "0236-formal-archive-checkpoint-and-resource-contract", "0237-stage17-calibration-export-boundary",
    "0238-q16c-sealed-original-schedule-sources", "0239-archive-aware-calibration-export-lineage"))
ACCEPTANCE_BINDINGS = tuple("docs/evidence/stage17/" + directory + "/" + name
    for directory in ("Q16B-D211-ACCEPTANCE-20261103-01", "Q16A-D212-ACCEPTANCE-20261103-01")
    for name in ("owner-acceptance.json", "proposal.md", "inventory.json"))


def verify_policy_v58(**arguments):
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
        "docs/decisions/0231-formal-admission-custody-successor.md",
        "docs/decisions/0211-stage17-q16b-completion-interval.md",
        "docs/decisions/0212-stage17-q16a-demand-window.md",
        "config/stage17/stage17-fixed-phase-actions-v8.json",
        "config/schemas/stage17-fixed-phase-actions-v8.schema.json",
        "config/schemas/stage17-formal-retention-report-v1.schema.json",
        *("config/schemas/stage17-" + family + "-v6.schema.json" for family in (
            "fixed-action-request", "fixed-action-context", "phase-action-authorization",
            "phase-action-result", "phase-action-attempt", "phase-action-failure", "phase-action-completion")),
        *("config/schemas/stage17-formal-" + kind + "-" + boundary + "-v1.schema.json"
          for kind in ("ring", "service", "scheduled") for boundary in ("plan", "native-input")),
    }
    required.update(FORMAL_DECISIONS, ACCEPTANCE_BINDINGS)
    required.update("docs/evidence/stage17/FORMAL-STORAGE-D233-PROPOSAL-20261103-01/" + name
                    for name in ("owner-acceptance.json", "proposal.md", "acceptance-inventory.json"))
    required.update("config/schemas/" + name for name in (
        "stage17-formal-retention-report-v2.schema.json", "stage17-formal-archive-header-v1.schema.json",
        "stage17-formal-archive-encoder-plan-v1.schema.json", "stage17-calibration-freeze-v1.schema.json",
        "stage17-formal-ring-plan-v2.schema.json", "stage17-formal-service-plan-v2.schema.json",
        "stage17-formal-scheduled-plan-v2.schema.json"))
    root = arguments["root"]
    for directory in ("include/cpu_prefetch/calibration", "src/calibration",
                      "include/cpu_prefetch/runner", "src/runner", "include/cpu_prefetch/storage", "src/storage"):
        required.update(path.relative_to(root).as_posix() for path in (root / directory).rglob("*")
                        if path.is_file() and path.suffix in {".hpp", ".cpp"})
    if not required.issubset(paths):
        raise SemanticAdmissionError("policy v58 lacks accepted methods, native sources or formal contract bindings")
    closure = {item["path"] for item in policy["runtime_closure"].values()}
    required_runtime = {
        "tools/stage17_operational_cli_v17.py",
        "tools/stage17_phase_controller_v24.py",
        "tools/stage17_state_journal_v51.py",
        "tools/stage17_read_only_preflight_executor_v31.py",
        "tools/stage17_read_only_preflight_semantic_verifier_v32.py",
        "tools/stage17_q15_session_controller_v19.py",
        "tools/stage17_discovery_contract_v2.py",
        "tools/stage17_q16a_discovery_v2.py",
        "tools/stage17_discovery_validation_v2.py",
        "tools/stage17_output_registry_v10.py",
        "tools/stage17_fixed_action_executor_v9.py",
        "tools/stage17_pilot_candidate_artifact_v12.py",
        "tools/stage17_operational_semantics_v16.py",
        "tools/stage17_operational_cli_v18.py",
        "tools/stage17_phase_controller_v25.py",
        "tools/stage17_state_journal_v52.py",
        "tools/stage17_q15_session_controller_v20.py",
        "tools/stage17_read_only_preflight_executor_v32.py",
        "tools/stage17_output_registry_v11.py",
        "tools/stage17_fixed_action_executor_v10.py",
        "tools/stage17_formal_calibration_v1.py",
        "tools/stage17_q16a_capture_validation_v1.py",
        "tools/stage17_formal_service_capture_validation_v1.py",
        "tools/stage17_q16c_schedule_provenance_v1.py",
        "tools/stage17_phase_controller_v26.py", "tools/stage17_fixed_action_executor_v11.py",
        "tools/stage17_output_registry_v12.py", "tools/stage17_operational_semantics_v17.py",
        "tools/stage17_formal_calibration_v2.py", "tools/stage17_calibration_export_v2.py",
        "tools/stage17_formal_archive_v1.py", "tools/stage17_formal_archive_custody_v1.py",
        "tools/stage17_formal_archive_runtime_v1.py", "tools/stage17_formal_archive_broker_v1.py",
        "tools/stage17_formal_archive_registry_v1.py", "tools/stage17_formal_archive_jobs_v1.py",
        "tools/stage17_archive_channel_v1.py", "tools/stage17_formal_checkpoint_v1.py",
    }
    if not required_runtime.issubset(closure):
        raise SemanticAdmissionError("policy v58 lacks current D207 runtime")



verify_policy_v14 = verify_policy_v58


def verify_input(*, input_id, **arguments):
    if input_id == "S17-EXT-001":
        namespace = dict(preflight_dispatch._verify_ext001.__globals__)
        namespace["preflight"] = preflight
        return types.FunctionType(preflight_dispatch._verify_ext001.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id in {"S17-EXT-002", "S17-EXT-003", "S17-EXT-004", "S17-EXT-007"}:
        # This bridge imports the controller/journal, which resolves this policy.
        # Load it only after this module's public policy bindings exist.
        import stage17_operational_semantics_v17 as archival_operational
        namespace = dict(diagnostic.verify_operational_manifest_v11.__globals__)
        namespace["operational_v13"] = types.SimpleNamespace(
            OperationalSemanticError=operational.OperationalSemanticError,
            verify_manifest_v13=archival_operational.verify_manifest_v17)
        return types.FunctionType(diagnostic.verify_operational_manifest_v11.__code__, namespace)(
            input_id=input_id, **arguments)
    if input_id == "S17-EXT-006" and any(
            item.get("verifier_version") == release.VERIFIER_VERSION
            for item in arguments.get("receipt_documents", [])):
        namespace = dict(diagnostic.verify_s17_ext_006.__globals__)
        namespace["release_verifier"] = types.SimpleNamespace(
            VERIFIER_ID=release.VERIFIER_ID, VERIFIER_VERSION=release.VERIFIER_VERSION,
            ArtifactError=release.ArtifactError,
            verify_pilot_candidate_artifact_v9=release.verify_pilot_candidate_artifact_v12)
        result = types.FunctionType(diagnostic.verify_s17_ext_006.__code__, namespace)(**arguments)
        if result["context"].get("bundle_profile") in release.RECOGNIZED_PROFILES:
            result["context"].update(_qualified_archive_context(result["context"], **arguments))
        return result
    return predecessor.verify_input(input_id=input_id, **arguments)


def _qualified_archive_context(archive_context, *, root, admitted_resolutions, **unused):
    """Bind the actual provisioned codec runtime to both accepted releases."""
    qualified = admitted_resolutions["S17-EXT-003"].semantic_context.get("release")
    receipt = getattr(qualified, "archive_runtime_provenance", None)
    if not isinstance(receipt, dict):
        raise SemanticAdmissionError("EXT003 lacks its verified original archive-runtime receipt")
    for name in ("bundle_profile", "manifest_sha256", "manifest_size_bytes", "source_revision",
                 "sha256s_sha256", "sbom_sha256", "inventory_sha256"):
        if archive_context.get(name) != getattr(qualified, name, None):
            raise SemanticAdmissionError("EXT006 archival bundle differs from EXT003: " + name)
    try:
        return release.qualified_archive_context_v12(repository_root=root, receipt=receipt,
                                                     release_context=qualified)
    except (release.ArtifactError, OSError, ValueError) as error:
        raise SemanticAdmissionError("EXT006 archive runtime rejected: " + str(error)) from error
