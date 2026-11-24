"""D229 independent Q16b/Q16c retained single-capture validation.

Authenticated original metadata is supplied by the caller. Read-only constant-row
joins preserve every primary row, including FULL and excluded drain completions.
No joined file, inference, family acceptance, authority or successful evidence is
manufactured. Existing D220 observation/arena/file identity checks are reused.
"""
from __future__ import annotations
from contextlib import ExitStack
import array
import json
import os
import pathlib
import re
import struct
from jsonschema import Draft202012Validator
import stage17_q16a_capture_validation_v1 as d210
import stage17_formal_plan_v1 as plans

common, raw, codec = d210.common, d210.raw, d210.codec
ValidationError = common.ValidationError
require, exact, uint = common.require, common.exact, common.uint
PHASES, ROLES = d210.PHASES, d210.ROLES
SCHEMA_ID = 'cpu-prefetch-stage17-formal-service-capture-validation/1'
SOURCE_VERSIONS = dict(raw_format=codec.FORMAT_ID, raw_codec='stage17_raw_stream_decoder_v1',
    clock=raw.CLOCK_SUITE_ID, clock_window='stage17_raw_stream_decoder_v2',
    common_capture='stage17_q16a_capture_validation_v1', common_controls='stage17_discovery_validation_v3',
    input_contract='stage17_formal_plan_v1')
CONTROL_IDS = {'Q16b':'cpu-prefetch-stage17-formal-service-control/1',
               'Q16c':'cpu-prefetch-stage17-formal-scheduled-control/1'}
RULES = {'Q16b':'CONSUMER-ACTION-COMPLETION-HALF-OPEN-D211-v1',
         'Q16c':'SCHEDULE-ONCE-IMMEDIATE-FINISHED-NORMAL-DRAIN-D036-v1'}

