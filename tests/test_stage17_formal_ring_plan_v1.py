"""Software-only prospective family fixtures; no measured platform values."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_ring_plan_v1 as contract


def plan_fixture():
    captures = []
    for context, (state, placement, working_set) in enumerate(contract.CONTEXTS):
        far = placement == "FAR"
        for repetition in range(59):
            ordinal = context * 59 + repetition
            warmup = {"run_id": f"W{ordinal:04}", "seed_id": f"SW{ordinal:04}",
                      "namespace_id": "formal-warmup", "seed_hex": f"{ordinal*2:064x}"}
            measurement = {"run_id": f"M{ordinal:04}", "seed_id": f"SM{ordinal:04}",
                           "namespace_id": "formal-measurement", "seed_hex": f"{ordinal*2+1:064x}"}
            bounds = {"producer_attempt_limit": 10, "consumer_poll_limit": 10, "drain_ns": 1_000_000_000}
            capture = {"schema_version": "cpu-prefetch-stage17-formal-ring-capture/1",
                       "method_id": contract.METHOD, "package": "R0", "ordinal": ordinal,
                       "context_ordinal": context, "repetition_ordinal": repetition,
                       "hardware_state": state, "placement": placement, "working_set_class": working_set,
                       "warmup_ns": 5_000_000_000, "measurement_ns": 1_000_000_000,
                       "minimum_observations_per_series": 2,
                       "geometry": {"capacity": 8, "cache_line_bytes": 64, "base_page_bytes": 4096,
                                    "producer_cpu": 0, "consumer_cpu": 8 if far else 1,
                                    "producer_node": 0, "consumer_node": 1 if far else 0, "shared_node": 0},
                       "warmup": warmup, "measurement": measurement, "arena_seed": copy.deepcopy(measurement),
                       "seed_use": "ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS",
                       "budget": {"phases": [bounds, copy.deepcopy(bounds)], "barrier_poll_limit": 1000,
                                  "memory_bytes": 200000}}
            def stack(cpu, node):
                return {"bytes": 4096, "verified_base_page_bytes": 4096, "owner_cpu": cpu, "requested_node": node}
            capacity = {k: 10 for k in ("producer_primary_rows", "consumer_primary_rows", "producer_demand_rows", "consumer_demand_rows")}
            resources = {"ordinal": ordinal, "workers": {"producer_stack": stack(0, 0), "consumer_stack": stack(8 if far else 1, 1 if far else 0)},
                         "controller_stack": stack(2, 0), "core_bytes": 4096, "monitor_bytes": 4096,
                         "total_mapping_bytes": 200000, "region_bytes": [4096]*7,
                         "tls_module_capacity": 4, "thread_stat_bytes": 4096, "thread_status_bytes": 4096,
                         "thread_affinity_words": 4, "initial_consumer_state": 17,
                         "phase_capacity": [capacity, copy.deepcopy(capacity)]}
            limits = {k: None for k in ("minor_faults", "major_faults", "voluntary_switches", "involuntary_switches")}
            monitoring = {"ordinal": ordinal, "during_first_page": [0]*7, "during_page_count": [1]*7,
                          "during_offset_ticks": [0, 0], "observer_wait_poll_limit": 1000, "control_region_index": 0,
                          "counter_limits": [[copy.deepcopy(limits) for _ in range(2)] for _ in range(2)],
                          "hardware_identity": {"family": 6, "model": 62}, "environment_sources": []}
            budget = {"setup_ns": 1_000_000_000, "publication_ns": 1_000_000_000, "cleanup_ns": 1_000_000_000,
                      "watchdog_ns": 11_000_000_000, "publication_memory_bytes": 100000, "other_memory_bytes": 100000,
                      "memory_bytes": 400000, "metadata_output_bytes": 10000, "max_output_bytes": 20000}
            captures.append(dict(capture=capture, resources=resources, monitoring=monitoring, execution_budget=budget))
    output = 708*20000 + 1000000
    return {"schema_version": contract.VERSION, "plan_id": "software-plan", "protocol_version": "2.0.0-pre.3",
            "action_id": "Q16a", "method_id": contract.METHOD, "source_revision": "a"*40, "clean_source": True,
            "stand_id": "synthetic-stand", "repetitions_per_context": 59, "measurement_ns": 1_000_000_000,
            "minimum_observations_per_series": 2, "warmup_namespace": "formal-warmup", "measurement_namespace": "formal-measurement",
            "custody_policy_id": contract.CUSTODY, "captures": captures,
            "budget": {"setup_ns": 1_000_000_000, "cleanup_ns": 1_000_000_000,
                       "watchdog_ns": 708*11_000_000_000 + 2_000_000_000, "controller_memory_bytes": 20000000,
                       "memory_bytes": 20400000, "metadata_output_bytes": 1000000, "max_output_bytes": output,
                       "analysis_scratch_bytes": 1000000, "disk_reserve_bytes": 1000000, "required_free_disk_bytes": output+2000000}}


class FormalRingPlanTest(unittest.TestCase):
    def setUp(self):
        self.plan = plan_fixture()

    def reject(self):
        with self.assertRaises(contract.ContractError):
            contract.validate_plan(self.plan)

    def test_complete_family_exact_codec_extent_and_sequential_budget(self):
        result = contract.validate_plan(self.plan)
        self.assertEqual(len(result.captures), 708)
        self.assertEqual(result.captures[0].raw_bytes, 2*10*(136+96+88+88))
        self.assertEqual(result.captures[0].largest_raw_copy_bytes, 1360)
        self.assertEqual(result.required_watchdog_ns, 708*11_000_000_000+2_000_000_000)
        self.assertEqual(result.peak_memory_bytes, 20400000)
        self.assertEqual(result.required_free_disk_bytes, 708*20000+3000000)
        self.assertFalse(result.execution_authority)

    def test_no_partial_or_added_runs(self):
        self.plan["captures"].pop(); self.reject()

    def test_minimum_59_frozen_runs(self):
        self.plan["repetitions_per_context"] = 58; self.reject()

    def test_wrong_method_cannot_relabel_historical_data(self):
        self.plan["method_id"] = "RING-D2-RUNTAIL-LTL95C95-v1"; self.reject()

    def test_no_duration_or_minimum_adaptation(self):
        self.plan["captures"][0]["capture"]["measurement_ns"] += 1; self.reject()

    def test_global_seed_and_run_identity_uniqueness(self):
        for field in ("run_id", "seed_id", "seed_hex"):
            with self.subTest(field=field):
                self.plan = plan_fixture()
                self.plan["captures"][1]["capture"]["warmup"][field] = self.plan["captures"][0]["capture"]["warmup"][field]
                self.reject()

    def test_wrong_cpu_or_node_geometry(self):
        self.plan["captures"][0]["resources"]["workers"]["consumer_stack"]["owner_cpu"] = 26; self.reject()

    def test_raw_capacity_and_copy_memory_cannot_be_omitted(self):
        self.plan["captures"][0]["execution_budget"]["publication_memory_bytes"] = 1359; self.reject()
        self.plan = plan_fixture()
        self.plan["captures"][0]["resources"]["phase_capacity"][0]["consumer_demand_rows"] = 9; self.reject()

    def test_warmup_drains_publication_and_cleanup_count_toward_watchdog(self):
        self.plan["captures"][0]["execution_budget"]["watchdog_ns"] -= 1; self.reject()

    def test_family_disk_includes_analysis_scratch_and_reserve(self):
        self.plan["budget"]["required_free_disk_bytes"] -= 1; self.reject()

    def test_unsigned_overflow_bool_and_outside_observation_rejected(self):
        self.plan["measurement_ns"] = (1 << 64)-1; self.reject()
        self.plan = plan_fixture(); self.plan["minimum_observations_per_series"] = True; self.reject()
        self.plan = plan_fixture(); self.plan["captures"][0]["monitoring"]["during_offset_ticks"][1] = 1_000_000_000_000; self.reject()

    def test_context_order_and_per_repetition_bounds_frozen(self):
        self.plan["captures"][0]["capture"]["context_ordinal"] = 1; self.reject()
        self.plan = plan_fixture(); self.plan["captures"][1]["monitoring"]["observer_wait_poll_limit"] += 1; self.reject()

    def test_integral_float_and_invalid_line_geometry_rejected(self):
        self.plan["captures"][0]["resources"]["thread_stat_bytes"] = 4096.0; self.reject()
        self.plan = plan_fixture(); self.plan["captures"][0]["capture"]["geometry"]["cache_line_bytes"] = 63; self.reject()

    def test_schema_end_anchor_cannot_accept_trailing_newline(self):
        for field in ("run_id", "seed_id", "namespace_id", "seed_hex"):
            with self.subTest(field=field):
                self.plan = plan_fixture()
                self.plan["captures"][0]["capture"]["warmup"][field] += "\n"
                self.reject()

    def test_scientific_minimum_is_not_an_observed_count(self):
        self.plan["captures"][0]["capture"]["observed_count"] = 100000; self.reject()


if __name__ == "__main__":
    unittest.main()
