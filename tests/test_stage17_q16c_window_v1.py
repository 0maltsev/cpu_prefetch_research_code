"""Original deadline and infrastructure lifetime, including stale preparation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_window_v1 as current


class WindowTests(unittest.TestCase):
    def fixture(self):
        n=current.NS;start=100*n;now=start+4*3600*n
        record=dict(started_monotonic_ns=start,global_deadline_ns=start+86400*n,
            completed_monotonic_ns=now-n,source_deadline_ns=start+22500*n,
            all_workers_reaped=True,boot_id='actual-boot',software_source_revision='actual-source')
        cfg=dict(boot_id='actual-boot',source_revision='actual-source',lifecycle_seconds=20*3600-3600,
            protected_work_ns=60420*n,stop_seconds=120)
        return record,cfg,now

    def test_original_day_fits_all_prospective_work_and_restoration(self):
        record,cfg,now=self.fixture();self.assertTrue(current.infrastructure(record,cfg,now=now))
        self.assertEqual(current.validate(record,now=now,qualification=True),20*3600*current.NS)

    def test_stale_infrastructure_and_one_second_budget_shortfall_reject(self):
        record,cfg,now=self.fixture()
        with self.assertRaisesRegex(ValueError,'outlive original'):current.infrastructure(record,cfg,now=now+1201*current.NS)
        total=current.QUALIFICATION+current.FAMILY+current.ANALYSIS+current.RESTORATION
        for spare in (-1,0):
            with self.assertRaisesRegex(ValueError,'cannot fit'):
                current.validate(record,now=record['global_deadline_ns']-(total+spare)*current.NS,qualification=True)

    def test_old_coarse_day_lifetime_and_incomplete_protected_work_reject(self):
        record,cfg,now=self.fixture();cfg['lifecycle_seconds']=86400
        with self.assertRaisesRegex(ValueError,'outlive original'):current.infrastructure(record,cfg,now=now)
        record,cfg,now=self.fixture();cfg['protected_work_ns']-=600*current.NS
        with self.assertRaisesRegex(ValueError,'protected work'):current.infrastructure(record,cfg,now=now)


if __name__=='__main__':unittest.main()
