"""Formal declaration/prerequisite admission, software-only bound files."""
import copy
import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import stage17_phase_controller_v25 as controller
import stage17_q16a_discovery_v2 as selector
from test_stage17_formal_ring_plan_v1 import plan_fixture
from test_stage17_formal_plan_v1 import plan_fixture as service_plan_fixture


class FormalController(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = plan_fixture()
        self.plan["minimum_observations_per_series"] = 100000
        for item in self.plan["captures"]:
            item["capture"]["minimum_observations_per_series"] = 100000
            for phase in item["capture"]["budget"]["phases"]:
                phase.update(producer_attempt_limit=200001, consumer_poll_limit=200001)
            for phase in item["resources"]["phase_capacity"]:
                for key in phase: phase[key] = 200001
            item["execution_budget"].update(publication_memory_bytes=128_000_000,
                memory_bytes=129_000_000, max_output_bytes=200_000_000)
        self.plan["budget"].update(memory_bytes=149_000_000,
            max_output_bytes=708 * 200_000_000 + 1_000_000,
            required_free_disk_bytes=708 * 200_000_000 + 3_000_000,
            cleanup_ns=2_000_000_000,
            watchdog_ns=708 * 11_000_000_000 + 3_000_000_000)
        self.hardware = dict(mapping_id="INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1",
            q15_w_result_sha256="a" * 64, prestate=[dict(cpu=cpu, complete_value_hex="0000000000000000") for cpu in (0, 1, 8)])
        self.context = dict(bundle_profile="STAGE17-PILOT-CANDIDATE-BUNDLE-v26",
            supported_actions=["Q15-R", "Q15-W", "Q16a", "Q16b", "Q16c", "STAGE17-BLINDED-PILOT", "Q16A-DURATION-DISCOVERY"],
            release_artifact_role="STAGE17_FIXED_ACTION_WORKER", runtime_profile="STAGE17-FIXED-ACTION-WORKER-v4",
            release_artifact_size_bytes=123, release_artifact_sha256="b" * 64,
            release_artifact_path="/software-only-worker", source_revision="a" * 40)
        def resolution(context):
            return SimpleNamespace(semantic_context=context, resolution_id="software-resolution", sha256="c" * 64)
        self.validation = SimpleNamespace(resolutions={
            "S17-EXT-004": resolution({"hardware_mapping": {"mapping_id": self.hardware["mapping_id"], "prestate": self.hardware["prestate"]}}),
            "S17-EXT-005": resolution({"q15_w": {"result_sha256": self.hardware["q15_w_result_sha256"],
                "request": {"action_inputs": {"prestate": self.hardware["prestate"]}}}}),
            "S17-EXT-006": resolution(self.context)})
        observations = [selector.DiagnosticCapture(key, key.duration_ns,
            selector.ObservationCounts(200000, 200000, 199999, 199999), selector.StopReason.fixed_deadline)
            for key in selector.required_captures()]
        selected = selector.select_duration(observations)
        self.discovery = dict(scope="D207_D213_INDEPENDENT_VALIDATOR_V3", status="FULL_STUDY_VALIDATED",
            successor_validator_sha256=hashlib.sha256((ROOT / "tools/stage17_discovery_validation_v3.py").read_bytes()).hexdigest(),
            plan_sha256="d" * 64, execution_authority=False, formal_runs_contributed=0,
            validated_study=dict(plan_sha256="d" * 64, captures=[dataclasses.asdict(o) for o in observations],
                selection=dataclasses.asdict(selected), diagnostic_only=True, execution_authority=False, formal_runs_contributed=0))
        self.namespace = dict(schema_version="cpu-prefetch-stage17-formal-namespace-registration/1",
            plan_sha256=controller.registry.sha256(controller.registry.canonical(self.plan)),
            stand_id=self.plan["stand_id"], phase_identities=[item["capture"][phase] for item in self.plan["captures"] for phase in ("warmup", "measurement")], schedule_namespaces=[], execution_authority=False)
        self.request = dict(action_id="Q16a", stand_id="synthetic-stand", action_inputs={"plan": self.plan,
            "hardware_control": self.hardware, "prerequisite_bindings": {
                "discovery_validation": self.write("discovery", self.discovery), "q16a_validation": None,
                "q16b_validation": None, "namespace_registry": self.write("namespaces", self.namespace), "schedule_sources": []}})

    def write(self, name, value):
        raw = controller.registry.canonical(value)
        path = self.root / name
        path.write_bytes(raw)
        return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def validate(self):
        return controller.validate_action_inputs(self.request, self.validation)

    def test_complete_bound_q16a_declaration_and_derived_deadlines(self):
        extent = self.validate()
        policy = controller.deadline_policy(extent)
        self.assertEqual(policy["per_run_max_wall_seconds"], 11)
        self.assertEqual(policy["session_max_wall_seconds"], 7791)
        self.assertFalse(policy["implicit_extension"])

    def test_old_release_does_not_admit_new_formal_path(self):
        self.context["bundle_profile"] = "STAGE17-PILOT-CANDIDATE-BUNDLE-v25"
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_wrong_source_or_qualified_worker_pair_rejects(self):
        self.context["source_revision"] = "b" * 40
        with self.assertRaises(controller.ControllerError): self.validate()
        self.context["source_revision"] = "a" * 40
        self.hardware["q15_w_result_sha256"] = "f" * 64
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_incomplete_or_unselected_discovery_rejects(self):
        self.discovery["validated_study"]["captures"].pop()
        self.request["action_inputs"]["prerequisite_bindings"]["discovery_validation"] = self.write("discovery", self.discovery)
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_report_selection_cannot_override_original_counts(self):
        self.discovery["validated_study"]["selection"]["selected_duration_ns"] = 2_000_000_000
        self.request["action_inputs"]["prerequisite_bindings"]["discovery_validation"] = self.write("discovery", self.discovery)
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_original_bytes_and_namespace_membership_are_bound(self):
        (self.root / "discovery").write_bytes(b"{}")
        with self.assertRaises(controller.ControllerError): self.validate()
        self.request["action_inputs"]["prerequisite_bindings"]["discovery_validation"] = self.write("discovery", self.discovery)
        self.namespace["phase_identities"].pop()
        self.request["action_inputs"]["prerequisite_bindings"]["namespace_registry"] = self.write("namespaces", self.namespace)
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_future_phase_or_schedule_bindings_reject(self):
        self.request["action_inputs"]["prerequisite_bindings"]["q16a_validation"] = self.write("self-prior", {})
        with self.assertRaises(controller.ControllerError): self.validate()


class PriorCalibrationAdmission(unittest.TestCase):
    """Constructed normalized reports test admission, not raw-data provenance."""
    @classmethod
    def setUpClass(cls):
        cal = controller.calibration
        prospective = dict(repetitions=59, measurement_ns=1_000_000_000,
                           minimum_observations_per_series=100000)
        def binding(name):
            return dict(artifact_id=name, size_bytes=1, sha256="e" * 64)
        tail = dict(demand=dict(count=100000, rank=99900, value_ticks=8000),
                    issue=dict(count=100000, rank=100, value_ticks=1000))
        sources = [dict(capture_ordinal=i, warmup_run_id=f"W{i}", measurement_run_id=f"M{i}",
            validity="VALID", report_binding=binding(f"report-{i}"), failure=None,
            summary=dict(full_counts=[0, 0], duration_ticks=10**12, ticks_per_second=10**12,
                         tails=dict(producer=copy.deepcopy(tail), consumer=copy.deepcopy(tail))))
            for i in range(708)]
        geometry = [dict(context_ordinal=i, capacity=64, cache_line_bytes=64,
            slot_storage_bytes=512, source_binding=binding(f"geometry-{i}")) for i in range(6)]
        status, derived = cal._derive("Q16a", prospective, sources, geometry)
        cls.original = dict(schema_version=cal.SCHEMA_ID, action_id="Q16a",
            method_id=cal.METHOD["Q16a"], stand_id="synthetic-stand", source_revision="a" * 40,
            plan_sha256="d" * 64, status=status, prospective=prospective, ring_geometry=geometry,
            run_sources=sources, derived_result=derived, execution_authority=False, phase18_authority=False)
        cal.validate_calibration_record(cls.original)

    def setUp(self):
        self.result = copy.deepcopy(self.original)
        self.plan = service_plan_fixture("Q16c")
        self.binding = dict(sha256=hashlib.sha256(controller.registry.canonical(self.result)).hexdigest())
        for item in self.plan["captures"]:
            if item["capture"]["package"] == "R2":
                item["capture"]["ring_distance"]["calibration_evidence_id"] = "q16a-sha256-" + self.binding["sha256"]

    def validate(self):
        controller.validate_prior_calibration(self.result, "Q16a", self.plan, 1_000_000_000)
        controller.validate_ring_reuse(self.plan, self.result, self.binding)

    def test_complete_semantic_result_and_both_hardware_states_reuse(self):
        self.validate()

    def test_validated_header_cannot_hide_missing_or_forged_prior_result(self):
        self.result["run_sources"][0].update(validity="MISSING", report_binding=None, summary=None)
        with self.assertRaises(controller.ControllerError): self.validate()
        self.result = copy.deepcopy(self.original)
        self.result["derived_result"]["contexts"][0]["distance"]["d2_cache_lines"] = 3
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_prior_source_discovery_duration_and_minimum_are_required(self):
        for field, value in (("source_revision", "f" * 40), ("stand_id", "another-stand")):
            self.result = copy.deepcopy(self.original)
            self.result[field] = value
            with self.assertRaises(controller.ControllerError): self.validate()
        self.result = copy.deepcopy(self.original)
        with self.assertRaises(controller.ControllerError):
            controller.validate_prior_calibration(self.result, "Q16a", self.plan, 2_000_000_000)
        self.result["prospective"]["minimum_observations_per_series"] = 99999
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_h1_distance_and_original_record_digest_cannot_change(self):
        capture = next(item["capture"] for item in self.plan["captures"]
                       if item["capture"]["package"] == "R2" and item["capture"]["hardware_state"] == "H1")
        capture["ring_distance"]["cache_lines"] = 3
        with self.assertRaises(controller.ControllerError): self.validate()
        capture["ring_distance"]["cache_lines"] = 2
        capture["ring_distance"]["calibration_evidence_id"] = "unbound-result"
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_unprefetched_ring_also_preserves_calibrated_geometry(self):
        self.plan["captures"][0]["capture"]["geometry"]["capacity"] = 128
        with self.assertRaises(controller.ControllerError): self.validate()


class ScheduleSourceAdmission(unittest.TestCase):
    """Real accepted-generator files through the controller's source boundary.

This tests one capture's bindings; complete 180-cell membership remains the
separately tested prospective-family gate called before this boundary.
"""
    @classmethod
    def setUpClass(cls):
        from test_stage17_q16c_schedule_provenance_v1 import calibration_fixture
        cls.calibration = calibration_fixture()

    def setUp(self):
        import generate_schedule as generator
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources, self.registrations = [], []
        capture = dict(load_level="L025", warmup_ns=5_000_000_000,
                       measurement_ns=1_000_000_000, schedules=[])
        for phase in ("warmup", "measurement"):
            spec = generator.ScheduleSpec("schedule-" + phase,
                "WARMUP" if phase == "warmup" else "CALIBRATION", "namespace-" + phase,
                "registered-parent", "seed-" + phase, "derivation-" + phase,
                bytes(range(32)), 1000, capture[phase + "_ns"] * 1000,
                1, 50_000_000_000, "binary-" + phase, "schedule-" + phase + ".bin")
            generated = generator.generate_schedule(spec)
            def write(suffix, payload):
                path = self.root / (phase + suffix)
                path.write_bytes(payload)
                return dict(path=str(path), size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            self.sources.append(dict(artifact_id=spec.artifact_id,
                binding=write(".bin", generated.artifact_bytes),
                envelope_binding=write("-envelope.json", generated.envelope_bytes),
                derivation_binding=write("-derivation.json", generated.derivation_record_bytes),
                parent_namespace_id=spec.parent_namespace_id))
            self.registrations.append(dict(schedule_id=spec.schedule_id, namespace_id=spec.namespace_id,
                seed_id=spec.seed_id, phase=phase, parent_namespace_id=spec.parent_namespace_id))
            capture["schedules"].append(dict(schedule_id=spec.schedule_id, seed_id=spec.seed_id,
                namespace_id=spec.namespace_id, seed_hex=spec.master_seed.hex(), source_origin_ticks=spec.origin_ticks,
                source_horizon_ticks=spec.origin_ticks + spec.horizon_ticks, offered_count=len(generated.deadlines),
                deadline_ticks=list(generated.deadlines),
                source_artifact=dict(artifact_id=spec.artifact_id, sha256=generated.artifact_sha256)))
        self.plan = dict(scale_ordinal=0, captures=[dict(capture=capture)])

    def validate(self):
        controller.validate_schedule_sources(self.plan, self.sources, self.registrations, self.calibration)

    def test_original_binary_envelope_and_derivation_are_accepted(self):
        self.validate()

    def test_parent_claim_cannot_override_registered_parent(self):
        self.sources[0]["parent_namespace_id"] = "different-parent"
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_valid_literal_vectors_do_not_admit_changed_generator_bytes(self):
        path = Path(self.sources[0]["binding"]["path"])
        path.write_bytes(path.read_bytes()[:-1] + b"\xff")
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_rate_must_match_selected_scale_not_just_schedule_hash(self):
        self.plan["scale_ordinal"] = 1
        with self.assertRaises(controller.ControllerError): self.validate()

    def test_unreferenced_source_and_namespace_registration_reject(self):
        self.registrations.append({**self.registrations[0], "schedule_id": "extra"})
        with self.assertRaises(controller.ControllerError): self.validate()
        self.registrations.pop()
        self.sources.append({**self.sources[0], "artifact_id": "extra"})
        with self.assertRaises(controller.ControllerError): self.validate()


if __name__ == "__main__": unittest.main()
