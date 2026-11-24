"""D288 incident-bound86-report/188-source reuse; no execution authority.

The current admitted trust authenticates the original signed request. Exact
incident hashes retain historical authorship and cleanup. The D282 proof then
authenticates the original919c486 source producer under its own old identity.
The caller separately authenticates this packet and current phase authority.
"""
from pathlib import Path
import types

import stage17_q16c_empty_reuse_v1 as historical
import stage17_q16c_source_receipts_v2 as sources
import stage17_q16c_descriptive_calibration_v3 as composition
import stage17_formal_scheduled_continuation_v1 as contract
import stage17_q16c_execution_window_v3 as window
import stage17_q16c_prefix_compatibility_v1 as compatibility

admission=historical.admission
require,same,fields=admission.require,admission.same,admission.fields
SCHEMA='cpu-prefetch-stage17-q16c-prefix86-source-reuse/1'
REQUEST='96c82ab58046106712c1085d31af3326ac7406618d4ce49f361bdea1d2589d2a'
AUTHORIZATION='2a6fb1bf92a0e49d0f0d4a1499703519062f86c1072aeb8256c82f947b4770c7'
INVENTORY='8cfad0e13f95e896f1824ead7beba8dad6b44a5c7327a928e35f7a46b5746444'
FIXED=dict(original_plan=(contract.PARENT_SIZE,contract.PARENT_SHA256),
    failure=(contract.FAILURE_SIZE,contract.FAILURE_SHA256),
    checkpoint=(13473,'57dc6edee5750a81e4171c9072dd1738d883839e925aa9780b8457be5c41ff50'),
    custody=(6992,'a404c0f6e1641fbfda6beb8154dadf150c4dfe8b74fd95d019db53ce68507f1c'),
    restoration=(842,'ad2eb45db7d7f8b11ed372a3a76816f551ac7ac0081dcdb6eeacc8d5646dd326'))


def zero_events(checkpoint,failure,restoration,custody):
    """A prepared session is not a released phase or a completed measurement."""
    same(checkpoint['plan_sha256'],contract.PARENT_SHA256,'actual failed family')
    same(checkpoint['capture_ordinal'],86,'actual first unfinished original position')
    require(checkpoint['native_complete'] is False and checkpoint['execution_authority'] is False
        and checkpoint['scientific_validity']=='NOT_ASSESSED','retain failed evidence as failed')
    native=checkpoint['native_result_after_cleanup']
    require(type(native['stop']) is int and native['stop']==10 and native['publication_attempted'] is True
        and native['publication_succeeded'] is True,'actual failed-native diagnostic publication')
    phases=native['session']['lifecycle']['phases']
    require(type(phases) is list and len(phases)==2,'both original phases retained')
    for phase in phases:
        require(all(phase[key] is False for key in ('released','validated','before_observed','during_observed','after_observed'))
            and all(phase[key] is None for key in ('window','origin_sample','origin_status','observed_origin','drain_checkpoint')),
            'neither original phase may have been released')
        for role,keys in (('producer',('attempted','accepted','full')),('consumer',('polls','consumed_including_drain','empty'))):
            require(all(type(phase[role][key]) is int and phase[role][key]==0 for key in keys),
                    'zero original producer/consumer events required')
    artifacts=checkpoint['artifacts']
    require(type(artifacts) is list and len(artifacts)==8,'actual eight-artifact failed evidence')
    for index,(phase,role) in enumerate((('warmup','producer'),('warmup','consumer'),('measurement','producer'),('measurement','consumer'))):
        same(artifacts[index],dict(file_name=f'q16c-c86-{phase}-{role}.bin',size_bytes=0,
            sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),'empty original event stream')
    for key,value in dict(request_sha256=REQUEST,authorization_sha256=AUTHORIZATION,runtime_sha256=window.previous.WORKER,
            leader_reaped=True,process_group_gone=True,restoration_verified=True).items():same(failure[key],value,'original failure '+key)
    require(failure['quarantine_operation']['performed'] is False,'actual nonquarantined restoration required')
    rows=failure['recovery_readback']
    require(len(rows)==3 and {r['cpu'] for r in rows}=={0,1,8}
        and all(r['matches'] is True and r['requested_hex']==r['observed_hex']=='0000000000000000' for r in rows),
        'complete original MSR prestate restoration')
    require(restoration['verified'] is True and restoration['errors']==[]
        and restoration['maintenance_restoration_verified'] is True and restoration['root_restoration_verified'] is True,
        'actual original infrastructure restoration')
    for key,value in dict(status='ARCHIVED_AND_RELEASED',plan_sha256=contract.PARENT_SHA256,capture_ordinal=86,
            scientific_validity='NOT_ASSESSED',execution_authority=False).items():same(custody[key],value,'actual failed custody '+key)
    require(len(custody['artifacts'])==8,'failed evidence is preserved, never discarded')


