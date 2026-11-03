"""D228 prospective Q16a/b/c family declarations, without execution authority.

Q16a delegates unchanged to D221. Q16b/Q16c preserve the D227 native family
order and budget arithmetic; native sizing, schedule-source provenance, seed
reservation, qualified evidence and owner admission remain separate gates.
"""
from __future__ import annotations

import json
import pathlib

from jsonschema import Draft202012Validator

from check_canonical import canonicalize
import stage17_formal_ring_plan_v1 as ring
import stage17_formal_storage_budget_v1 as storage_budget
from stage17_discovery_contract_v2 import (
    ContractError, _constant, _geometry, _object, _product, _sum, _text, _uint,
)

METHOD = {'Q16a': ring.METHOD, 'Q16b': 'SERVICE-RATE-NP-LTL95C95-MIN-v1',
          'Q16c': 'MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1'}
VERSION = {'Q16a': ring.VERSION, 'Q16b': 'cpu-prefetch-stage17-formal-service-plan/1',
           'Q16c': 'cpu-prefetch-stage17-formal-scheduled-plan/1'}
CUSTODY = {action: ring.CUSTODY for action in METHOD}
SCHEMA = {action: f'config/schemas/stage17-formal-{kind}-plan-v1.schema.json'
          for action, kind in (('Q16a', 'ring'), ('Q16b', 'service'), ('Q16c', 'scheduled'))}
NATIVE_SCHEMA = {action: name.replace('-plan-v1', '-native-input-v1') for action, name in SCHEMA.items()}
ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGES = ('R0', 'R1', 'R2', 'L0', 'L1')
WORKING_SETS = ('L2_RESIDENT', 'LLC_RESIDENT', 'BEYOND_LLC')
LOADS = ('L025', 'L050', 'L075')
MAX_I64 = (1 << 63) - 1
CaptureBudget, FamilyBudget = ring.CaptureBudget, ring.FamilyBudget
CaptureExtent, FamilyExtent = ring.CaptureExtent, ring.FamilyExtent
_require, _budget = ring._require, ring._budget


def cells(action):
    """Execution order is state-major; the returned identity is package-major."""
    _require(action in ('Q16b', 'Q16c'), 'action', 'service/scheduled action required')
    result = []
    for state_number, state in enumerate(('H0', 'H1')):
        for package_number, package in enumerate(PACKAGES):
            for placement_number, placement in enumerate(('NEAR', 'FAR')):
                for working_number, working_set in enumerate(WORKING_SETS):
                    service_cell = package_number * 12 + state_number * 6 + placement_number * 3 + working_number
                    for load_number, load in enumerate(LOADS if action == 'Q16c' else (None,)):
                        cell = service_cell * 3 + load_number if action == 'Q16c' else service_cell
                        result.append((cell, state, package, placement, working_set, load))
    return tuple(result)


def _no_floats(value):
    _require(not isinstance(value, float), 'plan', 'floating-point input is forbidden')
    if isinstance(value, dict):
        for item in value.values():
            _no_floats(item)
    elif isinstance(value, list):
        for item in value:
            _no_floats(item)


def _package(capture, path):
    package = capture['package']
    linked, distance = capture['linked_order'], capture['ring_distance']
    _text(capture['software_prefetch_mapping_id'], path + '.software_prefetch_mapping_id')
    if package in ('L0', 'L1'):
        _require(linked is not None and distance is None, path, 'linked package requires node order, not ring distance')
        _text(linked['seed_id'], path + '.linked_order.seed_id')
        _text(linked['namespace_id'], path + '.linked_order.namespace_id')
        _text(linked['seed_hex'], path + '.linked_order.seed_hex', r'[0-9a-f]{64}')
        _constant(linked['arena_alignment_bytes'], capture['geometry']['base_page_bytes'], path + '.node_alignment')
    else:
        _require(linked is None, path, 'ring package cannot declare linked node order')
        if package == 'R0':
            _require(distance is None, path, 'R0 cannot declare a prefetch distance')
        elif package == 'R1':
            _require(distance is not None, path, 'R1 requires its registered distance')
            _constant(distance['cache_lines'], 1, path + '.ring_distance.cache_lines')
            _constant(distance['calibration_evidence_id'], '', path + '.ring_distance.calibration_evidence_id')
        else:
            _require(distance is not None, path, 'R2 requires a calibrated distance declaration')
            _text(distance['calibration_evidence_id'], path + '.ring_distance.calibration_evidence_id')
    # Native storage geometry and actual calibration evidence remain independent.


