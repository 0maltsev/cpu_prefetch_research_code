"""Real Linux procfd exit races and fail-closed supervision; no experiments."""
import argparse,errno,hashlib,importlib.util,json,os,pathlib,subprocess,sys,tempfile,time,types,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parent
parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--operator',type=pathlib.Path,default=ROOT/'docs/evidence/stage17/D258-SUPERVISOR-ESRCH-20261116-01/run_daycap_study.py')
parser.add_argument('--qualified-tools',type=pathlib.Path,default=ROOT/'tools')
args,remaining=parser.parse_known_args();sys.argv=[sys.argv[0],*remaining]
spec=importlib.util.spec_from_file_location('d258_subject',args.operator)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ProcExitTests(unittest.TestCase):
 def sleeper(self):
  p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  def cleanup():
   if p.poll() is None:p.kill();p.wait(timeout=5)
  self.addCleanup(cleanup);return p
 def read_after_real_exit(self,p):
  original=pathlib.Path.open;target=pathlib.Path(f'/proc/{p.pid}/stat');opened=[]
  def coordinated_open(path,*a,**kw):
   stream=original(path,*a,**kw)
   if path==target and not opened:
    opened.append(True);p.terminate();p.wait(timeout=5)
   return stream
  return patch.object(pathlib.Path,'open',coordinated_open),opened
 def test_kernel_returns_esrch_after_opened_stat_task_disappears(self):
  p=self.sleeper()
  with open(f'/proc/{p.pid}/stat') as stream:
   p.terminate();p.wait(timeout=5)
   with self.assertRaises(ProcessLookupError) as raised:stream.read()
  self.assertEqual(raised.exception.errno,errno.ESRCH)
 def test_enumeration_tolerates_real_stat_exit_after_open(self):
  p=self.sleeper();hook,opened=self.read_after_real_exit(p)
  with hook:found=m.descendants(os.getpid())
  self.assertTrue(opened);self.assertNotIn(p.pid,found)
 def test_healthy_child_remains_observed_when_sibling_exits(self):
  departing=self.sleeper();healthy=self.sleeper();ticks=m.start_ticks(healthy.pid)
  hook,opened=self.read_after_real_exit(departing)
  with hook:found=m.descendants(os.getpid())
  self.assertTrue(opened);self.assertNotIn(departing.pid,found)
  self.assertEqual(found[healthy.pid],ticks);self.assertIsNone(healthy.poll())
 def test_owner_observation_tolerates_real_stat_exit_after_open(self):
  p=self.sleeper();owned=m.OwnedProcess.__new__(m.OwnedProcess)
  owned.process=p;owned.leader_ticks=m.start_ticks(p.pid);owned.observed={}
  hook,opened=self.read_after_real_exit(p)
  with hook:found=owned.observe()
  self.assertTrue(opened);self.assertNotIn(p.pid,found)
 def test_tracked_child_liveness_tolerates_real_stat_exit_after_open(self):
  p=self.sleeper();ticks=m.start_ticks(p.pid);owned=m.OwnedProcess.__new__(m.OwnedProcess)
  owned.process=types.SimpleNamespace(pid=0);owned.observe=lambda:{p.pid:ticks}
  hook,opened=self.read_after_real_exit(p)
  with hook:found=owned.live()
  self.assertTrue(opened);self.assertNotIn(p.pid,found)
 def test_disappeared_children_file_is_only_a_missing_subtree(self):
  with patch.object(pathlib.Path,'read_text',side_effect=ProcessLookupError(errno.ESRCH,'task exited')):
   self.assertEqual(m.descendants(os.getpid()),{})
 def test_proc_permission_and_io_errors_are_not_hidden(self):
  for error in (PermissionError(errno.EACCES,'denied'),OSError(errno.EIO,'I/O error')):
   with self.subTest(error=type(error).__name__),patch.object(pathlib.Path,'read_text',side_effect=error):
    with self.assertRaises(type(error)):m.descendants(os.getpid())
 def test_owner_permission_error_still_fails(self):
  owned=m.OwnedProcess.__new__(m.OwnedProcess);owned.process=types.SimpleNamespace(pid=12);owned.leader_ticks=34;owned.observed={}
  with patch.object(m,'start_ticks',side_effect=PermissionError(errno.EACCES,'denied')):
   with self.assertRaises(PermissionError):owned.observe()
 def test_nonzero_owner_exit_is_preserved(self):
  with tempfile.TemporaryFile() as log:
   owned=m.OwnedProcess([sys.executable,'-B','-c','import time,sys;time.sleep(.05);sys.exit(7)'],log,set())
   try:self.assertEqual(owned.wait(time.monotonic_ns()+5*m.NANO),7)
   finally:
    if owned.process.poll() is None:owned.process.kill();owned.process.wait(timeout=5)
 def test_native_identity_signal_guard_remains_fail_closed(self):
  p=self.sleeper()
  with self.assertRaises(RuntimeError):m.send_pidfd(p.pid,m.start_ticks(p.pid),15,native={(1,'0'*64)})
  self.assertIsNone(p.poll())
 def test_real_native_loss_is_still_rejected_by_unchanged_archive_broker(self):
  sys.path.insert(0,str(args.qualified_tools))
  import stage17_formal_archive_broker_v1 as broker
  model=broker._NativeExcludedModel.__new__(broker._NativeExcludedModel)
  def exited():raise ProcessLookupError(errno.ESRCH,'software native leader exited')
  model.native=types.SimpleNamespace(observe_quiescence=exited);model.native_failure=None
  with self.assertRaises(broker.BrokerError):model.require_native()
 def test_only_observation_and_diagnostic_functions_changed(self):
  import ast
  baseline=ast.parse((args.operator.parent/'fixtures/baseline_run_daycap_study.py').read_bytes())
  fixed=ast.parse(args.operator.read_bytes())
  def functions(tree):
   result={}
   for n in tree.body:
    if isinstance(n,ast.FunctionDef):result[n.name]=ast.dump(n,include_attributes=False)
    elif isinstance(n,ast.ClassDef):
     for f in n.body:
      if isinstance(f,ast.FunctionDef):result[n.name+'.'+f.name]=ast.dump(f,include_attributes=False)
   return result
  a,b=functions(baseline),functions(fixed)
  self.assertEqual(a.keys(),b.keys())
  changed={name for name in a if a[name]!=b[name]}
  self.assertEqual(changed,{'descendants','OwnedProcess.observe','OwnedProcess.live','Study.command'})
  def values(tree):return [ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign)]
  self.assertEqual(values(baseline),values(fixed))
 def test_expired_original_preparation_deadline_is_not_reset_by_the_fix(self):
  with patch.object(m.time,'monotonic_ns',return_value=1210558041457867):
   with self.assertRaises(RuntimeError):m.Budget(1199961844786205)
 def test_error_report_preserves_errno_and_traceback_without_hiding_failure(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);bundle=root/'local-bundle-extract/fixture/release/bin';bundle.mkdir(parents=True)
   for n in ('cpu_prefetch_runner','cpu_prefetch_q15_clock_qualification_tool'):(bundle/n).write_bytes(b'inert fixture, never executed')
   s=m.Study.__new__(m.Study);s.root=root/'study';s.root.mkdir();s.args=types.SimpleNamespace(config=root/'none',config_sha256='0'*64)
   s.release=dict(bundle_name='fixture',worker_sha256='1'*64,clock_sha256='2'*64);s.result=dict(phases=[]);s.active=None
   def fail(*_):raise PermissionError(errno.EACCES,'software-only unexpected error')
   fake=types.SimpleNamespace(process=types.SimpleNamespace(pid=123,returncode=None),wait=fail)
   with patch.object(m,'E',root),patch.object(m,'configuration'),patch.object(m,'OwnedProcess',return_value=fake):
    with self.assertRaises(PermissionError):s.command('collection',['never executed'],time.monotonic_ns()+m.NANO)
   report=json.loads((s.root/'collection-result.json').read_bytes())
   self.assertEqual(report['failure_type'],'PermissionError');self.assertEqual(report['failure_errno'],errno.EACCES)
   self.assertIn('PermissionError',report['failure_traceback']);self.assertLessEqual(len(report['failure_traceback']),32768)

if __name__=='__main__':unittest.main()
