"""Software-only generated parent workflow: no hardware or native processes."""
from pathlib import Path
import contextlib,importlib.util,json,sys,tempfile,time,types,unittest
from unittest.mock import patch
P=Path(__file__).resolve().parent/'qualification-packet-919c486-5-software-only'
sys.path.insert(0,str(P));spec=importlib.util.spec_from_file_location('software_d277_qualification',P/'run_qualification_v28.py');q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)

class Tests(unittest.TestCase):
 def exercise(self,fail):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);order=[]
   docs={'stage17-q15-r-result-v4.json':dict(terminal_state='Q15_R_READ_ONLY_COMPLETE',quarantined=False),
    'stage17-q15-session-waiting-v1.json':{},'stage17-q15-w-result-v4.json':dict(terminal_state='Q15_W_RESTORED_COMPLETE',restoration_verified=not fail,quarantined=fail),'stage17-q15_w-completion-v4.json':{}}
   for name,doc in docs.items():(root/name).write_text(json.dumps(doc))
   @contextlib.contextmanager
   def guard(**kwargs):
    order.append('guard')
    try:yield
    except BaseException:order.append('restore-after-failure');raise
    else:order.append('guard-success')
   def handoff(**kwargs):
    self.assertTrue((root/'q15-owned-session-success-3.json').exists());order.append('retained-isolation')
   iso=types.SimpleNamespace(qualification_guard=guard,retain_q15w_handoff=handoff)
   process=types.SimpleNamespace(pid=123,returncode=0,poll=lambda:0,wait=lambda **kwargs:0)
   packet=q.Packet.__new__(q.Packet);packet.deadline=time.monotonic()+30;packet.cleanup_seconds=2;packet.session=None
   packet.argv=lambda name:['software-only'];packet.step=lambda name:order.append(name)
   with patch.object(q,'E',root),patch.object(q,'P',P),patch.object(q,'prepare_corrected_isolation',side_effect=lambda *args:order.append('prepare-retained')), \
        patch.object(q.subprocess,'Popen',return_value=process):
    if fail:
     with self.assertRaisesRegex(RuntimeError,'Q15-W actual restoration failed'):packet.qualify(iso)
    else:packet.qualify(iso)
   return order
 def test_success_retains_native_recovery_before_administrative_renewal(self):
  self.assertEqual(self.exercise(False),['guard','prepare-retained','v28-prepare-q15r.py','v28-author-admit-ext004.py','v28-prepare-continue-q15w.py','retained-isolation','v28-admit-ext005.py','guard-success'])
 def test_q15_failure_stops_before_handoff_and_administrative_renewal(self):
  self.assertEqual(self.exercise(True),['guard','prepare-retained','v28-prepare-q15r.py','v28-author-admit-ext004.py','v28-prepare-continue-q15w.py','restore-after-failure'])
if __name__=='__main__':unittest.main()
