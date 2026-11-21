"""Cold S180 parent planning from actual native sizing, with no run authority.

The qualified parent still owns provenance, signatures, namespace consumption,
complete EXT009 admission and the one operational window. A ceiling-only sizing
document cannot be converted to a collection plan by this module.
"""
from __future__ import annotations
import contextlib
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
from stage17_s180_checkpoint_v1 import BLUEPRINT_SHA256

SIZING = "cpu-prefetch-stage17-s180-sizing-plan/1"
PLAN = "cpu-prefetch-stage17-s180-session-plan/1"
REPORT = "cpu-prefetch-stage17-s180-prospective-layouts/1"
DAY_NS = 86_400_000_000_000
OUTPUT_LIMIT = 1024**2


class PlanError(archive.ArchiveError):
    pass


def require(condition, message):
    if not condition:
        raise PlanError("S180 planning: " + message)


def sha(document):
    return hashlib.sha256(archive.canonical(document)).hexdigest()


def _u(value, label, positive=False):
    return archive.uint(value, label, positive=positive)


def source_groups(sizing):
    require(sizing["schema_version"] == SIZING and sha(sizing["blueprint"]) == BLUEPRINT_SHA256,
            "exact approved sizing blueprint required")
    rows = sorted(sizing["blueprint"]["captures"], key=lambda r: r["execution_ordinal"])
    entries = sizing["captures"]
    require(type(entries) is list and len(entries) == 180, "complete family required")
    groups, order, artifacts, schedules = {}, [], set(), set()
    for i, (entry, row) in enumerate(zip(entries, rows, strict=True)):
        require(type(entry["execution_ordinal"]) is int and entry["execution_ordinal"] == i
                and type(entry["cell_ordinal"]) is int and entry["cell_ordinal"] == row["cell_ordinal"],
                "frozen capture order differs")
        key = row["placement"], row["working_set_class"], row["load_level"]
        phases = entry["phases"]
        require(type(phases) is list and len(phases) == 2, "two phases required")
        common = []
        for phase, p in enumerate(phases):
            origin = _u(p["source_origin_ticks"], "source origin")
            horizon = _u(p["source_horizon_ticks"], "source horizon", True)
            count = _u(p["offered_count"], "offered count", phase == 1)
            require(horizon - origin == row["warmup_ns" if phase == 0 else "measurement_ns"] * 1000,
                    "fixed source window differs")
            require(count <= _u(p["producer_attempt_limit"], "attempt bound", True),
                    "source count exceeds attempt bound")
            source = p["source_artifact"]
            if source is not None:
                require(type(source) is dict and set(source) == {"artifact_id", "sha256"}
                        and type(source["artifact_id"]) is str and source["artifact_id"], "original binding malformed")
                archive.sha(source["sha256"], "source hash")
            require(type(p["schedule_id"]) is str and p["schedule_id"], "schedule identity missing")
            common.append(dict(schedule_id=p["schedule_id"], source_origin_ticks=origin,
                source_horizon_ticks=horizon, offered_count=count, source_artifact=source))
        if key in groups:
            require(archive.canonical(groups[key]) == archive.canonical(common), "paired source coordinates differ")
        else:
            for p in common:
                require(p["schedule_id"] not in schedules, "independent schedule identity reused")
                schedules.add(p["schedule_id"])
                if p["source_artifact"] is not None:
                    artifact = p["source_artifact"]["artifact_id"]
                    require(artifact not in artifacts, "independent source artifact reused")
                    artifacts.add(artifact)
            groups[key] = common
            order.append(key)
    require(len(groups) == 18 and len(schedules) == 36, "all18 common source pairs required")
    return groups, order


def native_layouts(sizing, *, worker: runtime.ImageBinding, deadline_ns):
    """One fixed read-only native description using exact sealed image/input.

    The caller's worker binding must come from its qualified profile for actual
    admission. A development binding supports software verification only.
    """
    source_groups(sizing)
    raw = archive.canonical(sizing)
    require(len(raw) <= 16*1024**2, "sizing input exceeds native ceiling")
    require(type(deadline_ns) is int and time.monotonic_ns() < deadline_ns, "description deadline expired")
    with contextlib.ExitStack() as stack:
        executable = runtime._pin_image(worker, deadline_ns, stack)
        control = runtime._sealed_input(raw, "s180-sizing-input")
        stack.callback(os.close, control)
        # The native command can only calculate the fixed180 layouts. It has no
        # descriptor context, output directory, authority or source arrays.
        result = subprocess.run([f"/proc/self/fd/{executable}", "--describe-stage17-s180-layouts-v1",
            f"/proc/self/fd/{control}"], pass_fds=(executable, control), stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
            env={"PATH":"/usr/bin:/bin", "LC_ALL":"C", "TZ":"UTC"},
            timeout=max(0.001, (deadline_ns-time.monotonic_ns())/1e9))
        require(time.monotonic_ns() < deadline_ns and result.returncode == 0,
                "native description failed or expired: " + result.stderr[:1024].decode(errors="replace"))
        require(len(result.stdout) <= OUTPUT_LIMIT and len(result.stderr) <= 65536, "native output bound exceeded")
    report = archive.parse_json(result.stdout.strip())
    require(report["schema_version"] == REPORT and report["binary_sha256"] == worker.sha256
            and report["source_revision"] == sizing["source_revision"]
            and report["sizing_plan_sha256"] == sha(sizing), "actual native description binding differs")
    require(report["execution_authority"] is False and report["phase18_authority"] is False
            and report["session_admission_performed"] is False
            and report["source_count_basis"] == sizing["source_count_basis"], "description scope differs")
    return report


