"""Bind exact existing continuation, fresh isolation, and original qualification."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
P=E/'formal-q16a-continuation-authoring-1'
OLD=E.parent/'local-authoring-cpuprefetchv5-23'
NAME='cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
B=E/'local-bundle-extract'/NAME
A=E.parent/(NAME+'.tar.gz')
AUTH=E/'admission-root/evidence/formal-q16a-1'
Q=E/'isolation-preparation-v25-resume-1'


def main():
    assert os.geteuid()==1000
    handoff=json.loads((Q/'d242-reapplication-handoff.json').read_bytes())
    assert handoff['isolation_reapplied'] is True and handoff['qualification_repeated'] is False
    files=dict(plan=P/'plan.json',preparation=P/'preparation-provenance.json',
        request=AUTH/'request.json',authorization=AUTH/'authorization.json',signature=AUTH/'authorization.json.sig',
        admission=OLD/'formal-program-storage-admission-1.json',scope=OLD/'formal-archive-program-1/scope.json',
        profile=B/'config/stage17/formal-archive-implementation-profile-v1.json',manifest=B/'BUNDLE_MANIFEST.json',
        isolation_operator=Path('/run/cpu-prefetch-recovery-v25-qualified-1/isolation_core.py'),
        isolation_prestate=Q/'prospective-prestate.json',isolation_readback=Q/'d242-reapplication-handoff.json',
        clock_complete=E/'clock-qualification-v25-1/complete.json',q15_result=E/'stage17-q15-w-result-v4.json',
        q15_completion=E/'stage17-q15_w-completion-v4.json')
    assert len(files)==15
    command=['/usr/bin/python3.14','-B',str(E/'d242-admin-1/render_config.py'),
        '--repository-root',str(E/'admission-root'),'--evidence-root',str(E),'--bundle-root',str(B),
        '--program-root',str(OLD/'formal-archive-program-1'),'--launch-root',str(E/'formal-q16a-continuation-launch-1'),
        '--archive',str(A),'--sidecar',str(A)+'.sha256','--python','/usr/bin/python3.14','--setpriv','/usr/bin/setpriv',
        '--gid','1000','--controller-cpu','2','--supervisor-cpu','3','--output',str(P/'launch-config-1.json')]
    for role,path in files.items():command+=['--input-file',role,str(path)]
    subprocess.run(command,check=True,timeout=60)
    print('configuration_sha256',hashlib.sha256((P/'launch-config-1.json').read_bytes()).hexdigest())


if __name__=='__main__':main()
