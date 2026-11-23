"""D333 real lease/file I/O with explicit systemd/MSR/cgroup platform doubles."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_compaction_v1 as compaction
import stage17_s180_launcher_v1 as launcher
import test_stage17_s180_environment_v1 as hardware_tests
import s180_compaction_fixture


class CompactionTests(unittest.TestCase):
    def setUp(self):
        self.hardware=hardware_tests.EnvironmentTests();self.hardware.setUp()
        self.addCleanup(self.hardware.doCleanups)
        self.hardware.plan=compaction.monitored_plan(self.hardware.plan)
        self.hardware.sha=compaction.environment.planning.sha(self.hardware.plan)
        self.io=self.hardware.io();self.io.__enter__();self.addCleanup(self.io.close)
        self.environment=self.hardware.guard()

    def attach(self):
        return s180_compaction_fixture.attach(self,self.environment,self.hardware.root)

    def test_exact_approval_and_monitored_plan_preserve_all_scientific_inputs(self):
        self.assertEqual(compaction.approval(),compaction.APPROVAL_SHA)
        before=copy.deepcopy(self.hardware.plan);after=compaction.monitored_plan(before)
        self.assertEqual(before,after)
        self.assertEqual(len(after['captures']),180)
        after['captures'][0]['monitoring']['environment_sources'][-1]['byte_capacity']=64
        with self.assertRaises(compaction.CompactionError):compaction.require_monitored(after)

    def test_actual_durable_prestate_and_extended_lease_are_published_before_control_write(self):
        owned,control,_=self.attach()
        self.assertEqual(control.read_text().strip(),'0')
        owner=json.loads((compaction.ROOT/'owner.json').read_bytes())
        lease=json.loads(compaction.original.LEASE.read_bytes())
        self.assertEqual(lease['owner_sha256'],hashlib.sha256(owned.owner_raw).hexdigest())
        self.assertEqual(owner['plan_sha256'],self.hardware.sha)
        self.assertEqual(owned.guard.intent['observed_prestate'],1)
        self.assertIs(self.environment.compaction_guard(),owned)
        observed=self.environment.admission_observation(plan_sha256=self.hardware.sha)
        self.assertEqual(observed['compaction']['observed_value'],0)

    def test_normal_environment_restores_exact_sysctl_and_returns_version_two(self):
        owned,control,_=self.attach()
        result=self.hardware.restore(self.environment)
        self.assertEqual(result['schema_version'],'cpu-prefetch-stage17-s180-environment-restoration/2')
        self.assertTrue(result['compaction_restoration_verified']);self.assertEqual(result['errors'],[])
        self.assertEqual(control.read_text().strip(),'1');self.assertEqual(compaction.original.LEASE.read_bytes(),b'')
        self.assertTrue(owned.closed)

    def test_observed_zero_prestate_stays_zero_after_restoration(self):
        owned,control,_=s180_compaction_fixture.attach(self,self.environment,self.hardware.root,initial=0)
        self.assertEqual(owned.guard.intent['observed_prestate'],0)
        self.assertTrue(self.hardware.restore(self.environment)['compaction_restoration_verified'])
        self.assertEqual(control.read_text().strip(),'0')

    def test_failed_platform_restoration_keeps_control_and_lease_quarantined(self):
        owned,control,_=self.attach()
        error=dict(stage='hardware',cpu=8,error='independent original MSR readback failed')
        with mock.patch.object(self.environment,'_restore_hardware',return_value=([],[error])):
            result=self.hardware.restore(self.environment)
        self.assertFalse(result['hardware_restoration_verified'])
        self.assertFalse(result['compaction_restoration_verified'])
        self.assertIn(error,result['errors'])
        self.assertFalse(owned.closed)
        self.assertEqual(control.read_text().strip(),'0')
        self.assertTrue(compaction.original.LEASE.read_bytes())
        self.assertFalse((compaction.ROOT/'normal-platform.json').exists())

    def test_changed_control_latches_and_cannot_continue_after_it_recovers(self):
        owned,control,_=self.attach();control.write_text('1\n')
        with self.assertRaisesRegex(RuntimeError,'became enabled'):owned.check(boundary='AFTER_CAPTURE',ordinal=0)
        control.write_text('0\n')
        with self.assertRaisesRegex(compaction.CompactionError,'no automatic retry'):
            owned.check(boundary='BEFORE_RELEASE',ordinal=0)
        self.assertTrue((compaction.ROOT/'failure.json').exists())
        self.assertTrue(self.hardware.restore(self.environment)['compaction_restoration_verified'])

    def test_live_native_partition_prevents_compaction_restoration(self):
        owned,control,_=self.attach();(self.hardware.cg/'cgroup.procs').write_text('555\n')
        result=self.hardware.restore(self.environment)
        self.assertFalse(result['compaction_restoration_verified']);self.assertTrue(result['errors'])
        self.assertEqual(control.read_text().strip(),'0');self.assertTrue(compaction.original.LEASE.read_bytes())

    def test_owner_record_change_is_not_accepted_as_a_report(self):
        owned,control,_=self.attach();path=compaction.ROOT/'owner.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(compaction.CompactionError,'ownership/record'):
            owned.check(boundary='ADMISSION')
        self.assertEqual(control.read_text().strip(),'0')

    def test_expired_guard_does_not_renew_deadline_but_can_restore_after_quiescence(self):
        owned,control,_=self.attach();owned.guard.deadline_ns=time.monotonic_ns()-1
        with self.assertRaisesRegex(RuntimeError,'finite deadline expired'):owned.check(boundary='FINAL')
        self.assertEqual(owned.restore()['observed_value'],1)
        self.assertEqual(control.read_text().strip(),'1')

    def test_missing_supervision_or_monitored_input_blocks_before_control(self):
        with self.assertRaisesRegex(compaction.CompactionError,'actual environment and supervised'):
            compaction.prepare(environment_owner=self.environment,supervision={})
        self.assertFalse((self.hardware.root/'compaction').exists())

    def test_native_placement_and_capture_permission_are_not_issued_by_guard_preparation(self):
        owned,_,_=self.attach()
        self.assertFalse(self.environment._entry_used)
        result=owned.check(boundary='FAMILY_ENTRY')
        self.assertFalse(result['execution_authority']);self.assertEqual(result['requested_value'],0)

    def test_actual_script_hash_and_loaded_systemd_command_are_required(self):
        root=self.hardware.root;script=root/'verified-stop-post.py';script.write_bytes(compaction.stop_post_script());script.chmod(0o444)
        image=compaction.runtime.ImageBinding(script,script.stat().st_size,hashlib.sha256(script.read_bytes()).hexdigest())
        props=dict(MainPID=str(compaction.os.getpid()),ControlGroup='/'+compaction.UNIT,KillMode='control-group',
            SendSIGKILL='yes',NeedDaemonReload='no',ExecStopPost='{ argv[]='+str(compaction.PYTHON)+' -B '+str(script)+' ; }')
        with mock.patch.object(compaction,'RECOVERY_SCRIPT',script),mock.patch.object(compaction,'_unit',return_value=props), \
            mock.patch.object(compaction,'_membership',return_value='/'+compaction.UNIT):
            result=compaction.verify_supervision(recovery_script=image,deadline_ns=time.monotonic_ns()+10**9)
            result.check()
            props['ExecStopPost']='{ argv[]=/bin/true ; }'
            with self.assertRaisesRegex(compaction.CompactionError,'fixed loaded'):
                compaction.verify_supervision(recovery_script=image,deadline_ns=time.monotonic_ns()+10**9)
        script.chmod(0o644);script.write_text('changed')
        with self.assertRaisesRegex(compaction.CompactionError,'script bytes changed'):result.check()

    def test_wrong_process_or_cgroup_cannot_supply_supervision(self):
        owned,_,supervision=self.attach()
        with mock.patch.object(compaction,'RECOVERY_SCRIPT',supervision.script.path), \
            mock.patch.object(compaction,'_unit',return_value=dict(MainPID='99999')):
            with self.assertRaisesRegex(compaction.CompactionError,'supervised root'):
                compaction.verify_supervision(recovery_script=supervision.script,deadline_ns=time.monotonic_ns()+10**9)

    def test_live_owner_cannot_be_recovered_and_occupied_evidence_is_retained(self):
        owned,control,_=self.recovery_fixture();owned.guard.unlock()
        with self.assertRaisesRegex(compaction.CompactionError,'owner remains live'):
            compaction._recover(owned.owner,owned.owner_raw,deadline=time.monotonic_ns()+10**9)
        self.assertEqual(control.read_text().strip(),'0');self.assertTrue(compaction.original.LEASE.read_bytes())
        # Reacquire only for software fixture cleanup; no public adoption path.
        owned.guard.lock()

    def test_primary_guard_failure_survives_failure_receipt_io_error(self):
        owned,control,_=self.attach();control.write_text('1\n')
        with mock.patch.object(compaction,'_save',side_effect=OSError('software receipt disk full')):
            with self.assertRaisesRegex(RuntimeError,'became enabled'):owned.check(boundary='FINAL')
        self.assertTrue(owned.failed);self.assertIn('disk full',owned.failure_evidence_error)

    def test_production_restoration_cannot_pass_without_compaction_readback(self):
        with self.assertRaisesRegex(launcher.LaunchError,'independent environment restoration failed'):
            launcher._restore_result(self.environment,verified=self.hardware.verified(),
                cleanup=None,deadline_ns=self.hardware.window['end_monotonic_ns'])

    def test_wrong_worker_image_cannot_get_a_recovery_witness(self):
        owned,_,_=self.attach();process=subprocess.Popen(['/usr/bin/sleep','10'])
        worker=compaction.PinnedWorker(process.pid)
        try:
            with mock.patch.object(compaction,'_membership',return_value='/'+compaction.environment.UNIT+'/reserved'):
                with self.assertRaisesRegex(compaction.CompactionError,'image extent'):
                    owned.register_worker(worker,role='pilot')
            self.assertFalse((compaction.ROOT/'worker-pilot.json').exists())
        finally:process.terminate();process.wait();worker.close()

    def test_stop_post_restoration_requires_real_service_context(self):
        self.attach()
        with mock.patch.object(compaction,'_membership',return_value='/unrelated'):
            with self.assertRaisesRegex(compaction.CompactionError,'supervised recovery'):compaction.recover()

    def recovery_fixture(self):
        unit=self.hardware.root/'isolation-unit';unit.mkdir()
        moved=unit/'reserved';self.hardware.cg.rename(moved);self.hardware.cg=moved
        patch=mock.patch.object(compaction.environment,'CG',moved);patch.start();self.addCleanup(patch.stop)
        self.hardware.pre['partition_path']=str(moved)
        self.hardware.pre['operator_config']=dict(unit_name=compaction.environment.UNIT,
            evidence_root=str(compaction.environment.EVIDENCE))
        self.hardware.pre['prestate']['root']=dict(software_boundary=True)
        self.hardware.pre['prestate']['maintenance_before']={}
        self.hardware.core.configure=lambda pre:None
        self.hardware.core.root_state=lambda:dict(software_boundary=True)
        self.environment=self.hardware.guard()
        owned,control,_=self.attach()
        return owned,control,unit

    def dead_owner(self,owned):
        real=compaction._ticks
        def observed(pid):
            if pid==owned.owner['pid']:raise ProcessLookupError('software owner-death boundary')
            return real(pid)
        return mock.patch.object(compaction,'_ticks',side_effect=observed)

    def test_recovery_restores_hardware_then_control_after_verified_quiescence(self):
        owned,control,unit=self.recovery_fixture();owned.guard.unlock();shutil.rmtree(unit)
        self.hardware.set_value(8,15)
        core=self.hardware.core
        def restored(state):
            (core.Q/'restoration.json').write_text(json.dumps(dict(partition_absent=True,
                root_restoration_verified=True,maintenance_restoration_verified=True)))
        core.restore=restored
        with self.dead_owner(owned),mock.patch.object(compaction.environment,'_load_core',return_value=core):
            result=compaction._recover(owned.owner,owned.owner_raw,deadline=time.monotonic_ns()+30*10**9)
        self.assertTrue(result['verified']);self.assertEqual(self.hardware.value(8),0)
        self.assertEqual(control.read_text().strip(),'1');self.assertEqual(compaction.original.LEASE.read_bytes(),b'')
        self.assertTrue((compaction.ROOT/'recovery/completion.json').is_file())

    def test_normal_exit_stop_post_independently_confirms_completed_restoration_without_writes(self):
        owned,control,unit=self.recovery_fixture()
        self.assertTrue(self.hardware.restore(self.environment)['compaction_restoration_verified']);shutil.rmtree(unit)
        before=control.stat().st_mtime_ns
        with self.dead_owner(owned),mock.patch.object(compaction.environment,'_load_core',return_value=self.hardware.core):
            result=compaction._recover(owned.owner,owned.owner_raw,deadline=time.monotonic_ns()+30*10**9)
        self.assertTrue(result['verified']);self.assertEqual(control.stat().st_mtime_ns,before)
        self.assertEqual(compaction.original.LEASE.read_bytes(),b'')

    def test_unknown_live_task_is_quarantined_before_any_stop_or_control_write(self):
        owned,control,unit=self.recovery_fixture();owned.guard.unlock()
        (self.hardware.cg/'cgroup.procs').write_text('9999999\n')
        with self.dead_owner(owned),mock.patch.object(compaction.environment,'_load_core',return_value=self.hardware.core), \
            mock.patch.object(compaction,'_systemctl',side_effect=AssertionError('unknown tasks cannot be killed')):
            with self.assertRaisesRegex(compaction.CompactionError,'unknown live native'):
                compaction._recover(owned.owner,owned.owner_raw,deadline=time.monotonic_ns()+30*10**9)
        self.assertEqual(control.read_text().strip(),'0');self.assertTrue(compaction.original.LEASE.read_bytes())

    def test_foreign_recovery_lease_never_overwrites_a_control(self):
        owned,control,unit=self.recovery_fixture();owned.guard.unlock()
        lease=json.loads(compaction.original.LEASE.read_bytes());lease['owner_sha256']='f'*64
        compaction.original.LEASE.write_text(json.dumps(lease))
        with self.dead_owner(owned):
            with self.assertRaisesRegex(compaction.CompactionError,'foreign, partial or changed'):
                compaction._recover(owned.owner,owned.owner_raw,deadline=time.monotonic_ns()+30*10**9)
        self.assertEqual(control.read_text().strip(),'0');self.assertTrue(compaction.original.LEASE.read_bytes())


if __name__=='__main__':unittest.main()
