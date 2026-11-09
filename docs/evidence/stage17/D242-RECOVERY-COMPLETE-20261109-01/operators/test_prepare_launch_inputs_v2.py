import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'tools'), str(HERE.parent/'d242-admin-1')]
spec = importlib.util.spec_from_file_location('fixed_preparation', HERE/'prepare_launch_inputs_v2.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
import stage17_q16a_continuation_admission_v1 as admission


class MetadataTests(unittest.TestCase):
    def test_original_receipt_pinned_and_decimal_retained(self):
        path = ROOT/'docs/evidence/stage17/Q16A-PREFIX-COMPLETE-E25-20261109-01/analysis-process-result.json'
        raw = path.read_bytes(); binding = dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        reader = admission.BoundReader()
        with self.assertRaises(ValueError): reader.document(binding)
        reader = admission.BoundReader()
        result = module.load_analysis_completion(reader,binding); reader.finish()
        self.assertEqual(result['elapsed_seconds'],47838.16341974295)
        self.assertEqual(path.read_bytes(),raw)

    def test_failures_or_incomplete_cleanup_still_rejected(self):
        original = json.loads((ROOT/'docs/evidence/stage17/Q16A-PREFIX-COMPLETE-E25-20261109-01/analysis-process-result.json').read_bytes())
        class Reader:
            def read(self, binding): return binding
        for field,value in [('status','FAILED'),('exit_code',1),('exit_code',False),
            ('all_own_children_reaped',False),('raw_mutation',True),('execution_authority',True),
            ('elapsed_seconds',float('inf')),('elapsed_seconds',-1),('elapsed_seconds',True)]:
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                module.load_analysis_completion(Reader(),json.dumps(dict(original,**{field:value})).encode())

    def test_scientific_float_plan_contract_remains_unchanged(self):
        with self.assertRaises(ValueError): admission._json(b'{"measurement_ns":1.5}')


if __name__=='__main__':unittest.main()
