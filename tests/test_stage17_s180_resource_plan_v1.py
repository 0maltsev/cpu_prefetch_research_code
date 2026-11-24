"""Prospective arithmetic against the real cold worker; no research sources.

The original retained control-plan metadata is a hash-pinned fixture, alongside
unchanged actual blueprint/identities. Participant observation fields are an
explicit software fixture. No qualification or research source is generated.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_resource_plan_v1 as resource_plan
import stage17_formal_archive_runtime_v1 as runtime

ERRORS=(resource_plan.archive.ArchiveError,ValueError)


class ResourceTests(unittest.TestCase):
    worker=None

    @classmethod
    def setUpClass(cls):
        identity=subprocess.run([str(cls.worker),'--stage17-s180-runtime-identity-v1'],
            capture_output=True,check=True,timeout=30)
        cls.revision=json.loads(identity.stdout)['source_revision']
        root=Path(__file__).resolve().parents[1]
        cls.blueprint=resource_plan.archive.parse_json((root/'config/stage17/d310-s180-blueprint-v1.json').read_bytes())
        cls.control=(root/'docs/evidence/stage17/PILOT-D326-RESOURCES-20261122-01/original-control-plan.json').read_bytes()
        cls.hardware=dict(read_only=True,hardware_writes=0,qualification_performed=False,
            base_page_bytes=4096,cache_line_bytes=64,synthetic_fixture=True,cpus=[dict(cpu=cpu,nodes=[node],
                vendor='GenuineIntel',family=6,model=62,msr_1a4_observed=0) for cpu,node in ((0,0),(1,0),(8,1))])
        raw=cls.worker.read_bytes()
        cls.image=runtime.ImageBinding(cls.worker,len(raw),hashlib.sha256(raw).hexdigest())
        cls.identities=resource_plan.identities.planned_identities(cls.blueprint)
        cls.packet=cls.make()
        cls.report=cls.describe(cls.packet)
        # Independent, deliberately pessimistic test bound. Real evidence
        # uses the pinned accepted Zstd1.5.7 compressBound instead.
        cls.bounded,cls.envelope=resource_plan.bound_packet(cls.packet,cls.report,compress_bound=lambda n:2*n+4096)
        cls.final_report=cls.describe(cls.bounded)

    @classmethod
    def make(cls,**changes):
        args=dict(blueprint=cls.blueprint,prospective_identities=cls.identities,historical_plan_bytes=cls.control,
            hardware_observation=cls.hardware,source_revision=cls.revision,
            requested_cpuset_prefix='/sys/fs/cgroup/SOFTWARE-S180/reserved',recovery_ns=60*10**9)
        args.update(changes)
        return resource_plan.make_ceiling_packet(**args)

    @classmethod
    def describe(cls,packet):
        return resource_plan.planning.native_layouts(packet,worker=cls.image,deadline_ns=time.monotonic_ns()+60*10**9)

    def test_real_cold_worker_accepts_complete_ceiling_packet_without_sources(self):
        self.assertEqual(len(self.final_report['captures']),180)
        self.assertEqual(self.packet['captures'][0]['cell_ordinal'],137)
        for row,entry in zip(sorted(self.blueprint['captures'],key=lambda r:r['execution_ordinal']),self.packet['captures']):
            for i,phase in enumerate(('warmup','measurement')):
                mean=Fraction(row['nominal_rate']['numerator'],row['nominal_rate']['denominator'])*Fraction(row[phase+'_ns'],10**9)
                expected=-(-2*mean.numerator//mean.denominator)
                self.assertEqual(entry['phases'][i]['offered_count'],expected)
                self.assertIsNone(entry['phases'][i]['source_artifact'])
        self.assertFalse(self.final_report['session_admission_performed'])
        with self.assertRaises(resource_plan.planning.PlanError):
            resource_plan.planning.prepare(self.bounded,worker=self.image,deadline_ns=time.monotonic_ns()+10**9)

    def test_original_controls_identity_and_observation_drift_reject(self):
        for field,value in (('historical_plan_bytes',self.control+b' '),('prospective_identities',{})):
            with self.subTest(field=field),self.assertRaises(ERRORS):self.make(**{field:value})
        for field,value in (('base_page_bytes',16384),('cache_line_bytes',128),('qualification_performed',True)):
            hw=copy.deepcopy(self.hardware);hw[field]=value
            with self.subTest(field=field),self.assertRaises(ERRORS):self.make(hardware_observation=hw)
        hw=copy.deepcopy(self.hardware);hw['cpus'][2]['nodes']=[0]
        with self.assertRaises(ERRORS):self.make(hardware_observation=hw)

    def test_all_monitor_paths_and_nine_regions_are_preserved(self):
        for entry in self.packet['captures']:
            self.assertEqual(entry['monitoring']['during_page_count'],[1]*9)
            self.assertEqual(entry['monitoring']['during_first_page'],[0]*9)
            self.assertNotIn('hardware_identity',entry['monitoring'])
            self.assertEqual(sum(s['path'].startswith('/sys/fs/cgroup/SOFTWARE-S180/reserved/cpuset.')
                for s in entry['monitoring']['environment_sources']),5)
            self.assertEqual([p['drain_duration_ticks'] for p in entry['phases']],[30*10**12]*2)

    def test_legacy_extra_monitor_field_fails_at_real_native_boundary(self):
        bad=copy.deepcopy(self.packet);bad['captures'][0]['monitoring']['hardware_identity']=dict(family=6,model=62)
        with self.assertRaises(resource_plan.planning.PlanError):self.describe(bad)

    def test_archive_extents_charge_actual_long_ids_and_shared_node_orders(self):
        for row,entry,bound in zip(sorted(self.blueprint['captures'],key=lambda r:r['execution_ordinal']),
                self.bounded['captures'],self.envelope['capture_bounds']):
            widths=[]
            for key in ('warmup_run_id','run_id'):
                prefix=((4+len(row[key].encode())+7)//8)*8
                widths.extend([prefix+120,prefix+80])
            self.assertEqual(bound['primary_row_bytes'],widths)
            self.assertEqual(bound['primary_stream_bytes'],[widths[i]*entry['phases'][i//2]['offered_count'] for i in range(4)])
            self.assertEqual(bound['node_order_bytes'],(row['requested_geometry']['capacity']+1)*8)
            self.assertGreater(bound['archive_upper_bytes'],bound['canonical_output_bytes'])
            self.assertEqual(bound['metadata']['region_count'],9)
        self.assertFalse(self.envelope['resource_admission_performed'])

    def test_report_drift_and_unapproved_compression_credit_reject(self):
        bad=copy.deepcopy(self.report);bad['sizing_plan_sha256']='f'*64
        with self.assertRaises(ERRORS):resource_plan.bound_packet(self.packet,bad,compress_bound=lambda n:n+1000)
        for bound in (lambda n:n-1,lambda n:True,lambda n:2**64):
            with self.assertRaises(ERRORS):resource_plan.bound_packet(self.packet,self.report,compress_bound=bound)

    def test_fresh_description_required_after_bounding(self):
        with self.assertRaises(ERRORS):resource_plan.process_envelope(self.bounded,self.report,self.envelope)
        result=resource_plan.process_envelope(self.bounded,self.final_report,self.envelope)
        self.assertGreater(result['conservative_total_bytes'],64*1024**3)
        self.assertLessEqual(result['native_minimum_plus_cold_heap_bytes'],64*1024**3)
        self.assertFalse(result['whole_process_tree_limits_verified'])
        self.assertEqual(result['schema_version'],'cpu-prefetch-stage17-s180-requested-process-envelope/2')
        self.assertEqual(result['stage_total_bytes']['analysis'],196*resource_plan.GIB)
        self.assertEqual(result['analysis_worker_count'],12)
        self.assertTrue(result['analysis_requires_owned_quiescence'])
        self.assertTrue(result['in_process_decode_limit_readback_required'])
        self.assertEqual(result['conservative_total_bytes'],max(result['stage_total_bytes'].values()))

    def test_budget_caps_fit_one_day_but_do_not_assert_measured_eta(self):
        result=resource_plan.time_envelope(self.bounded,self.final_report)
        self.assertEqual(result['total_declared_stage_caps_ns'],85681*10**9)
        self.assertEqual(result['remaining_window_margin_ns'],719*10**9)
        self.assertFalse(result['expected_elapsed_time_verified'])
        self.assertFalse(result['execution_authority'])
        bad=copy.deepcopy(self.bounded)
        for e in bad['captures']:e['execution_budget']['watchdog_ns']=86400*10**9
        report=copy.deepcopy(self.final_report);report['sizing_plan_sha256']=resource_plan.planning.sha(bad)
        with self.assertRaises(ERRORS):resource_plan.time_envelope(bad,report)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--worker',type=Path,required=True)
    args,rest=parser.parse_known_args();ResourceTests.worker=args.worker.resolve()
    unittest.main(argv=[__file__,*rest])
