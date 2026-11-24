"""D288 bounded stand-only86-prefix/94-suffix independent Q16c analysis.

Caller supplies the authenticated private CLI and original prepared retention.
No qualification, collection, source generation, retries or inferred feasibility.
The same raw/custody rules run on every byte; failed scratch remains retained.
"""
from pathlib import Path
from multiprocessing.connection import wait
import dataclasses
import gc
import hashlib
import json
import multiprocessing
import os
import resource
import signal
import time

import stage17_q16c_descriptive_calibration_v2 as composition
import stage17_formal_scheduled_capture_validation_v2 as science
import stage17_q16c_control_reader_v1 as controls
import stage17_q16c_archive_scope_v1 as images
import stage17_q16c_source_prepare_v1 as process_cleanup

WORKERS=12
GIB=1024**3
CHILD_SECONDS=300
TOTAL_NS=3_600_000_000_000
PARENT_SETUP_NS=600_000_000_000
PARENT_CLEANUP_NS=120_000_000_000


def require(ok,message):
    if not ok:raise ValueError('Q16c independent analysis: '+message)


def save(path,document):
    return process_cleanup.save(Path(path),composition.archive.canonical(document))


def physical_cpus(allowed,topology):
    chosen={}
    for cpu in sorted(allowed):chosen.setdefault(tuple(topology[cpu]),cpu)
    require(len(chosen)>=WORKERS,'twelve actual distinct physical cores required')
    return list(chosen.values())[:WORKERS]


def scratch_envelope(canonical_sizes,retained_failed_bytes):
    require(type(canonical_sizes) is list and len(canonical_sizes) in (86,94)
        and all(type(n) is int and n>0 for n in canonical_sizes),'complete actual86 or94 canonical sizes required')
    require(type(retained_failed_bytes) is int and retained_failed_bytes>=0,'actual retained scratch charge required')
    result=sum(sorted(canonical_sizes,reverse=True)[:WORKERS])+retained_failed_bytes+17*GIB
    require(result<=256*GIB,'aggregate old failed and active scratch exceeds256GiB')
    return result


