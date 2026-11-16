"""Exact mixed-family minima and report identities; synthetic software evidence."""
import copy
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_calibration_v1 as current
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture
from test_stage17_formal_service_daycap_v1 import record,rebind
from test_stage17_formal_service_capture_validation_v1 import Fixture


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=parent_fixture();cls.plan=continuation_fixture(cls.parent)
        with tempfile.TemporaryDirectory() as directory:prototype=Fixture(pathlib.Path(directory)).run()
        def rows(items):
            result=[]
            for item in items:
                capture=item['capture'];report=copy.deepcopy(prototype);report['capture_ordinal']=capture['ordinal']
                for phase,name in zip(report['phases'],('warmup','measurement'),strict=True):phase['run_id']=capture[name]['run_id']
                result.append(record(capture,report))
            return result
        cls.retained=rows(cls.parent['captures'][:17]);cls.new=rows(cls.plan['captures']);cls.original=rows(cls.parent['captures'])

    def test_all60_exact_minima_match_original_method_without_mutating_any_report(self):
        before=copy.deepcopy((self.retained,self.new))
        result=current.evaluate(self.parent,self.plan,self.retained,self.new)
        baseline=current.original.evaluate(self.parent,self.original)
        self.assertEqual(result['derived_result'],baseline['derived_result'])
        self.assertEqual(result['status'],'DESCRIPTIVE')
        self.assertFalse(result['tolerance_guarantee']);self.assertFalse(result['execution_authority'])
        self.assertEqual(before,(self.retained,self.new))
        self.assertEqual([r['planned_captures'] for r in result['source_populations']],[17,103])
        source=result['run_sources'][17]
        self.assertEqual((source['original_capture_ordinal'],source['capture_ordinal']),(17,0))
        self.assertEqual(source['measurement_run_id'],self.plan['captures'][0]['capture']['measurement']['run_id'])

    def test_missing_source_report_stays_unresolved_and_never_gets_a_replacement(self):
        result=current.evaluate(self.parent,self.plan,self.retained,self.new[:-1])
        self.assertEqual(result['status'],'UNRESOLVED');self.assertIsNone(result['derived_result']['min_mu_ref'])
        self.assertEqual(sum(r['missing_runs'] for r in result['derived_result']['cells']),1)

    def test_duplicate_or_relabelled_local_ordinal_rejected(self):
        for rows in (self.new+[self.new[0]],copy.deepcopy(self.new)):
            if len(rows)==103:rows[0]['capture_ordinal']=17
            with self.assertRaises(current.reports.CalibrationError):
                current.evaluate(self.parent,self.plan,self.retained,rows)

    def test_original_id_cannot_replace_a_fresh_source_id(self):
        rows=copy.deepcopy(self.new);rows[0]['measurement_run_id']=self.parent['captures'][17]['capture']['measurement']['run_id']
        with self.assertRaises(current.reports.CalibrationError):current.evaluate(self.parent,self.plan,self.retained,rows)

    def test_genuine_zero_is_retained_as_exact_zero(self):
        rows=copy.deepcopy(self.new);document=current.reports.json.loads(rows[0]['report_utf8_bytes'])
        interval=document['phases'][1]['completion_interval'];interval['interval_consumed_count']=0;interval['outside_interval_consumed_count']=interval['consumed_count']
        rebind(rows[0],document)
        result=current.evaluate(self.parent,self.plan,self.retained,rows)
        self.assertEqual(result['status'],'DESCRIPTIVE')
        self.assertEqual(result['derived_result']['min_mu_ref'],dict(numerator=0,denominator=1))


if __name__=='__main__':unittest.main()
