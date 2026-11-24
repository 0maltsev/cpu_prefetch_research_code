"""Actual native description and parent-plan assembly; synthetic declarations."""
import argparse
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_plan_prepare_v1 as prepare
import stage17_formal_archive_runtime_v1 as runtime

ROOT = Path(__file__).resolve().parents[1]


def fixture(revision):
    blueprint = json.loads((ROOT / "config/stage17/d310-s180-blueprint-v1.json").read_bytes())
    rows = sorted(blueprint["captures"], key=lambda r:r["execution_ordinal"])
    captures = []
    raw = struct.pack(">4Q",1,2,2,3)
    for row in rows:
        geometry = row["requested_geometry"]
        context = (0 if row["placement"] == "NEAR" else 3) + ["L2_RESIDENT","LLC_RESIDENT","BEYOND_LLC"].index(row["working_set_class"])
        group = context * 3 + ["L025","L050","L075"].index(row["load_level"])
        def stack(cpu, node):
            return dict(bytes=8192,verified_base_page_bytes=4096,owner_cpu=cpu,requested_node=node)
        phases = [dict(producer_attempt_limit=4,consumer_poll_limit=2048,drain_duration_ticks=20_000_000,
            schedule_id=f"schedule-{group}-{phase}",source_origin_ticks=0,
            source_horizon_ticks=row["warmup_ns" if phase==0 else "measurement_ns"]*1000,offered_count=4,
            source_artifact=dict(artifact_id=f"source-{group}-{phase}",sha256=hashlib.sha256(raw).hexdigest()))
            for phase in range(2)]
        captures.append(dict(execution_ordinal=row["execution_ordinal"],cell_ordinal=row["cell_ordinal"],phases=phases,
            resources=dict(workers=dict(producer_stack=stack(geometry["producer_cpu"],geometry["producer_node"]),
                consumer_stack=stack(geometry["consumer_cpu"],geometry["consumer_node"])),controller_stack=stack(2,0),
                tls_module_capacity=8,thread_stat_bytes=4096,thread_status_bytes=4096,thread_affinity_words=4,
                initial_consumer_state=17,phase_capacity=[dict(producer_primary_rows=4,consumer_primary_rows=4) for _ in range(2)]),
            monitoring=dict(during_first_page=[0]*9,during_page_count=[1]*9,during_offset_ticks=[1,1],
                observer_wait_poll_limit=1_000_000,control_region_index=0,environment_sources=[],
                counter_limits=[[dict(minor_faults=None,major_faults=None,voluntary_switches=None,involuntary_switches=None)
                    for _ in range(2)] for _ in range(2)]),
            execution_budget=dict(watchdog_ns=7_000_000_000,archive_ns=100_000_000,max_output_bytes=1024**2,
                metadata_bytes=65536,barrier_poll_limit=5_000_000)))
    return dict(schema_version=prepare.SIZING,source_count_basis="EXACT_DECLARED_COUNTS",source_revision=revision,
        blueprint=blueprint,captures=captures,hardware=dict(identity=dict(family=6,model=62),
            prestate=[dict(cpu=cpu,value=0) for cpu in (0,1,8)],software_prefetch_mapping_id="X86-64-PREFETCHT0-ONLY-v1"),
        budget=dict(setup_ns=1_000_000_000,whole_plot_transition_ns=1_000_000_000,whole_plot_recovery_ns=60_000_000_000,
            finalization_ns=1_000_000_000,final_metadata_bytes=1024**2,entry_metadata_bytes=65536,
            memory_bytes=2*1024**3,max_output_bytes=1024**3),
        storage=dict(pilot_policy_id="D310-S180-LOSSLESS-STAND-PRIMARY-v1",approval_sha256=blueprint["approval"]["sha256"],
            program_id="synthetic-s180",program_scope_sha256="b"*64,implementation_profile_sha256="c"*64,
            archive_staging_bytes=1024**2,maximum_custody_receipt_bytes=131072))


class PreparationTests(unittest.TestCase):
    worker = None

    def setUp(self):
        raw = self.worker.read_bytes()
        self.image = runtime.ImageBinding(self.worker,len(raw),hashlib.sha256(raw).hexdigest())
        result = subprocess.run([str(self.worker),"--stage17-s180-runtime-identity-v1"],capture_output=True,check=True,timeout=30)
        self.plan = fixture(json.loads(result.stdout)["source_revision"])

    @staticmethod
    def deadline():
        return time.monotonic_ns()+60_000_000_000

    def test_actual_sealed_native_description_builds_complete_candidate_without_authority(self):
        plan, proof = prepare.prepare(self.plan,worker=self.image,deadline_ns=self.deadline())
        self.assertEqual(plan["schema_version"],prepare.PLAN)
        self.assertEqual(len(plan["captures"]),180)
        self.assertEqual(proof["plan_sha256"],prepare.sha(plan))
        self.assertTrue(all(len(row["expected_layout"]["region_bytes"])==9 for row in plan["captures"]))
        minima = proof["resource_minima"]
        self.assertEqual(minima["retained_source_vector_bytes"],36*4*8)
        self.assertEqual(minima["minimum_source_vector_limit_bytes"],36*4*8+4*8)
        self.assertEqual(minima["native_and_archive_process_count_upper"],4501)
        for key in ("launch_ready","execution_authority","signed_admission_verified","source_bytes_verified","phase18_authority"):
            self.assertIs(proof[key],False)

    def test_ceiling_sizing_accepts_explicitly_unknown_sources_but_cannot_be_collected(self):
        self.plan["source_count_basis"]="PROSPECTIVE_UPPER_CEILINGS"
        for entry in self.plan["captures"]:
            for phase in entry["phases"]: phase["source_artifact"]=None
        report = prepare.native_layouts(self.plan,worker=self.image,deadline_ns=self.deadline())
        self.assertEqual(report["source_count_basis"],"PROSPECTIVE_UPPER_CEILINGS")
        with self.assertRaises(prepare.PlanError): prepare.prepare(self.plan,worker=self.image,deadline_ns=self.deadline())

    def test_changed_pair_order_or_binary_and_inadequate_budget_reject(self):
        reordered = copy.deepcopy(self.plan)
        reordered["captures"].reverse()
        with self.assertRaises(prepare.PlanError): prepare.prepare(reordered,worker=self.image,deadline_ns=self.deadline())
        changed = copy.deepcopy(self.plan)
        changed["captures"][0]["phases"][0]["source_artifact"]["sha256"]="f"*64
        with self.assertRaises(prepare.PlanError): prepare.prepare(changed,worker=self.image,deadline_ns=self.deadline())
        with self.assertRaises(prepare.archive.ArchiveError):
            prepare.prepare(self.plan,worker=replace(self.image,sha256="f"*64),deadline_ns=self.deadline())
        self.plan["budget"]["memory_bytes"]=1
        with self.assertRaises(prepare.PlanError): prepare.prepare(self.plan,worker=self.image,deadline_ns=self.deadline())


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--worker",type=Path,required=True)
    args,rest=parser.parse_known_args()
    PreparationTests.worker=args.worker.resolve()
    unittest.main(argv=[__file__,*rest])
