"""Ignored offline Q16a operator. Full signed custody, then bounded raw science.

No capture, retry, signing, hardware access, archive mutation or EXT007 admission.
All operational inputs come from an explicitly hash-bound configuration.
"""
from __future__ import annotations
import argparse, contextlib, dataclasses, gc, hashlib, importlib, io, json, os
from pathlib import Path
import resource, stat, sys, time, types

GIB=1024**3
SCRATCH=256*GIB
RESERVE=16*GIB
SUPERVISION_SHA='82571bf245012b0d7b444924803909f8d3a0ba802001d7ad9a5d9410195f9403'
ROLES=('AUTHORIZATION','SIGNATURE','REQUEST','ATTEMPT','RESULT','COMPLETION')

def require(ok,message):
    if not ok:raise ValueError(message)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def unique(pairs):
    result={}
    for k,v in pairs:
        require(k not in result,'duplicate JSON key');result[k]=v
    return result

def parse(raw):
    return json.loads(raw,object_pairs_hook=unique,parse_float=lambda s:(_ for _ in ()).throw(ValueError('float forbidden')),
                      parse_constant=lambda s:(_ for _ in ()).throw(ValueError('nonfinite forbidden')))
def uint(x,label):
    require(type(x) is int and 0<x<2**64,label+' must be positive uint64');return x

def safe(path):
    p=Path(path)
    require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)),'absolute nonsymlink path required')
    return p

def read(binding,maximum=128*1024**2):
    require(set(binding)=={'path','size_bytes','sha256'},'file binding fields')
    p=safe(binding['path']);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before=os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size==binding['size_bytes']<=maximum,'bounded regular input required')
        raw=f.read(maximum+1);after=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==before.st_size and sha(raw)==binding['sha256'],'input bytes/identity differ')
    return raw

def binding(path):
    p=Path(path);raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=sha(raw))

def save(path,value,limit):
    raw=canonical(value);require(len(raw)<=limit,'output metadata bound exceeded')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return dict(path=str(path),size_bytes=len(raw),sha256=sha(raw))

def scratch_proof(canonical_bytes,worker_count,metadata_bytes,filesystem_bytes):
    for name,value in locals().copy().items():uint(value,name)
    require(worker_count in (1,4),'only one or four prospective workers')
    # Qualified formal_phase emits no drain_rows. Its consumer drain is wholly
    # in the eight primary/demand streams. The loader below rejects that key
    # BEFORE the shared parser could create any hidden TemporaryFile.
    total=canonical_bytes*worker_count+metadata_bytes+filesystem_bytes
    require(total<=SCRATCH,'aggregate scratch proof exceeds 256 GiB')
    return dict(worker_count=worker_count,canonical_bytes_per_capture=canonical_bytes,
                parser_drain_spool_bytes=0,retained_metadata_bytes=metadata_bytes,
                filesystem_overhead_bytes=filesystem_bytes,total_bytes=total,scratch_ceiling_bytes=SCRATCH)

def config(path,digest):
    p=safe(path);raw=read(dict(path=str(p),size_bytes=p.stat().st_size,sha256=digest),65536);c=parse(raw)
    require(c['schema_version']=='software-offline-q16a-analysis/1','analysis config version')
    require(c['operator_sha256']==sha(Path(__file__).read_bytes()),'operator source differs')
    require(c['supervision_sha256']==SUPERVISION_SHA==sha(Path(__file__).with_name('d234_supervision.py').read_bytes()),'D234 supervisor source differs')
    require(set(c['files'])==set(ROLES)|{'policy','historical_journal','geometry'},'exact original input set')
    require(c['execution_authority'] is False,'offline only')
    for k in ('repository_root','evidence_root','journal_directory','analysis_root'):safe(c[k])
    r=c['resources']
    for k in ('supervisor_as_bytes','coordinator_as_bytes','capture_as_bytes','total_memory_bytes','memory_reserve_bytes','timeout_seconds','metadata_bytes','filesystem_overhead_bytes','canonical_capture_bytes','worker_count'):
        uint(r[k],k)
    require(r['coordinator_as_bytes']==2*GIB and r['capture_as_bytes']==8*GIB,'explicit reviewed coordinator2/science8GiB limits required')
    require(r['supervisor_as_bytes']<=2*GIB,'supervisor exceeds2GiB')
    require(r['filesystem_overhead_bytes']>=4096*65536,'filesystem/report slack below256MiB')
    require(r['metadata_bytes']<=2*GIB,'bounded metadata allowance exceeds2GiB')
    scratch_proof(r['canonical_capture_bytes'],r['worker_count'],r['metadata_bytes'],r['filesystem_overhead_bytes'])
    concurrent=max(r['capture_as_bytes']*r['worker_count'],r['runtime']['broker_address_space_bytes']+r['runtime']['codec_address_space_bytes'])
    require(r['total_memory_bytes']>=r['supervisor_as_bytes']+r['coordinator_as_bytes']+concurrent,'aggregate memory omits simultaneous processes')
    return c

