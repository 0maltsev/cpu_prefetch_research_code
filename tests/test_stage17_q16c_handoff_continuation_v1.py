"""D306 authority, preserved signed artifacts and the actual rendered handoff."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_q16c_handoff_continuation_v1 as current
import stage17_q16c_continuation_operator_v1 as io
import test_stage17_q16c_saved_request_v1 as saved_tests

EVIDENCE = ROOT/'docs/evidence/stage17/Q16C-D301-D302-HANDOFF-STOP-20261120-01'


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.approval = json.loads((ROOT/'docs/evidence/stage17/Q16C-D306-ACCEPTED-20261120-01/owner-acceptance.json').read_bytes())

    def test_exact_approval_and_rendered_parent(self):
        current.parent_verified(); current.validate_acceptance(self.approval)
        proposal = (ROOT/'docs/decisions/0306-q16c-handoff-stop-continuation-proposal.md').read_bytes()
        self.assertEqual(hashlib.sha256(proposal).hexdigest(), current.PROPOSAL_SHA)
        for key, value in [('new_execution_windows', 1), ('manual_continuations', 2), ('owner_message', 'continue'),
                           ('remaining_capture_count', 93), ('maximum_remaining_seconds', 31461),
                           ('admitted_day_deadline_monotonic_ns', current.SIGNED_DAY_DEADLINE+1)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                current.validate_acceptance({**self.approval, key: value})

    def test_deadline_still_requires_full_envelope_and_no_default_exception(self):
        with self.assertRaises(ValueError):
            current.check_time(current.ORIGINAL_DEADLINE-current.ENVELOPE)
        cutoff = 1605164784571258
        with patch.object(current, 'runtime_deadline', return_value=current.SIGNED_DAY_DEADLINE):
            current.check_time(cutoff-1, {})
            with self.assertRaises(ValueError): current.check_time(cutoff, {})

    def test_metadata_clone_retains_d306_source_identity_and_admission_functions(self):
        f = current._function(current.saved._metadata_function, [("== 'D301'", "== 'D306'")])()
        self.assertEqual(f.__globals__['__file__'], current.__file__)
        self.assertIs(f.__globals__['validate_saved_state'], current.validate_saved_state)
        self.assertIs(f.__globals__['validate_acceptance'], current.validate_acceptance)
        self.assertEqual(f.__globals__['PROPOSAL_SHA'], current.PROPOSAL_SHA)
        self.assertIs(f.__globals__['verify_supplement'], current.verify_supplement)


class RenderTests(unittest.TestCase):
    def test_actual_collection_function_uses_the_new_prepared_paths(self):
        text = textwrap.dedent(inspect.getsource(saved_tests.HandoffTests.test_rendered_collection_uses_the_actual_prepared_authority))
        text = text.replace('d301', 'd306')
        namespace = {**saved_tests.HandoffTests.test_rendered_collection_uses_the_actual_prepared_authority.__globals__, 'current': current}
        exec(compile(text, 'D306-real-collection-fixture', 'exec'), namespace)
        namespace['test_rendered_collection_uses_the_actual_prepared_authority'](self)

    def test_no_unresolved_names_or_native_scientific_changes(self):
        namespace = {**saved_tests.HandoffTests.test_rendered_scripts_have_no_unresolved_global_name_like_auth.__globals__, 'current': current}
        text = textwrap.dedent(inspect.getsource(saved_tests.HandoffTests.test_rendered_scripts_have_no_unresolved_global_name_like_auth))
        exec(compile(text, 'D306-rendered-names', 'exec'), namespace)
        namespace['test_rendered_scripts_have_no_unresolved_global_name_like_auth'](self)
        for name in current.saved.previous.FROZEN:
            raw = (ROOT/'tools'/name).read_bytes()
            expected = current.saved.render(name, raw).replace(b'd301', b'd306').replace(b'D301', b'D306')
            expected = expected.replace(b'stage17_q16c_saved_request_v1', b'stage17_q16c_handoff_continuation_v1')
            self.assertEqual(current.render(name, raw), expected)


class HandoffTests(unittest.TestCase):
    def fixture(self, e):
        ops = e/'packet'; ops.mkdir(); out = ops/'runtime-output'; out.mkdir()
        oldout = e/'old-output'; oldout.mkdir(); family = e/'empty-family'; family.mkdir()
        b = lambda path, value: io.save(path, value)
        request = b(e/'request.json', dict(evidence_root_binding=dict(absolute_path=str(family))))
        plan = b(e/'plan.json', dict(storage=dict(program_scope_sha256='c'*64)))
        wrapper = b(oldout/'constructed.json', dict(status='UNSIGNED_INPUTS_VALIDATED', plan=plan))
        (out/'constructed.json').write_bytes(io.read(wrapper))
        template = json.loads((ROOT/'docs/evidence/stage17/Q16C-D298-AUTHORIZATION-STOP-20261119-01/d300-authorization-draft.json').read_bytes())
        template['request_binding'] = request
        auth_template = b(e/'template.json', template)
        oldauth = b(e/'old-auth.json', dict(preserved_fixture=True))
        oldsig = b(e/'old-auth.json.sig', dict(preserved_signature_fixture=True))
        worker = dict(software_worker_fixture=True)
        prepared = b(oldout/'prepared.json', dict(authorization=oldauth, signature=oldsig, request=request, worker=worker))
        old = dict(preconstruction=wrapper, output_root=str(oldout), saved_request=request,
            authorization_template=auth_template, authorization_schema=io.binding(ROOT/'config/schemas/stage17-phase-action-authorization-v6.schema.json'),
            worker=worker, **{k:dict(software_fixture=k) for k in ('family_registration', 'program_root', 'packet_root',
                'repository_root', 'source_revision', 'candidate_inventory', 'window_proof', 'deadline_supplement', 'latest_result', 'latest_recovery')})
        old.update(repository_root=str(e), program_root=str(e/'program'))
        oldb = b(e/'old-config.json', old)
        result = io.binding(EVIDENCE/'d301-study-1/result.json')
        recovery = io.binding(EVIDENCE/'d301-independent-recovery-1.json')
        c = dict(old, original_preconstruction=wrapper, preconstruction=io.binding(out/'constructed.json'),
            output_root=str(out), operational_authorization_path=str(ops/'authorization.json'),
            operator_sources={Path(current.__file__).name:dict(path=str(ops/Path(current.__file__).name))},
            stopped_configuration=oldb, stopped_handoff=dict(prepared=prepared, authorization=oldauth,
                signature=oldsig, result=result, recovery=recovery))
        return c, dict(STOPPED_CONFIGURATION_SHA=oldb['sha256'], STOPPED_AUTH_SHA=oldauth['sha256'],
            STOPPED_SIGNATURE_SHA=oldsig['sha256'], STOPPED_PREPARED_SHA=prepared['sha256'])

    def test_preserved_handoff_allows_only_fresh_paths_and_empty_native_family(self):
        with tempfile.TemporaryDirectory() as d:
            c, constants = self.fixture(Path(d))
            with patch.multiple(current, **constants):
                current.validate_handoff(c)
                for change in ('existing_authority', 'existing_prepared', 'nonempty_native_family', 'wrong_output_path', 'changed_old_signature'):
                    with self.subTest(change=change):
                        bad = copy.deepcopy(c); remove = None
                        if change == 'existing_authority': remove = Path(c['operational_authorization_path']); remove.touch()
                        elif change == 'existing_prepared': remove = Path(c['output_root'])/'prepared.json'; remove.touch()
                        elif change == 'nonempty_native_family':
                            remove = Path(io.document(c['saved_request'])['evidence_root_binding']['absolute_path'])/'stage17-q16c-attempt-v6.json'; remove.touch()
                        elif change == 'wrong_output_path': bad['output_root'] = str(Path(d)/'old-output')
                        else: bad['stopped_handoff']['signature']['sha256'] = 'f'*64
                        try:
                            with self.assertRaises(ValueError): current.validate_handoff(bad)
                        finally:
                            if remove is not None: remove.unlink()

    def test_real_authorization_publication_signature_and_prepared_readback(self):
        # Real file publication and real SSH signature; only the signing-key path,
        # clock gate and fixed-day lookup use explicit software fixtures.
        with tempfile.TemporaryDirectory() as d:
            e = Path(d); c, constants = self.fixture(e)
            key = e/'software-only-key'
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
            real_run = subprocess.run
            def signing(argv, **kwargs):
                self.assertEqual(argv[0:3], ['ssh-keygen', '-Y', 'sign'])
                argv = list(argv); argv[argv.index('-f')+1] = str(key)
                return real_run(argv, **kwargs)
            import datetime as dt
            endpoint = dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=10)
            old = {p: p.read_bytes() for p in (e/'old-auth.json', e/'old-auth.json.sig', e/'old-output/prepared.json')}
            with patch.multiple(current, **constants), patch.object(current, 'check_time'), \
                    patch.object(current.saved, 'deadline_utc', return_value=endpoint), patch.object(subprocess, 'run', side_effect=signing):
                made = current.prepare_authorization(c, time.monotonic_ns()+600*10**9)
            prepared = io.document(made)
            self.assertEqual(prepared['authorization']['path'], c['operational_authorization_path'])
            self.assertEqual(prepared['signature']['path'], c['operational_authorization_path']+'.sig')
            self.assertEqual(prepared['request'], c['saved_request'])
            self.assertEqual({p:p.read_bytes() for p in old}, old)
            value = io.document(prepared['authorization']); template = io.document(c['authorization_template'])
            self.assertEqual({k:v for k,v in value.items() if k not in ('issued_at_utc','expires_at_utc')},
                             {k:v for k,v in template.items() if k not in ('issued_at_utc','expires_at_utc')})
            allow = e/'allowed-signers'; allow.write_text('software-owner '+key.with_suffix('.pub').read_text())
            checked = real_run(['ssh-keygen','-Y','verify','-f',str(allow),'-I','software-owner','-n',
                'stage17-owner-acceptance','-s',prepared['signature']['path']], input=io.read(prepared['authorization']), capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            # Continue through the actual rendered collector with this exact newly
            # published handoff; substitute only witness/observation and native execution.
            import stage17_q16c_compaction_integration_v2 as guarded
            raw = current.render('stage17_q16c_continuation_operator_v1.py',
                (ROOT/'tools/stage17_q16c_continuation_operator_v1.py').read_bytes())
            collector = types.ModuleType('d306_real_collector'); collector.__file__ = '/software-only/operator.py'
            exec(compile(raw, collector.__file__, 'exec'), collector.__dict__)
            c.update(evidence_root=str(e), archive=dict(path=str(e/'candidate')), sidecar=dict(path=str(e/'sidecar')))
            (e/'platform-guard-d306-1').mkdir()
            io.save(e/'platform-guard-d306-1/witness.json', dict(software_witness=True))
            observed = []
            class Observations:
                def __init__(self, *args, **kwargs):
                    self.next_ordinal = 0; self.metadata_bindings = []; observed.append(self)
                def before_capture(self, ordinal): self.next_ordinal = ordinal
            def execute(**kwargs):
                self.assertEqual(kwargs['authorization_path'], Path(prepared['authorization']['path']))
                self.assertEqual(kwargs['signature_path'], Path(prepared['signature']['path']))
                observed[0].before_capture(0); observed[0].next_ordinal = 94
                observed[0].metadata_bindings = [dict(software_receipt=True)]
                return e/'not-a-native-run.json'
            cli = types.SimpleNamespace(base=types.SimpleNamespace(latest_journal=lambda e:e/'journal.json'),
                controller=types.SimpleNamespace(configure_platform_observations=lambda _:None), execute_formal=execute)
            with patch.object(collector, 'cli_for', return_value=cli), \
                    patch.object(guarded, 'ReadOnlyWitness', return_value=object()), patch.object(guarded, 'Observations', Observations):
                result = collector.sign_collect(c, time.monotonic_ns()+24860*10**9, 99)
            self.assertEqual(io.document(result)['actual_request'], c['saved_request'])


class SequenceTests(unittest.TestCase):
    def scenario(self, failure=None):
        original = saved_tests.SequenceTests.scenario
        text = textwrap.dedent(inspect.getsource(original)).replace('d301', 'd306')
        namespace = {**original.__globals__, 'current': current}
        exec(compile(text, 'D306-root-sequence-fixture', 'exec'), namespace)
        return namespace['scenario'](self, failure)

    def test_success_restores_before_validating_and_never_requalifies(self):
        events, result = self.scenario(); self.assertTrue(result['success'], result)
        self.assertEqual(events, ['admission','guard','isolation','authorize','sign-collect','hardware-restored',
                                 'isolation-restored','guard-restored','guard-unlocked','suffix'])

    def test_authority_failure_stops_before_collection(self):
        events, result = self.scenario('authorize'); self.assertFalse(result['success'])
        self.assertNotIn('sign-collect', events); self.assertNotIn('suffix', events); self.assertIn('guard-restored', events)

    def test_collection_failure_restores_without_retry_or_analysis(self):
        events, result = self.scenario('sign-collect'); self.assertFalse(result['success'])
        self.assertNotIn('suffix', events); self.assertIn('isolation-restored', events)


if __name__ == '__main__':
    unittest.main()
