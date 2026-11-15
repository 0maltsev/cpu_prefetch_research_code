"""Cold-only private cloning, exact grammar, and real custody regression checks."""
from __future__ import annotations

from dataclasses import replace
from contextlib import contextmanager
import os
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import stage17_archive_canonical_fast_v1 as fast
import stage17_archive_metadata_fast_v1 as adapter
import stage17_fixed_action_executor_v11 as executor
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_v1 as archive
import test_stage17_formal_archive_custody_v1 as original_tests
from test_stage17_formal_archive_v1 import codec_limit, digest

ORIGINAL_STORE = custody.ProgramStore


@contextmanager
def scandir_stat_override(callback):
    """Test-only DirEntry stat seam; leave every real directory traversal intact."""
    original_scandir = os.scandir
    class Entry:
        def __init__(self, entry):
            self.entry = entry
        def __getattr__(self, name):
            return getattr(self.entry, name)
        def stat(self, *, follow_symlinks=True):
            return callback(self.entry, follow_symlinks=follow_symlinks)
    @contextmanager
    def scan(path):
        with original_scandir(path) as entries:
            yield (Entry(entry) for entry in entries)
    with mock.patch.object(os, 'scandir', scan):
        yield


class CloneTests(unittest.TestCase):
    def test_store_class_and_original_globals_are_unchanged(self):
        original_globals = dict(vars(custody))
        original_members = dict(vars(ORIGINAL_STORE))
        modules = dict(sys.modules)
        store = adapter.make_store_class(base=ORIGINAL_STORE)
        self.assertTrue(issubclass(store, ORIGINAL_STORE))
        self.assertEqual(original_globals, vars(custody))
        self.assertEqual(original_members, vars(ORIGINAL_STORE))
        self.assertEqual(modules, sys.modules)
        scope = store.__init__.__globals__
        self.assertIs(scope['ProgramStore'], store)
        self.assertIsNot(scope, vars(custody))
        self.assertIsNot(scope['archive'], archive)
        self.assertIs(scope['archive'].canonical, fast.canonical)
        self.assertIs(scope['archive'].parse_json.__code__, archive.parse_json.__code__)
        self.assertIs(scope['archive'].parse_json.__globals__['canonical'], fast.canonical)
        for name, value in original_globals.items():
            if name not in ('archive', 'ProgramStore'):
                self.assertIs(scope[name], value)
        for name, value in original_members.items():
            if isinstance(value, types.FunctionType):
                clone = vars(store)[name]
            elif isinstance(value, staticmethod):
                clone, value = vars(store)[name].__func__, value.__func__
            else:
                continue
            self.assertIsNot(clone, value)
            self.assertIs(clone.__code__, adapter._physical_accounting.__code__
                          if name == 'physical_accounting' else value.__code__)
            self.assertIs(clone.__closure__, value.__closure__)
            self.assertIs(clone.__defaults__, value.__defaults__)
            self.assertIs(clone.__kwdefaults__, value.__kwdefaults__)
            self.assertIs(clone.__globals__, scope)

    def test_each_factory_call_has_an_independent_private_scope(self):
        first, second = adapter.make_store_class(), adapter.make_store_class()
        self.assertIsNot(first, second)
        self.assertIsNot(first.__init__.__globals__, second.__init__.__globals__)
        self.assertIsNot(first.__init__.__globals__['archive'], second.__init__.__globals__['archive'])

    def test_property_staticmethod_classmethod_and_closure_preserved(self):
        scope = dict(vars(custody))
        exec('def static(value=7): return archive.canonical({"value": value})\n'
             'def class_method(cls): return cls\n'
             'def getter(self): return archive.canonical({"value": 8})\n'
             'def setter(self, value): self.saved = value\n'
             'def deleter(self): del self.saved\n', scope)
        def enclosing(captured):
            def closure(self, *, label='preserved'):
                return captured, label
            return closure
        original_closure = enclosing(object())
        base = type('DescriptorStore', (ORIGINAL_STORE,), dict(
            static=staticmethod(scope['static']), class_method=classmethod(scope['class_method']),
            value=property(scope['getter'], scope['setter'], scope['deleter']),
            closure=original_closure))
        clone = adapter.make_store_class(base=base)
        instance = object.__new__(clone)
        self.assertEqual(clone.static(), b'{"value":7}')
        self.assertIs(clone.class_method(), clone)
        self.assertEqual(instance.value, b'{"value":8}')
        instance.value = 9
        self.assertEqual(instance.saved, 9)
        del instance.value
        self.assertFalse(hasattr(instance, 'saved'))
        self.assertIs(clone.closure.__closure__, original_closure.__closure__)
        self.assertEqual(instance.closure(), original_closure(instance))
        for accessor in (clone.value.fget, clone.value.fset, clone.value.fdel):
            self.assertIs(accessor.__globals__, clone.__init__.__globals__)

    def test_parse_grammar_and_error_behavior_are_exact(self):
        parse = adapter.make_store_class().__init__.__globals__['archive'].parse_json
        cases = [b'{}', b'{"a":1}', b'{"a":true,"b":null}',
                 b'{"a":1.25}', '{"😀":1,"\ue000":2}'.encode(),
                 b'{ "a":1}', b'{"a":1}\n', b'{"a":1,"a":2}', b'[]',
                 b'{"a":NaN}', b'{"a":Infinity}', b'{"a":18446744073709551616}',
                 b'{"a":-9223372036854775809}', b'{"a":"\xff"}', b'not json']
        def outcome(function, raw):
            try:
                return ('return', function(raw))
            except Exception as error:
                return ('raise', type(error), str(error))
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(outcome(parse, raw), outcome(archive.parse_json, raw))

    def test_executor_callbacks_share_private_globals_without_global_mutation(self):
        before = dict(vars(executor))
        adapted = adapter.make_executor(executor)
        self.assertEqual(before, vars(executor))
        scope = adapted.execute_fixed_action.__globals__
        for name in ('_broker_receipt', 'open_store', 'live_resources', 'custody_limits',
                     'run_archived_worker', 'execute_fixed_action'):
            original, clone = getattr(executor, name), getattr(adapted, name)
            self.assertIs(clone.__code__, original.__code__)
            self.assertIs(clone.__closure__, original.__closure__)
            self.assertIs(clone.__defaults__, original.__defaults__)
            self.assertIs(clone.__kwdefaults__, original.__kwdefaults__)
            self.assertIs(clone.__globals__, scope)
            self.assertIs(scope[name], clone)
        self.assertTrue(issubclass(adapted.custody.ProgramStore, ORIGINAL_STORE))
        for name, value in vars(executor).items():
            if name not in ('archive', 'custody') and not (
                    isinstance(value, types.FunctionType) and value.__module__ == executor.__name__):
                self.assertIs(getattr(adapted, name), value)
        self.assertIsNot(adapter.make_executor(executor).execute_fixed_action.__globals__, scope)

    def test_open_store_uses_private_store_and_limits_callback_and_keeps_path_gate(self):
        adapted = adapter.make_executor(executor)
        plan = dict(storage=dict(program_scope_sha256='a' * 64, checkpoint_bytes=131072))
        family = digest(archive.canonical(plan))
        request = dict(action_inputs=dict(plan=plan), evidence_root_binding=dict(
            absolute_path='/software-only/program/working/' + family))
        deadline = time.monotonic_ns() + 10**9
        scope = adapted.open_store.__globals__
        limits = custody.CustodyLimits(131072, 100, 100, 131072, deadline)
        with mock.patch.dict(scope, custody_limits=mock.Mock(return_value=limits)):
            result = adapted.open_store(request, deadline)
            scope['custody_limits'].assert_called_once_with(plan['storage'], deadline)
        self.assertIs(type(result), adapted.custody.ProgramStore)
        self.assertIs(result.limits, limits)
        request['evidence_root_binding']['absolute_path'] = '/software-only/wrong/' + family
        with self.assertRaises(executor.FixedActionExecutionError):
            adapted.open_store(request, deadline)

    def test_executor_historical_dispatch_and_archive_profile_gate_preserved(self):
        adapted = adapter.make_executor(executor)
        request = dict(action_id='Q15', schema_version='historical')
        with mock.patch.object(executor.previous, 'execute_fixed_action', return_value='historical') as prior:
            self.assertEqual(adapted.execute_fixed_action(archive_runtime_profile=None, request=request), 'historical')
            prior.assert_called_once_with(request=request)
        request = dict(action_id='Q16b', schema_version='cpu-prefetch-stage17-fixed-action-request/6',
            action_inputs=dict(plan=dict(schema_version='cpu-prefetch-stage17-formal-service-plan/2',
                storage=dict(implementation_profile_sha256='a' * 64))))
        profile = types.SimpleNamespace(decoder=types.SimpleNamespace(implementation_profile_sha256='b' * 64))
        with mock.patch.object(executor.plans, 'validate_plan', return_value=object()):
            with self.assertRaisesRegex(executor.FixedActionExecutionError, 'qualified runtime differs'):
                adapted.execute_fixed_action(archive_runtime_profile=profile, request=request)