def bounded_as(value,hard):resource.setrlimit(resource.RLIMIT_AS,(value,hard))

def modules(c):
    root=safe(c['repository_root']);policy=parse(read(c['files']['policy']))
    require(Path(c['files']['policy']['path'])==root/'config/stage17/stage17-operational-evidence-admission-policy-v58.json','policy path')
    # Verify original source closure BEFORE importing it. Journal admission then
    # verifies policy semantics and qualified release provenance independently.
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
           'stage17_q16a_capture_validation_v1','stage17_formal_calibration_v2','stage17_discovery_validation_parallel_v2')
    offline='tools/stage17_discovery_validation_parallel_v2.py'
    if offline not in pinned:
        require(read(c['parallel_adapter'])==(root/offline).read_bytes(),'offline pool bytes differ')
    loaded={name:importlib.import_module(name) for name in names}
    for name,m in loaded.items():
        require(Path(m.__file__).resolve()==root/'tools'/f'{name}.py','import escaped bound repository')
        # Parallel2 is offline D234; bind it separately through config if absent
        # from capture-release runtime_closure, never pretend it was qualified.
        relative='tools/'+name+'.py'
        if relative not in pinned:
            require(name=='stage17_discovery_validation_parallel_v2','analysis dependency absent from policy')
            raw=read(c['parallel_adapter']);require(raw==(root/relative).read_bytes(),'offline pool bytes differ')
    return types.SimpleNamespace(**{name.replace('stage17_',''):m for name,m in loaded.items()}),pinned

def limits(c,m,plan,profile,deadline):
    r=c['resources'];a=m.formal_archive_v1;reg=m.output_registry_v12
    custody=m.formal_archive_custody_v1.CustodyLimits(**r['custody'],deadline_ns=deadline)
    decoder=a.DecodeLimits(**r['decoder'],deadline_ns=deadline)
    runtime=m.formal_archive_runtime_v1.RetainedReadbackLimits(**r['runtime'],deadline_ns=deadline,max_children=708*9)
    raw=a.canonical(dict(schema_version='cpu-prefetch-stage17-archive-analysis-limits/1',plan_sha256=reg.plan_sha256(plan),
        program_scope_sha256=plan['storage']['program_scope_sha256'],implementation_profile_sha256=profile.decoder.implementation_profile_sha256,
        parent_address_space_bytes=r['coordinator_as_bytes'],total_memory_bytes=r['total_memory_bytes'],
        custody=dataclasses.asdict(custody),runtime=dataclasses.asdict(runtime),decoder=dataclasses.asdict(decoder),execution_authority=False,phase18_authority=False))
    return reg.AnalysisLimits(raw,a.PhysicalBinding(len(raw),sha(raw)),r['coordinator_as_bytes'],r['total_memory_bytes'],custody,runtime,decoder)

@contextlib.contextmanager
def formal_control(common,root,logical):
    class FormalJson(common.JsonReader):
        def value(self,key='',depth=0):
            require(key!='drain_rows','unexpected discovery drain JSON in formal control; no scratch bypass')
            return super().value(key,depth)
    with contextlib.ExitStack() as stack:
        raw=stack.enter_context(common.opened(root,logical));text=io.TextIOWrapper(raw,encoding='utf-8',errors='strict')
        try:yield FormalJson(text,stack).document()
        finally:text.detach()

