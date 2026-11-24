"""Exact owner-approved D346 per-run descriptive pilot tail calculations.

Offline numerical library only. The independent validator must establish raw
correctness/source/window provenance before calling it. These functions neither
validate a run nor generate observations, infer a freeze or grant execution.
"""
from __future__ import annotations
import array
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct
import time

SCHEMA='cpu-prefetch-stage17-s180-tail-numerics/1'
AGGREGATE_SCHEMA='cpu-prefetch-stage17-s180-block-length-candidate/1'
METHOD='D346-S180-TAIL-NUMERICS-v1'
ROOT=Path(__file__).resolve().parents[1]
PROPOSAL='docs/decisions/0346-s180-prospective-tail-numerical-conventions-proposal.md'
PROPOSAL_SIZE=6544
PROPOSAL_SHA='3563546e9267a92c3e52de9b95ef06ffbb54883a4a091525cd9515e932fb0a10'
ACCEPTANCE='docs/evidence/stage17/PILOT-D346-ACCEPTED-20261123-01/owner-acceptance.json'
ACCEPTANCE_SHA='b0ef439778d94cb9dd905d5117ed0565771c5e75eaeb7857dd29dee8a1540bf1'
# D334's unchanged ceil(2 * (5011713/4 events/s) * 1 second).
MAX_SAMPLES=(5011713+1)//2
U64_MAX=2**64-1


class NumericsError(ValueError):pass


def require(value,message):
    if not value:raise NumericsError('S180 tail numerics: '+message)


def _before(deadline):
    require(type(deadline) is int and time.monotonic_ns()<deadline,'original analysis deadline expired')


def _approval():
    with (ROOT/PROPOSAL).open('rb') as stream:raw=stream.read(PROPOSAL_SIZE+1)
    require(len(raw)==PROPOSAL_SIZE and hashlib.sha256(raw).hexdigest()==PROPOSAL_SHA,
        'exact unchanged approved numerical proposal required')
    with (ROOT/ACCEPTANCE).open('rb') as stream:raw=stream.read(4097)
    require(len(raw)<=4096 and hashlib.sha256(raw).hexdigest()==ACCEPTANCE_SHA,
        'actual exact owner acceptance required')
    value=json.loads(raw)
    require(value['approved'] is True and value['method_id']==METHOD
        and value['proposal']==dict(path=PROPOSAL,size_bytes=PROPOSAL_SIZE,sha256=PROPOSAL_SHA)
        and value['scientific_numerical_conventions_approved'] is True
        and all(value[k] is False for k in ('collection_changed','additional_measurements_authorized',
            'execution_authority','phase18_authority')),'owner acceptance scope differs')


def _fraction(value):
    # Rational numerators can exceed the JCS-I64 domain even though each raw
    # timestamp/count fits. Canonical decimal strings preserve every bit.
    value=Fraction(value)
    return dict(numerator_decimal=str(value.numerator),denominator_decimal=str(value.denominator))


def _pack(values,maximum,deadline):
    require(type(maximum) is int and 0<maximum<=MAX_SAMPLES,'frozen measurement source-count ceiling required')
    require(type(values) in (array.array,list,tuple),'bounded explicit integer latency sequence required')
    require(type(values) is not array.array or (values.typecode=='Q' and values.itemsize==8),
        'packed latencies must be unsigned64 words')
    size=len(values);require(size<=maximum,'accepted count exceeds frozen offered-count ceiling')
    packed=array.array('Q');require(packed.itemsize==8,'native unsigned64 storage unsupported')
    digest=hashlib.sha256();digest.update(b'D346-END-TO-END-U64BE-v1\0'+struct.pack('>Q',size))
    for i,value in enumerate(values):
        if i%256==0:_before(deadline)
        require(type(value) is int and 0<=value<=U64_MAX,'latency must be an exact unsigned64 integer tick value')
        packed.append(value);digest.update(struct.pack('>Q',value))
    require(len(values)==size and len(packed)==size,'latency extent changed during snapshot')
    _before(deadline);return packed,digest.hexdigest()


