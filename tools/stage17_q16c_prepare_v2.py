"""D275 authenticated Q16c metadata preparation; never executes a measurement.

Construction requires the actual new six-resolution qualification. Signing is
separate and retains the ordinary request, owner trust, one-use and UTC checks.
"""
import argparse
import copy
import dataclasses
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import types

SOURCE='919c48637cbdba9e466a3104f5cbb39f7184e39b'
WORKER='1baa213a137679460348ff6b861839044022957a4de0e5fc79929f7b49bed883'
NS=10**9


def require(ok,message):
    if not ok:raise ValueError('Q16c preparation: '+message)


def binding(path):
    path=Path(path)
    require(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'canonical nonsymlink metadata')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());require(0<before.st_size<=32*1024**2,'finite metadata size')
        raw=stream.read(before.st_size+1);after=os.fstat(stream.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(stamp(before)==stamp(after)==stamp(path.stat()) and len(raw)==before.st_size,'metadata changed')
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def read(bound):
    require(binding(bound['path'])==bound,'bound metadata changed')
    raw=Path(bound['path']).read_bytes()
    require(len(raw)==bound['size_bytes'] and hashlib.sha256(raw).hexdigest()==bound['sha256'],'metadata changed after binding')
    return raw


def document(bound):return json.loads(read(bound))


def save(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(Path(path).parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return binding(path)


def loader_for(c):
    bound=c['files']['loader'];name='stage17_q16c_packet_v2'
    require(name not in sys.modules,'unexpected loader cache')
    module=types.ModuleType(name);module.__file__=bound['path'];sys.modules[name]=module
    exec(compile(read(bound),module.__file__,'exec'),module.__dict__)
    return module


def remaining(record,qualification=False,now=None):
    now=time.monotonic_ns() if now is None else now
    reserve=(47820+5400+2400+(7200 if qualification else 0))*NS
    require(type(now) is int and now+reserve<record['global_deadline_ns'],'complete remaining separately approved execution envelope')
    return record['global_deadline_ns']-now


def comparison(old,current,admission,handoff):
    roots={side:Path(context['archive_bundle_root']) for side,context in [('original',old),('current',current)]}
    indexes={side:admission._inventory(document(binding(root/'BUNDLE_INVENTORY.json'))) for side,root in roots.items()}
    names=admission._source_names(indexes['original'])
    require(names==admission._source_names(indexes['current']),'complete source name coverage')
    def side(which,context):
        root=roots[which]
        return dict(source_revision=context['source_revision'],bundle_root=str(root),
            worker=binding(root/'release/bin/cpu_prefetch_runner'),bundle_inventory=binding(root/'BUNDLE_INVENTORY.json'),
            formal_codegen=binding(root/'build-provenance/formal_codegen_report.json'))
    def row(name):return dict(relative_path=name,**{side:binding(root/name) for side,root in roots.items()})
    return dict(original=side('original',old),current=side('current',current),
        source_comparisons=[row(name) for name in sorted(names)],
        queue_libraries={side:binding(root/handoff.QUEUE) for side,root in roots.items()},
        project_headers=[row(name) for name in handoff.HEADERS])


def construct(c):
    loader=loader_for(c);packet=Path(c['packet_root']);root=Path(c['repository_root']);evidence=Path(c['evidence_root'])
    require(root==loader.EVIDENCE/'admission-root' and evidence==loader.EVIDENCE
        and packet==evidence/'q16c-configuration-2','fixed incident roots')
    _,members=loader.verify_packet(packet,c['files']['manifest']['sha256'])
    loader.verify_archive(c['files']['archive'])
    policy=document(c['files']['policy'])
    require(c['files']['policy']==dict(path=str(root/'config/stage17/stage17-operational-evidence-admission-policy-v61.json'),
        size_bytes=loader.POLICY_SIZE,sha256=loader.POLICY_SHA256),'actual qualified policy61')
    for group in ('bindings','runtime_closure'):
        for b in policy[group].values():loader.read(dict(b,path=str(root/b['path'])))
    sys.path.insert(0,str(root/'tools'));sys.path.insert(1,str(packet))
    loader.load_modules(packet,members,c['files']['renewal_incident'])
    qualification=sys.modules['stage17_q16c_descriptive_administration_v2'].make_cli()
    qualification.activate();validation=qualification._validation(root,evidence,
        pilot_archive=Path(c['files']['archive']['path']),pilot_sidecar=Path(c['files']['sidecar']['path']))
    require(set(validation.resolutions)=={f'S17-EXT-{i:03d}' for i in range(1,7)}
        and validation.current_state=='READY_FOR_STAGE17_PHASE_AUTHORIZATION','actual complete fresh qualification')
    current=validation.resolutions['S17-EXT-006'].semantic_context
    require(current['source_revision']==SOURCE and current['release_artifact_sha256']==WORKER,'actual frozen native qualification')
    record=document(c['files']['source_manifest']);remaining(document(c['files']['execution_window']))
    require(record['boot_id']==c['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'same actual boot')
    archive=document(c['files']['archive_preparation']);history=document(c['files']['history_export'])
    out=Path(c['output_root']);require(not out.exists(),'exclusive metadata construction');out.mkdir(mode=0o700)
    plan=document(c['files']['plan_preview']);plan['storage']['implementation_profile_sha256']=archive['overlay_profile']['sha256']
    # The 47220s collection envelope remains intact after signing and the final
    # owner admission. This extra600s is declared prospectively, inside the same
    # original absolute window; no per-capture or scientific input changes.
    plan['budget']['watchdog_ns']=47820*NS
    cli=qualification
    cli.controller.contract.validate_plan('Q16c',plan);pb=c['files']['frozen_plan']
    require(document(pb)==plan and pb['path']==str(packet/'plan.json'),'exact prospectively frozen full180 plan')
    # Same completed originals and both old contexts; no raw decoding or repeats.
    h={phase:document(history[phase+'_context']) for phase in ('q16a','q16b')}
    for phase in h:save(packet/(phase+'-context.json'),h[phase])
    geometry=document(c['files']['geometry_provenance']);native=binding(packet/'native-geometry.json')
    require(geometry['source_revision']==SOURCE and geometry['output']['sha256']==native['sha256']
        and geometry['worker']['sha256']==WORKER,'actual current geometry query provenance')
    for b in geometry['libraries']:
        actual=binding(Path(current['archive_bundle_root'])/'release/lib'/Path(b['path']).name)
        require((actual['size_bytes'],actual['sha256'])==(b['size_bytes'],b['sha256']),'qualified geometry library')
    for b in geometry['verified_headers']:
        actual=binding(Path(current['archive_bundle_root'])/b['relative_path'])
        require((actual['size_bytes'],actual['sha256'])==(b['size_bytes'],b['sha256']),'qualified geometry header')
    handoffs=sys.modules['stage17_q16c_admission_limits_v1'].make_handoffs()
    rows={}
    for phase,handoff in zip(('q16a','q16b'),handoffs,strict=True):
        old=h[phase]['resolutions']['S17-EXT-006']['semantic_context']
        proof=comparison(old,current,handoff.admission,handoffs[0])
        proof.update(schema_version=handoff.SCHEMA,scope=dict(decision='D270',purpose=handoff.PURPOSE,
            stand_id=plan['stand_id'],boot_id=c['boot_id']),plan=pb,handoff=history['q16a_handoff'] if phase=='q16a'
            else c['files']['q16b_handoff'],native_geometry=native,
            platform_manifests=dict(original=binding(Path(old['archive_bundle_root']).parents[1]/'ext004-authoring-records-1/platform-manifest.json'),
                current=binding(evidence/'ext004-authoring-records-1/platform-manifest.json')),
            execution_authority=False,phase18_authority=False)
        if phase=='q16a':proof['original_plan']=history['q16a_plan']
        else:proof['parent_plan']=c['files']['parent_plan']
        rows[phase]=dict(historical_context=binding(packet/(phase+'-context.json')),
            compatibility=save(packet/(phase+'-compatibility.json'),proof))
        if phase=='q16a':rows[phase]['original_plan']=history['q16a_plan']
    history_config=dict(schema_version='cpu-prefetch-stage17-q16c-descriptive-historical-inputs/1',**rows,
        boot_id=c['boot_id'],execution_authority=False,phase18_authority=False)
    hb=save(packet/'historical-inputs.json',history_config)
    descriptor=dict(schema_version='cpu-prefetch-stage17-cold-archive-q16c-descriptive-overlay/1',
        source_revision=c['administrative_source_revision'],qualified_source_revision=SOURCE,qualified_worker_sha256=WORKER,
        baseline_bundle_root=current['archive_bundle_root'],runtime_root=current['archive_runtime_root'],
        overlay_bundle_root=str(Path(archive['overlay_profile']['path']).parents[2]),
        **{k:archive[k] for k in ('baseline_profile','overlay_profile','native_image','inventory_native_image','sources')},
        execution_authority=False,measurement_changes=False)
    ob=save(packet/'archive-overlay.json',descriptor)
    proof=dict(manifest=c['files']['execution_window'],signature=c['files']['execution_window_signature'])
    cli.controller.configure_execution_window(proof)
    cli.controller.configure_verified_descriptor(read(ob),packet);cli.controller.configure_historical_inputs(history_config,packet);cli.activate()
    cfg=dict(schema_version='cpu-prefetch-stage17-q16c-cli-configuration/2',repository_root=str(root),packet_root=str(packet),
        policy=c['files']['policy'],manifest=c['files']['manifest'],overlay=ob,historical_inputs=hb,
        archive=c['files']['archive'],sidecar=c['files']['sidecar'],window=c['files']['source_manifest'],
        boot_id=c['boot_id'],execution_window_proof=proof,renewal_incident=c['files']['renewal_incident'],execution_authority=False)
    cb=save(packet/'cli-configuration.json',cfg)
    original_request=document(c['files']['old_request']);prerequisites=copy.deepcopy(original_request['action_inputs']['prerequisite_bindings'])
    sources=[];registrations=[];completion=document(c['files']['source_completion']);setup=document(record['source_setup'])
    completion={key:completion[key] for key in ('manifest','signature')}
    for original,result in zip(setup['sources'],record['sources'],strict=True):
        sources.append(dict(artifact_id=original['artifact_id'],binding=result['binary'],envelope_binding=result['envelope'],
            derivation_binding=result['derivation'],parent_namespace_id=original['parent_namespace_id'],source_preparation=completion))
        registrations.append({key:original[key] for key in ('schedule_id','namespace_id','seed_id','phase','parent_namespace_id')})
    nb=save(packet/'namespace-registry.json',dict(schema_version='cpu-prefetch-stage17-formal-namespace-registration/1',
        plan_sha256=pb['sha256'],stand_id=plan['stand_id'],phase_identities=[i['capture'][p] for i in plan['captures'] for p in ('warmup','measurement')],
        schedule_namespaces=registrations,execution_authority=False))
    prerequisites.update(q16a_validation=history['q16a_handoff'],q16b_validation=c['files']['q16b_handoff'],
        namespace_registry=nb,schedule_sources=sources)
    q4=validation.resolutions['S17-EXT-004'].semantic_context;q5=validation.resolutions['S17-EXT-005'].semantic_context['q15_w']
    inputs=dict(plan=plan,hardware_control=dict(mapping_id=q4['hardware_mapping']['mapping_id'],
        q15_w_result_sha256=q5['result_sha256'],prestate=q5['request']['action_inputs']['prestate']),prerequisite_bindings=prerequisites)
    cli.controller._validate_inputs(dict(action_id='Q16c',action_inputs=inputs),validation)
    ab=save(packet/'action-inputs.json',inputs);loader.check_loaded()
    return save(out/'constructed.json',dict(schema_version='cpu-prefetch-stage17-q16c-constructed/1',plan=pb,
        action_inputs=ab,cli_configuration=cb,qualified_worker=dict(path=current['release_artifact_path'],
            size_bytes=current['release_artifact_size_bytes'],sha256=current['release_artifact_sha256']),
        status='ALL_SOURCE_HISTORY_COMPATIBILITY_GATES_PASS',execution_authority=False,phase18_authority=False))


def sign(c):
    loader=loader_for(c);packet=Path(c['packet_root']);evidence=Path(c['evidence_root']);root=Path(c['repository_root'])
    built=document(binding(Path(c['output_root'])/'constructed.json'));cfgb=built['cli_configuration']
    cli,cfg=loader.activate(Path(cfgb['path']),cfgb['sha256']);plan=document(built['plan']);remaining(document(c['files']['execution_window']))
    require(built['status']=='ALL_SOURCE_HISTORY_COMPATIBILITY_GATES_PASS','actual independent preparation')
    # The already recorded prospective audits precede generation and registration.
    for key in ('local_audit','stand_audit'):
        audit=document(c['files'][key]);require(audit['status']=='PASS_SCOPED_HISTORY_AUDIT'
            and not audit['matches'] and not audit['errors']
            and audit['source_setup_sha256']==document(c['files']['source_manifest'])['source_setup']['sha256'],
            'actual prospective full792-seed namespace audit')
    executor=cli.controller.make_executor();program=Path(c['program_root']);planid=built['plan']['sha256']
    limits=executor.custody_limits(plan['storage'],time.monotonic_ns()+120*NS)
    with executor.custody.ProgramStore(program,scope_sha256=plan['storage']['program_scope_sha256'],family_id=planid,limits=limits) as store:
        require(not store._capture_pending and all(s['kind']=='RELEASED' for s in store._states.values()),'quiescent retained program')
        before=copy.deepcopy(store._families);tip=dataclasses.asdict(store.ledger_binding());require(planid not in before,'family already registered')
        store.prepare_family(planid);require(set(store._families)==set(before)|{planid}
            and all(store._families[k]==v for k,v in before.items()),'old family changed')
        after=dataclasses.asdict(store.ledger_binding())
    save(Path(c['output_root'])/'registration.json',dict(before=tip,after=after,new_family_id=planid,old_family_count=len(before),execution_authority=False))
    authroot=root/'evidence/formal-q16c-d270-1';authroot.mkdir(mode=0o700)
    common=dict(repository_root=root,evidence_root=evidence,pilot_archive=Path(cfg['archive']['path']),pilot_sidecar=Path(cfg['sidecar']['path']))
    req=cli.author_formal_request(**common,action_id='Q16c',action_inputs_path=Path(built['action_inputs']['path']),
        request_id='CPU-PREFETCH-V5-V28-Q16C-REQUEST-1',authorization_id='CPU-PREFETCH-V5-V28-Q16C-AUTH-1',
        attempt_id='CPU-PREFETCH-V5-V28-Q16C-ATTEMPT-1',session_id='CPU-PREFETCH-V5-V28-Q16C-SESSION-1',
        output_root=program/'working'/planid,destination=authroot/'request.json')
    now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    issued=now.isoformat().replace('+00:00','Z');expires=(now+datetime.timedelta(seconds=47820)).isoformat().replace('+00:00','Z')
    auth=cli.author_formal_authorization(**common,request_path=req,actor='maltsev.oiu@phystech.edu',reviewer='OWNER',
        issued_at_utc=issued,expires_at_utc=expires,destination=authroot/'authorization.json')
    result=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(auth)],
        stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
    save(Path(c['output_root'])/'signing-result.json',dict(exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
    require(result.returncode==0,'actual signing failed');sig=Path(str(auth)+'.sig')
    cli.verify_formal_signature(repository_root=root,journal=cli.base.latest_journal(evidence),journal_directory=evidence/'journal',
        operational_evidence_root=evidence,authorization_path=auth,signature_path=sig,
        pilot_archive=common['pilot_archive'],pilot_sidecar=common['pilot_sidecar'])
    return save(Path(c['output_root'])/'prepared.json',dict(schema_version='cpu-prefetch-stage17-q16c-prepared/1',
        plan=built['plan'],request=binding(req),authorization=binding(auth),signature=binding(sig),cli_configuration=cfgb,
        worker=built['qualified_worker'],execution_authority=False,phase18_authority=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('construct','sign'))
    parser.add_argument('--configuration',type=Path,required=True);parser.add_argument('--configuration-sha256',required=True);args=parser.parse_args()
    require(os.getuid()==os.geteuid()==1000,'actual evidence owner')
    c=document(dict(path=str(args.configuration),size_bytes=args.configuration.stat().st_size,sha256=args.configuration_sha256))
    require(c['execution_authority'] is False and c['phase18_authority'] is False,'preparation grants no authority')
    for key,b in c['files'].items():
        if key!='archive':read(b)
    print(json.dumps((construct if args.mode=='construct' else sign)(c)),flush=True)


if __name__=='__main__':main()
