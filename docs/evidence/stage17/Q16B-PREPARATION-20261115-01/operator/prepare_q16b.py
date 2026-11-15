"""D248 cold Q16b candidate builder. Never register, sign, isolate or measure."""
from __future__ import annotations
import argparse
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'build/stage17-step5-prep/formal-q16a-authoring-1')]
import prepare_q16a as old
import stage17_formal_plan_v1 as service
import stage17_formal_plan_v2 as formal
import stage17_formal_archive_v1 as archive
import stage17_formal_storage_budget_v1 as storage

NS=10**9;MIB=1024**2;GIB=1024**3
WARMUP_CAP=100_000_000;MEASUREMENT_CAP=30_000_000
WORKER_AS=224*GIB;CONTROLLER_AS=BROKER_AS=2*GIB
SOURCE='42f2ebb96f751319cd55fc1fabdcf7f91ab1c8d0'
STAND_E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')

def require(ok,label):
    if not ok:raise ValueError(label)
def digest(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def bind(p,target=None):
    p=Path(p).resolve(strict=True);b=p.read_bytes()
    return dict(path=str(p) if target is None else str(target),size_bytes=len(b),sha256=digest(b))
def write(p,d):
    with Path(p).open('xb') as f:f.write(archive.canonical(d))
def identity(master,phase,ordinal):
    namespace='CPU-PREFETCH-V5-V25-Q16B-'+phase+'-1'
    rid='B25'+('W' if phase=='WARMUP' else 'M')+f'{ordinal:08d}'
    return dict(namespace_id=namespace,seed_id=namespace+f'-SEED-{ordinal:04d}',run_id=rid,
        seed_hex=digest(bytes.fromhex(master)+b'\0'+namespace.encode()+b'\0'+rid.encode()))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse-identities',type=Path)
    args=parser.parse_args();out=args.output.resolve()
    require(out.parent==HERE,'candidate must be a fresh local preparation sibling')
    out.mkdir(exist_ok=False);layouts=out/'layouts';layouts.mkdir()
    request_path=HERE/'inputs/q16a-request.json';require(bind(request_path)['sha256']=='aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a','actual retained request')
    request=load(request_path);parent=request['action_inputs']['plan']
    require(parent['source_revision']==SOURCE,'qualified native source')
    handoff_path=ROOT/'docs/evidence/stage17/Q16B-PREPARATION-20261115-01/stand/preparation/q16a-handoff.json'
    handoff=bind(handoff_path,STAND_E/'q16b-handoff-preparation-1/q16a-handoff.json')
    require(handoff['sha256']=='0d4e2d233167fc6157001b0fe38e763a77dbbcd65a19b7ef2e09c2563c02c4bb','actual admitted Q16a handoff')
    binary=HERE/'native-sizing/release/service-layout';provenance=load(HERE/'native-sizing/release/provenance.json')
    require(bind(binary)['sha256']==load(HERE/'native-sizing/RESULT.json')['release_binary']['sha256'],'reviewed native query')
    require(load(HERE/'native-sizing/RESULT.json')['status']=='PASS','native query checks')
    model=old.model_module();compress=old.zstd_bounder(ROOT/'build/ext007-runtime-20261101/root/usr/lib/libzstd.so.1.5.7')
    proof_inputs={name:bind(path) for name,path in dict(
        metadata_helper=old.__file__,allocation_helper=old.earlier.__file__,
        imported_r3_helper=old.r3.__file__,symbolic_observation_model=model.__file__,
        zstd_library=ROOT/'build/ext007-runtime-20261101/root/usr/lib/libzstd.so.1.5.7').items()}
    retained=load(args.reuse_identities) if args.reuse_identities else None
    master=retained['master_seed_hex'] if retained else secrets.token_hex(32)
    identities=[identity(master,phase,i) for i in range(3540) for phase in ('WARMUP','MEASUREMENT')]
    if retained:require(identities==retained['phase_identities'],'original prospective identities differ')
    geometry=load(ROOT/'docs/evidence/stage17/Q16A-COMPOSITION-ACTUAL-20261115-01/stand/composition/native-geometry-verification.json')['records']
    template=parent['captures'][0];hardware=request['action_inputs']['hardware_control']
    prestate=[dict(cpu=r['cpu'],value=int(r['complete_value_hex'],16)) for r in hardware['prestate']]
    rows=[];proofs=[];largest=staging=peak=0
    for cell,state,package,placement,ws,_ in service.cells('Q16b'):
        position=len(rows)//59;ordinal=len(rows)
        item={k:copy.deepcopy(template[k]) for k in ('capture','resources','monitoring')}
        c,r,m=(item[k] for k in ('capture','resources','monitoring'))
        c.pop('context_ordinal');c.pop('minimum_observations_per_series')
        c.update(schema_version='cpu-prefetch-stage17-formal-service-capture/1',method_id=service.METHOD['Q16b'],
            package=package,ordinal=ordinal,cell_ordinal=cell,repetition_ordinal=0,hardware_state=state,
            placement=placement,working_set_class=ws,warmup_ns=5*NS,measurement_ns=NS,
            software_prefetch_mapping_id='X86-64-PREFETCHT0-ONLY-v1',linked_order=None,ring_distance=None)
        context=(0 if placement=='NEAR' else 3)+service.WORKING_SETS.index(ws)
        g=geometry[context];consumer=1 if placement=='NEAR' else 8;node=0 if placement=='NEAR' else 1
        c['geometry'].update(capacity=g['capacity'],cache_line_bytes=g['cache_line_bytes'],consumer_cpu=consumer,consumer_node=node)
        c['warmup'],c['measurement']=copy.deepcopy(identities[2*ordinal:2*ordinal+2]);c['arena_seed']=copy.deepcopy(c['measurement'])
        if package in ('R1','R2'):
            c['ring_distance']=dict(cache_lines=1 if package=='R1' else 2,calibration_evidence_id='' if package=='R1' else 'q16a-sha256-'+handoff['sha256'])
        if package in ('L0','L1'):
            c['linked_order']=dict(seed_id=f'CPU-PREFETCH-V5-V25-Q16B-NODE-SEED-{ordinal:04d}',
                namespace_id='CPU-PREFETCH-V5-V25-Q16B-NODE-ORDER-1',arena_alignment_bytes=c['geometry']['base_page_bytes'],
                seed_hex=digest(bytes.fromhex(master)+b'\0NODE\0'+str(ordinal).encode()))
        c['budget'].update(memory_bytes=WORKER_AS,phases=[dict(producer_attempt_limit=n,consumer_poll_limit=n,drain_ns=30*NS) for n in (WARMUP_CAP,MEASUREMENT_CAP)])
        r['ordinal']=m['ordinal']=ordinal
        r['workers']['consumer_stack'].update(owner_cpu=consumer,requested_node=node)
        r.update(core_bytes=1,monitor_bytes=1,total_mapping_bytes=1,region_bytes=[1]*7,
            phase_capacity=[dict(producer_primary_rows=n,consumer_primary_rows=n) for n in (WARMUP_CAP,MEASUREMENT_CAP)])
        native=dict(**item,hardware_prestate=prestate);path=layouts/f'cell-{cell:02d}.input.json';write(path,native)
        run=subprocess.run([str(binary),'--describe',str(path)],capture_output=True,timeout=35)
        (layouts/f'cell-{cell:02d}.stderr').write_bytes(run.stderr)
        require(run.returncode==0,'cold native layout rejected: '+run.stderr.decode(errors='replace'))
        output=layouts/f'cell-{cell:02d}.layout.json';output.write_bytes(run.stdout);answer=load(output)
        require(answer['source_revision']==SOURCE and answer['source_dirty'] is False and answer['declared_layout_rechecked'] is True,'qualified native layout identity')
        r.update(answer['layout']);meta=old.metadata_bound(model,r,m)
        raw=[];widths=[]
        for phase,n in zip(('warmup','measurement'),(WARMUP_CAP,MEASUREMENT_CAP)):
            prefix=old.align(4+len(c[phase]['run_id'].encode()),8)
            for body in (120,80):widths.append(prefix+body);raw.append((prefix+body)*n)
        extra=(c['geometry']['capacity']+1)*8 if package in ('L0','L1') else 0
        # The publisher retains a node-order artifact even for an empty ring order.
        streams=[*raw,extra]
        control=meta['control_bytes']+MIB;total=sum(streams)+control
        archive_max=(sum(max(old.archive_upper(n,8192*w,compress),old.archive_upper(n,4*MIB,compress))
                         for n,w in zip(raw,widths,strict=True))
            +sum(old.archive_upper(n,4*MIB,compress) for n in [extra,control])+2*MIB)
        copy_floor=max(*raw,extra)
        minimum_memory=r['total_mapping_bytes']+copy_floor+meta['cold_heap_model_bytes']
        require(minimum_memory<=WORKER_AS,'native/publication/metadata bound exceeds224GiB')
        budget=dict(setup_ns=120*NS,publication_ns=1800*NS,cleanup_ns=120*NS,
            watchdog_ns=(120+5+1+60+1800+120)*NS,publication_memory_bytes=copy_floor,
            other_memory_bytes=meta['cold_heap_model_bytes'],memory_bytes=WORKER_AS,
            metadata_output_bytes=control,max_output_bytes=total)
        largest=max(largest,total);staging=max(staging,old.align(archive_max,4096));peak=max(peak,minimum_memory)
        proofs.append(dict(cell_ordinal=cell,native_input=bind(path),native_output=bind(output),metadata=meta,
            maximum_raw_bytes=sum(streams),required_memory_bytes=minimum_memory,maximum_output_bytes=total))
        for repetition in range(59):
            row={**copy.deepcopy(item),'execution_budget':copy.deepcopy(budget)};n=len(rows)
            for k in ('capture','resources','monitoring'):row[k]['ordinal']=n
            cap=row['capture'];cap['repetition_ordinal']=repetition
            cap['warmup'],cap['measurement']=copy.deepcopy(identities[2*n:2*n+2]);cap['arena_seed']=copy.deepcopy(cap['measurement'])
            if cap['linked_order'] is not None:
                cap['linked_order'].update(seed_id=f'CPU-PREFETCH-V5-V25-Q16B-NODE-SEED-{n:04d}',seed_hex=digest(bytes.fromhex(master)+b'\0NODE\0'+str(n).encode()))
            rows.append(row)
        print('NATIVE_CELL_SIZED',position,cell,package,placement,ws,flush=True)
    st=copy.deepcopy(parent['storage']);st.update(archive_staging_bytes=staging,analysis_capture_workspace_bytes=largest)
    family=copy.deepcopy(parent['budget']);family.update(controller_memory_bytes=CONTROLLER_AS,
        watchdog_ns=240*NS+sum(r['execution_budget']['watchdog_ns']+st['per_capture_archive_ns'] for r in rows),
        max_output_bytes=16*MIB+sum(r['execution_budget']['max_output_bytes'] for r in rows),
        memory_bytes=WORKER_AS+CONTROLLER_AS+st['codec_address_space_bytes']+st['broker_address_space_bytes'])
    plan=dict(schema_version=formal.VERSION['Q16b'],plan_id='CPU-PREFETCH-V5-V25-Q16B-PLAN-1',protocol_version='2.0.0-pre.3',
        action_id='Q16b',method_id=service.METHOD['Q16b'],source_revision=SOURCE,clean_source=True,stand_id=parent['stand_id'],
        repetitions_per_cell=59,measurement_ns=NS,warmup_namespace=identities[0]['namespace_id'],measurement_namespace=identities[1]['namespace_id'],
        custody_policy_id=storage.POLICY,captures=rows,budget=family,storage=st)
    extent=formal.validate_plan('Q16b',plan);write(out/'plan.json',plan)
    namespace=dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',plan_sha256=bind(out/'plan.json')['sha256'],
        stand_id=plan['stand_id'],phase_identities=identities,schedule_namespaces=[],execution_authority=False)
    write(out/'namespace_registry.json',namespace)
    write(out/'identities.json',dict(master_seed_hex=master,phase_identities=identities,
        linked_order_identities=[r['capture']['linked_order'] for r in rows if r['capture']['linked_order'] is not None],execution_authority=False))
    require(all(bind(b['path'])==b for b in proof_inputs.values()),'metadata proof input drift')
    write(out/'preparation.json',dict(status='COLD_NATIVE_SIZED_CANDIDATE',plan=bind(out/'plan.json'),
        prospective_duration_approval='D248',q16a_handoff=handoff,hardware_control=hardware,
        native_query=bind(binary),native_query_provenance=bind(HERE/'native-sizing/release/provenance.json'),
        helper=bind(__file__),metadata_proof_inputs=proof_inputs,retained_request=bind(request_path),native_cells=proofs,
        required_worker_as_bytes=WORKER_AS,required_family_as_bytes=family['memory_bytes'],
        minimum_native_publication_metadata_peak_bytes=peak,largest_capture_bytes=largest,archive_staging_bytes=staging,
        required_watchdog_ns=extent.required_watchdog_ns,planned_captures=len(rows),minimum_active_phase_ns=3540*6*NS,
        registration_performed=False,history_namespace_audit_performed=False,execution_authority=False,phase18_authority=False))
    print('CANDIDATE_VALIDATED',bind(out/'plan.json')['sha256'],len(rows),flush=True)

if __name__=='__main__':main()
