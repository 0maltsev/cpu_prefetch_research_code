"""Bounded offline validation of immutable E23 Q16a captures 0..176 only.

No experiment, retry, signing, family success, or continuation execution authority.
The copied original operator supplies unchanged spool, D212 callback and supervisor.
"""
from __future__ import annotations
import dataclasses
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import sys
import time
import types

HERE=Path(__file__).resolve().parent
BASE_SHA='5ed34087443a79c81ff00135bbfd4adb2e3f516770dd034be9f998ae69b0ac99'
base_path=HERE/'original_analysis.py'
raw=base_path.read_bytes()
if hashlib.sha256(raw).hexdigest()!=BASE_SHA:raise ValueError('original operator bytes differ')
spec=importlib.util.spec_from_file_location('prefix_original_analysis',base_path)
base=importlib.util.module_from_spec(spec);sys.modules[spec.name]=base
exec(compile(raw,str(base_path),'exec'),base.__dict__)
require,read,parse,save,sha,canonical=base.require,base.read,base.parse,base.save,base.sha,base.canonical
GIB=base.GIB
PLAN_SHA='a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7'
FAILURE_SHA='a6704159e3dd2adab1598e2959202cfa5a6a0b5c9164a01fab967deeb251c7e4'
REVISION='dd981b4fdcf953386d4a7514fec381ff9be6e359'
WORKER_SHA='2e54f9ab7752e8e0f8be02df76970cb94849c93e923cf625d38550a658963c4f'
ADAPTER_SHA='07a4bba1379c686a8f31e42aadeb93200a8574d55c7a1ffaea7b92606a6303f7'
PILOT_SHA='aa6c1da2c157aaabe9d1964b7fee25a1d4b8d38f1bd289468ccbdcb4ad6bece8'
PILOT_SIZE=80530880
PILOT_NAME='cpu-prefetch-pilot-candidate-2.0.0-dd981b4-clean-d9e61e67bfa8.tar.gz'
ROLES=('AUTHORIZATION','SIGNATURE','REQUEST','ATTEMPT','FAILURE')
SCHEMA='cpu-prefetch-stage17-q16a-accepted-prefix/1'


