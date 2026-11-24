"""One fixed S180 source/qualification/admission/collection/analysis composition.

Library only. Its qualified root service must authenticate the complete source
and image profile, explicit storage commitments and whole-run ETA before entry.
No configuration-selected command, signer, backend, retry or window reset exists.
A successful handoff still requires independent service-exit verification.
"""
from __future__ import annotations
import contextlib
from dataclasses import dataclass,replace
import hashlib
import os
from pathlib import Path
import signal
import stat
import subprocess
import threading
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_s180_admission_custody_v1 as programme
import stage17_s180_analysis_phase_v1 as phase
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_authority_v1 as authority
import stage17_s180_calibration_compatibility_v1 as compatibility
import stage17_s180_clock_qualification_v1 as clocks
import stage17_s180_compaction_v1 as compaction
import stage17_s180_environment_v1 as environment
import stage17_s180_family_analysis_v1 as analysis
import stage17_s180_journal_v1 as journal
import stage17_s180_launcher_v1 as launcher
import stage17_s180_namespace_admission_v1 as namespaces
import stage17_s180_owner_replay_v1 as original
import stage17_s180_plan_admission_v1 as admission
import stage17_s180_platform_v1 as platform
import stage17_s180_q15_session_v1 as q15
import stage17_s180_qualification_evidence_v1 as qualification
import stage17_s180_resource_admission_v1 as resources
import stage17_s180_resource_plan_v1 as budgets
import stage17_s180_source_author_v1 as author

ROOT=environment.EVIDENCE.parent
PROGRAM=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-23/formal-archive-program-1')
KEY=Path('/home/omaltsev/.ssh/id_ed25519')
NAMESPACE='stage17-owner-acceptance'
PRINCIPAL='maltsev.oiu@phystech.edu'
SCHEMA='cpu-prefetch-stage17-s180-controller-handoff/2'
DECLARATION_SHA='a87db70744a25ffa98361c430e6f486e009960b7f7468e052b336b415093ef7a'
NS=10**9
GIB=1024**3
MIB=1024**2
_CONSUMED=False


class ExecutionError(archive.ArchiveError):pass


def require(ok,message):
    if not ok:raise ExecutionError('S180 execution: '+message)


def _sha(value):return hashlib.sha256(archive.canonical(value)).hexdigest()


def _binding(path):
    with archive.open_regular(path) as stream:
        before=archive.file_stamp(os.fstat(stream.fileno()));raw=stream.read(16*MIB+1)
        require(len(raw)<=16*MIB and before==archive.file_stamp(os.fstat(stream.fileno())),
            'bounded stable controller metadata required')
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _bytes(path,raw):
    require(type(raw) is bytes and 0<len(raw)<=16*MIB,'bounded controller publication required')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        position=0
        while position<len(raw):
            size=os.write(fd,raw[position:]);require(size>0,'controller publication stalled');position+=size
        os.fsync(fd)
    finally:os.close(fd)
    namespaces._sync_directory(path.parent);return _binding(path)


def _save(name,value):return _bytes(ROOT/name,archive.canonical(value))


