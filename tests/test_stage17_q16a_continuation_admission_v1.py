"""D240 independent metadata admission tests using actual D220 byte fixtures.

Synthetic report/ledger construction here establishes software behavior only.
It is never a qualification context or a claim of 177 collected captures.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_q16a_continuation_admission_v1 as admission
from test_stage17_q16a_capture_validation_v1 import Fixture


def save(path,document):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=admission.canonical(document);path.write_bytes(data)
    return dict(path=str(path),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def name_binding(binding):return dict(file_name=Path(binding['path']).name,size_bytes=binding['size_bytes'],sha256=binding['sha256'])


class CaptureEvidence:
    def __init__(self,root,full=False):
        self.root=root;raw=root/'raw';raw.mkdir()
        f=Fixture(raw,full=full);self.report=f.run()
        self.parent={'captures':[dict(capture=f.capture,resources=f.resources)]}
        self.scope='e'*64;self.family=root/'program/working'/admission.contract.PARENT_SHA256
        self.ledger=root/'program/ledger';self.family.mkdir(parents=True);self.ledger.mkdir()
        logical=[];headers=[];names=admission.registry.capture_names('Q16a',0)
        for name in names:
            phase=next((p for p in ('warmup','measurement') if '-'+p+'-' in name),None)
            owner=next((p for p in ('producer','consumer') if '-'+p in name),None)
            if phase:
                role=owner+('_demand' if '-demand' in name else '')
                data=(raw/f'{phase}-{role}.bin').read_bytes()
            else:data=admission.canonical(f.control)
            digest=hashlib.sha256(data).hexdigest()
            logical.append(dict(file_name=name,size_bytes=len(data),sha256=digest))
            headers.append(dict(artifact_id=admission.contract.PARENT_SHA256+':'+name,canonical_sha256=digest,
                canonical_size_bytes=len(data),phase=phase,run_id=f.capture[phase]['run_id'] if phase else None,worker=owner))
        cp=dict(schema_version=admission.checkpoint.SCHEMA,action_id='Q16a',plan_sha256=admission.contract.PARENT_SHA256,
            capture_ordinal=0,capture_identity=dict(warmup_run_id=f.capture['warmup']['run_id'],measurement_run_id=f.capture['measurement']['run_id'],hardware_state=f.capture['hardware_state']),
            native_complete=True,native_result_after_cleanup=f.final,artifacts=logical,scientific_validity='NOT_ASSESSED',execution_authority=False)
        cpbinding=save(self.family/'formal-capture-0-final-checkpoint.json',cp)
        artifacts=[];verified=[];release_bindings=[]
        for sequence,(row,header) in enumerate(zip(logical,headers,strict=True),1):
            aid=header['artifact_id'];archive_name=hashlib.sha256(aid.encode()).hexdigest()+'.cpfa';physical=dict(size_bytes=123,sha256='f'*64)
            released=save(self.ledger/f'{sequence:016d}.json',dict(kind='RELEASED',artifact_id=aid,sequence=sequence,payload=dict(header=header,physical=physical,archive_name=archive_name,checkpoint_sha256=cpbinding['sha256'])))
            release_bindings.append(released)
            common=dict(artifact_id=aid,logical=row,physical=physical,archive_name=archive_name,released_record=name_binding(released))
            artifacts.append(dict(common,expected_logical=row,failure_receipt=None))
            verified.append(dict(common,header=header,role=vars(admission.archive_registry.role_profile('Q16a',row['file_name']))))
        receipt=dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',capture_ordinal=0,
            plan_sha256=admission.contract.PARENT_SHA256,program_scope_sha256=self.scope,checkpoint=name_binding(cpbinding),
            status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False,
            artifacts=artifacts,ledger_tip=name_binding(release_bindings[-1]))
        receiptbinding=save(self.family/'formal-capture-0-archive-custody.json',receipt)
        save(self.ledger/'0000000000000010.json',dict(kind='CUSTODY_RECEIPT',previous_sha256=receipt['ledger_tip']['sha256'],payload=dict(family_id=admission.contract.PARENT_SHA256,checkpoint_sha256=cpbinding['sha256'],receipt=name_binding(receiptbinding))))
        reportbinding=save(root/'reports/capture-0.json',self.report)
        self.row=dict(original_ordinal=0,context_ordinal=0,repetition_ordinal=0,checkpoint_binding=cpbinding,custody_binding=receiptbinding,validation_report_binding=reportbinding)
        self.authenticated=dict(capture_ordinal=0,checkpoint=name_binding(cpbinding),custody_receipt=name_binding(receiptbinding),artifacts=verified,native_result_after_cleanup=f.final,execution_authority=False)

    def validate(self):
        reader=admission.BoundReader()
        result=admission._capture_record(self.row,self.authenticated,self.parent,self.scope,reader)
        reader.finish();return result


class CompatibilityEvidence:
    """Synthetic source bytes; strict machine gate is tested separately."""
    def __init__(self,root):
        self.plan=dict(source_revision='b'*40,continuation=dict(monitor_path_replacements=[]))
        self.document=dict(schema_version=admission.COMPATIBILITY_SCHEMA,monitor_path_replacements=[],execution_authority=False)
        self.indices={};self.paths={}
        names=set(admission.codegen.SOURCE_PATHS)|{'tools/check_formal_codegen.py','include/cpu_prefetch/private_extra.hpp'}
        for side in ('original','continuation'):
            r=root/side;rows=[]
            def write(name,data):
                p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
                binding=dict(path=str(p),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
                rows.append(dict(binding,path=name));return binding
            for name in names:
                data=name.encode()+ (b' cold change' if side=='continuation' and name==admission.COLD_SOURCE else b'')
                write(name,data)
            worker=write('release/bin/cpu_prefetch_runner',b'fake worker '+side.encode())
            report=write('build-provenance/formal_codegen_report.json',b'{"synthetic":true}')
            index=save(r/'BUNDLE_INVENTORY.json',dict(files=rows))
            self.indices[side]={v['path']:dict(v,path=str(r/v['path'])) for v in rows};self.paths[side]=r
            self.document[side]=dict(source_revision=admission.contract.PARENT_SOURCE if side=='original' else self.plan['source_revision'],
                bundle_root=str(r),worker=worker,formal_codegen=report,bundle_inventory=index)
        self.document['measured_sources']=[];self.document['cold_source_changes']=[]
        for name in sorted(names):
            row=dict(relative_path=name,original=self.indices['original'][name],continuation=self.indices['continuation'][name])
            self.document['cold_source_changes' if name==admission.COLD_SOURCE else 'measured_sources'].append(row)
        new=self.document['continuation'];self.context=dict(archive_bundle_root=new['bundle_root'],source_revision=new['source_revision'],
            release_artifact_path=new['worker']['path'],release_artifact_size_bytes=new['worker']['size_bytes'],
            release_artifact_sha256=new['worker']['sha256'],inventory_sha256=new['bundle_inventory']['sha256'])

    def validate(self):
        old=self.document['original'];reader=admission.BoundReader()
        with patch.multiple(admission,ORIGINAL_WORKER_SHA=old['worker']['sha256'],ORIGINAL_WORKER_SIZE=old['worker']['size_bytes'],
                            ORIGINAL_CODEGEN_SHA=old['formal_codegen']['sha256'],ORIGINAL_INVENTORY_SHA=old['bundle_inventory']['sha256']), \
             patch.object(admission.codegen,'validate_report_bindings') as gate:
            result=admission._compatibility(self.document,self.plan,self.context,reader)
            self.calls=gate.call_count;reader.finish();return result


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='d240-admission-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_actual_d220_report_and_original_checkpoint_custody(self):
        fixture=CaptureEvidence(self.root)
        result=fixture.validate()
        self.assertEqual(result['full_counts'],[0,0])
        self.assertEqual(set(result['tails']),{'producer','consumer'})

    def test_valid_full_is_not_relabelled_invalid_or_zero_loss(self):
        fixture=CaptureEvidence(self.root,full=True)
        result=fixture.validate()
        self.assertGreater(sum(result['full_counts']),0)
        self.assertFalse(fixture.report['zero_loss_all_phases'])

    def test_mutated_report_binding_identity_or_original_stream_rejected(self):
        fixture=CaptureEvidence(self.root)
        for mutation in (lambda r:r.update(capture_ordinal=1),
                         lambda r:r['phases'][1].update(run_id='wrong-run'),
                         lambda r:r['phases'][1]['stream_sha256'].update(producer='0'*64),
                         lambda r:r.update(raw_reconciliation_validated=False),
                         lambda r:r['phases'][1]['counts'].update(consumed_including_drain=0)):
            report=copy.deepcopy(fixture.report);mutation(report)
            fixture.row['validation_report_binding']=save(self.root/'reports/capture-0.json',report)
            with self.subTest(mutation=mutation),self.assertRaises((admission.contract.ContractError,admission.calibration.CalibrationError)):
                fixture.validate()

    def test_missing_or_tampered_checkpoint_and_custody_rejected(self):
        fixture=CaptureEvidence(self.root)
        binding=fixture.row['checkpoint_binding'];original=Path(binding['path']).read_bytes()
        Path(binding['path']).write_bytes(original.replace(b'"native_complete":true',b'"native_complete":null'))
        with self.assertRaises(admission.AdmissionError):fixture.validate()
        Path(binding['path']).write_bytes(original)
        Path(fixture.row['custody_binding']['path']).unlink()
        with self.assertRaises(OSError):fixture.validate()

    def test_archive_phase_or_run_cannot_be_swapped(self):
        fixture=CaptureEvidence(self.root)
        fixture.authenticated['artifacts'][0]['header']['run_id']='other-run'
        with self.assertRaises(admission.AdmissionError):fixture.validate()

    def test_failed_boundary_requires_unreleased_phases_and_empty_original_streams(self):
        fixture=CaptureEvidence(self.root)
        cp=json.loads(Path(fixture.row['checkpoint_binding']['path']).read_bytes())
        receipt=json.loads(Path(fixture.row['custody_binding']['path']).read_bytes())
        cp['capture_ordinal']=receipt['capture_ordinal']=177;cp['native_complete']=False
        cp['native_result_after_cleanup']['stop']=10
        capture=copy.deepcopy(fixture.parent['captures'][0]['capture']);capture['ordinal']=177
        for row in cp['artifacts']:
            row['file_name']=row['file_name'].replace('q16a-c0-','q16a-c177-')
            if row['file_name'].endswith('.bin'):row.update(size_bytes=0,sha256=hashlib.sha256(b'').hexdigest())
        for phase in cp['native_result_after_cleanup']['session']['phases']:
            for k in ('released','before_observed','during_observed','after_observed','validated'):phase[k]=False
            for k in ('observed_origin','origin_sample','origin_status','window','drain_checkpoint'):phase[k]=None
            for owner,keys in (('producer',('attempted','accepted','full')),('consumer',('polls','consumed_including_drain','empty'))):
                for key in keys:phase[owner][key]=0
        cpbinding=save(fixture.family/'formal-capture-177-final-checkpoint.json',cp)
        receipt['checkpoint']=name_binding(cpbinding)
        for row,logical in zip(receipt['artifacts'],cp['artifacts'],strict=True):row['logical']=row['expected_logical']=logical
        receiptbinding=save(fixture.family/'formal-capture-177-archive-custody.json',receipt)
        boundary=dict(original_ordinal=177,checkpoint=cpbinding,custody_receipt=receiptbinding,zero_raw_observations=True,
            both_phases_unreleased=True,physical_custody_verified=True,inverse_readback_performed=True)
        parent=dict(captures=[None]*177+[dict(capture=capture)],storage=dict(program_scope_sha256=fixture.scope))
        admission._failure_boundary(dict(failed_boundary=boundary),parent,admission.BoundReader())
        for mutation in (lambda c:c['native_result_after_cleanup']['session']['phases'][0].update(released=True),
                         lambda c:c['native_result_after_cleanup']['session']['phases'][1]['consumer'].update(polls=1),
                         lambda c:c['native_result_after_cleanup']['session']['phases'][0].update(observed_origin=123)):
            bad=copy.deepcopy(cp);mutation(bad);boundary['checkpoint']=save(Path(cpbinding['path']),bad)
            modified=copy.deepcopy(receipt);modified['checkpoint']=name_binding(boundary['checkpoint'])
            boundary['custody_receipt']=save(Path(receiptbinding['path']),modified)
            with self.subTest(mutation=mutation),self.assertRaises(admission.AdmissionError):
                admission._failure_boundary(dict(failed_boundary=boundary),parent,admission.BoundReader())

    def test_bound_reader_duplicates_symlinks_and_mutation(self):
        p=self.root/'record.json';p.write_bytes(b'{"a":1,"a":2}')
        b=dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        with self.assertRaises(admission.AdmissionError):admission.BoundReader().document(b)
        p.write_bytes(b'{}');b.update(size_bytes=2,sha256=hashlib.sha256(b'{}').hexdigest())
        reader=admission.BoundReader();reader.document(b);p.write_bytes(b'[]')
        with self.assertRaises(admission.AdmissionError):reader.finish()
        link=self.root/'link.json';link.symlink_to(p);b['path']=str(link)
        with self.assertRaises(admission.AdmissionError):admission.BoundReader().read(b)

    def test_reader_limits_reject_before_unbounded_io(self):
        p=self.root/'record.json';b=save(p,{})
        reader=admission.BoundReader();reader.total=admission.MAX_TOTAL_BYTES
        with self.assertRaises(admission.AdmissionError):reader.read(b)
        b['size_bytes']=admission.MAX_FILE_BYTES+1
        with self.assertRaises(admission.AdmissionError):admission.BoundReader().read(b)

    def test_boolean_compatibility_or_unbound_current_context_rejected(self):
        for doc in (True,dict(compatible=True),dict(schema_version=admission.COMPATIBILITY_SCHEMA,compatible=True)):
            with self.subTest(doc=doc),self.assertRaises(admission.AdmissionError):
                admission._compatibility(doc,{}, {}, admission.BoundReader())
        with self.assertRaises(admission.AdmissionError):admission.validate({'continuation':{}},{})

    def test_compatibility_exact_closure_and_both_machine_gates(self):
        fixture=CompatibilityEvidence(self.root)
        fixture.validate();self.assertEqual(fixture.calls,2)
        names={r['relative_path'] for r in fixture.document['measured_sources']}
        self.assertIn('include/cpu_prefetch/private_extra.hpp',names)
        self.assertIn('src/runner/stage17_fixed_action.cpp',names)

    def test_new_inventory_must_match_authenticated_context(self):
        fixture=CompatibilityEvidence(self.root);fixture.context['inventory_sha256']='0'*64
        with self.assertRaisesRegex(admission.AdmissionError,'authenticated qualified inventory'):fixture.validate()

    def test_no_omitted_dependency_extra_cold_exception_or_changed_source(self):
        fixture=CompatibilityEvidence(self.root)
        baseline=copy.deepcopy(fixture.document)
        for mutate in (lambda d:d['measured_sources'].pop(),
                       lambda d:d['cold_source_changes'].append(d['measured_sources'][0]),
                       lambda d:d['measured_sources'][0]['continuation'].update(sha256='0'*64)):
            fixture.document=copy.deepcopy(baseline);mutate(fixture.document)
            with self.subTest(mutate=mutate),self.assertRaises(admission.AdmissionError):fixture.validate()

    def test_fixed_strict_codegen_requires_both_disassemblers(self):
        with self.assertRaises(admission.codegen.AuditError):
            admission.codegen.validate_report_bindings(dict(schema_version=admission.codegen.SCHEMA,status='PASS',missing_tools=['LLVM_OBJDUMP']),binary=self.root/'missing',source_root=self.root)

    def test_prefix_coverage_rejects_missing_or_duplicate_before_file_reads(self):
        fields='schema_version status method_id parent_plan failed_family_receipt original_plan_sha256 original_failure_sha256 original_source_revision worker_sha256 original_authority program_scope_sha256 program_root_binding ledger_head contexts required_count records validator_source_files failed_boundary retained_failure_restoration_verified analysis_limits authenticated_custody analysis_operator original_analysis_operator qualified_policy family_validity_established execution_authority phase18_authority'
        p=dict.fromkeys(fields.split());plan=dict(continuation=dict(parent_plan={},failed_family_receipt={}));parent=dict(storage=dict(program_scope_sha256='e'*64))
        p.update(schema_version=admission.PREFIX_SCHEMA,status='VALIDATED',method_id=admission.contract.ring.METHOD,parent_plan={},failed_family_receipt={},original_plan_sha256=admission.contract.PARENT_SHA256,original_failure_sha256=admission.contract.FAILURE_SHA256,original_source_revision=admission.contract.PARENT_SOURCE,worker_sha256=admission.ORIGINAL_WORKER_SHA,program_scope_sha256='e'*64,contexts=[0,1,2],required_count=177,retained_failure_restoration_verified=True,family_validity_established=False,execution_authority=False,phase18_authority=False)
        for ordinals in (range(176),[0]*177):
            p['records']=[dict(original_ordinal=i) for i in ordinals]
            with self.assertRaises(admission.AdmissionError):admission._prefix(p,parent,{},plan,admission.BoundReader(),'',{})


if __name__=='__main__':unittest.main()
