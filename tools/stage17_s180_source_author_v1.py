"""Single supervised S180 source author for the qualified outer operator.

Library only. The outer operator authenticates this component, the frozen
packet/profile and whole-run ETA/readiness before namespace preparation. This
boundary verifies its own live source commitments; it grants no full admission.
"""
from __future__ import annotations
import contextlib
import copy
from dataclasses import asdict
from fractions import Fraction
import hashlib
import os
from pathlib import Path
import resource
import select
import signal
import stat
import threading
import time
from types import SimpleNamespace

import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
import stage17_s180_namespace_admission_v1 as namespaces
import stage17_s180_resource_admission_v1 as resources

archive=namespaces.archive
planning=namespaces.environment.planning
generator=namespaces.sources.provenance.generator
ROOT=namespaces.ROOT.parent/'source-author'
SIZING_PATH='config/stage17/d362-s180-stand-sizing-v1.json'
SIZING_SHA='ece6975ba86ea0b18547915df4817b11661c9e3cc6603f95d24d4b230f1f97f5'
SCHEMA='cpu-prefetch-stage17-s180-source-author/1'
SOURCE_CPU=3
CHILD_AS=8*1024**3
PARENT_AS=4*1024**3
METADATA_BYTES=20*1024**2
METADATA_INODES=64
CONTROL_BYTES=256*1024
CONSOLE_BYTES=64*1024
CLEANUP_NS=120*10**9
_TOKEN=object()


class AuthorError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise AuthorError('S180 source author: '+message)


def _before(deadline):require(time.monotonic_ns()<deadline,'original source deadline expired')


def requirements(sizing):
    """Exact fixed ceilings, never generated counts or statistical guarantees."""
    require(planning.sha(sizing)==SIZING_SHA and sizing['source_count_basis']=='PROSPECTIVE_UPPER_CEILINGS',
        'exact verified D362 stand-runtime prospective packet required')
    groups,order=planning.source_groups(sizing)
    identities=namespaces.audit.planned_identities(sizing['blueprint'])
    by_key={tuple(r[k] for k in ('placement','working_set_class','load_level','phase')):r for r in identities['sources']}
    rows={tuple(r[k] for k in ('placement','working_set_class','load_level')):r for r in sizing['blueprint']['captures']}
    jobs=[];total=0;pages=0;vectors=0
    for key in order:
        row=rows[key];rate=Fraction(row['nominal_rate']['numerator'],row['nominal_rate']['denominator']*10**12)
        for i,phase in enumerate(('warmup','measurement')):
            declaration=by_key[key+(phase,)];p=groups[key][i]
            horizon=row[phase+'_ns']*1000
            mean=rate*horizon;ceiling=(2*mean.numerator+mean.denominator-1)//mean.denominator
            require(p['offered_count']==ceiling and p['source_artifact'] is None
                and p['source_origin_ticks']==0 and p['source_horizon_ticks']==horizon
                and p['schedule_id']==declaration['schedule_id'],'prospective source ceiling/identity differs')
            size=8*ceiling;vectors=max(vectors,total+2*size);total+=size;pages+=(size+4095)//4096*4096
            jobs.append(dict(declaration=declaration,origin_ticks=0,horizon_ticks=horizon,
                numerator_events=rate.numerator,denominator_ticks=rate.denominator,maximum_count=ceiling))
    return dict(jobs=jobs,maximum_source_bytes=total,maximum_vector_bytes=vectors,
        source_bank_upper_bytes=total+72*1024**2,source_bank_upper_inodes=109,
        source_metadata_upper_bytes=METADATA_BYTES,source_metadata_upper_inodes=METADATA_INODES,
        source_process_and_page_upper_bytes=CHILD_AS+PARENT_AS+pages,
        full_resource_admission=False,execution_authority=False,phase18_authority=False)


