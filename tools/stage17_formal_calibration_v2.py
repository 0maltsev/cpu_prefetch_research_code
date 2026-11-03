"""D239 archive-plan admission with unchanged D230 arithmetic and report format.

Only the prospective plan validator is rebound, in private function globals.
Original /2 plan bytes are never projected, relabelled or rehashed as /1.
This module authenticates neither custody nor scientific-report provenance.
"""
from __future__ import annotations

import types

import stage17_formal_calibration_v1 as previous
import stage17_formal_plan_v2 as plans
import stage17_formal_archive_v1 as archive

SCHEMA_ID = previous.SCHEMA_ID
FAILURE_SCHEMA_ID = previous.FAILURE_SCHEMA_ID
METHOD = previous.METHOD
CalibrationError = previous.CalibrationError
validate_calibration_record = previous.validate_calibration_record

_plan_namespace = types.SimpleNamespace(**{
    **vars(previous.plans), "validate_plan": plans.validate_plan,
})
_evaluate = types.FunctionType(previous.evaluate.__code__,
    {**previous.evaluate.__globals__, "plans": _plan_namespace},
    name="_archive_aware_evaluate", argdefs=previous.evaluate.__defaults__)
_evaluate.__kwdefaults__ = previous.evaluate.__kwdefaults__
_archived_evaluate = types.FunctionType(previous.evaluate.__code__,
    {**_evaluate.__globals__, "canonical": archive.canonical},
    name="_native_archive_plan_evaluate", argdefs=previous.evaluate.__defaults__)
_archived_evaluate.__kwdefaults__ = previous.evaluate.__kwdefaults__


def plan_bytes(plan):
    """Native /2 plan identity excludes LF; legacy transport stays unchanged."""
    if isinstance(plan, dict) and plan.get("schema_version") in plans.VERSION.values():
        return archive.canonical(plan)
    return previous.canonical(plan)


def evaluate(action, plan, run_records, ring_geometry=None):
    """Validate original /1 or /2 plan, then apply the exact existing estimator."""
    evaluator = (_archived_evaluate if isinstance(plan, dict)
                 and plan.get("schema_version") in plans.VERSION.values() else _evaluate)
    return evaluator(action, plan, run_records, ring_geometry)
