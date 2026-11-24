"""D282 private administration, namespace and unchanged recovery contracts."""
import ast
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_namespace_audit_v2 as audit
import stage17_q16c_admission_limits_v2 as limits
import stage17_q16c_descriptive_administration_v3 as admin
import stage17_state_journal_v59 as journal
import launch_stage17_q16c_after_qualification_v4 as launch
from test_stage17_q16c_empty_reuse_v1 import old_plan
import stage17_q16c_restart_plan_v1 as restart


class Integration(unittest.TestCase):
    def test_private_current_policy_graph_and_reviewed_source_views(self):
        handoffs = limits.make_handoffs(); c = admin.make_controller(); cli = admin.make_cli(); cli.activate()
        self.assertIs(c.journal_runtime,journal); self.assertIs(c._v25.journal_runtime,journal)
        self.assertIs(c._v26.previous,c._v25); self.assertIs(cli.journal,journal)
        self.assertTrue(callable(c.configure_source_reuse))
        self.assertTrue(callable(c.configure_execution_window))
        self.assertEqual(handoffs[0].consume.__globals__['_comparison'].__globals__['REVIEWED_COLD_SOURCES'],
            handoffs[0].REVIEWED_COLD_SOURCES)
        self.assertIs(handoffs[1].consume.__globals__['compatibility'],handoffs[0])

    def test_failure_or_reused_handoff_cannot_launch(self):
        ok=dict(success=True,formal_capture_started=False,isolation_retained_for_formal=True)
        self.assertTrue(launch.finalized(dict(files={}),ok))
        for k in ok:
            bad=dict(ok);bad[k]=not bad[k]
            with self.subTest(key=k),self.assertRaises(ValueError):launch.finalized(dict(files={}),bad)
        with self.assertRaises(ValueError):launch.finalized(dict(files={'qualification_complete':{}}),ok)

    def test_original_native_cleanup_and_post_restoration_analysis_unchanged(self):
        def function(file,name):
            tree=ast.parse((ROOT/'tools'/file).read_text())
            return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        self.assertEqual(ast.dump(function('stage17_q16c_study_v3.py','run')),
            ast.dump(function('stage17_q16c_study_v5.py','run')))
        self.assertEqual(ast.dump(function('stage17_q16c_operator_v1.py','main')),
            ast.dump(function('stage17_q16c_operator_v3.py','main')))


class Namespaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=old_plan()
        cls.plan,cls.ids=restart.prepare(cls.original,dict(sources=[{} for _ in range(360)]),master_hex='45'*32)

    def test_fresh_identity_decimal_hex_escaped_and_key_collisions_detected(self):
        matcher=audit.Matcher(self.ids);row=self.ids['phase_identities'][0]
        for value in ({'run':row['run_id']},{'seed':row['seed_hex']},
            {'seed':int(row['seed_hex'],16)},{row['seed_id']:'value'}):
            with self.subTest(value=value): self.assertTrue(matcher.inspect(audit.old.canonical(value))[0])
        escaped=json.dumps({'run':row['run_id']}).replace('C29','\\u004329').encode()
        self.assertTrue(matcher.inspect(escaped)[0])

    def test_old_borrowed_bank_is_not_reported_as_fresh_but_history_is_visible(self):
        found,plans=audit.Matcher(self.ids).inspect(audit.old.canonical(self.original))
        self.assertEqual(found,[])
        self.assertIn(audit.old.sha(audit.old.canonical(self.original)),plans)
        with self.assertRaises(ValueError):audit.Matcher(self.ids).inspect(b'\n',lines=True)


if __name__=='__main__':unittest.main()
