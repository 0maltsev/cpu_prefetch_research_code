import datetime,json,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29';NAME='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';B=E/'local-bundle-extract'/NAME;A=E.parent/(NAME+'.tar.gz');S=pathlib.Path(str(A)+'.sha256');actor='maltsev.oiu@phystech.edu'
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def op(*args):
 print('OPERATOR',utc(),json.dumps(list(map(str,args))),flush=True);subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
def cli(*args):op('python3','-B',R/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args)
def author(kind,*args):op('python3','-B',P/'author_fresh_qualification_records_v2.py',kind,'--repository-root',R,'--evidence-root',E,'--bundle-root',B,'--pilot-archive',A,'--pilot-sidecar',S,'--id-prefix','CPU-PREFETCH-V5-V29','--archive-runtime-root','/',*args)


author('q15w-inputs')
QW=R/'evidence/q15w-fresh';op('mkdir','-m','0700',QW)
prefix='CPU-PREFETCH-V5-V29'
cli('author-request','--action','Q15-W','--action-inputs',E/'q15w-action-inputs-1.json','--request-id',prefix+'-Q15W-REQUEST-1','--session-id',prefix+'-Q15-SESSION-1','--authorization-id',prefix+'-Q15W-AUTH-1','--attempt-id',prefix+'-Q15W-ATTEMPT-1','--output-root',E,'--output',QW/'request.json')
issued=utc();expires=(datetime.datetime.fromisoformat(issued.replace('Z','+00:00'))+datetime.timedelta(seconds=1800)).isoformat().replace('+00:00','Z')
cli('author-authorization','--request',QW/'request.json','--actor',actor,'--reviewer','OWNER','--issued-at-utc',issued,'--expires-at-utc',expires,'--output',QW/'authorization.json')
assert not (QW/'authorization.json.sig').exists()
op('ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',QW/'authorization.json')
cli('verify-signature','--authorization',QW/'authorization.json','--signature',QW/'authorization.json.sig')
journal=subprocess.check_output(['runuser','-u','omaltsev','--','python3','-B',str(R/'tools/stage17_operational_cli_daycap_v4.py'),'--repository-root',str(R),'--evidence-root',str(E),'--pilot-archive',str(A),'--pilot-sidecar',str(S),'journal-path'],text=True).strip()
import sys
sys.path.insert(0,str(R/'tools'))
from stage17_q15_session_controller_v10 import _control_endpoint
control_id=_control_endpoint(json.loads((R/'evidence/q15r-fresh/request.json').read_bytes())['attempt_id'])[1:]
op('python3','-B',R/'tools/stage17_q15_session_controller_daycap_v4.py','--continue-q15-w','--control-id',control_id,'--journal',journal,'--journal-directory',E/'journal','--operational-evidence-root',E,'--authorization',QW/'authorization.json','--signature',QW/'authorization.json.sig','--pilot-archive',A,'--pilot-sidecar',S)