def _admit(sizing,budget,namespace_owner,deadline,protected_remaining_ns):
    proof=namespace_owner.proof();window=proof['window_binding'];now=time.monotonic_ns()
    require(not proof['source_generation_consumed'],'source generation already consumed')
    require(type(deadline) is int and now+2*CLEANUP_NS<deadline<=now+namespaces.SOURCE_NS
        and type(protected_remaining_ns) is int and protected_remaining_ns>0
        and deadline+protected_remaining_ns<window['end_monotonic_ns'],'source/cleanup/post-work budget cannot fit original window')
    # No discretionary caller-selected shorter post-work declaration can hide
    # qualification, full native/archive watchdogs, validation or restoration.
    b=sizing['budget'];native=sum(b[k] for k in ('setup_ns','whole_plot_transition_ns','whole_plot_recovery_ns','finalization_ns'))
    native+=sum(r['execution_budget']['watchdog_ns'] for r in sizing['captures'])
    post=native+sum(resources.prospective.EXTERNAL_TIME[k] for k in
        ('qualification_ns','independent_validation_ns','restoration_and_exit_ns'))
    require(protected_remaining_ns>=post,'declared post-source reserve omits required stages')
    observed=resources.platform_observation();soft,hard=observed['rlimit_as']
    require(0<soft<=PARENT_AS and (hard==resource.RLIM_INFINITY or hard>=CHILD_AS),
        'actual parent AS cap or source-child hard limit cannot fit')
    require(observed['base_page_bytes']==4096 and observed['memory_available_bytes']>=budget['source_process_and_page_upper_bytes'],
        'actual source memory/page availability cannot fit')
    for row in observed['memory_ancestors']:
        require(row['maximum_bytes'] is None or row['maximum_bytes']-row['current_bytes']>=budget['source_process_and_page_upper_bytes'],
            'actual source ancestor memory allowance cannot fit')
    needed=archive.checked_sum(custody.WORKSPACE,custody.SCRATCH,custody.RESERVE,
        budget['source_bank_upper_bytes'],METADATA_BYTES,namespaces.METADATA_RESERVE_BYTES)
    fs=os.statvfs(ROOT.parent)
    require(fs.f_bavail*fs.f_frsize>=needed and fs.f_favail>=budget['source_bank_upper_inodes']+METADATA_INODES+namespaces.METADATA_RESERVE_INODES,
        'actual source filesystem commitments cannot fit')
    require(SOURCE_CPU in os.sched_getaffinity(0),'requested source CPU3 unavailable to parent')
    return dict(observed_platform=observed,free_filesystem_bytes=fs.f_bavail*fs.f_frsize,
        free_filesystem_inodes=fs.f_favail,required_source_filesystem_bytes=needed,
        source_requirements={k:v for k,v in budget.items() if k!='jobs'},
        protected_remaining_ns=protected_remaining_ns,source_commitments_checked=True,
        complete_programme_quota_checked=False,full_resource_admission=False,execution_authority=False)


def _save(path,value,maximum=CONTROL_BYTES):return namespaces._save(path,value,maximum)


