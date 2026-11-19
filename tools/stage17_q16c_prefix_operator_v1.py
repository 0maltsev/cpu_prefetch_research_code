"""D288 original86 read-only validation under the immutable D285 packet.

Software-check loads and verifies code only. Validate requires the already
owner-signed new D288 window and consumes its original prefix start/deadline.
No qualification, native experiment, source generation or retry entry exists.
"""
import argparse
import hashlib
import json
import os
import stat
from pathlib import Path
import sys
import time
import types

OLD_LOADER_SHA='0dbad5df57a213327b3dc22f40a01b3263db4cb242c9b6895c2f2c8becd22e7c'
NEW_MODULES=(
 'stage17_formal_scheduled_continuation_v1','stage17_q16c_execution_window_v3',
 'stage17_q16c_descriptive_calibration_v3','stage17_q16a_q16c_descriptive_handoff_v3',
 'stage17_q16b_q16c_descriptive_handoff_v3','stage17_q16c_admission_limits_v3',
 'stage17_q16c_source_receipts_v2','stage17_q16c_scientific_sources_v1','stage17_q16c_prefix_compatibility_v1',
 'stage17_q16c_prefix_reuse_v1','stage17_q16c_retained_prefix_v1','stage17_q16c_analysis_v2')


def require(ok,message):
    if not ok:raise ValueError('D288 prefix operator: '+message)


def read(binding,maximum=32*1024**2):
    require(type(binding) is dict and set(binding)=={'path','size_bytes','sha256'},'closed binding')
    path=Path(binding['path']);size=binding['size_bytes']
    require(path.is_absolute() and '..' not in path.parts and all(not p.is_symlink() for p in (path,*path.parents)),
            'canonical nonsymlink input')
    require(type(size) is int and 0<size<=maximum,'bounded input')
    fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NONBLOCK|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode) and before.st_size==size,'regular input and actual size')
        raw=stream.read(size+1)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.stat(follow_symlinks=False)),
                'input changed during read')
    require(len(raw)==size and hashlib.sha256(raw).hexdigest()==binding['sha256'],'actual input digest')
    return raw


def binding(path):
    path=Path(path);raw=path.read_bytes()
    result=dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    read(result);return result


def bootstrap(configuration):
    require(os.getresuid()==(1000,)*3,'actual evidence owner')
    require(configuration['schema_version']=='cpu-prefetch-stage17-d288-prefix-packet/1'
        and configuration['execution_authority'] is False and configuration['phase18_authority'] is False,
        'prefix packet is read-only')
    require(configuration['operator_source']==binding(Path(__file__).resolve()),'actual bound prefix operator')
    require(not any(name.startswith('stage17_') for name in sys.modules),'fresh interpreter before original loader')
    b=configuration['original_loader'];require(b['sha256']==OLD_LOADER_SHA,'exact preserved D285 loader')
    loader=types.ModuleType('stage17_q16c_packet_v3');loader.__file__=b['path']
    sys.modules[loader.__name__]=loader
    exec(compile(read(b),b['path'],'exec'),loader.__dict__)
    old=configuration['original_cli_configuration']
    cli,cfg=loader.activate(Path(old['path']),old['sha256'])
    candidate=Path(configuration['candidate_bundle_root'])
    require(candidate.is_absolute() and candidate.resolve(strict=True)==candidate,'canonical actual candidate bundle')
    require(configuration['candidate_inventory']['path']==str(candidate/'BUNDLE_INVENTORY.json'),
            'actual candidate inventory namespace')
    inventory=json.loads(read(configuration['candidate_inventory']))
    require(inventory['source_revision']==configuration['candidate_source_revision'],
            'actual candidate source revision')
    index={row['path']:row for row in inventory['files']}
    require(len(index)==len(inventory['files']),'unique actual candidate members')
    worker='release/bin/cpu_prefetch_runner'
    require(configuration['candidate_worker']==dict(path=str(candidate/worker),
        size_bytes=index[worker]['size_bytes'],sha256=index[worker]['sha256']),'actual candidate worker binding')
    require(set(configuration['new_sources'])==set(NEW_MODULES),'closed prefix helper code set')
    pinned={}
    for name in NEW_MODULES:
        b=configuration['new_sources'][name];member='tools/'+name+'.py'
        require(b==dict(path=str(candidate/member),size_bytes=index[member]['size_bytes'],sha256=index[member]['sha256']),
                'candidate inventory prefix helper '+name)
        pinned[name]=read(b)
    # Original science modules stay loaded from their authenticated old source.
    # Load new cold helpers from verified bytes without changing those globals.
    for name in NEW_MODULES:
        loader.load_source(name,Path(configuration['new_sources'][name]['path']),pinned[name])
    loader.check_loaded()
    require(sys.modules['stage17_formal_plan_v1'].ROOT==Path(cfg['repository_root']),
            'original scientific/schema root must remain original')
    return loader,cli,cfg


