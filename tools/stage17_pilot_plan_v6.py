#!/usr/bin/env python3
"""Additive successor to `stage17_pilot_plan_v5.py` (ADR-0169).

Real gap discovered live on the first-ever real execution attempt of the
compiled `STAGE17-BLINDED-PILOT` action: the worker's own admission-ticket
check (`load_sealed_runner_ticket`, `src/runner/stage17_fixed_action.cpp`)
recomputes `runner_admission_sha256`/`runner_evidence_set_sha256` via
`protocol::json::canonicalize` (`src/protocol/json.cpp`), which serializes
with sorted keys and compact separators but appends NO trailing newline.
`stage17_pilot_plan_v4.py`'s own `canonical()` -- used both to construct
those two hashes and, via `_validate_admission`, to independently
re-verify them at admission time -- appends `"\n"` before hashing. The two
canonicalizations therefore never agree on those two specific fields: a
value that satisfies the Python-side admission check is guaranteed to fail
the compiled worker's own check, and vice versa. Confirmed directly this
session by computing both candidate hashes against the real, admitted
EXT-008 plan and comparing against the stored value and the real worker's
observed failure (`S17-RUN-ADMISSION-HASH: sealed runner admission/
evidence bytes drifted`).

No other `canonical()`-derived field (`plan_core_sha256`,
`frozen_schedule_hash`, `seed_derivation_hash`) is independently
re-verified by the compiled worker at runtime -- only `runner_admission`/
`runner_evidence_set` go through `load_sealed_runner_ticket`. This fix is
therefore narrowly scoped to `_validate_admission`'s own two comparisons,
matching the compiled worker's real, unchanged behavior exactly; every
other use of `canonical()` (including elsewhere in `_validate_admission`
itself, e.g. `plan["plan_core_sha256"]`) is untouched.

`validate()` is redefined once, fully, in `v5.py`, which imports
`_validate_admission` by name (`from stage17_pilot_plan_v4 import (...,
_validate_admission, ...)`) rather than a bare-attribute lookup -- so the
free variable `_validate_admission` inside `v5.py`'s own `validate()`
resolves against `v5.py`'s own module globals at call time, not `v4.py`'s.
The only correct way to change what that call actually invokes is to
reassign `stage17_pilot_plan_v5._validate_admission` directly, which is
what this module does.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from jsonschema import Draft202012Validator

import stage17_pilot_plan_v5 as base


def canonical_no_newline(value: object) -> bytes:
    """Matches `protocol::json::canonicalize` exactly: sorted keys, compact
    separators, no trailing newline. Do not use for anything the compiled
    worker does not itself independently re-verify -- see module docstring.
    """
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def _validate_admission(
    run: Mapping[str, Any], plan: Mapping[str, Any],
    ext6: Mapping[str, Any], known: Mapping[str, str],
    runner_schema: Draft202012Validator,
) -> None:
    admission = run["runner_admission"]
    errors = sorted(runner_schema.iter_errors(admission), key=lambda item: tuple(item.path))
    if errors:
        raise base.PilotPlanError(f"runner admission schema: {errors[0].message}")
    evidence = admission["evidence"]
    if ({item["kind"] for item in evidence} != base.ADMISSION_KINDS
            or len({item["binding_id"] for item in evidence}) != 1
            or admission["binding_id"] != evidence[0]["binding_id"]):
        raise base.PilotPlanError("runner evidence family/binding is incomplete")
    special = {
        "SOURCE_RELEASE": ext6["release_artifact_sha256"],
        "RUN_PLAN": plan["plan_core_sha256"],
        "WARMUP_SCHEDULE": run["warmup_schedule_sha256"],
        "MEASUREMENT_SCHEDULE": run["schedule_sha256"],
        "SEED_DERIVATION": base.seed_derivation_hash(run),
    }
    for item in evidence:
        expected = special.get(item["kind"], known.get(item["artifact_id"]))
        if expected is None or item["sha256"] != expected:
            raise base.PilotPlanError("runner evidence is self-selected or unadmitted")
    expected_consumer = (plan["topology_evidence"][
        "near_consumer_cpu" if run["placement"] == "NEAR" else "far_consumer_cpu"
    ])
    if (admission["protocol_version"] != base.PROTOCOL_VERSION
            or admission["stand_id"] != plan["stand_id"]
            or admission["source_revision"] != ext6["source_revision"]
            or admission["binary_sha256"] != ext6["release_artifact_sha256"]
            or admission["package"] != run["package"]
            or admission["placement"] != run["placement"]
            or admission["producer_cpu"] != plan["topology_evidence"]["producer_cpu"]
            or admission["consumer_cpu"] != expected_consumer
            or run["runner_admission_sha256"]
            != base.sha256(canonical_no_newline(admission))
            or run["runner_evidence_set_sha256"]
            != base.sha256(canonical_no_newline(evidence))):
        raise base.PilotPlanError("runner admission/release/topology lineage drifted")


base._validate_admission = _validate_admission
