"""D234 bounded size-ordered parallel execution of the unchanged D213 capture checks.

This is offline analysis only. A complete family passes identical bound-input,
whole-plot, capture, raw-custody and retention-claim checks before the unchanged
selector sees the original prospective order. No partial selection or retry.
"""
from __future__ import annotations
import contextlib
import hashlib
import json
import multiprocessing
import pathlib
import resource
import time
from multiprocessing.connection import wait as wait_connections

import stage17_discovery_validation_v3 as base

contract, registry, selector, codec, environment = base.contract, base.registry, base.selector, base.codec, base.environment
ValidationError=base.ValidationError
require,exact,uint,document,JsonReader,ValidatedStudy,validate_capture=(
    base.require,base.exact,base.uint,base.document,base.JsonReader,base.ValidatedStudy,base.validate_capture)
BASE_SHA256="661613aedbc77fd538970b8c5e79a4bbaa3d2acb7f503cb802725239b25e94bf"
MAX_WORKERS=16
DEFAULT_WORKER_MEMORY_BYTES=8*1024**3


def _worker_limits(memory_bytes):
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    ceiling=memory_bytes if hard==resource.RLIM_INFINITY else min(memory_bytes,hard)
    if soft!=resource.RLIM_INFINITY: ceiling=min(ceiling,soft)
    resource.setrlimit(resource.RLIMIT_AS,(ceiling,ceiling))


def validate_retained_study(*,action_inputs,retention_report,retention_binding,output_root,
                            worker_count=16,worker_memory_bytes=DEFAULT_WORKER_MEMORY_BYTES,
                            analysis_timeout_seconds=86400,progress=None):
    """Caller bounds total resources and original custody; this grants no authority."""
    require(type(worker_count) is int and 1<=worker_count<=MAX_WORKERS,"analysis worker bound")
    require(type(worker_memory_bytes) is int and worker_memory_bytes>0,"analysis memory bound")
    require(type(analysis_timeout_seconds) is int and 1<=analysis_timeout_seconds<=86400,"analysis deadline bound")
    require(hashlib.sha256(pathlib.Path(base.__file__).read_bytes()).hexdigest()==BASE_SHA256,
            "parallel analysis requires exact D213 checker bytes")
    try:
        return _validate_study(action_inputs,retention_report,retention_binding,pathlib.Path(output_root),
                               worker_count,worker_memory_bytes,analysis_timeout_seconds,progress)
    except ValidationError: raise
    except (KeyError,TypeError,ValueError,OverflowError,UnicodeError,OSError,codec.DecodeError) as error:
        raise ValidationError("missing, malformed or unsupported evidence: "+str(error)) from error


def _capture_job(job):
    root, cap, retained, final, r, m, hardware_control = job
    files=retained['artifacts']
    with document(root,files[-1]) as control:
        for i,phase in enumerate(control['phases']):
            for j,name in enumerate(('producer','consumer','demand')):
                short={key:phase[name][key] for key in ('file_name','size_bytes','sha256')}
                exact(short,files[i*3+j],'raw control custody binding')
        result,phases=validate_capture(root,control,final,cap,r,m,hardware_control)
    exact(retained['native_stop'],'trace_capacity' if phases[1].capacity_limited else 'complete','retention stop')
    sufficient=not phases[1].capacity_limited and all(c>=100000 for c in result.counts.values())
    exact(retained['native_validity'],'VALID' if sufficient else 'INSUFFICIENT','retention count claim')
    return cap.ordinal,result,phases

def _capture_group(connection,jobs,memory_bytes):
    try:
        _worker_limits(memory_bytes)
        for job in jobs: connection.send(("capture",_capture_job(job)))
        connection.send(("done",None))
    except BaseException as error:
        connection.send(("error",f"{type(error).__name__}: {str(error)[:4096]}"))
    finally:
        connection.close()


