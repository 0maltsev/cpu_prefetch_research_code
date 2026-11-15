"""Unsigned prefix reuse; no request, archive registration or native execution."""
import importlib.util,json,pathlib,tempfile,unittest,hashlib,types
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prefix_subject',HERE/'continuation-operators/preparation_prefix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
canon=lambda d:json.dumps(d,sort_keys=True,separators=(',',':')).encode()
def bind(p):return dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def read(b):
 raw=pathlib.Path(b['path']).read_bytes()
 if len(raw)!=b['size_bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('bound file changed')
 return raw
def write(p,v):
 with p.open('xb') as f:f.write(v if isinstance(v,bytes) else canon(v))
 return bind(p)
class PrefixTests(unittest.TestCase):
 def setUp(self):
  self.tmp=self.enterContext(tempfile.TemporaryDirectory());self.e=pathlib.Path(self.tmp)/'E26';self.e.mkdir();self.enterContext(patch.object(m,'E',self.e))
  self.out=self.e/'daycap-collection-preparation-1';self.out.mkdir();self.packet=self.e/'daycap-resume-configuration-1';self.packet.mkdir()
  failed=json.loads((HERE/'stand-handoff-2.json').read_bytes())['reports']['study-result.json']
  study=self.e/'daycap-resume-study-1';study.mkdir();self.failed=write(study/'study-result.json',failed)
  audit=write(self.out/'stand-namespace-audit.json',dict(status='FAIL',matches=[],errors=[dict(path=m.CAPACITY,reason='[Errno 13] Permission denied: original metadata')]))
  for n in ('plan.json','namespace_registry.json','action-inputs.json'):write(self.out/n,dict(software_only=n))
  write(self.out/'stand-namespace-audit.stderr',b'\n')
  for n in ('q16a-compatibility.json','historical-inputs.json'):write(self.packet/n,dict(software_only=n))
  reusable=[self.out/n for n in ('plan.json','namespace_registry.json','action-inputs.json')]+[self.packet/n for n in ('q16a-compatibility.json','historical-inputs.json')]
  self.d=dict(schema_version='software-d257-unsigned-preparation-prefix/1',plan_sha256=m.PLAN,failed_study=self.failed,failed_audit=audit,prefix_members=[bind(p) for p in sorted(self.out.iterdir())],reusable_files=[bind(p) for p in reusable],original_preparation_deadline_ns=1210558041457866,execution_authority=False,phase18_authority=False)
  self.config=self.e/'prefix.json';self.update()
 def update(self):self.config.write_bytes(canon(self.d));self.binding=bind(self.config)
 def adopt(self):return m.adopt(self.binding,read,write,canon,self.out,self.packet)
 def test_exact_recomputed_metadata_reuses_bytes_without_writes(self):
  f=self.adopt()
  for b in self.d['reusable_files']:
   p=pathlib.Path(b['path']);st=p.stat();self.assertEqual(f(p,json.loads(read(b))),b)
   self.assertEqual((p.stat().st_ino,p.stat().st_mtime_ns),(st.st_ino,st.st_mtime_ns))
  f(self.out/'new-report.json',dict(software_only=True))
 def test_recomputation_cannot_change_an_existing_plan(self):
  with self.assertRaises(ValueError):self.adopt()(self.out/'plan.json',dict(altered=True))
 def test_changed_or_expanded_prefix_stops(self):
  (self.out/'unexpected').write_bytes(b'x')
  with self.assertRaises(ValueError):self.adopt()
 def test_existing_signed_request_stops_before_reuse(self):
  p=self.e/'admission-root/evidence/formal-q16b-daycap-1';p.mkdir(parents=True)
  with self.assertRaises(ValueError):self.adopt()
 def test_any_collision_or_other_audit_error_stops(self):
  p=pathlib.Path(self.d['failed_audit']['path']);doc=json.loads(p.read_bytes());doc['matches']=[dict(collision=True)];p.write_bytes(canon(doc))
  self.d['failed_audit']=bind(p);self.d['prefix_members']=[bind(pathlib.Path(x['path'])) for x in self.d['prefix_members']];self.update()
  with self.assertRaises(ValueError):self.adopt()
 def test_executed_collection_is_not_a_metadata_prefix(self):
  p=pathlib.Path(self.failed['path']);doc=json.loads(p.read_bytes());doc['phases'].append(dict(phase='collection'));p.write_bytes(canon(doc));self.d['failed_study']=bind(p);self.update()
  with self.assertRaises(ValueError):self.adopt()
 def test_deadline_and_authority_cannot_be_extended(self):
  self.d['original_preparation_deadline_ns']+=1;self.update()
  with self.assertRaises(ValueError):self.adopt()
if __name__=='__main__':unittest.main()
