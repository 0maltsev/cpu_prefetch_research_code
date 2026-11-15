"""One new exact Q16b family: authenticated CLI20, one attempt, bounded cleanup.

--check is read-only. Launch/setup require fresh separately signed Q16b authority.
No signing, qualification, registration, measurement retry, or D243 reuse occurs.
"""
from __future__ import annotations

import argparse, datetime, hashlib, json, os
from pathlib import Path
import resource, signal, stat, subprocess, sys, time, types
import q16b_contract as fixed

CAP_NAMES=('sys_ptrace','sys_rawio','dac_override','perfmon')
CAP_MASK=sum(1<<n for n in (19,17,1,38))
MAX_INPUT_BYTES=128*1024**2
_ADMIN_CACHE=None


"""Operator reporting only: executor receipt shapes remain immutable."""
import re


def restoration_status(receipt, *, attempt_id, request_sha256, authorization_sha256, expected_prestate):
    for name, expected in (("attempt_id", attempt_id), ("request_sha256", request_sha256),
                           ("authorization_sha256", authorization_sha256), ("action_id", "Q16b")):
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
        expected = {row["cpu"]: row["complete_value_hex"] for row in expected_prestate}
        require(set(expected) == {0, 1, 8}, "exact restoration CPU coverage required")
        seen = set()
        for row in readback:
            if (not isinstance(row, dict) or type(row.get("cpu")) is not int
                    or row["cpu"] < 0 or row["cpu"] in seen or row.get("matches") is not True
                    or not isinstance(row.get("expected_hex"), str)
                    or re.fullmatch(r"[0-9a-f]{16}", row["expected_hex"]) is None
                    or row.get("observed_hex") != row["expected_hex"]):
                raise ValueError("invalid hardware restoration readback")
            require(expected.get(row["cpu"]) == row["expected_hex"], "restoration differs from signed prestate")
            seen.add(row["cpu"])
        require(seen == set(expected), "restoration omits CPUs")
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
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and 0<before.st_size<=MAX_INPUT_BYTES,'bounded regular file required')
        raw=stream.read(MAX_INPUT_BYTES+1);after=os.fstat(stream.fileno())
        require(len(raw)==before.st_size,'short input read')
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
    require(c['schema_version']=='software-formal-q16b-launch/1','configuration schema')
    require(c['stage'] in ('launch','prelaunch'),'configuration stage')
    require(set(c['files'])==set(fixed.input_paths(c['stage'])),'exact bound input membership required')
    for name,path in fixed.input_paths(c['stage']).items():
        require(c['files'][name]['path']==path,'fixed input locator differs: '+name)
    for name,path in fixed.paths().items():require(c[name]==path,'fixed root differs: '+name)
    require(c['launcher_sha256']==digest(bytes_at(Path(__file__).resolve())),'reviewed launcher bytes differ')
    require(c['contract_sha256']==digest(bytes_at(Path(fixed.__file__).resolve())),'operator contract differs')
    require(c['setup_helper_sha256']==digest(bytes_at(Path(__file__).resolve().with_name('reapply_isolation_q16b.py'))),'reviewed setup/hardware helper differs')
    require(c['uid']==1000 and c['gid']==1000,'recorded trusted UID/GID required')
    require((c['controller_cpu'],c['supervisor_cpu'])==(2,3),'recorded controller/supervisor placement required')
    require(c['admin_root']==str(fixed.ADMIN),'explicit packet root differs')
    require(c['files']['isolation_operator']['sha256']==fixed.CORE_SHA,'original core changed')
    require(c['setup_scope']==dict(action_id='Q16b',plan_sha256=fixed.PLAN_SHA,
        prior_D243_consumed=True,qualification_repeat=False,automatic_retry=False), 'prospective Q16b-only setup scope required')
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
    require(proof['required_worker_as_bytes']==native and proof['required_family_as_bytes']==family,
            'sizing proof/plan resource mismatch')
    require(as_bytes==native and memlock_bytes==mapped,'limits must equal proof-bound worker/mapping ceilings')
    require(mapped<=native and proof['minimum_native_publication_metadata_peak_bytes']<=native,'native publication exceeds worker ceiling')
    require(proof['archive_staging_bytes']==plan['storage']['archive_staging_bytes']
            and proof['largest_capture_bytes']==max(r['execution_budget']['max_output_bytes'] for r in plan['captures']), 'capture/staging proof differs')
    control=max(row['metadata']['control_bytes'] for row in proof['native_cells'])
    require(len(proof['native_cells'])==60 and {r['cell_ordinal'] for r in proof['native_cells']}==set(range(60)), 'all60 native-cell proof required')
    return dict(operational_memory_reserve_bytes=fixed.OPERATIONAL_MEMORY_RESERVE_BYTES,
                required_available_memory_bytes=family+fixed.OPERATIONAL_MEMORY_RESERVE_BYTES,address_space_bytes=as_bytes,
                memory_lock_bytes=memlock_bytes,required_worker_as_bytes=native,
                required_family_as_bytes=family,max_native_mapping_bytes=mapped,
                native_max_control_bytes=control,controller_address_space_bytes=plan['budget']['controller_memory_bytes'])

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

