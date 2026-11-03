"""Actual credential-bearing process transport; no archival custody claim."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import stage17_archive_channel_v1 as channel
from stage17_formal_checkpoint_v1 import PinnedWorker
from stage17_formal_archive_v1 import canonical


class ArchiveChannelTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.directory_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        self.addCleanup(os.close, self.directory_fd)
        self.checkpoint = self.write("formal-capture-0-final-checkpoint.json", {"plan_sha256": "c" * 64})
        self.request = dict(schema_version=channel.REQUEST_SCHEMA, request_sha256="a" * 64,
            program_scope_sha256="b" * 64, capture_ordinal=0, checkpoint=self.checkpoint,
            deadline_monotonic_ns=self.deadline())

    def write(self, name, value):
        raw = canonical(value)
        (self.root / name).write_bytes(raw)
        return dict(file_name=name, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def start(self, request=None, *, parent_sends=False):
        parent, worker = channel.create_channel()
        self.addCleanup(parent.close)
        self.addCleanup(worker.close)
        script = ("import socket,sys\n"
                  "s=socket.socket(fileno=int(sys.argv[1]))\n"
                  "s.settimeout(10)\n"
                  "raw=sys.argv[2].encode()\n"
                  "if sys.argv[3]=='child':s.send(raw)\n"
                  "print('ready',flush=True)\n"
                  "print(s.recv(8192).decode(),flush=True)\n")
        raw = canonical(request or self.request).decode()
        process = subprocess.Popen([sys.executable, "-B", "-c", script,
            str(worker.fileno()), raw, "parent" if parent_sends else "child"],
            pass_fds=(worker.fileno(),), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None: process.terminate()
            process.communicate(timeout=3)
        self.addCleanup(cleanup)
        self.assertEqual(process.stdout.readline(), b"ready\n")
        pinned = PinnedWorker(process.pid)
        self.addCleanup(pinned.close)
        if parent_sends: worker.send(raw.encode())
        worker.close()
        driver = channel.ArchiveChannel(parent, worker=pinned, directory_fd=self.directory_fd,
            request_sha256="a" * 64, program_scope_sha256="b" * 64, captures=1,
            maximum_checkpoint_bytes=8192, maximum_custody_receipt_bytes=8192,
            maximum_archive_ns=2_000_000_000)
        return driver, process

    @staticmethod
    def deadline():
        return time.monotonic_ns() + 2_000_000_000

    def receipt(self, **changes):
        value = dict(schema_version="cpu-prefetch-stage17-formal-archive-custody/1",
            program_scope_sha256="b" * 64, capture_ordinal=0, plan_sha256="c" * 64,
            checkpoint=self.checkpoint, status="ARCHIVED_AND_RELEASED",
            scientific_validity="NOT_ASSESSED", execution_authority=False)
        value.update(changes)
        return self.write("formal-capture-0-archive-custody.json", value)

    def test_actual_child_credentials_blocked_exchange_and_exact_ack(self):
        driver, process = self.start()
        pending = driver.receive(deadline_ns=self.deadline())
        self.assertEqual(pending.binding, self.checkpoint)
        self.assertEqual(pending.native_process_observation["pid"], process.pid)
        self.assertIsNone(process.poll())
        receipt = self.receipt()
        driver.acknowledge(receipt, deadline_ns=self.deadline())
        stdout, stderr = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, stderr)
        ack = json.loads(stdout)
        self.assertEqual(ack["checkpoint_sha256"], self.checkpoint["sha256"])
        self.assertEqual(ack["custody_receipt"], receipt)
        self.assertEqual(driver.ordinal, 1)
        with self.assertRaises(channel.ArchiveError):
            driver.acknowledge(receipt, deadline_ns=self.deadline())

    def test_actual_wrong_sender_credentials_rejected(self):
        driver, _ = self.start(parent_sends=True)
        with self.assertRaisesRegex(channel.ArchiveError, "credentials"):
            driver.receive(deadline_ns=self.deadline())

    def test_foreign_scope_reordered_capture_and_changed_original_rejected(self):
        for field, value in (("program_scope_sha256", "d" * 64), ("capture_ordinal", 1)):
            request = dict(self.request, **{field: value})
            driver, _ = self.start(request)
            with self.assertRaises(channel.ArchiveError): driver.receive(deadline_ns=self.deadline())
        driver, _ = self.start()
        (self.root / self.checkpoint["file_name"]).write_bytes(b"changed")
        with self.assertRaises(Exception): driver.receive(deadline_ns=self.deadline())

    def test_failed_archive_or_foreign_custody_cannot_acknowledge(self):
        driver, process = self.start()
        driver.receive(deadline_ns=self.deadline())
        for changes in (dict(status="ARCHIVED_FAILED_EVIDENCE"),
                        dict(program_scope_sha256="d" * 64),
                        dict(plan_sha256="d" * 64), dict(execution_authority=True)):
            receipt = self.receipt(**changes)
            with self.assertRaises(channel.ArchiveError):
                driver.acknowledge(receipt, deadline_ns=self.deadline())
            self.assertIsNone(process.poll())
            self.assertEqual(driver.ordinal, 0)

    def test_native_deadline_cannot_be_expired_or_extended(self):
        for deadline in (1, time.monotonic_ns() + 60_000_000_000):
            driver, _ = self.start(dict(self.request, deadline_monotonic_ns=deadline))
            with self.assertRaises(channel.ArchiveError):
                driver.receive(deadline_ns=self.deadline())

    def test_ack_keeps_original_native_deadline(self):
        driver, process = self.start(dict(self.request,
            deadline_monotonic_ns=time.monotonic_ns() + 300_000_000))
        driver.receive(deadline_ns=self.deadline())
        receipt = self.receipt()
        time.sleep(0.31)
        with self.assertRaisesRegex(channel.ArchiveError, "deadline expired"):
            driver.acknowledge(receipt, deadline_ns=self.deadline())
        self.assertEqual(driver.ordinal, 0)
        self.assertIsNone(process.poll())


if __name__ == "__main__":
    unittest.main()
