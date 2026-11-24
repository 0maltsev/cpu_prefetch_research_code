#!/usr/bin/env python3
"""Prepare exact Q16b registration arguments; NEVER initialize or register.

Future stand invocation performs packet-authenticated, fresh v27 admission and
read-only custody replay. This helper has no register switch or mutation path.
Namespace bytes remain outside the program, bound for later signed inputs.
"""
import argparse
import copy
from dataclasses import asdict
import importlib
from pathlib import Path
import re
import sys
import time
import audit_namespaces_q16b as audit

PROGRAM_ROOT = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-23/formal-archive-program-1')
PACKET_ROOT = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25/q16b-admission-operators-1')
PROGRAM_ID = 'CPU-PREFETCH-V5-V23-EXT007-FORMAL-1'
SCOPE_SHA = '4d0ddac91ec96bb7038f2903b965a2f1a785b63b108b5b05e645742ac8dcc0c2'
LEDGER_TIP = dict(file_name='0000000000058848.json', size_bytes=678,
    sha256='c663484f67bbaa9fe7ffb16717e8950df79f37c73049b3620cc7882bd18fbc8d')
STATE_SCHEMA = 'cpu-prefetch-stage17-q16b-program-registration-state/1'
require = audit.require


def require_families(families):
    require(type(families) is dict and set(families) == set(audit.FAMILIES),
            'exact original and continuation families required; no reset/adopt/retry')
    for family, facts in families.items():
        require(set(facts) == {'family_id', 'working_relative_path', 'device', 'inode'}, 'exact FAMILY facts required')
        require(facts['family_id'] == family and facts['working_relative_path'] == 'working/' + family,
                'retained family path differs')
        require(all(type(facts[k]) is int and facts[k] > 0 for k in ('device', 'inode')), 'retained family identity invalid')


def validate_state(state):
    require(set(state) == {'schema_version', 'program_root', 'program_id', 'scope_sha256', 'families',
                          'ledger_tip', 'execution_authority'}, 'exact existing program snapshot required')
    require(state['schema_version'] == STATE_SCHEMA and state['program_root'] == str(PROGRAM_ROOT)
            and state['program_id'] == PROGRAM_ID and state['scope_sha256'] == SCOPE_SHA
            and state['execution_authority'] is False, 'original program/scope snapshot differs')
    require_families(state['families'])
    require(state['ledger_tip'] == LEDGER_TIP, 'original ledger tip 58848 differs')


def guard_existing_program(store, expected_state):
    """Call under the existing ProgramStore lock immediately before registration.

    Pure guard: never prepares a family, appends a record, or retains metadata.
    Caller must keep this SAME store lock until its separately authorized append.
    """
    validate_state(expected_state)
    require(store._lock is not None, 'existing program lock must be held')
    require(Path(store.root) == PROGRAM_ROOT and store.scope_sha256 == SCOPE_SHA
            and store.scope['program_id'] == PROGRAM_ID, 'existing original program differs')
    require(store.family_id == audit.PLAN_SHA, 'constructor must bind exact final Q16b family')
    require_families(store._families)
    require(store._families == expected_state['families'], 'existing families changed')
    require(asdict(store.ledger_binding()) == expected_state['ledger_tip'], 'ledger tip changed')
    require(not store._capture_pending and all(s['kind'] == 'RELEASED' for s in store._states.values()),
            'unreleased or pending custody blocks a new family')
    require(not (PROGRAM_ROOT / 'working' / audit.PLAN_SHA).exists(), 'fresh Q16b family path required')
    return copy.deepcopy(expected_state)


def verify_one_family_append(before, after_families, record, raw):
    """Pure postcondition for a future separately authorized single FAMILY append."""
    validate_state(before)
    require(raw == audit.canonical(record), 'new FAMILY record must be exact canonical bytes')
    require(set(after_families) == set(audit.FAMILIES) | {audit.PLAN_SHA}, 'exactly one third family required')
    require({k: after_families[k] for k in audit.FAMILIES} == before['families'], 'retained families changed')
    require(set(record) == {'schema_version', 'scope_sha256', 'sequence', 'previous_sha256', 'kind',
                           'artifact_id', 'payload', 'timestamp_unix_ns'}, 'exact ledger record fields required')
    require(record['schema_version'] == 'cpu-prefetch-stage17-formal-representation-ledger/1'
            and record['scope_sha256'] == SCOPE_SHA and record['sequence'] == 58849
            and record['previous_sha256'] == LEDGER_TIP['sha256'] and record['kind'] == 'FAMILY'
            and record['artifact_id'] is None and type(record['timestamp_unix_ns']) is int
            and record['timestamp_unix_ns'] > 0, 'single FAMILY append chain differs')
    facts = after_families[audit.PLAN_SHA]
    require(set(facts) == {'family_id', 'working_relative_path', 'device', 'inode'}
            and facts['family_id'] == audit.PLAN_SHA
            and facts['working_relative_path'] == 'working/' + audit.PLAN_SHA
            and all(type(facts[k]) is int and facts[k] > 0 for k in ('device', 'inode')),
            'new family identity differs')
    require(record['payload'] == facts, 'new ledger FAMILY payload differs')
    return dict(file_name='0000000000058849.json', size_bytes=len(raw), sha256=audit.sha(raw))



