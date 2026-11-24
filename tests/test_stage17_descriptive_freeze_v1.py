"""Actual completed reports and negative scientific-claim/identity boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_descriptive_freeze_v1 as freeze

PATHS = {
    'Q16a': ROOT/'docs/evidence/stage17/Q16A-COMPOSITION-ACTUAL-20261115-01/stand/composition/authenticated-composition.json',
    'Q16b': ROOT/'docs/evidence/stage17/Q16B-D268-COMPLETE-20261117-01/calibration-validation.json',
    'Q16c': ROOT/'docs/evidence/stage17/Q16C-D306-COMPLETE-20261120-01/q16c-analysis-1/calibration-validation.json',
}


def binding(p):
    raw = p.read_bytes()
    return dict(path=str(p), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def results():
    values = {k:json.loads(p.read_bytes()) for k,p in PATHS.items()}
    values['Q16a'] = values['Q16a']['calibration']
    return values


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.sources = {k:binding(p) for k,p in PATHS.items()}
        self.predecessors = [dict(input_id=f'S17-EXT-{i:03d}', resolution_id=f'SOFTWARE-FIXTURE-{i}', sha256=str(i)*64) for i in range(1,7)]
        p = Path(self.tmp.name)/'provenance.json'
        p.write_bytes(freeze.canonical(dict(schema_version='cpu-prefetch-stage17-descriptive-freeze-provenance/1',
            source_records=self.sources,predecessor_resolutions=self.predecessors,execution_authority=False,phase18_authority=False)))
        self.proof = binding(p)

    def build(self):
        return freeze.build(record_id='SOFTWARE-TEST-OF-ACTUAL-COMPLETED-REPORTS',created_at_utc='2026-11-20T04:00:00Z',
            source_records=self.sources,provenance_record=self.proof,predecessor_resolutions=self.predecessors)

    def test_actual_1008_reports_preserve_methods_strata_and_failed_zero_loss(self):
        out = self.build(); freeze.verify(out)
        self.assertEqual(out['coverage'], {'Q16a':708,'Q16b':120,'Q16c':180})
        self.assertEqual(out['original_phase_count'], 2016)
        self.assertEqual(out['outputs']['q16b']['derived_result']['min_mu_ref'], dict(numerator=1670571,denominator=1))
        self.assertEqual(out['outputs']['q16b']['base_rates']['L025'], dict(numerator=1670571,denominator=4))
        self.assertEqual([r['distance']['d2_cache_lines'] for r in out['outputs']['q16a']['derived_result']['contexts']], [2]*6)
        self.assertEqual(out['outputs']['q16c']['platform_strata'], [dict(regime='UNRECORDED',captures=86),dict(regime='VERIFIED_ZERO',captures=94)])
        self.assertEqual(len(out['outputs']['q16c']['observed_zero_loss']['measurement']['full_bearing_original_ordinals']), 3)
        self.assertEqual(len(out['outputs']['q16c']['observed_zero_loss']['warmup']['full_bearing_original_ordinals']), 25)
        self.assertEqual(out['outputs']['q16c']['observed_zero_loss']['measurement']['zero_loss_gate'], 'FAIL')
        self.assertEqual(out['operational_admission'], 'NOT_GRANTED_BY_RECORD')
        self.assertFalse(out['legacy_statistical_freeze_satisfied'])
        self.assertEqual(out['state'], 'DESCRIPTIVE_DATA_FROZEN')

    def test_authority_legacy_status_confidence_or_feasibility_cannot_be_promoted(self):
        out = self.build()
        for key,value in [('execution_authority',True),('phase18_authority',True),('pilot_execution_authority',True),
                          ('legacy_statistical_freeze_satisfied',True),('state','FROZEN'),('operational_admission','PASS')]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                freeze.verify({**out,key:value})
        bad = copy.deepcopy(out); bad['outputs']['q16b']['tolerance_guarantee'] = True
        with self.assertRaises(ValueError): freeze.verify(bad)
        bad = copy.deepcopy(out); bad['outputs']['q16c']['final_scale_selection'] = 1
        with self.assertRaises(ValueError): freeze.verify(bad)

    def test_actual_source_bytes_and_all_three_compositions_are_mandatory(self):
        original = copy.deepcopy(self.sources)
        self.sources['Q16c']['sha256'] = 'f'*64
        with self.assertRaises(ValueError): self.build()
        self.sources = original; del self.sources['Q16b']
        with self.assertRaises(ValueError): self.build()

    def test_missing_duplicate_and_cross_family_run_identities_are_rejected(self):
        base = results()
        for change in ('missing','duplicate_report','cross_family_run','invalid'):
            bad = copy.deepcopy(base)
            if change == 'missing': bad['Q16c']['run_sources'].pop()
            elif change == 'duplicate_report': bad['Q16c']['run_sources'][1]['report_binding'] = bad['Q16a']['run_sources'][0]['report_binding']
            elif change == 'cross_family_run': bad['Q16b']['run_sources'][0]['warmup_run_id'] = bad['Q16a']['run_sources'][0]['warmup_run_id']
            else: bad['Q16b']['run_sources'][0]['validity'] = 'INVALID'
            with self.subTest(change=change),self.assertRaises(ValueError): freeze.project(bad)

    def test_strata_guarantees_observed_counts_and_rational_minima_are_checked(self):
        for change in ('strata','homogeneity','confidence','tolerance','minimum','counts','zero_loss'):
            bad = results()
            if change == 'strata': bad['Q16c']['run_sources'][0]['platform']['regime'] = 'VERIFIED_ZERO'
            elif change == 'homogeneity': bad['Q16c']['homogeneous_platform_evidence'] = True
            elif change == 'confidence': bad['Q16c']['confidence_claim'] = '95%'
            elif change == 'tolerance': bad['Q16b']['tolerance_guarantee'] = True
            elif change == 'minimum': bad['Q16b']['derived_result']['min_mu_ref']['numerator'] += 1
            elif change == 'counts': bad['Q16c']['run_sources'][0]['phases'][0]['counts']['accepted'] += 1
            else: bad['Q16c']['observed_zero_loss']['measurement']['zero_loss_gate'] = 'PASS'
            with self.subTest(change=change),self.assertRaises(ValueError): freeze.project(bad)

    def test_provenance_must_bind_the_actual_sources_and_six_predecessors(self):
        raw = json.loads(Path(self.proof['path']).read_bytes()); raw['source_records']['Q16b']['sha256'] = 'f'*64
        Path(self.proof['path']).write_bytes(freeze.canonical(raw)); self.proof = binding(Path(self.proof['path']))
        with self.assertRaises(ValueError): self.build()

    def test_scoped_schema_and_legacy_export_remain_distinct(self):
        from jsonschema import Draft202012Validator
        import stage17_calibration_export_v2 as legacy
        schema = json.loads((ROOT/freeze.SCHEMA_PATH).read_bytes())
        Draft202012Validator(schema).validate(self.build())
        with self.assertRaises(ValueError):
            legacy.validate_export(self.build(),owner_decision=None,source_packets=None)

    def test_symlink_cannot_replace_an_audited_source_locator(self):
        p = Path(self.tmp.name)/'composition-link.json'; p.symlink_to(PATHS['Q16c'])
        self.sources['Q16c']['path'] = str(p)
        with self.assertRaises(ValueError): self.build()

    def test_actual_publisher_writes_and_signs_the_separate_data_record(self):
        import contextlib,io as output_io,shutil,subprocess
        import prepare_stage17_descriptive_freeze_v1 as publisher
        import stage17_q16c_continuation_operator_v1 as file_io
        root = Path(self.tmp.name); packet = root/'packet'; packet.mkdir()
        evidence = root/'evidence'; evidence.mkdir(); destination = evidence/'freeze-1'
        for name in ('prepare_stage17_descriptive_freeze_v1.py','stage17_descriptive_freeze_v1.py'):
            shutil.copyfile(ROOT/'tools'/name,packet/name)
        shutil.copyfile(ROOT/freeze.SCHEMA_PATH,packet/'stage17-ext007-descriptive-freeze-v1.schema.json')
        rows = [dict(path=p.name,size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(packet.iterdir())]
        (packet/'manifest.json').write_bytes(freeze.canonical(dict(schema_version='software-d307-descriptive-freeze-packet/1',files=rows,execution_authority=False)))
        key = root/'software-only-key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
        allowed = root/'allowed'; allowed.write_text('software-owner '+key.with_suffix('.pub').read_text())
        trust = dict(measurements=dict(allowed_signers_path=str(allowed),allowed_signers_size_bytes=allowed.stat().st_size,
            allowed_signers_sha256=hashlib.sha256(allowed.read_bytes()).hexdigest(),principal='software-owner',sshsig_namespace='stage17-owner-acceptance'))
        real_run = subprocess.run
        def run(argv,**kwargs):
            if argv[:3] == ['ssh-keygen','-Y','sign']:
                argv = list(argv); argv[argv.index('-f')+1] = str(key)
            return real_run(argv,**kwargs)
        proof = json.loads(Path(self.proof['path']).read_bytes())
        args = ['publisher','--packet-sha256',binding(packet/'manifest.json')['sha256'],'--output-root',str(destination)]
        with patch.object(publisher,'__file__',str(packet/'prepare_stage17_descriptive_freeze_v1.py')), \
                patch.object(publisher,'E',evidence),patch.object(publisher,'authenticate',return_value=(file_io,self.sources,proof,trust)), \
                patch.object(publisher.os,'getresuid',return_value=(1000,)*3),patch.object(publisher.os,'getresgid',return_value=(1000,)*3), \
                patch.object(publisher.os,'getgroups',return_value=[]),patch.object(publisher.os,'sched_setaffinity'), \
                patch.object(publisher.resource,'setrlimit'),patch.object(publisher.signal,'alarm'), \
                patch.object(publisher.sys,'argv',args),patch.object(subprocess,'run',side_effect=run), \
                contextlib.redirect_stdout(output_io.StringIO()):
            publisher.main()
        completed = json.loads((destination/'complete.json').read_bytes())
        self.assertEqual(completed['status'],'DESCRIPTIVE_DATA_FREEZE_PUBLISHED')
        self.assertEqual(completed['original_report_count'],1008)
        self.assertFalse(completed['operational_ext007_admitted'])
        self.assertTrue(Path(completed['signature']['path']).is_file())
        data = json.loads((destination/'calibration-freeze.json').read_bytes())
        freeze.verify(data)


if __name__ == '__main__': unittest.main()
