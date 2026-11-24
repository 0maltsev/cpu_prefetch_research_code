"""D220 independent formal Q16a per-capture validation; no family admission.

The caller supplies authenticated original control/final-result and frozen input
objects. Raw files are opened without symlink traversal and checked by size,
identity and SHA256. Primary joins and demand associations use constant row
storage; arena replay and exact-quantile heaps retain their existing explicit
bounds. No joined file, successful status, or missing observation is synthesized.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import os
import pathlib
import re
from types import SimpleNamespace

from jsonschema import Draft202012Validator

import stage17_discovery_validation_v3 as common
import stage17_q16a_demand_decoder_v1 as demand
import stage17_raw_stream_decoder_v1 as codec
import stage17_raw_stream_decoder_v2 as raw

SCHEMA_ID = 'cpu-prefetch-stage17-q16a-capture-validation/1'
CONTROL_ID = 'cpu-prefetch-stage17-formal-ring-control/1'
ValidationError = common.ValidationError
require, exact, uint = common.require, common.exact, common.uint
ROLES = ('producer', 'consumer')
PHASES = ('warmup', 'measurement')


def _namespace(value):
    if isinstance(value, dict):
        return SimpleNamespace(**{key: _namespace(item) for key, item in value.items()})
    return value


def _input(capture, resources, monitoring):
    schema = pathlib.Path(__file__).resolve().parents[1] / 'config/schemas/stage17-formal-ring-native-input-v1.schema.json'
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
    context = capture['context_ordinal']
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
        for name in ('producer_primary_rows','consumer_primary_rows','producer_demand_rows'):
            require(capacity[name] >= bound['producer_attempt_limit'], 'uncovered producer bound')
        require(capacity['consumer_demand_rows'] >= bound['consumer_poll_limit'], 'uncovered consumer bound')
    minimum = capture['minimum_observations_per_series']
    for name in ('producer_attempt_limit','consumer_poll_limit'):
        require(minimum < capture['budget']['phases'][1][name], 'impossible issue minimum')


def _session(control, final, capture):
    exact(control['schema_version'], CONTROL_ID, 'formal control schema')
    exact(control['method_id'], demand.METHOD_ID, 'formal method')
    exact(control['capture_ordinal'], capture['ordinal'], 'capture ordinal')
    exact(control['minimum_observations_per_series'], capture['minimum_observations_per_series'], 'frozen minimum')
    for flag in ('execution_authority','inferential_validity_established','phase18_authority'):
        exact(control[flag], False, 'publisher grants no ' + flag)
    pre = control['native_result_before_publication_returns']
    exact(pre['stop'], 14, 'native complete before publication')
    exact(final['stop'], 14, 'native complete after cleanup')
    exact(pre['publication_attempted'], True, 'publication entered')
    exact(pre['publication_succeeded'], False, 'publication has not returned')
    exact(final['publication_attempted'], True, 'final publication attempted')
    exact(final['publication_succeeded'], True, 'final publication succeeded')
    session = pre['session']
    exact(final['session'], session, 'unchanged actual session')
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
        for flag in ('deadline_reached','arrivals_finished_published'):
            exact(producer[flag], True, 'producer ' + flag)
        exact(consumer['drained'], True, 'terminal queue drain')
        for owner in (producer, consumer):
            exact(owner['last_clock_status'], 0, 'owner final clock status')
            require(uint(owner['last_observed_tick'], 'owner last tick') >= begin, 'owner clock before phase')
        require(producer['last_observed_tick'] >= begin+duration, 'producer stopped before horizon')
        require(consumer['last_observed_tick'] >= begin+duration and
                consumer['last_observed_tick'] < window['drain_deadline_ticks'], 'consumer drain deadline')
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
        windows.append(dict(clock_suite_id=raw.CLOCK_SUITE_ID, time_unit=raw.TIME_UNIT,
            ticks_per_second=raw.TICKS_PER_SECOND, clock_origin_absolute_nanoseconds=origin,
            phase_origin=dict(sample), duration_ticks=duration))
    return pre, session, windows


def _common_controls(control, final, pre, session, capture, resources, monitoring, hardware_control):
    # These are field-name projections of already checked, retained observations.
    # No discovery stop/preparation/reset flags are created or passed as evidence.
    equivalent_session = dict(origins=[p['origin_sample']['relative_picoseconds'] for p in session['phases']])
    for name, phase in zip(PHASES, session['phases'], strict=True):
        equivalent_session[name] = [phase['producer'], phase['consumer']]
    projected = dict(control)
    # The shared environmental decoder names its observation envelope after
    # discovery. Formal publication uses precisely the same observation_document
    # encoder. This local view label is NOT an original document identity or a
    # discovery-session claim; _session already checked the formal identity.
    projected['schema_version'] = common.environment.CONTROL_VERSION
    for name in ('clock_origin','publication_attempted','publication_succeeded','core_mapping','monitor_mapping','controller_stack'):
        projected[name] = pre[name]
    projected['session'] = equivalent_session
    projected_final = dict(final, session=equivalent_session)
    regions = common.validate_controls(projected, projected_final, _namespace(capture), resources, monitoring, hardware_control)
    for i, phase in enumerate(session['phases']):
        after = [r for r in control['residency'] if r['request']['phase'] == i and r['request']['moment'] == 2]
        last_after = max(common.clock(r['end'], pre['clock_origin']['absolute_nanoseconds'], 'after query') for r in after)
        checkpoint = common.clock(phase['drain_checkpoint'], pre['clock_origin']['absolute_nanoseconds'], 'checkpoint')
        require(checkpoint >= last_after, 'checkpoint precedes AFTER monitoring')
        if i == 0:
            next_before = min(common.clock(r['begin'], pre['clock_origin']['absolute_nanoseconds'], 'measurement BEFORE')
                              for r in control['residency'] if r['request']['phase'] == 1 and r['request']['moment'] == 0)
            require(next_before >= checkpoint, 'measurement BEFORE precedes warmup checkpoint')
    return regions


def _arena(control, capture, regions):
    arena = common.Arena(_namespace(capture))
    g = capture['geometry']
    expected = dict(capacity=g['capacity'], cache_line_bytes=g['cache_line_bytes'], base_page_bytes=g['base_page_bytes'],
        allocated_bytes=g['capacity']*g['cache_line_bytes'], distinct_cache_lines=g['capacity'],
        distinct_pages=(g['capacity']*g['cache_line_bytes']+g['base_page_bytes']-1)//g['base_page_bytes'],
        base_page_aligned=True, every_record_line_aligned=True, padding_initialized=True,
        storage_address=regions[0]['address'], content_unchanged=True,
        prepared_content_sha256=arena.hashes[0], publication_content_sha256=arena.hashes[0],
        ordered_index_sha256=arena.hashes[1], address_delta_sha256=arena.hashes[2],
        ordered_index_error=None, address_delta_error=None)
    for name, value in expected.items(): exact(control['arena'][name], value, 'arena.'+name)
    return arena


def _bindings(phase, capture, resources, index, window):
    identity = capture[PHASES[index]]
    run_id = identity['run_id']
    prefix, pb, cb, jb = codec.row_layout(run_id)
    layout = dict(run_id_bytes=len(run_id.encode()), prefix_bytes=prefix,
                  producer_row_bytes=pb, consumer_row_bytes=cb, joined_row_bytes=jb)
    bindings = {}
    for role_index, role in enumerate(ROLES):
        exact(phase[role+'_available'], True, role+' available')
        exact(phase[role+'_prefix_complete'], True, role+' complete primary prefix')
        exact(phase[role+'_stopped'], False, role+' no capture failure')
        exact(phase[role+'_layout'], layout, role+' primary layout')
        for kind in ('primary','demand'):
            key = role if kind == 'primary' else role+'_demand'
            snapshot = phase[key+'_snapshot']
            row_bytes = (pb if role == 'producer' else cb) if kind == 'primary' else prefix+72
            count = uint(snapshot['row_count'], key+' row count')
            capacity = resources['phase_capacity'][index][role+'_'+kind+'_rows']
            expected = dict(run_id=run_id, row_count=count, row_capacity=capacity, row_bytes=row_bytes,
                            completeness='SEALED_COMPLETE', overflowed=False, retained_bytes=count*row_bytes)
            expected.update(dict(stream_kind=role_index) if kind == 'primary' else dict(format_id=demand.FORMAT_ID, worker=role_index))
            exact(snapshot, expected, key+' snapshot')
            require(count <= capacity, key+' exceeds capacity')
            artifact = phase[key]
            raw._object(artifact, 'file_name role schema_identity size_bytes sha256', key+' artifact reference')
            exact(artifact['role'], 'Q16A_PRIMARY_RAW' if kind == 'primary' else 'Q16A_DEMAND_RAW', key+' role')
            exact(artifact['schema_identity'], codec.FORMAT_ID if kind == 'primary' else demand.FORMAT_ID, key+' format')
            binding = raw._binding(dict(path=artifact['file_name'], size_bytes=artifact['size_bytes'], sha256=artifact['sha256'], row_count=count), key, row_bytes)
            bindings[key] = binding
            exact(phase[role+'_last_'+kind+'_append'], 0 if count else None, key+' append status')
        expected_contract = dict(schema_version=demand.CONTRACT_ID, method_id=demand.METHOD_ID, physical_format=demand.FORMAT_ID,
            run_id=run_id, role=role, phase=PHASES[index], phase_window=window,
            minimum_observations_per_series=None if index == 0 else capture['minimum_observations_per_series'], stream=bindings[role+'_demand'])
        exact(phase[role+'_demand_contract'], expected_contract, role+' actual demand window/binding')
    return bindings


def _demand_row(stream, run_id, row_bytes, ordinal, role, advanced, origin, begin, previous):
    row = codec._row(stream, row_bytes, run_id, 9, 'demand row')
    attempt, outcome, advancing, bs, ba, before, es, ea, after = row
    require(attempt == ordinal and outcome in ((0,1) if role == 'producer' else (0,2)), 'demand identity/outcome')
    require(bs == es == 0, 'failed demand clock, including excluded rows')
    raw._clock_pair(ba, before, origin, 'demand begin')
    raw._clock_pair(ea, after, origin, 'demand end')
    require(begin <= before <= after and previous <= before, 'demand clock order')
    exact(advancing, advanced if outcome == 0 else 0, 'demand advancing ordinal')
    return row


def _current(phase, last_p, last_pd, last_cd, origin, arena, arena_address, accepted, last_consumer_finish):
    p = phase['producer_current']
    c = phase['consumer_current']
    def current(event, row):
        require(event['failed_boundary'] is None, 'current failed boundary')
        expected = dict(outcome=row[1], before_status=0, after_status=0, operation_outcome=row[1],
                        operation_performed=True, failed_clock_status=None)
        exact(event['capture'], expected, 'current capture status')
        exact(event['demand_before'], dict(status=0, absolute_nanoseconds=row[4], relative_picoseconds=row[5]), 'current raw before')
        exact(event['demand_after'], dict(status=0, absolute_nanoseconds=row[7], relative_picoseconds=row[8]), 'current raw after')
    if last_p is None:
        exact(p['capture']['operation_performed'], False, 'no producer operation')
        require(p['primary'] is None and p['requested_attempt'] is None, 'absent producer current')
    else:
        current(p, last_pd)
        outcome = last_pd[1]
        exact(p['requested_attempt'], dict(logical_sequence=last_p[0], scheduled_arrival=last_p[2], candidate_accepted_ordinal=accepted-(outcome == 0)), 'current request')
        exact(p['selected'], dict(record_index=last_p[1], record_address=arena_address+last_p[1]*arena.line_bytes), 'current selection')
        primary = p['primary']
        for name, expected in dict(logical_sequence=last_p[0], record_index=last_p[1], scheduled_arrival=last_p[2],
                                   outcome=outcome, accepted_ordinal=last_p[13] if outcome == 0 else None).items():
            exact(primary[name], expected, 'current producer primary')
        for name, key, offset in (('handle_begin','producer_handle_begin',3), ('lookup_completion','record_lookup_completion',5),
                                  ('enqueue_invocation','enqueue_invocation',7), ('enqueue_completion','enqueue_attempt_completion',11)):
            sample = dict(absolute_nanoseconds=last_p[offset], relative_picoseconds=last_p[offset+1])
            exact(primary[key], sample, 'current primary clock')
            exact(p[name], dict(status=0, **sample), 'current event clock')
        if outcome == 0:
            sample = dict(absolute_nanoseconds=last_p[9], relative_picoseconds=last_p[10])
            exact(primary['enqueue_linearization'], sample, 'current publication sample')
            exact(p['enqueue_publication'], dict(status=0, **sample), 'current publication clock')
        else:
            require(primary['enqueue_linearization'] is None and p['enqueue_publication'] is None, 'FULL has publication')
    require(last_cd is not None and last_cd[1] == 2, 'successful drain lacks terminal EMPTY')
    current(c, last_cd)
    exact(c['candidate_consumed_ordinal'], accepted, 'terminal candidate ordinal')
    exact(c['operation'], dict(status=1, event_address=None), 'terminal empty operation')
    for name in ('primary','dequeue_observation','dequeue_completion','action_completion','access'):
        require(c[name] is None, 'terminal EMPTY contains item evidence')
    invocation = common.clock(c['dequeue_invocation'], origin, 'terminal invocation')
    require(last_consumer_finish <= invocation <= last_cd[5], 'terminal invocation order')


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _stable_files(root, retained):
    with ExitStack() as stack:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        stack.callback(os.close, fd)
        for binding, original in retained:
            current = raw._open_stream(stack, fd, binding, 'retained identity')
            exact(_stamp(current.before), original, 'raw file changed across capture validation')


def _join_phase(root, phase, state, capture, resources, index, window, arena, address, seen, retained):
    bindings = _bindings(phase, capture, resources, index, window)
    run_id = capture[PHASES[index]]['run_id']
    prefix, pb, cb, _ = codec.row_layout(run_id)
    origin = window['clock_origin_absolute_nanoseconds']; begin = window['phase_origin']['relative_picoseconds']
    end = begin + window['duration_ticks']; drain_end = state['window']['drain_deadline_ticks']
    accepted = full = polls = empty = 0
    checksum = uint(resources['initial_consumer_state'], 'initial checksum')
    previous_p = previous_c = previous_pd = previous_cd = begin
    last_p = last_pd = last_cd = None
    with ExitStack() as stack:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        stack.callback(os.close, root_fd)
        streams = {name: raw._open_stream(stack, root_fd, binding, name) for name, binding in bindings.items()}
        for name, stream in streams.items():
            retained.append((bindings[name], _stamp(stream.before)))
            identities = (('path', bindings[name]['path']), ('inode',stream.before.st_dev,stream.before.st_ino))
            for identity in identities:
                require(identity not in seen, 'raw artifacts alias across roles/phases')
                seen.add(identity)
        for logical in range(bindings['producer']['row_count']):
            p = codec._row(streams['producer'], pb, run_id, 15, 'producer primary')
            require(p[0] == logical and p[14] in (codec.ACCEPTED_FLAGS,codec.FULL_FLAGS), 'producer identity/flags')
            exact(p[1], arena.order[logical % len(arena.order)], 'deterministic record selection')
            for off in (3,5,7,11): raw._clock_pair(p[off], p[off+1], origin, 'producer primary clock')
            require(begin <= p[2] < end and previous_p <= p[2] <= p[4] <= p[6] <= p[8] <= p[12], 'producer primary order/horizon')
            pd = _demand_row(streams['producer_demand'],run_id,prefix+72,logical,'producer',accepted,origin,begin,previous_pd)
            require(p[8] <= pd[5] <= pd[8] <= p[12], 'producer acquire outside primary bracket')
            exact(pd[1], 0 if p[14] == codec.ACCEPTED_FLAGS else 1, 'producer demand/primary outcome')
            previous_p, previous_pd = p[12], pd[8]
            last_p, last_pd = p, pd
            if p[14] == codec.FULL_FLAGS:
                require(p[9] == p[10] == p[13] == 0, 'FULL has accepted-only values')
                full += 1
                continue
            raw._clock_pair(p[9],p[10],origin,'publication')
            require(p[13] == accepted and pd[8] <= p[10] <= p[12], 'accepted ordinal/publication')
            c = codec._row(streams['consumer'],cb,run_id,10,'consumer primary')
            require(c[0] == accepted and c[1] == p[1], 'primary ordinal/record join')
            for off in (2,4,6,8): raw._clock_pair(c[off],c[off+1],origin,'consumer primary clock')
            require(previous_c <= c[3] <= c[5] <= c[7] <= c[9] < drain_end and p[10] <= c[5], 'consumer primary order/publication')
            while True:
                require(polls < bindings['consumer_demand']['row_count'], 'missing advancing consumer demand')
                cd = _demand_row(streams['consumer_demand'],run_id,prefix+72,polls,'consumer',accepted,origin,begin,max(previous_cd,previous_c))
                polls += 1; previous_cd = cd[8]; last_cd = cd
                require(cd[8] < drain_end, 'consumer demand exceeds drain deadline')
                if cd[1] == 0:
                    require(c[3] <= cd[5] <= cd[8] <= c[5], 'consumer acquire outside primary bracket')
                    break
                empty += 1
                require(cd[8] <= c[3], 'EMPTY overlaps next item invocation')
            checksum = common.mix(checksum,c[1],arena.payload[c[1]])
            previous_c = c[9]; accepted += 1
        while polls < bindings['consumer_demand']['row_count']:
            cd = _demand_row(streams['consumer_demand'],run_id,prefix+72,polls,'consumer',accepted,origin,begin,max(previous_cd,previous_c))
            require(cd[1] == 2 and cd[8] < drain_end, 'unjoined advancement or late drain poll')
            polls += 1; empty += 1; previous_cd = cd[8]; last_cd = cd
        for stream in streams.values(): stream.finish()
    counts = dict(attempted=accepted+full, accepted=accepted, full=full, consumed_including_drain=accepted, polls=polls, empty=empty)
    exact(bindings['producer']['row_count'], counts['attempted'], 'producer rows')
    exact(bindings['producer_demand']['row_count'], counts['attempted'], 'producer demand rows')
    exact(bindings['consumer']['row_count'], accepted, 'consumer rows')
    for name, value in counts.items(): exact(phase[name], value, 'phase '+name)
    exact(phase['requests'], counts['attempted'], 'actual producer requests')
    for role, names in (('producer',('attempted','accepted','full')), ('consumer',('consumed_including_drain','polls','empty'))):
        for name in names: exact(state[role][name], counts[name], 'session '+name)
    exact(phase['initial_checksum'], resources['initial_consumer_state'], 'phase initial checksum reset')
    exact(phase['checksum'], checksum, 'full drain checksum')
    exact(phase['consumer_last_join'], dict(status=1,matched=accepted,failed_producer_row=None), 'native join crosscheck')
    require(state['producer']['last_observed_tick'] >= previous_p and
            state['consumer']['last_observed_tick'] >= max(previous_c,previous_cd), 'worker last clocks precede raw capture')
    _current(phase,last_p,last_pd,last_cd,origin,arena,address,accepted,previous_c)
    return dict(phase=PHASES[index], run_id=run_id, counts=counts, zero_loss=full == 0,
                stream_sha256={name:b['sha256'] for name,b in bindings.items()})


def validate_capture(root, control, final, capture, resources, monitoring, hardware_control):
    """Validate one authenticated capture; caller retains authority/provenance duties.

    Failure raises ValidationError and publishes no partial quantiles. Files are
    read-only. FULL is reconciled normally and reported by a separate zero-loss
    gate. No duration/repetition selection or family-level acceptance occurs.
    """
    try:
        _input(capture, resources, monitoring)
        pre, session, windows = _session(control, final, capture)
        regions = _common_controls(control,final,pre,session,capture,resources,monitoring,hardware_control)
        arena = _arena(control,capture,regions)
        require(len(control['phases']) == 2, 'two raw phases')
        seen = set(); retained = []
        phases = [_join_phase(root,control['phases'][i],session['phases'][i],capture,resources,i,windows[i],arena,regions[0]['address'],seen,retained)
                  for i in range(2)]
        # Both phases, all eight hashes and every primary/demand join passed.
        # Each decoder independently rechecks its original demand-file binding.
        _stable_files(root, retained)
        for i, phase in enumerate(phases):
            phase['demand'] = {role:demand.decode(root,control['phases'][i][role+'_demand_contract']) for role in ROLES}
        _stable_files(root, retained)
        return dict(schema_version=SCHEMA_ID, method_id=demand.METHOD_ID, capture_ordinal=capture['ordinal'],
            minimum_observations_per_series=capture['minimum_observations_per_series'], phases=phases,
            raw_reconciliation_validated=True, capture_execution_evidence_validated=True,
            zero_loss_all_phases=all(p['zero_loss'] for p in phases),
            measurement_zero_loss=phases[1]['zero_loss'], family_validity_established=False,
            execution_authority=False, phase18_authority=False)
    except ValidationError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, OSError, codec.DecodeError, OverflowError) as error:
        raise ValidationError('formal capture evidence rejected: '+str(error)) from error
