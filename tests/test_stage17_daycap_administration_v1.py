"""Regression against actual retained qualification, plus unchanged gate wiring."""
import copy,json,pathlib,sys,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import stage17_daycap_administration_v1 as admin
import stage17_operational_cli_daycap_v1 as original
class AssociationTests(unittest.TestCase):
 def setUp(self):
  raw=json.loads((ROOT/'docs/evidence/stage17/DAYCAP-120-ADMISSION-20261115-01/original-contexts-admission.json').read_bytes())
  self.contexts=raw;self.validation=types.SimpleNamespace(resolutions={k:types.SimpleNamespace(**v) for k,v in raw['resolutions'].items()})
 def test_actual_retained_ext006_has_no_stand_and_derivation_preserves_all_original_release_facts(self):
  old=self.validation.resolutions['S17-EXT-006'].semantic_context;self.assertNotIn('stand_id',old)
  before=copy.deepcopy(old);v=admin.associated_validation(self.validation,'CPU-PREFETCH-V5')
  self.assertEqual(v.resolutions['S17-EXT-006'].semantic_context,{**before,'stand_id':'CPU-PREFETCH-V5'})
  self.assertEqual(old,before);self.assertIs(v.resolutions['S17-EXT-004'],self.validation.resolutions['S17-EXT-004'])
 def test_wrong_platform_cannot_supply_a_release_association(self):
  with self.assertRaises(admin.handoff.Error):admin.associated_validation(self.validation,'ANOTHER-STAND')
 def test_contradictory_existing_release_association_is_rejected(self):
  self.validation.resolutions['S17-EXT-006'].semantic_context['stand_id']='CONFLICT'
  with self.assertRaises(admin.handoff.Error):admin.associated_validation(self.validation,'CPU-PREFETCH-V5')
 def test_current_trust_context_must_agree_when_present(self):
  self.validation.resolutions['S17-EXT-002']=types.SimpleNamespace(semantic_context={'stand_id':'CONFLICT'})
  with self.assertRaises(admin.handoff.Error):admin.associated_validation(self.validation,'CPU-PREFETCH-V5')
 def test_native_qualification_identities_are_never_relabelled(self):
  view=admin.associated_validation(self.validation,'CPU-PREFETCH-V5');old=self.validation.resolutions['S17-EXT-006'].semantic_context
  for k in ('source_revision','release_artifact_sha256','inventory_sha256','archive_bundle_root'):
   self.assertEqual(view.resolutions['S17-EXT-006'].semantic_context[k],old[k])
class GraphTests(unittest.TestCase):
 def test_only_fixed_handoff_changes_and_authority_bodies_remain_original(self):
  cli=admin.make_cli();controller=cli.controller
  self.assertIs(controller._validate_inputs.__globals__['handoff'].consume,admin.consume)
  self.assertIs(controller._v26.validate_action_inputs.__globals__['_validate_inputs'],controller._validate_inputs)
  self.assertIs(controller._v25._prepare_action.__globals__['journal_runtime'],controller.journal_runtime)
  for name in ('author_formal_request','author_formal_authorization','verify_formal_signature','execute_formal','prepare_formal_retention','admit_formal_retention'):
   self.assertIs(getattr(cli,name).__code__,getattr(original,name).__code__)
 def test_each_administrative_instance_has_isolated_configuration(self):
  left,right=admin.make_cli(),admin.make_cli()
  self.assertIsNot(left.controller.configure_historical_inputs.__globals__,right.controller.configure_historical_inputs.__globals__)
  self.assertIsNone(left.controller.configure_historical_inputs.__globals__['_HISTORICAL'])
 def test_activation_selects_fixed_controller_without_replacing_qualified_source_modules(self):
  before=admin.original_controller._validate_inputs;cli=admin.make_cli()
  try:
   cli.activate();self.assertIs(cli.base.controller,cli.controller);self.assertIs(cli.base.journal_runtime,cli.journal)
   self.assertIs(admin.original_controller._validate_inputs,before)
  finally:original.activate()
if __name__=='__main__':unittest.main()
