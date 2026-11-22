"""Local owned-dispatch integration, no production measurements or hardware.

The private dispatch seam receives explicit fixture admission/source provenance.
All36 sealed FDs and real C++ parsing/channel/codecs/supervision are exercised.
The separately linked endpoint identifies itself as synthetic and cannot pass
the public production identity gate. Upstream signature/source proof is tested
by D319/D322/D324; this suite does not assert fresh scientific admission.
"""
import argparse
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import time
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_launcher_v1 as launch
import test_stage17_s180_archive_broker_v1 as fixtures
from test_stage17_s180_plan_prepare_v1 import fixture


class FullFixture(fixtures.S180BrokerTests):
    describer=None
    def configure_plan(self,minimal):
        identity=json.loads(subprocess.check_output([str(self.describer),'--stage17-s180-runtime-identity-v1'],timeout=30))
        sizing=fixture(identity['source_revision'])
        sizing['storage']=dict(minimal['storage'],maximum_custody_receipt_bytes=131072)
        sizing['budget'].update(setup_ns=30*10**9,finalization_ns=2*10**9)
        for entry in sizing['captures']:
            entry['execution_budget'].update(watchdog_ns=100*10**9,archive_ns=90*10**9,max_output_bytes=4*1024**2)
        raw=self.describer.read_bytes()
        plan,_=launch.planning.prepare(sizing,worker=launch.runtime.ImageBinding(self.describer,len(raw),hashlib.sha256(raw).hexdigest()),
            deadline_ns=time.monotonic_ns()+60*10**9)
        return plan