def _sign(path,deadline):
    """Fixed offline owner signer; caller never supplies a command or key."""
    path=Path(path)
    require(path.is_absolute() and path.is_relative_to(ROOT) and path.resolve(strict=True)==path,
        'signing path outside original protected controller root')
    s=path.stat(follow_symlinks=False)
    require(stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and not s.st_mode&0o077,
        'protected root-owned signing input required')
    signature=Path(str(path)+'.sig');require(not os.path.lexists(signature),'signature already exists')
    remaining=(deadline-time.monotonic_ns())/NS;require(remaining>0,'original signing deadline expired')
    process=subprocess.Popen(['/usr/bin/ssh-keygen','-Y','sign','-f',str(KEY),'-n',NAMESPACE,str(path)],
        stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,
        env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
    try:
        out,err=process.communicate(timeout=min(30,remaining))
        require(process.returncode==0 and len(out)<=16384 and len(err)<=16384,'fixed owner signing failed')
        require(time.monotonic_ns()<deadline,'original signing deadline expired')
    except BaseException:
        if process.poll() is None:
            with contextlib.suppress(ProcessLookupError):os.killpg(process.pid,signal.SIGKILL)
            process.wait(timeout=10)
        raise
    finally:
        for stream in (process.stdout,process.stderr):stream.close()
    raw=compaction._root_file(signature,65536)
    require(0<len(raw)<=65536,'bounded protected owner signature required')
    fd=os.open(signature,os.O_RDONLY|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)
    namespaces._sync_directory(signature.parent);return signature


@dataclass(frozen=True)
class Inputs:
    """Qualified caller's bindings; these data do not assert readiness by themselves."""
    base_owner:object
    supervision:object
    sizing:dict
    native_image:runtime.ImageBinding
    clock_image:runtime.ImageBinding
    evidence_helper:runtime.ImageBinding
    support_root:Path
    native_source_root:Path
    native_release_root:Path
    codegen_report:Path
    archive_profile:runtime.RuntimeProfile
    local_history_binding:dict
    operator_revision:str
    operator_profile_sha256:str
    unrelated_reservations:dict


def _validate(inputs):
    require(type(inputs) is Inputs and type(inputs.base_owner) is original._VerifiedOriginal
        and type(inputs.supervision) is compaction._Supervision,'actual original owner and fixed service supervision required')
    require(os.getresuid()==(0,0,0) and threading.current_thread() is threading.main_thread()
        and threading.active_count()==1 and len(list(Path('/proc/self/task').iterdir()))==1,
        'single-threaded full-root controller required')
    inputs.supervision.check();base=inputs.base_owner.view();author.requirements(inputs.sizing)
    archive.sha(inputs.operator_profile_sha256,'qualified operator profile')
    require(inputs.unrelated_reservations==dict(declaration_sha256=DECLARATION_SHA,
        reserved_bytes=8*GIB,reserved_inodes=131072,workspace_committed_bytes=88*GIB,scratch_committed_bytes=88*GIB),
        'exact explicit D362 storage declaration required before source preparation')
    require(type(inputs.operator_revision) is str and len(inputs.operator_revision)==40
        and all(c in '0123456789abcdef' for c in inputs.operator_revision),'clean qualified operator revision required')
    for image,size,sha in ((inputs.native_image,compaction.NATIVE_SIZE,compaction.NATIVE_SHA),
            (inputs.clock_image,compaction.CLOCK_SIZE,compaction.CLOCK_SHA),
            (inputs.evidence_helper,qualification.HELPER_SIZE,qualification.HELPER_SHA)):
        require(type(image) is runtime.ImageBinding and image.size_bytes==size and image.sha256==sha,
            'exact frozen native/auxiliary image bindings required')
    deadline=time.monotonic_ns()+60*NS
    with contextlib.ExitStack() as stack:
        for image in (inputs.native_image,inputs.clock_image,inputs.evidence_helper):
            runtime._pin_image(image,deadline,stack)
    require(type(inputs.archive_profile) is runtime.RuntimeProfile and
        inputs.archive_profile.decoder.implementation_profile_sha256==inputs.sizing['storage']['implementation_profile_sha256'],
        'actual archive runtime differs from exact stand packet')
    runtime._closure_bytes(inputs.archive_profile,deadline)
    for image in (inputs.archive_profile.encoder,inputs.archive_profile.python):runtime._image_bytes(image,deadline)
    require(archive.hash_file(inputs.archive_profile.decoder.zstd_library_path,max_bytes=16*MIB,deadline_ns=deadline).sha256
        ==inputs.archive_profile.decoder.zstd_library_sha256,'actual archive codec bytes changed')
    qualification._codegen(inputs.support_root)
    trust=base.resolutions['S17-EXT-003'].semantic_context['trust']['measurements']
    require(trust['principal']==PRINCIPAL and trust['sshsig_namespace']==NAMESPACE,'original fixed owner trust differs')
    require(ROOT.parent.resolve(strict=True)==ROOT.parent,'canonical original controller parent required')
    return base


def _limits(plan,profile,deadline):
    """Requested engineering caps, not observed platform values."""
    native=launcher.LaunchLimits(plan['budget']['memory_bytes'],plan['budget']['memory_bytes'],
        plan['budget']['max_output_bytes'],1024,16384,120*NS,7200*NS)
    ledger=custody.CustodyLimits(131072,500000,500000,2*MIB,deadline)
    broker=runtime.RuntimeLimits(2*GIB,2*GIB,16*MIB,plan['storage']['maximum_custody_receipt_bytes'],
        16384,10*NS,deadline,deadline,24)
    width=max(max(archive.row_layout(row[key])[1:3])
        for row in plan['blueprint']['captures'] for key in ('warmup_run_id','run_id'))
    block=max(archive.BYTE_BLOCK,archive.ROWS_PER_BLOCK*width)
    canonical=max(row['execution_budget']['max_output_bytes'] for row in plan['captures'])
    decoder=archive.DecodeLimits(MIB,block+MIB,block,plan['storage']['archive_staging_bytes'],
        canonical,canonical//8192+1,1<<profile.decoder.window_log,deadline)
    return native,ledger,broker,decoder


class _MetadataBudget:
    """Spend one600-second budget across preparation and final admission."""
    def __init__(self):self.spent=0;self.started=None
    def start(self):
        require(self.started is None,'metadata clock already running');self.started=time.monotonic_ns()
    def remaining(self):
        used=self.spent+(0 if self.started is None else time.monotonic_ns()-self.started)
        remaining=budgets.EXTERNAL_TIME['public_preflight_ns']-used
        require(remaining>0,'original public preparation budget exhausted');return remaining
    def stop(self):
        require(self.started is not None,'metadata clock is not running')
        self.spent+=time.monotonic_ns()-self.started;self.started=None;self.remaining()
    def deadline(self,window,maximum=None):
        amount=self.remaining() if maximum is None else min(self.remaining(),maximum)
        return min(window['end_monotonic_ns'],time.monotonic_ns()+amount)


def _append(book,input_id,payload,deadline):
    raw=book.prepare_record(input_id=input_id,resolution_id='S180-'+input_id+'-1',payload=payload)
    path=ROOT/(input_id+'-resolution-draft.json');record=_bytes(path,raw);sig=_sign(path,deadline)
    return book.append(record_binding=record,signature_binding=_binding(sig))


def _authorize(plan,view,window,output):
    eight=view.resolutions['S17-EXT-008'].semantic_context;now=time.monotonic_ns();epoch=time.time_ns()//NS
    remaining=window['end_monotonic_ns']-now;require(remaining>0,'original authorization window expired')
    return dict(schema_version=authority.SCHEMA,authorization_id='S180-D310-1-AUTH',session_id='S180-D310-1-SESSION',
        request_id='S180-D310-1-REQUEST',attempt_id='S180-D310-1-ATTEMPT',stand_id=plan['blueprint']['stand_id'],actor=PRINCIPAL,
        trust_context={key:authority.binding(view.resolutions[name]) for key,name in
            (('ext002_resolution','S17-EXT-002'),('ext003_resolution','S17-EXT-003'))},
        plan_sha256=_sha(plan),runtime_binding=eight['runtime_binding'],release_binding=eight['release_binding'],
        prerequisite_bindings=dict(calibration_freeze_sha256=plan['blueprint']['calibration_freeze']['sha256'],
            ext007_resolution_sha256=view.resolutions['S17-EXT-007'].sha256,
            ext008_resolution_sha256=view.resolutions['S17-EXT-008'].sha256,
            ext009_resolution_sha256=view.resolutions['S17-EXT-009'].sha256,
            **{k:eight[k] for k in ('qualification_sha256','compatibility_sha256','runtime_profile_sha256')}),
        evidence_root_binding=output,window_binding=window,issued_at_epoch_seconds=epoch-1,
        expires_at_epoch_seconds=epoch+(remaining+NS-1)//NS+2,permission_scope=dict(authority.PERMISSIONS),
        synthetic_test_only=False,phase18_authority=False)


def _collect(inputs,base,window,metadata):
    owner=namespaces.reserve(blueprint=inputs.sizing['blueprint'],local_history_binding=inputs.local_history_binding,
        base_validation=base,operator_profile_sha256=inputs.operator_profile_sha256,window_binding=window,
        deadline_ns=metadata.deadline(window))
    try:
        metadata.stop()
        post=environment._work_ns(inputs.sizing)
        with author.prepare_sources(namespace_owner=owner,sizing=inputs.sizing,native_image=inputs.native_image,
                deadline_ns=min(window['end_monotonic_ns']-post-1,time.monotonic_ns()+namespaces.SOURCE_NS),
                protected_remaining_ns=post) as authored:
            plan=authored.plan;family=_sha(plan);source_owner=authored.source_owner
            metadata.start();native,ledger,broker,decoder=_limits(plan,inputs.archive_profile,window['end_monotonic_ns'])
            software=compatibility.verify(base_validation=base,plan_sha256=family,
                original_bundle=Path(base.resolutions['S17-EXT-006'].semantic_context['archive_bundle_root']),
                source_root=inputs.native_source_root,release_root=inputs.native_release_root,codegen_report=inputs.codegen_report)
            with stores.ProgramStore(PROGRAM,scope_sha256=plan['storage']['program_scope_sha256'],family_id=family,
                    limits=replace(ledger,deadline_ns=metadata.deadline(window)),ext009_resolution_sha256=None) as store:
                reservation=store.reserve_family()['document']
            with programme.own_programme(plan=plan,window_binding=window,program_root=PROGRAM,custody_limits=ledger,
                    deadline_ns=window['end_monotonic_ns'],preparation_deadline_ns=metadata.deadline(window)) as owned_programme:
                # Source preparation can take hours. Re-observe the actual
                # loaded recovery service before the first hardware change.
                supervision=compaction.verify_supervision(recovery_script=inputs.supervision.script,
                    deadline_ns=metadata.deadline(window))
                config=environment.prospective_config(plan=plan,window=window,operator_revision=inputs.operator_revision)
                with environment.prepare_environment(plan=plan,window=window,operator_config=config) as env:
                    compaction.prepare(environment_owner=env,supervision=supervision)
                    metadata.stop();qualification_deadline=min(window['end_monotonic_ns'],time.monotonic_ns()+1800*NS)
                    clock=clocks.qualify_clocks(environment_owner=env,clock_image=inputs.clock_image,deadline_ns=qualification_deadline)
                    prepared=q15.prepare(environment_owner=env,clock_owner=clock,base_validation=base,
                        operator_profile_sha256=inputs.operator_profile_sha256)
                    prepared.execute(native_image=inputs.native_image,signer=lambda path:_sign(path,qualification_deadline))
                    qualified=qualification.publish(completed_q15=prepared.completed(),helper=inputs.evidence_helper,
                        support_root=inputs.support_root)
                    require(time.monotonic_ns()<qualification_deadline,'original qualification deadline exhausted')
                    metadata.start();deadline=metadata.deadline(window,journal.METADATA_NS)
                    hardware=platform.verify_platform(plan=plan,environment_owner=env,qualification_owner=qualified,
                        compatibility_owner=software,base_validation=base,deadline_ns=deadline)
                    planned=admission.verify_plan(authored_sources=authored,qualification_owner=qualified,platform_owner=hardware,
                        compatibility_owner=software,base_validation=base,program_root=PROGRAM,custody_limits=ledger,
                        operator_profile_sha256=inputs.operator_profile_sha256,deadline_ns=deadline,programme_owner=owned_programme)
                    resource=resources.verify_resources(plan=plan,environment_owner=env,source_owner=source_owner,
                        worker=inputs.native_image,archive_profile=inputs.archive_profile,program_root=PROGRAM,native_limits=native,
                        custody_limits=ledger,unrelated_reservations=inputs.unrelated_reservations,deadline_ns=deadline,
                        programme_owner=owned_programme)
                    # Preserve the actual owned evidence for historical exit;
                    # these bytes cannot construct another live resource owner.
                    plan_evidence=_bytes(ROOT/'qualified-plan-admission.json',planned.report())
                    resource_evidence=_bytes(ROOT/'resource-admission.json',resource.report())
                    semantics=admission.ScopedSemantics(plan_owner=planned,resource_owner=resource)
                    book=journal.ScopedJournal(ROOT/'scoped-journal',base_validation=base,plan=plan,
                        semantic_policy_sha256=admission.POLICY_SHA,semantic_replay=semantics,synthetic_test_only=False)
                    book.initialize()
                    with book:
                        _append(book,'S17-EXT-008',planned.payload,deadline)
                        view=_append(book,'S17-EXT-009',dict(resource_proof_sha256=hashlib.sha256(resource.report()).hexdigest()),deadline)
                        owned_programme.bind_resource_admission(view=view)
                        authorization=_authorize(plan,view,window,reservation['evidence_root_binding'])
                        raw=archive.canonical(authorization);path=ROOT/'pilot-authorization.json';bound=_bytes(path,raw);sig=_sign(path,deadline)
                        authority.verify_authorization(authorization_bytes=raw,signature_path=sig,plan=plan,validation=view)
                        view=_append(book,'S17-EXT-010',dict(authorization=bound,signature=_binding(sig)),deadline)
                        verified=authority.verify_admitted_authorization(authorization_bytes=raw,signature_path=sig,plan=plan,validation=view)
                        admission_binding=_save('admission-complete.json',dict(plan_sha256=family,
                            request_sha256=verified.request_sha256,window_binding=window,
                            plan_evidence=plan_evidence,resource_evidence=resource_evidence,
                            derived_contexts={key:view.resolutions[key].semantic_context
                                for key in ('S17-EXT-008','S17-EXT-009','S17-EXT-010')},
                            live_owner_reconstruction_allowed=False,execution_authority=False,phase18_authority=False))
                        metadata.stop()
                        result=launcher.launch(journal=book,authorization_bytes=raw,signature_path=sig,source_owner=source_owner,
                            native_image=inputs.native_image,archive_profile=inputs.archive_profile,program_root=PROGRAM,
                            broker_limits=broker,custody_limits=ledger,decoder_limits=decoder,limits=native,restore_environment=env)
                        document=result['document']
                        require(document['status']=='NATIVE_COLLECTED_PENDING_SCIENTIFIC_VALIDATION'
                            and document['failure'] is None and document['acknowledged_captures']==180
                            and document['quarantined'] is False,'native family stopped; analysis and retries forbidden')
                        return dict(plan=plan,source_owner=source_owner,environment_owner=env,verified=verified,
                            terminal=result['terminal'],view=view,ledger=ledger,decoder=decoder,
                            admission_binding=admission_binding,authorization_binding=bound,authorization_signature=_binding(sig),
                            source_plan=_binding(author.ROOT/'plan.json'))
    finally:owner.close()


def _run(inputs,base):
    started=time.monotonic_ns();window=dict(boot_id=environment._boot(),start_monotonic_ns=started,
        end_monotonic_ns=started+budgets.planning.DAY_NS)
    metadata=_MetadataBudget();metadata.start()
    ROOT.mkdir(mode=0o700);namespaces._sync_directory(ROOT.parent)
    _save('controller-intent.json',dict(operator_revision=inputs.operator_revision,
        operator_profile_sha256=inputs.operator_profile_sha256,window_binding=window,
        automatic_retry=False,execution_authority=False,phase18_authority=False))
    try:
        collected=_collect(inputs,base,window,metadata)
        # _collect returns only after source descriptors and all collection
        # contexts close. The actual transition proves release and restoration.
        family=_sha(collected['plan'])
        with phase.analysis_phase(source_owner=collected['source_owner'],environment_owner=collected['environment_owner'],
                plan_sha256=family) as analysis_owner:
            final=analysis.analyze_family(phase_owner=analysis_owner,verified_request=collected['verified'],
                terminal_binding=collected['terminal'],program_root=PROGRAM,archive_profile=inputs.archive_profile,
                custody_limits=replace(collected['ledger'],deadline_ns=analysis_owner.deadline_ns),
                decoder_limits=replace(collected['decoder'],deadline_ns=analysis_owner.deadline_ns),
                output_directory=ROOT/'analysis',other_workspace_committed_bytes=inputs.unrelated_reservations['workspace_committed_bytes'],
                other_scratch_committed_bytes=inputs.unrelated_reservations['scratch_committed_bytes'])
        for key,value in dict(schema_version=analysis.SCHEMA,status='VALIDATED_DESCRIPTIVE_FAMILY_PENDING_OPERATIONAL_EXIT',
                archive_originals_inversely_verified=1440,actual_worker_completion_verified=True,original_archive_custody_verified=True,
                original_archive_epochs_unchanged_through_inverse=True,
                final_live_restoration_verified=True,operational_exit_verified=False,inferential_freeze_established=False,
                execution_authority=False,phase18_authority=False).items():
            require(type(final['report'][key]) is type(value) and final['report'][key]==value,
                'independent analysis has no valid complete handoff: '+key)
        require(len(final['report']['original_archive_epochs'])==1440,'all original archive epochs required for service exit')
        inputs.base_owner.view();require(time.monotonic_ns()<window['end_monotonic_ns'],'original24h window expired')
        report=dict(schema_version=SCHEMA,status='VALIDATED_PILOT_PENDING_INDEPENDENT_OPERATIONAL_EXIT',
            operator_revision=inputs.operator_revision,operator_profile_sha256=inputs.operator_profile_sha256,
            plan_sha256=family,request_sha256=collected['verified'].request_sha256,window_binding=window,
            controller_pid=os.getpid(),original_seven=[authority.binding(base.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,8)],
            scoped_resolutions=[authority.binding(collected['view'].resolutions[f'S17-EXT-{i:03d}']) for i in range(8,11)],
            family_validation=final['binding'],family_validation_status=final['report']['status'],
            admission_complete=collected['admission_binding'],pilot_authorization=collected['authorization_binding'],
            pilot_authorization_signature=collected['authorization_signature'],
            scoped_journal=_binding(ROOT/'scoped-journal/journal-3.json'),
            source_plan=collected['source_plan'],
            archive_originals_inversely_verified=final['report']['archive_originals_inversely_verified'],
            original_source_release=collected['source_owner'].released_proof(plan_sha256=family),
            controller_still_running=True,independent_service_exit_verified=False,inferential_freeze_established=False,
            automatic_retries=0,execution_authority=False,phase18_authority=False)
        path=ROOT/'controller-handoff.json';binding=_bytes(path,archive.canonical(report));sig=_sign(path,window['end_monotonic_ns'])
        authority.signatures._verify_signature(archive.canonical(report),sig,base.resolutions['S17-EXT-003'].semantic_context['trust'])
        require(time.monotonic_ns()<window['end_monotonic_ns'],'original window expired at controller handoff')
        return dict(handoff=binding,signature=_binding(sig),report=report)
    except BaseException as error:
        with contextlib.suppress(BaseException):_save('controller-failure.json',dict(failure=str(error)[:4096],
            error_type=type(error).__name__,window_binding=window,automatic_retry=False,stage17_complete=False,
            execution_authority=False,phase18_authority=False))
        raise


def execute_once(inputs):
    """Qualified fixed service only, after complete package/ETA/readiness gates.

    This begins the one operational window and performs real stand actions.
    No standalone entry point or report-file promotion into readiness exists.
    """
    global _CONSUMED
    base=_validate(inputs);require(not _CONSUMED,'controller entry already consumed; no automatic retry')
    require(not os.path.lexists(ROOT),'original controller root already exists; never adopt/reset it')
    _CONSUMED=True
    previous={}
    def interrupted(number,frame):
        # Repeated termination requests must not interrupt the first unwind.
        # Actual native/source supervisors install their own cleanup handlers.
        for selected in previous:signal.signal(selected,signal.SIG_IGN)
        raise ExecutionError('controller interrupted by signal '+str(number))
    try:
        for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):previous[number]=signal.signal(number,interrupted)
        return _run(inputs,base)
    finally:
        for number,handler in previous.items():signal.signal(number,handler)
