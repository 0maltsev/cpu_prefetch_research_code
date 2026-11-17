"""D279 real metadata/descriptor boundaries; no native execution or stand claims."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_resume_preparation_v1 as current
import stage17_q16c_prepare_v2 as base
import stage17_archive_q16c_descriptive_overlay_v1 as overlay


class ResumeTests(unittest.TestCase):
    def test_full_descriptor_rejects_old_paths_and_accepts_only_identical_relocation(self):
        packet=ROOT/'build/stage17-q16c-prep/operational-packet-ce40650-2'
        self.assertTrue(packet.is_dir(),'actual retained cold-packet fixture required')
        doc=json.loads((ROOT/'docs/evidence/stage17/Q16C-D277-COLD-STOP-20261117-01/failed_descriptor.json').read_bytes())
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);old=root/'packet1';new=root/'packet2';old.mkdir();new.mkdir()
            for name in doc['sources']:
                shutil.copyfile(packet/(name+'.py'),old/(name+'.py'));shutil.copyfile(packet/(name+'.py'),new/(name+'.py'))
            doc['sources']={name:base.binding(old/(name+'.py')) for name in doc['sources']}
            for key,role in [('baseline_bundle_root','baseline_profile'),('overlay_bundle_root','overlay_profile')]:
                p=root/key;p.mkdir();profile=p/overlay.PROFILE_MEMBER;profile.parent.mkdir(parents=True,exist_ok=True);profile.write_bytes(b'{}')
                doc[key]=str(p);doc[role]=base.binding(profile)
            doc['runtime_root']='/';original=copy.deepcopy(doc)
            with patch.object(overlay,'_CONFIG',None):
                with self.assertRaisesRegex(ValueError,'packet source namespace differs'):
                    overlay.configure_verified_descriptor(overlay.canonical(doc),new)
                fixed=current.relocate_sources(doc,new,base.read)
                overlay.configure_verified_descriptor(overlay.canonical(fixed),new)
            self.assertEqual(doc,original)
            self.assertEqual({k:v for k,v in fixed.items() if k!='sources'},{k:v for k,v in doc.items() if k!='sources'})
            for name,row in fixed['sources'].items():
                self.assertEqual(row,dict(doc['sources'][name],path=str(new/(name+'.py'))))
            first=next(iter(fixed['sources']));p=new/(first+'.py');p.write_bytes(p.read_bytes()+b'\n')
            with self.assertRaises(ValueError):current.relocate_sources(doc,new,base.read)

    def test_retained_output_must_be_byte_identical_and_failed_descriptor_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            packet=Path(directory);bindings={}
            for name in current.REUSED:bindings[name]=base.save(packet/name,dict(value=name))
            bad=packet/'archive-overlay.json';bad.write_bytes(b'original failure evidence')
            c=dict(packet_root=str(packet),retained_metadata=bindings)
            with patch.object(current,'PACKET',packet):save=current.publisher(base,c)
            for name in current.REUSED:
                self.assertEqual(save(packet/name,dict(value=name)),bindings[name])
                with self.assertRaisesRegex(ValueError,'retained metadata differs'):save(packet/name,dict(value='changed'))
            out=save(bad,dict(corrected=True))
            self.assertEqual(out['path'],str(packet/'archive-overlay-continuation-1.json'))
            self.assertEqual(bad.read_bytes(),b'original failure evidence')
            with self.assertRaises(FileExistsError):save(bad,dict(corrected=True))

    def test_original_validator_requires_stand_and_corrected_draft_reaches_hardware_gate(self):
        import stage17_phase_controller_v25 as validator
        plan=dict(stand_id='SOFTWARE-ACTUAL-STAND',source_revision='a'*40)
        inputs=dict(plan=plan,hardware_control={},prerequisite_bindings={})
        validation=types.SimpleNamespace(resolutions={'S17-EXT-006':types.SimpleNamespace(semantic_context=dict(source_revision='a'*40))})
        with patch.object(validator.contract,'validate_plan',return_value=object()),patch.object(validator,'runtime_from_context'), \
             patch.object(validator.hardware_controller,'_validate_hardware_control',side_effect=RuntimeError('HARDWARE_BOUNDARY_REACHED')):
            with self.assertRaisesRegex(KeyError,'stand_id'):
                validator.validate_action_inputs(dict(action_id='Q16c',action_inputs=inputs),validation)
            request=current.validation_draft(inputs,plan)
            self.assertEqual(request['stand_id'],'SOFTWARE-ACTUAL-STAND')
            with self.assertRaisesRegex(RuntimeError,'HARDWARE_BOUNDARY_REACHED'):
                validator.validate_action_inputs(request,validation)
            request['stand_id']='DIFFERENT'
            with self.assertRaisesRegex(validator.ControllerError,'stand/source'):
                validator.validate_action_inputs(request,validation)
        with self.assertRaises(ValueError):current.validation_draft(dict(plan=dict(plan)),plan)
        original=base.construct.__code__
        function=current.constructor_with_stand_identity(base,dict(vars(base)))
        self.assertIs(base.construct.__code__,original)
        self.assertIs(function.__globals__['_q16c_validation_draft'],current.validation_draft)

    def test_source_membership_cannot_expand(self):
        with self.assertRaisesRegex(ValueError,'seven'):current.relocate_sources(dict(sources={}),Path('/tmp'),base.read)


if __name__=='__main__':unittest.main()
