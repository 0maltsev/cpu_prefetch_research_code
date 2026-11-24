#!/usr/bin/env python3
"""D233 independent, bounded CPFA2331 readback. No execution authority.

Canonical bytes are opaque: this verifies lossless custody, never scientific
validity. Limits and implementation identities are mandatory caller inputs.
An optional sink is provisional until the entire returned proof exists.
"""
from __future__ import annotations

import array
import ctypes
import fcntl
import hashlib
import json
import os
import pathlib
import re
import resource
import stat
import struct
import sys
import time
from dataclasses import dataclass
from typing import BinaryIO

from check_canonical import canonicalize
from stage17_raw_stream_decoder_v1 import row_layout

POLICY_ID = "EXT007-FORMAL-LOSSLESS-STAND-PRIMARY-v1"
HEADER_SCHEMA = "cpu-prefetch-formal-archive-header/1"
RAW_CODEC = "RAW-U64LE-COLUMN-MODDELTA8192-ZSTD157-L3-v1"
BYTE_CODEC = "BYTES-4MIB-ZSTD157-L3-v1"
MAX_U64 = (1 << 64) - 1
BYTE_BLOCK = 4 * 1024 * 1024
ROWS_PER_BLOCK = 8192
HEADER_FIELDS = frozenset((
    "schema_version policy_id codec_id artifact_id artifact_role canonical_format "
    "run_id phase worker canonical_size_bytes canonical_sha256 row_bytes row_count "
    "block_size_bytes block_count fallback_reason implementation_profile_sha256 "
    "encoder_sha256 zstd_library_sha256 zstd_version compression_level "
    "worker_threads window_log checksum_flag content_size_flag dictionary_id_flag"
).split())


class ArchiveError(ValueError):
    pass


def canonical(value: object) -> bytes:
    return canonicalize(value).encode("utf-8", errors="strict")


def uint(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or not (int(positive) <= value <= MAX_U64):
        raise ArchiveError(f"{label}: invalid uint64")
    return value


def checked_sum(*values: int) -> int:
    result = sum(uint(v, "sum operand") for v in values)
    return uint(result, "sum overflow")


def checked_product(a: int, b: int) -> int:
    return uint(uint(a, "product operand") * uint(b, "product operand"), "product overflow")


def sha(value: object, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ArchiveError(f"{label}: invalid SHA256")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ArchiveError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data: bytes) -> dict:
    def nonfinite(_):
        raise ArchiveError("nonfinite JSON")
    try:
        value = json.loads(data.decode("utf-8", errors="strict"),
                           object_pairs_hook=_pairs, parse_constant=nonfinite)
        if not isinstance(value, dict) or canonical(value) != data:
            raise ArchiveError("JSON is not exact JCS-I64-v1 object bytes")
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise ArchiveError("invalid JSON") from exc


def file_stamp(st: os.stat_result) -> tuple:
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)


def open_regular(path: pathlib.Path) -> BinaryIO:
    # Resolve ancestors explicitly; no symlink traversal even in an ancestor.
    path = pathlib.Path(os.path.abspath(path))
    for parent in reversed(path.parents):
        if parent.is_symlink():
            raise ArchiveError("symlink path component")
    fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):
        os.close(fd)
        raise ArchiveError("not a regular file")
    return os.fdopen(fd, "rb")


@dataclass(frozen=True)
class PhysicalBinding:
    size_bytes: int
    sha256: str

    def validate(self):
        uint(self.size_bytes, "physical size")
        sha(self.sha256, "physical hash")


def hash_file(path: pathlib.Path, *, max_bytes: int, deadline_ns: int) -> PhysicalBinding:
    uint(max_bytes, "hash size limit")
    uint(deadline_ns, "hash deadline", positive=True)
    digest, count = hashlib.sha256(), 0
    with open_regular(path) as stream:
        before = file_stamp(os.fstat(stream.fileno()))
        if before[2] > max_bytes:
            raise ArchiveError("hash input exceeds byte limit")
        while True:
            if time.monotonic_ns() >= deadline_ns:
                raise ArchiveError("hash deadline expired")
            block = stream.read(min(1024 * 1024, max_bytes - count + 1))
            if not block:
                break
            count = checked_sum(count, len(block))
            if count > max_bytes:
                raise ArchiveError("hash input exceeds byte limit")
            digest.update(block)
        if (before != file_stamp(os.fstat(stream.fileno()))
                or before != file_stamp(os.stat(path, follow_symlinks=False))):
            raise ArchiveError("hash source identity changed")
    if time.monotonic_ns() >= deadline_ns:
        raise ArchiveError("hash deadline expired")
    return PhysicalBinding(count, digest.hexdigest())


