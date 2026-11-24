"""Ignored, review-before-use operator launcher for ONE archived Q16a family.

--check is read-only. --launch creates an exclusive intent and detaches one
root supervisor. Qualified CLI18/executor11 alone own native execution/MSR
recovery; the root supervisor reaps its one child and restores owned isolation.
No authority, measured defaults, retry, stand initialization or new gates.
"""
from __future__ import annotations
import argparse, datetime, hashlib, importlib.util, json, os
from pathlib import Path
import resource, signal, stat, subprocess, sys

CAP_NAMES=('sys_ptrace','sys_rawio','dac_override','perfmon')
CAP_MASK=sum(1<<n for n in (19,17,1,38))
FILES=('plan','preparation','request','authorization','signature','admission','scope','profile',
       'manifest','isolation_operator','isolation_prestate','isolation_readback','clock_complete',
       'q15_result','q15_completion')


"""Operator reporting only: executor receipt shapes remain immutable."""
import re


def restoration_status(receipt, *, attempt_id, request_sha256, authorization_sha256):
    for name, expected in (("attempt_id", attempt_id), ("request_sha256", request_sha256),
                           ("authorization_sha256", authorization_sha256), ("action_id", "Q16a")):
        if receipt.get(name) != expected:
            raise ValueError("executor receipt binding differs: " + name)
    schema = receipt.get("schema_version")
    if schema == "cpu-prefetch-stage17-phase-action-failure/6":
        operation = receipt.get("quarantine_operation")
        if not isinstance(operation, dict) or type(operation.get("performed")) is not bool:
            raise ValueError("failure quarantine observation missing")
        quarantined = operation["performed"]
        readback = receipt.get("recovery_readback")
        complete = False
    elif schema == "cpu-prefetch-stage17-phase-action-completion/6":
        quarantined = receipt.get("quarantined")
        if type(quarantined) is not bool:
            raise ValueError("completion quarantine observation missing")
        readback = receipt.get("live_restoration_readback")
        complete = True
    else:
        raise ValueError("unsupported executor receipt schema")
    for field in ("leader_reaped", "process_group_gone", "restoration_verified"):
        if type(receipt.get(field)) is not bool:
            raise ValueError("missing actual restoration/cleanup observation: " + field)
    verified = (receipt["restoration_verified"] and not quarantined
                and receipt["leader_reaped"] and receipt["process_group_gone"])
    if verified:
        if not isinstance(readback, list) or not readback:
            raise ValueError("claimed restoration lacks actual readback")
        seen = set()
        for row in readback:
            if (not isinstance(row, dict) or type(row.get("cpu")) is not int
                    or row["cpu"] < 0 or row["cpu"] in seen or row.get("matches") is not True
                    or not isinstance(row.get("requested_hex"), str)
                    or re.fullmatch(r"[0-9a-f]{16}", row["requested_hex"]) is None
                    or row.get("observed_hex") != row["requested_hex"]):
                raise ValueError("invalid hardware restoration readback")
            seen.add(row["cpu"])
    return {"hardware_restoration_verified": verified, "executor_completed": complete,
            "executor_quarantined": quarantined}


def error_record(error):
    return {"type": type(error).__name__, "message": str(error),
            "errno": getattr(error, "errno", None), "filename": getattr(error, "filename", None)}



def require(ok,message):
    if not ok: raise ValueError(message)

def digest(raw): return hashlib.sha256(raw).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()

