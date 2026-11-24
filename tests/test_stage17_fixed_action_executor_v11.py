"""Actual parked worker, isolated broker and codecs; no hardware or science."""
import argparse
import ast
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from test_stage17_formal_checkpoint_v1 import fixture
from test_stage17_formal_archive_v1 import ArchiveFixture, digest
import test_stage17_formal_archive_runtime_v1 as runtime_fixture
import stage17_fixed_action_executor_v11 as executor
import stage17_formal_archive_v1 as archive
import stage17_formal_archive_custody_v1 as custody
import stage17_formal_archive_runtime_v1 as runtime
from stage17_formal_archive_registry_v1 import capture_names, role_profile

SCRIPT = r'''
import fcntl,hashlib,json,os,socket,sys,time
fd=lambda flag:int(sys.argv[sys.argv.index(flag)+1])
cfd=fd('--context-fd'); rfd=fd('--request-fd'); out=fd('--output-dir-fd')
mask=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE
assert fcntl.fcntl(cfd,fcntl.F_GET_SEALS)&mask==mask
assert fcntl.fcntl(rfd,fcntl.F_GET_SEALS)&mask==mask
context=json.loads(os.pread(cfd,1048576,0)); request_raw=os.pread(rfd,1048576,0)
request=json.loads(request_raw)
if context['fixture_mode']=='hang':time.sleep(30)
stream=os.open('formal-capture-0-final-checkpoint.json',os.O_RDONLY,dir_fd=out)
raw=os.read(stream,131072);os.close(stream)
binding=dict(file_name='formal-capture-0-final-checkpoint.json',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
channel=socket.socket(fileno=context['archive_channel']['descriptor'])
message=dict(schema_version='cpu-prefetch-stage17-archive-checkpoint-request/1',
 request_sha256=hashlib.sha256(request_raw).hexdigest(),
 program_scope_sha256=context['archive_channel']['program_scope_sha256'],
 capture_ordinal=0,checkpoint=binding,deadline_monotonic_ns=time.monotonic_ns()+30_000_000_000)
channel.send(json.dumps(message,sort_keys=True,separators=(',',':')).encode())
reply=json.loads(channel.recv(8192))
assert reply['status']=='ARCHIVED_AND_RELEASED' and reply['checkpoint_sha256']==binding['sha256']
print('ACKNOWLEDGED',flush=True)
'''


