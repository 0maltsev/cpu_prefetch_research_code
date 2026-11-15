"""Actual bounded source files; never activates a stand or formal action."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_formal_admin_v1 as admin


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


if __name__ == '__main__':
    unittest.main()
