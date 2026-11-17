"""D273 bounded stand-only independent180-capture Q16c analysis.

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
TOTAL_NS=5_400_000_000_000
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
    require(type(canonical_sizes) is list and len(canonical_sizes)==180
        and all(type(n) is int and n>0 for n in canonical_sizes),'complete actual180 canonical sizes required')
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


def collect(jobs,profile,decoder_limits,hardware,cpus,output,deadline):
    require(len(jobs)==180 and len(cpus)==WORKERS and len(set(cpus))==WORKERS,'complete bounded analysis pool')
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
                print(json.dumps(dict(completed=len(results),total=180,capture_ordinal=ordinal)),flush=True)
            for process,connection,started,ordinal in active.values():
                require(time.monotonic_ns()-started<(CHILD_SECONDS+2)*10**9,'capture child cleanup deadline')
                require(process.is_alive() or connection.poll(),'analysis child exited without a result')
        require(set(results)==set(range(180)),'required180 analysis reports incomplete')
        return results
    finally:
        process_cleanup._stop(processes)
        for _,connection,_,_ in active.values():connection.close()
        for process in processes:process.close()


def analyze(cli,prepared,output,*,global_deadline_ns,retained_failed_scratch_bytes):
    started=time.monotonic_ns();deadline=min(started+TOTAL_NS,global_deadline_ns)
    require(deadline-started>=TOTAL_NS,'complete prospective90-minute analysis envelope does not fit')
    output=Path(output);require(output.is_absolute() and output.parent.resolve(strict=True)==output.parent
        and not output.exists(),'exclusive canonical analysis root required')
    plan=prepared.request['action_inputs']['plan']
    require(plan['schema_version']==composition.contract.VERSION and len(plan['captures'])==180,'actual descriptive Q16c family required')
    phase=Path(prepared.request['evidence_root_binding']['absolute_path'])
    verified=cli.admit_formal_retention(prepared,phase)
    require(verified['inverse_readback_performed'] is False and len(verified['captures'])==180,'all180 need independent actual decode')
    allowed=os.sched_getaffinity(0)
    topology={cpu:tuple(int((Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')/name).read_text())
        for name in ('physical_package_id','core_id')) for cpu in allowed}
    cpus=physical_cpus(allowed,topology)
    available=[r for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith('MemAvailable:')]
    require(len(available)==1 and int(available[0].split()[1])*1024>=112*GIB,'actual memory cannot support12 bounded workers')
    sizes=[sum(r['logical']['size_bytes'] for r in cap['artifacts']) for cap in verified['captures']]
    scratch=scratch_envelope(sizes,retained_failed_scratch_bytes)
    fs=os.statvfs(output.parent);require(fs.f_bavail*fs.f_frsize>=256*GIB+16*GIB,'actual scratch/reserve capacity unavailable')
    require(time.monotonic_ns()<started+PARENT_SETUP_NS,'analysis setup exceeded prospective600s')
    output.mkdir(mode=0o700);(output/'scratch').mkdir();(output/'reports').mkdir()
    save(output/'analysis-intent.json',dict(started_monotonic_ns=started,deadline_monotonic_ns=deadline,worker_count=WORKERS,
        physical_cpus=cpus,scratch_bytes=scratch,retained_failed_scratch_bytes=retained_failed_scratch_bytes,
        per_capture_seconds=CHILD_SECONDS,execution_authority=False,phase18_authority=False))
    save(output/'signed-family-metadata.json',verified)
    extent=cli.controller.contract.validate_plan('Q16c',plan)
    decoder=cli.registry._metadata_decode_limits(plan,extent,prepared.archive_runtime_profile,deadline)
    jobs=[dict(item=item,verified=cap,program_root=str(phase.parent.parent),scratch=str(output/'scratch'),reports=str(output/'reports'),
        canonical_bytes=sizes[i]) for i,(item,cap) in enumerate(zip(plan['captures'],verified['captures'],strict=True))]
    results=collect(jobs,prepared.archive_runtime_profile,decoder,prepared.request['action_inputs']['hardware_control'],cpus,output,
                    deadline-PARENT_CLEANUP_NS)
    records=[]
    for i in range(180):
        b=results[i]['report'];raw=composition.admission.BoundReader().read(b)
        records.append(dict(capture_ordinal=i,validity='VALID',report_utf8_bytes=raw,
            report_binding=dict(artifact_id=f'Q16C-D270-REPORT-{i:04d}',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
    result=composition.evaluate(plan,records);require(result['status']=='DESCRIPTIVE_COMPLETE','required coverage is incomplete')
    again=cli.admit_formal_retention(prepared,phase)
    require(composition.archive.canonical(again)==composition.archive.canonical(verified),'original signed custody metadata changed during analysis')
    require(time.monotonic_ns()<deadline,'analysis finalization deadline')
    composed=save(output/'calibration-validation.json',result)
    return save(output/'complete.json',dict(schema_version='cpu-prefetch-stage17-q16c-independent-analysis-completion/1',
        status='ALL_180_VALID_DESCRIPTIVE_COMPLETE',composition=composed,reports=[results[i]['report'] for i in range(180)],
        all_workers_reaped=True,elapsed_ns=time.monotonic_ns()-started,execution_authority=False,phase18_authority=False))
