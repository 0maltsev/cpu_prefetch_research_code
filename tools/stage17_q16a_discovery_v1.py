"""ADR-0178 design and selector for already-verified diagnostic observations.

This module performs no capture, file admission, signing, or hardware access.
Its result cannot authorize execution or contribute formal calibration data.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


DESIGN_ID = "D178-Q16A-SETUP-DISCOVERY-v1"
DURATIONS_NS = (100_000_000, 1_000_000_000, 5_000_000_000)
MINIMUM_OBSERVATIONS_PER_SEQUENCE = 100_000
CONTEXTS = tuple(
    (hardware_state, placement, working_set)
    for hardware_state in ("H0", "H1")
    for placement in ("NEAR", "FAR")
    for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC")
)


class StopReason(str, Enum):
    fixed_deadline = "FIXED_DEADLINE"
    trace_capacity = "TRACE_CAPACITY"
    mandatory_failure = "MANDATORY_FAILURE"


class SelectionState(str, Enum):
    incomplete = "INCOMPLETE"
    stopped = "STOPPED_MANDATORY_FAILURE"
    unresolved = "UNRESOLVED"
    selected = "SELECTED_FOR_PROSPECTIVE_FORMAL_PLAN"


@dataclass(frozen=True)
class CaptureKey:
    context_ordinal: int
    duration_ns: int


def required_captures() -> tuple[CaptureKey, ...]:
    return tuple(CaptureKey(context, duration)
                 for context in range(len(CONTEXTS)) for duration in DURATIONS_NS)


@dataclass(frozen=True)
class ObservationCounts:
    producer_demand: int
    consumer_demand: int
    producer_issue: int
    consumer_issue: int

    def values(self) -> tuple[int, ...]:
        return (self.producer_demand, self.consumer_demand,
                self.producer_issue, self.consumer_issue)


@dataclass(frozen=True)
class DiagnosticCapture:
    key: CaptureKey
    elapsed_ns: int | None
    counts: ObservationCounts
    stop_reason: StopReason
    validity_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class DurationSelection:
    state: SelectionState
    selected_duration_ns: int | None
    eligible_durations_ns: tuple[int, ...]
    present_captures: int
    diagnostic_only: bool = True
    formal_runs_contributed: int = 0
    execution_authority: bool = False


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
        "decision_id": "D-178",
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
