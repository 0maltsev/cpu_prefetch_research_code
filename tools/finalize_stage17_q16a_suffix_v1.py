"""Finish D244 bookkeeping from retained reports after its exact ledger error.

No capture, raw decode, original-receipt rewrite or retry. Optional waiting
observes only the original terminal receipt once every thirty minutes.
"""
from __future__ import annotations
import argparse
import dataclasses
import datetime
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

OPERATOR_SHA='b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23'
CONFIG_SHA='5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93'
ERROR_LINE='ValueError: ledger changed during offline validation'


def projected_head(file_binding,sequence):
    if type(sequence) is not int or sequence<0:
        raise ValueError('ledger sequence must be a nonnegative integer')
    if set(file_binding)!={'file_name','size_bytes','sha256'}:
        raise ValueError('original ledger file binding shape differs')
    return dict(sequence_number=sequence,sha256=file_binding['sha256'])


def expected_error(stderr):
    lines=stderr.rstrip().splitlines()
    if not lines or lines[-1]!=ERROR_LINE or 'validate_suffix.py' not in stderr:
        raise ValueError('not the exact D244 final ledger comparison error')


def finalize(v,a,c,out,m,pinned):
    A=Path(c['analysis_root']);r=c['resources'];reader=a.EvidenceReader()
    process_binding=a._current_binding(A/'analysis-process-result.json')
    process=json.loads(reader.read(process_binding),object_pairs_hook=v.base.unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite process JSON')))
    if process.get('exit_code')==0:
        a.check_process_result(process)
        v.save(out/'finalization-not-required.json',dict(status='ORIGINAL_FINALIZATION_SUCCEEDED',
            original_process=process_binding,raw_mutation=False,execution_authority=False),65536)
        return
    a._check_process_observations(process,1)
    stderr_binding=a._current_binding(A/'analysis-stderr.log')
    expected_error(reader.read(stderr_binding).decode('utf-8',errors='strict'))
    v.require(not (A/'validated-suffix-manifest.json').exists(),'original manifest already exists; do not replace')
    v.require({p.name for p in (A/'reports').glob('capture-*.json')}=={f'capture-{i}.json' for i in range(531)},'exact531 retained reports required')
    prepared=v.prepare(c,m);lifecycle=v.lifecycle(c,m,prepared,pinned)
    plan=prepared.request['action_inputs']['plan'];v.validate_population(plan)
    custody_binding=a._current_binding(A/'authenticated-suffix-custody.json');custody=reader.document(custody_binding)
    m.operational_semantics_v17._archive_scope(custody,prepared.request,prepared.root)
    v.require(len(custody['captures'])==531,'full authenticated custody required')
    limits=m.formal_archive_custody_v1.CustodyLimits(**r['custody'],deadline_ns=time.monotonic_ns()+1800*10**9)
    phase=Path(prepared.request['evidence_root_binding']['absolute_path'])
    declared={x['file_name']:{k:x[k] for k in ('file_name','size_bytes','sha256')} for x in lifecycle['result']['artifacts']}
    records=[]
    with m.formal_archive_custody_v1.ProgramStore(phase.parent.parent,scope_sha256=plan['storage']['program_scope_sha256'],family_id=v.PLAN_SHA,limits=limits) as store:
        before=dataclasses.asdict(store.ledger_binding())
        projected=projected_head(before,store._sequence-1)
        a.same(projected,custody['scope_bindings']['ledger_head'],'unchanged original ledger head')
        v.require(before!=custody['scope_bindings']['ledger_head'],'expected distinct ledger representations')
        for i,cap in enumerate(custody['captures']):
            a.match_signed_capture(cap,declared,i)
            capture=plan['captures'][i]['capture'];report=a._current_binding(A/'reports'/f'capture-{i}.json')
            def at_phase(b):
                v.require(Path(b['file_name']).name==b['file_name'],'flat signed artifact name')
                return dict(path=str(phase/b['file_name']),size_bytes=b['size_bytes'],sha256=b['sha256'])
            row=dict(local_ordinal=i,context_ordinal=capture['context_ordinal'],repetition_ordinal=capture['repetition_ordinal'],
                checkpoint_binding=at_phase(cap['checkpoint']),custody_binding=at_phase(cap['custody_receipt']),validation_report_binding=report)
            a.validate_capture(row,cap,plan,plan['storage']['program_scope_sha256'],reader,family_sha=v.PLAN_SHA)
            records.append(dict(local_ordinal=i,original_ordinal=i+177,measurement_run_id=capture['measurement']['run_id'],validation_report_binding=report))
        after=dataclasses.asdict(store.ledger_binding());a.same(after,before,'stable finalization ledger')
    for binding in c['files'].values():reader.read(binding)
    reader.read(process_binding);reader.read(stderr_binding);reader.finish()
    manifest=v.save(A/'validated-suffix-manifest.json',dict(schema_version='software-validated-q16a-suffix/1',status='VALIDATED',
        plan_sha256=v.PLAN_SHA,request=c['files']['REQUEST'],completion=c['files']['COMPLETION'],records=records,
        method_id=m.q16a_capture_validation_v1.demand.METHOD_ID,analysis_configuration_sha256=CONFIG_SHA,
        authenticated_custody=custody_binding,raw_mutation=False,family_validity_established=False,execution_authority=False,phase18_authority=False),r['metadata_bytes']//2)
    v.save(out/'finalization-result.json',dict(schema_version='software-q16a-retained-finalization/1',status='FINALIZED_FROM_RETAINED_REPORTS',
        original_process=process_binding,original_stderr=stderr_binding,configuration_sha256=CONFIG_SHA,
        operator=v.base.binding(Path(__file__).resolve()),validation_module=v.base.binding(Path(a.__file__).resolve()),
        ledger_file_binding=before,ledger_summary=projected,stable_ledger_file_binding=after,
        suffix_manifest=manifest,validated_reports=531,raw_redecode_performed=False,raw_mutation=False,execution_authority=False,phase18_authority=False,
        completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()),65536)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('operator-root','config','output-directory'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--wait',action='store_true');args=p.parse_args()
    if hashlib.sha256((args.operator_root/'validate_suffix.py').read_bytes()).hexdigest()!=OPERATOR_SHA:
        raise ValueError('original D244 operator source differs')
    sys.path.insert(0,str(args.operator_root));import validate_suffix as v
    c=v.config(args.config,CONFIG_SHA)
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,)*2)
    v.require(__import__('os').getuid()==1000,'owner-only metadata finalizer')
    out=v.base.safe(args.output_directory)
    v.require(not out.exists(),'fresh finalization output required')
    A=Path(c['analysis_root']);phase=Path(v.parse(v.read(c['files']['REQUEST']))['evidence_root_binding']['absolute_path'])
    v.require(not out.is_relative_to(phase.parent.parent) and not out.is_relative_to(Path(c['repository_root'])),'output/raw repository overlap')
    v.require(not out.is_relative_to(A) and not A.is_relative_to(out),'analysis/finalizer output overlap')
    out.mkdir(mode=0o700)
    intent=v.parse((A/'analysis-intent.json').read_bytes())
    deadline=intent['deadline_monotonic_ns']+1800*10**9
    v.save(out/'intent.json',dict(configuration_sha256=CONFIG_SHA,original_analysis_root=str(A),poll_seconds=1800,
        deadline_monotonic_ns=deadline,raw_redecode_performed=False,execution_authority=False),65536)
    try:
        while not (A/'analysis-process-result.json').is_file():
            v.require(args.wait,'original analysis is not complete')
            v.require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==c['boot_id'],'original analysis boot changed')
            remaining=(deadline-time.monotonic_ns())/1e9
            v.require(remaining>0,'original analysis terminal-receipt deadline exceeded')
            time.sleep(min(1800,remaining))
        # Import the new read-only gate after original qualified modules. The
        # original admission repository and running operator remain untouched.
        m,pinned=v.modules(c)
        import stage17_q16a_suffix_admission_v1 as admission
        finalize(v,admission,c,out,m,pinned)
    except BaseException as error:
        v.save(out/'finalization-error.json',dict(type=type(error).__name__,message=str(error),raw_mutation=False,execution_authority=False),65536)
        raise


if __name__=='__main__':main()
