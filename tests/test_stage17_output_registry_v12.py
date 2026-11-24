"""Archive-family adapter: full coverage metadata and actual nine-file custody.

The small real codec fixture tests the private byte seam, not a qualified
production family or authority. Production never accepts an injected readback.
"""
import copy
from dataclasses import asdict, replace
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import stage17_output_registry_v12 as registry
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_custody_v1 as custody
from test_stage17_formal_plan_v1 import plan_fixture
from test_stage17_calibration_export_v2 import archived_plan
import test_stage17_formal_archive_registry_v1 as real_fixture
from test_stage17_formal_archive_v1 import codec_limit, digest


class FamilyMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pinned = registry.pin_registry(ROOT)
        cls.plan = archived_plan(plan_fixture("Q16c"))
        cls.hardware = dict(mapping_id="synthetic-mapping", prestate=[
            dict(cpu=i, complete_value_hex="0000000000000000") for i in (0, 1, 8)])
        cls.request = dict(schema_version="cpu-prefetch-stage17-fixed-action-request/6",
            action_id="Q16c", request_id="synthetic-request", stand_id="synthetic-stand",
            authorization_id="synthetic-auth", attempt_id="synthetic-attempt",
            runtime_binding={}, release_binding={}, predecessor_resolutions=["a", "b", "c"],
            action_inputs=dict(plan=cls.plan, hardware_control=cls.hardware))
        cls.artifacts, captures = [], []
        for ordinal in range(180):
            names = registry.capture_names("Q16c", ordinal)
            bindings = []
            for name in (*names, f"formal-capture-{ordinal}-final-checkpoint.json",
                         f"formal-capture-{ordinal}-archive-custody.json"):
                role, schema, media = registry.artifact_identity("Q16c", name)
                binding = dict(role=role, schema_identity=schema, media_type=media,
                               file_name=name, size_bytes=0, sha256=digest(b""))
                cls.artifacts.append(binding)
                bindings.append(registry.reference(binding))
            captures.append(dict(ordinal=ordinal, native_complete=True, artifacts=bindings[:-2],
                                 checkpoint=bindings[-2], archive_custody=bindings[-1]))
        cls.report = dict(schema_version="cpu-prefetch-stage17-formal-retention-report/2",
            action_id="Q16c", plan_sha256=registry.plan_sha256(cls.plan),
            mapping_id=cls.hardware["mapping_id"], whole_plots=[
                dict(state="H0", apply_readback=[], restore_readback=[], restoration_verified=True),
                dict(state="H1", apply_readback=[dict(cpu=i, complete_value_hex="000000000000000f")
                     for i in (0, 1, 8)], restore_readback=list(reversed(cls.hardware["prestate"])),
                     restoration_verified=True)], captures=captures,
            native_results_after_cleanup=[dict(software_fixture=True) for _ in captures],
            restoration_verified=True, mandatory_failure=False, scientific_validity="NOT_ASSESSED",
            execution_authority=False, phase18_authority=False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.fd)

    def inputs(self, report=None):
        raw = archive.canonical(self.report if report is None else report)
        (self.root / registry.REPORT_NAME).write_bytes(raw)
        role, schema, media = registry.artifact_identity("Q16c", registry.REPORT_NAME)
        artifacts = copy.deepcopy(self.artifacts) + [dict(role=role, schema_identity=schema,
            media_type=media, file_name=registry.REPORT_NAME, size_bytes=len(raw), sha256=digest(raw))]
        result = dict(schema_version="cpu-prefetch-stage17-phase-action-result/6", result_id="synthetic-result",
            **{k: self.request[k] for k in ("request_id", "action_id", "stand_id", "authorization_id", "attempt_id",
                                          "runtime_binding", "release_binding", "predecessor_resolutions")},
            request_sha256=digest(registry.canonical(self.request)), authorization_sha256="b" * 64,
            artifacts=artifacts, started_at_utc="2030-01-01T00:00:00Z", completed_at_utc="2030-01-01T00:00:01Z",
            duration_ns=1_000_000_000, terminal_state="FORMAL_ARTIFACTS_RETAINED_UNASSESSED",
            restoration_verified=True, quarantined=False, synthetic_test_only=True, phase18_authority=False)
        return dict(registry=self.pinned, directory_fd=self.fd, result=result, request=self.request,
                    authorization_sha256="b" * 64, synthetic_test_only=True)

    def test_full180_metadata_native_no_lf_identity_transport_lf_preserved(self):
        plan, extent, report = registry._metadata(**self.inputs())
        self.assertEqual(len(extent.captures), 180)
        self.assertEqual(report["plan_sha256"], digest(archive.canonical(plan)))
        self.assertNotEqual(report["plan_sha256"], digest(registry.canonical(plan)))
        self.assertTrue(registry.canonical(self.request).endswith(b"\n"))
        wrong = copy.deepcopy(self.report)
        wrong["plan_sha256"] = digest(registry.canonical(plan))
        with self.assertRaisesRegex(registry.OutputAdmissionError, "plan_sha256"):
            registry._metadata(**self.inputs(wrong))

    def test_missing_last_capture_checkpoint_or_wrong_role_rejected(self):
        for index in (-2, -3, -4):
            values = self.inputs()
            values["result"]["artifacts"].pop(index)
            with self.assertRaises(registry.OutputAdmissionError): registry._metadata(**values)
        values = self.inputs()
        values["result"]["artifacts"][-2]["role"] = "Q16C_PRIMARY_RAW"
        with self.assertRaises(registry.OutputAdmissionError): registry._metadata(**values)

    def test_wholeplot_order_failed_native_or_changed_final_coverage_rejected(self):
        for mutate in (lambda r: r["whole_plots"][1]["restore_readback"].reverse(),
                       lambda r: r["captures"][-1].update(native_complete=False),
                       lambda r: r["native_results_after_cleanup"].pop(),
                       lambda r: r["captures"][-1].update(ordinal=True),
                       lambda r: r.update(execution_authority=True)):
            report = copy.deepcopy(self.report); mutate(report)
            with self.assertRaises(registry.OutputAdmissionError):
                registry._metadata(**self.inputs(report))

    def test_unqualified_profile_or_absent_analysis_plan_fails_closed(self):
        values = self.inputs()
        with self.assertRaisesRegex(registry.OutputAdmissionError, "RuntimeProfile"):
            registry.verify_archived_formal_family(**values, repository_root=ROOT,
                                                   archive_runtime_profile=True)
        image = runtime.ImageBinding(Path(sys.executable), 1, "e" * 64)
        profile = runtime.RuntimeProfile(image, image, SimpleNamespace(
            implementation_profile_sha256=self.plan["storage"]["implementation_profile_sha256"]), ())
        with self.assertRaisesRegex(registry.OutputAdmissionError, "offline analysis"):
            registry.verify_archived_formal_family(**values, repository_root=ROOT,
                                                   archive_runtime_profile=profile)

    def test_legacy_dispatch_unchanged(self):
        request = dict(self.request, schema_version="cpu-prefetch-stage17-fixed-action-request/5")
        values = dict(self.inputs(), request=request)
        with patch.object(registry.predecessor, "validate_worker_result", return_value="legacy") as previous:
            self.assertEqual(registry.validate_worker_result(**values), "legacy")
            previous.assert_called_once_with(**values)


class ActualInventoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = real_fixture.ArchiveRegistryTests("test_full_logical_physical_bijection_is_read_only_and_not_science")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.plan = dict(action_id="Q16a", storage=dict(program_id="synthetic-program"),
                         captures=[dict(capture=f.capture)])
        self.extent = SimpleNamespace(captures=[SimpleNamespace(ordinal=0)])
        final = archive.parse_json((f.store.working / f.checkpoint.file_name).read_bytes())
        self.report = dict(captures=[dict(checkpoint=asdict(f.checkpoint), archive_custody=asdict(f.receipt),
            artifacts=[asdict(s.expected) for s in f.sources])],
            native_results_after_cleanup=[final["native_result_after_cleanup"]])

    def verify(self, readback=archive.verify_archive):
        f = self.fixture
        with codec_limit():
            return registry._verified_inventory(store=f.store, plan=self.plan, extent=self.extent,
                report=self.report, profile=SimpleNamespace(decoder=f.f.profile),
                decoder_limits=f.f.limits, readback=readback)

    def test_actual_nine_archive_files_originals_absent_scope_from_store(self):
        result = self.verify()
        self.assertEqual(len(result["captures"][0]["artifacts"]), 9)
        self.assertEqual(result["scope_bindings"]["program_scope_sha256"], self.fixture.scope)
        self.assertEqual(result["scope_bindings"]["program_root_binding"]["inode"], self.fixture.root.stat().st_ino)
        self.assertEqual(result["scientific_validity"], "NOT_ASSESSED")
        self.assertFalse(result["execution_authority"])

    def test_outer_final_and_raw_binding_must_match_original_checkpoint(self):
        self.report["native_results_after_cleanup"][0]["stop"] = 12
        with self.assertRaisesRegex(registry.OutputAdmissionError, "final native"):
            self.verify()
        self.report["native_results_after_cleanup"][0]["stop"] = 14
        self.report["captures"][0]["artifacts"][0]["sha256"] = "f" * 64
        with self.assertRaisesRegex(registry.OutputAdmissionError, "canonical inventory"):
            self.verify()

    def test_foreign_family_artifact_or_pending_checkpoint_rejected(self):
        f = self.fixture
        key = f.family + ":foreign.bin"
        f.store._states[key] = {}
        with self.assertRaisesRegex(registry.OutputAdmissionError, "ledger"):
            self.verify()
        del f.store._states[key]
        f.store._capture_pending.add((f.family, "0" * 64))
        with self.assertRaisesRegex(registry.OutputAdmissionError, "unfinished"):
            self.verify()

    def test_fabricated_boolean_or_actual_corrupted_archive_rejected(self):
        with self.assertRaises(archive.ArchiveError): self.verify(lambda *a, **k: True)
        path = self.fixture.root / "archives" / self.fixture.document["artifacts"][0]["archive_name"]
        raw = path.read_bytes(); path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(archive.ArchiveError): self.verify()

    def test_metadata_adapter_does_not_invoke_a_decoder_or_claim_inverse(self):
        f = self.fixture
        with patch.object(custody, "checked_readback", side_effect=AssertionError("not metadata")):
            result = registry._verified_inventory(store=f.store, plan=self.plan, extent=self.extent,
                report=self.report, profile=SimpleNamespace(decoder=f.f.profile),
                decoder_limits=f.f.limits, metadata_only=True)
        self.assertFalse(result["inverse_readback_performed"])
        self.assertFalse(result["captures"][0]["inverse_readback_performed"])


