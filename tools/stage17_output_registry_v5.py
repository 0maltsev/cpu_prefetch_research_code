#!/usr/bin/env python3
"""Output-registry successor implementing ADR-0161: fixes the
`_validate_run_families` offered-count frozen-plan cross-check, which
compared the wrong field.

`stage17_output_registry_v4.py`'s real worker output schema (`config/
schemas/stage17-run-output-v3.schema.json`) deliberately carries two
distinct, both-required fields that happen to share a name with two
different request-side/output-side concepts: `planned_attempt_
capacity` echoes the request's own `offered_count` ceiling, while the
output's own `offered_count` field holds the real, measured, duration-
bound attempted count (`capture.report.attempted` in `src/runner/
stage17_fixed_action.cpp`) -- the actual scientific measurement, which
is *expected* to differ from the ceiling whenever `duration_ticks` (not
the ceiling) is the binding constraint, exactly the real, intended
design for Q16b/Q16c/the pilot's fixed-duration continuous-ready
capture. The original check at `v4.py:353` compared the output's own
(achieved) `offered_count` against the request's (ceiling) `offered_
count` -- two different quantities that happen to share a JSON key
name across the request and output schemas. This file changes only
that one comparison to read `document["planned_attempt_capacity"]`
instead, matching the field the real worker actually populates for
this exact cross-check.

`_validate_run_families` is defined once, in `v4.py`; its real caller
(`validate_worker_result`, also defined in `v4.py`) reaches it via a
bare name resolved against `v4.py`'s own module globals -- the same
free-variable-resolution rule established repeatedly this engagement
(ADR-0126/ADR-0131). So the only correct way to change it is a fresh
copy here, faithful to `v4`'s own body except for the one targeted
line ADR-0161 describes, monkey-patched onto `v4`'s own module
attribute so `validate_worker_result`'s bare call sees the fix.
"""

from __future__ import annotations

import pathlib
from typing import Any

import stage17_output_registry_v4 as base
import stage17_raw_stream_decoder_v1 as raw_decoder

OutputAdmissionError = base.OutputAdmissionError
PinnedOutputRegistry = base.PinnedOutputRegistry
RAW_ROLES = base.RAW_ROLES
RAW_SCHEMA = base.RAW_SCHEMA
RUN_JSON = base.RUN_JSON
SUMMARY_ROLE = base.SUMMARY_ROLE
_json_output = base._json_output
_raw_maximum = base._raw_maximum
_run_groups = base._run_groups
_stream_binding = base._stream_binding
validate_document = base.validate_document


