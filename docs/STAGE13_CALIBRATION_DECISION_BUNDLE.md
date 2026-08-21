# Stage 13 Calibration Decision/Input Bundle

Protocol version: **`2.0.0-pre.2`**

Decision IDs: **D-035**, **D-036**, **D-037**, and **D-038**  
Approval question: **Q12**  
State: **`ACCEPTED_Q12`**

The protocol, statistical, and repository owners accepted this exact bundle on
2026-08-21 by answering:

```text
Q12 - accept the bundle
```

Acceptance authorizes Stage 13 software implementation with synthetic and
fake inputs only. It would not authorize calibration collection, select a
stand, supply a duration or exact run count, freeze a capacity or seed, produce
`mu_ref` or `d2`, approve a pilot, or authorize confirmatory execution.

## Decision summary

| ID | Classification | Accepted selection | Owner | Gate | Supersession |
|---|---|---|---|---|---|
| D-035 | Scientific calibration estimator | `SERVICE-RATE-NP-LTL95C95-MIN-v1`: a distribution-free 95%-confidence/95%-content lower run-throughput tolerance limit; `mu_ref` is the minimum eligible cell limit | Protocol and statistical owners; calibration owner | Accepted for Stage 13 software; exact duration and planned count before calibration access | New estimator ID, prospective freeze, superseding ADR, and complete recalibration |
| D-036 | Scientific zero-loss feasibility and global action | `MATRIX-FULL-RUNCLUSTER-WHOEFFDING-BONFERRONI-v1`: independent-run-cluster weighted Hoeffding bounds, 95% simultaneous confidence, `pi_matrix=0.95`, and a five-member common rational load-scale ladder | Protocol and statistical owners; block-planning owner | Accepted for Stage 13 software; final calculation requires frozen `Rtotal` and schedules | New method/policy ID, prospective freeze, superseding ADR, and complete feasibility recalculation |
| D-037 | Scientific `d2` calibration | `RING-D2-RUNTAIL-LTL95C95-v1`: ring-off advancing-slot demand/issue observations, exact per-run p99.9/p0.1 summaries, and conservative marginal 95%/95% run-level extremes across both hardware states | Protocol and statistical owners; queue/timing owner | Accepted for Stage 13 software; stand context, duration, count, and evidence before `R2` use | New method ID, prospective freeze, superseding ADR, and complete per-context recalibration |
| D-038 | Calibration records, arithmetic, lifecycle, and compatibility | Versioned `JCS-I64-v1` plan/result/freeze records; exact rationals where possible; outward-rounded versioned Decimal arithmetic only for the Hoeffding margin; append-only invalidation and no hidden top-up | Repository, validation, calibration, and data-integrity owners | Accepted for Stage 13 software; exact schemas and conformance suite close Stage 13 | New schema/suite IDs and converters; immutable old records remain version-bound |

## Protocol constraints that are already fixed

This bundle does not reopen the following rules:

- service calibration reproduces every Stage A cell configuration except for
  its continuously ready producer;
- its response is consumed-event throughput over a fixed calibrated interval;
- calibration runs are independent, their duration and planned count are
  frozen before their values are opened, and `mu_ref` is the minimum valid
  one-sided 95% cell lower bound;
- the initial candidate loads are `1/4`, `1/2`, and `3/4` of `mu_ref`;
- the separate feasibility probe uses the actual pre-generated open-loop,
  exactly-one-attempt workload, retains every `FULL`, and evaluates the entire
  180-cell Stage A matrix rather than favorable cells;
- the matrix bound is
  `max(0, 1 - sum_c E_c*p_U,c)`, with `E_c=Rtotal*N_sched,c`;
- zero observed `FULL` events cannot imply `p_U,c=0`, and confirmatory strict
  zero loss remains `N_full=0` regardless of the feasibility method;
- `d2` uses ring-off evidence, separate producer and consumer slot-demand
  latency and issue intervals, one common resolved producer/consumer distance,
  whole-cache-line rounding, a minimum of two lines, a `C/4` cap, and
  per-platform/placement/working-set-capacity freeze;
- calibration, pilot, confirmatory, diagnostic, and warm-up namespaces remain
  disjoint; and