def documents(c,args):
    raw={name:read_bound(value) for name,value in c['files'].items()}
    d={name:json.loads(value) for name,value in raw.items() if name not in ('signature','isolation_operator')}
    plan=d['plan'];proof=d['preparation'];request=d['request'];storage=plan['storage']
    plan_sha=digest(raw['plan'])
    require(plan_sha==fixed.PLAN_SHA and raw['plan']==canonical(plan),'frozen exact canonical candidate-3 required')
    require(plan['schema_version']=='cpu-prefetch-stage17-formal-service-plan/2' and plan['action_id']=='Q16b', 'only new archived Q16b permitted')
    require(plan['source_revision']==fixed.SOURCE and plan['clean_source'] is True,'qualified native source differs')
    require(proof['plan']['sha256']==plan_sha and proof['plan']['size_bytes']==len(raw['plan']), 'actual preparation plan binding differs')
    require(proof['status']=='COLD_NATIVE_SIZED_CANDIDATE' and proof['execution_authority'] is False,'preparation is not execution authority')
    require(proof['planned_captures']==len(plan['captures'])==3540 and plan['repetitions_per_cell']==59
            and plan['measurement_ns']==1000000000 and all(r['capture']['warmup_ns']==5000000000 for r in plan['captures']), 'frozen duration/capture design differs')
    require(proof['required_watchdog_ns']==plan['budget']['watchdog_ns']==fixed.WATCHDOG_NS,'family watchdog differs')
    require(d['isolation_config']==fixed.isolation_config(plan),'new finite keeper configuration differs')
    require(request['action_id']=='Q16b' and request['schema_version']=='cpu-prefetch-stage17-fixed-action-request/6','fresh request action/version')
    require(request['action_inputs']['plan']==plan,'request carries different plan')
    require(request['action_inputs']['hardware_control']==proof['hardware_control'],'signed hardware prestate differs from preparation')
    require(digest(raw['handoff'])==proof['q16a_handoff']['sha256'],'authenticated Q16a handoff differs')
    scope=d['scope'];family=Path(c['program_root'])/'working'/plan_sha
    require(digest(raw['scope'])==storage['program_scope_sha256']==fixed.SCOPE_SHA,'shared program scope differs')
    require(scope['prospective_admission_sha256']==digest(raw['admission']),'original prospective admission differs')
    require(digest(raw['profile'])==storage['implementation_profile_sha256'],'qualified archive implementation differs')
    require(request['evidence_root_binding']['absolute_path']==str(family),'request is not the new registered family')
    auth=d['authorization'];binding=auth['request_binding']
    require(binding==c['files']['request'],'authorization request binding differs')
    require(auth['action_id']=='Q16b' and auth['one_attempt'] is True and auth['retry_allowed'] is False
            and auth['stop_first'] is True and auth['retain_partial'] is True and auth['stage18_authority'] is False,'one-shot stop-first authority required')
    manifest=d['manifest']
    require(manifest['bundle_profile']=='STAGE17-PILOT-CANDIDATE-BUNDLE-v26'
            and manifest['source_archive']['source_revision']==fixed.SOURCE
            and manifest['source_archive']['source_dirty'] is False,'clean qualified release differs')
    worker=manifest['stage17_fixed_action_runtime'];actual=bound(Path(c['bundle_root'])/worker['member_path'])
    require(actual['sha256']==worker['sha256']==fixed.WORKER_SHA and actual['size_bytes']==worker['size_bytes'],'qualified worker changed')
    py=bound(Path(c['python']))
    require((py['size_bytes'],py['sha256'])==(d['profile']['python']['size_bytes'],d['profile']['python']['sha256']), 'stand Python/profile differs')
    require(d['profile']['python']['location']=='runtime' and d['profile']['python']['path']=='usr/bin/python3.14','runtime-root binding differs')
    for image in (Path(c['python']),Path(actual['path'])):
        require(not image.stat().st_mode&(stat.S_ISUID|stat.S_ISGID) and 'security.capability' not in os.listxattr(image),'exec image changes capability inheritance')
    require(bound(Path(c['setpriv']))==c['setpriv_binding'],'setpriv image differs')
    require(all(row['resources']['controller_stack']['owner_cpu']==2 for row in plan['captures']), 'plan controller affinity differs')
    for row in plan['captures']:
        sources={s['path'] for s in row['monitoring']['environment_sources'] if s['path'].startswith('/sys/fs/cgroup/')}
        require(sources=={str(fixed.PARTITION/name) for name in ('cpuset.cpus','cpuset.cpus.effective','cpuset.cpus.exclusive','cpuset.cpus.partition','cpuset.mems.effective')},'frozen isolation monitor paths differ')
    program_admission_lineage(plan,d['parent_plan'],scope,d['admission'],program_root=c['program_root'],admission_sha256=digest(raw['admission']))
    require(d['capacity_proof']['families']==2 and d['capacity_proof']['program_root']==c['program_root']
            and d['capacity_proof']['scope_sha256']==fixed.SCOPE_SHA and d['capacity_proof']['boot_id']==fixed.BOOT, 'preparation program snapshot differs')
    require(d['clock_complete']['both_pairs_passed'] is True,'qualified near/far clocks incomplete')
    require(d['q15_result']['terminal_state']=='Q15_W_RESTORED_COMPLETE'
            and d['q15_result']['restoration_verified'] is True and d['q15_result']['quarantined'] is False,'Q15-W restoration incomplete')
    require(digest(raw['q15_result'])==proof['hardware_control']['q15_w_result_sha256'],'Q15-W result/prestate binding differs')
    require(d['q15_completion']['restoration_verified'] is True and d['q15_completion']['quarantined'] is False,'Q15-W completion unverified')
    require(d['q15_completion']['runtime_sha256']==fixed.WORKER_SHA and d['q15_completion']['leader_reaped'] is True
            and d['q15_completion']['process_group_gone'] is True,'Q15-W qualified runtime/cleanup differs')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==fixed.BOOT,'same boot required')
    requested=limits(plan,proof,args.address_space_bytes,args.memlock_bytes)
    require(c['requested_limits']==requested,'rendered resource declarations differ from actual proof/plan')
    require(c['files']['parent_plan']['sha256']=='a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7','original program parent plan differs')
    return d,family,requested

