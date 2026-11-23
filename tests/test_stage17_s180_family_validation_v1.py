"""Synthetic family metadata contracts, not a collected pilot or admission.

Templates come through the actual D350 software-fixture pipeline. Expanding
their metadata exercises whole-family relationships; it does not manufacture
180 actual raw validations or execute/qualify the frozen prospective design.
"""
import copy
import hashlib
import json
from pathlib import Path
import time
import unittest

import stage17_s180_family_validation_v1 as v
import test_stage17_s180_capture_validation_v1 as prior
from test_stage17_s180_plan_prepare_v1 import fixture as plan_fixture
from test_stage17_s180_capture_controls_v1 import old

REQUEST='c'*64
SESSION='SOFTWARE-ONLY-FAMILY-CONTRACT'


def template(all_full=False):
    case=prior.CaptureTests();case.setUp()
    try:
        if all_full:case.f=prior.Fixture(case.root,all_full=True)
        publication=case.publish();root=case.root/'analysis'/'capture0'
        return dict(report=json.loads((root/'capture-validation.json').read_bytes()),checkpoint=copy.deepcopy(case.f.checkpoint),
            publication=publication,envelopes=[json.loads((root/b['file_name']).read_bytes())
                for row in publication['joined'] for b in row['raw_stream_envelopes']])
    finally:case.doCleanups()


