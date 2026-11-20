"""D307 exact audited calibration data freeze, without execution authority.

This incident-bound format retains all original methods and source populations.
Operational admission must separately authenticate its producer and provenance.
"""
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

import stage17_q16a_continuation_admission_v1 as admission
import stage17_formal_calibration_v1 as mathematics
import stage17_formal_service_daycap_v1 as service

SCHEMA = 'cpu-prefetch-stage17-ext007-descriptive-freeze/1'
SCHEMA_PATH = 'config/schemas/stage17-ext007-descriptive-freeze-v1.schema.json'
SCOPE = 'STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY'
ACCEPTED = {
    'Q16a': (629535, '3c84e5436cedf2e513b28be3f7dc44fa6f44afc3632a728eb3b82d66be89192f'),
    'Q16b': (103724, '3894bf7d0d5223b50326d718815b8a7d106fe395dde2868fe3e06a271d754393'),
    'Q16c': (180045, 'b866590bbbe2bd779ac30bc686ce31dbb6822d02f9f30ec0a3c8119f63898418'),
}
COUNTS = {'Q16a': 708, 'Q16b': 120, 'Q16c': 180}
require, same, fields = admission.require, admission.same, admission.fields


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def project(results):
    """Check report identity/arithmetic and retain the original scientific claims."""
    fields(results, 'Q16a Q16b Q16c', 'all calibration results')
    a, b, c = (results[k] for k in COUNTS)
    same(a['schema_version'], 'cpu-prefetch-stage17-q16a-composite-calibration/1', 'Q16a format')
    same(a['status'], 'VALIDATED', 'Q16a complete')
    same(a['method_id'], mathematics.METHOD['Q16a'], 'Q16a original method')
    same(a['prospective'], dict(repetitions=59, measurement_ns=10**9, minimum_observations_per_series=100000), 'Q16a original design')
    same(b['schema_version'], 'cpu-prefetch-stage17-formal-service-continuation-descriptive/1', 'Q16b format')
    same(b['status'], 'DESCRIPTIVE', 'Q16b descriptive status')
    same(b['method_id'], 'SERVICE-RATE-DESCRIPTIVE-MIN2-DAYCAP-v1', 'Q16b descriptive method')
    same(b['prospective'], dict(repetitions=2, measurement_ns=10**9), 'Q16b original design')
    same(b['tolerance_guarantee'], False, 'no59-run tolerance guarantee')
    same(c['schema_version'], 'cpu-prefetch-stage17-q16c-descriptive-platform-strata/1', 'Q16c format')
    same(c['method_id'], 'MATRIX-FULL-DESCRIPTIVE-CONTINUED-PLATFORM-STRATA-v1', 'Q16c descriptive method')
    same(c['status'], 'DESCRIPTIVE_COMPLETE', 'Q16c complete')
    same(c['coverage'], dict(planned=180, valid=180, retained=86, new=94, missing=0, invalid=0), 'Q16c complete coverage')
    same(c['prospective'], dict(settings=180, repetitions_per_cell=1, warmup_ns=5*10**9, measurement_ns=10**9, scale_ordinal=0), 'Q16c original design')
    same(c['platform_strata'], [dict(regime='UNRECORDED', captures=86), dict(regime='VERIFIED_ZERO', captures=94)], 'actual platform strata')
    same(c['homogeneous_platform_evidence'], False, 'no homogeneous-platform inference')
    same(c['inferential_validity_established'], False, 'no Q16c confidence promotion')
    same(c['confidence_claim'], None, 'no Q16c confidence claim')
    same(c['final_matrix_feasibility'], 'NOT_EVALUATED', 'unresolved final feasibility')
    same(c['final_scale_selection'], None, 'unresolved final scale')
    ids = set(); reports = set()
    for phase, result in results.items():
        same(result['action_id'], phase, 'original action identity')
        same(result['stand_id'], a['stand_id'], 'same actual stand')
        for flag in ('execution_authority', 'phase18_authority'):
            same(result[flag], False, 'original false authority '+flag)
        rows = result['run_sources']; require(len(rows) == COUNTS[phase], 'complete '+phase+' coverage')
        for ordinal, row in enumerate(rows):
            key = 'original_slot' if phase == 'Q16a' else 'original_capture_ordinal' if phase == 'Q16b' else 'original_ordinal'
            same(row[key], ordinal, 'original report ordinal')
            same(row['validity'], 'VALID', 'actual per-report validity')
            report = row['report_binding']; fields(report, 'artifact_id size_bytes sha256', 'original report identity')
            require(report['artifact_id'] not in reports, 'report identity reused across families'); reports.add(report['artifact_id'])
            require(type(report['size_bytes']) is int and report['size_bytes'] > 0 and re.fullmatch('[0-9a-f]{64}', report['sha256']), 'bounded report identity')
            run_ids = [row[k] for k in ('warmup_run_id','measurement_run_id')] if phase != 'Q16c' else [p['run_id'] for p in row['phases']]
            require(len(run_ids) == 2, 'both original phases')
            for run in run_ids:
                require(type(run) is str and run and run not in ids, 'phase identity reused across families'); ids.add(run)
            if phase != 'Q16c': mathematics._check_summary(phase, row['summary'], result['prospective'])
    require(len(ids) == 2016 and len(reports) == 1008, 'exact combined report and phase identities')
    for flag in ('family_validity_established','producer_authentication_established'):
        same(a[flag], False, 'preserve Q16a mathematical boundary '+flag)
    status, derived = mathematics._derive('Q16a', a['prospective'], a['run_sources'], a['ring_geometry'])
    same(status, a['status'], 'Q16a recomputed status'); same(derived, a['derived_result'], 'exact Q16a arithmetic')
    require(len(a['source_populations']) == len(b['source_populations']) == 2, 'actual two-source populations')
    for flag in ('family_validity_established','report_provenance_authenticated','independent_runs_authenticated'):
        same(b[flag], False, 'preserve Q16b mathematical boundary '+flag)
    cells = b['derived_result']['cells']; require(len(cells) == 60, 'all60 service cells')
    # Capture order follows the accepted plan enumeration; displayed cells are
    # sorted by ID. Those orders differ, so an ID is not a capture offset.
    positions = {cell:position for position,(cell,*_) in enumerate(service.native.cells('Q16b'))}
    minima = []
    for ordinal, cell in enumerate(cells):
        same(cell['cell_ordinal'], ordinal, 'ordered service cell')
        position = positions[ordinal]
        values = [mathematics._fraction(row['summary']['throughput']) for row in b['run_sources'][position*2:position*2+2]]
        minimum = min(values); minima.append(minimum)
        same([cell['valid_runs'],cell['missing_runs'],cell['invalid_runs']], [2,0,0], 'complete paired service cell')
        same(cell['min_mu_cell'], mathematics._rational(minimum), 'exact descriptive cell minimum')
    minimum = min(minima)
    same(b['derived_result']['min_mu_ref'], mathematics._rational(minimum), 'exact descriptive global minimum')
    same(b['derived_result']['min_mu_ref'], dict(numerator=1670571, denominator=1), 'audited observed minimum')
    for result in (a,b):
        for name, index in (('warmup_zero_loss_gate',0),('measurement_zero_loss_gate',1)):
            same(result['derived_result'][name], mathematics._gate(result['run_sources'],index), 'separate original zero-loss gate')
    for index, phase in enumerate(('warmup','measurement')):
        full = []
        for ordinal, row in enumerate(c['run_sources']):
            value = row['phases'][index]; same(value['phase'], phase, 'Q16c phase order')
            counts = value['counts']; fields(counts, 'attempted accepted full consumed_including_drain offered', 'scheduled counts')
            require(all(type(n) is int and 0 <= n < 2**64 for n in counts.values()), 'actual unsigned counts')
            same(counts['attempted'], counts['offered'], 'one scheduled attempt per arrival')
            same(counts['accepted']+counts['full'], counts['attempted'], 'all scheduled producer outcomes')
            same(counts['consumed_including_drain'], counts['accepted'], 'independent complete consumer drain')
            same(value['zero_loss'], counts['full'] == 0, 'observed zero loss')
            if counts['full']: full.append(ordinal)
            same(row['platform']['regime'], 'UNRECORDED' if ordinal < 86 else 'VERIFIED_ZERO', 'actual per-capture stratum')
        same(c['observed_zero_loss'][phase], dict(zero_loss_gate='FAIL' if full else 'PASS', full_bearing_original_ordinals=full), 'Q16c separate zero-loss gate')
    return dict(q16a=dict(method_id=a['method_id'], prospective=a['prospective'], source_populations=a['source_populations'],
                         ring_geometry=a['ring_geometry'], derived_result=a['derived_result']),
        q16b=dict(method_id=b['method_id'], collector_method_id=b['collector_method_id'], prospective=b['prospective'],
                  source_populations=b['source_populations'], tolerance_guarantee=False, tolerance_claim=b['tolerance_claim'],
                  evidence_strength='DESCRIPTIVE_OBSERVED_MINIMUM', derived_result=b['derived_result'],
                  base_rates={k:mathematics._rational(minimum*f) for k,f in
                              (('L025',Fraction(1,4)),('L050',Fraction(1,2)),('L075',Fraction(3,4)))}),
        q16c={key:c[key] for key in ('method_id','collector_method_id','prospective','coverage','platform_strata',
            'homogeneous_platform_evidence','observed_zero_loss','evidence_strength','confidence_claim',
            'inferential_validity_established','final_matrix_feasibility','final_scale_selection')})


