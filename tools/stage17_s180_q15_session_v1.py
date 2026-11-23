"""Owned S180 persistent Q15-R/W; only the qualified stand operator calls this.

No CLI, experiment launcher, profile qualification, retry or test backend.
The caller authenticates original-seven replay and the complete operator/profile
before preparation, and supplies its fixed owner-signing callable, never one
chosen by input data. Scientific eligibility is separate from software transport.
"""
from __future__ import annotations

import contextlib
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import selectors
import signal
import stat
import subprocess
import threading
import time

from jsonschema import Draft202012Validator,FormatChecker
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
import stage17_s180_clock_qualification_v1 as clocks
import stage17_s180_compaction_v1 as compaction
import stage17_s180_environment_v1 as environment
import stage17_s180_q15_authority_v1 as authority

ROOT=authority.ROOT
CACHE=Path('/sys/devices/system/cpu/cpu0/cache/index3')
FILE_BYTES=65536
TOTAL_FILES=32
METADATA_BYTES=4*1024**2
METADATA_INODES=40
CONSOLE_BYTES=16384
CLEANUP_NS=120*10**9
WRITE_NS=180*10**9
SCHEMA='cpu-prefetch-stage17-s180-q15-session/1'
MAPPING='INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1'
_TOKEN=object()
ARTIFACTS={
    'Q15-R':(
        ('Q15_R_READ_ONLY_PRESTATE','q15-r-output-v3.json','stage17-q15-r-output-v3.schema.json'),
        ('Q15_R_ATOMIC_LAYOUT_RAW','q15-r-atomic-layout-raw-v1.json','stage17-q15-r-atomic-layout-raw-v1.schema.json'),
        ('Q15_R_ADDRESS_RESIDENCY_RAW','q15-r-address-residency-raw-v1.json','stage17-q15-r-address-residency-raw-v1.schema.json'),
        ('Q15_R_SOFTWARE_PREFETCH_RAW','q15-r-software-prefetch-raw-v1.json','stage17-q15-r-software-prefetch-raw-v2.schema.json'),
        ('Q15_R_CPU_MIGRATION_RAW','q15-r-cpu-migration-raw-v1.json','stage17-q15-r-cpu-migration-raw-v1.schema.json')),
    'Q15-W':(('Q15_W_TRANSACTION','q15-w-output-v3.json','stage17-q15-w-output-v3.schema.json'),)}


class SessionError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise SessionError('S180 Q15: '+message)


def _before(deadline):require(time.monotonic_ns()<deadline,'original qualification/action deadline expired')


