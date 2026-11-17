"""D276 corrected-Q15 once-only handoff from actual successful qualification to supervision."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import types


def finalized(c,qualification):
    if qualification!=dict(success=True,formal_capture_started=False,isolation_retained_for_formal=True):
        raise ValueError('actual successful retained qualification required')
    if 'qualification_complete' in c['files']:raise ValueError('handoff already finalized')
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--configuration',type=Path,required=True)
    p.add_argument('--configuration-sha256',required=True);p.add_argument('--operator-sha256',required=True);a=p.parse_args()
    if os.geteuid()!=0 or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=a.operator_sha256:
        raise ValueError('bound root launcher required')
    raw=a.configuration.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=a.configuration_sha256:raise ValueError('launch inputs changed')
    c=json.loads(raw);b=c['files']['preparation_operator'];source=Path(b['path']).read_bytes()
    if len(source)!=b['size_bytes'] or hashlib.sha256(source).hexdigest()!=b['sha256']:raise ValueError('bootstrap changed')
    helper=types.ModuleType('q16c_bound_bootstrap');helper.__file__=b['path'];exec(compile(source,b['path'],'exec'),helper.__dict__)
    helper.require(c['execution_authority'] is False and c['phase18_authority'] is False,'input authority')
    source_record=helper.document(c['files']['source_manifest']);evidence=Path(c['evidence_root'])
    helper.require(c['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'same actual boot')
    qualification_deadline=helper.document(helper.binding(evidence/'q15-continuation-window-1.json'))['qualification_deadline_monotonic_ns']
    deadline=min(source_record['global_deadline_ns'],qualification_deadline+2400*10**9)
    done=evidence/'qualification-family-complete-2.json';failed=evidence/'qualification-family-failure-2.json'
    while not done.exists():
        helper.require(not failed.exists(),'qualification failed; no next action or retry')
        helper.require(time.monotonic_ns()<deadline,'original qualification recovery deadline expired; no launch')
        time.sleep(2)
    helper.require(not failed.exists(),'conflicting qualification terminal receipts')
    bound=helper.binding(done);finalized(c,helper.document(bound));helper.remaining(source_record)
    c['files']['qualification_complete']=bound
    for key,b in c['files'].items():
        if key!='archive':helper.read(b)
    cfg=helper.save(evidence/'q16c-operational-configuration-2.json',c)
    helper.save(evidence/'q16c-qualification-handoff-2.json',dict(configuration=cfg,qualification=bound,
        source_manifest=c['files']['source_manifest'],original_global_deadline_ns=source_record['global_deadline_ns'],
        automatic_retries=0,qualification_repeated=False,phase18_authority=False))
    argv=['/usr/bin/python3','-B',c['files']['study_driver']['path'],'--run','--configuration',cfg['path'],
        '--configuration-sha256',cfg['sha256']]
    os.execv(argv[0],argv)


if __name__=='__main__':main()