class AnalysisResourceTests(unittest.TestCase):
    def setUp(self):
        deadline = time.monotonic_ns() + 60_000_000_000
        self.plan = dict(action_id="Q16a", storage=dict(program_scope_sha256="a" * 64,
            broker_address_space_bytes=1024**3, codec_address_space_bytes=2 * 1024**3,
            analysis_capture_workspace_bytes=1024**3, archive_quota_bytes=6_000_000_000_000))
        self.extent = SimpleNamespace(captures=[SimpleNamespace(ordinal=0)],
                                      declared=SimpleNamespace(memory_bytes=8 * 1024**3))
        self.profile = SimpleNamespace(decoder=SimpleNamespace(implementation_profile_sha256="b" * 64))
        self.values = dict(parent_address_space_bytes=2 * 1024**3, total_memory_bytes=5 * 1024**3,
            custody=custody.CustodyLimits(65536, 1000, 2000, 32768, deadline),
            runtime=runtime.RetainedReadbackLimits(1024**3, 2 * 1024**3, 65536, 65536,
                65536, 2_000_000_000, deadline, 9),
            decoder=archive.DecodeLimits(32768, 8 * 1024**2, 8 * 1024**2, 64 * 1024**2,
                64 * 1024**2, 1024, 1 << 22, deadline))

    def limits(self, **changes):
        values = dict(self.values, **changes)
        document = dict(schema_version="cpu-prefetch-stage17-archive-analysis-limits/1",
            plan_sha256=registry.plan_sha256(self.plan),
            program_scope_sha256=self.plan["storage"]["program_scope_sha256"],
            implementation_profile_sha256=self.profile.decoder.implementation_profile_sha256,
            parent_address_space_bytes=values["parent_address_space_bytes"],
            total_memory_bytes=values["total_memory_bytes"],
            **{k: asdict(values[k]) for k in ("custody", "runtime", "decoder")},
            execution_authority=False, phase18_authority=False)
        raw = archive.canonical(document)
        return registry.AnalysisLimits(original_bytes=raw,
            binding=archive.PhysicalBinding(len(raw), digest(raw)), **values)

    def validate(self, limits):
        with codec_limit():
            return limits.validate(self.plan, self.extent, self.profile)

    def test_bound_current_analysis_budget_accounts_parent_broker_decoder(self):
        limits = self.limits()
        self.assertIsNone(self.validate(limits))
        self.assertNotIn("authority_expiry_monotonic_ns", asdict(limits.runtime))
        for changed in (dict(total_memory_bytes=3 * 1024**3),
                        dict(parent_address_space_bytes=1024**3),
                        dict(runtime=replace(limits.runtime, max_children=8)),
                        dict(runtime=replace(limits.runtime, max_children=10)),
                        dict(runtime=replace(limits.runtime, cleanup_reserve_ns=1)),
                        dict(runtime=replace(limits.runtime, broker_address_space_bytes=2 * 1024**3))):
            with self.subTest(changed=changed), self.assertRaises((registry.OutputAdmissionError, archive.ArchiveError)):
                self.validate(self.limits(**changed))

    def test_original_limit_bytes_hash_and_deadlines_cannot_be_replaced(self):
        limits = self.limits()
        historical = runtime.RuntimeLimits(**asdict(limits.runtime),
                                            authority_expiry_monotonic_ns=limits.runtime.deadline_ns)
        for candidate in (replace(limits, original_bytes=limits.original_bytes+b"\n"),
                          replace(limits, binding=archive.PhysicalBinding(limits.binding.size_bytes, "f" * 64)),
                          self.limits(runtime=historical),
                          self.limits(decoder=replace(limits.decoder, deadline_ns=1)),
                          self.limits(custody=replace(limits.custody, deadline_ns=limits.custody.deadline_ns+1))):
            with self.assertRaises((registry.OutputAdmissionError, archive.ArchiveError)):
                self.validate(candidate)


if __name__ == "__main__":
    unittest.main()