def _schedules(capture, path):
    schedules = capture['schedules']
    for field in ('schedule_id', 'namespace_id', 'seed_id'):
        _require(schedules[0][field] != schedules[1][field], path, 'phase schedule identities must differ')
    sizes = []
    for index, source in enumerate(schedules):
        label = path + f'.schedules[{index}]'
        for field in ('schedule_id', 'namespace_id', 'seed_id'):
            _text(source[field], label + '.' + field)
        _text(source['seed_hex'], label + '.seed_hex', r'[0-9a-f]{64}')
        _text(source['source_artifact']['artifact_id'], label + '.source_artifact.artifact_id')
        _text(source['source_artifact']['sha256'], label + '.source_artifact.sha256', r'[0-9a-f]{64}')
        for phase in ('warmup', 'measurement'):
            _require(source['namespace_id'] != capture[phase]['namespace_id']
                     and source['seed_id'] != capture[phase]['seed_id'], label,
                     'schedule and arena identities must be separate')
        duration = capture['warmup_ns'] if index == 0 else capture['measurement_ns']
        end = _sum([source['source_origin_ticks'], _product(duration, 1000, label)], label + '.end')
        _constant(source['source_horizon_ticks'], end, label + '.horizon')
        count = source['offered_count']
        _require(len(source['deadline_ticks']) == count, label, 'offered count differs from source length')
        _require(count <= capture['budget']['phases'][index]['producer_attempt_limit'], label,
                 'offered count exceeds producer watchdog')
        _require(index == 0 or count > 0, label, 'measurement must offer an arrival')
        previous = source['source_origin_ticks']
        for deadline in source['deadline_ticks']:
            _require(previous <= deadline < end, label, 'deadline outside half-open ordered source horizon')
            previous = deadline
        sizes.append(_product(count, 8, label + '.raw_bytes'))
    _require(_sum(sizes, path + '.source_bytes') <= capture['budget']['memory_bytes'], path,
             'native memory ceiling cannot hold source vectors')
    return tuple(sizes)


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


def validate_plan(action, document) -> FamilyExtent:
    return _validate_plan(action, document, archived=False)


def _validate_plan(action, document, *, archived: bool) -> FamilyExtent:
    _require(type(action) is str and action in METHOD, 'action', 'unsupported formal action')
    if action == 'Q16a':
        return (ring._validate_plan(document, archived=True) if archived
                else ring.validate_plan(document))
    _no_floats(document)
    scheduled = action == 'Q16c'
    names = ('schema_version plan_id protocol_version action_id method_id source_revision clean_source '
             'stand_id repetitions_per_cell measurement_ns warmup_namespace measurement_namespace '
             'custody_policy_id captures budget') + (' scale_ordinal' if scheduled else '') + (' storage' if archived else '')
    plan = _object(document, names, 'plan')
    for name, expected in (('schema_version', VERSION[action].replace('/1', '/2') if archived else VERSION[action]), ('protocol_version', '2.0.0-pre.3'),
                           ('action_id', action), ('method_id', METHOD[action]), ('clean_source', True),
                           ('custody_policy_id', storage_budget.POLICY if archived else CUSTODY[action])):
        _constant(plan[name], expected, 'plan.' + name)
    for name in ('plan_id', 'stand_id', 'warmup_namespace', 'measurement_namespace'):
        _text(plan[name], 'plan.' + name)
    _text(plan['source_revision'], 'plan.source_revision', r'[0-9a-f]{40}')
    _require(plan['warmup_namespace'] != plan['measurement_namespace'], 'plan', 'phase namespaces coincide')
    repetitions = _uint(plan['repetitions_per_cell'], 'plan.repetitions_per_cell', 1 if scheduled else 59)
    duration = _uint(plan['measurement_ns'], 'plan.measurement_ns', 1)
    _product(duration, 1000, 'plan.measurement_ticks')
    if scheduled:
        _require(_uint(plan['scale_ordinal'], 'plan.scale_ordinal') < 5, 'plan.scale_ordinal', 'outside five-point ladder')
    ordered_cells = cells(action)
    count = _product(len(ordered_cells), repetitions, 'plan.capture_count')
    _require(type(plan['captures']) is list and len(plan['captures']) == count, 'plan.captures',
             'complete frozen cell/repetition coverage required')
    validator = Draft202012Validator(json.loads((ROOT / NATIVE_SCHEMA[action]).read_text()))
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
                              ('warmup_ns', 5_000_000_000), ('method_id', METHOD[action])):
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
    family = _budget(plan['budget'], FamilyBudget, 'plan.budget')
    _require(not schedule_seed_ids.intersection(seen['seed_id']), 'plan', 'schedule and arena seed IDs overlap')
    _require(not schedule_namespaces[0].intersection(schedule_namespaces[1]), 'plan',
             'warmup and measurement schedule namespaces overlap')
    _require(not set.union(*schedule_namespaces).intersection((plan['warmup_namespace'], plan['measurement_namespace'])),
             'plan', 'schedule and arena namespaces overlap')
    watchdog = _sum([family.setup_ns, family.cleanup_ns, *(e.declared.watchdog_ns for e in extents)], 'plan.watchdog')
    memory = _sum([family.controller_memory_bytes, max(e.declared.memory_bytes for e in extents)], 'plan.memory')
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
    return FamilyExtent(tuple(extents), watchdog, memory, output, disk, family)