def build(*, record_id, created_at_utc, source_records, provenance_record, predecessor_resolutions):
    import datetime as dt
    require(type(record_id) is str and record_id and '\n' not in record_id, 'explicit record identity')
    require(type(created_at_utc) is str and created_at_utc.endswith('Z'), 'explicit UTC creation time')
    stamp = dt.datetime.fromisoformat(created_at_utc.replace('Z','+00:00'))
    require(stamp.utcoffset() == dt.timedelta(0), 'actual UTC time')
    fields(source_records, 'Q16a Q16b Q16c', 'all original composition sources')
    require(type(predecessor_resolutions) is list and [p['input_id'] for p in predecessor_resolutions] ==
            [f'S17-EXT-{i:03d}' for i in range(1,7)], 'exact six qualification predecessors')
    reader = admission.BoundReader(); results = {}
    for phase, expected in ACCEPTED.items():
        bound = source_records[phase]
        same([bound['size_bytes'],bound['sha256']], list(expected), 'audited original '+phase+' composition')
        value = reader.document(bound); results[phase] = value['calibration'] if phase == 'Q16a' else value
    proof = reader.document(provenance_record)
    same(proof['schema_version'], 'cpu-prefetch-stage17-descriptive-freeze-provenance/1', 'provenance format')
    same(proof['source_records'], source_records, 'provenance source binding')
    same(proof['predecessor_resolutions'], predecessor_resolutions, 'provenance qualification lineage')
    same(proof['execution_authority'], False, 'provenance grants no execution')
    same(proof['phase18_authority'], False, 'provenance grants no Stage18')
    reader.finish()
    outputs = project(results)
    body = dict(schema_version=SCHEMA, protocol_version='2.0.0-pre.3', record_id=record_id,
        created_at_utc=created_at_utc, scope=SCOPE, state='DESCRIPTIVE_DATA_FROZEN', stand_id=results['Q16a']['stand_id'],
        source_records=source_records, provenance_record=provenance_record, predecessor_resolutions=predecessor_resolutions,
        outputs=outputs, coverage=dict(COUNTS), original_report_count=1008, original_phase_count=2016,
        unresolved_final_inputs=['Rtotal','Nruns','N_sched'], legacy_statistical_freeze_satisfied=False,
        operational_admission='NOT_GRANTED_BY_RECORD', pilot_execution_authority=False,
        execution_authority=False, phase18_authority=False)
    return dict(body, record_sha256=hashlib.sha256(canonical(body)).hexdigest())


def verify(document):
    """Recompute the full format; producer provenance still needs admission."""
    expected = build(**{key:document[key] for key in ('record_id','created_at_utc','source_records',
                     'provenance_record','predecessor_resolutions')})
    same(document, expected, 'freeze differs from original result recomputation')
    return expected
