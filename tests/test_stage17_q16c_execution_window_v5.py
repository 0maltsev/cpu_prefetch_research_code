"""D295 exact additional authority, cached-prefix budgets and stopped lineage."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_execution_window_v5 as current
from test_stage17_q16c_execution_window_v4 import record as old_record,bind


class ResumeWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        stub=self.folder/'stub.json';stub.write_bytes(b'{}')
        r=old_record();r.update(schema_version=current.SCHEMA,execution_window_id=current.IDENTITY,decision_id='D295')
        del r['prefix_validation_seconds'];r['retained_prefix_admission_seconds']=120
        r['bindings']={role:bind(stub) for role in current.ROLES}
        self.record=r
        launch='docs/evidence/stage17/Q16C-D292-LAUNCH-20261119-01/'
        stop='docs/evidence/stage17/Q16C-D292-PREFIX-VALIDATED-STOP-20261119-01/'
        paths=dict(resume_decision='docs/decisions/0295-q16c-validated-prefix-qualification-continuation-proposal.md',
            resume_acceptance='docs/evidence/stage17/Q16C-D295-ACCEPTED-20261119-01/owner-acceptance.json',
            validation_window=launch+'window.json',validation_signature=launch+'window.json.sig',
            validation_result=stop+'d292-study-1/result.json',validation_recovery=stop+'d292-independent-recovery-1.json',
            validation_completion=stop+'q16c-prefix-analysis-1/complete.json',validated_prefix=stop+'q16c-prefix-analysis-1/accepted-prefix.json')
        for role,path in paths.items():r['bindings'][role]=bind(ROOT/path)
        r['bindings']['original_plan']=json.loads((ROOT/paths['validated_prefix']).read_bytes())['parent_plan']

    def verify(self):
        # Historical envelope verification is independently covered by v4 tests
        # and fresh stand checks; no mock touches the new approval/metadata gates.
        original_read=current.read
        def read(binding):
            if binding==self.record['bindings']['original_plan']:return b'{}'
            return original_read(binding)
        with patch.object(current.historical,'verify_bindings',return_value={}),patch.object(current,'read',side_effect=read):
            return current.verify_bindings(self.record)

    def test_actual_approval_and_exact_completed_prefix_allow_metadata_admission_only(self):
        before=copy.deepcopy(self.record);self.verify();self.assertEqual(self.record,before)
        self.assertEqual(current.TOTAL,39380)
        self.assertEqual(current.PHASES[0],('retained_prefix_admission',120))
        expected=dict(expected_source=self.record['source_revision'],expected_worker=self.record['worker_sha256'],expected_boot=current.previous.BOOT)
        current.validate(self.record,now=self.record['started_monotonic_ns'],phase='retained_prefix_admission',**expected)
        with self.assertRaises(ValueError):current.validate(self.record,now=self.record['started_monotonic_ns'],phase='prefix_validation',**expected)

    def test_old_approval_cannot_authorize_the_new_attempt(self):
        self.record['bindings']['resume_acceptance']=bind(ROOT/'docs/evidence/stage17/Q16C-D292-ACCEPTED-20261119-01/owner-acceptance.json')
        with self.assertRaisesRegex(ValueError,'D295 owner acceptance'):self.verify()

    def test_rebound_acceptance_cannot_change_counts_words_retry_or_budget(self):
        original=copy.deepcopy(self.record)
        for key,value in (('maximum_total_seconds',39381),('owner_message','approve'),('automatic_retry',True),
                          ('reused_capture_count',85),('remaining_capture_count',93),('repeat_completed_raw_validations',True)):
            self.record=copy.deepcopy(original);role='resume_acceptance'
            data=current.parse(current.read(self.record['bindings'][role]));data[key]=value
            p=self.folder/(key+'.json');p.write_bytes(current.canonical(data));self.record['bindings'][role]=bind(p)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'D295 owner acceptance'):self.verify()

    def test_rebound_completed_prefix_or_successful_stop_replacement_is_rejected(self):
        original=copy.deepcopy(self.record)
        for role in ('validated_prefix','validation_completion','validation_result','validation_recovery'):
            self.record=copy.deepcopy(original);data=current.parse(current.read(self.record['bindings'][role]));data['extra']='changed'
            p=self.folder/(role+'.json');p.write_bytes(current.canonical(data));self.record['bindings'][role]=bind(p)
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'exact completed D292 evidence'):self.verify()


if __name__=='__main__':unittest.main()
