"""Actual lease/MSR file reads; explicit systemd/cgroup/CPU test doubles.

No host hardware is qualified or mutated. This exercises the post-analysis
boundary after the original owned restoration, without replaying that restore.
"""
import copy
import fcntl
import os
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_compaction_v1 as compaction
import test_stage17_s180_environment_v1 as fixtures
import s180_compaction_fixture

env=compaction.environment


class FinalEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.EnvironmentTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.cg=self.f.root/'owned-recovery.service'/'reserved';self.f.cg.mkdir(parents=True)
        (self.f.cg/'cgroup.procs').write_text('');(self.f.cg/'cgroup.events').write_text('populated 0\n')
        st=self.f.cg.stat();self.f.pre['prestate']['partition_identity']=[st.st_dev,st.st_ino]
        self.f.plan=compaction.monitored_plan(self.f.plan);self.f.sha=env.planning.sha(self.f.plan)
        self.root_before={'cgroup.controllers':'cpu cpuset','cgroup.subtree_control':'cpu',
            'cpuset.cpus.effective':'0-31','cpuset.mems.effective':'0-1','cpuset.cpus.isolated':''}
        self.maintenance={name:dict(ActiveState='active' if name.endswith('.timer') else 'inactive',
            SubState='waiting' if name.endswith('.timer') else 'dead',UnitFileState='enabled')
            for name in ('apt-daily.timer','apt-daily-upgrade.timer','apt-daily.service','apt-daily-upgrade.service')}
        self.f.pre['prestate'].update(root=copy.deepcopy(self.root_before),maintenance_before=copy.deepcopy(self.maintenance))
        self.f.core.root_state=lambda:copy.deepcopy(self.root_before)
        self.f.core.TIMER_SERVICES={'apt-daily.timer':'apt-daily.service','apt-daily-upgrade.timer':'apt-daily-upgrade.service'}
        self.f.core.systemd_state=lambda name:copy.deepcopy(self.maintenance[name])
        self.unit=dict(ActiveState='inactive',SubState='dead',MainPID='0');self.commands=[]
        def command(*args):
            self.commands.append(args)
            self.assertEqual(args,('systemctl','show',env.UNIT,'--property=ActiveState','--property=SubState','--property=MainPID'))
            return '\n'.join(k+'='+v for k,v in self.unit.items())
        self.f.core.command=command
        stack=self.f.io();stack.__enter__();self.addCleanup(stack.close)
        self.owner=self.f.guard()

    def restored(self,initial=1):
        owned,control,_=s180_compaction_fixture.attach(self,self.owner,self.f.root,initial=initial)
        self.assertEqual(self.f.restore(self.owner)['errors'],[])
        for p in self.f.cg.iterdir():p.unlink()
        self.f.cg.rmdir();self.f.cg.parent.rmdir()
        return owned,control

    def observe(self):return self.owner.final_restoration_observation(
        plan_sha256=self.f.sha,deadline_ns=self.f.window['end_monotonic_ns'])

    def test_fresh_readback_preserves_original_one_prestate_without_any_repairs(self):
        owned,control=self.restored();before={p:p.read_bytes() for p in self.f.root.rglob('*') if p.is_file()}
        prior=self.owner._command_state['deadline']
        with mock.patch.object(env.os,'pwrite',side_effect=AssertionError('final check must not repair')):
            value=self.observe()
        self.assertEqual(value['hardware_readbacks'],[dict(cpu=c,expected_value=0,observed_value=0) for c in env.CPUS])
        self.assertEqual(value['compaction']['observed_value'],1);self.assertTrue(value['owned_children_absent'])
        self.assertTrue(value['read_only']);self.assertFalse(value['operational_exit_verified'])
        self.assertFalse(value['phase18_authority']);self.assertEqual(len(self.f.restores),1)
        self.assertEqual(before,{p:p.read_bytes() for p in before});self.assertEqual(control.read_text(),'1\n')
        self.assertIsNone(owned.guard.fd);self.assertEqual(self.owner._command_state['deadline'],prior)
        with self.assertRaisesRegex(env.EnvironmentError,'already consumed'):self.observe()

    def test_zero_prestate_remains_zero_at_final_readback(self):
        self.restored(initial=0)
        self.assertEqual(self.observe()['compaction']['observed_value'],0)

    def test_changed_complete_msr_value_is_retained_and_failed_check_cannot_retry(self):
        self.restored();self.f.set_value(8,1<<20)
        with self.assertRaisesRegex(env.EnvironmentError,'MSR value/device changed'):self.observe()
        self.assertEqual(self.f.value(8),1<<20);self.f.set_value(8,0)
        with self.assertRaisesRegex(env.EnvironmentError,'already consumed'):self.observe()
        self.assertEqual(len(self.f.restores),1)

    def test_changed_cpu_root_state_rejects_prior_success(self):
        self.restored();self.root_before['cpuset.cpus.isolated']='0-2'
        with self.assertRaisesRegex(env.EnvironmentError,'CPU root state changed'):self.observe()

    def test_changed_maintenance_enablement_and_timer_activity_reject(self):
        self.restored();self.maintenance['apt-daily.timer']['ActiveState']='inactive'
        with self.assertRaisesRegex(env.EnvironmentError,'maintenance state changed'):self.observe()

    def test_new_recovery_partition_is_never_removed_by_readback(self):
        self.restored();self.f.cg.mkdir(parents=True)
        with self.assertRaisesRegex(env.EnvironmentError,'partition remains'):self.observe()
        self.assertTrue(self.f.cg.exists())

    def test_failed_recovery_service_is_not_treated_as_quiescent_success(self):
        self.restored();self.unit['ActiveState']='failed'
        with self.assertRaisesRegex(env.EnvironmentError,'service remains live or failed'):self.observe()

    def test_changed_compaction_control_is_not_repaired(self):
        _,control=self.restored();control.write_text('0\n')
        with self.assertRaisesRegex(compaction.CompactionError,'compaction value changed'):self.observe()
        self.assertEqual(control.read_text(),'0\n');self.assertEqual(compaction.original.LEASE.read_bytes(),b'')

    def test_reoccupied_or_replaced_lease_cannot_use_old_restoration(self):
        owned,_=self.restored();lease=compaction.original.LEASE;lease.write_bytes(b'foreign')
        with self.assertRaisesRegex(compaction.CompactionError,'replaced or occupied'):owned.restored_observation()
        lease.unlink();lease.write_bytes(b'')
        with self.assertRaisesRegex(compaction.CompactionError,'replaced or occupied'):owned.restored_observation()

    def test_exclusive_new_lease_holder_blocks_read_only_check(self):
        owned,_=self.restored();fd=os.open(compaction.original.LEASE,os.O_RDWR)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):owned.restored_observation()
        finally:os.close(fd)

    def test_changed_durable_restoration_receipt_rejects_current_control(self):
        owned,_=self.restored();path=owned.guard.root/'restoration.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(compaction.CompactionError,'restoration receipt changed'):self.observe()

    def test_original_window_expiry_cannot_grant_a_new_final_check_window(self):
        self.restored()
        with mock.patch.object(env.time,'monotonic_ns',return_value=self.f.window['end_monotonic_ns']):
            with self.assertRaisesRegex(env.EnvironmentError,'window/boot differs'):self.observe()

    def test_final_check_cannot_extend_the_caller_analysis_deadline(self):
        self.restored();before=time.monotonic_ns()
        value=self.owner.final_restoration_observation(plan_sha256=self.f.sha,deadline_ns=before+10**9)
        self.assertEqual(value['deadline_monotonic_ns'],before+10**9)

    def test_expired_analysis_deadline_blocks_before_systemd_queries(self):
        self.restored()
        with self.assertRaisesRegex(env.EnvironmentError,'deadline expired'):
            self.owner.final_restoration_observation(plan_sha256=self.f.sha,deadline_ns=time.monotonic_ns()-1)
        self.assertEqual(self.commands,[])

    def test_live_child_blocks_final_readback_before_systemd_queries(self):
        self.restored();pid=os.fork()
        if pid==0:
            try:time.sleep(10)
            finally:os._exit(0)
        try:
            with self.assertRaisesRegex(env.EnvironmentError,'descendants remain'):self.observe()
            self.assertEqual(self.commands,[])
        finally:os.kill(pid,9);os.waitpid(pid,0)


if __name__=='__main__':unittest.main()
