from pathlib import Path
import hashlib,importlib.util,json,os,subprocess,sys,tempfile
source=Path('/tmp/cpu-prefetch-s180-signature-check-1.py');raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='71ecc8c437997717a570fba60287de36576751fcc64610cab05b0fd6ac8d8ba1'
sys.path.insert(0,'/opt/cpu-prefetch-s180-common-0919b87-1/tools')
spec=importlib.util.spec_from_file_location('software_s180_public_trust_check',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
allowed=Path('/home/omaltsev/stage17-owner-evidence/local-authoring-cpuprefetchv5-32/ext002-authoring-1/ext002-allowed-signers')
before=allowed.stat();data=allowed.read_bytes();assert before.st_uid==1000 and len(data)==106 and hashlib.sha256(data).hexdigest()=='13071fb005c65eaaacd25bd1bf935a6edab0ea1d13a275f8ef09d91223ad0d48'
trust=dict(measurements=dict(allowed_signers_path=str(allowed),allowed_signers_size_bytes=106,allowed_signers_sha256=hashlib.sha256(data).hexdigest(),principal='maltsev.oiu@phystech.edu',sshsig_namespace='stage17-owner-acceptance'))
with tempfile.TemporaryDirectory(prefix='cpu-prefetch-s180-signature-software-',dir='/run') as directory:
 path=Path(directory)/'message';path.write_bytes(b'SOFTWARE PUBLIC TRUST ADAPTER VERIFICATION ONLY; NO EXECUTION AUTHORITY\n'+os.urandom(32));path.chmod(0o600)
 result=subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f','/home/omaltsev/.ssh/id_ed25519','-n','stage17-owner-acceptance',str(path)],stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
 assert result.returncode==0,'offline signer failed'
 module._verify_signature(path.read_bytes(),Path(str(path)+'.sig'),trust)
 try:module._verify_signature(path.read_bytes()+b'changed',Path(str(path)+'.sig'),trust)
 except module.ControllerError:rejected_changed_payload=True
 else:raise AssertionError('changed message was accepted')
after=allowed.stat();assert module.archive.file_stamp(before)==module.archive.file_stamp(after) and before.st_uid==after.st_uid==1000 and before.st_mode==after.st_mode and allowed.read_bytes()==data
source.unlink()
print(json.dumps(dict(status='ACTUAL_UID1000_PUBLIC_TRUST_ADAPTER_PASSED',source_sha256=hashlib.sha256(raw).hexdigest(),original_public_trust_owner_uid=1000,original_public_trust_bytes_and_mode_unchanged=True,changed_payload_rejected=rejected_changed_payload,operational_window_started=False,qualification_performed=False,scientific_captures_collected=0,execution_authority=False)))
