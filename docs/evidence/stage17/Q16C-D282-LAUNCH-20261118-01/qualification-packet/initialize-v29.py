import hashlib,os,pathlib,subprocess
parent=pathlib.Path('/home/omaltsev/stage17-owner-evidence')
name='cpu-prefetch-pilot-candidate-2.0.0-7fb8944-clean-4f94fa5cf272'
archive=parent/(name+'.tar.gz'); sidecar=pathlib.Path(str(archive)+'.sha256')
expected='54d017c8cabac7443c14dc863850e1e463b96bbbaf71885c1507a266e4dd11ab'
assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==expected
assert sidecar.read_text()==expected+'  '+archive.name+'\n'
evidence=parent/'local-authoring-cpuprefetchv5-29'
assert evidence.is_dir() and (evidence/'package-preparation-1/verification.json').is_file()
extract=evidence/'local-bundle-extract'
bundle=extract/name
def operator(*args):
 subprocess.run(['runuser','-u','omaltsev','--',*map(str,args)],check=True)
operator('python3','-B',bundle/'validators/verify_stand_bundle.py','--root',bundle)
operator('python3','-B',bundle/'tools/stage17_operational_cli_daycap_v4.py','--repository-root',bundle,'--evidence-root',evidence,'--pilot-archive',archive,'--pilot-sidecar',sidecar,'init','--materialize-admission-root')
print('DEPLOY_AND_INITIALIZE_PASS',bundle,evidence,flush=True)

assert hashlib.file_digest((bundle/'release/bin/cpu_prefetch_runner').open('rb'),'sha256').hexdigest()=='7455fa2802ca5f655c41faddd070da51b0cf98ac9c8b2360152dc1a480f85f2a'
