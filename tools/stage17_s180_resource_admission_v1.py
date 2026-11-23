"""Live S180 resource gate from owned sources, actual layouts and locked custody.

Only the qualified outer operator may compose this with qualified EXT008.
Reports cannot construct the live handle. No hardware writes, qualification,
reservation, source generation, capture or retry is performed here.
"""
from __future__ import annotations

import copy
import contextlib
import ctypes
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import resource
import time

import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_authority_v1 as authority
import stage17_s180_environment_v1 as environment
import stage17_s180_journal_v1 as journal
import stage17_s180_launcher_v1 as launcher
import stage17_s180_parent_v1 as parent
import stage17_s180_plan_prepare_v1 as planning
import stage17_s180_resource_plan_v1 as prospective
import stage17_s180_verified_sources_v1 as sources
import stage17_s180_admission_custody_v1 as admission_custody

SCHEMA='cpu-prefetch-stage17-s180-live-resource-evidence/3'
NATIVE_SHA='7460102040fb9685af75131e6810494960b149fcf82d95d776347e4379d8f0fc'
NATIVE_SIZE=6151832
GIB=1024**3
_TOKEN=object()


class ResourceError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise ResourceError('S180 resources: '+message)


def _before(deadline):
    require(type(deadline) is int and time.monotonic_ns()<deadline,'original resource deadline expired')


def _read(path,maximum=65536):
    with archive.open_regular(Path(path)) as stream:raw=stream.read(maximum+1)
    require(len(raw)<=maximum,'bounded platform observation exceeded')
    return raw.decode('ascii').strip()


def platform_observation():
    """Read current physical memory, all actual v2 ancestor caps and own limits."""
    memory={}
    for line in _read('/proc/meminfo').splitlines():
        key,_,value=line.partition(':');memory[key]=value.strip().split()
    available=memory.get('MemAvailable')
    require(available is not None and len(available)==2 and available[1]=='kB'
        and available[0].isdecimal(),'actual MemAvailable required')
    proc=Path('/proc')/str(os.getpid())
    unified=[line[3:] for line in _read(proc/'cgroup',4096).splitlines() if line.startswith('0::')]
    require(len(unified)==1,'exactly one unified hierarchy required')
    relative=Path(unified[0]);require(relative.is_absolute() and '..' not in relative.parts
        and str(relative)==unified[0],'canonical actual cgroup membership required')
    root=Path('/sys/fs/cgroup');current=root/str(relative).lstrip('/');ancestors=[]
    while current!=root:
        maximum=_read(current/'memory.max');used=_read(current/'memory.current')
        require((maximum=='max' or maximum.isdecimal()) and used.isdecimal(),'actual memory controller values required')
        ancestors.append(dict(path=str(current),maximum_bytes=None if maximum=='max' else int(maximum),
            current_bytes=int(used)))
        current=current.parent
    def limit(kind):return list(resource.getrlimit(kind))
    fds=sorted(int(p.name) for p in (proc/'fd').iterdir())
    return dict(observed_monotonic_ns=time.monotonic_ns(),pid=os.getpid(),
        boot_id=_read('/proc/sys/kernel/random/boot_id',128),
        memory_available_bytes=int(available[0])*1024,memory_ancestors=ancestors,
        rlimit_as=limit(resource.RLIMIT_AS),rlimit_memlock=limit(resource.RLIMIT_MEMLOCK),
        rlimit_nofile=limit(resource.RLIMIT_NOFILE),highest_observed_fd=max(fds),
        base_page_bytes=os.sysconf('SC_PAGE_SIZE'))


def assess_platform(observed,*,process_envelope,native_limits):
    """Pure comparisons; callers must obtain observed from actual fixed reads."""
    needed=process_envelope['conservative_total_bytes']
    require(observed['base_page_bytes']==4096,'accepted actual base page required')
    require(observed['memory_available_bytes']>=needed,'physical available memory omits full process/page envelope')
    for row in observed['memory_ancestors']:
        maximum=row['maximum_bytes']
        require(maximum is None or maximum>=row['current_bytes']+needed,
            'finite memory ancestor omits the conservative remaining envelope')
    soft,hard=observed['rlimit_as']
    require(0<soft<=process_envelope['requested_address_or_page_caps_bytes']['parent']
        and (hard==resource.RLIM_INFINITY or soft<=hard),'parent AS limit not installed/read back')
    _,hard=observed['rlimit_memlock']
    require(hard==resource.RLIM_INFINITY or hard>=native_limits.native_memlock_bytes,'hard memlock cannot support declared native lock')
    _,hard=observed['rlimit_nofile']
    require((hard==resource.RLIM_INFINITY or hard>=native_limits.native_open_files)
        and observed['highest_observed_fd']+sources.CONTROL_RESERVE<native_limits.native_open_files,
        'native descriptor inheritance/control reserve cannot fit')


