"""D307 finite owner-only metadata preparation; no hardware, raw decode or run.

The actual qualified Q16c CLI authenticates historical signatures, all six
qualifications, original Q16a/Q16b compatibility, schedules and archive custody.
Only previously validated report bytes are recomposed afterwards.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time
import types

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32')
OPS = E/'d306-continuation-1'
CONFIG_SHA = 'bf817971e193d8e4fa1e1ba0ba947583467561aa95a6a1f64db259571c43d6c0'
BOOT = '4c08cd05-b362-49dd-b37f-629e9c7ad79a'
NATIVE = '7b7c263cb850690cf333df0d196b18c875b4a53c'
WORKER = 'bc064c13afd7eb5142ae8ee434e95962e9b3fc3095c6c159d83376c3e7e8c019'
INVENTORY = '828fe1a3482b4b6c9d7249582648be43e920051033f103808e0fc7644362bf8a'


def require(value, message):
    if not value: raise ValueError('D307 freeze preparation: '+message)


def bind(p):
    import stat
    p = Path(p)
    require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)), 'canonical metadata path')
    fd = os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 32*1024**2, 'bounded regular metadata')
        raw = f.read(before.st_size+1)
        stamp = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(stamp(before) == stamp(os.fstat(f.fileno())) == stamp(p.stat(follow_symlinks=False))
                and len(raw) == before.st_size, 'stable original metadata')
    return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def load_io():
    raw = (OPS/'launch-configuration.json').read_bytes()
    require(hashlib.sha256(raw).hexdigest() == CONFIG_SHA, 'exact completed D306 configuration')
    c = json.loads(raw); b = c['operator_sources']['stage17_q16c_continuation_operator_v1.py']
    source = Path(b['path']).read_bytes()
    require(b == bind(Path(b['path'])) and Path(b['path']).parent == OPS, 'actual completed operator bytes')
    io = types.ModuleType('d307_frozen_q16c_operator'); io.__file__ = b['path']
    exec(compile(source,b['path'],'exec'), io.__dict__)
    for member in c['operator_sources'].values(): io.read(member)
    return io,c


def check_q16c(io,c,prepared):
    result_binding = io.binding(E/'d306-study-1/result.json'); result = io.document(result_binding)
    recovery_binding = io.binding(E/'d306-independent-recovery-1.json'); recovery = io.document(recovery_binding)
    require(result['success'] is True and result['errors'] == [], 'completed original producer')
    require([p['role'] for p in result['phases']] == ['authorize','sign-collect','suffix']
        and all(p['exit_code'] == 0 and p['leader_reaped'] is True
                and p['started_monotonic_ns'] < p['completed_monotonic_ns'] < p['deadline_ns'] for p in result['phases']),
        'original finite completed/reaped phases')
    require(result['native_terminal']['executor_completed'] is True
        and result['native_terminal']['executor_quarantined'] is False
        and result['native_terminal']['hardware_restoration_verified'] is True, 'actual native completion')
    require(result['partition_restoration']['verified'] is True and result['partition_restoration']['errors'] == []
        and recovery['verified'] is True and recovery['errors'] == [], 'both verified restorations')
    terminal = io.document(result['actual_executor_terminal'])
    require(terminal['authorization_sha256'] == hashlib.sha256(prepared.authorization_bytes).hexdigest()
        and terminal['request_sha256'] == hashlib.sha256(prepared.request_bytes).hexdigest()
        and terminal['attempt_id'] == prepared.request['attempt_id'], 'actual signed native terminal identity')
    root = E/'q16c-analysis-1'; final_binding = io.binding(root/'finalized.json'); final = io.document(final_binding)
    require(result['completion'] == final_binding and final['status'] == 'ALL_180_VALID_DESCRIPTIVE_COMPLETE'
        and final['all_workers_reaped'] is True and final['reused_prefix_reports'] == 86 and final['new_reports'] == 94,
        'actual180 completion linkage')
    done = io.document(final['completion'])
    require(done['status'] == 'ALL_SELECTED_VALID' and done['kind'] == 'SUFFIX94'
        and done['all_workers_reaped'] is True and len(done['reports']) == 94
        and 0 < done['elapsed_ns'] < 3600*10**9, 'complete original94 independent validation')
    for ordinal,b in enumerate(done['reports']):
        io.read(b); receipt = io.document(io.binding(root/f'capture-{ordinal}-process.json'))
        require(receipt['report'] == b and receipt['ordinal'] == ordinal and receipt['status'] == 'VALID'
            and receipt['exit_code'] == 0 and receipt['leader_reaped'] is True and receipt['canonical_spool_removed'] is True,
            'actual independent report and quiescent child')
    plan = prepared.request['action_inputs']['plan']; prefix = io.document(plan['continuation']['accepted_prefix_manifest'])
    old = io.report_records(io.binding(E/'q16c-prefix-analysis-1/complete.json'),artifact_bindings=prefix['reports'])
    new = io.report_records(final['completion'])
    collected = io.document(io.binding(Path(c['output_root'])/'collection.json'))
    d = io.document(io.binding(Path(c['output_root'])/'prepared.json'))
    import stage17_q16c_descriptive_calibration_v3 as composer
    recomputed = composer.evaluate(io.read(c['original_plan']),plan,old,new,plan_binding=d['plan'],
        request_sha256=d['request']['sha256'],platform_binding=collected['platform_observations'])
    raw = json.dumps(recomputed,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    require(raw == io.read(final['composition']), 'exact whole180 composition from original reports')
    return final['composition'],dict(producer_result=result_binding,independent_recovery=recovery_binding,
        finalized=final_binding,analysis_completion=final['completion'],native_terminal=result['actual_executor_terminal'],
        report_hashes_verified=180,new_process_receipts_verified=94,raw_decoding_repeated=False)


def authenticate():
    require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(), 'actual evidence owner')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'actual original boot')
    io,c = load_io()
    require(not Path(c['cgroup']).exists() and Path('/proc/sys/vm/compact_unevictable_allowed').read_text().strip() == '1', 'stand restored before metadata work')
    cli,d,args = io.common(c)
    historical = io.binding(cli.base.latest_journal(E))
    args['journal'] = Path(historical['path'])
    # prepare_formal_retention/admit_formal_retention perform metadata admission,
    # not execute_once or independent raw decoding.
    prepared = cli.prepare_formal_retention(**args)
    require(set(prepared.validation.resolutions) == {f'S17-EXT-{i:03d}' for i in range(1,7)}, 'historical journal through six qualifications')
    current = prepared.validation.resolutions['S17-EXT-006'].semantic_context
    require([current['source_revision'],current['release_artifact_sha256'],current['inventory_sha256']] ==
        [NATIVE,WORKER,INVENTORY], 'actual unchanged qualified native source')
    require(prepared.validation.latest_journal_sha256 == historical['sha256'], 'actual fixed original journal')
    archive = cli.admit_formal_retention(prepared,Path(prepared.request['evidence_root_binding']['absolute_path']))
    require(len(archive['captures']) == 94 and archive['inverse_readback_performed'] is False, 'all94 custody records, no raw inverse')
    sources = {phase:io.document(prepared.request['action_inputs']['prerequisite_bindings'][phase.lower()+'_validation'])['composition']
               for phase in ('Q16a','Q16b')}
    q16c,completion = check_q16c(io,c,prepared); sources['Q16c'] = q16c
    predecessors = [cli.base._resolution_binding(prepared.validation.resolutions[f'S17-EXT-{i:03d}']) for i in range(1,7)]
    return io,sources,dict(schema_version='cpu-prefetch-stage17-descriptive-freeze-provenance/1',
        status='SIGNED_LINEAGE_CUSTODY_AND_REPORTS_VERIFIED',stand_id=prepared.request['stand_id'],boot_id=BOOT,
        source_records=sources,predecessor_resolutions=predecessors,historical_journal=historical,
        qualified_source_revision=NATIVE,qualified_worker=io.binding(Path(current['release_artifact_path'])),
        qualified_inventory=c['candidate_inventory'],completed_configuration=io.binding(OPS/'launch-configuration.json'),
        original_handoffs={p:prepared.request['action_inputs']['prerequisite_bindings'][p.lower()+'_validation'] for p in ('Q16a','Q16b')},
        q16c_completion=completion,archive_scope=archive['scope_bindings'],archive_capture_count=94,
        completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),
        execution_authority=False,phase18_authority=False),prepared.validation.resolutions['S17-EXT-003'].semantic_context['trust']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet-sha256',required=True); parser.add_argument('--output-root',type=Path,required=True)
    a = parser.parse_args(); here = Path(__file__).resolve().parent
    require(os.getresuid() == (1000,)*3 and os.getresgid() == (1000,)*3 and not os.getgroups(), 'actual owner')
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2); os.sched_setaffinity(0,{3})
    signal.alarm(900)
    manifest_path = here/'manifest.json'; require(bind(manifest_path)['sha256'] == a.packet_sha256, 'actual administrative packet')
    packet = json.loads(manifest_path.read_bytes())
    require(packet['schema_version'] == 'software-d307-descriptive-freeze-packet/1' and packet['execution_authority'] is False, 'metadata-only packet')
    require({row['path'] for row in packet['files']} == {'prepare_stage17_descriptive_freeze_v1.py',
        'stage17_descriptive_freeze_v1.py','stage17-ext007-descriptive-freeze-v1.schema.json'}
        and len(packet['files']) == 3, 'exact three-member metadata implementation')
    for row in packet['files']:
        p = here/row['path']; require(p.is_relative_to(here) and '..' not in Path(row['path']).parts, 'flat owned packet member')
        require((bind(p)['size_bytes'],bind(p)['sha256']) == (row['size_bytes'],row['sha256']), 'exact source packet')
    require(a.output_root.parent == E and not a.output_root.exists() and not a.output_root.is_symlink(), 'exclusive administrative output')
    a.output_root.mkdir(mode=0o700); started = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        io,sources,proof,trust = authenticate()
        # The original qualified imports are already loaded. Add only the
        # separately bound new format after historical preparation completed.
        raw = (here/'stage17_descriptive_freeze_v1.py').read_bytes()
        module = types.ModuleType('d307_new_descriptive_freeze'); module.__file__ = str(here/'stage17_descriptive_freeze_v1.py')
        exec(compile(raw,module.__file__,'exec'),module.__dict__)
        proof['source_code_bindings'] = {n:bind(here/n) for n in ('prepare_stage17_descriptive_freeze_v1.py','stage17_descriptive_freeze_v1.py')}
        proof['administrative_packet'] = bind(manifest_path)
        proof_binding = io.save(a.output_root/'provenance.json',proof)
        value = module.build(record_id='CPU-PREFETCH-V5-EXT007-DESCRIPTIVE-FREEZE-1',
            created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z'),
            source_records=sources,provenance_record=proof_binding,predecessor_resolutions=proof['predecessor_resolutions'])
        schema = json.loads((here/'stage17-ext007-descriptive-freeze-v1.schema.json').read_bytes())
        from jsonschema import Draft202012Validator
        Draft202012Validator(schema).validate(value)
        freeze_binding = io.save(a.output_root/'calibration-freeze.json',value)
        signed = subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n',
            'stage17-owner-acceptance',freeze_binding['path']],capture_output=True,text=True,timeout=30)
        require(signed.returncode == 0, 'actual owner freeze signature')
        from stage17_phase_controller_v2 import _verify_signature
        # Reuse the actual trust returned by this same qualified preparation.
        _verify_signature(io.read(freeze_binding),Path(freeze_binding['path']+'.sig'),trust)
        completion = dict(status='DESCRIPTIVE_DATA_FREEZE_PUBLISHED',started_at_utc=started,
            completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),freeze=freeze_binding,
            signature=io.binding(Path(freeze_binding['path']+'.sig')),provenance=proof_binding,
            original_report_count=1008,operational_ext007_admitted=False,raw_decoding_repeated=False,
            new_measurements=0,execution_authority=False,phase18_authority=False)
        io.save(a.output_root/'complete.json',completion); print(json.dumps(completion),flush=True)
    except BaseException as error:
        raw = json.dumps(dict(type=type(error).__name__,message=str(error),execution_authority=False,phase18_authority=False)).encode()
        with (a.output_root/'failure.json').open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
        raise


if __name__ == '__main__': main()
