"""Software-only independent CPFA2331 goldens; no stand data or science claims."""
from __future__ import annotations

import contextlib
import ctypes
import hashlib
import io
import os
from pathlib import Path
import resource
import struct
import sys
import tempfile
import time
import unittest
from dataclasses import replace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage17_formal_archive_v1 as a


def digest(data):
    return hashlib.sha256(data).hexdigest()


@contextlib.contextmanager
def codec_limit():
    original = resource.getrlimit(resource.RLIMIT_AS)
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, original[1]))
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_AS, original)


class ArchiveFixture:
    def __init__(self, directory):
        self.directory = Path(directory)
        library = Path(os.environ.get("STAGE17_TEST_ZSTD_LIBRARY", "/usr/lib64/libzstd.so.1.5.7")).resolve()
        executable = Path(sys.executable).resolve()
        self.profile = a.DecoderProfile(digest(b"synthetic-profile"), digest(b"synthetic-encoder"),
            library, digest(library.read_bytes()), executable, digest(executable.read_bytes()), 22)
        self.limits = a.DecodeLimits(16384, 8 * 1024**2, 8 * 1024**2, 64 * 1024**2,
                                    64 * 1024**2, 1000, 1 << 22, time.monotonic_ns() + 90_000_000_000)
        self.lib = ctypes.CDLL(str(library))
        for name, result, args in (
            ("ZSTD_createCCtx", ctypes.c_void_p, []),
            ("ZSTD_freeCCtx", ctypes.c_size_t, [ctypes.c_void_p]),
            ("ZSTD_CCtx_setParameter", ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]),
            ("ZSTD_compressBound", ctypes.c_size_t, [ctypes.c_size_t]),
            ("ZSTD_compress2", ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]),
            ("ZSTD_isError", ctypes.c_uint, [ctypes.c_size_t]),
        ):
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = result, args

    def compress(self, data, *, checksum=1, content_size=1, window_log=22):
        ctx = self.lib.ZSTD_createCCtx()
        assert ctx
        try:
            for param, value in ((100, 3), (101, window_log), (200, content_size), (201, checksum), (202, 0), (400, 0)):
                assert not self.lib.ZSTD_isError(self.lib.ZSTD_CCtx_setParameter(ctx, param, value))
            bound = self.lib.ZSTD_compressBound(len(data))
            output = ctypes.create_string_buffer(bound)
            size = self.lib.ZSTD_compress2(ctx, output, bound, data, len(data))
            assert not self.lib.ZSTD_isError(size)
            return output.raw[:size]
        finally:
            self.lib.ZSTD_freeCCtx(ctx)

    def header(self, data, layout="u64", *, fallback=None):
        formats = {"producer": "RAW-OBS-U64LE-LP-RUNID-v1", "consumer": "RAW-OBS-U64LE-LP-RUNID-v1",
                   "demand": "Q16A-DEMAND-U64LE-LP-RUNID-v1", "u64": "NODEORDER-U64LE-v1", "bytes": "control/1"}
        role = a.RoleProfile("SYNTHETIC_" + layout.upper(), formats[layout], layout)
        run = "golden-λ" if layout not in ("u64", "bytes") else None
        width = role.row_bytes(run)
        raw = width is not None and fallback is None
        block_size = width * 8192 if raw else a.BYTE_BLOCK
        header = dict(schema_version=a.HEADER_SCHEMA, policy_id=a.POLICY_ID,
            codec_id=a.RAW_CODEC if raw else a.BYTE_CODEC, artifact_id="software-only-artifact",
            artifact_role=role.artifact_role, canonical_format=role.canonical_format,
            run_id=run, phase="measurement", worker=("producer" if layout == "demand" else role.worker()),
            canonical_size_bytes=len(data), canonical_sha256=digest(data), row_bytes=width if raw else None,
            row_count=len(data)//width if raw else None, block_size_bytes=block_size,
            block_count=(len(data)+block_size-1)//block_size, fallback_reason=fallback,
            implementation_profile_sha256=self.profile.implementation_profile_sha256,
            encoder_sha256=self.profile.encoder_sha256, zstd_library_sha256=self.profile.zstd_library_sha256,
            zstd_version="1.5.7", compression_level=3, worker_threads=1, window_log=22,
            checksum_flag=1, content_size_flag=1, dictionary_id_flag=0)
        return header, role

    def encode(self, data, header, *, frame_options=None):
        # Test encoder uses struct row tuples, independently of the packed-array inverse.
        h = a.canonical(header)
        output = bytearray(b"CPFA2331" + struct.pack("<Q", len(h)) + h)
        block_size = header["block_size_bytes"]
        for ordinal, offset in enumerate(range(0, len(data), block_size)):
            block = data[offset:offset+block_size]
            transformed = block
            if header["codec_id"] == a.RAW_CODEC:
                width = header["row_bytes"]
                rows = list(struct.iter_unpack("<" + "Q" * (width // 8), block))
                words = []
                for column in range(width // 8):
                    previous = 0
                    for row in rows:
                        words.append((row[column] - previous) % (1 << 64))
                        previous = row[column]
                transformed = struct.pack("<" + "Q" * len(words), *words)
            frame = self.compress(transformed, **(frame_options or {}))
            output.extend(struct.pack("<4Q", ordinal, offset, len(block), len(frame)))
            output.extend(hashlib.sha256(frame).digest())
            output.extend(frame)
        output.extend(b"CPFAEND1" + struct.pack("<2Q", header["block_count"], len(data)) + hashlib.sha256(data).digest())
        return bytes(output)

    def verify(self, wire, header, role, *, limits=None, sink=None, physical=None):
        path = self.directory / "fixture.cpfa"
        path.write_bytes(wire)
        with codec_limit():
            return a.verify_archive(path, expected_header=header, role=role,
                physical=physical or a.PhysicalBinding(len(wire), digest(wire)), profile=self.profile,
                limits=limits or self.limits, sink=sink)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.f = ArchiveFixture(self.temp.name)

    def test_rows_boundaries_wraps_opaque_all_bytes(self):
        for rows in (0, 1, 8191, 8192, 8193):
            data = b"".join(struct.pack("<Q", ((1 << 64)-1-i if i % 2 else i)) for i in range(rows))
            header, role = self.f.header(data)
            sink = io.BytesIO()
            wire = self.f.encode(data, header)
            result = self.f.verify(wire, header, role, sink=sink)
            self.assertEqual(sink.getvalue(), data)
            self.assertEqual(result.canonical, a.PhysicalBinding(len(data), digest(data)))
            self.assertEqual(wire, self.f.encode(data, header))
        for layout in ("producer", "consumer", "demand"):
            h, r = self.f.header(b"", layout)
            width = h["row_bytes"]
            # Deliberately opaque padding/status values: archive does not assert raw validity.
            data = bytes(range(256)) * width
            h, r = self.f.header(data, layout)
            sink = io.BytesIO()
            self.f.verify(self.f.encode(data, h), h, r, sink=sink)
            self.assertEqual(sink.getvalue(), data)

    def test_bytes_empty_full_partial_and_entire_failed_tail(self):
        for size in (0, 1, a.BYTE_BLOCK, a.BYTE_BLOCK + 13):
            data = (bytes(range(256)) * ((size+255)//256))[:size]
            h, r = self.f.header(data, "bytes")
            sink = io.BytesIO()
            self.f.verify(self.f.encode(data, h), h, r, sink=sink)
            self.assertEqual(data, sink.getvalue())
        data = b"unaligned failed native prefix\x00\xff"
        h, r = self.f.header(data, "producer", fallback="incomplete-row-prefix")
        sink = io.BytesIO()
        self.f.verify(self.f.encode(data, h), h, r, sink=sink)
        self.assertEqual(data, sink.getvalue())

    def test_external_geometry_identity_and_options_mandatory(self):
        data = bytes(16)
        h, r = self.f.header(data)
        wire = self.f.encode(data, h)
        for key, value in (("row_bytes", 16), ("codec_id", "unknown"), ("worker_threads", True),
                           ("run_id", "wrong"), ("phase", "warmup"), ("artifact_id", "wrong"),
                           ("worker", "consumer"), ("canonical_sha256", "0"*64),
                           ("zstd_version", "1.5.6"), ("compression_level", 4), ("window_log", 23)):
            with self.subTest(key=key), self.assertRaises(a.ArchiveError):
                self.f.verify(wire, dict(h, **{key: value}), r)
        for key in a.HEADER_FIELDS:
            mutant = dict(h)
            del mutant[key]
            with self.subTest(missing=key), self.assertRaises(a.ArchiveError):
                self.f.verify(wire, mutant, r)

    def test_missing_reordered_duplicate_truncated_corrupt_frames(self):
        data = bytes(8193 * 8)
        h, r = self.f.header(data)
        wire = self.f.encode(data, h)
        first = 16 + len(a.canonical(h))
        frame_size, = struct.unpack_from("<Q", wire, first+24)
        second = first+64+frame_size
        mutants = [wire[:-1], wire + b"x", wire[:first] + wire[second:],
                   wire[:first] + wire[first:second]*2 + wire[second:]]
        for offset, value in ((first, 1), (second, 0), (first+8, 8), (first+16, a.MAX_U64), (first+24, a.MAX_U64)):
            changed = bytearray(wire)
            struct.pack_into("<Q", changed, offset, value)
            mutants.append(bytes(changed))
        changed = bytearray(wire)
        changed[first+64+5] ^= 1
        mutants.append(bytes(changed))
        for i, mutant in enumerate(mutants):
            with self.subTest(i=i), self.assertRaises(a.ArchiveError):
                self.f.verify(mutant, h, r)

    def test_frame_options_and_concat_rejected_even_rehashed(self):
        data = b"abcdef"*200
        h, r = self.f.header(data, "bytes")
        for options in ({"checksum": 0}, {"content_size": 0}):
            with self.subTest(options=options), self.assertRaises(a.ArchiveError):
                self.f.verify(self.f.encode(data, h, frame_options=options), h, r)
        wire = self.f.encode(data, h)
        at = 16+len(a.canonical(h))
        frame = wire[at+64:-56]
        frame += self.f.compress(b"unexpected")
        mutant = wire[:at] + struct.pack("<4Q", 0, 0, len(data), len(frame)) + hashlib.sha256(frame).digest() + frame + wire[-56:]
        with self.assertRaises(a.ArchiveError):
            self.f.verify(mutant, h, r)

    def test_budgets_deadlines_partial_sink_and_hashes(self):
        data = bytes(8193*8)
        h, r = self.f.header(data)
        wire = self.f.encode(data, h)
        for field, value in (("max_header_bytes", 1), ("max_frame_bytes", 1), ("max_decoded_block_bytes", 1),
                             ("max_archive_bytes", 1), ("max_canonical_bytes", 1), ("max_blocks", 1),
                             ("max_window_bytes", 1024), ("deadline_ns", time.monotonic_ns()-1)):
            with self.subTest(field=field), self.assertRaises(a.ArchiveError):
                self.f.verify(wire, h, r, limits=replace(self.f.limits, **{field: value}))
        with self.assertRaises(a.ArchiveError):
            self.f.verify(wire, h, r, physical=a.PhysicalBinding(len(wire), "0"*64))
        class Partial:
            def write(self, data):
                return len(data)-1
        with self.assertRaisesRegex(a.ArchiveError, "partial decoded"):
            self.f.verify(wire, h, r, sink=Partial())

    def test_header_duplicate_noncanonical_and_oversize(self):
        h, r = self.f.header(b"")
        wire = self.f.encode(b"", h)
        old_len = len(a.canonical(h))
        for head in (a.canonical(h)[:-1]+b',"block_count":0}', b" " + a.canonical(h), b'{"x":NaN}'):
            bad = b"CPFA2331" + struct.pack("<Q", len(head)) + head + wire[16+old_len:]
            with self.assertRaises(a.ArchiveError):
                self.f.verify(bad, h, r)

    def test_actual_zstd_frame_window_expansion_rejected_before_output(self):
        data=bytes(5*1024**2)
        frame=self.f.compress(data,window_log=23)
        with codec_limit():
            decoder=a.ZstdDecoder(self.f.profile,self.f.limits)
            with self.assertRaisesRegex(a.ArchiveError,"window"):
                decoder.decode(frame,len(data))


if __name__ == "__main__":
    unittest.main()
