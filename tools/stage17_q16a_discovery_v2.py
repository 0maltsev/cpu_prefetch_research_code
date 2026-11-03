"""ADR-0207 versioned design and selector for already-verified diagnostic observations.

This module performs no capture, file admission, signing, or hardware access.
Its result cannot authorize execution or contribute formal calibration data.
"""

from __future__ import annotations

import argparse
import json
from typing import Sequence


# Reuse observation value types: the independent raw validator also returns
# these types. Only the prospective grid/selection policy is versioned here.
from stage17_q16a_discovery_v1 import (
    CONTEXTS, MINIMUM_OBSERVATIONS_PER_SEQUENCE, CaptureKey, DiagnosticCapture,
    DurationSelection, ObservationCounts, SelectionState, StopReason,
)

DESIGN_ID = "D207-Q16A-SETUP-DISCOVERY-v2"
DURATIONS_NS = (1_000_000_000, 2_000_000_000, 5_000_000_000)


def required_captures() -> tuple[CaptureKey, ...]:
    return tuple(CaptureKey(context, duration)
                 for context in range(len(CONTEXTS)) for duration in DURATIONS_NS)


def select_duration(captures: Sequence[DiagnosticCapture]) -> DurationSelection:
    planned = required_captures()
    if len(captures) > len(planned):
        raise ValueError("discovery contains extra captures or a hidden retry")
    for ordinal, capture in enumerate(captures):
        if (type(capture.key.context_ordinal) is not int
                or type(capture.key.duration_ns) is not int
                or capture.key != planned[ordinal]):
            raise ValueError("discovery is not the exact ordered prospective prefix")
        if not isinstance(capture.stop_reason, StopReason):
            raise ValueError("unknown discovery stop reason")
        if any(type(count) is not int or count < 0 for count in capture.counts.values()):
            raise ValueError("observation counts must be nonnegative integers")
        if (capture.counts.producer_issue >= max(1, capture.counts.producer_demand)
                or capture.counts.consumer_issue >= max(1, capture.counts.consumer_demand)):
            raise ValueError("issue intervals exceed the possible advancing demands")
        if capture.elapsed_ns is not None and (
                type(capture.elapsed_ns) is not int or capture.elapsed_ns < 0):
            raise ValueError("elapsed time must be an observed nonnegative integer or absent")
        if not isinstance(capture.validity_failures, tuple) or any(
                not isinstance(failure, str) or not failure
                for failure in capture.validity_failures):
            raise ValueError("validity failures must be explicit nonempty reason strings")
        mandatory_failure = (capture.stop_reason == StopReason.mandatory_failure
                             or bool(capture.validity_failures))
        if mandatory_failure:
            if ordinal != len(captures) - 1:
                raise ValueError("discovery continued after a mandatory failure")
            return DurationSelection(SelectionState.stopped, None, (), len(captures))
        if capture.elapsed_ns is None:
            raise ValueError("a capture without a mandatory clock failure must retain elapsed time")
        if (capture.stop_reason == StopReason.fixed_deadline
                and capture.elapsed_ns < capture.key.duration_ns):
            raise ValueError("fixed-deadline evidence stops before its declared horizon")
    if len(captures) != len(planned):
        return DurationSelection(SelectionState.incomplete, None, (), len(captures))
    eligible = tuple(duration for duration in DURATIONS_NS if all(
        capture.stop_reason == StopReason.fixed_deadline
        and capture.elapsed_ns is not None
        and capture.elapsed_ns >= duration
        and all(count >= MINIMUM_OBSERVATIONS_PER_SEQUENCE
                for count in capture.counts.values())
        for capture in captures if capture.key.duration_ns == duration
    ))
    return DurationSelection(
        SelectionState.selected if eligible else SelectionState.unresolved,
        min(eligible) if eligible else None, eligible, len(captures),
    )


def describe_design() -> dict[str, object]:
    return {
        "design_id": DESIGN_ID,
        "decision_id": "D-207",
        "diagnostic_only": True,
        "execution_authority": False,
        "formal_runs_contributed": 0,
        "minimum_observations_per_sequence": MINIMUM_OBSERVATIONS_PER_SEQUENCE,
        "capture_count": len(required_captures()),
        "captures": [
            {"ordinal": ordinal, "context_ordinal": capture.context_ordinal,
             "hardware_state": CONTEXTS[capture.context_ordinal][0],
             "placement": CONTEXTS[capture.context_ordinal][1],
             "working_set_class": CONTEXTS[capture.context_ordinal][2],
             "duration_ns": capture.duration_ns}
            for ordinal, capture in enumerate(required_captures())
        ],
        "operational_plan_complete": False,
        "required_before_execution": [
            "verified capture implementation and preparation",
            "qualified clean release",
            "exact namespace, run IDs, seeds, and predecessor hashes",
            "finite memory, storage, watchdog, and stand budgets",
            "exact signed diagnostic action authority",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe-design", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(describe_design(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
