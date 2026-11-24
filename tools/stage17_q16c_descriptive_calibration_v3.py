"""D288 compose actual86+94 reports without repeating any raw validation.

The caller must independently authenticate producer signatures, original custody
and qualification. This consumer authenticates the actual incident declaration,
report bytes/counts, prefix report manifest and recorded platform observations.
No report, admission result or successful composition grants execution authority.
"""
import hashlib

import stage17_q16c_descriptive_calibration_v2 as previous
import stage17_formal_scheduled_continuation_v1 as continuation
import stage17_q16c_execution_window_v3 as window

require,same,fields=previous.require,previous.same,previous.fields
SCHEMA='cpu-prefetch-stage17-q16c-descriptive-platform-strata/1'
PREFIX_SCHEMA='cpu-prefetch-stage17-q16c-accepted-prefix86/1'
MOMENTS=('before-native-authorization','after-native-checkpoint')


def _records(plan,records,count):
    require(type(records) is list and len(records)==count,'all required original reports; no subset or repeat')
    require([r['capture_ordinal'] for r in records]==list(range(count)),
            'exact original local ordinal order; no relabeling')
    return [previous._report(row,item['capture']) for row,item in zip(records,plan['captures'][:count],strict=True)]


def prefix_manifest(parent_bytes,records,*,plan_binding,analysis_completion):
    """Publishable only after all86 independent reports passed, never a plan."""
    require(type(parent_bytes) is bytes and len(parent_bytes)==continuation.PARENT_SIZE
        and hashlib.sha256(parent_bytes).hexdigest()==continuation.PARENT_SHA256,'exact original incident plan bytes')
    require(window.read(plan_binding)==parent_bytes,'actual original plan binding differs')
    parent=window.parse(parent_bytes);previous.contract.validate_plan(parent)
    rows=_records(parent,records,86)
    completion=window.parse(window.read(analysis_completion))
    for key,expected in dict(schema_version='cpu-prefetch-stage17-q16c-selected-analysis-completion/1',
            kind='PREFIX86',status='ALL_SELECTED_VALID',all_workers_reaped=True,execution_authority=False,
            phase18_authority=False,plan_binding=plan_binding).items():
        same(completion[key],expected,'actual independent prefix completion '+key)
    require(type(completion['elapsed_ns']) is int and 0<completion['elapsed_ns']<3600*10**9,
            'actual prefix analysis finished within original bound')
    require(type(completion['reports']) is list and len(completion['reports'])==86,'actual86 completion report bindings')
    for completed,row in zip(completion['reports'],records,strict=True):
        require(window.read(completed)==row['report_utf8_bytes'],'actual independently published report differs')
    return dict(schema_version=PREFIX_SCHEMA,parent_plan=plan_binding,original_source_revision=parent['source_revision'],
        failed_family_receipt_sha256=continuation.FAILURE_SHA256,analysis_completion=analysis_completion,
        reused_capture_ordinals=list(range(86)),reports=[r['report_binding'] for r in rows],
        compaction_control='UNRECORDED',all_required_reports_valid=True,
        scientific_method=previous.contract.COLLECTOR_METHOD,execution_authority=False,phase18_authority=False)


def _platform(raw,*,plan_sha256,request_sha256):
    require(type(raw) is bytes and 0<len(raw)<=2*1024**2,'bounded actual platform receipt bundle')
    document=window.parse(raw)
    fields(document,'schema_version request_sha256 plan_sha256 observation_count observations scientific_validity execution_authority',
           'actual platform bundle')
    for key,expected in dict(schema_version='cpu-prefetch-q16c-platform-observations/1',
            request_sha256=request_sha256,plan_sha256=plan_sha256,observation_count=188,
            scientific_validity='NOT_ASSESSED',execution_authority=False).items():
        same(document[key],expected,'actual platform '+key)
    observations=document['observations']
    require(type(observations) is list and len(observations)==188,'two actual observations for all94 captures')
    witness=None;last=0;result=[]
    for index,row in enumerate(observations):
        ordinal=index//2;moment=MOMENTS[index%2]
        fields(row,'schema_version capture_ordinal moment request_sha256 plan_sha256 checkpoint observed_monotonic_ns scientific_validity execution_authority control',
               'platform observation')
        for key,expected in dict(schema_version='cpu-prefetch-q16c-compaction-observation/1',capture_ordinal=ordinal,
                moment=moment,request_sha256=request_sha256,plan_sha256=plan_sha256,
                scientific_validity='NOT_ASSESSED',execution_authority=False).items():
            same(row[key],expected,'actual capture platform '+key)
        stamp=row['observed_monotonic_ns']
        require(type(stamp) is int and stamp>last,'actual ordered observation clock')
        last=stamp;control=row['control']
        fields(control,'requested_value observed_value verified witness_sha256','verified guard observation')
        require(type(control['requested_value']) is int and type(control['observed_value']) is int,
                'actual integer control readback')
        same(control['requested_value'],0,'requested compaction control')
        same(control['observed_value'],0,'verified compaction control')
        same(control['verified'],True,'actual control verification')
        digest=control['witness_sha256']
        require(type(digest) is str and len(digest)==64 and all(c in '0123456789abcdef' for c in digest),'actual guard witness identity')
        if witness is None:witness=digest
        same(digest,witness,'one original guarded native family')
        if moment==MOMENTS[0]:same(row['checkpoint'],None,'before authorization cannot invent checkpoint')
        else:
            checkpoint=row['checkpoint']
            fields(checkpoint,'file_name size_bytes sha256','actual quiescent checkpoint')
            same(checkpoint['file_name'],f'formal-capture-{ordinal}-final-checkpoint.json','actual local checkpoint identity')
            require(type(checkpoint['size_bytes']) is int and checkpoint['size_bytes']>0,'actual checkpoint size')
            require(type(checkpoint['sha256']) is str and len(checkpoint['sha256'])==64
                and all(c in '0123456789abcdef' for c in checkpoint['sha256']),'actual checkpoint digest')
            result.append(dict(regime='VERIFIED_ZERO',requested_value=0,observed_value=0,
                witness_sha256=witness,before_monotonic_ns=observations[index-1]['observed_monotonic_ns'],
                after_monotonic_ns=stamp,checkpoint=checkpoint))
    return result


