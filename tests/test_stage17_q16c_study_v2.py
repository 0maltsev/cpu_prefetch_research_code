"""Owner admission is additive; original collection/recovery bodies stay fixed."""
import ast
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_study_v1 as original
import stage17_q16c_study_v2 as current


class OwnerIntegrationTests(unittest.TestCase):
    def test_unchanged_root_pipeline_and_owner_guard_before_each_exec(self):
        a=ast.parse(Path(original.__file__).read_bytes());b=ast.parse(Path(current.__file__).read_bytes())
        old={n.name:n for n in a.body if isinstance(n,ast.FunctionDef)}
        new={n.name:n for n in b.body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(old.keys(),new.keys())
        for name in old:
            if name!='owner':self.assertEqual(ast.dump(old[name]),ast.dump(new[name]),name)
        node=new['owner'];statements=node.body
        first=next(i for i,n in enumerate(statements) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id=='admission' for t in n.targets))
        guard=statements[first:first+4]
        self.assertEqual(len(guard),4)
        self.assertTrue(any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='check'
            for n in ast.walk(guard[2])))
        node.body=statements[:first]+statements[first+4:]
        self.assertEqual(ast.dump(node),ast.dump(old['owner']))


if __name__=='__main__':unittest.main()
