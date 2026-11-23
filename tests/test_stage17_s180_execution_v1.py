"""Real signatures/journal/store with explicit software physics boundaries.

No public readiness claim: source generation, hardware qualification, native
collection and inverse analysis use declared doubles. Their existing tests
cover those boundaries. Here the actual coordinator order, data bindings and
failure cleanup execute, with a new disposable signer, never the stand key.
"""
import argparse
import contextlib
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_execution_v1 as execution
import test_stage17_s180_authority_v1 as previous


class ExecutionTests(unittest.TestCase):
    worker=None

    @classmethod
    def setUpClass(cls):
        previous.AuthorityTests.worker=cls.worker;previous.AuthorityTests.setUpClass()

    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(previous.tempfile,'tempdir',str(Path(__file__).resolve().parents[1]/'build')))
        self.f=previous.AuthorityTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root/'controller';self.events=[];self.failure=None;self.apis={}
        self.stack.enter_context(mock.patch.object(execution,'ROOT',self.root))
        self.stack.enter_context(mock.patch.object(execution,'KEY',self.f.key))
        self.stack.enter_context(mock.patch.object(execution,'_CONSUMED',False))
        self.program=self.f.root/'programme';self.stack.enter_context(mock.patch.object(execution,'PROGRAM',self.program))
        scope=execution.custody.ProgramStore.initialize(self.program,program_id=self.f.plan['storage']['program_id'],
            storage_domain_id='SOFTWARE-ONLY',prospective_admission_sha256='c'*64)
        self.plan=copy.deepcopy(self.f.plan);self.plan['storage']['program_scope_sha256']=scope
        self.family=execution._sha(self.plan)
        base_rows={k:copy.deepcopy(v) for k,v in self.f.resolutions.items() if int(k[-3:])<=7}
        trust=base_rows['S17-EXT-003'].semantic_context['trust']['measurements']
        trust.update(principal=execution.PRINCIPAL,sshsig_namespace=execution.NAMESPACE)
        self.f.allowed.write_text(execution.PRINCIPAL+' namespaces="'+execution.NAMESPACE+'" '+self.f.key.with_suffix('.pub').read_text())
        trust.update(allowed_signers_size_bytes=self.f.allowed.stat().st_size,
            allowed_signers_sha256=execution.hashlib.sha256(self.f.allowed.read_bytes()).hexdigest())
        base_rows['S17-EXT-007'].semantic_context.update(calibration_scope=execution.journal.CALIBRATION_SCOPE)
        self.base=SimpleNamespace(resolutions=base_rows,latest_journal_sha256='d'*64)
        self.base.resolutions['S17-EXT-006'].semantic_context['archive_bundle_root']='/SOFTWARE/accepted-original-bundle'
        self.source=SimpleNamespace(released=False,released_proof=self.released_proof)
        self.env=SimpleNamespace(closed=False)
        self.window=None
        self.inputs=SimpleNamespace(sizing=self.plan,local_history_binding={},operator_profile_sha256='b'*64,
            operator_revision='e'*40,archive_profile=SimpleNamespace(decoder=SimpleNamespace(window_log=22)),
            base_owner=SimpleNamespace(view=lambda:self.base),native_image=self.f.worker,clock_image=self.f.worker,
            evidence_helper=self.f.worker,support_root=Path('/SOFTWARE/support'),
            native_source_root=Path('/SOFTWARE/frozen-source'),native_release_root=Path('/SOFTWARE/frozen-release'),
            codegen_report=Path('/SOFTWARE/codegen.json'),supervision=SimpleNamespace(script=SimpleNamespace()),
            unrelated_reservations=dict(declaration_sha256=execution.DECLARATION_SHA,reserved_bytes=8*execution.GIB,
                reserved_inodes=131072,workspace_committed_bytes=88*execution.GIB,scratch_committed_bytes=88*execution.GIB))
        self.patch(execution.namespaces,'reserve',self.reserve)
        self.patch(execution.author,'prepare_sources',self.sources)
        self.patch(execution.compatibility,'verify',lambda **kwargs:self.event('compatibility'))
        self.patch(execution.environment,'prospective_config',lambda **kwargs:{})
        self.patch(execution.environment,'prepare_environment',self.environment)
        self.patch(execution.compaction,'verify_supervision',lambda **kwargs:self.event('supervision-fresh'))
        self.patch(execution.compaction,'prepare',lambda **kwargs:self.event('compaction'))
        self.patch(execution.clocks,'qualify_clocks',lambda **kwargs:self.event('clocks'))
        self.patch(execution.q15,'prepare',lambda **kwargs:SimpleNamespace(execute=self.q15,completed=lambda:self.event('q15-completed')))
        self.patch(execution.qualification,'publish',lambda **kwargs:self.event('export'))
        self.patch(execution.platform,'verify_platform',lambda **kwargs:self.event('platform'))
        self.patch(execution.admission,'verify_plan',lambda **kwargs:SimpleNamespace(payload={'SOFTWARE_PLAN':'only'}))
        self.patch(execution.resources,'verify_resources',lambda **kwargs:SimpleNamespace(report=lambda:b'SOFTWARE-RESOURCE'))
        self.patch(execution.admission,'ScopedSemantics',lambda **kwargs:self.semantic)
        self.patch(execution.launcher,'launch',self.launch)
        self.patch(execution.phase,'analysis_phase',self.analysis_phase)
        self.patch(execution.analysis,'analyze_family',self.analyze)
        self.real_own_programme=execution.programme.own_programme
        self.patch(execution.programme,'own_programme',self.own_programme)

    def patch(self,obj,name,value):
        current=self.apis.setdefault((id(obj),name),getattr(obj,name))
        replacement=mock.create_autospec(current,side_effect=value) if callable(current) and not isinstance(current,mock.Mock) else value
        self.stack.enter_context(mock.patch.object(obj,name,replacement))
    def event(self,name):
        self.events.append(name)
        if self.failure==name:raise ValueError('SOFTWARE forced '+name)
        return SimpleNamespace()

    def reserve(self,**kwargs):
        self.window=kwargs['window_binding'];self.event('namespace')
        return SimpleNamespace(close=lambda:self.event('namespace-closed'))

    @contextlib.contextmanager
    def sources(self,**kwargs):
        self.event('source-start')
        try:yield SimpleNamespace(plan=self.plan,source_owner=self.source)
        finally:self.source.released=True;self.event('source-released')

    @contextlib.contextmanager
    def environment(self,**kwargs):
        self.event('environment')
        try:yield self.env
        finally:
            if not self.env.closed:self.env.closed=True;self.event('restored')

    @contextlib.contextmanager
    def own_programme(self,**kwargs):
        with self.real_own_programme(**kwargs) as owner:
            self.event('programme-held');yield owner

    def q15(self,**kwargs):self.event('q15')

    def semantic(self,input_id,payload,view,*,for_execution):
        # Actual journal signatures/ordering, actual held programme binding and
        # actual authorization verifier still execute. Scientific facts here
        # are explicitly SOFTWARE fixtures, independently tested elsewhere.
        self.event(input_id)
        output=self.program/'working'/self.family;st=output.stat()
        common=dict(plan_sha256=self.family,window_binding=self.window,
            evidence_root_binding=dict(absolute_path=str(output),device=st.st_dev,inode=st.st_ino),phase18_authority=False)
        if input_id=='S17-EXT-008':
            self.assertEqual(payload,{'SOFTWARE_PLAN':'only'})
            return dict(common,scope_id=execution.authority.PLAN_SCOPE,runtime_binding=self.f.native,
                release_binding=self.f.authorization['release_binding'],qualification_sha256='1'*64,
                compatibility_sha256='2'*64,runtime_profile_sha256=self.inputs.operator_profile_sha256)
        self.assertEqual(payload,dict(resource_proof_sha256=hashlib.sha256(b'SOFTWARE-RESOURCE').hexdigest()))
        return dict(common,scope_id=execution.authority.RESOURCE_SCOPE,resource_admission_status='ADMITTED')

    def launch(self,**kwargs):
        self.event('native');self.assertFalse(self.source.released)
        # Real signed EXT009 was durably bound before the native boundary.
        # The SOFTWARE native double leaves the admission lease to its context;
        # production releases it through the original qualified launcher.
        current=self.program/'metadata'/('s180-admission-'+self.family+'.json')
        self.assertTrue(current.exists())
        self.env.closed=True;self.event('restored')
        failed=self.failure=='native-stop'
        return dict(document=dict(status='STOPPED' if failed else 'NATIVE_COLLECTED_PENDING_SCIENTIFIC_VALIDATION',
            failure='SOFTWARE native failure' if failed else None,acknowledged_captures=3 if failed else 180,
            quarantined=False),terminal=dict(file_name='SOFTWARE-terminal',size_bytes=1,sha256='f'*64))

    def released_proof(self,**kwargs):
        self.assertTrue(self.source.released);return dict(software_fixture_only=True,released=True)

    @contextlib.contextmanager
    def analysis_phase(self,**kwargs):
        self.assertTrue(self.source.released);self.assertTrue(self.env.closed)
        self.event('analysis-phase')
        yield SimpleNamespace(deadline_ns=self.window['end_monotonic_ns']-1800*execution.NS)
        self.event('analysis-phase-closed')

    def analyze(self,**kwargs):
        self.event('analysis');self.assertTrue(self.source.released)
        self.assertEqual(kwargs['other_workspace_committed_bytes'],88*execution.GIB)
        return dict(binding=dict(file_name='family-validation.json',size_bytes=1,sha256='f'*64),
            report=dict(schema_version=execution.analysis.SCHEMA,status='VALIDATED_DESCRIPTIVE_FAMILY_PENDING_OPERATIONAL_EXIT',
                archive_originals_inversely_verified=1440,actual_worker_completion_verified=True,original_archive_custody_verified=True,
                final_live_restoration_verified=True,operational_exit_verified=False,inferential_freeze_established=False,
                execution_authority=False,phase18_authority=False))

    def run_flow(self):return execution._run(self.inputs,self.base)

    def test_full_coordinator_real_signed_journal_and_programme_bindings(self):
        result=self.run_flow()
        self.assertEqual(result['report']['status'],'VALIDATED_PILOT_PENDING_INDEPENDENT_OPERATIONAL_EXIT')
        self.assertFalse(result['report']['independent_service_exit_verified'])
        self.assertFalse(result['report']['phase18_authority'])
        self.assertEqual(self.events.count('native'),1);self.assertEqual(self.events.count('source-start'),1)
        self.assertLess(self.events.index('S17-EXT-009'),self.events.index('native'))
        self.assertLess(self.events.index('source-start'),self.events.index('supervision-fresh'))
        self.assertLess(self.events.index('supervision-fresh'),self.events.index('environment'))
        self.assertLess(self.events.index('restored'),self.events.index('analysis-phase'))
        self.assertLess(self.events.index('source-released'),self.events.index('analysis-phase'))
        self.assertTrue((self.root/'controller-handoff.json.sig').exists())

    def test_stop_terminal_never_reaches_analysis_or_handoff(self):
        self.failure='native-stop'
        with self.assertRaisesRegex(execution.ExecutionError,'native family stopped'):self.run_flow()
        self.assertNotIn('analysis-phase',self.events);self.assertNotIn('analysis',self.events)
        self.assertTrue(self.source.released);self.assertTrue(self.env.closed)
        self.assertFalse((self.root/'controller-handoff.json').exists())
        failure=json.loads((self.root/'controller-failure.json').read_bytes());self.assertFalse(failure['automatic_retry'])

    def test_q15_failure_restores_releases_and_forbids_native(self):
        self.failure='q15'
        with self.assertRaisesRegex(ValueError,'forced q15'):self.run_flow()
        self.assertNotIn('native',self.events);self.assertNotIn('analysis',self.events)
        self.assertTrue(self.env.closed);self.assertTrue(self.source.released)
        self.assertLess(self.events.index('restored'),self.events.index('source-released'))

    def test_clock_failure_does_not_call_q15_or_native(self):
        self.failure='clocks'
        with self.assertRaisesRegex(ValueError,'forced clocks'):self.run_flow()
        self.assertNotIn('q15',self.events);self.assertNotIn('native',self.events)
        self.assertTrue(self.env.closed);self.assertTrue(self.source.released)

    def test_changed_recovery_service_after_sources_blocks_hardware(self):
        self.failure='supervision-fresh'
        with self.assertRaisesRegex(ValueError,'forced supervision-fresh'):self.run_flow()
        self.assertNotIn('environment',self.events);self.assertNotIn('clocks',self.events)
        self.assertTrue(self.source.released);self.assertIn('namespace-closed',self.events)

    def test_analysis_failure_never_retries_collected_native(self):
        self.failure='analysis'
        with self.assertRaisesRegex(ValueError,'forced analysis'):self.run_flow()
        self.assertEqual(self.events.count('native'),1);self.assertEqual(self.events.count('analysis'),1)
        self.assertFalse((self.root/'controller-handoff.json').exists())

    def test_incomplete_analysis_report_cannot_become_a_validated_handoff(self):
        valid=self.analyze
        def stopped(**kwargs):
            result=valid(**kwargs);result['report']['actual_worker_completion_verified']=False;return result
        self.patch(execution.analysis,'analyze_family',stopped)
        with self.assertRaisesRegex(execution.ExecutionError,'no valid complete handoff'):self.run_flow()
        self.assertFalse((self.root/'controller-handoff.json').exists());self.assertEqual(self.events.count('native'),1)

    def test_resource_admission_failure_restores_without_native_collection(self):
        def rejected(**kwargs):raise ValueError('SOFTWARE actual resource admission rejected')
        self.patch(execution.resources,'verify_resources',rejected)
        with self.assertRaisesRegex(ValueError,'resource admission rejected'):self.run_flow()
        self.assertNotIn('native',self.events);self.assertTrue(self.source.released);self.assertTrue(self.env.closed)

    def test_source_failure_never_prepares_hardware_or_qualifies(self):
        self.failure='source-start'
        with self.assertRaisesRegex(ValueError,'forced source-start'):self.run_flow()
        self.assertNotIn('environment',self.events);self.assertNotIn('clocks',self.events)
        self.assertIn('namespace-closed',self.events);self.assertFalse((self.root/'controller-handoff.json').exists())

    def test_compatibility_failure_releases_sources_without_hardware(self):
        self.failure='compatibility'
        with self.assertRaisesRegex(ValueError,'forced compatibility'):self.run_flow()
        self.assertTrue(self.source.released);self.assertNotIn('environment',self.events);self.assertNotIn('native',self.events)

    def test_descriptor_claim_cannot_replace_actual_native_bytes_before_window(self):
        # Only these typed producer boundaries are explicit SOFTWARE doubles;
        # the actual cold image pin/hash check must still reject the bytes.
        base_owner=object.__new__(execution.original._VerifiedOriginal);base_owner.view=lambda:self.base
        supervision=object.__new__(execution.compaction._Supervision);supervision.check=lambda:None
        bad=self.f.root/'not-the-frozen-worker';bad.write_bytes(b'SOFTWARE invalid executable')
        images=[execution.runtime.ImageBinding(bad,size,sha) for size,sha in
            ((execution.compaction.NATIVE_SIZE,execution.compaction.NATIVE_SHA),
             (execution.compaction.CLOCK_SIZE,execution.compaction.CLOCK_SHA),
             (execution.qualification.HELPER_SIZE,execution.qualification.HELPER_SHA))]
        values={k:getattr(self.inputs,k) for k in execution.Inputs.__dataclass_fields__}
        values.update(base_owner=base_owner,supervision=supervision,native_image=images[0],clock_image=images[1],evidence_helper=images[2])
        self.patch(execution.author,'requirements',lambda value:None)
        with self.assertRaises(ValueError):execution.execute_once(execution.Inputs(**values))
        self.assertFalse(self.root.exists());self.assertFalse(execution._CONSUMED)

    def test_base_changed_after_collection_cannot_publish_handoff(self):
        def changed():raise ValueError('SOFTWARE original journal changed')
        self.inputs.base_owner.view=changed
        with self.assertRaisesRegex(ValueError,'journal changed'):self.run_flow()
        self.assertFalse((self.root/'controller-handoff.json').exists());self.assertEqual(self.events.count('native'),1)

    def test_failed_root_is_not_adopted_or_overwritten(self):
        self.root.mkdir();original=b'SOFTWARE previous failure';(self.root/'keep').write_bytes(original)
        with self.assertRaises(FileExistsError):self.run_flow()
        self.assertEqual((self.root/'keep').read_bytes(),original);self.assertFalse(self.events)

    def test_public_entry_rejects_reports_before_any_namespace(self):
        with self.assertRaisesRegex(execution.ExecutionError,'actual original owner'):execution.execute_once({})
        self.assertFalse(self.root.exists())

    def test_public_consumption_survives_failure_and_prevents_second_attempt(self):
        self.patch(execution,'_validate',lambda value:self.base)
        calls=[]
        def failed(*args):calls.append(1);raise RuntimeError('SOFTWARE once-only failure')
        self.patch(execution,'_run',failed)
        with self.assertRaisesRegex(RuntimeError,'once-only'):execution.execute_once(self.inputs)
        with self.assertRaisesRegex(execution.ExecutionError,'already consumed'):execution.execute_once(self.inputs)
        self.assertEqual(calls,[1])

    def test_parent_signal_handlers_are_restored_after_fail_stop(self):
        self.patch(execution,'_validate',lambda value:self.base)
        before={n:signal.getsignal(n) for n in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
        def interrupted(*args):os.kill(os.getpid(),signal.SIGTERM)
        self.patch(execution,'_run',interrupted)
        with self.assertRaisesRegex(execution.ExecutionError,'interrupted by signal'):execution.execute_once(self.inputs)
        self.assertEqual({n:signal.getsignal(n) for n in before},before)
        self.assertTrue(execution._CONSUMED)

    def test_signer_cannot_sign_outside_root_or_overwrite_signature(self):
        other=self.f.root/'outside.json';other.write_bytes(b'SOFTWARE')
        with self.assertRaisesRegex(execution.ExecutionError,'outside'):execution._sign(other,time.monotonic_ns()+execution.NS)
        self.root.mkdir();path=self.root/'input.json';path.write_bytes(b'SOFTWARE');path.chmod(0o600)
        execution._sign(path,time.monotonic_ns()+10*execution.NS)
        with self.assertRaisesRegex(execution.ExecutionError,'already exists'):execution._sign(path,time.monotonic_ns()+execution.NS)

    def test_signing_timeout_kills_and_reaps_its_actual_process(self):
        self.root.mkdir();path=self.root/'input.json';path.write_bytes(b'SOFTWARE-only signing timeout');path.chmod(0o600)
        original=execution.subprocess.Popen;children=[]
        def blocked(argv,**kwargs):
            self.assertEqual(argv[:3],['/usr/bin/ssh-keygen','-Y','sign'])
            process=original([sys.executable,'-I','-B','-c','import time; time.sleep(60)'],**kwargs)
            children.append(process);return process
        with mock.patch.object(execution.subprocess,'Popen',side_effect=blocked):
            with self.assertRaises(execution.subprocess.TimeoutExpired):execution._sign(path,time.monotonic_ns()+execution.NS//5)
        self.assertEqual(len(children),1);self.assertEqual(children[0].returncode,-signal.SIGKILL)
        self.assertFalse(Path(str(path)+'.sig').exists())


class BudgetTests(unittest.TestCase):
    def test_metadata_budget_pauses_work_but_never_resets_spent_time(self):
        now=[100]
        with mock.patch.object(execution.time,'monotonic_ns',side_effect=lambda:now[0]):
            budget=execution._MetadataBudget();budget.start();now[0]+=200*execution.NS;budget.stop()
            now[0]+=8*3600*execution.NS;self.assertEqual(budget.remaining(),400*execution.NS)
            budget.start();now[0]+=399*execution.NS;budget.stop();self.assertEqual(budget.remaining(),execution.NS)
            budget.start();now[0]+=execution.NS
            with self.assertRaisesRegex(execution.ExecutionError,'budget exhausted'):budget.stop()

    def test_explicit_decoder_bounds_cover_original_whole_capture_and_blocks(self):
        path=Path(__file__).resolve().parents[1]/'config/stage17/d362-s180-stand-sizing-v1.json'
        plan=json.loads(path.read_bytes());profile=SimpleNamespace(decoder=SimpleNamespace(window_log=22))
        native,ledger,broker,decoder=execution._limits(plan,profile,time.monotonic_ns()+execution.NS)
        self.assertEqual(native.native_address_space_bytes,64*execution.GIB)
        self.assertEqual(broker.max_children,24);self.assertEqual(broker.broker_address_space_bytes,2*execution.GIB)
        self.assertEqual(ledger.max_checkpoint_bytes,2*execution.MIB)
        self.assertGreaterEqual(decoder.max_decoded_block_bytes,4*execution.MIB)
        self.assertGreaterEqual(decoder.max_canonical_bytes,max(r['execution_budget']['max_output_bytes'] for r in plan['captures']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);args,rest=p.parse_known_args()
    ExecutionTests.worker=args.worker.resolve();unittest.main(argv=[sys.argv[0],*rest])
