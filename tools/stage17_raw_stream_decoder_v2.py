#!/usr/bin/env python3
"""Independent D211 completion counting over fully reconciled primary streams.

Physical RAW-OBS-U64LE-LP-RUNID-v1 bytes are unchanged. All three streams are
read once through hash-checked open descriptors with O(1) row storage. Counts
include all drain rows for integrity; only the separate interval numerator
uses the accepted completion window. This does not validate warmup, hardware,
or whether a supplied origin was actually released: the formal admission
adapter must bind measurement_window to original execution evidence first.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import os
import pathlib
import stat
import sys
from typing import Any

import stage17_raw_stream_decoder_v1 as legacy

FORMAT_ID = legacy.FORMAT_ID
CONTRACT_ID = 'cpu-prefetch-stage17-raw-stream-contract/2'
SCHEMA_ID = 'cpu-prefetch-stage17-independent-raw-reconciliation/2'
COUNTING_RULE_ID = 'AMEND-2.0.0-pre.3-Q16B-INTERVAL-COMPLETIONS-v1'
CLOCK_SUITE_ID = 'LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1'
TIME_UNIT = 'PICOSECONDS'
TICKS_PER_SECOND = 1_000_000_000_000
MAX_U64 = (1 << 64) - 1
DecodeError = legacy.DecodeError


def _object(value: Any, keys: str, label: str) -> dict:
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        raise DecodeError(label + ': exact fields required')
    return value


def _uint(value: Any, label: str, minimum: int = 0) -> int:
    if type(value) is not int or not minimum <= value <= MAX_U64:
        raise DecodeError(label + ': uint64 integer required')
    return value


def _clock_pair(absolute: int, relative: int, origin: int, label: str) -> None:
    _uint(absolute, label + '.absolute_nanoseconds')
    _uint(relative, label + '.relative_picoseconds')
    if absolute < origin:
        raise DecodeError(label + ': timestamp before clock origin')
    delta = absolute - origin
    if delta > MAX_U64 // 1000 or delta * 1000 != relative:
        raise DecodeError(label + ': clock-domain conversion mismatch/overflow')


def validate_measurement_window(document: Any) -> tuple[int, int, int]:
    """Return (clock origin ns, measurement origin ps, exclusive end ps)."""
    window = _object(document, 'clock_suite_id time_unit ticks_per_second '
                     'clock_origin_absolute_nanoseconds measurement_origin duration_ticks',
                     'measurement_window')
    if (window['clock_suite_id'] != CLOCK_SUITE_ID or window['time_unit'] != TIME_UNIT
            or type(window['ticks_per_second']) is not int
            or window['ticks_per_second'] != TICKS_PER_SECOND):
        raise DecodeError('measurement_window: unsupported clock suite/unit/rate')
    origin = _uint(window['clock_origin_absolute_nanoseconds'], 'clock origin')
    sample = _object(window['measurement_origin'], 'absolute_nanoseconds relative_picoseconds',
                     'measurement origin')
    _clock_pair(sample['absolute_nanoseconds'], sample['relative_picoseconds'], origin,
                'measurement origin')
    start = sample['relative_picoseconds']
    duration = _uint(window['duration_ticks'], 'duration_ticks', 1)
    if duration > MAX_U64 - start:
        raise DecodeError('measurement_window: endpoint overflow')
    end = start + duration
    # An integer-ps endpoint may lie between ns samples. Its first possible
    # at/after-end clock sample must also fit the codec's uint64 absolute ns.
    if (end + 999) // 1000 > MAX_U64 - origin:
        raise DecodeError('measurement_window: absolute endpoint overflow')
    return origin, start, end


def _binding(value: Any, label: str, row_bytes: int) -> dict:
    binding = _object(value, 'path size_bytes sha256 row_count', label)
    path, digest = binding['path'], binding['sha256']
    if (not isinstance(path, str) or not path or '\0' in path
            or pathlib.PurePosixPath(path).is_absolute()
            or any(part in ('', '.', '..') for part in path.split('/'))):
        raise DecodeError(label + ': unsafe relative stream path')
    if (not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)):
        raise DecodeError(label + ': invalid SHA-256')
    size = _uint(binding['size_bytes'], label + '.size_bytes')
    count = _uint(binding['row_count'], label + '.row_count')
    if count > MAX_U64 // row_bytes or count * row_bytes != size:
        raise DecodeError(label + ': row/byte count mismatch or overflow')
    return binding


class _HashedStream:
    def __init__(self, file, binding, label):
        self.file, self.binding, self.label = file, binding, label
        self.before = os.fstat(file.fileno())
        if not stat.S_ISREG(self.before.st_mode) or self.before.st_size != binding['size_bytes']:
            raise DecodeError(label + ': regular-file byte binding mismatch')
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def read(self, size):
        value = self.file.read(size)
        self.digest.update(value)
        self.bytes_read += len(value)
        return value

    def finish(self):
        if self.read(1):
            raise DecodeError(self.label + ': trailing bytes')
        after = os.fstat(self.file.fileno())
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if stamp(self.before) != stamp(after):
            raise DecodeError(self.label + ': raw file changed during read')
        if self.bytes_read != self.binding['size_bytes'] or self.digest.hexdigest() != self.binding['sha256']:
            raise DecodeError(self.label + ': byte count/SHA-256 mismatch')


def _open_stream(stack, root_fd, binding, label):
    """No symlink components or special files beneath the caller's root fd."""
    parent = root_fd
    parts = binding['path'].split('/')
    for part in parts[:-1]:
        parent = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
        stack.callback(os.close, parent)
    fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                 dir_fd=parent)
    try:
        file = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    stack.enter_context(file)
    return _HashedStream(file, binding, label)


