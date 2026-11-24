"""D261 stand-only repaired-reader validation of exactly the 17 retained E26 captures.

Uses original signed preparation and the unchanged D254 child/raw validator.
No collection, custody mutation, retries, full-family admission or reuse credit.
"""
import dataclasses, datetime, hashlib, importlib.util, json, multiprocessing as mp
import os, pathlib, resource, signal, sys, time, traceback, types

E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
OP=E/'daycap-resume-operators-2'
PACK=E/'q16b-continuation-operators-1'
ROOT=E/'q16b-prefix-analysis-3'
HARD=1286361844786205
BOOT='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
HELPER_SHA='d9f6ca2be2903e51064ac8d365477dfb8301abafee57e191165f4bb74f47c465'
REPAIR=E/'d261-reader-operators-1'
READER=dict(path=str(REPAIR/'stage17_formal_control_reader_v1.py'),size_bytes=5922,sha256='236c794b385803b8d8edc4720d3cede81d86806111b0fe4f82e54410f47e625c')
GIB=1024**3

def require(ok,message):
    if not ok:raise ValueError(message)

def main():
    require(os.getuid()==os.geteuid()==1000,'actual evidence owner required')
    require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'original boot changed')
    started=time.monotonic_ns(); deadline=min(HARD-1800*10**9,started+5400*10**9)
    require(deadline>started,'original study cutoff expired')
    ROOT.mkdir(mode=0o700);(ROOT/'scratch').mkdir();(ROOT/'reports').mkdir()
    spec=importlib.util.spec_from_file_location('bound_d254_analysis',OP/'analyze_daycap.py')
    a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    require(a.sha((OP/'analyze_daycap.py').read_bytes())=='3a771d5fa64ffcbaee08afc4d98b1ffdc47f6f5cd487c48fcbe812b87a54ca2b','unchanged D254 child operator')
    a.save(ROOT/'analysis-intent.json',dict(schema_version='software-d259-retained-prefix-analysis/1',
        started_monotonic_ns=started,deadline_monotonic_ns=deadline,original_hard_deadline_ns=HARD,
        captures=list(range(17)),maximum_workers=8,per_capture_seconds=900,
        operator=a.binding(pathlib.Path(__file__)),helper_sha256=HELPER_SHA,control_reader=READER,
        initial_capture_ordinal=6,initial_workers=1,
        execution_authority=False,phase18_authority=False,custody_mutation=False))
    c=json.loads((E/'daycap-collection-preparation-1/analysis-configuration.json').read_bytes())
    cli=a.configure(c)
    reader_module=types.ModuleType('bound_d261_control_reader');reader_module.__file__=READER['path']
    exec(compile(a.read(READER),reader_module.__file__,'exec'),reader_module.__dict__)
    child_target=__import__('functools').partial(reader_module.analysis_child,original_child=a.child)
    print(json.dumps(dict(stage='original_cli_configured')),flush=True)
    prepared=cli.prepare_formal_retention(repository_root=pathlib.Path(c['repository_root']),
        operational_evidence_root=E,journal=pathlib.Path(c['files']['journal']['path']),journal_directory=E/'journal',
        authorization_path=pathlib.Path(c['files']['authorization']['path']),signature_path=pathlib.Path(c['files']['signature']['path']),
        pilot_archive=pathlib.Path(c['archive']),pilot_sidecar=pathlib.Path(c['sidecar']))
    require(prepared.request_bytes==a.read(c['files']['request']),'actual signed request differs')
    plan=prepared.request['action_inputs']['plan']
    require(len(plan['captures'])==120,'original fixed120 plan required')
    phase=pathlib.Path(prepared.request['evidence_root_binding']['absolute_path'])
    failure_raw=(phase/'stage17-q16b-failure-v6.json').read_bytes()
    require(a.sha(failure_raw)=='332662f64d2f802578c0152aec69781f3b913afca43efe2714483da7e80b3269','original failure changed')
    failure=json.loads(failure_raw)
    require(failure['leader_reaped'] is True and failure['process_group_gone'] is True
        and failure['restoration_verified'] is True and failure['quarantine_operation']['performed'] is False,
        'original native cleanup/restoration not proven')
    require(failure['request_sha256']==c['files']['request']['sha256']
        and failure['runtime_sha256']=='305cedfc5438c68ececfa6a0f954d757112a50c87f687b93ad7b013b7ed757dd',
        'original failed worker/request differs')
    restoration_raw=(E/'daycap-resume-study-2/partition-restoration.json').read_bytes()
    require(a.sha(restoration_raw)=='4cdad298a4b40421e413dd5f315145bbc89a1c8ac832c2fd9de4312d42aa7fe9','original isolation restoration changed')
    restoration=json.loads(restoration_raw)
    require(restoration['verified'] is True and not restoration['errors'],'isolation restoration not verified')
    a.read(restoration['receipt'])
    print(json.dumps(dict(stage='original_signed_lifecycle_prepared')),flush=True)
    helper_raw=(PACK/'stage17_retained_capture_inspection_v1.py').read_bytes()
    require(a.sha(helper_raw)==HELPER_SHA,'inspection helper bytes changed')
    helper=types.ModuleType('bound_d259_inspection');helper.__file__=str(PACK/'stage17_retained_capture_inspection_v1.py')
    exec(compile(helper_raw,helper.__file__,'exec'),helper.__dict__)
    import stage17_formal_archive_registry_v1 as registry
    extent=cli.controller.contract.validate_plan('Q16b',plan)
    decode=cli.registry._metadata_decode_limits(plan,extent,prepared.archive_runtime_profile,deadline)
    executor=cli.controller.make_executor();verified=[]
    with executor.open_store(prepared.request,deadline) as store:
        ledger=dataclasses.asdict(store.ledger_binding())
        require(ledger==json.loads((E/'q16b-prefix-inspection-1/inventory.json').read_bytes())['ledger'],
            'original inspected ledger changed')
        for ordinal in range(17):
            def bound(name):
                path=phase/name
                require(path.stat().st_size<=128*1024,'small metadata required')
                raw=path.read_bytes()
                return dict(file_name=name,size_bytes=len(raw),sha256=a.sha(raw))
            arguments=dict(store=store,action='Q16b',capture=plan['captures'][ordinal]['capture'],
                checkpoint_binding=bound(f'formal-capture-{ordinal}-final-checkpoint.json'),
                decoder_profile=prepared.archive_runtime_profile.decoder,decoder_limits=decode)
            if ordinal<16:
                row=registry.verify_capture_metadata(**arguments,
                    receipt_binding=bound(f'formal-capture-{ordinal}-archive-custody.json'))
            else:row=helper.inspect_capture(**arguments)
            verified.append(row);a.save(ROOT/f'capture-{ordinal}-metadata.json',row)
            print(json.dumps(dict(stage='metadata',completed=len(verified),total=17)),flush=True)
        require(dataclasses.asdict(store.ledger_binding())==ledger,'inspection wrote original ledger')
    allowed=os.sched_getaffinity(0)
    observed={cpu:tuple(int((pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')/name).read_text())
        for name in ('physical_package_id','core_id')) for cpu in allowed}
    cpus=a.workers_for(allowed,observed)
    mem={line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines()
         if line.startswith('MemAvailable:')}
    require(mem['MemAvailable']>=164*GIB,'164GiB analysis available memory required')
    # Charge retained failed canonical spools and exact bound retained sizes.
    retained_spool_bytes=0
    for old_root in (E/'q16b-prefix-analysis-1/scratch',E/'q16b-prefix-analysis-2/scratch'):
        require(old_root.is_dir() and not old_root.is_symlink(),'original scratch root changed')
        for p in old_root.rglob('*'):
            st=p.lstat()
            require(not p.is_symlink(),'symlink in retained scratch')
            if p.is_file():
                require(st.st_nlink==1,'hardlink in retained scratch')
                retained_spool_bytes+=max(st.st_size,st.st_blocks*512)
            else:require(p.is_dir(),'unexpected retained scratch object')
    canonical_sizes=[sum(row['logical']['size_bytes'] for row in cap['artifacts']) for cap in verified]
    require(all(0<n<=c['canonical_capture_bytes'] for n in canonical_sizes),'actual canonical size exceeds declaration')
    scratch=retained_spool_bytes+sum(sorted(canonical_sizes,reverse=True)[:8])+17*GIB
    require(scratch<=256*GIB,'retained+active aggregate scratch exceeds256GiB')
    fs=os.statvfs(ROOT);require(fs.f_bavail*fs.f_frsize>=256*GIB+16*GIB,'scratch+reserve required')
    resource.setrlimit(resource.RLIMIT_AS,(2*GIB,16*GIB));resource.setrlimit(resource.RLIMIT_FSIZE,(256*GIB,256*GIB))
    a.save(ROOT/'metadata-complete.json',dict(captures=17,original_signed_lifecycle_prepared=True,
        ledger=ledger,ledger_unchanged=True,physical_cpus=cpus,available_memory_bytes=mem['MemAvailable'],
        scratch_bytes=scratch,retained_failed_spool_bytes=retained_spool_bytes,control_reader=READER,custody_incomplete_ordinals=[16],execution_authority=False))
    jobs=[dict(item=plan['captures'][i],verified=row,program_root=str(phase.parent.parent),
        scratch=str(ROOT/'scratch'),reports=str(ROOT/'reports'),canonical_bytes=sum(row['logical']['size_bytes'] for row in verified[i]['artifacts']))
        for i,row in enumerate(verified)]
    context=mp.get_context('fork');pending=[jobs[6]]+jobs[:6]+jobs[7:];active={};results={}
    def interrupted(signum,_):raise RuntimeError('analysis interrupted by signal '+str(signum))
    for signum in (signal.SIGTERM,signal.SIGINT):signal.signal(signum,interrupted)
    try:
        while pending or active:
            require(time.monotonic_ns()<deadline,'prefix whole-analysis deadline')
            for cpu in cpus:
                if cpu in active or not pending:continue
                if 6 not in results and (active or pending[0]['item']['capture']['ordinal']!=6):continue
                job=pending.pop(0);receiver,sender=context.Pipe(duplex=False)
                process=context.Process(target=child_target,args=(sender,job,prepared.archive_runtime_profile,
                    decode,prepared.request['action_inputs']['hardware_control'],cpu,deadline))
                process.start();sender.close();active[cpu]=(process,receiver,time.monotonic_ns(),job['item']['capture']['ordinal'])
            for cpu,(process,connection,child_started,ordinal) in list(active.items()):
                require(time.monotonic_ns()-child_started<902*10**9,'child cleanup deadline')
                if connection.poll():
                    result=connection.recv();process.join(timeout=2)
                    a.save(ROOT/f'capture-{ordinal}-process.json',result)
                    require(process.exitcode==0,'analysis child exit')
                    require(result['status']=='VALID' and result['ordinal']==ordinal,'invalid retained capture: '+str(result))
                    results[ordinal]=result;connection.close();del active[cpu]
                    print(json.dumps(dict(stage='raw_validation',completed=len(results),total=17,ordinal=ordinal,
                        seconds=result['seconds'])),flush=True)
                elif not process.is_alive():raise RuntimeError('analysis child exited without report '+str(ordinal))
            if active:time.sleep(.1)
    finally:
        for process,connection,_,_ in active.values():
            if process.is_alive():process.terminate()
        for process,connection,_,_ in active.values():
            process.join(timeout=2)
            if process.is_alive():process.kill();process.join(timeout=2)
            connection.close()
        require(all(not p.is_alive() for p,_,_,_ in active.values()),'analysis children not reaped')
    with executor.open_store(prepared.request,deadline) as store:
        require(dataclasses.asdict(store.ledger_binding())==ledger,'original ledger changed during analysis')
    require(set(results)==set(range(17)),'all17 required without replacements')
    manifest=dict(status='ALL_17_RAW_VALIDATED_CUSTODY_INCOMPLETE',captures=17,
        original_request=c['files']['request'],original_family=phase.name,ledger=ledger,
        original_hard_deadline_ns=HARD,completed_monotonic_ns=time.monotonic_ns(),
        elapsed_seconds=(time.monotonic_ns()-started)/1e9,
        reports=[dict(ordinal=i,report=results[i]['report'],seconds=results[i]['seconds']) for i in range(17)],
        custody_incomplete_ordinals=[16],control_reader=READER,all_raw_reconstructed_and_hash_checked=True,
        canonical_spools_removed=True,completed_family_established=False,reuse_accepted=False,
        execution_authority=False,phase18_authority=False)
    a.save(ROOT/'analysis-complete.json',manifest)
    print(json.dumps(dict(stage='complete',status=manifest['status'],captures=17)),flush=True)

if __name__=='__main__':
    try:main()
    except BaseException as error:
        raw=(json.dumps(dict(status='FAILED',error=repr(error),traceback=traceback.format_exc(limit=20)[-32768:],
            execution_authority=False),sort_keys=True)+'\n').encode()
        if ROOT.is_dir():
            with (ROOT/'analysis-failure.json').open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        raise
