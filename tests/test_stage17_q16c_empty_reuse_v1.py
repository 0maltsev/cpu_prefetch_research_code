"""D282 software-only incident and prospective-input regression checks."""
import copy
import json
from pathlib import Path
import sys
import unittest

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


if __name__ == '__main__': unittest.main()
