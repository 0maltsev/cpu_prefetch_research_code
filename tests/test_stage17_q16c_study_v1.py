"""Supervisor integration with simulated native/hardware boundaries only."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_study_v1 as current
import stage17_q16c_window_v1 as window
import stage17_q16c_restoration_v1 as restoration


class StudyTests(unittest.TestCase):
    def exercise(self,failed_role=None):
        p=Path(__file__).resolve().parents[1]/'build/stage17-d260-release/operators-d268/original_supervisor.py'
        if not p.exists():self.skipTest('recorded original ownership core required')
        spec=importlib.util.spec_from_file_location('software_q16c_original_ownership',p);original=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=original;spec.loader.exec_module(original);self.addCleanup(sys.modules.pop,spec.name,None)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'clock').mkdir();(root/'cgroup').mkdir();out=root/'authoring';out.mkdir()
            (root/'cgroup/cgroup.procs').write_text('')
            def put(path,value):
                path.write_text(json.dumps(value));return current.binding(path)
            now=time.monotonic_ns();record=dict(started_monotonic_ns=now-4*3600*10**9,
                global_deadline_ns=now+20*3600*10**9,completed_monotonic_ns=now-10**9,
                source_deadline_ns=now+10**9,all_workers_reaped=True)
            source=put(root/'source.json',record);qualification=put(root/'qualified.json',dict(success=True))
            clock_source='''from pathlib import Path
import json
Q=Path({q!r});CG=Path({cg!r})
BEFORE={{'root':{{'actual':'synthetic-original'}},'maintenance_before':{{}}}}
class ISO:
 @staticmethod
 def verify_remaining_lifetime(*args):pass
def preparation():return {{'prestate':BEFORE}}
def restore(pre):
 assert pre==BEFORE
 (CG/'cgroup.procs').unlink();CG.rmdir();(Q/'restoration.json').write_text(json.dumps({{'verified':True}}))
def root_state():return BEFORE['root']
'''.format(q=str(root/'clock'),cg=str(root/'cgroup'))
            (root/'clock.py').write_text(clock_source)
            c=dict(evidence_root=str(root),output_root=str(out),worker=dict(size_bytes=123,sha256='synthetic'),
                files=dict(source_manifest=source,qualification_complete=qualification,clock_adapter=current.binding(root/'clock.py')))
            args=types.SimpleNamespace(configuration=root/'configuration.json',configuration_sha256='synthetic-config')
            pre=[dict(cpu=i,complete_value_hex='0000000000000001') for i in (0,1,8)]
            request=dict(attempt_id='synthetic-attempt',evidence_root_binding=dict(absolute_path=str(root/'family')),
                action_inputs=dict(hardware_control=dict(prestate=pre)))
            (root/'family').mkdir();calls=[]
            class NativeBoundary:
                def __init__(self,argv,log,native,protect_native):
                    self.role=argv[argv.index('--role')+1];self.process=types.SimpleNamespace(pid=100,returncode=None)
                    self.forced=[];calls.append(self.role)
                def wait(self,deadline):
                    role=self.role;code=1 if role==failed_role else 0
                    if role=='sign':
                        rb=put(out/'request.json',request);ab=put(out/'authorization.json',dict(expires_at_utc=
                            (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=window.FAMILY)).isoformat()))
                        put(out/'prepared.json',dict(request=rb,authorization=ab))
                    if role=='collect':
                        d=json.loads((out/'prepared.json').read_text());failure=code!=0
                        receipt=dict(action_id='Q16c',attempt_id=request['attempt_id'],request_sha256=d['request']['sha256'],
                            authorization_sha256=d['authorization']['sha256'],schema_version='cpu-prefetch-stage17-phase-action-'+('failure' if failure else 'completion')+'/6',
                            leader_reaped=True,process_group_gone=True,restoration_verified=True)
                        field='requested_hex' if failure else 'expected_hex'
                        receipt['recovery_readback' if failure else 'live_restoration_readback']=[dict(cpu=i,**{field:'0000000000000001'},
                            observed_hex='0000000000000001',matches=True) for i in (0,1,8)]
                        receipt.update(dict(quarantine_operation=dict(performed=False)) if failure else dict(quarantined=False))
                        put(root/'family'/('stage17-q16c-'+('failure' if failure else 'completion')+'-v6.json'),receipt)
                    if role=='analyze':
                        (root/'q16c-analysis-1').mkdir();put(root/'q16c-analysis-1/complete.json',
                            dict(status='ALL_180_VALID_DESCRIPTIVE_COMPLETE',reports=list(range(180)),all_workers_reaped=True))
                    self.process.returncode=code;return code
                def stop(self,deadline):pass
            helper=types.SimpleNamespace(**{**vars(original),'OwnedProcess':NativeBoundary,'subreaper':lambda:None})
            with mock.patch.object(current.os,'geteuid',return_value=0),mock.patch.object(current.os,'chown'),mock.patch.object(current.os,'sched_setaffinity'):
                code=current.run(args,c,helper,window,restoration)
            result=json.loads((root/'q16c-study-1/complete.json').read_text())
            self.assertTrue(json.loads((root/'q16c-study-1/partition-restoration.json').read_text())['verified'])
            self.assertFalse((root/'cgroup').exists());self.assertEqual(result['automatic_retries'],0)
            self.assertFalse(result['phase18_authority'])
            sys.modules.pop('q16c_bound_isolation',None)
            return code,result,calls

    def test_full_workflow_restores_before_independent_analysis(self):
        code,result,calls=self.exercise();self.assertEqual(code,0,result)
        self.assertEqual(calls,['construct','sign','check','collect','analyze']);self.assertTrue(result['success'])

    def test_admission_or_collection_failure_restores_and_stops_without_retry(self):
        for failed,expected in [('check',['construct','sign','check']),('collect',['construct','sign','check','collect'])]:
            with self.subTest(failed=failed):
                code,result,calls=self.exercise(failed);self.assertEqual(code,1);self.assertFalse(result['success'])
                self.assertEqual(calls,expected);self.assertTrue(result['errors'])


if __name__=='__main__':unittest.main()
