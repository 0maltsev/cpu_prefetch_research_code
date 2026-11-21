"""Actual S180 sender credentials and bounded stop/continuation transport."""
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_s180_archive_channel_v1 as channel
import stage17_s180_checkpoint_v1 as contract
from stage17_formal_checkpoint_v1 import PinnedWorker
from stage17_formal_archive_v1 import canonical
from test_stage17_s180_checkpoint_v1 import fixture


class S180ChannelTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.directory_fd)
        self.document, _ = fixture()
        self.checkpoint = self.write("s180-e0-checkpoint.json", self.document)

    def write(self, name, value):
        raw = canonical(value)
        (self.root / name).write_bytes(raw)
        return dict(file_name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    @staticmethod
    def deadline():
        return time.monotonic_ns() + 3_000_000_000

    def start(self, *, changes=None, parent_sends=False):
        parent, child = channel.create_channel()
        self.addCleanup(parent.close)
        self.addCleanup(child.close)
        request = dict(schema_version=channel.REQUEST_SCHEMA, request_sha256="a"*64,
            program_scope_sha256="c"*64, capture_ordinal=0, checkpoint=self.checkpoint,
            deadline_monotonic_ns=self.deadline())
        request.update(changes or {})
        script = ("import socket,sys\n"
            "s=socket.socket(fileno=int(sys.argv[1]));s.settimeout(10)\n"
            "if sys.argv[3]=='child':s.send(sys.argv[2].encode())\n"
            "print('ready',flush=True)\n"
            "print(s.recv(8192).decode(),flush=True)\n")
        raw = canonical(request).decode()
        process = subprocess.Popen([sys.executable, "-B", "-c", script,
            str(child.fileno()), raw, "parent" if parent_sends else "child"],
            pass_fds=(child.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None: process.terminate()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        self.assertEqual(process.stdout.readline(), b"ready\n")
        worker = PinnedWorker(process.pid)
        self.addCleanup(worker.close)
        if parent_sends: child.send(raw.encode())
        child.close()
        driver = channel.ArchiveChannel(parent, worker=worker, directory_fd=self.directory_fd,
            request_sha256="a"*64, program_scope_sha256="c"*64, captures=180,
            maximum_checkpoint_bytes=131072, maximum_custody_receipt_bytes=131072,
            maximum_archive_ns=3_000_000_000, session_id="software-only-s180", plan_sha256="b"*64)
        return driver, process

    def receipt(self, **changes):
        # Transport fixture only. The real broker/ledger integration is separate.
        document = dict(schema_version=contract.CUSTODY_SCHEMA, program_scope_sha256="c"*64,
            plan_sha256="b"*64, execution_ordinal=0, checkpoint=self.checkpoint, ledger_tip={}, artifacts=[],
            status="ARCHIVED_AND_RELEASED", storage_extension=dict(
                file_name="s180-extension-"+"b"*64+".json", size_bytes=1, sha256="d"*64),
            scientific_validity="NOT_ASSESSED", execution_authority=False, phase18_authority=False)
        document.update(changes)
        return self.write("s180-e0-archive-custody.json", document)

    def test_actual_child_exchange_exact_original_checkpoint_and_ack(self):
        driver, process = self.start()
        pending = driver.receive(deadline_ns=self.deadline())
        self.assertEqual(pending.document, self.document)
        self.assertEqual(pending.native_process_observation["pid"], process.pid)
        receipt = self.receipt()
        driver.acknowledge(receipt, deadline_ns=self.deadline())
        stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)["schema_version"], channel.ACK_SCHEMA)
        self.assertEqual(driver.ordinal, 1)
        self.assertFalse(driver.stopped)
        with self.assertRaises(channel.ArchiveError): driver.acknowledge(receipt, deadline_ns=self.deadline())
        self.assertTrue(driver.stopped)

    def test_failed_evidence_negative_ack_releases_parked_child_and_latches_stop(self):
        self.document["native_complete"] = False
        self.document["native_result_after_private_cleanup"]["stop"] = 12
        self.checkpoint = self.write("s180-e0-checkpoint.json", self.document)
        driver, process = self.start()
        driver.receive(deadline_ns=self.deadline())
        driver.acknowledge(self.receipt(status="ARCHIVED_FAILED_EVIDENCE"), deadline_ns=self.deadline())
        stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)["status"], "ARCHIVED_FAILED_EVIDENCE")
        self.assertTrue(driver.stopped)
        with self.assertRaises(channel.ArchiveError): driver.receive(deadline_ns=self.deadline())

    def test_wrong_credentials_schema_scope_or_order_stop_on_first_error(self):
        for changes, parent in (({}, True), ({"schema_version":"cpu-prefetch-stage17-archive-checkpoint-request/1"}, False),
                ({"program_scope_sha256":"f"*64}, False), ({"capture_ordinal":1}, False)):
            driver, _ = self.start(changes=changes, parent_sends=parent)
            with self.assertRaises(channel.ArchiveError): driver.receive(deadline_ns=self.deadline())
            self.assertTrue(driver.stopped)

    def test_invalid_or_foreign_custody_stops_without_ack(self):
        for changes in (dict(phase18_authority=True), dict(execution_ordinal=False), dict(unexpected=True),
                dict(storage_extension=dict(file_name="s180-extension-"+"e"*64+".json", size_bytes=1, sha256="d"*64)),
                dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1")):
            driver, process = self.start()
            driver.receive(deadline_ns=self.deadline())
            with self.assertRaises(channel.ArchiveError):
                driver.acknowledge(self.receipt(**changes), deadline_ns=self.deadline())
            self.assertTrue(driver.stopped)
            self.assertIsNone(process.poll())

    def test_failed_native_cannot_receive_success_ack_and_session_drift_rejects(self):
        self.document["native_complete"] = False
        self.document["native_result_after_private_cleanup"]["stop"] = 12
        self.checkpoint = self.write("s180-e0-checkpoint.json", self.document)
        driver, _ = self.start()
        driver.receive(deadline_ns=self.deadline())
        with self.assertRaises(channel.ArchiveError): driver.acknowledge(self.receipt(), deadline_ns=self.deadline())
        self.document["session_id"] = "foreign-session"
        self.checkpoint = self.write("s180-e0-checkpoint.json", self.document)
        driver, _ = self.start()
        with self.assertRaises(channel.ArchiveError): driver.receive(deadline_ns=self.deadline())


if __name__ == "__main__": unittest.main()
