"""Fresh original custody, actual pool outputs and full S180 family validation.

Only the qualified outer supplies the actual original admitted request and
launch-terminal binding. No collection, qualification, source generation,
deadline reset or Stage18 authority exists in this callable.
"""
from __future__ import annotations
from dataclasses import asdict,replace
import contextlib
import hashlib
import os
import stat
from pathlib import Path

import stage17_s180_analysis_pool_v1 as pool
import stage17_s180_archive_custody_v1 as stores
import stage17_s180_archive_registry_v1 as registry
import stage17_s180_archive_broker_v1 as broker
import stage17_s180_parent_v1 as parent
import stage17_s180_analysis_input_v1 as analysis_input

archive=pool.archive
require=pool.require
exact=pool.worker.exact
SCHEMA='cpu-prefetch-stage17-s180-validated-family-analysis/4'


def _binding(reference):
    value=pool.worker.runtime.custody.BoundFile(**{k:reference[k] for k in ('file_name','size_bytes','sha256')})
    value.binding();return value


def _read(store,directory,reference,maximum):
    binding=_binding(reference)
    raw=store._read_bound(directory/binding.file_name,binding.binding(),maximum)
    value=archive.parse_json(raw)
    exact(archive.canonical(value),raw,'original canonical metadata bytes')
    return value


def _capture(store,request,native_result,ordinal,profile,decoder_limits,phase_owner=None):
    """Read one complete original from the locked ledger, never report-only."""
    require(store.family_id in store._families,'original admitted family missing; never create/adopt in analysis')
    if store._extension_binding is None:store.prepare_family(store.family_id)
    plan=request['plan'];family=store.family_id;prefix=f's180-e{ordinal}'
    references=native_result['artifacts'][ordinal*11:ordinal*11+11]
    require(len(references)==11,'complete original native capture references required')
    attempt_ref,checkpoint_ref,custody_ref=references[0],references[9],references[10]
    for reference,name,role,schema in ((attempt_ref,prefix+'-attempt.json','S180_RUN_ATTEMPT','cpu-prefetch-stage17-s180-run-attempt/1'),
            (checkpoint_ref,prefix+'-checkpoint.json','S180_CAPTURE_CHECKPOINT',pool.worker.capture.checkpoint_contract.SCHEMA),
            (custody_ref,prefix+'-archive-custody.json','S180_ARCHIVE_CUSTODY',pool.worker.capture.checkpoint_contract.CUSTODY_SCHEMA)):
        for key,value in dict(file_name=name,role=role,schema_identity=schema,media_type='application/json').items():
            exact(reference[key],value,'original native '+key)
    attempt=_read(store,store.working,attempt_ref,parent.PARENT_RECORD_LIMIT)
    checkpoint=_read(store,store.working,checkpoint_ref,store.limits.max_checkpoint_bytes)
    exact(checkpoint['artifacts'],references[1:9],'original eight-file native publication')
    receipt=_read(store,store.working,custody_ref,store.limits.max_record_bytes)
    reader=registry.verify_capture_metadata if phase_owner is None else analysis_input.verify_original
    owner={} if phase_owner is None else dict(phase_owner=phase_owner)
    verified=reader(**owner,store=store,capture=broker.capture_contract(request,ordinal),
        checkpoint_binding=asdict(_binding(checkpoint_ref)),receipt_binding=asdict(_binding(custody_ref)),
        decoder_profile=profile.decoder,decoder_limits=decoder_limits)
    analysis_input.check(verified)
    name=f's180-parent-{family}-e{ordinal}.json'
    raw=store._read_bound(store.root/'metadata'/name,None,parent.PARENT_RECORD_LIMIT)
    parent_receipt=archive.parse_json(raw);exact(archive.canonical(parent_receipt),raw,'original parent receipt canonical bytes')
    for key,value in dict(schema_version=parent.RECEIPT_SCHEMA,plan_sha256=family,execution_ordinal=ordinal,
            checkpoint=asdict(_binding(checkpoint_ref)),custody_receipt=asdict(_binding(custody_ref)),
            status='ARCHIVED_AND_RELEASED',broker_processes=25,scientific_validity='NOT_ASSESSED',
            execution_authority=False,phase18_authority=False).items():exact(parent_receipt[key],value,'actual parent '+key)
    cleanup=parent_receipt['broker_cleanup']
    for key,value in dict(returncode=0,leader_reaped=True,process_group_gone=True,
            descendants_detected_after_leader_exit=False,cleanup_deadline_overrun=False,leader_wait_timed_out=False).items():
        exact(cleanup[key],value,'actual original broker '+key)
    registration=store.read_verified_record(pool.worker.runtime.custody.BoundFile(**parent_receipt['custody_registration']))
    exact(registration['kind'],'CUSTODY_RECEIPT','actual parent custody registration')
    exact(registration['payload'],dict(family_id=family,checkpoint_sha256=checkpoint_ref['sha256'],
        receipt=asdict(_binding(custody_ref))),'actual parent registered custody bytes')
    return dict(checkpoint=checkpoint,attempt=attempt,custody_receipt=receipt,parent_receipt=parent_receipt,registry_proof=verified)


