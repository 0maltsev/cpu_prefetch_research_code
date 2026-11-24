"""D260 exact suffix coverage and immutable prospective design; synthetic only."""
import copy
import dataclasses
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_service_continuation_v1 as current
import stage17_formal_service_daycap_v1 as original
from test_stage17_formal_service_daycap_v1 import select_repetitions
from test_stage17_formal_plan_v2 import archived_fixture


def parent_fixture():
    result = select_repetitions(archived_fixture('Q16b'), 2)
    result['source_revision'] = current.PARENT_SOURCE
    return result


def continuation_fixture(parent):
    result = copy.deepcopy(parent)
    result.update(schema_version=current.VERSION, source_revision='b'*40,
        plan_id='synthetic-service-continuation', warmup_namespace='new-warmup', measurement_namespace='new-measurement')
    result['captures'] = result['captures'][17:]
    for ordinal, item in enumerate(result['captures']):
        for part in ('capture', 'resources', 'monitoring'):
            item[part]['ordinal'] = ordinal
        for phase in ('warmup', 'measurement'):
            identity = item['capture'][phase]
            identity.update(run_id=('X' if phase == 'warmup' else 'Y')+identity['run_id'][1:],
                seed_id='new-'+identity['seed_id'], namespace_id=result[phase+'_namespace'])
        item['capture']['arena_seed'] = copy.deepcopy(item['capture']['measurement'])
        linked = item['capture']['linked_order']
        if linked is not None:
            linked.update(seed_id='new-'+linked['seed_id'], namespace_id='new-node-order')
    def binding(name, digest, size=100):
        return dict(path='/synthetic/'+name, size_bytes=size, sha256=digest)
    result['continuation'] = dict(policy_id=current.POLICY,
        parent_plan=binding('parent.json', current.PARENT_SHA256, current.PARENT_SIZE),
        failed_family_receipt=binding('failure.json', current.FAILURE_SHA256, current.FAILURE_SIZE),
        accepted_prefix_manifest=binding('prefix.json', 'c'*64),
        compatibility_manifest=binding('compatibility.json', 'd'*64),
        reused_capture_ordinals=list(range(17)), original_first_ordinal=17,
        original_total_captures=120, remaining_capture_count=103,
        seed_policy=current.SEED_POLICY, monitor_path_replacements=[], future_retries=0)
    return result


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = parent_fixture()
        cls.plan = continuation_fixture(cls.parent)

    def test_exact_103_from_original17_with_odd_first_repetition(self):
        before = copy.deepcopy(self.plan)
        extent = current.validate_plan(self.plan)
        current._compare_parent(self.plan, self.parent)
        self.assertEqual(len(extent.captures), 103)
        self.assertFalse(extent.execution_authority)
        self.assertEqual(self.plan, before)
        first, last = (self.plan['captures'][i]['capture'] for i in (0, -1))
        self.assertEqual((first['ordinal'], first['cell_ordinal'], first['repetition_ordinal']), (0, 14, 1))
        self.assertEqual((last['ordinal'], last['cell_ordinal'], last['repetition_ordinal']), (102, 59, 1))
        old = [c['capture']['cell_ordinal'] for c in self.parent['captures'][:17]]
        new = [c['capture']['cell_ordinal'] for c in self.plan['captures']]
        self.assertEqual({cell:(old+new).count(cell) for cell in range(60)}, {cell:2 for cell in range(60)})

    def test_retains_full_finite_original_per_capture_bounds(self):
        extent = current.validate_plan(self.plan)
        old = original.validate_plan(self.parent)
        self.assertEqual(extent.captures, tuple(dataclasses.replace(c, ordinal=i)
            for i, c in enumerate(old.captures[17:])))
        self.assertEqual(extent.declared, old.declared)
        self.assertLess(extent.required_watchdog_ns, old.required_watchdog_ns)
        self.assertEqual(extent.required_free_disk_bytes, old.required_free_disk_bytes)

    def test_historical_service_versions_do_not_accept_suffix(self):
        original.validate_plan(self.parent)
        with self.assertRaises(current.ContractError):
            original.validate_plan(self.plan)
        for version in ('cpu-prefetch-stage17-formal-service-plan/1',
                        'cpu-prefetch-stage17-formal-service-plan/2', original.VERSION):
            p = copy.deepcopy(self.plan);p['schema_version'] = version
            with self.subTest(version=version), self.assertRaises(current.ContractError):
                current.validate_plan(p)

    def test_no_missing_duplicate_extra_or_shifted_capture(self):
        for mutate in (lambda p:p['captures'].pop(),
                       lambda p:p['captures'].append(copy.deepcopy(p['captures'][-1])),
                       lambda p:p['captures'][0]['capture'].update(repetition_ordinal=0),
                       lambda p:p['captures'][0]['capture'].update(cell_ordinal=8),
                       lambda p:p['captures'][0]['capture'].update(ordinal=17)):
            p = copy.deepcopy(self.plan);mutate(p)
            with self.subTest(mutate=mutate), self.assertRaises(current.ContractError):
                current.validate_plan(p)

    def test_incident_bindings_and_prefix_are_closed(self):
        for mutate in (lambda p:p['continuation']['parent_plan'].update(sha256='0'*64),
                       lambda p:p['continuation']['failed_family_receipt'].update(size_bytes=1083),
                       lambda p:p['continuation'].update(original_first_ordinal=16),
                       lambda p:p['continuation'].update(reused_capture_ordinals=list(range(16))),
                       lambda p:p['continuation'].update(future_retries=1),
                       lambda p:p['continuation'].pop('accepted_prefix_manifest'),
                       lambda p:p['continuation'].pop('compatibility_manifest'),
                       lambda p:p['continuation']['accepted_prefix_manifest'].update(path='/a/../b'),
                       lambda p:p.update(source_revision=current.PARENT_SOURCE)):
            p = copy.deepcopy(self.plan);mutate(p)
            with self.subTest(mutate=mutate), self.assertRaises(current.ContractError):
                current.validate_plan(p)

    def test_parent_comparison_rejects_new_science_or_identity_reuse(self):
        for mutate in (lambda p:p['captures'][0]['capture']['measurement'].update(seed_hex='f'*64),
                       lambda p:p['captures'][0]['capture'].update(warmup_ns=1),
                       lambda p:p['captures'][0]['capture']['geometry'].update(capacity=16),
                       lambda p:p['captures'][0]['execution_budget'].update(setup_ns=1),
                       lambda p:p['budget'].update(watchdog_ns=1),
                       lambda p:p['storage'].update(program_scope_sha256='f'*64),
                       lambda p:p['captures'][0]['capture']['warmup'].update(run_id=self.parent['captures'][0]['capture']['warmup']['run_id'])):
            p = copy.deepcopy(self.plan);mutate(p)
            with self.subTest(mutate=mutate), self.assertRaises(current.ContractError):
                current._compare_parent(p, self.parent)

    def test_wrong_parent_bytes_never_authorize(self):
        for value in (self.parent, b'{}', original.plan_bytes(self.parent)):
            with self.subTest(kind=type(value)), self.assertRaises(current.ContractError):
                current.validate_parent(self.plan, value)

    def test_node_order_numeric_seed_preserved_with_fresh_identity(self):
        ordinal = next(i for i, row in enumerate(self.plan['captures'])
                       if row['capture']['linked_order'] is not None)
        for mutate in (lambda linked:linked.update(seed_hex='0'*64),
                       lambda linked:linked.update(seed_id=self.parent['captures'][17+ordinal]['capture']['linked_order']['seed_id']),
                       lambda linked:linked.update(namespace_id=self.parent['warmup_namespace'])):
            p = copy.deepcopy(self.plan)
            mutate(p['captures'][ordinal]['capture']['linked_order'])
            with self.subTest(mutate=mutate), self.assertRaises(current.ContractError):
                current._compare_parent(p, self.parent)

    def test_real_103_budget_and_storage_limits_are_checked(self):
        for mutate in (lambda p:p['budget'].update(watchdog_ns=24*3600*10**9+1),
                       lambda p:p['captures'][0]['execution_budget'].update(max_output_bytes=1),
                       lambda p:p['storage'].update(archive_quota_bytes=1),
                       lambda p:p['captures'][0]['capture'].update(measurement_ns=2*10**9)):
            p = copy.deepcopy(self.plan);mutate(p)
            with self.subTest(mutate=mutate), self.assertRaises(current.ContractError):
                current.validate_plan(p)


if __name__ == '__main__':
    unittest.main()
