"""Real declaration/dispatch checks; no stand or experimental execution."""
import copy
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_execution_v1 as current
import stage17_service_daycap_execution_v1 as previous
import stage17_formal_service_continuation_v1 as declaration
import stage17_formal_service_daycap_v1 as daycap
from test_stage17_formal_service_continuation_v1 import parent_fixture, continuation_fixture


class ExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = parent_fixture()
        cls.plan = continuation_fixture(cls.parent)

    def test_actual_extent_contains_only_103_new_captures(self):
        before = copy.deepcopy(self.plan)
        extent = current.make_contract().validate_plan('Q16b', self.plan)
        self.assertEqual(extent, declaration.validate_plan(self.plan))
        self.assertEqual([e.ordinal for e in extent.captures], list(range(103)))
        self.assertFalse(extent.execution_authority)
        self.assertEqual(before, self.plan)
        self.assertEqual(current.make_contract().validate_plan('Q16b', self.parent),
                         daycap.validate_plan(self.parent))

    def test_malformed_continuation_cannot_fall_back_to_historical_method(self):
        for mutate in (lambda p: p['captures'].pop(),
                       lambda p: p['continuation'].update(original_first_ordinal=16),
                       lambda p: p['continuation'].update(future_retries=1)):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.assertRaises(declaration.ContractError):
                current.make_contract().validate_plan('Q16b', plan)

    def test_original_action_and_document_are_delegated_unchanged(self):
        original = previous.make_contract()
        sentinel = object()
        for action, document in [('Q16a', {}), ('Q16c', {}), ('Q16b', None),
                                 ('Q16b', {'schema_version': declaration.VERSION+'.1'})]:
            with mock.patch.object(previous, 'make_contract', return_value=original):
                with mock.patch.object(original, 'validate_plan', return_value=sentinel) as call:
                    self.assertIs(current.make_contract().validate_plan(action, document), sentinel)
                    self.assertIs(call.call_args.args[1], document)
                    call.assert_called_once_with(action, document)

    def test_executor_finish_registry_and_worker_use_same_private_contract(self):
        executor = current.make_executor()
        scope = executor.execute_fixed_action.__globals__
        self.assertIs(scope['plans'], executor.plans)
        self.assertIs(scope['output_registry'], executor.output_registry)
        self.assertIs(scope['is_archived'], executor.is_archived)
        registry_scope = executor.output_registry._metadata.__globals__
        self.assertIs(registry_scope['contract'], executor.plans)
        self.assertEqual(len(executor.plans.validate_plan('Q16b', self.plan).captures), 103)
        request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
                       action_id='Q16b', action_inputs=dict(plan=self.plan))
        self.assertTrue(executor.is_archived(request))
        request['schema_version'] = 'cpu-prefetch-stage17-fixed-action-request/5'
        self.assertFalse(executor.is_archived(request))

    def test_original_contract_and_global_dispatch_still_reject_continuation(self):
        original = previous.make_contract()
        registry = previous.original_registry.contract
        before = dict(vars(registry))
        current.make_executor()
        self.assertEqual(before, vars(registry))
        with self.assertRaises(declaration.ContractError):
            original.validate_plan('Q16b', self.plan)
        with self.assertRaises(declaration.ContractError):
            registry.validate_plan('Q16b', self.plan)


if __name__ == '__main__':
    unittest.main()
