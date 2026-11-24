"""Software-only source binding, authority and original bounded-cleanup checks."""
import hashlib,importlib.util,json,os,pathlib,sys,tempfile,time,types,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[3]
OP=pathlib.Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('d260_study_subject',OP/'run_d260_study.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
s=importlib.util.spec_from_file_location('d258_cleanup_subject',OP/'original_supervisor.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)

class OperatorTests(unittest.TestCase):
 def test_authenticated_bytes_reject_modification_and_symlinks(self):
  with tempfile.TemporaryDirectory() as name:
   p=pathlib.Path(name)/'metadata';p.write_bytes(b'{"captures":103}');b=m.binding(p);self.assertEqual(m.read(b),p.read_bytes())
   p.write_bytes(b'{"captures":102}')
   with self.assertRaises(RuntimeError):m.read(b)
   q=p.parent/'alias';q.symlink_to(p)
   with self.assertRaises(RuntimeError):m.read(dict(b,path=str(q)))
 def test_exclusive_receipts_never_overwrite_failure_history(self):
  with tempfile.TemporaryDirectory() as name:
   p=pathlib.Path(name)/'result.json';m.save(p,dict(success=False))
   with self.assertRaises(FileExistsError):m.save(p,dict(success=True))
   self.assertFalse(json.loads(p.read_bytes())['success'])
 def test_private_owner_rejects_an_unrelated_parent_before_prepared_inputs(self):
  with tempfile.TemporaryDirectory() as name:
   p=pathlib.Path(name);(p/'study-intent.json').write_text(json.dumps(dict(supervisor_pid=-1,supervisor_start_ticks=-1,configuration_sha256='a'*64)))
   with mock.patch.object(m,'STUDY',p),mock.patch.object(m,'prepared',side_effect=AssertionError('must not access authority')):
    with self.assertRaisesRegex(RuntimeError,'dedicated parent'):m.owner(types.SimpleNamespace(config_sha256='a'*64),{}, {},h)
 def test_source_loader_has_no_main_side_effect_or_qualification_call(self):
  self.assertFalse(m.STUDY.exists())
  import ast
  tree=ast.parse((OP/'run_d260_study.py').read_bytes());calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
  self.assertFalse(any(n.func.attr in ('run_near','run_far','run_q15') for n in calls))
 def test_original_bounded_restore_reaps_actual_cleanup_child(self):
  with tempfile.TemporaryDirectory() as name:
   root=pathlib.Path(name)
   def restore():m.save(root/'partition-restoration.json',dict(verified=True));return True
   state=types.SimpleNamespace(root=root,result={},budget=types.SimpleNamespace(end=time.monotonic_ns()+10**10),restore=restore)
   self.assertTrue(h.Study.bounded_restore(state));self.assertTrue(state.result['partition_restoration']['verified'])
 def test_failed_original_cleanup_cannot_be_success(self):
  with tempfile.TemporaryDirectory() as name:
   root=pathlib.Path(name)
   def restore():m.save(root/'partition-restoration.json',dict(verified=False));return False
   state=types.SimpleNamespace(root=root,result={},budget=types.SimpleNamespace(end=time.monotonic_ns()+10**10),restore=restore)
   self.assertFalse(h.Study.bounded_restore(state));self.assertFalse(state.result['partition_restoration']['verified'])

if __name__=='__main__':unittest.main()
