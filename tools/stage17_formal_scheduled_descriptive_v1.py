"""D270 complete descriptive Q16c declaration; no execution authority.

Static scheduled successor of D228 arithmetic, using exact original-source
metadata without inline arrays. Historical plan/1 and /2 remain unchanged.
Source generation/authentication, actual descriptors, geometry and owner
admission remain separate gates. No formal D036 confidence claim is made.
"""
from __future__ import annotations
import json
from jsonschema import Draft202012Validator
from check_canonical import canonicalize
import stage17_formal_plan_v1 as native
from stage17_discovery_contract_v2 import (ContractError, _constant, _geometry,
    _object, _product, _sum, _text, _uint)

ROOT = native.ROOT
VERSION = 'cpu-prefetch-stage17-formal-scheduled-plan/3'
METHOD = 'MATRIX-FULL-DESCRIPTIVE-SCREEN-v1'
COLLECTOR_METHOD = native.METHOD['Q16c']
NATIVE_SCHEMA = 'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'
SCHEMA = 'config/schemas/stage17-formal-scheduled-plan-v3.schema.json'
DAYCAP_NS = 86_400_000_000_000
MAX_I64 = native.MAX_I64
FamilyExtent, CaptureExtent = native.FamilyExtent, native.CaptureExtent
FamilyBudget, CaptureBudget = native.FamilyBudget, native.CaptureBudget
_require, _budget = native._require, native._budget
_no_floats, cells, _package = native._no_floats, native.cells, native._package
storage_budget = native.storage_budget


def _schedules(capture, path):
    sources = capture['schedules']
    sizes = []
    for key in ('schedule_id', 'namespace_id', 'seed_id'):
        _require(sources[0][key] != sources[1][key], path, 'phase schedule identities coincide')
    for i, source in enumerate(sources):
        _constant(source['storage_format'], 'SEALED_U64BE_ORIGINAL-v1', path)
        for phase in ('warmup', 'measurement'):
            _require(source['namespace_id'] != capture[phase]['namespace_id']
                and source['seed_id'] != capture[phase]['seed_id'], path,
                'schedule and arena identity coincide')
        duration = capture['warmup_ns'] if i == 0 else capture['measurement_ns']
        end = _sum([source['source_origin_ticks'], _product(duration, 1000, path)], path)
        _constant(source['source_horizon_ticks'], end, path)
        count = _uint(source['offered_count'], path, 0 if i == 0 else 1)
        _require(count <= capture['budget']['phases'][i]['producer_attempt_limit'], path,
                 'source count exceeds producer watchdog')
        sizes.append(_product(count, 8, path))
    _require(_sum(sizes, path) <= capture['budget']['memory_bytes'], path,
             'source vectors exceed native ceiling')
    return tuple(sizes)


def validate_transport(plan):
    transport = _object(plan['source_transport'], 'schema_version format source_bytes '
        'owned_vector_bytes loader_transient_bytes descriptor_count metadata_bytes '
        'maximum_source_memory_bytes', 'source_transport')
    _constant(transport['schema_version'], 'cpu-prefetch-stage17-schedule-transport-budget/1', 'source_transport')
    _constant(transport['format'], 'SEALED_U64BE_ORIGINAL-v1', 'source_transport')
    sizes, identities = [], set()
    for item in plan['captures']:
        for source in item['capture']['schedules']:
            artifact = source['source_artifact']['artifact_id']
            _require(artifact not in identities, 'source_transport', 'reused original-source artifact identity')
            identities.add(artifact)
            sizes.append(_product(source['offered_count'], 8, 'source_transport'))
    total = _sum(sizes, 'source_transport')
    _constant(transport['descriptor_count'], 360, 'source_transport')
    _constant(len(sizes), 360, 'source_transport')
    _constant(transport['source_bytes'], total, 'source_transport')
    _constant(transport['owned_vector_bytes'], total, 'source_transport')
    _require(_uint(transport['loader_transient_bytes'], 'source_transport') >= max(sizes) + 8192,
             'source_transport', 'loader transient copy/block omitted')
    _require(_uint(transport['metadata_bytes'], 'source_transport') >= 1024**2,
             'source_transport', 'source-table/hash/allocator reserve omitted')
    required = _sum([total, total, transport['loader_transient_bytes'], transport['metadata_bytes']], 'source_transport')
    _require(_uint(transport['maximum_source_memory_bytes'], 'source_transport') >= required,
             'source_transport', 'sealed bytes/owned arrays/transient/metadata omitted')
    return transport