- a material platform, build, queue, consumer action, capacity, hardware-state,
  or policy change invalidates every dependent calibration freeze.

`FULL`, low effective count, and an unfavorable calibration value are data.
They are not lifecycle failures and do not authorize deletion, selective
repetition, or a favorable substitute.

## Dependency order

Stage 13 has a strict evidence graph:

```text
eligible platform/build/control evidence
  -> common capacity and residency evidence
  -> D-037 d2 calibration in six placement/working-set contexts
  -> instantiate R2 with immutable d2 evidence
  -> D-035 service calibration over 5*2*2*3 = 60 cells
  -> mu_ref and candidate rate schedules
  -> D-036 open-loop feasibility probes over 180 cells per candidate scale
  -> Stage 14/15 freeze Rtotal and every planned N_sched,c
  -> final matrix-feasibility record and load freeze
```

The software calculators and validators can be implemented before those
external inputs exist. They must emit `NOT_EVALUATED` or a blocking error, not
a placeholder result. In particular, a provisional feasibility calculation
cannot become final until the exact `Rtotal`, `Nruns=180*Rtotal`, and every
planned schedule count are immutable inputs.

## D-035: service-rate estimator

### Options considered

| Option | Benefit | Material risk | Recommendation |
|---|---|---|---|
| One-sided Student-t lower confidence bound on mean run throughput | Familiar and compact | Exact coverage requires a distributional assumption; a t-quantile implementation or new dependency is needed; an outlier model would remain open | Do not select for v1 |
| Percentile or BCa bootstrap lower bound | Fewer parametric assumptions | Bootstrap count, seed, resampling grammar, and tail behavior add a second unresolved calibration design; finite-sample coverage is approximate | Do not select for v1 |
| Minimum of a prospectively fixed independent-run sample as a nonparametric lower tolerance limit | Integer/rational min operation; no fitted distribution or new dependency; conservative and transparent | Requires at least 59 valid independent runs per cell for the accepted 95/95 statement and can make stand cost or feasibility unfavorable | **Selected** |

### Accepted exact rule

For valid independent service-calibration run `r` in cell `c`, retain exact
integers `consumed_r`, `interval_ticks_r`, and `ticks_per_second`. Define the
exact rational throughput

```text
T_c,r = consumed_r * ticks_per_second / interval_ticks_r
```

without converting it through binary floating point. The producer is
continuously ready; the queue implementation, package, consumer action,
placement, capacity, working-set construction, verified hardware state, clock,
reset, and drain rules are otherwise the same as the corresponding Stage A
cell. A `FULL` attempt is retained. Only a protocol-invalid run is ineligible
for the estimator, and its artifacts remain immutable.

Let `n_c` be the number of valid values in the prospectively enumerated plan.
Require `n_c>=59`. Define

```text
mu_cell,c = min_r T_c,r
mu_ref    = min_c mu_cell,c
```

For independent identically distributed run-level throughputs, the sample
minimum is a distribution-free one-sided lower tolerance limit: with
confidence `1-0.95^n_c`, at least 95% of future run-level throughput values are
not below it. At `n_c=59`, that confidence is greater than 95%. This makes the
otherwise open target of the protocol's 95% lower bound explicit: v1 bounds a
conservative 5th run-throughput percentile, not a Gaussian mean.

The exact planned run count and duration are still mandatory freeze inputs.
They may exceed the minima but may not be extended after values are opened.
If fewer than 59 planned runs remain valid, the cell and `mu_ref` are
unresolved. There is no automatic “run until 59 valid” behavior. A valid zero
throughput produces a zero limit and an unresolved/infeasible offered-load
plan; it is not discarded.

### Scientific and compatibility effect

This choice is intentionally conservative and may reduce the common offered
rate compared with a mean-based estimator. It avoids silently assuming normal
run throughput. The content probability, confidence construction, planned
sample, rational throughput grammar, valid-run policy, and min-across-cell rule
are suite identity. Changing any of them requires prospective recalibration;
old values are never reinterpreted.

## D-036: matrix zero-loss feasibility

### Options considered

