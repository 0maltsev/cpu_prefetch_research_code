"""D240 composition mathematics over two original Q16a report populations.

This boundary verifies plans, report bytes and D230 summaries. Authenticate the
two validation producers, custody, geometry and qualification separately before
admission. No native 708-capture result or substituted execution plan is made.
"""
from __future__ import annotations

import hashlib
import json

import stage17_formal_calibration_v1 as calibration
import stage17_formal_plan_v2 as plans
import stage17_formal_ring_continuation_v1 as continuation
from stage17_formal_archive_v1 import canonical

SCHEMA = 'cpu-prefetch-stage17-q16a-composite-calibration/1'
CompositeError = calibration.CalibrationError
require = calibration.require


def _reports(plan, records, *, start, stop, offset):
    require(type(records) is list, 'finite original report list required')
    indexed = {}
    for record in records:
        calibration._object(record, 'capture_ordinal measurement_run_id validity report_binding report_utf8_bytes', 'original report record')
        ordinal = calibration._uint(record['capture_ordinal'], 'local report ordinal')
        require(start <= ordinal < stop and ordinal not in indexed,
                'duplicate or out-of-population report; no replacement or top-up')
        capture = plan['captures'][ordinal]['capture']
        calibration._constant(record['measurement_run_id'], capture['measurement']['run_id'], 'original run identity')
        require(record['validity'] in ('VALID', 'INVALID'), 'explicit original report validity')
        indexed[ordinal] = record
    result = []
    plan_hash = hashlib.sha256(canonical(plan)).hexdigest()
    for ordinal in range(start, stop):
        item = plan['captures'][ordinal];capture = item['capture']
        original = ordinal + offset
        row = dict(original_slot=original, local_capture_ordinal=ordinal,
            context_ordinal=capture['context_ordinal'], repetition_ordinal=capture['repetition_ordinal'],
            source_plan_sha256=plan_hash, source_revision=plan['source_revision'],
            warmup_run_id=capture['warmup']['run_id'], measurement_run_id=capture['measurement']['run_id'],
            validity='MISSING', report_binding=None, summary=None, failure=None)
        require((row['context_ordinal'], row['repetition_ordinal']) == divmod(original, 59),
                'original context/repetition mapping differs')
        if ordinal in indexed:
            record = indexed[ordinal]
            report, binding = calibration._report(record)
            row.update(validity=record['validity'], report_binding=binding)
            if record['validity'] == 'VALID':
                row['summary'] = calibration._valid_summary('Q16a', report, capture, item['resources'])
            else:
                row['failure'] = calibration._failure(report, 'Q16a', plan_hash, plan, capture)
        result.append(row)
    return result


def _evaluate(original, suffix, original_records, suffix_records, geometry):
    """Internal normalized boundary; caller must validate both real plans first."""
    for key in ('stand_id', 'measurement_ns', 'minimum_observations_per_series', 'repetitions_per_context'):
        calibration._constant(suffix[key], original[key], 'shared prospective ' + key)
    require(original['repetitions_per_context'] == 59, 'D240 exact 59 repetitions required')
    sources = (_reports(original, original_records, start=0, stop=177, offset=0)
               + _reports(suffix, suffix_records, start=0, stop=531, offset=177))
    require([row['original_slot'] for row in sources] == list(range(708)), 'exact composed coverage required')
    run_ids = set();report_ids = set()
    for row in sources:
        for name in ('warmup_run_id', 'measurement_run_id'):
            require(row[name] not in run_ids, 'original run identity reused across populations')
            run_ids.add(row[name])
        if row['report_binding'] is not None:
            identity = row['report_binding']['artifact_id']
            require(identity not in report_ids, 'validation-report identity reused across populations')
            report_ids.add(identity)
    g = calibration._geometry(geometry, original)
    calibration._geometry(g, suffix)
    prospective = dict(repetitions=59, measurement_ns=original['measurement_ns'],
        minimum_observations_per_series=original['minimum_observations_per_series'])
    status, derived = calibration._derive('Q16a', prospective, sources, g)
    return dict(schema_version=SCHEMA, action_id='Q16a', method_id=calibration.METHOD['Q16a'],
        collection_policy=continuation.POLICY, stand_id=original['stand_id'],
        source_populations=[dict(plan_sha256=hashlib.sha256(canonical(plan)).hexdigest(),
            source_revision=plan['source_revision'], original_first_ordinal=slots[0],
            original_last_ordinal=slots[1], required_reports=count)
            for plan, slots, count in ((original, [0, 176], 177), (suffix, [177, 707], 531))],
        status=status, prospective=prospective, ring_geometry=g, run_sources=sources,
        derived_result=derived, producer_authentication_established=False,
        family_validity_established=False, execution_authority=False, phase18_authority=False)


def evaluate(original_plan_bytes, suffix_plan, original_records, suffix_records, ring_geometry):
    """Check immutable D240 plans and original report identities, then derive.

    A mathematical VALIDATED status alone grants no operational/scientific
    admission. Missing and invalid reports remain explicit, with no retry.
    """
    try:
        require(type(original_plan_bytes) is bytes, 'original parent bytes required')
        continuation.validate_parent(suffix_plan, original_plan_bytes)
        original = json.loads(original_plan_bytes, object_pairs_hook=continuation._unique,
                              parse_constant=continuation._reject_constant)
        plans.validate_plan('Q16a', original)
        plans.validate_plan('Q16a', suffix_plan)
        return _evaluate(original, suffix_plan, original_records, suffix_records, ring_geometry)
    except CompositeError:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        raise CompositeError('Q16a composition rejected: ' + str(error)) from error


def evaluate_authenticated(*, prepared, configuration_binding, ring_geometry, suffix_finalization_binding=None):
    """Compose actual admitted prefix and finished suffix report populations.

    Geometry provenance and final EXT007 freeze are still caller obligations;
    the result explicitly does not admit them or grant execution authority.
    No original report, request or native result is rewritten.
    """
    import stage17_q16a_suffix_admission_v1 as suffix_admission
    import stage17_q16a_continuation_admission_v1 as prefix_admission
    suffix = suffix_admission.authenticate(prepared=prepared,configuration_binding=configuration_binding,
                                           finalization_binding=suffix_finalization_binding)
    plan = prepared.request['action_inputs']['plan']
    prefix_admission.validate(plan,prepared.validation.resolutions['S17-EXT-006'].semantic_context)
    reader = suffix_admission.EvidenceReader()
    prefix_binding = plan['continuation']['accepted_prefix_manifest']
    prefix = reader.document(prefix_binding)
    original_bytes = reader.read(plan['continuation']['parent_plan'])
    original = prefix_admission._json(original_bytes)
    records = []
    for row in prefix['records']:
        ordinal = row['original_ordinal']
        raw = reader.read(row['validation_report_binding'])
        capture = original['captures'][ordinal]['capture']
        records.append(dict(capture_ordinal=ordinal,measurement_run_id=capture['measurement']['run_id'],validity='VALID',
            report_binding=dict(artifact_id='Q16A-PREFIX-REPORT-'+str(ordinal),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),
            report_utf8_bytes=raw.decode('utf-8')))
    result = evaluate(original_bytes,plan,records,suffix['records'],ring_geometry)
    reader.finish()
    return dict(calibration=result,prefix_manifest=prefix_binding,
        suffix_provenance={key:value for key,value in suffix.items() if key!='records'},
        geometry_provenance_established=False,ext007_admitted=False,execution_authority=False,phase18_authority=False)
