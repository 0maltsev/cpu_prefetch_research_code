#!/usr/bin/env python3
"""D233 fixed cold codec subprocesses and custody orchestration.

Run this callable in the dedicated bounded broker, never in the controller that
owns the parked native worker. Existing supervisor v3 requires sole child-family
ownership. Only the pinned encoder or sealed-source decoder command can execute.
Collection authority, native IPC and live checkpoint verification remain callers'
mandatory, independently qualified responsibilities.
"""
from __future__ import annotations

import ast
import contextlib
from dataclasses import asdict, dataclass, replace
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import time
from typing import Callable

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_process_group_supervisor_v3 as supervisor

_SEALS = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
_ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"}
_ENCODER_LIMITS = frozenset(("window_log maximum_header_bytes maximum_decoded_block_bytes "
    "maximum_encoded_block_bytes maximum_archive_bytes maximum_observed_context_bytes "
    "io_chunk_bytes maximum_io_calls deadline_monotonic_ns").split())
_ENCODER_IDENTITY = tuple(("artifact_id artifact_role canonical_format run_id phase worker canonical_size_bytes "
    "canonical_sha256 codec_id row_bytes fallback_reason implementation_profile_sha256 encoder_sha256 zstd_library_sha256").split())

# This fixed bootstrap executes only the profile-bound sealed local Python
# closure. No module body is reread from a mutable source pathname after pinning.
# Standard library/interpreter are the admitted hermetic runtime, not downloaded.
_BOOTSTRAP = r'''
import fcntl,hashlib,importlib.abc,importlib.util,json,os,sys
mask=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
mode=sys.argv[1]
mapfd,maplimit,requestfd,archivefd,resultfd,inputlimit,resultlimit=map(int,sys.argv[2:])
def sealed(fd,maximum):
    if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&mask!=mask:raise RuntimeError('unsealed source/input')
    n=os.fstat(fd).st_size
    if not 0<n<=maximum:raise RuntimeError('source/input bound')
    data=os.pread(fd,n,0)
    if len(data)!=n:raise RuntimeError('short source/input')
    return data
mapping=json.loads(sealed(mapfd,maplimit))
class Loader(importlib.abc.Loader):
    def __init__(self,item):self.item=item
    def create_module(self,spec):return None
    def exec_module(self,module):
        item=self.item
        data=sealed(item['fd'],item['size_bytes'])
        if len(data)!=item['size_bytes'] or hashlib.sha256(data).hexdigest()!=item['sha256']:raise RuntimeError('sealed module hash')
        module.__file__=item['path']
        exec(compile(data,item['path'],'exec'),module.__dict__)
class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        item=mapping.get(fullname)
        if item is None:return None
        return importlib.util.spec_from_loader(fullname,Loader(item),origin=item['path'])
sys.meta_path.insert(0,Finder())
if mode=='decode':
    import stage17_formal_archive_runtime_v1 as runtime
    runtime._decode_child(requestfd,archivefd,resultfd,inputlimit,resultlimit)
elif mode=='broker':
    import stage17_formal_archive_broker_v1 as broker
    broker._broker_child(requestfd,resultfd,inputlimit,resultlimit)
elif mode=='s180_broker':
    import stage17_s180_archive_broker_v1 as broker
    broker._broker_child(requestfd,resultfd,inputlimit,resultlimit)
else:raise RuntimeError('unknown fixed sealed entrypoint')
'''


class RuntimeError(custody.CustodyError):
    pass


@dataclass(frozen=True)
class ImageBinding:
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ModuleBinding:
    module: str
    image: ImageBinding


@dataclass(frozen=True)
class RuntimeProfile:
    encoder: ImageBinding
    python: ImageBinding
    decoder: archive.DecoderProfile
    source_closure: tuple[ModuleBinding, ...]


@dataclass(frozen=True)
class RuntimeLimits:
    broker_address_space_bytes: int
    codec_address_space_bytes: int
    max_input_bytes: int
    max_result_bytes: int
    max_console_bytes: int
    cleanup_reserve_ns: int
    deadline_ns: int
    authority_expiry_monotonic_ns: int
    max_children: int

    @property
    def final_deadline_ns(self):
        return min(self.deadline_ns, self.authority_expiry_monotonic_ns)

    def validate(self):
        _validate_limits(self)

    def before_spawn(self):
        if time.monotonic_ns()+self.cleanup_reserve_ns >= self.final_deadline_ns:
            raise RuntimeError("no finite codec time remains before cleanup/authority deadline")


