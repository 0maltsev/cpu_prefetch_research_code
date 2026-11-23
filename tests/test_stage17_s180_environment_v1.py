"""Stand environment adapter with explicit software-only platform doubles.

Actual temporary files exercise fixed-offset MSR I/O and failure retention.
Character-device/CPU identity and systemd/cgroup actions are test doubles;
these results do not qualify hardware or mutate the host/stand environment.
The preserved isolation source itself is hash checked and loaded unchanged.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_environment_v1 as env
import stage17_s180_authority_v1 as authority
from test_stage17_s180_plan_prepare_v1 import fixture


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='s180-environment-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.cg=self.root/'reserved';self.cg.mkdir()
        (self.cg/'cgroup.procs').write_text('');(self.cg/'cgroup.events').write_text('populated 0\n')
        self.plan=fixture(env.NATIVE_REVISION);self.plan['schema_version']=env.planning.PLAN
        del self.plan['source_count_basis']
        for row in self.plan['captures']:
            row['monitoring']['environment_sources']=[dict(path=str(env.CG/name)) for name in
                ('cpuset.cpus','cpuset.cpus.effective','cpuset.cpus.exclusive','cpuset.cpus.partition','cpuset.mems.effective')]
        now=time.monotonic_ns();self.window=dict(boot_id=env._boot(),start_monotonic_ns=now,end_monotonic_ns=now+env.planning.DAY_NS)
        self.sha=env.planning.sha(self.plan);self.restores=[];self.retained=[];self.prepared=0
        self.files={};self.devices={}
        for cpu in env.CPUS:
            path=self.root/f'msr-{cpu}';path.write_bytes(bytes(env.MSR)+bytes(8));self.files[cpu]=path
            st=path.stat();self.devices[cpu]=(st.st_dev,st.st_ino,st.st_rdev)
        st=self.cg.stat()
        self.pre=dict(partition_path=str(env.CG),prestate=dict(partition_identity=[st.st_dev,st.st_ino]))
        self.core=SimpleNamespace(Q=self.root,read=lambda p:Path(p).read_text().strip(),
            identity=lambda p:[Path(p).stat().st_dev,Path(p).stat().st_ino],isolated_state=lambda:{},
            verify_remaining_lifetime=lambda *args:None,restore=self.restore_core,retain=self.retain)
        self.affinity=set(os.sched_getaffinity(0))

    def retain(self,path,value):
        self.retained.append((str(path),value));Path(path).write_text(json.dumps(value))

    def restore_core(self,state):
        self.restores.append(state)
        (self.root/'restoration.json').write_text(json.dumps(dict(partition_absent=True,
            root_restoration_verified=True,maintenance_restoration_verified=True)))

    def guard(self):
        return env._PreparedEnvironment(token=env._TOKEN,plan=self.plan,window=self.window,
            core=self.core,preparation=self.pre,devices=self.devices,affinity=self.affinity,
            command_state=dict(deadline=self.window['end_monotonic_ns']))

    def io(self):
        stack=env.contextlib.ExitStack();real_open=os.open
        def opened(path,flags,*args,**kwargs):
            for cpu in env.CPUS:
                if str(path)==f'/dev/cpu/{cpu}/msr':return real_open(self.files[cpu],flags,*args,**kwargs)
            return real_open(path,flags,*args,**kwargs)
        stack.enter_context(mock.patch.object(env,'CG',self.cg))
        stack.enter_context(mock.patch.object(env,'_cpu_identity',return_value=None))
        stack.enter_context(mock.patch.object(env.os,'open',side_effect=opened))
        stack.enter_context(mock.patch.object(env.stat,'S_ISCHR',return_value=True))
        return stack

    def verified(self,**changes):
        authorization=dict(plan_sha256=self.sha,window_binding=self.window);authorization.update(changes)
        return authority.VerifiedRequest(env.archive.canonical(authorization),b'{}')

    def restore(self,guard,**changes):
        args=dict(verified=self.verified(),native_cleanup=SimpleNamespace(leader_reaped=True,process_group_gone=True),
            deadline_ns=self.window['end_monotonic_ns']);args.update(changes)
        return guard(**args)

    def value(self,cpu):
        with self.files[cpu].open('rb') as stream:stream.seek(env.MSR);return int.from_bytes(stream.read(8),'little')

    def set_value(self,cpu,value):
        with self.files[cpu].open('r+b') as stream:stream.seek(env.MSR);stream.write(value.to_bytes(8,'little'))

    def test_frozen_core_is_exact_original_source_with_no_import_actions(self):
        core=env._load_core()
        raw=Path(core.__file__).read_bytes()
        self.assertEqual(len(raw),23863);self.assertEqual(hashlib.sha256(raw).hexdigest(),env.CORE_SHA)
        self.assertIsNone(core.CONFIG);self.assertIsNone(core.CG)
        self.assertEqual(core.RESERVED,frozenset((0,1,2,8,16,17,18,24)))

    def test_prospective_config_uses_managed_unit_and_cannot_extend_window(self):
        c=env.prospective_config(plan=self.plan,window=self.window,operator_revision='1'*40)
        self.assertEqual(c['unit_name'],env.UNIT);self.assertEqual(c['evidence_root'],str(env.EVIDENCE))
        self.assertLess(c['lifecycle_seconds']*10**9+env.ISOLATION_PREPARATION_NS,
            self.window['end_monotonic_ns']-time.monotonic_ns())
        self.assertGreater(c['protected_work_ns'],0)

    def test_legacy_cpu_mapping_and_provisional_cgroup_paths_reject_before_actions(self):
        for change in (lambda p:p['hardware'].update(identity=dict(family=6,model=85)),
            lambda p:p['hardware']['prestate'][2].update(cpu=26),
            lambda p:p['captures'][0]['monitoring']['environment_sources'][0].update(path='/sys/fs/cgroup/cpu-prefetch-stage17-s180/reserved/cpuset.cpus')):
            p=copy.deepcopy(self.plan);change(p)
            with self.assertRaises(env.EnvironmentError):env._plan(p)

    def test_real_fixed_offset_restore_changes_only_expected_cpu_values(self):
        for cpu in env.CPUS:self.set_value(cpu,15)
        with self.io():
            guard=self.guard();result=self.restore(guard)
            self.assertTrue(result['hardware_restoration_verified']);self.assertEqual(result['errors'],[])
            self.assertTrue(result['cpu_isolation_restoration_verified'] and result['maintenance_restoration_verified'])
            self.assertEqual([self.value(cpu) for cpu in env.CPUS],[0,0,0])
            self.assertEqual(len(self.restores),1)
            with self.assertRaisesRegex(env.EnvironmentError,'closed'):self.restore(guard)
        self.assertTrue((self.root/'s180-restoration.json').is_file())

    def test_already_restored_hardware_is_read_only(self):
        with self.io(),mock.patch.object(env.os,'pwrite',side_effect=AssertionError('no unnecessary hardware write')):
            result=self.restore(self.guard())
        self.assertTrue(result['hardware_restoration_verified'])

    def test_admission_observes_actual_prestate_without_placement_or_writes(self):
        with self.io(),mock.patch.object(env.os,'pwrite',side_effect=AssertionError('admission is read-only')):
            guard=self.guard();observed=guard.admission_observation(plan_sha256=self.sha)
            self.assertEqual(observed['hardware_readbacks'],[dict(cpu=c,observed_value=0) for c in env.CPUS])
            self.assertFalse(observed['native_placement_performed']);self.assertFalse(guard._entry_used)
            self.set_value(8,15)
            with self.assertRaisesRegex(env.EnvironmentError,'prestate/device changed'):
                guard.admission_observation(plan_sha256=self.sha)
            self.assertEqual(self.value(8),15)

    def test_admission_rejects_live_or_replaced_partition(self):
        with self.io():
            guard=self.guard();(self.cg/'cgroup.procs').write_text('555\n')
            with self.assertRaisesRegex(env.EnvironmentError,'empty owned partition'):
                guard.admission_observation(plan_sha256=self.sha)

    def test_unrelated_msr_bits_are_not_overwritten_and_other_cpus_restore(self):
        for cpu in env.CPUS:self.set_value(cpu,15)
        self.set_value(8,(1<<20)|15)
        with self.io():result=self.restore(self.guard())
        self.assertFalse(result['hardware_restoration_verified']);self.assertTrue(result['errors'])
        self.assertEqual(self.value(8),(1<<20)|15)
        self.assertEqual([self.value(0),self.value(1)],[0,0])
        self.assertEqual(len(self.restores),1)

    def test_one_device_failure_does_not_skip_other_cpus_or_environment(self):
        for cpu in env.CPUS:self.set_value(cpu,15)
        real=env._open_msr
        def fail(cpu,*args):
            if cpu==8:raise OSError('software device failure')
            return real(cpu,*args)
        with self.io(),mock.patch.object(env,'_open_msr',side_effect=fail):result=self.restore(self.guard())
        self.assertFalse(result['hardware_restoration_verified']);self.assertEqual(self.value(8),15)
        self.assertEqual([self.value(0),self.value(1)],[0,0]);self.assertEqual(len(self.restores),1)

    def test_live_cgroup_blocks_hardware_writes(self):
        (self.cg/'cgroup.procs').write_text('555\n')
        with self.io(),mock.patch.object(env.os,'pwrite',side_effect=AssertionError('no write while native live')):
            result=self.restore(self.guard())
        self.assertFalse(result['hardware_restoration_verified']);self.assertTrue(result['errors'])

    def test_wrong_plan_window_and_unreaped_process_cannot_restore(self):
        with self.io():
            guard=self.guard()
            for changes in (dict(verified=self.verified(plan_sha256='f'*64)),
                dict(deadline_ns=self.window['end_monotonic_ns']+1),
                dict(native_cleanup=SimpleNamespace(leader_reaped=False,process_group_gone=False))):
                with self.assertRaises(env.EnvironmentError):self.restore(guard,**changes)
        self.assertEqual(self.restores,[])

    def test_context_exit_restores_before_authorization_and_cannot_be_reused(self):
        with self.io():
            guard=self.guard()
            with self.assertRaisesRegex(ValueError,'body failure'):
                with guard:raise ValueError('body failure')
            self.assertEqual(len(self.restores),1)
            with self.assertRaisesRegex(env.EnvironmentError,'closed'):guard.__enter__()

    def test_native_handoff_is_single_use_and_closes_control_before_removal(self):
        with self.io():
            guard=self.guard()
            with guard.native_entry(plan_sha256=self.sha) as entry:
                fd=entry['descriptor'];self.assertEqual(entry['controller_cpu'],2)
                self.assertEqual(entry['relative_path'],'/'+env.UNIT+'/reserved')
                self.assertEqual(os.fstat(fd).st_ino,(self.cg/'cgroup.procs').stat().st_ino)
                self.restore(guard)
                with self.assertRaises(OSError):os.fstat(fd)
            with self.assertRaises(env.EnvironmentError):guard.native_entry(plan_sha256=self.sha).__enter__()

    def test_serialized_report_cannot_construct_handle(self):
        with self.assertRaises(env.EnvironmentError):
            env._PreparedEnvironment(token=object(),plan=self.plan,window=self.window,core=self.core,
                preparation=self.pre,devices=self.devices,affinity=self.affinity,command_state={})

    def factory(self,*,overrun=False):
        plan=copy.deepcopy(self.plan)
        for row in plan['captures']:
            for source in row['monitoring']['environment_sources']:
                source['path']=str(self.cg/Path(source['path']).name)
        with mock.patch.object(env,'CG',self.cg):
            config=env.prospective_config(plan=plan,window=self.window,operator_revision='1'*40)
        def prepare(config):
            pre=copy.deepcopy(self.pre)
            pre['partition_path']=str(self.cg)
            pre['prestate']['keeper_deadline_monotonic_ns']=self.window['end_monotonic_ns']+(1 if overrun else -1)
            return pre
        self.core.prepare=prepare
        with self.io(),mock.patch.object(env,'_load_core',return_value=self.core):
            return env.prepare_environment(plan=plan,window=self.window,operator_config=config)

    def test_preparation_factory_pins_actual_msr_prestate_before_actions(self):
        guard=self.factory()
        self.assertEqual(guard._devices,self.devices)
        self.assertFalse(guard._closed)

    def test_post_prepare_keeper_overrun_rolls_back_environment_and_affinity(self):
        before=set(os.sched_getaffinity(0))
        with self.assertRaisesRegex(env.EnvironmentError,'exceeds original window'):self.factory(overrun=True)
        self.assertEqual(len(self.restores),1)
        self.assertEqual(set(os.sched_getaffinity(0)),before)

    def test_expired_preparation_allows_core_internal_restoration_commands(self):
        plan=copy.deepcopy(self.plan)
        for row in plan['captures']:
            for source in row['monitoring']['environment_sources']:
                source['path']=str(self.cg/Path(source['path']).name)
        clock=[time.monotonic_ns()]
        def prepare(config):
            clock[0]+=121*10**9
            self.core.restore(self.pre['prestate'])
            raise TimeoutError('preparation deadline exhausted')
        def restore(state):
            self.core.command('systemctl','daemon-reload')
            self.restore_core(state)
        self.core.prepare=prepare;self.core.restore=restore
        with self.io(),mock.patch.object(env,'_load_core',return_value=self.core), \
            mock.patch.object(env.time,'monotonic_ns',side_effect=lambda:clock[0]), \
            mock.patch.object(env.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')) as command:
            config=env.prospective_config(plan=plan,window=self.window,operator_revision='1'*40)
            with self.assertRaisesRegex(TimeoutError,'deadline exhausted'):
                env.prepare_environment(plan=plan,window=self.window,operator_config=config)
            self.assertEqual(command.call_count,1)
            self.assertGreater(command.call_args.kwargs['timeout'],0)
            self.assertLessEqual(command.call_args.kwargs['timeout'],120)
        self.assertEqual(len(self.restores),1)

    def test_expired_window_blocks_entry_but_still_unwinds_without_extending_authority(self):
        for cpu in env.CPUS:self.set_value(cpu,15)
        with self.io(),mock.patch.object(env.time,'monotonic_ns',return_value=self.window['end_monotonic_ns']+1):
            guard=self.guard()
            with self.assertRaises(env.EnvironmentError):guard.native_entry(plan_sha256=self.sha).__enter__()
            result=self.restore(guard)
        self.assertTrue(result['hardware_restoration_verified'])
        self.assertTrue(result['errors']);self.assertEqual(self.value(0),0)
        record=json.loads((self.root/'s180-restoration.json').read_bytes())
        self.assertTrue(record['operational_deadline_overrun']);self.assertFalse(record['collection_authority_extended'])
        self.assertEqual(record['window_binding'],self.window)


if __name__=='__main__':unittest.main()
