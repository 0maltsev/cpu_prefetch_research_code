"""D288 one signed24h day starting at actual86-prefix validation, never import.

The record itself grants no native execution authority. The root operator must
verify its owner signature, actual clean candidate/software packet and all role
bindings. Future prefix/qualification outputs are not invented in this record.
"""
import datetime as dt
import hashlib
from pathlib import Path
import re

import stage17_q16c_execution_window_v2 as previous

NS=10**9
SCHEMA='cpu-prefetch-stage17-q16c-prefix86-execution-window/1'
IDENTITY='CPU-PREFETCH-V5-V30-D288-EXECUTION-WINDOW-1'
DECISION_SHA='5dc0daf58a4025f6df6d0132f1ef0924bbe19f79b8c94563ac9ab28d301ee2b2'
PHASES=(('prefix_validation',3600),('qualification',7200),('preparation',1200),
        ('collection',24860),('restoration',2400),('suffix_analysis',3600))
TOTAL=sum(n for _,n in PHASES)
ROLES=frozenset(('decision','acceptance','original_plan','original_failure','original_execution_window',
    'candidate_inventory','candidate_worker','software_checks','prefix_validation_packet',
    'prospective_continuation_inputs','guard_source','platform_acceptance','operator_sources'))
EVIDENCE=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-30')
FIELDS=frozenset(('schema_version','execution_window_id','decision_id','source_revision','worker_sha256','boot_id',
    'stand_id','started_monotonic_ns','global_deadline_ns','started_at_utc','bindings','automatic_retries',
    'new_windows_allowed','execution_authority','phase18_authority',*(name+'_seconds' for name,_ in PHASES)))
parse,canonical,read=previous.parse,previous.canonical,previous.read


def require(value,message):
    if not value:raise ValueError('Q16c D288 window: '+message)


def validate_record(record,*,now,expected_source,expected_worker,expected_boot):
    require(type(record) is dict and set(record)==FIELDS,'closed execution-window fields')
    require(record['schema_version']==SCHEMA and record['execution_window_id']==IDENTITY
        and record['decision_id']=='D288','exact approved one-window identity')
    require(type(expected_source) is str and re.fullmatch('[0-9a-f]{40}',expected_source)
        and expected_source!=previous.SOURCE,'actual clean continuation candidate source required')
    require(type(expected_worker) is str and re.fullmatch('[0-9a-f]{64}',expected_worker)
        and expected_worker!=previous.WORKER,'actual continuation candidate worker required')
    require(record['source_revision']==expected_source and record['worker_sha256']==expected_worker
        and record['boot_id']==expected_boot==previous.BOOT,'actual candidate and original verified boot')
    require(type(record['stand_id']) is str and bool(record['stand_id']),'actual stand identity')
    require(type(record['bindings']) is dict and set(record['bindings'])==ROLES,'complete prepared packet roles')
    require(record['execution_authority'] is False and record['phase18_authority'] is False
        and type(record['automatic_retries']) is int and record['automatic_retries']==0
        and type(record['new_windows_allowed']) is int and record['new_windows_allowed']==0,'no retry or further window')
    for name,seconds in PHASES:
        require(type(record[name+'_seconds']) is int and record[name+'_seconds']==seconds,'unchanged '+name+' budget')
    started,end=record['started_monotonic_ns'],record['global_deadline_ns']
    require(type(now) is int and type(started) is int and type(end) is int and 0<started<=now<end,
            'original monotonic window start/end')
    require(end-started==86400*NS,'one exact24h interval')
    require(type(record['started_at_utc']) is str and record['started_at_utc'].endswith('Z'),'actual UTC start')
    dt.datetime.fromisoformat(record['started_at_utc'].replace('Z','+00:00'))
    return end-now


def validate(record,*,now,phase,expected_source,expected_worker,expected_boot):
    remaining=validate_record(record,now=now,expected_source=expected_source,
        expected_worker=expected_worker,expected_boot=expected_boot)
    names=[name for name,_ in PHASES]
    require(phase in names,'explicit current phase')
    required=sum(n for _,n in PHASES[names.index(phase):])*NS
    require(remaining>required,'complete remaining phase/cleanup envelope does not fit')
    return remaining


