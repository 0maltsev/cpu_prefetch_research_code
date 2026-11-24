"""Software-only D232 provenance checks against original D029 generator bytes."""
import copy
import dataclasses
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from fractions import Fraction
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import generate_schedule as gen
import stage17_formal_calibration_v1 as cal
import stage17_formal_plan_v1 as plans
import stage17_q16c_schedule_provenance_v1 as provenance


def binding(name, raw):
    return dict(artifact_id=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def calibration_fixture(mu=80):
    """Explicit synthetic complete D230 record; not collected capture evidence."""
    sources = [dict(capture_ordinal=i, warmup_run_id=f'W{i}', measurement_run_id=f'M{i}',
        validity='VALID', report_binding=binding(f'REPORT-{i}', b'synthetic'), failure=None,
        summary=dict(full_counts=[0, 0], duration_ticks=10**12, ticks_per_second=10**12,
            completion_count=mu, consumed_including_drain=mu, outside_interval_consumed_count=0,
            throughput=dict(numerator=mu, denominator=1))) for i in range(60 * 59)]
    cells = [dict(cell_ordinal=cell, hardware_state=state, package=package, placement=placement,
        working_set_class=working, planned_runs=59, present_runs=59, valid_runs=59, invalid_runs=0,
        missing_runs=0, status='VALIDATED', blockers=[], mu_cell=dict(numerator=mu, denominator=1))
        for cell, state, package, placement, working, _ in plans.cells('Q16b')]
    record = dict(schema_version=cal.SCHEMA_ID, action_id='Q16b', method_id=cal.METHOD['Q16b'],
        stand_id='SOFTWARE-FIXTURE', source_revision='a' * 40, plan_sha256='b' * 64,
        status='VALIDATED', prospective=dict(repetitions=59, measurement_ns=10**9), ring_geometry=None,
        run_sources=sources, derived_result=dict(measurement_zero_loss_gate='PASS', warmup_zero_loss_gate='PASS',
            cells=sorted(cells, key=lambda c: c['cell_ordinal']), mu_ref=dict(numerator=mu, denominator=1),
            candidate_loads=[dict(numerator=(Fraction(mu) * f).numerator,
                                 denominator=(Fraction(mu) * f).denominator)
                             for f in (Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))]),
        execution_authority=False, phase18_authority=False)
    cal.validate_calibration_record(record)
    return record


class ProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.calibration = calibration_fixture()
        cls.golden_calibration = calibration_fixture(40_000_000_000)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='d232-')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def source(self, *, phase='measurement', scale=0, load='L025', origin=0, golden=False, namespace=None):
        rate = Fraction(40_000_000_000 if golden else 80) * provenance.SCALES[scale] * provenance.LOADS[load] / 10**12
        duration_ns = 5_000_000_000 if phase == 'warmup' else (10 if golden else 1_000_000_000)
        spec = gen.ScheduleSpec('stage7-golden', 'WARMUP' if phase == 'warmup' else 'CALIBRATION',
            namespace or 'stage7-schedule-test', 'stage-a-common', 'stage7-test-seed', 'stage7-test-derivation',
            bytes(range(32)), origin, duration_ns * 1000, rate.numerator, rate.denominator,
            'stage7-golden-artifact', 'stage7-golden.bin')
        generated = gen.generate_schedule(spec)
        path = self.root / 'schedule.bin'
        path.write_bytes(generated.artifact_bytes)
        native = dict(schedule_id=spec.schedule_id, seed_id=spec.seed_id, namespace_id=spec.namespace_id,
            seed_hex=spec.master_seed.hex(), source_origin_ticks=origin,
            source_horizon_ticks=origin + spec.horizon_ticks, offered_count=len(generated.deadlines),
            deadline_ticks=list(generated.deadlines),
            source_artifact=dict(artifact_id=spec.artifact_id, sha256=generated.artifact_sha256))
        args = dict(schedule=native, phase=phase, duration_ns=duration_ns, scale_ordinal=scale, load_level=load,
            calibration_record=self.golden_calibration if golden else self.calibration,
            artifact_path=path, artifact_binding=binding(spec.artifact_id, generated.artifact_bytes),
            envelope_utf8_bytes=generated.envelope_bytes, envelope_binding=binding('ENVELOPE', generated.envelope_bytes),
            derivation_utf8_bytes=generated.derivation_record_bytes,
            derivation_binding=binding('DERIVATION', generated.derivation_record_bytes),
            expected_parent_namespace_id=spec.parent_namespace_id)
        return args, spec, generated

    def update_document(self, args, kind, mutate, self_hash=True):
        field = kind + '_utf8_bytes'
        doc = json.loads(args[field])
        mutate(doc)
        if self_hash:
            key = 'schedule_sha256' if kind == 'envelope' else 'record_sha256'
            doc[key] = '0' * 64
            doc[key] = hashlib.sha256(gen.canonicalize(doc).encode()).hexdigest()
        raw = gen.canonicalize(doc).encode() + b'\n'
        args[field] = raw
        args[kind + '_binding'] = binding(kind.upper(), raw)

    def test_original_generator_goldens_and_native_coordinate_conversion(self):
        args, _, generated = self.source(golden=True)
        self.assertEqual(len(generated.deadlines), 104)
        self.assertEqual(generated.artifact_sha256, '18f1da603f3d4383bb08410ffb0e41a8c4df336871765e633b4f116f1b22e81c')
        self.assertEqual(generated.decoded_deadlines_sha256, 'a07a349e5e95ff170036ffb21361d4d85dc9073177de7687c263ff254517a441')
        result = provenance.verify_schedule_source(**args)
        self.assertEqual(result['nominal_offered_rate'], dict(numerator_events=1, denominator_ticks=100))
        self.assertFalse(result['execution_authority']); self.assertFalse(result['phase18_authority'])
        args, _, _ = self.source(origin=123456789)
        result = provenance.verify_schedule_source(**args)
        self.assertEqual(result['source_horizon_ticks'], 123456789 + 10**12)
        self.assertEqual(result['duration_ticks'], 10**12)

    def test_all_accepted_scale_and_load_rates_exact(self):
        for scale, factor in enumerate((Fraction(1), Fraction(9, 10), Fraction(4, 5), Fraction(7, 10), Fraction(3, 5))):
            for load, multiplier in (('L025', Fraction(1, 4)), ('L050', Fraction(1, 2)), ('L075', Fraction(3, 4))):
                with self.subTest(scale=scale, load=load):
                    args, _, _ = self.source(scale=scale, load=load)
                    result = provenance.verify_schedule_source(**args)
                    expected = 80 * factor * multiplier / 10**12
                    self.assertEqual(result['nominal_offered_rate'], dict(
                        numerator_events=expected.numerator, denominator_ticks=expected.denominator))

    def test_five_second_warmup_same_master_seed_disjoint_namespace(self):
        warmup, _, _ = self.source(phase='warmup', namespace='warmup-stream')
        self.assertTrue(provenance.verify_schedule_source(**warmup)['accepted_generation_verified'])
        measurement, _, _ = self.source(namespace='measurement-stream')
        self.assertEqual(warmup['schedule']['seed_hex'], measurement['schedule']['seed_hex'])
        self.assertTrue(provenance.verify_schedule_source(**measurement)['accepted_generation_verified'])

    def test_missing_invalid_or_zero_calibration_cannot_supply_positive_rate(self):
        for mutate in (lambda r: r.update(status='UNRESOLVED'),
                       lambda r: r['derived_result']['mu_ref'].update(numerator=81),
                       lambda r: r['run_sources'].pop(),
                       lambda r: r.update(execution_authority=True)):
            args, _, _ = self.source(); args['calibration_record'] = copy.deepcopy(self.calibration)
            mutate(args['calibration_record'])
            with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)
        args, _, _ = self.source(); args['calibration_record'] = calibration_fixture(0)
        with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)

    def test_binary_native_binding_and_finite_coordinates_reject_mutants(self):
        mutations = [lambda a: a['schedule']['deadline_ticks'].__setitem__(0, True),
            lambda a: a['schedule']['deadline_ticks'].__setitem__(0, a['schedule']['deadline_ticks'][0] + 1),
            lambda a: a['schedule'].update(source_horizon_ticks=10**12 + 1),
            lambda a: a['schedule'].update(source_origin_ticks=(1 << 64) - 1),
            lambda a: a['schedule'].update(offered_count=True),
            lambda a: a['schedule'].update(seed_hex='0' * 64),
            lambda a: a['schedule'].update(schedule_id='stage7-golden\n'),
            lambda a: a['schedule']['source_artifact'].update(sha256='0' * 64),
            lambda a: a.update(scale_ordinal=True), lambda a: a.update(scale_ordinal=5),
            lambda a: a.update(load_level='L100'), lambda a: a.update(phase='pilot'),
            lambda a: a.update(expected_parent_namespace_id='wrong-parent'),
            lambda a: a.update(duration_ns=0)]
        for mutate in mutations:
            args, _, _ = self.source(); mutate(args)
            with self.subTest(mutation=mutate), self.assertRaises(provenance.ScheduleProvenanceError):
                provenance.verify_schedule_source(**args)
        for raw in (b'', b'x', b'\0' * 8):
            args, _, _ = self.source(); args['artifact_path'].write_bytes(raw)
            with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)

    def test_metadata_original_hash_duplicates_floats_and_bound_size(self):
        for kind in ('envelope', 'derivation'):
            args, _, _ = self.source(); args[kind + '_binding']['sha256'] = '0' * 64
            with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)
            for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.5}', b'\xff',
                        b' ' * (provenance.MAX_METADATA_BYTES + 1)):
                args, _, _ = self.source(); args[kind + '_utf8_bytes'] = raw
                args[kind + '_binding'] = binding(kind, raw)
                with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)
        args, _, _ = self.source()
        self.update_document(args, 'envelope', lambda d: d.update(schedule_id='different'), self_hash=False)
        with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)

    def test_rehashed_envelope_rate_suite_role_and_derivation_mutants(self):
        cases = [('envelope', lambda d: d.update(schedule_kind='CONFIRMATORY')),
            ('envelope', lambda d: d.update(arrival_family='CONTINUOUS_READY')),
            ('envelope', lambda d: d.update(time_unit='ns')),
            ('envelope', lambda d: d.update(horizon_ticks=d['horizon_ticks'] + 1)),
            ('envelope', lambda d: d['nominal_offered_rate'].update(numerator_events=2)),
            ('envelope', lambda d: d['rng'].update(version='2')),
            ('envelope', lambda d: d['rng'].update(parent_namespace_id='other')),
            ('envelope', lambda d: d.update(decoded_deadlines_sha256='0' * 64)),
            ('envelope', lambda d: d['deadline_storage'].update(artifact_sha256='0' * 64)),
            ('envelope', lambda d: d['inclusion_boundary'].update(start_inclusive=1)),
            ('derivation', lambda d: d.update(derived_key_u32be_hex='0' * 16)),
            ('derivation', lambda d: d.update(namespace_id='other')),
            ('derivation', lambda d: d.update(seed_id='other')),
            ('derivation', lambda d: d.update(parent_namespace_id='other')),
            ('derivation', lambda d: d.update(python_version='3.13.1')),
            ('derivation', lambda d: d.update(purpose='arena'))]
        for kind, mutate in cases:
            args, _, _ = self.source(); self.update_document(args, kind, mutate)
            with self.subTest(kind=kind, mutate=mutate), self.assertRaises(provenance.ScheduleProvenanceError):
                provenance.verify_schedule_source(**args)

    def test_rehashed_forged_deadlines_fail_accepted_regeneration(self):
        args, spec, generated = self.source()
        rows = list(generated.deadlines); rows[0] += 1
        raw = b''.join(struct.pack('>Q', n) for n in rows)
        args['artifact_path'].write_bytes(raw); args['artifact_binding'] = binding(spec.artifact_id, raw)
        args['schedule']['deadline_ticks'] = rows
        args['schedule']['source_artifact']['sha256'] = args['artifact_binding']['sha256']
        def mutate(doc):
            doc['deadline_storage']['artifact_sha256'] = args['artifact_binding']['sha256']
            doc['decoded_deadlines_sha256'] = gen._decoded_hash(spec, tuple(rows))
        self.update_document(args, 'envelope', mutate)
        with self.assertRaisesRegex(provenance.ScheduleProvenanceError, 'generated deadline'):
            provenance.verify_schedule_source(**args)

    def test_rehashed_truncation_cannot_hide_first_excluded_draw(self):
        args, spec, generated = self.source()
        rows = generated.deadlines[:-1]; raw = generated.artifact_bytes[:-8]
        args['artifact_path'].write_bytes(raw); args['artifact_binding'] = binding(spec.artifact_id, raw)
        args['schedule'].update(deadline_ticks=list(rows), offered_count=len(rows))
        args['schedule']['source_artifact']['sha256'] = args['artifact_binding']['sha256']
        def mutate(doc):
            doc['offered_count'] = len(rows)
            doc['deadline_storage'].update(row_count=len(rows), byte_count=len(raw), artifact_sha256=args['artifact_binding']['sha256'])
            doc['decoded_deadlines_sha256'] = gen._decoded_hash(spec, rows)
        self.update_document(args, 'envelope', mutate)
        with self.assertRaisesRegex(provenance.ScheduleProvenanceError, 'omits generated'):
            provenance.verify_schedule_source(**args)

    def test_bounded_reads_no_whole_generation_and_file_identity(self):
        args, _, _ = self.source(golden=True)
        fdopen = provenance.os.fdopen
        reads = []
        class Reader:
            def __init__(self, *a, **kw): self.file = fdopen(*a, **kw)
            def __enter__(self): return self
            def __exit__(self, *a): self.file.close()
            def fileno(self): return self.file.fileno()
            def read(self, n=-1):
                selftest.assertIn(n, (1, 8)); reads.append(n)
                return self.file.read(n)
        selftest = self
        with mock.patch.object(provenance.os, 'fdopen', Reader), \
             mock.patch.object(gen, 'generate_schedule', side_effect=AssertionError('whole-vector generation forbidden')):
            provenance.verify_schedule_source(**args)
        self.assertEqual(reads.count(8), 104)
        args, _, _ = self.source()
        original_advance = gen._advance_cumulative
        changed = False
        def replace_file(*a, **kw):
            nonlocal changed
            if not changed:
                changed = True
                path = args['artifact_path']; same_bytes = path.read_bytes()
                path.unlink(); path.write_bytes(same_bytes)
            return original_advance(*a, **kw)
        with mock.patch.object(gen, '_advance_cumulative', replace_file), \
             self.assertRaisesRegex(provenance.ScheduleProvenanceError, 'identity changed'):
            provenance.verify_schedule_source(**args)
        args, _, _ = self.source(); link = self.root / 'link.bin'; link.symlink_to(args['artifact_path'])
        args['artifact_path'] = link
        with self.assertRaises(provenance.ScheduleProvenanceError): provenance.verify_schedule_source(**args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
