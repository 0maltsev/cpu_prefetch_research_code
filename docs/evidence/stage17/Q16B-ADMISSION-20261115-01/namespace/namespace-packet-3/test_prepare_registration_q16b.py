"""Synthetic guard and bridge tests only; never touches a stand/program."""
import ast
import copy
from dataclasses import dataclass
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import audit_namespaces_q16b as audit
import prepare_registration_q16b as prep

HERE = Path(__file__).resolve().parent

@dataclass
class Tip:
    file_name: str
    size_bytes: int
    sha256: str


def state():
    families = {family: dict(family_id=family, working_relative_path='working/' + family,
                            device=1, inode=i + 10) for i, family in enumerate(audit.FAMILIES)}
    return dict(schema_version=prep.STATE_SCHEMA, program_root=str(prep.PROGRAM_ROOT),
        program_id=prep.PROGRAM_ID, scope_sha256=prep.SCOPE_SHA, families=families,
        ledger_tip=copy.deepcopy(prep.LEDGER_TIP), execution_authority=False)


def store(expected):
    return NS(root=prep.PROGRAM_ROOT, scope_sha256=prep.SCOPE_SHA,
        scope=dict(program_id=prep.PROGRAM_ID), family_id=audit.PLAN_SHA,
        _families=copy.deepcopy(expected['families']), ledger_binding=lambda: Tip(**expected['ledger_tip']),
        _lock=object(), _capture_pending=set(), _states={})