def capacity_plan(plan,envelope,limits,*,workspace_committed_bytes,scratch_committed_bytes):
    """Full family plus retained output and explicit other W/S commitments.

    Commitments include old failed evidence and unrelated future usage inside
    the same W/S ceilings. They require authenticated census/declaration in the
    qualified caller; there is no zero default or claim of measurement here.
    """
    archive.uint(workspace_committed_bytes,'other committed workspace')
    archive.uint(scratch_committed_bytes,'other committed scratch')
    analysis=prospective.analysis_output_envelope(plan)
    # Each eight-artifact capture uses CHECKPOINT, 6 transitions/artifact and
    # CUSTODY_RECEIPT. Reserve16 extra records for first-failure/terminal evidence.
    records=180*(2+6*8)+16
    metadata=archive.checked_sum(records*limits.max_record_bytes,
        180*(2*limits.max_checkpoint_bytes+plan['storage']['maximum_custody_receipt_bytes']
            +parent.PARENT_RECORD_LIMIT),plan['budget']['final_metadata_bytes'],
        plan['budget']['entry_metadata_bytes'],16*limits.max_record_bytes)
    files=records+180*(8+6)+16+analysis['required_inodes']
    peak=envelope['maximum_capture_workspace_bytes']
    scratch=archive.checked_sum(prospective.ANALYSIS_WORKERS*peak,17*GIB,scratch_committed_bytes)
    retained_output=archive.checked_sum(plan['budget']['final_metadata_bytes'],
        analysis['workspace_bytes_upper'],workspace_committed_bytes)
    space=custody.SpacePlan(peak,retained_output,peak,
        plan['storage']['archive_staging_bytes'],metadata,scratch,2*files)
    return space,records,files


def _storage(plan,envelope,limits,program_root,unrelated_reservations,programme_owner=None):
    family=planning.sha(plan)
    if programme_owner is None:
        context=stores.ProgramStore(Path(program_root),scope_sha256=plan['storage']['program_scope_sha256'],
            family_id=family,limits=limits,ext009_resolution_sha256=None)
    else:
        require(type(programme_owner) is admission_custody._OwnedProgramme and programme_owner.root==Path(program_root)
            and programme_owner._store.limits==limits,'actual original programme/limits owner required')
        context=programme_owner.inspect(plan_sha256=family)
    with context as store:
        require(store.scope['program_id']==plan['storage']['program_id'],'original programme differs')
        device=store.root.stat().st_dev
        require(all((store.root/name).stat().st_dev==device for name in store.DIRECTORIES),
            'programme directories must share the observed storage filesystem')
        reservation,_=store.inspect_reservation()
        marker=store.root/'metadata'/parent._attempt_name(family)
        require(not marker.exists() and not marker.is_symlink(),'original family attempt already consumed')
        require(not any(store.working.iterdir()),'native evidence/attempt predates resource admission')
        require(not store._capture_pending and all(row['kind']=='RELEASED' for row in store._states.values())
            and store.reserved_bytes()==0,'prior programme custody/reservations incomplete')
        usage=store.physical_accounting();fs=os.statvfs(store.root)
        require({'workspace_committed_bytes','scratch_committed_bytes'}<=set(unrelated_reservations),
            'explicit other workspace and scratch commitments required')
        space,records,files=capacity_plan(plan,envelope,limits,
            workspace_committed_bytes=unrelated_reservations['workspace_committed_bytes'],
            scratch_committed_bytes=unrelated_reservations['scratch_committed_bytes'])
        require(store._sequence+records<=limits.max_ledger_records,'future ledger records exceed replay ceiling')
        require(usage.unique_objects+files<=limits.max_inventory_files,'future physical inventory exceeds ceiling')
        snapshot=custody.CapacitySnapshot(fs.f_bavail*fs.f_frsize,fs.f_favail,usage.quota_bytes,0,
            unrelated_reservations['reserved_bytes'],unrelated_reservations['reserved_inodes'])
        custody.check_capacity(snapshot,space)
        require(archive.checked_sum(usage.quota_bytes,envelope['archive_family_upper_bytes'],space.retained_metadata_bytes)
            <=custody.PROGRAM_QUOTA,'complete family archive/metadata exceeds remaining shared quota')
        return dict(evidence_root_binding=reservation['evidence_root_binding'],snapshot=asdict(snapshot),
            physical_usage=asdict(usage),space_plan=asdict(space),ledger_records=store._sequence,
            prospective_ledger_records=records,prospective_files=files,
            analysis_output_envelope=prospective.analysis_output_envelope(plan),
            unrelated_reservations_declaration=unrelated_reservations,
            original_scope_sha256=store.scope_sha256,ledger_tip=asdict(store.ledger_binding()))


