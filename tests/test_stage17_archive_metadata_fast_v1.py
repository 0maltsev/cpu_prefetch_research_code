"""Cold-only private cloning, exact grammar, and real custody regression checks."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
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
            self.assertIs(clone.__code__, value.__code__)
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


if __name__ == '__main__':
    unittest.main()
