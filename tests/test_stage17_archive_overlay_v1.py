"""Synthetic cold overlay admission and real sealed two-readback integration."""
import argparse
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'), str(Path(__file__).resolve().parent)]
import stage17_archive_overlay_v1 as overlay
import stage17_archive_bundle_profile_v1 as bundle
import stage17_formal_archive_runtime_v1 as runtime
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
from test_stage17_formal_archive_v1 import ArchiveFixture, codec_limit, digest
from test_stage17_formal_archive_custody_v1 import CustodyFixture

TOOLS = Path(__file__).resolve().parents[1] / 'tools'


class OverlayTests(unittest.TestCase):
    encoder = None
    library = None

    def setUp(self):
        if self.encoder is None or self.library is None:
            self.skipTest('explicit native --encoder and --library required')
        self.temp = tempfile.TemporaryDirectory(prefix='d252-overlay-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.baseline = self.root / 'synthetic-baseline'
        self.baseline.mkdir()
        for name in bundle.local_source_closure(TOOLS):
            target = self.baseline / 'tools' / (name + '.py')
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(TOOLS / target.name, target)
        self.fixture = ArchiveFixture(self.root)
        for source, member in ((self.encoder, bundle.ENCODER_PATH),
                               (self.fixture.profile.zstd_library_path, bundle.ZSTD_PATH)):
            target = self.baseline / member
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(source.stat().st_mode & 0o777)
        baseline_profile = bundle.build_profile(bundle_root=self.baseline, runtime_root=Path('/'), window_log=22)
        p = self.baseline / bundle.PROFILE_PATH
        p.parent.mkdir(parents=True)
        p.write_bytes(overlay.canonical(baseline_profile))
        self.packet = self.root / 'packet'
        self.packet.mkdir()
        self.wrapper = self.packet / (overlay.NATIVE_MODULE + '.py')
        shutil.copyfile(TOOLS / self.wrapper.name, self.wrapper)
        shutil.copyfile(TOOLS / (overlay.CANONICAL_MODULE + '.py'), self.packet / (overlay.CANONICAL_MODULE + '.py'))
        shutil.copyfile(TOOLS / (overlay.METADATA_MODULE + '.py'), self.packet / (overlay.METADATA_MODULE + '.py'))
        self.destination = self.root / 'new-overlay'
        self.document = overlay.build_overlay(baseline_bundle_root=self.baseline, runtime_root=Path('/'),
            destination=self.destination, native_library=self.library, wrapper=self.wrapper, source_revision='a' * 40)
        self.old_config = overlay._CONFIG
        overlay._CONFIG = None
        self.addCleanup(setattr, overlay, '_CONFIG', self.old_config)
        self.configure()
        self.validation = SimpleNamespace(resolutions={'S17-EXT-006': SimpleNamespace(semantic_context={
            'archive_bundle_root': str(self.baseline), 'archive_runtime_root': '/',
            'archive_profile_binding': {**self.document['baseline_profile'], 'path': bundle.PROFILE_PATH}})})
        self.request = {'action_id': 'Q16b', 'action_inputs': {'plan': {'storage': {
            'implementation_profile_sha256': self.document['overlay_profile']['sha256']}}}}
        self.original = self.load(self.document['baseline_profile'], self.baseline)

    def configure(self):
        return overlay.configure_verified_descriptor(overlay.canonical(self.document), self.packet)

    def load(self, binding, root):
        return runtime.load_runtime_profile(Path(binding['path']),
            expected=archive.PhysicalBinding(binding['size_bytes'], binding['sha256']), bundle_root=root,
            runtime_root=Path('/'), max_profile_bytes=131072, deadline_ns=time.monotonic_ns() + 60_000_000_000)

    def admit(self):
        with patch.object(overlay.qualified, 'qualified_archive_profile', return_value=self.original) as old:
            value = overlay.qualified_profile(self.request, self.validation, deadline_ns=time.monotonic_ns() + 60_000_000_000)
            self.assertEqual(old.call_args.args[0]['action_inputs']['plan']['storage']['implementation_profile_sha256'],
                             self.document['baseline_profile']['sha256'])
        return value

    def refreeze_candidate(self):
        profile = bundle.build_profile(bundle_root=self.destination, runtime_root=Path('/'), window_log=22)
        p = self.destination / bundle.PROFILE_PATH
        p.write_bytes(overlay.canonical(profile))
        self.document['overlay_profile'] = overlay.binding(p)
        overlay._CONFIG = None
        self.configure()
        self.request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = self.document['overlay_profile']['sha256']

    def test_only_exact_overlay_admitted_and_original_sources_untouched(self):
        before = (self.baseline / 'tools/stage17_formal_archive_v1.py').read_bytes()
        actual = self.admit()
        self.assertEqual(actual.encoder.sha256, self.original.encoder.sha256)
        self.assertEqual(len(actual.source_closure), len(self.original.source_closure) + 4)
        self.assertEqual((self.baseline / 'tools/stage17_formal_archive_v1.py').read_bytes(), before)
        self.assertEqual((self.destination / 'tools/stage17_formal_archive_v1.py').read_bytes(), before + overlay.PATCH)

    def test_unconfigured_wrong_signed_profile_and_changed_context_rejected(self):
        original_request = copy.deepcopy(self.request)
        self.request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'signed plan'):
            self.admit()
        self.request = original_request
        self.validation.resolutions['S17-EXT-006'].semantic_context['archive_runtime_root'] = str(self.root)
        with self.assertRaisesRegex(ValueError, 'EXT006'):
            self.admit()
        overlay._CONFIG = None
        with self.assertRaisesRegex(ValueError, 'not configured'):
            self.admit()

    def test_descriptor_reentry_mutation_and_invalid_fields(self):
        self.configure()
        self.document['source_revision'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.configure()
        overlay._CONFIG[2]['source_revision'] = 'c' * 40
        with self.assertRaisesRegex(ValueError, 'mutated'):
            self.admit()
        overlay._CONFIG = None
        self.document['execution_authority'] = True
        with self.assertRaisesRegex(ValueError, 'cold-only'):
            self.configure()

    def test_rehashed_source_changes_and_extra_dependencies_rejected(self):
        target = self.destination / 'tools/stage17_formal_archive_custody_v1.py'
        target.write_bytes(target.read_bytes() + b'\n# unauthorized body delta\n')
        self.refreeze_candidate()
        with self.assertRaisesRegex(ValueError, 'historical verifier body'):
            self.admit()

    def test_native_image_grammar_and_hash_reject_extra_code(self):
        raw = self.library.read_bytes()
        source = overlay.image_source(raw)
        self.assertEqual(overlay.image_from_source(source), raw)
        for candidate in (source + b'raise RuntimeError("injection")\n', source.replace(b'IMAGE_SHA256', b'OTHER_SHA256', 1),
                          source.replace(str(len(raw)).encode(), str(len(raw) + 1).encode(), 1)):
            with self.assertRaises(ValueError):
                overlay.image_from_source(candidate)

    def test_real_sealed_native_inverse_both_custody_readbacks(self):
        profile = self.admit()
        synthetic = self.root / 'custody-fixture'
        synthetic.mkdir()
        data = b''.join(((i * 0xfedcba9876543211) % (1 << 64)).to_bytes(8, 'little') for i in range(8193))
        capacity = SimpleNamespace(f_bavail=7_000_000_000_000, f_frsize=1, f_favail=100000)
        with patch('os.statvfs', return_value=capacity):
            f = CustodyFixture(synthetic, source_data=data)
            f.f.profile = profile.decoder
            f.header, f.role = f.f.header(data)
            f.header['artifact_id'] = f.artifact_id
            # Exact source/checkpoint file identity is independent of this
            # synthetic role. Both actual decoder children see the new profile.
            limits = runtime.RuntimeLimits(2 * 1024**3, 2 * 1024**3, 131072, 131072, 131072,
                2_000_000_000, time.monotonic_ns() + 60_000_000_000, time.monotonic_ns() + 60_000_000_000, 3)
            enc = dict(window_log=22, maximum_header_bytes=16384, maximum_decoded_block_bytes=8 * 1024**2,
                maximum_encoded_block_bytes=8 * 1024**2, maximum_archive_bytes=64 * 1024**2,
                maximum_observed_context_bytes=64 * 1024**2, io_chunk_bytes=1024**2,
                maximum_io_calls=100000, deadline_monotonic_ns=limits.final_deadline_ns)
            job = runtime.ArchiveJob(f.artifact_id, f.header, f.role, enc, f.f.limits)
            with codec_limit(), f.store() as store:
                store.prepare_family(f.family)
                engine = runtime.ColdArchiveRuntime(store, profile=profile, limits=limits)
                outcome = engine.archive_capture(f.checkpoint, (f.source,), (job,), verify_checkpoint=f.callback)
                self.assertEqual(outcome.status, 'ARCHIVED_AND_RELEASED')
                self.assertEqual(engine.child_count, 3)  # encode + both actual readbacks
                self.assertFalse(f.original.exists())
                receipt = json.loads((f.working / outcome.receipt.file_name).read_bytes())
                self.assertEqual(receipt['artifacts'][0]['logical']['sha256'], digest(data))
                self.assertEqual(receipt['scientific_validity'], 'NOT_ASSESSED')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--encoder', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    OverlayTests.encoder = args.encoder.resolve()
    OverlayTests.library = args.library.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
