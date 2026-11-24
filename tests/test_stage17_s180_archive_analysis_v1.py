"""Actual CPFA inverse and independent joined output, synthetic originals only."""
import copy
from dataclasses import asdict,replace
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import struct
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_archive_analysis_v1 as analysis
import test_stage17_s180_capture_validation_v1 as primary
import test_stage17_s180_archive_broker_v1 as broker


def digest(raw):return hashlib.sha256(raw).hexdigest()


def worker(sender,args,profile,limits,cpu,mode,parent):
    try:
        os.setsid();os.sched_setaffinity(0,{cpu})
        resource.setrlimit(resource.RLIMIT_AS,(analysis.bounds.ANALYSIS_CHILD_AS,analysis.bounds.ANALYSIS_CHILD_AS))
        codec=analysis.load_codec(profile,deadline_ns=time.monotonic_ns()+45*10**9)
        if mode=='wrong_cpu':cpu=-1
        if mode=='wrong_as':resource.setrlimit(resource.RLIMIT_AS,(8*analysis.bounds.GIB,analysis.bounds.ANALYSIS_CHILD_AS))
        if mode=='expired':codec.deadline_ns=time.monotonic_ns()-1
        try:
            result=analysis.analyze_capture(codec=codec,decode_limits=limits,expected_cpu=cpu,expected_parent_pid=parent,**args)
            if mode=='repeat':
                args=dict(args,output_directory=args['output_directory'].with_name('duplicate'))
                try:analysis.analyze_capture(codec=codec,decode_limits=limits,expected_cpu=cpu,expected_parent_pid=parent,**args)
                except ValueError as error:result['second_job_rejected']=str(error);result['codec_failed']=codec.failed
                else:raise AssertionError('duplicate admitted')
            sender.send(dict(status='PASSED',result=result))
        except BaseException as error:
            sender.send(dict(status='REJECTED',reason=str(error),codec_failed=codec.failed,
                restored_as=list(resource.getrlimit(resource.RLIMIT_AS))))
    except BaseException as error:sender.send(dict(status='WORKER_ERROR',reason=repr(error)))
    finally:sender.close()


class ArchivedTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='s180-archived-analysis-software-',dir=Path(__file__).resolve().parents[1]/'build');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.original=self.root/'original';self.original.mkdir(mode=0o700)
        self.program=self.root/'program';self.program.mkdir(mode=0o700);self.archives=self.program/'archives';self.archives.mkdir(mode=0o700)
        self.scratch=self.root/'scratch';self.scratch.mkdir(mode=0o700)
        self.results=self.root/'results';self.results.mkdir(mode=0o700)
        self.fixture=primary.Fixture(self.original)
        codec=broker.ArchiveFixture(self.root);python=broker.image(sys.executable)
        codec.profile=replace(codec.profile,encoder_sha256=python.sha256)
        self.profile=analysis.runtime.RuntimeProfile(python,python,codec.profile,broker.qualified_closure())
        self.limits=codec.limits;self.encoder=codec;self.make_inventory()

    def make_inventory(self):
        f=self.fixture;inventory=[]
        for original in f.checkpoint['artifacts']:
            name=original['file_name'];data=(self.original/name).read_bytes();role=analysis.capture.checkpoint_contract.role_profile(0,name)
            phase='warmup' if '-warmup-' in name else 'measurement' if '-measurement-' in name else None
            run=f.capture['warmup_run_id' if phase=='warmup' else 'run_id'] if phase else None
            width=role.row_bytes(run);raw=width is not None;block=width*8192 if raw else analysis.archive.BYTE_BLOCK
            artifact_id=primary.PLAN+':'+name
            header=dict(schema_version=analysis.archive.HEADER_SCHEMA,policy_id=analysis.archive.POLICY_ID,
                codec_id=analysis.archive.RAW_CODEC if raw else analysis.archive.BYTE_CODEC,
                artifact_id=artifact_id,artifact_role=role.artifact_role,canonical_format=role.canonical_format,
                run_id=run,phase=phase,worker=role.worker(),canonical_size_bytes=len(data),canonical_sha256=digest(data),
                row_bytes=width if raw else None,row_count=len(data)//width if raw else None,block_size_bytes=block,
                block_count=(len(data)+block-1)//block,fallback_reason=None,
                implementation_profile_sha256=self.encoder.profile.implementation_profile_sha256,
                encoder_sha256=self.encoder.profile.encoder_sha256,zstd_library_sha256=self.encoder.profile.zstd_library_sha256,
                zstd_version='1.5.7',compression_level=3,worker_threads=1,window_log=22,checksum_flag=1,
                content_size_flag=1,dictionary_id_flag=0)
            wire=self.encoder.encode(data,header);archive_name=digest(artifact_id.encode())+'.cpfa'
            (self.archives/archive_name).write_bytes(wire)
            inventory.append(dict(artifact_id=artifact_id,logical={k:original[k] for k in ('file_name','size_bytes','sha256')},
                archive_name=archive_name,physical=dict(size_bytes=len(wire),sha256=digest(wire)),header=header,role=asdict(role)))
        checkpoint_bytes=analysis.archive.canonical(f.checkpoint)
        proof=dict(execution_ordinal=0,continuation_allowed=True,inverse_readback_performed=False,scientific_validity='NOT_ASSESSED',
            checkpoint=dict(file_name='s180-e0-checkpoint.json',size_bytes=len(checkpoint_bytes),sha256=digest(checkpoint_bytes)),artifacts=inventory)
        self.args=dict(program_root=self.program,scratch_root=self.scratch,output_directory=self.results/'capture-0',
            registry_proof=proof,checkpoint=copy.deepcopy(f.checkpoint),capture_row=copy.deepcopy(f.capture),entry=copy.deepcopy(f.entry),
            hardware=copy.deepcopy(f.hardware),master_seed_hex=primary.SEED,family_context_cleanup=copy.deepcopy(f.cleanup),
            plan_sha256=primary.PLAN,program_scope_sha256=primary.SCOPE,session_id=primary.SESSION,
            canonical_bytes_bound=sum(r['logical']['size_bytes'] for r in inventory),maximum_output_bytes=2*1024**2)

    def invoke(self,mode=None):
        context=multiprocessing.get_context('fork');receiver,sender=context.Pipe(duplex=False)
        cpu=min(os.sched_getaffinity(0));process=context.Process(target=worker,args=(sender,self.args,self.profile,self.limits,cpu,mode,os.getpid()))
        process.start();sender.close()
        try:
            self.assertTrue(receiver.poll(55),'actual inverse worker result deadline');result=receiver.recv();process.join(5)
            self.assertFalse(process.is_alive());self.assertEqual(process.exitcode,0)
        finally:
            if process.is_alive():process.kill();process.join(5)
            receiver.close();process.close()
        self.assertNotEqual(result['status'],'WORKER_ERROR',result)
        return result

    def test_every_original_is_reconstructed_then_both_phases_published_with_durable_archive_uris(self):
        before={p.name:p.read_bytes() for p in self.archives.iterdir()};result=self.invoke()
        self.assertEqual(result['status'],'PASSED',result)
        value=result['result'];self.assertEqual(value['original_archives_inversely_verified'],8)
        self.assertTrue(value['canonical_spool_removed']);self.assertFalse(value['original_archive_custody_verified'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.archives.iterdir()})
        self.assertTrue(all(p.name.endswith('.lock') for p in self.scratch.iterdir()))
        output=self.args['output_directory'];publication=json.loads((output/'complete.json').read_bytes())
        report=json.loads((output/'capture-validation.json').read_bytes())
        self.assertEqual(report['tail_numerics']['raw_accepted_count'],4)
        for phase in publication['joined']:
            raw=(output/phase['artifact']['file_name']).read_bytes();self.assertEqual(digest(raw),phase['artifact']['sha256'])
            for index,binding in enumerate(phase['raw_stream_envelopes']):
                envelope=json.loads((output/binding['file_name']).read_bytes());uri=envelope['storage']['artifact_uri']
                if index<2:
                    self.assertTrue(uri.startswith(self.archives.as_uri()+'/'));self.assertTrue(uri.endswith('.cpfa'))
                    self.assertEqual(envelope['compression'],analysis.archive.RAW_CODEC)
                else:self.assertEqual(uri,(output/phase['artifact']['file_name']).as_uri())

    def pending_input(self):
        self.args['registry_proof'].update(schema_version=analysis.analysis_input.SCHEMA,continuation_allowed=False,
            original_collection_release_verified=True,physical_sha256_verification_pending=True,
            independent_inverse_required=True,execution_authority=False,phase18_authority=False)

    def test_pending_input_requires_actual_complete_inverse_before_publication(self):
        self.pending_input();result=self.invoke()
        self.assertEqual(result['status'],'PASSED',result)
        self.assertEqual(result['result']['original_archives_inversely_verified'],8)
        self.assertTrue((self.args['output_directory']/'complete.json').exists())

    def test_pending_payload_damage_is_rejected_by_actual_inverse_and_keeps_evidence(self):
        self.pending_input();path=self.archives/self.args['registry_proof']['artifacts'][-1]['archive_name']
        data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        result=self.invoke();self.assertEqual(result['status'],'REJECTED',result)
        self.assertTrue(result['codec_failed']);self.assertFalse((self.args['output_directory']/'complete.json').exists())
        self.assertTrue(any(p.is_dir() for p in self.scratch.iterdir()));self.assertEqual(path.read_bytes(),data)

    def test_pending_proof_cannot_disable_inverse_or_claim_native_continuation(self):
        self.pending_input();self.args['registry_proof']['independent_inverse_required']=False
        result=self.invoke();self.assertEqual(result['status'],'REJECTED',result)
        self.assertFalse(self.args['output_directory'].exists())

    def test_all_full_is_valid_data_with_empty_derived_output_and_undefined_tail(self):
        self.fixture=primary.Fixture(self.original,all_full=True);self.make_inventory();result=self.invoke()
        self.assertEqual(result['status'],'PASSED',result)
        report=json.loads((self.args['output_directory']/'capture-validation.json').read_bytes())
        self.assertFalse(report['measurement_zero_loss']);self.assertEqual(report['tail_numerics']['raw_accepted_count'],0)
        self.assertTrue(all(r['joined_size_bytes']==0 for r in report['phases']))

    def test_corrupt_last_archive_keeps_failed_spool_and_originals(self):
        path=self.archives/self.args['registry_proof']['artifacts'][-1]['archive_name'];data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        result=self.invoke();self.assertEqual(result['status'],'REJECTED',result);self.assertTrue(result['codec_failed'])
        roots=[p for p in self.scratch.iterdir() if p.is_dir()];self.assertEqual(len(roots),1)
        self.assertTrue((roots[0]/'reservation.json').exists());self.assertTrue(any(p.suffix=='.bin' for p in roots[0].iterdir()))
        self.assertEqual(path.read_bytes(),data);self.assertFalse(self.args['output_directory'].exists())
        self.assertEqual(result['restored_as'],[analysis.bounds.ANALYSIS_CHILD_AS]*2)

    def test_lossless_but_invalid_primary_fails_and_keeps_canonical_evidence(self):
        reference=self.fixture.control['phases'][0]['producer'];path=self.original/reference['file_name']
        data=bytearray(path.read_bytes());prefix=analysis.archive.row_layout(self.fixture.capture['warmup_run_id'])[0]
        struct.pack_into('<Q',data,prefix,99);path.write_bytes(data);reference['sha256']=digest(data)
        self.fixture.refresh();self.make_inventory();result=self.invoke()
        self.assertEqual(result['status'],'REJECTED',result);self.assertTrue(result['codec_failed'])
        self.assertTrue(any(p.is_dir() for p in self.scratch.iterdir()))
        self.assertTrue((self.args['output_directory']/'failure.json').exists())

    def test_foreign_checkpoint_inventory_missing_role_and_small_bound_are_rejected(self):
        original=copy.deepcopy(self.args)
        for change in ('checkpoint','role','missing','bound'):
            self.args=copy.deepcopy(original)
            if change=='checkpoint':self.args['registry_proof']['checkpoint']['sha256']='f'*64
            if change=='role':self.args['registry_proof']['artifacts'][0]['role']['artifact_role']='FOREIGN'
            if change=='missing':self.args['registry_proof']['artifacts'].pop()
            if change=='bound':self.args['canonical_bytes_bound']=1
            result=self.invoke();self.assertEqual(result['status'],'REJECTED',result);self.assertTrue(result['codec_failed'])
            self.assertFalse(self.args['output_directory'].exists())

    def test_actual_cpu_limits_and_original_deadline_are_required(self):
        for mode in ('wrong_cpu','wrong_as','expired'):
            result=self.invoke(mode);self.assertEqual(result['status'],'REJECTED',result);self.assertTrue(result['codec_failed'])
            self.assertFalse(self.args['output_directory'].exists())

    def test_coherently_reencoded_foreign_header_run_cannot_relabel_original_bytes(self):
        row=self.args['registry_proof']['artifacts'][0]
        row['header']['run_id']='Z'*len(row['header']['run_id'].encode())
        wire=self.encoder.encode((self.original/row['logical']['file_name']).read_bytes(),row['header'])
        (self.archives/row['archive_name']).write_bytes(wire)
        row['physical']=dict(size_bytes=len(wire),sha256=digest(wire))
        result=self.invoke();self.assertEqual(result['status'],'REJECTED',result)
        self.assertTrue(result['codec_failed']);self.assertFalse(self.args['output_directory'].exists())

    def test_existing_output_is_never_adopted_and_decoded_failure_stays(self):
        output=self.args['output_directory'];output.mkdir(mode=0o700);foreign=output/'foreign';foreign.write_bytes(b'keep')
        result=self.invoke();self.assertEqual(result['status'],'REJECTED',result)
        self.assertEqual(foreign.read_bytes(),b'keep');self.assertTrue(any(p.is_dir() for p in self.scratch.iterdir()))

    def test_repeated_original_capture_is_rejected_without_second_publication(self):
        result=self.invoke('repeat');self.assertEqual(result['status'],'PASSED',result)
        self.assertIn('already consumed',result['result']['second_job_rejected']);self.assertTrue(result['result']['codec_failed'])
        self.assertFalse((self.results/'duplicate').exists())


if __name__=='__main__':unittest.main()
