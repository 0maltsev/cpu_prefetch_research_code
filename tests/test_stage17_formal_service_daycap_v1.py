"""D254 synthetic declarations and descriptive math; no stand/performance claim."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from jsonschema import Draft202012Validator, ValidationError
import stage17_formal_service_daycap_v1 as current
import stage17_formal_plan_v1 as native
import stage17_formal_plan_v2 as archived
import stage17_formal_storage_budget_v1 as storage
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_service_capture_validation_v1 import Fixture as ServiceCapture


def select_repetitions(source, repetitions):
    """Select actual original captures without fabricating repeated rows/IDs."""
    result = {key: copy.deepcopy(value) for key, value in source.items() if key != 'captures'}
    result['captures'] = []
    for item in source['captures']:
        if item['capture']['repetition_ordinal'] >= repetitions:
            continue
        item = copy.deepcopy(item)
        ordinal = len(result['captures'])
        for key in ('capture', 'resources', 'monitoring'):
            item[key]['ordinal'] = ordinal
        result['captures'].append(item)
    result.update(schema_version=current.VERSION, method_id=current.METHOD, repetitions_per_cell=repetitions)
    family = result['budget']
    family['max_output_bytes'] = family['metadata_output_bytes'] + sum(
        item['execution_budget']['max_output_bytes'] for item in result['captures'])
    family['watchdog_ns'] = family['setup_ns'] + family['cleanup_ns'] + sum(
        item['execution_budget']['watchdog_ns'] + result['storage']['per_capture_archive_ns']
        for item in result['captures'])
    return result


def binding(name, raw):
    return dict(artifact_id=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def record(capture, report, validity='VALID'):
    raw = json.dumps(report, sort_keys=True, separators=(',', ':'), allow_nan=False).encode() + b'\n'
    return dict(capture_ordinal=capture['ordinal'], measurement_run_id=capture['measurement']['run_id'],
                validity=validity, report_binding=binding('report-' + str(capture['ordinal']), raw),
                report_utf8_bytes=raw.decode())


def rebind(row, report):
    row.update(record(dict(ordinal=row['capture_ordinal'], measurement=dict(run_id=row['measurement_run_id'])),
                      report, row['validity']))


class DaycapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build the historical storage fixture once; retain only three real runs
        # per cell for all boundary cases. Never triple the 3540-entry arrays.
        original = archived_fixture('Q16b')
        cls.source = select_repetitions(original, 3)
        del original
        cls.plan = select_repetitions(cls.source, 2)
        cls.schema = json.loads((native.ROOT / current.SCHEMA).read_text())
        with tempfile.TemporaryDirectory(prefix='d254-synthetic-report-') as temporary:
            cls.prototype = ServiceCapture(pathlib.Path(temporary)).run()
        cls.records = []
        for item in cls.plan['captures']:
            capture = item['capture']
            report = copy.deepcopy(cls.prototype)
            report['capture_ordinal'] = capture['ordinal']
            for phase, name in zip(report['phases'], ('warmup', 'measurement'), strict=True):
                phase['run_id'] = capture[name]['run_id']
            cls.records.append(record(capture, report))

    def reject_plan(self, mutate, message=None):
        plan = copy.deepcopy(self.plan)
        mutate(plan)
        with self.assertRaises(current.ContractError) as caught:
            current.validate_plan(plan)
        if message:
            self.assertIn(message, str(caught.exception))

    def test_complete_contract_identity_exact_extents_and_no_mutation(self):
        before = copy.deepcopy(self.plan)
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema).validate(self.plan)
        result = current.validate_plan(self.plan)
        self.assertEqual(self.plan, before)
        self.assertEqual(len(result.captures), 120)
        self.assertEqual(result.captures[0].raw_bytes, 4640)
        self.assertEqual(result.captures[36].raw_bytes, 4640 + 65 * 8)
        self.assertEqual(result.captures[0].largest_raw_copy_bytes, 1360)
        self.assertEqual(result.required_watchdog_ns, 120 * 12_000_000_000 + 2_000_000_000)
        self.assertEqual(result.peak_memory_bytes, 20_400_000 + storage.CODEC_MEMORY + 1024**3)
        self.assertEqual(result.maximum_output_bytes, 120 * 20000 + 1_000_000)
        self.assertEqual(result.required_free_disk_bytes, storage.QUOTA + storage.WORKSPACE + storage.SCRATCH + storage.RESERVE)
        self.assertFalse(result.execution_authority)
        cells = [item['capture']['cell_ordinal'] for item in self.plan['captures']]
        self.assertEqual({cell: cells.count(cell) for cell in range(60)}, {cell: 2 for cell in range(60)})
        self.assertEqual(cells[12], 12)
        self.assertEqual(cells[60], 6)
        native_schema = json.loads((native.ROOT / native.NATIVE_SCHEMA['Q16b']).read_text())
        for name, definition in native_schema['$defs'].items():
            self.assertEqual(self.schema['$defs'][name], definition)
        self.assertEqual({item['capture']['method_id'] for item in self.plan['captures']}, {current.COLLECTOR_METHOD})
        self.assertEqual(current.VERSION, 'cpu-prefetch-stage17-formal-service-plan/3')
        self.assertEqual(current.METHOD, 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1')

    def test_canonical_hash_is_original_native_plan_no_projection_or_lf(self):
        encoded = current.plan_bytes(self.plan)
        expected = json.dumps(self.plan, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        self.assertEqual(encoded, expected)
        self.assertFalse(encoded.endswith(b'\n'))
        self.assertEqual(json.loads(encoded), self.plan)
        report = current.evaluate(self.plan, [])
        self.assertEqual(report['plan_sha256'], hashlib.sha256(expected).hexdigest())

    def test_new_validator_rejects_historical_versions_other_actions_and_methods(self):
        for version in (native.VERSION['Q16b'], archived.VERSION['Q16b'], current.VERSION + '.1'):
            with self.subTest(version=version):
                self.reject_plan(lambda p: p.update(schema_version=version))
        for action in ('Q16a', 'Q16c'):
            self.reject_plan(lambda p: p.update(action_id=action))
        self.reject_plan(lambda p: p.update(method_id=current.COLLECTOR_METHOD))
        self.reject_plan(lambda p: p['captures'][0]['capture'].update(method_id=current.METHOD))
        for validator in (native.validate_plan, archived.validate_plan):
            with self.assertRaises(current.ContractError):
                validator('Q16b', self.plan)

    def test_one_or_three_repetitions_even_complete_coverage_rejected(self):
        for repetitions in (1, 3):
            plan = select_repetitions(self.source, repetitions)
            self.assertEqual(len(plan['captures']), 60 * repetitions)
            with self.assertRaises(current.ContractError):
                current.validate_plan(plan)
            with self.assertRaises(ValidationError):
                Draft202012Validator(self.schema).validate(plan)

    def test_frozen_coverage_and_identity_mutants(self):
        mutations = [
            lambda p: p['captures'].pop(),
            lambda p: p['captures'].append(copy.deepcopy(p['captures'][-1])),
            lambda p: p['captures'].__setitem__(slice(0, 2), list(reversed(p['captures'][:2]))),
            lambda p: p['captures'][0]['capture'].update(cell_ordinal=1),
            lambda p: p['captures'][0]['capture'].update(repetition_ordinal=1),
            lambda p: p['captures'][0]['capture'].update(hardware_state='H1'),
            lambda p: p['captures'][0]['capture'].update(package='R1'),
            lambda p: p['captures'][0]['capture'].update(placement='FAR'),
            lambda p: p['captures'][0]['capture'].update(working_set_class='BEYOND_LLC'),
            lambda p: p.update(measurement_ns=2_000_000_000),
            lambda p: p['captures'][0]['capture'].update(measurement_ns=2_000_000_000),
            lambda p: p['captures'][0]['capture'].update(warmup_ns=1),
            lambda p: p['captures'][0]['resources'].update(ordinal=1),
            lambda p: p['captures'][0]['monitoring'].update(ordinal=1),
            lambda p: p['captures'][0]['capture']['warmup'].update(namespace_id='wrong'),
            lambda p: p['captures'][1]['capture']['warmup'].update(run_id=p['captures'][0]['capture']['warmup']['run_id']),
            lambda p: p['captures'][1]['capture']['warmup'].update(seed_id=p['captures'][0]['capture']['warmup']['seed_id']),
            lambda p: p['captures'][1]['capture']['warmup'].update(seed_hex=p['captures'][0]['capture']['warmup']['seed_hex']),
            lambda p: p['captures'][0]['capture']['arena_seed'].update(run_id='wrong'),
            lambda p: p.update(unknown=True),
            lambda p: p.pop('storage'),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                self.reject_plan(mutate)

    def test_native_geometry_package_sizing_and_observation_checks_retained(self):
        mutations = [
            lambda p: p['captures'][0]['capture']['geometry'].update(producer_cpu=True),
            lambda p: p['captures'][1]['capture']['geometry'].update(capacity=128),
            lambda p: p['captures'][12]['capture'].update(ring_distance=None),
            lambda p: p['captures'][36]['capture'].update(linked_order=None),
            lambda p: p['captures'][0]['resources']['workers']['consumer_stack'].update(owner_cpu=7),
            lambda p: p['captures'][0]['resources']['controller_stack'].update(owner_cpu=0),
            lambda p: p['captures'][0]['monitoring']['during_offset_ticks'].__setitem__(1, 10**12),
            lambda p: p['captures'][1]['capture']['budget']['phases'][0].update(producer_attempt_limit=9),
            lambda p: p['captures'][0]['resources']['phase_capacity'][0].update(producer_primary_rows=1),
            lambda p: p['captures'][0]['resources']['phase_capacity'][0].update(consumer_primary_rows=1),
            lambda p: p['captures'][0]['capture']['budget'].update(memory_bytes=1),
            lambda p: p['captures'][0]['execution_budget'].update(publication_memory_bytes=1),
            lambda p: p['captures'][0]['execution_budget'].update(memory_bytes=1),
            lambda p: p['captures'][0]['execution_budget'].update(max_output_bytes=1),
            lambda p: p['captures'][0]['execution_budget'].update(watchdog_ns=1),
            lambda p: p['budget'].update(controller_memory_bytes=1),
            lambda p: p['budget'].update(memory_bytes=1),
            lambda p: p['budget'].update(max_output_bytes=1),
            lambda p: p['budget'].update(required_free_disk_bytes=1),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                self.reject_plan(mutate)

    def test_archive_resources_and_entire_day_watchdog_including_validation(self):
        plan = copy.deepcopy(self.plan)
        plan['budget']['watchdog_ns'] = current.DAYCAP_NS
        current.validate_plan(plan)
        Draft202012Validator(self.schema).validate(plan)
        result = current.validate_plan(self.plan)
        self.reject_plan(lambda p: p['budget'].update(watchdog_ns=result.required_watchdog_ns - 1))
        self.reject_plan(lambda p: p['budget'].update(watchdog_ns=current.DAYCAP_NS + 1), '24-hour')
        self.reject_plan(lambda p: p['budget'].update(cleanup_ns=current.DAYCAP_NS))
        self.reject_plan(lambda p: p['storage'].update(per_capture_archive_ns=current.DAYCAP_NS))
        for key, value in (('archive_quota_bytes', storage.QUOTA - 1), ('workspace_bytes', storage.WORKSPACE - 1),
                           ('implementation_profile_sha256', 'bad'), ('program_scope_sha256', 'bad'),
                           ('analysis_capture_workspace_bytes', 1), ('broker_address_space_bytes', storage.CODEC_MEMORY + 1),
                           ('checkpoint_bytes', 10001), ('archive_staging_bytes', storage.WORKSPACE)):
            with self.subTest(storage=key):
                self.reject_plan(lambda p: p['storage'].update({key: value}))

    def test_floats_booleans_and_out_of_domain_values_rejected(self):
        for value in (2.0, True, -1, 2**64, None, '2'):
            with self.subTest(repetitions=value):
                self.reject_plan(lambda p: p.update(repetitions_per_cell=value))
        for value in (1.0, True, -1, 2**64):
            self.reject_plan(lambda p: p['captures'][0]['execution_budget'].update(setup_ns=value))
        self.reject_plan(lambda p: p['captures'][0]['monitoring']['hardware_identity'].update(model=6.0))
        self.reject_plan(lambda p: p['captures'][0]['capture']['budget']['phases'][0].update(drain_ns=2**64 - 1))
        self.reject_plan(lambda p: p['budget'].update(setup_ns=2**64 - 1))

    def test_descriptive_exact_two_per_cell_and_explicit_claim_boundaries(self):
        before = copy.deepcopy(self.records)
        result = current.evaluate(self.plan, self.records)
        self.assertEqual(self.records, before)
        self.assertEqual(result['schema_version'], current.SCHEMA_ID)
        self.assertEqual(result['method_id'], current.METHOD)
        self.assertEqual(result['collector_method_id'], current.COLLECTOR_METHOD)
        self.assertEqual(result['status'], 'DESCRIPTIVE')
        self.assertTrue(result['descriptive_summary_complete'])
        self.assertIsNone(result['tolerance_claim'])
        for flag in ('tolerance_guarantee', 'report_provenance_authenticated', 'independent_runs_authenticated',
                     'family_validity_established', 'execution_authority', 'phase18_authority'):
            self.assertIs(result[flag], False)
        cells = result['derived_result']['cells']
        self.assertEqual([cell['cell_ordinal'] for cell in cells], list(range(60)))
        self.assertTrue(all(cell['valid_runs'] == cell['planned_runs'] == 2 for cell in cells))
        self.assertTrue(all(cell['min_mu_cell'] == dict(numerator=3, denominator=1) for cell in cells))
        self.assertEqual(result['derived_result']['min_mu_ref'], dict(numerator=3, denominator=1))
        self.assertNotIn('mu_ref', result['derived_result'])

    def test_exact_fraction_rates_and_genuine_zero_are_retained(self):
        self.assertEqual(current.capture_reports.exact_throughput(1, 10, 3), dict(numerator=10, denominator=3))
        # Verify cancellation before the checked uint64 rational boundary.
        self.assertEqual(current.capture_reports.exact_throughput(2**64 - 1, 10**12, 10**12),
                         dict(numerator=2**64 - 1, denominator=1))
        rows = copy.deepcopy(self.records)
        report = json.loads(rows[0]['report_utf8_bytes'])
        interval = report['phases'][1]['completion_interval']
        interval.update(interval_consumed_count=0, outside_interval_consumed_count=interval['consumed_count'])
        rebind(rows[0], report)
        result = current.evaluate(self.plan, rows)
        self.assertEqual(result['derived_result']['min_mu_ref'], dict(numerator=0, denominator=1))
        self.assertEqual(result['derived_result']['cells'][0]['min_mu_cell'], dict(numerator=0, denominator=1))
        self.assertEqual(result['derived_result']['cells'][0]['valid_runs'], 2)
        self.assertEqual(result['status'], 'DESCRIPTIVE')
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'], 'PASS')

    def test_minimum_uses_both_repetitions_and_all_sixty_cells(self):
        rows = copy.deepcopy(self.records)
        for index, count in ((0, 2), (1, 1), (119, 0)):
            report = json.loads(rows[index]['report_utf8_bytes'])
            interval = report['phases'][1]['completion_interval']
            interval.update(interval_consumed_count=count,
                            outside_interval_consumed_count=interval['consumed_count'] - count)
            rebind(rows[index], report)
        # Input receipt order cannot change the planned state-major grouping.
        result = current.evaluate(self.plan, list(reversed(rows)))
        cells = result['derived_result']['cells']
        self.assertEqual(cells[0]['min_mu_cell'], dict(numerator=1, denominator=1))
        self.assertEqual(cells[59]['min_mu_cell'], dict(numerator=0, denominator=1))
        self.assertEqual(result['derived_result']['min_mu_ref'], dict(numerator=0, denominator=1))

    def test_full_is_valid_data_and_fails_separate_zero_loss_gate(self):
        rows = copy.deepcopy(self.records)
        report = json.loads(rows[0]['report_utf8_bytes'])
        counts = report['phases'][1]['counts']
        counts['attempted'] += 1
        counts['full'] = 1
        report['phases'][1]['zero_loss'] = False
        report['measurement_zero_loss'] = report['zero_loss_all_phases'] = False
        rebind(rows[0], report)
        result = current.evaluate(self.plan, rows)
        self.assertEqual(result['status'], 'DESCRIPTIVE')
        self.assertEqual(result['run_sources'][0]['validity'], 'VALID')
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'], 'FAIL')

    def test_missing_and_invalid_runs_remain_unresolved_without_topups(self):
        result = current.evaluate(self.plan, self.records[1:])
        self.assertEqual(result['status'], 'UNRESOLVED')
        self.assertFalse(result['descriptive_summary_complete'])
        self.assertEqual(result['run_sources'][0]['validity'], 'MISSING')
        self.assertIsNone(result['derived_result']['min_mu_ref'])
        self.assertIsNone(result['derived_result']['cells'][0]['min_mu_cell'])
        self.assertEqual(result['derived_result']['cells'][0]['valid_runs'], 1)
        capture = self.plan['captures'][0]['capture']
        failed = dict(schema_version=current.capture_reports.FAILURE_SCHEMA_ID, action_id='Q16b',
            method_id=current.COLLECTOR_METHOD, capture_ordinal=0,
            warmup_run_id=capture['warmup']['run_id'], measurement_run_id=capture['measurement']['run_id'],
            plan_sha256=hashlib.sha256(current.plan_bytes(self.plan)).hexdigest(), source_revision=self.plan['source_revision'],
            error=dict(type='ValidationError', message='synthetic rejection'),
            input_bindings=dict(native_input=binding('input', b'i'), control=binding('control', b'c'),
                final=binding('final', b'f'), raw_artifacts=[binding('raw-' + str(i), b'r') for i in range(5)]),
            execution_authority=False, phase18_authority=False)
        rows = [record(capture, failed, 'INVALID'), *self.records[1:]]
        result = current.evaluate(self.plan, rows)
        self.assertEqual(result['status'], 'UNRESOLVED')
        self.assertEqual(result['derived_result']['cells'][0]['invalid_runs'], 1)
        self.assertEqual(result['run_sources'][0]['failure'], failed)
        self.assertIsNone(result['derived_result']['min_mu_ref'])

    def test_report_bindings_membership_collector_flags_and_domains_are_checked(self):
        mutations = [
            lambda rows: rows.append(copy.deepcopy(rows[0])),
            lambda rows: rows[0].update(capture_ordinal=120),
            lambda rows: rows[0].update(capture_ordinal=True),
            lambda rows: rows[0].update(measurement_run_id='unplanned'),
            lambda rows: rows[0]['report_binding'].update(sha256='0' * 64),
            lambda rows: rows[0]['report_binding'].update(size_bytes=1),
            lambda rows: rows[0].update(validity='INVALID'),
        ]
        for index, mutate in enumerate(mutations):
            rows = copy.deepcopy(self.records)
            mutate(rows)
            with self.subTest(mutation=index), self.assertRaises(current.CalibrationError):
                current.evaluate(self.plan, rows)
        for field, value in (('method_id', current.METHOD), ('capture_ordinal', 0.0),
                             ('family_validity_established', True), ('execution_authority', True),
                             ('capture_execution_evidence_validated', False), ('raw_reconciliation_validated', False)):
            rows = copy.deepcopy(self.records)
            report = json.loads(rows[0]['report_utf8_bytes'])
            report[field] = value
            rebind(rows[0], report)
            with self.subTest(field=field), self.assertRaises(current.CalibrationError):
                current.evaluate(self.plan, rows)
        for value in (1.0, True, -1, 2**64):
            rows = copy.deepcopy(self.records)
            report = json.loads(rows[0]['report_utf8_bytes'])
            report['phases'][1]['completion_interval']['interval_consumed_count'] = value
            rebind(rows[0], report)
            with self.subTest(count=value), self.assertRaises(current.CalibrationError):
                current.evaluate(self.plan, rows)

    def test_original_report_json_must_be_unambiguous(self):
        for suffix in (',"capture_ordinal":0}', ',"unexpected":NaN}'):
            rows = copy.deepcopy(self.records)
            text = rows[0]['report_utf8_bytes'].rstrip()[:-1] + suffix
            rows[0].update(report_utf8_bytes=text, report_binding=binding('report-0', text.encode()))
            with self.subTest(suffix=suffix), self.assertRaises(current.CalibrationError):
                current.evaluate(self.plan, rows)


if __name__ == '__main__':
    unittest.main()
