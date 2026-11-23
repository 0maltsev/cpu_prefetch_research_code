"""Owned S180 dynamic qualification export through the accepted typed builder.

No CLI, hardware collector, retry, profile qualification or EXT008 permission.
The qualified operator supplies its actual completed Q15 owner and fixed package
paths after the full prospective ETA gate. Original data and methods stay fixed.
"""
from __future__ import annotations
import contextlib
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import threading
import time
from jsonschema import Draft202012Validator,FormatChecker

import check_software_prefetch_mapping_codegen as codegen
import stage17_s180_q15_session_v1 as q15

archive=q15.archive
runtime=q15.runtime
supervisor=q15.supervisor
ROOT=q15.ROOT.parent/'qualification-evidence'
SCHEMA='cpu-prefetch-stage17-s180-dynamic-qualification-evidence/1'
HELPER_SHA='6b8898238157e4d589615cbc6c57ced54aa143b403ef66bd337cab4960f3a918'
HELPER_SIZE=700568
SUPPORT_REVISION='d024758bc8c9436d55dcb2bfb530d9c098410cab'
SUPPORT_PINS={
    'clean-support-build.json':'18ad4583f8d3bc8b85e037eac6d9dfffc51a416435ff53d0d90987d653813b0a',
    'gcc-clean-software_prefetch_t0_mapping_codegen_report.json':'9c0b73f8f83c4afb20d6137b4b36a49369709686a20bbf8b0c52b19ab4c41949',
    'clang-clean-software_prefetch_t0_mapping_codegen_report.json':'60871b0e4c428e55633e6a2d21de162708d600563a81a8269aacbeff9dca1757'}
SOURCES={
    'RUNTIME_ATOMIC_LAYOUT':'q15-r-atomic-layout-raw-v1.json',
    'ACTUAL_CPU_MIGRATION':'q15-r-cpu-migration-raw-v1.json',
    'ADDRESS_RESIDENCY':'q15-r-address-residency-raw-v1.json',
    'SOFTWARE_PREFETCH_MAPPING':'q15-r-software-prefetch-raw-v1.json'}
FILE_BYTES=65536
CLEANUP_NS=10*10**9
AUTHOR_NS=10*10**9
_TOKEN=object()


class EvidenceError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise EvidenceError('S180 qualification evidence: '+message)


def _before(deadline):require(time.monotonic_ns()<deadline,'original qualification/export deadline expired')


def _bytes(path):return q15.compaction._root_file(path,FILE_BYTES)


def _binding(path,raw):return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _bound(row):
    raw=_bytes(Path(row['path']))
    require(len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'original producer evidence changed')
    return raw


def _codegen(root):
    """Fixed D338 support leaf; its historical PC locators are never executed."""
    root=Path(root)
    require(root.is_absolute() and root.resolve(strict=True)==root,'canonical qualified support root required')
    st=root.stat();require(st.st_uid==0 and not st.st_mode&0o022,'protected support directory required')
    data={};bindings=[]
    for name,sha in SUPPORT_PINS.items():
        path=root/name;raw=_bytes(path)
        require(hashlib.sha256(raw).hexdigest()==sha,'exact clean D338 support evidence differs')
        data[name]=json.loads(raw);bindings.append(_binding(path,raw))
    metadata=data['clean-support-build.json']
    require(metadata['source_revision']==SUPPORT_REVISION and metadata['source_clean_observed'] is True
        and metadata['measurement_source_revision']==q15.environment.NATIVE_REVISION,
        'actual support/native source identity differs')
    source_root=Path(__file__).resolve().parents[1]
    for compiler,identity in (('gcc','GNU'),('clang','Clang')):
        row=metadata['builds'][compiler];build=row['metadata']
        require(build['source_revision']==SUPPORT_REVISION and build['source_dirty'] is False
            and build['compiler']['id']==identity and build['build_type']=='Release','actual two-compiler build differs')
        for kind in ('probe','mutant'):
            path=root/(compiler+'-'+kind);raw=_bytes(path)
            require(len(raw)==row[kind]['size_bytes'] and hashlib.sha256(raw).hexdigest()==row[kind]['sha256'],
                'actual support probe/mutant bytes differ')
            bindings.append(_binding(path,raw))
        codegen.validate_t0_report(data[compiler+'-clean-software_prefetch_t0_mapping_codegen_report.json'],
            binary=root/(compiler+'-probe'),mutant=root/(compiler+'-mutant'),source_root=source_root)
    return bindings,dict(gcc_codegen_passed=True,clang_codegen_passed=True,gnu_objdump_passed=True,llvm_objdump_passed=True)


def _schema():
    raw=(Path(__file__).resolve().parents[1]/'config/schemas/qualification-evidence-v3.schema.json').read_bytes()
    schema=json.loads(raw);Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema,format_checker=FormatChecker())


