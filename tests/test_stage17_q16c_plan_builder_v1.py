"""Count-sized declaration arithmetic and real retained metadata bound parity."""
import copy
import hashlib
import json
import os
import fcntl
import struct
import subprocess
import tempfile
import time
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_plan_builder_v1 as current
from test_stage17_q16c_layout_query_v1 import BINARY,ROOT


class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent=json.loads((ROOT/'docs/evidence/stage17/D266-RESUMED-ADMISSION-20261116-01/original-parent-plan.json').read_bytes())

    def identities(self):
        return current.prospective_inputs(self.parent,master_hex='a'*64,bundle_root='/synthetic/actual-bundle',
            source_revision='919c48637cbdba9e466a3104f5cbb39f7184e39b',inventory_sha256='b'*64,
            boot_id='00000000-0000-4000-8000-000000000000')

    def test_full180_by_two_unique_sources_and_independent_namespaces(self):
        x=self.identities();sources=x['source_setup']['sources']
        self.assertEqual(len(sources),360);self.assertEqual(len(x['phase_identities']),360)
        for key in ('schedule_id','seed_id','seed_hex','namespace_id','artifact_id'):
            self.assertEqual(len({s[key] for s in sources}),360)
        self.assertFalse({p['seed_id'] for p in x['phase_identities']}&{p['seed_id'] for p in sources})
        self.assertEqual([p['load_level'] for p in sources[:6]],['L025','L025','L050','L050','L075','L075'])
        self.assertEqual({len(p['run_id']) for p in x['phase_identities']},{12})
        self.assertEqual(x,self.identities())

    def test_metadata_helper_reproduces_every_original120_capture_bound(self):
        for item in self.parent['captures']:
            result=current.bounds.metadata_bound(item['resources'],item['monitoring'])
            self.assertEqual(result['cold_heap_model_bytes'],item['execution_budget']['other_memory_bytes'])
            self.assertEqual(result['control_bytes']+current.MIB,item['execution_budget']['metadata_output_bytes'])

    def test_all_arrivals_fit_primary_buffers_and_drains_monitoring_geometry_preserved(self):
        x=self.identities();results=[dict(ordinal=i,exit_code=0,leader_reaped=True,
            provenance=dict(offered_count=i+1),binary=dict(sha256='c'*64)) for i in range(360)]
        rows=current.capture_inputs(self.parent,x,results,cpuset_prefix='/sys/fs/cgroup/synthetic/reserved/',q16a_handoff_sha256='d'*64)
        settings={}
        for item in self.parent['captures']:
            c=item['capture'];settings[(c['hardware_state'],c['package'],c['placement'],c['working_set_class'])]=item
        self.assertEqual(len(rows),180)
        for i,item in enumerate(rows):
            c,r,m=(item[k] for k in ('capture','resources','monitoring'))
            old=settings[(c['hardware_state'],c['package'],c['placement'],c['working_set_class'])]
            self.assertEqual(c['geometry'],old['capture']['geometry'])
            for j,phase in enumerate(c['budget']['phases']):
                count=i*2+j+1
                self.assertEqual(phase['producer_attempt_limit'],count)
                self.assertEqual(phase['consumer_poll_limit'],10**9)
                self.assertEqual(phase['drain_ns'],old['capture']['budget']['phases'][j]['drain_ns'])
                self.assertEqual(r['phase_capacity'][j],dict(producer_primary_rows=count,consumer_primary_rows=count))
            for key in ('during_first_page','during_page_count','during_offset_ticks','counter_limits','observer_wait_poll_limit'):
                self.assertEqual(m[key],old['monitoring'][key])
            relocated=[s['path'] for s in m['environment_sources'] if '/reserved/cpuset.' in s['path']]
            self.assertEqual(len(relocated),5);self.assertTrue(all(p.startswith('/sys/fs/cgroup/synthetic/reserved/') for p in relocated))
        self.assertEqual(current.FAMILY_SETUP_NS+current.FAMILY_CLEANUP_NS+180*(120*10**9+current.ARCHIVE_NS),47220*10**9)

    @unittest.skipUnless(BINARY.exists(),'explicit frozen919c486 sizing binary required')
    def test_complete_180_native_layouts_and_plan_resource_admission(self):
        # Synthetic binary values test sizing only. They intentionally have no
        # generator/provenance receipt and cannot authorize any experiment.
        x=self.identities();data=struct.pack('>QQ',1000,2000);digest=hashlib.sha256(data).hexdigest()
        results=[dict(ordinal=i,exit_code=0,leader_reaped=True,provenance=dict(offered_count=2),
                      binary=dict(sha256=digest)) for i in range(360)]
        rows=current.capture_inputs(self.parent,x,results,cpuset_prefix='/sys/fs/cgroup/synthetic/reserved/',q16a_handoff_sha256='d'*64)
        descriptors=[];layouts=[]
        try:
            for _ in range(2):
                writer=os.memfd_create('synthetic-builder-source',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
                try:
                    os.write(writer,data)
                    fcntl.fcntl(writer,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
                    descriptors.append(os.open('/proc/self/fd/'+str(writer),os.O_RDONLY|os.O_CLOEXEC))
                finally:os.close(writer)
            with tempfile.TemporaryDirectory(prefix='q16c-complete-plan-software-') as t:
                path=Path(t)/'input.json'
                for row in rows:
                    sources=row['capture']['schedules']
                    doc=copy.deepcopy(row);doc['hardware_prestate']=[dict(cpu=i,value=0) for i in (0,1,8)]
                    doc['schedule_source_context']=dict(bindings=[dict(artifact_id=s['source_artifact']['artifact_id'],
                        sha256=digest,size_bytes=16,descriptor=fd) for s,fd in zip(sources,descriptors,strict=True)],
                        maximum_vector_bytes=64,deadline_monotonic_ns=time.monotonic_ns()+30*10**9)
                    path.write_text(json.dumps(doc));result=subprocess.run([str(BINARY),'--describe',str(path)],
                        pass_fds=descriptors,capture_output=True,timeout=35)
                    self.assertEqual(result.returncode,0,result.stderr);layouts.append(json.loads(result.stdout))
            # A portable conservative compressBound envelope for this arithmetic
            # test, not a codec claim: no compression credit is taken.
            plan,proof=current.assemble(self.parent,x,rows,layouts,profile_sha256='e'*64,
                compress_bound=lambda n:n+(n>>8)+1024)
            extent=current.contract.validate_plan(plan)
            self.assertEqual(len(extent.captures),180)
            self.assertEqual(plan['source_transport']['source_bytes'],360*16)
            self.assertEqual(proof['family_watchdog_ns'],47220*10**9)
            self.assertLess(plan['budget']['memory_bytes'],64*1024**3)
            self.assertEqual(plan['storage']['program_scope_sha256'],self.parent['storage']['program_scope_sha256'])
            self.assertTrue(all(r['resources']['region_bytes']!=[1]*7 for r in plan['captures']))
        finally:
            for descriptor in descriptors:os.close(descriptor)


if __name__=='__main__':unittest.main()
