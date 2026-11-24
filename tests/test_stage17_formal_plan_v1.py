"""D228 complete software declarations, not stand sizing or scientific admission."""
import copy
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from jsonschema import Draft202012Validator
import stage17_formal_plan_v1 as contract
from test_stage17_formal_ring_plan_v1 import plan_fixture as ring_fixture


def plan_fixture(action='Q16c', repetitions=None):
    scheduled = action == 'Q16c'
    repetitions = (1 if scheduled else 59) if repetitions is None else repetitions
    original = ring_fixture()
    template = original['captures'][0]
    captures = []
    for state_index, state in enumerate(('H0', 'H1')):
        for package_index, package in enumerate(('R0', 'R1', 'R2', 'L0', 'L1')):
            for placement_index, placement in enumerate(('NEAR', 'FAR')):
                for ws_index, ws in enumerate(('L2_RESIDENT', 'LLC_RESIDENT', 'BEYOND_LLC')):
                    service_cell = package_index * 12 + state_index * 6 + placement_index * 3 + ws_index
                    for load_index, load in enumerate(('L025', 'L050', 'L075') if scheduled else (None,)):
                        for repetition in range(repetitions):
                            ordinal = len(captures)
                            item = copy.deepcopy(template)
                            c, r, m = (item[key] for key in ('capture', 'resources', 'monitoring'))
                            del c['context_ordinal']; del c['minimum_observations_per_series']
                            kind = 'scheduled' if scheduled else 'service'
                            c.update(schema_version=f'cpu-prefetch-stage17-formal-{kind}-capture/1',
                                method_id=contract.METHOD[action], package=package, ordinal=ordinal,
                                cell_ordinal=service_cell * 3 + load_index if scheduled else service_cell,
                                repetition_ordinal=repetition, hardware_state=state, placement=placement,
                                working_set_class=ws, software_prefetch_mapping_id='synthetic-software-mapping',
                                linked_order=None, ring_distance=None)
                            c['geometry'].update(capacity=64,consumer_cpu=8 if placement=='FAR' else 1,
                                                 consumer_node=1 if placement=='FAR' else 0)
                            for phase_index, phase in enumerate(('warmup','measurement')):
                                c[phase]=dict(run_id=f'{phase[0].upper()}{ordinal:04}',seed_id=f'S{phase_index}-{ordinal}',
                                    seed_hex=f'{ordinal*2+phase_index:064x}',namespace_id='formal-'+phase)
                            c['arena_seed']=copy.deepcopy(c['measurement'])
                            if package in ('L0','L1'):
                                c['linked_order']=dict(seed_id='synthetic-node-order',seed_hex='f'*64,
                                    namespace_id='node-order',arena_alignment_bytes=4096)
                            elif package in ('R1','R2'):
                                c['ring_distance']=dict(cache_lines=1 if package=='R1' else 2,
                                    calibration_evidence_id='' if package=='R1' else 'synthetic-prior-q16a')
                            r['ordinal']=m['ordinal']=ordinal
                            r['workers']['consumer_stack'].update(owner_cpu=c['geometry']['consumer_cpu'],
                                requested_node=c['geometry']['consumer_node'])
                            for rows in r['phase_capacity']:
                                del rows['producer_demand_rows']; del rows['consumer_demand_rows']
                            if scheduled:
                                c.update(scale_ordinal=0,load_level=load,schedules=[])
                                for phase_index, phase in enumerate(('warmup','measurement')):
                                    origin=1000; count=2 if phase_index==0 else 3
                                    c['schedules'].append(dict(schedule_id=f'schedule-{phase_index}-{ordinal}',
                                        seed_id=f'schedule-seed-{phase_index}-{ordinal}',seed_hex='e'*64,
                                        namespace_id=f'schedule-stream-{phase_index}-{ordinal}',
                                        source_origin_ticks=origin,source_horizon_ticks=origin+c[phase+'_ns']*1000,
                                        offered_count=count,deadline_ticks=[origin+i for i in range(count)],
                                        source_artifact=dict(artifact_id=f'schedule-source-{phase_index}-{ordinal}',sha256='d'*64)))
                            captures.append(item)
    original.pop('minimum_observations_per_series');original.pop('repetitions_per_context')
    original.update(schema_version=contract.VERSION[action],action_id=action,method_id=contract.METHOD[action],
        repetitions_per_cell=repetitions,captures=captures)
    if scheduled:original['scale_ordinal']=0
    budget=original['budget'];budget['watchdog_ns']=len(captures)*11_000_000_000+2_000_000_000
    budget['max_output_bytes']=len(captures)*20000+budget['metadata_output_bytes']
    budget['required_free_disk_bytes']=budget['max_output_bytes']+budget['analysis_scratch_bytes']+budget['disk_reserve_bytes']
    return original


class FormalPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan=plan_fixture()

    def reject(self, message=None, action=None):
        with self.assertRaises(contract.ContractError) as caught:
            contract.validate_plan(action or self.plan['action_id'],self.plan)
        if message:self.assertIn(message,str(caught.exception))

    def test_complete_service3540_raw_counts_order_and_budgets(self):
        plan=plan_fixture('Q16b')
        result=contract.validate_plan('Q16b',plan)
        self.assertEqual(len(result.captures),3540)
        self.assertEqual([e.ordinal for e in result.captures],list(range(3540)))
        self.assertEqual(result.captures[0].raw_bytes,2*10*(136+96))
        self.assertEqual(result.captures[3*6*59].raw_bytes,2*10*(136+96)+(64+1)*8)
        self.assertEqual(result.captures[0].largest_raw_copy_bytes,1360)
        self.assertEqual(result.required_watchdog_ns,3540*11_000_000_000+2_000_000_000)
        self.assertEqual(result.peak_memory_bytes,20400000)
        self.assertEqual(result.required_free_disk_bytes,3540*20000+3000000)
        self.assertFalse(result.execution_authority)
        identities=[item['capture']['cell_ordinal'] for item in plan['captures']]
        self.assertEqual(identities[6*59],12)
        self.assertEqual(identities[30*59],6)
        self.assertEqual({cell:identities.count(cell) for cell in range(60)},{cell:59 for cell in range(60)})

    def test_complete_scheduled180_exact_extra_vectors_and_shared_masterseed(self):
        result=contract.validate_plan('Q16c',self.plan)
        self.assertEqual(len(result.captures),180)
        self.assertEqual(result.captures[0].raw_bytes,4640+2*8+3*8)
        self.assertEqual(result.captures[54].raw_bytes,4640+65*8+2*8+3*8)
        self.assertEqual(self.plan['captures'][18]['capture']['cell_ordinal'],36)
        self.assertEqual(self.plan['captures'][90]['capture']['cell_ordinal'],18)
        self.assertEqual(result.required_watchdog_ns,180*11_000_000_000+2_000_000_000)
        self.assertFalse(result.execution_authority)
        self.assertEqual({s['seed_hex'] for x in self.plan['captures'] for s in x['capture']['schedules']},{'e'*64})

    def test_lp_run_id_padding_changes_exact_primary_extents(self):
        capture=self.plan['captures'][0]['capture']
        capture['warmup']['run_id']='WXYZ'  # 4-byte length + 4 bytes: 8-byte prefix.
        capture['measurement']['run_id']='M'*21  # 25 bytes rounded up to 32.
        capture['arena_seed']=copy.deepcopy(capture['measurement'])
        result=contract.validate_plan('Q16c',self.plan)
        self.assertEqual(result.captures[0].raw_bytes,10*(128+88+152+112)+40)
        self.assertEqual(result.captures[0].largest_raw_copy_bytes,1520)

    def test_schema_defs_match_native_and_complete_families_validate(self):
        for action in ('Q16b','Q16c'):
            with self.subTest(action=action):
                schema=json.loads((contract.ROOT/contract.SCHEMA[action]).read_text())
                native=json.loads((contract.ROOT/contract.NATIVE_SCHEMA[action]).read_text())
                Draft202012Validator.check_schema(schema)
                for key,value in native['$defs'].items():self.assertEqual(schema['$defs'][key],value)
                plan=plan_fixture(action)
                self.assertEqual(list(Draft202012Validator(schema).iter_errors(plan)),[])

    def test_q16a_delegates_unchanged_and_exports_extent_api(self):
        value={'opaque':'passed unchanged'};sentinel=object()
        with patch.object(contract.ring,'validate_plan',return_value=sentinel) as validate:
            self.assertIs(contract.validate_plan('Q16a',value),sentinel)
            validate.assert_called_once_with(value)
        self.assertIs(contract.FamilyExtent,contract.ring.FamilyExtent)
        self.assertIs(contract.CaptureExtent,contract.ring.CaptureExtent)
        self.reject(action='Q16a')
        for action in ('unknown',True,None):self.reject(action=action if action else 'unknown')

    def test_no_missing_extra_reordered_or_wrong_cell_repetition(self):
        original=copy.deepcopy(self.plan)
        for change in ('missing','extra','order','cell','state','package','load','repetition'):
            with self.subTest(change=change):
                self.plan=copy.deepcopy(original)
                if change=='missing':self.plan['captures'].pop()
                elif change=='extra':self.plan['captures'].append(copy.deepcopy(self.plan['captures'][0]))
                elif change=='order':self.plan['captures'][0],self.plan['captures'][1]=self.plan['captures'][1],self.plan['captures'][0]
                else:
                    key={'cell':'cell_ordinal','state':'hardware_state','package':'package','load':'load_level','repetition':'repetition_ordinal'}[change]
                    self.plan['captures'][0]['capture'][key]={'cell':1,'state':'H1','package':'R1','load':'L050','repetition':1}[change]
                self.reject()

    def test_repetition_floor_single_candidate_and_no_scientific_defaults(self):
        self.plan['repetitions_per_cell']=0;self.reject()
        self.plan=plan_fixture('Q16b',58);self.reject('repetitions_per_cell')
        self.plan=plan_fixture();self.plan['scale_ordinal']=5;self.reject('ladder')
        self.plan=plan_fixture();self.plan['captures'][-1]['capture']['scale_ordinal']=1;self.reject('scale_ordinal')
        self.plan=plan_fixture();self.plan['minimum_observations_per_series']=100000;self.reject('exactly fields')
        del self.plan['minimum_observations_per_series'];del self.plan['measurement_ns'];self.reject('exactly fields')

    def test_phase_and_schedule_identity_uniqueness_namespace_isolation(self):
        original=copy.deepcopy(self.plan)
        for field in ('run_id','seed_id','seed_hex'):
            self.plan=copy.deepcopy(original)
            self.plan['captures'][1]['capture']['warmup'][field]=self.plan['captures'][0]['capture']['warmup'][field]
            self.reject('reused')
        for field in ('schedule_id','seed_id'):
            self.plan=copy.deepcopy(original)
            self.plan['captures'][1]['capture']['schedules'][0][field]=self.plan['captures'][0]['capture']['schedules'][0][field]
            self.reject('reused')
        self.plan=copy.deepcopy(original)
        self.plan['captures'][1]['capture']['schedules'][1]['namespace_id']=self.plan['captures'][0]['capture']['schedules'][0]['namespace_id']
        self.reject('namespaces overlap')

    def test_recursive_float_bool_lf_ids_and_hex_rejected(self):
        original=copy.deepcopy(self.plan)
        for name in ('float','bool','id','hex','sourcehash','scheduleid'):
            with self.subTest(name=name):
                self.plan=copy.deepcopy(original);first=self.plan['captures'][0]
                if name=='float':first['resources']['thread_stat_bytes']=4096.0
                elif name=='bool':first['capture']['measurement_ns']=True
                elif name=='id':first['capture']['warmup']['seed_id']+='\n'
                elif name=='hex':first['capture']['warmup']['seed_hex']+='\n'
                elif name=='sourcehash':first['capture']['schedules'][0]['source_artifact']['sha256']+='\n'
                else:first['capture']['schedules'][0]['schedule_id']+='\n'
                self.reject()

    def test_schedule_horizon_count_order_endpoint_and_capacity(self):
        original=copy.deepcopy(self.plan)
        for change in ('length','empty_measurement','endpoint','before','order','origin_overflow','duration','watchdog'):
            with self.subTest(change=change):
                self.plan=copy.deepcopy(original);c=self.plan['captures'][0]['capture'];s=c['schedules'][1]
                if change=='length':s['offered_count']+=1
                elif change=='empty_measurement':s['offered_count']=0;s['deadline_ticks']=[]
                elif change=='endpoint':s['deadline_ticks'][-1]=s['source_horizon_ticks']
                elif change=='before':s['deadline_ticks'][0]=s['source_origin_ticks']-1
                elif change=='order':s['deadline_ticks'].reverse()
                elif change=='origin_overflow':s['source_origin_ticks']=(1<<64)-1
                elif change=='duration':s['source_horizon_ticks']+=1
                else:s['offered_count']=11;s['deadline_ticks']=[1000]*11
                self.reject()
        self.plan=copy.deepcopy(original);source=self.plan['captures'][0]['capture']['schedules'][0]
        source['offered_count']=0;source['deadline_ticks']=[]
        # Native warmup permits an empty explicit source. This is no wall-time or monitoring claim.
        self.assertEqual(contract.validate_plan('Q16c',self.plan).captures[0].raw_bytes,4640+24)

    def test_package_specific_declarations_and_paired_geometry(self):
        original=copy.deepcopy(self.plan)
        for change in ('r0_distance','r1_evidence','r2_missing','linked_missing','linked_alignment','paired','owner','observer'):
            with self.subTest(change=change):
                self.plan=copy.deepcopy(original)
                if change=='r0_distance':self.plan['captures'][0]['capture']['ring_distance']={'cache_lines':1,'calibration_evidence_id':''}
                elif change=='r1_evidence':self.plan['captures'][18]['capture']['ring_distance']['calibration_evidence_id']='wrong'
                elif change=='r2_missing':self.plan['captures'][36]['capture']['ring_distance']=None
                elif change=='linked_missing':self.plan['captures'][54]['capture']['linked_order']=None
                elif change=='linked_alignment':self.plan['captures'][54]['capture']['linked_order']['arena_alignment_bytes']=8192
                elif change=='paired':self.plan['captures'][90]['capture']['geometry']['capacity']=128
                elif change=='owner':self.plan['captures'][0]['resources']['workers']['consumer_stack']['owner_cpu']=26
                else:self.plan['captures'][0]['monitoring']['during_offset_ticks'][1]=1_000_000_000_000
                self.reject()

    def test_repeated_cell_bounds_do_not_adapt(self):
        self.plan=plan_fixture('Q16c',2)
        self.plan['captures'][1]['monitoring']['observer_wait_poll_limit']+=1
        self.reject('repeated_bounds')

    def test_complete_output_includes_extra_vectors_and_conservative_copy_floor(self):
        item=self.plan['captures'][54];c=item['capture'];budget=item['execution_budget']
        budget['max_output_bytes']=4640+520+40+budget['metadata_output_bytes']-1
        self.reject('output omitted')
        budget['max_output_bytes']=20000
        for phase,rows,source in zip(c['budget']['phases'],item['resources']['phase_capacity'],c['schedules'],strict=True):
            phase['producer_attempt_limit']=1
            rows['producer_primary_rows']=rows['consumer_primary_rows']=1
            source['offered_count']=1;source['deadline_ticks']=source['deadline_ticks'][:1]
        budget['publication_memory_bytes']=535
        self.reject('copy floor')
        budget['publication_memory_bytes']=536
        result=contract.validate_plan('Q16c',self.plan)
        self.assertEqual(result.captures[54].raw_bytes,464+520+16)
        self.assertEqual(result.captures[54].largest_raw_copy_bytes,520)

    def test_checked_overflows_signed_watchdogs_and_all_budget_components(self):
        original=copy.deepcopy(self.plan)
        for change in ('duration','raw_product','consumer_capacity','signed_capture','signed_family','sum_memory','capture_time','mapping','process','family_output','disk_declared'):
            with self.subTest(change=change):
                self.plan=copy.deepcopy(original);item=self.plan['captures'][0];budget=item['execution_budget']
                if change=='duration':self.plan['measurement_ns']=(1<<64)-1
                elif change=='raw_product':item['resources']['phase_capacity'][0]['producer_primary_rows']=(1<<64)-1
                elif change=='consumer_capacity':item['resources']['phase_capacity'][0]['consumer_primary_rows']=9
                elif change=='signed_capture':budget['watchdog_ns']=1<<63
                elif change=='signed_family':self.plan['budget']['watchdog_ns']=1<<63
                elif change=='sum_memory':budget['other_memory_bytes']=(1<<64)-1
                elif change=='capture_time':budget['watchdog_ns']-=1
                elif change=='mapping':item['capture']['budget']['memory_bytes']=199999
                elif change=='process':budget['memory_bytes']=399999
                elif change=='family_output':self.plan['budget']['max_output_bytes']-=1
                else:self.plan['budget']['max_output_bytes']+=1
                self.reject()


if __name__=='__main__':
    unittest.main(verbosity=2)