def _constrain():
    os.umask(0o077)
    for kind,value in ((resource.RLIMIT_AS,q15.clocks.AS_BYTES),(resource.RLIMIT_FSIZE,FILE_BYTES),
        (resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(value,value));require(resource.getrlimit(kind)==(value,value),'author child limit readback differs')


def _author(executable,raw,output,arguments,deadline,state):
    """Fixed pure-JSON helper, sealed original input and exclusive output FD."""
    _before(deadline-CLEANUP_NS);process=None;cleanup=None;failure=None;console=bytearray();handlers={}
    lease=supervisor.SupervisorLease();end=min(deadline-CLEANUP_NS,time.monotonic_ns()+AUTHOR_NS)
    def interrupted(number,frame):raise EvidenceError('evidence author interrupted by signal '+str(number))
    with contextlib.ExitStack() as stack:
        source=runtime._sealed_input(raw,'s180-original-qualification-raw');stack.callback(os.close,source)
        fd=os.open(output,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600);stack.callback(os.close,fd)
        require(max(executable,source,fd)<128,'author inherited descriptors exceed fixed limit')
        selector=selectors.DefaultSelector();stack.callback(selector.close)
        lease.enter()
        try:
            for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):handlers[number]=signal.signal(number,interrupted)
            try:
                process=subprocess.Popen([f'/proc/self/fd/{executable}','--raw',f'/proc/self/fd/{source}',
                    '--output',f'/proc/self/fd/{fd}',*arguments],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,pass_fds=(executable,source,fd),close_fds=True,start_new_session=True,
                    preexec_fn=_constrain,env=dict(PATH='/usr/bin:/bin',LANG='C',LC_ALL='C',TZ='UTC'))
                for stream in (process.stdout,process.stderr):
                    os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ)
                exited=False;diagnostics=[]
                while not exited or selector.get_map():
                    _before(end);require(os.fstat(fd).st_size<=FILE_BYTES,'author output exceeded bound')
                    exited=supervisor._peek_leader_exit_held(process.pid,diagnostics) is not None
                    for key,_ in selector.select(.02):
                        block=os.read(key.fd,min(4096,q15.CONSOLE_BYTES-len(console)+1))
                        if block:
                            console.extend(block);require(len(console)<=q15.CONSOLE_BYTES,'author console exceeded bound')
                        else:selector.unregister(key.fileobj)
            except BaseException as error:failure=error
            finally:
                def during_cleanup(number,frame):
                    nonlocal failure
                    failure=failure or EvidenceError('signal during evidence-author cleanup')
                for number in handlers:signal.signal(number,during_cleanup)
                if process is not None:
                    try:
                        cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                            leader_wait_deadline_ns=min(deadline,time.monotonic_ns()+CLEANUP_NS),
                            global_deadline_ns=min(deadline,time.monotonic_ns()+CLEANUP_NS),identity_model=lease.identity_model)
                        require(cleanup.leader_reaped and cleanup.process_group_gone and cleanup.returncode==0
                            and not cleanup.descendants_detected_after_leader_exit and not cleanup.cleanup_deadline_overrun
                            and not cleanup.leader_wait_timed_out,'author failure or incomplete/abnormal cleanup')
                    except BaseException as error:failure=failure or error
                    for stream in (process.stdout,process.stderr):stream.close()
                state['last_transport']=dict(child_pid=None if process is None else process.pid,
                    cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),console_hex=console.hex())
                os.fsync(fd)
        finally:
            for number,handler in handlers.items():signal.signal(number,handler)
            lease.close(suppress=failure is not None)
        if failure is not None:raise failure
        _before(deadline)
        return state['last_transport']