def _publish(path,raw,identity,maximum):
    require(type(raw) is bytes and len(raw)<=maximum,'original source artifact exceeds its declared ceiling')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);require(n>0,'source publication made no progress');view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    namespaces._sync_directory(path.parent)
    return dict(artifact_id=identity,path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _generate(job,index,source_directory,master_seed):
    d=job['declaration'];spec=generator.ScheduleSpec(d['schedule_id'],
        'WARMUP' if d['phase']=='warmup' else 'PILOT',d['namespace_id'],d['parent_namespace_id'],d['seed_id'],
        d['derivation_record_id'],bytes.fromhex(master_seed),job['origin_ticks'],job['horizon_ticks'],
        job['numerator_events'],job['denominator_ticks'],d['artifact_id'],f'source-{index:02d}.u64be')
    generated=generator.generate_schedule(spec);count=len(generated.deadlines)
    require(count<=job['maximum_count'],'original source extent ceiling reached; no clipping or replacement')
    require(count>0 or d['phase']=='warmup','empty measurement source cannot form the declared native candidate')
    record={k:d[k] for k in ('placement','working_set_class','load_level','phase')}
    for kind,name,identity,raw,maximum in (
        ('binary',f'source-{index:02d}.u64be',d['artifact_id'],generated.artifact_bytes,8*job['maximum_count']),
        ('envelope',f'source-{index:02d}-schedule.json',d['envelope_artifact_id'],generated.envelope_bytes,1024**2),
        ('derivation',f'source-{index:02d}-derivation.json',d['derivation_artifact_id'],generated.derivation_record_bytes,1024**2)):
        record[kind]=_publish(source_directory/name,raw,identity,maximum)
    return dict(ordinal=index,offered_count=count,record=record)


def _worker(jobs,master_seed,source_directory):
    """One generation pass only. Independent D323 verification is in the parent."""
    rows=[]
    for i,job in enumerate(jobs):
        row=_generate(job,i,source_directory,master_seed);rows.append(row)
        _save(ROOT/f'source-{i:02d}.json',row,8192)
    _save(ROOT/'bank.json',dict(schema_version=SCHEMA,sources=rows,source_count=36,
        independent_verification_performed=False,execution_authority=False))


def _child(gate,ready,console,jobs,master_seed,source_directory,original_mask):
    try:
        os.setsid()
        for number in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGCHLD):signal.signal(number,signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK,original_mask)
        # A fork inherits the namespace lock/open files. Close copies without
        # flock(UNLOCK), so the parent's actual lease remains held.
        for fd in list(map(int,os.listdir('/proc/self/fd'))):
            if fd>2 and fd not in (gate,ready,console):
                with contextlib.suppress(OSError):os.close(fd)
        os.umask(0o077)
        null=os.open('/dev/null',os.O_RDONLY);os.dup2(null,0);os.close(null)
        os.dup2(console,1);os.dup2(console,2);os.close(console)
        for kind,value in ((resource.RLIMIT_AS,CHILD_AS),(resource.RLIMIT_FSIZE,
            max(CONTROL_BYTES,max(8*j['maximum_count'] for j in jobs))),
            (resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
            resource.setrlimit(kind,(value,value));require(resource.getrlimit(kind)==(value,value),'source child rlimit readback differs')
        os.sched_setaffinity(0,{SOURCE_CPU});require(os.sched_getaffinity(0)=={SOURCE_CPU},'source child affinity differs')
        _save(ROOT/'child-ready.json',dict(schema_version=SCHEMA,pid=os.getpid(),start_ticks=namespaces._ticks(),
            process_group=os.getpgrp(),session=os.getsid(0),requested_cpu=SOURCE_CPU,observed_cpus=sorted(os.sched_getaffinity(0)),
            actual_rlimit_as=list(resource.getrlimit(resource.RLIMIT_AS)),
            inherited_cgroup=resources._read(f'/proc/{os.getpid()}/cgroup',4096)),8192)
        require(os.write(ready,b'R')==1,'source readiness pipe made no progress');os.close(ready)
        require(os.read(gate,1)==b'G','source parent did not release actual child');os.close(gate)
        _worker(jobs,master_seed,source_directory);os._exit(0)
    except BaseException as error:
        with contextlib.suppress(BaseException):_save(ROOT/'child-failure.json',dict(schema_version=SCHEMA,
            failure=f'{type(error).__name__}: {str(error)[:4096]}',automatic_retry=False,execution_authority=False),8192)
        os._exit(1)


def _run_child(budget,master_seed,source_directory,deadline):
    """Held session leader + pidfd during handshake, then accepted subreaper cleanup."""
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1,
        'single-threaded main-process source supervisor required')
    require(signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'default held-child SIGCHLD disposition required')
    now=time.monotonic_ns();end=deadline-CLEANUP_NS;require(now<end,'source cleanup reserve absent')
    lease=supervisor.SupervisorLease();previous={};pid=None;process=None;pidfd=None;cleanup=None;failure=None;released=False
    handshake_reaped=False
    ready_r,ready_w=os.pipe2(os.O_CLOEXEC);gate_r,gate_w=os.pipe2(os.O_CLOEXEC)
    console_r,console_w=os.pipe2(os.O_CLOEXEC);console=bytearray();os.set_blocking(console_r,False)
    def drain():
        while True:
            try:block=os.read(console_r,min(4096,CONSOLE_BYTES-len(console)+1))
            except BlockingIOError:return
            if not block:return
            available=CONSOLE_BYTES-len(console);console.extend(block[:available])
            require(len(block)<=available,'source console bound exceeded; bounded prefix retained')
    def interrupted(number,frame):raise AuthorError('source preparation interrupted by signal '+str(number))
    try:
        lease.enter()
        for number in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
        original_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set(previous))
        try:
            pid=os.fork()
            if pid==0:_child(gate_r,ready_w,console_w,budget['jobs'],master_seed,source_directory,original_mask)
            process=SimpleNamespace(pid=pid,returncode=None);pidfd=os.pidfd_open(pid)
        finally:
            if pid!=0:signal.pthread_sigmask(signal.SIG_SETMASK,original_mask)
        os.close(ready_w);ready_w=None;os.close(gate_r);gate_r=None
        os.close(console_w);console_w=None
        handshake=min(end,time.monotonic_ns()+10*10**9)
        while True:
            _before(handshake);drain()
            readable,_,_=select.select([ready_r],[],[],.05)
            if readable:
                if os.read(ready_r,2)!=b'R':
                    detail=''
                    if (ROOT/'child-failure.json').exists():
                        detail=': '+archive.parse_json(namespaces._protected(ROOT/'child-failure.json',8192))['failure']
                    raise AuthorError('source child failed before readiness'+detail)
                break
            require(supervisor._peek_leader_exit_held(pid,[]) is None,'source child exited before readiness')
        identity=lease.identity_model.identity_for_local_pid(pid)
        require(identity.local_pgid==pid and os.getsid(pid)==pid,'source child did not establish its own session')
        ready=archive.parse_json(namespaces._protected(ROOT/'child-ready.json',8192))
        require(ready['pid']==pid and ready['start_ticks']==Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]
            and ready['inherited_cgroup']==resources._read(f'/proc/{os.getpid()}/cgroup',4096),
            'source child identity or inherited cgroup differs')
        require(os.write(gate_w,b'G')==1,'source release pipe made no progress');released=True
        os.close(gate_w);gate_w=None
        while supervisor._peek_leader_exit_held(pid,[]) is None:
            _before(end);drain()
            time.sleep(.05)
        drain()
    except BaseException as error:failure=error
    finally:
        def cleanup_signal(number,frame):
            nonlocal failure
            failure=failure or AuthorError('signal during mandatory source cleanup '+str(number))
        for number in previous:signal.signal(number,cleanup_signal)
        if process is not None:
            try:
                if not released:
                    # Before release the child cannot create descendants. Its
                    # group may not exist yet: target only the held pidfd.
                    if pidfd is None:
                        # Single-threaded default-SIGCHLD parent has not reaped
                        # this direct child. WNOWAIT first verifies ownership;
                        # its held PID cannot be reused before our own wait.
                        supervisor._peek_leader_exit_held(pid,[]);os.kill(pid,signal.SIGKILL)
                    else:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                    process.returncode=supervisor._waitpid_leader_fail_stop(pid,[])
                    handshake_reaped=True
                    require(not lease.identity_model.direct_children(),'source handshake left owned children')
                else:
                    cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                        leader_wait_deadline_ns=min(end,time.monotonic_ns()+supervisor.predecessor.TERM_GRACE_NS),
                        global_deadline_ns=deadline,identity_model=lease.identity_model)
                    require(cleanup.leader_reaped and cleanup.process_group_gone and cleanup.returncode==0
                        and not cleanup.descendants_detected_after_leader_exit and not cleanup.cleanup_deadline_overrun
                        and not cleanup.leader_wait_timed_out,'source child failure or abnormal cleanup')
            except BaseException as error:failure=failure or error
        try:drain()
        except BaseException as error:failure=failure or error
        for fd in (ready_r,ready_w,gate_r,gate_w,pidfd,console_r,console_w):
            if fd is not None:
                with contextlib.suppress(OSError):os.close(fd)
        for number,handler in previous.items():signal.signal(number,handler)
        try:lease.close()
        except BaseException as error:failure=failure or error
    result=dict(schema_version=SCHEMA,pid=pid,started_monotonic_ns=now,completed_monotonic_ns=time.monotonic_ns(),
        generation_deadline_ns=deadline,cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),
        source_child_returncode=None if process is None else process.returncode,
        pre_release_leader_reaped=handshake_reaped,
        failure=None if failure is None else str(failure)[:4096],automatic_retry=False,execution_authority=False)
    _publish(ROOT/'console.txt',bytes(console),'SOFTWARE-DIAGNOSTICS',CONSOLE_BYTES)
    _save(ROOT/'generation-result.json',result)
    if failure is not None:raise failure
    _before(deadline);return result


