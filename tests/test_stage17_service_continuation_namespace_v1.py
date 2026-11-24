"""Exact prospective seed exception; no stand, raw reads or registration."""
import copy
import hashlib
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_namespace_v1 as current
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class NamespaceTests(unittest.TestCase):
    def setUp(self):
        self.parent=parent_fixture()
        self.parent.update(warmup_namespace='PARENT-WARM',measurement_namespace='PARENT-MEASURE')
        for i,item in enumerate(self.parent['captures']):
            c=item['capture']
            for phase,letter in [('warmup','W'),('measurement','M')]:
                c[phase].update(run_id=f'B27{letter}{i:08d}',seed_id=f'PARENT-{letter}-SEED-{i:04d}',namespace_id=self.parent[phase+'_namespace'])
            c['arena_seed']=copy.deepcopy(c['measurement'])
            if c['linked_order'] is not None:c['linked_order'].update(seed_id=f'PARENT-NODE-SEED-{i:04d}',namespace_id='PARENT-NODE',seed_hex=f'{80000+i:064x}')
        self.plan=continuation_fixture(self.parent)
        raw=current.base.canonical(self.parent)
        digest=hashlib.sha256(raw).hexdigest()
        # Only the immutable real-incident hash boundary is synthetic; real
        # schemas,103 identity extraction and every matching rule execute.
        with mock.patch.object(current.contract,'validate_parent',return_value=current.contract.validate_plan(self.plan)):
            with mock.patch.object(current.base,'PLAN_SHA',digest):
                self.matcher=current.Matcher(self.plan,raw)
                self.old_registry=current.base.planned_identities(self.parent,raw)
        self.seed=self.plan['captures'][0]['capture']['measurement']['seed_hex']

    def inspect(self,value):return self.matcher.inspect(current.base.canonical(value))[0]

    def test_only_exact_parent_and_full_original_registry_allow_existing_numeric_seeds(self):
        self.assertEqual(self.inspect(self.parent),[])
        self.assertEqual(self.inspect(self.old_registry),[])
        self.assertEqual(self.inspect(dict(parent=self.parent)),[])
        self.assertEqual(self.inspect(dict(serialized=current.base.canonical(self.parent).decode())),[])
        self.assertTrue(self.matcher.authorized_documents)

    def test_bare_seed_hex_decimal_integer_and_alternative_encoding_are_collisions(self):
        for value in (self.seed,int(self.seed,16),str(int(self.seed,16)),'0x'+self.seed.upper()):
            with self.subTest(value=value):self.assertIn('numeric_seed:'+self.seed,self.inspect(dict(seed=value)))

    def test_whole_parent_does_not_waive_an_actual_seed_outside_it(self):
        self.assertIn('numeric_seed:'+self.seed,self.inspect(dict(prospective=self.parent,executed_seed=self.seed)))

    def test_partial_or_changed_parent_and_registry_cannot_claim_exception(self):
        for value in (copy.deepcopy(self.parent),copy.deepcopy(self.old_registry)):
            if 'captures' in value:value['captures'].pop()
            else:value['phase_identities'].pop()
            self.assertIn('numeric_seed:'+self.seed,self.inspect(value))

    def test_modified_parent_metadata_does_not_inherit_prospective_permission(self):
        value=copy.deepcopy(self.parent);value['plan_id']+='-different'
        self.assertIn('numeric_seed:'+self.seed,self.inspect(value))

    def test_fresh_textual_identity_collision_is_never_waived(self):
        run=self.plan['captures'][0]['capture']['measurement']['run_id']
        self.assertIn(run,self.inspect(dict(run_id=run)))
        encoded='{"run_id":"'+''.join('\\u%04x'%ord(c) for c in run)+'"}'
        self.assertIn(run,self.matcher.inspect(encoded.encode())[0])

    def test_counts_are_real_suffix_only_and_original_base_is_unchanged(self):
        self.assertEqual(len(self.matcher.document['phase_identities']),206)
        self.assertEqual(len(self.matcher.document['linked_order_identities']),48)
        self.assertEqual(len(self.matcher.numeric),254)
        self.assertEqual(current.base.STAND_EXCLUSIONS,('local-authoring-cpuprefetchv5-26/daycap-collection-preparation-1',))


if __name__=='__main__':unittest.main()