@dataclass(frozen=True)
class RetainedReadbackLimits:
    """Current offline analysis limits; contains no historical capture authority."""
    broker_address_space_bytes: int
    codec_address_space_bytes: int
    max_input_bytes: int
    max_result_bytes: int
    max_console_bytes: int
    cleanup_reserve_ns: int
    deadline_ns: int
    max_children: int

    @property
    def final_deadline_ns(self):return self.deadline_ns

    def validate(self):_validate_limits(self)

    def before_spawn(self):
        if time.monotonic_ns()+self.cleanup_reserve_ns>=self.deadline_ns:
            raise RuntimeError("offline readback deadline/cleanup budget exhausted")


def _validate_limits(limits):
    for name,value in vars(limits).items():archive.uint(value,name,positive=True)
    if limits.codec_address_space_bytes>2*1024**3:raise RuntimeError("codec AS exceeds D233 2 GiB ceiling")
    minimum=supervisor.predecessor.TERM_GRACE_NS+supervisor.predecessor.KILL_GRACE_NS
    if limits.cleanup_reserve_ns<minimum:raise RuntimeError("cleanup reserve does not cover existing TERM/KILL grace")
    observed,_=resource.getrlimit(resource.RLIMIT_AS)
    if observed==resource.RLIM_INFINITY or not 0<observed<=limits.broker_address_space_bytes:
        raise RuntimeError("broker actual AS is not prospectively bounded")
    limits.before_spawn()


@dataclass(frozen=True)
class ArchiveJob:
    artifact_id: str
    header: dict
    role: archive.RoleProfile
    encoder_limits: dict
    decoder_limits: archive.DecodeLimits


@dataclass(frozen=True)
class CaptureArchiveOutcome:
    receipt: custody.BoundFile
    status: str
    receipt_ledger_record: custody.BoundFile


def load_runtime_profile(profile_path: Path, *, expected: archive.PhysicalBinding,
                         bundle_root: Path, runtime_root: Path,
                         max_profile_bytes: int, deadline_ns: int) -> RuntimeProfile:
    """Load exact qualified implementation bytes, with explicit root namespaces.

    The document has no self hash. Its externally admitted byte hash becomes the
    archive header's implementation_profile_sha256. Runtime-relative Python and
    libraries resolve only beneath the supplied qualified hermetic runtime root;
    there is no search of host tools, PATH, or fallback dependency locations.
    """
    expected.validate()
    archive.uint(max_profile_bytes,"implementation profile byte bound",positive=True)
    if expected.size_bytes>max_profile_bytes:raise RuntimeError("implementation profile byte bound")
    roots={"bundle":Path(bundle_root),"runtime":Path(runtime_root)}
    for root in roots.values():
        if not root.is_absolute() or not root.is_dir() or any(p.is_symlink() for p in (root,*root.parents)):
            raise RuntimeError("implementation profile root must be explicit absolute nonsymlink directory")
    with archive.open_regular(profile_path) as stream:
        before=archive.file_stamp(os.fstat(stream.fileno()))
        raw=stream.read(max_profile_bytes+1)
        if (archive.PhysicalBinding(len(raw),hashlib.sha256(raw).hexdigest())!=expected
                or before!=archive.file_stamp(os.fstat(stream.fileno()))
                or before!=archive.file_stamp(Path(profile_path).stat(follow_symlinks=False))):
            raise RuntimeError("implementation profile exact binding changed")
    document=archive.parse_json(raw)
    if (set(document)!={"schema_version","policy_id","encoder","python","zstd_library","source_closure","options"}
            or document["schema_version"]!="cpu-prefetch-formal-archive-implementation-profile/1"
            or document["policy_id"]!=archive.POLICY_ID):
        raise RuntimeError("implementation profile schema/policy/fields")
    fixed=dict(zstd_version="1.5.7",compression_level=3,worker_threads=1,nbWorkers=0,
               checksum_flag=1,content_size_flag=1,dictionary_id_flag=0)
    options=document["options"]
    if not isinstance(options,dict) or set(options)!=set(fixed)|{"window_log"}:
        raise RuntimeError("implementation options field set")
    for key,value in fixed.items():
        if type(options[key]) is not type(value) or options[key]!=value:
            raise RuntimeError("implementation option differs: "+key)
    if type(options["window_log"]) is not int or not 10<=options["window_log"]<=31:
        raise RuntimeError("implementation explicit window bound")

    def image(value):
        if not isinstance(value,dict) or set(value)!={"location","path","size_bytes","sha256"}:
            raise RuntimeError("implementation image binding shape")
        relative=value["path"]
        if (value["location"] not in roots or not isinstance(relative,str) or not relative or "\x00" in relative
                or Path(relative).is_absolute() or ".." in Path(relative).parts
                or str(Path(relative))!=relative or relative=="."):
            raise RuntimeError("implementation image relative path")
        result=ImageBinding(roots[value["location"]]/relative,
            archive.uint(value["size_bytes"],"implementation image size",positive=True),
            archive.sha(value["sha256"],"implementation image hash"))
        actual=archive.hash_file(result.path,max_bytes=result.size_bytes,deadline_ns=deadline_ns)
        if actual!=archive.PhysicalBinding(result.size_bytes,result.sha256):
            raise RuntimeError("implementation actual image binding differs")
        return result

    encoder,python,library=(image(document[key]) for key in ("encoder","python","zstd_library"))
    if not isinstance(document["source_closure"],list) or not document["source_closure"]:
        raise RuntimeError("implementation source closure absent")
    modules=[]
    for item in document["source_closure"]:
        if not isinstance(item,dict) or set(item)!={"module","image"} or not isinstance(item["module"],str):
            raise RuntimeError("implementation source module shape")
        modules.append(ModuleBinding(item["module"],image(item["image"])))
    decoder=archive.DecoderProfile(expected.sha256,encoder.sha256,library.path,library.sha256,
                                  python.path,python.sha256,options["window_log"])
    result=RuntimeProfile(encoder,python,decoder,tuple(modules))
    _closure_bytes(result,deadline_ns)
    return result


