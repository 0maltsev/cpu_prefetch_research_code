"""Scoped CLI dispatch checks; signature/schema gates use preserved bodies."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_operational_cli_v20 as cli


class FormalDispatchTests(unittest.TestCase):
    def test_v27_selected_in_every_private_formal_body_without_legacy_mutation(self):
        original = {name: getattr(cli.previous, name) for name in cli.FUNCTIONS}
        scope = cli.formal_functions()
        for name in cli.FUNCTIONS:
            self.assertIs(scope[name].__globals__['controller'], cli.controller)
            self.assertIs(scope[name].__globals__['_validation'], scope['_validation'])
            self.assertIs(getattr(cli.previous, name), original[name])
        self.assertEqual(cli.previous.controller.__name__, 'stage17_phase_controller_v26')

    def test_verification_execution_and_retention_keep_v6_authority_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'authorization.json'
            controller = SimpleNamespace(prepare_action=Mock(return_value='prepared'),
                execute_once=Mock(return_value='executed'), prepare_retention=Mock(return_value='retained'))
            with patch.object(cli, 'activate') as activate, patch.object(cli, 'controller', controller):
                path.write_text(json.dumps(dict(schema_version='wrong')))
                for operation in (cli.verify_formal_signature, cli.execute_formal, cli.prepare_formal_retention):
                    with self.assertRaises(cli.previous.OperationalCliError):
                        operation(authorization_path=path)
                for callback in vars(controller).values():
                    callback.assert_not_called()
                path.write_text(json.dumps(dict(schema_version='cpu-prefetch-stage17-phase-action-authorization/6')))
                self.assertEqual(cli.verify_formal_signature(authorization_path=path), 'prepared')
                self.assertEqual(cli.execute_formal(authorization_path=path), 'executed')
                self.assertEqual(cli.prepare_formal_retention(authorization_path=path), 'retained')
                for callback in vars(controller).values():
                    callback.assert_called_once_with(authorization_path=path)
                self.assertEqual(activate.call_count, 6)

    def test_accepted_journal_adapter_activated_after_preserved_runtime(self):
        observed = []
        with patch.object(cli.previous, 'activate', side_effect=lambda: observed.append('original')), \
             patch.object(cli.recovery, 'activate', side_effect=lambda: observed.append('D242')):
            cli.activate()
        self.assertEqual(observed, ['original', 'D242'])

    def test_nonformal_commands_delegate_to_existing_administrative_cli(self):
        for argv in (['tool'], ['tool', 'd242-check'], ['tool', 'status']):
            with patch.object(sys, 'argv', argv), patch.object(cli.administrative_previous, 'main', return_value=17) as previous:
                self.assertEqual(cli.main(), 17)
                previous.assert_called_once_with()

    def test_formal_cli_routes_into_the_new_preserved_namespace(self):
        with patch.object(sys, 'argv', ['tool', 'execute-formal']), \
             patch.object(cli, 'formal_functions', return_value={'main': Mock(return_value=23)}) as functions:
            self.assertEqual(cli.main(), 23)
            functions.return_value['main'].assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
