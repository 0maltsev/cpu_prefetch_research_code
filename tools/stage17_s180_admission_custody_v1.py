"""One actual programme replay/lease through short S180 admission.

No source generation, qualification, attempt consumption or native launch.
Keep the original lock and recheck immutable filesystem stamps instead of
reparsing every historical JSON record at each signed metadata operation.
"""
from __future__ import annotations
import contextlib
from dataclasses import asdict
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import time

import stage17_formal_archive_v1 as archive
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_authority_v1 as authority

SCHEMA='cpu-prefetch-stage17-s180-owned-admission-programme/1'
METADATA_BYTES=2*1024**2
METADATA_INODES=16
_TOKEN=object()
_QUARANTINED_LOCK_STREAMS=[]


class ProgrammeError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise ProgrammeError('S180 admission programme: '+message)


def _stamp(path):
    st=path.stat(follow_symlinks=False)
    require((stat.S_ISDIR(st.st_mode) or stat.S_ISREG(st.st_mode))
        and not st.st_mode&0o022,'protected original programme inventory required')
    return (*archive.file_stamp(st),st.st_mode,st.st_uid)


class _AdmissionStore(stores.ProgramStore):
    def __init__(self,*args,reading_deadline_ns=None,**kwargs):
        self._read_stamps={};self._allow_admission_write=False
        self._reading_deadline_ns=kwargs['limits'].deadline_ns if reading_deadline_ns is None else reading_deadline_ns
        super().__init__(*args,**kwargs)

    def _check(self):
        require(time.monotonic_ns()<self._reading_deadline_ns,'original programme reading deadline expired')
        return super()._check()

    def _read_bound(self,path,binding,maximum):
        require(time.monotonic_ns()<self._reading_deadline_ns,'original programme reading deadline expired')
        before=_stamp(path);raw=super()._read_bound(path,binding,maximum)
        require(before==_stamp(path),'programme metadata changed across original read')
        previous=self._read_stamps.setdefault(path,before)
        require(previous==before,'original replayed metadata stamp changed')
        return raw

    def _before_write(self,amount):
        require(self._allow_admission_write,'admission programme is read-only except the exact EXT009 binding')
        return super()._before_write(amount)


