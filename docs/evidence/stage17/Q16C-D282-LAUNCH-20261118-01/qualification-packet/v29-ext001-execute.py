import datetime,json,os,pathlib,subprocess
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');R=E/'admission-root';P=E/'operator-preparation-v29'
NAME='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272';B=E/'local-bundle-extract'/NAME;A=E.parent/(NAME+'.tar.gz');S=pathlib.Path(str(A)+'.sha256')
actor='maltsev.oiu@phystech.edu';prefix='CPU-PREFETCH-V5-V29'
def utc():return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def operator(*args,capture=False):
 print('OPERATOR',utc(),json.dumps(list(map(str,args))),flush=True)
 return subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True,stdout=subprocess.PIPE if capture else None,text=capture)
def cli(*args,capture=False):return operator('python3','-B',R/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',R,'--evidence-root',E,'--pilot-archive',A,'--pilot-sidecar',S,*args,capture=capture)
assert len(list((E/'journal').glob('*.json')))==1,'fresh journal required'
attestation=P/'d124-attestation-v26.json'
operator('python3','-B',R/'tools/author_stage17_no_predecessor_attestation_v1.py','--attestation-id',prefix+'-D124-ATTESTATION-1','--actor',actor,'--search-evidence',P/'d124-combined-search-v26.json','--search-evidence-schema-identity','cpu-prefetch-stage17-d120-d121-d123-search-record/1','--output',attestation)
preflight=E/'ext001-preflight-output-1';operator('mkdir','-m','0700',preflight)
pin=E.parent/'local-authoring-cpuprefetchv5-14/ext001-authoring-1';x1=R/'evidence/ext001-v5-26'
now=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0);issued=now.isoformat().replace('+00:00','Z');expires=(now+datetime.timedelta(hours=2)).isoformat().replace('+00:00','Z')
cli('author-ext001','--stand-id','CPU-PREFETCH-V5','--ssh-target','omaltsev@localhost','--known-hosts-host','localhost','--pinned-host-public-key',pin/'pinned-host-public-key.txt','--pinned-known-hosts',P/'known-hosts-exact-localhost','--transport-identity','/home/omaltsev/.ssh/id_ed25519','--bundle-root-locator',B,'--capture-id',prefix+'-EXT001-CAPTURE-1','--captured-at-utc',issued,'--preflight-evidence-root',preflight,'--no-predecessor-attestation',attestation,'--actor',actor,'--issued-at-utc',issued,'--expires-at-utc',expires,'--authorization-id',prefix+'-EXT001-AUTH-1','--attempt-id',prefix+'-EXT001-ATTEMPT-1','--contract-id',prefix+'-EXT001-CONTRACT-1','--envelope-id',prefix+'-EXT001-ENVELOPE-1','--output-directory',x1)
cli('admit-resolution','--input-id','S17-EXT-001','--actor',actor,'--recorded-at-utc',utc(),'--repository-evidence',x1/'envelope-v14.json','--authorization-file',x1/'authorization-v11.json')
cli('append-transition','--actor',actor,'--timestamp-utc',utc())
journal=cli('journal-path',capture=True).stdout.strip()
command=['setpriv','--reuid=1000','--regid=1000','--clear-groups','--inh-caps=+sys_ptrace','--ambient-caps=+sys_ptrace','--','python3','-B',str(R/'tools/stage17_read_only_preflight_executor_v36.py'),'--execute','--repository-root',str(R),'--journal',journal,'--journal-directory',str(E/'journal')]
print('EXECUTE_BOUND_READONLY_PREFLIGHT',utc(),json.dumps(command),flush=True)
subprocess.run(command,check=True)
print('EXT001_PREFLIGHT_COMPLETE',utc(),flush=True)
