"""D233 local-only custody interruptions and finite resource gates."""
from __future__ import annotations

import errno
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from dataclasses import replace
from unittest import mock
from types import SimpleNamespace

from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
import stage17_formal_archive_v1 as a
import stage17_formal_archive_custody_v1 as c


class CustodyFixture:
    def __init__(self, directory, *, source_data=b"exact original control\x00\xff", expected=None):
        self.directory = Path(directory)
        self.f = ArchiveFixture(self.directory)
        self.root = self.directory / "future-program"
        self.scope = c.ProgramStore.initialize(self.root, program_id="synthetic-future-program",
            storage_domain_id="synthetic-single-domain", prospective_admission_sha256=digest(b"synthetic authority"))
        self.limits = c.CustodyLimits(65536, 1024, 4096, 65536, time.monotonic_ns()+90_000_000_000)
        self.family = digest(b"synthetic prospective plan")
        with self.store() as store:
            self.working = store.prepare_family(self.family)
        self.data = source_data
        self.header, self.role = self.f.header(source_data, "bytes")
        self.header["artifact_id"] = self.family + ":control.json"
        self.artifact_id = self.header["artifact_id"]
        self.original = self.working / "control.json"
        self.original.write_bytes(source_data)
        expected = source_data if expected is None else expected
        self.source = c.SourceBinding(self.artifact_id,
            c.BoundFile(self.original.name, len(expected), digest(expected)),
            a.PhysicalBinding(len(source_data), digest(source_data)), None)
        document = dict(schema_version=c.CHECKPOINT_SCHEMA, action_id="Q16a",
            plan_sha256=digest(b"synthetic prospective plan"), capture_ordinal=0,
            capture_identity=dict(warmup_run_id="warmup", measurement_run_id="measurement", hardware_state="H0"),
            native_result_after_cleanup={"synthetic": True, "all_workers_joined": True},
            artifacts=[dict(file_name=self.original.name, size_bytes=len(expected), sha256=digest(expected))],
            native_complete=False, scientific_validity="NOT_ASSESSED", execution_authority=False)
        raw = a.canonical(document)
        (self.working / "checkpoint.json").write_bytes(raw)
        self.checkpoint = c.BoundFile("checkpoint.json", len(raw), digest(raw))
        self.callback_calls = 0
        self.wire = self.f.encode(source_data, self.header)
        self.physical = a.PhysicalBinding(len(self.wire), digest(self.wire))

    def callback(self, document, sources):
        # Software fixture only: real callback must additionally inspect actual
        # process/thread quiescence, using the qualified runtime verifier.
        if document["native_result_after_cleanup"] != {"synthetic": True, "all_workers_joined": True}:
            raise c.CustodyError("synthetic cleanup evidence differs")
        self.callback_calls += 1

    def store(self):
        return c.ProgramStore(self.root, scope_sha256=self.scope, family_id=self.family, limits=self.limits)

    def begin(self, store):
        store.prepare_family(self.family)
        store.begin_capture(self.checkpoint, (self.source,), verify_checkpoint=self.callback)

    def reserve(self, store):
        path = store.reserve_archive(self.artifact_id, staging_name="source.staging",
                                     maximum_archive_bytes=len(self.wire)+1024)
        with path.open("xb") as stream:
            stream.write(self.wire)
        return path

    def publish(self, store):
        with codec_limit():
            return store.verify_and_publish(self.artifact_id, archive_name="source.cpfa",
                expected_header=self.header, role=self.role, physical=self.physical,
                profile=self.f.profile, limits=self.f.limits)

    def release(self, store):
        with codec_limit():
            store.release_working_copy(self.artifact_id, profile=self.f.profile, limits=self.f.limits)


