"""Read-only post-service verification for the approved descriptive S180 pilot.

The qualified caller authenticates this code/profile and the actual original
seven-input owner. Historical signed facts never reconstruct a live admission
owner. No raw inverse, measurement, repair, retry or Stage18 permission exists.
"""
from __future__ import annotations
from dataclasses import asdict
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import time

import stage17_s180_execution_v1 as execution
import stage17_s180_checkpoint_v1 as checkpoint

archive=execution.archive
SCHEMA='cpu-prefetch-stage17-s180-scoped-operational-exit/1'
UNIT=execution.compaction.UNIT
CGROUP=Path('/sys/fs/cgroup')/UNIT


def require(ok,message):
    if not ok:raise execution.ExecutionError('S180 independent exit: '+message)


def same(actual,expected,label):
    require(archive.canonical(actual)==archive.canonical(expected),label+' differs')


def _bound(binding,path):
    same(binding,execution._binding(path),'retained '+path.name+' binding')
    raw=execution.compaction._root_file(path,16*execution.MIB)
    require(hashlib.sha256(raw).hexdigest()==binding['sha256'],'retained bytes changed during read')
    return archive.parse_json(raw)


def _unit(deadline):
    raw=execution.compaction._systemctl('show',UNIT,
        '--property=MainPID,ControlPID,ActiveState,SubState,Result,ExecMainCode,ExecMainStatus,ExecStopPost,NeedDaemonReload',
        deadline=deadline)
    observed=dict(row.split('=',1) for row in raw.splitlines() if '=' in row)
    for key,value in dict(MainPID='0',ControlPID='0',ActiveState='inactive',SubState='dead',
            Result='success',ExecMainCode='1',ExecMainStatus='0',NeedDaemonReload='no').items():
        require(observed.get(key)==value,'main service not successfully stopped: '+key)
    command=observed.get('ExecStopPost','')
    require(command.count('argv[]=')==1 and command.split('argv[]=',1)[1].split(' ;',1)[0]
        ==' '.join((str(execution.compaction.PYTHON),'-B',str(execution.compaction.RECOVERY_SCRIPT))),
        'fixed loaded stop-post command differs')
    require('code=exited' in command and 'status=0' in command,'stop-post did not complete successfully')
    require(not os.path.lexists(CGROUP),'main service cgroup still exists')
    return observed


def _archives(family,report):
    """Check epochs anchored before the completed full inverse, not new hashes."""
    rows=report['original_archive_epochs']
    require(type(rows) is list and len(rows)==1440,'all1440 verified original epochs required')
    expected={hashlib.sha256((family+':'+name).encode()).hexdigest()+'.cpfa'
        for ordinal in range(180) for name in checkpoint.capture_names(ordinal)}
    require(len(expected)==1440,'fixed complete artifact namespace required')
    observed=set();device=execution.PROGRAM.stat(follow_symlinks=False).st_dev
    for row in rows:
        require(type(row) is dict and set(row)=={'archive_name','expected_physical','stamp','mode','uid','gid'},
            'archive epoch shape differs')
        name=row['archive_name'];require(name in expected and name not in observed,'duplicate or foreign archive epoch')
        observed.add(name);s=(execution.PROGRAM/'archives'/name).stat(follow_symlinks=False)
        require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and not s.st_mode&0o022
            and s.st_dev==device,'retained original archive is unsafe')
        same(list(archive.file_stamp(s)),row['stamp'],'verified original archive epoch')
        same([stat.S_IMODE(s.st_mode),s.st_uid,s.st_gid],[row['mode'],row['uid'],row['gid']],
            'verified archive protection')
        same(s.st_size,row['expected_physical']['size_bytes'],'verified original archive extent')
        archive.sha(row['expected_physical']['sha256'],'original physical digest')
    require(observed==expected,'incomplete original epochs')


