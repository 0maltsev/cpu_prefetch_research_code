"""Approved single day, ordered finite budgets and actual packet byte binding."""
import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_execution_window_v3 as current

SOURCE='b'*40
WORKER='c'*64
EXPECTED=dict(expected_source=SOURCE,expected_worker=WORKER,expected_boot=current.previous.BOOT)

def record():
    return dict(schema_version=current.SCHEMA,execution_window_id=current.IDENTITY,decision_id='D288',
        source_revision=SOURCE,worker_sha256=WORKER,boot_id=current.previous.BOOT,stand_id='software-only',
        started_monotonic_ns=10**15,global_deadline_ns=10**15+86400*10**9,started_at_utc='2026-11-19T12:00:00Z',
        bindings={name:{} for name in current.ROLES},automatic_retries=0,new_windows_allowed=0,
        execution_authority=False,phase18_authority=False,**{name+'_seconds':n for name,n in current.PHASES})

class WindowTests(unittest.TestCase):
    def test_all_six_exact_phase_budgets_and_remaining_envelope(self):
        r=record();self.assertEqual(current.TOTAL,42860)
        self.assertEqual([name for name,_ in current.PHASES],['prefix_validation','qualification','preparation','collection','restoration','suffix_analysis'])
        for index,(name,_) in enumerate(current.PHASES):
            required=sum(n for _,n in current.PHASES[index:])*10**9
            last=r['global_deadline_ns']-required
            current.validate(r,now=last-1,phase=name,**EXPECTED)
            with self.assertRaisesRegex(ValueError,'does not fit'):current.validate(r,now=last,phase=name,**EXPECTED)
        self.assertEqual(r,record())

    def test_no_old_release_reset_smaller_budget_extra_role_or_automatic_retry(self):
        changes=[('source_revision',current.previous.SOURCE),('worker_sha256',current.previous.WORKER),
            ('boot_id','other'),('started_monotonic_ns',True),('global_deadline_ns',record()['global_deadline_ns']+1),
            ('automatic_retries',True),('new_windows_allowed',1),('execution_authority',True),('phase18_authority',True),
            ('extra',False),('started_at_utc','2026-11-19T12:00:00')]
        changes.extend((name+'_seconds',seconds-1) for name,seconds in current.PHASES)
        for key,value in changes:
            r=record();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):current.validate_record(r,now=10**15,**EXPECTED)
        for key in current.ROLES:
            r=record();del r['bindings'][key]
            with self.subTest(missing=key),self.assertRaises(ValueError):current.validate_record(r,now=10**15,**EXPECTED)

    def test_actual_candidate_required_and_parent_clock_is_not_new_authority(self):
        for expected in (dict(EXPECTED,expected_source=current.previous.SOURCE),
                         dict(EXPECTED,expected_worker=current.previous.WORKER)):
            with self.assertRaises(ValueError):current.validate_record(record(),now=10**15,**expected)
        with self.assertRaises(ValueError):current.validate_record(record(),now=record()['global_deadline_ns'],**EXPECTED)

    def test_bounded_reader_hashes_actual_files_rejects_mutation_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'packet.json';p.write_bytes(b'{"original":true}\n')
            b=dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertEqual(current.parse(current.read(b)),dict(original=True))
            p.write_bytes(b'{"original":null}\n')
            with self.assertRaises(ValueError):current.read(b)
            link=Path(directory)/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):current.read(dict(b,path=str(link)))
        for raw in (b'{"x":1,"x":2}',b'{"x":1.0}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):current.parse(raw)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'build/stage17-q16c-d282/actual-launch-records/window.json').is_file(),
                         'preserved original incident packet unavailable')
    def test_actual_approvals_parent_incident_and_unchanged_old_window_bindings(self):
        root=Path(__file__).resolve().parents[1]
        def bind(path):
            raw=path.read_bytes();return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);placeholder=folder/'metadata.json';placeholder.write_bytes(b'{}')
            r=record();r['bindings']={key:bind(placeholder) for key in current.ROLES}
            roles=dict(decision='docs/decisions/0288-q16c-retained-prefix-continuation-proposal.md',
                acceptance='docs/evidence/stage17/Q16C-D288-ACCEPTED-20261119-01/owner-acceptance.json',
                platform_acceptance='docs/evidence/stage17/Q16C-D286-ACCEPTED-20261119-01/owner-acceptance.json',
                original_plan='build/stage17-q16c-d282/prospective-plan.json',
                original_failure='docs/evidence/stage17/Q16C-D285-NATIVE-STOP-20261118-01/stage17-q16c-failure-v6.json',
                original_execution_window='build/stage17-q16c-d282/actual-launch-records/window.json')
            for role,path in roles.items():r['bindings'][role]=bind(root/path)
            r['worker_sha256']=r['bindings']['candidate_worker']['sha256']
            before=copy.deepcopy(r);current.verify_bindings(r);self.assertEqual(r,before)
            approval=current.parse(current.read(r['bindings']['acceptance']));approval['remaining_capture_count']=93
            changed=folder/'altered-approval.json';changed.write_bytes(current.canonical(approval));r['bindings']['acceptance']=bind(changed)
            with self.assertRaisesRegex(ValueError,'owner approval'):current.verify_bindings(r)

if __name__=='__main__':unittest.main()
