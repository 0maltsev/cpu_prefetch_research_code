"""D260 complete private graph and mandatory prefix gate; software only."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_administration_v1 as current
import stage17_phase_controller_daycap_v2 as qualified
import stage17_phase_controller_daycap_v1 as historical
import stage17_archive_daycap_overlay_v1 as overlay
import stage17_service_daycap_execution_v1 as old_execution
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class ControllerTests(unittest.TestCase):
    def test_whole_graph_uses_fresh_qualified_journal_and_103_contract(self):
        view=current.make_controller()
        self.assertIs(view.journal_runtime,qualified.journal)
        self.assertIs(view._v25.journal_runtime,qualified.journal)
        self.assertIs(view._v26.previous,view._v25)
        self.assertIs(view._v26._prepare_action.__globals__['_validate_inputs'],view._validate_inputs)
        self.assertIs(view.prepare_action.__globals__['_v26'],view._v26)
        self.assertEqual(len(view.contract.validate_plan('Q16b',continuation_fixture(parent_fixture())).captures),103)
        self.assertIs(view.make_executor,current.execution.make_executor)

    def test_distinct_private_descriptor_and_historical_context_per_controller(self):
        left,right=current.make_controller(),current.make_controller()
        self.assertIsNot(left.overlay,right.overlay)
        self.assertIsNone(left.overlay._CONFIG)
        self.assertIsNone(right.overlay._CONFIG)
        self.assertIsNot(left.configure_verified_descriptor.__globals__,right.configure_verified_descriptor.__globals__)
        self.assertIsNone(left._HISTORICAL)
        self.assertIsNone(right._HISTORICAL)
        self.assertIs(left.overlay.qualified_profile.__code__,overlay.qualified_profile.__code__)

    def test_unsupported_plan_never_attempts_prefix_or_native_execution(self):
        view=current.make_controller()
        for plan in ({},parent_fixture()):
            request=dict(action_id='Q16b',action_inputs=dict(plan=plan))
            with mock.patch.object(current.prefix,'admit',side_effect=AssertionError('prefix must not run')):
                with self.assertRaises(view.ControllerError):view._validate_inputs(request,object())

    def test_prefix_failure_propagates_after_actual_prior_validator(self):
        view=current.make_controller();plan=continuation_fixture(parent_fixture())
        request=dict(action_id='Q16b',action_inputs=dict(plan=plan))
        prior=view._validate_inputs.__closure__
        # Original input validator remains a real mandatory dependency; replace
        # only its internal v25 seam to test failure routing without a stand.
        extent=view.contract.validate_plan('Q16b',plan)
        with mock.patch.object(view._v25,'_with_globals',return_value=extent) as inputs:
            with mock.patch.object(current.prefix,'admit',side_effect=ValueError('failed original17')):
                with self.assertRaisesRegex(ValueError,'failed original17'):
                    view._validate_inputs(request,object())
            inputs.assert_called_once()

    def test_historical_and_qualification_modules_remain_unmodified(self):
        before=(historical.contract,historical.registry,historical.overlay,overlay._CONFIG,
                old_execution.make_contract,qualified._CONTROLLER)
        cli=current.make_cli()
        self.assertIs(cli.author_formal_request.__globals__['controller'],cli.controller)
        self.assertIs(cli.author_formal_request.__globals__['registry'],cli.registry)
        self.assertEqual(before,(historical.contract,historical.registry,historical.overlay,overlay._CONFIG,
                old_execution.make_contract,qualified._CONTROLLER))


if __name__=='__main__':unittest.main()
