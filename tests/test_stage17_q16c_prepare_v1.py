"""Actual release comparison and finite metadata custody; no stand actions."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_prepare_v1 as current
import stage17_q16c_admission_limits_v1 as limits
import stage17_q16a_q16c_descriptive_handoff_v1 as handoff


class PreparationTests(unittest.TestCase):
    def test_exact_metadata_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json';b=current.save(path,dict(execution_authority=False))
            self.assertEqual(current.document(b),dict(execution_authority=False))
            other=Path(directory)/'alias';other.symlink_to(path)
            with self.assertRaisesRegex(ValueError,'nonsymlink'):current.binding(other)
            path.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'changed'):current.read(b)

    def test_full_qualified_release_comparison_covers_only_five_reviewed_changes(self):
        root=Path(__file__).resolve().parents[1]
        old=list((root/'build/stage17-d260-release/verified-07a93fb').glob('cpu-prefetch-*'))
        new=list((root/'build/stage17-q16c-prep/verified-919c486').glob('cpu-prefetch-*'))
        if len(old)!=1 or len(new)!=1:self.skipTest('explicit actual old/new extracted bundles required')
        contexts=[dict(archive_bundle_root=str(p),source_revision=s) for p,s in zip((old[0],new[0]),
            ('07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8',current.SOURCE),strict=True)]
        proof=current.comparison(*contexts,limits.ADMISSION,handoff)
        self.assertEqual(len(proof['source_comparisons']),124)
        changed={row['relative_path'] for row in proof['source_comparisons'] if row['original']['sha256']!=row['current']['sha256']}
        self.assertEqual(changed,set(handoff.REVIEWED_COLD_SOURCES))
        for row in proof['source_comparisons']:
            if row['relative_path'] in changed:self.assertEqual(row['current']['sha256'],handoff.REVIEWED_COLD_SOURCES[row['relative_path']])
        self.assertEqual(proof['queue_libraries']['original']['sha256'],proof['queue_libraries']['current']['sha256'])
        for row in proof['project_headers']:self.assertEqual(row['original']['sha256'],row['current']['sha256'])

    def test_final_family_authority_preparation_is_charged_before_registration(self):
        now=10**12;total=(47820+5400+2400)*10**9
        self.assertEqual(current.remaining(dict(global_deadline_ns=now+total+1),now=now),total+1)
        with self.assertRaisesRegex(ValueError,'original-window envelope'):
            current.remaining(dict(global_deadline_ns=now+total),now=now)


if __name__=='__main__':unittest.main()
