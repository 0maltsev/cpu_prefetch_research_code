"""Owned S180 namespace reservation from actual finite historical audits.

Preserves D325's strict auditor and distinguishes only three exact software
sizing declarations. No source generation, qualification, capture or execution
entry point. The qualified outer operator still supplies package/ETA/readiness.
"""
from __future__ import annotations
import contextlib
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import time

import stage17_formal_archive_v1 as archive
import stage17_q16a_continuation_admission_v1 as readers
import stage17_s180_authority_v1 as authority
import stage17_s180_environment_v1 as environment
import stage17_s180_namespace_audit_v1 as audit
import stage17_s180_verified_sources_v1 as sources

ROOT=environment.EVIDENCE.parent/'namespace'
STAND_BASE=environment.EVIDENCE.parents[2]
LOCAL_BASE='/home/omaltsev/research/cpu_prefetch_research_code'
LOCAL_AUDIT_SIZE=12165984
LOCAL_AUDIT_SHA='36b26846c28842645346d3e67959c8a0d7e1a00ea5dfbaeaf2b9bad0f6534311'
DECLARATIONS={
    'docs/evidence/stage17/PILOT-D326-RESOURCES-20261122-01/bounded-sizing.json':
        (3061798,'f7d1f971f49fd1efbda1a4a83eab88fa85c5377d00c194a3242c4bedcdf3088f'),
    'docs/evidence/stage17/PILOT-D329-ENVIRONMENT-20261123-01/managed-sizing-v2.json':
        (3071698,'0269ca1d6fd598d41d3bfce0d7139f7852591a8affe5deb1203789fea7e35448'),
    'docs/evidence/stage17/PILOT-D334-COMPACTION-INTEGRATION-20261123-01/d333-sizing-v3.json':
        (3098878,'2f33f33a070be20f2c6a00f86a51f52c1912bb4393113178a95431b247e1cc86')}
SCHEMA='cpu-prefetch-stage17-s180-namespace-reservation/1'
LOCAL_SCHEMA='cpu-prefetch-stage17-s180-reviewed-local-history/1'
REPORT_BYTES=96*1024**2
CONTROL_BYTES=1024**2
METADATA_RESERVE_BYTES=128*1024**2
METADATA_RESERVE_INODES=16
PREPARATION_METADATA_NS=600*10**9
SOURCE_NS=28800*10**9
_TOKEN=object()


class NamespaceError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise NamespaceError('S180 namespaces: '+message)


def _sha(value):return hashlib.sha256(archive.canonical(value)).hexdigest()


def _before(deadline):
    require(type(deadline) is int and time.monotonic_ns()<deadline,'original namespace deadline expired')


def _ticks():return Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]


def _sync_directory(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)


def _protected(path,maximum):
    with archive.open_regular(path) as stream:
        st=os.fstat(stream.fileno());require(st.st_uid==0 and st.st_nlink==1 and not st.st_mode&0o022,
            'root-owned protected metadata required')
        raw=stream.read(maximum+1)
        require(len(raw)<=maximum and archive.file_stamp(st)==archive.file_stamp(os.fstat(stream.fileno()))
            ==archive.file_stamp(path.stat(follow_symlinks=False)),'bounded stable metadata required')
    return raw


def _save(path,value,maximum=CONTROL_BYTES):
    raw=archive.canonical(value);require(len(raw)<=maximum,'retained namespace metadata bound exceeded')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);require(n>0,'namespace publication made no progress');view=view[n:]
        os.fsync(fd)
    finally:os.close(fd)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fsync(directory)
    finally:os.close(directory)
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _bound(binding):
    raw=_protected(Path(binding['path']),REPORT_BYTES)
    require(len(raw)==binding['size_bytes'] and hashlib.sha256(raw).hexdigest()==binding['sha256'],
        'bound metadata changed')
    return raw


