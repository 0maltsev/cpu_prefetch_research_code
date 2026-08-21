#!/usr/bin/env python3
"""Synthetic-only conformance tests for accepted Stage 13 statistics."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import calibration_statistics as calibration  # noqa: E402


SHA256 = "a" * 64


def config(index: int = 0) -> calibration.MatrixConfig:
    scale = calibration.ACCEPTED_LADDER[index]
    return calibration.MatrixConfig(
        estimator_id=calibration.MATRIX_METHOD_ID,
        arithmetic_profile_id=calibration.ARITHMETIC_PROFILE_ID,
        assumptions=(
            "independent run clusters",
            "common marginal FULL probability within each planned cell candidate",
        ),
        owner_ids=("synthetic-calibration-owner", "synthetic-statistical-owner"),
        authority_artifact_id="synthetic-authority",
        authority_sha256=SHA256,
        stand_budget_artifact_id="synthetic-stand-budget",
        stand_budget_sha256=SHA256,
        confidence_numerator=19,
        confidence_denominator=20,
        acceptance_threshold_numerator=19,
        acceptance_threshold_denominator=20,
        family_cell_count=180,
        family_candidate_count=5,
        planned_blocks=1,
        planned_runs=180,
        global_scale_numerator=scale.numerator,
        global_scale_denominator=scale.denominator,
        candidate_index=index,
    )


def cells(phase: str = "CALIBRATION") -> tuple[calibration.CellProbe, ...]:
    return tuple(
        calibration.CellProbe(
            cell_id=f"cell-{index:03d}",
            namespace_id="synthetic-feasibility-g1",
            schedule_id=f"synthetic-schedule-{index:03d}",
            schedule_sha256=SHA256,
            runs=(
                calibration.ClusterRun(
                    run_id=f"probe-{index:03d}",
                    offered_count=100,
                    full_count=0,
                    source_artifact_id=f"raw-{index:03d}",
                    source_sha256=SHA256,
                    integrity_artifact_id=f"integrity-{index:03d}",
                    integrity_sha256=SHA256,
                    failure_artifact_id=None,
                    failure_sha256=None,
                    validity="VALID",
                    evidence_phase=phase,
                ),
            ),
            planned_run_ids=(f"probe-{index:03d}",),
            planned_confirmatory_runs=1,
            scheduled_events_per_run=1,
        )
        for index in range(180)
    )


class ArithmeticProfileTests(unittest.TestCase):
    def test_direct_and_higher_precision_golden_vectors(self) -> None:
        vectors = (
            (
                tuple((100, 0) for _ in range(59)),
                Fraction(0, 1),
                Fraction(1, 59),
                "0.28815789923026432163018722476748269615937832924530077553557855216276822866253863",
            ),
            (
                tuple((100, 1 if index == 0 else 0) for index in range(59)),
                Fraction(1, 5900),
                Fraction(1, 59),
                "0.28832739075568805044374654680138100124412409195716518231523956911192077103541998",
            ),
            (
                tuple((100 if index < 58 else 200, 0) for index in range(59)),
                Fraction(0, 1),
                Fraction(31, 1800),
                "0.29046989619466753217139324131062660450085282350529164009676542616982060085550397",
            ),
        )
        for counts, expected_hat, expected_weight_sum, expected_upper in vectors:
            with self.subTest(expected_upper=expected_upper):
                p_hat, weight_sum, upper = calibration.p_upper(counts)
                reference = calibration.p_upper_reference(counts)
                self.assertEqual(p_hat, expected_hat)
                self.assertEqual(weight_sum, expected_weight_sum)
                self.assertEqual(calibration.decimal_text(upper), expected_upper)
                self.assertEqual(calibration.decimal_text(reference), expected_upper)
                self.assertGreaterEqual(upper, reference)

    def test_all_zero_is_positive_and_full_clamps_to_one(self) -> None:
        self.assertGreater(
            calibration.p_upper(tuple((100, 0) for _ in range(59)))[2],
            Decimal(0),
        )
        self.assertEqual(
            calibration.p_upper(tuple((100, 100) for _ in range(59)))[2],
            Decimal(1),
        )

    def test_zero_offered_and_invalid_counts_fail_closed(self) -> None:
        with self.assertRaises(calibration.CalibrationError) as zero:
            calibration.p_upper(((0, 0),))
        self.assertEqual(zero.exception.category, "ZERO_OFFERED_RUN")
        with self.assertRaises(calibration.CalibrationError) as mismatch:
            calibration.p_upper(((1, 2),))
        self.assertEqual(mismatch.exception.category, "COUNT_MISMATCH")


class MatrixFeasibilityTests(unittest.TestCase):
    def test_complete_matrix_accounts_for_simultaneous_exposure(self) -> None:
        result = calibration.evaluate_matrix(config(), cells())
        self.assertEqual(len(result.cell_bounds), 180)
        self.assertEqual(result.planned_blocks, 1)
        self.assertEqual(result.planned_runs, 180)
        self.assertEqual(result.planned_offered_events, 180)
        self.assertEqual(result.matrix_probability_lower, Decimal(0))
        self.assertFalse(result.passes)
        self.assertTrue(all(bound.p_upper > 0 for bound in result.cell_bounds))

    def test_incomplete_matrix_and_confirmatory_access_are_forbidden(self) -> None:
        with self.assertRaises(calibration.CalibrationError) as incomplete:
            calibration.evaluate_matrix(config(), cells()[:-1])
        self.assertEqual(incomplete.exception.category, "INCOMPLETE_MATRIX")
        with self.assertRaises(calibration.CalibrationError) as forbidden:
            calibration.evaluate_matrix(config(), cells("CONFIRMATORY"))
        self.assertEqual(forbidden.exception.category, "FORBIDDEN_OUTCOME_ACCESS")

        invalid_cells = list(cells())
        invalid_run = replace(
            invalid_cells[0].runs[0],
            validity="INVALID",
            source_artifact_id=None,
            source_sha256=None,
            integrity_artifact_id=None,
            integrity_sha256=None,
            failure_artifact_id="probe-failure",
            failure_sha256=SHA256,
        )
        invalid_cells[0] = replace(invalid_cells[0], runs=(invalid_run,))
        with self.assertRaises(calibration.CalibrationError) as invalid:
            calibration.evaluate_matrix(config(), invalid_cells)
        self.assertEqual(invalid.exception.category, "INCOMPLETE_ESTIMATOR")

        unplanned_cells = list(cells())
        unplanned_cells[0] = replace(
            unplanned_cells[0], planned_run_ids=("different-prospective-run",)
        )
        with self.assertRaises(calibration.CalibrationError) as unplanned:
            calibration.evaluate_matrix(config(), unplanned_cells)
        self.assertEqual(unplanned.exception.category, "INCOMPLETE_PROBE_PLAN")

    def test_configurable_fields_are_mandatory_but_must_match_accepted_suite(self) -> None:
        wrong = replace(
            config(),
            acceptance_threshold_numerator=9,
            acceptance_threshold_denominator=10,
        )
        with self.assertRaises(calibration.CalibrationError) as rejected:
            calibration.evaluate_matrix(wrong, cells())
        self.assertEqual(rejected.exception.category, "THRESHOLD_MISMATCH")

    def test_first_passing_global_scale_is_treatment_blind(self) -> None:
        def result(
            namespace: str, index: int, lower: str, passes: bool
        ) -> calibration.MatrixResult:
            return calibration.MatrixResult(
                (),
                namespace,
                index,
                calibration.ACCEPTED_LADDER[index],
                1,
                180,
                180,
                Decimal(lower),
                passes,
            )

        selected = calibration.select_first_passing_global_scale(
            (
                result("g1", 0, "0.9", False),
                result("g09", 1, "0.9", False),
                result("g08", 2, "0.96", True),
            )
        )
        self.assertEqual(selected, Fraction(4, 5))
        with self.assertRaises(calibration.CalibrationError):
            calibration.select_first_passing_global_scale(
                (
                    result("g1", 0, "0.9", False),
                    result("g09", 1, "0.9", False),
                )
            )
        self.assertIsNone(
            calibration.select_first_passing_global_scale(
                tuple(
                    result(f"g{index}", index, "0.9", False)
                    for index in range(len(calibration.ACCEPTED_LADDER))
                )
            )
        )
        wrong_binding = [
            result(f"g{index}", index, "0.9", False)
            for index in range(len(calibration.ACCEPTED_LADDER))
        ]
        wrong_binding[0] = replace(wrong_binding[0], global_scale=Fraction(9, 10))
        with self.assertRaises(calibration.CalibrationError):
            calibration.select_first_passing_global_scale(wrong_binding)

        with self.assertRaises(calibration.CalibrationError) as after_stop:
            calibration.select_first_passing_global_scale(
                (
                    result("g1", 0, "0.96", True),
                    result("g09", 1, "0.96", True),
                )
            )
        self.assertEqual(after_stop.exception.category, "OUTCOME_AFTER_STOP")


class CalibrationRecordTests(unittest.TestCase):
    def test_canonical_sealing_round_trip_and_append_only_publication(self) -> None:
        record = {
            "schema_version": "cpu-prefetch-calibration-freeze/1",
            "protocol_version": calibration.PROTOCOL_VERSION,
            "record_id": "synthetic-not-evaluated-freeze",
            "state": "NOT_EVALUATED",
            "source_records": [{"artifact_id": "synthetic-plan", "sha256": SHA256}],
            "invalidation_fingerprint_sha256": SHA256,
            "proposed_outputs": [],
            "unresolved_inputs": ["stand calibration evidence"],
            "supersedes_record_id": None,
        }
        sealed, encoded = calibration.seal_record(record)
        self.assertEqual(json.loads(encoded), sealed)
        zeroed = dict(sealed)
        zeroed["record_sha256"] = "0" * 64
        import hashlib

        self.assertEqual(
            hashlib.sha256(calibration.canonicalize(zeroed)).hexdigest(),
            sealed["record_sha256"],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            destination = calibration.publish_append_only(
                path, sealed["record_id"], encoded
            )
            self.assertEqual(destination.read_bytes(), encoded)
            with self.assertRaises(calibration.CalibrationError) as overwrite:
                calibration.publish_append_only(path, sealed["record_id"], encoded)
            self.assertEqual(overwrite.exception.category, "ATTEMPTED_OVERWRITE")

    def test_canonicalization_forbids_floating_point(self) -> None:
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize({"forbidden": 0.5})
        self.assertEqual(
            calibration.canonicalize({"unsigned": (1 << 64) - 1}),
            b'{"unsigned":18446744073709551615}',
        )
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize({"overflow": 1 << 64})
        with self.assertRaises(calibration.CalibrationError):
            calibration.canonicalize({"surrogate": "\ud800"})

    def test_canonicalization_uses_utf16_key_order(self) -> None:
        self.assertEqual(
            calibration.canonicalize({"\ue000": 1, "\U00010000": 2}),
            '{"\U00010000":2,"\ue000":1}'.encode(),
        )

    def test_material_change_invalidates_dependent_freeze(self) -> None:
        identity = {
            "platform": "synthetic-platform",
            "build": "synthetic-build-a",
            "queue": "ring-spsc-v1",
            "memory_order": "RING-SPSC-RA-v1",
            "consumer_action": "consumer-action-v1",
            "clock": "fake-clock-v1",
            "capacity": 1024,
        }
        fingerprint = calibration.invalidation_fingerprint(identity)
        self.assertTrue(calibration.freeze_remains_applicable(fingerprint, identity))
        changed = dict(identity)
        changed["build"] = "synthetic-build-b"
        self.assertFalse(
            calibration.freeze_remains_applicable(fingerprint, changed)
        )


if __name__ == "__main__":
    unittest.main()
