"""Actual completed Q16b metadata and real current source closure.

Synthetic qualification/platform boundary only; no stand or empirical claim.
Actual platform and qualified original release proof remain operational gates.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_q16b_q16c_descriptive_handoff_v1 as current
import test_stage17_q16a_q16c_descriptive_handoff_v1 as source_fixture
import test_stage17_q16a_daycap_handoff_v1 as files
from test_stage17_q16b_handoff_v1 import fixture as completed_fixture


class Q16bReuseTests(unittest.TestCase):
    def setUp(self):
        self.sources = source_fixture.Q16cQ16aReuseTests()
        self.sources.setUp(); self.addCleanup(self.sources.doCleanups)
        self.e = e = self.sources.e
        self.document, self.original_validation = completed_fixture()
        parent = json.loads(Path(self.document['parent_plan']['path']).read_bytes())
        settings = {}
        for item in parent['captures']:
            c = item['capture']; settings[(c['hardware_state'], c['package'], c['placement'], c['working_set_class'])] = c
        for item in e.plan['captures']:
            c = item['capture']; prior = settings[(c['hardware_state'], c['package'], c['placement'], c['working_set_class'])]
            for key in ('geometry', 'software_prefetch_mapping_id', 'ring_distance'): c[key] = copy.deepcopy(prior[key])
            if c['linked_order'] is not None:
                c['linked_order']['arena_alignment_bytes'] = prior['linked_order']['arena_alignment_bytes']
        for item in e.plan['captures']:
            budget = item['execution_budget']
            budget.update(publication_memory_bytes=32 * 1024**2, memory_bytes=34 * 1024**2,
                          max_output_bytes=32 * 1024**2)
        e.plan['budget']['memory_bytes'] += 34 * 1024**2
        e.plan['budget']['max_output_bytes'] = 181 * 32 * 1024**2
        e.plan['storage']['analysis_capture_workspace_bytes'] = 64 * 1024**2
        p = e.proof
        p['schema_version'] = current.SCHEMA
        p['scope'].update(purpose=current.PURPOSE)
        p.pop('original_plan'); p['parent_plan'] = copy.deepcopy(self.document['parent_plan'])
        p['handoff'] = files.save(e.root / 'q16b-handoff.json', self.document)
        p['plan'] = files.save(e.root / 'q16c-plan.json', e.plan)
        geometry = json.loads(Path(self.document['geometry']['path']).read_bytes())
        geometry['source_revision'] = e.plan['source_revision']
        p['native_geometry'] = files.save(e.root / 'current-native.json', geometry)

    def consume(self):
        e = self.e; real = current.compatibility._release
        def release(side, context, reader, source):
            return e.releases['original'] if source == current.original.SOURCE else real(side, context, reader, source)
        proof = files.save(e.root / 'q16b-compatibility.json', e.proof)
        with mock.patch.object(current.compatibility, '_release', side_effect=release), \
             mock.patch.object(current.compatibility, '_platforms'):
            return current.consume(self.document, validation=e.validation, original_validation=self.original_validation,
                plan=e.plan, selected_duration_ns=10**9, compatibility_binding=proof,
                original_boot_id=e.boot, boot_id=e.boot)

    def test_actual_120_reports_both_histories_and_full_gates_are_preserved(self):
        result = self.consume()
        self.assertEqual(result, json.loads(Path(self.document['composition']['path']).read_bytes()))
        self.assertEqual(result['status'], 'DESCRIPTIVE'); self.assertFalse(result['tolerance_guarantee'])
        self.assertEqual(len(result['run_sources']), 120)
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'], 'FAIL')
        self.assertFalse(result['execution_authority']); self.assertFalse(result['phase18_authority'])

    def test_rebound_changed_parent_or_current_setting_cannot_reuse(self):
        self.e.proof['parent_plan']['sha256'] = '0' * 64
        with self.assertRaises(current.Error): self.consume()
        self.e.proof['parent_plan'] = self.document['parent_plan']
        for item in self.e.plan['captures'][:3]: item['capture']['geometry']['capacity'] //= 2
        self.e.proof['plan'] = files.save(self.e.root / 'q16c-plan.json', self.e.plan)
        with self.assertRaises(current.Error): self.consume()

    def test_no_source_omission_or_wrong_original_qualification(self):
        self.e.proof['source_comparisons'].pop()
        with self.assertRaises(current.Error): self.consume()
        self.original_validation.resolutions['S17-EXT-006'].semantic_context['source_revision'] = '0' * 40
        with self.assertRaises(current.Error): self.consume()


if __name__ == '__main__': unittest.main()
