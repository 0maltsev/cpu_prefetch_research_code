"""Real bounded cold child processes; synthetic local custody only."""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from test_stage17_formal_archive_v1 import codec_limit,digest
from test_stage17_formal_archive_custody_v1 import CustodyFixture
import stage17_formal_archive_v1 as a
import stage17_formal_archive_custody_v1 as c
import stage17_formal_archive_runtime_v1 as r

TOOLS=Path(__file__).resolve().parents[1]/"tools"
MODULES=("stage17_formal_archive_runtime_v1","stage17_formal_archive_custody_v1","stage17_formal_archive_v1",
         "stage17_raw_stream_decoder_v1","check_canonical","stage17_process_group_supervisor_v3",
         "stage17_process_group_supervisor_v2","stage17_process_group_supervisor_v1")


def image(path):
    path=Path(path).resolve()
    return r.ImageBinding(path,path.stat().st_size,digest(path.read_bytes()))


class ArchiveRuntimeTests(unittest.TestCase):
    encoder:Path|None=None

    def setUp(self):
        if self.encoder is None:self.skipTest("requires --encoder actual compiled binary")
        capacity=mock.patch("os.statvfs",return_value=SimpleNamespace(f_bavail=7_000_000_000_000,f_frsize=1,f_favail=100000))
        capacity.start()
        self.addCleanup(capacity.stop)
        self.temp=tempfile.TemporaryDirectory(prefix="d233-runtime-test-")
        self.addCleanup(self.temp.cleanup)
        self.f=CustodyFixture(self.temp.name)
        self.f.f.profile=replace(self.f.f.profile,encoder_sha256=image(self.encoder).sha256)
        self.f.header["encoder_sha256"]=self.f.f.profile.encoder_sha256
        self.profile=r.RuntimeProfile(image(self.encoder),image(sys.executable),self.f.f.profile,
            tuple(r.ModuleBinding(name,image(TOOLS/(name+".py"))) for name in MODULES))
        self.limits=r.RuntimeLimits(2*1024**3,2*1024**3,65536,65536,65536,1_500_000_000,
                                   time.monotonic_ns()+60_000_000_000,time.monotonic_ns()+60_000_000_000,30)
        native=dict(window_log=22,maximum_header_bytes=16384,maximum_decoded_block_bytes=8*1024**2,
            maximum_encoded_block_bytes=8*1024**2,maximum_archive_bytes=64*1024**2,
            maximum_observed_context_bytes=64*1024**2,io_chunk_bytes=1024*1024,maximum_io_calls=100000,
            deadline_monotonic_ns=self.limits.final_deadline_ns)
        self.job=r.ArchiveJob(self.f.artifact_id,self.f.header,self.f.role,native,self.f.f.limits)

    def runtime(self,store,**changes):
        store.prepare_family(self.f.family)
        return r.ColdArchiveRuntime(store,profile=self.profile,limits=replace(self.limits,**changes))

    def profile_document(self):
        root=TOOLS.parent
        def binding(item,location):
            base=root if location=="bundle" else Path("/")
            return dict(location=location,path=str(item.path.relative_to(base)),size_bytes=item.size_bytes,sha256=item.sha256)
        return dict(schema_version="cpu-prefetch-formal-archive-implementation-profile/1",policy_id=a.POLICY_ID,
            encoder=binding(self.profile.encoder,"bundle"),python=binding(self.profile.python,"runtime"),
            zstd_library=binding(image(self.profile.decoder.zstd_library_path),"runtime"),
            source_closure=[dict(module=m.module,image=binding(m.image,"bundle")) for m in self.profile.source_closure],
            options=dict(zstd_version="1.5.7",compression_level=3,worker_threads=1,nbWorkers=0,window_log=22,
                         checksum_flag=1,content_size_flag=1,dictionary_id_flag=0))

    def load_profile(self,document):
        path=Path(self.temp.name)/"implementation-profile.json"
        raw=a.canonical(document)
        path.write_bytes(raw)
        return r.load_runtime_profile(path,expected=a.PhysicalBinding(len(raw),digest(raw)),bundle_root=TOOLS.parent,
            runtime_root=Path("/"),max_profile_bytes=65536,deadline_ns=self.limits.final_deadline_ns)

    def test_actual_encoder_sealed_decoder_publication_release_receipt(self):
        self.profile=self.load_profile(self.profile_document())
        self.f.header["implementation_profile_sha256"]=self.profile.decoder.implementation_profile_sha256
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            result=runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)
            self.assertEqual(result.status,"ARCHIVED_AND_RELEASED")
            self.assertEqual(runtime.child_count,3)
            self.assertFalse(self.f.original.exists())
            receipt=json.loads((self.f.working/result.receipt.file_name).read_bytes())
            self.assertEqual(receipt["program_scope_sha256"],self.f.scope)
            self.assertEqual(receipt["plan_sha256"],self.f.family)
            self.assertEqual(receipt["scientific_validity"],"NOT_ASSESSED")
            self.assertFalse(receipt["execution_authority"])
            self.assertEqual(receipt["artifacts"][0]["logical"],receipt["artifacts"][0]["expected_logical"])
            release=receipt["artifacts"][0]["released_record"]
            self.assertEqual(json.loads((self.f.root/"ledger"/release["file_name"]).read_bytes())["kind"],"RELEASED")
            record=json.loads((self.f.root/"ledger"/result.receipt_ledger_record.file_name).read_bytes())
            self.assertEqual(record["kind"],"CUSTODY_RECEIPT")
            self.assertEqual(record["payload"]["receipt"]["sha256"],result.receipt.sha256)
            self.assertTrue(runtime.last_transport["cleanup"]["leader_reaped"])
            self.assertTrue(runtime.last_transport["cleanup"]["process_group_gone"])

    def test_profile_options_paths_source_closure_and_no_self_hash(self):
        document=self.profile_document()
        loaded=self.load_profile(document)
        self.assertEqual(loaded.decoder.implementation_profile_sha256,digest(a.canonical(document)))
        for mutate in (lambda d:d["options"].update(nbWorkers=1),lambda d:d["options"].update(worker_threads=True),
                       lambda d:d["encoder"].update(path="../outside"),lambda d:d["zstd_library"].update(sha256="0"*64),
                       lambda d:d.update(implementation_profile_sha256="0"*64),
                       lambda d:d.update(source_closure=[m for m in d["source_closure"] if m["module"]!="check_canonical"])):
            candidate=copy.deepcopy(document)
            mutate(candidate)
            with self.assertRaises(a.ArchiveError):self.load_profile(candidate)

    def test_request_seals_reject_mutable_inputs(self):
        fd=os.memfd_create("synthetic-unsealed",os.MFD_ALLOW_SEALING)
        try:
            os.write(fd,b"{}")
            with self.assertRaisesRegex(r.RuntimeError,"unsealed"):r._read_sealed(fd,100)
        finally:os.close(fd)
        sealed=r._sealed_input(b"{}","synthetic-sealed")
        try:
            self.assertEqual(r._read_sealed(sealed,100),b"{}")
            with self.assertRaises(OSError):os.pwrite(sealed,b"xx",0)
            with self.assertRaises(OSError):os.ftruncate(sealed,0)
        finally:os.close(sealed)

    def test_sealed_exec_uses_only_explicit_qualified_library_directory(self):
        directory=Path(self.temp.name)/"qualified-libraries"
        directory.mkdir()
        library=directory/"libzstd.so.1"
        shutil.copyfile(self.profile.decoder.zstd_library_path,library)
        self.profile=replace(self.profile,decoder=replace(self.profile.decoder,zstd_library_path=library))
        with codec_limit(),self.f.store() as store,mock.patch.dict(os.environ,
                {"LD_LIBRARY_PATH":"/unapproved", "LD_PRELOAD":"/unapproved/inject.so"}):
            runtime=self.runtime(store)
            outcome=runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)
            self.assertEqual(outcome.status,"ARCHIVED_AND_RELEASED")
            self.assertEqual(runtime.child_count,3)

    def test_required_closure_and_actual_image_drift_reject_before_spawn(self):
        with codec_limit(),self.f.store() as store:
            store.prepare_family(self.f.family)
            bad_profiles=(replace(self.profile,source_closure=tuple(m for m in self.profile.source_closure if m.module!="stage17_process_group_supervisor_v2")),
                replace(self.profile,source_closure=tuple(replace(m,image=replace(m.image,sha256="0"*64)) if m.module=="check_canonical" else m
                                                          for m in self.profile.source_closure)))
            for profile in bad_profiles:
                with self.subTest(profile=profile),mock.patch("subprocess.Popen") as spawn,self.assertRaises(r.RuntimeError):
                    r.ColdArchiveRuntime(store,profile=profile,limits=self.limits)
                spawn.assert_not_called()

    def test_already_expired_and_no_cleanup_time_never_spawn(self):
        with codec_limit(),self.f.store() as store:
            store.prepare_family(self.f.family)
            for expiry in (time.monotonic_ns()-1,time.monotonic_ns()+500_000_000):
                with mock.patch("subprocess.Popen") as spawn,self.assertRaises(r.RuntimeError):
                    r.ColdArchiveRuntime(store,profile=self.profile,limits=replace(self.limits,authority_expiry_monotonic_ns=expiry))
                spawn.assert_not_called()
            self.assertEqual(self.f.original.read_bytes(),self.f.data)

    def test_real_child_authority_deadline_kills_and_reaps_before_family_deadline(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store,authority_expiry_monotonic_ns=time.monotonic_ns()+1_800_000_000)
            start=time.monotonic()
            # Unit-test private supervisor seam only; public runtime never accepts
            # arbitrary argv. This actual sleeper exercises kernel kill/reap.
            with self.assertRaisesRegex(r.RuntimeError,"codec failed"):
                runtime._run_fixed("encode",["/usr/bin/sleep","30"],(),monitored_outputs=(),file_size_limit=65536)
            self.assertLess(time.monotonic()-start,3)
            cleanup=runtime.last_transport["cleanup"]
            self.assertTrue(cleanup["leader_reaped"] and cleanup["process_group_gone"])
            self.assertFalse(cleanup["cleanup_deadline_overrun"])
            self.assertNotEqual(cleanup["returncode"],0)

    def test_real_output_bound_and_descendant_exit_are_fail_closed(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store,max_console_bytes=32)
            with self.assertRaises(r.RuntimeError):
                runtime._run_fixed("decode",[sys.executable,"-c","import sys;sys.stdout.write('x'*4096)"],(),
                                   monitored_outputs=(),file_size_limit=65536)
            self.assertTrue(runtime.last_transport["cleanup"]["process_group_gone"])
            with self.assertRaisesRegex(r.RuntimeError,"cleanup"):
                runtime._run_fixed("decode",[sys.executable,"-c",
                    "import os,time; p=os.fork(); os._exit(0) if p else None; os.close(1); os.close(2); time.sleep(30)"],(),
                    monitored_outputs=(),file_size_limit=65536)
            self.assertTrue(runtime.last_transport["cleanup"]["leader_reaped"])
            self.assertTrue(runtime.last_transport["cleanup"]["descendants_detected_after_leader_exit"])

    def test_missing_source_job_and_native_failure_preserve_original(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            with self.assertRaisesRegex(r.RuntimeError,"every exact source"):
                runtime.archive_capture(self.f.checkpoint,(self.f.source,),(),verify_checkpoint=self.f.callback)
            job=replace(self.job,encoder_limits=dict(self.job.encoder_limits,maximum_observed_context_bytes=1))
            with self.assertRaises(r.RuntimeError):
                runtime.archive_capture(self.f.checkpoint,(self.f.source,),(job,),verify_checkpoint=self.f.callback)
            self.assertEqual(self.f.original.read_bytes(),self.f.data)
            self.assertNotEqual(store._states[self.f.artifact_id]["kind"],"RELEASED")
            self.assertTrue(runtime.last_transport["cleanup"]["leader_reaped"])
            failed=list((self.f.root/"metadata").glob("*.encoder-failure-result.bin"))
            self.assertEqual(len(failed),1)
            self.assertNotEqual(json.loads(failed[0].read_bytes())["stop"],"COMPLETE_STAGING_SYNCED")

    def test_decoder_actual_result_wrong_request_binding_not_accepted(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            self.f.begin(store)
            stage=store.reserve_archive(self.f.artifact_id,staging_name="mutant.staging",maximum_archive_bytes=64*1024**2)
            physical,_,_=runtime.encode(self.job,stage)
            original_result=runtime._result
            def corrupt(fd):
                raw,document=original_result(fd)
                document["request_sha256"]="0"*64
                return raw,document
            with mock.patch.object(runtime,"_result",side_effect=corrupt),self.assertRaisesRegex(r.RuntimeError,"binding"):
                runtime.readback(stage,expected_header=self.f.header,role=self.f.role,physical=physical,
                                 profile=self.profile.decoder,limits=self.f.f.limits)
            self.assertTrue(self.f.original.exists())

    def test_byte_discrepancy_retained_but_cannot_emit_normal_continuation_receipt(self):
        expected=c.BoundFile(self.f.original.name,len(b"expected"),digest(b"expected"))
        checkpoint_path=self.f.working/self.f.checkpoint.file_name
        document=json.loads(checkpoint_path.read_bytes())
        document["artifacts"]=[dict(file_name=expected.file_name,size_bytes=expected.size_bytes,sha256=expected.sha256)]
        raw=a.canonical(document)
        checkpoint_path.write_bytes(raw)
        self.f.checkpoint=c.BoundFile(checkpoint_path.name,len(raw),digest(raw))
        failure=b'{"failure":"synthetic-source-hash-discrepancy"}'
        failure_path=self.f.root/"metadata"/"source-failure.json"
        failure_path.write_bytes(failure)
        self.f.source=replace(self.f.source,expected=expected,
            failure_receipt=c.BoundFile(failure_path.name,len(failure),digest(failure)))
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            outcome=runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)
            self.assertEqual(outcome.status,"ARCHIVED_FAILED_EVIDENCE")
            document=json.loads((self.f.working/outcome.receipt.file_name).read_bytes())
            self.assertNotEqual(document["artifacts"][0]["logical"],document["artifacts"][0]["expected_logical"])
            self.assertEqual(document["artifacts"][0]["failure_receipt"]["sha256"],digest(failure))
            self.assertEqual(document["status"],"ARCHIVED_FAILED_EVIDENCE")

    def test_family_namespaces_keep_identical_native_filenames_disjoint_under_one_quota(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            first=runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)
            first_usage=store.physical_usage()
        other_family=digest(b"next admitted prospective family")
        with codec_limit(),c.ProgramStore(self.f.root,scope_sha256=self.f.scope,family_id=other_family,limits=self.f.limits) as store:
            working=store.prepare_family(other_family)
            self.assertNotEqual(working,self.f.working)
            original=working/self.f.original.name
            original.write_bytes(self.f.data)
            document=json.loads((self.f.working/self.f.checkpoint.file_name).read_bytes())
            document["plan_sha256"]=other_family
            raw=a.canonical(document)
            (working/self.f.checkpoint.file_name).write_bytes(raw)
            checkpoint=c.BoundFile(self.f.checkpoint.file_name,len(raw),digest(raw))
            source=replace(self.f.source,artifact_id=other_family+":"+self.f.original.name)
            header=dict(self.f.header,artifact_id=source.artifact_id)
            job=replace(self.job,artifact_id=source.artifact_id,header=header)
            runtime=r.ColdArchiveRuntime(store,profile=self.profile,limits=self.limits)
            second=runtime.archive_capture(checkpoint,(source,),(job,),verify_checkpoint=self.f.callback)
            self.assertEqual(first.receipt.file_name,second.receipt.file_name)
            self.assertTrue((self.f.working/first.receipt.file_name).exists())
            self.assertTrue((working/second.receipt.file_name).exists())
            self.assertEqual(len(list((self.f.root/"archives").glob("*.cpfa"))),2)
            self.assertGreater(store.physical_usage(),first_usage)
            self.assertEqual(store.scope["shared_program_quota_bytes"],c.PROGRAM_QUOTA)

    def test_retained_readback_actual_child_needs_no_live_checkpoint_and_writes_no_ledger(self):
        with codec_limit(),self.f.store() as store:
            runtime=self.runtime(store)
            outcome=runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)
            receipt=json.loads((self.f.working/outcome.receipt.file_name).read_bytes())
            entry=receipt["artifacts"][0]
            before={p.name:digest(p.read_bytes()) for p in (self.f.root/"ledger").iterdir()}
        with codec_limit(),self.f.store() as store:
            limits=r.RetainedReadbackLimits(**{k:v for k,v in vars(self.limits).items() if k!="authority_expiry_monotonic_ns"})
            runtime=r.ColdArchiveRuntime(store,profile=self.profile,limits=limits)
            self.assertIsNone(store._checkpoint)
            proof=runtime.readback_retained(self.f.root/"archives"/entry["archive_name"],expected_header=self.f.header,
                role=self.f.role,physical=a.PhysicalBinding(**entry["physical"]),profile=self.profile.decoder,limits=self.f.f.limits)
            self.assertEqual(proof.canonical.sha256,digest(self.f.data))
            self.assertEqual(before,{p.name:digest(p.read_bytes()) for p in (self.f.root/"ledger").iterdir()})
            with self.assertRaisesRegex(r.RuntimeError,"no encode/custody"):
                runtime.archive_capture(self.f.checkpoint,(self.f.source,),(self.job,),verify_checkpoint=self.f.callback)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--encoder",type=Path,required=True)
    args,rest=parser.parse_known_args()
    ArchiveRuntimeTests.encoder=args.encoder.resolve()
    unittest.main(argv=[sys.argv[0],*rest])
