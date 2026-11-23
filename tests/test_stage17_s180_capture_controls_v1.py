"""Disjoint retained-byte fixtures; no host measurement or qualification claim."""
import copy
from contextlib import ExitStack
import io
import json
from pathlib import Path
import tempfile
import time
import unittest

import stage17_s180_capture_controls_v1 as v
import test_stage17_formal_service_capture_validation_v1 as old


class Fixture(old.Fixture):
    def __init__(self,root,full=False):
        super().__init__(root,scheduled=True,full=full)
        self.legacy=copy.deepcopy((self.control,self.final,self.capture,self.resources,self.monitoring,self.hardware))
        c=self.capture;g=c['geometry'];self.bounds=[]
        for i,b in enumerate(c['budget']['phases']):
            source=c['schedules'][i]
            self.bounds.append(dict(producer_attempt_limit=b['producer_attempt_limit'],consumer_poll_limit=b['consumer_poll_limit'],
                drain_duration_ticks=b['drain_ns']*1000,offered_count=source['offered_count'],
                source_origin_ticks=source['source_origin_ticks'],source_horizon_ticks=source['source_horizon_ticks']))
        self.capture=dict(execution_ordinal=0,requested_geometry=g,requested_hardware_state=c['hardware_state'],
            verified_hardware_state=None,
            placement=c['placement'],working_set_class=c['working_set_class'],run_id=c['measurement']['run_id'],
            warmup_run_id=c['warmup']['run_id'],warmup_ns=c['warmup_ns'],measurement_ns=c['measurement_ns'],
            arena_namespace='SOFTWARE-S180-PERSISTENT-ARENA',node_order_namespace='SOFTWARE-S180-PERSISTENT-NODES')
        pre=self.control['native_result_before_publication_returns']
        pre['session']=dict(initial_queue_reset=True,scheduled=pre['session'])
        self.final['session']=copy.deepcopy(pre['session'])
        pre['cleanup_scope']=self.final['cleanup_scope']=v.SCOPE
        self.control.update(schema_version=v.CONTROL,method_id=v.METHOD,execution_ordinal=0,
            prospective_capture=copy.deepcopy(self.capture),repeated_temporal_block_covariance_claim=False,
            cleanup_observation_scope='BEFORE_PRIVATE_CLEANUP_FAMILY_CLEANUP_REQUIRES_SEPARATE_EVIDENCE')
        self.control.pop('capture_ordinal');self.control.pop('schedule_mapping')
        maps=[];self.cleanup={}
        sizes=[((g['capacity']*72+4095)//4096)*4096,((g['capacity']+1)*64+12288+4095)//4096*4096]
        for i,name in enumerate(('records','queues')):
            plan=dict(bytes=sizes[i],verified_base_page_bytes=4096,owner_cpu=g['producer_cpu'],requested_node=g['shared_node'])
            address=0xA00000+i*0x200000
            mapping=old.qfixture.evidence.mapping(plan,address,201)
            maps.append(mapping);self.cleanup[name]=copy.deepcopy(mapping)
            self.cleanup[name].update(cleanup_attempted=True,unlock=old.qfixture.evidence.call(),unmap=old.qfixture.evidence.call())
            self.resources['region_bytes'].append(sizes[i])
            self.control['regions'].append(dict(address=address,bytes=sizes[i],expected_node=g['shared_node']))
        self.resources['total_mapping_bytes']+=sum(sizes)
        for key in ('region_bytes','total_mapping_bytes'):self.control['layout'][key]=copy.deepcopy(self.resources[key])
        base=0xC00000
        self.control['shared_data']=dict(available=True,stable_identity=True,lifetime='ENTIRE_FAMILY_NOT_PER_CAPTURE',
            final_family_cleanup_observed=False,mappings=maps,arena_object=base,ring_object=base+64,
            linked_object=base+128,node_bytes=base+4096,
            **{k:self.capture[k] for k in ('placement','working_set_class','arena_namespace','node_order_namespace')})
        self.monitoring['during_first_page'].extend([0,0]);self.monitoring['during_page_count'].extend([1,1])
        states=pre['session']['scheduled']['lifecycle']['phases']
        rows=[]
        for phase,state in enumerate(states):
            begin=state['observed_origin'];duration=state['window']['duration_ticks']
            for moment in range(3):
                template=next(r for r in self.control['residency'] if r['request']['phase']==phase and r['request']['moment']==moment)
                for i,region in enumerate(self.control['regions']):
                    row=copy.deepcopy(template);offset=self.monitoring['during_offset_ticks'][phase] if moment==1 else 0
                    row['request']=dict(phase=phase,moment=moment,region_index=i,offset_ticks=offset)
                    row['controls']=2 if i==self.monitoring['control_region_index'] else 1
                    count=1 if moment==1 else region['bytes']//4096
                    row['page_addresses']=[region['address']+n*4096 for n in range(count)]
                    row['page_status']=[region['expected_node']]*count
                    tick=(begin-30000 if moment==0 else begin+offset if moment==1 else begin+duration+300000)+i*2000
                    row.update(begin=old.qfixture.clock(tick),end=old.qfixture.clock(tick+1000))
                    if moment==1:row.update(wait_first=old.qfixture.clock(tick),wait_last=old.qfixture.clock(tick))
                    rows.append(row)
        self.control['residency']=rows
        env=old.qfixture.evidence.env_fixture
        body=b''.join(env.vma(r['address'],r['address']+r['bytes']) for r in self.control['regions'])
        source=self.monitoring['environment_sources'][0]
        self.control['environment_samples']=[env.sample(body,source,0,group) for group in range(6)]
        workers=dict(records_bytes=self.resources['region_bytes'][0],producer_bytes=self.resources['region_bytes'][1],
            consumer_bytes=self.resources['region_bytes'][2],schedule_offsets=[0,64],emitter_object=0,package_object=64,
            phases=[dict(producer_object=128,consumer_object=0,producer_raw=576,consumer_raw=576,
                raw=dict(producer_bytes=64,consumer_bytes=64)) for _ in range(2)])
        self.expected_layout=copy.deepcopy(dict(self.control['layout'],workers=workers))
        self.control['layout']['workers']={k:x for k,x in workers.items() if k!='phases'}
        self.control['layout']['workers']['phases']=[dict(producer_object=128,consumer_object=0,producer_raw=576,
            consumer_raw=576,producer_raw_bytes=64,consumer_raw_bytes=64) for _ in range(2)]
        self.resources={k:x for k,x in self.resources.items() if k in
            ('workers','controller_stack','tls_module_capacity','thread_stat_bytes','thread_status_bytes',
                'thread_affinity_words','initial_consumer_state','phase_capacity')}
        self.hardware=dict(identity=self.monitoring.pop('hardware_identity'),
            prestate=[dict(cpu=r['cpu'],value=int(r['complete_value_hex'],16)) for r in self.hardware['prestate']],
            software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')
        self.monitoring.pop('ordinal')

    def run(self,deadline_ns=None):
        return v.validate_capture_controls(self.control,self.final,capture=self.capture,resources=self.resources,
            monitoring=self.monitoring,hardware_control=self.hardware,expected_layout=self.expected_layout,
            phase_bounds=self.bounds,family_context_cleanup=self.cleanup,
            deadline_ns=time.monotonic_ns()+10**10 if deadline_ns is None else deadline_ns)


class ControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='s180-controls-software-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.f=Fixture(self.root)

    def fails(self):
        with self.assertRaises(v.ValidationError):self.f.run()

    def test_all54_pages_actual_lifecycle_and_private_and_shared_cleanup(self):
        r=self.f.run();self.assertTrue(r['capture_control_evidence_validated'])
        self.assertEqual(r['residency_observations_verified'],54);self.assertEqual(len(r['regions']),9)
        self.assertTrue(r['private_cleanup_verified']);self.assertTrue(r['shared_context_cleanup_verified'])
        for k in ('raw_reconciliation_performed','original_sources_verified','node_order_verified',
                'complete_family_lineage_verified','run_validity_assessed','execution_authority'):
            self.assertFalse(r[k])

    def test_full_is_retained_and_does_not_fail_control_validity(self):
        self.f=Fixture(self.root,full=True);self.assertTrue(self.f.run()['capture_control_evidence_validated'])

    def test_real_streaming_control_parser_packed_pages_are_not_materialized_for_hashing(self):
        with ExitStack() as stack:
            original=json.dumps(self.f.control)
            self.f.control=v.common.JsonReader(io.StringIO(original),stack).document()
            self.assertIsInstance(self.f.control['residency'][-1]['page_status'],v.common.PackedPages)
            self.assertTrue(self.f.run()['capture_control_evidence_validated'])

    def test_h1_requires_actual_full_value_readbacks_and_keeps_requested_verified_distinct(self):
        f=self.f;f.capture['requested_hardware_state']='H1';f.control['prospective_capture']=copy.deepcopy(f.capture)
        for c in f.control['controls']:
            c['hardware']['requested_state']=1
            for cpu in c['hardware']['cpus']:
                cpu.update(raw_bytes=list((15).to_bytes(8,'little')),observed_value=15,expected_value=15)
        self.assertTrue(f.run()['capture_control_evidence_validated'])
        self.assertIsNone(f.capture['verified_hardware_state'])
        f.control['controls'][0]['hardware']['cpus'][0]['raw_bytes'][0]=0;self.fails()

    def test_shared_region_must_not_overlap_private_mapping_or_separate_monitor(self):
        for address in (0x100000,0x800000):
            self.f=Fixture(self.root)
            self.f.control['shared_data']['mappings'][0]['mapping']['address']=address
            self.f.cleanup['records']['mapping']['address']=address
            self.f.control['regions'][7]['address']=address
            self.fails()

    def test_original_seven_region_validator_still_accepts_original_evidence(self):
        c,f,cap,r,m,h=self.f.legacy
        result=old.v.validate_capture(self.root,c,f,cap,r,m,h)
        self.assertTrue(result['capture_execution_evidence_validated'])

    def test_nine_region_environment_has_distinct_identity_and_checks_last_region(self):
        f=self.f
        r=v.common.environment.validate_s180_environment(f.control,f.monitoring['environment_sources'],
            f.control['regions'],base_page_bytes=4096)
        self.assertEqual(r['schema_version'],'cpu-prefetch-s180-environment-validation/1')
        self.assertTrue(all(len(x['regions'])==9 for x in r['smaps_groups']))
        with self.assertRaises(v.common.environment.EnvironmentEvidenceError):
            v.common.environment.validate_environment(f.control,f.monitoring['environment_sources'],f.control['regions'],base_page_bytes=4096)
        source=f.monitoring['environment_sources'][0];env=old.qfixture.evidence.env_fixture
        body=b''.join(env.vma(r['address'],r['address']+r['bytes']) for r in f.control['regions'][:-1])
        f.control['environment_samples'][5]=env.sample(body,source,0,5);self.fails()

    def test_extra_shared_queries_cannot_be_dropped_reordered_or_relabelled(self):
        for mutation in ('drop','order','label'):
            self.f=Fixture(self.root);rows=self.f.control['residency']
            if mutation=='drop':rows.pop(8)
            elif mutation=='order':rows[7],rows[8]=rows[8],rows[7]
            else:rows[8]['request']['region_index']=7
            self.fails()

    def test_shared_query_addresses_nodes_syscalls_and_time_are_independently_checked(self):
        for mutation in ('address','node','syscall','time','during_finished'):
            self.f=Fixture(self.root);row=self.f.control['residency'][17]
            if mutation=='address':row['page_addresses'][0]+=4096
            elif mutation=='node':row['page_status'][0]=99
            elif mutation=='syscall':row['query']['syscall_return']=-1
            elif mutation=='time':row['end']=old.qfixture.clock(0)
            else:row['finished_after']=1
            self.fails()

    def test_shared_preparation_readonly_identity_lifetime_and_bounds(self):
        for mutation in ('cleanup','readonly','owner','namespace','object','extent','alias'):
            self.f=Fixture(self.root);s=self.f.control['shared_data']
            if mutation=='cleanup':s['mappings'][0]['cleanup_attempted']=True
            elif mutation=='readonly':s['mappings'][0]['read_only']['return_value']=-1
            elif mutation=='owner':s['mappings'][1]['after_touch']['thread_id']['return_value']+=1
            elif mutation=='namespace':s['arena_namespace']='WRONG-SOFTWARE-ARENA'
            elif mutation=='object':s['arena_object']=0
            elif mutation=='extent':s['node_bytes']+=self.f.expected_layout['region_bytes'][8]
            else:s['linked_object']=s['ring_object']
            self.fails()

    def test_shared_release_requires_original_mapping_owner_and_successful_calls(self):
        for mutation in ('identity','owner','unmap','unlock','attempt','request'):
            self.f=Fixture(self.root);q=self.f.cleanup['queues']
            if mutation=='identity':q['mapping']['address']+=4096
            elif mutation=='owner':q['after_touch']['thread_id']['return_value']+=1
            elif mutation in ('unmap','unlock'):q[mutation]['return_value']=-1
            elif mutation=='attempt':q['cleanup_attempted']=False
            else:q['requested']['bytes']+=4096
            self.fails()

    def test_session_origin_reset_stop_counts_and_watchdogs_are_bound(self):
        for mutation in ('reset','stop','origin','count','watchdog','complete'):
            self.f=Fixture(self.root);p=self.f.control['native_result_before_publication_returns']
            s=p['session']['scheduled']['lifecycle']
            if mutation=='reset':p['session']['initial_queue_reset']=False
            elif mutation=='stop':s['stop']=2
            elif mutation=='origin':s['phases'][1]['origin_sample']['absolute_nanoseconds']+=1
            elif mutation=='count':s['phases'][1]['producer']['full']+=1
            elif mutation=='watchdog':self.f.bounds[1]['consumer_poll_limit']=1
            else:p['stop']=13
            self.f.final['session']=copy.deepcopy(p['session']);self.fails()

    def test_after_query_must_precede_checkpoint_and_next_phase_before_observations(self):
        self.f.control['residency'][26]['end']['relative_picoseconds']+=1000000
        self.f.control['residency'][26]['end']['absolute_nanoseconds']+=1000;self.fails()

    def test_bound_sizes_during_extents_and_cold_worker_layout_cannot_drift(self):
        for mutation in ('size','during','workers'):
            self.f=Fixture(self.root)
            if mutation=='size':self.f.expected_layout['region_bytes'][8]+=4096
            elif mutation=='during':self.f.monitoring['during_first_page'][8]=1000000
            else:self.f.control['layout']['workers']['schedule_offsets'][0]+=8
            self.fails()

    def test_private_cleanup_and_real_hardware_observation_cannot_be_substituted(self):
        for mutation in ('private','hardware','prestate'):
            self.f=Fixture(self.root)
            if mutation=='private':self.f.final['worker_mappings'][0]['unmap']['return_value']=-1
            elif mutation=='hardware':self.f.control['controls'][-1]['hardware']['cpus'][-1]['raw_bytes'][0]^=1
            else:self.f.hardware['prestate'][0]['value']=16
            self.fails()

    def test_scheduled_finish_before_horizon_does_not_inherit_q16b_hold_rule(self):
        p=self.f.control['native_result_before_publication_returns'];s=p['session']['scheduled']
        for i,state in enumerate(s['lifecycle']['phases']):
            finish=state['window']['producer_deadline_ticks']-1000
            state['producer'].update(last_observed_tick=finish,deadline_reached=False)
            s['schedules'][i]['producer_completion']=old.qfixture.clock(finish)
        self.f.final['session']=copy.deepcopy(p['session'])
        self.assertTrue(self.f.run()['capture_control_evidence_validated'])

    def test_native_schedule_proof_drift_and_original_deadline_fail(self):
        for mutation in ('count','clock','last','validated'):
            self.f=Fixture(self.root);p=self.f.control['native_result_before_publication_returns']
            row=p['session']['scheduled']['schedules'][1]
            if mutation=='count':row['offered']+=1
            elif mutation=='clock':row['producer_completion']['absolute_nanoseconds']+=1
            elif mutation=='last':row['mapped_last_deadline']=0
            else:row['mapped_schedule_validated']=False
            self.f.final['session']=copy.deepcopy(p['session']);self.fails()
        self.f=Fixture(self.root)
        with self.assertRaisesRegex(v.ValidationError,'deadline expired'):self.f.run(deadline_ns=0)

    def test_missing_bounds_bad_integer_geometry_and_uncovered_raw_capacity_fail(self):
        for mutation in ('capacity','line','state','source','raw_capacity','stack'):
            self.f=Fixture(self.root)
            if mutation=='capacity':self.f.capture['requested_geometry']['capacity']=True
            elif mutation=='line':self.f.capture['requested_geometry']['cache_line_bytes']=0
            elif mutation=='state':self.f.capture['requested_hardware_state']='UNKNOWN'
            elif mutation=='source':self.f.bounds[0]['source_horizon_ticks']+=1
            elif mutation=='raw_capacity':self.f.resources['phase_capacity'][0]['consumer_primary_rows']=1
            else:self.f.resources['workers']['producer_stack']['owner_cpu']=99
            self.f.control['prospective_capture']=copy.deepcopy(self.f.capture);self.fails()


if __name__=='__main__':unittest.main()