def _parallel_captures(jobs,worker_count,memory_bytes,timeout_seconds,progress):
    context=multiprocessing.get_context("fork")
    processes=[];connections={};finished=set();completed=set()
    captures=[None]*len(jobs);phase_counts=[None]*len(jobs)
    deadline=time.monotonic()+timeout_seconds
    try:
        # Scheduling changes only offline work order. Every unchanged capture
        # check runs, and the original ordinal is restored before selection.
        ordered_jobs=sorted(jobs,key=lambda job:(-job[2]['artifacts'][-1]['size_bytes'],job[1].ordinal))
        for worker in range(min(worker_count,len(jobs))):
            receive,send=context.Pipe(duplex=False)
            process=context.Process(target=_capture_group,args=(send,ordered_jobs[worker::worker_count],memory_bytes))
            try: process.start()
            except BaseException:
                receive.close();send.close();raise
            send.close();processes.append(process);connections[receive]=process
        while connections:
            remaining=deadline-time.monotonic()
            require(remaining>0,"parallel analysis deadline exceeded")
            ready=wait_connections(list(connections),timeout=min(1.0,remaining))
            for connection in ready:
                process=connections[connection]
                try: kind,payload=connection.recv()
                except EOFError as error: raise ValidationError("analysis worker exited without complete receipt") from error
                if kind=="error": raise ValidationError("analysis worker rejected capture: "+payload)
                if kind=="done":
                    finished.add(process.pid);connection.close();del connections[connection]
                    continue
                require(kind=="capture","unknown analysis worker message")
                ordinal,result,phases=payload
                require(type(ordinal) is int and 0<=ordinal<len(jobs) and ordinal not in completed,
                        "duplicate/outside worker result")
                captures[ordinal]=result;phase_counts[ordinal]=phases;completed.add(ordinal)
                if progress is not None: progress(ordinal,len(completed),len(jobs))
            for connection,process in connections.items():
                if process.exitcode is not None and not connection.poll():
                    raise ValidationError("analysis worker exited before complete receipt")
        require(len(completed)==len(jobs) and len(finished)==len(processes),"incomplete parallel family")
        for process in processes:
            process.join(timeout=max(0.0,deadline-time.monotonic()))
            require(process.exitcode==0,"analysis worker did not exit successfully")
        return captures,phase_counts
    finally:
        for connection in connections: connection.close()
        for process in processes:
            if process.is_alive(): process.terminate()
        for process in processes:
            process.join(timeout=5)
            if process.is_alive(): process.kill();process.join(timeout=5)
            require(not process.is_alive(),"analysis worker could not be reaped")
            process.close()


