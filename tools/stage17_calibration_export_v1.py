"""D237 analysis-only Stage17 calibration export, never execution authority.

Recompute from bound original report bytes; do not confuse byte identity with
authenticated provenance. This version cannot issue FROZEN: independent owner,
lifecycle, raw-validation and analysis-code admission remains an explicit gate.
It neither reads raw streams nor changes their producer release qualification.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
import re
import struct

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

import calibration_statistics as statistics
import stage17_formal_calibration_v1 as calibration
import stage17_formal_plan_v1 as plans

SCHEMA_ID = 'cpu-prefetch-stage17-calibration-freeze/1'
SCHEMA_PATH = Path(__file__).resolve().parents[1] / 'config/schemas/stage17-calibration-freeze-v1.schema.json'
ACTIONS = ('Q16a', 'Q16b', 'Q16c')
FINAL = dict(state='NOT_EVALUATED', passes=None, selected_global_scale=None,
             matrix_probability_lower=None, unresolved_inputs=['Rtotal', 'Nruns', 'N_sched'])
PROVENANCE_BLOCKERS = [
    'OWNER_AUTHORITY_PROVENANCE_NOT_ADMITTED',
    'SIGNED_LIFECYCLE_AND_RAW_VALIDATION_PROVENANCE_NOT_ADMITTED',
    'ANALYSIS_CODE_PROVENANCE_NOT_ADMITTED',
    'COMMON_MARGINAL_DESIGN_PROVENANCE_NOT_ADMITTED',
    'SCHEDULE_GENERATOR_AND_NAMESPACE_PROVENANCE_NOT_ADMITTED',
]


class ExportError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ExportError(message)


def exact(actual, expected, message):
    require(calibration.canonical(actual) == calibration.canonical(expected), message)


def fields(value, keys, label):
    require(type(value) is dict and set(value) == set(keys.split()), label + ' fields differ')
    return value


def uint(value):
    require(type(value) is int and 0 <= value <= calibration.MAX_U64, 'invalid uint64')
    return value


def packet(value, inventory):
    fields(value, 'binding utf8_bytes', 'source packet')
    bound = calibration._binding(value['binding'])
    raw = value['utf8_bytes']
    require(type(raw) is bytes, 'original UTF-8 bytes required')
    require(len(raw) == bound['size_bytes'] and hashlib.sha256(raw).hexdigest() == bound['sha256'],
            'source original size/SHA differs')
    require(bound['artifact_id'] not in inventory, 'ambiguous duplicate source artifact ID')
    doc = json.loads(raw.decode('utf-8'), object_pairs_hook=calibration._unique,
                     parse_constant=lambda _: (_ for _ in ()).throw(ExportError('nonfinite JSON')))
    require(type(doc) is dict, 'source JSON object required')
    calibration._strict(doc)
    inventory[bound['artifact_id']] = bound
    return doc, bound


def _reports(action, value, plan, inventory):
    require(type(value) is list, 'capture report sequence required')
    records = []; parsed = {}
    for row in value:
        fields(row, 'capture_ordinal measurement_run_id validity report', 'capture report input')
        ordinal = uint(row['capture_ordinal'])
        require(ordinal < len(plan['captures']) and ordinal not in parsed, 'duplicate/unplanned capture report')
        require(row['validity'] in ('VALID', 'INVALID'), 'invalid receipt decision')
        capture = plan['captures'][ordinal]['capture']
        exact(row['measurement_run_id'], capture['measurement']['run_id'], 'report run identity differs')
        doc, bound = packet(row['report'], inventory)
        parsed[ordinal] = (row['validity'], doc, bound)
        records.append(dict(capture_ordinal=ordinal, measurement_run_id=row['measurement_run_id'],
            validity=row['validity'], report_binding=bound,
            report_utf8_bytes=row['report']['utf8_bytes'].decode('utf-8')))
    return records, parsed


def _probe(plan, reports):
    try:
        return _probe_reports(plan, reports)
    except ExportError:
        raise
    except (KeyError, ValueError, TypeError, OverflowError) as error:
        raise ExportError(str(error)) from error


def _probe_reports(plan, reports):
    rows = []; blockers = []
    for item in plan['captures']:
        capture = item['capture']; ordinal = capture['ordinal']
        entry = reports.get(ordinal)
        base = dict(capture_ordinal=ordinal, cell_ordinal=capture['cell_ordinal'],
                    measurement_run_id=capture['measurement']['run_id'],
                    repetition_ordinal=capture['repetition_ordinal'])
        if entry is None:
            rows.append(dict(base, validity='MISSING', report_binding=None, counts=None))
            blockers.append(f'Q16c capture {ordinal} MISSING')
            continue
        validity, report, bound = entry
        if validity == 'INVALID':
            # D230's failure grammar is action-generic; Q16c additionally binds
            # two prepared schedules, giving seven raw artifacts in all.
            fields(report, 'schema_version action_id method_id capture_ordinal warmup_run_id measurement_run_id '
                   'plan_sha256 source_revision error input_bindings execution_authority phase18_authority', 'probe failure')
            exact(report['schema_version'], calibration.FAILURE_SCHEMA_ID, 'failure schema')
            exact(report['action_id'], 'Q16c', 'failure action')
            exact(report['method_id'], plans.METHOD['Q16c'], 'failure method')
            exact(report['capture_ordinal'], ordinal, 'failure ordinal')
            for name in ('warmup', 'measurement'):
                exact(report[name + '_run_id'], capture[name]['run_id'], 'failure phase identity')
            exact(report['source_revision'], plan['source_revision'], 'failure source revision')
            exact(report['plan_sha256'], hashlib.sha256(calibration.canonical(plan)).hexdigest(), 'failure plan hash')
            calibration._no_authority(report)
            fields(report['error'], 'type message', 'failure error')
            require(all(type(v) is str and v for v in report['error'].values()), 'failure error absent')
            inputs = fields(report['input_bindings'], 'native_input control final raw_artifacts', 'failure sources')
            require(type(inputs['raw_artifacts']) is list and len(inputs['raw_artifacts']) == 7,
                    'probe failure must bind all seven raw artifacts')
            bindings = [calibration._binding(inputs[k]) for k in ('native_input', 'control', 'final')]
            bindings += [calibration._binding(b) for b in inputs['raw_artifacts']]
            require(len({b['artifact_id'] for b in bindings}) == len(bindings), 'duplicate failure source')
            rows.append(dict(base, validity='INVALID', report_binding=bound, counts=None))
            blockers.append(f'Q16c capture {ordinal} INVALID')
            continue
        exact(report['schema_version'], calibration.REPORT_SCHEMA['Q16b'], 'D229 schema required')
        exact(report['action_id'], 'Q16c', 'D229 action differs')
        exact(report['method_id'], plans.METHOD['Q16c'], 'D036 method differs')
        exact(report['capture_ordinal'], ordinal, 'D229 ordinal differs')
        calibration._no_authority(report)
        for key in ('raw_reconciliation_validated', 'capture_execution_evidence_validated'):
            exact(report[key], True, 'D229 evidence flag differs')
        exact(report['family_validity_established'], False, 'per-capture report claims family validity')
        require(type(report['phases']) is list and len(report['phases']) == 2, 'both probe phases required')
        require(type(report['schedules']) is list and len(report['schedules']) == 2,
                'both prepared schedule summaries required')
        nodes = fields(report['node_order'], 'count sha256', 'node order summary')
        exact(nodes['count'], capture['geometry']['capacity'] + 1
              if capture['package'] in ('L0', 'L1') else 0, 'node order extent differs')
        require(type(nodes['sha256']) is str and re.fullmatch('[0-9a-f]{64}', nodes['sha256']),
                'node order hash absent')
        counts = []
        for index, name in enumerate(('warmup', 'measurement')):
            phase = report['phases'][index]
            exact(phase['phase'], name, 'probe phase differs')
            exact(phase['run_id'], capture[name]['run_id'], 'probe run ID differs')
            values = calibration._phase_counts(phase)
            require(set(phase['stream_sha256']) == {'producer', 'consumer'}, 'probe primary hashes absent')
            offered = uint(values['offered'])
            exact(offered, values['attempted'], 'one attempt per offered arrival')
            exact(offered, capture['schedules'][index]['offered_count'], 'offered differs from prospective source')
            limits = item['resources']['phase_capacity'][index]
            require(offered <= capture['budget']['phases'][index]['producer_attempt_limit']
                    and offered <= limits['producer_primary_rows']
                    and values['accepted'] <= limits['consumer_primary_rows'],
                    'probe counts exceed prospective bounds')
            schedule = fields(report['schedules'][index],
                'offered source_sha256 actual_phase_origin_ticks source_origin_ticks', 'prepared schedule summary')
            source = capture['schedules'][index]
            exact(schedule['offered'], offered, 'prepared source offered differs')
            exact(schedule['source_origin_ticks'], source['source_origin_ticks'], 'source origin differs')
            uint(schedule['actual_phase_origin_ticks'])
            digest = hashlib.sha256()
            for tick in source['deadline_ticks']:
                digest.update(struct.pack('<Q', tick))
            exact(schedule['source_sha256'], digest.hexdigest(), 'prepared schedule vector hash differs')
            # D229 reports the prepared u64 vector, not the accepted generator
            # artifact/envelope. D232 admission remains an explicit blocker.
            require(index == 0 or offered > 0, 'zero-offered measurement is ineligible')
            counts.append(dict(offered=offered, accepted=values['accepted'], full=values['full'],
                               consumed_including_drain=values['consumed_including_drain']))
        exact(report['measurement_zero_loss'], counts[1]['full'] == 0, 'probe measurement zero loss differs')
        exact(report['zero_loss_all_phases'], all(c['full'] == 0 for c in counts), 'probe all-phase zero loss differs')
        rows.append(dict(base, validity='VALID', report_binding=bound, counts=counts))
    return dict(method_id=plans.METHOD['Q16c'], scale_ordinal=plan['scale_ordinal'],
                repetitions_per_cell=plan['repetitions_per_cell'], planned_captures=len(rows),
                coverage_state='COMPLETE' if not blockers else 'UNRESOLVED',
                inference_state='NOT_EVALUATED', run_sources=rows), blockers


def build_export(*, identity, owner_decision, source_packets):
    """Build an explicitly unresolved export with independently checked inputs.

