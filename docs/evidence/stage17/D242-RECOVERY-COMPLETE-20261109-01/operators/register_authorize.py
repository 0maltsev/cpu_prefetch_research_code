"""One D240 registration and separately signed authority; no worker invocation."""
from pathlib import Path
import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time

E = Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25')
OLD = E.parent/'local-authoring-cpuprefetchv5-23'
ADMIN = E/'d242-admin-1'
R = E/'admission-root'
P = E/'formal-q16a-continuation-authoring-1'
NAME = 'cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a'
B = E/'local-bundle-extract'/NAME
A = E.parent/(NAME+'.tar.gz')
S = Path(str(A)+'.sha256')
AUTH = R/'evidence/formal-q16a-1'
PLAN_SHA = '91c83558b5c5d891cabdd4d875da1292120df5940397298063d55c901a8866c2'
sys.path[:0] = [str(ADMIN),str(R/'tools')]
import stage17_operational_cli_v18 as cli
import stage17_state_journal_v53 as recovery
import stage17_phase_controller_v26 as controller
cli.activate(); recovery.activate()


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def register(plan):
    assert json.loads((P/'prepare-launch-inputs-2.json').read_bytes())['exit_code'] == 0
    profile = B/'config/stage17/formal-archive-implementation-profile-v1.json'
    admission = OLD/'formal-program-storage-admission-1.json'
    deadline = time.monotonic_ns()+plan['budget']['setup_ns']
    command = ['/usr/bin/python3.14','-B',str(ADMIN/'register_family.py'),
        '--repository-root',str(R),'--evidence-root',str(E),'--pilot-archive',str(A),'--pilot-sidecar',str(S),
        '--program-root',str(OLD/'formal-archive-program-1'),'--plan',str(P/'plan.json'),'--plan-sha256',PLAN_SHA,
        '--scope-sha256',plan['storage']['program_scope_sha256'],'--admission',str(admission),
        '--admission-sha256',digest(admission),'--profile',str(profile),'--profile-sha256',digest(profile),
        '--deadline-monotonic-ns',str(deadline),'--output',str(P/'family-registration-1.json'),'--register']
    with (P/'register-family-1.log').open('xb') as log:
        subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=150)
    receipt=json.loads((P/'family-registration-1.json').read_bytes())
    assert receipt['registered'] is True and receipt['plan_sha256'] == PLAN_SHA
    print(json.dumps(dict(registered=True,working_root=receipt['working_root'],plan_sha256=PLAN_SHA,experimental_invocation=False)),flush=True)


def authorize(plan):
    receipt=json.loads((P/'family-registration-1.json').read_bytes())
    assert receipt['registered'] is True and receipt['plan_sha256'] == PLAN_SHA
    output=Path(receipt['working_root'])
    assert output.is_dir() and not list(output.iterdir())
    AUTH.mkdir(mode=0o700)
    common=dict(repository_root=R,evidence_root=E,pilot_archive=A,pilot_sidecar=S)
    prefix='CPU-PREFETCH-V5-V25-Q16A'
    cli.author_formal_request(**common,action_id='Q16a',action_inputs_path=P/'action-inputs.json',
        request_id=prefix+'-REQUEST-1',authorization_id=prefix+'-AUTH-1',attempt_id=prefix+'-ATTEMPT-1',
        session_id=prefix+'-SESSION-1',output_root=output,destination=AUTH/'request.json')
    extent=controller.contract.validate_plan('Q16a',plan)
    policy=controller.deadline_policy(extent)
    now=dt.datetime.now(dt.timezone.utc)
    stamp=lambda value:value.isoformat().replace('+00:00','Z')
    cli.author_formal_authorization(**common,request_path=AUTH/'request.json',actor='maltsev.oiu@phystech.edu',
        reviewer='OWNER',issued_at_utc=stamp(now),
        expires_at_utc=stamp(now+dt.timedelta(seconds=policy['session_max_wall_seconds'])),
        destination=AUTH/'authorization.json')
    subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519',
        '-n','stage17-owner-acceptance',str(AUTH/'authorization.json')],check=True,timeout=15)
    # Signature verification and all resource/isolation admission remain mandatory
    # in the existing launcher --check and again before its one execution.
    print(json.dumps(dict(request_sha256=digest(AUTH/'request.json'),authorization_sha256=digest(AUTH/'authorization.json'),
        signature_sha256=digest(AUTH/'authorization.json.sig'),experimental_invocation=False)),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('register','authorize'))
    args=parser.parse_args()
    assert os.geteuid()==1000
    recovery.admin_binding()
    assert digest(P/'plan.json')==PLAN_SHA
    plan=json.loads((P/'plan.json').read_bytes())
    assert len(plan['captures'])==531 and plan['source_revision']==recovery.SOURCE
    (register if args.operation=='register' else authorize)(plan)


if __name__=='__main__':main()
