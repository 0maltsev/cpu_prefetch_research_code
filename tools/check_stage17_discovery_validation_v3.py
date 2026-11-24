"""Independent synthetic fixtures/mutants; no scientific or hardware evidence."""
from __future__ import annotations
import contextlib
import copy
import dataclasses
import hashlib
import importlib.util
import io
import json
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

import stage17_discovery_validation_v3 as v
import check_stage17_discovery_v2 as plans
import check_stage17_discovery_action_v2 as actions

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tests'))
import test_stage17_discovery_environment as env_fixture
import test_stage17_discovery_metadata as metadata_fixture


def binding(path):
    return dict(file_name=path.name,size_bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def sample(tick,origin=1_000_000):
    return dict(absolute_nanoseconds=origin+tick//1000,relative_picoseconds=tick)


def clock(tick): return dict(status=0,**sample(tick))
def call(value=0): return dict(return_value=value,error_number=0)


def raw_phase(root,cap,phase_name='measurement',*,full=False,limited=False):
    identity=getattr(cap,phase_name);run_id=identity.run_id
    warmup=phase_name=='warmup'
    duration=v.contract.WARMUP_NS if warmup else cap.measurement_ns
    origin=100_000 if warmup else v.contract.WARMUP_NS*1000+1_000_000
    deadline=origin+duration*1000
    capacity=getattr(cap.budget,phase_name+'_attempt_capacity')
    count=capacity if limited else 3
    arena=v.Arena(cap)
    p_rows=[];c_rows=[];checksum=17;accepted=0
    for logical in range(count):
        index=arena.order[logical%len(arena.order)];t=origin+(logical*10+1)*1000
        is_full=full and logical==1
        p=[logical,index,t]
        for tick in (t,t+1000,t+2000,0 if is_full else t+3000,t+4000):
            p.extend((0,0) if tick==0 else (1_000_000+tick//1000,tick))
        p.extend((0 if is_full else accepted,1 if is_full else 15));p_rows.append(p)
        if not is_full:
            c=[accepted,index]
            for tick in (t+5000,t+6000,t+7000,t+8000):c.extend((1_000_000+tick//1000,tick))
            c_rows.append(c);accepted+=1;checksum=v.mix(checksum,index,arena.payload[index])
    # The last accepted event is consumed by drain and never contributes demand/issue counts.
    drain_base=deadline+200_000
    for i in range(4):c_rows[-1][2+i*2:4+i*2]=[1_000_000+drain_base//1000+i,drain_base+i*1000]
    prefix=v.codec._prefix(run_id)
    base=f'discovery-c{cap.ordinal:02d}-{phase_name}'
    files=[]
    for name,rows,words in (('producer',p_rows,15),('consumer',c_rows,10)):
        path=root/(base+'-'+name+'.bin')
        with path.open('wb') as stream:
            for row in rows:stream.write(prefix+struct.pack('<'+str(words)+'Q',*row))
        files.append(dict(binding(path),role='DISCOVERY_'+name.upper()+'_RAW',schema_identity=v.codec.FORMAT_ID))
    advancing=accepted-1;empty=1 if limited else 2;consumer_attempts=advancing+empty
    vector_counts=(count,max(accepted-1,0),consumer_attempts,max(advancing-1,0))
    pstarts=[p[8] for p in p_rows if p[14]==15];cstarts=[c[3] for c in c_rows[:advancing]]
    vectors=([1000]*count,[b-a for a,b in zip(pstarts,pstarts[1:])],
             [1000]*consumer_attempts,[b-a for a,b in zip(cstarts,cstarts[1:])])
    path=root/(base+'-demand.bin');path.write_bytes(b''.join(struct.pack('<Q',x) for vector in vectors for x in vector))
    files.append(dict(binding(path),role='DISCOVERY_DEMAND_RAW',schema_identity='DISCOVERY-FOUR-U64LE-VECTORS-v1'))
    prefix_bytes,pbytes,cbytes,jbytes=v.codec.row_layout(run_id)
    layout=dict(run_id_bytes=len(run_id),prefix_bytes=prefix_bytes,producer_row_bytes=pbytes,consumer_row_bytes=cbytes,joined_row_bytes=jbytes)
    result=dict(producer_available=True,consumer_available=True,producer=files[0],consumer=files[1],demand=files[2],
        run_id=run_id,consumer_run_id=run_id,attempted=count,accepted=accepted,full=int(full),producer_row_count=count,
        consumer_row_count=accepted,consumed_including_drain=accepted,producer_prefix_complete=True,consumer_prefix_complete=True,
        checksum=checksum,initial_checksum=17,capture_horizon_complete=not limited,drain_requests=2,drain_retention_exhausted=False,
        producer_nonadvancing=int(full),consumer_nonadvancing=empty,producer_layout=layout,consumer_layout=copy.deepcopy(layout))
    result.update(producer_last_append=0,consumer_last_append=0,consumer_last_join=dict(status=1,matched=accepted,failed_producer_row=None))
    for name,kind,n,row_bytes in (('producer',0,count,pbytes),('consumer',1,accepted,cbytes)):
        result[name+'_snapshot']=dict(run_id=run_id,stream_kind=kind,row_count=n,row_capacity=capacity,row_bytes=row_bytes,
            retained_bytes=n*row_bytes,overflowed=False,completeness='SEALED_INCOMPLETE' if limited else 'SEALED_COMPLETE')
    offset=0;vectors=[]
    for name,n in zip(('producer_demand','producer_issue','consumer_demand','consumer_issue'),vector_counts):
        vectors.append(dict(name=name,available=True,offset_bytes=offset,count=n));offset+=n*8
    result['demand_vectors']=vectors
    workers=[dict(stop=1 if limited else 0,attempts=count,advanced=accepted,full=int(full),empty=0,
                  last_observed_tick=deadline-1000 if limited else deadline,failed_clock_status=None,
                  last_attempt_outcome=0,last_operation_outcome=0,last_attempt_before_status=0,last_attempt_after_status=0),
             dict(stop=6 if limited else 0,attempts=consumer_attempts,advanced=advancing,full=0,empty=empty,
                  last_observed_tick=deadline-1000 if limited else deadline,failed_clock_status=None,
                  last_attempt_outcome=2,last_operation_outcome=2,last_attempt_before_status=0,last_attempt_after_status=0)]
    c=c_rows[-1]
    primary=dict(consumed_ordinal=c[0],observed_record_index=c[1])
    for name,i in (('dequeue_invocation',2),('dequeue_linearization',4),('dequeue_completion',6),('consumer_action_completion',8)):
        primary[name]=dict(absolute_nanoseconds=c[i],relative_picoseconds=c[i+1])
    def event(empty):
        t=drain_base+(10000 if empty else 0)
        return dict(failed_boundary=None,capture=dict(operation_performed=True,failed_clock_status=None,
            before_status=0,after_status=0,outcome=2 if empty else 0,operation_outcome=2 if empty else 0),
            candidate_consumed_ordinal=accepted if empty else advancing,
            dequeue_invocation=clock(t),dequeue_observation=None if empty else clock(t+1000),
            dequeue_completion=None if empty else clock(t+2000),action_completion=None if empty else clock(t+3000),
            demand_before=clock(t),demand_after=clock(t+1000),
            primary=None if empty else primary,operation=dict(status=1 if empty else 0,event_address=None if empty else 0x100000+c[1]*64),
            access=None if empty else dict(status=0,record_index=c[1],payload=arena.payload[c[1]]))
    result['drain_rows']=[event(False),event(True)]
    p=p_rows[-1];producer_primary=dict(logical_sequence=p[0],record_index=p[1],scheduled_arrival=p[2],outcome=0,accepted_ordinal=p[13])
    producer_current=dict(capture=dict(operation_performed=True,outcome=0,operation_outcome=0,before_status=0,after_status=0,failed_clock_status=None),
        failed_boundary=None,requested_attempt=dict(logical_sequence=p[0],scheduled_arrival=p[2],candidate_accepted_ordinal=p[13]),
        selected=dict(record_index=p[1],record_address=0x100000+p[1]*64),demand_before=clock(p[8]),demand_after=clock(p[8]+1000))
    for event_name,primary_name,i in (('handle_begin','producer_handle_begin',3),('lookup_completion','record_lookup_completion',5),
            ('enqueue_invocation','enqueue_invocation',7),('enqueue_publication','enqueue_linearization',9),('enqueue_completion','enqueue_attempt_completion',11)):
        producer_current[event_name]=clock(p[i+1]);producer_primary[primary_name]=dict(absolute_nanoseconds=p[i],relative_picoseconds=p[i+1])
    producer_current['primary']=producer_primary
    consumer_current=event(True);consumer_current['candidate_consumed_ordinal']=advancing
    current_time=origin+count*10000
    consumer_current.update(dequeue_invocation=clock(current_time),demand_before=clock(current_time),demand_after=clock(current_time+1000))
    result.update(producer_current=producer_current,consumer_current=consumer_current)
    drain=dict(stop=0,reset_verified=warmup,failed_clock_status=None,attempts=2,dequeued=1,last_observed_tick=drain_base+10000,
        final_audit=dict(occupied_slots=0,positions_in_range=True,producer_position=accepted,consumer_position=accepted))
    kwargs=dict(run_id=run_id,phase_origin=origin,clock_origin=1_000_000,duration_ns=duration,attempt_capacity=capacity,
        drain_capacity=cap.budget.drain_attempt_capacity,initial_checksum=17,arena=arena,reset_required=warmup,arena_address=0x100000)
    return result,workers,drain,kwargs


def thread(tid,cpu):
    fields=['0']*50;fields[0]='R';fields[7]='10';fields[9]='0';fields[19]='1234';fields[36]=str(cpu)
    raw_stat=(str(tid)+' (test (thread)) '+' '.join(fields)+'\n').encode()
    raw_status=f'Pid:\t{tid}\nTgid:\t100\nvoluntary_ctxt_switches:\t3\nnonvoluntary_ctxt_switches:\t4\n'.encode()
    def f(raw):return dict(complete=True,raw_bytes=list(raw),read=call(len(raw)),end_probe=call(),end_probe_byte=None)
    stat=dict(task_id=tid,state='R',start_time_ticks=1234,minor_faults=10,major_faults=0,last_cpu=cpu)
    return dict(stop=7,stat_before_read=f(raw_stat),stat_after_read=f(raw_stat),status_read=f(raw_status),
        stat_before=stat,stat_after=copy.deepcopy(stat),status=dict(task_id=tid,thread_group_id=100,voluntary_context_switches=3,involuntary_context_switches=4),
        affinity_mask=[1<<cpu],affinity_call=call(8),affinity_cpu_count=1,singleton_affinity_cpu=cpu)


def mapping(plan,address,tid,*,stack=False,cleanup=False):
    observation=dict(affinity=call(),current_cpu=call(plan['owner_cpu']),thread_id=call(tid),faults=call(),
        minor_faults=0,major_faults=0,affinity_cpu_count=1,requested_cpu_in_affinity=True)
    result=dict(requested=plan,base_page_bytes=call(plan['verified_base_page_bytes']),mapping=dict(address=address,error_number=0),
        binding=call(),no_huge_pages=call(),lock=call(),unlock=call() if cleanup else None,unmap=call() if cleanup else None,
        cleanup_attempted=cleanup,stop=11 if stack else 10)
    if stack:
        result.update(minimum_stack_bytes=call(4096),guard=call(),populate=call(),before_populate=observation,after_populate=copy.deepcopy(observation),
            thread={k:0 for k in ('attribute_init','attribute_stack','attribute_guard','attribute_affinity','create','attribute_destroy','join')})
    else:result.update(affinity_request=call(),before_touch=observation,after_touch=copy.deepcopy(observation),read_only=call(),prefaulted_pages=plan['bytes']//4096)
    return result


def capture_fixture(root,cap,*,limited=False,full=False):
    g=cap.geometry
    stack=lambda cpu,node:dict(bytes=16384,verified_base_page_bytes=4096,owner_cpu=cpu,requested_node=node)
    sizes=[g.capacity*64,4096,4096,16384,16384,4096,16384]
    r=dict(ordinal=cap.ordinal,workers=dict(producer_stack=stack(g.producer_cpu,g.producer_node),consumer_stack=stack(g.consumer_cpu,g.consumer_node)),
        controller_stack=stack(2,0),core_bytes=4096,monitor_bytes=131072,total_mapping_bytes=sum(sizes)+131072+3*4096,
        region_bytes=sizes,tls_module_capacity=8,thread_stat_bytes=4096,thread_status_bytes=4096,thread_affinity_words=1,initial_consumer_state=17)
    m=dict(ordinal=cap.ordinal,during_first_page=[0]*7,during_page_count=[1]*7,during_offset_ticks=[2_500_000_000_000, cap.measurement_ns*250],
        observer_wait_poll_limit=100,control_region_index=5,counter_limits=[[dict(minor_faults=0,major_faults=0,voluntary_switches=0,involuntary_switches=0) for _ in range(2)] for _ in range(2)],
        hardware_identity=dict(family=6,model=62))
    hardware=dict(mapping_id='INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1',prestate=[dict(cpu=c,complete_value_hex='0000000000000000') for c in (0,1,8)])
    control=dict(schema_version='cpu-prefetch-stage17-discovery-control/1',capture_ordinal=cap.ordinal,diagnostic_only=True,execution_authority=False,phase18_authority=False,
        capture_stop_before_publication=15 if limited else 13,clock_origin=dict(status=0,absolute_nanoseconds=1_000_000),publication_attempted=True,publication_succeeded=False,
        cleanup_observation_scope='BEFORE_PUBLICATION_RETURNS_FINAL_CLEANUP_REQUIRES_RETURNED_NATIVE_RESULT',worker_preparation=[7,7])
    regions=[];maps=[];stacks=[]
    for i in range(3):
        cpu=(g.producer_cpu,g.producer_cpu,g.consumer_cpu)[i];node=(g.shared_node,g.producer_node,g.consumer_node)[i]
        plan=dict(bytes=sizes[i],verified_base_page_bytes=4096,owner_cpu=cpu,requested_node=node)
        address=0x100000+i*0x100000
        maps.append(mapping(plan,address,101 if i<2 else 102))
        regions.append(dict(address=address,bytes=sizes[i],expected_node=node))
    for i,name in enumerate(('producer_stack','consumer_stack')):
        address=0x400000+i*0x100000;plan=r['workers'][name]
        stacks.append(mapping(plan,address-4096,101+i,stack=True))
        regions.append(dict(address=address,bytes=plan['bytes'],expected_node=plan['requested_node']))
    control.update(worker_mappings=maps,worker_stacks=stacks)
    for name,address in (('core',0x600000),('monitor',0x800000)):
        plan=dict(r['controller_stack'],bytes=r[name+'_bytes'])
        control[name+'_mapping']=mapping(plan,address,103)
        control['core' if name=='core' else 'monitor_arena']=dict(address=address,bytes=plan['bytes'])
    regions.append(dict(address=0x600000,bytes=4096,expected_node=0))
    control['controller_stack']=mapping(r['controller_stack'],0x700000-4096,103,stack=True)
    regions.append(dict(address=0x700000,bytes=16384,expected_node=0));control['regions']=regions
    control['layout']={k:r[k] for k in ('core_bytes','monitor_bytes','total_mapping_bytes','region_bytes')}
    control['tls_snapshots']=[]
    for role in (0,1,0,1,2,2):
        address=regions[(3,4,6)[role]]['address']
        control['tls_snapshots'].append(dict(stop=6,iteration_return=0,thread_before=call(101+role),thread_after=call(101+role),fs_read=call(),fs_base=address+512,
            modules=[dict(image_base=0,module_id=1,address=address+128,bytes=32)],used=1,visited_objects=2,loader_adds=2,loader_subs=0))
    control['hardware_preparation']=dict(attempted=True,released=True,stop=6,resolver_errors=[],requested_identity=m['hardware_identity'],
        observed_identity=dict(value=m['hardware_identity'],errors=[]),mapping_id=hardware['mapping_id'],cpu_count=3,
        cpus=[dict(cpu=c,expected_h0=0,expected_h1=15,open=call(10+i),close=call()) for i,c in enumerate((0,1,8))])
    control['thread_preparations']=[dict(requested_task_id=101+i,attempted=True,ready=False,directory_open=call(10),stat_open=call(11),status_open=call(12),closes=[call()]*3,
        initial=thread(101+i,cpu)) for i,cpu in enumerate((g.producer_cpu,g.consumer_cpu))]
    phases=[];session=dict(stop=8 if limited else 9,warmup_verified=True,measurement_verified=True,preparation=[1,1],worker_exception=[False,False],
        private_reset_verified=[True,True],origin_status=[0,0],observations=[dict(before=2,during=2,after=2)]*2,origins=[])
    for name in ('warmup','measurement'):
        phase,workers,drain,kwargs=raw_phase(root,cap,name,full=full,limited=limited and name=='measurement')
        phases.append(phase);session[name]=workers;session[name+'_drain']=drain;session['origins'].append(kwargs['phase_origin'])
    session['observed_origins']=copy.deepcopy(session['origins']);control['session']=session;control['phases']=phases
    arena=v.Arena(cap)
    control['arena']=dict(capacity=g.capacity,cache_line_bytes=64,base_page_bytes=4096,allocated_bytes=g.capacity*64,distinct_cache_lines=g.capacity,distinct_pages=g.capacity*64//4096,
        base_page_aligned=True,every_record_line_aligned=True,padding_initialized=True,storage_address=regions[0]['address'],content_unchanged=True,
        prepared_content_sha256=arena.hashes[0],publication_content_sha256=arena.hashes[0],ordered_index_sha256=arena.hashes[1],address_delta_sha256=arena.hashes[2],ordered_index_error=None,address_delta_error=None)
    control['controls']=[];control['residency']=[]
    state=0 if cap.hardware_state=='H0' else 1
    for phase in range(2):
        origin=session['origins'][phase];duration=v.contract.WARMUP_NS if phase==0 else cap.measurement_ns
        for moment in range(3):
            request=dict(phase=phase,moment=moment,region_index=5,offset_ticks=m["during_offset_ticks"][phase] if moment==1 else 0)
            control['controls'].append(dict(request=request,attempted=True,stop=6,workers=[thread(101,g.producer_cpu),thread(102,g.consumer_cpu)],
                hardware=dict(attempted=True,stop=4,mapping_id=hardware['mapping_id'],prepared_controller_identity=m['hardware_identity'],requested_state=state,cpu_count=3,
                    cpus=[dict(cpu=c,read=call(8),raw_bytes=list((15 if state else 0).to_bytes(8,'little')),observed_value=15 if state else 0,expected_value=15 if state else 0,matches=True) for c in (0,1,8)])))
            for i,region in enumerate(regions):
                t=(origin-20000 if moment==0 else origin+m["during_offset_ticks"][phase] if moment==1 else origin+duration*1000+100000)+i*2000
                count=1 if moment==1 else region['bytes']//4096
                control['residency'].append(dict(request=dict(request,region_index=i),stop=8,controls=2 if i==5 else 1,query=dict(syscall_return=0,error_number=0),
                    page_addresses=[region['address']+j*4096 for j in range(count)],page_status=[region['expected_node']]*count,begin=clock(t),end=clock(t+1000),
                    wait_first=clock(t) if moment==1 else None,wait_last=clock(t) if moment==1 else None,wait_polls=1 if moment==1 else 0,
                    finished_before=0 if moment==1 else None,finished_after=0 if moment==1 else None))
    source=dict(path='/proc/self/smaps',byte_capacity=16384,chunk_bytes=1024,max_data_reads=32,requested=[True]*6)
    m['environment_sources']=[source]
    raw=b''.join(env_fixture.vma(row['address'],row['address']+row['bytes']) for row in regions)
    control.update(environment_group_order=list(v.environment.GROUP_ORDER),environment_preparations=[dict(attempted=True,released=True,stop=4,open=call(20),close=call(),
        plan=dict(path_bytes=list(source['path'].encode()),**{k:x for k,x in source.items() if k!='path'}))],
        environment_samples=[env_fixture.sample(raw,source,0,group) for group in range(6)])
    final={k:copy.deepcopy(control[k]) for k in ('session','clock_origin','worker_mappings','worker_stacks','controller_stack','core_mapping','monitor_mapping')}
    final.update(stop=15 if limited else 13,publication_attempted=True,publication_succeeded=True)
    for item in [*final['worker_mappings'],*final['worker_stacks'],final['controller_stack'],final['core_mapping'],final['monitor_mapping']]:
        item.update(cleanup_attempted=True,unlock=call(),unmap=call())
    return control,final,r,m,hardware


def study_fixture(root):
    plan=plans.fixture()
    for item in plan['captures']:
        item['geometry']['capacity']=64
    parsed=v.contract.validate_plan(plan)
    resources=[];monitoring=[];native=[];retained=[];finals=[]
    for cap in parsed.captures:
        control,final,r,m,hardware=capture_fixture(root,cap,limited=False,full=True)
        files=[]
        for phase in control['phases']:
            for name in ('producer','consumer','demand'):
                files.append({key:phase[name][key] for key in ('file_name','size_bytes','sha256')})
        path=root/f'discovery-c{cap.ordinal:02d}-control.json'
        path.write_bytes(v.registry.canonical(control));files.append(binding(path))
        resources.append(r);monitoring.append(m);native.append(dict(ordinal=cap.ordinal,resources=r,monitoring=m));finals.append(final)
        retained.append(dict(ordinal=cap.ordinal,warmup_run_id=cap.warmup.run_id,measurement_run_id=cap.measurement.run_id,
            artifacts=files,native_stop='complete',native_validity='INSUFFICIENT',failure_reasons=[]))
    docs={name:dict(synthetic=name) for name in ('stand','qualification','namespace_registry')}
    docs.update(resource_plan=dict(schema_version='cpu-prefetch-discovery-resources/1',captures=resources),
                monitoring_plan=dict(schema_version='cpu-prefetch-discovery-monitoring/1',captures=monitoring))
    for name,doc in docs.items():plan[name]=actions.bound(name,doc)
    for dep in plan['dependencies']:
        name=dep['resolution']['artifact_id'];doc=dict(synthetic=name);docs[name]=doc;dep['resolution']=actions.bound(name,doc)
    parsed=v.contract.validate_plan(plan)
    whole=[]
    for state in ('H0','H1'):
        whole.append(dict(state=state,restoration_verified=True,
            restore_readback=list(reversed(hardware['prestate'])) if state=='H1' else [],
            apply_readback=[dict(cpu=c,complete_value_hex='000000000000000f') for c in (0,1,8)] if state=='H1' else []))
    hw=dict(schema_version='cpu-prefetch-stage17-discovery-hardware/1',plan_sha256=parsed.sha256,mapping_id=hardware['mapping_id'],
        whole_plots=whole,native_results_after_cleanup=finals,restoration_verified=True,mandatory_failure=False,phase18_authority=False)
    path=root/'studyhardware.json';path.write_bytes(v.registry.canonical(hw));hw_binding=binding(path)
    report=dict(schema_version='cpu-prefetch-stage17-discovery-retention-report/1',plan_sha256=parsed.sha256,captures=retained,hardware_state=hw_binding,
        diagnostic_only=True,scientific_validity='NOT_ASSESSED',eligible_for_duration_selection=False,formal_runs_contributed=0,execution_authority=False)
    path=root/v.registry.REPORT_NAME;path.write_bytes(v.registry.canonical(report))
    inputs=dict(plan=plan,hardware_control=hardware,native_captures=native,
        bound_documents=[dict(artifact_id=name,document=doc,utf8_bytes=v.registry.canonical(doc).decode()) for name,doc in docs.items()])
    return dict(action_inputs=inputs,retention_report=report,retention_binding=binding(path),output_root=root)


class IndependentDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
        base=v.contract.validate_plan(plans.fixture()).captures[0]
        self.cap=dataclasses.replace(base,geometry=dataclasses.replace(base.geometry,capacity=64),
            budget=dataclasses.replace(base.budget,warmup_attempt_capacity=8,measurement_attempt_capacity=8))

    def test_deterministic_cpp_known_answers(self):
        self.assertEqual(v.draw((0,0),0),0x6627e8d5e169c58d)
        self.assertEqual(v.draw((0,0),1),0xbc57ac4c9b00dbd8)
        seed=bytes(range(32)).hex();k=v.key(seed,'stage6-test','event-order')
        self.assertEqual(k,(0x204497c9,0x221fbf67));self.assertEqual(v.draw(k,0),0x22585625d47ac20b)
        cap=dataclasses.replace(self.cap,geometry=dataclasses.replace(self.cap.geometry,capacity=8),
            arena_seed=dataclasses.replace(self.cap.arena_seed,seed_hex=seed,namespace_id='stage6-test'))
        arena=v.Arena(cap)
        self.assertEqual(list(arena.order),[7,4,0,5,2,6,1,3])
        self.assertEqual(arena.hashes,('a14a1bde2dacaf6622af22ccb0b05b3c98b95a40741f9c25e85625ad2e393d60',
            'af670b376e5b3784d7d3fa5fb326fd630d05f2a9d0e8c2fcf1f325232dbfa73b','e36232c7069da78a765c528361837744233ca7ed54554d836bf58e4c9503aa12'))

    def test_software_memory_and_syscall_integer_bounds(self):
        for geometry in (dataclasses.replace(self.cap.geometry,capacity=1<<24),
                         dataclasses.replace(self.cap.geometry,cache_line_bytes=1<<30)):
            with self.subTest(geometry=geometry),self.assertRaises(v.ValidationError):
                v.Arena(dataclasses.replace(self.cap,geometry=geometry))
        with self.assertRaises(v.ValidationError):v.call(call(1<<63),minimum=0)

    def test_independent_raw_join_drain_and_full_separate_from_validity(self):
        phase,workers,drain,kwargs=raw_phase(self.root,self.cap,full=True)
        result=v.validate_phase(self.root,phase,workers,drain,**kwargs)
        self.assertEqual((result.attempted,result.accepted,result.full,result.consumed),(3,2,1,2))
        self.assertFalse(result.zero_loss)
        self.assertEqual(result.counts,v.selector.ObservationCounts(3,3,1,0))

    def test_capacity_is_retained_insufficient(self):
        c,f,r,m,h=capture_fixture(self.root,self.cap,limited=True)
        result,phases=v.validate_capture(self.root,c,f,self.cap,r,m,h)
        self.assertEqual(result.stop_reason,v.selector.StopReason.trace_capacity)
        self.assertTrue(phases[1].capacity_limited)
        # A peer can finish an admitted operation after the other owner's
        # capacity poll, and exit without taking a new loop clock reading.
        p,w,d,k=raw_phase(self.root,self.cap,limited=True)
        event=p['consumer_current'];before=event['demand_before']['relative_picoseconds']
        after=k['phase_origin']+k['duration_ns']*1000+100000
        event['demand_after']=clock(after);w[1]['last_observed_tick']=before
        path=self.root/p['demand']['file_name'];payload=bytearray(path.read_bytes())
        vector=p['demand_vectors'][2]
        struct.pack_into('<Q',payload,vector['offset_bytes']+(vector['count']-1)*8,after-before)
        path.write_bytes(payload);p['demand'].update(binding(path))
        self.assertTrue(v.validate_phase(self.root,p,w,d,**k).capacity_limited)

    def test_complete_capture_all_raw_controls(self):
        args=capture_fixture(self.root,self.cap,full=True)
        c,f,r,m,h=args
        result,phases=v.validate_capture(self.root,c,f,self.cap,r,m,h)
        self.assertEqual(result.stop_reason,v.selector.StopReason.fixed_deadline)
        self.assertFalse(phases[1].zero_loss)

    def test_consumer_admitted_attempt_can_cross_fixed_horizon(self):
        p,w,d,k=raw_phase(self.root,self.cap)
        deadline=k['phase_origin']+k['duration_ns']*1000
        path=self.root/p['consumer']['file_name'];data=bytearray(path.read_bytes())
        prefix,_,row_bytes,_=v.codec.row_layout(k['run_id']);offset=row_bytes+prefix
        c=list(struct.unpack_from('<10Q',data,offset))
        for i in range(4):c[2+i*2:4+i*2]=[1_000_000+deadline//1000+i,deadline+i*1000]
        struct.pack_into('<10Q',data,offset,*c);path.write_bytes(data);p['consumer'].update(binding(path))
        w[1].update(last_observed_tick=deadline+5000,last_attempt_outcome=0,last_operation_outcome=0)
        primary=dict(consumed_ordinal=c[0],observed_record_index=c[1])
        event=dict(failed_boundary=None,candidate_consumed_ordinal=c[0],capture=dict(operation_performed=True,failed_clock_status=None,
            outcome=0,operation_outcome=0,before_status=0,after_status=0),operation=dict(status=0,event_address=0x100000+c[1]*64),
            access=dict(status=0,record_index=c[1],payload=k['arena'].payload[c[1]]),demand_before=clock(deadline),demand_after=clock(deadline+1000))
        for event_name,primary_name,i in (('dequeue_invocation','dequeue_invocation',2),('dequeue_observation','dequeue_linearization',4),
                ('dequeue_completion','dequeue_completion',6),('action_completion','consumer_action_completion',8)):
            event[event_name]=clock(c[i+1]);primary[primary_name]=dict(absolute_nanoseconds=c[i],relative_picoseconds=c[i+1])
        event['primary']=primary;p['consumer_current']=event
        path=self.root/p['demand']['file_name'];data=bytearray(path.read_bytes())
        struct.pack_into('<Q',data,p['demand_vectors'][3]['offset_bytes'],deadline-(k['phase_origin']+6000))
        path.write_bytes(data);p['demand'].update(binding(path))
        result=v.validate_phase(self.root,p,w,d,**k)
        self.assertFalse(result.capacity_limited)

    def test_affinity_prefix_and_tls_missing_observations_fail_closed(self):
        observed=thread(101,64);observed['affinity_mask']=[0,1]
        with self.assertRaisesRegex(v.ValidationError,'prefix'):v.validate_thread(observed,64,101)
        c,f,r,m,h=capture_fixture(self.root,self.cap)
        for name,value in (('loader_adds',None),('loader_subs',None),('visited_objects',0)):
            with self.subTest(name=name):
                bad=copy.deepcopy(c)
                for i in (0,2):bad['tls_snapshots'][i][name]=value
                with self.assertRaises(v.ValidationError):v.validate_tls(bad,bad['regions'],r,[101,102,103])
        c['tls_snapshots'][0]['modules'][0]['module_id']=0
        with self.assertRaises(v.ValidationError):v.validate_tls(c,c['regions'],r,[101,102,103])

    def test_drain_cannot_precede_after_phase_observations(self):
        c,f,r,m,h=capture_fixture(self.root,self.cap)
        for row in c['residency']:
            if row['request']['phase']==1 and row['request']['moment']==2:
                for field in ('begin','end'):
                    tick=row[field]['relative_picoseconds']+500000
                    row[field]=clock(tick)
        with self.assertRaisesRegex(v.ValidationError,'drain began before AFTER'):
            v.validate_capture(self.root,c,f,self.cap,r,m,h)

    def test_raw_integrity_counts_drain_and_boundaries(self):
        for change in ('hash','count','offset','checksum','drain','deadline','bool','row','padding','demand','issue','zero','sub_ns','last_clock','current_clock','drain_clock','cursor','wrong_cursor'):
            with self.subTest(change=change):
                p,w,d,k=raw_phase(self.root,self.cap)
                if change=='hash':(self.root/p['producer']['file_name']).write_bytes(b'bad')
                elif change=='count':p['producer_snapshot']['row_count']+=1
                elif change=='offset':p['demand_vectors'][1]['offset_bytes']+=8
                elif change=='checksum':p['checksum']^=1
                elif change=='drain':p['drain_rows'][0]['primary']['observed_record_index']^=1
                elif change=='deadline':w[0]['last_observed_tick']=k['phase_origin']
                elif change=='bool':p['demand_vectors'][0]['available']=1
                elif change=='last_clock':w[0]['last_attempt_before_status']=1
                elif change=='current_clock':p['producer_current']['capture']['failed_clock_status']=1
                elif change=='drain_clock':d['last_observed_tick']=0
                elif change=='cursor':d['final_audit'].update(producer_position=64,consumer_position=64)
                elif change=='wrong_cursor':d['final_audit'].update(producer_position=1,consumer_position=1)
                else:
                    target=p['demand'] if change in ('demand','issue','zero','sub_ns') else p['producer'];path=self.root/target['file_name'];data=bytearray(path.read_bytes())
                    if change=='padding':data[4+len(k['run_id'])]=1
                    elif change=='demand':data[:8]=struct.pack('<Q',999999)
                    elif change=='issue':struct.pack_into('<Q',data,p['demand_vectors'][1]['offset_bytes'],1)
                    elif change=='zero':struct.pack_into('<Q',data,p['demand_vectors'][2]['offset_bytes'],0)
                    elif change=='sub_ns':struct.pack_into('<Q',data,p['demand_vectors'][2]['offset_bytes'],1001)
                    else:
                        prefix=v.codec.row_layout(k['run_id'])[0];struct.pack_into('<Q',data,prefix+3*8,1)
                    path.write_bytes(data);target.update(binding(path))
                with self.assertRaises((v.ValidationError,v.codec.DecodeError)):v.validate_phase(self.root,p,w,d,**k)

    def test_control_mutants_cannot_hide_behind_success_flags(self):
        original=capture_fixture(self.root,self.cap)
        for change in ('cpu','msr','page','tls','cleanup','fault','stat','warmup','layout','smaps','synthetic','observed_origin','arena_seed','mapping_owner'):
            with self.subTest(change=change):
                c,f,r,m,h=copy.deepcopy(original)
                if change=='cpu':c['controls'][0]['workers'][0]['affinity_mask']=[3]
                elif change=='msr':c['controls'][2]['hardware']['cpus'][0]['raw_bytes'][0]=1
                elif change=='page':c['residency'][0]['page_status'][0]=1
                elif change=='tls':c['tls_snapshots'][0]['modules'][0]['address']=0
                elif change=='cleanup':f['core_mapping']['unmap']=call(-1)
                elif change=='fault':c['controls'][1]['workers'][0]['stat_after']['minor_faults']=11
                elif change=='stat':c['controls'][0]['workers'][0]['stat_before_read']['raw_bytes'][-1]=0
                elif change=='warmup':c['session']['warmup'][0]['stop']=1;f['session']=copy.deepcopy(c['session'])
                elif change=='layout':c['regions'][0]['bytes']+=4096
                elif change=='synthetic':c['synthetic']=True
                elif change=='observed_origin':c['session']['observed_origins'][0]+=1;f['session']=copy.deepcopy(c['session'])
                elif change=='arena_seed':c['arena']['ordered_index_sha256']='0'*64
                elif change=='mapping_owner':c['worker_mappings'][0]['before_touch']['thread_id']=call(103)
                else:c['environment_samples'][0]['raw_bytes'][-1]=0
                with self.assertRaises((v.ValidationError,v.environment.EnvironmentEvidenceError)):v.validate_capture(self.root,c,f,self.cap,r,m,h)

    def test_json_spools_drain_and_rejects_duplicate_and_unbounded_metadata(self):
        text='{"drain_rows":['+','.join('{"row":1}' for _ in range(1000))+'],"x":2}'
        with contextlib.ExitStack() as stack,patch.object(v,'MAX_JSON_NODES',20):
            result=v.JsonReader(io.StringIO(text),stack).document()
            self.assertIsInstance(result['drain_rows'],v.Spool)
            self.assertEqual(sum(row['row'] for row in result['drain_rows']),1000)
        for text in ('{"x":1,"x":2}','{"x":NaN}','{"x":1}junk'):
            with self.subTest(text=text),contextlib.ExitStack() as stack:
                with self.assertRaises((v.ValidationError,ValueError)):v.JsonReader(io.StringIO(text),stack).document()
        with contextlib.ExitStack() as stack,patch.object(v,'MAX_JSON_NODES',10):
            with self.assertRaisesRegex(v.ValidationError,'metadata'):
                v.JsonReader(io.StringIO('[0,0,0,0,0,0,0,0,0,0]'),stack).document()

    def test_full36_original_bindings_and_no_selective_selection(self):
        arguments=study_fixture(self.root)
        result=v.validate_retained_study(**arguments)
        self.assertEqual(len(result.captures),36)
        self.assertEqual(result.selection.state,v.selector.SelectionState.unresolved)
        self.assertFalse(result.execution_authority)
        self.assertEqual(result.formal_runs_contributed,0)
        self.assertTrue(all(not p[1].zero_loss for p in result.phase_counts))
        for change in ('missing','hash','duplicate','retry'):
            with self.subTest(change=change):
                bad=copy.deepcopy(arguments)
                if change=='missing':bad['action_inputs']['bound_documents'].pop()
                elif change=='hash':bad['action_inputs']['bound_documents'][0]['utf8_bytes']+='\n'
                elif change=='duplicate':
                    bad['action_inputs']['bound_documents'][0]['utf8_bytes']='{"x":1,"x":2}'
                else:bad['retention_report']['captures'].append(copy.deepcopy(bad['retention_report']['captures'][0]))
                with self.assertRaises(v.ValidationError):v.validate_retained_study(**bad)


class WholePlotReadbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)

    def rewrite_hardware(self, arguments, hardware):
        path=self.root/'studyhardware.json'
        path.write_bytes(v.registry.canonical(hardware))
        arguments['retention_report']['hardware_state']=binding(path)
        path=self.root/v.registry.REPORT_NAME
        path.write_bytes(v.registry.canonical(arguments['retention_report']))
        arguments['retention_binding']=binding(path)

    def test_native_action_shape_reproduces_v2_failure_and_v3_validates_full36(self):
        import stage17_discovery_validation_v2 as previous
        self.assertEqual(hashlib.sha256(pathlib.Path(previous.__file__).read_bytes()).hexdigest(),
                         'ada4fdce46c83366e7a86eb574f3364131fff496333599a6201223a2d15a3e68')
        arguments=study_fixture(self.root)
        with self.assertRaisesRegex(previous.ValidationError,'whole plot restore prestate: differs'):
            previous.validate_retained_study(**arguments)
        # Real byte/control validators run for every synthetic capture; no mocks.
        result=v.validate_retained_study(**arguments)
        self.assertEqual(len(result.captures),36)
        self.assertEqual(result.selection.state,v.selector.SelectionState.unresolved)
        self.assertFalse(result.execution_authority)
        self.assertEqual(result.formal_runs_contributed,0)

    def test_analysis_module_outside_qualified_root_uses_registry_schema(self):
        arguments=study_fixture(self.root)
        analysis=self.root/'separate-analysis';analysis.mkdir()
        path=analysis/'stage17_discovery_validation_v3.py'
        path.write_bytes(pathlib.Path(v.__file__).read_bytes())
        name='_d213_external_analysis_test'
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,{name:module}):
            spec.loader.exec_module(module)
            self.assertIs(module.registry,v.registry)
            self.assertFalse((path.parents[1]/v.registry.REPORT_SCHEMA).exists())
            result=module.validate_retained_study(**arguments)
        self.assertEqual(len(result.captures),36)
        self.assertFalse(result.execution_authority)

    def test_whole_plot_mutants_rejected_before_capture_validation_or_selection(self):
        arguments=study_fixture(self.root)
        original=json.loads((self.root/'studyhardware.json').read_bytes())
        changes=('h0_apply','h0_restore','h0_missing','h0_null','h0_restore_false',
                 'h1_apply_missing','h1_apply_extra','h1_apply_duplicate','h1_apply_order',
                 'h1_apply_value','h1_restore_missing','h1_restore_extra',
                 'h1_restore_duplicate','h1_restore_order','h1_restore_value',
                 'h1_restore_false','plot_missing','plot_extra','plot_order',
                 'study_restore_false')
        for change in changes:
            with self.subTest(change=change):
                hardware=copy.deepcopy(original)
                h0,h1=hardware['whole_plots']
                if change=='h0_apply':h0['apply_readback']=[copy.deepcopy(h1['restore_readback'][0])]
                elif change=='h0_restore':h0['restore_readback']=[copy.deepcopy(h1['restore_readback'][0])]
                elif change=='h0_missing':del h0['apply_readback']
                elif change=='h0_null':h0['restore_readback']=None
                elif change=='h0_restore_false':h0['restoration_verified']=False
                elif change=='h1_restore_false':h1['restoration_verified']=False
                elif change=='plot_missing':hardware['whole_plots'].pop()
                elif change=='plot_extra':hardware['whole_plots'].append(copy.deepcopy(h1))
                elif change=='plot_order':hardware['whole_plots'].reverse()
                elif change=='study_restore_false':hardware['restoration_verified']=False
                else:
                    _,operation,mutation=change.split('_')
                    rows=h1[operation+'_readback']
                    if mutation=='missing':rows.pop()
                    elif mutation=='extra':rows.append(copy.deepcopy(rows[0]))
                    elif mutation=='duplicate':rows[1]=copy.deepcopy(rows[0])
                    elif mutation=='order':rows.reverse()
                    elif mutation=='value':rows[0]['complete_value_hex']='000000000000001f'
                self.rewrite_hardware(arguments,hardware)
                with patch.object(v,'validate_capture') as capture,patch.object(v.selector,'select_duration') as select:
                    with self.assertRaises(v.ValidationError):v.validate_retained_study(**arguments)
                    capture.assert_not_called();select.assert_not_called()

    def test_every_phase_moment_and_cpu_still_requires_actual_msr_read(self):
        plan=v.contract.validate_plan(plans.fixture())
        for state in ('H0','H1'):
            cap=next(c for c in plan.captures if c.hardware_state==state)
            cap=dataclasses.replace(cap,geometry=dataclasses.replace(cap.geometry,capacity=64),
                budget=dataclasses.replace(cap.budget,warmup_attempt_capacity=8,measurement_attempt_capacity=8))
            original=capture_fixture(self.root,cap)
            # Exercise both full capture positives, not just the whole-plot log.
            c,f,r,m,h=original
            v.validate_capture(self.root,c,f,cap,r,m,h)
            for group in range(6):
                for cpu in range(3):
                    with self.subTest(state=state,group=group,cpu=cpu):
                        c,f,r,m,h=copy.deepcopy(original)
                        c['controls'][group]['hardware']['cpus'][cpu]['raw_bytes'][0]^=1
                        with self.assertRaisesRegex(v.ValidationError,'raw MSR readback'):
                            v.validate_controls(c,f,cap,r,m,h)
            for change in ('missing_group','missing_cpu','duplicate_cpu','cpu_order',
                           'short_read','short_bytes','observed','expected','matches','state','mapping'):
                with self.subTest(state=state,change=change):
                    c,f,r,m,h=copy.deepcopy(original)
                    hardware=c['controls'][0]['hardware'];row=hardware['cpus'][0]
                    if change=='missing_group':c['controls'].pop()
                    elif change=='missing_cpu':hardware['cpus'].pop()
                    elif change=='duplicate_cpu':hardware['cpus'][1]=copy.deepcopy(row)
                    elif change=='cpu_order':hardware['cpus'].reverse()
                    elif change=='short_read':row['read']['return_value']=7
                    elif change=='short_bytes':row['raw_bytes'].pop()
                    elif change=='observed':row['observed_value']^=1
                    elif change=='expected':row['expected_value']^=1
                    elif change=='matches':row['matches']=False
                    elif change=='state':hardware['requested_state']^=1
                    elif change=='mapping':hardware['mapping_id']='wrong'
                    with self.assertRaises(v.ValidationError):v.validate_controls(c,f,cap,r,m,h)


class PackedMetadataV3Tests(metadata_fixture.PackedMetadataTests):
    def setUp(self):
        # Reuse the original six parser regressions against the successor,
        # without changing any historical test or validator module bytes.
        self.validator=patch.object(metadata_fixture,'v',v)
        self.validator.start();self.addCleanup(self.validator.stop)


if __name__=='__main__':unittest.main()