def _realize(sizing,budget,bank):
    require(bank['schema_version']==SCHEMA and bank['source_count']==36 and len(bank['sources'])==36
        and bank['independent_verification_performed'] is False,'complete unverified original bank required')
    out=copy.deepcopy(sizing);out['source_count_basis']='EXACT_DECLARED_COUNTS';records=[];lookup={};paths=set()
    for i,(job,row) in enumerate(zip(budget['jobs'],bank['sources'],strict=True)):
        d=job['declaration'];r=row['record'];count=row['offered_count']
        require(type(row['ordinal']) is int and row['ordinal']==i and type(count) is int
            and 0<=count<=job['maximum_count'] and (count>0 or d['phase']=='warmup'),
            'original source count/order exceeds fixed ceiling')
        key=tuple(d[k] for k in ('placement','working_set_class','load_level','phase'))
        require(tuple(r[k] for k in ('placement','working_set_class','load_level','phase'))==key
            and r['binary']['size_bytes']==8*count,'source coordinates/count differ')
        provenance=namespaces.sources.provenance
        provenance._fields(r,provenance.RECORD_FIELDS,'generated source record')
        for kind,identity,name,maximum in (
            ('binary',d['artifact_id'],f'source-{i:02d}.u64be',8*count),
            ('envelope',d['envelope_artifact_id'],f'source-{i:02d}-schedule.json',1024**2),
            ('derivation',d['derivation_artifact_id'],f'source-{i:02d}-derivation.json',1024**2)):
            ref=r[kind];provenance._fields(ref,provenance.FILE_FIELDS,'generated source artifact')
            path=namespaces.ROOT/'sources'/name;st=path.stat(follow_symlinks=False)
            require(ref['artifact_id']==identity and ref['path']==str(path) and path.resolve(strict=True)==path
                and stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_nlink==1 and not st.st_mode&0o022
                and type(ref['size_bytes']) is int and 0<=ref['size_bytes']==st.st_size<=maximum,
                'generated source artifact locator/identity/extent differs')
            archive.sha(ref['sha256'],'generated source artifact');paths.add(path)
        lookup[key]=dict(count=count,binding={k:r['binary'][k] for k in ('artifact_id','sha256')});records.append(r)
    require(len(paths)==108 and set((namespaces.ROOT/'sources').iterdir())==paths,'generated source inventory differs')
    for bp,entry in zip(sorted(out['blueprint']['captures'],key=lambda r:r['execution_ordinal']),out['captures'],strict=True):
        for i,phase in enumerate(('warmup','measurement')):
            item=lookup[tuple(bp[k] for k in ('placement','working_set_class','load_level'))+(phase,)]
            entry['phases'][i].update(offered_count=item['count'],source_artifact=item['binding'])
    return out,records


