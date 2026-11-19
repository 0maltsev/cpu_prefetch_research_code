"""D288 read-only original-family authentication and partial custody inventory.

No execution entry point is returned. Original authorization expiry is evaluated
as historical provenance only inside retention preparation; every ordinary
signature, original qualification, hardware, source and namespace check remains.
The separate approved D288 analysis clock is supplied by the supervising packet.
"""
import dataclasses
import hashlib
import os
from pathlib import Path
import types

import stage17_q16c_prefix_reuse_v1 as incident
import stage17_q16c_execution_window_v3 as window
import stage17_q16c_archive_scope_v1 as images
import stage17_archive_metadata_fast_v1 as metadata
import stage17_formal_archive_registry_v1 as capture_registry

require=incident.require


def prepare_original(administration,**arguments):
    """Authenticate the consumed original authority; expose retention only.

    administration must be loaded by the authenticated original packet loader.
    Pinning the exact incident authority before the private factory ensures this
    historical window adapter cannot prepare another request or native action.
    """
    raw=Path(arguments['authorization_path']).read_bytes()
    require(hashlib.sha256(raw).hexdigest()==incident.AUTHORIZATION,'exact consumed original authority required')
    document=window.parse(raw)
    require(document['request_binding']['sha256']==incident.REQUEST,'exact consumed original request required')
    original=administration.execution_window

    def historical_authenticate(proof,*,validation,plan,now):
        # The original signed day remains immutable. Its old start is used
        # only to authenticate its historical envelope in this read-only path.
        record=original.parse(original.read(proof['manifest']))
        return original.authenticate(proof,validation=validation,plan=plan,now=record['started_monotonic_ns'])

    factory=metadata._clone(administration.make_controller,{**administration.make_controller.__globals__,
        'execution_window':types.SimpleNamespace(**{**vars(original),'authenticate':historical_authenticate})})
    cli_factory=metadata._clone(administration.make_cli,{**administration.make_cli.__globals__,'make_controller':factory})
    cli=cli_factory()
    # Configuration is authenticated and applied by the caller to the original
    # factory, so copy its already-pinned data through an explicit callback is
    # not supported here. The caller supplies the canonical bound documents.
    return _Preparation(cli,arguments)


class _Preparation:
    """Single retention configuration; intentionally no execute/main method."""
    def __init__(self,cli,arguments):
        self._cli,self._arguments=cli,arguments

    def authenticate(self,*,historical_inputs,packet_root,execution_window,source_reuse,archive_descriptor):
        controller=self._cli.controller
        controller.configure_historical_inputs(historical_inputs,packet_root)
        controller.configure_execution_window(execution_window)
        controller.configure_source_reuse(source_reuse)
        controller.configure_verified_descriptor(archive_descriptor,packet_root)
        prepared=self._cli.prepare_formal_retention(**self._arguments)
        require(hashlib.sha256(prepared.request_bytes).hexdigest()==incident.REQUEST
            and hashlib.sha256(prepared.authorization_bytes).hexdigest()==incident.AUTHORIZATION,
            'actual authenticated consumed request/authority')
        return prepared,types.SimpleNamespace(registry=self._cli.registry,executor=self._cli.executor,
            unbound_control=self._cli._unbound_control)


def verify_failed_custody(*,store,capture,checkpoint_binding,receipt_binding,decoder_profile,decoder_limits):
    """Validate the original failed86 ledger/bytes, without scientific credit."""
    for bound,key in ((checkpoint_binding,'checkpoint'),(receipt_binding,'custody')):
        require((bound['size_bytes'],bound['sha256'])==incident.FIXED[key],'exact original failed diagnostic '+key)
    require(store.family_id==incident.contract.PARENT_SHA256 and capture['ordinal']==86,'exact failed diagnostic family/capture')
    original=capture_registry._verify_capture
    def failed_completion(actual,expected,label):
        if label=='native checkpoint completion':
            require(expected is True and actual is False,'diagnostic checkpoint must remain failed')
            return
        capture_registry.same(actual,expected,label)
    verified=metadata._clone(original,{**original.__globals__,'same':failed_completion})(store=store,action='Q16c',
        capture=capture,checkpoint_binding=checkpoint_binding,receipt_binding=receipt_binding,
        decoder_profile=decoder_profile,decoder_limits=decoder_limits,readback=None,metadata_only=True)
    require(verified['native_result_after_cleanup']['stop']==10,'original diagnostic stop')
    return dict(verified,native_complete=False,retained_diagnostic_only=True)


