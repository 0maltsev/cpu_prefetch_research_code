"""Bound source, closed membership, cache/mutation and streaming archive gates."""
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_continuation_packet_v3 as current


class PacketTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=pathlib.Path(t.name)
        self.previous=dict(current._LOADED);current._LOADED.clear()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for name in tuple(current._LOADED):sys.modules.pop(name,None)
        current._LOADED.clear();current._LOADED.update(self.previous)

    def binding(self,path):
        raw=path.read_bytes();return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def manifest(self):
        names=[n+'.py' for n in current.MODULES]+['stage17_service_continuation_packet_v3.py']
        for name in names:(self.root/name).write_bytes(b'"synthetic verified source"\n')
        rows=[dict(name=n,**{k:v for k,v in self.binding(self.root/n).items() if k!='path'}) for n in names]
        d=dict(schema_version='cpu-prefetch-stage17-d260-cold-packet/1',administrative_source_revision='a'*40,
            qualified_source_revision='07a93fb4cfbf423ab4ed29912d3aa3ce4aaebbe8',
            qualified_worker_sha256='5497678d637578843abaf5e9d708cecaebe3b26acd4f5b1da48c8fbf91835cb8',
            files=rows,execution_authority=False,phase18_authority=False)
        p=self.root/'manifest.json';p.write_text(json.dumps(d));return self.binding(p)['sha256']

    def test_complete_actual_bound_members_are_verified_without_imports(self):
        digest=self.manifest();d,members=current.verify_packet(self.root,digest)
        self.assertEqual(len(members),len(current.MODULES)+1)
        self.assertFalse(d['execution_authority'])

    def test_altered_member_or_expanded_executable_directory_rejected(self):
        digest=self.manifest();p=self.root/(current.MODULES[0]+'.py');old=p.read_bytes();p.write_bytes(old+b' ')
        with self.assertRaises(ValueError):current.verify_packet(self.root,digest)
        p.write_bytes(old);(self.root/'foreign.py').write_bytes(b'raise RuntimeError()')
        with self.assertRaisesRegex(ValueError,'unlisted'):current.verify_packet(self.root,digest)

    def test_duplicate_json_cannot_override_a_verified_field(self):
        with self.assertRaises(ValueError):current.strict_json(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):current.strict_json(b'{"a":1.0}')

    def test_unverified_cache_and_later_function_or_constant_replacement_rejected(self):
        name='d260_synthetic_verified_module';source=b'import json\nPIN="expected"\ndef run():return PIN\n'
        module=current.load_source(name,self.root/'module.py',source);current.check_loaded()
        with self.assertRaises(ValueError):current.load_source(name,self.root/'module.py',source)
        module.PIN='changed'
        with self.assertRaisesRegex(ValueError,'constant'):current.check_loaded()
        module.PIN='expected';module.run=lambda:True
        with self.assertRaisesRegex(ValueError,'function'):current.check_loaded()

    def test_later_import_or_module_substitution_rejected(self):
        name='d260_synthetic_import_module';module=current.load_source(name,self.root/'module.py',b'import json\ndef run():return 1\n')
        module.json=object()
        with self.assertRaisesRegex(ValueError,'import'):current.check_loaded()

    def test_archive_larger_than_metadata_ceiling_streams_and_hashes_exactly(self):
        p=self.root/'archive.tar.gz'
        with p.open('wb') as stream:
            for _ in range(33):stream.write(b'x'*1024**2)
        binding=self.binding(p)
        with self.assertRaises(ValueError):current.read(binding)
        current.verify_archive(binding)
        with p.open('r+b') as stream:stream.write(b'y')
        with self.assertRaisesRegex(ValueError,'digest'):current.verify_archive(binding)


if __name__=='__main__':unittest.main()
