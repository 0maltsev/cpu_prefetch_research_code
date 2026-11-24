"""Prospective S180 ceiling packet and finite resource arithmetic, not admission.

No schedules, represented arrays, hardware changes or empirical observations.
Actual counts, qualified profiles, locked custody replay and live limits must
still be authenticated by the qualified parent before execution.
"""
from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
from pathlib import Path

import stage17_formal_archive_v1 as archive
import stage17_q16c_resource_bounds_v1 as retained
import stage17_s180_namespace_audit_v1 as identities
import stage17_s180_plan_prepare_v1 as planning

NS=10**9
MIB=1024**2
GIB=1024**3
TIB=1024**4
NATIVE_CAP=64*GIB
ANALYSIS_WORKERS=12
ANALYSIS_CHILD_AS=16*GIB
ANALYSIS_FAMILY_METADATA=4*MIB
CAPTURE_NS=260*NS
ARCHIVE_NS=140*NS
EXTERNAL_TIME=dict(public_preflight_ns=600*NS,qualification_ns=1800*NS,
    source_generation_and_verification_ns=28800*NS,independent_validation_ns=5400*NS,
    restoration_and_exit_ns=1800*NS)
RESOURCE_FIELDS=('workers controller_stack tls_module_capacity thread_stat_bytes thread_status_bytes '
                 'thread_affinity_words initial_consumer_state phase_capacity').split()
MONITORING_FIELDS=('during_first_page during_page_count during_offset_ticks observer_wait_poll_limit '
                   'control_region_index counter_limits environment_sources').split()


class ResourcePlanError(archive.ArchiveError):
    pass


def require(value,message):
    if not value:raise ResourcePlanError('S180 prospective resources: '+message)


def _integer(value,label,positive=False):
    return archive.uint(value,label,positive=positive)


