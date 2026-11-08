"""D240 bound prefix/compatibility admission; no collection or raw reanalysis.

The controller supplies authenticated EXT006 semantic_context at authoring and
execution. Signed references do not substitute for the checks below. Complete
original raw decoding is performed by the separately pinned prefix operator.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time
from types import SimpleNamespace

import check_formal_codegen as codegen
import stage17_formal_ring_continuation_v1 as contract
import stage17_formal_calibration_v1 as calibration
import stage17_formal_checkpoint_v1 as checkpoint
import stage17_formal_archive_registry_v1 as archive_registry
import stage17_output_registry_v11 as registry
from stage17_formal_archive_v1 import canonical

COMPATIBILITY_SCHEMA = 'cpu-prefetch-stage17-q16a-continuation-compatibility/1'
PREFIX_SCHEMA = 'cpu-prefetch-stage17-q16a-accepted-prefix/1'
ORIGINAL_WORKER_SHA = '2e54f9ab7752e8e0f8be02df76970cb94849c93e923cf625d38550a658963c4f'
ORIGINAL_WORKER_SIZE = 4952112
ORIGINAL_INVENTORY_SHA = '0e2cc234cf3c42f2575471e4e13ebda257c5250cd7e356bf5e995fced432778a'
ORIGINAL_CODEGEN_SHA = '43f44f296f05cf7ff15f831943a118433429ba5764cd6b8f53f8d501e02a8bae'
COLD_SOURCE = 'src/runner/stage17_formal_family.cpp'
QUALIFIED_VALIDATORS = (
    'stage17_q16a_capture_validation_v1.py', 'stage17_q16a_demand_decoder_v1.py',
    'stage17_discovery_validation_v3.py', 'stage17_formal_archive_registry_v1.py',
    'stage17_formal_archive_custody_v1.py', 'stage17_formal_archive_v1.py',
    'stage17_formal_checkpoint_v1.py')
OPERATOR_SHA = {
    'validate_prefix.py': '1791eda89e43eea28502a3201b50b4f969bb5b73eb89214d49179814422cdbc6',
    'original_analysis.py': '5ed34087443a79c81ff00135bbfd4adb2e3f516770dd034be9f998ae69b0ac99',
    'd234_supervision.py': '82571bf245012b0d7b444924803909f8d3a0ba802001d7ad9a5d9410195f9403',
    'stage17_discovery_validation_parallel_v2.py': '07a4bba1379c686a8f31e42aadeb93200a8574d55c7a1ffaea7b92606a6303f7'}
MAX_FILE_BYTES = 32 * 1024**2
MAX_TOTAL_BYTES = 256 * 1024**2
MAX_FILES = 4096
MAX_SECONDS = 120


class AdmissionError(contract.ContractError):
    pass


def require(condition, message):
    if not condition:
        raise AdmissionError('Q16a continuation admission: ' + message)


def same(actual, expected, label):
    require(canonical(actual) == canonical(expected), label + ' differs')


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names.split()), label + ' fields differ')
    return value


def _json(data):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def constant(_value):
        raise AdmissionError('nonfinite JSON')
    value = json.loads(data, object_pairs_hook=pairs, parse_constant=constant)
    contract._no_floats(value)
    return value


def _stamp(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


class BoundReader:
    """Finite exact original bytes from regular nonsymlink paths, with race checks."""
    def __init__(self):
        self.deadline = time.monotonic() + MAX_SECONDS
        self.total = 0
        self.observed = {}

    def read(self, binding):
        fields(binding, 'path size_bytes sha256', 'file binding')
        p = Path(str(contract._path(binding['path'])))
        size, digest = binding['size_bytes'], binding['sha256']
        require(type(size) is int and 0 <= size <= MAX_FILE_BYTES, 'file bound')
        require(type(digest) is str and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'file digest')
        require(time.monotonic() < self.deadline and len(self.observed) < MAX_FILES, 'proof deadline/file bound')
        self.total += size
        require(self.total <= MAX_TOTAL_BYTES, 'aggregate metadata bound')
        require(p.resolve(strict=True) == p, 'symlink in bound path')
        fd = os.open(p, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            before = os.fstat(fd)
            require(stat.S_ISREG(before.st_mode) and before.st_size == size, 'regular file size')
            data = bytearray()
            while len(data) < size:
                require(time.monotonic() < self.deadline, 'proof read deadline')
                block = os.read(fd, min(1024**2, size - len(data)))
                require(bool(block), 'truncated bound file')
                data.extend(block)
            require(not os.read(fd, 1) and _stamp(before) == _stamp(os.fstat(fd)) == _stamp(p.lstat()), 'file changed during read')
        finally:
            os.close(fd)
        require(hashlib.sha256(data).hexdigest() == digest, 'file SHA256 mismatch')
        prior = self.observed.setdefault(str(p), _stamp(before))
        require(prior == _stamp(before), 'bound file changed between references')
        return bytes(data)

    def document(self, binding):
        return _json(self.read(binding))

    def finish(self):
        require(time.monotonic() < self.deadline, 'proof deadline expired')
        for name, stamp in self.observed.items():
            require(_stamp(Path(name).lstat()) == stamp and Path(name).resolve(strict=True) == Path(name),
                    'proof changed before admission completed')


def _member(root, name):
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and '..' not in relative.parts and str(relative) == name, 'bundle member path')
    return str(Path(root) / name)


def _inventory(document):
    rows = document['files']
    require(type(rows) is list and len(rows) <= MAX_FILES, 'bundle inventory bound')
    result = {}
    for row in rows:
        fields(row, 'path size_bytes sha256', 'inventory row')
        require(row['path'] not in result, 'duplicate bundle member')
        result[row['path']] = row
    return result


def _source_names(index):
    # Exact qualified bundled include/src closure, not an arbitrary caller list.
    return {name for name in index if name.startswith(('include/', 'src/'))} | set(codegen.SOURCE_PATHS) | {'tools/check_formal_codegen.py'}


def _compatibility(document, plan, context, reader):
    fields(document, 'schema_version original continuation measured_sources cold_source_changes monitor_path_replacements execution_authority', 'compatibility')
    same(document['schema_version'], COMPATIBILITY_SCHEMA, 'compatibility version')
    same(document['execution_authority'], False, 'compatibility authority')
    same(document['monitor_path_replacements'], plan['continuation']['monitor_path_replacements'], 'declared monitor relocation')
    sides = []
    for side in ('original', 'continuation'):
        d = fields(document[side], 'source_revision bundle_root worker formal_codegen bundle_inventory', side + ' release')
        root = str(contract._path(d['bundle_root']))
        require(Path(root).resolve(strict=True) == Path(root), 'bundle root symlink')
        same(d['source_revision'], contract.PARENT_SOURCE if side == 'original' else plan['source_revision'], side + ' source')
        for key, member in (('worker', 'release/bin/cpu_prefetch_runner'),
                            ('formal_codegen', 'build-provenance/formal_codegen_report.json'),
                            ('bundle_inventory', 'BUNDLE_INVENTORY.json')):
            same(d[key]['path'], _member(root, member), side + ' ' + key + ' locator')
        if side == 'original':
            same(d['worker']['sha256'], ORIGINAL_WORKER_SHA, 'original worker')
            same(d['worker']['size_bytes'], ORIGINAL_WORKER_SIZE, 'original worker size')
            same(d['formal_codegen']['sha256'], ORIGINAL_CODEGEN_SHA, 'original strict codegen')
            same(d['bundle_inventory']['sha256'], ORIGINAL_INVENTORY_SHA, 'original qualified inventory')
        else:
            same(root, context['archive_bundle_root'], 'qualified bundle root')
            same(d['source_revision'], context['source_revision'], 'qualified new source')
            same(d['bundle_inventory']['sha256'], context['inventory_sha256'], 'authenticated qualified inventory')
            same(d['worker'], dict(path=context['release_artifact_path'],size_bytes=context['release_artifact_size_bytes'],
                                  sha256=context['release_artifact_sha256']), 'qualified new worker')
        reader.read(d['worker'])
        index = _inventory(reader.document(d['bundle_inventory']))
        report = reader.document(d['formal_codegen'])
        for key, member in (('worker','release/bin/cpu_prefetch_runner'),('formal_codegen','build-provenance/formal_codegen_report.json')):
            same({k:d[key][k] for k in ('size_bytes','sha256')},{k:index[member][k] for k in ('size_bytes','sha256')}, 'inventory ' + key)
        sides.append((root, index, report, d))
    old, new = sides
    names = _source_names(old[1])
    same(sorted(names), sorted(_source_names(new[1])), 'complete bundled measurement dependency closure')
    require(COLD_SOURCE in names, 'cold parser absent from closure')
    rows = document['measured_sources'] + document['cold_source_changes']
    require(type(document['measured_sources']) is list and type(document['cold_source_changes']) is list,
            'source comparison arrays required')
    require(len(rows) == len(names), 'source comparison coverage')
    require([r['relative_path'] for r in document['cold_source_changes']] == [COLD_SOURCE], 'only declared cold parser exception')
    seen = set()
    for row in rows:
        fields(row, 'relative_path original continuation', 'source comparison')
        name = row['relative_path'];require(name in names and name not in seen, 'source omitted/duplicated/foreign');seen.add(name)
        for key, data in (('original',old),('continuation',new)):
            expected = dict(data[1][name],path=_member(data[0],name))
            same(row[key], expected, 'qualified source ' + name)
            reader.read(row[key])
        if name != COLD_SOURCE:
            same(row['original']['sha256'], row['continuation']['sha256'], 'unchanged measurement dependency ' + name)
    for root, _, report, d in sides:
        # Existing strict both-disassembler/42-worker/negative-mutant validator.
        codegen.validate_report_bindings(report,binary=Path(d['worker']['path']),source_root=Path(root))
    return old[0], old[1]


def _bound_name(binding):
    return dict(file_name=Path(binding['path']).name,size_bytes=binding['size_bytes'],sha256=binding['sha256'])


def _ledger_record(reader, root, binding):
    name=binding['file_name']
    require(type(name) is str and Path(name).name == name and name.endswith('.json'), 'ledger record basename')
    return reader.document(dict(path=str(root/name),size_bytes=binding['size_bytes'],sha256=binding['sha256']))


def _checkpoint_identity(document, capture, logical):
    sources = tuple(SimpleNamespace(expected=SimpleNamespace(**r)) for r in logical)
    checkpoint.validate_checkpoint(document, action='Q16a',plan_sha256=contract.PARENT_SHA256,capture=capture,sources=sources)


def _capture_record(row, authenticated, parent, scope_sha, reader):
    fields(row, 'original_ordinal context_ordinal repetition_ordinal checkpoint_binding custody_binding validation_report_binding','prefix row')
    ordinal = row['original_ordinal'];item=parent['captures'][ordinal];capture=item['capture']
    same([row['context_ordinal'],row['repetition_ordinal']],list(divmod(ordinal,59)),'prefix context/repetition')
    cp = reader.document(row['checkpoint_binding']);receipt=reader.document(row['custody_binding']);report=reader.document(row['validation_report_binding'])
    same(_bound_name(row['checkpoint_binding'])['file_name'],f'formal-capture-{ordinal}-final-checkpoint.json','checkpoint filename')
    same(_bound_name(row['custody_binding'])['file_name'],f'formal-capture-{ordinal}-archive-custody.json','custody filename')
    for key,value in dict(schema_version='cpu-prefetch-stage17-formal-archive-custody/1',capture_ordinal=ordinal,
            plan_sha256=contract.PARENT_SHA256,program_scope_sha256=scope_sha,checkpoint=_bound_name(row['checkpoint_binding']),
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
        same(artifact['artifact_id'],contract.PARENT_SHA256+':'+name,'original artifact identity')
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
    _checkpoint_identity(cp,capture,logical)
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
    same(registration['payload'],dict(family_id=contract.PARENT_SHA256,
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


def _failure_boundary(prefix, parent, reader):
    failed=prefix['failed_boundary']
    same(failed['original_ordinal'],177,'failed original ordinal')
    for key in ('zero_raw_observations','both_phases_unreleased','physical_custody_verified','inverse_readback_performed'):
        same(failed[key],True,'failed boundary '+key)
    cp=reader.document(failed['checkpoint']);receipt=reader.document(failed['custody_receipt'])
    same(cp['native_complete'],False,'original failed native outcome')
    logical=[r['logical'] for r in receipt['artifacts']]
    _checkpoint_identity(cp,parent['captures'][177]['capture'],logical)
    same(receipt['checkpoint'],_bound_name(failed['checkpoint']),'failed checkpoint binding')
    same(receipt['plan_sha256'],contract.PARENT_SHA256,'failed original plan')
    same(receipt['capture_ordinal'],177,'failed receipt ordinal')
    same(receipt['program_scope_sha256'],parent['storage']['program_scope_sha256'],'failed shared scope')
    same(receipt['scientific_validity'],'NOT_ASSESSED','failed science disposition')
    same(receipt['status'],'ARCHIVED_AND_RELEASED','failed evidence durable custody')
    same(receipt['execution_authority'],False,'failed custody authority')
    require(len(logical)==9,'failed nine artifacts retained')
    for artifact in receipt['artifacts']:
        same(artifact['failure_receipt'],None,'failed evidence original bytes')
        same(artifact['logical'],artifact['expected_logical'],'failed evidence canonical identity')
    for row in logical:
        if row['file_name'].endswith('.bin'):
            same([row['size_bytes'],row['sha256']],[0,hashlib.sha256(b'').hexdigest()],'failed raw stream must be empty')
    phases=cp['native_result_after_cleanup']['session']['phases'];require(len(phases)==2,'two failed phases')
    for phase in phases:
        same(phase['released'],False,'zero-observation phase unreleased')
        for key in ('observed_origin','origin_sample','origin_status','window','drain_checkpoint'):
            same(phase[key],None,'unreleased phase '+key)
        for key in ('before_observed','during_observed','after_observed','validated'):
            same(phase[key],False,'unreleased phase '+key)
        for role,keys in (('producer',('attempted','accepted','full')),('consumer',('polls','consumed_including_drain','empty'))):
            for key in keys:same(phase[role][key],0,'failed phase observations')


def _prefix_sources(prefix, old_root, old_index, reader):
    rows=prefix['validator_source_files'];require(type(rows)is list and len(rows)==11,'exact prefix validator source closure')
    expected=set(QUALIFIED_VALIDATORS)|set(OPERATOR_SHA);seen=set()
    for row in rows:
        name=Path(row['path']).name;require(name in expected and name not in seen,'foreign/duplicate prefix validator');seen.add(name)
        reader.read(row)
        if name in OPERATOR_SHA:same(row['sha256'],OPERATOR_SHA[name],'reviewed prefix operator')
        else:same({k:row[k] for k in ('size_bytes','sha256')},{k:old_index['tools/'+name][k] for k in ('size_bytes','sha256')},'original qualified validator')
    for key,name in (('analysis_operator','validate_prefix.py'),('original_analysis_operator','original_analysis.py')):
        same(prefix[key],next(r for r in rows if Path(r['path']).name==name),'prefix operator binding')
    policy=prefix['qualified_policy'];member='config/stage17/stage17-operational-evidence-admission-policy-v58.json'
    same({k:policy[k] for k in ('size_bytes','sha256')},{k:old_index[member][k] for k in ('size_bytes','sha256')},'original qualified policy')
    reader.read(policy)


def _authority(prefix, parent, failure, reader):
    refs=fields(prefix['original_authority'],'AUTHORIZATION SIGNATURE REQUEST ATTEMPT historical_journal','original authority')
    docs={k:reader.document(v) for k,v in refs.items() if k!='SIGNATURE'};reader.read(refs['SIGNATURE'])
    same(refs['AUTHORIZATION']['sha256'],failure['authorization_sha256'],'consumed authority hash')
    same(refs['REQUEST']['sha256'],failure['request_sha256'],'original request hash')
    request,attempt=docs['REQUEST'],docs['ATTEMPT']
    same(request['schema_version'],'cpu-prefetch-stage17-fixed-action-request/6','original request version')
    same(request['action_id'],'Q16a','original action')
    same(request['action_inputs']['plan'],parent,'request original plan')
    same(request['runtime_binding']['sha256'],ORIGINAL_WORKER_SHA,'original request worker')
    for field in ('request_sha256','authorization_sha256','attempt_id'):
        same(attempt[field],failure[field],'failure/attempt '+field)
    same(attempt['runtime_sha256'],ORIGINAL_WORKER_SHA,'original attempt worker')
    same(attempt['one_attempt'],True,'original one attempt');same(attempt['retries'],0,'original no retry')
    same(attempt['marker_durable'],True,'original durable attempt marker')
    same(attempt['evidence_root_binding'],request['evidence_root_binding'],'original signed root')
    same(attempt['authorization_id'],request['authorization_id'],'original authorization identity')
    for doc,kind in ((attempt,'attempt'),(failure,'failure')):
        same(doc['schema_version'],'cpu-prefetch-stage17-phase-action-'+kind+'/6','original lifecycle version')
        same(doc['phase18_authority'],False,'original lifecycle no Stage18 authority')
        same(doc['action_id'],'Q16a','original lifecycle action')
        same(doc['attempt_id'],request['attempt_id'],'original lifecycle attempt')
    same(failure['runtime_sha256'],ORIGINAL_WORKER_SHA,'failed worker')
    for flag in ('restoration_verified','leader_reaped','process_group_gone'):same(failure[flag],True,'original failure '+flag)
    same(failure['quarantine_operation'],dict(performed=False,record_sha256=None),'original restored unquarantined')
    pre=request['action_inputs']['hardware_control']['prestate'];rows=failure['recovery_readback']
    same(sorted(r['cpu'] for r in rows),sorted(r['cpu'] for r in pre),'restored all original CPUs')
    expected={r['cpu']:r['complete_value_hex'] for r in pre}
    for row in rows:
        same(row['matches'],True,'original restoration observation');same(row['observed_hex'],expected[row['cpu']],'restored original register')
    root=Path(request['evidence_root_binding']['absolute_path'])
    require(root.name==contract.PARENT_SHA256 and root.parent.name=='working','original family root')
    for row in prefix['records']:
        for key in ('checkpoint_binding','custody_binding'):same(str(Path(row[key]['path']).parent),str(root),'original capture root')
    return root


def _prefix(prefix, parent, failure, plan, reader, old_root, old_index):
    required='schema_version status method_id parent_plan failed_family_receipt original_plan_sha256 original_failure_sha256 original_source_revision worker_sha256 original_authority program_scope_sha256 program_root_binding ledger_head contexts required_count records validator_source_files failed_boundary retained_failure_restoration_verified analysis_limits authenticated_custody analysis_operator original_analysis_operator qualified_policy family_validity_established execution_authority phase18_authority'
    fields(prefix,required,'accepted prefix')
    fixed=dict(schema_version=PREFIX_SCHEMA,status='VALIDATED',method_id=contract.ring.METHOD,
        parent_plan=plan['continuation']['parent_plan'],failed_family_receipt=plan['continuation']['failed_family_receipt'],
        original_plan_sha256=contract.PARENT_SHA256,original_failure_sha256=contract.FAILURE_SHA256,
        original_source_revision=contract.PARENT_SOURCE,worker_sha256=ORIGINAL_WORKER_SHA,
        program_scope_sha256=parent['storage']['program_scope_sha256'],contexts=[0,1,2],required_count=177,
        retained_failure_restoration_verified=True,family_validity_established=False,execution_authority=False,phase18_authority=False)
    for key,value in fixed.items():same(prefix[key],value,'prefix '+key)
    rows=prefix['records'];require(type(rows)is list and len(rows)==177,'all177 prefix reports required')
    same([r['original_ordinal'] for r in rows],list(range(177)),'complete ordered original prefix')
    _prefix_sources(prefix,old_root,old_index,reader)
    root=_authority(prefix,parent,failure,reader)
    binding=prefix['program_root_binding'];same(binding['absolute_path'],str(root.parent.parent),'program root identity')
    st=Path(binding['absolute_path']).stat(follow_symlinks=False)
    same([st.st_dev,st.st_ino,st.st_uid,f'{stat.S_IMODE(st.st_mode):04o}'],[binding['device'],binding['inode'],binding['owner_uid'],binding['mode']],'actual original program identity')
    inventory=reader.document(prefix['authenticated_custody']);same(inventory['execution_authority'],False,'prefix custody authority')
    same(inventory['ledger_head'],prefix['ledger_head'],'authenticated ledger head')
    same(inventory['failed_boundary'],prefix['failed_boundary'],'authenticated failed boundary')
    require(len(inventory['captures'])==177,'authenticated prefix coverage')
    ledger=prefix['ledger_head'];head=_ledger_record(reader,root.parent.parent/'ledger',ledger)
    same(head['schema_version'],'cpu-prefetch-stage17-formal-representation-ledger/1','prefix ledger version')
    same(head['scope_sha256'],prefix['program_scope_sha256'],'prefix ledger scope')
    same(ledger['file_name'],f'{head["sequence"]:016d}.json','prefix ledger sequence')
    scope_path=root.parent.parent/'scope.json'
    scope=reader.document(dict(path=str(scope_path),size_bytes=scope_path.stat().st_size,sha256=prefix['program_scope_sha256']))
    same(scope['program_id'],parent['storage']['program_id'],'original shared program')
    same(scope['shared_program_quota_bytes'],parent['storage']['archive_quota_bytes'],'original shared quota')
    limits=reader.document(prefix['analysis_limits']);same(limits['source_plan_sha256'],contract.PARENT_SHA256,'offline analysis original plan');same(limits['execution_authority'],False,'offline analysis authority')
    _failure_boundary(prefix,parent,reader)
    summaries=[]
    for row,authenticated in zip(rows,inventory['captures'],strict=True):
        summaries.append(_capture_record(row,authenticated,parent,prefix['program_scope_sha256'],reader))
    return summaries


@dataclass(frozen=True)
class AdmissionSummary:
    prefix_captures: int
    continuation_captures: int
    original_plan_sha256: str
    original_failure_sha256: str
    prefix_manifest_sha256: str
    compatibility_manifest_sha256: str
    execution_authority: bool = False


def validate(plan, qualification_context) -> AdmissionSummary:
    """Current context must originate from authenticated EXT006 verification."""
    reader=BoundReader()
    try:
        continuation=plan['continuation']
        parent_bytes=reader.read(continuation['parent_plan'])
        contract.validate_parent(plan,parent_bytes);parent=_json(parent_bytes)
        failure=reader.document(continuation['failed_family_receipt'])
        compat=reader.document(continuation['compatibility_manifest'])
        old_root,old_index=_compatibility(compat,plan,qualification_context,reader)
        prefix=reader.document(continuation['accepted_prefix_manifest'])
        _prefix(prefix,parent,failure,plan,reader,old_root,old_index)
        reader.finish()
        return AdmissionSummary(177,531,contract.PARENT_SHA256,contract.FAILURE_SHA256,
            continuation['accepted_prefix_manifest']['sha256'],continuation['compatibility_manifest']['sha256'])
    except AdmissionError:
        raise
    except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError,contract.ContractError,
            calibration.CalibrationError,codegen.AuditError) as error:
        raise AdmissionError('Q16a continuation proof rejected: '+str(error)) from error
