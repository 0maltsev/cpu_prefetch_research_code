"""Real published-archive inspection after a synthetic stopped owner."""
from dataclasses import asdict
import copy
import hashlib
import pathlib
import tempfile
import time
import unittest

from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
from test_stage17_formal_checkpoint_v1 import fixture
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_registry_v1 as registry
import stage17_formal_checkpoint_v1 as checkpoint
import stage17_retained_capture_inspection_v1 as inspection


class RetainedInspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = pathlib.Path(temporary.name)
        self.f = ArchiveFixture(self.base)
        self.root = self.base/'program'
        self.family = 'b'*64
        self.scope = custody.ProgramStore.initialize(self.root, program_id='synthetic',
            storage_domain_id='synthetic-domain', prospective_admission_sha256='c'*64)
        self.limits = custody.CustodyLimits(131072, 1024, 4096, 131072,
                                           time.monotonic_ns()+60_000_000_000)
        self.store = self.open_store()
        self.store.__enter__()
        self.addCleanup(lambda: self.store.__exit__(None, None, None))
        working = self.store.prepare_family(self.family)
        final, self.capture, _ = fixture()
        final['action_id'] = 'Q16b'
        self.sources, encoded = [], []
        for name in registry.capture_names('Q16b', 0):
            role = registry.role_profile('Q16b', name)
            data = b'{"synthetic_control":true}' if role.layout == 'bytes' else b''
            phase = next((p for p in ('warmup', 'measurement') if f'-{p}-' in name), None)
            run_id = self.capture[phase]['run_id'] if phase else None
            worker = next((w for w in ('producer', 'consumer') if f'-{w}' in name), None)
            header, _ = self.f.header(data, role.layout)
            width = role.row_bytes(run_id)
            header.update(artifact_id=self.family+':'+name, artifact_role=role.artifact_role,
                canonical_format=role.canonical_format, phase=phase, run_id=run_id, worker=worker,
                row_bytes=width, row_count=0 if width else None,
                block_size_bytes=8192*width if width else archive.BYTE_BLOCK)
            (working/name).write_bytes(data)
            self.sources.append(custody.SourceBinding(header['artifact_id'],
                custody.BoundFile(name, len(data), digest(data)),
                archive.PhysicalBinding(len(data), digest(data)), None))
            encoded.append((header, role, self.f.encode(data, header)))
        final['artifacts'] = [asdict(s.expected) for s in self.sources]
        raw = archive.canonical(final)
        self.checkpoint = custody.BoundFile('formal-capture-0-final-checkpoint.json', len(raw), digest(raw))
        (working/self.checkpoint.file_name).write_bytes(raw)
        def verify(document, sources):
            checkpoint.validate_checkpoint(document, action='Q16b', plan_sha256=self.family,
                                            capture=self.capture, sources=sources)
        self.store.begin_capture(self.checkpoint, tuple(self.sources), verify_checkpoint=verify)
        for index, (source, (header, role, wire)) in enumerate(zip(self.sources, encoded, strict=True)):
            stem = hashlib.sha256(source.artifact_id.encode()).hexdigest()
            staging = self.store.reserve_archive(source.artifact_id, staging_name=stem+'.staging',
                                                  maximum_archive_bytes=len(wire)+4096)
            staging.write_bytes(wire)
            with codec_limit():
                self.store.verify_and_publish(source.artifact_id, archive_name=stem+'.cpfa',
                    expected_header=header, role=role, physical=archive.PhysicalBinding(len(wire), digest(wire)),
                    profile=self.f.profile, limits=self.f.limits)
                if index != len(self.sources)-1:
                    self.store.release_working_copy(source.artifact_id, profile=self.f.profile, limits=self.f.limits)
        self.store.__exit__(None, None, None)
        self.store = self.open_store()
        self.store.__enter__()  # lost in-memory live-worker context, real replay

    def open_store(self):
        return custody.ProgramStore(self.root, scope_sha256=self.scope,
            family_id=self.family, limits=self.limits)

    def inspect(self, **changes):
        values = dict(store=self.store, action='Q16b', capture=self.capture,
            checkpoint_binding=asdict(self.checkpoint), decoder_profile=self.f.profile,
            decoder_limits=self.f.limits)
        values.update(changes)
        return inspection.inspect_capture(**values)

    def snapshot(self):
        return {str(p.relative_to(self.root)): digest(p.read_bytes())
                for p in self.root.rglob('*') if p.is_file()}

    def test_reopened_published_control_inspected_without_science_or_writes(self):
        before = self.snapshot()
        result = self.inspect()
        self.assertEqual([r['current_state'] for r in result['artifacts']], ['RELEASED']*5+['PUBLISHED'])
        self.assertEqual(len(result['artifacts']), 6)
        for field in ('custody_complete', 'family_completion_established', 'inverse_readback_performed',
                      'execution_authority', 'phase18_authority'):
            self.assertIs(result[field], False)
        self.assertEqual(result['scientific_validity'], 'NOT_ASSESSED')
        self.assertEqual(before, self.snapshot())
        with self.assertRaises(custody.CustodyError):
            self.store.prepare_family(self.family)  # inspection cannot clear pending
        self.assertIsNone(self.store._checkpoint)

    def test_corrupted_archive_cannot_use_ledger_as_readback(self):
        row = self.store._states[self.sources[-1].artifact_id]
        path = self.root/'archives'/row['payload']['archive_name']
        raw = path.read_bytes()
        path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        with self.assertRaises(archive.ArchiveError):
            self.inspect()
        self.assertTrue((self.store.working/self.sources[-1].expected.file_name).exists())

    def test_wrong_original_capture_or_checkpoint_rejected(self):
        for change in (dict(capture=dict(self.capture, ordinal=1)),
                       dict(capture=dict(self.capture, hardware_state='H1')),
                       dict(checkpoint_binding=dict(asdict(self.checkpoint), sha256='f'*64))):
            with self.subTest(change=change), self.assertRaises(archive.ArchiveError):
                self.inspect(**change)

    def test_changed_checkpoint_and_missing_retained_copy_rejected(self):
        path = self.store.working/self.checkpoint.file_name
        raw = path.read_bytes()
        path.write_bytes(raw+b' ')
        with self.assertRaises(archive.ArchiveError):
            self.inspect()
        path.write_bytes(raw)
        (self.root/'metadata'/('checkpoint-'+self.checkpoint.sha256+'.json')).unlink()
        with self.assertRaises(FileNotFoundError):
            self.inspect()

    def test_unpublished_state_or_unsourced_record_rejected(self):
        artifact = self.sources[-1].artifact_id
        original = self.store._states[artifact]
        for kind in ('RESERVED', 'VERIFIED', 'RELEASE_INTENT'):
            self.store._states[artifact] = dict(original, kind=kind)
            with self.subTest(kind=kind), self.assertRaises(archive.ArchiveError):
                self.inspect()
        mutant = copy.deepcopy(original)
        mutant['payload']['source']['actual']['sha256'] = 'f'*64
        self.store._states[artifact] = mutant
        with self.assertRaises(archive.ArchiveError):
            self.inspect()

    def test_missing_pending_or_changed_family_identity_rejected(self):
        self.store._capture_pending.clear()
        with self.assertRaises(archive.ArchiveError):
            self.inspect()
        self.store._capture_pending.add((self.family, self.checkpoint.sha256))
        self.store._families[self.family]['inode'] += 1
        with self.assertRaises(archive.ArchiveError):
            self.inspect()


if __name__ == '__main__':
    unittest.main()
