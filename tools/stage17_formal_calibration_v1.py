"""D230 pure calibration of a fixed plan from bound D220/D229 report bytes.

No raw-file access or report-provenance authentication occurs here. The caller
authenticates the report-producing analysis and native geometry evidence. This
module checks original report-byte bindings, identity, report semantics and exact
calibration arithmetic; it cannot authorize collection, replacement or R2 use.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json

import stage17_formal_plan_v1 as plans
import stage17_q16a_demand_decoder_v1 as demand
import stage17_raw_stream_decoder_v1 as codec
import stage17_raw_stream_decoder_v2 as raw
from stage17_discovery_contract_v2 import _object, _uint, _text, _constant, _sum, _product, ContractError

SCHEMA_ID = 'cpu-prefetch-stage17-formal-calibration-validation/1'
FAILURE_SCHEMA_ID = 'cpu-prefetch-stage17-formal-capture-validation-failure/1'
REPORT_SCHEMA = {'Q16a':'cpu-prefetch-stage17-q16a-capture-validation/1',
                 'Q16b':'cpu-prefetch-stage17-formal-service-capture-validation/1'}
METHOD = {action:plans.METHOD[action] for action in REPORT_SCHEMA}
CONTEXTS = tuple((placement, working_set) for placement in ('NEAR','FAR')
                 for working_set in plans.WORKING_SETS)
MINIMUM_VALID_RUNS = 59
MAX_U64 = (1 << 64) - 1


class CalibrationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CalibrationError(message)


def canonical(document):
    # Same original plan encoding as the v6 output registry: trailing LF included.
    return (json.dumps(document,sort_keys=True,separators=(',',':'),ensure_ascii=False,
                       allow_nan=False)+'\n').encode('utf-8')


def _strict(value):
    if isinstance(value,float):
        raise CalibrationError('floating-point input is forbidden')
    if isinstance(value,dict):
        for item in value.values():_strict(item)
    elif isinstance(value,list):
        for item in value:_strict(item)


def _unique(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'duplicate JSON key: '+key)
        result[key]=value
    return result


def _binding(value):
    item=_object(value,'artifact_id size_bytes sha256','source binding')
    _text(item['artifact_id'],'source artifact_id')
    _uint(item['size_bytes'],'source size_bytes')
    _text(item['sha256'],'source sha256',r'[0-9a-f]{64}')
    return copy.deepcopy(item)


def _report(record):
    binding=_binding(record['report_binding'])
    require(type(record['report_utf8_bytes']) is str,'report must supply original UTF-8 text')
    original=record['report_utf8_bytes'].encode('utf-8',errors='strict')
    require(len(original)==binding['size_bytes'],'report original size differs')
    require(hashlib.sha256(original).hexdigest()==binding['sha256'],'report original SHA256 differs')
    value=json.loads(original,object_pairs_hook=_unique,
                     parse_constant=lambda x: (_ for _ in ()).throw(CalibrationError('nonfinite JSON')))
    require(type(value) is dict,'report must be an object')
    _strict(value)
    return value,binding


def exact_throughput(completion_count, ticks_per_second, duration_ticks):
    """Reduced uint64 rational, with cancellation before the checked product."""
    _uint(completion_count,'completion_count')
    _uint(ticks_per_second,'ticks_per_second',1)
    _uint(duration_ticks,'duration_ticks',1)
    return _rational(Fraction(completion_count*ticks_per_second,duration_ticks))


def _rational(value):
    _uint(value.numerator,'rational numerator')
    _uint(value.denominator,'rational denominator',1)
    return dict(numerator=value.numerator,denominator=value.denominator)


def _fraction(value):
    obj=_object(value,'numerator denominator','exact rational')
    n=_uint(obj['numerator'],'numerator');d=_uint(obj['denominator'],'denominator',1)
    result=Fraction(n,d)
    require(result.numerator==n and result.denominator==d,'rational is not reduced')
    return result


def ring_distance(ell_star, c_star, capacity, cache_line_bytes, slot_bytes):
    for name,value in (('ell_star',ell_star),('c_star',c_star),('capacity',capacity),
                       ('cache_line_bytes',cache_line_bytes),('slot_bytes',slot_bytes)):
        _uint(value,name,1)
    def ceil_div(n,d):
        return _uint(n//d+int(n%d!=0),'ceil division')
    d1=ceil_div(cache_line_bytes,slot_bytes)
    slots=ceil_div(ell_star,c_star);lines=ceil_div(slots,d1)
    cap=(capacity//4)//d1
    result=dict(d1_slots=d1,raw_slots=slots,raw_lines=lines,cap_lines=cap,
                d2_cache_lines=None,producer_distance_slots=None,consumer_distance_slots=None)
    if cap<2:
        return result,'one-quarter cap is below two cache lines'
    d2_lines=min(max(2,lines),cap)
    d2_slots=_product(d2_lines,d1,'d2_slots')
    if d2_slots<=d1:
        return result,'R2 collapses to R1'
    result.update(d2_cache_lines=d2_lines,producer_distance_slots=d2_slots,consumer_distance_slots=d2_slots)
    return result,None


def _no_authority(report):
    _constant(report['execution_authority'],False,'report.execution_authority')
    _constant(report['phase18_authority'],False,'report.phase18_authority')


def _phase_counts(phase):
    counts=phase['counts']
    for field in ('attempted','accepted','full','consumed_including_drain'):
        _uint(counts[field],'phase '+field)
    require(_sum([counts['accepted'],counts['full']],'attempts')==counts['attempted'],
            'accepted/FULL equation differs')
    require(counts['consumed_including_drain']==counts['accepted'],'full-drain count differs')
    _constant(phase['zero_loss'],counts['full']==0,'phase zero_loss')
    for digest in phase['stream_sha256'].values():_text(digest,'raw stream sha256',r'[0-9a-f]{64}')
    return counts


def _tail(report, name, expected_count, minimum, probability):
    tail=_object(report[name],'count rank value_ticks retained_heap_items',name)
    count=_uint(tail['count'],name+'.count',minimum)
    require(count==expected_count,'tail count differs from eligible count')
    rank=demand.exact_rank(count,probability,1000)
    _constant(tail['rank'],rank,name+'.rank')
    _constant(tail['retained_heap_items'],min(rank,count-rank+1),name+'.retained_heap_items')
    value=_uint(tail['value_ticks'],name+'.value_ticks',1)
    return dict(count=count,rank=rank,value_ticks=value)


def _valid_summary(action, report, capture, resources):
    _constant(report['schema_version'],REPORT_SCHEMA[action],'capture report schema')
    _constant(report['method_id'],METHOD[action],'capture method')
    _constant(report['capture_ordinal'],capture['ordinal'],'capture ordinal')
    _no_authority(report)
    for flag in ('raw_reconciliation_validated','capture_execution_evidence_validated'):
        _constant(report[flag],True,'capture report '+flag)
    _constant(report['family_validity_established'],False,'capture family boundary')
    if action=='Q16b':_constant(report['action_id'],action,'capture action')
    require(type(report['phases']) is list and len(report['phases'])==2,'both capture phases required')
    phase_counts=[]
    for index,name in enumerate(('warmup','measurement')):
        phase=report['phases'][index]
        _constant(phase['phase'],name,'phase role')
        _constant(phase['run_id'],capture[name]['run_id'],'phase run identity')
        counts=_phase_counts(phase);phase_counts.append(counts)
        if action=='Q16a':
            _uint(counts['polls'],'consumer polls');_uint(counts['empty'],'consumer empty')
            require(_sum([counts['accepted'],counts['empty']],'consumer polls')==counts['polls'],
                    'consumer poll count partition differs')
        require(counts['attempted']<=capture['budget']['phases'][index]['producer_attempt_limit']
                and counts['attempted']<=resources['phase_capacity'][index]['producer_primary_rows']
                and counts['accepted']<=resources['phase_capacity'][index]['consumer_primary_rows'],
                'capture counts exceed prospective primary bounds')
        expected_roles={'producer','consumer'}|({'producer_demand','consumer_demand'} if action=='Q16a' else set())
        require(set(phase['stream_sha256'])==expected_roles,'all primary/demand stream hashes required')
    full_counts=[c['full'] for c in phase_counts]
    _constant(report['measurement_zero_loss'],full_counts[1]==0,'measurement zero loss')
    _constant(report['zero_loss_all_phases'],all(n==0 for n in full_counts),'all-phase zero loss')
    result=dict(full_counts=full_counts,duration_ticks=_product(capture['measurement_ns'],1000,'duration'),
                ticks_per_second=raw.TICKS_PER_SECOND)
    measurement=report['phases'][1]
    if action=='Q16b':
        interval=measurement['completion_interval']
        _constant(interval['completion_counting_rule_id'],raw.COUNTING_RULE_ID,'D211 counting rule')
        window=interval['measurement_window'];_,_,end=raw.validate_measurement_window(window)
        _constant(window['duration_ticks'],result['duration_ticks'],'fixed measurement duration')
        _constant(interval['interval_end_ticks'],end,'interval end')
        total=_uint(interval['consumed_count'],'consumed_count')
        inside=_uint(interval['interval_consumed_count'],'interval_consumed_count')
        outside=_uint(interval['outside_interval_consumed_count'],'outside_interval_consumed_count')
        require(total==phase_counts[1]['consumed_including_drain'] and
                _sum([inside,outside],'completion total')==total,'completion count partition differs')
        result.update(completion_count=inside,consumed_including_drain=total,
                      outside_interval_consumed_count=outside,
                      throughput=exact_throughput(inside,result['ticks_per_second'],result['duration_ticks']))
    else:
        minimum=capture['minimum_observations_per_series']
        _constant(report['minimum_observations_per_series'],minimum,'prospective minimum')
        tails={}
        windows=[]
        for index,phase in enumerate(report['phases']):
            require(set(phase['demand'])=={'producer','consumer'},'both demand owners required')
            for role,decoded in phase['demand'].items():
                _constant(decoded['schema_version'],demand.SCHEMA_ID,'demand classifier schema')
                _constant(decoded['method_id'],METHOD[action],'demand method')
                _constant(decoded['physical_format'],demand.FORMAT_ID,'demand codec')
                _constant(decoded['role'],role,'demand role')
                _constant(decoded['phase'],phase['phase'],'demand phase')
                _constant(decoded['run_id'],phase['run_id'],'demand run ID')
                _constant(decoded['raw_stream_validated'],True,'raw demand checked')
                _constant(decoded['primary_reconciliation_validated'],False,'decoder separate primary boundary')
                _constant(decoded['execution_evidence_validated'],False,'decoder separate execution boundary')
                _constant(decoded['execution_authority'],False,'decoder authority')
                _constant(decoded['inferential_eligible'],index==1,'demand phase eligibility')
                _constant(decoded['minimum_observations_per_series'],minimum if index else None,'demand minimum')
                window=copy.deepcopy(decoded['phase_window']);window['measurement_origin']=window.pop('phase_origin')
                _,_,end=raw.validate_measurement_window(window)
                _constant(window['duration_ticks'],_product(capture['warmup_ns'] if index==0 else capture['measurement_ns'],1000,'phase duration'),'phase duration')
                _constant(decoded['interval_end_ticks'],end,'demand interval end')
                _constant(decoded['stream']['sha256'],phase['stream_sha256'][role+'_demand'],'demand raw binding')
                if not index:
                    require(decoded['demand_p999'] is None and decoded['issue_p001'] is None,'warmup has inferential quantiles')
                    continue
                windows.append(window)
                counts=decoded['counts']
                for field in ('attempted','advanced','full','empty','outside_demand','eligible_demand','eligible_advanced','eligible_issue'):
                    _uint(counts[field],'demand '+field)
                require(_sum([counts['advanced'],counts['full'],counts['empty']],'attempts')==counts['attempted']
                        and counts['eligible_demand']+counts['outside_demand']==counts['attempted']
                        and counts['eligible_issue']==max(counts['eligible_advanced']-1,0)
                        and counts['eligible_advanced']<=min(counts['advanced'],counts['eligible_demand']),
                        'demand count equations differ')
                expected=phase_counts[1]
                require(counts['advanced']==expected['accepted'],'demand advancement differs from primary joins')
                if role=='producer':
                    require(counts['attempted']==expected['attempted'] and counts['full']==expected['full']
                            and counts['empty']==0,'producer demand count mismatch')
                else:
                    require(counts['attempted']==expected['polls'] and counts['empty']==expected['empty']
                            and counts['full']==0,'consumer demand count mismatch')
                tails[role]=dict(demand=_tail(decoded,'demand_p999',counts['eligible_demand'],minimum,999),
                                 issue=_tail(decoded,'issue_p001',counts['eligible_issue'],minimum,1))
        require(windows[0]==windows[1],'owner measurement windows differ')
        result['tails']=tails
    return result


def _failure(report, action, plan_hash, plan, capture):
    obj=_object(report,'schema_version action_id method_id capture_ordinal warmup_run_id measurement_run_id '
                'plan_sha256 source_revision error input_bindings execution_authority phase18_authority','failure report')
    for field,expected in (('schema_version',FAILURE_SCHEMA_ID),('action_id',action),('method_id',METHOD[action]),
                           ('capture_ordinal',capture['ordinal']),('warmup_run_id',capture['warmup']['run_id']),
                           ('measurement_run_id',capture['measurement']['run_id']),('plan_sha256',plan_hash),
                           ('source_revision',plan['source_revision'])):
        _constant(obj[field],expected,'failure '+field)
    _no_authority(obj)
    error=_object(obj['error'],'type message','failure error')
    for value in error.values():require(type(value) is str and bool(value),'explicit failure type/message required')
    inputs=_object(obj['input_bindings'],'native_input control final raw_artifacts','failed input bindings')
    bindings=[_binding(inputs[name]) for name in ('native_input','control','final')]
    require(type(inputs['raw_artifacts']) is list and len(inputs['raw_artifacts'])==(8 if action=='Q16a' else 5),
            'failure must bind every retained raw input')
    bindings.extend(_binding(value) for value in inputs['raw_artifacts'])
    require(len({b['artifact_id'] for b in bindings})==len(bindings),'failed input identities alias')
    return copy.deepcopy(obj)


def _geometry(records, plan=None):
    require(type(records) is list and len(records)==6,'six explicit native ring geometry records required')
    result=[]
    for ordinal,value in enumerate(records):
        row=_object(value,'context_ordinal capacity cache_line_bytes slot_storage_bytes source_binding','native ring geometry')
        _constant(row['context_ordinal'],ordinal,'geometry context order')
        capacity=_uint(row['capacity'],'geometry capacity',1)
        line=_uint(row['cache_line_bytes'],'geometry cache_line_bytes',1)
        total=_uint(row['slot_storage_bytes'],'native ring slot storage bytes',1)
        require(total%capacity==0,'native slot storage is not an exact capacity multiple')
        require(capacity&(capacity-1)==0 and line&(line-1)==0,'ring capacity/line must be powers of two')
        _binding(row['source_binding'])
        if plan is not None:
            for item in plan['captures']:
                c=item['capture']
                if c['context_ordinal']%6==ordinal:
                    _constant(capacity,c['geometry']['capacity'],'native geometry capacity differs from plan')
                    _constant(line,c['geometry']['cache_line_bytes'],'native cache line differs from plan')
        result.append(copy.deepcopy(row))
    return result


def _gate(sources,index):
    if any(row['validity']=='VALID' and row['summary']['full_counts'][index]>0 for row in sources):return 'FAIL'
    return 'PASS' if all(row['validity']=='VALID' for row in sources) else 'UNRESOLVED'


def _group(rows):
    valid=[row for row in rows if row['validity']=='VALID']
    missing=sum(row['validity']=='MISSING' for row in rows)
    blockers=[]
    if missing:blockers.append('prospective run plan is incomplete')
    if len(valid)<MINIMUM_VALID_RUNS:blockers.append('fewer than 59 valid independent runs')
    return dict(planned_runs=len(rows),present_runs=len(rows)-missing,valid_runs=len(valid),
                invalid_runs=sum(row['validity']=='INVALID' for row in rows),missing_runs=missing,
                status='UNRESOLVED' if blockers else 'VALIDATED',blockers=blockers),valid


def _derive(action,prospective,sources,geometry):
    repetitions=prospective['repetitions']
    result=dict(measurement_zero_loss_gate=_gate(sources,1),warmup_zero_loss_gate=_gate(sources,0))
    status='VALIDATED'
    if action=='Q16b':
        cells=[];minimum=None
        for position,(cell,state,package,placement,working_set,_) in enumerate(plans.cells(action)):
            rows=sources[position*repetitions:(position+1)*repetitions]
            group,valid=_group(rows)
            mu=min((_fraction(row['summary']['throughput']) for row in valid),default=None)
            if group['status']!='VALIDATED':status='UNRESOLVED';mu=None
            if mu is not None:minimum=mu if minimum is None else min(mu,minimum)
            cells.append(dict(cell_ordinal=cell,package=package,hardware_state=state,placement=placement,
                              working_set_class=working_set,**group,mu_cell=None if mu is None else _rational(mu)))
        if status!='VALIDATED':minimum=None
        result.update(cells=sorted(cells,key=lambda c:c['cell_ordinal']),
                      mu_ref=None if minimum is None else _rational(minimum),
                      candidate_loads=[] if minimum is None else [_rational(minimum*factor)
                          for factor in (Fraction(1,4),Fraction(1,2),Fraction(3,4))])
    else:
        contexts=[]
        for context,(placement,working_set) in enumerate(CONTEXTS):
            states=[];eligible=[]
            for state_index,state in enumerate(('H0','H1')):
                position=state_index*6+context
                rows=sources[position*repetitions:(position+1)*repetitions]
                group,valid=_group(rows);limits=None
                if group['status']=='VALIDATED':
                    limits={}
                    for role in ('producer','consumer'):
                        limits[role+'_demand_upper_ticks']=max(r['summary']['tails'][role]['demand']['value_ticks'] for r in valid)
                        limits[role+'_issue_lower_ticks']=min(r['summary']['tails'][role]['issue']['value_ticks'] for r in valid)
                    eligible.append(limits)
                states.append(dict(hardware_state=state,**group,limits=limits))
            blockers=[];limits=None;distance=None
            if len(eligible)!=2:
                blockers.append('both hardware states require complete plans and 59 valid runs')
            else:
                limits={}
                for role in ('producer','consumer'):
                    limits[role+'_demand_upper_ticks']=max(v[role+'_demand_upper_ticks'] for v in eligible)
                    limits[role+'_issue_lower_ticks']=min(v[role+'_issue_lower_ticks'] for v in eligible)
                ell=max(limits['producer_demand_upper_ticks'],limits['consumer_demand_upper_ticks'])
                issue=min(limits['producer_issue_lower_ticks'],limits['consumer_issue_lower_ticks'])
                limits.update(ell_star_ticks=ell,c_star_ticks=issue)
                g=geometry[context]
                distance,reason=ring_distance(ell,issue,g['capacity'],g['cache_line_bytes'],g['slot_storage_bytes']//g['capacity'])
                if reason:blockers.append(reason)
            context_status='UNRESOLVED' if blockers else 'VALIDATED'
            if blockers:status='UNRESOLVED'
            contexts.append(dict(context_ordinal=context,placement=placement,working_set_class=working_set,
                states=states,limits=limits,distance=distance,status=context_status,blockers=blockers))
        result['contexts']=contexts
    return status,result


def _check_summary(action,value,prospective):
    names='full_counts duration_ticks ticks_per_second '+('tails' if action=='Q16a' else
        'completion_count consumed_including_drain outside_interval_consumed_count throughput')
    summary=_object(value,names,'normalized run summary')
    require(type(summary['full_counts']) is list and len(summary['full_counts'])==2,'two FULL counts required')
    for number in summary['full_counts']:_uint(number,'FULL count')
    _constant(summary['duration_ticks'],_product(prospective['measurement_ns'],1000,'duration'),'summary duration')
    _constant(summary['ticks_per_second'],raw.TICKS_PER_SECOND,'summary clock unit')
    if action=='Q16b':
        for field in ('completion_count','consumed_including_drain','outside_interval_consumed_count'):_uint(summary[field],field)
        require(_sum([summary['completion_count'],summary['outside_interval_consumed_count']],'completions')==summary['consumed_including_drain'],
                'normalized completion partition differs')
        require(summary['throughput']==exact_throughput(summary['completion_count'],summary['ticks_per_second'],summary['duration_ticks']),
                'normalized exact throughput differs')
        _fraction(summary['throughput'])
    else:
        tails=_object(summary['tails'],'producer consumer','normalized owner tails')
        for owner in tails.values():
            _object(owner,'demand issue','normalized tail types')
            for name,probability in (('demand',999),('issue',1)):
                tail=_object(owner[name],'count rank value_ticks','normalized tail')
                count=_uint(tail['count'],'eligible count',prospective['minimum_observations_per_series'])
                _constant(tail['rank'],demand.exact_rank(count,probability,1000),'normalized exact rank')
                _uint(tail['value_ticks'],'positive tail',1)


def validate_calibration_record(document):
    """Check record mathematics/coverage; authenticate its producer separately."""
    try:
        _strict(document)
        obj=_object(document,'schema_version action_id method_id stand_id source_revision plan_sha256 status '
                    'prospective ring_geometry run_sources derived_result execution_authority phase18_authority','calibration record')
        action=obj['action_id'];require(type(action) is str and action in METHOD,'unsupported calibration action')
        _constant(obj['schema_version'],SCHEMA_ID,'calibration schema')
        _constant(obj['method_id'],METHOD[action],'calibration method')
        _text(obj['stand_id'],'stand_id');_text(obj['source_revision'],'source_revision',r'[0-9a-f]{40}')
        _text(obj['plan_sha256'],'plan_sha256',r'[0-9a-f]{64}');_no_authority(obj)
        prospective=_object(obj['prospective'],'repetitions measurement_ns'+(' minimum_observations_per_series' if action=='Q16a' else ''),'prospective')
        repetitions=_uint(prospective['repetitions'],'repetitions',59)
        _uint(prospective['measurement_ns'],'measurement_ns',1);_product(prospective['measurement_ns'],1000,'duration')
        if action=='Q16a':_uint(prospective['minimum_observations_per_series'],'minimum',1)
        expected=_product(12 if action=='Q16a' else 60,repetitions,'run count')
        require(type(obj['run_sources']) is list and len(obj['run_sources'])==expected,'complete planned source decision product required')
        ids=set();artifacts=set()
        for ordinal,row in enumerate(obj['run_sources']):
            _object(row,'capture_ordinal warmup_run_id measurement_run_id validity report_binding summary failure','run decision')
            _constant(row['capture_ordinal'],ordinal,'source ordinal')
            for name in ('warmup_run_id','measurement_run_id'):
                _text(row[name],name);require(row[name] not in ids,'duplicate planned run identity');ids.add(row[name])
            require(row['validity'] in ('VALID','INVALID','MISSING'),'invalid run decision')
            if row['validity']=='MISSING':
                require(row['report_binding'] is row['summary'] is row['failure'] is None,'missing run invents evidence')
                continue
            binding=_binding(row['report_binding'])
            require(binding['artifact_id'] not in artifacts,'duplicate capture-report identity');artifacts.add(binding['artifact_id'])
            if row['validity']=='VALID':
                require(row['failure'] is None,'valid run also claims failure')
                _check_summary(action,row['summary'],prospective)
            else:
                require(row['summary'] is None,'invalid run enters estimator')
                capture=dict(ordinal=ordinal,warmup=dict(run_id=row['warmup_run_id']),measurement=dict(run_id=row['measurement_run_id']))
                _failure(row['failure'],action,obj['plan_sha256'],obj,capture)
        if action=='Q16a':geometry=_geometry(obj['ring_geometry'])
        else:
            require(obj['ring_geometry'] is None,'Q16b must not claim ring geometry');geometry=None
        status,derived=_derive(action,prospective,obj['run_sources'],geometry)
        _constant(obj['status'],status,'calibration status')
        require(canonical(obj['derived_result'])==canonical(derived),
                'derived calibration result differs from exact source summaries')
        return document
    except CalibrationError:raise
    except (ContractError,KeyError,TypeError,ValueError,OverflowError,raw.DecodeError) as error:
        raise CalibrationError('calibration record rejected: '+str(error)) from error


def evaluate(action,plan,run_records,ring_geometry=None):
    """Evaluate only the fixed prospective family, preserving missing/invalid runs."""
    try:
        require(type(action) is str and action in METHOD,'Q16a or Q16b required')
        plans.validate_plan(action,plan)
        plan_hash=hashlib.sha256(canonical(plan)).hexdigest()
        repetitions=plan['repetitions_per_context' if action=='Q16a' else 'repetitions_per_cell']
        prospective=dict(repetitions=repetitions,measurement_ns=plan['measurement_ns'])
        if action=='Q16a':prospective['minimum_observations_per_series']=plan['minimum_observations_per_series']
        require(type(run_records) is list,'run_records must be a finite list')
        indexed={}
        for record in run_records:
            _object(record,'capture_ordinal measurement_run_id validity report_binding report_utf8_bytes','run record')
            ordinal=_uint(record['capture_ordinal'],'record ordinal')
            require(ordinal<len(plan['captures']) and ordinal not in indexed,'duplicate or unplanned run; no top-up')
            capture=plan['captures'][ordinal]['capture']
            _constant(record['measurement_run_id'],capture['measurement']['run_id'],'record planned run ID')
            require(record['validity'] in ('VALID','INVALID'),'explicit report validity required')
            indexed[ordinal]=record
        sources=[]
        for ordinal,item in enumerate(plan['captures']):
            capture=item['capture']
            row=dict(capture_ordinal=ordinal,warmup_run_id=capture['warmup']['run_id'],
                measurement_run_id=capture['measurement']['run_id'],validity='MISSING',
                report_binding=None,summary=None,failure=None)
            if ordinal in indexed:
                record=indexed[ordinal];report,binding=_report(record)
                row.update(validity=record['validity'],report_binding=binding)
                if record['validity']=='VALID':row['summary']=_valid_summary(action,report,capture,item['resources'])
                else:row['failure']=_failure(report,action,plan_hash,plan,capture)
            sources.append(row)
        if action=='Q16a':geometry=_geometry(ring_geometry,plan)
        else:require(ring_geometry is None,'Q16b does not use ring geometry');geometry=None
        status,derived=_derive(action,prospective,sources,geometry)
        result=dict(schema_version=SCHEMA_ID,action_id=action,method_id=METHOD[action],stand_id=plan['stand_id'],
            source_revision=plan['source_revision'],plan_sha256=plan_hash,status=status,prospective=prospective,
            ring_geometry=geometry,run_sources=sources,derived_result=derived,execution_authority=False,phase18_authority=False)
        return validate_calibration_record(result)
    except CalibrationError:raise
    except (ContractError,KeyError,TypeError,ValueError,OverflowError,UnicodeError,raw.DecodeError) as error:
        raise CalibrationError('calibration evaluation rejected: '+str(error)) from error
