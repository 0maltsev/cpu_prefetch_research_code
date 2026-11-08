"""Reader software checks; no stand, decoded empirical claims or measurements."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import validate_prefix as v

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT/'tools'))
import stage17_discovery_validation_v3 as common


def small_item():
    return dict(capture={'geometry': {'base_page_bytes': 4096}},
                resources={'region_bytes': [4096]*7},
                monitoring={'during_page_count': [1]*7})


def observation():
    return {'residency': [{'page_addresses': [4096], 'page_status': [0]} for _ in range(42)]}


class ReaderTests(unittest.TestCase):
    def parse(self, document, item=None):
        with contextlib.ExitStack() as stack:
            reader = v.formal_reader(common, io.StringIO(json.dumps(document)), stack, item or small_item())
            return reader.document(), reader

    def test_exact_original_signed_formal_capacities(self):
        path = ROOT/'build/stage17-step5-prep/formal-q16a-authoring-v23-1/final-v23-1/plan.json'
        raw = path.read_bytes()
        self.assertEqual(v.sha(raw), v.PLAN_SHA)
        plan = json.loads(raw)
        for i, expected in ((0,387710976),(59,387710976),(118,388759552)):
            layout = v.packed_page_layout(plan['captures'][i])
            self.assertEqual(layout['packed_capacity_bytes'], expected)
            self.assertEqual(len(layout['array_counts']), 84)
            self.assertGreater(expected, common.MAX_PACKED_PAGE_BYTES)
            self.assertLess(expected, 512*1024**2)

    def test_real_packed_reader_and_unmodified_historical_global(self):
        before = common.MAX_PACKED_PAGE_BYTES
        with patch.object(common, 'MAX_PACKED_PAGE_BYTES', 65536):
            with contextlib.ExitStack() as stack:
                with self.assertRaisesRegex(common.ValidationError, 'cumulative packed page'):
                    common.JsonReader(io.StringIO(json.dumps(observation())), stack).document()
            actual, reader = self.parse(observation())
            self.assertEqual(common.MAX_PACKED_PAGE_BYTES, 65536)
        self.assertEqual(common.MAX_PACKED_PAGE_BYTES, before)
        self.assertEqual(reader.packed_bytes, 84*65536)
        self.assertEqual(list(actual['residency'][0]['page_addresses']), [4096])
        self.assertEqual(list(actual['residency'][0]['page_status']), [0])
        self.assertIsInstance(actual['residency'][0]['page_addresses'], common.PackedPages)

    def test_missing_expanded_and_wrong_length_arrays_fail(self):
        for mutation in ('missing', 'extra', 'wrong_count'):
            data = observation()
            if mutation == 'missing': data['residency'].pop()
            if mutation == 'extra': data['residency'].append(data['residency'][0])
            if mutation == 'wrong_count': data['residency'][0]['page_status'].append(0)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.parse(data)

    def test_numeric_range_and_type_checks_remain(self):
        for key, value in [('page_addresses',-1),('page_addresses',2**64),
                           ('page_status',2**63),('page_status',True),('page_status',1.0)]:
            data = observation(); data['residency'][0][key] = [value]
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                self.parse(data)

    def test_formal_drain_spool_bypass_rejected(self):
        data = observation(); data['drain_rows'] = []
        with self.assertRaisesRegex(ValueError, 'unexpected discovery drain'):
            self.parse(data)

    def test_declared_geometry_and_capacity_bounds(self):
        for mutation in ('unaligned','wrong_regions','during_overflow','large','noninteger'):
            item = small_item()
            if mutation == 'unaligned': item['resources']['region_bytes'][0] += 1
            if mutation == 'wrong_regions': item['resources']['region_bytes'].pop()
            if mutation == 'during_overflow': item['monitoring']['during_page_count'][0] = 2
            if mutation == 'large': item['resources']['region_bytes'] = [4096*20_000_000]*7
            if mutation == 'noninteger': item['resources']['region_bytes'][0] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                v.packed_page_layout(item)

    def test_adapter_retains_original_validation_callback(self):
        original = v._original_validate_spooled
        def fake(m, job):
            return formal_control(m.q16a_capture_validation_v1.common, 'root', 'logical')
        job = dict(item=small_item(), resources={'capture_as_bytes':8*1024**3})
        import types
        modules = types.SimpleNamespace(q16a_capture_validation_v1=types.SimpleNamespace(common=common))
        with (patch.object(v, '_original_validate_spooled', fake),
              patch.object(v, 'formal_control_bounded', return_value=73) as control):
            self.assertEqual(v.base.validate_spooled(modules, job), 73)
            control.assert_called_once_with(common, 'root', 'logical', item=job['item'])
            control.reset_mock()
            job['resources']['capture_as_bytes'] = 256*1024**2
            with self.assertRaisesRegex(ValueError, 'unchanged AS'):
                v.base.validate_spooled(modules, job)
            control.assert_not_called()
        self.assertIs(original.__globals__, vars(v.base))
        self.assertEqual(v.base.sha(Path(v.base_path).read_bytes()), v.BASE_SHA)


if __name__ == '__main__':
    unittest.main()