def _validate_study(inputs,report,report_binding,root,worker_count,worker_memory_bytes,analysis_timeout_seconds,progress):
    import io
    from jsonschema import Draft202012Validator
    import stage17_phase_controller_v24 as controller
    plan=contract.validate_plan(inputs['plan'])
    exact(report_binding['file_name'],registry.REPORT_NAME,'retention filename')
    with document(root,report_binding) as actual:exact(actual,report,'admitted retention bytes')
    # The separately hash-bound analysis successor may live outside the
    # qualified root. Schema custody stays with its pinned registry dependency.
    schema=json.loads((pathlib.Path(registry.__file__).resolve().parents[1]/registry.REPORT_SCHEMA).read_text())
    require(not list(Draft202012Validator(schema).iter_errors(report)),'retention report schema')
    exact(report['plan_sha256'],plan.sha256,'retention plan binding')
    exact(report['hardware_state']['file_name'],'studyhardware.json','hardware filename')
    require(report_binding['size_bytes']+report['hardware_state']['size_bytes']<=plan.budget.metadata_output_bytes,
            'study metadata bound')
    bindings=[plan.stand,plan.qualification,plan.resource_plan,plan.monitoring_plan,plan.namespace_registry]
    bindings.extend(dep.resolution for dep in plan.dependencies)
    bound={}
    require(len(inputs['bound_documents'])==len(bindings),'incomplete bound inputs')
    for item in inputs['bound_documents']:
        require(item['artifact_id'] not in bound,'duplicate bound input')
        binding=next((b for b in bindings if b.artifact_id==item['artifact_id']),None)
        require(binding is not None,'unbound input')
        raw=item['utf8_bytes'].encode('utf-8')
        exact(len(raw),binding.size_bytes,'bound input size')
        exact(hashlib.sha256(raw).hexdigest(),binding.sha256,'bound input original SHA256')
        with contextlib.ExitStack() as stack:parsed=JsonReader(io.StringIO(item['utf8_bytes']),stack).document()
        exact(registry.canonical(parsed),registry.canonical(item['document']),'bound parsed document')
        bound[item['artifact_id']]=parsed
    resources=bound[plan.resource_plan.artifact_id];monitoring=bound[plan.monitoring_plan.artifact_id]
    try:
        controller._native_inputs(plan,resources,monitoring,inputs['native_captures'])
    except controller.ControllerError as error:
        raise ValidationError('bound native inputs: '+str(error)) from error
    all_bindings=[report_binding,report['hardware_state']]
    jobs=[]
    with document(root,report['hardware_state']) as hardware:
        exact(hardware['schema_version'],'cpu-prefetch-stage17-discovery-hardware/1','hardware schema')
        exact(hardware['plan_sha256'],plan.sha256,'hardware plan binding')
        exact(hardware['mapping_id'],inputs['hardware_control']['mapping_id'],'study hardware mapping')
        exact(hardware['restoration_verified'],True,'study restoration')
        exact(hardware['mandatory_failure'],False,'study mandatory failure')
        exact(hardware['phase18_authority'],False,'no phase18 authority')
        require(len(hardware['native_results_after_cleanup'])==36,'36 final cleanup results required')
        prestate=inputs['hardware_control']['prestate']
        require(len(hardware['whole_plots'])==2,'exact two hardware whole plots')
        for state,plot in zip(('H0','H1'),hardware['whole_plots'],strict=True):
            exact(plot['state'],state,'whole plot state');exact(plot['restoration_verified'],True,'whole plot restoration')
            # D213: these are write-action readbacks, not the independent
            # per-capture observations. H0 verifies but never writes; H1
            # applies in prestate order and restores in reverse write order.
            expected_restore=list(reversed(prestate)) if state=='H1' else []
            expected_apply=[dict(cpu=v['cpu'],complete_value_hex=f"{int(v['complete_value_hex'],16)|15:016x}") for v in prestate] if state=='H1' else []
            exact(plot['restore_readback'],expected_restore,'whole plot restore prestate')
            exact(plot['apply_readback'],expected_apply,'whole plot applied state')
        for cap,retained,final,r,m in zip(plan.captures,report['captures'],hardware['native_results_after_cleanup'],
                                         resources['captures'],monitoring['captures'],strict=True):
            exact(retained['ordinal'],cap.ordinal,'retained ordinal')
            exact(retained['warmup_run_id'],cap.warmup.run_id,'retained warmup identity')
            exact(retained['measurement_run_id'],cap.measurement.run_id,'retained measurement identity')
            files=retained['artifacts'];exact([b['file_name'] for b in files],list(registry.capture_names(cap.ordinal)),'retained seven artifacts')
            require(sum(uint(b['size_bytes'],'artifact size') for b in files)<=cap.budget.max_output_bytes,'capture output bound')
            require(sum(b['size_bytes'] for b in files[:6])<=cap.budget.retained_output_bytes,'capture retained raw bound')
            require(files[-1]['size_bytes']<=cap.budget.metadata_output_bytes,'capture metadata bound')
            all_bindings.extend(files)
            jobs.append((root,cap,retained,final,r,m,inputs['hardware_control']))
    require(sum(b['size_bytes'] for b in all_bindings)<=plan.maximum_output_bytes,'study output bound')
    captures,phase_counts=_parallel_captures(jobs,worker_count,worker_memory_bytes,analysis_timeout_seconds,progress)
    return ValidatedStudy(plan.sha256,hashlib.sha256(registry.canonical(all_bindings)).hexdigest(),
        tuple(captures),tuple(phase_counts),selector.select_duration(captures))