def evaluate(parent_bytes,plan,prefix_records,suffix_records,*,plan_binding,request_sha256,platform_binding):
    """Closed full-matrix composition; a missing/invalid input stops the family."""
    continuation.validate_parent(plan,parent_bytes)
    raw_plan=window.read(plan_binding)
    require(raw_plan==previous.archive.canonical(plan),'actual canonical native plan bytes differ')
    require(type(request_sha256) is str and len(request_sha256)==64
        and all(c in '0123456789abcdef' for c in request_sha256),'actual signed request identity')
    parent=window.parse(parent_bytes)
    old=_records(parent,prefix_records,86);new=_records(plan,suffix_records,94)
    prefix=window.parse(window.read(plan['continuation']['accepted_prefix_manifest']))
    fields(prefix,'schema_version parent_plan original_source_revision failed_family_receipt_sha256 analysis_completion reused_capture_ordinals reports compaction_control all_required_reports_valid scientific_method execution_authority phase18_authority',
           'accepted prefix manifest')
    for key,value in dict(schema_version=PREFIX_SCHEMA,parent_plan=plan['continuation']['parent_plan'],
            original_source_revision=continuation.PARENT_SOURCE,failed_family_receipt_sha256=continuation.FAILURE_SHA256,
            reused_capture_ordinals=list(range(86)),reports=[r['report_binding'] for r in old],
            compaction_control='UNRECORDED',all_required_reports_valid=True,scientific_method=previous.contract.COLLECTOR_METHOD,
            execution_authority=False,phase18_authority=False).items():same(prefix[key],value,'accepted prefix '+key)
    # Authenticate its completion bytes; never rerun the86 raw validators.
    completion=window.parse(window.read(prefix['analysis_completion']))
    same(completion['status'],'ALL_SELECTED_VALID','retained prefix completion')
    same(completion['kind'],'PREFIX86','retained prefix phase')
    platform=_platform(window.read(platform_binding),plan_sha256=plan_binding['sha256'],request_sha256=request_sha256)
    rows=[];identities=set();report_ids=set();run_ids=set()
    for retained,selected,family in ((True,old,continuation.PARENT_SHA256),(False,new,plan_binding['sha256'])):
        for row in selected:
            local=row['capture_ordinal'];global_ordinal=local if retained else 86+local
            identity=(family,local)
            require(identity not in identities,'duplicate composite family/capture identity');identities.add(identity)
            report_id=row['report_binding']['artifact_id']
            require(report_id not in report_ids,'duplicate original report artifact identity');report_ids.add(report_id)
            for phase in row['phases']:
                require(phase['run_id'] not in run_ids,'cross-family phase run identity reused');run_ids.add(phase['run_id'])
            rows.append(dict(row,original_ordinal=global_ordinal,family_plan_sha256=family,
                source_revision=parent['source_revision'] if retained else plan['source_revision'],
                platform=dict(regime='UNRECORDED',requested_value=None,observed_value=None) if retained else platform[local]))
    same([r['original_ordinal'] for r in rows],list(range(180)),'complete original matrix order')
    gates={}
    for index,name in enumerate(('warmup','measurement')):
        full=[r['original_ordinal'] for r in rows if not r['phases'][index]['zero_loss']]
        gates[name]=dict(zero_loss_gate='FAIL' if full else 'PASS',full_bearing_original_ordinals=full)
    return dict(schema_version=SCHEMA,action_id='Q16c',method_id=continuation.METHOD,
        collector_method_id=continuation.COLLECTOR_METHOD,stand_id=plan['stand_id'],status='DESCRIPTIVE_COMPLETE',
        parent_plan_sha256=continuation.PARENT_SHA256,continuation_plan_binding=plan_binding,
        accepted_prefix_manifest=plan['continuation']['accepted_prefix_manifest'],platform_observations=platform_binding,
        prospective=dict(settings=180,repetitions_per_cell=1,warmup_ns=5_000_000_000,measurement_ns=1_000_000_000,scale_ordinal=0),
        coverage=dict(planned=180,valid=180,retained=86,new=94,missing=0,invalid=0),run_sources=rows,
        platform_strata=[dict(regime='UNRECORDED',captures=86),dict(regime='VERIFIED_ZERO',captures=94)],
        homogeneous_platform_evidence=False,observed_zero_loss=gates,
        evidence_strength='DESCRIPTIVE_SINGLE_CAPTURE_PER_SETTING_WITH_PLATFORM_STRATA',confidence_claim=None,
        inferential_validity_established=False,final_matrix_feasibility='NOT_EVALUATED',final_scale_selection=None,
        execution_authority=False,phase18_authority=False)