class _VerifiedEvidence:
    def __init__(self,*,token,owner,helper,support_root,receipt,files):
        require(token is _TOKEN,'actual verified publication required')
        self.owner=owner;self.helper=helper;self.support_root=Path(support_root);self.pid=os.getpid();self.failed=False
        self._receipt=archive.canonical(receipt);self._files=archive.canonical(dict(files=files))
        st=ROOT.stat(follow_symlinks=False);self._directory=(st.st_dev,st.st_ino)

    def proof(self,*,plan_sha256):
        try:
            require(self.pid==os.getpid() and not self.failed,'evidence ownership failed; no retry')
            original=self.owner.proof(plan_sha256=plan_sha256)
            st=ROOT.stat(follow_symlinks=False)
            require(stat.S_ISDIR(st.st_mode) and st.st_uid==0 and stat.S_IMODE(st.st_mode)==0o700
                and (st.st_dev,st.st_ino)==self._directory,'original export directory changed')
            rows=archive.parse_json(self._files)['files']
            require({str(p) for p in ROOT.iterdir()}=={r['path'] for r in rows},'original export inventory changed')
            for row in rows:_bound(row)
            receipt=archive.parse_json(self._receipt);_bound(receipt)
            _codegen(self.support_root)
            require(archive.hash_file(self.helper.path,max_bytes=self.helper.size_bytes,
                deadline_ns=min(original['window_binding']['end_monotonic_ns'],time.monotonic_ns()+60*10**9))
                ==archive.PhysicalBinding(self.helper.size_bytes,self.helper.sha256),'original builder image changed')
            self.owner.proof(plan_sha256=plan_sha256)
            return dict(schema_version=SCHEMA,plan_sha256=plan_sha256,window_binding=original['window_binding'],
                qualification_evidence=receipt,qualification_sha256=receipt['sha256'],
                base_resolutions=original['base_resolutions'],measurement_runtime_binding=original['runtime_binding'],
                qualification_profile_sha256=original['release_binding']['source_resolution_sha256'],
                dynamic_qualification_verified=True,envelope_count=10,full_ext008_admission=False,
                original_action_deadline_extended=False,execution_authority=False,phase18_authority=False)
        except BaseException:
            self.failed=True;self.owner.failed=True;self.owner.prepared.failed=True
            self.owner.prepared.owner._qualification_failed=True
            raise


def publish(*,completed_q15,helper,support_root):
    """One bounded actual export, before the original qualification deadline."""
    require(type(completed_q15) is q15._CompletedQ15,'actual completed Q15 owner required')
    state={}
    try:return _publish(completed_q15,helper,support_root,state)
    except BaseException as error:
        completed_q15.failed=True;completed_q15.prepared.failed=True
        completed_q15.prepared.owner._qualification_failed=True
        if 'directory' in state and ROOT.exists():
            st=ROOT.stat(follow_symlinks=False)
            if (st.st_dev,st.st_ino)==state['directory'] and not os.path.lexists(ROOT/'index.json'):
                try:
                    q15._save(ROOT/'index.json',dict(schema_version=SCHEMA,status='STOPPED',
                        plan_sha256=state['plan_sha256'],window_binding=state['window_binding'],
                        current_source=state.get('current_source'),last_transport=state.get('last_transport'),
                        failure=str(error)[:4096],execution_authority=False,phase18_authority=False))
                except BaseException as publication:raise error from publication
        raise


