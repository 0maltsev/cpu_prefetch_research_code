"""Real sealed ELF/pidfd/subreaper clock transport; explicit platform doubles.

The endpoint emits software data, not clock measurements. Only temporary files
represent MSRs/cgroups/sysctl, with no accepted stand qualification credit.
Production code has no switch permitting this endpoint or hardware backend.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_clock_qualification_v1 as clock
import test_stage17_s180_environment_v1 as hardware
import s180_compaction_fixture


class ClockTests(unittest.TestCase):
    endpoint=None

    def setUp(self):
        self.hardware=hardware.EnvironmentTests();self.hardware.setUp();self.addCleanup(self.hardware.doCleanups)
        self.hardware.plan=clock.compaction.monitored_plan(self.hardware.plan)
        self.hardware.sha=clock.environment.planning.sha(self.hardware.plan)
        self.io=self.hardware.io();self.io.__enter__();self.addCleanup(self.io.close)
        self.owner=self.hardware.guard()
        self.guard,self.control,_=s180_compaction_fixture.attach(self,self.owner,self.hardware.root)
        self.stack=clock.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.root=self.hardware.root/'clock-qualification'
        self.stack.enter_context(mock.patch.object(clock,'ROOT',self.root))
        # Private test binding to a separate synthetic ELF, with actual /proc
        # executable hashing preserved. Cgroup placement is the platform double.
        self.image=clock.runtime.ImageBinding(self.endpoint,self.endpoint.stat().st_size,
            hashlib.sha256(self.endpoint.read_bytes()).hexdigest())
        self.stack.enter_context(mock.patch.object(clock.compaction,'CLOCK_SHA',self.image.sha256))
        self.stack.enter_context(mock.patch.object(clock.compaction,'CLOCK_SIZE',self.image.size_bytes))
        self.stack.enter_context(mock.patch.object(clock.compaction,'_membership',
            return_value='/'+clock.environment.UNIT+'/reserved'))
        self.production_place=clock._place
        self.stack.enter_context(mock.patch.object(clock,'_place',side_effect=self.place))

    def place(self,entry):
        # Run the actual child limits/placement/readback routine. The numeric
        # CPU and fake membership/file behavior are explicit platform doubles.
        self.production_place(dict(entry,controller_cpu=min(os.sched_getaffinity(0))))
        (self.hardware.cg/'cgroup.procs').write_text('')

    def qualify(self):
        return clock.qualify_clocks(environment_owner=self.owner,clock_image=self.image,
            deadline_ns=time.monotonic_ns()+300*10**9)

    def mode(self,value):(self.hardware.root/'test-mode').write_text(value)

    def result(self,pair):return json.loads((self.root/pair/'result.json').read_bytes())

    def test_actual_sealed_processes_are_ordered_reaped_and_prove_only_clock_pairs(self):
        owned=self.qualify();proof=owned.proof(plan_sha256=self.hardware.sha)
        self.assertTrue(proof['clock_pairs_qualified']);self.assertFalse(proof['full_qualification'])
        self.assertFalse(proof['execution_authority']);self.assertEqual(self.owner._qualification_roles,['near','far'])
        for pair in ('near','far'):
            value=self.result(pair);self.assertEqual(value['status'],'CLOCK_PAIR_QUALIFIED')
            self.assertTrue(value['started_at_utc'].endswith('Z') and value['completed_at_utc'].endswith('Z'))
            self.assertTrue(value['cleanup']['leader_reaped'] and value['cleanup']['process_group_gone'])
            self.assertEqual(value['worker_sha256'],self.image.sha256)
            self.assertTrue((clock.compaction.ROOT/f'worker-{pair}.json').is_file())
            with self.assertRaises(ProcessLookupError):os.kill(value['native_pid'],0)
        self.assertGreaterEqual(self.result('far')['started_monotonic_ns'],self.result('near')['completed_monotonic_ns'])
        self.assertFalse(self.owner._entry_used)
        self.assertTrue(self.hardware.restore(self.owner)['compaction_restoration_verified'])

    def test_near_failure_retains_raw_and_prevents_far_native_and_retry(self):
        self.mode('fail-near')
        with self.assertRaisesRegex(clock.ClockError,'helper failed'):self.qualify()
        self.assertFalse((self.root/'far').exists());self.assertTrue((self.root/'near/clock-raw.json').exists())
        self.assertEqual(self.result('near')['status'],'STOPPED');self.assertTrue((self.root/'failure.json').exists())
        self.assertFalse((self.root/'completion.json').exists())
        with self.assertRaisesRegex(clock.environment.EnvironmentError,'restoration only'):self.qualify()
        with self.assertRaises(clock.environment.EnvironmentError):self.owner.native_entry(plan_sha256=self.hardware.sha).__enter__()
        self.assertTrue(self.hardware.restore(self.owner)['compaction_restoration_verified'])

    def test_far_failure_preserves_near_and_leaves_no_workers(self):
        self.mode('fail-far')
        with self.assertRaisesRegex(clock.ClockError,'helper failed'):self.qualify()
        self.assertEqual(self.result('near')['status'],'CLOCK_PAIR_QUALIFIED')
        self.assertEqual(self.result('far')['status'],'STOPPED')
        self.assertTrue(self.result('far')['cleanup']['leader_reaped'])
        self.assertFalse(clock.supervisor.ProcfsIdentityModel().direct_children())

    def test_expired_capture_stops_reaps_and_does_not_continue(self):
        self.mode('timeout')
        # Expire the boundary after actual registration deterministically.
        # A one-second test cap can expire in setup under debug allocation and
        # never exercise the intended live-child termination requirement.
        with mock.patch.object(clock,'_check_capture_deadline',
            side_effect=clock.ClockError('original clock capture deadline expired')):
            with self.assertRaisesRegex(clock.ClockError,'capture deadline expired'):self.qualify()
        self.assertTrue(self.result('near')['cleanup']['leader_reaped'])
        self.assertLess(self.result('near')['cleanup']['returncode'],0)
        self.assertFalse((self.root/'far').exists())

    def test_console_overflow_is_bounded_and_stops_before_far(self):
        self.mode('console')
        with self.assertRaisesRegex(clock.ClockError,'console bound'):self.qualify()
        result=self.result('near')
        self.assertLessEqual(len(bytes.fromhex(result['console_hex'])),clock.CONSOLE_BYTES+1)
        self.assertTrue(result['cleanup']['leader_reaped']);self.assertFalse((self.root/'far').exists())

    def test_malformed_output_is_retained_as_failure_after_cleanup(self):
        self.mode('malformed')
        with self.assertRaises(clock.archive.ArchiveError):self.qualify()
        self.assertEqual((self.root/'near/clock-raw.json').read_bytes(),b'{partial')
        self.assertIsNotNone(self.result('near')['raw']);self.assertFalse((self.root/'far').exists())

    def test_completed_namespace_and_roles_are_never_reused(self):
        self.qualify()
        with self.assertRaises(FileExistsError):self.qualify()
        self.assertEqual(self.owner._qualification_roles,['near','far'])

    def test_altered_source_image_fails_before_any_process(self):
        wrong=clock.runtime.ImageBinding(self.image.path,self.image.size_bytes,'f'*64)
        with self.assertRaisesRegex(clock.ClockError,'exact frozen'):
            clock.qualify_clocks(environment_owner=self.owner,clock_image=wrong,deadline_ns=time.monotonic_ns()+300*10**9)
        self.assertFalse(self.root.exists())

    def test_changed_raw_evidence_latches_the_live_handle(self):
        owned=self.qualify();path=self.root/'near/clock-raw.json';raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(clock.ClockError,'evidence changed'):owned.proof(plan_sha256=self.hardware.sha)
        path.write_bytes(raw)
        with self.assertRaisesRegex(clock.ClockError,'no retry'):owned.proof(plan_sha256=self.hardware.sha)

    def test_proof_dictionaries_cannot_mutate_retained_bindings(self):
        owned=self.qualify();proof=owned.proof(plan_sha256=self.hardware.sha);proof['completion']['sha256']='f'*64
        self.assertNotEqual(owned.proof(plan_sha256=self.hardware.sha)['completion']['sha256'],'f'*64)

    def test_child_raw_permissions_do_not_depend_on_parent_shell_umask(self):
        before=os.umask(0o002)
        try:
            self.qualify()
            for pair in ('near','far'):
                self.assertEqual((self.root/pair/'clock-raw.json').stat().st_mode&0o777,0o600)
        finally:os.umask(before)

    def test_raw_counts_cpu_flags_and_field_types_are_strict(self):
        self.qualify();good=json.loads((self.root/'near/clock-raw.json').read_bytes())
        for key,value in [('consumer_cpu',26),('producer_delta_count',1),('producer_prime_read_count',True),
            ('cross_core_passed',1),('producer_pinned',False),('exchanges_per_window',1)]:
            wrong=copy.deepcopy(good);wrong[key]=value
            with self.assertRaises(clock.ClockError):clock.verify_raw(wrong,'near')
        good['unreviewed_field']=True
        with self.assertRaises(clock.ClockError):clock.verify_raw(good,'near')

    def test_deadline_cannot_extend_accepted_budget_or_window(self):
        for end in (time.monotonic_ns()+60*10**9,time.monotonic_ns()+1801*10**9,self.hardware.window['end_monotonic_ns']+1):
            with self.assertRaisesRegex(clock.ClockError,'qualification budget'):
                clock.qualify_clocks(environment_owner=self.owner,clock_image=self.image,deadline_ns=end)
        self.assertFalse(self.root.exists())

    def test_environment_rejects_skipped_repeated_and_failed_qualification_roles(self):
        with self.assertRaisesRegex(clock.environment.EnvironmentError,'order differs'):
            self.owner.qualification_entry(plan_sha256=self.hardware.sha,role='far').__enter__()
        with self.owner.qualification_entry(plan_sha256=self.hardware.sha,role='near'):pass
        with self.assertRaisesRegex(clock.environment.EnvironmentError,'order differs'):
            self.owner.qualification_entry(plan_sha256=self.hardware.sha,role='near').__enter__()
        with self.assertRaisesRegex(ValueError,'software qualification failure'):
            with self.owner.qualification_entry(plan_sha256=self.hardware.sha,role='far'):
                raise ValueError('software qualification failure')
        with self.assertRaisesRegex(clock.environment.EnvironmentError,'restoration only'):
            self.owner.qualification_entry(plan_sha256=self.hardware.sha,role='q15').__enter__()

    def test_reports_cannot_construct_live_clocks(self):
        with self.assertRaises(clock.ClockError):clock._VerifiedClocks(token=object(),owner=self.owner,image=self.image,
            completion={},bindings=[])

    def test_signal_interrupts_owned_child_and_stops_before_far(self):
        self.mode('signal')
        with self.assertRaisesRegex(clock.ClockError,'interrupted by signal'):self.qualify()
        self.assertTrue(self.result('near')['cleanup']['leader_reaped'])
        self.assertFalse((self.root/'far').exists())

    def test_escaped_owned_descendant_is_reaped_and_rejects_qualification(self):
        self.mode('escape')
        with self.assertRaisesRegex(clock.ClockError,'abnormal cleanup'):self.qualify()
        result=self.result('near')
        self.assertTrue(result['cleanup']['descendants_detected_after_leader_exit'])
        self.assertTrue(result['cleanup']['process_group_gone'])
        self.assertFalse(clock.supervisor.ProcfsIdentityModel().direct_children())
        self.assertFalse((self.root/'far').exists())

    def test_image_change_after_binding_is_rejected_by_sealed_snapshot(self):
        path=self.hardware.root/'changed-image';raw=bytearray(self.endpoint.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        image=clock.runtime.ImageBinding(path,self.image.size_bytes,self.image.sha256)
        with self.assertRaisesRegex(clock.runtime.RuntimeError,'pinned executable hash'):
            clock.qualify_clocks(environment_owner=self.owner,clock_image=image,deadline_ns=time.monotonic_ns()+300*10**9)
        self.assertTrue((self.root/'failure.json').exists());self.assertFalse((self.root/'far').exists())
        self.assertFalse((clock.compaction.ROOT/'worker-near.json').exists())

    def test_failed_attempt_publication_latches_without_spawning(self):
        original=clock.compaction._save
        def save(path,value):
            if Path(path).name=='attempt.json':raise OSError('software durable publication failure')
            return original(path,value)
        with mock.patch.object(clock.compaction,'_save',side_effect=save):
            with self.assertRaisesRegex(OSError,'publication failure'):self.qualify()
        self.assertTrue(self.owner._qualification_failed);self.assertTrue((self.root/'failure.json').exists())
        self.assertFalse((self.root/'near').exists())

    def test_complete_metadata_ceilings_fit_the_existing_external_reserve(self):
        limits=clock.RECORD_LIMITS
        maximum=2*(limits['intent.json']+limits['result.json']+clock.FILE_BYTES)
        maximum+=limits['attempt.json']+limits['completion.json']+limits['failure.json']
        self.assertLessEqual(maximum+clock.METADATA_INODES*4096,clock.METADATA_BYTES)
        self.assertLessEqual(clock.METADATA_BYTES+128*1024,
            clock.compaction.METADATA_RESERVE_BYTES-clock.compaction.OWNER_LIMIT)
        self.assertLessEqual(clock.METADATA_INODES+16,clock.compaction.METADATA_RESERVE_INODES)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--endpoint',type=Path,required=True)
    args,remaining=parser.parse_known_args();ClockTests.endpoint=args.endpoint.resolve(strict=True)
    unittest.main(argv=[sys.argv[0],*remaining])
