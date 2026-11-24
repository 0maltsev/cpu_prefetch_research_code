"""Fresh source/arena/node namespaces and numeric collision detection."""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_namespace_audit_v1 as current
import test_stage17_q16c_plan_builder_v1 as fixtures


class NamespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.BuilderTests.setUpClass()

    def setUp(self):
        fixture=fixtures.BuilderTests();fixture.parent=fixtures.BuilderTests.parent
        self.identities=fixture.identities();self.matcher=current.Matcher(self.identities)

    def test_all792_seeds_and_all360_sources_are_included(self):
        self.assertEqual(len(self.matcher.numeric),792)
        for row in self.identities['source_setup']['sources']:
            matches,_=self.matcher.inspect(json.dumps(dict(source=row)).encode())
            self.assertIn(row['namespace_id'],matches)
            self.assertIn('numeric_seed:'+row['seed_hex'],matches)

    def test_decimal_hex_escaped_embedded_and_jsonl_collisions_cannot_hide(self):
        row=self.identities['source_setup']['sources'][0];seed=row['seed_hex']
        samples=[json.dumps(dict(seed=int(seed,16))).encode(),json.dumps(dict(seed='0x'+seed)).encode(),
            ('{"id":"'+''.join('\\u%04x'%ord(c) for c in row['namespace_id'])+'"}').encode(),
            json.dumps(dict(comment='embedded:'+row['namespace_id']+':suffix')).encode()]
        for raw in samples:self.assertTrue(self.matcher.inspect(raw)[0])
        self.assertTrue(self.matcher.inspect(b'{}\n'+samples[0]+b'\n',True)[0])
        self.assertEqual(self.matcher.inspect(b'{"unrelated":"CPU-PREFETCH-V5-V27","number":1234}')[0],[])

    def test_duplicates_and_old_prospective_exceptions_are_not_allowed(self):
        self.identities['source_setup']['sources'][1]['seed_hex']=self.identities['phase_identities'][0]['seed_hex']
        with self.assertRaises(ValueError):current.Matcher(self.identities)


if __name__=='__main__':unittest.main()
