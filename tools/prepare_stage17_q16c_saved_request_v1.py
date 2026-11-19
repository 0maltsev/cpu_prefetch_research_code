"""Prepare approved D301 metadata even when its native time gate has expired.

Only the owner acceptance is signed. No operational authorization is created.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import stage17_q16c_saved_request_v1 as saved


def binding(path):
    path=Path(path)
    saved.require(path.is_absolute() and all(not p.is_symlink() for p in (path,*path.parents)),'canonical metadata path')
    raw=path.read_bytes()
    return dict(path=str(path),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def document(path):return json.loads(Path(path).read_bytes())


def publish(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return binding(path)


def main():
    saved.require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(),'actual evidence owner')
    ops=Path(__file__).resolve().parent;E=saved.E
    saved.require(ops.parent==E and ops.name.startswith('d301-continuation-'),'exclusive D301 metadata namespace')
    prior=E/'d298-continuation-4/launch-configuration.json'
    saved.require(binding(prior)['sha256']=='afef345d8a0183d51a469266ad159dc337d969d76ebb3770341ce44b66543c63','exact stopped D298 configuration')
    c=document(prior);manifest=document(ops/'administrative-packet.json');revision=manifest['administrative_source_revision']
    saved.require(re.fullmatch('[0-9a-f]{40}',revision) and revision!=saved.NATIVE_SOURCE,'actual separate administrative identity')
    for row in manifest['files']:
        actual=binding(ops/row['path'])
        saved.require((actual['size_bytes'],actual['sha256'])==(row['size_bytes'],row['sha256']),'actual packet bytes')
    sources=dict(c['operator_sources'])
    for path in sorted(ops.glob('*.py')):sources[path.name]=binding(path)
    iso=document(c['qualification_isolation_configuration']['path'])
    iso['evidence_root']=str(E/'isolation-preparation-v32-d301-1')
    isob=publish(ops/'isolation-configuration.json',iso)
    authority=ops/'authority';acceptance=authority/'owner-acceptance.json'
    saved.validate_acceptance(document(acceptance))
    saved.require(binding(authority/'proposal.md')['sha256']==saved.PROPOSAL_SHA,'exact approved D301 text')
    sign=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n',
                         'stage17-owner-acceptance',str(acceptance)],capture_output=True,text=True,timeout=30)
    publish(ops/'acceptance-signing-result.json',dict(exit_code=sign.returncode,stdout=sign.stdout,stderr=sign.stderr))
    saved.require(sign.returncode==0,'owner acceptance signing failed')
    inventory=publish(ops/'operator-sources.json',dict(schema_version='cpu-prefetch-d301-administrative-operators/1',
        administrative_source_revision=revision,qualified_native_source_revision=saved.NATIVE_SOURCE,
        sources=sources,execution_authority=False,phase18_authority=False))
    candidate=Path(c['candidate_inventory']['path']).parent
    c.update(schema_version='cpu-prefetch-d301-saved-request-inputs/1',continuation_decision='D301',
        administrative_source_revision=revision,operator_sources=sources,operator_inventory=inventory,
        supervisor_unit='cpu-prefetch-d301-v32-1.service',clock_adapter=binding(ops/'d301_rearm_isolation.py'),
        qualification_isolation_configuration=isob,
        continuation_authority=dict(proposal=binding(authority/'proposal.md'),acceptance=binding(acceptance),
                                    signature=binding(Path(str(acceptance)+'.sig'))),
        saved_request=binding(Path(c['repository_root'])/'evidence/formal-q16c-d295-1/request.json'),
        authorization_template=binding(E/'d300-authorization-software-check-1/authorization-draft.json'),
        authorization_schema=binding(candidate/'config/schemas/stage17-phase-action-authorization-v6.schema.json'),
        family_registration=binding(Path(c['output_root'])/'registration.json'),
        latest_result=binding(E/'d298-study-1/result.json'),latest_recovery=binding(E/'d298-independent-recovery-1.json'),
        administrative_packet=binding(ops/'administrative-packet.json'))
    result=publish(ops/'launch-configuration.json',c)
    print(json.dumps(dict(status='D301_METADATA_PUBLISHED_TIME_GATE_CLOSED',configuration=result,
        administrative_source_revision=revision,qualified_native_source_revision=saved.NATIVE_SOURCE,
        launch_permitted=False,controls_rearmed=False,operational_authority_signed=False,execution_authority=False)),flush=True)


if __name__=='__main__':main()
