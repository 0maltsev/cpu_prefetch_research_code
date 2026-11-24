"""Corrected first-native qualification cannot extend the study or retry data."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_q15_continuation_window_v1 as current


class ContinuationTests(unittest.TestCase):
    def test_success_budget_is_new_subdeadline_with_the_original_day(self):
        n=current.NS;now=10**14;start=now-8*3600*n
        record=dict(started_monotonic_ns=start,global_deadline_ns=start+86400*n,
            completed_monotonic_ns=start+4*3600*n,source_deadline_ns=start+22500*n,all_workers_reaped=True)
        self.assertEqual(current.validate(record,now=now,qualification=True),16*3600*n)
        last=record['global_deadline_ns']-current.SUCCESS_ENVELOPE_SECONDS*n
        with self.assertRaisesRegex(ValueError,'cannot fit'):current.validate(record,now=last,qualification=True)
        record['global_deadline_ns']+=n
        with self.assertRaisesRegex(ValueError,'original24h'):current.validate(record,now=now,qualification=True)

    def fixture(self):
        return dict(clocks=dict(both_pairs_passed=True),failed_launch=dict(formal_capture_started=False,automatic_retry=False,
            error="RuntimeError('persistent Q15 session exited without a complete result: 1')"),
            terminal=dict(exit_code=1,leader_reaped=True,cleanup_error=None),restoration=dict(verified=True,partition_absent=True),
            owner=dict(status='PASS',verified_execution_uid=1000,source_revision='source',worker=dict(sha256='worker'),worker_executed=False),
            attempt_files=[],source_revision='source',worker_sha256='worker')

    def test_exact_unstarted_incident_and_corrected_owner_only(self):
        self.assertTrue(current.verify_retained(**self.fixture()))
        for group,key,value in [('clocks','both_pairs_passed',False),('terminal','leader_reaped',False),
            ('restoration','verified',False),('owner','worker_executed',True)]:
            bad=self.fixture();bad[group][key]=value
            with self.assertRaises(ValueError):current.verify_retained(**bad)
        bad=self.fixture();bad['attempt_files']=['stage17-q15_r-attempt-v4.json']
        with self.assertRaisesRegex(ValueError,'no retry'):current.verify_retained(**bad)

    def test_keeper_funds_only_isolated_work_but_global_gate_retains_analysis(self):
        n=current.NS;now=10**14;start=now-8*3600*n
        record=dict(started_monotonic_ns=start,global_deadline_ns=start+86400*n,
            completed_monotonic_ns=start+4*3600*n,source_deadline_ns=start+22500*n,all_workers_reaped=True,
            boot_id='boot',software_source_revision='source')
        cfg=dict(boot_id='boot',source_revision='source',lifecycle_seconds=16*3600-2400-120,
            protected_work_ns=(current.QUALIFICATION+current.FAMILY+120)*n,stop_seconds=120)
        self.assertTrue(current.infrastructure(record,cfg,now=now))
        cfg['lifecycle_seconds']=16*3600
        with self.assertRaisesRegex(ValueError,'restoration reserve'):current.infrastructure(record,cfg,now=now)


if __name__=='__main__':unittest.main()
