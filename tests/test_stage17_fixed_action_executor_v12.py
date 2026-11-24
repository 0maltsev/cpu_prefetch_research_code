"""Cold transaction deduplication; local software fixtures, no stand authority."""
from __future__ import annotations

import argparse
import ast
import contextlib
from dataclasses import asdict, dataclass, replace
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import types
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import stage17_archive_metadata_fast_v1 as metadata
import stage17_archive_metadata_fast_v2 as metadata_v2
import stage17_archive_flow_private_v1 as flow
import stage17_fixed_action_executor_v11 as original
import stage17_fixed_action_executor_v12 as executor
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_v1 as archive
import test_stage17_fixed_action_executor_v11 as worker_tests
from test_stage17_formal_archive_custody_v1 import CustodyFixture


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.request = {'same': 'request'}
        self.pending = SimpleNamespace(ordinal=0, document={'native_complete': True})
        self.outcome = object()
        self.deadline = time.monotonic_ns() + 60_000_000_000
        self.extent = SimpleNamespace(captures=[object(), object()])
        self.events, self.stores, self.saved = [], [], []
        events, stores = self.events, self.stores
        class Store:
            locked = False
            exits = 0
            def __enter__(self):
                self.locked = True
                return self
            def __exit__(self, *args):
                self.locked = False
                self.exits += 1
        def factory(request, deadline):
            store = Store()
            stores.append(store)
            events.append(('open', request, deadline))
            return store
        self.factory = mock.Mock(side_effect=factory)
        self.scope = dict(events=self.events, saved=self.saved, failure=None,
                          open_store=executor.open_store)
        exec('def receipt(request, pending, outcome, deadline):\n'
             '    saved.append(open_store)\n'
             '    with open_store(request, deadline) as store:\n'
             '        events.append(("receipt", store, store.locked))\n'
             '        if failure == "receipt": raise OSError("receipt failed")\n'
             '    return {"receipt": "exact"}\n'
             'def resources(fd, extent, *, request, deadline_ns, ordinal=0):\n'
             '    with open_store(request, deadline_ns) as store:\n'
             '        events.append(("resources", store, store.locked, ordinal, fd))\n'
             '        if failure == "resources": raise OSError("resources failed")\n', self.scope)

    def finish(self):
        with mock.patch.object(executor, 'open_store', self.factory), \
                mock.patch.object(executor, '_broker_receipt', self.scope['receipt']), \
                mock.patch.object(executor, 'live_resources', self.scope['resources']):
            return executor._finish_archived_capture(self.request, self.pending, self.outcome, self.deadline,
                directory_fd=7, extent=self.extent)

    def test_one_actual_open_both_callbacks_share_lock_and_original_globals_unchanged(self):
        before = dict(self.scope)
        self.assertEqual(self.finish(), {'receipt': 'exact'})
        self.factory.assert_called_once_with(self.request, self.deadline)
        self.assertEqual([event[0] for event in self.events], ['open', 'receipt', 'resources'])
        self.assertIs(self.events[1][1], self.events[2][1])
        self.assertTrue(self.events[1][2] and self.events[2][2])
        self.assertEqual(self.events[2][3:], (1, 7))
        self.assertEqual(self.scope, before)
        self.assertFalse(self.stores[0].locked)
        self.assertEqual(self.stores[0].exits, 1)

    def test_last_capture_skips_resources_and_new_transactions_open_fresh(self):
        self.pending.ordinal = 1
        self.finish()
        self.finish()
        self.assertEqual([event[0] for event in self.events], ['open', 'receipt', 'open', 'receipt'])
        self.assertIsNot(self.stores[0], self.stores[1])
        self.assertTrue(all(store.exits == 1 and not store.locked for store in self.stores))

    def test_native_failure_follows_receipt_and_prevents_resources(self):
        self.pending.document['native_complete'] = False
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.finish()
        self.assertEqual(caught.exception.category, 'NATIVE_FAILURE')
        self.assertEqual([event[0] for event in self.events], ['open', 'receipt'])
        self.assertEqual(self.stores[0].exits, 1)

    def test_callback_failure_releases_lock_without_reopening(self):
        for failure in ('receipt', 'resources'):
            with self.subTest(failure=failure):
                self.events.clear()
                self.scope['failure'] = failure
                with self.assertRaisesRegex(OSError, failure + ' failed'):
                    self.finish()
                self.assertEqual(sum(event[0] == 'open' for event in self.events), 1)
                self.assertEqual(self.stores[-1].exits, 1)
                self.assertFalse(self.stores[-1].locked)

    def test_request_identity_deadline_value_type_and_ended_transaction_are_rejected(self):
        self.finish()
        held = self.saved[0]
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            held(self.request, self.deadline)
        self.assertEqual(caught.exception.category, 'ARCHIVE_STORE_REUSE')
        for request, deadline in ((dict(self.request), self.deadline),
                                  (self.request, self.deadline + 1),
                                  (self.request, float(self.deadline))):
            self.scope.update(candidate_request=request, candidate_deadline=deadline)
            exec('def receipt(request, pending, outcome, deadline):\n'
                 '    with open_store(candidate_request, candidate_deadline): pass\n', self.scope)
            with self.subTest(request=request, deadline=deadline), \
                    self.assertRaises(executor.FixedActionExecutionError) as caught:
                self.finish()
            self.assertEqual(caught.exception.category, 'ARCHIVE_STORE_REUSE')
            self.assertFalse(self.stores[-1].locked)
            self.assertEqual(self.stores[-1].exits, 1)

    def test_open_failure_runs_no_callback(self):
        self.factory.side_effect = OSError('fresh open failed')
        with self.assertRaisesRegex(OSError, 'fresh open failed'):
            self.finish()
        self.assertEqual(self.events, [])
        self.assertEqual(self.saved, [])


