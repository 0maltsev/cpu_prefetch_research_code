"""Bounded S180 family data-consistency checks over authenticated originals.

The qualified caller authenticates original metadata, source-generation proof,
published analysis bytes/process completion and fresh archive-ledger custody.
This pure data-contract layer does not supply those facts, reread event data,
restore the stand, admit execution, freeze inference or authorize Stage18.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from fractions import Fraction

from jsonschema import Draft202012Validator,ValidationError as SchemaError
import stage17_s180_capture_validation_v1 as capture
import stage17_s180_plan_prepare_v1 as planning

common=capture.common
require,exact,uint=common.require,common.exact,common.uint
SCHEMA='cpu-prefetch-stage17-s180-family-data-validation/1'
ROOT=Path(__file__).resolve().parents[1]
DAY_NS=86400000000000
MAX_METADATA_BYTES=256*1024**2
RECORD_FIELDS=set('report checkpoint attempt custody_receipt parent_receipt registry_proof publication envelopes'.split())
NATIVE_FIELDS=set(('schema_version session_id plan_sha256 blueprint_sha256 method_id stop attempted completed '
    'restoration_attempted restoration_verified cleanup_verified contexts_after_family_release whole_plots '
    'artifacts publication_scope execution_authority phase18_authority').split())
CONTEXTS=[(placement,working) for placement in ('NEAR','FAR')
    for working in ('L2_RESIDENT','LLC_RESIDENT','BEYOND_LLC')]


def before(deadline):capture.before(deadline)
def sha(value):return capture.sha(value)


def _bound(name,document):
    raw=capture.canonical(document)
    return dict(file_name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _reference(name,role,schema,document):
    return dict(_bound(name,document),role=role,schema_identity=schema,media_type='application/json')


def _native(result,plan,session_id,plan_sha):
    require(type(result) is dict and set(result)==NATIVE_FIELDS,'exact native family-result fields')
    for k,v in dict(schema_version='cpu-prefetch-stage17-s180-session-result/1',session_id=session_id,
            plan_sha256=plan_sha,blueprint_sha256=planning.BLUEPRINT_SHA256,method_id=capture.controls.METHOD,
            stop=1,attempted=180,completed=180,restoration_attempted=True,restoration_verified=True,
            cleanup_verified=True,publication_scope='BEFORE_FINAL_PUBLICATION_RETURNS',
            execution_authority=False,phase18_authority=False).items():exact(result[k],v,'native '+k)
    require(type(result['contexts_after_family_release']) is list
        and len(result['contexts_after_family_release'])==6,'all six actual context releases')
    order=plan['blueprint']['requested_whole_plot_order']
    require(len(result['whole_plots'])==2,'exactly two whole-plot restorations')
    prestate=plan['hardware']['prestate'];seen=set()
    for row in prestate:
        cpu=uint(row['cpu'],'prestate CPU');value=uint(row['value'],'full MSR prestate')
        require(cpu not in seen and value&15==0,'distinct supported H0 prestate');seen.add(cpu)
    require(bool(seen),'nonempty admitted CPU set')
    apply=[];restore=[]
    for state,plot in zip(order,result['whole_plots'],strict=True):
        exact(plot['requested_state'],state,'whole-plot hardware order')
        exact(plot['restoration_verified'],True,'native whole-plot restoration')
        if state=='H1':
            apply.extend(dict(cpu=r['cpu'],complete_value=r['value']|15) for r in prestate)
            restore.extend(dict(cpu=r['cpu'],complete_value=r['value']) for r in reversed(prestate))
        exact(plot['cumulative_apply_readback'],apply,'actual cumulative apply history')
        exact(plot['cumulative_restore_readback'],restore,'actual cumulative reverse restore history')
        exact(plot['independent_restore_observations'],[dict(cpu=r['cpu'],requested_prestate=r['value'],
            observed_value=r['value'],read_succeeded=True) for r in prestate],'independent full-value restore observations')


def _custody(item,ordinal,plan,plan_sha,session_id,request_sha256,window):
    report=item['report'];checkpoint=item['checkpoint'];attempt=item['attempt']
    prefix='s180-e'+str(ordinal);scope=plan['storage']['program_scope_sha256']
    cp_binding=_bound(prefix+'-checkpoint.json',checkpoint)
    receipt=item['custody_receipt'];receipt_binding=_bound(prefix+'-archive-custody.json',receipt)
    for k,v in dict(schema_version='cpu-prefetch-stage17-s180-run-attempt/1',session_id=session_id,
            plan_sha256=plan_sha,execution_ordinal=ordinal,cell_ordinal=report['cell_ordinal'],
            run_id=report['run_id'],retry_allowed=False).items():exact(attempt[k],v,'one native attempt '+k)
    require(set(attempt)==set('schema_version session_id plan_sha256 execution_ordinal cell_ordinal run_id retry_allowed deadline_monotonic_ns'.split()),
        'exact original attempt fields')
    require(window['start_monotonic_ns']<uint(attempt['deadline_monotonic_ns'],'capture deadline')<=window['end_monotonic_ns'],
        'attempt outside original monotonic operational window')
    exact(checkpoint['session_id'],session_id,'checkpoint session')
    exact(checkpoint['plan_sha256'],plan_sha,'checkpoint plan')
    exact(checkpoint['program_scope_sha256'],scope,'checkpoint programme')
    exact(checkpoint['execution_ordinal'],ordinal,'checkpoint ordinal')
    exact(checkpoint['native_complete'],True,'complete original checkpoint')
    exact(report['checkpoint_sha256'],cp_binding['sha256'],'analyzed original checkpoint')
    refs=capture.checkpoint_contract.original_references(checkpoint)
    exact(len(refs),8,'all eight originals')
    capture.checkpoint_contract.validate_checkpoint(checkpoint,plan_sha256=plan_sha,program_scope_sha256=scope,
        session_id=session_id,ordinal=ordinal,sources=tuple(SimpleNamespace(expected=capture.BoundFile(**r)) for r in refs))
    exact(report['original_artifacts'],refs,'all independently read original bytes')
    for k,v in dict(schema_version=capture.checkpoint_contract.CUSTODY_SCHEMA,plan_sha256=plan_sha,
            program_scope_sha256=scope,execution_ordinal=ordinal,checkpoint=cp_binding,status='ARCHIVED_AND_RELEASED',
            scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False).items():
        exact(receipt[k],v,'original custody '+k)
    rows=receipt['artifacts'];proof=item['registry_proof']
    require(type(rows) is list and len(rows)==8 and len(proof['artifacts'])==8,'complete original custody inventories')
    exact(proof['execution_ordinal'],ordinal,'registry ordinal')
    exact(proof['checkpoint'],cp_binding,'registry checkpoint')
    exact(proof['custody_receipt'],receipt_binding,'registry custody receipt')
    exact(proof['continuation_allowed'],True,'custody permitted native continuation')
    for original,row,verified in zip(refs,rows,proof['artifacts'],strict=True):
        artifact_id=plan_sha+':'+original['file_name']
        exact(row['artifact_id'],artifact_id,'native artifact identity')
        exact(row['expected_logical'],original,'expected original custody bytes')
        exact(row['logical'],original,'retained original custody bytes')
        exact(row['failure_receipt'],None,'no hidden source discrepancy')
        exact(row['archive_name'],hashlib.sha256(artifact_id.encode()).hexdigest()+'.cpfa','authoritative archive name')
        for name,expected in dict(artifact_id=artifact_id,logical=original,archive_name=row['archive_name'],
                physical=row['physical'],released_record=row['released_record']).items():exact(verified[name],expected,'registry '+name)
        for name,expected in dict(artifact_id=artifact_id,canonical_size_bytes=original['size_bytes'],
                canonical_sha256=original['sha256']).items():exact(verified['header'][name],expected,'verified header '+name)
    parent=item['parent_receipt']
    for k,v in dict(schema_version='cpu-prefetch-stage17-s180-parent-custody/1',plan_sha256=plan_sha,request_sha256=request_sha256,
            execution_ordinal=ordinal,checkpoint=cp_binding,custody_receipt=receipt_binding,broker_processes=25,
            status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False).items():
        exact(parent[k],v,'parent custody '+k)
    cleanup=parent['broker_cleanup']
    for k,v in dict(returncode=0,leader_reaped=True,process_group_gone=True,descendants_detected_after_leader_exit=False,
            cleanup_deadline_overrun=False,leader_wait_timed_out=False).items():exact(cleanup[k],v,'actual broker cleanup '+k)
    return [_reference(prefix+'-attempt.json','S180_RUN_ATTEMPT','cpu-prefetch-stage17-s180-run-attempt/1',attempt),
        *checkpoint['artifacts'],_reference(prefix+'-checkpoint.json','S180_CAPTURE_CHECKPOINT',capture.checkpoint_contract.SCHEMA,checkpoint),
        _reference(prefix+'-archive-custody.json','S180_ARCHIVE_CUSTODY',capture.checkpoint_contract.CUSTODY_SCHEMA,receipt)]


def _publication(item,ordinal,plan_sha,envelope_validator):
    report=item['report'];publication=item['publication'];prefix=plan_sha+':analysis:'+str(ordinal)+':'
    for k,v in dict(schema_version='cpu-prefetch-stage17-s180-analysis-publication/1',execution_ordinal=ordinal,
            run_id=report['run_id'],plan_sha256=plan_sha,durable_joined_publication_verified=True,
            aggregate_resource_admission_performed=False,original_archive_custody_verified=False,
            full_family_validity_established=False,execution_authority=False,phase18_authority=False).items():exact(publication[k],v,'publication '+k)
    exact(publication['capture_validation'],_bound('capture-validation.json',report),'published original capture report')
    exact(publication['tail_numerics'],_bound('tail-numerics.json',report['tail_numerics']),'published original numerics')
    require(len(publication['joined'])==2 and len(item['envelopes'])==6,'both derived phases and all six envelopes')
    for i,(phase,row,audit) in enumerate(zip(('warmup','measurement'),publication['joined'],report['phases'],strict=True)):
        exact(row['phase'],phase,'published phase')
        exact(row['artifact'],dict(file_name=phase+'-joined.bin',size_bytes=audit['joined_size_bytes'],
            sha256=audit['joined_sha256']),'independent joined binding')
        audit_document=dict(schema_version='cpu-prefetch-stage17-s180-validated-join-audit/1',artifact_id=prefix+phase+':join-audit',
            capture_validation=publication['capture_validation'],phase=phase,join_status='PASSED',
            independently_reconciled_primary_audit=audit,execution_authority=False)
        audit_binding=dict(_bound(phase+'-join-audit.json',audit_document),artifact_id=audit_document['artifact_id'])
        exact(row['join_audit'],audit_binding,'actual PASSED join-audit bytes')
        require(len(row['raw_stream_envelopes'])==3,'producer/consumer/joined envelopes')
        source_refs=[]
        for kind,binding,envelope in zip(('PRODUCER','CONSUMER','JOINED_DERIVED'),row['raw_stream_envelopes'],
                item['envelopes'][i*3:i*3+3],strict=True):
            envelope_validator.validate(envelope)
            exact(binding,_bound(phase+'-'+kind.lower()+'-envelope.json',envelope),'actual envelope bytes')
            joined=kind=='JOINED_DERIVED';original=None if joined else audit['primary_streams'][kind.lower()]
            expected=dict(run_id=audit['run_id'],stream_kind=kind,physical_format_record_id=capture.codec.FORMAT_ID,
                encoding='U64LE_LENGTH_PREFIXED_UTF8_RUN_ID_PAD8',time_unit=capture.raw.TIME_UNIT,endianness='LITTLE_ENDIAN',
                row_count=audit['joined_row_count'] if joined else original['row_count'],
                byte_count=audit['joined_size_bytes'] if joined else original['size_bytes'],
                artifact_sha256=audit['joined_sha256'] if joined else original['sha256'],immutable_ordering=True,
                integrity_artifact_ref=dict(artifact_id=audit_binding['artifact_id'],sha256=audit_binding['sha256']))
            expected['artifact_id']=prefix+phase+':joined' if joined else plan_sha+':'+original['path']
            for name,value in expected.items():exact(envelope[name],value,'bound envelope '+name)
            exact(envelope['storage']['mode'],'EXTERNAL_IMMUTABLE_ARTIFACT','production envelope storage')
            if joined:
                exact(envelope['compression'],'NONE','retained uncompressed joined URI')
                exact(envelope['source_artifacts'],source_refs,'joined original source references')
            else:source_refs.append(dict(artifact_id=envelope['artifact_id'],sha256=envelope['artifact_sha256']))


def _numeric_consistency(numeric,n):
    """Check defining metadata equations, without re-estimating or pooling data."""
    exact(numeric['raw_accepted_count'],n,'analyzed measurement population')
    fraction=lambda v:Fraction(int(v['numerator_decimal']),int(v['denominator_decimal']))
    for tail in (numeric['primary_tail'],numeric['secondary_tail']):
        exact(tail['raw_count'],n,'tail raw population');k=uint(tail['exceedance_count'],'strict exceedances')
        require(k<=n,'tail exceedances exceed accepted population')
        exact(tail['variance_numerator_decimal'],str(k*(n-k)),'fixed-N variance numerator')
        exact(tail['variance_denominator_decimal'],str(n*n),'fixed-N variance denominator')
        h=tail['correlation_horizon_events'];effective=tail['effective_count']
        if h is not None:
            require(type(h) is int and 1<=h and h+9<n,'horizon not confirmed by ten observed lags')
            exact(tail['horizon_confirmation_endpoint'],h+9,'observed ten-lag endpoint')
            require(h+9<=tail['evaluated_max_lag']<n,'reported horizon beyond evaluated lags')
        if k in (0,n):require(h is None and effective is None,'zero-variance indicator cannot claim dependence/effective count')
        if effective is None:
            exact(tail['primary_200000_gate'],'UNRESOLVED','undefined primary effective count')
            exact(tail['secondary_2000000_gate'],'UNRESOLVED','undefined secondary effective count')
        else:
            raw_tau=fraction(tail['tau_raw']);tau=fraction(tail['tau']);eff=fraction(effective)
            require(raw_tau>0 and tau==max(1,raw_tau) and 0<eff<=n and eff==Fraction(n,1)/tau,
                'exact reported IPS time/effective-count equations differ')
            exact(tail['primary_200000_gate'],'PASS' if eff>=200000 else 'FAIL','exact primary gate')
            exact(tail['secondary_2000000_gate'],'PASS' if eff>=2000000 else 'FAIL','exact secondary gate')
    exact(numeric['secondary_p9999_reported'],numeric['secondary_tail']['secondary_2000000_gate']=='PASS',
        'secondary quantile requires its own effective population')


def validate_family(*,plan,session_id,request_sha256,native_result,records,window_binding,deadline_ns):
    """Check the complete matrix and original data relationships, never a subset.

    Inputs must come from qualified actual readers/supervision, not asserted
    success documents. The returned consistency proof leaves those external
    authenticity, live-custody and operational-exit gates explicitly unverified.
    """
    try:
        before(deadline_ns);exact(plan['schema_version'],planning.PLAN,'concrete collection plan')
        require('source_count_basis' not in plan,'ceiling packet cannot be analyzed as collected data')
        exact(sha(plan['blueprint']),planning.BLUEPRINT_SHA256,'unchanged approved blueprint')
        planning.source_groups(dict(plan,schema_version=planning.SIZING))
        planning.archive.sha(request_sha256,'original signed request')
        plan_sha=sha(plan);rows=sorted(plan['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
        require(type(records) is list and len(records)==180 and len(plan['captures'])==180,'all180 original records required')
        require(set(window_binding)=={'boot_id','start_monotonic_ns','end_monotonic_ns'},'original window fields')
        start=uint(window_binding['start_monotonic_ns'],'window start');end=uint(window_binding['end_monotonic_ns'],'window end')
        require(start>0 and end-start==DAY_NS and start<=time.monotonic_ns()<deadline_ns<=end,'original24h window/deadline')
        _native(native_result,plan,session_id,plan_sha)
        env_schema=json.loads((ROOT/'protocol/2.0.0-pre.3/handoff/schemas/raw-observation.schema.json').read_bytes())
        envelope_validator=Draft202012Validator(env_schema)
        numeric_validator=Draft202012Validator(json.loads((ROOT/'config/schemas/stage17-s180-tail-numerics-v1.schema.json').read_bytes()))
        capture.tails._approval()
        contexts={};groups={};previous_end=None;native_refs=[];reports={};loss=[];warm_loss=[];low=[];secondary=[]
        totals=[dict(offered=0,accepted=0,full=0),dict(offered=0,accepted=0,full=0)]
        metadata_bytes=len(capture.canonical(plan))+len(capture.canonical(native_result))
        source_bindings=[]
        for ordinal,(row,entry,item) in enumerate(zip(rows,plan['captures'],records,strict=True)):
            before(deadline_ns);require(type(item) is dict and set(item)==RECORD_FIELDS,'exact authenticated record components')
            metadata_bytes+=len(capture.canonical(item));require(metadata_bytes<=MAX_METADATA_BYTES,'bounded family metadata exceeded')
            exact(row['execution_ordinal'],ordinal,'approved execution order')
            report=item['report'];prospective=capture.prospective_capture(row,entry)
            for k,v in dict(schema_version=capture.SCHEMA,execution_ordinal=ordinal,cell_ordinal=row['cell_ordinal'],run_id=row['run_id'],
                    plan_sha256=plan_sha,program_scope_sha256=plan['storage']['program_scope_sha256'],session_id=session_id,
                    prospective_capture_sha256=sha(prospective),capture_validation_status='PASSED',
                    capture_execution_evidence_validated=True,raw_reconciliation_validated=True,immutable_arena_validated=True,
                    node_order_validated=True,source_publications_match_admitted_hashes=True,original_schedule_generation_repeated=False,
                    prior_source_generation_verification_required=True,family_validity_established=False,run_validity_assessed=False,
                    durable_joined_publication_verified=False,execution_authority=False,phase18_authority=False).items():exact(report[k],v,'capture report '+k)
            proof=report['control_evidence'];context=(row['placement'],row['working_set_class']);context_index=CONTEXTS.index(context)
            cleanup=native_result['contexts_after_family_release'][context_index]
            for k,v in dict(execution_ordinal=ordinal,run_id=row['run_id'],prospective_capture_sha256=sha(prospective),
                    resources_sha256=sha(entry['resources']),monitoring_sha256=sha(entry['monitoring']),hardware_control_sha256=sha(plan['hardware']),
                    expected_layout_sha256=sha(entry['expected_layout']),phase_bounds_sha256=sha(entry['phases']),
                    family_context_cleanup_sha256=sha(cleanup),capture_control_evidence_validated=True,private_cleanup_verified=True,
                    shared_context_cleanup_verified=True,residency_observations_verified=54,environment_groups_verified=6).items():exact(proof[k],v,'control proof '+k)
            shared=proof['shared_data'];regions,_=capture.controls._shared(dict(shared_data=shared),row,
                dict(region_bytes=entry['expected_layout']['region_bytes']),cleanup)
            exact(len(proof['regions']),9,'all nine bound regions')
            exact(proof['regions'][7:9],regions,'actual bound persistent regions')
            exact(report['nodes']['count'],row['requested_geometry']['capacity']+1,'all persistent nodes')
            exact(report['nodes']['publication'],report['original_artifacts'][4],'actual node publication')
            exact(report['nodes']['pattern'],shared['node_pattern'],'same validated node pattern')
            count=row['requested_geometry']['capacity']+1;g=row['requested_geometry'];pattern=report['nodes']['pattern']
            for k,v in dict(transition_count=count,distinct_line_count=count,shortest_period=count,
                    distinct_page_count=(count*g['cache_line_bytes']+g['base_page_bytes']-1)//g['base_page_bytes'],
                    adjacent_fraction_at_most_one_percent=True,modal_fraction_at_most_one_percent=True).items():exact(pattern[k],v,'node summary '+k)
            identity=dict(shared_data=shared,regions=regions,nodes_sha256=report['nodes']['publication']['sha256'])
            if context in contexts:exact(identity,contexts[context],'unchanged whole-family shared context')
            else:contexts[context]=identity
            native_refs.extend(_custody(item,ordinal,plan,plan_sha,session_id,request_sha256,window_binding))
            final=item['checkpoint']['native_result_after_private_cleanup']
            states=final['session']['scheduled']['lifecycle']['phases'];origin=final['clock_origin']['absolute_nanoseconds']
            require(len(report['phases'])==len(states)==len(report['source_publications'])==2,'two complete phases')
            for i,(phase,state,p,source) in enumerate(zip(report['phases'],states,entry['phases'],report['source_publications'],strict=True)):
                exact(phase['run_id'],row['warmup_run_id' if i==0 else 'run_id'],'phase event identity')
                exact(phase['phase'],('WARMUP','MEASUREMENT')[i],'phase type')
                exact(phase['join_status'],'PASSED','independent join')
                offered=uint(phase['offered_count'],'offered');accepted=uint(phase['accepted_count'],'accepted');full=uint(phase['full_count'],'FULL')
                exact(offered,p['offered_count'],'admitted original arrivals');exact(phase['attempted_count'],offered,'all arrivals attempted')
                exact(accepted+full,offered,'independent accepted/FULL equation');exact(phase['consumed_count'],accepted,'independent complete drain')
                exact(phase['schema_version'],capture.join.SCHEMA,'independent join method')
                exact(phase['physical_format'],capture.codec.FORMAT_ID,'fixed joined physical format')
                exact(phase['time_unit'],capture.raw.TIME_UNIT,'joined interval unit')
                exact(phase['endianness'],'LITTLE','joined word order')
                _,pb,cb,jb=capture.codec.row_layout(phase['run_id'])
                exact(phase['joined_row_count'],accepted,'complete derived row count')
                exact(phase['joined_row_bytes'],jb,'derived row layout')
                exact(phase['joined_size_bytes'],accepted*jb,'complete derived extent')
                for role,count,row_bytes,reference in zip(('producer','consumer'),(offered,accepted),(pb,cb),
                        report['original_artifacts'][i*2:i*2+2],strict=True):
                    exact(phase['primary_streams'][role],dict(path=reference['file_name'],size_bytes=count*row_bytes,
                        sha256=reference['sha256'],row_count=count),'complete original '+role+' extent')
                    exact(reference['size_bytes'],count*row_bytes,'actual original extent')
                for k,v in dict(attempted=offered,accepted=accepted,full=full).items():exact(state['producer'][k],v,'native producer '+k)
                exact(state['consumer']['consumed_including_drain'],accepted,'native drained count')
                exact(source['offered_count'],offered,'original source count')
                exact(source['phase'],('warmup','measurement')[i],'source phase')
                exact(source['publication'],report['original_artifacts'][5+i],'actual source publication')
                exact(source['original_source_artifact'],p['source_artifact'],'original source membership')
                exact(source['original_big_endian_sha256'],p['source_artifact']['sha256'],'original source bytes')
                key=(context,row['load_level'],i);paired=dict(original=source['original_source_artifact'],count=offered,
                    original_be=source['original_big_endian_sha256'],published_le=source['publication']['sha256'])
                if key in groups:exact(paired,groups[key],'same paired schedule across packages/hardware')
                else:groups[key]=paired
                for k,v in dict(offered=offered,accepted=accepted,full=full).items():totals[i][k]+=v
                sample=state['origin_sample'];capture.raw._clock_pair(sample['absolute_nanoseconds'],sample['relative_picoseconds'],origin,'family actual phase origin')
                actual_window=dict(clock_suite_id=capture.raw.CLOCK_SUITE_ID,time_unit=capture.raw.TIME_UNIT,ticks_per_second=capture.raw.TICKS_PER_SECOND,
                    clock_origin_absolute_nanoseconds=origin,measurement_origin=sample,duration_ticks=row['warmup_ns' if i==0 else 'measurement_ns']*1000)
                exact(proof['phase_windows'][i],actual_window,'original phase clock/window')
                checkpoint=state['drain_checkpoint'];common.clock(checkpoint,origin,'family drain checkpoint')
                require(checkpoint['absolute_nanoseconds']>=sample['absolute_nanoseconds'],'checkpoint before phase origin')
                if previous_end is not None:require(sample['absolute_nanoseconds']>=previous_end,'overlapping or reordered actual capture phases')
                previous_end=checkpoint['absolute_nanoseconds']
            exact(report['warmup_zero_loss'],report['phases'][0]['full_count']==0,'warmup zero-loss gate')
            exact(report['measurement_zero_loss'],report['phases'][1]['full_count']==0,'measurement zero-loss gate')
            if not report['warmup_zero_loss']:warm_loss.append(ordinal)
            if not report['measurement_zero_loss']:loss.append(ordinal)
            numeric=report['tail_numerics'];numeric_validator.validate(numeric)
            _numeric_consistency(numeric,report['phases'][1]['accepted_count'])
            if numeric['primary_tail']['primary_200000_gate']!='PASS':low.append(ordinal)
            if not numeric['secondary_p9999_reported']:secondary.append(ordinal)
            _publication(item,ordinal,plan_sha,envelope_validator);reports[row['run_id']]=numeric
            source_bindings.append(dict(execution_ordinal=ordinal,checkpoint_sha256=sha(item['checkpoint']),
                capture_report_sha256=sha(report),publication_sha256=sha(item['publication']),
                custody_receipt_sha256=sha(item['custody_receipt']),parent_receipt_sha256=sha(item['parent_receipt'])))
        exact(set(contexts),set(CONTEXTS),'all six persistent contexts');exact(len(groups),36,'all36 paired sources')
        ranges=[]
        for context in CONTEXTS:
            for region in contexts[context]['regions']:
                begin=region['address'];end=begin+region['bytes']
                require(all(end<=left or right<=begin for left,right in ranges),'different persistent contexts overlap')
                ranges.append((begin,end))
        for row,item in zip(rows,records,strict=True):
            proof=item['report']['control_evidence'];page=row['requested_geometry']['base_page_bytes']
            private=[dict(address=r['address']-(page if i in (3,4,6) else 0),
                bytes=r['bytes']+(page if i in (3,4,6) else 0)) for i,r in enumerate(proof['regions'][:7])]
            monitor=item['checkpoint']['native_result_after_private_cleanup']['monitor_mapping']
            private.append(dict(address=monitor['mapping']['address'],bytes=monitor['requested']['bytes']))
            for region in private:
                begin=region['address'];end=begin+region['bytes']
                require(all(end<=left or right<=begin for left,right in ranges),'private/monitor/guard overlaps a persistent context')
        exact(native_result['artifacts'],native_refs,'complete original native publication/attempt/custody order')
        block=capture.tails.candidate_block_length(reports,required_run_ids=[r['run_id'] for r in rows])
        result=dict(schema_version=SCHEMA,scope='D310-S180-DESCRIPTIVE-FAMILY-DATA-CONSISTENCY',status='PASSED',
            plan_sha256=plan_sha,request_sha256=request_sha256,native_result_sha256=sha(native_result),window_binding=window_binding,
            captures_verified=180,whole_plots_verified=2,shared_contexts_verified=6,paired_sources_verified=36,
            native_artifact_references_verified=len(native_refs),phase_count_totals=dict(warmup=totals[0],measurement=totals[1]),
            source_bindings=source_bindings,measurement_zero_loss_failed_ordinals=loss,warmup_zero_loss_failed_ordinals=warm_loss,
            primary_effective_count_not_passed_ordinals=low,secondary_quantile_withheld_ordinals=secondary,
            block_length_candidate=block,family_data_consistency_validated=True,
            native_recorded_hardware_restoration_verified=True,shared_lifetime_and_cleanup_consistency_verified=True,
            recovery_duration_independently_measured=False,
            original_archive_custody_verified=False,analysis_supervision_verified=False,original_generator_provenance_verified=False,
            live_environment_restoration_verified=False,operational_exit_verified=False,inferential_freeze_established=False,
            repeated_block_covariance_estimated=False,execution_authority=False,phase18_authority=False)
        before(deadline_ns);return result
    except common.ValidationError:raise
    except (ValueError,TypeError,KeyError,IndexError,OSError,SchemaError,capture.raw.DecodeError) as error:
        raise common.ValidationError('S180 family validation: '+str(error)) from error
