"""Fresh private routing, original graph parity and prefix-failure propagation."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_administration_v2 as current
import test_stage17_service_continuation_administration_v1 as original
from test_stage17_formal_service_continuation_v1 import parent_fixture,continuation_fixture


class ControllerTests(unittest.TestCase):
    def test_diagnostic_failure_propagates_through_private_full_graph(self):
        view=current.make_controller();plan=continuation_fixture(parent_fixture())
        extent=view.contract.validate_plan('Q16b',plan)
        with mock.patch.object(view._v25,'_with_globals',return_value=extent):
            with mock.patch.object(current.prefix,'admit',side_effect=ValueError('D265 failed')) as gate:
                with self.assertRaisesRegex(ValueError,'D265 failed'):
                    view._validate_inputs(dict(action_id='Q16b',action_inputs=dict(plan=plan)),object())
                gate.assert_called_once()
        self.assertIs(view._v26._prepare_action.__globals__['_validate_inputs'],view._validate_inputs)

    def test_cli_routes_to_private_controller_without_mutating_originals(self):
        before=current.previous.make_controller.__globals__['prefix']
        cli=current.make_cli()
        self.assertIs(cli.author_formal_request.__globals__['controller'],cli.controller)
        self.assertIs(current.previous.make_controller.__globals__['prefix'],before)
        self.assertIsNot(before,current.prefix)
        self.assertIs(cli.controller.journal_runtime,current.previous.qualification.journal)
        self.assertIsNone(cli.controller.overlay._CONFIG)


if __name__=='__main__':unittest.main()