def _outputs(store,root,pool_result,records):
    complete=pool_result['result']
    exact(pool_result['binding']['file_name'],'complete.json','actual pool terminal name')
    require(complete['actual_worker_completion_verified'] is True and complete['completed_captures']==180,
        'actual complete worker result required')
    require(type(records) is list and len(records)==180 and type(complete['records']) is list
        and len(complete['records'])==180,'all180 actual output records required; counts alone are insufficient')
    raw=store._read_bound(root/'complete.json',_binding(pool_result['binding']).binding(),pool.META_MAX)
    exact(archive.parse_json(raw),complete,'actual owned pool completion bytes')
    for ordinal,(record,item) in enumerate(zip(records,complete['records'],strict=True)):
        exact(item['execution_ordinal'],ordinal,'actual original worker result order')
        directory=root/'captures'/f'capture-{ordinal}'
        publication=_read(store,directory,item['manifest'],pool.META_MAX)
        exact(pool._snapshot(directory,publication),item['output_snapshot'],'retained output after actual process reap')
        record['publication']=publication
        record['report']=_read(store,directory,publication['capture_validation'],pool.META_MAX)
        record['envelopes']=[_read(store,directory,reference,pool.META_MAX)
            for phase in publication['joined'] for reference in phase['raw_stream_envelopes']]
    return records


def _archive_snapshot(store,records):
    """Original file epochs spanning the actual full inverse, no payload read.

    The signed final family report carries these epochs to the independent
    service-exit observer. A stat snapshot is never a substitute for inverse
    byte/hash verification; publication follows both checks and unchanged epochs.
    """
    rows=[];seen=set();device=store.root.stat(follow_symlinks=False).st_dev
    for record in records:
        for item in record['registry_proof']['artifacts']:
            identity=item['artifact_id'];name=hashlib.sha256(identity.encode()).hexdigest()+'.cpfa'
            exact(item['archive_name'],name,'original snapshot archive identity')
            require(name not in seen,'duplicate original snapshot archive');seen.add(name)
            path=store.root/'archives'/name;s=path.stat(follow_symlinks=False)
            require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and not s.st_mode&0o022
                and s.st_dev==device,'original snapshot file is unsafe')
            exact(s.st_size,item['physical']['size_bytes'],'original snapshot archive extent')
            rows.append(dict(archive_name=name,expected_physical=dict(item['physical']),
                stamp=list(archive.file_stamp(s)),mode=stat.S_IMODE(s.st_mode),uid=s.st_uid,gid=s.st_gid))
    return sorted(rows,key=lambda row:row['archive_name'])


def _publish(root,report,check):
    """Actual complete metadata is provisional until its final deadline check."""
    root,identity=pool.worker.directory(root,owned=True);published=False
    try:
        binding=pool._save(root/'family-validation.pending.json',report)
        total,_=pool._usage(root);captures,_=pool._usage(root/'captures');scratch,_=pool._usage(root/'scratch')
        require(total-captures-scratch<=pool.phase.bounds.ANALYSIS_FAMILY_METADATA,'actual complete family metadata budget exceeded')
        check()
        os.link(root/'family-validation.pending.json',root/'family-validation.json',follow_symlinks=False)
        (root/'family-validation.pending.json').unlink();published=True;pool.worker.runtime.custody._sync_dir(root)
        check();return dict(binding=dict(binding,file_name='family-validation.json'),report=report)
    except BaseException:
        if published:
            with contextlib.suppress(OSError,ValueError):
                if pool.worker.directory(root)[1]==identity:
                    (root/'family-validation.json').rename(root/'uncommitted-family-validation.json')
                    pool.worker.runtime.custody._sync_dir(root)
        raise


