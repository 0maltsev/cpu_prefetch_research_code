"""S180 parent attempt consumption and verified archive acknowledgement.

The qualified launcher supplies an actual D319 VerifiedRequest from fresh D322
semantic replay. This library does not produce missing semantic facts, verify a
runtime package, spawn the measurement worker or restore CPU isolation. Its
receipt never promotes archive custody to scientific validity or Stage18.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import os
from pathlib import Path
import stat
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_s180_authority_v1 as authority
import stage17_s180_archive_channel_v1 as channels
import stage17_s180_archive_broker_v1 as brokers
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_archive_registry_v1 as registry

ATTEMPT_PREFIX='s180-parent-attempt-'
ATTEMPT_SCHEMA='cpu-prefetch-stage17-s180-parent-attempt/1'
RECEIPT_SCHEMA='cpu-prefetch-stage17-s180-parent-custody/1'
PARENT_RECORD_LIMIT=64*1024


class ParentError(archive.ArchiveError):
    pass


def require(value,message):
    if not value:raise ParentError('S180 parent: '+message)


def _documents(verified):
    require(type(verified) is authority.VerifiedRequest,'actual immutable signature/request value required')
    authorization=archive.parse_json(verified.authorization_bytes)
    request=archive.parse_json(verified.request_bytes)
    require(authorization['schema_version']==authority.SCHEMA and request['schema_version']==authority.REQUEST_SCHEMA,
        'original authorization/request schema differs')
    require(authorization['synthetic_test_only'] is False and authorization['phase18_authority'] is False
        and request['synthetic_test_only'] is False and request['phase18_authority'] is False,
        'production scoped request required; no synthetic selector')
    for key in ('session_id','request_id','attempt_id','authorization_id','stand_id','runtime_binding','release_binding'):
        authority.same(request[key],authorization[key],'parent original '+key)
    authority.same(request['prerequisite_bindings'],dict(authorization['prerequisite_bindings'],
        ext010_authorization_sha256=verified.authorization_sha256),'parent admitted prerequisites')
    require(authority.sha(archive.canonical(request['plan']))==authorization['plan_sha256'],
        'original admitted plan differs')
    authority._window_shape(authorization)
    authority._sample_window(authorization)
    return authorization,request


def _root(directory_fd,authorization):
    st=os.fstat(directory_fd);root=authorization['evidence_root_binding']
    require(stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and not st.st_mode&0o022
        and (st.st_dev,st.st_ino)==(root['device'],root['inode']),'held output root differs')
    path=Path(root['absolute_path'])
    require(path.is_absolute() and str(path)==str(path.resolve(strict=True))
        and path.name==authorization['plan_sha256'] and path.parent.name=='working',
        'original output path is unsafe')
    current=path.stat(follow_symlinks=False)
    require((current.st_dev,current.st_ino)==(st.st_dev,st.st_ino),'output root path changed')


def _attempt_name(family):
    return ATTEMPT_PREFIX+archive.sha(family,'parent family')+'.json'


def _record_bytes(document):
    raw=archive.canonical(document)
    require(len(raw)<=PARENT_RECORD_LIMIT,'parent metadata exceeds reserved bound')
    return raw


def _attempt_document(verified,authorization,request):
    return dict(schema_version=ATTEMPT_SCHEMA,request_sha256=verified.request_sha256,
        authorization_sha256=verified.authorization_sha256,plan_sha256=authorization['plan_sha256'],
        session_id=request['session_id'],attempt_id=request['attempt_id'],
        prerequisite_bindings=request['prerequisite_bindings'],window_binding=authorization['window_binding'],
        runtime_binding=request['runtime_binding'],attempts=1,automatic_retries=0,
        scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)


def consume_attempt(*,verified,store):
    """Consume one already-admitted family in quota-accounted metadata.

    Call only after full current launch admission, before starting the worker.
    A partial marker also consumes the attempt and requires explicit recovery.
    The existing broker lock serializes attempts; no family is created/adopted.
    """
    authorization,request=_documents(verified)
    store._check()
    require(type(store) is stores.ProgramStore and store.family_id==authorization['plan_sha256']
        and store.family_id in store._families,'original admitted family must already exist')
    require(store.ext009_resolution_sha256==request['prerequisite_bindings']['ext009_resolution_sha256'],
        'original resource admission differs')
    store.prepare_family(store.family_id)
    fd=os.open(store.working,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        _root(fd,authorization)
        for name in ('s180-session-entry.json','s180-session-result.json'):
            try:os.stat(name,dir_fd=fd,follow_symlinks=False)
            except FileNotFoundError:continue
            raise ParentError('S180 parent: native evidence already exists')
        return store.retain_metadata(_attempt_name(store.family_id),
            _record_bytes(_attempt_document(verified,authorization,request)))
    finally:os.close(fd)


class CheckpointParent:
    """One exact admitted worker and a monotonic, fail-stop checkpoint stream.

    No input report can choose a codec, callback, semantic policy or executable.
    The qualified caller owns and pins the worker, runtime profile and actual
    supervisor lease. This component verifies the original durable attempt and
    actual native image, then performs the full broker/ledger/ACK sequence.
    """
    def __init__(self,*,verified,channel,program_root,profile,limits,custody_limits,
                 decoder_limits,identity_model,platform_guard=None):
        self.platform_guard=platform_guard
        try:
            if platform_guard is not None:
                from stage17_s180_compaction_v1 import _OwnedCompaction
                require(type(platform_guard) is _OwnedCompaction,'owned D333 guard required')
            self._initialize(verified=verified,channel=channel,program_root=program_root,profile=profile,
                limits=limits,custody_limits=custody_limits,decoder_limits=decoder_limits,identity_model=identity_model)
        except BaseException:
            self.stopped=True
            if type(channel) is channels.ArchiveChannel:channel.stopped=True
            raise

    def _initialize(self,*,verified,channel,program_root,profile,limits,custody_limits,
                    decoder_limits,identity_model):
        authorization,request=_documents(verified)
        if self.platform_guard is not None:
            require(self.platform_guard.owner['plan_sha256']==authorization['plan_sha256']
                and self.platform_guard.owner['window']==authorization['window_binding'],
                'guard belongs to another admitted family/window')
        require(type(channel) is channels.ArchiveChannel,'fixed S180 archive channel required')
        require(type(profile) is runtime.RuntimeProfile and type(limits) is runtime.RuntimeLimits
            and type(custody_limits) is custody.CustodyLimits and type(decoder_limits) is archive.DecodeLimits,
            'fixed runtime and finite limits required')
        plan=request['plan'];storage=plan['storage']
        require(channel.request_sha256==verified.request_sha256
            and channel.plan_sha256==authorization['plan_sha256']
            and channel.session_id==request['session_id']
            and channel.program_scope_sha256==storage['program_scope_sha256']
            and channel.ordinal==0 and channel.pending is None and not channel.stopped,
            'channel scope or initial state differs')
        require(profile.decoder.implementation_profile_sha256==storage['implementation_profile_sha256'],
            'archive profile differs from admitted plan')
        require(len(plan['captures'])==180 and all('execution_budget' in e for e in plan['captures']),
            'complete capture bounds required')
        _root(channel.directory_fd,authorization)
        require(Path(program_root).is_absolute()
            and Path(program_root)==Path(authorization['evidence_root_binding']['absolute_path']).parent.parent,
            'programme root differs from original admitted output')
        expected=archive.canonical(_attempt_document(verified,authorization,request))
        self._attempt_path=Path(program_root)/'metadata'/_attempt_name(authorization['plan_sha256'])
        attempt=archive.open_regular(self._attempt_path)
        fd=attempt.fileno()
        try:
            st=os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_uid==os.geteuid()
                and not st.st_mode&0o077 and st.st_size==len(expected)
                and os.pread(fd,PARENT_RECORD_LIMIT+1,0)==expected,'original consumed attempt differs')
            self._attempt_identity=archive.file_stamp(st)
        finally:attempt.close()
        channel.worker._alive()
        # /proc/<pinned-pid>/exe intentionally follows the kernel-owned exe link,
        # not a caller-selected executable pathname. Recheck held PIDFD identity.
        fd=os.open(f'/proc/{channel.worker.pid}/exe',os.O_RDONLY|os.O_CLOEXEC)
        try:
            image=request['runtime_binding'];st=os.fstat(fd)
            require(stat.S_ISREG(st.st_mode) and st.st_size==image['size_bytes'] and 0<st.st_size<=256*1024**2,
                'actual worker image extent differs')
            digest=hashlib.sha256();offset=0
            while offset<st.st_size:
                require(time.monotonic_ns()<limits.final_deadline_ns,'worker image hash deadline')
                block=os.pread(fd,min(65536,st.st_size-offset),offset)
                require(bool(block),'actual worker image truncated');digest.update(block);offset+=len(block)
            require(archive.file_stamp(os.fstat(fd))==archive.file_stamp(st)
                and digest.hexdigest()==image['sha256'],'actual pinned worker image differs')
        finally:os.close(fd)
        channel.worker._alive()
        self.verified,self.authorization,self.request=verified,authorization,request
        self.channel,self.program_root,self.profile=channel,Path(program_root),profile
        self.limits,self.custody_limits,self.decoder_limits=limits,custody_limits,decoder_limits
        self.identity_model,self.stopped=identity_model,False

    def _guard(self):
        authority._sample_window(self.authorization)
        _root(self.channel.directory_fd,self.authorization)
        st=self._attempt_path.stat(follow_symlinks=False)
        require(archive.file_stamp(st)==self._attempt_identity,'consumed attempt changed')
        self.channel.worker._alive()

    def checkpoint(self,*,deadline_ns):
        require(not self.stopped,'checkpoint parent stopped; no retry permitted')
        try:
            self._guard()
            deadline=min(archive.uint(deadline_ns,'checkpoint deadline',positive=True),
                self.limits.final_deadline_ns,self.authorization['window_binding']['end_monotonic_ns'])
            pending=self.channel.receive(deadline_ns=deadline)
            platform_after=(None if self.platform_guard is None else
                self.platform_guard.check(boundary='AFTER_CAPTURE',ordinal=pending.ordinal))
            entry=self.request['plan']['captures'][pending.ordinal]
            require(pending.deadline_ns-time.monotonic_ns()<=entry['execution_budget']['archive_ns'],
                'capture archive deadline exceeds its admitted interval')
            deadline=min(deadline,pending.deadline_ns)
            limits=replace(self.limits,deadline_ns=deadline)
            custody_limits=replace(self.custody_limits,deadline_ns=min(deadline,self.custody_limits.deadline_ns))
            decoder_limits=replace(self.decoder_limits,deadline_ns=min(deadline,self.decoder_limits.deadline_ns))
            storage=self.request['plan']['storage'];family=self.authorization['plan_sha256']
            with brokers.ArchiveBrokerClient(profile=self.profile,limits=limits,
                    identity_model=self.identity_model,native_worker=self.channel.worker) as client:
                outcome=client.archive_capture(program_root=self.program_root,scope_sha256=storage['program_scope_sha256'],
                    family_id=family,custody_limits=custody_limits,request_document=self.request,
                    capture_ordinal=pending.ordinal,checkpoint=custody.BoundFile(**pending.binding))
                processes=client.actual_processes
            cleanup=outcome.cleanup
            require(cleanup.returncode==0 and cleanup.leader_reaped and cleanup.process_group_gone
                and not cleanup.descendants_detected_after_leader_exit and not cleanup.cleanup_deadline_overrun
                and not cleanup.leader_wait_timed_out,'broker cleanup is not normal and complete')
            self._guard()
            with stores.ProgramStore(self.program_root,scope_sha256=storage['program_scope_sha256'],
                    family_id=family,ext009_resolution_sha256=self.request['prerequisite_bindings']['ext009_resolution_sha256'],
                    limits=custody_limits) as store:
                require(family in store._families,'original family reservation is absent')
                store.prepare_family(family)
                require(store.working==Path(self.authorization['evidence_root_binding']['absolute_path']),
                    'custody family belongs to another output path')
                proof=registry.verify_capture_metadata(store=store,capture=brokers.capture_contract(self.request,pending.ordinal),
                    checkpoint_binding=pending.binding,receipt_binding=asdict(outcome.receipt),
                    decoder_profile=self.profile.decoder,decoder_limits=decoder_limits)
                record=store.read_verified_record(outcome.receipt_ledger_record)
                require(record['kind']=='CUSTODY_RECEIPT' and record['payload']==dict(family_id=family,
                    checkpoint_sha256=pending.binding['sha256'],receipt=asdict(outcome.receipt)),
                    'broker custody registration differs from actual ledger')
                require(processes==1+3*len(proof['artifacts']),'broker child count differs from fixed encoder/readback sequence')
                expected_status='ARCHIVED_AND_RELEASED' if proof['continuation_allowed'] else 'ARCHIVED_FAILED_EVIDENCE'
                require(outcome.status==expected_status,'broker/independent registry status differs')
                self._guard()
                platform_release=(None if self.platform_guard is None else
                    self.platform_guard.check(boundary='BEFORE_RELEASE',ordinal=pending.ordinal))
                document=dict(schema_version=RECEIPT_SCHEMA,request_sha256=self.verified.request_sha256,
                    plan_sha256=family,execution_ordinal=pending.ordinal,checkpoint=pending.binding,
                    custody_receipt=asdict(outcome.receipt),custody_registration=asdict(outcome.receipt_ledger_record),
                    broker_processes=processes,broker_cleanup=runtime._jsonable(asdict(cleanup)),
                    status=outcome.status,scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
                if self.platform_guard is not None:
                    document['platform_guard']=dict(after_capture=platform_after,before_release=platform_release)
                parent_receipt=store.retain_metadata(f's180-parent-{family}-e{pending.ordinal}.json',_record_bytes(document))
            require(time.monotonic_ns()<deadline,'custody replay/publication exceeded original archive deadline')
            if self.platform_guard is not None:
                self.platform_guard.check(boundary='BEFORE_RELEASE',ordinal=pending.ordinal)
            self.channel.acknowledge(asdict(outcome.receipt),deadline_ns=deadline)
            self.stopped=not proof['continuation_allowed']
            return dict(parent_receipt=asdict(parent_receipt),status=outcome.status,
                capture_ordinal=pending.ordinal,continuation_allowed=not self.stopped,
                scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
        except BaseException:
            self.stopped=True
            self.channel.stopped=True
            raise
