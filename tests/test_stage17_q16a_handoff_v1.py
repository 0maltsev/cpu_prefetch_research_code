"""Exact retained metadata tests; no raw decode, experiment or run authority."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_q16a_handoff_v1 as handoff
import stage17_phase_controller_v27 as controller
import stage17_phase_controller_v26 as previous
import test_stage17_phase_controller_v25 as old_tests
from test_stage17_formal_plan_v2 import archived_fixture

EVIDENCE = ROOT / 'docs/evidence/stage17/Q16A-COMPOSITION-ACTUAL-20261115-01/stand/composition'


def fixture():
    names = dict(completion='complete.json', composition='authenticated-composition.json',
                 geometry='native-geometry-verification.json')
    document = dict(schema_version=handoff.SCHEMA, execution_authority=False, phase18_authority=False)
    for key, name in names.items():
        path = EVIDENCE / name
        raw = path.read_bytes()
        document[key] = dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    geometry = json.loads((EVIDENCE / names['geometry']).read_bytes())
    bundle = str(Path(geometry['shared_queue_libraries']['continuation']['path']).parents[2])
    context = dict(source_revision=handoff.SOURCE, inventory_sha256=handoff.INVENTORY, archive_bundle_root=bundle)
    validation = SimpleNamespace(resolutions={
        'S17-EXT-006': SimpleNamespace(semantic_context=context),
        'S17-EXT-004': SimpleNamespace(semantic_context=dict(pilot_platform_measurements=dict(
            platform_manifest_sha256=geometry['platform_manifest']['sha256'])))})
    plan = dict(source_revision=handoff.SOURCE, stand_id='CPU-PREFETCH-V5')
    return document, validation, plan


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.document, self.validation, self.plan = fixture()

    def consume(self):
        return handoff.consume(self.document, validation=self.validation, plan=self.plan,
                               selected_duration_ns=1_000_000_000)

    def test_actual_completed_two_source_result_preserved_with_full_and_no_authority(self):
        result = self.consume()
        self.assertEqual(len(result['run_sources']), 708)
        self.assertEqual([p['required_reports'] for p in result['source_populations']], [177, 531])
        self.assertNotEqual(result['source_populations'][0]['source_revision'], result['source_populations'][1]['source_revision'])
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'], 'FAIL')
        self.assertEqual([c['distance']['d2_cache_lines'] for c in result['derived_result']['contexts']], [2] * 6)
        self.assertFalse(result['execution_authority'])
        self.assertFalse(result['producer_authentication_established'])
        self.assertFalse(result['family_validity_established'])

    def test_rebinding_changed_output_cannot_substitute_for_authenticated_producer(self):
        with tempfile.TemporaryDirectory() as temp:
            for key in handoff.ACCEPTED:
                with self.subTest(key=key):
                    original = self.document[key]
                    payload = Path(original['path']).read_bytes() + b' '
                    path = Path(temp) / key
                    path.write_bytes(payload)
                    self.document[key] = dict(path=str(path), size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                    with self.assertRaises(handoff.Error):
                        self.consume()
                    self.document[key] = original

    def test_symlink_copy_rejected_even_when_content_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            link = Path(temp) / 'same-bytes'
            link.symlink_to(self.document['composition']['path'])
            self.document['composition']['path'] = str(link)
            with self.assertRaises(handoff.Error):
                self.consume()

    def test_different_qualification_stand_platform_and_duration_rejected(self):
        original = copy.deepcopy((self.validation, self.plan))
        for field in ('source_revision', 'inventory_sha256', 'archive_bundle_root'):
            self.validation, self.plan = copy.deepcopy(original)
            self.validation.resolutions['S17-EXT-006'].semantic_context[field] = 'different'
            with self.subTest(field=field), self.assertRaises(handoff.Error):
                self.consume()
        self.validation, self.plan = copy.deepcopy(original)
        self.plan['stand_id'] = 'different'
        with self.assertRaises(handoff.Error):
            self.consume()
        self.validation, self.plan = copy.deepcopy(original)
        self.validation.resolutions['S17-EXT-004'].semantic_context['pilot_platform_measurements']['platform_manifest_sha256'] = '0' * 64
        with self.assertRaises(handoff.Error):
            self.consume()
        self.validation, self.plan = copy.deepcopy(original)
        with self.assertRaises(handoff.Error):
            handoff.consume(self.document, validation=self.validation, plan=self.plan, selected_duration_ns=2_000_000_000)

    def test_declared_authority_and_unknown_fields_rejected(self):
        for field, value in (('execution_authority', True), ('phase18_authority', 0), ('unreviewed', False)):
            original = copy.deepcopy(self.document)
            self.document[field] = value
            with self.subTest(field=field), self.assertRaises(handoff.Error):
                self.consume()
            self.document = original


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.base = old_tests.FormalController()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.document, qualified, _ = fixture()
        self.base.context.update(qualified.resolutions['S17-EXT-006'].semantic_context)
        self.base.validation.resolutions['S17-EXT-004'].semantic_context.update(
            qualified.resolutions['S17-EXT-004'].semantic_context)
        self.plan = archived_fixture('Q16b')
        self.plan.update(source_revision=handoff.SOURCE, stand_id='CPU-PREFETCH-V5')
        self.plan['storage']['analysis_capture_workspace_bytes'] = 64 * 1024**2
        self.binding = self.base.write('q16a-handoff', self.document)
        for item in self.plan['captures']:
            c = item['capture']
            c['geometry']['capacity'] = (512, 65536, 1048576)[previous.contract.WORKING_SETS.index(c['working_set_class'])]
            budget = item['execution_budget']
            budget['publication_memory_bytes'] = 64 * 1024**2
            budget['memory_bytes'] = item['resources']['total_mapping_bytes'] + budget['publication_memory_bytes'] + budget['other_memory_bytes']
            budget['max_output_bytes'] = 64 * 1024**2
            if c['package'] == 'R2':
                c['ring_distance'] = dict(cache_lines=2, calibration_evidence_id='q16a-sha256-' + self.binding['sha256'])
        self.plan['budget']['max_output_bytes'] = len(self.plan['captures']) * 64 * 1024**2 + self.plan['budget']['metadata_output_bytes']
        self.plan['budget']['memory_bytes'] = (self.plan['budget']['controller_memory_bytes']
            + max(i['execution_budget']['memory_bytes'] for i in self.plan['captures'])
            + self.plan['storage']['codec_address_space_bytes']
            + self.plan['storage']['broker_address_space_bytes'])
        self.base.namespace.update(plan_sha256=hashlib.sha256(previous.archive.canonical(self.plan)).hexdigest(),
            stand_id=self.plan['stand_id'], phase_identities=[i['capture'][p] for i in self.plan['captures'] for p in ('warmup', 'measurement')])
        self.request = self.base.request
        self.request.update(action_id='Q16b', stand_id='CPU-PREFETCH-V5', schema_version='cpu-prefetch-stage17-fixed-action-request/6')
        self.request['action_inputs']['plan'] = self.plan
        self.request['action_inputs']['prerequisite_bindings'].update(q16a_validation=self.binding,
            namespace_registry=self.base.write('namespace-service', self.base.namespace))

    def validate(self):
        # Profile admission is tested separately in v26; this checks all formal
        # plan/discovery/hardware/prior/namespace gates before profile loading.
        return controller._validate_inputs(self.request, self.base.validation)

    def test_handoff_enters_service_admission_without_legacy_schema_projection(self):
        before = copy.deepcopy(self.request)
        self.assertEqual(len(self.validate().captures), 3540)
        self.assertEqual(self.request, before)
        with self.assertRaises(previous.ControllerError):
            previous._validate_inputs(self.request, self.base.validation)

    def test_wrong_r2_distance_and_wrong_evidence_binding_rejected(self):
        capture = next(i['capture'] for i in self.plan['captures'] if i['capture']['package'] == 'R2')
        for key, value in (('cache_lines', 1), ('calibration_evidence_id', 'different')):
            original = copy.deepcopy(capture['ring_distance'])
            capture['ring_distance'][key] = value
            with self.subTest(key=key), self.assertRaises(previous.ControllerError):
                self.validate()
            capture['ring_distance'] = original

    def test_historical_controller_globals_are_unchanged(self):
        prior = previous.previous.validate_prior_calibration
        original_globals = dict(prior.__globals__)
        self.validate()
        self.assertEqual(prior.__globals__, original_globals)


if __name__ == '__main__':
    unittest.main()
