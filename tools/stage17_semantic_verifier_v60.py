"""D263 fresh qualification policy for the D260 cold native continuation parser.

Preserve the immutable v59 policy and all scientific/authority checks. Rebind
only the reviewed cold parser and packaging selectors; fresh action execution
still requires separately verified prerequisites, signatures and one-use gates.
"""
from __future__ import annotations

import json
import types

import stage17_semantic_verifier_v59 as predecessor
import stage17_read_only_preflight_semantic_verifier_v34 as preflight

POLICY_PATH = predecessor.POLICY_PATH.parent/'stage17-operational-evidence-admission-policy-v60.json'
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent/'stage17-operational-evidence-admission-policy-v60.schema.json'
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = '60'
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
REBIND_PATHS = predecessor.REBIND_PATHS
FORMAL_DECISIONS = (*predecessor.FORMAL_DECISIONS, *("docs/decisions/"+name+'.md' for name in (
    '0258-stage17-procfs-exit-race', '0259-retained-complete-capture-inspection',
    '0260-q16b-retained-prefix-continuation-proposal', '0261-plan-sized-formal-control-reader',
    '0262-post-exit-published-capture-custody', '0263-d260-fresh-qualification-policy')))
NEW_ROOTS = ('stage17_semantic_verifier_v60', 'stage17_state_journal_v56',
    'stage17_read_only_preflight_executor_v34', 'stage17_read_only_preflight_semantic_verifier_v34',
    'stage17_operational_cli_daycap_v2', 'stage17_q15_session_controller_daycap_v2',
    'stage17_phase_controller_daycap_v2', 'stage17_formal_service_continuation_v1',
    'stage17_formal_control_reader_v1', 'stage17_post_exit_custody_v1')
SUCCESSOR_BINDINGS = (POLICY_SCHEMA.as_posix(), predecessor.POLICY_PATH.as_posix(),
    predecessor.POLICY_SCHEMA.as_posix(), preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH,
    'tools/author_stage17_policy_v60.py', 'config/schemas/stage17-formal-service-plan-v4.schema.json',
    'docs/STAGE17_EXT007_Q16B_CONTINUATION_V1_DECISION.md',
    'docs/evidence/stage17/Q16B-PREFIX-RECOVERY-20261116-01/owner-acceptance-d260.json')


def audit_inherited_bindings(root, policy, historical):
    # The complete v59 audit has the same exact allowed rebind set. Keep all
    # inherited paths, all other bytes and every fresh source-byte check.
    return predecessor.audit_inherited_bindings(root, policy, historical)


def verify_policy_v60(**arguments):
    # Reuse v58's complete v55 schema/closure/ten-input and formal-source gates.
    # v59's additional predecessors, roots and methods are retained in the
    # immutable v59 parent and audited below, rather than relabeling its bytes.
    body = predecessor.predecessor.verify_policy_v58
    scope = dict(body.__globals__, POLICY_SCHEMA=POLICY_SCHEMA,
                 VERIFIER_VERSION=VERIFIER_VERSION, preflight=preflight,
                 FORMAL_DECISIONS=FORMAL_DECISIONS)
    types.FunctionType(body.__code__, scope)(**arguments)
    root, policy = arguments['root'], arguments['policy']
    from stage17_semantic_verifier_v3 import _binding_for
    expected = _binding_for(root, predecessor.POLICY_PATH.as_posix())
    if policy['predecessor'] != expected:
        raise SemanticAdmissionError('policy60 predecessor differs from immutable59')
    _, raw = pinned_binding_bytes(root, expected, 'policy59 predecessor')
    historical = json.loads(raw)
    audit_inherited_bindings(root, policy, historical)
    if policy['runtime_import_roots'] != list(dict.fromkeys((*historical['runtime_import_roots'], *NEW_ROOTS))):
        raise SemanticAdmissionError('policy60 exact runtime roots differ')
    paths = {item['path'] for item in policy['bindings'].values()}
    if not set((*SUCCESSOR_BINDINGS, *FORMAL_DECISIONS)).issubset(paths):
        raise SemanticAdmissionError('policy60 lacks current source/approval bindings')


verify_policy_v14 = verify_policy_v60


def verify_input(*, input_id, **arguments):
    if input_id == 'S17-EXT-001':
        envelopes = [doc for _, doc in arguments.get('repository_documents', [])
                     if doc.get('schema_version') == 'cpu-prefetch-stage17-operational-evidence-envelope/14']
        if (len(envelopes) == 1 and isinstance(envelopes[0].get('semantic_policy'), dict)
                and envelopes[0]['semantic_policy'].get('path') in (
                    predecessor.preflight.POLICY_PATH, predecessor.predecessor.preflight.POLICY_PATH)):
            return predecessor.verify_input(input_id=input_id, **arguments)
        body = predecessor.predecessor.preflight_dispatch._verify_ext001
        return types.FunctionType(body.__code__, dict(body.__globals__, preflight=preflight))(
            input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