def _undefined(n,k,reason):
    return dict(status='UNDEFINED',reason=reason,raw_count=n,exceedance_count=k,
        variance_numerator_decimal=str(k*(n-k)),variance_denominator_decimal=str(n*n),
        correlation_horizon_events=None,horizon_confirmation_endpoint=None,
        ips_status='UNDEFINED',ips_reason=reason,ips_positive_pairs=0,
        ips_first_nonpositive_pair=None,ips_stop_pair=None,tau_raw=None,tau=None,effective_count=None,
        primary_200000_gate='UNRESOLVED',secondary_2000000_gate='UNRESOLVED',
        evaluated_max_lag=None,sparse_pair_contributions=0)


def _below_threshold(numerator,denominator,n):
    return 625*n*numerator*numerator<2401*denominator*denominator


def _dependence(packed,threshold,deadline):
    """Exact sparse binary cross-counts; no FFT, lag cutoff or fake convergence."""
    _before(deadline);n=len(packed);positions=array.array('Q')
    for i,value in enumerate(packed):
        if i%256==0:_before(deadline)
        if value>threshold:positions.append(i)
    k=len(positions)
    if not n:return _undefined(n,k,'NO_ACCEPTED_EVENTS')
    if k in (0,n):return _undefined(n,k,'ZERO_TAIL_INDICATOR_VARIANCE')
    cross=array.array('Q',[0])*n;cross[0]=k;contributions=0
    for i,left in enumerate(positions):
        _before(deadline)
        for j in range(i+1,k):
            if contributions%256==0:_before(deadline)
            cross[positions[j]-left]+=1;contributions+=1
    denominator=n*k*(n-k);n_squared=n*n;nk=n*k;k_squared=k*k
    a=k;b=0;below=0;horizon=None;endpoint=None;positive_pairs=0;pair_sum=0
    even=None;stop_index=None;stop_pair=None;last=None
    for lag in range(n):
        if lag%256==0:_before(deadline)
        while a and positions[a-1]>=n-lag:a-=1
        while b<k and positions[b]<lag:b+=1
        numerator=n_squared*cross[lag]-nk*(a+k-b)+(n-lag)*k_squared
        last=lag
        if horizon is None and lag>=1:
            below=below+1 if _below_threshold(numerator,denominator,n) else 0
            if below==10:horizon=lag-9;endpoint=lag
        if stop_index is None:
            if lag%2==0:even=numerator
            else:
                pair=even+numerator
                if pair<=0:stop_index=lag//2;stop_pair=_fraction(Fraction(pair,denominator))
                else:positive_pairs+=1;pair_sum+=pair
        if horizon is not None and stop_index is not None:break
    _before(deadline)
    result=dict(status='DEFINED' if horizon is not None else 'HORIZON_UNRESOLVED',
        reason=None if horizon is not None else 'NO_OBSERVED_TEN_LAG_INTERVAL',raw_count=n,exceedance_count=k,
        variance_numerator_decimal=str(k*(n-k)),variance_denominator_decimal=str(n*n),
        correlation_horizon_events=horizon,horizon_confirmation_endpoint=endpoint,
        ips_status='UNRESOLVED',ips_reason=None,ips_positive_pairs=positive_pairs,
        ips_first_nonpositive_pair=stop_index,ips_stop_pair=stop_pair,tau_raw=None,tau=None,effective_count=None,
        primary_200000_gate='UNRESOLVED',secondary_2000000_gate='UNRESOLVED',
        evaluated_max_lag=last,sparse_pair_contributions=contributions)
    if stop_index is None:
        result['ips_reason']='NO_OBSERVED_NONPOSITIVE_COMPLETE_PAIR';return result
    raw_tau=Fraction(-denominator+2*pair_sum,denominator);result['tau_raw']=_fraction(raw_tau)
    if raw_tau<=0:
        result['ips_reason']='NONPOSITIVE_RAW_AUTOCORRELATION_TIME';return result
    tau=max(Fraction(1),raw_tau);effective=Fraction(n,1)/tau
    require(0<effective<=n,'effective count outside accepted raw-count bound')
    result.update(ips_status='DEFINED',tau=_fraction(tau),effective_count=_fraction(effective),
        primary_200000_gate='PASS' if effective>=200000 else 'FAIL',
        secondary_2000000_gate='PASS' if effective>=2000000 else 'FAIL')
    return result


