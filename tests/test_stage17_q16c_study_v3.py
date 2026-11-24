"""The D277 study selects its new deadline and preserves recovery machinery."""
import ast
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_study_v2 as old
import stage17_q16c_study_v3 as new


class StudyTests(unittest.TestCase):
    def test_only_execution_deadline_selection_changes_in_root_pipeline(self):
        before=ast.parse(Path(old.__file__).read_bytes());after=ast.parse(Path(new.__file__).read_bytes())
        for n in ast.walk(after):
            if isinstance(n,ast.Constant) and isinstance(n.value,str):
                n.value={'execution_window':'source_manifest','q16c_execution_window':'q16c_original_window'}.get(n.value,n.value)
        functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
        a,b=functions(before),functions(after);self.assertEqual(a.keys(),b.keys())
        for name in a:self.assertEqual(ast.dump(a[name]),ast.dump(b[name]),name)


if __name__=='__main__':unittest.main()