@dataclass(frozen=True)
class Declared:
    memory_bytes: int = 0
    required_free_disk_bytes: int = 0


@dataclass(frozen=True)
class Extent:
    declared: Declared
    captures: tuple


class RealTransactionTests(unittest.TestCase):
    def setUp(self):
        self.capacity = SimpleNamespace(f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100000)
        patch = mock.patch.object(os, 'statvfs', return_value=self.capacity)
        patch.start()
        self.addCleanup(patch.stop)
        patch = mock.patch.object(os, 'fstatvfs', return_value=self.capacity)
        patch.start()
        self.addCleanup(patch.stop)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.f = f = CustodyFixture(temp.name)
        with f.store() as store:
            f.begin(store)
            f.reserve(store)
            f.publish(store)
            f.release(store)
            document = dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',
                program_scope_sha256=f.scope, plan_sha256=f.family, capture_ordinal=0,
                checkpoint=asdict(f.checkpoint), status='ARCHIVED_AND_RELEASED',
                scientific_validity='NOT_ASSESSED', execution_authority=False)
            receipt = store.retain_custody_receipt('formal-capture-0-archive-custody.json', archive.canonical(document))
            registration = store.ledger_binding()
        self.outcome = SimpleNamespace(receipt=receipt, receipt_ledger_record=registration,
            status='ARCHIVED_AND_RELEASED', cleanup=SimpleNamespace(leader_reaped=True, process_group_gone=True,
                returncode=0, cleanup_deadline_overrun=False, descendants_detected_after_leader_exit=False))
        self.pending = SimpleNamespace(binding=asdict(f.checkpoint), ordinal=0, document={'native_complete': True})
        storage = dict(program_id='synthetic-future-program', program_scope_sha256=f.scope,
            capture_workspace_overhead_bytes=0, archive_staging_bytes=0, checkpoint_bytes=65536,
            analysis_capture_workspace_bytes=0)
        self.request = dict(action_inputs=dict(plan=dict(storage=storage)))
        capture = SimpleNamespace(declared=SimpleNamespace(max_output_bytes=0))
        self.extent = Extent(Declared(), (capture, capture))
        self.deadline = time.monotonic_ns() + 60_000_000_000
        self.fd = os.open(f.working, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.fd)
        self.opened = []

    def factory(self, request, deadline):
        self.assertIs(request, self.request)
        self.assertEqual(deadline, self.deadline)
        store = custody.ProgramStore(self.f.root, scope_sha256=self.f.scope, family_id=self.f.family,
            limits=replace(self.f.limits, deadline_ns=deadline))
        self.opened.append(store)
        return store

    def finish(self, module=executor):
        with mock.patch.object(module, 'open_store', side_effect=self.factory):
            return module._finish_archived_capture(self.request, self.pending, self.outcome, self.deadline,
                directory_fd=self.fd, extent=self.extent)

    def test_real_receipt_and_resources_keep_one_exclusive_lock(self):
        events = []
        original_read, original_usage = custody.ProgramStore.read_verified_record, custody.ProgramStore.physical_usage
        def check_lock(store, label):
            self.assertIsNotNone(store._lock)
            with self.assertRaises(BlockingIOError):
                with self.f.store():
                    self.fail('another writer acquired the transaction lock')
            events.append((label, store))
        def read(store, binding):
            check_lock(store, 'receipt')
            return original_read(store, binding)
        def usage(store):
            check_lock(store, 'resources')
            return original_usage(store)
        with mock.patch.object(custody.ProgramStore, 'read_verified_record', read), \
                mock.patch.object(custody.ProgramStore, 'physical_usage', usage):
            self.assertEqual(self.finish(), asdict(self.outcome.receipt))
        self.assertEqual([label for label, _ in events], ['receipt', 'resources'])
        self.assertIs(events[0][1], events[1][1])
        self.assertEqual(len(self.opened), 1)
        self.assertIsNone(self.opened[0]._lock)

    def test_original_bodies_and_metadata_factory_clone_have_real_parity(self):
        with mock.patch.object(original, 'open_store', side_effect=self.factory):
            expected = original._broker_receipt(self.request, self.pending, self.outcome, self.deadline)
            original.live_resources(self.fd, self.extent, request=self.request,
                                    deadline_ns=self.deadline, ordinal=1)
        self.assertEqual(len(self.opened), 2)
        adapted = metadata.make_executor(executor)
        scope = adapted._finish_archived_capture.__globals__
        for name in ('_broker_receipt', 'live_resources', 'open_store', 'run_archived_worker'):
            self.assertIs(getattr(adapted, name).__globals__, scope)
        with mock.patch.dict(scope, open_store=self.factory):
            self.assertEqual(adapted._finish_archived_capture(self.request, self.pending, self.outcome,
                self.deadline, directory_fd=self.fd, extent=self.extent), expected)
        self.assertEqual(len(self.opened), 3)
        self.assertTrue(all(store._lock is None for store in self.opened))

    def test_bad_receipt_cleanup_and_resource_failures_release_real_lock(self):
        for failure in ('cleanup', 'receipt', 'resources'):
            with self.subTest(failure=failure):
                if failure == 'cleanup':
                    self.outcome.cleanup.leader_reaped = False
                elif failure == 'receipt':
                    self.pending.binding = {**self.pending.binding, 'sha256': '0' * 64}
                else:
                    self.capacity.f_favail = 0
                with self.assertRaises((executor.FixedActionExecutionError, custody.CustodyError)):
                    self.finish()
                self.assertIsNone(self.opened[-1]._lock)
                with self.f.store():
                    pass
                self.outcome.cleanup.leader_reaped = True
                self.pending.binding = asdict(self.f.checkpoint)
                self.capacity.f_favail = 100000

    def test_each_transaction_replays_prefix_and_failed_enter_releases_lock(self):
        self.assertEqual(self.finish(), asdict(self.outcome.receipt))
        path = self.f.root / 'ledger/0000000000000000.json'
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b'"FAMILY"', b'"FAMiLY"'))
        with self.assertRaisesRegex(custody.CustodyError, 'unknown ledger transition'):
            self.finish()
        self.assertEqual(len(self.opened), 2)
        self.assertTrue(all(store._lock is None for store in self.opened))


