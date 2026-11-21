"""Real temporary directory/ledger tests; no stand or experimental raw data."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_archive_custody_v1 as base
import stage17_formal_archive_v1 as archive
import stage17_s180_archive_custody_v1 as current
import stage17_s180_archive_reservation_v1 as reservation


class ReservationTests(unittest.TestCase):
    def setUp(self):
        # The real D233 failure reserve is16GiB; /tmp is a smaller tmpfs here.
        # Use the actual workspace filesystem rather than mocking free space.
        temp = tempfile.TemporaryDirectory(prefix="s180-reservation-",
            dir=Path(__file__).resolve().parents[1] / "build")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "program"
        self.scope = base.ProgramStore.initialize(self.root, program_id="synthetic-program",
            storage_domain_id="synthetic-disk", prospective_admission_sha256="a"*64)
        self.family, self.prior = "b"*64, "c"*64
        self.limits = base.CustodyLimits(131072, 1024, 4096, 131072, time.monotonic_ns()+30_000_000_000)
        with base.ProgramStore(self.root, scope_sha256=self.scope, family_id=self.prior, limits=self.limits) as store:
            store.prepare_family(self.prior)
        self.original_scope = (self.root / "scope.json").read_bytes()
        self.original_record = (self.root / "ledger/0000000000000000.json").read_bytes()

    def store(self, ext009=None, **changes):
        args = dict(scope_sha256=self.scope, family_id=self.family, limits=self.limits,
            ext009_resolution_sha256=ext009)
        args.update(changes)
        return current.ProgramStore(self.root, **args)

    def reserve(self):
        with self.store() as store:
            return store.reserve_family()

    def test_actual_inode_is_available_before_ext009_and_never_grants_capture(self):
        with self.store() as store:
            before = store.physical_usage()
            result = store.reserve_family()
            document, binding = store.inspect_reservation()
            self.assertEqual(result, dict(document=document, binding=asdict(binding)))
            st = store.working.stat()
            self.assertEqual(document["evidence_root_binding"], dict(absolute_path=str(store.working),
                device=st.st_dev, inode=st.st_ino))
            for flag in ("admission_bound", "execution_authority", "phase18_authority"):
                self.assertIs(document[flag], False)
            self.assertGreater(store.physical_usage(), before)
            self.assertEqual(list(store.working.iterdir()), [])
            with self.assertRaises(base.CustodyError):
                store.prepare_family(self.family)
            with self.assertRaises(base.CustodyError):
                store._family_scope_fields()
            self.assertEqual(store.scope["shared_program_quota_bytes"], base.PROGRAM_QUOTA)
        self.assertEqual((self.root / "scope.json").read_bytes(), self.original_scope)
        self.assertEqual((self.root / "ledger/0000000000000000.json").read_bytes(), self.original_record)

    def test_ext009_can_be_bound_once_after_reservation_and_same_inode_is_reused(self):
        original = self.reserve()
        with self.store("d"*64) as store:
            receipt = store.bind_admission()
            doc = archive.parse_json((self.root / "metadata" / receipt.file_name).read_bytes())
            self.assertEqual(doc["ext009_resolution_sha256"], "d"*64)
            self.assertEqual(doc["reservation"], original["binding"])
            self.assertEqual(store.prepare_family(self.family), store.working)
            self.assertEqual(store.inspect_reservation()[0], original["document"])
            self.assertIs(doc["execution_authority"], False)
            with self.assertRaises(FileExistsError):
                store.bind_admission()
        with self.store("d"*64) as store:
            store.prepare_family(self.family)
            self.assertEqual(store.working.stat().st_ino, original["document"]["evidence_root_binding"]["inode"])
        with self.store("e"*64) as store:
            with self.assertRaises(base.CustodyError):
                store.prepare_family(self.family)

    def test_legacy_replay_and_prior_family_remain_usable_without_new_ledger_kinds(self):
        self.reserve()
        with base.ProgramStore(self.root, scope_sha256=self.scope, family_id=self.prior, limits=self.limits) as store:
            self.assertEqual(set(store._families), {self.prior, self.family})
            store.prepare_family(self.prior)
        with base.ProgramStore(self.root, scope_sha256=self.scope, family_id=self.family, limits=self.limits) as store:
            with self.assertRaises(base.CustodyError):
                store.prepare_family(self.family)
        records = [json.loads(p.read_bytes()) for p in sorted((self.root / "ledger").iterdir())]
        self.assertEqual([r["kind"] for r in records], ["FAMILY", "FAMILY"])

    def test_repeated_reservation_and_second_family_are_rejected_without_adoption(self):
        self.reserve()
        for family in (self.family, "f"*64):
            with self.store(family_id=family) as store:
                before = sorted(p.name for p in (self.root / "metadata").iterdir())
                with self.assertRaises(base.CustodyError):
                    store.reserve_family()
                self.assertEqual(sorted(p.name for p in (self.root / "metadata").iterdir()), before)
        with self.store("d"*64) as store:
            with self.assertRaises(base.CustodyError):
                store.reserve_family()

    def test_orphan_directory_or_metadata_is_not_adopted_or_replaced(self):
        path = self.root / "working" / self.family
        path.mkdir()
        with self.store() as store:
            with self.assertRaises(base.CustodyError):
                store.reserve_family()
        self.assertEqual(list((self.root / "metadata").iterdir()), [])
        path.rmdir()
        original = self.root / "metadata" / f"s180-extension-{self.family}.json"
        original.write_bytes(b"retained incomplete software fixture")
        with self.store() as store:
            with self.assertRaises(base.CustodyError):
                store.reserve_family()
        self.assertEqual(original.read_bytes(), b"retained incomplete software fixture")
        self.assertFalse(path.exists())

    def test_missing_partial_or_changed_admission_blocks_before_capture(self):
        self.reserve()
        path = self.root / "metadata" / f"s180-admission-{self.family}.json"
        with self.store("d"*64) as store:
            with self.assertRaises(FileNotFoundError):
                store.prepare_family(self.family)
            store.bind_admission()
        raw = path.read_bytes()
        for changed in (b"{", raw.replace(b'd'*64, b'e'*64)):
            path.write_bytes(changed)
            with self.store("d"*64) as store:
                with self.assertRaises(base.CustodyError):
                    store.prepare_family(self.family)

    def test_wrong_directory_or_data_before_admission_blocks(self):
        self.reserve()
        path = self.root / "working" / self.family
        (path / "unapproved-data").write_bytes(b"software-only")
        with self.store("d"*64) as store:
            with self.assertRaises(base.CustodyError):
                store.bind_admission()
        (path / "unapproved-data").unlink()
        path.rename(path.with_name("e"*64))
        path.mkdir()
        with self.store("d"*64) as store:
            with self.assertRaises(base.CustodyError):
                store.bind_admission()

    def test_group_writable_reserved_directory_cannot_be_admitted(self):
        self.reserve()
        path = self.root / "working" / self.family
        path.chmod(0o770)
        with self.store("d"*64) as store:
            with self.assertRaises(base.CustodyError):
                store.bind_admission()
        path.chmod(0o700)


if __name__ == "__main__":
    unittest.main()
