"""Bounded offline validation of the collected D240 suffix; no experiments."""
from __future__ import annotations
import ast
import dataclasses
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import time
import types

HERE=Path(__file__).resolve().parent
PREFIX_SHA='b62ad1ee2d9f43e3b895f8aad6709e80762eca76a2d883b37dbdee80a232f218'
if hashlib.sha256((HERE/'validate_prefix.py').read_bytes()).hexdigest()!=PREFIX_SHA:
    raise ValueError('reviewed formal reader operator differs')
import validate_prefix as support
base=support.base
require,read,parse,save,sha=base.require,base.read,base.parse,base.save,base.sha
PLAN_SHA='91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
REQUEST_SHA='aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a'
COMPLETION_SHA='ef0fb5775e70e8512add2231925506b7f73fa28c676775fe5aac43f90c7a07ed'
ADMIN_SHA='ffa0c16115440880ecbd2a46d08bf3364712caa2f23ead0b7106bb5b5c478e26'
ROLES=base.ROLES


def config(path,digest):
    path=base.safe(path)
    c=parse(read(dict(path=str(path),size_bytes=path.stat().st_size,sha256=digest),65536))
    require(c['schema_version']=='software-offline-q16a-suffix-analysis/1','suffix config version')
    require(c['operator_sha256']==sha(Path(__file__).read_bytes()),'operator source differs')
    require(c['supervision_sha256']==base.SUPERVISION_SHA==sha((HERE/'d234_supervision.py').read_bytes()),'supervisor differs')
    require(c['execution_authority'] is False,'offline only')
    require(set(c['files'])==set(ROLES)|{'policy','historical_journal'},'exact signed input set')
    require(c['files']['REQUEST']['sha256']==REQUEST_SHA and c['files']['COMPLETION']['sha256']==COMPLETION_SHA,'incident bindings differ')
    for name in ('repository_root','evidence_root','journal_directory','analysis_root'):base.safe(c[name])
    r=c['resources']
    for key in ('supervisor_as_bytes','coordinator_as_bytes','capture_as_bytes','total_memory_bytes','memory_reserve_bytes','timeout_seconds','metadata_bytes','filesystem_overhead_bytes','canonical_capture_bytes','worker_count'):base.uint(r[key],key)
    require(r['supervisor_as_bytes']==r['coordinator_as_bytes']==2*base.GIB and r['capture_as_bytes']==8*base.GIB,'reviewed process limits')
    require(r['worker_count']==4 and r['total_memory_bytes']==36*base.GIB and r['memory_reserve_bytes']==8*base.GIB,'aggregate memory bounds')
    require(r['timeout_seconds']==259200 and r['metadata_bytes']==2*base.GIB and r['filesystem_overhead_bytes']==256*1024**2,'finite offline limits')
    require(r['runtime']['codec_address_space_bytes']==2*base.GIB,'decoder process bound')
    support.scratch_proof(r)
    return c


