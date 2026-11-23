"""Scoped history/claim tests; no actual stand namespace is registered."""
import contextlib
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_namespace_admission_v1 as admission
import test_stage17_s180_namespace_audit_v1 as histories


class NamespaceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.history=histories.NamespaceTests();self.history.setUp();self.addCleanup(self.history.doCleanups)
        self.stack=admission.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.blueprint=self.history.bp
        if getattr(self,'software_namespaces',False):
            self.blueprint=json.loads(json.dumps(self.blueprint).replace('CPU-PREFETCH-V5-D310-S180-1','SOFTWARE-NAMESPACE-SOURCE'))
            self.blueprint['master_seed_hex']='22'*32
            for row in self.blueprint['captures']:row['nominal_rate']=dict(
                numerator={'L025':25,'L050':35,'L075':45}[row['load_level']],denominator=1,unit='EVENTS_PER_SECOND')
            fingerprint=admission._sha(self.blueprint)
            for module,key in ((admission.audit,'BLUEPRINT_SHA256'),(admission.environment.planning,'BLUEPRINT_SHA256')):
                self.stack.enter_context(mock.patch.object(module,key,fingerprint))
            self.history.bp=self.blueprint
        self.root=self.history.context/'s180-d310-1';self.root.mkdir(mode=0o700)
        self.local_report=self.history.run_audit('local')
        raw=admission.archive.canonical(self.local_report);self.local=self.history.root/'pc-history.json';self.local.write_bytes(raw)
        self.binding=dict(path=str(self.local),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        self.base=SimpleNamespace(resolutions={f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',
            resolution_id=f'SOFTWARE-ORIGINAL-{i}',sha256=str(i)*64,semantic_context={}) for i in range(1,8)})
        self.base.resolutions['S17-EXT-002'].semantic_context=dict(stand_id=self.blueprint['stand_id'])
        self.base.resolutions['S17-EXT-007'].sha256=self.blueprint['ext007_resolution']['sha256']
        self.base.resolutions['S17-EXT-007'].semantic_context=dict(calibration_scope='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY',
            data_provenance_accepted=True,legacy_statistical_freeze_satisfied=False)
        now=time.monotonic_ns();self.window=dict(boot_id=admission.environment._boot(),start_monotonic_ns=now,
            end_monotonic_ns=now+admission.environment.planning.DAY_NS)
        for name,value in [('ROOT',self.root/'namespace'),('STAND_BASE',self.history.stand),
                ('LOCAL_BASE',str(self.history.local)),('LOCAL_AUDIT_SHA',self.binding['sha256']),
                ('LOCAL_AUDIT_SIZE',self.binding['size_bytes'])]:
            self.stack.enter_context(mock.patch.object(admission,name,value))

    def reserve(self,**changes):
        args=dict(blueprint=self.blueprint,local_history_binding=self.binding,base_validation=self.base,
            operator_profile_sha256='b'*64,window_binding=self.window,deadline_ns=time.monotonic_ns()+30*10**9)
        args.update(changes);owner=admission.reserve(**args);self.addCleanup(owner.close);return owner

    def test_real_local_and_stand_audits_create_one_owned_durable_reservation(self):
        owner=self.reserve();proof=owner.proof()
        self.assertTrue(proof['namespace_reservation_verified']);self.assertFalse(proof['source_generation_consumed'])
        self.assertFalse(proof['full_ext008_admission']);self.assertFalse(proof['execution_authority'])
        self.assertFalse(proof['resource_admission_performed'])
        self.assertEqual(proof['planned_namespaces_including_root'],52)
        self.assertEqual(proof['base_resolutions'][6]['sha256'],self.blueprint['ext007_resolution']['sha256'])
        self.assertEqual((admission.ROOT/'sources').exists(),False)
        self.assertEqual(json.loads((admission.ROOT/'stand-history.json').read_bytes())['status'],'PASS_SCOPED_HISTORY_AUDIT')

    def test_stand_collision_stops_before_ready_and_preserves_failed_claim(self):
        self.history.save(self.history.receipts/'consumed.json',dict(run=self.blueprint['captures'][0]['run_id']))
        with self.assertRaisesRegex(admission.NamespaceError,'stand history'):self.reserve()
        self.assertTrue((admission.ROOT/'failure.json').is_file());self.assertFalse((admission.ROOT/'ready.json').exists())
        with self.assertRaises(FileExistsError):self.reserve()

    def test_existing_claim_is_never_adopted_even_after_close(self):
        owner=self.reserve();raw=(admission.ROOT/'intent.json').read_bytes();owner.close()
        with self.assertRaises(FileExistsError):self.reserve()
        self.assertEqual((admission.ROOT/'intent.json').read_bytes(),raw)

    def test_generation_permission_is_consumed_once_and_preserved_on_close(self):
        owner=self.reserve();deadline=time.monotonic_ns()+20*10**9
        permit=owner.consume_generation(deadline_ns=deadline,protected_remaining_ns=60*10**9)
        self.assertIs(permit.owner,owner);self.assertEqual(permit.deadline_ns,deadline)
        self.assertTrue(owner.proof()['source_generation_consumed'])
        with self.assertRaisesRegex(admission.NamespaceError,'already consumed'):owner.consume_generation(
            deadline_ns=deadline,protected_remaining_ns=60*10**9)
        self.assertTrue((admission.ROOT/'generation-intent.json').is_file())

    def test_changed_claim_or_support_latches_failure(self):
        owner=self.reserve();path=admission.ROOT/'intent.json';raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(admission.NamespaceError,'bound metadata changed'):owner.proof()
        path.write_bytes(raw)
        with self.assertRaisesRegex(admission.NamespaceError,'failed'):owner.proof()

    def test_wrong_plan_seed_window_and_changed_antecedent_never_reserve(self):
        bad=copy.deepcopy(self.blueprint);bad['master_seed_hex']='0'*64
        with self.assertRaises(ValueError):self.reserve(blueprint=bad)
        self.assertFalse(admission.ROOT.exists())
        bad=dict(self.window,boot_id='another-boot')
        with self.assertRaises(ValueError):self.reserve(window_binding=bad)
        path=self.local;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(admission.readers.AdmissionError):self.reserve()
        self.assertFalse(admission.ROOT.exists())

    def test_overlong_generation_or_missing_post_work_cannot_consume(self):
        owner=self.reserve()
        for deadline,protected in ((time.monotonic_ns()+admission.SOURCE_NS+10**9,1),
                (time.monotonic_ns()+10**9,0),(self.window['end_monotonic_ns'],60*10**9)):
            with self.assertRaises(admission.NamespaceError):owner.consume_generation(
                deadline_ns=deadline,protected_remaining_ns=protected)
        self.assertFalse((admission.ROOT/'generation-intent.json').exists())

    def test_report_dictionary_and_different_process_cannot_construct_or_use_owner(self):
        with self.assertRaisesRegex(admission.NamespaceError,'actual owned'):
            admission._NamespaceOwner(token=object(),directory=None,lock=None,intent={},bindings=[],local_binding={})
        owner=self.reserve()
        with mock.patch.object(admission.os,'getpid',return_value=-1):
            with self.assertRaisesRegex(admission.NamespaceError,'process'):owner.proof()

    def test_replaced_directory_is_not_modified_on_failure(self):
        owner=self.reserve();admission.ROOT.rename(admission.ROOT.with_name('retained-original'))
        admission.ROOT.mkdir(mode=0o700);(admission.ROOT/'unrelated').write_text('preserve')
        with self.assertRaisesRegex(admission.NamespaceError,'directory identity'):owner.proof()
        self.assertEqual({p.name for p in admission.ROOT.iterdir()},{'unrelated'})

    def test_closed_descriptor_replacement_is_not_closed_or_unlocked(self):
        owner=self.reserve();fd=owner.lock;os.close(fd)
        replacement=os.open(self.local,os.O_RDONLY);self.assertEqual(replacement,fd)
        try:
            with self.assertRaisesRegex(admission.NamespaceError,'descriptor changed'):owner.close()
            self.assertGreater(os.fstat(replacement).st_size,0)
        finally:os.close(replacement)


class LocalReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history=histories.NamespaceTests();cls.history.setUp()
        cls.stack=admission.contextlib.ExitStack();cls.stack.enter_context(mock.patch.object(admission,'LOCAL_BASE',str(cls.history.local)))
        root=Path(__file__).resolve().parents[1]
        for name in admission.DECLARATIONS:
            path=cls.history.local/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,path)
        cls.original=cls.history.run_audit('local')

    @classmethod
    def tearDownClass(cls):cls.stack.close();cls.history.doCleanups()

    def setUp(self):self.report=copy.deepcopy(self.original)

    def review(self):return admission.review_local_history(self.report,blueprint=self.history.bp)

    def test_only_the_three_exact_unmaterialized_sizing_declarations_are_recognized(self):
        before=copy.deepcopy(self.report);result=self.review()
        self.assertEqual(result['original_status'],'FAIL');self.assertEqual(self.report,before)
        self.assertEqual(len(result['recognized_prospective_declarations']),3)
        self.assertTrue(result['selected_history_reviewed']);self.assertFalse(result['global_unused_claim'])
        self.assertFalse(result['namespace_registration_performed'])

    def test_copied_known_packet_at_another_locator_is_still_an_unknown_match(self):
        self.report['matches'][0]['path']=str(self.history.local/'docs/evidence/unrecognized-copy.json')
        with self.assertRaisesRegex(admission.NamespaceError,'unrecognized'):self.review()

    def test_changed_digest_or_extra_consumed_source_match_is_rejected(self):
        self.report['matches'][0]['sha256']='0'*64
        with self.assertRaisesRegex(admission.NamespaceError,'changed prospective'):self.review()
        self.report=copy.deepcopy(self.original);other=copy.deepcopy(self.report['matches'][0]);other['path']=str(
            self.history.local/'docs/evidence/actual-source-envelope.json');self.report['matches'].append(other)
        with self.assertRaisesRegex(admission.NamespaceError,'unrecognized'):self.review()

    def test_errors_exclusions_reduced_scope_and_authority_assertions_never_pass(self):
        for field,value in [('errors',[{'reason':'missing history'}]),('own_prospective_exclusions',['ignored']),
                ('source_generation_performed',True),('execution_authority',True)]:
            self.report=copy.deepcopy(self.original);self.report[field]=value
            with self.assertRaises(admission.NamespaceError):self.review()
        self.report=copy.deepcopy(self.original);self.report['limits']['max_files']=1
        with self.assertRaisesRegex(admission.NamespaceError,'bounded local audit'):self.review()