class _AuthoredSources:
    def __init__(self,*,token,namespace_owner,source_owner,plan,records,completion,metadata):
        require(token is _TOKEN,'actual supervised generation and independent owned verification required')
        self.namespace_owner=namespace_owner;self.source_owner=source_owner;self._plan=archive.canonical(plan)
        self._records=archive.canonical(dict(records=records));self._completion=archive.canonical(completion)
        self._metadata=archive.canonical(dict(files=metadata));self.failed=False;self.closed=False
        st=ROOT.stat(follow_symlinks=False);self._directory_identity=(st.st_dev,st.st_ino)

    @property
    def plan(self):return archive.parse_json(self._plan)

    @property
    def records(self):return archive.parse_json(self._records)['records']

    def proof(self):
        require(not self.failed and not self.closed,'source author failed or closed; no retry')
        try:
            proof=self.namespace_owner.proof();self.source_owner.proof(plan_sha256=hashlib.sha256(self._plan).hexdigest())
            st=ROOT.stat(follow_symlinks=False)
            require(ROOT.resolve(strict=True)==ROOT and stat.S_ISDIR(st.st_mode) and st.st_uid==0
                and stat.S_IMODE(st.st_mode)==0o700 and (st.st_dev,st.st_ino)==self._directory_identity,
                'original source-author directory identity differs')
            metadata=archive.parse_json(self._metadata)['files']
            require(set(ROOT.iterdir())=={Path(r['path']) for r in metadata},'source-author metadata inventory changed')
            for row in metadata:namespaces._bound(row)
            completion=archive.parse_json(self._completion)
            return dict(schema_version=SCHEMA,plan_sha256=hashlib.sha256(self._plan).hexdigest(),completion=completion,
                original_generation_passes=1,independent_generation_verification_passes=1,source_bank_owned_and_verified=True,
                namespace_source_binding=proof['source_bank_binding'],full_ext008_admission=False,
                full_resource_admission=False,execution_authority=False,phase18_authority=False)
        except BaseException:
            self.failed=True;raise