def packed_page_layout(item):
    """Exact prospective 42-query/84-array capacity, including 64-KiB slack.

    The discovery parser's 256-MiB ceiling is insufficient for the signed
    formal mappings. Derive this isolated reader's limit from those unchanged
    inputs; never infer it from observed values or mutate historical modules.
    """
    page=base.uint(item['capture']['geometry']['base_page_bytes'],'base page')
    require(page>0 and page&(page-1)==0,'base page geometry')
    regions=item['resources']['region_bytes']
    during=item['monitoring']['during_page_count']
    require(len(regions)==len(during)==7,'seven frozen residency regions')
    full=[]
    for size,count in zip(regions,during,strict=True):
        base.uint(size,'region bytes');base.uint(count,'during pages')
        require(size>0 and size%page==0 and count<=size//page,'frozen residency extent')
        full.append(size//page)
    counts=[]
    for _phase in range(2):
        for moment in range(3):
            for count in (during if moment==1 else full):
                counts.extend((count,count))
    capacity=sum(((count+8191)//8192)*65536 for count in counts)
    require(0<capacity<=512*1024**2,'formal packed page ceiling512MiB')
    return dict(method='SIGNED-FORMAL-RESIDENCY-PACKED-CAPACITY-v1',
                array_counts=counts,packed_capacity_bytes=capacity,
                maximum_packed_capacity_bytes=512*1024**2,
                original_discovery_limit_bytes=256*1024**2,
                block_items=8192,integer_bytes=8,execution_authority=False)


def formal_reader(common,stream,stack,item):
    layout=packed_page_layout(item)
    require(common.PAGE_BLOCK_ITEMS==8192,'unchanged 64KiB packed blocks')
    original=common.JsonReader.packed_pages
    require(not original.__code__.co_freevars,'packed reader has unexpected free variables')
    bounded=types.FunctionType(original.__code__,
        {**original.__globals__,'MAX_PACKED_PAGE_BYTES':layout['packed_capacity_bytes']})
    class FormalJson(common.JsonReader):
        arrays=0
        def packed_pages(self,key,depth):
            require(self.arrays<len(layout['array_counts']),'expanded residency arrays')
            result=bounded(self,key,depth)
            require(len(result)==layout['array_counts'][self.arrays],'frozen residency array count')
            self.arrays+=1
            return result
        def value(self,key='',depth=0):
            require(key!='drain_rows','unexpected discovery drain JSON in formal control; no scratch bypass')
            return super().value(key,depth)
        def document(self):
            result=super().document()
            require(self.arrays==84 and self.packed_bytes==layout['packed_capacity_bytes'],
                    'complete frozen residency capacity required')
            return result
    return FormalJson(stream,stack)


@contextlib.contextmanager
def formal_control_bounded(common,root,logical,*,item):
    with contextlib.ExitStack() as stack:
        raw=stack.enter_context(common.opened(root,logical))
        text=io.TextIOWrapper(raw,encoding='utf-8',errors='strict')
        try:yield formal_reader(common,text,stack,item).document()
        finally:text.detach()


_original_validate_spooled=base.validate_spooled
def validate_spooled_bounded(m,job):
    layout=packed_page_layout(job['item'])
    common=m.q16a_capture_validation_v1.common
    require(layout['packed_capacity_bytes']+common.MAX_RESIDENT_TEXT+common.MAX_ARENA_BYTES
            <job['resources']['capture_as_bytes'],'reader plus existing metadata/arena exceeds unchanged AS')
    def control(common,root,logical):
        return formal_control_bounded(common,root,logical,item=job['item'])
    callback=types.FunctionType(_original_validate_spooled.__code__,
                               {**vars(base),'formal_control':control})
    return callback(m,job)


# The original scheduler/decoder/validator/supervisor bytes stay unchanged.
# Only this explicit operator supplies its prospective control-reader capacity.
base.validate_spooled=validate_spooled_bounded



def load_adapter(binding, root):
    name='stage17_discovery_validation_parallel_v2'
    path=base.safe(binding['path'])
    require(path==HERE/(name+'.py') and not path.is_relative_to(root),'explicit separately staged adapter path')
    raw=read(binding)
    require(sha(raw)==ADAPTER_SHA,'original dd981 offline adapter bytes differ')
    require(name not in sys.modules,'offline adapter already imported from unverified path')
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    try:
        exec(compile(raw,str(path),'exec'),module.__dict__)
        require(Path(module.base.__file__).resolve()==root/'tools/stage17_discovery_validation_v3.py','adapter base escaped qualified R')
        require(sha(Path(module.base.__file__).read_bytes())==module.BASE_SHA256,'adapter base source hash differs')
        return module
    except BaseException:
        sys.modules.pop(name,None)
        raise


def modules(c):
    # Preserve the original full-policy source verification, but qualify only
    # capture modules as repository members. The offline scheduler is explicit.
    import importlib
    root=base.safe(c['repository_root']);policy=parse(read(c['files']['policy']))
    require(Path(c['files']['policy']['path'])==root/'config/stage17/stage17-operational-evidence-admission-policy-v58.json','policy path')
    pinned={}
    for section in ('runtime_closure','bindings'):
        for row in policy[section].values():
            rel=Path(row['path']);require(not rel.is_absolute() and '..' not in rel.parts,'policy locator')
            raw=read(dict(path=str(root/rel),size_bytes=row['size_bytes'],sha256=row['sha256']))
            if str(rel) in pinned:require(pinned[str(rel)]==raw,'conflicting policy pin')
            pinned[str(rel)]=raw
    sys.path.insert(0,str(root/'tools'))
    names=('stage17_operational_semantics_v17','stage17_phase_controller_v26','stage17_output_registry_v12',
        'stage17_formal_archive_v1','stage17_formal_archive_custody_v1','stage17_formal_archive_runtime_v1',
        'stage17_q16a_capture_validation_v1','stage17_formal_calibration_v2')
    loaded={name:importlib.import_module(name) for name in names}
    for name,module in loaded.items():
        require(Path(module.__file__).resolve()==root/'tools'/f'{name}.py','qualified import escaped repository')
        require('tools/'+name+'.py' in pinned,'qualified analysis dependency absent from policy')
    loaded['stage17_discovery_validation_parallel_v2']=load_adapter(c['parallel_adapter'],root)
    return types.SimpleNamespace(**{name.replace('stage17_',''):module for name,module in loaded.items()}),pinned


def config(path,digest):
    p=base.safe(path);c=parse(read(dict(path=str(p),size_bytes=p.stat().st_size,sha256=digest),65536))
    require(c['schema_version']=='software-offline-q16a-prefix-analysis/1','prefix config schema')
    require(c['operator_sha256']==sha(Path(__file__).read_bytes()),'prefix operator source')
    require(c['supervision_sha256']==base.SUPERVISION_SHA==sha((HERE/'d234_supervision.py').read_bytes()),'supervisor bytes')
    require(set(c['files'])==set(ROLES)|{'policy','historical_journal','parent_plan','capture_bindings'},'original prefix inputs')
    require(c['execution_authority'] is False,'offline only')
    original_transport(c)
    require(c['manifest_schema_sha256']==sha((HERE/'prefix-manifest.schema.json').read_bytes()),'manifest schema bytes')
    for name in ('repository_root','evidence_root','journal_directory','analysis_root'):base.safe(c[name])
    require(c['files']['parent_plan']['sha256']==PLAN_SHA and c['files']['FAILURE']['sha256']==FAILURE_SHA,'fixed E23 parent/failure')
    r=c['resources']
    for key in ('supervisor_as_bytes','coordinator_as_bytes','capture_as_bytes','total_memory_bytes','memory_reserve_bytes','timeout_seconds','metadata_bytes','filesystem_overhead_bytes','canonical_capture_bytes','worker_count'):base.uint(r[key],key)
    require(r['supervisor_as_bytes']==r['coordinator_as_bytes']==2*GIB and r['capture_as_bytes']==8*GIB,'reviewed process AS bounds')
    require(r['worker_count'] in (1,2,3,4),'finite one-to-four workers')
    require(r['total_memory_bytes']==(4+8*r['worker_count'])*GIB,'aggregate includes both parent processes')
    require(r['runtime']['codec_address_space_bytes']==2*GIB,'qualified decoder AS')
    require(r['metadata_bytes']==2*GIB and r['filesystem_overhead_bytes']>=256*1024**2,'metadata/filesystem reservations')
    scratch_proof(r)
    return c


def scratch_proof(r):
    total=r['canonical_capture_bytes']*r['worker_count']+r['metadata_bytes']+r['filesystem_overhead_bytes']
    require(total<=base.SCRATCH,'aggregate scratch exceeds signed 256GiB ceiling')
    return dict(worker_count=r['worker_count'],canonical_bytes_per_capture=r['canonical_capture_bytes'],
        retained_metadata_bytes=r['metadata_bytes'],filesystem_overhead_bytes=r['filesystem_overhead_bytes'],
        parser_drain_spool_bytes=0,total_bytes=total,scratch_ceiling_bytes=base.SCRATCH)


def validate_failure_lifecycle(request,auth,attempt,failure,bindings,parse_utc):
    """Check failure/6 honestly; never manufacture RESULT or COMPLETION."""
    require(request['action_id']=='Q16a' and request['schema_version']=='cpu-prefetch-stage17-fixed-action-request/6','original Q16a request')
    require(request['runtime_binding']['sha256']==WORKER_SHA,'original measured worker')
    for doc,kind in ((attempt,'attempt'),(failure,'failure')):
        require(doc['schema_version']==f'cpu-prefetch-stage17-phase-action-{kind}/6','original lifecycle schema')
        for key in ('action_id','attempt_id'):require(doc[key]==request[key],key+' differs')
        require(doc['request_sha256']==bindings['REQUEST']['sha256'] and doc['authorization_sha256']==bindings['AUTHORIZATION']['sha256'],'lifecycle original hashes')
        require(doc['runtime_sha256']==WORKER_SHA and doc['phase18_authority'] is False,'runtime/authority differs')
    require(attempt['authorization_id']==request['authorization_id'] and attempt['evidence_root_binding']==request['evidence_root_binding'],'attempt root/authority')
    require(attempt['release_resolution_id']==request['release_binding']['source_resolution_id'] and attempt['release_resolution_sha256']==request['release_binding']['source_resolution_sha256'],'attempt release')
    require(attempt['one_attempt'] is True and attempt['retries']==0 and attempt['marker_durable'] is True,'one-shot original marker')
    require(failure['failure_id']==request['attempt_id']+':failure','failure ID')
    for name in ('leader_reaped','process_group_gone','restoration_verified','partial_retained'):require(failure[name] is True,'failed family '+name)
    require(failure['quarantine_operation']==dict(performed=False,record_sha256=None),'quarantine not cleared')
    pre={r['cpu']:r['complete_value_hex'] for r in request['action_inputs']['hardware_control']['prestate']}
    rows=failure['recovery_readback'];require(len(rows)==len(pre),'restoration coverage')
    seen=set()
    for row in rows:
        require(set(row)=={'cpu','matches','observed_hex','requested_hex'} and row['cpu'] in pre and row['cpu'] not in seen,'restoration CPU identity')
        require(row['matches'] is True and row['observed_hex']==row['requested_hex']==pre[row['cpu']],'original full-register restoration')
        seen.add(row['cpu'])
    issued,expires,started,ended=map(parse_utc,(auth['issued_at_utc'],auth['expires_at_utc'],attempt['started_at_utc'],failure['completed_at_utc']))
    require(issued<=started<expires and started<=ended<=expires,'original authority timestamps')


def validate_selection(plan,index):
    require(sha(canonical(plan))==PLAN_SHA and plan['source_revision']==REVISION,'original plan/source')
    require(len(plan['captures'])==708 and plan['repetitions_per_context']==59,'original full prospective family')
    require(type(index) is list and len(index)==178,'all177 complete plus failed boundary bindings required')
    for ordinal,row in enumerate(index):
        require(set(row)=={'original_ordinal','checkpoint','custody_receipt'} and row['original_ordinal']==ordinal,'exact ordered prefix and boundary')
        cap=plan['captures'][ordinal]['capture']
        require(cap['ordinal']==ordinal and (cap['context_ordinal'],cap['repetition_ordinal'])==divmod(ordinal,59),'parent scientific slots')
        for key,suffix in (('checkpoint','final-checkpoint'),('custody_receipt','archive-custody')):
            require(Path(row[key]['path']).name==f'formal-capture-{ordinal}-{suffix}.json','capture binding filename')


def validate_failed_zero(final,receipt):
    require(final['capture_ordinal']==177 and final['native_complete'] is False,'original failed boundary')
    phases=final['native_result_after_cleanup']['session']['phases']
    require(len(phases)==2,'failed phases')
    for phase in phases:
        require(phase['released'] is False,'failed boundary released a phase')
        for owner,fields in (('producer',('attempted','accepted','full')),('consumer',('polls','consumed_including_drain','empty'))):
            require(all(type(phase[owner][k]) is int and phase[owner][k]==0 for k in fields),'failed boundary has observations')
    refs=final['artifacts'];require(len(refs)==9 and len(receipt['artifacts'])==9,'failed original artifact coverage')
    for ref,row in zip(refs,receipt['artifacts'],strict=True):
        require(row['logical']==row['expected_logical']==ref and row['failure_receipt'] is None,'failed original logical identity')
    require(all(r['size_bytes']==0 and r['sha256']==sha(b'') for r in refs[:8]),'failed raw streams nonempty')


def bound_name(value):
    return dict(file_name=Path(value['path']).name,size_bytes=value['size_bytes'],sha256=value['sha256'])


def verify_failed(store,registry,checkpoint_module,index,plan,profile,decode):
    """Authenticate failed boundary custody, without granting native completion."""
    row=index[177];final=parse(read(row['checkpoint']));receipt=parse(read(row['custody_receipt']))
    validate_failed_zero(final,receipt)
    cp=bound_name(row['checkpoint']);rb=bound_name(row['custody_receipt']);same=registry.same
    require(set(receipt)==registry.RECEIPT_FIELDS,'failed receipt fields')
    for key,value in dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',program_scope_sha256=store.scope_sha256,
        plan_sha256=store.family_id,capture_ordinal=177,checkpoint=cp,status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False).items():same(receipt[key],value,'failed '+key)
    tip=registry._ledger(store,receipt['ledger_tip'])
    next_record=store.read_verified_record(store._record_bindings[tip['sequence']+1])
    same(next_record['kind'],'CUSTODY_RECEIPT','failed ledger receipt kind')
    same(next_record['payload'],dict(family_id=store.family_id,checkpoint_sha256=cp['sha256'],receipt=rb),'failed receipt ledger binding')
    sources=[]
    for name,artifact in zip(registry.capture_names('Q16a',177),receipt['artifacts'],strict=True):
        require(set(artifact)==registry.ARTIFACT_FIELDS,'failed artifact fields')
        identity=store.family_id+':'+name;same(artifact['artifact_id'],identity,'failed artifact identity')
        logical=registry.custody.BoundFile(**artifact['logical']);same(logical.file_name,name,'failed logical role')
        source=registry.custody.SourceBinding(identity,logical,logical.binding(),None);sources.append(source)
        record=registry._ledger(store,artifact['released_record'])
        same(record,store._states[identity],'failed current released state');same(record['kind'],'RELEASED','failed released kind')
        same(record['artifact_id'],identity,'failed released ID');require(record['sequence']<=tip['sequence'],'failed release after receipt')
        payload=record['payload'];same(payload['source'],dataclasses.asdict(source),'failed original source');same(payload['checkpoint_sha256'],cp['sha256'],'failed release checkpoint')
        same(payload['storage_domain_id'],store.scope['storage_domain_id'],'failed storage domain')
        archive_name=sha(identity.encode())+'.cpfa';same(artifact['archive_name'],archive_name,'failed archive name');same(payload['archive_name'],archive_name,'failed released archive name')
        same(payload['physical'],artifact['physical'],'failed physical');role=registry.role_profile('Q16a',name);same(payload['role'],dataclasses.asdict(role),'failed role')
        header=payload['header'];same(header['artifact_id'],identity,'failed header identity')
        phase=next((p for p in ('warmup','measurement') if '-'+p+'-' in name),None)
        same(header['phase'],phase,'failed header phase')
        same(header['run_id'],plan['captures'][177]['capture'][phase]['run_id'] if phase else None,'failed header run')
        same(header['worker'],next((w for w in ('producer','consumer') if '-'+w in name),None),'failed header worker')
        same(header['canonical_size_bytes'],logical.size_bytes,'failed canonical size');same(header['canonical_sha256'],logical.sha256,'failed canonical SHA')
        # Full bounded inverse of all failed artifacts, including the entire
        # control stream; no output materialization or scientific success claim.
        registry.archive.verify_archive(store.root/'archives'/archive_name,expected_header=header,role=role,
            physical=registry.archive.PhysicalBinding(**artifact['physical']),profile=profile.decoder,limits=decode)
    checkpoint_module.validate_checkpoint(final,action='Q16a',plan_sha256=store.family_id,capture=plan['captures'][177]['capture'],sources=tuple(sources))
    store._read_bound(store.root/'metadata'/('checkpoint-'+cp['sha256']+'.json'),registry.custody.BoundFile(**cp).binding(),store.limits.max_checkpoint_bytes)
    return dict(original_ordinal=177,checkpoint=row['checkpoint'],custody_receipt=row['custody_receipt'],zero_raw_observations=True,
                both_phases_unreleased=True,physical_custody_verified=True,inverse_readback_performed=True,scientific_validity='NOT_ASSESSED')



def original_transport(c):
    archive=c['pilot_archive'];sidecar=c['pilot_sidecar']
    expected=Path(c['evidence_root']).parent/PILOT_NAME
    require(Path(archive['path'])==expected and Path(sidecar['path'])==Path(str(expected)+'.sha256'),'original archive transport paths')
    require(archive['sha256']==PILOT_SHA and archive['size_bytes']==PILOT_SIZE,'original qualified archive binding')
    read(archive)
    require(read(sidecar)==(PILOT_SHA+'  '+PILOT_NAME+'\n').encode(),'original archive sidecar bytes')
    return Path(archive['path']),Path(sidecar['path'])


def prepare_original(c,m):
    """Full historical retention preparation, never collection or raw parsing."""
    files=c['files'];docs={key:parse(read(files[key])) for key in ROLES if key!='SIGNATURE'}
    request=docs['REQUEST'];archive,sidecar=original_transport(c)
    prepared=m.phase_controller_v26.prepare_retention(repository_root=Path(c['repository_root']),operational_evidence_root=Path(c['evidence_root']),
        journal=Path(files['historical_journal']['path']),journal_directory=Path(c['journal_directory']),
        authorization_path=Path(files['AUTHORIZATION']['path']),signature_path=Path(files['SIGNATURE']['path']),synthetic_test_only=False,pilot_archive=archive,pilot_sidecar=sidecar)
    require(prepared.authorization_bytes==read(files['AUTHORIZATION']) and prepared.request_bytes==read(files['REQUEST']),'prepared original authority/request')
    require(sha(read(files['historical_journal']))==prepared.validation.latest_journal_sha256,'original historical journal')
    require(set(prepared.validation.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,7)},'original six qualification dependencies')
    for key,kind in (('ATTEMPT','attempt'),('FAILURE','failure')):
        m.output_registry_v12.validate_document(prepared.registry,docs[key],m.output_registry_v12.schema_path('phase-action-'+kind),'original '+key)
    validate_failure_lifecycle(request,docs['AUTHORIZATION'],docs['ATTEMPT'],docs['FAILURE'],files,m.phase_controller_v26.support._parse_utc)
    return prepared


def coordinate(c,deadline):
    root=Path(c['analysis_root']);r=c['resources'];m,pinned=modules(c)
    from importlib import import_module
    registry=import_module('stage17_formal_archive_registry_v1');cp=import_module('stage17_formal_checkpoint_v1')
    files=c['files'];docs={key:parse(read(files[key])) for key in ROLES if key!='SIGNATURE'}
    plan=parse(read(files['parent_plan']));index=parse(read(files['capture_bindings']))
    validate_selection(plan,index);request=docs['REQUEST'];require(canonical(request['action_inputs']['plan'])==read(files['parent_plan']),'request embeds original plan bytes')
    prepared=prepare_original(c,m)
    phase=Path(request['evidence_root_binding']['absolute_path']);require(phase.name==PLAN_SHA and phase.parent.name=='working','signed original family path')
    for key in ('ATTEMPT','FAILURE'):require(Path(files[key]['path']).parent==phase,'original lifecycle root')
    for row in index:
        for key in ('checkpoint','custody_receipt'):require(Path(row[key]['path']).parent==phase,'original capture root')
    roots=m.output_registry_v12.roots
    fd,identity=roots._componentwise_output_root(phase,Path(c['repository_root']),request['evidence_root_binding'])
    storage=plan['storage'];profile=prepared.archive_runtime_profile
    require(r['canonical_capture_bytes']<=storage['analysis_capture_workspace_bytes'],'signed spool ceiling')
    require(r['total_memory_bytes']<=plan['budget']['memory_bytes'],'signed family memory ceiling')
    custody=m.formal_archive_custody_v1.CustodyLimits(**r['custody'],deadline_ns=deadline)
    decode=m.formal_archive_v1.DecodeLimits(**r['decoder'],deadline_ns=deadline);decode.validate()
    require(decode.max_canonical_bytes<=r['canonical_capture_bytes'] and decode.max_archive_bytes<=storage['archive_quota_bytes'],'decoder signed bounds')
    page_proofs=[dict(context_ordinal=i//59,**packed_page_layout(plan['captures'][i])) for i in (0,59,118)]
    analysis_binding=save(root/'original-analysis-limits.json',dict(resources=r,scratch=scratch_proof(r),deadline_monotonic_ns=deadline,source_plan_sha256=PLAN_SHA,parallel_adapter=c['parallel_adapter'],pilot_archive=c['pilot_archive'],pilot_sidecar=c['pilot_sidecar'],formal_control_reader=page_proofs,execution_authority=False),65536)
    try:
        with m.formal_archive_custody_v1.ProgramStore(phase.parent.parent,scope_sha256=storage['program_scope_sha256'],family_id=PLAN_SHA,limits=custody) as store:
            require(store.scope['program_id']==storage['program_id'],'program ID')
            family=store._families[PLAN_SHA];require((family['device'],family['inode'])==identity,'original ledger root')
            store._family_identity=identity
            expected={PLAN_SHA+':'+name for ordinal in range(178) for name in registry.capture_names('Q16a',ordinal)}
            require({k for k in store._states if k.startswith(PLAN_SHA+':')}==expected,'exact retained177+failed boundary artifact set')
            require(not any(f==PLAN_SHA for f,_ in store._capture_pending),'unfinished original checkpoint')
            require(store.physical_usage()+store.reserved_bytes()<=m.formal_archive_custody_v1.PROGRAM_QUOTA,'shared program physical quota')
            ledger_before=dataclasses.asdict(store.ledger_binding())
            (root/'reports').mkdir(mode=0o700)
            verified=[]
            for row,item in zip(index[:177],plan['captures'][:177],strict=True):
                read(row['checkpoint']);read(row['custody_receipt'])
                cap=registry.verify_capture_metadata(store=store,action='Q16a',capture=item['capture'],checkpoint_binding=bound_name(row['checkpoint']),
                    receipt_binding=bound_name(row['custody_receipt']),decoder_profile=profile.decoder,decoder_limits=decode)
                verified.append(cap)
            failed=verify_failed(store,registry,cp,index,plan,profile,decode)
            inventory_binding=save(root/'authenticated-prefix-custody.json',dict(captures=verified,failed_boundary=failed,ledger_head=ledger_before,execution_authority=False),r['metadata_bytes']//4)
            decoder_profile=m.formal_archive_runtime_v1._jsonable(dataclasses.asdict(profile.decoder))
            jobs=[dict(item=item,verified=cap,resources=r,decoder_profile=decoder_profile,decoder_limits=dataclasses.asdict(decode),
                program_root=str(store.root),scratch=str(root/'scratch'),reports=str(root/'reports'),hardware_control=request['action_inputs']['hardware_control'])
                for item,cap in zip(plan['captures'][:177],verified,strict=True)]
            for job in jobs:require(sum(a['logical']['size_bytes'] for a in job['verified']['artifacts'])<=r['canonical_capture_bytes'],'actual canonical capture exceeds proof')
            outputs=base.ordered_pool(m,jobs,c,deadline)
            require(len(outputs)==177,'all177 independently validated reports required')
            captures=[]
            for ordinal,(output,item,cap) in enumerate(zip(outputs,plan['captures'][:177],verified,strict=True)):
                report=parse(read(output,r['metadata_bytes']//(708*3+16)))
                require(report['capture_ordinal']==ordinal and report['raw_reconciliation_validated'] is True and report['capture_execution_evidence_validated'] is True,'validated report identity/coverage')
                capture=item['capture']
                captures.append(dict(original_ordinal=ordinal,context_ordinal=capture['context_ordinal'],repetition_ordinal=capture['repetition_ordinal'],
                    checkpoint_binding=index[ordinal]['checkpoint'],custody_binding=index[ordinal]['custody_receipt'],validation_report_binding=output))
            for original in files.values():read(original)
            for row in index:
                read(row['checkpoint']);read(row['custody_receipt'])
            require(dataclasses.asdict(store.ledger_binding())==ledger_before,'original ledger changed')
            roots._verify_root_identity(fd,identity);store._check()
            validator_sources=[base.binding(Path(module.__file__)) for module in (m.q16a_capture_validation_v1,m.q16a_capture_validation_v1.demand,m.q16a_capture_validation_v1.common,registry,m.formal_archive_custody_v1,m.formal_archive_v1,cp)]
            validator_sources.extend([base.binding(Path(__file__)),base.binding(base_path),base.binding(HERE/'d234_supervision.py'),base.binding(Path(m.discovery_validation_parallel_v2.__file__))])
            manifest=dict(schema_version=SCHEMA,status='VALIDATED',method_id=m.q16a_capture_validation_v1.demand.METHOD_ID,
                parent_plan=files['parent_plan'],failed_family_receipt=files['FAILURE'],original_plan_sha256=PLAN_SHA,original_failure_sha256=FAILURE_SHA,original_source_revision=REVISION,worker_sha256=WORKER_SHA,
                original_authority={k:files[k] for k in ('AUTHORIZATION','SIGNATURE','REQUEST','ATTEMPT','historical_journal')},
                program_scope_sha256=store.scope_sha256,program_root_binding=m.output_registry_v12._root_binding(store.root),ledger_head=ledger_before,
                contexts=[0,1,2],required_count=177,records=captures,validator_source_files=validator_sources,failed_boundary=failed,retained_failure_restoration_verified=True,
                analysis_limits=analysis_binding,authenticated_custody=inventory_binding,analysis_operator=base.binding(Path(__file__)),
                original_analysis_operator=base.binding(base_path),qualified_policy=files['policy'],family_validity_established=False,
                execution_authority=False,phase18_authority=False)
            from jsonschema import Draft202012Validator
            Draft202012Validator(parse((HERE/'prefix-manifest.schema.json').read_bytes())).validate(manifest)
            save(root/'accepted-prefix-manifest.json',manifest,r['metadata_bytes']//2)
    finally:os.close(fd)


def main():
    # Original supervisor/argv/resource controls; only configuration and coordinator
    # dispatch differ. __file__ ensures the child invokes this prefix operator.
    fn=types.FunctionType(base.main.__code__,{**vars(base),'config':config,'coordinate':coordinate,'__file__':__file__,
        'scratch_proof':lambda a,b,c,d:scratch_proof(dict(canonical_capture_bytes=a,worker_count=b,metadata_bytes=c,filesystem_overhead_bytes=d))})
    return fn()


if __name__=='__main__':raise SystemExit(main())