def _read(path):
    raw=compaction._root_file(path,FILE_BYTES)
    return archive.parse_json(raw),dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _save(path,value):
    raw=archive.canonical(value);require(len(raw)<=FILE_BYTES,'bounded Q15 metadata required')
    compaction._save(path,value)
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _save_bytes(path,raw):
    require(type(raw) is bytes and 0<len(raw)<=FILE_BYTES,'bounded Q15 input/signature required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        require(os.write(fd,raw)==len(raw),'short Q15 input publication');os.fsync(fd)
    finally:os.close(fd)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _schemas():
    root=Path(__file__).resolve().parents[1]/'config/schemas'
    names={s for entries in ARTIFACTS.values() for _,_,s in entries}|{'stage17-phase-action-result-v4.schema.json'}
    result={}
    for name in names:
        raw=compaction._read(root/name,FILE_BYTES);value=json.loads(raw)
        Draft202012Validator.check_schema(value)
        result[name]=(value,Draft202012Validator(value,format_checker=FormatChecker()))
    return result


def _result(verified,validators):
    request=verified.request();action=request['action_id']
    result,binding=_read(ROOT/('stage17-q15-'+('r' if action=='Q15-R' else 'w')+'-result-v4.json'))
    validators['stage17-phase-action-result-v4.schema.json'][1].validate(result)
    for key in ('request_id','action_id','stand_id','authorization_id','attempt_id','runtime_binding',
        'release_binding','predecessor_resolutions','synthetic_test_only','phase18_authority'):
        require(result[key]==request[key] and type(result[key]) is type(request[key]),'native result lineage differs: '+key)
    require(result['request_sha256']==authority.pilot.sha(verified.request_bytes)
        and result['authorization_sha256']==authority.pilot.sha(verified.authorization_bytes)
        and result['result_id']==request['attempt_id']+':result'
        and result['quarantined'] is False,'native result request/authority identity differs')
    require(result['terminal_state']==('Q15_R_READ_ONLY_COMPLETE' if action=='Q15-R' else 'Q15_W_RESTORED_COMPLETE')
        and result['restoration_verified'] is (action=='Q15-W'),'native terminal state differs')
    entries=ARTIFACTS[action];observed=result['artifacts']
    require(len(observed)==len(entries) and len({r['file_name'] for r in observed})==len(entries),'native output family expanded/duplicated')
    documents={};bindings=[binding]
    for role,name,schema in entries:
        rows=[r for r in observed if r['role']==role and r['file_name']==name]
        require(len(rows)==1 and rows[0]['media_type']=='application/json','fixed Q15 artifact identity differs')
        document,bound=_read(ROOT/name);row=rows[0]
        require(row['sha256']==bound['sha256'] and row['size_bytes']==bound['size_bytes']
            and row['schema_identity']==document['schema_version'],'Q15 original artifact bytes differ')
        validators[schema][1].validate(document);documents[role]=document;bindings.append(bound)
    return result,documents,bindings


def _read_gate(documents,context,authorization_sha):
    value=documents['Q15_R_READ_ONLY_PRESTATE'];inputs=context['action_inputs']
    for name in ('qualification_id','attempt_id','session_id'):require(value[name]==inputs[name],'Q15-R input lineage differs')
    require(value['authorization_sha256']==authorization_sha and value['cpu_family']==6 and value['cpu_model']==62
        and value['mapping_id']==MAPPING,'Q15-R source/model identity differs')
    plan=inputs['probe_platform_binding'];pages=2*plan['verified_local_llc_bytes']//4096
    require(value['buffer_size_bytes']==pages*4096,'exact original Q15 working set differs')
    for role in ('regular_probe','pointer_probe'):
        require(value[role]['minor_faults']==value[role]['major_faults']==0,'Q15-R counted faults')
    require(value['regular_probe']['counter_value']>0,'H0 regular stream cannot distinguish the required counter')
    for role,raw in documents.items():
        if role=='Q15_R_READ_ONLY_PRESTATE':continue
        require(raw['session_id']==context['session_id'] and raw['qualification_id']==context['qualification_id'],
            'raw Q15-R session/qualification differs')
    atomic=documents['Q15_R_ATOMIC_LAYOUT_RAW']
    for name,wanted in dict(pointer_atomic_width_bytes=8,pointer_atomic_alignment_bytes=8,
        termination_atomic_width_bytes=4,termination_atomic_alignment_bytes=4,cache_line_bytes=64,
        pointer_atomic_runtime_lock_free=True,termination_atomic_runtime_lock_free=True,queue_layout_passed=True,
        ownership_lines_separated=True,termination_dedicated_line=True).items():
        require(type(atomic[name]) is type(wanted) and atomic[name]==wanted,'runtime atomic/layout failure: '+name)
    residency=documents['Q15_R_ADDRESS_RESIDENCY_RAW']
    require(residency['mechanism_id']=='LINUX_MOVE_PAGES_PER_PAGE_NUMA_NODE_QUERY'
        and len(residency['regions'])==2,'original Q15 residency observation family differs')
    for region,name in zip(residency['regions'],('regular_stream_probe_buffer','pointer_dependent_probe_buffer'),strict=True):
        require(region==dict(region=name,expected_node=0,before_page_count=pages,during_page_count=pages,
            after_page_count=pages,unavailable_page_count=0,wrong_node_page_count=0,migrated_page_count=0),
            'Q15-R residency failure or footprint mismatch')
    cpu=documents['Q15_R_CPU_MIGRATION_RAW']
    require(cpu['expected_cpu']==0 and cpu['samples']==[dict(probe=probe,point=point,cpu=0)
        for probe in ('regular_stream','pointer_dependent') for point in ('entry','exit')]
        and cpu['singleton_affinity']==dict(regular_stream=True,pointer_dependent=True),'Q15-R CPU/migration failure')
    prefetch=documents['Q15_R_SOFTWARE_PREFETCH_RAW']
    require(prefetch['mapping_id']=='X86-64-PREFETCHT0-ONLY-v1' and prefetch['observed_cpu']==0,
        'fixed stand software-prefetch mapping differs')
    for role in ('producer','consumer'):
        require(prefetch[role+'_maximum_extended_leaf']>=0x80000001
            and prefetch[role+'_extended_leaf_ecx']&0x100==0
            and prefetch[role+'_prfchw_supported'] is False,'raw PRFCHW observation differs from the stand mapping')
    return value


def _write_gate(value,context,authorization_sha):
    inputs=context['action_inputs']
    for key in ('q15_r_attempt_sha256','q15_r_result_sha256','session_id'):
        require(value[key]==inputs[key],'Q15-W exact R/session lineage differs')
    require(value['authorization_sha256']==authorization_sha,'Q15-W authorization differs')
    expected=inputs['prestate']
    require(value['restore_readback']==expected and value['apply_readback']==[
        dict(cpu=row['cpu'],complete_value_hex=f"{int(row['complete_value_hex'],16)|15:016x}") for row in expected],
        'Q15-W exact apply/restore readbacks differ')
    # Existing native ADR0150 tolerance, not a new zero-counter requirement.
    for role in ('regular_probe','pointer_probe'):
        require(value[role]['counter_value']<=2000,'Q15-W accepted native counter tolerance exceeded')


def _platform():
    values={name:compaction._read(CACHE/name,128).decode('ascii').strip() for name in ('level','type','size','coherency_line_size')}
    require(values['level']=='3' and values['type']=='Unified' and values['coherency_line_size']=='64'
        and re.fullmatch('[1-9][0-9]*K',values['size']) is not None,'observed CPU0 LLC geometry unavailable')
    require(os.sysconf('SC_PAGE_SIZE')==4096,'observed Q15 base page differs')
    llc=int(values['size'][:-1])*1024;require(llc%4096==0,'observed LLC page geometry differs')
    return dict(cpu=0,numa_node=0,verified_local_llc_bytes=llc,verified_base_page_bytes=4096),values


class _PreparedQ15:
    def __init__(self,*,token,owner,clock_owner,base,context,validators,preparation):
        require(token is _TOKEN,'actual Q15 preparation required')
        self.owner=owner;self.clock_owner=clock_owner;self.base=copy.deepcopy(base)
        self._context=archive.canonical(context);self.validators=validators;self.preparation=preparation
        self.pid=os.getpid();self.failed=False;self.used=False

    def _guard(self):
        try:return self._checked_guard()
        except BaseException:
            self.failed=True;self.owner._qualification_failed=True
            raise

    def _checked_guard(self):
        require(self.pid==os.getpid() and not self.failed,'Q15 preparation failed or belongs to another process')
        context=archive.parse_json(self._context);self.owner._guard(context['plan_sha256'])
        proof=self.clock_owner.proof(plan_sha256=context['plan_sha256'])
        require(proof['qualification_deadline_monotonic_ns']==context['qualification_deadline_monotonic_ns']
            and proof['qualification_started_monotonic_ns']==context['qualification_started_monotonic_ns'],
            'original clock qualification budget differs')
        _before(context['qualification_deadline_monotonic_ns'])
        st=ROOT.stat(follow_symlinks=False);root=context['evidence_root_binding']
        require(stat.S_ISDIR(st.st_mode) and st.st_uid==0 and stat.S_IMODE(st.st_mode)==0o700
            and [st.st_dev,st.st_ino]==[root['device'],root['inode']],'original Q15 directory changed')
        raw=compaction._root_file(ROOT/'preparation.json',FILE_BYTES)
        require(hashlib.sha256(raw).hexdigest()==self.preparation['sha256'],'original Q15 preparation changed')
        return context

    def unsigned_authorization(self):return self._unsigned(self._guard())

    def _unsigned(self,context):
        self._guard()
        rows=[authority.pilot.binding(self.base.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,8)]
        epoch=time.time_ns()//10**9;remaining=context['qualification_deadline_monotonic_ns']-time.monotonic_ns()
        phase='R' if context['action_id']=='Q15-R' else 'W';prefix='S180-Q15-'+context['plan_sha256']
        return dict(**{k:copy.deepcopy(context[k]) for k in authority.COMMON},schema_version=authority.SCHEMA,
            authorization_id=prefix+'-'+phase+'-AUTH',request_id=prefix+'-'+phase+'-REQUEST',attempt_id=prefix+'-'+phase+'-ATTEMPT',
            actor=self.base.resolutions['S17-EXT-003'].semantic_context['trust']['measurements']['principal'],
            trust_context=dict(ext002_resolution=rows[1],ext003_resolution=rows[2]),base_resolutions=rows,
            issued_at_epoch_seconds=epoch-1,expires_at_epoch_seconds=epoch+(remaining+10**9-1)//10**9+2,
            permission_scope=copy.deepcopy(authority.PERMISSIONS),synthetic_test_only=False,phase18_authority=False)

    def execute(self,*,native_image,signer):
        """Signer is fixed qualified operator code taking a protected file path.

        It returns that path's .sig, using admitted owner trust. It is not an
        artifact-selected command/plugin. Both phases are reverified here.
        """
        return _execute(self,native_image=native_image,signer=signer)


def prepare(*,environment_owner,clock_owner,base_validation,operator_profile_sha256):
    """Live preparation only after the qualified operator's package/ETA gates."""
    require(type(environment_owner) is environment._PreparedEnvironment,'actual owned environment required')
    try:
        return _prepare(environment_owner=environment_owner,clock_owner=clock_owner,
            base_validation=base_validation,operator_profile_sha256=operator_profile_sha256)
    except BaseException:
        environment_owner._qualification_failed=True
        raise


def _prepare(*,environment_owner,clock_owner,base_validation,operator_profile_sha256):
    require(type(environment_owner) is environment._PreparedEnvironment and type(clock_owner) is clocks._VerifiedClocks
        and clock_owner.owner is environment_owner,'actual owned environment and its clock pair proof required')
    archive.sha(operator_profile_sha256,'independently qualified operator/profile')
    guard=environment_owner.compaction_guard();plan=guard.owner['plan'];family=guard.owner['plan_sha256']
    proof=clock_owner.proof(plan_sha256=family);_before(proof['qualification_deadline_monotonic_ns'])
    require(environment_owner._qualification_roles==['near','far'],'exact completed near/far placement required')
    require(set(base_validation.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,8)},'original seven required')
    environment_owner.admission_observation(plan_sha256=family)
    platform,observed=_platform();validators=_schemas()
    require(ROOT.parent.resolve(strict=True)==ROOT.parent,'canonical qualification parent required')
    clocks._mkdir(ROOT);st=ROOT.stat(follow_symlinks=False)
    prefix='S180-Q15-'+family;runtime_binding=dict(role=authority.ROLE,profile=authority.PROFILE,
        sha256=authority.resources.NATIVE_SHA,size_bytes=authority.resources.NATIVE_SIZE)
    context=dict(schema_version=authority.CONTEXT_SCHEMA,plan_sha256=family,window_binding=guard.owner['window'],
        **{k:proof[k] for k in ('qualification_started_monotonic_ns','qualification_deadline_monotonic_ns')},
        evidence_root_binding=dict(absolute_path=str(ROOT),device=st.st_dev,inode=st.st_ino,owner_uid=st.st_uid,mode=f'{stat.S_IMODE(st.st_mode):04o}'),
        runtime_binding=runtime_binding,release_binding=dict(source_resolution_id=authority.RELEASE_ID,
            source_resolution_sha256=operator_profile_sha256,artifact_role=authority.ROLE,runtime_profile=authority.PROFILE,
            worker_sha256=runtime_binding['sha256'],worker_size_bytes=runtime_binding['size_bytes'],source_revision=environment.NATIVE_REVISION),
        session_id=prefix+'-SESSION',qualification_id=prefix+'-QUAL',stand_id=plan['blueprint']['stand_id'],
        action_id='Q15-R',phase18_authority=False,action_inputs=dict(qualification_id=prefix+'-QUAL',
            attempt_id=prefix+'-R-ATTEMPT',session_id=prefix+'-SESSION',probe_platform_binding=platform))
    try:
        authority._context(context)
        binding=_save(ROOT/'preparation.json',dict(schema_version=SCHEMA,context=context,clock_proof=proof,
            observed_cache=observed,operator_profile_sha256=operator_profile_sha256,
            package_qualification_performed_here=False,execution_authority=False))
        return _PreparedQ15(token=_TOKEN,owner=environment_owner,clock_owner=clock_owner,base=base_validation,
            context=context,validators=validators,preparation=binding)
    except BaseException:
        environment_owner._qualification_failed=True
        raise


