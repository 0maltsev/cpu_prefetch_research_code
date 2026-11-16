"""D260 incident-bound103-capture Q16b declaration; no execution authority.

The actual original17 reports, post-exit custody, compatibility and qualified
new release require independent admission. This declaration never supplies them.
Historical D254 service/3 and all older methods remain unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction

from jsonschema import Draft202012Validator

from check_canonical import canonicalize
import stage17_formal_plan_v1 as native
import stage17_formal_storage_budget_v1 as storage_v1
import stage17_formal_calibration_v1 as capture_reports
from stage17_discovery_contract_v2 import (
    ContractError, _constant, _geometry, _object, _product, _sum, _text, _uint,
)

VERSION = 'cpu-prefetch-stage17-formal-service-plan/4'
METHOD = 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1'
COLLECTOR_METHOD = 'SERVICE-RATE-NP-LTL95C95-MIN-v1'
SCHEMA = 'config/schemas/stage17-formal-service-plan-v4.schema.json'
SCHEMA_ID = 'cpu-prefetch-stage17-formal-service-descriptive/1'
DAYCAP_NS = 24 * 60 * 60 * 1_000_000_000
REPETITIONS = 2
MEASUREMENT_NS = 1_000_000_000
WARMUP_NS = 5_000_000_000
FamilyExtent = native.FamilyExtent
CalibrationError = capture_reports.CalibrationError


POLICY = 'Q16B-RETAINED-PREFIX-CONTINUATION-v1'
SEED_POLICY = 'PRESERVE_ORIGINAL_NUMERIC_SEEDS_FRESH_IDENTITIES'
PARENT_SOURCE = 'aa3285f15acbd3314cae64a628c113488a8438b8'
PARENT_SHA256 = '53ef4baad885eeece98697d6c57b0dd0a375107504b277ffef7482185081e486'
PARENT_SIZE = 2072840
FAILURE_SHA256 = '332662f64d2f802578c0152aec69781f3b913afca43efe2714483da7e80b3269'
FAILURE_SIZE = 1084
FIRST_ORDINAL = 17
CAPTURE_COUNT = 103

def validate_plan(document) -> FamilyExtent:
    """Recompute extents for exactly103 real suffix captures, without projection."""
    validate_declaration(document)
    native._no_floats(document)
    plan = _object(document,
        'schema_version plan_id protocol_version action_id method_id source_revision clean_source '
        'stand_id repetitions_per_cell measurement_ns warmup_namespace measurement_namespace '
        'custody_policy_id captures budget storage continuation', 'plan')
    for name, expected in (('schema_version', VERSION), ('protocol_version', '2.0.0-pre.3'),
                           ('action_id', 'Q16b'), ('method_id', METHOD), ('clean_source', True),
                           ('custody_policy_id', storage_v1.POLICY),
                           ('repetitions_per_cell', REPETITIONS), ('measurement_ns', MEASUREMENT_NS)):
        _constant(plan[name], expected, 'plan.' + name)
    for name in ('plan_id', 'stand_id', 'warmup_namespace', 'measurement_namespace'):
        _text(plan[name], 'plan.' + name)
    _text(plan['source_revision'], 'plan.source_revision', r'[0-9a-f]{40}')
    native._require(plan['warmup_namespace'] != plan['measurement_namespace'], 'plan', 'phase namespaces coincide')
    repetitions = _uint(plan['repetitions_per_cell'], 'plan.repetitions_per_cell', REPETITIONS)
    duration = _uint(plan['measurement_ns'], 'plan.measurement_ns', 1)
    _product(duration, 1000, 'plan.measurement_ticks')
    ordered_cells = native.cells('Q16b')
    count = CAPTURE_COUNT
    native._require(type(plan['captures']) is list and len(plan['captures']) == count, 'plan.captures',
                    'complete frozen cell/repetition coverage required')
    validator = Draft202012Validator(json.loads((native.ROOT / native.NATIVE_SCHEMA['Q16b']).read_text()))
    seen = {name: set() for name in ('run_id', 'seed_id', 'seed_hex')}
    geometries, repeated = {}, {}
    extents = []
    for ordinal, item in enumerate(plan['captures']):
        path = f'plan.captures[{ordinal}]'
        item = _object(item, 'capture resources monitoring execution_budget', path)
        native_input = {key: item[key] for key in ('capture', 'resources', 'monitoring')}
        error = next(validator.iter_errors(native_input), None)
        native._require(error is None, path, '' if error is None else error.message)
        capture, resources, monitoring = (item[key] for key in ('capture', 'resources', 'monitoring'))
        position, repetition = divmod(FIRST_ORDINAL + ordinal, repetitions)
        cell, state, package, placement, working_set, _ = ordered_cells[position]
        for key, expected in (('ordinal', ordinal), ('cell_ordinal', cell), ('repetition_ordinal', repetition),
                              ('hardware_state', state), ('package', package), ('placement', placement),
                              ('working_set_class', working_set), ('measurement_ns', duration),
                              ('warmup_ns', WARMUP_NS), ('method_id', COLLECTOR_METHOD)):
            _constant(capture[key], expected, path + '.capture.' + key)
        for key, obj in (('resources', resources), ('monitoring', monitoring)):
            _constant(obj['ordinal'], ordinal, path + '.' + key + '.ordinal')
        for phase in ('warmup', 'measurement'):
            identity = capture[phase]
            for field in ('run_id', 'seed_id', 'namespace_id'):
                _text(identity[field], path + '.' + phase + '.' + field)
            _text(identity['seed_hex'], path + '.' + phase + '.seed_hex', r'[0-9a-f]{64}')
            _constant(identity['namespace_id'], plan[phase + '_namespace'], path + '.' + phase + '.namespace_id')
            for field, used in seen.items():
                native._require(identity[field] not in used, path, 'reused run/seed identity or seed value')
                used.add(identity[field])
        _constant(capture['arena_seed'], capture['measurement'], path + '.arena_seed')
        geometry = capture['geometry']
        _geometry(geometry, placement, path + '.geometry')
        geometry_key = package, placement, working_set
        if geometry_key in geometries:
            _constant(geometry, geometries[geometry_key], path + '.paired_geometry')
        geometries[geometry_key] = geometry
        native._package(capture, path)
        for role in ('producer', 'consumer'):
            stack = resources['workers'][role + '_stack']
            _constant(stack['owner_cpu'], geometry[role + '_cpu'], path + '.workers.' + role)
            _constant(stack['requested_node'], geometry[role + '_node'], path + '.workers.' + role)
        native._require(resources['controller_stack']['owner_cpu'] not in (geometry['producer_cpu'], geometry['consumer_cpu']),
                        path, 'controller shares a worker CPU')
        for index, phase in enumerate(capture['budget']['phases']):
            phase_ns = capture['warmup_ns'] if index == 0 else duration
            _product(phase['drain_ns'], 1000, path + '.drain_ticks')
            native._require(monitoring['during_offset_ticks'][index] < _product(phase_ns, 1000, path), path,
                            'during observation begins outside phase')
        invariant = {'budget': capture['budget'],
                     'resources': {k: v for k, v in resources.items() if k != 'ordinal'},
                     'monitoring': {k: v for k, v in monitoring.items() if k != 'ordinal'}}
        if cell in repeated:
            _constant(invariant, repeated[cell], path + '.repeated_bounds')
        repeated[cell] = invariant
        raw, largest, copy_floor = native._raw_extent(capture, resources, False, path)
        budget = native._budget(item['execution_budget'], native.CaptureBudget, path + '.execution_budget')
        known_time = _sum([budget.setup_ns, capture['warmup_ns'], duration,
                          *(phase['drain_ns'] for phase in capture['budget']['phases']),
                          budget.publication_ns, budget.cleanup_ns], path + '.required_watchdog_ns')
        native._require(known_time <= budget.watchdog_ns <= native.MAX_I64, path,
                        'watchdog omits time or exceeds signed native duration')
        mapping = resources['total_mapping_bytes']
        native._require(mapping <= capture['budget']['memory_bytes'], path, 'native mapping ceiling insufficient')
        native._require(budget.publication_memory_bytes >= copy_floor, path, 'publication copy floor omitted')
        memory = _sum([mapping, budget.publication_memory_bytes, budget.other_memory_bytes], path + '.memory')
        native._require(budget.memory_bytes >= memory, path, 'mapped/publication/other memory omitted')
        native._require(budget.max_output_bytes >= _sum([raw, budget.metadata_output_bytes], path + '.output'),
                        path, 'raw or metadata output omitted')
        extents.append(native.CaptureExtent(ordinal, raw, largest, mapping, known_time, budget))
    family = native._budget(plan['budget'], native.FamilyBudget, 'plan.budget')
    # cleanup_ns includes final family validation; archive time is added below.
    watchdog = _sum([family.setup_ns, family.cleanup_ns, *(e.declared.watchdog_ns for e in extents)], 'plan.watchdog')
    memory = _sum([family.controller_memory_bytes, max(e.declared.memory_bytes for e in extents)], 'plan.memory')
    output = _sum([family.metadata_output_bytes, *(e.declared.max_output_bytes for e in extents)], 'plan.output')
    storage = storage_v1.validate_storage_plan(
        plan['storage'], [e.declared for e in extents], family,
        native_family_watchdog_ns=watchdog, native_family_memory_bytes=memory,
        logical_output_bound_bytes=output)
    disk = storage.required_initial_free_bytes
    watchdog = storage.minimum_family_watchdog_ns
    memory = storage.minimum_family_memory_bytes
    for declared, required, label in ((family.watchdog_ns, watchdog, 'watchdog'),
                                      (family.memory_bytes, memory, 'memory'), (family.max_output_bytes, output, 'output'),
                                      (family.required_free_disk_bytes, disk, 'free disk')):
        native._require(declared >= required, 'plan.budget', label + ' omits declared component')
    native._require(family.watchdog_ns <= DAYCAP_NS, 'plan.budget', 'watchdog exceeds 24-hour family day cap')
    native._require(family.controller_memory_bytes >= len(canonicalize(plan).encode('utf-8')), 'plan.budget',
                    'controller cannot hold even canonical plan bytes')
    return FamilyExtent(tuple(extents), watchdog, memory, output, disk, family)


def validate_declaration(plan):
    """Check closed incident references, not the contents of those references."""
    from stage17_formal_ring_continuation_v1 import _path, _path_replacements
    native._no_floats(plan)
    validator = Draft202012Validator(json.loads((native.ROOT / SCHEMA).read_text()))
    error = next(validator.iter_errors(plan), None)
    native._require(error is None, 'continuation schema', '' if error is None else error.message)
    for key in ('parent_plan', 'failed_family_receipt', 'accepted_prefix_manifest', 'compatibility_manifest'):
        _path(plan['continuation'][key]['path'])
    _path_replacements(plan['continuation']['monitor_path_replacements'])
    native._require(plan['source_revision'] != PARENT_SOURCE, 'continuation source',
                    'new qualified native source required')


def _compare_parent(plan, parent):
    """Compare already authenticated declarations; retain both report histories."""
    from stage17_formal_ring_continuation_v1 import _path_replacements
    _constant(parent['source_revision'], PARENT_SOURCE, 'original qualified source')
    native._require(plan['plan_id'] != parent['plan_id'], 'continuation', 'fresh plan ID required')
    changed = {'schema_version', 'plan_id', 'source_revision', 'warmup_namespace',
               'measurement_namespace', 'captures', 'storage'}
    for key, value in parent.items():
        if key not in changed:
            _constant(plan[key], value, 'unchanged original '+key)
    expected_storage = copy.deepcopy(parent['storage'])
    expected_storage['implementation_profile_sha256'] = plan['storage']['implementation_profile_sha256']
    _constant(plan['storage'], expected_storage, 'unchanged shared program and storage bounds')
    old_ids = {c['capture'][phase][key] for c in parent['captures']
               for phase in ('warmup', 'measurement') for key in ('run_id', 'seed_id', 'namespace_id')}
    old_ids.update(c['capture']['linked_order'][key] for c in parent['captures']
        if c['capture']['linked_order'] is not None for key in ('seed_id', 'namespace_id'))
    replacements = _path_replacements(plan['continuation']['monitor_path_replacements'])
    used = set()
    for ordinal, item in enumerate(plan['captures']):
        original = parent['captures'][FIRST_ORDINAL+ordinal]
        expected = copy.deepcopy(original)
        for part in ('capture', 'resources', 'monitoring'):
            expected[part]['ordinal'] = ordinal
        for phase in ('warmup', 'measurement'):
            identity = item['capture'][phase]
            old = original['capture'][phase]
            _constant(identity['seed_hex'], old['seed_hex'], 'preserved original numeric seed')
            for key in ('run_id', 'seed_id', 'namespace_id'):
                native._require(identity[key] not in old_ids, 'continuation', 'original phase ID reused')
            native._require((4+len(identity['run_id'].encode())+7)//8
                            == (4+len(old['run_id'].encode())+7)//8,
                            'continuation', 'new run ID changes canonical record width')
            expected['capture'][phase] = copy.deepcopy(identity)
        expected['capture']['arena_seed'] = copy.deepcopy(item['capture']['measurement'])
        if original['capture']['linked_order'] is not None:
            linked = item['capture']['linked_order']
            _constant(linked['seed_hex'], original['capture']['linked_order']['seed_hex'],
                      'preserved original numeric node-order seed')
            for key in ('seed_id', 'namespace_id'):
                native._require(linked[key] not in old_ids, 'continuation', 'original node-order ID reused')
                expected['capture']['linked_order'][key] = linked[key]
        for source in expected['monitoring']['environment_sources']:
            if source['path'] in replacements:
                used.add(source['path'])
                source['path'] = replacements[source['path']]
        _constant(item, expected, 'unchanged original capture '+str(FIRST_ORDINAL+ordinal))
    _constant(sorted(used), sorted(replacements), 'all monitor replacements used')


def validate_parent(plan, original_plan_bytes):
    """Authenticate pinned parent bytes and preserve its prospective experiments."""
    import stage17_formal_service_daycap_v1 as original
    from stage17_formal_ring_continuation_v1 import _unique, _reject_constant
    extent = validate_plan(plan)
    native._require(type(original_plan_bytes) is bytes, 'continuation', 'exact parent bytes required')
    native._require(len(original_plan_bytes) == PARENT_SIZE
                    and hashlib.sha256(original_plan_bytes).hexdigest() == PARENT_SHA256,
                    'continuation', 'original incident plan differs')
    parent = json.loads(original_plan_bytes, object_pairs_hook=_unique, parse_constant=_reject_constant)
    original.validate_plan(parent)
    _compare_parent(plan, parent)
    return extent


def plan_bytes(plan):
    validate_plan(plan)
    return canonicalize(plan).encode('utf-8', errors='strict')
