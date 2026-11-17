"""D277 separate execution day; original signed source-study timestamps stay intact.

This cold administrative record grants no native execution authority. Callers
must authenticate its owner signature, all lineage bytes and the ordinary signed
native request independently. No record is created or consumed on import.
"""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat

NS=10**9
QUALIFICATION=7200
COLLECTION=47220
AUTHORITY_PREPARATION=600
FAMILY=COLLECTION+AUTHORITY_PREPARATION
ANALYSIS=5400
RESTORATION=2400
TOTAL=QUALIFICATION+FAMILY+ANALYSIS+RESTORATION
SCHEMA='cpu-prefetch-stage17-q16c-retained-setup-execution-window/1'
IDENTITY='CPU-PREFETCH-V5-V28-D277-EXECUTION-WINDOW-1'
SOURCE='919c48637cbdba9e466a3104f5cbb39f7184e39b'
WORKER='1baa213a137679460348ff6b861839044022957a4de0e5fc79929f7b49bed883'
BOOT='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
DECISION_SHA='cde22d6426984a29054c01781f2bdf309c8eda1aa2d735909fddc0631e9df056'
EVIDENCE=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-28')
ROLES=frozenset(('source_manifest','source_signature','sizing','clocks','acceptance','decision','plan','qualified_inventory','qualified_worker','administrative_manifest'))
FIELDS=frozenset(('schema_version','execution_window_id','decision_id','source_revision','worker_sha256','boot_id','stand_id',
    'started_monotonic_ns','global_deadline_ns','started_at_utc','bindings','qualification_seconds','family_seconds',
    'analysis_seconds','restoration_seconds','automatic_retries','new_windows_allowed','execution_authority','phase18_authority'))


def require(ok,message):
    if not ok:raise ValueError('Q16c D277 execution window: '+message)


def canonical(value):return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:require(k not in out,'duplicate JSON key');out[k]=v
        return out
    def invalid(v):raise ValueError('noninteger/nonfinite JSON '+v)
    return json.loads(raw,object_pairs_hook=pairs,parse_float=invalid,parse_constant=invalid)


def read(b):
    require(type(b) is dict and set(b)=={'path','size_bytes','sha256'},'closed file binding')
    p=Path(b['path']);size=b['size_bytes']
    require(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'canonical nonsymlink binding')
    require(type(size) is int and 0<size<=32*1024**2,'bounded file size')
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno());require(stat.S_ISREG(before.st_mode) and before.st_size==size,'regular bound file')
        raw=f.read(size+1)
        require(stamp(before)==stamp(os.fstat(f.fileno()))==stamp(p.stat(follow_symlinks=False)),'input changed')
    require(len(raw)==size and hashlib.sha256(raw).hexdigest()==b['sha256'],'bound bytes differ')
    return raw


def validate(record,*,now,qualification=False):
    require(type(record) is dict and set(record)==FIELDS,'closed execution window fields')
    require(record['schema_version']==SCHEMA and record['execution_window_id']==IDENTITY
        and record['decision_id']=='D277','one approved versioned execution window')
    require(record['source_revision']==SOURCE and record['worker_sha256']==WORKER and record['boot_id']==BOOT,'actual frozen release and boot')
    require(type(record['stand_id']) is str and bool(record['stand_id']),'actual stand identity')
    require(type(record['bindings']) is dict and set(record['bindings'])==ROLES,'complete retained setup lineage')
    require(record['execution_authority'] is False and record['phase18_authority'] is False
        and type(record['automatic_retries']) is int and record['automatic_retries']==0
        and type(record['new_windows_allowed']) is int and record['new_windows_allowed']==0,'no additional execution or retry authority')
    for key,value in [('qualification_seconds',QUALIFICATION),('family_seconds',FAMILY),('analysis_seconds',ANALYSIS),('restoration_seconds',RESTORATION)]:
        require(type(record[key]) is int and record[key]==value,'unchanged prospective '+key)
    start=record['started_monotonic_ns'];end=record['global_deadline_ns']
    require(type(now) is int and type(start) is int and type(end) is int and 0<start<=now,'actual monotonic start')
    require(end-start==86400*NS,'exact separate24h interval')
    stamp=record['started_at_utc'];require(type(stamp) is str and stamp.endswith('Z'),'explicit UTC start')
    dt.datetime.fromisoformat(stamp.replace('Z','+00:00'))
    remaining=FAMILY+ANALYSIS+RESTORATION+(QUALIFICATION if qualification else 0)
    require(now+remaining*NS<end,'complete remaining envelope cannot fit')
    return end-now


