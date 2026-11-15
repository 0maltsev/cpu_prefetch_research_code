"""D253/D254 software admission fixtures; no stand or execution authority."""
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
import shutil
import sys
import time
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'tools'), str(Path(__file__).resolve().parent)]
import stage17_archive_daycap_overlay_v1 as current
import stage17_archive_inventory_bundle_v1 as inventory_bundle
import stage17_archive_bundle_profile_v1 as bundle
import stage17_formal_service_daycap_v1 as daycap
import test_stage17_archive_overlay_v1 as legacy
from test_stage17_formal_plan_v2 import archived_fixture
from test_stage17_formal_service_daycap_v1 import select_repetitions

TOOLS = Path(__file__).resolve().parents[1] / 'tools'


class DaycapOverlayTests(unittest.TestCase):
    encoder = library = inventory_library = None

    @classmethod
    def setUpClass(cls):
        if any(value is None for value in (cls.encoder, cls.library, cls.inventory_library)):
            raise unittest.SkipTest('explicit --encoder, --library and --inventory-library required')
        cls.plan = select_repetitions(archived_fixture('Q16b'), 2)

    def setUp(self):
        fixture = legacy.OverlayTests(methodName='runTest')
        fixture.encoder, fixture.library = self.encoder, self.library
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        self.root, self.baseline, self.packet = fixture.root, fixture.baseline, fixture.packet
        self.original = fixture.original
        self.intermediate = fixture.destination
        self.destination = self.root / 'd253-candidate'
        for name in inventory_bundle.MODULES:
            shutil.copyfile(TOOLS / (name + '.py'), self.packet / (name + '.py'))
        inventory_bundle.build_candidate(baseline_bundle_root=self.intermediate, runtime_root=Path('/'),
            destination=self.destination, native_library=self.inventory_library, source_root=self.packet)
        for name in (current.IMAGE_MODULE, current.INVENTORY_IMAGE_MODULE):
            shutil.copyfile(self.destination / 'tools' / (name + '.py'), self.packet / (name + '.py'))
        self.document = dict(schema_version=current.SCHEMA, source_revision='a' * 40,
            qualified_source_revision='c' * 40,
            qualified_worker_sha256=hashlib.sha256(self.encoder.read_bytes()).hexdigest(),
            baseline_bundle_root=str(self.baseline), runtime_root='/', overlay_bundle_root=str(self.destination),
            baseline_profile=current.binding(self.baseline / current.PROFILE_MEMBER),
            overlay_profile=current.binding(self.destination / current.PROFILE_MEMBER),
            native_image=self.image_binding(self.library.read_bytes()),
            inventory_native_image=self.image_binding(self.inventory_library.read_bytes()),
            sources={name: current.binding(self.packet / (name + '.py')) for name in current.EXTRA_MODULES},
            execution_authority=False, measurement_changes=False)
        saved = current._CONFIG
        current._CONFIG = None
        self.addCleanup(setattr, current, '_CONFIG', saved)
        self.configure()
        self.validation = fixture.validation
        resolution = self.validation.resolutions['S17-EXT-006']
        resolution.resolution_id, resolution.sha256 = 'software-ext006', 'e' * 64
        context = self.validation.resolutions['S17-EXT-006'].semantic_context
        context.update(source_revision=self.document['qualified_source_revision'],
            release_artifact_sha256=self.document['qualified_worker_sha256'],
            release_artifact_size_bytes=self.encoder.stat().st_size, release_artifact_path=str(self.encoder),
            bundle_profile='STAGE17-PILOT-CANDIDATE-BUNDLE-v26',
            supported_actions=['Q15-R', 'Q15-W', 'Q16a', 'Q16b', 'Q16c',
                               'STAGE17-BLINDED-PILOT', 'Q16A-DURATION-DISCOVERY'],
            release_artifact_role='STAGE17_FIXED_ACTION_WORKER', runtime_profile='STAGE17-FIXED-ACTION-WORKER-v4')
        self.request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6', action_id='Q16b',
                            action_inputs=dict(plan=copy.deepcopy(self.plan)))
        self.request['action_inputs']['plan']['source_revision'] = self.document['qualified_source_revision']
        self.request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = self.document['overlay_profile']['sha256']

    @staticmethod
    def image_binding(raw):
        return dict(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def configure(self):
        return current.configure_verified_descriptor(current.canonical(self.document), self.packet)

    def admit(self):
        return current.qualified_profile(self.request, self.validation,
                                        deadline_ns=time.monotonic_ns() + 60_000_000_000)

    def refreeze_candidate(self):
        profile = bundle.build_profile(bundle_root=self.destination, runtime_root=Path('/'), window_log=22)
        path = self.destination / current.PROFILE_MEMBER
        path.write_bytes(current.canonical(profile))
        self.document['overlay_profile'] = current.binding(path)
        current._CONFIG = None
        self.configure()
        self.request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = self.document['overlay_profile']['sha256']

    def test_real_v26_qualification_root_relocation_and_exact_closure(self):
        before = copy.deepcopy(self.request)
        baseline_bytes = {p.relative_to(self.baseline): p.read_bytes() for p in self.baseline.rglob('*') if p.is_file()}
        with patch.object(current.qualified, 'qualified_archive_profile',
                          wraps=current.qualified.qualified_archive_profile) as authenticate:
            profile = self.admit()
        original_request = authenticate.call_args.args[0]
        expected_request = copy.deepcopy(before)
        expected_request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = self.document['baseline_profile']['sha256']
        self.assertEqual(original_request, expected_request)
        self.assertEqual(self.request, before)
        self.assertEqual(len(profile.source_closure), len(self.original.source_closure) + 7)
        self.assertNotEqual(profile.encoder.path, self.original.encoder.path)
        self.assertEqual(profile.encoder.sha256, self.original.encoder.sha256)
        self.assertEqual(baseline_bytes, {p.relative_to(self.baseline): p.read_bytes() for p in self.baseline.rglob('*') if p.is_file()})
        self.assertFalse(self.document['execution_authority'])

    def test_wrong_worker_source_and_baseline_context_rejected_before_qualification(self):
        context = self.validation.resolutions['S17-EXT-006'].semantic_context
        for field, wrong in (('source_revision', 'd' * 40), ('release_artifact_sha256', 'd' * 64),
                             ('archive_bundle_root', str(self.destination)), ('archive_runtime_root', str(self.root)),
                             ('archive_profile_binding', {**context['archive_profile_binding'], 'sha256': 'd' * 64})):
            with self.subTest(field=field), patch.dict(context, {field: wrong}), \
                    patch.object(current.qualified, 'qualified_archive_profile') as authenticate:
                with self.assertRaisesRegex(ValueError, 'EXT006'):
                    self.admit()
                authenticate.assert_not_called()

    def test_all_explicit_bundle_and_runtime_roots_can_relocate(self):
        relocated = self.root / 'relocated'
        relocated.mkdir()
        runtime_root = relocated / 'runtime'
        python = runtime_root / 'usr/bin/python3.14'
        python.parent.mkdir(parents=True)
        shutil.copyfile(self.original.python.path, python)
        baseline, candidate = relocated / 'qualified-baseline', relocated / 'selected-candidate'
        shutil.move(self.baseline, baseline)
        shutil.move(self.destination, candidate)
        self.document.update(baseline_bundle_root=str(baseline), overlay_bundle_root=str(candidate),
                             runtime_root=str(runtime_root),
                             baseline_profile=current.binding(baseline / current.PROFILE_MEMBER),
                             overlay_profile=current.binding(candidate / current.PROFILE_MEMBER))
        context = self.validation.resolutions['S17-EXT-006'].semantic_context
        context.update(archive_bundle_root=str(baseline), archive_runtime_root=str(runtime_root))
        current._CONFIG = None
        self.configure()
        profile = self.admit()
        self.assertEqual(profile.python.path, python)
        self.assertEqual(profile.encoder.path, candidate / bundle.ENCODER_PATH)
        self.assertEqual(profile.decoder.implementation_profile_sha256, self.document['overlay_profile']['sha256'])

    def test_failed_qualification_propagates_without_loading_candidate_or_fallback(self):
        context = self.validation.resolutions['S17-EXT-006'].semantic_context
        context['runtime_profile'] = 'UNQUALIFIED'
        with patch.object(current.runtime, 'load_runtime_profile', side_effect=AssertionError('bypass')) as load:
            with self.assertRaisesRegex(current.qualified.ControllerError, 'qualified release'):
                self.admit()
        load.assert_not_called()

    def test_baseline_profile_bytes_are_reauthenticated(self):
        path = self.baseline / current.PROFILE_MEMBER
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaisesRegex(current.qualified.ControllerError, 'implementation rejected'):
            self.admit()

    def test_only_d254_q16b_120_and_at_most_24_hours(self):
        cases = [lambda r: r.update(action_id='Q16c'),
                 lambda r: r['action_inputs']['plan'].update(schema_version='cpu-prefetch-stage17-formal-service-plan/2'),
                 lambda r: r['action_inputs']['plan'].update(method_id=daycap.COLLECTOR_METHOD),
                 lambda r: r['action_inputs']['plan'].update(repetitions_per_cell=3),
                 lambda r: r['action_inputs']['plan']['captures'].pop(),
                 lambda r: r['action_inputs']['plan']['budget'].update(watchdog_ns=daycap.DAYCAP_NS + 1),
                 lambda r: r['action_inputs']['plan']['storage'].update(implementation_profile_sha256='0' * 64),
                 lambda r: r['action_inputs']['plan'].update(source_revision='d' * 40)]
        original = self.request
        for mutate in cases:
            self.request = copy.deepcopy(original)
            mutate(self.request)
            with self.subTest(mutate=mutate), patch.object(current.qualified, 'qualified_archive_profile') as authenticate:
                with self.assertRaises(ValueError):
                    self.admit()
                authenticate.assert_not_called()
        self.request = copy.deepcopy(original)
        self.request['action_inputs']['plan']['budget']['watchdog_ns'] = daycap.DAYCAP_NS
        self.admit()

    def test_unconfigured_descriptor_and_expired_deadline_rejected(self):
        with self.assertRaisesRegex(ValueError, 'deadline'):
            current.qualified_profile(self.request, self.validation, deadline_ns=1)
        current._CONFIG = None
        with self.assertRaisesRegex(ValueError, 'not configured'):
            self.admit()

    def test_descriptor_reentry_and_mutation_rejected(self):
        self.configure()
        self.document['source_revision'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.configure()
        current._CONFIG[2]['source_revision'] = 'e' * 40
        with self.assertRaisesRegex(ValueError, 'mutated'):
            self.admit()

    def test_descriptor_authority_fields_bindings_and_packet_paths(self):
        original = copy.deepcopy(self.document)
        cases = [lambda d: d.update(execution_authority=True), lambda d: d.update(measurement_changes=True),
                 lambda d: d.update(qualified_source_revision='unknown'),
                 lambda d: d.update(qualified_worker_sha256='unknown'),
                 lambda d: d['baseline_profile'].update(sha256='0' * 64),
                 lambda d: d['overlay_profile'].update(path=str(self.baseline / current.PROFILE_MEMBER)),
                 lambda d: d['sources'][current.NATIVE_MODULE].update(path=str(TOOLS / (current.NATIVE_MODULE + '.py'))),
                 lambda d: d['sources'].pop(current.INVENTORY_IMAGE_MODULE),
                 lambda d: d.update(native_image=dict(size_bytes=True, sha256='0' * 64)),
                 lambda d: d.update(overlay_bundle_root=str(self.baseline)),
                 lambda d: d.update(runtime_root=str(self.root / '..'))]
        for mutate in cases:
            current._CONFIG = None
            self.document = copy.deepcopy(original)
            mutate(self.document)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                self.configure()
        self.document = original
        current._CONFIG = None
        with self.assertRaises(ValueError):
            current.configure_verified_descriptor(current.canonical(original) + b'\n', self.packet)
        linked = self.root / 'linked-packet'
        linked.symlink_to(self.packet, target_is_directory=True)
        with self.assertRaises(ValueError):
            current.configure_verified_descriptor(current.canonical(original), linked)

    def test_all_seven_packet_sources_rechecked_after_configuration(self):
        for name in current.EXTRA_MODULES:
            path = self.packet / (name + '.py')
            before = path.read_bytes()
            path.write_bytes(before + b'\n# changed packet\n')
            with self.subTest(module=name), self.assertRaisesRegex(ValueError, 'packet source'):
                self.admit()
            path.write_bytes(before)

    def test_rehashed_wrong_custody_hook_and_unchanged_old_module_rejected(self):
        for name in ('stage17_formal_archive_custody_v1', 'stage17_formal_archive_runtime_v1'):
            path = self.destination / 'tools' / (name + '.py')
            before = path.read_bytes()
            path.write_bytes(before + b'\n# unauthorized body delta\n')
            self.refreeze_candidate()
            with self.subTest(module=name), self.assertRaisesRegex(ValueError, 'historical verifier body'):
                self.admit()
            path.write_bytes(before)

    def test_rehashed_extra_source_closure_rejected(self):
        (self.destination / 'tools/stage17_unapproved_extra.py').write_bytes(b'VALUE = 1\n')
        path = self.destination / 'tools/stage17_archive_metadata_fast_v2.py'
        path.write_bytes(path.read_bytes() + b'\nimport stage17_unapproved_extra\n')
        self.refreeze_candidate()
        with self.assertRaisesRegex(ValueError, 'source membership'):
            self.admit()

    def test_rehashed_extra_source_not_matching_packet_rejected(self):
        path = self.destination / 'tools/stage17_archive_metadata_fast_v2.py'
        path.write_bytes(path.read_bytes() + b'\n# wrong adapter\n')
        self.refreeze_candidate()
        with self.assertRaisesRegex(ValueError, 'sealed packet source'):
            self.admit()

    def test_both_native_descriptors_reject_different_elf_binding(self):
        original = copy.deepcopy(self.document)
        for field in ('native_image', 'inventory_native_image'):
            self.document = copy.deepcopy(original)
            self.document[field]['sha256'] = '0' * 64
            current._CONFIG = None
            with self.subTest(image=field), self.assertRaisesRegex(ValueError, 'native image'):
                self.configure()

    def test_inventory_generated_literal_source_never_executes_code(self):
        path = self.destination / 'tools' / (current.INVENTORY_IMAGE_MODULE + '.py')
        sentinel = self.root / 'must-not-exist'
        path.write_bytes(path.read_bytes() + f'\nopen({str(sentinel)!r}, "w").close()\n'.encode())
        packet = self.packet / path.name
        shutil.copyfile(path, packet)
        self.document['sources'][current.INVENTORY_IMAGE_MODULE] = current.binding(packet)
        current._CONFIG = None
        with self.assertRaises(ValueError):
            self.configure()
        self.assertFalse(sentinel.exists())

    def test_encoder_zstd_and_options_rehash_cannot_change_qualified_bytes(self):
        for key in ('encoder', 'python', 'zstd_library', 'options'):
            path = self.destination / current.PROFILE_MEMBER
            original = path.read_bytes()
            document = current.archive.parse_json(original)
            target = None
            if key == 'options':
                document[key]['window_log'] += 1
            else:
                if key == 'python':
                    # Bundle-local identical Python still violates the frozen
                    # runtime namespace; never touch the real interpreter.
                    target = self.destination / 'python-copy'
                    shutil.copyfile(self.original.python.path, target)
                    before = target.read_bytes()
                    document[key].update(location='bundle', path=target.name)
                else:
                    target = self.destination / document[key]['path']
                    before = target.read_bytes()
                    target.write_bytes(before + b'\x00')
                    document[key].update(self.image_binding(target.read_bytes()))
            path.write_bytes(current.canonical(document))
            self.document['overlay_profile'] = current.binding(path)
            current._CONFIG = None
            self.configure()
            self.request['action_inputs']['plan']['storage']['implementation_profile_sha256'] = self.document['overlay_profile']['sha256']
            with self.subTest(image=key), self.assertRaisesRegex(ValueError, 'dependency/options'):
                self.admit()
            if target is not None:
                target.write_bytes(before)
            path.write_bytes(original)

    def test_real_sealed_inverse_inventory_and_both_custody_readbacks(self):
        legacy.OverlayTests.test_real_sealed_native_inverse_both_custody_readbacks(self)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--encoder', type=Path, required=True)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--inventory-library', type=Path, required=True)
    args, remaining = parser.parse_known_args()
    DaycapOverlayTests.encoder = args.encoder.resolve()
    DaycapOverlayTests.library = args.library.resolve()
    DaycapOverlayTests.inventory_library = args.inventory_library.resolve()
    unittest.main(argv=[sys.argv[0], *remaining])