def review_local_history(report,*,blueprint):
    """Pure classification; never registration or proof of a fresh audit call."""
    identities=audit.planned_identities(blueprint)
    require(report['schema_version']==audit.AUDIT_SCHEMA and report['mode']=='local'
        and report['base']==LOCAL_BASE and report['blueprint_sha256']==audit.BLUEPRINT_SHA256
        and report['prospective_identities_sha256']==audit.sha(identities),'original local history scope differs')
    require(not report['errors'] and report['own_prospective_exclusions']==[]
        and all(report[k] is False for k in ('registration_performed','namespace_registration_performed',
            'source_generation_performed','resource_admission_performed','execution_authority','phase18_authority')),
        'incomplete or authority-bearing local history cannot be reviewed')
    require(report['numeric_seeds_collision_scanned'] is True
        and report['limits']==audit.public.asdict(audit.public.Limits())
        and report['checked_files']==len(report['checked_inventory'])
        and report['checked_inventory_sha256']==audit.public.sha(audit.public.canonical(report['checked_inventory']))
        and report['status']==('FAIL' if report['matches'] else 'PASS_SCOPED_HISTORY_AUDIT'),
        'actual bounded local audit inventory/status differs')
    known=[];seen=set();root=Path(__file__).resolve().parents[1]
    for row in report['matches']:
        path=Path(row['path']);require(path.is_relative_to(Path(LOCAL_BASE)),'foreign local declaration locator')
        name=str(path.relative_to(LOCAL_BASE));require(name in DECLARATIONS and name not in seen,
            'unrecognized or duplicate historical namespace match')
        seen.add(name);size,sha=DECLARATIONS[name]
        require(row['size_bytes']==size and row['sha256']==sha
            and set(row['matched'])=={'identity_family:'+blueprint['blueprint_id'],
                'numeric_seed:'+blueprint['master_seed_hex']},'changed prospective declaration match')
        reader=readers.BoundReader();document=reader.document(dict(path=str(root/name),size_bytes=size,sha256=sha));reader.finish()
        require(document['schema_version']==environment.planning.SIZING
            and document['source_count_basis']=='PROSPECTIVE_UPPER_CEILINGS'
            and _sha(document['blueprint'])==audit.BLUEPRINT_SHA256
            and len(document['captures'])==180
            and all(p['source_artifact'] is None for c in document['captures'] for p in c['phases']),
            'reviewed declaration contains generated sources or a concrete execution plan')
        known.append(dict(relative_path=name,size_bytes=size,sha256=sha,
            classification='EXACT_SOFTWARE_SIZING_WITHOUT_ORIGINAL_SOURCES'))
    # Keep the original FAIL and matches intact. The new result distinguishes
    # exact declarations; it never changes the historical auditor's behavior.
    return dict(schema_version=LOCAL_SCHEMA,original_status=report['status'],
        original_observed_at_utc=report['observed_at_utc'],frozen_local_antecedent_only=True,
        original_checked_files=report['checked_files'],original_checked_inventory_sha256=report['checked_inventory_sha256'],
        recognized_prospective_declarations=known,unrecognized_consumption_matches=0,
        selected_history_reviewed=True,global_unused_claim=False,namespace_registration_performed=False,
        source_generation_performed=False,execution_authority=False,phase18_authority=False)


def _local(binding,blueprint):
    readers.fields(binding,'path size_bytes sha256','local historical report binding')
    require(binding['size_bytes']==LOCAL_AUDIT_SIZE and binding['sha256']==LOCAL_AUDIT_SHA,
        'exact actual PC history report required')
    reader=readers.BoundReader();report=reader.document(binding);reader.finish()
    return review_local_history(report,blueprint=blueprint)


def _base(validation,blueprint):
    rows=validation.resolutions
    require(set(rows)=={f'S17-EXT-{i:03d}' for i in range(1,8)},'actual original-seven replay required')
    bindings=[]
    for key,row in sorted(rows.items()):
        require(row.input_id==key,'original replay input identity differs');archive.sha(row.sha256,'original resolution')
        bindings.append(authority.binding(row))
    context=rows['S17-EXT-007'].semantic_context
    require(rows['S17-EXT-002'].semantic_context['stand_id']==blueprint['stand_id']
        and rows['S17-EXT-007'].sha256==blueprint['ext007_resolution']['sha256']
        and context.get('calibration_scope')=='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY'
        and context.get('data_provenance_accepted') is True
        and context.get('legacy_statistical_freeze_satisfied') is False,'actual descriptive predecessor differs')
    return bindings


@dataclass(frozen=True)
class _GenerationPermit:
    owner: object
    deadline_ns: int
    intent_sha256: str


