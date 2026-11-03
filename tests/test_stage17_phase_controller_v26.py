"""Actual profile files with synthetic release contexts; no phase authority."""
import hashlib
from pathlib import Path
import shutil
import sys
import time
import unittest

import test_stage17_phase_controller_v25 as historical_tests
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_archive_runtime_v1 import MODULES
from test_stage17_formal_archive_v1 import ArchiveFixture
import stage17_phase_controller_v26 as controller
import stage17_formal_archive_v1 as archive


class ArchiveControllerTests(unittest.TestCase):
    def setUp(self):
        self.original = historical_tests.FormalController()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.request = self.original.request
        self.request["schema_version"] = "cpu-prefetch-stage17-fixed-action-request/6"
        self.validation = self.original.validation
        self.plan = self.original.plan
        self.plan["schema_version"] = controller.plans.VERSION["Q16a"]
        defaults = archived_fixture("Q16a")
        self.plan["custody_policy_id"] = defaults["custody_policy_id"]
        self.plan["storage"] = defaults["storage"]
        storage = self.plan["storage"]
        storage["analysis_capture_workspace_bytes"] = 512 * 1024**2
        budget = self.plan["budget"]
        budget["memory_bytes"] += storage["codec_address_space_bytes"] + storage["broker_address_space_bytes"]
        budget["watchdog_ns"] += len(self.plan["captures"]) * storage["per_capture_archive_ns"]
        for key in ("analysis_scratch_bytes", "disk_reserve_bytes", "required_free_disk_bytes"):
            budget[key] = defaults["budget"][key]
        root = self.original.root / "bundle"
        (root / "tools").mkdir(parents=True)
        (root / "config/stage17").mkdir(parents=True)
        encoder = root / "software-fixture-encoder"
        encoder.write_bytes(b"software-only image; never executed or qualified")
        tools = Path(__file__).resolve().parents[1] / "tools"
        for name in MODULES:
            shutil.copyfile(tools / (name + ".py"), root / "tools" / (name + ".py"))

        def binding(path, location):
            path = path.resolve()
            return dict(location=location, path=str(path.relative_to(root if location == "bundle" else Path("/"))),
                        size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        decoder = ArchiveFixture(self.original.root).profile
        document = dict(schema_version="cpu-prefetch-formal-archive-implementation-profile/1",
            policy_id=archive.POLICY_ID, encoder=binding(encoder, "bundle"),
            python=binding(Path(sys.executable), "runtime"),
            zstd_library=binding(decoder.zstd_library_path, "runtime"),
            source_closure=[dict(module=name, image=binding(root / "tools" / (name + ".py"), "bundle"))
                            for name in MODULES],
            options=dict(zstd_version="1.5.7", compression_level=3, worker_threads=1, nbWorkers=0,
                         window_log=22, checksum_flag=1, content_size_flag=1, dictionary_id_flag=0))
        raw = archive.canonical(document)
        path = root / "config/stage17/formal-archive-implementation-profile-v1.json"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        storage["implementation_profile_sha256"] = digest
        self.context = self.original.context
        self.context.update(archive_profile_binding=dict(path=str(path), size_bytes=len(raw), sha256=digest),
                            archive_bundle_root=str(root), archive_runtime_root="/")
        self.original.namespace["plan_sha256"] = hashlib.sha256(archive.canonical(self.plan)).hexdigest()
        self.request["action_inputs"]["prerequisite_bindings"]["namespace_registry"] = self.original.write(
            "namespaces", self.original.namespace)

    def profile(self):
        return controller.qualified_archive_profile(self.request, self.validation,
                                                    deadline_ns=time.monotonic_ns() + 5_000_000_000)

    def test_complete_original_plan_and_actual_profile_admitted_without_execution(self):
        extent = controller.validate_action_inputs(self.request, self.validation)
        self.assertEqual(len(extent.captures), 708)
        self.assertFalse(extent.execution_authority)
        profile = self.profile()
        self.assertEqual(profile.decoder.implementation_profile_sha256,
                         self.plan["storage"]["implementation_profile_sha256"])

    def test_absent_or_unqualified_profile_has_no_host_fallback(self):
        for key in ("archive_profile_binding", "archive_bundle_root", "archive_runtime_root"):
            value = self.context.pop(key)
            with self.assertRaises(controller.ControllerError): self.profile()
            self.context[key] = value
        self.context["bundle_profile"] = "STAGE17-PILOT-CANDIDATE-BUNDLE-v25"
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_signed_profile_original_bytes_and_local_closure_must_match(self):
        expected = self.plan["storage"]["implementation_profile_sha256"]
        self.plan["storage"]["implementation_profile_sha256"] = "0" * 64
        with self.assertRaises(controller.ControllerError): self.profile()
        self.plan["storage"]["implementation_profile_sha256"] = expected
        source = Path(self.context["archive_bundle_root"]) / "tools/check_canonical.py"
        source.write_bytes(source.read_bytes() + b"\n# mutated\n")
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_profile_path_cannot_escape_qualified_bundle_or_extend_deadline(self):
        with self.assertRaises(controller.ControllerError):
            controller.qualified_archive_profile(self.request, self.validation, deadline_ns=1)
        self.context["archive_profile_binding"]["path"] = str(self.original.root / "foreign.json")
        with self.assertRaises(controller.ControllerError): self.profile()

    def test_archive_validator_does_not_mutate_historical_globals(self):
        original = controller.previous.contract.validate_plan
        namespace = dict(controller.previous.validate_action_inputs.__globals__)
        controller.validate_action_inputs(self.request, self.validation)
        self.assertIs(controller.previous.contract.validate_plan, original)
        self.assertEqual(namespace, controller.previous.validate_action_inputs.__globals__)


if __name__ == "__main__":
    unittest.main()
