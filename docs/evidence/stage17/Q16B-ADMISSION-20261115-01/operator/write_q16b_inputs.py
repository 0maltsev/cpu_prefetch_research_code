"""Publish unsigned prospective inputs only; no family, signature or worker."""
import hashlib,json,os,pathlib,sys
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'formal-q16b-preparation-1'
assert os.getuid()==os.geteuid()==1000
sys.path.insert(0,str(E/'q16b-admission-operators-1'));import stage17_formal_admin_v1 as admin
admin.activate_packet('34db47d894557354e871b7699182ffd3a8bd12cc094374ccf380a715f43a7648')
import stage17_formal_archive_v1 as archive
rpath=E/'admission-root/evidence/formal-q16a-1/request.json';rbytes=rpath.read_bytes();assert hashlib.sha256(rbytes).hexdigest()=='aa780db91ceaaedca11fe3b4036c3506e9de80b5a25c6189c69c7a065ed8026a'
pbytes=(P/'plan.json').read_bytes();assert hashlib.sha256(pbytes).hexdigest()=='ba4f0eb1371d3a4dfb0945f9177c98993a08bd6c7ebcf188b4ab40cf5ac2f702'
r=json.loads(rbytes);plan=json.loads(pbytes)
def bind(p):
 raw=p.read_bytes();return dict(path=str(p),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
prereq=dict(r['action_inputs']['prerequisite_bindings']);prereq.update(q16a_validation=bind(E/'q16b-handoff-preparation-1/q16a-handoff.json'),q16b_validation=None,namespace_registry=bind(P/'namespace_registry.json'),schedule_sources=[])
assert prereq['q16a_validation']['sha256']=='0d4e2d233167fc6157001b0fe38e763a77dbbcd65a19b7ef2e09c2563c02c4bb'
doc=dict(plan=plan,hardware_control=r['action_inputs']['hardware_control'],prerequisite_bindings=prereq)
raw=archive.canonical(doc);out=P/'action-inputs-proposal.json';assert not out.exists()
with out.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
fd=os.open(P,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
print(json.dumps(dict(status='UNSIGNED_Q16B_INPUTS_PUBLISHED',path=str(out),size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),plan_sha256=hashlib.sha256(pbytes).hexdigest(),namespace_registered=False,signature_created=False,experiment_started=False,execution_authority=False),sort_keys=True))
