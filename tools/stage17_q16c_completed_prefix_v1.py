"""D295 metadata-only reuse of the exact86 completed D292 validation reports.

No archive reader, raw validator, qualification or measurement entry point.
Original reports/manifests are copied byte-for-byte, retaining their own paths
and source/time identities. All experiment authority remains separately signed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types

import stage17_q16c_execution_window_v5 as window
import stage17_q16c_scientific_sources_v1 as science

E31=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-31')
ANALYSIS=E31/'q16c-prefix-analysis-1'
CONTEXT_SHA='c3fbeac94f60bf89aec54df76720d3e35b1c07e27d9b0e3cdfb823c4986fdb74'
PROCESS_SHA='95f26e49f237ab3a16fa7c678ecc490aeb0a0e30daf1ce87688ba27b812c4ad3'
require=window.require


def binding(path):
    raw=Path(path).read_bytes()
    b=dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    require(window.read(b)==raw,'stable bound metadata')
    return b


def document(b):return window.parse(window.read(b))


def verify_reports(completion_binding,prefix_binding,process_bindings):
    """Only report/receipt hashes and recorded claims; no scientific recomputation."""
    for role,b in (('validation_completion',completion_binding),('validated_prefix',prefix_binding)):
        size,digest=window.PRIOR_BINDINGS[role]
        require((b['size_bytes'],b['sha256'])==(size,digest),'exact retained '+role)
    completed=document(completion_binding);prefix=document(prefix_binding)
    require(completed['status']=='ALL_SELECTED_VALID' and completed['kind']=='PREFIX86'
        and completed['all_workers_reaped'] is True and 0<completed['elapsed_ns']<3600*10**9,
            'actual completed86 analysis')
    require(prefix['all_required_reports_valid'] is True and prefix['reused_capture_ordinals']==list(range(86))
        and prefix['compaction_control']=='UNRECORDED' and prefix['analysis_completion']==completion_binding,
            'original accepted prefix and its actual completion')
    reports=completed['reports'];retained=prefix['reports']
    require(type(reports) is list and len(reports)==len(retained)==86
        and type(process_bindings) is list and len(process_bindings)==86,'exact86 membership')
    rows=[]
    for ordinal,(b,accepted,p) in enumerate(zip(reports,retained,process_bindings,strict=True)):
        require(b['path']==str(ANALYSIS/'reports'/f'capture-{ordinal}.json')
            and p['path']==str(ANALYSIS/f'capture-{ordinal}-process.json'),'original report/receipt paths')
        require((accepted['size_bytes'],accepted['sha256'])==(b['size_bytes'],b['sha256'])
            and accepted['artifact_id']==f'Q16C-D292-PREFIX-{ordinal:04d}','original report identities and bytes')
        report=document(b);receipt=document(p)
        require(report['capture_ordinal']==ordinal and report['action_id']=='Q16c'
            and report['raw_reconciliation_validated'] is True and report['capture_execution_evidence_validated'] is True
            and report['family_validity_established'] is False and report['execution_authority'] is False
            and report['phase18_authority'] is False,'retained valid capture report; family not yet complete')
        require(receipt['ordinal']==ordinal and receipt['status']=='VALID' and receipt['exit_code']==0
            and receipt['leader_reaped'] is True and receipt['report']==b
            and receipt['canonical_spool_removed'] is True,'original successful/reaped process receipt')
        rows.append(dict(file_name=Path(p['path']).name,size_bytes=p['size_bytes'],sha256=p['sha256']))
    require(hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()==PROCESS_SHA,'exact original process receipt bytes')
    return completed,prefix


def _lineage(c,record,trust):
    from stage17_phase_controller_v2 import _verify_signature
    contents=window.verify_bindings(record)
    for role,sig in (('validation_window','validation_signature'),('prior_execution_window','prior_execution_signature')):
        _verify_signature(contents[role],Path(record['bindings'][sig]['path']),trust)
    old=window.parse(contents['validation_window'])
    packet=document(old['bindings']['prefix_validation_packet'])
    require(packet['candidate_inventory']==old['bindings']['candidate_inventory']
        and packet['candidate_worker']==old['bindings']['candidate_worker']
        and packet['candidate_source_revision']==old['source_revision'],'actual original validation candidate')
    old_index=science.admission._inventory(document(packet['candidate_inventory']))
    for name,b in packet['new_sources'].items():
        row=old_index['tools/'+name+'.py']
        require((b['size_bytes'],b['sha256'])==(row['size_bytes'],row['sha256']),'original validation helper inventory')
        window.read(b)
    original_operators=document(old['bindings']['operator_sources'])
    for b in original_operators['sources'].values():window.read(b)
    # The raw-validation child and its caller are the actual completed sources.
    current_index=science.admission._inventory(document(c['candidate_inventory']))
    for name in ('stage17_q16c_analysis_v2','stage17_q16c_control_reader_v1'):
        member='tools/'+name+'.py'
        require(current_index[member]['sha256']==old_index[member]['sha256'],
                'unchanged completed raw-analysis source '+name)
    context=document(c['original_context'])
    validation=types.SimpleNamespace(resolutions={k:types.SimpleNamespace(**v) for k,v in context['resolutions'].items()})
    reader=science.admission.BoundReader()
    manifest=science.authenticate(c['original_scientific_packet'],validation,reader)
    original=Path(context['resolutions']['S17-EXT-006']['semantic_context']['archive_bundle_root'])
    native_index=science.admission._inventory(document(binding(original/'BUNDLE_INVENTORY.json')))
    dependencies=science.bindings(original,Path(c['candidate_inventory']['path']).parent,
        native_index,current_index,manifest,reader)
    reader.finish()
    return len(dependencies)


def admit(c,*,packet_binding,proof,deadline_ns):
    require(os.getresuid()==(1000,)*3,'actual evidence owner')
    require(c['schema_version']=='cpu-prefetch-stage17-d295-completed-prefix-packet/1'
        and c['execution_authority'] is False and c['phase18_authority'] is False,'read-only completed-prefix packet')
    require(c['operator_source']==binding(Path(__file__).resolve()),'actual completed-prefix operator')
    inventory=document(c['candidate_inventory']);index={r['path']:r for r in inventory['files']}
    require(len(index)==len(inventory['files']) and inventory['source_revision']==c['candidate_source_revision'],
            'actual clean candidate inventory')
    member=index['tools/stage17_q16c_completed_prefix_v1.py']
    require((c['operator_source']['size_bytes'],c['operator_source']['sha256'])==(member['size_bytes'],member['sha256']),
            'completed-prefix code is qualified candidate source')
    record=document(proof['manifest']);now=time.monotonic_ns()
    window.validate(record,now=now,phase='retained_prefix_admission',expected_source=c['candidate_source_revision'],
        expected_worker=c['candidate_worker']['sha256'],expected_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    require(proof['manifest']['path']==str(window.EVIDENCE/'d295-execution-window-1/window.json')
        and proof['signature']['path']==proof['manifest']['path']+'.sig','exclusive fresh signed window')
    require(deadline_ns==record['started_monotonic_ns']+120*10**9 and now<deadline_ns,'original120s metadata ceiling')
    for role,key in (('prefix_validation_packet',None),('candidate_inventory','candidate_inventory'),
                     ('candidate_worker','candidate_worker'),('validation_completion','completion'),('validated_prefix','accepted_prefix')):
        require(record['bindings'][role]==(packet_binding if key is None else c[key]),'actual signed cached-prefix role '+role)
    require(c['original_context']['sha256']==CONTEXT_SHA,'actual original admitted owner/source export')
    context=document(c['original_context']);trust=context['resolutions']['S17-EXT-003']['semantic_context']['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and trust['subject_id']==record['stand_id'],'actual retained-study owner')
    from stage17_phase_controller_v2 import _verify_signature
    window.read(proof['signature']);_verify_signature(window.read(proof['manifest']),Path(proof['signature']['path']),trust)
    count=_lineage(c,record,trust)
    verify_reports(c['completion'],c['accepted_prefix'],c['process_receipts'])
    output=Path(c['output_root'])
    require(output==window.EVIDENCE/'q16c-prefix-analysis-1' and not output.exists(),'exclusive metadata reuse output')
    require(time.monotonic_ns()<deadline_ns,'metadata verification deadline')
    output.mkdir(mode=0o700)
    for name,b in (('complete.json',c['completion']),('accepted-prefix.json',c['accepted_prefix'])):
        raw=window.read(b)
        with (output/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(output,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    require(time.monotonic_ns()<deadline_ns,'metadata publication deadline')
    return dict(status='COMPLETED_86_REPORTS_REUSED_NO_RAW_VALIDATION',reports=86,scientific_dependencies=count,
        accepted_prefix=binding(output/'accepted-prefix.json'),completion=binding(output/'complete.json'),
        raw_validation_repeated=False,all_workers_reaped=True,execution_authority=False,phase18_authority=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('admit','software-check'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--window-proof',type=Path);p.add_argument('--deadline-ns',type=int);a=p.parse_args()
    b=dict(path=str(a.configuration),size_bytes=a.configuration.stat().st_size,sha256=a.configuration_sha256);c=document(b)
    if a.mode=='software-check':
        require(c['operator_source']==binding(Path(__file__).resolve()),'actual code')
        verify_reports(c['completion'],c['accepted_prefix'],c['process_receipts'])
        print(json.dumps(dict(status='EXACT_COMPLETED_86_METADATA_VERIFIED',raw_validation_repeated=False,window_started=False)))
    else:
        proof=document(binding(a.window_proof))
        print(json.dumps(admit(c,packet_binding=b,proof=proof,deadline_ns=a.deadline_ns)))


if __name__=='__main__':main()
