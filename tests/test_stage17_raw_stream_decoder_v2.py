"""Independent byte fixtures for accepted D211; no native or stand execution."""
from __future__ import annotations
import copy
import hashlib
import json
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_raw_stream_decoder_v1 as legacy
import stage17_raw_stream_decoder_v2 as decoder


class Fixture:
    """Hand-encode existing physical rows, with independently supplied event times.

    Tuples are (producer issue ps, consumer invocation ps, action completion ps).
    Each operation's intermediate boundaries equal its invocation; clock ties
    are valid. FULL rows use (issue ps, None, None).
    """
    def __init__(self, root, events=None, *, clock_origin=9007199254740993,
                 start=10000, duration=20000, run_id='D211X'):
        if events is None:
            events = [(10000, 10000, 10000), (11000, 11000, 29000),
                      (12000, 29000, 30000), (13000, 30000, 31000)]
        self.root, self.run_id = root, run_id
        encoded = run_id.encode('utf-8')
        self.prefix = struct.pack('<I', len(encoded)) + encoded + b'\0' * ((-4-len(encoded)) % 8)
        self.rows = dict(producer=[], consumer=[], joined=[])
        accepted = 0
        for logical, (issue, begin, finish) in enumerate(events):
            absolute_issue = clock_origin + issue // 1000
            full = begin is None
            self.rows['producer'].append([
                logical, logical % 2, issue, absolute_issue, issue, absolute_issue, issue,
                absolute_issue, issue, 0 if full else absolute_issue, 0 if full else issue,
                absolute_issue, issue, 0 if full else accepted, 1 if full else 15])
            if full:
                continue
            self.rows['consumer'].append([
                accepted, logical % 2, clock_origin + begin // 1000, begin,
                clock_origin + begin // 1000, begin, clock_origin + begin // 1000, begin,
                clock_origin + finish // 1000, finish])
            self.rows['joined'].append([
                accepted, logical, logical % 2, logical, accepted,
                issue, issue, issue, issue, issue, issue, begin, begin, begin, finish,
                0, 0, 0, 0, begin-issue, 0, finish-begin, finish-begin, finish-issue])
            accepted += 1
        self.contract = dict(
            schema_version='cpu-prefetch-stage17-raw-stream-contract/2', run_id=run_id,
            physical_format='RAW-OBS-U64LE-LP-RUNID-v1', streams={},
            measurement_window=dict(clock_suite_id='LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1',
                time_unit='PICOSECONDS', ticks_per_second=1_000_000_000_000,
                clock_origin_absolute_nanoseconds=clock_origin,
                measurement_origin=dict(absolute_nanoseconds=clock_origin + start // 1000,
                                        relative_picoseconds=start), duration_ticks=duration))
        self.save()

    def save(self):
        for name, words in self.rows.items():
            data = b''.join(self.prefix + struct.pack('<' + 'Q'*len(row), *row) for row in words)
            path = self.root / (name + '.bin')
            path.write_bytes(data)
            self.contract['streams'][name] = dict(path=path.name, size_bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(), row_count=len(words))

    def rehash(self, name):
        binding = self.contract['streams'][name]
        data = (self.root / binding['path']).read_bytes()
        binding.update(size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())

    def run(self):
        return decoder.reconcile(self.root, self.contract)


class CompletionCounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)

    def test_start_end_crossing_and_drain_keep_full_join_total(self):
        fixture = Fixture(self.root)
        result = fixture.run()
        self.assertEqual(result['consumed_count'], 4)
        self.assertEqual(result['accepted_count'], 4)
        self.assertEqual(result['interval_consumed_count'], 2)
        self.assertEqual(result['outside_interval_consumed_count'], 2)
        self.assertEqual(result['interval_end_ticks'], 30000)
        self.assertEqual(result['join_status'], 'PASSED')
        self.assertEqual(result['schema_version'], 'cpu-prefetch-stage17-independent-raw-reconciliation/2')
        self.assertEqual(result['completion_counting_rule_id'], 'AMEND-2.0.0-pre.3-Q16B-INTERVAL-COMPLETIONS-v1')
        self.assertEqual(result['measurement_window'], fixture.contract['measurement_window'])
        self.assertFalse(result['execution_evidence_validated'])
        self.assertFalse(result['execution_authority'])
        self.assertEqual(result['n_eff_claimed'], None)
        # The very same bytes retain legacy full-stream reconciliation.
        old = {k:v for k,v in fixture.contract.items() if k != 'measurement_window'}
        old['schema_version'] = 'cpu-prefetch-stage17-raw-stream-contract/1'
        self.assertEqual(legacy.reconcile(self.root, old)['consumed_count'], 4)

    def test_valid_zero_interval_throughput_retains_drain(self):
        fixture = Fixture(self.root, [(10000, 10000, 30000), (11000, 30000, 31000)])
        result = fixture.run()
        self.assertEqual(result['interval_consumed_count'], 0)
        self.assertEqual(result['outside_interval_consumed_count'], 2)
        self.assertEqual(result['run_validity'], 'VALID')
        self.assertEqual(result['zero_loss_status'], 'PASS')

    def test_valid_full_and_empty_consumer_stream(self):
        fixture = Fixture(self.root, [(10000, None, None), (11000, None, None)])
        result = fixture.run()
        self.assertEqual((result['offered_count'], result['full_count'], result['consumed_count']), (2, 2, 0))
        self.assertEqual(result['interval_consumed_count'], 0)
        self.assertEqual(result['outside_interval_consumed_count'], 0)
        self.assertEqual(result['run_validity'], 'VALID')
        self.assertEqual(result['zero_loss_status'], 'FAIL')

    def test_full_row_does_not_shift_accepted_join_ordinals(self):
        fixture = Fixture(self.root, [(10000, 10000, 10000), (11000, None, None), (12000, 12000, 30000)])
        result = fixture.run()
        self.assertEqual((result['offered_count'], result['full_count'], result['accepted_count']), (3,1,2))
        self.assertEqual(result['interval_consumed_count'], 1)
        self.assertEqual(result['outside_interval_consumed_count'], 1)

    def test_exact_64_bit_absolute_and_relative_integers(self):
        start = 9007199254741000
        fixture = Fixture(self.root, [(start,start,start),(start+1000,start+1000,start+2000)],
                          clock_origin=9007199254740993,start=start,duration=2000)
        result = fixture.run()
        self.assertEqual(result['interval_consumed_count'],1)
        self.assertEqual(result['outside_interval_consumed_count'],1)
        self.assertEqual(result['interval_end_ticks'],9007199254743000)
        self.assertEqual(result['measurement_window']['clock_origin_absolute_nanoseconds'],9007199254740993)

    def test_unit_suite_and_strict_integer_negatives(self):
        mutants = [('clock_suite_id','CLOCK_REALTIME'),('time_unit','NANOSECONDS'),
                   ('ticks_per_second',10**9),('ticks_per_second',1e12),
                   ('clock_origin_absolute_nanoseconds',True),('duration_ticks',0),
                   ('duration_ticks',-1),('duration_ticks',20000.0),('duration_ticks',1<<64)]
        for key,value in mutants:
            fixture = Fixture(self.root)
            fixture.contract['measurement_window'][key] = value
            with self.subTest(key=key,value=value), self.assertRaises(decoder.DecodeError):fixture.run()
        for key in ('absolute_nanoseconds','relative_picoseconds'):
            fixture = Fixture(self.root)
            fixture.contract['measurement_window']['measurement_origin'][key] = True
            with self.assertRaises(decoder.DecodeError):fixture.run()

    def test_missing_and_forged_origin_bindings(self):
        for mutation in ('missing','clock_origin','origin_pair','before_rows'):
            fixture = Fixture(self.root)
            w = fixture.contract['measurement_window']
            if mutation=='missing':del w['measurement_origin']
            elif mutation=='clock_origin':w['clock_origin_absolute_nanoseconds'] += 1
            elif mutation=='origin_pair':w['measurement_origin']['relative_picoseconds'] += 1
            else:
                w['measurement_origin']['relative_picoseconds'] += 1000
                w['measurement_origin']['absolute_nanoseconds'] += 1
            with self.subTest(mutation=mutation), self.assertRaises(decoder.DecodeError):fixture.run()

    def test_endpoint_and_clock_conversion_overflow(self):
        fixture = Fixture(self.root)
        w = fixture.contract['measurement_window']
        w['duration_ticks'] = (1<<64)-1
        with self.assertRaisesRegex(decoder.DecodeError,'endpoint overflow'):fixture.run()
        fixture = Fixture(self.root,[],clock_origin=(1<<64)-1,start=0,duration=1000)
        with self.assertRaisesRegex(decoder.DecodeError,'absolute endpoint overflow'):fixture.run()
        fixture = Fixture(self.root)
        w = fixture.contract['measurement_window']
        w['clock_origin_absolute_nanoseconds'] = 0
        w['measurement_origin'] = dict(absolute_nanoseconds=(1<<64)-1,relative_picoseconds=1000)
        with self.assertRaisesRegex(decoder.DecodeError,'conversion mismatch/overflow'):fixture.run()

    def test_every_consumer_and_producer_clock_pair_checked(self):
        for name, indices in [('consumer',(2,4,6,8)),('producer',(3,5,7,9,11))]:
            for index in indices:
                fixture = Fixture(self.root)
                fixture.rows[name][0][index] += 1
                fixture.save()
                with self.subTest(name=name,index=index), self.assertRaisesRegex(decoder.DecodeError,'clock-domain'):
                    fixture.run()
        fixture=Fixture(self.root)
        fixture.rows['consumer'][0][2]=0;fixture.save()
        with self.assertRaisesRegex(decoder.DecodeError,'before clock origin'):fixture.run()

    def test_local_and_cross_row_order_even_with_matching_clock_pairs(self):
        fixture = Fixture(self.root)
        fixture.rows['consumer'][1][9]=10000
        fixture.rows['consumer'][1][8]=fixture.contract['measurement_window']['clock_origin_absolute_nanoseconds']+10
        fixture.save()
        with self.assertRaisesRegex(decoder.DecodeError,'timestamp order'):fixture.run()
        # Locally ordered consumer row starts before previous action completed.
        fixture = Fixture(self.root,[(10000,10000,20000),(11000,19000,21000)])
        with self.assertRaisesRegex(decoder.DecodeError,'cross-row'):fixture.run()
        fixture = Fixture(self.root,[(11000,11000,11000),(10000,12000,12000)])
        with self.assertRaisesRegex(decoder.DecodeError,'producer local/cross-row'):fixture.run()

    def test_pre_origin_consumer_is_not_hidden_as_outside(self):
        fixture = Fixture(self.root)
        fixture.rows['consumer'][0][2] = fixture.contract['measurement_window']['clock_origin_absolute_nanoseconds'] + 9
        fixture.rows['consumer'][0][3] = 9000
        fixture.save()
        with self.assertRaisesRegex(decoder.DecodeError,'timestamp order'):fixture.run()

    def test_raw_runid_length_padding_and_identity_headers(self):
        for name in ('producer','consumer','joined'):
            for offset in (0,4,len(Fixture(self.root).prefix)-1):
                fixture = Fixture(self.root)
                path=self.root/(name+'.bin');raw=bytearray(path.read_bytes());raw[offset] ^= 1;path.write_bytes(raw)
                fixture.rehash(name)
                with self.subTest(name=name,offset=offset),self.assertRaisesRegex(decoder.DecodeError,'run_id'):
                    fixture.run()

    def test_count_hash_size_and_role_bindings(self):
        for field,value in [('row_count',True),('row_count',5),('row_count',1<<64),
                            ('size_bytes',True),('size_bytes',1),('sha256','0'*64)]:
            fixture=Fixture(self.root);fixture.contract['streams']['consumer'][field]=value
            with self.subTest(field=field),self.assertRaises(decoder.DecodeError):fixture.run()
        fixture=Fixture(self.root);fixture.contract['run_id']='OTHER'
        with self.assertRaises(decoder.DecodeError):fixture.run()
        fixture=Fixture(self.root);fixture.contract['streams']['consumer']['path']='producer.bin'
        with self.assertRaisesRegex(decoder.DecodeError,'distinct paths'):fixture.run()

    def test_forged_join_ordinal_index_and_full_fields(self):
        for name,index in [('joined',23),('consumer',0),('consumer',1),('producer',0),('producer',13)]:
            fixture=Fixture(self.root);fixture.rows[name][0][index]+=1;fixture.save()
            with self.subTest(name=name,index=index),self.assertRaises(decoder.DecodeError):fixture.run()
        fixture=Fixture(self.root,[(10000,None,None)])
        fixture.rows['producer'][0][10]=10000;fixture.save()
        with self.assertRaisesRegex(decoder.DecodeError,'FULL'):fixture.run()

    def test_truncated_extra_and_symlink_streams(self):
        for change in ('truncate','extra','symlink','parent_symlink','traversal'):
            fixture=Fixture(self.root)
            path=self.root/'consumer.bin'
            if change=='truncate':path.write_bytes(path.read_bytes()[:-1])
            elif change=='extra':path.write_bytes(path.read_bytes()+b'x')
            elif change=='symlink':
                path.rename(self.root/'saved.bin');path.symlink_to(self.root/'saved.bin')
            elif change=='parent_symlink':
                directory=self.root/'link';directory.symlink_to(self.root,target_is_directory=True)
                fixture.contract['streams']['consumer']['path']='link/consumer.bin'
            else:fixture.contract['streams']['consumer']['path']='../consumer.bin'
            with self.subTest(change=change),self.assertRaises(decoder.DecodeError):fixture.run()
            if path.is_symlink():path.unlink()

    def test_legacy_file_hash_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT/'tools/stage17_raw_stream_decoder_v1.py').read_bytes()).hexdigest(),
                         '6a393bbd7c6721f715cd7b23c5a5c59368365ad3e77d950f2337d52089bfcab3')

    def test_cli_duplicate_contract_rejected_and_positive_output(self):
        fixture=Fixture(self.root)
        path=self.root/'contract.json';path.write_text(json.dumps(fixture.contract))
        command=[sys.executable,'-B',str(ROOT/'tools/stage17_raw_stream_decoder_v2.py'),
                 '--root',str(self.root),'--contract',str(path)]
        result=subprocess.run(command,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['interval_consumed_count'],2)
        path.write_text('{"schema_version":"x",'+path.read_text()[1:])
        result=subprocess.run(command,capture_output=True,check=False)
        self.assertEqual(result.returncode,1)
        self.assertIn(b'duplicate JSON key',result.stderr)


if __name__=='__main__':unittest.main()
