"""D254 private integration using software fixtures only; no stand access."""
from __future__ import annotations

import ast
import copy
import hashlib
import inspect
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
import stage17_archive_flow_private_v1 as flow
import stage17_archive_inventory_native_v1 as inventory
import stage17_archive_metadata_fast_v1 as metadata
import stage17_fixed_action_executor_v10 as v10
import stage17_fixed_action_executor_v12 as v12
import stage17_formal_plan_v1 as native
import stage17_formal_plan_v2 as historical
import stage17_formal_service_daycap_v1 as daycap
import stage17_output_registry_v12 as original_registry
import stage17_service_daycap_execution_v1 as current
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_service_daycap_v1 import select_repetitions


def request_for(plan):
    return dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
                action_id='Q16b', action_inputs=dict(plan=plan))


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = select_repetitions(archived_fixture('Q16b'), 2)


class ContractTests(FixtureTests):
    def test_new_real_fixture_has_original_bytes_and_exact_120_extent(self):
        contract = current.make_contract()
        before = copy.deepcopy(self.plan)
        extent = contract.validate_plan('Q16b', self.plan)
        self.assertEqual(extent, daycap.validate_plan(self.plan))
        self.assertEqual(len(extent.captures), 120)
        self.assertEqual(extent.required_watchdog_ns, 120 * 12_000_000_000 + 2_000_000_000)
        self.assertLessEqual(extent.declared.watchdog_ns, 24 * 60 * 60 * 1_000_000_000)
        self.assertFalse(extent.execution_authority)
        self.assertEqual(before, self.plan)
        self.assertEqual(contract.VERSION, historical.VERSION)
        self.assertEqual(set(contract.VERSION), {'Q16a', 'Q16b', 'Q16c'})
        self.assertTrue(contract.is_archived_plan('Q16b', self.plan))
        self.assertTrue(current.is_archived(request_for(self.plan)))
        self.assertFalse(original_registry.is_archived(request_for(self.plan)))

    def test_every_historical_or_unsupported_document_is_delegated_by_identity(self):
        contract = current.make_contract()
        for action in ('Q16a', 'Q16b', 'Q16c', 'Q15-R', None):
            documents = [None, [], {}, {'schema_version': daycap.VERSION + '.1'}]
            if action in historical.VERSION:
                documents.extend({'schema_version': version} for version in (
                    native.VERSION[action], historical.VERSION[action], historical.CONTINUATION_VERSION))
            if action != 'Q16b':
                documents.append({'schema_version': daycap.VERSION})
            for document in documents:
                with self.subTest(action=action, document=document):
                    sentinel = object()
                    with mock.patch.object(historical, 'validate_plan', return_value=sentinel) as old:
                        self.assertIs(contract.validate_plan(action, document), sentinel)
                    self.assertIs(old.call_args.args[1], document)
                    old.assert_called_once_with(action, document)
        failure = historical.ContractError('historical failure')
        with mock.patch.object(historical, 'validate_plan', side_effect=failure):
            with self.assertRaises(historical.ContractError) as caught:
                contract.validate_plan('Q16c', {})
        self.assertIs(caught.exception, failure)

    def test_new_bad_method_fails_without_historical_reinterpretation(self):
        plan = copy.deepcopy(self.plan)
        plan['method_id'] = daycap.COLLECTOR_METHOD
        with mock.patch.object(historical, 'validate_plan', side_effect=AssertionError('historical fallback')):
            with self.assertRaises(daycap.ContractError):
                current.make_contract().validate_plan('Q16b', plan)

    def test_requested_300_native_240_archive_budget_keeps_30_second_drains(self):
        plan = copy.deepcopy(self.plan)
        second = 1_000_000_000
        for item in plan['captures']:
            for phase in item['capture']['budget']['phases']:
                phase['drain_ns'] = 30 * second
            item['execution_budget'].update(setup_ns=120 * second, publication_ns=90 * second,
                                           cleanup_ns=24 * second, watchdog_ns=300 * second)
        plan['storage']['per_capture_archive_ns'] = 240 * second
        plan['budget'].update(setup_ns=120 * second, cleanup_ns=120 * second,
                              watchdog_ns=65040 * second)
        before = copy.deepcopy(plan)
        extent = current.make_contract().validate_plan('Q16b', plan)
        self.assertEqual(extent.required_watchdog_ns, 65040 * second)
        self.assertEqual(extent.declared.watchdog_ns, (18 * 3600 + 4 * 60) * second)
        self.assertEqual({capture.required_watchdog_ns for capture in extent.captures}, {300 * second})
        self.assertEqual(plan, before)

    def test_historical_two_repetition_service_still_rejected_under_59_gate(self):
        for version in (native.VERSION['Q16b'], historical.VERSION['Q16b']):
            plan = copy.deepcopy(self.plan)
            plan.update(schema_version=version, method_id=daycap.COLLECTOR_METHOD)
            if version == native.VERSION['Q16b']:
                del plan['storage']
                plan['custody_policy_id'] = native.CUSTODY['Q16b']
            with self.subTest(version=version), self.assertRaisesRegex(historical.ContractError, '59'):
                current.make_contract().validate_plan('Q16b', plan)

    def test_archival_detection_preserves_old_formats_and_request_gate(self):
        contract = current.make_contract()
        for action in historical.VERSION:
            for version in (native.VERSION[action], historical.VERSION[action],
                            historical.CONTINUATION_VERSION, daycap.VERSION, 'unknown'):
                plan = dict(schema_version=version)
                expected = (action == 'Q16b' and version == daycap.VERSION
                            or historical.is_archived_plan(action, plan))
                self.assertEqual(contract.is_archived_plan(action, plan), expected)
                for request_version in ('/5', '/6', '/7'):
                    request = request_for(plan)
                    request.update(action_id=action,
                        schema_version='cpu-prefetch-stage17-fixed-action-request' + request_version)
                    self.assertEqual(current.is_archived(request), expected and request_version == '/6')
        for request in ({}, {'action_id': 'Q16b'}, request_for(None)):
            self.assertFalse(current.is_archived(request))