def _signed(prepared,context,signer):
    prepared._guard();phase='r' if context['action_id']=='Q15-R' else 'w'
    path=ROOT/f'q15-{phase}-authorization.json'
    require(not os.path.lexists(str(path)+'.sig'),'Q15 signature path already occupied; no adoption')
    raw=archive.canonical(prepared._unsigned(context));_save_bytes(path,raw)
    deadline=context['qualification_deadline_monotonic_ns'];_before(deadline)
    require(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'foreign active signing timer; do not replace')
    previous=signal.getsignal(signal.SIGALRM)
    def expired(number,frame):raise SessionError('owner signing exceeded original qualification deadline')
    signal.signal(signal.SIGALRM,expired)
    try:
        remaining=deadline-time.monotonic_ns();require(remaining>0,'owner signing deadline already expired')
        signal.setitimer(signal.ITIMER_REAL,remaining/10**9)
        signature=Path(signer(path))
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    _before(deadline)
    require(signature==Path(str(path)+'.sig'),'fixed Q15 signature publication path required')
    compaction._root_file(signature,FILE_BYTES)
    verified=authority.verify_authorization(authorization_bytes=raw,signature_path=signature,
        qualification_context=context,base_validation=prepared.base)
    _save_bytes(ROOT/f'q15-{phase}-request.json',verified.request_bytes)
    definition=Path(__file__).resolve().parents[1]/'config/stage17/stage17-fixed-phase-actions-v5.json'
    digest=hashlib.sha256(compaction._read(definition,FILE_BYTES)).hexdigest()
    native=verified.native_context(fixed_action_definition_sha256=digest)
    _save_bytes(ROOT/f'q15-{phase}-context.json',authority.carrier.canonical(native))
    attempt=_save(ROOT/f'q15-{phase}-attempt.json',dict(schema_version=SCHEMA,action_id=context['action_id'],
        attempt_id=verified.request()['attempt_id'],authorization_sha256=authority.pilot.sha(raw),
        request_sha256=authority.pilot.sha(verified.request_bytes),one_attempt=True,automatic_retries=0,execution_authority=False))
    return verified,native,attempt


