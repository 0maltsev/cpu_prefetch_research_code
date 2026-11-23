"""Actual bounded archive inverse followed by independent S180 validation.

Call only in an owned, qualified analysis worker after the original collection,
custody and aggregate-resource gates. This primitive authenticates every physical
and reconstructed byte, but supplies no ledger or execution admission itself.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import resource
import stat

import stage17_s180_capture_validation_v1 as capture
import stage17_s180_resource_plan_v1 as bounds
import stage17_formal_archive_runtime_v1 as runtime
import stage17_q16c_archive_scope_v1 as images

archive=runtime.archive
require=capture.require
exact=capture.exact
_TOKEN=object()
SCHEMA='cpu-prefetch-stage17-s180-archived-capture-analysis/1'


def directory(path,*,owned=False):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path,'actual canonical nonsymlink directory required')
    s=path.stat(follow_symlinks=False)
    require(stat.S_ISDIR(s.st_mode) and not s.st_mode&0o022 and (not owned or s.st_uid==os.geteuid()),
        'protected analysis/input directory required')
    return path,(s.st_dev,s.st_ino)


class _Codec:
    def __init__(self,*,token,profile,deadline_ns,modules):
        require(token is _TOKEN,'only authenticated archive images construct a worker codec')
        self.profile=profile;self.deadline_ns=deadline_ns;self.archive,self.custody=modules
        self.pid=os.getpid();self.failed=False;self.replay_cache=capture.ReplayCache();self.consumed_ordinals=set()

    def check(self):
        capture.before(self.deadline_ns)
        require(self.pid==os.getpid() and not self.failed,'original codec worker failed or belongs to another process')


def load_codec(profile,*,deadline_ns):
    """Once per dedicated worker; execute exact verified private source bytes."""
    capture.before(deadline_ns)
    require(type(profile) is runtime.RuntimeProfile,'actual archive runtime profile required')
    exact(profile.decoder.encoder_sha256,profile.encoder.sha256,'profile encoder image')
    exact(profile.decoder.decoder_executable_sha256,profile.python.sha256,'profile interpreter image')
    for image in (profile.encoder,profile.python):runtime._image_bytes(image,deadline_ns)
    modules=images.selected_archive_modules(profile,deadline_ns)
    return _Codec(token=_TOKEN,profile=profile,deadline_ns=deadline_ns,modules=modules)


def analyze_capture(*,codec,program_root,scratch_root,output_directory,registry_proof,checkpoint,
                    capture_row,entry,hardware,master_seed_hex,family_context_cleanup,
                    plan_sha256,program_scope_sha256,session_id,decode_limits,
                    canonical_bytes_bound,maximum_output_bytes,expected_cpu,expected_parent_pid):
    """Decode all eight originals once, publish durable results, release spool.

    Actual custody/plan/package and aggregate budgets belong to the qualified
    supervisor. Failed/partial spools and outputs stay retained; a failed codec
    cannot process another job. Original archive URIs never name inverse spools.
    """
    require(type(codec) is _Codec,'actual owned worker codec required')
    try:
        codec.check();deadline=codec.deadline_ns
        require(type(expected_cpu) is int and os.sched_getaffinity(0)=={expected_cpu},'actual worker CPU readback differs')
        require(os.getppid()==expected_parent_pid and expected_parent_pid!=os.getpid()
            and os.getsid(0)==os.getpid(),'owned dedicated analysis session required')
        exact(resource.getrlimit(resource.RLIMIT_AS),(bounds.ANALYSIS_CHILD_AS,bounds.ANALYSIS_CHILD_AS),
            'installed/read-back worker AS limits')
        require(type(decode_limits) is archive.DecodeLimits,'actual finite inverse limits required')
        ordinal=capture_row['execution_ordinal'];names=capture.checkpoint_contract.capture_names(ordinal)
        require(ordinal not in codec.consumed_ordinals,'original capture analysis already consumed; no repeat')
        codec.consumed_ordinals.add(ordinal)
        originals=capture.checkpoint_contract.original_references(checkpoint)
        require(len(originals)==8 and [r['file_name'] for r in originals]==list(names),'all eight original references required')
        exact(registry_proof['execution_ordinal'],ordinal,'original registry ordinal')
        exact(registry_proof['continuation_allowed'],True,'original native custody continuation')
        exact(registry_proof['inverse_readback_performed'],False,'fresh complete inverse required')
        exact(registry_proof['scientific_validity'],'NOT_ASSESSED','original custody validity scope')
        cp_raw=archive.canonical(checkpoint)
        exact(registry_proof['checkpoint'],dict(file_name=f's180-e{ordinal}-checkpoint.json',size_bytes=len(cp_raw),
            sha256=hashlib.sha256(cp_raw).hexdigest()),'actual original checkpoint bytes')
        require(len(registry_proof['artifacts'])==8,'complete original archive inventory required')
        program,program_identity=directory(program_root);archives,archive_identity=directory(program/'archives')
        scratch,scratch_identity=directory(scratch_root,owned=True)
        output=Path(output_directory);parent,parent_identity=directory(output.parent,owned=True)
        require(not scratch.is_relative_to(program) and not output.is_relative_to(program)
            and not output.is_relative_to(scratch) and not scratch.is_relative_to(output),
            'separate canonical scratch, permanent output and original archive trees required')
        total=0;artifacts=[];locations={}
        a,c=codec.archive,codec.custody
        for original,row in zip(originals,registry_proof['artifacts'],strict=True):
            codec.check();name=original['file_name'];artifact_id=plan_sha256+':'+name
            exact(row['artifact_id'],artifact_id,'original archive identity')
            exact(row['logical'],original,'original canonical bytes')
            archive_name=hashlib.sha256(artifact_id.encode()).hexdigest()+'.cpfa'
            exact(row['archive_name'],archive_name,'authoritative original archive path')
            role=capture.checkpoint_contract.role_profile(ordinal,name)
            exact(row['role'],asdict(role),'actual original archive role')
            phase=next((p for p in ('warmup','measurement') if '-'+p+'-' in name),None)
            run=capture_row['warmup_run_id' if phase=='warmup' else 'run_id'] if phase else None
            for key,value in dict(artifact_id=artifact_id,canonical_size_bytes=original['size_bytes'],
                    canonical_sha256=original['sha256'],phase=phase,run_id=run,worker=role.worker()).items():
                exact(row['header'][key],value,'original header '+key)
            total=archive.checked_sum(total,original['size_bytes'])
            artifacts.append(c.SpoolArtifact(name,archives/archive_name,row['header'],a.RoleProfile(**row['role']),
                a.PhysicalBinding(**row['physical'])))
            locations[name]=dict(artifact_uri=(archives/archive_name).as_uri(),compression=row['header']['codec_id'])
        require(total<=archive.uint(canonical_bytes_bound,'admitted canonical spool bound',positive=True)
            <=runtime.custody.SCRATCH,'sufficient original canonical bound within policy required')
        limits=a.DecodeLimits(**dict(asdict(decode_limits),deadline_ns=min(decode_limits.deadline_ns,deadline)))
        decoder=a.DecoderProfile(**asdict(codec.profile.decoder))
        before=resource.getrlimit(resource.RLIMIT_AS)
        try:
            resource.setrlimit(resource.RLIMIT_AS,(2*bounds.GIB,before[1]))
            exact(resource.getrlimit(resource.RLIMIT_AS),(2*bounds.GIB,before[1]),'actual temporary inverse AS limit')
            with c.capture_spool(scratch,capture_id=f's180-e{ordinal}',canonical_bytes_bound=canonical_bytes_bound,
                    deadline_ns=deadline,artifacts=tuple(artifacts),profile=decoder,limits=limits) as root:
                resource.setrlimit(resource.RLIMIT_AS,before)
                exact(resource.getrlimit(resource.RLIMIT_AS),before,'actual validation AS limit restored')
                publication=capture.validate_and_publish_capture(root,output_directory=output,
                    maximum_output_bytes=maximum_output_bytes,original_locations=locations,deadline_ns=deadline,
                    checkpoint=checkpoint,capture=capture_row,entry=entry,hardware=hardware,master_seed_hex=master_seed_hex,
                    family_context_cleanup=family_context_cleanup,replay_cache=codec.replay_cache,plan_sha256=plan_sha256,
                    program_scope_sha256=program_scope_sha256,session_id=session_id)
                # Root/parent replacement must fail before successful spool
                # cleanup. Any such failure retains all reconstructed originals.
                for path,identity in ((program,program_identity),(archives,archive_identity),
                        (scratch,scratch_identity),(parent,parent_identity)):
                    exact(directory(path)[1],identity,'original analysis directory identity')
        finally:
            resource.setrlimit(resource.RLIMIT_AS,before)
        codec.check()
        return dict(schema_version=SCHEMA,execution_ordinal=ordinal,plan_sha256=plan_sha256,
            publication=publication,original_archives_inversely_verified=8,canonical_spool_removed=True,
            canonical_input_bytes=total,worker_pid=os.getpid(),worker_parent_pid=os.getppid(),actual_cpu=expected_cpu,
            actual_validation_address_space_bytes=list(resource.getrlimit(resource.RLIMIT_AS)),
            original_archive_custody_verified=False,full_family_validity_established=False,
            aggregate_resource_admission_performed=False,execution_authority=False,phase18_authority=False)
    except BaseException:
        codec.failed=True
        raise
