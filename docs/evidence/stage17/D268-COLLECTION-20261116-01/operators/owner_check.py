"""Read-only actual signature, current journal and resource admission before Q16b."""
import argparse,hashlib,json,os,pathlib,sys,time,types

def require(v,m):
 if not v:raise ValueError(m)
def read(b):
 p=pathlib.Path(b['path']);require(p.is_absolute() and all(not x.is_symlink() for x in (p,*p.parents)),'nonsymlink binding')
 with p.open('rb') as f:
  before=os.fstat(f.fileno());require(0<before.st_size==b['size_bytes']<=128*1024**2,'input size');raw=f.read(before.st_size+1);after=os.fstat(f.fileno())
 stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
 require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==before.st_size and hashlib.sha256(raw).hexdigest()==b['sha256'],'changed source/data binding');return raw
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepared-phase',type=pathlib.Path,required=True);p.add_argument('--prepared-phase-sha256',required=True);p.add_argument('--global-deadline-ns',type=int,required=True);a=p.parse_args()
 require(os.getuid()==os.geteuid()==1000 and time.monotonic_ns()<a.global_deadline_ns,'trusted owner and finite deadline')
 d=json.loads(read(dict(path=str(a.prepared_phase),size_bytes=a.prepared_phase.stat().st_size,sha256=a.prepared_phase_sha256)))
 require(d['schema_version']=='software-d254-prepared-phase/1' and d['execution_authority'] is False,'prepared phase schema')
 module=types.ModuleType('daycap_cli');module.__file__=d['wrappers']['cli']['path'];exec(compile(read(d['wrappers']['cli']),module.__file__,'exec'),module.__dict__)
 cli,c=module.configure(pathlib.Path(d['files']['cli_configuration']['path']),d['files']['cli_configuration']['sha256'])
 E=pathlib.Path(d['evidence_root']);root=pathlib.Path(d['repository_root']);latest=cli.base.latest_journal(E)
 # Original v6 prepare_action validates actual detached owner signature, current
 # source/hardware/scientific prerequisites, UTC lease and unconsumed namespace.
 prepared=cli.controller.prepare_action(repository_root=root,operational_evidence_root=E,journal=latest,journal_directory=E/'journal',authorization_path=pathlib.Path(d['files']['authorization']['path']),signature_path=pathlib.Path(d['files']['signature']['path']),pilot_archive=pathlib.Path(c['archive']['path']),pilot_sidecar=pathlib.Path(c['sidecar']['path']))
 require(prepared.request_bytes==read(d['files']['request']) and prepared.request['action_inputs']['plan']==json.loads(read(d['files']['plan'])),'actual request or approved plan changed')
 executor=cli.controller.make_executor();extent=cli.controller.contract.validate_plan('Q16b',prepared.request['action_inputs']['plan'])
 phase=pathlib.Path(d['output_root']);require(phase.is_dir() and not list(phase.iterdir()),'fresh empty registered family required')
 fd=os.open(phase,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
 try:observed=executor.live_resources(fd,extent,request=prepared.request,deadline_ns=min(a.global_deadline_ns,time.monotonic_ns()+120*10**9))
 finally:os.close(fd)
 require(observed['memory_available_bytes']>=extent.declared.memory_bytes+8*1024**3,'native plus operational memory reserve')
 require(time.monotonic_ns()<a.global_deadline_ns,'owner-check exceeded qualification/preparation deadline')
 print(json.dumps(dict(status='ORIGINAL_SIGNATURE_AND_CURRENT_ADMISSION_PASS',captures=103,plan_sha256=d['files']['plan']['sha256'],qualified_worker_sha256=prepared.runtime['sha256'],resource_observation=observed,execution_authority=False)),flush=True)
