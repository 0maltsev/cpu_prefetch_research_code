"""Exact software compatibility; synthetic ancestry is not journal admission."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_calibration_compatibility_v1 as compatibility


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.root=Path(self.directory.name).resolve()
        self.old=self.root/'old';self.source=self.root/'source';self.build=self.root/'build'
        for root in (self.old,self.source,self.build):root.mkdir()
        self.rows=[]
        def put(root,name,raw,inventory=False):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            row=dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            if inventory:self.rows.append(row)
            return row
        self.put=put
        changed=[]
        for name,before,after in [('include/unchanged.hpp',b'original',b'original'),
                ('src/cold.cpp',b'old cold',b'new cold'),('src/pilot.cpp',None,b'pilot')]:
            before_row=None if before is None else put(self.old,name,before,True)
            after_row=put(self.source,name,after)
            if before!=after:changed.append(dict(path=name,original_sha256=None if before_row is None else before_row['sha256'],
                current_sha256=after_row['sha256']))
        self.rules_name='tools/check_formal_codegen.py'
        for root in (self.old,self.source):put(root,self.rules_name,b'original rule',root==self.old)
        old_worker=put(self.old,'release/bin/cpu_prefetch_runner',b'old worker',True)
        worker=put(self.build,'cpu_prefetch_runner',b'new worker')
        put(self.old,'build-provenance/formal_codegen_report.json',b'{"old":true}',True)
        self.report=self.root/'codegen.json';self.report.write_text('{"current":true}')
        libraries=[]
        for name in ('queue','calibration'):
            before=put(self.old,'release/lib/libcpu_prefetch_'+name+'.a',name.encode(),True)
            after=put(self.build,'libcpu_prefetch_'+name+'.a',name.encode()+(b' pilot' if name=='calibration' else b''))
            libraries.append(dict(library=name,original=before,current=after,identical=name!='calibration'))
        inv=put(self.old,'BUNDLE_INVENTORY.json',compatibility.archive.canonical(dict(
            source_revision='a'*40,files=self.rows)))
        self.rules=dict(schema_version=compatibility.REVIEW_SCHEMA,original_source_revision='a'*40,
            current_source_revision='b'*40,original_inventory=inv,original_worker=old_worker,
            current_worker=worker,libraries=libraries,changed_native_sources=changed,
            original_ext006_sha256='6'*64,original_ext007_sha256='7'*64,
            calibration_freeze_sha256='f'*64)
        self.rules['original_unbundled_native_sources']=[put(self.source,'src/unbundled.cpp',b'original omitted source')]
        self.rules['current_build_metadata']=put(self.build,'generated/version_metadata.json',
            json.dumps(dict(source_revision='b'*40,source_dirty=False,build_type='Release'),indent=2).encode()+b'\n')
        raw=self.report.read_bytes();self.rules['current_codegen']=dict(path=self.report.name,size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest())
        self.base=SimpleNamespace(resolutions={f'S17-EXT-{i:03d}':SimpleNamespace(
            input_id=f'S17-EXT-{i:03d}',resolution_id=f'original-{i}',sha256=str(i)*64,semantic_context={}) for i in range(1,8)})
        self.base.resolutions['S17-EXT-006'].semantic_context=dict(source_revision='a'*40,
            archive_bundle_root=str(self.old),release_artifact_path=str(self.old/old_worker['path']),
            release_artifact_size_bytes=old_worker['size_bytes'],release_artifact_sha256=old_worker['sha256'],
            inventory_sha256=inv['sha256'])
        self.base.resolutions['S17-EXT-007'].semantic_context=dict(calibration_scope=compatibility.CALIBRATION_SCOPE,
            data_provenance_accepted=True,legacy_statistical_freeze_satisfied=False)
        self.stack=compatibility.contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(compatibility,'_review',side_effect=lambda:copy.deepcopy(self.rules)))
        self.stack.enter_context(mock.patch.object(compatibility.readers,'_source_names',side_effect=lambda index:
            {n for n in index if n.startswith(('include/','src/'))}|{self.rules_name}))
        self.codegen=self.stack.enter_context(mock.patch.object(compatibility,'_codegen'))

    def verify(self,**changes):
        args=dict(base_validation=self.base,plan_sha256='d'*64,original_bundle=self.old,
            source_root=self.source,release_root=self.build,codegen_report=self.report)
        args.update(changes);return compatibility.verify(**args)

    def test_actual_files_and_reviewed_change_are_required_without_full_admission(self):
        owner=self.verify();proof=owner.proof(base_validation=self.base,plan_sha256='d'*64)
        self.assertTrue(proof['software_compatibility_verified'])
        for key in ('full_ext008_admission','execution_authority','phase18_authority','legacy_statistical_freeze_satisfied'):
            self.assertIs(proof[key],False)
        self.assertEqual(len(proof['base_resolutions']),7)
        self.assertEqual(proof['calibration_scope'],compatibility.CALIBRATION_SCOPE)
        self.assertEqual(proof['reviewed_shared_changes'],['src/cold.cpp'])
        self.assertEqual(proof['new_native_sources'],['src/pilot.cpp'])
        self.assertEqual(self.codegen.call_count,1)

    def test_unreviewed_shared_source_change_rejects(self):
        (self.source/'include/unchanged.hpp').write_bytes(b'rewritten')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'shared source differs'):self.verify()

    def test_wrong_reviewed_source_or_added_source_rejects(self):
        for name in ('src/cold.cpp','src/pilot.cpp'):
            with self.subTest(name=name):
                p=self.source/name;raw=p.read_bytes();p.write_bytes(raw+b'x')
                with self.assertRaisesRegex(compatibility.readers.AdmissionError,'SHA256 mismatch|regular file size'):self.verify()
                p.write_bytes(raw)

    def test_unexpected_missing_and_symlink_native_sources_reject(self):
        extra=self.source/'src/foreign.cpp';extra.write_bytes(b'foreign')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'source closure'):self.verify()
        extra.unlink();path=self.source/'src/pilot.cpp';raw=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(compatibility.CompatibilityError,'source closure'):self.verify()
        target=self.root/'outside';target.write_bytes(raw);path.symlink_to(target)
        with self.assertRaisesRegex(compatibility.CompatibilityError,'symlink'):self.verify()

    def test_library_worker_and_inventory_tamper_reject(self):
        for path in (self.build/'libcpu_prefetch_queue.a',self.build/'libcpu_prefetch_calibration.a',
                self.build/'cpu_prefetch_runner',self.old/'BUNDLE_INVENTORY.json',self.source/'src/unbundled.cpp'):
            with self.subTest(path=path.name):
                raw=path.read_bytes();path.write_bytes(raw+b'x')
                with self.assertRaises(compatibility.readers.AdmissionError):self.verify()
                path.write_bytes(raw)

    def test_codegen_rejection_propagates_without_owner(self):
        self.codegen.side_effect=compatibility.CompatibilityError('actual dual codegen rejected')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'dual codegen rejected'):self.verify()

    def test_original_release_and_descriptive_ancestry_must_match(self):
        for key,field,value in [('S17-EXT-006','inventory_sha256','0'*64),
                ('S17-EXT-006','source_revision','0'*40),
                ('S17-EXT-007','legacy_statistical_freeze_satisfied',True),
                ('S17-EXT-007','data_provenance_accepted',False)]:
            with self.subTest(field=field):
                original=copy.deepcopy(self.base);self.base.resolutions[key].semantic_context[field]=value
                with self.assertRaises(compatibility.CompatibilityError):self.verify()
                self.base=original

    def test_relocated_bytes_keep_original_locators_and_are_inspection_only(self):
        context=self.base.resolutions['S17-EXT-006'].semantic_context
        context['archive_bundle_root']='/original/stand/bundle'
        context['release_artifact_path']='/original/stand/bundle/release/bin/cpu_prefetch_runner'
        with self.assertRaisesRegex(compatibility.CompatibilityError,'mirror'):self.verify()
        owner=self.verify(allow_inspection_mirror=True);proof=owner.proof(base_validation=self.base,plan_sha256='d'*64)
        self.assertTrue(proof['inspection_mirror']);self.assertEqual(proof['original_release_context'],context)
        with self.assertRaisesRegex(compatibility.CompatibilityError,'inspection mirror'):
            owner.proof(base_validation=self.base,plan_sha256='d'*64,for_execution=True)

    def test_completed_proof_rehashes_and_latches_tamper(self):
        owner=self.verify();p=self.source/'src/cold.cpp';raw=p.read_bytes();p.write_bytes(raw+b'x')
        with self.assertRaises(compatibility.readers.AdmissionError):owner.proof(base_validation=self.base,plan_sha256='d'*64)
        p.write_bytes(raw)
        with self.assertRaisesRegex(compatibility.CompatibilityError,'failed'):
            owner.proof(base_validation=self.base,plan_sha256='d'*64)

    def test_completed_proof_rejects_changed_plan_and_original_seven(self):
        owner=self.verify()
        with self.assertRaisesRegex(compatibility.CompatibilityError,'plan'):
            owner.proof(base_validation=self.base,plan_sha256='e'*64)
        owner=self.verify();self.base.resolutions['S17-EXT-001'].sha256='0'*64
        with self.assertRaisesRegex(compatibility.CompatibilityError,'ancestry'):
            owner.proof(base_validation=self.base,plan_sha256='d'*64)

    def test_report_cannot_construct_an_owner_and_wrong_process_cannot_use_it(self):
        with self.assertRaisesRegex(compatibility.CompatibilityError,'actual verification'):
            compatibility._VerifiedCompatibility(token=object(),receipt={},files=[],paths={})
        owner=self.verify()
        with mock.patch.object(compatibility.os,'getpid',return_value=-1):
            with self.assertRaisesRegex(compatibility.CompatibilityError,'process'):
                owner.proof(base_validation=self.base,plan_sha256='d'*64)

    def test_duplicate_and_traversal_inventory_rows_reject(self):
        for rows in ([dict(path='../outside',size_bytes=0,sha256='0'*64)],
                [dict(path='src/a',size_bytes=0,sha256='0'*64)]*2):
            with self.assertRaises(compatibility.CompatibilityError):compatibility._inventory(dict(files=rows),self.old)

    def test_source_added_during_codegen_and_after_completion_is_rejected(self):
        path=self.source/'src/unexpected.cpp'
        self.codegen.side_effect=lambda *args,**kwargs:path.write_bytes(b'unexpected')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'closure changed during'):self.verify()
        path.unlink();self.codegen.side_effect=None;owner=self.verify();path.write_bytes(b'unexpected')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'closure changed'):
            owner.proof(base_validation=self.base,plan_sha256='d'*64)

    def test_source_root_or_top_level_source_directory_symlink_rejects(self):
        alias=self.root/'alias';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaisesRegex(compatibility.CompatibilityError,'canonical directory'):self.verify(source_root=alias)
        (self.source/'include').rename(self.root/'includes');(self.source/'include').symlink_to(self.root/'includes')
        with self.assertRaisesRegex(compatibility.CompatibilityError,'symlink'):self.verify()

    def test_original_source_and_current_build_provenance_or_report_tamper_rejects(self):
        for path in (self.old/'src/cold.cpp',self.build/'generated/version_metadata.json',self.report):
            with self.subTest(path=path.name):
                raw=path.read_bytes();path.write_bytes(raw+b' ')
                with self.assertRaises(compatibility.readers.AdmissionError):self.verify()
                path.write_bytes(raw)

    def test_expired_metadata_lease_and_byte_limit_reject(self):
        with mock.patch.object(compatibility.readers,'MAX_SECONDS',0):
            with self.assertRaisesRegex(compatibility.readers.AdmissionError,'deadline'):self.verify()
        with mock.patch.object(compatibility.readers,'MAX_TOTAL_BYTES',8):
            with self.assertRaisesRegex(compatibility.readers.AdmissionError,'aggregate metadata'):self.verify()

    def test_supplemental_source_cannot_override_an_original_or_new_source(self):
        self.rules['original_unbundled_native_sources'][0]['path']='src/cold.cpp'
        with self.assertRaisesRegex(compatibility.CompatibilityError,'supplemental source coverage'):self.verify()


class FixedReviewTests(unittest.TestCase):
    def test_actual_review_bytes_are_pinned_and_preserve_scope(self):
        rules=compatibility._review()
        self.assertEqual(rules['current_source_revision'],'34247cedab4abe4b44732daae8fdac1700eccffd')
        self.assertEqual(sum(r['identical'] for r in rules['libraries']),8)
        self.assertEqual(len(rules['original_unbundled_native_sources']),54)
        self.assertEqual(len(rules['changed_native_sources']),23)
        self.assertEqual(rules['calibration_freeze_sha256'],
            'cdf85bf585c997e079f432f904d93849fa5f69757440c7cefcf61ca7e06d742c')

    def test_changed_review_bytes_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.json';path.write_bytes(compatibility.REVIEW.read_bytes()+b' ')
            with mock.patch.object(compatibility,'REVIEW',path):
                with self.assertRaisesRegex(compatibility.readers.AdmissionError,'SHA256 mismatch'):compatibility._review()


if __name__=='__main__':unittest.main()