def _history(base,handoff,plan):
    root=execution.ROOT
    admission=_bound(handoff['admission_complete'],root/'admission-complete.json')
    same(admission['plan_sha256'],handoff['plan_sha256'],'historical admitted plan')
    same(admission['request_sha256'],handoff['request_sha256'],'historical admitted request')
    same(admission['window_binding'],handoff['window_binding'],'historical admission window')
    require(admission['live_owner_reconstruction_allowed'] is False,'historical facts cannot reconstruct live owners')
    plan_evidence=_bound(admission['plan_evidence'],root/'qualified-plan-admission.json')
    resource=_bound(admission['resource_evidence'],root/'resource-admission.json')
    for evidence in (plan_evidence,resource):
        same(evidence['plan_sha256'],handoff['plan_sha256'],'historical evidence plan')
        require(evidence['execution_authority'] is False and evidence['phase18_authority'] is False,
            'historical evidence grants unexpected authority')
    contexts=admission['derived_contexts']
    require(set(contexts)=={f'S17-EXT-{i:03d}' for i in range(8,11)},'historical context set differs')
    same(plan_evidence['derived_scoped_context'],contexts['S17-EXT-008'],'actual owned EXT008 context')
    def historical(input_id,payload,view,*,for_execution):
        require(for_execution is False,'exit cannot perform live admission replay')
        binding=admission['plan_evidence' if input_id=='S17-EXT-008' else 'resource_evidence']
        key='plan_proof_sha256' if input_id=='S17-EXT-008' else 'resource_proof_sha256'
        same(payload,{key:binding['sha256']},'signed historical evidence payload')
        return contexts[input_id]
    book=execution.journal.ScopedJournal(root/'scoped-journal',base_validation=base,plan=plan,
        semantic_policy_sha256=execution.admission.POLICY_SHA,semantic_replay=historical,synthetic_test_only=False)
    with book:
        view=book.inspect(for_execution=False)
        require(view.generation==3,'all three actual scoped resolutions required')
        same([execution.authority.binding(view.resolutions[f'S17-EXT-{i:03d}']) for i in range(8,11)],
            handoff['scoped_resolutions'],'signed historical scoped resolutions')
        for key in contexts:same(view.resolutions[key].semantic_context,contexts[key],'signed historical '+key)
    _bound(handoff['scoped_journal'],root/'scoped-journal/journal-3.json')
    authorization=_bound(handoff['pilot_authorization'],root/'pilot-authorization.json')
    same(handoff['pilot_authorization_signature'],execution._binding(root/'pilot-authorization.json.sig'),
        'original authorization signature')
    same(authorization,contexts['S17-EXT-010']['authorization'],'actual historical authorization')
    same(authorization['window_binding'],handoff['window_binding'],'original authorization window')
    return view


