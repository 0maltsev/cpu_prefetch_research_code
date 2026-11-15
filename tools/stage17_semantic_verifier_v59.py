"""Generic fresh release admission; preserve v58 semantics and strict gates.

Only the approved cold family source and its packaging selectors may differ
among inherited bindings.
Historical policy58/preflight32 bytes remain predecessor facts. New EXT001
envelopes bind policy33; original policy32 envelopes retain their actual route.
Release qualification stays v12 and performs the complete bundle verifier.
"""
from __future__ import annotations

import json
import types

import stage17_semantic_verifier_v58 as predecessor
import stage17_read_only_preflight_semantic_verifier_v33 as preflight

POLICY_PATH = predecessor.POLICY_PATH.parent / 'stage17-operational-evidence-admission-policy-v59.json'
POLICY_SCHEMA = predecessor.POLICY_SCHEMA.parent / 'stage17-operational-evidence-admission-policy-v59.schema.json'
VERIFIER_ID = predecessor.VERIFIER_ID
VERIFIER_VERSION = '59'
INPUT_IDS = predecessor.INPUT_IDS
SemanticAdmissionError = predecessor.SemanticAdmissionError
sha_file = predecessor.sha_file
discover_python_closure = predecessor.discover_python_closure
pinned_binding_bytes = predecessor.pinned_binding_bytes
FORMAL_DECISIONS = (*predecessor.FORMAL_DECISIONS,
    'docs/decisions/0252-stage17-cold-archive-native-inverse.md',
    'docs/decisions/0253-stage17-fresh-custody-scan-overhead.md',
    'docs/decisions/0254-stage17-one-day-service-calibration.md')
ACCEPTANCE_BINDINGS = predecessor.ACCEPTANCE_BINDINGS
REBIND_PATH = 'src/runner/stage17_formal_family.cpp'
REBIND_PATHS = frozenset((REBIND_PATH, 'tools/create_stand_bundle.py', 'tools/verify_stand_bundle.py'))
NEW_ROOTS = ('stage17_semantic_verifier_v59', 'stage17_state_journal_v54',
    'stage17_read_only_preflight_executor_v33', 'stage17_read_only_preflight_semantic_verifier_v33',
    'stage17_operational_cli_daycap_v1', 'stage17_q15_session_controller_daycap_v1',
    'stage17_phase_controller_daycap_v1')
SUCCESSOR_BINDINGS = (POLICY_SCHEMA.as_posix(), predecessor.POLICY_PATH.as_posix(),
    predecessor.POLICY_SCHEMA.as_posix(), preflight.POLICY_PATH, preflight.POLICY_SCHEMA_PATH,
    'tools/author_stage17_policy_v59.py',
    'tools/stage17_archive_inverse_native_v1.cpp',
    'tools/stage17_archive_inventory_native_v1.cpp',
    'config/schemas/stage17-formal-service-plan-v3.schema.json')


def audit_inherited_bindings(root, policy, historical):
    """Keep every inherited source binding except the explicitly approved file."""
    for group in ('bindings', 'runtime_closure'):
        for key, old in historical[group].items():
            current = policy[group].get(key)
            if current is None or current.get('path') != old['path']:
                raise SemanticAdmissionError('policy59 removed/renamed inherited binding: ' + old['path'])
            if old['path'] not in REBIND_PATHS and current != old:
                raise SemanticAdmissionError('policy59 changed unapproved inherited binding: ' + old['path'])
            pinned_binding_bytes(root, current, group + ' ' + key)


def verify_policy_v59(**arguments):
    # Run the complete existing v58 body. It in turn runs all v55 schema,
    # exact-byte, full import closure, native, contract and ten-input checks.
    scope = {**predecessor.verify_policy_v58.__globals__, 'POLICY_SCHEMA': POLICY_SCHEMA,
             'VERIFIER_VERSION': VERIFIER_VERSION, 'preflight': preflight,
             'FORMAL_DECISIONS': FORMAL_DECISIONS}
    types.FunctionType(predecessor.verify_policy_v58.__code__, scope)(**arguments)
    root, policy = arguments['root'], arguments['policy']
    from stage17_semantic_verifier_v3 import _binding_for
    expected = _binding_for(root, predecessor.POLICY_PATH.as_posix())
    if policy['predecessor'] != expected:
        raise SemanticAdmissionError('policy59 predecessor is not exact immutable policy58')
    _, raw = pinned_binding_bytes(root, expected, 'policy58 predecessor')
    historical = json.loads(raw)
    audit_inherited_bindings(root, policy, historical)
    if policy['runtime_import_roots'] != list(dict.fromkeys((*historical['runtime_import_roots'], *NEW_ROOTS))):
        raise SemanticAdmissionError('policy59 runtime roots differ from exact generic successor')
    paths = {item['path'] for item in policy['bindings'].values()}
    if not set((*SUCCESSOR_BINDINGS, *FORMAL_DECISIONS)).issubset(paths):
        raise SemanticAdmissionError('policy59 lacks fresh source/policy/decision bindings')


verify_policy_v14 = verify_policy_v59


def verify_input(*, input_id, **arguments):
    if input_id == 'S17-EXT-001':
        envelopes = [doc for _, doc in arguments.get('repository_documents', [])
                     if doc.get('schema_version') == 'cpu-prefetch-stage17-operational-evidence-envelope/14']
        # Preserve original manifest bytes and their own policy. They cannot
        # masquerade as fresh executor33 facts: runtime readiness still checks
        # each envelope's actual implementation snapshot against loaded paths.
        if (len(envelopes) == 1 and isinstance(envelopes[0].get('semantic_policy'), dict)
                and envelopes[0]['semantic_policy'].get('path') == predecessor.preflight.POLICY_PATH):
            return predecessor.verify_input(input_id=input_id, **arguments)
        scope = {**predecessor.preflight_dispatch._verify_ext001.__globals__, 'preflight': preflight}
        return types.FunctionType(predecessor.preflight_dispatch._verify_ext001.__code__, scope)(
            input_id=input_id, **arguments)
    return predecessor.verify_input(input_id=input_id, **arguments)
