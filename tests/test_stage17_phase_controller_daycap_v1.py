"""Software-only D254 controller admission; no stand, worker or raw validation.

The handoff and overlay boundaries have their own real-byte suites. Here their
returned metadata is synthetic so the unchanged controller admission body can
be exercised without fabricating qualification or starting a capture.
"""
from __future__ import annotations

import ast
import copy
import datetime as dt
import hashlib
import inspect
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_phase_controller_daycap_v1 as current
import stage17_state_journal_v52 as old_journal
import test_stage17_phase_controller_v25 as old_tests
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_service_daycap_v1 import select_repetitions
from test_stage17_q16a_handoff_v1 import fixture as retained_fixture


def save(path, value, *, transport=False):
    raw = current.registry.canonical(value) if transport else current.admission.canonical(value)
    path.write_bytes(raw)
    return dict(path=str(path), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class Configuration:
    def __init__(self, root, handoff_binding=None, stand='synthetic-stand'):
        self.root = root
        self.boot = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
        self.plan = dict(action_id='Q16a', stand_id=stand, source_revision=current.handoff.original.SOURCE)
        self.context = dict(schema_version=current.CONTEXT_SCHEMA, boot_id=self.boot,
            resolutions={
                'S17-EXT-004': dict(semantic_context=dict(stand_id=stand,
                    pilot_platform_measurements=dict(platform_manifest_sha256='f' * 64), retained_marker='old004')),
                'S17-EXT-006': dict(semantic_context=dict(stand_id=stand,
                    source_revision=current.handoff.original.SOURCE,
                    release_artifact_sha256=current.handoff.OLD_WORKER,
                    inventory_sha256=current.handoff.original.INVENTORY,
                    archive_bundle_root='/software-only/actual-old-bundle', retained_marker='old006'))},
            execution_authority=False, phase18_authority=False)
        context_binding = save(root / 'historical-context.json', self.context)
        plan_binding = save(root / 'actual-old-plan.json', self.plan)
        if handoff_binding is None:
            handoff_binding = save(root / 'handoff.json', dict(schema_version=current.handoff.original.SCHEMA))
        self.proof = dict(schema_version=current.handoff.SCHEMA,
            scope=dict(decision='D254', purpose=current.handoff.PURPOSE, stand_id=stand, boot_id=self.boot),
            original_plan=plan_binding, handoff=handoff_binding, execution_authority=False, phase18_authority=False)
        self.document = dict(schema_version=current.SCHEMA, historical_context=context_binding,
            original_plan=plan_binding, compatibility=save(root / 'compatibility.json', self.proof),
            boot_id=self.boot, execution_authority=False, phase18_authority=False)

    def configure(self):
        current.configure_historical_inputs(self.document, self.root)

    def rebind_context(self):
        self.document['historical_context'] = save(self.root / 'historical-context.json', self.context)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(current, '_HISTORICAL', None))
        self.temp = self.enterContext(tempfile.TemporaryDirectory(prefix='d254-controller-config-'))
        self.f = Configuration(Path(self.temp))

    def test_bound_json_context_and_actual_old_plan_loaded_without_shared_mutable_inputs(self):
        before = copy.deepcopy(self.f.document)
        self.f.configure()
        self.f.configure()
        self.assertEqual(before, self.f.document)
        config, context, validation, plan, proof = current._historical_inputs()
        self.assertEqual(plan, self.f.plan)
        self.assertEqual(context, self.f.context)
        self.assertEqual(config, self.f.document)
        self.assertEqual(proof, self.f.proof)
        self.assertEqual(validation.resolutions['S17-EXT-006'].semantic_context,
                         self.f.context['resolutions']['S17-EXT-006']['semantic_context'])
        # Subsequent admission rereads authenticated files, not caller objects.
        self.f.document['boot_id'] = 'changed'
        validation.resolutions['S17-EXT-006'].semantic_context['retained_marker'] = 'changed'
        self.assertEqual(current._historical_inputs()[2].resolutions['S17-EXT-006'].semantic_context['retained_marker'],
                         'old006')

    def test_configuration_is_required_and_cannot_be_replaced(self):
        with self.assertRaisesRegex(current.ControllerError, 'not configured'):
            current._historical_inputs()
        self.f.configure()
        foreign = Path(self.temp) / 'another-packet'
        foreign.mkdir()
        other = Configuration(foreign)
        with self.assertRaisesRegex(current.ControllerError, 'already pinned'):
            other.configure()

    def test_authority_unknown_fields_callbacks_and_wrong_schema_rejected(self):
        original = copy.deepcopy(self.f.document)
        for key, value in (('execution_authority', True), ('phase18_authority', 0),
                           ('consume', lambda: None), ('schema_version', 'unknown')):
            self.f.document = copy.deepcopy(original)
            self.f.document[key] = value
            with self.subTest(key=key), self.assertRaises(current.ControllerError):
                self.f.configure()

    def test_context_requires_exact_exported_resolutions_not_calibration(self):
        original = copy.deepcopy(self.f.context)
        mutations = (lambda d: d.update(schema_version=current.handoff.original.SCHEMA),
                     lambda d: d.update(execution_authority=True),
                     lambda d: d['resolutions'].pop('S17-EXT-004'),
                     lambda d: d['resolutions'].update(callback={}),
                     lambda d: d['resolutions']['S17-EXT-006']['semantic_context'].update(source_revision='c' * 40),
                     lambda d: d['resolutions']['S17-EXT-006']['semantic_context'].update(release_artifact_sha256='c' * 64),
                     lambda d: d['resolutions']['S17-EXT-006']['semantic_context'].update(inventory_sha256='c' * 64),
                     lambda d: d.update(boot_id='00000000-0000-0000-0000-000000000000'))
        for index, mutate in enumerate(mutations):
            self.f.context = copy.deepcopy(original)
            mutate(self.f.context)
            self.f.rebind_context()
            with self.subTest(index=index), self.assertRaises(current.ControllerError):
                self.f.configure()

    def test_binding_mutation_symlinks_and_packet_escape_rejected(self):
        original = copy.deepcopy(self.f.document)
        for key in ('historical_context', 'original_plan', 'compatibility'):
            self.f.document = copy.deepcopy(original)
            self.f.document[key]['sha256'] = '0' * 64
            with self.subTest(key=key), self.assertRaises(current.ControllerError):
                self.f.configure()
        self.f.document = copy.deepcopy(original)
        link = self.f.root / 'context-link.json'
        link.symlink_to(self.f.document['historical_context']['path'])
        self.f.document['historical_context']['path'] = str(link)
        with self.assertRaises(current.ControllerError):
            self.f.configure()
        nested = self.f.root / 'nested'
        nested.mkdir()
        self.f.document['historical_context'] = save(nested / 'context.json', self.f.context)
        with self.assertRaisesRegex(current.ControllerError, 'packet namespace'):
            self.f.configure()

    def test_each_pinned_file_is_reauthenticated_at_use(self):
        self.f.configure()
        for key in ('historical_context', 'original_plan', 'compatibility'):
            path = Path(self.f.document[key]['path'])
            before = path.read_bytes()
            path.write_bytes(before + b' ')
            with self.subTest(key=key), self.assertRaises(current.ControllerError):
                current._historical_inputs()
            path.write_bytes(before)

    def test_bound_plan_or_proof_cannot_substitute_another_source_stand_or_scope(self):
        self.f.plan['source_revision'] = 'c' * 40
        self.f.document['original_plan'] = save(self.f.root / 'actual-old-plan.json', self.f.plan)
        self.f.proof['original_plan'] = self.f.document['original_plan']
        self.f.document['compatibility'] = save(self.f.root / 'compatibility.json', self.f.proof)
        with self.assertRaisesRegex(current.ControllerError, 'actual old plan source'):
            self.f.configure()


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = select_repetitions(archived_fixture('Q16b'), 2)
        cls.plan['budget']['cleanup_ns'] += 1_000_000_000
        cls.plan['budget']['watchdog_ns'] += 1_000_000_000

    def setUp(self):
        self.enterContext(patch.object(current, '_HISTORICAL', None))
        self.base = old_tests.FormalController()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.request = self.base.request
        self.plan = copy.deepcopy(self.__class__.plan)
        self.plan.update(source_revision='c' * 40, stand_id=self.request['stand_id'])
        self.base.context['source_revision'] = self.plan['source_revision']
        self.document, _, _ = retained_fixture()
        handoff_binding = self.base.write('retained-handoff.json', self.document)
        for item in self.plan['captures']:
            if item['capture']['package'] == 'R2':
                item['capture']['ring_distance']['calibration_evidence_id'] = 'q16a-sha256-' + handoff_binding['sha256']
        self.request.update(action_id='Q16b', schema_version='cpu-prefetch-stage17-fixed-action-request/6')
        self.request['action_inputs']['plan'] = self.plan
        self.request['action_inputs']['prerequisite_bindings']['q16a_validation'] = handoff_binding
        self.f = Configuration(self.base.root, handoff_binding)
        self.f.configure()
        self.bind_namespace()
        self.result = dict(ring_geometry=[dict(capacity=64, cache_line_bytes=64) for _ in range(6)],
                           derived_result=dict(contexts=[dict(distance=dict(d2_cache_lines=2)) for _ in range(6)]))

    def bind_namespace(self):
        self.base.namespace.update(plan_sha256=hashlib.sha256(current.registry.archive.canonical(self.plan)).hexdigest(),
            stand_id=self.plan['stand_id'], phase_identities=[item['capture'][phase] for item in self.plan['captures']
                                                            for phase in ('warmup', 'measurement')])
        self.request['action_inputs']['prerequisite_bindings']['namespace_registry'] = self.base.write(
            'daycap-namespace.json', self.base.namespace)

    def validate(self):
        with patch.object(current.handoff, 'consume', return_value=self.result) as consume:
            extent = current._validate_inputs(self.request, self.base.validation)
            return extent, consume

    def test_complete_original_body_accepts_120_and_fixed_old_inputs_reach_handoff(self):
        before = copy.deepcopy(self.request)
        extent, consume = self.validate()
        self.assertEqual(len(extent.captures), 120)
        self.assertEqual(self.request, before)
        args, kwargs = consume.call_args
        self.assertEqual(args, (self.document,))
        self.assertIs(kwargs['validation'], self.base.validation)
        self.assertIs(kwargs['plan'], self.plan)
        self.assertEqual(kwargs['original_plan'], self.f.plan)
        self.assertEqual(kwargs['original_validation'].resolutions['S17-EXT-006'].semantic_context,
                         self.f.context['resolutions']['S17-EXT-006']['semantic_context'])
        self.assertEqual(kwargs['compatibility'], self.f.document['compatibility'])
        self.assertEqual(kwargs['original_boot_id'], self.f.boot)
        self.assertEqual(kwargs['boot_id'], self.f.boot)
        self.assertEqual(kwargs['selected_duration_ns'], 1_000_000_000)
        self.assertFalse(extent.execution_authority)

    def test_runtime_qualified_source_changes_without_any_controller_source_constant(self):
        self.plan['source_revision'] = self.base.context['source_revision'] = 'd' * 40
        self.bind_namespace()
        self.assertEqual(len(self.validate()[0].captures), 120)

    def test_source_hardware_discovery_and_namespace_guards_remain_original(self):
        request, context = copy.deepcopy(self.request), copy.deepcopy(self.base.context)
        mutations = (
            lambda: self.base.context.update(source_revision='f' * 40),
            lambda: self.base.context.update(runtime_profile='UNQUALIFIED'),
            lambda: self.request['action_inputs']['hardware_control'].update(q15_w_result_sha256='0' * 64),
            lambda: [item['monitoring']['hardware_identity'].update(model=85) for item in self.plan['captures']],
            lambda: self.request['action_inputs']['prerequisite_bindings'].update(q16b_validation={}),
            lambda: self.request['action_inputs']['prerequisite_bindings'].update(schedule_sources=[{}]),
            lambda: self.request['action_inputs']['prerequisite_bindings']['namespace_registry'].update(sha256='0' * 64))
        for index, mutate in enumerate(mutations):
            self.request = copy.deepcopy(request)
            self.plan = self.request['action_inputs']['plan']
            self.base.context.clear()
            self.base.context.update(context)
            mutate()
            with self.subTest(index=index), self.assertRaises(current.ControllerError):
                self.validate()

    def test_discovery_counts_selection_and_complete_namespace_stay_binding(self):
        self.base.discovery['validated_study']['selection']['selected_duration_ns'] = 2_000_000_000
        self.request['action_inputs']['prerequisite_bindings']['discovery_validation'] = self.base.write(
            'changed-discovery.json', self.base.discovery)
        with self.assertRaisesRegex(current.ControllerError, 'selection differs'):
            self.validate()

    def test_handoff_failure_and_ring_evidence_failure_cannot_fall_back(self):
        with patch.object(current.handoff, 'consume', side_effect=current.handoff.Error('rejected retained bytes')):
            with self.assertRaisesRegex(current.ControllerError, 'rejected retained bytes'):
                current._validate_inputs(self.request, self.base.validation)
        capture = next(item['capture'] for item in self.plan['captures'] if item['capture']['package'] == 'R2')
        capture['ring_distance']['calibration_evidence_id'] = 'foreign'
        with self.assertRaisesRegex(current.ControllerError, 'R2 distance/evidence'):
            self.validate()

    def test_public_validation_requires_new_overlay_and_propagates_qualification_failure(self):
        with patch.object(current.handoff, 'consume', return_value=self.result), \
             patch.object(current.overlay, 'qualified_profile', return_value='qualified') as qualify:
            self.assertEqual(len(current.validate_action_inputs(self.request, self.base.validation).captures), 120)
            qualify.assert_called_once()
            self.assertIs(qualify.call_args.args[0], self.request)
            self.assertIs(qualify.call_args.args[1], self.base.validation)
        with patch.object(current.handoff, 'consume', return_value=self.result), \
             patch.object(current.overlay, 'qualified_profile', side_effect=ValueError('profile drift')):
            with self.assertRaisesRegex(current.ControllerError, 'profile drift'):
                current.validate_action_inputs(self.request, self.base.validation)

    def test_non_daycap_inputs_and_profiles_delegate_to_original_v27_v28(self):
        request = dict(action_id='Q16c', action_inputs=dict(plan=dict(schema_version='historical')))
        with patch.object(current.original_v27, '_validate_inputs', return_value='old-inputs') as validate:
            self.assertEqual(current._validate_inputs(request, self.base.validation), 'old-inputs')
            validate.assert_called_once_with(request, self.base.validation)
        with patch.object(current.original_v28, 'qualified_archive_profile', return_value='old-profile') as profile:
            self.assertEqual(current.qualified_archive_profile(request, self.base.validation, deadline_ns=123), 'old-profile')
            profile.assert_called_once_with(request, self.base.validation, deadline_ns=123)


