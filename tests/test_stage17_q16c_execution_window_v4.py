"""D292 additional authority requires unchanged science and exact stopped history."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_execution_window_v4 as current

SOURCE='b'*40
WORKER='c'*64
EXPECTED=dict(expected_source=SOURCE,expected_worker=WORKER,expected_boot=current.previous.BOOT)


def record():
    return dict(schema_version=current.SCHEMA,execution_window_id=current.IDENTITY,decision_id='D292',
        source_revision=SOURCE,worker_sha256=WORKER,boot_id=current.previous.BOOT,stand_id='software-only',
        started_monotonic_ns=10**16,global_deadline_ns=10**16+86400*10**9,started_at_utc='2026-11-19T16:00:00Z',
        bindings={name:{} for name in current.ROLES},automatic_retries=0,new_windows_allowed=0,
        execution_authority=False,phase18_authority=False,**{name+'_seconds':n for name,n in current.PHASES})


def bind(path):
    raw=path.read_bytes()
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


class AdditionalWindowTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        p=self.root/'metadata.json';p.write_bytes(b'{}')
        self.record=record();self.record['bindings']={key:bind(p) for key in current.ROLES}
        accepted='docs/evidence/stage17/Q16C-D292-ACCEPTED-20261119-01/'
        stopped='docs/evidence/stage17/Q16C-D288-PREFIX-STOP-20261119-01/'
        paths=dict(decision='docs/decisions/0288-q16c-retained-prefix-continuation-proposal.md',
            acceptance='docs/evidence/stage17/Q16C-D288-ACCEPTED-20261119-01/owner-acceptance.json',
            platform_acceptance='docs/evidence/stage17/Q16C-D286-ACCEPTED-20261119-01/owner-acceptance.json',
            original_plan='build/stage17-q16c-d282/prospective-plan.json',
            original_failure='docs/evidence/stage17/Q16C-D285-NATIVE-STOP-20261118-01/stage17-q16c-failure-v6.json',
            original_execution_window='build/stage17-q16c-d282/actual-launch-records/window.json',
            continuation_decision='docs/decisions/0292-q16c-metadata-stop-continuation-proposal.md',
            continuation_acceptance=accepted+'owner-acceptance.json',prior_execution_window=accepted+'prior-window.json',
            prior_execution_signature=accepted+'prior-window.json.sig',prior_result=stopped+'result.json',
            prior_recovery=stopped+'d288-independent-recovery-1.json',
            repair_verification='docs/evidence/stage17/Q16C-D291-PRIVATE-REGISTRY-20261119-01/verification-summary.json')
        self.original_lineage_available=all((ROOT/path).is_file() for path in paths.values())
        if not self.original_lineage_available:return
        for role,path in paths.items():self.record['bindings'][role]=bind(ROOT/path)
        self.record['worker_sha256']=self.record['bindings']['candidate_worker']['sha256']

    def replace_document(self,role,change):
        value=current.parse(current.read(self.record['bindings'][role]));change(value)
        p=self.root/(role+'.json');p.write_bytes(current.canonical(value))
        self.record['bindings'][role]=bind(p)

    def test_both_actual_approvals_and_exact_prior_failure_and_recovery_are_read_only(self):
        if not self.original_lineage_available:self.skipTest('preserved original lineage unavailable')
        before=copy.deepcopy(self.record)
        current.verify_bindings(self.record)
        self.assertEqual(self.record,before)
        self.assertEqual(current.PHASES,current.scientific.PHASES)
        self.assertEqual(current.TOTAL,42860)
        self.assertNotEqual(current.EVIDENCE,current.scientific.EVIDENCE)

    def test_old_approval_cannot_authorize_another_window(self):
        if not self.original_lineage_available:self.skipTest('preserved original lineage unavailable')
        self.record['bindings']['continuation_acceptance']=self.record['bindings']['acceptance']
        with self.assertRaisesRegex(ValueError,'additional D292 owner approval'):
            current.verify_bindings(self.record)

    def test_rebound_approval_cannot_change_counts_deadlines_or_retry_scope(self):
        if not self.original_lineage_available:self.skipTest('preserved original lineage unavailable')
        original=copy.deepcopy(self.record)
        for key,value in (('remaining_capture_count',93),('reused_capture_count',85),
                ('maximum_total_seconds',42861),('new_execution_windows',2),('automatic_retry',True),
                ('repeat_completed_raw_validations',True),('phase18_authority',True)):
            self.record=copy.deepcopy(original)
            self.replace_document('continuation_acceptance',lambda d:d.update({key:value}))
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'additional D292 owner approval'):
                current.verify_bindings(self.record)

    def test_rebound_prior_success_changed_clock_or_unverified_recovery_is_rejected(self):
        if not self.original_lineage_available:self.skipTest('preserved original lineage unavailable')
        original=copy.deepcopy(self.record)
        for role,change in (
                ('prior_result',lambda d:d.update(success=True)),
                ('prior_recovery',lambda d:d.update(verified=False)),
                ('prior_execution_window',lambda d:d.update(started_monotonic_ns=1))):
            self.record=copy.deepcopy(original);self.replace_document(role,change)
            with self.subTest(role=role),self.assertRaisesRegex(ValueError,'exact consumed D288 evidence'):
                current.verify_bindings(self.record)

    def test_unchanged_finite_phases_require_all_new_roles_and_no_retry(self):
        r=record()
        for index,(phase,_) in enumerate(current.PHASES):
            last=r['global_deadline_ns']-sum(n for _,n in current.PHASES[index:])*10**9
            current.validate(r,now=last-1,phase=phase,**EXPECTED)
            with self.assertRaises(ValueError):current.validate(r,now=last,phase=phase,**EXPECTED)
        for key in current.ROLES:
            r=record();del r['bindings'][key]
            with self.subTest(role=key),self.assertRaises(ValueError):
                current.validate_record(r,now=10**16,**EXPECTED)
        for key,value in (('decision_id','D288'),('execution_window_id',current.scientific.IDENTITY),
                ('new_windows_allowed',1),('automatic_retries',1),('prefix_validation_seconds',3601)):
            r=record();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                current.validate_record(r,now=10**16,**EXPECTED)


if __name__=='__main__':unittest.main()
