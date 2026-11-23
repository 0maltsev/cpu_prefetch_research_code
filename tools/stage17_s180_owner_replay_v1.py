"""Owned original-journal replay under its original UNIX credentials.

Root controls S180 hardware; the historical transport/signature snapshot needs
a process with the original owner's full credentials and ordinary procfs access.
Only actual supervised execution creates the returned view. No report-file
loader, scientific action, key permission change or execution authority exists.
The qualified outer authenticates this source closure and all replay locators.
"""
from __future__ import annotations
import contextlib
import ctypes
from dataclasses import asdict,dataclass
import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import select
import signal
import threading
import time
from types import SimpleNamespace

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
import stage17_state_journal_v62 as original
import stage17_q16a_continuation_admission_v1 as readers

SCHEMA='cpu-prefetch-stage17-s180-owned-original-replay/1'
OWNER_UID=OWNER_GID=1000
CPU=3
CHILD_AS=8*1024**3
DATA_MAX=32*1024**2
# The unchanged legacy reader snapshots its accepted 89.7 MB input archive.
# Its bounded temporary files are distinct from the small returned JSON frame.
CHILD_FILE_BYTES=256*1024**2
CONSOLE_MAX=16384
CLEANUP_NS=120*10**9
FIELDS={'repository_root','evidence_root','latest_journal','journal_directory','pilot_archive','pilot_sidecar'}
# Closed data interface consumed by the S180 ancestry, trust and compatibility
# readers. Legacy live release/context objects never leave their owner process.
CONTEXT_FIELDS={
    'S17-EXT-001':(), 'S17-EXT-002':('stand_id',), 'S17-EXT-003':('trust',),
    'S17-EXT-004':(), 'S17-EXT-005':(),
    'S17-EXT-006':('source_revision','inventory_sha256','release_artifact_sha256',
        'release_artifact_size_bytes','archive_bundle_root','release_artifact_path'),
    'S17-EXT-007':('calibration_scope','data_provenance_accepted','legacy_statistical_freeze_satisfied')}
_TOKEN=object()


def require(ok,message):
    if not ok:raise archive.ArchiveError('S180 owner replay: '+message)


def before(deadline):require(time.monotonic_ns()<deadline,'original replay deadline expired')


def _project(result):
    return runtime._jsonable(dict(current_state=result.current_state,pilot_ready=result.pilot_ready,
        resolved_input_ids=list(result.resolved_input_ids),missing_input_ids=list(result.missing_input_ids),
        resolution_count=result.resolution_count,transition_count=result.transition_count,
        latest_journal_sha256=result.latest_journal_sha256,action_ready=result.action_ready,stand_status=result.stand_status,
        resolutions={key:dict(input_id=row.input_id,resolution_id=row.resolution_id,sha256=row.sha256,
            semantic_context={name:row.semantic_context[name] for name in CONTEXT_FIELDS[key]})
            for key,row in result.resolutions.items()}))


