"""Exact archive parse acceptance/error parity; software verification only."""
from __future__ import annotations

import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import stage17_archive_json_fast_v1 as fast
import stage17_formal_archive_v1 as archive


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.parse = fast.bind_parse(archive.parse_json)

    def parity(self, raw, parser=None):
        if parser is None:
            parser = self.parse
        try:
            expected = archive.parse_json(raw)
        except Exception as error:
            with self.assertRaises(type(error)) as caught:
                parser(raw)
            self.assertIs(type(caught.exception), type(error))
            self.assertEqual(caught.exception.args, error.args)
            self.assertEqual(str(caught.exception), str(error))
            self.assertIs(type(caught.exception.__cause__), type(error.__cause__))
            if error.__cause__ is not None:
                self.assertEqual(str(caught.exception.__cause__), str(error.__cause__))
        else:
            actual = parser(raw)
            self.assertIs(type(actual), dict)
            self.assertEqual(actual, expected)

    def fallback(self, raw):
        original = Mock(wraps=archive.parse_json)
        self.parity(raw, fast.bind_parse(original))
        original.assert_called_once()
        self.assertIs(original.call_args.args[0], raw)

    def test_canonical_ascii_object_uses_builtin_load_and_single_dump(self):
        raw = b'{"a":[null,false,true,0,9999999999999999999],"z":{"key":"value"}}'
        original = Mock(side_effect=AssertionError('unexpected fallback'))
        with patch.object(fast.json, 'loads', wraps=json.loads) as loads, \
                patch.object(fast.json, 'dumps', wraps=json.dumps) as dumps:
            self.assertEqual(fast.bind_parse(original)(raw),
                             {'a': [None, False, True, 0, 9999999999999999999],
                              'z': {'key': 'value'}})
        loads.assert_called_once_with(raw.decode('utf-8', errors='strict'))
        dumps.assert_called_once_with(
            {'a': [None, False, True, 0, 9999999999999999999], 'z': {'key': 'value'}},
            sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        original.assert_not_called()

    def test_ascii_escaping_controls_and_fake_syntax_stay_in_fast_domain(self):
        value = {'': '\b\t\n\f\r\x00\\"/',
                 'a': ('{[ -9999999999999999999999 1.2 1e9 1E9 NaN Infinity '
                       '\\"a\\":1,"a":2 \\u00e9 ]}') * 150}
        raw = archive.canonical(value)
        original = Mock(side_effect=AssertionError('string contents treated as syntax'))
        self.assertEqual(fast.bind_parse(original)(raw), value)
        original.assert_not_called()
        self.parity(raw)

    def test_noncanonical_bytes_and_nonobjects_fall_back(self):
        for raw in (b'', b' {}', b'{}\n', b'{ "a":1}', b'{"b":2,"a":1}',
                    b'{"a": 1}', b'{"a":"\\/"}', b'{"a":"\\u0061"}',
                    b'{"a":"\\u000A"}', b'[]', b'[{}]', b'null', b'true',
                    b'1', b'"text"', b'{}{}'):
            with self.subTest(raw=raw):
                self.fallback(raw)

    def test_duplicates_nested_deep_and_escaped_keys_preserve_specific_error(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":1,"\\u0061":2}',
                    b'{"a":{"x":0,"x":0}}', b'{"a":[{"x":1,"x":2}]}',
                    b'{"a":1,"a":NaN}', b'{"a":NaN,"a":1}',
                    b'{"a":18446744073709551616,"a":0}',
                    b'{"a":' + b'[' * 129 + b'{"x":0,"x":1}' + b']' * 129 + b'}',
                    b'{"\\u00e9":1,"\\u00e9":2}'):
            with self.subTest(raw=raw):
                self.fallback(raw)
        with self.assertRaisesRegex(archive.ArchiveError, '^duplicate JSON key: a$'):
            self.parse(b'{"a":1,"\\u0061":2}')

    def test_malformed_nonfinite_and_overflow_preserve_errors(self):
        for token in (b'NaN', b'Infinity', b'-Infinity', b'nan', b'inf', b'1e9999',
                      b'-1e9999', b'01', b'-01', b'+1', b'.1', b'1.', b'1e',
                      b'1e+', b'--1', b'True', b'undefined'):
            with self.subTest(token=token):
                self.fallback(b'{"a":' + token + b'}')
        for raw in (b'{', b'{"a":}', b'{"a":1,}', b'{"a":[1,]}',
                    b'{"a":"unterminated}', b'{"a":"\\q"}',
                    b'{"a":"\\u00xz"}', b'{"a":"raw\x00control"}',
                    b'{"a":"\\"}', b'{/*comment*/}', b'{"a":1}\x00'):
            with self.subTest(raw=raw):
                self.fallback(raw)

    def test_all_negatives_floats_and_large_integers_fall_back(self):
        for token in (b'-0', b'-1', b'-999999999999999999', b'-1000000000000000000',
                      b'-9223372036854775808', b'-9223372036854775809',
                      b'10000000000000000000', b'18446744073709551615',
                      b'18446744073709551616', b'9' * 100,
                      b'0.0', b'-0.0', b'1.0', b'1.25', b'1e-7', b'1E-7',
                      b'1e+21', b'5e-324', b'1e-6', b'1.7976931348623157e+308'):
            with self.subTest(token=token):
                self.fallback(b'{"a":' + token + b'}')
        self.assertEqual(self.parse(b'{"a":18446744073709551615}'),
                         {'a': (1 << 64) - 1})
        with self.assertRaisesRegex(ValueError, '^integer is outside the JCS-I64-v1 domain$'):
            self.parse(b'{"a":18446744073709551616}')

    def test_safe_integer_boundaries_use_fast_path(self):
        for number in (0, 1, 10**18 - 1, 10**18, (1 << 63) - 1, 10**19 - 1):
            raw = ('{"a":' + str(number) + '}').encode('ascii')
            original = Mock(side_effect=AssertionError('safe integer fell back'))
            with self.subTest(number=number):
                self.assertEqual(fast.bind_parse(original)(raw), {'a': number})
                original.assert_not_called()
                self.parity(raw)

    def test_container_budget_counts_all_containers_and_masks_string_contents(self):
        for count in (127, 128, 129):
            for raw in (b'{"a":' + b'[' * (count - 1) + b'0' + b']' * (count - 1) + b'}',
                        b'{"a":[' + b','.join([b'{}'] * (count - 2)) + b']}'):
                with self.subTest(count=count, prefix=raw[:20]):
                    if count <= 128:
                        original = Mock(side_effect=AssertionError('budget boundary fell back'))
                        self.parity(raw, fast.bind_parse(original))
                        original.assert_not_called()
                    else:
                        self.fallback(raw)
        for depth in (200, 2000):
            self.fallback(b'{"a":' + b'[' * depth + b'0' + b']' * depth + b'}')

    def test_unicode_utf16_order_escaped_keys_and_invalid_utf8_fall_back(self):
        for raw in ('{"a":"é😀"}'.encode(), '{"é":1}'.encode(),
                    '{"𐀀":1,"":2}'.encode(),
                    b'{"a":"\\u00e9"}', b'{"\\u00e9":1}',
                    b'{"\\ud800\\udc00":1,"\\ue000":2}',
                    b'{"\\ue000":2,"\\ud800\\udc00":1}',
                    b'{"a":"\\ud800"}', b'{"\\udfff":1}',
                    b'{"a":"\xff"}', b'{"a":"\xc0\xaf"}',
                    b'{"a":"\xed\xa0\x80"}', b'{"a":"\xf0\x80\x80\x80"}',
                    b'\xef\xbb\xbf{}', b'\xff\xfe{\x00}\x00'):
            with self.subTest(raw=raw):
                self.fallback(raw)

    def test_nonbytes_and_subclasses_are_delegated_without_inspection(self):
        class Bytes(bytes):
            def isascii(self):
                raise AssertionError('subclass inspected')
        class Text(str):
            pass
        for raw in (Bytes(b'{}'), bytearray(b'{}'), memoryview(b'{}'),
                    '{}', Text('{}'), None, 1, {}, []):
            with self.subTest(kind=type(raw).__name__):
                marker = object()
                original = Mock(return_value=marker)
                self.assertIs(fast.bind_parse(original)(raw), marker)
                original.assert_called_once()
                self.assertIs(original.call_args.args[0], raw)
                self.fallback(raw)

    def test_binding_is_explicit_independent_and_does_not_patch_archive(self):
        original_parse, original_canonical = archive.parse_json, archive.canonical
        first, second = Mock(return_value={'first': 1}), Mock(return_value={'second': 2})
        parse_first, parse_second = fast.bind_parse(first), fast.bind_parse(second)
        self.assertEqual(parse_first(b' []'), {'first': 1})
        self.assertEqual(parse_second(b' []'), {'second': 2})
        self.assertEqual(parse_first(b' []'), {'first': 1})
        self.assertEqual(first.call_count, 2)
        second.assert_called_once_with(b' []')
        self.assertIs(archive.parse_json, original_parse)
        self.assertIs(archive.canonical, original_canonical)

    def test_repeated_inputs_return_independent_trees_without_semantic_cache(self):
        raw = b'{"a":[{"b":1}]}'
        first = self.parse(raw)
        first['a'][0]['b'] = 7
        self.assertEqual(self.parse(raw), {'a': [{'b': 1}]})
        original = Mock(wraps=archive.parse_json)
        parse = fast.bind_parse(original)
        for _ in range(3):
            self.assertEqual(parse(b'{"a":-1}'), {'a': -1})
        self.assertEqual(original.call_count, 3)

    def test_fast_exceptions_delegate_once_and_preserve_original_exception_identity(self):
        for operation in ('loads', 'dumps'):
            for failure in (ValueError('speculative failure'), RecursionError('depth'),
                            OverflowError('overflow'), MemoryError('allocation')):
                error = archive.ArchiveError('original failure')
                original = Mock(side_effect=error)
                with self.subTest(operation=operation, failure=type(failure)), \
                        patch.object(fast.json, operation, side_effect=failure), \
                        self.assertRaises(archive.ArchiveError) as caught:
                    fast.bind_parse(original)(b'{}')
                self.assertIs(caught.exception, error)
                self.assertIsNone(error.__context__)
                original.assert_called_once_with(b'{}')

    def test_shared_jcs_fixtures_wrapped_as_objects_and_canonical_forms(self):
        fixture = json.loads((ROOT / 'tests/fixtures/jcs_i64_v1.json').read_bytes())
        for case in fixture['cases']:
            with self.subTest(case=case['name']):
                self.parity(('{"value":' + case['input'] + '}').encode())
                self.parity(('{"value":' + case['canonical'] + '}').encode())

    def test_2000_deterministic_targeted_random_cases(self):
        rng = random.Random(253)
        leaves = [None, False, True, 0, 1, -1, -(1 << 63), -(1 << 63) - 1,
                  (1 << 63) - 1, 10**19 - 1, 10**19, (1 << 64) - 1, 1 << 64,
                  '', '\x00\\"', 'é😀', '\ud800', 0.0, -0.0, 1.25, 1e-7,
                  1e21, float('inf'), float('nan'), '{[ -12345678901234567890 1e2 ]}']
        keys = ['', 'a', 'A', 'z', '0', '\x00', '\\"', 'é', '\U00010000', '\ue000']

        def tree(depth):
            choice = rng.randrange(4) if depth else 0
            if choice < 2:
                return rng.choice(leaves)
            if choice == 2:
                return [tree(depth - 1) for _ in range(rng.randrange(4))]
            return {rng.choice(keys): tree(depth - 1) for _ in range(rng.randrange(4))}

        for case in range(2000):
            value = {rng.choice(keys): tree(4) for _ in range(rng.randrange(5))}
            mode = case % 10
            if mode == 0:
                # Guaranteed canonical fast-domain objects in every random batch.
                value = {'a': rng.randrange(10**19), 's': rng.choice(keys[:7]),
                         'z': [rng.randrange(1000), None, bool(rng.randrange(2))]}
            raw = json.dumps(value, sort_keys=bool(rng.randrange(2)),
                             separators=(',', ':') if mode != 1 else (', ', ': '),
                             ensure_ascii=True).encode('ascii')
            if mode == 2:
                raw = b'{"duplicate":0,"duplicate":1,"nested":' + raw + b'}'
            elif mode == 3:
                raw = b'{"a":' + rng.choice([
                    b'-0', b'-9223372036854775809', b'18446744073709551616',
                    b'NaN', b'Infinity', b'1e9999', b'01', b'1e+', b'5e-324']) + b'}'
            elif mode == 4:
                position = rng.randrange(len(raw) + 1)
                raw = raw[:position] + rng.choice([b'\xff', b'\x00', b'\\', b',', b'"']) + raw[position:]
            elif mode == 5:
                raw = raw[:rng.randrange(len(raw))]
            elif mode == 6:
                raw = rng.choice([b' ', b'\n', b'\xef\xbb\xbf']) + raw
            elif mode == 7:
                raw = b'{"a":[' + b','.join([b'{}'] * rng.randrange(125, 135)) + b']}'
            elif mode == 8:
                raw = b'{"a":0,"\\u0061":1,"nested":' + raw + b'}'
            with self.subTest(case=case, mode=mode):
                self.parity(raw)


if __name__ == '__main__':
    unittest.main()
