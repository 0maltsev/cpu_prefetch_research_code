"""Real closed D256 bytes through the D257 loader; software imports only."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('loader_subject',HERE/'operators/administration_loader.py')
loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
def read(b):
 raw=Path(b['path']).read_bytes()
 if len(raw)!=b['size_bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('bound bytes differ')
 return raw
def binding(p):return dict(path=str(p),size_bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
class LoaderTests(unittest.TestCase):
 def test_closed_packet_and_private_graph_and_cache_rejection(self):
  with tempfile.TemporaryDirectory() as directory:
   d=Path(directory)
   fixture=ROOT/'docs/evidence/stage17/D256-E26-REPAIR-20261115-01'
   for name in ('stage17_state_journal_v55.py','stage17_daycap_administration_v1.py','stage17_daycap_administration_v2.py','stage17_e26_transition_repair.py'):
    shutil.copyfile(ROOT/'tools'/name,d/name)
   shutil.copyfile(ROOT/'docs/decisions/0256-stage17-e26-transition-authority-renewal.md',d/'decision.md')
   shutil.copyfile(fixture/'administrative-owner-acceptance.json',d/'owner-acceptance.json')
   shutil.copyfile(fixture/'administrative-manifest.json',d/'manifest.json')
   loader.DIRECTORY=d
   cfg=dict(administration_manifest=binding(d/'manifest.json'),administration=binding(d/'stage17_daycap_administration_v2.py'))
   changed=json.loads(json.dumps(cfg));changed['administration_manifest']['sha256']='0'*64
   with self.assertRaises(ValueError):loader.load(changed,read)
   decision=(d/'decision.md').read_bytes();(d/'decision.md').write_bytes(b'altered')
   with self.assertRaises(ValueError):loader.load(cfg,read)
   (d/'decision.md').write_bytes(decision)
   sys.path.insert(0,str(ROOT/'build/stage17-daycap-120/release-source-aa3285f/tools'))
   cli=loader.load(cfg,read)
   self.assertEqual(Path(cli.journal.__file__),d/'stage17_state_journal_v55.py')
   self.assertIs(cli.controller._v25._prepare_action.__globals__['journal_runtime'],cli.journal)
   self.assertIs(cli.controller._validate_inputs.__globals__['handoff'].consume,sys.modules['stage17_daycap_administration_v1'].consume)
   with self.assertRaisesRegex(ValueError,'cached'):loader.load(cfg,read)
if __name__=='__main__':unittest.main()
