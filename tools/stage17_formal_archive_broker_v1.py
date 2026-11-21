#!/usr/bin/env python3
"""Fixed sealed D233 broker client/entrypoint; no arbitrary command interface.

The live parent already owns the whole-family subreaper lease. Only its pinned,
parked native leader is excluded from broker cleanup. Offline readers use an
ordinary sole-child lease. The broker owns sequential codec children itself.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, replace
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import selectors
import subprocess
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
from stage17_formal_checkpoint_v1 import PinnedWorker, validate_checkpoint
from stage17_formal_archive_jobs_v1 import build_capture_jobs

REQUEST_SCHEMA="cpu-prefetch-stage17-archive-broker-request/1"
RESULT_SCHEMA="cpu-prefetch-stage17-archive-broker-result/1"


class BrokerError(runtime.RuntimeError):
    pass


@dataclass(frozen=True)
class BrokerOutcome:
    receipt: custody.BoundFile
    status: str
    receipt_ledger_record: custody.BoundFile
    cleanup: supervisor.CleanupResult


class _NativeExcludedModel:
    """Exclude exactly one held native identity, never a general baseline set.

    A native exit invalidates success, but cleanup scans must still finish. The
    matching held zombie is excluded only from broker cleanup and is left for
    the outer family owner to reap. No replacement PID is excluded.
    """
    def __init__(self, base, native):
        self.base,self.native=base,native
        self.native_failure=None
        if supervisor._prctl_get_subreaper()!=1:
            raise BrokerError("live broker requires existing outer subreaper lease")
        base.verify_stable()
        native.observe_quiescence()
        children=base.direct_children()
        if set(children)!={native.pid}:
            raise BrokerError("live broker baseline must be exactly the pinned native leader")
        self.identity=children[native.pid]
        if self.identity.start_time_ticks!=native.start_ticks:
            raise BrokerError("native supervisor/PIDFD identity differs")

    def _observe(self):
        try:self.native.observe_quiescence()
        except BaseException as exc:self.native_failure=str(exc)

    @property
    def snapshot(self):return self.base.snapshot

    def require_native(self):
        self._observe()
        if self.native_failure is not None:raise BrokerError("parked native identity/quiescence failed: "+self.native_failure)

    def verify_stable(self):
        self.base.verify_stable()
        self._observe()

    def identity_for_local_pid(self,pid):
        if pid==self.native.pid:raise BrokerError("broker leader aliases pinned native")
        return self.base.identity_for_local_pid(pid)

    def direct_children(self):
        self._observe()
        children=self.base.direct_children()
        found=children.get(self.native.pid)
        if found==self.identity:
            children.pop(self.native.pid)
        elif found is not None:
            self.native_failure="native PID identity was replaced"
        else:
            self.native_failure="native leader ceased to be an owned child"
        return children

    def process_group_members(self,group):
        self._observe()
        if group==self.identity.local_pgid:
            raise BrokerError("broker cleanup group aliases native group")
        return self.base.process_group_members(group)


def _client_limits(limits):
    for name,value in vars(limits).items():archive.uint(value,name,positive=True)
    if limits.broker_address_space_bytes>2*1024**3 or limits.codec_address_space_bytes>2*1024**3:
        raise BrokerError("broker/codec AS exceeds admitted 2 GiB ceiling")
    minimum=supervisor.predecessor.TERM_GRACE_NS+supervisor.predecessor.KILL_GRACE_NS
    if limits.cleanup_reserve_ns<minimum:raise BrokerError("broker cleanup reserve is insufficient")
    limits.before_spawn()


def _supervise_broker(argv,fds,*,profile,limits,result_fd,identity_model=None,native_worker=None):
    """Private fixed-command transport. Never modifies the parent's AS limit."""
    _client_limits(limits)
    lease=None
    if native_worker is None:
        if identity_model is not None:raise BrokerError("offline broker cannot borrow an unrelated identity model")
        lease=supervisor.SupervisorLease()
        lease.enter()
        model=lease.identity_model
    else:
        if identity_model is None:raise BrokerError("live broker requires the actual outer identity model")
        model=_NativeExcludedModel(identity_model,native_worker)
    process=None
    cleanup=None
    failure=None
    selector=selectors.DefaultSelector()
    console=bytearray()
    try:
        try:
            limits.before_spawn()
            if native_worker is not None:model.require_native()
            def constrain():
                resource.setrlimit(resource.RLIMIT_AS,(limits.broker_address_space_bytes,)*2)
                resource.setrlimit(resource.RLIMIT_CORE,(0,0))
                # Broker writes only bounded metadata/ledger directly; codec
                # children install their own explicit native archive ceiling.
                resource.setrlimit(resource.RLIMIT_FSIZE,(custody.PROGRAM_QUOTA,)*2)
            process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                shell=False,close_fds=True,pass_fds=fds,start_new_session=True,preexec_fn=constrain,
                env=dict(runtime._ENVIRONMENT,LD_LIBRARY_PATH=str(profile.decoder.zstd_library_path.parent)))
            for stream in (process.stdout,process.stderr):
                os.set_blocking(stream.fileno(),False)
                selector.register(stream,selectors.EVENT_READ)
            while selector.get_map():
                limits.before_spawn()
                if native_worker is not None:model.require_native()
                if os.fstat(result_fd).st_size>limits.max_result_bytes:raise BrokerError("broker result FD bound")
                remaining=(limits.final_deadline_ns-limits.cleanup_reserve_ns-time.monotonic_ns())/1e9
                for key,_ in selector.select(max(0,min(remaining,0.05))):
                    data=os.read(key.fd,min(65536,limits.max_console_bytes-len(console)+1))
                    if not data:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        console.extend(data)
                        if len(console)>limits.max_console_bytes:raise BrokerError("broker stdout/stderr bound")
        except BaseException as exc:failure=exc
        finally:
            for key in tuple(selector.get_map().values()):key.fileobj.close()
            selector.close()
            if process is not None:
                cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                    leader_wait_deadline_ns=min(time.monotonic_ns()+limits.cleanup_reserve_ns,limits.final_deadline_ns),
                    global_deadline_ns=limits.final_deadline_ns,identity_model=model)
    finally:
        if lease is not None:lease.close(suppress=failure is not None)
    error=None
    if (cleanup is None or not cleanup.leader_reaped or not cleanup.process_group_gone
            or cleanup.descendants_detected_after_leader_exit or cleanup.cleanup_deadline_overrun):
        error="broker cleanup incomplete/descendant/deadline failure"
    elif native_worker is not None and model.native_failure is not None:
        error="native quiescence lost during broker: "+model.native_failure
    elif failure is not None:error="broker transport failed: "+str(failure)
    elif cleanup.returncode!=0:error="broker exited unsuccessfully: "+str(cleanup.returncode)+": "+console.decode("utf-8",errors="replace")
    if error is not None:
        exception=BrokerError(error)
        exception.cleanup_proof=cleanup
        raise exception from failure
    return cleanup


