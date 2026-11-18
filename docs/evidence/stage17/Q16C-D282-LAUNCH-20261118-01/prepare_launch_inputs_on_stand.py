"""Bind prepared inputs and authenticate empty attempt; never starts a window."""
import hashlib,json,os,sys,time
from pathlib import Path
E=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-29');P=E/'q16c-configuration-1';Q=E/'operator-preparation-v29';R=E/'admission-root';O=E.with_name('local-authoring-cpuprefetchv5-28');B=next((E/'local-bundle-extract').iterdir())
def binding(p):
 p=Path(p);assert not any(x.is_symlink() for x in (p,*p.parents));raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def load(p):return json.loads(Path(p).read_bytes())
def save(p,x):
 with p.open('x') as f:json.dump(x,f,sort_keys=True,separators=(',',':'));f.flush();os.fsync(f.fileno())
 os.chown(p,1000,1000)
c=load(O/'q16c-d277-launch-inputs-1.json');c.update(administrative_source_revision='19c3b60a',evidence_root=str(E),packet_root=str(P),repository_root=str(R),output_root=str(E/'q16c-authoring-1'),cgroup='/sys/fs/cgroup/cpu-prefetch-recovery-v29-qualified-1.service/reserved',source_revision='7fb894425c82fa7d7f1891f52b3bcdacc2c83585',bundle_inventory_sha256=binding(B/'BUNDLE_INVENTORY.json')['sha256'],worker=binding(B/'release/bin/cpu_prefetch_runner'))
c['administrative_source_revision']=load(P/'manifest.json')['administrative_source_revision']
for key,name in dict(action_operator='stage17_q16c_operator_v3.py',preparation_operator='stage17_q16c_prepare_v3.py',study_driver='stage17_q16c_study_v5.py',loader='stage17_q16c_packet_v3.py',manifest='manifest.json',archive_preparation='archive-preparation.json',frozen_plan='plan.json',plan_preview='plan.json',geometry_provenance='native-geometry-provenance.json',local_audit='local-namespace-audit.json',stand_audit='stand-namespace-audit.json',window_helper='stage17_q16c_execution_window_v2.py',ownership_core='original_supervisor.py',restoration_helper='stage17_q16c_restoration_v1.py',execution_owner_guard='check_stage17_execution_owner_v1.py').items():c['files'][key]=binding(P/name)
c['files']['clock_adapter']=binding(Q/'run_clock_qualification_v29.py');c['files']['isolation_core']=binding(Path('/run/cpu-prefetch-recovery-v29-qualified-1/isolation_core.py'));c['files']['source_reuse']=binding(E/'source-bank-reuse-3/reuse-proof.json');c['files']['policy']=binding(R/'config/stage17/stage17-operational-evidence-admission-policy-v62.json')
a=B.parent.parent.parent/(B.name+'.tar.gz');assert a==E.parent/(B.name+'.tar.gz');c['files']['archive']=binding(a);c['files']['sidecar']=binding(Path(str(a)+'.sha256'))
for key in ('execution_window','execution_window_signature'):c['files'].pop(key)
for key,b in c['files'].items():assert binding(b['path'])==b,key
for key in ('local_audit','stand_audit'):
 d=load(c['files'][key]['path']);assert d['status']=='PASS_SCOPED_HISTORY_AUDIT' and not d['matches'] and not d['errors'];assert d['planned_numeric_seeds']==432
sys.path.insert(0,str(R/'tools'));sys.path.insert(0,str(P));import stage17_q16c_empty_reuse_v1 as reuse
reuse.inspect(load(c['files']['source_reuse']['path']),load(P/'plan.json'))
assert len(list((E/'journal').glob('*.json')))==1 and not (E/'qualification-family-intent-1.json').exists()
assert c['files']['source_manifest']['sha256']=='017e8a64630ba57207ecf08fc98b67908c77acafb0f2e483bbfb24d3e2206b00'
save(E/'d282-launch-preparation-1.json',c)
print(json.dumps(dict(status='ALL_PREPARED_INPUTS_AND_EMPTY_ATTEMPT_BOUND',configuration=binding(E/'d282-launch-preparation-1.json'),window_started=False)),flush=True)