| Option | Benefit | Material risk | Recommendation |
|---|---|---|---|
| Event-level Clopper-Pearson/binomial upper limits | Exact under independent Bernoulli events | The experiment explicitly requires a dependence/clustering treatment; queue-full outcomes within a run are not justified as independent | Reject for v1 |
| Ordinary event bootstrap or “zero observed means zero” | Easy to compute | Can return a zero upper bound and ignores run clustering; directly violates the protocol | Reject |
| Whole-run cluster bootstrap/GEE | Can model clustering flexibly | Approximate small-sample behavior, resampling grammar, smoothing at zero, and an additional analysis dependency remain open | Defer unless v1 is superseded |
| Weighted Hoeffding bound over independent bounded run-cluster full fractions with prospective Bonferroni allocation | Requires only independent runs and `0<=Y<=1`; permits arbitrary within-run event dependence; strictly positive finite-sample margin | May be extremely conservative and may prove the planned matrix infeasible | **Selected** |

### Accepted exact rule

For feasibility run `r` of Stage A cell `c` and global candidate scale `g_j`,
define the exact run-cluster fraction

```text
Y_cjr = N_full,cjr / N_offered,cjr
w_cjr = N_offered,cjr / sum_r N_offered,cjr
p_hat,cj = sum_r w_cjr * Y_cjr
```

Runs, not events, are the independent units. Within-run dependence is
unrestricted. A run with zero offered events is invalid for this estimator;
its absence cannot be silently repaired. The frozen schedule generator,
namespace family, platform/build/action/capacity, and run-generation process
must support the prospective common-marginal interpretation across the probe
and planned matrix.

Use familywise one-sided confidence `1-alpha_family=19/20` and prospectively
allocate

```text
alpha_cj = (1/20) / (180 * 5) = 1/18000
p_U,cj = min(1,
             p_hat,cj
             + sqrt(log(1/alpha_cj) * sum_r(w_cjr^2) / 2))
```

across all 180 cells and all five candidate scales. The margin is positive for
every finite input, including all-zero observations. Exact counts and weights
remain rational. Only the positive transcendental margin uses the D-038
versioned outward-rounded Decimal calculation.

The accepted minimum whole-matrix completion probability is the
explicit owner risk choice

```text
pi_matrix = 19/20 = 0.95
```

For frozen `Rtotal` and schedules, calculate

```text
E_cj = Rtotal * N_sched,cj
P_L,j = max(0, 1 - sum_c E_cj * p_U,cj)
```

using the protocol's exact exposure model. Confidence in the simultaneous
`p_U` family and the `pi_matrix` completion-probability threshold are distinct
quantities even though both are accepted as 0.95.

### Accepted global load rule

Evaluate this exact descending common rational ladder:

```text
g = [1/1, 9/10, 4/5, 7/10, 3/5]
rates(g) = g * [1/4, 1/2, 3/4] * mu_ref
```

Each candidate uses its own disjoint predeclared feasibility namespace and a
complete 180-cell probe plan. Evaluate from largest to smallest and select the
first candidate with `P_L>=pi_matrix`. The prospective Bonferroni family
includes all five candidates even if sequential stopping means later candidates
are never run. No cell-specific rate exists.

If no candidate passes, Stage A remains infeasible or unresolved. Capacity may
be revised only through a new prospective freeze that invalidates the affected
`d2`, service-rate, schedule, storage-budget, and feasibility evidence. The
software must not invent another ladder point, loosen confidence or
`pi_matrix`, accept a nonzero confirmatory full threshold, or use achieved
throughput as offered load.

### Scientific and compatibility effect

The accepted method deliberately prefers a visible infeasibility result to an
optimistic independence assumption. It may require substantially more
calibration exposure or a prospective capacity/design revision. Confidence
allocation, cluster unit, weighting, ladder, `pi_matrix`, Decimal profile, and
global selection rule are compatibility fields.

## D-037: ring-distance calibration

### Options considered

