"""Bounded metadata checks using synthetic D220 evidence; no stand authority."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16a_suffix_admission_v1 as suffix
from test_stage17_q16a_continuation_admission_v1 import CaptureEvidence,save


class SuffixAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.evidence=CaptureEvidence(self.root)

    def check(self,*,family=None):
        f=self.evidence;row=copy.deepcopy(f.row);row['local_ordinal']=row.pop('original_ordinal')
        reader=suffix.EvidenceReader()
        result=suffix.validate_capture(row,f.authenticated,f.parent,f.scope,reader,
            family_sha=suffix.previous.contract.PARENT_SHA256 if family is None else family)
        reader.finish();return result

    def test_generic_capture_matches_original_admission_and_keeps_globals(self):
        old=suffix.previous.MAX_FILES
        self.assertEqual(self.check(),self.evidence.validate())
        self.assertEqual(suffix.previous.MAX_FILES,old)

    def test_local_ordinal_is_independent_of_original_context_position(self):
        f=self.evidence;f.parent['captures'][0]['capture'].update(context_ordinal=3,repetition_ordinal=0)
        f.row.update(context_ordinal=3,repetition_ordinal=0)
        self.assertIsInstance(self.check(),dict)

    def test_wrong_source_family_and_changed_report_rejected(self):
        with self.assertRaises(suffix.previous.AdmissionError):self.check(family='0'*64)
        binding=self.evidence.row['validation_report_binding'];p=Path(binding['path']);p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(suffix.previous.AdmissionError):self.check()

    def test_native_count_discrepancy_rejected_even_if_report_shape_is_valid(self):
        f=self.evidence
        f.authenticated['native_result_after_cleanup']['session']['phases'][1]['producer']['full']+=1
        # The authenticated checkpoint bytes disagree; a status flag cannot fix it.
        with self.assertRaises(suffix.previous.AdmissionError):self.check()

    def test_custody_and_checkpoint_must_match_signed_original_inventory(self):
        cap=self.evidence.authenticated
        declared={a['logical']['file_name']:copy.deepcopy(a['logical']) for a in cap['artifacts']}
        declared.update({cap[key]['file_name']:copy.deepcopy(cap[key]) for key in ('checkpoint','custody_receipt')})
        suffix.match_signed_capture(cap,declared,0)
        for key in ('checkpoint','custody_receipt','logical','order'):
            changed=copy.deepcopy(cap)
            if key in ('checkpoint','custody_receipt'):changed[key]['sha256']='0'*64
            if key=='logical':changed['artifacts'][0]['logical']['sha256']='0'*64
            if key=='order':changed['artifacts'].reverse()
            with self.subTest(key=key),self.assertRaises(suffix.previous.AdmissionError):suffix.match_signed_capture(changed,declared,0)

    def test_process_completion_requires_typed_actual_cleanup(self):
        d=dict(status='ANALYSIS_EXITED',exit_code=0,all_own_children_reaped=True,execution_authority=False,
               raw_mutation=False,elapsed_seconds=123.5,maximum_sampled_scratch_bytes=1000)
        suffix.check_process_result(d)
        for key,value in [('status','ANALYSIS_ABORTED'),('exit_code',False),('exit_code',0.0),
                          ('all_own_children_reaped',1),('raw_mutation',True),('elapsed_seconds',float('nan')),
                          ('elapsed_seconds',float('inf')),('elapsed_seconds',259201),
                          ('maximum_sampled_scratch_bytes',256*1024**3+1)]:
            c=copy.deepcopy(d);c[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(suffix.previous.AdmissionError):suffix.check_process_result(c)

    def test_nonregular_or_symlink_evidence_not_accepted(self):
        p=self.root/'document';p.write_text('{}');link=self.root/'link';link.symlink_to(p)
        with self.assertRaises(suffix.previous.AdmissionError):suffix._current_binding(link)
        fifo=self.root/'fifo';os.mkfifo(fifo)
        with self.assertRaises(suffix.previous.AdmissionError):suffix._current_binding(fifo)

    def test_in_progress_analysis_cannot_enter_authenticated_composition(self):
        import stage17_q16a_composite_v1 as composite
        # Synthetic preparation can demonstrate rejection, never admission.
        plan={};c=dict(schema_version='software-offline-q16a-suffix-analysis/1',execution_authority=False,
                       repository_root=str(self.root),analysis_root=str(self.root/'analysis'))
        binding=save(self.root/'analysis-config.json',c)
        prepared=suffix.controller.PreparedArchiveAction(root=self.root,authorization={},authorization_bytes=b'',
            request={'action_inputs':{'plan':plan}},request_bytes=b'',runtime={},worker_path=self.root/'unused',
            release={},validation=None,registry=None,archive_runtime_profile=None)
        with patch.multiple(suffix,CONFIG_SHA=binding['sha256'],PLAN_SHA=hashlib.sha256(suffix.previous.canonical(plan)).hexdigest()):
            with self.assertRaises(suffix.AnalysisIncomplete):
                composite.evaluate_authenticated(prepared=prepared,configuration_binding=binding,ring_geometry=[])
        self.assertFalse((self.root/'analysis').exists())

    def test_exact_finalizer_source_and_ledger_projection(self):
        import finalize_stage17_q16a_suffix_v1 as finalizer
        self.assertEqual(hashlib.sha256(Path(finalizer.__file__).read_bytes()).hexdigest(),suffix.FINALIZER_SHA)
        binding=dict(file_name='0000000000000010.json',size_bytes=123,sha256='a'*64)
        head=finalizer.projected_head(binding,10)
        self.assertEqual(head,dict(sequence_number=10,sha256='a'*64))
        self.assertNotEqual(head,binding)  # Original D244 comparison always fails.
        for sequence in (-1,True,1.0):
            with self.assertRaises(ValueError):finalizer.projected_head(binding,sequence)
        with self.assertRaises(ValueError):finalizer.projected_head({'sha256':'a'*64},10)

    def test_finalizer_does_not_accept_other_analysis_failures(self):
        import finalize_stage17_q16a_suffix_v1 as finalizer
        original='File "/bound/validate_suffix.py", line 1, in coordinate\nValueError: ledger changed during offline validation\n'
        finalizer.expected_error(original)
        for error in ('ValueError: raw hash mismatch',original.replace('validate_suffix.py','other.py'),
                      original+'ValueError: another error\n',''):
            with self.assertRaises(ValueError):finalizer.expected_error(error)
        # The ordinary admission path still rejects the original nonzero exit.
        d=dict(status='ANALYSIS_EXITED',exit_code=1,all_own_children_reaped=True,
               execution_authority=False,raw_mutation=False,elapsed_seconds=1.5,maximum_sampled_scratch_bytes=1000)
        with self.assertRaises(suffix.previous.AdmissionError):suffix.check_process_result(d)


if __name__=='__main__':unittest.main()
