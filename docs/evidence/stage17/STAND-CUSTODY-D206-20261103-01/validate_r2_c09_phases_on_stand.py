"""Reconcile retained failed R2 capture phases under accepted D206 primary custody."""
import dataclasses,datetime,hashlib,json,os,pathlib,sys,tempfile,traceback
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19')
R=E/'admission-root';O=E/'discovery-output-r2-1';D=E/'d206-stand-primary-1'
sys.path.insert(0,str(R/'tools'));import stage17_discovery_validation_v1 as v
assert hashlib.sha256(pathlib.Path(v.__file__).read_bytes()).hexdigest()=='ec5dd7250fa682465ae49ab97ccdf58799611b01f551b2b8da4547a295f5510a'
approval=json.loads((D/'owner-acceptance.json').read_bytes());assert approval['policy_id']=='EXT007-RAW-NONE-STAND-PRIMARY-v1' and approval['m_dur']==1
assert hashlib.sha256((D/'proposal.md').read_bytes()).hexdigest()==approval['proposal_sha256']
supervisor=json.loads((E/'discovery-supervisor-result-r2-1.json').read_bytes());assert supervisor['partition_restoration']['verified'] and supervisor['partition_restoration']['partition_absent']
manifest=json.loads((E/'r2-output-inventory.json').read_bytes())
files={f['path']:dict(file_name=f['path'],size_bytes=f['size_bytes'],sha256=f['sha256']) for f in manifest['files'] if not f['path'].startswith('operator/')}
request_path=R/'evidence/discovery-r2-fresh/request.json';request_raw=request_path.read_bytes()
assert hashlib.sha256(request_raw).hexdigest()=='5c2da9d3712bd7051706f8ce4767d280438d1765354d7133aeaecd71cb75a871'
inputs=json.loads(request_raw)['action_inputs'];plan=v.contract.validate_plan(inputs['plan']);capture=plan.captures[9]
assert plan.sha256=='f43cb76f89a095ea27f2b8c9c6b08188fee72768844fc0b3848051a8f6a549e7'
resources=inputs['native_captures'][9]['resources'];monitoring=inputs['native_captures'][9]['monitoring'];tempfile.tempdir=str(D)
report=dict(started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='FAILED_CAPTURE_09_PHASE_INTEGRITY_ONLY',
 custody_policy=approval['policy_id'],owner_acceptance_sha256=hashlib.sha256((D/'owner-acceptance.json').read_bytes()).hexdigest(),
 request_sha256=hashlib.sha256(request_raw).hexdigest(),validator_sha256=hashlib.sha256(pathlib.Path(v.__file__).read_bytes()).hexdigest(),
 duration_selection='UNRESOLVED_INVALID_PARTIAL_STUDY',formal_runs_contributed=0,execution_authority=False,phases=[])
try:
    with v.document(O,files['studyhardware.json']) as hardware:final=hardware['native_results_after_cleanup'][9]
    with v.document(O,files['discovery-c09-control.json']) as c:
        try:v.validate_capture(O,c,final,capture,resources,monitoring,inputs['hardware_control'])
        except v.ValidationError as error:report['full_capture_validation']=dict(status='REJECTED',reason=str(error))
        else:raise AssertionError('failed capture unexpectedly passed')
        assert report['full_capture_validation']['reason']=='mandatory session stop'
        arena=v.Arena(capture)
        for name,want in zip(('prepared_content_sha256','ordered_index_sha256','address_delta_sha256'),arena.hashes):v.exact(c['arena'][name],want,'arena '+name)
        v.exact(c['arena']['publication_content_sha256'],arena.hashes[0],'published arena')
        for i,name in enumerate(('warmup','measurement')):
            s=c['session'];identity=capture.warmup if i==0 else capture.measurement
            result=v.validate_phase(O,c['phases'][i],s[name],s[name+'_drain'],run_id=identity.run_id,
                phase_origin=s['origins'][i],clock_origin=c['clock_origin']['absolute_nanoseconds'],
                duration_ns=v.contract.WARMUP_NS if i==0 else capture.measurement_ns,
                attempt_capacity=capture.budget.warmup_attempt_capacity if i==0 else capture.budget.measurement_attempt_capacity,
                drain_capacity=capture.budget.drain_attempt_capacity,initial_checksum=resources['initial_consumer_state'],
                arena=arena,reset_required=i==0,arena_address=c['regions'][0]['address'])
            report['phases'].append(dict(phase=name,status='PASS',result=dataclasses.asdict(result)))
            print('PHASE_RECONCILED',name,flush=True)
        report['status']='FAILED_CAPTURE_PHASES_RECONCILED_NOT_VALID_CAPTURE'
except Exception as error:
    report.update(status='PHASE_RECONCILIATION_REJECTED',error=str(error),traceback=traceback.format_exc())
report['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (D/'c09-phase-validation.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(report,indent=2),flush=True)
sys.exit(0 if report['status']=='FAILED_CAPTURE_PHASES_RECONCILED_NOT_VALID_CAPTURE' else 1)
