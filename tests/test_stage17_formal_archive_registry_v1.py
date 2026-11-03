"""Real lossless custody with synthetic native receipts; no scientific credit."""
from dataclasses import asdict
import hashlib
import pathlib
import tempfile
import time
import unittest
from unittest.mock import patch

from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
from test_stage17_formal_checkpoint_v1 import fixture as checkpoint_fixture
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
import stage17_formal_checkpoint_v1 as checkpoint


class ArchiveRegistryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = pathlib.Path(temporary.name)
        self.f = ArchiveFixture(self.base)
        self.root = self.base / "program"
        self.family = "b" * 64
        self.scope = custody.ProgramStore.initialize(self.root, program_id="synthetic-program",
            storage_domain_id="synthetic-domain", prospective_admission_sha256="c" * 64)
        self.limits = custody.CustodyLimits(131072, 1024, 4096, 131072,
                                           time.monotonic_ns() + 60_000_000_000)
        self.store = custody.ProgramStore(self.root, scope_sha256=self.scope,
                                          family_id=self.family, limits=self.limits)
        self.store.__enter__()
        self.addCleanup(self.store.__exit__, None, None, None)
        working = self.store.prepare_family(self.family)
        final, self.capture, _ = checkpoint_fixture()
        self.sources, encoded = [], []
        for name in registry.capture_names("Q16a", 0):
            role = registry.role_profile("Q16a", name)
            data = b'{"synthetic_control":true}' if role.layout == "bytes" else b""
            phase = next((p for p in ("warmup", "measurement") if f"-{p}-" in name), None)
            run_id = self.capture[phase]["run_id"] if phase else None
            worker = next((w for w in ("producer", "consumer") if f"-{w}" in name), None)
            header, _ = self.f.header(data, role.layout)
            width = role.row_bytes(run_id)
            header.update(artifact_id=self.family + ":" + name, artifact_role=role.artifact_role,
                canonical_format=role.canonical_format, phase=phase, run_id=run_id, worker=worker,
                row_bytes=width, row_count=0 if width else None,
                block_size_bytes=8192 * width if width else archive.BYTE_BLOCK)
            (working / name).write_bytes(data)
            source = custody.SourceBinding(header["artifact_id"],
                custody.BoundFile(name, len(data), digest(data)),
                archive.PhysicalBinding(len(data), digest(data)), None)
            self.sources.append(source)
            encoded.append((header, role, self.f.encode(data, header)))
        final["artifacts"] = [asdict(s.expected) for s in self.sources]
        raw = archive.canonical(final)
        self.checkpoint = custody.BoundFile("formal-capture-0-final-checkpoint.json", len(raw), digest(raw))
        (working / self.checkpoint.file_name).write_bytes(raw)

        def verify(document, sources):
            # This fixture checks native receipt semantics; actual process
            # quiescence is covered by the separate real-worker channel tests.
            checkpoint.validate_checkpoint(document, action="Q16a", plan_sha256=self.family,
                                            capture=self.capture, sources=sources)

        self.store.begin_capture(self.checkpoint, tuple(self.sources), verify_checkpoint=verify)
        for source, (header, role, wire) in zip(self.sources, encoded, strict=True):
            stem = hashlib.sha256(source.artifact_id.encode()).hexdigest()
            staging = self.store.reserve_archive(source.artifact_id, staging_name=stem + ".staging",
                                                  maximum_archive_bytes=len(wire) + 4096)
            with staging.open("xb") as stream: stream.write(wire)
            with codec_limit():
                self.store.verify_and_publish(source.artifact_id, archive_name=stem + ".cpfa",
                    expected_header=header, role=role, physical=archive.PhysicalBinding(len(wire), digest(wire)),
                    profile=self.f.profile, limits=self.f.limits)
                self.store.release_working_copy(source.artifact_id, profile=self.f.profile, limits=self.f.limits)
        rows = []
        for source in self.sources:
            record = self.store._states[source.artifact_id]
            rows.append(dict(logical=asdict(source.expected), expected_logical=asdict(source.expected),
                failure_receipt=None, artifact_id=source.artifact_id,
                released_record=asdict(self.store.ledger_binding(record)),
                archive_name=record["payload"]["archive_name"], physical=record["payload"]["physical"]))
        self.document = dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1",
            program_scope_sha256=self.scope, plan_sha256=self.family, capture_ordinal=0,
            checkpoint=asdict(self.checkpoint), ledger_tip=asdict(self.store.ledger_binding()),
            artifacts=rows, status="ARCHIVED_AND_RELEASED", scientific_validity="NOT_ASSESSED",
            execution_authority=False)
        self.receipt = self.store.retain_custody_receipt("formal-capture-0-archive-custody.json",
                                                        archive.canonical(self.document))

    def verify(self, **kwargs):
        with codec_limit():
            return registry.verify_capture(store=self.store, action="Q16a", capture=self.capture,
                checkpoint_binding=asdict(self.checkpoint), receipt_binding=asdict(self.receipt),
                decoder_profile=self.f.profile, decoder_limits=self.f.limits,
                readback=kwargs.get("readback", archive.verify_archive))

    def test_full_logical_physical_bijection_is_read_only_and_not_science(self):
        before = {str(p.relative_to(self.root)): digest(p.read_bytes())
                  for p in self.root.rglob("*") if p.is_file()}
        result = self.verify()
        self.assertEqual(len(result["artifacts"]), 9)
        self.assertEqual(result["scientific_validity"], "NOT_ASSESSED")
        self.assertFalse(result["execution_authority"])
        self.assertTrue(all(not (self.store.working / s.expected.file_name).exists() for s in self.sources))
        after = {str(p.relative_to(self.root)): digest(p.read_bytes())
                 for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_actual_archive_corruption_cannot_use_ledger_hash_as_readback(self):
        path = self.root / "archives" / self.document["artifacts"][0]["archive_name"]
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaises(archive.ArchiveError): self.verify()

    def test_foreign_or_duplicate_logical_artifact_rejected(self):
        self.document["artifacts"][1] = self.document["artifacts"][0]
        raw = archive.canonical(self.document)
        (self.store.working / self.receipt.file_name).write_bytes(raw)
        self.receipt = custody.BoundFile(self.receipt.file_name, len(raw), digest(raw))
        with self.assertRaises(archive.ArchiveError): self.verify()

    def test_unsourced_boolean_decoder_proof_is_rejected(self):
        with self.assertRaises(archive.ArchiveError):
            self.verify(readback=lambda *args, **kwargs: True)

    def metadata(self):
        return registry.verify_capture_metadata(store=self.store, action="Q16a", capture=self.capture,
            checkpoint_binding=asdict(self.checkpoint), receipt_binding=asdict(self.receipt),
            decoder_profile=self.f.profile, decoder_limits=self.f.limits)

    def test_metadata_checks_original_bytes_without_decoder_or_inverse_claim(self):
        with patch.object(archive, "verify_archive", side_effect=AssertionError("must not decode")), \
                patch.object(custody, "checked_readback", side_effect=AssertionError("no proof fabrication")):
            result = self.metadata()
        self.assertFalse(result["inverse_readback_performed"])
        self.assertEqual(len(result["artifacts"]), 9)
        self.assertEqual(result["scientific_validity"], "NOT_ASSESSED")
        path = self.root / "archives" / result["artifacts"][-1]["archive_name"]
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with self.assertRaises(archive.ArchiveError): self.metadata()

    def test_metadata_physical_header_must_match_exact_ledger(self):
        path = self.root / "archives" / self.document["artifacts"][0]["archive_name"]
        raw = path.read_bytes()
        path.write_bytes(b"WRONG123" + raw[8:])
        with self.assertRaisesRegex(archive.ArchiveError, "header prefix"):
            self.metadata()


if __name__ == "__main__":
    unittest.main()
