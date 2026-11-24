"""D254 metadata gates only: no raw validation, native work or stand access.

Synthetic bundles exercise real bound reads, source closure, schemas and strict
retained codegen checks. Public success tests stub the immutable old admission
and old release boundary: synthetic bytes cannot have the pinned D246 digests.
Separate parity tests call the real original consumer on its audited artifacts.
Nothing here establishes qualification or scientific validity.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_q16a_daycap_handoff_v1 as current
from test_stage17_q16a_handoff_v1 import fixture as retained_fixture
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_service_daycap_v1 import select_repetitions

SOURCE = 'a245baad58bfb43af33412e4c5a7712b15a3287f'


def binding(path):
    data = path.read_bytes()
    return dict(path=str(path), size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def save(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(current.admission.canonical(document))
    return binding(path)


def strict_report(root, worker):
    operations = {}
    for worker_spec in current.codegen.expected_workers():
        vector = worker_spec.vector()
        witnesses = [[i, opcode] for i, opcode in enumerate(
            opcode for opcode, count in vector.items() for _ in range(count))]
        operations[worker_spec.key()] = dict(native_reference_path='synthetic', raw_clock_call_sites={'clock': [1]},
            root_address=1, active_addresses=[1], cold_boundary_addresses=[2],
            prefetch_vector=vector, prefetch_witnesses=witnesses)
    tools = {kind: dict(status='PASS', version=version, disassembly_sha256='a' * 64,
                       negative_checks={name: 'REJECTED' for name in current.codegen.NEGATIVE_CASES},
                       operations=copy.deepcopy(operations))
             for kind, version in (('GNU_OBJDUMP', '2.46'), ('LLVM_OBJDUMP', '22.1.0'))}
    return dict(schema_version=current.codegen.SCHEMA, status='PASS', missing_tools=[],
        binary_sha256=worker['sha256'], rule_set_sha256=binding(root / 'tools/check_formal_codegen.py')['sha256'],
        source_evidence={name: binding(root / name)['sha256'] for name in current.codegen.SOURCE_PATHS}, tools=tools)


class Evidence:
    def __init__(self, root, plan):
        self.root, self.plan = root, copy.deepcopy(plan)
        self.plan.update(source_revision=SOURCE, stand_id='CPU-PREFETCH-V5')
        self.boot = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
        captures = []
        for placement in ('NEAR', 'FAR'):
            for working_set in current.daycap.native.WORKING_SETS:
                capture = next(item['capture'] for item in self.plan['captures']
                               if item['capture']['placement'] == placement and
                               item['capture']['working_set_class'] == working_set)
                captures.append(dict(capture=copy.deepcopy(capture)))
        self.original_plan = dict(action_id='Q16a', source_revision=current.original.SOURCE,
                                  stand_id=self.plan['stand_id'], captures=captures)
        self.result = dict(stand_id=self.plan['stand_id'], source_populations=[dict(
            source_revision=current.original.SOURCE,
            plan_sha256=hashlib.sha256(current.admission.canonical(self.original_plan)).hexdigest())],
            execution_authority=False, phase18_authority=False, family_validity_established=False,
            producer_authentication_established=False,
            ring_geometry=[dict(context_ordinal=i, capacity=64, cache_line_bytes=64, slot_storage_bytes=512,
                                source_binding=dict(artifact_id='synthetic-native', size_bytes=1, sha256='b' * 64))
                           for i in range(6)],
            derived_result=dict(contexts=[dict(distance=dict(d2_cache_lines=2)) for _ in range(6)]))
        self.proof = dict(schema_version=current.SCHEMA, scope=dict(decision='D254', purpose=current.PURPOSE,
                          stand_id=self.plan['stand_id'], boot_id=self.boot),
                          execution_authority=False, phase18_authority=False)
        self.releases, self.contexts = {}, {}
        names = set(current.codegen.SOURCE_PATHS) | set(current.HEADERS) | {
            'tools/check_formal_codegen.py', 'include/cpu_prefetch/extra_dependency.hpp'}
        for side in ('original', 'current'):
            bundle = root / side
            rows = []

            def write(name, raw):
                path = bundle / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                bound = binding(path)
                rows.append(dict(bound, path=name))
                return bound

            for name in sorted(names):
                data = (ROOT / name).read_bytes() if name == current.COLD_SOURCE and side == 'current' else name.encode()
                write(name, data)
            write(current.QUEUE, b'identical synthetic static archive')
            worker = write('release/bin/cpu_prefetch_runner', b'synthetic worker ' + side.encode())
            report = strict_report(bundle, worker)
            report_binding = write('build-provenance/formal_codegen_report.json', current.admission.canonical(report))
            inventory = save(bundle / 'BUNDLE_INVENTORY.json', dict(files=rows))
            source = current.original.SOURCE if side == 'original' else SOURCE
            self.proof[side] = dict(source_revision=source, bundle_root=str(bundle), worker=worker,
                                   bundle_inventory=inventory, formal_codegen=report_binding)
            index = {row['path']: row for row in rows}
            self.releases[side] = str(bundle), index, report
            self.contexts[side] = dict(source_revision=source, archive_bundle_root=str(bundle),
                inventory_sha256=inventory['sha256'], release_artifact_path=worker['path'],
                release_artifact_size_bytes=worker['size_bytes'], release_artifact_sha256=worker['sha256'],
                stand_id=self.plan['stand_id'])

        def member(side, name):
            bundle, index, _ = self.releases[side]
            return dict(index[name], path=str(Path(bundle) / name))

        def comparison(name):
            return dict(relative_path=name, original=member('original', name), current=member('current', name))

        self.proof['source_comparisons'] = [comparison(name) for name in sorted(names)]
        self.proof['project_headers'] = [comparison(name) for name in current.HEADERS]
        self.proof['queue_libraries'] = {side: member(side, current.QUEUE) for side in self.releases}
        geometry = dict(shared_queue_libraries=dict(continuation=member('original', current.QUEUE)),
                        verified_headers=list(current.HEADERS))
        self.document = dict(schema_version=current.original.SCHEMA, execution_authority=False, phase18_authority=False,
                             geometry=save(root / 'retained-geometry.json', geometry))
        self.proof['handoff'] = save(root / 'handoff.json', self.document)
        self.proof['original_plan'] = save(root / 'original-plan.json', self.original_plan)
        self.proof['plan'] = save(root / 'plan.json', self.plan)
        evidence_id = 'q16a-sha256-' + self.proof['handoff']['sha256']
        for item in self.plan['captures']:
            if item['capture']['package'] == 'R2':
                item['capture']['ring_distance']['calibration_evidence_id'] = evidence_id
        self.proof['plan'] = save(root / 'plan.json', self.plan)
        self.proof['native_geometry'] = save(root / 'native.json', dict(
            schema_version='software-native-ring-slot-geometry/1', source_revision=SOURCE,
            source_dirty=False, api='RingSpscQueue::storage_requirements', hardware_observation=False,
            execution_authority=False, records=[{key: row[key] for key in (
                'context_ordinal', 'capacity', 'cache_line_bytes', 'slot_storage_bytes')}
                for row in self.result['ring_geometry']]))
        self.proof['platform_manifests'] = {}
        self.validation = self.validation_for(self.contexts['current'])
        self.original_validation = self.validation_for(dict(self.contexts['original'],
            inventory_sha256=current.original.INVENTORY, release_artifact_sha256=current.OLD_WORKER))

    def validation_for(self, context):
        side = 'original' if context['source_revision'] == current.original.SOURCE else 'current'
        platform = json.loads((ROOT / 'docs/evidence/stage17/FORMAL-Q16A-V23-FIRST-CAPTURE-20261103-01/'
            'qualification/ext004-authoring-records-1/platform-manifest.json').read_bytes())
        result_sha = ('d' if side == 'original' else 'e') * 64
        clock_id, readback_id, auth_id = (f'synthetic-{side}-{role}' for role in ('clock', 'readback', 'auth'))
        platform['platform_id'] = self.plan['stand_id']
        platform['record_sha256'] = result_sha
        platform['clock']['acceptance_record_id'] = clock_id
        for row in platform['hardware_prefetch_states']:
            row.update(readback_artifact_id=readback_id, behavioral_probe_artifact_id=readback_id,
                       privileged_authority_id=auth_id if row['requested'] == 'H0' else 'NONE')
        platform_binding = save(self.root / (side + '-platform.json'), platform)
        self.proof['platform_manifests'][side] = platform_binding
        return SimpleNamespace(resolutions={
            'S17-EXT-006': SimpleNamespace(semantic_context=context),
            'S17-EXT-004': SimpleNamespace(semantic_context=dict(stand_id=self.plan['stand_id'],
                pilot_platform_measurements=dict(platform_manifest_sha256=platform_binding['sha256'],
                                                  q15_r_result_sha256=result_sha),
                q15_r=dict(result_sha256=result_sha, authorization=dict(authorization_id=auth_id),
                           result=dict(artifacts=[dict(sha256='a' * 64)])),
                qualification_evidence=[dict(kind='SELECTED_PAIR_CLOCK', artifact_id=clock_id,
                    eligible=True, stand_id=self.plan['stand_id'])],
                artifact_index={clock_id: dict(sha256='b' * 64), readback_id: dict(sha256='a' * 64)}))})

    def consume(self):
        compat = save(self.root / 'compatibility.json', self.proof)
        actual_release = current._release

        def release(side, context, reader, expected_source):
            # Only the old archival boundary is stubbed. The current release,
            # all source/header/library bytes and codegen checks are real.
            if expected_source == current.original.SOURCE:
                return self.releases['original']
            return actual_release(side, context, reader, expected_source)

        with patch.object(current.original, 'consume', return_value=self.result) as delegated, \
             patch.object(current, '_release', side_effect=release):
            result = current.consume(self.document, validation=self.validation, plan=self.plan,
                selected_duration_ns=1_000_000_000, original_validation=self.original_validation,
                original_plan=self.original_plan, compatibility=compat, original_boot_id=self.boot, boot_id=self.boot)
            delegated.assert_called_once_with(self.document, validation=self.original_validation,
                plan=self.original_plan, selected_duration_ns=1_000_000_000)
            return result


class DaycapHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.legacy = archived_fixture('Q16b')
        cls.plan = select_repetitions(cls.legacy, 2)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='d254-metadata-')
        self.addCleanup(self.temp.cleanup)
        self.f = Evidence(Path(self.temp.name), self.plan)

    def reject(self, mutate, message):
        mutate()
        with self.assertRaises(current.Error) as caught:
            self.f.consume()
        self.assertIn(message, str(caught.exception))

    def test_source_compatible_success_returns_original_object_and_flags_without_mutation(self):
        before = copy.deepcopy((self.f.plan, self.f.original_plan, self.f.result, self.f.proof))
        self.assertIs(self.f.consume(), self.f.result)
        self.assertEqual((self.f.plan, self.f.original_plan, self.f.result, self.f.proof), before)
        for name in ('execution_authority', 'phase18_authority', 'family_validity_established',
                     'producer_authentication_established'):
            self.assertIs(self.f.result[name], False)
        self.assertEqual(self.f.result['source_populations'][0]['source_revision'], current.original.SOURCE)

    def test_actual_bound_historical_q16b_plan_can_be_the_original_consumer_argument(self):
        self.f.original_plan = copy.deepcopy(self.legacy)
        self.f.original_plan.update(source_revision=current.original.SOURCE, stand_id=self.f.plan['stand_id'])
        self.f.proof['original_plan'] = save(self.f.root / 'signed-old-service-plan.json', self.f.original_plan)
        before = copy.deepcopy(self.f.original_plan)
        self.assertIs(self.f.consume(), self.f.result)
        self.assertEqual(self.f.original_plan, before)
        self.assertEqual(self.f.original_plan['repetitions_per_cell'], 59)

    def test_new_daycap_plan_cannot_be_relabelled_as_historical_consumer_argument(self):
        self.f.original_plan = copy.deepcopy(self.f.plan)
        self.f.original_plan['source_revision'] = current.original.SOURCE
        self.f.proof['original_plan'] = save(self.f.root / 'projected-old-plan.json', self.f.original_plan)
        self.reject(lambda: None, 'actual signed historical service plan version')

    def test_real_release_binding_checks_both_sides_without_substituting_identities(self):
        for side in ('original', 'current'):
            reader = current.admission.BoundReader()
            release = self.f.proof[side]
            actual = current._release(release, self.f.contexts[side], reader, release['source_revision'])
            self.assertEqual(actual, self.f.releases[side])
            reader.finish()
        context = dict(self.f.contexts['original'], release_artifact_sha256=current.OLD_WORKER)
        with self.assertRaisesRegex(current.Error, 'actual qualified worker'):
            current._release(self.f.proof['original'], context, current.admission.BoundReader(), current.original.SOURCE)

    def test_old_plan_projection_or_changed_bound_document_rejected(self):
        self.reject(lambda: self.f.original_plan.update(source_revision=SOURCE), 'bound actual original_plan')

    def test_rebound_changed_old_plan_still_rejected_by_retained_population_identity(self):
        self.f.original_plan['unreviewed'] = True
        self.f.proof['original_plan'] = save(self.f.root / 'original-plan.json', self.f.original_plan)
        self.reject(lambda: None, 'actual completed source42 plan identity')

    def test_old_worker_and_inventory_remain_fixed(self):
        for field in ('release_artifact_sha256', 'inventory_sha256'):
            with self.subTest(field=field):
                context = self.f.original_validation.resolutions['S17-EXT-006'].semantic_context
                before = context[field]
                context[field] = '0' * 64
                with self.assertRaisesRegex(current.Error, 'actual old'):
                    self.f.consume()
                context[field] = before

    def test_new_plan_must_match_exact_actual_qualified_source(self):
        self.reject(lambda: self.f.validation.resolutions['S17-EXT-006'].semantic_context.update(
            source_revision=current.original.SOURCE), 'actual new qualified source revision required')

    def test_current_source_is_runtime_qualification_not_original_review_revision(self):
        source = 'c' * 40
        self.f.plan['source_revision'] = source
        self.f.contexts['current']['source_revision'] = source
        self.f.proof['current']['source_revision'] = source
        self.f.proof['plan'] = save(self.f.root / 'plan.json', self.f.plan)
        bound = self.f.proof['native_geometry']
        native = json.loads(Path(bound['path']).read_bytes())
        native['source_revision'] = source
        self.f.proof['native_geometry'] = save(Path(bound['path']), native)
        self.assertIs(self.f.consume(), self.f.result)

    def test_current_worker_inventory_and_bundle_are_bound_to_qualification(self):
        context = self.f.validation.resolutions['S17-EXT-006'].semantic_context
        original = copy.deepcopy(context)
        for field, value in (('release_artifact_sha256', '0' * 64), ('release_artifact_size_bytes', 1),
                             ('inventory_sha256', '0' * 64), ('archive_bundle_root', str(self.f.root))):
            with self.subTest(field=field):
                context.update(original)
                context[field] = value
                with self.assertRaises(current.Error):
                    self.f.consume()

    def test_current_qualification_cannot_relabel_old_worker_inventory_or_bundle(self):
        context = self.f.validation.resolutions['S17-EXT-006'].semantic_context
        old = self.f.original_validation.resolutions['S17-EXT-006'].semantic_context
        before = copy.deepcopy(context)
        for field in ('release_artifact_sha256', 'inventory_sha256', 'archive_bundle_root'):
            with self.subTest(field=field):
                context.update(before)
                context[field] = old[field]
                with self.assertRaisesRegex(current.Error, 'must not relabel old'):
                    self.f.consume()

    def test_scope_authority_unknown_fields_and_boolean_types_fail_closed(self):
        original = copy.deepcopy(self.f.proof)
        for key, value in (('execution_authority', True), ('phase18_authority', 0), ('waiver', True)):
            with self.subTest(key=key):
                self.f.proof = copy.deepcopy(original)
                self.f.proof[key] = value
                with self.assertRaises(current.Error):
                    self.f.consume()
        self.f.proof = copy.deepcopy(original)
        self.reject(lambda: self.f.proof['scope'].update(purpose='GENERAL-REUSE'), 'compatibility reuse scope')

    def test_platform_and_stand_drift_rejected(self):
        self.reject(lambda: self.f.validation.resolutions['S17-EXT-004'].semantic_context[
            'pilot_platform_measurements'].update(platform_manifest_sha256='0' * 64), 'current qualified platform bytes')

    def test_fresh_platform_references_and_result_hashes_are_accepted(self):
        self.assertNotEqual(self.f.proof['platform_manifests']['original']['sha256'],
                            self.f.proof['platform_manifests']['current']['sha256'])
        self.assertIs(self.f.consume(), self.f.result)

    def test_rebound_physical_platform_and_clock_drift_fail_closed(self):
        bound = self.f.proof['platform_manifests']['current']
        original = json.loads(Path(bound['path']).read_bytes())
        context = self.f.validation.resolutions['S17-EXT-004'].semantic_context
        mutations = (lambda d: d['cpu'].update(microcode='different'),
                     lambda d: d['topology'].update(smt_enabled=False),
                     lambda d: d['memory'].update(base_page_bytes=8192),
                     lambda d: d['software'].update(kernel='different'),
                     lambda d: d['clock'].update(conversion_record_id='different'),
                     lambda d: d['hardware_prefetch_states'][0].update(verified='UNKNOWN'))
        for index, mutate in enumerate(mutations):
            document = copy.deepcopy(original)
            mutate(document)
            self.f.proof['platform_manifests']['current'] = save(Path(bound['path']), document)
            context['pilot_platform_measurements']['platform_manifest_sha256'] = binding(Path(bound['path']))['sha256']
            with self.subTest(index=index), self.assertRaisesRegex(current.Error, 'same actual'):
                self.f.consume()

    def test_rebound_foreign_clock_readback_authority_or_result_lineage_rejected(self):
        bound = self.f.proof['platform_manifests']['current']
        original = json.loads(Path(bound['path']).read_bytes())
        context = self.f.validation.resolutions['S17-EXT-004'].semantic_context
        mutations = (lambda d: d['clock'].update(acceptance_record_id='old-or-foreign-clock'),
                     lambda d: d['hardware_prefetch_states'][0].update(readback_artifact_id='foreign'),
                     lambda d: d['hardware_prefetch_states'][0].update(behavioral_probe_artifact_id='foreign'),
                     lambda d: d['hardware_prefetch_states'][0].update(privileged_authority_id='foreign'),
                     lambda d: d.update(record_sha256='0' * 64))
        for index, mutate in enumerate(mutations):
            document = copy.deepcopy(original)
            mutate(document)
            self.f.proof['platform_manifests']['current'] = save(Path(bound['path']), document)
            context['pilot_platform_measurements']['platform_manifest_sha256'] = binding(Path(bound['path']))['sha256']
            with self.subTest(index=index), self.assertRaises(current.Error):
                self.f.consume()

    def test_stand_drift_rejected(self):
        self.reject(lambda: self.f.validation.resolutions['S17-EXT-006'].semantic_context.update(stand_id='elsewhere'),
                    'qualified stand')

    def test_byte_identical_queue_and_all_three_headers_are_mandatory(self):
        for name in (current.QUEUE, *current.HEADERS):
            path = Path(self.f.proof['current']['bundle_root']) / name
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.subTest(name=name), self.assertRaises(current.Error):
                self.f.consume()
            path.write_bytes(original)
        self.reject(lambda: self.f.proof['project_headers'].pop(), 'exact comparison coverage')

    def test_even_rebound_different_queue_or_header_bytes_have_no_waiver(self):
        for name in (current.QUEUE, *current.HEADERS):
            old_index = self.f.releases['original'][1]
            old_binding = dict(old_index[name])
            path = Path(self.f.proof['original']['bundle_root']) / name
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            updated = binding(path)
            old_index[name] = dict(updated, path=name)
            row = (self.f.proof['queue_libraries'] if name == current.QUEUE else next(
                row for row in self.f.proof['project_headers'] if row['relative_path'] == name))
            previous = row['original']
            row['original'] = updated
            with self.subTest(name=name), self.assertRaisesRegex(current.Error, 'byte-identical'):
                self.f.consume()
            row['original'] = previous
            old_index[name] = old_binding
            path.write_bytes(original)

    def test_source_closure_no_omissions_duplicates_or_extra_cold_exceptions(self):
        rows = self.f.proof['source_comparisons']
        original = copy.deepcopy(rows)
        for replacement in (rows[:-1], rows[:-1] + rows[:1], rows + [dict(relative_path='src/foreign.cpp')]):
            self.f.proof['source_comparisons'] = replacement
            with self.assertRaises(current.Error):
                self.f.consume()
        self.f.proof['source_comparisons'] = original
        self.f.releases['original'][1]['src/extra.cpp'] = dict(path='src/extra.cpp', size_bytes=0, sha256='0' * 64)
        self.reject(lambda: None, 'strict qualified source closure')

    def test_rebound_measurement_change_and_unreviewed_cold_hash_rejected(self):
        for name in ('include/cpu_prefetch/extra_dependency.hpp', current.COLD_SOURCE):
            row = next(row for row in self.f.proof['source_comparisons'] if row['relative_path'] == name)
            path = Path(row['current']['path'])
            data, before = path.read_bytes(), copy.deepcopy(row['current'])
            path.write_bytes(data + b' unreviewed')
            row['current'] = binding(path)
            self.f.releases['current'][1][name] = dict(row['current'], path=name)
            # Refresh actual current inventory to reach the source comparison.
            side = self.f.proof['current']
            side['bundle_inventory'] = save(Path(side['bundle_root']) / 'BUNDLE_INVENTORY.json',
                dict(files=list(self.f.releases['current'][1].values())))
            self.f.contexts['current']['inventory_sha256'] = side['bundle_inventory']['sha256']
            with self.subTest(name=name), self.assertRaisesRegex(current.Error, 'byte-identical|reviewed cold'):
                self.f.consume()
            path.write_bytes(data)
            row['current'] = before
            self.f.releases['current'][1][name] = dict(before, path=name)

    def test_strict_codegen_semantic_body_proof_is_not_just_a_pass_flag(self):
        side = self.f.proof['original']
        report = self.f.releases['original'][2]
        report['tools']['LLVM_OBJDUMP']['operations'].pop(next(iter(report['tools']['LLVM_OBJDUMP']['operations'])))
        side['formal_codegen'] = save(Path(side['formal_codegen']['path']), report)
        self.reject(lambda: None, 'exact 42 native workers')

    def test_native_api_source_and_each_layout_field_must_match(self):
        bound = self.f.proof['native_geometry']
        doc = json.loads(Path(bound['path']).read_bytes())
        for field in ('capacity', 'cache_line_bytes', 'slot_storage_bytes', 'context_ordinal'):
            changed = copy.deepcopy(doc)
            changed['records'][5][field] += 1
            self.f.proof['native_geometry'] = save(Path(bound['path']), changed)
            with self.subTest(field=field), self.assertRaisesRegex(current.Error, 'current actual queue API layout'):
                self.f.consume()
        changed = copy.deepcopy(doc)
        changed['source_revision'] = current.original.SOURCE
        self.f.proof['native_geometry'] = save(Path(bound['path']), changed)
        self.reject(lambda: None, 'current native source_revision')

    def test_full_schema_and_semantic_daycap_body_are_required(self):
        original = copy.deepcopy(self.f.plan)
        mutations = (lambda p: p.update(extra=True), lambda p: p.update(repetitions_per_cell=59),
                     lambda p: p.update(method_id=current.daycap.COLLECTOR_METHOD),
                     lambda p: p['captures'][0]['capture'].update(method_id=current.daycap.METHOD),
                     lambda p: p['captures'].pop(),
                     lambda p: p['captures'][0]['execution_budget'].update(watchdog_ns=1))
        for index, mutate in enumerate(mutations):
            self.f.plan = copy.deepcopy(original)
            mutate(self.f.plan)
            self.f.proof['plan'] = save(self.f.root / 'plan.json', self.f.plan)
            with self.subTest(index=index), self.assertRaises(current.Error):
                self.f.consume()

    def test_all_sixty_settings_geometry_and_r2_evidence_checked(self):
        original = copy.deepcopy(self.f.plan)
        for position in range(60):
            self.f.plan = copy.deepcopy(original)
            capture = self.f.plan['captures'][position * 2]['capture']
            if capture['package'] == 'R2':
                capture['ring_distance']['calibration_evidence_id'] = 'wrong-handoff'
            else:
                capture['geometry']['capacity'] *= 2
            with self.subTest(cell=capture['cell_ordinal']), self.assertRaises(current.Error):
                current._reuse(self.f.plan, self.f.original_plan, self.f.result, self.f.proof['handoff'])

    def test_structurally_valid_paired_geometry_drift_reaches_reuse_gate(self):
        for item in self.f.plan['captures']:
            capture = item['capture']
            if (capture['package'], capture['placement'], capture['working_set_class']) == ('R0', 'NEAR', 'L2_RESIDENT'):
                capture['geometry']['capacity'] *= 2
        # Both states and repetitions agree: ordinary plan validation passes.
        current.daycap.validate_plan(self.f.plan)
        self.f.proof['plan'] = save(self.f.root / 'plan.json', self.f.plan)
        self.reject(lambda: None, 'all service settings retain qualified geometry')

    def test_structurally_valid_r2_wrong_distance_and_evidence_reach_reuse_gate(self):
        original = copy.deepcopy(self.f.plan)
        for field, value in (('cache_lines', 3), ('calibration_evidence_id', 'wrong-handoff')):
            self.f.plan = copy.deepcopy(original)
            for item in self.f.plan['captures']:
                if item['capture']['package'] == 'R2':
                    item['capture']['ring_distance'][field] = value
            current.daycap.validate_plan(self.f.plan)
            self.f.proof['plan'] = save(self.f.root / 'plan.json', self.f.plan)
            with self.subTest(field=field), self.assertRaisesRegex(current.Error, 'exact retained R2 distance/evidence'):
                self.f.consume()

    def test_symlink_or_changed_compatibility_binding_is_rejected(self):
        bound = save(self.f.root / 'compatibility.json', self.f.proof)
        link = self.f.root / 'symlink.json'
        link.symlink_to(bound['path'])
        for changed in (dict(bound, path=str(link)), dict(bound, sha256='0' * 64)):
            with self.subTest(binding=changed), patch.object(current.original, 'consume', return_value=self.f.result):
                with self.assertRaises(current.Error):
                    current.consume(self.f.document, validation=self.f.validation, plan=self.f.plan,
                        selected_duration_ns=1_000_000_000, original_validation=self.f.original_validation,
                        original_plan=self.f.original_plan, compatibility=changed,
                        original_boot_id=self.f.boot, boot_id=self.f.boot)

    def test_boot_mismatch_rejected_without_stand_access(self):
        with patch.object(current.original, 'consume', return_value=self.f.result):
            with self.assertRaisesRegex(current.Error, 'same verified boot'):
                current.consume(self.f.document, validation=self.f.validation, plan=self.f.plan,
                    selected_duration_ns=1_000_000_000, original_validation=self.f.original_validation,
                    original_plan=self.f.original_plan, compatibility=save(self.f.root / 'compat.json', self.f.proof),
                    original_boot_id=self.f.boot, boot_id='00000000-0000-0000-0000-000000000000')


class OriginalParityTests(unittest.TestCase):
    def test_real_original_receives_actual_old_qualification_and_plan_before_compatibility(self):
        document, validation, plan = retained_fixture()
        expected = current.original.consume(document, validation=validation, plan=plan,
                                             selected_duration_ns=1_000_000_000)
        self.assertEqual(len(expected['run_sources']), 708)
        self.assertEqual(expected['derived_result']['measurement_zero_loss_gate'], 'FAIL')
        with patch.object(current.original, 'consume', wraps=current.original.consume) as delegate:
            with self.assertRaises(current.Error):
                current.consume(document, validation=object(), plan=object(), selected_duration_ns=1_000_000_000,
                    original_validation=validation, original_plan=plan, compatibility={},
                    original_boot_id='unused', boot_id='unused')
            delegate.assert_called_once_with(document, validation=validation, plan=plan,
                                             selected_duration_ns=1_000_000_000)
            self.assertIs(delegate.call_args.kwargs['plan'], plan)
            self.assertIs(delegate.call_args.kwargs['validation'], validation)

    def test_original_negative_gates_still_fail_before_new_context_is_examined(self):
        document, validation, plan = retained_fixture()
        for mutate in (lambda: document.update(execution_authority=True),
                       lambda: plan.update(source_revision=SOURCE),
                       lambda: document['composition'].update(sha256='0' * 64)):
            document, validation, plan = retained_fixture()
            mutate()
            with self.assertRaises(current.Error):
                current.consume(document, validation=object(), plan=object(), selected_duration_ns=1_000_000_000,
                    original_validation=validation, original_plan=plan, compatibility={},
                    original_boot_id='unused', boot_id='unused')


if __name__ == '__main__':
    unittest.main()
