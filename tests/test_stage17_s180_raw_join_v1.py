"""Disjoint software fixtures; no stand observations or pilot validity credit."""
import array
import copy
import hashlib
import io
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest import mock

import stage17_s180_raw_join_v1 as join
import stage17_s180_tail_numerics_v1 as tail


class JoinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='s180-primary-software-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.order=array.array('Q',[1,0]);self.payload=array.array('Q',[77,88])
        self.fixture()

    def fixture(self,phase='MEASUREMENT',full=(1,),count=4):
        self.run='SOFTWARE-S180-RAW-PHASE';self.phase=phase
        duration=10**12 if phase=='MEASUREMENT' else 5*10**12
        self.start=100000;self.origin=1000;self.source_origin=5000
        self.schedule=array.array('Q',[self.source_origin+x for x in
            ([1000,2000,3000,duration-1000] if count else [])])
        self.p=[];self.q=[];checksum=3;previous_p=previous_q=self.start;accepted=0
        def clock(t):return self.origin+t//1000,t
        for logical,tick in enumerate(self.schedule):
            due=self.start+tick-self.source_origin;b=max(due,previous_p);r=b+4000
            record=self.order[logical%2]
            p=[logical,record,due,*clock(b),*clock(b+1000),*clock(b+2000),
                *clock(b+3000),*clock(r),accepted,15]
            if logical in full:p[9]=p[10]=p[13]=0;p[14]=1
            else:
                v=max(r,previous_q);q=[accepted,record,*clock(v),*clock(v+1000),*clock(v+2000),*clock(v+3000)]
                self.q.append(q);checksum=join.mix(checksum,record,self.payload[record]);accepted+=1;previous_q=v+3000
            self.p.append(p);previous_p=r
        self.contract=dict(schema_version=join.CONTRACT,run_id=self.run,phase=phase,
            clock_origin_absolute_nanoseconds=self.origin,phase_origin_relative_picoseconds=self.start,
            duration_ticks=duration,drain_deadline_ticks=self.start+duration+100000,
            source_origin_ticks=self.source_origin,source_horizon_ticks=self.source_origin+duration,
            maximum_offered=100,initial_checksum=3,expected_checksum=checksum,streams={})
        self.write_inputs()

    def write_inputs(self):
        prefix,pb,cb,jb=join.codec.row_layout(self.run);encoded=self.run.encode()
        self.prefix=struct.pack('<I',len(encoded))+encoded+bytes(prefix-4-len(encoded))
        for role,rows,words in (('producer',self.p,15),('consumer',self.q,10)):
            data=b''.join(self.prefix+struct.pack('<'+'Q'*words,*r) for r in rows)
            path=self.root/(role+'.bin');path.write_bytes(data)
            self.contract['streams'][role]=dict(path=path.name,size_bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),row_count=len(rows))

    def call(self,**overrides):
        options=dict(record_order=self.order,payloads=self.payload,schedule_ticks=self.schedule,
            candidate=self.output,deadline_ns=time.monotonic_ns()+10**10)
        options.update(overrides)
        return join.derive_phase(self.root,self.contract,**options)

    def candidate(self):
        self.output=tempfile.NamedTemporaryFile('w+b',dir=self.root,delete=False);self.addCleanup(self.output.close)

    def fails(self,text=None,**kwargs):
        with self.assertRaises(join.JoinError) as caught:self.call(**kwargs)
        if text:self.assertIn(text,str(caught.exception))
        self.assertEqual(caught.exception.audit['join_status'],'FAILED')
        self.assertFalse(caught.exception.audit['successful_joined_dataset'])

    def test_all_arrivals_full_repeating_index_drain_and_exact_joined_rows(self):
        self.candidate();audit,latencies=self.call()
        self.assertEqual((audit['offered_count'],audit['accepted_count'],audit['full_count']),(4,3,1))
        self.assertEqual(audit['zero_loss_status'],'FAIL');self.assertEqual(len(latencies),3)
        self.assertGreater(self.q[-1][9],self.start+10**12)
        self.output.seek(0);_,_,_,jb=join.codec.row_layout(self.run)
        rows=[join.codec._row(self.output,jb,self.run,24,'software joined') for _ in range(3)]
        self.assertEqual([r[0] for r in rows],[0,1,2]);self.assertEqual([r[1] for r in rows],[0,2,3])
        self.assertEqual([r[2] for r in rows],[1,1,0])
        self.assertEqual(rows[0],(0,0,1,0,0,101000,101000,102000,103000,104000,105000,
            105000,106000,107000,108000,0,1000,2000,3000,2000,2000,2000,1000,7000))
        self.assertEqual([r[-1] for r in rows],list(latencies))
        for row in rows:self.assertEqual(row[18]+row[19]+row[21],row[23])
        self.assertFalse(audit['run_validity_assessed']);self.assertFalse(audit['successful_joined_dataset_published'])
        self.assertEqual(tail.analyze(latencies,maximum_samples=100,deadline_ns=time.monotonic_ns()+10**10)['raw_accepted_count'],3)

    def test_warmup_reconciles_all_rows_but_never_supplies_measurement_latencies(self):
        self.fixture(phase='WARMUP');self.candidate();audit,latencies=self.call()
        self.assertEqual(audit['accepted_count'],3);self.assertEqual(list(latencies),[])
        self.assertGreater(audit['joined_size_bytes'],0)

    def test_response_overlap_does_not_replace_linearization_boundaries(self):
        self.p=self.p[:1];self.q=self.q[:1];self.schedule=self.schedule[:1]
        self.p[0][12]=self.q[0][9]+1000;self.p[0][11]=self.origin+self.p[0][12]//1000
        self.contract['expected_checksum']=join.mix(3,1,88);self.write_inputs();self.candidate()
        audit,values=self.call();self.assertEqual(audit['accepted_count'],1)
        self.assertEqual(list(values),[7000])

    def test_same_byte_primary_mutation_during_read_fails_stamp_check(self):
        original=join.codec._row;changed=False;path=self.root/'producer.bin'
        def mutate(*args):
            nonlocal changed
            result=original(*args)
            if not changed:
                changed=True
                with path.open('r+b',buffering=0) as stream:first=stream.read(1);stream.seek(0);stream.write(first)
            return result
        self.candidate()
        with mock.patch.object(join.codec,'_row',side_effect=mutate):self.fails('changed during read')

    def test_empty_and_all_full_remain_correct_separate_zero_loss_data(self):
        for full,count in (((),0),((0,1,2,3),4)):
            self.fixture(full=full,count=count);self.candidate();audit,values=self.call()
            self.assertEqual(audit['accepted_count'],0);self.assertEqual(list(values),[])
            self.assertEqual(audit['joined_sha256'],hashlib.sha256(b'').hexdigest())
            self.assertEqual(audit['zero_loss_status'],'PASS' if not count else 'FAIL')

    def test_accepted_ordinal_and_record_index_are_checked_independently(self):
        for i in (0,1):
            self.fixture();self.q[1][i]=0;self.write_inputs();self.candidate();self.fails('ordinal/record')

    def test_full_has_no_fabricated_publication_or_consumer(self):
        self.p[1][9]=self.origin;self.write_inputs();self.candidate();self.fails('FULL contains')

    def test_missing_extra_reordered_and_duplicate_rows_fail_after_hash_rebinding(self):
        for mutation in ('missing','extra','reorder','duplicate'):
            self.fixture()
            if mutation=='missing':self.q.pop()
            elif mutation=='extra':self.q.append(self.q[-1][:])
            elif mutation=='reorder':self.q[0],self.q[1]=self.q[1],self.q[0]
            else:self.q[1]=self.q[0][:]
            self.write_inputs();self.candidate();self.fails()

    def test_absolute_clock_conversion_publication_crossrow_and_drain_boundaries(self):
        for mutation in ('clock','publication','producer_order','consumer_order','drain'):
            self.fixture()
            if mutation=='clock':self.p[0][3]+=1
            elif mutation=='publication':self.q[0][5]=self.p[0][10]-1000;self.q[0][4]=self.origin+self.q[0][5]//1000
            elif mutation=='producer_order':self.p[2][4]=self.p[0][12]-1000;self.p[2][3]=self.origin+self.p[2][4]//1000
            elif mutation=='consumer_order':self.q[1][3]=self.q[0][9]-1000;self.q[1][2]=self.origin+self.q[1][3]//1000
            else:self.contract['drain_deadline_ticks']=self.q[-1][9]
            self.write_inputs();self.candidate();self.fails()

    def test_original_schedule_translation_and_horizon_are_not_inferred_from_raw(self):
        for mutation in ('translation','order','endpoint'):
            self.fixture()
            if mutation=='translation':self.schedule[0]+=1000
            elif mutation=='order':self.schedule[1]=self.source_origin
            else:self.schedule[-1]=self.source_origin+10**12
            self.candidate();self.fails()

    def test_payload_corruption_count_and_repeating_arena_order_fail(self):
        self.candidate();self.fails('checksum',payloads=array.array('Q',[77,89]))
        self.candidate();self.fails('permutation',record_order=array.array('Q',[1,1]))
        self.candidate();self.fails('sequence',record_order=array.array('Q',[0,1]))
        self.candidate();self.fails('per offered',schedule_ticks=array.array('Q',self.schedule[:-1]))

    def test_raw_hash_padding_run_identity_and_trailing_bytes_fail(self):
        path=self.root/'producer.bin'
        for mutation in ('hash','padding','run','trailing'):
            self.fixture();data=bytearray(path.read_bytes())
            if mutation=='hash':data[-1]^=1
            elif mutation=='padding':data[len(self.prefix)-1]=1
            elif mutation=='run':data[4]^=1
            else:data+=b'x'
            path.write_bytes(data)
            if mutation in ('padding','run'):self.contract['streams']['producer']['sha256']=hashlib.sha256(data).hexdigest()
            self.candidate();self.fails()

    def test_symlink_paths_same_physical_inputs_and_output_alias_are_rejected(self):
        path=self.root/'producer.bin';saved=self.root/'saved.bin';path.rename(saved);path.symlink_to(saved)
        self.candidate();self.fails()
        path.unlink();saved.rename(path)
        self.fixture(count=0);(self.root/'consumer.bin').unlink();os.link(path,self.root/'consumer.bin')
        self.candidate();self.fails('physical input/output alias')
        (self.root/'consumer.bin').unlink();(self.root/'consumer.bin').write_bytes(b'')
        os.chmod(path,0o600)
        with path.open('r+b') as output:self.fails('physical input/output alias',candidate=output)

    def test_candidate_must_be_fresh_private_regular_and_reconstructed(self):
        self.candidate();self.output.write(b'x');self.output.flush();self.output.seek(0);self.fails('fresh private')
        self.fails('candidate',candidate=io.BytesIO())
        self.candidate();os.fchmod(self.output.fileno(),0o666);self.fails('fresh private')
        self.candidate();original=self.output.read
        with mock.patch.object(self.output,'read',side_effect=lambda n:bytes(n) if n>0 else original(n)):
            self.fails('reconstructed bytes')

    def test_deadline_expiry_never_returns_success(self):
        self.candidate();self.fails('deadline expired',deadline_ns=0)
        self.candidate();original=join.before;calls=0
        def expired(deadline):
            nonlocal calls
            calls+=1
            if calls==10:raise join.JoinError('original analysis deadline expired')
            original(deadline)
        with mock.patch.object(join,'before',side_effect=expired):self.fails('deadline expired')

    def test_contract_types_bounds_unknown_fields_and_float_values_fail(self):
        original=copy.deepcopy(self.contract)
        for key,value in (('phase','OTHER'),('duration_ticks',1),('maximum_offered',True),
                ('maximum_offered',join.MAX_MEASUREMENT+1),('expected_checksum',3.0),
                ('clock_origin_absolute_nanoseconds',join.U64),('extra',1)):
            self.contract=copy.deepcopy(original);self.contract[key]=value;self.candidate();self.fails()
        self.contract=original;self.candidate();self.fails('packed',payloads=[77,88])


if __name__=='__main__':unittest.main()