def infrastructure(record,configuration,*,now):
    validate(record,now=now,qualification=True)
    require(configuration['boot_id']==record['boot_id'] and configuration['source_revision']==record['source_revision'],'actual source/boot')
    life=configuration['lifecycle_seconds'];protected=configuration['protected_work_ns']
    require(type(life) is int and type(protected) is int and protected>=(QUALIFICATION+FAMILY)*NS,'complete protected native work')
    require(life*NS>protected+configuration['stop_seconds']*NS,'finite isolation keeper underfunded')
    require(now+(life+RESTORATION)*NS<=record['global_deadline_ns'],'keeper exceeds execution restoration reserve')
    return True


def authenticate(proof,*,validation,plan,now):
    """Verify owner signature and exact original bytes; never alter old deadlines."""
    require(type(proof) is dict and set(proof)=={'manifest','signature'},'signed execution window proof')
    require(proof['manifest']['path']==str(EVIDENCE/'d277-execution-window-1/window.json')
        and proof['signature']['path']==proof['manifest']['path']+'.sig','one exclusive execution namespace')
    raw=read(proof['manifest']);record=parse(raw);require(raw==canonical(record),'canonical window bytes')
    validate(record,now=now)
    b=record['bindings'];values={k:read(v) for k,v in b.items()}
    # This is the ordinary authenticated EXT003 owner trust, never a new signer.
    import stage17_phase_controller_v2 as support
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and record['stand_id']==trust['subject_id'],'actual admitted stand owner')
    read(proof['signature']);support._verify_signature(raw,Path(proof['signature']['path']),trust)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'live boot differs')
    require(b['decision']['sha256']==DECISION_SHA,'unchanged accepted D277 proposal')
    acceptance=parse(values['acceptance'])
    require(acceptance['decision_id']=='D277' and acceptance['owner_message']=='continue'
        and acceptance['recorded_decision_sha256']==DECISION_SHA,'recorded owner acceptance')
    source=parse(values['source_manifest']);clocks=parse(values['clocks'])
    require(source['stand_id']==record['stand_id']==plan['stand_id'] and source['boot_id']==BOOT and source['software_source_revision']==SOURCE
        and source['all_workers_reaped'] is True and source['completed_monotonic_ns']<source['source_deadline_ns']
        and source['global_deadline_ns']-source['started_monotonic_ns']==86400*NS,'unaltered completed original source study')
    require(source['completed_monotonic_ns']<record['started_monotonic_ns'],'retained setup precedes new execution')
    require(clocks['both_pairs_passed'] is True,'both retained clocks must pass')
    require(len(source['sources'])==360,'complete original source population')
    require(b['source_manifest']['sha256']=='017e8a64630ba57207ecf08fc98b67908c77acafb0f2e483bbfb24d3e2206b00'
        and b['source_signature']['sha256']=='e1f160ef1a5528a4e2ff67cfc2787833ace309140caf89a9966aaf44559642f9'
        and b['sizing']['sha256']=='15b1fdbfcb144a8e9a983a2b013bfc6f874181cf550f590a74ba2a0b905f71ce','exact completed original setup')
    require(parse(values['plan'])==plan and len(plan['captures'])==180 and plan['source_revision']==SOURCE
        and plan['budget']['watchdog_ns']==FAMILY*NS,'exact frozen full180 plan')
    require(b['qualified_worker']['sha256']==WORKER
        and b['qualified_inventory']['sha256']==source['bundle_inventory_sha256'],'exact qualified runtime')
    context=validation.resolutions['S17-EXT-006'].semantic_context
    require(context['source_revision']==SOURCE and context['release_artifact_sha256']==WORKER,'actually qualified current release')
    admin=parse(values['administrative_manifest'])
    require(admin['qualified_source_revision']==SOURCE and admin['qualified_worker_sha256']==WORKER
        and admin['execution_authority'] is False and admin['phase18_authority'] is False,'bound cold administrative packet')
    return record