def _validate_run_families(
    registry: PinnedOutputRegistry, directory_fd: int, action_id: str,
    request: dict[str, Any], artifacts: list[dict[str, Any]],
) -> None:
    prefixes, groups = _run_groups(action_id, request, artifacts)
    summary_role, summary_schema = SUMMARY_ROLE[action_id]
    role_set = set(RAW_ROLES) | set(RUN_JSON) | {summary_role}
    for prefix, run in prefixes.items():
        group = groups[prefix]
        if {item["role"] for item in group} != role_set or len(group) != 10:
            raise OutputAdmissionError("per-run role family is incomplete or duplicated")
        maximum = _raw_maximum(run)
        raw_hashes: dict[str, str] = {}
        documents: dict[str, dict[str, Any]] = {}
        for binding in group:
            _stream_binding(directory_fd, binding, maximum)
            role = binding["role"]
            if role in RAW_ROLES:
                if binding["media_type"] != "application/octet-stream" or binding["schema_identity"] != RAW_SCHEMA:
                    raise OutputAdmissionError("raw observation contract drifted")
                raw_hashes[role] = binding["sha256"]
                continue
            if binding["media_type"] != "application/json":
                raise OutputAdmissionError("run JSON artifact media type drifted")
            document = _json_output(directory_fd, binding["file_name"], binding["size_bytes"])
            documents[role] = document
            if role == summary_role:
                if binding["schema_identity"] != summary_schema:
                    raise OutputAdmissionError("run summary schema identity drifted")
                validate_document(registry, document,
                                  "config/schemas/stage17-run-output-v3.schema.json",
                                  binding["file_name"])
                if any(document.get(key) != run.get(key) for key in (
                    "run_id", "plan_sha256", "schedule_sha256", "seed_id",
                    "runner_admission_sha256", "package", "cell_ordinal",
                    "repetition_ordinal", "hardware_state", "placement",
                    "working_set_class", "load_level",
                )):
                    raise OutputAdmissionError("run summary differs from signed request")
                if document["planned_attempt_capacity"] != run["offered_count"]:
                    raise OutputAdmissionError("run offered count differs from frozen plan")
            else:
                identity, schema_path = RUN_JSON[role]
                if binding["schema_identity"] != identity:
                    raise OutputAdmissionError("run JSON schema identity drifted")
                if schema_path is not None:
                    validate_document(registry, document, schema_path,
                                      binding["file_name"])
        audit = documents.get("JOIN_AUDIT")
        summary = documents.get(summary_role)
        if summary is None:
            raise OutputAdmissionError("run summary is absent")
        raw_bindings = {item["role"]: item for item in group
                        if item["role"] in RAW_ROLES}
        independently_joined = raw_decoder.reconcile(
            pathlib.Path(f"/proc/self/fd/{directory_fd}"),
            {
                "schema_version": "cpu-prefetch-stage17-raw-stream-contract/1",
                "run_id": run["run_id"],
                "physical_format": RAW_SCHEMA,
                "streams": {
                    "producer": {
                        "path": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["PRODUCER_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["offered_count"],
                    },
                    "consumer": {
                        "path": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["CONSUMER_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["consumed_count"],
                    },
                    "joined": {
                        "path": raw_bindings["JOINED_RAW_OBSERVATIONS"]["file_name"],
                        "size_bytes": raw_bindings["JOINED_RAW_OBSERVATIONS"]["size_bytes"],
                        "sha256": raw_bindings["JOINED_RAW_OBSERVATIONS"]["sha256"],
                        "row_count": summary["accepted_count"],
                    },
                },
            },
        )
        if (independently_joined["offered_count"] != summary["offered_count"]
                or independently_joined["accepted_count"] != summary["accepted_count"]
                or independently_joined["full_count"] != summary["full_count"]
                or independently_joined["consumed_count"] != summary["consumed_count"]
                or (independently_joined["zero_loss_status"] == "PASS")
                is not summary["zero_loss"]):
            raise OutputAdmissionError(
                "worker summary differs from independently decoded records"
            )
        if (audit is None or audit.get("run_id") != run["run_id"]
                or audit.get("producer_raw_sha256")
                != raw_hashes.get("PRODUCER_RAW_OBSERVATIONS")
                or audit.get("consumer_raw_sha256")
                != raw_hashes.get("CONSUMER_RAW_OBSERVATIONS")
                or audit.get("joined_raw_sha256")
                != raw_hashes.get("JOINED_RAW_OBSERVATIONS")
                or audit.get("producer_rows") != summary["offered_count"]
                or audit.get("accepted_rows") != summary["accepted_count"]
                or audit.get("full_rows") != summary["full_count"]
                or audit.get("consumer_rows") != summary["consumed_count"]
                or audit.get("join_status") != "PASSED"
                or audit.get("record_index_is_event_identity") is not False):
            raise OutputAdmissionError("join audit differs from exact raw stream bytes")
        for role in ("PRODUCER_RAW_ENVELOPE", "CONSUMER_RAW_ENVELOPE",
                     "JOINED_RAW_ENVELOPE"):
            if documents.get(role, {}).get("run_id") != run["run_id"]:
                raise OutputAdmissionError("raw envelope run lineage drifted")
        residency = documents.get("PAGE_RESIDENCY_PROVENANCE")
        expected_consumer = 1 if run["placement"] == "NEAR" else 26
        if (residency is None or residency.get("run_id") != run["run_id"]
                or residency.get("producer_cpu") != 0
                or residency.get("consumer_cpu") != expected_consumer
                or residency.get("producer_migrated") is not False
                or residency.get("consumer_migrated") is not False
                or residency.get("verified") is not True):
            raise OutputAdmissionError("page/affinity/migration evidence drifted")


base._validate_run_families = _validate_run_families
