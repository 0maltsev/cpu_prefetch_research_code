"""Real disposable SSHSIG and public snapshots; no stand key or chmod of trust."""
import contextlib
import copy
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_signature_v1 as signature


class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.stack=contextlib.ExitStack();self.addCleanup(self.stack.close)
        factory=tempfile.TemporaryDirectory
        self.root=Path(self.stack.enter_context(factory(prefix='s180-public-trust-',
            dir=Path(__file__).resolve().parents[1]/'build')))
        self.key=self.root/'owner';self.payload=b'SOFTWARE SIGNATURE VERIFICATION ONLY'
        subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(self.key)],
            check=True,capture_output=True,timeout=10)
        self.message=self.root/'message';self.message.write_bytes(self.payload)
        subprocess.run(['/usr/bin/ssh-keygen','-Y','sign','-f',str(self.key),'-n','software-only',str(self.message)],
            check=True,capture_output=True,timeout=10)
        self.sig=Path(str(self.message)+'.sig');self.allowed=self.root/'allowed-signers'
        raw=b'research-owner namespaces="software-only" '+self.key.with_suffix('.pub').read_bytes()
        self.allowed.write_bytes(raw);self.allowed.chmod(0o600)
        self.trust=dict(measurements=dict(allowed_signers_path=str(self.allowed),allowed_signers_size_bytes=len(raw),
            allowed_signers_sha256=hashlib.sha256(raw).hexdigest(),principal='research-owner',sshsig_namespace='software-only'))
        # /run is the actual qualified root destination. The single-UID test
        # namespace uses its own protected fixture tree for ephemeral copies.
        self.stack.enter_context(mock.patch.object(signature.tempfile,'TemporaryDirectory',
            side_effect=lambda **kwargs:factory(prefix=kwargs['prefix'],dir=self.root)))

    def test_same_owner_public_contract_still_accepts_actual_signature(self):
        signature._verify_signature(self.payload,self.sig,self.trust)

    def test_actual_public_projection_keeps_original_bytes_and_context(self):
        before=self.allowed.stat();trust=copy.deepcopy(self.trust);raw=self.allowed.read_bytes()
        signature._projected_verify(self.payload,self.sig,self.trust,raw)
        self.assertEqual(signature.archive.file_stamp(self.allowed.stat()),signature.archive.file_stamp(before))
        self.assertEqual(self.allowed.read_bytes(),raw);self.assertEqual(self.trust,trust)
        self.assertFalse(list(self.root.glob('cpu-prefetch-s180-public-trust-*')))

    def test_wrong_payload_or_namespace_rejected_with_actual_projection(self):
        with self.assertRaises(signature.ControllerError):
            signature._projected_verify(self.payload+b'changed',self.sig,self.trust,self.allowed.read_bytes())
        self.trust['measurements']['sshsig_namespace']='wrong'
        with self.assertRaises(signature.ControllerError):
            signature._projected_verify(self.payload,self.sig,self.trust,self.allowed.read_bytes())

    def test_hash_extent_and_protection_drift_rejected(self):
        for field,value in (('allowed_signers_sha256','0'*64),('allowed_signers_size_bytes',1)):
            trust=copy.deepcopy(self.trust);trust['measurements'][field]=value
            with self.subTest(field=field),self.assertRaises(signature.ControllerError):
                signature._verify_signature(self.payload,self.sig,trust)
        self.allowed.chmod(0o622)
        with self.assertRaisesRegex(signature.ControllerError,'protection'):
            signature._verify_signature(self.payload,self.sig,self.trust)

    def test_original_trust_mutation_during_verification_is_detected(self):
        original=signature.legacy._verify_signature
        def changed(*args):
            original(*args);self.allowed.write_bytes(self.allowed.read_bytes())
        with mock.patch.object(signature.legacy,'_verify_signature',side_effect=changed):
            with self.assertRaisesRegex(signature.ControllerError,'changed through'):
                signature._verify_signature(self.payload,self.sig,self.trust)

    def test_unknown_owner_is_rejected_before_snapshot(self):
        with mock.patch.object(signature.os,'fstat',return_value=SimpleNamespace(st_uid=1001)):
            with self.assertRaisesRegex(signature.ControllerError,'unrecognized'):
                signature._verify_signature(self.payload,self.sig,self.trust)

    def test_symlink_and_hardlink_public_trust_rejected(self):
        other=self.root/'other';other.symlink_to(self.allowed)
        trust=copy.deepcopy(self.trust);trust['measurements']['allowed_signers_path']=str(other)
        with self.assertRaisesRegex(signature.ControllerError,'canonical'):
            signature._verify_signature(self.payload,self.sig,trust)
        other.unlink();os.link(self.allowed,other)
        with self.assertRaisesRegex(signature.ControllerError,'protection'):
            signature._verify_signature(self.payload,self.sig,self.trust)


if __name__=='__main__':unittest.main()