def verify_bindings(record):
    contents={name:read(binding) for name,binding in record['bindings'].items()}
    require(hashlib.sha256(contents['decision']).hexdigest()==DECISION_SHA,'exact approved proposal bytes')
    approval=parse(contents['acceptance'])
    require(approval['decision_id']=='D288' and approval['owner_message']=='approve'
        and approval['recorded_decision_sha256']==DECISION_SHA and approval['new_execution_windows']==1
        and approval['automatic_retry'] is False and approval['exact_decision_text_approved'] is True
        and approval['reused_capture_count']==86 and approval['remaining_capture_count']==94
        and approval['maximum_total_seconds']==TOTAL and approval['repeat_completed_measurements'] is False
        and approval['phase18_authority'] is False,'actual D288 owner approval')
    platform=parse(contents['platform_acceptance'])
    require(platform['decision_id']=='D286' and platform['exact_decision_text_approved'] is True
        and platform['recorded_decision_sha256']=='a81997651d5697355f138908ccb0a101ee5b02644607f719d9bfb212645b3142'
        and type(platform['requested_locked_page_compaction_value']) is int
        and platform['requested_locked_page_compaction_value']==0
        and platform['exact_prestate_restoration_required'] is True
        and platform['source_revision']==previous.SOURCE and platform['worker_sha256']==previous.WORKER,
            'actual D286 guarded-platform acceptance')
    require(record['bindings']['candidate_worker']['sha256']==record['worker_sha256'],'actual candidate bytes')
    from stage17_formal_scheduled_continuation_v1 import PARENT_SHA256,PARENT_SIZE,FAILURE_SHA256,FAILURE_SIZE
    for role,sha,size in [('original_plan',PARENT_SHA256,PARENT_SIZE),('original_failure',FAILURE_SHA256,FAILURE_SIZE)]:
        require(record['bindings'][role]['sha256']==sha and len(contents[role])==size,'original incident '+role)
    # The old window is historical provenance. Its expiry is not extended or
    # used as the execution clock for any D288 action.
    old=parse(contents['original_execution_window'])
    require(record['bindings']['original_execution_window']['sha256']=='43b83a21677b394194e409fcfe8bb291e404ce2563ccce906d550e7edbafd993'
        and len(contents['original_execution_window'])==3462
        and old['schema_version']==previous.SCHEMA and old['execution_window_id']==previous.IDENTITY
        and old['source_revision']==previous.SOURCE and old['worker_sha256']==previous.WORKER
        and old['boot_id']==record['boot_id'],'actual original D282 window lineage')
    return contents


def authenticate(proof,*,validation,plan,now):
    """Owner-signed window plus actual qualified candidate, never an override."""
    require(type(proof) is dict and set(proof)=={'manifest','signature'},'signed D288 execution-window proof')
    require(proof['manifest']['path']==str(EVIDENCE/'d288-execution-window-1/window.json')
        and proof['signature']['path']==proof['manifest']['path']+'.sig','one exclusive new execution namespace')
    raw=read(proof['manifest']);record=parse(raw)
    require(raw==canonical(record),'canonical signed execution window')
    context=validation.resolutions['S17-EXT-006'].semantic_context
    validate_record(record,now=now,expected_source=context['source_revision'],
        expected_worker=context['release_artifact_sha256'],expected_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and record['stand_id']==trust['subject_id']==plan['stand_id'],
            'actual admitted stand owner')
    from stage17_phase_controller_v2 import _verify_signature
    read(proof['signature']);_verify_signature(raw,Path(proof['signature']['path']),trust)
    contents=verify_bindings(record)
    require(record['bindings']['candidate_inventory']['sha256']==context['inventory_sha256'],
            'actual fresh candidate inventory')
    import stage17_formal_scheduled_continuation_v1 as continuation
    continuation.validate_parent(plan,contents['original_plan'])
    require(plan['source_revision']==record['source_revision'],'actual qualified plan source')
    return record


def infrastructure(record,configuration,*,now,expected_source,expected_worker,expected_boot):
    validate(record,now=now,phase='qualification',expected_source=expected_source,
        expected_worker=expected_worker,expected_boot=expected_boot)
    require(configuration['boot_id']==record['boot_id'] and configuration['source_revision']==record['source_revision'],
            'actual isolation source/boot')
    life,protected,stop=(configuration[key] for key in ('lifecycle_seconds','protected_work_ns','stop_seconds'))
    require(type(life) is int and type(protected) is int and type(stop) is int and stop>0
        and protected>=(7200+1200+24860)*NS and life*NS>protected+stop*NS,'complete finite protected native work')
    require(now+(life+2400+3600)*NS<=record['global_deadline_ns'],'isolation keeper exceeds final restoration/analysis reserve')
    return True
