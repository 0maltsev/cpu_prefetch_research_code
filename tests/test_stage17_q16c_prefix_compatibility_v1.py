"""Actual file comparisons; synthetic original qualification boundary only."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_prefix_compatibility_v1 as current
import stage17_semantic_verifier_v61 as semantic
import stage17_phase_controller_v2 as owner
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
            report['rule_set_sha256']=files.binding(root/'tools/check_formal_codegen.py')['sha256']
            report['source_evidence']={name:files.binding(root/name)['sha256'] for name in current.limits.make_handoffs()[0].codegen.SOURCE_PATHS}
            rb=files.save(root/'build-provenance/formal_codegen_report.json',report)
            index['build-provenance/formal_codegen_report.json']=dict(rb,path='build-provenance/formal_codegen_report.json')
            e.proof[side]['formal_codegen']=rb
            inventory=files.save(root/'BUNDLE_INVENTORY.json',dict(files=list(index.values())))
            e.proof[side]['bundle_inventory']=inventory;e.contexts[side]['inventory_sha256']=inventory['sha256']
        e.proof['original']['source_revision']=current.contract.PARENT_SOURCE
        old=e.original_validation.resolutions['S17-EXT-006'].semantic_context
        old.update(source_revision=current.contract.PARENT_SOURCE,release_artifact_sha256=current.window.previous.WORKER,
            inventory_sha256='8cfad0e13f95e896f1824ead7beba8dad6b44a5c7327a928e35f7a46b5746444')
        self.proof=dict(schema_version=current.SCHEMA,decision='D288',stand_id=e.plan['stand_id'],boot_id=e.boot,
            parent_plan_sha256=current.contract.PARENT_SHA256,original=e.proof['original'],current=e.proof['current'],
            platform_manifests=e.proof['platform_manifests'],execution_authority=False,phase18_authority=False)
        # Reproduce the real deployment: the reader belongs to the original
        # signed cold packet and is absent from its qualified bundle.
        original_root,original_index,_=e.releases['original']
        reader='tools/stage17_q16c_control_reader_v1.py'
        packet=e.root/'original-scientific-packet';packet.mkdir()
        member=packet/Path(reader).name;member.write_bytes((Path(original_root)/reader).read_bytes())
        (Path(original_root)/reader).unlink();original_index.pop(reader)
        self.packet=files.save(packet/'manifest.json',dict(schema_version='cpu-prefetch-stage17-q16c-cold-packet/1',
            qualified_source_revision=current.contract.PARENT_SOURCE,qualified_worker_sha256=current.window.previous.WORKER,
            execution_authority=False,phase18_authority=False,
            files=[dict(name=member.name,size_bytes=member.stat().st_size,sha256=files.binding(member)['sha256'])]))
        self.proof['original_scientific_packet']=dict(manifest=self.packet)
        self.refresh()
    def refresh(self):
        e=self.e
        def comparison(name):
            return dict(relative_path=name,**{side:dict(index[name],path=str(Path(root)/name))
                for side,(root,index,_) in e.releases.items()})
        names=current.admission._source_names(e.releases['original'][1])
        self.proof.update(libraries=[comparison(n) for n in sorted(current.LIBRARIES)],
            source_comparisons=[comparison(n) for n in sorted(names)],
            scientific_dependencies=current.science.bindings(e.releases['original'][0],e.releases['current'][0],
                e.releases['original'][1],e.releases['current'][1],self.packet,current.admission.BoundReader()))
    def consume(self):
        helpers=current.limits.make_handoffs();selected=helpers[0];actual=selected._release
        def release(side,context,reader,source):
            return self.e.releases['original'] if source==current.contract.PARENT_SOURCE else actual(side,context,reader,source)
        binding=files.save(self.e.root/'prefix-compatibility.json',self.proof)
        with patch.object(current.limits,'make_handoffs',return_value=helpers),patch.object(selected,'_release',side_effect=release),\
             patch.object(current.science,'authenticate',return_value=self.packet):
            return current.consume(self.e.plan,binding,validation=self.e.validation,
                original_validation=self.e.original_validation,boot_id=self.e.boot)
    def test_nine_actual_libraries_full_scientific_closure_and_platform_history_are_preserved(self):
        result=self.consume()
        self.assertEqual(result['identical_measured_libraries'],sorted(current.LIBRARIES))
        self.assertEqual(result['original_platform_regime'],'UNRECORDED')
        self.assertEqual(result['current_platform_regime'],'VERIFIED_ZERO_REQUIRED')
        self.assertFalse(result['execution_authority']);self.assertFalse(result['phase18_authority'])
    def test_original_packet_reader_cannot_be_changed_or_omitted(self):
        self.proof['scientific_dependencies']=[r for r in self.proof['scientific_dependencies']
            if r['relative_path']!='tools/stage17_q16c_control_reader_v1.py']
        with self.assertRaises(current.admission.AdmissionError):self.consume()
        self.refresh();p=Path(self.packet['path']).parent/'stage17_q16c_control_reader_v1.py'
        p.write_bytes(p.read_bytes()+b'\n# altered reader\n')
        with self.assertRaises(current.admission.AdmissionError):self.consume()
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
        with self.assertRaises(current.admission.AdmissionError):self.refresh()

class OriginalScientificSignatureTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.folder=self.root/'d282-execution-window-1';self.folder.mkdir()
        self.key=self.root/'test-key'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],check=True,capture_output=True)
        self.packet=files.save(self.root/'manifest.json',dict(test_only=True))
        record=dict(source_revision=current.window.previous.SOURCE,worker_sha256=current.window.previous.WORKER,
            stand_id='SOFTWARE-ONLY-SIGNATURE-TEST',bindings=dict(administrative_manifest=self.packet))
        raw=json.dumps(record,sort_keys=True,separators=(',',':')).encode()
        raw+=b' '*(3462-len(raw));self.assertEqual(len(raw),3462)
        p=self.folder/'window.json';p.write_bytes(raw)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.key),'-n','stage17-owner-acceptance',str(p)],
            check=True,capture_output=True)
        signers=self.root/'allowed-signers';signers.write_bytes(b'test-owner '+self.key.with_suffix('.pub').read_bytes())
        b=files.binding(signers)
        trust=dict(subject_id=record['stand_id'],measurements=dict(reviewer_role='OWNER',principal='test-owner',
            sshsig_namespace='stage17-owner-acceptance',allowed_signers_path=str(signers),
            allowed_signers_size_bytes=b['size_bytes'],allowed_signers_sha256=b['sha256']))
        self.validation=types.SimpleNamespace(resolutions={'S17-EXT-003':types.SimpleNamespace(semantic_context=dict(trust=trust))})
        self.proof=dict(execution_window=files.binding(p),signature=files.binding(Path(str(p)+'.sig')),manifest=self.packet)

    def authenticate(self):
        with patch.object(current.window.previous,'EVIDENCE',self.root),\
             patch.object(current.science,'WINDOW_SHA',self.proof['execution_window']['sha256']),\
             patch.object(current.science,'SIGNATURE_SHA',self.proof['signature']['sha256']):
            return current.science.authenticate(self.proof,self.validation,current.admission.BoundReader())

    def test_actual_owner_signature_authenticates_the_exact_signed_packet_binding(self):
        self.assertEqual(self.authenticate(),self.packet)

    def test_unsigned_substitute_manifest_is_rejected(self):
        self.proof['manifest']=files.save(self.root/'other-manifest.json',dict(test_only='substitute'))
        with self.assertRaises(current.admission.AdmissionError):self.authenticate()

    def test_rebound_corrupt_signature_is_still_rejected_by_real_crypto(self):
        p=Path(self.proof['signature']['path']);data=bytearray(p.read_bytes());data[len(data)//2]^=1;p.write_bytes(data)
        self.proof['signature']=files.binding(p)
        with self.assertRaises(owner.ControllerError):self.authenticate()

    def test_non_owner_trust_does_not_authenticate_a_valid_signature(self):
        self.validation.resolutions['S17-EXT-003'].semantic_context['trust']['measurements']['reviewer_role']='OTHER'
        with self.assertRaises(current.admission.AdmissionError):self.authenticate()


if __name__=='__main__':unittest.main()
