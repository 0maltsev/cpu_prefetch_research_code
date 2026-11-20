"""D308 metadata-only successor; immutable policy64 and native sources remain."""
import json
import stage17_semantic_verifier_v64 as predecessor
import stage17_semantic_verifier_v58 as formal
import stage17_archive_metadata_fast_v1 as cloning
import stage17_operational_semantics_v19 as scoped

POLICY_PATH = predecessor.POLICY_PATH.parent/'stage17-operational-evidence-admission-policy-v65.json'
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent/'stage17-operational-evidence-admission-policy-v65.schema.json'
VERIFIER_ID,VERIFIER_VERSION = predecessor.VERIFIER_ID,'65'
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
FORMAL_DECISIONS = (*predecessor.FORMAL_DECISIONS,'docs/decisions/0308-ext007-chronological-qualification-membership.md')
NEW_ROOTS = ('stage17_semantic_verifier_v65','stage17_state_journal_v62','stage17_operational_semantics_v19')
SUCCESSOR_BINDINGS = (POLICY_SCHEMA.as_posix(),predecessor.POLICY_PATH.as_posix(),predecessor.POLICY_SCHEMA.as_posix(),
    'tools/author_stage17_policy_v65.py','tools/admit_stage17_descriptive_freeze_v2.py',
    'docs/evidence/stage17/EXT007-D308-JOURNAL-ORDER-20261120-01/original-journal-000009.json')


def verify_policy_v65(**arguments):
    root,policy = arguments['root'],arguments['policy']
    cloning._clone(formal.verify_policy_v58,{**formal.verify_policy_v58.__globals__,
        'POLICY_SCHEMA':POLICY_SCHEMA,'VERIFIER_VERSION':VERIFIER_VERSION,
        'preflight':predecessor.predecessor.preflight,'FORMAL_DECISIONS':FORMAL_DECISIONS})(**arguments)
    from stage17_semantic_verifier_v3 import _binding_for
    expected = _binding_for(root,predecessor.POLICY_PATH.as_posix())
    if policy['predecessor'] != expected: raise SemanticAdmissionError('policy65 retains immutable policy64')
    _,raw = pinned_binding_bytes(root,expected,'policy64 predecessor'); old = json.loads(raw)
    for group in ('bindings','runtime_closure'):
        for key,value in old[group].items():
            if policy[group].get(key) != value: raise SemanticAdmissionError('policy65 may not rewrite inherited '+group+' '+key)
    if policy['runtime_import_roots'] != list(dict.fromkeys((*old['runtime_import_roots'],*NEW_ROOTS))):
        raise SemanticAdmissionError('policy65 exact metadata roots differ')
    if not set((*SUCCESSOR_BINDINGS,*FORMAL_DECISIONS)) <= {v['path'] for v in policy['bindings'].values()}:
        raise SemanticAdmissionError('policy65 lacks reviewed source/failure regression bindings')


verify_policy_v14 = verify_policy_v65


def verify_input(**arguments):
    # Preserve v64's legacy fallback to v63, its future-pilot guard and its
    # complete candidate/source checks; only scoped semantics19 is selected.
    return cloning._clone(predecessor.verify_input,{**predecessor.verify_input.__globals__,'scoped':scoped})(**arguments)
