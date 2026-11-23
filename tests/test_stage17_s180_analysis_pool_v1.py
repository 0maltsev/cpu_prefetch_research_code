"""Actual isolated worker/decoder/process cleanup; synthetic scientific inputs."""
from contextlib import ExitStack
from dataclasses import replace
import copy
import errno
import json
import os
from pathlib import Path
import signal
import struct
import sys
import unittest
from unittest import mock
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_analysis_pool_v1 as pool
import test_stage17_s180_analysis_phase_v1 as phases
import test_stage17_s180_archive_analysis_v1 as archives
import test_stage17_s180_family_validation_v1 as family_fixtures


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.p=phases.PhaseTests();self.p.setUp();self.addCleanup(self.p.doCleanups)
        self.h,self.source,self.environment,_=self.p.owned()
        self.a=archives.ArchivedTests();self.a.setUp();self.addCleanup(self.a.doCleanups)
        self.root=self.a.root/'pool';self.root.mkdir(mode=0o700)
        for name in ('captures','workers','scratch'):(self.root/name).mkdir(mode=0o700)
        self.job=copy.deepcopy(self.a.args);self.job['output_directory']=self.root/'captures'/'capture-0';self.job['scratch_root']=self.root/'scratch'

    def run_core(self):
        with self.p.enter(self.source,self.environment,self.h.sha) as owner:
            self.owner=owner
            return pool._run_pool(owner,[self.job],self.a.profile,self.a.limits,self.root)

    def failures_cleaned(self):
        report=json.loads((self.root/'pool-processes.json').read_bytes())
        self.assertEqual(report['status'],'FAILED');self.assertFalse(report['actual_worker_completion_verified'])
        self.assertTrue(all(r['cleanup']['leader_reaped'] for r in report['cleanup']))
        self.assertTrue(self.owner.failed)
        return report

    def test_real_twelve_worker_sessions_decode_validate_and_reap_before_success(self):
        records,report=self.run_core()
        self.assertEqual(set(records),{0});self.assertEqual(report['workers_started'],12)
        self.assertTrue(report['actual_worker_completion_verified']);self.assertFalse(report['full_family_validity_established'])
        self.assertEqual(len(report['cleanup']),12)
        self.assertTrue(all(r['cleanup']['leader_reaped'] and r['cleanup']['process_group_gone']
            and r['cleanup']['returncode']==0 for r in report['cleanup']))
        self.assertTrue(all(r['startup']['parent_death_signal']==signal.SIGKILL for r in report['cleanup']))
        self.assertTrue((self.job['output_directory']/'complete.json').exists())
        self.assertTrue(all(p.name.endswith('.lock') for p in (self.root/'scratch').iterdir()))

    def test_first_corrupt_original_stops_every_worker_and_retains_failed_spool(self):
        row=self.job['registry_proof']['artifacts'][-1];path=self.a.archives/row['archive_name']
        data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        with self.assertRaisesRegex(pool.phase.resources.ResourceError,'required capture failed'):self.run_core()
        self.failures_cleaned();self.assertEqual(path.read_bytes(),data)
        self.assertTrue(any(p.is_dir() for p in (self.root/'scratch').iterdir()))

    def test_success_messages_never_override_actual_nonzero_worker_exit(self):
        real_exit=os._exit
        def exited(code):real_exit(23 if code==0 else code)
        with mock.patch.object(pool.os,'_exit',side_effect=exited):
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'nonzero exit'):self.run_core()
        report=self.failures_cleaned();self.assertTrue(any(r['cleanup']['returncode']==23 for r in report['cleanup']))

    def test_failed_pre_release_readiness_reaps_only_its_owned_child(self):
        real=pool.resource.setrlimit
        def limit(kind,value):
            if kind==pool.resource.RLIMIT_NOFILE:raise RuntimeError('injected pre-release failure')
            return real(kind,value)
        with mock.patch.object(pool.resource,'setrlimit',side_effect=limit):
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'before readiness'):self.run_core()
        report=self.failures_cleaned();self.assertEqual(report['workers_started'],1)
        self.assertTrue(report['cleanup'][0]['cleanup']['pre_release_stop'])

    def test_escaped_descendant_is_reaped_and_invalidates_worker_success(self):
        real=pool.worker.analyze_capture
        def analyze(**kwargs):
            result=real(**kwargs)
            pid=os.fork()
            if pid==0:
                os.setsid();signal.signal(signal.SIGTERM,signal.SIG_IGN)
                while True:signal.pause()
            return result
        with mock.patch.object(pool.worker,'analyze_capture',side_effect=analyze):
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'abnormal analysis worker cleanup'):self.run_core()
        report=self.failures_cleaned()
        self.assertTrue(any(r['cleanup'].get('descendants_detected_after_leader_exit') for r in report['cleanup']))

    def test_parent_signal_stops_children_and_cannot_promote_completed_output(self):
        real=pool.worker.analyze_capture
        def analyze(**kwargs):
            result=real(**kwargs);os.kill(os.getppid(),signal.SIGTERM);return result
        with mock.patch.object(pool.worker,'analyze_capture',side_effect=analyze):
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'signal'):self.run_core()
        self.failures_cleaned()

    def test_partial_pipe_creation_failure_leaks_no_parent_descriptor(self):
        before=set(os.listdir('/proc/self/fd'));real=pool.os.pipe2;calls=0
        def pipe(flags):
            nonlocal calls
            calls+=1
            if calls==3:raise OSError(errno.EMFILE,'injected partial pipe failure')
            return real(flags)
        with mock.patch.object(pool.os,'pipe2',side_effect=pipe):
            with self.assertRaisesRegex(OSError,'partial pipe failure'):self.run_core()
        report=self.failures_cleaned();self.assertEqual(report['workers_started'],0)
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_pidfd_failure_before_release_still_reaps_its_actual_child(self):
        with mock.patch.object(pool.os,'pidfd_open',side_effect=OSError(errno.ENOMEM,'injected pidfd failure')):
            with self.assertRaisesRegex(OSError,'pidfd failure'):self.run_core()
        report=self.failures_cleaned();self.assertTrue(report['cleanup'][0]['cleanup']['pre_release_stop'])

    def test_public_missing_originals_consumes_phase_without_creating_output(self):
        output=self.a.root/'public-analysis'
        profile=replace(self.a.profile,decoder=replace(self.a.profile.decoder,
            implementation_profile_sha256=self.h.plan['storage']['implementation_profile_sha256']))
        with self.p.enter(self.source,self.environment,self.h.sha) as owner:
            args=dict(phase_owner=owner,inputs=[],native_result={},session_id='SOFTWARE',program_root=self.a.program,
                archive_profile=profile,decode_limits=self.a.limits,output_directory=output,
                other_workspace_committed_bytes=0,other_scratch_committed_bytes=0)
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'all180'):pool.run_analysis(**args)
            self.assertTrue(owner.failed);self.assertFalse(output.exists())
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'failed'):pool.run_analysis(**args)

    def test_console_overrun_retains_bounded_prefix_and_stops_the_pool(self):
        real=pool.worker.analyze_capture
        def analyze(**kwargs):
            os.write(1,b'x'*(pool.CONSOLE_MAX+1));return real(**kwargs)
        with mock.patch.object(pool.worker,'analyze_capture',side_effect=analyze):
            with self.assertRaisesRegex(pool.phase.resources.ResourceError,'prefix retained'):self.run_core()
        self.failures_cleaned()
        consoles=[p.read_bytes() for p in (self.root/'workers').iterdir()]
        self.assertIn(b'x'*pool.CONSOLE_MAX,consoles)


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original=family_fixtures.plan_fixture
        def fixture(revision):
            plan=original(revision)
            for row in plan['captures']:row['execution_budget']['max_output_bytes']=64*1024**2
            return plan
        # The earlier metadata-only family fixture did not reserve actual
        # decoded bytes. Give this software fixture an explicit sufficient
        # budget before its plan/checkpoint hashes are constructed.
        with mock.patch.object(family_fixtures,'plan_fixture',side_effect=fixture):
            cls.f=family_fixtures.family_fixture(family_fixtures.template())

    def jobs(self,inputs=None):
        f=self.f;plan=f['plan'];bounds=pool.phase.bounds.analysis_output_envelope(plan)
        if inputs is None:inputs=[dict(checkpoint=r['checkpoint'],registry_proof=r['registry_proof']) for r in f['records']]
        return pool._jobs(plan,f['native_result'],inputs,program=Path('/SOFTWARE/program'),scratch=Path('/SOFTWARE/analysis/scratch'),
            captures=Path('/SOFTWARE/analysis/captures'),session_id=f['session_id'],output_bounds=bounds['capture_bounds'])

    def test_all180_metadata_inputs_keep_original_rows_seed_and_one_context_per_worker(self):
        jobs=self.jobs();self.assertEqual(len(jobs),180)
        self.assertEqual([j['capture_row']['execution_ordinal'] for j in jobs],list(range(180)))
        self.assertTrue(all(j['master_seed_hex']==self.f['plan']['blueprint']['master_seed_hex'] for j in jobs))
        slots=pool._partitions(jobs);self.assertEqual([len(s) for s in slots],[15]*12)
        self.assertEqual({j['capture_row']['execution_ordinal'] for s in slots for j in s},set(range(180)))
        self.assertTrue(all(len({(j['capture_row']['placement'],j['capture_row']['working_set_class']) for j in s})==1 for s in slots))

    def test_versioned_output_budget_explicitly_includes_family_metadata(self):
        envelope=pool.phase.bounds.analysis_output_envelope(self.f['plan'])
        self.assertEqual(envelope['schema_version'],'cpu-prefetch-stage17-s180-analysis-output-envelope/2')
        self.assertEqual(envelope['family_metadata_reserve_bytes'],4*1024**2)
        self.assertEqual(envelope['workspace_bytes_upper'],4*1024**2+sum(r['maximum_output_bytes'] for r in envelope['capture_bounds']))
        self.assertEqual(pool.phase.resources.SCHEMA,'cpu-prefetch-stage17-s180-live-resource-evidence/4')

    def test_missing_and_reordered_originals_do_not_form_a_family(self):
        inputs=[dict(checkpoint=r['checkpoint'],registry_proof=r['registry_proof']) for r in self.f['records']]
        with self.assertRaisesRegex(pool.phase.resources.ResourceError,'all180'):self.jobs(inputs[:-1])
        with self.assertRaisesRegex(pool.phase.resources.ResourceError,'lineage'):self.jobs([inputs[1],inputs[0],*inputs[2:]])