def reconcile(root: pathlib.Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Verify original rows/joins and derive D211 counts; never admit a run."""
    obj = _object(contract, 'schema_version run_id physical_format streams measurement_window', 'contract')
    if obj['schema_version'] != CONTRACT_ID or obj['physical_format'] != FORMAT_ID:
        raise DecodeError('unsupported contract or physical format')
    run_id = obj['run_id']
    if not isinstance(run_id, str):
        raise DecodeError('run_id must be a string')
    try:
        _, producer_bytes, consumer_bytes, joined_bytes = legacy.row_layout(run_id)
    except (ValueError, UnicodeError) as error:
        raise DecodeError('invalid run_id encoding') from error
    clock_origin, start, end = validate_measurement_window(obj['measurement_window'])
    streams = _object(obj['streams'], 'producer consumer joined', 'streams')
    row_sizes = dict(producer=producer_bytes, consumer=consumer_bytes, joined=joined_bytes)
    bindings = {name: _binding(streams[name], name, size) for name, size in row_sizes.items()}
    if len({binding['path'] for binding in bindings.values()}) != 3:
        raise DecodeError('stream roles must bind distinct paths')
    accepted = full = interval = outside = 0
    previous_producer_finish = previous_consumer_finish = start
    try:
        with ExitStack() as stack:
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            stack.callback(os.close, root_fd)
            opened = {name: _open_stream(stack, root_fd, value, name) for name, value in bindings.items()}
            if len({(s.before.st_dev, s.before.st_ino) for s in opened.values()}) != 3:
                raise DecodeError('stream roles alias the same physical file')
            producer, consumer, joined = (opened[name] for name in ('producer', 'consumer', 'joined'))
            for logical in range(bindings['producer']['row_count']):
                p = legacy._row(producer, producer_bytes, run_id, 15, f'producer[{logical}]')
                if p[0] != logical or p[14] not in (legacy.ACCEPTED_FLAGS, legacy.FULL_FLAGS):
                    raise DecodeError('producer logical sequence/flags mismatch')
                for absolute_index in (3, 5, 7, 11):
                    _clock_pair(p[absolute_index], p[absolute_index+1], clock_origin, 'producer sample')
                if not (p[2] <= p[4] <= p[6] <= p[8] <= p[12]) or p[4] < previous_producer_finish:
                    raise DecodeError('producer local/cross-row timestamp order invalid')
                previous_producer_finish = p[12]
                if p[14] == legacy.FULL_FLAGS:
                    if p[9] != 0 or p[10] != 0 or p[13] != 0:
                        raise DecodeError('FULL contains accepted-only values')
                    full += 1
                    continue
                _clock_pair(p[9], p[10], clock_origin, 'producer publication')
                if p[13] != accepted or not p[8] <= p[10] <= p[12]:
                    raise DecodeError('accepted ordinal/publication mismatch')
                c = legacy._row(consumer, consumer_bytes, run_id, 10, f'consumer[{accepted}]')
                j = legacy._row(joined, joined_bytes, run_id, 24, f'joined[{accepted}]')
                if c[0] != accepted or c[1] != p[1]:
                    raise DecodeError('consumer ordinal/record index mismatch')
                for absolute_index in (2, 4, 6, 8):
                    _clock_pair(c[absolute_index], c[absolute_index+1], clock_origin, 'consumer sample')
                if (not c[3] <= c[5] <= c[7] <= c[9] or c[3] < previous_consumer_finish
                        or c[5] < p[10]):
                    raise DecodeError('consumer local/cross-row/publication timestamp order invalid')
                previous_consumer_finish = c[9]
                expected = (
                    accepted, p[0], p[1], logical, accepted,
                    p[2], p[4], p[6], p[8], p[10], p[12], c[3], c[5], c[7], c[9],
                    p[4]-p[2], p[6]-p[4], p[12]-p[8], p[10]-p[2], c[5]-p[10],
                    c[7]-c[3], c[9]-c[5], c[9]-c[7], c[9]-p[2],
                )
                if j != expected:
                    raise DecodeError('joined row differs from independently derived row')
                accepted += 1
                if start <= c[9] < end:
                    interval += 1
                else:
                    outside += 1
            for stream in opened.values():
                stream.finish()
    except OSError as error:
        raise DecodeError('raw stream access failed: ' + str(error)) from error
    if (bindings['consumer']['row_count'] != accepted or bindings['joined']['row_count'] != accepted
            or accepted + full != bindings['producer']['row_count'] or interval + outside != accepted):
        raise DecodeError('full-stream reconciliation/count equations differ')
    result = legacy.Reconciliation(bindings['producer']['row_count'], accepted, full, accepted,
                                   True, full == 0, 'NOT_EVALUATED').document(
                                       run_id, {name: b['sha256'] for name, b in bindings.items()})
    result.update(schema_version=SCHEMA_ID, completion_counting_rule_id=COUNTING_RULE_ID,
                  measurement_window=dict(obj['measurement_window'],
                      measurement_origin=dict(obj['measurement_window']['measurement_origin'])),
                  interval_end_ticks=end, interval_consumed_count=interval,
                  outside_interval_consumed_count=outside,
                  execution_evidence_validated=False, execution_authority=False)
    return result


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise DecodeError('duplicate JSON key: ' + key)
        value[key] = item
    return value


def _invalid_constant(value):
    raise DecodeError('nonfinite JSON number: ' + value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=pathlib.Path)
    parser.add_argument('--contract', required=True, type=pathlib.Path)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_bytes(), object_pairs_hook=_unique,
                         parse_constant=_invalid_constant)
    print(legacy.canonical(reconcile(args.root, contract)).decode(), end='')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, DecodeError) as error:
        print(f'stage17-raw-stream-decoder-v2: FAIL: {error}', file=sys.stderr)
        raise SystemExit(1) from error
