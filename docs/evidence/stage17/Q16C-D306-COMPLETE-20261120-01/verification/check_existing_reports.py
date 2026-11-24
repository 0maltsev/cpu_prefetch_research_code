"""Verify final existing report bytes/composition only; never decode raw data."""
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

os.sched_setaffinity(0, {3})
assert os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups()
e = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
ops = e/'d306-continuation-1'; config = ops/'launch-configuration.json'
sha = 'bf817971e193d8e4fa1e1ba0ba947583467561aa95a6a1f64db259571c43d6c0'
assert hashlib.sha256(config.read_bytes()).hexdigest() == sha
sys.path.insert(0, str(ops))
import stage17_q16c_continuation_operator_v1 as io
c = json.loads(config.read_bytes())
sys.path.append(str(Path(c['repository_root'])/'tools'))
for b in c['operator_sources'].values(): io.read(b)
prepared = io.document(io.binding(Path(c['output_root'])/'prepared.json'))
request = io.document(prepared['request']); plan = io.document(prepared['plan'])
root = Path(request['evidence_root_binding']['absolute_path'])
result = io.document(io.binding(e/'d306-study-1/result.json'))
recovery = io.document(io.binding(e/'d306-independent-recovery-1.json'))
assert result['success'] is True and result['errors'] == []
assert [x['role'] for x in result['phases']] == ['authorize','sign-collect','suffix']
assert all(x['exit_code'] == 0 and x['leader_reaped'] is True and
           x['started_monotonic_ns'] < x['completed_monotonic_ns'] < x['deadline_ns'] for x in result['phases'])
assert result['partition_restoration']['verified'] is True and result['partition_restoration']['errors'] == []
assert recovery['verified'] is True and recovery['errors'] == []
assert recovery['signalled_native'] == recovery['signalled_owner'] == []
assert result['native_terminal']['executor_completed'] is True
assert result['native_terminal']['hardware_restoration_verified'] is True
assert result['native_terminal']['executor_quarantined'] is False
assert result['actual_executor_terminal'] == result['native_terminal']['binding']
io.read(result['actual_executor_terminal'])
for report in (result['partition_restoration'], recovery):
    assert [r['cpu'] for r in report['msr_readback']] == [0,1,8]
    assert all(r['matches'] is True and r['expected_hex'] == r['observed_hex'] for r in report['msr_readback'])
assert result['partition_restoration']['compaction_restored'] is True
assert recovery['compaction']['verified'] is True and recovery['compaction']['observed_value'] == 1
assert Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip() == '1'
assert not Path(c['cgroup']).exists()
out = e/'q16c-analysis-1'
finished_binding = io.binding(out/'finalized.json'); finished = io.document(finished_binding)
assert result['completion'] == finished_binding
assert finished['status'] == 'ALL_180_VALID_DESCRIPTIVE_COMPLETE'
assert finished['reused_prefix_reports'] == 86 and finished['new_reports'] == 94 and finished['all_workers_reaped'] is True
done = io.document(finished['completion'])
assert done['status'] == 'ALL_SELECTED_VALID' and done['kind'] == 'SUFFIX94' and done['all_workers_reaped'] is True
assert done['plan_binding'] == prepared['plan'] and len(done['reports']) == 94
assert 0 < done['elapsed_ns'] < 3600*10**9
for ordinal, bound in enumerate(done['reports']):
    io.read(bound)
    receipt = io.document(io.binding(out/f'capture-{ordinal}-process.json'))
    assert receipt['status'] == 'VALID' and receipt['ordinal'] == ordinal
    assert receipt['exit_code'] == 0 and receipt['leader_reaped'] is True and receipt['canonical_spool_removed'] is True
    assert receipt['report'] == bound and 0 < receipt['elapsed_ns'] < 300*10**9
assert len(list((out/'reports').glob('capture-*.json'))) == 94
assert len(list(out.glob('capture-*-process.json'))) == 94
old_completion = io.binding(e/'q16c-prefix-analysis-1/complete.json')
retained = io.document(plan['continuation']['accepted_prefix_manifest'])
old = io.report_records(old_completion, artifact_bindings=retained['reports'])
new = io.report_records(finished['completion'])
collected = io.document(io.binding(Path(c['output_root'])/'collection.json'))
import stage17_q16c_descriptive_calibration_v3 as composition
assert Path(composition.__file__).read_bytes() == (Path(c['candidate_inventory']['path']).parent/
    'tools/stage17_q16c_descriptive_calibration_v3.py').read_bytes()
recomputed = composition.evaluate(io.read(c['original_plan']), plan, old, new, plan_binding=prepared['plan'],
    request_sha256=prepared['request']['sha256'], platform_binding=collected['platform_observations'])
actual = io.read(finished['composition'])
assert actual == json.dumps(recomputed, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode()
assert recomputed['coverage'] == dict(planned=180,valid=180,retained=86,new=94,missing=0,invalid=0)
assert recomputed['platform_strata'] == [dict(regime='UNRECORDED',captures=86),dict(regime='VERIFIED_ZERO',captures=94)]
assert recomputed['homogeneous_platform_evidence'] is False and recomputed['confidence_claim'] is None
assert recomputed['inferential_validity_established'] is False and recomputed['final_matrix_feasibility'] == 'NOT_EVALUATED'
assert recomputed['final_scale_selection'] is None
completion_time = dt.datetime.fromtimestamp((out/'finalized.json').stat().st_mtime, dt.timezone.utc).isoformat()
summary = dict(status='ALL_180_EXISTING_REPORTS_AND_COMPOSITION_VERIFIED',
    checked_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),finalized_file_mtime_utc=completion_time,
    configuration_sha256=sha,coverage=recomputed['coverage'],platform_strata=recomputed['platform_strata'],
    method_id=recomputed['method_id'],collector_method_id=recomputed['collector_method_id'],
    evidence_strength=recomputed['evidence_strength'],
    zero_loss={name:dict(gate=gate['zero_loss_gate'],full_bearing_capture_count=len(gate['full_bearing_original_ordinals']),
                        original_ordinals=gate['full_bearing_original_ordinals']) for name,gate in recomputed['observed_zero_loss'].items()},
    report_hashes_verified=180,reaped_suffix_process_receipts_verified=94,whole_composition_recomputed_from_reports=True,
    raw_decoding_repeated=False,measurements_repeated=False,qualification_repeated=False,
    collection_seconds=(result['phases'][1]['completed_monotonic_ns']-result['phases'][1]['started_monotonic_ns'])/1e9,
    analysis_seconds=(result['phases'][2]['completed_monotonic_ns']-result['phases'][2]['started_monotonic_ns'])/1e9,
    signed_lifecycle_terminal_binding=result['actual_executor_terminal'],native_executor_completed=True,
    native_quarantined=False,restoration_verified=True,independent_recovery_verified=True,
    calibration_freeze_admitted=False,ext007_admitted=False,stage17_complete=False,phase18_authority=False,
    execution_authority=False,final_matrix_feasibility='NOT_EVALUATED',final_scale_selection=None)
files = {}
for name in ('analysis-intent.json','complete.json','calibration-validation.json','finalized.json'):
    p = out/name; raw = p.read_bytes(); assert len(raw) < 2*1024**2
    files['q16c-analysis-1/'+name] = dict(size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),data=base64.b64encode(raw).decode())
print(json.dumps(dict(summary=summary,files=files)),flush=True)
