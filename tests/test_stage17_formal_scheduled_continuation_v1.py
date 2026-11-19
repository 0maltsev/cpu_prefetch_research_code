"""D288 exact94 pending settings and immutable parent inputs; software only."""
import copy
import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_scheduled_continuation_v1 as current
import stage17_formal_scheduled_descriptive_v1 as original
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


def parent_fixture():
    result=plan_fixture();result['source_revision']=current.PARENT_SOURCE
    result['budget']['metadata_output_bytes']=16*1024**2
    result['budget']['max_output_bytes']+=16*1024**2
    result['budget']['watchdog_ns']=47_820_000_000_000
    return result


def continuation_fixture(parent):
    result=copy.deepcopy(parent)
    result.update(schema_version=current.VERSION,method_id=current.METHOD,source_revision='b'*40,
        plan_id='software-only-q16c-continuation',warmup_namespace='new-warmup',measurement_namespace='new-measurement')
    result['captures']=result['captures'][86:]
    for ordinal,item in enumerate(result['captures']):
        for part in ('capture','resources','monitoring'):item[part]['ordinal']=ordinal
        for phase in ('warmup','measurement'):
            identity=item['capture'][phase]
            identity.update(run_id=('X' if phase=='warmup' else 'Y')+identity['run_id'][1:],seed_id='new-'+identity['seed_id'],namespace_id=result[phase+'_namespace'])
        item['capture']['arena_seed']=copy.deepcopy(item['capture']['measurement'])
        linked=item['capture']['linked_order']
        if linked is not None:linked.update(seed_id='new-'+linked['seed_id'],namespace_id='new-node-order')
    def binding(name,sha,size=100):return dict(path='/synthetic/'+name,size_bytes=size,sha256=sha)
    result['continuation']=dict(policy_id=current.POLICY,parent_plan=binding('parent.json',current.PARENT_SHA256,current.PARENT_SIZE),
        failed_family_receipt=binding('failure.json',current.FAILURE_SHA256,current.FAILURE_SIZE),
        accepted_prefix_manifest=binding('prefix.json','c'*64),compatibility_manifest=binding('compatibility.json','d'*64),
        reused_capture_ordinals=list(range(86)),original_first_ordinal=86,original_total_captures=180,
        remaining_capture_count=94,seed_policy=current.SEED_POLICY,monitor_path_replacements=[],future_retries=0)
    result['platform_control']=dict(schema_version='cpu-prefetch-q16c-platform-control/1',
        control_path='/proc/sys/vm/compact_unevictable_allowed',requested_value=0,
        observation_policy='BEFORE_AUTHORIZATION_AFTER_CHECKPOINT-v1',witness_transport='READ_ONLY_ROOT_LEASE_FD-v1',metadata_output_bytes=2*1024**2)
    sizes=[s['offered_count']*8 for row in result['captures'] for s in row['capture']['schedules']]
    t=result['source_transport'];t.update(descriptor_count=188,source_bytes=sum(sizes),owned_vector_bytes=sum(sizes),
        loader_transient_bytes=max(sizes)+8192,maximum_source_memory_bytes=2*sum(sizes)+max(sizes)+8192+t['metadata_bytes'])
    result['budget']['watchdog_ns']=24_860_000_000_000
    return result


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=parent_fixture();cls.plan=continuation_fixture(cls.parent)

    def test_exact_original86_to179_and_identical_per_capture_limits(self):
        before=copy.deepcopy(self.plan)
        extent=current.validate_plan(self.plan);current._compare_parent(self.plan,self.parent)
        old=original.validate_plan(self.parent)
        self.assertEqual(len(extent.captures),94)
        self.assertEqual(extent.captures,tuple(dataclasses.replace(e,ordinal=i) for i,e in enumerate(old.captures[86:])))
        self.assertEqual(self.plan,before)
        self.assertFalse(extent.execution_authority)
        self.assertEqual([r['capture']['cell_ordinal'] for r in self.plan['captures']],
                         [r['capture']['cell_ordinal'] for r in self.parent['captures'][86:]])

    def test_old_full_matrix_contract_remains_strict_and_unchanged(self):
        original.validate_plan(self.parent)
        with self.assertRaises(current.ContractError):original.validate_plan(self.plan)
        bad=copy.deepcopy(self.plan);bad['schema_version']=original.VERSION
        with self.assertRaises(current.ContractError):current.validate_plan(bad)

    def test_no_missing_duplicate_shifted_or_additional_capture(self):
        for change in (lambda p:p['captures'].pop(),lambda p:p['captures'].append(copy.deepcopy(p['captures'][0])),
            lambda p:p['captures'][0]['capture'].update(ordinal=86),lambda p:p['captures'][0]['capture'].update(cell_ordinal=0),
            lambda p:p['captures'][0]['capture'].update(load_level='L025')):
            bad=copy.deepcopy(self.plan);change(bad)
            with self.subTest(change=change),self.assertRaises(current.ContractError):current.validate_plan(bad)

    def test_exact_incident_prefix_and_no_retry_authority(self):
        for field,value in [('original_first_ordinal',85),('remaining_capture_count',93),('future_retries',1),
            ('reused_capture_ordinals',list(range(85))),('policy_id','other')]:
            bad=copy.deepcopy(self.plan);bad['continuation'][field]=value
            with self.subTest(field=field),self.assertRaises(current.ContractError):current.validate_plan(bad)
        for field in ('parent_plan','failed_family_receipt'):
            bad=copy.deepcopy(self.plan);bad['continuation'][field]['sha256']='0'*64
            with self.assertRaises(current.ContractError):current.validate_plan(bad)
        bad=copy.deepcopy(self.plan);bad['source_revision']=current.PARENT_SOURCE
        with self.assertRaises(current.ContractError):current.validate_plan(bad)

    def test_control_request_is_prospective_and_has_no_invented_readback(self):
        for field,value in [('requested_value',1),('control_path','/other'),('metadata_output_bytes',1),
            ('observed_value',0),('observation_policy','SKIP_ON_ERROR')]:
            bad=copy.deepcopy(self.plan);bad['platform_control'][field]=value
            with self.subTest(field=field),self.assertRaises(current.ContractError):current.validate_plan(bad)

    def test_source_transport_and_whole_family_bounds_are_finite(self):
        for field in ('source_bytes','owned_vector_bytes','descriptor_count','maximum_source_memory_bytes'):
            bad=copy.deepcopy(self.plan);bad['source_transport'][field]-=1
            with self.subTest(field=field),self.assertRaises(current.ContractError):current.validate_plan(bad)
        for seconds in (24859,24861):
            bad=copy.deepcopy(self.plan);bad['budget']['watchdog_ns']=seconds*10**9
            with self.assertRaises(current.ContractError):current.validate_plan(bad)

    def test_parent_comparison_rejects_adaptive_science_or_old_identity(self):
        for change in (lambda p:p['captures'][0]['capture'].update(geometry=self.parent['captures'][0]['capture']['geometry']),
            lambda p:p['captures'][0]['capture']['measurement'].update(seed_hex='f'*64),
            lambda p:p['captures'][0]['capture']['schedules'][0].update(offered_count=7),
            lambda p:p['captures'][0]['capture']['warmup'].update(run_id=self.parent['captures'][86]['capture']['warmup']['run_id']),
            lambda p:p['captures'][0]['execution_budget'].update(watchdog_ns=999999999999)):
            bad=copy.deepcopy(self.plan);change(bad)
            with self.subTest(change=change),self.assertRaises(current.ContractError):current._compare_parent(bad,self.parent)

    def test_parent_bytes_must_match_real_incident_not_a_synthetic_declaration(self):
        with self.assertRaises(current.ContractError):current.validate_parent(self.plan,json.dumps(self.parent).encode())

    @unittest.skipUnless((current.ROOT/'build/stage17-q16c-d282/prospective-plan.json').is_file(),
                         'original preserved incident metadata unavailable')
    def test_actual_preserved_incident_plan_keeps_all_pending_numeric_seeds_and_schedules(self):
        raw=(current.ROOT/'build/stage17-q16c-d282/prospective-plan.json').read_bytes()
        parent=json.loads(raw);plan=continuation_fixture(parent)
        extent=current.validate_parent(plan,raw)
        self.assertEqual(len(extent.captures),94)
        for old,new in zip(parent['captures'][86:],plan['captures'],strict=True):
            self.assertEqual(old['capture']['schedules'],new['capture']['schedules'])
            for phase in ('warmup','measurement'):
                self.assertEqual(old['capture'][phase]['seed_hex'],new['capture'][phase]['seed_hex'])


if __name__=='__main__':unittest.main()
