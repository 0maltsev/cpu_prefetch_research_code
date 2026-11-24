"""D206 stand-side failed-capture inspection using the unchanged bounded reader."""
import datetime, hashlib, json, os, pathlib, sys, tempfile
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
R=E/'admission-root';O=E/'discovery-output-r2-1';D=E/'d206-stand-primary-1'
sys.path.insert(0,str(R/'tools'))
import stage17_discovery_validation_v1 as v
assert hashlib.sha256(pathlib.Path(v.__file__).read_bytes()).hexdigest()=='ec5dd7250fa682465ae49ab97ccdf58799611b01f551b2b8da4547a295f5510a'
acceptance=json.loads((D/'owner-acceptance.json').read_bytes())
assert acceptance['policy_id']=='EXT007-RAW-NONE-STAND-PRIMARY-v1' and acceptance['m_dur']==1
assert acceptance['exact_user_reply']=='Approve stand-only raw storage and PC cleanup'
assert hashlib.sha256((D/'proposal.md').read_bytes()).hexdigest()==acceptance['proposal_sha256']
supervisor=json.loads((E/'discovery-supervisor-result-r2-1.json').read_bytes())
assert supervisor['partition_restoration']['verified'] and supervisor['partition_restoration']['partition_absent']
manifest=json.loads((E/'r2-output-inventory.json').read_bytes())
files={f['path']:dict(file_name=f['path'],size_bytes=f['size_bytes'],sha256=f['sha256']) for f in manifest['files'] if not f['path'].startswith('operator/')}
tempfile.tempdir=str(D)
def compact(row):
    return {k:value for k,value in row.items() if value is None or isinstance(value,(int,str,bool)) or k in ('request','begin','end')}
with v.document(O,files['studyhardware.json']) as hardware:
    finals=hardware['native_results_after_cleanup']
    final=finals[9]
    hardware_summary={k:hardware[k] for k in ('restoration_verified','mandatory_failure')}
with v.document(O,files['discovery-c09-control.json']) as control:
    report=dict(recorded_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='FAILED_R2_CAPTURE_09_CONTROL_DIAGNOSIS_ONLY_NO_DURATION_SELECTION',
        custody_policy=acceptance['policy_id'],owner_acceptance_sha256=hashlib.sha256((D/'owner-acceptance.json').read_bytes()).hexdigest(),
        control_binding=files['discovery-c09-control.json'],hardware_binding=files['studyhardware.json'],
        validator_sha256=hashlib.sha256(pathlib.Path(v.__file__).read_bytes()).hexdigest(),
        control_keys=list(control),session=control['session'],final_native_result=final,
        capture_stop_before_publication=control['capture_stop_before_publication'],hardware_summary=hardware_summary,
        controls=[dict(index=i,**compact(row)) for i,row in enumerate(control['controls'])],
        residency=[dict(index=i,**compact(row)) for i,row in enumerate(control['residency'])],
        phase_summaries=[{k:row[k] for k in ('run_id','producer_available','consumer_available','producer_prefix_complete','consumer_prefix_complete','capture_horizon_complete','attempted','accepted','full','consumed_including_drain') if k in row} for row in control['phases']],
        formal_runs_contributed=0,execution_authority=False,duration_selection='UNRESOLVED_INVALID_PARTIAL_STUDY')
with (D/'c09-control-diagnosis.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(report,indent=2))
