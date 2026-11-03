"""Pure synthetic D207 contract/selector regressions; no capture or authority."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator

import check_stage17_discovery_contract as legacy_fixture
import stage17_discovery_contract_v1 as legacy_contract
import stage17_discovery_contract_v2 as contract
import stage17_q16a_discovery_v1 as legacy_selector
import stage17_q16a_discovery_v2 as selector


def fixture() -> dict:
    """Synthetic declarations only: never a qualified layout/resource plan.

    Large declared buffers are not allocated or filled. Consumers may replace
    observation dataclasses for phase-only tests without weakening this plan.
    """
    document = legacy_fixture.fixture()
    document.update(schema_version=contract.PLAN_VERSION, design_id=selector.DESIGN_ID,
                    custody_policy_id=contract.CUSTODY_POLICY_ID,
                    amendment_id=contract.AMENDMENT_ID)
    for ordinal, capture in enumerate(document["captures"]):
        duration = (1_000_000_000, 2_000_000_000, 5_000_000_000)[ordinal % 3]
        capture["measurement_ns"] = duration
        budget = capture["budget"]
        budget.update(warmup_attempt_capacity=30_000_000,
                      measurement_attempt_capacity=30_000_000,
                      watchdog_ns=5_010_000_000 + duration,
                      memory_bytes=32 * 1024**3,
                      retained_output_bytes=16 * 1024**3,
                      max_output_bytes=16 * 1024**3 + 1024**2)
    budget = document["budget"]
    budget["watchdog_ns"] = (budget["setup_ns"] + budget["cleanup_ns"]
                             + sum(c["budget"]["watchdog_ns"] for c in document["captures"]))
    budget["memory_budget_bytes"] = 32 * 1024**3 + budget["controller_memory_bytes"]
    budget["output_budget_bytes"] = (budget["metadata_output_bytes"]
                                    + sum(c["budget"]["max_output_bytes"]
                                          for c in document["captures"]))
    budget["custody_domains"] = [{"domain_id": "synthetic-stand-primary", "copies": 1,
                                  "budget_bytes": budget["output_budget_bytes"]}]
    return document


def request(plan: contract.DiscoveryPlan) -> dict:
    """Exact canonical binding for signed-lifecycle test callers."""
    document = legacy_fixture.request(plan)
    document["schema_version"] = contract.REQUEST_VERSION
    return document


def observations() -> list[selector.DiagnosticCapture]:
    return [selector.DiagnosticCapture(key, key.duration_ns,
                                      selector.ObservationCounts(100_001, 100_001, 100_000, 100_000),
                                      selector.StopReason.fixed_deadline)
            for key in selector.required_captures()]


class DiscoveryV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = pathlib.Path(__file__).resolve().parents[1]
        schema = json.loads((cls.root / contract.SCHEMA_PATH).read_text())
        Draft202012Validator.check_schema(schema)
        cls.schema = Draft202012Validator(schema)

    def reject(self, document, *, schema_too=False):
        with self.assertRaises(contract.ContractError):
            contract.validate_plan(document)
        if schema_too:
            self.assertFalse(self.schema.is_valid(document))

    def test_fixture_exact_grid_and_independent_budget_arithmetic(self):
        document = fixture()
        self.schema.validate(document)
        plan = contract.validate_plan(document)
        self.assertEqual(len(plan.captures), 36)
        self.assertEqual(plan.unavoidable_duration_ns, 276_000_000_000)
        self.assertEqual(plan.required_watchdog_ns, 279_360_000_000)
        self.assertEqual(plan.peak_memory_bytes, 34_360_786_944)
        self.assertEqual(plan.maximum_output_bytes, 618_514_087_936)
        self.assertEqual(plan.custody_policy_id, "EXT007-RAW-NONE-STAND-PRIMARY-v1")
        self.assertEqual(plan.amendment_id, "AMEND-2.0.0-pre.3-EXT007-DISCOVERY-DURATION-v2")
        self.assertFalse(plan.execution_authority)
        for context in range(12):
            self.assertEqual([c.measurement_ns for c in plan.captures[context * 3:context * 3 + 3]],
                             [1_000_000_000, 2_000_000_000, 5_000_000_000])

    def test_v1_bytes_and_legacy_contract_unchanged(self):
        hashes = {
            "tools/stage17_q16a_discovery_v1.py": "5af8082cc9c76c5d2f73aa465719946ee7bd9b7df73fbd549b0f95b4bd995750",
            "tools/stage17_discovery_contract_v1.py": "f8e4fb5ccb2570cd4c45dec45c319e5720454f41fbd9a393019278b41e168b82",
            "config/schemas/stage17-discovery-plan-v1.schema.json": "ffe49f08a8b51b1ecbc40760dd8855b46937bd3628baf9faec7f481a4d3fa175",
        }
        for path, expected in hashes.items():
            self.assertEqual(hashlib.sha256((self.root / path).read_bytes()).hexdigest(), expected)
        old = legacy_fixture.fixture()
        legacy_contract.validate_plan(old)
        self.reject(old, schema_too=True)
        with self.assertRaises(legacy_contract.ContractError):
            legacy_contract.validate_plan(fixture())
        self.assertEqual(legacy_selector.DURATIONS_NS, (100_000_000, 1_000_000_000, 5_000_000_000))

    def test_old_grid_rejected_under_v2_identity(self):
        document = fixture()
        for index, capture in enumerate(document["captures"]):
            capture["measurement_ns"] = (100_000_000, 1_000_000_000, 5_000_000_000)[index % 3]
        self.reject(document, schema_too=True)

    def test_exact_warmup_and_both_attempt_capacities(self):
        for name in ("warmup_attempt_capacity", "measurement_attempt_capacity"):
            for bad in (29_999_999, 30_000_001, True, 30_000_000.0):
                with self.subTest(name=name, bad=bad):
                    document = fixture()
                    document["captures"][0]["budget"][name] = bad
                    self.reject(document, schema_too=type(bad) is not float)
        document = fixture()
        document["captures"][0]["warmup_ns"] -= 1
        self.reject(document, schema_too=True)

    def test_exact_policy_amendment_and_authority(self):
        for key, value in (("custody_policy_id", "two-copies"), ("amendment_id", "old"),
                           ("execution_authority", True), ("phase18_authority", True),
                           ("diagnostic_only", False), ("clean_source", False), ("retries", 1)):
            document = fixture()
            document[key] = value
            with self.subTest(key=key):
                self.reject(document, schema_too=True)
        for key in ("custody_policy_id", "amendment_id"):
            document = fixture()
            del document[key]
            self.reject(document, schema_too=True)

    def test_exact_one_domain_one_copy(self):
        for count in (0, 2):
            document = fixture()
            document["budget"]["custody_domains"] *= count
            self.reject(document, schema_too=True)
        for copies in (0, 2, True, 1.0):
            document = fixture()
            document["budget"]["custody_domains"][0]["copies"] = copies
            self.reject(document, schema_too=type(copies) is not float)
        document = fixture()
        document["budget"]["custody_domains"][0]["budget_bytes"] -= 1
        self.reject(document)

    def test_request_exact_binding_versions_and_authority(self):
        document = fixture()
        plan = contract.validate_plan(document)
        value = request(plan)
        self.schema.validate(value)
        self.assertEqual(contract.validate_request(value, document).plan, plan)
        for name, bad in (("artifact_id", "other"), ("size_bytes", 1), ("sha256", "0" * 64)):
            mutated = copy.deepcopy(value)
            mutated["plan_binding"][name] = bad
            with self.subTest(name=name), self.assertRaises(contract.ContractError):
                contract.validate_request(mutated, document)
        for name, bad in (("schema_version", legacy_contract.REQUEST_VERSION),
                          ("execution_authority", True), ("phase18_authority", True)):
            mutated = copy.deepcopy(value)
            mutated[name] = bad
            self.assertFalse(self.schema.is_valid(mutated))
            with self.assertRaises(contract.ContractError):
                contract.validate_request(mutated, document)

    def test_exact_prefix_identity_and_dependencies(self):
        for change in ("missing", "extra", "order", "run_id", "seed", "namespace", "dependency"):
            document = fixture()
            captures = document["captures"]
            if change == "missing":
                captures.pop()
            elif change == "extra":
                captures.append(copy.deepcopy(captures[-1]))
            elif change == "order":
                captures[0], captures[1] = captures[1], captures[0]
            elif change == "run_id":
                captures[1]["warmup"]["run_id"] = captures[0]["warmup"]["run_id"]
            elif change == "seed":
                captures[1]["warmup"]["seed_hex"] = captures[0]["warmup"]["seed_hex"]
            elif change == "namespace":
                document["warmup_namespace"] = document["measurement_namespace"]
            else:
                document["dependencies"][0]["input_id"] = "S17-EXT-006"
            with self.subTest(change=change):
                self.reject(document)

    def test_finite_budget_boundaries(self):
        for field in ("watchdog_ns", "memory_budget_bytes", "output_budget_bytes"):
            document = fixture()
            document["budget"][field] -= 1
            self.reject(document)
        document = fixture()
        document["captures"][0]["budget"]["watchdog_ns"] -= 1
        self.reject(document)
        document = fixture()
        document["budget"]["setup_ns"] = (1 << 64) - 1
        self.reject(document)

    def test_canonical_plan_and_immutable_result(self):
        document = fixture()
        plan = contract.validate_plan(document)
        self.assertEqual(plan.canonical_bytes, contract.validate_plan(
            dict(reversed(tuple(document.items())))).canonical_bytes)
        self.assertEqual(plan.sha256, hashlib.sha256(plan.canonical_bytes).hexdigest())
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.execution_authority = True


class DiscoveryV2SelectorTests(unittest.TestCase):
    def test_legacy_observation_types_new_grid_shortest_common(self):
        self.assertIs(selector.DiagnosticCapture, legacy_selector.DiagnosticCapture)
        self.assertIs(selector.CaptureKey, legacy_selector.CaptureKey)
        result = selector.select_duration(observations())
        self.assertEqual(result.state, selector.SelectionState.selected)
        self.assertEqual(result.selected_duration_ns, 1_000_000_000)
        self.assertEqual(result.eligible_durations_ns, (1_000_000_000, 2_000_000_000, 5_000_000_000))
        self.assertFalse(result.execution_authority)
        self.assertEqual(result.formal_runs_contributed, 0)

    def test_each_of_four_sequences_and_all_contexts_required(self):
        for context in range(12):
            for name in selector.ObservationCounts.__dataclass_fields__:
                captures = observations()
                values = dict(producer_demand=100_001, consumer_demand=100_001,
                              producer_issue=100_000, consumer_issue=100_000)
                values[name] = 99_999
                if name.endswith("demand"):
                    values[name.replace("demand", "issue")] = 99_998
                index = context * 3
                captures[index] = dataclasses.replace(captures[index], counts=selector.ObservationCounts(**values))
                with self.subTest(context=context, sequence=name):
                    self.assertEqual(selector.select_duration(captures).selected_duration_ns, 2_000_000_000)

    def test_low_counts_unresolved_no_extension(self):
        captures = [dataclasses.replace(c, counts=selector.ObservationCounts(2, 2, 1, 1))
                    for c in observations()]
        result = selector.select_duration(captures)
        self.assertEqual(result.state, selector.SelectionState.unresolved)
        self.assertIsNone(result.selected_duration_ns)

    def test_measurement_capacity_is_insufficient_not_mandatory(self):
        captures = observations()
        captures[0] = dataclasses.replace(captures[0], elapsed_ns=1,
                                          stop_reason=selector.StopReason.trace_capacity)
        result = selector.select_duration(captures)
        self.assertEqual(result.state, selector.SelectionState.selected)
        self.assertEqual(result.selected_duration_ns, 2_000_000_000)
        self.assertEqual(selector.select_duration(captures[:1]).state, selector.SelectionState.incomplete)

    def test_warmup_capacity_or_other_mandatory_failure_stops(self):
        # The raw/session adapter classifies warmup exhaustion as mandatory;
        # this selector receives that evidence, never infers a phase from counts.
        for reason, failures in ((selector.StopReason.mandatory_failure, ()),
                                 (selector.StopReason.trace_capacity, ("warmup trace capacity",)),
                                 (selector.StopReason.fixed_deadline, ("monitoring outside window",))):
            capture = dataclasses.replace(observations()[0], stop_reason=reason,
                                          elapsed_ns=None, validity_failures=failures)
            self.assertEqual(selector.select_duration([capture]).state, selector.SelectionState.stopped)
            with self.assertRaises(ValueError):
                selector.select_duration([capture, observations()[1]])

    def test_old_grid_retry_reorder_and_early_deadline_rejected(self):
        base = observations()
        mutants = [base + [base[-1]], [base[1], base[0]],
                   [dataclasses.replace(base[0], key=selector.CaptureKey(0, 100_000_000))],
                   [dataclasses.replace(base[0], elapsed_ns=999_999_999)],
                   [dataclasses.replace(base[0], elapsed_ns=None)]]
        for mutant in mutants:
            with self.assertRaises(ValueError):
                selector.select_duration(mutant)
        self.assertEqual(selector.select_duration(base[:-1]).state, selector.SelectionState.incomplete)

    def test_counts_strict_and_issue_reconciliation(self):
        for bad in (-1, True, 100_001.0):
            capture = dataclasses.replace(observations()[0],
                                          counts=selector.ObservationCounts(bad, 100_001, 100_000, 100_000))
            with self.assertRaises(ValueError):
                selector.select_duration([capture])
        capture = dataclasses.replace(observations()[0], counts=selector.ObservationCounts(3, 3, 3, 2))
        with self.assertRaises(ValueError):
            selector.select_duration([capture])


if __name__ == "__main__":
    unittest.main()
