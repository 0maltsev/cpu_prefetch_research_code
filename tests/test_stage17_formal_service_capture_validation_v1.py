"""D229 small independent retained-byte fixtures, no empirical/stand claim."""
from __future__ import annotations
import copy
import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import stage17_formal_service_capture_validation_v1 as v
import test_stage17_q16a_capture_validation_v1 as qfixture


class Fixture(qfixture.Fixture):
    def __init__(self,root,*,scheduled=False,full=False):
        super().__init__(root,full=full)
        self.action='Q16c' if scheduled else 'Q16b'
        c=self.capture;c.pop('context_ordinal');c.pop('minimum_observations_per_series')
        c.update(schema_version='cpu-prefetch-stage17-formal-'+('scheduled' if scheduled else 'service')+'-capture/1',
            method_id=v.plans.METHOD[self.action],cell_ordinal=0,linked_order=None,ring_distance=None,
            software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1')
        self.monitoring['hardware_identity']=dict(family=6,model=62)
        for rows in self.resources['phase_capacity']:
            rows.pop('producer_demand_rows');rows.pop('consumer_demand_rows')
        self.control.pop('minimum_observations_per_series')
        self.control.update(schema_version=v.CONTROL_IDS[self.action],method_id=c['method_id'],completion_rule=v.RULES[self.action])
        for i,phase in enumerate(self.control['phases']):
            old=phase['producer_current']
            phase['producer_current']=dict(status=0,failed_boundary=None,clock_status=0,observation=old['primary'])
            phase['consumer_current']=dict(status=1,failed_boundary=None,clock_status=0,record_status=0,observation=None)
            phase['retained_attempts']=phase.pop('attempted');phase['retained_consumed_including_drain']=phase.pop('consumed_including_drain')
            for role in ('producer','consumer'):
                phase[role+'_last_append']=phase.pop(role+'_last_primary_append')
                if role=='consumer':phase[role+'_last_append']=None
                phase[role]['role']=self.action.upper()+'_PRIMARY_RAW'
                for key in list(phase):
                    if key.startswith(role+'_demand') or key in (role+'_prefix_complete',role+'_last_demand_append'):
                        del phase[key]
            phase['completion_interval']=None
        self.control['node_order']=self.artifact('node-order.bin',b'',self.action.upper()+'_NODE_ORDER','NODEORDER-U64LE-v1')
        self.control['node_order_count']=0
        if scheduled:
            c.update(load_level='L025',scale_ordinal=0,schedules=[])
            source_results=[];published=[]
            for i,name in enumerate(v.PHASES):
                state=self.states()[i];begin=state['observed_origin'];duration=state['window']['duration_ticks']
                values=[7000+p[2]-begin for p in self.rows[(i,'producer')]]
                source=dict(schedule_id=name+'-schedule',seed_id=name+'-schedule-seed',seed_hex='a'*64,
                    namespace_id=name+'-schedule-namespace',source_origin_ticks=7000,source_horizon_ticks=7000+duration,
                    offered_count=len(values),deadline_ticks=values,source_artifact=dict(artifact_id=name+'-source',sha256='b'*64))
                c['schedules'].append(source)
                result=dict(offered=len(values),source_origin_ticks=7000,source_horizon_ticks=7000+duration,
                    producer_wait_polls=0,mapped_last_deadline=begin+values[-1]-7000,
                    producer_completion=qfixture.clock(state['producer']['last_observed_tick']),mapped_schedule_validated=True,
                    all_arrivals_attempted=True)
                source_results.append(result)
                stream=self.artifact(name+'-schedule.bin',struct.pack('<'+str(len(values))+'Q',*values),'Q16C_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1')
                published.append(dict(prospective=copy.deepcopy({k:v for k,v in source.items() if k!='deadline_ticks'}),prepared_available=True,
                    stream=stream,time_unit='PICOSECONDS',coordinates='SOURCE_SCHEDULE_BEFORE_ACTUAL_ORIGIN_TRANSLATION',
                    prepared_count=len(values),source_origin_ticks=7000,source_horizon_ticks=7000+duration,phase_released=True,
                    attempted=len(values),all_arrivals_attempted=True))
                self.control['phases'][i].pop('completion_interval')
            pre=self.control['native_result_before_publication_returns'];pre['session']=dict(lifecycle=pre['session'],schedules=source_results)
            self.control['schedules']=published
        else:self.recount_interval()
        self.extend_records()
        self.sync()

    def extend_records(self):
        capacity=self.capture['geometry']['capacity']
        offset=(capacity*72+63)//64*64
        size=((offset+128+4095)//4096)*4096
        prior=self.resources['region_bytes'][0]
        self.resources['region_bytes'][0]=size
        self.resources['total_mapping_bytes']+=size-prior
        self.control['layout']['region_bytes']=list(self.resources['region_bytes'])
        self.control['layout']['total_mapping_bytes']=self.resources['total_mapping_bytes']
        self.control['layout']['workers']=dict(record_order=capacity*64)
        self.control['regions'][0]['bytes']=size
        for document in (self.control,self.final):
            document['worker_mappings'][0]['requested']['bytes']=size
            document['worker_mappings'][0]['prefaulted_pages']=size//4096
        for row in self.control['residency']:
            if row['request']['region_index']==0 and row['request']['moment']!=1:
                row['page_addresses']=[self.control['regions'][0]['address']+i*4096 for i in range(size//4096)]
                row['page_status']=[0]*(size//4096)
        env=qfixture.evidence.env_fixture
        body=b''.join(env.vma(r['address'],r['address']+r['bytes']) for r in self.control['regions'])
        source=self.monitoring['environment_sources'][0]
        self.control['environment_samples']=[env.sample(body,source,0,group) for group in range(6)]
        if self.action=='Q16c':self.control['schedule_mapping']=dict(offsets=[offset,offset+64],counts=[4,4])

    def states(self):
        session=self.control['native_result_before_publication_returns']['session']
        return session.get('lifecycle',session)['phases']
    def sync(self):self.final['session']=copy.deepcopy(self.control['native_result_before_publication_returns']['session'])
    def artifact(self,name,data,role,schema):
        (self.root/name).write_bytes(data)
        return dict(file_name=name,role=role,schema_identity=schema,size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    def recount_interval(self):
        state=self.states()[1];begin=state['observed_origin'];duration=state['window']['duration_ticks'];end=begin+duration
        rows=self.rows[(1,'consumer')];inside=sum(begin<=r[9]<end for r in rows)
        w=dict(clock_suite_id=v.raw.CLOCK_SUITE_ID,time_unit=v.raw.TIME_UNIT,ticks_per_second=10**12,
            clock_origin_absolute_nanoseconds=1_000_000,measurement_origin=qfixture.sample(begin),duration_ticks=duration)
        self.control['phases'][1]['completion_interval']=dict(status=0,failed_consumer_row=None,counts=dict(measurement_window=w,
            interval_end_ticks=end,consumed_count=len(rows),interval_consumed_count=inside,outside_interval_consumed_count=len(rows)-inside))
    def run(self):return v.validate_capture(self.root,self.control,self.final,self.capture,self.resources,self.monitoring,self.hardware)


class FormalCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)

    def test_both_modes_full_valid_and_zero_loss_separate(self):
        for scheduled in (False,True):
            for full in (False,True):
                f=Fixture(self.root,scheduled=scheduled,full=full);report=f.run()
                self.assertTrue(report['raw_reconciliation_validated']);self.assertTrue(report['capture_execution_evidence_validated'])
                self.assertEqual(report['measurement_zero_loss'],not full)
                self.assertFalse(report['family_validity_established']);self.assertFalse(report['execution_authority'])
                self.assertEqual(report['phases'][1]['counts']['accepted'],4-int(full))
                if not scheduled:
                    self.assertEqual(report['phases'][1]['completion_interval']['interval_consumed_count'],3-int(full))
                    self.assertEqual(report['phases'][1]['completion_interval']['outside_interval_consumed_count'],1)
                else:
                    self.assertNotIn('completion_interval',report['phases'][1])
                    self.assertNotIn('completion_counting_rule',report['source_versions'])

    def test_service_exact_end_excluded_and_zero_throughput_retained(self):
        f=Fixture(self.root);state=f.states()[1];end=state['window']['producer_deadline_ticks']
        for n,row in enumerate(f.rows[(1,'consumer')]):
            finish=end+n*10000
            for off,delta in ((2,-3000),(4,-2000),(6,-1000),(8,0)):
                tick=finish+delta;row[off]=1_000_000+tick//1000;row[off+1]=tick
        f.save_rows(1,'consumer');f.recount_interval()
        result=f.run()['phases'][1]['completion_interval']
        self.assertEqual(result['interval_consumed_count'],0);self.assertEqual(result['outside_interval_consumed_count'],4)

    def test_scheduled_due_times_allow_late_handling_and_no_horizon_hold(self):
        f=Fixture(self.root,scheduled=True)
        for i in range(2):
            phase=f.control['phases'][i];state=f.states()[i]
            finish=f.rows[(i,'producer')][-1][12]+1000
            state['producer'].update(last_observed_tick=finish,deadline_reached=False)
            f.control['native_result_before_publication_returns']['session']['schedules'][i]['producer_completion']=qfixture.clock(finish)
            # Common source arrival at origin is legal; actual handlers run later.
            source=f.capture['schedules'][i];source['deadline_ticks']=[source['source_origin_ticks']]*4
            f.control['schedules'][i]['stream']=f.artifact(v.PHASES[i]+'-schedule.bin',struct.pack('<4Q',*source['deadline_ticks']),
                'Q16C_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1')
            f.control['native_result_before_publication_returns']['session']['schedules'][i]['mapped_last_deadline']=state['observed_origin']
            for row in f.rows[(i,'producer')]:row[2]=state['observed_origin']
            phase['producer_current']['observation']['scheduled_arrival']=state['observed_origin']
            f.save_rows(i,'producer')
        f.sync();self.assertTrue(f.run()['measurement_zero_loss'])

    def test_wrong_due_source_or_missing_arrival_rejected(self):
        for mutant in ('raw_due','source_bytes','offered','prepared','release'):
            f=Fixture(self.root,scheduled=True)
            if mutant=='raw_due':
                f.rows[(1,'producer')][0][2]+=1000;f.save_rows(1,'producer')
            elif mutant=='source_bytes':
                path=self.root/f.control['schedules'][1]['stream']['file_name'];data=path.read_bytes();path.write_bytes(bytes([data[0]^1])+data[1:])
                f.control['schedules'][1]['stream']['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            elif mutant=='offered':f.capture['schedules'][1]['offered_count']+=1
            elif mutant=='prepared':f.control['schedules'][1]['prepared_available']=False
            else:f.control['schedules'][1]['phase_released']=False
            with self.subTest(mutant=mutant),self.assertRaises(v.ValidationError):f.run()

    def test_excluded_drain_corruption_not_waived(self):
        for scheduled in (False,True):
            for field in (0,1,2,3,8,9):
                f=Fixture(self.root,scheduled=scheduled);f.rows[(1,'consumer')][-1][field]^=1;f.save_rows(1,'consumer')
                with self.subTest(scheduled=scheduled,field=field),self.assertRaises(v.ValidationError):f.run()

    def test_bad_primary_headers_hashes_truncation_and_aliases(self):
        for mutation in ('run_id','padding','hash','truncate','alias'):
            f=Fixture(self.root);p=f.control['phases'][1]['producer'];path=self.root/p['file_name'];data=bytearray(path.read_bytes())
            if mutation=='alias':f.control['phases'][1]['consumer']['file_name']=p['file_name']
            else:
                if mutation=='run_id':data[4]^=1
                elif mutation=='padding':data[v.codec.row_layout(f.capture['measurement']['run_id'])[0]-1]^=1
                elif mutation=='hash':data[-1]^=1
                else:data=data[:-1]
                path.write_bytes(data)
                if mutation in ('run_id','padding'):p['sha256']=hashlib.sha256(data).hexdigest()
            with self.subTest(mutation=mutation),self.assertRaises(v.ValidationError):f.run()

    def test_control_reset_cleanup_and_count_failures(self):
        for scheduled in (False,True):
            for mutant in ('during','reset','cleanup','checksum','counts','current','interval'):
                f=Fixture(self.root,scheduled=scheduled)
                if mutant=='during':f.states()[1]['during_observed']=False;f.sync()
                elif mutant=='reset':
                    session=f.control['native_result_before_publication_returns']['session'];session.get('lifecycle',session)['queue_reset']=False;f.sync()
                elif mutant=='cleanup':f.final['worker_mappings'][0]['cleanup_attempted']=False
                elif mutant=='checksum':f.control['phases'][1]['checksum']^=1
                elif mutant=='counts':f.control['phases'][1]['retained_attempts']+=1
                elif mutant=='current':f.control['phases'][1]['consumer_current']['status']=2
                elif scheduled:f.control['phases'][1]['completion_interval']={}
                else:f.control['phases'][1]['completion_interval']['counts']['interval_consumed_count']+=1
                with self.subTest(scheduled=scheduled,mutant=mutant),self.assertRaises(v.ValidationError):f.run()

    def test_five_package_declarations_and_linked_order_replay(self):
        for scheduled in (False,True):
            for number,package in enumerate(v.plans.PACKAGES):
                f=Fixture(self.root,scheduled=scheduled)
                f.capture.update(package=package,cell_ordinal=number*12*(3 if scheduled else 1))
                if package in ('R1','R2'):
                    f.capture['ring_distance']=dict(cache_lines=1 if package=='R1' else 3,
                        calibration_evidence_id='' if package=='R1' else 'synthetic-accepted-distance')
                if package in ('L0','L1'):
                    f.capture['linked_order']=dict(seed_id='node-seed',seed_hex='c'*64,namespace_id='node-namespace',
                        arena_alignment_bytes=f.capture['geometry']['base_page_bytes'])
                    # Fixture uses the registered deterministic generator; byte
                    # reversal below separately tests original order, not a set.
                    count=f.capture['geometry']['capacity']+1;order=list(range(count))
                    draws=v.common.draws(v.common.key('c'*64,'node-namespace','node-order'))
                    for remaining in range(count,1,-1):
                        threshold=((1<<64)-remaining)%remaining
                        while True:
                            value=next(draws)
                            if value>=threshold:break
                        selected=value%remaining
                        order[remaining-1],order[selected]=order[selected],order[remaining-1]
                    f.control['node_order_count']=count
                    f.control['node_order']=f.artifact('node-order.bin',struct.pack('<'+str(count)+'Q',*order),
                        f.action.upper()+'_NODE_ORDER','NODEORDER-U64LE-v1')
                with self.subTest(scheduled=scheduled,package=package):self.assertTrue(f.run()['raw_reconciliation_validated'])
                if package in ('L0','L1'):
                    order[0],order[1]=order[1],order[0]
                    f.control['node_order']=f.artifact('node-order.bin',struct.pack('<'+str(count)+'Q',*order),
                        f.action.upper()+'_NODE_ORDER','NODEORDER-U64LE-v1')
                    with self.assertRaises(v.ValidationError):f.run()

    def test_missing_mandatory_control_evidence_and_failed_prefix_reject(self):
        for field in ('controls','residency','tls_snapshots','thread_preparations','hardware_preparation',
                      'environment_samples','environment_preparations','worker_mappings'):
            f=Fixture(self.root);del f.control[field]
            with self.subTest(field=field),self.assertRaises(v.ValidationError):f.run()
        for scheduled in (False,True):
            f=Fixture(self.root,scheduled=scheduled)
            f.control['phases'][1]['consumer_snapshot']['completeness']='SEALED_INCOMPLETE'
            with self.assertRaises(v.ValidationError):f.run()

    def test_warmup_full_keeps_measurement_gate_separate(self):
        for scheduled in (False,True):
            f=Fixture(self.root,scheduled=scheduled,full=(True,False));result=f.run()
            self.assertFalse(result['zero_loss_all_phases']);self.assertTrue(result['measurement_zero_loss'])

    def test_schedule_source_binding_and_positive_exposure_required(self):
        for mutant in ('hash','zero','namespace','unit','mappedlast','finished','mapping'):
            f=Fixture(self.root,scheduled=True)
            if mutant=='hash':f.control['schedules'][1]['prospective']['source_artifact']['sha256']='d'*64
            elif mutant=='zero':f.capture['schedules'][1].update(offered_count=0,deadline_ticks=[])
            elif mutant=='namespace':f.capture['schedules'][1]['namespace_id']=f.capture['schedules'][0]['namespace_id']
            elif mutant=='unit':f.control['schedules'][1]['time_unit']='NANOSECONDS'
            elif mutant=='mapping':f.control['schedule_mapping']['offsets'][1]=f.resources['region_bytes'][0]
            else:
                source=f.control['native_result_before_publication_returns']['session']['schedules'][1]
                if mutant=='mappedlast':source['mapped_last_deadline']+=1000
                else:source['all_arrivals_attempted']=False
                f.sync()
            with self.subTest(mutant=mutant),self.assertRaises(v.ValidationError):f.run()

    def test_raw_reads_are_row_bounded_and_no_joined_file_required(self):
        f=Fixture(self.root);original=v.raw._HashedStream.read;sizes=[]
        def read(stream,size):sizes.append(size);return original(stream,size)
        with patch.object(v.raw._HashedStream,'read',read):f.run()
        self.assertLessEqual(max(sizes),v.codec.row_layout(f.capture['measurement']['run_id'])[1])
        self.assertFalse(any('joined' in p.name for p in self.root.iterdir()))

if __name__=='__main__':unittest.main()
