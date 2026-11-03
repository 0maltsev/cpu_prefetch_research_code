"""Synthetic contract tests only; no stand access, signing or measurements."""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import pathlib
import unittest

from jsonschema import Draft202012Validator

import stage17_discovery_contract_v1 as contract


def binding(name: str) -> dict:
    return {"artifact_id": name, "size_bytes": 64,
            "sha256": hashlib.sha256(name.encode()).hexdigest()}


def fixture() -> dict:
    """All geometry, timing margins and budgets below are synthetic controls."""
    captures = []
    for state in ("H0", "H1"):
        for placement in ("NEAR", "FAR"):
            for working_set in ("L2_RESIDENT", "LLC_RESIDENT", "BEYOND_LLC"):
                context = len(captures) // 3
                for horizon in (100_000_000, 1_000_000_000, 5_000_000_000):
                    ordinal = len(captures)
                    identities = {}
                    for offset, phase in enumerate(("warmup", "measurement")):
                        identities[phase] = {
                            "run_id": f"synthetic-{phase}-{ordinal}",
                            "seed_id": f"synthetic-seed-{phase}-{ordinal}",
                            "seed_hex": f"{ordinal * 2 + offset:064x}",
                            "namespace_id": f"diagnostic-{phase}",
                        }
                    captures.append({
                        "ordinal": ordinal, "context_ordinal": context,
                        "hardware_state": state, "placement": placement,
                        "working_set_class": working_set, "warmup_ns": 5_000_000_000,
                        "measurement_ns": horizon, **identities,
                        "arena_seed": copy.deepcopy(identities["measurement"]),
                        "seed_use": "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
                        "geometry": {"producer_cpu": 0,
                                     "consumer_cpu": 1 if placement == "NEAR" else 8,
                                     "producer_node": 0,
                                     "consumer_node": 0 if placement == "NEAR" else 1,
                                     "shared_node": 0, "capacity": 512,
                                     "cache_line_bytes": 64, "base_page_bytes": 4096},
                        "budget": {"setup_ns": 1_000_000, "drain_ns": 1_000_000,
                                   "publication_ns": 3_000_000, "cleanup_ns": 4_000_000,
                                   "watchdog_ns": 5_010_000_000 + horizon,
                                   "warmup_attempt_capacity": 200_000,
                                   "measurement_attempt_capacity": 200_000,
                                   "drain_attempt_capacity": 513,
                                   "barrier_poll_limit": 1_000_000,
                                   "memory_bytes": 128 * 1024 * 1024,
                                   "retained_output_bytes": 64 * 1024 * 1024,
                                   "metadata_output_bytes": 1024 * 1024,
                                   "max_output_bytes": 65 * 1024 * 1024},
                    })
    return {
        "schema_version": contract.PLAN_VERSION, "protocol_version": "2.0.0-pre.3",
        "design_id": "D178-Q16A-SETUP-DISCOVERY-v1", "plan_id": "synthetic-plan",
        "stand_id": "synthetic-stand", "source_revision": "a" * 40, "clean_source": True,
        **{name: binding(name) for name in ("release", "stand", "qualification",
                                           "resource_plan", "monitoring_plan", "namespace_registry")},
        "dependencies": [{"input_id": f"S17-EXT-{index:03d}",
                          "resolution": binding(f"resolution-{index}")} for index in range(1, 7)],
        "warmup_namespace": "diagnostic-warmup", "measurement_namespace": "diagnostic-measurement",
        "minimum_observations": {name: 100_000 for name in (
            "producer_demand", "consumer_demand", "producer_issue", "consumer_issue")},
        "captures": captures,
        "budget": {"setup_ns": 1_000_000_000, "cleanup_ns": 2_000_000_000,
                   "watchdog_ns": 256_560_000_000, "controller_memory_bytes": 1024 * 1024,
                   "memory_budget_bytes": 129 * 1024 * 1024,
                   "metadata_output_bytes": 1024 * 1024,
                   "output_budget_bytes": 2341 * 1024 * 1024,
                   "custody_domains": [{"domain_id": "synthetic-a", "copies": 1,
                                       "budget_bytes": 2341 * 1024 * 1024},
                                      {"domain_id": "synthetic-b", "copies": 2,
                                       "budget_bytes": 4682 * 1024 * 1024}]},
        "diagnostic_only": True, "execution_authority": False,
        "phase18_authority": False, "retries": 0,
    }


def request(plan: contract.DiscoveryPlan) -> dict:
    return {"schema_version": contract.REQUEST_VERSION, "request_id": "synthetic-request",
            "plan_binding": {"artifact_id": plan.plan_id, "size_bytes": len(plan.canonical_bytes),
                             "sha256": plan.sha256},
            "diagnostic_only": True, "execution_authority": False, "phase18_authority": False}


class DiscoveryContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).resolve().parents[1] / contract.SCHEMA_PATH
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        cls.schema = Draft202012Validator(schema)

    def reject(self, document, message=None):
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_plan(document)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_exact_grid_and_independent_duration_budget(self):
        document = fixture()
        self.schema.validate(document)
        plan = contract.validate_plan(document)
        self.assertEqual(len(plan.captures), 36)
        self.assertEqual(plan.unavoidable_duration_ns, 253_200_000_000)
        self.assertEqual(plan.required_watchdog_ns, 256_560_000_000)
        self.assertEqual(plan.peak_memory_bytes, 135_266_304)
        self.assertEqual(plan.maximum_output_bytes, 2_454_716_416)
        self.assertFalse(plan.execution_authority)

    def test_request_exact_binding_and_no_authority(self):
        document = fixture()
        plan = contract.validate_plan(document)
        value = request(plan)
        self.schema.validate(value)
        accepted = contract.validate_request(value, document)
        self.assertEqual(accepted.plan, plan)
        self.assertFalse(accepted.execution_authority)
        for field, bad in (("artifact_id", "other"), ("size_bytes", 1), ("sha256", "0" * 64)):
            mutated = copy.deepcopy(value)
            mutated["plan_binding"][field] = bad
            with self.subTest(field=field), self.assertRaises(contract.ContractError):
                contract.validate_request(mutated, document)
        document["stand_id"] = "different-stand"
        with self.assertRaises(contract.ContractError):
            contract.validate_request(value, document)

    def test_canonical_bytes_are_order_independent_and_frozen(self):
        document = fixture()
        plan = contract.validate_plan(document)
        reordered = dict(reversed(tuple(document.items())))
        self.assertEqual(contract.validate_plan(reordered).canonical_bytes, plan.canonical_bytes)
        self.assertEqual(hashlib.sha256(plan.canonical_bytes).hexdigest(), plan.sha256)
        self.assertFalse(plan.canonical_bytes.endswith(b"\n"))
        document["captures"][0]["geometry"]["capacity"] = 1
        self.assertEqual(plan.captures[0].geometry.capacity, 512)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.captures[0].budget.memory_bytes = 1

    def test_180_second_watchdog_and_one_ns_underbudget_rejected(self):
        for seconds in (180_000_000_000, 253_200_000_000, 256_559_999_999):
            document = fixture()
            document["budget"]["watchdog_ns"] = seconds
            self.reject(document, "watchdog_ns")
        document = fixture()
        document["captures"][0]["budget"]["watchdog_ns"] -= 1
        self.reject(document, "declared stages")

    def test_missing_extra_reordered_duplicate_captures_rejected(self):
        for mutate in (lambda x: x.pop(), lambda x: x.append(copy.deepcopy(x[0])),
                       lambda x: x.reverse(), lambda x: x.__setitem__(1, copy.deepcopy(x[0]))):
            document = fixture()
            mutate(document["captures"])
            self.reject(document)

    def test_fixed_design_fields_and_minima(self):
        for field, bad in (("warmup_ns", 10_000_000), ("measurement_ns", 200_000_000),
                           ("context_ordinal", 1), ("hardware_state", "H1"),
                           ("working_set_class", "LLC_RESIDENT"), ("placement", "FAR")):
            document = fixture()
            document["captures"][0][field] = bad
            self.reject(document, field)
        for sequence in ("producer_demand", "consumer_demand", "producer_issue", "consumer_issue"):
            document = fixture()
            document["minimum_observations"][sequence] -= 1
            self.reject(document, sequence)

    def test_identity_seed_and_namespace_reuse_rejected(self):
        for field in ("run_id", "seed_id", "seed_hex", "namespace_id"):
            document = fixture()
            document["captures"][0]["measurement"][field] = document["captures"][0]["warmup"][field]
            self.reject(document)
        document = fixture()
        document["measurement_namespace"] = document["warmup_namespace"]
        self.reject(document, "disjoint")
        document = fixture()
        document["captures"][1]["warmup"]["seed_hex"] = document["captures"][0]["measurement"]["seed_hex"]
        self.reject(document, "reused")
        document = fixture()
        document["captures"][0]["warmup"]["seed_hex"] = "0" * 16
        self.reject(document, "seed_hex")

    def test_one_explicit_arena_seed_and_reserved_warmup(self):
        document = fixture()
        plan = contract.validate_plan(document)
        self.assertEqual(plan.captures[0].arena_seed, plan.captures[0].measurement)
        self.assertNotEqual(plan.captures[0].arena_seed.seed_hex, plan.captures[0].warmup.seed_hex)
        for field, value in (("seed_use", "SEPARATE_WARMUP_PERMUTATION"),
                             ("arena_seed", copy.deepcopy(document["captures"][0]["warmup"]))):
            mutated = copy.deepcopy(document)
            mutated["captures"][0][field] = value
            self.reject(mutated)
        document["captures"][0]["arena_seed"]["seed_hex"] = "f" * 64
        self.reject(document, "explicitly equal")

    def test_explicit_placement_and_geometry_required(self):
        for name in ("producer_cpu", "consumer_cpu", "producer_node", "consumer_node",
                     "shared_node", "capacity", "cache_line_bytes", "base_page_bytes"):
            document = fixture()
            del document["captures"][0]["geometry"][name]
            self.reject(document, "geometry")
        for field, bad in (("consumer_cpu", 0), ("consumer_node", 1), ("shared_node", 1),
                           ("capacity", 3), ("cache_line_bytes", 0), ("base_page_bytes", 32)):
            document = fixture()
            document["captures"][0]["geometry"][field] = bad
            self.reject(document, "geometry")
        document = fixture()
        document["captures"][9]["geometry"]["consumer_node"] = 0
        self.reject(document, "placement")
        document = fixture()
        document["captures"][18]["geometry"]["capacity"] *= 2
        self.reject(document, "paired")

    def test_release_and_dependency_bindings_required(self):
        for field in ("release", "stand", "qualification", "resource_plan", "monitoring_plan", "namespace_registry"):
            document = fixture()
            del document[field]
            self.reject(document)
            document = fixture()
            document[field]["sha256"] = "not-a-hash"
            self.reject(document, field)
        for mutate in (lambda d: d.__setitem__("clean_source", False),
                       lambda d: d.__setitem__("source_revision", "HEAD"),
                       lambda d: d["dependencies"].pop(),
                       lambda d: d["dependencies"].reverse()):
            document = fixture()
            mutate(document)
            self.reject(document)

    def test_resource_insufficiency_rejected(self):
        for field in ("memory_budget_bytes", "output_budget_bytes"):
            document = fixture()
            document["budget"][field] -= 1
            self.reject(document, field)
        document = fixture()
        document["budget"]["custody_domains"][1]["budget_bytes"] -= 1
        self.reject(document, "custody")
        for field in ("memory_bytes", "max_output_bytes"):
            document = fixture()
            document["captures"][0]["budget"][field] = 1
            self.reject(document, field)
        document = fixture()
        document["budget"]["custody_domains"].append(copy.deepcopy(document["budget"]["custody_domains"][0]))
        self.reject(document, "duplicate custody")
        document = fixture()
        document["captures"][0]["budget"]["memory_bytes"] = 64 * 1024 * 1024
        self.reject(document, "arena plus retained")

    def test_uint64_overflow_in_durations_memory_output_copies_and_geometry(self):
        for field in ("setup_ns", "drain_ns", "watchdog_ns", "memory_bytes", "max_output_bytes"):
            document = fixture()
            document["captures"][0]["budget"][field] = contract.MAX_U64
            self.reject(document, "integer")
        document = fixture()
        document["budget"]["custody_domains"][0]["copies"] = contract.MAX_U64
        self.reject(document, "integer")
        document = fixture()
        document["captures"][0]["geometry"]["capacity"] = 1 << 63
        self.reject(document, "record_arena_bytes")

    def test_bool_float_negative_and_unbounded_values_are_not_integers(self):
        for bad in (True, 1.0, -1, 0, contract.MAX_U64 + 1, float("inf")):
            document = fixture()
            document["captures"][0]["budget"]["warmup_attempt_capacity"] = bad
            self.reject(document, "warmup_attempt_capacity")
        document = fixture()
        document["captures"][0]["ordinal"] = False
        self.reject(document, "ordinal")

    def test_no_extra_fields_retry_or_execution_authority(self):
        for key, value in (("retries", 1), ("execution_authority", True),
                           ("phase18_authority", True), ("diagnostic_only", False),
                           ("command", "anything")):
            document = fixture()
            document[key] = value
            self.reject(document)
            self.assertFalse(self.schema.is_valid(document))
        document = fixture()
        value = request(contract.validate_plan(document))
        value["execution_authority"] = True
        with self.assertRaises(contract.ContractError):
            contract.validate_request(value, document)
        self.assertFalse(self.schema.is_valid(value))


if __name__ == "__main__":
    unittest.main()
