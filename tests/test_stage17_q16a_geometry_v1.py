"""Software layout checks; no actual platform observation or authority."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16a_geometry_v1 as geometry


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.parent=dict(source_revision='a'*40,captures=[dict(capture=dict(context_ordinal=i,
            geometry=dict(capacity=512,cache_line_bytes=64))) for i in range(12)])
        self.suffix=dict(captures=self.parent['captures'][3:])
        self.native=dict(schema_version='software-native-ring-slot-geometry/1',source_revision='a'*40,
            source_dirty=False,api='RingSpscQueue::storage_requirements',hardware_observation=False,execution_authority=False,
            records=[dict(context_ordinal=i,capacity=512,cache_line_bytes=64,slot_storage_bytes=4096,cursor_storage_bytes=128) for i in range(6)])
        self.output=dict(size_bytes=947,sha256='b'*64)

    def test_both_original_populations_keep_observed_layout_and_source_binding(self):
        old=copy.deepcopy((self.native,self.parent,self.suffix))
        rows=geometry.layout_records(self.native,self.parent,self.suffix,64,self.output)
        self.assertEqual(len(rows),6)
        self.assertEqual(rows[0]['slot_storage_bytes'],4096)
        self.assertEqual(rows[0]['source_binding'],dict(artifact_id='D240-RETAINED-NATIVE-GEOMETRY',**self.output))
        self.assertEqual((self.native,self.parent,self.suffix),old)

    def test_source_authority_order_and_layout_mutants_rejected(self):
        for mutation in ('revision','dirty','api','hardware','authority','count','order','line','capacity','slots'):
            n=copy.deepcopy(self.native)
            if mutation=='revision':n['source_revision']='c'*40
            if mutation=='dirty':n['source_dirty']=True
            if mutation=='api':n['api']='fabricated'
            if mutation=='hardware':n['hardware_observation']=True
            if mutation=='authority':n['execution_authority']=True
            if mutation=='count':n['records'].pop()
            if mutation=='order':n['records'].reverse()
            if mutation=='line':n['records'][0]['cache_line_bytes']=128
            if mutation=='capacity':n['records'][0]['capacity']=1024
            if mutation=='slots':n['records'][0]['slot_storage_bytes']=4097
            with self.subTest(mutation=mutation),self.assertRaises((geometry.admission.AdmissionError,geometry.admission.calibration.CalibrationError)):
                geometry.layout_records(n,self.parent,self.suffix,64,self.output)

    def test_admitted_cacheline_and_continuation_geometry_must_match(self):
        with self.assertRaises(geometry.admission.AdmissionError):geometry.layout_records(self.native,self.parent,self.suffix,128,self.output)
        p=copy.deepcopy(self.suffix);p['captures'][0]['capture']['geometry']['capacity']=1024
        with self.assertRaises(geometry.admission.AdmissionError):geometry.layout_records(self.native,self.parent,p,64,self.output)


if __name__=='__main__':unittest.main()
