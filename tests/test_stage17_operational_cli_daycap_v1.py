"""D254 CLI wiring: unchanged authorities and the actual fresh journal graph."""
import ast,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import stage17_operational_cli_daycap_v1 as current
import stage17_operational_cli_v18 as original
import stage17_q15_session_controller_daycap_v1 as q15

class WiringTests(unittest.TestCase):
 def test_activation_selects_actual_fresh_admission_and_authoring(self):
  current.activate()
  self.assertIs(current.base.journal_runtime,current.journal)
  self.assertIs(current.base.controller,current.controller)
  self.assertIs(current.base.author_ext001,current.author_ext001_daycap_v1)
  self.assertEqual(current.journal.SEMANTIC_POLICY_PATH.name,'stage17-operational-evidence-admission-policy-v59.json')
 def test_formal_command_bodies_keep_original_signature_retention_and_expiry_gates(self):
  old=ast.parse(pathlib.Path(original.__file__).read_text());new=ast.parse(pathlib.Path(current.__file__).read_text())
  names={'_validation','author_formal_request','author_formal_authorization','verify_formal_signature','execute_formal','prepare_formal_retention','admit_formal_retention'}
  for name in names:
   left=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
   right=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
   self.assertEqual(ast.dump(left),ast.dump(right),name)
 def test_retention_helpers_remain_actual_v10(self):
  self.assertEqual(current.executor.__name__,'stage17_fixed_action_executor_v10')
  self.assertTrue(callable(current.executor._componentwise_output_root))
  self.assertTrue(callable(current.executor.predecessor._exists_at))
 def test_daycap_registry_rejects_insufficient_formal_family(self):
  with self.assertRaises(current.controller.daycap.ContractError):current.controller.contract.validate_plan('Q16b',{'schema_version':'cpu-prefetch-stage17-formal-service-plan/3'})
 def test_q15_session_selects_same_actual_fresh_controller(self):
  q15.activate()
  self.assertIs(q15.execution_body.phase_controller,current.controller)
  self.assertIs(q15.initial_body.phase_controller,current.controller)
 def tearDown(self):original.activate()

if __name__=='__main__':unittest.main()
