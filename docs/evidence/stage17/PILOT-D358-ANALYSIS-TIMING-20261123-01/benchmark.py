"""S180 synthetic archive-to-publication timing; no research observations."""
import array,copy,datetime,hashlib,json,os,resource,signal,struct,sys,time
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT if (ROOT/'tools').exists() else ROOT.parents[1]
sys.path[:0]=[str(SOURCE/'tools'),str(SOURCE/'tests')]
import test_stage17_s180_archive_analysis_v1 as fixture
A=fixture.analysis


def scale(test,count):
    f=test.fixture
    old_ids=[f.capture[k] for k in ('warmup_run_id','run_id')]
    new_ids=[('SOFTWARE-ONLY-S180-ANALYSIS-'+name+'-').ljust(44,'X') for name in ('WARMUP','MEASUREMENT')]
    def relabel(value):
        if isinstance(value,dict):
            for key,item in value.items():value[key]=relabel(item)
        elif isinstance(value,list):
            for index,item in enumerate(value):value[index]=relabel(item)
        elif isinstance(value,str) and value in old_ids:return new_ids[old_ids.index(value)]
        return value
    for value in (f.capture,f.control,f.final,f.entry,f.checkpoint):relabel(value)
    arena=f.cache.get(f.capture,fixture.primary.SEED,DEADLINE)[0]
    scheduled=f.control['native_result_before_publication_returns']['session']['scheduled']
    for i,name in enumerate(('warmup','measurement')):
        phase=f.control['phases'][i];state=scheduled['lifecycle']['phases'][i];begin=state['observed_origin']
        run=f.capture['warmup_run_id' if i==0 else 'run_id'];prefix,pb,cb,jb=A.archive.row_layout(run)
        encoded=run.encode();header=struct.pack('<I',len(encoded))+encoded+bytes(prefix-4-len(encoded))
        source=array.array('Q');origin=f.bounds[i]['source_origin_ticks'];checksum=f.resources['initial_consumer_state']
        paths=[f.root/f's180-e0-{name}-{role}.bin' for role in ('producer','consumer')]
        hashes=[hashlib.sha256(),hashlib.sha256()]
        with paths[0].open('wb',buffering=1024**2) as producer,paths[1].open('wb',buffering=1024**2) as consumer:
            for logical in range(count):
                tick=origin+1000+logical*10000;source.append(tick);due=begin+tick-origin;record=arena.order[logical%len(arena.order)]
                def clock(t):return 1000000+t//1000,t
                p=[logical,record,due,*clock(due),*clock(due+1000),*clock(due+2000),*clock(due+3000),*clock(due+4000),logical,15]
                c=[logical,record,*clock(due+4000),*clock(due+5000),*clock(due+6000),*clock(due+7000)]
                left=header+struct.pack('<15Q',*p);right=header+struct.pack('<10Q',*c)
                producer.write(left);consumer.write(right);hashes[0].update(left);hashes[1].update(right)
                checksum=A.capture.common.mix(checksum,record,arena.payload[record])
            for stream in (producer,consumer):stream.flush();os.fsync(stream.fileno())
        for j,(role,width,path) in enumerate(zip(('producer','consumer'),(pb,cb),paths,strict=True)):
            phase[role]=dict(file_name=path.name,size_bytes=count*width,sha256=hashes[j].hexdigest(),role='S180_PRIMARY_RAW',schema_identity=A.capture.codec.FORMAT_ID)
            phase[role+'_snapshot'].update(row_count=count,row_capacity=count+1,row_bytes=width,retained_bytes=count*width)
            phase[role+'_layout'].update(run_id_bytes=len(run.encode()),prefix_bytes=prefix,producer_row_bytes=pb,consumer_row_bytes=cb,joined_row_bytes=jb)
        f.resources['phase_capacity'][i]=dict(producer_primary_rows=count+1,consumer_primary_rows=count+1)
        phase.update(requests=count,retained_attempts=count,accepted=count,full=0,retained_consumed_including_drain=count,checksum=checksum,polls=count+1,empty=1,
            consumer_last_join=dict(status=1,matched=count,failed_producer_row=None))
        state['producer'].update(attempted=count,accepted=count,full=0)
        state['consumer'].update(consumed_including_drain=count,polls=count+1,empty=1)
        observation=dict(logical_sequence=p[0],record_index=p[1],scheduled_arrival=p[2],outcome=0,accepted_ordinal=p[13])
        for key,off in (('producer_handle_begin',3),('record_lookup_completion',5),('enqueue_invocation',7),('enqueue_linearization',9),('enqueue_attempt_completion',11)):
            observation[key]=dict(absolute_nanoseconds=p[off],relative_picoseconds=p[off+1])
        phase['producer_current']['observation']=observation
        original=array.array('Q',source)
        if sys.byteorder=='little':original.byteswap()
        f.bounds[i].update(producer_attempt_limit=count+1,consumer_poll_limit=count+1,offered_count=count,
            source_artifact=dict(artifact_id='SOFTWARE-'+name+'-ORIGINAL',sha256=hashlib.sha256(original.tobytes()).hexdigest()))
        little=array.array('Q',source)
        if sys.byteorder!='little':little.byteswap()
        f.control['schedules'][i]['stream']=f.artifact(f's180-e0-{name}-schedule.bin',little.tobytes(),'S180_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1')
        f.control['schedules'][i].update(prepared_count=count,attempted=count)
        scheduled['schedules'][i].update(offered=count,mapped_last_deadline=due)
    f.prospective=A.capture.prospective_capture(f.capture,f.entry)
    for i,row in enumerate(f.control['schedules']):row['prospective']=copy.deepcopy(f.prospective['schedules'][i])
    f.final['session']=copy.deepcopy(f.control['native_result_before_publication_returns']['session'])
    f.refresh();test.make_inventory()
    test.args['entry']=copy.deepcopy(f.entry)
    test.args['maximum_output_bytes']=count*sum(A.archive.row_layout(f.capture[key])[-1] for key in ('warmup_run_id','run_id'))+4*1024**2
    test.limits=replace(test.limits,max_archive_bytes=2*1024**3,max_canonical_bytes=2*1024**3,max_blocks=100000,deadline_ns=DEADLINE)