class _NamespaceOwner:
    def __init__(self,*,token,directory,lock,intent,bindings,local_binding):
        require(token is _TOKEN,'actual owned reservation required')
        self.directory=directory;self.lock=lock;self._intent=archive.canonical(intent)
        self._bindings=archive.canonical(dict(files=bindings));self._local=archive.canonical(local_binding)
        self.pid=os.getpid();self.ticks=_ticks();self.failed=False;self.closed=False
        self.generation=None;self.source_owner=None;self._source_binding=None;self._source_directory=None
        self._identity=(os.fstat(directory).st_dev,os.fstat(directory).st_ino)
        self._lock_identity=(os.fstat(lock).st_dev,os.fstat(lock).st_ino)

    def _add(self,binding):
        rows=archive.parse_json(self._bindings)['files'];rows.append(binding);self._bindings=archive.canonical(dict(files=rows))

    def _check(self):
        require(not self.closed and not self.failed and os.getpid()==self.pid and _ticks()==self.ticks,
            'namespace owner is closed, failed or belongs to another process')
        intent=archive.parse_json(self._intent);environment._window(intent['window_binding'])
        s=ROOT.stat(follow_symlinks=False)
        require(ROOT.resolve(strict=True)==ROOT and stat.S_ISDIR(s.st_mode) and s.st_uid==0
            and stat.S_IMODE(s.st_mode)==0o700 and (s.st_dev,s.st_ino)==self._identity
            and (os.fstat(self.directory).st_dev,os.fstat(self.directory).st_ino)==self._identity,
            'original namespace directory identity differs')
        lock=ROOT/'owner.lock';ls=lock.stat(follow_symlinks=False)
        require((ls.st_dev,ls.st_ino)==self._lock_identity==(os.fstat(self.lock).st_dev,os.fstat(self.lock).st_ino)
            and stat.S_ISREG(ls.st_mode) and ls.st_uid==0 and ls.st_nlink==1 and ls.st_size==0
            and stat.S_IMODE(ls.st_mode)==0o600,
            'original namespace lease identity differs')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        files=archive.parse_json(self._bindings)['files'];expected={Path(r['path']).name for r in files}|{'owner.lock'}
        if self.generation is not None:
            expected.add('sources');path=ROOT/'sources';source_dir=path.stat(follow_symlinks=False)
            require(path.resolve(strict=True)==path and stat.S_ISDIR(source_dir.st_mode) and source_dir.st_uid==0
                and stat.S_IMODE(source_dir.st_mode)==0o700
                and (source_dir.st_dev,source_dir.st_ino)==self._source_directory,'original source directory identity changed')
        require({p.name for p in ROOT.iterdir()}==expected,'namespace metadata inventory changed')
        for row in files:_bound(row)
        local=archive.parse_json(self._local);_bound(local)
        if self.source_owner is not None:
            record=archive.parse_json(_bound(archive.parse_json(self._source_binding)))
            proof=self.source_owner.proof(plan_sha256=record['plan_sha256'])
            require(proof['generation_report_sha256']==record['source_generation_report_sha256'],
                'original bound source bank changed')
            require(set((ROOT/'sources').iterdir())=={Path(p) for p in record['source_paths']},
                'bound source bank inventory changed')
        return intent

    def _failure(self,error):
        self.failed=True
        try:
            st=ROOT.stat(follow_symlinks=False)
            if not self.closed and (st.st_dev,st.st_ino)==self._identity and not os.path.lexists(ROOT/'failure.json'):
                _save(ROOT/'failure.json',dict(schema_version=SCHEMA,status='FAILED_NO_RETRY',failure=str(error)[:4096],
                    source_generation_consumed=self.generation is not None,execution_authority=False,phase18_authority=False))
        except BaseException:pass  # Never mutate an unknown replacement directory.

    def proof(self):
        try:
            intent=self._check();return dict(schema_version=SCHEMA,window_binding=intent['window_binding'],
                blueprint_sha256=intent['blueprint_sha256'],base_resolutions=intent['base_resolutions'],
                operator_profile_sha256=intent['operator_profile_sha256'],namespace_reservation_verified=True,
                planned_namespaces_including_root=52,planned_phase_identities=360,planned_source_identities=36,
                stand_history_at_reservation_verified=True,frozen_local_antecedent_verified=True,global_unused_claim=False,
                source_generation_consumed=self.generation is not None,source_bank_binding=
                    None if self._source_binding is None else archive.parse_json(self._source_binding),
                namespace_metadata_upper_bytes=METADATA_RESERVE_BYTES,namespace_metadata_upper_inodes=METADATA_RESERVE_INODES,
                resource_admission_performed=False,full_ext008_admission=False,execution_authority=False,phase18_authority=False)
        except BaseException as error:self._failure(error);raise

    def consume_generation(self,*,deadline_ns,protected_remaining_ns):
        try:
            intent=self._check();require(self.generation is None,'source generation already consumed')
            now=time.monotonic_ns();require(type(deadline_ns) is int and now<deadline_ns<=now+SOURCE_NS
                and type(protected_remaining_ns) is int and protected_remaining_ns>0
                and deadline_ns+protected_remaining_ns<intent['window_binding']['end_monotonic_ns'],
                'finite source deadline omits declared remaining work or exceeds original window')
            binding=_save(ROOT/'generation-intent.json',dict(schema_version=SCHEMA,kind='ONE_SOURCE_GENERATION_CONSUMED',
                started_monotonic_ns=now,deadline_monotonic_ns=deadline_ns,protected_remaining_ns=protected_remaining_ns,
                blueprint_sha256=intent['blueprint_sha256'],window_binding=intent['window_binding'],
                operator_profile_sha256=intent['operator_profile_sha256'],source_count=36,automatic_retry=False,
                execution_authority=False,phase18_authority=False))
            self._add(binding);self.generation=_GenerationPermit(self,deadline_ns,binding['sha256'])
            (ROOT/'sources').mkdir(mode=0o700);source_dir=(ROOT/'sources').stat(follow_symlinks=False)
            self._source_directory=(source_dir.st_dev,source_dir.st_ino);_sync_directory(ROOT)
            self.proof();return self.generation
        except BaseException as error:self._failure(error);raise

    def bind_sources(self,*,permit,source_owner,plan):
        try:
            intent=self._check();require(permit is self.generation and type(permit) is _GenerationPermit
                and permit.owner is self and self.source_owner is None,'original single-use generation permit required')
            _before(permit.deadline_ns);require(type(source_owner) is sources._VerifiedSources,'actual verified source owner required')
            family=environment.planning.sha(plan)
            require(_sha(plan['blueprint'])==intent['blueprint_sha256'],'source bank blueprint differs')
            proof=source_owner.proof(plan_sha256=family)
            require(proof['valid_until_monotonic_ns']==intent['window_binding']['end_monotonic_ns'],
                'source ownership does not preserve the original full window')
            report=archive.parse_json(source_owner.generation_report(plan_sha256=family))
            identities=audit.planned_identities(plan['blueprint']);expected={tuple(r[k] for k in
                ('placement','working_set_class','load_level','phase')):r for r in identities['sources']}
            require(len(report['sources'])==36,'complete source bank required')
            paths=set()
            for row in report['sources']:
                key=tuple(row[k] for k in ('placement','working_set_class','load_level','phase'));declared=expected.pop(key)
                require(row['namespace_id']==declared['namespace_id'] and row['seed_id']==declared['seed_id']
                    and row['schedule_id']==declared['schedule_id'] and row['derivation_record_id']==declared['derivation_record_id'],
                    'source seed/namespace/derivation differs from reserved identities')
                for kind,identity in (('binary','artifact_id'),('envelope','envelope_artifact_id'),('derivation','derivation_artifact_id')):
                    path=Path(row[kind]['path']);s=path.stat(follow_symlinks=False)
                    require(path.parent==ROOT/'sources' and path.resolve(strict=True)==path and s.st_uid==0
                        and s.st_nlink==1 and row[kind]['artifact_id']==declared[identity],
                        'source file was not exclusively published in the owned bank')
                    paths.add(path)
            require(not expected and len(paths)==108 and {p for p in (ROOT/'sources').iterdir()}==paths,
                'owned source directory inventory differs')
            _before(permit.deadline_ns)
            binding=_save(ROOT/'source-binding.json',dict(schema_version=SCHEMA,plan_sha256=family,
                generation_intent_sha256=permit.intent_sha256,source_generation_report_sha256=proof['generation_report_sha256'],
                source_paths=sorted(str(p) for p in paths),
                completed_monotonic_ns=time.monotonic_ns(),generation_deadline_ns=permit.deadline_ns,
                namespace_reservation_verified=True,scoped_source_membership_verified=True,
                execution_authority=False,phase18_authority=False))
            _before(permit.deadline_ns)
            self._add(binding);self._source_binding=archive.canonical(binding);self.source_owner=source_owner
            result=self.proof();_before(permit.deadline_ns);return result
        except BaseException as error:self._failure(error);raise

    def close(self):
        if self.closed:return
        self.closed=True;errors=[]
        for fd,identity,locked in ((self.lock,self._lock_identity,True),(self.directory,self._identity,False)):
            try:
                st=os.fstat(fd)
                require((st.st_dev,st.st_ino)==identity,'owned namespace descriptor changed; not closing replacement')
                if locked and os.getpid()==self.pid:fcntl.flock(fd,fcntl.LOCK_UN)
                os.close(fd)
            except BaseException as error:errors.append(str(error))
        require(not errors,'; '.join(errors))