| Option | Benefit | Material risk | Recommendation |
|---|---|---|---|
| Raw maximum latency and minimum issue interval | Very conservative and simple | One interrupted sample or timer tie dominates; sample-size dependence is uncontrolled | Reject for v1 |
| Means, medians, or fitted parametric tails | Stable | Not conservative for a lookahead intended to cover tail demand latency and fast issue cadence | Reject |
| Exact per-run p99.9 latency and p0.1 issue summaries, then nonparametric 95/95 run-level extremes | Uses the protocol's inverse-ECDF rule, no fitted distribution/new dependency, and separates event tails from run independence | Requires at least 59 valid independent runs per hardware state/context and may hit the capacity cap | **Selected** |

### Calibration observations

Use `D2_CALIBRATION`, the exact ring-off package, the accepted clock, and no
software prefetch. For every platform, placement, and frozen working-set
capacity context, calibrate both verified hardware-prefetch states separately.
The final distance is common across those states so the R2 software parameter
does not change with the hardware whole plot.

Instrument the same ring-slot acquire demand that determines whether the
current producer slot is empty and whether the current consumer slot contains
an event:

- slot-demand latency is the checked elapsed time from immediately before that
  acquire load to immediately after it returns;
- producer issue interval is between successive demand-start timestamps whose
  attempts advance the producer slot (`ACCEPTED`);
- consumer issue interval is between successive demand-start timestamps whose
  attempts advance the consumer slot (successful dequeue);
- `FULL` and empty attempts and their counts remain retained but do not
  represent advancement by one ring slot and therefore do not enter the issue
  interval sequence; and
- capture instrumentation is calibration-only, outside confirmatory runs, and
  must not alter the queue's release/acquire order.

This boundary mapping is a scientific interpretation of the open calibration
method, not an ordinary instrumentation default. Q12 accepted this mapping;
Stage 13 must implement and verify it without reinterpretation.

### Accepted exact summaries and distance

For each valid run and each of the four positive observation sequences
(producer/consumer demand latency and producer/consumer advancing issue
interval), use the protocol's non-interpolated order statistic
`X_(ceil(p*N))`:

- demand latency: `p=999/1000`;
- advancing issue interval: `p=1/1000`.

The exact per-sequence minimum observation count and run duration remain
prospective execution inputs; no default is supplied here. Empty, overflowed,
nonpositive-issue, failed-clock, failed-integrity, or otherwise invalid series
cannot contribute a summary.

For each hardware state and context, require at least 59 valid results from a
prospectively enumerated independent-run plan. Take the maximum of the
run-level demand p99.9 values and the minimum of the run-level issue p0.1
values. As in D-035, those extrema give a distribution-free
95%-confidence/95%-content tolerance statement over independent run-level
summaries. Invalid planned runs remain in the plan and do not authorize a
top-up. Then define across producer, consumer, H0, and H1:

```text
ell_star = max(all four eligible demand-latency upper limits)
c_star   = min(all four eligible advancing-issue lower limits)
```

The accepted 95%-confidence/95%-content statements are marginal for the
demand extreme and issue extreme. V1 does not claim that both statements hold
simultaneously with 95% confidence. The max/min merge is conservative across
workers and hardware states within each marginal statement; adding a joint
confidence claim or multiplicity adjustment requires a prospective superseding
decision.

Require `c_star>0`. Let

```text
d1_slots  = ceil(cache_line_bytes / slot_bytes)
raw_slots = ceil(ell_star / c_star)
raw_lines = ceil(raw_slots / d1_slots)
cap_lines = floor((C/4) / d1_slots)
d2_lines  = min(max(2, raw_lines), cap_lines)
d2_slots  = d2_lines * d1_slots
```

All divisions are checked integer ceiling/floor operations. If
`cap_lines<2`, `d2_slots<=d1_slots`, the cap collapses R2 to R1, arithmetic
overflows, or evidence is incomplete, the context is ineligible. The same
resolved `d2_slots` and evidence ID bind both producer and consumer R2 sites.

### Scientific and compatibility effect

The selected p99.9/p0.1 summaries and cross-state conservative merge can
increase R2 distance and can make a context ineligible. They prevent hardware
state or treatment effect from choosing a favorable software distance. The
capture boundaries, eligible operations, quantiles, tolerance construction,
context key, rounding, minimum, cap, and collapse rule are suite identity.

## D-038: records, arithmetic, and invalidation