def run(count):
    test=fixture.ArchivedTests();test.setUp()
    try:
        start=time.monotonic_ns();scale(test,count);prepared=time.monotonic_ns()-start
        cpu=min(os.sched_getaffinity(0));os.sched_setaffinity(0,{cpu})
        resource.setrlimit(resource.RLIMIT_AS,(A.bounds.ANALYSIS_CHILD_AS,A.bounds.ANALYSIS_CHILD_AS))
        codec=A.load_codec(test.profile,deadline_ns=DEADLINE);usage=resource.getrusage(resource.RUSAGE_SELF);start=time.monotonic_ns()
        outcome=A.analyze_capture(codec=codec,decode_limits=test.limits,expected_cpu=cpu,expected_parent_pid=os.getppid(),**test.args)
        elapsed=time.monotonic_ns()-start;after=resource.getrusage(resource.RUSAGE_SELF)
        report=json.loads((test.args['output_directory']/'capture-validation.json').read_bytes())
        assert report['capture_validation_status']=='PASSED' and report['tail_numerics']['raw_accepted_count']==count
        assert all(r['offered_count']==r['accepted_count']==count for r in report['phases'])
        result=dict(count_each_phase=count,fixture_preparation_ns=prepared,archive_inverse_to_durable_publication_ns=elapsed,
            cpu_user_seconds=after.ru_utime-usage.ru_utime,cpu_system_seconds=after.ru_stime-usage.ru_stime,max_resident_kib=after.ru_maxrss,
            canonical_input_bytes=outcome['canonical_input_bytes'],archived_bytes=sum(p.stat().st_size for p in test.archives.iterdir()),
            permanent_output_bytes=sum(p.stat().st_size for p in test.args['output_directory'].iterdir()),
            inverse_archives=outcome['original_archives_inversely_verified'],canonical_spool_removed=outcome['canonical_spool_removed'],
            row_identity_utf8_bytes=[len(test.fixture.capture[k].encode()) for k in ('warmup_run_id','run_id')],
            control_metadata_scope='SMALL_SYNTHETIC54_QUERY_FIXTURE_NOT_MAXIMUM',geometry_capacity=test.fixture.capture['requested_geometry']['capacity'],
            actual_original_archive_encoder_used=False,independent_test_encoder_used=True,actual_capture_validator_used=True,
            actual_worker_supervisor_used=False)
        location=test.root;test.doCleanups();result['synthetic_files_removed']=not location.exists();return result
    except BaseException:
        # The benchmark has no research data. Its process-owned temporary
        # software fixture is removed by the original test cleanup on failure.
        test.doCleanups();raise


os.umask(0o077)
if os.getsid(0)!=os.getpid():os.setsid()
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
resource.setrlimit(resource.RLIMIT_AS,(A.bounds.ANALYSIS_CHILD_AS,A.bounds.ANALYSIS_CHILD_AS))
resource.setrlimit(resource.RLIMIT_FSIZE,(2*1024**3,2*1024**3))
def expired(*_):raise TimeoutError('original finite synthetic timing limit expired')
signal.signal(signal.SIGALRM,expired);signal.alarm(600);DEADLINE=time.monotonic_ns()+590*10**9
manifest=ROOT/'source-closure.json'
if manifest.exists():
    for row in json.loads(manifest.read_bytes())['files']:
        raw=(ROOT/row['path']).read_bytes()
        assert len(raw)==row['size_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
for process in Path('/proc').iterdir():
    if not process.name.isdecimal():continue
    try:assert (process/'comm').read_text().strip()!='cpu_prefetch_runner'[:15]
    except (OSError,ValueError):pass
fs=os.statvfs(SOURCE/'build');assert fs.f_bavail*fs.f_frsize>=20*1024**3 and fs.f_favail>=128
count=int(sys.argv[1]);assert 4<=count<=1000000
result=run(count);signal.alarm(0)
print(json.dumps(dict(schema_version='cpu-prefetch-stage17-s180-synthetic-full-capture-timing/1',
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),python=sys.version,cpu_affinity=sorted(os.sched_getaffinity(0)),
    result=result,whole_family_timing=False,software_only=True,research_raw_read=False,scientific_source_generated=False,
    qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False),sort_keys=True))
