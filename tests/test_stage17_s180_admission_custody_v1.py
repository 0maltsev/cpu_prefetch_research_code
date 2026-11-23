"""Real held programme/metadata ownership tests, no research source or stand."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_admission_custody_v1 as custody
import stage17_s180_journal_v1 as journal
from test_stage17_s180_plan_prepare_v1 import fixture


class ProgrammeTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='s180-programme-software-',dir=Path(__file__).resolve().parents[1]/'build');self.addCleanup(temp.cleanup)
        self.directory=Path(temp.name);self.root=self.directory/'programme'
        self.plan=fixture('34247cedab4abe4b44732daae8fdac1700eccffd')
        self.plan['schema_version']='cpu-prefetch-stage17-s180-session-plan/1';del self.plan['source_count_basis']
        self.plan['storage']['program_scope_sha256']=custody.stores.ProgramStore.initialize(self.root,
            program_id=self.plan['storage']['program_id'],storage_domain_id='SOFTWARE-ONLY',prospective_admission_sha256='a'*64)
        self.family=hashlib.sha256(custody.archive.canonical(self.plan)).hexdigest()
        self.limits=custody.stores.base.CustodyLimits(131072,500000,500000,2*1024**2,time.monotonic_ns()+120*10**9)
        with self.store() as store:
            for i in range(10):store.append('FAILURE',None,dict(software_history=i))
            store.reserve_family()
        now=time.monotonic_ns();self.window=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            start_monotonic_ns=now,end_monotonic_ns=now+86400*10**9)
        self.working=self.root/'working'/self.family

    def store(self):return custody.stores.ProgramStore(self.root,
        scope_sha256=self.plan['storage']['program_scope_sha256'],family_id=self.family,limits=self.limits,
        ext009_resolution_sha256=None)

    def own(self,**changes):
        args=dict(plan=self.plan,window_binding=self.window,program_root=self.root,custody_limits=self.limits,
            deadline_ns=time.monotonic_ns()+60*10**9,preparation_deadline_ns=time.monotonic_ns()+30*10**9)
        args.update(changes);return custody.own_programme(**args)

    def view(self,*,complete=False):
        st=self.working.stat();context=dict(scope_id=custody.authority.RESOURCE_SCOPE,plan_sha256=self.family,
            window_binding=self.window,evidence_root_binding=dict(absolute_path=str(self.working),device=st.st_dev,inode=st.st_ino),
            resource_admission_status='ADMITTED',phase18_authority=False)
        rows={f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',resolution_id=f'SOFTWARE-{i}',sha256=str(i)*64,
            semantic_context={}) for i in range(1,10)}
        rows['S17-EXT-008'].semantic_context={k:v for k,v in context.items() if k!='resource_admission_status'}
        rows['S17-EXT-008'].semantic_context['scope_id']=custody.authority.PLAN_SCOPE
        rows['S17-EXT-009'].semantic_context=context
        return journal.JournalView(rows,'c'*64,2,False)

    def test_one_real_replay_stays_locked_through_many_checked_metadata_uses(self):
        original=custody._AdmissionStore._replay
        with mock.patch.object(custody._AdmissionStore,'_replay',autospec=True,side_effect=original) as calls:
            with self.own() as owner:
                for _ in range(10):
                    with owner.inspect(plan_sha256=self.family) as store:
                        self.assertEqual(store.inspect_reservation()[0]['family_id'],self.family)
                self.assertEqual(calls.call_count,1)
                self.assertEqual(owner.check(plan_sha256=self.family)['original_replay_count'],1)
                self.assertFalse(json.loads(owner.report())['execution_authority'])
                self.assertEqual(owner._store._reading_deadline_ns,owner.deadline)
                pid=os.fork()
                if pid==0:
                    try:
                        with self.store():pass
                    except BlockingIOError:os._exit(0)
                    except BaseException:os._exit(2)
                    os._exit(1)
                _,status=os.waitpid(pid,0);self.assertEqual(os.waitstatus_to_exitcode(status),0)
            with self.store() as store:self.assertEqual(store._sequence,11)

    def test_same_size_old_record_change_rejects_and_restored_bytes_cannot_revive_owner(self):
        with self.own() as owner:
            p=self.root/'ledger/0000000000000000.json';raw=p.read_bytes();p.write_bytes(raw.replace(b'0',b'1',1))
            with self.assertRaisesRegex(custody.ProgrammeError,'inventory or file stamp changed'):owner.check(plan_sha256=self.family)
            p.write_bytes(raw)
            with self.assertRaisesRegex(custody.ProgrammeError,'owner closed, failed'):owner.check(plan_sha256=self.family)

    def test_new_unregistered_object_is_detected_and_never_deleted(self):
        with self.own() as owner:
            p=self.root/'metadata/foreign.json';p.write_bytes(b'{}')
            with self.assertRaisesRegex(custody.ProgrammeError,'inventory or file stamp changed'):owner.check(plan_sha256=self.family)
            self.assertEqual(p.read_bytes(),b'{}')

    def test_ordinary_writes_are_forbidden_without_affecting_original_ledger(self):
        with self.own() as owner:
            with owner.inspect(plan_sha256=self.family) as store:
                with self.assertRaisesRegex(custody.ProgrammeError,'read-only'):store.append('FAILURE',None,dict(forbidden=True))
                with self.assertRaisesRegex(custody.ProgrammeError,'read-only'):store.retain_metadata('unplanned.json',b'{}')
            self.assertEqual(owner.check(plan_sha256=self.family)['ledger_records'],11)

    def test_single_scoped_resource_binding_updates_only_exact_owned_file_and_directory(self):
        before={p.name:p.read_bytes() for p in (self.root/'ledger').iterdir()}
        with self.own() as owner:
            binding=owner.bind_resource_admission(view=self.view())
            self.assertEqual(binding['resolution_sha256'],'9'*64)
            self.assertTrue((self.root/'metadata'/binding['metadata']['file_name']).exists())
            with owner.inspect(plan_sha256=self.family) as store:store._family_scope_fields()
            with self.assertRaisesRegex(custody.ProgrammeError,'unused binding'):owner.bind_resource_admission(view=self.view())
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.root/'ledger').iterdir()})

    def test_wrong_scoped_profile_output_window_and_incomplete_view_cannot_bind(self):
        with self.own() as owner:
            view=self.view();rows=view.resolutions;rows['S17-EXT-009'].semantic_context['evidence_root_binding']['inode']+=1
            with self.assertRaisesRegex(custody.ProgrammeError,'output/window'):
                owner.bind_resource_admission(view=journal.JournalView(rows,'c'*64,2,False))
            self.assertFalse(any(p.name.startswith('s180-admission-') for p in (self.root/'metadata').iterdir()))

    def test_closed_expired_and_forged_programme_handles_fail(self):
        with self.assertRaisesRegex(custody.ProgrammeError,'actual held'):
            custody._OwnedProgramme(token=object(),store=None,plan={},window={},deadline=1)
        with self.own() as owner:
            owner.deadline=time.monotonic_ns()-1
            with self.assertRaisesRegex(custody.ProgrammeError,'deadline expired'):owner.check(plan_sha256=self.family)
        with self.assertRaisesRegex(custody.ProgrammeError,'owner closed, failed'):owner.check(plan_sha256=self.family)

    def test_replaced_root_and_original_lock_are_rejected_without_unknown_writes(self):
        with self.own() as owner:
            self.root.rename(self.root.with_name('retained-original'));self.root.mkdir(mode=0o700)
            (self.root/'foreign').write_text('keep')
            with self.assertRaises((custody.ProgrammeError,custody.stores.base.CustodyError,FileNotFoundError)):
                owner.check(plan_sha256=self.family)
            self.assertEqual({p.name for p in self.root.iterdir()},{'foreign'})

    def test_reused_lock_fd_is_not_closed_by_cleanup_or_python_stream_destructor(self):
        context=self.own();owner=context.__enter__();fd=owner._store._lock.fileno()
        p=self.directory/'replacement';p.write_bytes(b'keep');os.close(fd);replacement=os.open(p,os.O_RDONLY)
        self.assertEqual(fd,replacement)
        try:
            with self.assertRaisesRegex(custody.ProgrammeError,'not closing replacement'):context.__exit__(None,None,None)
            import gc
            del owner;gc.collect();self.assertEqual(os.read(replacement,4),b'keep')
        finally:
            os.close(replacement)
            # Only the test knows the foreign descriptor is now closed. Clear
            # its quarantined Python wrapper without a shutdown EBADF message.
            stream=custody._QUARANTINED_LOCK_STREAMS.pop()
            try:stream.close()
            except OSError:pass

    def test_complete_authorization_handoff_releases_once_without_consuming_native_attempt(self):
        with self.own() as owner:
            owner.bind_resource_admission(view=self.view());rows=self.view().resolutions
            authorization=dict(plan_sha256=self.family,window_binding=self.window,prerequisite_bindings=dict(ext009_resolution_sha256='9'*64))
            raw=custody.archive.canonical(authorization);verified=custody.authority.VerifiedRequest(raw,b'{}')
            rows['S17-EXT-010']=SimpleNamespace(semantic_context=dict(authorization_sha256=hashlib.sha256(raw).hexdigest()))
            view=journal.JournalView(rows,'c'*64,3,False);owner.release_for_launch(view=view,verified=verified)
            self.assertTrue(owner.closed);self.assertTrue(owner.released)
            with self.store() as store:self.assertEqual(store._sequence,11)
            with self.assertRaisesRegex(custody.ProgrammeError,'owner closed'):owner.release_for_launch(view=view,verified=verified)
        self.assertFalse(any(p.name.startswith('s180-attempt') for p in (self.root/'metadata').iterdir()))

    def test_existing_research_uid_is_observed_preserved_and_never_chowned_to_controller(self):
        original=Path.stat
        def observed(path,*args,**kwargs):
            value=original(path,*args,**kwargs)
            if path in (self.root,self.root/'broker.lock'):
                fields={k:getattr(value,k) for k in dir(value) if k.startswith('st_')}
                fields['st_uid']=1000;return SimpleNamespace(**fields)
            return value
        with mock.patch.object(Path,'stat',observed):
            with mock.patch.object(custody.os,'chown',side_effect=AssertionError('must preserve owner')):
                with self.own() as owner:
                    report=json.loads(owner.report())
                    self.assertEqual(report['actual_programme_owner_uid'],1000)
                    self.assertEqual(report['actual_broker_lock_owner_uid'],1000)
                    self.assertEqual(report['current_controller_uid'],0)
                    self.assertTrue(owner.check(plan_sha256=self.family)['original_lock_still_held'])

    def test_expired_or_extended_preparation_budget_cannot_start_a_lease(self):
        for deadline in (time.monotonic_ns()-1,time.monotonic_ns()+601*10**9):
            with self.subTest(deadline=deadline),self.assertRaisesRegex(custody.ProgrammeError,'public-preflight deadline'):
                with self.own(preparation_deadline_ns=deadline):self.fail('invalid preparation budget')
        with self.store() as store:self.assertEqual(store._sequence,11)


if __name__=='__main__':unittest.main()