def _environment(plan,report,deadline):
    """Fresh readback against the original signed post-analysis proof; no repair."""
    env=execution.environment;compaction=execution.compaction;expected=report['final_environment_observation']
    same(expected['plan_sha256'],report['plan_sha256'],'final environment plan')
    require(expected['hardware_restoration_verified'] is True and expected['cpu_isolation_restoration_verified'] is True
        and expected['maintenance_restoration_verified'] is True and expected['compaction_restoration_verified'] is True,
        'original final restoration missing')
    require(not os.path.lexists(env.CG.parent) and not os.path.lexists(Path('/run/systemd/system')/env.UNIT),
        'recovery unit file or cgroup remains')
    core=env._load_core()
    def systemctl(*args):
        require(args and args[0]=='systemctl','unexpected readback command')
        return compaction._systemctl(*args[1:],deadline=deadline)
    core.command=systemctl
    same(core.root_state(),expected['root'],'current restored CPU root')
    for name,previous in expected['maintenance'].items():
        current=core.systemd_state(name)
        require(current['UnitFileState']==previous['UnitFileState']
            and (name not in core.TIMER_SERVICES or current['ActiveState']==previous['ActiveState']),
            'current restored maintenance differs')
    raw=compaction._systemctl('show',env.UNIT,'--property=ActiveState,SubState,MainPID',deadline=deadline)
    same(dict(row.split('=',1) for row in raw.splitlines()),expected['recovery_service'],'current recovery service')
    owner_raw=compaction._root_file(compaction.ROOT/'owner.json',compaction.OWNER_LIMIT)
    require(hashlib.sha256(owner_raw).hexdigest()==expected['compaction']['owner_sha256'],'original guard owner changed')
    owner=archive.parse_json(owner_raw);same(owner['plan'],plan,'original restoration owner plan')
    same(owner['window'],expected['window_binding'],'original restoration owner window')
    same(owner['preparation']['prestate']['root'],expected['root'],'original CPU root restoration')
    for row in plan['hardware']['prestate']:
        fd,identity=env._open_msr(row['cpu'])
        try:
            same(list(identity),owner['devices'][str(row['cpu'])],'current original MSR device')
            same(env._read_msr(fd),row['value'],'current restored MSR')
        finally:os.close(fd)
    intent_raw=compaction._root_file(compaction.ROOT/'guard/intent.json',4096)
    intent=archive.parse_json(intent_raw)
    restoration=archive.parse_json(compaction._root_file(compaction.ROOT/'guard/restoration.json',4096))
    require(restoration['verified'] is True and restoration['intent_sha256']==hashlib.sha256(intent_raw).hexdigest(),
        'original compaction restoration receipt differs')
    for key in ('requested_value','observed_value'):same(restoration[key],intent['observed_prestate'],'restored compaction '+key)
    same(expected['compaction']['original_value'],intent['observed_prestate'],'original compaction prestate')
    lease=compaction.original.LEASE
    fd=os.open(lease,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB);s=os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and not s.st_mode&0o022
            and s.st_size==0 and os.pread(fd,1,0)==b'','restored compaction lease occupied or unsafe')
        same([s.st_dev,s.st_ino],expected['compaction']['lease_identity'],'current original lease')
        same(compaction._identity(lease),expected['compaction']['lease_identity'],'named original lease')
        same(compaction.original.LinuxControl().read(),intent['observed_prestate'],'current restored compaction control')
        require(archive.file_stamp(os.fstat(fd))==archive.file_stamp(s),'lease epoch changed through readback')
    finally:os.close(fd)
    return dict(read_only=True,original_root_and_maintenance_verified=True,original_msr_values_and_devices_verified=True,
        original_compaction_receipt_and_unoccupied_lease_verified=True)


def observe(*,base_owner,operator_revision,operator_profile_sha256):
    """Qualified independent caller only; write a signed scoped exit once.

    This proves the main experiment service has exited. The caller must itself
    exit successfully before an external status reader claims overall completion.
    """
    require(type(base_owner) is execution.original._VerifiedOriginal,'actual fresh original owner required')
    require(os.getresuid()==(0,0,0),'full root exit observer required')
    return _observe(base_owner.view(),operator_revision,operator_profile_sha256)