@dataclass(frozen=True)
class RoleProfile:
    artifact_role: str
    canonical_format: str
    layout: str  # producer, consumer, demand, u64, bytes; admitted externally

    def row_bytes(self, run_id: str | None) -> int | None:
        if not self.artifact_role or not self.canonical_format:
            raise ArchiveError("empty role profile")
        if self.layout == "bytes":
            return None
        if self.layout == "u64":
            if self.canonical_format not in ("NODEORDER-U64LE-v1", "SCHEDULE-DEADLINES-U64LE-v1", "SCHEDULE-ABS-U64BE-v1"):
                raise ArchiveError("unsupported u64 role format")
            return 8
        if not isinstance(run_id, str):
            raise ArchiveError("raw format requires run identity")
        try:
            prefix, producer, consumer, _ = row_layout(run_id)
        except (RuntimeError, UnicodeError) as exc:
            raise ArchiveError("invalid run identity") from exc
        if self.canonical_format == "RAW-OBS-U64LE-LP-RUNID-v1":
            if self.layout == "producer":
                return producer
            if self.layout == "consumer":
                return consumer
        if (self.canonical_format == "Q16A-DEMAND-U64LE-LP-RUNID-v1"
                and self.layout == "demand"):
            return prefix + 72
        raise ArchiveError("unsupported canonical row geometry")

    def worker(self) -> str | None:
        return self.layout if self.layout in ("producer", "consumer") else None


@dataclass(frozen=True)
class DecoderProfile:
    implementation_profile_sha256: str
    encoder_sha256: str
    zstd_library_path: pathlib.Path
    zstd_library_sha256: str
    decoder_executable_path: pathlib.Path
    decoder_executable_sha256: str
    window_log: int


@dataclass(frozen=True)
class DecodeLimits:
    max_header_bytes: int
    max_frame_bytes: int
    max_decoded_block_bytes: int
    max_archive_bytes: int
    max_canonical_bytes: int
    max_blocks: int
    max_window_bytes: int
    deadline_ns: int

    def validate(self):
        for key, value in vars(self).items():
            uint(value, key, positive=key not in ("max_canonical_bytes", "max_blocks"))
        self.check_time()

    def check_time(self):
        if time.monotonic_ns() >= self.deadline_ns:
            raise ArchiveError("archive deadline expired")