def _sizing(plan):
    sizing=copy.deepcopy(plan);sizing['schema_version']=planning.SIZING
    sizing['source_count_basis']='EXACT_DECLARED_COUNTS'
    for row in sizing['captures']:del row['expected_layout']
    return sizing


def _arithmetic(plan,report,*,compress_bound):
    sizing=_sizing(plan)
    require(report['sizing_plan_sha256']==planning.sha(sizing),'actual native description belongs to another exact plan')
    require(all(a['expected_layout']==b['expected_layout'] for a,b in zip(plan['captures'],report['captures'],strict=True)),
        'exact plan/native layouts differ')
    bounded,envelope=prospective.bound_packet(sizing,report,compress_bound=compress_bound)
    for wanted,actual in zip(bounded['captures'],plan['captures'],strict=True):
        require(all(wanted['execution_budget'][key]<=actual['execution_budget'][key]
            for key in ('metadata_bytes','max_output_bytes')),'actual output/metadata bound is insufficient')
    require(bounded['storage']['archive_staging_bytes']<=plan['storage']['archive_staging_bytes'],
        'declared archive staging cannot hold incompressible capture')
    minimum=planning.resource_minima(sizing,report)
    require(minimum['minimum_native_memory_bytes']+envelope['maximum_cold_heap_model_bytes']<=plan['budget']['memory_bytes'],
        'native/cold heap exceed declared memory')
    envelope['bounded_sizing_plan_sha256']=planning.sha(sizing)
    envelope['count_ceiling_method']='EXACT-DECLARED-ORIGINAL-SOURCE-COUNTS-v1'
    process=prospective.process_envelope(sizing,report,envelope)
    timing=prospective.time_envelope(sizing,report)
    return envelope,process,timing


