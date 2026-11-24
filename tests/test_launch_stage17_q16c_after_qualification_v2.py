"""D276 handoff preserves all original behavior with separate incident paths."""
import ast
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import launch_stage17_q16c_after_qualification_v1 as original
import launch_stage17_q16c_after_qualification_v2 as current


class HandoffTests(unittest.TestCase):
    def test_new_handoff_changes_only_prospective_incident_file_paths(self):
        before=ast.parse(Path(original.__file__).read_bytes());after=ast.parse(Path(current.__file__).read_bytes())
        rename={'q15-continuation-window-1.json':'continuation-window-1.json',
            'qualification-family-complete-2.json':'qualification-family-complete-1.json',
            'qualification-family-failure-2.json':'qualification-family-failure-1.json',
            'q16c-operational-configuration-2.json':'q16c-operational-configuration-1.json',
            'q16c-qualification-handoff-2.json':'q16c-qualification-handoff-1.json'}
        for n in ast.walk(after):
            if isinstance(n,ast.Constant) and isinstance(n.value,str):n.value=rename.get(n.value,n.value)
        for name in ('finalized','main'):
            a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b))


if __name__=='__main__':unittest.main()