def validate_header(header: dict, role: RoleProfile, profile: DecoderProfile,
                    limits: DecodeLimits) -> None:
    limits.validate()
    if set(header) != HEADER_FIELDS:
        raise ArchiveError("archive header field set")
    fixed = dict(schema_version=HEADER_SCHEMA, policy_id=POLICY_ID,
                 artifact_role=role.artifact_role, canonical_format=role.canonical_format,
                 implementation_profile_sha256=profile.implementation_profile_sha256,
                 encoder_sha256=profile.encoder_sha256, zstd_library_sha256=profile.zstd_library_sha256,
                 zstd_version="1.5.7", compression_level=3, worker_threads=1,
                 window_log=profile.window_log, checksum_flag=1, content_size_flag=1,
                 dictionary_id_flag=0)
    if header["worker"] not in (None, "producer", "consumer"):
        raise ArchiveError("invalid worker")
    if ((role.layout in ("producer", "consumer") and header["worker"] != role.worker())
            or (role.layout == "demand" and header["worker"] is None)
            or (role.layout in ("u64", "bytes") and header["worker"] is not None)):
        raise ArchiveError("worker/role geometry differs")
    for key, value in fixed.items():
        if type(header[key]) is not type(value) or header[key] != value:
            raise ArchiveError(f"archive profile mismatch: {key}")
    for key in ("canonical_sha256", "implementation_profile_sha256", "encoder_sha256", "zstd_library_sha256"):
        sha(header[key], key)
    if not isinstance(header["artifact_id"], str) or not header["artifact_id"]:
        raise ArchiveError("invalid artifact identity")
    if (header["run_id"] is not None and (not isinstance(header["run_id"], str) or not header["run_id"])):
        raise ArchiveError("invalid run identity")
    if header["phase"] not in (None, "warmup", "measurement"):
        raise ArchiveError("invalid phase")
    if type(profile.window_log) is not int or not 10 <= profile.window_log <= 31:
        raise ArchiveError("unsupported explicit window log")
    if 1 << profile.window_log > limits.max_window_bytes:
        raise ArchiveError("profile window exceeds decoder limit")
    size = uint(header["canonical_size_bytes"], "canonical size")
    if size > limits.max_canonical_bytes:
        raise ArchiveError("canonical size exceeds limit")
    width = role.row_bytes(header["run_id"])
    if header["codec_id"] == RAW_CODEC:
        if (width is None or type(header["row_bytes"]) is not int or header["row_bytes"] != width
                or uint(header["row_count"], "row count") * width != size
                or header["fallback_reason"] is not None):
            raise ArchiveError("raw row geometry/fallback mismatch")
        block_size = checked_product(ROWS_PER_BLOCK, width)
    elif header["codec_id"] == BYTE_CODEC:
        if header["row_bytes"] is not None or header["row_count"] is not None:
            raise ArchiveError("byte codec cannot claim row geometry")
        reason = header["fallback_reason"]
        if ((width is not None and (not isinstance(reason, str) or not reason))
                or (width is None and reason is not None)):
            raise ArchiveError("byte fallback reason mismatch")
        block_size = BYTE_BLOCK
    else:
        raise ArchiveError("unsupported codec")
    count = (size + block_size - 1) // block_size
    if (uint(header["block_size_bytes"], "block size", positive=True) != block_size
            or uint(header["block_count"], "block count") != count
            or count > limits.max_blocks or min(size, block_size) > limits.max_decoded_block_bytes):
        raise ArchiveError("block geometry exceeds limit or differs")


class _FrameHeader(ctypes.Structure):
    _fields_ = [("content_size", ctypes.c_ulonglong), ("window_size", ctypes.c_ulonglong),
                ("block_max", ctypes.c_uint), ("frame_type", ctypes.c_int),
                ("header_size", ctypes.c_uint), ("dict_id", ctypes.c_uint),
                ("checksum", ctypes.c_uint), ("reserved1", ctypes.c_uint), ("reserved2", ctypes.c_uint)]


