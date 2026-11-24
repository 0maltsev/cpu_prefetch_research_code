import copy
import json
from pathlib import Path
import tempfile
import unittest
import validate_suffix as v


class SuffixTests(unittest.TestCase):
    def test_original_collected_population_and_identity_drift(self):
        root=Path(__file__).resolve().parents[3]
        plan=json.loads((root/'build/stage17-step5-prep/formal-q16a-continuation-authoring-1/plan.json').read_bytes())
        self.assertEqual(len(v.validate_population(plan)),531)
        for item in plan['captures']:
            layout=v.support.packed_page_layout(item)
            self.assertEqual(len(layout['array_counts']),84)
            self.assertLessEqual(layout['packed_capacity_bytes'],512*1024**2)
        for field,value in [('ordinal',1),('context_ordinal',4)]:
            changed=copy.deepcopy(plan);changed['captures'][0]['capture'][field]=value
            with self.assertRaises(ValueError):v.validate_population(changed)

    def valid_config(self):
        g=v.base.GIB
        files={key:{} for key in (*v.ROLES,'policy','historical_journal')}
        files['REQUEST']={'sha256':v.REQUEST_SHA};files['COMPLETION']={'sha256':v.COMPLETION_SHA}
        return dict(schema_version='software-offline-q16a-suffix-analysis/1',operator_sha256=v.sha(Path(v.__file__).read_bytes()),
            supervision_sha256=v.base.SUPERVISION_SHA,execution_authority=False,files=files,
            repository_root='/tmp/repo',evidence_root='/tmp/evidence',journal_directory='/tmp/journal',analysis_root='/tmp/analysis',
            resources=dict(supervisor_as_bytes=2*g,coordinator_as_bytes=2*g,capture_as_bytes=8*g,total_memory_bytes=36*g,memory_reserve_bytes=8*g,
                timeout_seconds=259200,metadata_bytes=2*g,filesystem_overhead_bytes=256*1024**2,canonical_capture_bytes=48*g,worker_count=4,
                runtime={'codec_address_space_bytes':2*g}))

    def check(self,document):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'config.json';p.write_bytes(v.base.canonical(document))
            return v.config(p,v.sha(p.read_bytes()))

    def test_bounded_configuration(self):
        self.check(self.valid_config())

    def test_input_authority_and_resource_mutants_rejected(self):
        for mutation in ('authority','completion','role','memory','scratch','workers','timeout','operator'):
            c=self.valid_config()
            if mutation=='authority':c['execution_authority']=True
            if mutation=='completion':c['files']['COMPLETION']['sha256']='0'*64
            if mutation=='role':del c['files']['SIGNATURE']
            if mutation=='memory':c['resources']['total_memory_bytes']-=1
            if mutation=='scratch':c['resources']['canonical_capture_bytes']=256*v.base.GIB
            if mutation=='workers':c['resources']['worker_count']=8
            if mutation=='timeout':c['resources']['timeout_seconds']*=2
            if mutation=='operator':c['operator_sha256']='0'*64
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.check(c)


if __name__=='__main__':unittest.main()