class SourceBindingTests(unittest.TestCase):
    software_namespaces=True
    setUp=NamespaceAdmissionTests.setUp
    reserve=NamespaceAdmissionTests.reserve

    @contextlib.contextmanager
    def bank(self,owner,permit,*,wrong_derivation=False):
        from fractions import Fraction
        import stage17_s180_source_provenance_v1 as provenance
        from test_stage17_s180_plan_prepare_v1 import fixture
        plan=fixture(admission.environment.NATIVE_REVISION);plan['schema_version']=admission.environment.planning.PLAN
        del plan['source_count_basis'];plan['blueprint']=self.blueprint;records=[]
        identities=admission.audit.planned_identities(self.blueprint)
        geometry={(r['placement'],r['working_set_class'],r['load_level']):r for r in self.blueprint['captures']}
        for i,row in enumerate(identities['sources']):
            key=tuple(row[k] for k in ('placement','working_set_class','load_level'));bp=geometry[key]
            rate=Fraction(bp['nominal_rate']['numerator'],bp['nominal_rate']['denominator']*10**12)
            phase=0 if row['phase']=='warmup' else 1
            derivation=('SOFTWARE-UNREGISTERED-'+str(i)) if wrong_derivation else row['derivation_record_id']
            spec=provenance.generator.ScheduleSpec(row['schedule_id'],'WARMUP' if phase==0 else 'PILOT',
                row['namespace_id'],row['parent_namespace_id'],row['seed_id'],derivation,
                bytes.fromhex(self.blueprint['master_seed_hex']),0,bp[row['phase']+'_ns']*1000,
                rate.numerator,rate.denominator,row['artifact_id'],f'source-{i}.bin')
            generated=provenance.generator.generate_schedule(spec)
            record={k:row[k] for k in ('placement','working_set_class','load_level','phase')}
            for kind,identity,raw in [('binary',row['artifact_id'],generated.artifact_bytes),
                    ('envelope',row['envelope_artifact_id'],generated.envelope_bytes),
                    ('derivation',row['derivation_artifact_id'],generated.derivation_record_bytes)]:
                path=admission.ROOT/'sources'/f'source-{i}-{kind}';path.write_bytes(raw)
                record[kind]=dict(artifact_id=identity,path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            records.append(record)
            for entry,b in zip(plan['captures'],sorted(self.blueprint['captures'],key=lambda r:r['execution_ordinal']),strict=True):
                if tuple(b[k] for k in ('placement','working_set_class','load_level'))==key:
                    entry['phases'][phase].update(schedule_id=row['schedule_id'],offered_count=len(generated.deadlines),
                        source_artifact=dict(artifact_id=row['artifact_id'],sha256=generated.artifact_sha256),
                        producer_attempt_limit=max(1,len(generated.deadlines)))
                    entry['resources']['phase_capacity'][phase]=dict(producer_primary_rows=len(generated.deadlines),
                        consumer_primary_rows=len(generated.deadlines))
        with admission.sources.verified_sources(plan=plan,seed_id=identities['master_seed']['seed_id'],records=records,
                maximum_source_bytes=1024**2,maximum_vector_bytes=2*1024**2,verification_deadline_ns=permit.deadline_ns,
                valid_until_ns=self.window['end_monotonic_ns']) as source_owner:
            yield source_owner,plan

    def test_actual_generated_verified_sealed_bank_binds_all_reserved_identities(self):
        owner=self.reserve();permit=owner.consume_generation(deadline_ns=time.monotonic_ns()+30*10**9,
            protected_remaining_ns=60*10**9)
        with self.bank(owner,permit) as (bank,plan):
            result=owner.bind_sources(permit=permit,source_owner=bank,plan=plan)
            self.assertIsNotNone(result['source_bank_binding']);self.assertIs(owner.source_owner,bank)
            self.assertTrue(owner.proof()['namespace_reservation_verified']);self.assertFalse(result['full_ext008_admission'])

    def test_other_valid_generator_derivation_does_not_substitute_for_registered_identity(self):
        owner=self.reserve();permit=owner.consume_generation(deadline_ns=time.monotonic_ns()+30*10**9,
            protected_remaining_ns=60*10**9)
        with self.bank(owner,permit,wrong_derivation=True) as (bank,plan):
            with self.assertRaisesRegex(admission.NamespaceError,'reserved identities'):
                owner.bind_sources(permit=permit,source_owner=bank,plan=plan)

    def test_unregistered_extra_file_in_the_bank_is_retained_and_rejected(self):
        owner=self.reserve();permit=owner.consume_generation(deadline_ns=time.monotonic_ns()+30*10**9,
            protected_remaining_ns=60*10**9)
        with self.bank(owner,permit) as (bank,plan):
            (admission.ROOT/'sources'/'unexpected').write_bytes(b'retain')
            with self.assertRaisesRegex(admission.NamespaceError,'directory inventory'):
                owner.bind_sources(permit=permit,source_owner=bank,plan=plan)
            self.assertEqual((admission.ROOT/'sources'/'unexpected').read_bytes(),b'retain')

    def test_bound_bank_rejects_later_unregistered_files(self):
        owner=self.reserve();permit=owner.consume_generation(deadline_ns=time.monotonic_ns()+30*10**9,
            protected_remaining_ns=60*10**9)
        with self.bank(owner,permit) as (bank,plan):
            owner.bind_sources(permit=permit,source_owner=bank,plan=plan)
            (admission.ROOT/'sources'/'late').write_bytes(b'retain')
            with self.assertRaisesRegex(admission.NamespaceError,'bound source bank inventory changed'):owner.proof()


if __name__=='__main__':unittest.main()