class NamespaceTests(unittest.TestCase):
    def test_execute_port_changes_only_local_imports_to_private_aliases(self):
        original = ast.parse(inspect.getsource(v12.execute_fixed_action)).body[0]
        adapted = ast.parse(inspect.getsource(current._execute_fixed_action)).body[0]
        original.body = original.body[2:]
        class PrivateRegistry(ast.NodeTransformer):
            def visit_Name(self, node):
                if node.id == 'registry':
                    node.id = 'output_registry'
                return node
        PrivateRegistry().visit(original)
        self.assertEqual([ast.dump(node) for node in original.body],
                         [ast.dump(node) for node in adapted.body])

    def test_registry_clones_all_local_functions_into_one_fresh_scope(self):
        contract = current.make_contract()
        registry = current.make_output_registry(contract)
        another = current.make_output_registry()
        scope = registry.is_archived.__globals__
        self.assertIs(scope['contract'], contract)
        self.assertIs(registry.contract, contract)
        self.assertIs(scope['archive'].canonical, fast.canonical)
        self.assertIs(scope['archive'].parse_json.__globals__['canonical'], fast.canonical)
        self.assertIsNot(scope, another.is_archived.__globals__)
        self.assertIsNot(registry.custody.ProgramStore, another.custody.ProgramStore)
        self.assertIs(registry.custody.ProgramStore.physical_accounting, inventory._physical_accounting)
        for name, original in vars(original_registry).items():
            if isinstance(original, types.FunctionType) and original.__module__ == original_registry.__name__:
                with self.subTest(function=name):
                    clone = getattr(registry, name)
                    self.assertIsNot(clone, original)
                    self.assertIs(clone.__code__, original.__code__)
                    self.assertIs(clone.__globals__, scope)
                    self.assertIs(scope[name], clone)
                    self.assertIs(clone.__defaults__, original.__defaults__)
                    self.assertIs(clone.__kwdefaults__, original.__kwdefaults__)
                    self.assertIs(clone.__closure__, original.__closure__)

    def test_executor_worker_finish_and_registry_use_private_composed_scope(self):
        executor = current.make_executor()
        another = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        self.assertIs(scope['plans'], executor.plans)
        self.assertIs(scope['is_archived'], executor.output_registry.is_archived)
        self.assertIs(executor.output_registry.contract, executor.plans)
        self.assertIs(executor.output_registry.custody, executor.custody)
        self.assertIs(scope['custody'], executor.custody)
        self.assertIsNot(executor.custody.ProgramStore, another.custody.ProgramStore)
        self.assertIsNot(scope, another.execute_fixed_action.__globals__)
        for name, original in vars(v12).items():
            if (isinstance(original, types.FunctionType) and original.__module__ == v12.__name__
                    and name != 'execute_fixed_action'):
                clone = getattr(executor, name)
                self.assertIs(clone.__globals__, scope)
                self.assertIs(clone.__code__, original.__code__)
                self.assertIs(scope[name], clone)
        self.assertEqual(inspect.signature(executor.execute_fixed_action), inspect.signature(v12.execute_fixed_action))

    def test_factories_do_not_change_original_globals_classes_or_sources(self):
        modules = (historical, original_registry, v10, v12, metadata, flow, daycap)
        snapshots = [(module, dict(vars(module)), Path(module.__file__).read_bytes()) for module in modules]
        old_version, old_schema = dict(historical.VERSION), dict(historical.SCHEMA)
        original_store = original_registry.custody.ProgramStore
        store_methods = dict(vars(original_store))
        for _ in range(2):
            contract = current.make_contract()
            contract.VERSION['Q16b'] = 'private mutation'
            contract.SCHEMA['Q16b'] = 'private mutation'
            current.make_output_registry()
            current.make_executor()
        self.assertEqual(historical.VERSION, old_version)
        self.assertEqual(historical.SCHEMA, old_schema)
        self.assertEqual(dict(vars(original_store)), store_methods)
        for module, snapshot, source in snapshots:
            self.assertEqual(dict(vars(module)), snapshot, module.__name__)
            self.assertEqual(Path(module.__file__).read_bytes(), source)