class StaticCopyTests(unittest.TestCase):
    def test_metadata_factory_preserves_all_shared_modules_and_executor_globals(self):
        original_globals, new_globals = dict(vars(original)), dict(vars(executor))
        modules = dict(sys.modules)
        adapted = metadata.make_executor(executor)
        self.assertEqual(original_globals, vars(original))
        self.assertEqual(new_globals, vars(executor))
        self.assertEqual(modules, sys.modules)
        self.assertIs(adapted._finish_archived_capture.__code__, executor._finish_archived_capture.__code__)
        self.assertIsNot(adapted._finish_archived_capture.__globals__, vars(executor))

    def test_static_copy_changes_only_cold_run_loop_and_added_helper(self):
        old = ast.parse((ROOT / 'tools/stage17_fixed_action_executor_v11.py').read_text())
        new = ast.parse((ROOT / 'tools/stage17_fixed_action_executor_v12.py').read_text())
        old_run = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == 'run_archived_worker')
        normalized = []
        for node in new.body:
            if isinstance(node, ast.Import) and [alias.name for alias in node.names] == ['contextlib']:
                continue
            if isinstance(node, ast.FunctionDef) and node.name == '_finish_archived_capture':
                continue
            if isinstance(node, ast.FunctionDef) and node.name == 'run_archived_worker':
                node = old_run
            normalized.append(node)
        new.body = normalized
        self.assertEqual(ast.dump(new), ast.dump(old))


