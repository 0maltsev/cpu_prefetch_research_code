"""D273 pure prospective identities and count-sized Q16c family arithmetic.

No signing, stand access, clock anchoring, source generation or measurements.
The caller authenticates historical inputs, actual source receipts, native
layout answers and archive profile before admitting the returned declaration.
"""
import copy
import hashlib
import re
import stage17_formal_scheduled_descriptive_v1 as contract
import stage17_q16c_resource_bounds_v1 as bounds

NS=10**9;MIB=1024**2;GIB=1024**3
NATIVE_MEMORY=32*GIB
SETUP_NS=25*NS;PUBLICATION_NS=25*NS;CLEANUP_NS=4*NS;ARCHIVE_NS=140*NS
FAMILY_SETUP_NS=300*NS;FAMILY_CLEANUP_NS=120*NS


def sha(raw):return hashlib.sha256(raw).hexdigest()


def identity(master,domain,ordinal,phase):
    namespace='CPU-PREFETCH-V5-V28-Q16C-'+domain+'-'+phase.upper()+'-1'
    run='C28'+('W' if phase=='warmup' else 'M')+f'{ordinal:08d}'
    return dict(namespace_id=namespace,seed_id=namespace+f'-SEED-{ordinal:04d}',run_id=run,
                seed_hex=sha(master+b'\0'+namespace.encode()+b'\0'+run.encode()))


def prospective_inputs(parent, *, master_hex, bundle_root, source_revision, inventory_sha256, boot_id):
    bounds.require(re.fullmatch('[0-9a-f]{64}',master_hex) is not None,'prospective256-bit master required')
    master=bytes.fromhex(master_hex);sources=[];phase_identities=[];linked=[]
    for ordinal,cell in enumerate(contract.cells('Q16c')):
        for phase in ('warmup','measurement'):
            arena=identity(master,'ARENA',ordinal,phase);phase_identities.append(arena)
            original=identity(master,'SOURCE',ordinal,phase)
            namespace=original['namespace_id']+f'-CELL-{ordinal:04d}'
            identity_id=f'CPU-PREFETCH-V5-V28-Q16C-SOURCE-{2*ordinal+int(phase=="measurement"):04d}'
            sources.append(dict(ordinal=len(sources),capture_ordinal=ordinal,phase=phase,load_level=cell[-1],
                schedule_id=identity_id,seed_id=original['seed_id'],seed_hex=original['seed_hex'],namespace_id=namespace,
                parent_namespace_id=original['namespace_id'],artifact_id=identity_id+'-U64BE',
                artifact_uri=identity_id+'.u64be',derivation_record_id=identity_id+'-DERIVATION'))
        linked.append(dict(seed_id=f'CPU-PREFETCH-V5-V28-Q16C-NODES-SEED-{ordinal:04d}',
            namespace_id='CPU-PREFETCH-V5-V28-Q16C-NODES-1',
            seed_hex=sha(master+b'\0Q16C-NODES\0'+str(ordinal).encode())))
    return dict(schema_version='cpu-prefetch-stage17-q16c-prospective-identities/1',
        master_seed_hex=master_hex,phase_identities=phase_identities,linked_order_identities=linked,
        source_setup=dict(schema_version='cpu-prefetch-stage17-q16c-source-setup/1',stand_id=parent['stand_id'],
            boot_id=boot_id,bundle_root=bundle_root,source_revision=source_revision,bundle_inventory_sha256=inventory_sha256,
            sources=sources,execution_authority=False,phase18_authority=False),execution_authority=False,phase18_authority=False)


