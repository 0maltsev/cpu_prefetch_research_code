"""Actual byte bindings and exact closure; synthetic images grant no qualification."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_archive_bundle_profile_v1 as profile


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'; self.runtime = self.root / 'runtime'
        for root, name, data in (
            (self.bundle, profile.ENCODER_PATH, b'encoder-bytes'),
            (self.bundle, profile.ZSTD_PATH, b'zstd-bytes'),
            (self.runtime, profile.PYTHON_PATH, b'python-bytes'),
            (self.bundle, 'tools/stage17_formal_archive_runtime_v1.py', b'import stage17_shared\n'),
            (self.bundle, 'tools/stage17_formal_archive_broker_v1.py', b'from stage17_jobs import run\n'),
            (self.bundle, 'tools/stage17_jobs.py', b'import stage17_shared\n'),
            (self.bundle, 'tools/stage17_shared.py', b'VALUE = 1\n')):
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        self.doc = profile.build_profile(bundle_root=self.bundle, runtime_root=self.runtime, window_log=22)
        self.save()

    def save(self):
        path = self.bundle / profile.PROFILE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(profile.canonical(self.doc))

    def test_exact_bytes_and_explicit_relocated_runtime(self):
        self.assertEqual(profile.verify_profile(bundle_root=self.bundle), self.doc)
        context = profile.qualified_context(bundle_root=self.bundle, runtime_root=self.runtime)
        self.assertEqual(set(context), {'archive_profile_binding','archive_bundle_root','archive_runtime_root'})
        self.assertEqual(context['archive_runtime_root'], str(self.runtime))
        self.assertEqual(context['archive_profile_binding'], profile.binding(self.bundle, profile.PROFILE_PATH))
        self.assertNotIn(str(self.runtime), profile.canonical(self.doc).decode())
        moved = self.root / 'stand-runtime'; self.runtime.rename(moved)
        self.assertEqual(profile.qualified_context(bundle_root=self.bundle, runtime_root=moved)['archive_runtime_root'], str(moved))

    def test_materializer_copies_actual_zstd_license_and_runtime_binding(self):
        import create_stand_bundle as creator
        import stage17_formal_archive_runtime_v1 as runtime
        import stage17_formal_archive_v1 as archive
        import time
        accepted = Path('/usr/lib/libzstd.so.1.5.7')
        if not accepted.is_file():
            self.fail('accepted zstd runtime required for package integration test')
        for source, relative in ((accepted, 'usr/lib/libzstd.so.1.5.7'),
                                 (Path('/usr/share/licenses/zstd/LICENSE'), 'usr/share/licenses/zstd/LICENSE')):
            target = self.runtime / relative; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        # Real repository module graph, synthetic nonexecuted encoder/Python images.
        root = Path(__file__).resolve().parents[1]
        for name in profile.ROOT_MODULES:
            (self.bundle / "tools" / (name + ".py")).unlink()
        manifest = creator.materialize_archive_profile(root=root, staging=self.bundle,
            runtime_root=self.runtime, window_log=22)
        document = profile.verify_profile(bundle_root=self.bundle, runtime_root=self.runtime)
        self.assertEqual(manifest, profile.manifest_binding(bundle_root=self.bundle))
        self.assertEqual((self.bundle / profile.ZSTD_PATH).read_bytes(), accepted.read_bytes())
        names = {item['module'] for item in document['source_closure']}
        self.assertIn('stage17_formal_archive_jobs_v1', names)
        binding = manifest['profile']
        loaded = runtime.load_runtime_profile(self.bundle / profile.PROFILE_PATH,
            expected=archive.PhysicalBinding(binding['size_bytes'], binding['sha256']),
            bundle_root=self.bundle, runtime_root=self.runtime,
            max_profile_bytes=16*1024*1024, deadline_ns=time.monotonic_ns()+10_000_000_000)
        self.assertEqual(loaded.decoder.implementation_profile_sha256, binding['sha256'])

    def test_actual_runtime_not_path_inferred(self):
        (self.runtime / profile.PYTHON_PATH).write_bytes(b'changed')
        profile.verify_profile(bundle_root=self.bundle)  # package-only check cannot qualify runtime
        with self.assertRaisesRegex(profile.ProfileError, 'bytes differ'):
            profile.qualified_context(bundle_root=self.bundle, runtime_root=self.runtime)
        with self.assertRaises(profile.ProfileError):
            profile.build_profile(bundle_root=self.bundle, runtime_root=Path('relative'), window_log=22)

    def test_both_roots_include_jobs_and_exact_membership(self):
        names = [v['module'] for v in self.doc['source_closure']]
        self.assertIn('stage17_jobs', names)
        self.assertIn('stage17_shared', names)
        original = copy.deepcopy(self.doc)
        for mutate in (lambda d: d['source_closure'].pop(),
                       lambda d: d['source_closure'].append(d['source_closure'][0]),
                       lambda d: d['source_closure'].reverse()):
            self.doc = copy.deepcopy(original); mutate(self.doc); self.save()
            with self.assertRaisesRegex(profile.ProfileError, 'membership'):
                profile.verify_profile(bundle_root=self.bundle)

    def test_mutated_source_missing_dependency_and_symbolic_member_reject(self):
        (self.bundle / 'tools/stage17_jobs.py').write_text('import stage17_missing\n')
        with self.assertRaisesRegex(profile.ProfileError, 'missing local dependency'):
            profile.verify_profile(bundle_root=self.bundle)
        path = self.bundle / profile.ENCODER_PATH; path.unlink(); path.symlink_to(self.runtime / profile.PYTHON_PATH)
        with self.assertRaisesRegex(profile.ProfileError, 'symlink'):
            profile.verify_profile(bundle_root=self.bundle)

    def test_options_paths_shapes_and_noncanonical_transport_reject(self):
        original = copy.deepcopy(self.doc)
        for mutate in (lambda d: d['options'].update(nbWorkers=1),
                       lambda d: d['options'].update(window_log=True),
                       lambda d: d['python'].update(path='../usr/bin/python3.14'),
                       lambda d: d['encoder'].update(size_bytes=True),
                       lambda d: d.update(implementation_profile_sha256='0'*64)):
            self.doc = copy.deepcopy(original); mutate(self.doc); self.save()
            with self.assertRaises(profile.ProfileError): profile.verify_profile(bundle_root=self.bundle)
        self.doc = original; self.save()
        path = self.bundle / profile.PROFILE_PATH; path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaisesRegex(profile.ProfileError, 'canonical'):
            profile.verify_profile(bundle_root=self.bundle)


if __name__ == '__main__': unittest.main()
