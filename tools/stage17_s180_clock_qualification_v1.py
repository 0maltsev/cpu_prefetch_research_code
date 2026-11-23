"""Fixed S180 near/far qualification from an actual owned prepared environment.

Library only: the qualified outer operator supplies package/ETA/window gates.
No source generation, Q15, admission, pilot, retry or alternate backend exists.
The frozen helper performs the accepted clock evaluation; raw fields are checked
against that fixed method, not reinterpreted as a new estimator or full trace.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict
import datetime
import hashlib
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import threading
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
import stage17_s180_compaction_v1 as compaction
import stage17_s180_environment_v1 as environment

ROOT=environment.EVIDENCE.parent/'clock-qualification'
RAW_SCHEMA='cpu-prefetch-stage17-q15-clock-pair-raw/1'
SCHEMA='cpu-prefetch-stage17-s180-clock-qualification/1'
AS_BYTES=8*1024**3
MEMLOCK_BYTES=8*1024**2
FILE_BYTES=8192
CONSOLE_BYTES=16384
PAIR_NS=600*10**9
CLEANUP_NS=120*10**9
# Part of D334's existing 1MiB/64-inode external metadata headroom; not new quota.
METADATA_BYTES=512*1024
METADATA_INODES=16
RECORD_LIMITS={'attempt.json':4096,'intent.json':16384,'result.json':65536,'completion.json':8192,'failure.json':8192}
_TOKEN=object()


class ClockError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise ClockError('S180 clocks: '+message)


def _check_capture_deadline(deadline):
    require(time.monotonic_ns()<deadline,'original clock capture deadline expired')


def _utc():return datetime.datetime.now(datetime.UTC).isoformat().replace('+00:00','Z')


def verify_raw(value,pair):
    require(pair in ('near','far'),'fixed clock pair required')
    expected=dict(schema_version=RAW_SCHEMA,pair=pair,producer_cpu=0,consumer_cpu=1 if pair=='near' else 8,
        producer_pinned=True,consumer_pinned=True,producer_prime_read_count=100000,consumer_prime_read_count=100000,
        producer_delta_count=10000000,consumer_delta_count=10000000,producer_to_consumer_window_count=3,
        consumer_to_producer_window_count=3,exchanges_per_window=100000,
        producer_per_core_passed=True,consumer_per_core_passed=True,cross_core_passed=True)
    require(type(value) is dict and set(value)==set(expected),'closed original raw clock fields required')
    require(all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()),
        'accepted pair/count/pinning/evaluator result differs')
    return archive.parse_json(archive.canonical(value))


def _record(path,value):
    raw=archive.canonical(value);require(len(raw)<=RECORD_LIMITS[path.name],'bounded clock metadata required')
    compaction._save(path,value)
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _mkdir(path):
    path.mkdir(mode=0o700)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)


def _sync_raw(path):
    with archive.open_regular(path) as stream:
        actual=os.fstat(stream.fileno())
        require(actual.st_uid==0 and actual.st_nlink==1 and not actual.st_mode&0o022,
            'protected original raw clock output required')
        before=archive.file_stamp(actual);raw=stream.read(FILE_BYTES+1)
        require(len(raw)<=FILE_BYTES and archive.file_stamp(os.fstat(stream.fileno()))==before,
            'bounded stable raw clock output required')
        os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)
    return raw


def _place(entry):
    """Child-only actual limits, cgroup and controller affinity readbacks."""
    os.umask(0o077)
    require(os.umask(0o077)==0o077,'actual child output protection differs')
    for kind,value in ((resource.RLIMIT_AS,AS_BYTES),(resource.RLIMIT_MEMLOCK,MEMLOCK_BYTES),
        (resource.RLIMIT_FSIZE,FILE_BYTES),(resource.RLIMIT_NOFILE,128),(resource.RLIMIT_CORE,0)):
        resource.setrlimit(kind,(value,value))
        require(resource.getrlimit(kind)==(value,value),'actual clock child limit differs')
    raw=str(os.getpid()).encode();require(os.write(entry['descriptor'],raw)==len(raw),'clock placement failed')
    os.close(entry['descriptor'])
    require(compaction._membership(os.getpid())==entry['relative_path'],'actual clock child cgroup differs')
    os.sched_setaffinity(0,{entry['controller_cpu']})
    require(os.sched_getaffinity(0)=={entry['controller_cpu']},'actual clock child affinity differs')


def _capture(*,owner,image,pair,deadline,window):
    """Actual sealed image, held leader/subreaper, bounded pipes, durable evidence."""
    guard=owner.compaction_guard();guard.check(boundary='FAMILY_ENTRY')
    directory=ROOT/pair;_mkdir(directory)
    raw_path=directory/'clock-raw.json'
    started_utc=_utc();now=time.monotonic_ns();end=min(deadline-CLEANUP_NS,now+PAIR_NS)
    require(end>now,'original qualification budget omits cleanup')
    before=owner.admission_observation(plan_sha256=guard.owner['plan_sha256'])
    _record(directory/'intent.json',dict(pair=pair,worker_sha256=image.sha256,
        worker_size_bytes=image.size_bytes,plan_sha256=guard.owner['plan_sha256'],window_binding=window,
        started_monotonic_ns=now,measurement_deadline_monotonic_ns=end,qualification_deadline_monotonic_ns=deadline,
        actual_environment_before=before,automatic_retries=0,execution_authority=False))
    process=None;worker=None;cleanup=None;failure=None;raw_binding=None
    console=bytearray();diagnostics=[];lease=supervisor.SupervisorLease();previous={}
    def interrupted(number,frame):raise ClockError('clock qualification interrupted by signal '+str(number))
    with contextlib.ExitStack() as stack:
        executable=runtime._pin_image(image,end,stack)
        selector=selectors.DefaultSelector();stack.callback(selector.close)
        try:
            lease.enter()
            for number in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
            with owner.qualification_entry(plan_sha256=guard.owner['plan_sha256'],role=pair) as entry:
                try:
                    process=subprocess.Popen([f'/proc/self/fd/{executable}','--qualify-pair',pair,'--output',str(raw_path)],
                        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                        close_fds=True,pass_fds=(executable,entry['descriptor']),start_new_session=True,
                        preexec_fn=lambda:_place(entry),env={'PATH':'/usr/bin:/bin','LC_ALL':'C','LANG':'C','TZ':'UTC'})
                    worker=compaction.PinnedWorker(process.pid);guard.register_worker(worker,role=pair)
                    for stream in (process.stdout,process.stderr):
                        os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ)
                    exited=False
                    while not exited or selector.get_map():
                        _check_capture_deadline(end)
                        exited=supervisor._peek_leader_exit_held(process.pid,diagnostics) is not None
                        for key,_ in selector.select(timeout=.05):
                            block=os.read(key.fd,min(4096,CONSOLE_BYTES-len(console)+1))
                            if block:
                                console.extend(block);require(len(console)<=CONSOLE_BYTES,'clock console bound exceeded')
                            else:selector.unregister(key.fileobj)
                except BaseException as error:failure=error
                finally:
                    def cleanup_interrupted(number,frame):
                        nonlocal failure
                        failure=failure or ClockError('signal during mandatory clock cleanup '+str(number))
                    for number in previous:signal.signal(number,cleanup_interrupted)
                    if process is not None:
                        try:
                            cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None,
                                leader_wait_deadline_ns=min(end,time.monotonic_ns()+supervisor.predecessor.TERM_GRACE_NS),
                                global_deadline_ns=min(window['end_monotonic_ns'],time.monotonic_ns()+CLEANUP_NS),
                                identity_model=lease.identity_model)
                            require(cleanup.leader_reaped and cleanup.process_group_gone,'clock cleanup is incomplete')
                            require(cleanup.returncode==0 and not cleanup.descendants_detected_after_leader_exit
                                and not cleanup.cleanup_deadline_overrun and not cleanup.leader_wait_timed_out,
                                'clock helper failed or required abnormal cleanup')
                        except BaseException as error:failure=failure or error
                        for stream in (process.stdout,process.stderr):
                            if stream:stream.close()
                    if worker is not None:worker.close()
                if failure is not None:raise failure
                require(time.monotonic_ns()<deadline,'original qualification deadline expired')
                raw=_sync_raw(raw_path);verify_raw(archive.parse_json(raw),pair)
                raw_binding=dict(path=str(raw_path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                after=owner.admission_observation(plan_sha256=guard.owner['plan_sha256'])
                guard.check(boundary='FINAL')
        except BaseException as error:failure=failure or error
        finally:
            for number,handler in previous.items():signal.signal(number,handler)
            try:lease.close()
            except BaseException as error:failure=failure or error
        # Retain failed/partial raw output without interpreting it as a pass.
        if raw_binding is None and raw_path.exists():
            try:
                raw=_sync_raw(raw_path);raw_binding=dict(path=str(raw_path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            except BaseException as error:failure=failure or error
        result=dict(schema_version=SCHEMA,pair=pair,plan_sha256=guard.owner['plan_sha256'],window_binding=window,
            started_monotonic_ns=now,completed_monotonic_ns=time.monotonic_ns(),
            started_at_utc=started_utc,completed_at_utc=_utc(),
            worker_sha256=image.sha256,worker_size_bytes=image.size_bytes,raw=raw_binding,
            native_pid=None if process is None else process.pid,native_start_ticks=None if worker is None else worker.start_ticks,
            cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),console_hex=console.hex(),
            status='CLOCK_PAIR_QUALIFIED' if failure is None else 'STOPPED',
            failure=None if failure is None else str(failure)[:4096],
            actual_environment_after=None if failure is not None else after,
            full_qualification=False,execution_authority=False,phase18_authority=False)
        try:binding=_record(directory/'result.json',result)
        except BaseException as error:
            if failure is None:raise
            raise failure from error
        if failure is not None:raise failure
        return binding,raw_binding


class _VerifiedClocks:
    def __init__(self,*,token,owner,image,completion,bindings):
        require(token is _TOKEN,'actual owned near/far collection required')
        self.owner=owner;self.image=image;self._completion=archive.canonical(completion)
        self._bindings=archive.canonical(dict(bindings=bindings));self.pid=os.getpid();self.failed=False

    def proof(self,*,plan_sha256):
        require(not self.failed,'clock proof failed; no retry')
        try:return self._proof(plan_sha256=plan_sha256)
        except BaseException:
            self.failed=True;self.owner._qualification_failed=True
            raise

    def _proof(self,*,plan_sha256):
        require(self.pid==os.getpid(),'clock proof belongs to another process')
        self.owner._guard(plan_sha256);guard=self.owner.compaction_guard()
        require(guard.owner['plan_sha256']==plan_sha256,'clock plan differs')
        completion=archive.parse_json(self._completion)
        bindings=archive.parse_json(self._bindings)['bindings'];verified={}
        for row in (*bindings,completion):
            raw=compaction._root_file(Path(row['path']),65536)
            require(len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'],
                'original clock evidence changed')
            verified[row['path']]=raw
        require(archive.hash_file(self.image.path,max_bytes=self.image.size_bytes,
            deadline_ns=min(guard.guard.deadline_ns,time.monotonic_ns()+60*10**9))
            ==archive.PhysicalBinding(self.image.size_bytes,self.image.sha256),'original clock image changed')
        attempt=archive.parse_json(verified[bindings[0]['path']])
        finished=archive.parse_json(verified[completion['path']])
        return dict(schema_version=SCHEMA,plan_sha256=plan_sha256,window_binding=guard.owner['window'],
            completion=completion,selected_pairs=['near','far'],clock_pairs_qualified=True,
            qualification_started_monotonic_ns=attempt['started_monotonic_ns'],
            qualification_deadline_monotonic_ns=attempt['deadline_monotonic_ns'],
            clocks_completed_monotonic_ns=finished['completed_monotonic_ns'],
            full_qualification=False,execution_authority=False,phase18_authority=False)


def qualify_clocks(*,environment_owner,clock_image,deadline_ns):
    """One actual ordered family, after the qualified outer operator's ETA gate."""
    now=time.monotonic_ns()  # Include entry verification in the original stage cap.
    require(type(environment_owner) is environment._PreparedEnvironment and type(clock_image) is runtime.ImageBinding,
        'actual owned environment and qualified image binding required')
    guard=environment_owner.compaction_guard();window=guard.owner['window']
    environment_owner._guard(guard.owner['plan_sha256'])
    require(clock_image.sha256==compaction.CLOCK_SHA and clock_image.size_bytes==compaction.CLOCK_SIZE,
        'exact frozen clock helper required')
    require(type(deadline_ns) is int and time.monotonic_ns()+CLEANUP_NS<deadline_ns<=window['end_monotonic_ns']
        and deadline_ns-now<=environment.resources.EXTERNAL_TIME['qualification_ns'],'fixed original qualification budget required')
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and len(list(Path('/proc/self/task').iterdir()))==1,'single-threaded owned qualifier required')
    require(ROOT.parent.resolve(strict=True)==ROOT.parent,'canonical qualification parent required')
    _mkdir(ROOT)  # Durable once-only namespace; even a failure is never adopted.
    bindings=[]
    try:
        attempt=_record(ROOT/'attempt.json',dict(plan_sha256=guard.owner['plan_sha256'],window_binding=window,
            started_monotonic_ns=now,deadline_monotonic_ns=deadline_ns,automatic_retries=0,execution_authority=False))
        for pair in ('near','far'):
            result,raw=_capture(owner=environment_owner,image=clock_image,pair=pair,deadline=deadline_ns,window=window)
            bindings.extend((result,raw))
        completion=_record(ROOT/'completion.json',dict(schema_version=SCHEMA,plan_sha256=guard.owner['plan_sha256'],
            window_binding=window,deadline_monotonic_ns=deadline_ns,completed_monotonic_ns=time.monotonic_ns(),
            pair_results=bindings,clock_pairs_qualified=True,full_qualification=False,execution_authority=False))
        owned=_VerifiedClocks(token=_TOKEN,owner=environment_owner,image=clock_image,completion=completion,bindings=[attempt,*bindings])
        owned.proof(plan_sha256=guard.owner['plan_sha256'])
        require(time.monotonic_ns()<deadline_ns,'original qualification deadline expired after durable proof')
        return owned
    except BaseException as error:
        environment_owner._qualification_failed=True
        try:_record(ROOT/'failure.json',dict(error=str(error)[:4096],automatic_retries=0,execution_authority=False))
        except BaseException:pass
        raise
