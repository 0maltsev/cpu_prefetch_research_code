"""Actual signatures/journal/ledger/epochs; explicit software science and OS seams."""
import argparse
import contextlib
import copy
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_exit_v1 as exit_check
import test_stage17_s180_execution_v1 as coordinator

execution=exit_check.execution


class ExitTests(unittest.TestCase):
    worker=None

    @classmethod
    def setUpClass(cls):
        coordinator.ExecutionTests.worker=cls.worker
        coordinator.ExecutionTests.setUpClass()

    def setUp(self):
        self.f=coordinator.ExecutionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.family=self.f.family
        self.resource_raw=execution.archive.canonical(dict(plan_sha256=self.family,execution_authority=False,phase18_authority=False))
        self.f.patch(execution.resources,'verify_resources',lambda **kw:SimpleNamespace(report=lambda:self.resource_raw))
        self.f.patch(execution.admission,'verify_plan',lambda **kw:SimpleNamespace(
            report=self.plan_report,payload=dict(plan_proof_sha256=hashlib.sha256(self.plan_report()).hexdigest())))
        old_semantic=self.f.semantic
        def semantic(input_id,payload,view,*,for_execution):
            old_payload={'SOFTWARE_PLAN':'only'} if input_id=='S17-EXT-008' else dict(
                resource_proof_sha256=hashlib.sha256(b'SOFTWARE-RESOURCE').hexdigest())
            return old_semantic(input_id,old_payload,view,for_execution=for_execution)
        self.semantic=semantic
        self.f.patch(execution.admission,'ScopedSemantics',lambda **kwargs:semantic)
        self.f.patch(execution.analysis,'analyze_family',self.analyze)
        self.unit_patch=self.f.stack.enter_context(mock.patch.object(exit_check,'_unit',return_value=dict(software_os_boundary=True)))
        self.env_patch=self.f.stack.enter_context(mock.patch.object(exit_check,'_environment',return_value=dict(software_os_boundary=True)))
        # The shared signing fixture uses disjoint synthetic monitoring paths;
        # the fixed stand plan validator is an explicit platform seam here.
        self.f.stack.enter_context(mock.patch.object(execution.environment,'_plan',autospec=True))

    def plan_report(self):
        context=self.semantic('S17-EXT-008',{},None,for_execution=False)
        return execution.archive.canonical(dict(plan_sha256=self.family,derived_scoped_context=context,
            execution_authority=False,phase18_authority=False))

    def analyze(self,**kwargs):
        # Explicit SOFTWARE validation report. Actual science/inverse workers
        # have separate integration tests; this tests post-service composition.
        self.f.event('analysis')
        artifacts=[];directory=self.f.program/'archives'
        for ordinal in range(180):
            for name in exit_check.checkpoint.capture_names(ordinal):
                identity=self.family+':'+name;archive_name=hashlib.sha256(identity.encode()).hexdigest()+'.cpfa'
                raw=b'SOFTWARE-ONLY';path=directory/archive_name;path.write_bytes(raw);path.chmod(0o600)
                artifacts.append(dict(artifact_id=identity,archive_name=archive_name,
                    physical=dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
        limits=execution.custody.CustodyLimits(131072,500000,500000,2*execution.MIB,time.monotonic_ns()+60*execution.NS)
        with execution.stores.ProgramStore(self.f.program,scope_sha256=self.f.plan['storage']['program_scope_sha256'],
                family_id=self.family,limits=limits,ext009_resolution_sha256=None) as store:
            epochs=execution.analysis._archive_snapshot(store,[dict(registry_proof=dict(artifacts=artifacts))])
            tip=asdict(store.ledger_binding())
        report=dict(schema_version=execution.analysis.SCHEMA,status='VALIDATED_DESCRIPTIVE_FAMILY_PENDING_OPERATIONAL_EXIT',
            plan_sha256=self.family,request_sha256=kwargs['verified_request'].request_sha256,
            archive_originals_inversely_verified=1440,actual_worker_completion_verified=True,
            original_archive_custody_verified=True,original_archive_epochs_unchanged_through_inverse=True,
            original_archive_epochs=epochs,original_ledger_tip=tip,family_data_consistency=dict(status='PASSED'),
            final_environment_observation=dict(software_os_boundary=True,window_binding=self.f.window),final_live_restoration_verified=True,
            original_generation_binding=self.f.source.released_proof(),
            operational_exit_verified=False,inferential_freeze_established=False,execution_authority=False,phase18_authority=False)
        out=self.root/'analysis';out.mkdir()
        bound=execution._bytes(out/'family-validation.json',execution.archive.canonical(report))
        return dict(report=report,binding={k:v for k,v in dict(bound,file_name='family-validation.json').items() if k!='path'})

    def run_controller(self):
        result=self.f.run_flow()
        self.f.stack.enter_context(mock.patch.object(execution.author,'ROOT',self.root/'source-author'))
        return result

    def observe(self):
        return exit_check._observe(self.f.base,self.f.inputs.operator_revision,self.f.inputs.operator_profile_sha256)

    def test_signed_historical_exit_verifies_originals_and_creates_no_new_attempt(self):
        self.run_controller();result=self.observe()
        self.assertEqual(result['report']['status'],'SCOPED_STAGE17_OPERATIONALLY_COMPLETE')
        self.assertEqual(result['report']['archive_epochs_verified_after_service_exit'],1440)
        self.assertFalse(result['report']['phase18_authority']);self.assertTrue(result['report']['observer_still_running'])
        self.assertFalse(result['report']['raw_inverse_repeated'])
        self.assertEqual(self.f.events.count('native'),1);self.assertEqual(self.f.events.count('source-start'),1)
        self.assertTrue((self.root/'scoped-stage17-exit.json.sig').is_file())
        with self.assertRaises(FileExistsError):self.observe()

    def test_same_bytes_rewritten_after_inverse_block_exit(self):
        self.run_controller();path=next((self.f.program/'archives').iterdir());path.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(execution.ExecutionError,'epoch'):self.observe()
        self.assertFalse((self.root/'scoped-stage17-exit.json').exists())

    def test_missing_archive_blocks_exit(self):
        self.run_controller();next((self.f.program/'archives').iterdir()).unlink()
        with self.assertRaises(FileNotFoundError):self.observe()
        self.assertFalse((self.root/'scoped-stage17-exit.json').exists())

    def test_changed_historical_plan_evidence_blocks_exit(self):
        self.run_controller();path=self.root/'qualified-plan-admission.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(execution.ExecutionError,'binding'):self.observe()

    def test_changed_source_plan_blocks_exit(self):
        self.run_controller();path=self.root/'source-author/plan.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(execution.ExecutionError,'binding'):self.observe()

    def test_failure_record_blocks_exit(self):
        self.run_controller();(self.root/'controller-failure.json').write_bytes(b'{}')
        with self.assertRaisesRegex(execution.ExecutionError,'controller failed'):self.observe()

    def test_changed_profile_blocks_exit(self):
        self.run_controller()
        with self.assertRaisesRegex(execution.ExecutionError,'profile'):
            exit_check._observe(self.f.base,self.f.inputs.operator_revision,'f'*64)

    def test_changed_signed_handoff_blocks_exit(self):
        self.run_controller();path=self.root/'controller-handoff.json';path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(Exception):self.observe()
        self.assertFalse((self.root/'scoped-stage17-exit.json').exists())

    def test_os_restoration_failure_blocks_publication(self):
        self.run_controller();self.env_patch.side_effect=ValueError('SOFTWARE changed MSR')
        with self.assertRaisesRegex(ValueError,'changed MSR'):self.observe()
        self.assertFalse((self.root/'scoped-stage17-exit.json').exists())

    def test_still_running_service_blocks_publication(self):
        self.run_controller();self.unit_patch.side_effect=ValueError('SOFTWARE service live')
        with self.assertRaisesRegex(ValueError,'service live'):self.observe()
        self.env_patch.assert_not_called()

    def test_public_api_rejects_serialized_original_owner(self):
        with self.assertRaisesRegex(execution.ExecutionError,'actual fresh original'):
            exit_check.observe(base_owner=dict(verified=True),operator_revision='e'*40,operator_profile_sha256='f'*64)
        self.assertFalse(self.root.exists())


class UnitTests(unittest.TestCase):
    def properties(self,**changes):
        command=' '.join((str(execution.compaction.PYTHON),'-B',str(execution.compaction.RECOVERY_SCRIPT)))
        props=dict(MainPID='0',ControlPID='0',ActiveState='inactive',SubState='dead',Result='success',
            ExecMainCode='1',ExecMainStatus='0',NeedDaemonReload='no',
            ExecStopPost='{ argv[]='+command+' ; code=exited ; status=0 ; }')
        props.update(changes);return '\n'.join(k+'='+v for k,v in props.items())

    def test_stopped_service_requires_actual_successful_stop_post(self):
        with mock.patch.object(execution.compaction,'_systemctl',return_value=self.properties()),mock.patch.object(
                exit_check.os.path,'lexists',return_value=False):
            self.assertEqual(exit_check._unit(time.monotonic_ns()+execution.NS)['MainPID'],'0')

    def test_live_failed_changed_stop_post_or_remaining_cgroup_rejected(self):
        for changes in (dict(MainPID='32'),dict(ControlPID='3'),dict(Result='exit-code'),dict(ExecMainStatus='1'),
                dict(ExecStopPost='unqualified'),dict(NeedDaemonReload='yes'),dict(ExecMainCode='0')):
            with self.subTest(changes=changes),mock.patch.object(execution.compaction,'_systemctl',return_value=self.properties(**changes)),mock.patch.object(
                    exit_check.os.path,'lexists',return_value=False):
                with self.assertRaises(execution.ExecutionError):exit_check._unit(time.monotonic_ns()+execution.NS)
        with mock.patch.object(execution.compaction,'_systemctl',return_value=self.properties()),mock.patch.object(
                exit_check.os.path,'lexists',return_value=True):
            with self.assertRaisesRegex(execution.ExecutionError,'cgroup'):exit_check._unit(time.monotonic_ns()+execution.NS)


class RestorationTests(unittest.TestCase):
    """Real guard receipts/lease/MSR-shaped files, explicit synthetic OS reads."""
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        temporary=self.stack.enter_context(tempfile.TemporaryDirectory(prefix='s180-exit-restoration-',
            dir=Path(__file__).resolve().parents[1]/'build'))
        self.root=Path(temporary);compaction=execution.compaction;env=execution.environment
        self.stack.enter_context(mock.patch.object(compaction,'ROOT',self.root/'compaction'))
        compaction.ROOT.mkdir();(compaction.ROOT/'guard').mkdir()
        self.lease=self.root/'lease';self.lease.write_bytes(b'');self.lease.chmod(0o600)
        self.stack.enter_context(mock.patch.object(compaction.original,'LEASE',self.lease))
        control=self.root/'sysctl';control.write_text('1\n')
        self.stack.enter_context(mock.patch.object(compaction.original,'CONTROL',control));self.control=control
        self.stack.enter_context(mock.patch.object(env,'CG',self.root/'absent-recovery/reserved'))
        self.devices={};self.plan=dict(hardware=dict(prestate=[dict(cpu=cpu,value=cpu+20) for cpu in (0,1,8)]))
        for row in self.plan['hardware']['prestate']:
            path=self.root/('msr-'+str(row['cpu']));path.write_bytes(b'\0'*env.MSR+row['value'].to_bytes(8,'little'))
            s=path.stat();self.devices[str(row['cpu'])]=[s.st_dev,s.st_ino,s.st_rdev]
        def open_msr(cpu):return os.open(self.root/('msr-'+str(cpu)),os.O_RDONLY),tuple(self.devices[str(cpu)])
        self.stack.enter_context(mock.patch.object(env,'_open_msr',side_effect=open_msr))
        self.maintenance=dict(ActiveState='active',SubState='waiting',UnitFileState='enabled')
        self.core=SimpleNamespace(root_state=lambda:dict(software_root='original'),TIMER_SERVICES={'a.timer':'a.service'})
        self.core.systemd_state=lambda name:dict(line.split('=',1) for line in self.core.command('systemctl','show',name).splitlines())
        self.stack.enter_context(mock.patch.object(env,'_load_core',return_value=self.core))
        self.systemctl=self.stack.enter_context(mock.patch.object(compaction,'_systemctl',side_effect=self.systemctl_read))
        owner=dict(plan=self.plan,window={'software_window':True},devices=self.devices,
            preparation=dict(prestate=dict(root=dict(software_root='original'))))
        owner_raw=execution.archive.canonical(owner)
        execution._bytes(compaction.ROOT/'owner.json',owner_raw)
        intent=dict(observed_prestate=1);intent_raw=compaction.original.canonical(intent)
        execution._bytes(compaction.ROOT/'guard/intent.json',intent_raw)
        execution._bytes(compaction.ROOT/'guard/restoration.json',compaction.original.canonical(dict(verified=True,
            intent_sha256=hashlib.sha256(intent_raw).hexdigest(),requested_value=1,observed_value=1)))
        s=self.lease.stat()
        self.expected=dict(plan_sha256='f'*64,hardware_restoration_verified=True,cpu_isolation_restoration_verified=True,
            maintenance_restoration_verified=True,compaction_restoration_verified=True,root=dict(software_root='original'),
            maintenance={'a.timer':copy.deepcopy(self.maintenance)},window_binding=owner['window'],
            recovery_service=dict(ActiveState='inactive',SubState='dead',MainPID='0'),
            compaction=dict(owner_sha256=hashlib.sha256(owner_raw).hexdigest(),original_value=1,
                lease_identity=[s.st_dev,s.st_ino]))
        self.report=dict(plan_sha256='f'*64,final_environment_observation=self.expected)

    def systemctl_read(self,*args,deadline):
        self.assertEqual(args[0],'show')
        values=self.maintenance if args[1]=='a.timer' else dict(ActiveState='inactive',SubState='dead',MainPID='0')
        return '\n'.join(key+'='+value for key,value in values.items())

    def observe(self):return exit_check._environment(self.plan,self.report,time.monotonic_ns()+10*execution.NS)

    def test_actual_unchanged_receipts_lease_and_values_are_only_read(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        result=self.observe();self.assertTrue(result['read_only'])
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertGreater(self.systemctl.call_count,0)

    def test_changed_msr_value_blocks_exit_without_repair(self):
        path=self.root/'msr-8';path.write_bytes(b'\0'*execution.environment.MSR+b'\0'*8)
        with self.assertRaisesRegex(execution.ExecutionError,'restored MSR'):self.observe()
        self.assertEqual(int.from_bytes(path.read_bytes()[-8:],'little'),0)

    def test_occupied_or_replaced_lease_blocks_exit_without_clear(self):
        self.lease.write_bytes(b'new owner')
        with self.assertRaisesRegex(execution.ExecutionError,'lease occupied'):self.observe()
        self.assertEqual(self.lease.read_bytes(),b'new owner')
        self.lease.unlink();self.lease.write_bytes(b'')
        # Explicitly use a different inode even on a filesystem reusing the old.
        self.expected['compaction']['lease_identity'][1]+=1
        with self.assertRaisesRegex(execution.ExecutionError,'lease'):self.observe()

    def test_changed_control_or_maintenance_blocks_exit_without_repair(self):
        self.control.write_text('0\n')
        with self.assertRaisesRegex(execution.ExecutionError,'compaction control'):self.observe()
        self.assertEqual(self.control.read_text(),'0\n')
        self.control.write_text('1\n');self.maintenance['UnitFileState']='disabled'
        with self.assertRaisesRegex(execution.ExecutionError,'maintenance'):self.observe()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',type=Path,required=True);args,rest=p.parse_known_args()
    ExitTests.worker=args.worker.resolve();unittest.main(argv=[sys.argv[0],*rest])