class ZstdDecoder:
    """Pinned 1.5.7 public C API; one independent frame, no implicit allocation size."""
    def __init__(self, profile: DecoderProfile, limits: DecodeLimits):
        limits.validate()
        address_space, _ = resource.getrlimit(resource.RLIMIT_AS)
        if address_space == resource.RLIM_INFINITY or not 0 < address_space <= 2 * 1024**3:
            raise ArchiveError("decoder requires finite RLIMIT_AS at most 2 GiB")
        sha(profile.decoder_executable_sha256, "decoder executable hash")
        sha(profile.zstd_library_sha256, "zstd library hash")
        for path, expected in ((profile.zstd_library_path, profile.zstd_library_sha256),
                               (profile.decoder_executable_path, profile.decoder_executable_sha256)):
            # These source-qualified dependencies have explicit exact file sizes.
            actual = hash_file(path, max_bytes=path.stat().st_size, deadline_ns=limits.deadline_ns)
            if actual.sha256 != expected:
                raise ArchiveError("decoder dependency hash mismatch")
        # The qualified interpreter may execute from a sealed ELF snapshot. Pin
        # the actual kernel executable bytes, not pathname/inode equivalence to
        # the original image. /proc/self/exe is a kernel-owned link, never input.
        running_hash=hashlib.sha256()
        with open("/proc/self/exe","rb") as running:
            before=file_stamp(os.fstat(running.fileno()))
            if before[2]!=profile.decoder_executable_path.stat().st_size:
                raise ArchiveError("actual decoder executable size differs")
            while True:
                limits.check_time()
                block=running.read(1024*1024)
                if not block:break
                running_hash.update(block)
            if before!=file_stamp(os.fstat(running.fileno())):
                raise ArchiveError("actual decoder executable changed")
        if running_hash.hexdigest()!=profile.decoder_executable_sha256:
            raise ArchiveError("actual decoder executable hash differs")
        self.lib = ctypes.CDLL(str(profile.zstd_library_path))
        signatures = {
            "ZSTD_versionNumber": (ctypes.c_uint, []),
            "ZSTD_isError": (ctypes.c_uint, [ctypes.c_size_t]),
            "ZSTD_getErrorName": (ctypes.c_char_p, [ctypes.c_size_t]),
            "ZSTD_getFrameHeader": (ctypes.c_size_t, [ctypes.POINTER(_FrameHeader), ctypes.c_void_p, ctypes.c_size_t]),
            "ZSTD_findFrameCompressedSize": (ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_size_t]),
            "ZSTD_compressBound": (ctypes.c_size_t, [ctypes.c_size_t]),
            "ZSTD_createDCtx": (ctypes.c_void_p, []),
            "ZSTD_freeDCtx": (ctypes.c_size_t, [ctypes.c_void_p]),
            "ZSTD_DCtx_setParameter": (ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]),
            "ZSTD_decompressDCtx": (ctypes.c_size_t, [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]),
        }
        for name, (result, args) in signatures.items():
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = result, args
        if self.lib.ZSTD_versionNumber() != 10507:
            raise ArchiveError("decoder zstd version is not 1.5.7")
        self.profile, self.limits = profile, limits

    def checked(self, result: int) -> int:
        if self.lib.ZSTD_isError(result):
            raise ArchiveError("zstd: " + self.lib.ZSTD_getErrorName(result).decode())
        return result

    def decode(self, frame: bytes, decoded_length: int) -> bytes:
        self.limits.check_time()
        if (decoded_length > self.limits.max_decoded_block_bytes or not decoded_length
                or len(frame) > self.limits.max_frame_bytes
                or len(frame) > self.lib.ZSTD_compressBound(decoded_length)):
            raise ArchiveError("frame input/output limit")
        info = _FrameHeader()
        if self.checked(self.lib.ZSTD_getFrameHeader(ctypes.byref(info), frame, len(frame))) != 0:
            raise ArchiveError("truncated zstd frame header")
        if (info.frame_type != 0 or info.content_size != decoded_length or info.dict_id != 0
                or info.checksum != 1 or info.window_size > (1 << self.profile.window_log)
                or info.window_size > self.limits.max_window_bytes or frame[4] & 3):
            raise ArchiveError("zstd frame profile/decoded size/window differs")
        if self.checked(self.lib.ZSTD_findFrameCompressedSize(frame, len(frame))) != len(frame):
            raise ArchiveError("concatenated or trailing frame bytes")
        context = self.lib.ZSTD_createDCtx()
        if not context:
            raise ArchiveError("zstd context allocation failed")
        try:
            self.checked(self.lib.ZSTD_DCtx_setParameter(context, 100, self.profile.window_log))
            output = ctypes.create_string_buffer(decoded_length)
            if self.checked(self.lib.ZSTD_decompressDCtx(context, output, decoded_length, frame, len(frame))) != decoded_length:
                raise ArchiveError("decoded length differs")
            self.limits.check_time()
            return output.raw
        finally:
            self.lib.ZSTD_freeDCtx(context)


def inverse_columns(data: bytes, row_bytes: int, *, deadline_ns: int) -> bytes:
    if not row_bytes or row_bytes % 8 or len(data) % row_bytes:
        raise ArchiveError("inverse row geometry")
    words = array.array("Q")
    words.frombytes(data)
    if sys.byteorder != "little":
        words.byteswap()
    rows, columns = len(data) // row_bytes, row_bytes // 8
    output = array.array("Q", [0]) * len(words)
    for column in range(columns):
        if time.monotonic_ns() >= deadline_ns:
            raise ArchiveError("inverse deadline expired")
        previous = 0
        for row in range(rows):
            previous = (previous + words[column * rows + row]) & MAX_U64
            output[row * columns + column] = previous
    if sys.byteorder != "little":
        output.byteswap()
    return output.tobytes()


@dataclass(frozen=True)
class VerifiedArchive:
    physical: PhysicalBinding
    canonical: PhysicalBinding
    header_sha256: str
    block_count: int
    file_identity: tuple
    verified_at_unix_ns: int


