"""Install D285 correction layer and bind original metadata; no launch."""
import hashlib,json,os,sys,tarfile
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');S=E/'q16c-continuation-1';P=E/'q16c-configuration-1'
assert os.geteuid()==0 and not S.exists()
def binding(p):
 raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(p):return json.loads(p.read_bytes())
def save(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,separators=(',',':'));f.flush();os.fsync(f.fileno())
 os.chown(p,1000,1000);os.chmod(p,0o444)
S.mkdir(mode=0o700);os.chown(S,1000,1000)
with tarfile.open(E/'d285-preparation-1.tar') as t:
 for m in t.getmembers():
  assert m.isfile() and Path(m.name).name==m.name
  p=S/m.name
  with p.open('xb') as f:f.write(t.extractfile(m).read())
  os.chown(p,1000,1000);os.chmod(p,0o444)
m=load(S/'continuation-manifest.json')
for row in m['files']:assert binding(S/row['name'])==dict(path=str(S/row['name']),size_bytes=row['size_bytes'],sha256=row['sha256'])
assert binding(P/'manifest.json')['sha256']=='731e59e84edd1a56d1ea54d37ba055dffc990d09f88b6ea83084214c8f6f023a'
c=load(E/'q16c-operational-configuration-1.json');assert c['administrative_source_revision']=='19c3b60c57e21137a3cbfef173304f993536dbaa'
c.update(output_root=str(E/'q16c-authoring-2'),continuation_source_revision=m['administrative_source_revision'])
for k,n in dict(loader='stage17_q16c_d285_loader_v1.py',preparation_operator='stage17_q16c_resume_preparation_v2.py',study_driver='stage17_q16c_study_v6.py',action_operator='stage17_q16c_operator_v4.py',clock_adapter='stage17_q16c_continuation_isolation_v1.py',fixed_guard='stage17_q16c_empty_reuse_v1.py',rearm_operator='launch_stage17_q16c_rearmed_v2.py',continuation_manifest='continuation-manifest.json',continuation_decision='0285-q16c-unarmed-d284-continuation.md').items():c['files'][k]=binding(S/n)
for k,n in dict(prior_study_complete='q16c-study-1/complete.json',prior_partition_restoration='q16c-study-1/partition-restoration.json',prior_construct_log='q16c-study-1/construct.log',verified_repair='source-reuse-constructor-software-check-1/complete.json',q15w_request='admission-root/evidence/q15w-fresh/request.json',q15w_completion='stage17-q15_w-completion-v4.json').items():c['files'][k]=binding(E/n)
retained=('q16a-context.json','q16b-context.json','q16a-compatibility.json','q16b-compatibility.json','historical-inputs.json','archive-overlay.json','cli-configuration.json','namespace-registry.json')
c['retained_metadata']={n:binding(P/n) for n in retained}
assert not (P/'action-inputs.json').exists() and not (E/'q16c-authoring-2').exists()
assert not (Path(c['program_root'])/'working'/c['files']['frozen_plan']['sha256']).exists()
assert not (E/'admission-root/evidence/formal-q16c-d282-1').exists()
for k,b in c['files'].items():assert binding(Path(b['path']))==b,k
save(S/'preconstruction-configuration.json',c)
print(json.dumps(dict(status='D285_SOFTWARE_CONFIGURATION_READY_NO_LAUNCH',configuration=binding(S/'preconstruction-configuration.json'),continuation_manifest=binding(S/'continuation-manifest.json'))),flush=True)
