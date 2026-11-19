"""Actual file comparisons; synthetic original qualification boundary only."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_prefix_compatibility_v1 as current
import stage17_semantic_verifier_v61 as semantic
import test_stage17_q16a_q16c_descriptive_handoff_v3 as fixture
import test_stage17_q16a_daycap_handoff_v1 as files

ROOT=Path(__file__).resolve().parents[1]

class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.Q16cQ16aReuseTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.e=e=self.fixture.e
        self.dependencies=semantic.discover_python_closure(ROOT,current.SCIENTIFIC_ROOTS)|{
            'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json','config/schemas/schedule-derivation-v2.schema.json',
            'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
        for side,(folder,index,report) in e.releases.items():
            root=Path(folder)
            for name in sorted(self.dependencies|current.LIBRARIES):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes((ROOT/name).read_bytes() if name in self.dependencies else b'identical measured library '+name.encode())
                index[name]=dict(files.binding(path),path=name)
            inventory=files.save(root/'BUNDLE_INVENTORY.json',dict(files=list(index.values())))
            e.proof[side]['bundle_inventory']=inventory;e.contexts[side]['inventory_sha256']=inventory['sha256']
        e.proof['original']['source_revision']=current.contract.PARENT_SOURCE
        old=e.original_validation.resolutions['S17-EXT-006'].semantic_context
        old.update(source_revision=current.contract.PARENT_SOURCE,release_artifact_sha256=current.window.previous.WORKER,
            inventory_sha256='8cfad0e13f95e896f1824ead7beba8dad6b44a5c7327a928e35f7a46b5746444')
        self.proof=dict(schema_version=current.SCHEMA,decision='D288',stand_id=e.plan['stand_id'],boot_id=e.boot,
            parent_plan_sha256=current.contract.PARENT_SHA256,original=e.proof['original'],current=e.proof['current'],
            platform_manifests=e.proof['platform_manifests'],execution_authority=False,phase18_authority=False)
        self.refresh()
    def refresh(self):
        e=self.e
        def comparison(name):
            return dict(relative_path=name,**{side:dict(index[name],path=str(Path(root)/name))
                for side,(root,index,_) in e.releases.items()})
        names=current.admission._source_names(e.releases['original'][1])
        self.proof.update(libraries=[comparison(n) for n in sorted(current.LIBRARIES)],
            source_comparisons=[comparison(n) for n in sorted(names)],
            scientific_dependencies=[comparison(n) for n in sorted(self.dependencies)])
    def consume(self):
        helpers=current.limits.make_handoffs();selected=helpers[0];actual=selected._release
        def release(side,context,reader,source):
            return self.e.releases['original'] if source==current.contract.PARENT_SOURCE else actual(side,context,reader,source)
        binding=files.save(self.e.root/'prefix-compatibility.json',self.proof)
        with patch.object(current.limits,'make_handoffs',return_value=helpers),patch.object(selected,'_release',side_effect=release):
            return current.consume(self.e.plan,binding,validation=self.e.validation,
                original_validation=self.e.original_validation,boot_id=self.e.boot)
    def test_nine_actual_libraries_full_scientific_closure_and_platform_history_are_preserved(self):
        result=self.consume()
        self.assertEqual(result['identical_measured_libraries'],sorted(current.LIBRARIES))
        self.assertEqual(result['original_platform_regime'],'UNRECORDED')
        self.assertEqual(result['current_platform_regime'],'VERIFIED_ZERO_REQUIRED')
        self.assertFalse(result['execution_authority']);self.assertFalse(result['phase18_authority'])
    def test_changed_or_missing_measured_library_fails_even_with_rebound_inventory(self):
        name='release/lib/libcpu_prefetch_timing.a';root,index,_=self.e.releases['current'];path=Path(root)/name
        path.write_bytes(b'different timing implementation');index[name]=dict(files.binding(path),path=name)
        inventory=files.save(Path(root)/'BUNDLE_INVENTORY.json',dict(files=list(index.values())))
        self.proof['current']['bundle_inventory']=inventory;self.e.contexts['current']['inventory_sha256']=inventory['sha256']
        self.refresh()
        with self.assertRaises(current.admission.AdmissionError):self.consume()
        self.proof['libraries'].pop()
        with self.assertRaises(current.admission.AdmissionError):self.consume()
    def test_changed_raw_validator_or_generator_and_wrong_incident_do_not_reuse(self):
        self.proof['parent_plan_sha256']='0'*64
        with self.assertRaises(current.admission.AdmissionError):self.consume()
        self.proof['parent_plan_sha256']=current.contract.PARENT_SHA256
        root,index,_=self.e.releases['current'];name='tools/stage17_formal_scheduled_capture_validation_v2.py'
        path=Path(root)/name;path.write_bytes(path.read_bytes()+b'\n# changed raw validator\n')
        index[name]=dict(files.binding(path),path=name)
        inventory=files.save(Path(root)/'BUNDLE_INVENTORY.json',dict(files=list(index.values())))
        self.proof['current']['bundle_inventory']=inventory;self.e.contexts['current']['inventory_sha256']=inventory['sha256']
        self.refresh()
        with self.assertRaises(current.admission.AdmissionError):self.consume()

if __name__=='__main__':unittest.main()
