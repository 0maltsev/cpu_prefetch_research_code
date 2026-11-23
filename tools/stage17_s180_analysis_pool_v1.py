"""Fixed S180 archive-analysis workers; no collection or custody admission.

The qualified outer authenticates completed collection and original custody.
Only actual child completion and fresh output bindings count here. Failed
spools/results stay retained, and the original analysis phase cannot retry.
"""
from __future__ import annotations
import contextlib
import ctypes
from dataclasses import asdict
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import select
import signal
import stat
import struct
import time
from types import SimpleNamespace

import stage17_s180_analysis_phase_v1 as phase
import stage17_s180_archive_analysis_v1 as worker
import stage17_s180_family_validation_v1 as family

archive=worker.archive
require=phase.require
SCHEMA='cpu-prefetch-stage17-s180-analysis-pool/1'
FRAME_MAX=65536
CONSOLE_MAX=16384
CLEANUP_NS=120*10**9
META_MAX=4*1024**2
_CONTEXTS=family.CONTEXTS


def before(deadline):require(time.monotonic_ns()<deadline,'original analysis deadline expired')


def _save(path,value):
    raw=archive.canonical(value);require(len(raw)<=META_MAX,'bounded pool metadata exceeded')
    worker.runtime.custody._write_new(path,raw)
    return dict(file_name=path.name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _send(fd,value):
    raw=archive.canonical(value);require(len(raw)<=FRAME_MAX,'worker frame bound exceeded')
    data=struct.pack('<I',len(raw))+raw
    while data:
        n=os.write(fd,data);require(n>0,'worker pipe made no progress');data=data[n:]


def _read(fd,buffer,maximum):
    while True:
        try:block=os.read(fd,min(65536,maximum-len(buffer)+1))
        except BlockingIOError:return False
        if not block:return True
        if len(buffer)+len(block)>maximum:
            buffer.extend(block[:maximum-len(buffer)])
            require(False,'bounded worker transport/console exceeded; prefix retained')
        buffer.extend(block)


def _frames(buffer):
    while len(buffer)>=4:
        size=struct.unpack_from('<I',buffer)[0];require(0<size<=FRAME_MAX,'invalid worker frame extent')
        if len(buffer)<4+size:return
        raw=bytes(buffer[4:4+size]);del buffer[:4+size]
        value=archive.parse_json(raw);require(archive.canonical(value)==raw,'noncanonical worker message')
        yield value


def _snapshot(directory,publication):
    root,identity=worker.directory(directory,owned=True)
    require(publication['output_root_identity']==dict(device=identity[0],inode=identity[1]),'published output root differs')
    rows=[];charge=0
    for path in sorted(root.iterdir()):
        s=path.stat(follow_symlinks=False)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and not s.st_mode&0o022,'unsafe published worker object')
        charge=archive.checked_sum(charge,max(s.st_size,s.st_blocks*512))
        rows.append(dict(file_name=path.name,stamp=list(archive.file_stamp(s))))
    require(len(rows)+1<=18 and charge<=publication['maximum_output_bytes'],'published output exceeds its budget')
    for item in publication['joined']:
        for binding in (item['artifact'],item['join_audit'],*item['raw_stream_envelopes']):
            s=(root/binding['file_name']).stat(follow_symlinks=False)
            require(s.st_size==binding['size_bytes'],'published artifact extent differs')
    return dict(root_identity=list(identity),files=rows,charged_bytes=charge)


