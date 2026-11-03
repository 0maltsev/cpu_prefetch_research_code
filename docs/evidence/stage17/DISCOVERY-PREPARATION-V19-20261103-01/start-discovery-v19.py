"""One-shot detached supervision of the already signed diagnostic action."""
import datetime,hashlib,json,os,pathlib,subprocess,sys
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
R=E/'admission-root';P=E/'operator-preparation-v19';D=E/'discovery-preparation-1';O=E/'discovery-output-1';Q=R/'evidence/discovery-fresh'
A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-ac64633-clean-91a93014b4eb.tar.gz';S=pathlib.Path(str(A)+'.sha256')
sys.path.insert(0,str(P));import run_clock_requalification_v2 as isolation
LAUNCHER=D/'preparation/discovery-launch-224gib-v1.py'
PLAN_SHA='e841c5f00b90db7871423133e1842e6441cdf585633978833239693881ba0967'
LAUNCHER_SHA='7ac619571e7374bd287c36ca91030d5c5f5b52a7017120b012ec597a498747d2'
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def retain(path,doc):
    data=(json.dumps(doc,sort_keys=True,indent=2)+'\n').encode()
    with path.open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    path.chmod(0o644)
def binding(path):
    data=path.read_bytes();return dict(path=str(path),size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
def checks():
    assert os.geteuid()==0
    assert hashlib.sha256((D/'plan.json').read_bytes()).hexdigest()==PLAN_SHA
    assert hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()==LAUNCHER_SHA
    assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
    state=isolation.isolated_state();assert state['partition']['cgroup.procs']==''
    mem=pathlib.Path('/proc/meminfo').read_text()
    available=int(next(line.split()[1] for line in mem.splitlines() if line.startswith('MemAvailable:')))*1024
    assert available >= 242*1024**3,available
    v=os.statvfs(O);free=v.f_bavail*v.f_frsize;assert free>=286091292214,free
    assert not list(O.iterdir()),'output already contains an attempted action'
    assert (Q/'authorization.json.sig').is_file()
    authorization=json.loads((Q/'authorization.json').read_bytes())
    assert authorization['action_id']=='Q16A-DURATION-DISCOVERY' and authorization['one_attempt'] is True
    now=datetime.datetime.now(datetime.timezone.utc)
    assert datetime.datetime.fromisoformat(authorization['issued_at_utc'].replace('Z','+00:00'))<=now<datetime.datetime.fromisoformat(authorization['expires_at_utc'].replace('Z','+00:00'))
    return dict(utc=utc(),isolation=state,stand_memavailable_bytes=available,stand_disk_available_bytes=free,plan=binding(D/'plan.json'),request=binding(Q/'request.json'),authorization=binding(Q/'authorization.json'),signature=binding(Q/'authorization.json.sig'),launcher=binding(LAUNCHER))
def command():
    return ['/usr/bin/python3','-B',str(LAUNCHER),'--python','/usr/bin/python3','--setpriv','/usr/bin/setpriv','--gid','1000','--controller',str(R/'tools/stage17_phase_controller_v23.py'),'--record',str(E/'discovery-launch-readback-1.json'),'--','--repository-root',str(R),'--journal',str(E/'journal/stage17-state-journal-000009.json'),'--journal-directory',str(E/'journal'),'--operational-evidence-root',str(E),'--authorization',str(Q/'authorization.json'),'--signature',str(Q/'authorization.json.sig'),'--pilot-archive',str(A),'--pilot-sidecar',str(S)]
if sys.argv[1:]==['--owner']:
    isolation.write_control(isolation.CG/'cgroup.procs',str(os.getpid()))
    os.sched_setaffinity(0,{2})
    argv=command();os.execv(argv[0],argv)
elif sys.argv[1:]==['--supervise']:
    os.sched_setaffinity(0,{3})
    observation=checks();retain(E/'discovery-supervisor-prelaunch-1.json',observation)
    print('DISCOVERY_LAUNCH',utc(),flush=True)
    child=None;code=None;errors=[]
    try:
        child=subprocess.Popen(['/usr/bin/python3','-B',str(pathlib.Path(__file__).resolve()),'--owner'],stdin=subprocess.DEVNULL,start_new_session=True)
        retain(E/'discovery-child-pid-1.json',dict(pid=child.pid,supervisor_pid=os.getpid(),utc=utc()))
        code=child.wait()
    except BaseException as error:
        errors.append(repr(error))
    finally:
        # Waiting/reaping is not another action invocation. The executor keeps
        # responsibility for its finite watchdog, worker quiescence and MSRs.
        if child is not None:
            while child.poll() is None:
                try:code=child.wait()
                except InterruptedError:continue
            code=child.returncode
        print('DISCOVERY_EXIT',utc(),code,flush=True)
        completion=list(O.glob('*completion-v5.json'));success=code==0 and len(completion)==1 and not errors
        result=dict(utc=utc(),exit_code=code,completion_present=bool(completion),success=success,supervisor_errors=errors,partition_procs=(isolation.CG/'cgroup.procs').read_text())
        if not success:
            if result['partition_procs']=='':
                prestate=json.loads((E/'clock-requalification-2/prospective-plan.json').read_bytes())['prestate']
                try:
                    isolation.restore(prestate)
                    result['partition_restoration']=json.loads((E/'clock-requalification-2/restoration.json').read_bytes())
                except Exception as error:
                    result['partition_restoration_error']=repr(error)
            else:result['partition_restoration_error']='Partition still populated; no unrelated tasks killed'
        else:result['isolation_retained_for_dependent_work']=True
        retain(E/'discovery-supervisor-result-1.json',result)
        print(json.dumps(result),flush=True)
elif not sys.argv[1:]:
    observation=checks();observation.update(argv=command(),supervisor_script=binding(pathlib.Path(__file__).resolve()),pc_check=json.loads((D/'preparation/pc-prelaunch-capacity-1.json').read_bytes()))
    assert observation['pc_check']['available_bytes']>=286091292214
    age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(observation['pc_check']['observed_at_utc'])).total_seconds();assert 0<=age<=300,age
    retain(E/'discovery-launch-intent-1.json',observation)
    with (E/'discovery-session-1.log').open('xb') as log:
        child=subprocess.Popen(['/usr/bin/python3','-B',str(pathlib.Path(__file__).resolve()),'--supervise'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
    retain(E/'discovery-supervisor-pid-1.json',dict(pid=child.pid,utc=utc()))
    print('SUPERVISOR_STARTED',child.pid,flush=True)
else:raise SystemExit('unsupported mode')
