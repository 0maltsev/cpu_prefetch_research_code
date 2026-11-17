"""Cold packet custody and original loader guard regression; no phase action."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_packet_v1 as current
import stage17_service_continuation_packet_v3 as previous


class PacketTests(unittest.TestCase):
    def test_original_byte_identity_and_loaded_code_guards_are_unchanged(self):
        old=ast.parse(Path(previous.__file__).read_bytes())
        new=ast.parse(Path(current.__file__).read_bytes())
        for name in ('read','load_source','check_loaded','verify_archive','strict_json'):
            a=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b),name)

    def test_actual_packet_bytes_reject_changed_and_unlisted_executables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);rows=[]
            for name in (*current.MODULES,'stage17_q16c_packet_v1'):
                raw=(Path(current.__file__).parent/(name+'.py')).read_bytes()
                (root/(name+'.py')).write_bytes(raw)
                rows.append(dict(name=name+'.py',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            manifest=dict(schema_version='cpu-prefetch-stage17-q16c-cold-packet/1',
                administrative_source_revision='f'*40,qualified_source_revision='919c48637cbdba9e466a3104f5cbb39f7184e39b',
                qualified_worker_sha256='1baa213a137679460348ff6b861839044022957a4de0e5fc79929f7b49bed883',
                files=rows,execution_authority=False,phase18_authority=False)
            def publish():
                raw=json.dumps(manifest).encode();(root/'manifest.json').write_bytes(raw)
                return hashlib.sha256(raw).hexdigest()
            digest=publish();document,members=current.verify_packet(root,digest)
            self.assertEqual(len(members),len(rows));self.assertIs(document['execution_authority'],False)
            foreign=root/'unlisted.py';foreign.write_bytes(b'raise RuntimeError("unverified")')
            with self.assertRaisesRegex(ValueError,'unlisted executable'):current.verify_packet(root,digest)
            foreign.unlink();target=root/rows[0]['name'];original=target.read_bytes();target.write_bytes(original+b'\n')
            with self.assertRaisesRegex(ValueError,'regular bound source'):current.verify_packet(root,digest)
            target.write_bytes(original);manifest['qualified_source_revision']='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8'
            with self.assertRaisesRegex(ValueError,'actual new native release'):current.verify_packet(root,publish())


if __name__=='__main__':unittest.main()
