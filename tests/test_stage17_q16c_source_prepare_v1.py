"""Software-only pool ownership, publication and original-source tests."""
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_source_prepare_v1 as current
import stage17_q16c_admission_limits_v1 as limits


def synthetic_job(source, output, bundle, basis):
    # No generator/capture claim: deterministic software IPC fixture only.
    return dict(ordinal=source['ordinal'], synthetic_software_fixture=True)


def broken_job(source, output, bundle, basis):
    if source['ordinal']==4: raise ValueError('synthetic source failure')
    time.sleep(30)
    return synthetic_job(source, output, bundle, basis)


class SourceJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.basis=json.dumps(dict(base_rates={k:dict(numerator=n,denominator=4)
            for k,n in [('L025',1),('L050',2),('L075',3)]})).encode()
        self.sources=[dict(ordinal=i,phase=('warmup','measurement')[i%2],
                           load_level=('L025','L050','L075')[i//2%3]) for i in range(360)]

    def collect(self, job, deadline):
        with mock.patch.object(current,'WORKERS',4), mock.patch.object(current,'_original_job',job):
            return current.collect_sources(self.sources,self.root,self.root,self.basis,deadline)

    def test_complete_ordered_publication_requires_actual_worker_reaping(self):
        before={p.pid for p in multiprocessing.active_children()}
        rows=self.collect(synthetic_job,time.monotonic_ns()+10**10)
        self.assertEqual(set(rows),set(range(360)))
        self.assertTrue(all(r['leader_reaped'] is True and r['exit_code']==0 for r in rows.values()))
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)
        self.assertNotIn('leader_reaped',json.loads((self.root/'source-progress-000.json').read_bytes()))
        self.assertTrue(json.loads((self.root/'source-result-000.json').read_bytes())['leader_reaped'])

    def test_first_error_reaps_every_owned_worker_without_success_publication(self):
        before={p.pid for p in multiprocessing.active_children()}; started=time.monotonic()
        with self.assertRaisesRegex(ValueError,'synthetic source failure'):
            self.collect(broken_job,time.monotonic_ns()+10**10)
        self.assertLess(time.monotonic()-started,5)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)
        self.assertFalse(list(self.root.glob('source-result-*.json')))

    def test_deadline_reaps_all_workers_and_does_not_publish_completed_family(self):
        before={p.pid for p in multiprocessing.active_children()}
        with self.assertRaisesRegex(ValueError,'deadline'):
            self.collect(broken_job,1)
        self.assertEqual({p.pid for p in multiprocessing.active_children()},before)
        self.assertFalse(list(self.root.glob('source-result-*.json')))

    def test_strict_source_setup_and_exclusive_publication(self):
        for raw in (b'{"a":1,"a":2}',b'{"a":1.0}',b'{"a":NaN}'):
            with self.assertRaises(ValueError): current.strict_json(raw)
        current.save(self.root/'once.json',b'{}')
        with self.assertRaises(FileExistsError): current.save(self.root/'once.json',b'{}')

    def test_new_inventory_limit_is_finite_and_does_not_mutate_historical_reader(self):
        rows=[dict(path=f'tools/source{i}.py',size_bytes=1,sha256='a'*64) for i in range(4119)]
        self.assertEqual(len(limits.ADMISSION._inventory(dict(files=rows))),4119)
        with self.assertRaises(limits.original.AdmissionError): limits.original._inventory(dict(files=rows))
        rows.extend(dict(path=f'tools/source{i}.py',size_bytes=1,sha256='a'*64) for i in range(4119,8193))
        with self.assertRaises(limits.original.AdmissionError): limits.ADMISSION._inventory(dict(files=rows))
        a,b=limits.make_handoffs()
        self.assertIs(a.consume.__globals__['_release'].__globals__['admission'],limits.ADMISSION)
        self.assertIs(b.consume.__globals__['compatibility'],a)


if __name__=='__main__': unittest.main()
