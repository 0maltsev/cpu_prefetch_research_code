"""D272 fresh qualification policy for D270 original-source transport.

Preserve immutable policy60 and every inherited source and authority check.
Rebind only the five reviewed cold native files and two packaging selectors.
"""
from __future__ import annotations

import json
import types

import stage17_semantic_verifier_v60 as predecessor
import stage17_read_only_preflight_semantic_verifier_v35 as preflight

POLICY_PATH = predecessor.POLICY_PATH.parent/'stage17-operational-evidence-admission-policy-v61.json'
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent/'stage17-operational-evidence-admission-policy-v61.schema.json'
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = '61'
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
import stage17_q16a_q16c_descriptive_handoff_v1 as reviewed
REBIND_PATHS = predecessor.REBIND_PATHS | frozenset(reviewed.REVIEWED_COLD_SOURCES)
FORMAL_DECISIONS = (*predecessor.FORMAL_DECISIONS, *("docs/decisions/"+name+'.md' for name in (
    '0269-completed-q16b-descriptive-handoff', '0270-q16c-descriptive-screen-proposal',
    '0271-q16c-descriptive-original-source-integration', '0272-q16c-fresh-release-policy')))
NEW_ROOTS = ('stage17_semantic_verifier_v61', 'stage17_state_journal_v57',
    'stage17_read_only_preflight_executor_v35', 'stage17_read_only_preflight_semantic_verifier_v35',
    'stage17_operational_cli_daycap_v3', 'stage17_q15_session_controller_daycap_v3',
    'stage17_phase_controller_daycap_v3', 'stage17_formal_scheduled_descriptive_v1',
    'stage17_q16c_source_execution_v1', 'stage17_q16c_schedule_provenance_v2',
    'stage17_formal_scheduled_capture_validation_v2', 'stage17_q16c_descriptive_calibration_v1',
    'stage17_q16a_q16c_descriptive_handoff_v1', 'stage17_q16b_q16c_descriptive_handoff_v1')
SUCCESSOR_BINDINGS = (POLICY_SCHEMA.as_posix(), predecessor.POLICY_PATH.as_posix(),
    predecessor.POLICY_SCHEMA.as_posix(), preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH,
    'tools/author_stage17_policy_v61.py', 'config/schemas/stage17-formal-scheduled-plan-v3.schema.json',
    'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json',
    'config/schemas/stage17-fixed-action-context-v7.schema.json',
    'docs/STAGE17_EXT007_Q16C_DESCRIPTIVE_V1_DECISION.md',
    'docs/evidence/stage17/Q16C-D270-ACCEPTED-20261117-01/owner-acceptance.json',
    'docs/evidence/stage17/Q16C-D271-SOFTWARE-20261117-01/checks.json')



def audit_inherited_bindings(root, policy, historical):
    # Keep every inherited path and all nonexception bytes. The exact five
    # current native hashes are additionally checked below.
    body = predecessor.predecessor.audit_inherited_bindings
    return types.FunctionType(body.__code__, {**body.__globals__, 'REBIND_PATHS': REBIND_PATHS})(root, policy, historical)


def verify_policy_v61(**arguments):
    # Reuse v58's complete v55 schema/closure/ten-input and formal-source gates.
    # All policy60 predecessor roots/methods remain bound and audited below.
    body = predecessor.predecessor.predecessor.verify_policy_v58
    scope = dict(body.__globals__, POLICY_SCHEMA=POLICY_SCHEMA,
                 VERIFIER_VERSION=VERIFIER_VERSION, preflight=preflight,
                 FORMAL_DECISIONS=FORMAL_DECISIONS)
    types.FunctionType(body.__code__, scope)(**arguments)
    root, policy = arguments['root'], arguments['policy']
    from stage17_semantic_verifier_v3 import _binding_for
    expected = _binding_for(root, predecessor.POLICY_PATH.as_posix())
    if policy['predecessor'] != expected:
        raise SemanticAdmissionError('policy61 predecessor differs from immutable60')
    _, raw = pinned_binding_bytes(root, expected, 'policy60 predecessor')
    historical = json.loads(raw)
    audit_inherited_bindings(root, policy, historical)
    by_path = {r['path']: r for r in policy['bindings'].values()}
    for name, digest in reviewed.REVIEWED_COLD_SOURCES.items():
        if by_path[name]['sha256'] != digest:
            raise SemanticAdmissionError('unreviewed cold source '+name)
    if policy['runtime_import_roots'] != list(dict.fromkeys((*historical['runtime_import_roots'], *NEW_ROOTS))):
        raise SemanticAdmissionError('policy61 exact runtime roots differ')
    paths = {item['path'] for item in policy['bindings'].values()}
    if not set((*SUCCESSOR_BINDINGS, *FORMAL_DECISIONS)).issubset(paths):
        raise SemanticAdmissionError('policy61 lacks current source/approval bindings')


verify_policy_v14 = verify_policy_v61


def verify_input(*, input_id, **arguments):
    if input_id == 'S17-EXT-001':
        envelopes = [doc for _, doc in arguments.get('repository_documents', [])
                     if doc.get('schema_version') == 'cpu-prefetch-stage17-operational-evidence-envelope/14']
        if (len(envelopes) == 1 and isinstance(envelopes[0].get('semantic_policy'), dict)
                and envelopes[0]['semantic_policy'].get('path') in (
                    predecessor.preflight.POLICY_PATH, predecessor.predecessor.preflight.POLICY_PATH)):
            return predecessor.verify_input(input_id=input_id, **arguments)
        body = predecessor.predecessor.predecessor.preflight_dispatch._verify_ext001
        return types.FunctionType(body.__code__, dict(body.__globals__, preflight=preflight))(
            input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