def _profile(document):
    def image(value):return runtime.ImageBinding(Path(value["path"]),value["size_bytes"],value["sha256"])
    decoder=dict(document["decoder"])
    for name in ("zstd_library_path","decoder_executable_path"):decoder[name]=Path(decoder[name])
    return runtime.RuntimeProfile(image(document["encoder"]),image(document["python"]),
        archive.DecoderProfile(**decoder),tuple(runtime.ModuleBinding(m["module"],image(m["image"])) for m in document["source_closure"]))


class _Client:
    request_schema = REQUEST_SCHEMA
    result_schema = RESULT_SCHEMA
    entry_mode = "broker"
    entry_module = "stage17_formal_archive_broker_v1"
    def __init__(self,*,profile,limits,identity_model=None,native_worker=None):
        _client_limits(limits)
        self.profile,self.limits=profile,limits
        self.identity_model,self.native_worker=identity_model,native_worker
        self.closure=runtime._closure_bytes(profile,limits.final_deadline_ns)
        if self.entry_module not in self.closure:
            raise BrokerError("qualified source closure omits broker entrypoint")
        self.jobs=0
        self.actual_processes=0
        self.last_cleanup=None
        self._entered=False

    def __enter__(self):
        if self._entered:raise BrokerError("broker client already entered")
        self._entered=True
        return self

    def __exit__(self,*_):self._entered=False

    def _invoke(self,mode,parameters):
        if not self._entered:raise BrokerError("broker client context is not active")
        if self.jobs>=self.limits.max_children:raise BrokerError("broker job budget exhausted")
        _client_limits(self.limits)
        self.jobs+=1
        raw=archive.canonical(dict(schema_version=self.request_schema,mode=mode,
            profile=runtime._jsonable(asdict(self.profile)),limits=asdict(self.limits),parameters=parameters))
        if len(raw)>self.limits.max_input_bytes:raise BrokerError("broker sealed request byte bound")
        with contextlib.ExitStack() as stack:
            executable=runtime._pin_image(self.profile.python,self.limits.final_deadline_ns,stack)
            request_fd=runtime._sealed_input(raw,"stage17-broker-request")
            stack.callback(os.close,request_fd)
            result_fd=os.memfd_create("stage17-broker-result",os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            stack.callback(os.close,result_fd)
            mapping={}
            source_fds=[]
            for name,(binding,source) in self.closure.items():
                fd=runtime._sealed_input(source,"stage17-broker-source-"+name)
                stack.callback(os.close,fd)
                source_fds.append(fd)
                mapping[name]=dict(fd=fd,path=str(binding.image.path),size_bytes=binding.image.size_bytes,sha256=binding.image.sha256)
            map_raw=archive.canonical(mapping)
            if len(map_raw)>self.limits.max_input_bytes:raise BrokerError("broker source map byte bound")
            map_fd=runtime._sealed_input(map_raw,"stage17-broker-source-map")
            stack.callback(os.close,map_fd)
            native_fds=() if self.native_worker is None else (self.native_worker.descriptor,)
            argv=[f"/proc/self/fd/{executable}","-I","-B","-c",runtime._BOOTSTRAP,self.entry_mode,
                str(map_fd),str(self.limits.max_input_bytes),str(request_fd),"-1",str(result_fd),
                str(self.limits.max_input_bytes),str(self.limits.max_result_bytes)]
            cleanup=_supervise_broker(argv,(executable,request_fd,result_fd,map_fd,*source_fds,*native_fds),
                profile=self.profile,limits=self.limits,result_fd=result_fd,
                identity_model=self.identity_model,native_worker=self.native_worker)
            self.last_cleanup=cleanup
            fcntl.fcntl(result_fd,fcntl.F_ADD_SEALS,runtime._SEALS)
            result=archive.parse_json(runtime._read_sealed(result_fd,self.limits.max_result_bytes))
            if (set(result)!={"schema_version","mode","request_sha256","result","codec_children"}
                    or result["schema_version"]!=self.result_schema or result["mode"]!=mode
                    or result["request_sha256"]!=hashlib.sha256(raw).hexdigest()):
                raise BrokerError("actual sealed broker result binding differs")
            children=archive.uint(result["codec_children"],"broker codec child count")
            if children>self.limits.max_children:raise BrokerError("broker codec child count exceeds admitted budget")
            self.actual_processes+=1+children
            return result["result"],cleanup


class ArchiveBrokerClient(_Client):
    def __init__(self,*,profile,limits,identity_model,native_worker):
        if type(limits) is not runtime.RuntimeLimits:raise BrokerError("live broker requires live finite authority limits")
        if not isinstance(native_worker,PinnedWorker):raise BrokerError("live broker requires an actual pinned native handle")
        super().__init__(profile=profile,limits=limits,identity_model=identity_model,native_worker=native_worker)

    def archive_capture(self,*,program_root,scope_sha256,family_id,custody_limits,
                        request_document,capture_ordinal,checkpoint):
        self.native_worker.observe_quiescence()
        parameters=dict(program_root=str(Path(program_root).absolute()),scope_sha256=scope_sha256,family_id=family_id,
            custody_limits=asdict(custody_limits),request_document=request_document,capture_ordinal=capture_ordinal,
            checkpoint=asdict(checkpoint),native=dict(pid=self.native_worker.pid,start_ticks=self.native_worker.start_ticks,
                                                   pidfd=self.native_worker.descriptor))
        value,cleanup=self._invoke("archive_capture",parameters)
        if set(value)!={"receipt","status","receipt_ledger_record"} or value["status"] not in ("ARCHIVED_AND_RELEASED","ARCHIVED_FAILED_EVIDENCE"):
            raise BrokerError("broker custody outcome shape/status")
        receipt=custody.BoundFile(**value["receipt"])
        receipt.binding()
        registration=custody.BoundFile(**value["receipt_ledger_record"])
        registration.binding()
        self.native_worker.observe_quiescence()
        return BrokerOutcome(receipt,value["status"],registration,cleanup)


class RetainedReadbackClient(_Client):
    def __init__(self,*,profile,limits):
        if type(limits) is not runtime.RetainedReadbackLimits:
            raise BrokerError("retained readback requires separate current offline analysis limits")
        super().__init__(profile=profile,limits=limits)

    def readback(self,path,*,expected_header,role,physical,profile,limits):
        if profile!=self.profile.decoder:raise BrokerError("retained readback profile differs")
        path=Path(path).absolute()
        if path.parent.name!="archives":raise BrokerError("retained readback is outside a scoped archive directory")
        parameters=dict(path=str(path),expected_header=expected_header,role=asdict(role),physical=asdict(physical),limits=asdict(limits))
        value,_=self._invoke("readback_retained",parameters)
        proof=archive.VerifiedArchive(archive.PhysicalBinding(**value["physical"]),archive.PhysicalBinding(**value["canonical"]),
            value["header_sha256"],value["block_count"],tuple(value["file_identity"]),value["verified_at_unix_ns"])
        if (proof.physical!=physical or proof.canonical!=archive.PhysicalBinding(expected_header["canonical_size_bytes"],expected_header["canonical_sha256"])
                or proof.header_sha256!=hashlib.sha256(archive.canonical(expected_header)).hexdigest()
                or proof.block_count!=expected_header["block_count"]
                or proof.file_identity!=archive.file_stamp(path.stat(follow_symlinks=False))):
            raise BrokerError("retained readback proof differs from exact physical/canonical request")
        return proof


class _RetainedView:
    """Read-only child view: parent keeps the real ProgramStore/ledger lock."""
    def __init__(self,path,header,limits):
        self.root=path.parent.parent
        self.family_id=archive.sha(header["artifact_id"].split(":",1)[0],"retained artifact family")
        self.limits=custody.CustodyLimits(limits.max_input_bytes,1,1,limits.max_input_bytes,limits.final_deadline_ns)
        self._identities={}
        for directory in (self.root,self.root/"archives"):
            if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):raise BrokerError("retained view symlink")
            st=directory.stat()
            self._identities[directory]=(st.st_dev,st.st_ino)
        with archive.open_regular(self.root/"scope.json") as stream:
            raw=stream.read(limits.max_input_bytes+1)
        if len(raw)>limits.max_input_bytes:raise BrokerError("retained scope byte bound")
        scope=archive.parse_json(raw)
        if scope.get("policy_id")!=archive.POLICY_ID or scope.get("future_formal_only") is not True:
            raise BrokerError("retained archive is outside D233 future-program scope")
        self.scope_binding=archive.PhysicalBinding(len(raw),hashlib.sha256(raw).hexdigest())

    def _check(self):
        self.limits.check_time()
        for path,identity in self._identities.items():
            st=path.stat(follow_symlinks=False)
            if (st.st_dev,st.st_ino)!=identity:raise BrokerError("retained view root changed")
        actual=archive.hash_file(self.root/"scope.json",max_bytes=self.limits.max_record_bytes,deadline_ns=self.limits.deadline_ns)
        if actual!=self.scope_binding:raise BrokerError("retained program scope changed")