def _child(connection,job,profile,decoder_limits,hardware,cpu,deadline):
    try:
        signal.signal(signal.SIGTERM,signal.SIG_DFL)
        os.sched_setaffinity(0,{cpu});require(os.sched_getaffinity(0)=={cpu},'actual child CPU affinity')
        resource.setrlimit(resource.RLIMIT_AS,(2*GIB,8*GIB))
        resource.setrlimit(resource.RLIMIT_CPU,(CHILD_SECONDS,CHILD_SECONDS))
        def expired(*_):raise TimeoutError('independent capture300s limit')
        signal.signal(signal.SIGALRM,expired)
        signal.alarm(max(1,min(CHILD_SECONDS,(deadline-time.monotonic_ns())//10**9)))
        archive,custody=images.selected_archive_modules(profile,deadline)
        decoder=archive.DecoderProfile(**dataclasses.asdict(profile.decoder))
        limits=archive.DecodeLimits(**dataclasses.asdict(decoder_limits))
        item=job['item'];verified=job['verified'];ordinal=item['capture']['ordinal'];started=time.monotonic_ns()
        packed_capacity=controls.packed_capacity(item['capture'],item['resources'],item['monitoring'])
        artifacts=tuple(custody.SpoolArtifact(row['logical']['file_name'],Path(job['program_root'])/'archives'/row['archive_name'],
            row['header'],archive.RoleProfile(**row['role']),archive.PhysicalBinding(**row['physical'])) for row in verified['artifacts'])
        require(len(artifacts)==8 and artifacts[-1].file_name==f'q16c-c{ordinal}-control.json','exact scheduled artifact set')
        limits=dataclasses.replace(limits,deadline_ns=min(deadline,started+CHILD_SECONDS*10**9))
        gc.collect()
        with custody.capture_spool(Path(job['scratch']),capture_id=f'capture-{ordinal}',canonical_bytes_bound=job['canonical_bytes'],
            deadline_ns=limits.deadline_ns,artifacts=artifacts,profile=decoder,limits=limits) as root:
            resource.setrlimit(resource.RLIMIT_AS,(8*GIB,8*GIB))
            with controls.control(root,verified['artifacts'][-1]['logical'],capture=item['capture'],
                resources=item['resources'],monitoring=item['monitoring']) as document:
                report=science.validate_capture(root,document,verified['native_result_after_cleanup'],
                    item['capture'],item['resources'],item['monitoring'],hardware)
            binding=save(Path(job['reports'])/f'capture-{ordinal}.json',report)
        connection.send(dict(status='VALID',ordinal=ordinal,report=binding,elapsed_ns=time.monotonic_ns()-started,
            maximum_resident_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,canonical_spool_removed=True,
            control_reader=controls.VERSION,packed_page_capacity_bytes=packed_capacity))
    except BaseException as error:
        connection.send(dict(status='FAILED',ordinal=job['item']['capture']['ordinal'],error=type(error).__name__+': '+str(error)[:4096]))
    finally:connection.close()


def collect(jobs,profile,decoder_limits,hardware,cpus,output,deadline,*,kind):
    count=86 if kind=='PREFIX86' else 94 if kind=='SUFFIX94' else 0
    require(count>0 and len(jobs)==count and len(cpus)==WORKERS and len(set(cpus))==WORKERS,'complete bounded analysis pool')
    require({job['item']['capture']['ordinal'] for job in jobs}==set(range(count)),
        'exact selected original capture membership required')
    # Largest first is an engineering scheduling choice, never selection of data.
    pending=sorted(jobs,key=lambda j:(-j['canonical_bytes'],j['item']['capture']['ordinal']))
    active={};results={};processes=[];context=multiprocessing.get_context('fork')
    try:
        while pending or active:
            require(time.monotonic_ns()<deadline,'whole analysis deadline')
            for cpu in cpus:
                if cpu in active or not pending:continue
                job=pending.pop(0);receiver,sender=context.Pipe(duplex=False)
                process=context.Process(target=_child,args=(sender,job,profile,decoder_limits,hardware,cpu,deadline))
                process.start();sender.close();processes.append(process)
                active[cpu]=(process,receiver,time.monotonic_ns(),job['item']['capture']['ordinal'])
            channels={v[1]:k for k,v in active.items()}
            for connection in wait(list(channels),timeout=0.25):
                cpu=channels[connection];process,_,started,ordinal=active[cpu]
                result=connection.recv();process.join(2)
                require(process.exitcode==0 and not process.is_alive(),'actual scientific child completion/reaping failed')
                save(output/f'capture-{ordinal}-process.json',dict(result,leader_reaped=True,exit_code=process.exitcode))
                require(result['status']=='VALID' and result['ordinal']==ordinal,'invalid required capture: '+str(result))
                require(ordinal not in results,'duplicate analysis capture')
                results[ordinal]=result;connection.close();del active[cpu]
                print(json.dumps(dict(completed=len(results),total=count,capture_ordinal=ordinal)),flush=True)
            for process,connection,started,ordinal in active.values():
                require(time.monotonic_ns()-started<(CHILD_SECONDS+2)*10**9,'capture child cleanup deadline')
                require(process.is_alive() or connection.poll(),'analysis child exited without a result')
        require(set(results)==set(range(count)),'required selected analysis reports incomplete')
        return results
    finally:
        process_cleanup._stop(processes)
        for _,connection,_,_ in active.values():connection.close()
        for process in processes:process.close()


def phase_deadline(started,observed,global_deadline_ns):
    require(type(started) is int and 0<started<=observed,'actual original analysis phase start')
    deadline=min(started+TOTAL_NS,global_deadline_ns)
    require(deadline-started>=TOTAL_NS,'complete prospective60-minute analysis envelope does not fit')
    require(observed<deadline,'original analysis deadline expired')
    return deadline


def analyze_verified(plan,verified,profile,decoder,hardware,output,*,kind,plan_binding,global_deadline_ns,
                     retained_failed_scratch_bytes,started_monotonic_ns):
    """Called only with the statically authenticated prefix/suffix retention.

    This helper grants no input admission: its root operator must authenticate
    signed original/new request/authorization, exact plan, terminal recovery,
    quiescent program scope/ledger and every custody row before calling it.
    The entry point binds that operator and these bytes to the actual packet.
    """
    require(kind in ('PREFIX86','SUFFIX94'),'explicit D288 analysis phase')
    from stage17_q16c_execution_window_v3 import read,parse
    import stage17_formal_scheduled_continuation_v1 as continuation
    raw=read(plan_binding)
    require(parse(raw)==plan,'actual bound analysis plan bytes')
    count=86 if kind=='PREFIX86' else 94
    if kind=='PREFIX86':
        require(len(raw)==continuation.PARENT_SIZE and hashlib.sha256(raw).hexdigest()==continuation.PARENT_SHA256,
                'exact original incident plan for prefix validation')
        composition.contract.validate_plan(plan)
        items=plan['captures'][:86]
    else:
        continuation.validate_plan(plan)
        items=plan['captures']
    require(len(verified['captures'])==count and verified['inverse_readback_performed'] is False,
            'all selected custody metadata requires fresh inverse validation')
    require([cap['capture_ordinal'] for cap in verified['captures']]==list(range(count))
        and all(cap['inverse_readback_performed'] is False and cap['scientific_validity']=='NOT_ASSESSED'
                and cap['execution_authority'] is False for cap in verified['captures']),
        'ordered original custody metadata; no previously validated subset')
    scope=verified['scope_bindings']
    require(scope['program_scope_sha256']==plan['storage']['program_scope_sha256'],
            'actual signed shared-program scope')
    program=Path(scope['program_root_binding']['absolute_path'])
    require(program.is_absolute() and program.resolve(strict=True)==program,
            'actual canonical admitted archive-program root')
    if 'program_root' in verified:
        require(verified['program_root']==str(program),'conflicting admitted program roots')
    observed=time.monotonic_ns();deadline=phase_deadline(started_monotonic_ns,observed,global_deadline_ns)
    output=Path(output);require(output.is_absolute() and output.parent.resolve(strict=True)==output.parent
        and not output.exists(),'exclusive analysis root; no retry')
    allowed=os.sched_getaffinity(0)
    topology={cpu:tuple(int((Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')/name).read_text())
        for name in ('physical_package_id','core_id')) for cpu in allowed}
    cpus=physical_cpus(allowed,topology)
    available=[r for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith('MemAvailable:')]
    require(len(available)==1 and int(available[0].split()[1])*1024>=112*GIB,'actual12-worker RAM reserve')
    sizes=[sum(r['logical']['size_bytes'] for r in cap['artifacts']) for cap in verified['captures']]
    scratch=scratch_envelope(sizes,retained_failed_scratch_bytes)
    fs=os.statvfs(output.parent);require(fs.f_bavail*fs.f_frsize>=256*GIB+16*GIB,'actual scratch/reserve')
    require(time.monotonic_ns()<started_monotonic_ns+PARENT_SETUP_NS,'original600s analysis setup expired')
    output.mkdir(mode=0o700);(output/'scratch').mkdir();(output/'reports').mkdir()
    save(output/'analysis-intent.json',dict(kind=kind,started_monotonic_ns=started_monotonic_ns,
        deadline_monotonic_ns=deadline,worker_count=WORKERS,physical_cpus=cpus,scratch_bytes=scratch,
        retained_failed_scratch_bytes=retained_failed_scratch_bytes,per_capture_seconds=CHILD_SECONDS,
        execution_authority=False,phase18_authority=False))
    save(output/'signed-family-metadata.json',verified)
    jobs=[dict(item=item,verified=cap,program_root=str(program),scratch=str(output/'scratch'),
        reports=str(output/'reports'),canonical_bytes=sizes[i])
        for i,(item,cap) in enumerate(zip(items,verified['captures'],strict=True))]
    results=collect(jobs,profile,decoder,hardware,cpus,output,deadline-PARENT_CLEANUP_NS,kind=kind)
    require(time.monotonic_ns()<deadline,'selected analysis finalization deadline')
    return save(output/'complete.json',dict(schema_version='cpu-prefetch-stage17-q16c-selected-analysis-completion/1',
        status='ALL_SELECTED_VALID',kind=kind,plan_binding=plan_binding,
        reports=[results[i]['report'] for i in range(count)],all_workers_reaped=True,
        elapsed_ns=time.monotonic_ns()-started_monotonic_ns,execution_authority=False,phase18_authority=False))
