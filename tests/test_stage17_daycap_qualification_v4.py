"""D281 fresh qualification source selection, without stand execution."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_phase_controller_daycap_v4 as phase
import stage17_operational_cli_daycap_v4 as cli
import stage17_state_journal_v59 as journal
import create_stand_bundle as creator
import verify_stand_bundle as verifier
import stage17_q16a_q16c_descriptive_handoff_v2 as reviewed
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture
from stage17_discovery_contract_v2 import ContractError

ROOT = Path(__file__).resolve().parents[1]


class QualificationTests(unittest.TestCase):
    def test_complete_private_qualification_graph_and_cli_use_policy62(self):
        selected = phase.make_controller()
        self.assertIs(selected.journal_runtime, journal)
        self.assertIs(selected._v25.journal_runtime, journal)
        self.assertIs(selected._v26.previous, selected._v25)
        self.assertIs(cli.journal, journal)
        self.assertIs(cli.controller, phase)
        self.assertIsNot(cli._base, cli.previous.base)
        for name in ('author_formal_request', 'author_formal_authorization', 'verify_formal_signature',
                     'prepare_formal_retention'):
            self.assertIs(getattr(cli, name).__code__, getattr(cli.previous, name).__code__)
        self.assertIs(cli._VIEW.main.__code__, cli.previous.main.__code__)
        self.assertIs(cli._base.main.__globals__['journal_runtime'], journal)
        self.assertIs(cli._base.main.__globals__['author_ext001'], cli._VIEW.author_ext001_daycap_v1)

    def test_ext001_authoring_preserves_every_rule_and_selects_exact_policy35(self):
        old = ast.parse((ROOT/'tools/stage17_operational_cli_daycap_v3.py').read_text())
        new = ast.parse((ROOT/'tools/stage17_operational_cli_daycap_v4.py').read_text())
        original = next(n for n in old.body if isinstance(n, ast.FunctionDef) and n.name=='author_ext001_daycap_v3')
        actual = next(n for n in new.body if isinstance(n, ast.FunctionDef) and n.name=='author_ext001_daycap_v4')
        actual.name = original.name
        for node in ast.walk(actual):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                node.value = node.value.replace('policy-v36.json','policy-v35.json')
        self.assertEqual(ast.dump(actual), ast.dump(original))
        self.assertIs(cli._base.main.__globals__['author_ext001'], cli.author_ext001_daycap_v4)

    def test_qualification_entry_cannot_bypass_descriptive_collection_admission(self):
        with self.assertRaises(ContractError):
            phase.contract.validate_plan('Q16c', plan_fixture())

    def test_current_tuple_and_both_predecessor_routes_are_exact(self):
        profile = 'STAGE17-PILOT-CANDIDATE-BUNDLE-v26'
        for policy, preflight, controller in [(59, 33, 1), (60, 34, 2), (61, 35, 3), (62, 36, 4)]:
            doc = dict(policy=dict(path=f'config/stage17/stage17-operational-evidence-admission-policy-v{policy}.json'))
            self.assertEqual(verifier.daycap_admission_tuple(profile, doc), (policy, preflight, preflight,
                f'STAGE17-FIXED-ACTION-PHASE-CONTROLLER-DAYCAP-v{controller}',
                f'tools/stage17_phase_controller_daycap_v{controller}.py'))
            self.assertIsNone(verifier.daycap_admission_tuple('unknown-profile', doc))
        self.assertEqual(creator.STAGE17_POLICY_PATH, 'config/stage17/stage17-operational-evidence-admission-policy-v62.json')
        self.assertEqual(creator.STAGE17_CONTROLLER_ENTRYPOINT, 'tools/stage17_phase_controller_daycap_v4.py')

    def test_historical_policy_bytes_remain_bound_and_only_reviewed_native_delta_changes(self):
        old = ROOT / 'config/stage17/stage17-operational-evidence-admission-policy-v61.json'
        new = json.loads((ROOT / creator.STAGE17_POLICY_PATH).read_bytes())
        self.assertEqual(new['predecessor']['sha256'], hashlib.sha256(old.read_bytes()).hexdigest())
        old = json.loads(old.read_bytes())
        changed = {row['path'] for key, row in old['bindings'].items() if new['bindings'][key] != row}
        self.assertEqual(changed, {'include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp','src/runner/stage17_formal_scheduled_action.cpp','tools/create_stand_bundle.py','tools/verify_stand_bundle.py'})
        for row in new['bindings'].values():
            if row['path'] in reviewed.REVIEWED_COLD_SOURCES:
                self.assertEqual(row['sha256'], reviewed.REVIEWED_COLD_SOURCES[row['path']])


class ColdSourceReview(unittest.TestCase):
    def compare(self, name, current_bytes, *, identical=False):
        with tempfile.TemporaryDirectory() as directory:
            roots = {side: Path(directory) / side for side in ('original', 'current')}
            rows = {'relative_path': name}
            releases = {}
            for side, payload in (('original', b'previous qualified source\n'),
                                  ('current', current_bytes)):
                path = roots[side] / name
                path.parent.mkdir(parents=True)
                path.write_bytes(payload)
                bound = dict(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                releases[side] = (roots[side], {name: bound}, {})
                rows[side] = dict(bound, path=str(path))
            reader = reviewed.admission.BoundReader()
            reviewed._comparison([rows], {name}, releases, reader, identical=identical)
            reader.finish()

    def test_exact_reviewed_cold_bytes_pass_but_rehashed_edits_fail(self):
        name = 'src/runner/stage17_formal_scheduled_action.cpp'
        raw = (ROOT / name).read_bytes()
        self.compare(name, raw)
        with self.assertRaisesRegex(reviewed.Error, 'reviewed'):
            self.compare(name, raw + b'\n// unreviewed\n')

    def test_measured_identity_is_required_even_for_a_reviewed_path(self):
        name = 'include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp'
        with self.assertRaisesRegex(reviewed.Error, 'byte-identical'):
            self.compare(name, (ROOT / name).read_bytes(), identical=True)
        with self.assertRaisesRegex(reviewed.Error, 'byte-identical'):
            self.compare('src/workload/deterministic.cpp', b'changed measured source')

    def test_old_review_and_execution_bodies_remain_unchanged(self):
        old = reviewed.previous
        changed = {name for name in old.REVIEWED_COLD_SOURCES
                   if old.REVIEWED_COLD_SOURCES[name] != reviewed.REVIEWED_COLD_SOURCES[name]}
        self.assertEqual(changed, {
            'src/runner/stage17_formal_scheduled_action.cpp',
            'include/cpu_prefetch/runner/stage17_formal_scheduled_action.hpp'})
        self.assertIs(reviewed.consume.__code__, old.consume.__code__)
        self.assertIsNot(reviewed.consume.__globals__, old.consume.__globals__)
        self.assertIs(reviewed.consume.__globals__['_comparison'], reviewed._comparison)
        self.assertIs(old.consume.__globals__['_comparison'], old._comparison)


if __name__ == '__main__': unittest.main()
