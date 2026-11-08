"""Local authoring checks only; no qualification or experiment claims."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

import prepare_launch_inputs as p


class InputsTests(unittest.TestCase):
    def test_hardware_comes_from_new_qualification_and_preserves_original_state(self):
        original = dict(mapping_id='actual-fixture-mapping', prestate=[dict(cpu=0, complete_value_hex='0'*16)],
                        q15_w_result_sha256='a'*64)
        mapping = {k: copy.deepcopy(original[k]) for k in ('mapping_id', 'prestate')}
        q15w = dict(result_sha256='b'*64, request=dict(action_inputs=dict(prestate=copy.deepcopy(original['prestate']))))
        validation = SimpleNamespace(resolutions={
            'S17-EXT-004': SimpleNamespace(semantic_context=dict(hardware_mapping=mapping)),
            'S17-EXT-005': SimpleNamespace(semantic_context=dict(q15_w=q15w))})
        result = p.hardware(validation, original)
        self.assertEqual(result['q15_w_result_sha256'], 'b'*64)
        self.assertEqual(result['prestate'], original['prestate'])
        q15w['request']['action_inputs']['prestate'][0]['cpu'] = 8
        with self.assertRaisesRegex(ValueError, 'fresh Q15-R/W'):
            p.hardware(validation, original)
        mapping['prestate'][0]['cpu'] = 8
        with self.assertRaisesRegex(ValueError, 'original qualified'):
            p.hardware(validation, original)

    def test_actual_remaining_geometry_preserves_original_resource_limits(self):
        root = Path(__file__).resolve().parents[4]
        parent = json.loads((root/'build/stage17-step5-prep/formal-q16a-authoring-v23-1/final-v23-1/plan.json').read_bytes())
        suffix = copy.deepcopy(parent)
        suffix['captures'] = suffix['captures'][177:]
        proof = p.resources(suffix, parent)
        self.assertEqual(proof, dict(required_worker_as_bytes=240518168576,
            max_native_mapping_bytes=24877350912, required_family_as_bytes=246960619520,
            operational_memory_reserve_bytes=8589934592))
        suffix['budget']['memory_bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'family budget'):
            p.resources(suffix, parent)

    def test_exact_two_scopes_and_bound_plans_required(self):
        phases = []
        for ordinal in range(177, 708):
            for letter, phase in [('W', 'WARMUP'), ('M', 'MEASUREMENT')]:
                namespace = 'CPU-PREFETCH-V5-V25-Q16A-'+phase+'-1'
                phases.append(dict(run_id=f'F25{letter}{ordinal:08d}', seed_id=namespace+f'-SEED-{ordinal:04d}',
                                   seed_hex='0'*64, namespace_id=namespace))
        identities = dict(phase_identities=phases)
        binding = dict(path='/fixture/plan', size_bytes=1, sha256='a'*64)
        parent = dict(path='/fixture/parent', size_bytes=1, sha256='b'*64)
        common = dict(status='PASS_SCOPED_HISTORY_AUDIT', matches=[], errors=[], checked_files=1,
                      execution_authority=False, needles=sorted(p.audit.Matcher(identities).wanted),
                      plan_binding=binding, parent_plan_binding=parent,
                      parent_contract=dict(original_numeric_seeds_preserved=True, numeric_seeds_collision_scanned=False))
        reports = [dict(common, roots=['/fixture/docs/evidence']),
                   dict(common, roots=['/home/omaltsev/stage17-owner-evidence/context/journal'])]
        p.check_audits(reports, binding, identities, parent)
        for kind in ('duplicate', 'collision', 'different_plan', 'missing'):
            rows = copy.deepcopy(reports)
            if kind == 'duplicate': rows[1] = rows[0]
            elif kind == 'collision': rows[0]['matches'] = ['collision']
            elif kind == 'different_plan': rows[0]['plan_binding']['sha256'] = 'c'*64
            else: rows.pop()
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                p.check_audits(rows, binding, identities, parent)


if __name__ == '__main__':
    unittest.main(verbosity=2)
