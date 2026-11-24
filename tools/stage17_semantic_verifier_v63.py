"""D289 exact /4 continuation release policy; historical policy62 stays immutable."""
import json
import types
import stage17_semantic_verifier_v62 as predecessor
import stage17_semantic_verifier_v58 as formal_body
import stage17_read_only_preflight_semantic_verifier_v37 as preflight
import stage17_q16a_q16c_descriptive_handoff_v3 as reviewed
import stage17_archive_metadata_fast_v1 as metadata

POLICY_PATH=predecessor.POLICY_PATH.parent/'stage17-operational-evidence-admission-policy-v63.json'
POLICY_SCHEMA=predecessor.POLICY_SCHEMA.parent/'stage17-operational-evidence-admission-policy-v63.schema.json'
VERIFIER_ID=predecessor.VERIFIER_ID
VERIFIER_VERSION='63'
INPUT_IDS=predecessor.INPUT_IDS
SemanticAdmissionError=predecessor.SemanticAdmissionError
sha_file=predecessor.sha_file
discover_python_closure=predecessor.discover_python_closure
pinned_binding_bytes=predecessor.pinned_binding_bytes
REBIND_PATHS=predecessor.REBIND_PATHS | frozenset(reviewed.REVIEWED_COLD_SOURCES)
FORMAL_DECISIONS=(*predecessor.FORMAL_DECISIONS,*("docs/decisions/"+name+'.md' for name in (
    '0286-q16c-locked-page-compaction-proposal','0287-q16c-compaction-handshake-integration',
    '0288-q16c-retained-prefix-continuation-proposal','0289-q16c-prefix-continuation-implementation',
    '0290-q16c-actual-scientific-source-provenance','0291-q16c-private-custody-registry',
    '0292-q16c-metadata-stop-continuation-proposal','0293-q16c-d292-execution-authority',
    '0294-q16c-qualification-handoff-boot-binding','0295-q16c-validated-prefix-qualification-continuation-proposal',
    '0296-q16c-completed-prefix-admission')))
NEW_ROOTS=('stage17_semantic_verifier_v63','stage17_state_journal_v60',
    'stage17_read_only_preflight_executor_v37','stage17_read_only_preflight_semantic_verifier_v37',
    'stage17_operational_cli_daycap_v5','stage17_q15_session_controller_daycap_v5',
    'stage17_phase_controller_daycap_v5','stage17_formal_scheduled_continuation_v1',
    'stage17_q16c_source_execution_v2','stage17_q16c_compaction_integration_v2',
    'stage17_locked_compaction_guard_v1','stage17_q16a_q16c_descriptive_handoff_v3',
    'stage17_q16b_q16c_descriptive_handoff_v3','stage17_q16c_analysis_v2',
    'stage17_q16c_execution_window_v3','stage17_q16c_execution_window_v4','stage17_q16c_execution_window_v5',
    'stage17_q16c_completed_prefix_v1','stage17_q16c_descriptive_calibration_v3',
    'stage17_q16c_descriptive_administration_v4','stage17_q16c_retained_prefix_v1')
SUCCESSOR_BINDINGS=(POLICY_SCHEMA.as_posix(),predecessor.POLICY_PATH.as_posix(),predecessor.POLICY_SCHEMA.as_posix(),
    preflight.POLICY_PATH,preflight.POLICY_SCHEMA_PATH,'tools/author_stage17_policy_v63.py',
    'config/schemas/stage17-formal-scheduled-plan-v4.schema.json',
    'docs/STAGE17_EXT007_Q16C_D286_ACCEPTANCE.md','docs/STAGE17_EXT007_Q16C_D288_ACCEPTANCE.md',
    'docs/evidence/stage17/Q16C-D286-ACCEPTED-20261119-01/owner-acceptance.json',
    'docs/evidence/stage17/Q16C-D288-ACCEPTED-20261119-01/owner-acceptance.json',
    'docs/STAGE17_EXT007_Q16C_D292_ACCEPTANCE.md',
    'docs/evidence/stage17/Q16C-D292-ACCEPTED-20261119-01/owner-acceptance.json',
    'docs/STAGE17_EXT007_Q16C_D295_ACCEPTANCE.md',
    'docs/evidence/stage17/Q16C-D295-ACCEPTED-20261119-01/owner-acceptance.json')


def audit_inherited_bindings(root,policy,historical):
    return metadata._clone(predecessor.audit_inherited_bindings,
        {**predecessor.audit_inherited_bindings.__globals__,'REBIND_PATHS':REBIND_PATHS})(root,policy,historical)


def verify_policy_v63(**arguments):
    metadata._clone(formal_body.verify_policy_v58,{**formal_body.verify_policy_v58.__globals__,
        'POLICY_SCHEMA':POLICY_SCHEMA,'VERIFIER_VERSION':VERIFIER_VERSION,
        'preflight':preflight,'FORMAL_DECISIONS':FORMAL_DECISIONS})(**arguments)
    root,policy=arguments['root'],arguments['policy']
    from stage17_semantic_verifier_v3 import _binding_for
    expected=_binding_for(root,predecessor.POLICY_PATH.as_posix())
    if policy['predecessor']!=expected:raise SemanticAdmissionError('policy63 predecessor differs from immutable62')
    _,raw=pinned_binding_bytes(root,expected,'policy62 predecessor')
    historical=json.loads(raw);audit_inherited_bindings(root,policy,historical)
    by_path={r['path']:r for r in policy['bindings'].values()}
    for name,digest in reviewed.REVIEWED_COLD_SOURCES.items():
        if by_path[name]['sha256']!=digest:raise SemanticAdmissionError('unreviewed cold source '+name)
    if policy['runtime_import_roots']!=list(dict.fromkeys((*historical['runtime_import_roots'],*NEW_ROOTS))):
        raise SemanticAdmissionError('policy63 exact runtime roots differ')
    if not set((*SUCCESSOR_BINDINGS,*FORMAL_DECISIONS))<=set(by_path):
        raise SemanticAdmissionError('policy63 lacks exact continuation/source/approval bindings')


verify_policy_v14=verify_policy_v63


def verify_input(*,input_id,**arguments):
    if input_id=='S17-EXT-001':
        envelopes=[doc for _,doc in arguments.get('repository_documents',[])
                   if doc.get('schema_version')=='cpu-prefetch-stage17-operational-evidence-envelope/14']
        if len(envelopes)==1 and isinstance(envelopes[0].get('semantic_policy'),dict) and envelopes[0]['semantic_policy'].get('path') in (
                predecessor.preflight.POLICY_PATH,predecessor.predecessor.preflight.POLICY_PATH):
            return predecessor.verify_input(input_id=input_id,**arguments)
        body=formal_body.preflight_dispatch._verify_ext001
        return metadata._clone(body,{**body.__globals__,'preflight':preflight})(input_id=input_id,**arguments)
    return predecessor.verify_input(input_id=input_id,**arguments)
