"""D333 owned S180 compaction control and fixed supervised recovery.

Only qualified operator code may prepare this after its full ETA/window gates.
No input-selected command, control, lease, helper image or recovery namespace.
Unknown ownership remains quarantined; this is never an experiment launcher.
"""
from __future__ import annotations
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_runtime_v1 as runtime
from stage17_formal_checkpoint_v1 import PinnedWorker
import stage17_locked_compaction_guard_v1 as original
import stage17_process_group_supervisor_v3 as supervisor
import stage17_s180_environment_v1 as environment

APPROVAL_PATH='docs/evidence/stage17/PILOT-D333-ACCEPTED-20261123-01/owner-acceptance.json'
APPROVAL_SHA='5ca1d5e2f742606f171a8bec35c20cb5a02ed1d9bd59b0157d722e7e43506019'
ROOT=environment.EVIDENCE.parent/'compaction'
UNIT='cpu-prefetch-s180-operator-1.service'
RECOVERY_SCRIPT=Path('/run/cpu-prefetch-s180-operator-1/stop_post.py')
PYTHON=Path('/usr/bin/python3.14')
NATIVE_SHA='7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc'
NATIVE_SIZE=6151832
CLOCK_SHA='cb6422db0be2c3ff3b20897bc58ff4b892ba04e34e9f16f93a8b6d5a04caad69'
CLOCK_SIZE=478632
OWNER_LIMIT=16*1024**2
METADATA_RESERVE_BYTES=OWNER_LIMIT+1024**2
METADATA_RESERVE_INODES=64
CONTROL_SOURCE=dict(path=str(original.CONTROL),byte_capacity=32,chunk_bytes=32,max_data_reads=2,requested=[True]*6)
_TOKEN=object()


class CompactionError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise CompactionError('S180 compaction: '+message)


def approval():
    path=Path(__file__).resolve().parents[1]/APPROVAL_PATH
    raw=_read(path,4096)
    require(hashlib.sha256(raw).hexdigest()==APPROVAL_SHA,'exact approved D333 receipt required')
    value=archive.parse_json(raw)
    require(value['approved'] is True and value['scope']=='SINGLE_D310_S180_FAMILY'
        and value['requested_control_value']==0 and value['supervised_stop_post_required'] is True,'approval scope differs')
    return APPROVAL_SHA


def monitored_plan(plan):
    """Prospective copy only; full native/resource bounds must be recomputed."""
    approval();value=archive.parse_json(archive.canonical(plan))
    require(len(value['captures'])==180,'full original S180 matrix required')
    for row in value['captures']:
        entries=row['monitoring']['environment_sources']
        found=[e for e in entries if e['path']==CONTROL_SOURCE['path']]
        require(not found or found==[CONTROL_SOURCE],'compaction source duplicated or changed')
        if not found:entries.append(archive.parse_json(archive.canonical(CONTROL_SOURCE)))
    return value


def require_monitored(plan):
    require(monitored_plan(plan)==plan,'phase control readbacks are absent')


def _read(path,maximum):
    with archive.open_regular(path) as stream:
        before=archive.file_stamp(os.fstat(stream.fileno()));raw=stream.read(maximum+1)
        require(len(raw)<=maximum and before==archive.file_stamp(os.fstat(stream.fileno())),'bounded stable record required')
    return raw


def _identity(path):
    s=Path(path).stat(follow_symlinks=False);return [s.st_dev,s.st_ino]


def _root_file(path,maximum):
    raw=_read(path,maximum);s=Path(path).stat(follow_symlinks=False)
    require(s.st_uid==0 and s.st_nlink==1 and not s.st_mode&0o022,'root-owned protected record required')
    return raw


def _save(path,value):
    raw=archive.canonical(value);require(len(raw)<=OWNER_LIMIT,'recovery/guard record exceeds bound')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        require(os.write(fd,raw)==len(raw),'short durable guard record');os.fsync(fd)
    finally:os.close(fd)
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)


