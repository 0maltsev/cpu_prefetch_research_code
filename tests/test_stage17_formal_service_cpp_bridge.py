"""Actual typed C++ service/scheduled backends -> unchanged D229 input artifacts.

Scripted software phase driver and synthetic platform observations only; the
fixture never executes/qualifies the native persistent worker or a stand.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from test_stage17_formal_service_capture_validation_v1 import Fixture,v


class FormalServiceCppBridgeTests(unittest.TestCase):
    binary:pathlib.Path

    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='formal-service-cpp-bridge-');cls.addClassCleanup(cls.tmp.cleanup)
        cls.base=pathlib.Path(cls.tmp.name);cls.cases={}
        for scheduled in (False,True):
            for package in ('R0','L1'):
                name=('scheduled' if scheduled else 'service')+'-'+package
                seed=cls.base/(name+'-inputs');seed.mkdir()
                fixture=Fixture(seed,scheduled=scheduled)
                if package=='L1':
                    fixture.capture.update(package='L1',cell_ordinal=144 if scheduled else 48,
                        linked_order=dict(seed_id='node-seed',seed_hex='c'*64,namespace_id='node-namespace',arena_alignment_bytes=4096))
                config=cls.base/(name+'.json')
                config.write_text(json.dumps(dict(capture=fixture.capture,resources=fixture.resources,
                    monitoring=fixture.monitoring,hardware_control=fixture.hardware)))
                output=cls.base/(name+'-cpp')
                run=subprocess.run([str(cls.binary),'--mode','scheduled' if scheduled else 'service',str(config),str(output)],
                    capture_output=True,text=True,timeout=30)
                if run.returncode:raise AssertionError(f'{name}: C++ fixture exited {run.returncode}: {run.stderr}')
                control=json.loads((output/(fixture.action.lower()+f'-c{fixture.capture["ordinal"]}-control.json')).read_bytes())
                final=json.loads((output/'fixture-final-result.json').read_bytes())
                digests={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()}
                cls.cases[(scheduled,package)]=(fixture,output,control,final,digests)

    def validate(self,key,*,control=None,final=None,root=None,capture=None):
        f,path,c,r,_=self.cases[key]
        return v.validate_capture(path if root is None else root,c if control is None else control,r if final is None else final,
            f.capture if capture is None else capture,f.resources,f.monitoring,f.hardware)

    def test_actual_r0_l1_both_modes_pass_original_documents(self):
        for key,(fixture,output,control,final,digests) in self.cases.items():
            with self.subTest(key=key):
                result=self.validate(key)
                self.assertTrue(result['raw_reconciliation_validated']);self.assertTrue(result['capture_execution_evidence_validated'])
                self.assertTrue(result['measurement_zero_loss']);self.assertFalse(result['family_validity_established'])
                self.assertEqual(len(list(output.glob('*.bin'))),7 if key[0] else 5)
                self.assertEqual(result['phases'][1]['counts']['consumed_including_drain'],4)
                if key[0]:
                    self.assertNotIn('completion_interval',result['phases'][1])
                    self.assertEqual(result['phases'][1]['counts']['offered'],4)
                else:
                    interval=result['phases'][1]['completion_interval']
                    self.assertEqual(interval['interval_consumed_count'],3)
                    self.assertEqual(interval['outside_interval_consumed_count'],1)
                self.assertEqual(result['node_order']['count'],513 if key[1]=='L1' else 0)
                for phase in control['phases']:
                    self.assertIsNone(phase['consumer_last_append'])
                    self.assertEqual(phase['consumer_current']['status'],1)
                self.assertEqual(digests,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir()})

    def test_scheduled_mapped_sources_are_original_and_execution_is_distinct(self):
        for key,(f,output,control,final,_) in self.cases.items():
            if not key[0]:continue
            for index,row in enumerate(control['schedules']):
                self.assertTrue(row['prepared_available']);self.assertTrue(row['phase_released']);self.assertTrue(row['all_arrivals_attempted'])
                blob=(output/row['stream']['file_name']).read_bytes()
                self.assertEqual(row['stream']['sha256'],hashlib.sha256(blob).hexdigest());self.assertEqual(len(blob),32)
                self.assertNotIn('deadline_ticks',row['prospective'])
                state=final['session']['lifecycle']['phases'][index]
                self.assertFalse(state['producer']['deadline_reached'])
                self.assertTrue(state['producer']['arrivals_finished_published'])

    def test_duration_and_due_binding_mutants_rejected(self):
        for key,(f,_,control,_,_) in self.cases.items():
            capture=copy.deepcopy(f.capture);capture['measurement_ns']+=1
            with self.subTest(key=key),self.assertRaises(v.ValidationError):self.validate(key,capture=capture)
            if key[0]:
                capture=copy.deepcopy(f.capture);capture['schedules'][1]['deadline_ticks'][0]+=1000
                with self.assertRaises(v.ValidationError):self.validate(key,capture=capture)

    def test_mapped_source_extent_and_cleanup_mutants_rejected(self):
        for key,(_,_,control,final,_) in self.cases.items():
            bad=copy.deepcopy(final);bad['worker_mappings'][0]['unmap']['return_value']=-1
            with self.subTest(key=key),self.assertRaises(v.ValidationError):self.validate(key,final=bad)
            if key[0]:
                bad=copy.deepcopy(control);bad['schedule_mapping']['offsets'][1]=0
                with self.assertRaises(v.ValidationError):self.validate(key,control=bad)
            bad=copy.deepcopy(control);bad['worker_mappings'][0]['binding']['return_value']=-1
            with self.assertRaises(v.ValidationError):self.validate(key,control=bad)
            bad=copy.deepcopy(control);bad['phases'][1]['consumer_last_append']=0
            with self.assertRaisesRegex(v.ValidationError,'consumer append status'):self.validate(key,control=bad)

    def test_excluded_drain_raw_corruption_rejected_even_with_rehashed_binding(self):
        for key,(f,output,control,_,_) in self.cases.items():
            with tempfile.TemporaryDirectory(dir=self.base) as tmp:
                target=pathlib.Path(tmp)/'retained';shutil.copytree(output,target)
                bad=copy.deepcopy(control);binding=bad['phases'][1]['consumer'];path=target/binding['file_name']
                blob=bytearray(path.read_bytes())
                # Last little-endian action-completion tick: break exact ns/ps
                # conversion in the excluded drain row, retain its original size.
                blob[-8]^=1;path.write_bytes(blob);binding['sha256']=hashlib.sha256(blob).hexdigest()
                with self.subTest(key=key),self.assertRaises(v.ValidationError):self.validate(key,control=bad,root=target)

    def test_fixture_scope_never_claims_native_execution_or_qualification(self):
        for key,(_,output,_,_,_) in self.cases.items():
            scope=json.loads((output/'fixture-scope.json').read_bytes())
            self.assertTrue(scope['synthetic'])
            for flag in ('hardware_claim','execution_authority','production_worker','native_lifecycle_executed'):
                self.assertFalse(scope[flag])
            self.assertEqual(scope['raw_artifacts'],7 if key[0] else 5)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=pathlib.Path,required=True)
    args,rest=parser.parse_known_args();FormalServiceCppBridgeTests.binary=args.binary.resolve()
    unittest.main(argv=[sys.argv[0],*rest])
