"""D230 synthetic report mathematics; no family collection or hardware claim.

Actual small D220/D229 fixtures check report-shape compatibility. Complete
families below deliberately contain constructed software report summaries;
they are not claims that thousands of raw captures were produced or admitted.
"""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_calibration_v1 as cal
from test_stage17_formal_ring_plan_v1 import plan_fixture as ring_plan
from test_stage17_formal_plan_v1 import plan_fixture as service_plan
from test_stage17_q16a_capture_validation_v1 import Fixture as RingCapture
from test_stage17_formal_service_capture_validation_v1 import Fixture as ServiceCapture


def binding(name,raw=b'synthetic source binding'):
    return dict(artifact_id=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def record(capture,report,validity='VALID'):
    raw=cal.canonical(report)
    return dict(capture_ordinal=capture['ordinal'],measurement_run_id=capture['measurement']['run_id'],
        validity=validity,report_binding=binding(f'capture-report-{capture["ordinal"]}',raw),
        report_utf8_bytes=raw.decode())


def rebind(row,report):
    raw=cal.canonical(report);row['report_utf8_bytes']=raw.decode()
    row['report_binding']=binding(row['report_binding']['artifact_id'],raw)


def failure(plan,capture,action):
    return dict(schema_version=cal.FAILURE_SCHEMA_ID,action_id=action,method_id=cal.METHOD[action],
        capture_ordinal=capture['ordinal'],warmup_run_id=capture['warmup']['run_id'],
        measurement_run_id=capture['measurement']['run_id'],plan_sha256=hashlib.sha256(cal.canonical(plan)).hexdigest(),
        source_revision=plan['source_revision'],error=dict(type='ValidationError',message='synthetic integrity rejection'),
        input_bindings=dict(native_input=binding('input'),control=binding('control'),final=binding('final'),
                            raw_artifacts=[binding('raw-'+str(i)) for i in range(8 if action=='Q16a' else 5)]),
        execution_authority=False,phase18_authority=False)


class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='d230-report-shapes-');cls.addClassCleanup(cls.tmp.cleanup)
        cls.prototypes={}
        cls.fixtures={}
        for action,kind in (('Q16a',RingCapture),('Q16b',ServiceCapture)):
            root=pathlib.Path(cls.tmp.name)/action;root.mkdir()
            fixture=kind(root);cls.fixtures[action]=fixture;cls.prototypes[action]=fixture.run()
        cls.plans={};cls.records={};cls.geometry=[];cls.results={}
        for action in ('Q16a','Q16b'):
            plan,records,geometry=cls.make_family(action)
            cls.plans[action]=plan;cls.records[action]=records
            if geometry is not None:cls.geometry=geometry
            cls.results[action]=cal.evaluate(action,plan,records,geometry)

    @classmethod
    def make_family(cls,action,repetitions=59):
        if action=='Q16a':
            if repetitions!=59:raise ValueError('fixture uses accepted 59-run ring base')
            plan=ring_plan();plan['minimum_observations_per_series']=1
            for item in plan['captures']:
                item['capture']['minimum_observations_per_series']=1
                item['capture']['geometry']['capacity']=1024
        else:
            plan=service_plan('Q16b',repetitions)
            for item in plan['captures']:
                for phase,rows in zip(item['capture']['budget']['phases'],item['resources']['phase_capacity'],strict=True):
                    phase['producer_attempt_limit']=phase['consumer_poll_limit']=100
                    rows['producer_primary_rows']=rows['consumer_primary_rows']=100
                item['execution_budget']['max_output_bytes']=100000
            plan['budget']['max_output_bytes']=len(plan['captures'])*100000+plan['budget']['metadata_output_bytes']
            plan['budget']['required_free_disk_bytes']=plan['budget']['max_output_bytes']+2000000
        records=[]
        for item in plan['captures']:
            capture=item['capture'];report=copy.deepcopy(cls.prototypes[action])
            report['capture_ordinal']=capture['ordinal']
            for i,name in enumerate(('warmup','measurement')):
                phase=report['phases'][i];phase['run_id']=capture[name]['run_id']
                if action=='Q16a':
                    for role,decoded in phase['demand'].items():
                        decoded['run_id']=phase['run_id']
                        if i==1:
                            # Scaled accepted C++ ring_fixture vectors; common
                            # 1000 factor preserves the exact distance ratios.
                            high=100000 if capture['ordinal']==0 else 17000
                            decoded['demand_p999']['value_ticks']=high if role=='producer' else 20000
                            decoded['issue_p001']['value_ticks']=4000
            if action=='Q16b':
                phase=report['phases'][1]
                phase['counts'].update(attempted=100,accepted=100,full=0,consumed_including_drain=100)
                inside=80 if capture['ordinal']==0 else 100
                phase['completion_interval'].update(consumed_count=100,interval_consumed_count=inside,
                                                    outside_interval_consumed_count=100-inside)
            records.append(record(capture,report))
        geometry=None
        if action=='Q16a':
            geometry=[dict(context_ordinal=i,capacity=1024,cache_line_bytes=64,slot_storage_bytes=8192,
                           source_binding=binding('native-layout-'+str(i))) for i in range(6)]
        return plan,records,geometry

    def test_actual_D220_D229_report_shapes_normalize_without_raw_reanalysis(self):
        for action,fixture in self.fixtures.items():
            summary=cal._valid_summary(action,self.prototypes[action],fixture.capture,fixture.resources)
            self.assertEqual(summary['duration_ticks'],fixture.capture['measurement_ns']*1000)
            if action=='Q16b':
                self.assertEqual(summary['completion_count'],3)
                self.assertEqual(summary['consumed_including_drain'],4)
                self.assertEqual(summary['throughput'],dict(numerator=3,denominator=1))

    def test_complete_families_match_accepted_cpp_known_vectors(self):
        service=self.results['Q16b'];self.assertEqual(service['status'],'VALIDATED')
        self.assertEqual(len(service['derived_result']['cells']),60)
        self.assertEqual(service['derived_result']['mu_ref'],dict(numerator=80,denominator=1))
        self.assertEqual(service['derived_result']['candidate_loads'],[dict(numerator=n,denominator=1) for n in (20,40,60)])
        ring=self.results['Q16a'];self.assertEqual(ring['status'],'VALIDATED')
        contexts=ring['derived_result']['contexts'];self.assertEqual(len(contexts),6)
        self.assertEqual(contexts[0]['limits']['ell_star_ticks'],100000)
        self.assertEqual(contexts[0]['limits']['c_star_ticks'],4000)
        self.assertEqual(contexts[0]['distance']['d2_cache_lines'],4)
        self.assertEqual(contexts[0]['distance']['producer_distance_slots'],32)
        self.assertEqual(contexts[0]['distance']['consumer_distance_slots'],32)
        self.assertEqual(contexts[-1]['distance']['d2_cache_lines'],2)
        for action,result in self.results.items():
            self.assertFalse(result['execution_authority']);self.assertFalse(result['phase18_authority'])
            self.assertEqual(result['plan_sha256'],hashlib.sha256(cal.canonical(self.plans[action])).hexdigest())
            self.assertTrue(cal.canonical(self.plans[action]).endswith(b'\n'))
            self.assertIs(cal.validate_calibration_record(result),result)

    def test_D035_invalid58_of59_unresolved_but59_of60_valid_no_topup(self):
        plan,records,_=self.make_family('Q16b')
        records[0]=record(plan['captures'][0]['capture'],failure(plan,plan['captures'][0]['capture'],'Q16b'),'INVALID')
        result=cal.evaluate('Q16b',plan,records)
        self.assertEqual(result['status'],'UNRESOLVED');self.assertIsNone(result['derived_result']['mu_ref'])
        self.assertEqual(result['derived_result']['cells'][0]['valid_runs'],58)
        self.assertEqual(result['run_sources'][0]['validity'],'INVALID')
        self.assertIsNone(result['run_sources'][0]['summary'])
        plan,records,_=self.make_family('Q16b',60)
        records[0]=record(plan['captures'][0]['capture'],failure(plan,plan['captures'][0]['capture'],'Q16b'),'INVALID')
        result=cal.evaluate('Q16b',plan,records)
        self.assertEqual(result['status'],'VALIDATED')
        self.assertEqual(result['derived_result']['cells'][0]['valid_runs'],59)
        self.assertEqual(result['derived_result']['mu_ref'],dict(numerator=100,denominator=1))
        records.pop(0)  # Still 59 valid results, but the planned receipt is absent.
        result=cal.evaluate('Q16b',plan,records)
        self.assertEqual(result['status'],'UNRESOLVED')
        self.assertEqual(result['derived_result']['cells'][0]['valid_runs'],59)
        self.assertEqual(result['derived_result']['cells'][0]['missing_runs'],1)
        self.assertIsNone(result['derived_result']['mu_ref'])
        self.assertEqual(result['run_sources'][0]['validity'],'MISSING')
        tampered=copy.deepcopy(result)
        tampered['status']='VALIDATED'
        with self.assertRaises(cal.CalibrationError):cal.validate_calibration_record(tampered)

    def test_D037_missing_or_invalid_run_remains_unresolved(self):
        for invalid in (False,True):
            records=copy.deepcopy(self.records['Q16a']);plan=self.plans['Q16a']
            if invalid:records[0]=record(plan['captures'][0]['capture'],failure(plan,plan['captures'][0]['capture'],'Q16a'),'INVALID')
            else:records.pop(0)
            result=cal.evaluate('Q16a',plan,records,self.geometry)
            self.assertEqual(result['status'],'UNRESOLVED')
            context=result['derived_result']['contexts'][0]
            self.assertEqual(context['states'][0]['valid_runs'],58)
            self.assertIsNone(context['distance'])
            self.assertEqual(result['run_sources'][0]['validity'],'INVALID' if invalid else 'MISSING')
            self.assertEqual(len(result['run_sources']),708)

    def test_valid_zero_rate_and_FULL_remain_separate_from_validity(self):
        records=copy.deepcopy(self.records['Q16b']);first=json.loads(records[0]['report_utf8_bytes'])
        first['phases'][1]['completion_interval'].update(interval_consumed_count=0,outside_interval_consumed_count=100)
        rebind(records[0],first)
        result=cal.evaluate('Q16b',self.plans['Q16b'],records)
        self.assertEqual(result['status'],'VALIDATED')
        self.assertEqual(result['derived_result']['mu_ref'],dict(numerator=0,denominator=1))
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'],'PASS')
        first['phases'][1]['counts'].update(accepted=99,full=1,consumed_including_drain=99)
        first['phases'][1]['zero_loss']=False;first['measurement_zero_loss']=False;first['zero_loss_all_phases']=False
        first['phases'][1]['completion_interval'].update(consumed_count=99,outside_interval_consumed_count=99)
        rebind(records[0],first)
        result=cal.evaluate('Q16b',self.plans['Q16b'],records)
        self.assertEqual(result['status'],'VALIDATED')
        self.assertEqual(result['derived_result']['measurement_zero_loss_gate'],'FAIL')
        self.assertEqual(result['derived_result']['mu_ref'],dict(numerator=0,denominator=1))

    def test_duplicate_unplanned_and_mismatched_run_membership_rejected(self):
        plan=self.plans['Q16a']
        for mutation in ('duplicate','extra','wrong_id'):
            rows=copy.deepcopy(self.records['Q16a'])
            if mutation=='duplicate':rows.append(copy.deepcopy(rows[0]))
            elif mutation=='extra':rows.append(dict(rows[0],capture_ordinal=708))
            else:rows[0]['measurement_run_id']='not-planned'
            with self.subTest(mutation=mutation),self.assertRaises(cal.CalibrationError):
                cal.evaluate('Q16a',plan,rows,self.geometry)

    def test_original_report_bytes_and_no_duplicate_json_or_boolean_exclusion(self):
        original=copy.deepcopy(self.records['Q16a'])
        for mutation in ('hash','size','duplicate_key','float','invalid_boolean','invalid_without_failure'):
            with self.subTest(mutation=mutation):
                rows=copy.deepcopy(original)
                if mutation=='hash':rows[0]['report_binding']['sha256']='0'*64
                elif mutation=='size':rows[0]['report_binding']['size_bytes']+=1
                elif mutation=='duplicate_key':
                    text=rows[0]['report_utf8_bytes'].rstrip();text=text[:-1]+',"capture_ordinal":0}\n'
                    rows[0]['report_utf8_bytes']=text;rows[0]['report_binding']=binding('capture-report-0',text.encode())
                elif mutation=='float':
                    report=json.loads(rows[0]['report_utf8_bytes']);report['capture_ordinal']=0.0;rebind(rows[0],report)
                elif mutation=='invalid_boolean':rows[0]['validity']=False
                else:rows[0]['validity']='INVALID'
                with self.assertRaises(cal.CalibrationError):cal.evaluate('Q16a',self.plans['Q16a'],rows,self.geometry)

    def test_failure_requires_source_identity_error_and_bound_raw_inputs(self):
        plan=self.plans['Q16a'];capture=plan['captures'][0]['capture'];original=failure(plan,capture,'Q16a')
        for mutation in ('method','plan','revision','run','raw_missing','error_missing','authority'):
            with self.subTest(mutation=mutation):
                report=copy.deepcopy(original)
                if mutation=='method':report['method_id']='old-method'
                elif mutation=='plan':report['plan_sha256']='0'*64
                elif mutation=='revision':report['source_revision']='0'*40
                elif mutation=='run':report['measurement_run_id']='wrong'
                elif mutation=='raw_missing':report['input_bindings']['raw_artifacts'].pop()
                elif mutation=='error_missing':report['error']['message']=''
                else:report['execution_authority']=True
                with self.assertRaises((cal.CalibrationError,cal.ContractError)):
                    cal._failure(report,'Q16a',hashlib.sha256(cal.canonical(plan)).hexdigest(),plan,capture)

    def test_valid_report_required_evidence_flags_origins_ranks_and_minimum(self):
        fixture=self.fixtures['Q16a'];original=self.prototypes['Q16a']
        for mutation in ('schema','ordinal','run','reconciliation','execution','authority','rank','minimum','clock'):
            with self.subTest(mutation=mutation):
                report=copy.deepcopy(original)
                if mutation=='schema':report['schema_version']='legacy'
                elif mutation=='ordinal':report['capture_ordinal']+=1
                elif mutation=='run':report['phases'][1]['run_id']='wrong'
                elif mutation=='reconciliation':report['raw_reconciliation_validated']=False
                elif mutation=='execution':report['capture_execution_evidence_validated']=False
                elif mutation=='authority':report['phase18_authority']=True
                elif mutation=='rank':report['phases'][1]['demand']['producer']['demand_p999']['rank']-=1
                elif mutation=='minimum':report['minimum_observations_per_series']+=1
                else:report['phases'][1]['demand']['producer']['phase_window']['ticks_per_second']=1000
                with self.assertRaises((cal.CalibrationError,cal.ContractError,cal.raw.DecodeError)):
                    cal._valid_summary('Q16a',report,fixture.capture,fixture.resources)

    def test_semantic_record_gate_rejects_derived_tampering_and_bool_counts(self):
        for action in ('Q16a','Q16b'):
            for mutation in ('derived','count_bool','source_duplicate','status','authority','method'):
                with self.subTest(action=action,mutation=mutation):
                    doc=copy.deepcopy(self.results[action])
                    if mutation=='derived':
                        if action=='Q16a':doc['derived_result']['contexts'][0]['distance']['consumer_distance_slots']+=1
                        else:doc['derived_result']['mu_ref']['numerator']+=1
                    elif mutation=='count_bool':
                        doc['derived_result']['contexts' if action=='Q16a' else 'cells'][0]['context_ordinal' if action=='Q16a' else 'cell_ordinal']=False
                    elif mutation=='source_duplicate':doc['run_sources'][1]['measurement_run_id']=doc['run_sources'][0]['measurement_run_id']
                    elif mutation=='status':doc['status']='UNRESOLVED'
                    elif mutation=='authority':doc['execution_authority']=True
                    else:doc['method_id']='old-method'
                    with self.assertRaises(cal.CalibrationError):cal.validate_calibration_record(doc)

    def test_native_slot_bytes_not_invented_and_cap_collapse_is_unresolved(self):
        for mutation in ('missing','nonmultiple','wrong_line','wrong_capacity'):
            geometry=copy.deepcopy(self.geometry)
            if mutation=='missing':geometry.pop()
            elif mutation=='nonmultiple':geometry[0]['slot_storage_bytes']+=1
            elif mutation=='wrong_line':geometry[0]['cache_line_bytes']=128
            else:geometry[0]['capacity']=512
            with self.subTest(mutation=mutation),self.assertRaises((cal.CalibrationError,cal.ContractError)):
                cal._geometry(geometry,self.plans['Q16a'])
        doc=copy.deepcopy(self.results['Q16a'])
        doc['ring_geometry'][0].update(capacity=32,slot_storage_bytes=256)
        status,derived=cal._derive('Q16a',doc['prospective'],doc['run_sources'],doc['ring_geometry'])
        self.assertEqual(status,'UNRESOLVED')
        self.assertIsNone(derived['contexts'][0]['distance']['producer_distance_slots'])
        self.assertEqual(derived['contexts'][0]['distance']['cap_lines'],1)

    def test_exact_arithmetic_cpp_vectors_uint64_boundary_and_overflow(self):
        self.assertEqual(cal.exact_throughput(3,100,20),dict(numerator=15,denominator=1))
        self.assertEqual(cal.exact_throughput(cal.MAX_U64,cal.MAX_U64,cal.MAX_U64),dict(numerator=cal.MAX_U64,denominator=1))
        self.assertEqual(cal.exact_throughput(0,10**12,1),dict(numerator=0,denominator=1))
        for values in ((cal.MAX_U64,cal.MAX_U64,1),(1,1,0),(True,1,1)):
            with self.assertRaises(cal.ContractError):cal.exact_throughput(*values)
        self.assertEqual(cal.ring_distance(100,4,1024,64,8)[0]['producer_distance_slots'],32)
        self.assertEqual(cal.ring_distance(cal.MAX_U64,1,1024,64,8)[0]['producer_distance_slots'],256)
        self.assertEqual(cal.ring_distance(100,4,128,64,8)[0]['d2_cache_lines'],4)
        self.assertIsNotNone(cal.ring_distance(100,4,32,64,8)[1])
        for values in ((100,0,1024,64,8),(1<<64,1,1024,64,8)):
            with self.assertRaises(cal.ContractError):cal.ring_distance(*values)


if __name__=='__main__':unittest.main(verbosity=2)
