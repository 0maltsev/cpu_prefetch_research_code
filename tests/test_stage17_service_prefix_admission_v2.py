"""Reproduce the real saved-manifest failure; preserve integer-only science."""
from decimal import Decimal
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_service_prefix_admission_v2 as current
import test_stage17_service_prefix_admission_v1 as original_capture_tests


class DiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=json.loads((ROOT/'docs/evidence/stage17/D261-CONTROL-READER-20261116-01/completed-analysis.json').read_bytes())
        row=next(v for k,v in data['files'].items() if k.endswith('/analysis-complete.json'))
        cls.raw=(json.dumps(row['document'],sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        assert len(cls.raw)==current.SIZE and hashlib.sha256(cls.raw).hexdigest()==current.SHA256

    def test_actual_unchanged_bytes_reproduce_original_live_failure(self):
        with self.assertRaisesRegex(current.previous.contract.ContractError,'floating-point'):
            current.previous.admission._json(self.raw)

    def test_only_exact_completed_diagnostic_accepts_exact_elapsed_decimals(self):
        document=current.software_diagnostic(self.raw)
        self.assertIsInstance(document['elapsed_seconds'],Decimal)
        self.assertEqual(document['captures'],17)
        self.assertTrue(all(type(row['ordinal']) is int and type(row['seconds']) is Decimal for row in document['reports']))
        self.assertEqual(document['elapsed_seconds'],Decimal('2012.731938508'))

    def test_changed_or_forged_diagnostic_is_rejected(self):
        for raw in (self.raw+b' ',self.raw.replace(b'2012.731938508',b'2012.731938509'),b'{"captures":17,"elapsed_seconds":1.0}'):
            with self.assertRaises(current.previous.admission.AdmissionError):current.software_diagnostic(raw)

    def test_bound_reader_authenticates_bytes_and_science_remains_integer_only(self):
        with tempfile.TemporaryDirectory() as name:
            path=pathlib.Path(name)/'diagnostic.json';path.write_bytes(self.raw)
            binding=dict(path=str(path),size_bytes=len(self.raw),sha256=current.SHA256)
            reader=current.DiagnosticReader();self.assertEqual(reader.document(binding)['captures'],17);reader.finish()
            scientific=b'{"counter":1.0}';path.write_bytes(scientific)
            binding.update(size_bytes=len(scientific),sha256=hashlib.sha256(scientific).hexdigest())
            with self.assertRaisesRegex(current.previous.contract.ContractError,'floating-point'):
                current.DiagnosticReader().document(binding)
            binding.update(size_bytes=current.SIZE,sha256=current.SHA256)
            with self.assertRaises(current.previous.admission.AdmissionError):current.DiagnosticReader().document(binding)

    def test_original_reader_and_admission_globals_remain_unchanged(self):
        self.assertIs(current.previous.admit.__globals__['admission'].BoundReader,current.previous.admission.BoundReader)
        self.assertIsNot(current.DiagnosticReader,current.previous.admission.BoundReader)
        with self.assertRaisesRegex(current.previous.contract.ContractError,'floating-point'):
            current.previous.admission._json(self.raw)

    def test_private_entry_still_rejects_a_missing_continuation(self):
        with self.assertRaisesRegex(KeyError,'continuation'):
            current.admit({},object())


class DiagnosticReaderCaptureTests(original_capture_tests.PrefixCaptureTests):
    """Run the real custody/codec failure cases through the corrected reader."""
    def verify(self):
        reader=current.DiagnosticReader()
        current.previous._capture(reader,self.row,self.parent,self.root)
        reader.finish()


if __name__=='__main__':unittest.main()