def _child(gate,ready,progress,console,jobs,profile,limits,cpu,parent,deadline,mask):
    try:
        os.setsid()
        for number in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP,signal.SIGCHLD):signal.signal(number,signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK,mask)
        libc=phase.supervisor.predecessor._LIBC;death=ctypes.c_int()
        require(libc.prctl(1,signal.SIGKILL,0,0,0)==0
            and libc.prctl(2,ctypes.byref(death),0,0,0)==0 and death.value==signal.SIGKILL
            and os.getppid()==parent,'actual parent-death fail-stop/readback differs')
        for fd in list(map(int,os.listdir('/proc/self/fd'))):
            if fd>2 and fd not in (gate,ready,progress,console):
                with contextlib.suppress(OSError):os.close(fd)
        os.umask(0o077)
        null=os.open('/dev/null',os.O_RDONLY)
        if null!=0:os.dup2(null,0);os.close(null)
        os.dup2(console,1);os.dup2(console,2);os.close(console)
        file_bound=max([META_MAX,*[max(j['canonical_bytes_bound'],j['maximum_output_bytes']) for j in jobs]])
        for kind,value in ((resource.RLIMIT_AS,phase.bounds.ANALYSIS_CHILD_AS),(resource.RLIMIT_FSIZE,file_bound),
                (resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0),
                (resource.RLIMIT_CPU,max(1,(deadline-time.monotonic_ns()+10**9-1)//10**9))):
            resource.setrlimit(kind,(value,value));require(resource.getrlimit(kind)==(value,value),'worker rlimit readback differs')
        os.sched_setaffinity(0,{cpu});require(os.sched_getaffinity(0)=={cpu},'worker affinity readback differs')
        packet=dict(kind='READY',pid=os.getpid(),parent_pid=os.getppid(),session=os.getsid(0),
            process_group=os.getpgrp(),cpu=cpu,start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19],
            address_space=list(resource.getrlimit(resource.RLIMIT_AS)),open_files=list(resource.getrlimit(resource.RLIMIT_NOFILE)),
            parent_death_signal=death.value)
        _send(ready,packet);os.close(ready)
        require(os.read(gate,1)==b'G','analysis parent did not release worker');os.close(gate)
        codec=worker.load_codec(profile,deadline_ns=deadline)
        ordinals=[]
        for job in jobs:
            result=worker.analyze_capture(codec=codec,decode_limits=limits,expected_cpu=cpu,expected_parent_pid=parent,**job)
            output=Path(job['output_directory']);publication=result['publication'];ordinal=result['execution_ordinal']
            raw=(output/'complete.json').read_bytes();require(len(raw)<=META_MAX and archive.parse_json(raw)==publication,'actual worker manifest differs')
            _send(progress,dict(kind='CAPTURE',execution_ordinal=ordinal,
                manifest=dict(file_name='complete.json',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
                output_snapshot=_snapshot(output,publication),canonical_spool_removed=result['canonical_spool_removed'],
                maximum_resident_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
            ordinals.append(ordinal)
        _send(progress,dict(kind='DONE',execution_ordinals=ordinals));os.close(progress);os._exit(0)
    except BaseException as error:
        with contextlib.suppress(BaseException):_send(progress,dict(kind='FAILED',reason=type(error).__name__+': '+str(error)[:4096]))
        os._exit(1)


def _partitions(jobs):
    """Two workers per shared context; no subset, pooling or measurement order change."""
    slots=[[] for _ in range(12)];sizes=[0]*12
    for context_index,context in enumerate(_CONTEXTS):
        selected=[job for job in jobs if (job['capture_row']['placement'],job['capture_row']['working_set_class'])==context]
        for job in sorted(selected,key=lambda j:(-j['canonical_bytes_bound'],j['capture_row']['execution_ordinal'])):
            index=min((context_index*2,context_index*2+1),key=lambda i:(sizes[i],i))
            slots[index].append(job);sizes[index]+=job['canonical_bytes_bound']
    require(sum(map(len,slots))==len(jobs),'unknown shared analysis context')
    return slots


def _pipes():
    pairs=[]
    try:
        for _ in range(4):pairs.append(os.pipe2(os.O_CLOEXEC))
        return pairs
    except BaseException:
        for pair in pairs:
            for fd in pair:os.close(fd)
        raise


class _PoolCleanupView:
    """Exclude only other actual held leaders; retain every unknown orphan.

    An adopted child is fatal to the pool even when its original worker parent
    is no longer identifiable. This view makes no biological-parent assertion.
    """
    def __init__(self,model,leader,children):
        self.model=model;self.leader=leader;self.children=children;self.snapshot=model.snapshot

    def verify_stable(self):self.model.verify_stable()

    def identity_for_local_pid(self,pid):return self.model.identity_for_local_pid(pid)

    def process_group_members(self,pgid):return self.model.process_group_members(pgid)

    def direct_children(self):
        rows=self.model.direct_children()
        for child in self.children:
            pid=child['pid']
            if pid==self.leader or pid not in rows:continue
            identity=rows[pid];packet=child.get('ready_packet')
            if packet is not None and str(identity.start_time_ticks)==packet['start_ticks'] and identity.local_pgid==pid:
                del rows[pid]
        return rows


def _run_pool(owner,jobs,profile,limits,root):
    """Process core; public admission below requires all180 original captures."""
    owner.check();deadline=owner.deadline_ns-CLEANUP_NS;before(deadline)
    require(len(owner.cpus)==12 and len(set(owner.cpus))==12,'actual twelve-CPU phase required')
    slots=_partitions(jobs);children=[];records={};failure=None;previous={};all_cleanup=[];parent_pid=os.getpid()
    def interrupted(number,frame):raise phase.resources.ResourceError('analysis interrupted by signal '+str(number))
    try:
        for number in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
        for index,(cpu,assigned) in enumerate(zip(owner.cpus,slots,strict=True)):
            before(deadline)
            (gate_r,gate_w),(ready_r,ready_w),(progress_r,progress_w),(console_r,console_w)=_pipes()
            for fd in (ready_r,progress_r,console_r):os.set_blocking(fd,False)
            mask=signal.pthread_sigmask(signal.SIG_BLOCK,set(previous));pid=None
            try:
                pid=os.fork()
                if pid==0:_child(gate_r,ready_w,progress_w,console_w,assigned,profile,limits,cpu,parent_pid,deadline,mask)
                child=dict(index=index,pid=pid,pidfd=None,process=SimpleNamespace(pid=pid,returncode=None),
                    gate=gate_w,ready_fd=ready_r,progress_fd=progress_r,console_fd=console_r,
                    ready=bytearray(),progress=bytearray(),console=bytearray(),released=False,
                    jobs=assigned,seen=[],done=False,progress_eof=False,handshake=False)
                children.append(child);child['pidfd']=os.pidfd_open(pid)
            finally:
                for fd in (gate_r,ready_w,progress_w,console_w):os.close(fd)
                if pid is None:
                    for fd in (gate_w,ready_r,progress_r,console_r):os.close(fd)
                if pid!=0:signal.pthread_sigmask(signal.SIG_SETMASK,mask)
            end=min(deadline,time.monotonic_ns()+10*10**9)
            while not child['handshake']:
                before(end);eof=_read(ready_r,child['ready'],FRAME_MAX+4);_read(console_r,child['console'],CONSOLE_MAX)
                packets=list(_frames(child['ready']))
                if packets:
                    require(len(packets)==1 and not child['ready'],'one actual readiness frame required')
                    packet=packets[0];identity=owner.lease.identity_model.identity_for_local_pid(pid)
                    require(packet['kind']=='READY' and packet['pid']==pid and packet['parent_pid']==os.getpid()
                        and packet['process_group']==packet['session']==pid and identity.local_pgid==pid and os.getsid(pid)==pid
                        and packet['cpu']==cpu and os.sched_getaffinity(pid)=={cpu}
                        and packet['parent_death_signal']==signal.SIGKILL,'actual ready worker identity/affinity differs')
                    require(packet['start_ticks']==Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19],
                        'actual ready worker birth differs')
                    require(tuple(packet['address_space'])==resource.prlimit(pid,resource.RLIMIT_AS)==(phase.bounds.ANALYSIS_CHILD_AS,)*2,
                        'actual child AS differs')
                    require(tuple(packet['open_files'])==resource.prlimit(pid,resource.RLIMIT_NOFILE)==(128,128),'actual child descriptor bound differs')
                    child['handshake']=True;child['ready_packet']=packet
                    os.close(ready_r);child['ready_fd']=None
                else:
                    require(not eof and phase.supervisor._peek_leader_exit_held(pid,[]) is None,'worker exited before readiness')
                    select.select([ready_r],[],[],.02)
        for child in children:
            require(os.write(child['gate'],b'G')==1,'worker release made no progress');os.close(child['gate']);child['gate']=None;child['released']=True
        while True:
            before(deadline);all_exited=True
            fs=os.statvfs(root)
            require(fs.f_bavail*fs.f_frsize>=worker.runtime.custody.RESERVE,'actual analysis failure reserve exhausted')
            for child in children:
                # WNOWAIT precedes the pipe drain: every byte written before
                # an observed exit must be read before judging completion.
                exited=phase.supervisor._peek_leader_exit_held(child['pid'],[]) is not None
                eof=_read(child['progress_fd'],child['progress'],FRAME_MAX*2+8)
                _read(child['console_fd'],child['console'],CONSOLE_MAX)
                for value in _frames(child['progress']):
                    require(value['kind']!='FAILED','required capture failed: '+str(value.get('reason','')))
                    require(not child['done'],'worker sent data after completion')
                    if value['kind']=='CAPTURE':
                        ordinal=value['execution_ordinal'];position=len(child['seen'])
                        require(position<len(child['jobs']) and ordinal==child['jobs'][position]['capture_row']['execution_ordinal']
                            and ordinal not in records and value['canonical_spool_removed'] is True,'worker capture order/count/cleanup differs')
                        output=Path(child['jobs'][position]['output_directory'])
                        with archive.open_regular(output/'complete.json') as stream:raw=stream.read(META_MAX+1)
                        require(len(raw)<=META_MAX and dict(file_name='complete.json',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())==value['manifest'],
                            'actual completed worker manifest binding differs')
                        publication=archive.parse_json(raw);require(_snapshot(output,publication)==value['output_snapshot'],'worker output changed after completion')
                        child['seen'].append(ordinal);records[ordinal]=dict(value,worker_index=child['index'])
                    else:
                        require(value['kind']=='DONE' and value['execution_ordinals']==child['seen']
                            and len(child['seen'])==len(child['jobs']),'incomplete worker terminal frame')
                        child['done']=True
                require(not eof or (not child['progress'] and child['done']),'worker exited without complete framed results')
                require(not exited or child['done'],'worker exited before its completed data')
                all_exited=all_exited and exited
            if all_exited:break
            select.select([c['progress_fd'] for c in children],[],[],.02)
        require(len(records)==len(jobs),'missing required original analysis')
    except BaseException as error:failure=error
    finally:
        def cleanup_signal(number,frame):
            nonlocal failure
            failure=failure or phase.resources.ResourceError('signal during mandatory analysis cleanup '+str(number))
        for number in previous:signal.signal(number,cleanup_signal)
        for child in children:
            try:
                if not child['handshake']:
                    if child['pidfd'] is not None:signal.pidfd_send_signal(child['pidfd'],signal.SIGKILL)
                    else:os.kill(child['pid'],signal.SIGKILL)
                    child['process'].returncode=phase.supervisor._waitpid_leader_fail_stop(child['pid'],[])
                    cleanup=dict(leader_reaped=True,pre_release_stop=True,returncode=child['process'].returncode)
                else:
                    cleanup=asdict(phase.supervisor.cleanup_process_group(child['process'],force_stop=failure is not None or not child['released'],
                        leader_wait_deadline_ns=min(owner.deadline_ns,time.monotonic_ns()+phase.supervisor.predecessor.TERM_GRACE_NS),
                        global_deadline_ns=owner.deadline_ns,
                        identity_model=_PoolCleanupView(owner.lease.identity_model,child['pid'],children)))
                    all_cleanup.append(dict(worker_index=child['index'],pid=child['pid'],startup=child.get('ready_packet'),
                        cleanup=worker.runtime._jsonable(cleanup)))
                    require(cleanup['leader_reaped'] and cleanup['process_group_gone']
                        and not cleanup['cleanup_deadline_overrun'] and not cleanup['leader_wait_timed_out']
                        and not cleanup['descendants_detected_after_leader_exit'],'abnormal analysis worker cleanup')
                    if failure is None:require(cleanup['returncode']==0,'analysis worker nonzero exit')
                if not child['handshake']:
                    all_cleanup.append(dict(worker_index=child['index'],pid=child['pid'],startup=child.get('ready_packet'),
                        cleanup=worker.runtime._jsonable(cleanup)))
            except BaseException as error:failure=failure or error
            for key in ('console_fd','progress_fd'):
                with contextlib.suppress(BaseException):_read(child[key],child[key[:-3]],CONSOLE_MAX if key=='console_fd' else FRAME_MAX*2+8)
            with contextlib.suppress(BaseException):
                worker.runtime.custody._write_new(root/'workers'/f'worker-{child["index"]}-console.txt',bytes(child['console']))
            for key in ('gate','ready_fd','progress_fd','console_fd','pidfd'):
                if child.get(key) is not None:
                    with contextlib.suppress(OSError):os.close(child[key])
        for number,handler in previous.items():signal.signal(number,handler)
        if owner.lease.identity_model.direct_children():failure=failure or phase.resources.ResourceError('analysis left owned descendants')
        if failure is None:
            try:
                owner.check()
                for job in jobs:
                    ordinal=job['capture_row']['execution_ordinal'];record=records[ordinal]
                    publication=archive.parse_json((Path(job['output_directory'])/'complete.json').read_bytes())
                    require(_snapshot(Path(job['output_directory']),publication)==record['output_snapshot'],
                        'retained output changed after actual worker reap')
            except BaseException as error:failure=error
        report=dict(schema_version=SCHEMA,workers_started=len(children),required_captures=len(jobs),
            completed_capture_ordinals=sorted(records),cleanup=all_cleanup,status='PASSED' if failure is None else 'FAILED',
            failure=None if failure is None else str(failure)[:4096],automatic_retry=False,
            actual_worker_completion_verified=failure is None,original_archive_custody_verified=False,
            full_family_validity_established=False,execution_authority=False,phase18_authority=False)
        if failure is not None:owner.failed=True
        _save(root/'pool-processes.json',report)
    if failure is not None:owner.failed=True;raise failure
    return records,report


def _jobs(plan,native_result,inputs,*,program,scratch,captures,session_id,output_bounds):
    require(type(inputs) is list and len(inputs)==180,'all180 original checkpoint/custody inputs required')
    rows=sorted(plan['blueprint']['captures'],key=lambda r:r['execution_ordinal']);plan_sha=family.sha(plan);jobs=[]
    family._native(native_result,plan,session_id,plan_sha)
    for ordinal,(row,entry,item,output) in enumerate(zip(rows,plan['captures'],inputs,output_bounds,strict=True)):
        require(type(item) is dict and set(item)=={'checkpoint','registry_proof'},'exact original analysis input fields')
        checkpoint=item['checkpoint'];proof=item['registry_proof']
        require(checkpoint['execution_ordinal']==proof['execution_ordinal']==ordinal
            and checkpoint['session_id']==session_id and checkpoint['plan_sha256']==plan_sha
            and checkpoint['program_scope_sha256']==plan['storage']['program_scope_sha256'],'original ordered input lineage differs')
        originals=worker.capture.checkpoint_contract.original_references(checkpoint)
        require(len(originals)==8,'complete original capture required')
        worker.analysis_input.check(proof)
        canonical_bytes=archive.checked_sum(*(r['size_bytes'] for r in originals))
        require(canonical_bytes<=entry['execution_budget']['max_output_bytes'],'original source bytes exceed admitted capture bound')
        cleanup=native_result['contexts_after_family_release'][_CONTEXTS.index((row['placement'],row['working_set_class']))]
        jobs.append(dict(program_root=program,scratch_root=scratch,output_directory=captures/f'capture-{ordinal}',
            registry_proof=proof,checkpoint=checkpoint,capture_row=row,entry=entry,hardware=plan['hardware'],
            master_seed_hex=plan['blueprint']['master_seed_hex'],family_context_cleanup=cleanup,plan_sha256=plan_sha,
            program_scope_sha256=plan['storage']['program_scope_sha256'],session_id=session_id,
            canonical_bytes_bound=canonical_bytes,maximum_output_bytes=output['maximum_output_bytes']))
    return jobs


def _usage(root):
    charge=0;count=0;seen=set()
    for current,dirs,files in os.walk(root,followlinks=False):
        for path in (Path(current),*(Path(current)/name for name in files)):
            s=path.stat(follow_symlinks=False);require(not stat.S_ISLNK(s.st_mode),'unexpected analysis symlink')
            require(stat.S_ISDIR(s.st_mode) or (stat.S_ISREG(s.st_mode) and s.st_nlink==1),'unexpected analysis object')
            key=s.st_dev,s.st_ino;require(key not in seen,'aliased analysis inventory');seen.add(key)
            charge=archive.checked_sum(charge,max(s.st_size,s.st_blocks*512));count+=1
        for name in dirs:require(not (Path(current)/name).is_symlink(),'unexpected analysis directory symlink')
    return charge,count


def run_analysis(*,phase_owner,inputs,native_result,session_id,program_root,archive_profile,decode_limits,
                 output_directory,other_workspace_committed_bytes,other_scratch_committed_bytes):
    """Analyze all180 original captures once under an actual owned phase.

    The qualified outer must independently authenticate completed native
    collection, these original custody inputs/package and aggregate census.
    No metadata success document can construct the required resource owner;
    this callable neither grants that upstream admission nor family validity.
    """
    require(type(phase_owner) is phase._AnalysisPhase,'actual owned analysis phase required')
    phase_owner.check();require(not phase_owner._pool_consumed,'analysis pool already consumed; no retry')
    phase_owner._pool_consumed=True;root=None;lock=None;identity=None
    try:
        plan=archive.parse_json(phase_owner.environment_owner._plan)
        require(family.sha(plan)==phase_owner.plan_sha256,'original phase/plan differs')
        require(type(session_id) is str and bool(session_id),'original session identity required')
        require(type(archive_profile) is worker.runtime.RuntimeProfile and type(decode_limits) is archive.DecodeLimits,
            'actual archive profile and finite inverse limits required')
        require(archive_profile.decoder.implementation_profile_sha256==plan['storage']['implementation_profile_sha256'],
            'original admitted archive implementation profile differs')
        for value in (other_workspace_committed_bytes,other_scratch_committed_bytes):archive.uint(value,'explicit other committed storage')
        envelope=phase.bounds.analysis_output_envelope(plan)
        require(envelope['workspace_bytes_upper']+other_workspace_committed_bytes<=worker.runtime.custody.WORKSPACE,
            'retained analysis plus other workspace exceeds approved W')
        program,_=worker.directory(program_root);output=Path(output_directory);worker.directory(output.parent,owned=True)
        require(output.is_absolute() and output.name not in ('','.','..') and not output.is_relative_to(program),
            'exclusive protected analysis location outside original programme required')
        # Validate every input before creating a partial analysis tree.
        jobs=_jobs(plan,native_result,inputs,program=program,scratch=output/'scratch',captures=output/'captures',
            session_id=session_id,output_bounds=envelope['capture_bounds'])
        own_scratch=archive.checked_sum(12*max(j['canonical_bytes_bound'] for j in jobs),17*phase.bounds.GIB)
        scratch=archive.checked_sum(own_scratch,other_scratch_committed_bytes)
        require(scratch<=worker.runtime.custody.SCRATCH,'active and retained scratch exceed approved S')
        fs=os.statvfs(output.parent)
        require(fs.f_bavail*fs.f_frsize>=envelope['workspace_bytes_upper']+own_scratch+worker.runtime.custody.RESERVE
            and fs.f_favail>=envelope['required_inodes'],'actual analysis free-space/inode envelope insufficient')
        output.mkdir(mode=0o700);root=output;_,identity=worker.directory(root,owned=True)
        lock=os.open(root/'analysis.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for name in ('captures','workers','scratch'):(root/name).mkdir(mode=0o700)
        _save(root/'analysis-intent.json',dict(schema_version=SCHEMA,plan_sha256=phase_owner.plan_sha256,
            original_phase=phase_owner.check(),captures=180,worker_count=12,storage_output_envelope=envelope,
            scratch_bytes_upper=scratch,other_workspace_committed_bytes=other_workspace_committed_bytes,
            other_scratch_committed_bytes=other_scratch_committed_bytes,automatic_retry=False,
            original_archive_custody_verified=False,execution_authority=False,phase18_authority=False))
        records,processes=_run_pool(phase_owner,jobs,archive_profile,decode_limits,root)
        require(set(records)==set(range(180)),'all original180 results required')
        workspace,objects=_usage(root/'captures');scratch_actual,_=_usage(root/'scratch')
        require(workspace<=sum(r['maximum_output_bytes'] for r in envelope['capture_bounds'])
            and workspace+other_workspace_committed_bytes+META_MAX<=worker.runtime.custody.WORKSPACE
            and scratch_actual+other_scratch_committed_bytes<=worker.runtime.custody.SCRATCH,'actual retained allocated/logical output exceeds W/S')
        require(worker.directory(root)[1]==identity,'analysis output root replaced')
        phase_owner.check()
        complete=dict(schema_version=SCHEMA,status='ALL180_ANALYZED_PENDING_FAMILY_VALIDATION',plan_sha256=phase_owner.plan_sha256,
            completed_captures=180,records=[records[i] for i in range(180)],actual_worker_completion_verified=True,
            allocated_or_logical_capture_charge_bytes=workspace,canonical_scratch_charge_bytes=scratch_actual,
            original_archive_custody_verified=False,full_family_validity_established=False,
            aggregate_resource_admission_performed=False,execution_authority=False,phase18_authority=False)
        binding=_save(root/'complete.pending.json',complete);phase_owner.check()
        total,objects=_usage(root)
        require(total-workspace-scratch_actual<=phase.bounds.ANALYSIS_FAMILY_METADATA
            and objects<=envelope['required_inodes'],'actual family metadata/object budget exceeded')
        os.link(root/'complete.pending.json',root/'complete.json',follow_symlinks=False)
        (root/'complete.pending.json').unlink();worker.runtime.custody._sync_dir(root);phase_owner.check()
        return dict(binding=dict(binding,file_name='complete.json'),result=complete)
    except BaseException as error:
        phase_owner.failed=True
        same_root=False
        if root is not None:
            with contextlib.suppress(OSError,ValueError):same_root=worker.directory(root)[1]==identity
        if same_root:
            with contextlib.suppress(BaseException):
                if (root/'complete.json').exists():(root/'complete.json').rename(root/'uncommitted-complete.json')
                _save(root/'failure.json',dict(schema_version=SCHEMA,status='FAILED',reason=str(error)[:4096],
                    original_analysis_attempt_consumed=True,automatic_retry=False,execution_authority=False,phase18_authority=False))
        raise
    finally:
        if lock is not None:os.close(lock)
