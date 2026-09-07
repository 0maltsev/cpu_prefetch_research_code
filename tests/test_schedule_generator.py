#!/usr/bin/env python3
"""Correctness tests for the offline ADR-0029 schedule generator."""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

import _pydecimal
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_schedule as schedule  # noqa: E402


SEED = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
)


def make_spec(**changes: object) -> schedule.ScheduleSpec:
    values: dict[str, object] = {
        "schedule_id": "stage7-golden",
        "schedule_kind": "CONFIRMATORY",
        "namespace_id": "stage7-schedule-test",
        "parent_namespace_id": "stage-a-common",
        "seed_id": "stage7-test-seed",
        "derivation_record_id": "stage7-test-derivation",
        "master_seed": SEED,
        "origin_ticks": 0,
        "horizon_ticks": 10000,
        "numerator_events": 1,
        "denominator_ticks": 100,
        "artifact_id": "stage7-golden-artifact",
        "artifact_uri": "stage7-golden.bin",
    }
    values.update(changes)
    return schedule.ScheduleSpec(**values)


class ScheduleGeneratorTests(unittest.TestCase):
    def test_accepted_direct_and_integrated_goldens(self) -> None:
        raw = (0, 1, (1 << 63) - 1, 1 << 63, (1 << 64) - 2, (1 << 64) - 1)
        expected_offsets = (4505, 8901, 8970, 9039, 9039, 9039)
        self.assertEqual(
            schedule._transform_draws_for_test(raw, 1, 100), expected_offsets
        )
        self.assertEqual(
            schedule._transform_draws_for_test(raw, 1, 100, _pydecimal),
            expected_offsets,
        )

        spec = make_spec()
        key = schedule._derive_key(spec.master_seed, spec.namespace_id)
        self.assertEqual(key, (0x3F0BB803, 0x84B3F51C))
        self.assertEqual(
            tuple(schedule._philox_draw(key, index) for index in range(4)),
            (
                0x97A43571A6326B9A,
                0x56C3C6FDD95D24B5,
                0x6C6F5FB1B58C9A53,
                0xE5323DE41D1A3F26,
            ),
        )
        generated = schedule.generate_schedule(spec)
        reference = schedule._generate_deadlines(
            spec,
            lambda ordinal: schedule._philox_draw(key, ordinal),
            _pydecimal,
        )
        self.assertEqual(generated.deadlines, reference)
        self.assertEqual(len(generated.deadlines), 104)
        self.assertEqual(
            generated.deadlines[:12],
            (52, 160, 246, 257, 296, 365, 413, 570, 688, 872, 963, 1059),
        )
        self.assertEqual(
            generated.deadlines[-12:],
            (8963, 9091, 9164, 9299, 9471, 9495, 9605, 9656, 9835, 9868, 9902, 9998),
        )
        self.assertEqual(
            generated.artifact_sha256,
            "18f1da603f3d4383bb08410ffb0e41a8c4df336871765e633b4f116f1b22e81c",
        )
        self.assertEqual(
            generated.decoded_deadlines_sha256,
            "a07a349e5e95ff170036ffb21361d4d85dc9073177de7687c263ff254517a441",
        )
        self.assertEqual(
            generated.schedule_sha256,
            "df42859564d5075cca591b663e9db8a34da1e8a6ee4d81983d797db2bc6944f9",
        )

    def test_same_input_reproduces_all_bytes(self) -> None:
        first = schedule.generate_schedule(make_spec())
        second = schedule.generate_schedule(make_spec())
        self.assertEqual(first, second)

    def test_envelope_validates_and_canonical_round_trip_is_lossless(self) -> None:
        generated = schedule.generate_schedule(make_spec())
        envelope = json.loads(generated.envelope_bytes)
        schema = json.loads(
            (
                ROOT
                / "protocol/2.0.0-pre.2/handoff/schemas/schedule.schema.json"
            ).read_text(encoding="utf-8")
        )
        Draft202012Validator(schema).validate(envelope)
        derivation = json.loads(generated.derivation_record_bytes)
        derivation_schema = json.loads(
            (ROOT / "config/schemas/schedule-derivation-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(derivation_schema).validate(derivation)
        self.assertEqual(envelope["rng"]["algorithm"], schedule.SCHEDULE_ALGORITHM)
        self.assertEqual(envelope["rng"]["version"], schedule.SCHEDULE_VERSION)
        self.assertEqual(envelope["time_unit"], "ps")
        self.assertEqual(envelope["deadline_encoding"], "ABSOLUTE_INTEGER_TICKS")
        self.assertEqual(envelope["offered_count"], 104)
        self.assertEqual(
            envelope["rng"]["derivation_record_id"], derivation["record_id"]
        )
        self.assertEqual(derivation["seed_id"], envelope["rng"]["seed_id"])
        self.assertEqual(
            derivation["parent_namespace_id"],
            envelope["rng"]["parent_namespace_id"],
        )
        self.assertEqual(derivation["namespace_id"], envelope["namespace_id"])
        self.assertEqual(derivation["derived_key_u32be_hex"], "3f0bb80384b3f51c")
        zeroed = dict(derivation)
        zeroed["record_sha256"] = "0" * 64
        self.assertEqual(
            hashlib.sha256(schedule.canonicalize(zeroed).encode()).hexdigest(),
            derivation["record_sha256"],
        )
        self.assertEqual(
            schedule.canonicalize(json.loads(schedule.canonicalize(envelope))),
            schedule.canonicalize(envelope),
        )

    def test_empty_minimal_and_deadline_at_horizon_exclusion(self) -> None:
        minimal = schedule.generate_schedule(make_spec(horizon_ticks=1))
        self.assertEqual(minimal.deadlines, ())
        self.assertEqual(minimal.artifact_bytes, b"")
        at_first_deadline = schedule.generate_schedule(make_spec(horizon_ticks=52))
        self.assertEqual(at_first_deadline.deadlines, ())
        after_first_deadline = schedule.generate_schedule(make_spec(horizon_ticks=53))
        self.assertEqual(after_first_deadline.deadlines, (52,))
        shifted = schedule.generate_schedule(
            make_spec(origin_ticks=100, horizon_ticks=53)
        )
        self.assertEqual(shifted.deadlines, (152,))

    def test_exact_rate_and_overflow_fail_closed(self) -> None:
        for changes, category in (
            ({"numerator_events": 0}, "RATE_INVALID"),
            ({"denominator_ticks": 0}, "RATE_INVALID"),
            (
                {"numerator_events": 2, "denominator_ticks": 200},
                "RATE_NONCANONICAL",
            ),
            (
                {"origin_ticks": schedule.UINT64_MAX, "horizon_ticks": 1},
                "HORIZON_OVERFLOW",
            ),
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(schedule.ScheduleGenerationError) as raised:
                    schedule.generate_schedule(make_spec(**changes))
                self.assertEqual(raised.exception.category, category)

        with self.assertRaises(schedule.ScheduleGenerationError) as exhausted:
            schedule._generate_deadlines(
                make_spec(), lambda _: 0, max_draw_ordinal=0
            )
        self.assertEqual(exhausted.exception.category, "DRAW_EXHAUSTION")

    def test_small_configuration_matrix_preserves_order_and_horizon(self) -> None:
        for namespace in ("warmup-test", "pilot-test", "confirmatory-test"):
            for numerator, denominator in ((1, 1), (1, 10), (3, 10)):
                for origin, horizon in ((0, 1), (0, 100), (1000, 100)):
                    with self.subTest(
                        namespace=namespace,
                        rate=(numerator, denominator),
                        origin=origin,
                        horizon=horizon,
                    ):
                        generated = schedule.generate_schedule(
                            make_spec(
                                namespace_id=namespace,
                                origin_ticks=origin,
                                horizon_ticks=horizon,
                                numerator_events=numerator,
                                denominator_ticks=denominator,
                            )
                        )
                        self.assertEqual(
                            tuple(sorted(generated.deadlines)), generated.deadlines
                        )
                        self.assertTrue(
                            all(
                                origin <= deadline < origin + horizon
                                for deadline in generated.deadlines
                            )
                        )

    def test_publication_is_append_only_and_rolls_back_partial_pair(self) -> None:
        generated = schedule.generate_schedule(make_spec())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "schedule.bin"
            envelope = root / "schedule.json"
            derivation = root / "derivation.json"
            schedule.publish_schedule(generated, artifact, envelope, derivation)
            self.assertEqual(artifact.read_bytes(), generated.artifact_bytes)
            self.assertEqual(envelope.read_bytes(), generated.envelope_bytes)
            self.assertEqual(
                derivation.read_bytes(), generated.derivation_record_bytes
            )
            with self.assertRaises(schedule.ScheduleGenerationError) as raised:
                schedule.publish_schedule(
                    generated,
                    artifact,
                    root / "other.json",
                    root / "other-derivation.json",
                )
            self.assertEqual(raised.exception.category, "PUBLICATION_FAILURE")
            self.assertFalse((root / "other.json").exists())
            self.assertFalse((root / "other-derivation.json").exists())
            self.assertEqual(artifact.read_bytes(), generated.artifact_bytes)

    def test_generation_api_has_no_queue_completion_or_outcome_input(self) -> None:
        self.assertEqual(
            tuple(inspect.signature(schedule.generate_schedule).parameters), ("spec",)
        )
        self.assertNotIn(
            "outcome", {field.name for field in dataclasses.fields(schedule.ScheduleSpec)}
        )
        queue_outcomes = ["FULL", "ACCEPTED"]
        before = schedule.generate_schedule(make_spec())
        queue_outcomes.reverse()
        after = schedule.generate_schedule(make_spec())
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
