"""Prepare and check exact retained E25 inputs; never launch a measurement."""
import dataclasses
import json
from pathlib import Path
import time
import types
import validate_suffix as v

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')


def bound(path):
    b=v.base.binding(path);v.read(b);return b


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--analysis-root',type=Path,required=True);args=parser.parse_args()
    out=v.base.safe(args.destination);analysis=v.base.safe(args.analysis_root)
    v.require(not out.exists() and not analysis.exists(),'fresh outputs required')
    r=E/'admission-root';auth=r/'evidence/formal-q16a-1'
    launch=v.parse((E/'formal-q16a-continuation-authoring-1/launch-config-2.json').read_bytes())
    request=v.parse(v.read(launch['files']['request']));plan=request['action_inputs']['plan'];v.validate_population(plan)
    phase=Path(request['evidence_root_binding']['absolute_path'])
    for p in (out,analysis):
        v.require(not p.is_relative_to(phase.parent.parent) and not p.is_relative_to(r),'output overlaps retained evidence or qualified repository')
    v.require(not out.is_relative_to(analysis) and not analysis.is_relative_to(out),'output overlap')
    files={key:bound(path) for key,path in dict(AUTHORIZATION=auth/'authorization.json',SIGNATURE=auth/'authorization.json.sig',REQUEST=auth/'request.json',
        ATTEMPT=phase/'stage17-q16a-attempt-v6.json',RESULT=phase/'stage17-action-result-v6.json',COMPLETION=phase/'stage17-q16a-completion-v6.json',
        policy=r/'config/stage17/stage17-operational-evidence-admission-policy-v58.json',historical_journal=E/'journal/stage17-state-journal-000009.json').items()}
    archive=bound(Path(launch['archive']));sidecar=bound(Path(launch['sidecar']))
    v.require(archive['sha256']=='1d81eac6cbfddb9ef2fb155430f065be819fdfc87695d67a19f65d15c676b567','qualified release archive')
    c=dict(schema_version='software-offline-q16a-suffix-analysis/1',repository_root=str(r),evidence_root=str(E),journal_directory=str(E/'journal'),
        analysis_root=str(analysis),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),execution_authority=False,
        files=files,operator_sha256=v.sha(Path(v.__file__).read_bytes()),supervision_sha256=v.base.SUPERVISION_SHA,
        parallel_adapter=bound(v.HERE/'stage17_discovery_validation_parallel_v2.py'),python=bound(Path('/usr/bin/python3.14')),
        pilot_archive=archive,pilot_sidecar=sidecar)
    m,pinned=v.modules(c);prepared=v.prepare(c,m);v.lifecycle(c,m,prepared,pinned)
    extent=m.formal_calibration_v2.plans.validate_plan('Q16a',plan)
    profile=prepared.archive_runtime_profile
    v.require(c['python']['sha256']==profile.python.sha256 and c['python']['size_bytes']==profile.python.size_bytes,'qualified Python binding')
    decode=dataclasses.asdict(m.output_registry_v12._metadata_decode_limits(plan,extent,profile,time.monotonic_ns()+259200*10**9));decode.pop('deadline_ns')
    storage=plan['storage'];g=v.base.GIB
    c['resources']=dict(supervisor_as_bytes=2*g,coordinator_as_bytes=2*g,capture_as_bytes=8*g,worker_count=4,total_memory_bytes=36*g,
        memory_reserve_bytes=8*g,timeout_seconds=259200,metadata_bytes=2*g,filesystem_overhead_bytes=256*1024**2,
        canonical_capture_bytes=storage['analysis_capture_workspace_bytes'],runtime=dict(codec_address_space_bytes=storage['codec_address_space_bytes']),
        custody=dict(max_record_bytes=max(131072,storage['checkpoint_bytes']),max_ledger_records=1000000,max_inventory_files=1000000,max_checkpoint_bytes=storage['checkpoint_bytes']),decoder=decode)
    proof=v.support.scratch_proof(c['resources'])
    v.require(c['resources']['total_memory_bytes']<=extent.declared.memory_bytes,'signed memory ceiling')
    out.mkdir(mode=0o700)
    binding=v.save(out/'analysis-config.json',c,65536);v.config(Path(binding['path']),binding['sha256'])
    report=dict(status='PREPARED_SIGNED_LIFECYCLE_PASS',configuration=binding,scratch_proof=proof,execution_authority=False,phase18_authority=False,
        original_supervisor_unchanged=True,raw_mutation=False,raw_validation_started=False)
    v.save(out/'preparation.json',report,65536);print(json.dumps(report),flush=True)


if __name__=='__main__':main()