def analyze_family(*,phase_owner,verified_request,terminal_binding,program_root,archive_profile,custody_limits,
                   decoder_limits,output_directory,other_workspace_committed_bytes,other_scratch_committed_bytes):
    """Called after actual owned launch/restoration/source release, exactly once.

    Input signatures/profile/census remain the qualified outer's responsibility.
    This reads exact retained launch bytes and a freshly locked original ledger;
    metadata asserts no raw validity until the actual worker and family checks.
    """
    require(type(phase_owner) is pool.phase._AnalysisPhase,'actual original analysis phase required')
    phase_owner.check();require(not phase_owner._pool_consumed,'original analysis already consumed')
    try:
        authorization,request=parent._documents(verified_request)
        exact(request['plan'],archive.parse_json(phase_owner.environment_owner._plan),'actual owned original plan')
        exact(authorization['window_binding'],archive.parse_json(phase_owner.window),'original owned operational window')
        exact(authorization['plan_sha256'],phase_owner.plan_sha256,'original collected plan identity')
        limits=replace(custody_limits,deadline_ns=min(custody_limits.deadline_ns,phase_owner.deadline_ns))
        with stores.ProgramStore(Path(program_root),scope_sha256=request['plan']['storage']['program_scope_sha256'],
                family_id=phase_owner.plan_sha256,limits=limits,
                ext009_resolution_sha256=request['prerequisite_bindings']['ext009_resolution_sha256']) as store:
            require(not store._capture_pending and store.reserved_bytes()==0
                and all(row['kind']=='RELEASED' for row in store._states.values()),'original custody/quotas not quiescent')
            fd=os.open(store.working,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:parent._root(fd,authorization)
            finally:os.close(fd)
            exact(terminal_binding['file_name'],f's180-launch-terminal-{store.family_id}.json','original launch terminal name')
            terminal=_read(store,store.root/'metadata',terminal_binding,parent.PARENT_RECORD_LIMIT)
            for key,value in dict(schema_version='cpu-prefetch-stage17-s180-launch-terminal/1',request_sha256=verified_request.request_sha256,
                    plan_sha256=store.family_id,status='NATIVE_COLLECTED_PENDING_SCIENTIFIC_VALIDATION',
                    acknowledged_captures=180,native_spawned=True,quarantined=False,failure=None,automatic_retries=0,
                    environment_restoration_failure=None,scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False).items():
                exact(terminal[key],value,'actual original terminal '+key)
            exact(terminal['environment_restoration'],phase_owner.environment_owner.restored_proof(plan_sha256=store.family_id),
                'actual same-process restoration')
            for key,value in dict(returncode=0,leader_reaped=True,process_group_gone=True,
                    descendants_detected_after_leader_exit=False,cleanup_deadline_overrun=False,leader_wait_timed_out=False).items():
                exact(terminal['native_cleanup'][key],value,'actual native cleanup '+key)
            expected=archive.canonical(parent._attempt_document(verified_request,authorization,request))
            raw=store._read_bound(store.root/'metadata'/parent._attempt_name(store.family_id),None,parent.PARENT_RECORD_LIMIT)
            exact(raw,expected,'actual consumed original family attempt')
            exact(terminal['native_result']['file_name'],'s180-session-result.json','original native result name')
            native=_read(store,store.working,terminal['native_result'],request['plan']['budget']['final_metadata_bytes'])
            pool.family._native(native,request['plan'],request['session_id'],store.family_id)
            require(len(native['artifacts'])==1980,'all original180 native publications required')
            tip=asdict(store.ledger_binding());records=[]
            for ordinal in range(180):
                phase_owner.check()
                record=_capture(store,request,native,ordinal,archive_profile,decoder_limits,phase_owner=phase_owner)
                exact(record['parent_receipt']['request_sha256'],verified_request.request_sha256,'actual original request receipt')
                records.append(record)
            originals=_archive_snapshot(store,records)
            require(len(originals)==1440,'all1440 original archive epochs required')
            result=pool.run_analysis(phase_owner=phase_owner,inputs=[dict(checkpoint=r['checkpoint'],registry_proof=r['registry_proof']) for r in records],
                native_result=native,session_id=request['session_id'],program_root=program_root,archive_profile=archive_profile,
                decode_limits=decoder_limits,output_directory=output_directory,
                other_workspace_committed_bytes=other_workspace_committed_bytes,other_scratch_committed_bytes=other_scratch_committed_bytes)
            records=_outputs(store,Path(output_directory),result,records)
            consistency=pool.family.validate_family(plan=request['plan'],session_id=request['session_id'],
                request_sha256=verified_request.request_sha256,native_result=native,records=records,
                window_binding=authorization['window_binding'],deadline_ns=phase_owner.deadline_ns)
            exact(_archive_snapshot(store,records),originals,'original archive epochs changed through inverse/family validation')
            exact(asdict(store.ledger_binding()),tip,'original custody unchanged through analysis')
            phase_owner.check()
            final_environment=phase_owner.environment_owner.final_restoration_observation(
                plan_sha256=store.family_id,deadline_ns=phase_owner.deadline_ns)
            phase_owner.check()
            report=dict(schema_version=SCHEMA,status='VALIDATED_DESCRIPTIVE_FAMILY_PENDING_OPERATIONAL_EXIT',
                plan_sha256=store.family_id,request_sha256=verified_request.request_sha256,terminal_binding=terminal_binding,
                original_ledger_tip=tip,archive_originals_inversely_verified=1440,actual_worker_completion_verified=True,
                original_archive_custody_verified=True,family_data_consistency=consistency,
                original_archive_epochs=originals,original_archive_epochs_unchanged_through_inverse=True,
                archive_verification_order='ORIGINAL_LEDGER_HEADERS_THEN_OWNED_PARALLEL_FULL_PHYSICAL_AND_CANONICAL_INVERSE',
                original_generation_binding=phase_owner.source_owner.released_proof(plan_sha256=store.family_id),
                prior_owned_environment_restoration_verified=True,final_live_restoration_verified=True,
                final_environment_observation=final_environment,
                operational_exit_verified=False,inferential_freeze_established=False,
                execution_authority=False,phase18_authority=False)
            def final_check():
                phase_owner.check()
                exact(_archive_snapshot(store,records),originals,'original archive epochs changed before final publication')
                exact(asdict(store.ledger_binding()),tip,'original custody changed before final publication')
                phase_owner.check()
            return _publish(Path(output_directory),report,final_check)
    except BaseException:
        phase_owner.failed=True
        raise
