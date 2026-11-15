"""Operator software verification only; never invokes stand operators or SSH."""
import ast
import copy
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch, Mock

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]
spec = importlib.util.spec_from_file_location('study_software_test', HERE / 'operators/run_daycap_study.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def save(p, d):
    p.write_bytes(m.canonical(d))
    return m.binding(p)


class BindingAndBudgetTests(unittest.TestCase):
    def test_anchor_counts_prerequisites_and_preserves_absolute_cleanup_reserve(self):
        now = 10**15
        start = now - 240 * m.NANO
        with patch.object(m.time, 'monotonic_ns', return_value=now):
            budget = m.Budget(start)
            self.assertEqual(budget.work, start + 84600 * m.NANO)
            self.assertEqual(budget.end, start + 86400 * m.NANO)
            self.assertEqual(budget.end - budget.work, 1800 * m.NANO)
            self.assertEqual(budget.qualify_prep, now + 3600 * m.NANO)
            self.assertEqual(budget.phase(m.COLLECTION_SECONDS), now + m.COLLECTION_SECONDS * m.NANO)
        with patch.object(m.time, 'monotonic_ns', return_value=start + 84000 * m.NANO):
            self.assertEqual(budget.phase(13500), budget.work)
        with patch.object(m.time, 'monotonic_ns', return_value=budget.work):
            with self.assertRaises(RuntimeError):
                budget.phase(1)

    def test_late_qualification_reserves_fixed_native_analysis_reporting_budgets(self):
        start = 10**15
        now = start + 10000 * m.NANO
        with patch.object(m.time, 'monotonic_ns', return_value=now):
            budget = m.Budget(start)
            self.assertEqual(budget.qualify_prep, budget.end - (57600 + 13500 + 3600) * m.NANO)
            self.assertLess(budget.qualify_prep - now, 3600 * m.NANO)
        with patch.object(m.time, 'monotonic_ns', return_value=start + 11700 * m.NANO):
            with self.assertRaises(RuntimeError):
                m.Budget(start)

    def test_actual_bound_monotonic_anchor_not_future_launch_or_caller_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'first-result.json'
            record = dict(operator='v26-ext001-execute.py', exit_code=0, leader_reaped=True,
                          started_monotonic_ns=1000, completed_monotonic_ns=2000)
            c = dict(admission_start=save(p, record))
            with patch.object(m.time, 'monotonic_ns', return_value=3000):
                self.assertEqual(m.admission_anchor(c), 1000)
                for key, value in (('exit_code', 1), ('leader_reaped', False),
                                   ('started_monotonic_ns', True), ('completed_monotonic_ns', 4000)):
                    changed = dict(record, **{key: value})
                    c['admission_start'] = save(p, changed)
                    with self.subTest(key=key), self.assertRaises(RuntimeError):
                        m.admission_anchor(c)

    def test_bound_regular_bytes_reject_changed_payload_symlink_duplicate_json_and_noninteger_values(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'input.json'
            b = save(p, dict(software_only=True))
            self.assertEqual(m.parse(m.bound(b)), dict(software_only=True))
            p.write_bytes(p.read_bytes() + b' ')
            with self.assertRaises(RuntimeError):
                m.bound(b)
            p.write_bytes(b'{}')
            link = Path(temp) / 'link'
            link.symlink_to(p)
            with self.assertRaises(RuntimeError):
                m.bound(dict(path=str(link), size_bytes=2, sha256=hashlib.sha256(b'{}').hexdigest()))
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.0}'):
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                m.parse(raw)

    def test_original_restoration_status_semantic_body_is_unchanged(self):
        old = REPOSITORY / 'docs/evidence/stage17/ARCHIVE-NATIVE-20261115-01/restart-operators-v3/formal_launch_q16b.py'
        function = next(n for n in ast.parse(old.read_bytes()).body if isinstance(n, ast.FunctionDef)
                        and n.name == 'restoration_status')
        new = ast.parse(inspect.getsource(m.restoration_status)).body[0]
        self.assertEqual(ast.dump(function), ast.dump(new))


class ReceiptAndAnalysisTests(unittest.TestCase):
    def prestate(self):
        return [dict(cpu=cpu, complete_value_hex='0000000000000000') for cpu in (0, 1, 8)]

    def receipt(self, success=True):
        d = dict(schema_version='cpu-prefetch-stage17-phase-action-' + ('completion' if success else 'failure') + '/6',
                 action_id='Q16b', attempt_id='software', request_sha256='a' * 64, authorization_sha256='b' * 64,
                 leader_reaped=True, process_group_gone=True, restoration_verified=True)
        readback = [dict(cpu=r['cpu'], observed_hex=r['complete_value_hex'], matches=True,
                        **{('expected_hex' if success else 'requested_hex'): r['complete_value_hex']}) for r in self.prestate()]
        if success:
            d.update(quarantined=False, live_restoration_readback=readback)
        else:
            d.update(quarantine_operation=dict(performed=False), recovery_readback=readback)
        return d

    def test_restored_failure_is_not_executor_success_and_missing_readback_is_not_restoration(self):
        kwargs = dict(attempt_id='software', request_sha256='a' * 64, authorization_sha256='b' * 64,
                      expected_prestate=self.prestate())
        failure = m.restoration_status(self.receipt(False), **kwargs)
        self.assertTrue(failure['hardware_restoration_verified'])
        self.assertFalse(failure['executor_completed'])
        for field, value in (('leader_reaped', False), ('process_group_gone', False), ('quarantined', True)):
            self.assertFalse(m.restoration_status(dict(self.receipt(), **{field: value}), **kwargs)['hardware_restoration_verified'])
        d = self.receipt()
        d['live_restoration_readback'].pop()
        with self.assertRaises(RuntimeError):
            m.restoration_status(d, **kwargs)

    def test_exactly_one_actual_receipt_and_no_failure_to_success_conversion(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            study = m.Study.__new__(m.Study)
            study.result = {}
            d = dict(output_root=str(root), files=dict(request=dict(sha256='a' * 64), authorization=dict(sha256='b' * 64)))
            request = dict(attempt_id='software', action_inputs=dict(hardware_control=dict(prestate=self.prestate())))
            for record in (self.receipt(False), self.receipt(True)):
                p = root / ('stage17-q16b-' + ('completion' if record.get('quarantined') is False else 'failure') + '-v6.json')
                save(p, record)
                with self.assertRaises(RuntimeError):
                    study.collection_receipt(d, request)

    def test_success_requires_actual_all120_descriptive_report_and_preserves_conservative_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual_plan = dict(source_revision=m.SOURCE, stand_id='software-stand')
            request = save(root / 'request.json', dict(action_inputs=dict(plan=actual_plan)))
            analysis = dict(analysis_root=str(root), files=dict(request=request))
            calibration = dict(action_id='Q16b', method_id='SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1',
                source_revision=m.SOURCE, stand_id=actual_plan['stand_id'], plan_sha256=m.plan_sha256(actual_plan),
                status='DESCRIPTIVE', descriptive_summary_complete=True, tolerance_claim=None, tolerance_guarantee=False,
                execution_authority=False, phase18_authority=False,
                report_provenance_authenticated=False, independent_runs_authenticated=False, family_validity_established=False,
                run_sources=[dict(validity='VALID') for _ in range(120)],
                derived_result=dict(cells=[dict(valid_runs=2) for _ in range(60)]))
            report = save(root / 'calibration.json', calibration)
            complete = dict(status='ALL_120_ANALYZED', calibration_status='DESCRIPTIVE', captures=120, cells=60,
                            repetitions_per_cell=2, all_raw_reconstructed_and_hash_checked=True, canonical_spools_removed=True,
                            ext007_admitted=False, execution_authority=False, phase18_authority=False, report=report)
            save(root / 'analysis-complete.json', complete)
            study = m.Study.__new__(m.Study)
            study.result = {}
            study.analysis_result(analysis)
            self.assertIn('analysis_completion', study.result)
            for key, value in (('calibration_status', 'VALIDATED'), ('captures', 119), ('ext007_admitted', True),
                               ('all_raw_reconstructed_and_hash_checked', False)):
                save(root / 'analysis-complete.json', dict(complete, **{key: value}))
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    study.analysis_result(analysis)
            calibration['run_sources'].pop()
            complete['report'] = save(root / 'calibration.json', calibration)
            save(root / 'analysis-complete.json', complete)
            with self.assertRaises(RuntimeError):
                study.analysis_result(analysis)


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='d254-operator-transition-'))
        self.evidence = Path(self.temp)
        self.enterContext(patch.object(m, 'E', self.evidence))
        self.enterContext(patch.object(m.os, 'chown'))

    def study(self, failure=None, restored=True, cleanup_error=False):
        s = m.Study.__new__(m.Study)
        s.root = self.evidence / 'daycap-resume-study-1'
        s.args = types.SimpleNamespace(config=self.evidence / 'config.json', config_sha256='c' * 64)
        s.budget = m.Budget(time.monotonic_ns())
        s.c = dict(python=dict(path=sys.executable), pilot_archive=dict(path='/software-only/archive'),
                   pilot_sidecar=dict(path='/software-only/sidecar'), prepare_configuration=dict(path='/software-only/prep', sha256='d' * 64))
        s.operators = {'prepare_collection.py': dict(path='/software-only/prepare_collection.py')}
        s.qualifiers = {'run_qualification_v26.py': dict(path='/software-only/run_qualification_v26.py')}
        s.c['qualification_inventory'] = dict(sha256='e' * 64)
        s.release = {}
        s.active = None
        s.result = dict(success=False, errors=[], phases=[], source_revision=m.SOURCE,
                        ext007_admitted=False, execution_authority=False, phase18_authority=False)
        events = []
        s.clock = types.SimpleNamespace(config=dict(lifecycle_seconds=72000,stop_seconds=120),ISO=types.SimpleNamespace(prepare=lambda _:events.append('isolation')))
        s.c['resume_inputs'] = dict(path='/software-only/retained.json',sha256='f'*64)
        self.enterContext(patch.object(m,'retained_inputs',return_value=dict(bindings=dict(administration_manifest=dict(sha256='f'*64)))))
        def command(label, argv, deadline):
            events.append(label)
            self.assertNotIn('--prerequisites', argv)
            s.result['phases'].append(label)
            if failure == label:
                if cleanup_error:
                    s.active = types.SimpleNamespace(stop=Mock(side_effect=RuntimeError('cleanup failed')), forced=[],
                                                     process=types.SimpleNamespace(pid=123, returncode=None))
                raise RuntimeError('software failure ' + label)
            if label == 'retained-admission':
                save(s.root / 'retained-admission.log', dict(status='PASS',current_state='READY_FOR_STAGE17_PHASE_AUTHORIZATION',resolutions=6,transitions=3,pilot_ready=False))
        s.command = command
        def restore():
            events.append('restore')
            s.result['partition_restoration'] = dict(verified=restored)
            return restored
        s.bounded_restore = restore
        s.check_isolation = Mock()
        def receipt(*_):
            events.append('actual-receipt')
            s.result['collection_receipt'] = dict(executor_completed=True, hardware_restoration_verified=True)
        s.collection_receipt = receipt
        s.analysis_result = lambda *_: events.append('all120-validated')
        pb = dict(path='/software-only/prepared-phase.json', sha256='1' * 64)
        d = dict(wrappers=dict(cli=dict(path='/software-only/daycap_cli.py')),
                 files=dict(cli_configuration=dict(path='/software-only/cli-config', sha256='2' * 64),
                            authorization=dict(path='/software-only/auth'), signature=dict(path='/software-only/signature')),
                 repository_root='/software-only/repository')
        self.enterContext(patch.object(m, 'prepared', return_value=(pb, d, {}, {})))
        return s, events

    def test_successful_order_restores_hardware_and_partition_before_analysis(self):
        s, events = self.study()
        self.assertTrue(s.run()['success'])
        self.assertTrue(s.result['reduced_q16b_calibration_done'])
        self.assertEqual(events, ['retained-admission', 'preparation', 'isolation', 'owner-check', 'collection', 'actual-receipt',
                                  'restore', 'analysis', 'all120-validated'])
        self.assertFalse(s.result['ext007_admitted'])
        self.assertTrue((s.root / 'study-result.json').is_file())

    def test_no_retry_and_no_analysis_after_each_prerequisite_or_native_failure(self):
        for failure in ('retained-admission', 'preparation', 'owner-check', 'collection'):
            with self.subTest(failure=failure):
                s, events = self.study(failure)
                self.assertFalse(s.run()['success'])
                self.assertEqual(events.count(failure), 1)
                self.assertIn('restore', events)
                self.assertNotIn('analysis', events)
                self.assertFalse((s.root / 'collection-intent.json').exists() if failure != 'collection' else False)
                # Each independent software case gets a fresh test namespace.
                __import__('shutil').rmtree(s.root)
                (self.evidence / 'qualification-family-complete-1.json').unlink(missing_ok=True)

    def test_cleanup_failure_remains_failure_and_prevents_analysis(self):
        for restored in (False, True):
            s, events = self.study('collection', restored=restored, cleanup_error=True)
            self.assertFalse(s.run()['success'])
            self.assertTrue(any('cleanup failed' in message for message in s.result['errors']))
            self.assertIn('restore', events)
            self.assertNotIn('analysis', events)
            __import__('shutil').rmtree(s.root)
            (self.evidence / 'qualification-family-complete-1.json').unlink(missing_ok=True)

    def test_isolation_restoration_failure_blocks_analysis_even_after_native_success(self):
        s, events = self.study(restored=False)
        self.assertFalse(s.run()['success'])
        self.assertNotIn('analysis', events)

    def test_existing_study_namespace_cannot_be_restarted(self):
        s, events = self.study()
        s.root.mkdir()
        with self.assertRaises(FileExistsError):
            s.run()
        self.assertEqual(events, [])

    def test_analysis_failure_cannot_turn_completed_collection_into_study_success(self):
        s, events = self.study('analysis')
        self.assertFalse(s.run()['success'])
        self.assertEqual(events.count('analysis'), 1)
        self.assertLess(events.index('restore'), events.index('analysis'))
        self.assertNotIn('all120-validated', events)


class PreparedContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='d254-prepared-contract-'))
        self.e = Path(self.temp)
        self.enterContext(patch.object(m, 'E', self.e))
        self.root = self.e / 'daycap-collection-preparation-1'
        self.root.mkdir()
        self.c = dict(source_revision=m.SOURCE, boot_id='software-boot')
        self.release = dict(bundle_name='software-bundle')
        worker = self.e / 'local-bundle-extract/software-bundle/release/bin/cpu_prefetch_runner'
        worker.parent.mkdir(parents=True)
        worker.write_bytes(b'inert software fixture, never executed')
        self.release['worker_sha256'] = m.binding(worker)['sha256']
        self.plan = dict(source_revision=m.SOURCE, stand_id='software-only', clean_source=True, action_id='Q16b',
            schema_version='cpu-prefetch-stage17-formal-service-plan/3',
            method_id='SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1', repetitions_per_cell=2,
            budget=dict(watchdog_ns=m.NATIVE_SECONDS * m.NANO),
            captures=[dict(execution_budget=dict(memory_bytes=m.WORKER_AS),
                           resources=dict(total_mapping_bytes=m.MEMLOCK)) for _ in range(120)])
        # The standalone file may use transport whitespace; output identity is
        # the qualified native JCS plan hash without LF, never that whitespace.
        p = self.root / 'plan.json'
        p.write_text(json.dumps(self.plan, indent=2) + '\n')
        output = self.e / 'shared-program/working' / m.plan_sha256(self.plan)
        output.mkdir(parents=True)
        self.request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6', action_id='Q16b',
            action_inputs=dict(plan=self.plan, hardware_control=dict(software_fixture_only=True)),
            evidence_root_binding=dict(absolute_path=str(output)))
        request = save(self.root / 'request.json', self.request)
        authorization = save(self.root / 'authorization.json', dict(action_id='Q16b', request_binding=request))
        signature = save(self.root / 'signature', dict(software_fixture_only=True))
        repository = str(self.e / 'admission-root')
        cli = save(self.root / 'cli.json', dict(repository_root=repository, boot_id=self.c['boot_id']))
        analysis = save(self.root / 'analysis.json', dict(repository_root=repository, evidence_root=str(self.e),
            boot_id=self.c['boot_id'], execution_authority=False, analysis_root=str(self.e / 'analysis'),
            files=dict(request=request, authorization=authorization, signature=signature)))
        limits = save(self.root / 'limits.json', dict(address_space_bytes=m.WORKER_AS, memlock_bytes=m.MEMLOCK))
        hardware = save(self.root / 'hardware.json', self.request['action_inputs']['hardware_control'])
        self.operators = {}
        for name in ('daycap_cli.py', 'owner_check.py', 'analyze_daycap.py'):
            self.operators[name] = save(self.root / name, dict(software_fixture_only=True))
        self.document = dict(schema_version=m.PREPARED_SCHEMA, source_revision=m.SOURCE, boot_id=self.c['boot_id'],
            repository_root=repository, evidence_root=str(self.e), output_root=str(output), worker=m.binding(worker),
            files=dict(request=request, authorization=authorization, signature=signature, plan=m.binding(p),
                       cli_configuration=cli, analysis_config=analysis, limits=limits, hardware_control=hardware),
            wrappers=dict(cli=self.operators['daycap_cli.py'], owner_check=self.operators['owner_check.py'],
                          analysis=self.operators['analyze_daycap.py']), execution_authority=False, phase18_authority=False)

    def prepare(self):
        save(self.root / 'prepared-phase.json', self.document)
        return m.prepared(self.c, self.operators, self.release)

    def test_exact_published_schema_and_plan_derived_limits_without_native_execution(self):
        _, actual, request, _ = self.prepare()
        self.assertEqual(actual, self.document)
        self.assertEqual(request, self.request)

    def test_metadata_source_limits_wrappers_and_hardware_cannot_be_substituted(self):
        before = copy.deepcopy(self.document)
        for key, value in (('source_revision', '0' * 40), ('execution_authority', True)):
            self.document = dict(before, **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.prepare()
        self.document = copy.deepcopy(before)
        self.document['files']['limits'] = save(self.root / 'limits.json', dict(address_space_bytes=m.WORKER_AS - 1,
                                                                               memlock_bytes=m.MEMLOCK))
        with self.assertRaisesRegex(RuntimeError, 'actual plan worker/mapping maxima'):
            self.prepare()

    def test_completed_namespace_rejected_before_execution_but_readable_after_restoration(self):
        self.prepare()
        save(Path(self.document['output_root']) / 'stage17-q16b-completion-v6.json', dict(software_fixture_only=True))
        with self.assertRaisesRegex(RuntimeError, 'already consumed'):
            m.prepared(self.c, self.operators, self.release)
        self.assertEqual(m.prepared_after(self.c, self.operators, self.release)[1], self.document)


class RootRestorationBoundsTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='d254-software-restoration-'))
        self.s = m.Study.__new__(m.Study)
        self.s.root = Path(self.temp)
        self.s.result = {}
        self.s.budget = m.Budget(time.monotonic_ns())

    def test_original_core_phase_report_is_reaped_and_preserved(self):
        def software_only():
            m.save(self.s.root / 'partition-restoration.json', dict(verified=True, software_fixture_only=True))
            return True
        self.s.restore = software_only
        self.assertTrue(self.s.bounded_restore())
        self.assertTrue(self.s.result['partition_restoration']['software_fixture_only'])

    def test_finite_cleanup_child_timeout_is_retained_as_failure(self):
        self.s.restore = lambda: time.sleep(5)
        with patch.object(m, 'CLEANUP_SECONDS', .05):
            self.assertFalse(self.s.bounded_restore())
        self.assertFalse(self.s.result['partition_restoration']['verified'])
        self.assertTrue((self.s.root / 'partition-restoration-timeout.json').is_file())
        self.assertFalse(m.descendants(os.getpid()))


