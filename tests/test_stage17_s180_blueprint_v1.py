import copy
from fractions import Fraction
import itertools
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_blueprint_v1 as pilot


class BlueprintTests(unittest.TestCase):
    def setUp(self):
        self.value = pilot.build(blueprint_id='SOFTWARE-S180-NOT-REGISTERED',master_seed_hex='b3'*32)

    def test_all_factors_one_repetition_and_two_whole_plots(self):
        rows = self.value['captures']
        expected = set(itertools.product(('R0','R1','R2','L0','L1'),('H0','H1'),
            ('NEAR','FAR'),('L2_RESIDENT','LLC_RESIDENT','BEYOND_LLC'),('L025','L050','L075')))
        self.assertEqual({(r['package'],r['requested_hardware_state'],r['placement'],
            r['working_set_class'],r['load_level']) for r in rows},expected)
        self.assertEqual(len(rows),180)
        self.assertEqual(sorted(r['execution_ordinal'] for r in rows),list(range(180)))
        ordered = sorted(rows,key=lambda r:r['execution_ordinal'])
        for block in range(2):
            self.assertEqual({r['requested_hardware_state'] for r in ordered[block*90:(block+1)*90]},
                             {self.value['requested_whole_plot_order'][block]})
        self.assertTrue(all(r['warmup_ns']==5_000_000_000 and r['measurement_ns']==1_000_000_000
                            and r['repetition_ordinal']==0 for r in rows))

    def test_shared_paired_arenas_and_schedules_and_disjoint_phases(self):
        rows = self.value['captures'];self.assertEqual(len({r['arena_namespace'] for r in rows}),6)
        self.assertEqual(len({r['node_order_namespace'] for r in rows}),6)
        warm = {r['warmup_schedule_namespace'] for r in rows}
        measured = {r['measurement_schedule_namespace'] for r in rows}
        self.assertEqual(len(warm),18);self.assertEqual(len(measured),18);self.assertFalse(warm & measured)
        self.assertEqual(len({r['run_id'] for r in rows}|{r['warmup_run_id'] for r in rows}),360)
        for r in rows:
            rate=r['nominal_rate'];actual=Fraction(rate['numerator'],rate['denominator'])
            self.assertEqual(actual,Fraction(1670571)*{'L025':Fraction(1,4),'L050':Fraction(1,2),'L075':Fraction(3,4)}[r['load_level']])
            self.assertIsNone(r['verified_hardware_state'])

    def test_current_source_geometry_and_distance_without_verified_promotion(self):
        rows=self.value['captures']
        for r in rows:
            g=r['requested_geometry']
            self.assertEqual(g['capacity'],{'L2_RESIDENT':512,'LLC_RESIDENT':65536,'BEYOND_LLC':1048576}[r['working_set_class']])
            self.assertEqual((g['producer_cpu'],g['consumer_cpu']),(0,1 if r['placement']=='NEAR' else 8))
            self.assertEqual(r['distance']['d2_cache_lines'],2)
        self.assertEqual(self.value['geometry_evidence_status'],'SOURCE_DECLARATION_PENDING_CURRENT_ADMISSION')
        for key in ('launch_ready','execution_authority','phase18_authority','legacy_statistical_freeze_satisfied',
                    'operational_window_started','repeated_temporal_block_covariance_claim'):
            self.assertIs(self.value[key],False)

    def test_changed_coverage_rates_order_storage_or_authority_are_rejected(self):
        for key in ('coverage','rate','order','duration','geometry','storage','claim','authority','blockers'):
            bad=copy.deepcopy(self.value)
            if key=='coverage':bad['captures'].pop()
            elif key=='rate':bad['captures'][0]['nominal_rate']['numerator']+=1
            elif key=='order':bad['captures'][0]['execution_ordinal']=bad['captures'][1]['execution_ordinal']
            elif key=='duration':bad['captures'][0]['measurement_ns']+=1
            elif key=='geometry':bad['captures'][0]['verified_hardware_state']='H0'
            elif key=='storage':bad['storage']['independent_raw_backup']=True
            elif key=='claim':bad['repeated_temporal_block_covariance_claim']=True
            elif key=='authority':bad['launch_ready']=True
            else:bad['blockers']=[]
            with self.subTest(key=key),self.assertRaises(ValueError):pilot.verify(bad)

    def test_source_drift_and_unsupported_identity_fail(self):
        pins={**pilot.PINS,pilot.ACCEPTANCE:'0'*64}
        with patch.object(pilot,'PINS',pins),self.assertRaisesRegex(ValueError,'exact approved source'):
            pilot.verify(self.value)
        for seed,identity in [('not-a-seed','valid'),('b3'*32,'../unsafe')]:
            with self.assertRaises(ValueError):pilot.build(blueprint_id=identity,master_seed_hex=seed)

    def test_reproducible_design_and_changed_seed_requires_changed_full_order(self):
        self.assertEqual(pilot.verify(self.value),self.value)
        other=pilot.build(blueprint_id=self.value['blueprint_id'],master_seed_hex='b4'*32)
        self.assertNotEqual([r['execution_ordinal'] for r in self.value['captures']],
                            [r['execution_ordinal'] for r in other['captures']])

    def test_local_blueprint_reuses_prior_admission_without_remote_repreparation(self):
        with patch.object(pilot.freeze,'verify',side_effect=AssertionError('no repeated source preparation')) as prepare:
            value=pilot.build(blueprint_id=self.value['blueprint_id'],master_seed_hex=self.value['master_seed_hex'])
        prepare.assert_not_called();self.assertEqual(value,self.value)
        self.assertEqual(value['calibration_admission']['sha256'],pilot.PINS[pilot.ADMISSION])

    def test_repository_evidence_bindings_are_portable_to_the_stand(self):
        for key in ('approval','calibration_freeze','calibration_admission','ext007_resolution','observed_geometry_metadata'):
            self.assertFalse(Path(self.value[key]['path']).is_absolute(),key)
        # This is a retained source history locator on the stand, not a copied
        # PC repository binding or a claim about the future pilot producer.
        self.assertTrue(Path(self.value['source_geometry_plan']['path']).is_absolute())


if __name__=='__main__':unittest.main()
