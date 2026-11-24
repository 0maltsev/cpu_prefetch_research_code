"""Original per-capture checkpoint binding and pinned live-worker observation.

The qualified IPC driver must keep the native worker blocked at its checkpoint
until custody acknowledgement. This module does not manufacture that handshake,
launch a codec, admit science, or authorize another measured capture.
"""
from __future__ import annotations

import os
import pathlib
import select

from stage17_formal_archive_v1 import ArchiveError, canonical, sha, uint
from stage17_output_registry_v11 import capture_names

SCHEMA = "cpu-prefetch-stage17-formal-capture-checkpoint/1"
FIELDS = frozenset(("schema_version action_id plan_sha256 capture_ordinal capture_identity "
                    "native_result_after_cleanup artifacts native_complete scientific_validity "
                    "execution_authority").split())
NATIVE_FIELDS = frozenset(("stop session clock_origin core_mapping monitor_mapping controller_stack "
                           "worker_mappings worker_stacks publication_attempted publication_succeeded").split())


def validate_checkpoint(document, *, action, plan_sha256, capture, sources):
    """Validate original bytes already hashed by the caller; no raw analysis gate."""
    if (type(document) is not dict or set(document) != FIELDS
            or document["schema_version"] != SCHEMA
            or document["action_id"] != action or action not in ("Q16a", "Q16b", "Q16c")
            or document["plan_sha256"] != sha(plan_sha256, "plan hash")
            or type(document["native_complete"]) is not bool
            or document["scientific_validity"] != "NOT_ASSESSED"
            or document["execution_authority"] is not False):
        raise ArchiveError("checkpoint contract or plan/action binding differs")
    ordinal = uint(document["capture_ordinal"], "checkpoint ordinal")
    if ordinal != uint(capture["ordinal"], "prospective ordinal"):
        raise ArchiveError("checkpoint ordinal differs")
    identity = dict(warmup_run_id=capture["warmup"]["run_id"],
                    measurement_run_id=capture["measurement"]["run_id"],
                    hardware_state=capture["hardware_state"])
    if canonical(document["capture_identity"]) != canonical(identity):
        raise ArchiveError("checkpoint phase identity differs")
    references = [dict(file_name=s.expected.file_name, size_bytes=s.expected.size_bytes,
                       sha256=s.expected.sha256) for s in sources]
    if canonical(document["artifacts"]) != canonical(references):
        raise ArchiveError("checkpoint original artifact bindings differ")
    names = [r["file_name"] for r in references]
    expected = capture_names(action, ordinal)
    if len(names) != len(set(names)) or any(name not in expected for name in names):
        raise ArchiveError("checkpoint contains foreign or duplicate capture artifacts")
    # A publication failure may retain only a prefix. It grants no next capture.
    if names != [name for name in expected if name in names]:
        raise ArchiveError("checkpoint publication order differs")
    final = document["native_result_after_cleanup"]
    if type(final) is not dict or set(final) != NATIVE_FIELDS:
        raise ArchiveError("checkpoint final native result shape differs")
    stop = uint(final["stop"], "native stop")
    if stop > 14 or any(type(final[k]) is not bool for k in ("publication_attempted", "publication_succeeded")):
        raise ArchiveError("checkpoint native status is malformed")
    complete = (stop == 14 and final["publication_attempted"]
                and final["publication_succeeded"] and tuple(names) == expected)
    if document["native_complete"] is not complete:
        raise ArchiveError("checkpoint native completion claim differs")
    if complete:
        mappings, stacks = final["worker_mappings"], final["worker_stacks"]
        if type(mappings) is not list or len(mappings) != 3 or type(stacks) is not list or len(stacks) != 2:
            raise ArchiveError("completed checkpoint lacks original worker cleanup")
        for value in [*mappings, *stacks, final["core_mapping"],
                      final["monitor_mapping"], final["controller_stack"]]:
            if type(value) is not dict or value.get("cleanup_attempted") is not True:
                raise ArchiveError("completed checkpoint lacks cleanup observation")
            for field in ("unlock", "unmap"):
                if canonical(value.get(field)) != canonical(dict(return_value=0, error_number=0)):
                    raise ArchiveError("completed checkpoint reports failed memory cleanup")
        for value in [*stacks, final["controller_stack"]]:
            thread = value.get("thread")
            if (type(thread) is not dict or type(thread.get("create")) is not int
                    or thread["create"] != 0 or type(thread.get("join")) is not int
                    or thread["join"] != 0):
                raise ArchiveError("completed checkpoint lacks successful original joins")


def _identity(pid):
    raw = pathlib.Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    fields = raw[raw.rfind(")") + 2:].split()
    if len(fields) < 20:
        raise ArchiveError("worker proc identity is truncated")
    return fields[0], int(fields[19])


class PinnedWorker:
    """A runtime-owned process handle; observe only, never signal or reap.

    The driver creates this after spawning the exact qualified worker and keeps
    its IPC peer open. Observe quiescence only while that peer waits for the
    matching checkpoint acknowledgement; procfs alone cannot prove IPC state.
    """
    def __init__(self, pid):
        if type(pid) is not int or pid <= 0:
            raise ArchiveError("invalid worker PID")
        before = _identity(pid)
        self.pid, self.descriptor = pid, os.pidfd_open(pid, 0)
        self.start_ticks = before[1]
        try:
            # Scheduler state may change while opening the pidfd; start ticks
            # identify the process. The separate liveness check rejects exits.
            if _identity(pid)[1] != self.start_ticks:
                raise ArchiveError("worker identity changed while pinning")
            self._alive()
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None

    def _alive(self):
        if self.descriptor is None:
            raise ArchiveError("worker handle is closed")
        poll = select.poll()
        poll.register(self.descriptor, select.POLLIN)
        if poll.poll(0):
            raise ArchiveError("worker exited or pidfd is invalid")
        state, start = _identity(self.pid)
        if start != self.start_ticks or state in ("Z", "X", "x"):
            raise ArchiveError("worker process identity is not live")

    def observe_quiescence(self):
        self._alive()
        root = pathlib.Path(f"/proc/{self.pid}/task")
        tasks = sorted(int(path.name) for path in root.iterdir())
        if tasks != [self.pid]:
            raise ArchiveError("native worker still has capture/controller threads")
        children = (root / str(self.pid) / "children").read_text(encoding="ascii").split()
        if children:
            raise ArchiveError("native worker still has child processes")
        self._alive()
        if sorted(int(path.name) for path in root.iterdir()) != tasks:
            raise ArchiveError("native task set changed during observation")
        return dict(pid=self.pid, start_ticks=self.start_ticks, task_ids=tasks,
                    child_pids=[], measurement_authority=False)
