"""Actual journal snapshots reproduce the preview fork without stand changes."""
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_state_journal_v12 as journal
import finalize_stage17_descriptive_admission_v1 as recovery

FIXTURE = ROOT/'docs/evidence/stage17/EXT007-D309-ADMITTED-20261120-01/pre-recovery/journal'


class PreviewRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copytree(FIXTURE,self.root/'journal')
        self.preview = self.root/'journal/d308-scoped-admission-preview.json'
        self.destination = self.root/'preserved-preview.json'
        self.original = {p.name:p.read_bytes() for p in (self.root/'journal').glob('stage17-state-journal-*.json')}

    def lineage(self):
        return journal._lineage(evidence_root=self.root,
            latest_path=self.root/'journal/stage17-state-journal-000010.json',
            schema_path=ROOT/journal.SCHEMA_PATHS['journal_schema_sha256'],journal_directory=self.root/'journal')

    def test_actual_failure_then_unchanged_lineage_passes_with_preserved_preview(self):
        self.assertEqual(len(self.original),11)
        self.assertEqual(hashlib.sha256(self.original['stage17-state-journal-000010.json']).hexdigest(),recovery.JOURNAL_SHA)
        with self.assertRaisesRegex(journal.JournalError,'journal fork detected'): self.lineage()
        raw = self.preview.read_bytes()
        receipt = recovery.preserve_preview(self.preview,self.destination,recovery.PREVIEW_SHA)
        self.assertFalse(self.preview.exists()); self.assertEqual(self.destination.read_bytes(),raw)
        self.assertTrue(receipt['bytes_unchanged']); self.assertFalse(receipt['canonical_journal_modified'])
        lineage,latest = self.lineage()
        self.assertEqual(len(lineage),11); self.assertEqual(len(latest['resolution_records']),7)
        for name,value in self.original.items(): self.assertEqual((self.root/'journal'/name).read_bytes(),value)

    def test_changed_preview_or_existing_custody_destination_cannot_remove_evidence(self):
        self.preview.write_bytes(self.preview.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'exact preview'): recovery.preserve_preview(self.preview,self.destination,recovery.PREVIEW_SHA)
        self.assertTrue(self.preview.exists()); self.assertFalse(self.destination.exists())
        self.preview.write_bytes((FIXTURE/self.preview.name).read_bytes()); self.destination.write_bytes(b'keep')
        with self.assertRaises(FileExistsError): recovery.preserve_preview(self.preview,self.destination,recovery.PREVIEW_SHA)
        self.assertTrue(self.preview.exists()); self.assertEqual(self.destination.read_bytes(),b'keep')

    def test_a_genuine_second_branch_remains_blocking(self):
        recovery.preserve_preview(self.preview,self.destination,recovery.PREVIEW_SHA)
        (self.root/'journal/other-branch.json').write_bytes(self.destination.read_bytes())
        with self.assertRaisesRegex(journal.JournalError,'journal fork detected'): self.lineage()


if __name__ == '__main__': unittest.main()