def analyze(latencies,*,maximum_samples,deadline_ns):
    """One numerical result only; caller authenticates the actual reconciled run."""
    _before(deadline_ns);_approval();packed,digest=_pack(latencies,maximum_samples,deadline_ns);n=len(packed)
    ordered=sorted(packed);_before(deadline_ns)
    def quantile(numerator,denominator):
        if not n:return None
        rank=(numerator*n+denominator-1)//denominator
        return ordered[rank-1]
    quantiles={name:quantile(num,den) for name,num,den in (
        ('p50',1,2),('p90',9,10),('p99',99,100),('p999',999,1000))}
    secondary=quantile(9999,10000)
    primary_dependence=_dependence(packed,quantiles['p999'],deadline_ns)
    secondary_dependence=_dependence(packed,secondary,deadline_ns)
    secondary_estimable=secondary_dependence['secondary_2000000_gate']=='PASS'
    result=dict(schema_version=SCHEMA,method_id=METHOD,proposal_sha256=PROPOSAL_SHA,
        owner_acceptance_sha256=ACCEPTANCE_SHA,ordered_integer_latency_sha256=digest,raw_accepted_count=n,
        exact_quantiles_ticks=quantiles,secondary_p9999_ticks=secondary if secondary_estimable else None,
        secondary_p9999_reported=secondary_estimable,maximum_ticks=ordered[-1] if n else None,
        primary_tail=primary_dependence,secondary_tail=secondary_dependence,
        primary_log_status=('UNDEFINED_NO_ACCEPTED_EVENTS' if not n else
            'UNDEFINED_ZERO_QUANTILE' if quantiles['p999']==0 else 'NOT_COMPUTED_BY_EXACT_TAIL_METHOD'),
        aggregate_block_length_selected=False,stability_resampling_status='NOT_EVALUATED',
        confirmatory_horizon_frozen=False,warmup_frozen=False,repeated_block_covariance_estimated=False,
        raw_reconciliation_performed=False,source_provenance_verified=False,run_validity_assessed=False,
        execution_authority=False,phase18_authority=False)
    _before(deadline_ns);return result


def candidate_block_length(reports,*,required_run_ids):
    """Treatment-blind maximum only for the exact complete required population.

    Does not establish raw validity or freeze confirmation. No subset/top-up.
    The caller authenticates reports and the original required run identities.
    """
    require(type(required_run_ids) in (list,tuple) and len(required_run_ids)==180
        and all(type(name) is str and 0<len(name)<=512 and all(ord(c)>=32 and ord(c)!=127 for c in name) for name in required_run_ids)
        and len(set(required_run_ids))==180,'exact full required180-run population required')
    require(type(reports) is dict and set(reports)==set(required_run_ids),'complete required run reports; no subset permitted')
    horizons=[]
    for name in required_run_ids:
        report=reports[name]
        require(report['schema_version']==SCHEMA and report['method_id']==METHOD
            and report['proposal_sha256']==PROPOSAL_SHA and report['owner_acceptance_sha256']==ACCEPTANCE_SHA,
            'required report uses a different numerical method')
        h=report['primary_tail']['correlation_horizon_events']
        if h is not None:require(type(h) is int and h>=1,'invalid observed correlation horizon')
        horizons.append(h)
    unresolved=[name for name,h in zip(required_run_ids,horizons,strict=True) if h is None]
    identity_bytes=json.dumps(list(required_run_ids),separators=(',',':'),ensure_ascii=False).encode()
    return dict(schema_version=AGGREGATE_SCHEMA,method_id=METHOD,proposal_sha256=PROPOSAL_SHA,
        owner_acceptance_sha256=ACCEPTANCE_SHA,required_run_ids_sha256=hashlib.sha256(identity_bytes).hexdigest(),
        required_runs=180,unresolved_run_ids=unresolved,
        status='UNRESOLVED' if unresolved else 'CANDIDATE_ONLY',
        maximum_observed_horizon_events=None if unresolved else max(horizons),
        candidate_block_length_events=None if unresolved else 2*max(horizons),
        raw_family_validity_established=False,stability_resampling_status='NOT_EVALUATED',
        confirmatory_horizon_frozen=False,warmup_frozen=False,execution_authority=False,phase18_authority=False)