def guard_registered_program(store, before):
    """Check the exact one-record postcondition under the SAME custody lock."""
    require(store._lock is not None, 'existing program lock must remain held')
    require(Path(store.root) == PROGRAM_ROOT and store.scope_sha256 == SCOPE_SHA
            and store.scope['program_id'] == PROGRAM_ID and store.family_id == audit.PLAN_SHA,
            'post-registration program differs')
    tip = store.ledger_binding()
    require(tip.file_name == '0000000000058849.json', 'exactly one new ledger record required')
    record = store.read_verified_record(tip)
    result = verify_one_family_append(before, store._families, record, audit.canonical(record))
    require(asdict(tip) == result, 'post-registration ledger binding differs')
    return result


def verify_history(report, mode, identities_sha256):
    require(report['schema_version'] == audit.REPORT_SCHEMA and report['mode'] == mode,
            'matching Q16b history audit mode required')
    require(report['status'] == 'PASS_SCOPED_HISTORY_AUDIT' and report['errors'] == [] and report['matches'] == [],
            'history audit has blocking errors/collisions')
    require(report['plan_sha256'] == audit.PLAN_SHA and report['plan_binding']['sha256'] == audit.PLAN_SHA
            and report['identities_binding']['sha256'] == identities_sha256,
            'history audit final plan/identities binding differs')
    require(report['helper_sha256'] == audit.sha(audit.read_metadata(Path(audit.__file__).absolute(), 1024**2)),
            'history audit source differs from frozen scanner')
    require(report['prior_registered_plan_sha256'] == sorted(audit.FAMILIES)
            and report['numeric_seeds_collision_scanned'] is True
            and report['planned_numeric_seeds'] == 8496 and report['planned_phase_identities'] == 7080
            and report['planned_linked_order_identities'] == 1416, 'complete numeric history proof required')
    require(report['limits'] == asdict(audit.Limits()), 'fresh finite scan limits differ')
    base = audit.absolute(report['base'])
    if mode == 'stand':
        require(base == PROGRAM_ROOT.parents[1], 'stand all-E history base differs')
    require(report['own_prospective_exclusions'] == list(map(str, audit.exclusions(mode, base))),
            'finite own-preparation exclusions differ')
    require(report['roots'] and report['checked_files'] > 0
            and report['checked_files'] == len(report['checked_inventory'])
            and report['checked_inventory_sha256'] == audit.sha(audit.canonical(report['checked_inventory'])),
            'history inventory differs')
    require(report['execution_authority'] is False and report['registration_performed'] is False,
            'history authority differs')


def fresh_admission(args, plan, inputs):
    """No supplied validation/context/callback bypasses packet or journal gates.

    A bound typed action-input document supports admission before a family
    directory exists. This minimal semantic envelope is NOT a formal request.
    Signed v6 request authoring/execution retains its original root/inode gates.
    """
    require(time.monotonic_ns() < args.deadline_monotonic_ns, 'preparation deadline expired')
    require(args.packet_root == PACKET_ROOT, 'exact E25 administrative packet root required')
    audit.absolute(args.packet_root)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.packet_root))
    admin = importlib.import_module('stage17_formal_admin_v1')
    require(Path(admin.__file__).absolute() == args.packet_root / 'stage17_formal_admin_v1.py', 'admin import outside bound packet')
    cli = admin.activate_packet(args.packet_manifest_sha256)
    functions = cli.formal_functions()
    validation = functions['_validation'](args.repository_root, args.evidence_root,
        pilot_archive=args.pilot_archive, pilot_sidecar=args.pilot_sidecar, synthetic=False)
    controller = cli.controller
    require(Path(controller.__file__).name == 'stage17_phase_controller_v27.py', 'v27 controller required')
    require(all('S17-EXT-' + str(i).zfill(3) in validation.resolutions for i in range(1, 7)),
            'all six fresh qualified resolutions required')
    runtime, release, _ = controller.runtime_from_context(validation)
    pinned = functions['registry'].pin_registry(args.repository_root)
    definition = pinned.action('Q16b')
    require(validation.current_state == definition['required_state'], 'fresh Q16b journal state gate differs')
    require(type(inputs) is dict and set(inputs) == {'plan', 'hardware_control', 'prerequisite_bindings'},
            'exact typed action input fields required')
    require(audit.canonical(inputs['plan']) == audit.canonical(plan), 'action inputs differ from exact final Q16b plan')
    require(validation.resolutions['S17-EXT-006'].semantic_context['source_revision'] == plan['source_revision'],
            'original qualified worker source differs')
    semantic_request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
        action_id='Q16b', stand_id=plan['stand_id'], action_inputs=inputs)
    # This exact v27 gate validates the complete plan, actual handoff, hardware,
    # namespace declaration, discovery and qualified archive implementation.
    controller.validate_action_inputs(semantic_request, validation)
    require(time.monotonic_ns() < args.deadline_monotonic_ns, 'fresh admission exceeded deadline')
    return dict(controller='stage17_phase_controller_v27', packet_manifest_sha256=args.packet_manifest_sha256,
        qualification_resolution_sha256=validation.resolutions['S17-EXT-006'].sha256,
        source_revision=plan['source_revision'], fresh_journal_validation=True,
        runtime_binding=runtime, release_binding=release, formal_request_authored=False,
        output_root_binding_created=False, execution_authority=False)


