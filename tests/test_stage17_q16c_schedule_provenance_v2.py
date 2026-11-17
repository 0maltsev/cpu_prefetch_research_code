"""Software-only exact-generator integration; no stand observations."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import generate_schedule as gen
import stage17_q16c_schedule_provenance_v2 as current


def binding(identity, raw):
    return dict(artifact_id=identity, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


class DescriptiveSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='q16c-descriptive-software-')
        cls.basis = (current.ROOT / 'docs/evidence/stage17/Q16B-HANDOFF-20261117-01/descriptive-load-basis.json').read_bytes()
        # One real accepted-generator second at the approved lowest load. Its
        # values are test software output, never empirical research evidence.
        cls.spec = gen.ScheduleSpec('synthetic-q16c-source', 'CALIBRATION',
            'synthetic-q16c-source-namespace', 'synthetic-q16c-parent', 'synthetic-q16c-seed',
            'synthetic-q16c-derivation', bytes(range(32)), 0, 10**12,
            1670571, 4 * 10**12, 'synthetic-original', 'synthetic-original.bin')
        cls.generated = gen.generate_schedule(cls.spec)
        cls.path = Path(cls.temp.name) / 'source.bin'
        cls.path.write_bytes(cls.generated.artifact_bytes)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def arguments(self):
        s, g = self.spec, self.generated
        source = dict(schedule_id=s.schedule_id, seed_id=s.seed_id, namespace_id=s.namespace_id,
            seed_hex=s.master_seed.hex(), source_origin_ticks=0, source_horizon_ticks=10**12,
            offered_count=len(g.deadlines), storage_format='SEALED_U64BE_ORIGINAL-v1',
            source_artifact=dict(artifact_id=s.artifact_id, sha256=g.artifact_sha256))
        return dict(schedule=source, phase='measurement', duration_ns=10**9, scale_ordinal=0,
            load_level='L025', load_basis_utf8_bytes=self.basis, artifact_path=self.path,
            artifact_binding=binding(s.artifact_id, g.artifact_bytes),
            envelope_utf8_bytes=g.envelope_bytes, envelope_binding=binding('synthetic-envelope', g.envelope_bytes),
            derivation_utf8_bytes=g.derivation_record_bytes,
            derivation_binding=binding('synthetic-derivation', g.derivation_record_bytes),
            expected_parent_namespace_id=s.parent_namespace_id)

    def test_accepted_original_bytes_and_exact_descriptive_rate(self):
        r = current.verify_schedule_source(**self.arguments())
        self.assertTrue(r['accepted_generation_verified'])
        self.assertEqual(r['offered_count'], len(self.generated.deadlines))
        self.assertEqual(r['nominal_offered_rate'], dict(numerator_events=1670571, denominator_ticks=4 * 10**12))
        self.assertEqual(r['descriptive_load_basis_sha256'], current.BASIS_SHA256)
        self.assertEqual(r['family_method_id'], 'MATRIX-FULL-DESCRIPTIVE-SCREEN-v1')
        self.assertIsNone(r['confidence_claim'])
        self.assertFalse(r['execution_authority']); self.assertFalse(r['phase18_authority'])
        self.assertNotIn('calibration_record_sha256', r)

    def test_forged_basis_other_scale_horizon_and_inline_placeholder_rejected(self):
        for key, value in [('load_basis_utf8_bytes', self.basis.replace(b'1670571', b'1670572')),
                           ('scale_ordinal', 1), ('duration_ns', 10**9 + 1),
                           ('expected_parent_namespace_id', 'unregistered-parent')]:
            a = self.arguments(); a[key] = value
            with self.subTest(key=key), self.assertRaises(current.ScheduleProvenanceError):
                current.verify_schedule_source(**a)
        a = self.arguments(); a['schedule']['deadline_ticks'] = []
        with self.assertRaises(current.ScheduleProvenanceError): current.verify_schedule_source(**a)

    def test_altered_original_binary_rejected_without_generator_substitution(self):
        p = Path(self.temp.name) / 'corrupt.bin'
        raw = bytearray(self.generated.artifact_bytes); raw[:8] = bytes(8); p.write_bytes(raw)
        a = self.arguments(); a['artifact_path'] = p
        with self.assertRaises(current.ScheduleProvenanceError): current.verify_schedule_source(**a)


if __name__ == '__main__': unittest.main()
