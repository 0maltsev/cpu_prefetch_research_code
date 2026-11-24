"""Real interrupted-custody transitions; synthetic authority and cleanup fixture."""
from dataclasses import asdict
import pathlib
import unittest

import test_stage17_retained_capture_inspection_v1 as fixture
from test_stage17_formal_archive_v1 import codec_limit
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
import stage17_post_exit_custody_v1 as recovery


class RecoveryTests(fixture.RetainedInspectionTests):
    def evidence(self):
        return {role:asdict(self.store.retain_metadata('synthetic-recovery-'+role+'.json',
                archive.canonical(dict(role=role,synthetic_only=True))))
            for role in ('authorization','signature','prefix_validation','native_failure','restoration')}

    def close(self, *, verifier=None, readback=archive.verify_archive, evidence=None):
        values = self.evidence() if evidence is None else evidence
        # Fixture verifier supplies only deterministic software state. Production
        # must authenticate actual signed authority, all17 reports and absence.
        if verifier is None:
            def verifier(document,sources):
                self.assertTrue(document['native_complete'])
                self.assertEqual(len(sources),6)
        with codec_limit():
            return recovery.close_published_capture(store=self.store,action='Q16b',capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint),profile=self.f.profile,limits=self.f.limits,
                readback=readback,verify_post_exit=verifier,retained_evidence=values)

    def test_post_exit_release_and_receipt_use_original_custody_contract(self):
        before = (self.store.working/self.checkpoint.file_name).read_bytes()
        calls=[]
        result=self.close(verifier=lambda *_: calls.append('verified absent'))
        self.assertEqual(result['repeated_measurements'],0)
        self.assertFalse(result['encoded_new_archives'])
        self.assertFalse(result['execution_authority'])
        self.assertGreaterEqual(len(calls),4)
        self.assertFalse((self.store.working/self.sources[-1].expected.file_name).exists())
        self.assertEqual((self.store.working/self.checkpoint.file_name).read_bytes(),before)
        self.assertEqual(self.store._capture_pending,set())
        actual=registry.verify_capture_metadata(store=self.store,action='Q16b',capture=self.capture,
            checkpoint_binding=asdict(self.checkpoint),receipt_binding=result['custody_receipt'],
            decoder_profile=self.f.profile,decoder_limits=self.f.limits)
        self.assertEqual(len(actual['artifacts']),6)
        self.assertEqual(actual['scientific_validity'],'NOT_ASSESSED')
        kinds=[self.store.read_verified_record(b)['kind'] for b in self.store._record_bindings]
        self.assertEqual(kinds.count('RECOVERY'),1)
        self.assertEqual(kinds[-1],'CUSTODY_RECEIPT')

    def test_boolean_or_failed_post_exit_proof_never_writes_intent(self):
        evidence=self.evidence()
        before=self.snapshot()
        for value in (True,False):
            with self.subTest(value=value),self.assertRaisesRegex(custody.CustodyError,'boolean'):
                self.close(verifier=lambda *_:value,evidence=evidence)
            self.assertEqual(self.snapshot(),before)
        def gone(*_):raise custody.CustodyError('worker still active')
        with self.assertRaisesRegex(custody.CustodyError,'worker still active'):
            self.close(verifier=gone,evidence=evidence)
        self.assertEqual(self.snapshot(),before)

    def test_missing_or_changed_retained_proof_prevents_recovery(self):
        evidence=self.evidence();before=self.snapshot()
        missing=dict(evidence);del missing['signature']
        with self.assertRaises(custody.CustodyError):self.close(evidence=missing)
        self.assertEqual(self.snapshot(),before)
        p=self.store.root/'metadata'/evidence['authorization']['file_name']
        p.write_bytes(p.read_bytes()+b' ')
        before=self.snapshot()
        with self.assertRaises(custody.CustodyError):self.close(evidence=evidence)
        self.assertEqual(self.snapshot(),before)

    def test_changed_original_cannot_be_released(self):
        evidence=self.evidence()
        p=self.store.working/self.sources[-1].expected.file_name
        p.write_bytes(b'changed')
        before=self.snapshot()
        with self.assertRaises(archive.ArchiveError):self.close(evidence=evidence)
        self.assertEqual(self.snapshot(),before)

    def test_real_interrupted_release_intent_is_outside_this_recovery(self):
        evidence=self.evidence();source=self.sources[-1]
        state=self.store._states[source.artifact_id]
        self.store.append('RELEASE_INTENT',source.artifact_id,state['payload'])
        before=self.snapshot()
        with self.assertRaises(archive.ArchiveError):self.close(evidence=evidence)
        self.assertEqual(self.snapshot(),before)
        self.assertTrue((self.store.working/source.expected.file_name).exists())

    def test_bad_actual_readback_retains_recovery_intent_and_original(self):
        with self.assertRaises(archive.ArchiveError):self.close(readback=lambda *_args,**_kwargs:True)
        self.assertEqual(self.store._states[self.sources[-1].artifact_id]['kind'],'PUBLISHED')
        self.assertTrue((self.store.working/self.sources[-1].expected.file_name).exists())
        self.assertFalse((self.store.working/'formal-capture-0-archive-custody.json').exists())
        kinds=[self.store.read_verified_record(b)['kind'] for b in self.store._record_bindings]
        self.assertEqual(kinds[-1],'RECOVERY')

    def test_lost_post_exit_condition_after_intent_prevents_release(self):
        calls=[]
        def verifier(*_):
            calls.append(1)
            if len(calls)>=3:raise custody.CustodyError('post-exit condition changed')
        with self.assertRaisesRegex(custody.CustodyError,'condition changed'):self.close(verifier=verifier)
        self.assertTrue((self.store.working/self.sources[-1].expected.file_name).exists())
        self.assertEqual(self.store._states[self.sources[-1].artifact_id]['kind'],'PUBLISHED')

    def test_mixed_private_decoder_and_store_namespaces_fail_before_mutation(self):
        import types
        evidence=self.evidence();before=self.snapshot()
        wrong=types.SimpleNamespace(**{**vars(custody),'archive':types.SimpleNamespace(**vars(archive))})
        with self.assertRaisesRegex(custody.CustodyError,'namespaces differ'):
            recovery.close_published_capture(store=self.store,action='Q16b',capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint),profile=self.f.profile,limits=self.f.limits,
                readback=archive.verify_archive,verify_post_exit=lambda *_:None,
                retained_evidence=evidence,custody_api=wrong)
        self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
