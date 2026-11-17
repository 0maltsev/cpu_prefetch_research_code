"""Real file custody/permissions and closed inventory before any native launch."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import check_stage17_execution_owner_v1 as current


class OwnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.worker=self.root/'release/bin/cpu_prefetch_runner';self.worker.parent.mkdir(parents=True)
        self.worker.write_bytes(b'synthetic nonexecuted worker');self.worker.chmod(0o755)
        (self.root/'BUNDLE_MANIFEST.json').write_bytes(b'{}');(self.root/'SHA256SUMS').write_bytes(b'synthetic checksums\n')
        rows=[]
        for name in ('BUNDLE_MANIFEST.json','release/bin/cpu_prefetch_runner'):
            raw=(self.root/name).read_bytes();rows.append(dict(path=name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        raw=json.dumps(dict(source_revision='1'*40,files=rows)).encode();(self.root/'BUNDLE_INVENTORY.json').write_bytes(raw)
        self.args=dict(uid=os.geteuid(),inventory_sha256=hashlib.sha256(raw).hexdigest(),source_revision='1'*40,
            worker_sha256=rows[1]['sha256'])

    def test_complete_owner_and_exact_byte_admission_executes_nothing(self):
        result=current.check(self.root,**self.args)
        self.assertEqual(result['checked_files'],4);self.assertEqual(result['inventory_entries'],2)
        self.assertIs(result['worker_executed'],False);self.assertIs(result['permissions_changed'],False)

    def test_real_wrong_owner_is_rejected_at_the_original_failure_boundary(self):
        with self.assertRaisesRegex(ValueError,'not an execution-owner regular file'):
            current.owned(self.worker,os.geteuid()+1,executable=True)

    def test_executable_mode_and_group_write_guards(self):
        self.worker.chmod(0o644)
        with self.assertRaisesRegex(ValueError,'not executable'):current.check(self.root,**self.args)
        self.worker.chmod(0o775)
        with self.assertRaisesRegex(ValueError,'group/world writable'):current.check(self.root,**self.args)

    def test_changed_missing_and_unlisted_files_reject(self):
        original=self.worker.read_bytes();self.worker.write_bytes(original+b'x')
        with self.assertRaisesRegex(ValueError,'bytes differ'):current.check(self.root,**self.args)
        self.worker.write_bytes(original);extra=self.root/'unexpected.py';extra.write_bytes(b'pass')
        with self.assertRaisesRegex(ValueError,'unlisted'):current.check(self.root,**self.args)
        extra.unlink();self.worker.unlink()
        with self.assertRaisesRegex(ValueError,'missing'):current.check(self.root,**self.args)

    def test_symlink_cannot_replace_owned_regular_worker(self):
        self.worker.unlink();self.worker.symlink_to(self.root/'BUNDLE_MANIFEST.json')
        with self.assertRaisesRegex(ValueError,'not an execution-owner regular file'):current.check(self.root,**self.args)

    def test_authenticated_empty_evidence_is_valid_without_weakening_worker_identity(self):
        p=self.root/'BUNDLE_MANIFEST.json';p.write_bytes(b'')
        inv=self.root/'BUNDLE_INVENTORY.json';v=json.loads(inv.read_bytes())
        v['files'][0].update(size_bytes=0,sha256=hashlib.sha256(b'').hexdigest())
        raw=json.dumps(v).encode();inv.write_bytes(raw);self.args['inventory_sha256']=hashlib.sha256(raw).hexdigest()
        self.assertEqual(current.check(self.root,**self.args)['status'],'PASS')


if __name__=='__main__':unittest.main()
