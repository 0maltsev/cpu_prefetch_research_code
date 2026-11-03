#!/usr/bin/env python3
"""Pure budget checks; synthetic extents supply no hardware measurements."""
import copy
import dataclasses
import pathlib
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_storage_budget_v1 as budget
from stage17_formal_ring_plan_v1 import FamilyBudget


class StorageBudgetTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(schema_version=budget.VERSION, program_id="future-formal-program",
            policy_id=budget.POLICY, implementation_profile_sha256="a" * 64, program_scope_sha256="b" * 64,
            archive_quota_bytes=6_000_000_000_000, workspace_bytes=512 * 1024**3,
            analysis_scratch_bytes=256 * 1024**3, disk_reserve_bytes=16 * 1024**3,
            codec_address_space_bytes=2 * 1024**3, codec_processes=1, broker_address_space_bytes=1024**3,
            per_capture_archive_ns=100, archive_staging_bytes=10000,
            capture_workspace_overhead_bytes=4096, checkpoint_bytes=1000,
            analysis_capture_workspace_bytes=100000)
        self.captures = [SimpleNamespace(max_output_bytes=100000, metadata_output_bytes=1000)] * 708
        self.family = FamilyBudget(1, 1, 100000, 1000, 4 * 1024**3, 1000,
            70_801_000, 256 * 1024**3, 16 * 1024**3, 6_841_813_590_016)

    def validate(self, **kwargs):
        return budget.validate_storage_plan(self.plan, self.captures, self.family,
            native_family_watchdog_ns=1000, native_family_memory_bytes=100000,
            logical_output_bound_bytes=70_801_000, **kwargs)

    def test_exact_policy_arithmetic_and_no_completion_guarantee(self):
        result = self.validate()
        self.assertEqual(result.required_initial_free_bytes, 6_841_813_590_016)
        self.assertEqual(result.peak_capture_workspace_bytes, 114096)
        self.assertEqual(result.minimum_family_watchdog_ns, 71800)
        self.assertEqual(result.minimum_family_memory_bytes, 3_221_325_472)
        self.assertEqual(result.logical_output_bound_bytes, 70_801_000)
        self.assertFalse(result.completion_guaranteed)
        self.assertFalse(result.execution_authority)

    def test_approved_constants_cannot_be_lowered_or_multiplied(self):
        original = copy.deepcopy(self.plan)
        for name in ("archive_quota_bytes", "workspace_bytes", "analysis_scratch_bytes",
                     "disk_reserve_bytes", "codec_address_space_bytes", "codec_processes"):
            for delta in (-1, 1):
                with self.subTest(name=name, delta=delta):
                    self.plan = copy.deepcopy(original)
                    self.plan[name] += delta
                    with self.assertRaises(budget.ContractError): self.validate()

    def test_workspace_includes_original_staging_and_overhead(self):
        self.plan["archive_staging_bytes"] = budget.WORKSPACE - 100000 - 4096
        self.validate()
        self.plan["archive_staging_bytes"] += 1
        with self.assertRaisesRegex(budget.ContractError, "workspace"): self.validate()

    def test_missing_cold_time_memory_or_logical_output_rejected(self):
        original = self.family
        for field, value in (("watchdog_ns", 71799), ("memory_bytes", 3_221_325_471),
                             ("max_output_bytes", 70_800_999),
                             ("required_free_disk_bytes", 6_841_813_590_015)):
            with self.subTest(field=field):
                self.family = dataclasses.replace(original, **{field: value})
                with self.assertRaises(budget.ContractError): self.validate()

    def test_checkpoint_and_one_capture_spool_must_fit(self):
        for key, value in (("checkpoint_bytes", 1001),
                           ("analysis_capture_workspace_bytes", 99999),
                           ("analysis_capture_workspace_bytes", budget.SCRATCH + 1)):
            original = copy.deepcopy(self.plan)
            with self.subTest(key=key, value=value):
                self.plan[key] = value
                with self.assertRaises(budget.ContractError): self.validate()
            self.plan = original

    def test_malformed_and_unbounded_inputs_rejected(self):
        for key, value in (("codec_processes", True), ("per_capture_archive_ns", 0),
                           ("per_capture_archive_ns", 1 << 63),
                           ("archive_staging_bytes", 6_000_000_000_001),
                           ("implementation_profile_sha256", "bad")):
            original = copy.deepcopy(self.plan)
            with self.subTest(key=key, value=value):
                self.plan[key] = value
                with self.assertRaises(budget.ContractError): self.validate()
            self.plan = original

    def test_remaining_quota_uses_program_usage_not_per_family_reset(self):
        self.assertEqual(budget.remaining_admission_bytes(retained_program_bytes=0),
                         6_841_813_590_016)
        self.assertEqual(budget.remaining_admission_bytes(retained_program_bytes=1_000_000_000_000),
                         5_841_813_590_016)
        self.assertEqual(budget.remaining_admission_bytes(retained_program_bytes=6_000_000_000_000),
                         841_813_590_016)
        for used in (-1, True, 6_000_000_000_001):
            with self.assertRaises(budget.ContractError):
                budget.remaining_admission_bytes(retained_program_bytes=used)


if __name__ == "__main__":
    unittest.main()