### Accepted record family

Stage 13 should add implementation-owned Draft 2020-12 schemas under
`config/schemas/` without editing imported schemas:

| Record | Required role |
|---|---|
| `cpu-prefetch-calibration-plan/1` | Immutable method IDs, context product, exact duration/count/sample inputs, identities, namespaces, candidate ladder, confidence allocation, owners, authority, budget, and all prerequisite hashes before outcome access |
| `cpu-prefetch-service-rate-calibration/1` | Every planned run identity/status/count/interval/exact throughput, valid-run set, per-cell limit, and `mu_ref` source set |
| `cpu-prefetch-d2-calibration/1` | Raw observation references, exact boundary/method IDs, per-run summaries, H0/H1 context merge, geometry, `ell_star`, `c_star`, rounding, cap, and resolved distance or ineligibility |
| `cpu-prefetch-zero-loss-feasibility/1` | Every probe source/count, run-cluster fraction, weights, simultaneous upper bounds, candidate schedules/exposures, `Rtotal`, `P_L`, `pi_matrix`, and selected global action |
| `cpu-prefetch-calibration-freeze/1` | Complete immutable dependency graph, selected outputs, nonselected candidates, authority/date/input hashes, material-change fingerprint, and superseded record where applicable |

All records use explicit IDs rather than path parsing, `2.0.0-pre.2`,
`JCS-I64-v1`, zero-self SHA-256 where self-identification is needed, and exact
source artifact references. Unknown versions or mixed graphs fail closed.

### Arithmetic and dependency policy

- Counts, ticks, rates, throughput comparisons, quantiles, exposure, `d1`, and
  `d2` use checked integers and exact reduced rationals.
- The weighted Hoeffding logarithm and square root use an offline,
  implementation-owned, versioned Python 3.14 Decimal suite with explicit
  precision, operation order, and outward rounding. It reuses the accepted
  Python dependency but not the Stage 7 schedule suite ID or derivation domain.
- Stage 13 must publish direct boundary vectors and independent high-precision
  reference vectors before accepting that arithmetic implementation.
- No SciPy, R runtime, Boost.Math, or another dependency is authorized by Q12.
  Adding one requires the dependency/license process and a superseding ADR.
- Statistical calculation, schema/config parsing, hashing, serialization,
  allocation, and artifact publication remain outside every calibration timed
  interval.

### Lifecycle and invalidation

The calibration plan enumerates all run IDs before value access. There is no
hidden top-up, retry-until-valid, selective cell rerun, or mutable result file.
Failures and partial products remain append-only. An incomplete estimator is
`NOT_EVALUATED`/unresolved, not computed from a silently smaller favorable set.

A material change to any bound platform/build identity, queue source or memory
order, consumer action, clock/boundary policy, capacity/geometry, hardware
state mapping, package policy, schedule suite, calibration estimator, or
arithmetic suite invalidates dependent freezes. The new plan and result use
new IDs and reference the superseded freeze; prior artifacts are never
overwritten or reclassified.

## Required external inputs

Q12 supplies none of these values. Their absence blocks collection or final
freeze at the indicated gate, but does not block synthetic Stage 13 software
implementation after Q12 acceptance.

| Input | Required record/evidence | Gate |
|---|---|---|
| Eligible stand, exact build, compiler/libraries, selected CPU pairs, affinity/NUMA/page residency, clock qualification, H0/H1 mapping/probes, restoration, and authority | Accepted Stage 9/16 platform evidence and immutable build identity | Before any calibration execution |
| Common near/far capacity for each working-set class, cache/line/slot facts, footprints, and residency proof | Capacity selection and verified platform records | Before D-037 |
| D-037 exact duration, planned independent runs per state/context (`>=59`), minimum observations per sequence, namespaces/seeds, and storage/stand budget | Accepted calibration plan | Before D-037 collection |
| D-035 exact fixed duration and planned independent runs per cell (`>=59`), calibration namespaces/seeds, and storage/stand budget | Accepted calibration plan | Before D-035 collection |
| D-036 exact planned probe runs per cell/scale, horizons, schedules, namespaces/seeds, and storage/stand budget | Accepted calibration plan | Before feasibility collection |
| `Rtotal`, `Nruns`, and every final `N_sched,cj` | Stage 14/15 precision and schedule freeze records | Before final D-036 feasibility/load freeze |
| Named calibration operator, statistical reviewer, freeze authority, access chronology, and stand-hours approval | Authority and budget records | Before collection/freeze as applicable |

