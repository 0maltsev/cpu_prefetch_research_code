"""Publish the approved D298 administrative packet; no experiment or window."""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import stage17_q16c_qualified_continuation_v1 as resume

E=resume.E
OPS=E/'d298-continuation-1'


def binding(path):
    p=Path(path);raw=p.read_bytes()
    resume.require(p.is_absolute() and all(not q.is_symlink() for q in (p,*p.parents)), 'canonical packet metadata')
    return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def document(path):return json.loads(Path(path).read_bytes())


def save(path,value):
    raw=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return binding(path)


def main():
    resume.require(os.getresuid()==(1000,)*3 and os.getresgid()==(1000,)*3 and not os.getgroups(), 'actual evidence owner')
    resume.check_time(__import__('time').monotonic_ns())
    frozen=E/'q16c-continuation-final-1/launch-configuration.json'
    rehearsal=E/'d297-software-preparation-2/configuration.json'
    resume.require(binding(frozen)['sha256']=='3359f96629594f46b7bd4b362a7ae5485c1480c7fb159cf40a5040ef633458d2', 'exact stopped configuration')
    resume.require(binding(rehearsal)['sha256']=='08332ed19c0ee66894e9fce4524c2108e8e420e212385896be6cea18d7ed2bbd', 'exact passed rehearsal')
    c=document(rehearsal)
    manifest=document(OPS/'administrative-packet.json')
    revision=manifest['administrative_source_revision']
    resume.require(re.fullmatch('[0-9a-f]{40}',revision) and revision!=resume.NATIVE_SOURCE, 'actual distinct administrative revision')
    for row in manifest['files']:
        actual=binding(OPS/row['path']);resume.require(actual['size_bytes']==row['size_bytes'] and actual['sha256']==row['sha256'], 'exact administrative packet bytes')
    sources=dict(c['operator_sources'])
    for p in sorted(OPS.glob('*.py')):sources[p.name]=binding(p)
    iso=document(c['qualification_isolation_configuration'])
    iso['evidence_root']=str(E/'isolation-preparation-v32-d298-1')
    isolation=save(OPS/'isolation-configuration.json',iso)
    acceptance=OPS/'authority/owner-acceptance.json';proposal=OPS/'authority/proposal.md'
    resume.validate_acceptance(document(acceptance))
    resume.require(binding(proposal)['sha256']==resume.PROPOSAL_SHA,'actual approved proposal')
    signed=subprocess.run(['ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519',
        '-n','stage17-owner-acceptance',str(acceptance)],capture_output=True,text=True,timeout=30)
    save(OPS/'acceptance-signing-result.json',dict(exit_code=signed.returncode,stdout=signed.stdout,stderr=signed.stderr))
    resume.require(signed.returncode==0,'owner signature failed')
    inventory=save(OPS/'operator-sources.json',dict(schema_version='cpu-prefetch-d298-administrative-operators/1',
        administrative_source_revision=revision,qualified_native_source_revision=resume.NATIVE_SOURCE,
        sources=sources,execution_authority=False,phase18_authority=False))
    receipts=sorted(E.glob('v32-*.result.json'));resume.require(len(receipts)==7,'actual complete qualification receipts')
    c.update(continuation_decision='D298',administrative_source_revision=revision,operator_sources=sources,
        operator_inventory=inventory,supervisor_unit='cpu-prefetch-d298-v32-1.service',
        original_total_deadline_ns=resume.DEADLINE,qualified_clock_adapter=c['clock_adapter'],
        clock_adapter=binding(OPS/'d298_rearm_isolation.py'),qualification_isolation_configuration=isolation,
        continuation_authority=dict(proposal=binding(proposal),acceptance=binding(acceptance),signature=binding(Path(str(acceptance)+'.sig'))),
        preconstruction=binding(Path(c['output_root'])/'constructed.json'),
        prior_result=binding(E/'d295-study-1/result.json'),prior_recovery=binding(E/'d295-independent-recovery-1.json'),
        prior_qualification=binding(E/'qualification-family-complete-1.json'),qualification_receipts=[binding(p) for p in receipts],
        frozen_configuration=binding(frozen),rehearsal_configuration=binding(rehearsal),
        window_proof=document(E/'execution-window-proof.json'),administrative_packet=binding(OPS/'administrative-packet.json'))
    output=save(OPS/'launch-configuration.json',c)
    print(json.dumps(dict(status='D298_BOUND_ADMINISTRATIVE_CONFIGURATION',configuration=output,
        administrative_source_revision=revision,qualified_native_source_revision=resume.NATIVE_SOURCE,
        experiments_started=0,new_execution_window=False,execution_authority=False)),flush=True)


if __name__=='__main__':main()
