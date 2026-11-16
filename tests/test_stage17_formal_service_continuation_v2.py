"""Recomputed family time retains immutable qualified v1 and every capture."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_service_continuation_v1 as original
import stage17_formal_service_continuation_v2 as current
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.parent=parent_fixture();self.plan=continuation_fixture(self.parent)

    def test_only_suffix_watchdog_may_drop_completed_work(self):
        required=current.validate_plan(self.plan).required_watchdog_ns
        before=copy.deepcopy(self.parent)
        self.plan['budget']['watchdog_ns']=required
        current._compare_parent(self.plan,self.parent)
        self.assertEqual(self.parent,before)
        self.assertLess(required,self.parent['budget']['watchdog_ns'])
        with self.assertRaises(current.ContractError):original._compare_parent(self.plan,self.parent)

    def test_watchdog_bounds_and_all_other_family_fields_remain_enforced(self):
        required=current.validate_plan(self.plan).required_watchdog_ns
        for value in (required-1,self.parent['budget']['watchdog_ns']+1):
            self.plan['budget']['watchdog_ns']=value
            with self.subTest(watchdog=value),self.assertRaises(current.ContractError):
                current._compare_parent(self.plan,self.parent)
        self.plan['budget']['watchdog_ns']=required
        for field in ('cleanup_ns','setup_ns','analysis_scratch_bytes','disk_reserve_bytes'):
            plan=copy.deepcopy(self.plan);plan['budget'][field]+=1
            with self.subTest(field=field),self.assertRaises(current.ContractError):
                current._compare_parent(plan,self.parent)

    def test_original_function_and_globals_stay_bound_to_original_comparison(self):
        self.assertIs(original.validate_parent.__globals__['_compare_parent'],original._compare_parent)
        self.assertIs(current.validate_plan,original.validate_plan)
        for value in (self.parent,b'{}',b'[]'):
            with self.assertRaises(current.ContractError):current.validate_parent(self.plan,value)


if __name__=='__main__':unittest.main()
