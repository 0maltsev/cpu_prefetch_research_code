"""Explicit v6 CLI and post-expiry custody; software fixtures, no stand."""
import ast
import copy
import datetime as dt
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import stage17_operational_cli_v18 as cli
import test_stage17_fixed_action_executor_v10 as executor_fixtures


class FormalCli(unittest.TestCase):
    def fixture(self, fail=False):
        helper = executor_fixtures.FormalSignedProcess()
        arguments, output = helper.prepare(fail=fail)
        self.addCleanup(helper.doCleanups)
        root = output.parent
        (root / 'journal').mkdir()
        (root / 'journal/stage17-state-journal-000000.json').write_text('{}')
        cli.journal.validate_operational_journal.return_value.resolutions['S17-EXT-002'].semantic_context['stand_id'] = 'synthetic-stand'
        return arguments, output

    def test_activation_and_ext001_successor_preserve_exact_body(self):
        import stage17_operational_cli_v17 as old
        predecessor_body = inspect.getsource(old.author_ext001_v17).replace('author_ext001_v17', 'author_ext001_v18').replace(
            'stage17-read-only-preflight-evidence-admission-policy-v31.json',
            'stage17-read-only-preflight-evidence-admission-policy-v32.json')
        self.assertEqual(ast.dump(ast.parse(predecessor_body)), ast.dump(ast.parse(inspect.getsource(cli.author_ext001_v18))))
        cli.activate()
        self.assertIs(cli.base.author_ext001, cli.author_ext001_v18)
        self.assertIs(cli.base.controller, cli.controller)
        self.assertIs(cli.base.journal_runtime, cli.journal)
        self.assertTrue(str(cli.journal.SEMANTIC_POLICY_PATH).endswith('-v58.json'))
        self.assertIs(cli.base.pilot_artifact.build_contract_v4, cli.release.build_contract_v12)
        self.assertEqual(cli.base.semantics_v6.ROLE_SCHEMA_v6, cli.operational.ROLE_SCHEMA_v16)

    def test_discovery_private_globals_do_not_rebind_historical_modules(self):
        old_registry, old_controller = cli.discovery_cli.registry, cli.discovery_cli.controller
        cli.activate()
        functions = cli._discovery_functions()
        self.assertIs(functions['registry'], cli.discovery_registry)
        self.assertIs(functions['controller'].journal_runtime, cli.journal)
        self.assertIs(functions['controller'].prepare_action, cli.controller.prepare_action)
        self.assertIs(cli.discovery_cli.registry, old_registry)
        self.assertIs(cli.discovery_cli.controller, old_controller)
        self.assertIs(functions['author_request'].__globals__, functions)

    def test_formal_authoring_rejects_nonformal_action_before_any_io(self):
        with self.assertRaises(cli.OperationalCliError):
            cli.author_formal_request(action_id='Q15-R',repository_root=ROOT,evidence_root=Path('/absent'),
                action_inputs_path=Path('/absent'),request_id='x',authorization_id='x',attempt_id='x',session_id='x',
                output_root=Path('/absent'),destination=Path('/absent'))

    def test_formal_entrypoints_never_delegate_v4_authority(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'authority.json'
            path.write_text('{"schema_version":"cpu-prefetch-stage17-phase-action-authorization/4"}')
            for function in (cli.verify_formal_signature, cli.execute_formal, cli.prepare_formal_retention):
                with self.subTest(function=function.__name__), self.assertRaises(cli.OperationalCliError):
                    function(authorization_path=path)

    def test_author_sign_execute_and_actual_expiry_retention(self):
        arguments, output = self.fixture()
        root = output.parent
        original = json.loads(arguments['authorization_path'].read_bytes())
        old_request = json.loads((root / 'request.json').read_bytes())
        inputs = root / 'inputs.json'
        inputs.write_bytes(cli.canonical(old_request['action_inputs']))
        request_path, authorization_path = root / 'formal-request.json', root / 'formal-authorization.json'
        common = dict(repository_root=ROOT,evidence_root=root,synthetic=True)
        cli.author_formal_request(**common,action_id='Q16a',action_inputs_path=inputs,request_id='request',
            authorization_id='auth',attempt_id='attempt',session_id='session',output_root=output,destination=request_path)
        self.assertEqual(request_path.read_bytes(),cli.canonical(old_request))
        now = dt.datetime.now(dt.timezone.utc)
        expiry = (now + dt.timedelta(seconds=45)).replace(microsecond=0)
        timestamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00','Z')
        cli.author_formal_authorization(**common,request_path=request_path,actor='software-owner',reviewer='OWNER',
            issued_at_utc=timestamp(now-dt.timedelta(seconds=1)),expires_at_utc=timestamp(expiry),destination=authorization_path)
        self.assertFalse(Path(str(authorization_path)+'.sig').exists(), 'authoring must not sign')
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(root/'key'),'-n','stage17-owner-acceptance',str(authorization_path)],
                       check=True,capture_output=True,timeout=10)
        arguments.update(authorization_path=authorization_path,signature_path=Path(str(authorization_path)+'.sig'))
        prepared = cli.verify_formal_signature(**arguments)
        self.assertEqual(prepared.request['schema_version'],'cpu-prefetch-stage17-fixed-action-request/6')
        outcome = cli.execute_formal(**arguments)
        self.assertTrue(outcome.completion['leader_reaped'] and outcome.completion['process_group_gone'])
        # Let the actual signed wall-clock expiry pass: no patched clock and no
        # edited authorization/completion records to manufacture expired custody.
        while (remaining := (expiry-dt.datetime.now(dt.timezone.utc)).total_seconds()) > 0:
            time.sleep(min(remaining + 0.02, 1))
        for function in (cli.verify_formal_signature, cli.execute_formal):
            with self.subTest(function=function.__name__), self.assertRaises(cli.controller.ControllerError):
                function(**arguments)
        retained = cli.prepare_formal_retention(**arguments)
        report = cli.admit_formal_retention(retained, output)
        self.assertEqual(len(report['captures']),708)
        self.assertEqual(report['scientific_validity'],'NOT_ASSESSED')
        self.assertFalse(report['execution_authority'])
        completion_path = outcome.completion_path
        original_completion = completion_path.read_bytes()
        completion = json.loads(original_completion)
        mutants = []
        bad = copy.deepcopy(completion);bad['resource_admission']['required_memory_bytes'] += 1;mutants.append(bad)
        bad = copy.deepcopy(completion);bad['leader_reaped'] = False;mutants.append(bad)
        bad = copy.deepcopy(completion);bad['live_restoration_readback'][0]['observed_hex'] = '0000000000000001';mutants.append(bad)
        bad = copy.deepcopy(completion);bad['result']['sha256'] = '0'*64;mutants.append(bad)
        try:
            for bad in mutants:
                completion_path.write_bytes(cli.canonical(bad))
                with self.assertRaises((cli.OperationalCliError,cli.registry.OutputAdmissionError)):
                    cli.admit_formal_retention(retained,output)
        finally:completion_path.write_bytes(original_completion)

    def test_real_failed_execution_cannot_admit_completed_retention(self):
        arguments, output = self.fixture(fail=True)
        with self.assertRaises(cli.executor.FixedActionExecutionError): cli.execute_formal(**arguments)
        prepared = cli.prepare_formal_retention(**arguments)
        with self.assertRaisesRegex(cli.OperationalCliError,'failed/quarantined'):
            cli.admit_formal_retention(prepared,output)


if __name__ == '__main__': unittest.main()