def _observe(base,revision,profile):
    root=execution.ROOT;deadline=time.monotonic_ns()+1800*execution.NS
    execution._bytes(root/'independent-exit-attempt.json',archive.canonical(dict(observer_pid=os.getpid(),
        started_monotonic_ns=time.monotonic_ns(),operator_revision=revision,operator_profile_sha256=profile,
        automatic_retry=False,execution_authority=False,phase18_authority=False)))
    require(not os.path.lexists(root/'controller-failure.json'),'original controller failed; no exit promotion')
    path=root/'controller-handoff.json';raw=execution.compaction._root_file(path,16*execution.MIB)
    execution.authority.signatures._verify_signature(raw,Path(str(path)+'.sig'),
        base.resolutions['S17-EXT-003'].semantic_context['trust'])
    handoff=archive.parse_json(raw)
    for key,value in dict(schema_version=execution.SCHEMA,status='VALIDATED_PILOT_PENDING_INDEPENDENT_OPERATIONAL_EXIT',
            operator_revision=revision,operator_profile_sha256=profile,automatic_retries=0,
            independent_service_exit_verified=False,inferential_freeze_established=False,
            execution_authority=False,phase18_authority=False).items():same(handoff[key],value,'signed handoff '+key)
    same(handoff['original_seven'],[execution.authority.binding(base.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,8)],
        'unchanged actual original seven')
    execution.environment._window(handoff['window_binding'])
    deadline=min(deadline,handoff['window_binding']['end_monotonic_ns'])
    unit=_unit(deadline)
    plan=_bound(handoff['source_plan'],execution.author.ROOT/'plan.json')
    execution.environment._plan(plan);same(execution._sha(plan),handoff['plan_sha256'],'original source plan digest')
    view=_history(base,handoff,plan)
    bound=dict(handoff['family_validation']);name=bound.pop('file_name')
    same(name,'family-validation.json','complete family report name')
    report=_bound(dict(bound,path=str(root/'analysis'/name)),root/'analysis'/name)
    for key,value in dict(schema_version=execution.analysis.SCHEMA,status='VALIDATED_DESCRIPTIVE_FAMILY_PENDING_OPERATIONAL_EXIT',
            plan_sha256=handoff['plan_sha256'],request_sha256=handoff['request_sha256'],archive_originals_inversely_verified=1440,
            actual_worker_completion_verified=True,original_archive_custody_verified=True,
            original_archive_epochs_unchanged_through_inverse=True,final_live_restoration_verified=True,
            operational_exit_verified=False,inferential_freeze_established=False,execution_authority=False,phase18_authority=False).items():
        same(report[key],value,'actual verified family '+key)
    require(report['family_data_consistency']['status']=='PASSED','original complete family consistency failed')
    same(report['final_environment_observation']['window_binding'],handoff['window_binding'],'original final environment window')
    same(report['original_generation_binding'],handoff['original_source_release'],'original source release after collection')
    limits=execution.custody.CustodyLimits(131072,500000,500000,2*execution.MIB,deadline)
    with execution.stores.ProgramStore(execution.PROGRAM,scope_sha256=plan['storage']['program_scope_sha256'],
            family_id=handoff['plan_sha256'],limits=limits,ext009_resolution_sha256=view.resolutions['S17-EXT-009'].sha256) as store:
        require(store.family_id in store._families,'original family missing; never create it at exit')
        require(not store._capture_pending and store.reserved_bytes()==0
            and all(row['kind']=='RELEASED' for row in store._states.values()),'original programme is not quiescent')
        same(asdict(store.ledger_binding()),report['original_ledger_tip'],'original ledger after inverse')
        _archives(handoff['plan_sha256'],report)
        restoration=_environment(plan,report,deadline)
        same(_unit(deadline),unit,'stopped service changed during exit verification')
        _archives(handoff['plan_sha256'],report)
        require(time.monotonic_ns()<deadline,'original exit deadline expired')
        result=dict(schema_version=SCHEMA,status='SCOPED_STAGE17_OPERATIONALLY_COMPLETE',scope='D310-S180-DESCRIPTIVE-PILOT',
            plan_sha256=handoff['plan_sha256'],operator_revision=revision,operator_profile_sha256=profile,
            window_binding=handoff['window_binding'],controller_handoff=execution._binding(path),
            family_validation=handoff['family_validation'],original_seven=handoff['original_seven'],
            scoped_resolutions=handoff['scoped_resolutions'],main_service_exit=unit,restoration=restoration,
            archive_epochs_verified_after_service_exit=1440,raw_inverse_repeated=False,measurements_repeated=False,
            full_and_low_count_outcomes_retained=True,observer_still_running=True,
            inferential_freeze_established=False,execution_authority=False,phase18_authority=False)
        output=root/'scoped-stage17-exit.json';binding=execution._bytes(output,archive.canonical(result))
        sig=execution._sign(output,deadline)
        execution.authority.signatures._verify_signature(archive.canonical(result),sig,
            base.resolutions['S17-EXT-003'].semantic_context['trust'])
        _archives(handoff['plan_sha256'],report)
        require(time.monotonic_ns()<deadline,'original exit publication expired')
        return dict(report=result,binding=binding,signature=execution._binding(sig))
