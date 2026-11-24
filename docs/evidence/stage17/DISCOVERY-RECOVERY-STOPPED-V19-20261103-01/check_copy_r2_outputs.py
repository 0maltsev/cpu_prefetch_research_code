"""Synthetic custody tests. Mock scp; no network or study-byte reads."""
import contextlib
import datetime as dt
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name('copy_r2_outputs.py')
spec = importlib.util.spec_from_file_location('copy_r2_under_test', SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class CopyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='r2-byte-custody-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.dest = self.root / 'copies' / 'discovery-output-r2-1'
        self.content = {f'file-{i}.bin': bytes([i]) * (19+i) for i in range(7)}
        self.files = [dict(path=k, size_bytes=len(v), sha256=hashlib.sha256(v).hexdigest()) for k,v in self.content.items()]
        now = dt.datetime.now(dt.timezone.utc)
        self.result = dict(utc=(now-dt.timedelta(seconds=3)).isoformat(), exit_code=1,
            partition_procs='', success=False, completion_present=False,
            partition_restoration=dict(verified=True, partition_absent=True, utc=(now-dt.timedelta(seconds=2)).isoformat()))
        self.inventory = dict(root=m.SOURCE, observed_at_utc=(now-dt.timedelta(seconds=1)).isoformat(), files=self.files + [
            dict(path='operator/supervisor.json',size_bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())])
        self.audit = dict(root=m.SOURCE, observed_at_utc=now.isoformat(), post_quiescence=True,
            complete=True, regular_files_only=True, no_symlinks=True, errors=[])
        self.args = types.SimpleNamespace(inventory=self.root/'inventory.json', supervisor_result=self.root/'result.json',
            inventory_audit=self.root/'audit.json', receipt=self.root/'receipt.json', jobs=4, file_timeout_seconds=10)
        self.calls=[]; self.active=0; self.peak=0; self.lock=threading.Lock(); self.bad=None; self.fail=None
        self.refresh()

    def refresh(self):
        for p,x in [(self.args.inventory,self.inventory),(self.args.supervisor_result,self.result)]:
            p.write_text(json.dumps(x))
        self.audit.update(inventory_sha256=hashlib.sha256(self.args.inventory.read_bytes()).hexdigest(),
                          supervisor_result_sha256=hashlib.sha256(self.args.supervisor_result.read_bytes()).hexdigest())
        self.args.inventory_audit.write_text(json.dumps(self.audit))

    def spawn(self, argv, **kwargs):
        self.assertEqual(argv[0], '/usr/bin/scp'); self.assertNotIn('-C', argv)
        self.assertEqual(argv[1:3], ['-F', '/dev/null'])
        self.assertIn('Compression=no', argv); self.assertIn('ConnectionAttempts=1', argv)
        self.assertIn('ServerAliveInterval=15', argv); self.assertIn('ServerAliveCountMax=2', argv)
        self.assertTrue(argv[-2].startswith('root@94.126.205.83:'+m.SOURCE+'/'))
        name=argv[-2].rsplit('/',1)[1]
        with self.lock:
            self.calls.append(name); self.active+=1; self.peak=max(self.active,self.peak)
        Path(argv[-1]).write_bytes(b'bad' if self.bad==name else self.content[name])
        owner=self
        class Child:
            def wait(self, timeout=None):
                time.sleep(0.015)
                with owner.lock: owner.active-=1
                return 1 if owner.fail==name else 0
            def kill(self): raise AssertionError('unexpected kill')
        return Child()

    def execute(self, free=10**15):
        with patch.object(m, 'DEST', self.dest), patch.object(m.subprocess, 'Popen', self.spawn), \
             patch.object(m.os, 'statvfs', return_value=types.SimpleNamespace(f_bavail=free, f_frsize=1)), \
             contextlib.redirect_stdout(io.StringIO()):
            return m.run(self.args)

    def test_success_copies_exact_set_bounded_and_compatible_receipt(self):
        self.assertEqual(self.execute(),0); self.assertEqual(set(self.calls),set(self.content))
        self.assertLessEqual(self.peak,4); self.assertGreater(self.peak,1)
        self.assertEqual(set(self.calls[:4]), {'file-6.bin', 'file-5.bin', 'file-4.bin', 'file-3.bin'})
        receipt=json.loads(self.args.receipt.read_bytes())
        self.assertEqual(receipt['files'],self.files); self.assertEqual(receipt['status'],'PASS_ORIGINAL_BYTE_SECOND_COPY')
        self.assertFalse(receipt['compression']); self.assertFalse(receipt['execution_authority'])
        self.assertTrue(receipt['scientific_validity_not_implied'])
        self.assertEqual(receipt['total_bytes'],sum(map(len,self.content.values())))
        for name,data in self.content.items(): self.assertEqual((self.dest/name).read_bytes(),data)
        original=self.args.receipt.read_bytes(); self.calls.clear()
        self.assertEqual(self.execute(),0); self.assertEqual(self.calls,[])
        self.assertEqual(self.args.receipt.read_bytes(),original)

    def test_existing_valid_file_skipped(self):
        self.dest.mkdir(parents=True); name=next(iter(self.content)); (self.dest/name).write_bytes(self.content[name])
        self.assertEqual(self.execute(),0); self.assertNotIn(name,self.calls)

    def test_existing_invalid_file_preserved(self):
        self.dest.mkdir(parents=True); name=next(iter(self.content)); (self.dest/name).write_bytes(b'wrong')
        with self.assertRaises(RuntimeError): self.execute()
        self.assertEqual((self.dest/name).read_bytes(),b'wrong'); self.assertFalse(self.calls)

    def test_hash_mismatch_retains_partial_stops_next_batch(self):
        self.bad='file-6.bin'
        self.assertEqual(self.execute(),1); self.assertLessEqual(len(self.calls),4)
        self.assertFalse(self.args.receipt.exists()); self.assertFalse((self.dest/self.bad).exists())
        partials=list(self.dest.parent.glob('*.custody/invocation-*/*.partial'))
        self.assertTrue(partials); self.assertIn(b'bad',[p.read_bytes() for p in partials])

    def test_scp_failure_no_retry_and_rerun_can_complete(self):
        self.fail='file-6.bin'; self.assertEqual(self.execute(),1)
        self.assertLessEqual(len(self.calls),4); self.assertEqual(len(self.calls),len(set(self.calls)))
        prior={p.name:p.read_bytes() for p in self.dest.iterdir()}; self.fail=None; self.calls.clear()
        self.assertEqual(self.execute(),0)
        self.assertFalse(set(prior)&set(self.calls))

    def test_space_gate_before_any_copy(self):
        needed=sum(map(len,self.content.values()))+m.SPOOL_RESERVE
        with self.assertRaises(RuntimeError): self.execute(free=needed-1)
        self.assertFalse(self.calls)
        self.assertFalse(self.args.receipt.exists())

    def test_unsafe_and_duplicate_names_rejected(self):
        for name in ('../escape','/absolute','x/../bad','-flag','name;cmd','operator/../bad'):
            with self.subTest(name=name):
                self.inventory['files']=[dict(self.files[0],path=name)]; self.refresh()
                with self.assertRaises(RuntimeError): self.execute()
        self.inventory['files']=[self.files[0],self.files[0]]; self.refresh()
        with self.assertRaises(RuntimeError): self.execute()
        self.assertFalse(self.calls)

    def test_source_audit_binding_and_symlink_gate(self):
        self.audit['no_symlinks']=False; self.refresh()
        with self.assertRaises(RuntimeError): self.execute()
        self.audit['no_symlinks']=True; self.refresh()
        self.args.inventory.write_text(self.args.inventory.read_text()+' ')
        with self.assertRaises(RuntimeError): self.execute()
        self.assertFalse(self.calls)

    def test_unrestored_and_prequiescence_inventory_rejected(self):
        self.result['partition_restoration']['verified']=False; self.refresh()
        with self.assertRaises(RuntimeError): self.execute()
        self.result['partition_restoration']['verified']=True
        self.inventory['observed_at_utc']='2000-01-01T00:00:00Z'; self.refresh()
        with self.assertRaises(RuntimeError): self.execute()
        self.assertFalse(self.calls)

    def test_destination_symlink_rejected(self):
        self.dest.mkdir(parents=True); target=self.root/'target'; target.write_bytes(self.content['file-0.bin'])
        (self.dest/'file-0.bin').symlink_to(target)
        with self.assertRaises(RuntimeError): self.execute()
        self.assertFalse(self.calls)

    def test_atomic_rename_never_clobbers(self):
        src=self.root/'src'; dst=self.root/'dst'; src.write_bytes(b'new'); dst.write_bytes(b'old')
        with self.assertRaises(FileExistsError): m.rename_noreplace(src,dst)
        self.assertEqual(src.read_bytes(),b'new'); self.assertEqual(dst.read_bytes(),b'old')

    def test_timeout_kills_only_copy_group_and_retains_partial(self):
        item=self.files[0]; dest=self.root/'timeout-dest'; dest.mkdir()
        work=self.root/'timeout-work'; work.mkdir(); calls=[]
        class TimedProcess:
            pid=12345
            def wait(self, timeout=None):
                calls.append(timeout)
                if timeout is not None: raise m.subprocess.TimeoutExpired('mock-scp', timeout)
                return -9
        with patch.object(m.subprocess,'Popen',return_value=TimedProcess()), patch.object(m.os,'killpg') as kill:
            result=m.copy_one(item,dest,work,10,threading.Event(),threading.Lock())
        self.assertEqual(result['status'],'FAILED'); self.assertEqual(calls,[10,None])
        kill.assert_called_once_with(12345,m.signal.SIGKILL)
        self.assertTrue((work/(item['path']+'.partial')).is_file())
        self.assertFalse((dest/item['path']).exists())

    def test_unexpected_destination_rejected(self):
        self.dest.mkdir(parents=True); (self.dest/'extra.bin').write_bytes(b'extra')
        with self.assertRaises(RuntimeError): self.execute()
        self.assertFalse(self.calls)

if __name__=='__main__':
    print('COPY_HELPER_SHA256',hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),flush=True)
    unittest.main(verbosity=2)
