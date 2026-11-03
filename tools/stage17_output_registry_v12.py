"""Original /2 formal archive-family custody; no scientific/execution credit.

The controller supplies its qualified RuntimeProfile. Original request transport
keeps its historical LF; native /2 plan identity is JCS without LF. Independent
offline readback requires a separately bounded current analysis plan, never a
fresh interpretation of the historical collection authorization's expiry.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import stat

from jsonschema import Draft202012Validator

import stage17_output_registry_v11 as predecessor
import stage17_formal_plan_v2 as contract
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as capture_registry
import stage17_formal_archive_runtime_v1 as runtime
import stage17_fixed_action_executor_v4 as roots

base = predecessor.base
OutputAdmissionError = predecessor.OutputAdmissionError
PinnedOutputRegistry = predecessor.PinnedOutputRegistry
validate_document = predecessor.validate_document
canonical = predecessor.canonical  # Signed request/result transport, including LF.
sha256 = predecessor.sha256
schema_path = predecessor.schema_path
PLAN_PATH, PLAN_SCHEMA = predecessor.PLAN_PATH, predecessor.PLAN_SCHEMA
REPORT_SCHEMA = "config/schemas/stage17-formal-retention-report-v2.schema.json"
REPORT_NAME, RESULT_NAME = predecessor.REPORT_NAME, predecessor.RESULT_NAME
FAMILIES, FORMAL_ACTIONS = predecessor.FAMILIES, predecessor.FORMAL_ACTIONS
capture_names = predecessor.capture_names
same = predecessor._same


def plan_sha256(plan):
    return sha256(archive.canonical(plan))


def pin_registry(root):
    old = predecessor.pin_registry(root)
    schemas = dict(old.schemas)
    for path in (REPORT_SCHEMA, *contract.SCHEMA.values()):
        payload = base._safe_repository_file(root, PurePosixPath(path))
        document = json.loads(payload)
        Draft202012Validator.check_schema(document)
        schemas[path] = base.PinnedSchema(path, len(payload), sha256(payload), document,
                                          Draft202012Validator(document))
    return PinnedOutputRegistry(old.plan_bytes, old.plan_sha256, old.plan, schemas)


def is_archived(request):
    action = request.get("action_id")
    return (action in FORMAL_ACTIONS
            and request.get("schema_version") == "cpu-prefetch-stage17-fixed-action-request/6"
            and request.get("action_inputs", {}).get("plan", {}).get("schema_version") == contract.VERSION[action])


def artifact_identity(action, name):
    if name == REPORT_NAME:
        return ("FORMAL_CALIBRATION_RETENTION_REPORT",
                "cpu-prefetch-stage17-formal-retention-report/2", "application/json")
    if name.endswith("-final-checkpoint.json"):
        return ("FORMAL_CAPTURE_FINAL_CHECKPOINT",
                "cpu-prefetch-stage17-formal-capture-checkpoint/1", "application/json")
    if name.endswith("-archive-custody.json"):
        return ("FORMAL_CAPTURE_ARCHIVE_CUSTODY",
                "cpu-prefetch-stage17-formal-archive-custody/1", "application/json")
    return predecessor.artifact_identity(action, name)


def reference(binding):
    return {k: binding[k] for k in ("file_name", "size_bytes", "sha256")}


def _metadata(*, registry, directory_fd, result, request, authorization_sha256,
              synthetic_test_only):
    if not is_archived(request):
        raise OutputAdmissionError("archival verifier requires an original /2 formal plan")
    action, plan = request["action_id"], request["action_inputs"]["plan"]
    extent = contract.validate_plan(action, plan)
    validate_document(registry, result, schema_path("phase-action-result"), "archival result")
    for key in ("request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
                "runtime_binding", "release_binding", "predecessor_resolutions"):
        same(result[key], request[key], "archival result " + key)
    for key, expected in dict(authorization_sha256=authorization_sha256,
            request_sha256=sha256(canonical(request)), synthetic_test_only=synthetic_test_only,
            restoration_verified=True, quarantined=False, phase18_authority=False,
            terminal_state="FORMAL_ARTIFACTS_RETAINED_UNASSESSED").items():
        same(result[key], expected, "archival result " + key)
    expected = {REPORT_NAME}
    for capture in extent.captures:
        expected.update(capture_names(action, capture.ordinal))
        expected.update((f"formal-capture-{capture.ordinal}-final-checkpoint.json",
                         f"formal-capture-{capture.ordinal}-archive-custody.json"))
    artifacts = result["artifacts"]
    names = [item["file_name"] for item in artifacts]
    if len(set(names)) != len(names) or set(names) != expected:
        raise OutputAdmissionError("archival family logical/checkpoint/custody inventory is not exact")
    indexed = {item["file_name"]: item for item in artifacts}
    for item in artifacts:
        same([item["role"], item["schema_identity"], item["media_type"]],
             list(artifact_identity(action, item["file_name"])), "archival artifact role/schema/media")
        archive.uint(item["size_bytes"], "logical size")
        archive.sha(item["sha256"], "logical SHA")
    if sum(item["size_bytes"] for item in artifacts) > extent.declared.max_output_bytes:
        raise OutputAdmissionError("archival family canonical output exceeds its bound")
    report = predecessor._bound_report(directory_fd, indexed[REPORT_NAME],
                                        extent.declared.metadata_output_bytes)
    validate_document(registry, report, REPORT_SCHEMA, "archival retention report")
    hardware = request["action_inputs"]["hardware_control"]
    for key, expected_value in dict(action_id=action, plan_sha256=plan_sha256(plan),
                                    mapping_id=hardware["mapping_id"]).items():
        same(report[key], expected_value, "retention " + key)
    prestate = hardware["prestate"]
    for state, plot in zip(("H0", "H1"), report["whole_plots"], strict=True):
        applied = [dict(cpu=v["cpu"], complete_value_hex=f"{int(v['complete_value_hex'], 16) | 15:016x}")
                   for v in prestate] if state == "H1" else []
        same(plot, dict(state=state, apply_readback=applied,
            restore_readback=list(reversed(prestate)) if state == "H1" else [],
            restoration_verified=True), "archival whole-plot readbacks")
    if (len(report["captures"]) != len(extent.captures)
            or len(report["native_results_after_cleanup"]) != len(extent.captures)):
        raise OutputAdmissionError("archival family capture/final result coverage differs")
    for capture, retained in zip(extent.captures, report["captures"], strict=True):
        raw = [indexed[name] for name in capture_names(action, capture.ordinal)]
        cp = indexed[f"formal-capture-{capture.ordinal}-final-checkpoint.json"]
        receipt = indexed[f"formal-capture-{capture.ordinal}-archive-custody.json"]
        same(retained, dict(ordinal=capture.ordinal, artifacts=[reference(i) for i in raw],
            native_complete=True, checkpoint=reference(cp), archive_custody=reference(receipt)),
            "archival capture original bindings")
        if cp["size_bytes"] > plan["storage"]["checkpoint_bytes"]:
            raise OutputAdmissionError("native checkpoint exceeds signed bound")
        all_files = [*raw, cp, receipt]
        if sum(i["size_bytes"] for i in all_files) > capture.declared.max_output_bytes:
            raise OutputAdmissionError("archival capture canonical output exceeds bound")
        if sum(i["size_bytes"] for i in all_files if i["media_type"] == "application/json") > capture.declared.metadata_output_bytes:
            raise OutputAdmissionError("archival capture metadata exceeds bound")
    return plan, extent, report


@dataclass(frozen=True)
class AnalysisLimits:
    """Original finite offline resource plan; not experimental authority."""
    original_bytes: bytes
    binding: archive.PhysicalBinding
    parent_address_space_bytes: int
    total_memory_bytes: int
    custody: custody.CustodyLimits
    runtime: runtime.RetainedReadbackLimits
    decoder: archive.DecodeLimits

    def validate(self, plan, extent, profile):
        if (type(self.runtime) is not runtime.RetainedReadbackLimits
                or type(self.custody) is not custody.CustodyLimits
                or type(self.decoder) is not archive.DecodeLimits):
            raise OutputAdmissionError("offline analysis requires exact retained limits, not collection authority")
        self.binding.validate()
        if (type(self.original_bytes) is not bytes or len(self.original_bytes) > 65536
                or self.binding != archive.PhysicalBinding(len(self.original_bytes), sha256(self.original_bytes))):
            raise OutputAdmissionError("offline analysis original resource-plan binding differs")
        expected = dict(schema_version="cpu-prefetch-stage17-archive-analysis-limits/1",
            plan_sha256=plan_sha256(plan), program_scope_sha256=plan["storage"]["program_scope_sha256"],
            implementation_profile_sha256=profile.decoder.implementation_profile_sha256,
            parent_address_space_bytes=self.parent_address_space_bytes,
            total_memory_bytes=self.total_memory_bytes,
            custody=asdict(self.custody), runtime=asdict(self.runtime), decoder=asdict(self.decoder),
            execution_authority=False, phase18_authority=False)
        same(archive.parse_json(self.original_bytes), expected, "original analysis resource plan")
        self.custody.validate()
        self.decoder.validate()
        for name, value in vars(self.runtime).items():
            archive.uint(value, name, positive=True)
        deadline = self.runtime.deadline_ns
        if not (deadline == self.custody.deadline_ns == self.decoder.deadline_ns):
            raise OutputAdmissionError("offline deadlines differ (historical collection expiry is not an analysis deadline)")
        self.runtime.before_spawn()
        storage = plan["storage"]
        archive.uint(self.parent_address_space_bytes, "offline parent AS", positive=True)
        archive.uint(self.total_memory_bytes, "offline aggregate memory", positive=True)
        required_memory = archive.checked_sum(self.parent_address_space_bytes,
            self.runtime.broker_address_space_bytes, self.runtime.codec_address_space_bytes)
        if not required_memory <= self.total_memory_bytes <= extent.declared.memory_bytes:
            raise OutputAdmissionError("offline aggregate memory omits parent/broker/decoder or exceeds family ceiling")
        actual_as, _ = resource.getrlimit(resource.RLIMIT_AS)
        if actual_as == resource.RLIM_INFINITY or not 0 < actual_as <= self.parent_address_space_bytes:
            raise OutputAdmissionError("offline analysis parent AS is not separately bounded")
        if (self.runtime.broker_address_space_bytes > storage["broker_address_space_bytes"]
                or self.runtime.codec_address_space_bytes != storage["codec_address_space_bytes"]
                or self.decoder.max_canonical_bytes > storage["analysis_capture_workspace_bytes"]
                or self.decoder.max_archive_bytes > storage["archive_quota_bytes"]):
            raise OutputAdmissionError("offline analysis exceeds signed storage resource ceilings")
        required = sum(len(capture_names(plan["action_id"], c.ordinal)) for c in extent.captures)
        if self.runtime.max_children != required:
            raise OutputAdmissionError("offline decoder child count must equal one readback per original artifact")
        minimum = (runtime.supervisor.predecessor.TERM_GRACE_NS
                   + runtime.supervisor.predecessor.KILL_GRACE_NS)
        if self.runtime.cleanup_reserve_ns < minimum:
            raise OutputAdmissionError("offline cleanup reserve omits fixed child cleanup grace")


def _root_binding(path):
    value = path.stat(follow_symlinks=False)
    return dict(absolute_path=str(path), device=value.st_dev, inode=value.st_ino,
                owner_uid=value.st_uid, mode=f"{stat.S_IMODE(value.st_mode):04o}")


def _verified_inventory(*, store, plan, extent, report, profile, decoder_limits,
                        readback=None, metadata_only=False):
    """Private real-byte seam. Production supplies only its fixed qualified client."""
    if store.family_id not in store._families:
        raise OutputAdmissionError("family has no original ledger registration")
    same(store.scope["program_id"], plan["storage"]["program_id"], "shared program ID")
    current = store.working.stat(follow_symlinks=False)
    original = store._families[store.family_id]
    same([current.st_dev, current.st_ino], [original["device"], original["inode"]], "family ledger root")
    store._family_identity = (current.st_dev, current.st_ino)
    expected_ids = {store.family_id + ":" + name for c in extent.captures
                    for name in capture_names(plan["action_id"], c.ordinal)}
    actual_ids = {key for key in store._states if key.startswith(store.family_id + ":")}
    if actual_ids != expected_ids or any(family == store.family_id for family, _ in store._capture_pending):
        raise OutputAdmissionError("family ledger has missing/foreign artifacts or unfinished checkpoints")
    inventory = []
    for item, retained, final in zip(plan["captures"], report["captures"],
                                      report["native_results_after_cleanup"], strict=True):
        arguments = dict(store=store, action=plan["action_id"],
            capture=item["capture"], checkpoint_binding=retained["checkpoint"],
            receipt_binding=retained["archive_custody"], decoder_profile=profile.decoder,
            decoder_limits=decoder_limits)
        verified = (capture_registry.verify_capture_metadata(**arguments) if metadata_only
                    else capture_registry.verify_capture(**arguments, readback=readback))
        same(verified["native_result_after_cleanup"], final, "outer final native result versus checkpoint")
        same([row["logical"] for row in verified["artifacts"]], retained["artifacts"],
             "outer original canonical inventory versus archived originals")
        inventory.append(verified)
    store._check()
    tip = store.ledger_binding()
    return dict(captures=inventory, scope_bindings=dict(program_id=store.scope["program_id"],
        implementation_profile_sha256=profile.decoder.implementation_profile_sha256,
        program_scope_sha256=store.scope_sha256, phase_root_binding=_root_binding(store.working),
        program_root_binding=_root_binding(store.root),
        ledger_head=dict(sequence_number=store._sequence - 1, sha256=tip.sha256)),
        inverse_readback_performed=not metadata_only,
        scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False)


def _metadata_decode_limits(plan, extent, profile, deadline_ns):
    # These match the immutable codec geometry and cold-job header/frame bounds;
    # canonical/staging bounds remain the actual signed prospective declarations.
    import stage17_formal_archive_jobs_v1 as jobs
    largest = max(c.declared.max_output_bytes for c in extent.captures)
    block = archive.BYTE_BLOCK
    for item in plan["captures"]:
        capture = item["capture"]
        for name in capture_names(plan["action_id"], capture["ordinal"]):
            role = capture_registry.role_profile(plan["action_id"], name)
            phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
            width = role.row_bytes(capture[phase]["run_id"] if phase else None)
            if width is not None:
                block = max(block, archive.checked_product(archive.ROWS_PER_BLOCK, width))
    minimum_block = archive.ROWS_PER_BLOCK * 8
    return archive.DecodeLimits(jobs.HEADER_BYTES,
        archive.checked_sum(archive.checked_product(block, 2), jobs.IO_CHUNK_BYTES),
        block, plan["storage"]["archive_staging_bytes"], largest,
        (largest + minimum_block - 1) // minimum_block,
        1 << profile.decoder.window_log, deadline_ns)


def verify_archived_formal_metadata(*, registry, repository_root, directory_fd, result,
        request, authorization_sha256, synthetic_test_only, archive_runtime_profile,
        deadline_ns):
    """Collection completion: exact ledger/checkpoint/header + physical SHA only.

    No codec child, independent inverse claim, scientific credit or next-capture
    authorization. The existing executor owns the current absolute deadline.
    """
    try:
        if not isinstance(archive_runtime_profile, runtime.RuntimeProfile):
            raise OutputAdmissionError("qualified archive RuntimeProfile is required")
        archive.uint(deadline_ns, "collection metadata deadline", positive=True)
        plan, extent, report = _metadata(registry=registry, directory_fd=directory_fd,
            result=result, request=request, authorization_sha256=authorization_sha256,
            synthetic_test_only=synthetic_test_only)
        storage = plan["storage"]
        same(archive_runtime_profile.decoder.implementation_profile_sha256,
             storage["implementation_profile_sha256"], "qualified archive implementation profile")
        phase = Path(request["evidence_root_binding"]["absolute_path"])
        if phase.parent.name != "working" or phase.name != plan_sha256(plan):
            raise OutputAdmissionError("archive phase root is not program/working/native-plan-SHA")
        descriptor, identity = roots._componentwise_output_root(phase, Path(repository_root),
                                                              request["evidence_root_binding"])
        try:
            current = os.fstat(directory_fd)
            same([current.st_dev, current.st_ino], list(identity), "held output descriptor")
            # Reuse the executor's exact finite collection guards, not fresh
            # implicit analysis authority or a second experimental timeout.
            from stage17_fixed_action_executor_v11 import custody_limits
            with custody.ProgramStore(phase.parent.parent,
                    scope_sha256=storage["program_scope_sha256"], family_id=phase.name,
                    limits=custody_limits(storage, deadline_ns)) as store:
                verified = _verified_inventory(store=store, plan=plan, extent=extent,
                    report=report, profile=archive_runtime_profile,
                    decoder_limits=_metadata_decode_limits(plan, extent, archive_runtime_profile, deadline_ns),
                    metadata_only=True)
                roots._verify_root_identity(descriptor, identity)
                same(verified["scope_bindings"]["phase_root_binding"],
                     request["evidence_root_binding"], "actual signed phase root")
                return verified
        finally:
            os.close(descriptor)
    except OutputAdmissionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as error:
        raise OutputAdmissionError("archive metadata admission rejected: " + str(error)) from error


def verify_archived_formal_family(*, registry, repository_root, directory_fd, result,
        request, authorization_sha256, synthetic_test_only, archive_runtime_profile,
        analysis_limits=None):
    """Requires the controller's qualified profile and a dedicated bounded broker.

    No public callback/boolean-proof seam; unavailable broker or absent finite
    offline admission fails closed. Physical inventory remains uncredited science.
    """
    try:
        if not isinstance(archive_runtime_profile, runtime.RuntimeProfile):
            raise OutputAdmissionError("qualified archive RuntimeProfile is required")
        if not isinstance(analysis_limits, AnalysisLimits):
            raise OutputAdmissionError("separate finite original offline analysis resource plan is required")
        actual_as, _ = resource.getrlimit(resource.RLIMIT_AS)
        parent_limit = archive.uint(analysis_limits.parent_address_space_bytes, "offline parent AS", positive=True)
        if actual_as == resource.RLIM_INFINITY or not 0 < actual_as <= parent_limit:
            raise OutputAdmissionError("offline analysis parent AS is not separately bounded")
        plan, extent, report = _metadata(registry=registry, directory_fd=directory_fd,
            result=result, request=request, authorization_sha256=authorization_sha256,
            synthetic_test_only=synthetic_test_only)
        storage = plan["storage"]
        same(archive_runtime_profile.decoder.implementation_profile_sha256,
             storage["implementation_profile_sha256"], "qualified archive implementation profile")
        analysis_limits.validate(plan, extent, archive_runtime_profile)
        phase = Path(request["evidence_root_binding"]["absolute_path"])
        if phase.parent.name != "working" or phase.name != plan_sha256(plan):
            raise OutputAdmissionError("archive phase root is not program/working/native-plan-SHA")
        root_fd, identity = roots._componentwise_output_root(phase, Path(repository_root), request["evidence_root_binding"])
        try:
            observed = os.fstat(directory_fd)
            same([observed.st_dev, observed.st_ino], list(identity), "held output descriptor")
            # The fixed broker integration is deliberately lazy; the qualified
            # implementation, never caller-provided proof flags, owns execution.
            from stage17_formal_archive_broker_v1 import RetainedReadbackClient
            with custody.ProgramStore(phase.parent.parent,
                    scope_sha256=storage["program_scope_sha256"], family_id=phase.name,
                    limits=analysis_limits.custody) as store:
                with RetainedReadbackClient(profile=archive_runtime_profile,
                        limits=analysis_limits.runtime) as client:
                    verified = _verified_inventory(store=store, plan=plan, extent=extent,
                        report=report, profile=archive_runtime_profile,
                        decoder_limits=analysis_limits.decoder, readback=client.readback)
                verified["analysis_plan_binding"] = asdict(analysis_limits.binding)
                roots._verify_root_identity(root_fd, identity)
                same(verified["scope_bindings"]["phase_root_binding"],
                     request["evidence_root_binding"], "actual signed phase root")
                return verified
        finally:
            os.close(root_fd)
    except OutputAdmissionError:
        raise
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as error:
        raise OutputAdmissionError("archive-family admission rejected: " + str(error)) from error


def validate_worker_result(*, registry, directory_fd, result, request,
        authorization_sha256, synthetic_test_only, archive_runtime_profile=None,
        analysis_limits=None, repository_root=None):
    if not is_archived(request):
        return predecessor.validate_worker_result(registry=registry, directory_fd=directory_fd,
            result=result, request=request, authorization_sha256=authorization_sha256,
            synthetic_test_only=synthetic_test_only)
    return verify_archived_formal_family(registry=registry, repository_root=repository_root,
        directory_fd=directory_fd, result=result, request=request,
        authorization_sha256=authorization_sha256, synthetic_test_only=synthetic_test_only,
        archive_runtime_profile=archive_runtime_profile, analysis_limits=analysis_limits)
