"""Actual authoring/verification policy sharing; native budget remains intact."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_administration_v3 as current
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class AuthorityBudgetTests(unittest.TestCase):
    def test_author_and_verifier_use_same_bounded_margin_without_native_changes(self):
        cli=current.make_cli();view=cli.controller
        plan=continuation_fixture(parent_fixture());plan['budget']['watchdog_ns']=55860*10**9
        plan['budget']['cleanup_ns']=2*10**9
        extent=view.contract.validate_plan('Q16b',plan)
        policy=view.deadline_policy(extent)
        self.assertEqual(policy['session_max_wall_seconds'],57600)
        self.assertEqual(extent.declared.watchdog_ns,55860*10**9)
        self.assertIs(view._v25._prepare_action.__globals__['deadline_policy'],view.deadline_policy)
        self.assertIs(cli.author_formal_authorization.__globals__['controller'].deadline_policy,view.deadline_policy)
        old=current.previous.previous.association.original_controller.original_v25.deadline_policy(extent)
        self.assertEqual(old['session_max_wall_seconds'],55860)
        self.assertEqual({k:v for k,v in policy.items() if k!='session_max_wall_seconds'},
                         {k:v for k,v in old.items() if k!='session_max_wall_seconds'})
    def test_different_extent_cannot_select_margin(self):
        view=current.make_controller();plan=parent_fixture()
        with self.assertRaisesRegex(current.previous.previous.association.original_controller.ControllerError,'exact103'):
            view.deadline_policy(view.contract.validate_plan('Q16b',plan))


if __name__=='__main__':unittest.main()
