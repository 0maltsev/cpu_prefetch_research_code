"""Actual fork/generator/sealed-bank tests using disjoint tiny SOFTWARE sources.

Only explicit fixture packet/native bindings and live resource observations are
doubled. Real child limits, affinity, held-leader cleanup, files and accepted
independent generation verification execute. No stand preparation occurs.
"""
import contextlib
import copy
from dataclasses import replace
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
import stage17_s180_source_author_v1 as author
import test_stage17_s180_namespace_admission_v1 as namespace_tests
from test_stage17_s180_plan_prepare_v1 import fixture

REPO=Path(__file__).resolve().parents[1]


class RequirementTests(unittest.TestCase):
    def setUp(self):
        self.sizing=json.loads((REPO/'config/stage17/d362-s180-stand-sizing-v1.json').read_bytes())

    def test_stand_packet_changes_only_the_accepted_archive_implementation_binding(self):
        old=json.loads((REPO/'docs/evidence/stage17/PILOT-D334-COMPACTION-INTEGRATION-20261123-01/d333-sizing-v3.json').read_bytes())
        with self.assertRaisesRegex(author.AuthorError,'exact verified'):author.requirements(old)
        self.assertEqual(self.sizing['storage']['implementation_profile_sha256'],
            '23fac285def38a913d4fbb2727eebdb4cda0a18a8f9352bfa9aafa6bee3ca9f6')
        old['storage']['implementation_profile_sha256']=self.sizing['storage']['implementation_profile_sha256']
        self.assertEqual(self.sizing,old)

    def test_actual_frozen_ceiling_packet_has36_streams_without_generation(self):
        with mock.patch.object(author.generator,'generate_schedule',side_effect=AssertionError('must remain cold')):
            budget=author.requirements(self.sizing)
        self.assertEqual(len(budget['jobs']),36)
        self.assertGreater(budget['maximum_source_bytes'],10**9)
        self.assertGreater(budget['maximum_vector_bytes'],budget['maximum_source_bytes'])
        self.assertEqual(budget['source_bank_upper_inodes'],109)
        self.assertFalse(budget['execution_authority']);self.assertFalse(budget['full_resource_admission'])

    def test_changed_ceiling_packet_and_self_consistent_wrong_count_reject(self):
        self.sizing['captures'][0]['phases'][0]['offered_count']-=1
        with self.assertRaisesRegex(author.AuthorError,'exact verified'):author.requirements(self.sizing)
        # Updating a software fixture digest cannot bypass the scientific
        # identity/count derivation. Patch every paired occurrence consistently.
        key=self.sizing['captures'][0]['phases'][0]['schedule_id']
        count=self.sizing['captures'][0]['phases'][0]['offered_count']
        for c in self.sizing['captures']:
            if c['phases'][0]['schedule_id']==key:c['phases'][0]['offered_count']=count
        with mock.patch.object(author,'SIZING_SHA',author.planning.sha(self.sizing)):
            with self.assertRaisesRegex(author.AuthorError,'source ceiling'):author.requirements(self.sizing)


