"""Independent byte fixtures and full-sort oracles; no hardware/capture execution."""
from __future__ import annotations
import hashlib
import json
import pathlib
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import stage17_q16a_demand_decoder_v1 as decoder


class Fixture:
    def __init__(self, root, events=None, *, role='producer', phase='measurement',
                 start=10000, duration=10000, clock_origin=9007199254740993,
                 minimum=2, run_id='D212X'):
        # Events are explicit (outcome, acquire-before ps, acquire-after ps).
        if events is None:
            nonadvance = 1 if role == 'producer' else 2
            events = [(0,10000,11000),(nonadvance,12000,13000),(0,14000,15000),
                      (0,19000,22000),(nonadvance,22000,22000),
                      (0,23000,24000),(0,25000,26000)]
        self.root, self.path = root, root / 'arbitrary-name.bin'
        encoded = run_id.encode('utf-8')
        self.prefix = struct.pack('<I',len(encoded)) + encoded + bytes((-4-len(encoded)) % 8)
        self.rows = []
        advanced = 0
        for ordinal,(outcome,before,after) in enumerate(events):
            self.rows.append([ordinal,outcome,advanced if outcome == 0 else 0,
                              0,clock_origin+before//1000,before,
                              0,clock_origin+after//1000,after])
            advanced += outcome == 0
        self.contract = dict(schema_version='cpu-prefetch-stage17-q16a-demand-stream/1',
            physical_format='Q16A-DEMAND-U64LE-LP-RUNID-v1',
            method_id='RING-D2-RUNTAIL-LTL95C95-WINDOW-v2',run_id=run_id,role=role,phase=phase,
            phase_window=dict(clock_suite_id='LINUX-CLOCK-MONOTONIC-RAW-VDSO-PS-v1',
                time_unit='PICOSECONDS',ticks_per_second=10**12,
                clock_origin_absolute_nanoseconds=clock_origin,
                phase_origin=dict(absolute_nanoseconds=clock_origin+start//1000,
                                  relative_picoseconds=start),duration_ticks=duration),
            minimum_observations_per_series=None if phase == 'warmup' else minimum)
        self.save()

    def save(self):
        self.path.write_bytes(b''.join(self.prefix+struct.pack('<9Q',*row) for row in self.rows))
        self.bind()

    def bind(self):
        raw = self.path.read_bytes()
        self.contract['stream'] = dict(path=self.path.name,size_bytes=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),row_count=len(self.rows))

    def run(self):
        return decoder.decode(self.root,self.contract)


class DemandDecoderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)

    def test_start_crossing_end_drain_full_empty_and_all_advancing_ordinals(self):
        for role in ('producer','consumer'):
            f = Fixture(self.root,role=role)
            result = f.run()
            self.assertEqual(result['counts'],dict(attempted=7,advanced=5,
                full=2 if role=='producer' else 0,empty=2 if role=='consumer' else 0,
                eligible_demand=4,eligible_advanced=3,eligible_issue=2,outside_demand=3))
            self.assertEqual(result['demand_p999'],dict(count=4,rank=4,value_ticks=3000,retained_heap_items=1))
            self.assertEqual(result['issue_p001'],dict(count=2,rank=1,value_ticks=4000,retained_heap_items=1))
            self.assertEqual(result['phase_window'],f.contract['phase_window'])
            self.assertTrue(result['inferential_eligible'])
            self.assertFalse(result['primary_reconciliation_validated'])
            self.assertFalse(result['execution_evidence_validated'])
            self.assertFalse(result['execution_authority'])

    def test_demand_start_at_end_excluded_bracket_end_at_end_included(self):
        f = Fixture(self.root,[(0,10000,11000),(0,19000,20000),(0,20000,20000)],minimum=1)
        result = f.run()
        self.assertEqual(result['counts']['eligible_demand'],2)
        self.assertEqual(result['counts']['eligible_issue'],1)
        self.assertEqual(result['counts']['outside_demand'],1)
        self.assertEqual(result['demand_p999']['value_ticks'],1000)

    def test_independent_reference_full_sort_small_populations_and_rank_boundaries(self):
        rng = random.Random(212)
        for n in (2,3,10,999,1000,1001,2001):
            events=[];latencies=[];starts=[];tick=10000
            for i in range(n):
                latency=rng.randint(1,15)*1000
                outcome=0 if i%3 else 1
                events.append((outcome,tick,tick+latency));latencies.append(latency)
                if outcome==0:starts.append(tick)
                tick += latency+rng.randint(1,10)*1000
            if len(starts)<2:events[0]=(0,*events[0][1:]);starts.insert(0,10000)
            f=Fixture(self.root,events,minimum=1,duration=tick)
            result=f.run()
            issues=[b-a for a,b in zip(starts,starts[1:])]
            for key,values,p in (('demand_p999',latencies,999),('issue_p001',issues,1)):
                rank=(p*len(values)+999)//1000
                expected=sorted(values)[rank-1]
                self.assertEqual(result[key]['value_ticks'],expected,(n,key))
                self.assertEqual(result[key]['rank'],rank)
                self.assertEqual(result[key]['retained_heap_items'],min(rank,len(values)-rank+1))
            self.assertLess(len(json.dumps(result)),2500)

    def test_warmup_raw_only_zero_and_empty_do_not_infer_or_apply_minimum(self):
        for events in ([],[(0,10000,10000),(1,20000,20000)]):
            result=Fixture(self.root,events,phase='warmup').run()
            self.assertFalse(result['inferential_eligible'])
            self.assertIsNone(result['demand_p999'])
            self.assertIsNone(result['issue_p001'])
            self.assertIsNone(result['minimum_observations_per_series'])
            self.assertEqual(result['counts']['attempted'],len(events))
            self.assertEqual(result['counts']['outside_demand'],1 if events else 0)

    def test_schema_is_valid_and_fixtures_have_phase_minimum_parity(self):
        schema=json.loads((ROOT/'config/schemas/stage17-q16a-demand-stream-v1.schema.json').read_bytes())
        Draft202012Validator.check_schema(schema)
        validator=Draft202012Validator(schema)
        for phase in ('warmup','measurement'):
            f=Fixture(self.root,phase=phase)
            validator.validate(f.contract);f.run()
            bad_values=(1,False,0,-1) if phase=='warmup' else (None,False,0,-1,1<<64)
            for value in bad_values:
                f.contract['minimum_observations_per_series']=value
                with self.subTest(phase=phase,value=value):
                    self.assertTrue(list(validator.iter_errors(f.contract)))
                    with self.assertRaises(decoder.DecodeError):f.run()

    def test_minimum_applies_to_both_sequences_without_partial_summary(self):
        for events,minimum in (([],1),([(0,10000,11000)],1),
                               ([(1,10000,11000),(1,12000,13000)],1),
                               ([(0,10000,11000),(0,12000,13000)],2),
                               ([(0,20000,21000),(0,22000,23000)],1)):
            with self.subTest(events=events),self.assertRaisesRegex(decoder.DecodeError,'insufficient'):
                Fixture(self.root,events,minimum=minimum).run()

    def test_eligible_zero_is_invalid_not_filtered(self):
        f=Fixture(self.root,[(0,10000,10000),(0,12000,13000)],minimum=1)
        with self.assertRaisesRegex(decoder.DecodeError,'nonpositive'):f.run()

    def test_all_rows_validate_clock_status_conversion_and_order_even_drain(self):
        for phase in ('measurement','warmup'):
            for row_index in (0,6):
                for word,value in ((3,1),(6,1),(4,0),(7,0),(5,1),(8,1)):
                    f=Fixture(self.root,phase=phase);f.rows[row_index][word]=value;f.save()
                    with self.subTest(phase=phase,row=row_index,word=word),self.assertRaises(decoder.DecodeError):f.run()
            f=Fixture(self.root,phase=phase)
            origin=f.contract['phase_window']['clock_origin_absolute_nanoseconds']
            f.rows[6][4:6]=[origin+23,23000];f.save()
            with self.assertRaisesRegex(decoder.DecodeError,'bracket order'):f.run()
            f=Fixture(self.root,phase=phase)
            f.rows[0][4:6]=[origin+9,9000];f.save()
            with self.assertRaisesRegex(decoder.DecodeError,'before released origin'):f.run()

    def test_attempt_advancing_identity_nonadvance_and_role_outcomes(self):
        for index,word,value in ((0,0,1),(6,0,8),(6,2,1),(1,2,1),(4,2,1),(6,1,3),(0,1,2)):
            f=Fixture(self.root);f.rows[index][word]=value;f.save()
            with self.subTest(index=index,word=word),self.assertRaises(decoder.DecodeError):f.run()
        f=Fixture(self.root,role='consumer');f.rows[1][1]=1;f.save()
        with self.assertRaisesRegex(decoder.DecodeError,'wrong-role'):f.run()

    def test_strict_window_units_origin_conversion_and_overflow(self):
        for field,value in (('duration_ticks',0),('duration_ticks',True),('duration_ticks',1.0),
                            ('duration_ticks',(1<<64)-1),('clock_origin_absolute_nanoseconds',True),
                            ('ticks_per_second',1e12),('time_unit','NANOSECONDS'),('clock_suite_id','wrong')):
            f=Fixture(self.root);f.contract['phase_window'][field]=value
            with self.subTest(field=field,value=value),self.assertRaises(decoder.DecodeError):f.run()
        f=Fixture(self.root);f.contract['phase_window']['phase_origin']['relative_picoseconds']+=1
        with self.assertRaisesRegex(decoder.DecodeError,'conversion'):f.run()
        f=Fixture(self.root,[],phase='warmup',clock_origin=(1<<64)-1,start=0,duration=1000)
        with self.assertRaisesRegex(decoder.DecodeError,'absolute endpoint overflow'):f.run()
        f=Fixture(self.root);f.contract['phase_window']['phase_origin']=dict(absolute_nanoseconds=(1<<64)-1,relative_picoseconds=1000)
        with self.assertRaisesRegex(decoder.DecodeError,'conversion'):f.run()

    def test_exact_64bit_clock_and_rank_math(self):
        start=9007199254741000
        f=Fixture(self.root,[(0,start,start+1000),(0,start+2000,start+4000)],start=start,minimum=1,duration=5000)
        result=f.run()
        self.assertEqual(result['phase_window']['phase_origin']['relative_picoseconds'],start)
        self.assertEqual(result['demand_p999']['value_ticks'],2000)
        for n in (1,999,1000,1001,(1<<64)-1):
            for p in (1,999):self.assertEqual(decoder.exact_rank(n,p,1000),(n*p+999)//1000)

    def test_raw_headers_padding_hash_size_count_and_explicit_identity(self):
        for offset in (0,4,15):
            f=Fixture(self.root);data=bytearray(f.path.read_bytes());data[offset]^=1;f.path.write_bytes(data);f.bind()
            with self.assertRaisesRegex(decoder.DecodeError,'run_id'):f.run()
        for key,value in (('sha256','0'*64),('row_count',True),('row_count',8),('row_count',1<<64),('size_bytes',1)):
            f=Fixture(self.root);f.contract['stream'][key]=value
            with self.subTest(key=key),self.assertRaises(decoder.DecodeError):f.run()
        for key,value in (('run_id','OTHER'),('run_id',''),('phase','unknown'),('role','unknown'),('method_id','v1'),('physical_format','RAW-OBS-U64LE-LP-RUNID-v1')):
            f=Fixture(self.root);f.contract[key]=value
            with self.subTest(key=key),self.assertRaises(decoder.DecodeError):f.run()

    def test_no_symlink_traversal_truncation_or_extra_bytes(self):
        for mutation in ('symlink','parent_link','traverse','short','extra'):
            f=Fixture(self.root)
            if mutation=='symlink':f.path.rename(self.root/'old');f.path.symlink_to(self.root/'old')
            elif mutation=='parent_link':
                (self.root/'link').symlink_to(self.root,target_is_directory=True)
                f.contract['stream']['path']='link/'+f.path.name
            elif mutation=='traverse':f.contract['stream']['path']='../'+f.path.name
            else:f.path.write_bytes(f.path.read_bytes()[:-1] if mutation=='short' else f.path.read_bytes()+b'x')
            with self.subTest(mutation=mutation),self.assertRaises(decoder.DecodeError):f.run()
            if f.path.is_symlink():f.path.unlink()

    def test_both_passes_verify_original_hash_and_detect_between_pass_change(self):
        f=Fixture(self.root);original=decoder.raw._HashedStream.finish;seen=[]
        def finish(stream):
            original(stream);seen.append(stream.digest.hexdigest())
        with patch.object(decoder.raw._HashedStream,'finish',finish):f.run()
        self.assertEqual(seen,[f.contract['stream']['sha256']]*2)
        original_tail=decoder._Tail
        def changed_tail(count,numerator):
            if numerator==999:
                data=bytearray(f.path.read_bytes());data[-8]^=1;f.path.write_bytes(data)
            return original_tail(count,numerator)
        with patch.object(decoder,'_Tail',changed_tail),self.assertRaises(decoder.DecodeError):f.run()

    def test_legacy_codec_bytes_unchanged_and_cli_duplicate_rejection(self):
        self.assertEqual(hashlib.sha256((ROOT/'tools/stage17_raw_stream_decoder_v1.py').read_bytes()).hexdigest(),
                         '6a393bbd7c6721f715cd7b23c5a5c59368365ad3e77d950f2337d52089bfcab3')
        f=Fixture(self.root);path=self.root/'contract.json';path.write_text(json.dumps(f.contract))
        command=[sys.executable,'-B',str(ROOT/'tools/stage17_q16a_demand_decoder_v1.py'),
                 '--root',str(self.root),'--contract',str(path)]
        result=subprocess.run(command,capture_output=True,check=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['demand_p999']['value_ticks'],3000)
        insufficient=dict(f.contract,minimum_observations_per_series=5)
        path.write_text(json.dumps(insufficient))
        result=subprocess.run(command,capture_output=True,check=False)
        self.assertEqual(result.returncode,1)
        self.assertEqual(result.stdout,b'')
        self.assertIn(b'insufficient',result.stderr)
        path.write_text('{"phase":"measurement",'+json.dumps(f.contract)[1:])
        result=subprocess.run(command,capture_output=True,check=False)
        self.assertEqual(result.returncode,1)
        self.assertEqual(result.stdout,b'')
        self.assertIn(b'duplicate JSON key',result.stderr)


if __name__=='__main__':unittest.main()