class PrivateFlowCompositionTests(unittest.TestCase):
    def test_actual_composition_leaves_existing_module_globals_and_classes_unchanged(self):
        modules = (original, executor, custody, archive, metadata, metadata_v2, flow, flow.inventory)
        globals_before = [(module, dict(vars(module))) for module in modules]
        members_before = dict(vars(custody.ProgramStore))
        loaded_before = dict(sys.modules)
        flow.make_executor()
        flow.make_executor()
        for module, before in globals_before:
            self.assertEqual(before, vars(module), module.__name__)
        self.assertEqual(members_before, vars(custody.ProgramStore))
        self.assertEqual(loaded_before, sys.modules)

    def test_every_factory_call_has_independent_executor_and_store_namespaces(self):
        first, second = flow.make_executor(), flow.make_executor()
        first_scope, second_scope = first.execute_fixed_action.__globals__, second.execute_fixed_action.__globals__
        self.assertIsNot(first_scope, second_scope)
        self.assertIsNot(first.custody, second.custody)
        self.assertIsNot(first.archive, second.archive)
        self.assertIsNot(first.custody.ProgramStore, second.custody.ProgramStore)
        self.assertIsNot(first.custody.ProgramStore._read_bound.__globals__,
                         second.custody.ProgramStore._read_bound.__globals__)
        first_scope['composition_test_marker'] = object()
        self.assertNotIn('composition_test_marker', second_scope)
        self.assertNotIn('composition_test_marker', vars(executor))

    def test_all_executor_clones_are_v12_and_composed_store_keeps_v2_read_and_native_inventory(self):
        adapted = flow.make_executor()
        scope = adapted.execute_fixed_action.__globals__
        for name, function in vars(executor).items():
            if not isinstance(function, types.FunctionType) or function.__module__ != executor.__name__:
                continue
            with self.subTest(function=name):
                clone = getattr(adapted, name)
                self.assertIs(clone.__code__, function.__code__)
                self.assertIs(clone.__defaults__, function.__defaults__)
                self.assertIs(clone.__kwdefaults__, function.__kwdefaults__)
                self.assertIs(clone.__closure__, function.__closure__)
                self.assertIs(clone.__globals__, scope)
                self.assertIs(scope[name], clone)
                if hasattr(original, name):
                    self.assertIsNot(clone.__code__, getattr(original, name).__code__)
        store = adapted.custody.ProgramStore
        self.assertIs(scope['custody'].ProgramStore, store)
        self.assertIs(store._read_bound.__code__, metadata_v2._read_bound.__code__)
        self.assertIs(store._replay.__code__, custody.ProgramStore._replay.__code__)
        self.assertIs(store.physical_accounting, flow.inventory._physical_accounting)

    def test_finish_cloned_globals_open_composed_store_once_for_both_callbacks(self):
        adapted = flow.make_executor()
        scope, events = adapted._finish_archived_capture.__globals__, []
        store_class = adapted.custody.ProgramStore
        plan = dict(storage=dict(checkpoint_bytes=65536, program_scope_sha256='a' * 64))
        family = original.previous.sha256(archive.canonical(plan))
        request = dict(action_inputs=dict(plan=plan), evidence_root_binding=dict(
            absolute_path='/software-only/program/working/' + family))
        pending = SimpleNamespace(ordinal=0, document={'native_complete': True})
        deadline = time.monotonic_ns() + 60_000_000_000
        callback_scope = dict(owner=self, events=events, expected_class=store_class,
                              open_store=executor.open_store)
        exec('def receipt(request, pending, outcome, deadline):\n'
             '    with open_store(request, deadline) as store:\n'
             '        owner.assertIs(type(store), expected_class)\n'
             '        owner.assertTrue(store.composition_test_locked)\n'
             '        events.append(("receipt", store))\n'
             '    return {"receipt": "exact"}\n'
             'def resources(fd, extent, *, request, deadline_ns, ordinal=0):\n'
             '    with open_store(request, deadline_ns) as store:\n'
             '        owner.assertIs(type(store), expected_class)\n'
             '        owner.assertTrue(store.composition_test_locked)\n'
             '        events.append(("resources", store))\n', callback_scope)
        def entered(store):
            store.composition_test_locked = True
            events.append(('enter', store))
            return store
        def exited(store, *args):
            store.composition_test_locked = False
            events.append(('exit', store))
        # Stub filesystem entry only: the actual composed factory, constructor,
        # open_store body and cloned finish helper resolve their real globals.
        with mock.patch.object(store_class, '__enter__', entered), \
                mock.patch.object(store_class, '__exit__', exited), \
                mock.patch.dict(scope, _broker_receipt=callback_scope['receipt'],
                                live_resources=callback_scope['resources']):
            self.assertEqual(adapted._finish_archived_capture(request, pending, object(), deadline,
                directory_fd=7, extent=SimpleNamespace(captures=[object(), object()])), {'receipt': 'exact'})
        self.assertEqual([event for event, _ in events], ['enter', 'receipt', 'resources', 'exit'])
        self.assertTrue(all(store is events[0][1] for _, store in events))
        self.assertEqual(events[0][1].family_id, family)
        self.assertFalse(events[0][1].composition_test_locked)


