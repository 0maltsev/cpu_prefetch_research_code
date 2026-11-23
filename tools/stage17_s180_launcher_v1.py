"""Owned S180 dispatch/IPC/cleanup for the qualified stand operator.

No input-selected backend, command, verifier or automatic retry. The operator
must supply the actual scoped journal, owned source bank, qualified runtime
profile and a pinned-code environment restorer. This callable does not create
those prerequisites or perform independent scientific validation.
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict,dataclass,replace
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
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_process_group_supervisor_v3 as supervisor
from stage17_formal_checkpoint_v1 import PinnedWorker
import stage17_s180_authority_v1 as authority
import stage17_s180_journal_v1 as journals
import stage17_s180_parent_v1 as parent
import stage17_s180_verified_sources_v1 as sources
import stage17_s180_plan_prepare_v1 as planning
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_archive_channel_v1 as channels


class LaunchError(archive.ArchiveError):
    pass


def require(value,message):
    if not value:raise LaunchError('S180 launcher: '+message)


@dataclass(frozen=True)
class LaunchLimits:
    native_address_space_bytes:int
    native_memlock_bytes:int
    native_file_bytes:int
    native_open_files:int
    max_console_bytes:int
    cleanup_reserve_ns:int
    post_native_reserve_ns:int

    def validate(self):
        for k,v in vars(self).items():archive.uint(v,k,positive=True)
        require(self.max_console_bytes<=16384,'console exceeds bounded terminal-record allowance')
        require(64<=self.native_open_files<=1024,'explicit native FD ceiling outside supported range')
        minimum=supervisor.predecessor.TERM_GRACE_NS+supervisor.predecessor.KILL_GRACE_NS
        require(self.cleanup_reserve_ns>=minimum,'native cleanup reserve is insufficient')


def _family_ns(plan):
    b=plan['budget']
    return archive.checked_sum(*(b[k] for k in ('setup_ns','whole_plot_transition_ns',
        'whole_plot_recovery_ns','finalization_ns')),
        *(e['execution_budget']['watchdog_ns'] for e in plan['captures']))


def _check_membership(raw,relative_path):
    # The unified cpuset hierarchy may coexist with an unrelated legacy
    # hierarchy (for example net_cls). Require exactly one exact v2 entry.
    require(len(raw)<=4096 and [line for line in raw.splitlines() if line.startswith('0::')]==['0::'+relative_path],
        'native cgroup placement readback differs')


def _context(verified,source_context,child_socket,directory_fd):
    authorization,request=parent._documents(verified)
    parent._root(directory_fd,authorization)
    root=os.fstat(directory_fd);window=authorization['window_binding']
    return dict(schema_version='cpu-prefetch-stage17-s180-session-context/1',
        **{k:request[k] for k in ('session_id','request_id','attempt_id','authorization_id')},
        authorization_sha256=verified.authorization_sha256,request_sha256=verified.request_sha256,
        plan_sha256=authorization['plan_sha256'],runtime_sha256=request['runtime_binding']['sha256'],
        release_sha256=request['release_binding']['worker_sha256'],
        prerequisite_bindings=request['prerequisite_bindings'],readiness_scope='D310-S180-SCOPED-READY-v1',
        issued_at_epoch_seconds=authorization['issued_at_epoch_seconds'],
        expires_at_epoch_seconds=authorization['expires_at_epoch_seconds'],
        window_start_monotonic_ns=window['start_monotonic_ns'],window_end_monotonic_ns=window['end_monotonic_ns'],
        schedule_source_context=source_context,
        archive_channel=dict(descriptor=child_socket.fileno(),controller_pid=os.getpid(),
            program_scope_sha256=request['plan']['storage']['program_scope_sha256']),
        output_directory=dict(device=root.st_dev,inode=root.st_ino),boot_id=window['boot_id'],
        synthetic_test_only=False,phase18_authority=False)


def _native_result(directory_fd,verified,acknowledged,maximum):
    """Original terminal state is necessary; never a substitute for all ACKs."""
    from stage17_output_registry_v11 import _bound_report
    fd=os.open('s180-session-result.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory_fd)
    try:
        before=archive.file_stamp(os.fstat(fd));require(0<before[2]<=maximum,'native result byte bound')
        digest=hashlib.sha256();offset=0
        while offset<before[2]:
            block=os.pread(fd,min(65536,before[2]-offset),offset)
            require(bool(block),'native result truncated');digest.update(block);offset+=len(block)
        require(archive.file_stamp(os.fstat(fd))==before,'native result changed while hashing')
    finally:os.close(fd)
    binding=dict(file_name='s180-session-result.json',size_bytes=before[2],sha256=digest.hexdigest())
    result=_bound_report(directory_fd,binding,maximum)
    authorization,request=parent._documents(verified)
    require(result['schema_version']=='cpu-prefetch-stage17-s180-session-result/1'
        and result['session_id']==request['session_id'] and result['plan_sha256']==authorization['plan_sha256']
        and result['blueprint_sha256']==planning.BLUEPRINT_SHA256
        and result['method_id']=='STAGE17-PILOT-S180-DESCRIPTIVE-v1'
        and result['execution_authority'] is False and result['phase18_authority'] is False,
        'original native result scope differs')
    require(type(acknowledged) is int and acknowledged==180
        and type(result['attempted']) is int and result['attempted']==180
        and type(result['completed']) is int and result['completed']==180
        and type(result['stop']) is int and result['stop']==1,
        'native completion does not match all180 actual custody acknowledgements')
    require(all(result[k] is True for k in ('restoration_attempted','restoration_verified','cleanup_verified')),
        'native final restoration/cleanup failed')
    contexts=result['contexts_after_family_release']
    require(type(contexts) is list and len(contexts)==6,'all six final shared contexts required')
    for context in contexts:
        require(set(context)=={'records','queues'},'final shared mapping fields differ')
        for mapping in context.values():
            require(type(mapping) is dict and mapping.get('cleanup_attempted') is True
                and all(archive.canonical(mapping.get(k))==archive.canonical(dict(return_value=0,error_number=0)) for k in ('unlock','unmap')),
                'shared context cleanup is incomplete')
    plots=result['whole_plots'];expected=request['plan']['hardware']['prestate']
    require(type(plots) is list and len(plots)==2,'two original whole plots required')
    order=[r['requested_hardware_state'] for r in sorted(request['plan']['blueprint']['captures'],key=lambda r:r['execution_ordinal'])]
    for plot,state in zip(plots,(order[0],order[90]),strict=True):
        require(plot['requested_state']==state and plot['restoration_verified'] is True,'whole-plot restoration differs')
        observed=plot['independent_restore_observations']
        require(type(observed) is list and len(observed)==len(expected),'all restoration CPU observations required')
        require(archive.canonical(sorted(observed,key=lambda r:r['cpu']))==archive.canonical([dict(cpu=r['cpu'],requested_prestate=r['value'],
            observed_value=r['value'],read_succeeded=True) for r in sorted(expected,key=lambda r:r['cpu'])]),
            'native independent MSR restoration differs')
    return binding


def _restore_result(restorer,*,verified,cleanup,deadline_ns):
    """Pinned operator code must independently restore/read back actual state.

    A required callable is supplied by qualified code, never from configuration.
    Its result is evidence only and cannot authorize another capture or retry.
    """
    require(callable(restorer),'qualified environment restoration is mandatory')
    result=restorer(verified=verified,native_cleanup=cleanup,deadline_ns=deadline_ns)
    from stage17_s180_environment_v1 import _PreparedEnvironment
    real=type(restorer) is _PreparedEnvironment
    fields={'schema_version','plan_sha256','boot_id',
        'hardware_restoration_verified','cpu_isolation_restoration_verified','maintenance_restoration_verified','errors'}
    if real:fields.add('compaction_restoration_verified')
    require(type(result) is dict and set(result)==fields,
        'environment restoration evidence fields differ')
    authorization=archive.parse_json(verified.authorization_bytes)
    require(result['schema_version']=='cpu-prefetch-stage17-s180-environment-restoration/'+('2' if real else '1')
        and (not real or result['compaction_restoration_verified'] is True)
        and result['plan_sha256']==authorization['plan_sha256']
        and result['boot_id']==authorization['window_binding']['boot_id']
        and result['errors']==[] and all(result[k] is True for k in ('hardware_restoration_verified',
            'cpu_isolation_restoration_verified','maintenance_restoration_verified')),
        'independent environment restoration failed')
    require(time.monotonic_ns()<deadline_ns,'environment restoration exceeded original window')
    return result


def _execute_verified(*,verified,source_owner,native_image,archive_profile,program_root,
                      broker_limits,custody_limits,decoder_limits,limits,restore_environment,native_partition=None,platform_guard=None):
    """Private transport seam. Production calls only through launch()."""
    limits.validate();require(callable(restore_environment),'qualified environment restoration is mandatory')
    require(threading.current_thread() is threading.main_thread() and threading.active_count()==1
        and len(list(Path('/proc/self/task').iterdir()))==1,
        'owned launch requires a single-threaded main process')
    authorization,request=parent._documents(verified);plan=request['plan'];window=authorization['window_binding']
    family=authorization['plan_sha256'];family_ns=_family_ns(plan)
    require(time.monotonic_ns()+family_ns+limits.post_native_reserve_ns<window['end_monotonic_ns'],
        'native family plus downstream/restoration reserve exceeds original window')
    require(native_image.sha256==request['runtime_binding']['sha256']
        and native_image.size_bytes==request['runtime_binding']['size_bytes'],'admitted image differs')
    require(type(source_owner) is sources._VerifiedSources,'actual process-owned verified source bank required')
    proof=source_owner.proof(plan_sha256=family)
    require(proof['source_count']==36 and proof['valid_until_monotonic_ns']>=window['end_monotonic_ns'],
        'source ownership must cover the original window')
    process=None;worker=None;component=None;cleanup=None;failure=None;restore=None;final=None;attempt=None;restore_failure=None
    console=bytearray();lease=supervisor.SupervisorLease();selector=selectors.DefaultSelector()
    previous={};consumed=False;native_deadline=0;driver=None;stop_ack_sent=False
    def interrupted(number,frame):
        raise LaunchError('interrupted by signal '+str(number))
    with contextlib.ExitStack() as stack:
        executable=runtime._pin_image(native_image,min(window['end_monotonic_ns'],time.monotonic_ns()+60*10**9),stack)
        endpoint,child=channels.create_channel();stack.callback(endpoint.close);stack.callback(child.close)
        directory=os.open(authorization['evidence_root_binding']['absolute_path'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        stack.callback(os.close,directory);parent._root(directory,authorization)
        request_fd=runtime._sealed_input(verified.request_bytes,'s180-owned-request');stack.callback(os.close,request_fd)
        try:
            lease.enter()
            for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
                previous[number]=signal.signal(number,interrupted)
            storage=plan['storage']
            with stores.ProgramStore(Path(program_root),scope_sha256=storage['program_scope_sha256'],family_id=family,
                    ext009_resolution_sha256=request['prerequisite_bindings']['ext009_resolution_sha256'],limits=custody_limits) as store:
                require(store.working==Path(authorization['evidence_root_binding']['absolute_path']),
                    'original programme/output mismatch')
                # Original source checks and loading deadline are adjacent to
                # dispatch, after potentially lengthy locked custody replay.
                loading_deadline=min(window['end_monotonic_ns'],time.monotonic_ns()+plan['budget']['setup_ns'])
                source_context,source_fds=source_owner.native_inputs(plan_sha256=family,loading_deadline_ns=loading_deadline)
                context=_context(verified,source_context,child,directory)
                context_raw=archive.canonical(context);require(len(context_raw)<=1024**2,'native context exceeds1MiB')
                context_fd=runtime._sealed_input(context_raw,'s180-owned-context');stack.callback(os.close,context_fd)
                inherited=(executable,request_fd,context_fd,directory,child.fileno(),*source_fds)
                if native_partition is not None:inherited=(*inherited,native_partition['descriptor'])
                require(len(set(inherited))==len(inherited) and max(inherited)<limits.native_open_files,
                    'inherited native descriptors alias or exceed configured ceiling')
                marker=store.root/'metadata'/parent._attempt_name(family)
                if marker.exists() or marker.is_symlink():raise FileExistsError('S180 attempt already consumed')
                try:attempt=parent.consume_attempt(verified=verified,store=store)
                finally:consumed=marker.exists() or marker.is_symlink()
            parent._documents(verified)
            require(time.monotonic_ns()<loading_deadline,'source loading deadline expired before spawn')
            native_deadline=time.monotonic_ns()+family_ns
            require(native_deadline+limits.post_native_reserve_ns<window['end_monotonic_ns'],
                'admission consumed the downstream/restoration reserve')
            def constrain():
                resource.setrlimit(resource.RLIMIT_AS,(limits.native_address_space_bytes,)*2)
                resource.setrlimit(resource.RLIMIT_MEMLOCK,(limits.native_memlock_bytes,)*2)
                resource.setrlimit(resource.RLIMIT_FSIZE,(limits.native_file_bytes,)*2)
                resource.setrlimit(resource.RLIMIT_NOFILE,(limits.native_open_files,)*2)
                resource.setrlimit(resource.RLIMIT_CORE,(0,0))
                if native_partition is not None:
                    fd=native_partition['descriptor'];raw=str(os.getpid()).encode('ascii')
                    require(os.write(fd,raw)==len(raw),'native cgroup placement write failed')
                    os.close(fd)
                    with open('/proc/self/cgroup','r',encoding='ascii') as stream:membership=stream.read(4097)
                    _check_membership(membership,native_partition['relative_path'])
                    os.sched_setaffinity(0,{native_partition['controller_cpu']})
                    require(os.sched_getaffinity(0)=={native_partition['controller_cpu']},'native initial affinity readback differs')
                require(resource.getrlimit(resource.RLIMIT_AS)==(limits.native_address_space_bytes,)*2
                    and resource.getrlimit(resource.RLIMIT_MEMLOCK)==(limits.native_memlock_bytes,)*2
                    and resource.getrlimit(resource.RLIMIT_NOFILE)==(limits.native_open_files,)*2
                    and resource.getrlimit(resource.RLIMIT_FSIZE)==(limits.native_file_bytes,)*2
                    and resource.getrlimit(resource.RLIMIT_CORE)==(0,0),'native rlimit readback failed')
            argv=[f'/proc/self/fd/{executable}','--execute-stage17-s180-session-v1','--request-fd',str(request_fd),
                '--context-fd',str(context_fd),'--output-dir-fd',str(directory),'--fixed-dispatch-end']
            process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                shell=False,close_fds=True,pass_fds=inherited,start_new_session=True,preexec_fn=constrain,
                env={'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C','TZ':'UTC'})
            child.close();worker=PinnedWorker(process.pid)
            if platform_guard is not None:platform_guard.register_worker(worker,role='pilot')
            driver=channels.ArchiveChannel(endpoint,worker=worker,directory_fd=directory,
                request_sha256=verified.request_sha256,program_scope_sha256=storage['program_scope_sha256'],captures=180,
                maximum_checkpoint_bytes=custody_limits.max_checkpoint_bytes,
                maximum_custody_receipt_bytes=storage['maximum_custody_receipt_bytes'],
                maximum_archive_ns=max(e['execution_budget']['archive_ns'] for e in plan['captures']),
                session_id=request['session_id'],plan_sha256=family)
            component=parent.CheckpointParent(verified=verified,channel=driver,program_root=program_root,
                profile=archive_profile,limits=replace(broker_limits,deadline_ns=min(native_deadline,broker_limits.deadline_ns)),
                custody_limits=custody_limits,decoder_limits=decoder_limits,identity_model=lease.identity_model,
                platform_guard=platform_guard)
            selector.register(endpoint,selectors.EVENT_READ,'channel');selector.register(worker.descriptor,selectors.EVENT_READ,'exit')
            for stream in (process.stdout,process.stderr):
                os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,'console')
            exited=False
            while not exited:
                authority._sample_window(authorization)
                require(time.monotonic_ns()<native_deadline,'native family watchdog expired')
                ready=selector.select(min(0.1,max(0,(native_deadline-time.monotonic_ns())/10**9)))
                # A final ACK may race normal exit. Drain console first; a
                # finished family never treats channel EOF as a new checkpoint.
                for key,_ in sorted(ready,key=lambda pair:0 if pair[0].data=='console' else 1):
                    if key.data=='console':
                        block=os.read(key.fd,min(65536,limits.max_console_bytes-len(console)+1))
                        if not block:selector.unregister(key.fileobj)
                        else:
                            console.extend(block);require(len(console)<=limits.max_console_bytes,'native console limit exceeded')
                    elif key.data=='exit':exited=True
                    elif driver.ordinal<180:
                        outcome=component.checkpoint(deadline_ns=native_deadline)
                        stop_ack_sent=not outcome['continuation_allowed']
                        require(outcome['continuation_allowed'],'native capture failed; evidence retained and stop ACK sent')
                    else:selector.unregister(endpoint)
        except BaseException as exc:failure=exc
        finally:
            def cleanup_interrupted(number,frame):
                nonlocal failure
                failure=failure or LaunchError('signal received during mandatory cleanup '+str(number))
            for number in previous:signal.signal(number,cleanup_interrupted)
            if driver is not None and failure is not None:driver.stopped=True
            selector.close()
            if process is not None:
                try:
                    grace=plan['budget']['finalization_ns'] if stop_ack_sent else limits.cleanup_reserve_ns
                    cleanup=supervisor.cleanup_process_group(process,force_stop=failure is not None and not stop_ack_sent,
                        leader_wait_deadline_ns=min(native_deadline,time.monotonic_ns()+grace),
                        global_deadline_ns=window['end_monotonic_ns'],identity_model=lease.identity_model)
                    require(cleanup.leader_reaped and cleanup.process_group_gone,'native process cleanup is incomplete')
                    if cleanup.returncode!=0 or cleanup.descendants_detected_after_leader_exit or cleanup.cleanup_deadline_overrun or cleanup.leader_wait_timed_out:
                        failure=failure or LaunchError('native exited unsuccessfully or required abnormal cleanup')
                except BaseException as exc:failure=failure or exc
                for stream in (process.stdout,process.stderr):
                    if stream:
                        try:
                            while True:
                                block=os.read(stream.fileno(),min(65536,limits.max_console_bytes-len(console)+1))
                                if not block:break
                                console.extend(block)
                                require(len(console)<=limits.max_console_bytes,'native console limit exceeded at exit')
                        except BaseException as exc:failure=failure or exc
                        finally:stream.close()
            if worker is not None:worker.close()
            if consumed:
                try:
                    require(process is None or (cleanup is not None and cleanup.leader_reaped and cleanup.process_group_gone),
                        'cannot restore environment before native quiescence')
                    restore=_restore_result(restore_environment,verified=verified,cleanup=cleanup,deadline_ns=window['end_monotonic_ns'])
                    lease.identity_model.verify_stable()
                    require(not lease.identity_model.direct_children(),'environment restorer left owned children')
                except BaseException as exc:
                    restore_failure=str(exc)[:4096];failure=failure or exc
            for number,handler in previous.items():signal.signal(number,handler)
            try:lease.close()
            except BaseException as exc:failure=failure or exc
        if consumed:
            try:
                if failure is None:
                    require(driver is not None and not driver.stopped,'native custody stream stopped')
                    final=_native_result(directory,verified,driver.ordinal,plan['budget']['final_metadata_bytes'])
            except BaseException as exc:failure=exc
            document=dict(schema_version='cpu-prefetch-stage17-s180-launch-terminal/1',
                request_sha256=verified.request_sha256,plan_sha256=family,attempt=None if attempt is None else asdict(attempt),
                attempt_file_name=parent._attempt_name(family),requested_native_limits=asdict(limits),
                native_child_rlimits_verified=process is not None,
                native_spawned=process is not None,native_cleanup=None if cleanup is None else runtime._jsonable(asdict(cleanup)),
                native_pid=None if process is None else process.pid,
                native_start_ticks=None if worker is None else worker.start_ticks,
                native_partition_placement_verified=process is not None and native_partition is not None,
                acknowledged_captures=0 if driver is None else driver.ordinal,native_result=final,environment_restoration=restore,
                environment_restoration_failure=restore_failure,
                quarantined=restore is None or restore_failure is not None or attempt is None
                    or (cleanup is not None and (cleanup.descendants_detected_after_leader_exit
                        or cleanup.cleanup_deadline_overrun or cleanup.leader_wait_timed_out)),
                status='NATIVE_COLLECTED_PENDING_SCIENTIFIC_VALIDATION' if failure is None else 'STOPPED',
                failure=None if failure is None else str(failure)[:4096],console_hex=bytes(console).hex(),
                automatic_retries=0,scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
            with stores.ProgramStore(Path(program_root),scope_sha256=plan['storage']['program_scope_sha256'],family_id=family,
                    ext009_resolution_sha256=request['prerequisite_bindings']['ext009_resolution_sha256'],
                    limits=replace(custody_limits,deadline_ns=window['end_monotonic_ns'])) as store:
                terminal=store.retain_metadata(f's180-launch-terminal-{family}.json',parent._record_bytes(document))
            return dict(document=document,terminal=asdict(terminal))
        if failure is not None:raise failure
        raise LaunchError('dispatch ended without consuming an attempt')


def _check_identity(identity,request):
    require(all(identity[k]==request['runtime_binding'][k] for k in ('role','profile','sha256','size_bytes'))
        and identity['source_revision']==request['plan']['source_revision']
        and identity['source_dirty'] is False and identity['synthetic_test_only'] is False
        and identity['execution_authority'] is False and identity['phase18_authority'] is False,
        'exact clean production native identity required')


def launch(*,journal,authorization_bytes,signature_path,source_owner,native_image,archive_profile,
           program_root,broker_limits,custody_limits,decoder_limits,limits,restore_environment):
    """Production-only launch from current independently replayed scoped inputs.

    The operator's source/profile/qualification/resource semantics and restorer
    must be qualified, pinned code. No dictionary success report is accepted as
    a journal or source bank, and there is no synthetic/command/plugin switch.
    """
    require(type(journal) is journals.ScopedJournal and journal.mode is False,'actual production scoped journal required')
    from stage17_s180_environment_v1 import _PreparedEnvironment
    require(type(restore_environment) is _PreparedEnvironment,'actual owned stand environment required')
    with restore_environment:
        restore_environment.compaction_guard().check(boundary='FAMILY_ENTRY')
        return _launch_in_environment(journal=journal,authorization_bytes=authorization_bytes,signature_path=signature_path,
            source_owner=source_owner,native_image=native_image,archive_profile=archive_profile,program_root=program_root,
            broker_limits=broker_limits,custody_limits=custody_limits,decoder_limits=decoder_limits,
            limits=limits,restore_environment=restore_environment)


def _launch_in_environment(*,journal,authorization_bytes,signature_path,source_owner,native_image,archive_profile,
                           program_root,broker_limits,custody_limits,decoder_limits,limits,restore_environment):
    view=journal.inspect(for_execution=True)
    require(view.scoped_inputs_complete and not view.synthetic_test_only,'complete production scoped inputs required')
    verified=authority.verify_admitted_authorization(authorization_bytes=authorization_bytes,
        signature_path=Path(signature_path),plan=journal.plan,validation=view)
    authorization,request=parent._documents(verified);limits.validate()
    require(limits.native_address_space_bytes==request['plan']['budget']['memory_bytes']
        and limits.native_memlock_bytes==request['plan']['budget']['memory_bytes']
        and limits.native_file_bytes==request['plan']['budget']['max_output_bytes'],
        'native limits differ from admitted complete plan')
    with contextlib.ExitStack() as stack:
        executable=runtime._pin_image(native_image,min(authorization['window_binding']['end_monotonic_ns'],time.monotonic_ns()+30*10**9),stack)
        result=subprocess.run([f'/proc/self/fd/{executable}','--stage17-s180-runtime-identity-v1'],
            pass_fds=(executable,),stdin=subprocess.DEVNULL,capture_output=True,timeout=30,check=True,
            env={'PATH':'/usr/bin:/bin','LC_ALL':'C','TZ':'UTC'})
        require(len(result.stdout)<=8192 and len(result.stderr)<=8192,'native identity output bound')
        import json
        identity=json.loads(result.stdout)
        _check_identity(identity,request)
    # Actual scoped semantics holds one replayed programme lock across short
    # admission. Release it once, only after the exact signed launch request and
    # actual native identity pass. The original launcher then takes its own lock
    # and replays custody before consuming the durable attempt.
    from stage17_s180_plan_admission_v1 import ScopedSemantics
    if type(journal.semantic_replay) is ScopedSemantics:
        journal.semantic_replay.release_for_launch(view=view,verified=verified)
    with restore_environment.native_entry(plan_sha256=authorization['plan_sha256']) as partition:
        return _execute_verified(verified=verified,source_owner=source_owner,native_image=native_image,
            archive_profile=archive_profile,program_root=program_root,broker_limits=broker_limits,
            custody_limits=custody_limits,decoder_limits=decoder_limits,limits=limits,
            restore_environment=restore_environment,native_partition=partition,
            platform_guard=restore_environment.compaction_guard())
