import datetime,json,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-19');R=E/'admission-root';Q=R/'evidence/discovery-r2-fresh'
A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-ac64633-clean-91a93014b4eb.tar.gz';S=pathlib.Path(str(A)+'.sha256')
def op(*args):
    print('OPERATOR',datetime.datetime.now(datetime.timezone.utc).isoformat(),json.dumps(list(map(str,args))),flush=True)
    subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
def cli(command,*args):
    op('python3','-B',R/'tools/stage17_operational_cli_v16.py',command,'--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args)
request=json.loads((Q/'request.json').read_bytes())
assert request['action_id']=='Q16A-DURATION-DISCOVERY' and request['synthetic_test_only'] is False
now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
duration=(request['action_inputs']['plan']['budget']['watchdog_ns']+999999999)//1000000000
utc=lambda x:x.isoformat().replace('+00:00','Z')
cli('author-discovery-authorization','--request',Q/'request.json','--actor','maltsev.oiu@phystech.edu','--reviewer','OWNER','--issued-at-utc',utc(now),'--expires-at-utc',utc(now+datetime.timedelta(seconds=duration)),'--output',Q/'authorization.json')
op('ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',Q/'authorization.json')
cli('verify-discovery-signature','--authorization',Q/'authorization.json','--signature',Q/'authorization.json.sig')
print('FINITE_DISCOVERY_AUTHORITY_VERIFIED_NOT_EXECUTED',flush=True)
