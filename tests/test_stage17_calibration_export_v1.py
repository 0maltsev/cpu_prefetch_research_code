"""D237 synthetic bounded exports; no signed authority or hardware claims."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import struct
import tempfile
import unittest

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_calibration_export_v1 as export
import stage17_formal_calibration_v1 as cal
import test_stage17_formal_calibration_v1 as fixtures
from test_stage17_formal_plan_v1 import plan_fixture
from test_stage17_formal_service_capture_validation_v1 import Fixture as ServiceFixture


def packet(name, document):
    raw = cal.canonical(document)
    return dict(binding=fixtures.binding(name, raw), utf8_bytes=raw)


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.CalibrationTests.setUpClass()
        cls.addClassCleanup(fixtures.CalibrationTests.doClassCleanups)
        f = fixtures.CalibrationTests
        cls.identity = dict(record_id='SYNTHETIC-EXPORT', stand_id='synthetic-stand',
                            source_revision='a'*40, created_at_utc='2026-11-03T18:00:00Z')
        # Deliberately self-attesting claims must NOT produce FROZEN.
        cls.owner = packet('owner', dict(approved=True, authenticated=True, state='FROZEN'))
        cls.sources = dict(plans={}, calibrations={}, capture_reports={}, geometry_sources=[],
            lifecycle={a:packet('lifecycle-'+a, dict(action_id=a, admitted=True, signature_verified=True))
                       for a in export.ACTIONS},
            probe_design=packet('probe-design', dict(common_marginal=True, independent_runs=True)),
            analysis_provenance=packet('analysis-code', dict(authenticated=True)))
        geometry = copy.deepcopy(f.geometry)
        for g in geometry:
            p = packet('native-layout-'+str(g['context_ordinal']), dict(
                layout=dict(workers=dict(ring_storage=dict(slot_bytes=g['slot_storage_bytes'])))))
            g['source_binding'] = p['binding']; cls.sources['geometry_sources'].append(p)
        for action in ('Q16a', 'Q16b'):
            plan = copy.deepcopy(f.plans[action]); records = copy.deepcopy(f.records[action])
            cls.rename(plan, action)
            if action == 'Q16b': cls.ring_reuse(plan, geometry, cls.q16a)
            rows = []
            for record, item in zip(records, plan['captures'], strict=True):
                c = item['capture']; report = json.loads(record['report_utf8_bytes'])
                for phase_index, phase in enumerate(('warmup', 'measurement')):
                    report['phases'][phase_index]['run_id'] = c[phase]['run_id']
                    if action == 'Q16a':
                        for owner in report['phases'][phase_index]['demand'].values(): owner['run_id'] = c[phase]['run_id']
                p = packet(action+'-capture-report-'+str(c['ordinal']), report)
                rows.append(dict(capture_ordinal=c['ordinal'], measurement_run_id=c['measurement']['run_id'],
                                 validity='VALID', report=p))
            cal_rows = [dict(capture_ordinal=r['capture_ordinal'],measurement_run_id=r['measurement_run_id'],
                validity=r['validity'],report_binding=r['report']['binding'],report_utf8_bytes=r['report']['utf8_bytes'].decode())
                for r in rows]
            result = cal.evaluate(action, plan, cal_rows, geometry if action == 'Q16a' else None)
            cls.sources['plans'][action] = packet(action+'-plan', plan)
            cls.sources['calibrations'][action] = packet(action+'-calibration', result)
            cls.sources['capture_reports'][action] = rows
            if action == 'Q16a': cls.q16a = (result, cls.sources['calibrations'][action]['binding'])
        plan = plan_fixture('Q16c'); cls.rename(plan, 'Q16c'); cls.ring_reuse(plan, geometry, cls.q16a)
        cls.sources['plans']['Q16c'] = packet('Q16c-plan', plan)
        with tempfile.TemporaryDirectory() as directory:
            prototype = ServiceFixture(Path(directory), scheduled=True).run()
        rows = []
        for item in plan['captures']:
            c = item['capture']; doc = copy.deepcopy(prototype); doc['capture_ordinal'] = c['ordinal']
            for i, phase in enumerate(('warmup', 'measurement')):
                n = c['schedules'][i]['offered_count']
                doc['phases'][i].update(run_id=c[phase]['run_id'], zero_loss=True,
                    counts=dict(offered=n, attempted=n, accepted=n, full=0, consumed_including_drain=n))
                source = c['schedules'][i]
                doc['schedules'][i].update(offered=n, source_origin_ticks=source['source_origin_ticks'],
                    source_sha256=hashlib.sha256(b''.join(struct.pack('<Q', t)
                        for t in source['deadline_ticks'])).hexdigest())
            # The full-family fixture consists of synthetic report documents,
            # not 180 actual native captures. No raw provenance is asserted.
            doc['node_order']['count'] = c['geometry']['capacity'] + 1 if c['package'] in ('L0','L1') else 0
            doc.update(measurement_zero_loss=True,zero_loss_all_phases=True)
            rows.append(dict(capture_ordinal=c['ordinal'],measurement_run_id=c['measurement']['run_id'],
                validity='VALID',report=packet('Q16c-capture-report-'+str(c['ordinal']),doc)))
        cls.sources['capture_reports']['Q16c'] = rows
        cls.result = export.build_export(identity=cls.identity,owner_decision=cls.owner,source_packets=cls.sources)

    @staticmethod
    def rename(plan, action):
        for phase in ('warmup','measurement'):
            plan[phase+'_namespace'] = action+'-'+plan[phase+'_namespace']
        for item in plan['captures']:
            c=item['capture']
            for phase in ('warmup','measurement'):
                for name in ('run_id','seed_id'): c[phase][name]=action+'-'+c[phase][name]
                c[phase]['namespace_id']=plan[phase+'_namespace']
            c['arena_seed']=copy.deepcopy(c['measurement'])

    @staticmethod
    def ring_reuse(plan, geometry, q16a):
        result, bound = q16a
        for item in plan['captures']:
            c=item['capture']
            if c['package'] in ('R0','R1','R2'):
                context=(0 if c['placement']=='NEAR' else 3)+export.plans.WORKING_SETS.index(c['working_set_class'])
                c['geometry']['capacity']=geometry[context]['capacity']
                if c['package']=='R2':
                    c['ring_distance']=dict(cache_lines=result['derived_result']['contexts'][context]['distance']['d2_cache_lines'],
                        calibration_evidence_id='q16a-sha256-'+bound['sha256'])

    def test_complete_original_reports_math_but_untrusted_provenance_unresolved(self):
        d=self.result
        self.assertEqual(d['state'],'UNRESOLVED')
        self.assertEqual(d['outputs']['q16b']['mu_ref'],dict(numerator=80,denominator=1))
        self.assertEqual(d['outputs']['q16a']['contexts'][0]['distance']['d2_cache_lines'],4)
        self.assertEqual(d['outputs']['q16c']['coverage_state'],'COMPLETE')
        self.assertEqual(len(d['outputs']['q16c']['run_sources']),180)
        self.assertIn('OWNER_AUTHORITY_PROVENANCE_NOT_ADMITTED',d['blockers'])
        self.assertFalse(d['execution_authority']);self.assertFalse(d['phase18_authority'])
        self.assertEqual(d['final_matrix_feasibility'],export.FINAL)
        self.assertEqual(d['outputs']['service_rate_unit'],'EVENTS_PER_SECOND')

    def test_schema_and_independent_full_recomputation(self):
        schema=json.loads(export.SCHEMA_PATH.read_text());Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.result)
        self.assertIs(export.validate_export(self.result,owner_decision=self.owner,source_packets=self.sources),self.result)
        d=copy.deepcopy(self.result);d['outputs']['q16b']['mu_ref']['numerator']=81
        with self.assertRaisesRegex(export.ExportError,'recomputed'):
            export.validate_export(d,owner_decision=self.owner,source_packets=self.sources)

    def test_frozen_final_pass_authority_and_old_method_cannot_be_relabelled(self):
        for key,value in (('state','FROZEN'),('execution_authority',True),('phase18_authority',True)):
            d=copy.deepcopy(self.result);d[key]=value
            with self.assertRaises(export.ExportError):export.validate_export(d,owner_decision=self.owner,source_packets=self.sources)
        d=copy.deepcopy(self.result);d['final_matrix_feasibility']['passes']=True
        with self.assertRaises(export.ExportError):export.validate_export(d,owner_decision=self.owner,source_packets=self.sources)
        old=json.loads((export.SCHEMA_PATH.parent/'calibration-freeze-v1.schema.json').read_text())
        self.assertFalse(Draft202012Validator(old).is_valid(self.result))

    def test_original_byte_hash_duplicate_keys_and_invented_decoded_packet_rejected(self):
        for raw in (b'{"approved":true,"approved":true}',b'{"n":NaN}',b'{"n":1.5}',b'\xff'):
            owner=dict(binding=fixtures.binding('owner',raw),utf8_bytes=raw)
            with self.assertRaises(export.ExportError):
                export.build_export(identity=self.identity,owner_decision=owner,source_packets=self.sources)
        owner=copy.deepcopy(self.owner);owner['binding']['sha256']='0'*64
        with self.assertRaises(export.ExportError):export.build_export(identity=self.identity,owner_decision=owner,source_packets=self.sources)
        owner=copy.deepcopy(self.owner);owner['document']={'approved':True}
        with self.assertRaises(export.ExportError):export.build_export(identity=self.identity,owner_decision=owner,source_packets=self.sources)

    def probe_inputs(self):
        plan=json.loads(self.sources['plans']['Q16c']['utf8_bytes'])
        _,reports=export._reports('Q16c',self.sources['capture_reports']['Q16c'],plan,{})
        return plan,reports

    def test_probe_missing_and_full_never_create_success_or_new_sample(self):
        plan,reports=self.probe_inputs();reports.pop(179)
        d,blockers=export._probe(plan,reports)
        self.assertEqual(d['coverage_state'],'UNRESOLVED');self.assertIn('MISSING',blockers[0])
        self.assertEqual(d['run_sources'][-1]['validity'],'MISSING')
        plan,reports=self.probe_inputs();valid,doc,bound=reports[0]
        c=doc['phases'][1]['counts'];c.update(full=1,accepted=c['attempted']-1,consumed_including_drain=c['attempted']-1)
        doc['phases'][1]['zero_loss']=doc['measurement_zero_loss']=doc['zero_loss_all_phases']=False
        d,blockers=export._probe(plan,reports)
        self.assertEqual(blockers,[]);self.assertEqual(d['run_sources'][0]['counts'][1]['full'],1)
        self.assertEqual(d['inference_state'],'NOT_EVALUATED')

    def test_probe_report_method_origin_identity_counts_and_flags_reject(self):
        mutations=[lambda d:d.update(method_id='WRONG'),lambda d:d.update(capture_ordinal=True),
            lambda d:d.update(raw_reconciliation_validated=False),lambda d:d.update(capture_execution_evidence_validated=False),
            lambda d:d.update(family_validity_established=True),lambda d:d.update(phase18_authority=True),
            lambda d:d['phases'][1].update(run_id='wrong'),lambda d:d['phases'][1]['counts'].update(offered=0),
            lambda d:d['phases'][1]['counts'].update(full=True),
            lambda d:d['schedules'][1].update(source_sha256='e'*64),
            lambda d:d['schedules'][0].update(source_origin_ticks=0),
            lambda d:d['schedules'][1].update(actual_phase_origin_ticks=True),
            lambda d:d.update(schedules=[]),lambda d:d['node_order'].update(count=1),
            lambda d:d['node_order'].update(sha256='e'*64+'\n')]
        for mutate in mutations:
            plan,reports=self.probe_inputs();mutate(reports[0][1])
            with self.assertRaises(export.ExportError):export._probe(plan,reports)

    def test_missing_original_calibration_receipt_rejects_retained_valid_claim(self):
        sources=dict(self.sources);sources['capture_reports']=dict(self.sources['capture_reports'])
        sources['capture_reports']['Q16a']=self.sources['capture_reports']['Q16a'][:-1]
        with self.assertRaisesRegex(export.ExportError,'original report recomputation'):
            export.build_export(identity=self.identity,owner_decision=self.owner,source_packets=sources)


if __name__=='__main__':unittest.main(verbosity=2)
