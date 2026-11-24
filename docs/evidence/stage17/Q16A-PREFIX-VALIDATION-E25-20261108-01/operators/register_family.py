"""D240 continuation registration into the unchanged original shared program.

No initialize/reset/adopt path. Original parent must be the only registered
family; qualified journal context and full production continuation admission
must pass before a new 531-capture family can be registered.
"""
import argparse, hashlib, json, os
from pathlib import Path
import sys, time
import formal_launch as launcher


def sha(raw): return hashlib.sha256(raw).hexdigest()

def require(ok, message):
    if not ok: raise ValueError(message)

def read_bound(path, digest):
    path = Path(path)
    require(path.is_absolute() and all(not p.is_symlink() for p in (path,*path.parents)), 'absolute nonsymlink path required')
    raw = path.read_bytes()
    require(sha(raw) == digest, 'bound bytes differ: '+str(path))
    return json.loads(raw), raw

def require_parent_only(families,parent_sha256):
    require(set(families)=={parent_sha256},'only retained original parent family may exist; no reset/adoption/retry')

def admit_continuation(args,plan):
    # No raw qualification-context JSON argument and no callback supplied by
    # a caller can bypass the existing authenticated root/journal verifier.
    import stage17_operational_cli_v18 as cli
    import stage17_phase_controller_v26 as controller
    import stage17_q16a_continuation_admission_v1 as admission
    require(args.deadline_monotonic_ns>time.monotonic_ns(),'preparation deadline expired')
    validation=cli._validation(args.repository_root,args.evidence_root,
        pilot_archive=args.pilot_archive,pilot_sidecar=args.pilot_sidecar,synthetic=False)
    require(all('S17-EXT-'+str(i).zfill(3) in validation.resolutions for i in range(1,7)),
            'all six qualified predecessor resolutions required')
    controller.previous.runtime_from_context(validation)
    resolution=validation.resolutions['S17-EXT-006']
    context=resolution.semantic_context
    require(context['source_revision']==plan['source_revision'],'qualified continuation source differs')
    profile=controller.qualified_archive_profile({'action_inputs':{'plan':plan}},validation,
                                                deadline_ns=args.deadline_monotonic_ns)
    require(profile.decoder.implementation_profile_sha256==args.profile_sha256,
            'qualified current profile differs')
    require(args.profile==Path(context['archive_bundle_root'])/'config/stage17/formal-archive-implementation-profile-v1.json',
            'profile path is outside actual qualified bundle')
    admission.validate(plan,context)
    require(args.deadline_monotonic_ns>time.monotonic_ns(),'continuation admission exceeded preparation deadline')
    return dict(resolution_id=resolution.resolution_id,sha256=resolution.sha256,
                source_revision=context['source_revision'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root','program-root','plan','admission','profile','output','evidence-root','pilot-archive','pilot-sidecar'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('plan-sha256','scope-sha256','admission-sha256','profile-sha256'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--deadline-monotonic-ns',type=int,required=True)
    p.add_argument('--register',action='store_true',help='Without this, perform read-only checks and print proposed family path.')
    args=p.parse_args()
    require(os.geteuid()==1000,'run as trusted UID1000; never chown/adopt an existing program')
    sys.path.insert(0,str(args.repository_root/'tools'))
    import stage17_formal_archive_v1 as archive
    import stage17_formal_plan_v2 as plans
    import stage17_fixed_action_executor_v11 as executor
    import stage17_formal_archive_custody_v1 as custody
    plan,raw=read_bound(args.plan,args.plan_sha256)
    require(raw==archive.canonical(plan),'plan must be exact canonical no-LF bytes')
    require(plan['schema_version']=='cpu-prefetch-stage17-formal-ring-plan/3','continuation helper requires exact archived Q16a /3')
    plans.validate_plan('Q16a',plan)
    scope,_=read_bound(args.program_root/'scope.json',args.scope_sha256)
    admission,_=read_bound(args.admission,args.admission_sha256)
    profile,_=read_bound(args.profile,args.profile_sha256)
    require(profile['policy_id']==archive.POLICY_ID,'profile policy differs')
    require(scope['prospective_admission_sha256']==args.admission_sha256,'scope admission differs')
    require(scope['program_id']==plan['storage']['program_id'],'program ID differs')
    launcher.continuation_lineage(plan,scope,admission,program_root=str(args.program_root),
                                  admission_sha256=args.admission_sha256)
    qualification_binding=admit_continuation(args,plan)
    require(plan['storage']['program_scope_sha256']==args.scope_sha256,'scope differs')
    require(plan['storage']['implementation_profile_sha256']==args.profile_sha256,'profile differs')
    require(args.deadline_monotonic_ns>time.monotonic_ns(),'preparation deadline expired')
    family=sha(raw);working=args.program_root/'working'/family
    require(not working.exists() and not args.output.exists(),'fresh family and exclusive receipt required')
    with custody.ProgramStore(args.program_root,scope_sha256=args.scope_sha256,family_id=family,
            limits=executor.custody_limits(plan['storage'],args.deadline_monotonic_ns)) as store:
        require_parent_only(store._families,plan['continuation']['parent_plan']['sha256'])
        result=dict(plan_sha256=family,program_scope_sha256=store.scope_sha256,working_root=str(working),
                    registered=False,execution_authority=False,
                    parent_plan_sha256=plan['continuation']['parent_plan']['sha256'],
                    qualification_binding=qualification_binding,
                    continuation_evidence=plan['continuation'])
        if args.register:
            require(store.prepare_family(family)==working,'registered family path differs')
            result['registered']=True
    if args.register:
        payload=archive.canonical(result)
        fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
        fd=os.open(args.output.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(fd)
        finally:os.close(fd)
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