def isolation(c,d):
    raw=read_bound(c['files']['isolation_operator'])
    module=types.ModuleType('owned_q16b_isolation');module.__file__=str(fixed.CORE)
    exec(compile(raw,str(fixed.CORE),'exec'),module.__dict__)
    pre=d['isolation_prestate'];module.configure(pre)
    require(pre['operator_config']==d['isolation_config'] and pre['prestate']['operator_config']==d['isolation_config'], 'isolation did not use new Q16b finite configuration')
    require(pre['operator_script_sha256']==fixed.CORE_SHA and pre['source_revision']==fixed.SOURCE
            and pre['boot_id']==fixed.BOOT and pre['partition_path']==str(fixed.PARTITION),'Q16b isolation prestate differs')
    handoff=d['isolation_readback']
    require(handoff['action_id']=='Q16b' and handoff['plan_sha256']==fixed.PLAN_SHA
            and handoff['isolation_reapplied'] is True and handoff['qualification_repeated'] is False
            and handoff['isolation_prestate_sha256']==c['files']['isolation_prestate']['sha256']
            and handoff['configuration_sha256']==c['files']['isolation_config']['sha256']
            and handoff['setup_scope']==c['setup_scope'],'new Q16b setup receipt differs')
    module.Q=Path(c['launch_root'])
    return module