def validate_spooled(m,job):
    a=m.formal_archive_v1;custody=m.formal_archive_custody_v1;validator=m.q16a_capture_validation_v1
    r=job['resources'];item=job['item'];verified=job['verified'];ordinal=item['capture']['ordinal']
    profile=dict(job['decoder_profile'])
    for key in ('zstd_library_path','decoder_executable_path'):profile[key]=Path(profile[key])
    profile=a.DecoderProfile(**profile);decode=a.DecodeLimits(**job['decoder_limits'])
    artifacts=tuple(custody.SpoolArtifact(row['logical']['file_name'],Path(job['program_root'])/'archives'/row['archive_name'],
        row['header'],a.RoleProfile(**row['role']),a.PhysicalBinding(**row['physical'])) for row in verified['artifacts'])
    require(len(artifacts)==9 and sum(row['logical']['size_bytes'] for row in verified['artifacts'])<=r['canonical_capture_bytes'],'nine artifacts/canonical bound')
    control=verified['artifacts'][-1]['logical'];require(control['file_name']==f'q16a-c{ordinal}-control.json','control role/order')
    # Dedicated single-thread pool process; codec soft limit is enforced only
    # during decode. The immutable hard limit stays the prospective science AS.
    gc.collect();resource.setrlimit(resource.RLIMIT_AS,(r['runtime']['codec_address_space_bytes'],r['capture_as_bytes']))
    with custody.capture_spool(Path(job['scratch']),capture_id=f'capture-{ordinal}',canonical_bytes_bound=r['canonical_capture_bytes'],
            deadline_ns=decode.deadline_ns,artifacts=artifacts,profile=profile,limits=decode) as root:
        resource.setrlimit(resource.RLIMIT_AS,(r['capture_as_bytes'],r['capture_as_bytes']))
        with formal_control(validator.common,root,control) as document:
            report=validator.validate_capture(root,document,verified['native_result_after_cleanup'],item['capture'],
                item['resources'],item['monitoring'],job['hardware_control'])
        output=save(Path(job['reports'])/f'capture-{ordinal}.json',report,r['metadata_bytes']//(708*3+16))
    return ordinal,output,None

_POOL_MODULES=None

def capture_group(connection,jobs,memory_bytes):
    try:
        resource.setrlimit(resource.RLIMIT_AS,(memory_bytes,memory_bytes))
        for job,_,_ in jobs:
            connection.send(('capture',validate_spooled(_POOL_MODULES,job)))
        connection.send(('done',None))
    except BaseException as error:
        connection.send(('error',f'{type(error).__name__}: {str(error)[:4096]}'))
    finally:connection.close()

def ordered_pool(m,jobs,c,deadline):
    global _POOL_MODULES
    _POOL_MODULES=m
    base=m.discovery_validation_parallel_v2
    private=types.FunctionType(base._parallel_captures.__code__,{**base._parallel_captures.__globals__,'_capture_group':capture_group})
    packed=[(j,types.SimpleNamespace(ordinal=j['item']['capture']['ordinal']),{'artifacts':[{'size_bytes':j['verified']['artifacts'][-1]['logical']['size_bytes']}]}) for j in jobs]
    remaining=(deadline-time.monotonic_ns())/1e9;require(remaining>0,'science deadline expired')
    results,_=private(packed,c['resources']['worker_count'],c['resources']['capture_as_bytes'],remaining,
        lambda ordinal,done,total:print(json.dumps(dict(capture_ordinal=ordinal,completed=done,total=total)),flush=True))
    return results

def geometry_inputs(c,m,plan,prepared):
    geometry=parse(read(c['files']['geometry']))
    require(set(geometry)=={'records','sources','native_provenance','platform_manifest'} and len(geometry['records'])==6,'six bound native geometry records and provenance required')
    platform_raw=read(geometry['platform_manifest']);platform=parse(platform_raw)
    expected_platform=prepared.validation.resolutions['S17-EXT-004'].semantic_context['pilot_platform_measurements']['platform_manifest_sha256']
    require(sha(platform_raw)==expected_platform,'geometry platform is not actual admitted EXT004 platform')
    line=uint(platform['cpu']['cache_line_bytes'],'admitted cache line')
    provenance=parse(read(geometry['native_provenance']))
    require(provenance['schema_version']=='software-native-ring-slot-geometry-provenance/1' and provenance['source_revision']==plan['source_revision'],'native geometry provenance/source differs')
    require(provenance['qualified_worker']['sha256']==prepared.request['runtime_binding']['sha256'] and provenance['qualified_worker']['size_bytes']==prepared.request['runtime_binding']['size_bytes'],'geometry libraries are not bound to this qualified worker')
    source_index={b['artifact_id']:b['binding'] for b in geometry['sources']}
    require(len(source_index)==len(geometry['sources']),'geometry source aliases')
    for row in geometry['records']:
        b=row['source_binding'];raw=read(source_index[b['artifact_id']]);require(len(raw)==b['size_bytes'] and sha(raw)==b['sha256'],'native geometry source binding')
        require(provenance['output']['sha256']==sha(raw) and provenance['output']['size_bytes']==len(raw),'native output/provenance bytes differ')
        native=parse(raw)
        require(native['schema_version']=='software-native-ring-slot-geometry/1' and native['api']=='RingSpscQueue::storage_requirements' and native['source_revision']==plan['source_revision'] and native['source_dirty'] is False and native['hardware_observation'] is False,'actual native geometry source differs')
        require(len(native['records'])==6,'native six contexts required')
        observed=native['records'][row['context_ordinal']]
        require(all(row[k]==observed[k] for k in ('context_ordinal','capacity','cache_line_bytes','slot_storage_bytes')) and row['cache_line_bytes']==line,'geometry row differs from native slot output/admitted cache line')
    # Native slot bytes are read directly from actual API output, independently
    # of capacity; the hardware cache-line value comes from admitted EXT004.
    m.formal_calibration_v2.previous._geometry(geometry['records'],plan)
    return geometry

def coordinate(c,deadline):
    root=Path(c['analysis_root']);r=c['resources'];m,pinned=modules(c);s=m.operational_semantics_v17
    artifacts=[]
    for role in ROLES:
        b=c['files'][role];raw=read(b)
        artifacts.append(s.reader.Artifact('Q16A_'+role,Path(b['path']),raw,len(raw),sha(raw),None if role=='SIGNATURE' else parse(raw),dict(artifact_id=role)))
    byrole={x.role:x for x in artifacts};request=byrole['Q16A_REQUEST'].document;plan=request['action_inputs']['plan']
    require(len(plan['captures'])==708 and [i['capture']['ordinal'] for i in plan['captures']]==list(range(708)),'all708 prospective captures required')
    journal=read(c['files']['historical_journal'])
    prepared=m.phase_controller_v26.prepare_retention(repository_root=Path(c['repository_root']),operational_evidence_root=Path(c['evidence_root']),
        journal=Path(c['files']['historical_journal']['path']),journal_directory=Path(c['journal_directory']),
        authorization_path=Path(c['files']['AUTHORIZATION']['path']),signature_path=Path(c['files']['SIGNATURE']['path']),synthetic_test_only=False)
    require(prepared.request_bytes==byrole['Q16A_REQUEST'].payload,'prepared request differs')
    geometry=geometry_inputs(c,m,plan,prepared)
    require(r['canonical_capture_bytes']<=plan['storage']['analysis_capture_workspace_bytes'],'spool bound exceeds signed storage ceiling')
    require(r['runtime']['codec_address_space_bytes']==2*GIB,'existing decoder requires explicit2GiB limit')
    analysis=limits(c,m,plan,prepared.archive_runtime_profile,deadline)
    save(root/'original-analysis-limits.json',parse(analysis.original_bytes),65536)
    verified=s.verify_signed_formal_family(repository_root=Path(c['repository_root']),evidence_root=Path(c['evidence_root']),
        historical_journal=Path(c['files']['historical_journal']['path']),journal_directory=Path(c['journal_directory']),artifacts=artifacts,
        action_id='Q16a',admitted_resolutions=prepared.validation.resolutions,allow_synthetic=False,pinned_repository_bytes=pinned,analysis_limits=analysis)
    require(sha(journal)==verified['historical_journal_sha256'],'historical journal changed')
    custody=verified['archive_report'];require(custody['inverse_readback_performed'] is True and len(custody['captures'])==708,'full inverse custody required')
    save(root/'signed-family-custody.json',verified,r['metadata_bytes']//4)
    (root/'reports').mkdir(mode=0o700)
    profile=m.formal_archive_runtime_v1._jsonable(dataclasses.asdict(prepared.archive_runtime_profile.decoder))
    jobs=[dict(item=item,verified=cap,resources=r,decoder_profile=profile,decoder_limits=dataclasses.asdict(analysis.decoder),
        program_root=custody['scope_bindings']['program_root_binding']['absolute_path'],scratch=str(root/'scratch'),reports=str(root/'reports'),
        hardware_control=request['action_inputs']['hardware_control']) for item,cap in zip(plan['captures'],custody['captures'],strict=True)]
    for i,j in enumerate(jobs):
        require(j['verified']['capture_ordinal']==i,'custody capture order')
        require(sum(a['logical']['size_bytes'] for a in j['verified']['artifacts'])<=r['canonical_capture_bytes'],'actual canonical capture exceeds resource proof')
    reports=ordered_pool(m,jobs,c,deadline)
    require(len(reports)==708,'all708 scientific reports required')
    records=[]
    for ordinal,b in enumerate(reports):
        raw=read(b,r['metadata_bytes']//(708*3+16));records.append(dict(capture_ordinal=ordinal,
            measurement_run_id=plan['captures'][ordinal]['capture']['measurement']['run_id'],validity='VALID',
            report_binding=dict(artifact_id='Q16A-CAPTURE-'+str(ordinal),size_bytes=len(raw),sha256=sha(raw)),report_utf8_bytes=raw.decode('utf-8')))
    result=m.formal_calibration_v2.evaluate('Q16a',plan,records,geometry['records'])
    save(root/'calibration-validation.json',result,r['metadata_bytes']//4)
    save(root/'analysis-complete.json',dict(status='ALL_708_ANALYZED',calibration_status=result['status'],
        report=binding(root/'calibration-validation.json'),source_plan_sha256=m.output_registry_v12.plan_sha256(plan),
        execution_authority=False,phase18_authority=False,ext007_admitted=False),65536)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True,type=Path);p.add_argument('--config-sha256',required=True)
    p.add_argument('--run',action='store_true');p.add_argument('--coordinate-deadline-ns',type=int,help=argparse.SUPPRESS);args=p.parse_args()
    c=config(args.config,args.config_sha256);r=c['resources'];root=Path(c['analysis_root'])
    require(os.getuid()==os.geteuid()==1000,'UID1000 offline operator required')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==c['boot_id'],'boot differs')
    actual=Path('/proc/self/exe').resolve();expected=read(c['python'],128*1024**2)
    require(sha(actual.read_bytes())==sha(expected),'actual selected Python differs')
    if args.coordinate_deadline_ns:
        require(root.is_dir(),'analysis root absent');bounded_as(r['coordinator_as_bytes'],r['capture_as_bytes'])
        resource.setrlimit(resource.RLIMIT_FSIZE,(SCRATCH,SCRATCH));coordinate(c,args.coordinate_deadline_ns);return 0
    require(not root.exists(),'fresh analysis root required; no retry/adoption')
    request=parse(read(c['files']['REQUEST']));program=safe(request['evidence_root_binding']['absolute_path']).parent.parent
    require(not root.is_relative_to(program) and not program.is_relative_to(root),'analysis/program overlap')
    for b in c['files'].values():read(b)
    sys.path.insert(0,str(Path(__file__).parent));import d234_supervision as supervisor
    memory=supervisor.mem_available(Path('/proc/meminfo').read_text());disk=supervisor.available_disk(root.parent)
    require(memory>=r['total_memory_bytes']+r['memory_reserve_bytes'] and disk>=SCRATCH+RESERVE,'fresh resource admission insufficient')
    proof=scratch_proof(r['canonical_capture_bytes'],r['worker_count'],r['metadata_bytes'],r['filesystem_overhead_bytes'])
    if not args.run:print(json.dumps(dict(status='PREPARATION_ONLY',scratch=proof,signed_custody_checked=False,execution_authority=False)));return 0
    root.mkdir(mode=0o700);(root/'scratch').mkdir(mode=0o700);bounded_as(r['supervisor_as_bytes'],r['capture_as_bytes']);resource.setrlimit(resource.RLIMIT_FSIZE,(SCRATCH,SCRATCH))
    deadline=time.monotonic_ns()+r['timeout_seconds']*1_000_000_000
    save(root/'analysis-intent.json',dict(configuration_sha256=args.config_sha256,deadline_monotonic_ns=deadline,
        resources=r,scratch=proof,observed_memory_bytes=memory,observed_disk_bytes=disk,execution_authority=False),65536)
    argv=[str(Path(c['python']['path'])),'-B',str(Path(__file__).resolve()),'--config',str(args.config),'--config-sha256',args.config_sha256,'--coordinate-deadline-ns',str(deadline)]
    outcome=supervisor.supervise(argv,root,timeout_seconds=r['timeout_seconds'],scratch_limit=SCRATCH,disk_reserve=RESERVE)
    save(root/'analysis-process-result.json',outcome,65536)
    return 0 if outcome['status']=='ANALYSIS_EXITED' and outcome.get('exit_code')==0 and outcome['all_own_children_reaped'] else 1

if __name__=='__main__':raise SystemExit(main())
