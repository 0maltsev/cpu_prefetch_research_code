"""D270 declaration checks; synthetic fixtures confer no execution authority."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from jsonschema import Draft202012Validator
import stage17_formal_scheduled_descriptive_v1 as current
import stage17_formal_plan_v2 as historical
from test_stage17_formal_plan_v2 import archived_fixture


def plan_fixture():
    p = archived_fixture('Q16c')
    p.update(schema_version=current.VERSION, method_id=current.METHOD)
    sizes = []
    for item in p['captures']:
        c = item['capture']
        c['schema_version'] = 'cpu-prefetch-stage17-formal-scheduled-capture/2'
        for source in c['schedules']:
            source.pop('deadline_ticks')
            source['storage_format'] = 'SEALED_U64BE_ORIGINAL-v1'
            sizes.append(source['offered_count'] * 8)
    total = sum(sizes)
    p['source_transport'] = dict(schema_version='cpu-prefetch-stage17-schedule-transport-budget/1',
        format='SEALED_U64BE_ORIGINAL-v1', source_bytes=total, owned_vector_bytes=total,
        loader_transient_bytes=max(sizes) + 8192, descriptor_count=360, metadata_bytes=1024**2,
        maximum_source_memory_bytes=2 * total + max(sizes) + 8192 + 1024**2)
    p['budget']['memory_bytes'] += p['source_transport']['maximum_source_memory_bytes']
    return p


class DescriptivePlanTests(unittest.TestCase):
    def test_full_matrix_exact_count_and_collector_identity(self):
        p = plan_fixture()
        Draft202012Validator(json.loads((current.ROOT / current.SCHEMA).read_text())).validate(p)
        r = current.validate_plan(p)
        self.assertEqual(len(r.captures), 180)
        self.assertFalse(r.execution_authority)
        self.assertEqual({c['capture']['cell_ordinal'] for c in p['captures']}, set(range(180)))
        self.assertTrue(all(c['capture']['method_id'] == current.COLLECTOR_METHOD for c in p['captures']))
        with self.assertRaises(current.ContractError): historical.validate_plan('Q16c', p)
        historical.validate_plan('Q16c', archived_fixture('Q16c'))

    def test_rejects_coverage_rate_duration_and_legacy_relabelling(self):
        mutations = [lambda p: p['captures'].pop(),
            lambda p: p.update(repetitions_per_cell=2), lambda p: p.update(measurement_ns=2_000_000_000),
            lambda p: p.update(scale_ordinal=1), lambda p: p.update(method_id=current.COLLECTOR_METHOD),
            lambda p: p['captures'][0]['capture'].update(method_id=current.METHOD),
            lambda p: p['captures'][1]['capture'].update(cell_ordinal=0),
            lambda p: p['budget'].update(watchdog_ns=current.DAYCAP_NS + 1)]
        for change in mutations:
            p = plan_fixture(); change(p)
            with self.subTest(change=change), self.assertRaises(current.ContractError):
                current.validate_plan(p)

    def test_all_memory_components_and_exact_descriptor_membership_required(self):
        for key in ('source_bytes', 'owned_vector_bytes', 'loader_transient_bytes',
                    'descriptor_count', 'metadata_bytes', 'maximum_source_memory_bytes'):
            p = plan_fixture(); p['source_transport'][key] -= 1
            with self.subTest(key=key), self.assertRaises(current.ContractError): current.validate_plan(p)
        p = plan_fixture(); p['budget']['memory_bytes'] -= p['source_transport']['maximum_source_memory_bytes']
        with self.assertRaises(current.ContractError): current.validate_plan(p)
        p = plan_fixture()
        p['captures'][1]['capture']['schedules'][0]['source_artifact']['artifact_id'] = \
            p['captures'][0]['capture']['schedules'][0]['source_artifact']['artifact_id']
        with self.assertRaises(current.ContractError): current.validate_plan(p)

    def test_no_inline_array_placeholder_or_unverified_source_extent(self):
        for change in [lambda s: s.update(deadline_ticks=[]), lambda s: s.update(storage_format='INLINE'),
                       lambda s: s.update(offered_count=100), lambda s: s.update(source_horizon_ticks=10),
                       lambda s: s.update(offered_count=True)]:
            p = plan_fixture(); change(p['captures'][0]['capture']['schedules'][1])
            with self.subTest(change=change), self.assertRaises(current.ContractError): current.validate_plan(p)


if __name__ == '__main__': unittest.main()
