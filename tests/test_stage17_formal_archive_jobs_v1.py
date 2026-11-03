"""Real files and encoder/decoder processes; synthetic native facts only."""
import argparse
from dataclasses import asdict, replace
import pathlib
import struct
import sys
import tempfile
import time
import unittest

from test_stage17_formal_checkpoint_v1 import fixture
from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
import test_stage17_formal_archive_runtime_v1 as runtime_fixture
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_jobs_v1 as jobs
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_checkpoint_v1 as checkpoint


class CaptureJobTests(unittest.TestCase):
    encoder = None

    def setUp(self):
        if self.encoder is None:
            self.skipTest("requires --encoder actual compiled binary")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = pathlib.Path(temp.name)
        self.f = ArchiveFixture(self.base)
        image = runtime_fixture.image
        self.profile = runtime.RuntimeProfile(image(self.encoder), image(sys.executable),
            replace(self.f.profile, encoder_sha256=image(self.encoder).sha256),
            tuple(runtime.ModuleBinding(name, image(runtime_fixture.TOOLS / (name + ".py")))
                  for name in runtime_fixture.MODULES))
        root = self.base / "program"
        scope = custody.ProgramStore.initialize(root, program_id="software-jobs", storage_domain_id="software-disk",
                                                 prospective_admission_sha256="a" * 64)
        self.deadline = time.monotonic_ns() + 60_000_000_000
        self.store = custody.ProgramStore(root, scope_sha256=scope, family_id="b" * 64,
            limits=custody.CustodyLimits(131072, 2048, 4096, 131072, self.deadline))
        self.store.__enter__()
        self.addCleanup(self.store.__exit__, None, None, None)
        self.working = self.store.prepare_family("b" * 64)
        self.document, self.capture, _ = fixture()
        self.originals = {}
        for name in jobs.capture_names("Q16a", 0):
            role = jobs.role_profile("Q16a", name)
            phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
            width = role.row_bytes(self.capture[phase]["run_id"] if phase else None)
            if width is None:
                data = b'{"synthetic_control":true}'
            else:
                run = self.capture[phase]["run_id"].encode()
                prefix = struct.pack("<I", len(run)) + run
                prefix += bytes(-len(prefix) % 8)
                data = (prefix + bytes(i % 251 for i in range(width - len(prefix)))) * 3
            (self.working / name).write_bytes(data)
            self.originals[name] = data
        self.document["artifacts"] = [dict(file_name=name, size_bytes=len(data), sha256=digest(data))
                                      for name, data in self.originals.items()]
        self.storage = dict(program_id="software-jobs", program_scope_sha256=scope,
            implementation_profile_sha256=self.profile.decoder.implementation_profile_sha256,
            archive_staging_bytes=8 * 1024**2)
        self.observations = 0

    def observe(self):
        # The separate real native-channel tests establish process observation.
        self.observations += 1

    def build(self, **changes):
        arguments = dict(store=self.store, action="Q16a", capture=self.capture, document=self.document,
            profile=self.profile, storage=self.storage, maximum_capture_bytes=1024**2,
            deadline_ns=self.deadline, verify_quiescence=self.observe)
        arguments.update(changes)
        return jobs.build_capture_jobs(**arguments)

    def archive(self, sources, tasks):
        raw = archive.canonical(self.document)
        binding = custody.BoundFile("formal-capture-0-final-checkpoint.json", len(raw), digest(raw))
        (self.working / binding.file_name).write_bytes(raw)
        def verify(document, actual_sources):
            checkpoint.validate_checkpoint(document, action="Q16a", plan_sha256=self.store.family_id,
                capture=self.capture, sources=actual_sources)
        limits = runtime.RuntimeLimits(2 * 1024**3, 2 * 1024**3, 131072, 131072, 131072,
                                       2_000_000_000, self.deadline, self.deadline, 27)
        with codec_limit():
            worker = runtime.ColdArchiveRuntime(self.store, profile=self.profile, limits=limits)
            return worker.archive_capture(binding, sources, tasks, verify_checkpoint=verify)

    def test_full_original_order_actual_native_codec_and_byte_reconstruction(self):
        sources, tasks = self.build()
        self.assertEqual([s.expected.file_name for s in sources], list(self.originals))
        outcome = self.archive(sources, tasks)
        self.assertEqual(outcome.status, "ARCHIVED_AND_RELEASED")
        self.assertGreaterEqual(self.observations, 10)
        self.assertTrue(all(not (self.working / name).exists() for name in self.originals))

    def test_observed_partial_row_is_retained_as_failed_byte_archive(self):
        name = next(iter(self.originals))
        observed = self.originals[name] + b"\xff"
        (self.working / name).write_bytes(observed)
        sources, tasks = self.build()
        self.assertEqual(tasks[0].header["codec_id"], archive.BYTE_CODEC)
        self.assertEqual(tasks[0].header["fallback_reason"], "INCOMPLETE_CANONICAL_ROW")
        self.assertEqual(sources[0].actual.sha256, digest(observed))
        self.assertIsNotNone(sources[0].failure_receipt)
        outcome = self.archive(sources, tasks)
        self.assertEqual(outcome.status, "ARCHIVED_FAILED_EVIDENCE")

    def test_failed_native_prefix_leaves_unlisted_partial_file_untouched(self):
        self.document["native_complete"] = False
        self.document["native_result_after_cleanup"].update(stop=12, publication_succeeded=False)
        self.document["artifacts"] = self.document["artifacts"][:3]
        sources, tasks = self.build()
        self.assertEqual(len(sources), 3)
        self.assertEqual(len(tasks), 3)
        self.assertTrue(all(t.header["codec_id"] == archive.BYTE_CODEC for t in tasks))
        self.assertTrue(all((self.working / name).read_bytes() == data for name, data in self.originals.items()))

    def test_aligned_corruption_is_preserved_without_claiming_valid_row_geometry(self):
        name = next(iter(self.originals))
        malformed = bytes(len(self.originals[name]))
        (self.working / name).write_bytes(malformed)
        sources, tasks = self.build()
        self.assertEqual(tasks[0].header["codec_id"], archive.BYTE_CODEC)
        self.assertEqual(tasks[0].header["fallback_reason"], "SOURCE_BINDING_DISCREPANCY")
        self.assertEqual(sources[0].actual.sha256, digest(malformed))
        self.assertEqual(self.archive(sources, tasks).status, "ARCHIVED_FAILED_EVIDENCE")

    def test_capacity_deadline_scope_and_order_reject_before_release(self):
        with self.assertRaises(archive.ArchiveError): self.build(maximum_capture_bytes=1)
        with self.assertRaises(archive.ArchiveError): self.build(deadline_ns=1)
        wrong = dict(self.storage, implementation_profile_sha256="0" * 64)
        with self.assertRaises(archive.ArchiveError): self.build(storage=wrong)
        self.document["artifacts"].reverse()
        with self.assertRaises(archive.ArchiveError): self.build()
        self.assertTrue(all((self.working / name).exists() for name in self.originals))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--encoder", type=pathlib.Path)
    args, remaining = parser.parse_known_args()
    CaptureJobTests.encoder = args.encoder
    unittest.main(argv=[sys.argv[0], *remaining])
