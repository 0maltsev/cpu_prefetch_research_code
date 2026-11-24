"""Synthetic normalized reports exercise composition, not scientific provenance."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_q16c_descriptive_calibration_v1 as current
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


def reports(plan, full_ordinal=None):
    result = []
    for item in plan['captures']:
        capture = item['capture']; phases = []
        for i, name in enumerate(('warmup', 'measurement')):
            count = capture['schedules'][i]['offered_count']
            full = int(i == 1 and capture['ordinal'] == full_ordinal)
            phases.append(dict(phase=name, run_id=capture[name]['run_id'], counts=dict(offered=count,
                attempted=count, accepted=count-full, full=full, consumed_including_drain=count-full), zero_loss=not full))
        report = dict(schema_version=current.raw_validator.SCHEMA_ID, action_id='Q16c',
            method_id=current.contract.COLLECTOR_METHOD, capture_ordinal=capture['ordinal'],
            source_versions=current.raw_validator.SOURCE_VERSIONS, phases=phases,
            raw_reconciliation_validated=True, capture_execution_evidence_validated=True,
            family_validity_established=False, measurement_zero_loss=phases[1]['zero_loss'],
            zero_loss_all_phases=all(p['zero_loss'] for p in phases), execution_authority=False, phase18_authority=False)
        raw = current.archive.canonical(report)
        result.append(dict(capture_ordinal=capture['ordinal'], validity='VALID', report_utf8_bytes=raw,
            report_binding=dict(artifact_id='synthetic-report-'+str(capture['ordinal']),
                                size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())))
    return result


class CompositionTests(unittest.TestCase):
    def setUp(self): self.plan = plan_fixture()

    def test_complete_coverage_has_no_formal_confidence_or_scale_selection(self):
        r = current.evaluate(self.plan, reports(self.plan))
        self.assertEqual(r['status'], 'DESCRIPTIVE_COMPLETE')
        self.assertEqual(r['coverage'], dict(planned=180, valid=180, invalid=0, missing=0))
        self.assertIsNone(r['confidence_claim']); self.assertIsNone(r['final_scale_selection'])
        self.assertEqual(r['final_matrix_feasibility'], 'NOT_EVALUATED')
        self.assertFalse(r['execution_authority']); self.assertFalse(r['phase18_authority'])

    def test_valid_full_remains_complete_and_fails_separate_measurement_gate(self):
        r = current.evaluate(self.plan, reports(self.plan, full_ordinal=17))
        self.assertEqual(r['status'], 'DESCRIPTIVE_COMPLETE')
        self.assertEqual(r['observed_zero_loss']['measurement'],
            dict(zero_loss_gate='FAIL', full_bearing_capture_ordinals=[17]))
        self.assertEqual(r['run_sources'][17]['validity'], 'VALID')
        self.assertEqual(r['run_sources'][17]['phases'][1]['counts']['full'], 1)

    def test_missing_or_invalid_never_makes_complete_and_original_binding_is_retained(self):
        rows = reports(self.plan); failure = b'{"synthetic_failure":true}'
        rows[17].update(validity='INVALID', report_utf8_bytes=failure,
            report_binding=dict(artifact_id='synthetic-failure-17', size_bytes=len(failure), sha256=hashlib.sha256(failure).hexdigest()))
        rows.pop()
        r = current.evaluate(self.plan, rows)
        self.assertEqual(r['status'], 'INCOMPLETE')
        self.assertEqual(r['coverage'], dict(planned=180, valid=178, invalid=1, missing=1))
        self.assertEqual(r['run_sources'][17]['report_binding'], rows[17]['report_binding'])
        self.assertEqual(r['observed_zero_loss']['measurement']['zero_loss_gate'], 'NOT_ESTABLISHED')

    def test_duplicate_unplanned_hash_or_unreconciled_count_rejected(self):
        for mutation in ('duplicate', 'unplanned', 'hash', 'counts'):
            rows = reports(self.plan)
            if mutation == 'duplicate': rows[-1] = copy.deepcopy(rows[0])
            elif mutation == 'unplanned': rows[-1]['capture_ordinal'] = 180
            elif mutation == 'hash': rows[0]['report_binding']['sha256'] = '0' * 64
            else:
                report = current.admission._json(rows[0]['report_utf8_bytes'])
                report['phases'][1]['counts']['consumed_including_drain'] += 1
                raw = current.archive.canonical(report); rows[0]['report_utf8_bytes'] = raw
                rows[0]['report_binding'].update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(mutation=mutation), self.assertRaises(current.Error): current.evaluate(self.plan, rows)


if __name__ == '__main__': unittest.main()
