"""Fresh qualification identity, immutable predecessor and fail-closed routing."""
import ast
import hashlib
import json
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_phase_controller_daycap_v2 as current
import stage17_state_journal_v56 as journal
from stage17_discovery_contract_v2 import ContractError
import create_stand_bundle as creator
import verify_stand_bundle as verifier
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class QualificationTests(unittest.TestCase):
    def test_cli_bodies_preserve_all_prior_rules_except_new_identity_imports_and_policy(self):
        old=(ROOT/'tools/stage17_operational_cli_daycap_v1.py').read_text()
        new=(ROOT/'tools/stage17_operational_cli_daycap_v2.py').read_text()
        for before,after in [('stage17_phase_controller_daycap_v2','stage17_phase_controller_daycap_v1'),
            ('stage17_read_only_preflight_executor_v34','stage17_read_only_preflight_executor_v33'),
            ('stage17_state_journal_v56','stage17_state_journal_v54'),('policy-v34.json','policy-v33.json')]:
            new=new.replace(before,after)
        left,right=ast.parse(old),ast.parse(new)
        left.body=left.body[1:];right.body=right.body[1:]
        self.assertEqual(ast.dump(left),ast.dump(right))

    def test_complete_private_action_graph_uses_fresh_journal(self):
        view=current.make_controller()
        self.assertIs(view.journal_runtime,journal)
        self.assertIs(view._v25.journal_runtime,journal)
        self.assertIs(view._v26.previous,view._v25)
        self.assertIs(view.prepare_action.__globals__['_v26'],view._v26)
        self.assertNotIn('stage17_state_journal_v55',view.prepare_action.__globals__)

    def test_qualification_entry_cannot_execute_a_declared_continuation(self):
        plan=continuation_fixture(parent_fixture())
        with self.assertRaises(ContractError):
            current.contract.validate_plan('Q16b',plan)
        self.assertEqual(len(plan['captures']),103)

    def test_explicit_new_bundle_tuple_and_current_packaging_bindings(self):
        policy=dict(policy=dict(path='config/stage17/stage17-operational-evidence-admission-policy-v60.json'))
        expected=(60,34,34,'STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v2',
                  'tools/stage17_phase_controller_daycap_v2.py')
        for profile in ('STAGE17-PILOT-CANDIDATE-BUNDLE-v26','STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22'):
            self.assertEqual(verifier.daycap_admission_tuple(profile,policy),expected)
        self.assertIsNone(verifier.daycap_admission_tuple('STAGE17-PILOT-CANDIDATE-BUNDLE-v25',policy))
        self.assertEqual(creator.STAGE17_POLICY_PATH,policy['policy']['path'])
        self.assertEqual(creator.STAGE17_CONTROLLER_ENTRYPOINT,expected[-1])

    def test_predecessor_policy_bytes_keep_original_cold_source_identity(self):
        old_path=ROOT/'config/stage17/stage17-operational-evidence-admission-policy-v59.json'
        new_path=ROOT/'config/stage17/stage17-operational-evidence-admission-policy-v60.json'
        old,new=json.loads(old_path.read_bytes()),json.loads(new_path.read_bytes())
        self.assertEqual(new['predecessor']['sha256'],hashlib.sha256(old_path.read_bytes()).hexdigest())
        before=old['bindings']['src__runner__stage17_formal_family_cpp']
        after=new['bindings']['src__runner__stage17_formal_family_cpp']
        self.assertEqual(before['sha256'],'6d18ae41bd0a51d173ea98a53b9e88f13a245efd296f8d4e0a6a4558915d2951')
        self.assertNotEqual(before['sha256'],after['sha256'])
        self.assertEqual(after['sha256'],hashlib.sha256((ROOT/after['path']).read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