class _VerifiedResources:
    def __init__(self,*,token,plan,environment_owner,source_owner,worker,archive_profile,program_root,
                 native_limits,custody_limits,deadline,envelope,process,timing,initial,unrelated_reservations,programme_owner=None):
        require(token is _TOKEN,'only actual resource verification constructs the handle')
        self._plan=archive.canonical(plan);self._family=planning.sha(plan)
        self._environment=environment_owner;self._sources=source_owner;self._worker=worker
        self._profile=archive_profile;self._program=Path(program_root);self._limits=native_limits
        self._custody=custody_limits;self._deadline=deadline;self._envelope=envelope;self._process=process
        self._pid=os.getpid();self._last=archive.canonical(initial)
        self._failed=False;self._context=None;self._prior=None
        self._unrelated=archive.canonical(unrelated_reservations)
        self._programme=programme_owner
        self._report=archive.canonical(dict(schema_version=SCHEMA,plan_sha256=self._family,
            source_proof=source_owner.proof(plan_sha256=self._family),envelope=envelope,
            process_envelope=process,time_envelope=timing,initial_observation=initial,
            automatic_retry=False,execution_authority=False,phase18_authority=False))

    def _observe(self):
        _before(self._deadline);require(self._pid==os.getpid(),'resource owner belongs to another process')
        plan=archive.parse_json(self._plan)
        hardware=self._environment.admission_observation(plan_sha256=self._family)
        proof=self._sources.proof(plan_sha256=self._family)
        require(proof['sealed_source_bytes']==self._process['native_resource_minima']['retained_source_vector_bytes'],
            'actual sealed sources differ from complete exact counts')
        context,_=self._sources.native_inputs(plan_sha256=self._family,
            loading_deadline_ns=min(self._deadline,time.monotonic_ns()+plan['budget']['setup_ns']))
        require(self._process['native_resource_minima']['minimum_source_vector_limit_bytes']<=context['maximum_vector_bytes']
            <=plan['budget']['memory_bytes'],'source vector ownership limit differs')
        platform=platform_observation();assess_platform(platform,process_envelope=self._process,native_limits=self._limits)
        require(platform['boot_id']==hardware['boot_id'],'platform/owned hardware boot differs')
        required=launcher._family_ns(plan)+prospective.EXTERNAL_TIME['independent_validation_ns']+prospective.EXTERNAL_TIME['restoration_and_exit_ns']
        require(time.monotonic_ns()+required<hardware['window_binding']['end_monotonic_ns'],
            'remaining original window omits native/analysis/restoration')
        require('stage17_s180_archive_broker_v1' in runtime._closure_bytes(self._profile,self._deadline),
            'actual archive closure omits S180 entry')
        for image in (self._profile.encoder,self._profile.python):runtime._image_bytes(image,self._deadline)
        library=self._profile.decoder.zstd_library_path
        require(archive.hash_file(library,max_bytes=16*1024**2,deadline_ns=self._deadline).sha256
            ==self._profile.decoder.zstd_library_sha256,'actual codec library changed')
        with contextlib.ExitStack() as stack:runtime._pin_image(self._worker,self._deadline,stack)
        storage=_storage(plan,self._envelope,self._custody,self._program,archive.parse_json(self._unrelated),self._programme)
        self._sources.proof(plan_sha256=self._family)
        hardware=self._environment.admission_observation(plan_sha256=self._family)
        platform=platform_observation();assess_platform(platform,process_envelope=self._process,native_limits=self._limits)
        require(platform['boot_id']==hardware['boot_id'] and time.monotonic_ns()+required
            <hardware['window_binding']['end_monotonic_ns'],'live boot/window changed during locked resource replay')
        _before(self._deadline)
        return dict(hardware=hardware,platform=platform,storage=storage)

    def report(self):return self._report

    def last_observation(self):return self._last

    def __call__(self,input_id,payload,view,*,for_execution):
        require(type(for_execution) is bool,'explicit replay classification required')
        require(input_id=='S17-EXT-009','this gate derives only scoped EXT009')
        require(type(view) is journal.JournalView and view.synthetic_test_only is False
            and set(view.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,9)},'actual preceding scoped EXT008 required')
        require(payload==dict(resource_proof_sha256=hashlib.sha256(self._report).hexdigest()),
            'signed resource evidence binding differs')
        prior=view.resolutions['S17-EXT-008'].semantic_context
        if not for_execution:
            require(self._pid==os.getpid() and self._context is not None and self._prior==archive.canonical(prior),
                'historical replay requires the original actually derived context')
            return archive.parse_json(self._context)
        require(not self._failed,'original resource gate failed; no automatic retry')
        try:return self._live_context(prior)
        except BaseException:
            self._failed=True
            raise

    def _live_context(self,prior):
        observed=self._observe();self._last=archive.canonical(observed)
        root=observed['storage']['evidence_root_binding'];window=observed['hardware']['window_binding']
        require(prior['scope_id']==authority.PLAN_SCOPE and prior['plan_sha256']==self._family
            and prior['window_binding']==window and prior['evidence_root_binding']==root
            and prior['runtime_binding']==dict(role=authority.ROLE,profile=authority.PROFILE,
                sha256=self._worker.sha256,size_bytes=self._worker.size_bytes)
            and prior['release_binding']==dict(source_revision=environment.NATIVE_REVISION,worker_sha256=self._worker.sha256)
            and prior['phase18_authority'] is False,'qualified plan/resource binding differs')
        context=dict(scope_id=authority.RESOURCE_SCOPE,plan_sha256=self._family,window_binding=window,
            evidence_root_binding=root,resource_admission_status='ADMITTED',phase18_authority=False)
        self._context=archive.canonical(context);self._prior=archive.canonical(prior)
        return context


