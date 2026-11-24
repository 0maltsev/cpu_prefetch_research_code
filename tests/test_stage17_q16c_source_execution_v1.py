"""Real sealed memfds from synthetic originals; no experiment execution."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_q16c_source_execution_v1 as current
import stage17_service_daycap_execution_v1 as previous
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


class SourcePinTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='q16c-source-pin-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.plan = plan_fixture(); self.bindings = []
        self.plan['budget']['setup_ns'] += 30_000_000_000
        self.plan['budget']['watchdog_ns'] += 30_000_000_000
        for item in self.plan['captures']:
            for source in item['capture']['schedules']:
                raw = b'\0' * (8 * source['offered_count'])
                path = self.root / source['source_artifact']['artifact_id']
                path.write_bytes(raw)
                digest = hashlib.sha256(raw).hexdigest()
                source['source_artifact']['sha256'] = digest
                self.bindings.append(dict(artifact_id=path.name, path=str(path), size_bytes=len(raw), sha256=digest))
        self.deadline = time.monotonic_ns() + 60_000_000_000

    def test_complete_pinning_and_exception_cleanup_without_original_mutation(self):
        before = set(os.listdir('/proc/self/fd'))
        captured = []
        with self.assertRaisesRegex(RuntimeError, 'owned-stop'):
            with current.pin_original_sources(self.plan, self.bindings, deadline_ns=self.deadline) as (context, fds):
                self.assertEqual(len(context['bindings']), 360); self.assertEqual(len(fds), 360)
                captured.extend(fds)
                for fd, binding in zip(fds, self.bindings):
                    self.assertEqual(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE, os.O_RDONLY)
                    self.assertEqual(fcntl.fcntl(fd, fcntl.F_GET_SEALS) & current.SEALS, current.SEALS)
                    self.assertEqual(hashlib.sha256(os.pread(fd, 1024, 0)).hexdigest(), binding['sha256'])
                raise RuntimeError('owned-stop')
        self.assertEqual(set(os.listdir('/proc/self/fd')), before)
        for fd in captured:
            with self.assertRaises(OSError): os.fstat(fd)
        for binding in self.bindings:
            self.assertEqual(hashlib.sha256(Path(binding['path']).read_bytes()).hexdigest(), binding['sha256'])

    def test_missing_reordered_changed_symlink_and_expired_sources_rejected_with_no_fd_leak(self):
        def symlink(bindings):
            path = Path(bindings[0]['path']); original = path.with_suffix('.original')
            path.rename(original); path.symlink_to(original)
        for mutate in [lambda b: b.pop(), lambda b: b.reverse(),
                       lambda b: b[-1].update(sha256='0' * 64), symlink]:
            before = set(os.listdir('/proc/self/fd')); bindings = copy.deepcopy(self.bindings); mutate(bindings)
            with self.subTest(mutate=mutate), self.assertRaises((current.ContractError, current.archive.ArchiveError, OSError)):
                with current.pin_original_sources(self.plan, bindings, deadline_ns=self.deadline):
                    self.fail('rejected source yielded descriptors')
            self.assertEqual(set(os.listdir('/proc/self/fd')), before)
        with self.assertRaises(current.ContractError):
            with current.pin_original_sources(self.plan, self.bindings, deadline_ns=1): self.fail('expired pin')

    def test_contract_and_executor_are_private_and_legacy_remains_strict(self):
        old = previous.make_contract(); new = current.make_contract()
        self.assertTrue(new.is_archived_plan('Q16c', self.plan))
        self.assertFalse(old.is_archived_plan('Q16c', self.plan))
        new.validate_plan('Q16c', self.plan)
        with self.assertRaises(current.ContractError): old.validate_plan('Q16c', self.plan)
        executor = current.make_executor()
        self.assertIsNot(executor.plans, old)
        self.assertIsNot(executor.execute_fixed_action, previous.make_executor().execute_fixed_action)

    def test_worker_bridge_preserves_context_bindings_and_releases_only_owned_fds(self):
        import stage17_fixed_action_executor_v10 as executor
        original = dict(schema_version='cpu-prefetch-stage17-fixed-action-context/6',
                        request_sha256='a' * 64, authorization_sha256='b' * 64)
        pinned = executor.predecessor._pin_generated(executor.canonical(original), 'SYNTHETIC_ORIGINAL_CONTEXT')
        self.addCleanup(pinned.close)
        argv = ['synthetic-worker', '--context-fd', str(pinned.descriptor)]
        before = set(os.listdir('/proc/self/fd'))
        with current.sealed_worker_inputs(argv, (pinned.descriptor,), plan=self.plan,
                original_bindings=self.bindings, deadline_ns=self.deadline) as (args, fds):
            context_fd = int(args[2])
            self.assertNotEqual(context_fd, pinned.descriptor)
            self.assertNotIn(pinned.descriptor, fds)
            context = json.loads(os.pread(context_fd, 1024**2, 0))
            self.assertEqual(context.pop('schema_version'), 'cpu-prefetch-stage17-fixed-action-context/7')
            sources = context.pop('schedule_source_context')
            self.assertEqual(len(sources['bindings']), 360)
            self.assertEqual(set(fds), {context_fd, *(b['descriptor'] for b in sources['bindings'])})
            self.assertEqual(context, {k:v for k,v in original.items() if k != 'schema_version'})
        self.assertEqual(set(os.listdir('/proc/self/fd')), before)
        self.assertEqual(json.loads(os.pread(pinned.descriptor, 1024**2, 0)), original)


if __name__ == '__main__': unittest.main()