def admin(c):
    global _ADMIN_CACHE
    raw=read_bound(c['admin_bootstrap'])
    require(c['admin_bootstrap']['path']==str(fixed.ADMIN/'stage17_formal_admin_v2.py'), 'packet bootstrap path differs')
    require(c['packet_manifest']['path']==str(fixed.ADMIN/'manifest.json'),'packet manifest path differs')
    manifest=read_bound(c['packet_manifest'])
    packet=json.loads(manifest)
    require(packet['schema_version']==fixed.ADMIN_SCHEMA,'v2 packet schema required')
    rows=packet['files']
    require(type(rows) is list and 4<=len(rows)<=64,'finite complete v2 packet members required')
    members=[r for r in rows if isinstance(r,dict) and r.get('name')==fixed.ADMIN_MODULE+'.py']
    source_sha256=digest(raw)
    require(len(members)==1 and members[0]==dict(name=fixed.ADMIN_MODULE+'.py',
        size_bytes=len(raw),sha256=source_sha256),'bootstrap bytes differ from verified packet member')
    identity=(source_sha256,canonical(c['admin_bootstrap']),canonical(c['packet_manifest']))
    if _ADMIN_CACHE is None:
        require(fixed.ADMIN_MODULE not in sys.modules,'unverified bootstrap already cached')
        module=types.ModuleType(fixed.ADMIN_MODULE);module.__file__=c['admin_bootstrap']['path']
        sys.modules[fixed.ADMIN_MODULE]=module
        try:
            exec(compile(raw,module.__file__,'exec'),module.__dict__)
            activate=module.activate_packet
            require(isinstance(activate,types.FunctionType) and activate.__globals__ is module.__dict__,
                    'compiled bootstrap activation function required')
            code=activate.__code__
            result=activate(c['packet_manifest']['sha256'])
            require(sys.modules.get(fixed.ADMIN_MODULE) is module and module.activate_packet is activate
                    and activate.__code__ is code,'bootstrap identity changed during activation')
        except BaseException:
            if sys.modules.get(fixed.ADMIN_MODULE) is module:
                del sys.modules[fixed.ADMIN_MODULE]
            raise
        _ADMIN_CACHE=(identity,module,activate,code)
        return result
    expected,module,activate,code=_ADMIN_CACHE
    require(identity==expected and sys.modules.get(fixed.ADMIN_MODULE) is module,
            'activated bootstrap binding or module identity changed')
    require(module.activate_packet is activate and activate.__code__ is code
            and activate.__globals__ is module.__dict__,'activated bootstrap function/code identity changed')
    # The same authenticated instance retains v2 provenance across the two
    # prepare_signature calls. v2 rechecks its complete activated closure.
    return module.activate_packet(c['packet_manifest']['sha256'])


def prepare_signature(c):
    cli=admin(c)
    return cli.verify_formal_signature(repository_root=Path(c['repository_root']),
        journal=cli.previous.base.latest_journal(Path(c['evidence_root'])),journal_directory=Path(c['evidence_root'])/'journal',
        operational_evidence_root=Path(c['evidence_root']),authorization_path=Path(c['files']['authorization']['path']),
        signature_path=Path(c['files']['signature']['path']),pilot_archive=Path(c['archive']),pilot_sidecar=Path(c['sidecar']))