source_packets has plans(Q16a/b/c), calibrations(Q16a/b), capture_reports(Q16a/b/c),
geometry_sources(6), lifecycle(Q16a/b/c), probe_design and analysis_provenance.
Opaque provenance packets are bound and retained, never treated as admission.
"""
    try:
        return _build(identity, owner_decision, source_packets)
    except ExportError:
        raise
    except (KeyError, ValueError, TypeError, OverflowError, ValidationError) as error:
        raise ExportError(str(error)) from error


def _build(identity, owner_decision, sources):
    fields(identity, 'record_id stand_id source_revision created_at_utc', 'export identity')
    for key in ('record_id', 'stand_id'):
        require(type(identity[key]) is str and bool(identity[key]), 'empty export identity')
    require(type(identity['source_revision']) is str and re.fullmatch('[0-9a-f]{40}', identity['source_revision']),
            'producer source revision must be explicit')
    require(type(identity['created_at_utc']) is str and identity['created_at_utc'].endswith('Z'), 'UTC creation time required')
    datetime.datetime.fromisoformat(identity['created_at_utc'].replace('Z', '+00:00'))
    fields(sources, 'plans calibrations capture_reports geometry_sources lifecycle probe_design analysis_provenance', 'source packets')
    fields(sources['plans'], 'Q16a Q16b Q16c', 'plans')
    fields(sources['calibrations'], 'Q16a Q16b', 'calibrations')
    fields(sources['capture_reports'], 'Q16a Q16b Q16c', 'reports')
    fields(sources['lifecycle'], 'Q16a Q16b Q16c', 'lifecycle')
    inventory = {}; blockers = list(PROVENANCE_BLOCKERS)
    _, owner = packet(owner_decision, inventory)
    documents = {}; plan_bindings = {}; parsed = {}; records = {}
    run_ids = set()
    for action in ACTIONS:
        plan, bound = packet(sources['plans'][action], inventory)
        plans.validate_plan(action, plan)
        for key in ('stand_id', 'source_revision'):
            exact(plan[key], identity[key], 'plan producer/stand differs')
        for item in plan['captures']:
            for phase in ('warmup', 'measurement'):
                run_id = item['capture'][phase]['run_id']
                require(run_id not in run_ids, 'run ID reused across formal families')
                run_ids.add(run_id)
        documents[action] = plan; plan_bindings[action] = bound
        records[action], parsed[action] = _reports(action, sources['capture_reports'][action], plan, inventory)

    original = {}; calibration_bindings = {}
    for action in ('Q16a', 'Q16b'):
        original[action], calibration_bindings[action] = packet(sources['calibrations'][action], inventory)
        calibration.validate_calibration_record(original[action])
    geometry = original['Q16a']['ring_geometry']
    require(type(sources['geometry_sources']) is list and len(sources['geometry_sources']) == 6,
            'all six geometry source packets required')
    for item, expected in zip(sources['geometry_sources'], geometry, strict=True):
        document, bound = packet(item, inventory)
        exact(bound, expected['source_binding'], 'native geometry source binding differs')
        # This adapter binds original source bytes, but does not turn arbitrary
        # layout JSON into authenticated native geometry evidence.
    blockers.append('NATIVE_GEOMETRY_PROVENANCE_NOT_ADMITTED')
    for action in ('Q16a', 'Q16b'):
        recomputed = calibration.evaluate(action, documents[action], records[action],
                                         geometry if action == 'Q16a' else None)
        exact(original[action], recomputed, 'D230 record differs from original report recomputation')
        if recomputed['status'] != 'VALIDATED':
            blockers.append(action + '_CALIBRATION_UNRESOLVED')
    for action in ('Q16b', 'Q16c'):
        for item in documents[action]['captures']:
            capture = item['capture']
            if capture['package'] not in ('R0', 'R1', 'R2'):
                continue
            context = (0 if capture['placement'] == 'NEAR' else 3) + plans.WORKING_SETS.index(capture['working_set_class'])
            expected = geometry[context]
            for key in ('capacity', 'cache_line_bytes'):
                exact(capture['geometry'][key], expected[key], 'later ring geometry differs from Q16a')
            distance = original['Q16a']['derived_result']['contexts'][context]['distance']
            if capture['package'] == 'R2':
                require(distance is not None and distance['d2_cache_lines'] is not None, 'unresolved Q16a cannot supply R2')
                exact(capture['ring_distance'], dict(cache_lines=distance['d2_cache_lines'],
                    calibration_evidence_id='q16a-sha256-' + calibration_bindings['Q16a']['sha256']),
                    'R2 distance/source binding differs')

    probe, probe_blockers = _probe(documents['Q16c'], parsed['Q16c'])
    blockers += probe_blockers
    provenance = {}
    for action in ACTIONS:
        _, provenance[action] = packet(sources['lifecycle'][action], inventory)
    _, design = packet(sources['probe_design'], inventory)
    _, analysis = packet(sources['analysis_provenance'], inventory)
    result = dict(schema_version=SCHEMA_ID, protocol_version='2.0.0-pre.3', scope='STAGE17_EXT007',
        **identity, state='UNRESOLVED', owner_decision=owner, plan_bindings=plan_bindings,
        calibration_bindings=calibration_bindings, lifecycle_bindings=provenance,
        probe_design_binding=design, analysis_provenance_binding=analysis,
        source_bindings=sorted(inventory.values(), key=lambda b: b['artifact_id']),
        outputs=dict(q16a=original['Q16a']['derived_result'], ring_geometry=geometry,
                     q16b=original['Q16b']['derived_result'], service_rate_unit='EVENTS_PER_SECOND', q16c=probe),
        final_matrix_feasibility=dict(FINAL), blockers=blockers,
        execution_authority=False, phase18_authority=False)
    sealed, _ = statistics.seal_record(result)
    Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(sealed)
    return sealed


def validate_export(document, *, owner_decision, source_packets):
    """Recompute the entire export from original packets, never promote authority."""
    try:
        Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(document)
        identity = {key: document[key] for key in ('record_id', 'stand_id', 'source_revision', 'created_at_utc')}
        expected = build_export(identity=identity, owner_decision=owner_decision, source_packets=source_packets)
        exact(document, expected, 'export differs from independently recomputed original source packets')
        return document
    except ExportError:
        raise
    except (KeyError, ValueError, TypeError, ValidationError) as error:
        raise ExportError(str(error)) from error