def _hardware(blueprint,observed):
    require(observed.get('read_only') is True and observed.get('hardware_writes') == 0
            and observed.get('qualification_performed') is False,'explicit read-only unqualified hardware observation required')
    rows={r['cpu']:r for r in observed['cpus']}
    wanted=set()
    for row in blueprint['captures']:
        geometry=row['requested_geometry']
        require(observed['base_page_bytes']==geometry['base_page_bytes']
                and observed['cache_line_bytes']==geometry['cache_line_bytes'],'current/source page or cache-line geometry differs')
        for role in ('producer','consumer'):
            cpu,node=geometry[role+'_cpu'],geometry[role+'_node'];wanted.add(cpu)
            require(cpu in rows and rows[cpu]['nodes']==[node],'current/source CPU-node geometry differs')
    require(set(rows)==wanted and len(rows)==len(observed['cpus']),'exact distinct participant observations required')
    models={(r['vendor'],r['family'],r['model']) for r in rows.values()}
    require(len(models)==1 and next(iter(models))[0]=='GenuineIntel','participant CPU identity differs')
    _,family,model=next(iter(models))
    return dict(identity=dict(family=_integer(family,'family',True),model=_integer(model,'model')),
        prestate=[dict(cpu=cpu,value=_integer(rows[cpu]['msr_1a4_observed'],'observed MSR')) for cpu in sorted(rows)],
        software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')


def make_ceiling_packet(*,blueprint,prospective_identities,historical_plan_bytes,hardware_observation,
                        source_revision,requested_cpuset_prefix,recovery_ns):
    """Build all180 prospective entries from actual retained control declarations.

    Twice the expected count is an engineering ceiling, not a statistical
    confidence bound or a replacement for the fixed time horizon. Overflow must
    stop preparation; no clipping, top-up or new source realization is allowed.
    """
    require(prospective_identities==identities.planned_identities(blueprint),'exact prospective identities required')
    old_binding=blueprint['source_geometry_plan']
    require(type(historical_plan_bytes) is bytes and len(historical_plan_bytes)==old_binding['size_bytes']
            and hashlib.sha256(historical_plan_bytes).hexdigest()==old_binding['sha256'],'original control-plan bytes differ')
    old=archive.parse_json(historical_plan_bytes)
    require(old['stand_id']==blueprint['stand_id'] and len(old['captures'])==180,'full original declared control matrix required')
    original={r['capture']['cell_ordinal']:r for r in old['captures']}
    require(len(original)==180,'distinct original control settings required')
    require(type(source_revision) is str and len(source_revision)==40
            and all(c in '0123456789abcdef' for c in source_revision),'actual native source revision required')
    prefix=Path(requested_cpuset_prefix)
    require(prefix.is_absolute() and str(prefix)==requested_cpuset_prefix and '..' not in prefix.parts,
            'explicit prospective absolute cpuset path required')
    recovery=_integer(recovery_ns,'prospective whole-plot recovery',True)
    hardware=_hardware(blueprint,hardware_observation)
    source_index={(r['placement'],r['working_set_class'],r['load_level'],r['phase']):r
                  for r in prospective_identities['sources']}
    captures=[]
    for row in sorted(blueprint['captures'],key=lambda r:r['execution_ordinal']):
        prior=original[row['cell_ordinal']];c=prior['capture']
        require(all(c[k]==row[v] for k,v in (('hardware_state','requested_hardware_state'),('package','package'),
            ('placement','placement'),('working_set_class','working_set_class'),('load_level','load_level')))
            and c['geometry']==row['requested_geometry'],'source controls belong to another setting/geometry')
        resources={k:copy.deepcopy(prior['resources'][k]) for k in RESOURCE_FIELDS}
        require(prior['monitoring']['hardware_identity']==hardware['identity'],
                'original/current declared hardware identity differs')
        monitoring={k:copy.deepcopy(prior['monitoring'][k]) for k in MONITORING_FIELDS}
        for key in ('during_first_page','during_page_count'):
            require(len(monitoring[key])==7,'original seven-region monitoring declaration required')
            monitoring[key].extend([0,0] if key=='during_first_page' else [1,1])
        relocated=0
        for source in monitoring['environment_sources']:
            if '/reserved/cpuset.' in source['path']:
                source['path']=str(prefix/source['path'].rsplit('/',1)[1]);relocated+=1
        require(relocated==5,'all five original cpuset observation paths must relocate')
        phases=[]
        for i,phase in enumerate(('warmup','measurement')):
            rate=Fraction(row['nominal_rate']['numerator'],row['nominal_rate']['denominator'])
            duration=row[phase+'_ns'];mean=rate*Fraction(duration,NS)
            ceiling=(2*mean.numerator+mean.denominator-1)//mean.denominator
            declaration=source_index[row['placement'],row['working_set_class'],row['load_level'],phase]
            old_phase=c['budget']['phases'][i]
            phases.append(dict(schedule_id=declaration['schedule_id'],source_origin_ticks=0,
                source_horizon_ticks=_integer(duration*1000,'source horizon',True),offered_count=ceiling,
                source_artifact=None,producer_attempt_limit=ceiling,
                consumer_poll_limit=old_phase['consumer_poll_limit'],drain_duration_ticks=old_phase['drain_ns']*1000))
            resources['phase_capacity'][i]=dict(producer_primary_rows=ceiling,consumer_primary_rows=ceiling)
        captures.append(dict(execution_ordinal=row['execution_ordinal'],cell_ordinal=row['cell_ordinal'],
            phases=phases,resources=resources,monitoring=monitoring,
            execution_budget=dict(watchdog_ns=CAPTURE_NS,archive_ns=ARCHIVE_NS,max_output_bytes=8*GIB,
                metadata_bytes=GIB,barrier_poll_limit=c['budget']['barrier_poll_limit'])))
    storage={k:old['storage'][k] for k in ('program_id','program_scope_sha256','implementation_profile_sha256')}
    storage.update(pilot_policy_id='D310-S180-LOSSLESS-STAND-PRIMARY-v1',approval_sha256=blueprint['approval']['sha256'],
        archive_staging_bytes=8*GIB,maximum_custody_receipt_bytes=2*MIB)
    packet=dict(schema_version=planning.SIZING,source_count_basis='PROSPECTIVE_UPPER_CEILINGS',
        source_revision=source_revision,blueprint=copy.deepcopy(blueprint),captures=captures,
        hardware=hardware,storage=storage,
        budget=dict(setup_ns=300*NS,whole_plot_transition_ns=NS,whole_plot_recovery_ns=recovery,
            finalization_ns=120*NS,final_metadata_bytes=128*MIB,entry_metadata_bytes=2*MIB,
            memory_bytes=NATIVE_CAP,max_output_bytes=2*TIB))
    planning.source_groups(packet)
    return packet


def metadata_envelope(layout,monitoring,resources):
    """Nine-region extension of the accepted symbolic common-observation model."""
    regions=layout['region_bytes']
    require(len(regions)==9 and all(type(n) is int and n>0 and n%4096==0 for n in regions),
            'nine declared4096-page native regions required')
    require(resources['tls_module_capacity']==8 and resources['thread_stat_bytes']==4096
            and resources['thread_status_bytes']==4096 and resources['thread_affinity_words']==4,
            'accepted TLS/thread model capacities required')
    require(len(monitoring['during_page_count'])==9,'nine requested during-probe counts required')
    model=retained.model
    full=model.control(dict(layout=layout),[0,0]);common={k:full[k] for k in retained.COMMON_KEYS}
    common['regions']=model.Repeat(model.REGION,9)
    common['residency']=[model.residency(monitoring['during_page_count'][i] if moment==1 else size//4096)
        for _ in range(2) for moment in range(3) for i,size in enumerate(regions)]
    preparations=[];samples=[]
    for source in monitoring['environment_sources']:
        prep=copy.deepcopy(model.ENV_PREP)
        prep['plan']=dict(path_bytes=list(source['path'].encode()),
            **{k:source[k] for k in ('byte_capacity','chunk_bytes','max_data_reads','requested')})
        preparations.append(prep);sample=copy.deepcopy(model.ENV_SAMPLE)
        sample['raw_bytes']=model.Repeat(255,source['byte_capacity'])
        sample['reads']=model.Repeat(model.FILE_READ,source['max_data_reads']);samples.extend([sample]*6)
    common['environment_preparations']=preparations;common['environment_samples']=samples
    control=model.size(common)+retained.FIXED_METADATA_ALLOWANCE
    tree=retained.allocation_tree(common)+64*retained.FIXED_METADATA_ALLOWANCE
    heap=max(2*tree,tree+3*control,2*control)+retained.FIXED_NATIVE_RUNTIME_ALLOWANCE
    return dict(control_bytes=control,cold_heap_model_bytes=heap,region_count=9,
        fixed_pilot_metadata_allowance_bytes=retained.FIXED_METADATA_ALLOWANCE,
        model_caveat='Symbolic type-width/allocation envelope, not allocator/RSS certification')


def bound_packet(sizing,report,*,compress_bound):
    """Use actual cold native layouts and accepted Zstd bound; no ratio credit."""
    def no_credit_bound(n):
        bound=_integer(compress_bound(n),'compression upper bound')
        require(bound>=n,'compression bound takes an unapproved ratio credit')
        return bound
    require(report['schema_version']==planning.REPORT and report['sizing_plan_sha256']==planning.sha(sizing),
            'actual native description belongs to another packet')
    require(len(report['captures'])==180,'complete actual cold layouts required')
    out=copy.deepcopy(sizing)
    rows=sorted(out['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
    bounds=[];archive_total=0;max_staging=0;max_heap=0;peak_capture=0
    for row,entry,computed in zip(rows,out['captures'],report['captures'],strict=True):
        require(computed['execution_ordinal']==entry['execution_ordinal'] and computed['cell_ordinal']==entry['cell_ordinal'],
                'actual cold layout order differs')
        meta=metadata_envelope(computed['expected_layout'],entry['monitoring'],entry['resources'])
        extents=[];widths=[]
        for phase_index,phase in enumerate(('warmup','measurement')):
            run=row['warmup_run_id' if phase_index==0 else 'run_id']
            _,producer,consumer,_=archive.row_layout(run)
            count=entry['phases'][phase_index]['offered_count']
            for width in (producer,consumer):
                widths.append(width);extents.append(archive.checked_product(count,width))
        # Shared node orders are published for every package, including rings.
        node_bytes=archive.checked_product(row['requested_geometry']['capacity']+1,8)
        schedules=[archive.checked_product(p['offered_count'],8) for p in entry['phases']]
        control=archive.checked_sum(meta['control_bytes'],2*MIB)
        total=archive.checked_sum(*extents,node_bytes,*schedules,control)
        archive_max=archive.checked_sum(2*MIB,
            *(max(retained.archive_upper(n,8192*w,no_credit_bound),retained.archive_upper(n,archive.BYTE_BLOCK,no_credit_bound))
                for n,w in zip(extents,widths,strict=True)),
            *(retained.archive_upper(n,archive.BYTE_BLOCK,no_credit_bound) for n in (node_bytes,*schedules,control)))
        entry['execution_budget'].update(metadata_bytes=control,max_output_bytes=total)
        archive_total=archive.checked_sum(archive_total,archive_max)
        max_staging=max(max_staging,archive_max);max_heap=max(max_heap,meta['cold_heap_model_bytes'])
        peak_capture=max(peak_capture,total)
        bounds.append(dict(execution_ordinal=entry['execution_ordinal'],cell_ordinal=entry['cell_ordinal'],
            primary_row_bytes=widths,primary_stream_bytes=extents,node_order_bytes=node_bytes,
            schedule_bytes=schedules,metadata=meta,canonical_output_bytes=total,archive_upper_bytes=archive_max))
    out['storage']['archive_staging_bytes']=(max_staging+4095)//4096*4096
    # Only output/metadata/staging bounds changed. Obtain a new actual native
    # description of this exact packet before any subsequent resource admission.
    return out,dict(schema_version='cpu-prefetch-stage17-s180-prospective-resource-envelope/1',
        bounded_sizing_plan_sha256=planning.sha(out),
        source_count_basis=out['source_count_basis'],count_ceiling_method='TWO-TIMES-EXPECTED-ARRIVALS-INTEGER-CEILING-v1',
        canonical_family_upper_bytes=sum(b['canonical_output_bytes'] for b in bounds)+out['budget']['final_metadata_bytes']+out['budget']['entry_metadata_bytes'],
        archive_family_upper_bytes=archive_total,maximum_capture_workspace_bytes=peak_capture,
        maximum_archive_staging_bytes=out['storage']['archive_staging_bytes'],
        maximum_cold_heap_model_bytes=max_heap,capture_bounds=bounds,source_bytes_materialized=False,
        archive_profile_declaration='HISTORICAL_REFERENCE_PENDING_S180_QUALIFICATION',
        current_hardware_qualified=False,complete_external_resources_included=False,
        resource_admission_performed=False,whole_operational_eta_verified=False,execution_authority=False,phase18_authority=False)


def analysis_output_envelope(plan):
    """Retained joined output, not a disposable inverse spool or admission.

    Reserve every offered event as accepted; no compression or loss credit.
    One MiB per capture is the existing D350 metadata bound. Another MiB is
    an engineering allocation allowance, not an observed filesystem property.
    Actual publishers/supervision must enforce allocated as well as logical
    charges and fail if either this bound or an aggregate policy is exceeded.
    """
    planning.source_groups(dict(plan,schema_version=planning.SIZING))
    rows=sorted(plan['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
    bounds=[];total=0;workspace=0
    for row,entry in zip(rows,plan['captures'],strict=True):
        joined=0
        for i,phase in enumerate(entry['phases']):
            count=archive.uint(phase['offered_count'],'original offered count')
            run=row['warmup_run_id' if i==0 else 'run_id']
            joined=archive.checked_sum(joined,count*archive.row_layout(run)[3])
        maximum=archive.checked_sum(joined,2*MIB)
        require(maximum<=256*GIB,'per-capture result exceeds existing publication bound')
        bounds.append(dict(execution_ordinal=row['execution_ordinal'],joined_logical_bytes_upper=joined,
            metadata_reserve_bytes=MIB,allocation_allowance_bytes=MIB,maximum_output_bytes=maximum))
        total=archive.checked_sum(total,joined);workspace=archive.checked_sum(workspace,maximum)
    return dict(schema_version='cpu-prefetch-stage17-s180-analysis-output-envelope/2',
        captures=180,count_basis='ALL_ORIGINAL_OFFERED_EVENTS_ACCEPTED_NO_COMPRESSION_CREDIT',
        joined_logical_bytes_upper=total,workspace_bytes_upper=archive.checked_sum(workspace,ANALYSIS_FAMILY_METADATA),
        family_metadata_reserve_bytes=ANALYSIS_FAMILY_METADATA,
        required_inodes=180*18+64+ANALYSIS_WORKERS*11,capture_bounds=bounds,resource_admission_performed=False,
        actual_allocation_observed=False,execution_authority=False,phase18_authority=False)


def process_envelope(sizing,native_report,envelope):
    """Requested process ceilings, not observed limits or an RSS certificate.

    Source memfd pages are charged independently of native vector ownership.
    Sum all collection-stage caps and all analysis-stage caps separately.
    The analysis stage requires actual owned native/environment/source release
    before its larger pool may exist. Decode runs in those same workers under
    a temporary2GiB soft limit, never in an additional simultaneous child.
    Requested caps alone cannot supply the mandatory transition/readbacks.
    """
    require(envelope['bounded_sizing_plan_sha256']==planning.sha(sizing),
            'resource envelope belongs to another bounded packet')
    minima=planning.resource_minima(sizing,native_report)
    native_with_heap=archive.checked_sum(minima['minimum_native_memory_bytes'],
        envelope['maximum_cold_heap_model_bytes'])
    require(native_with_heap<=sizing['budget']['memory_bytes'],
            'native mappings, payload and cold heap exceed requested limit')
    groups,order=planning.source_groups(sizing)
    source_pages=sum((p['offered_count']*8+4095)//4096*4096 for key in order for p in groups[key])
    collection=dict(native=sizing['budget']['memory_bytes'],parent=4*GIB,
        source_generation_or_verification_child=8*GIB,archive_broker=2*GIB,
        archive_codec=2*GIB,sealed_source_pages=source_pages)
    analysis=dict(parent=4*GIB,independent_validation_children=ANALYSIS_WORKERS*ANALYSIS_CHILD_AS)
    caps=dict(collection,independent_validation_children=analysis['independent_validation_children'],
        independent_decode_children=0)
    stage_totals={name:archive.checked_sum(*values.values()) for name,values in
        dict(collection=collection,analysis=analysis).items()}
    return dict(schema_version='cpu-prefetch-stage17-s180-requested-process-envelope/2',
        sizing_plan_sha256=planning.sha(sizing),requested_address_or_page_caps_bytes=caps,
        stage_caps_bytes=dict(collection=collection,analysis=analysis),stage_total_bytes=stage_totals,
        conservative_total_bytes=max(stage_totals.values()),analysis_worker_count=ANALYSIS_WORKERS,
        analysis_requires_owned_quiescence=True,in_process_decode_limit_readback_required=True,
        native_minimum_plus_cold_heap_bytes=native_with_heap,native_resource_minima=minima,
        memory_lock_requested_bytes=sizing['budget']['memory_bytes'],
        memory_lock_limits_verified=False,whole_process_tree_limits_verified=False,
        allocator_rss_certified=False,resource_admission_performed=False,
        execution_authority=False,phase18_authority=False)


def time_envelope(sizing,native_report):
    minimum=planning.resource_minima(sizing,native_report)
    native=minimum['native_family_watchdog_ns']
    total=archive.checked_sum(native,*EXTERNAL_TIME.values())
    require(total<=planning.DAY_NS,'complete declared stage caps exceed one day')
    return dict(native_family_watchdog_ns=native,external_stage_caps_ns=dict(EXTERNAL_TIME),
        requested_operational_cap_ns=planning.DAY_NS,total_declared_stage_caps_ns=total,
        remaining_window_margin_ns=planning.DAY_NS-total,expected_elapsed_time_verified=False,
        source_preparation_started=False,resource_admission_performed=False,execution_authority=False,phase18_authority=False)
