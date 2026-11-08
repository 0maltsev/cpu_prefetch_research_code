"""D240 local fixtures only; no stand scan or empirical namespace clearance."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(HERE)]
import audit_namespaces_v25 as audit
import render_continuation as renderer
import stage17_q16a_continuation_admission_v1 as admission

OLD=ROOT/'build/stage17-step5-prep/formal-q16a-authoring-v23-1/audit_namespaces.py'
PARENT=ROOT/'build/stage17-step5-prep/formal-q16a-authoring-v23-1/final-v23-1/plan.json'


class NamespaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent_raw=PARENT.read_bytes();parent=json.loads(cls.parent_raw)
        paths=[s['path'] for s in parent['captures'][177]['monitoring']['environment_sources']
               if Path(s['path']).name in admission.contract.CPUSET_FILES]
        binding=lambda name:dict(path='/software-fixture/'+name,size_bytes=1,sha256='b'*64)
        spec=dict(parent_plan=renderer.data_binding(PARENT,cls.parent_raw),
            failed_family_receipt=dict(path='/software-fixture/failure',size_bytes=admission.contract.FAILURE_SIZE,sha256=admission.contract.FAILURE_SHA256),
            accepted_prefix_manifest=binding('prefix'),
            monitor_path_replacements=[dict(original_path=p,continuation_path='/sys/fs/cgroup/cpu-prefetch-v25-fixture/'+Path(p).name) for p in paths])
        cls.plan=renderer.assemble(parent,spec,'e58b180075c3e239705cae384fa28f3dc6e41b39',
            parent['storage']['implementation_profile_sha256'],binding('compatibility'),admission)
        cls.plan_raw=admission.canonical(cls.plan)
        cls.identities=dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',
            plan_sha256=hashlib.sha256(cls.plan_raw).hexdigest(),stand_id=cls.plan['stand_id'],
            phase_identities=[c['capture'][p] for c in cls.plan['captures'] for p in ('warmup','measurement')],
            schedule_namespaces=[],execution_authority=False)

    def test_original_root_selection_scanner_and_finite_limits_unchanged(self):
        old=ast.parse(OLD.read_bytes());new=ast.parse(Path(audit.__file__).read_bytes())
        for name in ('selected_roots','audit'):
            left=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name==name)
            right=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(left),ast.dump(right))
        self.assertEqual((audit.MAX_FILE,audit.MAX_TOTAL,audit.MAX_FILES),(64*1024**2,2*1024**3,20000))

    def test_1062_phase_identities_and_numeric_seed_reuse_not_collisions(self):
        m=audit.Matcher(self.identities);row=self.identities['phase_identities'][0]
        self.assertEqual(len(m.wanted),2126)
        self.assertEqual(m.json(json.dumps({'same_prospective_seed':row['seed_hex']}).encode()),[])
        for key in ('run_id','seed_id','namespace_id'):
            with self.subTest(key=key):
                escaped=json.dumps({'history':row[key]}).replace('F25','\\u004625').encode()
                self.assertIn(row[key],m.json(escaped))
        self.assertEqual(m.json(b'{"unrelated":"old-context"}\n',lines=True),[])
        for rows in (self.identities['phase_identities'][:-1],self.identities['phase_identities']+[row]):
            with self.assertRaises(ValueError):audit.Matcher(dict(self.identities,phase_identities=rows))
        duplicate=copy.deepcopy(self.identities);duplicate['phase_identities'][2]['run_id']=row['run_id']
        with self.assertRaisesRegex(ValueError,'unique'):audit.Matcher(duplicate)

    def test_exact_parent_contract_and_registry_bindings(self):
        proof=audit.validate_prospective(self.identities,self.plan_raw,self.parent_raw,admission.contract)
        self.assertTrue(proof['original_numeric_seeds_preserved']);self.assertFalse(proof['numeric_seeds_collision_scanned'])
        # The real parent-comparison function separately rejects changed numeric
        # seeds; history matching must not make that scientific decision.
        mutated=copy.deepcopy(self.plan)
        mutated['captures'][0]['capture']['warmup']['seed_hex']='0'*64
        with self.assertRaises(admission.contract.ContractError):
            admission.contract._compare_parent(mutated,json.loads(self.parent_raw))
        wrong=copy.deepcopy(self.identities);wrong['phase_identities'][0]['seed_hex']='0'*64
        with patch.object(admission.contract,'validate_parent') as parent_gate:
            with self.assertRaisesRegex(ValueError,'namespace registration differs'):
                audit.validate_prospective(wrong,self.plan_raw,self.parent_raw,admission.contract)
            parent_gate.assert_called_once_with(self.plan,self.parent_raw)

    def test_only_exact_own_e25_directory_may_be_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            local=base/'build/stage17-step5-prep/formal-q16a-continuation-authoring-1'
            stand=base/'local-authoring-cpuprefetchv5-25/formal-q16a-continuation-authoring-1'
            audit.validate_prospective_directory('local',base,local)
            audit.validate_prospective_directory('stand',base,stand)
            for mode,wrong in [('stand',stand.parent),('stand',base/'local-authoring-cpuprefetchv5-23'/stand.name),
                               ('local',base),('local',local.parent/'formal-q16a-authoring-v23-1')]:
                with self.assertRaises(ValueError):audit.validate_prospective_directory(mode,base,wrong)

    def test_scoped_scan_exclusion_errors_bounds_and_raw_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);m=audit.Matcher(self.identities);row=self.identities['phase_identities'][0]
            own=root/'formal-q16a-continuation-authoring-1';own.mkdir()
            (own/'prospective.json').write_text(json.dumps(row))
            (root/'history.json').write_text(json.dumps({'seed_hex':row['seed_hex']}))
            (root/'raw.bin').write_bytes(b'not-json '+row['run_id'].encode())
            report=audit.audit([root],m,own,time.monotonic()+5)
            self.assertEqual(report['status'],'PASS_SCOPED_HISTORY_AUDIT')
            self.assertEqual(report['checked_files'],1);self.assertEqual(len(report['excluded']),1)
            (root/'collision.json').write_text(json.dumps({'run_id':row['run_id']}))
            report=audit.audit([root],m,own,time.monotonic()+5)
            self.assertEqual(report['status'],'FAIL');self.assertEqual(len(report['matches']),1)
            (root/'symlink.json').symlink_to(root/'history.json')
            with patch.object(audit,'MAX_FILE',1):report=audit.audit([root],m,own,time.monotonic()+5)
            self.assertEqual(report['status'],'FAIL');self.assertGreaterEqual(len(report['errors']),3)
            report=audit.audit([root],m,own,time.monotonic()-1)
            self.assertEqual(report['status'],'FAIL')

    def test_stand_allowlist_ignores_unselected_raw_and_old_prospective_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)/'stage17-owner-evidence';base.mkdir();ctx=base/'local-authoring-cpuprefetchv5-23';ctx.mkdir()
            (ctx/'context.json').write_text('{}')
            (ctx/'admission-root/evidence').mkdir(parents=True)
            (ctx/'discovery-preparation-1').mkdir()
            (ctx/'discovery-output-r3-1').mkdir();(ctx/'formal-archive-program-1').mkdir()
            roots=audit.selected_roots('stand',base)
            self.assertEqual(set(roots),{ctx/'context.json',ctx/'admission-root/evidence',ctx/'discovery-preparation-1'})

    def test_bound_input_rejects_wrong_hash_symlink_and_oversize(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'data';raw=b'actual';p.write_bytes(raw);sha=hashlib.sha256(raw).hexdigest()
            self.assertEqual(audit.bound_input(p,sha,6),raw)
            for digest,maximum in [('0'*64,6),(sha,5)]:
                with self.assertRaises(ValueError):audit.bound_input(p,digest,maximum)
            link=root/'link';link.symlink_to(p)
            with self.assertRaises(ValueError):audit.bound_input(link,sha,6)

    def test_real_cli_local_fixture_with_actual_parent_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);(base/'AGENTS.md').write_text('software test fixture only')
            for relative in ('docs/evidence','build/stage17-step2-prep','build/stage17-step3-prep'):
                (base/relative).mkdir(parents=True)
            (base/'docs/evidence/history.json').write_text(json.dumps({'seed_hex':self.identities['phase_identities'][0]['seed_hex']}))
            plan=base/'plan.json';plan.write_bytes(self.plan_raw)
            ids=base/'identities.json';ids_raw=admission.canonical(self.identities);ids.write_bytes(ids_raw)
            command=[sys.executable,'-B',str(Path(audit.__file__)), '--repository-root',str(ROOT),
                '--mode','local','--base',str(base),'--identities',str(ids),'--identities-sha256',hashlib.sha256(ids_raw).hexdigest(),
                '--plan',str(plan),'--plan-sha256',hashlib.sha256(self.plan_raw).hexdigest(),
                '--parent-plan',str(PARENT),'--parent-plan-sha256',admission.contract.PARENT_SHA256,
                '--prospective-directory',str(base/'build/stage17-step5-prep/formal-q16a-continuation-authoring-1'),
                '--wall-seconds','300']
            result=subprocess.run(command,capture_output=True,text=True,timeout=300)
            self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(result.stdout)
            self.assertEqual(report['status'],'PASS_SCOPED_HISTORY_AUDIT');self.assertEqual(report['checked_files'],1)
            self.assertEqual(report['parent_contract']['phase_identities'],1062)
            self.assertFalse(report['execution_authority']);self.assertEqual(report['matches'],[])


if __name__=='__main__':unittest.main(verbosity=2)
