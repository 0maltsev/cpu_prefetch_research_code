"""D276 owner-admitted Q16c family, original owned-process recovery, then offline analysis.

Requires successful actual qualification. No retry, new window, qualification,
old-data validation, archive-program initialization or Stage18 action occurs.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time
import traceback
import types

NS=10**9
CORE='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
OWNERSHIP='47e819dbcd6110d5b356d091e706141131efa5938b0ae0740059efc4d3cb1416'


def require(ok,message):
    if not ok:raise RuntimeError('Q16c study: '+message)


def read(b):
    p=Path(b['path']);require(p.is_absolute() and not any(q.is_symlink() for q in (p,*p.parents)),'nonsymlink source')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());require(0<before.st_size==b['size_bytes']<=32*1024**2,'bounded metadata')
        raw=f.read(before.st_size+1);after=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(stamp(before)==stamp(after)==stamp(p.stat()) and len(raw)==b['size_bytes']
        and hashlib.sha256(raw).hexdigest()==b['sha256'],'bound source changed')
    return raw


def binding(p):
    p=Path(p);raw=p.read_bytes();b=dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());read(b);return b


def load(b):return json.loads(read(b))


def module(name,b):
    require(name not in sys.modules,'foreign module cache')
    m=types.ModuleType(name);m.__file__=b['path'];sys.modules[name]=m;exec(compile(read(b),b['path'],'exec'),m.__dict__);return m


def save(p,value):
    with p.open('xb') as f:f.write(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode());f.flush();os.fsync(f.fileno())
    if os.geteuid()==0:os.chown(p,1000,1000)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def configure(a):
    c=load(dict(path=str(a.configuration),size_bytes=a.configuration.stat().st_size,sha256=a.configuration_sha256))
    require(c['execution_authority'] is False and c['phase18_authority'] is False,'configuration authority')
    require(c['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'same actual boot')
    for key,b in c['files'].items():
        if key!='archive':read(b)
    require(c['files']['study_driver']==binding(Path(__file__).resolve()),'actual driver binding')
    require(c['files']['ownership_core']['sha256']==OWNERSHIP and c['files']['isolation_core']['sha256']==CORE,'original recovery cores')
    h=module('q16c_owned_process_core',c['files']['ownership_core'])
    window=module('q16c_original_window',c['files']['window_helper'])
    restoration=module('q16c_actual_restoration',c['files']['restoration_helper'])
    return c,h,window,restoration


def actual_online_cpus():
    result=set()
    for part in Path('/sys/devices/system/cpu/online').read_text().strip().split(','):
        pair=part.split('-');result.update(range(int(pair[0]),int(pair[-1])+1))
    require(bool(result),'actual online CPU set')
    return result


def owner(a,c,h):
    evidence=Path(c['evidence_root']);study=evidence/'q16c-study-1';intent=load(binding(study/'intent.json'))
    require(os.getppid()==intent['supervisor_pid'] and h.start_ticks(os.getppid())==intent['supervisor_start_ticks']
        and intent['configuration_sha256']==a.configuration_sha256,'actual dedicated parent')
    native=a.role!='analyze';plan=load(c['files']['plan_preview'])
    memory=plan['budget']['memory_bytes'] if native else 16*1024**3
    memlock=max(i['resources']['total_mapping_bytes'] for i in plan['captures']) if native else 8*1024**2
    cg=Path(c['cgroup']);cpus={2} if native else actual_online_cpus()
    if a.owner:
        require(os.geteuid()==0 and len(list(Path('/proc/self/task').iterdir()))==1,'single-threaded root handoff')
        resource.setrlimit(resource.RLIMIT_AS,(memory,)*2);resource.setrlimit(resource.RLIMIT_MEMLOCK,(memlock,)*2)
        if native:
            require((cg/'cgroup.procs').read_text().strip()=='','empty owned partition')
            with (cg/'cgroup.procs').open('w') as f:f.write(str(os.getpid())+'\n')
        os.sched_setaffinity(0,cpus);names=h.CAP_NAMES if native else ('sys_ptrace',);caps='-all,'+','.join('+'+n for n in names)
        argv=['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups','--bounding-set='+caps,
            '--inh-caps='+caps,'--ambient-caps='+caps,sys.executable,'-B',str(Path(__file__).resolve()),'--inner','--role',a.role,
            '--configuration',str(a.configuration),'--configuration-sha256',a.configuration_sha256,'--deadline-ns',str(a.deadline_ns)]
        os.execv(argv[0],argv)
    require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(),'exact evidence owner')
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    mask=h.CAP_MASK if native else h.ANALYSIS_CAP_MASK
    require(all(int(status[k].strip(),16)==mask for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'exact owner capabilities')
    require(os.sched_getaffinity(0)==cpus and resource.getrlimit(resource.RLIMIT_AS)==(memory,)*2
        and resource.getrlimit(resource.RLIMIT_MEMLOCK)==(memlock,)*2,'actual placement and finite limits')
    require(time.monotonic_ns()<a.deadline_ns<=load(c['files']['source_manifest'])['global_deadline_ns'],'absolute owner deadline')
    admission=module('q16c_execution_owner_admission',c['files']['execution_owner_guard'])
    source=load(c['files']['source_manifest'])
    observed=admission.check(Path(c['worker']['path']).parents[2],uid=1000,
        inventory_sha256=source['bundle_inventory_sha256'],source_revision=source['software_source_revision'],
        worker_sha256=c['worker']['sha256'])
    save(study/(a.role+'-execution-owner-admission.json'),observed)

    b=c['files']['preparation_operator' if a.role in ('construct','sign') else 'action_operator']
    argv=[sys.executable,'-B',b['path'],a.role,'--configuration',str(a.configuration),'--configuration-sha256',a.configuration_sha256]
    if a.role not in ('construct','sign'):argv+=['--deadline-ns',str(a.deadline_ns)]
    os.execv(argv[0],argv)


def run(a,c,h,window,restoration):
    require(os.geteuid()==0 and len(list(Path('/proc/self/task').iterdir()))==1,'dedicated root supervisor')
    require(not h.descendants(os.getpid()),'no unrelated descendants');h.subreaper();os.sched_setaffinity(0,{3})
    evidence=Path(c['evidence_root']);study=evidence/'q16c-study-1';record=load(c['files']['source_manifest'])
    window.validate(record,now=time.monotonic_ns());require(not study.exists(),'one exclusive family; no retry')
    require(load(c['files']['qualification_complete'])['success'] is True,'actual fresh qualification completion')
    study.mkdir(mode=0o700);os.chown(study,1000,1000)
    result=dict(schema_version='cpu-prefetch-stage17-q16c-study/1',supervisor_pid=os.getpid(),
        supervisor_start_ticks=h.start_ticks(os.getpid()),configuration_sha256=a.configuration_sha256,
        started_monotonic_ns=time.monotonic_ns(),global_deadline_ns=record['global_deadline_ns'],
        automatic_retries=0,success=False,errors=[],phases=[],phase18_authority=False)
    save(study/'intent.json',result);active=None;clock=None;prepared=request=None;restored=False
    def interrupted(number,frame):raise RuntimeError('study signal '+str(number))
    old={s:signal.signal(s,interrupted) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
    def command(role,deadline):
        nonlocal active
        require(time.monotonic_ns()<deadline,'phase deadline');phase=dict(role=role,started_monotonic_ns=time.monotonic_ns(),deadline_ns=deadline)
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--owner','--role',role,'--configuration',str(a.configuration),
            '--configuration-sha256',a.configuration_sha256,'--deadline-ns',str(deadline)]
        native={(c['worker']['size_bytes'],c['worker']['sha256'])}
        try:
            with (study/(role+'.log')).open('xb') as log:
                active=h.OwnedProcess(argv,log,native,protect_native=role=='collect');phase['pid']=active.process.pid
                code=active.wait(deadline);phase.update(exit_code=code,leader_reaped=True);require(code==0,role+' failed');active=None
        finally:
            phase['completed_monotonic_ns']=time.monotonic_ns();save(study/(role+'-result.json'),phase);result['phases'].append(phase)
    def check_terminal():
        if prepared is None:return
        phase=Path(request['evidence_root_binding']['absolute_path'])
        paths=[phase/('stage17-q16c-'+name+'-v6.json') for name in ('completion','failure')]
        found=[p for p in paths if p.exists()]
        if not found:
            require(not (phase/'stage17-q16c-attempt-v6.json').exists(),'attempt lacks recovery receipt');return
        require(len(found)==1,'conflicting terminal receipts')
        observed=restoration.restoration_status(load(binding(found[0])),attempt_id=request['attempt_id'],
            request_sha256=prepared['request']['sha256'],authorization_sha256=prepared['authorization']['sha256'],
            expected_prestate=request['action_inputs']['hardware_control']['prestate'])
        require(observed['hardware_restoration_verified'],'actual native hardware recovery unverified')
        result['native_terminal']=dict(binding=binding(found[0]),**observed)
    def restore_owned():
        report=dict(verified=False,errors=[])
        try:
            require(clock is not None,'bound isolation adapter required');pre=clock.preparation();receipt=clock.Q/'restoration.json'
            if not receipt.exists():clock.restore(pre['prestate'])
            require(load(binding(receipt))['verified'] is True and not clock.CG.exists(),'actual partition restoration')
            require(clock.root_state()==pre['prestate']['root'],'actual original root state')
            for name,before in pre['prestate']['maintenance_before'].items():
                actual=clock.ISO.systemd_state(name)
                require(actual['UnitFileState']==before['UnitFileState'] and (name not in clock.ISO.TIMER_SERVICES
                    or actual['ActiveState']==before['ActiveState']),'actual maintenance restoration')
            report.update(verified=True,receipt=binding(receipt))
        except BaseException as error:report['errors'].append(repr(error))
        save(study/'partition-restoration.json',report);return report['verified']
    try:
        clock=module('q16c_bound_isolation',c['files']['clock_adapter']);pre=clock.preparation()
        clock.ISO.verify_remaining_lifetime(pre['prestate'],window.FAMILY*NS,120*NS)
        require((clock.CG/'cgroup.procs').read_text().strip()=='','retained empty qualified partition')
        start=time.monotonic_ns();window.validate(record,now=start)
        prep_deadline=min(start+600*NS,record['global_deadline_ns']-(window.COLLECTION+window.ANALYSIS+window.RESTORATION)*NS)
        command('construct',prep_deadline);command('sign',prep_deadline);command('check',prep_deadline)
        prepared=load(binding(Path(c['output_root'])/'prepared.json'));request=load(prepared['request'])
        expiry=datetime.datetime.fromisoformat(load(prepared['authorization'])['expires_at_utc'].replace('Z','+00:00'))
        require((expiry-datetime.datetime.now(datetime.timezone.utc)).total_seconds()>=window.COLLECTION,'full signed collection lease')
        window.validate(record,now=time.monotonic_ns());command('collect',time.monotonic_ns()+window.COLLECTION*NS)
        check_terminal();require(result['native_terminal']['executor_completed'],'required native family completion')
    except BaseException as error:result['errors'].append(repr(error));result['failure_traceback']=traceback.format_exc(limit=20)[-32768:]
    finally:
        for s in old:signal.signal(s,lambda n,f:result['errors'].append('signal during cleanup '+str(n)))
        if active is not None:
            try:active.stop(record['global_deadline_ns']);require(not active.forced,'forced cleanup retained')
            except BaseException as error:result['errors'].append('owned cleanup '+repr(error))
            active=None
        # Signing/check may have published authority before failing. Always inspect
        # its actual request before deciding that native recovery is unnecessary.
        try:
            if prepared is None and (Path(c['output_root'])/'prepared.json').exists():
                prepared=load(binding(Path(c['output_root'])/'prepared.json'));request=load(prepared['request'])
            check_terminal()
        except BaseException as error:result['errors'].append('native recovery '+repr(error))
        try:
            state=types.SimpleNamespace(budget=types.SimpleNamespace(end=min(record['global_deadline_ns'],time.monotonic_ns()+window.RESTORATION*NS)),
                root=study,result=result,restore=restore_owned)
            restored=h.Study.bounded_restore(state);require(restored,'bounded actual isolation restoration')
        except BaseException as error:result['errors'].append('isolation cleanup '+repr(error))
    try:
        if not result['errors'] and restored:
            for s in old:signal.signal(s,interrupted)
            require(time.monotonic_ns()+window.ANALYSIS*NS<record['global_deadline_ns'],'complete analysis reserve')
            command('analyze',time.monotonic_ns()+window.ANALYSIS*NS)
            done=load(binding(evidence/'q16c-analysis-1/complete.json'))
            require(done['status']=='ALL_180_VALID_DESCRIPTIVE_COMPLETE' and len(done['reports'])==180
                and done['all_workers_reaped'] is True,'actual independent full180 analysis')
            result['analysis_complete']=binding(evidence/'q16c-analysis-1/complete.json');result['success']=True
    except BaseException as error:result['errors'].append('analysis '+repr(error));result['failure_traceback']=traceback.format_exc(limit=20)[-32768:]
    finally:
        for s in old:signal.signal(s,lambda n,f:result['errors'].append('signal during final cleanup '+str(n)))
        if active is not None:
            try:active.stop(record['global_deadline_ns'])
            except BaseException as error:result['errors'].append('analysis cleanup '+repr(error))
        if h.descendants(os.getpid()):result['errors'].append('owned descendants remain')
        result['success']=result['success'] and not result['errors'] and restored and time.monotonic_ns()<record['global_deadline_ns']
        result['completed_monotonic_ns']=time.monotonic_ns();save(study/'complete.json',result)
        for s,handler in old.items():signal.signal(s,handler)
    return 0 if result['success'] else 1


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    for name in ('run','owner','inner'):m.add_argument('--'+name,action='store_true')
    p.add_argument('--role',choices=('construct','sign','check','collect','analyze'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--deadline-ns',type=int);a=p.parse_args();c,h,w,r=configure(a)
    if a.run:return run(a,c,h,w,r)
    owner(a,c,h)


if __name__=='__main__':raise SystemExit(main())