def collect_metadata(prepared,facade,*,plan_binding,restoration_binding,deadline_ns):
    """One held inventory transaction; select all86 and preserve failed86."""
    plan=prepared.request['action_inputs']['plan']
    require(hashlib.sha256(prepared.request_bytes).hexdigest()==incident.REQUEST
        and hashlib.sha256(prepared.authorization_bytes).hexdigest()==incident.AUTHORIZATION,
        'only exact original authenticated incident accepted')
    require(window.read(plan_binding)==facade.registry.archive.canonical(plan)
        and plan_binding['sha256']==incident.contract.PARENT_SHA256,'exact original signed plan bytes')
    extent=incident.composition.previous.contract.validate_plan(plan)
    phase=Path(prepared.request['evidence_root_binding']['absolute_path'])
    require(phase.name==incident.contract.PARENT_SHA256 and phase.parent.name=='working','actual original program family root')
    descriptor,identity=facade.executor._componentwise_output_root(phase,prepared.root,prepared.request['evidence_root_binding'])
    try:
        require(not facade.executor._quarantine_present(descriptor),'quarantined original family cannot admit prefix')
        attempt=facade.unbound_control(descriptor,'stage17-q16c-attempt-v6.json')
        for key,expected in dict(action_id='Q16c',request_sha256=incident.REQUEST,authorization_sha256=incident.AUTHORIZATION,
            runtime_sha256=window.previous.WORKER,evidence_root_binding=prepared.request['evidence_root_binding']).items():
            incident.same(attempt[key],expected,'actual original attempt '+key)
        failure_binding=dict(path=str(phase/'stage17-q16c-failure-v6.json'),
            size_bytes=incident.contract.FAILURE_SIZE,sha256=incident.contract.FAILURE_SHA256)
        failure=window.parse(window.read(failure_binding));restoration=window.parse(window.read(restoration_binding))
        checkpoint_binding=dict(file_name='formal-capture-86-final-checkpoint.json',size_bytes=incident.FIXED['checkpoint'][0],sha256=incident.FIXED['checkpoint'][1])
        receipt_binding=dict(file_name='formal-capture-86-archive-custody.json',size_bytes=incident.FIXED['custody'][0],sha256=incident.FIXED['custody'][1])
        def file_binding(b):return dict(path=str(phase/b['file_name']),size_bytes=b['size_bytes'],sha256=b['sha256'])
        checkpoint=window.parse(window.read(file_binding(checkpoint_binding)));receipt=window.parse(window.read(file_binding(receipt_binding)))
        incident.zero_events(checkpoint,failure,restoration,receipt)
        require(sorted(int(p.name.split('-')[2]) for p in phase.glob('formal-capture-*-final-checkpoint.json'))==list(range(87)),
            'exact86 completed plus one failed checkpoint; no later attempt')
        profile=prepared.archive_runtime_profile
        archive,custody=images.selected_archive_modules(profile,deadline_ns)
        decode=facade.registry._metadata_decode_limits(plan,extent,profile,deadline_ns)
        decoder=archive.DecoderProfile(**dataclasses.asdict(profile.decoder))
        decode=archive.DecodeLimits(**dataclasses.asdict(decode))
        from stage17_fixed_action_executor_v11 import custody_limits
        limits=custody.CustodyLimits(**dataclasses.asdict(custody_limits(plan['storage'],deadline_ns)))
        with custody.ProgramStore(phase.parent.parent,scope_sha256=plan['storage']['program_scope_sha256'],
                family_id=phase.name,limits=limits) as store:
            require(store.family_id in store._families and store.scope['program_id']==plan['storage']['program_id'],
                    'original ledger family/program registration')
            original=store._families[store.family_id];observed=store.working.stat(follow_symlinks=False)
            require((observed.st_dev,observed.st_ino)==(original['device'],original['inode']),
                    'actual original ledger family directory identity')
            store._family_identity=(observed.st_dev,observed.st_ino)
            actual={(key) for key in store._states if key.startswith(store.family_id+':')}
            expected={store.family_id+':'+name for ordinal in range(87) for name in capture_registry.capture_names('Q16c',ordinal)}
            require(actual==expected and not any(family==store.family_id for family,_ in store._capture_pending),
                    'exact complete archived original prefix and failed custody')
            captures=[]
            for ordinal,item in enumerate(plan['captures'][:86]):
                def local_binding(name,maximum):
                    p=phase/name
                    with archive.open_regular(p) as stream:
                        before=archive.file_stamp(os.fstat(stream.fileno()))
                        require(0<before[2]<=maximum,'bounded original capture metadata')
                        raw=stream.read(before[2]+1)
                        require(len(raw)==before[2] and before==archive.file_stamp(os.fstat(stream.fileno()))
                            ==archive.file_stamp(p.stat(follow_symlinks=False)),'stable original metadata')
                    return dict(file_name=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                captures.append(capture_registry.verify_capture_metadata(store=store,action='Q16c',capture=item['capture'],
                    checkpoint_binding=local_binding(f'formal-capture-{ordinal}-final-checkpoint.json',limits.max_checkpoint_bytes),
                    receipt_binding=local_binding(f'formal-capture-{ordinal}-archive-custody.json',limits.max_record_bytes),
                    decoder_profile=decoder,decoder_limits=decode))
            failed=verify_failed_custody(store=store,capture=plan['captures'][86]['capture'],
                checkpoint_binding=checkpoint_binding,receipt_binding=receipt_binding,decoder_profile=decoder,decoder_limits=decode)
            store._check();tip=store.ledger_binding()
            result=dict(captures=captures,retained_failed_capture=failed,program_root=str(store.root),
                scope_bindings=dict(program_scope_sha256=store.scope_sha256,family_plan_sha256=store.family_id,
                    program_root_binding=facade.registry._root_binding(store.root),
                    phase_root_binding=facade.registry._root_binding(store.working),
                    ledger_head=dict(sequence_number=store._sequence-1,sha256=tip.sha256)),
                inverse_readback_performed=False,scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
        facade.executor._verify_root_identity(descriptor,identity)
        return result,decode
    finally:os.close(descriptor)
