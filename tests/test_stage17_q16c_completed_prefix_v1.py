"""Actual completed86 metadata, corruption gates and retained composition IDs."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_completed_prefix_v1 as current
import stage17_q16c_continuation_operator_v1 as operator

EVIDENCE=ROOT/'docs/evidence/stage17/Q16C-D292-PREFIX-VALIDATED-STOP-20261119-01'


def bound(path,original):
    raw=path.read_bytes()
    return dict(path=str(original),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


class CompletedPrefixTests(unittest.TestCase):
    def setUp(self):
        self.mapping={}
        self.complete=bound(EVIDENCE/'q16c-prefix-analysis-1/complete.json',current.ANALYSIS/'complete.json')
        self.prefix=bound(EVIDENCE/'q16c-prefix-analysis-1/accepted-prefix.json',current.ANALYSIS/'accepted-prefix.json')
        self.mapping[self.complete['path']]=EVIDENCE/'q16c-prefix-analysis-1/complete.json'
        self.mapping[self.prefix['path']]=EVIDENCE/'q16c-prefix-analysis-1/accepted-prefix.json'
        self.receipts=[]
        for i in range(86):
            report=current.ANALYSIS/'reports'/f'capture-{i}.json';receipt=current.ANALYSIS/f'capture-{i}-process.json'
            self.mapping[str(report)]=EVIDENCE/'reports'/report.name
            self.mapping[str(receipt)]=EVIDENCE/'processes'/receipt.name
            self.receipts.append(bound(self.mapping[str(receipt)],receipt))
        original_read=current.window.read
        def read(binding):
            if binding['path'] not in self.mapping:raise AssertionError('non-metadata read: '+binding['path'])
            return original_read(dict(binding,path=str(self.mapping[binding['path']])))
        self.reader=read

    def verify(self,receipts=None):
        with patch.object(current.window,'read',side_effect=self.reader):
            return current.verify_reports(self.complete,self.prefix,self.receipts if receipts is None else receipts)

    def test_actual86_reports_and_reaped_receipts_are_read_only_and_preserve_original_identity(self):
        before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.mapping.values()}
        complete,prefix=self.verify()
        self.assertEqual(len(complete['reports']),86)
        self.assertEqual(prefix['compaction_control'],'UNRECORDED')
        self.assertEqual(prefix['reports'][0]['artifact_id'],'Q16C-D292-PREFIX-0000')
        self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.mapping.values()})

    def test_missing_duplicate_or_substituted_receipt_cannot_reduce_coverage(self):
        for values in (self.receipts[:-1],self.receipts+[self.receipts[0]],
                       [self.receipts[0]]*86):
            with self.subTest(count=len(values)),self.assertRaises(ValueError):self.verify(values)

    def test_mutated_report_or_receipt_bytes_fail_without_raw_readback(self):
        with tempfile.TemporaryDirectory() as d:
            for original in (str(current.ANALYSIS/'reports/capture-0.json'),str(current.ANALYSIS/'capture-0-process.json')):
                old=self.mapping[original];changed=Path(d)/old.name
                raw=old.read_bytes();changed.write_bytes(raw[:-1]+bytes([raw[-1]^1]));self.mapping[original]=changed
                try:
                    with self.subTest(path=original),self.assertRaises(ValueError):self.verify()
                finally:self.mapping[original]=old

    def test_rebound_foreign_ordinal_or_failed_process_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'changed.json'
            for mutation in (dict(ordinal=1),dict(exit_code=1),dict(leader_reaped=False),dict(status='FAILED')):
                receipts=copy.deepcopy(self.receipts);original=self.mapping[receipts[0]['path']]
                value=json.loads(original.read_bytes());value.update(mutation);p.write_bytes(current.window.canonical(value))
                receipts[0]=bound(p,current.ANALYSIS/'capture-0-process.json');self.mapping[receipts[0]['path']]=p
                try:
                    with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.verify(receipts)
                finally:self.mapping[receipts[0]['path']]=original

    def test_composition_reuses_actual_accepted_report_ids_instead_of_relabeling_them(self):
        accepted=json.loads((EVIDENCE/'q16c-prefix-analysis-1/accepted-prefix.json').read_bytes())['reports']
        with patch.object(operator,'read',side_effect=self.reader):
            records=operator.report_records(self.complete,artifact_bindings=accepted)
        self.assertEqual([r['report_binding'] for r in records],accepted)
        self.assertEqual(records[85]['report_binding']['artifact_id'],'Q16C-D292-PREFIX-0085')
        for mutation in ('duplicate','hash'):
            changed=copy.deepcopy(accepted)
            if mutation=='duplicate':changed[1]['artifact_id']=changed[0]['artifact_id']
            else:changed[0]['sha256']='0'*64
            with self.subTest(mutation=mutation),patch.object(operator,'read',side_effect=self.reader),self.assertRaises(ValueError):
                operator.report_records(self.complete,artifact_bindings=changed)


if __name__=='__main__':unittest.main()
