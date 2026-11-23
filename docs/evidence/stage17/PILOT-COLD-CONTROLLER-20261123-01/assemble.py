from pathlib import Path
import subprocess,tarfile,io,json,hashlib,shutil,os,datetime
repo=Path.cwd();rev=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert rev.startswith('0919b87') and not subprocess.check_output(['git','status','--porcelain'])
parent=repo/'build/stage17-s180-cold-operator-prep';target=parent/'package-0919b87-1';target.mkdir()
def extract(revision,names,destination):
 raw=subprocess.check_output(['git','archive',revision,*names]);destination.mkdir(parents=True,exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  assert all(m.isfile() or m.isdir() for m in t.getmembers()),'only regular source files/directories accepted'
  t.extractall(destination,filter='data')
extract(rev,['tools','config','docs','protocol'],target)
extract('34247cedab4abe4b44732daae8fdac1700eccffd',['include','src'],target/'frozen-native-source')
rules=json.loads((target/'config/stage17/s180-calibration-compatibility-review-v1.json').read_bytes())
release=repo/'build/stage17-s180-release-34247ce'
rows=[rules['current_worker'],rules['current_build_metadata'],rules['current_codegen'],*[r['current'] for r in rules['libraries']]]
rows.append(dict(path='cpu_prefetch_q15_clock_qualification_tool',size_bytes=478632,sha256='cb6422db0be2c3ff3b20897bc58ff4b892ba04e34e9f16f93a8b6d5a04caad69'))
for r in rows:
 src=release/r['path'];raw=src.read_bytes();assert len(raw)==r['size_bytes'] and hashlib.sha256(raw).hexdigest()==r['sha256']
 dest=target/'frozen-native-release'/r['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
helper=repo/'build/stage17-qualification-helper-release-3266ed3/cpu_prefetch_q15_qualification_evidence_tool'
raw=helper.read_bytes();assert len(raw)==700568 and hashlib.sha256(raw).hexdigest()=='6b8898238157e4d589615cbc6c57ced54aa143b403ef66bd337cab4960f3a918'
(target/'frozen-native-release'/helper.name).write_bytes(raw)
audit=repo/'build/stage17-s180-namespace-admission-prep/current-local-audit.json';raw=audit.read_bytes()
assert len(raw)==12165984 and hashlib.sha256(raw).hexdigest()=='36b26846c28842645346d3e67959c8a0d7e1a00ea5dfbaeaf2b9bad0f6534311'
(target/'inputs').mkdir();(target/'inputs/d342-local-audit.json').write_bytes(raw)
files=[]
for f in sorted(target.rglob('*')):
 if f.is_dir():f.chmod(0o555);continue
 raw=f.read_bytes();name=str(f.relative_to(target));mode=0o555 if name in ('frozen-native-release/cpu_prefetch_runner','frozen-native-release/cpu_prefetch_q15_clock_qualification_tool','frozen-native-release/cpu_prefetch_q15_qualification_evidence_tool') else 0o444
 f.chmod(mode);files.append(dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),mode=mode))
manifest=dict(schema_version='cpu-prefetch-stage17-s180-cold-operator-source-package/1',source_revision=rev,source_clean_verified=True,frozen_native_revision='34247cedab4abe4b44732daae8fdac1700eccffd',files=files,source_preparation_performed=False,qualification_performed=False,operational_window_started=False,execution_authority=False,phase18_authority=False)
raw=json.dumps(manifest,sort_keys=True,separators=(',',':')).encode();m=target/'S180_COLD_SOURCE_MANIFEST.json';m.write_bytes(raw);m.chmod(0o444)
archive=parent/'package-0919b87-1.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=3) as t:
 for f in sorted(target.rglob('*')):t.add(f,arcname=str(f.relative_to(target)),recursive=False)
result=dict(source_revision=rev,package_root=str(target),files=len(files)+1,payload_bytes=sum(x['size_bytes'] for x in files),manifest_size_bytes=len(raw),manifest_sha256=hashlib.sha256(raw).hexdigest(),transport_size_bytes=archive.stat().st_size,transport_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),cold_software_only=True,execution_authority=False,operational_window_started=False)
(parent/'assembly.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True,indent=2))
