"""D261 allocation bounds, original grammar and independent science integration."""
import contextlib
import hashlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
import stage17_formal_control_reader_v1 as reader
from test_stage17_formal_service_capture_validation_v1 import Fixture


def plan_parts():
    capture = dict(method_id='SERVICE-RATE-NP-LTL95C95-MIN-v1', geometry=dict(base_page_bytes=4096))
    resources = dict(region_bytes=[4096]*7, workers={key:dict(bytes=4096)
        for key in ('producer_stack', 'consumer_stack')}, core_bytes=4096, controller_stack=dict(bytes=4096))
    monitoring = dict(during_first_page=[0]*7, during_page_count=[1]*7)
    return capture, resources, monitoring


def parse(raw, capacity):
    with contextlib.ExitStack() as stack:
        return reader.reader_type(capacity)(io.StringIO(raw), stack).document()


class ReaderTests(unittest.TestCase):
    def test_exact_plan_capacity_charges_all_84_arrays_and_slack(self):
        c,r,m = plan_parts()
        self.assertEqual(reader.packed_capacity(c,r,m), 84*65536)
        r['region_bytes'][0] = (8192+1)*4096
        self.assertEqual(reader.packed_capacity(c,r,m), 92*65536)
        m['during_page_count'][0] = 8193
        self.assertEqual(reader.packed_capacity(c,r,m), 96*65536)

    def test_real_signed_e26_page_counts_require_more_than_original_cap(self):
        # Independent diagnostic's actual seven-region page counts, not invented hardware.
        diagnosis = json.loads((pathlib.Path(__file__).resolve().parents[1]/
            'docs/evidence/stage17/Q16B-PREFIX-RECOVERY-20261116-01/reader-capacity-diagnosis.json').read_bytes())
        for row in diagnosis['rows']:
            # The historical diagnosis appended four regions already included
            # by region_bytes. Check the actual seven, retain that history.
            c,r,m = plan_parts();pages=row['region_pages'][:7]
            r['region_bytes'] = [n*4096 for n in pages]
            for key,n in zip(('producer_stack','consumer_stack'),pages[3:5],strict=True):r['workers'][key]['bytes']=n*4096
            r['core_bytes'],r['controller_stack']['bytes'] = (n*4096 for n in pages[5:])
            capacity = reader.packed_capacity(c,r,m)
            self.assertEqual(capacity,row['required_rounded_packed_capacity_bytes']-4*8*65536)
            self.assertGreater(capacity,reader.common.MAX_PACKED_PAGE_BYTES)
            self.assertLessEqual(capacity,512*1024**2)

    def test_before_allocation_rejects_next_block_without_mutating_other_readers(self):
        original = reader.common.MAX_PACKED_PAGE_BYTES
        packed_method = reader.common.JsonReader.packed_pages
        one,two = reader.reader_type(65536),reader.reader_type(131072)
        raw='{"page_addresses":[0],"page_status":[-5]}'
        with contextlib.ExitStack() as stack:
            first=one(io.StringIO(raw),stack)
            with self.assertRaisesRegex(reader.common.ValidationError,'cumulative packed'):
                first.document()
            self.assertEqual(first.packed_bytes,65536)
            second=two(io.StringIO(raw),stack);result=second.document()
            self.assertEqual(second.packed_bytes,131072)
            self.assertEqual(list(result['page_status']),[-5])
            self.assertIsInstance(result['page_addresses'],reader.common.PackedPages)
        self.assertEqual(reader.common.MAX_PACKED_PAGE_BYTES,original)
        self.assertIs(reader.common.JsonReader.packed_pages,packed_method)
        self.assertIs(one.packed_pages.__code__,packed_method.__code__)

    def test_unchanged_signed_unsigned_integer_boundaries_and_grammar(self):
        result=parse('{"page_addresses":[0,18446744073709551615],"page_status":[-9223372036854775808,9223372036854775807]}',131072)
        self.assertEqual(list(result['page_addresses']),[0,(1<<64)-1])
        self.assertEqual(list(result['page_status']),[-(1<<63),(1<<63)-1])
        for raw in ('{"page_addresses":[-1]}','{"page_status":[9223372036854775808]}',
                    '{"page_status":[-9223372036854775809]}','{"page_addresses":[18446744073709551616]}',
                    '{"page_status":[true]}','{"page_status":[1.0]}','{"page_status":[01]}',
                    '{"x":1,"x":2}','{"page_status":[1,]}','{"x":1} trailing',
                    '{"drain_rows":[]}'):
            with self.subTest(raw=raw),self.assertRaises((ValueError,reader.common.ValidationError)):
                parse(raw,131072)

    def test_rejects_unbounded_invalid_and_out_of_region_declarations(self):
        for value in (True,0,-1,65535,512*1024**2+65536,1.0):
            with self.subTest(value=value),self.assertRaises(reader.common.ValidationError):reader.reader_type(value)
        for mutate in (lambda c,r,m:r['region_bytes'].pop(),
                       lambda c,r,m:r['region_bytes'].__setitem__(0,4097),
                       lambda c,r,m:m['during_page_count'].__setitem__(0,2),
                       lambda c,r,m:m['during_first_page'].__setitem__(0,-1),
                       lambda c,r,m:m['during_page_count'].__setitem__(0,True),
                       lambda c,r,m:r['region_bytes'].__setitem__(0,1<<63)):
            c,r,m=plan_parts();mutate(c,r,m)
            with self.subTest(mutate=mutate),self.assertRaises(reader.common.ValidationError):reader.packed_capacity(c,r,m)

    def test_real_control_readback_and_unchanged_scientific_validator(self):
        with tempfile.TemporaryDirectory() as temporary:
            f=Fixture(pathlib.Path(temporary),full=True)
            expected=f.run()
            raw=json.dumps(f.control,separators=(',',':')).encode()
            p=pathlib.Path(temporary)/'control.json';p.write_bytes(raw)
            logical=dict(file_name=p.name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
            with reader.control(p.parent,logical,capture=f.capture,resources=f.resources,monitoring=f.monitoring) as control:
                actual=__import__('stage17_formal_service_capture_validation_v1').validate_capture(
                    f.root,control,f.final,f.capture,f.resources,f.monitoring,f.hardware)
            self.assertEqual(actual,expected)
            self.assertFalse(actual['measurement_zero_loss'])
            self.assertFalse(actual['family_validity_established'])
            p.write_bytes(raw+b' ')
            with self.assertRaises(reader.common.ValidationError):
                with reader.control(p.parent,logical,capture=f.capture,resources=f.resources,monitoring=f.monitoring):pass

    def test_original_child_reader_selection_preserves_valid_and_failed_envelopes(self):
        import types
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=pathlib.Path(temporary.name);raw=b'{"page_addresses":[123],"page_status":[-5]}'
        (root/'control.json').write_bytes(raw)
        c,r,m=plan_parts();job=dict(item=dict(capture=c,resources=r,monitoring=m),root=root,
            logical=dict(file_name='control.json',size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
        # Real bytecode cloning seam; the production original body is separately
        # authenticated. No substitution of the packed reader or fake proof.
        scope=dict(common=reader.common,control=lambda *_: (_ for _ in ()).throw(AssertionError('old reader selected')))
        exec('def child(connection,job,profile,limits,hardware,cpu,deadline):\n'
             ' with control(common,job["root"],job["logical"]) as document:\n'
             '  connection.send(dict(status=hardware,ordinal=6,pages=list(document["page_status"])))\n'
             ' connection.close()\n',scope)
        original=scope['child']
        for status in ('VALID','FAILED'):
            sent=[];closed=[]
            pipe=types.SimpleNamespace(send=sent.append,close=lambda:closed.append(True))
            reader.analysis_child(pipe,job,None,None,status,None,None,original_child=original)
            self.assertEqual(sent[0]['status'],status)
            self.assertEqual(sent[0]['ordinal'],6)
            self.assertEqual(sent[0]['pages'],[-5])
            self.assertEqual(sent[0]['control_reader']['packed_capacity_bytes'],84*65536)
            self.assertEqual(closed,[True])
        self.assertIs(scope['child'],original)


if __name__=='__main__':unittest.main()
