# ADR-0178: Prospective Q16a duration discovery

- Status: `ACCEPTED`
- Date: 2026-10-30
- Decision ID: D-178
- Protocol version: `2.0.0-pre.3`, unchanged
- Scope: an accepted diagnostic setup study before formal D-037 collection
- Lifecycle gate: discovery design accepted; exact operational inputs and execution authority remain required

## Context

The owner suggests learning the duration and minimum observation requirements
from a run rather than supplying unsupported numerical values in advance.
D-037 requires both inputs before formal collection; it does not provide
defaults. Its 59 independent runs per hardware-state/context cannot be
extended or supplemented after viewing insufficient or unfavorable results.
The handoff explicitly separates diagnostic and calibration namespaces and
expects numerical calibration inputs to be supported by treatment-blind
measurements.

## Accepted sequence

Use a separately planned diagnostic study to learn whether candidate time
budgets produce the intended observation counts on this stand. Freeze the
candidate budgets, contexts, capture identities, seeds, resource limits,
validity checks, and selection rule before this diagnostic study starts.
Its raw data remain retained and identified as diagnostic-only. This is
not permission to relabel an attempted formal run retrospectively.

After completing the diagnostic study, produce a new typed D-037 plan with
the selected fixed duration, minimum counts, warm-up/reset behavior, exact
independent-run enumeration, and all prerequisite hashes. Formal Q16a uses
fresh run identities and seed namespaces; no diagnostic capture counts
toward its required 59 runs per state/context.

## Accepted candidate design

- Cover all 12 H0/H1, near/far, and working-set contexts of the prepared plan.
- Try requested measurement durations of 100 ms, 1 s, and 5 s once per
  context: 36 prospectively enumerated diagnostic captures, each with a fixed
  horizon. These are accepted experimental controls, not measured platform
  properties or already accepted formal durations.
- Use a planning minimum of 100,000 valid observations in each of the four
  producer/consumer demand/advancing-issue sequences. At that count, the
  0.1% probability mass corresponds to 100 order-statistic ranks. This is a
  planning rationale, not a confidence, effective-sample-size, independence,
  or quantile-accuracy guarantee. The owner accepts this discovery criterion;
  the subsequent formal plan still requires its prospective freeze.
- Count every sequence independently. In particular, 100,000 successful
  advancing demand observations yield only 99,999 between-demand issue
  intervals. The old 100,000-sample ceiling must not be mistaken for meeting
  the proposed minimum in every sequence.
- Choose the shortest candidate duration for which every required context
  passes the frozen count, clock, integrity, placement/residency, and resource
  checks. One diagnostic capture per candidate/context supplies setup
  evidence only; it does not prove that every later independent run will
  achieve that count or meet a tail-precision target.
- Use one common selected measurement duration across the context matrix in
  the subsequent formal plan. If no candidate qualifies, retain the entire
  diagnostic result and leave duration selection unresolved. Any further
  study requires a new prospective plan; do not extend this study until it
  succeeds.

## Access and stop rules

Duration selection consumes elapsed time, the four observation counts,
bounded-buffer/storage use, and mandatory validity evidence. Do not select
by p99.9/p0.1 values, candidate `d2`, package comparisons, favorable H0/H1
differences, or confirmatory outcomes. Keep any treatment-bearing summaries
out of the selection artifact. Required state/context identities remain
available to the operator for correct execution; no independent blinding
or auditor claim is made.

Every diagnostic capture stops at its declared time even if its count is
insufficient. A filled trace buffer is a retained failed/insufficient capture,
not permission to allocate more memory or lengthen the capture. Freeze
explicit buffer, durable-storage, timeout, and total-stand budgets after
checking actual available resources; this proposal supplies no fabricated
hardware capacities. Stop the study on mandatory hardware-control, integrity,
placement, clock, or restoration failure and retain partial evidence. Prove
restoration or quarantine the stand; never automatically retry.

Formal collection then uses its frozen duration and minimum-count rule.
Insufficient or otherwise invalid formal runs remain in the planned family;
they authorize no top-up, selective replacement, extension, or conversion to
diagnostic data. The accepted D-037 estimator and its eligibility gates
remain unchanged.

## Remaining prerequisites

The current capture loop does not implement the proposed fixed-duration
termination, warm-up/reset, or verified producer-home residency behavior.
The separately authored 10 ms warm-up record is not wired into that loop
and is not accepted by this proposal as a settling-time result. Resolve
and prospectively bind that behavior before the diagnostic study.

This proposal does not bypass the readiness state, source/release and
qualification invalidation rules, clean-candidate requirements, namespace
registration, finite signed action authority, or storage/custody gates. Do
not execute it under the formal Q16a action contract by merely changing its
label. Any necessary diagnostic action/schema changes require their own
recorded, tested implementation. If adopting this sequence changes a
protocol-fixed rule, obtain the versioned protocol amendment before the
affected implementation or collection.

## Disposition

On 2026-10-30 the owner answered `approve` to the exact discovery-plan
proposal. This accepts the candidate grid, 100,000-per-sequence planning
criterion, separation from formal collection, and selection/stop rules above.
It does not select the eventual duration, approve unmeasured hardware state,
waive implementation or release gates, create data, resolve an external
input, or issue the exact finite signed operational authorization. Existing
protocol snapshots, admitted evidence, and stopped attempts remain unchanged.
