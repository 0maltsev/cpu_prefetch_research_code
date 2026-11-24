"""Explicit v6 CLI and post-expiry custody; software fixtures, no stand."""
import ast
import copy
import datetime as dt
import inspect
import io
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests')]
import stage17_operational_cli_v18 as cli
import test_stage17_fixed_action_executor_v10 as executor_fixtures


class LegacyQ15Cli(unittest.TestCase):
    """Actual CLI/parser/schema/signature preparation, synthetic journal only.

    No worker, hardware access or archival codec is executed. Temporary local
    keys are exclusively software fixtures and cannot authorize the stand.
    """
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='q15-cli-preparation-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / 'repository'
        self.repository.mkdir()
        shutil.copytree(ROOT / 'config', self.repository / 'config')
        (self.repository / 'BUNDLE_MANIFEST.json').write_text(json.dumps(dict(
            bundle_profile='STAGE17-HERMETIC-DRY-RUN-BUNDLE-v8',
            stage17_fixed_action_runtime={'synthetic_test_only': True},
            pilot_authorized=False, confirmatory_authorized=False)))
        self.output = self.root / 'output'; self.output.mkdir(mode=0o700)
        (self.root / 'journal').mkdir()
        (self.root / 'journal/stage17-state-journal-000000.json').write_text('{}')
        self.key = self.root / 'software-key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],
                       check=True,capture_output=True,timeout=10)
        allowed = self.root / 'allowed-signers'
        allowed.write_text('software-owner '+self.key.with_suffix('.pub').read_text())
        trust = dict(subject_id='software-stand', measurements=dict(principal='software-owner',
            reviewer_role='OWNER',sshsig_namespace='stage17-owner-acceptance',
            allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest()))
        self.runtime = dict(worker_path=str(self.root/'never-executed-worker'),worker_size_bytes=123,
            worker_sha256='a'*64,worker_role='STAGE17_FIXED_ACTION_WORKER',
            runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4',supported_actions=[
                'Q15-R','Q15-W','Q16a','Q16b','Q16c','STAGE17-BLINDED-PILOT','Q16A-DURATION-DISCOVERY'])
        resolutions = {f'S17-EXT-{i:03d}':SimpleNamespace(input_id=f'S17-EXT-{i:03d}',
            resolution_id=f'SOFTWARE-RESOLUTION-{i}',sha256=str(i)*64,semantic_context={})
            for i in range(1,7)}
        resolutions['S17-EXT-002'].semantic_context={'stand_id':'software-stand'}
        resolutions['S17-EXT-003'].semantic_context={'trust':trust,'runtime':{'measurements':self.runtime}}
        resolutions['S17-EXT-006'].semantic_context={'bundle_profile':'STAGE17-PILOT-CANDIDATE-BUNDLE-v26'}
        self.validation = SimpleNamespace(current_state='PREFLIGHT_ACCEPTED',resolutions=resolutions)
        self.enterContext(patch.object(cli.journal,'validate_operational_journal',return_value=self.validation))
        self.no_execution = self.enterContext(patch.object(cli.controller,'execute_once',
            side_effect=AssertionError('preparation must never execute a worker')))
        self.no_archive = self.enterContext(patch.object(cli.controller,'qualified_archive_profile',
            side_effect=AssertionError('Q15 must not enter formal archive admission')))

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ['stage17_operational_cli_v18.py','--repository-root',str(self.repository),
                '--evidence-root',str(self.root),'--synthetic-test-only',*map(str,args)]
        with patch.object(sys,'argv',argv), redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli.main()
        return result, stdout.getvalue()+stderr.getvalue()

    def inputs(self, action):
        if action=='Q15-R':
            return dict(qualification_id='SOFTWARE-Q15R',attempt_id='SOFTWARE-Q15-R-ATTEMPT',
                session_id='SOFTWARE-SESSION',probe_platform_binding=dict(cpu=0,numa_node=0,
                    verified_base_page_bytes=4096,verified_local_llc_bytes=26214400))
        return dict(q15_r_attempt_sha256='b'*64,q15_r_result_sha256='c'*64,
            session_id='SOFTWARE-SESSION',prestate=[dict(cpu=0,complete_value_hex='0000000000000000')])

    def request(self, action, inputs=None, expected_error=None):
        path=self.root/(action+'-inputs.json')
        path.write_bytes(cli.canonical(self.inputs(action) if inputs is None else inputs))
        request=self.root/(action+'-request.json')
        result, text=self.invoke('author-request','--action',action,'--action-inputs',path,
            '--request-id','SOFTWARE-'+action+'-REQUEST','--session-id','SOFTWARE-SESSION',
            '--authorization-id','SOFTWARE-'+action+'-AUTH','--attempt-id','SOFTWARE-'+action+'-ATTEMPT',
            '--output-root',self.output,'--output',request)
        if expected_error is None:
            self.assertEqual(result,0,text)
        else:
            self.assertNotEqual(result,0,text)
            self.assertIn(expected_error,text)
            self.assertFalse(request.exists())
        return request

    def authorize(self, action, request):
        now=dt.datetime.now(dt.timezone.utc)
        stamp=lambda value:value.isoformat(timespec='seconds').replace('+00:00','Z')
        authorization=self.root/(action+'-authorization.json')
        result,text=self.invoke('author-authorization','--request',request,'--actor','software-owner',
            '--reviewer','OWNER','--issued-at-utc',stamp(now-dt.timedelta(seconds=1)),
            '--expires-at-utc',stamp(now+dt.timedelta(seconds=120)),'--output',authorization)
        self.assertEqual(result,0,text)
        signature=Path(str(authorization)+'.sig')
        self.assertFalse(signature.exists(),'authoring signed implicitly')
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.key),'-n',
            'stage17-owner-acceptance',str(authorization)],check=True,capture_output=True,timeout=10)
        return authorization,signature

    def test_both_q15_actions_author_sign_verify_through_current_cli_without_execution(self):
        for action in ('Q15-R','Q15-W'):
            with self.subTest(action=action):
                request=self.request(action)
                document=json.loads(request.read_bytes())
                self.assertEqual(document['schema_version'],'cpu-prefetch-stage17-fixed-action-request/4')
                self.assertEqual(document['release_binding']['source_resolution_id'],'SOFTWARE-RESOLUTION-3')
                self.assertEqual(document['runtime_binding']['sha256'],self.runtime['worker_sha256'])
                authorization,signature=self.authorize(action,request)
                result,text=self.invoke('verify-signature','--authorization',authorization,'--signature',signature)
                self.assertEqual(result,0,text)
                self.assertIn('signature=VERIFIED action=NOT_EXECUTED',text)
        self.no_execution.assert_not_called()
        self.no_archive.assert_not_called()
        self.assertEqual(list(self.output.iterdir()),[])

    def test_missing_legacy_callbacks_reproduces_original_cli_failure(self):
        # Reproduce the two original missing exports through the actual CLI;
        # no production bytes or historical module globals are rewritten.
        for name in ('_runtime_from_context', '_validate_action_inputs'):
            with self.subTest(callback=name):
                callback = getattr(cli.controller, name)
                try:
                    delattr(cli.controller, name)
                    self.request('Q15-R', expected_error="has no attribute '"+name+"'")
                finally:
                    setattr(cli.controller, name, callback)
        self.no_execution.assert_not_called()

    def test_incomplete_action_inputs_fail_before_request_publication(self):
        for action in ('Q15-R','Q15-W'):
            values=self.inputs(action);values.pop('session_id')
            with self.subTest(action=action):
                self.request(action,values,expected_error='production action input family is incomplete/expanded')
            self.assertFalse((self.root/(action+'-request.json')).exists())

    def test_changed_signature_and_missing_q15w_dependency_fail_closed(self):
        request=self.request('Q15-R')
        authorization,signature=self.authorize('Q15-R',request)
        authority=json.loads(authorization.read_bytes());authority['retain_partial']=False
        authorization.write_bytes(cli.canonical(authority))
        result,text=self.invoke('verify-signature','--authorization',authorization,'--signature',signature)
        self.assertNotEqual(result,0,text)
        self.validation.resolutions.pop('S17-EXT-004')
        self.request('Q15-W',expected_error='action predecessor resolution is absent')
        self.assertFalse((self.root/'Q15-W-request.json').exists())
        self.no_execution.assert_not_called()


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
