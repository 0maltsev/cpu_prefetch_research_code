import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('reapplication',Path(__file__).with_name('reapply_isolation_v2.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class HardwareGuards(unittest.TestCase):
    def setUp(self):
        self.plan={'captures':[dict(capture={'geometry':dict(producer_cpu=0,producer_node=0,consumer_cpu=8,consumer_node=1)},
                                   resources={'controller_stack':dict(owner_cpu=2,requested_node=0)})]}
        self.topology={'0':'0,16','2':'2,18','8':'8,24'}
        self.expected=[dict(cpu=0,complete_value_hex='0000000000000000'),dict(cpu=8,complete_value_hex='0000000000000000')]
        self.enterContext(patch.object(module.os,'open',return_value=77))
        self.enterContext(patch.object(module.os,'close'))
        self.pread=self.enterContext(patch.object(module.os,'pread',return_value=b'\0'*8))
        self.read=self.enterContext(patch.object(Path,'read_text',autospec=True,
            side_effect=lambda path:self.topology[path.parts[-3][3:]]))
        self.glob=self.enterContext(patch.object(Path,'glob',autospec=True,
            side_effect=lambda path,pattern:[Path('node1' if path.name=='cpu8' else 'node0')]))

    def test_matching_actual_readback(self):
        value=module.hardware(self.plan,self.expected,self.topology)
        self.assertEqual(value['topology']['8']['numa_node'],1)
        self.assertTrue(all(row['matches'] for row in value['msr_readback']))

    def test_msr_mismatch_or_short_read(self):
        for raw in (b'\1'+b'\0'*7,b'\0'*7):
            self.pread.return_value=raw
            with self.assertRaises(AssertionError):module.hardware(self.plan,self.expected,self.topology)

    def test_numa_mismatch(self):
        self.glob.side_effect=lambda path,pattern:[Path('node0')]
        with self.assertRaises(AssertionError):module.hardware(self.plan,self.expected,self.topology)

    def test_smt_mismatch(self):
        self.read.side_effect=lambda path:'0'
        with self.assertRaises(AssertionError):module.hardware(self.plan,self.expected,self.topology)

    def test_missing_or_rejected_approval_stops_before_core_load(self):
        with patch.object(module.os,'geteuid',return_value=0),patch.object(module,'sha',return_value=module.CORE_SHA), \
             patch.object(module.importlib.util,'spec_from_file_location') as loader:
            with patch.object(Path,'read_bytes',side_effect=FileNotFoundError):
                with self.assertRaises(FileNotFoundError):module.main()
            with patch.object(Path,'read_bytes',return_value=json.dumps({'decision_id':'D243','approved':False}).encode()):
                with self.assertRaises(AssertionError):module.main()
            loader.assert_not_called()


if __name__=='__main__':unittest.main()
