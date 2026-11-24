"""One-shot read-only D269 Q16b handoff publication; no hardware or raw decode.

Run from an authenticated flat administrative packet outside the qualified root.
The completed source-bound original CLI verifies signed lifecycle and custody;
only original report bytes are read for exact descriptive recomposition.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sys
import types

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-27')
P=E/'d260-configuration-3'
A=E/'d260-analysis-1'
S=E/'d260-study-1'
O=E/'q16b-handoff-preparation-1'
CFG_SHA='ce3f5177b83d63df82b512fad865510bce9064b7091996cef8de7bc7bb806ec0'
LOADER_SHA='b8c54a71ea73b8e4381cb85bd2d7352c5a5524085d05babe9d6673a3fedc0058'
BOOT='4c08cd05-b362-49dd-b37f-629e9c7ad79a'
MEMBERS={'prepare_stage17_q16b_handoff_v1.py','stage17_q16b_handoff_v1.py',
         'stage17_service_continuation_calibration_v1.py'}


def require(ok,message):
    if not ok:raise ValueError(message)


def read(binding,maximum=32*1024**2):
    require(type(binding) is dict and set(binding)=={'path','size_bytes','sha256'},'exact source binding')
    p=Path(binding['path']);size=binding['size_bytes']
    require(p.is_absolute() and all(not x.is_symlink() for x in (p,*p.parents)), 'canonical nonsymlink source')
    require(type(size) is int and 0<=size<=maximum,'finite source size')
    with p.open('rb') as f:
        before=os.fstat(f.fileno());require(before.st_size==size,'original source size');raw=f.read(size+1)
        after=os.fstat(f.fileno())
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(len(raw)==size and stamp(before)==stamp(after)==stamp(p.stat()) and hashlib.sha256(raw).hexdigest()==binding['sha256'],'changed source')
    return raw


def binding(path):
    p=Path(path);require(not p.is_symlink() and p.stat().st_size<=32*1024**2,'bounded public metadata')
    raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def save(path,value):
    raw=(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return binding(path)


def module(name,path,raw):
    require(name not in sys.modules,'unexpected module cache')
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
    exec(compile(raw,str(path),'exec'),m.__dict__);return m


def main(expected_manifest):
    require(os.getuid()==os.geteuid()==1000,'evidence owner required')
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'same completed physical boot')
    resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,)*2)
    packet=Path(__file__).resolve().parent;mb=binding(packet/'manifest.json')
    require(mb['sha256']==expected_manifest,'explicit handoff packet hash')
    manifest=json.loads(read(mb));require(set(manifest)=={'schema_version','files','execution_authority'},'packet fields')
    require(manifest['schema_version']=='software-d269-q16b-handoff-packet/1' and manifest['execution_authority'] is False,'packet has no execution authority')
    rows=manifest['files'];require(type(rows) is list and len(rows)==3 and {r['name'] for r in rows}==MEMBERS,'exact handoff source closure')
    require({p.name for p in packet.iterdir()}==MEMBERS|{'manifest.json'},'closed handoff directory; no caches')
    sources={}
    for row in rows:
        require(set(row)=={'name','size_bytes','sha256'} and row['name'] in MEMBERS,'flat listed source')
        sources[row['name']]=read(dict(path=str(packet/row['name']),size_bytes=row['size_bytes'],sha256=row['sha256']),2*1024**2)
    require(sources[Path(__file__).name]==Path(__file__).read_bytes(),'operator source changed')
    loader_path=P/'stage17_service_continuation_packet_v3.py';lb=binding(loader_path)
    require(lb['sha256']==LOADER_SHA,'original admitted cold loader')
    loader=module('stage17_service_continuation_packet_v3',loader_path,read(lb))
    cli,cfg=loader.activate(P/'cli-configuration.json',CFG_SHA)
    prepared_phase=json.loads(read(binding(E/'d267-admission-preparation-3/prepared-phase.json')))
    common=dict(repository_root=E/'admission-root',operational_evidence_root=E,
        journal=cli.base.latest_journal(E),journal_directory=E/'journal',
        authorization_path=Path(prepared_phase['files']['authorization']['path']),
        signature_path=Path(prepared_phase['files']['signature']['path']),
        pilot_archive=Path(cfg['archive']['path']),pilot_sidecar=Path(cfg['sidecar']['path']))
    require(not O.exists(),'exclusive handoff publication; no hidden retry');O.mkdir(mode=0o700)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        prepared=cli.prepare_formal_retention(**common)
        require(prepared.request_bytes==read(prepared_phase['files']['request']),'original signed request')
        phase=Path(prepared.request['evidence_root_binding']['absolute_path'])
        verified=cli.admit_formal_retention(prepared,phase)
        require(len(verified['captures'])==103 and verified['inverse_readback_performed'] is False,'all103 custody metadata; no raw inverse')
        metadata=save(O/'signed-family-metadata.json',verified)
        print('SIGNED_LIFECYCLE_AND_103_CUSTODY_METADATA_VERIFIED',flush=True)
        plan=prepared.request['action_inputs']['plan'];parent_raw=read(plan['continuation']['parent_plan']);parent=json.loads(parent_raw)
        prefix=json.loads(read(plan['continuation']['accepted_prefix_manifest']));old=[];new=[]
        for row in prefix['captures']:
            i=row['original_ordinal'];raw=read(row['scientific_report'])
            old.append(dict(capture_ordinal=i,measurement_run_id=parent['captures'][i]['capture']['measurement']['run_id'],validity='VALID',report_binding=dict(artifact_id=f'Q16B-ORIGINAL-AA-{i}',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),report_utf8_bytes=raw.decode()))
        for i in range(103):
            process=json.loads(read(binding(A/f'capture-{i}-process.json')))
            require(process['status']=='VALID' and process['ordinal']==i,'every completed analysis process valid')
            raw=read(process['report'])
            new.append(dict(capture_ordinal=i,measurement_run_id=plan['captures'][i]['capture']['measurement']['run_id'],validity='VALID',report_binding=dict(artifact_id=f'Q16B-CAPTURE-{i}',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()),report_utf8_bytes=raw.decode()))
        compose=module('d269_completed_service_math',packet/'stage17_service_continuation_calibration_v1.py',sources['stage17_service_continuation_calibration_v1.py'])
        result=compose.evaluate(parent,plan,old,new)
        composition_binding=binding(A/'calibration-validation.json');original=read(composition_binding)
        canonical=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        require(canonical==original,'exact original descriptive composition recomputed from all120 original reports')
        handoff=module('d269_q16b_handoff',packet/'stage17_q16b_handoff_v1.py',sources['stage17_q16b_handoff_v1.py'])
        document=dict(schema_version=handoff.SCHEMA,completion=binding(S/'study-result.json'),analysis=binding(A/'analysis-complete.json'),composition=composition_binding,plan=prepared_phase['files']['plan'],parent_plan=plan['continuation']['parent_plan'],geometry=binding(P/'native-geometry.json'),execution_authority=False,phase18_authority=False)
        retained=handoff.consume(document,validation=prepared.validation,selected_duration_ns=plan['measurement_ns'])
        require(retained==result,'unchanged completed120-report result')
        basis=handoff.load_basis(retained);basis_binding=save(O/'descriptive-load-basis.json',basis);hb=save(O/'q16b-handoff.json',document)
        loader.check_loaded()
        verification=dict(schema_version='software-d269-q16b-handoff-verification/1',status='VERIFIED_Q16B_DESCRIPTIVE_HANDOFF',started_at_utc=started,completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),handoff=hb,descriptive_load_basis=basis_binding,packet_manifest=mb,signed_family_metadata=metadata,valid_reports=120,source_populations=retained['source_populations'],measurement_zero_loss_gate=retained['derived_result']['measurement_zero_loss_gate'],warmup_zero_loss_gate=retained['derived_result']['warmup_zero_loss_gate'],statistical_evidence_strength='DESCRIPTIVE_OBSERVED_MINIMUM',tolerance_guarantee=False,new_measurements=0,raw_redecode_performed=False,raw_mutation=False,ext007_admitted=False,execution_authority=False,phase18_authority=False)
        save(O/'verification.json',verification);print(json.dumps(dict(status=verification['status'],handoff=hb,descriptive_load_basis=basis_binding)),flush=True)
    except BaseException as error:
        save(O/'failure.json',dict(type=type(error).__name__,message=str(error),new_measurements=0,raw_redecode_performed=False,execution_authority=False));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest-sha256',required=True);args=parser.parse_args();main(args.manifest_sha256)
