"""S180 credential-bearing channel; only qualified custody can receive an ACK.

The parent must verify the broker's ledger and child cleanup before acknowledge.
A negative acknowledgement stops the channel and grants no next capture.
"""
from types import SimpleNamespace
from stage17_archive_channel_v1 import ArchiveChannel as BaseChannel, create_channel
from stage17_formal_archive_v1 import ArchiveError, sha
from stage17_formal_archive_custody_v1 import BoundFile
import stage17_s180_checkpoint_v1 as contract

REQUEST_SCHEMA = "cpu-prefetch-stage17-s180-archive-checkpoint-request/1"
ACK_SCHEMA = "cpu-prefetch-stage17-s180-archive-checkpoint-ack/1"


class ArchiveChannel(BaseChannel):
    request_schema = REQUEST_SCHEMA
    ack_schema = ACK_SCHEMA
    custody_schema = contract.CUSTODY_SCHEMA
    receipt_ordinal_field = "execution_ordinal"

    def __init__(self, *args, session_id, plan_sha256, **kwargs):
        if type(session_id) is not str or not session_id:
            raise ArchiveError("S180 channel session is missing")
        if kwargs.get("captures") != 180 or type(kwargs.get("captures")) is not int:
            raise ArchiveError("S180 channel requires exactly 180 prospective captures")
        self.session_id = session_id
        self.plan_sha256 = sha(plan_sha256, "S180 channel plan")
        self.stopped = False
        super().__init__(*args, **kwargs)

    @staticmethod
    def checkpoint_name(ordinal): return f"s180-e{ordinal}-checkpoint.json"
    @staticmethod
    def custody_name(ordinal): return f"s180-e{ordinal}-archive-custody.json"

    def receive(self, *, deadline_ns):
        if self.stopped:
            raise ArchiveError("S180 channel stopped; retry is not allowed")
        try:
            pending = super().receive(deadline_ns=deadline_ns)
            # Structural validation of sender-declared expected bindings only.
            # The broker separately hashes the actual files and inverse output.
            expected = tuple(SimpleNamespace(expected=BoundFile(**r)) for r in contract.original_references(pending.document))
            contract.validate_checkpoint(pending.document, plan_sha256=self.plan_sha256,
                program_scope_sha256=self.program_scope_sha256, session_id=self.session_id,
                ordinal=pending.ordinal, sources=expected)
            return pending
        except BaseException:
            self.stopped = True
            raise

    def _receipt_status(self, receipt, pending):
        status = receipt.get("status")
        if (set(receipt) != contract.CUSTODY_FIELDS
                or type(receipt.get("execution_ordinal")) is not int
                or status not in ("ARCHIVED_AND_RELEASED", "ARCHIVED_FAILED_EVIDENCE")
                or receipt.get("phase18_authority") is not False
                or type(receipt.get("storage_extension")) is not dict):
            raise ArchiveError("S180 custody/extension receipt is malformed")
        extension = BoundFile(**receipt["storage_extension"])
        extension.binding()
        if extension.file_name != f"s180-extension-{self.plan_sha256}.json":
            raise ArchiveError("S180 custody extension belongs to another family")
        if pending.document["native_complete"] is not True and status == "ARCHIVED_AND_RELEASED":
            raise ArchiveError("failed S180 capture cannot receive a continuation ACK")
        return status

    def acknowledge(self, receipt_binding, *, deadline_ns):
        if self.stopped:
            raise ArchiveError("S180 channel stopped; no acknowledgement is allowed")
        try:
            return super().acknowledge(receipt_binding, deadline_ns=deadline_ns)
        except BaseException:
            self.stopped = True
            raise

    def _after_ack(self, status):
        self.stopped = status != "ARCHIVED_AND_RELEASED"
