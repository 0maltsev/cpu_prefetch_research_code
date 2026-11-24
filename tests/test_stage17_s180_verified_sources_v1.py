"""Actual sealing/child/cleanup integration with disjoint synthetic sources."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import stage17_s180_verified_sources_v1 as owned
import test_stage17_s180_source_provenance_v1 as fixtures


def descriptors():
    return {int(p.name) for p in Path('/proc/self/fd').iterdir()
            if p.exists() and 'stage17-s180-verified-source' in os.readlink(p)}


class VerifiedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.SourceTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixtures.SourceTests.tearDownClass()

    def setUp(self):
        self.f=fixtures.SourceTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.sha=owned.provenance.planning.sha(self.f.p)
        self.before=descriptors()
        self.addCleanup(lambda:self.assertEqual(self.before,descriptors()))

    def bank(self,**changes):
        now=time.monotonic_ns()
        args=dict(plan=self.f.p,seed_id=self.f.seed,records=self.f.r,maximum_source_bytes=1024**2,
            maximum_vector_bytes=1024**2,verification_deadline_ns=now+30_000_000_000,
            valid_until_ns=now+60_000_000_000)
        args.update(changes)
        return owned.verified_sources(**args)

    def inputs(self,bank):
        deadline=min(bank._until,time.monotonic_ns()+self.f.p['budget']['setup_ns'])
        return bank.native_inputs(plan_sha256=self.sha,loading_deadline_ns=deadline)

    def test_owned_release_proof_requires_complete_close_and_no_remaining_alias(self):
        with self.bank() as bank:
            with self.assertRaisesRegex(owned.SourcesError,'complete owned source release'):
                bank.released_proof(plan_sha256=self.sha)
            report=bank.generation_report(plan_sha256=self.sha)
        proof=bank.released_proof(plan_sha256=self.sha)
        self.assertEqual(proof['generation_report_sha256'],hashlib.sha256(report).hexdigest())
        self.assertTrue(proof['all_owned_source_descriptors_released'])
        self.assertFalse(proof['execution_authority'])

    def test_duplicate_descriptor_is_detected_by_actual_owned_release_proof(self):
        alias=None
        try:
            with self.bank() as bank:
                _,fds=self.inputs(bank);alias=os.dup(fds[0])
            with self.assertRaisesRegex(owned.SourcesError,'descriptor alias'):
                bank.released_proof(plan_sha256=self.sha)
        finally:
            if alias is not None:os.close(alias)

    def test_actual_generation_runs_once_and_fast_reads_keep_all36_exact_sealed_sources(self):
        real=owned.provenance.verify_source_bank
        with mock.patch.object(owned.provenance,'verify_source_bank',wraps=real) as verify:
            with self.bank() as bank:
                first=bank.generation_report(plan_sha256=self.sha)
                for _ in range(3):
                    context,fds=self.inputs(bank)
                    self.assertEqual(bank.generation_report(plan_sha256=self.sha),first)
                    proof=bank.proof(plan_sha256=self.sha)
                    self.assertFalse(proof['execution_authority'])
                    self.assertFalse(proof['resource_admission_performed'])
                self.assertEqual(verify.call_count,1)
                self.assertEqual(len(fds),36)
                self.assertEqual(set(fds),descriptors()-self.before)
                for binding in context['bindings']:
                    fd=binding['descriptor'];raw=os.pread(fd,binding['size_bytes']+1,0)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),binding['canonical_sha256'])
                    self.assertEqual(fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE,os.O_RDONLY)
                    self.assertEqual(fcntl.fcntl(fd,fcntl.F_GET_SEALS)&owned.SEALS,owned.SEALS)
                    with self.assertRaises(OSError):os.write(fd,b'x')
                context['bindings'][0]['canonical_sha256']='f'*64
                self.assertNotEqual(self.inputs(bank)[0]['bindings'][0]['canonical_sha256'],'f'*64)
                alias=os.open(f'/proc/self/fd/{fds[0]}',os.O_RDWR|os.O_CLOEXEC)
                try:
                    with self.assertRaises(OSError):os.pwrite(alias,b'x',0)
                    with self.assertRaises(OSError):os.ftruncate(alias,0)
                finally:os.close(alias)
        self.assertEqual(descriptors(),self.before)
        with self.assertRaises(owned.SourcesError):bank.generation_report(plan_sha256=self.sha)

    def test_real_child_reads_exact_inherited_native_context_sources(self):
        with self.bank() as bank:
            context,fds=self.inputs(bank)
            script='''import json,os,sys,fcntl,hashlib
c=json.load(sys.stdin)
assert c['schema_version']=='cpu-prefetch-stage17-s180-schedule-source-context/1'
mask=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
for b in c['bindings']:
 f=b['descriptor'];assert fcntl.fcntl(f,fcntl.F_GET_SEALS)&mask==mask
 assert fcntl.fcntl(f,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY
 raw=os.pread(f,b['size_bytes']+1,0)
 assert len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['canonical_sha256']
print(len(c['bindings']))
'''
            result=subprocess.run([sys.executable,'-B','-c',script],input=json.dumps(context),text=True,
                pass_fds=fds,capture_output=True,timeout=15,check=True)
            self.assertEqual(result.stdout.strip(),'36')
            self.assertEqual(bank.proof(plan_sha256=self.sha)['owner_pid'],os.getpid())

    def test_signed_journal_replay_uses_live_verified_sources_without_regenerating(self):
        import stage17_s180_journal_v1 as journal
        # Source generation, seals, SSHSIG and journal publication are real.
        # Original replay, qualification/runtime and resource facts are fixtures;
        # this is not the still-missing qualified complete semantic provider.
        scratch=self.f.directory.parent
        key=scratch/'owner'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],
            check=True,capture_output=True,timeout=10)
        allowed=scratch/'allowed-signers'
        allowed.write_text('software-owner namespaces="cpu-prefetch-stage17" '+key.with_suffix('.pub').read_text())
        trust=dict(measurements=dict(principal='software-owner',sshsig_namespace='cpu-prefetch-stage17',
            allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest()))
        base={f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',resolution_id=f'software-{i}',
            sha256=hashlib.sha256(str(i).encode()).hexdigest(),semantic_context={}) for i in range(1,8)}
        base['S17-EXT-003'].semantic_context=dict(trust=trust)
        base['S17-EXT-007'].sha256=self.f.p['blueprint']['ext007_resolution']['sha256']
        base['S17-EXT-007'].semantic_context=dict(calibration_scope=journal.CALIBRATION_SCOPE,
            data_provenance_accepted=True,legacy_statistical_freeze_satisfied=False)
        validation=SimpleNamespace(resolutions=base,latest_journal_sha256='d'*64)
        output=scratch/'working'/self.sha;output.mkdir(parents=True,mode=0o700);st=output.stat()
        start=time.monotonic_ns();end=start+owned.DAY_NS
        context=dict(scope_id=journal.authority.PLAN_SCOPE,plan_sha256=self.sha,
            window_binding=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                start_monotonic_ns=start,end_monotonic_ns=end),
            evidence_root_binding=dict(absolute_path=str(output),device=st.st_dev,inode=st.st_ino),
            runtime_binding=dict(role=journal.authority.ROLE,profile=journal.authority.PROFILE,sha256='e'*64,size_bytes=1),
            release_binding=dict(source_revision=self.f.p['source_revision'],worker_sha256='e'*64),
            qualification_sha256='a'*64,compatibility_sha256='b'*64,runtime_profile_sha256='c'*64,
            phase18_authority=False)
        real=owned.provenance.verify_source_bank
        with mock.patch.object(owned.provenance,'verify_source_bank',wraps=real) as verify, \
             mock.patch.object(journal,'BLUEPRINT_SHA256',self.f.fingerprint):
            with self.bank(valid_until_ns=end) as bank:
                expected=hashlib.sha256(bank.generation_report(plan_sha256=self.sha)).hexdigest()
                def semantic(input_id,payload,view,*,for_execution):
                    self.assertEqual(input_id,'S17-EXT-008')
                    actual=hashlib.sha256(bank.generation_report(plan_sha256=self.sha)).hexdigest()
                    owned.require(payload==dict(generation_report_sha256=actual),'journal source proof differs')
                    self.inputs(bank)
                    return context
                obj=journal.ScopedJournal(scratch/'journal',base_validation=validation,plan=self.f.p,
                    semantic_policy_sha256='f'*64,semantic_replay=semantic,synthetic_test_only=True)
                obj.initialize()
                with obj:
                    with self.assertRaisesRegex(owned.SourcesError,'source proof differs'):
                        obj.prepare_record(input_id='S17-EXT-008',resolution_id='software-scoped-8',
                            payload=dict(generation_report_sha256='f'*64))
                    raw=obj.prepare_record(input_id='S17-EXT-008',resolution_id='software-scoped-8',
                        payload=dict(generation_report_sha256=expected))
                    path=scratch/'signed-8.json';path.write_bytes(raw)
                    subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(key),
                        '-n','cpu-prefetch-stage17',str(path)],check=True,capture_output=True,timeout=10)
                    def binding(p):
                        raw=p.read_bytes()
                        return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                    view=obj.append(record_binding=binding(path),signature_binding=binding(Path(str(path)+'.sig')))
                    for _ in range(3):self.assertEqual(obj.inspect(for_execution=True).generation,1)
                    self.assertFalse(view.pilot_ready)
                    self.assertFalse(view.execution_authority)
                    self.assertEqual(verify.call_count,1)
                    metadata=Path(self.f.r[0]['envelope']['path']);metadata.write_bytes(metadata.read_bytes()+b' ')
                    with self.assertRaisesRegex(owned.SourcesError,'changed since generation verification'):
                        obj.inspect(for_execution=True)

    def test_forged_serialized_proof_cannot_construct_owned_bank(self):
        with self.assertRaises(TypeError):self.bank(verified_report={'accepted_generation_verified':True})
        with self.assertRaises(owned.SourcesError):
            owned._VerifiedSources(token=object(),report={},bindings=[],originals={},
                maximum_vector_bytes=1,valid_until_ns=time.monotonic_ns()+1,maximum_loading_ns=1)

    def test_loading_deadline_is_short_even_when_verified_bank_lives_for_a_day(self):
        with self.bank(valid_until_ns=time.monotonic_ns()+owned.DAY_NS) as bank:
            deadline=time.monotonic_ns()+self.f.p['budget']['setup_ns']
            context,_=bank.native_inputs(plan_sha256=self.sha,loading_deadline_ns=deadline)
            self.assertEqual(context['deadline_monotonic_ns'],deadline)
            self.assertLessEqual(deadline-time.monotonic_ns(),self.f.p['budget']['setup_ns'])
            self.assertGreater(bank.proof(plan_sha256=self.sha)['valid_until_monotonic_ns'],deadline)
            for invalid in (0,bank._until,bank._until+1):
                with self.assertRaisesRegex(owned.SourcesError,'loading deadline'):
                    bank.native_inputs(plan_sha256=self.sha,loading_deadline_ns=invalid)
            with self.assertRaises(TypeError):bank.native_inputs(plan_sha256=self.sha)

    def test_all_limits_fail_before_generator_or_source_pinning(self):
        for changes in (dict(maximum_source_bytes=1),dict(maximum_vector_bytes=1),
            dict(verification_deadline_ns=0),dict(valid_until_ns=0),
            dict(valid_until_ns=time.monotonic_ns()+owned.DAY_NS+10**12)):
            with mock.patch.object(owned.provenance,'verify_source_bank') as verify:
                with self.subTest(changes=changes),self.assertRaises(owned.SourcesError):
                    with self.bank(**changes):pass
                verify.assert_not_called()
        with mock.patch.object(owned.resource,'getrlimit',return_value=(32,32)):
            with self.assertRaisesRegex(owned.SourcesError,'FD limit'):
                with self.bank():pass
        self.assertEqual(descriptors(),self.before)

    def test_generator_failure_retains_originals_and_opens_no_sealed_fds(self):
        binding=self.f.r[0]['binary'];path=Path(binding['path'])
        raw=path.read_bytes();path.write_bytes(bytes(8)+raw[8:])
        original=path.read_bytes()
        with self.assertRaises(owned.provenance.SourceError):
            with self.bank():pass
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(descriptors(),self.before)

    def test_partial_pin_failure_closes_prior_fds_and_preserves_all_input_files(self):
        original={p.name:p.read_bytes() for p in self.f.directory.iterdir()}
        real=owned._pin;count=0
        def fail(*args,**kwargs):
            nonlocal count
            count+=1
            if count==4:raise OSError('synthetic fourth-source pin failure')
            return real(*args,**kwargs)
        with mock.patch.object(owned,'_pin',side_effect=fail):
            with self.assertRaises(OSError):
                with self.bank():pass
        self.assertEqual(descriptors(),self.before)
        self.assertEqual({p.name:p.read_bytes() for p in self.f.directory.iterdir()},original)

    def test_changed_source_between_verification_and_pin_is_rejected(self):
        real=owned._pin;count=0
        def mutate(binding,**kwargs):
            nonlocal count
            count+=1
            if count==2:
                path=Path(binding['path']);raw=path.read_bytes();path.write_bytes(bytes(8)+raw[8:])
            return real(binding,**kwargs)
        with mock.patch.object(owned,'_pin',side_effect=mutate):
            with self.assertRaisesRegex(owned.SourcesError,'changed while sealing'):
                with self.bank():pass
        self.assertEqual(descriptors(),self.before)

    def test_changed_metadata_after_sealing_blocks_fast_reuse(self):
        with self.bank() as bank:
            path=Path(self.f.r[0]['envelope']['path']);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(owned.SourcesError,'changed since generation verification'):
                self.inputs(bank)
        self.assertEqual(descriptors(),self.before)

    def test_real_short_writes_are_completed_before_sealing(self):
        real=owned.os.write
        def short(fd,data):return real(fd,data[:max(1,len(data)//2)])
        with mock.patch.object(owned.os,'write',side_effect=short):
            with self.bank() as bank:
                context,_=self.inputs(bank)
                for binding in context['bindings']:
                    raw=os.pread(binding['descriptor'],binding['size_bytes']+1,0)
                    self.assertEqual(hashlib.sha256(raw).hexdigest(),binding['canonical_sha256'])

    def test_seal_failure_releases_partial_source_and_all_previous_fds(self):
        real=owned.fcntl.fcntl;count=0
        def fail(fd,command,*args):
            nonlocal count
            if command==owned.fcntl.F_ADD_SEALS:
                count+=1
                if count==3:raise OSError('synthetic third-source seal failure')
            return real(fd,command,*args)
        with mock.patch.object(owned.fcntl,'fcntl',side_effect=fail):
            with self.assertRaises(OSError):
                with self.bank():pass
        self.assertEqual(descriptors(),self.before)

    def test_parent_exception_closes_complete_bank_without_deleting_originals(self):
        with self.assertRaisesRegex(RuntimeError,'synthetic parent stop'):
            with self.bank():raise RuntimeError('synthetic parent stop')
        self.assertEqual(descriptors(),self.before)
        self.assertEqual(len(list(self.f.directory.iterdir())),108)

    def test_wrong_plan_other_process_and_expiry_cannot_reuse_owner(self):
        with self.bank() as bank:
            for getter in (bank.proof,lambda **kw:bank.native_inputs(**kw,loading_deadline_ns=time.monotonic_ns()+1),bank.generation_report):
                with self.assertRaisesRegex(owned.SourcesError,'plan differs'):getter(plan_sha256='f'*64)
            with mock.patch.object(owned.os,'getpid',return_value=os.getpid()+1):
                with self.assertRaisesRegex(owned.SourcesError,'another process'):self.inputs(bank)
            with mock.patch.object(owned.time,'monotonic_ns',return_value=time.monotonic_ns()+owned.DAY_NS):
                with self.assertRaisesRegex(owned.SourcesError,'deadline expired'):bank.proof(plan_sha256=self.sha)

    def test_replaced_fd_fails_without_closing_foreign_descriptor_and_releases_rest(self):
        replacement=None;others=()
        try:
            with self.assertRaisesRegex(owned.SourcesError,'replaced or failed cleanup'):
                with self.bank() as bank:
                    _,fds=self.inputs(bank);replacement=fds[0];others=fds[1:]
                    os.close(replacement)
                    foreign=os.open('/dev/null',os.O_RDONLY|os.O_CLOEXEC)
                    if foreign!=replacement:
                        os.dup2(foreign,replacement);os.close(foreign)
                    with self.assertRaisesRegex(owned.SourcesError,'descriptor changed'):
                        self.inputs(bank)
            os.fstat(replacement)
            for fd in others:
                with self.assertRaises(OSError):os.fstat(fd)
        finally:
            if replacement is not None:os.close(replacement)
        self.assertEqual(descriptors(),self.before)


if __name__=='__main__':
    unittest.main()
