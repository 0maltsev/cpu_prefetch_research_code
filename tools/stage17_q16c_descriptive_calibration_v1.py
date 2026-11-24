"""D270 descriptive coverage/count composition; no D036 inference or authority.

Input report bytes must come from independently authenticated raw validation.
This function verifies their exact bindings and normalized arithmetic; it does
not prove their author, raw custody, source compatibility or execution lineage.
"""
from __future__ import annotations
import hashlib
import re

import stage17_formal_archive_v1 as archive
import stage17_formal_scheduled_descriptive_v1 as contract
import stage17_formal_scheduled_capture_validation_v2 as raw_validator
import stage17_q16a_continuation_admission_v1 as admission

SCHEMA = 'cpu-prefetch-stage17-q16c-descriptive-calibration/1'
Error = admission.AdmissionError
require, same, fields = admission.require, admission.same, admission.fields


def uint(value):
    require(type(value) is int and 0 <= value < 2**64, 'exact unsigned64 count required')
    return value


def _report(record, capture):
    fields(record, 'capture_ordinal validity report_binding report_utf8_bytes', 'Q16c report source')
    same(record['validity'], 'VALID', 'required independent report validity')
    bound, raw = record['report_binding'], record['report_utf8_bytes']
    fields(bound, 'artifact_id size_bytes sha256', 'report binding')
    require(type(bound['artifact_id']) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}', bound['artifact_id']),
            'report artifact identity required')
    require(type(raw) is bytes and 0 < len(raw) <= 1024**2, 'bounded report bytes required')
    same(bound['size_bytes'], len(raw), 'original report size')
    same(bound['sha256'], hashlib.sha256(raw).hexdigest(), 'original report hash')
    report = admission._json(raw)
    for name, expected in dict(schema_version=raw_validator.SCHEMA_ID, action_id='Q16c',
            method_id=contract.COLLECTOR_METHOD, capture_ordinal=capture['ordinal'],
            raw_reconciliation_validated=True, capture_execution_evidence_validated=True,
            family_validity_established=False, execution_authority=False, phase18_authority=False).items():
        same(report[name], expected, 'independent capture ' + name)
    same(report['source_versions'], raw_validator.SOURCE_VERSIONS, 'independent validator source identities')
    require(type(report['phases']) is list and len(report['phases']) == 2, 'two actual independent phases')
    phases = []
    for i, phase_name in enumerate(('warmup', 'measurement')):
        phase = report['phases'][i]
        same(phase['phase'], phase_name, 'phase identity')
        same(phase['run_id'], capture[phase_name]['run_id'], 'original phase run identity')
        counts = phase['counts']
        fields(counts, 'attempted accepted full consumed_including_drain offered', 'normalized scheduled counts')
        for value in counts.values(): uint(value)
        same(counts['offered'], capture['schedules'][i]['offered_count'], 'prospective original offered count')
        same(counts['attempted'], counts['offered'], 'one attempt per original arrival')
        same(counts['accepted'] + counts['full'], counts['attempted'], 'all producer outcomes retained')
        same(counts['consumed_including_drain'], counts['accepted'], 'independent complete consumer reconciliation')
        same(phase['zero_loss'], counts['full'] == 0, 'observed phase zero loss')
        phases.append(dict(phase=phase_name, run_id=phase['run_id'], counts=dict(counts), zero_loss=phase['zero_loss']))
    same(report['measurement_zero_loss'], phases[1]['zero_loss'], 'measurement gate')
    same(report['zero_loss_all_phases'], all(p['zero_loss'] for p in phases), 'all-phase gate')
    return dict(capture_ordinal=capture['ordinal'], cell_ordinal=capture['cell_ordinal'],
        report_binding=dict(bound), validity='VALID', phases=phases)


def evaluate(plan, run_records):
    """All required cells or an explicit incomplete result; no automatic repeats."""
    contract.validate_plan(plan)
    require(type(run_records) is list and len(run_records) <= 180, 'bounded actual report list required')
    indexed, bindings = {}, set()
    for row in run_records:
        fields(row, 'capture_ordinal validity report_binding report_utf8_bytes', 'run record')
        ordinal = uint(row['capture_ordinal'])
        require(ordinal < 180 and ordinal not in indexed, 'duplicate or unplanned report ordinal')
        require(row['validity'] in ('VALID', 'INVALID', 'MISSING'), 'unknown report validity')
        if row['validity'] == 'VALID':
            result = _report(row, plan['captures'][ordinal]['capture'])
            artifact_id = result['report_binding']['artifact_id']
            require(artifact_id not in bindings, 'duplicate report artifact identity')
            bindings.add(artifact_id)
        else:
            bound, raw = row['report_binding'], row['report_utf8_bytes']
            if row['validity'] == 'MISSING':
                require(bound is None and raw is None, 'missing capture invents a report')
            else:
                # Retain invalid evidence, but never admit its counts or silently
                # convert it to a valid result. Its failure receipt is caller-owned.
                require(type(raw) is bytes and 0 < len(raw) <= 1024**2 and type(bound) is dict,
                        'invalid capture must retain its bound failure evidence')
                fields(bound, 'artifact_id size_bytes sha256', 'invalid evidence binding')
                same(bound['size_bytes'], len(raw), 'invalid evidence size')
                same(bound['sha256'], hashlib.sha256(raw).hexdigest(), 'invalid evidence hash')
            result = dict(capture_ordinal=ordinal, cell_ordinal=plan['captures'][ordinal]['capture']['cell_ordinal'],
                          report_binding=bound, validity=row['validity'], phases=None)
        indexed[ordinal] = result
    rows = [indexed.get(i, dict(capture_ordinal=i, cell_ordinal=plan['captures'][i]['capture']['cell_ordinal'],
            report_binding=None, validity='MISSING', phases=None)) for i in range(180)]
    valid = [r for r in rows if r['validity'] == 'VALID']
    complete = len(valid) == 180
    gates = {}
    for i, phase in enumerate(('warmup', 'measurement')):
        full = [r['capture_ordinal'] for r in valid if not r['phases'][i]['zero_loss']]
        gates[phase] = dict(zero_loss_gate='FAIL' if full else ('PASS' if complete else 'NOT_ESTABLISHED'),
                           full_bearing_capture_ordinals=full)
    return dict(schema_version=SCHEMA, action_id='Q16c', method_id=contract.METHOD,
        collector_method_id=contract.COLLECTOR_METHOD, stand_id=plan['stand_id'],
        source_revision=plan['source_revision'], plan_sha256=hashlib.sha256(archive.canonical(plan)).hexdigest(),
        status='DESCRIPTIVE_COMPLETE' if complete else 'INCOMPLETE',
        prospective=dict(settings=180, repetitions_per_cell=1, measurement_ns=1_000_000_000,
                         warmup_ns=5_000_000_000, scale_ordinal=0),
        coverage=dict(planned=180, valid=len(valid), invalid=sum(r['validity']=='INVALID' for r in rows),
                      missing=sum(r['validity']=='MISSING' for r in rows)),
        run_sources=rows, observed_zero_loss=gates, evidence_strength='DESCRIPTIVE_SINGLE_CAPTURE_PER_SETTING',
        confidence_claim=None, inferential_validity_established=False,
        final_matrix_feasibility='NOT_EVALUATED', final_scale_selection=None,
        execution_authority=False, phase18_authority=False)