def verify_resources(*,plan,environment_owner,source_owner,worker,archive_profile,program_root,
                     native_limits,custody_limits,unrelated_reservations,deadline_ns,programme_owner):
    """The qualified outer operator authenticates profile and reservation ancestry.

    Future unrelated reservations are an explicit externally authenticated
    administrative declaration, not a platform measurement or a default zero.
    This gate performs no filesystem-wide census of future obligations.
    """
    require(type(environment_owner) is environment._PreparedEnvironment
        and type(source_owner) is sources._VerifiedSources,'actual owned environment and sources required')
    require(type(programme_owner) is admission_custody._OwnedProgramme,'actual held programme required before short resource admission')
    require(type(worker) is runtime.ImageBinding and worker.sha256==NATIVE_SHA and worker.size_bytes==NATIVE_SIZE,
        'exact frozen production native required')
    require(type(native_limits) is launcher.LaunchLimits and type(custody_limits) is custody.CustodyLimits,
        'actual finite limit contracts required')
    native_limits.validate();custody_limits.validate();_before(deadline_ns)
    require(deadline_ns<=custody_limits.deadline_ns and deadline_ns-time.monotonic_ns()<=journal.METADATA_NS,
        'resource gate exceeds original short metadata lease')
    environment._plan(plan)
    from stage17_s180_compaction_v1 import require_monitored, METADATA_RESERVE_BYTES, METADATA_RESERVE_INODES
    from stage17_s180_q15_session_v1 import METADATA_BYTES as Q15_BYTES, METADATA_INODES as Q15_INODES
    require_monitored(plan);environment_owner.compaction_guard().check(boundary='ADMISSION')
    require(native_limits.native_address_space_bytes==native_limits.native_memlock_bytes==plan['budget']['memory_bytes']
        and native_limits.native_file_bytes==plan['budget']['max_output_bytes']
        and native_limits.post_native_reserve_ns>=prospective.EXTERNAL_TIME['independent_validation_ns']
            +prospective.EXTERNAL_TIME['restoration_and_exit_ns'],'native/post-native declarations differ')
    require(type(archive_profile) is runtime.RuntimeProfile
        and archive_profile.decoder.implementation_profile_sha256==plan['storage']['implementation_profile_sha256'],
        'actual archive profile differs from exact plan')
    authority.fields(unrelated_reservations,{'reserved_bytes','reserved_inodes','declaration_sha256',
        'workspace_committed_bytes','scratch_committed_bytes'},
        'authenticated unrelated-reservations declaration')
    for name in ('reserved_bytes','reserved_inodes','workspace_committed_bytes','scratch_committed_bytes'):
        archive.uint(unrelated_reservations[name],name)
    archive.sha(unrelated_reservations['declaration_sha256'],'reservation declaration')
    require(unrelated_reservations['reserved_bytes']>=METADATA_RESERVE_BYTES+Q15_BYTES
        and unrelated_reservations['reserved_inodes']>=METADATA_RESERVE_INODES+Q15_INODES,
        'declared external commitments omit bounded D333 recovery/Q15 metadata')
    report=planning.native_layouts(_sizing(plan),worker=worker,deadline_ns=deadline_ns)
    library=archive_profile.decoder.zstd_library_path
    require(0<library.stat().st_size<=16*1024**2,'bounded actual codec library required')
    binding=runtime.ImageBinding(library,library.stat().st_size,archive_profile.decoder.zstd_library_sha256)
    with contextlib.ExitStack() as stack:
        fd=runtime._pin_image(binding,deadline_ns,stack)
        codec=ctypes.CDLL('/proc/self/fd/'+str(fd));codec.ZSTD_versionNumber.restype=ctypes.c_uint
        require(codec.ZSTD_versionNumber()==10507,'exact accepted codec version required')
        codec.ZSTD_compressBound.argtypes=[ctypes.c_size_t];codec.ZSTD_compressBound.restype=ctypes.c_size_t
        envelope,process,timing=_arithmetic(plan,report,compress_bound=codec.ZSTD_compressBound)
    owner=_VerifiedResources(token=_TOKEN,plan=plan,environment_owner=environment_owner,source_owner=source_owner,
        worker=worker,archive_profile=archive_profile,program_root=program_root,native_limits=native_limits,
        custody_limits=custody_limits,deadline=deadline_ns,envelope=envelope,process=process,timing=timing,initial={},
        unrelated_reservations=unrelated_reservations,programme_owner=programme_owner)
    initial=owner._observe();owner._last=archive.canonical(initial)
    evidence=archive.parse_json(owner._report);evidence['initial_observation']=initial;owner._report=archive.canonical(evidence)
    return owner
