"""Real codecs, ledger, checkpoint and scientific report on synthetic streams."""
from dataclasses import asdict
import copy
import hashlib
import pathlib
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_service_prefix_admission_v1 as current
from test_stage17_formal_service_capture_validation_v1 import Fixture as Capture
from test_stage17_formal_archive_v1 import ArchiveFixture,codec_limit,digest


class PrefixCaptureTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=pathlib.Path(temp.name);raw=self.base/'raw';raw.mkdir()
        capture=Capture(raw);report=capture.run()
        self.capture=capture
        self.root=self.base/'program';c=current.custody;a=current.archive
        scope=c.ProgramStore.initialize(self.root,program_id='synthetic-d260',storage_domain_id='synthetic-domain',prospective_admission_sha256='c'*64)
        codec=self.base/'codec';codec.mkdir();self.codec=ArchiveFixture(codec)
        limits=c.CustodyLimits(131072,1024,4096,131072,time.monotonic_ns()+60*10**9)
        self.store=c.ProgramStore(self.root,scope_sha256=scope,family_id=current.contract.PARENT_SHA256,limits=limits)
        self.store.__enter__();self.addCleanup(self.store.__exit__,None,None,None)
        working=self.store.prepare_family(current.contract.PARENT_SHA256)
        data=[]
        for i,phase in enumerate(('warmup','measurement')):
            for role in ('producer','consumer'):
                data.append((raw/capture.control['phases'][i][role]['file_name']).read_bytes())
        data.extend([(raw/capture.control['node_order']['file_name']).read_bytes(),a.canonical(capture.control)])
        sources=[];encoded=[]
        for name,payload in zip(current.capture_registry.capture_names('Q16b',0),data,strict=True):
            role=current.capture_registry.role_profile('Q16b',name)
            phase=next((v for v in ('warmup','measurement') if '-'+v+'-' in name),None)
            worker=next((v for v in ('producer','consumer') if '-'+v in name),None)
            run=capture.capture[phase]['run_id'] if phase else None
            header,_=self.codec.header(payload,role.layout);width=role.row_bytes(run)
            header.update(artifact_id=current.contract.PARENT_SHA256+':'+name,artifact_role=role.artifact_role,
                canonical_format=role.canonical_format,phase=phase,run_id=run,worker=worker,row_bytes=width,
                row_count=len(payload)//width if width else None,block_size_bytes=8192*width if width else a.BYTE_BLOCK)
            (working/name).write_bytes(payload)
            sources.append(c.SourceBinding(header['artifact_id'],c.BoundFile(name,len(payload),digest(payload)),a.PhysicalBinding(len(payload),digest(payload)),None))
            encoded.append((header,role,self.codec.encode(payload,header)))
        cp=dict(schema_version=current.checkpoint.SCHEMA,action_id='Q16b',plan_sha256=current.contract.PARENT_SHA256,
            capture_ordinal=0,capture_identity=dict(warmup_run_id=capture.capture['warmup']['run_id'],
            measurement_run_id=capture.capture['measurement']['run_id'],hardware_state=capture.capture['hardware_state']),
            native_result_after_cleanup=capture.final,artifacts=[asdict(s.expected) for s in sources],
            native_complete=True,scientific_validity='NOT_ASSESSED',execution_authority=False)
        cp_bytes=a.canonical(cp);cp_binding=c.BoundFile('formal-capture-0-final-checkpoint.json',len(cp_bytes),digest(cp_bytes));(working/cp_binding.file_name).write_bytes(cp_bytes)
        def verify(doc,sources):
            current.checkpoint.validate_checkpoint(doc,action='Q16b',plan_sha256=current.contract.PARENT_SHA256,capture=capture.capture,sources=sources)
        self.store.begin_capture(cp_binding,tuple(sources),verify_checkpoint=verify)
        for source,(header,role,wire) in zip(sources,encoded,strict=True):
            stem=hashlib.sha256(source.artifact_id.encode()).hexdigest();staging=self.store.reserve_archive(source.artifact_id,staging_name=stem+'.staging',maximum_archive_bytes=len(wire)+4096);staging.write_bytes(wire)
            with codec_limit():
                self.store.verify_and_publish(source.artifact_id,archive_name=stem+'.cpfa',expected_header=header,role=role,physical=a.PhysicalBinding(len(wire),digest(wire)),profile=self.codec.profile,limits=self.codec.limits)
                self.store.release_working_copy(source.artifact_id,profile=self.codec.profile,limits=self.codec.limits)
        rows=[]
        for source in sources:
            r=self.store._states[source.artifact_id];rows.append(dict(logical=asdict(source.expected),expected_logical=asdict(source.expected),failure_receipt=None,artifact_id=source.artifact_id,released_record=asdict(self.store.ledger_binding(r)),archive_name=r['payload']['archive_name'],physical=r['payload']['physical']))
        receipt=dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',program_scope_sha256=scope,plan_sha256=current.contract.PARENT_SHA256,capture_ordinal=0,checkpoint=asdict(cp_binding),ledger_tip=asdict(self.store.ledger_binding()),artifacts=rows,status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False)
        receipt_binding=self.store.retain_custody_receipt('formal-capture-0-archive-custody.json',a.canonical(receipt))
        authenticated=current.capture_registry.verify_capture_metadata(store=self.store,action='Q16b',capture=capture.capture,checkpoint_binding=asdict(cp_binding),receipt_binding=asdict(receipt_binding),decoder_profile=self.codec.profile,decoder_limits=self.codec.limits)
        self.parent=dict(captures=[dict(capture=capture.capture,resources=capture.resources)],storage=dict(program_scope_sha256=scope))
        self.row=dict(original_ordinal=0,checkpoint=asdict(cp_binding),custody_receipt=asdict(receipt_binding),verified_custody=self.save('verified.json',authenticated),scientific_report=self.save('report.json',report))

    def save(self,name,document):
        raw=current.archive.canonical(document);p=self.base/name;p.write_bytes(raw)
        return dict(path=str(p),size_bytes=len(raw),sha256=digest(raw))

    def verify(self):
        reader=current.admission.BoundReader()
        current._capture(reader,self.row,self.parent,self.root);reader.finish()

    def test_real_original_custody_and_independent_report_pass_without_writing(self):
        before={str(p):digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}
        self.verify()
        self.assertEqual(before,{str(p):digest(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()})

    def test_actual_archive_corruption_is_rejected(self):
        path=next((self.root/'archives').glob('*.cpfa'));data=path.read_bytes();path.write_bytes(data[:-1]+bytes([data[-1]^1]))
        with self.assertRaises(current.admission.AdmissionError):self.verify()

    def test_changed_report_raw_binding_is_rejected_even_when_rebound(self):
        p=pathlib.Path(self.row['scientific_report']['path']);report=current.admission._json(p.read_bytes());report['phases'][0]['stream_sha256']['producer']='0'*64
        self.row['scientific_report']=self.save('report.json',report)
        with self.assertRaises(current.admission.AdmissionError):self.verify()

    def test_missing_receipt_cannot_be_replaced_by_completion_flag(self):
        phase=self.root/'working'/current.contract.PARENT_SHA256
        (phase/self.row['custody_receipt']['file_name']).unlink()
        with self.assertRaises((OSError,current.admission.AdmissionError)):self.verify()

    def test_bound_native_checkpoint_corruption_is_rejected(self):
        phase=self.root/'working'/current.contract.PARENT_SHA256
        p=phase/self.row['checkpoint']['file_name'];p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(current.admission.AdmissionError):self.verify()


if __name__=='__main__':unittest.main()