def _ticks(pid):
    raw=_read(Path('/proc')/str(pid)/'stat',65536).decode().rsplit(')',1)[1].split()
    require(raw[0] not in ('Z','X','x'),'process is not live');return int(raw[19])


def _membership(pid):
    rows=[v[3:] for v in _read(Path('/proc')/str(pid)/'cgroup',4096).decode().splitlines() if v.startswith('0::')]
    require(len(rows)==1,'one actual unified cgroup entry required');return rows[0]


def _systemctl(*arguments,deadline):
    require(time.monotonic_ns()<deadline,'finite recovery/supervision deadline expired')
    result=subprocess.run(['/usr/bin/systemctl',*arguments],stdin=subprocess.DEVNULL,capture_output=True,
        timeout=max(.001,min(120,(deadline-time.monotonic_ns())/10**9)),check=False,
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
    require(result.returncode==0 and len(result.stdout)<=65536 and len(result.stderr)<=65536
        and time.monotonic_ns()<deadline,'fixed systemd operation failed or expired')
    return result.stdout.decode().strip()


def _unit(deadline):
    raw=_systemctl('show',UNIT,'--property=MainPID,ControlPID,ControlGroup,KillMode,SendSIGKILL,ExecStopPost,NeedDaemonReload',deadline=deadline)
    return dict(row.split('=',1) for row in raw.splitlines() if '=' in row)


class _Supervision:
    def __init__(self,*,token,script,properties):
        require(token is _TOKEN,'actual supervision verification required')
        self.script=script;self.properties=properties;self.pid=os.getpid();self.identity=_identity(script.path)

    def check(self):
        require(os.getpid()==self.pid and _identity(self.script.path)==self.identity,'supervisor/script identity changed')
        require(hashlib.sha256(_root_file(self.script.path,1024**2)).hexdigest()==self.script.sha256,
            'recovery script bytes changed')


def verify_supervision(*,recovery_script,deadline_ns):
    """The qualified profile supplies this fixed-path script's external binding."""
    approval();require(os.geteuid()==0,'root supervisor required')
    require(type(recovery_script) is runtime.ImageBinding and recovery_script.path==RECOVERY_SCRIPT,'fixed recovery script required')
    raw=_root_file(RECOVERY_SCRIPT,1024**2)
    require(raw==stop_post_script() and len(raw)==recovery_script.size_bytes
        and hashlib.sha256(raw).hexdigest()==recovery_script.sha256,
        'profile-bound stop-post script differs')
    props=_unit(deadline_ns)
    require(props.get('MainPID')==str(os.getpid()) and props.get('ControlGroup')=='/'+UNIT
        and _membership(os.getpid())=='/'+UNIT and props.get('KillMode')=='control-group'
        and props.get('SendSIGKILL')=='yes' and props.get('NeedDaemonReload')=='no',
        'actual supervised root operator differs')
    command=props.get('ExecStopPost','')
    require(command.count('argv[]=')==1 and command.split('argv[]=',1)[1].split(' ;',1)[0]
        ==' '.join((str(PYTHON),'-B',str(RECOVERY_SCRIPT))),'one fixed loaded stop-post command required')
    return _Supervision(token=_TOKEN,script=recovery_script,properties=props)


def stop_post_script():
    """Exact fixed entry bytes for the qualified root package installer."""
    return (b'from pathlib import Path\nimport sys\n'
        b'sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))\n'
        b'from stage17_s180_compaction_v1 import recover\n'
        b'if __name__ == "__main__":\n    recover()\n')


class _Lease(original.Guard):
    def __init__(self,root,*,deadline,owner_sha256):
        super().__init__(root,deadline_ns=deadline,control=original.LinuxControl(),lease=original.LEASE)
        self.owner_sha256=owner_sha256

    def expected_lease(self):
        return dict(super().expected_lease(),scope='D333-S180-v1',owner_sha256=self.owner_sha256)


class _OwnedCompaction:
    def __init__(self,*,token,owner,owner_raw,guard,supervision):
        require(token is _TOKEN,'actual owned preparation required')
        self.owner=owner;self.owner_raw=owner_raw;self.guard=guard;self.supervision=supervision
        self.pid=os.getpid();self.lease_identity=_identity(original.LEASE);self.failed=False;self.closed=False

    def _ownership(self):
        require(not self.closed and self.pid==os.getpid(),'guard is closed or belongs to another process')
        require(_identity(original.LEASE)==self.lease_identity==list((os.fstat(self.guard.fd).st_dev,os.fstat(self.guard.fd).st_ino))
            and _root_file(ROOT/'owner.json',OWNER_LIMIT)==self.owner_raw
            and archive.canonical(self.owner)==self.owner_raw,'guard ownership/record changed')
        self.supervision.check()

    def check(self,*,boundary,ordinal=None):
        require(boundary in ('ADMISSION','FAMILY_ENTRY','AFTER_CAPTURE','BEFORE_RELEASE','FINAL'), 'fixed guard boundary required')
        require(ordinal is None or (type(ordinal) is int and 0<=ordinal<180),'capture ordinal differs')
        require(not self.failed,'compaction guard failed; no automatic retry')
        try:
            self._ownership();observed=self.guard.verify()
            return dict(approval_sha256=APPROVAL_SHA,owner_sha256=hashlib.sha256(self.owner_raw).hexdigest(),
                boundary=boundary,execution_ordinal=ordinal,boot_id=self.owner['window']['boot_id'],
                observed_monotonic_ns=time.monotonic_ns(),**observed,execution_authority=False)
        except BaseException as error:
            self.failed=True
            self.failure=str(error)
            try:_save(ROOT/'failure.json',dict(error=str(error),boundary=boundary,execution_ordinal=ordinal,
                operational_window_reset=False,execution_authority=False))
            except BaseException as evidence_error:self.failure_evidence_error=str(evidence_error)
            raise

    def register_worker(self,worker,*,role):
        require(type(worker) is PinnedWorker and role in ('near','far','q15','pilot'),'fixed owned worker role required')
        self.check(boundary='FAMILY_ENTRY');worker._alive()
        expected=CLOCK_SHA if role in ('near','far') else NATIVE_SHA
        require(_membership(worker.pid)=='/'+environment.UNIT+'/reserved','worker not in original reserved partition')
        fd=os.open(f'/proc/{worker.pid}/exe',os.O_RDONLY|os.O_CLOEXEC)
        try:
            require(os.fstat(fd).st_size==(CLOCK_SIZE if role in ('near','far') else NATIVE_SIZE),'worker image extent differs')
            digest=hashlib.sha256()
            while block:=os.read(fd,1024**2):
                require(time.monotonic_ns()<self.guard.deadline_ns,'worker registration deadline expired')
                digest.update(block)
            require(digest.hexdigest()==expected,'actual owned worker image differs')
        finally:os.close(fd)
        worker._alive()
        _save(ROOT/('worker-'+role+'.json'),dict(role=role,pid=worker.pid,start_ticks=worker.start_ticks,sha256=expected,
            plan_sha256=self.owner['plan_sha256'],boot_id=self.owner['window']['boot_id']))

    def restore(self,*,platform_proof=None):
        self._ownership()
        require(not supervisor.ProcfsIdentityModel().direct_children(),'owned children remain before compaction restoration')
        require(not environment.CG.exists() or environment.CG.joinpath('cgroup.procs').read_text().strip()=='',
            'native partition is live before compaction restoration')
        if platform_proof is not None:
            require(type(platform_proof) is dict and set(platform_proof)=={'hardware_restoration_verified',
                'cpu_isolation_restoration_verified','maintenance_restoration_verified','errors'}
                and platform_proof['errors']==[] and all(platform_proof[k] is True for k in
                    ('hardware_restoration_verified','cpu_isolation_restoration_verified','maintenance_restoration_verified')),
                'platform restoration is incomplete; leave compaction lease occupied')
            _save(ROOT/'normal-platform.json',dict(owner_sha256=hashlib.sha256(self.owner_raw).hexdigest(),
                platform=platform_proof,execution_authority=False))
        result=self.guard.restore();self.guard.unlock();self.closed=True
        return result

    def restored_observation(self):
        """Read actual post-analysis controls; never reacquire or repair a guard."""
        require(self.closed and self.pid==os.getpid() and self.guard.fd is None,
            'same-process completed compaction restoration required')
        require(_root_file(ROOT/'owner.json',OWNER_LIMIT)==self.owner_raw
            and archive.canonical(self.owner)==self.owner_raw,'original restored owner record changed')
        intent=self.guard.intent
        require(_root_file(self.guard.root/'intent.json',4096)==original.canonical(intent),
            'original restored intent changed')
        expected=dict(schema_version='cpu-prefetch-locked-compaction-restoration/1',
            boot_id=intent['boot_id'],requested_value=intent['observed_prestate'],
            observed_value=intent['observed_prestate'],verified=True,
            intent_sha256=self.guard.expected_lease()['intent_sha256'])
        require(_root_file(self.guard.root/'restoration.json',4096)==original.canonical(expected),
            'actual original compaction restoration receipt changed')
        fd=os.open(original.LEASE,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
        try:
            # A shared nonblocking lock detects a new holder without creating,
            # truncating or adopting the old lease. Keep it across readback.
            fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            st=os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_uid==0 and st.st_nlink==1
                and not st.st_mode&0o022 and [st.st_dev,st.st_ino]==self.lease_identity
                and _identity(original.LEASE)==self.lease_identity and st.st_size==0
                and os.pread(fd,1,0)==b'','actual compaction lease replaced or occupied')
            require(self.guard.control.boot()==intent['boot_id']==self.owner['window']['boot_id'],
                'restored compaction belongs to another boot')
            observed=self.guard.control.read()
            require(observed==intent['observed_prestate'],'actual restored compaction value changed')
            require(archive.file_stamp(os.fstat(fd))==archive.file_stamp(st)
                and _identity(original.LEASE)==self.lease_identity,'restored lease changed during readback')
            return dict(approval_sha256=APPROVAL_SHA,owner_sha256=hashlib.sha256(self.owner_raw).hexdigest(),
                original_value=intent['observed_prestate'],observed_value=observed,
                lease_identity=self.lease_identity,lease_empty=True,verified=True)
        finally:os.close(fd)


def prepare(*,environment_owner,supervision):
    """Actual D333 preparation; never call before full operational ETA/admission preparation."""
    approval();require(type(environment_owner) is environment._PreparedEnvironment
        and type(supervision) is _Supervision,'actual environment and supervised recovery required')
    supervision.check()
    plan=archive.parse_json(environment_owner._plan);window=archive.parse_json(environment_owner._window)
    environment_owner._guard(environment.planning.sha(plan));require_monitored(plan)
    require(environment_owner._compaction is None,'guard already attached; no retry')
    require(not environment.CG.joinpath('cgroup.procs').read_text().strip(),'native tasks precede guard preparation')
    require(ROOT.parent.resolve(strict=True)==ROOT.parent,'canonical guard parent required')
    ROOT.mkdir(mode=0o700)
    owner=dict(schema_version='cpu-prefetch-stage17-s180-compaction-owner/1',approval_sha256=APPROVAL_SHA,
        pid=os.getpid(),start_ticks=_ticks(os.getpid()),plan_sha256=environment.planning.sha(plan),plan=plan,window=window,
        preparation=archive.parse_json(environment_owner._preparation),devices={str(k):list(v) for k,v in environment_owner._devices.items()},
        affinity=sorted(environment_owner._affinity),supervision_script_sha256=supervision.script.sha256,
        execution_authority=False,phase18_authority=False)
    _save(ROOT/'owner.json',owner);raw=_root_file(ROOT/'owner.json',OWNER_LIMIT)
    guard=_Lease(ROOT/'guard',deadline=window['end_monotonic_ns'],owner_sha256=hashlib.sha256(raw).hexdigest())
    guard.__enter__()
    owned=_OwnedCompaction(token=_TOKEN,owner=owner,owner_raw=raw,guard=guard,supervision=supervision)
    try:
        owned.check(boundary='ADMISSION');environment_owner._compaction=owned
        return owned
    except BaseException:
        try:owned.restore()
        finally:guard.unlock()
        raise


def _recover(owner,raw,*,deadline):
    """Fixed stop-post body after independent service/owner-death verification."""
    require(archive.canonical(owner)==raw and owner['approval_sha256']==APPROVAL_SHA
        and owner['plan_sha256']==environment.planning.sha(owner['plan']),
        'original recovery plan/approval differs')
    require(owner['preparation']['partition_path']==str(environment.CG)
        and owner['preparation']['operator_config']['unit_name']==environment.UNIT
        and owner['preparation']['operator_config']['evidence_root']==str(environment.EVIDENCE),
        'fixed isolation recovery configuration differs')
    require(original.LinuxControl().boot()==owner['window']['boot_id'],'recovery cannot cross boot')
    try:live=_ticks(owner['pid'])==owner['start_ticks']
    except (OSError,CompactionError):live=False
    require(not live,'original owner remains live')
    guard=_Lease(ROOT/'guard',deadline=0,owner_sha256=hashlib.sha256(raw).hexdigest())
    guard.intent=json.loads(_root_file(ROOT/'guard/intent.json',4096));guard.lock()
    try:
        if guard.lease_record() is None:
            require(not environment.CG.exists() and not environment.CG.parent.exists()
                and not supervisor.ProcfsIdentityModel().direct_children(),'already-restored recovery is not quiescent')
            core=environment._load_core();core.configure(owner['preparation'])
            require(core.root_state()==owner['preparation']['prestate']['root'],'actual original CPU root state differs')
            for row in owner['plan']['hardware']['prestate']:
                fd,identity=environment._open_msr(row['cpu'])
                try:require(list(identity)==owner['devices'][str(row['cpu'])]
                    and environment._read_msr(fd)==row['value'],'actual restored MSR prestate differs')
                finally:os.close(fd)
            proof_path=ROOT/'normal-platform.json'
            if proof_path.exists():
                proof=archive.parse_json(_root_file(proof_path,65536))
                require(proof['owner_sha256']==hashlib.sha256(raw).hexdigest()
                    and proof['platform']['errors']==[] and all(proof['platform'][k] is True for k in
                        ('hardware_restoration_verified','cpu_isolation_restoration_verified','maintenance_restoration_verified')),
                    'original platform restoration was not verified')
            else:
                require(all(core.systemd_state(k)==v for k,v in owner['preparation']['prestate']['maintenance_before'].items()),
                    'actual original maintenance state differs')
            return guard.restore()
        require(guard.lease_record()==guard.expected_lease(),'foreign, partial or changed lease; do not restore')
        pre=owner['preparation'];core=environment._load_core();core.configure(pre)
        if environment.CG.parent.exists():
            pids=[]
            if environment.CG.exists():
                require(_identity(environment.CG)==pre['prestate']['partition_identity'],'owned partition replaced')
                pids=[int(v) for v in environment.CG.joinpath('cgroup.procs').read_text().split()]
            witnesses=[]
            for role in ('near','far','q15','pilot'):
                path=ROOT/('worker-'+role+'.json')
                if path.exists():
                    row=archive.parse_json(_root_file(path,4096))
                    require(set(row)=={'role','pid','start_ticks','sha256','plan_sha256','boot_id'}
                        and row['role']==role,'fixed worker witness fields/role differ')
                    witnesses.append(row)
            for pid in pids:
                rows=[w for w in witnesses if w['pid']==pid and w['start_ticks']==_ticks(pid)
                    and w['plan_sha256']==owner['plan_sha256'] and w['boot_id']==owner['window']['boot_id']]
                require(len(rows)==1,'unknown live native task; leave guard occupied')
                expected=CLOCK_SHA if rows[0]['role'] in ('near','far') else NATIVE_SHA
                require(rows[0]['sha256']==expected,'worker witness image differs')
                with open(f'/proc/{pid}/exe','rb') as stream:
                    require(os.fstat(stream.fileno()).st_size==(CLOCK_SIZE if rows[0]['role'] in ('near','far') else NATIVE_SIZE),
                        'live worker image extent differs')
                    digest=hashlib.file_digest(stream,'sha256').hexdigest()
                require(digest==expected,'live worker executable differs')
            require(core.identity(environment.CG.parent)==pre['prestate']['unit_identity']
                and _ticks(pre['prestate']['keeper_pid'])==pre['prestate']['keeper_start_ticks']
                and environment.CG.parent.joinpath('cgroup.procs').read_text().strip()==''
                and environment.CG.parent.joinpath('supervisor/cgroup.procs').read_text().strip()==str(pre['prestate']['keeper_pid'])
                and {p.name for p in environment.CG.parent.iterdir() if p.is_dir()}
                    ==({'supervisor','reserved'} if environment.CG.exists() else {'supervisor'}),
                'original isolation keeper/unit changed')
            _systemctl('stop',environment.UNIT,deadline=deadline)
        require(not environment.CG.exists() and not supervisor.ProcfsIdentityModel().direct_children(),
            'workers remain after supervised stop')
        recovery=ROOT/'recovery';recovery.mkdir(mode=0o700);core.Q=recovery/'isolation';core.Q.mkdir(mode=0o700)
        def bounded(*args):
            require(args and args[0]=='systemctl','fixed recovery command required')
            return _systemctl(*args[1:],deadline=deadline)
        core.command=bounded
        restored=environment._PreparedEnvironment(token=environment._TOKEN,plan=owner['plan'],window=owner['window'],
            core=core,preparation=pre,devices={int(k):tuple(v) for k,v in owner['devices'].items()},
            affinity=set(owner['affinity']),command_state=dict(deadline=deadline))
        restored._deadline=deadline
        result=restored._restore(owner['plan'],owner['window'])
        require(not result['errors'] and all(result[k] is True for k in ('hardware_restoration_verified',
            'cpu_isolation_restoration_verified','maintenance_restoration_verified')),'independent platform recovery failed')
        control=guard.restore()
        _save(recovery/'completion.json',dict(environment=result,compaction=control,execution_authority=False,phase18_authority=False))
        return control
    finally:guard.unlock()


def recover():
    """Only the fixed root operator's actual ExecStopPost may enter recovery."""
    approval();require(os.geteuid()==0 and _membership(os.getpid())=='/'+UNIT,'fixed supervised recovery required')
    deadline=time.monotonic_ns()+120*10**9;props=_unit(deadline)
    require(props.get('ControlPID')==str(os.getpid()) and props.get('MainPID')=='0'
        and props.get('KillMode')=='control-group','actual stop-post ownership differs')
    try:
        raw=_root_file(ROOT/'owner.json',OWNER_LIMIT);owner=archive.parse_json(raw)
        return _recover(owner,raw,deadline=deadline)
    except BaseException as error:
        try:_save(ROOT/'recovery-failure.json',dict(error=str(error),quarantined=True,execution_authority=False))
        except BaseException:pass
        raise
