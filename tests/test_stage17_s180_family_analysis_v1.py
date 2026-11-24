"""Fresh actual archive/ledger metadata; synthetic native/parent claims only."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_family_analysis_v1 as analysis
import test_stage17_s180_archive_broker_v1 as broker_tests


class OriginalTests(unittest.TestCase):
    encoder=None
    def setUp(self):
        self.f=broker_tests.S180BrokerTests();self.f.encoder=self.encoder
        self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.outcome=self.f.live();self.request=self.f.request
        attempt=dict(software_fixture_only=True)
        raw=analysis.archive.canonical(attempt);name='s180-e0-attempt.json';(self.f.working/name).write_bytes(raw)
        attempt_ref=dict(file_name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
            role='S180_RUN_ATTEMPT',schema_identity='cpu-prefetch-stage17-s180-run-attempt/1',media_type='application/json')
        checkpoint_ref=dict(asdict(self.f.checkpoint),role='S180_CAPTURE_CHECKPOINT',
            schema_identity=analysis.pool.worker.capture.checkpoint_contract.SCHEMA,media_type='application/json')
        custody_ref=dict(asdict(self.outcome.receipt),role='S180_ARCHIVE_CUSTODY',
            schema_identity=analysis.pool.worker.capture.checkpoint_contract.CUSTODY_SCHEMA,media_type='application/json')
        self.native=dict(artifacts=[attempt_ref,*self.f.document['artifacts'],checkpoint_ref,custody_ref])
        # These are explicit software parent claims. Actual production reads
        # the original qualified parent's retained receipt, not this fixture.
        self.parent=dict(schema_version=analysis.parent.RECEIPT_SCHEMA,plan_sha256=self.f.family,execution_ordinal=0,
            checkpoint=asdict(self.f.checkpoint),custody_receipt=asdict(self.outcome.receipt),
            custody_registration=asdict(self.outcome.receipt_ledger_record),status='ARCHIVED_AND_RELEASED',broker_processes=25,
            broker_cleanup=dict(returncode=0,leader_reaped=True,process_group_gone=True,
                descendants_detected_after_leader_exit=False,cleanup_deadline_overrun=False,leader_wait_timed_out=False),
            scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
        self.parent_path=self.f.root/'metadata'/f's180-parent-{self.f.family}-e0.json';self.write_parent()

    def write_parent(self):self.parent_path.write_bytes(analysis.archive.canonical(self.parent))

    def load(self,phase_owner=None):
        with self.f.store() as store:
            return analysis._capture(store,self.request,self.native,0,self.f.profile,
                analysis.archive.DecodeLimits(32768,4*1024**2,4*1024**2,8*1024**2,4*1024**2,100,1<<22,self.f.deadline),
                phase_owner=phase_owner)

    def software_phase(self):
        # Explicit typed-owner boundary double; actual phase ownership is
        # independently covered by its source/restoration/process tests.
        owner=object.__new__(analysis.analysis_input.phase._AnalysisPhase)
        owner.plan_sha256=self.f.family;owner.deadline_ns=self.f.deadline;owner._pool_consumed=False
        owner.failed=False;owner.check=lambda:{}
        return owner

    def test_analysis_input_keeps_original_custody_but_never_grants_continuation(self):
        with mock.patch.object(analysis.registry,'_physical_metadata',side_effect=AssertionError('no duplicate full archive pass')):
            proof=self.load(self.software_phase())['registry_proof']
        self.assertEqual(proof['schema_version'],analysis.analysis_input.SCHEMA)
        self.assertFalse(proof['continuation_allowed']);self.assertTrue(proof['physical_sha256_verification_pending'])
        self.assertTrue(proof['independent_inverse_required']);self.assertFalse(proof['execution_authority'])

    def test_payload_damage_stays_pending_and_original_collection_route_still_rejects_it(self):
        receipt=json.loads((self.f.working/self.outcome.receipt.file_name).read_bytes())
        path=self.f.root/'archives'/receipt['artifacts'][0]['archive_name'];raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        proof=self.load(self.software_phase())['registry_proof']
        self.assertFalse(proof['continuation_allowed']);self.assertTrue(proof['physical_sha256_verification_pending'])
        with self.assertRaisesRegex(ValueError,'hash differs'):self.load()

    def test_serialized_foreign_consumed_or_expired_phase_cannot_prepare_inputs(self):
        with self.assertRaisesRegex(ValueError,'actual post-restoration'):self.load({})
        owner=self.software_phase();owner._pool_consumed=True
        with self.assertRaisesRegex(ValueError,'unconsumed analysis'):self.load(owner)
        owner=self.software_phase();owner.plan_sha256='f'*64
        with self.assertRaisesRegex(ValueError,'unconsumed analysis'):self.load(owner)
        owner=self.software_phase();owner.deadline_ns=self.f.deadline-1
        with self.assertRaisesRegex(ValueError,'deadline exceeds'):self.load(owner)
        self.assertTrue(owner.failed)

    def test_missing_physical_archive_still_fails_pending_header_preparation(self):
        receipt=json.loads((self.f.working/self.outcome.receipt.file_name).read_bytes())
        path=self.f.root/'archives'/receipt['artifacts'][0]['archive_name'];path.unlink()
        owner=self.software_phase()
        with self.assertRaises((ValueError,OSError)):self.load(owner)
        self.assertTrue(owner.failed)

    def test_actual_registered_eight_originals_are_read_without_raw_decode_or_ledger_write(self):
        before={p.name:p.read_bytes() for p in (self.f.root/'ledger').iterdir()}
        value=self.load();self.assertTrue(value['registry_proof']['continuation_allowed'])
        self.assertFalse(value['registry_proof']['inverse_readback_performed'])
        self.assertEqual(len(value['registry_proof']['artifacts']),8)
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.f.root/'ledger').iterdir()})

    def test_original_archive_epochs_require_full_inverse_separately_and_detect_same_byte_rewrite(self):
        record=self.load(self.software_phase())
        with self.f.store() as store:
            snapshot=analysis._archive_snapshot(store,[record]);self.assertEqual(len(snapshot),8)
            self.assertEqual(snapshot,analysis._archive_snapshot(store,[record]))
            path=store.root/'archives'/snapshot[0]['archive_name'];original=path.read_bytes();path.write_bytes(original)
            self.assertEqual(path.read_bytes(),original)
            self.assertNotEqual(snapshot,analysis._archive_snapshot(store,[record]))
        self.assertTrue(record['registry_proof']['physical_sha256_verification_pending'])

    def test_duplicate_or_missing_original_cannot_have_a_complete_epoch_snapshot(self):
        record=self.load(self.software_phase())
        with self.f.store() as store:
            with self.assertRaisesRegex(ValueError,'duplicate original'):analysis._archive_snapshot(store,[record,record])
            path=store.root/'archives'/record['registry_proof']['artifacts'][0]['archive_name'];path.unlink()
            with self.assertRaises(OSError):analysis._archive_snapshot(store,[record])

    def test_unprotected_original_permissions_block_epoch_publication(self):
        record=self.load(self.software_phase())
        with self.f.store() as store:
            path=store.root/'archives'/record['registry_proof']['artifacts'][0]['archive_name'];path.chmod(0o666)
            with self.assertRaisesRegex(ValueError,'snapshot file is unsafe'):analysis._archive_snapshot(store,[record])

    def test_changed_original_checkpoint_and_native_reference_hash_are_rejected(self):
        self.native['artifacts'][9]['sha256']='f'*64
        with self.assertRaises(ValueError):self.load()

    def test_parent_failure_and_foreign_custody_registration_cannot_be_promoted(self):
        self.parent['broker_cleanup']['returncode']=23;self.write_parent()
        with self.assertRaises(ValueError):self.load()
        self.parent['broker_cleanup']['returncode']=0
        self.parent['custody_registration']['sha256']='f'*64;self.write_parent()
        with self.assertRaises(ValueError):self.load()

    def test_current_physical_archive_damage_is_not_replaced_by_receipt_success(self):
        receipt=json.loads((self.f.working/self.outcome.receipt.file_name).read_bytes())
        path=self.f.root/'archives'/receipt['artifacts'][0]['archive_name'];path.unlink()
        with self.assertRaises((ValueError,OSError)):self.load()


class PublicationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='s180-family-publication-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        for name in ('captures','scratch'):(self.root/name).mkdir(mode=0o700)

    def test_complete_metadata_is_durable_and_never_overwrites_an_existing_result(self):
        result=analysis._publish(self.root,dict(software_fixture_only=True),lambda:None)
        self.assertEqual(result['binding']['file_name'],'family-validation.json')
        with self.assertRaises(FileExistsError):analysis._publish(self.root,{},lambda:None)
        self.assertEqual(json.loads((self.root/'family-validation.json').read_bytes()),dict(software_fixture_only=True))

    def test_late_expiry_retains_uncommitted_metadata_without_a_success_marker(self):
        calls=0
        def check():
            nonlocal calls
            calls+=1
            if calls==2:raise TimeoutError('injected original phase expiry')
        with self.assertRaises(TimeoutError):analysis._publish(self.root,dict(software_fixture_only=True),check)
        self.assertFalse((self.root/'family-validation.json').exists())
        self.assertTrue((self.root/'uncommitted-family-validation.json').exists())

    def test_serialized_completion_counts_cannot_replace_missing_actual_outputs(self):
        result=dict(result=dict(actual_worker_completion_verified=True,completed_captures=180,records=[]),
            binding=dict(file_name='complete.json'))
        with self.assertRaisesRegex(ValueError,'all180 actual output records'):
            analysis._outputs(None,self.root,result,[])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--encoder',type=Path,required=True)
    args,rest=parser.parse_known_args();OriginalTests.encoder=args.encoder.resolve();unittest.main(argv=[sys.argv[0],*rest])
