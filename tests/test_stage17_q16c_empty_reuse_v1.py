"""D282 software-only incident and prospective-input regression checks."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_q16c_empty_reuse_v1 as reuse
import stage17_q16c_restart_plan_v1 as restart
import stage17_q16c_execution_window_v2 as window
from test_stage17_formal_scheduled_descriptive_v1 import plan_fixture


def old_plan():
    plan = plan_fixture()
    plan['source_revision'] = reuse.OLD_SOURCE
    for item in plan['captures']:
        item['monitoring']['environment_sources'] = [dict(path=
            '/sys/fs/cgroup/cpu-prefetch-recovery-v28-qualified-1.service/reserved/cpuset.'+name)
            for name in ('cpus', 'cpus.effective', 'cpus.exclusive', 'partition', 'mems.effective')]
    return plan


class EmptyAttempt(unittest.TestCase):
    def setUp(self):
        root = ROOT/'docs/evidence/stage17/Q16C-D279-NATIVE-STOP-20261118-01'
        self.checkpoint = json.loads((root/'checkpoint.json').read_bytes())
        self.failure = json.loads((root/'native_failure.json').read_bytes())
        self.restoration = dict(verified=True, errors=[])

    def test_actual_empty_checkpoint_and_failure_are_eligible(self):
        reuse.empty(self.checkpoint, self.failure, self.restoration)

    def test_any_observation_or_mapping_stops_reuse(self):
        changes = [lambda c: c.update(native_complete=True),
            lambda c: c.update(artifacts=[{}]), lambda c: c.update(capture_ordinal=1),
            lambda c: c['native_result_after_cleanup'].update(session={}),
            lambda c: c['native_result_after_cleanup'].update(clock_origin=0),
            lambda c: c['native_result_after_cleanup'].update(publication_attempted=True),
            lambda c: c['native_result_after_cleanup']['core_mapping']['requested'].update(bytes=4096),
            lambda c: c['native_result_after_cleanup']['controller_stack'].update(cleanup_attempted=True)]
        for change in changes:
            c = copy.deepcopy(self.checkpoint); change(c)
            with self.subTest(change=change), self.assertRaises(reuse.admission.AdmissionError):
                reuse.empty(c, self.failure, self.restoration)

    def test_unknown_cleanup_quarantine_or_wrong_lineage_stops(self):
        changes = [lambda f: f.update(leader_reaped=False), lambda f: f.update(process_group_gone=False),
            lambda f: f.update(restoration_verified=False), lambda f: f.update(request_sha256='0'*64),
            lambda f: f['quarantine_operation'].update(performed=True),
            lambda f: f['recovery_readback'].pop()]
        for change in changes:
            f = copy.deepcopy(self.failure); change(f)
            with self.subTest(change=change), self.assertRaises(reuse.admission.AdmissionError):
                reuse.empty(self.checkpoint, f, self.restoration)
        with self.assertRaises(reuse.admission.AdmissionError):
            reuse.empty(self.checkpoint, self.failure, dict(verified=False, errors=['failure']))


class ProspectivePlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = old_plan()
        cls.setup = dict(sources=[{} for _ in range(360)])
        cls.new, cls.identities = restart.prepare(cls.old, cls.setup, master_hex='91'*32)

    def test_same_full_matrix_bank_limits_and_new_identities(self):
        reuse.compare_plan(self.new, self.old)
        self.assertEqual(len(self.identities['phase_identities']), 360)
        self.assertEqual(len(self.identities['linked_order_identities']), 72)
        self.assertEqual(len({r['seed_hex'] for r in self.identities['phase_identities']+
            self.identities['linked_order_identities']}), 432)
        self.assertEqual(self.identities['original_source_setup'], self.setup)
        for a, b in zip(self.new['captures'], self.old['captures'], strict=True):
            self.assertEqual(a['capture']['schedules'], b['capture']['schedules'])
            self.assertEqual(a['resources'], b['resources'])
        self.assertFalse(self.identities['execution_authority'])

    def test_no_rate_geometry_sample_storage_or_budget_changes(self):
        changes = [lambda p: p['captures'].pop(), lambda p: p.update(measurement_ns=5),
            lambda p: p['budget'].update(watchdog_ns=1), lambda p: p['storage'].update(archive_quota_bytes=1),
            lambda p: p['captures'][0]['capture']['geometry'].update(capacity=1024),
            lambda p: p['captures'][0]['capture']['schedules'][0].update(offered_count=1),
            lambda p: p['captures'][0]['resources'].update(core_bytes=True)]
        for change in changes:
            p = copy.deepcopy(self.new); change(p)
            with self.subTest(change=change), self.assertRaises(reuse.admission.AdmissionError):
                reuse.compare_plan(p, self.old)

    def test_duplicate_or_historical_seed_and_run_identity_rejected(self):
        p = copy.deepcopy(self.new)
        p['captures'][1]['capture']['warmup']['seed_hex'] = p['captures'][0]['capture']['warmup']['seed_hex']
        with self.assertRaises(reuse.admission.AdmissionError): reuse.compare_plan(p, self.old)
        p = copy.deepcopy(self.new)
        p['captures'][0]['capture']['warmup'] = self.old['captures'][0]['capture']['warmup']
        with self.assertRaises(reuse.admission.AdmissionError): reuse.compare_plan(p, self.old)


class Window(unittest.TestCase):
    def record(self):
        return dict(schema_version=window.SCHEMA, execution_window_id=window.IDENTITY, decision_id='D282',
            source_revision=window.SOURCE, worker_sha256=window.WORKER, boot_id=window.BOOT,
            stand_id='CPU-PREFETCH-V5', started_monotonic_ns=1, global_deadline_ns=1+86400*window.NS,
            started_at_utc='2026-11-18T08:00:00Z', bindings={k:{} for k in window.ROLES},
            qualification_seconds=7200, family_seconds=47820, analysis_seconds=5400,
            restoration_seconds=2400, automatic_retries=0, new_windows_allowed=0,
            execution_authority=False, phase18_authority=False)

    def test_unchanged_complete_ceiling_and_old_deadline_independent(self):
        self.assertEqual(window.TOTAL, 62820)
        r = self.record(); window.validate(r, now=2, qualification=True)
        self.assertEqual(r['global_deadline_ns'], 1+86400*window.NS)

    def test_no_extension_wrong_release_partial_budget_or_late_launch(self):
        for key, value in [('source_revision', reuse.OLD_SOURCE), ('worker_sha256', reuse.OLD_WORKER),
            ('automatic_retries', True), ('family_seconds', 47220), ('global_deadline_ns', 86401*window.NS)]:
            r = self.record(); r[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): window.validate(r, now=2)
        r = self.record()
        with self.assertRaises(ValueError):
            window.validate(r, now=r['global_deadline_ns']-window.TOTAL*window.NS, qualification=True)


class QualifiedSourceReuse(unittest.TestCase):
    """Exercise inspect's real closure discovery and exact source comparisons.

    Only the stand-bound signed-document reader and signature boundary are
    substituted. Bundle files, dependency traversal, plan/incident checks and
    every producer/consumer comparison execute normally. Actual stand evidence
    supplies separate verification of those authentication boundaries.
    """
    @classmethod
    def setUpClass(cls):
        cls.original_plan = old_plan()
        cls.plan, _ = restart.prepare(cls.original_plan, dict(sources=[{} for _ in range(360)]),
            master_hex='37'*32)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.roots = {name:self.root/name for name in ('original','current')}
        self.files = {
            'tools/generate_schedule.py': b'import helper\n',
            'tools/stage17_q16c_schedule_provenance_v2.py': b'import helper\n',
            'tools/helper.py': b'VALUE = "same source"\n',
            'protocol/2.0.0-pre.3/handoff/schemas/schedule.schema.json': b'{}\n',
            'config/schemas/schedule-derivation-v2.schema.json': b'{}\n',
            'config/schemas/stage17-formal-scheduled-native-input-v2.schema.json': b'{}\n',
        }
        for root in self.roots.values():
            for name, raw in self.files.items():
                path = root/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        fixture = ROOT/'docs/evidence/stage17/Q16C-D279-NATIVE-STOP-20261118-01'
        release = dict(source_revision=reuse.OLD_SOURCE, release_artifact_sha256=reuse.OLD_WORKER,
            archive_bundle_root=str(self.roots['original']), inventory_sha256='1'*64)
        self.current = dict(source_revision=reuse.SOURCE, release_artifact_sha256=reuse.WORKER,
            archive_bundle_root=str(self.roots['current']), inventory_sha256='2'*64)
        self.validation = types.SimpleNamespace(resolutions={'S17-EXT-006':
            types.SimpleNamespace(semantic_context=self.current)})
        self.documents = dict(original_plan=copy.deepcopy(self.original_plan),
            original_request=dict(action_inputs=dict(plan=copy.deepcopy(self.original_plan))),
            original_authorization={},
            checkpoint=json.loads((fixture/'checkpoint.json').read_bytes()),
            failure=json.loads((fixture/'native_failure.json').read_bytes()),
            restoration=dict(verified=True, errors=[]),
            custody=dict(artifacts=[], status='ARCHIVED_AND_RELEASED'),
            original_context=dict(schema_version='cpu-prefetch-stage17-original-source-qualification-export/1',
                boot_id=window.BOOT, execution_authority=False, phase18_authority=False,
                resolutions={'S17-EXT-006':dict(semantic_context=release),
                    'S17-EXT-003':dict(semantic_context=dict(trust=dict(subject_id=self.plan['stand_id'],
                        measurements=dict(reviewer_role='OWNER'))))}))
        self.proof = dict(schema_version=reuse.SCHEMA, decision='D282')
        for name in (*self.documents, 'original_signature'):
            self.proof[name] = dict(path=str(self.root/name), size_bytes=1, sha256='0'*64)
        for name, digest in {**reuse.FIXED, 'original_plan':reuse.OLD_PLAN,
                'original_request':reuse.OLD_REQUEST, 'original_authorization':reuse.OLD_AUTHORIZATION}.items():
            self.proof[name]['sha256'] = digest
        (self.root/'formal-capture-0-final-checkpoint.json').write_bytes(b'{}')
        reader = mock.Mock()
        reader.document.side_effect = lambda binding:self.documents[Path(binding['path']).name]
        reader.read.return_value = b'original signed payload'
        self.reader = reader
        reader_patch = mock.patch.object(reuse.admission, 'BoundReader', return_value=reader)
        reader_patch.start(); self.addCleanup(reader_patch.stop)
        signature_patch = mock.patch.object(reuse.original.controller.support, '_verify_signature')
        self.signature = signature_patch.start(); self.addCleanup(signature_patch.stop)

    def inspect(self):
        return reuse.inspect(self.proof, self.plan, validation=self.validation)

    def test_matching_qualified_closures_and_bytes_pass_full_inspect(self):
        old, original_plan = self.inspect()
        self.assertEqual(original_plan, self.original_plan)
        self.assertEqual(old.resolutions['S17-EXT-006'].semantic_context['source_revision'], reuse.OLD_SOURCE)
        self.reader.finish.assert_called_once_with()
        self.signature.assert_called_once()

    def test_added_transitive_dependency_is_rejected(self):
        (self.roots['current']/'tools/helper.py').write_bytes(b'import extra\n')
        (self.roots['current']/'tools/extra.py').write_bytes(b'VALUE = 1\n')
        with self.assertRaisesRegex(reuse.admission.AdmissionError, 'complete identical generator closure'):
            self.inspect()

    def test_missing_transitive_dependency_is_rejected(self):
        for name in ('generate_schedule.py','stage17_q16c_schedule_provenance_v2.py'):
            (self.roots['current']/'tools'/name).write_bytes(b'VALUE = 1\n')
        with self.assertRaisesRegex(reuse.admission.AdmissionError, 'complete identical generator closure'):
            self.inspect()

    def test_changed_python_bytes_with_identical_membership_are_rejected(self):
        path = self.roots['current']/'tools/helper.py'
        path.write_bytes(b'VALUE = "different source"\n')
        with self.assertRaisesRegex(reuse.admission.AdmissionError, 'unchanged original generator tools/helper.py'):
            self.inspect()

    def test_each_schema_requires_identical_bytes(self):
        for name, raw in self.files.items():
            if not name.endswith('.json'): continue
            with self.subTest(schema=name):
                path = self.roots['current']/name; path.write_bytes(raw+b'\n')
                try:
                    with self.assertRaisesRegex(reuse.admission.AdmissionError, 'unchanged original generator'):
                        self.inspect()
                finally: path.write_bytes(raw)

    def test_missing_schema_is_rejected(self):
        (self.roots['current']/'config/schemas/schedule-derivation-v2.schema.json').unlink()
        with self.assertRaises(FileNotFoundError): self.inspect()

    def test_wrong_or_relabelled_consumer_is_rejected(self):
        for name, value in [('source_revision',reuse.OLD_SOURCE),
                ('release_artifact_sha256',reuse.OLD_WORKER), ('inventory_sha256','1'*64),
                ('archive_bundle_root',str(self.roots['original']))]:
            with self.subTest(field=name):
                saved = self.current[name]; self.current[name] = value
                try:
                    with self.assertRaises(reuse.admission.AdmissionError): self.inspect()
                finally: self.current[name] = saved


if __name__ == '__main__': unittest.main()