@contextlib.contextmanager
def prepare_sources(*,namespace_owner,sizing,native_image,deadline_ns,protected_remaining_ns):
    """Only after qualified whole-run ETA/profile/readiness checks. Never retry."""
    require(os.geteuid()==0 and type(namespace_owner) is namespaces._NamespaceOwner,'actual root-owned namespace owner required')
    require(native_image.sha256==resources.NATIVE_SHA and native_image.size_bytes==resources.NATIVE_SIZE,
        'unchanged frozen native image required')
    budget=requirements(sizing);admission=_admit(sizing,budget,namespace_owner,deadline_ns,protected_remaining_ns)
    require(archive.hash_file(native_image.path,max_bytes=native_image.size_bytes,
        deadline_ns=min(deadline_ns,time.monotonic_ns()+60*10**9))
        ==archive.PhysicalBinding(native_image.size_bytes,native_image.sha256),
        'actual frozen native bytes differ before source consumption')
    ROOT.mkdir(mode=0o700);namespaces._sync_directory(ROOT.parent);permit=None;authored=None
    st=ROOT.stat(follow_symlinks=False);directory_identity=(st.st_dev,st.st_ino)
    try:
        _save(ROOT/'intent.json',dict(schema_version=SCHEMA,sizing_sha256=SIZING_SHA,
            window_binding=namespace_owner.proof()['window_binding'],source_deadline_ns=deadline_ns,
            partial_source_admission=admission,automatic_retry=False,full_ext008_admission=False,execution_authority=False))
        permit=namespace_owner.consume_generation(deadline_ns=deadline_ns,protected_remaining_ns=protected_remaining_ns)
        _run_child(budget,sizing['blueprint']['master_seed_hex'],namespaces.ROOT/'sources',deadline_ns)
        bank=archive.parse_json(namespaces._protected(ROOT/'bank.json',CONTROL_BYTES))
        exact,records=_realize(sizing,budget,bank)
        plan,preparation=planning.prepare(exact,worker=native_image,deadline_ns=deadline_ns)
        _save(ROOT/'plan.json',plan,16*1024**2);_save(ROOT/'plan-preparation.json',preparation)
        # Exactly one independent accepted-generator pass, streaming in the
        # bounded parent, followed by sealing all originals in the same owner.
        with namespaces.sources.verified_sources(plan=plan,seed_id=budget['jobs'][0]['declaration']['seed_id'],records=records,
                maximum_source_bytes=budget['maximum_source_bytes'],maximum_vector_bytes=budget['maximum_vector_bytes'],
                verification_deadline_ns=deadline_ns,valid_until_ns=namespace_owner.proof()['window_binding']['end_monotonic_ns']) as source_owner:
            binding=namespace_owner.bind_sources(permit=permit,source_owner=source_owner,plan=plan)
            completion=_save(ROOT/'completion.json',dict(schema_version=SCHEMA,plan_sha256=planning.sha(plan),
                completed_monotonic_ns=time.monotonic_ns(),source_generation_deadline_ns=deadline_ns,
                original_generation_passes=1,independent_generation_verification_passes=1,
                namespace_source_binding=binding['source_bank_binding'],full_ext008_admission=False,execution_authority=False))
            _before(deadline_ns)
            metadata=[]
            for path in sorted(ROOT.iterdir()):
                raw=namespaces._protected(path,16*1024**2);metadata.append(dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
            require(sum(r['size_bytes'] for r in metadata)<=METADATA_BYTES and len(metadata)<=METADATA_INODES,
                'source-author metadata reservation exceeded')
            authored=_AuthoredSources(token=_TOKEN,namespace_owner=namespace_owner,source_owner=source_owner,
                plan=plan,records=records,completion=completion,metadata=metadata)
            authored.proof();yield authored
    except BaseException as error:
        namespace_owner._failure(error)
        if authored is not None:authored.failed=True
        with contextlib.suppress(BaseException):
            st=ROOT.stat(follow_symlinks=False)
            if (st.st_dev,st.st_ino)==directory_identity:
                _save(ROOT/'failure.json',dict(schema_version=SCHEMA,
                    failure=f'{type(error).__name__}: {str(error)[:4096]}',source_generation_consumed=permit is not None,
                    partial_outputs_retained=True,automatic_retry=False,execution_authority=False),8192)
        raise
    finally:
        if authored is not None:authored.closed=True
