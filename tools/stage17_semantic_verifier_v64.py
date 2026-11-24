"""D307 scoped descriptive EXT007 admission; all historical dispatch is retained."""
import json
from pathlib import Path

import stage17_semantic_verifier_v63 as predecessor
import stage17_semantic_verifier_v58 as formal
import stage17_archive_metadata_fast_v1 as cloning
import stage17_operational_semantics_v18 as scoped

POLICY_PATH = predecessor.POLICY_PATH.parent/'stage17-operational-evidence-admission-policy-v64.json'
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent/'stage17-operational-evidence-admission-policy-v64.schema.json'
VERIFIER_ID,VERIFIER_VERSION = predecessor.VERIFIER_ID,'64'
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
FORMAL_DECISIONS = (*predecessor.FORMAL_DECISIONS,'docs/decisions/0307-ext007-scoped-descriptive-freeze.md')
NEW_ROOTS = ('stage17_semantic_verifier_v64','stage17_state_journal_v61','stage17_operational_semantics_v18',
             'stage17_descriptive_freeze_v1')
SUCCESSOR_BINDINGS = (POLICY_SCHEMA.as_posix(),predecessor.POLICY_PATH.as_posix(),predecessor.POLICY_SCHEMA.as_posix(),
    'tools/author_stage17_policy_v64.py','tools/prepare_stage17_descriptive_freeze_v1.py',
    'tools/admit_stage17_descriptive_freeze_v1.py',
    'config/schemas/stage17-operational-artifact-v5.schema.json',
    scoped.MANIFEST_SCHEMA,scoped.freeze.SCHEMA_PATH,scoped.ACCEPTED_PATH)


def verify_policy_v64(**arguments):
    root,policy = arguments['root'],arguments['policy']
    cloning._clone(formal.verify_policy_v58,{**formal.verify_policy_v58.__globals__,
        'POLICY_SCHEMA':POLICY_SCHEMA,'VERIFIER_VERSION':VERIFIER_VERSION,
        'preflight':predecessor.preflight,'FORMAL_DECISIONS':FORMAL_DECISIONS})(**arguments)
    from stage17_semantic_verifier_v3 import _binding_for
    expected = _binding_for(root,predecessor.POLICY_PATH.as_posix())
    if policy['predecessor'] != expected: raise SemanticAdmissionError('policy64 must retain exact immutable policy63')
    _,raw = pinned_binding_bytes(root,expected,'policy63 predecessor'); old = json.loads(raw)
    for group in ('bindings','runtime_closure'):
        for key,value in old[group].items():
            if policy[group].get(key) != value: raise SemanticAdmissionError('policy64 may not rewrite inherited '+group+' '+key)
    if policy['runtime_import_roots'] != list(dict.fromkeys((*old['runtime_import_roots'],*NEW_ROOTS))):
        raise SemanticAdmissionError('policy64 exact metadata roots differ')
    paths = {v['path'] for v in policy['bindings'].values()}
    if not set((*SUCCESSOR_BINDINGS,*FORMAL_DECISIONS)) <= paths:
        raise SemanticAdmissionError('policy64 lacks scoped schema/source/evidence bindings')


verify_policy_v14 = verify_policy_v64


def verify_input(*,input_id,**arguments):
    if input_id in {'S17-EXT-008','S17-EXT-009','S17-EXT-010'}:
        prior = arguments['admitted_resolutions'].get('S17-EXT-007')
        if prior is not None and prior.semantic_context.get('calibration_scope') == scoped.freeze.SCOPE:
            raise SemanticAdmissionError('descriptive EXT007 grants no legacy pilot or EXT008-010 admission')
    if input_id != 'S17-EXT-007':
        return predecessor.verify_input(input_id=input_id,**arguments)
    candidates = [p for p,d in arguments['repository_documents'] if d.get('schema_version') ==
                  'cpu-prefetch-stage17-operational-input-manifest/5']
    for receipt in arguments['receipt_documents']:
        locator = receipt.get('artifact_locator')
        if isinstance(locator,str):
            p = Path(locator); document,_ = scoped.reader.load(p)
            if document.get('schema_version') == 'cpu-prefetch-stage17-operational-input-manifest/5': candidates.append(p)
    if not candidates: return predecessor.verify_input(input_id=input_id,**arguments)
    if len(candidates) != 1 or len(arguments['receipt_documents']) != 1:
        raise SemanticAdmissionError('descriptive EXT007 requires one exact external manifest')
    root = arguments['root']; pinned = {}
    for group in ('bindings','runtime_closure'):
        for key,binding in arguments['policy'][group].items():
            _,raw = pinned_binding_bytes(root,binding,group+' '+key); pinned[binding['path']] = raw
    try:
        context = scoped.verify_manifest_v18(repository_root=root,manifest_path=candidates[0],
            admitted_resolutions=arguments['admitted_resolutions'],expected_input_id=input_id,
            allow_synthetic=arguments['allow_synthetic'],pinned_repository_bytes=pinned)
    except (scoped.OperationalSemanticError,ValueError,OSError,KeyError,TypeError) as error:
        raise SemanticAdmissionError('descriptive EXT007 rejected: '+str(error)) from error
    return dict(authorization=None,context=context)
