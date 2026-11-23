"""Actual source/store composition; explicit qualification/platform boundary doubles.

Real tiny SOFTWARE generation, independent verification/sealing, namespace lease,
reserved FAMILY and metadata checks execute. No real hardware qualification or
operational resolution is created. Prior producer/crypto/native suites cover
their own unchanged boundaries independently.
"""
import copy
import json
import os
from pathlib import Path
import sys
import subprocess
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_plan_admission_v1 as gate
import test_stage17_s180_source_author_v1 as source_tests


class PlanAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_tests.AuthorTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.stack=gate.author.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.program=self.fixture.root/'program'
        scope=gate.resources.custody.ProgramStore.initialize(self.program,
            program_id=self.fixture.sizing['storage']['program_id'],storage_domain_id='SOFTWARE-STORAGE',
            prospective_admission_sha256='c'*64)
        self.fixture.sizing['storage']['program_scope_sha256']=scope
        self.stack.enter_context(mock.patch.object(gate.author,'SIZING_SHA',gate.author.planning.sha(self.fixture.sizing)))
        self.authored=self.stack.enter_context(self.fixture.prepare());self.plan=self.authored.plan
        self.family=gate.author.planning.sha(self.plan);self.base=self.fixture.base;self.profile='b'*64
        self.limits=gate.resources.custody.CustodyLimits(131072,500000,500000,2*1024**2,time.monotonic_ns()+120*10**9)
        with gate.resources.stores.ProgramStore(self.program,scope_sha256=scope,family_id=self.family,
                limits=self.limits,ext009_resolution_sha256=None) as store:store.reserve_family()
        self.working=self.program/'working'/self.family
        self.root=self.fixture.root/'plan-admission';self.stack.enter_context(mock.patch.object(gate,'ROOT',self.root))
        # These producers have their own real-process and real-artifact tests.
        # Here their typed live proof boundary is explicit software fixture data.
        self.environment=object.__new__(gate.resources.environment._PreparedEnvironment)
        self.environment._qualification_failed=False
        self.qualified=object.__new__(gate.qualification._VerifiedEvidence)
        self.qualified.owner=SimpleNamespace(prepared=SimpleNamespace(owner=self.environment))
        self.software=object.__new__(gate.compatibility._VerifiedCompatibility)
        self.platform=object.__new__(gate.platform._VerifiedPlatform)
        self.platform.environment=self.environment;self.platform.qualification=self.qualified;self.platform.compatibility=self.software
        original=gate._original(self.base,self.plan['blueprint']);window=self.fixture.window
        self.software_proof=dict(plan_sha256=self.family,base_resolutions=original,software_compatibility_verified=True,
            inspection_mirror=False,current_source_revision=gate.resources.environment.NATIVE_REVISION)
        self.qualified_proof=dict(plan_sha256=self.family,base_resolutions=original,window_binding=window,
            measurement_runtime_binding=dict(role=gate.authority.ROLE,profile=gate.authority.PROFILE,
                sha256=gate.resources.NATIVE_SHA,size_bytes=gate.resources.NATIVE_SIZE),
            qualification_sha256='a'*64,qualification_profile_sha256=self.profile,dynamic_qualification_verified=True,envelope_count=10)
        raw=gate.archive.canonical(dict(schema_version='SOFTWARE-PLATFORM',plan_sha256=self.family))
        self.platform_proof=dict(plan_sha256=self.family,base_resolutions=original,window_binding=window,
            qualification_sha256='a'*64,software_compatibility_sha256=gate._sha(self.software_proof),
            platform_evidence_sha256=gate.author.hashlib.sha256(raw).hexdigest(),current_geometry_and_regime_verified=True)
        self.stack.enter_context(mock.patch.object(gate.qualification._VerifiedEvidence,'proof',
            side_effect=lambda **kwargs:copy.deepcopy(self.qualified_proof)))
        self.stack.enter_context(mock.patch.object(gate.compatibility._VerifiedCompatibility,'proof',
            side_effect=lambda **kwargs:copy.deepcopy(self.software_proof)))
        self.stack.enter_context(mock.patch.object(gate.platform._VerifiedPlatform,'proof',
            side_effect=lambda **kwargs:copy.deepcopy(self.platform_proof)))
        self.stack.enter_context(mock.patch.object(gate.platform._VerifiedPlatform,'report',return_value=raw))
        self.stack.enter_context(mock.patch.object(gate.blueprint,'verify',return_value={'SOFTWARE_BLUEPRINT':True}))
        self.view=gate.journal.JournalView(copy.deepcopy(self.base.resolutions),'c'*64,0,False)

    def verify(self,**changes):
        args=dict(authored_sources=self.authored,qualification_owner=self.qualified,platform_owner=self.platform,
            compatibility_owner=self.software,base_validation=self.base,program_root=self.program,custody_limits=self.limits,
            operator_profile_sha256=self.profile,deadline_ns=time.monotonic_ns()+60*10**9)
        args.update(changes);return gate.verify_plan(**args)

    def replay(self,owner,**changes):
        args=dict(input_id='S17-EXT-008',payload=owner.payload,view=self.view,for_execution=True)
        args.update(changes);return owner(**args)

    def test_owned_source_and_real_reserved_family_derive_exact_narrow_ext008(self):
        before={p.name:p.read_bytes() for p in (self.program/'ledger').iterdir()}
        owner=self.verify();context=self.replay(owner)
        self.assertEqual(context['scope_id'],gate.authority.PLAN_SCOPE);self.assertEqual(context['plan_sha256'],self.family)
        self.assertEqual(context['evidence_root_binding']['inode'],self.working.stat().st_ino)
        self.assertEqual(context['qualification_sha256'],'a'*64)
        self.assertEqual(context['runtime_profile_sha256'],self.profile);self.assertFalse(context['phase18_authority'])
        compatibility=json.loads(owner.compatibility_report())
        self.assertFalse(compatibility['legacy_statistical_freeze_satisfied'])
        self.assertFalse(compatibility['calibration_strata_homogeneous_claim'])
        self.assertFalse(compatibility['generic_pilot_readiness'])
        report=json.loads(owner.report());self.assertTrue(report['scoped_ext008_semantics_verified'])
        self.assertFalse(report['runtime_profile_qualification_performed_here'])
        self.assertEqual(self.replay(owner,for_execution=False),context)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.program/'ledger').iterdir()})
        self.assertFalse(any(self.working.iterdir()));self.assertEqual(len(list(self.root.iterdir())),4)

    def test_reports_different_owners_and_inspection_mirrors_cannot_substitute(self):
        with self.assertRaisesRegex(gate.PlanAdmissionError,'actual live'):
            self.verify(authored_sources=self.authored.proof())
        self.software_proof['inspection_mirror']=True
        with self.assertRaisesRegex(gate.PlanAdmissionError,'prerequisites are incomplete'):self.verify()
        self.assertTrue(self.environment._qualification_failed);self.assertFalse(self.root.exists())

    def test_cross_environment_qualification_rejects_before_publication(self):
        self.qualified.owner.prepared.owner=object()
        with self.assertRaisesRegex(gate.PlanAdmissionError,'different owners'):self.verify()
        self.assertFalse(self.root.exists())

    def test_wrong_profile_window_ancestry_or_qualification_binding_rejects(self):
        original=copy.deepcopy(self.qualified_proof)
        for key,value in [('qualification_profile_sha256','e'*64),('envelope_count',8),('plan_sha256','f'*64),
                ('base_resolutions',[]),('window_binding',dict(self.fixture.window,end_monotonic_ns=self.fixture.window['end_monotonic_ns']+1))]:
            self.qualified_proof.clear();self.qualified_proof.update(copy.deepcopy(original));self.qualified_proof[key]=value
            with self.subTest(field=key),self.assertRaises(gate.PlanAdmissionError):self.verify()
            self.assertFalse(self.root.exists())

    def test_nonempty_original_family_and_different_programme_cannot_admit(self):
        path=self.working/'partial';path.write_bytes(b'keep')
        with self.assertRaisesRegex(gate.PlanAdmissionError,'nonempty'):self.verify()
        self.assertEqual(path.read_bytes(),b'keep');self.assertFalse(self.root.exists())

    def test_live_expiry_stops_and_historical_inspection_cannot_revalidate(self):
        owner=self.verify();context=self.replay(owner)
        owner.deadline=time.monotonic_ns()-1
        with self.assertRaisesRegex(gate.PlanAdmissionError,'deadline expired'):self.replay(owner)
        self.assertTrue(owner.failed);self.assertTrue(self.environment._qualification_failed)
        self.assertEqual(self.replay(owner,for_execution=False),context)
        owner.deadline=time.monotonic_ns()+60*10**9
        with self.assertRaisesRegex(gate.PlanAdmissionError,'owner failed'):self.replay(owner)

    def test_changed_typed_platform_compatibility_evidence_latches_live_failure(self):
        owner=self.verify();path=self.root/'compatibility.json';raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaisesRegex(gate.author.namespaces.NamespaceError,'bound metadata changed'):self.replay(owner)
        path.write_bytes(raw)
        with self.assertRaisesRegex(gate.PlanAdmissionError,'owner failed'):self.replay(owner)

    def test_changed_current_source_bank_cannot_reuse_previously_valid_ext008(self):
        owner=self.verify();(self.fixture.root/'namespace'/'sources'/'unexpected').write_bytes(b'keep')
        with self.assertRaisesRegex(gate.author.namespaces.NamespaceError,'inventory changed'):self.replay(owner)
        self.assertTrue(owner.failed);self.assertTrue(self.environment._qualification_failed)

    def test_unknown_payload_changed_original_or_synthetic_view_never_derive(self):
        owner=self.verify()
        with self.assertRaisesRegex(gate.PlanAdmissionError,'signed scoped plan'):self.replay(owner,payload={'plan_proof_sha256':'0'*64})
        with self.assertRaisesRegex(gate.PlanAdmissionError,'original-seven view'):
            self.replay(owner,view=gate.journal.JournalView(self.view.resolutions,'c'*64,0,True))
        changed=self.view.resolutions;changed['S17-EXT-001'].sha256='f'*64
        with self.assertRaisesRegex(gate.PlanAdmissionError,'bindings changed'):
            self.replay(owner,view=gate.journal.JournalView(changed,'c'*64,0,False))

    def test_scoped_evidence_replacement_and_completed_reuse_are_rejected(self):
        owner=self.verify();self.root.rename(self.root.with_name('retained-plan-evidence'));self.root.mkdir(mode=0o700)
        (self.root/'unrelated').write_bytes(b'keep')
        with self.assertRaisesRegex(gate.PlanAdmissionError,'directory identity'):self.replay(owner)
        self.assertEqual({p.name for p in self.root.iterdir()},{'unrelated'})
        with self.assertRaises(FileExistsError):self.verify()
        self.assertEqual({p.name for p in self.root.iterdir()},{'unrelated'})

    def test_context_and_payload_returned_copies_cannot_mutate_owner(self):
        owner=self.verify();context=self.replay(owner);context['runtime_profile_sha256']='f'*64
        payload=owner.payload;payload['plan_proof_sha256']='f'*64
        self.assertEqual(self.replay(owner)['runtime_profile_sha256'],self.profile)
        self.assertNotEqual(owner.payload,payload)

    def test_fixed_router_delegates_only_owned_plan_resource_and_leaves_ext010_to_journal(self):
        plan=self.verify();resource=object.__new__(gate.resources._VerifiedResources)
        resource._environment=self.environment;resource._sources=self.authored.source_owner;resource._family=self.family
        router=gate.ScopedSemantics(plan_owner=plan,resource_owner=resource)
        self.assertEqual(router.policy_sha256,gate.POLICY_SHA)
        self.assertEqual(router('S17-EXT-008',plan.payload,self.view,for_execution=True),self.replay(plan))
        with mock.patch.object(gate.resources._VerifiedResources,'__call__',return_value={'SOFTWARE_RESOURCE_CONTEXT':True}) as called:
            self.assertEqual(router('S17-EXT-009',{},self.view,for_execution=False),{'SOFTWARE_RESOURCE_CONTEXT':True})
            called.assert_called_once()
        with self.assertRaisesRegex(gate.PlanAdmissionError,'original signed'):router('S17-EXT-010',{},self.view,for_execution=True)
        resource._sources=object()
        with self.assertRaisesRegex(gate.PlanAdmissionError,'different live owners'):
            gate.ScopedSemantics(plan_owner=plan,resource_owner=resource)

    def test_actual_signed_ext008_journal_uses_owned_callback_and_preserves_original_seven(self):
        key=self.fixture.root/'software-owner'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],
            check=True,capture_output=True,timeout=10)
        allowed=self.fixture.root/'allowed-signers';allowed.write_text('software-owner namespaces="cpu-prefetch-stage17" '+key.with_suffix('.pub').read_text())
        self.base.resolutions['S17-EXT-003'].semantic_context=dict(trust=dict(measurements=dict(principal='software-owner',
            sshsig_namespace='cpu-prefetch-stage17',allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=gate.authority.sha(allowed.read_bytes()))))
        self.base.latest_journal_sha256='c'*64;plan=self.verify()
        with mock.patch.object(gate.journal,'BLUEPRINT_SHA256',gate._sha(self.plan['blueprint'])):
            journal=gate.journal.ScopedJournal(self.fixture.root/'scoped-journal',base_validation=self.base,
                plan=self.plan,semantic_policy_sha256=gate.POLICY_SHA,semantic_replay=plan,synthetic_test_only=False)
            journal.initialize()
            with journal:
                raw=journal.prepare_record(input_id='S17-EXT-008',resolution_id='SOFTWARE-OWNED-EXT008',payload=plan.payload)
                path=self.fixture.root/'signed-ext008.json';path.write_bytes(raw)
                subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(key),'-n','cpu-prefetch-stage17',str(path)],
                    check=True,capture_output=True,timeout=10)
                def binding(p):
                    b=p.read_bytes();return dict(path=str(p),size_bytes=len(b),sha256=gate.authority.sha(b))
                view=journal.append(record_binding=binding(path),signature_binding=binding(Path(str(path)+'.sig')))
                self.assertEqual(view.generation,1);self.assertEqual(journal.inspect(for_execution=True).generation,1)
                self.assertFalse(view.pilot_ready);self.assertFalse(view.execution_authority);self.assertFalse(view.phase18_authority)
                for name,original in self.base.resolutions.items():
                    self.assertEqual(vars(view.resolutions[name]),vars(original))


if __name__=='__main__':unittest.main()
