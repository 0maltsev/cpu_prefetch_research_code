"""D260 descriptive composition of17 original and103 new capture reports.

Original report bytes, local ordinals, IDs and source revisions remain intact.
This computes D254's exact minima only; callers must authenticate both families,
qualification/compatibility, raw validation and custody independently.
"""
import hashlib

import stage17_formal_service_continuation_v2 as continuation
import stage17_formal_service_daycap_v1 as original
import stage17_formal_calibration_v1 as reports

SCHEMA='cpu-prefetch-stage17-formal-service-continuation-descriptive/1'


def evaluate(parent, plan, retained_records, new_records):
    try:
        original.validate_plan(parent)
        continuation.validate_plan(plan)
        continuation._compare_parent(plan,parent)
        sources=[];populations=[]
        for population,declared,items,records,offset in (
            ('RETAINED_PREFIX',parent,parent['captures'][:17],retained_records,0),
            ('CONTINUATION',plan,plan['captures'],new_records,17)):
            reports._strict(records)
            reports.require(type(records) is list,'finite source-population records required')
            indexed={}
            for record in records:
                reports._object(record,'capture_ordinal measurement_run_id validity report_binding report_utf8_bytes','source record')
                ordinal=reports._uint(record['capture_ordinal'],'local capture ordinal')
                reports.require(ordinal<len(items) and ordinal not in indexed,'duplicate/unplanned source run; no top-up')
                capture=items[ordinal]['capture']
                reports._constant(record['measurement_run_id'],capture['measurement']['run_id'],'actual source run ID')
                reports.require(record['validity'] in ('VALID','INVALID'),'explicit source validity required')
                indexed[ordinal]=record
            plan_hash=hashlib.sha256(original.native.canonicalize(declared).encode()).hexdigest()
            populations.append(dict(population_id=population,source_revision=declared['source_revision'],
                plan_sha256=plan_hash,planned_captures=len(items),original_first_ordinal=offset))
            for local,item in enumerate(items):
                capture=item['capture']
                row=dict(original_capture_ordinal=offset+local,capture_ordinal=local,
                    source_population=population,source_revision=declared['source_revision'],
                    source_plan_sha256=plan_hash,warmup_run_id=capture['warmup']['run_id'],
                    measurement_run_id=capture['measurement']['run_id'],validity='MISSING',
                    report_binding=None,summary=None,failure=None)
                if local in indexed:
                    record=indexed[local];document,binding=reports._report(record)
                    row.update(validity=record['validity'],report_binding=binding)
                    if record['validity']=='VALID':
                        row['summary']=reports._valid_summary('Q16b',document,capture,item['resources'])
                    else:row['failure']=reports._failure(document,'Q16b',plan_hash,declared,capture)
                sources.append(row)
        reports.require(len(sources)==120,'exact17 plus103 source slots required')
        cells=[];minima=[];complete=True
        for position,(cell,state,package,placement,working_set,_) in enumerate(original.native.cells('Q16b')):
            rows=sources[position*2:position*2+2]
            valid=[r for r in rows if r['validity']=='VALID'];missing=sum(r['validity']=='MISSING' for r in rows)
            minimum=None
            if len(valid)==2:
                minimum=min(reports._fraction(r['summary']['throughput']) for r in valid);minima.append(minimum)
            else:complete=False
            cells.append(dict(cell_ordinal=cell,hardware_state=state,package=package,placement=placement,
                working_set_class=working_set,planned_runs=2,present_runs=2-missing,valid_runs=len(valid),
                missing_runs=missing,invalid_runs=sum(r['validity']=='INVALID' for r in rows),
                min_mu_cell=None if minimum is None else reports._rational(minimum)))
        return dict(schema_version=SCHEMA,action_id='Q16b',method_id=original.METHOD,
            collector_method_id=original.COLLECTOR_METHOD,stand_id=plan['stand_id'],
            status='DESCRIPTIVE' if complete else 'UNRESOLVED',source_populations=populations,
            prospective=dict(repetitions=2,measurement_ns=original.MEASUREMENT_NS),run_sources=sources,
            derived_result=dict(cells=sorted(cells,key=lambda r:r['cell_ordinal']),
                min_mu_ref=reports._rational(min(minima)) if complete else None,
                measurement_zero_loss_gate=reports._gate(sources,1),warmup_zero_loss_gate=reports._gate(sources,0)),
            descriptive_summary_complete=complete,tolerance_claim=None,tolerance_guarantee=False,
            report_provenance_authenticated=False,independent_runs_authenticated=False,
            family_validity_established=False,execution_authority=False,phase18_authority=False)
    except reports.CalibrationError:raise
    except (continuation.ContractError,KeyError,TypeError,ValueError,OverflowError,UnicodeError) as error:
        raise reports.CalibrationError('D260 descriptive composition rejected: '+str(error)) from error
