import sys,pathlib,json,unittest,importlib.util
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[3]
OLD=ROOT/'build/stage17-step3-prep/d207-stand-validation'
sys.path.insert(0,str(OLD))
import test_validate_d207_retained_study as previous
sys.path.insert(0,str(HERE))
import validate_d207_retained_study_parallel_v1 as wrapper
previous.wrapper=wrapper
class Successor(previous.Boundaries):
 def pipeline_fixture(self):
  args=super().pipeline_fixture()
  doc=dict(status='FULL_STUDY_VALIDATION_REJECTED',error='whole plot restore prestate: differs',plan_sha256=args.plan_sha256,request_sha256=args.request_sha256,authorization_sha256=args.authorization_sha256,result_sha256=args.admitted_result_sha256,supervisor_sha256=args.supervisor_sha256)
  args.previous_validation=self.root/'previous.json';args.previous_validation.write_text(json.dumps(doc))
  args.previous_validation_sha256=wrapper.sha(args.previous_validation.read_bytes())
  return args
 def test_current_production_module_wiring(self):
  cli,registry,validator,modules=wrapper.load_runtime(ROOT)
  self.assertIs(cli.registry,registry)
  self.assertEqual(validator.__name__,'stage17_discovery_validation_parallel_v1')
  self.assertEqual(validator.base.__name__,'stage17_discovery_validation_v3')
  self.assertEqual(pathlib.Path(validator.__file__).parent,HERE)
  for m in modules:
   if m not in (validator,validator.base):self.assertEqual(pathlib.Path(m.__file__).parent,ROOT/'tools')
 def test_successor_code_and_decision_hash_pinned(self):
  for key in ('SUCCESSOR_SHA256','CORRECTION_SHA256','PARALLEL_SHA256','PARALLEL_DECISION_SHA256'):
   with self.subTest(key=key),patch.object(wrapper,key,'0'*64):
    with self.assertRaisesRegex(ValueError,'SHA256 differs'):wrapper.load_runtime(ROOT)
 def test_rejected_report_hash_pinned(self):
  args=self.pipeline_fixture();args.previous_validation_sha256='0'*64
  with self.assertRaisesRegex(ValueError,'SHA256 differs'):wrapper.validate(args)
  self.assertFalse(args.output.exists())
 def test_prior_rejection_must_match_exact_study_and_error(self):
  args=self.pipeline_fixture();original=json.loads(args.previous_validation.read_bytes())
  for key,value in [('status','FULL_STUDY_VALIDATED'),('error','different failure'),('plan_sha256','0'*64),('request_sha256','0'*64),('authorization_sha256','0'*64),('result_sha256','0'*64),('supervisor_sha256','0'*64)]:
   with self.subTest(key=key):
    doc=dict(original);doc[key]=value;args.previous_validation.write_text(json.dumps(doc));args.previous_validation_sha256=wrapper.sha(args.previous_validation.read_bytes())
    with self.assertRaisesRegex(ValueError,'original rejected report'):wrapper.validate(args)
    self.assertFalse(args.output.exists())
if __name__=='__main__':unittest.main(verbosity=2)
