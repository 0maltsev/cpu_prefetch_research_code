"""Cold D233 inverse over an authenticated, sealed native image.

The generated image module is an ordinary member of the exact archive source
closure. No image search, mutable library pathname or Python-loop fallback is
allowed. Archive framing, physical/canonical hashes and both readbacks remain
the original independent verifier's responsibility.
"""
from __future__ import annotations

import base64
import ctypes
import fcntl
import hashlib
import os
import re
import time

MAX_IMAGE_BYTES = 1024 * 1024
MAX_BLOCK_BYTES = 4 * 1024 * 1024
_NATIVE = None


class NativeInverse:
    def __init__(self, encoded, size_bytes, sha256):
        if (type(encoded) is not bytes or len(encoded) > (MAX_IMAGE_BYTES * 5 + 3) // 4
                or type(size_bytes) is not int or not 0 < size_bytes <= MAX_IMAGE_BYTES
                or type(sha256) is not str or not re.fullmatch('[0-9a-f]{64}', sha256)):
            raise ValueError('native inverse image binding')
        raw = base64.b85decode(encoded)
        if len(raw) != size_bytes or hashlib.sha256(raw).hexdigest() != sha256 or raw[:4] != b'\x7fELF':
            raise ValueError('native inverse image bytes differ')
        descriptor = os.memfd_create('stage17-cold-archive-inverse-v1', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        try:
            if os.write(descriptor, raw) != len(raw):
                raise ValueError('short native inverse snapshot')
            os.fchmod(descriptor, 0o500)
            seals = fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL
            fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)
            if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) & seals != seals:
                raise ValueError('native inverse snapshot not sealed')
            library = ctypes.CDLL(f'/proc/self/fd/{descriptor}', mode=os.RTLD_LOCAL | os.RTLD_NOW)
            function = library.cpu_prefetch_archive_inverse_v1
            function.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t)
            function.restype = ctypes.c_int
        except BaseException:
            os.close(descriptor)
            raise
        # Keep the sealed descriptor and loaded image alive together. Reusing
        # its fd pathname for another image cannot confuse the dynamic loader.
        self.descriptor, self.library, self.function = descriptor, library, function
        self.image_sha256 = sha256

    def inverse(self, data, row_bytes, *, deadline_ns):
        if (type(data) is not bytes or type(row_bytes) is not int or row_bytes <= 0
                or row_bytes % 8 or row_bytes > MAX_BLOCK_BYTES or len(data) > MAX_BLOCK_BYTES
                or len(data) % row_bytes or len(data) // row_bytes > 8192):
            raise ValueError('native inverse row geometry')
        if time.monotonic_ns() >= deadline_ns:
            raise ValueError('native inverse deadline expired')
        output = ctypes.create_string_buffer(len(data))
        if self.function(data, output, len(data), row_bytes) != 0:
            raise ValueError('native inverse rejected block')
        if time.monotonic_ns() >= deadline_ns:
            raise ValueError('native inverse deadline expired')
        return output.raw


def inverse_columns(data, row_bytes, *, deadline_ns):
    global _NATIVE
    from stage17_formal_archive_v1 import ArchiveError
    try:
        if _NATIVE is None:
            from stage17_archive_inverse_image_v1 import IMAGE_B85, IMAGE_SIZE_BYTES, IMAGE_SHA256
            _NATIVE = NativeInverse(IMAGE_B85, IMAGE_SIZE_BYTES, IMAGE_SHA256)
        return _NATIVE.inverse(data, row_bytes, deadline_ns=deadline_ns)
    except ValueError as error:
        raise ArchiveError(str(error)) from error