class FiniteChildTests(unittest.TestCase):
    def test_reused_leader_pid_is_never_traversed_as_our_owner(self):
        child = m.OwnedProcess.__new__(m.OwnedProcess)
        child.process = types.SimpleNamespace(pid=123456)
        child.leader_ticks, child.observed = 10, {}
        with patch.object(m, 'start_ticks', return_value=20), \
             patch.object(m, 'descendants', return_value={}) as tree:
            self.assertEqual(child.observe(), {})
        tree.assert_called_once_with(os.getpid())

    def test_timeout_signals_separate_native_child_before_owner_and_allows_cleanup(self):
        with tempfile.TemporaryDirectory(prefix='d254-finite-child-') as temp:
            root = Path(temp)
            ready, restored = root / 'ready', root / 'software-cleanup'
            executable = Path(sys.executable).resolve()
            identity = (executable.stat().st_size, hashlib.sha256(executable.read_bytes()).hexdigest())
            source = ('import pathlib,subprocess,sys; '
                      'p=subprocess.Popen([sys.executable,"-c","import time; time.sleep(15)"],start_new_session=True); '
                      f'pathlib.Path({str(ready)!r}).write_text(str(p.pid)); '
                      'p.wait(); '
                      f'pathlib.Path({str(restored)!r}).write_text("software cleanup only")')
            with (root / 'log').open('wb') as log:
                child = m.OwnedProcess([str(executable), '-c', source], log, {identity})
                try:
                    deadline = time.monotonic() + 3
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(ready.exists())
                    native_pid = int(ready.read_text())
                    with self.assertRaises(RuntimeError):
                        child.wait(time.monotonic_ns() + 30_000_000)
                    signals = []
                    actual_send = m.send_pidfd
                    def record(pid, ticks, sig, **kw):
                        signals.append((pid, sig, kw))
                        return actual_send(pid, ticks, sig, **kw)
                    with patch.object(m, 'send_pidfd', side_effect=record):
                        child.stop(time.monotonic_ns() + 4 * m.NANO)
                    self.assertEqual(signals[0][0:2], (native_pid, signal.SIGTERM))
                    self.assertEqual(signals[0][2]['native'], {identity})
                    self.assertNotIn(child.process.pid, [row[0] for row in signals])
                    self.assertTrue(restored.is_file())
                    self.assertEqual(child.forced, [])
                    self.assertEqual(child.process.returncode, 0)
                finally:
                    if child.process.poll() is None:
                        child.stop(time.monotonic_ns() + 4 * m.NANO)

    def test_pidfd_native_identity_rejects_wrong_image_without_signalling(self):
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(5)'], stdout=log, stderr=log)
            try:
                with self.assertRaises(RuntimeError):
                    m.send_pidfd(process.pid, m.start_ticks(process.pid), signal.SIGTERM, native={(1, '0' * 64)})
                self.assertIsNone(process.poll())
            finally:
                process.terminate()
                process.wait(timeout=2)


if __name__ == '__main__':
    unittest.main()
