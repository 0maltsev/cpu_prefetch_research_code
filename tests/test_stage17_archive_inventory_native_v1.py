"""Fresh native/Python inventory parity and authenticated caller checks."""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_archive_inventory_native_v1 as native
import stage17_archive_metadata_fast_v1 as previous
import stage17_formal_archive_custody_v1 as custody

LIBRARY = None


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = LIBRARY.read_bytes()
        cls.raw, cls.digest = raw, hashlib.sha256(raw).hexdigest()
        cls.native = native.NativeInventory(base64.b85encode(raw), len(raw), cls.digest)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'program'
        self.scope = custody.ProgramStore.initialize(self.root, program_id='native-inventory-test',
            storage_domain_id='test-only', prospective_admission_sha256='a' * 64)
        self.family = 'b' * 64
        self.limits = custody.CustodyLimits(131072, 10000, 10000, 131072,
                                           time.monotonic_ns() + 60_000_000_000)
        self.store = previous.make_store_class()(self.root, scope_sha256=self.scope,
                                                family_id=self.family, limits=self.limits)
        self.store.__enter__()
        self.addCleanup(self.store.__exit__)
        # Inventory-only fixture: no quota-bearing custody transaction or
        # synthetic claim about this development filesystem's free capacity.
        self.store.working.mkdir(mode=0o700)

    def scan(self, **overrides):
        arguments = dict(max_inventory_files=self.limits.max_inventory_files,
                         retained_relative_paths=[], deadline_ns=self.limits.deadline_ns)
        arguments.update(overrides)
        return self.native.scan(self.root, **arguments)

    def parity(self, **overrides):
        expected = self.store.physical_accounting()
        self.assertEqual(self.scan(**overrides), expected)
        return expected

    def test_empty_and_every_directory_accounting(self):
        self.parity()
        for name in ('archives', 'metadata', 'ledger'):
            for i in range(13):
                (self.root / name / str(i)).write_bytes(bytes([i]) * (i * 997))
        self.parity()

    def test_hardlinks_sparse_and_retained_receipt_deduplication(self):
        original = self.root / 'archives' / 'one'
        original.write_bytes(b'x' * 17000)
        os.link(original, self.root / 'metadata' / 'two')
        with (self.root / 'archives' / 'sparse').open('wb') as stream:
            stream.truncate(128 * 1024**2)
        receipt = self.store.working / 'formal-capture-0-final-checkpoint.json'
        receipt.write_bytes(b'checkpoint')
        self.store._retained_receipts.add((self.family, receipt.name))
        self.parity(retained_relative_paths=['working/' + self.family + '/' + receipt.name])

    def test_untracked_raw_workspace_is_exempt_but_counts_toward_bound(self):
        (self.store.working / 'native.bin').symlink_to('/nonexistent')
        self.parity()
        (self.store.working / 'another-native.bin').write_bytes(b'raw')
        with self.assertRaises(ValueError):
            self.scan(max_inventory_files=1)

    def test_every_scan_observes_new_files_and_changed_sizes(self):
        before = self.parity()
        p = self.root / 'archives' / 'new'
        p.write_bytes(b'data' * 3000)
        after = self.parity()
        self.assertGreater(after.quota_bytes, before.quota_bytes)
        with p.open('wb') as stream:
            stream.truncate(64 * 1024**2)
        self.assertGreater(self.parity().logical_size_bytes, after.logical_size_bytes)

    def test_symlinks_and_unexpected_types_are_rejected(self):
        for name in ('archives', 'metadata', 'ledger'):
            p = self.root / name / 'bad'
            p.symlink_to(self.root / 'scope.json')
            with self.assertRaises(ValueError):
                self.scan()
            p.unlink()
        p = self.store.working / 'formal-capture-0-archive-custody.json'
        p.mkdir()
        with self.assertRaises(ValueError):
            self.scan()

    def test_invalid_family_and_retained_path_rejected(self):
        bad = self.root / 'working' / 'not-a-sha'
        bad.mkdir()
        with self.assertRaises(ValueError):
            self.scan()
        bad.rmdir()
        for value in ('../scope.json', 'working/' + self.family + '/../scope.json',
                      'working/' + self.family + '/..', 'working/invalid/receipt'):
            with self.assertRaises(ValueError):
                self.scan(retained_relative_paths=[value])

    def test_image_binding_seals_and_expired_deadline(self):
        seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
        self.assertEqual(fcntl.fcntl(self.native.descriptor, fcntl.F_GET_SEALS) & seals, seals)
        for size, digest in ((len(self.raw) + 1, self.digest), (len(self.raw), '0' * 64)):
            with self.assertRaises(ValueError):
                native.NativeInventory(base64.b85encode(self.raw), size, digest)
        with self.assertRaises(ValueError):
            self.scan(deadline_ns=1)
        for value in (-1, 0, 1 << 64, True):
            with self.assertRaises(ValueError):
                self.scan(max_inventory_files=value)

    def test_composed_store_remains_private_and_checks_lock(self):
        original = custody.ProgramStore
        old_native = native._NATIVE
        native._NATIVE = self.native
        self.addCleanup(setattr, native, '_NATIVE', old_native)
        cls = native.make_store_class()
        self.assertIs(custody.ProgramStore, original)
        obj = cls(self.root, scope_sha256=self.scope, family_id=self.family, limits=self.limits)
        with self.assertRaises(custody.CustodyError):
            obj.physical_accounting()
        # Use the held store's private state solely to exercise the composed
        # public accounting method against the same genuinely held lock.
        obj.__dict__.update(self.store.__dict__)
        self.assertEqual(obj.physical_accounting(), self.store.physical_accounting())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--library', type=Path, required=True)
    args, rest = parser.parse_known_args()
    LIBRARY = args.library.resolve()
    unittest.main(argv=[sys.argv[0], *rest])