def _hardware(prepared,worker=None):
    """Independent actual device/prestate checks, optionally at sealed R barrier."""
    context=archive.parse_json(prepared._context);owner=prepared.owner
    require(environment._boot()==context['window_binding']['boot_id'],'original Q15 boot changed')
    require(owner._core.identity(environment.CG)==archive.parse_json(owner._preparation)['prestate']['partition_identity'],
        'owned Q15 partition replaced')
    members=owner._core.read(environment.CG/'cgroup.procs')
    if worker is not None:
        worker.observe_quiescence()
        require(members==str(worker.pid) and compaction._membership(worker.pid)=='/'+environment.UNIT+'/reserved',
            'sealed Q15-R worker/partition membership differs')
    else:
        require(members=='' and not supervisor.ProcfsIdentityModel().direct_children(),
            'workers remain before hardware restoration verification')
    observed=[]
    for row in prepared.owner.compaction_guard().owner['plan']['hardware']['prestate']:
        fd,identity=environment._open_msr(row['cpu'])
        try:
            value=environment._read_msr(fd)
            require(identity==owner._devices[row['cpu']] and value==row['value'],'actual original Q15 MSR prestate differs')
            observed.append(dict(cpu=row['cpu'],complete_value_hex=f'{value:016x}'))
        finally:os.close(fd)
    if worker is not None:worker._alive()
    return observed


