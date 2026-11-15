"""Actual bounded source files; never activates a stand or formal action."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_formal_admin_v2 as admin


class PacketTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.document = dict(schema_version=admin.SCHEMA, source_revision='a' * 40,
            qualified_worker_unchanged=True, execution_authority=False, files=[])
        for name in sorted(admin.REQUIRED):
            raw = b'"""software-only test source"""\n'
            (self.root / name).write_bytes(raw)
            self.document['files'].append(dict(name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))

    def freeze(self, raw=None):
        raw = json.dumps(self.document).encode() if raw is None else raw
        (self.root / 'manifest.json').write_bytes(raw)
        return hashlib.sha256(raw).hexdigest()

    def test_complete_packet_accepted_as_source_only(self):
        self.assertEqual(admin.verify_packet(self.root, self.freeze()), self.document)

    def test_rehashed_manifest_does_not_hide_member_change(self):
        digest = self.freeze()
        (self.root / self.document['files'][0]['name']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, digest)

    def test_missing_closure_duplicate_member_and_path_escape_rejected(self):
        original = list(self.document['files'])
        for rows in (original[:-1], original + [original[0]], [dict(original[0], name='../outside'), *original[1:]]):
            self.document['files'] = rows
            with self.assertRaises(ValueError):
                admin.verify_packet(self.root, self.freeze())

    def test_wrong_manifest_authority_duplicate_json_and_symlink_rejected(self):
        self.freeze()
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, '0' * 64)
        self.document['execution_authority'] = True
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze())
        self.document['execution_authority'] = False
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze(b'{"files":[],"files":[]}'))
        name = self.document['files'][0]['name']
        source = self.root / name
        original = self.root / 'original'
        source.rename(original)
        source.symlink_to(original)
        with self.assertRaises(ValueError):
            admin.verify_packet(self.root, self.freeze())


class VerifiedImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.name = 'software_source_fixture_v2'
        self.addCleanup(lambda: sys.modules.pop(self.name, None))
        self.addCleanup(lambda: admin._LOADED.pop(self.name, None))

    def test_matching_file_path_does_not_authenticate_a_cached_callback(self):
        path = self.root / 'validate_suffix.py'
        path.write_text('def modules(c): return "verified"\n')
        fake = types.ModuleType('validate_suffix')
        fake.__file__ = str(path)
        fake.modules = lambda c: 'unverified'
        with patch.dict(sys.modules, {'validate_suffix': fake}):
            with self.assertRaises(ValueError):
                admin.reject_foreign_cache(self.root)
            with self.assertRaises(ValueError):
                admin.load_verified_source('validate_suffix', path, path.read_bytes())

    def test_compiles_authenticated_bytes_instead_of_reopening_changed_path(self):
        path = self.root / 'source.py'
        verified = b'def value(): return 7\n'
        path.write_text('def value(): return 999\n')
        module = admin.load_verified_source(self.name, path, verified)
        self.assertEqual(module.value(), 7)
        admin.check_verified_modules()
        # Trusted reentry is stable; another module merely claiming its locator
        # is rejected after activation as well as before it.
        with patch.dict(sys.modules, {self.name: types.ModuleType(self.name)}):
            with self.assertRaises(ValueError):
                admin.check_verified_modules()

    def test_post_activation_code_or_import_replacement_rejected(self):
        module = admin.load_verified_source(self.name, self.root / 'source.py',
            b'import json\ndef value(): return 7\n')
        original = module.value.__code__
        module.value.__code__ = (lambda: 999).__code__
        with self.assertRaises(ValueError):
            admin.check_verified_modules()
        module.value.__code__ = original
        module.json = types.ModuleType('json')
        with self.assertRaises(ValueError):
            admin.check_verified_modules()


if __name__ == '__main__':
    unittest.main()
