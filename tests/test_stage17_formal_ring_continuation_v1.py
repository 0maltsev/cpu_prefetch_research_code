"""D240 bounded synthetic declaration tests; no stand or execution authority."""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_formal_ring_continuation_v1 as contract
import stage17_formal_ring_plan_v1 as ring
from test_stage17_formal_plan_v2 import archived_fixture


def parent_fixture():
    """Software geometry only; never claim these are the pinned original bytes."""
    p = archived_fixture('Q16a')
    p['source_revision'] = contract.PARENT_SOURCE
    p['minimum_observations_per_series'] = 100000
    for item in p['captures']:
        c = item['capture']; c['minimum_observations_per_series'] = 100000
        for phase in c['budget']['phases']:
            phase.update(producer_attempt_limit=100002, consumer_poll_limit=100002)
        for capacity in item['resources']['phase_capacity']:
            for key in capacity: capacity[key] = 100002
        item['execution_budget'].update(publication_memory_bytes=20_000_000,
            memory_bytes=40_000_000, max_output_bytes=100_000_000)
        source = dict(path='/proc/meminfo', byte_capacity=4096, chunk_bytes=4096,
                      max_data_reads=2, requested=[True]*6)
        item['monitoring']['environment_sources'].append(source)
        item['monitoring']['environment_sources'] += [dict(source, path='/sys/fs/cgroup/cpu-prefetch-old/'+name)
                                                    for name in sorted(contract.CPUSET_FILES)]
    p['budget'].update(memory_bytes=5*1024**3, max_output_bytes=708*100_000_000+1_000_000)
    p['storage'].update(analysis_capture_workspace_bytes=100_000_000, archive_staging_bytes=100_000_000)
    return p


def continuation_fixture(parent=None):
    """Actual /3 shape for Python/C++ fixtures; fresh IDs, original numeric seeds."""
    old = parent_fixture() if parent is None else parent
    p = copy.deepcopy(old)
    p.update(schema_version=contract.VERSION, plan_id='synthetic-continuation', source_revision='b'*40,
             warmup_namespace='continuation-warmup', measurement_namespace='continuation-measurement')
    p['captures'] = p['captures'][177:]
    for ordinal, item in enumerate(p['captures']):
        for part in ('capture','resources','monitoring'): item[part]['ordinal'] = ordinal
        for phase in ('warmup','measurement'):
            identity=item['capture'][phase]
            # Replace first letter, preserving exact byte and LP width.
            identity.update(run_id=('X' if phase=='warmup' else 'Y')+identity['run_id'][1:],
                            seed_id='continuation-'+identity['seed_id'], namespace_id=p[phase+'_namespace'])
        item['capture']['arena_seed'] = copy.deepcopy(item['capture']['measurement'])
    def binding(name, digest, size=1):return dict(path='/fixture/'+name, size_bytes=size, sha256=digest)
    p['continuation'] = dict(policy_id=contract.POLICY,
        parent_plan=binding('original-plan.json',contract.PARENT_SHA256,contract.PARENT_SIZE),
        failed_family_receipt=binding('failure.json',contract.FAILURE_SHA256,contract.FAILURE_SIZE),
        accepted_prefix_manifest=binding('prefix.json','c'*64),compatibility_manifest=binding('compatibility.json','d'*64),
        reused_contexts=[0,1,2],remaining_contexts=list(range(3,12)),original_first_ordinal=177,
        failed_original_ordinal=177,seed_policy=contract.SEED_POLICY,monitor_path_replacements=[],future_retries=0)
    return p


class ContinuationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=parent_fixture();cls.prototype=continuation_fixture(cls.parent)

    def test_exact_531_and_parent_comparison_no_projection(self):
        p=copy.deepcopy(self.prototype);before=copy.deepcopy(p)
        result=contract.validate_plan(p)
        contract._compare_parent(p,self.parent)
        self.assertEqual(len(result.captures),531)
        self.assertEqual([p['captures'][i*59]['capture']['context_ordinal'] for i in range(9)],list(range(3,12)))
        self.assertFalse(result.execution_authority);self.assertEqual(p,before)
        self.assertEqual(p['captures'][0]['capture']['measurement']['seed_hex'],self.parent['captures'][177]['capture']['measurement']['seed_hex'])

    def test_exact_coverage_and_incident_negatives(self):
        mutants=(lambda p:p['captures'].pop(), lambda p:p['captures'].append(copy.deepcopy(p['captures'][-1])),
            lambda p:p['captures'][0]['capture'].update(context_ordinal=0),
            lambda p:p['captures'][0]['capture'].update(ordinal=177),
            lambda p:p['captures'][0]['capture'].update(repetition_ordinal=1),
            lambda p:p['continuation']['parent_plan'].update(sha256='0'*64),
            lambda p:p['continuation']['failed_family_receipt'].update(sha256='0'*64),
            lambda p:p['continuation'].update(future_retries=1),
            lambda p:p['continuation'].update(reused_contexts=[0,1]),
            lambda p:p['continuation'].update(remaining_contexts=list(range(2,11))),
            lambda p:p['continuation'].pop('compatibility_manifest'),
            lambda p:p['continuation'].pop('accepted_prefix_manifest'),
            lambda p:p.update(measurement_ns=2_000_000_000),
            lambda p:p.update(minimum_observations_per_series=99999),
            lambda p:p.update(source_revision=contract.PARENT_SOURCE))
        for mutate in mutants:
            p=copy.deepcopy(self.prototype);mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(contract.ContractError):contract.validate_plan(p)

    def test_old_versions_remain_strict(self):
        ring._validate_plan(self.parent,archived=True)
        with self.assertRaises(contract.ContractError):ring._validate_plan(self.prototype,archived=True)
        p=copy.deepcopy(self.prototype);p['schema_version']='cpu-prefetch-stage17-formal-ring-plan/2';p.pop('continuation')
        with self.assertRaises(contract.ContractError):ring._validate_plan(p,archived=True)

    def test_parent_science_seed_identity_and_bounds_are_immutable(self):
        mutants=(lambda p:p['captures'][0]['capture']['measurement'].update(seed_hex='f'*64),
            lambda p:p['captures'][0]['capture']['warmup'].update(run_id=self.parent['captures'][0]['capture']['warmup']['run_id']),
            lambda p:p['captures'][0]['capture']['geometry'].update(capacity=16),
            lambda p:p['captures'][0]['execution_budget'].update(watchdog_ns=123),
            lambda p:p['budget'].update(watchdog_ns=1),
            lambda p:p['storage'].update(program_scope_sha256='e'*64),
            lambda p:p['captures'][0]['monitoring']['environment_sources'][0].update(byte_capacity=1))
        for mutate in mutants:
            p=copy.deepcopy(self.prototype);mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(contract.ContractError):contract._compare_parent(p,self.parent)

    def test_exact_cpuset_relocation_only(self):
        p=copy.deepcopy(self.prototype)
        changes=[dict(original_path='/sys/fs/cgroup/cpu-prefetch-old/'+name,
                      continuation_path='/sys/fs/cgroup/cpu-prefetch-new/'+name) for name in sorted(contract.CPUSET_FILES)]
        p['continuation']['monitor_path_replacements']=changes
        mapping={r['original_path']:r['continuation_path'] for r in changes}
        for item in p['captures']:
            for source in item['monitoring']['environment_sources']:source['path']=mapping.get(source['path'],source['path'])
        contract.validate_plan(p);contract._compare_parent(p,self.parent)
        for mutate in (lambda q:q['continuation']['monitor_path_replacements'].pop(),
                       lambda q:q['continuation']['monitor_path_replacements'][0].update(continuation_path='/etc/passwd'),
                       lambda q:q['captures'][0]['monitoring']['environment_sources'][0].update(path='/proc/uptime')):
            q=copy.deepcopy(p);mutate(q)
            with self.subTest(mutate=mutate),self.assertRaises(contract.ContractError):contract._compare_parent(q,self.parent)

    def test_actual_original_byte_gate_no_object_or_wrong_bytes(self):
        for value in (self.parent,b'{}'):
            with self.subTest(value=type(value)),self.assertRaises(contract.ContractError):contract.validate_parent(self.prototype,value)

    def test_finite_budget_and_canonical_paths(self):
        for mutate in (lambda p:p['captures'][0]['execution_budget'].update(max_output_bytes=1),
                       lambda p:p['budget'].update(watchdog_ns=1),
                       lambda p:p['budget'].update(max_output_bytes=2**64),
                       lambda p:p['continuation']['accepted_prefix_manifest'].update(path='/a/../b'),
                       lambda p:p['captures'][0]['capture'].update(measurement_ns=1e9)):
            p=copy.deepcopy(self.prototype);mutate(p)
            with self.subTest(mutate=mutate),self.assertRaises(contract.ContractError):contract.validate_plan(p)


if __name__=='__main__':
    unittest.main()