class RegistrationTests(unittest.TestCase):
    def test_both_families_tip_and_program_preserved_without_mutation(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp, patch.object(prep, 'PROGRAM_ROOT', Path(tmp)):
            expected = state()
            actual = store(expected)
            saved = copy.deepcopy(actual._families)
            result = prep.guard_existing_program(actual, expected)
            self.assertEqual(result, expected)
            self.assertEqual(actual._families, saved)
            self.assertIsNot(result['families'], expected['families'])
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_extra_missing_changed_family_or_tip_never_admitted(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp, patch.object(prep, 'PROGRAM_ROOT', Path(tmp)):
            for mutant in ('missing', 'extra', 'facts', 'tip', 'unlock', 'pending', 'unreleased', 'constructor', 'orphan'):
                with self.subTest(mutant=mutant):
                    expected = state()
                    actual = store(expected)
                    if mutant == 'missing':
                        actual._families.pop(audit.FAMILIES[0])
                    elif mutant == 'extra':
                        actual._families[audit.PLAN_SHA] = {}
                    elif mutant == 'facts':
                        actual._families[audit.FAMILIES[0]]['inode'] += 1
                    elif mutant == 'tip':
                        actual.ledger_binding = lambda: Tip('0000000000058849.json', 678, 'a' * 64)
                    elif mutant == 'unlock':
                        actual._lock = None
                    elif mutant == 'pending':
                        actual._capture_pending.add('pending')
                    elif mutant == 'unreleased':
                        actual._states['old'] = dict(kind='PUBLISHED')
                    elif mutant == 'constructor':
                        actual.family_id = audit.FAMILIES[0]
                    elif mutant == 'orphan':
                        (Path(tmp) / 'working' / audit.PLAN_SHA).mkdir(parents=True)
                    with self.assertRaises(ValueError):
                        prep.guard_existing_program(actual, expected)

    def test_only_one_third_family_append_and_exact_old_tip_allowed(self):
        expected = state()
        after = copy.deepcopy(expected['families'])
        facts = dict(family_id=audit.PLAN_SHA, working_relative_path='working/' + audit.PLAN_SHA, device=1, inode=50)
        after[audit.PLAN_SHA] = facts
        record = dict(schema_version='cpu-prefetch-stage17-formal-representation-ledger/1',
            scope_sha256=prep.SCOPE_SHA, sequence=58849, previous_sha256=prep.LEDGER_TIP['sha256'],
            kind='FAMILY', artifact_id=None, payload=facts, timestamp_unix_ns=1)
        tip = prep.verify_one_family_append(expected, after, record, audit.canonical(record))
        self.assertEqual(tip['file_name'], '0000000000058849.json')
        for key, value in [('sequence', 58850), ('previous_sha256', '0' * 64), ('kind', 'CHECKPOINT')]:
            wrong = dict(record, **{key: value})
            with self.assertRaises(ValueError):
                prep.verify_one_family_append(expected, after, wrong, audit.canonical(wrong))
        changed = copy.deepcopy(after)
        changed[audit.FAMILIES[0]]['inode'] += 1
        with self.assertRaisesRegex(ValueError, 'retained families changed'):
            prep.verify_one_family_append(expected, changed, record, audit.canonical(record))
        with self.assertRaisesRegex(ValueError, 'canonical'):
            prep.verify_one_family_append(expected, after, record, audit.canonical(record) + b'\n')

    def test_post_guard_rejects_additional_append_even_with_same_third_family(self):
        with tempfile.TemporaryDirectory(dir=HERE) as tmp, patch.object(prep, 'PROGRAM_ROOT', Path(tmp)):
            before = state()
            actual = store(before)
            facts = dict(family_id=audit.PLAN_SHA, working_relative_path='working/' + audit.PLAN_SHA, device=1, inode=99)
            actual._families[audit.PLAN_SHA] = facts
            record = dict(schema_version='cpu-prefetch-stage17-formal-representation-ledger/1',
                scope_sha256=prep.SCOPE_SHA, sequence=58849, previous_sha256=prep.LEDGER_TIP['sha256'],
                kind='FAMILY', artifact_id=None, payload=facts, timestamp_unix_ns=1)
            raw = audit.canonical(record)
            actual.ledger_binding = lambda: Tip('0000000000058849.json', len(raw), audit.sha(raw))
            actual.read_verified_record = lambda _: record
            self.assertEqual(prep.guard_registered_program(actual, before)['sha256'], audit.sha(raw))
            actual.ledger_binding = lambda: Tip('0000000000058850.json', len(raw), audit.sha(raw))
            with self.assertRaisesRegex(ValueError, 'exactly one new ledger'):
                prep.guard_registered_program(actual, before)

    def test_snapshot_rejects_count_only_wrong_scope_and_ledger(self):
        expected = state()
        prep.validate_state(expected)
        for key, value in [('families', 2), ('scope_sha256', '0' * 64), ('ledger_tip', {}), ('execution_authority', True)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                prep.validate_state(dict(expected, **{key: value}))

    def history(self):
        inventory = [dict(path='/fixture/history.json', size_bytes=2, sha256=audit.sha(b'{}'))]
        return dict(schema_version=audit.REPORT_SCHEMA, mode='stand', base=str(prep.PROGRAM_ROOT.parents[1]),
            status='PASS_SCOPED_HISTORY_AUDIT', errors=[], matches=[], plan_sha256=audit.PLAN_SHA,
            plan_binding=dict(sha256=audit.PLAN_SHA), identities_binding=dict(sha256='1' * 64),
            helper_sha256=audit.sha(Path(audit.__file__).read_bytes()), prior_registered_plan_sha256=sorted(audit.FAMILIES),
            numeric_seeds_collision_scanned=True, planned_numeric_seeds=8496, planned_phase_identities=7080,
            planned_linked_order_identities=1416, limits=audit.asdict(audit.Limits()),
            own_prospective_exclusions=list(map(str, audit.exclusions('stand', prep.PROGRAM_ROOT.parents[1]))),
            roots=['/fixture/history.json'], checked_files=1, checked_inventory=inventory,
            checked_inventory_sha256=audit.sha(audit.canonical(inventory)), execution_authority=False, registration_performed=False)

    def test_both_history_binding_numeric_proof_source_and_errors_are_mandatory(self):
        report = self.history()
        prep.verify_history(report, 'stand', '1' * 64)
        for key, value in [('status', 'FAIL'), ('errors', [{}]), ('matches', [{}]), ('planned_numeric_seeds', 7080),
                           ('helper_sha256', '0' * 64), ('numeric_seeds_collision_scanned', False),
                           ('prior_registered_plan_sha256', []), ('checked_inventory_sha256', '0' * 64),
                           ('own_prospective_exclusions', []), ('limits', {})]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                prep.verify_history(dict(report, **{key: value}), 'stand', '1' * 64)
        with self.assertRaises(ValueError):
            prep.verify_history(report, 'local', '1' * 64)

    def bridge(self):
        events = []
        args = NS(packet_root=prep.PACKET_ROOT, packet_manifest_sha256='a' * 64,
            repository_root=Path('/fixture/repo'), evidence_root=Path('/fixture/evidence'),
            pilot_archive=Path('/fixture/pilot'), pilot_sidecar=Path('/fixture/sidecar'), deadline_monotonic_ns=10**30)
        plan = dict(source_revision='b' * 40, stand_id='CPU-PREFETCH-V5')
        resolutions = {'S17-EXT-' + str(i).zfill(3): NS(sha256=str(i) * 64,
            semantic_context=dict(source_revision=plan['source_revision'])) for i in range(1, 7)}
        validation = NS(resolutions=resolutions, current_state='READY')
        fresh = Mock(side_effect=lambda *a, **k: (events.append('journal'), validation)[1])
        controller = NS(__file__='/packet/stage17_phase_controller_v27.py',
            runtime_from_context=Mock(return_value=({'runtime': 1}, {'release': 1}, None)),
            validate_action_inputs=Mock(side_effect=lambda *a: events.append('inputs')))
        pinned = NS(action=lambda _: dict(required_state='READY', required_resolution_ids=list(resolutions)))
        registry = NS(pin_registry=lambda _: pinned, validate_document=Mock(), schema_path=lambda _: '/schema')
        base = NS(_resolution_binding=lambda r: r.sha256)
        cli = NS(controller=controller, formal_functions=lambda: dict(_validation=fresh, registry=registry, base=base))
        activate = Mock(side_effect=lambda _: (events.append('activate'), cli)[1])
        admin = NS(__file__=str(prep.PACKET_ROOT / 'stage17_formal_admin_v1.py'), activate_packet=activate)
        request = dict(plan=plan, hardware_control={'fixture': 1}, prerequisite_bindings={'fixture': 1})
        return args, plan, request, admin, cli, fresh, events, validation

    def test_packet_activation_precedes_actual_fresh_validation_then_v27_inputs(self):
        args, plan, request, admin, cli, fresh, events, validation = self.bridge()
        with patch.object(prep.importlib, 'import_module', return_value=admin):
            result = prep.fresh_admission(args, plan, request)
        self.assertEqual(events, ['activate', 'journal', 'inputs'])
        admin.activate_packet.assert_called_once_with(args.packet_manifest_sha256)
        fresh.assert_called_once_with(args.repository_root, args.evidence_root,
            pilot_archive=args.pilot_archive, pilot_sidecar=args.pilot_sidecar, synthetic=False)
        cli.controller.validate_action_inputs.assert_called_once_with(dict(
            schema_version='cpu-prefetch-stage17-fixed-action-request/6', action_id='Q16b',
            stand_id=plan['stand_id'], action_inputs=request), validation)
        self.assertFalse(result['output_root_binding_created'])
        self.assertFalse(result['formal_request_authored'])
        self.assertTrue(result['fresh_journal_validation'])

    def test_failed_packet_no_journal_call_and_qualification_state_and_v27_errors_block(self):
        for mutant in ('packet', 'state', 'v27', 'inputs_missing', 'inputs_extra', 'inputs_plan', 'source'):
            args, plan, request, admin, cli, fresh, events, validation = self.bridge()
            if mutant == 'packet':
                admin.activate_packet.side_effect = ValueError('packet differs')
            elif mutant == 'state':
                validation.current_state = 'WRONG'
            elif mutant == 'v27':
                cli.controller.validate_action_inputs.side_effect = ValueError('handoff rejected')
            elif mutant == 'inputs_missing':
                request.pop('hardware_control')
            elif mutant == 'inputs_extra':
                request['synthetic_test_only'] = True
            elif mutant == 'inputs_plan':
                request['plan'] = dict(plan, source_revision='d' * 40)
            elif mutant == 'source':
                validation.resolutions['S17-EXT-006'].semantic_context['source_revision'] = 'c' * 40
            with self.subTest(mutant=mutant), patch.object(prep.importlib, 'import_module', return_value=admin):
                with self.assertRaises(ValueError):
                    prep.fresh_admission(args, plan, request)
            if mutant == 'packet':
                fresh.assert_not_called()

    def test_source_has_no_registration_initialization_metadata_write_or_signing_calls(self):
        tree = ast.parse(Path(prep.__file__).read_bytes())
        forbidden = {'prepare_family', 'append', 'retain_metadata', 'initialize', 'initialize_program',
                     'write_bytes', 'write_text', 'sign', 'execute_once', 'execute_formal'}
        calls = {n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                 for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Attribute, ast.Name))}
        self.assertEqual(calls & forbidden, set())
        parser_text = Path(prep.__file__).read_text()
        self.assertNotIn("add_argument('--register'", parser_text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
