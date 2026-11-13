"""D240/D244 retained suffix metadata admission; no raw decode or collection.

The per-capture check preserves admission_v1 logic, with explicit local ordinal
and source-family SHA parameters. Qualified capture code remains immutable.
"""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import stat
from types import SimpleNamespace
import time
import types

import stage17_q16a_continuation_admission_v1 as previous
import stage17_operational_semantics_v17 as semantics
import stage17_phase_controller_v26 as controller

require,same,fields=previous.require,previous.same,previous.fields
registry,archive_registry,calibration=previous.registry,previous.archive_registry,previous.calibration
_bound_name,_ledger_record,_json=previous._bound_name,previous._ledger_record,previous._json
MAX_FILE_BYTES=previous.MAX_FILE_BYTES
PLAN_SHA='91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
CONFIG_SHA='5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
PACKET_SHA='73411f7d55e67e53e1e398755420a906f8804126cfd99f29319e1e0831c7be3c'
FINALIZER_SHA='2efbac4f4b7e320db1c0694822fadaf41ffa3424cda5bd9f671b417a946c2d95'


class AnalysisIncomplete(previous.AdmissionError):
    pass


def _current_binding(path):
    path=Path(path)
    require(path.resolve(strict=True)==path,'symlink in current evidence path')
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size<=MAX_FILE_BYTES,'bounded regular evidence file')
        data=stream.read(MAX_FILE_BYTES+1)
        after=os.fstat(stream.fileno())
    require(len(data)==before.st_size<=MAX_FILE_BYTES and previous._stamp(before)==previous._stamp(after)==previous._stamp(path.lstat()),
            'current evidence changed during binding')
    return dict(path=str(path),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def _check_process_observations(document,expected_exit):
    for key,value in dict(status='ANALYSIS_EXITED',exit_code=expected_exit,all_own_children_reaped=True,
                          execution_authority=False,raw_mutation=False).items():
        # bool and integer comparisons must remain distinct.
        require(type(document.get(key)) is type(value) and document[key]==value,'analysis process '+key)
    elapsed=document.get('elapsed_seconds')
    require(type(elapsed) in (int,float) and math.isfinite(elapsed) and 0<=elapsed<=259200,'finite analysis duration')
    used=document.get('maximum_sampled_scratch_bytes')
    require(type(used) is int and 0<=used<=256*1024**3,'analysis scratch ceiling')


def check_process_result(document):
    _check_process_observations(document,0)


def verify_finalization(reader,binding,process_binding,process,c):
    """Accept only the explicit D245 ledger-shape supplement, never hide failure."""
    _check_process_observations(process,1)
    d=reader.document(binding)
    fields(d,'schema_version status original_process original_stderr configuration_sha256 operator validation_module ledger_file_binding ledger_summary stable_ledger_file_binding suffix_manifest validated_reports raw_redecode_performed raw_mutation execution_authority phase18_authority completed_at_utc','finalization supplement')
    for key,value in dict(schema_version='software-q16a-retained-finalization/1',status='FINALIZED_FROM_RETAINED_REPORTS',
            original_process=process_binding,configuration_sha256=CONFIG_SHA,validated_reports=531,
            raw_redecode_performed=False,raw_mutation=False,execution_authority=False,phase18_authority=False).items():
        same(d[key],value,'finalization '+key)
    same(d['operator']['sha256'],FINALIZER_SHA,'reviewed metadata finalizer')
    reader.read(d['operator']);reader.read(d['validation_module'])
    same(d['validation_module']['sha256'],hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'metadata validation source')
    A=Path(c['analysis_root'])
    same(d['original_stderr']['path'],str(A/'analysis-stderr.log'),'original error path')
    stderr=reader.read(d['original_stderr']).decode('utf-8',errors='strict')
    require(stderr.rstrip().splitlines()[-1:] == ['ValueError: ledger changed during offline validation']
            and 'validate_suffix.py' in stderr,'exact original ledger comparison error required')
    same(d['ledger_file_binding'],d['stable_ledger_file_binding'],'unchanged original ledger file')
    same(d['ledger_summary']['sha256'],d['ledger_file_binding']['sha256'],'same ledger tip in both representations')
    phase=Path(c['files']['RESULT']['path']).parent
    current=_ledger_record(reader,phase.parent.parent/'ledger',d['ledger_file_binding'])
    same(current['sequence'],d['ledger_summary']['sequence_number'],'original ledger sequence projection')
    same(d['suffix_manifest']['path'],str(A/'validated-suffix-manifest.json'),'corrected suffix manifest path')
    reader.read(d['suffix_manifest'])
    return d


def match_signed_capture(cap,declared,ordinal):
    for key,name in [('checkpoint',f'formal-capture-{ordinal}-final-checkpoint.json'),
                     ('custody_receipt',f'formal-capture-{ordinal}-archive-custody.json')]:
        same(cap[key],declared[name],'signed original '+key)
    same([a['logical']['file_name'] for a in cap['artifacts']],list(registry.capture_names('Q16a',ordinal)),'signed canonical artifact order')
    for artifact in cap['artifacts']:
        same(artifact['logical'],declared[artifact['logical']['file_name']],'signed original canonical artifact')


class EvidenceReader(previous.BoundReader):
    # This offline metadata gate has separate finite bounds. Historical prefix
    # admission's limits and globals remain unchanged.
    def __init__(self):
        super().__init__()
        self.deadline=time.monotonic()+1800
    read=types.FunctionType(previous.BoundReader.read.__code__,
        {**previous.BoundReader.read.__globals__,'MAX_FILES':12000,'MAX_TOTAL_BYTES':512*1024**2})


def _checkpoint_identity(document,capture,logical,family_sha):
    sources=tuple(SimpleNamespace(expected=SimpleNamespace(**r)) for r in logical)
    previous.checkpoint.validate_checkpoint(document,action='Q16a',plan_sha256=family_sha,capture=capture,sources=sources)


def validate_capture(row, authenticated, parent, scope_sha, reader, *, family_sha):
    fields(row, 'local_ordinal context_ordinal repetition_ordinal checkpoint_binding custody_binding validation_report_binding','prefix row')
    ordinal = row['local_ordinal'];item=parent['captures'][ordinal];capture=item['capture']
    same([row['context_ordinal'],row['repetition_ordinal']],[capture['context_ordinal'],capture['repetition_ordinal']],'prefix context/repetition')
    cp = reader.document(row['checkpoint_binding']);receipt=reader.document(row['custody_binding']);report=reader.document(row['validation_report_binding'])
    same(_bound_name(row['checkpoint_binding'])['file_name'],f'formal-capture-{ordinal}-final-checkpoint.json','checkpoint filename')
    same(_bound_name(row['custody_binding'])['file_name'],f'formal-capture-{ordinal}-archive-custody.json','custody filename')
    for key,value in dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',capture_ordinal=ordinal,
            plan_sha256=family_sha,program_scope_sha256=scope_sha,checkpoint=_bound_name(row['checkpoint_binding']),
            status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False).items():
        same(receipt[key],value,'capture custody '+key)
    names=registry.capture_names('Q16a',ordinal)
    require(len(receipt['artifacts'])==len(names)==9,'nine original artifacts required')
    logical=[]
    require(len(authenticated['artifacts'])==9,'authenticated custody artifact count')
    ledger_root=Path(row['checkpoint_binding']['path']).parent.parent.parent/'ledger'
    tip=_ledger_record(reader,ledger_root,receipt['ledger_tip'])
    for name,artifact,verified in zip(names,receipt['artifacts'],authenticated['artifacts'],strict=True):
        same(artifact['logical']['file_name'],name,'logical artifact filename')
        same(artifact['logical'],artifact['expected_logical'],'no logical discrepancy')
        same(artifact['failure_receipt'],None,'no capture integrity failure')
        same(artifact['artifact_id'],family_sha+':'+name,'original artifact identity')
        for field in ('artifact_id','logical','physical','archive_name','released_record'):
            same(artifact[field],verified[field],'authenticated original '+field)
        header=verified['header'];same(header['artifact_id'],artifact['artifact_id'],'archive header identity')
        same(header['canonical_sha256'],artifact['logical']['sha256'],'canonical header hash')
        same(header['canonical_size_bytes'],artifact['logical']['size_bytes'],'canonical header size')
        phase=next((p for p in ('warmup','measurement') if '-'+p+'-' in name),None)
        worker=next((w for w in ('producer','consumer') if '-'+w in name),None)
        same(header['phase'],phase,'archive phase identity')
        same(header['run_id'],capture[phase]['run_id'] if phase else None,'archive run identity')
        same(header['worker'],worker,'archive worker identity')
        same(verified['role'],vars(archive_registry.role_profile('Q16a',name)),'archive role and canonical format')
        release=_ledger_record(reader,ledger_root,artifact['released_record'])
        same(release['kind'],'RELEASED','original released transition')
        same(release['artifact_id'],artifact['artifact_id'],'released artifact identity')
        require(release['sequence']<=tip['sequence'],'release after custody tip')
        for field in ('header','physical','archive_name'):
            same(release['payload'][field],verified[field],'released original '+field)
        same(release['payload']['checkpoint_sha256'],row['checkpoint_binding']['sha256'],'released checkpoint')
        logical.append(artifact['logical'])
    same(cp['artifacts'],logical,'checkpoint original artifact order')
    _checkpoint_identity(cp,capture,logical,family_sha)
    same(cp['native_complete'],True,'prefix native completion')
    same(authenticated['capture_ordinal'],ordinal,'authenticated capture ordinal')
    same(authenticated['checkpoint'],_bound_name(row['checkpoint_binding']),'authenticated checkpoint')
    same(authenticated['custody_receipt'],_bound_name(row['custody_binding']),'authenticated receipt')
    same(authenticated['native_result_after_cleanup'],cp['native_result_after_cleanup'],'original complete native result')
    same(authenticated['execution_authority'],False,'custody no authority')
    registration_path=ledger_root/f'{tip["sequence"]+1:016d}.json'
    # The record following the tip is the original receipt registration. Its
    # own bytes are bounded here; the prefix operator authenticated the chain.
    require(registration_path.is_file(),'original receipt registration missing')
    raw_size=registration_path.stat().st_size
    require(raw_size<=MAX_FILE_BYTES,'receipt registration bound')
    with registration_path.open('rb') as stream:
        registration_raw=stream.read(MAX_FILE_BYTES+1)
    registration=_json(reader.read(dict(path=str(registration_path),size_bytes=raw_size,
        sha256=hashlib.sha256(registration_raw).hexdigest())))
    same(registration['previous_sha256'],receipt['ledger_tip']['sha256'],'receipt registration previous tip')
    same(registration['kind'],'CUSTODY_RECEIPT','receipt registration kind')
    same(registration['payload'],dict(family_id=family_sha,
        checkpoint_sha256=row['checkpoint_binding']['sha256'],receipt=_bound_name(row['custody_binding'])),
        'registered original custody receipt')
    # The existing D230 adapter checks both original D212 phase reports and
    # positive-series/quantile/minimum rules, preserving FULL as a separate gate.
    summary=calibration._valid_summary('Q16a',report,capture,item['resources'])
    indexed={r['file_name']:r for r in logical}
    for index,phase in enumerate(report['phases']):
        native=cp['native_result_after_cleanup']['session']['phases'][index]
        for field in ('attempted','accepted','full'):
            same(phase['counts'][field],native['producer'][field],'independent versus native producer '+field)
        for field in ('polls','empty','consumed_including_drain'):
            same(phase['counts'][field],native['consumer'][field],'independent versus native consumer '+field)
        for role in ('producer','consumer'):
            name=f'q16a-c{ordinal}-{phase["phase"]}-{role}'
            same(phase['stream_sha256'][role],indexed[name+'.bin']['sha256'],'primary report original hash')
            demand=indexed[name+'-demand.bin']
            same(phase['stream_sha256'][role+'_demand'],demand['sha256'],'demand report original hash')
            stream=phase['demand'][role]['stream']
            same([stream['sha256'],stream['size_bytes']],[demand['sha256'],demand['size_bytes']],'demand decoded binding')
    return summary


