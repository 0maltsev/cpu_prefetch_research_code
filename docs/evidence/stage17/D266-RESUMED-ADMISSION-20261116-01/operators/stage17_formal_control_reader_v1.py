"""D261 finite, plan-sized Q16b control reading; unchanged scientific checks.

Only the cumulative packed-page allocation ceiling differs from the original
reader. Original parser bytecode, integer/error rules and PackedPages type are
reused in a private function namespace. No qualified global is modified.
The caller must authenticate and validate the original signed plan first.
"""
from __future__ import annotations

import contextlib
import io
import types

import stage17_discovery_validation_v3 as common

VERSION = 'cpu-prefetch-stage17-formal-control-reader/1'
MAX_PACKED_BYTES = 512 * 1024**2
BLOCK_ITEMS = 8192
BLOCK_BYTES = BLOCK_ITEMS * 8
U64 = (1 << 64) - 1


def _uint(value, label, *, positive=False):
    common.require(type(value) is int and (1 if positive else 0) <= value <= U64,
                   label+': expected bounded integer')
    return value


def packed_capacity(capture, resources, monitoring):
    """Charge every rounded array block in the 42 planned residency records."""
    common.exact(capture['method_id'], 'SERVICE-RATE-NP-LTL95C95-MIN-v1', 'Q16b collector')
    page = _uint(capture['geometry']['base_page_bytes'], 'verified base page bytes', positive=True)
    regions = resources['region_bytes']
    common.require(type(regions) is list and len(regions) == 7, 'seven declared residency regions required')
    common.exact(regions[3:], [resources['workers'][key]['bytes']
        for key in ('producer_stack', 'consumer_stack')]+[resources['core_bytes'],
        resources['controller_stack']['bytes']], 'declared residency stack/core geometry')
    pages = []
    for size in regions:
        _uint(size, 'mapped region bytes', positive=True)
        common.require(size % page == 0, 'region is not a whole number of base pages')
        pages.append(size // page)
    first, count = (monitoring[key] for key in ('during_first_page', 'during_page_count'))
    common.require(type(first) is list and type(count) is list
                   and len(first) == len(count) == 7, 'seven bounded during residency regions required')
    for begin, length, maximum in zip(first, count, pages, strict=True):
        _uint(begin, 'during first page'); _uint(length, 'during page count')
        common.require(begin <= maximum and length <= maximum-begin, 'during residency exceeds actual region')
    rounded = lambda n: ((n + BLOCK_ITEMS-1) // BLOCK_ITEMS) * BLOCK_BYTES
    # Two phases, BEFORE/AFTER over every full region, and one DURING per
    # phase; both page_addresses and page_status arrays receive their own slack.
    capacity = 8 * sum(rounded(n) for n in pages) + 4 * sum(rounded(n) for n in count)
    common.require(0 < capacity <= MAX_PACKED_BYTES, 'planned packed page capacity exceeds finite 512MiB ceiling')
    return capacity


def reader_type(capacity):
    """Bind one finite allocation ceiling without altering shared parser state."""
    _uint(capacity, 'packed capacity', positive=True)
    common.require(capacity % BLOCK_BYTES == 0 and capacity <= MAX_PACKED_BYTES,
                   'packed capacity must be whole blocks within 512MiB')
    common.require(common.PAGE_BLOCK_ITEMS == BLOCK_ITEMS, 'qualified reader block geometry differs')
    original = common.JsonReader.packed_pages
    scope = dict(original.__globals__, MAX_PACKED_PAGE_BYTES=capacity)
    packed = types.FunctionType(original.__code__, scope, original.__name__,
                                original.__defaults__, original.__closure__)
    packed.__kwdefaults__ = original.__kwdefaults__

    class FormalJson(common.JsonReader):
        packed_pages = packed

        def value(self, key='', depth=0):
            common.require(key != 'drain_rows', 'unexpected formal drain JSON')
            return super().value(key, depth)

    return FormalJson


@contextlib.contextmanager
def control(root, logical, *, capture, resources, monitoring):
    capacity = packed_capacity(capture, resources, monitoring)
    reader = reader_type(capacity)
    with contextlib.ExitStack() as stack:
        raw = stack.enter_context(common.opened(root, logical))
        text = io.TextIOWrapper(raw, encoding='utf-8', errors='strict')
        try:
            yield reader(text, stack).document()
        finally:
            text.detach()


def analysis_child(connection, job, profile, decoder_limits, hardware, cpu, deadline,
                   *, original_child):
    """Select only the new reader in an authenticated original child body.

    The calling operator authenticates original_child and this source before
    starting children. Original decode, resource, validation, output and error
    paths execute unchanged. The process envelope records the new reader; the
    scientific report itself retains its original schema and validator bytes.
    """
    item = job['item']
    capacity = packed_capacity(item['capture'], item['resources'], item['monitoring'])

    def read_control(provided_common, root, logical):
        common.require(provided_common is common, 'qualified science/common module differs')
        return control(root, logical, capture=item['capture'],
                       resources=item['resources'], monitoring=item['monitoring'])

    class ReportingConnection:
        def send(self, result):
            connection.send(dict(result, control_reader=dict(version=VERSION,
                packed_capacity_bytes=capacity,
                hard_ceiling_bytes=MAX_PACKED_BYTES, original_parser_bytecode_preserved=True)))

        def close(self):
            connection.close()

    scope = dict(original_child.__globals__, control=read_control)
    child = types.FunctionType(original_child.__code__, scope, original_child.__name__,
                               original_child.__defaults__, original_child.__closure__)
    child.__kwdefaults__ = original_child.__kwdefaults__
    child(ReportingConnection(), job, profile, decoder_limits, hardware, cpu, deadline)