class LauncherTests(unittest.TestCase):
    encoder=None;endpoint=None;describer=None;sanitized_endpoint=None

    def setUp(self):
        self.f=FullFixture();self.f.encoder=self.encoder;self.f.describer=self.describer
        self.f.reserve_before_admission=True;self.f.setUp();self.addCleanup(self.f.doCleanups)
        # The endpoint's90s archive interval must fit the outer test deadline,
        # including preparation already elapsed. Do not weaken channel checks.
        self.f.deadline=time.monotonic_ns()+180*10**9
        self.f.limits=replace(self.f.limits,deadline_ns=self.f.deadline,authority_expiry_monotonic_ns=self.f.deadline)
        self.f.custody_limits=replace(self.f.custody_limits,deadline_ns=self.f.deadline)
        self.request=copy.deepcopy(self.f.request)
        raw=self.endpoint.read_bytes();self.image=launch.runtime.ImageBinding(self.endpoint,len(raw),hashlib.sha256(raw).hexdigest())
        native=dict(role=launch.authority.ROLE,profile=launch.authority.PROFILE,sha256=self.image.sha256,size_bytes=self.image.size_bytes)
        self.request.update(session_id='software-launcher-exit',request_id='software-request',authorization_id='software-authorization',
            attempt_id='software-attempt',stand_id=self.request['plan']['blueprint']['stand_id'],runtime_binding=native,
            release_binding=dict(source_revision=self.request['plan']['source_revision'],worker_sha256=native['sha256']),
            synthetic_test_only=False,phase18_authority=False)
        now=time.monotonic_ns();st=self.f.working.stat()
        self.authorization={k:self.request[k] for k in ('session_id','request_id','authorization_id','attempt_id',
            'stand_id','runtime_binding','release_binding','synthetic_test_only','phase18_authority')}
        self.authorization.update(schema_version=launch.authority.SCHEMA,plan_sha256=self.f.family,
            prerequisite_bindings=copy.deepcopy(self.request['prerequisite_bindings']),
            evidence_root_binding=dict(absolute_path=str(self.f.working),device=st.st_dev,inode=st.st_ino),
            window_binding=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_monotonic_ns=now,end_monotonic_ns=now+launch.authority.DAY_NS),
            issued_at_epoch_seconds=time.time_ns()//10**9-1,expires_at_epoch_seconds=time.time_ns()//10**9+86420)
        self.refresh()
        bindings=[];seen=set()
        for entry in self.request['plan']['captures']:
            for p in entry['phases']:
                artifact=p['source_artifact']
                if artifact['artifact_id'] in seen:continue
                seen.add(artifact['artifact_id']);raw=struct.pack('>4Q',1,2,2,3)
                fd=launch.runtime._sealed_input(raw,'software-launcher-original')
                bindings.append(dict(artifact_id=artifact['artifact_id'],canonical_sha256=hashlib.sha256(raw).hexdigest(),
                    size_bytes=len(raw),descriptor=fd))
        self.bank=launch.sources._VerifiedSources(token=launch.sources._TOKEN,report=dict(plan_sha256=self.f.family,software_fixture_only=True),
            bindings=bindings,originals={},maximum_vector_bytes=1024**2,
            valid_until_ns=self.authorization['window_binding']['end_monotonic_ns'],
            maximum_loading_ns=self.request['plan']['budget']['setup_ns'])
        self.addCleanup(self.bank._close)
        self.limits=launch.LaunchLimits(512*1024**2,min(resource.getrlimit(resource.RLIMIT_MEMLOCK)[0],8*1024**2),
            1024**3,512,16384,2*10**9,7200*10**9)
        self.restores=[]

    def refresh(self):
        raw=launch.archive.canonical(self.authorization)
        self.request['prerequisite_bindings']['ext010_authorization_sha256']=hashlib.sha256(raw).hexdigest()
        self.verified=launch.authority.VerifiedRequest(raw,launch.archive.canonical(self.request))

    def restore(self,*,verified,native_cleanup,deadline_ns):
        self.assertEqual(verified.request_sha256,self.verified.request_sha256)
        self.assertTrue(native_cleanup is None or (native_cleanup.leader_reaped and native_cleanup.process_group_gone))
        self.assertEqual(launch.supervisor.ProcfsIdentityModel().direct_children(),{})
        self.restores.append(native_cleanup)
        return dict(schema_version='cpu-prefetch-stage17-s180-environment-restoration/1',plan_sha256=self.f.family,
            boot_id=self.authorization['window_binding']['boot_id'],hardware_restoration_verified=True,
            cpu_isolation_restoration_verified=True,maintenance_restoration_verified=True,errors=[])

    def arguments(self):
        return dict(verified=self.verified,source_owner=self.bank,native_image=self.image,archive_profile=self.f.profile,
            program_root=self.f.root,broker_limits=self.f.limits,custody_limits=self.f.custody_limits,
            decoder_limits=launch.archive.DecodeLimits(32768,4*1024**2,4*1024**2,8*1024**2,4*1024**2,100,1<<22,self.f.deadline),
            limits=self.limits,restore_environment=self.restore)

    def run_case(self,case,**changes):
        self.request['session_id']='software-launcher-'+case;self.authorization['session_id']=self.request['session_id'];self.refresh()
        self.f.document['session_id']=self.request['session_id'];self.f.write_checkpoint()
        args=self.arguments();args.update(changes)
        before=dict(as_limit=resource.getrlimit(resource.RLIMIT_AS),lock=resource.getrlimit(resource.RLIMIT_MEMLOCK),
            files=resource.getrlimit(resource.RLIMIT_NOFILE),handlers={s:launch.signal.getsignal(s) for s in (launch.signal.SIGTERM,launch.signal.SIGINT,launch.signal.SIGHUP)})
        result=launch._execute_verified(**args)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS),before['as_limit'])
        self.assertEqual(resource.getrlimit(resource.RLIMIT_MEMLOCK),before['lock'])
        self.assertEqual(resource.getrlimit(resource.RLIMIT_NOFILE),before['files'])
        for s,h in before['handlers'].items():self.assertEqual(launch.signal.getsignal(s),h)
        doc=result['document'];self.assertEqual(doc['status'],'STOPPED')
        self.assertTrue(doc['native_cleanup']['leader_reaped'] and doc['native_cleanup']['process_group_gone'])
        self.assertEqual(doc['automatic_retries'],0);self.assertEqual(doc['scientific_validity'],'NOT_ASSESSED')
        raw=(self.f.root/'metadata'/result['terminal']['file_name']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['terminal']['sha256'])
        self.assertEqual(len(self.restores),1)
        self.assertNotIn(b'runtime error:',bytes.fromhex(doc['console_hex']))
        return result

    def test_real_fixed_dispatch_reads_all36_sources_and_retains_nonzero_exit(self):
        result=self.run_case('exit')
        self.assertEqual(result['document']['native_cleanup']['returncode'],23)
        self.assertEqual((self.f.working/'software-launcher-started.txt').read_text(),'36 sealed sources read\n')
        self.assertIn(b'test-only early exit',bytes.fromhex(result['document']['console_hex']))
        self.assertEqual(result['document']['acknowledged_captures'],0)

    def test_failed_capture_uses_real_broker_stop_ack_then_allows_native_finalization(self):
        self.f.document['native_complete']=False
        self.f.document['native_result_after_private_cleanup']['stop']=12
        result=self.run_case('stop')
        self.assertEqual(result['document']['acknowledged_captures'],1,result['document']['failure'])
        self.assertEqual(result['document']['native_cleanup']['returncode'],2)
        self.assertTrue((self.f.working/'software-launcher-native-restored.txt').is_file())
        self.assertEqual(result['document']['native_cleanup']['terminal_cleanup_outcome'],'NORMAL_LEADER_REAPED_GROUP_QUIESCENT')
        self.assertEqual(len(list((self.f.root/'archives').iterdir())),8)

    def test_native_console_exhaustion_stops_and_reaps_owned_group(self):
        result=self.run_case('spam')
        self.assertIn('console limit',result['document']['failure'])
        self.assertLessEqual(len(bytes.fromhex(result['document']['console_hex'])),16385)

    def test_sigterm_runs_cleanup_and_restoration_then_restores_handlers(self):
        result=self.run_case('interrupt')
        self.assertIn('signal',result['document']['failure'])

    def test_escaped_descendant_is_reaped_before_environment_restoration(self):
        result=self.run_case('descendant')
        self.assertTrue(result['document']['native_cleanup']['descendants_detected_after_leader_exit'])
        self.assertGreaterEqual(result['document']['native_cleanup']['maximum_descendant_count'],1)
        self.assertTrue(result['document']['quarantined'])

    def test_missing_restorer_and_serialized_source_report_fail_before_attempt(self):
        for changes in (dict(restore_environment=None),dict(source_owner={'source_count':36})):
            args=self.arguments();args.update(changes)
            with self.assertRaises(launch.LaunchError):launch._execute_verified(**args)
        self.assertFalse((self.f.root/'metadata'/launch.parent._attempt_name(self.f.family)).exists())

    def test_insufficient_original_window_fails_before_attempt(self):
        args=self.arguments();args['limits']=replace(self.limits,post_native_reserve_ns=launch.authority.DAY_NS)
        with self.assertRaisesRegex(launch.LaunchError,'original window'):launch._execute_verified(**args)
        self.assertFalse((self.f.root/'metadata'/launch.parent._attempt_name(self.f.family)).exists())

    def test_attempt_cannot_dispatch_twice(self):
        self.run_case('exit')
        with self.assertRaises(FileExistsError):launch._execute_verified(**self.arguments())
        self.assertEqual(len(self.restores),1)

    def test_failure_after_marker_publication_restores_without_dispatch_or_retry(self):
        real=launch.parent.consume_attempt
        def fail(**args):
            real(**args);raise OSError('test-only failure after durable consumption')
        with mock.patch.object(launch.parent,'consume_attempt',side_effect=fail):
            result=launch._execute_verified(**self.arguments())
        self.assertEqual(result['document']['status'],'STOPPED')
        self.assertFalse(result['document']['native_spawned'])
        self.assertIsNone(result['document']['native_cleanup'])
        self.assertIsNone(result['document']['attempt'])
        self.assertTrue(result['document']['quarantined'])
        self.assertEqual(len(self.restores),1)
        self.assertTrue((self.f.root/'metadata'/launch.parent._attempt_name(self.f.family)).is_file())

    def test_bad_independent_restoration_never_promotes_success(self):
        def bad(**kwargs):
            result=self.restore(**kwargs);result['hardware_restoration_verified']=False;return result
        result=self.run_case('exit',restore_environment=bad)
        self.assertIsNone(result['document']['environment_restoration'])
        self.assertTrue(result['document']['quarantined'])
        self.assertIn('restoration failed',result['document']['environment_restoration_failure'])

    def test_public_entry_rejects_serialized_or_synthetic_admission(self):
        args=self.arguments();del args['verified']
        for fake in (dict(scoped_inputs_complete=True),SimpleNamespace(mode=False)):
            with self.assertRaisesRegex(launch.LaunchError,'actual production scoped journal'):
                launch.launch(journal=fake,authorization_bytes=self.verified.authorization_bytes,signature_path=self.f.base/'no-signature',**args)
        self.assertFalse((self.f.root/'metadata'/launch.parent._attempt_name(self.f.family)).exists())

    def native_document(self):
        clean=dict(cleanup_attempted=True,unlock=dict(return_value=0,error_number=0),unmap=dict(return_value=0,error_number=0))
        expected=self.request['plan']['hardware']['prestate']
        plots=[dict(requested_state=state,restoration_verified=True,independent_restore_observations=[
            dict(cpu=r['cpu'],requested_prestate=r['value'],observed_value=r['value'],read_succeeded=True) for r in expected])
            for state in ('H1','H0')]
        return dict(schema_version='cpu-prefetch-stage17-s180-session-result/1',session_id=self.request['session_id'],
            plan_sha256=self.f.family,blueprint_sha256=launch.planning.BLUEPRINT_SHA256,method_id='STAGE17-PILOT-S180-DESCRIPTIVE-v1',
            attempted=180,completed=180,stop=1,restoration_attempted=True,restoration_verified=True,cleanup_verified=True,
            contexts_after_family_release=[dict(records=copy.deepcopy(clean),queues=copy.deepcopy(clean)) for _ in range(6)],
            whole_plots=plots,execution_authority=False,phase18_authority=False)

    def check_result(self,document,acks):
        (self.f.working/'s180-session-result.json').write_bytes(launch.archive.canonical(document))
        fd=os.open(self.f.working,os.O_RDONLY|os.O_DIRECTORY)
        try:return launch._native_result(fd,self.verified,acks,1024**2)
        finally:os.close(fd)

    def test_native_completion_requires_all_actual_acknowledgements_and_shared_cleanup(self):
        document=self.native_document()
        self.assertEqual(self.check_result(document,180)['file_name'],'s180-session-result.json')
        for acks in (0,179,True):
            with self.assertRaisesRegex(launch.LaunchError,'acknowledgements'):self.check_result(document,acks)
        for change in (lambda d:d.update(completed=True),lambda d:d.update(phase18_authority=True),
                lambda d:d['contexts_after_family_release'].pop(),
                lambda d:d['contexts_after_family_release'][0]['records']['unmap'].update(return_value=False),
                lambda d:d['whole_plots'][0]['independent_restore_observations'][0].update(observed_value=False)):
            changed=copy.deepcopy(document);change(changed)
            with self.assertRaises(launch.LaunchError):self.check_result(changed,180)

    def test_real_fixture_identity_cannot_pass_production_gate(self):
        identity=json.loads(subprocess.check_output([str(self.endpoint),'--stage17-s180-runtime-identity-v1'],timeout=30))
        request=copy.deepcopy(self.request);request['plan']['source_revision']=identity['source_revision']
        with self.assertRaisesRegex(launch.LaunchError,'clean production native'):launch._check_identity(identity,request)

    def test_native_entry_result_and_attempt_metadata_are_charged_in_shared_quota(self):
        names=['s180-session-entry.json','s180-session-result.json','s180-e0-attempt.json','s180-e179-attempt.json']
        for name in names:
            path=self.f.working/name;path.write_bytes(b'{"software_fixture":true}');path.chmod(0o600)
        with self.f.store() as store:
            original=launch.custody.ProgramStore.physical_accounting(store)
            current=store.physical_accounting()
            self.assertEqual(current.quota_bytes-original.quota_bytes,
                sum(max((self.f.working/n).stat().st_size,(self.f.working/n).stat().st_blocks*512) for n in names))
            self.assertEqual(current.unique_objects-original.unique_objects,len(names))

    def test_unsafe_native_metadata_is_rejected_without_following_aliases(self):
        path=self.f.working/'s180-session-entry.json'
        path.symlink_to(self.f.working/next(iter(self.f.originals)))
        with self.f.store() as store:
            with self.assertRaisesRegex(launch.custody.CustodyError,'unsafe retained'):store.physical_accounting()

    def test_sanitized_cpp_harness_parses_exact_sealed_context_and_all_sources(self):
        self.assertIsNotNone(self.sanitized_endpoint)
        lease=launch.supervisor.SupervisorLease();process=None;lease.enter()
        try:
            with launch.contextlib.ExitStack() as stack:
                endpoint,child=launch.channels.create_channel();stack.callback(endpoint.close);stack.callback(child.close)
                directory=os.open(self.f.working,os.O_RDONLY|os.O_DIRECTORY);stack.callback(os.close,directory)
                context,fds=self.bank.native_inputs(plan_sha256=self.f.family,loading_deadline_ns=time.monotonic_ns()+20*10**9)
                context=launch._context(self.verified,context,child,directory)
                request=launch.runtime._sealed_input(self.verified.request_bytes,'software-sanitized-request');stack.callback(os.close,request)
                control=launch.runtime._sealed_input(launch.archive.canonical(context),'software-sanitized-context');stack.callback(os.close,control)
                process=subprocess.Popen([str(self.sanitized_endpoint),'--execute-stage17-s180-session-v1','--request-fd',str(request),
                    '--context-fd',str(control),'--output-dir-fd',str(directory),'--fixed-dispatch-end'],
                    pass_fds=(request,control,directory,child.fileno(),*fds),start_new_session=True,
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=dict(PATH='/usr/bin:/bin',
                        LD_LIBRARY_PATH=os.environ.get('LD_LIBRARY_PATH',''),ASAN_OPTIONS='detect_leaks=0',
                        UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1'))
                cleanup=launch.supervisor.cleanup_process_group(process,force_stop=False,
                    leader_wait_deadline_ns=time.monotonic_ns()+10*10**9,global_deadline_ns=self.f.deadline,
                    identity_model=lease.identity_model)
                stdout,stderr=process.communicate(timeout=5)
                self.assertEqual(cleanup.returncode,23,stderr)
                self.assertNotIn(b'AddressSanitizer',stderr);self.assertNotIn(b'runtime error:',stderr)
                self.assertEqual((self.f.working/'software-launcher-started.txt').read_text(),'36 sealed sources read\n')
        finally:
            if process is not None and process.returncode is None:
                launch.supervisor.cleanup_process_group(process,force_stop=True,
                    leader_wait_deadline_ns=time.monotonic_ns()+2*10**9,global_deadline_ns=self.f.deadline,
                    identity_model=lease.identity_model)
            if process is not None:
                if process.stdout:process.stdout.close()
                if process.stderr:process.stderr.close()
            lease.close()


def load_tests(loader,tests,pattern):
    names=loader.getTestCaseNames(LauncherTests)
    if LauncherTests.sanitized_endpoint is None:names=[n for n in names if not n.startswith('test_sanitized_')]
    return unittest.TestSuite(LauncherTests(n) for n in names)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--encoder',type=Path,required=True)
    p.add_argument('--endpoint',type=Path,required=True);p.add_argument('--describer',type=Path,required=True)
    p.add_argument('--sanitized-endpoint',type=Path)
    args,rest=p.parse_known_args();LauncherTests.encoder=args.encoder.resolve()
    LauncherTests.endpoint=args.endpoint.resolve();LauncherTests.describer=args.describer.resolve()
    LauncherTests.sanitized_endpoint=None if args.sanitized_endpoint is None else args.sanitized_endpoint.resolve()
    unittest.main(argv=[__file__,*rest])
