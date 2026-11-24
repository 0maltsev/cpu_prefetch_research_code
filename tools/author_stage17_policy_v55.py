"""Render prospective diagnostic policy v55; no write or execution authority."""
from __future__ import annotations
import argparse
import pathlib
import re
import sys

import author_stage17_policy_v54 as predecessor
import stage17_semantic_verifier_v55 as verifier
import check_discovery_codegen as discovery_codegen

_BASE = predecessor.predecessor._BASE
ROOTS = tuple(predecessor.ROOTS) + (
    'stage17_discovery_contract_v1', 'stage17_output_registry_v9',
    'stage17_phase_controller_v22', 'stage17_operational_cli_v15',
    'stage17_fixed_action_executor_v8', 'stage17_q15_session_controller_v17',
    'stage17_pilot_candidate_artifact_v9', 'stage17_operational_semantics_v13',
    'stage17_semantic_verifier_v55', 'stage17_state_journal_v49',
    'stage17_discovery_validation_v1', 'stage17_discovery_environment_v1',
)
SOURCE_ROOTS = (
    'tools/runner_main.cpp', 'src/runner/stage17_fixed_action.cpp',
    'src/runner/stage17_discovery_action.cpp', 'src/runner/stage17_discovery_publication.cpp',
    'src/calibration/native_discovery_capture.cpp', 'src/platform/thread_monitor.cpp',
    'src/platform/prepared_file_snapshot.cpp',
    'src/queue/linked_spsc.cpp',
)
SUCCESSOR_BINDINGS = (
    'config/stage17/stage17-operational-evidence-admission-policy-v54.json',
    'config/schemas/stage17-operational-evidence-admission-policy-v55.schema.json',
    'config/stage17/stage17-fixed-phase-actions-v7.json',
    'config/schemas/stage17-fixed-phase-actions-v7.schema.json',
    'config/schemas/stage17-discovery-plan-v1.schema.json',
    'config/schemas/stage17-discovery-retention-report-v1.schema.json',
    'config/schemas/stage17-pilot-candidate-external-contract-v7.schema.json',
    'config/schemas/stage17-runtime-release-provenance-v7.schema.json',
    'docs/decisions/0201-stage17-live-discovery-control-composition.md',
    'docs/decisions/0202-stage17-native-diagnostic-execution-and-custody.md',
    'docs/decisions/0203-caller-owned-linked-queue-storage.md',
    'tests/queue_linked_storage_test.cpp', 'config/queue-provenance/linked-spsc.json',
    'tests/stage17_discovery_action_test.cpp', 'tests/stage17_discovery_publication_test.cpp',
    'tests/calibration_native_discovery_test.cpp',
    'tests/platform_prepared_file_snapshot_test.cpp', 'tests/test_discovery_codegen.py',
    'tools/create_stand_bundle.py', 'tools/verify_stand_bundle.py',
    'tools/check_discovery_codegen.py', 'tools/discovery_codegen_probe.cpp',
    'tools/stage17_test_worker_main.cpp',
    'tools/author_stage17_policy_v55.py', 'tools/check_stage17_discovery_action.py',
    'tools/check_stage17_discovery_contract.py', 'tools/check_stage17_q16a_discovery.py',
    'tools/check_stage17_discovery_validation.py', 'tests/test_stage17_discovery_environment.py',
    'tools/stage17_discovery_fixture_main.cpp', 'tests/test_stage17_discovery_cpp_bridge.py',
    *discovery_codegen.SOURCE_EVIDENCE_PATHS,
    *(f'config/schemas/stage17-{family}-v5.schema.json' for family in (
        'fixed-action-request','fixed-action-context','phase-action-authorization',
        'phase-action-result','phase-action-attempt','phase-action-failure','phase-action-completion')),
)


def native_source_closure(root):
    pending = list(SOURCE_ROOTS)
    found = set()
    while pending:
        relative = pending.pop()
        if relative in found:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError('native source is absent: ' + relative)
        found.add(relative)
        for include in re.findall(r'^\s*#\s*include\s*"([^"]+)"', path.read_text(), re.MULTILINE):
            candidate = root / 'include' / include if include.startswith('cpu_prefetch/') else path.parent / include
            if not candidate.is_relative_to(root):
                raise ValueError('native include escapes root')
            pending.append(candidate.relative_to(root).as_posix())
    return found


def render(root):
    root = root.resolve()
    policy = predecessor.render(root)
    policy.update(schema_version='cpu-prefetch-stage17-operational-evidence-admission-policy/55',
        policy_id='STAGE17-OPERATIONAL-EVIDENCE-ADMISSION-POLICY-v55',policy_version='55',
        predecessor=_BASE.binding(root,predecessor.verifier.POLICY_PATH.as_posix()),
        predecessor_status='SUPERSEDED_ADDS_D178_BOUNDED_DIAGNOSTIC_ADMISSION',
        runtime_import_roots=list(ROOTS),
        runtime_closure={pathlib.PurePosixPath(path).stem:_BASE.binding(root,path)
            for path in sorted(verifier.discover_python_closure(root,ROOTS))},
        entries=[dict(input_id=key,status='IMPLEMENTED',verifier_id=verifier.VERIFIER_ID,
                      verifier_version=verifier.VERIFIER_VERSION) for key in verifier.INPUT_IDS])
    bindings = dict(policy['bindings'])
    for path in sorted(set(SUCCESSOR_BINDINGS) | native_source_closure(root)):
        bindings[path.replace('/','__').replace('.','_')] = _BASE.binding(root,path)
    policy['bindings'] = bindings
    return policy


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args();payload=_BASE.canonical(render(args.root))
    if args.check:
        path=args.root/verifier.POLICY_PATH
        if not path.is_file() or path.read_bytes()!=payload:
            print('stage17-policy-v55: FAIL: generated bytes differ',file=sys.stderr);return 1
        print('stage17-policy-v55: PASS');return 0
    sys.stdout.buffer.write(payload);return 0


if __name__=='__main__':
    raise SystemExit(main())