def _child(gate,ready,console,output,arguments,uid,gid,parent,deadline,mask):
    try:
        os.setsid();os.dup2(console,1);os.dup2(console,2)
        null=os.open('/dev/null',os.O_RDONLY);os.dup2(null,0)
        keep={0,1,2,gate,ready,output}
        # Close inherited copies without flock(LOCK_UN): the parent's held
        # source/programme locks must remain held in its open descriptions.
        for name in os.listdir('/proc/self/fd'):
            fd=int(name)
            if fd not in keep:
                with contextlib.suppress(OSError):os.close(fd)
        os.sched_setaffinity(0,{CPU})
        resource.setrlimit(resource.RLIMIT_AS,(CHILD_AS,CHILD_AS))
        resource.setrlimit(resource.RLIMIT_FSIZE,(CHILD_FILE_BYTES,CHILD_FILE_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE,(1024,1024));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        if uid:os.setgroups([])
        os.setresgid(gid,gid,gid);os.setresuid(uid,uid,uid)
        require(os.getresuid()==(uid,)*3 and os.getresgid()==(gid,)*3 and (not uid or not os.getgroups()),
            'actual full owner credentials differ')
        libc=ctypes.CDLL(None,use_errno=True)
        require(libc.prctl(4,1,0,0,0)==0 and libc.prctl(3,0,0,0,0)==1,
            'ordinary owner procfs dumpability readback failed')
        death=ctypes.c_int()
        require(libc.prctl(1,signal.SIGKILL,0,0,0)==0 and libc.prctl(2,ctypes.byref(death),0,0,0)==0
            and death.value==signal.SIGKILL and os.getppid()==parent,'parent-death guard readback failed')
        for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(number,signal.SIG_DFL)
        signal.pthread_sigmask(signal.SIG_SETMASK,mask)
        require(os.write(ready,b'R')==1 and os.read(gate,2)==b'G','original replay gate failed')
        os.close(ready);os.close(gate);before(deadline)
        result=original.validate_operational_journal(**arguments,
            as_of_utc=datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds').replace('+00:00','Z'),
            allow_synthetic_test_evidence=False)
        raw=archive.canonical(_project(result));require(0<len(raw)<=DATA_MAX,'original replay result byte ceiling')
        position=0
        while position<len(raw):
            before(deadline);n=os.pwrite(output,raw[position:position+65536],position)
            require(n>0,'original replay result made no progress');position+=n
        fcntl.fcntl(output,fcntl.F_ADD_SEALS,runtime._SEALS);before(deadline)
        os._exit(0)
    except BaseException as error:
        with contextlib.suppress(OSError):os.write(2,(type(error).__name__+': '+str(error)[:2048]+'\n').encode())
        os._exit(1)


def _run(arguments,deadline,*,uid,gid):
    """Fixed forked reader; uid0 here is used only by private namespace tests."""
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and len(list(Path('/proc/self/task').iterdir()))==1
        and signal.getsignal(signal.SIGCHLD)==signal.SIG_DFL,'single-threaded default-SIGCHLD parent required')
    started=time.monotonic_ns();end=deadline-CLEANUP_NS;before(end)
    lease=supervisor.SupervisorLease();pid=process=pidfd=cleanup=None
    previous={};failure=None;released=False;console=bytearray();output=None
    fds=[]
    def pipe():
        pair=os.pipe2(os.O_CLOEXEC);fds.extend(pair);return pair
    def drain():
        while True:
            try:block=os.read(console_r,min(4096,CONSOLE_MAX-len(console)+1))
            except BlockingIOError:return
            if not block:return
            available=CONSOLE_MAX-len(console);console.extend(block[:available])
            require(len(block)<=available,'bounded original-reader console exceeded')
    def interrupted(number,frame):raise archive.ArchiveError('original replay interrupted by signal '+str(number))
    ready_r=ready_w=gate_r=gate_w=console_r=console_w=None
    observed=None;credentials=os.getresuid();groups=os.getresgid()
    try:
        ready_r,ready_w=pipe();gate_r,gate_w=pipe();console_r,console_w=pipe();os.set_blocking(console_r,False)
        output=os.memfd_create('s180-original-owner-result',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING);fds.append(output)
        lease.enter()
        for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
        mask=signal.pthread_sigmask(signal.SIG_BLOCK,set(previous))
        try:
            parent=os.getpid();pid=os.fork()
            if pid==0:_child(gate_r,ready_w,console_w,output,arguments,uid,gid,parent,end,mask)
            process=SimpleNamespace(pid=pid,returncode=None);pidfd=os.pidfd_open(pid);fds.append(pidfd)
        finally:
            if pid!=0:signal.pthread_sigmask(signal.SIG_SETMASK,mask)
        for fd in (ready_w,gate_r,console_w):os.close(fd);fds.remove(fd)
        handshake=min(end,time.monotonic_ns()+10*10**9)
        while True:
            before(handshake);drain()
            if select.select([ready_r],[],[],.05)[0]:
                require(os.read(ready_r,2)==b'R','original reader failed before readiness');break
            require(supervisor._peek_leader_exit_held(pid,[]) is None,'original reader exited before readiness')
        identity=lease.identity_model.identity_for_local_pid(pid)
        status={k:v.strip() for k,v in (line.split(':',1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)}
        require([int(v) for v in status['Uid'].split()]==[uid]*4
            and [int(v) for v in status['Gid'].split()]==[gid]*4 and (not uid or not status['Groups']),
            'actual reader kernel credentials differ')
        require(identity.local_pgid==pid and os.getsid(pid)==pid and os.sched_getaffinity(pid)=={CPU},
            'actual original-reader session/affinity differs')
        require(Path(f'/proc/{pid}/cgroup').read_bytes()==Path('/proc/self/cgroup').read_bytes(),
            'original reader escaped inherited control group')
        observed=dict(uid=uid,gid=gid,actual_uid_fields=[int(v) for v in status['Uid'].split()],
            actual_gid_fields=[int(v) for v in status['Gid'].split()],session_id=pid,start_ticks=identity.start_time_ticks,
            address_space_bytes=list(resource.prlimit(pid,resource.RLIMIT_AS)),
            file_size_bytes=list(resource.prlimit(pid,resource.RLIMIT_FSIZE)))
        require(observed['address_space_bytes']==[CHILD_AS,CHILD_AS],'actual original-reader AS differs')
        require(observed['file_size_bytes']==[CHILD_FILE_BYTES,CHILD_FILE_BYTES],
            'actual original-reader file limit differs')
        require(os.write(gate_w,b'G')==1,'original-reader release failed');released=True
        os.close(gate_w);fds.remove(gate_w)
        while supervisor._peek_leader_exit_held(pid,[]) is None:
            before(end);drain();time.sleep(.05)
        drain()
    except BaseException as error:failure=error
    finally:
        def cleanup_signal(number,frame):
            nonlocal failure
            failure=failure or archive.ArchiveError('signal during original-reader cleanup '+str(number))
        for number in previous:signal.signal(number,cleanup_signal)
        if process is not None:
            try:
                if not released:
                    if pidfd is None:
                        supervisor._peek_leader_exit_held(pid,[]);os.kill(pid,signal.SIGKILL)
                    else:signal.pidfd_send_signal(pidfd,signal.SIGKILL)
                    process.returncode=supervisor._waitpid_leader_fail_stop(pid,[])
                    require(not lease.identity_model.direct_children(),'unreleased original reader left descendants')
                else:
                    cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                        leader_wait_deadline_ns=min(end,time.monotonic_ns()+supervisor.predecessor.TERM_GRACE_NS),
                        global_deadline_ns=deadline,identity_model=lease.identity_model)
                    require(cleanup.returncode==0 and cleanup.leader_reaped and cleanup.process_group_gone
                        and not cleanup.descendants_detected_after_leader_exit and not cleanup.cleanup_deadline_overrun
                        and not cleanup.leader_wait_timed_out,'original-reader failure or abnormal cleanup')
            except BaseException as error:failure=failure or error
        try:
            if console_r is not None:drain()
            require(os.getresuid()==credentials and os.getresgid()==groups,'root parent credentials changed')
            if failure is None:
                before(deadline);raw=runtime._read_sealed(output,DATA_MAX);data=archive.parse_json(raw)
            else:data=None
        except BaseException as error:failure=failure or error;data=None
        for fd in fds:
            with contextlib.suppress(OSError):os.close(fd)
        for number,handler in previous.items():signal.signal(number,handler)
        try:lease.close()
        except BaseException as error:failure=failure or error
    report=dict(schema_version=SCHEMA,pid=pid,started_monotonic_ns=started,completed_monotonic_ns=time.monotonic_ns(),
        deadline_monotonic_ns=deadline,observed_reader=observed,cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),
        failure=None if failure is None else str(failure)[:2048],console_prefix=bytes(console).decode(errors='replace'),
        root_parent_credentials_preserved=os.getresuid()==credentials and os.getresgid()==groups,
        root_uids_before=list(credentials),root_uids_after=list(os.getresuid()),actual_owner_reader_completed=failure is None,
        execution_authority=False,phase18_authority=False)
    if failure is not None:
        error=archive.ArchiveError('owned original replay failed: '+str(failure));error.report=report;raise error from failure
    return data,report


