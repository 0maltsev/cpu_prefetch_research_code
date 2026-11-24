"""D263 fresh policy/journal/preflight source admission, with no stand access."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import author_stage17_policy_v60 as author
import create_stand_bundle as creator
import stage17_semantic_verifier_v60 as semantic
import stage17_read_only_preflight_semantic_verifier_v34 as preflight
import stage17_read_only_preflight_executor_v34 as executor
import stage17_state_journal_v56 as journal
import stage17_state_journal as base

ROOT = Path(__file__).resolve().parents[1]


class PrivateScopes(unittest.TestCase):
    def test_journal_complete_core_bodies_select_only_new_semantics(self):
        before = dict(vars(journal.core))
        selected = journal.configure()
        for name, original in vars(journal.core).items():
            if getattr(original, '__module__', None) == journal.core.__name__ and hasattr(original, '__code__'):
                actual = getattr(selected, name)
                self.assertIs(actual.__code__, original.__code__)
                self.assertIs(actual.__globals__['semantic'], semantic)
                self.assertEqual(actual.__globals__['SEMANTIC_POLICY_PATH'], semantic.POLICY_PATH)
                self.assertIs(actual.__globals__['_transitions'].__code__, journal.core._transitions.__code__)
        self.assertEqual(dict(vars(journal.core)), before)
        self.assertNotIn('stage17_state_journal_v53', selected.validate_operational_journal.__globals__)

    def test_preflight_uses_original_gates_in_one_private_scope(self):
        before = dict(vars(executor.owner))
        selected = executor.activate()
        for name in ('execute_once', '_prospective_validation', '_prepare_action', '_transport_once', 'main'):
            self.assertIs(getattr(selected, name).__code__, getattr(executor.owner, name).__code__)
            self.assertIs(getattr(selected, name).__globals__, selected.execute_once.__globals__)
        self.assertIs(selected.current_journal, journal)
        self.assertIs(selected._prospective_validation.__globals__['current_journal'], journal)
        self.assertEqual(selected.EXECUTOR_ID, 'STAGE17-READ-ONLY-PREFLIGHT-EXECUTOR-v34')
        self.assertEqual(dict(vars(executor.owner)), before)
        paths = executor.runtime_identity_paths()
        for key in ('executor', 'state_journal'):
            expected = (executor if key == 'executor' else journal).__file__
            self.assertEqual(paths[key], str(Path(expected).resolve()))
            actual = author._BASE.binding(ROOT, preflight.IMPLEMENTATION_PATHS[key])
            self.assertEqual(Path(paths[key]), ROOT / actual['path'])

    def test_preparation_failure_does_not_create_marker_or_start_transport(self):
        selected = executor.activate()
        scope = selected.execute_once.__globals__
        prepare, transport = Mock(side_effect=AssertionError('preparation bypass')), Mock()
        with patch.dict(scope, _prospective_validation=lambda **kw: SimpleNamespace(action_ready=False,
                action_context=None), _prepare_action=prepare, _transport_once=transport):
            with self.assertRaisesRegex(executor.ActionExecutionError, 'not prospectively action-ready'):
                selected.execute_once(repository_root=ROOT, latest_journal=ROOT / 'unused', journal_directory=ROOT)
        prepare.assert_not_called()
        transport.assert_not_called()

    def test_qualification_failure_propagates_before_preflight_preparation(self):
        selected = executor.activate()
        scope = selected.execute_once.__globals__
        failure = journal.JournalError('qualification rejected')
        with patch.object(journal, 'validate_operational_journal', side_effect=failure) as validate, \
                patch.dict(scope, _prepare_action=lambda *args: self.fail('qualification bypass')):
            with self.assertRaisesRegex(journal.JournalError, 'qualification rejected'):
                selected.execute_once(repository_root=ROOT, latest_journal=ROOT / 'unused', journal_directory=ROOT)
        validate.assert_called_once()


class PolicyAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.historical = json.loads((ROOT / semantic.predecessor.POLICY_PATH).read_bytes())

    def verify(self, policy, root=None):
        root = ROOT if root is None else root
        semantic.verify_policy_v60(root=root, policy=policy, **{key: self.historical[key] for key in (
            'graph_sha256', 'catalog_sha256', 'genesis_record_sha256', 'resolution_schema_sha256')})

    def test_every_old_binding_audited_and_only_approved_cpp_rebound(self):
        candidate = copy.deepcopy(self.historical)
        for group in ('bindings','runtime_closure'):
            for key, value in candidate[group].items():
                if value['path'] in semantic.REBIND_PATHS:
                    candidate[group][key] = author._BASE.binding(ROOT, value['path'])
        semantic.audit_inherited_bindings(ROOT, candidate, self.historical)
        # Omitting an inherited source, or simply rehashing it, is not a
        # legitimate successor. The old binding itself must remain unchanged.
        other = next(k for k, v in candidate['bindings'].items() if v['path'] not in semantic.REBIND_PATHS)
        for mutation in ('remove', 'rehash'):
            changed = copy.deepcopy(candidate)
            if mutation == 'remove':
                changed['bindings'].pop(other)
            else:
                changed['bindings'][other]['sha256'] = '0' * 64
            with self.subTest(mutation=mutation), self.assertRaisesRegex(semantic.SemanticAdmissionError, 'inherited binding'):
                semantic.audit_inherited_bindings(ROOT, changed, self.historical)

    def test_checked_in_policy_is_exact_fresh_renderer_output(self):
        current = author.render(ROOT)
        self.assertEqual((ROOT / semantic.POLICY_PATH).read_bytes(), author._BASE.canonical(current))
        self.verify(current)
        for group in ('bindings', 'runtime_closure'):
            changed = {key for key in self.historical[group]
                       if self.historical[group][key] != current[group][key]}
            self.assertTrue({current[group][key]['path'] for key in changed} <= semantic.REBIND_PATHS)
        roots = current['runtime_import_roots']
        self.assertTrue(set(semantic.NEW_ROOTS) <= set(roots))
        self.assertIn('stage17_phase_controller_v26', roots)
        closure = {v['path'] for v in current['runtime_closure'].values()}
        self.assertFalse({'tools/stage17_state_journal_v53.py', 'tools/stage17_operational_cli_v19.py'} & closure)

    def test_rehashed_native_or_removed_runtime_does_not_weaken_old_gates(self):
        current = author.render(ROOT)
        for mutation in ('native', 'missing', 'root', 'authority', 'graph', 'entry', 'predecessor'):
            value = copy.deepcopy(current)
            if mutation == 'native':
                value['bindings']['src__runner__stage17_formal_family_cpp']['sha256'] = '0' * 64
            elif mutation == 'missing':
                value['runtime_closure'].pop('stage17_state_journal_v56')
            elif mutation == 'root':
                value['runtime_import_roots'].append('stage17_formal_control_reader_v1')
            elif mutation == 'authority':
                value['stage18_authority'] = True
            elif mutation == 'graph':
                value['graph_sha256'] = '0' * 64
            elif mutation == 'entry':
                value['entries'][0]['verifier_version'] = '58'
            else:
                value['predecessor'] = value['bindings']['config__stage17__stage17-operational-evidence-admission-policy-v57_json']
            with self.subTest(mutation=mutation), self.assertRaises(semantic.SemanticAdmissionError):
                self.verify(value)

    def test_packaging_audits_and_copies_actual_policy_bound_files(self):
        current = creator.current_stage17_policy(ROOT)
        self.assertEqual(current, author.render(ROOT))
        with tempfile.TemporaryDirectory() as temporary:
            staging = Path(temporary)
            files = creator.copy_policy_bound_files(ROOT, staging, current)
            self.assertEqual(len(files), sum(len(current[group]) for group in ('bindings', 'runtime_closure')))
            for item in files:
                expected = {key: item[key] for key in ('path', 'size_bytes', 'sha256')}
                self.assertEqual(author._BASE.binding(staging, item['path']), expected)
            self.verify(current, root=staging)
        self.assertEqual(creator.STAGE17_PROFILE, 'STAGE17-PILOT-CANDIDATE-BUNDLE-v26')
        self.assertEqual(creator.STAGE17_DRY_RUN_PROFILE, 'STAGE17-HERMETIC-DRY-RUN-BUNDLE-v22')
        self.assertEqual(len(creator.STAGE17_CODEGEN_INPUTS), 8)
        self.assertEqual(creator.STAGE17_CONTROLLER_ENTRYPOINT, 'tools/stage17_phase_controller_daycap_v2.py')

    def test_fresh_journal_has_no_readiness_or_execution_authority(self):
        observed = journal.checked_in_status(ROOT)
        self.assertEqual(observed.current_state, 'PREPARED')
        self.assertEqual((observed.resolution_count, observed.transition_count), (0, 0))
        self.assertFalse(observed.action_ready)
        self.assertFalse(observed.pilot_ready)
        self.assertEqual(observed.stand_status, 'NOT_ACCESSED')

    def test_real_cli_init_status_and_real_ext001_rejection_without_stand(self):
        with tempfile.TemporaryDirectory(prefix='stage17-policy60-init-') as temporary:
            for command in ('init', 'status'):
                completed = subprocess.run([sys.executable, '-B',
                    str(ROOT / 'tools/stage17_operational_cli_daycap_v2.py'),
                    '--repository-root', str(ROOT), '--evidence-root', temporary, command],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            policy = author.render_preflight(ROOT)
            # The actual generic journal and original EXT001 semantic body
            # reject missing evidence. No mocked policy/manifest, transport,
            # signature, marker, experiment, or qualification is supplied.
            with self.assertRaisesRegex(semantic.SemanticAdmissionError, 'requires exactly one v14 envelope'):
                semantic.verify_input(input_id='S17-EXT-001', root=ROOT, repository_documents=[],
                    receipt_documents=[], resolution={}, catalog={},
                    graph_sha256=policy['predecessor']['graph_sha256'],
                    catalog_sha256=policy['predecessor']['catalog_sha256'],
                    genesis_sha256=policy['predecessor']['genesis_record_sha256'],
                    resolution_schema_sha256=policy['predecessor']['resolution_schema_sha256'])


class PreflightPolicy(unittest.TestCase):
    def verify(self, policy):
        fields = {k: v for k, v in policy['predecessor'].items() if k.endswith('_sha256')}
        preflight.verify_policy_v34(root=ROOT, policy=policy, **fields)

    def test_original_rules_and_exact_new_loaded_implementation_snapshot(self):
        policy = author.render_preflight(ROOT)
        self.assertEqual((ROOT / preflight.POLICY_PATH).read_bytes(), author._BASE.canonical(policy))
        self.verify(policy)
        old = json.loads((ROOT / preflight.POLICY_V33_PATH).read_bytes())
        for field in ('action_readiness', 'operational_admission', 'schema_bindings',
                      'fixed_action_plan', 'successor_action_plan', 'operational_definitions'):
            self.assertEqual(policy[field], old[field])
        for key in ('executor', 'state_journal'):
            self.assertEqual(policy['implementations'][key]['path'], preflight.IMPLEMENTATION_PATHS[key])
        policy['implementations']['executor'] = old['implementations']['executor']
        with self.assertRaisesRegex(preflight.SemanticAdmissionError, 'runtime closure'):
            self.verify(policy)

    def test_historical_envelopes_use_their_actual_old_policy_without_relabel(self):
        documents = [(ROOT / 'old-envelope', {'schema_version': 'cpu-prefetch-stage17-operational-evidence-envelope/14',
            'semantic_policy': {'path': semantic.predecessor.preflight.POLICY_PATH}})]
        before = copy.deepcopy(documents)
        with patch.object(semantic.predecessor, 'verify_input', return_value='historical') as old:
            self.assertEqual(semantic.verify_input(input_id='S17-EXT-001', repository_documents=documents), 'historical')
        self.assertIs(old.call_args.kwargs['repository_documents'], documents)
        self.assertEqual(before, documents)

    def test_fresh_envelope_invokes_complete_policy33_and_original_semantics(self):
        policy = author.render_preflight(ROOT)
        arguments = dict(root=ROOT, repository_documents=[], graph_sha256=policy['predecessor']['graph_sha256'],
            catalog_sha256=policy['predecessor']['catalog_sha256'],
            genesis_sha256=policy['predecessor']['genesis_record_sha256'],
            resolution_schema_sha256=policy['predecessor']['resolution_schema_sha256'])
        with patch.object(preflight, 'verify_s17_ext_001_semantics_v27', return_value='fresh') as verify:
            self.assertEqual(semantic.verify_input(input_id='S17-EXT-001', **arguments), 'fresh')
        self.assertEqual(verify.call_args.kwargs['policy_path'], ROOT / preflight.POLICY_PATH)
        self.assertEqual(verify.call_args.kwargs['policy'], policy)
        self.assertEqual(verify.call_args.kwargs['policy_sha256'], semantic.sha_file(ROOT / preflight.POLICY_PATH))


if __name__ == '__main__':
    unittest.main()