class MetadataTests(FixtureTests):
    def setUp(self):
        self.registry = current.make_output_registry()
        self.pinned = self.registry.pin_registry(ROOT)
        temporary = self.enterContext(tempfile.TemporaryDirectory(prefix='d254-private-metadata-'))
        self.root = Path(temporary)
        self.fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.fd)

    def inputs(self):
        registry = self.registry
        request = request_for(self.plan)
        request.update(request_id='software-request', stand_id='software-stand',
            authorization_id='software-auth', attempt_id='software-attempt', runtime_binding={},
            release_binding={}, predecessor_resolutions=['a', 'b', 'c'])
        hardware = dict(mapping_id='software-mapping', prestate=[
            dict(cpu=cpu, complete_value_hex='0000000000000000') for cpu in (0, 1, 8)])
        request['action_inputs']['hardware_control'] = hardware
        artifacts, captures = [], []
        for ordinal in range(120):
            bindings = []
            for name in (*registry.capture_names('Q16b', ordinal),
                         f'formal-capture-{ordinal}-final-checkpoint.json',
                         f'formal-capture-{ordinal}-archive-custody.json'):
                role, schema, media = registry.artifact_identity('Q16b', name)
                item = dict(role=role, schema_identity=schema, media_type=media,
                    file_name=name, size_bytes=0, sha256=hashlib.sha256(b'').hexdigest())
                artifacts.append(item)
                bindings.append(registry.reference(item))
            captures.append(dict(ordinal=ordinal, native_complete=True, artifacts=bindings[:-2],
                                 checkpoint=bindings[-2], archive_custody=bindings[-1]))
        report = dict(schema_version='cpu-prefetch-stage17-formal-retention-report/2',
            action_id='Q16b', plan_sha256=registry.plan_sha256(self.plan), mapping_id=hardware['mapping_id'],
            whole_plots=[dict(state='H0', apply_readback=[], restore_readback=[], restoration_verified=True),
                dict(state='H1', apply_readback=[dict(cpu=cpu, complete_value_hex='000000000000000f')
                    for cpu in (0, 1, 8)], restore_readback=list(reversed(hardware['prestate'])),
                    restoration_verified=True)], captures=captures,
            native_results_after_cleanup=[dict(software_fixture=True) for _ in captures],
            restoration_verified=True, mandatory_failure=False, scientific_validity='NOT_ASSESSED',
            execution_authority=False, phase18_authority=False)
        raw = registry.archive.canonical(report)
        (self.root / registry.REPORT_NAME).write_bytes(raw)
        role, schema, media = registry.artifact_identity('Q16b', registry.REPORT_NAME)
        artifacts.append(dict(role=role, schema_identity=schema, media_type=media,
            file_name=registry.REPORT_NAME, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        result = dict(schema_version='cpu-prefetch-stage17-phase-action-result/6', result_id='software-result',
            **{key: request[key] for key in ('request_id', 'action_id', 'stand_id', 'authorization_id',
                'attempt_id', 'runtime_binding', 'release_binding', 'predecessor_resolutions')},
            request_sha256=registry.sha256(registry.canonical(request)), authorization_sha256='c' * 64,
            artifacts=artifacts, started_at_utc='2030-01-01T00:00:00Z', completed_at_utc='2030-01-01T00:00:01Z',
            duration_ns=1_000_000_000, terminal_state='FORMAL_ARTIFACTS_RETAINED_UNASSESSED',
            restoration_verified=True, quarantined=False, synthetic_test_only=True, phase18_authority=False)
        return dict(registry=self.pinned, directory_fd=self.fd, request=request, result=result,
                    authorization_sha256='c' * 64, synthetic_test_only=True)

    def test_original_metadata_body_accepts_complete_new_120_family(self):
        values = self.inputs()
        plan, extent, report = self.registry._metadata(**values)
        self.assertIs(plan, self.plan)
        self.assertEqual(len(extent.captures), 120)
        self.assertEqual(len(report['captures']), 120)
        self.assertFalse(report['execution_authority'])
        self.assertTrue(self.registry.canonical(values['request']).endswith(b'\n'))
        self.assertFalse(self.registry.archive.canonical(plan).endswith(b'\n'))
        with self.assertRaises(original_registry.OutputAdmissionError):
            original_registry._metadata(**values)

    def test_new_metadata_requires_exact_artifact_inventory(self):
        values = self.inputs()
        values['result']['artifacts'].pop(-2)
        with self.assertRaisesRegex(original_registry.OutputAdmissionError, 'inventory is not exact'):
            self.registry._metadata(**values)

    def test_metadata_profile_check_uses_new_extent_before_filesystem_admission(self):
        runtime = original_registry.runtime
        image = runtime.ImageBinding(Path('/software-only/unused-image'), 1, 'e' * 64)
        profile = runtime.RuntimeProfile(image, image,
            types.SimpleNamespace(implementation_profile_sha256='f' * 64), ())
        with self.assertRaisesRegex(original_registry.OutputAdmissionError, 'implementation profile'):
            self.registry.verify_archived_formal_metadata(**self.inputs(), repository_root=ROOT,
                archive_runtime_profile=profile, deadline_ns=time.monotonic_ns() + 60_000_000_000)


def wrapped_v10(*, repository_root, authorization, authorization_bytes, request, request_bytes,
                worker_binding, worker_path, release_binding, output_root, synthetic_test_only=False):
    """Transport-only fake; the adapter clones this just as it clones v10."""
    calls.append(dict(locals()))
    extent = contract.validate_plan(request['action_id'], request['action_inputs']['plan'])
    calls.append(extent)
    calls.append(live_resources(37, extent))
    calls.append(_run_formal_worker(('software-only-worker',), (9,),
        global_deadline_ns=123, monotonic_expiry_ns=122, authority_guard=authority_guard))
    calls.append(output_registry.validate_worker_result(registry='pinned', directory_fd=37,
        result={'software_only': True}, request=request, authorization_sha256='c' * 64,
        synthetic_test_only=synthetic_test_only))
    return result_token


class ExecutorTests(FixtureTests):
    def arguments(self, request=None):
        return dict(repository_root=ROOT, authorization={'signed': True}, authorization_bytes=b'auth\n',
            request=request_for(self.plan) if request is None else request, request_bytes=b'request\n',
            worker_binding={'original': 'worker'}, worker_path=Path('/software-only/worker'),
            release_binding={'original': 'release'}, output_root=Path('/software-only/working/family'),
            synthetic_test_only=True)

    def test_new_extent_and_original_arguments_reach_wrapped_v10_and_private_hooks(self):
        executor = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        calls, token, guard = [], object(), mock.Mock()
        fake = metadata._clone(wrapped_v10, {**wrapped_v10.__globals__,
            'calls': calls, 'result_token': token, 'authority_guard': guard})
        previous = types.SimpleNamespace(**{**vars(v10), 'execute_fixed_action': fake})
        arguments = self.arguments()
        profile = types.SimpleNamespace(decoder=types.SimpleNamespace(implementation_profile_sha256='a' * 64))
        with mock.patch.dict(scope, previous=previous, live_resources=mock.Mock(return_value='resources'),
                run_archived_worker=mock.Mock(return_value='worker')), \
                mock.patch.object(executor.output_registry, 'verify_archived_formal_metadata',
                                  return_value='metadata') as verify:
            self.assertIs(executor.execute_fixed_action(archive_runtime_profile=profile, **arguments), token)
            resource_args = scope['live_resources'].call_args
            worker_args = scope['run_archived_worker'].call_args
        self.assertEqual(calls[0], arguments)
        self.assertIs(calls[0]['request'], arguments['request'])
        self.assertEqual(len(calls[1].captures), 120)
        self.assertEqual(calls[1], daycap.validate_plan(self.plan))
        self.assertEqual(calls[2:], ['resources', 'worker', 'metadata'])
        self.assertEqual(resource_args.args, (37, calls[1]))
        self.assertIs(resource_args.kwargs['request'], arguments['request'])
        self.assertEqual(worker_args.kwargs['extent'], calls[1])
        self.assertIs(worker_args.kwargs['profile'], profile)
        self.assertIs(worker_args.kwargs['authority_guard'], guard)
        self.assertEqual(worker_args.kwargs['global_deadline_ns'], 123)
        self.assertEqual(worker_args.kwargs['monotonic_expiry_ns'], 122)
        self.assertEqual(verify.call_args.kwargs['deadline_ns'], resource_args.kwargs['deadline_ns'])
        self.assertIs(verify.call_args.kwargs['request'], arguments['request'])
        self.assertIs(verify.call_args.kwargs['archive_runtime_profile'], profile)
        self.assertEqual(verify.call_args.kwargs['repository_root'], ROOT)

    def test_wrong_profile_rejected_before_wrapped_v10_or_worker(self):
        executor = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        previous = types.SimpleNamespace(execute_fixed_action=mock.Mock(side_effect=AssertionError('v10 entered')))
        profile = types.SimpleNamespace(decoder=types.SimpleNamespace(implementation_profile_sha256='f' * 64))
        with mock.patch.dict(scope, previous=previous, run_archived_worker=mock.Mock()) as patched:
            with self.assertRaises(v12.FixedActionExecutionError) as caught:
                executor.execute_fixed_action(archive_runtime_profile=profile, **self.arguments())
            self.assertEqual(caught.exception.category, 'ARCHIVE_PROFILE')
            previous.execute_fixed_action.assert_not_called()
            patched['run_archived_worker'].assert_not_called()

    def test_ordinary_historical_call_delegates_unchanged_without_profile_access(self):
        executor = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        previous = types.SimpleNamespace(execute_fixed_action=mock.Mock(return_value='historical'))
        for request in ({'schema_version': 'cpu-prefetch-stage17-fixed-action-request/5'},
                        request_for({'schema_version': native.VERSION['Q16b']})):
            arguments = self.arguments(request)
            with mock.patch.dict(scope, previous=previous):
                self.assertEqual(executor.execute_fixed_action(archive_runtime_profile=None, **arguments), 'historical')
            previous.execute_fixed_action.assert_called_with(**arguments)


def receipt_callback(request, pending, outcome, deadline):
    with open_store(request, deadline) as store:
        events.append(('receipt', store, store.locked))
        saved.append(open_store)
    return {'receipt': 'private'}


def resources_callback(fd, extent, *, request, deadline_ns, ordinal=0):
    with open_store(request, deadline_ns) as store:
        events.append(('resources', store, store.locked))


class FinishTests(unittest.TestCase):
    def test_unchanged_finish_binds_callbacks_to_our_private_transaction(self):
        executor = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        request, outcome, events, saved = {}, object(), [], []
        pending = types.SimpleNamespace(ordinal=0, document=dict(native_complete=True))
        extent = types.SimpleNamespace(captures=[object(), object()])
        deadline = time.monotonic_ns() + 60_000_000_000
        class Store:
            locked = False
            def __enter__(self):
                self.locked = True
                events.append(('enter', self, self.locked))
                return self
            def __exit__(self, *args):
                self.locked = False
                events.append(('exit', self, self.locked))
        store = Store()
        factory = mock.Mock(return_value=store)
        scope.update(events=events, saved=saved)
        with mock.patch.dict(scope, open_store=factory,
                _broker_receipt=metadata._clone(receipt_callback, scope),
                live_resources=metadata._clone(resources_callback, scope)), \
                mock.patch.object(v12, 'open_store', side_effect=AssertionError('original scope used')):
            self.assertEqual(executor._finish_archived_capture(request, pending, outcome, deadline,
                directory_fd=37, extent=extent), {'receipt': 'private'})
        factory.assert_called_once_with(request, deadline)
        self.assertEqual([event[0] for event in events], ['enter', 'receipt', 'resources', 'exit'])
        self.assertTrue(all(event[1] is store for event in events))
        self.assertTrue(events[1][2] and events[2][2])
        self.assertFalse(store.locked)
        with self.assertRaisesRegex(v12.FixedActionExecutionError, 'transaction ended'):
            saved[0](request, deadline)


if __name__ == '__main__':
    unittest.main()
