"""Real Q15 peer, SSHSIG, accepted C++ builder and supervised sealed transport.

Platform/prerequisite clocks are explicit software fixtures. Without the optional
actual support package, codegen/package readiness is also a named boundary
double; no public production backend or fixture selector exists. Nothing here
qualifies stand hardware or produces performance evidence.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_qualification_evidence_v1 as evidence
import test_stage17_s180_q15_session_v1 as sessions


class EvidenceTests(unittest.TestCase):
    endpoint=None;helper=None;support=None;sanitized_helper=None

    def setUp(self):
        self.f=sessions.SessionTests();self.f.endpoint=self.endpoint;self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.hardware.root/'qualification-evidence';self.helper_image=evidence.runtime.ImageBinding(
            self.helper,self.helper.stat().st_size,hashlib.sha256(self.helper.read_bytes()).hexdigest())
        self.stack=evidence.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(evidence,'ROOT',self.root))
        self.stack.enter_context(mock.patch.object(evidence,'HELPER_SHA',self.helper_image.sha256))
        self.stack.enter_context(mock.patch.object(evidence,'HELPER_SIZE',self.helper_image.size_bytes))
        self.stack.enter_context(mock.patch.object(evidence.q15.compaction,'CLOCK_SHA',self.f.image.sha256))
        self.stack.enter_context(mock.patch.object(evidence.q15.compaction,'CLOCK_SIZE',self.f.image.size_bytes))
        # The existing Q15 transport suite intentionally uses a minimal private
        # prerequisite-clock fixture. Here expand it to protected raw/result
        # files. Actual ordered clock process transport is tested in D335.
        clock=self.f.clock;original=evidence.archive.parse_json(clock._bindings)['bindings'][0]
        parent=Path(original['path']).parent
        self.stack.enter_context(mock.patch.object(evidence.q15.clocks,'ROOT',parent))
        start=evidence.archive.parse_json(evidence.q15.compaction._root_file(Path(original['path']),65536))
        rows=[]
        for pair in ('near','far'):
            folder=parent/pair;folder.mkdir(mode=0o700)
            raw=dict(schema_version=evidence.q15.clocks.RAW_SCHEMA,pair=pair,producer_cpu=0,consumer_cpu=1 if pair=='near' else 8,
                producer_pinned=True,consumer_pinned=True,producer_prime_read_count=100000,consumer_prime_read_count=100000,
                producer_delta_count=10000000,consumer_delta_count=10000000,producer_to_consumer_window_count=3,
                consumer_to_producer_window_count=3,exchanges_per_window=100000,producer_per_core_passed=True,
                consumer_per_core_passed=True,cross_core_passed=True)
            raw_binding=evidence.q15._save(folder/'clock-raw.json',raw)
            result=evidence.q15._save(folder/'result.json',dict(status='CLOCK_PAIR_QUALIFIED',pair=pair,
                plan_sha256=self.f.hardware.sha,window_binding=self.f.hardware.window,worker_sha256=self.f.image.sha256,
                started_monotonic_ns=start['started_monotonic_ns'],completed_monotonic_ns=start['started_monotonic_ns'],
                completed_at_utc='2026-11-23T00:00:00Z',raw=raw_binding))
            rows.extend((result,raw_binding))
        Path(evidence.archive.parse_json(clock._completion)['path']).unlink()  # software fixture, not real evidence
        completion=evidence.q15._save(parent/'completion.json',dict(plan_sha256=self.f.hardware.sha,
            window_binding=self.f.hardware.window,completed_monotonic_ns=start['started_monotonic_ns'],
            pair_results=rows,clock_pairs_qualified=True))
        clock._completion=evidence.archive.canonical(completion)
        clock._bindings=evidence.archive.canonical(dict(bindings=[original,*rows]))
        if self.support is None:
            # Explicit external package boundary double. Production requires the
            # pinned actual D338 records and probe bytes and has no such switch.
            self.stack.enter_context(mock.patch.object(evidence,'_codegen',return_value=([],dict(
                gcc_codegen_passed=True,clang_codegen_passed=True,gnu_objdump_passed=True,llvm_objdump_passed=True))))

    def completed(self):
        prepared=self.f.prepare();self.f.execute(prepared);return prepared.completed()

    def publish(self,owner):
        return evidence.publish(completed_q15=owner,helper=self.helper_image,support_root=self.support or '/software-package-double')

    def test_actual_ten_typed_envelopes_keep_source_producer_identities_and_limits(self):
        owner=self.completed();export=self.publish(owner);proof=export.proof(plan_sha256=self.f.hardware.sha)
        self.assertTrue(proof['dynamic_qualification_verified']);self.assertFalse(proof['full_ext008_admission'])
        self.assertFalse(proof['execution_authority']);index=json.loads((self.root/'index.json').read_bytes())
        self.assertEqual(index['qualification_profile_sha256'],'b'*64)
        self.assertEqual(index['measurement_runtime_binding']['sha256'],self.f.image.sha256)
        self.assertEqual(index['base_resolutions'],proof['base_resolutions']);self.assertEqual(len(proof['base_resolutions']),7)
        self.assertEqual(len(index['envelopes']),10);self.assertEqual(len(list(self.root.iterdir())),11)
        pids=[]
        for row in index['envelopes']:
            document=json.loads(evidence._bound(row['envelope']))
            self.assertTrue(document['eligible']);self.assertEqual(document['kind'],row['kind'])
            self.assertEqual(document['sources'][0]['sha256'],row['source']['sha256'])
            self.assertEqual(document['consumer_cpu'],1 if row['pair']=='near' else 8)
            self.assertEqual(document['binary_sha256'],self.f.image.sha256)
            if row['kind']=='SOFTWARE_PREFETCH_MAPPING':
                self.assertEqual(document['details']['ring_producer_instruction'],'PREFETCHT0')
            self.assertTrue(row['transport']['cleanup']['leader_reaped'] and row['transport']['cleanup']['process_group_gone'])
            pids.append(row['transport']['child_pid'])
        self.assertEqual(len(set(pids)),10)
        self.assertFalse(evidence.supervisor.ProcfsIdentityModel().direct_children())
        for pid in pids:
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
        self.assertEqual(len(owner.proof(plan_sha256=self.f.hardware.sha)['files'])+len(list(self.root.iterdir()))+2,34)
        self.assertTrue(self.f.hardware.restore(self.f.owner)['compaction_restoration_verified'])

    def test_completed_evidence_survives_action_expiry_without_run_authority(self):
        owner=self.completed();export=self.publish(owner);before=owner.proof(plan_sha256=self.f.hardware.sha)
        future=before['qualification_deadline_monotonic_ns']+1
        with mock.patch.object(time,'monotonic_ns',return_value=future):
            proof=export.proof(plan_sha256=self.f.hardware.sha)
            self.assertTrue(proof['dynamic_qualification_verified']);self.assertFalse(proof['original_action_deadline_extended'])
        self.assertFalse(hasattr(owner,'execute'));self.assertFalse(hasattr(export,'execute'))

    def test_changed_original_signature_latches_completed_owner_even_if_restored(self):
        owner=self.completed();path=self.f.root/'q15-r-authorization.json.sig';raw=path.read_bytes();path.write_bytes(raw+b'x')
        with self.assertRaisesRegex(evidence.q15.SessionError,'original evidence changed'):owner.proof(plan_sha256=self.f.hardware.sha)
        path.write_bytes(raw)
        with self.assertRaisesRegex(evidence.q15.SessionError,'no retry'):owner.proof(plan_sha256=self.f.hardware.sha)
        self.assertFalse(self.root.exists())

    def test_report_or_unexecuted_preparation_cannot_construct_completion_or_export(self):
        prepared=self.f.prepare()
        with self.assertRaisesRegex(evidence.q15.SessionError,'successful owned'):prepared.completed()
        with self.assertRaisesRegex(evidence.EvidenceError,'actual completed'):self.publish({})
        with self.assertRaisesRegex(evidence.q15.SessionError,'actual successful'):
            evidence.q15._CompletedQ15(token=object(),prepared=prepared,image=self.f.image,bindings=[])

    def test_changed_export_latches_without_republishing(self):
        owner=self.completed();export=self.publish(owner);path=self.root/'far-SELECTED_PAIR_CLOCK.json';raw=path.read_bytes()
        path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(evidence.EvidenceError,'original producer evidence changed'):export.proof(plan_sha256=self.f.hardware.sha)
        path.write_bytes(raw)
        with self.assertRaisesRegex(evidence.EvidenceError,'no retry'):export.proof(plan_sha256=self.f.hardware.sha)

    def test_changed_export_directory_and_unexpected_file_reject(self):
        owner=self.completed();export=self.publish(owner);(self.root/'unexpected.json').write_text('{}')
        with self.assertRaisesRegex(evidence.EvidenceError,'inventory changed'):export.proof(plan_sha256=self.f.hardware.sha)

    def test_existing_export_directory_is_never_adopted_or_modified(self):
        owner=self.completed();self.root.mkdir(mode=0o700);marker=self.root/'historical';marker.write_bytes(b'retain')
        with self.assertRaises(FileExistsError):self.publish(owner)
        self.assertEqual(list(self.root.iterdir()),[marker]);self.assertEqual(marker.read_bytes(),b'retain')
        self.assertTrue(self.f.owner._qualification_failed)

    def test_late_export_cannot_reset_original_qualification_deadline(self):
        owner=self.completed();proof=owner.proof(plan_sha256=self.f.hardware.sha)
        with mock.patch.object(time,'monotonic_ns',return_value=proof['qualification_deadline_monotonic_ns']+1):
            with self.assertRaisesRegex(evidence.EvidenceError,'deadline expired'):self.publish(owner)
        self.assertFalse(self.root.exists())

    def test_helper_failure_retains_partial_output_stops_and_proves_cleanup(self):
        owner=self.completed();original=evidence._author
        def corrupt(executable,raw,output,arguments,deadline,state):
            return original(executable,b'{partial',output,arguments,deadline,state)
        with mock.patch.object(evidence,'_author',side_effect=corrupt):
            with self.assertRaisesRegex(evidence.EvidenceError,'author failure'):self.publish(owner)
        index=json.loads((self.root/'index.json').read_bytes());self.assertEqual(index['status'],'STOPPED')
        self.assertIn(b'not valid JSON',bytes.fromhex(index['last_transport']['console_hex']))
        self.assertTrue(index['last_transport']['cleanup']['leader_reaped'])
        self.assertEqual(len(list(self.root.iterdir())),2);self.assertFalse(evidence.supervisor.ProcfsIdentityModel().direct_children())
        with self.assertRaises(evidence.q15.SessionError):self.publish(owner)

    def test_changed_clock_raw_is_rejected_before_any_export(self):
        owner=self.completed();path=evidence.q15.clocks.ROOT/'far/clock-raw.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(evidence.q15.clocks.ClockError):self.publish(owner)
        self.assertFalse(self.root.exists())

    def test_author_deadline_failure_retains_pid_and_quiescence(self):
        owner=self.completed();original=evidence._before
        def before(deadline):
            # The author stage sets a fresh10s action bound after the original
            # deadline check. Fail it only after Popen registers a real child.
            children=evidence.supervisor.ProcfsIdentityModel().direct_children()
            if children:raise evidence.EvidenceError('software author action deadline')
            return original(deadline)
        with mock.patch.object(evidence,'_before',side_effect=before):
            with self.assertRaisesRegex(evidence.EvidenceError,'author action deadline'):self.publish(owner)
        index=json.loads((self.root/'index.json').read_bytes())
        self.assertEqual(index['status'],'STOPPED');self.assertTrue(index['last_transport']['cleanup']['leader_reaped'])
        self.assertFalse(evidence.supervisor.ProcfsIdentityModel().direct_children())

    def test_wrong_builder_binding_is_rejected_without_namespace(self):
        owner=self.completed();bad=evidence.runtime.ImageBinding(self.helper,self.helper_image.size_bytes,'f'*64)
        with self.assertRaisesRegex(evidence.EvidenceError,'exact clean'):
            evidence.publish(completed_q15=owner,helper=bad,support_root=self.support or '/software-package-double')
        self.assertFalse(self.root.exists())

    def test_background_thread_blocks_author_before_export_namespace(self):
        owner=self.completed();release=threading.Event();thread=threading.Thread(target=release.wait)
        thread.start()
        try:
            with self.assertRaisesRegex(evidence.EvidenceError,'single-threaded'):self.publish(owner)
        finally:release.set();thread.join(2)
        self.assertFalse(thread.is_alive());self.assertFalse(self.root.exists())

    def test_sanitized_builder_exports_all_ten_kinds_over_sealed_fds(self):
        if self.sanitized_helper is None:self.skipTest('separate sanitizer helper not requested')
        owner=self.completed();path=self.sanitized_helper
        self.helper_image=evidence.runtime.ImageBinding(path,path.stat().st_size,hashlib.sha256(path.read_bytes()).hexdigest())
        original_set=resource.setrlimit;original_get=resource.getrlimit;original_popen=subprocess.Popen
        def limit(kind,value):
            if kind!=resource.RLIMIT_AS:original_set(kind,value)
        def readback(kind):
            return (evidence.q15.clocks.AS_BYTES,)*2 if kind==resource.RLIMIT_AS else original_get(kind)
        def popen(*args,**kwargs):
            if '--raw' in args[0]:
                kwargs['env']=dict(kwargs['env'],LD_LIBRARY_PATH=os.environ.get('LD_LIBRARY_PATH',''),
                    ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            return original_popen(*args,**kwargs)
        # Test-only ASan shadow-address/environment boundary; normal cases above
        # use the actual production child cap and stripped environment.
        with mock.patch.object(evidence,'HELPER_SHA',self.helper_image.sha256), \
            mock.patch.object(evidence,'HELPER_SIZE',self.helper_image.size_bytes), \
            mock.patch.object(evidence.resource,'setrlimit',side_effect=limit), \
            mock.patch.object(evidence.resource,'getrlimit',side_effect=readback), \
            mock.patch.object(evidence.subprocess,'Popen',side_effect=popen):
            result=self.publish(owner);proof=result.proof(plan_sha256=self.f.hardware.sha)
        self.assertTrue(proof['dynamic_qualification_verified'])
        index=json.loads((self.root/'index.json').read_bytes())
        for row in index['envelopes']:
            console=bytes.fromhex(row['transport']['console_hex'])
            self.assertNotIn(b'AddressSanitizer',console);self.assertNotIn(b'runtime error:',console)


class SupportTests(unittest.TestCase):
    def test_changed_pinned_support_record_cannot_supply_flags(self):
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'clean-support-build.json').write_text('{}')
            with self.assertRaisesRegex(evidence.EvidenceError,'exact clean D338'):evidence._codegen(root)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--endpoint',type=Path,required=True)
    parser.add_argument('--helper',type=Path,required=True);parser.add_argument('--support-root',type=Path)
    parser.add_argument('--sanitized-helper',type=Path)
    args,remaining=parser.parse_known_args();EvidenceTests.endpoint=args.endpoint.resolve(strict=True)
    EvidenceTests.helper=args.helper.resolve(strict=True)
    if args.support_root:EvidenceTests.support=args.support_root.resolve(strict=True)
    if args.sanitized_helper:EvidenceTests.sanitized_helper=args.sanitized_helper.resolve(strict=True)
    unittest.main(argv=[sys.argv[0],*remaining])
