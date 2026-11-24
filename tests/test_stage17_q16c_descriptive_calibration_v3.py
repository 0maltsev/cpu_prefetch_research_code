"""Mixed-family composition: real report parsing/hash/count/control rules.

Synthetic plans replace the incident-authentication seam only. No raw science or
stand observation is credited by these software fixtures.
"""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_descriptive_calibration_v3 as current
from test_stage17_formal_scheduled_continuation_v1 import parent_fixture,continuation_fixture
from test_stage17_q16c_descriptive_calibration_v2 import reports


class CompositionTests(unittest.TestCase):
    def bind(self,name,value):
        raw=value if type(value) is bytes else current.window.canonical(value)
        path=self.root/name;path.write_bytes(raw)
        return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.parent=parent_fixture();self.plan=continuation_fixture(self.parent)
        self.old=reports(self.parent,full_ordinal=17)[:86];self.new=reports(self.plan,full_ordinal=0)
        for row in self.new:row['report_binding']['artifact_id']='new-'+row['report_binding']['artifact_id']
        self.parent_raw=current.window.canonical(self.parent)
        self.complete=self.bind('complete.json',dict(status='ALL_SELECTED_VALID',kind='PREFIX86'))
        self.prefix=dict(schema_version=current.PREFIX_SCHEMA,parent_plan=self.plan['continuation']['parent_plan'],
            original_source_revision=current.continuation.PARENT_SOURCE,
            failed_family_receipt_sha256=current.continuation.FAILURE_SHA256,analysis_completion=self.complete,
            reused_capture_ordinals=list(range(86)),reports=[r['report_binding'] for r in self.old],
            compaction_control='UNRECORDED',all_required_reports_valid=True,
            scientific_method=current.continuation.COLLECTOR_METHOD,execution_authority=False,phase18_authority=False)
        self.plan['continuation']['accepted_prefix_manifest']=self.bind('prefix.json',self.prefix)
        self.bound=self.bind('plan.json',current.previous.archive.canonical(self.plan));self.request='d'*64
        observations=[]
        for ordinal in range(94):
            for index,moment in enumerate(current.MOMENTS):
                observations.append(dict(schema_version='cpu-prefetch-q16c-compaction-observation/1',
                    capture_ordinal=ordinal,moment=moment,request_sha256=self.request,plan_sha256=self.bound['sha256'],
                    checkpoint=None if index==0 else dict(file_name=f'formal-capture-{ordinal}-final-checkpoint.json',
                        size_bytes=100,sha256='f'*64),observed_monotonic_ns=len(observations)+1,
                    scientific_validity='NOT_ASSESSED',execution_authority=False,
                    control=dict(requested_value=0,observed_value=0,verified=True,witness_sha256='e'*64)))
        self.platform=dict(schema_version='cpu-prefetch-q16c-platform-observations/1',request_sha256=self.request,
            plan_sha256=self.bound['sha256'],observation_count=188,observations=observations,
            scientific_validity='NOT_ASSESSED',execution_authority=False)
        self.platform_binding=self.bind('platform.json',self.platform)
        def synthetic_incident(plan,raw):
            self.assertEqual(raw,self.parent_raw)
            current.continuation.validate_plan(plan)
            current.previous.contract.validate_plan(self.parent)
            current.continuation._compare_parent(plan,self.parent)
        self.patch=patch.object(current.continuation,'validate_parent',side_effect=synthetic_incident)
        self.patch.start();self.addCleanup(self.patch.stop)

    def evaluate(self):
        return current.evaluate(self.parent_raw,self.plan,self.old,self.new,plan_binding=self.bound,
            request_sha256=self.request,platform_binding=self.platform_binding)

    def test_full_matrix_retains_original_local_ordinals_runs_counts_and_distinct_platform_strata(self):
        result=self.evaluate();self.assertEqual(result['status'],'DESCRIPTIVE_COMPLETE')
        rows=result['run_sources'];self.assertEqual(len(rows),180)
        self.assertEqual([r['original_ordinal'] for r in rows],list(range(180)))
        self.assertEqual(rows[86]['capture_ordinal'],0)
        self.assertEqual(rows[86]['cell_ordinal'],self.parent['captures'][86]['capture']['cell_ordinal'])
        self.assertNotEqual(rows[0]['family_plan_sha256'],rows[86]['family_plan_sha256'])
        self.assertEqual(rows[85]['platform'],dict(regime='UNRECORDED',requested_value=None,observed_value=None))
        self.assertEqual(rows[86]['platform']['regime'],'VERIFIED_ZERO')
        self.assertFalse(result['homogeneous_platform_evidence'])
        self.assertIsNone(result['confidence_claim']);self.assertIsNone(result['final_scale_selection'])
        self.assertFalse(result['inferential_validity_established']);self.assertFalse(result['execution_authority'])
        self.assertFalse(result['phase18_authority'])

    def test_valid_full_remains_valid_but_fails_separate_gate_in_both_families(self):
        result=self.evaluate()
        self.assertEqual(result['observed_zero_loss']['measurement'],dict(zero_loss_gate='FAIL',full_bearing_original_ordinals=[17,86]))
        self.assertEqual(result['run_sources'][17]['validity'],'VALID')
        self.assertEqual(result['run_sources'][86]['phases'][1]['counts']['full'],1)

    def test_missing_invalid_duplicate_and_relabelled_prefix_reports_stop(self):
        saved=copy.deepcopy(self.old)
        for mode in ('missing','invalid','duplicate','relabel','hash'):
            self.old=copy.deepcopy(saved)
            if mode=='missing':self.old.pop()
            elif mode=='invalid':self.old[0]['validity']='INVALID'
            elif mode=='duplicate':self.old[-1]=copy.deepcopy(self.old[0])
            elif mode=='relabel':self.old[0]['capture_ordinal']=86
            else:self.old[0]['report_binding']['sha256']='0'*64
            with self.subTest(mode=mode),self.assertRaises(current.previous.Error):self.evaluate()

    def test_missing_wrong_regime_clock_witness_or_checkpoint_cannot_claim_verified_zero(self):
        saved=copy.deepcopy(self.platform)
        for mode in ('missing','one','bool','clock','witness','checkpoint','request'):
            self.platform=copy.deepcopy(saved)
            observation=self.platform['observations'][1]
            if mode=='missing':self.platform['observations'].pop()
            elif mode=='one':observation['control']['observed_value']=1
            elif mode=='bool':observation['control']['observed_value']=False
            elif mode=='clock':observation['observed_monotonic_ns']=1
            elif mode=='witness':observation['control']['witness_sha256']='b'*64
            elif mode=='checkpoint':observation['checkpoint']['file_name']='formal-capture-1-final-checkpoint.json'
            else:observation['request_sha256']='a'*64
            self.platform_binding=self.bind('platform.json',self.platform)
            with self.subTest(mode=mode),self.assertRaises(current.previous.Error):self.evaluate()

    def test_prefix_manifest_and_original_report_bytes_cannot_be_substituted(self):
        self.prefix['compaction_control']='VERIFIED_ZERO'
        self.plan['continuation']['accepted_prefix_manifest']=self.bind('prefix.json',self.prefix)
        self.bound=self.bind('plan.json',current.previous.archive.canonical(self.plan))
        with self.assertRaises(current.previous.Error):self.evaluate()

    def test_actual_incident_gate_remains_required_outside_synthetic_seam(self):
        self.patch.stop()
        with self.assertRaises(current.continuation.ContractError):self.evaluate()

    def test_prefix_publication_requires_actual_complete_reports_and_preserves_original_bindings(self):
        parent=self.bind('parent.json',self.parent_raw)
        report_bindings=[self.bind(f'capture-{i}.json',row['report_utf8_bytes']) for i,row in enumerate(self.old)]
        completion=dict(schema_version='cpu-prefetch-stage17-q16c-selected-analysis-completion/1',
            status='ALL_SELECTED_VALID',kind='PREFIX86',all_workers_reaped=True,execution_authority=False,
            phase18_authority=False,plan_binding=parent,elapsed_ns=1,reports=report_bindings)
        bound=self.bind('complete-prefix.json',completion)
        # The real immutable incident check remains tested above. This one
        # substitutes only its known byte identity for the software fixture.
        with patch.object(current.continuation,'PARENT_SIZE',len(self.parent_raw)),patch.object(
                current.continuation,'PARENT_SHA256',hashlib.sha256(self.parent_raw).hexdigest()):
            manifest=current.prefix_manifest(self.parent_raw,self.old,plan_binding=parent,analysis_completion=bound)
            self.assertEqual(manifest['reports'],[r['report_binding'] for r in self.old])
            self.assertEqual(manifest['compaction_control'],'UNRECORDED')
            Path(report_bindings[0]['path']).write_bytes(b'corruption')
            with self.assertRaises(ValueError):current.prefix_manifest(self.parent_raw,self.old,plan_binding=parent,analysis_completion=bound)


if __name__=='__main__':unittest.main()