def bytes_at(path):
    path=Path(path)
    require(path.is_absolute() and all(not p.is_symlink() for p in (path,*path.parents)), 'absolute nonsymlink path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode),'regular file required')
        raw=stream.read();after=os.fstat(stream.fileno())
    key=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(key(before)==key(after)==key(path.stat()),'input changed during read')
    return raw

def bound(path):
    raw=bytes_at(path);return dict(path=str(path),size_bytes=len(raw),sha256=digest(raw))

def read_bound(value):
    require(set(value)=={'path','size_bytes','sha256'},'file binding shape')
    raw=bytes_at(value['path']);require(len(raw)==value['size_bytes'] and digest(raw)==value['sha256'],'file binding differs: '+value['path'])
    return raw

def read_config(args):
    raw=bytes_at(args.config);require(digest(raw)==args.config_sha256,'configuration changed')
    c=json.loads(raw)
    require(c['schema_version']=='software-formal-q16a-launch/1','configuration schema')
    require(set(c['files'])==set(FILES),'exact bound input membership required')
    require(c['launcher_sha256']==digest(bytes_at(Path(__file__).resolve())),'reviewed launcher bytes differ')
    require(c['uid']==1000 and type(c['gid']) is int and c['gid']>=0,'explicit trusted UID/GID required')
    require(Path(c['program_root']).is_absolute() and Path(c['launch_root']).is_absolute(),'absolute roots required')
    return c

def retain(c,name,value):
    path=Path(c['launch_root'])/name
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(canonical(value)+b'\n');stream.flush();os.fsync(stream.fileno())
    if os.geteuid()==0:os.chown(path,c['uid'],c['gid'])
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def limits(plan,proof,as_bytes,memlock_bytes):
    require(type(as_bytes) is int and type(memlock_bytes) is int and as_bytes>0 and memlock_bytes>0,'explicit finite positive limits required')
    native=max(row['execution_budget']['memory_bytes'] for row in plan['captures'])
    mapped=max(row['resources']['total_mapping_bytes'] for row in plan['captures'])
    family=plan['budget']['memory_bytes']
    require(proof['required_worker_as_bytes']==native and proof['max_native_mapping_bytes']==mapped
            and proof['required_family_as_bytes']==family,'sizing proof/plan resource mismatch')
    require(as_bytes==native,'AS must equal plan-bound worker ceiling; family total is not per-process AS')
    require(memlock_bytes>=mapped,'MEMLOCK below actual maximum native mapping bytes')
    require(memlock_bytes<=as_bytes,'MEMLOCK exceeds AS')
    reserve=proof['operational_memory_reserve_bytes']
    require(type(reserve) is int and reserve>=0,'explicit prospective operational memory reserve required')
    return dict(operational_memory_reserve_bytes=reserve,required_available_memory_bytes=family+reserve,
                address_space_bytes=as_bytes,memory_lock_bytes=memlock_bytes,
                required_worker_as_bytes=native,required_family_as_bytes=family,max_native_mapping_bytes=mapped)

def program_admission_lineage(plan,parent,scope,admission,*,program_root,admission_sha256):
    # The original shared program is not reinitialized for a new qualified
    # producer. Its admission binds the original implementation profile; the
    # continuation plan separately binds the newly qualified runtime profile.
    storage=plan['storage'];original=parent['storage']
    require(scope['program_id']==storage['program_id']==original['program_id'], 'shared program identity differs')
    require(storage['program_scope_sha256']==original['program_scope_sha256'], 'continuation changed program scope')
    require(scope['prospective_admission_sha256']==admission_sha256, 'original admission hash differs')
    require(admission['schema_version']=='cpu-prefetch-stage17-formal-program-storage-admission/1', 'original admission schema')
    require(admission['program_root']==program_root and admission['program_id']==original['program_id'], 'original admission root/program differs')
    require(admission['implementation_profile_sha256']==original['implementation_profile_sha256'], 'original admission/profile lineage differs')
    require(admission['source_revision']==parent['source_revision'], 'original admission/source lineage differs')
    require(admission['storage_domain_id']==scope['storage_domain_id'], 'original storage domain differs')
    require(scope['shared_program_quota_bytes']==storage['archive_quota_bytes']==admission['archive_quota_bytes'], 'shared program quota differs')
    for key in ('workspace_bytes','analysis_scratch_bytes','disk_reserve_bytes'):
        require(admission[key]==storage[key]==original[key], 'original storage ceiling differs: '+key)

def continuation_lineage(plan,scope,admission,*,program_root,admission_sha256):
    import stage17_formal_ring_continuation_v1 as continuation
    parent_bytes=read_bound(plan['continuation']['parent_plan'])
    continuation.validate_parent(plan,parent_bytes)
    parent=json.loads(parent_bytes)
    # Exact proof bytes must exist before the qualified controller verifies
    # their meanings. Hash checks alone grant no prefix/compatibility credit.
    for key in ('failed_family_receipt','accepted_prefix_manifest','compatibility_manifest'):
        read_bound(plan['continuation'][key])
    program_admission_lineage(plan,parent,scope,admission,program_root=program_root,
                              admission_sha256=admission_sha256)
    return parent

def documents(c,args):
    raw={name:read_bound(value) for name,value in c['files'].items()}
    d={name:json.loads(value) for name,value in raw.items() if name not in ('signature','isolation_operator')}
    plan=d['plan'];proof=d['preparation'];request=d['request'];storage=plan['storage']
    sys.path.insert(0,str(Path(c['repository_root'])/'tools'))
    import stage17_formal_archive_v1 as archive
    require(raw['plan']==archive.canonical(plan),'plan must be exact repository canonical bytes without LF')
    plan_sha=digest(raw['plan'])
    require(proof['plan_sha256']==plan_sha and proof['source_revision']==plan['source_revision'],'layout proof identity')
    require(plan['schema_version']=='cpu-prefetch-stage17-formal-ring-plan/3','only incident-bound archived Q16a continuation permitted')
    require(request['action_id']=='Q16a' and request['schema_version']=='cpu-prefetch-stage17-fixed-action-request/6','request action/version')
    require(request['action_inputs']['plan']==plan,'request carries different plan')
    scope=d['scope'];family=Path(c['program_root'])/'working'/plan_sha
    require(Path(c['files']['scope']['path'])==Path(c['program_root'])/'scope.json','scope path differs')
    require(scope['program_id']==storage['program_id'] and digest(raw['scope'])==storage['program_scope_sha256'],'program scope differs')
    require(scope['prospective_admission_sha256']==digest(raw['admission']),'prospective admission differs')
    require(digest(raw['profile'])==storage['implementation_profile_sha256'],'archive implementation differs')
    require(request['evidence_root_binding']['absolute_path']==str(family),'request is not the registered family root')
    auth=d['authorization'];binding=auth['request_binding']
    require(binding['path']==c['files']['request']['path'] and binding['sha256']==digest(raw['request'])
            and binding['size_bytes']==len(raw['request']),'authorization request binding differs')
    require(auth['action_id']=='Q16a' and auth['one_attempt'] is True and auth['retry_allowed'] is False,'one-shot formal authority required')
    manifest=d['manifest']
    require(manifest['bundle_profile']=='STAGE17-PILOT-CANDIDATE-BUNDLE-v26'
            and manifest['source_archive']['source_revision']==plan['source_revision']
            and manifest['source_archive']['source_dirty'] is False,'clean qualified release differs')
    bundle=Path(c['bundle_root'])
    require(Path(c['files']['manifest']['path'])==bundle/'BUNDLE_MANIFEST.json'
            and Path(c['files']['profile']['path'])==bundle/'config/stage17/formal-archive-implementation-profile-v1.json','release member paths differ')
    worker=manifest['stage17_fixed_action_runtime'];actual=bound(bundle/worker['member_path'])
    require((actual['size_bytes'],actual['sha256'])==(worker['size_bytes'],worker['sha256']),'qualified worker bytes changed')
    python=Path(c['python']);require(python==Path('/usr/bin/python3.14'),'actual qualified stand Python path required')
    py=bound(python);require((py['size_bytes'],py['sha256'])==(d['profile']['python']['size_bytes'],d['profile']['python']['sha256']),'stand Python/profile differs')
    require(d['profile']['python']['location']=='runtime' and d['profile']['python']['path']=='usr/bin/python3.14','qualified runtime-root / binding differs')
    for image in (python,bundle/worker['member_path']):
        require(not image.stat().st_mode&(stat.S_ISUID|stat.S_ISGID) and 'security.capability' not in os.listxattr(image),'exec image would alter ambient capability inheritance')
    require(bound(Path(c['setpriv']))==c['setpriv_binding'],'setpriv image differs')
    for key in ('controller_cpu','supervisor_cpu'):require(type(c[key]) is int and c[key]>=0,'explicit CPU required')
    require(c['controller_cpu']!=c['supervisor_cpu'],'supervisor and controller CPU alias')
    require(all(row['resources']['controller_stack']['owner_cpu']==c['controller_cpu'] for row in plan['captures']), 'plan/controller affinity differs')
    continuation_lineage(plan,scope,d['admission'],program_root=c['program_root'],
                         admission_sha256=digest(raw['admission']))
    return d,family,limits(plan,proof,args.address_space_bytes,args.memlock_bytes)

def isolation(c,d):
    path=Path(c['files']['isolation_operator']['path'])
    spec=importlib.util.spec_from_file_location('owned_formal_isolation',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    pre=d['isolation_prestate']
    module.configure(pre)
    require(pre['operator_script_sha256']==c['files']['isolation_operator']['sha256']
            and pre['source_revision']==d['plan']['source_revision']
            and pre['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            and pre['partition_path']==str(module.CG),'qualified isolation prestate differs')
    require(d['clock_complete']['both_pairs_passed'] is True,'actual near/far clocks not complete')
    require(d['q15_result']['terminal_state']=='Q15_W_RESTORED_COMPLETE'
            and d['q15_result']['restoration_verified'] is True and d['q15_result']['quarantined'] is False,'Q15-W restoration not complete')
    require(c['controller_cpu'] in module.RESERVED and c['supervisor_cpu'] in module.HOUSEKEEPING,'explicit owner CPU partition mismatch')
    # Restore receipt goes to this NEW launch directory, never overwrites clocks.
    module.Q=Path(c['launch_root'])
    return module

def prepare_signature(c):
    sys.path.insert(0,str(Path(c['repository_root'])/'tools'))
    import stage17_operational_cli_v18 as cli
    return cli.verify_formal_signature(repository_root=Path(c['repository_root']),
        journal=cli.base.latest_journal(Path(c['evidence_root'])),journal_directory=Path(c['evidence_root'])/'journal',
        operational_evidence_root=Path(c['evidence_root']),authorization_path=Path(c['files']['authorization']['path']),
        signature_path=Path(c['files']['signature']['path']),pilot_archive=Path(c['archive']),pilot_sidecar=Path(c['sidecar']))

def owner_check(c,args):
    """Bounded read-only admission under the same trusted owner credentials."""
    command=setpriv_command(c,args,mode='owner-check')
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True,close_fds=True)
    try:
        stdout,stderr=process.communicate(timeout=180)
        require(len(stdout)+len(stderr)<=1024*1024,'owner check console exceeds bound')
        require(process.returncode==0,'owner admission failed: '+stderr.decode(errors='replace')[:4096])
        result=json.loads(stdout)
        require(type(result) is dict and result.get('execution_authority') is False,
                'owner admission result differs')
        require(result.get('configuration_sha256')==args.config_sha256 and result.get('owner_uid')==c['uid'],
                'owner admission identity differs')
        return result
    finally:
        # This is only our fresh session, never the formal worker/supervisor.
        if process.returncode is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        process.wait(timeout=10)
        process.stdout.close();process.stderr.close()


def checks(c,args):
    if os.geteuid()==0:
        documents(c,args)  # Recheck bound setpriv/Python images before credential handoff.
        return owner_check(c,args)
    require(os.getresuid()==(c['uid'],)*3 and os.getresgid()==(c['gid'],)*3 and not os.getgroups(),
            'read-only checks require trusted owner credentials')
    require(all(int(status()[key],16)==CAP_MASK for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),
            'read-only owner capability mask differs')
    d,family,requested=documents(c,args);iso=isolation(c,d)
    state=iso.isolated_state()
    iso.verify_remaining_lifetime(d['isolation_prestate']['prestate'],
        d['plan']['budget']['watchdog_ns'],d['plan']['budget']['cleanup_ns'])
    require(state['partition']['cgroup.procs']=='' and 'populated 0' in state['partition']['cgroup.events'].splitlines(),'partition not quiescent')
    require(family.is_dir() and not family.is_symlink() and not list(family.iterdir()),'fresh registered empty family required')
    require(family.stat().st_uid==1000,'family is not owned by trusted UID')
    prepare_signature(c)  # Existing qualified read-only admission; no attempt marker.
    import stage17_fixed_action_executor_v11 as executor
    import stage17_formal_plan_v2 as plans
    extent=plans.validate_plan('Q16a',d['plan'])
    fd=os.open(family,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:observed=executor.live_resources(fd,extent,request=d['request'],deadline_ns=__import__('time').monotonic_ns()+extent.declared.cleanup_ns)
    finally:os.close(fd)
    require(observed['memory_available_bytes']>=requested['required_available_memory_bytes'], 'fresh MemAvailable below family plus prospective headroom')
    return dict(utc=utc(),configuration_sha256=args.config_sha256,owner_uid=os.geteuid(),files=c['files'],requested_limits=requested,resource_observation=observed,
                isolation=state,plan_sha256=c['files']['plan']['sha256'],execution_authority=False)

def cli_command(c):
    return [c['python'],'-B',str(Path(c['repository_root'])/'tools/stage17_operational_cli_v18.py'),'execute-formal',
        '--repository-root',c['repository_root'],'--evidence-root',c['evidence_root'],
        '--authorization',c['files']['authorization']['path'],'--signature',c['files']['signature']['path'],
        '--pilot-archive',c['archive'],'--pilot-sidecar',c['sidecar']]

def self_command(args,mode):
    return [sys.executable,'-B',str(Path(__file__).resolve()),'--'+mode,'--config',str(args.config),
            '--config-sha256',args.config_sha256,'--address-space-bytes',str(args.address_space_bytes),
            '--memlock-bytes',str(args.memlock_bytes)]

def setpriv_command(c,args,mode='inner'):
    caps='-all,'+','.join('+'+name for name in CAP_NAMES)
    return [c['setpriv'],'--reuid=1000','--regid='+str(c['gid']),'--clear-groups',
            '--bounding-set='+caps,'--inh-caps='+caps,'--ambient-caps='+caps,
            *([c['python']]+self_command(args,mode)[1:])]

def status():return {k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)}

def validate_identity(c,args,observed):
    require(observed['uid']==[1000]*3 and observed['gid']==[c['gid']]*3 and not observed['groups'],'UID/GID/groups differ')
    require(observed['as']==[args.address_space_bytes]*2 and observed['memlock']==[args.memlock_bytes]*2,'finite limits differ')
    require(observed['affinity']==[c['controller_cpu']],'outer controller affinity differs')
    require(all(int(observed['status'][key],16)==CAP_MASK for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'outer parent capability mask differs')

def cleanup_context(c):
    # Snapshot only the exact reviewed restoration operator and prestate. Keep
    # this in memory before checks: later plan/auth/receipt errors must not
    # prevent restoring our owned empty partition.
    operator=read_bound(c['files']['isolation_operator'])
    pre=json.loads(read_bound(c['files']['isolation_prestate']))
    require(pre['operator_script_sha256']==digest(operator), 'restoration operator binding differs')
    require(pre['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'restoration boot differs')
    module=__import__('types').ModuleType('owned_formal_cleanup')
    module.__file__=c['files']['isolation_operator']['path']
    exec(compile(operator,c['files']['isolation_operator']['path'],'exec'),module.__dict__)
    module.configure(pre)
    require(pre['partition_path']==str(module.CG) and pre['source_revision']==module.REVISION, 'restoration scope differs')
    module.Q=Path(c['launch_root'])
    return module,pre['prestate']

def restore(c,context):
    iso,prestate=context
    if iso.CG.exists():
        require(iso.read(iso.CG/'cgroup.procs')=='' and 'populated 0' in iso.read(iso.CG/'cgroup.events').splitlines(),'live/unrelated partition task: restoration forbidden')
    iso.restore(prestate)
    result=json.loads((Path(c['launch_root'])/'restoration.json').read_bytes())
    require(result['verified'] is True and result['partition_absent'] is True,'owned isolation restoration unverified')
    return result

def require_intent(c,args):
    intent=json.loads(bytes_at(Path(c['launch_root'])/'launch-intent.json'))
    require(intent['configuration_sha256']==args.config_sha256
            and intent['address_space_bytes']==args.address_space_bytes
            and intent['memlock_bytes']==args.memlock_bytes
            and intent['command']==cli_command(c),'one-shot intent binding differs')

def handlers(callback):
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,callback)

def interrupted(number,frame):raise RuntimeError('launcher signal '+str(number))

def supervise(c,args):
    require_intent(c,args)
    context=cleanup_context(c)
    child=None;code=None;reaped=False;errors=[];family=None
    handlers(interrupted)
    try:
        os.sched_setaffinity(0,{c['supervisor_cpu']})
        _,family,_=documents(c,args)
        retain(c,'supervisor-prelaunch.json',checks(c,args))
        child=subprocess.Popen(self_command(args,'owner'),stdin=subprocess.DEVNULL,start_new_session=True)
        retain(c,'child-pid.json',dict(pid=child.pid,supervisor_pid=os.getpid(),utc=utc()))
        code=child.wait();reaped=True
    except BaseException as error:errors.append(repr(error))
    finally:
        handlers(lambda n,f:errors.append('signal during cleanup '+str(n)))
        if child is not None and not reaped:
            try:
                while True:
                    try:code=child.wait();reaped=True;break
                    except InterruptedError:continue  # Same child reap, never relaunch.
            except BaseException as error:errors.append('wait/reap failed: '+repr(error))
        result=dict(utc=utc(),exit_code=code,child_reaped=reaped,success=False,errors=errors)
        try:
            if family is not None:
                receipts=[family/name for name in ('stage17-q16a-completion-v6.json','stage17-q16a-failure-v6.json') if (family/name).is_file()]
                result['executor_receipts']=[bound(path) for path in receipts]
                if len(receipts)==1:
                    receipt=json.loads(bytes_at(receipts[0]))
                    request=json.loads(read_bound(c['files']['request']))
                    result.update(restoration_status(receipt,attempt_id=request['attempt_id'],
                        request_sha256=c['files']['request']['sha256'],authorization_sha256=c['files']['authorization']['sha256']))
                    result['success']=code==0 and reaped and receipts[0].name.endswith('completion-v6.json') and result['hardware_restoration_verified'] and not errors
        except BaseException as error:errors.append('receipt read failed: '+repr(error));result['success']=False
        try:
            require(child is None or reaped,'child not reaped; no restoration')
            result['partition_restoration']=restore(c,context)
        except BaseException as error:result['restoration_error']=error_record(error);result['success']=False
        retain(c,'supervisor-result.json',result)
    return result

def launch(c,args):
    # A used namespace is never adopted and does not confer cleanup ownership.
    launch_root=Path(c['launch_root']);require(not launch_root.exists(),'launch namespace already used; no retry')
    context=cleanup_context(c)
    launch_root.mkdir(mode=0o700)
    child=None;errors=[]
    handlers(interrupted)
    try:
        os.chown(launch_root,c['uid'],c['gid'])
        observation=checks(c,args)
        retain(c,'launch-intent.json',dict(configuration_sha256=args.config_sha256,checks=observation,
            address_space_bytes=args.address_space_bytes,memlock_bytes=args.memlock_bytes,command=cli_command(c)))
        with (launch_root/'session.log').open('xb') as stream:
            child=subprocess.Popen(self_command(args,'supervise'),stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,close_fds=True)
        retain(c,'supervisor-pid.json',dict(pid=child.pid,utc=utc()))
        print('SUPERVISOR_STARTED',child.pid)
    finally:
        handlers(lambda n,f:errors.append('signal during launch cleanup '+str(n)))
        # Once spawned, the detached supervisor owns its one child and cleanup,
        # even if this parent's PID receipt failed. Never launch a second child.
        if child is None:
            result=dict(utc=utc(),errors=errors)
            try:result['partition_restoration']=restore(c,context)
            except BaseException as error:result['restoration_error']=error_record(error)
            retain(c,'prelaunch-cleanup.json',result)

def main():
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    for name in ('check','launch','supervise','owner','inner','owner-check'):mode.add_argument('--'+name,action='store_true',help=argparse.SUPPRESS if name in ('supervise','owner','inner','owner-check') else None)
    parser.add_argument('--config',type=Path,required=True);parser.add_argument('--config-sha256',required=True)
    parser.add_argument('--address-space-bytes',type=int,required=True);parser.add_argument('--memlock-bytes',type=int,required=True)
    args=parser.parse_args();c=read_config(args)
    if args.owner_check:
        require(os.geteuid()==c['uid'],'owner check must run after credential handoff')
        resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
        print(json.dumps(checks(c,args),sort_keys=True));return
    if args.inner:
        d,_,_=documents(c,args)
        observed=dict(uid=list(os.getresuid()),gid=list(os.getresgid()),groups=os.getgroups(),status=status(),
            affinity=sorted(os.sched_getaffinity(0)),**{'as':list(resource.getrlimit(resource.RLIMIT_AS)),
            'memlock':list(resource.getrlimit(resource.RLIMIT_MEMLOCK))})
        validate_identity(c,args,observed)
        require_intent(c,args)
        prepare_signature(c)
        retain(c,'launch-readback.json',dict(utc=utc(),observed=observed,exec_argv=cli_command(c),configuration_sha256=args.config_sha256))
        argv=cli_command(c);os.execv(argv[0],argv)
    require(os.geteuid()==0,'root entry required for finite limits/credential handoff')
    os.sched_setaffinity(0,{c['supervisor_cpu']})
    if args.check:print(json.dumps(checks(c,args),sort_keys=True));return
    if args.owner:
        require_intent(c,args)
        d,_,_=documents(c,args);iso=isolation(c,d)
        require(int(status()['CapBnd'],16)&CAP_MASK==CAP_MASK,'required capabilities unavailable')
        resource.setrlimit(resource.RLIMIT_AS,(args.address_space_bytes,)*2)
        resource.setrlimit(resource.RLIMIT_MEMLOCK,(args.memlock_bytes,)*2)
        iso.write_control(iso.CG/'cgroup.procs',str(os.getpid()))
        os.sched_setaffinity(0,{c['controller_cpu']})
        argv=setpriv_command(c,args);os.execv(argv[0],argv)
    if args.supervise:supervise(c,args);return
    launch(c,args)

if __name__=='__main__':main()