@dataclass(frozen=True)
class Resolution:
    input_id:str
    resolution_id:str
    sha256:str
    semantic_context:dict


class _VerifiedOriginal:
    def __init__(self,*,token,data,report,arguments,anchors):
        require(token is _TOKEN,'only actual owner replay constructs original facts')
        require(data['resolution_count']==7 and data['transition_count']==3 and data['pilot_ready'] is False
            and set(data['resolutions'])=={f'S17-EXT-{i:03d}' for i in range(1,8)},'actual original-seven result differs')
        for key,row in data['resolutions'].items():
            require(row['input_id']==key and type(row['semantic_context']) is dict
                and set(row['semantic_context'])==set(CONTEXT_FIELDS[key]),'actual original resolution shape')
            archive.sha(row['sha256'],'original resolution')
        self._data=archive.canonical(data);self._report=archive.canonical(report);self.pid=os.getpid()
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();self._paths=anchors
        with archive.open_regular(arguments['latest_journal']) as stream:raw=stream.read(DATA_MAX+1)
        require(len(raw)<=DATA_MAX and hashlib.sha256(raw).hexdigest()==data['latest_journal_sha256'],
            'actual latest original journal changed after replay')
        journal=readers._json(raw)
        observed=set()
        for reference in journal['resolution_records']:
            path=arguments['evidence_root']/reference['path']
            with archive.open_regular(path) as stream:record_raw=stream.read(DATA_MAX+1)
            require(len(record_raw)<=DATA_MAX and hashlib.sha256(record_raw).hexdigest()==reference['sha256'],
                'original resolution bytes changed after replay')
            record=readers._json(record_raw);key=record['input_id']
            require(key in data['resolutions'] and key not in observed
                and data['resolutions'][key]['sha256']==reference['sha256']
                and data['resolutions'][key]['resolution_id']==record['resolution_id'],
                'actual reader result differs from original journal resolution bytes')
            observed.add(key)
        require(observed==set(CONTEXT_FIELDS),'all original input identities required')
        self.view()

    def view(self):
        require(self.pid==os.getpid() and os.getresuid()==(0,0,0)
            and self.boot==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'original replay belongs to another parent/boot')
        for path,before in self._paths.items():
            st=path.stat(follow_symlinks=False)
            require(before==(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns),'original journal changed after replay')
        data=archive.parse_json(self._data)
        data['resolutions']={k:Resolution(**r) for k,r in data['resolutions'].items()}
        for name in ('resolved_input_ids','missing_input_ids'):data[name]=tuple(data[name])
        return SimpleNamespace(**data)

    def proof(self):self.view();return archive.parse_json(self._report)


