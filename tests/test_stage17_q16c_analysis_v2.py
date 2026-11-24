"""D288 selected pools: real decode/science, exact membership and owned cleanup."""
import contextlib
import inspect
import io
import multiprocessing
from pathlib import Path
import sys
import time
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_analysis_v1 as old
import stage17_q16c_analysis_v2 as current
import test_stage17_q16c_analysis_v1 as fixture


class SelectedAnalysisTests(fixture.AnalysisTests):
    # Reuse the existing real eight-archive fixture with the new child entry.
    def test_actual_eight_archive_spool_science_and_valid_full_report(self):
        with mock.patch.object(fixture,'current',current):
            super().test_actual_eight_archive_spool_science_and_valid_full_report()

    def test_packet_admission_time_is_charged_to_the_original_analysis_phase(self):
        start=10**12;now=start+75*10**9;end=start+3600*10**9
        self.assertEqual(current.phase_deadline(start,now,end)-now,3525*10**9)
        for observed,limit in ((now,end-1),(end,end)):
            with self.assertRaises(ValueError):current.phase_deadline(start,observed,limit)
        self.assertEqual(inspect.getsource(current._child),inspect.getsource(old._child))

    def test_complete_pool_and_first_failure_cleanup_have_no_missing_reports_or_children(self):
        before={p.pid for p in multiprocessing.active_children()}
        for kind,count in (('PREFIX86',86),('SUFFIX94',94)):
            jobs=[dict(item=dict(capture=dict(ordinal=i)),canonical_bytes=i+1) for i in range(count)]
            output=self.root/kind;output.mkdir()
            with mock.patch.object(current,'WORKERS',4),mock.patch.object(current,'_child',fixture.synthetic_child),contextlib.redirect_stdout(io.StringIO()):
                results=current.collect(jobs,None,None,None,[0,1,2,3],output,time.monotonic_ns()+15*10**9,kind=kind)
            self.assertEqual(set(results),set(range(count)))
            failure=self.root/(kind+'-failed');failure.mkdir()
            with mock.patch.object(current,'WORKERS',4),mock.patch.object(current,'_child',fixture.failed_child):
                with self.assertRaisesRegex(ValueError,'invalid required capture'):
                    current.collect(jobs,None,None,None,[0,1,2,3],failure,time.monotonic_ns()+15*10**9,kind=kind)
            self.assertEqual({p.pid for p in multiprocessing.active_children()},before)

    def test_actual_physical_core_and_aggregate_scratch_bounds(self):
        topology={i:(0,i%12) for i in range(24)}
        self.assertEqual(current.physical_cpus(set(range(24)),topology),list(range(12)))
        with self.assertRaises(ValueError):current.physical_cpus(set(range(11)),topology)
        for count in (86,94):
            self.assertEqual(current.scratch_envelope([current.GIB]*count,2*current.GIB),31*current.GIB)
            with self.assertRaises(ValueError):current.scratch_envelope([22*current.GIB]*count,0)
        for count in (85,87,93,95,180):
            with self.assertRaises(ValueError):current.scratch_envelope([current.GIB]*count,0)
        self.assertLess(8*302*10**9+current.PARENT_SETUP_NS+current.PARENT_CLEANUP_NS,current.TOTAL_NS)

    def test_membership_is_checked_before_any_child_and_no_generic_subset_is_allowed(self):
        jobs=[dict(item=dict(capture=dict(ordinal=i)),canonical_bytes=i+1) for i in range(86)]
        jobs[0]['item']['capture']['ordinal']=86
        with mock.patch.object(current,'_child') as child:
            for kind in ('PREFIX86','SUFFIX94','ARBITRARY'):
                with self.assertRaises(ValueError):
                    current.collect(jobs,None,None,None,list(range(12)),self.root,time.monotonic_ns()+10**9,kind=kind)
            child.assert_not_called()


if __name__=='__main__':unittest.main()