def capture_inputs(parent, identities, source_results, *, cpuset_prefix, q16a_handoff_sha256):
    bounds.require(type(source_results) is list and len(source_results)==360,'complete actual original sources required')
    settings={}
    for item in parent['captures']:
        c=item['capture'];settings[(c['hardware_state'],c['package'],c['placement'],c['working_set_class'])]=item
    bounds.require(len(settings)==60,'all60 actual retained settings required')
    rows=[]
    for ordinal,(cell,state,package,placement,ws,load) in enumerate(contract.cells('Q16c')):
        item=copy.deepcopy(settings[(state,package,placement,ws)])
        item={k:item[k] for k in ('capture','resources','monitoring')};c,r,m=(item[k] for k in ('capture','resources','monitoring'))
        c.update(schema_version='cpu-prefetch-stage17-formal-scheduled-capture/2',method_id=contract.COLLECTOR_METHOD,
            ordinal=ordinal,cell_ordinal=cell,repetition_ordinal=0,scale_ordinal=0,load_level=load,schedules=[])
        c['warmup'],c['measurement']=copy.deepcopy(identities['phase_identities'][2*ordinal:2*ordinal+2])
        c['arena_seed']=copy.deepcopy(c['measurement'])
        if package=='R2':c['ring_distance']['calibration_evidence_id']='q16a-sha256-'+q16a_handoff_sha256
        if c['linked_order'] is not None:c['linked_order'].update(identities['linked_order_identities'][ordinal])
        c['budget']['memory_bytes']=NATIVE_MEMORY
        r['ordinal']=m['ordinal']=ordinal
        r.update(core_bytes=1,monitor_bytes=1,total_mapping_bytes=1,region_bytes=[1]*7)
        replaced=[]
        for source in m['environment_sources']:
            if '/reserved/cpuset.' in source['path']:
                source['path']=cpuset_prefix+source['path'].rsplit('/',1)[1];replaced.append(source['path'])
        bounds.require(len(replaced)==5,'all five retained cpuset paths must relocate together')
        for i,phase in enumerate(('warmup','measurement')):
            original=identities['source_setup']['sources'][2*ordinal+i];result=source_results[2*ordinal+i]
            bounds.require(result['ordinal']==2*ordinal+i and result['exit_code']==0 and result['leader_reaped'] is True,
                           'actual original source completion required')
            count=result['provenance']['offered_count']
            c['schedules'].append(dict(**{k:original[k] for k in ('schedule_id','seed_id','seed_hex','namespace_id')},
                source_origin_ticks=0,source_horizon_ticks=c[phase+'_ns']*1000,offered_count=count,
                storage_format='SEALED_U64BE_ORIGINAL-v1',source_artifact=dict(artifact_id=original['artifact_id'],sha256=result['binary']['sha256'])))
            c['budget']['phases'][i].update(producer_attempt_limit=count,consumer_poll_limit=1_000_000_000)
            r['phase_capacity'][i].update(producer_primary_rows=count,consumer_primary_rows=count)
        rows.append(item)
    return rows


