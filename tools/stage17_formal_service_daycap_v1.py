"""D254 Q16b declaration and descriptive arithmetic, without execution authority.

Exactly two planned runs for each of 60 cells replace the historical 59-run
tolerance guarantee. The family deadline includes native work, cold archival
work and final validation (reserved in family cleanup_ns). It is a declared
ceiling, not proof that collection or validation will finish within a day.

Capture method IDs identify the unchanged legacy collector format only. Bound
report bytes support descriptive arithmetic; their provenance, independence,
hardware qualification and family acceptance require separate authentication.
"""
from __future__ import annotations

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

VERSION = 'cpu-prefetch-stage17-formal-service-plan/3'
METHOD = 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1'
COLLECTOR_METHOD = 'SERVICE-RATE-NP-LTL95C95-MIN-v1'
SCHEMA = 'config/schemas/stage17-formal-service-plan-v3.schema.json'
SCHEMA_ID = 'cpu-prefetch-stage17-formal-service-descriptive/1'
DAYCAP_NS = 24 * 60 * 60 * 1_000_000_000
REPETITIONS = 2
MEASUREMENT_NS = 1_000_000_000
WARMUP_NS = 5_000_000_000
FamilyExtent = native.FamilyExtent
CalibrationError = capture_reports.CalibrationError


def validate_plan(document) -> FamilyExtent:
    """Recompute original native/storage bounds over the actual 120 entries.

    Private static service-only snapshot of formal_plan_v1._validate_plan,
    with family/collector identity split and the D254 exact duration, coverage
    and day cap. No projection, invented repetitions or historical rebinding.
    The caller's original document and all its bindings remain unchanged.
    """
    native._no_floats(document)
    plan = _object(document,
        'schema_version plan_id protocol_version action_id method_id source_revision clean_source '
        'stand_id repetitions_per_cell measurement_ns warmup_namespace measurement_namespace '
        'custody_policy_id captures budget storage', 'plan')
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
    count = _product(len(ordered_cells), repetitions, 'plan.capture_count')
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
        position, repetition = divmod(ordinal, repetitions)
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


def plan_bytes(document):
    """Original native canonical plan identity, without a trailing LF."""
    validate_plan(document)
    return canonicalize(document).encode('utf-8', errors='strict')


def evaluate(plan, run_records):
    """Describe the fixed family from bound original per-capture reports.

    Input records use the D230 record envelope, including original report text,
    size and SHA256. Only the legacy per-capture checks are reused; no legacy
    family estimator or tolerance method is invoked. Missing/invalid captures
    remain unresolved, and duplicate/unplanned captures are rejected.
    """
    try:
        plan_hash = hashlib.sha256(plan_bytes(plan)).hexdigest()
        capture_reports._strict(run_records)
        capture_reports.require(type(run_records) is list, 'run_records must be a finite list')
        indexed = {}
        for record in run_records:
            _object(record, 'capture_ordinal measurement_run_id validity report_binding report_utf8_bytes', 'run record')
            ordinal = _uint(record['capture_ordinal'], 'record ordinal')
            capture_reports.require(ordinal < len(plan['captures']) and ordinal not in indexed,
                                    'duplicate or unplanned run; no top-up')
            capture = plan['captures'][ordinal]['capture']
            _constant(record['measurement_run_id'], capture['measurement']['run_id'], 'record planned run ID')
            capture_reports.require(record['validity'] in ('VALID', 'INVALID'), 'explicit report validity required')
            indexed[ordinal] = record
        sources = []
        for ordinal, item in enumerate(plan['captures']):
            capture = item['capture']
            row = dict(capture_ordinal=ordinal, warmup_run_id=capture['warmup']['run_id'],
                       measurement_run_id=capture['measurement']['run_id'], validity='MISSING',
                       report_binding=None, summary=None, failure=None)
            if ordinal in indexed:
                record = indexed[ordinal]
                report, binding = capture_reports._report(record)
                row.update(validity=record['validity'], report_binding=binding)
                if record['validity'] == 'VALID':
                    row['summary'] = capture_reports._valid_summary('Q16b', report, capture, item['resources'])
                else:
                    row['failure'] = capture_reports._failure(report, 'Q16b', plan_hash, plan, capture)
            sources.append(row)
        cells = []
        complete = True
        minima: list[Fraction] = []
        for position, (cell, state, package, placement, working_set, _) in enumerate(native.cells('Q16b')):
            rows = sources[position * REPETITIONS:(position + 1) * REPETITIONS]
            valid = [row for row in rows if row['validity'] == 'VALID']
            missing = sum(row['validity'] == 'MISSING' for row in rows)
            mu = None
            if len(valid) == REPETITIONS:
                mu = min(capture_reports._fraction(row['summary']['throughput']) for row in valid)
                minima.append(mu)
            else:
                complete = False
            cells.append(dict(cell_ordinal=cell, hardware_state=state, package=package,
                              placement=placement, working_set_class=working_set, planned_runs=REPETITIONS,
                              present_runs=REPETITIONS - missing, valid_runs=len(valid), missing_runs=missing,
                              invalid_runs=sum(row['validity'] == 'INVALID' for row in rows),
                              min_mu_cell=None if mu is None else capture_reports._rational(mu)))
        minimum = min(minima) if complete else None
        # Fractions remain exact, including genuine 0/1; no positive floor.
        return dict(schema_version=SCHEMA_ID, action_id='Q16b', method_id=METHOD,
                    collector_method_id=COLLECTOR_METHOD, plan_sha256=plan_hash,
                    stand_id=plan['stand_id'], source_revision=plan['source_revision'],
                    status='DESCRIPTIVE' if complete else 'UNRESOLVED',
                    prospective=dict(repetitions=REPETITIONS, measurement_ns=MEASUREMENT_NS),
                    run_sources=sources, derived_result=dict(
                        cells=sorted(cells, key=lambda row: row['cell_ordinal']),
                        min_mu_ref=None if minimum is None else capture_reports._rational(minimum),
                        measurement_zero_loss_gate=capture_reports._gate(sources, 1),
                        warmup_zero_loss_gate=capture_reports._gate(sources, 0)),
                    descriptive_summary_complete=complete, tolerance_claim=None, tolerance_guarantee=False,
                    report_provenance_authenticated=False, independent_runs_authenticated=False,
                    family_validity_established=False, execution_authority=False, phase18_authority=False)
    except CalibrationError:
        raise
    except (ContractError, KeyError, TypeError, ValueError, OverflowError, UnicodeError,
            capture_reports.raw.DecodeError) as error:
        raise CalibrationError('descriptive evaluation rejected: ' + str(error)) from error