def _inventory():
    rows=list(ROOT.iterdir());require(len(rows)<=TOTAL_FILES,'bounded Q15 file family exceeded')
    total=0
    for path in rows:
        raw=compaction._root_file(path,FILE_BYTES);total+=len(raw)+4096
    require(total<=METADATA_BYTES,'complete Q15 metadata reservation exceeded')


def _place(entry):
    os.umask(0o077);require(os.umask(0o077)==0o077,'Q15 child output protection differs')
    for kind,value in ((resource.RLIMIT_AS,clocks.AS_BYTES),(resource.RLIMIT_MEMLOCK,clocks.MEMLOCK_BYTES),
        (resource.RLIMIT_FSIZE,FILE_BYTES),(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(value,value));require(resource.getrlimit(kind)==(value,value),'Q15 child limit readback differs')
    raw=str(os.getpid()).encode();require(os.write(entry['descriptor'],raw)==len(raw),'Q15 cgroup placement failed')
    os.close(entry['descriptor'])
    require(compaction._membership(os.getpid())==entry['relative_path'],'actual Q15 placement differs')
    os.sched_setaffinity(0,{entry['controller_cpu']})
    require(os.sched_getaffinity(0)=={entry['controller_cpu']},'actual Q15 controller affinity differs')


def _drain_console(process,selector,console):
    for stream in (process.stdout,process.stderr):
        while True:
            try:block=os.read(stream.fileno(),min(4096,CONSOLE_BYTES-len(console)+1))
            except BlockingIOError:break
            if not block:
                try:selector.unregister(stream)
                except KeyError:pass
                break
            console.extend(block);require(len(console)<=CONSOLE_BYTES,'Q15 console bound exceeded')


def _waiting(worker,control_fd):
    """Actual x86-64 read(owned pipe, header, 4), after native durable R publish.

    The frozen ELF creates its ready file before writing/fsyncing it. Existence
    alone cannot establish publication or the same-buffer control barrier.
    """
    worker._alive()
    child=Path('/proc')/str(worker.pid)
    observed=(child/'fd'/str(control_fd)).stat();original=os.fstat(control_fd)
    require(stat.S_ISFIFO(observed.st_mode) and (observed.st_dev,observed.st_ino)==(original.st_dev,original.st_ino),
        'actual private Q15 control pipe changed')
    fields=compaction._read(child/'syscall',512).decode('ascii').strip().split()
    worker._alive()
    if not (len(fields)==9 and fields[0]=='0' and int(fields[1],0)==control_fd and int(fields[3],0)==4):return None
    return dict(pid=worker.pid,start_ticks=worker.start_ticks,descriptor=control_fd,
        pipe_device=observed.st_dev,pipe_inode=observed.st_ino,observed_syscall=fields,
        observed_monotonic_ns=time.monotonic_ns())


def _execute(prepared,*,native_image,signer):
    require(type(prepared) is _PreparedQ15 and not prepared.used,'original Q15 attempt already consumed')
    context=prepared._guard();window=context['window_binding'];deadline=context['qualification_deadline_monotonic_ns']
    require(type(native_image) is runtime.ImageBinding and native_image.size_bytes==authority.resources.NATIVE_SIZE
        and native_image.sha256==authority.resources.NATIVE_SHA,'exact frozen Q15 native image required')
    require(callable(signer) and threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and len(list(Path('/proc/self/task').iterdir()))==1,'fixed single-threaded owner signer required')
    prepared.used=True;process=None;worker=None;cleanup=None;failure=None;read_result=None;write_result=None
    read_binding=None;write_binding=None;hardware=None;bindings=[];console=bytearray();previous={};write_fd=None
    lease=supervisor.SupervisorLease();guard=prepared.owner.compaction_guard();write_sent=False
    read_barrier=None;write_barrier=None
    def interrupted(number,frame):raise SessionError('Q15 interrupted by signal '+str(number))
    with contextlib.ExitStack() as stack:
        try:
            executable=runtime._pin_image(native_image,deadline,stack)
            read,native,attempt=_signed(prepared,context,signer)
            request_fd=runtime._sealed_input(read.request_bytes,'s180-Q15-R-request');stack.callback(os.close,request_fd)
            context_fd=runtime._sealed_input(authority.carrier.canonical(native),'s180-Q15-R-context');stack.callback(os.close,context_fd)
            output_fd=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC);stack.callback(os.close,output_fd)
            read_fd,write_fd=os.pipe2(os.O_CLOEXEC);stack.callback(os.close,read_fd)
            selector=selectors.DefaultSelector();stack.callback(selector.close)
            lease.enter()
            for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
            with prepared.owner.qualification_entry(plan_sha256=context['plan_sha256'],role='q15') as entry:
                try:
                    _before(deadline-CLEANUP_NS);guard.check(boundary='FAMILY_ENTRY')
                    inherited=(executable,request_fd,context_fd,read_fd,output_fd,entry['descriptor'])
                    require(max(inherited)<128,'Q15 inherited descriptors exceed original child limit')
                    argv=[f'/proc/self/fd/{executable}','--execute-stage17-q15-session-v1','--q15-r-request-fd',str(request_fd),
                        '--q15-r-context-fd',str(context_fd),'--q15-w-control-fd',str(read_fd),'--output-dir-fd',str(output_fd),'--fixed-dispatch-end']
                    process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        close_fds=True,pass_fds=inherited,start_new_session=True,preexec_fn=lambda:_place(entry),
                        env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','TZ':'UTC'})
                    worker=compaction.PinnedWorker(process.pid);guard.register_worker(worker,role='q15')
                    for stream in (process.stdout,process.stderr):
                        os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,'console')
                    os.set_blocking(write_fd,False);queue=b'';offset=0;stage_end=deadline-CLEANUP_NS;diagnostics=[]
                    while True:
                        _before(stage_end)
                        if read_result is None and (waiting:=_waiting(worker,read_fd)):
                            _drain_console(process,selector,console)
                            read_result,documents,read_bindings=_result(read,prepared.validators)
                            value=_read_gate(documents,context,authority.pilot.sha(read.authorization_bytes))
                            prestate=_hardware(prepared,worker)
                            read_barrier=dict(waiting,quiescence=worker.observe_quiescence(),msr_readbacks=prestate)
                            require(value['prestate']==prestate,'sealed Q15-R full prestate differs from live hardware')
                            ready,ready_binding=_read(ROOT/'stage17-q15-session-waiting-v1.json')
                            require(ready==dict(schema_version='cpu-prefetch-stage17-q15-session-waiting/1',session_id=context['session_id'],
                                q15_r_request_sha256=authority.pilot.sha(read.request_bytes),q15_r_result_sha256=read_bindings[0]['sha256'],
                                state='H0_SEALED_WAITING_FOR_Q15_W',same_buffer_retained=True,phase18_authority=False),
                                'actual same-buffer Q15-R barrier differs')
                            bindings.extend((*read_bindings,ready_binding));read_binding=read_bindings[0]
                            write_context=copy.deepcopy(context);write_context['action_id']='Q15-W'
                            write_context['action_inputs']=dict(q15_r_attempt_sha256=attempt['sha256'],
                                q15_r_result_sha256=read_binding['sha256'],session_id=context['session_id'],prestate=prestate)
                            guard.check(boundary='FAMILY_ENTRY');write,write_native,_=_signed(prepared,write_context,signer)
                            live_prestate=_hardware(prepared,worker);waiting=_waiting(worker,read_fd)
                            require(waiting,'sealed Q15-R pipe barrier changed')
                            write_barrier=dict(waiting,quiescence=worker.observe_quiescence(),msr_readbacks=live_prestate)
                            _drain_console(process,selector,console);_before(stage_end)
                            packets=(write.request_bytes,authority.carrier.canonical(write_native))
                            require(all(0<len(p)<=FILE_BYTES for p in packets),'Q15-W control packet bound')
                            queue=b''.join(len(p).to_bytes(4,'big')+p for p in packets)
                            selector.register(write_fd,selectors.EVENT_WRITE,'control');stage_end=min(stage_end,time.monotonic_ns()+WRITE_NS)
                        exited=supervisor._peek_leader_exit_held(process.pid,diagnostics) is not None
                        if exited and not selector.get_map():break
                        if exited and read_result is None:raise SessionError('Q15 worker exited before its sealed read barrier')
                        for key,_ in selector.select(timeout=.02):
                            if key.data=='control':
                                try:offset+=os.write(write_fd,queue[offset:])
                                except BlockingIOError:continue
                                if offset==len(queue):
                                    selector.unregister(write_fd);os.close(write_fd);write_fd=None;write_sent=True
                            else:
                                block=os.read(key.fd,min(4096,CONSOLE_BYTES-len(console)+1))
                                if block:
                                    console.extend(block);require(len(console)<=CONSOLE_BYTES,'Q15 console bound exceeded')
                                else:selector.unregister(key.fileobj)
                except BaseException as error:failure=error
                finally:
                    def cleanup_interrupted(number,frame):
                        nonlocal failure
                        failure=failure or SessionError('signal during mandatory Q15 cleanup '+str(number))
                    for number in previous:signal.signal(number,cleanup_interrupted)
                    if process is not None:
                        try:
                            cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                                leader_wait_deadline_ns=min(deadline,time.monotonic_ns()+supervisor.predecessor.TERM_GRACE_NS),
                                global_deadline_ns=min(window['end_monotonic_ns'],time.monotonic_ns()+CLEANUP_NS),
                                identity_model=lease.identity_model)
                            require(cleanup.leader_reaped and cleanup.process_group_gone,'Q15 worker quiescence is incomplete')
                            require(cleanup.returncode==0 and not cleanup.descendants_detected_after_leader_exit
                                and not cleanup.cleanup_deadline_overrun and not cleanup.leader_wait_timed_out,
                                'Q15 worker failed or required abnormal cleanup')
                        except BaseException as error:failure=failure or error
                        for stream in (process.stdout,process.stderr):
                            if stream:stream.close()
                    if worker is not None:worker.close()
                if failure is not None:raise failure
                require(write_sent,'separate Q15-W control was not fully delivered')
                write_result,documents,write_bindings=_result(write,prepared.validators)
                _write_gate(documents['Q15_W_TRANSACTION'],write_context,authority.pilot.sha(write.authorization_bytes))
                bindings.extend(write_bindings);write_binding=write_bindings[0]
                hardware=_hardware(prepared);guard.check(boundary='FINAL');_inventory();_before(deadline)
        except BaseException as error:failure=failure or error
        finally:
            if write_fd is not None:os.close(write_fd)
            for number,handler in previous.items():signal.signal(number,handler)
            try:lease.close()
            except BaseException as error:failure=failure or error
        prepared.failed=failure is not None
        if failure is not None:prepared.owner._qualification_failed=True
        terminal=dict(schema_version=SCHEMA,plan_sha256=context['plan_sha256'],window_binding=window,
            qualification_deadline_monotonic_ns=deadline,completed_monotonic_ns=time.monotonic_ns(),
            status='Q15_RW_VERIFIED' if failure is None else 'STOPPED',
            native_pid=None if process is None else process.pid,native_start_ticks=None if worker is None else worker.start_ticks,
            cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),read_result=read_binding,write_result=write_binding,
            read_barrier=read_barrier,write_barrier=write_barrier,
            original_msr_readbacks=hardware,console_hex=console.hex(),
            failure=None if failure is None else str(failure)[:4096],automatic_retries=0,
            clock_and_q15_evidence_complete=failure is None,execution_authority=False,phase18_authority=False)
        try:
            receipt=_save(ROOT/'terminal.json',terminal)
            if failure is None:_before(deadline)
        except BaseException as error:
            prepared.failed=True;prepared.owner._qualification_failed=True
            if failure is not None:raise failure from error
            raise
        if failure is not None:raise failure
        return dict(terminal=receipt,document=terminal,raw_bindings=bindings,execution_authority=False)