def _raw_extent(capture, resources, scheduled, path):
    primary = []
    for index, phase in enumerate(('warmup', 'measurement')):
        prefix = ((4 + len(capture[phase]['run_id'].encode('ascii')) + 7) // 8) * 8
        rows = resources['phase_capacity'][index]
        limit = capture['budget']['phases'][index]['producer_attempt_limit']
        for key, body in (('producer_primary_rows', 120), ('consumer_primary_rows', 80)):
            _require(rows[key] >= limit, path + '.' + key, 'primary capacity omits prospective producer attempts')
            primary.append(_product(rows[key], prefix + body, path + '.' + key))
    node_order = _product(_sum([capture['geometry']['capacity'], 1], path + '.nodes'), 8, path + '.node_bytes') \
        if capture['package'] in ('L0', 'L1') else 0
    schedules = _schedules(capture, path) if scheduled else ()
    extra = _sum([node_order, *schedules], path + '.extra_raw')
    total = _sum([*primary, extra], path + '.raw_bytes')
    # Native D227 conservatively reserves the sum of all extra vectors as one
    # copy floor, even though publication currently emits one artifact at a time.
    floor = max(max(primary), extra)
    actual_largest = max(*primary, node_order, *schedules)
    return total, actual_largest, floor


def validate_plan(document) -> FamilyExtent:
    action, archived = 'Q16c', True
    _no_floats(document)
    scheduled = action == 'Q16c'
    names = ('schema_version plan_id protocol_version action_id method_id source_revision clean_source '
             'stand_id repetitions_per_cell measurement_ns warmup_namespace measurement_namespace '
             'custody_policy_id captures budget') + (' scale_ordinal' if scheduled else '') + (' storage' if archived else '') + ' source_transport'
    plan = _object(document, names, 'plan')
    for name, expected in (('schema_version', VERSION), ('protocol_version', '2.0.0-pre.3'),
                           ('action_id', action), ('method_id', METHOD), ('clean_source', True),
                           ('custody_policy_id', storage_budget.POLICY)):
        _constant(plan[name], expected, 'plan.' + name)
    for name in ('plan_id', 'stand_id', 'warmup_namespace', 'measurement_namespace'):
        _text(plan[name], 'plan.' + name)
    _text(plan['source_revision'], 'plan.source_revision', r'[0-9a-f]{40}')
    _require(plan['warmup_namespace'] != plan['measurement_namespace'], 'plan', 'phase namespaces coincide')
    repetitions = _uint(plan['repetitions_per_cell'], 'plan.repetitions_per_cell', 1 if scheduled else 59)
    _constant(repetitions, 1, 'plan.repetitions_per_cell')
    _constant(plan['scale_ordinal'], 0, 'plan.scale_ordinal')
    _constant(plan['measurement_ns'], 1_000_000_000, 'plan.measurement_ns')
    duration = _uint(plan['measurement_ns'], 'plan.measurement_ns', 1)
    _product(duration, 1000, 'plan.measurement_ticks')
    if scheduled:
        _require(_uint(plan['scale_ordinal'], 'plan.scale_ordinal') < 5, 'plan.scale_ordinal', 'outside five-point ladder')
    ordered_cells = cells(action)
    count = _product(len(ordered_cells), repetitions, 'plan.capture_count')
    _require(type(plan['captures']) is list and len(plan['captures']) == count, 'plan.captures',
             'complete frozen cell/repetition coverage required')
    validator = Draft202012Validator(json.loads((ROOT / NATIVE_SCHEMA).read_text()))
    seen = {name: set() for name in ('run_id', 'seed_id', 'seed_hex')}
    schedule_ids, schedule_seed_ids = set(), set()
    schedule_namespaces = (set(), set())
    geometries, repeated = {}, {}
    extents = []
    for ordinal, item in enumerate(plan['captures']):
        path = f'plan.captures[{ordinal}]'
        item = _object(item, 'capture resources monitoring execution_budget', path)
        native = {key: item[key] for key in ('capture', 'resources', 'monitoring')}
        error = next(validator.iter_errors(native), None)
        _require(error is None, path, '' if error is None else error.message)
        capture, resources, monitoring = (item[key] for key in ('capture', 'resources', 'monitoring'))
        position, repetition = divmod(ordinal, repetitions)
        cell, state, package, placement, working_set, load = ordered_cells[position]
        for key, expected in (('ordinal', ordinal), ('cell_ordinal', cell), ('repetition_ordinal', repetition),
                              ('hardware_state', state), ('package', package), ('placement', placement),
                              ('working_set_class', working_set), ('measurement_ns', duration),
                              ('warmup_ns', 5_000_000_000), ('method_id', COLLECTOR_METHOD)):
            _constant(capture[key], expected, path + '.capture.' + key)
        if scheduled:
            _constant(capture['scale_ordinal'], plan['scale_ordinal'], path + '.scale_ordinal')
            _constant(capture['load_level'], load, path + '.load_level')
        for key, obj in (('resources', resources), ('monitoring', monitoring)):
            _constant(obj['ordinal'], ordinal, path + '.' + key + '.ordinal')
        for phase in ('warmup', 'measurement'):
            identity = capture[phase]
            for field in ('run_id', 'seed_id', 'namespace_id'):
                _text(identity[field], path + '.' + phase + '.' + field)
            _text(identity['seed_hex'], path + '.' + phase + '.seed_hex', r'[0-9a-f]{64}')
            _constant(identity['namespace_id'], plan[phase + '_namespace'], path + '.' + phase + '.namespace_id')
            for field, used in seen.items():
                _require(identity[field] not in used, path, 'reused run/seed identity or seed value')
                used.add(identity[field])
        _constant(capture['arena_seed'], capture['measurement'], path + '.arena_seed')
        if scheduled:
            for phase_index, source in enumerate(capture['schedules']):
                for field, used in (('schedule_id', schedule_ids), ('seed_id', schedule_seed_ids)):
                    _require(source[field] not in used, path, 'reused schedule or schedule-seed identity')
                    used.add(source[field])
                schedule_namespaces[phase_index].add(source['namespace_id'])
        geometry = capture['geometry']; _geometry(geometry, placement, path + '.geometry')
        geometry_key = package, placement, working_set
        if geometry_key in geometries:
            _constant(geometry, geometries[geometry_key], path + '.paired_geometry')
        geometries[geometry_key] = geometry
        _package(capture, path)
        for role in ('producer', 'consumer'):
            stack = resources['workers'][role + '_stack']
            _constant(stack['owner_cpu'], geometry[role + '_cpu'], path + '.workers.' + role)
            _constant(stack['requested_node'], geometry[role + '_node'], path + '.workers.' + role)
        _require(resources['controller_stack']['owner_cpu'] not in (geometry['producer_cpu'], geometry['consumer_cpu']),
                 path, 'controller shares a worker CPU')
        for index, phase in enumerate(capture['budget']['phases']):
            phase_ns = capture['warmup_ns'] if index == 0 else duration
            _product(phase['drain_ns'], 1000, path + '.drain_ticks')
            _require(monitoring['during_offset_ticks'][index] < _product(phase_ns, 1000, path), path,
                     'during observation begins outside phase')
        invariant = {'budget': capture['budget'],
                     'resources': {k:v for k,v in resources.items() if k != 'ordinal'},
                     'monitoring': {k:v for k,v in monitoring.items() if k != 'ordinal'}}
        if cell in repeated:
            _constant(invariant, repeated[cell], path + '.repeated_bounds')
        repeated[cell] = invariant
        raw, largest, copy_floor = _raw_extent(capture, resources, scheduled, path)
        budget = _budget(item['execution_budget'], CaptureBudget, path + '.execution_budget')
        known_time = _sum([budget.setup_ns, capture['warmup_ns'], duration,
                          *(phase['drain_ns'] for phase in capture['budget']['phases']),
                          budget.publication_ns, budget.cleanup_ns], path + '.required_watchdog_ns')
        _require(known_time <= budget.watchdog_ns <= MAX_I64, path, 'watchdog omits time or exceeds signed native duration')
        mapping = resources['total_mapping_bytes']
        _require(mapping <= capture['budget']['memory_bytes'], path, 'native mapping ceiling insufficient')
        _require(budget.publication_memory_bytes >= copy_floor, path, 'publication copy floor omitted')
        memory = _sum([mapping, budget.publication_memory_bytes, budget.other_memory_bytes], path + '.memory')
        _require(budget.memory_bytes >= memory, path, 'mapped/publication/other memory omitted')
        _require(budget.max_output_bytes >= _sum([raw, budget.metadata_output_bytes], path + '.output'),
                 path, 'raw or metadata output omitted')
        extents.append(CaptureExtent(ordinal, raw, largest, mapping, known_time, budget))
    transport = validate_transport(plan)
    family = _budget(plan['budget'], FamilyBudget, 'plan.budget')
    _require(not schedule_seed_ids.intersection(seen['seed_id']), 'plan', 'schedule and arena seed IDs overlap')
    _require(not schedule_namespaces[0].intersection(schedule_namespaces[1]), 'plan',
             'warmup and measurement schedule namespaces overlap')
    _require(not set.union(*schedule_namespaces).intersection((plan['warmup_namespace'], plan['measurement_namespace'])),
             'plan', 'schedule and arena namespaces overlap')
    watchdog = _sum([family.setup_ns, family.cleanup_ns, *(e.declared.watchdog_ns for e in extents)], 'plan.watchdog')
    memory = _sum([transport['maximum_source_memory_bytes'], family.controller_memory_bytes, max(e.declared.memory_bytes for e in extents)], 'plan.memory')
    output = _sum([family.metadata_output_bytes, *(e.declared.max_output_bytes for e in extents)], 'plan.output')
    if archived:
        storage = storage_budget.validate_storage_plan(
            plan['storage'], [e.declared for e in extents], family,
            native_family_watchdog_ns=watchdog, native_family_memory_bytes=memory,
            logical_output_bound_bytes=output)
        disk = storage.required_initial_free_bytes
        watchdog = storage.minimum_family_watchdog_ns
        memory = storage.minimum_family_memory_bytes
    else:
        disk = _sum([family.max_output_bytes, family.analysis_scratch_bytes, family.disk_reserve_bytes], 'plan.disk')
    for declared, required, label in ((family.watchdog_ns, watchdog, 'watchdog'),
                                      (family.memory_bytes, memory, 'memory'), (family.max_output_bytes, output, 'output'),
                                      (family.required_free_disk_bytes, disk, 'free disk')):
        _require(declared >= required, 'plan.budget', label + ' omits declared component')
    _require(family.watchdog_ns <= MAX_I64, 'plan.budget', 'watchdog exceeds signed native duration')
    _require(family.controller_memory_bytes >= len(canonicalize(plan).encode('utf-8')), 'plan.budget',
             'controller cannot hold even canonical plan bytes')
    _require(family.watchdog_ns <= DAYCAP_NS, 'plan.budget', 'descriptive screen exceeds24h')
    return FamilyExtent(tuple(extents), watchdog, memory, output, disk, family)
