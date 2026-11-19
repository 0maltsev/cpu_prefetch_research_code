"""D288 private /4 guard/source composition and legacy delegation."""
import inspect
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_compaction_integration_v1 as historical
import stage17_q16c_compaction_integration_v2 as current
import stage17_q16c_source_execution_v1 as old_sources
import stage17_q16c_source_execution_v2 as new_sources
import stage17_fixed_action_executor_v12 as transport
from test_stage17_formal_scheduled_continuation_v1 import parent_fixture,continuation_fixture


class CompositionTests(unittest.TestCase):
    def test_witness_and_platform_observation_bodies_remain_identical(self):
        for name in ('export_witness','ReadOnlyWitness'):
            self.assertIs(getattr(current,name),getattr(historical,name))
        self.assertTrue(issubclass(current.Observations,historical.Observations))

    def test_scoped_source_contract_includes_both_versions_without_global_mutation(self):
        original=dict(vars(old_sources));parent=parent_fixture();plan=continuation_fixture(parent)
        contract=new_sources.make_contract()
        contract.validate_plan('Q16c',parent);contract.validate_plan('Q16c',plan)
        with self.assertRaises(new_sources.ContractError):old_sources.make_contract().validate_plan('Q16c',plan)
        self.assertEqual(original,vars(old_sources))

    def test_guard_uses94_source_transport_and_original_cleanup_body(self):
        observations=types.SimpleNamespace(count=94,request_sha256='a'*64,plan_sha256='b'*64)
        value=current.make_executor(observations)
        execute=inspect.getclosurevars(value.execute_fixed_action).nonlocals['execute']
        base=inspect.getclosurevars(execute).nonlocals['base']
        self.assertIs(base.run_archived_worker.instrumented_runner.__code__,transport.run_archived_worker.__code__)
        with self.assertRaisesRegex(RuntimeError,'request binding differs'):
            value.execute_fixed_action(request=dict(action_id='Q16c',action_inputs=dict(plan={})))

    def test_existing_three_transport_receives_its_complete_original_bank(self):
        plan=parent_fixture();bindings=[dict(original=True)]*360
        dispatch=Mock(return_value='historical')
        with patch.object(new_sources.historical,'make_executor',return_value=types.SimpleNamespace(execute_fixed_action=dispatch)):
            result=new_sources.make_executor().execute_fixed_action(request=dict(action_id='Q16c',action_inputs=dict(plan=plan)),q16c_source_bindings=bindings)
        self.assertEqual(result,'historical')
        self.assertIs(dispatch.call_args.kwargs['q16c_source_bindings'],bindings)

    def test_live_resource_and_held_custody_paths_reserve_platform_metadata_without_changing_observed_capacity(self):
        observed=types.SimpleNamespace(count=94,request_sha256='a'*64,plan_sha256='b'*64)
        executor=current.make_executor(observed)
        execute=inspect.getclosurevars(executor.execute_fixed_action).nonlocals['execute']
        base=inspect.getclosurevars(execute).nonlocals['base'];custody=base.custody
        self.assertIs(base.live_resources.__globals__['custody'],custody)
        self.assertIs(base.open_store.__globals__['custody'],custody)
        snapshot=custody.CapacitySnapshot(10**13,1000,custody.PROGRAM_QUOTA-2*1024**2,0,0,0)
        space=custody.SpacePlan(0,0,0,0,1,0,1)
        before=vars(snapshot).copy()
        transport.custody.check_capacity(snapshot,space)
        with self.assertRaisesRegex(custody.CustodyError,'physical quota'):custody.check_capacity(snapshot,space)
        self.assertEqual(before,vars(snapshot))


if __name__=='__main__':unittest.main()
