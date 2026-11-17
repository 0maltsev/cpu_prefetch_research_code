"""Arithmetic only: frozen publisher JSON-size upper bounds, no capture.

Symbolic arrays never allocate their represented elements. Numeric maxima are
type-width bounds, not observed values. Optional scalar enums use null (4 bytes)
which dominates their uint8 representation. Full object branches dominate null.
Input geometry/buffers are exactly the nine-row preview repeated four times.
Valid native plan/prestate admission implies no hardware resolver errors; the
single native CPUID failure is conservatively included alongside a full value.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import hashlib
import os

ROOT=Path(__file__).resolve().parents[2]
PREVIEW=Path(__file__).with_name('discovery-resource-preview.json')
U=(1<<64)-1
E=255
F=False
MAPPING='INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1'

@dataclass(frozen=True)
class Repeat:
    value: object
    count: int

def encoded(value):
    return json.dumps(value,ensure_ascii=True,separators=(',',':')).encode()

def size(value):
    if isinstance(value,Repeat):
        return 2+value.count*size(value.value)+max(0,value.count-1)
    if isinstance(value,list):return 2+sum(map(size,value))+max(0,len(value)-1)
    if isinstance(value,dict):return 2+sum(len(encoded(k))+1+size(v) for k,v in value.items())+max(0,len(value)-1)
    return len(encoded(value))

def structure(value):
    """Object members and array element Values, excluding allocator overhead."""
    if isinstance(value,Repeat):
        m,a=structure(value.value);return m*value.count,(a+1)*value.count
    if isinstance(value,list):
        children=[structure(v) for v in value];return sum(v[0] for v in children),len(value)+sum(v[1] for v in children)
    if isinstance(value,dict):
        children=[structure(v) for v in value.values()];return len(value)+sum(v[0] for v in children),sum(v[1] for v in children)
    return 0,0

def nums(keys):return dict.fromkeys(keys.split(),U)
CALL=nums('return_value error_number')  # signed64 negatives also <=20 chars
PAIR=nums('absolute_nanoseconds relative_picoseconds')
CLOCK=dict(status=E,**PAIR)
CAPTURE=dict(outcome=E,before_status=None,after_status=None,operation_outcome=None,operation_performed=F,failed_clock_status=None)
PRIMARY_C=dict(consumed_ordinal=U,observed_record_index=U,**dict.fromkeys(('dequeue_invocation','dequeue_linearization','dequeue_completion','consumer_action_completion'),PAIR))
CONSUMER=dict(capture=CAPTURE,failed_boundary=None,candidate_consumed_ordinal=U,
    **dict.fromkeys(('dequeue_invocation','demand_before','demand_after','dequeue_observation','dequeue_completion','action_completion'),CLOCK),
    operation=dict(status=E,event_address=U),access=dict(status=E,record_index=U,payload=U),primary=PRIMARY_C)
PRIMARY_P=dict(logical_sequence=U,record_index=U,scheduled_arrival=U,
    **dict.fromkeys(('producer_handle_begin','record_lookup_completion','enqueue_invocation','enqueue_linearization','enqueue_attempt_completion'),PAIR),outcome=E,accepted_ordinal=U)
PRODUCER=dict(capture=CAPTURE,failed_boundary=None,requested_attempt=nums('logical_sequence scheduled_arrival candidate_accepted_ordinal'),
    selected=nums('record_index record_address'),**dict.fromkeys(('handle_begin','lookup_completion','enqueue_invocation','demand_before','demand_after','enqueue_publication','enqueue_completion'),CLOCK),primary=PRIMARY_P)
OWNER=dict(**dict.fromkeys(('affinity','current_cpu','thread_id','faults'),CALL),**nums('minor_faults major_faults affinity_cpu_count'),requested_cpu_in_affinity=F)
PLAN=nums('bytes verified_base_page_bytes owner_cpu requested_node')
MEMORY=dict(address=U,bytes=U)
REGION=dict(address=U,bytes=U,expected_node=U)
MAP=dict(requested=PLAN,**dict.fromkeys(('base_page_bytes','binding','no_huge_pages','affinity_request','lock','read_only','unlock','unmap'),CALL),
    mapping=dict(address=U,error_number=U),before_touch=OWNER,after_touch=OWNER,prefaulted_pages=U,stop=E,cleanup_attempted=F)
STACK=dict(requested=PLAN,**dict.fromkeys(('base_page_bytes','minimum_stack_bytes','binding','no_huge_pages','guard','populate','lock','unlock','unmap'),CALL),
    mapping=dict(address=U,error_number=U),before_populate=OWNER,after_populate=OWNER,stop=E,cleanup_attempted=F,
    thread=nums('attribute_init attribute_stack attribute_guard attribute_affinity create attribute_destroy join'))
WORKER=dict(stop=E,**nums('attempts advanced full empty last_observed_tick'),
    **dict.fromkeys(('last_attempt_outcome','last_operation_outcome','last_attempt_before_status','last_attempt_after_status','failed_clock_status'),None))
DRAIN=dict(stop=E,**nums('attempts dequeued last_observed_tick'),failed_clock_status=None,reset_verified=F,
    final_audit=dict(**nums('occupied_slots producer_position consumer_position'),positions_in_range=F))
SESSION=dict(stop=E,warmup_verified=F,measurement_verified=F,preparation=Repeat(E,2),worker_exception=Repeat(F,2),private_reset_verified=Repeat(F,2),
    origins=Repeat(U,2),observed_origins=Repeat(U,2),origin_status=Repeat(None,2),warmup=Repeat(WORKER,2),measurement=Repeat(WORKER,2),
    warmup_drain=DRAIN,measurement_drain=DRAIN,observations=Repeat(dict(before=E,during=E,after=E),2))
ROW_LAYOUT=nums('run_id_bytes prefix_bytes producer_row_bytes consumer_row_bytes joined_row_bytes')
LAYOUT_WORKERS=dict(**nums('records_bytes producer_bytes consumer_bytes record_order arena_object ring_object slots cursors'),
    ring_storage=nums('slot_bytes cursor_bytes'),phases=Repeat(dict(count=U,row=ROW_LAYOUT,raw=nums('producer_bytes consumer_bytes'),
        **nums('producer_object producer_demand producer_issue producer_raw consumer_object consumer_demand consumer_issue consumer_raw drain')),2))
ARENA=dict(**nums('capacity cache_line_bytes base_page_bytes allocated_bytes distinct_cache_lines distinct_pages storage_address'),
    **dict.fromkeys(('base_page_aligned','every_record_line_aligned','padding_initialized','content_unchanged'),F),
    **dict.fromkeys(('prepared_content_sha256','publication_content_sha256','ordered_index_sha256','address_delta_sha256'),'f'*64),
    ordered_index_error=None,address_delta_error=None)
REQUEST=nums('phase moment region_index offset_ticks')
TLS=dict(stop=E,iteration_return=U,**dict.fromkeys(('thread_before','thread_after','fs_read'),CALL),
    **nums('fs_base loader_adds loader_subs visited_objects used'),modules=Repeat(nums('image_base module_id address bytes'),8))
IDENTITY=nums('family model')
HW_PREP=dict(attempted=F,released=F,stop=E,requested_identity=IDENTITY,
    observed_identity=dict(value=IDENTITY,errors=[dict(category=E,path='$q15_fixed_msr',rule_id='Q15-CPUID-LEAF1',message='CPUID leaf 1 is unavailable')]),
    mapping_id=MAPPING,resolver_errors=[],cpu_count=U,cpus=Repeat(dict(**nums('cpu expected_h0 expected_h1'),open=CALL,close=CALL),3))
HW_SAMPLE=dict(attempted=F,stop=E,requested_state=E,prepared_controller_identity=IDENTITY,mapping_id=MAPPING,cpu_count=U,
    cpus=Repeat(dict(**nums('cpu expected_value observed_value'),read=CALL,matches=F,raw_bytes=Repeat(255,8)),3))
THREAD_FILE=dict(read=CALL,end_probe=CALL,end_probe_byte=None,complete=F,raw_bytes=Repeat(255,4096))
STAT=dict(**nums('task_id start_time_ticks minor_faults major_faults last_cpu'),state='\x00')
THREAD=dict(stop=E,**dict.fromkeys(('stat_before_read','stat_after_read','status_read'),THREAD_FILE),stat_before=STAT,stat_after=STAT,
    status=nums('task_id thread_group_id voluntary_context_switches involuntary_context_switches'),affinity_call=CALL,
    **nums('affinity_cpu_count singleton_affinity_cpu'),affinity_mask=Repeat(U,4))
THREAD_PREP=dict(requested_task_id=U,attempted=F,ready=F,directory_open=CALL,stat_open=CALL,status_open=CALL,initial=THREAD,closes=Repeat(CALL,3))
ENV_PLAN=dict(path_bytes=list(b'/proc/self/smaps'),byte_capacity=1048576,chunk_bytes=4096,max_data_reads=1024,requested=Repeat(F,6))
ENV_PREP=dict(attempted=F,released=F,stop=E,open=CALL,close=CALL,plan=ENV_PLAN)
FILE_READ=dict(offset=U,requested_bytes=U,observed=CALL)
ENV_SAMPLE=dict(source_index=U,group_index=U,attempted=F,stop=E,**nums('captured_bytes byte_capacity data_reads read_capacity'),
    raw_bytes=Repeat(255,1048576),reads=Repeat(FILE_READ,1024),eof_probe=FILE_READ,probe_byte=None)

def reference(name,role,schema):
    return dict(file_name=name,role=role,schema_identity=schema,size_bytes=U,sha256='f'*64)

def phase(name,drains):
    rid='D178W26N0300'  # preview IDs all have exactly 12 ASCII bytes
    snap=dict(run_id=rid,stream_kind=E,**nums('row_count row_capacity row_bytes retained_bytes'),completeness='SEALED_INCOMPLETE',overflowed=F)
    return dict(producer_available=F,consumer_available=F,
        producer=reference(name+'-producer.bin','DISCOVERY_PRODUCER_RAW','RAW-OBS-U64LE-LP-RUNID-v1'),
        consumer=reference(name+'-consumer.bin','DISCOVERY_CONSUMER_RAW','RAW-OBS-U64LE-LP-RUNID-v1'),
        demand=reference(name+'-demand.bin','DISCOVERY_DEMAND_RAW','DISCOVERY-FOUR-U64LE-VECTORS-v1'),
        producer_snapshot=snap,consumer_snapshot=snap,producer_layout=ROW_LAYOUT,consumer_layout=ROW_LAYOUT,
        run_id=rid,consumer_run_id=rid,**nums('attempted accepted full producer_row_count consumed_including_drain consumer_row_count checksum initial_checksum drain_requests producer_nonadvancing consumer_nonadvancing'),
        producer_prefix_complete=F,consumer_prefix_complete=F,capture_horizon_complete=F,drain_retention_exhausted=F,
        producer_last_append=None,consumer_last_append=None,producer_current=PRODUCER,consumer_current=CONSUMER,
        consumer_last_join=dict(status=E,matched=U,failed_producer_row=U),drain_rows=Repeat(CONSUMER,drains),
        demand_vectors=[dict(name=n,available=F,offset_bytes=U,count=U) for n in ('producer_demand','producer_issue','consumer_demand','consumer_issue')])

def residency(pages):
    return dict(request=REQUEST,stop=E,controls=E,wait_first=CLOCK,wait_last=CLOCK,begin=CLOCK,end=CLOCK,
        **nums('wait_polls prior_controller_tick finished_before finished_after'),query=nums('syscall_return error_number'),
        page_addresses=Repeat(U,pages),page_status=Repeat(-2147483648,pages))

FINAL=dict(stop=E,session=SESSION,clock_origin=dict(status=E,absolute_nanoseconds=U),core_mapping=MAP,monitor_mapping=MAP,controller_stack=STACK,
    worker_mappings=Repeat(MAP,3),worker_stacks=Repeat(STACK,2),publication_attempted=F,publication_succeeded=F)

def control(row,counts):
    pages=[n//4096 for n in row['layout']['region_bytes']]
    queries=[residency(1 if moment==1 else n) for phase_ in range(2) for moment in range(3) for n in pages]
    return dict(schema_version='cpu-prefetch-stage17-discovery-control/1',capture_ordinal=U,capture_stop_before_publication=E,
        clock_origin=dict(status=E,absolute_nanoseconds=U),publication_attempted=F,publication_succeeded=F,
        cleanup_observation_scope='BEFORE_PUBLICATION_RETURNS_FINAL_CLEANUP_REQUIRES_RETURNED_NATIVE_RESULT',
        core_mapping=MAP,monitor_mapping=MAP,controller_stack=STACK,worker_mappings=Repeat(MAP,3),worker_stacks=Repeat(STACK,2),
        result_worker_mappings=Repeat(MAP,3),result_worker_stacks=Repeat(STACK,2),worker_preparation=Repeat(E,2),
        core=MEMORY,monitor_arena=MEMORY,arena=ARENA,hardware_preparation=HW_PREP,
        environment_preparations=[ENV_PREP],environment_samples=Repeat(ENV_SAMPLE,6),
        environment_group_order=['WARMUP_BEFORE','WARMUP_DURING','WARMUP_AFTER','MEASUREMENT_BEFORE','MEASUREMENT_DURING','MEASUREMENT_AFTER'],
        thread_preparations=Repeat(THREAD_PREP,2),layout=dict(core_bytes=U,workers=LAYOUT_WORKERS,monitor_bytes=U,total_mapping_bytes=U,region_bytes=Repeat(U,7)),
        session=SESSION,phases=[phase('discovery-c00-'+p,n) for p,n in zip(('warmup','measurement'),counts)],
        regions=Repeat(REGION,7),residency=queries,controls=Repeat(dict(request=REQUEST,attempted=F,stop=E,workers=Repeat(THREAD,2),hardware=HW_SAMPLE),6),
        tls_snapshots=Repeat(TLS,6),diagnostic_only=F,execution_authority=F,phase18_authority=F)
