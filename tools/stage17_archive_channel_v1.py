"""Bounded parent side of D233's synchronous native checkpoint channel.

Transport only: the qualified driver must complete the actual broker process,
verify its custody/ledger result and prove its children reaped before calling
acknowledge(). Neither a packet nor a transport receipt establishes custody.
"""
from __future__ import annotations

import array
import os
import select
import socket
import struct
import time
from dataclasses import dataclass

from stage17_formal_archive_v1 import ArchiveError, canonical, parse_json, sha, uint
from stage17_formal_checkpoint_v1 import PinnedWorker
from stage17_output_registry_v11 import _bound_report

REQUEST_SCHEMA = "cpu-prefetch-stage17-archive-checkpoint-request/1"
ACK_SCHEMA = "cpu-prefetch-stage17-archive-checkpoint-ack/1"
PACKET_LIMIT = 8192


def create_channel():
    parent, worker = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET)
    try:
        parent.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        parent.setblocking(False)
        parent.set_inheritable(False)
        worker.set_inheritable(False)
        return parent, worker
    except BaseException:
        parent.close()
        worker.close()
        raise


def _wait(channel, event, deadline_ns):
    uint(deadline_ns, "channel deadline", positive=True)
    remaining = deadline_ns - time.monotonic_ns()
    if remaining <= 0:
        raise ArchiveError("archive channel deadline expired")
    poll = select.poll()
    poll.register(channel, event)
    ready = poll.poll(min((remaining + 999_999) // 1_000_000, (1 << 31) - 1))
    if (len(ready) != 1 or ready[0][0] != channel.fileno() or not ready[0][1] & event
            or ready[0][1] & (select.POLLERR | select.POLLHUP | select.POLLNVAL)
            or time.monotonic_ns() >= deadline_ns):
        raise ArchiveError("archive channel exited, timed out or became inaccessible")


@dataclass(frozen=True)
class PendingCheckpoint:
    ordinal: int
    binding: dict
    document: dict
    native_process_observation: dict
    deadline_ns: int


class ArchiveChannel:
    def __init__(self, channel, *, worker: PinnedWorker, directory_fd,
                 request_sha256, program_scope_sha256, captures,
                 maximum_checkpoint_bytes, maximum_custody_receipt_bytes,
                 maximum_archive_ns):
        self.channel, self.worker, self.directory_fd = channel, worker, directory_fd
        self.request_sha256 = sha(request_sha256, "request hash")
        self.program_scope_sha256 = sha(program_scope_sha256, "program scope")
        self.captures = uint(captures, "capture count", positive=True)
        self.maximum_checkpoint_bytes = uint(maximum_checkpoint_bytes, "checkpoint limit", positive=True)
        self.maximum_custody_receipt_bytes = uint(maximum_custody_receipt_bytes, "custody receipt limit", positive=True)
        self.maximum_archive_ns = uint(maximum_archive_ns, "archive interval", positive=True)
        self.ordinal, self.pending = 0, None
        before = os.fstat(directory_fd)
        self.directory_identity = before.st_dev, before.st_ino
        if (channel.family != socket.AF_UNIX
                or channel.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) != socket.SOCK_SEQPACKET
                or channel.getsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED) != 1):
            raise ArchiveError("native checkpoint requires local credential-bearing seqpacket channel")

    def _root(self):
        current = os.fstat(self.directory_fd)
        if (current.st_dev, current.st_ino) != self.directory_identity:
            raise ArchiveError("checkpoint output directory identity changed")

    def receive(self, *, deadline_ns):
        if self.pending is not None or self.ordinal >= self.captures:
            raise ArchiveError("checkpoint already pending or prospective family exhausted")
        self._root()
        _wait(self.channel, select.POLLIN, deadline_ns)
        raw, controls, flags, _ = self.channel.recvmsg(
            PACKET_LIMIT, socket.CMSG_SPACE(256), socket.MSG_CMSG_CLOEXEC)
        credentials = []
        unexpected = False
        for level, kind, data in controls:
            if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS and len(data) == 12:
                credentials.append(struct.unpack("3i", data))
            else:
                unexpected = True
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    descriptors = array.array("i")
                    descriptors.frombytes(data[:len(data) // descriptors.itemsize * descriptors.itemsize])
                    for descriptor in descriptors:
                        os.close(descriptor)
        if (not raw or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or unexpected
                or credentials != [(self.worker.pid, os.geteuid(), os.getegid())]):
            raise ArchiveError("checkpoint packet lacks exact worker credentials or carries unexpected data")
        message = parse_json(raw)
        if (set(message) != {"schema_version", "request_sha256", "program_scope_sha256",
                             "capture_ordinal", "checkpoint", "deadline_monotonic_ns"}
                or message["schema_version"] != REQUEST_SCHEMA
                or message["request_sha256"] != self.request_sha256
                or message["program_scope_sha256"] != self.program_scope_sha256
                or type(message["capture_ordinal"]) is not int
                or message["capture_ordinal"] != self.ordinal):
            raise ArchiveError("checkpoint request scope/order differs")
        cold_deadline = uint(message["deadline_monotonic_ns"], "native cold deadline", positive=True)
        now = time.monotonic_ns()
        if not now < cold_deadline <= min(deadline_ns, now + self.maximum_archive_ns):
            raise ArchiveError("native cold deadline expired or exceeds the admitted interval")
        binding = message["checkpoint"]
        if (type(binding) is not dict or set(binding) != {"file_name", "size_bytes", "sha256"}
                or binding["file_name"] != f"formal-capture-{self.ordinal}-final-checkpoint.json"):
            raise ArchiveError("checkpoint original receipt name differs")
        sha(binding["sha256"], "checkpoint hash")
        uint(binding["size_bytes"], "checkpoint size", positive=True)
        document = _bound_report(self.directory_fd, binding, self.maximum_checkpoint_bytes)
        observation = self.worker.observe_quiescence()
        if time.monotonic_ns() >= cold_deadline:
            raise ArchiveError("checkpoint receive exceeded deadline")
        self.pending = PendingCheckpoint(self.ordinal, dict(binding), document, observation, cold_deadline)
        return self.pending

    def acknowledge(self, receipt_binding, *, deadline_ns):
        """Only after qualified broker/ledger validation and actual child cleanup.

        Recheck the durable exact receipt here to prevent stale or foreign ACKs.
        Failure-evidence archival cannot authorize continuation.
        """
        pending = self.pending
        if pending is None:
            raise ArchiveError("no checkpoint is awaiting acknowledgement")
        deadline_ns = min(deadline_ns, pending.deadline_ns)
        if time.monotonic_ns() >= deadline_ns:
            raise ArchiveError("original archive deadline expired before acknowledgement")
        if (type(receipt_binding) is not dict
                or set(receipt_binding) != {"file_name", "size_bytes", "sha256"}
                or receipt_binding["file_name"] != f"formal-capture-{pending.ordinal}-archive-custody.json"):
            raise ArchiveError("custody receipt binding differs")
        sha(receipt_binding["sha256"], "custody hash")
        uint(receipt_binding["size_bytes"], "custody size", positive=True)
        self._root()
        receipt = _bound_report(self.directory_fd, receipt_binding, self.maximum_custody_receipt_bytes)
        if (receipt.get("schema_version") != "cpu-prefetch-stage17-formal-archive-custody/1"
                or receipt.get("program_scope_sha256") != self.program_scope_sha256
                or receipt.get("capture_ordinal") != pending.ordinal
                or receipt.get("plan_sha256") != pending.document.get("plan_sha256")
                or canonical(receipt.get("checkpoint")) != canonical(pending.binding)
                or receipt.get("status") != "ARCHIVED_AND_RELEASED"
                or receipt.get("scientific_validity") != "NOT_ASSESSED"
                or receipt.get("execution_authority") is not False):
            raise ArchiveError("custody receipt is incomplete, failed or belongs to another checkpoint")
        self.worker.observe_quiescence()
        packet = canonical(dict(schema_version=ACK_SCHEMA, request_sha256=self.request_sha256,
            program_scope_sha256=self.program_scope_sha256, capture_ordinal=pending.ordinal,
            checkpoint_sha256=pending.binding["sha256"], status="ARCHIVED_AND_RELEASED",
            custody_receipt=receipt_binding))
        if len(packet) > PACKET_LIMIT:
            raise ArchiveError("archive acknowledgement exceeds packet bound")
        _wait(self.channel, select.POLLOUT, deadline_ns)
        if self.channel.send(packet, socket.MSG_NOSIGNAL) != len(packet):
            raise ArchiveError("archive acknowledgement was not sent atomically")
        self.ordinal += 1
        self.pending = None