class FrameTests(unittest.TestCase):
    def test_partial_frames_and_bad_sizes_are_bounded_without_pickle(self):
        raw=pool.archive.canonical(dict(kind='DONE',execution_ordinals=[0]))
        buffer=bytearray(struct.pack('<I',len(raw))+raw[:3]);self.assertEqual(list(pool._frames(buffer)),[])
        buffer.extend(raw[3:]);self.assertEqual(list(pool._frames(buffer)),[dict(kind='DONE',execution_ordinals=[0])])
        self.assertEqual(buffer,bytearray())
        with self.assertRaises(pool.phase.resources.ResourceError):list(pool._frames(bytearray(struct.pack('<I',pool.FRAME_MAX+1))))

    def test_cleanup_view_excludes_only_same_birth_known_siblings(self):
        leader=SimpleNamespace(start_time_ticks=10,local_pgid=1)
        sibling=SimpleNamespace(start_time_ticks=20,local_pgid=2)
        unknown=SimpleNamespace(start_time_ticks=30,local_pgid=3)
        rows={1:leader,2:sibling,3:unknown}
        model=SimpleNamespace(snapshot=None,direct_children=lambda:dict(rows))
        view=pool._PoolCleanupView(model,1,[dict(pid=2,ready_packet=dict(start_ticks='20'))])
        self.assertEqual(set(view.direct_children()),{1,3})
        rows[2]=SimpleNamespace(start_time_ticks=99,local_pgid=2)
        self.assertEqual(set(view.direct_children()),{1,2,3})


if __name__=='__main__':unittest.main()
