"""Real native channel, codecs, ledger and ACK; explicitly synthetic admission.

The caller-supplied VerifiedRequest is an admission fixture, not a real scoped
resolution or a new signature verifier. D319/D322 cover that upstream boundary.
This test never invokes the production measurement entry or changes hardware.
"""
import argparse
import copy
from dataclasses import asdict,replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_parent_v1 as parent
import test_stage17_s180_archive_broker_v1 as fixtures
import stage17_s180_compaction_v1 as compaction
import test_stage17_s180_environment_v1 as hardware_tests
import s180_compaction_fixture


class ParentTests(unittest.TestCase):
    encoder=None
    channel_fixture=None

    def setUp(self):
        self.f=fixtures.S180BrokerTests()
        self.f.encoder=self.encoder;self.f.channel_fixture=self.channel_fixture
        self.f.reserve_before_admission=True
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.request=copy.deepcopy(self.f.request)
        native=dict(role=parent.authority.ROLE,profile=parent.authority.PROFILE,
            sha256=hashlib.sha256(self.channel_fixture.read_bytes()).hexdigest(),size_bytes=self.channel_fixture.stat().st_size)
        self.request.update(request_id='software-request',authorization_id='software-authorization',attempt_id='software-attempt',
            stand_id=self.request['plan']['blueprint']['stand_id'],runtime_binding=native,
            release_binding=dict(source_revision='0'*40,worker_sha256=native['sha256']),synthetic_test_only=False,phase18_authority=False)
        now=time.monotonic_ns();st=self.f.working.stat()
        self.authorization={k:self.request[k] for k in ('session_id','request_id','authorization_id','attempt_id',
            'stand_id','runtime_binding','release_binding','synthetic_test_only','phase18_authority')}
        self.authorization.update(schema_version=parent.authority.SCHEMA,plan_sha256=self.f.family,
            prerequisite_bindings=copy.deepcopy(self.request['prerequisite_bindings']),
            evidence_root_binding=dict(absolute_path=str(self.f.working),device=st.st_dev,inode=st.st_ino),
            window_binding=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_monotonic_ns=now,end_monotonic_ns=now+parent.authority.DAY_NS),
            issued_at_epoch_seconds=time.time_ns()//10**9-1,expires_at_epoch_seconds=time.time_ns()//10**9+86420)
        self.refresh()

    def refresh(self):
        raw=parent.archive.canonical(self.authorization)
        self.request['prerequisite_bindings']['ext010_authorization_sha256']=hashlib.sha256(raw).hexdigest()
        self.verified=parent.authority.VerifiedRequest(raw,parent.archive.canonical(self.request))

    def consume(self):
        with self.f.store() as store:return parent.consume_attempt(verified=self.verified,store=store)

    def test_attempt_is_exclusive_durable_and_charged_to_existing_shared_quota(self):
        with self.f.store() as store:
            before=store.physical_usage();scope=(store.root/'scope.json').read_bytes();families=dict(store._families)
            binding=parent.consume_attempt(verified=self.verified,store=store)
            raw=store._read_bound(store.root/'metadata'/binding.file_name,binding.binding(),65536)
            self.assertEqual(json.loads(raw)['attempts'],1)
            self.assertEqual(json.loads(raw)['automatic_retries'],0)
            self.assertGreaterEqual(store.physical_usage()-before,len(raw))
            self.assertEqual(store._families,families)
            self.assertEqual((store.root/'scope.json').read_bytes(),scope)
            with self.assertRaises(FileExistsError):parent.consume_attempt(verified=self.verified,store=store)

    def test_partial_attempt_and_native_entry_prevent_another_consumption(self):
        name=parent._attempt_name(self.f.family);path=self.f.root/'metadata'/name;path.write_bytes(b'{')
        with self.assertRaises(FileExistsError):self.consume()
        self.assertEqual(path.read_bytes(),b'{')
        path.unlink()  # Test-created partial marker only.
        native=self.f.working/'s180-session-entry.json';native.write_bytes(b'{}')
        with self.assertRaisesRegex(parent.ParentError,'native evidence'):self.consume()
        self.assertFalse(path.exists())

    def test_expired_window_or_foreign_output_does_not_consume_attempt(self):
        original=copy.deepcopy(self.authorization)
        self.authorization['window_binding']['boot_id']='another-boot';self.refresh()
        with self.assertRaises(parent.authority.AuthorityError):self.consume()
        self.authorization=original;self.authorization['evidence_root_binding']['inode']+=1;self.refresh()
        with self.assertRaisesRegex(parent.ParentError,'root differs'):self.consume()
        self.assertFalse((self.f.root/'metadata'/parent._attempt_name(self.f.family)).exists())

    def exchange(self,*,expected=None,mutate=None,constructor_changes=None):
        self.consume()
        lease=fixtures.supervisor.SupervisorLease()
        endpoint,child=fixtures.channel.create_channel()
        directory=os.open(self.f.working,os.O_RDONLY|os.O_DIRECTORY)
        process=None;worker=None;driver=None;component=None;cleaned=False
        try:
            lease.enter()
            process=subprocess.Popen([str(self.channel_fixture),str(child.fileno()),str(directory),
                self.verified.request_sha256,self.f.scope,str(self.f.deadline)],pass_fds=(child.fileno(),directory),
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            child.close();worker=fixtures.PinnedWorker(process.pid)
            driver=fixtures.channel.ArchiveChannel(endpoint,worker=worker,directory_fd=directory,
                request_sha256=self.verified.request_sha256,program_scope_sha256=self.f.scope,captures=180,
                maximum_checkpoint_bytes=131072,maximum_custody_receipt_bytes=131072,maximum_archive_ns=90*10**9,
                session_id=self.request['session_id'],plan_sha256=self.f.family)
            args=dict(verified=self.verified,channel=driver,program_root=self.f.root,profile=self.f.profile,
                limits=self.f.limits,custody_limits=self.f.custody_limits,identity_model=lease.identity_model,
                decoder_limits=parent.archive.DecodeLimits(32768,4*1024**2,4*1024**2,8*1024**2,4*1024**2,100,1<<22,self.f.deadline))
            args.update(constructor_changes or {})
            component=parent.CheckpointParent(**args)
            if mutate:mutate(component)
            outcome=component.checkpoint(deadline_ns=self.f.deadline)
            self.assertEqual(outcome['continuation_allowed'],expected)
            self.assertEqual(component.stopped,not expected)
            receipt=self.f.root/'metadata'/outcome['parent_receipt']['file_name']
            raw=receipt.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),outcome['parent_receipt']['sha256'])
            proof=json.loads(raw)
            self.assertEqual(proof['broker_processes'],1+3*len(self.f.document['artifacts']))
            self.assertTrue(proof['broker_cleanup']['leader_reaped'])
            self.assertTrue(proof['broker_cleanup']['process_group_gone'])
            self.assertFalse(proof['execution_authority'])
            self.assertEqual(proof['scientific_validity'],'NOT_ASSESSED')
            cleanup=fixtures.supervisor.cleanup_process_group(process,force_stop=False,
                leader_wait_deadline_ns=time.monotonic_ns()+2*10**9,global_deadline_ns=self.f.deadline,
                identity_model=lease.identity_model)
            cleaned=True
            stdout,stderr=process.communicate(timeout=5)
            self.assertEqual(process.returncode,0 if expected else 2,stderr)
            self.assertEqual(json.loads(stdout),dict(accepted=expected))
            self.assertTrue(cleanup.leader_reaped and cleanup.process_group_gone)
            self.assertEqual(driver.ordinal,1)
            if not expected:
                with self.assertRaisesRegex(parent.ParentError,'stopped'):component.checkpoint(deadline_ns=self.f.deadline)
            return proof
        except BaseException:
            if driver is not None:self.assertTrue(driver.stopped)
            if component is not None:
                self.assertTrue(component.stopped)
                self.assertTrue(driver.stopped)
                self.assertEqual(driver.ordinal,0)
                with self.assertRaisesRegex(parent.ParentError,'stopped'):component.checkpoint(deadline_ns=self.f.deadline)
            raise
        finally:
            child.close();endpoint.close();os.close(directory)
            try:
                if process is not None and not cleaned:
                    cleanup=fixtures.supervisor.cleanup_process_group(process,force_stop=True,
                        leader_wait_deadline_ns=time.monotonic_ns()+2*10**9,global_deadline_ns=self.f.deadline,
                        identity_model=lease.identity_model)
                    self.assertTrue(cleanup.leader_reaped and cleanup.process_group_gone)
            finally:
                if process is not None:
                    if process.stdout:process.stdout.close()
                    if process.stderr:process.stderr.close()
                if worker is not None:worker.close()
                lease.close()

    def test_actual_native_broker_independent_ledger_parent_receipt_and_ack(self):
        self.exchange(expected=True)

    def test_failed_capture_is_retained_and_receives_only_stop_ack(self):
        self.f.document['native_complete']=False
        self.f.document['native_result_after_private_cleanup']['stop']=12
        self.f.write_checkpoint();self.exchange(expected=False)

    def test_partial_failed_prefix_is_archived_without_deleting_unlisted_files(self):
        self.f.document['native_complete']=False
        self.f.document['native_result_after_private_cleanup']['stop']=12
        self.f.document['artifacts']=self.f.document['artifacts'][:2]
        self.f.write_checkpoint();self.exchange(expected=False)
        for name in fixtures.contract.capture_names(0)[2:]:
            self.assertEqual((self.f.working/name).read_bytes(),self.f.originals[name])

    def test_changed_attempt_stops_before_broker_and_keeps_all_originals(self):
        def mutate(_):
            path=self.f.root/'metadata'/parent._attempt_name(self.f.family);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(parent.ParentError,'attempt changed'):self.exchange(mutate=mutate)
        for name,raw in self.f.originals.items():self.assertEqual((self.f.working/name).read_bytes(),raw)

    def test_independent_ledger_failure_after_real_broker_sends_no_ack(self):
        real=parent.registry.verify_capture_metadata
        def corrupt(**args):
            path=next((self.f.root/'archives').iterdir());raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
            return real(**args)
        with mock.patch.object(parent.registry,'verify_capture_metadata',side_effect=corrupt):
            with self.assertRaises(parent.archive.ArchiveError):self.exchange()
        self.assertFalse(list((self.f.root/'metadata').glob('s180-parent-*-e0.json')))
        self.assertTrue(list((self.f.root/'archives').iterdir()))

    def test_actual_wrong_worker_image_is_rejected_before_any_codec(self):
        self.authorization['runtime_binding']=dict(self.authorization['runtime_binding'],sha256='f'*64)
        self.request['runtime_binding']=self.authorization['runtime_binding'];self.refresh()
        with self.assertRaisesRegex(parent.ParentError,'worker image differs'):self.exchange()
        self.assertFalse(list((self.f.root/'archives').iterdir()))

    def test_changed_archive_profile_is_rejected_before_any_codec(self):
        changed=replace(self.f.profile,decoder=replace(self.f.profile.decoder,implementation_profile_sha256='f'*64))
        with self.assertRaisesRegex(parent.ParentError,'archive profile differs'):
            self.exchange(constructor_changes=dict(profile=changed))
        self.assertFalse(list((self.f.root/'archives').iterdir()))

    def test_foreign_programme_root_is_rejected_before_any_codec(self):
        with self.assertRaisesRegex(parent.ParentError,'programme root differs'):
            self.exchange(constructor_changes=dict(program_root=self.f.base/'foreign-programme'))
        self.assertFalse(list((self.f.root/'archives').iterdir()))

    def test_broker_input_bound_failure_keeps_originals_and_sends_no_ack(self):
        with self.assertRaises(parent.archive.ArchiveError):
            self.exchange(constructor_changes=dict(limits=replace(self.f.limits,max_input_bytes=100)))
        for name,raw in self.f.originals.items():self.assertEqual((self.f.working/name).read_bytes(),raw)

    def guarded_fixture(self):
        def monitored(plan):
            for row in plan['captures']:row['monitoring']=dict(environment_sources=[])
            return compaction.monitored_plan(plan)
        with mock.patch.object(fixtures.S180BrokerTests,'configure_plan',side_effect=monitored):
            fixture=ParentTests();fixture.encoder=self.encoder;fixture.channel_fixture=self.channel_fixture;fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        hardware=hardware_tests.EnvironmentTests();hardware.setUp();self.addCleanup(hardware.doCleanups)
        io=hardware.io();io.__enter__();self.addCleanup(io.close)
        owner=compaction.environment._PreparedEnvironment(token=compaction.environment._TOKEN,plan=fixture.request['plan'],
            window=fixture.authorization['window_binding'],core=hardware.core,preparation=hardware.pre,
            devices=hardware.devices,affinity=hardware.affinity,
            command_state=dict(deadline=fixture.authorization['window_binding']['end_monotonic_ns']))
        guard,control,_=s180_compaction_fixture.attach(self,owner,hardware.root)
        return fixture,guard,control

    def test_guard_receipts_precede_real_native_ack_and_remain_in_parent_metadata(self):
        fixture,guard,_=self.guarded_fixture()
        proof=fixture.exchange(expected=True,constructor_changes=dict(platform_guard=guard))
        self.assertEqual(proof['platform_guard']['after_capture']['boundary'],'AFTER_CAPTURE')
        self.assertEqual(proof['platform_guard']['before_release']['observed_value'],0)
        self.assertEqual(proof['platform_guard']['before_release']['approval_sha256'],compaction.APPROVAL_SHA)

    def test_guard_failure_after_real_custody_retains_archives_and_sends_no_ack(self):
        fixture,guard,control=self.guarded_fixture();verify=parent.registry.verify_capture_metadata
        def changed(**args):
            result=verify(**args);control.write_text('1\n');return result
        with mock.patch.object(parent.registry,'verify_capture_metadata',side_effect=changed):
            with self.assertRaisesRegex(RuntimeError,'became enabled'):
                fixture.exchange(constructor_changes=dict(platform_guard=guard))
        self.assertTrue(list((fixture.f.root/'archives').iterdir()))
        self.assertFalse(list((fixture.f.root/'metadata').glob('s180-parent-*-e0.json')))
        self.assertTrue(guard.failed)

    def test_guard_for_another_family_is_rejected_before_codecs(self):
        fixture,guard,_=self.guarded_fixture();guard.owner['plan_sha256']='f'*64
        with self.assertRaisesRegex(parent.ParentError,'another admitted family'):
            fixture.exchange(constructor_changes=dict(platform_guard=guard))
        self.assertFalse(list((fixture.f.root/'archives').iterdir()))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--encoder',type=Path,required=True)
    parser.add_argument('--channel-fixture',type=Path,required=True)
    args,rest=parser.parse_known_args();ParentTests.encoder=args.encoder.resolve();ParentTests.channel_fixture=args.channel_fixture.resolve()
    unittest.main(argv=[__file__,*rest])