def reserve(*,blueprint,local_history_binding,base_validation,operator_profile_sha256,window_binding,deadline_ns):
    """Only after complete prospective package/ETA gates; starts no worker."""
    require(os.geteuid()==0,'qualified root owner required')
    identities=audit.planned_identities(blueprint);archive.sha(operator_profile_sha256,'qualified outer profile')
    base=_base(base_validation,blueprint);environment._window(window_binding);_before(deadline_ns)
    require(deadline_ns-time.monotonic_ns()<=PREPARATION_METADATA_NS and deadline_ns<=window_binding['end_monotonic_ns'],
        'namespace preparation exceeds original metadata/window bounds')
    local=_local(local_history_binding,blueprint)
    require(ROOT.parent.resolve(strict=True)==ROOT.parent and ROOT.parent.stat().st_uid==0
        and stat.S_IMODE(ROOT.parent.stat().st_mode)==0o700,'fixed protected namespace parent required')
    ROOT.mkdir(mode=0o700)  # Existing success/failure is never adopted or erased.
    _sync_directory(ROOT.parent)
    directory=lock=None;owner=None
    try:
        directory=os.open(ROOT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        lock=os.open(ROOT/'owner.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        os.fsync(lock)
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        intent=dict(schema_version=SCHEMA,blueprint_sha256=audit.BLUEPRINT_SHA256,identities_sha256=audit.sha(identities),
            base_resolutions=base,operator_profile_sha256=operator_profile_sha256,window_binding=window_binding,
            owner_pid=os.getpid(),owner_start_ticks=_ticks(),local_history=local_history_binding,
            local_history_review=local,namespace_registration_performed=True,source_generation_performed=False,
            automatic_retry=False,execution_authority=False,phase18_authority=False)
        original=_save(ROOT/'intent.json',intent)
        # No prospective exclusions are supplied; all selected stand history is
        # checked by the original strict D325 auditor after claim-root creation.
        report=audit.audit('stand',STAND_BASE,blueprint)
        require(report['status']=='PASS_SCOPED_HISTORY_AUDIT' and not report['matches'] and not report['errors'],
            'stand history contains a collision, missing evidence or audit failure')
        _before(deadline_ns);history=_save(ROOT/'stand-history.json',report,REPORT_BYTES)
        ready=_save(ROOT/'ready.json',dict(schema_version=SCHEMA,intent=original,stand_history=history,
            local_history_sha256=local_history_binding['sha256'],namespace_reservation_verified=True,
            selected_history_scope_only=True,execution_authority=False,phase18_authority=False))
        owner=_NamespaceOwner(token=_TOKEN,directory=directory,lock=lock,intent=intent,
            bindings=[original,history,ready],local_binding=local_history_binding)
        owner.proof();return owner
    except BaseException as error:
        if owner is not None:owner._failure(error);owner.close()
        else:
            try:
                if directory is not None:
                    st=ROOT.stat(follow_symlinks=False);held=os.fstat(directory)
                    if (st.st_dev,st.st_ino)==(held.st_dev,held.st_ino):
                        _save(ROOT/'failure.json',dict(schema_version=SCHEMA,status='FAILED_NO_RETRY',failure=str(error)[:4096],
                            source_generation_performed=False,execution_authority=False,phase18_authority=False))
            finally:
                if lock is not None:os.close(lock)
                if directory is not None:os.close(directory)
        raise