def verify_archive(path: pathlib.Path, *, expected_header: dict, role: RoleProfile,
                   physical: PhysicalBinding, profile: DecoderProfile,
                   limits: DecodeLimits, sink: BinaryIO | None = None,
                   archive_fd: int | None = None) -> VerifiedArchive:
    """Compare authenticated external bindings; sink bytes remain provisional on failure."""
    validate_header(expected_header, role, profile, limits)
    physical.validate()
    if physical.size_bytes > limits.max_archive_bytes:
        raise ArchiveError("physical archive exceeds limit")
    decoder = ZstdDecoder(profile, limits)
    phash, chash = hashlib.sha256(), hashlib.sha256()
    physical_count, canonical_count = 0, 0
    if archive_fd is not None:
        if (fcntl.fcntl(archive_fd, fcntl.F_GETFL) & os.O_ACCMODE) != os.O_RDONLY:
            raise ArchiveError("decoder archive fd must be read-only")
        pinned = os.fdopen(os.dup(archive_fd), "rb")
    else:
        pinned = open_regular(path)
    with pinned as stream:
        before = file_stamp(os.fstat(stream.fileno()))
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ArchiveError("decoder archive fd must be a regular file")
        stream.seek(0)
        if before[2] != physical.size_bytes:
            raise ArchiveError("physical size differs")

        def read(n):
            nonlocal physical_count
            limits.check_time()
            if checked_sum(physical_count, n) > physical.size_bytes:
                raise ArchiveError("truncated archive")
            data = stream.read(n)
            if len(data) != n:
                raise ArchiveError("truncated archive")
            physical_count += n
            phash.update(data)
            return data

        if read(8) != b"CPFA2331":
            raise ArchiveError("archive magic")
        header_len, = struct.unpack("<Q", read(8))
        if not 0 < header_len <= limits.max_header_bytes:
            raise ArchiveError("header size limit")
        header_bytes = read(header_len)
        header = parse_json(header_bytes)
        if header_bytes != canonical(expected_header):
            raise ArchiveError("header differs from admitted external logical/profile binding")
        for ordinal in range(header["block_count"]):
            index, offset, decoded, encoded = struct.unpack("<4Q", read(32))
            encoded_hash = read(32)
            required = min(header["block_size_bytes"], header["canonical_size_bytes"] - canonical_count)
            if (index != ordinal or offset != canonical_count or decoded != required
                    or encoded == 0 or encoded > limits.max_frame_bytes
                    or encoded > decoder.lib.ZSTD_compressBound(decoded)):
                raise ArchiveError("block order/offset/length differs")
            frame = read(encoded)
            if hashlib.sha256(frame).digest() != encoded_hash:
                raise ArchiveError("encoded frame hash differs")
            data = decoder.decode(frame, decoded)
            if header["codec_id"] == RAW_CODEC:
                data = inverse_columns(data, header["row_bytes"], deadline_ns=limits.deadline_ns)
            chash.update(data)
            canonical_count = checked_sum(canonical_count, len(data))
            if sink is not None:
                written = sink.write(data)
                if written != len(data):
                    raise ArchiveError("partial decoded sink write")
            limits.check_time()
        if read(8) != b"CPFAEND1":
            raise ArchiveError("missing archive completion footer")
        blocks, original_size = struct.unpack("<2Q", read(16))
        original_hash = read(32).hex()
        if (blocks != header["block_count"] or original_size != canonical_count
                or original_size != header["canonical_size_bytes"]
                or original_hash != chash.hexdigest() or original_hash != header["canonical_sha256"]):
            raise ArchiveError("canonical footer/size/hash differs")
        if physical_count != physical.size_bytes or stream.read(1):
            raise ArchiveError("trailing archive bytes")
        if phash.hexdigest() != physical.sha256:
            raise ArchiveError("whole physical archive hash differs")
        if (before != file_stamp(os.fstat(stream.fileno()))
                or before != file_stamp(os.stat(path, follow_symlinks=False))):
            raise ArchiveError("archive identity changed during readback")
    limits.check_time()
    return VerifiedArchive(physical, PhysicalBinding(canonical_count, chash.hexdigest()),
                           hashlib.sha256(header_bytes).hexdigest(), blocks, before, time.time_ns())
