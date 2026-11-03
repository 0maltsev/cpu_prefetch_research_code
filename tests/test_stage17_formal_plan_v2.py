"""D233 complete-family storage contracts; no experimental execution."""
import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from jsonschema import Draft202012Validator
import stage17_formal_plan_v1 as previous
import stage17_formal_plan_v2 as current
import stage17_formal_storage_budget_v1 as storage
from test_stage17_formal_ring_plan_v1 import plan_fixture as ring_fixture
from test_stage17_formal_plan_v1 import plan_fixture as other_fixture


def archived_fixture(action):
    plan = ring_fixture() if action == "Q16a" else other_fixture(action)
    plan["schema_version"] = current.VERSION[action]
    plan["custody_policy_id"] = storage.POLICY
    plan["storage"] = dict(schema_version=storage.VERSION, program_id="shared-future-program",
        policy_id=storage.POLICY, implementation_profile_sha256="a" * 64, program_scope_sha256="b" * 64,
        archive_quota_bytes=storage.QUOTA, workspace_bytes=storage.WORKSPACE,
        analysis_scratch_bytes=storage.SCRATCH, disk_reserve_bytes=storage.RESERVE,
        codec_address_space_bytes=storage.CODEC_MEMORY, codec_processes=1, broker_address_space_bytes=1024**3,
        per_capture_archive_ns=1_000_000_000, archive_staging_bytes=100000,
        capture_workspace_overhead_bytes=4096, checkpoint_bytes=1000,
        analysis_capture_workspace_bytes=100000)
    family = plan["budget"]
    family["watchdog_ns"] += len(plan["captures"]) * 1_000_000_000
    family["memory_bytes"] += storage.CODEC_MEMORY + 1024**3
    family["analysis_scratch_bytes"] = storage.SCRATCH
    family["disk_reserve_bytes"] = storage.RESERVE
    family["required_free_disk_bytes"] = storage.QUOTA + storage.WORKSPACE + storage.SCRATCH + storage.RESERVE
    return plan


class FormalPlanStorageTests(unittest.TestCase):
    def test_all_three_full_families_schema_and_exact_logical_parity(self):
        for action in ("Q16a", "Q16b", "Q16c"):
            with self.subTest(action=action):
                original = ring_fixture() if action == "Q16a" else other_fixture(action)
                old = previous.validate_plan(action, original)
                document = archived_fixture(action)
                schema = json.loads((previous.ROOT / current.SCHEMA[action]).read_text())
                Draft202012Validator(schema).validate(document)
                result = current.validate_plan(action, document)
                self.assertEqual(result.captures, old.captures)
                self.assertEqual(result.maximum_output_bytes, old.maximum_output_bytes)
                self.assertEqual(result.required_watchdog_ns,
                                 old.required_watchdog_ns + len(old.captures) * 1_000_000_000)
                self.assertEqual(result.peak_memory_bytes, old.peak_memory_bytes + storage.CODEC_MEMORY + 1024**3)
                self.assertFalse(result.execution_authority)

    def test_old_contract_stays_strict_and_old_dispatch_is_identical(self):
        original = ring_fixture()
        self.assertEqual(current.validate_plan("Q16a", original),
                         previous.validate_plan("Q16a", original))
        with self.assertRaises(storage.ContractError):
            previous.validate_plan("Q16a", archived_fixture("Q16a"))
        original["custody_policy_id"] = storage.POLICY
        with self.assertRaises(storage.ContractError): current.validate_plan("Q16a", original)

    def test_no_capture_omission_or_logical_budget_reduction(self):
        for mutation in (lambda p: p["captures"].pop(),
                         lambda p: p["captures"][0]["execution_budget"].update(max_output_bytes=1),
                         lambda p: p["budget"].update(max_output_bytes=1)):
            document = archived_fixture("Q16a")
            mutation(document)
            with self.assertRaises(storage.ContractError): current.validate_plan("Q16a", document)

    def test_physical_ceiling_cannot_substitute_for_cold_time_or_memory(self):
        for field, value in (("watchdog_ns", 1), ("memory_bytes", 1),
                             ("required_free_disk_bytes", storage.QUOTA)):
            document = archived_fixture("Q16c")
            document["budget"][field] = value
            with self.assertRaises(storage.ContractError): current.validate_plan("Q16c", document)

    def test_storage_identity_is_required_and_no_unknown_version(self):
        document = archived_fixture("Q16c")
        del document["storage"]
        with self.assertRaises(storage.ContractError): current.validate_plan("Q16c", document)
        document = archived_fixture("Q16c")
        document["schema_version"] = "cpu-prefetch-stage17-formal-scheduled-plan/3"
        with self.assertRaises(storage.ContractError): current.validate_plan("Q16c", document)


if __name__ == "__main__":
    unittest.main()
