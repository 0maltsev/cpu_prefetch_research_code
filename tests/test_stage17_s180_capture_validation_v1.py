"""Full original-byte software fixtures; no experiment or admission credit."""
import array
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest import mock
from types import SimpleNamespace

import stage17_s180_capture_validation_v1 as v
from test_stage17_s180_capture_controls_v1 import Fixture as ControlFixture

SEED='0000000000000000000000000000000000000000000000000000000000000001'
PLAN='a'*64
SCOPE='b'*64
SESSION='SOFTWARE-S180-CAPTURE-SESSION'


class Fixture(ControlFixture):
    def __init__(self,root,full=False,all_full=False):
        super().__init__(root,full=full)
        self.capture.update(cell_ordinal=0,package='R0',warmup_schedule_namespace='SOFTWARE-S180/WARMUP',
            measurement_schedule_namespace='SOFTWARE-S180/PILOT')
        self.cache=v.ReplayCache();arena,nodes,pattern=self.cache.get(self.capture,SEED,time.monotonic_ns()+10**10)
        self.control['shared_data']['node_pattern']=pattern
        self.control['node_order_count']=len(nodes)
        self.control['node_order']=self.artifact('s180-e0-node-order.bin',struct.pack('<'+'Q'*len(nodes),*nodes),
            'S180_NODE_ORDER','NODEORDER-U64LE-v1')
        g=self.capture['requested_geometry']
        self.control['arena'].update(storage_address=self.control['regions'][7]['address'],
            prepared_content_sha256=arena.hashes[0],publication_content_sha256=arena.hashes[0],
            ordered_index_sha256=arena.hashes[1],address_delta_sha256=arena.hashes[2])
        self.entry=dict(execution_ordinal=0,cell_ordinal=0,resources=self.resources,monitoring=self.monitoring,
            phases=self.bounds,expected_layout=self.expected_layout)
        scheduled=self.control['native_result_before_publication_returns']['session']['scheduled']
        for i,name in enumerate(('warmup','measurement')):
            phase=self.control['phases'][i];state=scheduled['lifecycle']['phases'][i]
            producers=self.rows[(i,'producer')];consumers=self.rows[(i,'consumer')]
            checksum=self.resources['initial_consumer_state'];accepted=0
            for logical,p in enumerate(producers):
                p[1]=arena.order[logical%len(arena.order)]
                if all_full:p[9]=p[10]=p[13]=0;p[14]=1
                if p[14]==15:
                    consumers[accepted][1]=p[1];checksum=v.common.mix(checksum,p[1],arena.payload[p[1]]);accepted+=1
            if all_full:consumers.clear()
            self.rows[(i,'consumer')]=consumers
            phase.update(accepted=accepted,full=len(producers)-accepted,retained_consumed_including_drain=accepted,
                checksum=checksum,polls=accepted+1,empty=1,consumer_last_join=dict(status=1,matched=accepted,failed_producer_row=None))
            state['producer'].update(accepted=accepted,full=len(producers)-accepted)
            state['consumer'].update(consumed_including_drain=accepted,polls=accepted+1,empty=1)
            for role,rows,words in (('producer',producers,15),('consumer',consumers,10)):
                run=self.capture['warmup_run_id' if i==0 else 'run_id'];prefix,_,_,_=v.codec.row_layout(run)
                encoded=run.encode();header=struct.pack('<I',len(encoded))+encoded+bytes(prefix-4-len(encoded))
                data=b''.join(header+struct.pack('<'+'Q'*words,*row) for row in rows)
                phase[role]=self.artifact(f's180-e0-{name}-{role}.bin',data,'S180_PRIMARY_RAW',v.codec.FORMAT_ID)
                phase[role+'_snapshot'].update(row_count=len(rows),retained_bytes=len(data))
            current=phase['producer_current']['observation'];p=producers[-1]
            current.update(record_index=p[1],outcome=0 if p[14]==15 else 1,
                accepted_ordinal=p[13] if p[14]==15 else None,
                enqueue_linearization=dict(absolute_nanoseconds=p[9],relative_picoseconds=p[10]) if p[14]==15 else None)
            source=self.legacy[2]['schedules'][i]
            values=source['deadline_ticks'];raw=struct.pack('<'+'Q'*len(values),*values)
            original=struct.pack('>'+'Q'*len(values),*values)
            self.bounds[i].update(schedule_id='SOFTWARE-'+name+'-schedule',
                source_artifact=dict(artifact_id='SOFTWARE-'+name+'-ORIGINAL',sha256=hashlib.sha256(original).hexdigest()))
            self.control['schedules'][i]['stream']=self.artifact(f's180-e0-{name}-schedule.bin',raw,
                'S180_PREPARED_SCHEDULE','SCHEDULE-DEADLINES-U64LE-v1')
        self.prospective=v.prospective_capture(self.capture,self.entry)
        self.control['prospective_capture']=copy.deepcopy(self.capture)
        for i,row in enumerate(self.control['schedules']):row['prospective']=copy.deepcopy(self.prospective['schedules'][i])
        self.final['session']=copy.deepcopy(self.control['native_result_before_publication_returns']['session'])
        self.checkpoint=dict(schema_version=v.checkpoint_contract.SCHEMA,session_id=SESSION,plan_sha256=PLAN,
            program_scope_sha256=SCOPE,execution_ordinal=0,native_complete=True,native_result_after_private_cleanup=self.final,
            artifacts=[],shared_data_still_family_owned=True,scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False)
        self.refresh()

    def refresh(self):
        control=self.artifact('s180-e0-control.json',json.dumps(self.control,separators=(',',':')).encode(),
            'S180_CAPTURE_CONTROL',v.controls.CONTROL)
        artifacts=[self.control['phases'][i][role] for i in range(2) for role in ('producer','consumer')]
        artifacts+=[self.control['node_order'],*(r['stream'] for r in self.control['schedules']),control]
        self.checkpoint['artifacts']=[dict(a,media_type='application/json' if a is control else 'application/octet-stream') for a in artifacts]

    def validate(self,candidates,**kwargs):
        args=dict(checkpoint=self.checkpoint,capture=self.capture,entry=self.entry,hardware=self.hardware,
            master_seed_hex=SEED,family_context_cleanup=self.cleanup,candidates=candidates,replay_cache=self.cache,
            plan_sha256=PLAN,program_scope_sha256=SCOPE,session_id=SESSION,deadline_ns=time.monotonic_ns()+10**10)
        args.update(kwargs);return v.validate_capture(self.root,**args)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='s180-full-software-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.f=Fixture(self.root);self.outputs=[]

    def candidates(self):
        result=[]
        for i in range(2):
            s=tempfile.NamedTemporaryFile('w+b',delete=False);self.addCleanup(s.close)
            self.addCleanup(lambda p=s.name:Path(p).unlink(missing_ok=True));result.append(s)
        return result

    def fails(self,**kwargs):
        with self.assertRaises(v.common.ValidationError):self.f.validate(self.candidates(),**kwargs)

    def test_actual_original_bytes_controls_sources_join_and_numerics(self):
        outputs=self.candidates();r=self.f.validate(outputs)
        self.assertEqual(r['capture_validation_status'],'PASSED');self.assertTrue(r['raw_reconciliation_validated'])
        self.assertTrue(r['immutable_arena_validated']);self.assertTrue(r['node_order_validated'])
        self.assertEqual(r['tail_numerics']['raw_accepted_count'],4)
        self.assertEqual(r['nodes']['count'],513);self.assertTrue(r['measurement_zero_loss'])
        self.assertFalse(r['original_schedule_generation_repeated']);self.assertFalse(r['family_validity_established'])
        for stream,audit in zip(outputs,r['phases'],strict=True):
            stream.seek(0);self.assertEqual(hashlib.sha256(stream.read()).hexdigest(),audit['joined_sha256'])

    def test_full_and_all_full_are_valid_with_separate_zero_loss_and_undefined_tail(self):
        for all_full in (False,True):
            self.f=Fixture(self.root,full=True,all_full=all_full);r=self.f.validate(self.candidates())
            self.assertFalse(r['measurement_zero_loss']);self.assertEqual(r['capture_validation_status'],'PASSED')
            self.assertEqual(r['tail_numerics']['raw_accepted_count'],0 if all_full else 3)
            self.assertIsNone(r['tail_numerics']['primary_tail']['effective_count'])

    def test_source_corruption_cannot_pass_by_rebinding_publication_hash(self):
        row=self.f.control['schedules'][1]['stream'];path=self.root/row['file_name']
        data=bytearray(path.read_bytes());data[0]^=1;path.write_bytes(data)
        row['sha256']=hashlib.sha256(data).hexdigest();self.f.refresh();self.fails()

    def test_node_permutation_and_summary_are_independent_even_for_ring(self):
        row=self.f.control['node_order'];p=self.root/row['file_name'];raw=p.read_bytes()
        p.write_bytes(raw[8:16]+raw[:8]+raw[16:]);row['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        self.f.refresh();self.fails()
        self.f=Fixture(self.root);self.f.control['shared_data']['node_pattern']['modal_nonzero_delta_count']+=1
        self.f.refresh();self.fails()

    def test_arena_content_order_seed_and_shared_record_address_are_independent(self):
        for mutation in ('content','order','address','seed'):
            self.f=Fixture(self.root)
            if mutation=='content':self.f.control['arena']['publication_content_sha256']='0'*64
            elif mutation=='order':self.f.control['arena']['ordered_index_sha256']='0'*64
            elif mutation=='address':self.f.control['arena']['storage_address']=self.f.control['regions'][0]['address']
            self.f.refresh();self.fails(**({'master_seed_hex':'2'*64} if mutation=='seed' else {}))

    def test_primary_mutation_rebinding_still_fails_join_and_precedes_numerics(self):
        row=self.f.control['phases'][1]['consumer'];path=self.root/row['file_name'];data=bytearray(path.read_bytes())
        prefix,_,_,_=v.codec.row_layout(self.f.capture['run_id']);data[prefix]^=1;path.write_bytes(data)
        row['sha256']=hashlib.sha256(data).hexdigest();self.f.refresh()
        with mock.patch.object(v.tails,'analyze',side_effect=AssertionError('must not analyze failed raw')):self.fails()

    def test_native_current_checksum_counts_and_snapshot_cannot_replace_raw(self):
        for mutation in ('current','checksum','count','snapshot'):
            self.f=Fixture(self.root);p=self.f.control['phases'][1]
            if mutation=='current':p['producer_current']['observation']['record_index']+=1
            elif mutation=='checksum':p['checksum']^=1
            elif mutation=='count':p['accepted']+=1
            else:p['consumer_snapshot']['overflowed']=True
            self.f.refresh();self.fails()

    def test_checkpoint_identity_and_complete_eight_artifacts_are_mandatory(self):
        for mutation in ('plan','complete','missing','role'):
            self.f=Fixture(self.root)
            if mutation=='plan':self.f.checkpoint['plan_sha256']='0'*64
            elif mutation=='complete':self.f.checkpoint['native_complete']=False
            elif mutation=='missing':self.f.checkpoint['artifacts'].pop()
            else:self.f.checkpoint['artifacts'][0]['role']='Q16C_PRIMARY_RAW'
            self.fails()

    def test_original_control_hash_duplicate_key_and_symlink_reject(self):
        for mutation in ('hash','duplicate','symlink'):
            self.f=Fixture(self.root);ref=self.f.checkpoint['artifacts'][-1];path=self.root/ref['file_name']
            if mutation=='hash':path.write_bytes(path.read_bytes()+b' ')
            elif mutation=='duplicate':
                raw=path.read_bytes();raw=b'{"execution_authority":false,'+raw[1:];path.write_bytes(raw)
                ref.update(sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
            else:path.rename(self.root/'control-saved');path.symlink_to(self.root/'control-saved')
            self.fails()
            if mutation=='symlink':path.unlink()

    def test_candidate_cross_phase_raw_alias_is_rejected_before_any_write(self):
        self.f=Fixture(self.root,all_full=True);raw=self.root/'s180-e0-measurement-consumer.bin'
        with raw.open('r+b') as alias:
            outputs=self.candidates()
            with self.assertRaises(v.common.ValidationError):self.f.validate((alias,outputs[1]))
        self.assertEqual(raw.read_bytes(),b'')
        outputs=self.candidates()
        with self.assertRaises(v.common.ValidationError):self.f.validate((outputs[0],outputs[0]))

    def test_cached_context_reuse_and_tamper_cannot_regenerate_favorable_data(self):
        with mock.patch.object(v.common,'Arena',side_effect=AssertionError('must reuse exact context')):
            self.assertEqual(self.f.validate(self.candidates())['capture_validation_status'],'PASSED')
        value=next(iter(self.f.cache._entries.values()))[0];value[0].order[0]^=1
        self.fails();value[0].order[0]^=1;self.fails()

    def test_deadline_or_missing_original_source_binding_cannot_return_success(self):
        self.fails(deadline_ns=0)
        self.f.entry['phases'][1]['source_artifact']['sha256']='0'*64
        self.f.refresh();self.fails()

    def test_exact_node_pattern_tie_breaks_negative_delta_and_cyclic_transition(self):
        pattern=v._pattern(array.array('Q',[2,0,3,1]),64,4096,time.monotonic_ns()+10**10)
        self.assertEqual(pattern,dict(transition_count=4,distinct_line_count=4,distinct_page_count=1,shortest_period=4,
            adjacent_line_transition_count=1,modal_nonzero_delta_count=2,modal_nonzero_delta=-128,
            adjacent_fraction_at_most_one_percent=False,modal_fraction_at_most_one_percent=False))

    def test_existing_cpp_arena_golden_checksums_are_preserved(self):
        capture=copy.deepcopy(self.f.capture);capture['requested_geometry']['capacity']=8
        capture['arena_namespace']='stage6-test';capture['node_order_namespace']='stage6-test/nodes'
        arena,_,_=v.ReplayCache().get(capture,'000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f',time.monotonic_ns()+10**10)
        self.assertEqual(arena.hashes,('a14a1bde2dacaf6622af22ccb0b05b3c98b95a40741f9c25e85625ad2e393d60',
            'af670b376e5b3784d7d3fa5fb326fd630d05f2a9d0e8c2fcf1f325232dbfa73b',
            'e36232c7069da78a765c528361837744233ca7ed54554d836bf58e4c9503aa12'))

    def publish(self,output=None,**kwargs):
        if output is None:output=self.root/'analysis'/'capture0'
        output.parent.mkdir(exist_ok=True,mode=0o700)
        # Original-byte root is a sibling, never the output ancestor.
        rawroot=self.root/'originals'
        if not rawroot.exists():
            rawroot.mkdir(mode=0o700)
            for p in list(self.root.glob('s180-e0-*')):p.rename(rawroot/p.name)
        options=dict(checkpoint=self.f.checkpoint,capture=self.f.capture,entry=self.f.entry,hardware=self.f.hardware,
            master_seed_hex=SEED,family_context_cleanup=self.f.cleanup,replay_cache=self.f.cache,
            plan_sha256=PLAN,program_scope_sha256=SCOPE,session_id=SESSION,deadline_ns=time.monotonic_ns()+10**10,
            output_directory=output,maximum_output_bytes=16*1024**2,
            original_locations={name:dict(artifact_uri=(rawroot/name).as_uri(),compression='NONE')
                for name in v.checkpoint_contract.capture_names(0)})
        options.update(kwargs)
        return v.validate_and_publish_capture(rawroot,**options)

    def test_durable_publication_has_both_join_audits_data_and_exact_analysis_bindings(self):
        output=self.root/'analysis'/'capture0';r=self.publish(output)
        self.assertTrue(r['durable_joined_publication_verified']);self.assertFalse(r['aggregate_resource_admission_performed'])
        self.assertFalse(r['full_family_validity_established']);self.assertTrue((output/'complete.json').exists())
        for b in [r['capture_validation'],r['tail_numerics'],*(x['artifact'] for x in r['joined']),*(x['join_audit'] for x in r['joined'])]:
            data=(output/b['file_name']).read_bytes();self.assertEqual(len(data),b['size_bytes'])
            self.assertEqual(hashlib.sha256(data).hexdigest(),b['sha256'])
        from jsonschema import Draft202012Validator
        schema=json.loads((Path(__file__).resolve().parents[1]/'protocol/2.0.0-pre.3/handoff/schemas/raw-observation.schema.json').read_bytes())
        validator=Draft202012Validator(schema)
        for row in r['joined']:
            self.assertEqual(len(row['raw_stream_envelopes']),3)
            envelopes=[json.loads((output/b['file_name']).read_bytes()) for b in row['raw_stream_envelopes']]
            for envelope in envelopes:validator.validate(envelope)
            self.assertEqual(envelopes[2]['source_artifacts'],[
                dict(artifact_id=e['artifact_id'],sha256=e['artifact_sha256']) for e in envelopes[:2]])
        self.assertFalse(r['original_archive_custody_verified'])
        self.assertFalse(any(output.glob('*.pending*')));self.assertFalse((output/'failure.json').exists())
        with self.assertRaises(FileExistsError):self.publish(output)

    def test_failed_publication_retains_partial_candidates_and_never_adopts_directory(self):
        self.f.entry['phases'][1]['source_artifact']['sha256']='0'*64
        output=self.root/'analysis'/'capture0'
        with self.assertRaises(v.common.ValidationError):self.publish(output)
        self.assertTrue((output/'failure.json').exists());self.assertFalse((output/'complete.json').exists())
        self.assertTrue((output/'warmup-joined.pending.bin').exists())
        originals={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.root/'originals').iterdir()}
        with self.assertRaises(FileExistsError):self.publish(output)
        self.assertEqual(originals,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.root/'originals').iterdir()})

    def test_output_budget_and_input_tree_separation_precede_writes(self):
        output=self.root/'analysis'/'capture0'
        with self.assertRaisesRegex(v.common.ValidationError,'output budget'):self.publish(output,maximum_output_bytes=1)
        self.assertFalse(output.exists())
        with self.assertRaisesRegex(v.common.ValidationError,'input tree'):
            self.publish(self.root/'originals'/'wrong')

    def test_late_deadline_failure_preserves_uncommitted_manifest_and_no_success_marker(self):
        output=self.root/'analysis'/'capture0';original=v.before
        def fail_after_marker(deadline):
            if (output/'complete.json').exists():raise v.common.ValidationError('SOFTWARE original analysis deadline expired')
            original(deadline)
        with mock.patch.object(v,'before',side_effect=fail_after_marker):
            with self.assertRaisesRegex(v.common.ValidationError,'deadline expired'):self.publish(output)
        self.assertFalse((output/'complete.json').exists());self.assertTrue((output/'uncommitted-complete.json').exists())
        self.assertEqual(json.loads((output/'failure.json').read_bytes())['status'],'FAILED')

    def test_foreign_output_object_latches_failure_without_deleting_it(self):
        output=self.root/'analysis'/'capture0';original=v.tails.analyze
        def foreign(*args,**kwargs):
            r=original(*args,**kwargs);(output/'foreign-evidence').write_bytes(b'keep');return r
        with mock.patch.object(v.tails,'analyze',side_effect=foreign):
            with self.assertRaisesRegex(v.common.ValidationError,'unexpected object'):self.publish(output)
        self.assertEqual((output/'foreign-evidence').read_bytes(),b'keep');self.assertFalse((output/'complete.json').exists())

    def test_fd_protection_does_not_depend_on_path_chmod_kernel_flags(self):
        with mock.patch.object(v.os,'chmod',side_effect=NotImplementedError('SOFTWARE unsupported path chmod flags')):
            r=self.publish()
        self.assertTrue(r['durable_joined_publication_verified'])

    def test_original_same_byte_mutation_during_analysis_invalidates_entire_capture(self):
        path=self.root/'s180-e0-warmup-producer.bin';original=v.tails.analyze
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            with path.open('r+b',buffering=0) as stream:first=stream.read(1);stream.seek(0);stream.write(first)
            return result
        with mock.patch.object(v.tails,'analyze',side_effect=changed):self.fails()


if __name__=='__main__':unittest.main()
