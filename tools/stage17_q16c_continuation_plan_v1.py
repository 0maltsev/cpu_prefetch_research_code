"""D288 freeze prospective94 inputs before validation; bind real outputs later.

A prospective record is not a native plan and grants no execution authority.
Numeric seeds and schedule descriptors always come from the exact parent bytes.
"""
import copy
import hashlib
import re

import stage17_formal_scheduled_continuation_v1 as contract
import stage17_formal_scheduled_descriptive_v1 as parent_contract
import stage17_formal_ring_continuation_v1 as paths
import stage17_q16c_execution_window_v3 as window
import stage17_q16c_prefix_compatibility_v1 as compatibility_contract

SCHEMA='cpu-prefetch-stage17-q16c-prospective94/1'
STATIC_KEYS=('protocol_version','action_id','clean_source','stand_id','repetitions_per_cell',
    'measurement_ns','scale_ordinal','custody_policy_id')


def require(ok,message):
    if not ok:raise ValueError('D288 prospective inputs: '+message)


def prospective(parent_bytes,*,parent_binding,failure_binding,source_revision,implementation_profile_sha256,
                monitor_path_replacements,id_prefix='CPU-PREFETCH-V5-V31'):
    require(type(parent_bytes) is bytes and len(parent_bytes)==contract.PARENT_SIZE
        and hashlib.sha256(parent_bytes).hexdigest()==contract.PARENT_SHA256,'exact original incident plan')
    require(parent_binding['size_bytes']==contract.PARENT_SIZE and parent_binding['sha256']==contract.PARENT_SHA256
        and failure_binding['size_bytes']==contract.FAILURE_SIZE and failure_binding['sha256']==contract.FAILURE_SHA256,
        'exact bound parent and failed incident')
    require(re.fullmatch('[0-9a-f]{40}',source_revision) and source_revision!=contract.PARENT_SOURCE,
            'actual clean new candidate source')
    require(re.fullmatch('[0-9a-f]{64}',implementation_profile_sha256),'actual prepared archive profile')
    require(id_prefix=='CPU-PREFETCH-V5-V31','one approved fresh identity family')
    parent=window.parse(parent_bytes);parent_contract.validate_plan(parent)
    replacements=paths._path_replacements(monitor_path_replacements)
    captures=copy.deepcopy(parent['captures'][86:]);used=set()
    warmup=id_prefix+'-Q16C-WARMUP';measurement=id_prefix+'-Q16C-MEASUREMENT'
    for local,item in enumerate(captures):
        original=86+local
        for key in ('capture','resources','monitoring'):item[key]['ordinal']=local
        capture=item['capture']
        for phase,letter,namespace in (('warmup','W',warmup),('measurement','M',measurement)):
            capture[phase].update(run_id=f'C31{letter}{original:08d}',
                seed_id=f'{id_prefix}-Q16C-{phase.upper()}-{original:04d}',namespace_id=namespace)
        capture['arena_seed']=copy.deepcopy(capture['measurement'])
        if capture['linked_order'] is not None:
            capture['linked_order'].update(seed_id=f'{id_prefix}-Q16C-NODE-{original:04d}',
                namespace_id=id_prefix+'-Q16C-NODES')
        for row in item['monitoring']['environment_sources']:
            if row['path'] in replacements:
                used.add(row['path']);row['path']=replacements[row['path']]
    require(used==set(replacements),'all and only declared cpuset paths replaced')
    sizes=[s['offered_count']*8 for row in captures for s in row['capture']['schedules']]
    transport=copy.deepcopy(parent['source_transport']);total=sum(sizes)
    transport.update(descriptor_count=188,source_bytes=total,owned_vector_bytes=total,
        loader_transient_bytes=max(sizes)+8192,maximum_source_memory_bytes=2*total+max(sizes)+8192+transport['metadata_bytes'])
    budget=copy.deepcopy(parent['budget']);budget['watchdog_ns']=24860*10**9
    storage=copy.deepcopy(parent['storage']);storage['implementation_profile_sha256']=implementation_profile_sha256
    return dict(schema_version=SCHEMA,parent_plan=parent_binding,failed_family_receipt=failure_binding,
        source_revision=source_revision,plan_id=id_prefix+'-Q16C-PREFIX86-CONTINUATION-1',
        warmup_namespace=warmup,measurement_namespace=measurement,
        static_family_fields={key:parent[key] for key in STATIC_KEYS},captures=captures,
        source_transport=transport,budget=budget,storage=storage,monitor_path_replacements=monitor_path_replacements,
        platform_control=dict(schema_version='cpu-prefetch-q16c-platform-control/1',
            control_path='/proc/sys/vm/compact_unevictable_allowed',requested_value=0,
            observation_policy='BEFORE_AUTHORIZATION_AFTER_CHECKPOINT-v1',witness_transport='READ_ONLY_ROOT_LEASE_FD-v1',
            metadata_output_bytes=2*1024**2),execution_authority=False,phase18_authority=False)


def construct(record,parent_bytes,*,accepted_prefix_manifest,compatibility_manifest):
    """Only the two actual data-dependent bindings are resolved after prefix."""
    require(type(record) is dict and record['schema_version']==SCHEMA and record['execution_authority'] is False
        and record['phase18_authority'] is False,'prospective record only')
    expected=prospective(parent_bytes,parent_binding=record['parent_plan'],failure_binding=record['failed_family_receipt'],
        source_revision=record['source_revision'],implementation_profile_sha256=record['storage']['implementation_profile_sha256'],
        monitor_path_replacements=record['monitor_path_replacements'])
    require(record==expected,'frozen prospective inputs changed')
    prefix=window.parse(window.read(accepted_prefix_manifest))
    require(prefix['schema_version']=='cpu-prefetch-stage17-q16c-accepted-prefix86/1'
        and prefix['parent_plan']==record['parent_plan'] and prefix['reused_capture_ordinals']==list(range(86))
        and prefix['all_required_reports_valid'] is True and prefix['compaction_control']=='UNRECORDED',
        'actual complete accepted prefix required')
    compatibility=window.parse(window.read(compatibility_manifest))
    require(compatibility['schema_version']==compatibility_contract.SCHEMA
        and compatibility['parent_plan_sha256']==contract.PARENT_SHA256
        and compatibility['current']['source_revision']==record['source_revision'],'actual incident compatibility required')
    result=dict(record['static_family_fields'],schema_version=contract.VERSION,method_id=contract.METHOD,
        plan_id=record['plan_id'],source_revision=record['source_revision'],warmup_namespace=record['warmup_namespace'],
        measurement_namespace=record['measurement_namespace'],captures=copy.deepcopy(record['captures']),
        budget=copy.deepcopy(record['budget']),storage=copy.deepcopy(record['storage']),
        source_transport=copy.deepcopy(record['source_transport']),platform_control=copy.deepcopy(record['platform_control']),
        continuation=dict(policy_id=contract.POLICY,parent_plan=record['parent_plan'],
            failed_family_receipt=record['failed_family_receipt'],accepted_prefix_manifest=accepted_prefix_manifest,
            compatibility_manifest=compatibility_manifest,reused_capture_ordinals=list(range(86)),original_first_ordinal=86,
            original_total_captures=180,remaining_capture_count=94,seed_policy=contract.SEED_POLICY,
            monitor_path_replacements=copy.deepcopy(record['monitor_path_replacements']),future_retries=0))
    contract.validate_parent(result,parent_bytes)
    return result
