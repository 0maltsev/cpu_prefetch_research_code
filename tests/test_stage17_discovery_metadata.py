"""Packed page JSON compatibility and bounded-memory software verification.

The maximum-geometry subprocess streams 31,944,212 integers without constructing
an input list/string or a native hardware capture. RSS includes the parser and
all retained arrays. This is a metadata resource test, not timing evidence.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import resource
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import stage17_discovery_validation_v1 as v


def parse(text):
    with contextlib.ExitStack() as stack:
        reader = v.JsonReader(io.StringIO(text), stack)
        return reader.document(), reader


class FragmentStream:
    """read(n) from finite fragments, retaining at most one fragment plus n."""
    def __init__(self, fragments):
        self.fragments = iter(fragments)
        self.pending = ''

    def read(self, size):
        while len(self.pending) < size:
            try:
                self.pending += next(self.fragments)
            except StopIteration:
                break
        result, self.pending = self.pending[:size], self.pending[size:]
        return result


def geometry_document():
    # Recorded preview BEYOND_LLC 18m/18m: exact seven region byte counts.
    pages = [n // 4096 for n in
             (603979776, 5539115008, 10206019584, 2097152, 2097152, 16384, 2097152)]
    counts = [1 if moment == 1 else n for _ in range(2)
              for moment in range(3) for n in pages]
    yield '{"residency":['
    for ordinal, count in enumerate(counts):
        if ordinal:
            yield ','
        yield '{'
        for index, (key, value) in enumerate((('page_addresses', str(v.U64)),
                                             ('page_status', str(-(1 << 63))))):
            if index:
                yield ','
            yield '"' + key + '":[' + value
            remaining = count - 1
            while remaining:
                amount = min(8192, remaining)
                yield (',' + value) * amount
                remaining -= amount
            yield ']'
        yield '}'
    yield ']}'


def maximum_geometry():
    with contextlib.ExitStack() as stack:
        reader = v.JsonReader(FragmentStream(geometry_document()), stack)
        result = reader.document()
        arrays = [row[key] for row in result['residency']
                  for key in ('page_addresses', 'page_status')]
        assert len(result['residency']) == 42
        assert sum(map(len, arrays)) == 31_944_212
        # Inspect every retained value, including values spanning stream blocks.
        for index, values in enumerate(arrays):
            expected = v.U64 if index % 2 == 0 else -(1 << 63)
            assert all(value == expected for value in values)
        report = dict(items=sum(map(len, arrays)), packed_bytes=reader.packed_bytes,
                      nodes=reader.nodes, text_bytes=reader.text_bytes,
                      peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        assert reader.packed_bytes <= v.MAX_PACKED_PAGE_BYTES
        assert report['peak_rss_bytes'] < 512 * 1024 * 1024
        print(json.dumps(report), flush=True)


class PackedMetadataTests(unittest.TestCase):
    def test_exact_integer_limits_and_empty(self):
        result, _ = parse('{"page_addresses":[0,18446744073709551615],'
                          '"page_status":[-9223372036854775808,9223372036854775807,0]}')
        self.assertEqual(list(result['page_addresses']), [0, v.U64])
        self.assertEqual(list(result['page_status']), [-(1 << 63), (1 << 63) - 1, 0])
        self.assertEqual(list(result['page_status']), list(result['page_status']))
        result, reader = parse('{"page_status":[],"page_addresses":[]}')
        self.assertEqual(len(result['page_status']), 0)
        self.assertEqual(reader.packed_bytes, 0)

    def test_type_range_lexical_and_delimiter_rejection(self):
        for key, invalids in (
                ('page_addresses', ['-1', '18446744073709551616']),
                ('page_status', ['-9223372036854775809', '9223372036854775808'])):
            for token in invalids + ['true', 'false', 'null', '1.0', '1e0', 'NaN',
                                     '"1"', '{}', '[]', '01', '+1', '1 2', '1,', '']:
                if token == '':
                    text = '{"' + key + '":[1'
                else:
                    text = '{"' + key + '":[' + token + ']}'
                with self.subTest(text=text), self.assertRaises(ValueError):
                    parse(text)

    def test_duplicate_truncation_and_trailing_rejection(self):
        for text in ('{"page_status":[0],"page_status":[1]}',
                     '{"page_addresses":[1]', '{"page_status":[1',
                     '{"page_status":[1]}x'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse(text)

    def test_packed_cumulative_capacity_includes_block_slack(self):
        with patch.object(v, 'MAX_PACKED_PAGE_BYTES', 65536):
            result, reader = parse('{"page_status":[0]}')
            self.assertEqual(len(result['page_status']), 1)
            self.assertEqual(reader.packed_bytes, 65536)
            with self.assertRaisesRegex(v.ValidationError, 'cumulative packed'):
                parse('{"page_status":[0],"page_addresses":[1]}')
            with self.assertRaisesRegex(v.ValidationError, 'cumulative packed'):
                parse('{"page_status":[' + ','.join(['0'] * 8193) + ']}')

    def test_only_packed_numbers_bypass_generic_guards(self):
        with patch.object(v, 'MAX_JSON_NODES', 4), patch.object(v, 'MAX_RESIDENT_TEXT', 80):
            result, reader = parse('{"page_status":[' + ','.join(['0'] * 9000) + ']}')
            self.assertEqual(len(result['page_status']), 9000)
            self.assertEqual(reader.nodes, 3)
            with self.assertRaisesRegex(v.ValidationError, 'metadata'):
                parse('{"ordinary":[0,0,0]}')
            with self.assertRaisesRegex(v.ValidationError, 'string size'):
                parse('{"ordinary":"' + 'x' * 80 + '"}')
            with self.assertRaises(ValueError):
                parse('{"page_status":["' + 'x' * 80 + '"]}')

    def test_stream_boundaries_whitespace_and_signed_zero(self):
        text = '{"page_addresses":[18446744073709551615,0],"page_status":[-0, -1, 2]}'
        class TinyStream(io.StringIO):
            def read(self, size):
                return super().read(min(size, 1))
        with contextlib.ExitStack() as stack:
            result = v.JsonReader(TinyStream(text), stack).document()
        self.assertEqual(list(result['page_addresses']), [v.U64, 0])
        self.assertEqual(list(result['page_status']), [0, -1, 2])

if __name__ == '__main__':
    if sys.argv[1:] == ['--maximum-geometry']:
        maximum_geometry()
    else:
        unittest.main()