class CustodyTests(unittest.TestCase):
    def setUp(self):
        capacity = mock.patch("os.statvfs", return_value=SimpleNamespace(
            f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100_000))
        capacity.start()
        self.addCleanup(capacity.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = CustodyFixture(self.temp.name)

    def test_failed_native_capture_archived_without_scientific_validity_or_retry(self):
        with self.f.store() as store:
            self.f.begin(store)
            self.f.reserve(store)
            self.f.publish(store)
            self.assertEqual(self.f.original.read_bytes(), self.f.data)
            self.f.release(store)
            self.assertFalse(self.f.original.exists())
            self.assertGreaterEqual(self.f.callback_calls, 5)
            with self.assertRaises(c.CustodyError):
                self.f.release(store)
        with self.f.store() as reopened:
            state = reopened._states[self.f.artifact_id]
            self.assertEqual(state["kind"], "RELEASED")
            self.assertEqual(state["payload"]["source"]["expected"]["sha256"], digest(self.f.data))
            self.assertEqual(reopened.reserved_bytes(), 0)
        self.assertTrue((self.f.working / "checkpoint.json").exists())
        self.assertEqual((self.f.root / "archives" / "source.cpfa").read_bytes(), self.f.wire)

    def test_no_adoption_historical_tree_missing_callback_or_false_boolean(self):
        with self.assertRaises(FileExistsError):
            c.ProgramStore.initialize(self.f.root, program_id="historical", storage_domain_id="same",
                                      prospective_admission_sha256=digest(b"new"))
        with self.f.store() as store:
            store.prepare_family(self.f.family)
            for callback in (None, lambda *_: True, lambda *_: False):
                with self.subTest(callback=callback), self.assertRaises(c.CustodyError):
                    store.begin_capture(self.f.checkpoint, (self.f.source,), verify_checkpoint=callback)
            with self.assertRaises(c.CustodyError):
                self.f.release(store)
        self.assertEqual(self.f.original.read_bytes(), self.f.data)

    def test_source_discrepancy_preserves_expected_and_actual_failure_bindings(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = CustodyFixture(tmp, expected=b"original expected bytes")
            with f.store() as store:
                with self.assertRaisesRegex(c.CustodyError, "failure binding"):
                    f.begin(store)
                failure = b'{"synthetic":true,"failure":"source-hash-mismatch"}'
                path = f.root / "metadata" / "failure.json"
                path.write_bytes(failure)
                f.source = replace(f.source, failure_receipt=c.BoundFile(path.name, len(failure), digest(failure)))
                f.begin(store)
                f.reserve(store)
                f.publish(store)
                f.release(store)
                retained = store._states[f.artifact_id]["payload"]["source"]
                self.assertNotEqual(retained["expected"]["sha256"], retained["actual"]["sha256"])
                self.assertEqual(retained["failure_receipt"]["sha256"], digest(failure))

    def test_missing_control_reference_and_changed_source_block_begin(self):
        with self.f.store() as store:
            store.prepare_family(self.f.family)
            with self.assertRaisesRegex(c.CustodyError, "every original source"):
                store.begin_capture(self.f.checkpoint, (), verify_checkpoint=self.f.callback)
            self.f.original.write_bytes(b"wrong")
            with self.assertRaises(a.ArchiveError):
                self.f.begin(store)
        self.assertTrue(self.f.original.exists())

    def test_bad_readback_and_published_tamper_never_release_source(self):
        with self.f.store() as store:
            self.f.begin(store)
            staging = self.f.reserve(store)
            staging.write_bytes(self.f.wire[:-1])
            with self.assertRaises(a.ArchiveError):
                self.f.publish(store)
            self.assertEqual(self.f.original.read_bytes(), self.f.data)
        with tempfile.TemporaryDirectory() as tmp:
            f = CustodyFixture(tmp)
            with f.store() as store:
                f.begin(store)
                f.reserve(store)
                f.publish(store)
                (f.root / "archives" / "source.cpfa").write_bytes(f.wire[:-1])
                with self.assertRaises(a.ArchiveError):
                    f.release(store)
                self.assertEqual(f.original.read_bytes(), f.data)

    def test_source_changed_or_hardlinked_after_publication_cannot_be_deleted(self):
        for hardlink in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                f = CustodyFixture(tmp)
                with f.store() as store:
                    f.begin(store)
                    f.reserve(store)
                    f.publish(store)
                    if hardlink:
                        os.link(f.original, f.working / "unexpected-alias")
                    else:
                        f.original.write_bytes(bytes(len(f.data)))
                    with self.assertRaises(a.ArchiveError):
                        f.release(store)
                    self.assertTrue(f.original.exists())

    def test_before_each_ledger_transition_crash_retains_canonical_representation(self):
        for transition in ("CHECKPOINT", "SOURCE_BOUND", "RESERVED", "VERIFIED", "PUBLISHED", "RELEASE_INTENT", "RELEASED"):
            with self.subTest(transition=transition), tempfile.TemporaryDirectory() as tmp:
                f = CustodyFixture(tmp)
                with f.store() as store:
                    original_append = store.append
                    def fail(kind, *args):
                        if kind == transition:
                            raise OSError(errno.EIO, "synthetic process crash")
                        return original_append(kind, *args)
                    with mock.patch.object(store, "append", side_effect=fail), self.assertRaises(OSError):
                        f.begin(store)
                        f.reserve(store)
                        f.publish(store)
                        f.release(store)
                if transition != "RELEASED":
                    self.assertEqual(f.original.read_bytes(), f.data)
                else:
                    with codec_limit():
                        proof = a.verify_archive(f.root / "archives" / "source.cpfa",
                            expected_header=f.header, role=f.role, physical=f.physical,
                            profile=f.f.profile, limits=f.f.limits)
                    self.assertEqual(proof.canonical.sha256, digest(f.data))

    def test_partial_write_disk_full_and_sync_failure_preserve_sources(self):
        for mode in ("partial", "disk-full", "fsync"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                f = CustodyFixture(tmp)
                with f.store() as store:
                    actual_write = os.write
                    def partial(fd, raw):
                        return actual_write(fd, raw[:max(1, len(raw)//2)])
                    target = "os.fsync" if mode == "fsync" else "os.write"
                    effect = partial if mode == "partial" else OSError(errno.ENOSPC if mode == "disk-full" else errno.EIO, mode)
                    with mock.patch(target, side_effect=effect), self.assertRaises((OSError, c.CustodyError)):
                        f.begin(store)
                self.assertEqual(f.original.read_bytes(), f.data)

    def test_pending_ledger_fail_closed_and_double_broker_forbidden(self):
        with self.f.store() as store:
            with self.assertRaises(BlockingIOError):
                with self.f.store():
                    self.fail("second broker must not enter")
            self.f.begin(store)
            (self.f.root / "ledger" / f"{store._sequence:016d}.pending").write_bytes(b"partial")
        with self.assertRaisesRegex(c.CustodyError, "explicit recovery"):
            with self.f.store():
                self.fail("incomplete ledger adopted")
        self.assertEqual(self.f.original.read_bytes(), self.f.data)

    def test_quiescence_loss_before_publish_or_release_preserves_source(self):
        with self.f.store() as store:
            self.f.begin(store)
            self.f.reserve(store)
            with mock.patch.object(store, "_verify_checkpoint", side_effect=c.CustodyError("worker active")):
                with self.assertRaises(c.CustodyError):
                    self.f.publish(store)
            self.f.publish(store)
            with mock.patch.object(store, "_verify_checkpoint", side_effect=c.CustodyError("worker active")):
                with self.assertRaises(c.CustodyError):
                    self.f.release(store)
            self.assertEqual(self.f.original.read_bytes(), self.f.data)

    def test_deadline_quota_and_actual_reservations(self):
        with self.f.store() as store:
            self.f.begin(store)
            with self.assertRaisesRegex(c.CustodyError, "quota"):
                store.reserve_archive(self.f.artifact_id, staging_name="too-big", maximum_archive_bytes=c.PROGRAM_QUOTA)
            self.assertFalse((self.f.root / "archives" / "too-big").exists())
            self.f.reserve(store)
            st = (self.f.root / "archives" / "source.staging").stat()
            self.assertEqual(store.reserved_bytes(), max(0, len(self.f.wire)+1024-max(st.st_size, st.st_blocks*512)))
            store.limits = replace(store.limits, deadline_ns=time.monotonic_ns()-1)
            with self.assertRaises(c.CustodyError):
                self.f.publish(store)
        self.assertEqual(self.f.original.read_bytes(), self.f.data)

    def test_allocation_pressure_hardlink_dedup_and_write_rounding(self):
        with self.f.store() as store:
            path = self.f.root / "metadata" / "one-byte"
            path.write_bytes(b"x")
            os.link(path, self.f.root / "metadata" / "same-inode")
            actual_stat = Path.stat
            def allocated_stat(p, **kwargs):
                st = actual_stat(p, **kwargs)
                if st.st_ino == actual_stat(path).st_ino:
                    return SimpleNamespace(st_dev=st.st_dev, st_ino=st.st_ino, st_size=1,
                                           st_blocks=128, st_mode=st.st_mode)
                return st
            with mock.patch.object(Path, "stat", allocated_stat):
                usage = store.physical_accounting()
                self.assertGreaterEqual(usage.allocated_bytes, 128*512)
                self.assertGreater(usage.quota_bytes, usage.logical_size_bytes)
                # Recompute unique inode accounting independently; aliases never
                # double-charge a transient staging/publication hardlink.
                paths = [self.f.root, *(self.f.root/name for name in store.DIRECTORIES),
                         self.f.working, self.f.root/"scope.json", self.f.root/"broker.lock", path,
                         path.with_name("same-inode"), *(self.f.root/"ledger").iterdir()]
                inodes = {(p.stat().st_dev,p.stat().st_ino):p.stat() for p in paths}
                self.assertEqual(usage.unique_objects, len(inodes))
                self.assertEqual(usage.quota_bytes, sum(max(s.st_size,s.st_blocks*512) for s in inodes.values()))
            with mock.patch("os.statvfs", return_value=SimpleNamespace(f_bavail=10**12, f_frsize=4096, f_favail=100)), \
                 mock.patch.object(store, "physical_usage", return_value=c.PROGRAM_QUOTA-4095):
                with self.assertRaisesRegex(c.CustodyError, "quota"):
                    store._before_write(1)

    def test_next_capture_rejected_until_every_prior_source_released(self):
        with self.f.store() as store:
            self.f.begin(store)
            for step in (lambda: None, lambda: self.f.reserve(store), lambda: self.f.publish(store)):
                step()
                with self.assertRaisesRegex(c.CustodyError, "previous capture"):
                    self.f.begin(store)
            self.assertEqual(self.f.original.read_bytes(), self.f.data)


    def test_old_ledger_record_binding_is_indexed_and_release_does_not_replay(self):
        with self.f.store() as store:
            self.f.begin(store)
            old=store._record_bindings[0]
            self.assertEqual(store.read_verified_record(old)["kind"],"FAMILY")
            with self.assertRaisesRegex(c.CustodyError,"index"):
                store.read_verified_record(replace(old,sha256="0"*64))
            self.f.reserve(store)
            self.f.publish(store)
            with mock.patch.object(store,"_replay",side_effect=AssertionError("quadratic replay")):
                self.f.release(store)
            path=self.f.root/"ledger"/old.file_name
            raw=path.read_bytes()
            path.write_bytes(raw.replace(b'"FAMILY"',b'"FAMiLY"'))
            with self.assertRaisesRegex(c.CustodyError,"binding"):
                store.read_verified_record(old)


class CapacityAndSpoolTests(unittest.TestCase):
    def setUp(self):
        capacity = mock.patch("os.statvfs", return_value=SimpleNamespace(
            f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100_000))
        capacity.start()
        self.addCleanup(capacity.stop)

    def test_shared_quota_fresh_free_reservations_inodes_and_checked_overflow(self):
        total = c.PROGRAM_QUOTA+c.WORKSPACE+c.SCRATCH+c.RESERVE
        snapshot = c.CapacitySnapshot(total, 100, 0, 0, 0, 0)
        plan = c.SpacePlan(1000, 10, 10, 2000, 100, 1000, 10)
        c.check_capacity(snapshot, plan)
        # Retained bytes already reduced free; no second subtraction of history.
        c.check_capacity(replace(snapshot, retained_bytes=500, free_bytes=total-500), plan)
        for mutant in (replace(snapshot, free_bytes=total-1), replace(snapshot, free_inodes=9),
                       replace(snapshot, unrelated_reserved_bytes=1),
                       replace(snapshot, retained_bytes=c.PROGRAM_QUOTA-1000),
                       replace(snapshot, in_flight_reserved_bytes=c.PROGRAM_QUOTA),
                       replace(snapshot, free_bytes=True), replace(snapshot, retained_bytes=a.MAX_U64)):
            with self.assertRaises(a.ArchiveError):
                c.check_capacity(mutant, plan)
        for mutant in (replace(plan, canonical_capture_bytes=c.WORKSPACE),
                       replace(plan, analysis_spool_bytes=c.SCRATCH+1),
                       replace(plan, archive_staging_bytes=a.MAX_U64)):
            with self.assertRaises(a.ArchiveError):
                c.check_capacity(snapshot, mutant)

    def test_spool_exact_decoding_bound_and_one_capture_per_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = ArchiveFixture(tmp)
            data = b"all original bytes\x00\xff"
            header, role = f.header(data, "bytes")
            wire = f.encode(data, header)
            physical = a.PhysicalBinding(len(wire), digest(wire))
            archive_path = Path(tmp) / "archive.cpfa"
            archive_path.write_bytes(wire)
            spool = Path(tmp) / "spools"
            spool.mkdir()
            artifacts = (c.SpoolArtifact("control.json", archive_path, header, role, physical),)
            args = dict(capture_id="capture0", canonical_bytes_bound=len(data), deadline_ns=f.limits.deadline_ns,
                        artifacts=artifacts, profile=f.profile, limits=f.limits)
            with codec_limit(), c.capture_spool(spool, **args) as decoded:
                self.assertEqual((decoded / "control.json").read_bytes(), data)
                with self.assertRaises(BlockingIOError):
                    with c.capture_spool(spool, **dict(args, capture_id="capture1")):
                        self.fail("concurrent spool")
            self.assertFalse(decoded.exists())
            self.assertEqual(archive_path.read_bytes(), wire)
            with self.assertRaises(c.CustodyError):
                with c.capture_spool(spool, **dict(args, canonical_bytes_bound=len(data)-1)):
                    self.fail("spool must reject before decode")

    def test_failed_spool_retained_and_original_archive_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = ArchiveFixture(tmp)
            header, role = f.header(b"retain", "bytes")
            wire = f.encode(b"retain", header)
            path = Path(tmp)/"source.cpfa"
            path.write_bytes(wire)
            spool = Path(tmp)/"spool"
            spool.mkdir()
            artifact = c.SpoolArtifact("data", path, header, role, a.PhysicalBinding(len(wire), "0"*64))
            with codec_limit(), self.assertRaises(a.ArchiveError):
                with c.capture_spool(spool, capture_id="failed", canonical_bytes_bound=6,
                    deadline_ns=f.limits.deadline_ns, artifacts=(artifact,), profile=f.profile, limits=f.limits):
                    self.fail("bad physical hash admitted")
            self.assertTrue((spool/f"{os.getpid()}-failed"/"data").exists())
            self.assertEqual(path.read_bytes(), wire)


if __name__ == "__main__":
    unittest.main()
