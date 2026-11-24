"""Native no-LF /2 plan identity versus preserved historical transport bytes."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_calibration_v1 as old
import stage17_formal_calibration_v2 as current
import stage17_calibration_export_v2 as export
import stage17_formal_plan_v2 as plans
import stage17_output_registry_v12 as registry


class PlanIdentityTests(unittest.TestCase):
    def test_native_exact_bytes_keep_unicode_integer_and_no_lf(self):
        plan = {"schema_version": plans.VERSION["Q16a"], "value": 18446744073709551615,
                "label": "λ", "capture": {"ordinal": 0}}
        expected = ('{"capture":{"ordinal":0},"label":"λ","schema_version":'
                    '"cpu-prefetch-stage17-formal-ring-plan/2","value":18446744073709551615}').encode()
        self.assertEqual(current.plan_bytes(plan), expected)
        self.assertEqual(registry.plan_sha256(plan), hashlib.sha256(expected).hexdigest())
        self.assertEqual(old.canonical(plan), expected + b"\n")
        self.assertEqual(registry.canonical(plan), expected + b"\n")
        plan["schema_version"] = plans.previous.VERSION["Q16a"]
        self.assertEqual(current.plan_bytes(plan), old.canonical(plan))

    def test_q16c_failure_requires_native_plan_identity_without_reencoding_report(self):
        capture = dict(ordinal=0, cell_ordinal=0, repetition_ordinal=0,
                       warmup=dict(run_id="warmup"), measurement=dict(run_id="measurement"))
        plan = dict(schema_version=plans.VERSION["Q16c"], source_revision="a" * 40,
                    scale_ordinal=0, repetitions_per_cell=1, captures=[dict(capture=capture)])
        bind = lambda name: dict(artifact_id=name, size_bytes=0, sha256=hashlib.sha256(b"").hexdigest())
        failure = dict(schema_version=old.FAILURE_SCHEMA_ID, action_id="Q16c", method_id=plans.previous.METHOD["Q16c"],
            capture_ordinal=0, warmup_run_id="warmup", measurement_run_id="measurement",
            plan_sha256=hashlib.sha256(current.plan_bytes(plan)).hexdigest(), source_revision=plan["source_revision"],
            error=dict(type="ValidationError", message="software-only failure"),
            input_bindings=dict(native_input=bind("input"), control=bind("control"), final=bind("final"),
                                raw_artifacts=[bind("raw-" + str(i)) for i in range(7)]),
            execution_authority=False, phase18_authority=False)
        original = old.canonical(failure)
        result, blockers = export._probe(plan, {0: ("INVALID", failure, bind("failure"))})
        self.assertEqual(result["coverage_state"], "UNRESOLVED")
        self.assertEqual(blockers, ["Q16c capture 0 INVALID"])
        self.assertEqual(old.canonical(failure), original)
        failure["plan_sha256"] = hashlib.sha256(old.canonical(plan)).hexdigest()
        with self.assertRaisesRegex(export.ExportError, "plan hash"):
            export._probe(plan, {0: ("INVALID", failure, bind("failure"))})


if __name__ == "__main__":
    unittest.main()