class _OwnedProgramme:
    def __init__(self,*,token,store,plan,window,deadline):
        require(token is _TOKEN,'actual held and replayed programme required')
        self._store=store;self._plan=archive.canonical(plan);self.window=archive.canonical(window)
        self.deadline=deadline;self.pid=os.getpid();self.closed=False;self.failed=False;self.released=False
        self.family=hashlib.sha256(self._plan).hexdigest();self.root=store.root
        # The accepted historical programme may belong to the research UID;
        # root is the current controller, not an invented historical owner.
        # Preserve and stamp-check actual owners/modes without chown/chmod.
        self._root_owner_uid=self.root.stat().st_uid
        self._lock_owner_uid=(self.root/'broker.lock').stat().st_uid
        self._lock_identity=archive.file_stamp(os.fstat(store._lock.fileno()))
        self._identity=(self.root.stat().st_dev,self.root.stat().st_ino)
        self._snapshot=None;self._report=None;self._ext009=None

    def _scan(self):
        """Bounded complete programme tree, including normally exempt raw files.

        Stat/read no payload bytes. Snapshot scope is this held programme only.
        Existing full physical accounting retains its distinct quota policy.
        """
        result={};pending=[(self.root,0)]
        maximum=self._store.limits.max_inventory_files+len(self._store._families)+16
        while pending:
            path,depth=pending.pop();require(time.monotonic_ns()<self.deadline,'original programme ownership deadline expired')
            require(depth<=8 and len(result)<maximum,'programme snapshot entry/depth bound exceeded')
            value=_stamp(path);result[path]=value
            if stat.S_ISDIR(value[-2]):
                with os.scandir(path) as entries:
                    for entry in entries:
                        require(len(result)+len(pending)<maximum,'programme snapshot entry bound exceeded')
                        pending.append((Path(entry.path),depth+1))
                require(_stamp(path)==value,'programme directory changed during inventory')
        return result

    def _check(self):
        require(not self.closed and not self.failed and os.getpid()==self.pid,'programme owner closed, failed or belongs to another process')
        require(time.monotonic_ns()<self.deadline,'original programme ownership deadline expired')
        store=self._store;store._check();fd=store._lock.fileno()
        require(archive.file_stamp(os.fstat(fd))==self._lock_identity==archive.file_stamp((self.root/'broker.lock').stat(follow_symlinks=False)),
            'original programme lock descriptor or inode changed')
        require(self.root.resolve(strict=True)==self.root and (self.root.stat().st_dev,self.root.stat().st_ino)==self._identity,
            'original programme root identity changed')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        for i,(path,value) in enumerate(self._snapshot.items()):
            if i%256==0:require(time.monotonic_ns()<self.deadline,'original programme ownership deadline expired')
            require(_stamp(path)==value,'held programme inventory or file stamp changed')
        # Every original directory's ctime/mtime/inode is checked too: adding,
        # removing or renaming an unlisted object changes its parent stamp.
        for path,value in store._read_stamps.items():require(self._snapshot.get(path)==value,'original replayed file changed since byte verification')
        return store

    def check(self,*,plan_sha256):
        try:
            require(plan_sha256==self.family,'original programme plan differs')
            store=self._check()
            return dict(schema_version=SCHEMA,plan_sha256=self.family,program_scope_sha256=store.scope_sha256,
                ledger_records=store._sequence,ledger_tip_sha256=store._previous,original_replay_count=1,
                original_lock_still_held=True,complete_programme_stamps_verified=True,
                inventory_objects=len(self._snapshot),ext009_binding=self._ext009,
                source_preparation_performed=False,full_resource_admission=False,execution_authority=False,phase18_authority=False)
        except BaseException:self.failed=True;raise

    @contextlib.contextmanager
    def inspect(self,*,plan_sha256):
        self.check(plan_sha256=plan_sha256)
        try:
            yield self._store
            self.check(plan_sha256=plan_sha256)
        except BaseException:self.failed=True;raise

    def report(self):
        require(self._report is not None,'no actual programme report exists');return bytes(self._report)

    def bind_resource_admission(self,*,view):
        """One exact metadata publication after actually signed scoped EXT009."""
        import stage17_s180_journal_v1 as journal
        try:
            self.check(plan_sha256=self.family)
            require(type(view) is journal.JournalView and not view.synthetic_test_only and view.generation==2
                and set(view.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,10)} and self._ext009 is None,
                'original signed EXT009 view and unused binding required')
            row=view.resolutions['S17-EXT-009'];prior=view.resolutions['S17-EXT-008'].semantic_context
            context=row.semantic_context
            require(context['scope_id']==authority.RESOURCE_SCOPE and context['plan_sha256']==self.family
                and context['resource_admission_status']=='ADMITTED' and context['phase18_authority'] is False
                and prior['plan_sha256']==self.family and prior['scope_id']==authority.PLAN_SCOPE,
                'signed scoped plan/resource admission differs')
            reservation,_=self._store.inspect_reservation()
            for value in (context,prior):
                require(archive.canonical(value['window_binding'])==self.window
                    and value['evidence_root_binding']==reservation['evidence_root_binding'],'signed resource output/window differs')
            archive.sha(row.sha256,'actual EXT009 resolution')
            before=dict(self._snapshot);path=self.root/'metadata'/('s180-admission-'+self.family+'.json')
            require(path not in before and not os.path.lexists(path),'resource binding already exists or is orphaned')
            self._store.ext009_resolution_sha256=row.sha256
            self._store._allow_admission_write=True
            try:binding=self._store.bind_admission()
            finally:self._store._allow_admission_write=False
            after=self._scan();expected=set(before)|{path}
            require(set(after)==expected,'resource publication changed unexpected programme membership')
            for name,value in before.items():
                if name!=self.root/'metadata':require(after[name]==value,'resource publication changed original programme evidence')
            # Only this exact charged metadata file and its directory changed.
            self._snapshot=after;self._ext009=dict(resolution_sha256=row.sha256,metadata=asdict(binding))
            self.check(plan_sha256=self.family);return dict(self._ext009)
        except BaseException:self.failed=True;raise

    def release_for_launch(self,*,view,verified):
        import stage17_s180_journal_v1 as journal
        self.check(plan_sha256=self.family)
        require(type(view) is journal.JournalView and view.scoped_inputs_complete and not view.synthetic_test_only
            and set(view.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,11)}
            and type(verified) is authority.VerifiedRequest and self._ext009 is not None,
            'complete actually verified scoped authorization required before release')
        authorization=archive.parse_json(verified.authorization_bytes)
        require(authorization['plan_sha256']==self.family and archive.canonical(authorization['window_binding'])==self.window
            and authorization['prerequisite_bindings']['ext009_resolution_sha256']==self._ext009['resolution_sha256']
            and view.resolutions['S17-EXT-010'].semantic_context['authorization_sha256']==hashlib.sha256(verified.authorization_bytes).hexdigest(),
            'current authorization/resource lineage differs at programme handoff')
        self.close();self.released=True

    def close(self):
        if self.closed:return
        self.closed=True
        # Do not close or unlock an unrelated replacement descriptor.
        lock=self._store._lock
        try:
            require(lock is not None and archive.file_stamp(os.fstat(lock.fileno()))==self._lock_identity,
                'programme lock descriptor changed; not closing replacement')
        except BaseException:
            # Retain the Python stream too: its destructor must not close an
            # unrelated FD reused after an unexpected external os.close().
            if lock is not None:_QUARANTINED_LOCK_STREAMS.append(lock)
            self._store._lock=None;raise
        self._store.__exit__(None,None,None)


