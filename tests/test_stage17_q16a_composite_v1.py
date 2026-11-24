"""Synthetic D240 composition checks; these fixtures establish no custody."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'tools')]
import stage17_q16a_composite_v1 as composite
from test_stage17_formal_ring_continuation_v1 import parent_fixture, continuation_fixture
from test_stage17_formal_calibration_v1 import binding, record, rebind, failure
from test_stage17_q16a_capture_validation_v1 import Fixture


class CompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        cls.original=parent_fixture()
        cls.original['minimum_observations_per_series']=1
        for item in cls.original['captures']:item['capture']['minimum_observations_per_series']=1
        cls.suffix=continuation_fixture(cls.original)
        root=Path(cls.tmp.name);(root/'normal').mkdir();(root/'full').mkdir()
        cls.prototype=Fixture(root/'normal').run();cls.full=Fixture(root/'full',full=True).run()
        cls.geometry=[dict(context_ordinal=i,capacity=8,cache_line_bytes=64,slot_storage_bytes=512,
            source_binding=binding('software-geometry-'+str(i))) for i in range(6)]
        cls.prefix_records=cls.records(cls.original,177,'original')
        cls.suffix_records=cls.records(cls.suffix,531,'suffix')

    @classmethod
    def records(cls,plan,count,leg):
        result=[]
        for item in plan['captures'][:count]:
            c=item['capture'];p=copy.deepcopy(cls.prototype);p['capture_ordinal']=c['ordinal']
            for i,name in enumerate(('warmup','measurement')):
                phase=p['phases'][i];phase['run_id']=c[name]['run_id']
                for role,d in phase['demand'].items():
                    d['run_id']=phase['run_id']
                    if i==1:
                        d['demand_p999']['value_ticks']=100000 if leg=='original' and c['ordinal']==0 else 20000
                        d['issue_p001']['value_ticks']=4000
            row=record(c,p);row['report_binding']['artifact_id']=leg+'-'+str(c['ordinal']);result.append(row)
        return result

    def calculate(self,prefix=None,suffix=None):
        return composite._evaluate(self.original,self.suffix,
            self.prefix_records if prefix is None else prefix,self.suffix_records if suffix is None else suffix,self.geometry)

    def test_original_identities_and_known_exact_math_preserved(self):
        before=copy.deepcopy((self.original,self.suffix,self.prefix_records,self.suffix_records))
        d=self.calculate();self.assertEqual(d['status'],'VALIDATED')
        self.assertEqual(len(d['run_sources']),708)
        self.assertEqual(d['run_sources'][177]['local_capture_ordinal'],0)
        self.assertEqual(d['run_sources'][177]['original_slot'],177)
        self.assertEqual(d['run_sources'][177]['measurement_run_id'],self.suffix['captures'][0]['capture']['measurement']['run_id'])
        self.assertEqual(d['run_sources'][0]['source_revision'],self.original['source_revision'])
        self.assertEqual(d['run_sources'][177]['source_revision'],self.suffix['source_revision'])
        self.assertEqual(d['derived_result']['contexts'][0]['limits']['ell_star_ticks'],100000)
        self.assertEqual(d['derived_result']['contexts'][0]['limits']['c_star_ticks'],4000)
        self.assertEqual(d['derived_result']['contexts'][0]['distance']['d2_cache_lines'],2)
        self.assertEqual(d['derived_result']['measurement_zero_loss_gate'],'PASS')
        for field in ('producer_authentication_established','family_validity_established','execution_authority','phase18_authority'):
            self.assertFalse(d[field])
        self.assertEqual((self.original,self.suffix,self.prefix_records,self.suffix_records),before)

    def test_missing_suffix_remains_unresolved_without_padding(self):
        d=self.calculate(suffix=self.suffix_records[:-1])
        self.assertEqual(d['status'],'UNRESOLVED')
        self.assertEqual(d['run_sources'][-1]['validity'],'MISSING')
        self.assertIsNone(d['run_sources'][-1]['summary'])
        self.assertEqual(d['derived_result']['contexts'][-1]['states'][1]['valid_runs'],58)

    def test_reconciled_full_is_retained_and_fails_only_its_separate_gate(self):
        rows=copy.deepcopy(self.prefix_records);p=copy.deepcopy(self.full)
        c=self.original['captures'][0]['capture'];p['capture_ordinal']=0
        for i,name in enumerate(('warmup','measurement')):
            p['phases'][i]['run_id']=c[name]['run_id']
            for d in p['phases'][i]['demand'].values():d['run_id']=c[name]['run_id']
        rebind(rows[0],p);d=self.calculate(prefix=rows)
        self.assertEqual(d['status'],'VALIDATED')
        self.assertEqual(d['run_sources'][0]['validity'],'VALID')
        self.assertEqual(d['derived_result']['measurement_zero_loss_gate'],'FAIL')

    def test_invalid_original_report_remains_bound_and_unresolved(self):
        rows=copy.deepcopy(self.prefix_records);c=self.original['captures'][0]['capture']
        p=failure(self.original,c,'Q16a')
        p['plan_sha256']=hashlib.sha256(composite.canonical(self.original)).hexdigest()
        rows[0]['validity']='INVALID';rebind(rows[0],p);d=self.calculate(prefix=rows)
        self.assertEqual(d['status'],'UNRESOLVED')
        self.assertEqual(d['run_sources'][0]['failure'],p)
        self.assertIsNone(d['run_sources'][0]['summary'])

    def test_report_corruption_identity_alias_and_topup_rejected(self):
        for mutation in ('bytes','identity','report_id','duplicate','out_of_range'):
            rows=copy.deepcopy(self.suffix_records)
            if mutation=='bytes':rows[0]['report_utf8_bytes']+=' '
            if mutation=='identity':rows[0]['measurement_run_id']=self.prefix_records[0]['measurement_run_id']
            if mutation=='report_id':rows[0]['report_binding']['artifact_id']=self.prefix_records[0]['report_binding']['artifact_id']
            if mutation=='duplicate':rows.append(copy.deepcopy(rows[0]))
            if mutation=='out_of_range':rows[0]['capture_ordinal']=531
            with self.subTest(mutation=mutation),self.assertRaises((composite.CompositeError,composite.calibration.ContractError)):self.calculate(suffix=rows)

    def test_source_plan_mismatch_and_changed_context_rejected(self):
        for key,value in [('measurement_ns',2),('stand_id','other')]:
            p=copy.deepcopy(self.suffix);p[key]=value
            with self.assertRaises((composite.CompositeError,composite.calibration.ContractError)):composite._evaluate(self.original,p,self.prefix_records,self.suffix_records,self.geometry)
        p=copy.deepcopy(self.suffix);p['captures'][0]['capture']['context_ordinal']=0
        with self.assertRaises(composite.CompositeError):composite._evaluate(self.original,p,self.prefix_records,self.suffix_records,self.geometry)

    def test_public_boundary_keeps_the_accepted_incident_constraints(self):
        # The mathematical fixture's lowered observation minimum cannot pass
        # as the immutable collected experiment, even with new byte bindings.
        raw=composite.canonical(self.original)
        for data in (raw,raw+b' ',b'{}',None):
            with self.assertRaises(composite.CompositeError):
                composite.evaluate(data,self.suffix,self.prefix_records,self.suffix_records,self.geometry)


if __name__=='__main__':unittest.main()
