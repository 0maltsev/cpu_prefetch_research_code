"""Create only a cold archive candidate and authenticate its exact source closure."""
import hashlib,json,pathlib,sys,types,os
E=pathlib.Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-25');P=E/'q16b-admission-operators-5';B=E/'local-bundle-extract/cpu-prefetch-pilot-candidate-2.0.0-42f2ebb-clean-e808f93edb5a';D=E/'q16b-native-archive-bundle-3';N=E/'q16b-native-archive-preparation-1';SOURCE='701dbabd100b33c53cd68b62f56e809c871a11fb'
assert os.getuid()==os.geteuid()==1000
old=E/'offline-suffix-operators-1';path=old/'validate_suffix.py';raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()=='b1feb13f9cbcfa9ec6c41d11662c64f1b8f11d591f311f75a2d166f6fe94be23'
sys.path.insert(0,str(old));m=types.ModuleType('validate_suffix');m.__file__=str(path);sys.modules[m.__name__]=m;exec(compile(raw,str(path),'exec'),m.__dict__)
c=m.config(E/'offline-suffix-preparation-1/inputs/analysis-config.json','5eab201fc805e5eee6921e67719cb3f9a7ffa008cf7d2835a740d9d61b322e93');m.modules(c)
sys.path.insert(0,str(P));import stage17_archive_overlay_v1 as overlay
library=N/'libcpu_prefetch_stage17_archive_inverse.so';assert hashlib.sha256(library.read_bytes()).hexdigest()=='3aff20a92b35eadb698cdb0bb28707d903952edbd2649f24f84edceacd8225d3'
descriptor=overlay.build_overlay(baseline_bundle_root=B,runtime_root=pathlib.Path('/'),destination=D,native_library=library,wrapper=P/'stage17_archive_inverse_native_v1.py',source_revision=SOURCE)
raw=overlay.canonical(descriptor)
with (P/'archive-overlay.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
files=[]
for path in sorted(P.iterdir()):
 if path.is_file():
  raw=path.read_bytes();files.append(dict(name=path.name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
manifest=dict(schema_version='cpu-prefetch-stage17-formal-admin-packet/3',source_revision=SOURCE,qualified_worker_unchanged=True,execution_authority=False,files=files)
raw=overlay.canonical(manifest)
with (P/'manifest.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
report=dict(status='COLD_NATIVE_ARCHIVE_OVERLAY_BUILT',source_revision=SOURCE,descriptor=overlay.binding(P/'archive-overlay.json'),manifest=overlay.binding(P/'manifest.json'),profile=descriptor['overlay_profile'],native_image=descriptor['native_image'],historical_bundle_unchanged=True,measurements_performed=False,execution_authority=False)
raw=overlay.canonical(report)
with (N/'overlay-publication-3.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
print(json.dumps(report,sort_keys=True))
