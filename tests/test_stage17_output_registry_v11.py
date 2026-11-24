"""Formal custody admission through real files; no empirical validity claim."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import stage17_output_registry_v11 as registry
from test_stage17_formal_ring_plan_v1 import plan_fixture


class FormalCustody(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pinned = registry.pin_registry(ROOT)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.plan = plan_fixture()
        cls.hardware = {"mapping_id": "INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1",
                        "q15_w_result_sha256": "a" * 64,
                        "prestate": [{"cpu": cpu, "complete_value_hex": "0000000000000000"} for cpu in (0, 1, 8)]}
        cls.request = dict(schema_version="cpu-prefetch-stage17-fixed-action-request/6",
            request_id="software-request", action_id="Q16a", stand_id="synthetic-stand",
            authorization_id="software-authorization", attempt_id="software-attempt",
            runtime_binding={}, release_binding={}, predecessor_resolutions=["a", "b", "c"],
            action_inputs={"plan": cls.plan, "hardware_control": cls.hardware, "prerequisite_bindings": {}})
        artifacts = []
        retained = []
        for ordinal in range(708):
            rows = []
            for name in registry.capture_names("Q16a", ordinal):
                role, schema, media = registry.artifact_identity("Q16a", name)
                # Empty primary/demand bytes are legitimate custody objects;
                # independent scientific validation must reject insufficient data.
                raw = b"{}\n" if media == "application/json" else b""
                (cls.root / name).write_bytes(raw)
                binding = dict(role=role, schema_identity=schema, media_type=media,
                    file_name=name, size_bytes=len(raw), sha256=registry.sha256(raw))
                artifacts.append(binding)
                rows.append({key: binding[key] for key in ("file_name", "size_bytes", "sha256")})
            retained.append(dict(ordinal=ordinal, artifacts=rows, native_complete=True))
        cls.report = dict(schema_version="cpu-prefetch-stage17-formal-retention-report/1",
            action_id="Q16a", plan_sha256=registry.sha256(registry.canonical(cls.plan)),
            mapping_id=cls.hardware["mapping_id"], whole_plots=[
                dict(state="H0", apply_readback=[], restore_readback=[], restoration_verified=True),
                dict(state="H1", apply_readback=[dict(cpu=x["cpu"], complete_value_hex="000000000000000f") for x in cls.hardware["prestate"]],
                     restore_readback=list(reversed(cls.hardware["prestate"])), restoration_verified=True)],
            native_results_after_cleanup=[{"software_fixture": True} for _ in range(708)], captures=retained,
            restoration_verified=True, mandatory_failure=False, scientific_validity="NOT_ASSESSED",
            execution_authority=False, phase18_authority=False)
        raw = registry.canonical(cls.report)
        (cls.root / registry.REPORT_NAME).write_bytes(raw)
        role, schema, media = registry.artifact_identity("Q16a", registry.REPORT_NAME)
        artifacts.append(dict(role=role, schema_identity=schema, media_type=media,
            file_name=registry.REPORT_NAME, size_bytes=len(raw), sha256=registry.sha256(raw)))
        cls.result = dict(schema_version="cpu-prefetch-stage17-phase-action-result/6",
            result_id="software-result", **{key: cls.request[key] for key in (
                "request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
                "runtime_binding", "release_binding", "predecessor_resolutions")},
            request_sha256=registry.sha256(registry.canonical(cls.request)), authorization_sha256="b" * 64,
            artifacts=artifacts, started_at_utc="2030-01-01T00:00:00Z", completed_at_utc="2030-01-01T00:00:01Z",
            duration_ns=1_000_000_000, terminal_state="FORMAL_ARTIFACTS_RETAINED_UNASSESSED",
            restoration_verified=True, quarantined=False, synthetic_test_only=True, phase18_authority=False)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def admit(self, result=None, request=None):
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            return registry.validate_worker_result(registry=self.pinned, directory_fd=descriptor,
                result=self.result if result is None else result,
                request=self.request if request is None else request,
                authorization_sha256="b" * 64, synthetic_test_only=True)
        finally:
            os.close(descriptor)

    def report_mutation(self, change):
        result = copy.deepcopy(self.result)
        report = copy.deepcopy(self.report)
        change(report)
        raw = registry.canonical(report)
        path = self.root / registry.REPORT_NAME
        original = path.read_bytes()
        try:
            path.write_bytes(raw)
            result["artifacts"][-1].update(size_bytes=len(raw), sha256=registry.sha256(raw))
            with self.assertRaises((registry.OutputAdmissionError, ValueError)):
                self.admit(result)
        finally:
            path.write_bytes(original)

    def test_complete_family_is_custody_only_and_unassessed(self):
        result = self.admit()
        self.assertEqual(len(result["captures"]), 708)
        self.assertEqual(result["scientific_validity"], "NOT_ASSESSED")
        self.assertFalse(result["execution_authority"])

    def test_missing_duplicate_extra_or_misclassified_artifacts_reject(self):
        for mode in ("missing", "duplicate", "extra", "role", "path"):
            result = copy.deepcopy(self.result)
            if mode == "missing": result["artifacts"].pop(0)
            elif mode == "duplicate": result["artifacts"].append(result["artifacts"][0])
            elif mode == "extra":
                result["artifacts"].append({**result["artifacts"][0], "file_name": "extra.bin"})
            elif mode == "role": result["artifacts"][0]["role"] = "Q16B_PRIMARY_RAW"
            else: result["artifacts"][0]["file_name"] = "../outside.bin"
            with self.assertRaises((registry.OutputAdmissionError, ValueError), msg=mode):
                self.admit(result)

    def test_actual_hash_and_size_are_verified(self):
        path = self.root / registry.capture_names("Q16a", 707)[0]
        try:
            path.write_bytes(b"tampered")
            with self.assertRaises(registry.OutputAdmissionError): self.admit()
        finally:
            path.write_bytes(b"")

    def test_symlink_cannot_substitute_for_a_bound_raw_file(self):
        path = self.root / registry.capture_names("Q16a", 707)[0]
        target = self.root / registry.capture_names("Q16a", 706)[0]
        path.unlink()
        try:
            path.symlink_to(target)
            with self.assertRaises((registry.OutputAdmissionError, OSError)): self.admit()
        finally:
            path.unlink(); path.write_bytes(b"")

    def test_whole_plot_and_cleanup_membership_are_exact(self):
        self.report_mutation(lambda report: report["whole_plots"][1]["restore_readback"].reverse())
        self.report_mutation(lambda report: report["native_results_after_cleanup"].pop())
        self.report_mutation(lambda report: report["captures"].reverse())
        self.report_mutation(lambda report: report["captures"][-1].update(native_complete=1))

    def test_report_cannot_claim_scientific_validity_or_new_authority(self):
        self.report_mutation(lambda report: report.update(scientific_validity="VALID"))
        self.report_mutation(lambda report: report.update(execution_authority=True))

    def test_lineage_and_restoration_fail_closed(self):
        for field, value in (("authorization_sha256", "0" * 64), ("request_sha256", "0" * 64),
                             ("restoration_verified", False), ("synthetic_test_only", False)):
            result = copy.deepcopy(self.result); result[field] = value
            with self.assertRaises(registry.OutputAdmissionError): self.admit(result)

    def test_all_three_artifact_name_families_are_distinct(self):
        for action, count in (("Q16a", 9), ("Q16b", 6), ("Q16c", 8)):
            names = registry.capture_names(action, 123)
            self.assertEqual(len(names), count)
            self.assertEqual(len(set(names)), count)
            for name in names: self.assertTrue(registry.artifact_identity(action, name))

    def test_report_parser_uses_hashed_snapshot_despite_same_size_replacement(self):
        path = self.root / registry.REPORT_NAME
        original = path.read_bytes()
        changed = copy.deepcopy(self.report)
        changed["whole_plots"][1]["restore_readback"].reverse()
        changed_raw = registry.canonical(changed)
        self.assertEqual(len(original), len(changed_raw))
        result = copy.deepcopy(self.result)
        result["artifacts"][-1]["sha256"] = registry.sha256(changed_raw)
        real_loads = registry.json.loads
        swapped = False
        def swap_before_parse(payload, *args, **kwargs):
            nonlocal swapped
            if isinstance(payload, bytearray) and payload == changed_raw:
                path.write_bytes(original)
                swapped = True
            return real_loads(payload, *args, **kwargs)
        try:
            path.write_bytes(changed_raw)
            with patch.object(registry.json, "loads", side_effect=swap_before_parse):
                with self.assertRaises(registry.OutputAdmissionError): self.admit(result)
            self.assertTrue(swapped)
        finally:
            path.write_bytes(original)


if __name__ == "__main__":
    unittest.main()
