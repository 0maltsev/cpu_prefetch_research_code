"""D254 selection leaves historical source-qualified tuples unchanged."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import verify_stand_bundle as verifier
class TupleTests(unittest.TestCase):
 def test_only_fresh_production_and_dry_run_profiles_select59(self):
  policy={'policy':{'path':'config/stage17/stage17-operational-evidence-admission-policy-v59.json'}}
  for name in ('STAGE17-PILOT-CANDIDATE-BUNDLE-v26','STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22'):
   self.assertEqual(verifier.daycap_admission_tuple(name,policy),(59,33,33,'STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v1','tools/stage17_phase_controller_daycap_v1.py'))
  self.assertIsNone(verifier.daycap_admission_tuple('STAGE17-PILOT-CANDIDATE-BUNDLE-v25',policy))
 def test_historical_and_unsupported_tuples_do_not_select_new_route(self):
  for p in ('58','60','059','59.json/extra'):
   self.assertIsNone(verifier.daycap_admission_tuple('STAGE17-PILOT-CANDIDATE-BUNDLE-v26',{'policy':{'path':f'config/stage17/stage17-operational-evidence-admission-policy-v{p}.json'}}))
 def test_malformed_metadata_cannot_select59(self):
  for c in (None,{}, {'policy':None},{'policy':'v59'}):self.assertIsNone(verifier.daycap_admission_tuple('STAGE17-PILOT-CANDIDATE-BUNDLE-v26',c))
if __name__=='__main__':unittest.main()
