"""One-shot detached supervision of the already signed diagnostic action."""
import datetime,hashlib,json,os,pathlib,subprocess,sys,signal
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
R=E/'admission-root';P=E/'operator-preparation-v19';D=E/'discovery-preparation-r2-1';O=E/'discovery-output-r2-1';Q=R/'evidence/discovery-r2-fresh'
A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-ac64633-clean-91a93014b4eb.tar.gz';S=pathlib.Path(str(A)+'.sha256')
sys.path.insert(0,str(P));import run_clock_requalification_v2 as isolation
isolation.Q=E/'discovery-isolation-r2-1'
LAUNCHER=D/'preparation/discovery-launch-224gib-v1.py'
PLAN_SHA='f43cb76f89a095ea27f2b8c9c6b08188fee72768844fc0b3848051a8f6a549e7'
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
    assert hashlib.sha256((P/'run_clock_requalification_v2.py').read_bytes()).hexdigest()=='22873c5c62ed4db7b6758bf7cec8a304afe428104d4ca8498c90414fe2dc5031'
    assert (isolation.Q/'prestate.json').is_file() and (isolation.Q/'isolation-verified.json').is_file()
    assert not (isolation.Q/'restoration.json').exists()
    assert hashlib.sha256((D/'plan.json').read_bytes()).hexdigest()==PLAN_SHA
    assert hashlib.sha256(LAUNCHER.read_bytes()).hexdigest()==LAUNCHER_SHA
    assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
    state=isolation.isolated_state();assert state['partition']['cgroup.procs']==''
    assert 'populated 0' in state['partition']['cgroup.events'].splitlines()
    mem=pathlib.Path('/proc/meminfo').read_text()
    available=int(next(line.split()[1] for line in mem.splitlines() if line.startswith('MemAvailable:')))*1024
    assert available >= 242*1024**3,available
    v=os.statvfs(O);free=v.f_bavail*v.f_frsize;assert free>=388544851990,free
    assert not list(O.iterdir()),'output already contains an attempted action'
    assert (Q/'authorization.json.sig').is_file()
    authorization=json.loads((Q/'authorization.json').read_bytes())
    assert authorization['action_id']=='Q16A-DURATION-DISCOVERY' and authorization['one_attempt'] is True
    now=datetime.datetime.now(datetime.timezone.utc)
    assert datetime.datetime.fromisoformat(authorization['issued_at_utc'].replace('Z','+00:00'))<=now<datetime.datetime.fromisoformat(authorization['expires_at_utc'].replace('Z','+00:00'))
    pc=json.loads((D/'preparation/pc-prelaunch-capacity-r2-1.json').read_bytes())
    assert pc['available_bytes']>=388544851990
    age=(now-datetime.datetime.fromisoformat(pc['observed_at_utc'])).total_seconds();assert 0<=age<=300,age
    return dict(utc=utc(),isolation=state,pc_check=pc,stand_memavailable_bytes=available,stand_disk_available_bytes=free,plan=binding(D/'plan.json'),request=binding(Q/'request.json'),authorization=binding(Q/'authorization.json'),signature=binding(Q/'authorization.json.sig'),launcher=binding(LAUNCHER))
def command():
    return ['/usr/bin/python3','-B',str(LAUNCHER),'--python','/usr/bin/python3','--setpriv','/usr/bin/setpriv','--gid','1000','--controller',str(R/'tools/stage17_phase_controller_v23.py'),'--record',str(E/'discovery-launch-readback-r2-1.json'),'--','--repository-root',str(R),'--journal',str(E/'journal/stage17-state-journal-000009.json'),'--journal-directory',str(E/'journal'),'--operational-evidence-root',str(E),'--authorization',str(Q/'authorization.json'),'--signature',str(Q/'authorization.json.sig'),'--pilot-archive',str(A),'--pilot-sidecar',str(S)]
if sys.argv[1:]==['--owner']:
    isolation.write_control(isolation.CG/'cgroup.procs',str(os.getpid()))
    os.sched_setaffinity(0,{2})
    argv=command();os.execv(argv[0],argv)
elif sys.argv[1:]==['--supervise']:
    child=None;code=None;errors=[]
    def interrupted(number,frame):raise RuntimeError('supervisor signal '+str(number))
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,interrupted)
    try:
        os.sched_setaffinity(0,{3})
        observation=checks();retain(E/'discovery-supervisor-prelaunch-r2-1.json',observation)
        print('DISCOVERY_LAUNCH',utc(),flush=True)
        child=subprocess.Popen(['/usr/bin/python3','-B',str(pathlib.Path(__file__).resolve()),'--owner'],stdin=subprocess.DEVNULL,start_new_session=True)
        retain(E/'discovery-child-pid-r2-1.json',dict(pid=child.pid,supervisor_pid=os.getpid(),utc=utc()))
        code=child.wait()
    except BaseException as error:
        errors.append(repr(error))
    finally:
        def cleanup_signal(number,frame):errors.append('signal during cleanup '+str(number))
        for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,cleanup_signal)
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
        if result['partition_procs']=='':
            prestate=json.loads((isolation.Q/'prestate.json').read_bytes())['prestate']
            try:
                isolation.restore(prestate)
                result['partition_restoration']=json.loads((isolation.Q/'restoration.json').read_bytes())
            except Exception as error:
                result['partition_restoration_error']=repr(error);result['success']=False
        else:
            result['partition_restoration_error']='Partition still populated; no unrelated tasks killed'
            result['success']=False
        retain(E/'discovery-supervisor-result-r2-1.json',result)
        print(json.dumps(result),flush=True)
elif not sys.argv[1:]:
    launched=False
    def interrupted(number,frame):raise RuntimeError('prelaunch signal '+str(number))
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,interrupted)
    try:
        observation=checks();observation.update(argv=command(),supervisor_script=binding(pathlib.Path(__file__).resolve()),pc_check=json.loads((D/'preparation/pc-prelaunch-capacity-r2-1.json').read_bytes()))
        assert observation['pc_check']['available_bytes']>=388544851990
        age=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(observation['pc_check']['observed_at_utc'])).total_seconds();assert 0<=age<=300,age
        retain(E/'discovery-launch-intent-r2-1.json',observation)
        with (E/'discovery-session-r2-1.log').open('xb') as log:
            child=subprocess.Popen(['/usr/bin/python3','-B',str(pathlib.Path(__file__).resolve()),'--supervise'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        print('SUPERVISOR_STARTED',child.pid,flush=True)
        launched=True
        retain(E/'discovery-supervisor-pid-r2-1.json',dict(pid=child.pid,utc=utc()))
    finally:
        for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,lambda number,frame:None)
        if not launched:
            # A successfully spawned supervisor owns cleanup even if retaining
            # its receipt fails; no second execution is attempted.
            if 'child' not in locals():
                prestate=json.loads((isolation.Q/'prestate.json').read_bytes())['prestate']
                isolation.restore(prestate)
else:raise SystemExit('unsupported mode')