def family_fixture(base):
    plan=plan_fixture('a'*40);plan['schema_version']=v.planning.PLAN;plan.pop('source_count_basis')
    rows=sorted(plan['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
    shared={};cleanups=[]
    for index,context in enumerate(v.CONTEXTS):
        row=next(r for r in rows if (r['placement'],r['working_set_class'])==context)
        g=row['requested_geometry'];page=g['base_page_bytes'];capacity=g['capacity'];line=g['cache_line_bytes']
        sizes=[((capacity*(line+8)+page-1)//page)*page,(((capacity+1)*line+16384+page-1)//page)*page]
        source=copy.deepcopy(base['report']['control_evidence']['shared_data']);maps=[];cleanup={}
        for i,name in enumerate(('records','queues')):
            address=0x10000000000+index*0x1000000000+i*0x80000000
            p=dict(bytes=sizes[i],verified_base_page_bytes=page,owner_cpu=g['producer_cpu'],requested_node=g['shared_node'])
            m=old.qfixture.evidence.mapping(p,address,201);maps.append(m);cleanup[name]=copy.deepcopy(m)
            cleanup[name].update(cleanup_attempted=True,unlock=old.qfixture.evidence.call(),unmap=old.qfixture.evidence.call())
        source.update(mappings=maps,**{k:row[k] for k in ('placement','working_set_class','arena_namespace','node_order_namespace')})
        q=maps[1]['mapping']['address'];source.update(arena_object=q,ring_object=q+64,linked_object=q+128,node_bytes=q+4096)
        count=capacity+1;source['node_pattern'].update(transition_count=count,distinct_line_count=count,shortest_period=count,
            distinct_page_count=(count*line+page-1)//page)
        shared[context]=(source,sizes);cleanups.append(cleanup)
    plan_sha=None;records=[]
    for ordinal,(row,entry) in enumerate(zip(rows,plan['captures'],strict=True)):
        layout=copy.deepcopy(base['report']['control_evidence']['regions'])
        source,sizes=shared[row['placement'],row['working_set_class']]
        # These are explicit synthetic metadata sizes, not a qualified native
        # layout or physical first-touch result for this prospective capture.
        entry['expected_layout']=dict(region_bytes=[r['bytes'] for r in layout[:7]]+sizes,
            core_bytes=4096,monitor_bytes=131072,total_mapping_bytes=1,workers={})
    plan_sha=v.sha(plan)
    now=time.monotonic_ns();window=dict(boot_id='SOFTWARE-ONLY-NO-ACTUAL-STAND',
        start_monotonic_ns=now-10**9,end_monotonic_ns=now-10**9+v.DAY_NS)
    native=dict(schema_version='cpu-prefetch-stage17-s180-session-result/1',session_id=SESSION,plan_sha256=plan_sha,
        blueprint_sha256=v.planning.BLUEPRINT_SHA256,method_id=v.capture.controls.METHOD,stop=1,attempted=180,completed=180,
        restoration_attempted=True,restoration_verified=True,cleanup_verified=True,contexts_after_family_release=cleanups,
        whole_plots=[],artifacts=[],publication_scope='BEFORE_FINAL_PUBLICATION_RETURNS',execution_authority=False,phase18_authority=False)
    apply=[];restore=[]
    for state in plan['blueprint']['requested_whole_plot_order']:
        if state=='H1':
            apply.extend(dict(cpu=r['cpu'],complete_value=r['value']|15) for r in plan['hardware']['prestate'])
            restore.extend(dict(cpu=r['cpu'],complete_value=r['value']) for r in reversed(plan['hardware']['prestate']))
        native['whole_plots'].append(dict(requested_state=state,cumulative_apply_readback=copy.deepcopy(apply),
            cumulative_restore_readback=copy.deepcopy(restore),restoration_verified=True,
            independent_restore_observations=[dict(cpu=r['cpu'],requested_prestate=r['value'],observed_value=r['value'],
                read_succeeded=True) for r in plan['hardware']['prestate']]))
    for ordinal,(row,entry) in enumerate(zip(rows,plan['captures'],strict=True)):
        item=copy.deepcopy(base);report=item['report'];cp=item['checkpoint'];prefix='s180-e'+str(ordinal)
        prospective=v.capture.prospective_capture(row,entry);context=(row['placement'],row['working_set_class'])
        shared_data,sizes=shared[context];cleanup=cleanups[v.CONTEXTS.index(context)]
        report.update(execution_ordinal=ordinal,cell_ordinal=row['cell_ordinal'],run_id=row['run_id'],plan_sha256=plan_sha,
            program_scope_sha256=plan['storage']['program_scope_sha256'],session_id=SESSION,prospective_capture_sha256=v.sha(prospective))
        proof=report['control_evidence'];proof.update(execution_ordinal=ordinal,run_id=row['run_id'],prospective_capture_sha256=v.sha(prospective),
            resources_sha256=v.sha(entry['resources']),monitoring_sha256=v.sha(entry['monitoring']),hardware_control_sha256=v.sha(plan['hardware']),
            expected_layout_sha256=v.sha(entry['expected_layout']),phase_bounds_sha256=v.sha(entry['phases']),family_context_cleanup_sha256=v.sha(cleanup),
            shared_data=copy.deepcopy(shared_data))
        proof['regions'][7:9]=[dict(address=m['mapping']['address'],bytes=m['requested']['bytes'],
            expected_node=m['requested']['requested_node']) for m in shared_data['mappings']]
        origin=1000000+ordinal*10000000000
        cp.update(session_id=SESSION,plan_sha256=plan_sha,program_scope_sha256=plan['storage']['program_scope_sha256'],execution_ordinal=ordinal)
        final=cp['native_result_after_private_cleanup'];final['clock_origin']['absolute_nanoseconds']=origin
        lifecycle=final['session']['scheduled']['lifecycle'];lifecycle['clock_origin']['absolute_nanoseconds']=origin
        for i,(phase,state,p,source) in enumerate(zip(report['phases'],lifecycle['phases'],entry['phases'],report['source_publications'],strict=True)):
            run=row['warmup_run_id' if i==0 else 'run_id'];phase['run_id']=run
            _,pb,cb,jb=v.capture.codec.row_layout(run);n=phase['accepted_count']
            phase.update(joined_row_bytes=jb,joined_size_bytes=n*jb)
            for role,count,size in (('producer',phase['offered_count'],pb),('consumer',n,cb)):
                binding=phase['primary_streams'][role];binding.update(path=prefix+'-'+('warmup' if i==0 else 'measurement')+'-'+role+'.bin',
                    row_count=count,size_bytes=count*size)
            sample=state['origin_sample'];sample['absolute_nanoseconds']=origin+sample['relative_picoseconds']//1000
            state['drain_checkpoint']['absolute_nanoseconds']=origin+state['drain_checkpoint']['relative_picoseconds']//1000
            proof['phase_windows'][i].update(clock_origin_absolute_nanoseconds=origin,measurement_origin=copy.deepcopy(sample))
            source.update(original_source_artifact=copy.deepcopy(p['source_artifact']),original_big_endian_sha256=p['source_artifact']['sha256'])
        originals=[]
        for i in range(2):
            for role in ('producer','consumer'):
                b=report['phases'][i]['primary_streams'][role]
                originals.append(dict(file_name=b['path'],size_bytes=b['size_bytes'],sha256=b['sha256']))
        originals.append(dict(report['nodes']['publication'],file_name=prefix+'-node-order.bin',
            size_bytes=(row['requested_geometry']['capacity']+1)*8))
        for i,source in enumerate(report['source_publications']):
            source['publication']['file_name']=prefix+'-'+('warmup' if i==0 else 'measurement')+'-schedule.bin'
            originals.append(copy.deepcopy(source['publication']))
        originals.append(dict(report['original_artifacts'][7],file_name=prefix+'-control.json'))
        report['original_artifacts']=originals;report['nodes'].update(publication=copy.deepcopy(originals[4]),
            count=row['requested_geometry']['capacity']+1,pattern=copy.deepcopy(shared_data['node_pattern']))
        cp['artifacts']=[dict(r,role=v.capture.checkpoint_contract.artifact_identity(ordinal,r['file_name'])[0],
            schema_identity=v.capture.checkpoint_contract.artifact_identity(ordinal,r['file_name'])[1],
            media_type=v.capture.checkpoint_contract.artifact_identity(ordinal,r['file_name'])[2]) for r in originals]
        report['checkpoint_sha256']=v.sha(cp)
        cp_binding=v._bound(prefix+'-checkpoint.json',cp)
        receipt=dict(schema_version=v.capture.checkpoint_contract.CUSTODY_SCHEMA,plan_sha256=plan_sha,
            program_scope_sha256=plan['storage']['program_scope_sha256'],execution_ordinal=ordinal,checkpoint=cp_binding,
            status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',execution_authority=False,phase18_authority=False,artifacts=[])
        registry=dict(execution_ordinal=ordinal,checkpoint=cp_binding,continuation_allowed=True,artifacts=[])
        for r in originals:
            artifact=plan_sha+':'+r['file_name'];rowmeta=dict(artifact_id=artifact,logical=r,expected_logical=r,failure_receipt=None,
                archive_name=hashlib.sha256(artifact.encode()).hexdigest()+'.cpfa',physical=dict(size_bytes=64,sha256='d'*64),
                released_record=dict(file_name='SOFTWARE-RELEASE.json',size_bytes=64,sha256='e'*64))
            receipt['artifacts'].append(rowmeta)
            registry['artifacts'].append(dict(artifact_id=artifact,logical=r,archive_name=rowmeta['archive_name'],
                physical=rowmeta['physical'],released_record=rowmeta['released_record'],
                header=dict(artifact_id=artifact,canonical_size_bytes=r['size_bytes'],canonical_sha256=r['sha256'])))
        receipt_binding=v._bound(prefix+'-archive-custody.json',receipt);registry['custody_receipt']=receipt_binding
        item.update(custody_receipt=receipt,registry_proof=registry,
            attempt=dict(schema_version='cpu-prefetch-stage17-s180-run-attempt/1',session_id=SESSION,plan_sha256=plan_sha,
                execution_ordinal=ordinal,cell_ordinal=row['cell_ordinal'],run_id=row['run_id'],retry_allowed=False,
                deadline_monotonic_ns=now+(ordinal+1)*10**9),
            parent_receipt=dict(schema_version='cpu-prefetch-stage17-s180-parent-custody/1',plan_sha256=plan_sha,
                request_sha256=REQUEST,execution_ordinal=ordinal,checkpoint=cp_binding,custody_receipt=receipt_binding,
                broker_processes=25,status='ARCHIVED_AND_RELEASED',scientific_validity='NOT_ASSESSED',
                execution_authority=False,phase18_authority=False,broker_cleanup=dict(returncode=0,leader_reaped=True,process_group_gone=True,
                    descendants_detected_after_leader_exit=False,cleanup_deadline_overrun=False,leader_wait_timed_out=False)))
        pub=item['publication'];pub.update(execution_ordinal=ordinal,run_id=row['run_id'],plan_sha256=plan_sha,
            capture_validation=v._bound('capture-validation.json',report),tail_numerics=v._bound('tail-numerics.json',report['tail_numerics']))
        for i,(phase,published) in enumerate(zip(report['phases'],pub['joined'],strict=True)):
            name=('warmup','measurement')[i];audit_id=plan_sha+':analysis:'+str(ordinal)+':'+name+':join-audit'
            audit=dict(schema_version='cpu-prefetch-stage17-s180-validated-join-audit/1',artifact_id=audit_id,
                capture_validation=pub['capture_validation'],phase=name,join_status='PASSED',
                independently_reconciled_primary_audit=phase,execution_authority=False)
            published.update(artifact=dict(file_name=name+'-joined.bin',size_bytes=phase['joined_size_bytes'],sha256=phase['joined_sha256']),
                join_audit=dict(v._bound(name+'-join-audit.json',audit),artifact_id=audit_id))
            sources=[];bindings=[]
            for j,kind in enumerate(('PRODUCER','CONSUMER','JOINED_DERIVED')):
                env=item['envelopes'][i*3+j];joined=kind=='JOINED_DERIVED';b=None if joined else phase['primary_streams'][kind.lower()]
                env.update(run_id=phase['run_id'],row_count=phase['accepted_count'] if joined else b['row_count'],
                    byte_count=phase['joined_size_bytes'] if joined else b['size_bytes'],
                    artifact_sha256=phase['joined_sha256'] if joined else b['sha256'],
                    artifact_id=plan_sha+':analysis:'+str(ordinal)+':'+name+':joined' if joined else plan_sha+':'+b['path'],
                    integrity_artifact_ref=dict(artifact_id=audit_id,sha256=published['join_audit']['sha256']))
                if joined:env['source_artifacts']=copy.deepcopy(sources)
                else:sources.append(dict(artifact_id=env['artifact_id'],sha256=env['artifact_sha256']))
                bindings.append(v._bound(name+'-'+kind.lower()+'-envelope.json',env))
            published['raw_stream_envelopes']=bindings
        records.append(item)
        native['artifacts'].extend([v._reference(prefix+'-attempt.json','S180_RUN_ATTEMPT','cpu-prefetch-stage17-s180-run-attempt/1',item['attempt']),
            *cp['artifacts'],v._reference(prefix+'-checkpoint.json','S180_CAPTURE_CHECKPOINT',v.capture.checkpoint_contract.SCHEMA,cp),
            v._reference(prefix+'-archive-custody.json','S180_ARCHIVE_CUSTODY',v.capture.checkpoint_contract.CUSTODY_SCHEMA,receipt)])
    return dict(plan=plan,session_id=SESSION,request_sha256=REQUEST,native_result=native,records=records,window_binding=window)


def rebind(family,ordinal,*,checkpoint_changed=False):
    """Refresh metadata hashes to test semantics past simple hash mismatches."""
    item=family['records'][ordinal];report=item['report'];pub=item['publication'];plan_sha=report['plan_sha256']
    prefix='s180-e'+str(ordinal);cp=item['checkpoint']
    if checkpoint_changed:
        cp_binding=v._bound(prefix+'-checkpoint.json',cp);report['checkpoint_sha256']=cp_binding['sha256']
        for document in (item['custody_receipt'],item['registry_proof'],item['parent_receipt']):document['checkpoint']=cp_binding
        receipt_binding=v._bound(prefix+'-archive-custody.json',item['custody_receipt'])
        item['registry_proof']['custody_receipt']=item['parent_receipt']['custody_receipt']=receipt_binding
        family['native_result']['artifacts'][ordinal*11:ordinal*11+11]=[
            v._reference(prefix+'-attempt.json','S180_RUN_ATTEMPT','cpu-prefetch-stage17-s180-run-attempt/1',item['attempt']),
            *cp['artifacts'],v._reference(prefix+'-checkpoint.json','S180_CAPTURE_CHECKPOINT',v.capture.checkpoint_contract.SCHEMA,cp),
            v._reference(prefix+'-archive-custody.json','S180_ARCHIVE_CUSTODY',v.capture.checkpoint_contract.CUSTODY_SCHEMA,item['custody_receipt'])]
    pub['capture_validation']=v._bound('capture-validation.json',report)
    pub['tail_numerics']=v._bound('tail-numerics.json',report['tail_numerics'])
    for i,(phase,row) in enumerate(zip(report['phases'],pub['joined'],strict=True)):
        name=('warmup','measurement')[i];audit_id=plan_sha+':analysis:'+str(ordinal)+':'+name+':join-audit'
        audit=dict(schema_version='cpu-prefetch-stage17-s180-validated-join-audit/1',artifact_id=audit_id,
            capture_validation=pub['capture_validation'],phase=name,join_status='PASSED',
            independently_reconciled_primary_audit=phase,execution_authority=False)
        row['join_audit']=dict(v._bound(name+'-join-audit.json',audit),artifact_id=audit_id)
        for j,kind in enumerate(('PRODUCER','CONSUMER','JOINED_DERIVED')):
            env=item['envelopes'][i*3+j]
            env['integrity_artifact_ref']=dict(artifact_id=audit_id,sha256=row['join_audit']['sha256'])
            row['raw_stream_envelopes'][j]=v._bound(name+'-'+kind.lower()+'-envelope.json',env)


class FamilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base=template();cls.all_full=template(all_full=True)
        cls.pristine=family_fixture(cls.base);cls.full_pristine=family_fixture(cls.all_full)

    def setUp(self):self.f=copy.deepcopy(self.pristine)
    def run_family(self):return v.validate_family(**self.f,deadline_ns=time.monotonic_ns()+120*10**9)
    def fails(self):
        with self.assertRaises(v.common.ValidationError):self.run_family()

    def test_complete_matrix_contexts_sources_native_order_and_no_operational_promotion(self):
        r=self.run_family();self.assertEqual(r['status'],'PASSED');self.assertEqual(r['captures_verified'],180)
        self.assertEqual(r['native_artifact_references_verified'],1980);self.assertEqual(r['paired_sources_verified'],36)
        self.assertEqual(r['phase_count_totals']['measurement'],dict(offered=720,accepted=720,full=0))
        self.assertEqual(r['primary_effective_count_not_passed_ordinals'],list(range(180)))
        for k in ('original_archive_custody_verified','analysis_supervision_verified','original_generator_provenance_verified',
                'operational_exit_verified','inferential_freeze_established','execution_authority','phase18_authority'):
            self.assertFalse(r[k])
        self.assertFalse(r['recovery_duration_independently_measured'])

    def test_all_full_and_undefined_effective_counts_are_retained_not_rejected(self):
        self.f=copy.deepcopy(self.full_pristine);r=self.run_family()
        self.assertEqual(r['phase_count_totals']['measurement'],dict(offered=720,accepted=0,full=720))
        self.assertEqual(r['measurement_zero_loss_failed_ordinals'],list(range(180)))
        self.assertEqual(r['block_length_candidate']['status'],'UNRESOLVED')

    def test_pending_inputs_preserve_consistency_without_claiming_physical_validity_or_continuation(self):
        for item in self.f['records']:
            item['registry_proof'].update(schema_version=v.analysis_input.SCHEMA,continuation_allowed=False,
                original_collection_release_verified=True,physical_sha256_verification_pending=True,
                independent_inverse_required=True,inverse_readback_performed=False,scientific_validity='NOT_ASSESSED',
                execution_authority=False,phase18_authority=False)
        r=self.run_family();self.assertEqual(r['status'],'PASSED')
        self.assertFalse(r['original_archive_custody_verified']);self.assertFalse(r['execution_authority'])
        self.f['records'][0]['registry_proof']['independent_inverse_required']=False;self.fails()

    def test_missing_duplicate_reordered_capture_or_changed_frozen_design_reject(self):
        for mutation in ('missing','duplicate','order','blueprint'):
            self.f=copy.deepcopy(self.pristine)
            if mutation=='missing':self.f['records'].pop()
            elif mutation=='duplicate':self.f['records'][1]=copy.deepcopy(self.f['records'][0])
            elif mutation=='order':self.f['records'][0],self.f['records'][1]=self.f['records'][1],self.f['records'][0]
            else:self.f['plan']['blueprint']['captures'][0]['measurement_ns']+=1
            self.fails()

    def test_same_context_identity_change_or_cross_context_overlap_reject(self):
        rows=sorted(self.f['plan']['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
        target=next(i for i,row in enumerate(rows[1:],1) if (row['placement'],row['working_set_class'])==
            (rows[0]['placement'],rows[0]['working_set_class']))
        self.f['records'][target]['report']['control_evidence']['shared_data']['arena_object']+=256
        with self.assertRaisesRegex(v.common.ValidationError,'unchanged whole-family shared context'):self.run_family()

    def test_distinct_context_overlap_rejects_even_with_coherently_rebound_reports(self):
        rows=sorted(self.f['plan']['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
        near=next(item['report']['control_evidence'] for row,item in zip(rows,self.f['records'],strict=True)
            if (row['placement'],row['working_set_class'])==v.CONTEXTS[0])
        self.f['native_result']['contexts_after_family_release'][3]=copy.deepcopy(self.f['native_result']['contexts_after_family_release'][0])
        cleanup=self.f['native_result']['contexts_after_family_release'][3]
        for i,(row,item) in enumerate(zip(rows,self.f['records'],strict=True)):
            if (row['placement'],row['working_set_class'])!=v.CONTEXTS[3]:continue
            proof=item['report']['control_evidence'];s=proof['shared_data'];s['mappings']=copy.deepcopy(near['shared_data']['mappings'])
            for name in ('arena_object','ring_object','linked_object','node_bytes'):s[name]=near['shared_data'][name]
            proof['regions'][7:9]=copy.deepcopy(near['regions'][7:9]);proof['family_context_cleanup_sha256']=v.sha(cleanup)
            rebind(self.f,i)
        with self.assertRaisesRegex(v.common.ValidationError,'different persistent contexts overlap'):self.run_family()

    def test_node_source_extent_and_pairing_tamper_cannot_be_hidden(self):
        for mutation in ('node','source','extent'):
            self.f=copy.deepcopy(self.pristine);r=self.f['records'][0]['report']
            if mutation=='node':r['nodes']['count']-=1
            elif mutation=='source':r['source_publications'][0]['original_big_endian_sha256']='0'*64
            else:r['phases'][1]['joined_size_bytes']-=1
            self.fails()

    def test_actual_phase_overlap_is_checked_in_raw_clock_without_mixing_window_clock(self):
        item=self.f['records'][1];final=item['checkpoint']['native_result_after_private_cleanup']
        origin=self.f['records'][0]['checkpoint']['native_result_after_private_cleanup']['clock_origin']['absolute_nanoseconds']
        final['clock_origin']['absolute_nanoseconds']=origin;session=final['session']['scheduled']['lifecycle']
        session['clock_origin']['absolute_nanoseconds']=origin
        for i,state in enumerate(session['phases']):
            sample=state['origin_sample'];sample['absolute_nanoseconds']=origin+sample['relative_picoseconds']//1000
            state['drain_checkpoint']['absolute_nanoseconds']=origin+state['drain_checkpoint']['relative_picoseconds']//1000
            item['report']['control_evidence']['phase_windows'][i].update(clock_origin_absolute_nanoseconds=origin,measurement_origin=copy.deepcopy(sample))
        rebind(self.f,1,checkpoint_changed=True)
        with self.assertRaisesRegex(v.common.ValidationError,'overlapping or reordered actual capture phases'):self.run_family()

    def test_private_or_monitor_mapping_cannot_alias_another_context(self):
        rows=sorted(self.f['plan']['blueprint']['captures'],key=lambda r:r['execution_ordinal'])
        for mutation in ('private','monitor'):
            self.f=copy.deepcopy(self.pristine);item=self.f['records'][0];context=(rows[0]['placement'],rows[0]['working_set_class'])
            other=next(r['report']['control_evidence']['regions'][7]['address'] for row,r in zip(rows,self.f['records'],strict=True)
                if (row['placement'],row['working_set_class'])!=context)
            if mutation=='private':item['report']['control_evidence']['regions'][0]['address']=other
            else:item['checkpoint']['native_result_after_private_cleanup']['monitor_mapping']['mapping']['address']=other
            rebind(self.f,0,checkpoint_changed=mutation=='monitor')
            with self.assertRaisesRegex(v.common.ValidationError,'private/monitor/guard overlaps'):self.run_family()

    def test_native_reference_drop_or_reorder_and_failed_cleanup_or_counts_reject(self):
        for mutation in ('drop','order','cleanup','count'):
            self.f=copy.deepcopy(self.pristine);native=self.f['native_result']
            if mutation=='drop':native['artifacts'].pop()
            elif mutation=='order':native['artifacts'][0],native['artifacts'][1]=native['artifacts'][1],native['artifacts'][0]
            elif mutation=='cleanup':native['cleanup_verified']=False
            else:native['completed']=179
            self.fails()

    def test_full_msr_restore_vectors_order_and_raw_read_values_reject_tamper(self):
        for mutation in ('apply','restore','independent','order'):
            self.f=copy.deepcopy(self.pristine);plots=self.f['native_result']['whole_plots']
            if mutation=='apply':plots[0]['cumulative_apply_readback'][0]['complete_value']^=16
            elif mutation=='restore':plots[0]['cumulative_restore_readback'].reverse()
            elif mutation=='independent':plots[-1]['independent_restore_observations'][0]['observed_value']=False
            else:plots.reverse()
            self.fails()

    def test_missing_custody_source_discrepancy_or_foreign_request_reject(self):
        for mutation in ('missing','discrepancy','request','broker'):
            self.f=copy.deepcopy(self.pristine);item=self.f['records'][0]
            if mutation=='missing':item['registry_proof']['artifacts'].pop()
            elif mutation=='discrepancy':item['custody_receipt']['artifacts'][0]['failure_receipt']={}
            elif mutation=='request':item['parent_receipt']['request_sha256']='0'*64
            else:item['parent_receipt']['broker_cleanup']['process_group_gone']=False
            self.fails()

    def test_derived_binding_envelope_identity_or_numeric_population_reject(self):
        for mutation in ('joined','envelope','numeric'):
            self.f=copy.deepcopy(self.pristine);item=self.f['records'][0]
            if mutation=='joined':item['publication']['joined'][0]['artifact']['sha256']='0'*64
            elif mutation=='envelope':item['envelopes'][0]['artifact_id']='FOREIGN'
            else:item['report']['tail_numerics']['raw_accepted_count']+=1
            if mutation in ('envelope','numeric'):rebind(self.f,0)
            self.fails()

    def test_defining_tail_equations_and_observed_horizon_bounds_are_checked(self):
        values=[0]*1999+[1,2]
        report=v.capture.tails.analyze(values,maximum_samples=2001,deadline_ns=time.monotonic_ns()+10**9)
        v._numeric_consistency(report,2001)
        for mutation in ('variance','horizon','time','gate'):
            changed=copy.deepcopy(report);tail=changed['primary_tail']
            if mutation=='variance':tail['variance_numerator_decimal']='0'
            elif mutation=='horizon':tail['correlation_horizon_events']=2000
            elif mutation=='time':tail['effective_count']['numerator_decimal']='99999999'
            else:tail['primary_200000_gate']='PASS'
            with self.assertRaises(v.common.ValidationError):v._numeric_consistency(changed,2001)

    def test_original_window_and_deadline_cannot_be_reset(self):
        self.f['window_binding']['end_monotonic_ns']+=1;self.fails()
        self.f=copy.deepcopy(self.pristine)
        with self.assertRaises(v.common.ValidationError):v.validate_family(**self.f,deadline_ns=0)


if __name__=='__main__':unittest.main()
