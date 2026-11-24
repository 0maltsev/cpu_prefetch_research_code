"""Real SSHSIG/sealed ELF/pipe/cleanup with explicit software platform doubles.

No hardware qualification or pilot credit. A separate C++ peer retains an actual
buffer across the two packets. Only CPU, cgroup, MSR and prerequisite clock
observations are software fixtures; production offers no alternate backend.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_q15_session_v1 as session
import test_stage17_s180_environment_v1 as hardware
import test_stage17_s180_q15_authority_v1 as signatures
import s180_compaction_fixture


def templates():
    common=dict(session_id='software-session',qualification_id='software-qualification')
    pre=[dict(cpu=c,complete_value_hex='0000000000000000') for c in (0,1,8)]
    probe=dict(counter_value=100,minor_faults=0,major_faults=0,cpu_verified=True,residency_verified=True,integrity_verified=True)
    return {
        'q15-r-output-v3.json':dict(schema_version='cpu-prefetch-stage17-q15-r-output/3',**common,
            authorization_sha256='a'*64,attempt_id='software-attempt',cpu_family=6,cpu_model=62,mapping_id=session.MAPPING,
            prestate=pre,buffer_size_bytes=262144,buffer_content_sha256='b'*64,regular_probe=probe,
            pointer_probe=dict(probe,counter_value=0),pointer_atomic_lock_free=True,queue_layout_passed=True,
            termination_atomic_lock_free=True,read_only=True,complete=True),
        'q15-r-atomic-layout-raw-v1.json':dict(schema_version='cpu-prefetch-stage17-q15-r-atomic-layout-raw/1',**common,
            pointer_atomic_width_bytes=8,pointer_atomic_alignment_bytes=8,termination_atomic_width_bytes=4,
            termination_atomic_alignment_bytes=4,cache_line_bytes=64,pointer_atomic_runtime_lock_free=True,
            termination_atomic_runtime_lock_free=True,queue_layout_passed=True,ownership_lines_separated=True,
            termination_dedicated_line=True),
        'q15-r-address-residency-raw-v1.json':dict(schema_version='cpu-prefetch-stage17-q15-r-address-residency-raw/1',**common,
            mechanism_id='LINUX_MOVE_PAGES_PER_PAGE_NUMA_NODE_QUERY',regions=[dict(region=name,expected_node=0,
                before_page_count=64,during_page_count=64,after_page_count=64,unavailable_page_count=0,
                wrong_node_page_count=0,migrated_page_count=0) for name in
                ('regular_stream_probe_buffer','pointer_dependent_probe_buffer')]),
        'q15-r-software-prefetch-raw-v1.json':dict(schema_version='cpu-prefetch-stage17-q15-r-software-prefetch-raw/2',**common,
            mapping_id='X86-64-PREFETCHT0-ONLY-v1',observed_cpu=0,producer_maximum_extended_leaf=0x80000008,
            producer_extended_leaf_ecx=1,producer_prfchw_supported=False,consumer_maximum_extended_leaf=0x80000008,
            consumer_extended_leaf_ecx=1,consumer_prfchw_supported=False),
        'q15-r-cpu-migration-raw-v1.json':dict(schema_version='cpu-prefetch-stage17-q15-r-cpu-migration-raw/1',**common,
            expected_cpu=0,samples=[dict(probe=p,point=t,cpu=0) for p in ('regular_stream','pointer_dependent')
                for t in ('entry','exit')],singleton_affinity=dict(regular_stream=True,pointer_dependent=True)),
        'q15-w-output-v3.json':dict(schema_version='cpu-prefetch-stage17-q15-w-output/3',session_id=common['session_id'],
            authorization_sha256='a'*64,q15_r_attempt_sha256='c'*64,q15_r_result_sha256='d'*64,live_prestate_matches=True,
            apply_readback=[dict(cpu=c,complete_value_hex='000000000000000f') for c in (0,1,8)],
            regular_probe=dict(counter_value=0,accepted=True,integrity_verified=True),
            pointer_probe=dict(counter_value=0,accepted=True,integrity_verified=True),restore_readback=copy.deepcopy(pre),
            restoration_verified=True,quarantine_operation=dict(performed=False,reason='RESTORATION_VERIFIED'),complete=True)}


class SessionTests(unittest.TestCase):
    endpoint=None
    sanitized_endpoint=None

    def setUp(self):
        self.hardware=hardware.EnvironmentTests();self.hardware.setUp();self.addCleanup(self.hardware.doCleanups)
        self.hardware.plan=session.compaction.monitored_plan(self.hardware.plan)
        self.hardware.sha=session.environment.planning.sha(self.hardware.plan)
        self.io=self.hardware.io();self.io.__enter__();self.addCleanup(self.io.close)
        self.owner=self.hardware.guard()
        self.guard,self.control,_=s180_compaction_fixture.attach(self,self.owner,self.hardware.root)
        self.stack=session.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.root=self.hardware.root/'q15-qualification';self.cache=self.hardware.root/'cache';self.cache.mkdir()
        for name,value in dict(level='3',type='Unified',size='128K',coherency_line_size='64').items():
            (self.cache/name).write_text(value+'\n')
        self.stack.enter_context(mock.patch.object(session,'ROOT',self.root))
        self.stack.enter_context(mock.patch.object(session.authority,'ROOT',self.root))
        self.stack.enter_context(mock.patch.object(session,'CACHE',self.cache))
        self.image=session.runtime.ImageBinding(self.endpoint,self.endpoint.stat().st_size,hashlib.sha256(self.endpoint.read_bytes()).hexdigest())
        for module in (session.compaction,session.authority.resources):
            self.stack.enter_context(mock.patch.object(module,'NATIVE_SHA',self.image.sha256))
            self.stack.enter_context(mock.patch.object(module,'NATIVE_SIZE',self.image.size_bytes))
        self.stack.enter_context(mock.patch.object(session.compaction,'_membership',return_value='/'+session.environment.UNIT+'/reserved'))
        self.production_place=session._place
        self.stack.enter_context(mock.patch.object(session,'_place',side_effect=self.place))
        original_cleanup=session.supervisor.cleanup_process_group
        def cleanup(*args,**kwargs):
            value=original_cleanup(*args,**kwargs)
            if value.leader_reaped and value.process_group_gone:(self.hardware.cg/'cgroup.procs').write_text('')
            return value
        self.stack.enter_context(mock.patch.object(session.supervisor,'cleanup_process_group',side_effect=cleanup))
        self.signatures=signatures.AuthorityTests();self.signatures.setUp();self.addCleanup(self.signatures.doCleanups)
        self.signatures.base.resolutions['S17-EXT-002'].semantic_context['stand_id']=self.hardware.plan['blueprint']['stand_id']
        self.base=self.signatures.base;self.signed=[]
        # Explicit prerequisite proof fixture; D335 separately tests actual clock
        # transport. Files and image are still physically bound by its live proof.
        now=time.monotonic_ns();clocks=self.hardware.root/'software-clock';clocks.mkdir(mode=0o700)
        attempt=session._save(clocks/'attempt.json',dict(started_monotonic_ns=now,deadline_monotonic_ns=now+300*10**9))
        complete=session._save(clocks/'completion.json',dict(completed_monotonic_ns=now))
        self.clock=session.clocks._VerifiedClocks(token=session.clocks._TOKEN,owner=self.owner,image=self.image,completion=complete,bindings=[attempt])
        self.owner._qualification_roles=['near','far']
        self.data=templates();self.fixture_root=self.hardware.root/'q15-fixtures';self.fixture_root.mkdir()
        self.publish_templates()

    def publish_templates(self):
        for name,value in self.data.items():(self.fixture_root/name).write_bytes(session.archive.canonical(value))

    def place(self,entry):self.production_place(dict(entry,controller_cpu=min(os.sched_getaffinity(0))))

    def signer(self,path):
        self.signed.append(path.name)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.signatures.key),'-n','cpu-prefetch-stage17',str(path)],
            check=True,capture_output=True,timeout=10)
        return Path(str(path)+'.sig')

    def prepare(self):
        return session.prepare(environment_owner=self.owner,clock_owner=self.clock,base_validation=self.base,operator_profile_sha256='b'*64)

    def execute(self,prepared=None,signer=None):return (prepared or self.prepare()).execute(native_image=self.image,signer=signer or self.signer)
    def mode(self,value):(self.hardware.root/'q15-test-mode').write_text(value)
    def terminal(self):return json.loads((self.root/'terminal.json').read_bytes())

    def stopped(self):
        value=self.terminal();self.assertEqual(value['status'],'STOPPED');self.assertTrue(self.owner._qualification_failed)
        self.assertFalse(value['execution_authority']);self.assertFalse(session.supervisor.ProcfsIdentityModel().direct_children())
        if value['native_pid'] is not None:
            self.assertTrue(value['cleanup']['leader_reaped'] and value['cleanup']['process_group_gone'])
            with self.assertRaises(ProcessLookupError):os.kill(value['native_pid'],0)
        self.assertTrue(self.hardware.restore(self.owner)['compaction_restoration_verified'])

    def test_one_native_buffer_separate_signed_write_and_verified_restoration(self):
        prepared=self.prepare();result=self.execute(prepared);value=result['document']
        self.assertEqual(value['status'],'Q15_RW_VERIFIED');self.assertFalse(value['execution_authority'])
        self.assertEqual(self.signed,['q15-r-authorization.json','q15-w-authorization.json'])
        self.assertEqual(value['original_msr_readbacks'],[dict(cpu=c,complete_value_hex='0000000000000000') for c in (0,1,8)])
        self.assertEqual(int((self.hardware.root/'q15-write-entered').read_text()),value['native_pid'])
        self.assertEqual(len(result['raw_bindings']),9);self.assertFalse(self.owner._entry_used)
        self.assertTrue(value['cleanup']['leader_reaped'] and value['cleanup']['process_group_gone'])
        self.assertEqual(self.owner._qualification_roles,['near','far','q15'])
        completed=prepared.completed();proof=completed.proof(plan_sha256=self.hardware.sha)
        self.assertTrue(proof['q15_verified']);self.assertFalse(proof['execution_authority'])
        self.assertEqual(len(proof['files']),21);self.assertIs(completed.prepared.owner,self.owner)
        for key in ('read_barrier','write_barrier'):
            self.assertEqual(value[key]['pid'],value['native_pid'])
            self.assertEqual(value[key]['quiescence']['task_ids'],[value['native_pid']])
            self.assertEqual(value[key]['msr_readbacks'],value['original_msr_readbacks'])
        self.assertEqual(value['read_barrier']['pipe_inode'],value['write_barrier']['pipe_inode'])
        self.assertTrue(self.hardware.restore(self.owner)['compaction_restoration_verified'])

    def test_existing_incomplete_ready_file_waits_for_actual_pipe_barrier(self):
        self.mode('delayed-ready');original=session._waiting;observed=[]
        def waiting(worker,control_fd):
            value=original(worker,control_fd)
            cue=self.hardware.root/'q15-close-publication'
            if (self.hardware.root/'q15-ready-incomplete').exists() and not cue.exists():
                self.assertFalse(value);self.assertEqual(self.signed,['q15-r-authorization.json'])
                self.assertEqual((self.root/'stage17-q15-session-waiting-v1.json').stat().st_size,0)
                observed.append(True);cue.write_text('allow durable publication')
            return value
        with mock.patch.object(session,'_waiting',side_effect=waiting):result=self.execute()
        self.assertEqual(observed,[True]);self.assertEqual(result['document']['status'],'Q15_RW_VERIFIED')

    def test_unavailable_procfs_barrier_stops_and_reaps_without_fallback(self):
        original=session.compaction._read
        def read(path,maximum):
            if Path(path).name=='syscall':raise PermissionError('software ptrace access denied')
            return original(path,maximum)
        with mock.patch.object(session.compaction,'_read',side_effect=read):
            with self.assertRaisesRegex(PermissionError,'ptrace access denied'):self.execute()
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_denied_read_signature_never_spawns_or_signs_write(self):
        def denied(path):raise ValueError('software read signing denied')
        with self.assertRaisesRegex(ValueError,'signing denied'):self.execute(signer=denied)
        self.assertIsNone(self.terminal()['native_pid']);self.stopped()

    def test_denied_write_signature_reaps_waiting_read_worker(self):
        def denied(path):
            if path.name.startswith('q15-w'):raise ValueError('software write signing denied')
            return self.signer(path)
        with self.assertRaisesRegex(ValueError,'write signing denied'):self.execute(signer=denied)
        self.assertTrue((self.root/'stage17-q15-r-result-v4.json').is_file());self.stopped()

    def test_preexisting_signature_path_is_never_adopted(self):
        prepared=self.prepare();(self.root/'q15-r-authorization.json.sig').write_bytes(b'foreign')
        with self.assertRaisesRegex(session.SessionError,'signature path already occupied'):self.execute(prepared)
        self.assertEqual(self.signed,[]);self.stopped()

    def test_migrated_cpu_rejects_before_write_signature(self):
        self.data['q15-r-cpu-migration-raw-v1.json']['samples'][-1]['cpu']=26;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'CPU/migration'):self.execute()
        self.assertEqual(self.signed,['q15-r-authorization.json']);self.stopped()

    def test_nonlockfree_atomic_rejects_before_write_signature(self):
        self.data['q15-r-atomic-layout-raw-v1.json']['pointer_atomic_runtime_lock_free']=False;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'atomic/layout'):self.execute()
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_wrong_page_rejects_before_write_signature(self):
        self.data['q15-r-address-residency-raw-v1.json']['regions'][0]['wrong_node_page_count']=1;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'residency'):self.execute()
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_wrong_prefetch_capability_rejects_before_write_signature(self):
        self.data['q15-r-software-prefetch-raw-v1.json']['producer_extended_leaf_ecx']=0x100;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'PRFCHW'):self.execute()
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_uninformative_h0_regular_counter_never_authorizes_write(self):
        self.data['q15-r-output-v3.json']['regular_probe']['counter_value']=0;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'distinguish'):self.execute()
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_wrong_full_restore_readback_fails_despite_zero_exit(self):
        self.data['q15-w-output-v3.json']['restore_readback'][2]['complete_value_hex']='0000000000000010';self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'apply/restore'):self.execute()
        self.assertEqual(self.terminal()['cleanup']['returncode'],0);self.stopped()

    def test_existing_native_counter_tolerance_is_retained(self):
        self.data['q15-w-output-v3.json']['regular_probe']['counter_value']=2000;self.publish_templates()
        self.assertEqual(self.execute()['document']['status'],'Q15_RW_VERIFIED')

    def test_exceeded_native_counter_tolerance_stops(self):
        self.data['q15-w-output-v3.json']['regular_probe']['counter_value']=2001;self.publish_templates()
        with self.assertRaisesRegex(session.SessionError,'counter tolerance'):self.execute()
        self.stopped()

    def test_live_write_timeout_reaps_without_retry(self):
        self.mode('timeout');original=session._before
        def before(deadline):
            if (self.hardware.root/'q15-write-entered').exists():raise session.SessionError('software original Q15 timeout')
            original(deadline)
        with mock.patch.object(session,'_before',side_effect=before):
            with self.assertRaisesRegex(session.SessionError,'original Q15 timeout'):self.execute()
        self.stopped()

    def test_escaped_child_is_reaped_and_rejects_success(self):
        self.mode('escape')
        with self.assertRaisesRegex(session.SessionError,'abnormal cleanup'):self.execute()
        self.assertTrue(self.terminal()['cleanup']['descendants_detected_after_leader_exit']);self.stopped()

    def test_console_overflow_stops_before_write(self):
        self.mode('console')
        with self.assertRaisesRegex(session.SessionError,'console bound'):self.execute()
        self.assertLessEqual(len(bytes.fromhex(self.terminal()['console_hex'])),16385)
        self.assertEqual(len(self.signed),1);self.stopped()

    def test_nonzero_write_exit_retains_read_evidence(self):
        self.mode('exit-write')
        with self.assertRaisesRegex(session.SessionError,'abnormal cleanup'):self.execute()
        self.assertTrue((self.root/'stage17-q15-r-result-v4.json').is_file());self.stopped()

    def test_repeat_attempt_and_namespace_never_adopt_completed_work(self):
        prepared=self.prepare();self.execute(prepared)
        with self.assertRaisesRegex(session.SessionError,'already consumed'):self.execute(prepared)
        with self.assertRaises(session.SessionError):self.prepare()

    def test_changed_preparation_blocks_dispatch(self):
        prepared=self.prepare();path=self.root/'preparation.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(session.SessionError,'preparation changed'):self.execute(prepared)
        self.assertFalse((session.compaction.ROOT/'worker-q15.json').exists())
        path.write_bytes(path.read_bytes().rstrip())
        with self.assertRaisesRegex(session.SessionError,'preparation failed'):self.execute(prepared)

    def test_invalid_actual_cache_latches_preparation_without_creating_root(self):
        (self.cache/'size').write_text('unknown\n')
        with self.assertRaisesRegex(session.SessionError,'LLC geometry'):self.prepare()
        self.assertFalse(self.root.exists());self.assertTrue(self.owner._qualification_failed)

    def test_changed_image_rejects_before_signature(self):
        prepared=self.prepare();wrong=session.runtime.ImageBinding(self.endpoint,self.image.size_bytes,'f'*64)
        with self.assertRaisesRegex(session.SessionError,'exact frozen'):prepared.execute(native_image=wrong,signer=self.signer)
        self.assertEqual(self.signed,[])

    def test_signing_deadline_interrupts_callback_and_restores_timer_handler(self):
        original=signal.setitimer;old=signal.getsignal(signal.SIGALRM)
        def timer(kind,seconds,*args):return original(kind,min(seconds,.05),*args)
        def blocked(path):time.sleep(60)
        with mock.patch.object(session.signal,'setitimer',side_effect=timer):
            with self.assertRaisesRegex(session.SessionError,'signing exceeded'):self.execute(signer=blocked)
        self.assertEqual(signal.getsignal(signal.SIGALRM),old);self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
        self.stopped()

    def test_complete_file_ceiling_fits_explicit_external_reservation(self):
        self.assertLessEqual(32*(65536+4096),session.METADATA_BYTES)
        self.assertLessEqual(session.TOTAL_FILES+1,session.METADATA_INODES)

    def test_sanitized_cpp_peer_uses_same_real_signature_and_pipe_protocol(self):
        if self.sanitized_endpoint is None:self.skipTest('separate sanitizer endpoint not requested')
        image=session.runtime.ImageBinding(self.sanitized_endpoint,self.sanitized_endpoint.stat().st_size,
            hashlib.sha256(self.sanitized_endpoint.read_bytes()).hexdigest())
        for module in (session.compaction,session.authority.resources):
            self.stack.enter_context(mock.patch.object(module,'NATIVE_SHA',image.sha256))
            self.stack.enter_context(mock.patch.object(module,'NATIVE_SIZE',image.size_bytes))
        original_set=resource.setrlimit;original_get=resource.getrlimit;original_popen=subprocess.Popen
        # ASan needs a huge shadow virtual address range; this software-only test
        # bypasses just AS and supplies sanitizer runtime variables. Production
        # child limits and stripped environment are unchanged and tested above.
        def limit(kind,value):
            if kind!=resource.RLIMIT_AS:original_set(kind,value)
        def readback(kind):
            return (session.clocks.AS_BYTES,)*2 if kind==resource.RLIMIT_AS else original_get(kind)
        def popen(*args,**kwargs):
            if '--execute-stage17-q15-session-v1' in args[0]:
                kwargs['env']=dict(kwargs['env'],LD_LIBRARY_PATH=os.environ.get('LD_LIBRARY_PATH',''),
                    ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            return original_popen(*args,**kwargs)
        prepared=self.prepare()
        with mock.patch.object(session.resource,'setrlimit',side_effect=limit), \
            mock.patch.object(session.resource,'getrlimit',side_effect=readback), \
            mock.patch.object(session.subprocess,'Popen',side_effect=popen):
            result=prepared.execute(native_image=image,signer=self.signer)
        self.assertEqual(result['document']['status'],'Q15_RW_VERIFIED')
        console=bytes.fromhex(result['document']['console_hex'])
        self.assertNotIn(b'AddressSanitizer',console);self.assertNotIn(b'runtime error:',console)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--endpoint',type=Path,required=True)
    parser.add_argument('--sanitized-endpoint',type=Path)
    args,remaining=parser.parse_known_args();SessionTests.endpoint=args.endpoint.resolve(strict=True)
    if args.sanitized_endpoint:SessionTests.sanitized_endpoint=args.sanitized_endpoint.resolve(strict=True)
    unittest.main(argv=[sys.argv[0],*remaining])