class PrivateGraphTests(unittest.TestCase):
    def tearDown(self):
        current.activate()

    def test_one_private_graph_binds_v25_and_v26_to_journal54(self):
        self.assertEqual(current.journal_runtime.__name__, 'stage17_state_journal_v54')
        self.assertIs(current._v26.previous, current._v25)
        self.assertIs(current._v26._prepare_action, current._prepare_archive)
        for name in ('_prepare_action', '_prepare_legacy', 'runtime_from_context'):
            function = getattr(current._v25, name)
            self.assertIs(function.__code__, getattr(current.original_v25, name).__code__)
            self.assertIs(function.__globals__['journal_runtime'], current.journal_runtime)
            self.assertIs(function.__globals__['activate'], current.activate)
        self.assertIs(current._v25._prepare_action.__globals__['_prepare_legacy'], current._v25._prepare_legacy)
        self.assertIs(current.runtime_from_context, current._v25.runtime_from_context)
        self.assertIs(current._runtime_from_context, current.original_v25._runtime_from_context)
        self.assertIs(current._validate_action_inputs, current.original_v25._validate_action_inputs)

    def test_q15_legacy_attributes_and_utc_signatures_are_preserved(self):
        self.assertIs(current.predecessor._parse_utc, current.support._parse_utc)
        self.assertIs(current.predecessor._now, current.support._now)
        self.assertEqual(current.predecessor._parse_utc('2030-01-01T00:00:00Z'),
                         dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc))
        for name, value in vars(current.original_v25.predecessor).items():
            self.assertIs(getattr(current.predecessor, name), value)
        self.assertIs(current.PreparedAction, current.original_v25.PreparedAction)
        self.assertEqual(inspect.signature(current._runtime_from_context),
                         inspect.signature(current.original_v25._runtime_from_context))
        self.assertEqual(inspect.signature(current._validate_action_inputs),
                         inspect.signature(current.original_v25._validate_action_inputs))

    def test_archive_preparation_is_v26_body_with_only_private_aliases(self):
        original = ast.parse(inspect.getsource(current.original_v26._prepare_action)).body[0]
        adapted = ast.parse(inspect.getsource(current._prepare_archive)).body[0]
        self.assertIsInstance(original.body[0], ast.Import)
        original.body = original.body[1:]
        class PrivateAliases(ast.NodeTransformer):
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == 'previous' and node.attr == 'PreparedAction':
                    return ast.Name(id='PreparedAction', ctx=ast.Load())
                return self.generic_visit(node)
            def visit_Name(self, node):
                if node.id == 'previous':
                    node.id = '_v25'
                return node
        PrivateAliases().visit(original)
        self.assertEqual([ast.dump(node) for node in original.body], [ast.dump(node) for node in adapted.body])

    def test_import_and_private_graph_do_not_mutate_original_v25_v26_dispatch(self):
        self.assertIs(current.original_v25.journal_runtime, old_journal)
        for name in ('_prepare_action', '_prepare_legacy', 'validate_action_inputs'):
            original = getattr(current.original_v25, name)
            self.assertIs(original.__globals__['journal_runtime'], old_journal)
            self.assertIsNot(original.__globals__, getattr(current._v25, name).__globals__)
        self.assertIs(current.original_v26.previous, current.original_v25)
        imports = ast.parse(Path(current.__file__).read_text())
        names = [alias.name for node in ast.walk(imports) if isinstance(node, ast.Import) for alias in node.names]
        self.assertNotIn('stage17_state_journal_v53', names)

    def test_activation_restores54_after_old52_side_effect_even_on_preparation_error(self):
        old_journal.activate()
        with patch.object(current._v26, '_prepare_action', side_effect=ValueError('stop')), \
             patch.object(current.journal_runtime, 'activate', wraps=current.journal_runtime.activate) as activate:
            with self.assertRaisesRegex(ValueError, 'stop'):
                current.prepare_action()
            activate.assert_called_once_with()

    def test_nonformal_preparation_uses_actual_private_legacy_body_and_journal54(self):
        captured = []
        def stop(**arguments):
            captured.append(arguments)
            raise RuntimeError('legacy body reached')
        # Exercise v25's real legacy wrapper. Its inner v24 binding must receive
        # journal54 and activation54, including the old formal preparation hook.
        original = current._v25._with_globals
        def inspect_bindings(function, replacements, arguments):
            if function is current.original_v25.predecessor.prepare_action:
                self.assertIs(replacements['journal_runtime'], current.journal_runtime)
                self.assertIs(replacements['activate'], current.activate)
                return stop(**arguments)
            return original(function, replacements, arguments)
        scope = current._v25._prepare_legacy.__globals__
        with patch.dict(scope, _with_globals=inspect_bindings):
            with self.assertRaisesRegex(RuntimeError, 'legacy body reached'):
                current._v25._prepare_legacy(authorization_path='software-only')
        self.assertEqual(captured, [dict(authorization_path='software-only')])

    def test_retention_flag_is_preserved_and_archive_preparation_requires_one_profile(self):
        for retention in (False, True):
            with patch.object(current._v26, '_prepare_action', return_value='prepared') as prepare:
                method = current.prepare_retention if retention else current.prepare_action
                self.assertEqual(method(marker='software-only'), 'prepared')
                prepare.assert_called_once_with(for_retention=retention, marker='software-only')

    def test_executor_uses_daycap_factory_with_exact_prepared_authority_and_bytes(self):
        request = dict(action_id='Q16b', schema_version='cpu-prefetch-stage17-fixed-action-request/6',
            action_inputs=dict(plan=dict(schema_version=current.daycap.VERSION)),
            evidence_root_binding=dict(absolute_path='/software-only/output'))
        prepared = types.SimpleNamespace(root=ROOT, request=request, request_bytes=b'original-request\n',
            authorization={'original': 'auth'}, authorization_bytes=b'original-auth\n', runtime={'original': 'runtime'},
            worker_path=Path('/software-only/worker'), release={'original': 'release'}, archive_runtime_profile=object())
        executor = types.SimpleNamespace(execute_fixed_action=Mock(return_value='executed'))
        with patch.object(current, 'prepare_action', return_value=prepared), \
             patch.object(current.execution, 'make_executor', return_value=executor) as factory:
            self.assertEqual(current.execute_once(synthetic_test_only=True), 'executed')
        factory.assert_called_once_with()
        executor.execute_fixed_action.assert_called_once_with(repository_root=ROOT,
            authorization=prepared.authorization, authorization_bytes=prepared.authorization_bytes,
            request=request, request_bytes=prepared.request_bytes, worker_binding=prepared.runtime,
            worker_path=prepared.worker_path, release_binding=prepared.release,
            output_root=Path('/software-only/output'), archive_runtime_profile=prepared.archive_runtime_profile,
            synthetic_test_only=True)