def prepare(args):
    plan_raw = audit.bound_input(args.plan, audit.PLAN_SHA)
    plan = audit.parse(plan_raw)
    ids_raw = audit.bound_input(args.identities, args.identities_sha256, 4 * 1024**2)
    audit.validate_registry(audit.parse(ids_raw), plan, plan_raw)
    expected = None
    if args.expected_program_state is not None:
        require(args.expected_program_state_sha256 is not None, 'bound expected state SHA256 required')
        state_raw = audit.bound_input(args.expected_program_state, args.expected_program_state_sha256, 1024**2)
        expected = audit.parse(state_raw)
        validate_state(expected)
    for mode in ('local', 'stand'):
        path = getattr(args, mode + '_audit')
        raw = audit.bound_input(path, getattr(args, mode + '_audit_sha256'), 96 * 1024**2)
        verify_history(audit.parse(raw), mode, args.identities_sha256)
    inputs_raw = audit.bound_input(args.action_inputs, args.action_inputs_sha256)
    inputs = audit.parse(inputs_raw)
    qualification = fresh_admission(args, plan, inputs)
    # Only after activate_packet has authenticated the original qualified closure.
    custody = importlib.import_module('stage17_formal_archive_custody_v1')
    executor = importlib.import_module('stage17_fixed_action_executor_v11')
    storage = plan['storage']
    require(storage['program_id'] == PROGRAM_ID and storage['program_scope_sha256'] == SCOPE_SHA,
            'final plan original program scope differs')
    limits = executor.custody_limits(storage, args.deadline_monotonic_ns)
    with custody.ProgramStore(PROGRAM_ROOT, scope_sha256=SCOPE_SHA, family_id=audit.PLAN_SHA, limits=limits) as store:
        if expected is None:
            # The pinned original tip authenticates replayed FAMILY facts; no
            # caller-invented device/inode values and no count-only snapshot.
            expected = dict(schema_version=STATE_SCHEMA, program_root=str(PROGRAM_ROOT),
                program_id=store.scope['program_id'], scope_sha256=store.scope_sha256,
                families=copy.deepcopy(store._families), ledger_tip=asdict(store.ledger_binding()),
                execution_authority=False)
        observed = guard_existing_program(store, expected)
        # Re-read the exact tip under this lock at the end as well.
        guard_existing_program(store, expected)
    return dict(schema_version='cpu-prefetch-stage17-q16b-registration-preparation/1',
        status='PREPARED_ARGUMENTS_ONLY', plan_binding=audit.binding(args.plan, plan_raw),
        action_inputs_binding=audit.binding(args.action_inputs, inputs_raw),
        namespace_reservation=audit.binding(args.identities, ids_raw),
        namespace_persistence='external immutable metadata; bind in later signed phase inputs',
        expected_program_state=observed, qualification=qualification,
        family_registration_arguments=dict(
            constructor='stage17_formal_archive_custody_v1.ProgramStore', root=str(PROGRAM_ROOT),
            scope_sha256=SCOPE_SHA, family_id=audit.PLAN_SHA, limits=asdict(limits),
            method='prepare_family', method_arguments=dict(family_id=audit.PLAN_SHA)),
        required_pre_registration_guard='guard_existing_program on SAME locked store; original ledger tip 58848',
        required_post_registration_guard='guard_registered_program on SAME locked store; exactly third family and tip 58849',
        guard_lock_released=True, live_guard_must_be_repeated=True,
        registered=False, execution_authority=False, phase18_authority=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repository-root', 'evidence-root', 'pilot-archive', 'pilot-sidecar', 'packet-root',
                 'plan', 'identities', 'local-audit', 'stand-audit', 'action-inputs'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('packet-manifest', 'identities', 'local-audit', 'stand-audit', 'action-inputs'):
        parser.add_argument('--' + name + '-sha256', required=True)
    parser.add_argument('--expected-program-state', type=Path)
    parser.add_argument('--expected-program-state-sha256')
    parser.add_argument('--deadline-monotonic-ns', type=int, required=True)
    args = parser.parse_args()
    require(0 < args.deadline_monotonic_ns - time.monotonic_ns() <= 1800 * 10**9, 'fresh finite deadline within 1800 seconds required')
    for key, value in vars(args).items():
        if key.endswith('_sha256') and value is not None:
            require(re.fullmatch('[0-9a-f]{64}', value), 'explicit SHA256 required: ' + key)
    print(audit.canonical(prepare(args)).decode())


if __name__ == '__main__':
    main()
