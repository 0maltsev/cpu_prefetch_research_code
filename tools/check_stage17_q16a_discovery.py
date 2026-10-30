"""Synthetic checks of the accepted discovery design; no measurements."""

from __future__ import annotations

import dataclasses
import unittest

import stage17_q16a_discovery_v1 as discovery


def complete_captures() -> list[discovery.DiagnosticCapture]:
    return [discovery.DiagnosticCapture(
        key, key.duration_ns,
        discovery.ObservationCounts(100_001, 100_001, 100_000, 100_000),
        discovery.StopReason.fixed_deadline,
    ) for key in discovery.required_captures()]


class DiscoveryTests(unittest.TestCase):
    def test_design_is_exactly_twelve_contexts_and_three_durations(self):
        plan = discovery.describe_design()
        self.assertEqual(plan["capture_count"], 36)
        self.assertEqual(len(set(discovery.CONTEXTS)), 12)
        self.assertEqual(discovery.DURATIONS_NS, (100_000_000, 1_000_000_000, 5_000_000_000))
        self.assertFalse(plan["execution_authority"])
        self.assertFalse(plan["operational_plan_complete"])

    def test_shortest_common_qualifying_duration_is_selected(self):
        captures = complete_captures()
        captures[0] = dataclasses.replace(captures[0], counts=discovery.ObservationCounts(10, 10, 9, 9))
        result = discovery.select_duration(captures)
        self.assertEqual(result.selected_duration_ns, 1_000_000_000)
        self.assertEqual(result.eligible_durations_ns, (1_000_000_000, 5_000_000_000))

    def test_every_context_must_pass(self):
        captures = complete_captures()
        for ordinal in (33, 34):
            captures[ordinal] = dataclasses.replace(captures[ordinal], counts=discovery.ObservationCounts(1, 1, 0, 0))
        self.assertEqual(discovery.select_duration(captures).selected_duration_ns, 5_000_000_000)

    def test_no_candidate_qualifies(self):
        captures = [dataclasses.replace(capture, counts=discovery.ObservationCounts(100_000, 100_000, 99_999, 99_999))
                    for capture in complete_captures()]
        result = discovery.select_duration(captures)
        self.assertEqual(result.state, discovery.SelectionState.unresolved)
        self.assertIsNone(result.selected_duration_ns)

    def test_all_four_counts_are_independent_requirements(self):
        for field in dataclasses.fields(discovery.ObservationCounts):
            captures = complete_captures()
            replacement = dataclasses.replace(captures[0].counts, **{field.name: 99_999})
            if field.name == "producer_demand":
                replacement = dataclasses.replace(replacement, producer_issue=99_998)
            if field.name == "consumer_demand":
                replacement = dataclasses.replace(replacement, consumer_issue=99_998)
            captures[0] = dataclasses.replace(captures[0], counts=replacement)
            self.assertEqual(discovery.select_duration(captures).selected_duration_ns, 1_000_000_000)

    def test_trace_capacity_cannot_substitute_for_fixed_time(self):
        captures = complete_captures()
        captures[0] = dataclasses.replace(captures[0], stop_reason=discovery.StopReason.trace_capacity)
        self.assertEqual(discovery.select_duration(captures).selected_duration_ns, 1_000_000_000)

    def test_early_stop_and_absent_clock_evidence_are_rejected(self):
        for elapsed in (None, 99_999_999):
            captures = complete_captures()
            captures[0] = dataclasses.replace(captures[0], elapsed_ns=elapsed)
            with self.assertRaises(ValueError):
                discovery.select_duration(captures)

    def test_partial_campaign_cannot_select_early(self):
        result = discovery.select_duration(complete_captures()[:-1])
        self.assertEqual(result.state, discovery.SelectionState.incomplete)
        self.assertIsNone(result.selected_duration_ns)
        self.assertEqual(discovery.select_duration([]).state, discovery.SelectionState.incomplete)

    def test_mandatory_failure_retains_prefix_and_stops(self):
        captures = complete_captures()[:2]
        captures[-1] = dataclasses.replace(captures[-1], elapsed_ns=None,
                                          stop_reason=discovery.StopReason.mandatory_failure)
        result = discovery.select_duration(captures)
        self.assertEqual(result.state, discovery.SelectionState.stopped)
        self.assertEqual(result.present_captures, 2)
        self.assertIsNone(result.selected_duration_ns)

    def test_continuing_after_failed_validity_gate_is_rejected(self):
        captures = complete_captures()
        captures[0] = dataclasses.replace(captures[0], validity_failures=("RESIDENCY_MISMATCH",))
        with self.assertRaises(ValueError):
            discovery.select_duration(captures)

    def test_duplicates_reordering_extra_and_unknown_captures_are_rejected(self):
        captures = complete_captures()
        malformed_families = (
            [captures[0], captures[0]], list(reversed(captures)), captures + [captures[0]],
            [dataclasses.replace(captures[0], key=discovery.CaptureKey(0, 123))],
            [dataclasses.replace(captures[0], key=discovery.CaptureKey(False, 100_000_000))],
            [dataclasses.replace(captures[0], key=discovery.CaptureKey(0, 100_000_000.0))],
        )
        for malformed in malformed_families:
            with self.assertRaises(ValueError):
                discovery.select_duration(malformed)

    def test_bool_negative_and_impossible_counts_are_rejected(self):
        for counts in (discovery.ObservationCounts(True, 1, 0, 0),
                       discovery.ObservationCounts(-1, 1, 0, 0),
                       discovery.ObservationCounts(100_000, 100_000, 100_000, 99_999)):
            capture = dataclasses.replace(complete_captures()[0], counts=counts)
            with self.assertRaises(ValueError):
                discovery.select_duration([capture])
        for elapsed in (True, -1):
            capture = dataclasses.replace(complete_captures()[0], elapsed_ns=elapsed)
            with self.assertRaises(ValueError):
                discovery.select_duration([capture])
        capture = dataclasses.replace(complete_captures()[0], stop_reason="FIXED_DEADLINE")
        with self.assertRaises(ValueError):
            discovery.select_duration([capture])

    def test_result_never_grants_authority_or_formal_credit(self):
        result = discovery.select_duration(complete_captures())
        self.assertEqual(result.selected_duration_ns, 100_000_000)
        self.assertTrue(result.diagnostic_only)
        self.assertFalse(result.execution_authority)
        self.assertEqual(result.formal_runs_contributed, 0)


if __name__ == "__main__":
    unittest.main()