def validate(configuration,loader,cli,cfg,deadline_ns):
    window=sys.modules['stage17_q16c_execution_window_v3']
    proof=configuration['execution_window_proof']
    record=window.parse(window.read(proof['manifest']))
    window.validate(record,now=time.monotonic_ns(),phase='prefix_validation',
        expected_source=configuration['candidate_source_revision'],expected_worker=configuration['candidate_worker']['sha256'],
        expected_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    window.verify_bindings(record)
    require(record['bindings']['prefix_validation_packet']==configuration['packet_binding'],
            'actual prospectively frozen prefix packet')
    require(record['bindings']['candidate_inventory']==configuration['candidate_inventory']
        and record['bindings']['candidate_worker']==configuration['candidate_worker'],'actual prepared candidate')
    start=record['started_monotonic_ns']
    require(deadline_ns==start+3600*10**9 and time.monotonic_ns()<deadline_ns,'original prefix deadline; no reset')
    root=Path(cfg['repository_root']);evidence=root.parent
    common=dict(repository_root=root,operational_evidence_root=evidence,journal=cli.base.latest_journal(evidence),
        journal_directory=evidence/'journal',authorization_path=Path(configuration['original_authorization']['path']),
        signature_path=Path(configuration['original_signature']['path']),pilot_archive=Path(cfg['archive']['path']),
        pilot_sidecar=Path(cfg['sidecar']['path']))
    retained=sys.modules['stage17_q16c_retained_prefix_v1']
    preparation=retained.prepare_original(sys.modules['stage17_q16c_descriptive_administration_v3'],**common)
    prepared,facade=preparation.authenticate(historical_inputs=loader.strict_json(loader.read(cfg['historical_inputs'])),
        packet_root=Path(cfg['packet_root']),execution_window=cfg['execution_window_proof'],
        source_reuse=loader.strict_json(loader.read(cfg['source_reuse'])),archive_descriptor=loader.read(cfg['overlay']))
    trust=prepared.validation.resolutions['S17-EXT-003'].semantic_context['trust']
    require(trust['measurements']['reviewer_role']=='OWNER' and record['stand_id']==trust['subject_id'],
            'actual authenticated owner of the retained study')
    window.read(proof['signature'])
    sys.modules['stage17_phase_controller_v2']._verify_signature(window.read(proof['manifest']),Path(proof['signature']['path']),trust)
    verified,decode=retained.collect_metadata(prepared,facade,plan_binding=configuration['original_plan'],
        restoration_binding=configuration['original_restoration'],deadline_ns=deadline_ns)
    analysis=sys.modules['stage17_q16c_analysis_v2'];output=Path(configuration['analysis_root'])
    completed=analysis.analyze_verified(prepared.request['action_inputs']['plan'],verified,prepared.archive_runtime_profile,
        decode,prepared.request['action_inputs']['hardware_control'],output,kind='PREFIX86',
        plan_binding=configuration['original_plan'],global_deadline_ns=record['global_deadline_ns'],
        retained_failed_scratch_bytes=configuration['retained_failed_scratch_bytes'],started_monotonic_ns=start)
    composition=sys.modules['stage17_q16c_descriptive_calibration_v3']
    complete=window.parse(window.read(completed));rows=[]
    for ordinal,b in enumerate(complete['reports']):
        raw=window.read(b)
        rows.append(dict(capture_ordinal=ordinal,validity='VALID',report_utf8_bytes=raw,
            report_binding=dict(artifact_id=f'Q16C-D288-PREFIX-{ordinal:04d}',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())))
    accepted=composition.prefix_manifest(window.read(configuration['original_plan']),rows,
        plan_binding=configuration['original_plan'],analysis_completion=completed)
    manifest=analysis.save(output/'accepted-prefix.json',accepted)
    require(time.monotonic_ns()<deadline_ns,'original prefix publication deadline')
    loader.check_loaded()
    return dict(status='ALL_86_VALID_PREFIX_MANIFEST_PUBLISHED',completion=completed,accepted_prefix=manifest,
        elapsed_ns=time.monotonic_ns()-start,all_workers_reaped=True,execution_authority=False,phase18_authority=False)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('software-check','validate'))
    p.add_argument('--configuration',type=Path,required=True);p.add_argument('--configuration-sha256',required=True)
    p.add_argument('--deadline-ns',type=int);a=p.parse_args()
    packet=dict(path=str(a.configuration),size_bytes=a.configuration.stat().st_size,sha256=a.configuration_sha256)
    document=json.loads(read(packet))
    if a.mode=='software-check':
        c=dict(document,packet_binding=packet)
    else:
        require(type(document) is dict and set(document)=={'schema_version','prefix_packet','execution_window_proof',
            'execution_authority','phase18_authority'} and document['schema_version']=='cpu-prefetch-stage17-d288-prefix-invocation/1'
            and document['execution_authority'] is False and document['phase18_authority'] is False,
            'closed fresh invocation, no self-referential packet hash')
        c=dict(json.loads(read(document['prefix_packet'])),packet_binding=document['prefix_packet'],
            execution_window_proof=document['execution_window_proof'])
    loader,cli,cfg=bootstrap(c)
    if a.mode=='software-check':
        print(json.dumps(dict(status='SOFTWARE_IMPORTS_VERIFIED',capture_validation_started=False,
            original_source_preserved=True,helpers=len(NEW_MODULES),execution_authority=False)),flush=True)
        return
    print(json.dumps(validate(c,loader,cli,cfg,a.deadline_ns)),flush=True)


if __name__=='__main__':main()
