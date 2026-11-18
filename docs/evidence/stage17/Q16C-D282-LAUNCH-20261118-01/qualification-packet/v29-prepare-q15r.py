import datetime,json,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29';NAME='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';B=E/'local-bundle-extract'/NAME;A=E.parent/(NAME+'.tar.gz');S=pathlib.Path(str(A)+'.sha256');actor='maltsev.oiu@phystech.edu'
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def op(*args):
 print('OPERATOR',utc(),json.dumps(list(map(str,args))),flush=True);subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
def cli(*args):op('python3','-B',R/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args)
def author(kind,*args):op('python3','-B',P/'author_fresh_qualification_records_v2.py',kind,'--repository-root',R,'--evidence-root',E,'--bundle-root',B,'--pilot-archive',A,'--pilot-sidecar',S,'--id-prefix','CPU-PREFETCH-V5-V29','--archive-runtime-root','/',*args)

import sys
sys.path.insert(0,str(P))
import run_clock_qualification_v29 as isolation
assert json.loads((E/'clock-qualification-v29-1/complete.json').read_bytes())['both_pairs_passed'] is True
isolation.isolated_state()
assert not list(E.glob('stage17-q15*')),'Q15 execution artifacts already exist'
author('q15r-inputs','--probe-cpu','0')
QR=R/'evidence/q15r-fresh'
op('mkdir','-m','0700',QR)
prefix='CPU-PREFETCH-V5-V29'
cli('author-request','--action','Q15-R','--action-inputs',E/'q15r-action-inputs-1.json','--request-id',prefix+'-Q15R-REQUEST-1','--session-id',prefix+'-Q15-SESSION-1','--authorization-id',prefix+'-Q15R-AUTH-1','--attempt-id',prefix+'-Q15R-ATTEMPT-1','--output-root',E,'--output',QR/'request.json')
issued=utc();expires=(datetime.datetime.fromisoformat(issued.replace('Z','+00:00'))+datetime.timedelta(seconds=1800)).isoformat().replace('+00:00','Z')
cli('author-authorization','--request',QR/'request.json','--actor',actor,'--reviewer','OWNER','--issued-at-utc',issued,'--expires-at-utc',expires,'--output',QR/'authorization.json')
assert not (QR/'authorization.json.sig').exists()
op('ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',QR/'authorization.json')
cli('verify-signature','--authorization',QR/'authorization.json','--signature',QR/'authorization.json.sig')