def _input(capture, resources, monitoring, action):
    schema = plans.ROOT / plans.NATIVE_SCHEMA[action]
    validator = Draft202012Validator(json.loads(schema.read_bytes()))
    errors = validator.iter_errors(dict(capture=capture, resources=resources, monitoring=monitoring))
    first = next(errors, None)
    require(first is None, 'formal native input shape: ' + (first.message if first else ''))
    # JSON Schema integers include integral floats; the wire contract does not.
    def integers(value):
        require(not isinstance(value, float), 'floating-point native input')
        if isinstance(value, dict):
            for item in value.values(): integers(item)
        elif isinstance(value, list):
            for item in value: integers(item)
    integers(dict(capture=capture, resources=resources, monitoring=monitoring))
    exact(resources['ordinal'], capture['ordinal'], 'resource ordinal')
    exact(monitoring['ordinal'], capture['ordinal'], 'monitor ordinal')
    cell = capture['cell_ordinal'] // (3 if action == 'Q16c' else 1)
    context = cell % 12
    exact(capture['package'], plans.PACKAGES[cell//12], 'package identity')
    plans._package(capture, 'capture')
    if action == 'Q16c':
        exact(capture['load_level'], plans.LOADS[capture['cell_ordinal'] % 3], 'load identity')
        plans._schedules(capture, 'capture')
    identity = monitoring['hardware_identity']
    mapping = {(6, 85):'X86-64-PREFETCHW-PREFETCHT0-v1', (6, 62):'X86-64-PREFETCHT0-ONLY-v1'}
    exact(capture['software_prefetch_mapping_id'], mapping.get((identity['family'],identity['model'])), 'accepted software mapping')
    exact(capture['hardware_state'], 'H0' if context < 6 else 'H1', 'context state')
    exact(capture['placement'], 'NEAR' if context // 3 % 2 == 0 else 'FAR', 'context placement')
    exact(capture['working_set_class'], ('L2_RESIDENT','LLC_RESIDENT','BEYOND_LLC')[context % 3], 'context class')
    exact(capture['arena_seed'], capture['measurement'], 'persistent measurement arena')
    for name in ('run_id','seed_id','namespace_id','seed_hex'):
        require(capture['warmup'][name] != capture['measurement'][name], 'reused phase ' + name)
    for phase in PHASES:
        for name in ('run_id','seed_id','namespace_id'):
            require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', capture[phase][name]) is not None,
                    'opaque phase identity')
        require(re.fullmatch(r'[0-9a-f]{64}', capture[phase]['seed_hex']) is not None, 'canonical seed')
    g = capture['geometry']
    require(64 <= g['cache_line_bytes'] <= g['base_page_bytes'] and
            all(value & (value-1) == 0 for value in (g['cache_line_bytes'], g['base_page_bytes'])),
            'native line/page geometry')
    for role in ROLES:
        stack = resources['workers'][role + '_stack']
        exact(stack['owner_cpu'], g[role + '_cpu'], 'worker CPU')
        exact(stack['requested_node'], g[role + '_node'], 'worker node')
        exact(stack['verified_base_page_bytes'], g['base_page_bytes'], 'worker page size')
    require(len({g['producer_cpu'], g['consumer_cpu'], resources['controller_stack']['owner_cpu']}) == 3,
            'owner CPU collision')
    exact(g['shared_node'], g['producer_node'], 'shared owner node')
    exact(g['producer_node'] == g['consumer_node'], capture['placement'] == 'NEAR', 'placement geometry')
    exact(resources['controller_stack']['verified_base_page_bytes'], g['base_page_bytes'], 'controller page size')
    require(resources['total_mapping_bytes'] <= capture['budget']['memory_bytes'], 'mapping memory ceiling')
    exact(resources['total_mapping_bytes'], sum(resources['region_bytes']) + resources['monitor_bytes'] + 3*g['base_page_bytes'],
          'total mapping including guards')
    for i, bound in enumerate(capture['budget']['phases']):
        capacity = resources['phase_capacity'][i]
        for name in ('producer_primary_rows','consumer_primary_rows'):
            require(capacity[name] >= bound['producer_attempt_limit'], 'uncovered producer bound')
        require(bound['consumer_poll_limit'] > 0 and bound['drain_ns'] > 0, 'finite phase bounds')
    for i, bound in enumerate(capture['budget']['phases']):
        duration = capture['warmup_ns' if i == 0 else 'measurement_ns'] * 1000
        require(duration <= raw.MAX_U64 and bound['drain_ns']*1000 <= raw.MAX_U64, 'phase tick overflow')
        require(monitoring['during_offset_ticks'][i] < duration, 'monitoring offset outside horizon')

def _session(control, final, capture, action):
    exact(control['schema_version'], CONTROL_IDS[action], 'formal control schema')
    exact(control['method_id'], plans.METHOD[action], 'formal method')
    exact(control['capture_ordinal'], capture['ordinal'], 'capture ordinal')
    exact(control['completion_rule'], RULES[action], 'completion rule')
    for flag in ('execution_authority','inferential_validity_established','phase18_authority'):
        exact(control[flag], False, 'publisher grants no ' + flag)
    pre = control['native_result_before_publication_returns']
    exact(pre['stop'], 14, 'native complete before publication')
    exact(final['stop'], 14, 'native complete after cleanup')
    exact(pre['publication_attempted'], True, 'publication entered')
    exact(pre['publication_succeeded'], False, 'publication has not returned')
    exact(final['publication_attempted'], True, 'final publication attempted')
    exact(final['publication_succeeded'], True, 'final publication succeeded')
    exact(final['session'], pre['session'], 'unchanged actual session')
    session = pre['session']['lifecycle'] if action == 'Q16c' else pre['session']
    exact(final['clock_origin'], pre['clock_origin'], 'unchanged native clock origin')
    exact(pre['clock_origin']['status'], 0, 'native origin status')
    origin = uint(pre['clock_origin']['absolute_nanoseconds'], 'native clock origin')
    exact(session['clock_origin'], dict(absolute_nanoseconds=origin), 'session clock origin')
    exact(session['stop'], 1, 'mandatory successful service session')
    exact(session['prepared'], [True, True], 'actual owner preparation')
    exact(session['private_reset'], [True, True], 'actual private reset')
    exact(session['queue_reset'], True, 'actual queue reset')
    require(len(session['phases']) == 2, 'two session phases')
    windows = []
    previous_checkpoint = None
    for i, phase in enumerate(session['phases']):
        exact(phase['origin_status'], 0, 'phase origin status')
        sample = raw._object(phase['origin_sample'], 'absolute_nanoseconds relative_picoseconds', 'phase origin sample')
        raw._clock_pair(sample['absolute_nanoseconds'], sample['relative_picoseconds'], origin, 'phase origin')
        begin = sample['relative_picoseconds']
        exact(phase['observed_origin'], begin, 'observed phase origin')
        duration = capture['warmup_ns' if i == 0 else 'measurement_ns'] * 1000
        drain = capture['budget']['phases'][i]['drain_ns'] * 1000
        require(duration <= raw.MAX_U64 - begin and drain <= raw.MAX_U64 - begin - duration, 'phase deadline overflow')
        window = dict(origin_ticks=begin, duration_ticks=duration, producer_deadline_ticks=begin+duration,
                      drain_deadline_ticks=begin+duration+drain)
        exact(phase['window'], window, 'prospective actual phase window')
        if previous_checkpoint is not None:
            require(begin >= previous_checkpoint, 'measurement precedes completed warmup checkpoint')
        for flag in ('released','before_observed','during_observed','after_observed','validated'):
            exact(phase[flag], True, 'phase ' + flag)
        producer, consumer = phase['producer'], phase['consumer']
        exact(producer['arrivals_finished_published'], True, 'immediate arrivals finished')
        if action == 'Q16b':
            exact(producer['deadline_reached'], True, 'service deadline reached')
        exact(consumer['drained'], True, 'terminal queue drain')
        for owner in (producer, consumer):
            exact(owner['last_clock_status'], 0, 'owner final clock status')
            require(uint(owner['last_observed_tick'], 'owner last tick') >= begin, 'owner clock before phase')
        if action == 'Q16b':
            require(producer['last_observed_tick'] >= begin+duration, 'producer stopped before horizon')
            require(consumer['last_observed_tick'] >= begin+duration, 'service consumer stopped before horizon')
        require(consumer['last_observed_tick'] < window['drain_deadline_ticks'], 'consumer drain deadline')
        checkpoint = common.clock(phase['drain_checkpoint'], origin, 'cold drain checkpoint')
        require(checkpoint >= max(producer['last_observed_tick'], consumer['last_observed_tick']), 'checkpoint before owner completion')
        previous_checkpoint = checkpoint
        for owner, names in ((producer, ('attempted','accepted','full')),
                             (consumer, ('polls','consumed_including_drain','empty'))):
            for name in names: uint(owner[name], name)
        exact(producer['attempted'], producer['accepted'] + producer['full'], 'producer counts')
        exact(consumer['polls'], consumer['consumed_including_drain'] + consumer['empty'], 'consumer counts')
        exact(consumer['consumed_including_drain'], producer['accepted'], 'full drain count')
        bound = capture['budget']['phases'][i]
        require(producer['attempted'] <= bound['producer_attempt_limit'] and consumer['polls'] <= bound['consumer_poll_limit'],
                'actual phase exceeds frozen watchdog')
        exact_window = dict(clock_suite_id=raw.CLOCK_SUITE_ID, time_unit=raw.TIME_UNIT,
            ticks_per_second=raw.TICKS_PER_SECOND, clock_origin_absolute_nanoseconds=origin,
            measurement_origin=dict(sample), duration_ticks=duration)
        raw.validate_measurement_window(exact_window)
        windows.append(dict(clock_suite_id=raw.CLOCK_SUITE_ID, time_unit=raw.TIME_UNIT,
            ticks_per_second=raw.TICKS_PER_SECOND, clock_origin_absolute_nanoseconds=origin,
            phase_origin=dict(sample), duration_ticks=duration))
    return pre, session, windows

def _binding(artifact, role, schema, count, row_bytes):
    raw._object(artifact, 'file_name role schema_identity size_bytes sha256', 'artifact reference')
    exact(artifact['role'], role, 'artifact role')
    exact(artifact['schema_identity'], schema, 'artifact format')
    return raw._binding(dict(path=artifact['file_name'],size_bytes=artifact['size_bytes'],
                             sha256=artifact['sha256'],row_count=count),'artifact',row_bytes)


def _open(stack, root_fd, binding, seen, retained):
    stream = raw._open_stream(stack, root_fd, binding, 'formal raw')
    for identity in (('path',binding['path']),('inode',stream.before.st_dev,stream.before.st_ino)):
        require(identity not in seen, 'raw artifacts alias across roles/phases')
        seen.add(identity)
    retained.append((binding,d210._stamp(stream.before)))
    return stream


def _node_order(root, control, capture, action, seen, retained):
    linked = capture['package'] in ('L0','L1')
    count = capture['geometry']['capacity'] + 1 if linked else 0
    exact(control['node_order_count'], count, 'node order count')
    binding = _binding(control['node_order'], action.upper()+'_NODE_ORDER', 'NODEORDER-U64LE-v1', count, 8)
    # Arena replay already caps capacity*16. This additional packed permutation
    # is at most half that existing bound plus one uint64, never Python-int O(N).
    require(count <= common.MAX_ARENA_BYTES//16+1, 'unsupported node replay bound')
    expected = array.array('Q', range(count))
    if linked:
        plan = capture['linked_order']
        draws = common.draws(common.key(plan['seed_hex'],plan['namespace_id'],'node-order'))
        for remaining in range(count,1,-1):
            threshold = ((-remaining)&raw.MAX_U64)%remaining
            while True:
                value = next(draws)
                if value >= threshold: break
            selected=value%remaining
            expected[remaining-1],expected[selected]=expected[selected],expected[remaining-1]
    with ExitStack() as stack:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);stack.callback(os.close,fd)
        stream=_open(stack,fd,binding,seen,retained)
        for value in expected:
            actual=struct.unpack('<Q',codec._read_exact(stream,8,'node order'))[0]
            exact(actual,value,'deterministic node order')
        stream.finish()
    return dict(count=count,sha256=binding['sha256'])


def _schedule_mapping(control,capture,resources):
    mapping=raw._object(control['schedule_mapping'],'offsets counts','mapped schedule extents')
    require(len(mapping['offsets'])==len(mapping['counts'])==2,'two schedule extents')
    order=uint(control['layout']['workers']['record_order'],'record order offset')
    capacity=capture['geometry']['capacity']
    require(order>=capacity*capture['geometry']['cache_line_bytes'],'record order overlaps records')
    previous=order+capacity*8
    for index in range(2):
        offset=uint(mapping['offsets'][index],'schedule offset')
        count=capture['schedules'][index]['offered_count']
        exact(mapping['counts'][index],count,'mapped schedule count')
        require(offset%8==0 and offset>=previous and offset<=resources['region_bytes'][0]
                and count<=(resources['region_bytes'][0]-offset)//8,'schedule mapping extent/order')
        previous=offset+count*8


def _schedule(root, control, capture, index, window, seen, retained):
    source=capture['schedules'][index]; row=control['schedules'][index]
    exact(row['prospective'],{k:v for k,v in source.items() if k!='deadline_ticks'},'schedule provenance')
    exact(row['prepared_available'],True,'actual prepared schedule available')
    exact(row['prepared_count'],source['offered_count'],'prepared schedule count')
    exact(row['source_origin_ticks'],source['source_origin_ticks'],'prepared schedule origin')
    exact(row['source_horizon_ticks'],source['source_horizon_ticks'],'prepared schedule endpoint')
    exact(row['time_unit'],raw.TIME_UNIT,'source schedule unit')
    exact(row['coordinates'],'SOURCE_SCHEDULE_BEFORE_ACTUAL_ORIGIN_TRANSLATION','source coordinates')
    exact(row['phase_released'],True,'schedule phase actually released')
    exact(row['all_arrivals_attempted'],True,'all offered arrivals attempted')
    exact(row['attempted'],source['offered_count'],'source attempt count')
    binding=_binding(row['stream'],'Q16C_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1',source['offered_count'],8)
    with ExitStack() as stack:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);stack.callback(os.close,fd)
        stream=_open(stack,fd,binding,seen,retained)
        for expected in source['deadline_ticks']:
            actual=struct.unpack('<Q',codec._read_exact(stream,8,'source schedule'))[0]
            exact(actual,expected,'actual mapped source differs from admitted schedule')
        stream.finish()
    native=control['native_result_before_publication_returns']['session']['schedules'][index]
    for name in ('offered','source_origin_ticks','source_horizon_ticks'):
        exact(native[name],source['offered_count' if name=='offered' else name],'native schedule '+name)
    exact(native['mapped_schedule_validated'],True,'native mapped schedule checked')
    exact(native['all_arrivals_attempted'],True,'native all arrivals attempted')
    uint(native['producer_wait_polls'],'schedule waiting polls')
    begin=window['phase_origin']['relative_picoseconds']
    last=begin+source['deadline_ticks'][-1]-source['source_origin_ticks'] if source['offered_count'] else None
    exact(native['mapped_last_deadline'],last,'last mapped deadline')
    completion=common.clock(native['producer_completion'],window['clock_origin_absolute_nanoseconds'],'producer completion')
    state=control['native_result_before_publication_returns']['session']['lifecycle']['phases'][index]
    exact(state['producer']['last_observed_tick'],completion,'actual producer completion sample')
    exact(state['producer']['deadline_reached'],completion>=begin+window['duration_ticks'],'literal horizon reached')
    require(begin<=completion<state['window']['drain_deadline_ticks'],'scheduled completion deadline')
    return dict(offered=source['offered_count'],source_sha256=binding['sha256'],
                actual_phase_origin_ticks=begin,source_origin_ticks=source['source_origin_ticks'])


def _primary_bindings(phase,capture,resources,index,action):
    run_id=capture[PHASES[index]]['run_id'];prefix,pb,cb,jb=codec.row_layout(run_id)
    layout=dict(run_id_bytes=len(run_id.encode()),prefix_bytes=prefix,producer_row_bytes=pb,
                consumer_row_bytes=cb,joined_row_bytes=jb)
    result={}
    for ordinal,role in enumerate(ROLES):
        exact(phase[role+'_available'],True,role+' available')
        exact(phase[role+'_stopped'],False,role+' capture complete')
        exact(phase[role+'_layout'],layout,role+' row layout')
        snapshot=phase[role+'_snapshot'];count=uint(snapshot['row_count'],'primary rows')
        capacity=resources['phase_capacity'][index][role+'_primary_rows'];row_bytes=pb if ordinal==0 else cb
        exact(snapshot,dict(run_id=run_id,row_count=count,row_capacity=capacity,row_bytes=row_bytes,
            completeness='SEALED_COMPLETE',overflowed=False,retained_bytes=count*row_bytes,stream_kind=ordinal),role+' snapshot')
        require(count<=capacity,'primary exceeds frozen capacity')
        # This is the last operation's append, not the last retained row's.
        # The mandatory terminal EMPTY poll resets the consumer optional.
        exact(phase[role+'_last_append'],0 if ordinal==0 and count else None,role+' append status')
        result[role]=_binding(phase[role],action.upper()+'_PRIMARY_RAW',codec.FORMAT_ID,count,row_bytes)
    return result


def _current(phase,last_p):
    p=phase['producer_current'];c=phase['consumer_current']
    if last_p is None:
        exact(p,None,'no fabricated producer current')
    else:
        exact(p['status'],0,'producer current complete');exact(p['failed_boundary'],None,'producer failure absent')
        exact(p['clock_status'],0,'producer current clock')
        values=dict(logical_sequence=last_p[0],record_index=last_p[1],scheduled_arrival=last_p[2],
                    outcome=0 if last_p[14]==codec.ACCEPTED_FLAGS else 1,
                    accepted_ordinal=last_p[13] if last_p[14]==codec.ACCEPTED_FLAGS else None)
        for name,off in (('producer_handle_begin',3),('record_lookup_completion',5),('enqueue_invocation',7),
                          ('enqueue_attempt_completion',11)):
            values[name]=dict(absolute_nanoseconds=last_p[off],relative_picoseconds=last_p[off+1])
        values['enqueue_linearization']=dict(absolute_nanoseconds=last_p[9],relative_picoseconds=last_p[10]) if last_p[14]==codec.ACCEPTED_FLAGS else None
        exact(p['observation'],values,'current producer raw crosscheck')
    # Legacy empty captures have no timestamps/observation. Do not fabricate one.
    exact(c,dict(status=1,failed_boundary=None,clock_status=0,record_status=0,observation=None),'terminal EMPTY current')


def _join_phase(root,phase,state,capture,resources,index,window,arena,action,seen,retained):
    bindings=_primary_bindings(phase,capture,resources,index,action)
    run_id=capture[PHASES[index]]['run_id'];_,pb,cb,_=codec.row_layout(run_id)
    origin=window['clock_origin_absolute_nanoseconds'];begin=window['phase_origin']['relative_picoseconds']
    end=begin+window['duration_ticks'];drain_end=state['window']['drain_deadline_ticks']
    accepted=full=interval=0;checksum=resources['initial_consumer_state'];previous_p=previous_c=begin;last_p=None
    with ExitStack() as stack:
        fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);stack.callback(os.close,fd)
        streams={role:_open(stack,fd,binding,seen,retained) for role,binding in bindings.items()}
        for logical in range(bindings['producer']['row_count']):
            p=codec._row(streams['producer'],pb,run_id,15,'producer primary');last_p=p
            require(p[0]==logical and p[14] in (codec.ACCEPTED_FLAGS,codec.FULL_FLAGS),'producer ordinal/flags')
            exact(p[1],arena.order[logical%len(arena.order)],'wrapped deterministic record index')
            for off in (3,5,7,11):raw._clock_pair(p[off],p[off+1],origin,'producer clock')
            require(begin<=p[2]<end and p[2]<=p[4]<=p[6]<=p[8]<=p[12]<drain_end and previous_p<=p[4],
                    'producer clocks/horizon/order')
            if action=='Q16c':
                source=capture['schedules'][index]
                require(logical<source['offered_count'],'attempt without offered arrival')
                exact(p[2],begin+source['deadline_ticks'][logical]-source['source_origin_ticks'],'actual due arrival mapping')
            else:
                require(previous_p<=p[2],'continuous-ready arrival precedes previous completion')
            previous_p=p[12]
            if p[14]==codec.FULL_FLAGS:
                require(p[9]==p[10]==p[13]==0,'FULL has accepted-only fields');full+=1;continue
            raw._clock_pair(p[9],p[10],origin,'publication clock')
            require(p[13]==accepted and p[8]<=p[10]<=p[12],'accepted ordinal/publication bracket')
            c=codec._row(streams['consumer'],cb,run_id,10,'consumer primary')
            require(c[0]==accepted and c[1]==p[1],'independent ordinal/record join')
            for off in (2,4,6,8):raw._clock_pair(c[off],c[off+1],origin,'consumer clock')
            require(previous_c<=c[3]<=c[5]<=c[7]<=c[9]<drain_end and p[10]<=c[5],'consumer order/publication/drain')
            checksum=common.mix(checksum,c[1],arena.payload[c[1]]);previous_c=c[9];accepted+=1
            interval+=begin<=c[9]<end
        for stream in streams.values():stream.finish()
    exact(bindings['consumer']['row_count'],accepted,'all consumer rows reconciled')
    counts=dict(attempted=accepted+full,accepted=accepted,full=full,consumed_including_drain=accepted)
    for name,key in (('requests','attempted'),('retained_attempts','attempted'),('accepted','accepted'),('full','full'),
                     ('retained_consumed_including_drain','consumed_including_drain')):
        exact(phase[name],counts[key],'retained '+name)
    for name in ('attempted','accepted','full'):exact(state['producer'][name],counts[name],'session '+name)
    exact(state['consumer']['consumed_including_drain'],accepted,'session consumed')
    for name in ('polls','empty'):exact(phase[name],state['consumer'][name],'consumer '+name)
    require(phase['empty']>=1 and phase['polls']==accepted+phase['empty'],'normal terminal drain counts')
    exact(phase['initial_checksum'],resources['initial_consumer_state'],'reset initial checksum')
    exact(phase['checksum'],checksum,'full drain checksum')
    exact(phase['consumer_last_join'],dict(status=1,matched=accepted,failed_producer_row=None),'native join independently checked')
    require(state['producer']['last_observed_tick']>=previous_p and state['consumer']['last_observed_tick']>=previous_c,
            'last owner clock precedes raw completion')
    _current(phase,last_p)
    result=dict(phase=PHASES[index],run_id=run_id,counts=counts,zero_loss=full==0,
                stream_sha256={role:b['sha256'] for role,b in bindings.items()})
    if action=='Q16b':
        if index==0:exact(phase['completion_interval'],None,'warmup has no service estimator')
        else:
            w=dict(window);w['measurement_origin']=w.pop('phase_origin')
            expected=dict(measurement_window=w,interval_end_ticks=end,consumed_count=accepted,
                          interval_consumed_count=interval,outside_interval_consumed_count=accepted-interval)
            exact(phase['completion_interval'],dict(status=0,failed_consumer_row=None,counts=expected),'independent D211 completion count')
            result['completion_interval']=dict(completion_counting_rule_id=raw.COUNTING_RULE_ID,**expected)
    else:
        require('completion_interval' not in phase,'scheduled capture must not apply D211 filtering')
        exact(counts['attempted'],capture['schedules'][index]['offered_count'],'one attempt per offered arrival')
        result['counts']['offered']=capture['schedules'][index]['offered_count']
    return result


def validate_capture(root,control,final,capture,resources,monitoring,hardware_control):
    """Validate one capture after caller authentication; invalid evidence raises.

    FULL and genuine zero service completions are retained, never retried. No
    schedule generation/source admission, family inference or release seal here.
    """
    try:
        versions={'cpu-prefetch-stage17-formal-service-capture/1':'Q16b',
                  'cpu-prefetch-stage17-formal-scheduled-capture/1':'Q16c'}
        action=versions[capture['schema_version']]
        _input(capture,resources,monitoring,action)
        pre,session,windows=_session(control,final,capture,action)
        regions=d210._common_controls(control,final,pre,session,capture,resources,monitoring,hardware_control)
        arena=d210._arena(control,capture,regions)
        require(len(control['phases'])==2,'two primary phases')
        seen=set();retained=[]
        nodes=_node_order(root,control,capture,action,seen,retained)
        schedules=None
        if action=='Q16c':
            _schedule_mapping(control,capture,resources)
            require(len(control['schedules'])==2 and len(pre['session']['schedules'])==2,'two prepared source schedules')
            schedules=[_schedule(root,control,capture,i,windows[i],seen,retained) for i in range(2)]
        phases=[_join_phase(root,control['phases'][i],session['phases'][i],capture,resources,i,windows[i],arena,action,seen,retained) for i in range(2)]
        d210._stable_files(root,retained)
        return dict(schema_version=SCHEMA_ID,action_id=action,method_id=plans.METHOD[action],
                    source_versions=dict(SOURCE_VERSIONS,control=CONTROL_IDS[action]),capture_ordinal=capture['ordinal'],
                    phases=phases,node_order=nodes,schedules=schedules,raw_reconciliation_validated=True,
                    capture_execution_evidence_validated=True,zero_loss_all_phases=all(p['zero_loss'] for p in phases),
                    measurement_zero_loss=phases[1]['zero_loss'],family_validity_established=False,
                    execution_authority=False,phase18_authority=False)
    except ValidationError:raise
    except (KeyError,TypeError,ValueError,IndexError,OSError,codec.DecodeError,OverflowError) as error:
        raise ValidationError('formal service/scheduled evidence rejected: '+str(error)) from error
