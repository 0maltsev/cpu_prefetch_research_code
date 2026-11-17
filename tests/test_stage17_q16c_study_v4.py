"""D279 retains original native supervision and binds completed preconstruction."""
import ast
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_q16c_study_v3 as old
import stage17_q16c_study_v4 as current
import stage17_q16c_operator_v1 as op1
import stage17_q16c_operator_v2 as op2
import launch_stage17_q16c_rearmed_v1 as rearm


class StudyTests(unittest.TestCase):
    def test_recovery_and_owner_handoff_unchanged_except_fresh_study_namespace(self):
        a=ast.parse(Path(old.__file__).read_bytes());b=ast.parse(Path(current.__file__).read_bytes())
        for n in ast.walk(b):
            if isinstance(n,ast.Constant) and n.value=='q16c-study-2':n.value='q16c-study-1'
        functions=lambda t:{n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}
        aa,bb=functions(a),functions(b)
        for name in aa:
            if name!='run':self.assertEqual(ast.dump(aa[name]),ast.dump(bb[name]),name)
        # Actual collection, cleanup and analysis calls are retained in the run
        # body. The original command('construct') is replaced by bound admission.
        before=Path(old.__file__).read_text();after=Path(current.__file__).read_text()
        block="""        result['preconstruction']=verify_preconstruction(c)
        save(study/'construct-admission.json',result['preconstruction'])
        command('sign',prep_deadline);command('check',prep_deadline)"""
        normalized=after.replace(block,"        command('construct',prep_deadline);command('sign',prep_deadline);command('check',prep_deadline)").replace('q16c-study-2','q16c-study-1')
        n=functions(ast.parse(normalized));self.assertEqual(ast.dump(aa['run']),ast.dump(n['run']))
        oldop=ast.parse(Path(op1.__file__).read_text());newop=ast.parse(Path(op2.__file__).read_text().replace('q16c-study-2','q16c-study-1'))
        self.assertEqual(ast.dump(functions(oldop)['main']),ast.dump(functions(newop)['main']))

    def test_preconstruction_requires_exact_configuration_plan_window_and_real_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);packet=root/'packet';packet.mkdir();out=root/'authoring';out.mkdir()
            def save(p,value):current.save(p,value);return current.binding(p)
            window=save(root/'window.json',dict(id='software-only'));sig=save(root/'sig.json',dict(id='software-only'))
            frozen=save(packet/'plan.json',dict(id='software-only'))
            worker=dict(path='/software-only-worker',size_bytes=1,sha256='1'*64)
            cfg=dict(packet_root=str(packet),manifest=dict(sha256='2'*64),boot_id='software-only',execution_window_proof=dict(manifest=window,signature=sig),
                overlay=save(packet/'archive-overlay-continuation-1.json',dict(execution_authority=False)),historical_inputs=save(packet/'history.json',{}))
            cb=save(packet/'cfg.json',cfg);ib=save(packet/'inputs.json',{})
            c=dict(output_root=str(out),packet_root=str(packet),worker=worker,boot_id='software-only',files=dict(frozen_plan=frozen,manifest=cfg['manifest'],execution_window=window,execution_window_signature=sig))
            before=save(root/'configuration-before.json',c)
            result=save(root/'construction-result.json',dict(exit_code=0,leader_reaped=True,configuration_sha256=before['sha256']))
            built=save(out/'constructed.json',dict(status='ALL_SOURCE_HISTORY_COMPATIBILITY_GATES_PASS',plan=frozen,qualified_worker=worker,cli_configuration=cb,action_inputs=ib))
            c['files'].update(preconstruction_configuration=before,preconstruction_result=result,constructed=built)
            current.verify_preconstruction(c)
            for key,value in [('boot_id','changed'),('output_root','/wrong')]:
                bad=copy.deepcopy(c);bad[key]=value
                with self.subTest(key=key),self.assertRaises(RuntimeError):current.verify_preconstruction(bad)
            p=Path(result['path']);d=json.loads(p.read_bytes());d['leader_reaped']=False;p.write_text(json.dumps(d));c['files']['preconstruction_result']=current.binding(p)
            with self.assertRaisesRegex(RuntimeError,'reaped'):current.verify_preconstruction(c)

    def test_hardware_prestate_must_be_observed_exactly_and_reads_are_read_only(self):
        request=dict(action_inputs=dict(prestate=[dict(cpu=n,complete_value_hex='0000000000000000') for n in (0,1,8)]))
        with patch.object(rearm.os,'open',return_value=5) as opened,patch.object(rearm.os,'close'),patch.object(rearm.os,'pread',return_value=b'\0'*8):
            rows=rearm.verify_hardware(request);self.assertEqual(len(rows),3)
            self.assertTrue(all(args[0][1]==rearm.os.O_RDONLY|rearm.os.O_CLOEXEC for args in opened.call_args_list))
        with patch.object(rearm.os,'open',return_value=5),patch.object(rearm.os,'close'),patch.object(rearm.os,'pread',return_value=b'\1'+b'\0'*7):
            with self.assertRaisesRegex(RuntimeError,'differs'):rearm.verify_hardware(request)


if __name__=='__main__':unittest.main()
