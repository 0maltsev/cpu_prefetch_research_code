"""Small independent byte fixtures; no hardware or family qualification claim."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_q16a_capture_validation_v1 as v
import check_stage17_discovery_validation_v3 as evidence
import check_stage17_discovery_v2 as plans


def sample(tick):
    return dict(absolute_nanoseconds=1_000_000+tick//1000, relative_picoseconds=tick)


def clock(tick): return dict(status=0, **sample(tick))


class Fixture:
    def __init__(self, root, *, full=False):
        self.root = root
        cap = v.common.contract.validate_plan(plans.fixture()).captures[0]
        self.cap = cap
        self.control,self.final,self.resources,self.monitoring,self.hardware = evidence.capture_fixture(root, cap)
        self.capture = dict(schema_version='cpu-prefetch-stage17-formal-ring-capture/1', method_id=v.demand.METHOD_ID,
            package='R0', ordinal=cap.ordinal, context_ordinal=cap.context_ordinal, repetition_ordinal=0,
            hardware_state=cap.hardware_state, placement=cap.placement, working_set_class=cap.working_set_class,
            warmup_ns=5_000_000_000, measurement_ns=cap.measurement_ns, minimum_observations_per_series=1,
            geometry=dataclasses.asdict(cap.geometry), warmup=dataclasses.asdict(cap.warmup),
            measurement=dataclasses.asdict(cap.measurement), arena_seed=dataclasses.asdict(cap.arena_seed),
            seed_use='ONE_PERSISTENT_ARENA_MEASUREMENT_SEED_WARMUP_RESERVED_NO_DRAWS',
            budget=dict(phases=[dict(producer_attempt_limit=16, consumer_poll_limit=16, drain_ns=1_000_000)]*2,
                        barrier_poll_limit=1000, memory_bytes=1<<30))
        self.resources['phase_capacity'] = [dict(producer_primary_rows=16,consumer_primary_rows=16,
            producer_demand_rows=16,consumer_demand_rows=16) for _ in range(2)]
        self.rows = {}
        old_session = self.control['session']
        phases = []
        states = []
        for i,name in enumerate(('warmup','measurement')):
            begin = old_session['origins'][i]
            duration = (5_000_000_000 if i == 0 else cap.measurement_ns)*1000
            phase,state = self.phase(i,name,begin,duration,full[i] if isinstance(full,tuple) else full)
            phases.append(phase); states.append(state)
            for row in self.control['residency']:
                if row['request']['phase'] == i and row['request']['moment'] == 2:
                    tick=begin+duration+300000+row['request']['region_index']*2000
                    row.update(begin=clock(tick),end=clock(tick+1000))
        session = dict(stop=1,clock_origin=dict(absolute_nanoseconds=1_000_000),prepared=[True,True],
                       private_reset=[True,True],queue_reset=True,phases=states)
        pre = {name:copy.deepcopy(self.control[name]) for name in
               ('clock_origin','core_mapping','monitor_mapping','controller_stack')}
        pre.update(stop=14,session=session,publication_attempted=True,publication_succeeded=False,
                   worker_mappings=None,worker_stacks=None)
        self.final.update(stop=14,session=copy.deepcopy(session))
        self.control.update(schema_version=v.CONTROL_ID,method_id=v.demand.METHOD_ID,
            minimum_observations_per_series=1,native_result_before_publication_returns=pre,
            phases=phases,inferential_validity_established=False)
        for name in ('diagnostic_only','capture_stop_before_publication','session','clock_origin',
                     'publication_attempted','publication_succeeded','core_mapping','monitor_mapping','controller_stack'):
            self.control.pop(name)

    def phase(self,i,name,begin,duration,full):
        identity=self.capture[name]; run_id=identity['run_id']; end=begin+duration
        arena=v.common.Arena(self.cap)
        producers=[];consumers=[];pd=[];cd=[];accepted=0;checksum=17
        def demand_row(ordinal,outcome,advanced,before,after):
            return [ordinal,outcome,advanced if outcome==0 else 0,0,1_000_000+before//1000,before,
                    0,1_000_000+after//1000,after]
        for logical in range(4):
            index=arena.order[logical%len(arena.order)];t=begin+1000+logical*10000
            is_full=full and logical==1
            p=[logical,index,t]
            for tick in (t,t+1000,t+2000,0 if is_full else t+3000,t+4000):
                p.extend([0,0] if tick==0 else [1_000_000+tick//1000,tick])
            p.extend([0 if is_full else accepted,1 if is_full else 15]);producers.append(p)
            pd.append(demand_row(logical,1 if is_full else 0,accepted,t+2000,t+3000))
            if not is_full:
                ct=end+200000 if logical==3 else t+5000
                c=[accepted,index]
                for tick in (ct,ct+1000,ct+2000,ct+3000):c.extend([1_000_000+tick//1000,tick])
                consumers.append(c)
                cd.append(demand_row(len(cd),0,accepted,ct,ct+1000))
                accepted+=1;checksum=v.common.mix(checksum,index,arena.payload[index])
        cd.append(demand_row(len(cd),2,0,end+210000,end+211000))
        counts=dict(requests=4,attempted=4,accepted=accepted,full=int(full),polls=len(cd),empty=1,consumed_including_drain=accepted)
        prefix,pb,cb,jb=v.codec.row_layout(run_id)
        phase=dict(counts,producer_available=True,consumer_available=True,producer_prefix_complete=True,consumer_prefix_complete=True,
            producer_stopped=False,consumer_stopped=False,checksum=checksum,initial_checksum=17,
            consumer_last_join=dict(status=1,matched=accepted,failed_producer_row=None))
        window=dict(clock_suite_id=v.raw.CLOCK_SUITE_ID,time_unit=v.raw.TIME_UNIT,ticks_per_second=10**12,
                    clock_origin_absolute_nanoseconds=1_000_000,phase_origin=sample(begin),duration_ticks=duration)
        for role,primary,drows,kind,rb in (('producer',producers,pd,0,pb),('consumer',consumers,cd,1,cb)):
            phase[role+'_layout']=dict(run_id_bytes=len(run_id.encode()),prefix_bytes=prefix,producer_row_bytes=pb,consumer_row_bytes=cb,joined_row_bytes=jb)
            for suffix,rows,words in (('',primary,15 if kind==0 else 10),('_demand',drows,9)):
                key=role+suffix;row_bytes=prefix+words*8
                path=self.root/f'{name}-{key}.bin'
                encoded=run_id.encode();header=struct.pack('<I',len(encoded))+encoded+bytes((-4-len(encoded))%8)
                path.write_bytes(b''.join(header+struct.pack('<'+str(words)+'Q',*r) for r in rows))
                self.rows[(i,key)]=rows
                phase[key]=dict(file_name=path.name,size_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    role='Q16A_DEMAND_RAW' if suffix else 'Q16A_PRIMARY_RAW',schema_identity=v.demand.FORMAT_ID if suffix else v.codec.FORMAT_ID)
                phase[key+'_snapshot']=dict(run_id=run_id,row_count=len(rows),row_capacity=16,row_bytes=row_bytes,
                    completeness='SEALED_COMPLETE',overflowed=False,retained_bytes=len(rows)*row_bytes)
                phase[key+'_snapshot'].update(dict(format_id=v.demand.FORMAT_ID,worker=kind) if suffix else dict(stream_kind=kind))
                phase[role+'_last_'+('demand' if suffix else 'primary')+'_append']=0
            artifact=phase[role+'_demand']
            phase[role+'_demand_contract']=dict(schema_version=v.demand.CONTRACT_ID,method_id=v.demand.METHOD_ID,physical_format=v.demand.FORMAT_ID,
                run_id=run_id,role=role,phase=name,phase_window=window,minimum_observations_per_series=None if i==0 else 1,
                stream=dict(path=artifact['file_name'],size_bytes=artifact['size_bytes'],sha256=artifact['sha256'],row_count=len(drows)))
        p=producers[-1];outcome=pd[-1][1]
        primary=dict(logical_sequence=p[0],record_index=p[1],scheduled_arrival=p[2],outcome=outcome,accepted_ordinal=p[13])
        pc=dict(capture=dict(outcome=outcome,before_status=0,after_status=0,operation_outcome=outcome,operation_performed=True,failed_clock_status=None),
            failed_boundary=None,requested_attempt=dict(logical_sequence=p[0],scheduled_arrival=p[2],candidate_accepted_ordinal=p[13]),
            selected=dict(record_index=p[1],record_address=0x100000+p[1]*64),demand_before=clock(pd[-1][5]),demand_after=clock(pd[-1][8]))
        for a,b,offset in (('handle_begin','producer_handle_begin',3),('lookup_completion','record_lookup_completion',5),
                          ('enqueue_invocation','enqueue_invocation',7),('enqueue_publication','enqueue_linearization',9),
                          ('enqueue_completion','enqueue_attempt_completion',11)):
            primary[b]=sample(p[offset+1]);pc[a]=clock(p[offset+1])
        pc['primary']=primary
        cc=dict(capture=dict(outcome=2,before_status=0,after_status=0,operation_outcome=2,operation_performed=True,failed_clock_status=None),
            failed_boundary=None,candidate_consumed_ordinal=accepted,dequeue_invocation=clock(end+210000),
            demand_before=clock(cd[-1][5]),demand_after=clock(cd[-1][8]),operation=dict(status=1,event_address=None))
        cc.update({key:None for key in ('primary','dequeue_observation','dequeue_completion','action_completion','access')})
        phase.update(producer_current=pc,consumer_current=cc)
        state=dict(origin_status=0,observed_origin=begin,origin_sample=sample(begin),drain_checkpoint=clock(end+400000),
            window=dict(origin_ticks=begin,duration_ticks=duration,producer_deadline_ticks=end,drain_deadline_ticks=end+1_000_000_000),
            producer=dict(last_clock_status=0,last_observed_tick=end,attempted=4,accepted=accepted,full=int(full),deadline_reached=True,arrivals_finished_published=True),
            consumer=dict(last_clock_status=0,last_observed_tick=end+220000,consumed_including_drain=accepted,polls=len(cd),empty=1,drained=True),
            released=True,before_observed=True,during_observed=True,after_observed=True,validated=True)
        return phase,state

    def run(self):
        return v.validate_capture(self.root,self.control,self.final,self.capture,self.resources,self.monitoring,self.hardware)

    def save_rows(self,index,key):
        phase=self.control['phases'][index];artifact=phase[key]
        run_id=self.capture[('warmup','measurement')[index]]['run_id'];encoded=run_id.encode()
        prefix=struct.pack('<I',len(encoded))+encoded+bytes((-4-len(encoded))%8)
        rows=self.rows[(index,key)];words=9 if key.endswith('_demand') else 15 if key=='producer' else 10
        path=self.root/artifact['file_name'];path.write_bytes(b''.join(prefix+struct.pack('<'+str(words)+'Q',*row) for row in rows))
        artifact.update(size_bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if key.endswith('_demand'):
            phase[key+'_contract']['stream'].update(size_bytes=artifact['size_bytes'],sha256=artifact['sha256'])


class CaptureValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)

    def test_complete_capture_and_full_separate_gate(self):
        for full in (False,True):
            f=Fixture(self.root,full=full);report=f.run()
            self.assertTrue(report['raw_reconciliation_validated'])
            self.assertTrue(report['capture_execution_evidence_validated'])
            self.assertEqual(report['zero_loss_all_phases'],not full)
            self.assertEqual(report['measurement_zero_loss'],not full)
            self.assertFalse(report['family_validity_established'])
            self.assertFalse(report['execution_authority'])
            measured=report['phases'][1]
            self.assertEqual(measured['counts']['accepted'],4-int(full))
            self.assertEqual(measured['demand']['producer']['demand_p999']['value_ticks'],1000)
            self.assertEqual(measured['demand']['consumer']['counts']['outside_demand'],2)
            self.assertIsNone(report['phases'][0]['demand']['producer']['demand_p999'])

    def test_warmup_full_does_not_relabel_measurement_zero_loss(self):
        for outcomes in ((True,False),(False,True)):
            report=Fixture(self.root,full=outcomes).run()
            self.assertTrue(report['raw_reconciliation_validated'])
            self.assertFalse(report['zero_loss_all_phases'])
            self.assertEqual(report['measurement_zero_loss'],not outcomes[1])
            self.assertEqual([p['zero_loss'] for p in report['phases']],[not x for x in outcomes])
            self.assertNotIn('zero_loss',report)

    def test_each_critical_evidence_missing_rejects_before_quantiles(self):
        paths=[('control','native_result_before_publication_returns'),
            ('control','worker_preparation'),('control','thread_preparations'),('control','tls_snapshots'),
            ('control','hardware_preparation'),('control','controls'),('control','residency'),
            ('control','environment_preparations'),('control','environment_samples'),
            ('control','native_result_before_publication_returns','clock_origin'),
            ('control','native_result_before_publication_returns','session','prepared'),
            ('control','native_result_before_publication_returns','session','private_reset'),
            ('control','native_result_before_publication_returns','session','queue_reset'),
            ('control','native_result_before_publication_returns','session','phases',0,'origin_sample'),
            ('control','native_result_before_publication_returns','session','phases',0,'drain_checkpoint'),
            ('control','native_result_before_publication_returns','session','phases',1,'window'),
            ('final','worker_mappings',0,'unmap'),('final','worker_mappings',1,'unlock'),
            ('final','worker_mappings',2,'cleanup_attempted'),('final','worker_stacks',0,'unmap'),
            ('final','worker_stacks',1,'unmap'),('final','controller_stack','unmap'),
            ('final','core_mapping','unmap'),('final','monitor_mapping','unmap'),
            ('final','publication_succeeded'),('control','controls',3,'hardware','cpus',0,'raw_bytes')]
        base=Fixture(self.root)
        for path in paths:
            f=copy.copy(base);f.control=copy.deepcopy(base.control);f.final=copy.deepcopy(base.final)
            target=getattr(f,path[0])
            for key in path[1:-1]: target=target[key]
            del target[path[-1]]
            # Do not let pre/final inequality mask a missing actual prerequisite.
            if path[:3] == ('control','native_result_before_publication_returns','session'):
                f.final['session']=copy.deepcopy(f.control['native_result_before_publication_returns']['session'])
            with self.subTest(path=path),patch.object(v.demand,'decode',side_effect=AssertionError('quantiles ran early')):
                with self.assertRaises(v.ValidationError):f.run()

    def test_actual_session_flags_cannot_be_manufactured_by_projection(self):
        for key,bad in (('prepared',[True,False]),('private_reset',[False,True]),('queue_reset',False),('stop',16)):
            f=Fixture(self.root)
            f.control['native_result_before_publication_returns']['session'][key]=bad
            f.final['session'][key]=copy.deepcopy(bad)
            with self.subTest(key=key),self.assertRaises(v.ValidationError):f.run()

    def test_method_minimum_window_and_phase_bindings(self):
        mutations=[lambda f:f.control.update(method_id='old'),lambda f:f.control.update(minimum_observations_per_series=2),
            lambda f:f.control['phases'][1]['producer_demand_contract'].update(minimum_observations_per_series=2),
            lambda f:f.control['phases'][0]['consumer_demand_contract'].update(phase='measurement'),
            lambda f:f.control['phases'][1]['producer_demand_contract']['phase_window'].update(duration_ticks=1),
            lambda f:f.final.update(stop=12),
            lambda f:f.control['phases'][0]['consumer_snapshot'].update(completeness='SEALED_INCOMPLETE')]
        for mutation in mutations:
            f=Fixture(self.root);mutation(f)
            with self.assertRaises(v.ValidationError):f.run()

    def test_all_eight_hashes_checked_before_quantiles_and_files_untouched(self):
        for index in range(2):
            for key in ('producer','consumer','producer_demand','consumer_demand'):
                f=Fixture(self.root);path=self.root/f.control['phases'][index][key]['file_name']
                original=path.read_bytes();path.write_bytes(original[:-1]+bytes([original[-1]^1]));mutant=path.read_bytes()
                with self.subTest(index=index,key=key),patch.object(v.demand,'decode',side_effect=AssertionError('quantiles ran early')):
                    with self.assertRaises(v.ValidationError):f.run()
                self.assertEqual(path.read_bytes(),mutant)

    def test_demand_primary_ordinal_outcome_bracket_and_clock_mutants(self):
        cases=[('producer_demand',0,2,7),('producer_demand',0,1,1),('producer_demand',0,3,1),
            ('producer_demand',0,4,0),('consumer_demand',0,2,1),('consumer',0,1,999),('producer',0,1,999)]
        for key,row,col,value in cases:
            f=Fixture(self.root);f.rows[(1,key)][row][col]=value;f.save_rows(1,key)
            with self.subTest(key=key,col=col),self.assertRaises(v.ValidationError):f.run()
        f=Fixture(self.root);row=f.rows[(1,'consumer_demand')][0];row[5]+=2000;row[4]+=2;row[8]+=2000;row[7]+=2
        f.save_rows(1,'consumer_demand')
        with self.assertRaises(v.ValidationError):f.run()

    def test_excluded_clock_failure_and_zero_positive_rules(self):
        f=Fixture(self.root);f.rows[(1,'consumer_demand')][-2][3]=1;f.save_rows(1,'consumer_demand')
        with self.assertRaises(v.ValidationError):f.run()
        f=Fixture(self.root);row=f.rows[(1,'producer_demand')][0];row[7:9]=row[4:6];f.save_rows(1,'producer_demand')
        with self.assertRaises(v.ValidationError):f.run()

    def test_warmup_and_excluded_drain_zero_brackets_remain_raw_valid(self):
        f=Fixture(self.root)
        row=f.rows[(0,'producer_demand')][0];row[7:9]=row[4:6];f.save_rows(0,'producer_demand')
        row=f.rows[(1,'consumer_demand')][-2];row[7:9]=row[4:6];f.save_rows(1,'consumer_demand')
        report=f.run()
        self.assertTrue(report['raw_reconciliation_validated'])
        self.assertEqual(report['phases'][1]['demand']['consumer']['demand_p999']['value_ticks'],1000)

    def test_cross_phase_checkpoint_and_actual_origin_regression(self):
        f=Fixture(self.root)
        session=f.control['native_result_before_publication_returns']['session']
        session['phases'][1]['origin_sample']['absolute_nanoseconds']-=1
        f.final['session']=copy.deepcopy(session)
        with self.assertRaises(v.ValidationError):f.run()
        f=Fixture(self.root);session=f.control['native_result_before_publication_returns']['session']
        before=min(r['begin']['relative_picoseconds'] for r in f.control['residency'] if r['request']['phase']==1 and r['request']['moment']==0)
        session['phases'][0]['drain_checkpoint']=clock(before+1000)
        f.final['session']=copy.deepcopy(session)
        with self.assertRaises(v.ValidationError):f.run()

    def test_current_failure_cannot_hide_behind_complete_stream_flags(self):
        for role in ('producer','consumer'):
            f=Fixture(self.root)
            f.control['phases'][1][role+'_current']['capture']['failed_clock_status']=1
            with self.subTest(role=role),self.assertRaises(v.ValidationError):f.run()

    def test_primary_changed_during_quantiles_rejected_without_returned_result(self):
        f=Fixture(self.root);original=v.demand.decode;changed=False
        def decode(root, contract):
            nonlocal changed
            result=original(root,contract)
            if not changed:
                path=self.root/f.control['phases'][0]['producer']['file_name']
                body=path.read_bytes();path.write_bytes(body[:-1]+bytes([body[-1]^1]));changed=True
            return result
        with patch.object(v.demand,'decode',decode),self.assertRaises(v.ValidationError):f.run()

    def test_checksum_arena_and_raw_readback_are_independent(self):
        mutations=[lambda f:f.control['phases'][1].update(checksum=0),
            lambda f:f.control['arena'].update(ordered_index_sha256='0'*64),
            lambda f:f.control['controls'][0]['hardware']['cpus'][0]['raw_bytes'].__setitem__(0,1),
            lambda f:f.control['residency'][0]['page_status'].__setitem__(0,9),
            lambda f:f.control['tls_snapshots'][0].update(fs_base=1)]
        for mutate in mutations:
            f=Fixture(self.root);mutate(f)
            with self.assertRaises(v.ValidationError):f.run()

    def test_symlink_and_duplicate_role_paths_rejected(self):
        f=Fixture(self.root);artifact=f.control['phases'][0]['producer'];path=self.root/artifact['file_name']
        target=self.root/'original';path.rename(target);path.symlink_to(target)
        with self.assertRaises(v.ValidationError):f.run()
        path.unlink();f=Fixture(self.root)
        f.control['phases'][1]['producer']['file_name']=f.control['phases'][0]['producer']['file_name']
        with self.assertRaises(v.ValidationError):f.run()

    def test_bounded_stream_reads_and_small_report(self):
        f=Fixture(self.root);reads=[];original=v.raw._HashedStream.read
        def read(stream,n):
            self.assertGreaterEqual(n,0);self.assertLessEqual(n,256)
            reads.append(n);return original(stream,n)
        with patch.object(v.raw._HashedStream,'read',read):report=f.run()
        self.assertGreater(len(reads),20)
        import json
        self.assertLess(len(json.dumps(report)),15000)


if __name__ == '__main__':
    unittest.main()