class RunLoopTests(unittest.TestCase):
    """Exercise the real v12 loop with process/kernel transport boundaries faked."""
    def setUp(self):
        stack = self.enterContext(contextlib.ExitStack())
        self.events, self.stores = [], []
        self.failure = None
        self.pending = SimpleNamespace(ordinal=0, binding=dict(file_name='checkpoint.json',
            size_bytes=2, sha256='a' * 64), document=dict(native_complete=True, artifacts=[]),
            deadline_ns=time.monotonic_ns() + 60_000_000_000)
        self.request = dict(action_inputs=dict(plan=dict(storage=dict(program_scope_sha256='b' * 64,
            checkpoint_bytes=131072, broker_address_space_bytes=2 * 1024**3,
            codec_address_space_bytes=2 * 1024**3, per_capture_archive_ns=30_000_000_000))))
        context = executor.previous.predecessor._pin_generated(b'{}', 'V12_SOFTWARE_CONTEXT')
        self.addCleanup(context.close)
        temp = self.enterContext(tempfile.TemporaryDirectory())
        directory_fd = os.open(temp, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, directory_fd)
        self.argv = ['software-only-worker', '--context-fd', str(context.descriptor),
                     '--output-dir-fd', str(directory_fd)]
        self.pass_fds = (context.descriptor, directory_fd)
        owner = self
        class Store:
            root, scope_sha256, family_id = Path('/software-only/program'), 'b' * 64, 'c' * 64
            locked = False
            def __enter__(self):
                self.locked = True
                owner.events.append('enter')
                return self
            def __exit__(self, *args):
                self.locked = False
                owner.events.append('exit')
        def factory(*args):
            if self.failure == 'open' and len(self.stores) == 2:
                raise OSError('post-broker open failure')
            store = Store()
            self.stores.append(store)
            return store
        self.factory = mock.Mock(side_effect=factory)
        class Endpoint:
            def fileno(self): return 12345
            def close(self): pass
        parent, child = Endpoint(), Endpoint()
        class Selector:
            def __init__(self): self.mapping = {}
            def register(self, stream, mask, name):
                self.mapping[stream] = SimpleNamespace(fileobj=stream, data=name)
            def unregister(self, stream): del self.mapping[stream]
            def get_map(self): return self.mapping
            def select(self, timeout): return [(self.mapping[parent], None)]
            def close(self): self.mapping.clear()
        class Handoff:
            ordinal = 0
            def __init__(self, *args, **kwargs): pass
            def receive(self, **kwargs): return owner.pending
            def acknowledge(self, receipt, **kwargs):
                owner.events.append('ack')
                self.ordinal += 1
        class Broker:
            def __init__(self, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def archive_capture(self, **kwargs):
                # The controller's constructor-only lookup must not enter.
                owner.assertEqual(owner.events, [])
                with factory(owner.request, owner.pending.deadline_ns):
                    owner.events.append('broker')
                return object()
        self.lease = SimpleNamespace(identity_model=object(), enter=mock.Mock(), close=mock.Mock())
        pinned = SimpleNamespace(close=mock.Mock())
        process = SimpleNamespace(pid=12345)
        for name in ('stdout', 'stderr'):
            read_fd, write_fd = os.pipe()
            os.close(write_fd)
            stream = os.fdopen(read_fd, 'rb')
            self.addCleanup(stream.close)
            setattr(process, name, stream)
        cleanup = SimpleNamespace(returncode=0, leader_reaped=True, process_group_gone=True,
            cleanup_deadline_overrun=False, descendants_detected_after_leader_exit=False,
            terminal_cleanup_outcome='SOFTWARE_ONLY_DONE')
        self.cleanup = mock.Mock(return_value=cleanup)
        scope = dict(owner=self, open_store=executor.open_store)
        exec('def receipt(request, pending, outcome, deadline):\n'
             '    with open_store(request, deadline) as store:\n'
             '        owner.assertTrue(store.locked)\n'
             '        owner.events.append("receipt")\n'
             '        if owner.failure == "receipt": raise OSError("receipt failure")\n'
             '    return {"receipt": "software-only"}\n'
             'def resources(fd, extent, *, request, deadline_ns, ordinal=0):\n'
             '    with open_store(request, deadline_ns) as store:\n'
             '        owner.assertTrue(store.locked)\n'
             '        owner.events.append("resources")\n'
             '        if owner.failure == "resources": raise OSError("resources failure")\n', scope)
        import stage17_formal_archive_broker_v1 as broker_module
        patches = [(executor, 'open_store', self.factory),
            (executor, '_broker_receipt', scope['receipt']), (executor, 'live_resources', scope['resources']),
            (executor.channel, 'create_channel', lambda: (parent, child)),
            (executor.channel, 'ArchiveChannel', Handoff), (executor.selectors, 'DefaultSelector', Selector),
            (executor.subprocess, 'Popen', mock.Mock(return_value=process)),
            (executor, 'PinnedWorker', mock.Mock(return_value=pinned)),
            (executor.os, 'waitid', mock.Mock(side_effect=[None, object()])),
            (executor.transport_base.process_supervisor, 'SupervisorLease', lambda: self.lease),
            (executor.transport_base.process_supervisor, 'cleanup_process_group', self.cleanup),
            (broker_module, 'ArchiveBrokerClient', Broker)]
        for target, name, value in patches:
            stack.enter_context(mock.patch.object(target, name, value))

    def run_worker(self):
        deadline = time.monotonic_ns() + 60_000_000_000
        return executor.run_archived_worker(self.argv, self.pass_fds, global_deadline_ns=deadline,
            monotonic_expiry_ns=deadline, authority_guard=lambda: None, request=self.request,
            profile=object(), extent=SimpleNamespace(captures=[object(), object()]))

    def test_two_replays_one_broker_and_one_finish_before_acknowledgment(self):
        self.assertEqual(self.run_worker().returncode, 0)
        self.assertEqual(len(self.stores), 3)
        self.assertEqual(self.events, ['enter', 'broker', 'exit', 'enter', 'receipt', 'resources', 'exit', 'ack'])
        self.assertTrue(all(not store.locked for store in self.stores))
        self.assertFalse(self.cleanup.call_args.kwargs['force_stop'])
        self.lease.close.assert_called_once()

    def assert_failure_cleanup(self, failure):
        self.failure = failure
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.run_worker()
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)
        self.assertTrue(self.cleanup.call_args.kwargs['force_stop'])
        self.assertNotIn('ack', self.events)
        self.assertTrue(all(not store.locked for store in self.stores))
        self.lease.close.assert_called_once()

    def test_receipt_failure_forces_cleanup_without_ack(self):
        self.assert_failure_cleanup('receipt')

    def test_resource_failure_forces_cleanup_without_ack(self):
        self.assert_failure_cleanup('resources')

    def test_fresh_open_failure_forces_cleanup_without_ack(self):
        self.assert_failure_cleanup('open')

    def test_native_failure_follows_receipt_without_resources_or_ack(self):
        self.pending.document['native_complete'] = False
        self.assert_failure_cleanup(None)
        self.assertIn('receipt', self.events)
        self.assertNotIn('resources', self.events)