def _jsonable(value):
    if isinstance(value,Path):return str(value)
    if isinstance(value,dict):return {k:_jsonable(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_jsonable(v) for v in value]
    return value


def _sealed_input(raw: bytes, label: str) -> int:
    fd = os.memfd_create(label,os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    try:
        if os.write(fd,raw)!=len(raw):raise RuntimeError("partial immutable input write")
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,_SEALS)
        readonly=os.open(f"/proc/self/fd/{fd}",os.O_RDONLY|os.O_CLOEXEC)
    finally:
        os.close(fd)
    return readonly


def _read_sealed(fd: int, maximum: int) -> bytes:
    if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&_SEALS!=_SEALS:
        raise RuntimeError("unsealed codec input/result")
    size=os.fstat(fd).st_size
    if not 0<size<=maximum:raise RuntimeError("codec input/result byte bound")
    raw=os.pread(fd,size,0)
    if len(raw)!=size:raise RuntimeError("short codec input/result")
    return raw


def _image_bytes(binding: ImageBinding, deadline: int) -> bytes:
    archive.uint(binding.size_bytes,"qualified image bytes",positive=True)
    archive.sha(binding.sha256,"qualified image SHA256")
    # All images have exact qualified sizes. Closure files are small and bounded
    # by the broker's explicit AS; binary hashing in _pin_image is streaming.
    with archive.open_regular(binding.path) as stream:
        before=archive.file_stamp(os.fstat(stream.fileno()))
        if before[2]!=binding.size_bytes:raise RuntimeError("qualified source size differs")
        raw=stream.read(binding.size_bytes+1)
        if (len(raw)!=binding.size_bytes or hashlib.sha256(raw).hexdigest()!=binding.sha256
                or before!=archive.file_stamp(os.fstat(stream.fileno()))
                or before!=archive.file_stamp(binding.path.stat(follow_symlinks=False))):
            raise RuntimeError("qualified source hash/identity differs")
    if time.monotonic_ns()>=deadline:raise RuntimeError("qualification binding deadline")
    return raw


def _closure_bytes(profile: RuntimeProfile, deadline: int) -> dict[str,tuple[ModuleBinding,bytes]]:
    modules={item.module:item for item in profile.source_closure}
    if len(modules)!=len(profile.source_closure) or "stage17_formal_archive_runtime_v1" not in modules:
        raise RuntimeError("duplicate/incomplete decoder source closure")
    root=modules["stage17_formal_archive_runtime_v1"].image.path.parent
    data={}
    for name,binding in modules.items():
        if not name.isidentifier() or binding.image.path!=root/(name+".py"):
            raise RuntimeError("decoder closure path/module differs")
        data[name]=(binding,_image_bytes(binding.image,deadline))
    for name,(_,raw) in data.items():
        tree=ast.parse(raw,filename=str(modules[name].image.path))
        for node in ast.walk(tree):
            imports=([entry.name.split(".")[0] for entry in node.names] if isinstance(node,ast.Import)
                     else [node.module.split(".")[0]] if isinstance(node,ast.ImportFrom) and node.module else [])
            for dependency in imports:
                if (root/(dependency+".py")).exists() and dependency not in data:
                    raise RuntimeError("missing qualified local import: "+dependency)
    return data


def _pin_image(binding: ImageBinding, deadline: int, stack: contextlib.ExitStack) -> int:
    stream=stack.enter_context(archive.open_regular(binding.path))
    before=archive.file_stamp(os.fstat(stream.fileno()))
    if before[2]!=binding.size_bytes:raise RuntimeError("executable size differs")
    digest=hashlib.sha256()
    sealed=os.memfd_create("stage17-qualified-executable",os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
    stack.callback(os.close,sealed)
    while True:
        if time.monotonic_ns()>=deadline:raise RuntimeError("executable hash deadline")
        block=stream.read(1024*1024)
        if not block:break
        digest.update(block)
        if os.write(sealed,block)!=len(block):raise RuntimeError("partial executable snapshot")
    if (digest.hexdigest()!=archive.sha(binding.sha256,"executable hash")
            or before!=archive.file_stamp(os.fstat(stream.fileno()))
            or before!=archive.file_stamp(binding.path.stat(follow_symlinks=False))):
        raise RuntimeError("pinned executable hash/identity differs")
    os.fchmod(sealed,0o500)
    fcntl.fcntl(sealed,fcntl.F_ADD_SEALS,_SEALS)
    readonly=os.open(f"/proc/self/fd/{sealed}",os.O_RDONLY|os.O_CLOEXEC)
    stack.callback(os.close,readonly)
    return readonly


class ColdArchiveRuntime:
    """Dedicated broker callable. No arbitrary argv/command execution surface."""
    def __init__(self, store: custody.ProgramStore, *, profile: RuntimeProfile, limits: RuntimeLimits | RetainedReadbackLimits):
        store._check()
        limits=replace(limits,deadline_ns=min(limits.deadline_ns,store.limits.deadline_ns))
        limits.validate()
        store.limits=replace(store.limits,deadline_ns=limits.final_deadline_ns)
        if (profile.encoder.sha256!=profile.decoder.encoder_sha256
                or profile.python.sha256!=profile.decoder.decoder_executable_sha256
                or profile.python.path!=profile.decoder.decoder_executable_path):
            raise RuntimeError("encoder/Python decoder profile bindings differ")
        self.store,self.profile,self.limits=store,profile,limits
        self.closure=_closure_bytes(profile,limits.final_deadline_ns)
        self.child_count=0
        self.last_transport=None

    def _run_fixed(self, kind: str, argv: list[str], fds: tuple[int,...], *,
                   monitored_outputs: tuple[tuple[int,int],...], file_size_limit: int) -> dict:
        # This is private; both callers construct exact fixed arguments and pin
        # the executable fd themselves. No user command/string reaches this seam.
        self.last_transport=None
        if kind not in ("encode","decode"):raise RuntimeError("unknown fixed codec operation")
        self.limits.validate()
        if self.child_count>=self.limits.max_children:raise RuntimeError("codec child budget exhausted")
        self.child_count+=1
        lease=supervisor.SupervisorLease()
        process=None
        failure=None
        cleanup=None
        console=bytearray()
        selector=selectors.DefaultSelector()
        lease.enter()  # fails closed if broker owns any unrelated/native child
        try:
            try:
                self.limits.before_spawn()
                def constrain():
                    resource.setrlimit(resource.RLIMIT_AS,(self.limits.codec_address_space_bytes,)*2)
                    resource.setrlimit(resource.RLIMIT_FSIZE,(file_size_limit,)*2)
                    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
                process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    pass_fds=fds,close_fds=True,shell=False,start_new_session=True,
                    env=dict(_ENVIRONMENT,LD_LIBRARY_PATH=str(self.profile.decoder.zstd_library_path.parent)),preexec_fn=constrain)
                for stream in (process.stdout,process.stderr):
                    os.set_blocking(stream.fileno(),False)
                    selector.register(stream,selectors.EVENT_READ)
                while selector.get_map():
                    self.limits.before_spawn()  # same absolute deadline, no extension
                    for fd,bound in monitored_outputs:
                        if os.fstat(fd).st_size>bound:raise RuntimeError("codec output exceeds FD byte bound")
                    remaining=(self.limits.final_deadline_ns-self.limits.cleanup_reserve_ns-time.monotonic_ns())/1e9
                    for key,_ in selector.select(max(0,min(remaining,0.05))):
                        data=os.read(key.fd,min(65536,self.limits.max_console_bytes-len(console)+1))
                        if not data:
                            selector.unregister(key.fileobj)
                            key.fileobj.close()
                        else:
                            console.extend(data)
                            if len(console)>self.limits.max_console_bytes:raise RuntimeError("codec stdout/stderr bound")
            except BaseException as exc:
                failure=exc
            finally:
                for key in tuple(selector.get_map().values()):key.fileobj.close()
                selector.close()
                if process is not None:
                    cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                        leader_wait_deadline_ns=min(time.monotonic_ns()+self.limits.cleanup_reserve_ns,self.limits.final_deadline_ns),
                        global_deadline_ns=self.limits.final_deadline_ns,identity_model=lease.identity_model)
        finally:
            lease.close(suppress=failure is not None)
        self.last_transport=dict(kind=kind,child_pid=process.pid if process else None,
            cleanup=_jsonable(asdict(cleanup)) if cleanup else None,console_hex=bytes(console).hex(),
            codec_address_space_bytes=self.limits.codec_address_space_bytes,
            deadline_monotonic_ns=self.limits.final_deadline_ns)
        if (cleanup is None or not cleanup.leader_reaped or not cleanup.process_group_gone
                or cleanup.descendants_detected_after_leader_exit or cleanup.cleanup_deadline_overrun):
            raise RuntimeError("codec cleanup not proven before deadline") from failure
        if failure is not None:raise RuntimeError("codec failed: "+str(failure)) from failure
        if cleanup.returncode!=0:raise RuntimeError("codec exited unsuccessfully: "+str(cleanup.returncode)+": "+bytes(console).decode("utf-8",errors="replace"))
        for fd,bound in monitored_outputs:
            if os.fstat(fd).st_size>bound:raise RuntimeError("codec final FD byte bound")
        return self.last_transport

    def _result(self, fd: int) -> tuple[bytes,dict]:
        fcntl.fcntl(fd,fcntl.F_ADD_SEALS,_SEALS)
        raw=_read_sealed(fd,self.limits.max_result_bytes)
        return raw,archive.parse_json(raw)

    def encode(self, job: ArchiveJob, staging: Path) -> tuple[archive.PhysicalBinding,bytes,dict]:
        if type(self.limits) is not RuntimeLimits:raise RuntimeError("offline readback grants no encode/custody authority")
        self.store._quiescent()
        source=self.store._sources.get(job.artifact_id)
        state=self.store._states.get(job.artifact_id)
        if (source is None or state is None or state["kind"]!="RESERVED"
                or staging!=self.store.root/"archives"/state["payload"]["staging_name"]):
            raise RuntimeError("encoder source/staging is not scoped to active custody")
        if set(job.encoder_limits)!=_ENCODER_LIMITS:raise RuntimeError("encoder limit field set")
        if job.encoder_limits["maximum_archive_bytes"]!=state["payload"]["maximum_archive_bytes"]:
            raise RuntimeError("encoder output ceiling differs from quota reservation")
        limits=dict(job.encoder_limits)
        limits["deadline_monotonic_ns"]=min(limits["deadline_monotonic_ns"],self.limits.final_deadline_ns-self.limits.cleanup_reserve_ns)
        plan=dict(identity={key:job.header[key] for key in _ENCODER_IDENTITY},limits=limits)
        raw=archive.canonical(plan)
        if len(raw)>self.limits.max_input_bytes:raise RuntimeError("encoder input byte bound")
        with contextlib.ExitStack() as stack:
            executable=_pin_image(self.profile.encoder,self.limits.final_deadline_ns,stack)
            source_stream=stack.enter_context(archive.open_regular(self.store.working/source.expected.file_name))
            target_fd=os.open(staging,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
            stack.callback(os.close,target_fd)
            plan_fd=_sealed_input(raw,"stage17-archive-plan")
            stack.callback(os.close,plan_fd)
            result_fd=os.memfd_create("stage17-archive-result",os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            stack.callback(os.close,result_fd)
            fds=(executable,source_stream.fileno(),target_fd,plan_fd,result_fd)
            argv=[f"/proc/self/fd/{executable}","--encode-stage17-archive-v1",
                "--source-fd",str(source_stream.fileno()),"--archive-fd",str(target_fd),
                "--plan-fd",str(plan_fd),"--result-fd",str(result_fd),
                "--plan-byte-limit",str(self.limits.max_input_bytes),"--result-byte-limit",str(self.limits.max_result_bytes)]
            try:
                outcome=self._run_fixed("encode",argv,fds,monitored_outputs=((target_fd,limits["maximum_archive_bytes"]),
                    (result_fd,self.limits.max_result_bytes)),file_size_limit=max(limits["maximum_archive_bytes"],self.limits.max_result_bytes))
            except BaseException as exc:
                cleanup=(self.last_transport or {}).get("cleanup")
                if cleanup and cleanup["leader_reaped"] and cleanup["process_group_gone"]:
                    fcntl.fcntl(result_fd,fcntl.F_ADD_SEALS,_SEALS)
                    size=os.fstat(result_fd).st_size
                    if size<=self.limits.max_result_bytes:
                        exc.codec_result_bytes=os.pread(result_fd,size,0)
                raise
            result_raw,result=self._result(result_fd)
            if (result.get("schema_version")!="cpu-prefetch-formal-archive-encoder-result/1"
                    or result.get("stop")!="COMPLETE_STAGING_SYNCED"
                    or result.get("observed_canonical_sha256")!=source.actual.sha256
                    or result.get("source_bytes_read")!=source.actual.size_bytes
                    or result.get("blocks_written")!=job.header["block_count"]):
                raise RuntimeError("actual encoder result differs from bound source")
            physical=archive.PhysicalBinding(result["archive_bytes_written"],result["observed_archive_sha256"])
            physical.validate()
            if physical.size_bytes!=os.fstat(target_fd).st_size:raise RuntimeError("encoder output size differs")
            return physical,result_raw,dict(outcome,request_sha256=hashlib.sha256(raw).hexdigest(),
                                          executable_sha256=self.profile.encoder.sha256,result_sha256=hashlib.sha256(result_raw).hexdigest())

    def readback(self, path: Path, *, expected_header: dict, role: archive.RoleProfile,
                 physical: archive.PhysicalBinding, profile: archive.DecoderProfile,
                 limits: archive.DecodeLimits) -> archive.VerifiedArchive:
        if type(self.limits) is not RuntimeLimits:raise RuntimeError("use explicit retained readback for offline analysis")
        self.store._quiescent()
        return self._readback(path,expected_header=expected_header,role=role,physical=physical,profile=profile,limits=limits)

    def readback_retained(self, path: Path, *, expected_header: dict, role: archive.RoleProfile,
                          physical: archive.PhysicalBinding, profile: archive.DecoderProfile,
                          limits: archive.DecodeLimits) -> archive.VerifiedArchive:
        if type(self.limits) is not RetainedReadbackLimits:raise RuntimeError("retained readback requires separate offline analysis limits")
        self.store._check()
        return self._readback(path,expected_header=expected_header,role=role,physical=physical,profile=profile,limits=limits)

    def _readback(self, path: Path, *, expected_header: dict, role: archive.RoleProfile,
                  physical: archive.PhysicalBinding, profile: archive.DecoderProfile,
                  limits: archive.DecodeLimits) -> archive.VerifiedArchive:
        if path.parent!=self.store.root/"archives" or profile!=self.profile.decoder:
            raise RuntimeError("decoder path/profile not scoped to current broker")
        limits=replace(limits,deadline_ns=min(limits.deadline_ns,self.limits.final_deadline_ns-self.limits.cleanup_reserve_ns))
        archive.validate_header(expected_header,role,profile,limits)
        request=dict(schema_version="cpu-prefetch-formal-archive-readback-request/1",path=str(path),
            expected_header=expected_header,role=asdict(role),physical=asdict(physical),
            profile=_jsonable(asdict(profile)),limits=asdict(limits))
        raw=archive.canonical(request)
        if len(raw)>self.limits.max_input_bytes:raise RuntimeError("decoder input bound")
        with contextlib.ExitStack() as stack:
            executable=_pin_image(self.profile.python,self.limits.final_deadline_ns,stack)
            source=stack.enter_context(archive.open_regular(path))
            request_fd=_sealed_input(raw,"stage17-archive-readback")
            stack.callback(os.close,request_fd)
            result_fd=os.memfd_create("stage17-archive-readback-result",os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
            stack.callback(os.close,result_fd)
            module_map={}
            module_fds=[]
            for name,(binding,source_bytes) in self.closure.items():
                fd=_sealed_input(source_bytes,"stage17-code-"+name)
                stack.callback(os.close,fd)
                module_fds.append(fd)
                module_map[name]=dict(fd=fd,path=str(binding.image.path),size_bytes=binding.image.size_bytes,sha256=binding.image.sha256)
            map_raw=archive.canonical(module_map)
            if len(map_raw)>self.limits.max_input_bytes:raise RuntimeError("sealed closure map bound")
            map_fd=_sealed_input(map_raw,"stage17-code-map")
            stack.callback(os.close,map_fd)
            argv=[f"/proc/self/fd/{executable}","-I","-B","-c",_BOOTSTRAP,"decode",
                str(map_fd),str(self.limits.max_input_bytes),str(request_fd),str(source.fileno()),str(result_fd),
                str(self.limits.max_input_bytes),str(self.limits.max_result_bytes)]
            self._run_fixed("decode",argv,(executable,source.fileno(),request_fd,result_fd,map_fd,*module_fds),
                monitored_outputs=((result_fd,self.limits.max_result_bytes),),file_size_limit=self.limits.max_result_bytes)
            result_raw,result=self._result(result_fd)
            if (set(result)!={"schema_version","request_sha256","proof","codec_address_space_bytes"}
                    or result["schema_version"]!="cpu-prefetch-formal-archive-readback-result/1"
                    or result["request_sha256"]!=hashlib.sha256(raw).hexdigest()
                    or result["codec_address_space_bytes"]!=self.limits.codec_address_space_bytes):
                raise RuntimeError("actual sealed decoder result/transport binding differs")
            value=result["proof"]
            proof=archive.VerifiedArchive(archive.PhysicalBinding(**value["physical"]),archive.PhysicalBinding(**value["canonical"]),
                value["header_sha256"],value["block_count"],tuple(value["file_identity"]),value["verified_at_unix_ns"])
            if (proof.physical!=physical or proof.canonical!=archive.PhysicalBinding(expected_header["canonical_size_bytes"],expected_header["canonical_sha256"])
                    or proof.header_sha256!=hashlib.sha256(archive.canonical(expected_header)).hexdigest()
                    or proof.block_count!=expected_header["block_count"]
                    or proof.file_identity!=archive.file_stamp(path.stat(follow_symlinks=False))):
                raise RuntimeError("decoder proof differs from immutable request/current artifact")
            self.last_transport.update(request_sha256=hashlib.sha256(raw).hexdigest(),
                executable_sha256=self.profile.python.sha256,result_sha256=hashlib.sha256(result_raw).hexdigest())
            return proof

    def archive_capture(self, checkpoint: custody.BoundFile, sources: tuple[custody.SourceBinding,...],
                        jobs: tuple[ArchiveJob,...], *, verify_checkpoint: Callable) -> CaptureArchiveOutcome:
        if type(self.limits) is not RuntimeLimits:raise RuntimeError("offline readback grants no encode/custody authority")
        if tuple(j.artifact_id for j in jobs)!=tuple(s.artifact_id for s in sources):
            raise RuntimeError("archive jobs must cover every exact source in original order")
        jobs=tuple(replace(job,decoder_limits=replace(job.decoder_limits,
            deadline_ns=min(job.decoder_limits.deadline_ns,self.limits.final_deadline_ns))) for job in jobs)
        for job,source in zip(jobs,sources):
            archive.validate_header(job.header,job.role,self.profile.decoder,job.decoder_limits)
            if (job.header["artifact_id"]!=source.artifact_id or job.header["canonical_size_bytes"]!=source.actual.size_bytes
                    or job.header["canonical_sha256"]!=source.actual.sha256):
                raise RuntimeError("archive job differs from actual source identity")
        self.store.begin_capture(checkpoint,sources,verify_checkpoint=verify_checkpoint)
        for job in jobs:
            try:
                stem=hashlib.sha256(job.artifact_id.encode()).hexdigest()
                stage=self.store.reserve_archive(job.artifact_id,staging_name=stem+".staging",
                    maximum_archive_bytes=job.encoder_limits["maximum_archive_bytes"])
                physical,result,transport=self.encode(job,stage)
                self.store.retain_metadata(stem+".encoder-result.json",result)
                self.store.append("CODEC_RESULT",job.artifact_id,transport)
                self.store.verify_and_publish(job.artifact_id,archive_name=stem+".cpfa",expected_header=job.header,
                    role=job.role,physical=physical,profile=self.profile.decoder,limits=job.decoder_limits,readback=self.readback)
                self.store.append("CODEC_RESULT",job.artifact_id,self.last_transport)
                self.store.release_working_copy(job.artifact_id,profile=self.profile.decoder,limits=job.decoder_limits,readback=self.readback)
                self.store.append("CODEC_RESULT",job.artifact_id,self.last_transport)
            except BaseException as exc:
                evidence=dict(transport=self.last_transport)
                failed_result=getattr(exc,"codec_result_bytes",None)
                if failed_result is not None:
                    try:evidence["encoder_result"]=asdict(self.store.retain_metadata(stem+".encoder-failure-result.bin",failed_result))
                    except BaseException:pass
                try:self.store.record_failure(job.artifact_id,operation="cold-archive",detail=str(exc),evidence=evidence)
                except BaseException:pass  # existing incomplete bytes remain; never repair/retry
                raise
        artifacts=[]
        for source in sources:
            state=self.store._states[source.artifact_id]
            artifacts.append(dict(logical=dict(file_name=source.expected.file_name,**asdict(source.actual)),
                expected_logical=asdict(source.expected),failure_receipt=asdict(source.failure_receipt) if source.failure_receipt else None,
                artifact_id=source.artifact_id,released_record=asdict(self.store.ledger_binding(state)),
                archive_name=state["payload"]["archive_name"],physical=state["payload"]["physical"]))
        status=self.store.capture_archive_status(sources)
        receipt_name,receipt=self.store.capture_archive_receipt(checkpoint,artifacts,status)
        binding=self.store.retain_custody_receipt(receipt_name,archive.canonical(receipt))
        self.limits.before_spawn()  # no normal continuation at/after authority deadline
        return CaptureArchiveOutcome(binding,status,self.store.ledger_binding())


def _decode_child(request_fd: int, archive_fd: int, result_fd: int, input_limit: int, result_limit: int):
    raw=_read_sealed(request_fd,input_limit)
    request=archive.parse_json(raw)
    if (set(request)!={"schema_version","path","expected_header","role","physical","profile","limits"}
            or request["schema_version"]!="cpu-prefetch-formal-archive-readback-request/1"):
        raise RuntimeError("readback request shape/version")
    profile=dict(request["profile"])
    for name in ("zstd_library_path","decoder_executable_path"):profile[name]=Path(profile[name])
    proof=archive.verify_archive(Path(request["path"]),expected_header=request["expected_header"],
        role=archive.RoleProfile(**request["role"]),physical=archive.PhysicalBinding(**request["physical"]),
        profile=archive.DecoderProfile(**profile),limits=archive.DecodeLimits(**request["limits"]),archive_fd=archive_fd)
    output=archive.canonical(dict(schema_version="cpu-prefetch-formal-archive-readback-result/1",
        request_sha256=hashlib.sha256(raw).hexdigest(),proof=_jsonable(asdict(proof)),
        codec_address_space_bytes=resource.getrlimit(resource.RLIMIT_AS)[0]))
    if len(output)>result_limit:raise RuntimeError("decoder result exceeds bound")
    if os.pwrite(result_fd,output,0)!=len(output):raise RuntimeError("partial decoder result write")
    os.fsync(result_fd)