def _broker_child(request_fd,result_fd,input_limit,result_limit):
    raw=runtime._read_sealed(request_fd,input_limit)
    request=archive.parse_json(raw)
    if set(request)!={"schema_version","mode","profile","limits","parameters"} or request["schema_version"]!=REQUEST_SCHEMA:
        raise BrokerError("broker request shape/version")
    profile=_profile(request["profile"])
    p=request["parameters"]
    mode=request["mode"]
    if mode=="archive_capture":
        if set(p)!={"program_root","scope_sha256","family_id","custody_limits","request_document","capture_ordinal","checkpoint","native"}:
            raise BrokerError("live broker request field set")
        limits=runtime.RuntimeLimits(**request["limits"])
        limits.validate()
        original=p["request_document"]
        if original.get("schema_version")!="cpu-prefetch-stage17-fixed-action-request/6":
            raise BrokerError("live broker requires exact formal request v6")
        action=original["action_id"]
        if action not in ("Q16a","Q16b","Q16c"):raise BrokerError("broker action is not formal")
        plan=original["action_inputs"]["plan"]
        if hashlib.sha256(archive.canonical(plan)).hexdigest()!=p["family_id"]:
            raise BrokerError("broker family differs from original plan hash")
        ordinal=archive.uint(p["capture_ordinal"],"capture ordinal")
        item=plan["captures"][ordinal]
        capture=item["capture"]
        if capture["ordinal"]!=ordinal:raise BrokerError("broker capture order differs")
        native=p["native"]
        if set(native)!={"pid","start_ticks","pidfd"}:raise BrokerError("native pinned identity fields")
        # The inherited kernel handle and a newly pinned local handle must agree.
        info=Path(f"/proc/self/fdinfo/{native['pidfd']}").read_text()
        fields=dict(line.split(":",1) for line in info.splitlines() if ":" in line)
        if int(fields.get("Pid","-1").strip())!=native["pid"]:raise BrokerError("inherited native pidfd differs")
        worker=PinnedWorker(native["pid"])
        try:
            if worker.start_ticks!=native["start_ticks"]:raise BrokerError("native start identity changed")
            def observe():worker.observe_quiescence()
            with custody.ProgramStore(Path(p["program_root"]),scope_sha256=p["scope_sha256"],family_id=p["family_id"],
                                       limits=custody.CustodyLimits(**p["custody_limits"])) as store:
                store.prepare_family(p["family_id"])
                checkpoint=custody.BoundFile(**p["checkpoint"])
                document=archive.parse_json(store._read_bound(store.working/checkpoint.file_name,
                    checkpoint.binding(),store.limits.max_checkpoint_bytes))
                sources,jobs=build_capture_jobs(store=store,action=action,capture=capture,document=document,profile=profile,
                    storage=plan["storage"],maximum_capture_bytes=item["execution_budget"]["max_output_bytes"],
                    deadline_ns=limits.final_deadline_ns,verify_quiescence=observe)
                def verify(document,sources):
                    validate_checkpoint(document,action=action,plan_sha256=store.family_id,capture=capture,sources=sources)
                    observe()
                engine=runtime.ColdArchiveRuntime(store,profile=profile,limits=limits)
                value=asdict(engine.archive_capture(checkpoint,sources,jobs,verify_checkpoint=verify))
                children=engine.child_count
        finally:worker.close()
    elif mode=="readback_retained":
        if set(p)!={"path","expected_header","role","physical","limits"}:raise BrokerError("retained broker request field set")
        limits=runtime.RetainedReadbackLimits(**request["limits"])
        limits.validate()
        path=Path(p["path"])
        if not path.is_absolute() or path.parent.name!="archives":raise BrokerError("retained broker path")
        view=_RetainedView(path,p["expected_header"],limits)
        engine=runtime.ColdArchiveRuntime(view,profile=profile,limits=replace(limits,max_children=1))
        value=asdict(engine.readback_retained(path,expected_header=p["expected_header"],role=archive.RoleProfile(**p["role"]),
            physical=archive.PhysicalBinding(**p["physical"]),profile=profile.decoder,limits=archive.DecodeLimits(**p["limits"])))
        view._check()
        children=engine.child_count
    else:raise BrokerError("unknown fixed broker operation")
    output=archive.canonical(dict(schema_version=RESULT_SCHEMA,mode=mode,request_sha256=hashlib.sha256(raw).hexdigest(),
                                  result=runtime._jsonable(value),codec_children=children))
    if len(output)>result_limit:raise BrokerError("broker result exceeds bound")
    if os.pwrite(result_fd,output,0)!=len(output):raise BrokerError("partial broker result write")
    os.fsync(result_fd)
