"""Cold native inverse parity/security, using an explicit compiled image."""
import argparse
import array
import base64
import hashlib
import os
from pathlib import Path
import random
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_archive_inverse_native_v1 as native
import stage17_formal_archive_v1 as original


class NativeInverseTests(unittest.TestCase):
    image = None

    @classmethod
    def setUpClass(cls):
        if cls.image is None:
            raise unittest.SkipTest('explicit --library required')
        cls.raw = cls.image.read_bytes()
        cls.encoded = base64.b85encode(cls.raw)
        cls.sha = hashlib.sha256(cls.raw).hexdigest()
        cls.inverse = native.NativeInverse(cls.encoded, len(cls.raw), cls.sha)

    def decode(self, data, width):
        return self.inverse.inverse(data, width, deadline_ns=time.monotonic_ns() + 30_000_000_000)

    def test_independent_forward_transform_and_reference_parity(self):
        rng = random.Random(252)
        for rows in (0, 1, 2, 17, 8191, 8192):
            for columns in (1, 12, 17, 32):
                values = [rng.getrandbits(64) for _ in range(rows * columns)]
                expected = b''.join(v.to_bytes(8, 'little') for v in values)
                encoded = bytearray()
                for column in range(columns):
                    previous = 0
                    for row in range(rows):
                        value = values[row * columns + column]
                        encoded += ((value - previous) % (1 << 64)).to_bytes(8, 'little')
                        previous = value
                encoded = bytes(encoded)
                with self.subTest(rows=rows, columns=columns):
                    self.assertEqual(self.decode(encoded, columns * 8), expected)
                    self.assertEqual(original.inverse_columns(encoded, columns * 8,
                        deadline_ns=time.monotonic_ns() + 30_000_000_000), expected)

    def test_wraparound_and_every_opaque_word_survives(self):
        values = [0xffffffffffffffff, 1, 1, 0xffffffffffffffff]
        data = b''.join(v.to_bytes(8, 'little') for v in values)
        expected = [0xffffffffffffffff, 0, 1, 0]
        self.assertEqual(self.decode(data, 8), b''.join(v.to_bytes(8, 'little') for v in expected))

    def test_bad_geometry_and_expiry_fail_without_a_fallback(self):
        for data, width in ((b'', 0), (b'', 7), (b'a', 8), (bytes(8 * 8193), 8),
                            (bytes(native.MAX_BLOCK_BYTES + 8), 8), (b'', native.MAX_BLOCK_BYTES + 8)):
            with self.subTest(size=len(data), width=width), self.assertRaises(ValueError):
                self.decode(data, width)
        with self.assertRaisesRegex(ValueError, 'deadline'):
            self.inverse.inverse(bytes(8), 8, deadline_ns=0)
        with patch.object(native.time, 'monotonic_ns', side_effect=(0, 100)):
            with self.assertRaisesRegex(ValueError, 'deadline'):
                self.inverse.inverse(bytes(8), 8, deadline_ns=50)

    def test_wrong_native_bytes_and_binding_types_rejected(self):
        for encoded, size, sha in ((self.encoded, len(self.raw), '0' * 64),
                                   (self.encoded, len(self.raw) + 1, self.sha),
                                   (b'bad', len(self.raw), self.sha),
                                   (self.encoded, True, self.sha),
                                   (self.encoded, len(self.raw), '../bad')):
            with self.subTest(size=size, sha=sha), self.assertRaises(ValueError):
                native.NativeInverse(encoded, size, sha)

    def test_loaded_image_is_sealed_and_not_dependent_on_source_path(self):
        import fcntl
        seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        self.assertEqual(fcntl.fcntl(self.inverse.descriptor, fcntl.F_GET_SEALS) & seals, seals)
        with self.assertRaises(OSError):
            os.pwrite(self.inverse.descriptor, b'x', 0)
        with self.assertRaises(OSError):
            os.ftruncate(self.inverse.descriptor, 0)
        self.assertEqual(self.decode(bytes(16), 8), bytes(16))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    NativeInverseTests.image = args.library.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
