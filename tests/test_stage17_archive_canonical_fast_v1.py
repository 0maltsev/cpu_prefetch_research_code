"""Byte/error parity with original JCS-I64-v1; no experimental observations."""
import json
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_canonical as original
import stage17_archive_canonical_fast_v1 as fast


class CanonicalTests(unittest.TestCase):
    def parity(self, value):
        try:
            expected = original.canonicalize(value).encode('utf-8')
        except Exception as error:
            with self.assertRaises(type(error)) as caught:
                fast.canonical(value)
            # Recursion limits depend on the extra caller frame, not bytes.
            if not isinstance(error, RecursionError):
                self.assertEqual(str(caught.exception), str(error))
        else:
            self.assertEqual(fast.canonical(value), expected)

    def fallback(self, value):
        self.parity(value)
        with patch.object(original, 'canonicalize', return_value='original-fallback') as called:
            self.assertEqual(fast.canonical(value), b'original-fallback')
            called.assert_called_once_with(value)

    def test_all_shared_jcs_fixtures(self):
        suite = json.loads((ROOT / 'tests/fixtures/jcs_i64_v1.json').read_bytes())
        self.assertEqual(suite['suite'], 'JCS-I64-v1')
        self.assertTrue(suite['cases'])
        for case in suite['cases']:
            with self.subTest(case=case['name']):
                value = json.loads(case['input'])
                self.assertEqual(fast.canonical(value), case['canonical'].encode('utf-8'))
                self.parity(value)

    def test_builtin_tree_uses_single_dump_without_original(self):
        value = {'z': [None, False, True, -7, (1 << 64) - 1], 'a': {'text': 'é😀'}}
        expected = '{"a":{"text":"é😀"},"z":[null,false,true,-7,18446744073709551615]}'.encode()
        with patch.object(original, 'canonicalize', side_effect=AssertionError('unexpected fallback')), \
             patch.object(fast.json, 'dumps', wraps=json.dumps) as dumps:
            self.assertEqual(fast.canonical(value), expected)
            dumps.assert_called_once_with(value, sort_keys=True, separators=(',', ':'),
                ensure_ascii=False, allow_nan=False)

    def test_independent_ascii_order_escaping_and_unicode_value(self):
        value = {'z': '\b\t\n\f\r\x00\\"/é😀', 'a': 2, 'A': 1, '': None}
        expected = '{"":null,"A":1,"a":2,"z":"\\b\\t\\n\\f\\r\\u0000\\\\\\"/é😀"}'.encode()
        self.assertEqual(fast.canonical(value), expected)

    def test_utf16_astral_key_order_and_surrogate_errors_use_original(self):
        value = {'\ue000': 3, '\U00010000': 2, '\r': 1}
        self.assertEqual(fast.canonical(value), '{"\\r":1,"𐀀":2,"":3}'.encode())
        self.fallback(value)
        for value in ('\ud800', '\udfff', {'key': '\ud800'}, {'\ud800': 1}):
            with self.subTest(value=repr(value)):
                self.parity(value)

    def test_integer_bounds_and_bool(self):
        for value in (-(1 << 63), (1 << 63) - 1, 1 << 63, (1 << 64) - 1, True, False):
            with self.subTest(value=value):
                self.parity(value)
        for value in (-(1 << 63) - 1, 1 << 64, {'nested': [1 << 100]}):
            self.fallback(value)

    def test_float_zero_exponents_and_nonfinite_preserve_original(self):
        for value in (0.0, -0.0, 1.0, 1e-7, 1e-6, 1e20, 1e21, -1.23e30,
                      5e-324, float('inf'), float('-inf'), float('nan'), {'x': [1.25]}):
            with self.subTest(value=repr(value)):
                self.fallback(value)
        self.assertEqual(fast.canonical(-0.0), b'0')
        self.assertEqual(fast.canonical(1e21), b'1e+21')

    def test_subclasses_unsupported_types_and_nonstring_keys_use_original(self):
        class Integer(int):
            def __str__(self): return '17'
        class Text(str): pass
        class Array(list): pass
        class Object(dict): pass
        for value in (Integer(3), Text('x'), Array([1]), Object(a=1),
                      {Text('key'): 1}, {1: 'bad key'}, {None: 1}, {True: 1},
                      (1, 2), {1, 2}, b'bytes', object()):
            with self.subTest(kind=type(value).__name__):
                self.fallback(value)

    def test_shared_containers_cycles_and_depth_limit(self):
        shared = {'leaf': 1}
        self.fallback([shared, shared])
        empty = []
        self.fallback({'a': empty, 'b': empty})
        cycle = []
        cycle.append(cycle)
        self.fallback(cycle)
        cycle_dict = {}
        cycle_dict['self'] = cycle_dict
        self.fallback(cycle_dict)
        value = 1
        for _ in range(fast.MAX_DEPTH): value = [value]
        self.parity(value)
        with patch.object(original, 'canonicalize', side_effect=AssertionError('depth boundary fallback')):
            self.assertEqual(fast.canonical(value), ('[' * 128 + '1' + ']' * 128).encode())
        self.fallback([value])

    def test_2000_deterministic_nested_mixed_cases(self):
        rng = random.Random(252)
        leaves = [None, False, True, 0, -1, -(1 << 63), (1 << 64) - 1,
                  -(1 << 63) - 1, 1 << 64, '', '\x00\\"', 'é😀', '\ud800',
                  0.0, -0.0, 1e-7, 1e21, float('inf'), float('nan'), b'bad', (1,)]
        keys = ['', 'a', 'A', 'z', '0', '\x00', 'é', '\U00010000', '\ue000', '\ud800', 1, None]
        def tree(depth):
            choice = rng.randrange(5) if depth else 0
            if choice < 2: return rng.choice(leaves)
            if choice == 2: return [tree(depth - 1) for _ in range(rng.randrange(5))]
            return {rng.choice(keys): tree(depth - 1) for _ in range(rng.randrange(5))}
        for case in range(2000):
            with self.subTest(case=case):
                self.parity(tree(5))


if __name__ == '__main__':
    unittest.main()
