"""Independent scheduled-source/primary reconciliation on small retained fixtures."""
import copy
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_formal_scheduled_capture_validation_v2 as current
import stage17_formal_service_capture_validation_v1 as historical
from test_stage17_formal_service_capture_validation_v1 import Fixture


class SourceCaptureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='q16c-sources-raw-')
        self.addCleanup(self.directory.cleanup); self.root = Path(self.directory.name)

    def fixture(self, full=False):
        f = Fixture(self.root, scheduled=True, full=full)
        self.original = copy.deepcopy(f.capture)
        f.capture['schema_version'] = 'cpu-prefetch-stage17-formal-scheduled-capture/2'
        for i, source in enumerate(f.capture['schedules']):
            values = source.pop('deadline_ticks')
            source['storage_format'] = 'SEALED_U64BE_ORIGINAL-v1'
            source['source_artifact']['sha256'] = hashlib.sha256(struct.pack('>' + str(len(values)) + 'Q', *values)).hexdigest()
            f.control['schedules'][i]['prospective'] = copy.deepcopy(source)
        return f

    def run_capture(self, f):
        return current.validate_capture(f.root, f.control, f.final, f.capture, f.resources, f.monitoring, f.hardware)

    def test_original_source_reconstruction_and_every_independent_primary_row(self):
        f = self.fixture(); result = self.run_capture(f)
        self.assertTrue(result['raw_reconciliation_validated'])
        self.assertTrue(result['capture_execution_evidence_validated'])
        self.assertFalse(result['family_validity_established']); self.assertFalse(result['execution_authority'])
        self.assertEqual(result['action_id'], 'Q16c')
        self.assertEqual([p['counts']['offered'] for p in result['phases']], [4, 4])
        self.assertNotIn('deadline_ticks', f.capture['schedules'][0])
        with self.assertRaises(historical.ValidationError): f.run()

    def test_genuine_full_is_valid_with_separate_zero_loss_failure(self):
        result = self.run_capture(self.fixture(full=True))
        self.assertTrue(result['raw_reconciliation_validated'])
        self.assertFalse(result['measurement_zero_loss'])
        self.assertEqual(result['phases'][1]['counts']['full'], 1)

    def test_changed_original_hash_changed_arrival_and_fake_inline_array_rejected(self):
        for mutation in ['hash', 'arrival', 'inline']:
            f = self.fixture()
            if mutation == 'hash':
                f.capture['schedules'][1]['source_artifact']['sha256'] = '0' * 64
                f.control['schedules'][1]['prospective'] = copy.deepcopy(f.capture['schedules'][1])
            elif mutation == 'arrival':
                f.rows[(1, 'producer')][0][2] += 1; f.save_rows(1, 'producer'); f.sync()
            else: f.capture['schedules'][1]['deadline_ticks'] = [0] * 4
            with self.subTest(mutation=mutation), self.assertRaises(current.ValidationError): self.run_capture(f)


if __name__ == '__main__': unittest.main()
