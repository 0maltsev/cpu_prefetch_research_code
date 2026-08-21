# ADR-0037: Stage 13 ring-distance calibration

- Status: `ACCEPTED`
- Date: 2026-08-21
- Classification: Scientific software-prefetch distance calibration
- Decision owners: Protocol owner; statistical owner; queue owner; timing owner; repository owner
- Protocol version: `2.0.0-pre.2`
- Supersedes: None; resolves D-037
- Lifecycle gate: Accepted before Stage 13 implementation; platform/context plan and evidence remain required before R2 use

## Context and scientific constraints

Protocol Section 4.2 requires ring-off calibration with separate producer and
consumer slot-demand latency and issue intervals. It fixes conservative merge,
whole-cache-line rounding, a minimum two-line distance, a one-quarter-capacity
cap, a common producer/consumer `d2`, and a separate freeze for every platform,
placement, and working-set capacity where quantities differ. It leaves the
exact conservative summaries and capture interpretation open.

The distance cannot depend on a treatment effect or confirmatory outcome. Both
verified hardware-prefetch states must be covered without allowing state to
select a favorable software distance.

## Options considered

1. Raw maximum demand latency and minimum issue interval.
2. Means, medians, or fitted parametric tails.
3. Exact per-run p99.9 demand and p0.1 advancing-issue summaries followed by
   distribution-free 95%/95% run-level extremes.

Raw extremes are uncontrolled by sample size and vulnerable to a single
interruption or timer tie. Central summaries do not conservatively represent
the required tail relation. Option 3 preserves exact inverse-ECDF semantics and
separates event-tail estimation from independent-run coverage.

## Decision

Select D-037 suite `RING-D2-RUNTAIL-LTL95C95-v1` as specified by the accepted
[`STAGE13_CALIBRATION_DECISION_BUNDLE.md`](../STAGE13_CALIBRATION_DECISION_BUNDLE.md).

For each platform, placement, and frozen working-set-capacity context, collect
ring-off calibration separately under verified H0 and H1 with no software
prefetch. Instrument the same ring-slot acquire demand that decides whether the
producer slot is empty or the consumer slot contains an event:

- demand latency is the accepted-clock interval immediately before through
  immediately after that acquire load;
- producer issue interval is between demand-start timestamps of successive
  accepted attempts that advance the producer slot;
- consumer issue interval is between demand-start timestamps of successive
  successful dequeues that advance the consumer slot;
- `FULL` and empty observations and counts remain retained, but do not advance
  a ring slot and do not enter the issue-interval sequence; and
- calibration instrumentation must not alter the queue's release/acquire
  mapping and is absent from confirmatory runs.

For each valid positive sequence in each run, use exact noninterpolated order
statistic `X_(ceil(p*N))`: `p=999/1000` for demand latency and `p=1/1000` for
advancing issue interval. The exact duration and minimum sequence count remain
prospective plan inputs.

For every hardware-state/context combination, require at least 59 valid
results from a prospectively enumerated independent-run plan. Invalid runs
remain in that immutable plan and never authorize a top-up. Take the maximum
run-level demand p99.9 and minimum run-level issue p0.1; these are
distribution-free 95%-confidence/95%-content run-level tolerance extremes.
Merge conservatively across producer, consumer, H0, and H1:

```text
ell_star = max(all eligible demand-latency upper limits)
c_star   = min(all eligible advancing-issue lower limits)
```

These 95%-confidence/95%-content statements are marginal for the demand
extreme and issue extreme. V1 does not claim that both hold simultaneously
with 95% confidence. The max/min merge is conservative across workers and
hardware states within each marginal statement. A joint confidence claim or
multiplicity adjustment is a different scientific decision and is not inferred
by implementation.

Require `c_star>0`, then use checked integer arithmetic:

```text
d1_slots  = ceil(cache_line_bytes / slot_bytes)
raw_slots = ceil(ell_star / c_star)
raw_lines = ceil(raw_slots / d1_slots)
cap_lines = floor((C/4) / d1_slots)
d2_lines  = min(max(2, raw_lines), cap_lines)
d2_slots  = d2_lines * d1_slots
```

The context is ineligible if `cap_lines<2`, `d2_slots<=d1_slots`, the cap
collapses R2 to R1, arithmetic overflows, or evidence is incomplete. The same
`d2_slots` and evidence ID bind both producer and consumer R2 sites and both
hardware states.

Q12 does not select a stand, capacity, line or slot size, duration, planned
count, minimum sequence count, namespace, seed, authority, budget, or actual
distance.

## Evidence

- The protocol and statistical owners answered
  `Q12 - accept the bundle` on 2026-08-21.
- Imported implementation specification Sections 4.1 and 4.2, exact
  inverse-ECDF rule, data dictionary, and calibration freeze-checklist row.
- Stage 6 exposes an external immutable distance parameter and rejects
  collapse without inventing a platform value.
- No treatment, calibration, pilot, confirmatory, latency, or throughput
  outcome was used to select this method.

## Consequences and compatibility

Scientific effect: conservative tail summaries and the cross-state merge can
increase distance or make a context ineligible. They prevent a favorable state
or treatment effect from selecting R2.

Compatibility effect: capture boundaries, advancing-operation eligibility,
quantiles, tolerance construction, required states/workers, context key,
geometry, marginal confidence boundary, rounding, minimum, cap, and collapse
rule are suite identity.

## Verification and acceptance tests

Stage 13 must test capture-boundary ordering, advancement-only intervals,
retained `FULL`/empty outcomes, both workers and hardware states, exact rank
selection, 58/59 valid-result boundaries, incomplete/zero/nonpositive series,
checked ceilings/floors, two-line minimum, quarter cap, collapse, context
mismatch, common-distance binding, canonical evidence, and material-change
invalidation using fake clocks and synthetic data only.

Assembly inspection may confirm required instrumentation and memory ordering,
but it cannot claim latency quality or qualify a stand.

## Rollback or supersession

Changing a boundary, eligible operation, quantile, tolerance construction,
state merge, context, geometry, minimum, cap, or collapse rule requires a new
method ID, prospective superseding ADR, and complete per-context
recalibration. Existing results remain immutable.

## Protocol-amendment assessment

No amendment is required because the protocol fixes the calibration structure
but leaves conservative summaries and exact boundaries open. If the accepted
acquire-demand boundary is found to conflict with the protocol's intended
scientific object, implementation must stop for owner clarification and, when
needed, a versioned amendment.
