"""D288 finite prefix/qualification/94-capture/restoration/suffix supervisor.

Only --run starts the one owner-approved day. --software-check cannot start it.
The frozen owned-process and isolation cores remain byte-identical.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import traceback
import types

import stage17_q16c_continuation_operator_v1 as io

NS=10**9
CORE='47e819dbcd6110d5b356d091e706141131efa5938b0ae0740059efc4d3cb1416'
ISOLATION='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-30')
ROLES={'prefix':3600,'qualification':7200,'construct':1200,'sign-collect':24860,'restoration':2400,'suffix':3600}


def module(name,b):
    io.require(name not in sys.modules,'fresh bound module '+name)
    m=types.ModuleType(name);m.__file__=b['path'];sys.modules[name]=m
    exec(compile(io.read(b),b['path'],'exec'),m.__dict__)
    return m


def configure(args):
    io.require(sys.flags.optimize==0,'assertion-dependent qualified operators require normal Python mode')
    c=io.document(dict(path=str(args.configuration),size_bytes=args.configuration.stat().st_size,sha256=args.configuration_sha256))
    io.require(c['execution_authority'] is False and c['phase18_authority'] is False,'no configuration authority')
    io.require(Path(c['evidence_root'])==E and c['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'one fresh E30 namespace and original boot')
    io.require(c['supervisor_unit']=='cpu-prefetch-d288-v30-1.service','one dedicated finite root study unit')
    io.require(c['operator_sources'][Path(__file__).name]==io.binding(Path(__file__).resolve()),'actual root driver')
    for b in c['operator_sources'].values():io.read(b)
    inventory=io.document(c['operator_inventory'])
    io.require(inventory['sources']==c['operator_sources'],'complete actual cold operator bindings')
    for role,key in (('operator_sources','operator_inventory'),('prefix_validation_packet','prefix_packet'),
                     ('prospective_continuation_inputs','prospective_inputs'),('software_checks','software_checks'),
                     ('original_plan','original_plan'),('original_failure','original_failure'),
                     ('candidate_inventory','candidate_inventory'),('candidate_worker','worker')):
        io.require(c['window_bindings'][role]==c[key],'actual prepared window role '+role)
    for key in ('prospective_inputs','prefix_packet','software_checks','original_plan','original_failure','original_context',
                'incident_reuse_inputs','native_geometry','overlay','operator_inventory','old_configuration'):
        io.read(c[key])
    for b in c['original_scientific_packet'].values():io.read(b)
    inventory=io.document(c['candidate_inventory'])
    io.require(inventory['source_revision']==c['source_revision'],'actual native source identity')
    io.require(c['ownership_core']['sha256']==CORE and c['isolation_core']['sha256']==ISOLATION,'frozen recovery cores')
    h=module('d288_owned_process_core',c['ownership_core'])
    return c,h


def online():
    cpus=set()
    for item in Path('/sys/devices/system/cpu/online').read_text().strip().split(','):
        a=item.split('-');cpus.update(range(int(a[0]),int(a[-1])+1))
    return cpus


def owner(args,c,h):
    intent=io.document(io.binding(E/'d288-study-1/intent.json'))
    io.require(os.getppid()==intent['supervisor_pid'] and h.start_ticks(os.getppid())==intent['supervisor_start_ticks']
        and intent['configuration_sha256']==args.configuration_sha256,'dedicated live root owner')
    prospective=io.document(c['prospective_inputs']);native=args.role in ('construct','sign-collect')
    memory=prospective['budget']['memory_bytes'] if native else 16*1024**3
    locked=max(row['resources']['total_mapping_bytes'] for row in prospective['captures']) if native else 8*1024**2
    cpus={2} if native else online()
    if args.owner:
        io.require(os.geteuid()==0 and len(list(Path('/proc/self/task').iterdir()))==1,'single-thread root handoff')
        resource.setrlimit(resource.RLIMIT_AS,(memory,)*2);resource.setrlimit(resource.RLIMIT_MEMLOCK,(locked,)*2)
        if native:
            cg=Path(c['cgroup']);io.require((cg/'cgroup.procs').read_text().strip()=='','empty qualified partition')
            (cg/'cgroup.procs').write_text(str(os.getpid())+'\n')
        os.sched_setaffinity(0,cpus)
        names=h.CAP_NAMES if native else ('sys_ptrace',);caps='-all,'+','.join('+'+n for n in names)
        argv=['/usr/bin/setpriv','--reuid=1000','--regid=1000','--clear-groups','--bounding-set='+caps,
            '--inh-caps='+caps,'--ambient-caps='+caps,sys.executable,'-B',str(Path(__file__).resolve()),'--inner',
            '--role',args.role,'--configuration',str(args.configuration),'--configuration-sha256',args.configuration_sha256,
            '--deadline-ns',str(args.deadline_ns)]
        if args.role=='sign-collect':
            # A new read-only open, never a duplicate of the root's lock FD.
            fd=os.open('/run/cpu-prefetch-locked-compaction-v1.lease',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            os.set_inheritable(fd,True);argv+=['--witness-fd',str(fd)]
        os.execv(argv[0],argv)
    io.require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(),'exact evidence owner')
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    mask=h.CAP_MASK if native else h.ANALYSIS_CAP_MASK
    io.require(all(int(status[k].strip(),16)==mask for k in ('CapInh','CapPrm','CapEff','CapBnd','CapAmb')),'exact role capabilities')
    io.require(os.sched_getaffinity(0)==cpus and resource.getrlimit(resource.RLIMIT_AS)==(memory,)*2
        and resource.getrlimit(resource.RLIMIT_MEMLOCK)==(locked,)*2,'actual role placement and limits')
    io.require(time.monotonic_ns()<args.deadline_ns<=intent['complete_deadline_ns'],'original finite role deadline')
    if args.role=='prefix':
        invocation=io.binding(E/'d288-prefix-invocation.json')
        argv=[sys.executable,'-B',c['operator_sources']['stage17_q16c_prefix_operator_v1.py']['path'],'validate',
            '--configuration',invocation['path'],'--configuration-sha256',invocation['sha256'],'--deadline-ns',str(args.deadline_ns)]
    else:
        argv=[sys.executable,'-B',c['operator_sources']['stage17_q16c_continuation_operator_v1.py']['path'],args.role,
            '--configuration',str(args.configuration),'--configuration-sha256',args.configuration_sha256,'--deadline-ns',str(args.deadline_ns)]
        if args.role=='sign-collect':argv+=['--witness-fd',str(args.witness_fd)]
    os.execv(argv[0],argv)


def sign_window(c):
    sys.path.insert(0,str(Path(c['repository_root'])/'tools'))
    import stage17_q16c_execution_window_v3 as window
    output=E/'d288-execution-window-1';io.require(not output.exists(),'one new window; no reset or retry')
    output.mkdir(mode=0o700);os.chown(output,1000,1000)
    start=time.monotonic_ns()
    record=dict(schema_version=window.SCHEMA,execution_window_id=window.IDENTITY,decision_id='D288',
        source_revision=c['source_revision'],worker_sha256=c['worker']['sha256'],boot_id=c['boot_id'],stand_id='CPU-PREFETCH-V5',
        started_monotonic_ns=start,global_deadline_ns=start+86400*NS,
        started_at_utc=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z'),bindings=c['window_bindings'],
        automatic_retries=0,new_windows_allowed=0,execution_authority=False,phase18_authority=False,
        **{phase+'_seconds':seconds for phase,seconds in window.PHASES})
    window.validate(record,now=start,phase='prefix_validation',expected_source=c['source_revision'],
        expected_worker=c['worker']['sha256'],expected_boot=c['boot_id']);window.verify_bindings(record)
    path=output/'window.json'
    with path.open('xb') as f:f.write(window.canonical(record));f.flush();os.fsync(f.fileno())
    os.chown(path,1000,1000)
    signed=subprocess.run(['runuser','-u','omaltsev','--','ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519',
        '-n','stage17-owner-acceptance',str(path)],capture_output=True,timeout=30)
    io.save(output/'signing-result.json',dict(exit_code=signed.returncode,stdout=signed.stdout.decode(errors='replace'),stderr=signed.stderr.decode(errors='replace')))
    io.require(signed.returncode==0,'actual owner window signature')
    proof=dict(manifest=io.binding(path),signature=io.binding(Path(str(path)+'.sig')))
    io.save(E/'execution-window-proof.json',proof)
    io.save(E/'d288-prefix-invocation.json',dict(schema_version='cpu-prefetch-stage17-d288-prefix-invocation/1',
        prefix_packet=c['prefix_packet'],execution_window_proof=proof,execution_authority=False,phase18_authority=False))
    return record


def run(args,c,h):
    io.require(os.geteuid()==0 and len(list(Path('/proc/self/task').iterdir()))==1 and not h.descendants(os.getpid()),
        'dedicated root supervisor')
    h.subreaper();os.sched_setaffinity(0,{3})
    study=E/'d288-study-1';study.mkdir(mode=0o700);os.chown(study,1000,1000)
    # All static packet/resource gates precede the actual prefix clock.
    io.require(not (E/'d288-execution-window-1').exists(),'unconsumed one-window namespace')
    available=next(line for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    io.require(int(available.split()[1])*1024>=112*1024**3,'actual analysis memory reserve')
    v=os.statvfs(E);io.require(v.f_bavail*v.f_frsize>=512*1024**3+256*1024**3+16*1024**3,'actual shared workspace/scratch/reserve')
    sys.path.insert(0,str(Path(c['repository_root'])/'tools'))
    import stage17_hardware_recovery_v1 as hardware
    prestate=tuple((cpu,hardware._read(cpu)) for cpu in (0,1,8))
    io.save(study/'msr-prestate.json',dict(mapping_id=hardware.MAPPING_ID,prestate=[dict(cpu=cpu,complete_value_hex=f'{value:016x}')
        for cpu,value in prestate],observed_monotonic_ns=time.monotonic_ns(),execution_authority=False))
    service_binding=None
    if 'supervisor_unit' in c:
        membership=Path('/proc/self/cgroup').read_text().strip()
        io.require(membership.startswith('0::/'),'actual unified root service cgroup')
        service=Path('/sys/fs/cgroup')/membership[4:]
        io.require(service.name==c['supervisor_unit'],'root process outside its dedicated study unit')
        s=service.stat(follow_symlinks=False)
        service_binding=dict(path=str(service),identity=[s.st_dev,s.st_ino])
    record=sign_window(c);start=record['started_monotonic_ns'];complete=start+42860*NS
    intent=dict(supervisor_pid=os.getpid(),supervisor_start_ticks=h.start_ticks(os.getpid()),configuration_sha256=args.configuration_sha256,
        started_monotonic_ns=start,complete_deadline_ns=complete,global_deadline_ns=record['global_deadline_ns'],automatic_retries=0,
        execution_authority=False,phase18_authority=False)
    if service_binding is not None:
        intent['root_service_cgroup']=service_binding
        intent['root_argv']=[str(Path(__file__).resolve()),*sys.argv[1:]]
    io.save(study/'intent.json',intent)
    result=dict(success=False,errors=[],phases=[],execution_authority=False,phase18_authority=False)
    active=None;guard=None;clock=None;restored=False
    def interrupted(n,f):raise RuntimeError('D288 supervisor signal '+str(n))
    previous={s:signal.signal(s,interrupted) for s in (signal.SIGTERM,signal.SIGINT,signal.SIGHUP)}
    def snapshot(owned):
        rows=owned.observe()
        value=dict(supervisor_pid=os.getpid(),supervisor_start_ticks=h.start_ticks(os.getpid()),
            configuration_sha256=args.configuration_sha256,owner_pid=owned.process.pid,owner_start_ticks=owned.leader_ticks,
            processes=[dict(pid=pid,start_ticks=ticks) for pid,ticks in sorted(rows.items())],observed_monotonic_ns=time.monotonic_ns())
        p=study/'owned-process-snapshot.json';tmp=study/'owned-process-snapshot.tmp'
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(fd,'wb') as f:f.write(json.dumps(value,sort_keys=True).encode());f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    def command(role,deadline):
        nonlocal active
        io.require(time.monotonic_ns()<deadline<=complete,'original role ceiling')
        argv=[sys.executable,'-B',str(Path(__file__).resolve()),'--owner','--role',role,'--configuration',str(args.configuration),
            '--configuration-sha256',args.configuration_sha256,'--deadline-ns',str(deadline)]
        phase=dict(role=role,started_monotonic_ns=time.monotonic_ns(),deadline_ns=deadline)
        try:
            with (study/(role+'.log')).open('xb') as log:
                active=h.OwnedProcess(argv,log,{(c['worker']['size_bytes'],c['worker']['sha256'])},protect_native=role=='sign-collect')
                phase['pid']=active.process.pid;last=0
                while active.process.poll() is None:
                    io.require(time.monotonic_ns()<deadline,'finite '+role+' deadline')
                    if time.monotonic_ns()-last>=NS:snapshot(active);last=time.monotonic_ns()
                    time.sleep(.1)
                code=active.wait(deadline);phase.update(exit_code=code,leader_reaped=True)
                io.require(code==0,role+' failed');active=None
        finally:
            phase['completed_monotonic_ns']=time.monotonic_ns();io.save(study/(role+'-result.json'),phase);result['phases'].append(phase)
    def restore_owned():
        report=dict(verified=False,errors=[])
        try:
            io.require(not h.descendants(os.getpid()),'owned children must be reaped before restoration')
            cg=Path(c['cgroup'])
            io.require(not cg.exists() or (cg/'cgroup.procs').read_text().strip()=='','native partition must be empty before MSR restoration')
            if guard is not None:hardware.restore(prestate)
            else:hardware.verify(prestate)
            if clock is not None:
                pre=clock.preparation();receipt=clock.Q/'restoration.json'
                if not receipt.exists():clock.restore(pre['prestate'])
                io.require(io.document(io.binding(receipt))['verified'] is True and not clock.CG.exists()
                    and clock.root_state()==pre['prestate']['root'],'actual partition/root restoration')
                for name,before in pre['prestate']['maintenance_before'].items():
                    actual=clock.ISO.systemd_state(name)
                    io.require(actual['UnitFileState']==before['UnitFileState'] and (name not in clock.ISO.TIMER_SERVICES
                        or actual['ActiveState']==before['ActiveState']),'actual maintenance restoration')
                report['receipt']=io.binding(receipt)
            if guard is not None:guard.restore()
            report.update(verified=True,msr_readback=hardware.verify(prestate),compaction_restored=guard is None or
                guard.control.read()==guard.intent['observed_prestate'])
        except BaseException as error:report['errors'].append(repr(error))
        out=E/'q16c-study-1';out.mkdir(mode=0o700,exist_ok=True);os.chown(out,1000,1000)
        io.save(out/'partition-restoration.json',report)
        return report['verified']
    try:
        command('prefix',start+3600*NS)
        prefix=io.document(io.binding(E/'q16c-prefix-analysis-1/accepted-prefix.json'))
        io.require(prefix['all_required_reports_valid'] is True and prefix['reused_capture_ordinals']==list(range(86)), 'all86 before qualification')
        import stage17_locked_compaction_guard_v1 as controls
        import stage17_q16c_compaction_integration_v2 as guarded
        guard=controls.Guard(E/'platform-guard-1',deadline_ns=start+36860*NS);guard.__enter__()
        # Root retains write ownership; the evidence owner can traverse only
        # to the separately published, hash-bound read-only witness.
        os.chmod(guard.root,0o711)
        description,fd=guarded.export_witness(guard)
        try:io.save(E/'platform-guard-1/witness.json',description)
        finally:os.close(fd)
        qualification_start=time.monotonic_ns()
        io.save(E/'continuation-window-1.json',dict(qualification_deadline_monotonic_ns=qualification_start+7200*NS,
            started_monotonic_ns=start,global_deadline_ns=record['global_deadline_ns'],new_window=False))
        packet=Path(c['qualification_packet']);sys.path.insert(0,str(packet))
        import run_qualification_v30 as qualification
        inventory=qualification.verify_packet(packet,c['qualification_inventory']['sha256'],installed=True)
        finite=io.document(io.binding(packet/'finite-qualification-plan.json'))
        q=qualification.Packet(inventory,finite)
        q.step('v30-ext001-execute.py');q.step('v30-admit-002-003-006.py')
        import run_clock_qualification_v30 as isolation
        clock=isolation;q.qualify(clock)
        for s in previous:signal.signal(s,interrupted)
        io.save(E/'qualification-family-complete-1.json',dict(success=True,formal_capture_started=False,isolation_retained_for_formal=True))
        guard.verify();hardware.verify(prestate)
        command('construct',min(time.monotonic_ns()+1200*NS,complete-(24860+2400+3600)*NS))
        guard.verify();command('sign-collect',min(time.monotonic_ns()+24860*NS,complete-(2400+3600)*NS))
        prepared=io.document(io.binding(Path(c['output_root'])/'prepared.json'));request=io.document(prepared['request'])
        native=Path(request['evidence_root_binding']['absolute_path'])/'stage17-q16c-completion-v6.json'
        restoration=module('d288_terminal_recovery',c['terminal_reader'])
        observed=restoration.restoration_status(io.document(io.binding(native)),attempt_id=request['attempt_id'],
            request_sha256=prepared['request']['sha256'],authorization_sha256=prepared['authorization']['sha256'],
            expected_prestate=request['action_inputs']['hardware_control']['prestate'])
        io.require(observed['executor_completed'] and observed['hardware_restoration_verified'],'actual complete native recovery')
        result['native_terminal']=dict(binding=io.binding(native),**observed)
    except BaseException as error:
        result['errors'].append(repr(error));result['traceback']=traceback.format_exc(limit=20)[-32768:]
    finally:
        for s in previous:signal.signal(s,lambda n,f:result['errors'].append('signal during recovery '+str(n)))
        if active is not None:
            try:active.stop(min(complete,time.monotonic_ns()+2400*NS));io.require(not active.forced,'forced cleanup retained as failure')
            except BaseException as error:result['errors'].append('owned cleanup '+repr(error))
        # Signing can publish an actual request before a later setup failure.
        # Preserve the executor's own terminal/recovery result independently
        # from any additional root restoration; never synthesize completion.
        try:
            p=Path(c['output_root'])/'prepared.json'
            if p.exists():
                prepared=io.document(io.binding(p));request=io.document(prepared['request'])
                root=Path(request['evidence_root_binding']['absolute_path'])
                terminal=[root/('stage17-q16c-'+name+'-v6.json') for name in ('completion','failure')]
                found=[p for p in terminal if p.exists()]
                io.require(len(found)<=1,'conflicting native terminal evidence')
                if found:
                    result['actual_executor_terminal']=io.binding(found[0])
                elif (root/'stage17-q16c-attempt-v6.json').exists():
                    result['errors'].append('native attempt lacks a qualified terminal recovery receipt')
        except BaseException as error:result['errors'].append('terminal evidence inspection '+repr(error))
        # Original bounded restoration forks retain independent recovery failures.
        try:
            io.require(not h.descendants(os.getpid()),'actual root-owned descendants must be gone before restoration fork')
            state=types.SimpleNamespace(budget=types.SimpleNamespace(end=min(complete,time.monotonic_ns()+2400*NS)),
                root=E/'q16c-study-1',result=result,restore=restore_owned)
            state.root.mkdir(mode=0o700,exist_ok=True)
            restored=h.Study.bounded_restore(state);io.require(restored,'bounded actual restoration')
        except BaseException as error:result['errors'].append('restoration '+repr(error))
        if guard is not None:guard.unlock()
    if not result['errors'] and restored:
        try:
            for s in previous:signal.signal(s,interrupted)
            command('suffix',min(time.monotonic_ns()+3600*NS,complete))
            done=io.binding(E/'q16c-analysis-1/finalized.json')
            io.require(io.document(done)['status']=='ALL_180_VALID_DESCRIPTIVE_COMPLETE','actual full composition')
            result.update(success=True,completion=done)
        except BaseException as error:result['errors'].append('suffix '+repr(error))
        finally:
            if active is not None:
                try:active.stop(min(complete,time.monotonic_ns()+120*NS))
                except BaseException as error:result['errors'].append('suffix cleanup '+repr(error))
    for s,handler in previous.items():signal.signal(s,handler)
    result['completed_monotonic_ns']=time.monotonic_ns();io.save(study/'result.json',result)
    io.require(result['success'],'D288 stopped incomplete; no automatic retry')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    for name in ('software-check','run','owner','inner'):mode.add_argument('--'+name,action='store_true')
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--role',choices=('prefix','construct','sign-collect','suffix'))
    p.add_argument('--deadline-ns',type=int);p.add_argument('--witness-fd',type=int);args=p.parse_args()
    c,h=configure(args)
    if args.software_check:
        print(json.dumps(dict(status='STATIC_OPERATOR_INPUTS_VERIFIED',window_started=False,execution_authority=False)),flush=True)
    elif args.owner or args.inner:owner(args,c,h)
    else:run(args,c,h)


if __name__=='__main__':main()
