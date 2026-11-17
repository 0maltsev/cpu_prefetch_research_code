"""Real archive reconstruction and raw validation; software process ownership.

The archive-profile authentication seam is synthetic. Decode, spool cleanup,
independent raw science and report publication are real existing implementations.
No stand observations, source generation or native experiment is performed.
"""
import copy
import contextlib
import dataclasses
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_analysis_v1 as current
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
from test_stage17_formal_archive_v1 import ArchiveFixture
import test_stage17_formal_scheduled_capture_validation_v2 as raw_fixture


def synthetic_child(connection,job,*args):
    connection.send(dict(status='VALID',ordinal=job['item']['capture']['ordinal']))
    connection.close()


def failed_child(connection,job,*args):
    connection.send(dict(status='FAILED',ordinal=job['item']['capture']['ordinal'],error='synthetic failure'))
    connection.close()


class AnalysisTests(unittest.TestCase):
    def test_packet_admission_time_is_charged_to_the_original_analysis_phase(self):
        start=10**12;now=start+75*10**9;end=start+current.TOTAL_NS
        self.assertEqual(current.phase_deadline(start,now,end),end)
        self.assertEqual(current.phase_deadline(start,now,end)-now,(5400-75)*10**9)
        with self.assertRaisesRegex(ValueError,'does not fit'):current.phase_deadline(start,now,end-1)
        with self.assertRaisesRegex(ValueError,'phase start'):current.phase_deadline(now+1,now,end)
        with self.assertRaisesRegex(ValueError,'expired'):current.phase_deadline(start,end,end)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='q16c-analysis-software-',dir=Path(__file__).resolve().parents[1]/'build')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)

    def test_actual_eight_archive_spool_science_and_valid_full_report(self):
        raw=raw_fixture.SourceCaptureTests();raw.setUp();self.addCleanup(raw.doCleanups)
        f=raw.fixture(full=True);encoder=ArchiveFixture(self.root)
        program=self.root/'program';(program/'archives').mkdir(parents=True)
        scratch=self.root/'scratch';scratch.mkdir();reports=self.root/'reports';reports.mkdir()
        control=copy.deepcopy(f.control);sources=[]
        for i,phase in enumerate(('warmup','measurement')):
            for role in ('producer','consumer'):sources.append((control['phases'][i][role],phase,role))
        sources.append((control['node_order'],None,None))
        for i,phase in enumerate(('warmup','measurement')):sources.append((control['schedules'][i]['stream'],phase,None))
        names=list(registry.capture_names('Q16c',0));artifacts=[]
        for i,(source,phase,worker) in enumerate(sources):
            data=(f.root/source['file_name']).read_bytes();source['file_name']=names[i]
            artifacts.append((names[i],data,phase,worker))
        artifacts.append((names[-1],archive.canonical(control),None,None))
        verified=[]
        for i,(name,data,phase,worker) in enumerate(artifacts):
            role=registry.role_profile('Q16c',name);header,_=encoder.header(data,role.layout)
            run_id=f.capture[phase]['run_id'] if phase and worker else None
            width=role.row_bytes(run_id)
            header.update(artifact_id='synthetic-evidence:'+name,artifact_role=role.artifact_role,
                canonical_format=role.canonical_format,phase=phase,run_id=run_id,worker=worker,
                row_bytes=width,row_count=len(data)//width if width else None,
                block_size_bytes=8192*width if width else archive.BYTE_BLOCK)
            wire=encoder.encode(data,header);stored=f'synthetic-{i}.cpfa';(program/'archives'/stored).write_bytes(wire)
            verified.append(dict(logical=dict(file_name=name,size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest()),
                header=header,role=dataclasses.asdict(role),archive_name=stored,
                physical=dict(size_bytes=len(wire),sha256=hashlib.sha256(wire).hexdigest())))
        item=dict(capture=f.capture,resources=f.resources,monitoring=f.monitoring)
        job=dict(item=item,verified=dict(artifacts=verified,native_result_after_cleanup=f.final),
            program_root=str(program),scratch=str(scratch),reports=str(reports),canonical_bytes=sum(len(x[1]) for x in artifacts))
        context=multiprocessing.get_context('fork');receiver,sender=context.Pipe(duplex=False)
        with mock.patch.object(current.images,'selected_archive_modules',return_value=(archive,custody)):
            process=context.Process(target=current._child,args=(sender,job,NS(decoder=encoder.profile),encoder.limits,
                f.hardware,min(os.sched_getaffinity(0)),time.monotonic_ns()+30*10**9))
            process.start();sender.close()
            try:
                self.assertTrue(receiver.poll(30));result=receiver.recv();process.join(2)
                self.assertEqual(process.exitcode,0);self.assertEqual(result['status'],'VALID',result)
                report=json.loads(Path(result['report']['path']).read_bytes())
                self.assertEqual(report['phases'][1]['counts']['full'],1)
                self.assertTrue(report['raw_reconciliation_validated']);self.assertTrue(result['canonical_spool_removed'])
                self.assertFalse(list(scratch.glob('*-capture-*')))
                self.assertEqual(len(list((program/'archives').iterdir())),8)
            finally:
                if process.is_alive():process.kill();process.join(2)
                receiver.close();process.close()

    def test_complete_pool_and_first_failure_cleanup_have_no_missing_reports_or_children(self):
        jobs=[dict(item=dict(capture=dict(ordinal=i)),canonical_bytes=i+1) for i in range(180)]
        before={p.pid for p in multiprocessing.active_children()}
        with mock.patch.object(current,'WORKERS',4),mock.patch.object(current,'_child',synthetic_child),contextlib.redirect_stdout(io.StringIO()):
            results=current.collect(jobs,None,None,None,[0,1,2,3],self.root,time.monotonic_ns()+15*10**9)
        self.assertEqual(set(results),set(range(180)))
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)
        failure=self.root/'failed';failure.mkdir()
        with mock.patch.object(current,'WORKERS',4),mock.patch.object(current,'_child',failed_child):
            with self.assertRaisesRegex(ValueError,'invalid required capture'):
                current.collect(jobs,None,None,None,[0,1,2,3],failure,time.monotonic_ns()+15*10**9)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)

    def test_actual_physical_core_and_aggregate_scratch_bounds(self):
        topology={i:(0,i%12) for i in range(24)}
        self.assertEqual(current.physical_cpus(set(range(24)),topology),list(range(12)))
        with self.assertRaises(ValueError):current.physical_cpus(set(range(11)),topology)
        self.assertEqual(current.scratch_envelope([current.GIB]*180,2*current.GIB),31*current.GIB)
        with self.assertRaises(ValueError):current.scratch_envelope([22*current.GIB]*180,0)
        with self.assertRaises(ValueError):current.scratch_envelope([current.GIB]*179,0)
        # Even a complete15-batch worst case plus setup/reaping fits90 minutes.
        self.assertLess(15*(current.CHILD_SECONDS+2)*10**9+current.PARENT_SETUP_NS+current.PARENT_CLEANUP_NS,current.TOTAL_NS)


if __name__=='__main__':unittest.main()