class ArchivedWorkerTests(worker_tests.ArchivedWorkerTests):
    def setUp(self):
        try:
            os.readlink('/proc/1/ns/pid')
            parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            with parent, child:
                parent.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        except OSError as error:
            self.skipTest(f'actual supervisor/channel prerequisites unavailable: {error}')
        # The sealed broker enforces the real 16-GiB reserve. /tmp may be a
        # smaller tmpfs; use the same disk-backed build area as broker tests.
        namespace = {**worker_tests.ArchivedWorkerTests.setUp.__globals__,
            'tempfile': SimpleNamespace(TemporaryDirectory=lambda: tempfile.TemporaryDirectory(
                prefix='executor-v12-', dir=ROOT / 'build'))}
        types.FunctionType(worker_tests.ArchivedWorkerTests.setUp.__code__, namespace)(self)

    # Reuse the real v11 fixture and assertions, changing only its worker target.
    run_worker = types.FunctionType(worker_tests.ArchivedWorkerTests.run_worker.__code__,
        {**worker_tests.ArchivedWorkerTests.run_worker.__globals__, 'executor': executor},
        argdefs=worker_tests.ArchivedWorkerTests.run_worker.__defaults__)
    run_worker.__kwdefaults__ = worker_tests.ArchivedWorkerTests.run_worker.__kwdefaults__

    def test_actual_success_constructs_two_controller_stores_but_enters_only_one(self):
        factory = executor.open_store
        transactions = []
        class Tracked:
            def __init__(self, store):
                self.store, self.enters, self.exits = store, 0, 0
            def __getattr__(self, name):
                return getattr(self.store, name)
            def __enter__(self):
                self.enters += 1
                return self.store.__enter__()
            def __exit__(self, *args):
                self.exits += 1
                return self.store.__exit__(*args)
        def opened(*args):
            tracked = Tracked(factory(*args))
            transactions.append(tracked)
            return tracked
        with mock.patch.object(executor, 'open_store', side_effect=opened):
            result = self.run_worker()
        self.assertEqual(result.returncode, 0)
        self.assertEqual([(item.enters, item.exits) for item in transactions], [(0, 0), (1, 1)])
        self.assertTrue(all(item.store._lock is None for item in transactions))

    def test_actual_post_broker_open_failure_keeps_worker_cleanup(self):
        factory = executor.open_store
        calls = 0
        def opened(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('post-broker fresh open failed')
            return factory(*args)
        with mock.patch.object(executor, 'open_store', side_effect=opened), \
                self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.run_worker()
        self.assertIn('post-broker fresh open failed', str(caught.exception))
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--encoder', type=Path)
    args, remaining = parser.parse_known_args()
    ArchivedWorkerTests.encoder = args.encoder
    unittest.main(argv=[sys.argv[0], *remaining])
