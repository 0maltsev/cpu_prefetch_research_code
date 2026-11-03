"""D239 full synthetic archival lineage; no archive or execution provenance claim."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_calibration_export_v1 as old_export
import stage17_calibration_export_v2 as export
import stage17_formal_calibration_v1 as old_calibration
import stage17_formal_calibration_v2 as calibration
import stage17_formal_plan_v1 as old_plans
import stage17_formal_plan_v2 as plans
import stage17_formal_storage_budget_v1 as storage
import test_stage17_calibration_export_v1 as fixtures
import test_stage17_formal_calibration_v1 as report_fixtures


def archived_plan(original):
    document = copy.deepcopy(original)
    action = document['action_id']
    document['schema_version'] = plans.VERSION[action]
    document['custody_policy_id'] = storage.POLICY
    document['storage'] = dict(schema_version=storage.VERSION, program_id='synthetic-shared-program',
        policy_id=storage.POLICY, implementation_profile_sha256='a'*64, program_scope_sha256='e'*64,
        archive_quota_bytes=storage.QUOTA, workspace_bytes=storage.WORKSPACE,
        analysis_scratch_bytes=storage.SCRATCH, disk_reserve_bytes=storage.RESERVE,
        codec_address_space_bytes=storage.CODEC_MEMORY, codec_processes=1, broker_address_space_bytes=1024**3,
        per_capture_archive_ns=1_000_000_000, archive_staging_bytes=1_000_000,
        capture_workspace_overhead_bytes=4096, checkpoint_bytes=1000,
        analysis_capture_workspace_bytes=1_000_000)
    budget = document['budget']
    budget['watchdog_ns'] += len(document['captures']) * 1_000_000_000
    budget['memory_bytes'] += storage.CODEC_MEMORY + document['storage']['broker_address_space_bytes']
    budget['analysis_scratch_bytes'] = storage.SCRATCH
    budget['disk_reserve_bytes'] = storage.RESERVE
    budget['required_free_disk_bytes'] = storage.QUOTA + storage.WORKSPACE + storage.SCRATCH + storage.RESERVE
    return document


def reports(rows):
    return [dict(capture_ordinal=row['capture_ordinal'], measurement_run_id=row['measurement_run_id'],
                 validity=row['validity'], report_binding=row['report']['binding'],
                 report_utf8_bytes=row['report']['utf8_bytes'].decode()) for row in rows]


class ArchiveLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ExportTests.setUpClass()
        cls.addClassCleanup(fixtures.ExportTests.doClassCleanups)
        cls.original = fixtures.ExportTests
        cls.sources = copy.deepcopy(cls.original.sources)
        cls.plans = {}
        for action in ('Q16a','Q16b','Q16c'):
            plan = archived_plan(json.loads(cls.sources['plans'][action]['utf8_bytes']))
            if action != 'Q16a':
                cls.original.ring_reuse(plan, cls.geometry, cls.q16a)
            cls.plans[action] = plan
            cls.sources['plans'][action] = fixtures.packet(action+'-plan', plan)
            if action != 'Q16c':
                geometry = json.loads(cls.sources['calibrations']['Q16a']['utf8_bytes'])['ring_geometry'] if action == 'Q16a' else None
                result = calibration.evaluate(action, plan, reports(cls.sources['capture_reports'][action]), geometry)
                cls.sources['calibrations'][action] = fixtures.packet(action+'-calibration', result)
                if action == 'Q16a':
                    cls.geometry = geometry
                    cls.q16a = result, cls.sources['calibrations']['Q16a']['binding']
        cls.result = export.build_export(identity=cls.original.identity, owner_decision=cls.original.owner,
                                         source_packets=cls.sources)

    def test_original_v2_full_families_math_and_lineage_without_false_freeze(self):
        self.assertEqual(self.result['state'],'UNRESOLVED')
        self.assertFalse(self.result['execution_authority'])
        self.assertFalse(self.result['phase18_authority'])
        self.assertEqual(self.result['final_matrix_feasibility'],old_export.FINAL)
        self.assertEqual(self.result['outputs'],self.original.result['outputs'])
        self.assertEqual(self.result['blockers'],self.original.result['blockers'])
        for action in ('Q16a','Q16b'):
            document = json.loads(self.sources['calibrations'][action]['utf8_bytes'])
            self.assertEqual(document['status'],'VALIDATED')
            native = json.dumps(self.plans[action], sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.assertEqual(document['plan_sha256'],hashlib.sha256(native).hexdigest())
            self.assertNotEqual(document['plan_sha256'],hashlib.sha256(native+b'\n').hexdigest())
            old = json.loads(self.original.sources['calibrations'][action]['utf8_bytes'])
            self.assertNotEqual(document['plan_sha256'],old['plan_sha256'])
        self.assertEqual([len(self.plans[a]['captures']) for a in ('Q16a','Q16b','Q16c')],[708,3540,180])

    def test_revalidation_uses_archive_adapter_and_rejects_old_calibration_binding(self):
        self.assertIs(export.validate_export(self.result, owner_decision=self.original.owner,
                                            source_packets=self.sources),self.result)
        sources = dict(self.sources)
        sources['calibrations'] = dict(self.sources['calibrations'])
        sources['calibrations']['Q16a'] = self.original.sources['calibrations']['Q16a']
        with self.assertRaisesRegex(export.ExportError,'original report recomputation'):
            export.build_export(identity=self.original.identity,owner_decision=self.original.owner,source_packets=sources)

    def test_predecessor_globals_and_old_public_behavior_are_unchanged(self):
        self.assertIs(old_calibration.evaluate.__globals__['plans'],old_plans)
        self.assertIs(old_export._build.__globals__['plans'],old_plans)
        self.assertIs(old_export._build.__globals__['calibration'],old_calibration)
        for action in ('Q16a','Q16b'):
            with self.assertRaises(old_calibration.CalibrationError):
                old_calibration.evaluate(action,self.plans[action],[],self.geometry if action=='Q16a' else None)
        with self.assertRaises(old_export.ExportError):
            old_export.build_export(identity=self.original.identity,owner_decision=self.original.owner,
                                    source_packets=self.sources)
        plan = json.loads(self.original.sources['plans']['Q16a']['utf8_bytes'])
        before = old_calibration.canonical(plan)
        actual = calibration.evaluate('Q16a',plan,reports(self.original.sources['capture_reports']['Q16a']),self.geometry)
        self.assertEqual(actual,json.loads(self.original.sources['calibrations']['Q16a']['utf8_bytes']))
        self.assertEqual(old_calibration.canonical(plan),before)

    def test_invalid_receipt_requires_original_archive_plan_hash_missing_stays_unresolved(self):
        plan = self.plans['Q16a']; rows = reports(self.sources['capture_reports']['Q16a'])
        failure = report_fixtures.failure(plan,plan['captures'][0]['capture'],'Q16a')
        failure['plan_sha256'] = hashlib.sha256(calibration.plan_bytes(plan)).hexdigest()
        rows[0] = report_fixtures.record(plan['captures'][0]['capture'],failure,'INVALID')
        rows.pop()
        before = old_calibration.canonical(plan)
        result = calibration.evaluate('Q16a',plan,rows,self.geometry)
        self.assertEqual(result['status'],'UNRESOLVED')
        self.assertEqual(result['run_sources'][0]['validity'],'INVALID')
        self.assertEqual(result['run_sources'][-1]['validity'],'MISSING')
        self.assertEqual(old_calibration.canonical(plan),before)
        old = json.loads(self.original.sources['plans']['Q16a']['utf8_bytes'])
        failure['plan_sha256'] = hashlib.sha256(old_calibration.canonical(old)).hexdigest()
        rows[0] = report_fixtures.record(plan['captures'][0]['capture'],failure,'INVALID')
        with self.assertRaisesRegex(calibration.CalibrationError,'plan_sha256'):
            calibration.evaluate('Q16a',plan,rows,self.geometry)

    def test_storage_and_unknown_version_rejected_before_any_math(self):
        for mutate in (lambda p:p.pop('storage'),
                       lambda p:p['storage'].update(archive_quota_bytes=1),
                       lambda p:p['budget'].update(watchdog_ns=1),
                       lambda p:p.update(schema_version=plans.VERSION['Q16a'].replace('/2','/3'))):
            plan = copy.deepcopy(self.plans['Q16a']); mutate(plan)
            with self.assertRaises(calibration.CalibrationError):
                calibration.evaluate('Q16a',plan,[],self.geometry)

    def test_original_packet_hashes_are_not_relabelled(self):
        for action in ('Q16a','Q16b','Q16c'):
            packet = self.sources['plans'][action]
            self.assertEqual(self.result['plan_bindings'][action],packet['binding'])
            self.assertEqual(hashlib.sha256(packet['utf8_bytes']).hexdigest(),packet['binding']['sha256'])
            self.assertEqual(json.loads(packet['utf8_bytes'])['schema_version'],plans.VERSION[action])
        document = copy.deepcopy(self.result);document['state']='FROZEN'
        with self.assertRaises(export.ExportError):
            export.validate_export(document,owner_decision=self.original.owner,source_packets=self.sources)


if __name__ == '__main__':
    unittest.main(verbosity=2)
