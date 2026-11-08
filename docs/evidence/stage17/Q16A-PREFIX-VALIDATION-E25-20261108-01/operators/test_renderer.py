"""Software-only authoring checks. No qualification/prefix success is invented."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'tests'),str(HERE)]
import render_continuation as r
import stage17_q16a_continuation_admission_v1 as a
from test_stage17_q16a_continuation_admission_v1 import CompatibilityEvidence

PARENT=ROOT/'build/stage17-step5-prep/formal-q16a-authoring-v23-1/final-v23-1/plan.json'
BUNDLE=ROOT/'build/stage17-step5-prep/d235-package-verification/clean-dd981b4fdcf953386d4a7514fec381ff9be6e359/verified-package-1/extracted/cpu-prefetch-pilot-candidate-2.0.0-dd981b4-clean-d9e61e67bfa8'


def replacements(parent):
    old=[s['path'] for s in parent['captures'][177]['monitoring']['environment_sources']
         if Path(s['path']).name in a.contract.CPUSET_FILES]
    return [dict(original_path=p,continuation_path='/sys/fs/cgroup/cpu-prefetch-v25-test/'+Path(p).name) for p in old]


def save(path,doc):
    raw=a.canonical(doc);path.write_bytes(raw);return r.data_binding(path,raw)


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=PARENT.read_bytes();cls.parent=a._json(cls.original)
        cls.spec=dict(parent_plan=r.data_binding(PARENT,cls.original),
            failed_family_receipt=dict(path='/evidence/failure.json',size_bytes=a.contract.FAILURE_SIZE,sha256=a.contract.FAILURE_SHA256),
            accepted_prefix_manifest=dict(path='/evidence/prefix.json',size_bytes=1,sha256='c'*64),
            monitor_path_replacements=replacements(cls.parent))
        cls.compat=dict(path='/evidence/compatibility.json',size_bytes=1,sha256='d'*64)

    def plan(self):
        return r.assemble(self.parent,self.spec,'b'*40,self.parent['storage']['implementation_profile_sha256'],self.compat,a)

    def test_actual_parent_exact_531_preserved_numeric_seeds_science_budgets(self):
        plan=self.plan();extent=a.contract.validate_parent(plan,self.original)
        self.assertEqual(len(extent.captures),531)
        self.assertEqual(a.canonical(self.parent),self.original)
        self.assertEqual(plan['storage'],self.parent['storage']);self.assertEqual(plan['budget'],self.parent['budget'])
        self.assertEqual(plan['captures'][0]['capture']['warmup']['run_id'],'F25W00000177')
        self.assertEqual(plan['captures'][-1]['capture']['measurement']['run_id'],'F25M00000707')
        for local,item in enumerate(plan['captures']):
            old=self.parent['captures'][local+177]
            for phase in ('warmup','measurement'):
                self.assertEqual(item['capture'][phase]['seed_hex'],old['capture'][phase]['seed_hex'])
                self.assertEqual((4+len(item['capture'][phase]['run_id'])+7)//8,(4+len(old['capture'][phase]['run_id'])+7)//8)
            self.assertEqual(item['capture']['arena_seed'],item['capture']['measurement'])
            self.assertEqual(item['execution_budget'],old['execution_budget'])
            self.assertEqual(item['capture']['context_ordinal'],3+local//59)
            self.assertEqual(item['capture']['repetition_ordinal'],local%59)
        self.assertEqual([x['capture']['ordinal'] for x in plan['captures']],list(range(531)))

    def test_all_five_monitor_paths_required_and_no_other_changes(self):
        for rows in ([],self.spec['monitor_path_replacements'][:4]):
            s=copy.deepcopy(self.spec);s['monitor_path_replacements']=rows
            with self.assertRaises(a.AdmissionError):r.assemble(self.parent,s,'b'*40,'c'*64,self.compat,a)
        s=copy.deepcopy(self.spec);s['monitor_path_replacements'][0]['continuation_path']='/proc/meminfo'
        with self.assertRaises(a.contract.ContractError):r.assemble(self.parent,s,'b'*40,'c'*64,self.compat,a)

    def test_mutating_preserved_seed_or_shared_quota_rejected(self):
        for change in ('seed','quota','threshold'):
            p=self.plan()
            if change=='seed':p['captures'][0]['capture']['measurement']['seed_hex']='0'*64
            elif change=='quota':p['storage']['archive_quota_bytes']+=1
            else:p['minimum_observations_per_series']-=1
            with self.assertRaises(a.contract.ContractError):a.contract._compare_parent(p,self.parent)

    def test_actual_bundle_compatibility_all_sources_and_dual_machine_reports(self):
        oldworker=r.existing_binding(BUNDLE/'release/bin/cpu_prefetch_runner',a)
        context=dict(archive_bundle_root=str(BUNDLE),source_revision='b'*40,
            release_artifact_path=oldworker['path'],release_artifact_size_bytes=oldworker['size_bytes'],
            release_artifact_sha256=oldworker['sha256'],inventory_sha256=a.ORIGINAL_INVENTORY_SHA)
        # Same actual old bundle on both sides tests renderer plumbing only;
        # this is explicitly not an authenticated successor qualification.
        spec=dict(original_bundle_root=str(BUNDLE),monitor_path_replacements=self.spec['monitor_path_replacements'])
        reader=a.BoundReader();doc=r.compatibility(spec,context,a,reader)
        p=self.plan();a._compatibility(doc,p,context,reader);reader.finish()
        self.assertEqual([x['relative_path'] for x in doc['cold_source_changes']],[a.COLD_SOURCE])
        self.assertGreater(len(doc['measured_sources']),100)

    def test_changed_hot_source_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=CompatibilityEvidence(Path(tmp))
            f.document['measured_sources'][0]['continuation']['sha256']='0'*64
            with self.assertRaises(a.AdmissionError):f.validate()

    def test_bound_hash_limits_symlinks_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'input';p.write_bytes(b'actual')
            self.assertEqual(r.existing_binding(p,a),r.data_binding(p,b'actual'))
            with self.assertRaises(a.AdmissionError):r.existing_binding(p,a,maximum=5)
            link=root/'link';link.symlink_to(p)
            with self.assertRaises(a.AdmissionError):r.existing_binding(link,a)
            out=root/'out';raw=a.canonical({'x':1})
            result=r.exclusive_outputs(out,{'plan.json':raw},a)
            self.assertEqual((out/'plan.json').read_bytes(),b'{"x":1}')
            self.assertEqual(result['plan.json'],r.data_binding(out/'plan.json',raw))
            with self.assertRaises(a.AdmissionError):r.exclusive_outputs(out,{'plan.json':b'overwrite'},a)
            self.assertEqual((out/'plan.json').read_bytes(),raw)

    def gate_spec(self,root,status):
        parent=save(root/'parent.json',{})
        failure=save(root/'failure.json',{})
        prefix=save(root/'prefix.json',{'status':status})
        return dict(schema_version=r.SPEC_VERSION,qualification=dict(evidence_root=str(root)),parent_plan=parent,
            failed_family_receipt=failure,accepted_prefix_manifest=prefix,original_bundle_root=str(root/'bundle'),continuation_bundle_root=str(root/'bundle'),
            monitor_path_replacements=[],output_directory=str(root/'output'))

    def test_prefix_incomplete_fails_before_qualification_or_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.gate_spec(root,'RUNNING')
            with patch.object(r,'E25',root),patch.object(r,'qualify') as qualify:
                with self.assertRaises(a.AdmissionError):r.render(spec,ROOT,a,None)
                qualify.assert_not_called()
            self.assertFalse((root/'output').exists())

    def test_qualification_failure_creates_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);spec=self.gate_spec(root,'VALIDATED')
            with patch.object(r,'E25',root),patch.object(r,'qualify',side_effect=ValueError('qualification rejected')):
                with self.assertRaisesRegex(ValueError,'qualification rejected'):r.render(spec,ROOT,a,None)
            self.assertFalse((root/'output').exists())

    def test_synthetic_final_pipeline_canonical_three_files_and_proof_failure(self):
        # Only the unavailable empirical prefix and live journal are replaced.
        # Exact parent, original bundle bytes and dual codegen gates stay real.
        for reject in (True,False):
            with self.subTest(reject=reject), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);spec=self.gate_spec(root,'VALIDATED')
                spec['parent_plan']=r.data_binding(PARENT,self.original)
                spec['failed_family_receipt']=copy.deepcopy(self.spec['failed_family_receipt'])
                failure_path=root/'actual-failure.json'
                failure_path.write_bytes((ROOT/'build/stage17-step5-prep/q16a-failure-observed-20261108-1/stage17-q16a-failure-v6.json').read_bytes())
                spec['failed_family_receipt']=r.existing_binding(failure_path,a)
                spec['monitor_path_replacements']=self.spec['monitor_path_replacements']
                spec['original_bundle_root']=str(BUNDLE);spec['continuation_bundle_root']=str(BUNDLE)
                worker=r.existing_binding(BUNDLE/'release/bin/cpu_prefetch_runner',a)
                context=dict(archive_bundle_root=str(BUNDLE),source_revision='b'*40,
                    release_artifact_path=worker['path'],release_artifact_size_bytes=worker['size_bytes'],
                    release_artifact_sha256=worker['sha256'],inventory_sha256=a.ORIGINAL_INVENTORY_SHA,
                    archive_profile_binding=dict(r.existing_binding(BUNDLE/r.PROFILE_MEMBER,a),path=r.PROFILE_MEMBER))
                validation=types.SimpleNamespace(resolutions={'S17-EXT-006':types.SimpleNamespace(semantic_context=context)})
                controller=types.SimpleNamespace(qualified_archive_profile=lambda *args,**kwargs:None)
                with patch.object(r,'E25',root),patch.object(r,'qualify',return_value=validation), \
                     patch.object(a,'_prefix',side_effect=a.AdmissionError('prefix proof rejected') if reject else None) as prefix:
                    if reject:
                        with self.assertRaisesRegex(a.AdmissionError,'prefix proof rejected'):
                            r.render(spec,ROOT,a,controller)
                        self.assertFalse((root/'output').exists())
                    else:
                        result=r.render(spec,ROOT,a,controller)
                        self.assertEqual(result['status'],'AUTHORED_NOT_REGISTERED')
                        self.assertFalse(result['namespace_collision_audit_performed'])
                        self.assertEqual(set(result['outputs']),{'plan.json','namespace_registry.json','compatibility.json'})
                        for name,binding in result['outputs'].items():
                            self.assertEqual(r.existing_binding(root/'output'/name,a),binding)
                            raw=(root/'output'/name).read_bytes()
                            self.assertEqual(raw,a.canonical(a._json(raw)));self.assertFalse(raw.endswith(b'\n'))
                        plan=a._json((root/'output/plan.json').read_bytes())
                        ns=a._json((root/'output/namespace_registry.json').read_bytes())
                        self.assertEqual(ns['plan_sha256'],result['outputs']['plan.json']['sha256'])
                        self.assertEqual(len(ns['phase_identities']),1062)
                        self.assertEqual(plan['continuation']['compatibility_manifest'],result['outputs']['compatibility.json'])
                    prefix.assert_called_once()

    def test_qualification_receives_actual_archive_and_sidecar_no_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);archive=root/'archive';archive.write_bytes(b'original')
            sidecar=root/'archive.sha256';sidecar.write_bytes(b'actual sidecar')
            spec=dict(qualification=dict(evidence_root=str(root),journal=str(root/'journal.json'),journal_directory=str(root/'journal'),
                pilot_archive=r.existing_binding(archive,a),pilot_sidecar=r.existing_binding(sidecar,a)))
            calls=[]
            def journal(**kw):calls.append(kw);raise ValueError('real journal seam')
            controller=types.SimpleNamespace(activate=lambda:None,support=types.SimpleNamespace(_now=lambda:'actual now'),
                previous=types.SimpleNamespace(journal_runtime=types.SimpleNamespace(validate_operational_journal=journal)))
            with self.assertRaisesRegex(ValueError,'real journal seam'):r.qualify(spec,ROOT,a,controller)
            self.assertEqual(calls[0]['pilot_archive'],archive);self.assertEqual(calls[0]['pilot_sidecar'],sidecar)
            self.assertIs(calls[0]['allow_synthetic_test_evidence'],False)
            archive.write_bytes(b'changed!')
            with self.assertRaises(a.AdmissionError):r.qualify(spec,ROOT,a,controller)
            self.assertEqual(len(calls),1)


if __name__=='__main__':unittest.main(verbosity=2)
