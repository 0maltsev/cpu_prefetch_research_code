"""Author/sign one exact Q16b authority; never executes or changes isolation."""
import datetime as dt,hashlib,json,os,pathlib,subprocess,sys
from types import SimpleNamespace
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');R=E/'admission-root';N=E/'q16b-namespace-admission-2';A=E.parent/'cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a.tar.gz';AUTH=R/'evidence/formal-q16b-2';PLAN='6302de1e50b6178004eb3a8e4d24579c0b5ef74e8a1504e254297faed9f1f847'
assert os.getuid()==os.geteuid()==1000
sys.path.insert(0,str(N/'operators-v3'));import prepare_registration_q16b as prep
cli=prep.activate_verified_admin(SimpleNamespace(packet_root=E/'q16b-admission-operators-5',packet_manifest_sha256='6d133fd4150b8de5ce2dc01a83f15bc7be0253216e25f81555b5391bdf830919'))
receipt=json.loads((N/'family-registration-1.json').read_bytes());assert receipt['registered'] is True and receipt['plan_sha256']==PLAN and receipt['new_ledger_tip']['file_name']=='0000000000059578.json'
family=pathlib.Path(receipt['working_root']);assert family.is_dir() and not family.is_symlink() and not list(family.iterdir())
inputs=E/'formal-q16b-preparation-2/action-inputs-proposal.json';assert hashlib.sha256(inputs.read_bytes()).hexdigest()=='4f8785e3a931cba0696c636c1a0c866322802293018efc57840b9df9386a636f'
assert not AUTH.exists();AUTH.mkdir(mode=0o700)
common=dict(repository_root=R,evidence_root=E,pilot_archive=A,pilot_sidecar=pathlib.Path(str(A)+'.sha256'))
cli.author_formal_request(**common,action_id='Q16b',action_inputs_path=inputs,request_id='CPU-PREFETCH-V5-V26-Q16B-REQUEST-1',authorization_id='CPU-PREFETCH-V5-V26-Q16B-AUTH-1',attempt_id='CPU-PREFETCH-V5-V26-Q16B-ATTEMPT-1',session_id='CPU-PREFETCH-V5-V26-Q16B-SESSION-1',output_root=family,destination=AUTH/'request.json')
print('Q16B_REQUEST_PUBLISHED',flush=True)
request_raw=(AUTH/'request.json').read_bytes();request_sha=hashlib.sha256(request_raw).hexdigest();request=json.loads(request_raw);assert hashlib.sha256(cli.controller.previous.previous.archive.canonical(request['action_inputs']['plan'])).hexdigest()==PLAN
extent=cli.controller.contract.validate_plan('Q16b',request['action_inputs']['plan']);policy=cli.controller.deadline_policy(extent)
now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0);stamp=lambda value:value.isoformat().replace('+00:00','Z')
old=json.loads((R/'evidence/formal-q16a-1/authorization.json').read_bytes())
cli.author_formal_authorization(**common,request_path=AUTH/'request.json',actor=old['actor'],reviewer=old['reviewer'],issued_at_utc=stamp(now),expires_at_utc=stamp(now+dt.timedelta(seconds=policy['session_max_wall_seconds'])),destination=AUTH/'authorization.json')
assert hashlib.sha256((AUTH/'request.json').read_bytes()).hexdigest()==request_sha
assert not (AUTH/'authorization.json.sig').exists()
subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(AUTH/'authorization.json')],check=True,timeout=30,stdin=subprocess.DEVNULL)
def bind(p):
 b=p.read_bytes();return dict(path=str(p),size_bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
report=dict(status='NEW_Q16B_AUTHORITY_SIGNED_PENDING_LIVE_ADMISSION',completed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),plan_sha256=PLAN,request=bind(AUTH/'request.json'),authorization=bind(AUTH/'authorization.json'),signature=bind(AUTH/'authorization.json.sig'),deadline_policy=policy,phase_root=str(family),signature_namespace='stage17-owner-acceptance',isolation_prepared=False,experiment_started=False,phase18_authority=False)
out=N/'authority-publication-1.json'
with out.open('x') as f:json.dump(report,f,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
print(json.dumps(report,sort_keys=True),flush=True)
