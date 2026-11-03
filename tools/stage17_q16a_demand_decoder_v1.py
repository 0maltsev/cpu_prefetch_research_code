#!/usr/bin/env python3
"""Independent D212 demand-stream classification and exact inverse-ECDF ranks.

Measurement uses two passes over one descriptor, each verifying bytes/SHA256 and
file identity. Pass one validates every retained row and determines eligible
counts. Pass two keeps only min(rank, N-rank+1) integer values per sequence.
For p999/p001 this is about 0.1% of each eligible sequence, not full vectors.
Warmup validates raw rows once without sequence inference.
Output size is independent of observation count. Caller must budget that heap
memory; no empirical duration, capacity or minimum count is supplied here.

This component does not establish primary-stream reconciliation, execution
origins, warmup/reset, hardware validity, independent repetitions or admission.
The formal adapter must bind those facts before using any returned summary.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import heapq
import json
import os
import pathlib
import sys
from typing import Any

import stage17_raw_stream_decoder_v1 as codec
import stage17_raw_stream_decoder_v2 as raw

FORMAT_ID = 'Q16A-DEMAND-U64LE-LP-RUNID-v1'
CONTRACT_ID = 'cpu-prefetch-stage17-q16a-demand-stream/1'
SCHEMA_ID = 'cpu-prefetch-stage17-q16a-demand-classification/1'
METHOD_ID = 'RING-D2-RUNTAIL-LTL95C95-WINDOW-v2'
DecodeError = codec.DecodeError


def exact_rank(count: int, numerator: int, denominator: int) -> int:
    """D037 X_(ceil(p*N)); decomposition matches accepted checked integer math."""
    raw._uint(count, 'sequence count', 1)
    raw._uint(numerator, 'probability numerator', 1)
    raw._uint(denominator, 'probability denominator', 1)
    if numerator > denominator:
        raise DecodeError('probability exceeds one')
    whole, remainder = divmod(count, denominator)
    rank = whole * numerator + (remainder * numerator + denominator - 1) // denominator
    if not 1 <= rank <= count:
        raise DecodeError('order-statistic rank outside sequence')
    return rank


class _Tail:
    def __init__(self, count: int, numerator: int):
        self.count = count
        self.rank = exact_rank(count, numerator, 1000)
        self.smallest = self.rank <= count - self.rank + 1
        self.limit = min(self.rank, count - self.rank + 1)
        self.values: list[int] = []
        self.seen = 0

    def add(self, value: int) -> None:
        self.seen += 1
        encoded = -value if self.smallest else value
        if len(self.values) < self.limit:
            heapq.heappush(self.values, encoded)
        elif encoded > self.values[0]:
            heapq.heapreplace(self.values, encoded)

    def result(self) -> dict[str, int]:
        if self.seen != self.count or len(self.values) != self.limit:
            raise DecodeError('second-pass eligible sequence count changed')
        value = -self.values[0] if self.smallest else self.values[0]
        return dict(count=self.count, rank=self.rank, value_ticks=value,
                    retained_heap_items=self.limit)


def _scan(stream, *, run_id, row_bytes, row_count, role, clock_origin,
          start, end, measurement, tails=None):
    counts = dict(attempted=0, advanced=0, full=0, empty=0, outside_demand=0)
    if measurement:
        counts.update(eligible_demand=0, eligible_advanced=0, eligible_issue=0)
    previous_end = start
    previous_eligible_advance = None
    for ordinal in range(row_count):
        row = codec._row(stream, row_bytes, run_id, 9, f'demand[{ordinal}]')
        attempt, outcome, advancing, before_status, before_abs, before, after_status, after_abs, after = row
        if attempt != ordinal:
            raise DecodeError('demand attempt ordinal is not contiguous')
        if outcome not in ((0, 1) if role == 'producer' else (0, 2)):
            raise DecodeError('unknown or wrong-role demand outcome')
        if before_status != 0 or after_status != 0:
            raise DecodeError('failed demand clock status in retained prefix')
        raw._clock_pair(before_abs, before, clock_origin, 'demand before')
        raw._clock_pair(after_abs, after, clock_origin, 'demand after')
        if before < start:
            raise DecodeError('phase demand before released origin')
        if before < previous_end or after < before:
            raise DecodeError('within/across demand bracket order invalid')
        previous_end = after
        if outcome == 0:
            if advancing != counts['advanced']:
                raise DecodeError('advancing ordinal is not contiguous')
            counts['advanced'] += 1
        else:
            if advancing != 0:
                raise DecodeError('nonadvancing demand has advancing identity')
            counts['full' if outcome == 1 else 'empty'] += 1
        counts['attempted'] += 1
        if before >= end:
            counts['outside_demand'] += 1
            continue
        if not measurement:
            continue
        latency = after - before
        if latency == 0:
            raise DecodeError('eligible demand sequence is nonpositive')
        counts['eligible_demand'] += 1
        if tails is not None:
            tails['demand'].add(latency)
        if outcome == 0:
            counts['eligible_advanced'] += 1
            if previous_eligible_advance is not None:
                issue = before - previous_eligible_advance
                if issue <= 0:
                    raise DecodeError('eligible issue sequence is nonpositive')
                counts['eligible_issue'] += 1
                if tails is not None:
                    tails['issue'].add(issue)
            previous_eligible_advance = before
    if (counts['advanced'] + counts['full'] + counts['empty'] != counts['attempted']
            or (measurement and (counts['eligible_issue'] != max(counts['eligible_advanced'] - 1, 0)
                or counts['eligible_demand'] + counts['outside_demand'] != counts['attempted']))):
        raise DecodeError('demand count equations differ')
    stream.finish()
    return counts


def decode(root: pathlib.Path, contract: dict[str, Any]) -> dict[str, Any]:
    """Validate one phase stream; only measurement can produce sequence summaries."""
    obj = raw._object(contract, 'schema_version physical_format method_id run_id role phase '
                      'stream phase_window minimum_observations_per_series', 'contract')
    if (obj['schema_version'] != CONTRACT_ID or obj['physical_format'] != FORMAT_ID
            or obj['method_id'] != METHOD_ID):
        raise DecodeError('unsupported Q16a contract/format/method')
    if obj['role'] not in ('producer', 'consumer') or obj['phase'] not in ('warmup', 'measurement'):
        raise DecodeError('explicit producer/consumer and warmup/measurement required')
    measurement = obj['phase'] == 'measurement'
    run_id = obj['run_id']
    if not isinstance(run_id, str):
        raise DecodeError('run_id must be a string')
    try:
        prefix_bytes = codec.row_layout(run_id)[0]
    except (ValueError, UnicodeError) as error:
        raise DecodeError('invalid run_id encoding') from error
    row_bytes = prefix_bytes + 9 * 8
    binding = raw._binding(obj['stream'], 'demand stream', row_bytes)
    minimum = obj['minimum_observations_per_series']
    if measurement:
        raw._uint(minimum, 'plan minimum count', 1)
    elif minimum is not None:
        raise DecodeError('warmup minimum must be null; no inferential count gate')
    window = raw._object(obj['phase_window'], 'clock_suite_id time_unit ticks_per_second '
                         'clock_origin_absolute_nanoseconds phase_origin duration_ticks', 'phase_window')
    projected = {key: value for key, value in window.items() if key != 'phase_origin'}
    projected['measurement_origin'] = window['phase_origin']
    clock_origin, start, end = raw.validate_measurement_window(projected)
    scan_args = dict(run_id=run_id, row_bytes=row_bytes, row_count=binding['row_count'],
                     role=obj['role'], clock_origin=clock_origin, start=start, end=end, measurement=measurement)
    summaries = dict(demand=None, issue=None)
    try:
        with ExitStack() as stack:
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            stack.callback(os.close, root_fd)
            first = raw._open_stream(stack, root_fd, binding, 'demand pass one')
            counts = _scan(first, **scan_args)
            if measurement:
                if counts['eligible_demand'] < minimum or counts['eligible_issue'] < minimum:
                    raise DecodeError('insufficient eligible demand/issue observations for plan minimum')
                tails = dict(demand=_Tail(counts['eligible_demand'], 999),
                             issue=_Tail(counts['eligible_issue'], 1))
                first.file.seek(0)
                second = raw._HashedStream(first.file, binding, 'demand pass two')
                identity = lambda info: (info.st_dev, info.st_ino, info.st_size,
                                         info.st_mtime_ns, info.st_ctime_ns)
                if identity(second.before) != identity(first.before):
                    raise DecodeError('demand file identity changed between passes')
                repeated = _scan(second, tails=tails, **scan_args)
                if repeated != counts:
                    raise DecodeError('demand counts changed between passes')
                summaries = {name: tail.result() for name, tail in tails.items()}
    except OSError as error:
        raise DecodeError('demand stream access failed: ' + str(error)) from error
    return dict(schema_version=SCHEMA_ID, physical_format=FORMAT_ID, method_id=METHOD_ID,
                run_id=run_id, role=obj['role'], phase=obj['phase'], stream=dict(binding),
                phase_window=dict(window, phase_origin=dict(window['phase_origin'])),
                minimum_observations_per_series=minimum, interval_end_ticks=end,
                counts=counts, inferential_eligible=measurement, demand_p999=summaries['demand'], issue_p001=summaries['issue'],
                raw_stream_validated=True, primary_reconciliation_validated=False,
                execution_evidence_validated=False, execution_authority=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=pathlib.Path, required=True)
    parser.add_argument('--contract', type=pathlib.Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_bytes(), object_pairs_hook=raw._unique,
                         parse_constant=raw._invalid_constant)
    print(codec.canonical(decode(args.root, contract)).decode(), end='')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, TypeError, DecodeError) as error:
        print(f'stage17-q16a-demand-decoder: FAIL: {error}', file=sys.stderr)
        raise SystemExit(1) from error