def _publish(owner,helper,support_root,state):
    context=archive.parse_json(owner.prepared._context);family=context['plan_sha256']
    proof=owner.proof(plan_sha256=family);deadline=proof['qualification_deadline_monotonic_ns'];_before(deadline-CLEANUP_NS)
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and len(list(Path('/proc/self/task').iterdir()))==1,'single-threaded owned evidence author required')
    require(type(helper) is runtime.ImageBinding and helper.sha256==HELPER_SHA and helper.size_bytes==HELPER_SIZE,
        'exact clean qualification builder required')
    require(ROOT.parent==q15.ROOT.parent and ROOT.parent.resolve(strict=True)==ROOT.parent,'fixed export parent required')
    support,flags=_codegen(support_root);schema=_schema()
    require(owner.prepared.clock_owner.image.sha256==q15.compaction.CLOCK_SHA
        and owner.prepared.clock_owner.image.size_bytes==q15.compaction.CLOCK_SIZE,'exact original clock producer required')
    raw_files=proof['files'];read=json.loads(_bound(raw_files['stage17-q15-r-result-v4.json']))
    clock=owner.prepared.clock_owner
    bindings=archive.parse_json(clock._bindings)['bindings'];originals={row['path']:row for row in bindings}
    completion=json.loads(_bound(archive.parse_json(clock._completion)))
    require(len(bindings)==5 and completion['pair_results']==bindings[1:]
        and completion['clock_pairs_qualified'] is True and completion['plan_sha256']==family
        and completion['window_binding']==proof['window_binding'],'complete original clock result/raw family required')
    inputs=[]
    for pair in ('near','far'):
        for kind,name in SOURCES.items():
            inputs.append((pair,kind,raw_files[name],read['completed_at_utc'],proof['session_id'],owner.image.sha256))
        result_path=str(q15.clocks.ROOT/pair/'result.json');raw_path=str(q15.clocks.ROOT/pair/'clock-raw.json')
        require(result_path in originals and raw_path in originals,'original clock pair evidence absent')
        result=json.loads(_bound(originals[result_path]));raw=json.loads(_bound(originals[raw_path]))
        require(result['status']=='CLOCK_PAIR_QUALIFIED' and result['pair']==pair
            and result['plan_sha256']==family and result['window_binding']==proof['window_binding']
            and result['worker_sha256']==clock.image.sha256 and result['raw']==originals[raw_path]
            and proof['qualification_started_monotonic_ns']<=result['started_monotonic_ns']
                <=result['completed_monotonic_ns']<=proof['qualification_deadline_monotonic_ns'],
            'original clock pair lineage/deadline differs')
        q15.clocks.verify_raw(raw,pair)
        inputs.append((pair,'SELECTED_PAIR_CLOCK',originals[raw_path],result['completed_at_utc'],
            'S180-CLOCK-'+family+'-'+pair,clock.image.sha256))
    q15.clocks._mkdir(ROOT)  # Never adopts or erases an existing/partial export.
    st=ROOT.stat();state.update(directory=(st.st_dev,st.st_ino),plan_sha256=family,window_binding=proof['window_binding'])
    published=[]
    with contextlib.ExitStack() as stack:
        executable=runtime._pin_image(helper,deadline,stack)
        for pair,kind,source,captured,binding_id,producer in inputs:
            owner.proof(plan_sha256=family);_before(deadline-CLEANUP_NS)
            path=ROOT/(pair+'-'+kind+'.json');source_id=proof['qualification_id']+':'+source['sha256']
            identity=dict(artifact_id=proof['qualification_id']+':'+pair+':'+kind,stand_id=proof['stand_id'],
                binding_id=binding_id,source_revision=q15.environment.NATIVE_REVISION,binary_sha256=producer,
                captured_at_utc=captured,worker_pair=pair,cpu_pair_selection_id='CPU-PREFETCH-V5-P0-NEAR-0-1-FAR-0-8-v1',
                source_artifact_id=source_id,kind=kind)
            if kind=='SOFTWARE_PREFETCH_MAPPING':identity.update({k:str(v).lower() for k,v in flags.items()})
            arguments=[]
            for key,value in identity.items():arguments.extend(('--'+key.replace('_','-'),value))
            state.update(current_source=source,last_transport=None)
            transport=_author(executable,_bound(source),path,arguments,deadline,state)
            raw=_bytes(path);document=archive.parse_json(raw);schema.validate(document)
            for key in ('artifact_id','stand_id','binding_id','source_revision','binary_sha256','captured_at_utc','kind'):
                require(document[key]==identity[key],'typed envelope producer identity differs')
            require(document['eligible'] is True and document['schema_version']=='cpu-prefetch-qualification-evidence/3'
                and document['sources']==[dict(artifact_id=source_id,sha256=source['sha256'])]
                and document['producer_cpu']==0 and document['consumer_cpu']==(1 if pair=='near' else 8),
                'typed envelope failed or changed source/pair')
            if kind=='SOFTWARE_PREFETCH_MAPPING':
                require(document['details']['mapping_id']==codegen.T0_MAPPING,'typed mapping differs')
            published.append(dict(pair=pair,kind=kind,envelope=_binding(path,raw),source=source,transport=transport))
    owner.proof(plan_sha256=family);_before(deadline)
    # Q15's21 files +10 envelopes +1 index, with two directories, fit D337's
    # unchanged4MiB/40-inode external reservation. No new archive quota.
    require(len(raw_files)==21 and len(published)==10,'closed successful evidence family differs')
    index=dict(schema_version=SCHEMA,status='DYNAMIC_QUALIFICATION_VERIFIED',plan_sha256=family,window_binding=proof['window_binding'],
        base_resolutions=proof['base_resolutions'],
        q15_terminal=raw_files['terminal.json'],q15_preparation=raw_files['preparation.json'],
        measurement_runtime_binding=proof['runtime_binding'],
        qualification_profile_sha256=proof['release_binding']['source_resolution_sha256'],
        clock_completion=archive.parse_json(clock._completion),
        qualified_measurement_source_revision=q15.environment.NATIVE_REVISION,
        evidence_builder=dict(size_bytes=helper.size_bytes,sha256=helper.sha256),support=support,envelopes=published,
        completed_monotonic_ns=time.monotonic_ns(),qualification_deadline_monotonic_ns=deadline,
        dynamic_qualification_verified=True,full_ext008_admission=False,execution_authority=False,phase18_authority=False)
    receipt=q15._save(ROOT/'index.json',index)
    files=[r['envelope'] for r in published]+[receipt]
    require(sum(r['size_bytes']+4096 for r in (*raw_files.values(),*files))+8192<=q15.METADATA_BYTES
        and len(raw_files)+len(files)+2<=q15.METADATA_INODES,'shared Q15/export metadata reservation exceeded')
    result=_VerifiedEvidence(token=_TOKEN,owner=owner,helper=helper,support_root=support_root,receipt=receipt,files=files)
    result.proof(plan_sha256=family);_before(deadline)
    return result