def authenticate(*, prepared, configuration_binding, finalization_binding=None):
    """Read actual finished D244 evidence against the controller's prepared trust.

    ``prepared`` must originate from qualified prepare_retention. This function
    rechecks signatures, chronology, restoration and original artifact linkage;
    no supplied validation boolean or partial process can substitute for them.
    """
    require(isinstance(prepared,controller.PreparedArchiveAction),'qualified archived preparation required')
    reader=EvidenceReader()
    c=reader.document(configuration_binding)
    same(configuration_binding['sha256'],CONFIG_SHA,'approved D244 configuration')
    same(c['schema_version'],'software-offline-q16a-suffix-analysis/1','offline config version')
    same(c['execution_authority'],False,'offline config authority')
    same(c['repository_root'],str(prepared.root),'qualified repository root')
    plan=prepared.request['action_inputs']['plan']
    same(hashlib.sha256(previous.canonical(plan)).hexdigest(),PLAN_SHA,'incident suffix plan')
    analysis=Path(c['analysis_root'])
    process_path=analysis/'analysis-process-result.json'
    if not process_path.is_file():
        raise AnalysisIncomplete('retained suffix analysis has not finished; no composition admission')
    previous.contract.validate_plan(plan)
    # elapsed_seconds is administrative timing. Scientific packets below retain
    # the strict integer-only parser; do not rewrite this original receipt.
    process_binding=_current_binding(process_path)
    process=json.loads(reader.read(process_binding),object_pairs_hook=calibration._unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite process JSON')))
    finalization=None
    if finalization_binding is None:
        check_process_result(process)
    else:
        finalization=verify_finalization(reader,finalization_binding,process_binding,process,c)
    packet=Path(c['parallel_adapter']['path']).parent
    packet_binding=_current_binding(packet/'manifest.json')
    same(packet_binding['sha256'],PACKET_SHA,'approved D244 operator packet')
    for row in reader.document(packet_binding)['files']:
        require(Path(row['name']).name==row['name'],'flat operator source name')
        reader.read(dict(path=str(packet/row['name']),size_bytes=row['size_bytes'],sha256=row['sha256']))
    same(c['operator_sha256'],_current_binding(packet/'validate_suffix.py')['sha256'],'actual offline entrypoint')
    sources=[]
    for role in semantics.ROLES:
        b=c['files'][role];raw=reader.read(b)
        sources.append(semantics.reader.Artifact('Q16A_'+role,Path(b['path']),raw,len(raw),hashlib.sha256(raw).hexdigest(),
            None if role=='SIGNATURE' else _json(raw),dict(artifact_id=role)))
    require(prepared.request_bytes==reader.read(c['files']['REQUEST']),'prepared request bytes differ')
    require(prepared.authorization_bytes==reader.read(c['files']['AUTHORIZATION']),'prepared authorization bytes differ')
    policy=reader.document(c['files']['policy']);pinned={}
    for section in ('runtime_closure','bindings'):
        for row in policy[section].values():
            rel=Path(row['path']);require(not rel.is_absolute() and '..' not in rel.parts,'qualified source locator')
            raw=reader.read(dict(path=str(prepared.root/rel),size_bytes=row['size_bytes'],sha256=row['sha256']))
            if str(rel) in pinned:require(raw==pinned[str(rel)],'inconsistent source pin')
            pinned[str(rel)]=raw
    for role,family in [('AUTHORIZATION','phase-action-authorization'),('REQUEST','fixed-action-request'),
                        ('ATTEMPT','phase-action-attempt'),('RESULT','phase-action-result'),('COMPLETION','phase-action-completion')]:
        artifact=next(a for a in sources if a.role=='Q16A_'+role)
        semantics.reader._validate(prepared.root,artifact.document,'config/schemas/stage17-'+family+'-v6.schema.json',role,pinned)
    expected=semantics._historical(prepared,prepared.validation.resolutions,c['files']['historical_journal']['path'])
    lifecycle=semantics._receipts(artifacts=sources,action_id='Q16a',trust=prepared.validation.resolutions['S17-EXT-003'].semantic_context['trust'],
        expected_predecessors=expected,extent=controller.plans.validate_plan('Q16a',plan),allow_synthetic=False)
    manifest_binding=_current_binding(analysis/'validated-suffix-manifest.json');manifest=reader.document(manifest_binding)
    if finalization is not None:same(manifest_binding,finalization['suffix_manifest'],'finalized suffix original bytes')
    fields(manifest,'schema_version status plan_sha256 request completion records method_id analysis_configuration_sha256 authenticated_custody raw_mutation family_validity_established execution_authority phase18_authority','suffix manifest')
    for key,value in dict(schema_version='software-validated-q16a-suffix/1',status='VALIDATED',plan_sha256=PLAN_SHA,
            method_id=calibration.METHOD['Q16a'],request=c['files']['REQUEST'],completion=c['files']['COMPLETION'],
            analysis_configuration_sha256=CONFIG_SHA,raw_mutation=False,family_validity_established=False,execution_authority=False,phase18_authority=False).items():
        same(manifest[key],value,'suffix manifest '+key)
    require(len(manifest['records'])==531,'all531 suffix records required')
    same(manifest['authenticated_custody']['path'],str(analysis/'authenticated-suffix-custody.json'),'actual authenticated custody path')
    custody=reader.document(manifest['authenticated_custody'])
    semantics._archive_scope(custody,prepared.request,prepared.root)
    require(len(custody['captures'])==531,'all531 authenticated custody records required')
    if finalization is not None:same(custody['scope_bindings']['ledger_head'],finalization['ledger_summary'],'original custody ledger projection')
    declared={row['file_name']:{k:row[k] for k in ('file_name','size_bytes','sha256')} for row in lifecycle['result']['artifacts']}
    phase=Path(prepared.request['evidence_root_binding']['absolute_path']);records=[]
    for i,(row,cap) in enumerate(zip(manifest['records'],custody['captures'],strict=True)):
        fields(row,'local_ordinal original_ordinal measurement_run_id validation_report_binding','suffix record')
        same([row['local_ordinal'],row['original_ordinal']],[i,i+177],'suffix original/local mapping')
        capture=plan['captures'][i]['capture'];same(row['measurement_run_id'],capture['measurement']['run_id'],'suffix run identity')
        same(row['validation_report_binding']['path'],str(analysis/'reports'/f'capture-{i}.json'),'actual report path')
        match_signed_capture(cap,declared,i)
        def bound_name(b):
            require(Path(b['file_name']).name==b['file_name'],'flat signed artifact name')
            return dict(path=str(phase/b['file_name']),size_bytes=b['size_bytes'],sha256=b['sha256'])
        projected=dict(local_ordinal=i,context_ordinal=capture['context_ordinal'],repetition_ordinal=capture['repetition_ordinal'],
            checkpoint_binding=bound_name(cap['checkpoint']),custody_binding=bound_name(cap['custody_receipt']),validation_report_binding=row['validation_report_binding'])
        validate_capture(projected,cap,plan,plan['storage']['program_scope_sha256'],reader,family_sha=PLAN_SHA)
        raw=reader.read(row['validation_report_binding'])
        records.append(dict(capture_ordinal=i,measurement_run_id=capture['measurement']['run_id'],validity='VALID',
            report_binding=dict(artifact_id='Q16A-SUFFIX-REPORT-'+str(i),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),report_utf8_bytes=raw.decode('utf-8')))
    reader.finish()
    return dict(records=records,manifest=manifest_binding,process_result=process_binding,configuration=configuration_binding,finalization=finalization_binding,
        completion=c['files']['COMPLETION'],execution_authority=False,phase18_authority=False)
