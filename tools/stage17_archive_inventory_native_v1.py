"""Authenticated cold inventory; no cached usage or experimental authority.

The native helper freshly stats every object selected by the original custody
inventory. The caller retains the original root/lock/directory checks. A failed
native invocation never falls back to a weaker or stale usage observation.
"""
from __future__ import annotations

import base64
import ctypes
import fcntl
import hashlib
import os
import re
import time

import stage17_formal_archive_custody_v1 as custody

MAX_IMAGE_BYTES = 1024 * 1024
_NATIVE = None


class Usage(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('logical_size_bytes', 'allocated_bytes', 'quota_bytes', 'unique_objects')]


class NativeInventory:
    def __init__(self, encoded, size_bytes, sha256):
        if (type(encoded) is not bytes or len(encoded) > (MAX_IMAGE_BYTES * 5 + 3) // 4
                or type(size_bytes) is not int or not 0 < size_bytes <= MAX_IMAGE_BYTES
                or type(sha256) is not str or not re.fullmatch('[0-9a-f]{64}', sha256)):
            raise ValueError('inventory image binding')
        raw = base64.b85decode(encoded)
        if len(raw) != size_bytes or hashlib.sha256(raw).hexdigest() != sha256 or raw[:4] != b'\x7fELF':
            raise ValueError('inventory image bytes differ')
        descriptor = os.memfd_create('stage17-cold-inventory-v1', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        try:
            if os.write(descriptor, raw) != len(raw):
                raise ValueError('short inventory snapshot')
            os.fchmod(descriptor, 0o500)
            seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
            fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
            if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) & seals != seals:
                raise ValueError('inventory snapshot not sealed')
            library = ctypes.CDLL(f'/proc/self/fd/{descriptor}', mode=os.RTLD_LOCAL | os.RTLD_NOW)
            function = library.cpu_prefetch_archive_inventory_v1
            function.argtypes = (ctypes.c_char_p, ctypes.c_uint64, ctypes.POINTER(ctypes.c_char_p),
                                 ctypes.c_uint64, ctypes.c_uint64, ctypes.POINTER(Usage))
            function.restype = ctypes.c_int
        except BaseException:
            os.close(descriptor)
            raise
        self.descriptor, self.library, self.function = descriptor, library, function
        self.image_sha256 = sha256

    def scan(self, root, *, max_inventory_files, retained_relative_paths, deadline_ns):
        path = os.fsencode(os.path.abspath(root))
        if b'\0' in path:
            raise ValueError('inventory path contains NUL')
        for value in (max_inventory_files, deadline_ns):
            if type(value) is not int or not 0 < value < 1 << 64:
                raise ValueError('inventory finite input bound')
        if time.monotonic_ns() >= deadline_ns:
            raise ValueError('inventory deadline expired')
        retained = []
        for name in retained_relative_paths:
            if type(name) is not str or '\0' in name:
                raise ValueError('inventory retained name')
            parts = name.split('/')
            if (len(parts) != 3 or parts[0] != 'working'
                    or re.fullmatch('[0-9a-f]{64}', parts[1]) is None
                    or not parts[2] or parts[2] in ('.', '..')):
                raise ValueError('inventory retained path')
            retained.append(os.fsencode(name))
        values = (ctypes.c_char_p * len(retained))(*retained)
        result = Usage()
        status = self.function(path, max_inventory_files, values, len(retained), deadline_ns,
                               ctypes.byref(result))
        if status != 0:
            raise ValueError('native inventory rejected current filesystem: status ' + str(status))
        if time.monotonic_ns() >= deadline_ns:
            raise ValueError('inventory deadline expired')
        return custody.PhysicalUsage(*(getattr(result, name) for name, _ in Usage._fields_))


def _physical_accounting(self):
    global _NATIVE
    self._check()
    retained = []
    for family, name in getattr(self, '_retained_receipts', set()):
        custody.archive.sha(family, 'retained family')
        retained.append('working/' + family + '/' + custody._name(name))
    try:
        if _NATIVE is None:
            from stage17_archive_inventory_image_v1 import IMAGE_B85, IMAGE_SIZE_BYTES, IMAGE_SHA256
            _NATIVE = NativeInventory(IMAGE_B85, IMAGE_SIZE_BYTES, IMAGE_SHA256)
        result = _NATIVE.scan(self.root, max_inventory_files=self.limits.max_inventory_files,
                              retained_relative_paths=retained, deadline_ns=self.limits.deadline_ns)
    except (ValueError, OSError) as error:
        raise custody.CustodyError(str(error)) from error
    self._check()
    return result


def make_store_class(base=custody.ProgramStore):
    from stage17_archive_metadata_fast_v2 import make_store_class as metadata_store
    parent = metadata_store(base=base)
    return type('NativeInventoryProgramStore', (parent,), {
        '__module__': __name__, 'physical_accounting': _physical_accounting})