def assemble(parent, identities, rows, native_layouts, *, profile_sha256, compress_bound):
    bounds.require(len(rows)==180 and len(native_layouts)==180,'complete actual180 native layout answers required')
    proof=[];largest=staging=peak=0
    source=identities['source_setup']['source_revision']
    for item,answer in zip(rows,native_layouts,strict=True):
        c,r,m=(item[k] for k in ('capture','resources','monitoring'))
        bounds.require(answer['source_revision']==source and answer['source_dirty'] is False
            and answer['declared_layout_rechecked'] is True,'actual clean native sizing identity differs')
        r.update(copy.deepcopy(answer['layout']));meta=bounds.metadata_bound(r,m)
        streams=[];widths=[]
        for phase in ('warmup','measurement'):
            prefix=(4+len(c[phase]['run_id'].encode('ascii'))+7)//8*8
            bounds.require(len(c[phase]['run_id'])==12,'retained12-byte phase ID model required')
            count=c['schedules'][int(phase=='measurement')]['offered_count']
            for body in (120,80):widths.append(prefix+body);streams.append((prefix+body)*count)
        nodes=(c['geometry']['capacity']+1)*8 if c['package'] in ('L0','L1') else 0
        schedules=[s['offered_count']*8 for s in c['schedules']]
        extra=nodes+sum(schedules);copy_floor=max(*streams,extra)
        control=meta['control_bytes']+MIB;total=sum(streams)+extra+control
        minimum=r['total_mapping_bytes']+copy_floor+meta['cold_heap_model_bytes']
        bounds.require(minimum<=NATIVE_MEMORY,'actual native/publication/metadata bound exceeds32GiB')
        archive_max=(sum(max(bounds.archive_upper(n,8192*w,compress_bound),bounds.archive_upper(n,4*MIB,compress_bound))
            for n,w in zip(streams,widths,strict=True))+sum(bounds.archive_upper(n,4*MIB,compress_bound) for n in [nodes,*schedules,control])+2*MIB)
        known=SETUP_NS+c['warmup_ns']+c['measurement_ns']+sum(p['drain_ns'] for p in c['budget']['phases'])+PUBLICATION_NS+CLEANUP_NS
        item['execution_budget']=dict(setup_ns=SETUP_NS,publication_ns=PUBLICATION_NS,cleanup_ns=CLEANUP_NS,
            watchdog_ns=known,publication_memory_bytes=copy_floor,other_memory_bytes=meta['cold_heap_model_bytes'],
            memory_bytes=NATIVE_MEMORY,metadata_output_bytes=control,max_output_bytes=total)
        largest=max(largest,total);staging=max(staging,(archive_max+4095)//4096*4096);peak=max(peak,minimum)
        proof.append(dict(ordinal=c['ordinal'],native_layout=answer,metadata=meta,required_memory_bytes=minimum))
    sizes=[s['offered_count']*8 for row in rows for s in row['capture']['schedules']];total=sum(sizes)
    transport=dict(schema_version='cpu-prefetch-stage17-schedule-transport-budget/1',format='SEALED_U64BE_ORIGINAL-v1',
        source_bytes=total,owned_vector_bytes=total,loader_transient_bytes=max(sizes)+8192,descriptor_count=360,
        metadata_bytes=MIB,maximum_source_memory_bytes=2*total+max(sizes)+8192+MIB)
    storage=copy.deepcopy(parent['storage']);storage.update(implementation_profile_sha256=profile_sha256,
        per_capture_archive_ns=ARCHIVE_NS,archive_staging_bytes=staging,analysis_capture_workspace_bytes=largest,
        capture_workspace_overhead_bytes=parent['storage']['capture_workspace_overhead_bytes']+total)
    family=copy.deepcopy(parent['budget']);family.update(setup_ns=FAMILY_SETUP_NS,cleanup_ns=FAMILY_CLEANUP_NS,
        controller_memory_bytes=2*GIB,watchdog_ns=FAMILY_SETUP_NS+FAMILY_CLEANUP_NS+sum(x['execution_budget']['watchdog_ns']+ARCHIVE_NS for x in rows),
        memory_bytes=NATIVE_MEMORY+transport['maximum_source_memory_bytes']+2*GIB+storage['codec_address_space_bytes']+storage['broker_address_space_bytes'],
        max_output_bytes=16*MIB+sum(x['execution_budget']['max_output_bytes'] for x in rows))
    plan=dict(schema_version=contract.VERSION,plan_id='CPU-PREFETCH-V5-V28-Q16C-D270-PLAN-1',protocol_version='2.0.0-pre.3',
        action_id='Q16c',method_id=contract.METHOD,source_revision=source,clean_source=True,stand_id=parent['stand_id'],
        repetitions_per_cell=1,measurement_ns=NS,warmup_namespace=identities['phase_identities'][0]['namespace_id'],
        measurement_namespace=identities['phase_identities'][1]['namespace_id'],scale_ordinal=0,custody_policy_id=parent['custody_policy_id'],
        captures=rows,budget=family,storage=storage,source_transport=transport)
    contract.validate_plan(plan)
    return plan,dict(capture_bounds=proof,peak_native_mapping_publication_metadata_bytes=peak,
        family_watchdog_ns=family['watchdog_ns'],source_bytes=total,execution_authority=False,phase18_authority=False)