def resource_minima(sizing, report):
    groups, order = source_groups(sizing)
    require(report["schema_version"] == REPORT and report["sizing_plan_sha256"] == sha(sizing),
            "resource report belongs to another sizing document")
    contexts, rows = report["contexts"], report["captures"]
    require(type(contexts) is list and len(contexts) == 6 and type(rows) is list and len(rows) == 180,
            "complete native report required")
    shared = 0
    for i, context in enumerate(contexts):
        require(type(context["context_ordinal"]) is int and context["context_ordinal"] == i, "context order differs")
        shared = archive.checked_sum(shared, _u(context["records_bytes"], "shared records", True),
                                     _u(context["queues_bytes"], "shared queues", True))
    private = 0
    for i, (row, entry) in enumerate(zip(rows, sizing["captures"], strict=True)):
        require(type(row["execution_ordinal"]) is int and row["execution_ordinal"] == i
                and row["cell_ordinal"] == entry["cell_ordinal"], "reported capture order differs")
        layout = row["expected_layout"]
        regions = layout["region_bytes"]
        require(type(regions) is list and len(regions) == 9, "nine native regions required")
        total = _u(layout["total_mapping_bytes"], "native mapping total", True)
        persistent = archive.checked_sum(_u(regions[7], "shared region", True), _u(regions[8], "shared region", True))
        require(total > persistent, "native mapping total omits private storage")
        private = max(private, total-persistent)
    retained = vector_peak = 0
    for key in order:
        for phase in groups[key]:
            amount = archive.checked_product(8, phase["offered_count"])
            vector_peak = max(vector_peak, archive.checked_sum(retained, archive.checked_product(2, amount)))
            retained = archive.checked_sum(retained, amount)
    budget = sizing["budget"]
    max_payload = max(_u(e["execution_budget"]["max_output_bytes"], "capture output", True) for e in sizing["captures"])
    final = _u(budget["final_metadata_bytes"], "final metadata", True)
    memory = archive.checked_sum(shared, private, vector_peak, max_payload, final)
    output = archive.checked_sum(final, _u(budget["entry_metadata_bytes"], "entry metadata", True),
        *(_u(e["execution_budget"]["max_output_bytes"], "capture output", True) for e in sizing["captures"]))
    duration = archive.checked_sum(*(_u(budget[k], k, k != "whole_plot_recovery_ns") for k in
        ("setup_ns", "whole_plot_transition_ns", "whole_plot_recovery_ns", "finalization_ns")),
        *(_u(e["execution_budget"]["watchdog_ns"], "capture watchdog", True) for e in sizing["captures"]))
    require(memory <= budget["memory_bytes"] and output <= budget["max_output_bytes"] and duration <= DAY_NS,
            "declared native memory/output/day envelope is insufficient")
    return dict(shared_mapping_bytes=shared, peak_private_mapping_bytes=private,
        retained_source_vector_bytes=retained, minimum_source_vector_limit_bytes=vector_peak,
        minimum_native_memory_bytes=memory, declared_native_output_bytes=output,
        native_family_watchdog_ns=duration, native_and_archive_process_count_upper=4501,
        sealed_source_bytes_not_in_native_vector_minimum=retained,
        complete_external_resources_included=False, whole_operational_eta_verified=False)


def prepare(sizing, *, worker: runtime.ImageBinding, deadline_ns):
    """Return a concrete collection-plan candidate, never admission/execution."""
    require(sizing.get("source_count_basis") == "EXACT_DECLARED_COUNTS",
            "prospective ceilings cannot become collection counts")
    groups, _ = source_groups(sizing)
    require(all(p["source_artifact"] is not None for phases in groups.values() for p in phases),
            "collection candidate requires explicit original source bindings")
    report = native_layouts(sizing, worker=worker, deadline_ns=deadline_ns)
    minimum = resource_minima(sizing, report)
    plan = copy.deepcopy(sizing)
    plan["schema_version"] = PLAN
    del plan["source_count_basis"]
    for entry, computed in zip(plan["captures"], report["captures"], strict=True):
        require("expected_layout" not in entry, "caller cannot inject a native layout")
        entry["expected_layout"] = computed["expected_layout"]
    proof = dict(schema_version="cpu-prefetch-stage17-s180-plan-preparation/1", plan_sha256=sha(plan),
        sizing_plan_sha256=sha(sizing), native_description_sha256=sha(report),
        native_binary_sha256=worker.sha256, source_revision=report["source_revision"], source_dirty=report["source_dirty"],
        resource_minima=minimum, source_bytes_verified=False, namespace_reservation_verified=False,
        signed_admission_verified=False, launch_ready=False, execution_authority=False, phase18_authority=False)
    return plan, proof