def owner_check(c,args):
    """Bounded read-only admission under the same trusted owner credentials."""
    command=setpriv_command(c,args,mode='owner-check')
    process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,start_new_session=True,close_fds=True)
    try:
        stdout,stderr=process.communicate(timeout=600)
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
        documents(c,args)
        return owner_check(c,args)
    require(os.getresuid()==(c['uid'],)*3 and os.getresgid()==(c['gid'],)*3 and not os.getgroups(),'trusted owner credentials required')
    require(all(int(status()[key],16)==CAP_MASK for key in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'owner capability mask differs')
    d,family,requested=documents(c,args)
    require(family.is_dir() and not family.is_symlink() and not list(family.iterdir()),'fresh registered empty Q16b family required')
    require(family.stat().st_uid==1000,'family is not owned by trusted UID')
    prepared=prepare_signature(c)
    require(prepared.request==d['request'] and prepared.authorization==d['authorization'],'fresh admitted inputs differ')
    import stage17_fixed_action_executor_v11 as executor
    import stage17_formal_plan_v2 as plans
    extent=plans.validate_plan('Q16b',d['plan'])
    deadline=time.monotonic_ns()+extent.declared.cleanup_ns
    fd=os.open(family,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:observed=executor.live_resources(fd,extent,request=d['request'],deadline_ns=deadline)
    finally:os.close(fd)
    with executor.open_store(d['request'],deadline) as store:
        accounting=store.physical_accounting()
        require(set(store._families)=={fixed.PLAN_SHA,'a9bef1239ea03d3871e40a0c52a0a3375d1eac7512d299443dd18405e89572f7',
            '91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'},'existing two families plus only new Q16b registration required')
        require(store.reserved_bytes()==0,'pending archive reservation blocks new family')
        require(accounting.quota_bytes>=d['capacity_proof']['physical_usage']['quota_bytes'],'retained program accounting regressed')
        observed['fresh_program_ledger']=vars(store.ledger_binding())
        observed['registered_families']=len(store._families)
        observed['reserved_bytes']=store.reserved_bytes()
    require(observed['memory_available_bytes']>=requested['required_available_memory_bytes'],'fresh MemAvailable below family plus 8GiB operational reserve')
    from reapply_isolation_q16b import hardware
    hardware_observation=hardware(d['plan'],d['preparation']['hardware_control']['prestate'],d['clock_plan']['topology'])
    state=None
    if c['stage']=='launch':
        iso=isolation(c,d);state=iso.isolated_state()
        iso.verify_remaining_lifetime(d['isolation_prestate']['prestate'],d['plan']['budget']['watchdog_ns'],d['plan']['budget']['cleanup_ns'])
        require(state['partition']['cgroup.procs']=='' and 'populated 0' in state['partition']['cgroup.events'].splitlines(),'partition not quiescent')
    else:
        require(not fixed.PARTITION.parent.exists(),'old unit cgroup must be absent before Q16b setup')
        require(not Path('/run/systemd/system',fixed.UNIT).exists(),'old runtime unit file must be absent before Q16b setup')
    # Signature/journal/expiry checked last as well as before read-only observations.
    prepare_signature(c)
    return dict(utc=utc(),configuration_sha256=args.config_sha256,owner_uid=os.geteuid(),files=c['files'],requested_limits=requested,
                resource_observation=observed,hardware_observation=hardware_observation,isolation=state,
                plan_sha256=fixed.PLAN_SHA,execution_authority=False)

def cli_command(c):
    return [c['python'],'-B',c['admin_bootstrap']['path'],'--packet-manifest-sha256',c['packet_manifest']['sha256'],'execute-formal',
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
    require(pre['operator_script_sha256']==digest(operator)==fixed.CORE_SHA, 'restoration operator binding differs')
    require(pre['operator_config']['evidence_root']==str(fixed.ISOLATION)
            and pre['operator_config']==pre['prestate']['operator_config']
            and pre['operator_config']['unit_name']==fixed.UNIT
            and pre['operator_config']['protected_work_ns']==fixed.WATCHDOG_NS+fixed.CLEANUP_NS
            and pre['operator_config']['lifecycle_seconds']==fixed.LIFECYCLE_SECONDS,'cleanup belongs to different setup')
    require(pre['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'restoration boot differs')
    module=__import__('types').ModuleType('owned_formal_cleanup')
    module.__file__=c['files']['isolation_operator']['path']
    exec(compile(operator,c['files']['isolation_operator']['path'],'exec'),module.__dict__)
    module.configure(pre)
    require(pre['partition_path']==str(module.CG)==str(fixed.PARTITION)
            and pre['source_revision']==module.REVISION==fixed.SOURCE, 'restoration scope differs')
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
    require(c['stage']=='launch','launch-stage bindings required')
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
        code=child.wait(timeout=fixed.WATCHDOG_NS/1e9);reaped=True
    except BaseException as error:errors.append(repr(error))
    finally:
        handlers(lambda n,f:errors.append('signal during cleanup '+str(n)))
        if child is not None and not reaped:
            try:
                try:os.killpg(child.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:code=child.wait(timeout=fixed.CLEANUP_NS/1e9)
                except subprocess.TimeoutExpired:
                    errors.append('owner cleanup deadline exceeded; killing owned outer group')
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    code=child.wait(timeout=10)
                reaped=True
            except BaseException as error:errors.append('wait/reap failed: '+repr(error))
        result=dict(utc=utc(),exit_code=code,child_reaped=reaped,success=False,errors=errors)
        try:
            if family is not None:
                receipts=[family/name for name in ('stage17-q16b-completion-v6.json','stage17-q16b-failure-v6.json') if (family/name).is_file()]
                result['executor_receipts']=[bound(path) for path in receipts]
                if len(receipts)==1:
                    receipt=json.loads(bytes_at(receipts[0]))
                    request=json.loads(read_bound(c['files']['request']))
                    result.update(restoration_status(receipt,attempt_id=request['attempt_id'],
                        request_sha256=c['files']['request']['sha256'],authorization_sha256=c['files']['authorization']['sha256'],
                        expected_prestate=request['action_inputs']['hardware_control']['prestate']))
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
    require(c['stage']=='launch','launch-stage bindings required')
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
        checks(c,args)  # Last empty-partition/resource/signature check before entry.
        d,_,_=documents(c,args);iso=isolation(c,d)
        require(int(status()['CapBnd'],16)&CAP_MASK==CAP_MASK,'required capabilities unavailable')
        resource.setrlimit(resource.RLIMIT_AS,(args.address_space_bytes,)*2)
        resource.setrlimit(resource.RLIMIT_MEMLOCK,(args.memlock_bytes,)*2)
        iso.write_control(iso.CG/'cgroup.procs',str(os.getpid()))
        os.sched_setaffinity(0,{c['controller_cpu']})
        argv=setpriv_command(c,args);os.execv(argv[0],argv)
    if args.supervise:
        result=supervise(c,args)
        raise SystemExit(0 if result['success'] else 1)
    launch(c,args)

if __name__=='__main__':main()