An input record must give an exact value and rationale. “Auto,” “host
default,” “until stable,” “until enough valid,” an unbounded run count, or a
value inferred from the development host is invalid.

## Required Stage 13 verification after acceptance

Implementation closure must include synthetic-only tests for:

- exact 60-cell service and six-context/two-state `d2` products;
- configuration equality with only the protocol-permitted calibration-mode
  difference;
- complete prospective run enumeration and namespace separation;
- exact throughput rationals, `n=58` rejection, `n=59` boundary, min-cell and
  zero-throughput behavior;
- invalid/partial planned runs with no hidden top-up;
- weighted Hoeffding direct vectors, outward rounding, simultaneous
  `180*5` allocation, all-zero positive upper bounds, unequal offered counts,
  overflow, and `p_U=1` clamping;
- exact exposure/union-bound arithmetic, all five global candidates, first-pass
  selection, no-pass unresolved state, and prohibition of a cell-specific
  adjustment;
- D2 boundary placement, advancement-only issue intervals, both workers and
  hardware states, exact inverse-ECDF ranks, 58/59 boundaries, zero issue,
  whole-line ceiling, two-line minimum, quarter cap, cap collapse, and context
  mismatch;
- source/hash/version/identity relationships, mixed-version rejection,
  canonical round trips, amendment/supersession, partial artifacts, and
  material-change invalidation; and
- applicable unit/property/integration, ASan/UBSan, TSan, format/static, schema,
  generated-code, and package checks without a latency/throughput claim.

Synthetic golden values are correctness fixtures and must be labelled as such.
No benchmark winner, rate recommendation, real `mu_ref`, real `d2`, or stand
eligibility may be reported by Stage 13 implementation tests.

## Evidence for this decision

- Imported implementation specification Sections 2, 4.1-4.2, 5.1-5.4, 8,
  10.5, 11, and 12; data dictionary run modes and load enums; freeze-checklist
  calibration rows; and the handoff readiness report.
- ADR-0001 through ADR-0034, especially the deterministic, clock, platform,
  lifecycle, storage, and reconciliation boundaries.
- NIST's description of nonparametric tolerance limits as one-sided confidence
  limits for population percentiles:
  <https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/tolelimi.htm>.
- Hoeffding's bounded-independent-variable inequality, applied here only to
  independent run-cluster fractions rather than events:
  <https://doi.org/10.1080/01621459.1963.10500830>.

These sources support the mathematical options. Q12 separately supplies the
owner acceptance of 95% content, `pi_matrix=0.95`, and the load ladder.

## Protocol-amendment assessment

No protocol amendment is required for the accepted decision: the imported
protocol explicitly leaves the estimator, dependence treatment, confidence,
`pi_matrix`, global reduction, duration/count, and conservative `d2` summaries
open for prospective freeze. Q12 selected these options without
changing queue-full validity, strict zero loss, the Stage A factors, the
union-bound equation, or replacement semantics.

If review concludes that “one-sided 95% lower confidence bound” must target a
mean rather than the accepted run-throughput percentile, or that the accepted
slot-demand boundary conflicts with the intended scientific object, Stage 13
must stop. That would be a scientific-meaning conflict requiring owner
clarification and, if the protocol text cannot support both readings, a
versioned protocol amendment rather than an engineering substitution.

## Approval record and post-approval state

Q12 accepted D-035 through D-038 on 2026-08-21. ADR-0035 through ADR-0038
record the four material decisions. The acceptance:

1. authorizes implementation only of the typed plans, calculators, validators,
   fake calibration modes, and synthetic tests described above;
2. keeps every external input visibly unresolved;
3. does not connect the implementation to a privileged stand or authorize a
   calibration run; and
4. requires stopping after Stage 13 software verification and reporting the
   remaining Stage 14/15/16/17 gates.
