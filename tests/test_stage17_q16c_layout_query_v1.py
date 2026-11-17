"""Pure native sizing against frozen919c486 libraries, with synthetic sources."""
import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path(os.environ.get('Q16C_LAYOUT_QUERY_BINARY',str(ROOT/'build/stage17-q16c-prep/layout-query-1/layout-query')))


@unittest.skipUnless(BINARY.exists(),'explicit frozen919c486 sizing binary required')
class NativeSizingTests(unittest.TestCase):
    def test_ring_near_and_linked_far_real_source_hash_and_exact_layout_checks(self):
        parent=json.loads((ROOT/'docs/evidence/stage17/D266-RESUMED-ADMISSION-20261116-01/original-parent-plan.json').read_bytes())
        with tempfile.TemporaryDirectory(prefix='q16c-native-sizing-software-') as t:
            for package,placement in [('R0','NEAR'),('L1','FAR')]:
                item=copy.deepcopy(next(x for x in parent['captures'] if x['capture']['package']==package and x['capture']['placement']==placement))
                c=item['capture'];c.update(schema_version='cpu-prefetch-stage17-formal-scheduled-capture/2',
                    method_id='MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1',scale_ordinal=0,load_level='L025',
                    cell_ordinal=c['cell_ordinal']*3,schedules=[])
                descriptors=[];bindings=[]
                try:
                    for i,phase in enumerate(('warmup','measurement')):
                        c['budget']['phases'][i].update(producer_attempt_limit=2,consumer_poll_limit=1000000000)
                        item['resources']['phase_capacity'][i].update(producer_primary_rows=2,consumer_primary_rows=2)
                        data=struct.pack('>QQ',1000,2000);digest=hashlib.sha256(data).hexdigest();identity=f'synthetic-original-{i}'
                        fd=os.memfd_create('synthetic-layout-source',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
                        try:
                            os.write(fd,data)
                            fcntl.fcntl(fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
                            reader=os.open('/proc/self/fd/'+str(fd),os.O_RDONLY|os.O_CLOEXEC)
                        finally:os.close(fd)
                        descriptors.append(reader);bindings.append(dict(artifact_id=identity,sha256=digest,size_bytes=16,descriptor=reader))
                        c['schedules'].append(dict(schedule_id='synthetic-schedule-'+str(i),seed_id='synthetic-source-seed-'+str(i),
                            seed_hex=str(i+1)*64,namespace_id='synthetic-source-namespace-'+str(i),source_origin_ticks=0,
                            source_horizon_ticks=c[phase+'_ns']*1000,offered_count=2,storage_format='SEALED_U64BE_ORIGINAL-v1',
                            source_artifact=dict(artifact_id=identity,sha256=digest)))
                    doc={k:item[k] for k in ('capture','resources','monitoring')}
                    doc['hardware_prestate']=[dict(cpu=i,value=0) for i in (0,1,8)]
                    doc['schedule_source_context']=dict(bindings=bindings,maximum_vector_bytes=64,
                        deadline_monotonic_ns=time.monotonic_ns()+30*10**9)
                    path=Path(t)/'input.json'
                    def run(mode):
                        path.write_text(json.dumps(doc))
                        return subprocess.run([str(BINARY),mode,str(path)],pass_fds=descriptors,capture_output=True,timeout=35)
                    result=run('--describe');self.assertEqual(result.returncode,0,result.stderr)
                    answer=json.loads(result.stdout)
                    self.assertEqual(answer['source_revision'],'919c48637cbdba9e466a3104f5cbb39f7184e39b')
                    self.assertIs(answer['declared_layout_rechecked'],True)
                    doc['resources'].update(answer['layout'])
                    result=run('--verify-declared');self.assertEqual(result.returncode,0,result.stderr)
                    doc['resources']['total_mapping_bytes']+=4096
                    self.assertNotEqual(run('--verify-declared').returncode,0)
                    doc['resources'].update(answer['layout']);bindings[1]['sha256']='0'*64
                    self.assertNotEqual(run('--describe').returncode,0)
                finally:
                    for fd in descriptors:os.close(fd)


if __name__=='__main__':unittest.main()
