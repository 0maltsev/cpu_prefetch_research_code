"""Fixed software profile and time accounting; no stand or experiment actions."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_service_v1 as service


class BudgetTests(unittest.TestCase):
    def timing(self):
        return dict(status='SOFTWARE_METADATA_TIMING_PASS',scientific_captures_collected=0,
            original_research_raw_bytes_read=0,operational_window_started=False,
            original_header_receipt_metadata_180_repeated_same_capture_ns=7900050742,
            synthetic_family_roundtrip_ns=2609222920,synthetic_complete_family_consistency_ns=5314072535,
            total_measured_metadata_components_ns=15823346197)

    def test_whole_analysis_and_pilot_estimates_fit_original_caps(self):
        result=service.analysis_budget(self.timing())
        self.assertEqual(result['estimated_analysis_ns'],5348934515095)
        self.assertEqual(result['estimated_analysis_margin_ns'],51065484905)
        self.assertEqual(result['estimated_whole_run_ns'],57084*10**9)
        self.assertLess(result['estimated_whole_run_ns'],result['operational_cap_ns'])
        self.assertFalse(result['estimate_is_guarantee']);self.assertFalse(result['execution_authority'])

    def test_slow_inconsistent_or_empirical_input_cannot_pass_budget(self):
        rows=[]
        for key,value in (('operational_window_started',True),('scientific_captures_collected',1),
                ('original_research_raw_bytes_read',1),('status','ASSERTED_READY'),
                ('total_measured_metadata_components_ns',1)):
            row=self.timing();row[key]=value;rows.append(row)
        row=self.timing();row['original_header_receipt_metadata_180_repeated_same_capture_ns']+=60*10**9
        row['total_measured_metadata_components_ns']+=60*10**9;rows.append(row)
        for row in rows:
            with self.subTest(row=row),self.assertRaises(RuntimeError):service.analysis_budget(row)


class ProfileTests(unittest.TestCase):
    def verify(self,rows,files):
        root=Path('/opt/SOFTWARE');raw=json.dumps(dict(files=rows)).encode()
        def read(path,maximum):return raw if path.name=='manifest.json' else files[str(path.relative_to(root))]
        with mock.patch.object(service,'_read',side_effect=read),mock.patch.object(service,'_inventory',
                return_value=set(files)|{'manifest.json'}):
            return service._manifest(root,'manifest.json',hashlib.sha256(raw).hexdigest())

    def row(self,path,raw=b'SOFTWARE'):
        return dict(path=path,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def test_exact_source_bindings_are_checked_before_import(self):
        result,seen=self.verify([self.row('tools/a.py')],{'tools/a.py':b'SOFTWARE'})
        self.assertEqual(seen,{'tools/a.py'})
        with self.assertRaisesRegex(RuntimeError,'bytes differ'):
            self.verify([self.row('tools/a.py')],{'tools/a.py':b'CHANGED!'})

    def test_duplicate_absolute_and_traversal_member_rejected(self):
        for rows in ([self.row('../a')],[self.row('/absolute')],[self.row('a'),self.row('a')],[self.row('.')]):
            with self.subTest(rows=rows),self.assertRaisesRegex(RuntimeError,'unsafe or duplicate'):
                self.verify(rows,{'a':b'SOFTWARE'})

    def test_external_manifest_digest_is_required(self):
        with mock.patch.object(service,'_read',return_value=b'{}'):
            with self.assertRaisesRegex(RuntimeError,'externally pinned'):
                service._manifest(Path('/opt/SOFTWARE'),'manifest.json','0'*64)

    def test_extra_module_not_in_profile_is_rejected(self):
        row=self.row('a');raw=json.dumps(dict(files=[row])).encode()
        with mock.patch.object(service,'_read',side_effect=lambda path,maximum:raw if path.name=='manifest.json' else b'SOFTWARE'),mock.patch.object(
                service,'_inventory',return_value={'manifest.json','a','stage17_shadow.py'}):
            with self.assertRaisesRegex(RuntimeError,'unexpected or missing'):
                service._manifest(Path('/opt/SOFTWARE'),'manifest.json',hashlib.sha256(raw).hexdigest())

    def test_public_entry_rejects_wrong_source_location_before_controller_import(self):
        with mock.patch.object(service.os,'getresuid',return_value=(0,0,0)):
            with self.assertRaisesRegex(RuntimeError,'fixed service source location'):service.authenticate('f'*64)

    def test_profile_cannot_select_commands_keys_or_runtime_backends(self):
        self.assertNotIn('command',service.MEMBERS);self.assertNotIn('private-key',service.MEMBERS)
        self.assertIn(service.HEADER,service.MEMBERS)
        self.assertIn('tools/stage17_s180_qualification_evidence_v1.py',service.MEMBERS)
        self.assertIn('config/schemas/qualification-evidence-v3.schema.json',service.MEMBERS)


if __name__=='__main__':unittest.main()
