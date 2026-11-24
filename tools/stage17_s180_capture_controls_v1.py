"""Independent retained S180 lifecycle, nine-region and cleanup checks.

Caller authenticates original artifacts and admitted prospective input first.
No hardware access, raw-row join, source reconstruction, publication or authority.
Native success flags never substitute for retained control/page/syscall evidence.
"""
from __future__ import annotations
import hashlib
import time
from types import SimpleNamespace

import stage17_discovery_validation_v3 as common
import stage17_raw_stream_decoder_v2 as raw
from stage17_formal_archive_v1 import canonical

SCHEMA='cpu-prefetch-stage17-s180-capture-controls-validation/1'
CONTROL='cpu-prefetch-stage17-s180-capture-control/1'
METHOD='STAGE17-PILOT-S180-DESCRIPTIVE-v1'
SCOPE='PRIVATE_CAPTURE_ONLY_SHARED_DATA_REMAINS_FAMILY_OWNED'
require,exact,uint=common.require,common.exact,common.uint
ValidationError=common.ValidationError


def _hash(value):return hashlib.sha256(canonical(value)).hexdigest()


def _uncleaned(mapping):
    exact(mapping['cleanup_attempted'],False,'mapping still live at publication')
    exact(mapping['unlock'],None,'live mapping not unlocked')
    exact(mapping['unmap'],None,'live mapping not unmapped')


