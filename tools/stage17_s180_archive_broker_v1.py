"""Fixed S180 cold broker: original checkpoint, explicit D310 scope, D233 codec.

Only the qualified parent may invoke this while its exact native child is parked.
This consumes authenticated prospective inputs; it does not admit a pilot itself.
"""
from dataclasses import asdict
import hashlib
import os
from pathlib import Path

import stage17_formal_archive_broker_v1 as base
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_custody_v1 as custody
import stage17_s180_archive_custody_v1 as storage
import stage17_s180_checkpoint_v1 as contract
from stage17_formal_archive_jobs_v1 import build_capture_jobs
from stage17_formal_checkpoint_v1 import PinnedWorker

REQUEST_SCHEMA = "cpu-prefetch-stage17-s180-archive-broker-request/1"
RESULT_SCHEMA = "cpu-prefetch-stage17-s180-archive-broker-result/1"


def capture_contract(request, ordinal):
    if (type(request) is not dict or request.get("schema_version") != "cpu-prefetch-stage17-s180-session-request/1"
            or type(request.get("session_id")) is not str or not request["session_id"]):
        raise base.BrokerError("S180 original request identity/version differs")
    plan = request["plan"]
    if (plan.get("schema_version") != "cpu-prefetch-stage17-s180-session-plan/1"
            or hashlib.sha256(archive.canonical(plan["blueprint"])).hexdigest() != contract.BLUEPRINT_SHA256):
        raise base.BrokerError("S180 exact approved blueprint differs")
    rows = sorted(plan["blueprint"]["captures"], key=lambda r: r["execution_ordinal"])
    entries = plan["captures"]
    if type(entries) is not list or len(entries) != 180:
        raise base.BrokerError("S180 whole family must contain 180 captures")
    for i, (entry, row) in enumerate(zip(entries, rows, strict=True)):
        if (type(entry) is not dict or type(entry.get("execution_ordinal")) is not int
                or entry["execution_ordinal"] != i or type(entry.get("cell_ordinal")) is not int
                or entry["cell_ordinal"] != row["cell_ordinal"]):
            raise base.BrokerError("S180 family order differs from frozen blueprint")
    settings = plan["storage"]
    if (settings.get("pilot_policy_id") != "D310-S180-LOSSLESS-STAND-PRIMARY-v1"
            or settings.get("approval_sha256") != contract.APPROVAL_SHA256):
        raise base.BrokerError("S180 pilot storage extension is absent")
    archive.sha(request["prerequisite_bindings"]["ext009_resolution_sha256"], "S180 EXT009 binding")
    archive.uint(ordinal, "S180 ordinal")
    contract.capture_names(ordinal)
    return dict(rows[ordinal], session_id=request["session_id"])


class ArchiveBrokerClient(base._Client):
    request_schema = REQUEST_SCHEMA
    result_schema = RESULT_SCHEMA
    entry_mode = "s180_broker"
    entry_module = "stage17_s180_archive_broker_v1"

    def __init__(self, *, profile, limits, identity_model, native_worker):
        if type(limits) is not runtime.RuntimeLimits or not isinstance(native_worker, PinnedWorker):
            raise base.BrokerError("S180 live broker requires finite authority and a pinned native")
        super().__init__(profile=profile, limits=limits, identity_model=identity_model, native_worker=native_worker)

    def archive_capture(self, *, program_root, scope_sha256, family_id, custody_limits,
                        request_document, capture_ordinal, checkpoint):
        capture_contract(request_document, capture_ordinal)
        if hashlib.sha256(archive.canonical(request_document["plan"])).hexdigest() != family_id:
            raise base.BrokerError("S180 family hash differs from original plan")
        self.native_worker.observe_quiescence()
        parameters = dict(program_root=str(Path(program_root).absolute()), scope_sha256=scope_sha256,
            family_id=family_id, custody_limits=asdict(custody_limits), request_document=request_document,
            capture_ordinal=capture_ordinal, checkpoint=asdict(checkpoint),
            native=dict(pid=self.native_worker.pid, start_ticks=self.native_worker.start_ticks,
                        pidfd=self.native_worker.descriptor))
        value, cleanup = self._invoke("archive_s180_capture", parameters)
        if (set(value) != {"receipt", "status", "receipt_ledger_record"}
                or value["status"] not in ("ARCHIVED_AND_RELEASED", "ARCHIVED_FAILED_EVIDENCE")):
            raise base.BrokerError("S180 broker result contract differs")
        receipt = custody.BoundFile(**value["receipt"])
        registration = custody.BoundFile(**value["receipt_ledger_record"])
        receipt.binding()
        registration.binding()
        self.native_worker.observe_quiescence()
        return base.BrokerOutcome(receipt, value["status"], registration, cleanup)


