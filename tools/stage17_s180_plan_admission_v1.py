"""Owned scoped EXT008 semantic composition, and fixed EXT008/009 routing.

No CLI or stand preparation. The qualified outer supplies its authenticated
original replay/profile, already generated sources, qualification and reserved
programme directory. These facts cannot be supplied as report dictionaries.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import stat
import time

import stage17_s180_blueprint_v1 as blueprint
import stage17_s180_calibration_compatibility_v1 as compatibility
import stage17_s180_platform_v1 as platform
import stage17_s180_qualification_evidence_v1 as qualification
import stage17_s180_source_author_v1 as author

archive=author.archive
resources=author.resources
journal=resources.journal
authority=resources.authority
ROOT=author.namespaces.ROOT.parent/'plan-admission'
POLICY='config/stage17/s180-scoped-semantic-policy-v1.json'
POLICY_SHA='f6e4c127f40fe6fcf840953b0a3177695a2069bd8d12efada87b9d9a36cc1aaf'
SCHEMA='cpu-prefetch-stage17-s180-scoped-plan-evidence/1'
COMPAT_SCHEMA='cpu-prefetch-stage17-s180-scoped-compatibility-evidence/1'
METADATA_BYTES=2*1024**2
METADATA_INODES=8
FILE_BYTES=1024**2
_TOKEN=object()


class PlanAdmissionError(archive.ArchiveError):pass


def require(value,message):
    if not value:raise PlanAdmissionError('S180 plan admission: '+message)


def _same(value,expected,message):require(archive.canonical(value)==archive.canonical(expected),message)


def _sha(value):return hashlib.sha256(archive.canonical(value)).hexdigest()


def _before(deadline):require(time.monotonic_ns()<deadline,'original scoped metadata deadline expired')


def _policy():
    raw=(Path(__file__).resolve().parents[1]/POLICY).read_bytes()
    require(len(raw)<=8192 and hashlib.sha256(raw).hexdigest()==POLICY_SHA,'fixed qualified semantic policy differs')
    return archive.parse_json(raw)


def _original(base,bp):return author.namespaces._base(base,bp)


def _reserved(plan,program_root,limits,programme_owner):
    family=author.planning.sha(plan)
    require(type(programme_owner) is resources.admission_custody._OwnedProgramme
        and programme_owner.root==Path(program_root) and programme_owner._store.limits==limits,
        'actual held programme/limits owner required')
    with programme_owner.inspect(plan_sha256=family) as store:
        require(store.scope['program_id']==plan['storage']['program_id'],'original programme identity differs')
        reservation,binding=store.inspect_reservation()
        require(not any(store.working.iterdir()) and not store._capture_pending
            and all(r['kind']=='RELEASED' for r in store._states.values()) and store.reserved_bytes()==0,
            'reserved family is nonempty or preceding custody is incomplete')
        require(not os.path.lexists(store.root/'metadata'/resources.parent._attempt_name(family)),
            'family attempt already consumed before EXT008')
        return dict(root=reservation['evidence_root_binding'],reservation_sha256=binding.sha256)


class _VerifiedPlan:
    def __init__(self,*,token,authored,qualified,platform_owner,compatibility_owner,base,program,limits,profile,deadline,programme):
        require(token is _TOKEN,'actual owned prerequisite composition required')
        self.authored=authored;self.qualification=qualified;self.platform=platform_owner
        self.compatibility=compatibility_owner;self.base=base;self.program=Path(program);self.limits=limits
        self.profile=profile;self.deadline=deadline;self.environment=platform_owner.environment
        self._plan=archive.canonical(authored.plan);self.family=hashlib.sha256(self._plan).hexdigest()
        self.pid=os.getpid();self.failed=False;self._context=None;self._report=None;self._compatibility=None;self._metadata=None
        self._directory_identity=None
        self.programme=programme

    @property
    def payload(self):
        require(self._report is not None,'no actually derived plan proof exists')
        return dict(plan_proof_sha256=hashlib.sha256(self._report).hexdigest())

    def report(self):
        require(self._report is not None,'no actually derived plan report exists');return bytes(self._report)

    def compatibility_report(self):
        require(self._compatibility is not None,'no actually derived compatibility report exists');return bytes(self._compatibility)

    def _facts(self):
        _before(self.deadline);require(self.pid==os.getpid() and not self.failed,'original plan owner failed or belongs to another process')
        _policy();plan=archive.parse_json(self._plan);blueprint.verify(plan['blueprint'])
        _same(self.authored.plan,plan,'authored concrete plan changed')
        original=_original(self.base,plan['blueprint'])
        source=self.authored.proof();namespace=self.authored.namespace_owner.proof()
        require(source['plan_sha256']==self.family and source['source_bank_owned_and_verified'] is True
            and source['original_generation_passes']==source['independent_generation_verification_passes']==1,
            'actual single-generation/independent-verification source ownership required')
        require(self.platform.qualification is self.qualification and self.platform.compatibility is self.compatibility
            and self.qualification.owner.prepared.owner is self.environment,
            'platform, qualification and compatibility use different owners')
        qualified=self.qualification.proof(plan_sha256=self.family)
        hardware=self.platform.proof(plan_sha256=self.family)
        software=self.compatibility.proof(base_validation=self.base,plan_sha256=self.family,for_execution=True)
        _same(hardware['base_resolutions'],original,'current platform original-seven ancestry differs')
        _same(qualified['base_resolutions'],original,'current qualification original-seven ancestry differs')
        _same(software['base_resolutions'],original,'calibration compatibility original-seven ancestry differs')
        _same(namespace['base_resolutions'],original,'namespace original-seven ancestry differs')
        require(hardware['current_geometry_and_regime_verified'] is True
            and qualified['dynamic_qualification_verified'] is True and qualified['envelope_count']==10
            and software['software_compatibility_verified'] is True and software['inspection_mirror'] is False,
            'required current scoped prerequisites are incomplete')
        require(hardware['plan_sha256']==qualified['plan_sha256']==software['plan_sha256']==self.family
            and hardware['qualification_sha256']==qualified['qualification_sha256']
            and hardware['software_compatibility_sha256']==_sha(software),
            'current qualification/calibration/platform plan bindings differ')
        _same(qualified['measurement_runtime_binding'],dict(role=authority.ROLE,profile=authority.PROFILE,
            sha256=resources.NATIVE_SHA,size_bytes=resources.NATIVE_SIZE),'qualified native runtime differs')
        require(qualified['qualification_profile_sha256']==namespace['operator_profile_sha256']==self.profile,
            'namespace/qualification/outer qualified profile differs')
        window=namespace['window_binding']
        for facts in (qualified,hardware):_same(facts['window_binding'],window,'original prerequisite window differs')
        require(source['namespace_source_binding']==namespace['source_bank_binding']
            and namespace['source_bank_binding'] is not None,'original source-bank namespace binding differs')
        # Stable original platform report + current fresh owned observation.
        # The scope is the fixed requested stand regime, not a universal
        # inventory claim or retroactive homogeneity of calibration strata.
        raw=self.platform.report();require(hashlib.sha256(raw).hexdigest()==hardware['platform_evidence_sha256'],
            'original platform evidence binding differs')
        output=_reserved(plan,self.program,self.limits,self.programme);_before(self.deadline)
        return dict(plan=plan,original=original,source=source,namespace=namespace,qualified=qualified,
            hardware=hardware,software=software,platform_raw=raw,output=output,window=window)

    def _derive(self,facts):
        return dict(scope_id=authority.PLAN_SCOPE,plan_sha256=self.family,window_binding=facts['window'],
            evidence_root_binding=facts['output']['root'],runtime_binding=facts['qualified']['measurement_runtime_binding'],
            release_binding=dict(source_revision=resources.environment.NATIVE_REVISION,worker_sha256=resources.NATIVE_SHA),
            qualification_sha256=facts['qualified']['qualification_sha256'],compatibility_sha256=hashlib.sha256(self._compatibility).hexdigest(),
            runtime_profile_sha256=self.profile,phase18_authority=False)

    def _metadata_check(self):
        require(self._metadata is not None,'no retained scoped evidence exists')
        st=ROOT.stat(follow_symlinks=False)
        require(ROOT.resolve(strict=True)==ROOT and stat.S_ISDIR(st.st_mode) and st.st_uid==0
            and stat.S_IMODE(st.st_mode)==0o700 and (st.st_dev,st.st_ino)==self._directory_identity,
            'original scoped evidence directory identity differs')
        rows=archive.parse_json(self._metadata)['files']
        require(set(ROOT.iterdir())=={Path(r['path']) for r in rows},'scoped evidence inventory changed')
        for row in rows:author.namespaces._bound(row)

    def __call__(self,input_id,payload,view,*,for_execution):
        require(type(for_execution) is bool and input_id=='S17-EXT-008','this owner derives only scoped EXT008')
        require(type(view) is journal.JournalView and view.synthetic_test_only is False
            and set(view.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,8)},'actual preceding original-seven view required')
        _same(_original(view,archive.parse_json(self._plan)['blueprint']),
            _original(self.base,archive.parse_json(self._plan)['blueprint']),'preceding original-seven bindings changed')
        require(payload==self.payload,'signed scoped plan evidence binding differs')
        if not for_execution:
            require(self.pid==os.getpid() and self._context is not None,'historical replay requires the original actually derived context')
            return archive.parse_json(self._context)
        try:
            self._metadata_check();facts=self._facts();context=self._derive(facts)
            _same(context,archive.parse_json(self._context),'live scoped context changed')
            require(_sha(facts['software'])==archive.parse_json(self._compatibility)['software_compatibility_sha256']
                and facts['hardware']['platform_evidence_sha256']==archive.parse_json(self._compatibility)['platform_evidence_sha256'],
                'original compatibility/platform evidence changed')
            return context
        except BaseException:
            self.failed=True;self.environment._qualification_failed=True
            raise


def verify_plan(*,authored_sources,qualification_owner,platform_owner,compatibility_owner,base_validation,
                program_root,custody_limits,operator_profile_sha256,deadline_ns,programme_owner):
    """The outer operator authenticates its actual profile and base replay first."""
    require(type(authored_sources) is author._AuthoredSources
        and type(qualification_owner) is qualification._VerifiedEvidence
        and type(platform_owner) is platform._VerifiedPlatform
        and type(compatibility_owner) is compatibility._VerifiedCompatibility,'actual live prerequisite owners required')
    archive.sha(operator_profile_sha256,'qualified outer profile')
    _before(deadline_ns);require(deadline_ns-time.monotonic_ns()<=journal.METADATA_NS,'short scoped metadata lease required')
    require(type(custody_limits) is resources.custody.CustodyLimits,'actual finite custody replay limits required')
    owner=_VerifiedPlan(token=_TOKEN,authored=authored_sources,qualified=qualification_owner,platform_owner=platform_owner,
        compatibility_owner=compatibility_owner,base=base_validation,program=program_root,limits=custody_limits,
        profile=operator_profile_sha256,deadline=deadline_ns,programme=programme_owner)
    created=None
    try:
        facts=owner._facts();ROOT.mkdir(mode=0o700);author.namespaces._sync_directory(ROOT.parent)
        st=ROOT.stat(follow_symlinks=False);created=(st.st_dev,st.st_ino)
        owner._directory_identity=created
        def save(name,raw):
            return author._publish(ROOT/name,raw,'SCOPED-PLAN-SUPPORT',FILE_BYTES)
        bindings=[save('platform.json',facts['platform_raw']),save('software-compatibility.json',archive.canonical(facts['software']))]
        compatible=dict(schema_version=COMPAT_SCHEMA,plan_sha256=owner.family,base_resolutions=facts['original'],
            calibration_scope='STAGE17_EXT007_DESCRIPTIVE_DATA_ONLY',software_compatibility_sha256=_sha(facts['software']),
            platform_evidence_sha256=facts['hardware']['platform_evidence_sha256'],operator_profile_sha256=owner.profile,
            qualification_sha256=facts['qualified']['qualification_sha256'],current_scoped_regime_verified=True,
            calibration_strata_homogeneous_claim=False,legacy_statistical_freeze_satisfied=False,
            final_matrix_feasibility='NOT_EVALUATED',generic_pilot_readiness=False,phase18_authority=False,execution_authority=False)
        owner._compatibility=archive.canonical(compatible);bindings.append(save('compatibility.json',owner._compatibility))
        context=owner._derive(facts);owner._context=archive.canonical(context)
        report=dict(schema_version=SCHEMA,semantic_policy_sha256=POLICY_SHA,plan_sha256=owner.family,
            base_resolutions=facts['original'],source_preparation_completion=facts['source']['completion'],
            namespace_source_binding=facts['namespace']['source_bank_binding'],reservation_sha256=facts['output']['reservation_sha256'],
            compatibility_sha256=hashlib.sha256(owner._compatibility).hexdigest(),derived_scoped_context=context,
            scoped_ext008_semantics_verified=True,runtime_profile_qualification_performed_here=False,
            full_programme_resource_admission=False,generic_pilot_readiness=False,execution_authority=False,phase18_authority=False)
        owner._report=archive.canonical(report);bindings.append(save('plan-evidence.json',owner._report))
        require(sum(r['size_bytes']+4096 for r in bindings)<=METADATA_BYTES and len(bindings)+1<=METADATA_INODES,
            'scoped metadata commitment exceeded')
        owner._metadata=archive.canonical(dict(files=[{k:r[k] for k in ('path','size_bytes','sha256')} for r in bindings]))
        owner._metadata_check();_before(deadline_ns);return owner
    except BaseException as error:
        owner.failed=True;owner.environment._qualification_failed=True
        if created is not None:
            try:
                st=ROOT.stat(follow_symlinks=False)
                if (st.st_dev,st.st_ino)==created:
                    author.namespaces._save(ROOT/'failure.json',dict(schema_version=SCHEMA,
                        failure=str(error)[:4096],automatic_retry=False,execution_authority=False),8192)
            except BaseException:pass
        raise


class ScopedSemantics:
    """Fixed qualified router; EXT010 remains the journal's original verifier."""
    def __init__(self,*,plan_owner,resource_owner):
        require(type(plan_owner) is _VerifiedPlan and type(resource_owner) is resources._VerifiedResources,
            'actual owned scoped plan/resources required')
        require(resource_owner._environment is plan_owner.environment and resource_owner._sources is plan_owner.authored.source_owner
            and resource_owner._family==plan_owner.family and resource_owner._programme is plan_owner.programme,
            'scoped plan/resources use different live owners')
        _policy();self.plan=plan_owner;self.resources=resource_owner;self.policy_sha256=POLICY_SHA

    def __call__(self,input_id,payload,view,*,for_execution):
        require(input_id in ('S17-EXT-008','S17-EXT-009'),'EXT010 must use original signed journal authorization')
        owner=self.plan if input_id=='S17-EXT-008' else self.resources
        return owner(input_id,payload,view,for_execution=for_execution)

    def release_for_launch(self,*,view,verified):
        self.plan.programme.release_for_launch(view=view,verified=verified)