@contextlib.contextmanager
def own_programme(*,plan,window_binding,program_root,custody_limits,deadline_ns,preparation_deadline_ns):
    """Qualified outer only, before short metadata admission, inside original day.

    Exactly one original replay; caller authenticates the concrete source plan
    and uses the original window/finite metadata-preparation budget. No root is
    created, adopted, repaired or reserved by this function.
    """
    from stage17_s180_environment_v1 import _window
    _window(window_binding);require(os.geteuid()==0,'root admission controller required')
    started=time.monotonic_ns()
    require(type(deadline_ns) is int and time.monotonic_ns()<deadline_ns<=window_binding['end_monotonic_ns']
        and deadline_ns<=custody_limits.deadline_ns,'original programme ownership deadline differs')
    require(type(preparation_deadline_ns) is int and started<preparation_deadline_ns<=min(deadline_ns,started+600*10**9),
        'explicit finite remaining public-preflight deadline required')
    family=hashlib.sha256(archive.canonical(plan)).hexdigest();owner=None
    store=_AdmissionStore(Path(program_root),scope_sha256=plan['storage']['program_scope_sha256'],family_id=family,
        limits=custody_limits,ext009_resolution_sha256=None,reading_deadline_ns=preparation_deadline_ns)
    store.__enter__()
    try:
        owner=_OwnedProgramme(token=_TOKEN,store=store,plan=plan,window=window_binding,deadline=deadline_ns)
        reservation,_=store.inspect_reservation()
        require(store.scope['program_id']==plan['storage']['program_id'] and not any(store.working.iterdir())
            and not store._capture_pending and all(r['kind']=='RELEASED' for r in store._states.values())
            and store.reserved_bytes()==0,'current reserved programme/custody is incomplete')
        usage=store.physical_accounting();snapshot=owner._scan()
        for path,value in store._read_stamps.items():require(snapshot.get(path)==value,'replayed file changed before ownership snapshot')
        owner._snapshot=snapshot
        digest=hashlib.sha256()
        for path,value in sorted(snapshot.items()):digest.update(archive.canonical(dict(path=str(path.relative_to(store.root)),stamp=list(value))))
        owner._report=archive.canonical(dict(schema_version=SCHEMA,plan_sha256=family,program_scope_sha256=store.scope_sha256,
            original_replay_count=1,ledger_records=store._sequence,ledger_tip_sha256=store._previous,
            inventory_objects=len(snapshot),inventory_stamp_sha256=digest.hexdigest(),initial_physical_usage=asdict(usage),
            original_reserved_root=reservation['evidence_root_binding'],actual_programme_owner_uid=owner._root_owner_uid,
            actual_broker_lock_owner_uid=owner._lock_owner_uid,current_controller_uid=os.geteuid(),
            preparation_started_monotonic_ns=started,preparation_completed_monotonic_ns=time.monotonic_ns(),
            preparation_deadline_ns=preparation_deadline_ns,ownership_deadline_ns=deadline_ns,
            execution_authority=False,phase18_authority=False))
        owner.check(plan_sha256=family)
        require(time.monotonic_ns()<preparation_deadline_ns,'original programme preparation deadline expired')
        # Distinct preparation budget and lease lifetime, both prospectively
        # inside the same original day. No admission or operational lease reset.
        store._reading_deadline_ns=deadline_ns
        yield owner
    finally:
        if owner is not None:owner.close()
        elif store._lock is not None:store.__exit__(None,None,None)
