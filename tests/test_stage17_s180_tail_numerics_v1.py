"""Independent direct-rational oracle against sparse D346 arithmetic.

All series are explicit synthetic software values, not CPU measurements.
"""
import array
import copy
from fractions import Fraction
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import stage17_s180_tail_numerics_v1 as tail


def frac(value):
    return None if value is None else Fraction(int(value['numerator_decimal']),int(value['denominator_decimal']))


def reference(bits):
    """Direct centered-products covariance; no pair histogram or production math."""
    n=len(bits);k=sum(bits)
    if not n or k in (0,n):return None
    mean=Fraction(k,n);centered=[Fraction(x)-mean for x in bits]
    variance=sum(x*x for x in centered)
    rho=[];below=0;h=None;stop=None;positive=0;total=Fraction(0)
    for lag in range(n):
        value=sum(centered[i]*centered[i+lag] for i in range(n-lag))/variance;rho.append(value)
        if h is None and lag>0:
            below=below+1 if n*value*value<Fraction(49,25)**2 else 0
            if below==10:h=lag-9
        if stop is None and lag%2:
            pair=rho[-2]+rho[-1]
            if pair<=0:stop=lag//2
            else:total+=pair;positive+=1
        if stop is not None and h is not None:break
    raw=-1+2*total if stop is not None else None
    tau=max(Fraction(1),raw) if raw is not None and raw>0 else None
    return dict(h=h,stop=stop,positive=positive,raw=raw,tau=tau,effective=Fraction(n,1)/tau if tau else None,
        stop_pair=rho[2*stop]+rho[2*stop+1] if stop is not None else None,last=len(rho)-1)


