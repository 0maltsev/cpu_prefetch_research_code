"""Private metadata reads with fresh checks and cached ancestor strings only.

Full ledger replay, canonical parsing and live inventory remain unchanged.
The default factory extends v1; an explicit base retains its inventory method
so another private factory can compose its own physical-accounting adapter.
No filesystem observations, bytes, hashes or semantic state are cached.
"""
from __future__ import annotations

import hashlib
import os
import stat

import stage17_archive_metadata_fast_v1 as previous
import stage17_formal_archive_v1 as archive
from stage17_formal_archive_custody_v1 import CustodyError


def _read_bound(self, path, binding, maximum):
    normalized = os.path.abspath(path)
    parent = os.path.dirname(normalized)
    if parent == normalized:
        ancestors = ()
    else:
        cache = getattr(self, '_metadata_read_ancestor_strings', None)
        if cache is None:
            cache = self._metadata_read_ancestor_strings = {}
        ancestors = cache.get(parent)
        if ancestors is None:
            parents = []
            current = parent
            while True:
                parents.append(current)
                ancestor = os.path.dirname(current)
                if ancestor == current:
                    break
                current = ancestor
            ancestors = cache[parent] = tuple(reversed(parents))
    for ancestor in ancestors:
        # Like Path.is_symlink in the supported runtime, islink performs a
        # fresh os.lstat and preserves its exception-to-False behavior.
        if os.path.islink(ancestor):
            raise archive.ArchiveError('symlink path component')

    descriptor = os.open(normalized, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise archive.ArchiveError('not a regular file')
        stream = os.fdopen(descriptor, 'rb')
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        before = archive.file_stamp(os.fstat(stream.fileno()))
        if before[2] > maximum:
            raise CustodyError('metadata byte bound')
        # Reading maximum+1 can allocate the entire (potentially GiB) ceiling
        # for a tiny record. One byte beyond the observed size detects growth;
        # an unequal length still rejects shrinkage or a short read.
        raw = stream.read(before[2] + 1)
        if len(raw) > maximum or before[2] != len(raw):
            raise CustodyError('metadata read length')
        if binding is not None and archive.PhysicalBinding(len(raw), hashlib.sha256(raw).hexdigest()) != binding:
            raise CustodyError('metadata binding differs')
        if (before != archive.file_stamp(os.fstat(stream.fileno()))
                or before != archive.file_stamp(path.stat(follow_symlinks=False))):
            raise CustodyError('metadata changed during read')
    return raw


def make_store_class(base=None):
    """Return an independent private store, overriding only bounded reads.

    Explicit bases preserve their physical_accounting implementation, including
    another private inventory adapter. No supplied class or globals are mutated.
    """
    if base is None:
        base = previous.make_store_class()
    result = previous.make_store_class(base=base)
    scope = result.__init__.__globals__
    result.physical_accounting = previous._clone(base.physical_accounting, scope)
    result._read_bound = previous._clone(_read_bound, scope)
    result.__name__ = result.__qualname__ = 'MetadataFastProgramStoreV2'
    result.__module__ = __name__
    return result