class FastCustodyRegressionTests(original_tests.CustodyTests):
    """Run every historical custody regression through the private subclass."""
    def setUp(self):
        fast_store = adapter.make_store_class(base=ORIGINAL_STORE)
        patch = mock.patch.object(custody, 'ProgramStore', fast_store)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_allocation_pressure_hardlink_dedup_and_write_rounding(self):
        # The unchanged historical assertion injects st_blocks through Path.stat.
        # Route only this test's DirEntry.stat through that same injection, so
        # its allocation-pressure and write-rounding assertions remain intact.
        with scandir_stat_override(lambda entry, **kwargs: Path(entry.path).stat(**kwargs)):
            super().test_allocation_pressure_hardlink_dedup_and_write_rounding()

    def test_every_ledger_record_is_reopened_without_replay_cache(self):
        with self.f.store() as store:
            for ordinal in range(3):
                store.record_failure(None, operation='software-test', detail=str(ordinal))
        expected = sorted((self.f.root / 'ledger').iterdir())
        for _ in range(2):
            store = self.f.store()
            with mock.patch.object(store, '_read_bound', wraps=store._read_bound) as read:
                with store:
                    observed = [call.args[0] for call in read.call_args_list
                                if call.args[0].parent == self.f.root / 'ledger']
                    self.assertEqual(observed, expected)
                    self.assertEqual(store._sequence, len(expected))

    def test_one_family_two_artifacts_full_replay_and_release(self):
        f = self.f
        second_data = b'second independent original\x00\xff'
        second_path = f.working / 'second.bin'
        second_path.write_bytes(second_data)
        second_header, second_role = f.f.header(second_data, 'bytes')
        second_id = f.family + ':second.bin'
        second_header['artifact_id'] = second_id
        second_source = custody.SourceBinding(second_id,
            custody.BoundFile(second_path.name, len(second_data), digest(second_data)),
            archive.PhysicalBinding(len(second_data), digest(second_data)), None)
        checkpoint_path = f.working / f.checkpoint.file_name
        checkpoint = archive.parse_json(checkpoint_path.read_bytes())
        checkpoint['artifacts'].append(dict(file_name=second_path.name,
            size_bytes=len(second_data), sha256=digest(second_data)))
        raw = archive.canonical(checkpoint)
        checkpoint_path.write_bytes(raw)
        f.checkpoint = replace(f.checkpoint, size_bytes=len(raw), sha256=digest(raw))
        wire = f.f.encode(second_data, second_header)
        with f.store() as store:
            store.prepare_family(f.family)
            store.begin_capture(f.checkpoint, (f.source, second_source), verify_checkpoint=f.callback)
            f.reserve(store)
            f.publish(store)
            f.release(store)
            staging = store.reserve_archive(second_id, staging_name='second.staging',
                                             maximum_archive_bytes=len(wire) + 1024)
            staging.write_bytes(wire)
            with codec_limit():
                store.verify_and_publish(second_id, archive_name='second.cpfa',
                    expected_header=second_header, role=second_role,
                    physical=archive.PhysicalBinding(len(wire), digest(wire)),
                    profile=f.f.profile, limits=f.f.limits)
                store.release_working_copy(second_id, profile=f.f.profile, limits=f.f.limits)
            sequence = store._sequence
        with f.store() as reopened:
            self.assertEqual(reopened._sequence, sequence)
            self.assertEqual(len(reopened._record_bindings), sequence)
            self.assertEqual(len(reopened._families), 1)
            self.assertEqual(reopened.reserved_bytes(), 0)
            for artifact in (f.artifact_id, second_id):
                self.assertEqual(reopened._states[artifact]['kind'], 'RELEASED')
            for bound in reopened._record_bindings:
                reopened.read_verified_record(bound)
        self.assertFalse(f.original.exists())
        self.assertFalse(second_path.exists())
        self.assertEqual((f.root / 'archives/second.cpfa').read_bytes(), wire)

    def test_chain_corruption_and_changed_root_admission_still_fail_closed(self):
        path = self.f.root / 'ledger/0000000000000000.json'
        document = archive.parse_json(path.read_bytes())
        document['previous_sha256'] = 'f' * 64
        path.write_bytes(archive.canonical(document))
        with self.assertRaisesRegex(custody.CustodyError, 'ledger chain differs'):
            with self.f.store():
                pass
        with self.assertRaisesRegex(custody.CustodyError, 'program scope changed'):
            with custody.ProgramStore(self.f.root, scope_sha256='f' * 64,
                    family_id=self.f.family, limits=self.f.limits):
                pass


class InventoryOracleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with mock.patch.object(os, 'statvfs', return_value=types.SimpleNamespace(
                f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100_000)):
            self.f = original_tests.CustodyFixture(self.temp.name)
        self.fast = adapter.make_store_class(base=ORIGINAL_STORE)

    def store(self, limits=None):
        return self.fast(self.f.root, scope_sha256=self.f.scope, family_id=self.f.family,
                         limits=limits or self.f.limits)

    def compare(self, store):
        # The oracle is the actual original function, never a second rewrite.
        expected = ORIGINAL_STORE.physical_accounting(store)
        actual = store.physical_accounting()
        self.assertEqual(actual, expected)
        return actual

    def compare_failure(self, store, error=Exception, message=None):
        with self.assertRaises(error) as original:
            ORIGINAL_STORE.physical_accounting(store)
        with self.assertRaises(type(original.exception)) as optimized:
            store.physical_accounting()
        self.assertEqual(str(optimized.exception), str(original.exception))
        if message is not None:
            self.assertIn(message, str(optimized.exception))

    def test_real_sparse_hardlinks_and_exact_directory_and_receipt_accounting(self):
        f = self.f
        (f.root / 'archives/empty').write_bytes(b'')
        dense = f.root / 'metadata/dense'
        dense.write_bytes(bytes(range(256)) * 33)
        os.link(dense, f.root / 'archives/hardlink')
        sparse = f.root / 'metadata/sparse'
        with sparse.open('wb') as stream:
            stream.seek(8 * 1024**2)
            stream.write(b'x')
        native = f.working / 'formal-capture-12-final-checkpoint.json'
        native.write_bytes(b'native checkpoint')
        native_custody = f.working / 'formal-capture-12-archive-custody.json'
        native_custody.write_bytes(b'native custody')
        retained = f.working / 'bound-native.json'
        retained.write_bytes(b'retained native receipt')
        # Existing working raw, spool and release-hold payloads have their
        # original workspace exemption, while the directories remain charged.
        (f.working / 'ignored-raw').write_bytes(b'workspace payload')
        (f.root / 'spool/ignored').write_bytes(b'analysis workspace')
        (f.root / 'release-hold/ignored').write_bytes(b'held workspace')
        with self.store() as store:
            store._retained_receipts.add((f.family, retained.name))
            store._retained_receipts.add((f.family, native_custody.name))
            result = self.compare(store)
            paths = [f.root, *(f.root / name for name in store.DIRECTORIES), f.working,
                     f.root / 'scope.json', f.root / 'broker.lock',
                     *(f.root / 'archives').iterdir(), *(f.root / 'metadata').iterdir(),
                     *(f.root / 'ledger').iterdir(), native, native_custody, retained]
            unique = {(st.st_dev, st.st_ino): st for st in
                      (path.stat(follow_symlinks=False) for path in paths)}
            self.assertEqual(result.unique_objects, len(unique))
            self.assertEqual(result.logical_size_bytes, sum(st.st_size for st in unique.values()))
            self.assertEqual(result.allocated_bytes, sum(st.st_blocks * 512 for st in unique.values()))
            self.assertEqual(result.quota_bytes, sum(max(st.st_size, st.st_blocks * 512)
                                                     for st in unique.values()))

    def test_working_raw_inventory_and_physical_inventory_exact_limits(self):
        for index in range(4):
            (self.f.working / f'raw-{index}').write_bytes(b'raw')
        with self.store() as store:
            working_count = len(list(self.f.working.iterdir()))
            total_count = working_count + sum(len(list((self.f.root / name).iterdir()))
                                            for name in ('archives', 'metadata', 'ledger'))
            store.limits = replace(store.limits, max_inventory_files=total_count)
            self.compare(store)
            store.limits = replace(store.limits, max_inventory_files=total_count - 1)
            self.compare_failure(store, custody.CustodyError, 'physical inventory limit')
            store.limits = replace(store.limits, max_inventory_files=working_count - 1)
            self.compare_failure(store, custody.CustodyError, 'working inventory limit')

    def test_nonregular_inventory_objects_are_rejected_without_following_symlinks(self):
        for area, kind in [('archives', 'symlink'), ('metadata', 'directory'),
                           ('archives', 'fifo'), ('working', 'symlink'), ('working', 'fifo')]:
            with self.subTest(area=area, kind=kind):
                path = (self.f.working / 'formal-capture-4-archive-custody.json'
                        if area == 'working' else self.f.root / area / 'unexpected')
                if kind == 'symlink':
                    path.symlink_to(self.f.root / 'scope.json')
                elif kind == 'fifo':
                    os.mkfifo(path)
                else:
                    path.mkdir()
                try:
                    with self.store() as store:
                        self.compare_failure(store, custody.CustodyError, 'unexpected physical inventory object')
                finally:
                    path.rmdir() if kind == 'directory' else path.unlink()

    def test_bad_working_namespace_and_wrong_working_directory_type(self):
        invalid = self.f.root / 'working/not-a-sha'
        invalid.mkdir()
        with self.store() as store:
            self.compare_failure(store, archive.ArchiveError, 'working family namespace')
        invalid.rmdir()
        wrong = self.f.root / 'working' / ('f' * 64)
        wrong.symlink_to(self.f.working, target_is_directory=True)
        with self.store() as store:
            self.compare_failure(store, custody.CustodyError, 'unexpected physical inventory object')

    def test_retained_receipts_keep_name_type_missing_and_dedup_checks(self):
        receipt = self.f.working / 'retained.json'
        receipt.write_bytes(b'exact receipt')
        with self.store() as store:
            store._retained_receipts.add((self.f.family, receipt.name))
            self.compare(store)
            receipt.unlink()
            self.compare_failure(store, FileNotFoundError)
            receipt.symlink_to(self.f.root / 'scope.json')
            self.compare_failure(store, custody.CustodyError, 'unexpected physical inventory object')
            store._retained_receipts = {(self.f.family, '../unsafe')}
            self.compare_failure(store, custody.CustodyError, 'unsafe scoped file name')

    def test_no_per_entry_path_stat_and_all_accounted_entries_are_freshly_statted(self):
        for index in range(10):
            (self.f.root / 'metadata' / f'file-{index}').write_bytes(bytes([index]))
        seen = []
        def observe(entry, **kwargs):
            self.assertEqual(kwargs, dict(follow_symlinks=False))
            seen.append(entry.path)
            return entry.stat(**kwargs)
        with self.store() as store:
            actual_path_stat = Path.stat
            with scandir_stat_override(observe), \
                 mock.patch.object(Path, 'stat', autospec=True, side_effect=actual_path_stat) as path_stat:
                first = store.physical_accounting()
                first_seen = list(seen)
                second = store.physical_accounting()
                self.assertEqual(first, second)
                self.assertEqual(seen, first_seen + first_seen)
                self.assertTrue(first_seen)
                paths = {call.args[0] for call in path_stat.call_args_list}
                expected_entries = {str(path) for name in ('archives', 'metadata', 'ledger')
                                    for path in (self.f.root / name).iterdir()}
                self.assertTrue(expected_entries.issubset(set(first_seen)))
                self.assertFalse({Path(path) for path in expected_entries}.intersection(paths))

    def test_original_root_and_deadline_checks_precede_inventory(self):
        with self.store() as store:
            store.limits = replace(store.limits, deadline_ns=time.monotonic_ns() - 1)
            with mock.patch.object(os, 'scandir', side_effect=AssertionError('inventory before _check')):
                self.compare_failure(store, custody.CustodyError, 'custody deadline expired')

    def test_replaced_directory_identity_is_rejected_before_inventory(self):
        with self.store() as store:
            working = self.f.root / 'working'
            moved = self.f.root / 'original-working'
            working.rename(moved)
            working.mkdir()
            try:
                with mock.patch.object(os, 'scandir', side_effect=AssertionError('inventory before _check')):
                    self.compare_failure(store, custody.CustodyError,
                                         'program directory changed or crossed filesystem')
            finally:
                working.rmdir()
                moved.rename(working)

    def test_checked_allocated_and_logical_arithmetic_remains_bounded(self):
        target = self.f.root / 'metadata/checked-arithmetic'
        target.write_bytes(b'x')
        actual_stat = Path.stat
        target_inode = actual_stat(target).st_ino
        for field, value in [('st_blocks', (1 << 64) // 512),
                             ('st_size', (1 << 64) - 1), ('st_blocks', -1)]:
            with self.subTest(field=field, value=value), self.store() as store:
                def injected(path, **kwargs):
                    st = actual_stat(path, **kwargs)
                    if st.st_ino != target_inode:
                        return st
                    fields = {key: getattr(st, key) for key in
                              ('st_dev', 'st_ino', 'st_size', 'st_blocks', 'st_mode')}
                    fields[field] = value
                    return types.SimpleNamespace(**fields)
                with mock.patch.object(Path, 'stat', injected), \
                     scandir_stat_override(lambda entry, **kwargs: Path(entry.path).stat(**kwargs)):
                    self.compare_failure(store, archive.ArchiveError)


if __name__ == '__main__':
    unittest.main()
