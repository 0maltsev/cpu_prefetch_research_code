"""D285 one owner-requested preconstruction, isolation rearm and first family."""
import argparse,datetime,hashlib,json,os,sys,time,types
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True);p.add_argument('--operator-sha256',required=True);a=p.parse_args()
assert os.geteuid()==0 and hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==a.operator_sha256
assert hashlib.sha256(a.configuration.read_bytes()).hexdigest()==a.configuration_sha256
c=json.loads(a.configuration.read_bytes());E=Path(c['evidence_root']);S=E/'q16c-continuation-1';assert a.configuration==S/'preconstruction-configuration.json'
b=c['files']['study_driver'];raw=Path(b['path']).read_bytes();assert len(raw)==b['size_bytes'] and hashlib.sha256(raw).hexdigest()==b['sha256']
d=types.ModuleType('d285_bound_driver');d.__file__=b['path'];exec(compile(raw,b['path'],'exec'),d.__dict__)
c,h,window,_=d.configure(a);os.sched_setaffinity(0,{3});window_record=d.load(c['files']['execution_window']);window.validate(window_record,now=time.monotonic_ns())
assert d.load(c['files']['prior_partition_restoration'])['verified'] is True
assert d.load(c['files']['qualification_complete'])==dict(success=True,formal_capture_started=False,isolation_retained_for_formal=True)
assert not Path(c['cgroup']).exists() and not (E/'q16c-study-2').exists()
family=Path(c['program_root'])/'working'/c['files']['frozen_plan']['sha256'];assert not family.exists()
assert not (Path(c['repository_root'])/'evidence/formal-q16c-d282-1').exists()
ledger=max((Path(c['program_root'])/'ledger').glob('*.json'));assert hashlib.sha256(ledger.read_bytes()).hexdigest()=='25a3d0aee5a175eb2a0a8d49a6d8c564716ce3d17f0240c98eed4540ec16280d'
fs=os.statvfs(c['program_root']);assert fs.f_bavail*fs.f_frsize>=6306162921472
plan=d.load(c['files']['frozen_plan']);memory=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))*1024
assert memory>=plan['budget']['memory_bytes']+8*1024**3
h.subreaper();started=time.monotonic_ns();stamp=datetime.datetime.now(datetime.timezone.utc)
d.save(S/'continuation-start.json',dict(started_monotonic_ns=started,started_at_utc=stamp.isoformat(),complete_ceiling_seconds=55620,estimated_ceiling_at_utc=(stamp+datetime.timedelta(seconds=55620)).isoformat(),global_deadline_ns=window_record['global_deadline_ns'],new_windows=0,clocks_repeated=False,q15_repeated=False,automatic_retries=0))
phase=dict(started_monotonic_ns=started,deadline_ns=started+600*10**9,configuration_sha256=a.configuration_sha256,exit_code=None,leader_reaped=False)
argv=['/usr/sbin/runuser','-u','omaltsev','--','/usr/bin/python3','-B',c['files']['preparation_operator']['path'],'construct','--configuration',str(a.configuration),'--configuration-sha256',a.configuration_sha256]
owned=None
try:
 with (S/'construct.log').open('xb') as log:
  owned=h.OwnedProcess(argv,log,{(c['worker']['size_bytes'],c['worker']['sha256'])},protect_native=False)
  phase['pid']=owned.process.pid;phase['exit_code']=owned.wait(phase['deadline_ns']);phase['leader_reaped']=True
finally:
 if owned is not None and owned.process.poll() is None:owned.stop(min(window_record['global_deadline_ns'],time.monotonic_ns()+120*10**9))
 phase['completed_monotonic_ns']=time.monotonic_ns();d.save(S/'preconstruction-result.json',phase)
assert phase['exit_code']==0 and phase['leader_reaped'] is True,'constructor failed; no isolation or native launch'
assert hashlib.sha256(ledger.read_bytes()).hexdigest()=='25a3d0aee5a175eb2a0a8d49a6d8c564716ce3d17f0240c98eed4540ec16280d'
c['files'].update(preconstruction_configuration=d.binding(a.configuration),preconstruction_result=d.binding(S/'preconstruction-result.json'),constructed=d.binding(Path(c['output_root'])/'constructed.json'))
d.verify_preconstruction(c);d.save(S/'operational-configuration.json',c);cb=d.binding(S/'operational-configuration.json')
operator=c['files']['rearm_operator'];argv=['/usr/bin/python3','-B',operator['path'],'--configuration',cb['path'],'--configuration-sha256',cb['sha256'],'--operator-sha256',operator['sha256']]
d.save(S/'rearm-handoff.json',dict(configuration=cb,argv=argv,actual_preconstruction=phase,original_window=c['files']['execution_window'],automatic_retries=0))
os.execv(argv[0],argv)