def _broker_child(request_fd, result_fd, input_limit, result_limit):
    raw = runtime._read_sealed(request_fd, input_limit)
    request = archive.parse_json(raw)
    if (set(request) != {"schema_version", "mode", "profile", "limits", "parameters"}
            or request["schema_version"] != REQUEST_SCHEMA or request["mode"] != "archive_s180_capture"):
        raise base.BrokerError("S180 fixed broker request shape/version differs")
    profile = base._profile(request["profile"])
    limits = runtime.RuntimeLimits(**request["limits"])
    limits.validate()
    p = request["parameters"]
    if set(p) != {"program_root", "scope_sha256", "family_id", "custody_limits", "request_document",
                  "capture_ordinal", "checkpoint", "native"}:
        raise base.BrokerError("S180 broker parameter fields differ")
    original, ordinal = p["request_document"], p["capture_ordinal"]
    capture = capture_contract(original, ordinal)
    plan = original["plan"]
    if hashlib.sha256(archive.canonical(plan)).hexdigest() != p["family_id"]:
        raise base.BrokerError("S180 actual plan hash differs")
    native = p["native"]
    if set(native) != {"pid", "start_ticks", "pidfd"}:
        raise base.BrokerError("S180 native handle fields differ")
    fields = dict(line.split(":", 1) for line in Path(f"/proc/self/fdinfo/{native['pidfd']}").read_text().splitlines() if ":" in line)
    if int(fields.get("Pid", "-1").strip()) != native["pid"]:
        raise base.BrokerError("S180 inherited pidfd differs")
    worker = PinnedWorker(native["pid"])
    try:
        if worker.start_ticks != native["start_ticks"]:
            raise base.BrokerError("S180 native start identity differs")
        def observe():
            worker.observe_quiescence()
        with storage.ProgramStore(Path(p["program_root"]), scope_sha256=p["scope_sha256"], family_id=p["family_id"],
                ext009_resolution_sha256=original["prerequisite_bindings"]["ext009_resolution_sha256"],
                limits=custody.CustodyLimits(**p["custody_limits"])) as store:
            store.prepare_family(p["family_id"])
            checkpoint = custody.BoundFile(**p["checkpoint"])
            if checkpoint.file_name != f"s180-e{ordinal}-checkpoint.json":
                raise base.BrokerError("S180 checkpoint filename differs")
            document = archive.parse_json(store._read_bound(store.working / checkpoint.file_name,
                checkpoint.binding(), store.limits.max_checkpoint_bytes))
            sources, jobs = build_capture_jobs(store=store, action="S180", capture=capture, document=document,
                profile=profile, storage=plan["storage"], maximum_capture_bytes=plan["captures"][ordinal]["execution_budget"]["max_output_bytes"],
                deadline_ns=limits.final_deadline_ns, verify_quiescence=observe)
            contract.require_private_cleanup_for_codec(document["native_result_after_private_cleanup"])
            def verify(document, sources):
                contract.require_private_cleanup_for_codec(document["native_result_after_private_cleanup"])
                contract.validate_checkpoint(document, plan_sha256=store.family_id, program_scope_sha256=store.scope_sha256,
                    session_id=original["session_id"], ordinal=ordinal, sources=sources)
                observe()
            engine = runtime.ColdArchiveRuntime(store, profile=profile, limits=limits)
            value = asdict(engine.archive_capture(checkpoint, sources, jobs, verify_checkpoint=verify))
            children = engine.child_count
    finally:
        worker.close()
    output = archive.canonical(dict(schema_version=RESULT_SCHEMA, mode=request["mode"],
        request_sha256=hashlib.sha256(raw).hexdigest(), result=runtime._jsonable(value), codec_children=children))
    if len(output) > result_limit or os.pwrite(result_fd, output, 0) != len(output):
        raise base.BrokerError("S180 broker result exceeds bound or write was partial")
    os.fsync(result_fd)
