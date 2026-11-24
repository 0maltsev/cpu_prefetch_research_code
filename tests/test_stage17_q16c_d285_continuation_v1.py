"""D285 preserves qualification, exact partial metadata and owned recovery."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16c_d285_loader_v1 as loader
import stage17_q16c_packet_v3 as baseline_loader
import stage17_q16c_resume_preparation_v2 as preparation
import stage17_q16c_prepare_v3 as baseline_preparation
import stage17_q16c_study_v6 as study
import launch_stage17_q16c_rearmed_v2 as rearm


class PatchTests(unittest.TestCase):
    def test_only_exact_old_guard_is_replaced_and_keeps_actual_file_identity(self):
        old=(ROOT/'tests/fixtures/stage17_d285/original_source_guard.py').read_bytes()
        self.assertEqual(hashlib.sha256(old).hexdigest(),loader._D285_ORIGINAL_SHA)
        fixed=ROOT/'tools/stage17_q16c_empty_reuse_v1.py'
        binding=baseline_preparation.binding(fixed)
        calls=[]
        namespace=dict(load_source=lambda *args:calls.append(args),read=baseline_loader.read,
            require=baseline_loader.require)
        loader.install_exact_override(namespace,binding)
        namespace['load_source'](loader._D285_TARGET,Path('/original/guard.py'),old)
        self.assertEqual(calls[-1],(loader._D285_TARGET,fixed,fixed.read_bytes()))
        namespace['load_source']('another_module',Path('/original/another.py'),b'original')
        self.assertEqual(calls[-1],('another_module',Path('/original/another.py'),b'original'))
        with self.assertRaisesRegex(ValueError,'exact original guard'):
            namespace['load_source'](loader._D285_TARGET,fixed,old+b'\n')
        with tempfile.TemporaryDirectory() as directory:
            bad=Path(directory)/'guard.py';bad.write_bytes(fixed.read_bytes()+b'\n')
            loader.install_exact_override(namespace,baseline_preparation.binding(bad))
            with self.assertRaisesRegex(ValueError,'exact verified repair'):
                namespace['load_source'](loader._D285_TARGET,bad,old)


class PreparationTests(unittest.TestCase):
    def test_reuses_only_eight_byte_identical_outputs_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            packet=Path(directory);retained={}
            for name in preparation.REUSED:
                retained[name]=baseline_preparation.save(packet/name,dict(value=name))
            cfg=dict(packet_root=str(packet),retained_metadata=retained)
            with patch.object(preparation,'PACKET',packet):
                save=preparation.publisher(baseline_preparation,cfg)
            for name in retained:
                self.assertEqual(save(packet/name,dict(value=name)),retained[name])
                with self.assertRaisesRegex(ValueError,'retained output differs'):
                    save(packet/name,dict(value='changed'))
                self.assertEqual(baseline_preparation.document(retained[name]),dict(value=name))
            new=save(packet/'action-inputs.json',dict(new=True))
            self.assertEqual(baseline_preparation.document(new),dict(new=True))
            with self.assertRaises(FileExistsError):save(packet/'action-inputs.json',dict(new=True))
            del cfg['retained_metadata'][next(iter(retained))]
            with patch.object(preparation,'PACKET',packet), self.assertRaisesRegex(ValueError,'eight'):
                preparation.publisher(baseline_preparation,cfg)

    def test_only_exact_prearm_failure_and_actual_complete_repair_are_eligible(self):
        failed=json.loads((ROOT/'docs/evidence/stage17/Q16C-D282-CONSTRUCTOR-STOP-20261118-01/study-complete.json').read_bytes())
        restored=json.loads((ROOT/'docs/evidence/stage17/Q16C-D282-CONSTRUCTOR-STOP-20261118-01/partition-restoration.json').read_bytes())
        verified=json.loads((ROOT/'docs/evidence/stage17/Q16C-D284-SOURCE-REPAIR-20261118-01/actual-constructor-validation-pass.json').read_bytes())
        log=(ROOT/'docs/evidence/stage17/Q16C-D282-CONSTRUCTOR-STOP-20261118-01/construct.log').read_bytes()
        preparation.validate_incident(failed,restored,verified,log)
        for row in (dict(failed,success=True),dict(failed,phases=failed['phases']+[dict(role='collect')]),
                dict(failed,failure_traceback='another failure')):
            with self.assertRaises(ValueError):preparation.validate_incident(row,restored,verified,log)
        for field,value in [('status','FAIL'),('full_constructor_validation_passed',False),
                ('actual_qualified_source','0'*40),('collection_restarted',True),('experimental_actions',1)]:
            bad=copy.deepcopy(verified);bad[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                preparation.validate_incident(failed,restored,bad,log)
        with self.assertRaises(ValueError):preparation.validate_incident(failed,restored,verified,b'another failure')


class StudyTests(unittest.TestCase):
    def test_preconstruction_is_bound_to_configuration_plan_and_reaped_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);packet=root/'packet';packet.mkdir();out=root/'authoring';out.mkdir()
            def save(path,value):study.save(path,value);return study.binding(path)
            window=save(root/'window.json',dict(software_only=True))
            sig=save(root/'signature.json',dict(software_only=True))
            plan=save(packet/'plan.json',dict(software_only=True))
            worker=dict(path='/software-only-worker',size_bytes=1,sha256='1'*64)
            cfg=dict(packet_root=str(packet),manifest=dict(sha256='2'*64),boot_id='software-only',
                execution_window_proof=dict(manifest=window,signature=sig),
                overlay=save(packet/'archive-overlay.json',dict(execution_authority=False)),
                historical_inputs=save(packet/'history.json',{}))
            cb=save(packet/'cli.json',cfg);ab=save(packet/'inputs.json',{})
            c=dict(output_root=str(out),packet_root=str(packet),worker=worker,boot_id='software-only',
                files=dict(frozen_plan=plan,manifest=cfg['manifest'],execution_window=window,execution_window_signature=sig))
            before=save(root/'before.json',c)
            result=save(root/'construction-result.json',dict(exit_code=0,leader_reaped=True,
                started_monotonic_ns=1,configuration_sha256=before['sha256']))
            built=save(out/'constructed.json',dict(status='ALL_SOURCE_HISTORY_COMPATIBILITY_GATES_PASS',
                plan=plan,qualified_worker=worker,cli_configuration=cb,action_inputs=ab))
            c['files'].update(preconstruction_configuration=before,preconstruction_result=result,constructed=built)
            study.verify_preconstruction(c)
            bad=copy.deepcopy(c);bad['boot_id']='changed'
            with self.assertRaisesRegex(RuntimeError,'configuration changed'):study.verify_preconstruction(bad)
            p=Path(result['path']);d=json.loads(p.read_bytes());d['leader_reaped']=False
            p.write_text(json.dumps(d));c['files']['preconstruction_result']=study.binding(p)
            with self.assertRaisesRegex(RuntimeError,'reaped'):study.verify_preconstruction(c)

    def test_native_owner_cleanup_and_analysis_unchanged_with_fresh_study_namespace(self):
        def functions(text):
            return {n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        original=(ROOT/'tools/stage17_q16c_study_v5.py').read_text()
        current=Path(study.__file__).read_text().replace('q16c-study-2','q16c-study-1')
        current=current.replace("        prep_started=load(c['files']['preconstruction_result'])['started_monotonic_ns']\n        prep_deadline=min(prep_started+600*NS,", "        prep_deadline=min(start+600*NS,")
        current=current.replace("        result['preconstruction']=verify_preconstruction(c)\n        save(study/'construct-admission.json',result['preconstruction'])\n        command('sign',prep_deadline);command('check',prep_deadline)",
            "        command('construct',prep_deadline);command('sign',prep_deadline);command('check',prep_deadline)")
        a,b=functions(original),functions(current)
        for name in a:self.assertEqual(ast.dump(a[name]),ast.dump(b[name]),name)
        oldop=functions((ROOT/'tools/stage17_q16c_operator_v3.py').read_text())
        newop=functions((ROOT/'tools/stage17_q16c_operator_v4.py').read_text().replace('q16c-study-2','q16c-study-1'))
        self.assertEqual(ast.dump(oldop['main']),ast.dump(newop['main']))

    def test_hardware_reads_are_read_only_and_mismatches_stop_rearm(self):
        request=dict(action_inputs=dict(prestate=[dict(cpu=n,complete_value_hex='0000000000000000') for n in (0,1,8)]))
        with patch.object(rearm.os,'open',return_value=5) as opened,patch.object(rearm.os,'close'),patch.object(rearm.os,'pread',return_value=b'\0'*8):
            self.assertEqual(len(rearm.verify_hardware(request)),3)
            self.assertTrue(all(call.args[1]==rearm.os.O_RDONLY|rearm.os.O_CLOEXEC for call in opened.call_args_list))
        with patch.object(rearm.os,'open',return_value=5),patch.object(rearm.os,'close'),patch.object(rearm.os,'pread',return_value=b'\1'+b'\0'*7):
            with self.assertRaisesRegex(RuntimeError,'differs'):rearm.verify_hardware(request)


if __name__=='__main__':unittest.main()
