"""Exact cold package + real sealed broker/codec checks; no empirical authority."""
import argparse
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_archive_bundle_profile_v1 as profile
import stage17_s180_archive_broker_v1 as broker
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_archive_bundle_profile_v1 as legacy
import test_stage17_s180_archive_broker_v1 as broker_tests

ROOT=Path(__file__).resolve().parents[1]


class ProfileTests(unittest.TestCase):
    encoder=None

    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='s180-package-',dir=ROOT/'build')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.bundle=self.root/'bundle';self.bundle.mkdir();self.runtime=self.root/'runtime'
        self.runtime.mkdir();self.repo=ROOT
        self.library=Path(os.environ.get('STAGE17_TEST_ZSTD_LIBRARY','/usr/lib64/libzstd.so.1.5.7')).resolve()
        self.put(self.runtime/'usr/lib/libzstd.so.1.5.7',self.library.read_bytes())
        self.put(self.runtime/'usr/share/licenses/zstd/LICENSE',b'SOFTWARE_FIXTURE_LICENSE_NOT_A_DISTRIBUTION')
        self.put(self.runtime/legacy.PYTHON_PATH,Path(sys.executable).read_bytes())
        self.put(self.bundle/legacy.ENCODER_PATH,self.encoder.read_bytes())
        self.document=profile.materialize(repository_root=self.repo,bundle_root=self.bundle,
            runtime_root=self.runtime,window_log=22)

    def put(self,path,raw):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)

    def save(self,document):
        path=self.bundle/profile.PROFILE_PATH;path.chmod(0o644);path.write_bytes(legacy.canonical(document))

    def load(self):
        bound=legacy.binding(self.bundle,profile.PROFILE_PATH)
        return profile.load_profile(bundle_root=self.bundle,runtime_root=self.runtime,
            expected=archive.PhysicalBinding(bound['size_bytes'],bound['sha256']),deadline_ns=time.monotonic_ns()+20*10**9)

    def fixture(self,loaded):
        class PackagedFixture(broker_tests.S180BrokerTests):
            encoder=self.encoder
            def configure_profile(self,previous):return loaded
        fixture=PackagedFixture('test_actual_broker_reconstructs_all_eight_sources_and_preserves_shared_quota')
        self.addCleanup(fixture.doCleanups);fixture.setUp();return fixture

    def test_actual_package_loader_and_sealed_broker_reconstruct_all_originals(self):
        loaded=self.load()
        self.assertIn('stage17_s180_archive_broker_v1',{r.module for r in loaded.source_closure})
        self.assertEqual(loaded.decoder.implementation_profile_sha256,
            legacy.binding(self.bundle,profile.PROFILE_PATH)['sha256'])
        self.fixture(loaded).test_actual_broker_reconstructs_all_eight_sources_and_preserves_shared_quota()

    def test_legacy_profile_reproduces_missing_s180_entry_without_relabeling_it(self):
        loaded=self.load()
        old_names=set(legacy.local_source_closure(ROOT/'tools'))
        old=replace(loaded,source_closure=tuple(r for r in loaded.source_closure if r.module in old_names))
        fixture=self.fixture(loaded)
        with self.assertRaisesRegex(broker.base.BrokerError,'omits broker entrypoint'):
            # Exercise the inherited closure guard without a fabricated live
            # worker. No broker command can execute during this constructor.
            broker.base._Client.__init__(broker.ArchiveBrokerClient.__new__(broker.ArchiveBrokerClient),
                profile=old,limits=fixture.limits)
        self.assertNotIn('stage17_s180_archive_broker_v1',old_names)
        self.assertEqual(legacy.ROOT_MODULES,('stage17_formal_archive_runtime_v1','stage17_formal_archive_broker_v1'))

    def test_actual_runtime_is_explicit_and_relocatable(self):
        self.assertEqual(profile.verify_profile(bundle_root=self.bundle,runtime_root=self.runtime),self.document)
        moved=self.root/'moved-runtime';self.runtime.rename(moved);self.runtime=moved
        self.assertEqual(profile.verify_profile(bundle_root=self.bundle,runtime_root=moved),self.document)
        self.assertNotIn(str(moved),legacy.canonical(self.document).decode())
        (moved/legacy.PYTHON_PATH).write_bytes(b'changed interpreter')
        with self.assertRaises(profile.ProfileError):self.load()

    def test_exact_closure_options_and_profile_transport(self):
        for change in (lambda d:d['source_closure'].pop(),
            lambda d:d['source_closure'].append(d['source_closure'][0]),
            lambda d:d['source_closure'].reverse(),lambda d:d['options'].update(nbWorkers=1),
            lambda d:d['options'].update(window_log=True),lambda d:d['python'].update(path='../python'),
            lambda d:d.update(execution_authority=True)):
            doc=copy.deepcopy(self.document);change(doc);self.save(doc)
            with self.assertRaises(profile.ProfileError):self.load()
        self.save(self.document)
        path=self.bundle/profile.PROFILE_PATH;path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(profile.ProfileError):self.load()

    def test_actual_source_change_and_foreign_expected_hash_reject(self):
        loaded=self.load();self.assertTrue(loaded.source_closure)
        path=self.bundle/'tools/stage17_s180_checkpoint_v1.py';path.chmod(0o644);original=path.read_bytes()
        path.write_bytes(original+b'\n')
        with self.assertRaises(profile.ProfileError):self.load()
        path.write_bytes(original)
        with self.assertRaises(archive.ArchiveError):
            profile.load_profile(bundle_root=self.bundle,runtime_root=self.runtime,
                expected=archive.PhysicalBinding(1,'f'*64),deadline_ns=time.monotonic_ns()+10**9)

    def test_missing_local_dependency_relative_import_and_symlink_reject(self):
        path=self.bundle/'tools/stage17_s180_checkpoint_v1.py';path.chmod(0o644);original=path.read_bytes()
        for suffix in (b'\nimport stage17_missing\n',b'\nfrom . import missing\n'):
            path.write_bytes(original+suffix)
            with self.assertRaises(profile.ProfileError):self.load()
        path.unlink();path.symlink_to(ROOT/'tools/stage17_s180_checkpoint_v1.py')
        with self.assertRaises(profile.ProfileError):self.load()

    def test_no_profile_or_partial_package_adoption(self):
        before=(self.bundle/profile.PROFILE_PATH).read_bytes()
        with self.assertRaisesRegex(profile.ProfileError,'no adoption'):
            profile.materialize(repository_root=ROOT,bundle_root=self.bundle,runtime_root=self.runtime,window_log=22)
        self.assertEqual((self.bundle/profile.PROFILE_PATH).read_bytes(),before)
        destination=self.root/'partial';destination.mkdir()
        self.put(destination/'tools/stage17_s180_archive_broker_v1.py',b'retained partial package')
        with self.assertRaisesRegex(profile.ProfileError,'no overwrite'):
            profile.materialize(repository_root=ROOT,bundle_root=destination,runtime_root=self.runtime,window_log=22)
        self.assertEqual((destination/'tools/stage17_s180_archive_broker_v1.py').read_bytes(),b'retained partial package')

    def test_profile_symlink_destination_and_expired_load_reject_before_actions(self):
        destination=self.root/'linked';destination.mkdir();outside=self.root/'outside';outside.mkdir()
        (destination/'config').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(profile.ProfileError,'symlink'):
            profile.materialize(repository_root=ROOT,bundle_root=destination,runtime_root=self.runtime,window_log=22)
        self.assertEqual(list(outside.iterdir()),[])
        expected=legacy.binding(self.bundle,profile.PROFILE_PATH)
        with self.assertRaisesRegex(profile.ProfileError,'deadline expired'):
            profile.load_profile(bundle_root=self.bundle,runtime_root=self.runtime,
                expected=archive.PhysicalBinding(expected['size_bytes'],expected['sha256']),deadline_ns=1)

    def repository(self):
        root=self.root/'repo';root.mkdir();shutil.copytree(self.bundle/'tools',root/'tools')
        subprocess.run(['git','init','-q',str(root)],check=True)
        subprocess.run(['git','-C',str(root),'add','tools'],check=True)
        subprocess.run(['git','-C',str(root),'-c','user.name=Software Fixture','-c','user.email=fixture@example.invalid',
            'commit','-qm','Disjoint software-only archive fixture'],check=True)
        return root

    def package(self):
        root=self.repository();destination=self.root/'clean-package'
        manifest=profile.create_package(repository_root=root,bundle_root=destination,runtime_root=self.runtime,
            encoder=self.encoder,window_log=22)
        expected=legacy.binding(destination,profile.MANIFEST_PATH)
        return root,destination,manifest,expected

    def test_clean_source_package_exact_inventory_and_no_authority(self):
        root,destination,manifest,expected=self.package()
        self.assertFalse(manifest['execution_authority']);self.assertFalse(manifest['operational_window_started'])
        self.assertFalse(manifest['native_worker_included'])
        self.assertEqual(profile.verify_package(bundle_root=destination,runtime_root=self.runtime,
            expected_manifest=expected),manifest)
        self.put(destination/'tools/unqualified_extra.py',b'extra')
        with self.assertRaisesRegex(profile.ProfileError,'membership'):
            profile.verify_package(bundle_root=destination,runtime_root=self.runtime,expected_manifest=expected)

    def test_dirty_revision_rejects_before_output_creation(self):
        root=self.repository();(root/'untracked').write_text('dirty')
        destination=self.root/'must-not-exist'
        with self.assertRaisesRegex(profile.ProfileError,'clean exact'):
            profile.create_package(repository_root=root,bundle_root=destination,runtime_root=self.runtime,
                encoder=self.encoder,window_log=22)
        self.assertFalse(destination.exists())

    def test_package_manifest_and_extra_same_named_nested_file_reject(self):
        _,destination,manifest,expected=self.package()
        self.put(destination/'tools'/profile.MANIFEST_PATH,b'extra named manifest')
        with self.assertRaisesRegex(profile.ProfileError,'membership'):
            profile.verify_package(bundle_root=destination,runtime_root=self.runtime,expected_manifest=expected)
        with self.assertRaisesRegex(profile.ProfileError,'pinned manifest'):
            profile.verify_package(bundle_root=destination,runtime_root=self.runtime,
                expected_manifest=dict(expected,sha256='f'*64))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--encoder',type=Path,required=True)
    args,remaining=parser.parse_known_args();ProfileTests.encoder=args.encoder.resolve()
    unittest.main(argv=[sys.argv[0],*remaining])
