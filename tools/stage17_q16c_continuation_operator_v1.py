"""D288 metadata construction, one signed94-capture action and final composition.

Run only through the bound root supervisor's owner handoff. Completed raw
validation reports are reused. This operator never qualifies or retries.
"""
import argparse
import copy
import dataclasses
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

NS = 10**9


def require(ok, message):
    if not ok:
        raise ValueError('D288 continuation operator: ' + message)


def read(b):
    p = Path(b['path'])
    require(p.is_absolute() and all(not q.is_symlink() for q in (p, *p.parents)), 'canonical nonsymlink input')
    require(type(b['size_bytes']) is int and 0 < b['size_bytes'] <= 32 * 1024**2, 'bounded metadata')
    from stat import S_ISREG
    fd = os.open(p, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        require(S_ISREG(before.st_mode) and before.st_size == b['size_bytes'], 'regular bound metadata')
        data = f.read(b['size_bytes'] + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(stamp(before) == stamp(os.fstat(f.fileno())) == stamp(p.stat(follow_symlinks=False)), 'metadata changed')
    require(len(data) == b['size_bytes'] and hashlib.sha256(data).hexdigest() == b['sha256'], 'metadata digest')
    return data


def binding(path):
    p = Path(path)
    raw = p.read_bytes()
    result = dict(path=str(p), size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    read(result)
    return result


def document(b):
    return json.loads(read(b))


def save(path, value):
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    if os.geteuid() == 0:
        os.chown(path, 1000, 1000)
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return binding(path)


def cli_for(c, configured=False):
    root = Path(c['repository_root'])
    sys.path.insert(0, str(root / 'tools'))
    import stage17_q16c_descriptive_administration_v4 as administration
    cli = administration.make_cli()
    if configured:
        packet = Path(c['packet_root'])
        cli.controller.configure_historical_inputs(document(binding(packet / 'historical-inputs.json')), packet)
        cli.controller.configure_verified_descriptor(read(binding(packet / 'archive-overlay.json')), packet)
        cli.controller.configure_execution_window(document(binding(Path(c['evidence_root']) / 'execution-window-proof.json')))
        cli.controller.configure_source_reuse(document(binding(packet / 'source-reuse.json')))
    cli.activate()
    return cli


def common(c, *, author=False):
    root, evidence = Path(c['repository_root']), Path(c['evidence_root'])
    result = dict(repository_root=root, pilot_archive=Path(c['archive']['path']), pilot_sidecar=Path(c['sidecar']['path']))
    if author:
        return dict(result, evidence_root=evidence)
    cli = cli_for(c, configured=True)
    d = document(binding(Path(c['output_root']) / 'prepared.json'))
    return cli, d, dict(result, operational_evidence_root=evidence,
        journal=cli.base.latest_journal(evidence), journal_directory=evidence / 'journal',
        authorization_path=Path(d['authorization']['path']), signature_path=Path(d['signature']['path']))


def comparison(old, current, admission, handoff):
    roots = {side: Path(value['archive_bundle_root']) for side, value in (('original', old), ('current', current))}
    indexes = {side: admission._inventory(document(binding(root / 'BUNDLE_INVENTORY.json'))) for side, root in roots.items()}
    names = admission._source_names(indexes['original'])
    require(names == admission._source_names(indexes['current']), 'full native source closure')
    def release(side, value):
        root = roots[side]
        return dict(source_revision=value['source_revision'], bundle_root=str(root),
            worker=binding(root / 'release/bin/cpu_prefetch_runner'), bundle_inventory=binding(root / 'BUNDLE_INVENTORY.json'),
            formal_codegen=binding(root / 'build-provenance/formal_codegen_report.json'))
    def row(name):
        return dict(relative_path=name, **{side: binding(root / name) for side, root in roots.items()})
    return dict(original=release('original', old), current=release('current', current),
        source_comparisons=[row(name) for name in sorted(names)],
        queue_libraries={side: binding(root / handoff.QUEUE) for side, root in roots.items()},
        project_headers=[row(name) for name in handoff.HEADERS])


def construct(c, deadline):
    cli = cli_for(c)
    root, evidence, packet = (Path(c[k]) for k in ('repository_root', 'evidence_root', 'packet_root'))
    validation = cli._validation(root, evidence, pilot_archive=Path(c['archive']['path']), pilot_sidecar=Path(c['sidecar']['path']))
    require(set(validation.resolutions) == {f'S17-EXT-{i:03d}' for i in range(1, 7)}
        and validation.current_state == 'READY_FOR_STAGE17_PHASE_AUTHORIZATION', 'six actual fresh qualifications')
    current = validation.resolutions['S17-EXT-006'].semantic_context
    require(current['source_revision'] == c['source_revision'] and current['release_artifact_sha256'] == c['worker']['sha256'],
        'actual repaired qualified release')
    old = document(c['original_context'])['resolutions']
    import stage17_q16c_admission_limits_v3 as limits
    import stage17_q16c_prefix_compatibility_v1 as compatibility
    import stage17_q16c_scientific_sources_v1 as science
    import stage17_q16c_continuation_plan_v1 as builder
    handoffs = limits.make_handoffs()
    original = old['S17-EXT-006']['semantic_context']
    proof = comparison(original, current, limits.ADMISSION, handoffs[0])
    proof.pop('queue_libraries'); proof.pop('project_headers')
    roots = {side: Path(value['archive_bundle_root']) for side, value in (('original', original), ('current', current))}
    def rows(names):
        return [dict(relative_path=name, **{side: binding(base / name) for side, base in roots.items()}) for name in sorted(names)]
    scientific_packet=c['original_scientific_packet']
    indexes={side:limits.ADMISSION._inventory(document(binding(base/'BUNDLE_INVENTORY.json'))) for side,base in roots.items()}
    dependency_reader=limits.ADMISSION.BoundReader()
    deps=science.bindings(roots['original'],roots['current'],indexes['original'],indexes['current'],
        scientific_packet['manifest'],dependency_reader)
    dependency_reader.finish()
    proof.update(schema_version=compatibility.SCHEMA, decision='D288', stand_id='CPU-PREFETCH-V5', boot_id=c['boot_id'],
        parent_plan_sha256=c['original_plan']['sha256'], libraries=rows(compatibility.LIBRARIES), scientific_dependencies=deps,
        original_scientific_packet=scientific_packet,
        platform_manifests=dict(original=binding(roots['original'].parents[1] / 'ext004-authoring-records-1/platform-manifest.json'),
            current=binding(evidence / 'ext004-authoring-records-1/platform-manifest.json')),
        execution_authority=False, phase18_authority=False)
    cb = save(packet / 'prefix-compatibility.json', proof)
    prefix = binding(evidence / 'q16c-prefix-analysis-1/accepted-prefix.json')
    plan = builder.construct(document(c['prospective_inputs']), read(c['original_plan']),
        accepted_prefix_manifest=prefix, compatibility_manifest=cb)
    pb = save(packet / 'plan.json', plan)
    cli.controller.contract.validate_plan('Q16c', plan)
    history = document(c['history_export'])
    h = {phase: document(history[phase + '_context']) for phase in ('q16a', 'q16b')}
    history_rows = {}
    for phase, handoff in zip(('q16a', 'q16b'), handoffs, strict=True):
        old_release = h[phase]['resolutions']['S17-EXT-006']['semantic_context']
        proof = comparison(old_release, current, handoff.admission, handoffs[0])
        proof.update(schema_version=handoff.SCHEMA, scope=dict(decision='D288', purpose=handoff.PURPOSE,
            stand_id=plan['stand_id'], boot_id=c['boot_id']), plan=pb,
            handoff=history['q16a_handoff'] if phase == 'q16a' else c['q16b_handoff'], native_geometry=c['native_geometry'],
            platform_manifests=dict(original=binding(Path(old_release['archive_bundle_root']).parents[1] / 'ext004-authoring-records-1/platform-manifest.json'),
                current=binding(evidence / 'ext004-authoring-records-1/platform-manifest.json')),
            execution_authority=False, phase18_authority=False)
        proof['original_plan' if phase == 'q16a' else 'parent_plan'] = history['q16a_plan'] if phase == 'q16a' else c['q16b_parent_plan']
        row = dict(historical_context=save(packet / (phase + '-context.json'), h[phase]),
            compatibility=save(packet / (phase + '-compatibility.json'), proof))
        if phase == 'q16a':
            row['original_plan'] = history['q16a_plan']
        history_rows[phase] = row
    save(packet / 'historical-inputs.json', dict(schema_version='cpu-prefetch-stage17-q16c-descriptive-historical-inputs/2', **history_rows, boot_id=c['boot_id'],
        execution_authority=False, phase18_authority=False))
    reuse = dict(document(c['incident_reuse_inputs']), accepted_prefix_manifest=prefix)
    save(packet / 'source-reuse.json', reuse)
    original_request = document(c['original_request'])
    prerequisites = copy.deepcopy(original_request['action_inputs']['prerequisite_bindings'])
    prerequisites['schedule_sources'] = prerequisites['schedule_sources'][172:]
    old_registry = document(prerequisites['namespace_registry'])
    registrations = old_registry['schedule_namespaces'][172:]
    prerequisites['namespace_registry'] = save(packet / 'namespace-registry.json',
        dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1', plan_sha256=pb['sha256'],
            stand_id=plan['stand_id'], phase_identities=[item['capture'][phase] for item in plan['captures'] for phase in ('warmup', 'measurement')],
            schedule_namespaces=registrations, execution_authority=False))
    q4 = validation.resolutions['S17-EXT-004'].semantic_context
    q5 = validation.resolutions['S17-EXT-005'].semantic_context['q15_w']
    inputs = dict(plan=plan, hardware_control=dict(mapping_id=q4['hardware_mapping']['mapping_id'],
        q15_w_result_sha256=q5['result_sha256'], prestate=q5['request']['action_inputs']['prestate']), prerequisite_bindings=prerequisites)
    configured = cli_for(c, configured=True)
    configured.controller._validate_inputs(dict(action_id='Q16c', stand_id=plan['stand_id'], action_inputs=inputs), validation)
    ab = save(packet / 'action-inputs.json', inputs)
    out = Path(c['output_root']); out.mkdir(mode=0o700)
    require(time.monotonic_ns() < deadline, 'original1200s preparation ceiling')
    return save(out / 'constructed.json', dict(plan=pb, action_inputs=ab, status='UNSIGNED_INPUTS_VALIDATED',
        execution_authority=False, phase18_authority=False))


def sign_collect(c, deadline, witness_fd):
    # The24860s collection clock already runs, including this single signing/admission.
    cli = cli_for(c, configured=True)
    root, evidence = Path(c['repository_root']), Path(c['evidence_root'])
    out = Path(c['output_root']); built = document(binding(out / 'constructed.json')); plan = document(built['plan'])
    require(built['status'] == 'UNSIGNED_INPUTS_VALIDATED', 'completed unsigned preparation')
    program = Path(c['program_root']); executor = cli.controller.make_executor()
    limits = executor.custody_limits(plan['storage'], min(deadline, time.monotonic_ns() + 120 * NS))
    with executor.custody.ProgramStore(program, scope_sha256=plan['storage']['program_scope_sha256'],
            family_id=built['plan']['sha256'], limits=limits) as store:
        require(not store._capture_pending and all(s['kind'] == 'RELEASED' for s in store._states.values()), 'quiescent retained program')
        before = copy.deepcopy(store._families); tip = dataclasses.asdict(store.ledger_binding())
        require(built['plan']['sha256'] not in before, 'unused fresh family')
        store.prepare_family(built['plan']['sha256'])
        require(set(store._families) == set(before) | {built['plan']['sha256']}
            and all(store._families[k] == value for k, value in before.items()), 'retained families unchanged')
        save(out / 'registration.json', dict(before=tip, after=dataclasses.asdict(store.ledger_binding()),
            new_family_id=built['plan']['sha256'], execution_authority=False))
    authroot = root / 'evidence/formal-q16c-d292-1'; authroot.mkdir(mode=0o700)
    author = common(c, author=True); prefix = 'CPU-PREFETCH-V5-V31-Q16C'
    req = cli.author_formal_request(**author, action_id='Q16c', action_inputs_path=Path(built['action_inputs']['path']),
        request_id=prefix+'-REQUEST-1', authorization_id=prefix+'-AUTH-1', attempt_id=prefix+'-ATTEMPT-1',
        session_id=prefix+'-SESSION-1', output_root=program/'working'/built['plan']['sha256'], destination=authroot/'request.json')
    # Subsecond issue precision prevents losing a full second by truncation.
    now = dt.datetime.now(dt.timezone.utc)
    auth = cli.author_formal_authorization(**author, request_path=req, actor='maltsev.oiu@phystech.edu', reviewer='OWNER',
        issued_at_utc=now.isoformat().replace('+00:00','Z'),
        expires_at_utc=(now+dt.timedelta(seconds=24860)).isoformat().replace('+00:00','Z'), destination=authroot/'authorization.json')
    signed = subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(auth)],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    save(out/'signing-result.json',dict(exit_code=signed.returncode,stdout=signed.stdout.decode(errors='replace'),stderr=signed.stderr.decode(errors='replace')))
    require(signed.returncode == 0, 'owner signature failed')
    d = dict(plan=built['plan'], request=binding(req), authorization=binding(auth), signature=binding(Path(str(auth)+'.sig')),
        worker=c['worker'], execution_authority=False, phase18_authority=False)
    save(out/'prepared.json',d)
    import stage17_q16c_compaction_integration_v2 as guarded
    witness = guarded.ReadOnlyWitness(document(binding(evidence/'platform-guard-1/witness.json')), witness_fd)
    class FiniteObservations(guarded.Observations):
        def before_capture(self,ordinal):
            if ordinal==0:
                require(time.monotonic_ns()+24560*NS<deadline,'full94-capture envelope before first native authorization')
            return super().before_capture(ordinal)
    observations = FiniteObservations(witness,evidence/'platform-observations-1',request_sha256=d['request']['sha256'],
        plan_sha256=d['plan']['sha256'],capture_count=94,program_root=program,
        program_scope_sha256=plan['storage']['program_scope_sha256'])
    cli.controller.configure_platform_observations(observations)
    # execute_formal performs the one ordinary signed admission before arming.
    require(time.monotonic_ns() + 24560*NS < deadline, '300s initial collection setup allowance exhausted')
    result = cli.execute_formal(repository_root=root,operational_evidence_root=evidence,journal=cli.base.latest_journal(evidence),
        journal_directory=evidence/'journal',authorization_path=auth,signature_path=Path(str(auth)+'.sig'),
        pilot_archive=Path(c['archive']['path']),pilot_sidecar=Path(c['sidecar']['path']))
    require(observations.next_ordinal == 94 and len(observations.metadata_bindings) == 1, 'all94 guarded custody checkpoints')
    require(time.monotonic_ns() < deadline, 'original24860s collection ceiling')
    return save(out/'collection.json',dict(result=str(result),platform_observations=observations.metadata_bindings[0],
        actual_request=d['request'],execution_authority=False,phase18_authority=False))


def suffix(c, deadline):
    evidence = Path(c['evidence_root'])
    require(document(binding(evidence/'q16c-study-1/partition-restoration.json'))['verified'] is True,
        'actual restoration before suffix analysis')
    cli,d,args = common(c)
    prepared = cli.prepare_formal_retention(**args)
    plan = prepared.request['action_inputs']['plan']; phase = Path(prepared.request['evidence_root_binding']['absolute_path'])
    verified = cli.admit_formal_retention(prepared, phase)
    import stage17_q16c_analysis_v2 as analysis
    import stage17_q16c_descriptive_calibration_v3 as composition
    extent = cli.controller.contract.validate_plan('Q16c',plan)
    decoder = cli.registry._metadata_decode_limits(plan,extent,prepared.archive_runtime_profile,deadline)
    completed = analysis.analyze_verified(plan,verified,prepared.archive_runtime_profile,decoder,
        prepared.request['action_inputs']['hardware_control'],evidence/'q16c-analysis-1',kind='SUFFIX94',plan_binding=d['plan'],
        global_deadline_ns=deadline,retained_failed_scratch_bytes=c['retained_failed_scratch_bytes'],
        started_monotonic_ns=deadline-3600*NS)
    def records(done,prefix):
        result=[]
        for ordinal,b in enumerate(document(done)['reports']):
            raw=read(b)
            result.append(dict(capture_ordinal=ordinal,validity='VALID',report_utf8_bytes=raw,
                report_binding=dict(artifact_id=f'Q16C-D288-{prefix}-{ordinal:04d}',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
        return result
    old=records(binding(evidence/'q16c-prefix-analysis-1/complete.json'),'PREFIX')
    new=records(completed,'SUFFIX')
    collected=document(binding(Path(c['output_root'])/'collection.json'))
    composed=composition.evaluate(read(c['original_plan']),plan,old,new,plan_binding=d['plan'],
        request_sha256=d['request']['sha256'],platform_binding=collected['platform_observations'])
    report=save(evidence/'q16c-analysis-1/calibration-validation.json',composed)
    require(time.monotonic_ns()<deadline,'original3600s suffix publication ceiling')
    return save(evidence/'q16c-analysis-1/finalized.json',dict(status='ALL_180_VALID_DESCRIPTIVE_COMPLETE',
        composition=report,completion=completed,reused_prefix_reports=86,new_reports=94,all_workers_reaped=True,
        execution_authority=False,phase18_authority=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=('construct','sign-collect','suffix'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--deadline-ns',type=int,required=True);p.add_argument('--witness-fd',type=int)
    args=p.parse_args()
    require(os.getresuid()==(1000,)*3 and time.monotonic_ns()<args.deadline_ns,'actual owner and original phase deadline')
    c=document(dict(path=str(args.configuration),size_bytes=args.configuration.stat().st_size,sha256=args.configuration_sha256))
    require(c['execution_authority'] is False and c['phase18_authority'] is False,'configuration grants no authority')
    for b in c['operator_sources'].values():read(b)
    require(c['operator_sources']['stage17_q16c_continuation_operator_v1.py']==binding(Path(__file__).resolve()),'actual operator source')
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    if args.mode=='construct':result=construct(c,args.deadline_ns)
    elif args.mode=='sign-collect':result=sign_collect(c,args.deadline_ns,args.witness_fd)
    else:result=suffix(c,args.deadline_ns)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