class TailTests(unittest.TestCase):
    def deadline(self):return time.monotonic_ns()+60*10**9

    def analyze(self,values,**changes):
        args=dict(maximum_samples=max(1,len(values)),deadline_ns=self.deadline());args.update(changes)
        return tail.analyze(values,**args)

    def compare(self,bits):
        observed=tail._dependence(array.array('Q',bits),0,self.deadline());expected=reference(bits)
        if expected is None:
            self.assertEqual(observed['ips_status'],'UNDEFINED');self.assertIsNone(observed['effective_count']);return
        self.assertEqual(observed['correlation_horizon_events'],expected['h'])
        self.assertEqual(observed['ips_first_nonpositive_pair'],expected['stop'])
        self.assertEqual(observed['ips_positive_pairs'],expected['positive'])
        self.assertEqual(frac(observed['tau_raw']),expected['raw'])
        self.assertEqual(frac(observed['tau']),expected['tau'])
        self.assertEqual(frac(observed['effective_count']),expected['effective'])
        self.assertEqual(frac(observed['ips_stop_pair']),expected['stop_pair'])
        self.assertEqual(observed['evaluated_max_lag'],expected['last'])
        self.assertEqual(observed['sparse_pair_contributions'],sum(bits)*(sum(bits)-1)//2)

    def test_all_binary_sequences_through_length9_match_direct_centered_product_oracle(self):
        for n in range(1,10):
            for bits in product((0,1),repeat=n):self.compare(bits)

    def test_longer_clustered_and_dispersed_indicators_match_direct_reference(self):
        rng=random.Random('SOFTWARE-D346-REFERENCE')
        for n in (11,25,71,137):
            cases=[[int(rng.randrange(10)==0) for _ in range(n)],
                [int(n//4<=i<n//2) for i in range(n)],
                [int(i%7 in (1,2)) for i in range(n)]]
            for bits in cases:
                with self.subTest(n=n,bits=bits):self.compare(bits)

    def test_inverse_ecdf_ties_strict_exceedance_and_same_ordered_digest_are_preserved(self):
        values=[0]*1999+[1,2];original=list(values);report=self.analyze(values)
        self.assertEqual(values,original);self.assertEqual(report['exact_quantiles_ticks']['p999'],0)
        self.assertEqual(report['primary_tail']['exceedance_count'],2)
        self.assertIsNone(report['secondary_p9999_ticks']);self.assertFalse(report['secondary_p9999_reported'])
        self.assertEqual(report['primary_log_status'],'UNDEFINED_ZERO_QUANTILE')
        again=self.analyze(tuple(values));self.assertEqual(again,report)
        self.assertEqual(report['primary_tail']['correlation_horizon_events'],2)
        self.assertEqual(report['primary_tail']['horizon_confirmation_endpoint'],11)

    def test_exact_noninterpolated_ranks_and_uint64_ticks_never_pass_through_float(self):
        values=list(range(1001));values[-1]=2**64-1;report=self.analyze(values)
        self.assertEqual(report['exact_quantiles_ticks'],dict(p50=500,p90=900,p99=990,p999=999))
        self.assertEqual(report['maximum_ticks'],2**64-1)
        changed=self.analyze(list(reversed(values)))
        self.assertEqual(changed['exact_quantiles_ticks'],report['exact_quantiles_ticks'])
        self.assertNotEqual(changed['ordered_integer_latency_sha256'],report['ordered_integer_latency_sha256'])

    def test_zero_events_and_zero_variance_do_not_claim_independence_or_effective_count(self):
        for values in ([],[5],[5]*2001):
            report=self.analyze(values)
            self.assertIsNone(report['primary_tail']['effective_count'])
            self.assertEqual(report['primary_tail']['primary_200000_gate'],'UNRESOLVED')
            self.assertIsNone(report['primary_tail']['correlation_horizon_events'])
        self.assertIsNone(self.analyze([])['maximum_ticks'])
        self.assertEqual(self.analyze([5]*2001)['exact_quantiles_ticks']['p999'],5)

    def test_missing_observed_complete_stop_pair_is_unresolved_without_zero_padding(self):
        result=tail._dependence(array.array('Q',[0,1]),0,self.deadline())
        self.assertEqual(result['ips_reason'],'NO_OBSERVED_NONPOSITIVE_COMPLETE_PAIR')
        self.assertIsNone(result['effective_count']);self.assertIsNone(result['tau_raw'])

    def test_strict_ten_lag_boundary_uses_exact_196_over100(self):
        self.assertFalse(tail._below_threshold(49,625,625))
        self.assertFalse(tail._below_threshold(-49,625,625))
        self.assertTrue(tail._below_threshold(48,625,625))
        self.assertFalse(tail._below_threshold(50,625,625))

    def test_negative_or_zero_ips_time_never_becomes_an_effective_count(self):
        found=[]
        for n in range(3,10):
            for bits in product((0,1),repeat=n):
                expected=reference(bits)
                if expected is not None and expected['raw'] is not None and expected['raw']<=0:
                    found=list(bits);break
            if found:break
        self.assertTrue(found,'independent oracle should exercise this finite-sample branch')
        result=tail._dependence(array.array('Q',found),0,self.deadline())
        self.assertEqual(result['ips_reason'],'NONPOSITIVE_RAW_AUTOCORRELATION_TIME')
        self.assertIsNone(result['effective_count'])

    def test_effective_count_clamps_to_raw_count_and_exact_primary_threshold_is_separate(self):
        for n,gate in ((199999,'FAIL'),(200000,'PASS')):
            values=array.array('Q',[0])*n;values[n//2]=1;report=self.analyze(values)
            self.assertEqual(frac(report['primary_tail']['tau']),1)
            self.assertEqual(frac(report['primary_tail']['effective_count']),n)
            self.assertEqual(report['primary_tail']['primary_200000_gate'],gate)
            self.assertFalse(report['run_validity_assessed']);self.assertFalse(report['confirmatory_horizon_frozen'])

    def test_secondary_quantile_is_suppressed_until_its_own_exact_effective_count_passes(self):
        for n,reported in ((1999999,False),(2000000,True)):
            values=array.array('Q',[0])*n;values[n//2]=1;report=self.analyze(values)
            self.assertEqual(report['secondary_p9999_reported'],reported)
            self.assertEqual(report['secondary_p9999_ticks'],0 if reported else None)
            self.assertEqual(report['secondary_tail']['secondary_2000000_gate'],'PASS' if reported else 'FAIL')

    def test_lossy_types_negative_ticks_oversized_sources_and_expired_budget_reject(self):
        for value in ([True],[1.0],[-1],[2**64],array.array('I',[1])):
            with self.subTest(value=value),self.assertRaises(tail.NumericsError):self.analyze(value)
        with self.assertRaisesRegex(tail.NumericsError,'offered-count ceiling'):self.analyze([1,2],maximum_samples=1)
        with self.assertRaisesRegex(tail.NumericsError,'source-count ceiling'):self.analyze([1],maximum_samples=tail.MAX_SAMPLES+1)
        with self.assertRaisesRegex(tail.NumericsError,'deadline expired'):self.analyze([1],deadline_ns=time.monotonic_ns()-1)

    def test_pair_histogram_generation_checks_original_deadline_without_returning_a_horizon(self):
        real=tail._before;calls=0
        def expire(deadline):
            nonlocal calls
            calls+=1
            if calls==5:raise tail.NumericsError('SOFTWARE fixed analysis deadline expired')
            real(deadline)
        with mock.patch.object(tail,'_before',side_effect=expire):
            with self.assertRaisesRegex(tail.NumericsError,'deadline expired'):
                tail._dependence(array.array('Q',[i%2 for i in range(1000)]),0,self.deadline())

    def test_owner_approval_and_original_proposal_bytes_are_required(self):
        with tempfile.TemporaryDirectory(prefix='s180-tail-policy-') as name:
            root=Path(name)
            for member in (tail.PROPOSAL,tail.ACCEPTANCE):
                p=root/member;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((tail.ROOT/member).read_bytes())
            with mock.patch.object(tail,'ROOT',root):
                self.analyze([1,2,3]);path=root/tail.ACCEPTANCE;raw=path.read_bytes();path.write_bytes(raw+b' ')
                with self.assertRaisesRegex(tail.NumericsError,'owner acceptance'):self.analyze([1])
                path.write_bytes(raw);path=root/tail.PROPOSAL;path.write_bytes(path.read_bytes()+b' ')
                with self.assertRaisesRegex(tail.NumericsError,'approved numerical proposal'):self.analyze([1])

    def test_large_exact_fractions_use_decimal_strings_in_canonical_json(self):
        value=Fraction(2**100+1,2**70+3);encoded=tail._fraction(value)
        self.assertEqual(frac(encoded),value);self.assertIsInstance(encoded['numerator_decimal'],str)
        report=self.analyze([i%37 for i in range(2001)])
        from check_canonical import canonicalize
        self.assertEqual(json.loads(canonicalize(report)),report)

    def test_complete_population_candidate_does_not_select_a_favorable_subset_or_freeze(self):
        report=self.analyze([0]*1999+[1,2]);ids=[f'SOFTWARE-RUN-{i}' for i in range(180)]
        reports={name:copy.deepcopy(report) for name in ids}
        result=tail.candidate_block_length(reports,required_run_ids=ids)
        self.assertEqual(result['candidate_block_length_events'],4)
        self.assertFalse(result['warmup_frozen']);self.assertFalse(result['raw_family_validity_established'])
        reports[ids[-1]]['primary_tail']['correlation_horizon_events']=None
        result=tail.candidate_block_length(reports,required_run_ids=ids)
        self.assertIsNone(result['candidate_block_length_events']);self.assertEqual(result['unresolved_run_ids'],[ids[-1]])
        del reports[ids[-1]]
        with self.assertRaisesRegex(tail.NumericsError,'no subset'):tail.candidate_block_length(reports,required_run_ids=ids)

    def test_schema_rejects_altered_authority_fraction_and_suppression_fields(self):
        from jsonschema import Draft202012Validator
        schema=json.loads((tail.ROOT/'config/schemas/stage17-s180-tail-numerics-v1.schema.json').read_bytes())
        Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema)
        for values in ([],[1]*11,list(range(2001))):validator.validate(self.analyze(values))
        report=self.analyze(list(range(2001)))
        for mutate in (lambda r:r.update(execution_authority=True),
                lambda r:r.update(secondary_p9999_ticks=1),
                lambda r:r['primary_tail']['tau'].update(denominator_decimal='0'),
                lambda r:r['primary_tail'].update(effective_count=True)):
            changed=copy.deepcopy(report);mutate(changed)
            self.assertTrue(list(validator.iter_errors(changed)))


if __name__=='__main__':unittest.main()
