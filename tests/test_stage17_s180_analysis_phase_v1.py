"""Real owned descriptors/lease; explicit software hardware/topology/RAM only."""
from contextlib import ExitStack
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_analysis_phase_v1 as phase
import stage17_formal_archive_runtime_v1 as runtime
import test_stage17_s180_environment_v1 as hardware_fixture
import s180_compaction_fixture


class PhaseTests(unittest.TestCase):
    def memory(self):
        return dict(memory_available_bytes=256*phase.bounds.GIB,memory_ancestors=[],
            rlimit_as=[4*phase.bounds.GIB,-1],base_page_bytes=4096,
            boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())

    def owned(self,*,release=True,restore=True):
        h=hardware_fixture.EnvironmentTests();h.setUp();self.addCleanup(h.doCleanups)
        h.plan=s180_compaction_fixture.compaction.monitored_plan(h.plan);h.sha=phase.environment.planning.sha(h.plan)
        stack=self.enterContext(ExitStack());stack.enter_context(h.io());env=h.guard()
        s180_compaction_fixture.attach(self,env,h.root)
        bindings=[]
        for index in range(36):
            raw=index.to_bytes(8,'big');fd=runtime._sealed_input(raw,'software-analysis-phase-source')
            bindings.append(dict(descriptor=fd,size_bytes=8,canonical_sha256=hashlib.sha256(raw).hexdigest()))
        source=phase.sources._VerifiedSources(token=phase.sources._TOKEN,report=dict(plan_sha256=h.sha),
            bindings=bindings,originals={},maximum_vector_bytes=4096,valid_until_ns=h.window['end_monotonic_ns'],
            maximum_loading_ns=300*10**9)
        self.addCleanup(lambda:None if source._closed else source._close())
        if release:source._close()
        if restore:
            result=h.restore(env);self.assertEqual(result['errors'],[])
            # The existing fake core records restoration; complete its software
            # partition removal so the new independent kernel readback is real.
            for path in h.cg.iterdir():path.unlink()
            h.cg.rmdir()
        observed=self.memory();stack.enter_context(mock.patch.object(phase.resources,'platform_observation',return_value=observed))
        real_read=Path.read_text
        def read(path,*args,**kwargs):
            text=str(path)
            if '/topology/' in text:
                return '0' if path.name=='physical_package_id' else text.split('/cpu')[-1].split('/')[0]
            return real_read(path,*args,**kwargs)
        stack.enter_context(mock.patch.object(Path,'read_text',read))
        return h,source,env,observed

    def enter(self,source,env,sha):
        return phase.analysis_phase(source_owner=source,environment_owner=env,plan_sha256=sha)

    def test_physical_cpu_selection_never_counts_smt_siblings_twice(self):
        allowed=set(range(24));topology={cpu:(cpu//12,cpu%6) for cpu in allowed}
        cpus=phase.physical_cpus(allowed,topology)
        self.assertEqual(len(cpus),12);self.assertEqual(len({topology[c] for c in cpus}),12)
        with self.assertRaisesRegex(phase.resources.ResourceError,'twelve actual'):
            phase.physical_cpus(set(range(12)),{cpu:(0,cpu%6) for cpu in range(12)})
        with self.assertRaises(phase.resources.ResourceError):phase.physical_cpus(allowed,{})

    def test_memory_covers_the_entire196gib_stage_and_every_ancestor(self):
        observed=self.memory();needed=phase.assess_memory(observed);self.assertEqual(needed,196*phase.bounds.GIB)
        for key,value in (('memory_available_bytes',needed-1),('rlimit_as',[-1,-1]),('base_page_bytes',8192)):
            with self.assertRaises(phase.resources.ResourceError):phase.assess_memory(dict(observed,**{key:value}))
        bad=dict(observed,memory_ancestors=[dict(maximum_bytes=needed,current_bytes=1)])
        with self.assertRaisesRegex(phase.resources.ResourceError,'ancestor'):phase.assess_memory(bad)

    def test_original90minute_analysis_retains30minute_exit_reserve(self):
        window=dict(boot_id='software',start_monotonic_ns=1,end_monotonic_ns=1+86400*10**9)
        last=window['end_monotonic_ns']-7200*10**9
        self.assertEqual(phase.phase_deadline(last,window),last+5400*10**9)
        with self.assertRaisesRegex(phase.resources.ResourceError,'do not fit'):phase.phase_deadline(last+1,window)
        with self.assertRaises(phase.resources.ResourceError):phase.phase_deadline(last,dict(window,end_monotonic_ns=window['end_monotonic_ns']+1))

    def test_serialized_success_cannot_construct_an_owned_phase(self):
        with self.assertRaisesRegex(phase.resources.ResourceError,'actual owned'):
            with self.enter({}, {}, 'a'*64):self.fail('asserted success admitted')

    def test_actual_closed_sources_restoration_and_child_lease_transition_once(self):
        h,source,env,_=self.owned()
        with self.enter(source,env,h.sha) as owner:
            proof=owner.check();self.assertEqual(proof['worker_count'],12)
            self.assertEqual(len(proof['physical_cpus']),12)
            self.assertTrue(proof['source_descriptors_released']);self.assertFalse(proof['actual_analysis_performed'])
            self.assertFalse(owner.lease.identity_model.direct_children())
        with self.assertRaisesRegex(phase.resources.ResourceError,'closed'):owner.check()
        with self.assertRaisesRegex(phase.resources.ResourceError,'consumed'):
            with self.enter(source,env,h.sha):self.fail('retry')

    def test_live_source_bank_rejects_and_consumes_the_original_transition(self):
        h,source,env,_=self.owned(release=False)
        with self.assertRaisesRegex(phase.sources.SourcesError,'complete owned source release'):
            with self.enter(source,env,h.sha):self.fail('live source admitted')
        source._close()
        with self.assertRaisesRegex(phase.resources.ResourceError,'consumed'):
            with self.enter(source,env,h.sha):self.fail('failed phase retried')

    def test_source_alias_prevents_release_proof_even_after_original_fds_close(self):
        h,source,env,_=self.owned(release=False)
        alias=os.dup(next(iter(source._identity)));self.addCleanup(os.close,alias);source._close()
        with self.assertRaisesRegex(phase.sources.SourcesError,'descriptor alias'):
            with self.enter(source,env,h.sha):self.fail('source alias survived')

    def test_environment_must_have_actually_completed_owned_restoration(self):
        h,source,env,_=self.owned(restore=False)
        with self.assertRaisesRegex(phase.environment.EnvironmentError,'completed environment restoration'):
            with self.enter(source,env,h.sha):self.fail('unrestored environment')

    def test_reappearing_partition_latches_failure(self):
        h,source,env,_=self.owned()
        with self.enter(source,env,h.sha) as owner:
            h.cg.mkdir()
            with self.assertRaisesRegex(phase.environment.EnvironmentError,'partition remains'):owner.check()
            h.cg.rmdir()
            with self.assertRaisesRegex(phase.resources.ResourceError,'failed'):owner.check()

    def test_remaining_descendant_is_never_adopted_or_killed(self):
        h,source,env,_=self.owned()
        child=subprocess.Popen([sys.executable,'-B','-c','import os;os.read(0,1)'],stdin=subprocess.PIPE,start_new_session=True)
        try:
            with self.assertRaises(Exception):
                with self.enter(source,env,h.sha):self.fail('prior descendant admitted')
            self.assertIsNone(child.poll())
        finally:
            child.stdin.close();child.wait(timeout=5)

    def test_expiry_never_resets_or_revives_the_original_analysis_window(self):
        h,source,env,_=self.owned()
        with self.enter(source,env,h.sha) as owner:
            with mock.patch.object(phase.time,'monotonic_ns',return_value=owner.deadline_ns):
                with self.assertRaisesRegex(phase.resources.ResourceError,'deadline expired'):owner.check()
            with self.assertRaisesRegex(phase.resources.ResourceError,'failed'):owner.check()

    def test_actual_memory_failure_does_not_allow_an_automatic_second_claim(self):
        h,source,env,observed=self.owned();observed['memory_available_bytes']=1
        with self.assertRaisesRegex(phase.resources.ResourceError,'physical RAM'):
            with self.enter(source,env,h.sha):self.fail('insufficient physical memory')
        observed['memory_available_bytes']=256*phase.bounds.GIB
        with self.assertRaisesRegex(phase.resources.ResourceError,'consumed'):
            with self.enter(source,env,h.sha):self.fail('memory recovery silently retries')


if __name__=='__main__':unittest.main()
