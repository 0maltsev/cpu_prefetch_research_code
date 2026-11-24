"""Descriptive controller graph and immutable historical identity boundaries."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_descriptive_administration_v1 as current
import stage17_phase_controller_daycap_v3 as qualification
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


class AdministrationTests(unittest.TestCase):
    def test_full_private_graph_selects_new_journal_plan_registry_and_overlay(self):
        c=current.make_controller();p=plan_fixture()
        self.assertIs(c.journal_runtime,qualification.journal)
        self.assertIs(c._v25.journal_runtime,qualification.journal)
        self.assertIs(c._v26.previous,c._v25)
        self.assertIs(c._v25._prepare_action.__globals__['registry'],c.registry)
        self.assertIs(c._v26._prepare_action.__globals__['_validate_inputs'],c._validate_inputs)
        self.assertEqual(c.contract.validate_plan('Q16c',p).captures[0].ordinal,0)
        self.assertTrue(c.is_archived(dict(action_id='Q16c',schema_version='cpu-prefetch-stage17-fixed-action-request/6',action_inputs=dict(plan=p))))
        self.assertIs(c.qualified_archive_profile.__globals__['overlay'],c.overlay)
        self.assertEqual(c.overlay.daycap.VERSION,p['schema_version'])
        self.assertIsNot(c.overlay,current.overlay_module)
        self.assertIsNone(current.overlay_module._CONFIG)

    def test_cli_inherited_functions_and_base_share_private_controller(self):
        cli=current.make_cli()
        for name in ('main','activate','author_formal_request','author_formal_authorization','verify_formal_signature',
                     'execute_formal','prepare_formal_retention','admit_formal_retention'):
            self.assertIs(getattr(cli,name).__globals__['controller'],cli.controller)
            self.assertIs(getattr(cli,name).__code__,getattr(current.qualified_cli._VIEW,name).__code__)
        cli.activate()
        self.assertIs(cli.base.controller,cli.controller)
        self.assertIs(cli.base.journal_runtime,qualification.journal)
        self.assertIs(current.qualified_cli.controller,qualification)

    def test_unconfigured_history_and_wrong_action_fail_before_native_execution(self):
        c=current.make_controller()
        with self.assertRaisesRegex(c.ControllerError,'history packet'):c._historical_inputs()
        for action in ('Q16a','Q16b','STAGE17-BLINDED-PILOT'):
            with self.assertRaisesRegex(c.ControllerError,'explicit Q16c/3'):
                c._validate_inputs(dict(action_id=action,action_inputs=dict(plan=plan_fixture())),None)

    def test_archive_overlay_preserves_every_rule_except_explicit_descriptive_identity(self):
        old=Path(current.overlay_module.oldv1.__file__).with_name('stage17_archive_daycap_overlay_v1.py')
        new=Path(current.overlay_module.__file__)
        before=ast.parse(old.read_text());after=ast.parse(new.read_text())
        a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name=='qualified_profile')
        b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='qualified_profile')
        for node in ast.walk(b):
            if isinstance(node,ast.Constant) and isinstance(node.value,str):
                node.value=node.value.replace('D270 Q16c only','D254 Q16b only').replace('D270 /3 plan and method required','D254 /3 plan and method required')
                if node.value=='Q16c':node.value='Q16b'
        self.assertEqual(ast.dump(a),ast.dump(b))


if __name__=='__main__':unittest.main()
