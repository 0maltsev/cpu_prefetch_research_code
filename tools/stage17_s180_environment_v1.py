"""Fixed stand S180 isolation/MSR preparation and independently checked restore.

This is preparation under D310, never scoped admission or measurement authority.
Only the fixed root-owned isolation core and Intel06_3EH CPU0/1/8 mapping exist.
No caller-selected hardware backend, command, register, CPU or recovery value.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import time
import types

import stage17_formal_archive_v1 as archive
import stage17_s180_plan_prepare_v1 as planning
import stage17_s180_resource_plan_v1 as resources

CORE_SHA='49e20041be148142898e46bb6bc72d15cbb4b23859aee12403c5586594358a8a'
CORE_SIZE=23863
UNIT='cpu-prefetch-recovery-s180-1.service'
CG=Path('/sys/fs/cgroup')/UNIT/'reserved'
EVIDENCE=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/s180-d310-1/isolation')
CPUS=(0,1,8)
MSR=0x1a4
MASK=15
NATIVE_REVISION='34247cedab4abe4b44732daae8fdac1700eccffd'
ISOLATION_PREPARATION_NS=120*10**9
_TOKEN=object()


class EnvironmentError(archive.ArchiveError):
    pass


def require(value,message):
    if not value:raise EnvironmentError('S180 environment: '+message)


def _boot():return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def _before(deadline):
    require(time.monotonic_ns()<deadline,'original preparation/restoration deadline expired')


def _window(window,*,cleanup=False):
    require(type(window) is dict and set(window)=={'boot_id','start_monotonic_ns','end_monotonic_ns'},'original window fields')
    start=archive.uint(window['start_monotonic_ns'],'window start',positive=True)
    end=archive.uint(window['end_monotonic_ns'],'window end',positive=True)
    now=time.monotonic_ns()
    require(end-start==planning.DAY_NS and start<=now and (cleanup or now<end) and window['boot_id']==_boot(),
        'original24h window/boot differs')


def _plan(plan):
    require(plan['schema_version']==planning.PLAN and planning.sha(plan['blueprint'])==planning.BLUEPRINT_SHA256
        and plan['source_revision']==NATIVE_REVISION,'exact approved blueprint and frozen native source required')
    require(plan['hardware']['identity']==dict(family=6,model=62),'accepted Intel06_3EH identity required')
    rows=plan['hardware']['prestate'];require(type(rows) is list and len(rows)==3,'complete prestate required')
    require([r['cpu'] for r in rows]==list(CPUS) and all(set(r)=={'cpu','value'} for r in rows),
        'exact CPU0/1/8 prestate required')
    for r in rows:archive.uint(r['cpu'],'CPU');archive.uint(r['value'],'complete prestate')
    require(len(plan['captures'])==180,'complete pilot required')
    names={'cpuset.cpus','cpuset.cpus.effective','cpuset.cpus.exclusive','cpuset.cpus.partition','cpuset.mems.effective'}
    expected={str(CG/n) for n in names}
    for e in plan['captures']:
        observed=[r['path'] for r in e['monitoring']['environment_sources'] if '/cpuset.' in r['path'] and '/reserved/' in r['path']]
        require(len(observed)==5 and set(observed)==expected,'requested monitoring paths differ from actual managed partition')


def _work_ns(plan):
    b=plan['budget']
    native=archive.checked_sum(*(b[k] for k in ('setup_ns','whole_plot_transition_ns','whole_plot_recovery_ns','finalization_ns')),
        *(e['execution_budget']['watchdog_ns'] for e in plan['captures']))
    return archive.checked_sum(native,*(resources.EXTERNAL_TIME[k] for k in
        ('qualification_ns','independent_validation_ns','restoration_and_exit_ns')))


def prospective_config(*,plan,window,operator_revision):
    """Requested finite infrastructure data only; never starts a window/unit."""
    _plan(plan);_window(window)
    require(type(operator_revision) is str and len(operator_revision)==40
        and all(c in '0123456789abcdef' for c in operator_revision),'exact operator source revision required')
    lifecycle=(window['end_monotonic_ns']-time.monotonic_ns()-ISOLATION_PREPARATION_NS)//10**9-2
    work=_work_ns(plan)
    require(lifecycle>0 and work+120*10**9<lifecycle*10**9,'remaining original window cannot cover infrastructure/work/cleanup')
    return dict(unit_name=UNIT,source_revision=operator_revision,boot_id=window['boot_id'],lifecycle_seconds=lifecycle,
        stop_seconds=120,protected_work_ns=work,evidence_root=str(EVIDENCE))


def _load_core():
    path=Path(__file__).with_name('stage17_recovery_isolation_core_v1.py')
    with archive.open_regular(path) as stream:
        st=os.fstat(stream.fileno());raw=stream.read(CORE_SIZE+1)
        require(st.st_uid==0 and not st.st_mode&0o022 and len(raw)==CORE_SIZE
            and hashlib.sha256(raw).hexdigest()==CORE_SHA
            and archive.file_stamp(os.fstat(stream.fileno()))==archive.file_stamp(st),
            'original root-owned frozen isolation source required')
    core=types.ModuleType('_s180_original_isolation');core.__file__=str(path)
    exec(compile(raw,str(path),'exec'),core.__dict__)
    return core


def _cpu_identity(cpu):
    with open('/proc/cpuinfo','rb') as stream:raw=stream.read(2*1024**2+1)
    require(len(raw)<=2*1024**2,'CPU inventory bound')
    found=[]
    for block in raw.decode('ascii').split('\n\n'):
        fields=dict(line.split(':',1) for line in block.splitlines() if ':' in line)
        fields={k.strip():v.strip() for k,v in fields.items()}
        if fields.get('processor')==str(cpu):found.append(fields)
    require(len(found)==1 and found[0].get('vendor_id')=='GenuineIntel'
        and found[0].get('cpu family')=='6' and found[0].get('model')=='62','actual CPU identity differs')


def _open_msr(cpu,writable=False):
    require(type(cpu) is int and cpu in CPUS,'fixed CPU mapping required')
    _cpu_identity(cpu)
    fd=os.open(f'/dev/cpu/{cpu}/msr',(os.O_RDWR if writable else os.O_RDONLY)|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        st=os.fstat(fd);require(stat.S_ISCHR(st.st_mode),'actual MSR character device required')
        return fd,(st.st_dev,st.st_ino,st.st_rdev)
    except BaseException:os.close(fd);raise


def _read_msr(fd):
    raw=os.pread(fd,8,MSR);require(len(raw)==8,'complete fixed MSR read required')
    return int.from_bytes(raw,'little')


class _PreparedEnvironment:
    def __init__(self,*,token,plan,window,core,preparation,devices,affinity,command_state):
        require(token is _TOKEN,'only actual preparation constructs an owned environment')
        self._plan=archive.canonical(plan);self._window=archive.canonical(window)
        self._preparation=archive.canonical(preparation);self._core=core;self._devices=devices
        self._affinity=affinity;self._pid=os.getpid();self._closed=False;self._entry_used=False
        self._deadline=window['end_monotonic_ns']
        self._command_state=command_state
        self._placement_fd=None

    def __enter__(self):
        require(not self._closed,'environment already closed');return self

    def __exit__(self,*exception):
        if not self._closed:
            plan=archive.parse_json(self._plan);window=archive.parse_json(self._window)
            result=self._restore(plan,window)
            require(not result['errors'] and all(result[k] is True for k in
                ('hardware_restoration_verified','cpu_isolation_restoration_verified','maintenance_restoration_verified')),
                'unstarted/aborted environment restoration failed')

    def _guard(self,plan_sha256,*,cleanup=False):
        require(not self._closed and self._pid==os.getpid(),'environment is closed or belongs to another process')
        plan=archive.parse_json(self._plan);window=archive.parse_json(self._window)
        require(planning.sha(plan)==plan_sha256,'environment belongs to another plan')
        _window(window,cleanup=cleanup);return plan,window

    @contextlib.contextmanager
    def native_entry(self,*,plan_sha256):
        """One actual cgroup.procs FD, used only by the native child pre-exec."""
        self._guard(plan_sha256)
        require(not self._entry_used,'environment native placement cannot be reused')
        self._core.isolated_state()
        pre=archive.parse_json(self._preparation)['prestate']
        self._core.verify_remaining_lifetime(pre,_work_ns(archive.parse_json(self._plan))
            -resources.EXTERNAL_TIME['qualification_ns']-resources.EXTERNAL_TIME['restoration_and_exit_ns'],
            resources.EXTERNAL_TIME['restoration_and_exit_ns'])
        require(self._core.identity(CG)==pre['partition_identity']
            and self._core.read(CG/'cgroup.procs')=='','actual owned partition is not empty')
        fd=os.open(CG/'cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self._placement_fd=fd
        try:
            require(self._core.identity(CG)==pre['partition_identity'],'partition changed while opening placement control')
            self._entry_used=True
            yield dict(descriptor=fd,relative_path='/'+UNIT+'/reserved',controller_cpu=2)
        finally:
            if self._placement_fd==fd:os.close(fd);self._placement_fd=None

    def _restore_hardware(self,plan):
        records=[];errors=[]
        for expected in reversed(plan['hardware']['prestate']):
            fd=None;row=dict(cpu=expected['cpu'],expected_value=expected['value'],write_attempted=False,verified=False)
            try:
                _before(self._deadline);require(_boot()==archive.parse_json(self._window)['boot_id'],'boot changed')
                fd,identity=_open_msr(expected['cpu'],True)
                require(identity==self._devices[expected['cpu']],'MSR device identity changed')
                current=_read_msr(fd);row['before_value']=current
                require((current^expected['value'])&~MASK==0,'unrelated MSR bits changed; do not overwrite')
                if current!=expected['value']:
                    row['write_attempted']=True
                    require(os.pwrite(fd,expected['value'].to_bytes(8,'little'),MSR)==8,'complete fixed MSR restore write required')
                row['observed_value']=_read_msr(fd);row['verified']=row['observed_value']==expected['value']
                require(row['verified'],'fixed MSR restore readback differs')
            except BaseException as error:errors.append(dict(stage='hardware',cpu=expected['cpu'],error=str(error)))
            finally:
                if fd is not None:os.close(fd)
                records.append(row)
        return records,errors

    def __call__(self,*,verified,native_cleanup,deadline_ns):
        from stage17_s180_authority_v1 import VerifiedRequest
        require(type(verified) is VerifiedRequest,'original verified request required')
        authorization=archive.parse_json(verified.authorization_bytes)
        plan,window=self._guard(authorization['plan_sha256'],cleanup=True)
        require(archive.canonical(authorization['window_binding'])==self._window
            and deadline_ns<=window['end_monotonic_ns'],'restoration window differs')
        require(native_cleanup is None or (native_cleanup.leader_reaped and native_cleanup.process_group_gone),
            'native cleanup must precede restoration')
        self._deadline=min(self._deadline,deadline_ns)
        return self._restore(plan,window)

    def _restore(self,plan,window):
        _window(window,cleanup=True)
        overrun=time.monotonic_ns()>=self._deadline
        if overrun:self._deadline=time.monotonic_ns()+120*10**9
        self._command_state['deadline']=self._deadline
        if self._placement_fd is not None:
            os.close(self._placement_fd);self._placement_fd=None
        pre=archive.parse_json(self._preparation)
        errors=([dict(stage='operational_deadline',error='original window exhausted; emergency unwind grants no collection authority')]
            if overrun else [])
        hardware=[];isolation=False;maintenance=False
        try:
            # Kernel membership is independent of the supplied process proof.
            if CG.exists():
                require(self._core.identity(CG)==pre['prestate']['partition_identity']
                    and self._core.read(CG/'cgroup.procs')==''
                    and 'populated 0' in self._core.read(CG/'cgroup.events').splitlines(),'live/replaced native partition; do not change MSRs')
            else:require(not CG.parent.exists(),'owned partition vanished with an uncertain unit')
            hardware,hardware_errors=self._restore_hardware(plan);errors.extend(hardware_errors)
        except BaseException as error:errors.append(dict(stage='hardware_quiescence',error=str(error)))
        try:
            self._core.restore(pre['prestate'])
            report=json.loads((self._core.Q/'restoration.json').read_bytes())
            isolation=report.get('partition_absent') is True and report.get('root_restoration_verified') is True
            maintenance=report.get('maintenance_restoration_verified') is True
        except BaseException as error:errors.append(dict(stage='isolation_maintenance',error=str(error)))
        try:
            os.sched_setaffinity(0,self._affinity)
            require(set(os.sched_getaffinity(0))==set(self._affinity),'operator affinity restoration differs')
        except BaseException as error:
            isolation=False;errors.append(dict(stage='affinity',error=str(error)))
        try:
            self._core.retain(self._core.Q/'s180-restoration.json',dict(plan_sha256=planning.sha(plan),
                boot_id=window['boot_id'],hardware_readbacks=hardware,errors=errors,
                window_binding=window,operational_deadline_overrun=overrun,
                cleanup_deadline_monotonic_ns=self._deadline,collection_authority_extended=False,
                cpu_isolation_restoration_verified=isolation,maintenance_restoration_verified=maintenance,
                scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False))
        finally:self._closed=True
        return dict(schema_version='cpu-prefetch-stage17-s180-environment-restoration/1',
            plan_sha256=planning.sha(plan),boot_id=window['boot_id'],
            hardware_restoration_verified=len(hardware)==3 and all(r['verified'] for r in hardware),
            cpu_isolation_restoration_verified=isolation,maintenance_restoration_verified=maintenance,errors=errors)


def prepare_environment(*,plan,window,operator_config):
    """Actual finite preparation. The qualified operator verifies D310 first.

    This must not be called until the owner has received the complete ETA and
    exact resource budget, with the original operational window already anchored.
    """
    _plan(plan);_window(window);require(os.geteuid()==0,'root operator required')
    require(operator_config['unit_name']==UNIT and operator_config['evidence_root']==str(EVIDENCE)
        and operator_config['boot_id']==window['boot_id'] and operator_config['stop_seconds']==120,
        'fixed infrastructure configuration differs')
    preparation_deadline=min(window['end_monotonic_ns'],time.monotonic_ns()+ISOLATION_PREPARATION_NS)
    require(operator_config['protected_work_ns']>=_work_ns(plan)
        and operator_config['lifecycle_seconds']*10**9<=window['end_monotonic_ns']-preparation_deadline,
        'keeper cannot fit original window or omits protected work')
    core=_load_core();affinity=set(os.sched_getaffinity(0));devices={}
    for expected in plan['hardware']['prestate']:
        fd,identity=_open_msr(expected['cpu'])
        try:require(_read_msr(fd)==expected['value'],'actual prestate differs before preparation')
        finally:os.close(fd)
        devices[expected['cpu']]=identity
    state=dict(deadline=preparation_deadline,preparing=True)
    def bounded_command(*args):
        require(args and args[0]=='systemctl','only fixed systemd infrastructure operations allowed')
        _before(state['deadline'])
        result=subprocess.run(['/usr/bin/systemctl',*args[1:]],stdin=subprocess.DEVNULL,capture_output=True,text=True,
            timeout=min(120,(state['deadline']-time.monotonic_ns())/10**9),check=False,
            env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
        _before(state['deadline']);require(result.returncode==0,'fixed systemd operation failed: '+result.stderr[-4096:])
        return result.stdout.strip()
    core.command=bounded_command
    original_restore=core.restore
    def restore_owned(prestate):
        # The frozen core calls restoration inside its preparation exception
        # handler. Give that cleanup its own finite allowance even when the
        # preparation allowance was exhausted; never resume preparation.
        if state['preparing']:
            now=time.monotonic_ns()
            state['deadline']=(min(window['end_monotonic_ns'],now+120*10**9)
                if now<window['end_monotonic_ns'] else now+120*10**9)
        return original_restore(prestate)
    core.restore=restore_owned
    pre=None
    try:
        pre=core.prepare(operator_config)
        require(pre['partition_path']==str(CG) and pre['prestate']['keeper_deadline_monotonic_ns']<=window['end_monotonic_ns'],
            'actual keeper/partition exceeds original window')
        core.verify_remaining_lifetime(pre['prestate'],_work_ns(plan)-resources.EXTERNAL_TIME['restoration_and_exit_ns'],
            resources.EXTERNAL_TIME['restoration_and_exit_ns'])
    except BaseException as error:
        # The original core retains and restores partial preparation failures.
        # Restore our process affinity even if its preparation raised.
        state['deadline']=window['end_monotonic_ns']
        issues=[]
        try:
            if pre is not None:
                try:
                    core.retain(core.Q/'s180-preparation-failure.json',dict(plan_sha256=planning.sha(plan),
                        window_binding=window,error=str(error),execution_authority=False,phase18_authority=False))
                except BaseException as evidence_error:issues.append('failure evidence: '+str(evidence_error))
                try:core.restore(pre['prestate'])
                except BaseException as cleanup_error:issues.append('infrastructure cleanup: '+str(cleanup_error))
        finally:
            try:os.sched_setaffinity(0,affinity)
            except BaseException as affinity_error:issues.append('affinity cleanup: '+str(affinity_error))
        if issues:raise EnvironmentError(str(error)+'; '+'; '.join(issues)) from error
        raise
    state['preparing']=False
    state['deadline']=window['end_monotonic_ns']
    return _PreparedEnvironment(token=_TOKEN,plan=plan,window=window,core=core,preparation=pre,
        devices=devices,affinity=affinity,command_state=state)
