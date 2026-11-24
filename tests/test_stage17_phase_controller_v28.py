"""Private archive substitution with the real v27 two-source input gates."""
import importlib.util
import hashlib
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
# The archive implementation is owned by the integration coordinator. Until it
# is present, substitute only that external boundary, never controller bodies.
OVERLAY_PENDING = importlib.util.find_spec('stage17_archive_overlay_v1') is None
if OVERLAY_PENDING:
    overlay = types.ModuleType('stage17_archive_overlay_v1')
    def unavailable(*args, **kwargs):
        raise AssertionError('real overlay integration is pending')
    overlay.qualified_profile = unavailable
    sys.modules[overlay.__name__] = overlay
import stage17_phase_controller_v28 as controller
import test_stage17_q16a_handoff_v1 as prior_tests


class OverlayControllerTests(prior_tests.ControllerTests):
    def validate(self):
        return controller._validate_inputs(self.request, self.base.validation)

    def test_new_signed_profile_uses_overlay_without_old_profile_fallback(self):
        self.plan['storage']['implementation_profile_sha256'] = 'e' * 64
        # Refresh the namespace's signed plan binding after the profile change.
        self.base.namespace['plan_sha256'] = hashlib.sha256(
            controller.previous.previous.archive.canonical(self.plan)).hexdigest()
        self.request['action_inputs']['prerequisite_bindings']['namespace_registry'] = self.base.write(
            'namespace-overlay', self.base.namespace)
        sentinel = object()
        original = controller.previous.previous
        before = dict(original.validate_action_inputs.__globals__)
        with patch.object(controller.overlay, 'qualified_profile', return_value=sentinel) as profile, \
             patch.object(original, 'qualified_archive_profile', side_effect=AssertionError('old profile fallback')):
            self.assertEqual(len(controller.validate_action_inputs(self.request, self.base.validation).captures), 3540)
            self.assertIs(controller.qualified_archive_profile(self.request, self.base.validation, deadline_ns=123), sentinel)
        self.assertEqual(before, original.validate_action_inputs.__globals__)
        self.assertEqual(profile.call_count, 2)
        self.assertEqual(profile.call_args.kwargs, {'deadline_ns': 123})

    def test_overlay_rejection_never_falls_back_to_old_profile(self):
        original = controller.previous.previous
        with patch.object(controller.overlay, 'qualified_profile', side_effect=controller.ControllerError('overlay rejected')), \
             patch.object(original, 'qualified_archive_profile', side_effect=AssertionError('fallback')):
            with self.assertRaisesRegex(controller.ControllerError, 'overlay rejected'):
                controller.validate_action_inputs(self.request, self.base.validation)

    def test_preparation_and_execution_clone_only_the_required_bindings(self):
        # Inspect the actual clone boundary without bypassing it with a fake
        # controller. The preserved v26 bodies and their globals stay intact.
        v26 = controller.previous.previous
        observations = []
        original_clone = v26.previous._with_globals
        def clone(function, replacements, arguments):
            observations.append((function, replacements, arguments))
            return 'prepared'
        snapshots = [dict(f.__globals__) for f in (v26._prepare_action, v26.execute_once)]
        with patch.object(v26.previous, '_with_globals', side_effect=clone):
            self.assertEqual(controller.prepare_action(token=1), 'prepared')
            self.assertEqual(controller.prepare_retention(token=2), 'prepared')
        for i, retention in enumerate((False, True)):
            function, replacements, arguments = observations[i]
            self.assertIs(function, v26._prepare_action)
            self.assertEqual(replacements, {'_validate_inputs': controller._validate_inputs,
                'qualified_archive_profile': controller.qualified_archive_profile})
            self.assertEqual(arguments, {'for_retention': retention, 'token': i + 1})
        self.assertEqual(snapshots, [dict(f.__globals__) for f in (v26._prepare_action, v26.execute_once)])
        self.assertIs(v26.previous._with_globals, original_clone)

    def test_public_qualification_aliases_and_handoff_remain_original(self):
        for name in ('ControllerError', 'contract', 'activate', 'support', 'runtime_from_context',
                     'deadline_policy', 'is_archived', '_runtime_from_context', '_validate_action_inputs'):
            self.assertIs(getattr(controller, name), getattr(controller.previous, name))
        self.assertIs(controller._validate_inputs, controller.previous._validate_inputs)


class DispatchTests(unittest.TestCase):
    def test_prepared_native_identity_and_all_authority_forwarded_to_private_executor(self):
        prepared = types.SimpleNamespace(root=Path('/tmp/qualified-root'), authorization={'id': 'a'},
            authorization_bytes=b'a', request={'evidence_root_binding': {'absolute_path': '/tmp/new-family'}},
            request_bytes=b'r', runtime={'sha256': 'original-native'}, worker_path=Path('/tmp/worker'),
            release={'id': 'original-release'}, archive_runtime_profile=object())
        calls = []
        executor = types.SimpleNamespace(execute_fixed_action=lambda **kw: calls.append(kw) or 'executed')
        import stage17_fixed_action_executor_v11 as original
        original_globals = dict(original.execute_fixed_action.__globals__)
        with patch.object(controller, 'prepare_action', return_value=prepared) as admission, \
             patch.object(controller, 'is_archived', return_value=True), \
             patch.object(controller.metadata, 'make_executor', return_value=executor) as factory:
            self.assertEqual(controller.execute_once(token=1), 'executed')
        admission.assert_called_once_with(token=1)
        factory.assert_called_once_with(original)
        self.assertEqual(calls[0]['worker_binding'], prepared.runtime)
        self.assertEqual(calls[0]['worker_path'], prepared.worker_path)
        self.assertEqual(calls[0]['request_bytes'], b'r')
        self.assertEqual(calls[0]['authorization_bytes'], b'a')
        self.assertIs(calls[0]['archive_runtime_profile'], prepared.archive_runtime_profile)
        self.assertFalse(calls[0]['synthetic_test_only'])
        self.assertEqual(original_globals, original.execute_fixed_action.__globals__)

    def test_failed_admission_never_constructs_or_executes_a_cold_adapter(self):
        with patch.object(controller, 'prepare_action', side_effect=ValueError('authority rejected')), \
             patch.object(controller.metadata, 'make_executor') as factory:
            with self.assertRaisesRegex(ValueError, 'authority rejected'):
                controller.execute_once()
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