def _stamp(path):
    st=path.stat(follow_symlinks=False)
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def _anchors(arguments,deadline):
    path=arguments['latest_journal'];before=_stamp(path)
    with archive.open_regular(path) as stream:raw=stream.read(DATA_MAX+1)
    require(len(raw)<=DATA_MAX and before==_stamp(path),'stable bounded original journal required')
    document=readers._json(raw)
    require(len(document['resolution_records'])==7 and len(document['transition_records'])==3,
        'original seven/three journal required')
    result={path:before,arguments['journal_directory']:_stamp(arguments['journal_directory'])}
    for reference in (*document['resolution_records'],*document['transition_records']):
        relative=Path(reference['path'])
        require(not relative.is_absolute() and '..' not in relative.parts and len(relative.parts)==2
            and relative.parts[0]=='records','original record locator scope differs')
        member=arguments['evidence_root']/relative
        require(member.resolve(strict=True)==member,'canonical original record required')
        stamp=_stamp(member)
        require(archive.hash_file(member,max_bytes=DATA_MAX,deadline_ns=deadline).sha256==reference['sha256']
            and stamp==_stamp(member),'original record bytes changed')
        result[member]=stamp
    return result


def verify_original(*,base_replay_arguments,deadline_ns):
    """Qualified root parent only; preserve the legacy reader and owner checks."""
    require(os.getresuid()==(0,0,0),'actual root controller required')
    require(type(base_replay_arguments) is dict and set(base_replay_arguments)==FIELDS,'fixed original replay locators required')
    arguments={k:Path(v) for k,v in base_replay_arguments.items()}
    require(all(p.is_absolute() and p.resolve(strict=True)==p for p in arguments.values()),'canonical original replay locators required')
    require(type(deadline_ns) is int and time.monotonic_ns()+CLEANUP_NS<deadline_ns
        <=time.monotonic_ns()+600*10**9,'bounded original preflight deadline required')
    anchors=_anchors(arguments,deadline_ns)
    data,report=_run(arguments,deadline_ns,uid=OWNER_UID,gid=OWNER_GID)
    try:return _VerifiedOriginal(token=_TOKEN,data=data,report=report,arguments=arguments,anchors=anchors)
    except BaseException as error:
        error.report=dict(report,fact_view_validation_failure=str(error)[:2048]);raise
