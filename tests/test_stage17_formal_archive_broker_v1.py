"""Actual dedicated broker/codec processes with a parked sibling native fixture."""
from __future__ import annotations

import argparse
import ast
from dataclasses import asdict,replace
import hashlib
import json
import os
from pathlib import Path
import resource
import struct
import subprocess
import sys
import tempfile
import time
import unittest

from test_stage17_formal_archive_v1 import ArchiveFixture,digest
from test_stage17_formal_checkpoint_v1 import fixture
from test_stage17_formal_archive_runtime_v1 import image,TOOLS
import stage17_formal_archive_v1 as a
import stage17_formal_archive_custody_v1 as c
import stage17_formal_archive_runtime_v1 as r
import stage17_formal_archive_broker_v1 as b
import stage17_process_group_supervisor_v3 as supervisor
from stage17_formal_checkpoint_v1 import PinnedWorker
from stage17_formal_archive_jobs_v1 import capture_names,role_profile


def qualified_closure():
    pending=["stage17_formal_archive_runtime_v1","stage17_formal_archive_broker_v1"]
    found={}
    while pending:
        name=pending.pop()
        if name in found:continue
        path=TOOLS/(name+".py")
        found[name]=r.ModuleBinding(name,image(path))
        for node in ast.walk(ast.parse(path.read_bytes())):
            names=([entry.name.split(".")[0] for entry in node.names] if isinstance(node,ast.Import)
                else [node.module.split(".")[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
            pending.extend(n for n in names if (TOOLS/(n+".py")).is_file() and n not in found)
    return tuple(found[n] for n in sorted(found))


class BrokerTests(unittest.TestCase):
    encoder:Path|None=None

    def setUp(self):
        if self.encoder is None:self.skipTest("requires --encoder actual compiled binary")
        # Dedicated actual filesystem test tree; /tmp can be a small tmpfs which
        # correctly fails the unchanged D233 16 GiB reserve in the exec broker.
        self.temp=tempfile.TemporaryDirectory(prefix="d233-broker-",dir=TOOLS.parent/"build")
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        fixture_profile=ArchiveFixture(self.base).profile
        self.profile=r.RuntimeProfile(image(self.encoder),image(sys.executable),
            replace(fixture_profile,encoder_sha256=image(self.encoder).sha256),qualified_closure())
        self.deadline=time.monotonic_ns()+90_000_000_000
        self.limits=r.RuntimeLimits(2*1024**3,2*1024**3,2*1024**2,131072,131072,2_000_000_000,
                                   self.deadline,self.deadline,27)
        self.custody_limits=c.CustodyLimits(131072,4096,8192,131072,self.deadline)
        self.root=self.base/"program"
        self.scope=c.ProgramStore.initialize(self.root,program_id="synthetic-broker-program",
            storage_domain_id="synthetic-disk",prospective_admission_sha256="a"*64)
        self.document,self.capture,_=fixture()
        storage=dict(program_id="synthetic-broker-program",program_scope_sha256=self.scope,
            implementation_profile_sha256=self.profile.decoder.implementation_profile_sha256,
            archive_staging_bytes=8*1024**2)
        self.plan=dict(storage=storage,captures=[dict(capture=self.capture,execution_budget=dict(max_output_bytes=1024**2))])
        self.family=digest(a.canonical(self.plan))
        self.request=dict(schema_version="cpu-prefetch-stage17-fixed-action-request/6",action_id="Q16a",
                          action_inputs=dict(plan=self.plan),synthetic_test_only=True)
        with c.ProgramStore(self.root,scope_sha256=self.scope,family_id=self.family,limits=self.custody_limits) as store:
            self.working=store.prepare_family(self.family)
        self.originals={}
        for name in capture_names("Q16a",0):
            role=role_profile("Q16a",name)
            phase=next((p for p in ("warmup","measurement") if f"-{p}-" in name),None)
            width=role.row_bytes(self.capture[phase]["run_id"] if phase else None)
            if width is None:data=b'{"synthetic_control":true}'
            else:
                run=self.capture[phase]["run_id"].encode()
                prefix=struct.pack("<I",len(run))+run
                prefix+=bytes((-len(prefix))%8)
                data=(prefix+bytes((i%251 for i in range(width-len(prefix)))))*3
            (self.working/name).write_bytes(data)
            self.originals[name]=data
        self.document["plan_sha256"]=self.family
        self.document["artifacts"]=[dict(file_name=n,size_bytes=len(v),sha256=digest(v)) for n,v in self.originals.items()]
        raw=a.canonical(self.document)
        name="formal-capture-0-final-checkpoint.json"
        (self.working/name).write_bytes(raw)
        self.checkpoint=c.BoundFile(name,len(raw),digest(raw))

    def parked(self):
        process=subprocess.Popen([sys.executable,"-c","import os;os.read(0,1)"],stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        # Constructor checks identity immediately. Native synthetic observations
        # are explicitly fixture-only; stdin is held open, never acknowledged here.
        worker=PinnedWorker(process.pid)
        return process,worker

    def stop_parked(self,process,worker,lease):
        process.stdin.close()
        result=supervisor.cleanup_process_group(process,force_stop=False,
            leader_wait_deadline_ns=time.monotonic_ns()+2_000_000_000,global_deadline_ns=self.deadline,
            identity_model=lease.identity_model)
        worker.close()
        self.assertTrue(result.leader_reaped and result.process_group_gone)

    def archive_live(self):
        lease=supervisor.SupervisorLease()
        lease.enter()
        process,worker=self.parked()
        try:
            before=resource.getrlimit(resource.RLIMIT_AS)
            with b.ArchiveBrokerClient(profile=self.profile,limits=self.limits,
                    identity_model=lease.identity_model,native_worker=worker) as client:
                outcome=client.archive_capture(program_root=self.root,scope_sha256=self.scope,family_id=self.family,
                    custody_limits=self.custody_limits,request_document=self.request,capture_ordinal=0,checkpoint=self.checkpoint)
            self.assertEqual(before,resource.getrlimit(resource.RLIMIT_AS))
            self.assertIsNone(process.poll())
            worker.observe_quiescence()
            return outcome
        finally:
            self.stop_parked(process,worker,lease)
            lease.close()

    def test_actual_live_broker_archives_all_sources_while_native_remains_parked(self):
        outcome=self.archive_live()
        self.assertEqual(outcome.status,"ARCHIVED_AND_RELEASED")
        self.assertTrue(outcome.cleanup.leader_reaped and outcome.cleanup.process_group_gone)
        receipt=json.loads((self.working/outcome.receipt.file_name).read_bytes())
        self.assertEqual(len(receipt["artifacts"]),9)
        self.assertTrue(all(not (self.working/name).exists() for name in self.originals))
        self.assertFalse(receipt["execution_authority"])

    def test_offline_readback_parent_lock_held_parent_as_unchanged_and_no_ledger_writes(self):
        outcome=self.archive_live()
        receipt=json.loads((self.working/outcome.receipt.file_name).read_bytes())
        entry=receipt["artifacts"][0]
        with c.ProgramStore(self.root,scope_sha256=self.scope,family_id=self.family,limits=self.custody_limits) as store:
            released=store.read_verified_record(c.BoundFile(**entry["released_record"]))["payload"]
            before={p.name:digest(p.read_bytes()) for p in (self.root/"ledger").iterdir()}
            address=resource.getrlimit(resource.RLIMIT_AS)
            limits=r.RetainedReadbackLimits(**{k:v for k,v in vars(self.limits).items() if k!="authority_expiry_monotonic_ns"})
            with b.RetainedReadbackClient(profile=self.profile,limits=replace(limits,max_children=1)) as client:
                proof=client.readback(self.root/"archives"/entry["archive_name"],expected_header=released["header"],
                    role=a.RoleProfile(**released["role"]),physical=a.PhysicalBinding(**entry["physical"]),
                    profile=self.profile.decoder,limits=a.DecodeLimits(32768,4*1024**2,4*1024**2,8*1024**2,
                        1024**2,100,1<<22,self.deadline))
                self.assertEqual(proof.canonical.sha256,entry["logical"]["sha256"])
                self.assertEqual(client.actual_processes,2)
            self.assertEqual(before,{p.name:digest(p.read_bytes()) for p in (self.root/"ledger").iterdir()})
            self.assertEqual(address,resource.getrlimit(resource.RLIMIT_AS))

    def test_escaped_broker_descendant_is_reaped_without_signalling_native(self):
        lease=supervisor.SupervisorLease()
        lease.enter()
        native,worker=self.parked()
        result_fd=os.memfd_create("synthetic-result",os.MFD_ALLOW_SEALING)
        try:
            script="import os,time; p=os.fork(); os._exit(0) if p else None; os.setsid(); os.close(1); os.close(2); time.sleep(30)"
            with self.assertRaises(b.BrokerError) as failed:
                b._supervise_broker([sys.executable,"-c",script],(),profile=self.profile,limits=self.limits,
                    result_fd=result_fd,identity_model=lease.identity_model,native_worker=worker)
            proof=failed.exception.cleanup_proof
            self.assertTrue(proof.leader_reaped and proof.process_group_gone)
            self.assertTrue(proof.descendants_detected_after_leader_exit)
            self.assertIsNone(native.poll())
            self.assertEqual(set(lease.identity_model.direct_children()),{native.pid})
            worker.observe_quiescence()
        finally:
            os.close(result_fd)
            self.stop_parked(native,worker,lease)
            lease.close()

    def test_live_broker_timeout_retains_raw_and_parked_native(self):
        lease=supervisor.SupervisorLease()
        lease.enter()
        native,worker=self.parked()
        result_fd=os.memfd_create("synthetic-result",os.MFD_ALLOW_SEALING)
        try:
            limits=replace(self.limits,authority_expiry_monotonic_ns=time.monotonic_ns()+2_300_000_000)
            with self.assertRaises(b.BrokerError) as failed:
                b._supervise_broker(["/usr/bin/sleep","30"],(),profile=self.profile,limits=limits,
                    result_fd=result_fd,identity_model=lease.identity_model,native_worker=worker)
            self.assertTrue(failed.exception.cleanup_proof.leader_reaped)
            self.assertTrue(failed.exception.cleanup_proof.process_group_gone)
            self.assertIsNone(native.poll())
            self.assertTrue(all((self.working/name).read_bytes()==data for name,data in self.originals.items()))
        finally:
            os.close(result_fd)
            self.stop_parked(native,worker,lease)
            lease.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--encoder",type=Path,required=True)
    args,rest=parser.parse_known_args()
    BrokerTests.encoder=args.encoder.resolve()
    unittest.main(argv=[sys.argv[0],*rest])
