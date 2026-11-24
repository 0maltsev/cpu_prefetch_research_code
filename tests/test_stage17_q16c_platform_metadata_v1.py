"""Actual D233 inventory charges ancillary control receipts; no experiments."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_archive_custody_v1 as custody
import stage17_q16c_platform_metadata_v1 as current
import stage17_q16c_compaction_integration_v1 as previous

class Witness:
    value=0
    def verify(self):
        row=dict(requested_value=0,observed_value=self.value,verified=self.value==0,witness_sha256='e'*64)
        if self.value:raise previous.ControlReadbackFailure(row)
        return row

class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'build');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.program=self.root/'program'
        self.scope=custody.ProgramStore.initialize(self.program,program_id='software-only',storage_domain_id='test-domain',prospective_admission_sha256='a'*64)
        self.witness=Witness()
    def observations(self,**kw):
        return current.Observations(self.witness,self.root/'observations',request_sha256='a'*64,plan_sha256='b'*64,
            capture_count=kw.get('count',94),program_root=self.program,program_scope_sha256=kw.get('scope',self.scope))
    def test_published_receipts_are_charged_by_unchanged_real_inventory(self):
        limits=custody.CustodyLimits(131072,1024,4096,131072,time.monotonic_ns()+10**9)
        with custody.ProgramStore(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits) as store:
            before=store.physical_accounting().quota_bytes
            observed=self.observations();observed.before_capture(0);observed.after_capture(0,dict(sha256='c'*64))
            observed.flush(store)
            after=store.physical_accounting().quota_bytes
            self.assertGreaterEqual(after-before,observed.metadata_bytes)
        self.assertEqual(len(observed.metadata_bindings),1)
        for binding in observed.metadata_bindings:
            raw=Path(binding['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),binding['sha256'])
            self.assertEqual(len(raw),binding['size_bytes'])
            self.assertEqual(Path(binding['path']).parent,self.program/'metadata')
    def test_failed_readback_is_preserved_and_charged_before_propagation(self):
        observed=self.observations();observed.before_capture(0);self.witness.value=1
        with self.assertRaises(previous.ControlReadbackFailure):observed.after_capture(0,{})
        limits=custody.CustodyLimits(131072,1024,4096,131072,time.monotonic_ns()+10**9)
        store_type=current.retaining_store_class(custody.ProgramStore,observed)
        with store_type(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits):pass
        self.assertEqual(len(observed.metadata_bindings),1)
        bundle=json.loads(Path(observed.metadata_bindings[0]['path']).read_bytes())
        self.assertEqual(bundle['observation_count'],2)
        self.assertEqual(bundle['observations'][-1]['control']['observed_value'],1)

    def test_store_failure_preserves_original_error_and_releases_lock(self):
        observed=self.observations();observed.before_capture(0)
        limits=custody.CustodyLimits(131072,1024,4096,131072,time.monotonic_ns()+10**9)
        store_type=current.retaining_store_class(custody.ProgramStore,observed)
        with self.assertRaisesRegex(RuntimeError,'original failure'):
            with store_type(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits):
                raise RuntimeError('original failure')
        self.assertEqual(len(observed.metadata_bindings),1)
        with custody.ProgramStore(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits):pass

    def test_bound_and_foreign_scope_stop_before_unaccounted_capture(self):
        with self.assertRaisesRegex(RuntimeError,'scoped archive'):self.observations(scope='0'*64)
        observed=self.observations();observed.metadata_bytes=2*1024**2
        with self.assertRaisesRegex(RuntimeError,'allowance'):observed.before_capture(0)
        self.assertEqual(observed.active,None)
    def test_ninety_four_only_and_no_unbounded_or_symlink_metadata(self):
        with self.assertRaisesRegex(RuntimeError,'exactly94'):self.observations(count=180)
        path=self.root/'too-large';path.write_bytes(b'x'*8193)
        with self.assertRaisesRegex(RuntimeError,'byte bound'):current.bounded(path,8192)
        link=self.root/'link';link.symlink_to(path)
        with self.assertRaises(Exception):current.bounded(link,8192)

    def test_complete94_sequence_is_published_once_in_existing_final_custody_transaction(self):
        observed=self.observations()
        for ordinal in range(94):
            observed.before_capture(ordinal)
            observed.after_capture(ordinal,dict(file_name=f'formal-capture-{ordinal}-final-checkpoint.json',
                size_bytes=100,sha256='c'*64))
        observed.complete();self.assertTrue(observed.ready())
        limits=custody.CustodyLimits(131072,1024,4096,131072,time.monotonic_ns()+10**9)
        store_type=current.retaining_store_class(custody.ProgramStore,observed)
        with store_type(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits) as store:
            self.assertEqual(len(observed.metadata_bindings),1)
            charged=store.physical_accounting().quota_bytes
        with store_type(self.program,scope_sha256=self.scope,family_id='b'*64,limits=limits) as store:
            self.assertEqual(store.physical_accounting().quota_bytes,charged)
        bundle=json.loads(Path(observed.metadata_bindings[0]['path']).read_bytes())
        self.assertEqual(bundle['observation_count'],188)
        self.assertLessEqual(observed.metadata_bindings[0]['size_bytes'],2*1024**2)
        self.assertFalse(observed.ready());self.assertEqual(len(observed.metadata_bindings),1)

if __name__=='__main__':unittest.main()
