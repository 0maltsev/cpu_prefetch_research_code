from pathlib import Path
import hashlib,io,json,os,subprocess,sys,tarfile
repo=Path.cwd();out=repo/'build/stage17-s180-service-prep'
assert not subprocess.check_output(['git','status','--porcelain']), 'clean source commit required'
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
sys.path.insert(0,str(repo/'tools'))
import stage17_s180_service_v1 as service
import stage17_s180_compaction_v1 as compaction
root=out/'package-2';root.mkdir()
names=['tools/stage17_s180_service_v1.py','tools/stage17_s180_execution_v1.py','tools/stage17_s180_family_analysis_v1.py','tools/stage17_s180_exit_v1.py','tools/stage17_s180_authority_v1.py','tools/stage17_s180_journal_v1.py','tools/stage17_s180_signature_v1.py',*service.RELOCATED]
for name in names:
 raw=subprocess.check_output(['git','show',revision+':'+name]);target=root/('stage17_s180_service_v1.py' if name=='tools/stage17_s180_service_v1.py' else name)
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
header=repo/'build/stage17-s180-release-source-34247ce'/service.HEADER
(root/service.HEADER).parent.mkdir(parents=True,exist_ok=True);(root/service.HEADER).write_bytes(header.read_bytes())
(root/'stop_post.py').write_bytes(compaction.stop_post_script())
(root/'metadata-timing.json').write_bytes((repo/'docs/evidence/stage17/PILOT-D364-SERVICE-EXIT-20261124-01/metadata-timing.json').read_bytes())
for name in service.SUPPORT:
 target=root/'support'/name;target.parent.mkdir(exist_ok=True);target.write_bytes((repo/'build/stage17-s180-qualification-evidence-prep/support'/name).read_bytes())
observed={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()};assert observed==service.MEMBERS
rows=[]
for name in sorted(observed):
 p=root/name;raw=p.read_bytes();p.chmod(0o444);rows.append(dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
profile=dict(schema_version=service.PROFILE_SCHEMA,source_revision=revision,files=rows)
raw=json.dumps(profile,sort_keys=True,separators=(',',':')).encode();(root/'profile.json').write_bytes(raw);(root/'profile.json').chmod(0o444)
digest=hashlib.sha256(raw).hexdigest()
for name,text in service.service_units(digest).items():(out/name).write_text(text)
archive=out/'package-2.tar'
with tarfile.open(archive,'w') as tf:
 for path in sorted(root.rglob('*')):
  if path.is_file():tf.add(path,arcname=path.relative_to(root).as_posix(),recursive=False)
result=dict(source_revision=revision,source_clean_verified=True,profile_sha256=digest,profile_size_bytes=len(raw),files=len(rows),transport_size_bytes=archive.stat().st_size,transport_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),operational_window_started=False,execution_authority=False)
(out/'service-package.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True,indent=2))