class AuthorityTests(unittest.TestCase):
    """Real SSHSIG and byte custody through v25's unchanged authority body."""
    @classmethod
    def setUpClass(cls):
        if not hasattr(ControllerTests, 'plan'):
            ControllerTests.setUpClass()

    def setUp(self):
        case = ControllerTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        self.case = case
        self.root = case.base.root
        self.validation = case.base.validation
        for i in range(1, 7):
            key = f'S17-EXT-{i:03d}'
            row = self.validation.resolutions.setdefault(key, types.SimpleNamespace(semantic_context={}))
            row.input_id, row.resolution_id, row.sha256 = key, 'software-resolution-' + str(i), str(i) * 64
        key = self.root / 'key'
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)],
                       capture_output=True, check=True, timeout=10)
        allowed = self.root / 'allowed-signers'
        allowed.write_text('software-owner ' + key.with_suffix('.pub').read_text())
        trust = dict(subject_id=case.plan['stand_id'], measurements=dict(principal='software-owner',
            reviewer_role='OWNER', sshsig_namespace='stage17-owner-acceptance', allowed_signers_path=str(allowed),
            allowed_signers_size_bytes=allowed.stat().st_size, allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest()))
        self.validation.resolutions['S17-EXT-003'].semantic_context['trust'] = trust
        worker = self.root / 'inert-worker'
        worker.write_bytes(b'synthetic worker bytes; never executed')
        case.base.context.update(release_artifact_path=str(worker), release_artifact_size_bytes=worker.stat().st_size,
                                 release_artifact_sha256=hashlib.sha256(worker.read_bytes()).hexdigest())
        pinned = current.registry.pin_registry(ROOT)
        definition = pinned.action('Q16b')
        self.validation.current_state = definition['required_state']
        expected = [current.original_v25.old._binding(self.validation.resolutions[key])
                    for key in definition['required_resolution_ids']]
        runtime, release, _ = current.runtime_from_context(self.validation)
        request = case.request
        request.update(request_id='software-request', session_id='software-session', authorization_id='software-auth',
            attempt_id='software-attempt', runtime_binding=runtime, release_binding=release,
            predecessor_resolutions=expected, synthetic_test_only=True, phase18_authority=False)
        # Use the production root binding shape, including actual filesystem identity.
        import stage17_operational_cli_v18 as cli
        request['evidence_root_binding'] = cli.base._root_binding(self.root)
        request_binding = save(self.root / 'request.json', request, transport=True)
        policy = current.deadline_policy(current.daycap.validate_plan(case.plan))
        now = dt.datetime.now(dt.timezone.utc)
        stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
        self.authorization = dict(schema_version='cpu-prefetch-stage17-phase-action-authorization/6',
            authorization_id=request['authorization_id'], session_id=request['session_id'], action_id='Q16b',
            actor='software-owner', reviewer='OWNER', target=dict(stand_id=case.plan['stand_id']),
            issued_at_utc=stamp(now - dt.timedelta(seconds=1)), expires_at_utc=stamp(now + dt.timedelta(seconds=120)),
            trust_context=dict(ext002_resolution=expected[1], ext003_resolution=expected[2]),
            predecessor_resolutions=expected, fixed_action_definition_sha256=pinned.plan_sha256,
            request_binding=request_binding, evidence_root_binding=request['evidence_root_binding'],
            permission_matrix=definition['permission_matrix'], deadline_policy=policy,
            one_attempt=True, retry_allowed=False, stop_first=True, retain_partial=True, stage18_authority=False)
        self.path = self.root / 'authorization.json'
        self.sign()
        self.arguments = dict(repository_root=ROOT, operational_evidence_root=self.root,
            journal=self.root / 'journal.json', journal_directory=self.root, authorization_path=self.path,
            signature_path=Path(str(self.path) + '.sig'), synthetic_test_only=True)
        self.enterContext(patch.object(current.journal_runtime, 'validate_operational_journal', return_value=self.validation))
        self.enterContext(patch.object(current.handoff, 'consume', return_value=case.result))
        self.profile = object()
        self.qualify = self.enterContext(patch.object(current.overlay, 'qualified_profile', return_value=self.profile))

    def sign(self):
        save(self.path, self.authorization, transport=True)
        signature = Path(str(self.path) + '.sig')
        if signature.exists():
            signature.unlink()
        subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'sign', '-f', str(self.root / 'key'),
                        '-n', 'stage17-owner-acceptance', str(self.path)],
                       capture_output=True, check=True, timeout=10)

    def test_real_signature_prepare_and_retention_use_journal54_and_profile_once(self):
        for method in (current.prepare_action, current.prepare_retention):
            self.qualify.reset_mock()
            prepared = method(**self.arguments)
            self.assertIsInstance(prepared, current.PreparedArchiveAction)
            self.assertIs(prepared.validation, self.validation)
            self.assertIs(prepared.archive_runtime_profile, self.profile)
            self.assertEqual(prepared.authorization_bytes, self.path.read_bytes())
            self.assertEqual(prepared.request_bytes, Path(self.authorization['request_binding']['path']).read_bytes())
            self.qualify.assert_called_once()

    def test_changed_authority_signature_and_fresh_expiry_fail_closed(self):
        self.authorization['authorization_id'] = 'tampered'
        save(self.path, self.authorization, transport=True)
        with self.assertRaises(current.support.ControllerError):
            current.prepare_action(**self.arguments)
        self.authorization['authorization_id'] = 'software-auth'
        now = dt.datetime.now(dt.timezone.utc)
        stamp = lambda value: value.isoformat(timespec='seconds').replace('+00:00', 'Z')
        self.authorization.update(issued_at_utc=stamp(now - dt.timedelta(seconds=120)),
                                  expires_at_utc=stamp(now - dt.timedelta(seconds=1)))
        self.sign()
        with self.assertRaisesRegex(current.ControllerError, 'authority window'):
            current.prepare_action(**self.arguments)
        # Historical retention authenticates bytes after expiry but grants no launch.
        self.assertIsInstance(current.prepare_retention(**self.arguments), current.PreparedArchiveAction)


if __name__ == '__main__':
    unittest.main()
