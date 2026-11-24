"""Real C++ software backend/session/publisher -> independent Python phase audit.

Use --binary <manually built stage17_discovery_fixture>. No hardware capture,
production admission, native page/TLS/MSR/thread/smaps qualification or release
codegen authority. Fixture control JSON is consumed as emitted, never rebuilt in
Python. The independently parsed synthetic frozen plan supplies identities,
geometry, arena seed, durations and capacities to both sides.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_stage17_discovery_contract as plans
import stage17_discovery_validation_v1 as validator


class CppDiscoveryBridgeTests(unittest.TestCase):
    binary: Path

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="discovery-cpp-bridge-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        source = plans.fixture()
        # Bound software-only fixture storage, before freezing/validating plan.
        for capture in source["captures"]:
            capture["budget"].update(warmup_attempt_capacity=4096,
                                     measurement_attempt_capacity=4096)
        cls.plan = validator.contract.validate_plan(source)
        cls.capture = cls.plan.captures[0]
        config = cls.root / "capture.json"
        config.write_text(json.dumps(source["captures"][0]), encoding="utf-8")
        cls.outputs = {}
        cls.captures = {}
        for mode in ("normal", "crossing", "capacity"):
            mode_source = copy.deepcopy(source)
            if mode == "capacity":
                mode_source["captures"][0]["budget"]["measurement_attempt_capacity"] = 8
            cls.captures[mode] = validator.contract.validate_plan(mode_source).captures[0]
            config.write_text(json.dumps(mode_source["captures"][0]), encoding="utf-8")
            root = cls.root / mode
            result = subprocess.run([str(cls.binary), str(config), str(root), mode],
                                    capture_output=True, text=True, timeout=30)
            if result.returncode:
                details = (root / "fixture-final-result.json")
                raise AssertionError(result.stderr + (details.read_text() if details.exists() else ""))
            control = json.loads((root / "discovery-c00-control.json").read_text())
            final = json.loads((root / "fixture-final-result.json").read_text())
            cls.outputs[mode] = (root, control, final)

    def validate_output(self, mode):
        root, control, final = self.outputs[mode]
        capture = self.captures.get(mode, self.capture)
        self.assertEqual(control["session"], final["session"])
        self.assertEqual(control["session"]["stop"], 8 if mode == "capacity" else 9)
        self.assertTrue(final["publication_attempted"])
        self.assertTrue(final["publication_succeeded"])
        self.assertFalse(control["publication_succeeded"])
        arena = validator.Arena(capture)
        for key, expected in zip(("publication_content_sha256", "ordered_index_sha256",
                                  "address_delta_sha256"), arena.hashes):
            self.assertEqual(control["arena"][key], expected)
        outcomes = []
        for i, name in enumerate(("warmup", "measurement")):
            kwargs = dict(run_id=getattr(capture, name).run_id,
                          phase_origin=control["session"]["origins"][i],
                          clock_origin=control["clock_origin"]["absolute_nanoseconds"],
                          duration_ns=validator.contract.WARMUP_NS if i == 0 else capture.measurement_ns,
                          attempt_capacity=getattr(capture.budget, name + "_attempt_capacity"),
                          drain_capacity=capture.budget.drain_attempt_capacity,
                          initial_checksum=17, arena=arena, reset_required=i == 0,
                          arena_address=control["arena"]["storage_address"])
            outcomes.append(validator.validate_phase(
                root, control["phases"][i], control["session"][name],
                control["session"][name + "_drain"], **kwargs))
            self.assertGreaterEqual(outcomes[-1].accepted, 2)
            self.assertEqual(control["session"][name][1]["advanced"], 1)
            self.assertGreaterEqual(control["session"][name + "_drain"]["dequeued"], 1)
            self.assertEqual(control["phases"][i]["drain_rows"][-1]["operation"]["status"], 1)
        return outcomes

    def test_real_cpp_phases_and_retained_drain(self):
        self.validate_output("normal")

    def test_valid_last_consumer_admission_crosses_deadline(self):
        self.validate_output("crossing")
        _, control, _ = self.outputs["crossing"]
        deadline = control["session"]["origins"][1] + self.capture.measurement_ns * 1000
        # This is the actual captured event, not a patched Python clock row.
        current = control["phases"][1]["consumer_current"]
        self.assertGreaterEqual(current["dequeue_invocation"]["relative_picoseconds"], deadline)
        self.assertGreaterEqual(control["session"]["measurement"][1]["last_observed_tick"],
                                current["action_completion"]["relative_picoseconds"])

    def test_capacity_retains_peer_inflight_action_after_its_last_poll(self):
        results = self.validate_output("capacity")
        self.assertTrue(results[1].capacity_limited)
        _, control, _ = self.outputs["capacity"]
        workers = control["session"]["measurement"]
        self.assertEqual([worker["stop"] for worker in workers], [1, 6])
        current = control["phases"][1]["consumer_current"]
        self.assertLess(workers[1]["last_observed_tick"],
                        current["action_completion"]["relative_picoseconds"])
        self.assertEqual(control["phases"][1]["consumer_snapshot"]["completeness"],
                         "SEALED_INCOMPLETE")

    def test_fixture_preserves_absent_hardware_facts(self):
        for root, control, final in self.outputs.values():
            scope = json.loads((root / "fixture-scope.json").read_text())
            self.assertTrue(scope["synthetic"])
            self.assertFalse(scope["hardware_claim"])
            self.assertFalse(scope["execution_authority"])
            self.assertEqual(final["stop"], 0)  # Native capture was never invoked.
            self.assertEqual(control["regions"], [])
            self.assertEqual(control["residency"], [])
            self.assertEqual(control["controls"], [])
            self.assertIsNone(final["worker_mappings"])
            self.assertEqual(len(list(root.glob("discovery-c00-*"))), 7)
            with self.assertRaises(validator.ValidationError):
                validator.validate_capture(root, control, final, self.capture, {}, {}, {})

    def test_actual_publisher_metadata_mutants_fail(self):
        root, original, final = self.outputs["normal"]
        for label in ("failed_current_clock", "bool_as_integer", "missing_drain", "wrong_checksum"):
            with self.subTest(label=label):
                control = copy.deepcopy(original)
                phase = control["phases"][1]
                if label == "failed_current_clock":
                    phase["producer_current"]["capture"]["before_status"] = 1
                elif label == "bool_as_integer":
                    phase["producer_prefix_complete"] = 1
                elif label == "missing_drain":
                    phase["drain_rows"].pop()
                else:
                    phase["checksum"] ^= 1
                self.outputs["mutant"] = (root, control, final)
                try:
                    with self.assertRaises(validator.ValidationError):
                        self.validate_output("mutant")
                finally:
                    del self.outputs["mutant"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args, rest = parser.parse_known_args()
    CppDiscoveryBridgeTests.binary = args.binary.resolve()
    unittest.main(argv=[sys.argv[0], *rest])
