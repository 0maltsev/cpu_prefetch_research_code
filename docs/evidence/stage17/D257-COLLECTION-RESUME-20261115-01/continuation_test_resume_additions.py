"""D257 software-only retained evidence, time limits and source parity."""
import ast,copy,importlib.util,json,pathlib,types,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('d257_subject',HERE/'continuation-operators/run_daycap_study.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ResumeTests(unittest.TestCase):
 def test_global_deadline_and_restoration_analysis_reserves_are_not_reset(self):
  start=10**15;now=start+9000*m.NANO
  with patch.object(m.time,'monotonic_ns',return_value=now):
   b=m.Budget(start)
   self.assertEqual(b.end,start+86400*m.NANO)
   self.assertEqual(b.work,start+84600*m.NANO)
   self.assertEqual(b.qualify_prep,start+11700*m.NANO)
   self.assertEqual(b.phase(m.COLLECTION_SECONDS),now+57600*m.NANO)
  with patch.object(m.time,'monotonic_ns',return_value=start+11700*m.NANO):
   with self.assertRaises(RuntimeError):m.Budget(start)
 def test_collection_always_leaves_analysis_and_both_cleanup_reserves(self):
  start=10**15
  with patch.object(m.time,'monotonic_ns',return_value=start):b=m.Budget(start)
  with patch.object(m.time,'monotonic_ns',return_value=start+11699*m.NANO):
   d=b.phase(m.COLLECTION_SECONDS)
   self.assertGreaterEqual(b.end-d,(13500+3600)*m.NANO)
 def test_no_qualification_or_program_initialization_path_in_resume_chain(self):
  tree=ast.parse((HERE/'continuation-operators/run_daycap_study.py').read_bytes())
  study=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Study')
  run=next(n for n in study.body if isinstance(n,ast.FunctionDef) and n.name=='run')
  literals={n.value for n in ast.walk(run) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
  self.assertNotIn('--qualify',literals);self.assertNotIn('--prerequisites',literals)
  source=ast.unparse(run)
  self.assertLess(source.index("self.command('preparation'"),source.index('self.clock.ISO.prepare'))
  self.assertNotIn('initialize_program',source)
 def test_unchanged_signature_owner_process_receipt_and_analysis_functions(self):
  old=ast.parse((HERE.parent/'stage17-daycap-120/run_daycap_study.py').read_bytes())
  new=ast.parse((HERE/'continuation-operators/run_daycap_study.py').read_bytes())
  def items(tree):
   out={}
   for n in tree.body:
    if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
    elif isinstance(n,ast.ClassDef):
     for f in n.body:
      if isinstance(f,ast.FunctionDef):out[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
   return out
  a,b=items(old),items(new)
  for name in ('restoration_status','prepared','prepared_after','owner_entry','cli_command','private_command',
   'OwnedProcess.__init__','OwnedProcess.observe','OwnedProcess.live','OwnedProcess.stop','OwnedProcess.wait',
   'Study.bounded_restore','Study.collection_receipt','Study.analysis_result'):
   self.assertEqual(a[name],b[name],name)
 def test_original_plan_and_all_measurement_phase_limits_are_unchanged(self):
  plan=json.loads((HERE.parent/'stage17-daycap-120/final-plan-aa3285f/plan.json').read_bytes())
  self.assertEqual(m.plan_sha256(plan),'53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486')
  self.assertEqual(plan['budget']['watchdog_ns'],65040*10**9)
  self.assertEqual(len(plan['captures']),120);self.assertEqual(plan['repetitions_per_cell'],2)
 def test_retained_binding_population_and_derived_fresh_isolation_config(self):
  original=json.loads((HERE/'stand-resume-inputs.json').read_bytes())
  self.assertEqual(set(original['bindings']),set(m.RETAINED_BINDINGS))
  for k,(p,h) in m.RETAINED_BINDINGS.items():self.assertEqual((original['bindings'][k]['path'],original['bindings'][k]['sha256']),(p,h))
  c=original['isolation_configuration']
  self.assertEqual(c['lifecycle_seconds'],72000)
  self.assertGreater(c['lifecycle_seconds']*m.NANO,c['protected_work_ns']+c['stop_seconds']*m.NANO)
  self.assertGreaterEqual(c['protected_work_ns'],(m.NATIVE_SECONDS+m.OWNER_CLEANUP_SECONDS)*m.NANO)
if __name__=='__main__':unittest.main()
