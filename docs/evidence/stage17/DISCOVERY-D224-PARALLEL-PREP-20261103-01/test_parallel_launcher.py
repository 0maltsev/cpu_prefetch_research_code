"""Finite local process-tree and admission tests; never execute retained analysis."""
import ast
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

import prepare_install as generator
import run_parallel_analysis as launcher

HERE = Path(__file__).resolve().parent


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='d224-launcher-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / launcher.ROOT_NAME
        self.root.mkdir(mode=0o700)
        (self.root/'scratch').mkdir(mode=0o700)

    def write_manifest(self):
        rows=[]
        for name in sorted(launcher.FILES):
            raw=('synthetic bound test file '+name).encode()
            path=self.root/name;path.write_bytes(raw);path.chmod(0o600)
            rows.append(dict(name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        argv=['/usr/bin/python3','-B',str(self.root/'validate_d207_retained_study_parallel_v1.py'),
            '--scratch-directory',str(self.root/'scratch'),
            '--output',str(self.root/'scratch/full-study-validation-parallel-v1.json'),
            '--output-root',str(Path(self.tmp.name)/'raw')]
        manifest=dict(schema_version='d224-analysis-installation/1',analysis_root=str(self.root),
            expected_boot_id=launcher.BOOT_ID,files=rows,argv=argv)
        path=self.root/'installed-bindings.json';path.write_text(json.dumps(manifest));path.chmod(0o600)
        return manifest,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_exact_six_pins_including_launcher_and_exclusive_ownership(self):
        manifest,digest=self.write_manifest()
        self.assertEqual(launcher.installation(self.root,digest)[0],manifest)
        for name in launcher.FILES:
            with self.subTest(name=name):
                path=self.root/name;raw=path.read_bytes();path.write_bytes(raw+b'\n')
                with self.assertRaisesRegex(ValueError,'SHA256 differs'):
                    launcher.installation(self.root,digest)
                path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'SHA256 differs'):
            launcher.installation(self.root,'0'*64)
        with patch.object(launcher.os,'getuid',return_value=1001):
            with self.assertRaisesRegex(ValueError,'UID 1000'):
                launcher.installation(self.root,digest)
        path=self.root/'run_parallel_analysis.py';path.chmod(0o666)
        with self.assertRaisesRegex(ValueError,'ownership/mode'):
            launcher.installation(self.root,digest)

    def test_symlink_duplicate_manifest_and_nonempty_scratch_rejected(self):
        manifest,digest=self.write_manifest()
        path=self.root/'run_parallel_analysis.py';outside=Path(self.tmp.name)/'outside'
        path.rename(outside);path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError,'symlink'):
            launcher.installation(self.root,digest)
        path.unlink();outside.rename(path)
        (self.root/'scratch/old-result').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'empty'):
            launcher.installation(self.root,digest)
        path=self.root/'duplicate.json';path.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError,'duplicate'):
            launcher.document(path)

    def test_exclusive_retention_never_overwrites(self):
        launcher.retain(self.root,'intent.json',dict(test=True))
        original=(self.root/'intent.json').read_bytes()
        with self.assertRaises(FileExistsError):
            launcher.retain(self.root,'intent.json',dict(test=False))
        self.assertEqual((self.root/'intent.json').read_bytes(),original)
        self.assertEqual((self.root/'intent.json').stat().st_mode&0o777,0o600)

    def test_fresh_resource_gate_exact_thresholds_and_failures(self):
        def read(path,*args,**kwargs):
            if str(path).endswith('boot_id'):return launcher.BOOT_ID+'\n'
            if str(path)=='/proc/meminfo':return f'MemAvailable: {80*1024**2} kB\n'
            raise AssertionError(path)
        with patch.object(launcher.Path,'read_text',autospec=True,side_effect=read), \
                patch.object(launcher.os,'sched_getaffinity',return_value=set(range(8))), \
                patch.object(launcher,'available_disk',return_value=32*launcher.GIB):
            report=launcher.resource_admission(self.root)
            self.assertEqual(report['required_mem_available_bytes'],80*launcher.GIB)
            self.assertFalse(report['scratch_is_hard_quota'])
            for name,value in (('cpus',7),('memory',80*launcher.GIB-1024),('disk',32*launcher.GIB-1),('boot','wrong')):
                with self.subTest(gate=name):
                    if name=='cpus':
                        with patch.object(launcher.os,'sched_getaffinity',return_value=set(range(value))),self.assertRaisesRegex(ValueError,'CPUs'):
                            launcher.resource_admission(self.root)
                    elif name=='memory':
                        with patch.object(launcher,'mem_available',return_value=value),self.assertRaisesRegex(ValueError,'80 GiB'):
                            launcher.resource_admission(self.root)
                    elif name=='disk':
                        with patch.object(launcher,'available_disk',return_value=value),self.assertRaisesRegex(ValueError,'disk'):
                            launcher.resource_admission(self.root)
                    else:
                        with patch.object(launcher.Path,'read_text',return_value='wrong'),self.assertRaises(ValueError):
                            launcher.resource_admission(self.root)
        for raw in ('MemFree: 123 kB\n','MemAvailable: 1 kB\nMemAvailable: 2 kB\n'):
            with self.assertRaises(ValueError):launcher.mem_available(raw)

    def retention_fixture(self):
        root=Path(self.tmp.name)/'raw';root.mkdir()
        artifacts=[];captures=[]
        for i in range(36):
            name=f'discovery-c{i:02d}-control.json';(root/name).write_bytes(b'{}')
            row=dict(file_name=name,size_bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())
            artifacts.append(row);captures.append(dict(ordinal=i,artifacts=[row]))
        report=dict(captures=captures)
        def rewrite():
            raw=json.dumps(report).encode();(root/'retention-report.json').write_bytes(raw)
            bound=dict(file_name='retention-report.json',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            raw=json.dumps(dict(artifacts=[*artifacts,bound])).encode();(root/'stage17-action-result-v5.json').write_bytes(raw)
            return {'--output-root':str(root),'--admitted-result-sha256':hashlib.sha256(raw).hexdigest()}
        return root,report,rewrite

    def test_retention_control_admission_bound_hash_size_full36(self):
        root,report,rewrite=self.retention_fixture();options=rewrite()
        result=launcher.retention_control_bound(options)
        self.assertEqual(result['control_files'],36)
        self.assertEqual(result['scratch_planning_estimate_bytes'],13509117792)
        self.assertFalse(result['expansion_factor_is_proved_bound'])
        self.assertFalse(result['control_content_hashes_checked_here'])
        bad=dict(options);bad['--admitted-result-sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'SHA256'):launcher.retention_control_bound(bad)
        last=report['captures'][-1]['artifacts'][0];last['size_bytes']=launcher.MAX_CONTROL_BYTES+1
        with self.assertRaisesRegex(ValueError,'ceiling'):launcher.retention_control_bound(rewrite())
        last['size_bytes']=2;options=rewrite();(root/last['file_name']).write_bytes(b'xxx')
        with self.assertRaisesRegex(ValueError,'actual control size'):launcher.retention_control_bound(options)
        report['captures'].pop()
        with self.assertRaisesRegex(ValueError,'full36'):launcher.retention_control_bound(rewrite())

    def test_original_argv_ast_only_and_three_path_changes(self):
        original=generator.original_argv(generator.OLD);actual=generator.adapted_argv()
        positions=[i for i,(a,b) in enumerate(zip(original,actual,strict=True)) if a!=b]
        self.assertEqual(positions,sorted([2,original.index('--scratch-directory')+1,original.index('--output')+1]))
        path=Path(self.tmp.name)/'untrusted.py'
        path.write_text("raise RuntimeError('MUST NOT EXECUTE')\nARGV=['literal']\n")
        self.assertEqual(generator.original_argv(path),['literal'])
        path.write_text("ARGV=[str(1)]\n")
        with self.assertRaises(ValueError):generator.original_argv(path)

    def test_installer_payload_and_manifest_self_binding_without_execution(self):
        destination=Path(self.tmp.name)/'install'
        summary=generator.prepare(destination)
        self.assertFalse(summary['executed'])
        manifest=(destination/'installed-bindings.json').read_bytes()
        self.assertEqual(hashlib.sha256(manifest).hexdigest(),summary['installation_sha256'])
        doc=json.loads(manifest);self.assertEqual({r['name'] for r in doc['files']},launcher.FILES)
        source=(destination/'install-and-start.py').read_text();tree=ast.parse(source)
        rows=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                  and any(isinstance(t,ast.Name) and t.id=='ROWS' for t in node.targets))
        self.assertEqual(len(rows),7)
        for row in rows:
            raw=base64.b64decode(row['base64'],validate=True)
            self.assertEqual(len(raw),row['size_bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
        self.assertIn('os.O_EXCL',source)
        self.assertIn("os.getuid()==os.geteuid()==1000",source)
        with self.assertRaises(FileExistsError):generator.prepare(destination)

    def execute_supervisor(self, program, *,timeout=2,scratch=16*1024**2,extra=''):
        code=f'''import json,sys
from pathlib import Path
sys.path.insert(0,{str(HERE)!r})
import run_parallel_analysis as launcher
{extra}
report=launcher.supervise([sys.executable,'-B','-c',{textwrap.dedent(program)!r}],Path({str(self.root)!r}),
 timeout_seconds={timeout},poll_seconds=0.02,scratch_limit={scratch},disk_reserve=0,grace_seconds=0.1)
print(json.dumps(report),flush=True)
'''
        result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertTrue(report['all_own_children_reaped'],report)
        for row in report['reaped_children']:
            with self.assertRaises(ProcessLookupError):os.kill(row['pid'],0)
        return report

    def test_actual_normal_exit_and_exclusive_logs(self):
        report=self.execute_supervisor("print('synthetic analysis only')")
        self.assertEqual(report['status'],'ANALYSIS_EXITED')
        self.assertEqual(report['exit_code'],0)
        self.assertEqual((self.root/'analysis-stdout.log').read_text(),'synthetic analysis only\n')
        report=self.execute_supervisor("raise AssertionError('must not run')")
        self.assertEqual(report['status'],'ANALYSIS_ABORTED')
        self.assertIn('FileExistsError',report['error'])

    def test_actual_nonzero_child_is_retained(self):
        report=self.execute_supervisor('import sys;sys.exit(7)')
        self.assertEqual(report['status'],'ANALYSIS_EXITED')
        self.assertEqual(report['exit_code'],7)

    def test_last_worker_join_between_snapshot_and_waitid_does_not_false_abort(self):
        program='''
            import os,time
            from pathlib import Path
            if os.fork()==0:
                Path('last-worker.pid').write_text(str(os.getpid()))
                while not Path('release-worker').exists():time.sleep(0.001)
                os._exit(0)
            os.waitpid(-1,0)
        '''
        extra=f'''
import time,os
root=Path({str(self.root)!r})
original_discover=launcher.OwnTree.discover
first=True
def delayed_discover(self):
    global first
    if not first:return original_discover(self)
    first=False
    deadline=time.monotonic()+3
    while not (root/'last-worker.pid').exists():
        if time.monotonic()>deadline:raise RuntimeError('fixture worker missing')
        time.sleep(0.001)
    snapshot=original_discover(self)
    worker=int((root/'last-worker.pid').read_text())
    if worker not in snapshot:raise AssertionError('real worker not sampled')
    (root/'release-worker').touch()
    while Path('/proc/'+str(worker)).exists():
        if time.monotonic()>deadline:raise RuntimeError('fixture worker not joined')
        time.sleep(0.001)
    leader=next(pid for pid in snapshot if pid!=worker)
    while Path('/proc/'+str(leader)+'/stat').read_text().rsplit(')',1)[1].split()[0]!='Z':
        if time.monotonic()>deadline:raise RuntimeError('fixture leader not exited')
        time.sleep(0.001)
    return snapshot
launcher.OwnTree.discover=delayed_discover
'''
        report=self.execute_supervisor(program,extra=extra)
        self.assertEqual(report['status'],'ANALYSIS_EXITED',report)
        self.assertEqual(report['exit_code'],0)

    def test_timeout_kills_escaped_descendant_and_preserves_unrelated_process(self):
        unrelated=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'],start_new_session=True)
        try:
            program='''
                import os,signal,time
                from pathlib import Path
                signal.signal(signal.SIGTERM,signal.SIG_IGN)
                child=os.fork()
                if child==0:
                    os.setsid()
                    Path('escaped.pid').write_text(str(os.getpid()))
                time.sleep(60)
            '''
            report=self.execute_supervisor(program,timeout=0.4)
            self.assertEqual(report['status'],'ANALYSIS_ABORTED')
            self.assertIn('deadline',report['error'])
            escaped=int((self.root/'escaped.pid').read_text())
            self.assertIn(escaped,[r['pid'] for r in report['reaped_children']])
            self.assertIsNone(unrelated.poll())
        finally:
            unrelated.terminate();unrelated.wait(timeout=5)

    def test_leader_exit_with_orphan_descendant_is_failure_and_reaped(self):
        program='''
            import os,time,signal
            from pathlib import Path
            if os.fork()==0:
                os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN)
                Path('orphan.pid').write_text(str(os.getpid()));time.sleep(60)
            else:
                while not Path('orphan.pid').exists():time.sleep(0.001)
                os._exit(0)
        '''
        report=self.execute_supervisor(program)
        self.assertEqual(report['status'],'ANALYSIS_ABORTED')
        self.assertIn('descendants',report['error'])
        self.assertIn(int((self.root/'orphan.pid').read_text()),[r['pid'] for r in report['reaped_children']])

    def test_unlinked_spool_counts_toward_monitored_budget(self):
        report=self.execute_supervisor('''
            import tempfile,time
            stream=tempfile.TemporaryFile(dir='scratch')
            stream.truncate(2*1024**2)
            time.sleep(60)
        ''',scratch=1024**2)
        self.assertEqual(report['status'],'ANALYSIS_ABORTED')
        self.assertIn('scratch allowance',report['error'])
        self.assertGreaterEqual(report['maximum_sampled_scratch_bytes'],2*1024**2)
        self.assertEqual(list((self.root/'scratch').iterdir()),[])

    def test_hard_as_and_file_limits_apply_only_inside_supervisor_subprocess(self):
        parent=resource.getrlimit(resource.RLIMIT_AS)
        code=f"import sys,json,resource;sys.path.insert(0,{str(HERE)!r});import run_parallel_analysis as m;m.hard_limits();print(json.dumps([resource.getrlimit(resource.RLIMIT_AS),resource.getrlimit(resource.RLIMIT_FSIZE)]))"
        result=subprocess.run([sys.executable,'-B','-c',code],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),[[8*launcher.GIB]*2,[16*launcher.GIB]*2])
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),parent)


if __name__=='__main__':
    unittest.main(verbosity=2)
