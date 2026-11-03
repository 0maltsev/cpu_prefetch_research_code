"""Actual C++ publisher -> untouched full Python capture validation.

Real software R0 events/arena/streams; scripted clock and typed synthetic
platform observations. No native execution, hardware evidence, family validity
or qualification-worker role. Reuses the finite Python prospective fixture;
its Python-generated raw/control objects are never used as C++ output.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from test_stage17_q16a_capture_validation_v1 import Fixture, v


class FormalRingCppBridgeTests(unittest.TestCase):
    binary: pathlib.Path

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='formal-ring-cpp-bridge-')
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.base = pathlib.Path(cls.tmp.name)
        seed = cls.base / 'python-prospective-fixture'
        seed.mkdir()
        cls.fixture = Fixture(seed)
        cls.input = dict(capture=cls.fixture.capture, resources=cls.fixture.resources,
                         monitoring=cls.fixture.monitoring, hardware_control=cls.fixture.hardware)
        config = cls.base / 'input.json'
        config.write_text(json.dumps(cls.input), encoding='utf-8')
        cls.output = cls.base / 'cpp-output'
        result = subprocess.run([str(cls.binary), str(config), str(cls.output)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(f'C++ fixture exited {result.returncode}: {result.stderr}')
        cls.control_path = cls.output / f'q16a-c{cls.fixture.capture["ordinal"]}-control.json'
        cls.final_path = cls.output / 'fixture-final-result.json'
        cls.control = json.loads(cls.control_path.read_bytes())
        cls.final = json.loads(cls.final_path.read_bytes())
        cls.original = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in cls.output.iterdir()}

    def validate(self, control=None, final=None):
        f = self.fixture
        return v.validate_capture(self.output, self.control if control is None else control,
                                  self.final if final is None else final,
                                  f.capture, f.resources, f.monitoring, f.hardware)

    def test_actual_publisher_control_full_capture_positive(self):
        report = self.validate()
        self.assertTrue(report['raw_reconciliation_validated'])
        self.assertTrue(report['capture_execution_evidence_validated'])
        self.assertTrue(report['measurement_zero_loss'])
        self.assertTrue(report['zero_loss_all_phases'])
        self.assertFalse(report['family_validity_established'])
        self.assertFalse(report['execution_authority'])
        self.assertEqual(len(list(self.output.glob('*.bin'))), 8)
        for phase in report['phases']:
            self.assertEqual(phase['counts'],dict(attempted=4,accepted=4,full=0,
                consumed_including_drain=4,polls=5,empty=1))
        measured = report['phases'][1]['demand']
        self.assertEqual(measured['consumer']['counts']['outside_demand'],2)
        self.assertEqual(measured['consumer']['counts']['eligible_issue'],2)
        self.assertEqual(measured['producer']['demand_p999']['value_ticks'],1000)
        self.assertEqual(measured['consumer']['demand_p999']['value_ticks'],1000)
        self.assertEqual(self.original,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.output.iterdir()})

    def test_every_raw_binding_and_phase_contract_is_original_cpp(self):
        for i, phase in enumerate(self.control['phases']):
            for role in ('producer','consumer'):
                for key in (role,role+'_demand'):
                    reference = phase[key]
                    body = (self.output/reference['file_name']).read_bytes()
                    self.assertEqual(reference['size_bytes'],len(body))
                    self.assertEqual(reference['sha256'],hashlib.sha256(body).hexdigest())
                    self.assertEqual(set(reference),{'file_name','role','schema_identity','size_bytes','sha256'})
                contract = phase[role+'_demand_contract']
                self.assertEqual(contract['phase'],('warmup','measurement')[i])
                self.assertEqual(contract['role'],role)
                self.assertEqual(contract['run_id'],self.fixture.capture[contract['phase']]['run_id'])
                self.assertEqual(contract['phase_window']['phase_origin'],
                    self.final['session']['phases'][i]['origin_sample'])

    def test_missing_serialized_common_evidence_rejected(self):
        for key in ('thread_preparations','tls_snapshots','hardware_preparation',
                    'worker_mappings','worker_stacks','controls','residency','environment_samples'):
            mutant = copy.deepcopy(self.control);del mutant[key]
            with self.subTest(key=key),self.assertRaises(v.ValidationError):self.validate(control=mutant)

    def test_failed_final_cleanup_rejected(self):
        for key in ('core_mapping','monitor_mapping','controller_stack'):
            mutant=copy.deepcopy(self.final);mutant[key]['unmap']['return_value']=-1
            mutant[key]['unmap']['error_number']=5
            with self.subTest(key=key),self.assertRaises(v.ValidationError):self.validate(final=mutant)

    def test_actual_phase_contract_binding_mutant_rejected(self):
        mutant=copy.deepcopy(self.control)
        mutant['phases'][1]['consumer_demand_contract']['phase_window']['duration_ticks']+=1000
        with self.assertRaises(v.ValidationError):self.validate(control=mutant)

    def test_sidecar_cannot_be_confused_with_native_qualification(self):
        scope=json.loads((self.output/'fixture-scope.json').read_bytes())
        self.assertTrue(scope['synthetic'])
        for key in ('hardware_claim','execution_authority','production_worker','native_lifecycle_executed'):
            self.assertFalse(scope[key])
        self.assertEqual(scope['raw_artifacts'],8)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',type=pathlib.Path,required=True)
    args,remaining=parser.parse_known_args()
    FormalRingCppBridgeTests.binary=args.binary.resolve()
    unittest.main(argv=[sys.argv[0],*remaining])
