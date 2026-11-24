"""Actual owner signatures, exact188 original bindings and unchanged old job."""
import copy
from pathlib import Path
import sys
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_source_receipts_v2 as current
import test_stage17_q16c_source_receipts_v1 as original
from test_stage17_formal_scheduled_continuation_v1 import continuation_fixture

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.f=original.ReceiptTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source_plan=copy.deepcopy(self.f.plan)
        self.source_plan['budget']['metadata_output_bytes']=16*1024**2
        self.source_plan['budget']['max_output_bytes']+=16*1024**2
        self.source_plan['budget']['watchdog_ns']=47820*10**9
        self.plan=continuation_fixture(self.source_plan)
        self.bindings=self.f.sources[172:];self.registrations=self.f.registrations[172:]
    def validate(self):
        return current.validate(self.plan,self.bindings,self.registrations,self.f.proof,
            source_plan=self.source_plan,validation=self.f.validation,boot_id=self.f.boot,deadline_ns=time.monotonic_ns()+60*10**9)
    def test_complete_old_signed_job_selects_only_exact_original_pending188(self):
        before=copy.deepcopy(self.f.record)
        record,bindings=self.validate()
        self.assertEqual(len(bindings),188);self.assertEqual(record,before)
        self.assertEqual([b['artifact_id'] for b in bindings],[s['artifact_id'] for s in self.f.sources[172:]])
        self.assertEqual(sum(b['size_bytes'] for b in bindings),self.plan['source_transport']['source_bytes'])
    def test_completed_sources_are_not_reopened_or_revalidated(self):
        path=Path(self.f.sources[0]['binding']['path']);path.unlink()
        self.assertEqual(len(self.validate()[1]),188)
    def test_pending_corruption_reordering_and_forged_local_source_identity_stop(self):
        path=Path(self.bindings[0]['binding']['path']);saved=path.read_bytes();path.write_bytes(b'x'*len(saved))
        with self.assertRaises(current.Error):self.validate()
        path.write_bytes(saved);self.bindings[0],self.bindings[1]=self.bindings[1],self.bindings[0]
        with self.assertRaises(current.Error):self.validate()
        self.bindings[0],self.bindings[1]=self.bindings[1],self.bindings[0]
        self.plan['captures'][0]['capture']['schedules'][0]['seed_hex']='f'*64
        with self.assertRaises(current.Error):self.validate()
    def test_omitted_original_job_or_pending_namespace_and_wrong_signature_stop(self):
        self.f.trust['measurements']['principal']='foreign'
        with self.assertRaises(current.controller.support.ControllerError):self.validate()
        self.f.trust['measurements']['principal']='synthetic-owner'
        self.registrations.pop()
        with self.assertRaises(current.Error):self.validate()
        self.registrations=self.f.registrations[172:];self.f.record['sources'].pop();self.f.sign()
        with self.assertRaises(current.Error):self.validate()
    def test_producer_history_and_generation_dependencies_cannot_change(self):
        self.f.record['sources'][172]['leader_reaped']=False;self.f.sign()
        with self.assertRaises(current.Error):self.validate()
        self.f.record['sources'][172]['leader_reaped']=True;self.f.sign()
        p=self.f.bundle/'tools/generate_schedule.py';p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaises(current.Error):self.validate()

if __name__=='__main__':unittest.main()
