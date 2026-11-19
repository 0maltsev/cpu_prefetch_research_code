"""Retained original incident fixtures prove zero-event boundary and recovery."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_prefix_reuse_v1 as current

class IncidentTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'docs/evidence/stage17/Q16C-D285-NATIVE-STOP-20261118-01'
        self.docs=[json.loads((root/name).read_bytes()) for name in ('formal-capture-86-final-checkpoint.json',
            'stage17-q16c-failure-v6.json','isolation-restoration.json','formal-capture-86-archive-custody.json')]
    def test_actual_prepared_but_unreleased_both_phases_qualify_for_source_reuse(self):
        before=copy.deepcopy(self.docs);current.zero_events(*self.docs)
        self.assertEqual(before,self.docs)
        self.assertFalse(self.docs[0]['native_complete'])
    def test_one_event_one_phase_release_or_missing_failed_raw_evidence_blocks_reuse(self):
        for mutation in ('attempt','release','consumed','raw','custody','restore','quarantine'):
            docs=copy.deepcopy(self.docs);phases=docs[0]['native_result_after_cleanup']['session']['lifecycle']['phases']
            if mutation=='attempt':phases[0]['producer']['attempted']=1
            elif mutation=='release':phases[0]['released']=True
            elif mutation=='consumed':phases[1]['consumer']['consumed_including_drain']=1
            elif mutation=='raw':docs[0]['artifacts'][0]['size_bytes']=1
            elif mutation=='custody':docs[3]['artifacts'].pop()
            elif mutation=='restore':docs[2]['verified']=False
            else:docs[1]['quarantine_operation']['performed']=True
            with self.subTest(mutation=mutation),self.assertRaises(current.admission.AdmissionError):current.zero_events(*docs)

if __name__=='__main__':unittest.main()