def profile_closure():
    tools = runtime_fixture.TOOLS
    pending, done = ['stage17_formal_archive_broker_v1'], set()
    while pending:
        name = pending.pop()
        if name in done: continue
        done.add(name)
        tree = ast.parse((tools / (name + '.py')).read_bytes())
        for node in ast.walk(tree):
            imports = ([entry.name.split('.')[0] for entry in node.names] if isinstance(node, ast.Import)
                       else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            pending.extend(n for n in imports if (tools / (n + '.py')).is_file() and n not in done)
    return tuple(runtime.ModuleBinding(name, runtime_fixture.image(tools / (name + '.py'))) for name in sorted(done))


class ArchivedWorkerTests(unittest.TestCase):
    encoder = None

    def setUp(self):
        if self.encoder is None: self.skipTest('requires --encoder actual compiled binary')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        fixture_profile = ArchiveFixture(self.base).profile
        image = runtime_fixture.image
        self.profile = runtime.RuntimeProfile(image(self.encoder), image(sys.executable),
            replace(fixture_profile, encoder_sha256=image(self.encoder).sha256), profile_closure())
        root = self.base / 'program'
        scope = custody.ProgramStore.initialize(root, program_id='software-transport', storage_domain_id='test-disk',
                                                 prospective_admission_sha256='a' * 64)
        final, capture, _ = fixture()
        storage = dict(program_id='software-transport', program_scope_sha256=scope,
            implementation_profile_sha256=self.profile.decoder.implementation_profile_sha256,
            archive_staging_bytes=8 * 1024**2, checkpoint_bytes=131072, per_capture_archive_ns=30_000_000_000,
            broker_address_space_bytes=2 * 1024**3, codec_address_space_bytes=2 * 1024**3)
        plan = dict(schema_version='cpu-prefetch-stage17-formal-ring-plan/2', storage=storage,
                    captures=[dict(capture=capture, execution_budget=dict(max_output_bytes=1024**2))])
        family = digest(archive.canonical(plan))
        with custody.ProgramStore(root, scope_sha256=scope, family_id=family,
                limits=executor.custody_limits(storage, time.monotonic_ns() + 60_000_000_000)) as store:
            self.working = store.prepare_family(family)
        self.originals = {}
        for name in capture_names('Q16a', 0):
            role = role_profile('Q16a', name)
            phase = next((p for p in ('warmup', 'measurement') if f'-{p}-' in name), None)
            width = role.row_bytes(capture[phase]['run_id'] if phase else None)
            if width is None: data = b'{"software_control":true}'
            else:
                run = capture[phase]['run_id'].encode()
                prefix = struct.pack('<I', len(run)) + run
                prefix += bytes(-len(prefix) % 8)
                data = (prefix + bytes(width - len(prefix))) * 2
            (self.working / name).write_bytes(data)
            self.originals[name] = data
        final['plan_sha256'] = family
        final['artifacts'] = [dict(file_name=name, size_bytes=len(data), sha256=digest(data))
                              for name, data in self.originals.items()]
        (self.working / 'formal-capture-0-final-checkpoint.json').write_bytes(archive.canonical(final))
        st = self.working.stat()
        self.request = dict(schema_version='cpu-prefetch-stage17-fixed-action-request/6', action_id='Q16a',
            action_inputs=dict(plan=plan), evidence_root_binding=dict(absolute_path=str(self.working),
                device=st.st_dev, inode=st.st_ino, owner_uid=st.st_uid, mode='0700'))
        self.directory_fd = os.open(self.working, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.directory_fd)
        self.request_snapshot = executor.previous.predecessor._pin_generated(
            executor.previous.canonical(self.request), 'SOFTWARE_ARCHIVE_REQUEST')
        self.addCleanup(self.request_snapshot.close)

    def run_worker(self, *, mode='normal', seconds=60, guard=lambda: None):
        context = executor.previous.predecessor._pin_generated(
            executor.previous.canonical(dict(fixture_mode=mode)), 'SOFTWARE_ARCHIVE_CONTEXT')
        self.addCleanup(context.close)
        args = (sys.executable, '-B', '-c', SCRIPT, '--request-fd', str(self.request_snapshot.descriptor),
                '--context-fd', str(context.descriptor), '--output-dir-fd', str(self.directory_fd))
        now = time.monotonic_ns()
        return executor.run_archived_worker(args,
            (self.request_snapshot.descriptor, context.descriptor, self.directory_fd),
            global_deadline_ns=now + seconds * 1_000_000_000,
            monotonic_expiry_ns=now + seconds * 1_000_000_000, authority_guard=guard,
            request=self.request, profile=self.profile, extent=SimpleNamespace(captures=[object()]))

    def test_actual_native_handoff_broker_codec_cleanup_and_receipt(self):
        outcome = self.run_worker()
        self.assertEqual(outcome.returncode, 0)
        self.assertEqual(outcome.stdout, b'ACKNOWLEDGED\n')
        self.assertTrue(outcome.leader_reaped and outcome.process_group_gone)
        self.assertTrue(all(not (self.working / name).exists() for name in self.originals))
        receipt = json.loads((self.working / 'formal-capture-0-archive-custody.json').read_bytes())
        self.assertEqual(receipt['status'], 'ARCHIVED_AND_RELEASED')
        self.assertEqual(len(receipt['artifacts']), 9)

    def test_failed_evidence_is_archived_but_worker_receives_no_continue(self):
        name = next(iter(self.originals))
        (self.working / name).write_bytes(self.originals[name] + b'\xff')
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.run_worker()
        self.assertIn('source discrepancy stops the family', str(caught.exception))
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)
        receipt = json.loads((self.working / 'formal-capture-0-archive-custody.json').read_bytes())
        self.assertEqual(receipt['status'], 'ARCHIVED_FAILED_EVIDENCE')

    def test_hung_worker_deadline_has_actual_reap_proof(self):
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.run_worker(mode='hang', seconds=3)
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)
        self.assertFalse((self.working / 'formal-capture-0-archive-custody.json').exists())

    def test_final_authority_rejection_has_no_created_process(self):
        def expired(): raise executor.FixedActionExecutionError('AUTHORITY_TIME', 'software expiry')
        with self.assertRaises(executor.FixedActionExecutionError) as caught:
            self.run_worker(guard=expired)
        self.assertEqual(caught.exception.category, 'WORKER_START')
        self.assertTrue(caught.exception.cleanup_proof.leader_reaped)
        self.assertTrue(caught.exception.cleanup_proof.process_group_gone)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--encoder', type=Path)
    args, remaining = parser.parse_known_args()
    ArchivedWorkerTests.encoder = args.encoder
    unittest.main(argv=[sys.argv[0], *remaining])