def inspect(proof,plan,*,validation):
    fields(proof,'schema_version decision original_plan original_context original_request original_authorization original_signature '
        'checkpoint failure restoration custody parent_source_reuse accepted_prefix_manifest','D288 incident reuse')
    same(proof['schema_version'],SCHEMA,'exact D288 reuse schema');same(proof['decision'],'D288','exact approved incident')
    reader=admission.BoundReader()
    for key,(size,digest) in FIXED.items():same([proof[key]['size_bytes'],proof[key]['sha256']],[size,digest],'immutable original '+key)
    same(proof['original_request']['sha256'],REQUEST,'actual original request')
    same(proof['original_authorization']['sha256'],AUTHORIZATION,'actual original authority')
    original_raw=reader.read(proof['original_plan']);contract.validate_parent(plan,original_raw)
    parent=window.parse(original_raw)
    docs={key:reader.document(proof[key]) for key in ('original_context','original_request','original_authorization',
        'checkpoint','failure','restoration','custody','parent_source_reuse','accepted_prefix_manifest')}
    zero_events(docs['checkpoint'],docs['failure'],docs['restoration'],docs['custody'])
    same(docs['original_request']['action_inputs']['plan'],parent,'actual signed parent plan')
    trust=validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and trust['subject_id']==plan['stand_id'],'actual current admitted owner')
    reader.read(proof['original_signature'])
    historical.original.controller.support._verify_signature(reader.read(proof['original_authorization']),
        Path(proof['original_signature']['path']),trust)
    context=docs['original_context']
    fields(context,'schema_version boot_id resolutions execution_authority phase18_authority','original qualified source export')
    same(context['schema_version'],'cpu-prefetch-stage17-original-source-qualification-export/1','original context schema')
    same(context['boot_id'],window.previous.BOOT,'same verified original boot')
    fields(context['resolutions'],'S17-EXT-003 S17-EXT-004 S17-EXT-006','actual original trust/platform/release')
    require(context['execution_authority'] is False and context['phase18_authority'] is False,'old export grants no authority')
    old=types.SimpleNamespace(resolutions={k:types.SimpleNamespace(semantic_context=v['semantic_context'])
        for k,v in context['resolutions'].items()})
    release=old.resolutions['S17-EXT-006'].semantic_context
    for key,value in dict(source_revision=contract.PARENT_SOURCE,release_artifact_sha256=window.previous.WORKER,
            inventory_sha256=INVENTORY).items():same(release[key],value,'exact original qualified '+key)
    old_trust=old.resolutions['S17-EXT-003'].semantic_context['trust']
    same(old_trust['subject_id'],trust['subject_id'],'original/current admitted stand owner')
    for name in ('principal','reviewer_role','sshsig_namespace'):
        same(old_trust['measurements'][name],trust['measurements'][name],'original/current owner '+name)
    def signers(value):
        measurements=value['measurements']
        return reader.read(dict(path=measurements['allowed_signers_path'],
            size_bytes=measurements['allowed_signers_size_bytes'],sha256=measurements['allowed_signers_sha256']))
    require(signers(old_trust)==signers(trust),'actual original/current admitted owner signer bytes differ')
    current=validation.resolutions['S17-EXT-006'].semantic_context
    same(plan['source_revision'],current['source_revision'],'actual new qualification')
    for key in ('source_revision','release_artifact_sha256','inventory_sha256','archive_bundle_root'):
        require(current[key]!=release[key],'do not relabel old qualification '+key)
    prefix=docs['accepted_prefix_manifest']
    same(proof['accepted_prefix_manifest'],plan['continuation']['accepted_prefix_manifest'],'exact prospective prefix proof')
    same(proof['original_plan'],plan['continuation']['parent_plan'],'exact parent plan binding')
    same(proof['failure'],plan['continuation']['failed_family_receipt'],'exact incident failure binding')
    require(prefix['schema_version']==composition.PREFIX_SCHEMA and prefix['all_required_reports_valid'] is True
        and prefix['reused_capture_ordinals']==list(range(86)) and prefix['compaction_control']=='UNRECORDED'
        and prefix['execution_authority'] is False and prefix['phase18_authority'] is False,'all86 independently validated reports required')
    completion=reader.document(prefix['analysis_completion'])
    require(completion['status']=='ALL_SELECTED_VALID' and completion['kind']=='PREFIX86'
        and completion['all_workers_reaped'] is True and completion['plan_binding']==proof['original_plan'],
        'actual bounded86-prefix completion')
    require(len(completion['reports'])==len(prefix['reports'])==86,'complete prefix report bindings')
    for local,(binding,reported) in enumerate(zip(completion['reports'],prefix['reports'],strict=True)):
        raw=reader.read(binding)
        row=dict(capture_ordinal=local,validity='VALID',report_binding=reported,report_utf8_bytes=raw)
        composition.previous._report(row,parent['captures'][local]['capture'])
    source_context,source_plan=historical.inspect(docs['parent_source_reuse'],parent,validation=old)
    roots={side:Path(value['archive_bundle_root']) for side,value in [('original',release),('current',current)]}
    closure=historical.original.semantic.discover_python_closure(roots['original'],('generate_schedule','stage17_q16c_schedule_provenance_v2'))
    require(closure==historical.original.semantic.discover_python_closure(roots['current'],('generate_schedule','stage17_q16c_schedule_provenance_v2')),
         'complete generator/validator dependency closure differs')
    closure|={'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json','config/schemas/schedule-derivation-v2.schema.json',
        'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json'}
    for name in sorted(closure):require((roots['original']/name).read_bytes()==(roots['current']/name).read_bytes(),
        'unchanged generation dependency '+name+' differs')
    compatibility.consume(plan,plan['continuation']['compatibility_manifest'],validation=validation,
        original_validation=old,boot_id=context['boot_id'])
    reader.finish()
    return source_context,source_plan


def validate(plan,bindings,registrations,source_proof,*,validation,boot_id,deadline_ns,reuse):
    original,source_plan=inspect(reuse,plan,validation=validation)
    return sources.validate(plan,bindings,registrations,source_proof,validation=original,source_plan=source_plan,
        boot_id=boot_id,deadline_ns=deadline_ns)
