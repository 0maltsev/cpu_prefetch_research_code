"""Original proof body and explicit Q16c receipt/CPU lineage."""
import ast
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_restoration_v1 as current


class RestorationTests(unittest.TestCase):
    def test_original_proof_changes_only_explicit_action_constant(self):
        p=Path(__file__).resolve().parents[1]/'build/stage17-d260-release/operators-d268/original_supervisor.py'
        if not p.exists():self.skipTest('recorded original ownership core required')
        old=next(n for n in ast.parse(p.read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='restoration_status')
        new=next(n for n in ast.parse(Path(current.__file__).read_bytes()).body if isinstance(n,ast.FunctionDef) and n.name=='restoration_status')
        for n in ast.walk(new):
            if isinstance(n,ast.Constant) and n.value=='Q16c':n.value='Q16b'
        self.assertEqual(ast.dump(old),ast.dump(new))

    def test_complete_cpu_readback_and_authentication_are_required(self):
        pre=[dict(cpu=i,complete_value_hex='0000000000000001') for i in (0,1,8)]
        receipt=dict(action_id='Q16c',attempt_id='attempt',request_sha256='request',authorization_sha256='authorization',
            schema_version='cpu-prefetch-stage17-phase-action-completion/6',quarantined=False,
            leader_reaped=True,process_group_gone=True,restoration_verified=True,
            live_restoration_readback=[dict(cpu=i,expected_hex='0000000000000001',observed_hex='0000000000000001',matches=True) for i in (0,1,8)])
        args=dict(attempt_id='attempt',request_sha256='request',authorization_sha256='authorization',expected_prestate=pre)
        self.assertTrue(current.restoration_status(receipt,**args)['hardware_restoration_verified'])
        for mutate in (lambda r:r.update(action_id='Q16b'),lambda r:r['live_restoration_readback'].pop(),
                       lambda r:r['live_restoration_readback'][0].update(observed_hex='0000000000000000')):
            bad=copy.deepcopy(receipt);mutate(bad)
            with self.assertRaises(ValueError):current.restoration_status(bad,**args)


if __name__=='__main__':unittest.main()
