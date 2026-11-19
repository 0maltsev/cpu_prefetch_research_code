"""D292 one signed24h day starting at actual86-prefix validation, never import.

The record itself grants no native execution authority. The root operator must
verify its owner signature, actual clean candidate/software packet and all role
bindings. Future prefix/qualification outputs are not invented in this record.
"""
import datetime as dt
import hashlib
from pathlib import Path
import re

import stage17_q16c_execution_window_v2 as previous
import stage17_q16c_execution_window_v3 as scientific

NS=10**9
SCHEMA='cpu-prefetch-stage17-q16c-prefix86-execution-window/2'
IDENTITY='CPU-PREFETCH-V5-V31-D292-EXECUTION-WINDOW-1'
DECISION_SHA='97bb720c84699f1b2bf8c71cd9152b32d2a137a527d3e80c8455902a618bdd5a'
PHASES=(('prefix_validation',3600),('qualification',7200),('preparation',1200),
        ('collection',24860),('restoration',2400),('suffix_analysis',3600))
TOTAL=sum(n for _,n in PHASES)
ADDITIONAL_ROLES=frozenset(('continuation_decision','continuation_acceptance',
    'prior_execution_window','prior_execution_signature','prior_result','prior_recovery','repair_verification'))
ROLES=scientific.ROLES | ADDITIONAL_ROLES
PRIOR_BINDINGS={'prior_execution_window': (4545, '17f9eb071cdd4cdb342af65bb42a90aaefa41c6026a37a6b1c5afbddb4f22040'), 'prior_execution_signature': (322, '2e28a578adda19df5c572ba78fd2d3fda06b4c9cc3da873a41586a605cd2b6f4'), 'prior_result': (1590, '5399e9bd7cec778c6bc23e6197e1c481fa91b98577728de4e4605a9b288923cc'), 'prior_recovery': (422, 'a8a623715c5eda27f93db3b2b082e98cb958346e81bc71c56de758a18c02d6f2')}
EVIDENCE=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-31')
FIELDS=frozenset(('schema_version','execution_window_id','decision_id','source_revision','worker_sha256','boot_id',
    'stand_id','started_monotonic_ns','global_deadline_ns','started_at_utc','bindings','automatic_retries',
    'new_windows_allowed','execution_authority','phase18_authority',*(name+'_seconds' for name,_ in PHASES)))
parse,canonical,read=previous.parse,previous.canonical,previous.read


def require(value,message):
    if not value:raise ValueError('Q16c D292 window: '+message)


def validate_record(record,*,now,expected_source,expected_worker,expected_boot):
    require(type(record) is dict and set(record)==FIELDS,'closed execution-window fields')
    require(record['schema_version']==SCHEMA and record['execution_window_id']==IDENTITY
        and record['decision_id']=='D292','exact approved one-window identity')
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
    # Authenticate D288's unchanged design and exact D286/D282 lineage first.
    scientific.verify_bindings(dict(record,bindings={key:record['bindings'][key] for key in scientific.ROLES}))
    contents={name:read(binding) for name,binding in record['bindings'].items()}
    require(hashlib.sha256(contents['continuation_decision']).hexdigest()==DECISION_SHA,
            'exact separately approved continuation proposal')
    approval=parse(contents['continuation_acceptance'])
    require(approval['decision_id']=='D292' and approval['owner_message']=='approve'
        and approval['recorded_decision_sha256']==DECISION_SHA and approval['new_execution_windows']==1
        and approval['automatic_retry'] is False and approval['exact_decision_text_approved'] is True
        and approval['reused_capture_count']==86 and approval['remaining_capture_count']==94
        and approval['maximum_total_seconds']==TOTAL and approval['repeat_completed_measurements'] is False
        and approval['repeat_completed_raw_validations'] is False and approval['phase18_authority'] is False,
            'actual additional D292 owner approval')
    for role,(size,digest) in PRIOR_BINDINGS.items():
        require(len(contents[role])==size and hashlib.sha256(contents[role]).hexdigest()==digest,
                'exact consumed D288 evidence '+role)
    old=parse(contents['prior_execution_window'])
    require(old['execution_window_id']==scientific.IDENTITY and old['decision_id']=='D288'
        and old['boot_id']==record['boot_id'] and old['started_monotonic_ns']<record['started_monotonic_ns'],
            'immutable prior D288 window; no reset')
    stopped=parse(contents['prior_result']);recovered=parse(contents['prior_recovery'])
    require(stopped['success'] is False and len(stopped['phases'])==1
        and stopped['phases'][0]['role']=='prefix' and stopped['phases'][0]['exit_code']==1
        and stopped['completed_monotonic_ns']<record['started_monotonic_ns']
        and stopped['partition_restoration']['verified'] is True
        and recovered['verified'] is True and recovered['errors']==[],
            'exact metadata-only stop and verified recovery')
    repair=parse(contents['repair_verification'])
    require(repair['status']=='SOFTWARE_REPAIR_VERIFIED_NO_EXPERIMENT_STARTED'
        and repair['raw_validation_retried'] is False and repair['experiment_restarted'] is False,
            'retained repair verification evidence')
    return contents


def authenticate(proof,*,validation,plan,now):
    """Owner-signed window plus actual qualified candidate, never an override."""
    require(type(proof) is dict and set(proof)=={'manifest','signature'},'signed D292 execution-window proof')
    require(proof['manifest']['path']==str(EVIDENCE/'d292-execution-window-1/window.json')
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
    _verify_signature(contents['prior_execution_window'],
        Path(record['bindings']['prior_execution_signature']['path']),trust)
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
