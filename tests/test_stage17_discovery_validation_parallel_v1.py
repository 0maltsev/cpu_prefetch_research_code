"""Independent D224 serial/parallel equivalence and fail-closed process tests.

All streams and platform evidence are the existing finite software fixtures.
These tests grant no experiment or retained hardware-evidence validity claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import pathlib
import resource
import shutil
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import check_stage17_discovery_validation_v3 as fixtures
import stage17_discovery_validation_parallel_v1 as parallel

base = fixtures.v


class RecordingContext:
    """Use actual forked processes, recording every started PID for reaping checks."""
    def __init__(self, fail_start_after=None):
        self.context = multiprocessing.get_context('fork')
        self.pids = []
        self.fail_start_after = fail_start_after

    def Pipe(self, *args, **kwargs):
        return self.context.Pipe(*args, **kwargs)

    def Process(self, *args, **kwargs):
        process = self.context.Process(*args, **kwargs)
        start = process.start

        def record_start():
            if self.fail_start_after is not None and len(self.pids) == self.fail_start_after:
                raise OSError('injected process start failure')
            start()
            self.pids.append(process.pid)

        process.start = record_start
        return process


class ParallelValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.family = tempfile.TemporaryDirectory(prefix='d224-fixture-')
        cls.addClassCleanup(cls.family.cleanup)
        cls.original_root = pathlib.Path(cls.family.name)
        cls.original = fixtures.study_fixture(cls.original_root)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='d224-case-')
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / 'evidence'
        shutil.copytree(self.original_root, self.root)
        self.arguments = copy.deepcopy(self.original)
        self.arguments['output_root'] = self.root

    def rewrite_report(self):
        path = self.root / base.registry.REPORT_NAME
        path.write_bytes(base.registry.canonical(self.arguments['retention_report']))
        self.arguments['retention_binding'] = fixtures.binding(path)

    def rewrite_hardware(self, hardware):
        path = self.root / 'studyhardware.json'
        path.write_bytes(base.registry.canonical(hardware))
        self.arguments['retention_report']['hardware_state'] = fixtures.binding(path)
        self.rewrite_report()

    def rewrite_control(self, ordinal, control):
        retained = self.arguments['retention_report']['captures'][ordinal]
        path = self.root / retained['artifacts'][-1]['file_name']
        path.write_bytes(base.registry.canonical(control))
        retained['artifacts'][-1] = fixtures.binding(path)
        self.rewrite_report()

    def control(self, ordinal):
        name = self.arguments['retention_report']['captures'][ordinal]['artifacts'][-1]['file_name']
        return json.loads((self.root / name).read_bytes())

    def assert_both_reject(self, message=None):
        for validator in (base.validate_retained_study, parallel.validate_retained_study):
            with self.subTest(validator=validator.__module__), patch.object(base.selector, 'select_duration') as select:
                with self.assertRaises(base.ValidationError) as caught:
                    validator(**self.arguments)
                if message:
                    self.assertIn(message, str(caught.exception))
                select.assert_not_called()

    def assert_reaped(self, context):
        self.assertTrue(context.pids)
        self.assertLessEqual(len(context.pids), 8)
        for pid in context.pids:
            with self.assertRaises(ProcessLookupError, msg=f'worker {pid} survived or was not reaped'):
                os.kill(pid, 0)

    def test_full36_exact_serial_equality_eight_workers_and_original_selection_order(self):
        original_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        serial = base.validate_retained_study(**self.arguments)
        progress = []
        context = RecordingContext()
        first_nonzero_receipt = pathlib.Path(self.tmp.name) / 'capture-one-received'
        original_job = parallel._capture_job

        def out_of_order_job(job):
            result = original_job(job)
            if result[0] == 0:
                deadline = time.monotonic() + 15
                while not first_nonzero_receipt.exists():
                    if time.monotonic() > deadline:
                        raise RuntimeError('fixture capture one never reached parent')
                    time.sleep(0.01)
            return result

        def record_progress(ordinal, completed, total):
            progress.append((ordinal, completed, total))
            if ordinal == 1:
                first_nonzero_receipt.touch()

        with patch.object(parallel.multiprocessing, 'get_context', return_value=context), \
                patch.object(parallel, '_capture_job', out_of_order_job), \
                patch.object(base.selector, 'select_duration', wraps=base.selector.select_duration) as select:
            actual = parallel.validate_retained_study(**self.arguments, worker_count=8,
                progress=record_progress)
        self.assertEqual(actual, serial)
        self.assertEqual(len(context.pids), 8)
        self.assert_reaped(context)
        self.assertEqual(len(actual.captures), 36)
        self.assertEqual([c.key for c in actual.captures], list(base.selector.required_captures()))
        self.assertEqual(sorted(p[0] for p in progress), list(range(36)))
        completion_order = [p[0] for p in progress]
        self.assertLess(completion_order.index(1), completion_order.index(0))
        self.assertEqual([p[1] for p in progress], list(range(1, 37)))
        self.assertEqual({p[2] for p in progress}, {36})
        select.assert_called_once()
        self.assertEqual(tuple(select.call_args.args[0]), serial.captures)
        self.assertFalse(actual.execution_authority)
        self.assertEqual(actual.formal_runs_contributed, 0)
        self.assertEqual(original_hashes, {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()})

    def test_full36_single_worker_preserves_result_and_checks_memory_limit(self):
        expected = base.validate_retained_study(**self.arguments)
        original_job = parallel._capture_job
        limit = 2 * 1024**3

        def limited_job(job):
            soft, hard = resource.getrlimit(resource.RLIMIT_AS)
            if not 0 < soft <= limit or not 0 < hard <= limit:
                raise AssertionError('worker AS limit not installed')
            return original_job(job)

        parent_limits = resource.getrlimit(resource.RLIMIT_AS)
        with patch.object(parallel, '_capture_job', limited_job):
            actual = parallel.validate_retained_study(**self.arguments, worker_count=1, worker_memory_bytes=limit)
        self.assertEqual(actual, expected)
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), parent_limits)

    def test_last_capture_primary_raw_hash_rejected(self):
        binding = self.arguments['retention_report']['captures'][35]['artifacts'][3]
        path = self.root / binding['file_name']
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        self.assert_both_reject()

    def test_last_capture_rebound_raw_ordinal_still_rejected(self):
        retained = self.arguments['retention_report']['captures'][35]
        control = self.control(35)
        path = self.root / retained['artifacts'][3]['file_name']
        raw = bytearray(path.read_bytes())
        prefix = base.codec.row_layout(control['phases'][1]['run_id'])[0]
        struct.pack_into('<Q', raw, prefix, 99)
        path.write_bytes(raw)
        rebound = fixtures.binding(path)
        retained['artifacts'][3] = rebound
        control['phases'][1]['producer'].update(rebound)
        self.rewrite_control(35, control)
        self.assert_both_reject()

    def test_last_capture_control_raw_binding_mismatch_rejected(self):
        control = self.control(35)
        control['phases'][1]['demand']['sha256'] = '0' * 64
        self.rewrite_control(35, control)
        self.assert_both_reject('raw control custody binding')

    def test_last_capture_actual_msr_and_final_cleanup_rejected(self):
        original_control = self.control(35)
        control = copy.deepcopy(original_control)
        control['controls'][5]['hardware']['cpus'][2]['raw_bytes'][0] ^= 1
        self.rewrite_control(35, control)
        self.assert_both_reject('raw MSR readback')
        self.rewrite_control(35, original_control)
        hardware = json.loads((self.root / 'studyhardware.json').read_bytes())
        hardware['native_results_after_cleanup'][35]['monitor_mapping']['cleanup_attempted'] = False
        self.rewrite_hardware(hardware)
        self.assert_both_reject()

    def test_global_whole_plot_and_bound_input_checks_preserved(self):
        original = copy.deepcopy(self.arguments)
        hardware = json.loads((self.root / 'studyhardware.json').read_bytes())
        hardware['whole_plots'][1]['restore_readback'].reverse()
        self.rewrite_hardware(hardware)
        self.assert_both_reject('whole plot restore prestate')
        self.arguments = original
        (self.root / 'studyhardware.json').write_bytes((self.original_root / 'studyhardware.json').read_bytes())
        self.rewrite_report()
        self.arguments['action_inputs']['bound_documents'][0]['utf8_bytes'] += '\n'
        self.assert_both_reject('bound input size')

    def test_missing_duplicate_and_false_retention_claims_rejected(self):
        original = copy.deepcopy(self.arguments)
        for change in ('missing', 'duplicate', 'stop', 'validity'):
            with self.subTest(change=change):
                self.arguments = copy.deepcopy(original)
                captures = self.arguments['retention_report']['captures']
                if change == 'missing':
                    captures.pop()
                elif change == 'duplicate':
                    captures[-1] = copy.deepcopy(captures[0])
                elif change == 'stop':
                    captures[-1]['native_stop'] = 'trace_capacity'
                else:
                    captures[-1]['native_validity'] = 'VALID'
                self.rewrite_report()
                self.assert_both_reject()

    def test_worker_exception_death_and_timeout_reap_every_started_child(self):
        def error(job):
            raise RuntimeError('injected capture failure')

        def die(job):
            os._exit(23)

        def stall(job):
            time.sleep(60)

        for replacement, expected in ((error, 'injected capture failure'),
                                      (die, 'worker exited'), (stall, 'deadline exceeded')):
            with self.subTest(failure=replacement.__name__):
                context = RecordingContext()
                start = time.monotonic()
                with patch.object(parallel.multiprocessing, 'get_context', return_value=context), \
                        patch.object(parallel, '_capture_job', replacement), \
                        patch.object(base.selector, 'select_duration') as select:
                    with self.assertRaisesRegex(base.ValidationError, expected):
                        parallel.validate_retained_study(**self.arguments, analysis_timeout_seconds=1)
                    select.assert_not_called()
                self.assertLess(time.monotonic() - start, 20)
                self.assert_reaped(context)

    def test_incomplete_duplicate_and_unsuccessful_worker_receipts_rejected(self):
        original_job = parallel._capture_job

        def missing(connection, jobs, memory_bytes):
            connection.send(('done', None))
            connection.close()

        def duplicate(connection, jobs, memory_bytes):
            result = original_job(jobs[0])
            connection.send(('capture', result))
            connection.send(('capture', result))
            connection.close()

        def bad_exit(connection, jobs, memory_bytes):
            for job in jobs:
                connection.send(('capture', original_job(job)))
            connection.send(('done', None))
            connection.close()
            os._exit(24)

        for replacement in (missing, duplicate, bad_exit):
            with self.subTest(receipt=replacement.__name__):
                context = RecordingContext()
                with patch.object(parallel.multiprocessing, 'get_context', return_value=context), \
                        patch.object(parallel, '_capture_group', replacement), \
                        patch.object(base.selector, 'select_duration') as select:
                    with self.assertRaises(base.ValidationError):
                        parallel.validate_retained_study(**self.arguments, analysis_timeout_seconds=30)
                    select.assert_not_called()
                self.assert_reaped(context)

    def test_progress_callback_failure_cleans_workers_and_skips_selection(self):
        def fail_progress(ordinal, completed, total):
            raise RuntimeError('progress sink failed')

        context = RecordingContext()
        with patch.object(parallel.multiprocessing, 'get_context', return_value=context), \
                patch.object(base.selector, 'select_duration') as select:
            with self.assertRaisesRegex(RuntimeError, 'progress sink failed'):
                parallel.validate_retained_study(**self.arguments, progress=fail_progress)
            select.assert_not_called()
        self.assert_reaped(context)

    def test_process_start_failure_reaps_already_started_workers_without_retry(self):
        context = RecordingContext(fail_start_after=2)

        def stall(job):
            time.sleep(60)

        with patch.object(parallel.multiprocessing, 'get_context', return_value=context), \
                patch.object(parallel, '_capture_job', stall), \
                patch.object(base.selector, 'select_duration') as select:
            with self.assertRaisesRegex(base.ValidationError, 'injected process start failure'):
                parallel.validate_retained_study(**self.arguments)
            select.assert_not_called()
        self.assertEqual(len(context.pids), 2)
        self.assert_reaped(context)

    def test_invalid_process_controls_and_changed_base_hash_rejected_before_fork(self):
        mutants = [('worker_count', value) for value in (True, 0, 9, 1.0)]
        mutants += [('worker_memory_bytes', value) for value in (True, 0, -1, 1.0)]
        mutants += [('analysis_timeout_seconds', value) for value in (True, 0, 86401, 1.0)]
        with patch.object(parallel.multiprocessing, 'get_context') as context, \
                patch.object(base.selector, 'select_duration') as select:
            for name, value in mutants:
                with self.subTest(name=name, value=value), self.assertRaises(base.ValidationError):
                    parallel.validate_retained_study(**self.arguments, **{name: value})
            with patch.object(parallel, 'BASE_SHA256', '0' * 64):
                with self.assertRaisesRegex(base.ValidationError, 'exact D213 checker bytes'):
                    parallel.validate_retained_study(**self.arguments)
            context.assert_not_called()
            select.assert_not_called()


if __name__ == '__main__':
    unittest.main()
