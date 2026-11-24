"""D260 stand-only independent validation of103 new captures; reuse original17.

The original decoder/scientific child is hash-pinned and only its D261 control
reader is selected. No measurement, retry, raw prefix reanalysis or signing.
"""
import argparse,dataclasses,functools,hashlib,importlib.util,json,multiprocessing as mp,os,pathlib,resource,signal,sys,time,types
GIB=1024**3
OP=pathlib.Path(__file__).resolve().parent
p=OP/'original_analysis.py'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='3a771d5fa64ffcbaee08afc4d98b1ffdc47f6f5cd487c48fcbe812b87a54ca2b'
s=importlib.util.spec_from_file_location('d260_original_archive_analysis',p);original=importlib.util.module_from_spec(s);s.loader.exec_module(original)
require,read,binding,canonical,sha=original.require,original.read,original.binding,original.canonical,original.sha
workers_for=original.workers_for
child_target=None

def save(path,value):
 result=original.save(path,value)
 fd=os.open(pathlib.Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 return result

def configure(c):
 global child_target
 require(c['schema_version']=='software-d260-offline-analysis/1' and c['execution_authority'] is False,'offline-only config')
 require(c['operator_sha256']==sha(pathlib.Path(__file__).read_bytes()),'analysis source changed')
 for b in c['files'].values():read(b)
 wrapper=types.ModuleType('d260_cli_wrapper');wrapper.__file__=c['files']['cli_wrapper']['path']
 exec(compile(read(c['files']['cli_wrapper']),wrapper.__file__,'exec'),wrapper.__dict__)
 cli,_=wrapper.configure(pathlib.Path(c['files']['cli_configuration']['path']),c['files']['cli_configuration']['sha256'])
 import stage17_formal_control_reader_v1 as reader
 require(sha(pathlib.Path(reader.__file__).read_bytes())=='236c794b385803b8d8edc4720d3cede81d86806111b0fe4f82e54410f47e625c','unchanged D261 reader required')
 child_target=functools.partial(reader.analysis_child,original_child=original.child)
 return cli

def aggregate_scratch(verified,maximum):
 old=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-26')
 failed=0
 for root in (old/'q16b-prefix-analysis-1/scratch',old/'q16b-prefix-analysis-2/scratch'):
  require(root.is_dir() and not root.is_symlink(),'original failed scratch root required')
  for p in root.rglob('*'):
   st=p.lstat();require(not p.is_symlink(),'failed scratch symlink')
   if p.is_file():
    require(st.st_nlink==1,'failed scratch hardlink');failed+=max(st.st_size,st.st_blocks*512)
   else:require(p.is_dir(),'failed scratch object')
 sizes=[sum(r['logical']['size_bytes'] for r in cap['artifacts']) for cap in verified['captures']]
 require(len(sizes)==103 and all(0<n<=maximum for n in sizes),'actual103 canonical sizes')
 total=failed+sum(sorted(sizes,reverse=True)[:8])+17*GIB
 require(total<=256*GIB,'retained plus active aggregate scratch exceeds256GiB')
 return total,failed,sizes

def compose(c,plan,new_records):
 b=c['files']['composition'];module=types.ModuleType('stage17_service_continuation_calibration_v1');module.__file__=b['path'];sys.modules[module.__name__]=module
 exec(compile(read(b),module.__file__,'exec'),module.__dict__)
 prefix=json.loads(read(plan['continuation']['accepted_prefix_manifest']))
 require(prefix['status']=='PREFIX_17_VALID_CUSTODY_COMPLETE' and len(prefix['captures'])==17,'completed original17 required')
 parent=json.loads(read(plan['continuation']['parent_plan']));records=[]
 for row in prefix['captures']:
  ordinal=row['original_ordinal'];raw=read(row['scientific_report']);records.append(dict(capture_ordinal=ordinal,measurement_run_id=parent['captures'][ordinal]['capture']['measurement']['run_id'],validity='VALID',report_binding=dict(artifact_id=f'Q16B-ORIGINAL-AA-{ordinal}',size_bytes=len(raw),sha256=sha(raw)),report_utf8_bytes=raw.decode()))
 result=module.evaluate(parent,plan,records,new_records)
 require(result['status']=='DESCRIPTIVE' and result['descriptive_summary_complete'] is True,'all17 plus103 must independently validate')
 require([p['planned_captures'] for p in result['source_populations']]==[17,103] and result['tolerance_guarantee'] is False,'explicit mixed lineage; no59-run guarantee')
 return result

def analyze(c,global_deadline):
 cli=configure(c);evidence=pathlib.Path(c['evidence_root']);root=pathlib.Path(c['analysis_root']);require(not root.exists(),'exclusive fresh analysis; no retry')
 require(pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==c['boot_id'],'boot changed')
 online=set()
 for token in pathlib.Path('/sys/devices/system/cpu/online').read_text().strip().split(','):
  if '-' in token:
   a,b=map(int,token.split('-'));online.update(range(a,b+1))
  else:online.add(int(token))
 # Runs only after signed completion has proved native reaping/restoration.
 os.sched_setaffinity(0,online);allowed=os.sched_getaffinity(0)
 observed={cpu:tuple(int((pathlib.Path(f'/sys/devices/system/cpu/cpu{cpu}/topology')/name).read_text()) for name in ('physical_package_id','core_id')) for cpu in allowed}
 cpus=workers_for(allowed,observed)
 mem={line.split(':')[0]:int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
 require(mem['MemAvailable']>=164*GIB,'fresh164GiB available-memory admission')
 canonical_bytes=c['canonical_capture_bytes'];require(0<canonical_bytes<=31227906332,'canonical capture ceiling')
 fs=os.statvfs(root.parent);require(fs.f_bavail*fs.f_frsize>=256*GIB+16*GIB,'fresh scratch+failure reserve')
 resource.setrlimit(resource.RLIMIT_AS,(2*GIB,16*GIB));resource.setrlimit(resource.RLIMIT_FSIZE,(256*GIB,256*GIB))
 prepared=cli.prepare_formal_retention(repository_root=pathlib.Path(c['repository_root']),operational_evidence_root=evidence,journal=pathlib.Path(c['files']['journal']['path']),journal_directory=evidence/'journal',authorization_path=pathlib.Path(c['files']['authorization']['path']),signature_path=pathlib.Path(c['files']['signature']['path']),pilot_archive=pathlib.Path(c['archive']),pilot_sidecar=pathlib.Path(c['sidecar']))
 require(prepared.request_bytes==read(c['files']['request']),'actual signed request differs')
 plan=prepared.request['action_inputs']['plan'];require(len(plan['captures'])==103,'all103 required')
 phase=pathlib.Path(prepared.request['evidence_root_binding']['absolute_path'])
 verified=cli.admit_formal_retention(prepared,phase)
 require(verified['inverse_readback_performed'] is False and len(verified['captures'])==103,'independent decode required for all103')
 root.mkdir(mode=0o700);(root/'scratch').mkdir();(root/'reports').mkdir()
 scratch,failed,canonical_sizes=aggregate_scratch(verified,canonical_bytes)
 deadline=min(global_deadline,time.monotonic_ns()+13500*10**9)
 save(root/'analysis-intent.json',dict(deadline_monotonic_ns=deadline,worker_count=8,physical_cpus=cpus,observed_memory_available_bytes=mem['MemAvailable'],scratch_bytes=scratch,retained_failed_spool_bytes=failed,per_capture_seconds=900,execution_authority=False))
 save(root/'signed-family-metadata.json',verified)
 a=cli.registry.archive;decode=cli.registry._metadata_decode_limits(plan,cli.controller.contract.validate_plan('Q16b',plan),prepared.archive_runtime_profile,deadline)
 jobs=[dict(item=item,verified=cap,program_root=str(phase.parent.parent),scratch=str(root/'scratch'),reports=str(root/'reports'),canonical_bytes=canonical_sizes[i]) for i,(item,cap) in enumerate(zip(plan['captures'],verified['captures'],strict=True))]
 context=mp.get_context('fork');pending=list(jobs);active={};results={}
 try:
  while pending or active:
   require(time.monotonic_ns()<deadline,'whole offline-analysis deadline')
   for cpu in cpus:
    if cpu in active or not pending:continue
    job=pending.pop(0);receiver,sender=context.Pipe(duplex=False)
    process=context.Process(target=child_target,args=(sender,job,prepared.archive_runtime_profile,decode,prepared.request['action_inputs']['hardware_control'],cpu,deadline))
    process.start();sender.close();active[cpu]=(process,receiver,time.monotonic_ns(),job['item']['capture']['ordinal'])
   for cpu,(process,connection,started,ordinal) in list(active.items()):
    require(time.monotonic_ns()-started<902*10**9,'capture child cleanup deadline')
    if connection.poll():
     result=connection.recv();process.join(timeout=2);require(process.exitcode==0,'analysis child exit')
     save(root/f'capture-{ordinal}-process.json',result);require(result['status']=='VALID' and result['ordinal']==ordinal,'invalid required capture: '+str(result))
     results[ordinal]=result;connection.close();del active[cpu]
     print(json.dumps(dict(completed=len(results),total=103,capture_ordinal=ordinal)),flush=True)
    elif not process.is_alive():raise RuntimeError('capture analysis exited without report '+str(ordinal))
   if active:time.sleep(.1)
 finally:
  for process,connection,_,_ in active.values():
   if process.is_alive():process.terminate()
  for process,connection,_,_ in active.values():
   process.join(timeout=2)
   if process.is_alive():process.kill();process.join(timeout=2)
   connection.close()
  require(all(not p.is_alive() for p,_,_,_ in active.values()),'analysis children not reaped')
 records=[]
 for ordinal in range(103):
  raw=read(results[ordinal]['report']);records.append(dict(capture_ordinal=ordinal,measurement_run_id=plan['captures'][ordinal]['capture']['measurement']['run_id'],validity='VALID',report_binding=dict(artifact_id=f'Q16B-CAPTURE-{ordinal}',size_bytes=len(raw),sha256=sha(raw)),report_utf8_bytes=raw.decode()))
 result=compose(c,plan,records);save(root/'calibration-validation.json',result)
 save(root/'analysis-complete.json',dict(status='ALL_103_ANALYZED',calibration_status=result['status'],report=binding(root/'calibration-validation.json'),captures=103,retained_prefix_captures=17,combined_capture_count=120,cells=60,repetitions_per_cell=2,all_raw_reconstructed_and_hash_checked=True,canonical_spools_removed=True,execution_authority=False,phase18_authority=False,ext007_admitted=False))
 return result


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--config-sha256',required=True);p.add_argument('--global-deadline-ns',type=int,required=True);a=p.parse_args()
 require(os.getuid()==os.geteuid()==1000,'actual evidence owner required')
 c=json.loads(read(dict(path=str(a.config),size_bytes=a.config.stat().st_size,sha256=a.config_sha256)))
 analyze(c,a.global_deadline_ns)