def _session(control,final,capture,phases):
    exact(control['schema_version'],CONTROL,'S180 control schema')
    exact(control['method_id'],METHOD,'S180 method')
    exact(control['execution_ordinal'],capture['execution_ordinal'],'execution order')
    exact(control['prospective_capture'],{k:v for k,v in capture.items() if k!='schedules'},'exact prospective capture')
    exact(control['completion_rule'],'SCHEDULE-ONCE-IMMEDIATE-FINISHED-NORMAL-DRAIN-D036-v1','scheduled completion rule')
    for flag in ('execution_authority','inferential_validity_established',
            'repeated_temporal_block_covariance_claim','phase18_authority'):
        exact(control[flag],False,'native metadata grants no '+flag)
    require(type(phases) is list and len(phases)==2,'two admitted phase bounds required')
    exact(capture['warmup_ns'],5000000000,'approved warmup')
    exact(capture['measurement_ns'],1000000000,'approved measurement')
    pre=control['native_result_before_publication_returns']
    for value in (pre,final):
        exact(value['stop'],14,'native capture complete')
        exact(value['cleanup_scope'],SCOPE,'private-only native cleanup scope')
        exact(value['publication_attempted'],True,'publication entered')
    exact(pre['publication_succeeded'],False,'callback has not returned')
    exact(pre['worker_mappings'],None,'returned worker mappings not yet captured')
    exact(pre['worker_stacks'],None,'returned worker stacks not yet captured')
    exact(final['publication_succeeded'],True,'callback returned successfully')
    exact(final['clock_origin'],pre['clock_origin'],'unchanged native clock origin')
    exact(final['session'],pre['session'],'unchanged actual S180 session')
    exact(pre['clock_origin']['status'],0,'native clock origin status')
    origin=uint(pre['clock_origin']['absolute_nanoseconds'],'native clock origin')
    pilot=pre['session'];exact(pilot['initial_queue_reset'],True,'initial family queue reset')
    scheduled=pilot['scheduled'];session=scheduled['lifecycle']
    exact(session['clock_origin'],dict(absolute_nanoseconds=origin),'session clock origin')
    exact(session['stop'],1,'successful lifecycle')
    exact(session['prepared'],[True,True],'both owners prepared')
    exact(session['private_reset'],[True,True],'both owners private reset')
    exact(session['queue_reset'],True,'actual interphase queue reset')
    require(len(session['phases'])==2 and len(scheduled['schedules'])==2,'two actual phases/schedules')
    windows=[];checkpoint=None
    for i,(state,bound) in enumerate(zip(session['phases'],phases,strict=True)):
        sample=raw._object(state['origin_sample'],'absolute_nanoseconds relative_picoseconds','actual origin')
        raw._clock_pair(sample['absolute_nanoseconds'],sample['relative_picoseconds'],origin,'actual phase origin')
        begin=sample['relative_picoseconds'];duration=capture['warmup_ns' if i==0 else 'measurement_ns']*1000
        exact(state['origin_status'],0,'phase origin status');exact(state['observed_origin'],begin,'actual released origin')
        drain=uint(bound['drain_duration_ticks'],'admitted drain duration')
        require(drain>0 and begin+duration+drain<=raw.MAX_U64,'finite nonoverflowing drain')
        require(origin+(begin+duration+drain+999)//1000<=raw.MAX_U64,'absolute drain endpoint overflows')
        expected=dict(origin_ticks=begin,duration_ticks=duration,producer_deadline_ticks=begin+duration,
            drain_deadline_ticks=begin+duration+drain)
        exact(state['window'],expected,'actual/admitted phase window')
        if checkpoint is not None:require(begin>=checkpoint,'measurement before warmup checkpoint')
        for name in ('released','before_observed','during_observed','after_observed','validated'):
            exact(state[name],True,'phase '+name)
        producer,consumer=state['producer'],state['consumer']
        exact(producer['arrivals_finished_published'],True,'immediate arrivals-finished publication')
        exact(consumer['drained'],True,'normal terminal drain')
        for owner,names in ((producer,('attempted','accepted','full')),
                (consumer,('polls','consumed_including_drain','empty'))):
            exact(owner['last_clock_status'],0,'last owner clock status')
            tick=uint(owner['last_observed_tick'],'last owner tick')
            require(begin<=tick<expected['drain_deadline_ticks'],'owner completion outside phase/drain')
            for name in names:uint(owner[name],name)
        exact(producer['attempted'],producer['accepted']+producer['full'],'producer count equation')
        exact(producer['attempted'],bound['offered_count'],'all offered arrivals attempted')
        exact(consumer['consumed_including_drain'],producer['accepted'],'full drain count')
        exact(consumer['polls'],consumer['consumed_including_drain']+consumer['empty'],'consumer count equation')
        require(consumer['empty']>=1,'terminal EMPTY observation required')
        require(producer['attempted']<=uint(bound['producer_attempt_limit'],'attempt limit')
            and consumer['polls']<=uint(bound['consumer_poll_limit'],'poll limit'),'frozen watchdog exceeded')
        exact(producer['deadline_reached'],producer['last_observed_tick']>=begin+duration,'literal horizon observation')
        source=scheduled['schedules'][i]
        for name,key in (('offered','offered_count'),('source_origin_ticks','source_origin_ticks'),
                ('source_horizon_ticks','source_horizon_ticks')):
            exact(source[name],bound[key],'native schedule '+name)
        require(bound['source_horizon_ticks']-bound['source_origin_ticks']==duration,'admitted source horizon differs')
        exact(source['mapped_schedule_validated'],True,'native mapped schedule validation')
        exact(source['all_arrivals_attempted'],True,'native schedule completed')
        uint(source['producer_wait_polls'],'native source waiting polls')
        completion=common.clock(source['producer_completion'],origin,'scheduled producer completion')
        exact(completion,producer['last_observed_tick'],'same scheduled producer completion sample')
        if bound['offered_count']:
            require(begin<=uint(source['mapped_last_deadline'],'last mapped deadline')<begin+duration,'mapped last deadline outside phase')
        else:exact(source['mapped_last_deadline'],None,'empty schedule has no last deadline')
        checkpoint=common.clock(state['drain_checkpoint'],origin,'drain checkpoint')
        require(checkpoint>=max(producer['last_observed_tick'],consumer['last_observed_tick']),
            'checkpoint precedes owner completion')
        window=dict(clock_suite_id=raw.CLOCK_SUITE_ID,time_unit=raw.TIME_UNIT,ticks_per_second=raw.TICKS_PER_SECOND,
            clock_origin_absolute_nanoseconds=origin,measurement_origin=dict(sample),duration_ticks=duration)
        raw.validate_measurement_window(window)
        windows.append(window)
    return pre,session,windows,scheduled['schedules']


def _shared(control,capture,resources,cleanup):
    shared=control['shared_data'];g=capture['requested_geometry']
    exact(shared['available'],True,'shared data available')
    exact(shared['stable_identity'],True,'native persistent identity')
    exact(shared['lifetime'],'ENTIRE_FAMILY_NOT_PER_CAPTURE','shared lifetime')
    exact(shared['final_family_cleanup_observed'],False,'publication precedes family cleanup')
    for name in ('placement','working_set_class','arena_namespace','node_order_namespace'):
        exact(shared[name],capture[name],'shared '+name)
    mappings=shared['mappings'];require(len(mappings)==2,'two persistent mappings')
    raw._object(cleanup,'records queues','actual family context cleanup')
    regions=[];tids=[]
    for i,(mapping,name) in enumerate(zip(mappings,('records','queues'),strict=True)):
        _uncleaned(mapping)
        plan=dict(bytes=resources['region_bytes'][7+i],verified_base_page_bytes=g['base_page_bytes'],
            owner_cpu=g['producer_cpu'],requested_node=g['shared_node'])
        region,tid=common.validate_mapping(mapping,plan,readonly=i==0)
        after,after_tid=common.validate_mapping(cleanup[name],plan,readonly=i==0,cleanup=True)
        exact(region,after,'family cleanup mapping identity');exact(tid,after_tid,'family cleanup owner')
        strip=lambda value:{k:v for k,v in value.items() if k not in ('cleanup_attempted','unlock','unmap')}
        exact(strip(cleanup[name]),strip(mapping),'unchanged shared preparation through family release')
        regions.append(region);tids.append(tid)
    exact(tids[0],tids[1],'persistent mapping first-touch owner')
    queues=regions[1];line=g['cache_line_bytes']
    objects=[]
    for name in ('arena_object','ring_object','linked_object','node_bytes'):
        address=uint(shared[name],'shared '+name)
        require(address%line==0 and queues['address']<=address<queues['address']+queues['bytes'],
            'shared object escapes observed queue mapping')
        objects.append(address)
    require(len(set(objects))==4,'shared objects alias')
    require(shared['node_bytes']+(g['capacity']+1)*line<=queues['address']+queues['bytes'],
        'node storage escapes observed queue mapping')
    return regions,shared


def validate_capture_controls(control,final,*,capture,resources,monitoring,hardware_control,
                              expected_layout,phase_bounds,family_context_cleanup,deadline_ns):
    """Validate actual phases, all54 observations and later shared release.

    Original source/arena hashes, rows, node permutation and complete180-run
    custody/identity lineage remain mandatory independent outer checks.
    """
    try:
        require(type(deadline_ns) is int and time.monotonic_ns()<deadline_ns,'original analysis deadline expired')
        pre,session,windows,schedules=_session(control,final,capture,phase_bounds)
        original_resources=resources;original_monitoring=monitoring;original_hardware=hardware_control
        raw._object(resources,'workers controller_stack tls_module_capacity thread_stat_bytes thread_status_bytes '
            'thread_affinity_words initial_consumer_state phase_capacity','S180 native resource input')
        raw._object(hardware_control,'identity prestate software_prefetch_mapping_id','S180 native hardware input')
        exact(hardware_control['identity'],dict(family=6,model=62),'approved stand identity')
        exact(hardware_control['software_prefetch_mapping_id'],'X86-64-PREFETCHT0-ONLY-v1','approved stand emitter mapping')
        prestate=[]
        for row in hardware_control['prestate']:
            raw._object(row,'cpu value','actual admitted MSR prestate')
            cpu=uint(row['cpu'],'prestate CPU');value=uint(row['value'],'full MSR prestate')
            prestate.append(dict(cpu=cpu,complete_value_hex=f'{value:016x}'))
        hardware_control=dict(mapping_id='INTEL-06_3EH-MSR-1A4-DISABLE-0_3-v1',prestate=prestate)
        monitoring=dict(monitoring,hardware_identity=original_hardware['identity'])
        layout_fields=('core_bytes','monitor_bytes','total_mapping_bytes','region_bytes')
        resources=dict(resources,**{k:expected_layout[k] for k in layout_fields})
        workers=expected_layout['workers']
        expected_workers={k:v for k,v in workers.items() if k!='phases'}
        expected_workers['phases']=[dict(producer_object=p['producer_object'],consumer_object=p['consumer_object'],
            producer_raw=p['producer_raw'],consumer_raw=p['consumer_raw'],
            producer_raw_bytes=p['raw']['producer_bytes'],consumer_raw_bytes=p['raw']['consumer_bytes']) for p in workers['phases']]
        exact(control['layout']['workers'],expected_workers,'exact cold/native private layout')
        g=capture['requested_geometry'];page=uint(g['base_page_bytes'],'verified page bytes')
        require(page>0 and page&(page-1)==0,'power-of-two explicit page geometry')
        line=uint(g['cache_line_bytes'],'explicit cache line bytes');capacity=uint(g['capacity'],'explicit capacity')
        require(64<=line<=page and line&(line-1)==0 and 8<=capacity<=1048576,'approved bounded record geometry')
        require(capture['requested_hardware_state'] in ('H0','H1'),'explicit requested hardware state')
        for role in ('producer','consumer'):
            stack=resources['workers'][role+'_stack']
            exact(stack['owner_cpu'],g[role+'_cpu'],'admitted stack owner CPU')
            exact(stack['requested_node'],g[role+'_node'],'admitted stack home')
            exact(stack['verified_base_page_bytes'],page,'admitted stack page geometry')
        require(len(resources['phase_capacity'])==2,'two admitted raw-capacity pairs')
        for capacities,bound in zip(resources['phase_capacity'],phase_bounds,strict=True):
            attempts=uint(bound['producer_attempt_limit'],'attempt limit')
            require(attempts>0 and uint(bound['consumer_poll_limit'],'poll limit')>0,'finite positive phase watchdogs')
            for name in ('producer_primary_rows','consumer_primary_rows'):
                require(uint(capacities[name],'raw row capacity')>=attempts,'raw capacity below admitted attempt limit')
        require(type(resources['region_bytes']) is list and len(resources['region_bytes'])==9,'nine admitted region sizes')
        for size in resources['region_bytes']:require(uint(size,'region size')>0 and size%page==0,'region page extent')
        for name in ('during_first_page','during_page_count'):
            require(len(monitoring[name])==9,'nine admitted monitoring extents')
        for i,size in enumerate(resources['region_bytes']):
            first=uint(monitoring['during_first_page'][i],'first queried page')
            count=uint(monitoring['during_page_count'][i],'queried page count')
            require(count>0 and first+count<=size//page,'DURING pages escape region')
        require(0<=uint(monitoring['control_region_index'],'control attachment')<9,'control attachment outside regions')
        shared_regions,shared=_shared(control,capture,resources,family_context_cleanup)
        for mapping in (*control['worker_mappings'],*control['worker_stacks'],pre['controller_stack'],
                pre['core_mapping'],pre['monitor_mapping']):_uncleaned(mapping)
        equivalent=dict(origins=[w['measurement_origin']['relative_picoseconds'] for w in windows])
        for name,state in zip(('warmup','measurement'),session['phases'],strict=True):
            equivalent[name]=[state['producer'],state['consumer']]
        view=dict(control,session=equivalent)
        for name in ('controller_stack','core_mapping','monitor_mapping',
                'clock_origin','publication_attempted','publication_succeeded'):view[name]=pre[name]
        final_view=dict(final,session=equivalent)
        namespace=SimpleNamespace(geometry=SimpleNamespace(**g),measurement_ns=capture['measurement_ns'],
            hardware_state=capture['requested_hardware_state'])
        regions=common.validate_controls(view,final_view,namespace,resources,monitoring,hardware_control,
            s180_shared_regions=shared_regions)
        origin=pre['clock_origin']['absolute_nanoseconds']
        for i,state in enumerate(session['phases']):
            after=[common.clock(r['end'],origin,'AFTER query') for r in control['residency']
                if r['request']['phase']==i and r['request']['moment']==2]
            checkpoint=common.clock(state['drain_checkpoint'],origin,'checkpoint')
            require(checkpoint>=max(after),'checkpoint precedes completed nine-region AFTER observations')
            if i==0:
                following=[common.clock(r['begin'],origin,'measurement BEFORE') for r in control['residency']
                    if r['request']['phase']==1 and r['request']['moment']==0]
                require(min(following)>=checkpoint,'measurement monitoring before warmup checkpoint')
        require(time.monotonic_ns()<deadline_ns,'original analysis deadline expired')
        result=dict(schema_version=SCHEMA,execution_ordinal=capture['execution_ordinal'],run_id=capture['run_id'],
            prospective_capture_sha256=_hash(capture),
            original_control_and_checkpoint_custody='CALLER_AUTHENTICATES_ORIGINAL_ARTIFACT_BYTES',
            resources_sha256=_hash(original_resources),monitoring_sha256=_hash(original_monitoring),hardware_control_sha256=_hash(original_hardware),
            expected_layout_sha256=_hash(expected_layout),
            phase_bounds_sha256=_hash(phase_bounds),family_context_cleanup_sha256=_hash(family_context_cleanup),
            regions=regions,phase_windows=windows,shared_data=shared,
            capture_control_evidence_validated=True,private_cleanup_verified=True,shared_context_cleanup_verified=True,
            residency_observations_verified=54,environment_groups_verified=6,
            raw_reconciliation_performed=False,original_sources_verified=False,node_order_verified=False,
            immutable_arena_verified=False,complete_family_lineage_verified=False,run_validity_assessed=False,
            execution_authority=False,phase18_authority=False)
        require(time.monotonic_ns()<deadline_ns,'original analysis deadline expired')
        return result
    except ValidationError:raise
    except (KeyError,TypeError,ValueError,IndexError,OverflowError,raw.DecodeError) as error:
        raise ValidationError('S180 capture controls: '+str(error)) from error
