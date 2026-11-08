"""Continuation collection routing cannot grant a complete-family calibration."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_formal_archive_v1 as archive
import stage17_formal_calibration_v2 as calibration
import stage17_formal_plan_v2 as plans
import stage17_output_registry_v12 as registry
import stage17_phase_controller_v26 as controller
import stage17_q16a_continuation_admission_v1 as admission
import stage17_operational_semantics_v17 as semantics


class ContinuationRouting(unittest.TestCase):
    def test_only_q16a_uses_the_continuation_archive_route(self):
        plan = dict(schema_version=plans.CONTINUATION_VERSION)
        for action in ('Q16a', 'Q16b', 'Q16c', 'Q15r'):
            request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
                           action_id=action, action_inputs=dict(plan=plan))
            self.assertEqual(controller.is_archived(request), action == 'Q16a')
            self.assertEqual(registry.is_archived(request), action == 'Q16a')
            request['schema_version'] = 'cpu-prefetch-stage17-fixed-action-request/5'
            self.assertFalse(controller.is_archived(request))
            self.assertFalse(registry.is_archived(request))

    def test_original_continuation_bytes_have_one_native_identity(self):
        plan = dict(schema_version=plans.CONTINUATION_VERSION, scientific_claim=False)
        self.assertEqual(calibration.plan_bytes(plan), archive.canonical(plan))
        self.assertFalse(calibration.plan_bytes(plan).endswith(b'\n'))

    def test_suffix_cannot_be_evaluated_as_a_complete_calibration(self):
        plan = dict(schema_version=plans.CONTINUATION_VERSION)
        with self.assertRaisesRegex(calibration.CalibrationError, 'original-prefix and suffix'):
            calibration.evaluate('Q16a', plan, [])

    def test_registry_pins_closed_continuation_schema(self):
        pinned = registry.pin_registry(ROOT)
        schema = pinned.schemas[plans.CONTINUATION_SCHEMA]
        self.assertEqual(schema.document['properties']['schema_version']['const'],
                         plans.CONTINUATION_VERSION)

    def test_controller_rejects_absent_proofs_before_legacy_admission(self):
        plan = dict(schema_version=plans.CONTINUATION_VERSION)
        request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6',
                       action_id='Q16a', action_inputs=dict(plan=plan))
        validation = SimpleNamespace(resolutions={
            'S17-EXT-006': SimpleNamespace(semantic_context={})})
        with patch.object(controller.previous, 'validate_action_inputs') as legacy:
            with self.assertRaisesRegex(controller.ControllerError, 'continuation evidence rejected'):
                controller.validate_action_inputs(request, validation)
            legacy.assert_not_called()

    def test_controller_uses_authenticated_context_and_propagates_proof_failure(self):
        plan = dict(schema_version=plans.CONTINUATION_VERSION)
        context = dict(source_revision='a'*40)
        validation = SimpleNamespace(resolutions={
            'S17-EXT-006': SimpleNamespace(semantic_context=context)})
        request = dict(action_inputs=dict(plan=plan))
        with patch.object(admission, 'validate', side_effect=admission.AdmissionError('tampered prefix')) as gate:
            with self.assertRaisesRegex(controller.ControllerError, 'tampered prefix'):
                controller._validate_inputs(request, validation)
            gate.assert_called_once_with(plan, context)

    def test_signed_collection_forwards_original_release_transport(self):
        artifacts = [SimpleNamespace(role='Q16A_'+role, path=Path('/fixture/'+role))
                     for role in ('AUTHORIZATION', 'SIGNATURE')]
        archive_path, sidecar = Path('/fixture/release.tar.gz'), Path('/fixture/release.tar.gz.sha256')
        with patch.object(semantics, '_dependencies', return_value=(None, controller)), \
                patch.object(controller, 'prepare_retention', side_effect=ValueError('stop before collection')) as prepare:
            with self.assertRaisesRegex(semantics.OperationalSemanticError, 'stop before collection'):
                semantics.verify_signed_formal_family(repository_root=ROOT, evidence_root='/fixture',
                    historical_journal='/fixture/journal.json', journal_directory='/fixture/journal',
                    artifacts=artifacts, action_id='Q16a', admitted_resolutions={}, allow_synthetic=True,
                    pinned_repository_bytes={}, pilot_archive=archive_path, pilot_sidecar=sidecar)
            self.assertEqual(prepare.call_args.kwargs['pilot_archive'], archive_path)
            self.assertEqual(prepare.call_args.kwargs['pilot_sidecar'], sidecar)


if __name__ == '__main__':
    unittest.main()