class AuthorTests(unittest.TestCase):
    software_namespaces=True
    setUp_namespace=namespace_tests.NamespaceAdmissionTests.setUp
    reserve=namespace_tests.NamespaceAdmissionTests.reserve

    def setUp(self):
        self.setUp_namespace();self.owner=self.reserve()
        self.sizing=fixture(author.namespaces.environment.NATIVE_REVISION)
        self.sizing['blueprint']=copy.deepcopy(self.blueprint)
        self.sizing['source_count_basis']='PROSPECTIVE_UPPER_CEILINGS'
        rows=sorted(self.blueprint['captures'],key=lambda r:r['execution_ordinal'])
        ids=author.namespaces.audit.planned_identities(self.blueprint)
        lookup={tuple(r[k] for k in ('placement','working_set_class','load_level','phase')):r for r in ids['sources']}
        for bp,entry in zip(rows,self.sizing['captures'],strict=True):
            for i,phase in enumerate(('warmup','measurement')):
                identity=lookup[tuple(bp[k] for k in ('placement','working_set_class','load_level'))+(phase,)]
                n=2*bp['nominal_rate']['numerator']*bp[phase+'_ns']//10**9
                entry['phases'][i].update(schedule_id=identity['schedule_id'],offered_count=n,
                    source_artifact=None,producer_attempt_limit=n)
                entry['resources']['phase_capacity'][i]=dict(producer_primary_rows=n,consumer_primary_rows=n)
        self.author_root=self.root/'source-author'
        for name,value in [('ROOT',self.author_root),('SIZING_SHA',author.planning.sha(self.sizing)),
                ('SOURCE_CPU',min(os.sched_getaffinity(0))),('CLEANUP_NS',10**9)]:
            self.stack.enter_context(mock.patch.object(author,name,value))
        self.observed=dict(rlimit_as=[author.PARENT_AS,-1],base_page_bytes=4096,
            memory_available_bytes=64*1024**3,memory_ancestors=[])
        self.stack.enter_context(mock.patch.object(author.resources,'platform_observation',side_effect=lambda:copy.deepcopy(self.observed)))
        self.stack.enter_context(mock.patch.object(author.os,'statvfs',return_value=SimpleNamespace(f_bavail=2*1024**4,
            f_frsize=1,f_favail=1000000)))
        # The frozen native intentionally accepts only the real approved
        # blueprint. Do not weaken it or generate real research identities for
        # tests. Here only its cold layout interface is a declared double;
        # the registered plan-preparation suite separately exercises the actual
        # unchanged native image and parser on cold declarations.
        def software_layouts(sizing,*,worker,deadline_ns):
            return dict(schema_version=author.planning.REPORT,sizing_plan_sha256=author.planning.sha(sizing),
                binary_sha256=worker.sha256,source_revision=sizing['source_revision'],source_dirty=False,
                source_count_basis=sizing['source_count_basis'],
                contexts=[dict(context_ordinal=i,records_bytes=4096,queues_bytes=4096) for i in range(6)],
                captures=[dict(execution_ordinal=r['execution_ordinal'],cell_ordinal=r['cell_ordinal'],
                    expected_layout=dict(region_bytes=[4096]*9,total_mapping_bytes=9*4096)) for r in sizing['captures']],
                execution_authority=False,phase18_authority=False,session_admission_performed=False)
        self.stack.enter_context(mock.patch.object(author.planning,'native_layouts',side_effect=software_layouts))
        path=REPO/'build/stage17-s180-release-34247ce/cpu_prefetch_runner'
        self.image=author.runtime.ImageBinding(path,author.resources.NATIVE_SIZE,author.resources.NATIVE_SHA)
        self.protected=4*3600*10**9

    def prepare(self,**changes):
        args=dict(namespace_owner=self.owner,sizing=self.sizing,native_image=self.image,
            deadline_ns=time.monotonic_ns()+30*10**9,protected_remaining_ns=self.protected)
        args.update(changes);return author.prepare_sources(**args)

    def result(self):return json.loads((self.author_root/'generation-result.json').read_bytes())

    def test_actual_forked_generation_native_plan_and_single_owned_verification(self):
        original=copy.deepcopy(self.sizing)
        verifier=author.namespaces.sources.provenance.verify_source_bank
        with mock.patch.object(author.namespaces.sources.provenance,'verify_source_bank',wraps=verifier) as calls:
            with self.prepare() as owner:
                proof=owner.proof();self.assertTrue(proof['source_bank_owned_and_verified'])
                self.assertFalse(proof['full_ext008_admission']);self.assertEqual(len(owner.records),36)
                self.assertEqual(calls.call_count,1)
                self.assertEqual(len(list((self.root/'namespace'/'sources').iterdir())),108)
                self.assertEqual(owner.plan['schema_version'],author.planning.PLAN)
                self.assertTrue(all(len(e['expected_layout']['region_bytes'])==9 for e in owner.plan['captures']))
                self.assertEqual(owner.proof(),proof);self.assertEqual(calls.call_count,1)
                ready=json.loads((self.author_root/'child-ready.json').read_bytes())
                self.assertEqual(ready['actual_rlimit_as'],[author.CHILD_AS]*2)
                self.assertEqual(ready['observed_cpus'],[author.SOURCE_CPU])
                self.assertEqual(ready['process_group'],ready['pid']);self.assertEqual(ready['session'],ready['pid'])
                self.assertTrue(self.result()['cleanup']['leader_reaped'])
                self.assertTrue(self.result()['cleanup']['process_group_gone'])
                plan=owner.plan;plan['budget']['setup_ns']=0
                self.assertGreater(owner.plan['budget']['setup_ns'],0)
            self.assertEqual(calls.call_count,1)
        self.assertEqual(self.sizing,original)
        with self.assertRaisesRegex(author.AuthorError,'closed'):owner.proof()
        self.assertFalse(author.supervisor.ProcfsIdentityModel().direct_children())

    def test_child_failure_keeps_partial_originals_and_burns_permission(self):
        real=author._generate
        def broken(job,index,directory,seed):
            if index==1:raise RuntimeError('SOFTWARE injected generation failure')
            return real(job,index,directory,seed)
        with mock.patch.object(author,'_generate',side_effect=broken):
            with self.assertRaisesRegex(author.AuthorError,'child failure'):
                with self.prepare():self.fail('failed child cannot yield')
        files=list((self.root/'namespace'/'sources').iterdir());self.assertEqual(len(files),3)
        self.assertTrue((self.author_root/'child-failure.json').exists());self.assertTrue((self.author_root/'failure.json').exists())
        self.assertTrue(self.result()['cleanup']['leader_reaped'])
        with self.assertRaises(author.namespaces.NamespaceError):
            with self.prepare():self.fail('cannot retry')
        self.assertEqual(files,list((self.root/'namespace'/'sources').iterdir()))

    def test_source_deadline_stops_child_and_proves_reaping(self):
        with mock.patch.object(author,'_worker',side_effect=lambda *args:time.sleep(30)):
            with self.assertRaisesRegex(author.AuthorError,'deadline expired'):
                with self.prepare(deadline_ns=time.monotonic_ns()+4*10**9):self.fail('late source cannot yield')
        result=self.result();self.assertTrue(result['cleanup']['leader_reaped'])
        self.assertTrue(result['cleanup']['process_group_gone']);self.assertFalse(result['automatic_retry'])
        self.assertFalse(author.supervisor.ProcfsIdentityModel().direct_children())

    def test_escaped_descendant_is_reaped_and_generation_rejected(self):
        def escaped(*args):
            if os.fork()==0:
                os.setsid();time.sleep(30);os._exit(0)
        with mock.patch.object(author,'_worker',side_effect=escaped):
            with self.assertRaisesRegex(author.AuthorError,'child failure'):
                with self.prepare():self.fail('descendant invalidates completion')
        cleanup=self.result()['cleanup'];self.assertTrue(cleanup['leader_reaped'])
        self.assertTrue(cleanup['descendants_detected_after_leader_exit'])
        self.assertFalse(author.supervisor.ProcfsIdentityModel().direct_children())

    def test_console_overflow_retains_bounded_prefix_and_stops(self):
        def noisy(*args):
            while True:os.write(1,b'x'*4096)
        with mock.patch.object(author,'_worker',side_effect=noisy):
            with self.assertRaisesRegex(author.AuthorError,'console bound'):
                with self.prepare():self.fail('overflow cannot yield')
        self.assertEqual((self.author_root/'console.txt').stat().st_size,author.CONSOLE_BYTES)
        self.assertTrue(self.result()['cleanup']['leader_reaped'])

    def test_wrong_native_incomplete_time_memory_and_space_fail_before_consumption(self):
        with self.assertRaisesRegex(author.AuthorError,'frozen native'):
            with self.prepare(native_image=replace(self.image,sha256='0'*64)):self.fail('wrong image')
        with self.assertRaisesRegex(author.AuthorError,'post-source reserve'):
            with self.prepare(protected_remaining_ns=1):self.fail('short post-work')
        self.observed['memory_available_bytes']=1
        with self.assertRaisesRegex(author.AuthorError,'memory/page'):
            with self.prepare():self.fail('insufficient memory')
        self.observed['memory_available_bytes']=64*1024**3
        with mock.patch.object(author.os,'statvfs',return_value=SimpleNamespace(f_bavail=1,f_frsize=1,f_favail=1)):
            with self.assertRaisesRegex(author.AuthorError,'filesystem commitments'):
                with self.prepare():self.fail('insufficient storage')
        self.assertFalse(self.author_root.exists());self.assertIsNone(self.owner.generation)

    def test_changed_original_and_completion_latch_ownership_failure(self):
        with self.prepare() as owner:
            p=self.author_root/'completion.json';raw=p.read_bytes();p.write_bytes(raw+b' ')
            with self.assertRaisesRegex(author.namespaces.NamespaceError,'bound metadata changed'):owner.proof()
            p.write_bytes(raw)
            with self.assertRaisesRegex(author.AuthorError,'failed'):owner.proof()

    def test_replaced_author_directory_is_not_used_for_failure_evidence(self):
        with self.assertRaisesRegex(author.AuthorError,'directory identity'):
            with self.prepare() as owner:
                self.author_root.rename(self.author_root.with_name('retained-author'))
                self.author_root.mkdir(mode=0o700);(self.author_root/'unrelated').write_bytes(b'keep')
                owner.proof()
        self.assertEqual({p.name for p in self.author_root.iterdir()},{'unrelated'})

    def test_no_report_can_construct_the_live_author(self):
        with self.assertRaisesRegex(author.AuthorError,'actual supervised'):
            author._AuthoredSources(token=object(),namespace_owner=None,source_owner=None,
                plan={},records=[],completion={},metadata=[])

    def test_signal_between_fork_and_parent_registration_still_reaps_held_child(self):
        real=author.os.fork
        def pending_signal():
            pid=real()
            if pid>0:os.kill(os.getpid(),signal.SIGTERM)
            return pid
        with mock.patch.object(author.os,'fork',side_effect=pending_signal):
            with self.assertRaisesRegex(author.AuthorError,'interrupted by signal'):
                with self.prepare():self.fail('interrupted source cannot yield')
        self.assertTrue(self.result()['pre_release_leader_reaped'])
        self.assertFalse(author.supervisor.ProcfsIdentityModel().direct_children())
        self.assertFalse((self.author_root/'bank.json').exists())

    def test_pidfd_failure_before_release_reaps_only_the_held_child(self):
        with mock.patch.object(author.os,'pidfd_open',side_effect=OSError('SOFTWARE descriptor exhaustion')):
            with self.assertRaisesRegex(OSError,'descriptor exhaustion'):
                with self.prepare():self.fail('missing pidfd cannot yield')
        self.assertTrue(self.result()['pre_release_leader_reaped'])
        self.assertFalse(author.supervisor.ProcfsIdentityModel().direct_children())

    def test_wrong_generated_artifact_identity_rejects_before_independent_verification(self):
        real=author._generate
        def other_id(*args):
            result=real(*args);result['record']['binary']['artifact_id']='SOFTWARE-FOREIGN';return result
        with mock.patch.object(author,'_generate',side_effect=other_id):
            with mock.patch.object(author.namespaces.sources.provenance,'verify_source_bank',
                    side_effect=AssertionError('must reject before expensive verification')) as check:
                with self.assertRaisesRegex(author.AuthorError,'artifact locator/identity'):
                    with self.prepare():self.fail('foreign stream cannot yield')
                self.assertEqual(check.call_count,0)


if __name__=='__main__':unittest.main()
