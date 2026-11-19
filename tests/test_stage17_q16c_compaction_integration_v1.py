"""Real lease/FD/transport boundaries plus private-runner ordering checks."""
import contextlib
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_archive_channel_v1 as channel
import stage17_fixed_action_executor_v12 as executor
import stage17_locked_compaction_guard_v1 as control_guard
import stage17_q16c_compaction_integration_v1 as integration
import stage17_q16c_source_execution_v1 as source_execution
import test_stage17_archive_channel_v1 as transport_tests


class Control:
    def __init__(self):
        self.value, self.boot_id = 1, 'software-test-boot'

    def boot(self):
        return self.boot_id

    def read(self):
        return self.value

    def write(self, value):
        self.value = value


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.control = Control()
        self.guard = control_guard.Guard(self.root / 'guard', control=self.control,
            lease=self.root / 'lease', deadline_ns=time.monotonic_ns() + 10 * 10**9)
        self.guard.__enter__()
        self.addCleanup(self.restore)
        self.description, self.fd = integration.export_witness(self.guard)
        self.addCleanup(os.close, self.fd)
        self.witness = integration.ReadOnlyWitness(self.description, self.fd, control=self.control)

    def restore(self):
        if self.guard.fd is not None:
            self.guard.__exit__(None, None, None)

    def observations(self, count=2, name='observations'):
        return integration.Observations(self.witness, self.root / name,
            request_sha256='a'*64, plan_sha256='b'*64, capture_count=count)

    def test_readonly_witness_is_separate_and_cannot_write_or_release_root_lock(self):
        self.assertEqual(fcntl.fcntl(self.fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
        with self.assertRaises(OSError):
            os.write(self.fd, b'overwrite')
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        self.assertTrue(self.witness.verify()['verified'])
        self.assertTrue(integration.locked_elsewhere(self.fd))
        with self.assertRaisesRegex(RuntimeError, 'read-only'):
            integration.ReadOnlyWitness(self.description, self.guard.fd, control=self.control)

    def test_witness_rejects_changed_lease_boot_process_and_deadline(self):
        with patch.object(integration, 'process_identity', return_value=self.description['supervisor_start_ticks']+1):
            with self.assertRaisesRegex(RuntimeError, 'identity changed'):
                self.witness.verify()
        self.control.boot_id = 'other-boot'
        with self.assertRaisesRegex(RuntimeError, 'boot changed'):
            self.witness.verify()
        self.control.boot_id = 'software-test-boot'
        with patch.object(integration.time, 'monotonic_ns', return_value=self.description['deadline_monotonic_ns']):
            with self.assertRaisesRegex(RuntimeError, 'deadline expired'):
                self.witness.verify()
        original = os.pread(self.guard.fd, 4096, 0)
        os.pwrite(self.guard.fd, b'X', 0)
        with self.assertRaisesRegex(RuntimeError, 'cleared or changed'):
            self.witness.verify()
        os.pwrite(self.guard.fd, original, 0)

    def test_lost_root_lock_is_detected_even_when_control_stays_zero(self):
        self.guard.unlock()
        self.assertEqual(self.control.value, 0)
        with self.assertRaisesRegex(RuntimeError, 'exclusive root lease'):
            self.witness.verify()
        control_guard.recover(self.root / 'guard', control=self.control, lease=self.root / 'lease')
        self.assertEqual(self.control.value, 1)

    def test_witness_export_requires_original_guard_owner(self):
        original = self.guard.intent['supervisor_pid']
        self.guard.intent['supervisor_pid'] += 1
        try:
            with self.assertRaisesRegex(RuntimeError, 'guard owner'):
                integration.export_witness(self.guard)
        finally:
            self.guard.intent['supervisor_pid'] = original

    def test_complete_observations_bind_request_plan_checkpoint_and_actual_state(self):
        observations = self.observations(1)
        checkpoint = dict(file_name='checkpoint.json', size_bytes=1, sha256='c'*64)
        observations.before_capture(0)
        observations.after_capture(0, checkpoint)
        observations.complete()
        reports = [json.loads(p.read_bytes()) for p in observations.root.iterdir()]
        self.assertEqual(len(reports), 2)
        self.assertEqual({r['moment'] for r in reports}, {'before-native-authorization','after-native-checkpoint'})
        for report in reports:
            self.assertEqual(report['request_sha256'], 'a'*64)
            self.assertEqual(report['plan_sha256'], 'b'*64)
            self.assertEqual(report['control']['requested_value'], 0)
            self.assertEqual(report['control']['observed_value'], 0)
            self.assertEqual(report['scientific_validity'], 'NOT_ASSESSED')
        self.assertEqual(next(r for r in reports if r['checkpoint'])['checkpoint'], checkpoint)

    def test_actual_drift_is_retained_as_one_instead_of_invented_or_unknown_value(self):
        observations = self.observations(1)
        observations.before_capture(0)
        self.control.value = 1
        with self.assertRaises(integration.ControlReadbackFailure):
            observations.after_capture(0, dict(sha256='c'*64))
        report = json.loads((observations.root/'capture-0-after-native-checkpoint.json').read_bytes())
        self.assertEqual(report['control']['observed_value'], 1)
        self.assertEqual(report['control']['requested_value'], 0)
        self.assertFalse(report['control']['verified'])

    def test_reordered_repeated_missing_and_foreign_metadata_are_rejected(self):
        observations = self.observations(2)
        with self.assertRaisesRegex(RuntimeError, 'authorization order'):
            observations.before_capture(1)
        observations.before_capture(0)
        with self.assertRaisesRegex(RuntimeError, 'checkpoint order'):
            observations.after_capture(1, {})
        with self.assertRaisesRegex(RuntimeError, 'missing platform observations'):
            observations.complete()
        observations.after_capture(0, {})
        with self.assertRaisesRegex(RuntimeError, 'authorization order'):
            observations.before_capture(0)
        with self.assertRaises(FileExistsError):
            self.observations(2)
        with self.assertRaisesRegex(RuntimeError, 'finite capture count'):
            self.observations(181, 'another')
        bad = dict(self.description, extra='foreign')
        with self.assertRaisesRegex(RuntimeError, 'closed witness'):
            integration.ReadOnlyWitness(bad, self.fd, control=self.control)

    @staticmethod
    def runner(events, *, count=2, after_native=None):
        class Channel:
            def __init__(self, *, captures):
                self.ordinal, self.pending = 0, None
            def receive(self, *, deadline_ns):
                if after_native is not None:
                    after_native(self.ordinal)
                self.pending = types.SimpleNamespace(ordinal=self.ordinal, binding=dict(sha256='c'*64))
                return self.pending
            def acknowledge(self, receipt_binding, *, deadline_ns):
                events.append(('ack', self.ordinal))
                self.ordinal += 1
                self.pending = None
        def start(*args, **kwargs):
            events.append(('native-launch', None))
            return object()
        scope = dict(subprocess=types.SimpleNamespace(Popen=start),
            channel=types.SimpleNamespace(ArchiveChannel=Channel), events=events, count=count)
        exec('def runner(pass_fds=()):\n'
             '    subprocess.Popen([], pass_fds=pass_fds)\n'
             '    handoff=channel.ArchiveChannel(captures=count)\n'
             '    for ordinal in range(count):\n'
             '        pending=handoff.receive(deadline_ns=1)\n'
             '        events.append(("archived", ordinal))\n'
             '        handoff.acknowledge({"synthetic_custody":True}, deadline_ns=1)\n'
             '    return "synthetic_complete"\n',scope)
        return scope['runner']

    def test_private_runner_preserves_code_and_gates_every_capture(self):
        observations = self.observations(2)
        events = []
        original = self.runner(events)
        original_globals = dict(original.__globals__)
        with patch.object(observations, 'before_capture', wraps=observations.before_capture) as before:
            run = integration.wrap_runner(original, observations)
            self.assertIs(run.instrumented_runner.__code__, original.__code__)
            self.assertEqual(run(), 'synthetic_complete')
            self.assertEqual([c.args for c in before.call_args_list], [(0,), (1,)])
        self.assertEqual(original_globals, original.__globals__)
        self.assertEqual(events, [('native-launch', None), ('archived',0), ('ack',0), ('archived',1), ('ack',1)])
        self.assertEqual(len(list(observations.root.iterdir())), 4)

    def test_failed_initial_check_prevents_native_launch(self):
        observations = self.observations()
        events = []
        run = integration.wrap_runner(self.runner(events), observations)
        self.control.value = 1
        with self.assertRaises(integration.ControlReadbackFailure):
            run()
        self.assertEqual(events, [])

    def test_failed_after_check_archives_then_blocks_ack_and_later_capture(self):
        observations = self.observations()
        events = []
        def drift(ordinal):
            self.control.value = 1
        run = integration.wrap_runner(self.runner(events, after_native=drift), observations)
        with self.assertRaisesRegex(RuntimeError, 'capture archived; next capture denied'):
            run()
        self.assertEqual(events, [('native-launch', None), ('archived', 0)])
        self.assertEqual(observations.next_ordinal, 0)

    def test_witness_descriptor_cannot_leak_into_native_pass_fds(self):
        observations = self.observations()
        events = []
        run = integration.wrap_runner(self.runner(events), observations)
        with self.assertRaisesRegex(RuntimeError, 'must not be inherited'):
            run(pass_fds=(self.fd,))
        self.assertEqual(events, [])

    def test_failed_after_receipt_publication_preserves_capture_before_stopping(self):
        observations = self.observations()
        events = []
        publish = control_guard.publish
        def fail_after(path, value):
            if 'after-native' in path.name:
                raise OSError('receipt publication failed')
            return publish(path, value)
        run = integration.wrap_runner(self.runner(events), observations)
        with patch.object(control_guard, 'publish', fail_after):
            with self.assertRaisesRegex(RuntimeError, 'next capture denied'):
                run()
        self.assertEqual(events, [('native-launch', None), ('archived', 0)])

    def test_final_platform_failure_retains_original_worker_cleanup_proof(self):
        observations = self.observations(1)
        events = []
        run = integration.wrap_runner(self.runner(events, count=1), observations)
        with patch.object(observations, 'complete', side_effect=RuntimeError('final check failed')):
            with self.assertRaisesRegex(RuntimeError, 'PLATFORM_AFTER_WORKER') as caught:
                run()
        self.assertEqual(caught.exception.cleanup_proof, 'synthetic_complete')
        self.assertEqual(events[-1], ('ack', 0))

    def test_native_failure_is_not_replaced_or_retried_by_guard_wrapper(self):
        observations = self.observations(1)
        events = []
        def fail(ordinal):
            raise ValueError('actual native failure')
        run = integration.wrap_runner(self.runner(events, count=1, after_native=fail), observations)
        with self.assertRaisesRegex(ValueError, 'actual native failure'):
            run()
        self.assertEqual(events, [('native-launch', None)])

    def test_real_transport_stays_blocked_after_post_capture_platform_failure(self):
        fixture = transport_tests.ArchiveChannelTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        observations = self.observations(1)
        observations.before_capture(0)
        guarded = integration.channel_namespace(channel, observations)
        with patch.object(channel, 'ArchiveChannel', guarded.ArchiveChannel):
            handoff, child = fixture.start()
        self.control.value = 1
        pending = handoff.receive(deadline_ns=fixture.deadline())
        self.assertEqual(pending.ordinal, 0)
        receipt = fixture.receipt()  # Transport fixture, no archival/scientific claim.
        self.assertTrue((fixture.root/receipt['file_name']).exists())
        with self.assertRaisesRegex(RuntimeError, 'next capture denied'):
            handoff.acknowledge(receipt, deadline_ns=fixture.deadline())
        self.assertIsNone(child.poll())
        self.assertEqual(handoff.ordinal, 0)

    def test_actual_executor_composition_is_private_and_retains_native_transport_code(self):
        observations = self.observations(1)
        original_channel = executor.run_archived_worker.__globals__['channel']
        original_subprocess = executor.run_archived_worker.__globals__['subprocess']
        result = integration.make_executor(observations)
        execute = inspect.getclosurevars(result.execute_fixed_action).nonlocals['execute']
        base = inspect.getclosurevars(execute).nonlocals['base']
        self.assertIs(base.run_archived_worker.instrumented_runner.__code__, executor.run_archived_worker.__code__)
        self.assertIs(executor.run_archived_worker.__globals__['channel'], original_channel)
        self.assertIs(executor.run_archived_worker.__globals__['subprocess'], original_subprocess)
        historical = source_execution.make_executor()
        self.assertFalse(hasattr(historical.run_archived_worker, 'instrumented_runner'))
        with self.assertRaisesRegex(RuntimeError, 'Q16c-only'):
            result.execute_fixed_action(request=dict(action_id='Q16b'))

    def test_platform_bindings_are_checked_before_original_contract_and_native_launch(self):
        observations = self.observations(1)
        result = integration.make_executor(observations)
        plan = dict(schema_version=source_execution.contract.VERSION, captures=[{}])
        request = dict(action_id='Q16c', action_inputs=dict(plan=plan))
        with self.assertRaisesRegex(RuntimeError, 'request binding differs'):
            result.execute_fixed_action(request=request)
        observations.request_sha256 = hashlib.sha256(result.previous.canonical(request)).hexdigest()
        with self.assertRaisesRegex(RuntimeError, 'plan binding differs'):
            result.execute_fixed_action(request=request)
        observations.plan_sha256 = hashlib.sha256(result.archive.canonical(plan)).hexdigest()
        observations.count = 2
        with self.assertRaisesRegex(RuntimeError, 'counts differ before launch'):
            result.execute_fixed_action(request=request)
        observations.count = 1
        # Correct bindings reach the original validator, which still rejects
        # this deliberately incomplete plan. The guard grants no admission.
        with self.assertRaises(source_execution.ContractError):
            result.execute_fixed_action(request=request)


if __name__ == '__main__':
    unittest.main()
