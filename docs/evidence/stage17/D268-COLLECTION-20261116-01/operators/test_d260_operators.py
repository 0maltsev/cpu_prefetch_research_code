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

class CollectionBudgetTests(unittest.TestCase):
 def budget(self,lease=57600):
  utc=m.datetime.datetime(2026,11,16,12,0,tzinfo=m.datetime.timezone.utc);now=10**15
  window=dict(last_safe_collection_start_ns=now+1000*m.NANO,deadline_monotonic_ns=now+(56460+13500+1800)*m.NANO)
  auth=dict(expires_at_utc=(utc+m.datetime.timedelta(seconds=lease)).isoformat())
  return window,auth,now,utc
 def test_full_native_and_controller_time_with_single_shared_restore_reserve(self):
  w,a,n,u=self.budget();end=m.collection_deadline(w,a,n,u)
  self.assertEqual(end-n,56460*m.NANO)
  self.assertEqual(w['deadline_monotonic_ns']-end,(13500+1800)*m.NANO)
 def test_original_short_lease_fails_before_collection(self):
  with self.assertRaisesRegex(RuntimeError,'signed lease'):m.collection_deadline(*self.budget(55860))
 def test_one_nanosecond_budget_shortfall_is_rejected(self):
  w,a,n,u=self.budget();w['deadline_monotonic_ns']-=1
  with self.assertRaisesRegex(RuntimeError,'envelope'):m.collection_deadline(w,a,n,u)
 def test_unchanged_original_start_cutoff_remains_mandatory(self):
  w,a,n,u=self.budget();w['last_safe_collection_start_ns']=n
  with self.assertRaisesRegex(RuntimeError,'original latest'):m.collection_deadline(w,a,n,u)

if __name__=='__main__':unittest.main()
