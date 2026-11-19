"""D288 charge the guard's ancillary receipts to the existing archive quota.

No new ledger kind or native artifact format. The final or failed-family receipt bundle is
published as one flat, content-addressed metadata file, which D233's unchanged
physical_accounting counts. The external root is bounded temporary workspace.
"""
import hashlib
import json
import os
from pathlib import Path

import stage17_locked_compaction_guard_v1 as controls
import stage17_q16c_compaction_integration_v1 as previous
import stage17_formal_archive_v1 as archive


def bounded(path, maximum):
    with archive.open_regular(path) as stream:
        before = archive.file_stamp(os.fstat(stream.fileno()))
        previous.require(before[2] <= maximum, 'platform metadata byte bound')
        raw = stream.read(before[2] + 1)
        previous.require(len(raw) == before[2]
                         and before == archive.file_stamp(os.fstat(stream.fileno()))
                         == archive.file_stamp(path.stat(follow_symlinks=False)), 'platform metadata changed')
    return raw


class Observations(previous.Observations):
    def __init__(self, *args, program_root, program_scope_sha256, **kwargs):
        previous.require(type(kwargs.get('capture_count')) is int and kwargs['capture_count'] == 94,
                         'D288 metadata budget is for exactly94 captures')
        self.program = Path(program_root)
        previous.require(self.program.is_absolute() and not any(
            p.is_symlink() for p in (self.program, *self.program.parents)), 'canonical program root')
        scope = bounded(self.program / 'scope.json', 131072)
        previous.require(len(scope) <= 131072 and hashlib.sha256(scope).hexdigest() == program_scope_sha256,
                         'actual scoped archive program required')
        document = json.loads(scope)
        previous.require(document['policy_id'] == 'EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1'
                         and document['future_formal_only'] is True, 'D233 future-program metadata only')
        previous.require((self.program / 'metadata').is_dir()
                         and not (self.program / 'metadata').is_symlink(), 'actual program metadata directory')
        self.metadata_bytes = 0
        self.metadata_bindings = []
        self.scope_sha256 = program_scope_sha256
        self.records = []
        self.failed = False
        self.publication_failure = None
        super().__init__(*args, **kwargs)

    def observe(self, ordinal, moment, checkpoint=None):
        previous.require(len(self.records)<2*self.count and self.metadata_bytes+8192<=2*1024**2,
                         'aggregate platform workspace allowance exceeded before publication')
        failure = None
        try:
            super().observe(ordinal, moment, checkpoint)
        except Exception as error:
            failure = error
        path = self.root / ('capture-' + str(ordinal) + '-' + moment + '.json')
        if path.is_file() and not path.is_symlink():
            raw = bounded(path, 8192)
            previous.require(self.metadata_bytes + len(raw) <= 2 * 1024**2,
                             'aggregate platform workspace allowance exceeded')
            self.metadata_bytes += len(raw)
            self.records.append(json.loads(raw))
        elif failure is None:
            raise RuntimeError('successful platform observation lacks its receipt')
        if failure is not None:
            self.failed = True
            raise failure

    def ready(self):
        return bool(self.records) and not self.metadata_bindings and (self.failed or self.next_ordinal == self.count)

    def flush(self, store):
        """Use the already-held original custody transaction, exactly once.

        Individual receipts are bounded working evidence until the final or
        failed capture. One authoritative bundle is retained through D233's
        own before-write quota/reserve checks. No extra full ledger replay.
        """
        if self.metadata_bindings or not self.records:
            return
        previous.require(store.root == self.program and store.scope_sha256 == self.scope_sha256
                         and store.family_id == self.plan_sha256, 'actual held family store required')
        document = dict(schema_version='cpu-prefetch-q16c-platform-observations/1',
            request_sha256=self.request_sha256,plan_sha256=self.plan_sha256,
            observation_count=len(self.records),observations=self.records,
            scientific_validity='NOT_ASSESSED',execution_authority=False)
        raw = controls.canonical(document)
        previous.require(len(raw) <= 2*1024**2,'platform metadata bundle allowance exceeded')
        digest = hashlib.sha256(raw).hexdigest()
        name = 'q16c-platform-' + digest + '.json'
        binding = store.retain_metadata(name,raw)
        self.metadata_bindings.append(dict(path=str(store.root/'metadata'/name),
            size_bytes=binding.size_bytes,sha256=binding.sha256))


def retaining_store_class(base,observations):
    """Add a bounded final/failure publication to existing exclusive stores."""
    class RetainingStore(base):
        def __enter__(self):
            super().__enter__()
            try:
                if observations.ready():observations.flush(self)
                return self
            except BaseException:
                super().__exit__(None,None,None)
                raise

        def __exit__(self,kind,error,traceback):
            try:
                if kind is not None and observations.records and not observations.metadata_bindings:
                    observations.failed=True
                    try:observations.flush(self)
                    except Exception as failure:
                        # Keep the primary native/resource failure and all
                        # durable working receipts if quota/deadline prevents
                        # authoritative metadata publication.
                        observations.publication_failure=repr(failure)
            finally:
                result=super().__exit__(kind,error,traceback)
            return result
    return RetainingStore