def validate_population(plan):
    require(sha(base.canonical(plan))==PLAN_SHA,'exact collected suffix plan')
    rows=plan['captures']
    require(len(rows)==531,'531 suffix captures required')
    for i,item in enumerate(rows):
        cap=item['capture']
        require(cap['ordinal']==i and cap['context_ordinal']==3+i//59,'local/context mapping')
        require(cap['measurement']['run_id']==f'F25M{i+177:08d}','original numeric identity mapping')
    return rows


def modules(c):
    m,pinned=support.modules(c)
    admin=Path(c['evidence_root'])/'d242-admin-1'
    payload=(admin/'manifest.json').read_bytes()
    require(sha(payload)==ADMIN_SHA,'approved D242 adapter manifest')
    for row in parse(payload)['files']:
        require(Path(row['name']).name==row['name'],'flat administrative binding')
        read(dict(path=str(admin/row['name']),size_bytes=row['size_bytes'],sha256=row['sha256']))
    sys.path.insert(0,str(admin))
    recovery=importlib.import_module('stage17_state_journal_v53')
    require(Path(recovery.__file__).resolve()==admin/'stage17_state_journal_v53.py','administrative import path')
    recovery.activate()
    return m,pinned


def prepare(c,m):
    p=m.phase_controller_v26.prepare_retention(repository_root=Path(c['repository_root']),
        operational_evidence_root=Path(c['evidence_root']),journal=Path(c['files']['historical_journal']['path']),
        journal_directory=Path(c['journal_directory']),authorization_path=Path(c['files']['AUTHORIZATION']['path']),
        signature_path=Path(c['files']['SIGNATURE']['path']),synthetic_test_only=False,
        pilot_archive=Path(c['pilot_archive']['path']),pilot_sidecar=Path(c['pilot_sidecar']['path']))
    require(p.request_bytes==read(c['files']['REQUEST']) and p.authorization_bytes==read(c['files']['AUTHORIZATION']),'prepared original signed bytes')
    return p


def lifecycle(c,m,p,pinned):
    s=m.operational_semantics_v17
    artifacts=[]
    for role in ROLES:
        b=c['files'][role];raw=read(b)
        artifacts.append(s.reader.Artifact('Q16A_'+role,Path(b['path']),raw,len(raw),sha(raw),None if role=='SIGNATURE' else parse(raw),dict(artifact_id=role)))
        if role!='SIGNATURE':
            family=dict(AUTHORIZATION='phase-action-authorization',REQUEST='fixed-action-request',ATTEMPT='phase-action-attempt',RESULT='phase-action-result',COMPLETION='phase-action-completion')[role]
            s.reader._validate(Path(c['repository_root']),parse(raw),'config/schemas/stage17-'+family+'-v6.schema.json',role,pinned)
    expected=s._historical(p,p.validation.resolutions,c['files']['historical_journal']['path'])
    return s._receipts(artifacts=artifacts,action_id='Q16a',trust=p.validation.resolutions['S17-EXT-003'].semantic_context['trust'],
        expected_predecessors=expected,extent=m.formal_calibration_v2.plans.validate_plan('Q16a',p.request['action_inputs']['plan']),allow_synthetic=False)


def coordinate(c,deadline):
    root=Path(c['analysis_root']);r=c['resources'];m,pinned=modules(c);p=prepare(c,m)
    plan=p.request['action_inputs']['plan'];items=validate_population(plan)
    family=lifecycle(c,m,p,pinned)
    save(root/'signed-lifecycle-validation.json',dict(status='PASS',completion=c['files']['COMPLETION'],historical_journal=c['files']['historical_journal'],
        original_supervisor_unchanged=True,restoration_verified=True,execution_authority=False),65536)
    phase=Path(p.request['evidence_root_binding']['absolute_path']);registry=m.output_registry_v12
    require(phase.name==PLAN_SHA and phase.parent.name=='working','original signed output path')
    fd,identity=registry.roots._componentwise_output_root(phase,Path(c['repository_root']),p.request['evidence_root_binding'])
    try:
        extent=m.formal_calibration_v2.plans.validate_plan('Q16a',plan)
        require(r['canonical_capture_bytes']==plan['storage']['analysis_capture_workspace_bytes'],'signed capture workspace')
        require(r['total_memory_bytes']<=extent.declared.memory_bytes,'signed family memory ceiling')
        verified=registry.verify_archived_formal_metadata(registry=p.registry,repository_root=Path(c['repository_root']),directory_fd=fd,
            result=family['result'],request=p.request,authorization_sha256=family['authorization_sha256'],synthetic_test_only=False,
            archive_runtime_profile=p.archive_runtime_profile,deadline_ns=deadline)
        m.operational_semantics_v17._archive_scope(verified,p.request,c['repository_root'])
        require(len(verified['captures'])==531,'full suffix metadata coverage')
        save(root/'authenticated-suffix-custody.json',verified,r['metadata_bytes']//4)
        profile=m.formal_archive_runtime_v1._jsonable(dataclasses.asdict(p.archive_runtime_profile.decoder))
        decode=m.formal_archive_v1.DecodeLimits(**r['decoder'],deadline_ns=deadline);decode.validate()
        require(decode.max_canonical_bytes<=r['canonical_capture_bytes'],'decoder capture ceiling')
        (root/'reports').mkdir(mode=0o700)
        jobs=[]
        for i,(item,cap) in enumerate(zip(items,verified['captures'],strict=True)):
            require(cap['capture_ordinal']==i,'metadata ordinal differs')
            require(sum(a['logical']['size_bytes'] for a in cap['artifacts'])<=r['canonical_capture_bytes'],'actual scratch extent')
            jobs.append(dict(item=item,verified=cap,resources=r,decoder_profile=profile,decoder_limits=dataclasses.asdict(decode),
                program_root=str(phase.parent.parent),scratch=str(root/'scratch'),reports=str(root/'reports'),hardware_control=p.request['action_inputs']['hardware_control']))
        outputs=base.ordered_pool(m,jobs,c,deadline)
        require(len(outputs)==531,'all suffix reports required')
        records=[]
        for i,b in enumerate(outputs):
            report=parse(read(b,r['metadata_bytes']//(708*3+16)))
            require(report['capture_ordinal']==i and report['raw_reconciliation_validated'] is True and report['capture_execution_evidence_validated'] is True,'raw report identity/coverage')
            records.append(dict(local_ordinal=i,original_ordinal=i+177,measurement_run_id=items[i]['capture']['measurement']['run_id'],validation_report_binding=b))
        for b in c['files'].values():read(b)
        custody_limits=m.formal_archive_custody_v1.CustodyLimits(**r['custody'],deadline_ns=deadline)
        with m.formal_archive_custody_v1.ProgramStore(phase.parent.parent,scope_sha256=plan['storage']['program_scope_sha256'],family_id=PLAN_SHA,limits=custody_limits) as store:
            require(dataclasses.asdict(store.ledger_binding())==verified['scope_bindings']['ledger_head'],'ledger changed during offline validation')
        registry.roots._verify_root_identity(fd,identity)
        save(root/'validated-suffix-manifest.json',dict(schema_version='software-validated-q16a-suffix/1',status='VALIDATED',
            plan_sha256=PLAN_SHA,request=c['files']['REQUEST'],completion=c['files']['COMPLETION'],records=records,
            method_id=m.q16a_capture_validation_v1.demand.METHOD_ID,analysis_configuration_sha256=c['configuration_sha256'],
            authenticated_custody=base.binding(root/'authenticated-suffix-custody.json'),raw_mutation=False,
            family_validity_established=False,execution_authority=False,phase18_authority=False),r['metadata_bytes']//2)
    finally:os.close(fd)


def main():
    def checked_config(path,digest):
        c=config(path,digest);c['configuration_sha256']=digest;return c
    fn=types.FunctionType(base.main.__code__,{**vars(base),'config':checked_config,'coordinate':coordinate,'__file__':__file__})
    return fn()


if __name__=='__main__':raise SystemExit(main())
