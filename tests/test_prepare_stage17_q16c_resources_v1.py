"""Real source-byte pinning, read-only seals and complete owned-FD cleanup."""
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_stage17_q16c_resources_v1 as current


class SourcePairTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.rows=[]
        for i in range(2):
            p=Path(self.tmp.name)/f'source{i}.bin';raw=bytes([i])*16;p.write_bytes(raw)
            self.rows.append(dict(artifact_id=f'synthetic-source-{i}',path=str(p),size_bytes=16,sha256=hashlib.sha256(raw).hexdigest()))

    def test_exact_bytes_are_readonly_and_all_owned_descriptors_close(self):
        before=set(os.listdir('/proc/self/fd'))
        with current.source_pair(self.rows) as rows:
            self.assertEqual(len(rows),2)
            self.assertNotEqual(os.fstat(rows[0]['descriptor']).st_ino,os.fstat(rows[1]['descriptor']).st_ino)
            for i,row in enumerate(rows):
                self.assertEqual(os.pread(row['descriptor'],16,0),bytes([i])*16)
                with self.assertRaises(OSError):os.write(row['descriptor'],b'x')
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_changed_second_original_releases_first_source_without_replacement(self):
        before=set(os.listdir('/proc/self/fd'));self.rows[1]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'hash differs'):
            with current.source_pair(self.rows):self.fail('corrupt original accepted')
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)
        self.assertEqual(Path(self.rows[0]['path']).read_bytes(),bytes(16))

    def test_sizing_context_covers_both_possible_decode_peaks_and_io_block(self):
        for first,second in [(16,16),(1024,8),(8,1024)]:
            sources=[dict(size_bytes=first),dict(size_bytes=second)]
            context=current.sizing_source_context(sources,12345)
            self.assertGreaterEqual(context['maximum_vector_bytes'],max(2*first,first+2*second)+8192)
            self.assertEqual(context['bindings'],sources)
            self.assertEqual(context['deadline_monotonic_ns'],12345)


if __name__=='__main__':unittest.main()
