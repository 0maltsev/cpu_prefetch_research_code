"""Cold failed-prefix reconciliation only, using the existing independent validator."""
import dataclasses
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

prep = Path(__file__).resolve().parent
repo = prep.parent.parent
sys.path.insert(0, str(repo / 'tools'))
import stage17_discovery_validation_v1 as validator
import stage17_discovery_contract_v1 as contract

custody_path = prep / 'stopped-copy-verification.json'
custody = json.loads(custody_path.read_text())
assert custody['status'] == 'PASS_ORIGINAL_BYTE_SECOND_COPY' and len(custody['files']) == 12
root = Path(custody['pc_root'])
inputs_path = prep / 'v19-plan-draft-2/action-inputs.json'
inputs = json.loads(inputs_path.read_text())
capture = contract.validate_plan(inputs['plan']).captures[0]
resources = inputs['native_captures'][0]['resources']
monitoring = inputs['native_captures'][0]['monitoring']
binding = next(f for f in custody['files'] if f['path'] == 'discovery-c00-control.json')
binding = dict(binding, file_name=binding['path'])
report = dict(scope='FAILED_WARMUP_PREFIX_ONLY', started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    custody_verification_sha256=hashlib.sha256(custody_path.read_bytes()).hexdigest(),
    action_inputs_sha256=hashlib.sha256(inputs_path.read_bytes()).hexdigest(),
    validator_sha256=hashlib.sha256(Path(validator.__file__).read_bytes()).hexdigest(),
    duration_selection='UNRESOLVED_NOT_ELIGIBLE', formal_runs_contributed=0, execution_authority=False)
try:
    with validator.document(root, binding) as control:
        session = control['session']
        report['session_stop'] = session['stop']
        report['warmup_workers'] = session['warmup']
        report['warmup_drain'] = session['warmup_drain']
        report['measurement_origin'] = session['origins'][1]
        try:
            validator.validate_capture(root, control, {}, capture, resources, monitoring, inputs['hardware_control'])
        except validator.ValidationError as error:
            report['full_capture_validation'] = dict(status='REJECTED', reason=str(error))
        else:
            raise AssertionError('failed capture unexpectedly accepted')
        assert report['full_capture_validation']['reason'] == 'mandatory session stop'
        arena = validator.Arena(capture)
        for name, expected in zip(('prepared_content_sha256', 'ordered_index_sha256', 'address_delta_sha256'), arena.hashes):
            validator.exact(control['arena'][name], expected, 'failed prefix arena ' + name)
        validator.exact(control['arena']['publication_content_sha256'], arena.hashes[0], 'publication arena hash')
        result = validator.validate_phase(root, control['phases'][0], session['warmup'], session['warmup_drain'],
            run_id=capture.warmup.run_id, phase_origin=session['origins'][0],
            clock_origin=control['clock_origin']['absolute_nanoseconds'], duration_ns=contract.WARMUP_NS,
            attempt_capacity=capture.budget.warmup_attempt_capacity, drain_capacity=capture.budget.drain_attempt_capacity,
            initial_checksum=resources['initial_consumer_state'], arena=arena, reset_required=False,
            arena_address=control['regions'][0]['address'])
        report['prefix_reconciliation'] = dict(status='PASS', result=dataclasses.asdict(result),
            reset_required=False, reset_reason='failed warmup stopped before reset/measurement; no successful-session claim')
        report['status'] = 'FAILED_STUDY_PREFIX_RECONCILED'
except Exception as error:
    report['status'] = 'FAILED_PREFIX_VALIDATION'
    report['error'] = str(error)
    report['traceback'] = traceback.format_exc()
report['finished_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
with (prep / 'stopped-prefix-validation.json').open('x') as out:
    json.dump(report, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
print(json.dumps(report, indent=2))
sys.exit(0 if report['status'] == 'FAILED_STUDY_PREFIX_RECONCILED' else 1)
